"""Use the actual sibling MAGIC TaskPlanner, TaskRuntime and ExecutionGateway."""

import asyncio
import hashlib
import fcntl
import json
import os
import time
from pathlib import Path
from uuid import uuid4

from execution.contracts import ActionResult, AdapterCapabilities, EvidenceRef, VerificationResult
from execution.gateway import ExecutionGateway
from .mcp_compat import CompatibleMCPClientManager as MCPClientManager
from state.store import TaskStore
from tasks.models import TaskNode, TaskPlan
from tasks.planner import TaskPlanner
from tasks.runtime import TaskRuntime

from .contracts import SCHEMAS, validate
from .planner import StructuredPlanClient
from .settings import DUCK_ROOT, MAGIC_ROOT, ROOT, STATE, URL


def server_config():
    return {
        "name": "microduck",
        "transport": "stdio",
        "command": "bash",
        "args": [str(ROOT / "run.sh"), "mcp"],
        "env": {
            "MAGIC_ROOT": str(MAGIC_ROOT),
            "MICRODUCK_ROOT": str(DUCK_ROOT),
            "MAGIC_DUCK_STATE": str(STATE),
            "MICRODUCK_BRIDGE_URL": URL,
            "ROS_DOMAIN_ID": os.environ.get("ROS_DOMAIN_ID", "84"),
        },
    }


class MCPRobot:
    """Polling happens in the runtime, outside Cortex's five-round deduplication loop."""

    capabilities = AdapterCapabilities(query=True, cancel=True, idempotent=True, fencing=False)

    def __init__(self, client, event_sink=None):
        self.client = client
        self.poll = 0
        self.event_sink = event_sink
        self.observed_status = {}

    async def call(self, name, arguments):
        response = await asyncio.wait_for(
            self.client.call_tool("mcp_microduck_" + name, arguments), timeout=10
        )
        if response.is_error:
            raise RuntimeError(response.text)
        data = response.structured_content
        if isinstance(data, dict) and "result" in data and len(data) == 1:
            data = data["result"]
        if not isinstance(data, dict):
            data = json.loads(response.text)
        if "error" in data:
            raise RuntimeError(data)
        return data

    def receipt(self, value):
        if self.event_sink and self.observed_status.get(value["command_id"]) != value["status"]:
            self.observed_status[value["command_id"]] = value["status"]
            self.event_sink("action", value)
        evidence = ()
        if value["status"] == "SUCCEEDED":
            raw = json.dumps(value, sort_keys=True, allow_nan=False).encode()
            evidence = (
                EvidenceRef(
                    value["command_id"] + ":receipt",
                    "microduck_ros_observation",
                    value["updated_at"],
                    uri=URL + "/actions/" + value["command_id"],
                    digest=hashlib.sha256(raw).hexdigest(),
                ),
            )
        return ActionResult(
            value["command_id"],
            value["status"],
            effect="unknown" if value["status"] == "UNKNOWN" else "known",
            detail=value["detail"],
            error_code=value.get("error_code"),
            data=value,
            evidence=evidence,
        )

    async def execute(self, request):
        validate(request.skill, request.arguments)
        return self.receipt(
            await self.call(
                "submit_action",
                dict(skill=request.skill, arguments=request.arguments, command_id=request.command_id),
            )
        )

    async def query(self, command_id):
        self.poll += 1
        return self.receipt(
            await self.call("get_action_status", dict(command_id=command_id, observation_token=self.poll))
        )

    async def cancel(self, command_id, reason):
        return self.receipt(await self.call("cancel_action", {"command_id": command_id}))


def verify_observation(node, result, world):
    if result.status != "SUCCEEDED" or not result.evidence:
        return VerificationResult("INCONCLUSIVE", "No confirmed execution observation")
    data = result.data.get("data", {})
    if not data.get("verification"):
        return VerificationResult("INCONCLUSIVE", "Missing domain verification")
    if node.skill in ("navigate", "navigate_to") and data.get("error_m", 99) > 0.3:
        return VerificationResult("FAIL", "Arrival not verified", result.evidence)
    if node.skill == "walk" and data.get("progress", -1) < abs(node.arguments["distance_m"]):
        return VerificationResult("FAIL", "Walking displacement not reached", result.evidence)
    if node.skill == "snapshot" and not Path(data.get("path", "")).is_file():
        return VerificationResult("FAIL", "Camera artifact missing", result.evidence)
    return VerificationResult("PASS", data["verification"], result.evidence)


def normalize_plan(plan):
    """Bound model output and force explicit serial resource ownership."""
    if len(plan.nodes) > 12:
        raise ValueError("At most 12 actions per task")
    nodes = []
    for node in plan.nodes:
        validate(node.skill, node.arguments)
        if node.condition or node.preconditions:
            raise ValueError("Conditional tasks need a registered domain predicate")
        dependencies = tuple(dict.fromkeys((*node.depends_on, *((nodes[-1].node_id,) if nodes else ()))))
        nodes.append(
            TaskNode(
                node.node_id,
                node.skill,
                node.arguments,
                depends_on=dependencies,
                resources=("microduck",),
                verifier="microduck_observation",
                timeout_seconds=200,
            )
        )
    return TaskPlan(plan.goal, tuple(nodes))


def load_plan(path):
    value = json.loads(Path(path).read_text())
    return normalize_plan(TaskPlan(value["goal"], tuple(TaskNode(**n) for n in value["nodes"])))


class Session:
    def __init__(self, database=None, event_sink=None):
        self.client = MCPClientManager([server_config()])
        self.database = database or STATE / "tasks.sqlite3"
        self.store = None
        self._runner_lock = None
        self.event_sink = event_sink

    async def __aenter__(self):
        try:
            Path(self.database).parent.mkdir(parents=True, exist_ok=True)
            self._runner_lock = Path(str(self.database) + ".runner.lock").open("w")
            fcntl.flock(self._runner_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            await self.client.start()
            self.robot = MCPRobot(self.client, self.event_sink)
            state = await self.robot.call("get_state", {})
            if not state["ready"]:
                raise RuntimeError("Simulator is not ready; start sim/nav and bridge first")
            self.store = TaskStore(self.database)
            # One bridge process is one execution site: its session_id is the binding.
            # Deriving the robot_id from it keeps repeated launches from colliding with
            # the identity recorded by an earlier launch (MAGIC's own convention).
            self.gateway = ExecutionGateway(
                self.store,
                {s: self.robot for s in SCHEMAS},
                robot_id=f"microduck:{state['session_id']}",
                binding_id=state["session_id"],
            )
            self.runtime = TaskRuntime(
                self.store, self.gateway, verifiers={"microduck_observation": verify_observation}
            )
            self.state = state
            return self
        except BaseException:
            await self.client.stop()
            if self.store:
                self.store.close()
            if self._runner_lock:
                self._runner_lock.close()
            raise

    async def __aexit__(self, *_):
        await self.client.stop()
        if self.store:
            self.store.close()
        if self._runner_lock:
            self._runner_lock.close()

    async def execute(self, plan, run_id=None, timeout=300, cancel_event=None):
        plan = normalize_plan(plan)
        run_id = run_id or uuid4().hex
        self.runtime.create(run_id, plan, max_actions=12, max_replans=0, deadline=time.time() + timeout)
        deadline = time.monotonic() + timeout
        last = None
        cancelling = False
        try:
            while time.monotonic() < deadline:
                if cancel_event and cancel_event.is_set() and not cancelling:
                    await self.runtime.cancel(run_id, "Interactive stop requested")
                    cancelling = True
                result = await self.runtime.step(run_id)
                state = self.runtime.status(run_id)
                summary = [(n["node_id"], n["state"]) for n in state["nodes"]]
                status = state["run"]["state"]
                if (status, summary) != last:
                    update = {"run_id": run_id, "state": status, "nodes": summary}
                    if self.event_sink:
                        self.event_sink("task", update)
                    else:
                        print(json.dumps(update, ensure_ascii=False), flush=True)
                    last = (status, summary)
                if status in ("SUCCEEDED", "FAILED", "PARTIAL", "CANCELLED", "WAITING_FOR_INPUT"):
                    return state
                if (result and result.status == "UNKNOWN") or any(
                    a["status"] == "UNKNOWN" for a in state["pending_actions"]
                ):
                    self.runtime.pause(run_id)
                    return self.runtime.status(run_id)
                await asyncio.sleep(0.25)
            await self.runtime.cancel(run_id, "Task deadline exceeded")
            return self.runtime.status(run_id)
        except BaseException:
            await self.runtime.cancel(run_id, "Runner interrupted")
            raise

    async def propose(self, goal, config_path=None, vision=False, context_extra=None):
        from dotenv import load_dotenv
        from llm import load_llm
        from runtime.env import load_env_vars
        import json5

        load_dotenv(ROOT / ".env", override=False)
        # Reuse the user's existing model settings without copying credentials.
        load_dotenv(MAGIC_ROOT / ".env", override=False)
        config_path = config_path or os.environ.get("MAGIC_LLM_CONFIG")
        if config_path:
            raw = json5.loads(Path(config_path).read_text())
            config = load_env_vars(raw.get("cortex_llm", raw))
        else:
            required = ("MAGIC_LLM_BASE_URL", "MAGIC_LLM_MODEL", "MAGIC_LLM_API_KEY")
            for target, source in zip(
                required, ("BENCHMARK_BASE_URL", "BENCHMARK_MODEL", "BENCHMARK_API_KEY")
            ):
                if not os.environ.get(target) and os.environ.get(source):
                    os.environ[target] = os.environ[source]
            if not all(os.environ.get(k) for k in required):
                raise ValueError("Set MAGIC_LLM_BASE_URL, MAGIC_LLM_MODEL and MAGIC_LLM_API_KEY in .env")
            config = {
                "type": "OpenAILLM",
                "config": {
                    "base_url": os.environ[required[0]],
                    "model": os.environ[required[1]],
                    "api_key": os.environ[required[2]],
                    "history_length": 0,
                    "timeout": 45,
                },
            }
        client = load_llm(config, available_actions=[])
        # This runner has no avatar UI. Avoid spawning its unrelated Zenoh provider.
        client._skip_state_management = True
        try:
            frame = None
            if vision:
                from .client import BridgeClient

                frame = (await BridgeClient().request("/image"))["base64"]
            planner = TaskPlanner(StructuredPlanClient(client, goal, frame), self.runtime, SCHEMAS)
            context = await self.robot.call("get_state", {})
            if context_extra:
                context["conversation"] = context_extra
            plan = await planner.propose(
                goal,
                constraints=[
                    "Simulation only. At most 12 actions in execution order; dependencies must reference earlier nodes.",
                    "Use microduck_observation as verifier. Do not use conditions or unregistered predicates.",
                    "Standing precedes walking if seated. Named rooms must come from state.places.",
                    "snapshot saves an image; it does not prove recognition of objects.",
                    "Never add unrequested movement. Stop if observations cannot ground the requested task.",
                ],
                context=context,
                timeout_seconds=50,
            )
            return normalize_plan(plan)
        finally:
            underlying = getattr(client, "_client", None)
            if underlying:
                await underlying.close()

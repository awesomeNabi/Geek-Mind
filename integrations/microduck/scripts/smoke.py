"""Real simulator/MCP/MAGIC test; optional --live-llm uses the configured model API."""

import argparse
import asyncio
import json
import os
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

parser = argparse.ArgumentParser()
parser.add_argument("--nav", action="store_true", help="Also test Nav2 arrival and cancellation")
parser.add_argument(
    "--live-llm", action="store_true", help="Use existing MAGIC model credentials instead of a fixture"
)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
state = root / ".runtime" / ("smoke-" + uuid4().hex[:8])
state.mkdir(parents=True)
os.environ.update(
    MAGIC_DUCK_STATE=str(state), ROS_DOMAIN_ID="85", MICRODUCK_BRIDGE_URL="http://127.0.0.1:8767"
)

# Imports must follow the isolated test environment settings.
from magic_microduck.client import BridgeClient  # noqa: E402
from magic_microduck.magic_runtime import Session  # noqa: E402

fixture = json.loads((root / "config/demo-plan.json").read_text())
for i, node in enumerate(fixture["nodes"]):
    node["verifier"] = "microduck_observation"
    node["depends_on"] = [fixture["nodes"][i - 1]["node_id"]] if i else []


class ModelFixture(BaseHTTPRequestHandler):
    calls = 0

    def log_message(self, *_):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert body["tools"][0]["function"]["name"] == "propose_task_plan"
        assert fixture["goal"] in json.dumps(body["messages"], ensure_ascii=False)
        ModelFixture.calls += 1
        value = {
            "id": "test-plan",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "local-fixture",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "plan",
                                "type": "function",
                                "function": {"name": "propose_task_plan", "arguments": json.dumps(fixture)},
                            }
                        ],
                    },
                }
            ],
        }
        data = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


async def wait_job(client, value, timeout=60):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = await client.status(value["command_id"])
        if value["status"] in ("SUCCEEDED", "FAILED", "CANCELLED", "UNKNOWN"):
            return value
        await asyncio.sleep(0.2)
    raise AssertionError(value)


async def test():
    client = BridgeClient()
    end = time.monotonic() + 90
    while time.monotonic() < end:
        for process in processes:
            assert process.poll() is None, "Simulator or bridge exited early; inspect logs"
        try:
            status = await client.state()
            if status["ready"] and (not args.nav or status["navigation_available"]):
                break
        except Exception:
            pass
        await asyncio.sleep(0.5)
    else:
        raise AssertionError("Simulator/bridge did not become ready")
    before = await client.state()
    async with Session(state / "tasks.sqlite3") as session:
        plan = await session.propose(fixture["goal"])
        result = await session.execute(plan, timeout=90)
        assert result["run"]["state"] == "SUCCEEDED", result
        if not args.live_llm:
            assert ModelFixture.calls == 1
        image = await session.client.call_tool("mcp_microduck_get_image", {})
        assert not image.is_error and any(b["type"] == "image" for b in image.content)
        tools = [t["function"]["name"] for t in session.client.get_tool_schemas()]
    after = await client.state()
    motion = await client.start("walk", {"distance_m": 1}, "cancel-walk")
    await asyncio.sleep(0.5)
    await client.cancel(motion["command_id"])
    cancelled = await wait_job(client, motion)
    assert cancelled["status"] == "CANCELLED", cancelled
    turn = await client.start("turn", {"degrees": 30}, "turn-probe")
    turned = await wait_job(client, turn)
    assert turned["status"] == "SUCCEEDED", turned
    nav_results = {}
    if args.nav:
        await client.request("/reset", {})
        goal = await client.start("navigate", {"place": "corridor north"}, "nav-arrival")
        nav_results["arrival"] = await wait_job(client, goal, timeout=100)
        assert nav_results["arrival"]["status"] == "SUCCEEDED", nav_results
        goal = await client.start("navigate", {"place": "kitchen"}, "nav-cancel")
        await asyncio.sleep(1)
        await client.cancel(goal["command_id"])
        nav_results["cancel"] = await wait_job(client, goal, timeout=15)
        assert nav_results["cancel"]["status"] == "CANCELLED", nav_results
    return {
        "planner": "actual MAGIC OpenAILLM + TaskPlanner, "
        + ("live model" if args.live_llm else "deterministic local fixture"),
        "execution": "actual MAGIC TaskRuntime + ExecutionGateway + MCPClientManager",
        "run": result,
        "tools": tools,
        "before": before,
        "after": after,
        "cancelled_walk": cancelled,
        "turn": turned,
        "navigation": nav_results,
        "mcp_image": True,
    }


processes, logs = [], []
model = ThreadingHTTPServer(("127.0.0.1", 0), ModelFixture)
threading.Thread(target=model.serve_forever, daemon=True).start()
if not args.live_llm:
    os.environ.update(
        MAGIC_LLM_BASE_URL=f"http://127.0.0.1:{model.server_port}/v1",
        MAGIC_LLM_MODEL="local-fixture",
        MAGIC_LLM_API_KEY="local-fixture",
    )
    os.environ.pop("MAGIC_LLM_CONFIG", None)
try:
    sim = ["nav", "agent:=false", "camera_rate:=2.0"] if args.nav else ["sim", "camera_rate:=2.0"]
    for name, cmd in [("sim", sim), ("bridge", ["bridge", "--port", "8767"])]:
        log = (state / f"{name}.log").open("w")
        logs.append(log)
        processes.append(
            subprocess.Popen(
                ["bash", str(root / "run.sh"), *cmd],
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        )
    result = asyncio.run(test())
    (state / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print("PASS: " + str(state / "result.json"), flush=True)
finally:
    for process in reversed(processes):
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=25)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    for log in logs:
        log.close()
    model.shutdown()
    model.server_close()

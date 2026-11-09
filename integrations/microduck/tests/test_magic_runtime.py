import time
import json
from types import SimpleNamespace

import pytest
from tasks.models import TaskNode, TaskPlan

from magic_microduck.magic_runtime import Session, normalize_plan


class FakeMCP:
    """Test transport only; the actual MAGIC task kernel is exercised."""

    def __init__(self, fail=False):
        self.jobs, self.starts, self.queries = {}, [], 0
        self.fail = fail

    async def start(self):
        pass

    async def stop(self):
        pass

    async def call_tool(self, name, args):
        name = name.removeprefix("mcp_microduck_")
        if name == "get_state":
            value = {"ready": True, "session_id": "fake-binding"}
        elif name == "submit_action":
            assert not any(j["status"] == "RUNNING" for j in self.jobs.values())
            self.starts.append(args["skill"])
            value = {
                "command_id": args["command_id"],
                "skill": args["skill"],
                "status": "RUNNING",
                "detail": "accepted",
                "data": {},
                "updated_at": time.time(),
            }
            self.jobs[args["command_id"]] = value
        elif name == "get_action_status":
            self.queries += 1
            value = self.jobs[args["command_id"]]
            if self.queries % 2 == 0:
                value.update(
                    status="FAILED" if self.fail else "SUCCEEDED",
                    updated_at=time.time(),
                    data={"verification": "observed"},
                )
        elif name == "cancel_action":
            value = self.jobs[args["command_id"]]
            value.update(status="CANCELLED")
        else:
            raise AssertionError(name)
        return SimpleNamespace(is_error=False, structured_content=value, text="")


def test_plan_rejects_invalid_args_and_forces_serial_order():
    plan = normalize_plan(
        TaskPlan(
            "look twice",
            (TaskNode("one", "look", {"direction": "left"}), TaskNode("two", "look", {"direction": "right"})),
        )
    )
    assert plan.nodes[1].depends_on == ("one",)
    assert plan.nodes[0].resources == ("microduck",)
    with pytest.raises(ValueError):
        normalize_plan(TaskPlan("bad", (TaskNode("bad", "walk", {"distance_m": 100}),)))


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True])
async def test_actual_magic_runtime_waits_and_does_not_repeat(tmp_path, fail):
    session = Session(tmp_path / "tasks.sqlite3")
    transport = session.client = FakeMCP(fail)
    async with session:
        plan = TaskPlan(
            "look twice",
            (TaskNode("one", "look", {"direction": "left"}), TaskNode("two", "look", {"direction": "right"})),
        )
        result = await session.execute(plan, timeout=8)
        assert result["run"]["state"] == ("FAILED" if fail else "SUCCEEDED")
        assert len(transport.starts) == (1 if fail else 2)
        assert transport.queries >= 2


def test_mcp_configuration_keeps_bridge_routing():
    from magic_microduck.magic_runtime import server_config
    from magic_microduck.settings import URL, STATE

    config = server_config()
    assert config["env"]["MICRODUCK_BRIDGE_URL"] == URL
    assert config["env"]["MAGIC_DUCK_STATE"] == str(STATE)
    assert all("KEY" not in k for k in config["env"])


def test_missing_bridge_reports_startup_hint_not_crash(monkeypatch):
    """A stopped simulator must read as a startup problem, never as `Error executing tool`."""
    import asyncio

    from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError

    from magic_microduck import mcp_server
    from magic_microduck.client import BridgeClient, BridgeUnavailable

    # Port 1 on loopback refuses immediately, so the test needs no simulator.
    client = BridgeClient("http://127.0.0.1:1")
    with pytest.raises(BridgeUnavailable) as caught:
        client.request_sync("/state")
    assert "bash run.sh up" in str(caught.value)

    monkeypatch.setattr(mcp_server, "client", client)
    with pytest.raises(ToolError) as tool_error:
        asyncio.run(mcp_server.server.call_tool("get_state", {}, None))
    assert not isinstance(tool_error.value, UnexpectedToolError)
    assert "bash run.sh up" in str(tool_error.value)


@pytest.mark.asyncio
async def test_sdk_v2_tool_schema_adapter():
    from magic_microduck.mcp_compat import SessionView
    from mcp.types import Tool

    class SDK:
        async def list_tools(self):
            return SimpleNamespace(
                tools=[Tool(name="state", description="read", input_schema={"type": "object"})]
            )

    result = await SessionView(SDK()).list_tools()
    assert result.tools[0].inputSchema == {"type": "object"}


@pytest.mark.asyncio
async def test_single_task_runner_ownership(tmp_path):
    first = Session(tmp_path / "tasks.sqlite3")
    first.client = FakeMCP()
    second = Session(tmp_path / "tasks.sqlite3")
    second.client = FakeMCP()
    async with first:
        with pytest.raises(BlockingIOError):
            async with second:
                raise AssertionError("Second task owner should not start")


@pytest.mark.asyncio
@pytest.mark.parametrize("wrong_id", [False, True])
async def test_model_plan_schema_rejects_ambiguous_node_fields(wrong_id):
    from jsonschema import ValidationError
    from magic_microduck.planner import StructuredPlanClient

    class LLM:
        function_schemas = []

        async def ask(self, prompt):
            schema = self.function_schemas[0]["function"]["parameters"]
            assert "node_id" in schema["properties"]["nodes"]["items"]["required"]
            assert schema["properties"]["goal"]["enum"] == ["look"]
            node = {
                "id" if wrong_id else "node_id": "look",
                "skill": "look",
                "arguments": {"direction": "left"},
                "depends_on": [],
                "verifier": "microduck_observation",
            }
            return SimpleNamespace(
                actions=[
                    SimpleNamespace(
                        type="propose_task_plan", value=json.dumps({"goal": "look", "nodes": [node]})
                    )
                ]
            )

    llm = LLM()
    client = StructuredPlanClient(llm, "look")
    if wrong_id:
        with pytest.raises(ValidationError):
            await client.ask("look")
    else:
        assert (await client.ask("look")).actions
    assert llm.function_schemas == []

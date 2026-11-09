import asyncio
import curses
import json
import time
from types import SimpleNamespace

import pytest
from tasks.models import TaskNode, TaskPlan

from magic_microduck.console import InteractiveConsole, Terminal
from magic_microduck.live import LiveState
from magic_microduck.magic_runtime import Session
from test_magic_runtime import FakeMCP


@pytest.mark.asyncio
@pytest.mark.parametrize("during_action", [False, True])
async def test_interactive_stop_prevents_following_actions(tmp_path, during_action):
    cancel = asyncio.Event()
    events = []

    def receive(kind, value):
        events.append((kind, value))
        if during_action and kind == "action" and value["status"] == "RUNNING":
            cancel.set()

    session = Session(tmp_path / "tasks.sqlite3", event_sink=receive)
    transport = session.client = FakeMCP()
    if not during_action:
        cancel.set()
    async with session:
        plan = TaskPlan(
            "look twice",
            (TaskNode("one", "look", {"direction": "left"}), TaskNode("two", "look", {"direction": "right"})),
        )
        result = await session.execute(plan, cancel_event=cancel, timeout=5)
    assert result["run"]["state"] == "CANCELLED"
    assert len(transport.starts) == int(during_action)
    assert events and events[-1][0] == "task"


def test_camera_freshness_and_bounded_event_journal(tmp_path):
    live = LiveState(tmp_path)
    live.set_frame("head", (b"jpeg", time.time()))
    live.set_frame("follow", (b"old", time.time() - 4))
    assert live.frame("head")[0] == b"jpeg"
    assert live.frame("follow") is None
    for i in range(210):
        live.emit("info", {"text": str(i)})
    assert len(live.snapshot()["events"]) == 200
    assert not live.snapshot()["cameras"]["follow"]["fresh"]
    live.close()
    assert len((tmp_path / "events.jsonl").read_text().splitlines()) == 210


def test_chinese_input_editing_and_history():
    terminal = Terminal(None)
    for char in "向前走":
        terminal.key(char)
    terminal.key(curses.KEY_LEFT)
    terminal.key("慢")
    assert terminal.key("\n") == "向前慢走"
    terminal.key(curses.KEY_UP)
    terminal.key(curses.KEY_BACKSPACE)
    assert terminal.key("\n") == "向前慢"
    assert terminal.key("\x04") == "/quit"


@pytest.mark.asyncio
async def test_immediate_stop_is_not_lost_before_goal_task_starts():
    app = InteractiveConsole.__new__(InteractiveConsole)
    app.goal_task = None
    app.ready = True
    app.stop_event = asyncio.Event()
    app.live = SimpleNamespace(snapshot=lambda: {"robot": {"ready": True}})
    app.emit = lambda *args, **kwargs: None
    app.phase = lambda *args, **kwargs: None

    class Bridge:
        async def stop(self):
            return {"detail": "stop requested"}

    app.bridge = Bridge()

    async def goal(_):
        assert app.stop_event.is_set()

    app.run_goal = goal
    await app.command("坐下")
    await app.command("/stop")
    await app.goal_task


def test_web_frame_and_state_are_read_only_and_expire(tmp_path):
    from magic_microduck.live import LiveServer
    from urllib.request import build_opener, ProxyHandler, Request
    from urllib.error import HTTPError

    live = LiveState(tmp_path)
    live.emit("goal", {"text": "<script>untrusted goal</script>"})
    live.set_frame("head", (b"jpeg bytes", time.time()))
    web = LiveServer(live, 0)
    base = f"http://127.0.0.1:{web.port}"
    client = build_opener(ProxyHandler({}))
    try:
        with client.open(base + "/api/state") as response:
            assert json.load(response)["goal"] == "<script>untrusted goal</script>"
        with client.open(base + "/frame.jpg?view=head") as response:
            assert response.read() == b"jpeg bytes"
        with pytest.raises(HTTPError) as error:
            client.open(base + "/frame.jpg?view=follow")
        assert error.value.code == 503
        with pytest.raises(HTTPError):
            client.open(Request(base + "/command", data=b"{}"))
    finally:
        web.close()
        live.close()

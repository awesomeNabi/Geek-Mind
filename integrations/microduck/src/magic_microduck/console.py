"""One-command interactive MAGIC terminal with a continuously updated live viewer."""

import argparse
import asyncio
import contextlib
import curses
import fcntl
import json
import logging
import os
import signal
import subprocess
import sys
import time
import webbrowser
from uuid import uuid4

from rich.cells import cell_len, set_cell_size

from .client import BridgeClient
from .live import LiveServer, LiveState
from .magic_runtime import Session, load_plan
from .settings import ROOT, STATE

PHASES = {
    "STARTING": "启动中",
    "READY": "等待指令",
    "PLANNING": "MAGIC 规划中",
    "EXECUTING": "执行中",
    "STOPPING": "停止中",
    "ERROR": "发生错误",
    "CLOSED": "已关闭",
}
NODE_STATES = {
    "PENDING": "待执行",
    "BLOCKED": "执行中",
    "RUNNING": "执行中",
    "VERIFYING": "验证中",
    "SUCCEEDED": "已完成",
    "FAILED": "失败",
    "CANCELLED": "已取消",
    "SKIPPED": "已跳过",
}
HELP = "输入自然语言并回车；/stop 停止任务 /demo 演示 /state 状态 /reset 重置 /help 帮助 /quit 退出"


class InteractiveConsole:
    def __init__(self, args):
        self.args = args
        STATE.mkdir(parents=True, exist_ok=True)
        self.guard = (STATE / "console.lock").open("w")
        fcntl.flock(self.guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.directory = STATE / ("console-" + uuid4().hex[:8])
        self.directory.mkdir()
        self.live = LiveState(self.directory)
        self.web = LiveServer(self.live, args.port)
        self.url = f"http://127.0.0.1:{self.web.port}"
        self.bridge = BridgeClient()
        self.children, self.logs, self.pollers = [], [], []
        self.goal_task = None
        self.stop_event = asyncio.Event()
        self.quit_event = asyncio.Event()
        self.ready = False
        self.owned_stack = False
        self.history = []
        logging.basicConfig(filename=str(self.directory / "agent.log"), level=logging.WARNING)

    def emit(self, kind, **data):
        self.live.emit(kind, data)

    def phase(self, value, text):
        self.emit("phase", phase=value, text=text)

    def spawn(self, name, arguments):
        log = (self.directory / f"{name}.log").open("w")
        self.logs.append(log)
        process = subprocess.Popen(
            ["bash", str(ROOT / "run.sh"), *arguments],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.children.append((name, process))
        return process

    async def start(self):
        self.emit("info", text=f"实时画面：{self.url}  |  运行记录：{self.directory}")
        self.emit("info", text=HELP)
        try:
            existing = await self.bridge.state()
        except Exception:
            existing = None
        if existing is None:
            command = ["up", "--no-camera"] + (["--flat"] if self.args.flat else [])
            self.spawn("stack", command)
            self.owned_stack = True
            self.emit("info", text="启动仿真、策略与 ROS 桥接器…")
        else:
            self.emit("info", text="接入已运行的桥接器；退出时保留原有仿真进程。")
        # An attached normal stack already publishes the head camera.
        observer = [
            "observer",
            "--scene",
            "flat" if self.args.flat else "apartment",
            "--fps",
            str(self.args.fps),
        ]
        if existing and existing.get("ages_seconds", {}).get("image", 99) < 2:
            observer.append("--no-head")
        self.spawn("observer", observer)
        self.pollers = [
            asyncio.create_task(self.telemetry()),
            asyncio.create_task(self.camera("head")),
            asyncio.create_task(self.camera("follow")),
        ]
        deadline = time.monotonic() + 100
        while not self.quit_event.is_set():
            for name, process in self.children:
                if process.poll() is not None:
                    raise RuntimeError(f"{name} 提前退出，请查看 {self.directory / (name + '.log')}")
            state = self.live.snapshot()
            if state["robot"].get("ready") and self.live.frame("head") and self.live.frame("follow"):
                if self.args.flat or state["robot"].get("navigation_available"):
                    self.ready = True
                    self.phase("READY", "仿真、实时画面与 MAGIC 入口已就绪，请输入指令。")
                    if not self.args.no_browser and (
                        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
                    ):
                        webbrowser.open(self.url)
                    return
            if time.monotonic() > deadline:
                raise RuntimeError(f"启动等待超时，请查看 {self.directory}")
            await asyncio.sleep(0.2)

    async def telemetry(self):
        disconnected = False
        while True:
            try:
                value = await self.bridge.state()
                self.live.update_robot(value)
                if disconnected:
                    self.emit("info", text="机器人状态连接已恢复。")
                disconnected = False
            except Exception:
                self.live.update_robot({"ready": False})
                if self.ready and not disconnected:
                    self.emit("error", text="机器人状态连接断开，等待重新连接。")
                disconnected = True
            await asyncio.sleep(0.4)

    async def camera(self, view):
        while True:
            try:
                value = await asyncio.to_thread(self.bridge.frame_sync, view)
                self.live.set_frame(view, value)
            except Exception:
                pass  # Old frames expire and the viewer explicitly displays offline.
            await asyncio.sleep(1 / self.args.fps)

    async def run_goal(self, goal, demo=False):
        self.emit("goal", text=goal)
        self.phase("PLANNING", "读取机器人当前状态，生成动作计划…")
        result_path = self.directory / f"task-{uuid4().hex}.json"
        try:
            async with Session(event_sink=self.live.emit) as session:
                if self.stop_event.is_set():
                    self.emit("info", text="任务已取消，没有下发新动作。")
                    return
                if demo:
                    plan = load_plan(ROOT / "config/demo-plan.json")
                else:
                    proposal = asyncio.create_task(
                        session.propose(
                            goal, self.args.llm_config, self.args.vision, context_extra=self.history[-6:]
                        )
                    )
                    stopped = asyncio.create_task(self.stop_event.wait())
                    try:
                        await asyncio.wait([proposal, stopped], return_when=asyncio.FIRST_COMPLETED)
                        if self.stop_event.is_set():
                            self.emit("info", text="规划已取消，没有下发新动作。")
                            return
                        plan = await proposal
                    finally:
                        for task in (proposal, stopped):
                            if not task.done():
                                task.cancel()
                        await asyncio.gather(proposal, stopped, return_exceptions=True)
                if self.stop_event.is_set():
                    return
                payload = {"goal": plan.goal, "nodes": [n.to_dict() for n in plan.nodes]}
                plan_path = result_path.with_suffix(".plan.json")
                plan_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
                self.live.emit("plan", {**payload, "path": str(plan_path)})
                self.phase("EXECUTING", "计划通过校验，开始执行；可随时输入 /stop。")
                result = await session.execute(plan, cancel_event=self.stop_event)
                result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
                status = result["run"]["state"]
                self.history.append({"goal": goal, "result": status})
                self.emit("result", text=f"任务结束：{status}；执行记录：{result_path}", status=status)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.emit("error", text=str(exc))
        finally:
            self.phase("READY", "可输入下一条指令。")

    async def command(self, text):
        text = text.strip()
        if not text:
            return
        if text in ("/quit", "/exit"):
            self.quit_event.set()
            return
        if text == "/help":
            self.emit("info", text=HELP)
            return
        if text == "/state":
            self.emit("info", text=json.dumps(self.live.snapshot()["robot"], ensure_ascii=False))
            return
        busy = self.goal_task is not None and not self.goal_task.done()
        if text in ("/stop", "停止", "停下", "停止执行", "取消任务"):
            self.stop_event.set()
            self.phase("STOPPING", "停止后续动作，等待控制器确认；训练策略需等待自然结束。")
            # The task loop cancels admission before any new dispatch; direct bridge stop also
            # covers independent external commands, and is never used as proof of completion.
            response = await self.bridge.stop()
            self.emit("info", text=response["detail"])
            if not busy:
                self.phase("READY", "停止请求已发送；实际状态见动作回执。")
            return
        if busy:
            self.emit("info", text="当前任务尚未结束。输入 /stop 取消，或等待结束后发送下一条指令。")
            return
        if not self.ready or not self.live.snapshot()["robot"].get("ready"):
            self.emit("error", text="机器人尚未就绪，请等待状态恢复。")
            return
        if text == "/reset":
            await self.bridge.request("/reset", {})
            self.emit("info", text="仿真已重置，历史不确定动作已关闭。")
        elif text == "/demo":
            goal = json.loads((ROOT / "config/demo-plan.json").read_text())["goal"]
            self.stop_event = asyncio.Event()
            self.goal_task = asyncio.create_task(self.run_goal(goal, demo=True))
        elif text.startswith("/"):
            self.emit("error", text="未知命令；输入 /help 查看帮助。")
        elif len(text) > 2000:
            self.emit("error", text="请将单次指令限制在 2000 字以内。")
        else:
            self.stop_event = asyncio.Event()
            self.goal_task = asyncio.create_task(self.run_goal(text))

    async def close(self):
        self.phase("STOPPING", "正在关闭交互控制台…")
        self.stop_event.set()
        if self.goal_task and not self.goal_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self.goal_task), timeout=12)
            except asyncio.TimeoutError:
                self.goal_task.cancel()
                await asyncio.gather(self.goal_task, return_exceptions=True)
        for task in self.pollers:
            task.cancel()
        await asyncio.gather(*self.pollers, return_exceptions=True)
        for name, process in reversed(self.children):
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:
                    await asyncio.to_thread(process.wait, timeout=45 if name == "stack" else 10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    await asyncio.to_thread(process.wait)
        for log in self.logs:
            log.close()
        self.phase("CLOSED", "控制台已退出。")
        await asyncio.to_thread(self.web.close)
        self.live.close()
        self.guard.close()


def clean(text):
    return "".join(c for c in str(text) if c.isprintable())


class Terminal:
    def __init__(self, screen):
        self.screen = screen
        self.text, self.cursor = "", 0
        self.history, self.history_at = [], 0
        if screen:
            screen.nodelay(True)
            with contextlib.suppress(curses.error):
                curses.curs_set(1)

    def key(self, key):
        if key in ("\n", "\r", curses.KEY_ENTER):
            value = self.text
            if value:
                self.history.append(value)
            self.history_at = len(self.history)
            self.text, self.cursor = "", 0
            return value
        if key == "\x04":
            return "/quit"
        if key in (curses.KEY_BACKSPACE, "\x7f", "\b"):
            if self.cursor:
                self.text = self.text[: self.cursor - 1] + self.text[self.cursor :]
                self.cursor -= 1
        elif key == curses.KEY_DC:
            self.text = self.text[: self.cursor] + self.text[self.cursor + 1 :]
        elif key == curses.KEY_LEFT:
            self.cursor = max(0, self.cursor - 1)
        elif key == curses.KEY_RIGHT:
            self.cursor = min(len(self.text), self.cursor + 1)
        elif key in (curses.KEY_UP, curses.KEY_DOWN):
            self.history_at = min(
                len(self.history), max(0, self.history_at + (-1 if key == curses.KEY_UP else 1))
            )
            self.text = self.history[self.history_at] if self.history_at < len(self.history) else ""
            self.cursor = len(self.text)
        elif isinstance(key, str) and key.isprintable() and len(self.text) < 2000:
            self.text = self.text[: self.cursor] + key + self.text[self.cursor :]
            self.cursor += len(key)

    def draw(self, app):
        screen = self.screen
        rows, cols = screen.getmaxyx()
        screen.erase()

        def put(y, x, text, width=None, attr=0):
            if 0 <= y < rows and 0 <= x < cols:
                with contextlib.suppress(curses.error):
                    screen.addstr(
                        y,
                        x,
                        set_cell_size(clean(text), max(0, min(width or cols - x - 1, cols - x - 1))),
                        attr,
                    )

        state = app.live.snapshot()
        put(0, 1, f"MAGIC / MICRODUCK    {PHASES.get(state['phase'], state['phase'])}", attr=curses.A_BOLD)
        put(1, 1, f"实时画面 {app.url}  (SSH 用户请转发此端口到本地)")
        robot = state["robot"]
        pose = robot.get("pose", {})
        put(
            2,
            1,
            f"机器人 {'在线' if robot.get('ready') else '离线'} | 策略 {robot.get('policy_state', '—')} | "
            f"位置 ({pose.get('x', 0):.3f}, {pose.get('y', 0):.3f}) | 朝向 {pose.get('yaw_degrees', 0):.1f}°",
        )
        put(3, 1, "目标：" + (state["goal"] or "等待输入自然语言指令"))
        if rows >= 16 and cols >= 75:
            left = max(26, cols // 3)
            put(5, 1, "动作计划", left - 2, curses.A_BOLD)
            for i, node in enumerate(state["plan"][: max(0, (rows - 10) // 2)]):
                status = state["node_states"].get(node["node_id"], "PENDING")
                put(6 + i * 2, 1, f"{i + 1}. {NODE_STATES.get(status, status)} {node['skill']}", left - 2)
                put(7 + i * 2, 3, json.dumps(node["arguments"], ensure_ascii=False), left - 4)
            put(5, left, "Agent 实时输出", attr=curses.A_BOLD)
            for i, event in enumerate(state["events"][-max(1, rows - 10) :]):
                stamp = time.strftime("%H:%M:%S", time.localtime(event["time"]))
                put(6 + i, left, f"{stamp} {event['text']}")
        else:
            for i, event in enumerate(state["events"][-max(1, rows - 9) :]):
                put(5 + i, 1, event["text"])
        put(rows - 3, 1, "/stop 停止 | /demo 演示 | /reset 重置 | /quit 退出 | ↑↓ 历史")
        offset = 0
        while cell_len(self.text[offset : self.cursor]) > max(1, cols - 6):
            offset += 1
        put(rows - 2, 1, "> " + self.text[offset:])
        with contextlib.suppress(curses.error):
            screen.move(rows - 2, min(cols - 2, 3 + cell_len(self.text[offset : self.cursor])))
        screen.refresh()


async def run(args, screen=None):
    app = InteractiveConsole(args)
    terminal = Terminal(screen)
    startup = asyncio.create_task(app.start())
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, app.quit_event.set)
    queue = asyncio.Queue()
    transport = None
    if screen is None:
        reader = asyncio.StreamReader()
        transport, _ = await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)

        async def input_lines():
            while line := await reader.readline():
                await queue.put(line.decode(errors="replace").strip())
            await queue.put("/quit")

        input_task = asyncio.create_task(input_lines())
        print(f"MAGIC 控制台 · {app.url}\n{HELP}", flush=True)
    seen = 0
    startup_checked = False
    try:
        while not app.quit_event.is_set():
            if startup.done() and not startup_checked:
                startup_checked = True
                try:
                    await startup
                except Exception as exc:
                    app.phase("ERROR", str(exc))
                    app.emit("error", text=str(exc))
            if app.ready:
                for name, process in app.children:
                    if process.poll() is not None:
                        app.ready = False
                        app.phase("ERROR", f"{name} 已退出；输入 /quit 关闭后重启。")
            if screen:
                terminal.draw(app)
                try:
                    for _ in range(100):
                        value = terminal.key(screen.get_wch())
                        if value is not None:
                            await queue.put(value)
                except curses.error:
                    pass
            else:
                for event in app.live.snapshot()["events"]:
                    if event["id"] > seen:
                        print(
                            time.strftime("[%H:%M:%S]", time.localtime(event["time"])),
                            clean(event["text"]),
                            flush=True,
                        )
                        seen = event["id"]
            while not queue.empty():
                try:
                    await app.command(queue.get_nowait())
                except Exception as exc:
                    app.emit("error", text=str(exc))
            await asyncio.sleep(0.08)
    finally:
        startup.cancel()
        await asyncio.gather(startup, return_exceptions=True)
        if transport:
            transport.close()
            input_task.cancel()
            await asyncio.gather(input_task, return_exceptions=True)
        app.phase("STOPPING", "正在停止任务并关闭本次启动的仿真，请稍候…")
        if screen:
            terminal.draw(app)
        else:
            print("正在关闭控制台及本次启动的仿真…", flush=True)
        await app.close()


def main():
    parser = argparse.ArgumentParser(description="MAGIC 实时交互控制台")
    parser.add_argument("--flat", action="store_true")
    parser.add_argument("--port", type=int, default=8780, help="本机实时画面端口")
    parser.add_argument("--fps", type=float, default=6, help="画面刷新率 1–15")
    parser.add_argument("--plain", action="store_true", help="逐行日志模式，适合重定向和简易终端")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--llm-config")
    parser.add_argument("--vision", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.fps <= 15:
        parser.error("fps must be between 1 and 15")
    try:
        if sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get("TERM") != "dumb" and not args.plain:
            curses.wrapper(lambda screen: asyncio.run(run(args, screen)))
        else:
            asyncio.run(run(args))
    except (OSError, RuntimeError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()

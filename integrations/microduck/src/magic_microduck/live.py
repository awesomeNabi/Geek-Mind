"""Thread-safe console state and a read-only local live-view HTTP server."""

import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from .settings import ROOT


def event_text(kind, data):
    if kind == "action":
        args = json.dumps(data.get("arguments", {}), ensure_ascii=False)
        return f"{data.get('skill', '动作')} {args} → {data['status']} · {data.get('detail', '')}"
    if kind == "task":
        return f"任务 {data['state']} · " + " / ".join(f"{n}: {s}" for n, s in data["nodes"])
    if kind == "plan":
        return f"计划已生成，共 {len(data['nodes'])} 步；保存于 {data['path']}"
    return str(data.get("text", kind))


class LiveState:
    def __init__(self, directory):
        self.lock = threading.RLock()
        self.events = deque(maxlen=200)
        self.frames = {}
        self.state = dict(phase="STARTING", goal="", robot={}, plan=[], node_states={}, run_state=None)
        self.state["session_id"] = uuid4().hex
        self.sequence = 0
        self.journal = (directory / "events.jsonl").open("a", encoding="utf-8")

    def emit(self, kind, data):
        with self.lock:
            self.sequence += 1
            event = dict(
                id=self.sequence, time=time.time(), kind=kind, text=event_text(kind, data), data=data
            )
            self.events.append(event)
            if kind == "phase":
                self.state["phase"] = data["phase"]
            elif kind == "goal":
                self.state.update(goal=data["text"], plan=[], node_states={}, run_state=None)
            elif kind == "plan":
                self.state["plan"] = data["nodes"]
            elif kind == "task":
                self.state.update(run_state=data["state"], node_states=dict(data["nodes"]))
            self.journal.write(json.dumps(event, ensure_ascii=False) + "\n")
            self.journal.flush()

    def update_robot(self, value):
        with self.lock:
            self.state["robot"] = value

    def set_frame(self, view, value):
        with self.lock:
            self.frames[view] = value

    def frame(self, view):
        with self.lock:
            value = self.frames.get(view)
            return value if value and time.time() - value[1] < 3 else None

    def snapshot(self):
        with self.lock:
            return {
                **self.state,
                "events": list(self.events),
                "time": time.time(),
                "cameras": {
                    key: {"observed_at": v[1], "fresh": time.time() - v[1] < 3}
                    for key, v in self.frames.items()
                },
            }

    def close(self):
        self.journal.close()


class LiveServer:
    def __init__(self, live, port):
        page = (ROOT / "web/index.html").read_bytes()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                parts = urlsplit(self.path)
                try:
                    if parts.path == "/":
                        self.reply(200, "text/html; charset=utf-8", page)
                    elif parts.path == "/api/state":
                        self.reply(
                            200, "application/json", json.dumps(live.snapshot(), ensure_ascii=False).encode()
                        )
                    elif parts.path in ("/frame.jpg", "/stream.mjpg"):
                        view = parse_qs(parts.query).get("view", ["follow"])[0]
                        if view not in ("head", "follow"):
                            self.reply(400, "text/plain", b"Unknown view")
                            return
                        value = live.frame(view)
                        if not value:
                            self.reply(503, "text/plain", b"Waiting for a fresh camera frame")
                        elif parts.path == "/frame.jpg":
                            self.reply(200, "image/jpeg", value[0])
                        else:
                            self.send_response(200)
                            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                            self.send_header("Cache-Control", "no-store")
                            self.end_headers()
                            last = None
                            while not self.server.stopping.is_set():
                                value = live.frame(view)
                                if not value:
                                    break
                                if value[1] != last:
                                    payload = value[0]
                                    self.wfile.write(
                                        b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                        + str(len(payload)).encode()
                                        + b"\r\n\r\n"
                                        + payload
                                        + b"\r\n"
                                    )
                                    self.wfile.flush()
                                    last = value[1]
                                self.server.stopping.wait(0.08)
                    else:
                        self.reply(404, "text/plain", b"Not found")
                except (BrokenPipeError, ConnectionResetError, TimeoutError):
                    pass

            def reply(self, status, mime, body):
                self.send_response(status)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.server.stopping = threading.Event()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def port(self):
        return self.server.server_port

    def close(self):
        self.server.stopping.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

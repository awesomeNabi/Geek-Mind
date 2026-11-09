"""Loopback JSON bridge, using only stdlib plus the existing ROS environment."""

import argparse
import fcntl
import faulthandler
import json
import os
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, parse_qs, urlsplit

from .contracts import ControlError
from .jobs import Jobs
from .settings import DUCK_ROOT, STATE


def handler_for(jobs):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def handle_request(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > 65536:
                    raise ValueError("Invalid request length")
                body = json.loads(self.rfile.read(length)) if length else {}
                if not isinstance(body, dict):
                    raise ValueError("JSON object required")
                path = self.path.split("?")[0]
                if self.command == "GET" and path == "/state":
                    value = {
                        **jobs.backend.state(),
                        "active_actions": jobs.active(),
                        "session_id": jobs.session_id,
                    }
                elif self.command == "GET" and path.startswith("/actions/"):
                    value = jobs.get(unquote(path[len("/actions/") :]))
                elif self.command == "GET" and path == "/image":
                    value = jobs.backend.image()
                elif self.command == "GET" and path == "/frame.jpg":
                    view = parse_qs(urlsplit(self.path).query).get("view", ["head"])[0]
                    frame = jobs.backend.frame(view)
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(frame["jpeg"])))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Observed-At", str(frame["observed_at"]))
                    self.end_headers()
                    self.wfile.write(frame["jpeg"])
                    return
                elif self.command == "POST" and path == "/actions":
                    value = jobs.start(body["skill"], body.get("arguments", {}), body.get("command_id"))
                elif self.command == "POST" and path == "/cancel":
                    value = jobs.cancel(body["command_id"])
                elif self.command == "POST" and path == "/stop":
                    value = jobs.stop()
                elif self.command == "POST" and path == "/reset":
                    value = jobs.reset()
                else:
                    self.reply(404, {"error": "not_found"})
                    return
                self.reply(200, value)
            except KeyError as exc:
                self.reply(404, {"error": "not_found", "detail": str(exc)})
            except (ValueError, TypeError) as exc:
                self.reply(400, {"error": "invalid_request", "detail": str(exc)})
            except ControlError as exc:
                self.reply(409, {"error": exc.code, "detail": str(exc), "status": exc.status})
            except Exception as exc:
                self.reply(500, {"error": "bridge_error", "detail": str(exc)})

        do_GET = handle_request
        do_POST = handle_request

        def reply(self, status, value):
            data = json.dumps(value, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--places", default=str(DUCK_ROOT / ".local/maps/apartment_places.yaml"))
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    # All launches of this project for one ROS domain share a controller lock.
    lock = (STATE / f"bridge-domain-{os.environ.get('ROS_DOMAIN_ID', '84')}.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("A bridge for this ROS domain is already running")
    import rclpy
    from .ros_backend import RosBackend

    if os.environ.get("MAGIC_DUCK_DEBUG"):
        faulthandler.dump_traceback_later(15, repeat=True)
    rclpy.init()
    backend = RosBackend(args.places, STATE / "images")
    jobs = Jobs(backend, STATE / "actions.sqlite3")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(jobs))

    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    print(f"Microduck bridge listening on http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
        jobs.close()
        backend.close()
        rclpy.shutdown()
        lock.close()


if __name__ == "__main__":
    main()

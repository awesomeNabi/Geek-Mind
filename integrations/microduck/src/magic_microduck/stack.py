"""Foreground supervisor for the simulator and bridge; only stops its own children."""

import argparse
import asyncio
import fcntl
import os
import signal
import subprocess
import time
from urllib.parse import urlparse
from uuid import uuid4

from .client import BridgeClient
from .settings import ROOT, STATE, URL


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--flat", action="store_true", help="Flat scene instead of apartment Nav2")
    parser.add_argument("--no-camera", action="store_true")
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    guard = (STATE / "stack.lock").open("w")
    try:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("This project stack is already running")
    client = BridgeClient()
    try:
        client.request_sync("/state")
    except Exception:
        pass
    else:
        raise SystemExit(f"A bridge already responds at {URL}; refusing a duplicate simulator")
    logdir = STATE / ("stack-" + uuid4().hex[:8])
    logdir.mkdir()
    commands = [
        ["sim" if args.flat else "nav", "camera:=false" if args.no_camera else "camera:=true"],
        ["bridge", "--port", str(urlparse(URL).port or 8766)],
    ]
    if not args.flat:
        commands[0].append("agent:=false")
    processes, logs = [], []

    def interrupted(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        for name, command in zip(("sim", "bridge"), commands):
            log = (logdir / f"{name}.log").open("w")
            logs.append(log)
            processes.append(
                subprocess.Popen(
                    ["bash", str(ROOT / "run.sh"), *command],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            )
        deadline = time.monotonic() + 90
        ready = False
        print(f"Starting; logs: {logdir}", flush=True)
        while True:
            if any(p.poll() is not None for p in processes):
                raise RuntimeError(f"A child exited; inspect {logdir}")
            if not ready:
                try:
                    state = client.request_sync("/state")
                    ready = state["ready"] and (args.flat or state["navigation_available"])
                except Exception:
                    pass
                if ready:
                    print(
                        'READY. In another terminal: bash run.sh demo   (or: bash run.sh ask "坐下然后站起来")',
                        flush=True,
                    )
                elif time.monotonic() > deadline:
                    raise RuntimeError(f"Stack startup timed out; inspect {logdir}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping owned simulator and bridge...", flush=True)
    finally:
        try:
            asyncio.run(client.stop())
        except Exception:
            pass
        for process in reversed(processes):
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        for log in logs:
            log.close()
        guard.close()


if __name__ == "__main__":
    main()

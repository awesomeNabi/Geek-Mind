"""One actuator owner, durable receipts, duplicate suppression, and restart barriers."""

import json
import sqlite3
import threading
import time
from uuid import uuid4

from .contracts import ControlError, TERMINAL, validate


class Jobs:
    def __init__(self, backend, path):
        self.backend = backend
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,intent TEXT,receipt TEXT)")
        self.events = {}
        self.threads = []
        self.closed = False
        self.session_id = uuid4().hex
        # A process restart is not proof that the robot stopped. Do not replay.
        for job_id, receipt in self.db.execute("SELECT id,receipt FROM jobs").fetchall():
            value = json.loads(receipt)
            if value["status"] not in TERMINAL:
                value.update(
                    status="UNKNOWN",
                    error_code="bridge_restarted",
                    detail="Explicit simulator reset required before another movement",
                )
                self._save(value)

    def _save(self, value):
        value["updated_at"] = time.time()
        self.db.execute(
            "UPDATE jobs SET receipt=? WHERE id=?", (json.dumps(value, allow_nan=False), value["command_id"])
        )

    def get(self, job_id):
        with self.lock:
            row = self.db.execute("SELECT receipt FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            return json.loads(row[0])

    def active(self):
        with self.lock:
            return [
                json.loads(r[0])
                for r in self.db.execute("SELECT receipt FROM jobs")
                if json.loads(r[0])["status"] not in TERMINAL
            ]

    def start(self, skill, arguments, command_id=None):
        validate(skill, arguments)
        command_id = command_id or uuid4().hex
        if not isinstance(command_id, str) or not 1 <= len(command_id) <= 200:
            raise ValueError("Invalid command_id")
        intent = json.dumps([skill, arguments], sort_keys=True, allow_nan=False)
        with self.lock:
            old = self.db.execute("SELECT intent FROM jobs WHERE id=?", (command_id,)).fetchone()
            if old:
                if old[0] != intent:
                    raise ControlError("command_id reused with different arguments", "identity_conflict")
                return self.get(command_id)
            if self.closed or self.active():
                raise ControlError("Robot busy or unresolved action; query/cancel/reset first", "busy")
            receipt = dict(
                command_id=command_id,
                skill=skill,
                arguments=arguments,
                status="RUNNING",
                detail="accepted",
                data={},
                error_code=None,
                session_id=self.session_id,
                created_at=time.time(),
                updated_at=time.time(),
            )
            self.db.execute("INSERT INTO jobs VALUES(?,?,?)", (command_id, intent, json.dumps(receipt)))
            cancel = self.events[command_id] = threading.Event()
            thread = threading.Thread(
                target=self._run, args=(command_id, skill, arguments, cancel), daemon=True
            )
            self.threads.append(thread)
            thread.start()
            return receipt

    def _run(self, job_id, skill, arguments, cancel):
        try:
            data = self.backend.execute(skill, arguments, cancel)
            status, detail, code = "SUCCEEDED", "Execution verified by controller observations", None
        except ControlError as exc:
            status, detail, code, data = exc.status, str(exc), exc.code, {}
        except Exception as exc:
            # An unexpected exception may have occurred after dispatch.
            status, detail, code, data = "UNKNOWN", str(exc), "unexpected_exception", {}
        with self.lock:
            value = self.get(job_id)
            value.update(status=status, detail=detail, error_code=code, data=data)
            self._save(value)
            self.events.pop(job_id, None)

    def cancel(self, job_id):
        with self.lock:
            value = self.get(job_id)
            if value["status"] in TERMINAL:
                return value
            if value["skill"] == "do_skill":
                # The upstream Trigger skill services have no cancellation API.
                value["detail"] = "Skill cannot be interrupted; continuing to observe completion"
                self._save(value)
                return value
            event = self.events.get(job_id)
            if event:
                event.set()
                value.update(status="CANCEL_REQUESTED", detail="Awaiting controller stop confirmation")
                self._save(value)
            return value

    def stop(self):
        values = [self.cancel(v["command_id"]) for v in self.active()]
        getattr(self.backend, "request_stop", self.backend.zero)()
        return {
            "actions": values,
            "detail": "Zero velocity sent; inspect receipts for confirmed cancellation",
        }

    def reset(self):
        with self.lock:
            if self.events:
                raise ControlError("Cancel and wait for the active action before resetting", "busy")
            self.backend.reset()
            for value in self.active():
                value.update(
                    status="FAILED",
                    error_code="explicit_sim_reset",
                    detail="Uncertain action closed by explicit simulator reset",
                )
                self._save(value)
            return {"reset": True}

    def close(self):
        self.closed = True
        self.stop()
        for thread in self.threads:
            thread.join(timeout=5)
        if not any(t.is_alive() for t in self.threads):
            self.db.close()

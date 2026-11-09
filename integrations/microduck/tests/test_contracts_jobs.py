import threading
import time

import pytest

from magic_microduck.contracts import ControlError, validate
from magic_microduck.jobs import Jobs


@pytest.mark.parametrize(
    "args",
    [
        {"distance_m": True},
        {"distance_m": float("nan")},
        {"distance_m": 3},
        {"distance_m": 0.1, "speed": 10},
        {},
    ],
)
def test_invalid_motion_never_admitted(args):
    with pytest.raises(ValueError):
        validate("walk", args)


class Backend:
    def __init__(self):
        self.calls = 0
        self.finish = threading.Event()

    def execute(self, skill, arguments, cancel):
        self.calls += 1
        while not self.finish.wait(0.01):
            if cancel.is_set():
                raise ControlError("stopped", "cancelled", "CANCELLED")
        return {"verification": "test observation"}

    def zero(self):
        pass

    def reset(self):
        pass


def wait(jobs, key, status):
    end = time.monotonic() + 2
    while time.monotonic() < end:
        if jobs.get(key)["status"] == status:
            return
        time.sleep(0.01)
    raise AssertionError(jobs.get(key))


def test_duplicate_identity_busy_and_cancellation(tmp_path):
    backend = Backend()
    jobs = Jobs(backend, tmp_path / "jobs.db")
    try:
        first = jobs.start("walk", {"distance_m": 0.2}, "one")
        assert jobs.start("walk", {"distance_m": 0.2}, "one") == first
        with pytest.raises(ControlError, match="different"):
            jobs.start("walk", {"distance_m": 0.3}, "one")
        with pytest.raises(ControlError, match="busy"):
            jobs.start("turn", {"degrees": 20}, "two")
        assert jobs.cancel("one")["status"] == "CANCEL_REQUESTED"
        wait(jobs, "one", "CANCELLED")
        assert jobs.start("walk", {"distance_m": 0.2}, "one")["status"] == "CANCELLED"
        assert backend.calls == 1
    finally:
        backend.finish.set()
        jobs.close()


def test_skill_cancel_does_not_claim_stop(tmp_path):
    backend = Backend()
    jobs = Jobs(backend, tmp_path / "jobs.db")
    try:
        jobs.start("do_skill", {"skill": "sit"}, "sit")
        assert jobs.cancel("sit")["status"] == "RUNNING"
        assert not jobs.events["sit"].is_set()
        backend.finish.set()
        wait(jobs, "sit", "SUCCEEDED")
    finally:
        backend.finish.set()
        jobs.close()


def test_restart_blocks_replay_until_explicit_reset(tmp_path):
    path = tmp_path / "jobs.db"
    backend = Backend()
    jobs = Jobs(backend, path)
    # Persist a receipt representing a process that disappeared after dispatch.
    jobs.db.execute(
        "INSERT INTO jobs VALUES(?,?,?)",
        ("old", '["walk", {"distance_m": 0.2}]', '{"command_id":"old","status":"RUNNING","skill":"walk"}'),
    )
    jobs.close()
    restarted = Jobs(backend, path)
    try:
        assert restarted.get("old")["status"] == "UNKNOWN"
        with pytest.raises(ControlError, match="busy"):
            restarted.start("walk", {"distance_m": 0.1}, "new")
        restarted.reset()
        assert restarted.get("old")["status"] == "FAILED"
        assert backend.calls == 0
    finally:
        restarted.close()

"""A seat's window: every recipient its whole limit, spawned only by the cap's end.

Design: lib/DESIGN.md#a-runs-window-and-the-entrances-cap
"""
import base64
import json
from pathlib import Path
import sys
import time

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(LIB / "tests"))
import dispatch_seat as seat
import run_lifecycle as lifecycle
from test_dispatch_seat import configure, job, primary_template, record, seen  # noqa: F401 - fixtures


def started_back(seconds):
    return time.monotonic() - seconds


@pytest.mark.parametrize("vendor, own", [("claude", "codex"), ("codex", "claude")])
def test_978_seat_notice_states_the_limit(job, vendor, own):
    args, _ = job
    args.vendor, args.own_vendor = vendor, own
    args.timeout_seconds = 1800
    # The launcher's own work has already spent 500 seconds of its cap.
    args.invocation_started_monotonic = started_back(500)
    seat.run_dispatch(args)
    request = json.loads(seat.sidecar(args.output, ".request.json").read_bytes())
    assert request["recipient_allocation_seconds"] == 1800
    assert request["preflight_cap"] == {"seconds": 900, "source": "default", "reason": None}
    attempt = record(args)["attempts"][0]
    assert attempt["vendor"] == vendor and attempt["launched"]
    assert attempt["allocation_seconds"] >= 1799
    if vendor == "claude":
        observed = seen(args, "claude")
        assert observed["command_ceiling"] == "1800000"
        assert b"up to 1800 seconds" in base64.b64decode(observed["stdin"])
        assert request["launch_controls"]["command_ceiling_ms"] == 1800000


def test_978_unlaunched_attempt(job, monkeypatch):
    args, _ = job
    args.timeout_seconds = 600
    real = seat.run_process
    withdrawn = []
    original = lifecycle.Deadline.withdraw_window

    def withdraw(self):
        withdrawn.append(self.in_window)
        return original(self)
    monkeypatch.setattr(lifecycle.Deadline, "withdraw_window", withdraw)

    def gone(command, **kwargs):
        if "claude" in command:
            raise FileNotFoundError("the claude executable disappeared")
        return real(command, **kwargs)
    monkeypatch.setattr(seat, "run_process", gone)
    seat.run_dispatch(args)
    first, second = record(args)["attempts"]
    # Nothing started, so the first attempt names no spawn and the window was withdrawn before the next.
    assert first["vendor"] == "claude" and first["launched"] is False
    assert "pre_spawn_seconds" not in first and "pre_spawn_parts" not in first
    assert True in withdrawn
    assert second["vendor"] == "codex" and second["launched"]
    assert second["allocation_seconds"] >= 599
    assert second["pre_spawn_seconds"] is not None


def test_978_a_fallback_after_a_spawned_primary_gets_the_whole_limit(job, monkeypatch):
    args, scenario = job
    args.timeout_seconds = 600
    configure(job, {"claude": {"message": "Not logged in", "sleep": 1}})
    monkeypatch.setattr(seat, "_steps_before_spawn", lambda *_a: 1)
    # Thirty seconds of the cap are left, more than the fallback's steps when the primary returns.
    args.invocation_started_monotonic = started_back(lifecycle.PREFLIGHT_CAP_SECONDS - 30)
    seat.run_dispatch(args)
    first, second = record(args)["attempts"]
    assert first["launched"] and first["outcome"] == "unavailable"
    assert second["vendor"] == "codex" and second["launched"]
    assert second["allocation_seconds"] >= 599


def test_978_a_fallback_whose_turn_comes_after_the_cap_is_not_started(job, monkeypatch):
    args, scenario = job
    args.timeout_seconds = 600
    configure(job, {"claude": {"message": "Not logged in", "sleep": 4}})
    monkeypatch.setattr(seat, "_steps_before_spawn", lambda *_a: 1)
    # The cap ends while the primary runs.
    args.invocation_started_monotonic = started_back(lifecycle.PREFLIGHT_CAP_SECONDS - 9)
    seat.run_dispatch(args)
    first, second = record(args)["attempts"]
    assert first["launched"]
    assert second["vendor"] == "codex" and not second["launched"]
    assert second["outcome"] == "unavailable"
    assert "cap ended before this fallback could start" in second["reason"]
    assert not (args.root / "seen-codex.json").exists()
    # The primary's launch is this bundle's record.
    assert seat.sidecar(args.output, ".request.json").is_file()


def test_978_late_fallback_leaves_no_bundle(job, monkeypatch):
    args, _ = job
    allowances = []
    original = lifecycle.Deadline.require_cap

    def spy(self, seconds=0):
        allowances.append(seconds)
        return original(self, seconds)
    monkeypatch.setattr(lifecycle.Deadline, "require_cap", spy)
    seat.run_dispatch(args)
    allowance = max(allowances)
    one = seat._steps_before_spawn(args, "claude", None) + lifecycle.SPAWN_MARGIN_SECONDS
    assert allowance > one  # The allowance covers both attempts, not only the first.
    output = args.output.parent / "late" / "verdict.md"
    args.output = output
    for path in args.root.glob("seen-*.json"):
        path.unlink()
    # More of the cap is left than one attempt needs and less than both.
    args.invocation_started_monotonic = started_back(lifecycle.PREFLIGHT_CAP_SECONDS - (one + allowance) / 2)
    with pytest.raises(seat.DispatchError, match="900-second cap"):
        seat.run_dispatch(args)
    assert not output.parent.exists() or not any(output.parent.iterdir())
    assert not list(args.root.glob("seen-*.json"))

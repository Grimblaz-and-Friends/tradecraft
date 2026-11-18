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


def latest_return(args):
    """The printed latest return on this clock: the call, the cap, the whole limit and the reserve."""
    started = getattr(args, "invocation_started_monotonic", None)
    reserve = min(60, max(10, args.timeout_seconds / 10))
    return started + lifecycle.PREFLIGHT_CAP_SECONDS + args.timeout_seconds + reserve


def allowance_of(args):
    """The cap a two-vendor seat needs at its request write: each attempt's steps and the margin."""
    return sum(seat._steps_before_spawn(args, vendor, None) for vendor in (args.vendor, args.own_vendor)) + (
        lifecycle.SPAWN_MARGIN_SECONDS)


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
    args.invocation_started_monotonic = time.monotonic()
    seat.run_dispatch(args)
    assert time.monotonic() < latest_return(args)
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
    configure(job, {"claude": {"message": "Not logged in", "sleep": 3}})
    # The cap ends about a minute after the primary returns, so the fallback's steps fit.
    args.invocation_started_monotonic = started_back(lifecycle.PREFLIGHT_CAP_SECONDS - allowance_of(args) - 65)
    seat.run_dispatch(args)
    assert time.monotonic() < latest_return(args)
    first, second = record(args)["attempts"]
    assert first["launched"] and first["outcome"] == "unavailable"
    assert second["vendor"] == "codex" and second["launched"]
    assert second["allocation_seconds"] >= 599


def test_978_a_fallback_whose_turn_comes_after_the_cap_is_not_started(job, monkeypatch):
    args, scenario = job
    args.timeout_seconds = 600
    allowance = allowance_of(args)
    # The cap admits the request write and then ends while the primary runs.
    configure(job, {"claude": {"message": "Not logged in", "sleep": allowance + 5}})
    args.invocation_started_monotonic = started_back(lifecycle.PREFLIGHT_CAP_SECONDS - allowance - 3)
    seat.run_dispatch(args)
    assert time.monotonic() < latest_return(args)
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


def _entrance_line(args, launched_after):
    import work
    command = ["--work", args.work, "--stage", args.stage, "--output", str(args.output)]
    return work._launched_split(command, None, launched_after)


@pytest.mark.parametrize("fallback", [True, False])
def test_978_the_entrance_line_names_the_spawned_attempt(job, monkeypatch, fallback):
    import preflight
    from datetime import datetime, timezone
    args, _ = job
    if not fallback:
        args.own_vendor = "claude"
    real = seat.run_process

    def gone(command, **kwargs):
        if "claude" in command:
            raise FileNotFoundError("the claude executable disappeared")
        return real(command, **kwargs)
    monkeypatch.setattr(seat, "run_process", gone)
    launched_after = datetime.now(timezone.utc).isoformat()
    with preflight.scope():
        seat.run_dispatch(args)
    request = json.loads(seat.sidecar(args.output, ".request.json").read_bytes())
    attempts = record(args)["attempts"]
    line = _entrance_line(args, launched_after)
    if fallback:
        spawned = attempts[1]
        assert line["until"] == "spawn"
        assert line == preflight.combine(request["preflight"], spawned["pre_spawn_seconds"],
                                         spawned["pre_spawn_parts"])
    else:
        # Nothing spawned: the line ends at the request record, never at a spawn.
        assert [attempt["launched"] for attempt in attempts] == [False]
        assert line["until"] == "request-record"


def test_978_late_fallback_after_an_unspawned_primary_still_spawns_by_the_cap(job, monkeypatch):
    args, _ = job
    allowance = allowance_of(args)
    version = seat.records.runtime_version
    real = seat.run_process
    opened = []

    def slow_version(command, *rest, **kwargs):
        if "claude" in command:
            time.sleep(15)  # The primary's version read is slow, and then its executable is gone.
        return version(command, *rest, **kwargs)

    def gone(command, **kwargs):
        if "claude" in command:
            raise FileNotFoundError("the claude executable removed itself")
        opened.append(lifecycle.current_deadline().window_opened)
        return real(command, **kwargs)
    monkeypatch.setattr(seat.records, "runtime_version", slow_version)
    monkeypatch.setattr(seat, "run_process", gone)
    # Three seconds more of the cap are left at the request write than both attempts' steps need.
    args.invocation_started_monotonic = started_back(lifecycle.PREFLIGHT_CAP_SECONDS - allowance - 3)
    cap_end = args.invocation_started_monotonic + lifecycle.PREFLIGHT_CAP_SECONDS
    seat.run_dispatch(args)
    logged = record(args)
    first, second = logged["attempts"]
    assert first["launched"] is False and second["launched"]
    assert "window_opened_late_seconds" not in logged
    assert opened and opened[0] <= cap_end
    assert not any("cap" in str(attempt.get("reason", "")) for attempt in logged["attempts"])


def test_978_a_fallback_refused_after_a_late_primary_keeps_the_primarys_record(job, monkeypatch):
    args, _ = job
    args.timeout_seconds = 60
    monkeypatch.setattr(seat, "_steps_before_spawn", lambda *_a: 1)
    allowance = allowance_of(args)
    reserve = min(60, max(10, args.timeout_seconds / 10))
    # The primary returns unavailable more than one reserve after the cap's end.
    configure(job, {"claude": {"message": "Not logged in", "sleep": 3 + reserve + 6}})
    args.invocation_started_monotonic = started_back(lifecycle.PREFLIGHT_CAP_SECONDS - allowance - 3)
    seat.run_dispatch(args)
    logged = record(args)
    first, second = logged["attempts"]
    assert first["launched"] and first["outcome"] == "unavailable"
    assert not second["launched"] and "cap ended before this fallback could start" in second["reason"]
    # The primary's launch is recorded whole: its record completed, its revision read after it.
    assert logged.get("completed_at")
    assert logged.get("revision_after") is not None
    assert time.monotonic() < latest_return(args)


def test_978_a_fallbacks_turn_tells_the_entrance_the_window_is_withdrawn(job, monkeypatch, tmp_path):
    args, _ = job
    args.launch_notice = tmp_path / "launch-notice.json"
    configure(job, {"claude": {"message": "Not logged in"}})
    version = seat.records.runtime_version
    seen_at_fallback = []

    def version_read(command, *rest, **kwargs):
        if "codex" in str(command):
            seen_at_fallback.append(lifecycle.read_launch_notice(args.launch_notice))
        return version(command, *rest, **kwargs)
    monkeypatch.setattr(seat.records, "runtime_version", version_read)
    seat.run_dispatch(args)
    first, second = record(args)["attempts"]
    assert first["launched"] and first["outcome"] == "unavailable" and second["launched"]
    # The fallback's own steps run on the cap, so the entrance must not hold it to the primary's window.
    assert seen_at_fallback == [None]

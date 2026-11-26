"""A stand-in for a launched builder and its launcher: one process that writes a run record and a log as they do.

The route fixture's `watch-` scenarios start it as a child, so the holder's wait has a live launch to read.
Its run record is rewritten by the launchers' own writer, `dispatch_lifecycle.atomic_record`, and its log
is in Claude's stream form: an `assistant` record for each step, `tool_progress` heartbeats while a step
runs, and a `user` record for each step's result. MODE says how it ends: `ready` completes the record
with success, `stopped` completes it as failed, `limit` completes it as stopped at its ceiling when its
limit is reached, and `crash` dies without completing it. With `--replay`
it appends a recorded-form log line by line instead of its own steps. With `--hold-until PATH` it ends
only once PATH exists, so a scenario reads it while it runs however slowly that scenario's machine is.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dispatch_lifecycle import atomic_record  # noqa: E402
import run_lifecycle as lifecycle  # noqa: E402

SESSION = "00000000-0000-4000-8000-00000000f1f0"
# Steps already in the log when the wait starts, each written as if minutes ago.
EARLIER = (("Bash", {"command": "git log --oneline -3", "description": "Orient in the tree"}),
           ("Read", {"file_path": "lib/job.py"}),
           ("Bash", {"command": "python -B -m pytest -q lib/tests", "description": "Run the job's tests"}))
# The steps taken while the wait watches: (seconds after the start, tool, input, a helper's step).
LIVE = ((2, "Edit", {"file_path": "lib/job.py", "old_string": "a", "new_string": "b"}, False),
        (4, "Agent", {"description": "Read the job's callers", "prompt": "List the job's callers."}, False),
        (6, "Grep", {"pattern": "def run_job"}, True),
        (8, "Bash", {"command": "python -B -m pytest -q lib/tests/test_job.py\nsecond line",
                     "description": "Run the job's tests a second time"}, False))
# The last live step runs this long with heartbeats only, so the builder is quiet for a known span.
QUIET_UNTIL = 20
END_AT = 22


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def _append(log: Path, record: dict) -> None:
    with log.open("ab") as stream:
        stream.write((json.dumps(record, ensure_ascii=True) + "\n").encode("utf-8"))


def _step(log: Path, identity: str, tool: str, tool_input: dict, *, helper: str | None, at: datetime) -> None:
    _append(log, {"type": "assistant", "message": {"id": f"msg-{identity}", "role": "assistant", "content": [
        {"type": "tool_use", "id": identity, "name": tool, "input": tool_input}]},
        "parent_tool_use_id": helper, "session_id": SESSION, "uuid": uuid.uuid4().hex, "timestamp": _stamp(at)})


def _result(log: Path, identity: str, *, helper: str | None, at: datetime) -> None:
    _append(log, {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": identity, "content": "ok"}]},
        "parent_tool_use_id": helper, "session_id": SESSION, "uuid": uuid.uuid4().hex, "timestamp": _stamp(at)})


def _heartbeat(log: Path, identity: str, tool: str, elapsed: int) -> None:
    _append(log, {"type": "tool_progress", "tool_use_id": f"{identity}-heartbeat-{elapsed}", "tool_name": tool,
                  "parent_tool_use_id": identity, "elapsed_time_seconds": elapsed, "heartbeat": True,
                  "session_id": SESSION, "uuid": uuid.uuid4().hex})


class Run:
    """The run record as the launcher keeps it: running with an elapsed checkpoint, then completed once."""

    def __init__(self, path: Path, log: Path, launched: datetime, dispatch: str):
        self.path, self.launched = path, launched
        self.record = {"schema_version": 2, "dispatch_id": dispatch, "launched_at": launched.isoformat(),
                       "launcher_process": lifecycle.process_identity(), "lifecycle": "running",
                       "elapsed_checkpoint_seconds": 0, "elapsed_checkpoint_interval_seconds": 1.0,
                       "attempts": [{"vendor": "claude", "launched": True, "stdout": str(log),
                                     "source_format": "claude-stream-json"}]}

    def checkpoint(self) -> None:
        self.record["elapsed_checkpoint_seconds"] = (datetime.now(timezone.utc) - self.launched).total_seconds()
        atomic_record(self.path, self.record)

    def complete(self, outcome: str, cause: str | None = None) -> None:
        self.record.update(lifecycle="completed", outcome=outcome,
                           completed_at=datetime.now(timezone.utc).isoformat())
        if cause:
            self.record["interruption_cause"] = cause
        self.checkpoint()


def _hold(run: Run, until: float, started: float, beat=None) -> None:
    """Keep the record's checkpoint fresh, and beat for a running step, until ``until`` seconds after the start."""
    while time.monotonic() - started < until:
        run.checkpoint()
        if beat is not None:
            beat()
        time.sleep(1.0)


def _held(run: Run, path: Path | None, beat=None) -> None:
    """Keep running until PATH exists, or for at most two minutes, so the stand-in never outlives its scenario."""
    end = time.monotonic() + 120
    while path is not None and not path.exists() and time.monotonic() < end:
        run.checkpoint()
        if beat is not None:
            beat()
        time.sleep(0.5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--dispatch", required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--mode", choices=("ready", "stopped", "limit", "crash"), required=True)
    parser.add_argument("--launched", required=True, help="the launch time, ISO 8601")
    parser.add_argument("--limit-at", type=float, help="with --mode limit: seconds after the start it reaches its limit")
    parser.add_argument("--replay", type=Path, help="a recorded-form log to append line by line")
    parser.add_argument("--hold-until", type=Path, help="end only once this file exists")
    args = parser.parse_args(argv)
    launched = datetime.fromisoformat(args.launched)
    started = time.monotonic()
    run = Run(args.run, args.log, launched, args.dispatch)
    now = datetime.now(timezone.utc)
    if args.replay is not None:
        args.log.write_bytes(b"")
        run.checkpoint()
        for line in args.replay.read_bytes().splitlines():
            record = json.loads(line)
            if "timestamp" in record:
                # Each record is stamped when it is appended, as the builder stamped it when it wrote it.
                record["timestamp"] = _stamp(datetime.now(timezone.utc))
            _append(args.log, record)
            run.checkpoint()
            time.sleep(0.25)
        _held(run, args.hold_until)
        run.complete("success")
        return 0
    _append(args.log, {"type": "system", "subtype": "init", "session_id": SESSION, "model": "fixture"})
    for index, (tool, tool_input) in enumerate(EARLIER):
        at = now - timedelta(minutes=9 - 3 * index)
        _step(args.log, f"toolu_earlier_{index}", tool, tool_input, helper=None, at=at)
        _result(args.log, f"toolu_earlier_{index}", helper=None, at=at + timedelta(minutes=2))
    run.checkpoint()
    parent = None
    for index, (when, tool, tool_input, helper) in enumerate(LIVE):
        _hold(run, when, started)
        identity = f"toolu_live_{index}"
        if tool == "Agent":
            parent = identity
        _step(args.log, identity, tool, tool_input, helper=parent if helper else None, at=datetime.now(timezone.utc))
        if index < len(LIVE) - 1:
            _result(args.log, identity, helper=parent if helper else None, at=datetime.now(timezone.utc))
    last, tool = f"toolu_live_{len(LIVE) - 1}", LIVE[-1][1]
    beats = iter(range(1, 1000))
    if args.mode == "limit":
        _hold(run, args.limit_at or QUIET_UNTIL, started, lambda: _heartbeat(args.log, last, tool, next(beats)))
        _held(run, args.hold_until, lambda: _heartbeat(args.log, last, tool, next(beats)))
        run.complete("interrupted", "ceiling")
        return 0
    _hold(run, QUIET_UNTIL, started, lambda: _heartbeat(args.log, last, tool, next(beats)))
    _result(args.log, last, helper=None, at=datetime.now(timezone.utc))
    _hold(run, END_AT, started)
    _held(run, args.hold_until)
    if args.mode == "crash":
        os._exit(70)  # It dies where it stands; its record is never completed.
    run.complete("success" if args.mode == "ready" else "failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

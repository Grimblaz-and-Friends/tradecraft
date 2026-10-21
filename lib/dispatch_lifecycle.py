"""Persist a launch as it happens; a final atomic write alone completes it."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time

from run_lifecycle import (ELAPSED_CHECKPOINT_INTERVAL_SECONDS, ELAPSED_CHECKPOINT_MARGIN_SECONDS,
                           current_deadline, process_identity)

SESSION = re.compile(r"[0-9a-f]{8}-[0-9a-f-]{27,}\Z", re.I)
HEADER = re.compile(r"(?im)^session id:\s*([0-9a-f]{8}-[0-9a-f-]{27,})\s*$")


def atomic_record(path, value):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".run-", delete=False) as stream:
        staged = Path(stream.name)
        stream.write((json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())
    try:
        # A Windows reader opened without delete sharing can briefly prevent
        # replacement. Retry the staged write, never the vendor launch, and keep
        # the retry inside the caller's recording allowance.
        retry_end = time.monotonic() + 1.0
        deadline = current_deadline()
        if deadline is not None:
            retry_end = min(retry_end, deadline.end - deadline.reserve / 4)
        while True:
            try:
                os.replace(staged, path)
                break
            except PermissionError as exc:
                remaining = retry_end - time.monotonic()
                if (os.name != "nt" or getattr(exc, "winerror", None) not in (5, 32, 33)
                        or not path.exists() or remaining <= 0):
                    raise
                time.sleep(min(0.01, remaining))
    finally:
        staged.unlink(missing_ok=True)


def claude_terminal(raw):
    """Read historical JSON or the terminal result in a stream-json log."""
    try:
        value = json.loads(raw.decode("utf-8"))
        if isinstance(value, dict):
            return value
    except (UnicodeError, ValueError):
        pass
    result = None
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except (UnicodeError, ValueError):
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            result = event
    return result


# Every Claude launch from either launcher runs with background work switched
# off and one command allowed to run as long as the launch itself (#887). The
# process environment wins over every settings source a launch reads, so these
# overwrite any inherited value rather than defer to one.
CLAUDE_BACKGROUND_SWITCH = "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"
CLAUDE_COMMAND_CEILING = "BASH_MAX_TIMEOUT_MS"
# Each can leave work running past the reply, or schedule a continuation the
# reply ends, even with background tasks switched off. Seats and use consumers
# name none of them in their --tools list.
CLAUDE_DISALLOWED_TOOLS = ("Monitor", "ScheduleWakeup", "CronCreate", "Workflow")
CLAUDE_DISALLOWED_ARGUMENT = "--disallowedTools=" + ",".join(CLAUDE_DISALLOWED_TOOLS)
NOT_RECORDED = "not recorded: launched before #887"
NOT_LAUNCHED = "not applied: the attempt was not launched"
NOT_COMPLETED = "not yet recorded: the launch has not completed"


def claude_command_ceiling_ms(allocation_seconds):
    return max(1, math.floor(allocation_seconds * 1000))


def claude_launch_env(base, allocation_seconds):
    env = dict(os.environ if base is None else base)
    env[CLAUDE_BACKGROUND_SWITCH] = "1"
    env[CLAUDE_COMMAND_CEILING] = str(claude_command_ceiling_ms(allocation_seconds))
    return env


def claude_launch_notice(allocation_seconds):
    ceiling = claude_command_ceiling_ms(allocation_seconds)
    seconds = f"{ceiling / 1000:.3f}".rstrip("0").rstrip(".")
    return (
        "Launcher notice: background work is switched off in this session. A command that "
        "outlives its timeout is stopped and reported to you, and work still running when you "
        "give your final reply fails this turn. One command may run up to "
        f"{seconds} seconds ({ceiling} ms), the time this launch gives you: when a command needs "
        f"longer than the 2-minute default, pass a Bash timeout of up to {ceiling}.\n"
    ).encode("utf-8")


def claude_launch_controls(allocation_seconds, notice, *, disallowed):
    return {
        "background_tasks": "disabled",
        "background_tasks_source": f"child process environment {CLAUDE_BACKGROUND_SWITCH}=1",
        "command_ceiling_ms": claude_command_ceiling_ms(allocation_seconds),
        "command_ceiling_source": f"child process environment {CLAUDE_COMMAND_CEILING}",
        "disallowed_tools": list(disallowed),
        "notice": notice.decode("utf-8"),
        "notice_sha256": hashlib.sha256(notice).hexdigest(),
    }


TASK_EVENTS = frozenset({"task_started", "task_updated", "task_progress", "task_notification"})
TERMINAL_TASK_STATUSES = frozenset({"completed", "failed", "killed", "stopped"})


def _opener(event):
    text = event.get("result")
    return event.get("num_turns") == 0 and not (isinstance(text, str) and text.strip())


def _task_status(event):
    if event.get("subtype") == "task_updated":
        patch = event.get("patch")
        return patch.get("status") if isinstance(patch, dict) else None
    if event.get("subtype") == "task_notification":
        return event.get("status")
    return None


def claude_stream_check(raw):
    """Find work that outlived the session's return in a stream-json log.

    The return is the first result that is not a resumed session's opening
    empty result. The turn ends at the first post_turn_summary before it, or at
    the return. Events at or before the last opener belong to an earlier
    session and never count. The check fires on (a) a further result after the
    return, (b) a task event after it, or (c) a task still running when the
    turn ended, including one that reports completion afterwards.
    """
    events = []
    for number, line in enumerate(raw.splitlines(), 1):
        try:
            event = json.loads(line)
        except (UnicodeError, ValueError):
            continue
        if isinstance(event, dict):
            events.append((number, event))
    check = {"status": "unread", "reason": None, "return_line": None, "turn_end_line": None,
             "result_lines": [n for n, e in events if e.get("type") == "result"],
             "causes": [], "backgrounded_tasks_observed": [], "return": None}
    if not events:
        check["reason"] = "no stream events were parsed"
        return check
    backgrounded = []
    for _number, event in events:
        if event.get("type") != "system" or event.get("subtype") not in TASK_EVENTS:
            continue
        patch = event.get("patch") if isinstance(event.get("patch"), dict) else {}
        if (event.get("is_backgrounded") is True or patch.get("is_backgrounded") is True
                or event.get("task_type") == "local_workflow"):
            task = event.get("task_id")
            if task not in backgrounded:
                backgrounded.append(task)
    check["backgrounded_tasks_observed"] = backgrounded
    opener_line, returned = 0, None
    for number, event in events:
        if event.get("type") != "result":
            continue
        if _opener(event):
            opener_line = number
            continue
        returned = (number, event)
        break
    if returned is None:
        check["reason"] = "no result followed the session's opening"
        return check
    return_line, check["return"] = returned
    turn_end = next((number for number, event in events if opener_line < number < return_line
                     and event.get("type") == "system" and event.get("subtype") == "post_turn_summary"),
                    return_line)
    check.update(return_line=return_line, turn_end_line=turn_end)
    causes = []
    for number, event in events:
        if number > return_line and event.get("type") == "result":
            causes.append({"kind": "further_reply", "task_id": None, "line": number})
    for number, event in events:
        if (number > return_line and event.get("type") == "system"
                and event.get("subtype") in TASK_EVENTS):
            causes.append({"kind": "task_event_after_return", "task_id": event.get("task_id"),
                           "line": number})
    seen, ended = {}, set()
    for number, event in events:
        if not opener_line < number < turn_end:
            continue
        if event.get("type") != "system" or event.get("subtype") not in TASK_EVENTS:
            continue
        task = event.get("task_id")
        seen.setdefault(task, number)
        if _task_status(event) in TERMINAL_TASK_STATUSES:
            ended.add(task)
    for task, number in seen.items():
        if task not in ended:
            causes.append({"kind": "task_running_at_return", "task_id": task, "line": number})
    check["causes"] = causes
    check["status"] = "work_outlived_return" if causes else "clean"
    return check


def stream_check_record(check):
    """The run-record form: everything but the selected return's payload."""
    return {key: value for key, value in check.items() if key != "return"}


def stream_check_reason(check):
    described = []
    for cause in check["causes"]:
        if cause["kind"] == "further_reply":
            described.append(f"a further reply at stdout line {cause['line']}")
        elif cause["kind"] == "task_event_after_return":
            described.append(f"task {cause['task_id']} reported at stdout line {cause['line']} after the return")
        else:
            described.append(f"task {cause['task_id']} (started by stdout line {cause['line']}) "
                             "was still running when the turn ended")
    return ("work outlived the return: " + "; ".join(described)
            + f"; the earlier reply is the result at stdout line {check['return_line']}, retained in the log")


class GrowingRun:
    def __init__(self, path, record, streams, *, expected=None, holder=None,
                 retained=None, retained_source=None):
        self.path, self.record, self.streams = path, record, streams
        self.expected, self.holder = expected, holder
        self.pending = {"stdout": b"", "stderr": b""}
        self.last_tick = 0
        self.started = None
        self.closed = False
        self.identity_changed = False
        record["launcher_process"] = process_identity()
        record["lifecycle"] = "running"
        record["elapsed_checkpoint_seconds"] = 0
        record["elapsed_checkpoint_interval_seconds"] = ELAPSED_CHECKPOINT_INTERVAL_SECONDS
        record["elapsed_checkpoint_margin_seconds"] = ELAPSED_CHECKPOINT_MARGIN_SECONDS
        if retained:
            record["session_identity"] = {"session_id": retained,
                "source": "proved predecessor", "bundle": retained_source,
                "reported_session_id": None, "reported_source": None}
        # Release the empty reservation's handle before replacing it on Windows.
        streams.streams.pop(path).close()
        self.checkpoint()

    def checkpoint(self):
        if self.closed:
            raise RuntimeError("completed run is immutable")
        atomic_record(self.path, self.record)
        self.identity_changed = False

    def begin_attempt(self, attempt, vendor, stdout_path, stderr_path):
        if self.started is not None:
            self.record.pop("session_identity", None)
            self.record.pop("session_identity_error", None)
            self.started = None
        self.attempt, self.vendor = attempt, vendor
        self.paths = {"stdout": stdout_path, "stderr": stderr_path}
        self.pending = {"stdout": b"", "stderr": b""}
        attempt.update(stdout=str(stdout_path), stderr=str(stderr_path),
                       stdout_encoding="raw-bytes", stderr_encoding="raw-bytes")
        self.checkpoint()

    def launched(self, pid):
        self.started = time.monotonic()
        self.attempt["launched"] = True
        try:
            self.record["recipient_process"] = process_identity(pid)
        except (OSError, ProcessLookupError):
            self.record["recipient_process"] = {"pid": pid, "unavailable_reason": "process exited before identity read"}
        self.checkpoint()

    def tick(self, *, persist=True):
        current = time.monotonic()
        if self.started is not None:
            self.record["elapsed_checkpoint_seconds"] = current - self.started
        if persist and (self.identity_changed or current - self.last_tick >= ELAPSED_CHECKPOINT_INTERVAL_SECONDS):
            self.last_tick = current
            self.checkpoint()

    def observe(self, session, source):
        if not isinstance(session, str) or not SESSION.fullmatch(session):
            return
        identity = self.record.setdefault("session_identity", {})
        before = dict(identity)
        previous_error = self.record.get("session_identity_error")
        previous = identity.get("session_id")
        identity.update(reported_session_id=session, reported_source=source)
        if session == self.holder:
            self.record["session_identity_error"] = "runtime returned the holder session as the builder session"
        elif self.expected and session != self.expected:
            self.record["session_identity_error"] = f"reported session {session} differs from requested {self.expected}"
        elif previous and previous != session:
            self.record["session_identity_error"] = f"runtime changed observed session from {previous} to {session}"
        else:
            identity.update(session_id=session, source=source)
            self.attempt.setdefault("observed", {}).update(session_id=session, session_id_source=source)
        self.identity_changed |= (identity != before or self.record.get("session_identity_error") != previous_error)

    def output(self, name, chunk):
        stream = self.streams[self.paths[name]]
        stream.write(chunk)
        stream.flush()
        self.pending[name] += chunk
        lines = self.pending[name].split(b"\n")
        self.pending[name] = lines.pop()
        for line in lines:
            self.event(name, line)
        # Flush raw bytes on every chunk; atomically record new identity at once
        # and elapsed time on the timer, without duplicate fsyncs per chunk.
        self.tick()

    def event(self, name, line):
        if name == "stderr":
            match = HEADER.search(line.decode("utf-8", "replace"))
            if (self.vendor == "codex" and self.attempt.get("source_format") != "codex-app-server-v2"
                    and match):
                self.observe(match.group(1), "codex stderr session id header")
            return
        try:
            event = json.loads(line)
        except (UnicodeError, ValueError):
            return
        if not isinstance(event, dict):
            return
        if (self.vendor == "codex" and self.attempt.get("source_format") != "codex-app-server-v2"
                and event.get("type") == "thread.started"):
            self.observe(event.get("thread_id"), "codex JSONL thread.started.thread_id")
        elif self.vendor == "claude":
            if event.get("type") == "system" and event.get("subtype") == "init":
                self.observe(event.get("session_id"), "claude stream-json system.init.session_id")
            elif event.get("type") == "result":
                self.observe(event.get("session_id"), "claude JSON result.session_id")

    def finish_attempt(self):
        for name, data in self.pending.items():
            if data:
                self.event(name, data)
        # Finalization owns the next durable completion write. Preserve a newly
        # parsed trailing identity immediately, but do not spend the reserve on
        # another timer checkpoint after the runner has already stopped.
        self.tick(persist=self.identity_changed)

    def finish(self):
        self.record["lifecycle"] = "completed"
        self.record["completed_at"] = datetime.now(timezone.utc).isoformat()
        self.checkpoint()
        self.closed = True

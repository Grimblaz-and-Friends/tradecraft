"""Persist a launch as it happens; a final atomic write alone completes it."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
import time

from run_lifecycle import process_identity

SESSION = re.compile(r"[0-9a-f]{8}-[0-9a-f-]{27,}\Z", re.I)
HEADER = re.compile(r"(?im)^session id:\s*([0-9a-f]{8}-[0-9a-f-]{27,})\s*$")


def atomic_record(path, value):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".run-", delete=False) as stream:
        staged = Path(stream.name)
        stream.write((json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def claude_terminal(raw):
    """Read historical JSON or the terminal result in a stream-json log."""
    decoded = raw.decode("utf-8")
    try:
        value = json.loads(decoded)
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


class GrowingRun:
    def __init__(self, path, record, streams, *, expected=None, holder=None,
                 retained=None, retained_source=None):
        self.path, self.record, self.streams = path, record, streams
        self.expected, self.holder = expected, holder
        self.pending = {"stdout": b"", "stderr": b""}
        self.last_tick = 0
        self.started = None
        self.closed = False
        record["launcher_process"] = process_identity()
        record["lifecycle"] = "running"
        record["elapsed_checkpoint_seconds"] = 0
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

    def tick(self):
        current = time.monotonic()
        if self.started is not None:
            self.record["elapsed_checkpoint_seconds"] = current - self.started
        if current - self.last_tick >= 0.25:
            self.last_tick = current
            self.checkpoint()

    def observe(self, session, source):
        if not isinstance(session, str) or not SESSION.fullmatch(session):
            return
        identity = self.record.setdefault("session_identity", {})
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

    def output(self, name, chunk):
        stream = self.streams[self.paths[name]]
        stream.write(chunk)
        stream.flush()
        self.pending[name] += chunk
        lines = self.pending[name].split(b"\n")
        self.pending[name] = lines.pop()
        for line in lines:
            self.event(name, line)
        self.tick()
        # Identity changes become durable immediately, independently of the timer.
        self.checkpoint()

    def event(self, name, line):
        if name == "stderr":
            match = HEADER.search(line.decode("utf-8", "replace"))
            if self.vendor == "codex" and match:
                self.observe(match.group(1), "codex stderr session id header")
            return
        try:
            event = json.loads(line)
        except (UnicodeError, ValueError):
            return
        if not isinstance(event, dict):
            return
        if self.vendor == "codex" and event.get("type") == "thread.started":
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
        self.tick()

    def finish(self):
        self.record["lifecycle"] = "completed"
        self.record["completed_at"] = datetime.now(timezone.utc).isoformat()
        self.checkpoint()
        self.closed = True

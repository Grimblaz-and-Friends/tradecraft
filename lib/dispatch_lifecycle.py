"""Persist a launch as it happens; a final atomic write alone completes it."""
from __future__ import annotations

from datetime import datetime, timezone
import json
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
        # Finalization owns the next durable completion write. Preserve a newly
        # parsed trailing identity immediately, but do not spend the reserve on
        # another timer checkpoint after the runner has already stopped.
        self.tick(persist=self.identity_changed)

    def finish(self):
        self.record["lifecycle"] = "completed"
        self.record["completed_at"] = datetime.now(timezone.utc).isoformat()
        self.checkpoint()
        self.closed = True

"""One run's pre-launch state: its clock, its timing split, its read memo and store indexes.

Design: lib/DESIGN.md#the-entrances-work-before-a-launch
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
import math
from pathlib import Path
import threading
import time

PARTS = ("github", "removals", "markers", "launch_preparation", "vendor")
UNTIL = ("report", "handoff", "request-record", "spawn")
_SCOPE: ContextVar["Scope | None"] = ContextVar("tradecraft_preflight", default=None)


class Scope:
    """Everything one run learns before its launch, kept only for that run's process."""

    def __init__(self, *, started=None, seed=None):
        seed = seed if isinstance(seed, dict) else {}
        start = seed.get("started_monotonic", started)
        now = time.monotonic()
        # A seed's start comes from the entrance's own monotonic clock on this machine.
        self.started = float(start) if isinstance(start, (int, float)) and math.isfinite(start) and start <= now else (
            now if started is None else float(started))
        self.parts = {name: 0.0 for name in PARTS}
        for name, value in (seed.get("parts") or {}).items():
            if name in self.parts and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0:
                self.parts[name] = float(value)
        route = seed.get("read_route") or {}
        self.contained = int(route.get("contained", 0) or 0)
        self.fallback = int(route.get("fallback", 0) or 0)
        self.fallback_reasons = [str(item) for item in route.get("fallback_reasons", [])][:20]
        self._stack: list[list] = []
        self._lock = threading.Lock()
        self.memo: dict = {}
        self.ref_memo: dict = {}
        self.indexes: dict = {}
        self._closers: list = []

    # The innermost part wins: entering one pauses the part around it.
    def enter(self, name):
        if name not in self.parts:
            raise ValueError(f"unknown preflight part {name!r}")
        now = time.monotonic()
        with self._lock:
            if self._stack:
                outer = self._stack[-1]
                self.parts[outer[0]] += now - outer[1]
            self._stack.append([name, now])

    def leave(self):
        now = time.monotonic()
        with self._lock:
            name, resumed = self._stack.pop()
            self.parts[name] += now - resumed
            if self._stack:
                self._stack[-1][1] = now

    def current_parts(self):
        now = time.monotonic()
        with self._lock:
            parts = dict(self.parts)
            if self._stack:
                name, resumed = self._stack[-1]
                parts[name] += now - resumed
        return parts

    def note_read(self, contained=True, reason=None):
        with self._lock:
            if contained:
                self.contained += 1
            else:
                self.fallback += 1
                if reason and reason not in self.fallback_reasons and len(self.fallback_reasons) < 20:
                    self.fallback_reasons.append(str(reason))

    def read_route(self):
        return {"contained": self.contained, "fallback": self.fallback,
                "fallback_reasons": list(self.fallback_reasons)}

    def snapshot(self, until):
        """The split from this run's call to now, as every report and record prints it."""
        if until not in UNTIL:
            raise ValueError(f"unknown preflight boundary {until!r}")
        total = max(0.0, time.monotonic() - self.started)
        return render(until, total, self.current_parts(), self.read_route())

    def mark(self):
        return time.monotonic(), self.current_parts()

    def since(self, mark):
        """Seconds and parts spent since `mark` (the attempt's pre-spawn interval)."""
        at, before = mark
        now_parts = self.current_parts()
        seconds = max(0.0, time.monotonic() - at)
        parts = {name: max(0.0, now_parts[name] - before.get(name, 0.0)) for name in PARTS}
        return round(seconds, 2), _rendered_parts(seconds, parts)

    def handoff(self):
        return {"schema_version": 1, "started_monotonic": self.started,
                "parts": self.current_parts(), "read_route": self.read_route()}

    def index(self, root, factory):
        key = str(Path(root).resolve()) if root is not None else None
        with self._lock:
            found = self.indexes.get(key)
            if found is None:
                found = self.indexes[key] = factory()
        return found

    def refresh(self):
        """A child that is not a read has returned: what it may have changed is read again."""
        self.ref_memo.clear()
        for index in list(self.indexes.values()):
            stale = getattr(index, "mark_stale", None)
            if stale:
                stale()

    def on_close(self, callback):
        self._closers.append(callback)

    def close(self):
        while self._closers:
            try:
                self._closers.pop()()
            except Exception:  # noqa: BLE001 - closing a scope must not mask the run's own result.
                pass


def _rendered_parts(total, parts):
    rounded = {f"{name}_seconds": round(parts.get(name, 0.0), 2) for name in PARTS}
    rounded["unattributed_seconds"] = round(max(0.0, total - sum(parts.get(name, 0.0) for name in PARTS)), 2)
    return rounded


def render(until, total, parts, read_route):
    return {"schema_version": 1, "until": until, "total_seconds": round(total, 2),
            "parts": _rendered_parts(total, parts), "read_route": read_route}


def combine(record_split, pre_spawn_seconds, pre_spawn_parts):
    """The request record's split continued to the recipient's spawn (`until: spawn`)."""
    total = float(record_split.get("total_seconds", 0.0)) + float(pre_spawn_seconds or 0.0)
    parts = {}
    for name in PARTS:
        key = f"{name}_seconds"
        parts[name] = float(record_split.get("parts", {}).get(key, 0.0)) + float((pre_spawn_parts or {}).get(key, 0.0))
    return render("spawn", total, parts, record_split.get("read_route") or
                  {"contained": 0, "fallback": 0, "fallback_reasons": []})


def current() -> Scope | None:
    return _SCOPE.get()


@contextmanager
def scope(*, started=None, seed=None):
    """Open one run's scope, or join the one already open."""
    existing = _SCOPE.get()
    if existing is not None:
        yield existing
        return
    opened = Scope(started=started, seed=seed)
    token = _SCOPE.set(opened)
    try:
        yield opened
    finally:
        _SCOPE.reset(token)
        opened.close()


@contextmanager
def part(name):
    opened = _SCOPE.get()
    if opened is None:
        yield
        return
    opened.enter(name)
    try:
        yield
    finally:
        opened.leave()


def note_read(contained=True, reason=None):
    opened = _SCOPE.get()
    if opened is not None:
        opened.note_read(contained, reason)


def snapshot(until):
    opened = _SCOPE.get()
    return opened.snapshot(until) if opened is not None else None


def refresh():
    opened = _SCOPE.get()
    if opened is not None:
        opened.refresh()


def write_handoff(path):
    opened = _SCOPE.get()
    if opened is None:
        return None
    Path(path).write_text(json.dumps(opened.handoff()), encoding="utf-8")
    return Path(path)


def load_handoff(path):
    """A launcher called directly has no handoff and measures from its own start."""
    if path is None:
        return None
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) and value.get("schema_version") == 1 else None

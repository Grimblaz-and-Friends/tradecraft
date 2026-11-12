"""Caller deadlines, Git content progress and build-only runtime accounting."""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import threading
import time

import preflight
import seat_process

DEFAULT_BUILD_TIMEOUT_SECONDS = 7200.0
DEFAULT_STAGE_TIMEOUT_SECONDS = 3600.0
TOTAL_BUILD_BUDGET_SECONDS = 14400.0
MINIMUM_CLEANUP_RESERVE_SECONDS = 10.0
ELAPSED_CHECKPOINT_INTERVAL_SECONDS = 0.25
ELAPSED_CHECKPOINT_MARGIN_SECONDS = 10.0
REPAIR_STAGES = frozenset({"floor", "review-disposition"})
_DEADLINE = ContextVar("tradecraft_caller_deadline", default=None)
_CLEANUP = ContextVar("tradecraft_recording_phase", default=False)


class RunTimeout(TimeoutError):
    """The run's own time ended; `limit` names the limit that ended it.

    Design: lib/DESIGN.md#the-entrances-work-before-a-launch
    """

    def __init__(self, message, deadline=None):
        super().__init__(message)
        self.limit = limit_phrase(deadline)


def limit_phrase(deadline=None):
    """Name the limit that ends this run, the one place a limit is named."""
    deadline = deadline if deadline is not None else current_deadline()
    if deadline is None:
        return "no run limit is set"
    stage = getattr(deadline, "stage", None)
    if stage in REPAIR_STAGES and deadline.end < deadline.started + deadline.limit:
        return f"the {stage} stage's {DEFAULT_STAGE_TIMEOUT_SECONDS:g}-second ceiling"
    declared = getattr(deadline, "declared", None)
    source = ("declared by --timeout-seconds" if declared else
              "the stage's default" if declared is False else "the caller's limit")
    return f"the {deadline.limit:g}-second limit ({source})"


class Deadline:
    def __init__(self, limit, *, started=None):
        if not math.isfinite(limit) or limit <= 0:
            raise ValueError("caller limit must be finite and positive")
        self.limit = float(limit)
        self.started = time.monotonic() if started is None else started
        if not math.isfinite(self.started) or self.started > time.monotonic():
            raise ValueError("invocation start must be a finite past monotonic time")
        self.reserve = min(60.0, max(MINIMUM_CLEANUP_RESERVE_SECONDS, self.limit / 10))
        self.end = self.started + self.limit
        self.probe_seconds = 0.0

    def remaining(self, *, cleanup=False):
        remaining = self.end - time.monotonic() - (0 if cleanup else self.reserve)
        if remaining <= 0:
            raise RunTimeout("caller limit leaves no useful launch window", self)
        return remaining

    def probe(self, default=20, *, cleanup=False):
        remaining = self.remaining(cleanup=cleanup)
        if cleanup:
            # Cleanup probes share only half the reserve. Closing streams and
            # atomically completing the record still need time afterward.
            remaining -= self.reserve / 2
        if remaining <= 0:
            raise RunTimeout("caller limit leaves no probe window before final recording", self)
        if cleanup and remaining <= self.probe_seconds:
            raise RunTimeout("remaining cleanup window is shorter than an observed probe", self)
        return min(default, remaining)

    def note_probe(self, started):
        self.probe_seconds = max(self.probe_seconds, time.monotonic() - started)

    @property
    def cleanup_end(self):
        return self.end - self.reserve / 2

    @property
    def wait_end(self):
        # The entrance stops waiting for its launcher here, keeping time to
        # contain the launcher's tree and return.
        return self.end - self.reserve / 4

    @property
    def final_write_at(self):
        """The latest moment a launcher's final recording may begin.

        Design: lib/DESIGN.md#the-launch-comparisons-crediting-and-allowance
        """
        # The same eighth the entrance leaves between its wait's end and stopping the launcher.
        return self.wait_end - self.reserve / 8


def stage_deadline(stage, caller_limit, *, started=None, declared=None):
    deadline = Deadline(caller_limit, started=started)
    deadline.stage, deadline.declared = stage, declared
    if stage in REPAIR_STAGES:
        deadline.end = min(deadline.end, deadline.started + DEFAULT_STAGE_TIMEOUT_SECONDS)
    return deadline


def current_deadline():
    return _DEADLINE.get()


def cleanup_deadline():
    deadline = current_deadline()
    return deadline.cleanup_end if deadline else None


def ceiling_reason(vendor, *, caller_limit, allocation, elapsed):
    return (f"{vendor} stopped at the recipient ceiling; caller limit {caller_limit:g}s; "
            f"recipient allocation {allocation:.2f}s; measured elapsed {elapsed:.2f}s")


@contextmanager
def deadline_scope(deadline):
    token = _DEADLINE.set(deadline)
    try:
        yield deadline
    finally:
        _DEADLINE.reset(token)


@contextmanager
def cleanup_scope():
    token = _CLEANUP.set(True)
    try:
        yield
    finally:
        _CLEANUP.reset(token)


def probe_timeout(default=20, *, cleanup=None):
    deadline = current_deadline()
    phase = _CLEANUP.get() if cleanup is None else cleanup
    return deadline.probe(default, cleanup=phase) if deadline else default


def process_identity(pid=None):
    pid = os.getpid() if pid is None else pid
    identity = {"pid": pid, "host": socket.gethostname(), "birth": None}
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        handle = kernel.OpenProcess(0x101000, False, pid)
        if not handle:
            # ERROR_INVALID_PARAMETER means this process no longer exists.
            if ctypes.get_last_error() == 87:
                raise ProcessLookupError(pid)
            raise OSError("cannot read process identity")
        try:
            status = kernel.WaitForSingleObject(handle, 0)
            if status == 0:
                raise ProcessLookupError(pid)
            if status != 258:
                raise OSError("cannot establish process liveness")
            values = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *(ctypes.byref(v) for v in values)):
                raise OSError("cannot read process creation time")
            identity["birth"] = str(values[0].dwHighDateTime << 32 | values[0].dwLowDateTime)
        finally:
            kernel.CloseHandle(handle)
    else:
        try:
            # The command name may contain spaces or parentheses.
            fields = Path(f"/proc/{pid}/stat").read_bytes().rsplit(b")", 1)[1].split()
            if fields[0] == b"Z":
                raise ProcessLookupError(pid)
            identity["birth"] = fields[19].decode("ascii")
        except FileNotFoundError:
            if Path("/proc").is_dir():
                raise ProcessLookupError(pid) from None
            result = seat_process.run_read(["ps", "-p", str(pid), "-o", "lstart="],
                                           cwd=None, timeout=1)
            if result.returncode == 1:
                raise ProcessLookupError(pid)
            if result.returncode != 0 or not result.stdout.strip():
                raise OSError("cannot read process identity")
            identity["birth"] = result.stdout.decode("ascii").strip()
    return identity


def _identity_liveness(identity):
    if not isinstance(identity, dict) or identity.get("host") != socket.gethostname():
        return "unresolved"
    if not isinstance(identity.get("pid"), int) or not identity.get("birth"):
        return "unresolved"
    try:
        current = process_identity(identity["pid"])
    except ProcessLookupError:
        return "stopped"
    except (OSError, ValueError):
        return "unresolved"
    return "active" if current == identity else "stopped"


def liveness(run):
    status = _identity_liveness(run.get("launcher_process"))
    if status != "stopped":
        return status
    if run.get("completed_at") and run.get("cleanup_proven") is True:
        return "stopped"
    # A launcher may die without taking an escaped or orphaned recipient with it.
    if "recipient_process" in run:
        return _identity_liveness(run["recipient_process"])
    return "stopped"


def content_snapshot(root, *, timeout=20):
    """Hash HEAD, index entries and exact nonignored working content."""
    end = time.monotonic() + timeout
    def git(*args):
        allowance = end - time.monotonic()
        if allowance <= 0:
            raise TimeoutError("content snapshot deadline")
        command = ["git", "-C", str(root), *args]
        result = seat_process.run_read(command, input=b"", cwd=Path.cwd(), timeout=allowance,
                                       cleanup_deadline=cleanup_deadline())
        if result.returncode:
            raise OSError("cannot read Git content snapshot: " + result.stderr.decode("utf-8", "replace"))
        return result.stdout
    try:
        root = Path(root)
        head = git("rev-parse", "HEAD").strip().decode("ascii")
        index = git("ls-files", "--stage", "-z")
        paths = sorted(set(git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0")) - {b""})
        digest = hashlib.sha256()
        digest.update(head.encode("ascii") + b"\0" + hashlib.sha256(index).digest())
        for raw in paths:
            if time.monotonic() >= end:
                raise TimeoutError("content snapshot deadline")
            digest.update(b"\0path\0" + raw + b"\0")
            path = root / os.fsdecode(raw)
            if path.is_symlink():
                digest.update(b"link\0" + os.fsencode(os.readlink(path)))
            elif path.is_dir():
                # A submodule's tracked content is its own Git tree.
                child = content_snapshot(path, timeout=max(0.01, end - time.monotonic()))
                if child.get("digest") is None:
                    raise OSError("unreadable submodule snapshot")
                digest.update(b"submodule\0" + child["digest"].encode("ascii"))
            elif not path.exists():
                digest.update(b"deleted")
            else:
                digest.update(b"file\0" + str(path.stat().st_mode & 0o111).encode("ascii") + b"\0")
                content = hashlib.sha256()
                with path.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        if time.monotonic() >= end:
                            raise TimeoutError("content snapshot deadline")
                        content.update(chunk)
                digest.update(content.digest())
        return {"head": head, "digest": digest.hexdigest(), "unavailable_reason": None}
    except (OSError, ValueError, TimeoutError, subprocess.TimeoutExpired) as exc:
        return {"head": None, "digest": None, "unavailable_reason": str(exc)}


def progress(baseline, current):
    if not isinstance(baseline, dict) or not isinstance(current, dict):
        return "unknown"
    if not baseline.get("digest") or not current.get("digest"):
        return "unknown"
    return "changed" if baseline["digest"] != current["digest"] else "unchanged"


def runtime_bounds(request, run):
    if run.get("recovery_error"):
        return {"lower_seconds": 0, "upper_seconds": None, "basis": run["recovery_error"],
                "lower_basis": "runtime evidence unavailable", "upper_basis": run["recovery_error"]}
    attempts = run.get("attempts") or []
    if run.get("completed_at") and attempts:
        measured = [a.get("elapsed_seconds") for a in attempts if isinstance(a, dict) and a.get("launched") is not False]
        if all(isinstance(a, dict) for a in attempts) and all(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0 for v in measured):
            total = sum(measured)
            return {"lower_seconds": total, "upper_seconds": total, "basis": "measured recipient runtime",
                    "lower_basis": "measured recipient runtime", "upper_basis": "measured recipient runtime"}
    checkpoint = run.get("elapsed_checkpoint_seconds")
    valid_checkpoint = (isinstance(checkpoint, (int, float)) and not isinstance(checkpoint, bool)
                        and math.isfinite(checkpoint) and checkpoint >= 0)
    lower = checkpoint if valid_checkpoint else 0
    lower_basis = "last durable elapsed checkpoint" if valid_checkpoint else "no valid elapsed checkpoint; zero lower bound"
    allocation = request.get("recipient_allocation_seconds")
    upper = max(lower, allocation) if isinstance(allocation, (int, float)) and math.isfinite(allocation) and allocation >= 0 else None
    upper_basis = "enforced recipient allocation" if upper is not None else "runtime upper bound unavailable"
    # Historical growing records used the same timer but did not retain its
    # policy. Missing process identities still leave liveness unresolved.
    interval = run.get("elapsed_checkpoint_interval_seconds", ELAPSED_CHECKPOINT_INTERVAL_SECONDS)
    margin = run.get("elapsed_checkpoint_margin_seconds", ELAPSED_CHECKPOINT_MARGIN_SECONDS)
    timing_known = all(isinstance(v, (int, float)) and not isinstance(v, bool)
                       and math.isfinite(v) and v > 0 for v in (interval, margin))
    if not run.get("completed_at"):
        launcher = _identity_liveness(run.get("launcher_process"))
        recipient = _identity_liveness(run.get("recipient_process"))
        if not valid_checkpoint:
            upper_basis += "; elapsed checkpoint missing or invalid"
        elif launcher != "stopped" or recipient != "stopped":
            upper_basis += f"; launcher {launcher}, recipient {recipient}"
        elif run.get("cleanup_proven") is False or run.get("launch_unresolved") or not timing_known:
            upper_basis += "; cleanup, spawn or checkpoint timing unproved"
        else:
            checkpoint_upper = lower + interval + margin
            upper = min(upper, checkpoint_upper) if upper is not None else checkpoint_upper
            upper_basis = (f"both processes proved dead; durable checkpoint + {interval:g}s interval + {margin:g}s margin"
                           + ("; capped by enforced allocation" if upper < checkpoint_upper else ""))
    return {"lower_seconds": lower, "upper_seconds": upper,
            "lower_basis": lower_basis, "upper_basis": upper_basis,
            "basis": lower_basis + "; " + upper_basis}


def runtime_account(bundles, *, root=None, branch=None, lineage=None):
    """Count distinct build dispatches; repair runtime stays visible but excluded."""
    rows, seen = [], set()
    for _order, path, request, run in bundles:
        dispatch = request.get("dispatch_id")
        if not dispatch or dispatch in seen:
            continue
        if root is not None and Path(str(request.get("root") or "")).resolve() != Path(root).resolve():
            continue
        if branch is not None and request.get("lineage_branch") != branch:
            continue
        if lineage is not None and request.get("budget_lineage") != lineage:
            continue
        seen.add(dispatch)
        rows.append({"dispatch_id": dispatch, "bundle": path, "stage": request.get("stage"),
                     "excluded": request.get("stage") != "build",
                     "override_reason": request.get("budget_override_reason"),
                     **runtime_bounds(request, run)})
    charged = [row for row in rows if not row["excluded"]]
    lower = sum(row["lower_seconds"] for row in charged)
    upper = (sum(row["upper_seconds"] for row in charged)
             if all(row["upper_seconds"] is not None for row in charged) else None)
    return {"budget_seconds": TOTAL_BUILD_BUDGET_SECONDS, "lower_seconds": lower,
            "upper_seconds": upper,
            "remaining_seconds": max(0, TOTAL_BUILD_BUDGET_SECONDS - upper) if upper is not None else None,
            "runs": rows}


def _json_copy(value):
    """A JSON value's own copy; parsed JSON holds only dicts, lists and immutable scalars."""
    if isinstance(value, dict):
        return {key: _json_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_copy(item) for item in value]
    return value


def _signature(path):
    try:
        status = os.stat(path)
    except OSError:
        return None
    return status.st_size, status.st_mtime_ns


def _read_record(path):
    """One record's signature, bytes (or the OSError) and one parse (or its failure)."""
    # Taken before the read: a write racing the read then shows as a change at the next refresh.
    signature = _signature(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return signature, exc, exc
    try:
        value = json.loads(raw)
    except ValueError as exc:
        value = exc
    return signature, raw, value


class _StoreRecords:
    """One store root's records as this run read them, shared by every spelling of that root.

    Paths are kept relative to the root so each caller's own spelling comes back to it.
    """

    def __init__(self, root):
        self.root = Path(root)
        self._lock = threading.RLock()
        self._requests = None  # relative paths in rglob order; None until listed
        self._runs = None
        self._stale = False
        self._records = {}  # relative path -> (signature, raw, value)

    def mark_stale(self):
        with self._lock:
            self._stale = True

    def forget(self, relative):
        with self._lock:
            self._records.pop(relative, None)
            self._stale = True  # A record the run wrote may be new to the listing too.

    def _relative(self, paths):
        return [path.relative_to(self.root) for path in paths]

    def _listed(self):
        """List on first use, and again after a refresh, rereading only what changed."""
        if self._requests is not None and not self._stale:
            return
        if self._stale:
            for relative, (signature, _raw, _value) in list(self._records.items()):
                if _signature(self.root / relative) != signature:
                    del self._records[relative]
        self._requests = self._relative(self.root.rglob("*.request.json"))
        self._runs = self._relative(self.root.rglob("*.run.json"))
        self._stale = False

    def _record(self, relative):
        found = self._records.get(relative)
        if found is None:
            found = self._records[relative] = _read_record(self.root / relative)
        return found

    # The store is read to check what markers claim, so every read of it counts under markers,
    # even one made while counting removals, and the store's cost stays in one part.
    def requests(self):
        with self._lock, preflight.part("markers"):
            self._listed()
            return [(relative, *self._record(relative)[1:]) for relative in self._requests]

    def listing(self):
        with self._lock, preflight.part("markers"):
            self._listed()
            return list(self._requests), list(self._runs)

    def lookup(self, relative):
        with self._lock, preflight.part("markers"):
            self._listed()
            return self._record(relative)[1:]


class StoreIndex:
    """The dispatch store as this run reads it: each request record once, each selected run once.

    Records come back as copies, so a reader that changes one cannot change what another sees.
    Design: lib/DESIGN.md#the-entrances-work-before-a-launch
    """

    def __init__(self, records, root):
        self._records = records
        self.root = Path(root)

    def _relative(self, path):
        path = Path(path)
        try:
            return path.relative_to(self.root)
        except ValueError:
            return path.resolve().relative_to(self._records.root.resolve())

    def requests(self, where=None):
        """`(path, raw, value)` per request record in rglob order; `where` sees the shared value and must not change it."""
        with preflight.part("markers"):
            return [(self.root / relative, raw, value if isinstance(value, Exception) else _json_copy(value))
                    for relative, raw, value in self._records.requests()
                    if where is None or where(value)]

    def requests_listing(self):
        return [self.root / relative for relative in self._records.listing()[0]]

    def runs_listing(self):
        return [self.root / relative for relative in self._records.listing()[1]]

    def run(self, path):
        """`(raw, value)` for one record, read at most once until it changes or is forgotten."""
        with preflight.part("markers"):
            raw, value = self._records.lookup(self._relative(path))
            return raw, value if isinstance(value, Exception) else _json_copy(value)

    def mark_stale(self):
        self._records.mark_stale()

    def forget(self, path):
        self._records.forget(self._relative(path))


def store_index(store):
    """The open run's index of `store`, or None outside a run or when the store is not a directory."""
    opened = preflight.current()
    if opened is None or store is None or not Path(store).is_dir():
        return None
    root = Path(store)
    return StoreIndex(opened.index(root, lambda: _StoreRecords(root)), root)


def launch_bundles(store, work, stages, *, after=None, exact_work=False, include_missing_stage=False):
    """Discover requests first so an unfinished newest attempt cannot disappear."""
    bundles = {}
    if not Path(store).is_dir():
        return []

    def wanted(request):
        attributed = (request.get("work") == work if exact_work else
                      str(request.get("work", "")).lower() == work.lower()) if isinstance(request, dict) else False
        return attributed and (request.get("stage") in stages
                               or (include_missing_stage and not request.get("stage")))

    index = store_index(store)
    if index is None:
        def requests():
            for path in Path(store).rglob("*.request.json"):
                try:
                    yield path, json.loads(path.read_bytes())
                except (OSError, ValueError):
                    continue  # No attribution can be established.

        def read_run(run_path):
            try:
                return json.loads(run_path.read_bytes())
            except (OSError, ValueError):
                return None
    else:
        # Only attributed requests are copied; a failed parse is never attributed.
        def requests():
            return ((path, value) for path, _raw, value in index.requests(where=wanted))

        def read_run(run_path):
            value = index.run(run_path)[1]
            return None if isinstance(value, Exception) else value
    for path, request in requests():
        if not wanted(request):
            continue
        stamp = request.get("launched_at") or request.get("started_at")
        try:
            moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if moment.tzinfo is None:
                raise ValueError("launch order has no timezone")
            order = moment.astimezone(timezone.utc).isoformat()
        except (AttributeError, TypeError, ValueError):
            # An attributed unproved attempt must not disappear behind an older success.
            order = "9999-12-31T23:59:59+00:00"
        if after is not None and order <= datetime.fromisoformat(after.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat():
            continue
        run_path = path.with_name(path.name.removesuffix(".request.json") + ".run.json")
        run = read_run(run_path)
        if run is None:
            run = {"recovery_error": "run record missing or unreadable"}
        if not isinstance(run, dict):
            run = {"recovery_error": "run record is not an object"}
        if not request.get("stage"):
            run = {**run, "recovery_error": "attributed launch has no stage identity"}
        if order.startswith("9999-"):
            run = {**run, "recovery_error": "launch order missing or invalid"}
        if request.get("schema_version") != 2 or (run.get("schema_version") != 2 and "recovery_error" not in run):
            run = {**run, "recovery_error": "unsupported dispatch schema"}
        if not request.get("dispatch_id") or (run.get("dispatch_id") is not None and run["dispatch_id"] != request["dispatch_id"]):
            run = {**run, "recovery_error": "dispatch identity mismatch"}
        key = request.get("dispatch_id") or str(path)
        previous = bundles.get(key)
        candidate = (order, str(run_path), request, run)
        if previous is None:
            bundles[key] = candidate
        elif str(previous[3].get("recovery_error", "")).startswith("conflicting copied"):
            # A later good copy cannot discharge an already observed conflict.
            bundles[key] = (max(order, previous[0]), str(run_path), request,
                            {**run, "recovery_error": previous[3]["recovery_error"]})
        elif previous[2] != request:
            bundles[key] = (max(order, previous[0]), str(run_path), request, {**run, "recovery_error": "conflicting copied requests"})
        elif run.get("completed_at") and not previous[3].get("completed_at"):
            bundles[key] = candidate
        elif run.get("completed_at") and previous[3].get("completed_at") and run != previous[3]:
            bundles[key] = (order, str(run_path), request, {**run, "recovery_error": "conflicting copied completions"})
    return sorted(bundles.values(), key=lambda item: (item[0], str(item[2].get("dispatch_id")), item[1]))


def stopped(run):
    if run.get("cleanup_proven") is False:
        return True
    if run.get("launch_unresolved"):
        return True
    if str(run.get("recovery_error", "")).startswith("conflicting copied"):
        return True
    if not run.get("completed_at"):
        return True
    # A turn refused because work outlived its return (#887) recovers like a
    # failed launched turn: its own session resumes, never a fresh builder.
    return run.get("lifecycle") == "completed" and run.get("outcome") in {
        "interrupted", "error", "work_outlived_return"} and any(
        a.get("launched") for a in run.get("attempts", []) if isinstance(a, dict))


def allocation(account, requested, *, override_reason=None):
    if override_reason is not None and not override_reason.strip():
        raise ValueError("budget override reason must be nonempty")
    if override_reason:
        return requested
    remaining = account["remaining_seconds"]
    if remaining is None:
        raise ValueError("build runtime upper bound is unknown; --budget-override-reason is required")
    if remaining <= 0:
        raise ValueError("build budget is exhausted; --budget-override-reason is required")
    return min(requested, remaining)


def recovery_session(request, run):
    if run.get("cleanup_proven") is False:
        raise ValueError("descendant cleanup is unproved; refuse another writer")
    if run.get("launch_unresolved"):
        raise ValueError("vendor spawn is unresolved; refuse another writer")
    if run.get("recovery_error"):
        raise ValueError(run["recovery_error"])
    if run.get("session_identity_error"):
        raise ValueError(run["session_identity_error"])
    requested = request.get("requested") or {}
    vendor = requested.get("vendor")
    if vendor not in {"codex", "claude"} or run.get("actual_vendor") != vendor:
        raise ValueError("stopped bundle has unproved vendor")
    if not run.get("completed_at"):
        status = liveness(run)
        if status != "stopped":
            raise ValueError(f"launch liveness is {status}; refuse another writer")
    identities = [a.get("observed", {}).get("session_id") for a in run.get("attempts", [])
                  if isinstance(a, dict) and isinstance(a.get("observed"), dict)]
    identity = run.get("session_identity") or {}
    session = identity.get("session_id")
    if session:
        identities.append(session)
    identities = {value for value in identities if isinstance(value, str) and value}
    if len(identities) != 1:
        raise ValueError("stopped bundle has missing or conflicting session identity")
    session = identities.pop()
    expected = requested.get("session_id") or (request.get("handover") or {}).get("replacement_session")
    if expected and session != expected:
        raise ValueError("reported session differs from requested or reserved identity")
    return session

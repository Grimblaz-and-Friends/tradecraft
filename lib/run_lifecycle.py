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
from seat_process import run_process
import time

DEFAULT_BUILD_TIMEOUT_SECONDS = 7200.0
DEFAULT_STAGE_TIMEOUT_SECONDS = 3600.0
TOTAL_BUILD_BUDGET_SECONDS = 14400.0
REPAIR_STAGES = frozenset({"floor", "review-disposition"})
_DEADLINE = ContextVar("tradecraft_caller_deadline", default=None)
_CLEANUP = ContextVar("tradecraft_recording_phase", default=False)


class Deadline:
    def __init__(self, limit, *, started=None):
        if not math.isfinite(limit) or limit <= 0:
            raise ValueError("caller limit must be finite and positive")
        self.limit = float(limit)
        self.started = time.monotonic() if started is None else started
        if not math.isfinite(self.started) or self.started > time.monotonic():
            raise ValueError("invocation start must be a finite past monotonic time")
        self.reserve = min(60.0, self.limit / 10)
        self.end = self.started + self.limit

    def remaining(self, *, cleanup=False):
        remaining = self.end - time.monotonic() - (0 if cleanup else self.reserve)
        if remaining <= 0:
            raise TimeoutError("caller limit leaves no useful launch window")
        return remaining

    def probe(self, default=20, *, cleanup=False):
        remaining = self.remaining(cleanup=cleanup)
        if cleanup:
            # Cleanup probes share only half the reserve. Closing streams and
            # atomically completing the record still need time afterward.
            remaining -= self.reserve / 2
        if remaining <= 0:
            raise TimeoutError("caller limit leaves no probe window before final recording")
        return min(default, remaining)

    @property
    def cleanup_end(self):
        return self.end - self.reserve / 2


def stage_deadline(stage, caller_limit, *, started=None):
    deadline = Deadline(caller_limit, started=started)
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
            result = subprocess.run(["ps", "-p", str(pid), "-o", "lstart="],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=1)
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
        if current_deadline() is None:
            result = subprocess.run(command, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=allowance)
        else:
            result = run_process(command, input=b"", cwd=Path.cwd(), timeout=allowance,
                                 on_tick=lambda: None, cleanup_deadline=cleanup_deadline())
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
        return {"lower_seconds": 0, "upper_seconds": None, "basis": run["recovery_error"]}
    attempts = run.get("attempts") or []
    if run.get("completed_at") and attempts:
        measured = [a.get("elapsed_seconds") for a in attempts if isinstance(a, dict) and a.get("launched") is not False]
        if all(isinstance(a, dict) for a in attempts) and all(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0 for v in measured):
            total = sum(measured)
            return {"lower_seconds": total, "upper_seconds": total, "basis": "measured recipient runtime"}
    lower = run.get("elapsed_checkpoint_seconds", 0)
    if not isinstance(lower, (int, float)) or not math.isfinite(lower) or lower < 0:
        lower = 0
    allocation = request.get("recipient_allocation_seconds")
    upper = max(lower, allocation) if isinstance(allocation, (int, float)) and math.isfinite(allocation) and allocation >= 0 else None
    return {"lower_seconds": lower, "upper_seconds": upper,
            "basis": "unfinished checkpoint and enforced allocation" if upper is not None else "runtime upper bound unavailable"}


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


def launch_bundles(store, work, stages, *, after=None, exact_work=False):
    """Discover requests first so an unfinished newest attempt cannot disappear."""
    bundles = {}
    if not Path(store).is_dir():
        return []
    for path in Path(store).rglob("*.request.json"):
        try:
            request = json.loads(path.read_bytes())
        except (OSError, ValueError):
            continue  # No attribution can be established.
        attributed = (request.get("work") == work if exact_work else
                      str(request.get("work", "")).lower() == work.lower()) if isinstance(request, dict) else False
        if not attributed or request.get("stage") not in stages:
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
        try:
            run = json.loads(run_path.read_bytes())
        except (OSError, ValueError):
            run = {"recovery_error": "run record missing or unreadable"}
        if not isinstance(run, dict):
            run = {"recovery_error": "run record is not an object"}
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
    if str(run.get("recovery_error", "")).startswith("conflicting copied"):
        return True
    if not run.get("completed_at"):
        return True
    return run.get("lifecycle") == "completed" and run.get("outcome") in {"interrupted", "error"} and any(
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

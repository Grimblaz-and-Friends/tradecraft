"""Which live stretch launch, if any, holds the current process in its process tree.

A builder's shell can clear a variable, but it cannot leave the tree its launcher holds: on
Windows the recipient runs in a kill-on-close job that allows no breakaway, which a stretch
launch names; on Linux the launcher is the recipient's child subreaper. So the tree, not the
variable, decides whether a process is a builder's; the variable only names which launch.
Design: lib/DESIGN.md#a-builders-own-checks-and-writes
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess

DISPATCH_VARIABLE = "TRADECRAFT_STRETCH_DISPATCH"
WORK_VARIABLE = "TRADECRAFT_STRETCH_WORK"
# Read and dropped by the launch worker, which names its job from it; no recipient sees it. It is a
# variable of its own because a seat launched with the other two still set would otherwise name its
# worker's job after the stretch's, find that name taken, and fail to start.
JOB_VARIABLE = "TRADECRAFT_STRETCH_JOB"
JOB_PREFIX = "Local\\tradecraft-stretch-"
VARIABLES = (DISPATCH_VARIABLE, WORK_VARIABLE, JOB_VARIABLE)
POINTERS = "stretch-launches"
DISPATCH_ID = re.compile(r"[0-9a-f]{32}")
JOB_OBJECT_QUERY = 0x0004
ERROR_FILE_NOT_FOUND = 2


class TreeUnknown(OSError):
    """A live launch's tree could not be checked: its job could not be queried, or a parent chain read."""


@dataclass
class Holding:
    """``held`` with the launch, ``none``, or ``unknown`` with the bundle whose check failed."""
    state: str
    launch: dict | None = None
    reason: str = ""

    def record(self) -> dict[str, object]:
        launch = self.launch or {}
        return {"state": self.state, "dispatch_id": launch.get("dispatch_id"),
                "request": launch.get("request"), "reason": self.reason or None}


def job_name(dispatch_id: str) -> str:
    return JOB_PREFIX + dispatch_id


def without_variables(env: dict[str, str]) -> dict[str, str]:
    """A copy of ``env`` that names no stretch launch, for every process a builder-mode entrance starts."""
    return {name: value for name, value in env.items() if name not in VARIABLES}


def pointer_directory(store: Path) -> Path:
    return Path(store) / POINTERS


def write_pointer(store: Path, *, dispatch_id: str, work: str, request: Path, run: Path,
                  session_id: str | None, launcher: dict, root: Path) -> Path:
    """Record a stretch launch where the tree check reads it, so no check walks the whole store."""
    directory = pointer_directory(store)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{dispatch_id}.json"
    staged = path.with_suffix(".tmp")
    staged.write_bytes(json.dumps({
        "schema_version": 1, "dispatch_id": dispatch_id, "work": work, "request": str(request),
        "run": str(run), "session_id": session_id, "launcher_process": launcher,
        "root": str(root)}, indent=2).encode("utf-8"))
    staged.replace(path)
    return path


def live_launches(store: Path) -> list[dict]:
    """The stretch launches whose run is not complete and whose launcher or recipient still lives."""
    import run_lifecycle as lifecycle  # A seat launcher imports this; keep its start light.

    directory = pointer_directory(store)
    try:
        paths = sorted(directory.glob("*.json"))
    except OSError:
        return []
    found = []
    for path in paths:
        try:
            pointer = json.loads(path.read_bytes())
            run = json.loads(Path(pointer["run"]).read_bytes()) if Path(pointer["run"]).is_file() else {}
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if not isinstance(pointer, dict) or not DISPATCH_ID.fullmatch(str(pointer.get("dispatch_id"))):
            continue
        if run.get("completed_at"):
            continue
        state = dict(run)
        state.setdefault("launcher_process", pointer.get("launcher_process"))
        if lifecycle.liveness(state) == "stopped":
            continue
        found.append({**pointer, "recipient_process": run.get("recipient_process")})
    return found


def _windows_in_job(dispatch_id: str) -> bool | None:
    """Whether this process is in the launch's named job, or one nested in it; None when no such job exists."""
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenJobObjectW.restype = wintypes.HANDLE
    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel.IsProcessInJob.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenJobObjectW(JOB_OBJECT_QUERY, False, job_name(dispatch_id))
    if not handle:
        error = ctypes.get_last_error()
        if error == ERROR_FILE_NOT_FOUND:
            return None
        raise TreeUnknown(f"the job of stretch {dispatch_id} could not be opened (error {error})")
    try:
        result = wintypes.BOOL()
        if not kernel.IsProcessInJob(kernel.GetCurrentProcess(), handle, ctypes.byref(result)):
            raise TreeUnknown(f"the job of stretch {dispatch_id} could not be queried "
                              f"(error {ctypes.get_last_error()})")
        return bool(result.value)
    finally:
        kernel.CloseHandle(handle)


def _parent(pid: int) -> int:
    stat = Path(f"/proc/{pid}/stat")
    if Path("/proc").is_dir():
        try:
            return int(stat.read_bytes().rsplit(b")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError) as exc:
            raise TreeUnknown(f"the parent of process {pid} could not be read: {exc}") from exc
    try:
        result = subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True,
                                timeout=5, stdin=subprocess.DEVNULL)
        return int(result.stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise TreeUnknown(f"the parent of process {pid} could not be read: {exc}") from exc


def _posix_below(identities: list[dict]) -> bool:
    """Whether this process's parent chain reaches one of these processes, each matched with its start time."""
    import run_lifecycle as lifecycle

    wanted = {identity.get("pid"): identity for identity in identities if isinstance(identity, dict)}
    pid, seen = os.getpid(), set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        if pid in wanted:
            try:
                if lifecycle.process_identity(pid) == wanted[pid]:
                    return True
            except ProcessLookupError:
                return False
            except (OSError, ValueError) as exc:
                raise TreeUnknown(f"process {pid} could not be identified: {exc}") from exc
        pid = _parent(pid)
    return False


def holds(launch: dict) -> bool | None:
    """Whether this launch's tree holds the current process; None when its named job does not exist."""
    if os.name == "nt":
        return _windows_in_job(launch["dispatch_id"])
    return _posix_below([launch.get("recipient_process"), launch.get("launcher_process")])


def stretch_holding(store: Path) -> Holding:
    """The one live stretch launch whose tree holds this process, ``none``, or ``unknown``.

    With no live stretch launch recorded, the store read is the whole check. A launch whose named
    job does not exist does not hold the process; ``unknown`` is for a check that errors.
    """
    unknown = None
    for launch in live_launches(Path(store)):
        try:
            held = holds(launch)
        except TreeUnknown as exc:
            unknown = Holding("unknown", launch, str(exc))
            continue
        if held:
            return Holding("held", launch)
    return unknown or Holding("none")


class LaunchRefused(ValueError):
    """A seat or record launch that cannot say truthfully who launched it, refused before any bundle."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


def attribution(store: Path, *, dispatch: str | None = None, session: str | None = None,
                origin: str | None = None) -> dict[str, object]:
    """The request-record fields that say who started a seat, read from the tree rather than the flags.

    Inside a live stretch launch's tree the seat is the builder's whatever its variable says, and a
    flag that disagrees with the holding launch is ignored and noted. Outside every tree it is the
    holder's, as before, and the entrance's builder flags are refused there. ``dispatch_origin``
    is declared and proves nothing; recomposing the dispatch decides whether it was the entrance's.
    """
    holding = stretch_holding(store)
    variable = os.environ.get(DISPATCH_VARIABLE)
    flagged = dispatch is not None or session is not None or origin is not None
    if holding.state == "unknown":
        # The entrance's flags claim a builder's check; with no tree to vouch for it, it would read as the holder's.
        if variable or flagged:
            raise LaunchRefused("launch-tree-unknown", f"the tree check of the stretch launch whose "
                                f"request is {holding.launch.get('request')} could not be made: {holding.reason}")
        return {"stretch_tree_check": holding.record()}
    if holding.state == "none":
        if variable:
            raise LaunchRefused("builder-identity-unproved", f"{DISPATCH_VARIABLE} names {variable}, but "
                                "no live stretch launch's tree holds this process")
        if flagged:
            raise LaunchRefused("launched-by-outside-a-stretch", "the entrance's builder flags were given "
                                "outside every stretch launch's tree")
        return {}
    launch = holding.launch
    present = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if present and present != launch.get("session_id"):
        # One session rule everywhere: a present session that is not the launch's is refused, as the
        # entrance refuses it; `declared` is for an absent session variable only.
        raise LaunchRefused("builder-identity-unproved", f"this session {present} is not the launch's "
                            f"session {launch.get('session_id')}")
    fields: dict[str, object] = {
        "launched_by": {"role": "builder", "dispatch_id": launch["dispatch_id"],
                        "session_id": launch.get("session_id"),
                        "identity": "proved" if present else "declared"},
        "dispatch_origin": "entrance" if origin == "entrance" else "caller"}
    ignored = {name: value for name, value in (("dispatch", dispatch), ("session", session))
               if value is not None and value != {"dispatch": launch["dispatch_id"],
                                                  "session": launch.get("session_id")}[name]}
    if ignored:
        fields["launched_by_ignored"] = ignored
    return fields

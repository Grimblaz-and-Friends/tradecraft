#!/usr/bin/env python3
"""The holder pane's logic: binding, readings, the read floor and the reminder.

Lab-only tooling (#888). The `holder-pane` mod's hooks module is a shim: it
runs this file as `python holder_pane.py <subcommand>` with one JSON object
on standard input and reads one JSON object from standard output. Everything
the pane shows, every file it writes and the one GitHub-reading subprocess it
starts are decided here, so the behaviour is testable with pytest and without
Claude Code.

An unbound session -- one that has run no `run <stage>` or `adopt` for a
change and has no single matching registry row -- gets nothing: every
subcommand returns at once having read at most its own binding file (and, for
`recover`, the implementation registry).

State lives under `~/.tradecraft/status/`: one documented status file per
change, and private state under `.pane/` (bindings, per-session state, the
per-change read floor and lock, the cached entrance reading and an index of
dispatch bundles). The entrance (`lib/work.py`, read-only form) is the only
subprocess, and the only thing that reaches GitHub.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

STAGES = (
    "artifact", "cold-seat", "build", "floor", "use", "review-disposition",
    "proof", "ready-reviewers", "release-report", "catch-up",
)
DISPATCHING = frozenset({"artifact", "cold-seat", "build", "floor", "use",
                         "review-disposition"})
# Stages that launch nobody: each publishes, merges or reports for itself, so the
# call's own report is the reading.
HOLDER_ONLY = frozenset({"proof", "ready-reviewers", "release-report", "catch-up"})
SEAT_STAGES = frozenset({"cold-seat", "use"})

# What a returned stage leaves, and for whom (artifact section 4's table).
RETURN_TABLE: dict[str, tuple[str, str]] = {
    "artifact": ("holder", "post the draft artifact, then run cold-seat"),
    "cold-seat": ("holder", "post the settlement or revise the draft"),
    "build": ("holder", "read the builder's return and record it"),
    "floor": ("holder", "read the builder's return and record it"),
    "review-disposition": ("holder", "read the builder's return and record it"),
    "catch-up": ("holder", "run floor, then proof, at the new head"),
    "use": ("holder", "write the session note and post the use marker"),
    "proof": ("holder", "read the entrance's next step (the proof is published)"),
    "ready-reviewers": ("reviewer", "connected reviewers run"),
    "release-report": ("holder", "post the release report"),
}

# The read floor (row 3): one entrance read per change per 35 minutes.
FLOOR_SECONDS = 2100
ENTRANCE_TIMEOUT_SECONDS = 540
GH_TIMEOUT_SECONDS = 60
STALE_LOCK_SECONDS = 660
PENDING_RECORD_SECONDS = 600
BUNDLE_MATCH_SLACK_SECONDS = 5

OWNER_DECISIONS = frozenset({"product-incident-required", "affirmation-invalid"})
OWNER_REASONS = frozenset({"practice-work-has-no-product-incident",
                           "review-risk-lane-missing-or-mismatched"})
CI_REASON_PREFIXES = ("latest-check-run-", "declared-floor-")
GATE_REASON_MARKERS = ("gate-evaluation", "required-gate-")
REVIEWER_REASONS = frozenset({"required-connected-reviewer-has-not-run"})
HOLDER_WAITING_REASONS = frozenset({"base-synchronization-unavailable"})
# Decisions that stop the flow under a stage of their own, matched by stage ahead
# of the status-level rules. A `build` stage is also a runnable stage, so its two
# are matched with their reason.
STAGE_PARTIES: dict[str, tuple[str, str]] = {
    "convergence": ("owner", "affirm the brief"),
    "artifact-source": ("holder", "repair the artifact source"),
    "implementation-scope": ("holder", "run the entrance with --instalment"),
    "merged-pull-request": ("holder", "decide what the issue still owes: close it, build again, "
                                      "or run a use owed after the merge"),
}
STAGE_REASON_PARTIES: dict[tuple[str, str], tuple[str, str]] = {
    ("build", "build-budget-holder-owned"): ("holder", "resolve the build budget"),
    ("build", "fresh-build-requires-released-registration"):
        ("holder", "run release for this work before a fresh build"),
    ("floor", "floor-command-missing"): ("holder", "rerun floor with --floor-command"),
}
# Waiting reasons built from a prefix in the entrance: each asks the holder for something.
HOLDER_WAITING_PREFIXES: dict[str, str] = {
    "reach-": "read the owed reach coverage",
    "resume-session-missing-for-": "supply the dispatch bundle or builder-session marker",
    "holder-session-id-required-for-": "pass --holder-session-id",
    "resume-session-identifies-holder-for-": "pass the builder's session, not the holder's",
}
# Only a terminal issue or pull request stops the pane; a merge with the issue open
# is holder-owned and still owes a decision.
FINAL_STAGES = frozenset({"terminal"})

STEWARD = "steward"
RENAMING_SOURCES = frozenset({"auto", "tool"})

STATUS_FIELDS = (
    "schema_version", "repository", "issue", "session_name", "session_id",
    "stage", "waiting_on", "next_step", "gate", "floor", "status", "source",
    "read_at",
)

WORK_PY = re.compile(r"[\\/]lib[\\/]work\.py$")
GH_POST = re.compile(r"(?:^|[\s;&|(])gh\s+(?P<rest>.*)")
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class Ctx:
    """What the core reads from the machine: the clock, home, and the runner."""

    def __init__(self, *, home: Path | None = None, now: float | None = None,
                 runner: Callable[..., Any] | None = None,
                 environ: dict[str, str] | None = None,
                 liveness: Callable[[Any], str] | None = None) -> None:
        self.home = home if home is not None else Path.home()
        self.liveness = liveness if liveness is not None else process_liveness
        self._now = now
        self.runner = runner if runner is not None else subprocess.run
        self.environ = environ if environ is not None else dict(os.environ)

    def now(self) -> float:
        return self._now if self._now is not None else time.time()

    @property
    def tradecraft(self) -> Path:
        return self.home / ".tradecraft"

    @property
    def status_dir(self) -> Path:
        return self.tradecraft / "status"

    @property
    def private(self) -> Path:
        return self.status_dir / ".pane"


# --- small file helpers ----------------------------------------------------

def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, value: Any) -> bool:
    """Write atomically, and only when the bytes change. Returns whether it wrote."""
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        if path.read_bytes() == data:
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    temp.write_bytes(data)
    os.replace(temp, path)
    return True


def _remove(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def change_key(repository: str, issue: int) -> str:
    owner, _, repo = repository.partition("/")
    return f"{owner}__{repo}__{int(issue)}"


def _safe(session_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", session_id)[:128] or "_"


def binding_path(ctx: Ctx, session_id: str) -> Path:
    return ctx.private / "bindings" / f"{_safe(session_id)}.json"


def session_path(ctx: Ctx, session_id: str) -> Path:
    return ctx.private / "sessions" / f"{_safe(session_id)}.json"


def change_path(ctx: Ctx, key: str) -> Path:
    return ctx.private / "changes" / f"{key}.json"


def lock_path(ctx: Ctx, key: str) -> Path:
    return ctx.private / "changes" / f"{key}.lock"


def status_path(ctx: Ctx, key: str) -> Path:
    return ctx.status_dir / f"{key}.json"


def iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_hhmm(epoch: float) -> str:
    return time.strftime("%H:%M", time.localtime(epoch))


def _epoch(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


# --- reading a command -------------------------------------------------------

def _tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=False)
    except ValueError:
        return command.split()


def _unquote(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def _option(tokens: list[str], name: str) -> str | None:
    for index, token in enumerate(tokens):
        token = _unquote(token)
        if token == name and index + 1 < len(tokens):
            return _unquote(tokens[index + 1])
        if token.startswith(name + "="):
            return token[len(name) + 1:]
    return None


def parse_entrance_call(command: str) -> dict[str, Any] | None:
    """Recognise `run <STAGE>` or `adopt` with --repo and --issue, in any wrapper.

    Matched on the arguments, not the script name, so a detached launcher
    (`python launch_stage.py label -- run build --repo R --issue N ...`)
    matches too. A read-only entrance call (no run/adopt) never matches.
    """
    tokens = [_unquote(token) for token in _tokens(command)]
    verb = None
    for index, token in enumerate(tokens):
        if token == "adopt":
            verb = ("adopt", None)
            break
        if token == "run" and index + 1 < len(tokens) and tokens[index + 1] in STAGES:
            verb = ("run", tokens[index + 1])
            break
    if verb is None:
        return None
    repository = _option(tokens, "--repo")
    issue = _option(tokens, "--issue")
    if not repository or "/" not in repository or not issue or not issue.isdigit():
        return None
    entrance = next((token for token in tokens if WORK_PY.search(token.replace('"', ""))), None)
    return {
        "verb": verb[0], "stage": verb[1], "repository": repository,
        "issue": int(issue), "root": _option(tokens, "--root"), "entrance": entrance,
        "instalment": _option(tokens, "--instalment"),
    }


def newest_cached_entrance(ctx: Ctx) -> str | None:
    base = ctx.home / ".claude" / "plugins" / "cache" / "tradecraft" / "tradecraft"
    try:
        versions = [entry for entry in base.iterdir() if SEMVER.match(entry.name)]
    except OSError:
        return None
    versions.sort(key=lambda entry: tuple(int(part) for part in entry.name.split(".")))
    for entry in reversed(versions):
        candidate = entry / "lib" / "work.py"
        if candidate.is_file():
            return str(candidate)
    return None


def last_json_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    found = None
    index = 0
    while True:
        start = text.find("{", index)
        if start < 0:
            return found
        try:
            value, end = decoder.raw_decode(text, start)
        except ValueError:
            index = start + 1
            continue
        if isinstance(value, dict):
            found = value
        index = end


def _is_decision(value: Any) -> bool:
    """An entrance report: it names a stage and a status (a reason is optional)."""
    return isinstance(value, dict) and all(key in value for key in ("stage", "status"))


# --- classifying a decision --------------------------------------------------

def _holder_step(stage: str, status: str) -> str:
    if status == "runnable":
        return f"run {stage}"
    if stage in STAGES:
        return f"run {stage}"
    return f"act on {stage}"


def classify(decision: dict[str, Any]) -> dict[str, str]:
    """Who an entrance decision waits on, and the next step (section 4's rules, in order)."""
    stage = str(decision.get("stage") or "")
    status = str(decision.get("status") or "")
    reason = str(decision.get("reason") or "")
    if stage in OWNER_DECISIONS or reason in OWNER_REASONS:
        return {"waiting_on": "owner", "next_step": f"owner: {reason or stage}"}
    party = STAGE_REASON_PARTIES.get((stage, reason)) or STAGE_PARTIES.get(stage)
    if party is not None:
        return {"waiting_on": party[0], "next_step": party[1]}
    if status == "waiting":
        if reason.startswith(CI_REASON_PREFIXES):
            return {"waiting_on": "ci", "next_step": f"wait for CI ({reason})"}
        if reason in REVIEWER_REASONS or any(marker in reason for marker in GATE_REASON_MARKERS):
            return {"waiting_on": "reviewer", "next_step": f"wait for review ({reason})"}
        if reason in HOLDER_WAITING_REASONS:
            return {"waiting_on": "holder", "next_step": f"resolve: {reason}"}
        for prefix, step in HOLDER_WAITING_PREFIXES.items():
            if reason.startswith(prefix):
                return {"waiting_on": "holder", "next_step": step}
    if status in ("runnable", "holder-owned"):
        if stage in FINAL_STAGES:
            return {"waiting_on": "none", "next_step": "none"}
        return {"waiting_on": "holder", "next_step": _holder_step(stage, status)}
    if status == "refused":
        return {"waiting_on": "holder", "next_step": f"resolve: {reason}"}
    if status == "terminal":
        return {"waiting_on": "none", "next_step": "none"}
    return {"waiting_on": "unknown", "next_step": reason or stage or "unknown"}


def _pull_request(decision: dict[str, Any]) -> int | None:
    for holder in (decision, decision.get("synchronization"), decision.get("floor")):
        if isinstance(holder, dict) and isinstance(holder.get("pull_request"), int):
            return int(holder["pull_request"])
    return None


def _head(decision: dict[str, Any]) -> str | None:
    for holder in (decision.get("required_gate"), decision.get("floor"),
                   decision.get("synchronization")):
        if isinstance(holder, dict):
            for key in ("head", "head_sha"):
                if isinstance(holder.get(key), str) and holder[key]:
                    return holder[key]
    return None


def gate_text(decision: dict[str, Any], pr: dict[str, Any] | None = None) -> str:
    gate = decision.get("required_gate")
    if isinstance(gate, dict) and gate.get("verdict"):
        return str(gate["verdict"])
    reason = str(decision.get("reason") or "")
    if decision.get("stage") == "release-report" and reason.startswith("all-evidence-complete"):
        return "green"
    if any(marker in reason for marker in GATE_REASON_MARKERS):
        return reason
    if _pull_request(decision) is None and _pr_number(pr) is None:
        return "not reached"
    return "-"


def floor_value(decision: dict[str, Any]) -> dict[str, Any]:
    floor = decision.get("floor")
    if not isinstance(floor, dict):
        return {"outcome": None, "satisfied": None}
    satisfied = floor.get("satisfied")
    return {"outcome": floor.get("outcome"),
            "satisfied": satisfied if isinstance(satisfied, bool) else None}


def _stalled_by_entrance(decision: dict[str, Any] | None) -> bool:
    if not isinstance(decision, dict):
        return False
    floor = decision.get("floor")
    return decision.get("stage") == "floor-stalled" or (
        isinstance(floor, dict) and floor.get("outcome") == "stalled")


def reading_from_decision(decision: dict[str, Any], source: str, now: float,
                          pr: dict[str, Any] | None = None) -> dict[str, Any]:
    reading = {
        "stage": str(decision.get("stage") or ""),
        "status": str(decision.get("status") or ""),
        "reason": str(decision.get("reason") or ""),
        "gate": gate_text(decision, pr),
        "floor": floor_value(decision),
        "source": source,
        "read_at": now,
        "pull_request": _pull_request(decision) or _pr_number(pr),
        "head": _head(decision),
        "entrance_stalled": _stalled_by_entrance(decision),
        "dispatch_id": None,
    }
    reading.update(classify(decision))
    return reading


def reading_from_return(stage: str, source_decision: dict[str, Any] | None, now: float,
                        dispatch_id: str | None = None,
                        pr: dict[str, Any] | None = None) -> dict[str, Any]:
    waiting_on, step = RETURN_TABLE[stage]
    base = source_decision if isinstance(source_decision, dict) else {}
    return {
        "stage": stage, "status": "returned", "reason": str(base.get("reason") or ""),
        "gate": gate_text(base, pr) if base else "-", "floor": floor_value(base),
        "source": "stage-return", "read_at": now,
        "pull_request": _pull_request(base) or _pr_number(pr),
        "head": _head(base), "entrance_stalled": _stalled_by_entrance(base),
        "dispatch_id": dispatch_id, "waiting_on": waiting_on, "next_step": step,
    }


def _pr_number(pr: Any) -> int | None:
    return int(pr["number"]) if isinstance(pr, dict) and isinstance(pr.get("number"), int) else None


def no_launch_reading(stage: str, report: dict[str, Any] | None, output: str, now: float,
                      pr: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """A stage that launches nobody: its own report is the reading.

    A report carrying the entrance's `next` decision (catch-up) reads as that
    decision; a report for another stage, or one refused, waiting or terminal,
    reads through the classifier; the stage's own success reads through the
    return table. No output at all keeps the previous reading.
    """
    if isinstance(report, dict) and _is_decision(report.get("next")):
        return reading_from_decision(report["next"], "stage-return", now, pr)
    if _is_decision(report) and (report["stage"] != stage or report["status"] in (
            "refused", "waiting", "terminal")):
        return reading_from_decision(report, "stage-return", now, pr)
    if report is not None or output.strip():
        return reading_from_return(stage, report, now, pr=pr)
    return None


# --- state -------------------------------------------------------------------

def load_binding(ctx: Ctx, session_id: str) -> dict[str, Any] | None:
    value = _read_json(binding_path(ctx, session_id))
    return value if isinstance(value, dict) and value.get("repository") else None


def load_session(ctx: Ctx, session_id: str) -> dict[str, Any]:
    value = _read_json(session_path(ctx, session_id))
    return value if isinstance(value, dict) else {}


def save_session(ctx: Ctx, session_id: str, state: dict[str, Any]) -> None:
    _write_json(session_path(ctx, session_id), state)


def load_change(ctx: Ctx, key: str) -> dict[str, Any]:
    value = _read_json(change_path(ctx, key))
    return value if isinstance(value, dict) else {}


def unbind(ctx: Ctx, session_id: str) -> None:
    _remove(binding_path(ctx, session_id))


def _desktop_record_dirs(ctx: Ctx) -> list[Path]:
    dirs = []
    appdata = ctx.environ.get("APPDATA")
    if appdata:
        dirs.append(Path(appdata) / "Claude" / "claude-code-sessions")
    local = ctx.environ.get("LOCALAPPDATA")
    if local:
        packages = Path(local) / "Packages"
        try:
            for entry in packages.iterdir():
                if entry.name.startswith("Claude_"):
                    dirs.append(entry / "LocalCache" / "Roaming" / "Claude" / "claude-code-sessions")
        except OSError:
            pass
    return dirs


def desktop_record(ctx: Ctx, session_id: str, state: dict[str, Any]) -> dict[str, Any] | None:
    """The desktop's own record of this session, matched by `cliSessionId`. Read only."""
    cached = state.get("desktop_record")
    if isinstance(cached, str):
        record = _read_json(Path(cached))
        if isinstance(record, dict) and record.get("cliSessionId") == session_id:
            return record
    for base in _desktop_record_dirs(ctx):
        for path in sorted(base.glob("*/*/local_*.json")):
            record = _read_json(path)
            if isinstance(record, dict) and record.get("cliSessionId") == session_id:
                state["desktop_record"] = str(path)
                return record
    return None


def title_info(ctx: Ctx, session_id: str, probe: Any, state: dict[str, Any]) -> dict[str, Any]:
    """Resolve the shim's title read (section 5).

    `probe` is what the shim saw: `{"decision": allow|ask|deny|absent, "text": ...}`.
    Anything but `allow` is unreadable, and then no record is consulted.
    """
    unreadable = {"readable": False, "title": None, "source": None}
    if not isinstance(probe, dict) or probe.get("decision") != "allow":
        return unreadable
    answered = last_json_object(str(probe.get("text") or "")) or {}
    title = answered.get("title") if isinstance(answered.get("title"), str) else None
    source = answered.get("titleSource") if isinstance(answered.get("titleSource"), str) else None
    record = desktop_record(ctx, session_id, state)
    if record is not None:
        if source is None and isinstance(record.get("titleSource"), str):
            source = record["titleSource"]
        if not title and isinstance(record.get("title"), str):
            title = record["title"]
    if not title:
        return unreadable
    return {"readable": True, "title": title, "source": source}


def is_steward(title: Any) -> bool:
    return isinstance(title, str) and title.strip().casefold() == STEWARD


# --- dispatch bundles --------------------------------------------------------

def _bundle_index(ctx: Ctx) -> dict[str, Any]:
    """Every bundle's request, parsed once and cached by request path."""
    index_path = ctx.private / "bundle-index.json"
    index = _read_json(index_path)
    if not isinstance(index, dict):
        index = {}
    root = ctx.tradecraft / "dispatches"
    changed = False
    try:
        directories = list(root.iterdir())
    except OSError:
        directories = []
    seen = set()
    for directory in directories:
        try:
            requests = list(directory.glob("*.request.json"))
        except OSError:
            continue
        for request_path in requests:
            key = str(request_path)
            seen.add(key)
            if key in index:
                continue
            request = _read_json(request_path)
            if not isinstance(request, dict):
                continue
            deadline = request.get("caller_limit_seconds")
            if not isinstance(deadline, (int, float)):
                deadline = request.get("stage_ceiling_seconds")
            index[key] = {
                "work": request.get("work"), "stage": request.get("stage"),
                "dispatch_id": request.get("dispatch_id"),
                "launched_at": _epoch(request.get("launched_at")),
                "deadline": float(deadline) if isinstance(deadline, (int, float)) else None,
            }
            changed = True
    for key in [key for key in index if key not in seen]:
        del index[key]
        changed = True
    if changed:
        _write_json(index_path, index)
    return index


def bundles_for(ctx: Ctx, work: str) -> list[dict[str, Any]]:
    found = []
    for request_path, entry in _bundle_index(ctx).items():
        if entry.get("work") != work or entry.get("launched_at") is None:
            continue
        run_path = Path(request_path[: -len(".request.json")] + ".run.json")
        run = _read_json(run_path)
        run = run if isinstance(run, dict) else {}
        logs = []
        for attempt in run.get("attempts") or []:
            if isinstance(attempt, dict):
                logs.extend(str(attempt[name]) for name in ("stdout", "stderr")
                            if isinstance(attempt.get(name), str))
        try:
            finished = run_path.stat().st_mtime
        except OSError:
            finished = None
        found.append({**entry, "lifecycle": run.get("lifecycle"), "logs": logs,
                      "processes": [run[name] for name in ("launcher_process",
                                                           "recipient_process")
                                    if isinstance(run.get(name), dict)],
                      "dispatch_id": run.get("dispatch_id") or entry.get("dispatch_id"),
                      "run_mtime": finished})
    found.sort(key=lambda bundle: bundle["launched_at"])
    return found


def process_liveness(identity: Any) -> str:
    """`active`, `stopped` or `unresolved`, by pid and birth, as lib/run_lifecycle.py does."""
    if not isinstance(identity, dict) or identity.get("host") != socket.gethostname():
        return "unresolved"
    pid, birth = identity.get("pid"), identity.get("birth")
    if not isinstance(pid, int) or not birth:
        return "unresolved"
    try:
        current = _process_birth(pid)
    except ProcessLookupError:
        return "stopped"
    except (OSError, ValueError, IndexError):
        return "unresolved"
    return "active" if current == str(birth) else "stopped"


def _process_birth(pid: int) -> str:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE,
                                           *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        handle = kernel.OpenProcess(0x101000, False, pid)
        if not handle:
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
            return str(values[0].dwHighDateTime << 32 | values[0].dwLowDateTime)
        finally:
            kernel.CloseHandle(handle)
    try:
        fields = Path(f"/proc/{pid}/stat").read_bytes().rsplit(b")", 1)[1].split()
    except FileNotFoundError:
        if Path("/proc").is_dir():
            raise ProcessLookupError(pid) from None
        raise OSError("no /proc") from None
    if fields[0] == b"Z":
        raise ProcessLookupError(pid)
    return fields[19].decode("ascii")


def live_running(ctx: Ctx, bundles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bundles still running: `running` on record, not superseded, and not proven dead.

    A killed launcher leaves `lifecycle: running` behind. Such a record is not
    running once a newer bundle of the same stage has finished, or once every
    process it names is proven gone; `unresolved` keeps it, as recovery does.
    """
    live = []
    for index, bundle in enumerate(bundles):
        if bundle.get("lifecycle") != "running":
            continue
        later = bundles[index + 1:]
        if any(other.get("stage") == bundle.get("stage") and other.get("lifecycle") != "running"
               for other in later):
            continue
        processes = bundle.get("processes") or []
        if processes and all(ctx.liveness(identity) == "stopped" for identity in processes):
            continue
        live.append(bundle)
    return live


def running_overlay(bundle: dict[str, Any], now: float) -> dict[str, Any]:
    launched = float(bundle["launched_at"])
    elapsed = max(0.0, now - launched)
    newest = None
    for log in bundle.get("logs") or []:
        try:
            mtime = Path(log).stat().st_mtime
        except OSError:
            continue
        newest = mtime if newest is None else max(newest, mtime)
    quiet = max(0.0, now - (newest if newest is not None else launched))
    deadline = bundle.get("deadline")
    return {
        "stage": bundle.get("stage"), "elapsed": elapsed, "deadline": deadline, "quiet": quiet,
        "stalled": bool(deadline is not None and elapsed > float(deadline)),
        "dispatch_id": bundle.get("dispatch_id"),
    }


# --- binding -----------------------------------------------------------------

def bind(ctx: Ctx, session_id: str, binding: dict[str, Any], title: dict[str, Any]) -> bool:
    """Bind unless the live title is `Steward` (row 2). Returns whether bound."""
    if title.get("readable") and is_steward(title.get("title")):
        unbind(ctx, session_id)
        return False
    previous = load_binding(ctx, session_id)
    state = load_session(ctx, session_id)
    if previous is None or (previous.get("repository"), previous.get("issue")) != (
            binding["repository"], binding["issue"]):
        # A new change: nothing from the previous one carries over but the rename record.
        state = {key: state[key] for key in ("desktop_record", "last_label", "last_title_set",
                                              "rename_disabled") if key in state}
    entrance = binding.get("entrance") or newest_cached_entrance(ctx)
    record = {
        "repository": binding["repository"], "issue": int(binding["issue"]),
        "root": binding.get("root"), "entrance": entrance, "session_id": session_id,
        "instalment": binding.get("instalment"),
        "bound_at": binding.get("bound_at") or ctx.now(),
    }
    _write_json(binding_path(ctx, session_id), record)
    save_session(ctx, session_id, state)
    return True


def recover(ctx: Ctx, session_id: str, root: str) -> dict[str, Any] | None:
    """Restart recovery: this session's binding file, else exactly one registry row."""
    existing = load_binding(ctx, session_id)
    if existing is not None:
        return existing
    registry = _read_json(ctx.tradecraft / "implementation-worktrees.json")
    rows = registry.get("worktrees") if isinstance(registry, dict) else None
    if not isinstance(rows, list) or not root:
        return None
    try:
        wanted = os.path.normcase(str(Path(root).resolve()))
    except OSError:
        return None
    matches = []
    for row in rows:
        if not isinstance(row, dict) or row.get("active") is not True:
            continue
        holder_root = row.get("holder_root")
        if not isinstance(holder_root, str):
            continue
        try:
            resolved = os.path.normcase(str(Path(holder_root).resolve()))
        except OSError:
            continue
        if resolved == wanted and isinstance(row.get("repository"), str) and isinstance(
                row.get("issue"), int):
            matches.append(row)
    if len(matches) != 1:
        return None
    row = matches[0]
    instalment = row.get("instalment") if isinstance(row.get("instalment"), str) else None
    return {"repository": row["repository"], "issue": row["issue"],
            "root": row["holder_root"], "entrance": newest_cached_entrance(ctx),
            "instalment": instalment}


# --- observing the holder's own calls ----------------------------------------

def _posts_to_pull_request(command: str, pull_request: int | None) -> int | None:
    """The PR this command posts to, when it is `pull_request`; any named PR when that is unknown."""
    for match in GH_POST.finditer(command):
        rest = match.group("rest")
        tokens = [_unquote(token) for token in _tokens(rest)]
        if len(tokens) >= 3 and tokens[0] == "pr" and tokens[1] in ("comment", "edit"):
            named = re.search(r"(?:^#?|/pull/)(\d+)$", tokens[2])
            if named and (pull_request is None or int(named.group(1)) == pull_request):
                return int(named.group(1))
        if tokens and tokens[0] == "api":
            target = re.search(r"issues/(\d+)/comments", rest)
            post = re.search(r"(?:-X|--method)[\s=]+POST", rest, re.IGNORECASE) or re.search(
                r"(?:^|\s)(?:-f|-F|--field|--raw-field|--input)(?:\s|=)", rest)
            if target and post and pull_request is not None and int(
                    target.group(1)) == pull_request:
                return pull_request
    return None


def observe(ctx: Ctx, payload: dict[str, Any]) -> dict[str, Any]:
    """The holder's own shell call ended: bind, and read any stage return."""
    session_id = str(payload["session_id"])
    command = str(payload.get("command") or "")
    output = str(payload.get("output") or "")
    started = float(payload.get("started_at") or ctx.now())
    ended = float(payload.get("ended_at") or ctx.now())
    call = parse_entrance_call(command)
    if call is None and load_binding(ctx, session_id) is None:
        return {"bound": False}
    state = load_session(ctx, session_id)
    title = title_info(ctx, session_id, payload.get("title"), state)
    if call is not None:
        if not bind(ctx, session_id, call, title):
            return {"bound": False}
    binding = load_binding(ctx, session_id)
    if binding is None:
        return {"bound": False}
    if is_steward(title.get("title")):
        unbind(ctx, session_id)
        return {"bound": False}
    state = load_session(ctx, session_id)
    pr = load_change(ctx, change_key(binding["repository"], binding["issue"])).get("pull_request")
    same_change = call is not None and (call["repository"], call["issue"]) == (
        binding["repository"], binding["issue"])
    if same_change and call["verb"] == "run":
        stage = call["stage"]
        if stage in DISPATCHING:
            _observe_launch(ctx, binding, state, stage, output, started, ended, pr)
        else:
            reading = no_launch_reading(stage, last_json_object(output), output, ended, pr)
            if reading is not None:
                state["reading"] = reading
            state.pop("pending", None)
            state.pop("tracked", None)
            state.pop("release_report_posted", None)
    reading = state.get("reading")
    if call is None and isinstance(reading, dict) and reading.get("stage") == "release-report" \
            and reading.get("source") == "stage-return":
        known = reading.get("pull_request") if isinstance(reading.get("pull_request"), int) \
            else _pr_number(pr)
        posted = _posts_to_pull_request(command, known)
        if posted is not None:
            state["release_report_posted"] = {"head": reading.get("head"), "pull_request": posted}
    save_session(ctx, session_id, state)
    return {"bound": True, "binding": binding}


def _observe_launch(ctx: Ctx, binding: dict[str, Any], state: dict[str, Any], stage: str,
                    output: str, started: float, ended: float,
                    pr: dict[str, Any] | None = None) -> None:
    state.pop("tracked", None)
    state.pop("release_report_posted", None)
    work = f"{binding['repository']}#{binding['issue']}"
    match = _matching_bundle(bundles_for(ctx, work), stage, started)
    if match is not None:
        state.pop("pending", None)
        if match.get("lifecycle") == "running":
            state["tracked"] = match.get("dispatch_id")
        else:
            state["reading"] = reading_from_return(stage, None, ended,
                                                   match.get("dispatch_id"), pr)
        return
    decision = last_json_object(output)
    if _is_decision(decision) and (decision.get("dispatch") is False
                                   or decision["status"] != "runnable"):
        # The entrance launched nobody and no bundle will come: its report is the reading,
        # whatever its status (a holder-owned budget or scope refusal included).
        state.pop("pending", None)
        state["reading"] = reading_from_decision(decision, "stage-return", ended, pr)
        return
    state["pending"] = {"stage": stage, "started_at": started, "ended_at": ended}


def _matching_bundle(bundles: list[dict[str, Any]], stage: str, started: float):
    candidates = [bundle for bundle in bundles if bundle.get("stage") == stage
                  and float(bundle["launched_at"]) >= started - BUNDLE_MATCH_SLACK_SECONDS]
    return candidates[-1] if candidates else None


# --- the view ------------------------------------------------------------------

def _newer(first: dict[str, Any] | None, second: dict[str, Any] | None):
    if not isinstance(first, dict):
        return second if isinstance(second, dict) else None
    if not isinstance(second, dict):
        return first
    return first if float(first.get("read_at") or 0) >= float(second.get("read_at") or 0) else second


def _label(view: dict[str, Any]) -> str:
    stage = view["stage"] or "unknown"
    running = view.get("running")
    if view.get("final"):
        return view["final"]
    if running is not None:
        if stage in SEAT_STAGES:
            return f"{stage} seat running"
        return f"{stage} stalled" if running.get("stalled") else f"{stage} running"
    waiting = view["waiting_on"]
    if waiting == "owner":
        return "waiting on you"
    if waiting == "holder":
        return f"holder: {stage}"
    if waiting == "builder":
        return f"{stage} seat running" if stage in SEAT_STAGES else f"{stage} running"
    if waiting == "ci":
        return "waiting on CI"
    if waiting == "reviewer":
        return "waiting on review"
    return stage


def compute_view(ctx: Ctx, binding: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Fold the readings, bundles and pending launch into what is shown. Mutates `state`."""
    now = ctx.now()
    key = change_key(binding["repository"], binding["issue"])
    work = f"{binding['repository']}#{binding['issue']}"
    change = load_change(ctx, key)
    bundles = bundles_for(ctx, work)
    pending = state.get("pending")
    if isinstance(pending, dict):
        match = _matching_bundle(bundles, pending["stage"], float(pending["started_at"]))
        if match is not None:
            state.pop("pending", None)
            pending = None
            if match.get("lifecycle") == "running":
                state["tracked"] = match.get("dispatch_id")
            else:
                state["reading"] = reading_from_return(
                    match["stage"], None, now, match.get("dispatch_id"))
    tracked = state.get("tracked")
    if tracked:
        bundle = next((item for item in bundles if item.get("dispatch_id") == tracked), None)
        if bundle is not None and bundle.get("lifecycle") != "running":
            state.pop("tracked", None)
            if bundle.get("stage") in RETURN_TABLE:
                state["reading"] = reading_from_return(
                    bundle["stage"], None, now, bundle.get("dispatch_id"))
    reading = _newer(state.get("reading"), change.get("reading"))
    view: dict[str, Any] = {
        "repository": binding["repository"], "issue": int(binding["issue"]),
        "stage": "", "status": "", "waiting_on": "unknown", "next_step": "no reading yet",
        "gate": "-", "floor": {"outcome": None, "satisfied": None}, "source": None,
        "read_at": None, "dispatch_id": None, "head": None, "running": None,
        "record_pending": False, "final": None, "read_failed_at": change.get("read_failed_at"),
    }
    if isinstance(reading, dict):
        for field in ("stage", "status", "waiting_on", "next_step", "gate", "floor", "source",
                      "read_at", "dispatch_id", "head"):
            view[field] = reading.get(field, view[field])
        if reading.get("stage") in FINAL_STAGES or reading.get("status") == "terminal":
            # Merged or closed is the pull request's own state, never the reason text.
            pr = change.get("pull_request")
            view["final"] = "merged" if isinstance(pr, dict) and pr.get("merged") else "closed"
            view["waiting_on"] = "none"
        posted = state.get("release_report_posted")
        if isinstance(posted, dict) and reading.get("stage") == "release-report" and (
                posted.get("head") in (None, reading.get("head"))):
            view["waiting_on"] = "owner"
            view["next_step"] = "merge"
    running = live_running(ctx, bundles)
    if view["final"] is None and isinstance(pending, dict):
        stage = pending["stage"]
        view.update({"stage": stage, "status": "launched", "source": "stage-return",
                     "read_at": float(pending["ended_at"]), "dispatch_id": None})
        if now - float(pending["ended_at"]) <= PENDING_RECORD_SECONDS:
            view.update({"waiting_on": "reviewer" if stage in SEAT_STAGES else "builder",
                         "next_step": f"{stage} launched, record pending",
                         "record_pending": True})
        else:
            view.update({"waiting_on": "holder",
                         "next_step": f"check the {stage} run (no dispatch record)",
                         "dispatch_id": f"pending@{int(float(pending['started_at']))}"})
    elif view["final"] is None and running:
        overlay = running_overlay(running[-1], now)
        if isinstance(reading, dict) and reading.get("entrance_stalled"):
            overlay["stalled"] = True
        stage = str(overlay["stage"])
        if not view["read_at"]:
            view.update({"read_at": float(running[-1]["launched_at"]), "source": "stage-return"})
        view.update({"stage": stage, "running": overlay, "dispatch_id": overlay["dispatch_id"],
                     "status": "running",
                     "waiting_on": "reviewer" if stage in SEAT_STAGES else "builder",
                     "next_step": f"wait for the {stage} {'seat' if stage in SEAT_STAGES else 'run'}"})
    view["label"] = _label(view)
    view["read_at_local"] = local_hhmm(float(view["read_at"])) if view["read_at"] else None
    if view["read_failed_at"]:
        view["read_failed_local"] = local_hhmm(float(view["read_failed_at"]))
    return view


def _status_record(binding: dict[str, Any], view: dict[str, Any], session_id: str,
                   session_name: str | None) -> dict[str, Any]:
    return {
        "schema_version": 1, "repository": binding["repository"], "issue": int(binding["issue"]),
        "session_name": session_name, "session_id": session_id, "stage": view["stage"],
        "waiting_on": view["waiting_on"], "next_step": view["next_step"], "gate": view["gate"],
        "floor": view["floor"], "status": view["status"], "source": view["source"],
        "read_at": iso(float(view["read_at"])) if view["read_at"] else None,
    }


def _rename_decision(view: dict[str, Any], title: dict[str, Any], state: dict[str, Any]):
    label = view["label"]
    if state.get("rename_disabled"):
        return None, f"rename skipped ({state['rename_disabled']})"
    if f"{view['issue']}|{label}" == state.get("last_label"):
        return None, None
    source = title.get("source")
    if title.get("readable") and source == "user":
        state["rename_disabled"] = "owner-set title"
        return None, "rename skipped (owner-set title)"
    if not title.get("readable") or source not in RENAMING_SOURCES:
        return None, "rename skipped (title source unknown)"
    return {"label": label}, None


def tick(ctx: Ctx, payload: dict[str, Any]) -> dict[str, Any]:
    """Fold the state, write the status file, and say what to draw and whether to rename."""
    session_id = str(payload["session_id"])
    binding = load_binding(ctx, session_id)
    if binding is None:
        return {"bound": False}
    state = load_session(ctx, session_id)
    title = title_info(ctx, session_id, payload.get("title"), state)
    if title.get("readable") and is_steward(title.get("title")):
        unbind(ctx, session_id)
        save_session(ctx, session_id, state)
        return {"bound": False}
    view = compute_view(ctx, binding, state)
    rename, note = _rename_decision(view, title, state)
    if note is not None:
        state["rename_note"] = note
    elif rename is None and state.get("rename_note", "").startswith("rename skipped (title"):
        state.pop("rename_note", None)
    view["rename_note"] = state.get("rename_note")
    session_name = title["title"] if title.get("readable") else state.get("last_title_set")
    key = change_key(binding["repository"], binding["issue"])
    _write_json(status_path(ctx, key), _status_record(binding, view, session_id, session_name))
    if view["final"] is not None:
        state["stopped"] = True
    save_session(ctx, session_id, state)
    return {"bound": True, "view": view, "rename": rename, "stopped": bool(view["final"])}


def renamed(ctx: Ctx, payload: dict[str, Any]) -> dict[str, Any]:
    """Record what became of a rename the shim attempted."""
    session_id = str(payload["session_id"])
    binding = load_binding(ctx, session_id)
    if binding is None:
        return {"bound": False}
    state = load_session(ctx, session_id)
    outcome = payload.get("outcome")
    if outcome == "renamed":
        state["last_label"] = f"{binding['issue']}|{payload.get('label')}"
        state["last_title_set"] = payload.get("title")
        state.pop("rename_note", None)
        record_path = status_path(ctx, change_key(binding["repository"], binding["issue"]))
        record = _read_json(record_path)
        if isinstance(record, dict) and record.get("session_id") == session_id:
            record["session_name"] = payload.get("title")
            _write_json(record_path, record)
    elif outcome == "would-prompt":
        state["rename_disabled"] = "would prompt"
        state["rename_note"] = "rename skipped (would prompt)"
    elif outcome == "no-tool":
        state["rename_note"] = "rename skipped (no title tool)"
    else:
        state["rename_note"] = "rename skipped (rename failed)"
    save_session(ctx, session_id, state)
    return {"bound": True, "rename_note": state.get("rename_note")}


# --- the entrance read (row 3) ----------------------------------------------------

def _take_lock(ctx: Ctx, key: str) -> bool:
    path = lock_path(ctx, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps({"pid": os.getpid(), "started_at": ctx.now()}).encode("utf-8")
    for _attempt in range(2):
        try:
            handle = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            held = _read_json(path)
            started = held.get("started_at") if isinstance(held, dict) else None
            if not isinstance(started, (int, float)):
                try:
                    started = path.stat().st_mtime
                except OSError:
                    continue
            if ctx.now() - float(started) <= STALE_LOCK_SECONDS:
                return False
            _remove(path)
            continue
        with os.fdopen(handle, "wb") as stream:
            stream.write(body)
        return True
    return False


def read(ctx: Ctx, payload: dict[str, Any]) -> dict[str, Any]:
    """Run the read-only entrance for this session's change, if the floor allows."""
    session_id = str(payload["session_id"])
    binding = load_binding(ctx, session_id)
    if binding is None:
        return {"ran": False, "why": "unbound"}
    key = change_key(binding["repository"], binding["issue"])
    change = load_change(ctx, key)
    state = load_session(ctx, session_id)
    for reading in (change.get("reading"), state.get("reading")):
        if isinstance(reading, dict) and (reading.get("stage") in FINAL_STAGES
                                          or reading.get("status") == "terminal"):
            return {"ran": False, "why": "stopped"}
    started = change.get("last_read_started")
    if isinstance(started, (int, float)) and ctx.now() - float(started) < FLOOR_SECONDS:
        return {"ran": False, "why": "floor"}
    entrance = binding.get("entrance")
    if not entrance or not binding.get("root"):
        return {"ran": False, "why": "no-entrance"}
    if not _take_lock(ctx, key):
        return {"ran": False, "why": "locked"}
    try:
        change["last_read_started"] = ctx.now()
        _write_json(change_path(ctx, key), change)
        argv = [sys.executable, str(entrance), "--repo", binding["repository"],
                "--issue", str(binding["issue"]), "--root", str(binding["root"])]
        if binding.get("instalment"):
            argv += ["--instalment", str(binding["instalment"])]
        decision = None
        try:
            completed = ctx.runner(argv, stdin=subprocess.DEVNULL, capture_output=True,
                                   timeout=ENTRANCE_TIMEOUT_SECONDS)
            stdout = completed.stdout
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            decision = last_json_object(stdout or "")
        except (OSError, subprocess.SubprocessError):
            decision = None
        change = load_change(ctx, key)
        pr = lookup_pull_request(ctx, binding["repository"], int(binding["issue"]))
        if pr is not None:
            change["pull_request"] = pr
        if _is_decision(decision):
            change["reading"] = reading_from_decision(decision, "entrance", ctx.now(),
                                                      change.get("pull_request"))
            change.pop("read_failed_at", None)
        else:
            change["read_failed_at"] = ctx.now()
        _write_json(change_path(ctx, key), change)
        return {"ran": True, "ok": _is_decision(decision)}
    finally:
        _remove(lock_path(ctx, key))


def lookup_pull_request(ctx: Ctx, repository: str, issue: int) -> dict[str, Any] | None:
    """The change's implementing PR: one `gh pr list` read, inside the floored read.

    The read-only report carries no PR number, so the pane finds the PR whose
    body closes the issue: an open one first, else the newest merged, else the
    newest closed. Returns None when none is found or gh fails.
    """
    argv = ["gh", "pr", "list", "--repo", repository, "--state", "all",
            "--search", f"{issue} in:body", "--json", "number,state,mergedAt,body",
            "--limit", "30"]
    try:
        completed = ctx.runner(argv, stdin=subprocess.DEVNULL, capture_output=True,
                               timeout=GH_TIMEOUT_SECONDS)
        stdout = completed.stdout
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        rows = json.loads(stdout or "[]")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if not isinstance(rows, list):
        return None
    closes = re.compile(rf"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#{issue}\b",
                        re.IGNORECASE)
    found = [row for row in rows if isinstance(row, dict) and isinstance(row.get("number"), int)
             and closes.search(str(row.get("body") or ""))]
    for wanted in ("OPEN", "MERGED", "CLOSED"):
        matches = sorted((row for row in found if str(row.get("state")).upper() == wanted),
                         key=lambda row: row["number"])
        if matches:
            row = matches[-1]
            return {"number": row["number"], "state": wanted,
                    "merged": wanted == "MERGED" or bool(row.get("mergedAt"))}
    return None


# --- the reminder (row 6) -----------------------------------------------------------

def remind(ctx: Ctx, payload: dict[str, Any]) -> dict[str, Any]:
    session_id = str(payload["session_id"])
    binding = load_binding(ctx, session_id)
    if binding is None:
        return {"block": None}
    if payload.get("stop_hook_active"):
        return {"block": None}
    state = load_session(ctx, session_id)
    view = compute_view(ctx, binding, state)
    if view["waiting_on"] != "holder":
        save_session(ctx, session_id, state)
        return {"block": None}
    key = "|".join((str(view["stage"]), str(view["next_step"]),
                    str(view.get("dispatch_id") or view.get("head") or "")))
    if state.get("reminded") == key:
        save_session(ctx, session_id, state)
        return {"block": None}
    state["reminded"] = key
    save_session(ctx, session_id, state)
    return {"block": f"next: {view['next_step']} (yours)"}


# --- the command line ------------------------------------------------------------------

def _recover_command(ctx: Ctx, payload: dict[str, Any]) -> dict[str, Any]:
    candidate = recover(ctx, str(payload["session_id"]), str(payload.get("root") or ""))
    return {"candidate": candidate}


def _bind_command(ctx: Ctx, payload: dict[str, Any]) -> dict[str, Any]:
    session_id = str(payload["session_id"])
    state = load_session(ctx, session_id)
    title = title_info(ctx, session_id, payload.get("title"), state)
    candidate = payload.get("binding")
    if not isinstance(candidate, dict):
        return {"bound": False}
    return {"bound": bind(ctx, session_id, candidate, title)}


def _classify_command(_ctx: Ctx, payload: dict[str, Any]) -> dict[str, Any]:
    return classify(payload)


COMMANDS: dict[str, Callable[[Ctx, dict[str, Any]], dict[str, Any]]] = {
    "recover": _recover_command, "bind": _bind_command, "observe": observe, "tick": tick,
    "renamed": renamed, "read": read, "remind": remind, "classify": _classify_command,
}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", newline="")
    parser = argparse.ArgumentParser(
        description="The holder pane's core: one JSON object in on stdin, one out on stdout.")
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args(argv)
    raw = sys.stdin.buffer.read().decode("utf-8") if not sys.stdin.closed else ""
    payload = json.loads(raw) if raw.strip() else {}
    payload_now = payload.get("now") if isinstance(payload, dict) else None
    ctx = Ctx(now=float(payload_now) if isinstance(payload_now, (int, float)) else None)
    result = COMMANDS[args.command](ctx, payload)
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

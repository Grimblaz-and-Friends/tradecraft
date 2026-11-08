#!/usr/bin/env python3
"""The holder pane's logic: binding, readings, the read floor and the reminder.

Design: tools/holder_pane/README.md#how-it-behaves

Lab-only tooling (#888). The `holder-pane` mod's hooks module is a shim: it
runs this file as `python holder_pane.py <subcommand>` with one JSON object
on standard input and reads one JSON object from standard output. Everything
the pane shows, every file it writes and the one GitHub-reading subprocess it
starts are decided here, so the behaviour is testable with pytest and without
Claude Code.

An unbound session -- one that has run no `run <stage>` or `adopt` for a
change and has no active registry row naming its session id -- gets nothing: every
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
# The shim kills `core read` at 600 s ($.process.run's ceiling). The core's whole
# worst case stays inside that with margin: the entrance, then at most three gh
# calls, each bounded by what is left of READ_BUDGET_SECONDS.
SHIM_READ_TIMEOUT_SECONDS = 600
READ_BUDGET_SECONDS = 540
ENTRANCE_TIMEOUT_SECONDS = 450
GH_TIMEOUT_SECONDS = 25
STALE_LOCK_SECONDS = SHIM_READ_TIMEOUT_SECONDS
PENDING_RECORD_SECONDS = 600
BUNDLE_MATCH_SLACK_SECONDS = 5

OWNER_DECISIONS = frozenset({"product-incident-required", "affirmation-invalid"})
OWNER_REASONS = frozenset({"practice-work-has-no-product-incident",
                           "review-risk-lane-missing-or-mismatched"})
CI_REASON_PREFIXES = ("latest-check-run-", "declared-floor-")
GATE_REASON_MARKERS = ("gate-evaluation", "required-gate-")
REVIEWER_REASONS = frozenset({"required-connected-reviewer-has-not-run"})
HOLDER_WAITING_REASONS = frozenset({
    "base-synchronization-unavailable", "merge-verdict-unknown", "merge-blocked-required-gate",
    "merge-blocked-unresolved-review-threads", "merge-blocked-unattributed",
})
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
RECORD_SEARCH_SECONDS = 600
RENAME_OFF = "rename off: the app's session records weren't found"
RENAMING_SOURCES = frozenset({"auto", "tool"})

STATUS_FIELDS = (
    "schema_version", "repository", "issue", "session_name", "session_id",
    "stage", "waiting_on", "next_step", "gate", "floor", "status", "source",
    "read_at",
)

WORK_PY = re.compile(r"[\\/]lib[\\/]work\.py$")
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
    # Proof and catch-up reports carry their head at the top level. It is read last, so a
    # decision's gate, floor or synchronization head wins where both are present.
    for holder in (decision.get("required_gate"), decision.get("floor"),
                   decision.get("synchronization"), decision):
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
                          pr: dict[str, Any] | None = None,
                          entrance_decision: bool = True) -> dict[str, Any]:
    """`entrance_decision` is false for a holder-only stage's own refused, waiting or terminal
    report: only the entrance's decision can end a posted release report (README "How it behaves")."""
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
        "decision": entrance_decision,
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
        "decision": False,
    }


def _pr_number(pr: Any) -> int | None:
    return int(pr["number"]) if isinstance(pr, dict) and isinstance(pr.get("number"), int) else None


def _moved_on(report: dict[str, Any], stage: str) -> bool:
    """A stage's own report is the entrance's decision about the change only when it names
    another stage than the one called and than the release report: a `run proof` refused
    because the base moved names `catch-up`, so the change has moved on."""
    return str(report.get("stage")) not in (stage, "release-report")


def no_launch_reading(stage: str, report: dict[str, Any] | None, output: str, now: float,
                      pr: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """A stage that launches nobody: its own report is the reading.

    A report carrying the entrance's `next` decision (catch-up) reads as that
    decision; a report for another stage, or one refused, waiting or terminal,
    reads through the classifier; the stage's own success reads through the
    return table. A call that printed no report (a failed run prints only
    `work: <error>` and exits 1) is no return: it keeps the previous reading.
    """
    if isinstance(report, dict) and _is_decision(report.get("next")):
        reading = reading_from_decision(report["next"], "stage-return", now, pr)
        if isinstance(report.get("head"), str) and report["head"]:
            # A catch-up's own head is the landed result: the head its next decision is at.
            reading["head"] = report["head"]
        return reading
    if _is_decision(report) and (report["stage"] != stage or report["status"] in (
            "refused", "waiting", "terminal")):
        return reading_from_decision(report, "stage-return", now, pr,
                                     entrance_decision=_moved_on(report, stage))
    if report is not None:
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


def forget_steward(ctx: Ctx, session_id: str) -> None:
    """A Steward keeps nothing of the pane's: its binding, its session state and its status file."""
    binding = load_binding(ctx, session_id)
    if binding is not None:
        path = status_path(ctx, change_key(binding["repository"], binding["issue"]))
        record = _read_json(path)
        if isinstance(record, dict) and record.get("session_id") == session_id:
            _remove(path)
    unbind(ctx, session_id)
    _remove(session_path(ctx, session_id))


def _desktop_record_dirs(ctx: Ctx) -> list[Path]:
    """Where the desktop app keeps its session records: its current place first, then the old."""
    dirs = []
    local = ctx.environ.get("LOCALAPPDATA")
    if local:
        try:
            dirs.extend(sorted(entry / "claude-code-sessions"
                               for entry in (Path(local) / "Claude-Data").iterdir()))
        except OSError:
            pass
    appdata = ctx.environ.get("APPDATA")
    if appdata:
        dirs.append(Path(appdata) / "Claude" / "claude-code-sessions")
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
    missed = state.get("desktop_miss_at")
    if isinstance(missed, (int, float)) and ctx.now() - float(missed) < RECORD_SEARCH_SECONDS:
        return None
    for base in _desktop_record_dirs(ctx):
        for path in sorted(base.glob("*/*/local_*.json")):
            record = _read_json(path)
            if isinstance(record, dict) and record.get("cliSessionId") == session_id:
                state["desktop_record"] = str(path)
                state.pop("desktop_miss_at", None)
                return record
    # Searched again only after a while: hundreds of records aren't read on every tick.
    state["desktop_miss_at"] = ctx.now()
    return None


def title_info(ctx: Ctx, session_id: str, probe: Any, state: dict[str, Any]) -> dict[str, Any]:
    """Resolve the shim's title read (section 5).

    `probe` is what the shim saw: `{"decision": allow|ask|deny|absent, "text": ...}`.
    Anything but `allow` is unreadable, and then the record's title serves only
    the Steward exemption (`steward`), never a rename. `records_missing` says the
    app's session records weren't found, so renaming is off and the pane says so.
    """
    if not isinstance(probe, dict) or probe.get("decision") != "allow":
        record = desktop_record(ctx, session_id, state)
        recorded = record.get("title") if isinstance(record, dict) else None
        return {"readable": False, "title": None, "source": None,
                "steward": is_steward(recorded), "records_missing": False}
    answered = last_json_object(str(probe.get("text") or "")) or {}
    title = answered.get("title") if isinstance(answered.get("title"), str) else None
    source = answered.get("titleSource") if isinstance(answered.get("titleSource"), str) else None
    record = desktop_record(ctx, session_id, state)
    if record is not None:
        if source is None and isinstance(record.get("titleSource"), str):
            source = record["titleSource"]
        if not title and isinstance(record.get("title"), str):
            title = record["title"]
    missing = record is None and source is None
    if not title:
        return {"readable": False, "title": None, "source": None, "steward": False,
                "records_missing": missing}
    return {"readable": True, "title": title, "source": source, "steward": is_steward(title),
            "records_missing": missing}


def is_steward(title: Any) -> bool:
    """`Steward`, or any repository's `<Name> Steward`: the address its holders reach it by."""
    if not isinstance(title, str):
        return False
    folded = title.strip().casefold()
    return folded == STEWARD or folded.endswith(" " + STEWARD)


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
    """Bind unless the session is a Steward. Returns whether bound."""
    if title.get("steward"):
        forget_steward(ctx, session_id)
        return False
    previous = load_binding(ctx, session_id)
    state = load_session(ctx, session_id)
    if previous is None or (previous.get("repository"), previous.get("issue")) != (
            binding["repository"], binding["issue"]):
        # A new change: nothing from the previous one carries over but the rename record, and
        # a posted release report, which no read would restore when the session comes back.
        state = {key: state[key] for key in ("desktop_record", "desktop_miss_at", "last_label",
                                              "last_title_set", "rename_disabled",
                                              "release_reports_posted",
                                              "release_report_posted") if key in state}
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


def _resolved(path: Any) -> str | None:
    if not isinstance(path, str) or not path:
        return None
    try:
        return os.path.normcase(str(Path(path).resolve()))
    except OSError:
        return None


def recover(ctx: Ctx, session_id: str, root: str) -> dict[str, Any] | None:
    """Restart recovery: this session's binding file, else the one active change naming this session.

    Matched by the row's `holder_session_id`, never by worktree alone: two
    holders can share a worktree, and the older must not take the newer's change.
    """
    existing = load_binding(ctx, session_id)
    if existing is not None:
        return existing
    registry = _read_json(ctx.tradecraft / "implementation-worktrees.json")
    rows = registry.get("worktrees") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        return None
    matches = [row for row in rows if isinstance(row, dict) and row.get("active") is True
               and row.get("holder_session_id") == session_id
               and isinstance(row.get("repository"), str) and isinstance(row.get("issue"), int)]
    wanted = _resolved(root)
    at_root = [row for row in matches
               if wanted is not None and _resolved(row.get("holder_root")) == wanted]

    def changes(found: list[dict[str, Any]]) -> set[tuple[Any, ...]]:
        return {(row["repository"], row["issue"], row.get("instalment")) for row in found}

    if len(changes(matches)) > 1:
        matches = at_root
    if len(changes(matches)) != 1:
        return None
    # Every remaining row names the same change, so any of them binds it; one at the
    # session's root is preferred only for the root the binding reports.
    row = next((row for row in matches if row in at_root), matches[-1])
    instalment = row.get("instalment") if isinstance(row.get("instalment"), str) else None
    return {"repository": row["repository"], "issue": row["issue"],
            "root": row["holder_root"], "entrance": newest_cached_entrance(ctx),
            "instalment": instalment}


# --- reading a shell command: its redirects and its posts ------------------
#
# The pane learns that the holder finished a step of its own only from the
# holder's own command text and the local files it names, never from GitHub.
# Anything the reader below cannot resolve reads as no redirect, or as an
# unreadable body, which the view shows as "posted, unconfirmed" until the next
# read: the safe outcome (README "How it behaves").

HEREDOC_OP = re.compile(r"(?<!<)<<(-?)[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
HEREDOC_SLOT = re.compile(r"<<\x00(\d+)\x00")
HEREDOC_CAT = re.compile(r"\$\(\s*cat\s+<<\x00(\d+)\x00\s*\)")
BACKGROUND_LAUNCH = re.compile(r"running in background with ID:\s*(?P<id>[A-Za-z0-9_.-]+?)\.?\s"
                               r"(?:[^\n]*?Output is being written to:\s*(?P<file>[^\n]+?\.output))?",
                               re.IGNORECASE)
EXIT_CODE = re.compile(r"\s*Exit code (\d+)")
# Built at runtime so the source stays ASCII.
ARROW, BOM = chr(0x2192), chr(0xFEFF)
TITLE_LINE = re.compile(r"\*\*Release report: #(\d+) " + ARROW
                        + r" PR #(\d+)\*\*(?=\s|$)(?P<rest>[^\n]*)")
TITLE_HEAD = re.compile(r"\s*at head\s+`?([0-9a-fA-F]{7,40})`?(?![0-9a-fA-F])")
ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.DOTALL)
PS_VARIABLE = re.compile(r"^\$([A-Za-z_][A-Za-z0-9_]*)$")
PS_ENV_VARIABLE = re.compile(r"^\$env:([A-Za-z_][A-Za-z0-9_]*)$", re.IGNORECASE)
STDOUT_REDIRECT = re.compile(r"^(1?>>?|&>>?|\*>>?)(?!&)")
# Reads are capped so a stray large file can't stall a hook.
# A body file needs only its opening line, which holds the title line.
BODY_LIMIT_BYTES = 65536
# An `--input` file is JSON that must parse whole: sized to hold any comment body GitHub
# accepts, plus its JSON.
INPUT_LIMIT_BYTES = 1024 * 1024
# A report past its cap reads as no report, which the next entrance read corrects, as for
# any report the pane can't find.
REPORT_LIMIT_BYTES = 8 * 1024 * 1024
# gh options that take no value, so the word after them is not theirs.
GH_SWITCHES = frozenset({"--web", "-w", "--edit-last", "--editor", "-e", "--yes",
                         "--create-if-none", "--delete-last", "--paginate", "--slurp", "-i",
                         "--include", "--silent", "--verbose"})


def lift_heredocs(command: str) -> tuple[str, list[str], list[bool]]:
    """Lift each heredoc's body out of the command, leaving `<<\\0N\\0` where its operator stood.

    Lifted first, so text inside a heredoc (a Python script that mentions `gh`)
    is never read as a call.
    """
    lines = command.split("\n")
    kept: list[str] = []
    bodies: list[str] = []
    quoted: list[bool] = []
    index = 0
    while index < len(lines):
        tags: list[str] = []

        def slot(match: re.Match) -> str:
            tags.append(match.group(3))
            bodies.append("")
            quoted.append(bool(match.group(2)))
            return f"<<\x00{len(bodies) - 1}\x00"

        kept.append(HEREDOC_OP.sub(slot, lines[index]))
        index += 1
        first = len(bodies) - len(tags)
        for offset, tag in enumerate(tags):
            body = []
            while index < len(lines) and lines[index].strip() != tag:
                body.append(lines[index])
                index += 1
            index += 1
            bodies[first + offset] = "".join(line + "\n" for line in body)
    return "\n".join(kept), bodies, quoted


def split_commands(text: str) -> list[list[str]]:
    """Quote-aware: pipelines cut on `;`, `&&`, `||`, `&` and newlines, each a list of `|` segments."""
    pipelines: list[list[str]] = []
    segments: list[str] = []
    current: list[str] = []
    quote: str | None = None
    depth = 0

    def cut_segment() -> None:
        segment = "".join(current).strip()
        current.clear()
        if segment:
            segments.append(segment)

    def cut_pipeline() -> None:
        cut_segment()
        if segments:
            pipelines.append(list(segments))
        segments.clear()

    index = 0
    while index < len(text):
        char = text[index]
        after = text[index + 1] if index + 1 < len(text) else ""
        if quote == "'":
            current.append(char)
            quote = None if char == "'" else quote
            index += 1
            continue
        if char in "\\`" and after == "\n" and quote is None:
            index += 2  # a line continuation (bash, PowerShell)
            continue
        if char == "\\" and quote == '"' and after:
            current.append(char + after)
            index += 2
            continue
        if char == "$" and after == "(":
            depth += 1
            current.append("$(")
            index += 2
            continue
        if char == ")" and depth:
            depth -= 1
        elif char == '"':
            quote = None if quote == '"' else '"'
        elif char == "'" and quote is None:
            quote = "'"
        elif quote is None and depth == 0:
            before = text[index - 1] if index else ""
            if char in ";\n":
                cut_pipeline()
                index += 1
                continue
            if char == "|":
                if after == "|":
                    cut_pipeline()
                    index += 2
                else:
                    cut_segment()
                    index += 1
                continue
            if char == "&" and after == "&":
                cut_pipeline()
                index += 2
                continue
            if char == "&" and before not in "<>" and after != ">":
                cut_pipeline()
                index += 1
                continue
        current.append(char)
        index += 1
    cut_pipeline()
    return pipelines


class Word:
    """One shell word: its source text, its value, and whether any expansion stayed unresolved."""

    def __init__(self) -> None:
        self.raw = ""
        self.value = ""
        self.unresolved: list[int] = []
        self.quoted = False

    @property
    def first_line_unresolved(self) -> bool:
        end = self.value.find("\n")
        return any(end < 0 or position < end for position in self.unresolved)


def _lookup(env: dict[str, str], name: str) -> str | None:
    if name in env:
        return env[name]
    folded = name.casefold()
    return next((value for key, value in env.items() if key.casefold() == folded), None)


def words(segment: str, env: dict[str, str], home: Path,
          shell: dict[str, str] | None = None) -> list[Word]:
    """Split a simple command into words, expanding `$NAME`, `${NAME}`, `$env:NAME` and `~`."""
    found: list[Word] = []
    word: Word | None = None
    quote: str | None = None
    index = 0
    while index < len(segment):
        char = segment[index]
        if quote is None and char in " \t\n\r":
            if word is not None:
                found.append(word)
                word = None
            index += 1
            continue
        if word is None:
            word = Word()
            if char == "~" and segment[index + 1:index + 2] in ("", "/", "\\", " "):
                word.raw += char
                word.value += str(home)
                index += 1
                continue
        if quote == "'":
            word.raw += char
            if char == "'":
                quote = None
            else:
                word.value += char
            index += 1
            continue
        if char == "'" and quote is None:
            quote = "'"
            word.quoted = True
            word.raw += char
            index += 1
            continue
        if char == '"':
            quote = None if quote == '"' else '"'
            word.quoted = True
            word.raw += char
            index += 1
            continue
        if char == "\\" and quote == '"' and segment[index + 1:index + 2] in ('"', "\\", "$", "`"):
            word.raw += segment[index:index + 2]
            word.value += segment[index + 1]
            index += 2
            continue
        if char == "`" and quote == '"':
            word.unresolved.append(len(word.value))
            word.raw += char
            word.value += char
            index += 1
            continue
        if char == "$":
            consumed, expansion = _expand(segment, index, env, shell)
            word.raw += segment[index:index + consumed]
            if expansion is None:
                word.unresolved.append(len(word.value))
                word.value += segment[index:index + consumed]
            else:
                word.value += expansion
            index += consumed
            continue
        word.raw += char
        word.value += char
        index += 1
    if word is not None:
        found.append(word)
    return found


def _expand(text: str, index: int, env: dict[str, str],
            shell: dict[str, str] | None = None) -> tuple[int, str | None]:
    """At a `$`: how many characters it spans, and its value (None when unresolved).

    `$env:NAME` reads only the environment; `$NAME` reads a PowerShell variable first, so
    `$S = '…'` never answers `$env:S`.
    """
    shell = shell or {}
    rest = text[index + 1:]
    if rest.startswith("("):
        depth, position = 0, 0
        for position, char in enumerate(rest):
            depth += 1 if char == "(" else -1 if char == ")" else 0
            if depth == 0:
                break
        return position + 2, None
    braced = re.match(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", rest)
    if braced:
        name = braced.group(1)
        return braced.end() + 1, shell.get(name, _lookup(env, name))
    powershell = re.match(r"env:([A-Za-z_][A-Za-z0-9_]*)", rest, re.IGNORECASE)
    if powershell:
        return powershell.end() + 1, _lookup(env, powershell.group(1))
    named = re.match(r"[A-Za-z_][A-Za-z0-9_]*", rest)
    if named:
        name = named.group(0)
        return named.end() + 1, shell.get(name, _lookup(env, name))
    if rest[:1] and (rest[0].isdigit() or rest[0] in "?!#@*-$"):
        return 2, None
    return 1, "$"


def _path(value: str | None, cwd: str | None) -> Path | None:
    """A path as the shell would open it: MSYS `/c/` drives, and relative to the last `cd`."""
    if not value:
        return None
    drive = re.match(r"^/([A-Za-z])(?:/(.*))?$", value)
    if drive:
        value = f"{drive.group(1).upper()}:/{drive.group(2) or ''}"
    path = Path(value)
    if not path.is_absolute():
        if not cwd:
            return None
        path = Path(cwd) / path
    return path


class Commands:
    """A shell command read once: its simple commands, with the variables and directory each sees."""

    def __init__(self, ctx: Ctx, command: str, root: str | None) -> None:
        text, self.bodies, quoted = lift_heredocs(command)
        env = dict(ctx.environ)
        shell: dict[str, str] = {}
        cwd = root or None
        self.pipelines: list[list[tuple[str, list[Word], str | None]]] = []
        for pipeline in split_commands(text):
            read: list[tuple[str, list[Word], str | None]] = []
            for segment in pipeline:
                found = words(segment, env, ctx.home, shell)
                read.append((segment, found, cwd))
                for slot in HEREDOC_SLOT.finditer(segment):
                    number = int(slot.group(1))
                    if not quoted[number]:
                        # An unquoted heredoc expands as the shell would; a quoted one is literal.
                        self.bodies[number] = _expand_text(self.bodies[number], env, shell)
                cwd = self._effects(found, env, cwd, shell)
            self.pipelines.append(read)

    @staticmethod
    def _effects(found: list[Word], env: dict[str, str], cwd: str | None,
                 shell: dict[str, str]) -> str | None:
        if not found:
            return cwd
        first = found[0]
        if len(found) >= 3 and found[1].raw == "=":
            if PS_ENV_VARIABLE.match(first.raw):
                env[PS_ENV_VARIABLE.match(first.raw).group(1)] = found[2].value
                return cwd
            if PS_VARIABLE.match(first.raw):
                shell[PS_VARIABLE.match(first.raw).group(1)] = found[2].value
                return cwd
        names = [word for word in (found[1:] if first.value == "export" else found)]
        if names and all(ASSIGNMENT.match(word.value) and not word.raw.startswith(("'", '"'))
                         for word in names):
            for word in names:
                name, value = ASSIGNMENT.match(word.value).groups()
                if word.unresolved:
                    env.pop(name, None)
                else:
                    env[name] = value
            return cwd
        if first.value.casefold() in ("cd", "set-location", "pushd"):
            target = next((word for word in found[1:] if not word.value.startswith("-")
                           and word.value.casefold() != "/d"), None)
            if target is None or target.unresolved:
                return None
            resolved = _path(target.value, cwd)
            return str(resolved) if resolved is not None else None
        return cwd

    def heredoc(self, segment: str) -> str | None:
        slot = HEREDOC_SLOT.search(segment)
        return self.bodies[int(slot.group(1))] if slot else None

    def redirect(self) -> Path | None:
        """Where the `run <stage>` call's report went: its stdout redirect or a tee in its pipe."""
        for pipeline in self.pipelines:
            for position, (segment, found, cwd) in enumerate(pipeline):
                if parse_entrance_call(segment) is None:
                    continue
                target: Path | None = None
                for index, word in enumerate(found):
                    operator = STDOUT_REDIRECT.match(word.raw)
                    if not operator:
                        continue
                    rest = word.value[len(operator.group(1)):]
                    if rest:
                        target = None if word.unresolved else _path(rest, cwd)
                    elif index + 1 < len(found):
                        following = found[index + 1]
                        target = None if following.unresolved else _path(following.value, cwd)
                for later, later_words, later_cwd in pipeline[position + 1:]:
                    tee = _tee_target(later_words, later_cwd)
                    if tee is not None:
                        target = tee
                return target
        return None

    def posts(self) -> list[dict[str, Any]]:
        """Every `gh` comment the command makes, with its target and the body it sends."""
        found = []
        for pipeline in self.pipelines:
            for segment, segment_words, cwd in pipeline:
                post = self._post(segment, segment_words, cwd)
                if post is not None:
                    found.append(post)
        return found

    def _post(self, segment: str, found: list[Word], cwd: str | None) -> dict[str, Any] | None:
        while found and ASSIGNMENT.match(found[0].value):
            found = found[1:]
        if len(found) < 3 or found[0].value != "gh":
            return None
        verb = [found[1].value, found[2].value]
        options, positional = _gh_arguments(found[3:] if verb[0] != "api" else found[2:])
        if verb[0] == "api":
            if not positional:
                return None
            endpoint = re.match(r"^/?repos/([^/]+)/([^/]+)/issues/(\d+)/comments/?$",
                                positional[0].value)
            method = _first(options, "-X", "--method")
            fields = [word for name in ("-f", "--raw-field", "-F", "--field")
                      for word in options.get(name, [])]
            has_input = bool(options.get("--input"))
            if not endpoint or (method is not None and method.value.upper() != "POST") or (
                    method is None and not fields and not has_input):
                return None
            repository = f"{endpoint.group(1)}/{endpoint.group(2)}"
            if "{owner}" in repository or "{repo}" in repository:
                repository = None
            return {"kind": "api", "target": int(endpoint.group(3)), "repository": repository,
                    "body": self._api_body(segment, options, cwd)}
        if verb not in (["pr", "comment"], ["issue", "comment"], ["pr", "edit"]):
            return None
        target = _target(positional[0].value) if positional else None
        if target is None:
            return None
        has_body = any(options.get(name) for name in ("-b", "--body", "-F", "--body-file"))
        if verb == ["pr", "edit"] and not has_body:
            return None
        repo = _first(options, "-R", "--repo")
        repository = _repository(repo.value) if repo is not None else _url_repository(
            positional[0].value)
        if "--delete-last" in options:
            # A delete, never a post: it may remove the report itself.
            return {"kind": verb[0], "target": target, "repository": repository,
                    "body": None, "delete": True}
        return {"kind": verb[0], "target": target, "repository": repository,
                "body": self._comment_body(segment, options, cwd)}

    def _comment_body(self, segment: str, options: dict[str, list[Word]],
                      cwd: str | None) -> str | None:
        inline = _first(options, "-b", "--body")
        if inline is not None:
            return self._inline(inline)
        named = _first(options, "-F", "--body-file")
        if named is None:
            return None
        if named.value == "-":
            return self.heredoc(segment)
        return None if named.unresolved else _read_text(_path(named.value, cwd))

    def _api_body(self, segment: str, options: dict[str, list[Word]],
                  cwd: str | None) -> str | None:
        for name, typed in (("-f", False), ("--raw-field", False), ("-F", True), ("--field", True)):
            for word in options.get(name, []):
                if not word.value.startswith("body="):
                    continue
                value = word.value[len("body="):]
                if typed and value.startswith("@"):
                    if value == "@-":
                        return self.heredoc(segment)
                    return None if word.unresolved else _read_text(_path(value[1:], cwd))
                return self._inline(word, prefix=len("body="))
        source = _first(options, "--input")
        if source is None:
            return None
        if source.value == "-":
            text = self.heredoc(segment)
        else:
            text = None if source.unresolved else _read_text(_path(source.value, cwd),
                                                             INPUT_LIMIT_BYTES)
        try:
            parsed = json.loads(text) if text is not None else None
        except ValueError:
            return None
        body = parsed.get("body") if isinstance(parsed, dict) else None
        return body if isinstance(body, str) else None

    def _inline(self, word: Word, prefix: int = 0) -> str | None:
        value = word.value[prefix:]
        heredoc = HEREDOC_CAT.fullmatch(value.strip())
        if heredoc:
            return self.bodies[int(heredoc.group(1))]
        if word.first_line_unresolved:
            return None
        return value


def _expand_text(text: str | None, env: dict[str, str],
                 shell: dict[str, str]) -> str | None:
    """An unquoted heredoc's text expanded; None when any expansion can't be resolved."""
    if text is None:
        return None
    out, index = [], 0
    while index < len(text):
        char = text[index]
        if char == "\\" and text[index + 1:index + 2] in ("$", "`", "\\"):
            out.append(text[index + 1])
            index += 2
            continue
        if char == "`":
            return None
        if char == "$":
            consumed, value = _expand(text, index, env, shell)
            if value is None:
                return None
            out.append(value)
            index += consumed
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _gh_arguments(found: list[Word]) -> tuple[dict[str, list[Word]], list[Word]]:
    """A gh command's options (each with its value) and its positional words."""
    options: dict[str, list[Word]] = {}
    positional: list[Word] = []
    index = 0
    while index < len(found):
        word = found[index]
        # An option's name is never quoted, though its attached value may be
        # (`--body-file="$REPORT"`); a quoted word is a positional argument.
        if word.raw.startswith("-") and len(word.value) > 1:
            name, equals, value = word.value.partition("=")
            if equals:
                attached = Word()
                attached.raw, attached.value, attached.quoted = word.raw, value, word.quoted
                attached.unresolved = [max(0, position - len(name) - 1)
                                       for position in word.unresolved]
                options.setdefault(name, []).append(attached)
            elif name in GH_SWITCHES or index + 1 >= len(found):
                options.setdefault(name, [])
            else:
                options.setdefault(name, []).append(found[index + 1])
                index += 1
        else:
            positional.append(word)
        index += 1
    return options, positional


def _first(options: dict[str, list[Word]], *names: str) -> Word | None:
    for name in names:
        if options.get(name):
            return options[name][-1]
    return None


def _target(text: str) -> int | None:
    match = re.match(r"^#?(\d+)$", text) or re.search(r"/(?:pull|issues)/(\d+)(?:[/#?].*)?$", text)
    return int(match.group(1)) if match else None


def _url_repository(text: str) -> str | None:
    """The repository a `…/O/R/pull/N` or `…/O/R/issues/N` target names, if it is a URL."""
    match = re.search(r"([^/\s]+)/([^/\s]+)/(?:pull|issues)/\d+", text)
    return f"{match.group(1)}/{match.group(2)}" if match else None


def _repository(text: str) -> str:
    parts = [part for part in re.sub(r"^https?://", "", text).split("/") if part]
    return "/".join(parts[-2:])


def _tee_target(found: list[Word], cwd: str | None) -> Path | None:
    if not found or found[0].value.casefold() not in ("tee", "tee-object", "out-file"):
        return None
    for index, word in enumerate(found[1:], start=1):
        if word.value.casefold() in ("-filepath", "-path", "-literalpath"):
            following = found[index + 1] if index + 1 < len(found) else None
            return None if following is None or following.unresolved else _path(
                following.value, cwd)
        if word.value.startswith("-"):
            continue
        return None if word.unresolved else _path(word.value, cwd)
    return None


def _read_text(path: Path | None, limit: int = BODY_LIMIT_BYTES) -> str | None:
    """A body file's first `limit` bytes as UTF-8 (a BOM stripped); None when it can't be read."""
    if path is None:
        return None
    try:
        with open(path, "rb") as stream:
            data = stream.read(limit)
    except OSError:
        return None
    return data.decode("utf-8", errors="replace").removeprefix(BOM)


def release_report_title(body: str | None, issue: int,
                         pull_request: int | None) -> dict[str, Any] | None:
    """The report's required title line naming this change, and the head it names (if any)."""
    if body is None:
        return None
    match = TITLE_LINE.match(body.lstrip())
    if not match or int(match.group(1)) != issue:
        return None
    named = int(match.group(2))
    if pull_request is not None and named != pull_request:
        return None
    head = TITLE_HEAD.match(match.group("rest"))
    return {"pull_request": named, "head": head.group(1) if head else None}


def report_file(path: Path | None, since: float) -> tuple[dict[str, Any] | None, float | None, bool]:
    """A complete entrance report in a file written since `since`, its mtime, and a `work:` failure.

    Complete means the last JSON object, starting a line and running to the end
    of the trimmed text, so a half-written report or an earlier run's file never
    reads as this call's return.
    """
    if path is None:
        return None, None, False
    try:
        mtime = path.stat().st_mtime
        if mtime < since - BUNDLE_MATCH_SLACK_SECONDS:
            return None, None, False
        with open(path, "rb") as stream:
            data = stream.read(REPORT_LIMIT_BYTES + 1)
    except OSError:
        return None, None, False
    if len(data) > REPORT_LIMIT_BYTES:
        return None, mtime, False  # its truncated prefix must never read as a complete report
    text = data.decode("utf-8", errors="replace")
    text = text.removeprefix(BOM).rstrip()
    failed = any(line.startswith("work: ") for line in text.splitlines())
    decoder = json.JSONDecoder()
    start = len(text)
    while True:
        start = text.rfind("{", 0, start)
        if start < 0:
            return None, mtime, failed
        if start == 0 or text[start - 1] == "\n":
            try:
                value, end = decoder.raw_decode(text, start)
            except ValueError:
                value, end = None, -1
            if end == len(text) and (_is_decision(value) or (
                    isinstance(value, dict) and "next" in value)):
                return value, mtime, failed
            if end == len(text):
                return None, mtime, failed


def _same_head(first: Any, second: Any) -> bool:
    # Title lines and reports may carry an abbreviated SHA. The floor keeps a short shared
    # prefix from matching an unrelated head and keeping the owner's merge showing.
    if not (isinstance(first, str) and isinstance(second, str)):
        return False
    first, second = first.lower(), second.lower()
    return min(len(first), len(second)) >= 7 and (first.startswith(second)
                                                   or second.startswith(first))


# --- observing the holder's own calls ----------------------------------------


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
    if title.get("steward"):
        forget_steward(ctx, session_id)
        return {"bound": False}
    # Binding may have reset the session's state for a new change, so it is read again; only
    # the desktop-record lookup the title read just made is kept, so it isn't repeated.
    state = {**load_session(ctx, session_id),
             **{key: state[key] for key in ("desktop_record", "desktop_miss_at") if key in state}}
    change = load_change(ctx, change_key(binding["repository"], binding["issue"]))
    pr = change.get("pull_request")
    root = payload.get("root") if isinstance(payload.get("root"), str) else None
    commands = Commands(ctx, command, root)
    same_change = call is not None and (call["repository"], call["issue"]) == (
        binding["repository"], binding["issue"])
    failed = payload.get("is_error") is True or (
        (code := EXIT_CODE.match(output)) is not None and int(code.group(1)) != 0)
    if same_change and call["verb"] == "run":
        stage = call["stage"]
        launch = BACKGROUND_LAUNCH.search(output)
        state.pop("background", None)  # a new stage call ends a background run's display
        if stage in DISPATCHING:
            _observe_launch(ctx, binding, state, stage, output, started, ended, pr, call)
        elif not failed and (payload.get("background") is True or launch is not None):
            # Run in the background: its report comes later, in a file (README "How it behaves").
            # A call that failed launched nothing, so it reads as a failure below instead.
            state["background"] = {
                "stage": stage, "started_at": started, "ended_at": None,
                "task_id": launch.group("id") if launch else None,
                "output_file": launch.group("file").strip() if launch and launch.group("file")
                else None,
                "redirect": str(commands.redirect()) if commands.redirect() else None,
            }
            state.pop("failure", None)
            state.pop("pending", None)
            state.pop("tracked", None)
        else:
            report = last_json_object(output)
            if report is None:
                # A holder that redirects the call's output leaves no report in the tool result.
                report = report_file(commands.redirect(), started)[0]
            reading = no_launch_reading(stage, report, output, ended, pr)
            if reading is not None:
                state["reading"] = reading
                state.pop("failure", None)
            else:
                # The stage never ran to a report: keep the reading and show the failure.
                state["failure"] = {"stage": stage, "at": ended}
            state.pop("pending", None)
            state.pop("tracked", None)
    if not failed:
        _observe_posts(binding, state, change, commands, ended, output)
    save_session(ctx, session_id, state)
    return {"bound": True, "binding": binding}


def _comment_shown(text: str, target: int) -> bool:
    """Whether a post's output shows the comment GitHub created on `target`."""
    return re.search(rf"/(?:issues|pull)/{int(target)}#issuecomment-\d+", text) is not None


def _observe_posts(binding: dict[str, Any], state: dict[str, Any], change: dict[str, Any],
                   commands: Commands, ended: float, output: str = "") -> None:
    """The holder's own posts to its change: a release report, or a step posted, unconfirmed.

    A release report counts only when the post's own output shows the comment GitHub
    created: no read would ever correct a report counted that was never posted, and a call
    can succeed while its post fails (`gh …; echo`). A post run in the background shows only
    its launch, so its task output file is read for that evidence as it fills.
    """
    launch = BACKGROUND_LAUNCH.search(output)
    output_file = launch.group("file").strip() if launch and launch.group("file") else None
    issue = int(binding["issue"])
    in_force = _newer(state.get("reading"), change.get("reading"))
    known = in_force.get("pull_request") if isinstance(in_force, dict) and isinstance(
        in_force.get("pull_request"), int) else _pr_number(change.get("pull_request"))
    for post in commands.posts():
        repository = post.get("repository")
        if repository is not None and repository.casefold() != str(
                binding["repository"]).casefold():
            continue
        title = release_report_title(post["body"], issue, known)
        target = post["target"]
        # Until the pane knows the change's pull request, a release report counts on the pull
        # request its title line names, since a wrong match never corrects itself; any other
        # `gh pr` post counts, as its wrong mark corrects itself at the next read.
        if known is not None:
            ours = target in (issue, known)
        elif title is not None:
            ours = target in (issue, title["pull_request"])
        else:
            ours = target == issue or post["kind"] == "pr"
        if not ours:
            continue
        if post.get("delete"):
            # The deleted comment may be the posted report: the next read decides again.
            _drop_report(state, binding)
            state.pop("report_post_pending", None)
            continue
        posted = state.get("posted") if isinstance(state.get("posted"), dict) else {}
        if title is not None:
            head = title["head"] or (in_force.get("head") if isinstance(in_force, dict) else None)
            record = {"at": ended, "pull_request": title["pull_request"], "head": head,
                      "change": _change_of(binding)}
            if _comment_shown(output, target):
                _keep_report(state, record)
                continue
            if output_file:
                state["report_post_pending"] = {**record, "target": target,
                                                "output_file": output_file}
            # Unshown, the post is unconfirmed until the next read, as any unreadable body is.
            state["posted"] = {"at": ended, "unreadable_at": ended}
            continue
        state["posted"] = {"at": ended, "unreadable_at": ended if post["body"] is None
                           else posted.get("unreadable_at")}


def _observe_launch(ctx: Ctx, binding: dict[str, Any], state: dict[str, Any], stage: str,
                    output: str, started: float, ended: float,
                    pr: dict[str, Any] | None = None,
                    call: dict[str, Any] | None = None) -> None:
    state.pop("tracked", None)
    state.pop("posted", None)
    owner = call if call is not None else binding
    work = f"{binding['repository']}#{binding['issue']}"
    match = _matching_bundle(bundles_for(ctx, work), stage, started)
    if match is not None:
        _drop_report(state, owner)
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
        # whatever its status (a holder-owned budget or scope refusal included). Nothing was
        # dispatched, so a posted release report stands.
        state.pop("pending", None)
        state["reading"] = reading_from_decision(decision, "stage-return", ended, pr,
                                                 entrance_decision=_moved_on(decision, stage))
        return
    if _is_decision(decision) and decision.get("dispatch") is True:
        _drop_report(state, owner)
    # Launched, its bundle not yet recorded: the report ends once the bundle shows it ran.
    state["pending"] = {"stage": stage, "started_at": started, "ended_at": ended,
                        "change": _change_of(owner)}


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
    if view.get("status") == "ended":
        return f"{stage} ended"
    if view.get("posted"):
        return f"{stage} posted, unconfirmed"
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


def _mtime(path: Any) -> float | None:
    try:
        return Path(str(path)).stat().st_mtime if path else None
    except OSError:
        return None


def _for_change(report: dict[str, Any], work: str | None) -> bool:
    """Whether a report names this change, by its own `work` or its next decision's. A report
    naming none (an up-to-date catch-up) can't be told apart, and is taken as this call's."""
    named = report.get("work")
    if not isinstance(named, str) and isinstance(report.get("next"), dict):
        named = report["next"].get("work")
    return work is None or not isinstance(named, str) or named.casefold() == work.casefold()


def _settle_background(state: dict[str, Any], change: dict[str, Any],
                       work: str | None = None) -> None:
    """A background stage ends at its complete report, an entrance read started after its task
    ended, or a `work:` failure once it has ended; until then it shows running (or ended).

    A read that started while the stage still ran can't reflect it, so it ends nothing: the
    pane keeps looking for the report, which then becomes the newer reading. Mutates `state`.
    """
    background = state.get("background")
    if not isinstance(background, dict):
        return
    stage = str(background.get("stage"))
    started = float(background.get("started_at") or 0)
    path = background.get("redirect") or background.get("output_file")
    report, written, failed = report_file(Path(path) if path else None, started)
    if report is not None and not _for_change(report, work):
        report = None
    reading = no_launch_reading(stage, report, "", float(written or started),
                                change.get("pull_request")) if report is not None else None
    if reading is not None:
        state["reading"] = reading
        state.pop("failure", None)
        state.pop("background", None)
        return
    entrance = change.get("reading")
    ended_at = background.get("ended_at")
    if isinstance(ended_at, (int, float)) and isinstance(entrance, dict) and float(
            entrance.get("read_at") or 0) > float(ended_at):
        state.pop("background", None)
        return
    if background.get("ended_at") and failed:
        state["failure"] = {"stage": stage, "at": float(background["ended_at"])}
        state.pop("background", None)


def _change_of(binding: dict[str, Any]) -> list[Any]:
    return [str(binding["repository"]), int(binding["issue"]), binding.get("instalment")]


def _report_key(change: list[Any]) -> str:
    return f"{str(change[0]).casefold()}#{int(change[1])}#{change[2] or ''}"


def _reports(state: dict[str, Any]) -> dict[str, Any]:
    """Posted release reports by change, so a session's report for one change never overwrites
    another's; a single report recorded without its change is the bound change's."""
    reports = state.get("release_reports_posted")
    reports = dict(reports) if isinstance(reports, dict) else {}
    legacy = state.pop("release_report_posted", None)
    if isinstance(legacy, dict):
        ours = legacy.get("change")
        key = _report_key(ours) if isinstance(ours, list) and len(ours) == 3 else ""
        reports[key] = legacy
    state["release_reports_posted"] = reports
    return reports


def _keep_report(state: dict[str, Any], record: dict[str, Any]) -> None:
    _reports(state)[_report_key(record["change"])] = record


def _report_keys(state: dict[str, Any], binding: dict[str, Any]) -> list[str]:
    """This change's report keys: same repository and issue, and the same instalment when it
    was posted under one."""
    change = _change_of(binding)
    keys = [_report_key(change), _report_key([change[0], change[1], None])]
    return [key for key in dict.fromkeys(keys + [""]) if key in _reports(state)]


def _posted_report(state: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any] | None:
    keys = _report_keys(state, binding)
    return _reports(state)[keys[0]] if keys else None


def _drop_report(state: dict[str, Any], binding: dict[str, Any]) -> None:
    for key in _report_keys(state, binding):
        _reports(state).pop(key, None)


def _settle_report_post(state: dict[str, Any]) -> None:
    """A report posted in the background counts once its task output shows the comment."""
    pending = state.get("report_post_pending")
    if not isinstance(pending, dict):
        return
    text = _read_text(Path(str(pending.get("output_file"))), REPORT_LIMIT_BYTES)
    if text is not None and _comment_shown(text, int(pending.get("target") or 0)):
        record = {key: pending[key] for key in ("at", "pull_request", "head", "change")}
        _keep_report(state, record)
        state.pop("report_post_pending", None)


def _end_report_post(state: dict[str, Any], change: dict[str, Any],
                     binding: dict[str, Any]) -> None:
    """A posted release report holds until a reading after it shows a new head, or the entrance
    decides another stage; a same-head stage call never ends it (README "How it behaves")."""
    posted = _posted_report(state, binding)
    if posted is None:
        return
    at = posted.get("at")
    # A posted-report record with no post time is dated before every reading, so any
    # reading can end it by these same rules.
    at = at if isinstance(at, (int, float)) else 0.0
    for reading in (state.get("reading"), change.get("reading")):
        if not isinstance(reading, dict) or float(reading.get("read_at") or 0) <= float(at):
            continue
        # An entrance read is a decision even when cached without the flag.
        decided = reading.get("decision") is True or reading.get("source") == "entrance"
        head = reading.get("head")
        if (decided and reading.get("stage") != "release-report") or (
                isinstance(head, str) and isinstance(posted.get("head"), str)
                and not _same_head(head, posted["head"])):
            _drop_report(state, binding)
            return


def _unconfirmed(state: dict[str, Any], reading: Any, view: dict[str, Any]) -> bool:
    """The holder posted the step this reading shows as its own, and no reading since says otherwise.

    A `run` step is finished by a stage call, which the pane sees, so a post never
    marks one; at the release report only a body the pane couldn't read does,
    since a readable one either carries the title line or isn't the report.
    """
    posted = state.get("posted")
    if not isinstance(posted, dict) or not isinstance(reading, dict) or (
            view["waiting_on"] != "holder"):
        return False
    if reading.get("stage") == "release-report":
        at = posted.get("unreadable_at")
    elif str(view["next_step"]).startswith(("run ", "rerun ")):
        at = None
    else:
        at = posted.get("at")
    return isinstance(at, (int, float)) and float(reading.get("read_at") or 0) <= float(at)


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
            launched = pending.get("change")
            if isinstance(launched, list) and len(launched) == 3:
                _drop_report(state, {"repository": launched[0], "issue": launched[1],
                                     "instalment": launched[2]})
            else:
                _drop_report(state, binding)
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
    _settle_background(state, change, work)
    _settle_report_post(state)
    _end_report_post(state, change, binding)
    reading = _newer(state.get("reading"), change.get("reading"))
    failure = state.get("failure")
    if isinstance(failure, dict) and isinstance(reading, dict) and float(
            reading.get("read_at") or 0) > float(failure.get("at") or 0):
        state.pop("failure", None)
        failure = None
    read_open = change.get("read_open")
    killed_read = isinstance(read_open, (int, float)) and now - float(read_open) > READ_BUDGET_SECONDS
    view: dict[str, Any] = {
        "repository": binding["repository"], "issue": int(binding["issue"]),
        "stage": "", "status": "", "waiting_on": "unknown", "next_step": "no reading yet",
        "gate": "-", "floor": {"outcome": None, "satisfied": None}, "source": None,
        "read_at": None, "dispatch_id": None, "head": None, "running": None,
        "record_pending": False, "final": None, "posted": False,
        "read_failed_at": float(read_open) if killed_read else change.get("read_failed_at"),
        "failure": (f"{failure['stage']} failed {local_hhmm(float(failure['at']))}"
                    if isinstance(failure, dict) else None),
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
    running = live_running(ctx, bundles)
    background = state.get("background") if isinstance(state.get("background"), dict) else None
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
    elif view["final"] is None and _posted_report(state, binding) is not None:
        view.update({"stage": "release-report", "waiting_on": "owner", "next_step": "merge"})
    elif view["final"] is None and background is not None and not background.get("ended_at"):
        stage = str(background["stage"])
        started = float(background["started_at"])
        written = _mtime(background.get("redirect") or background.get("output_file"))
        view.update({"stage": stage, "status": "running", "waiting_on": "unknown",
                     "next_step": f"wait for the {stage} run", "dispatch_id": None,
                     "running": {"stage": stage, "elapsed": max(0.0, now - started),
                                 "deadline": None, "stalled": False, "dispatch_id": None,
                                 "quiet": max(0.0, now - max(started, written or started))}})
    elif view["final"] is None and background is not None:
        stage = str(background["stage"])
        view.update({"stage": stage, "status": "ended", "waiting_on": "unknown",
                     "next_step": f"{stage} ended; its report is read at the next read"})
    elif view["final"] is None and _unconfirmed(state, reading, view):
        view.update({"waiting_on": "unknown", "posted": True,
                     "next_step": f"{view['next_step']} (posted, unconfirmed)"})
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
    if title.get("records_missing"):
        return None, RENAME_OFF
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
    if title.get("steward"):
        forget_steward(ctx, session_id)
        return {"bound": False}
    view = compute_view(ctx, binding, state)
    rename, note = _rename_decision(view, title, state)
    if note is not None:
        state["rename_note"] = note
    elif state.get("rename_note", "").startswith(("rename skipped (title", "rename off")):
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

def _own_identity() -> dict[str, Any]:
    try:
        birth = _process_birth(os.getpid())
    except (OSError, ValueError, IndexError):
        birth = None
    return {"pid": os.getpid(), "host": socket.gethostname(), "birth": birth}


def _take_lock(ctx: Ctx, key: str) -> bool:
    """Exclusive per change. A lock is stale past the shim's kill, or once its owner is gone."""
    path = lock_path(ctx, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps({**_own_identity(), "started_at": ctx.now()}).encode("utf-8")
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
            owner_gone = isinstance(held, dict) and ctx.liveness(held) == "stopped"
            if ctx.now() - float(started) <= STALE_LOCK_SECONDS and not owner_gone:
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
        started_at = ctx.now()
        deadline = started_at + READ_BUDGET_SECONDS
        change["last_read_started"] = started_at
        # Recorded before any step the shim's timeout can kill: a read that never
        # returns still shows `read failed` once its budget has passed.
        change["read_open"] = started_at
        _write_json(change_path(ctx, key), change)
        argv = [sys.executable, str(entrance), "--repo", binding["repository"],
                "--issue", str(binding["issue"]), "--root", str(binding["root"])]
        if binding.get("instalment"):
            argv += ["--instalment", str(binding["instalment"])]
        decision = None
        try:
            completed = ctx.runner(argv, stdin=subprocess.DEVNULL, capture_output=True,
                                   timeout=min(ENTRANCE_TIMEOUT_SECONDS,
                                               max(1.0, deadline - ctx.now())))
            stdout = completed.stdout
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            decision = last_json_object(stdout or "")
        except (OSError, subprocess.SubprocessError):
            decision = None
        pr = lookup_pull_request(ctx, binding["repository"], int(binding["issue"]), deadline,
                                 marker_producers(binding.get("root")))
        change = load_change(ctx, key)
        if pr is not None:
            change["pull_request"] = pr
        if _is_decision(decision):
            # Stamped with the read's start: the state it reports was collected then,
            # so a stage return observed while it ran stays the newer reading.
            change["reading"] = reading_from_decision(decision, "entrance", started_at,
                                                      change.get("pull_request"))
            change.pop("read_failed_at", None)
        else:
            change["read_failed_at"] = ctx.now()
        change.pop("read_open", None)
        _write_json(change_path(ctx, key), change)
        return {"ran": True, "ok": _is_decision(decision)}
    finally:
        _remove(lock_path(ctx, key))


CLOSING_REFERENCE = re.compile(
    r"(?im)^\s*(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?)\s+#([1-9][0-9]*)\s*$"
)
IMPLEMENTING_PR_MARKER = re.compile(r"<!--\s*tradecraft:implementing-pr:v1\b[^>]*?\bnumber=([1-9][0-9]*)")


def _gh_json(ctx: Ctx, argv: list[str], deadline: float | None) -> Any:
    remaining = GH_TIMEOUT_SECONDS if deadline is None else min(GH_TIMEOUT_SECONDS,
                                                                deadline - ctx.now())
    if remaining < 1:
        return None
    try:
        completed = ctx.runner(argv, stdin=subprocess.DEVNULL, capture_output=True,
                               timeout=remaining)
        stdout = completed.stdout
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        return json.loads(stdout or "null")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def marker_producers(root: Any) -> frozenset[str]:
    """The logins `.tradecraft/work.json` trusts to write markers, read locally from the root.

    The entrance honours a marker only from these authors; a missing or
    unreadable file trusts no one, so every marker is ignored.
    """
    if not root:
        return frozenset()
    config = _read_json(Path(str(root)) / ".tradecraft" / "work.json")
    names = config.get("marker_producers") if isinstance(config, dict) else None
    if not isinstance(names, list):
        return frozenset()
    return frozenset(name.lower() for name in names if isinstance(name, str) and name)


def lookup_pull_request(ctx: Ctx, repository: str, issue: int,
                        deadline: float | None = None,
                        producers: frozenset[str] = frozenset()) -> dict[str, Any] | None:
    """The change's implementing PR, found as the entrance finds it, inside the floored read.

    The read-only report carries no PR number. One `gh pr list` finds PRs whose
    body closes the issue with the entrance's own whole-line CLOSING_REFERENCE.
    Only when none does, the issue's comments are read for an `implementing-pr`
    marker written by one of `producers`, and that PR's state is read (two more calls). An open PR wins, else
    the newest merged, else the newest closed. None when nothing is found.
    """
    rows = _gh_json(ctx, ["gh", "pr", "list", "--repo", repository, "--state", "all",
                          "--search", f"{issue} in:body", "--json",
                          "number,state,mergedAt,body", "--limit", "30"], deadline)
    rows = rows if isinstance(rows, list) else []
    found = [row for row in rows if isinstance(row, dict) and isinstance(row.get("number"), int)
             and any(int(match.group(1)) == issue
                     for match in CLOSING_REFERENCE.finditer(str(row.get("body") or "")))]
    if not found:
        pages = _gh_json(ctx, ["gh", "api", f"repos/{repository}/issues/{issue}/comments",
                               "--paginate", "--slurp"], deadline)
        texts = [str(comment.get("body") or "")
                 for page in (pages if isinstance(pages, list) else [])
                 for comment in (page if isinstance(page, list) else [])
                 if isinstance(comment, dict) and isinstance(comment.get("user"), dict)
                 and str(comment["user"].get("login") or "").lower() in producers]
        numbers = [int(match.group(1)) for text in texts
                   for match in IMPLEMENTING_PR_MARKER.finditer(text)]
        if numbers:
            known = {row.get("number"): row for row in rows if isinstance(row, dict)}
            row = known.get(numbers[-1]) or _gh_json(
                ctx, ["gh", "pr", "view", str(numbers[-1]), "--repo", repository, "--json",
                      "number,state,mergedAt"], deadline)
            if isinstance(row, dict) and isinstance(row.get("number"), int):
                found = [row]
    for wanted in ("OPEN", "MERGED", "CLOSED"):
        matches = sorted((row for row in found if str(row.get("state")).upper() == wanted),
                         key=lambda row: row["number"])
        if matches:
            row = matches[-1]
            return {"number": row["number"], "state": wanted,
                    "merged": wanted == "MERGED" or bool(row.get("mergedAt"))}
    return None


# --- the reminder (row 6) -----------------------------------------------------------

def _strings(value: Any) -> set[str]:
    """Every string in a JSON value, whole, so a task id is never found inside a longer one."""
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return set().union(*(_strings(item) for item in value)) if value else set()
    return set()


def remind(ctx: Ctx, payload: dict[str, Any]) -> dict[str, Any]:
    session_id = str(payload["session_id"])
    binding = load_binding(ctx, session_id)
    if binding is None:
        return {"block": None}
    if payload.get("stop_hook_active"):
        return {"block": None}
    state = load_session(ctx, session_id)
    background = state.get("background")
    tasks = payload.get("background_tasks")
    if isinstance(background, dict) and background.get("task_id") and tasks is not None \
            and not background.get("ended_at") \
            and str(background["task_id"]) not in _strings(tasks):
        # Stop's own list no longer names the task: it has ended.
        background["ended_at"] = ctx.now()
    view = compute_view(ctx, binding, state)
    if view["waiting_on"] != "holder" or view.get("running") or view.get("posted"):
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

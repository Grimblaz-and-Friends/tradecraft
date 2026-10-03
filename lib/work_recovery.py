"""Read stopped implementer evidence without crediting it as stage success."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import dispatch_record as records
import run_lifecycle as lifecycle


def _entrance():
    main = sys.modules.get("__main__")
    if Path(getattr(main, "__file__", "")).stem == "work":
        return main
    import work
    return work


def launches(state, stage):
    work = _entrance()
    term, _lane = work._affirmed_review(state)
    after = term.timestamp if stage == "artifact" and term else None
    return lifecycle.launch_bundles(
        state.record_root or records.default_record_root(),
        f"{state.repo}#{state.issue_number}",
        work.RESUME_SOURCE_STAGES.get(stage, {stage}), after=after,
    )


def latest_stopped(state, stage):
    rows = launches(state, stage)
    return rows[-1] if rows and lifecycle.stopped(rows[-1][3]) else None


def stopped_source(state, stage):
    work = _entrance()
    latest = latest_stopped(state, stage)
    if latest is None:
        return None
    order, path, request, run = latest
    try:
        session = lifecycle.recovery_session(request, run)
    except ValueError as exc:
        raise work.WorkError(f"stopped bundle {path}: {exc}") from exc
    if not work.SESSION_ID.fullmatch(session):
        raise work.WorkError(f"stopped bundle {path}: invalid session identity")
    root_value = request.get("root")
    if not isinstance(root_value, str) or not root_value:
        raise work.WorkError(f"stopped bundle {path}: missing recipient root")
    root = Path(root_value).resolve()
    if work._version_key(request.get("producer_version")) is None:
        raise work.WorkError(f"stopped bundle {path}: producer version is missing or invalid")
    if stage != "artifact":
        rows = work._change_rows(state.repo, state.issue_number, state.instalment, active_only=True)
        if len(rows) != 1:
            raise work.WorkError(f"stopped bundle {path}: expected one active implementation registration")
        holder = state.holder_root or Path(str(rows[0].get("holder_root") or ""))
        registered, branch = work._validate_implementation_row(rows[0], holder)
        if not work._same_path(root, registered) or request.get("lineage_branch") != branch:
            raise work.WorkError(f"stopped bundle {path}: registered root or branch mismatch")
    elif state.holder_root and not work._same_path(root, state.holder_root):
        rows = work._change_rows(state.repo, state.issue_number, state.instalment, active_only=True)
        if len(rows) != 1 or not work._same_path(root, Path(str(rows[0].get("root") or ""))):
            raise work.WorkError(f"stopped bundle {path}: artifact recipient root mismatch")
    current_pr = state.pr.get("number") if state.pr else None
    prior_pr = request.get("lineage_pull_request")
    if prior_pr is not None and prior_pr != current_pr:
        raise work.WorkError(f"stopped bundle {path}: implementing pull request mismatch")
    if state.pr and stage != "artifact":
        head = state.pr.get("head") or {}
        if request.get("lineage_branch") != head.get("ref"):
            raise work.WorkError(f"stopped bundle {path}: pull-request branch mismatch")
    return work.ResumeSource(order, path, request, run, session)


def info(state, source):
    request, run = source.request, source.run
    root = Path(request["root"])
    # For a hard stop the read-only current tree is the predecessor stop state.
    current = run.get("stop_snapshot")
    if not isinstance(current, dict):
        current = lifecycle.content_snapshot(root, timeout=lifecycle.probe_timeout())
    baseline = request.get("progress_baseline") or request.get("launch_snapshot")
    budget = lifecycle.runtime_account(launches(state, "build"), root=root,
                                       branch=request.get("lineage_branch"))
    return {"bundle": source.path, "session": source.session,
            "vendor": request["requested"]["vendor"], "continuity": "resume",
            "interruption": "ceiling" if run.get("interruption_cause") == "ceiling" else "unfinished or failed turn; cause unknown",
            "caller_limit_seconds": request.get("caller_limit_seconds"),
            "baseline_snapshot": baseline, "stop_snapshot": current,
            "progress": lifecycle.progress(baseline, current), "build_runtime": budget}


def recommend(state, recommendation):
    work = _entrance()
    if recommendation.stage not in {"artifact", "build", "floor", "review-disposition", "open-pull-request", "waiting", "ready-reviewers", "use", "proof"}:
        return recommendation
    stage = "artifact" if recommendation.stage == "artifact" else "build"
    latest = latest_stopped(state, stage)
    if latest is None:
        return recommendation
    selected_stage = str(latest[2]["stage"])
    try:
        source = stopped_source(state, stage)
        recovery = info(state, source)
    except (work.WorkError, OSError, TimeoutError) as exc:
        return work._reported_decision(state, work.Decision(
            selected_stage, False, None, "stopped-run-unresolved", str(exc), status="holder-owned"))
    reason = "stopped-run-resume"
    runnable = True
    if recovery["interruption"] == "ceiling" or not source.run.get("completed_at"):
        if recovery["progress"] != "changed" and stage != "artifact":
            reason, runnable = ("stopped-run-no-progress" if recovery["progress"] == "unchanged"
                                else "stopped-run-progress-unknown"), False
        elif selected_stage == "build" and (recovery["build_runtime"]["remaining_seconds"] is None
                                             or recovery["build_runtime"]["remaining_seconds"] <= 0):
            reason, runnable = "stopped-run-build-budget", False
    decision = work.Decision(selected_stage, runnable, "resume", reason,
                             json.dumps(recovery, ensure_ascii=True, sort_keys=True),
                             status="runnable" if runnable else "holder-owned")
    return work._reported_decision(state, decision)


def instruction(recovery, available):
    return (f"Previous run stopped. Resume session {recovery['session']} on {recovery['vendor']}. "
            f"Retained evidence: {recovery['bundle']}. Inspect the tree as it stands before continuing; "
            f"available recipient time is at most {available:g} seconds. Leave useful work in the tree "
            "if the window ends. Perform only the named stage and return to the holder.\n").encode("utf-8")

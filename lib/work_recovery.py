"""Read stopped implementer evidence without crediting it as stage success."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import dispatch_record as records
import run_lifecycle as lifecycle
import artifact_tree


def _entrance():
    main = sys.modules.get("__main__")
    if Path(getattr(main, "__file__", "")).stem == "work":
        return main
    import work
    return work


def launches(state, stage, *, include_released=False):
    work = _entrance()
    term, _lane = work._affirmed_review(state)
    after = term.timestamp if stage == "artifact" and term else None
    return scoped(state, lifecycle.launch_bundles(
        state.record_root or records.default_record_root(),
        f"{state.repo}#{state.issue_number}",
        work.RESUME_SOURCE_STAGES.get(stage, {stage}), after=after,
    ), include_released=include_released)


def scoped(state, rows, *, include_released=False):
    """Scope lineage; only a read-only delivery comparison includes released PR evidence."""
    work = _entrance()
    registrations = work._change_rows(state.repo, state.issue_number, None, active_only=False)
    selected = [r for r in registrations if
                (state.instalment is None or r.get("instalment") == state.instalment)
                and (not state.holder_root or work._same_path(
                    Path(str(r.get("holder_root") or "")), state.holder_root))]
    if include_released and state.pr:
        selected = [r for r in selected if r.get("branch") == (state.pr.get("head") or {}).get("ref")]
    def released(request):
        if request.get("stage") == "artifact":
            return False
        root, branch = request.get("root"), request.get("lineage_branch")
        if not isinstance(root, str) or not root:
            return False
        matches = [r for r in registrations if work._same_path(Path(root), Path(str(r.get("root") or "")))
                   and r.get("branch") == branch]
        return bool(matches) and not any(r.get("active") is True for r in matches)
    def relevant(request):
        if "instalment" in request and state.instalment is not None:
            if request["instalment"] != state.instalment:
                return False
        if request.get("stage") == "artifact" and isinstance(request.get("artifact_copy"), dict):
            holder = request["artifact_copy"].get("holder_root")
            # Only proved sibling provenance can exclude a newer attempt.
            if isinstance(holder, str) and state.holder_root and not work._same_path(Path(holder), state.holder_root):
                try:
                    output = Path(request["artifact_copy"]["lifecycle_record"])
                    bundle = str(output).removesuffix(".artifact-copy.json") + ".run.json"
                    artifact_tree.provenance(request, bundle)
                except (KeyError, artifact_tree.ArtifactTreeError):
                    return True
                return False
            return True
        root = request.get("root")
        branch = request.get("lineage_branch")
        if not isinstance(root, str) or not root:
            return True  # Missing evidence cannot hide behind an older success.
        own = [r for r in selected if work._same_path(Path(root), Path(str(r.get("root") or "")))
               and (request.get("stage") == "artifact" or r.get("branch") == branch)]
        if own or (request.get("stage") == "artifact" and state.holder_root
                   and work._same_path(Path(root), state.holder_root)):
            return True
        return not any(work._same_path(Path(root), Path(str(r.get("root") or "")))
                       and (request.get("stage") == "artifact" or r.get("branch") == branch)
                       for r in registrations)
    return [row for row in rows if (include_released or not released(row[2])) and (relevant(row[2])
            or str(row[3].get("recovery_error", "")).startswith("conflicting copied"))]


def restartable(request, run):
    """A holder can explicitly replace a dead fresh failure with no identity."""
    identity = run.get("session_identity") or {}
    requested = request.get("requested")
    if not isinstance(identity, dict) or not isinstance(requested, dict):
        return False
    observed = [a.get("observed", {}).get("session_id") for a in run.get("attempts", [])
                if isinstance(a, dict) and isinstance(a.get("observed"), dict)]
    return (requested.get("vendor") in {"codex", "claude"}
            and run.get("actual_vendor") == requested["vendor"]
            and bool(run.get("completed_at")) and run.get("lifecycle") == "completed" and run.get("outcome") == "error"
            and lifecycle.liveness(run) == "stopped" and not run.get("launch_unresolved")
            and run.get("cleanup_proven") is not False and not run.get("recovery_error")
            and not run.get("session_identity_error") and not request.get("handover")
            and not requested.get("session_id")
            and not identity.get("session_id") and not identity.get("reported_session_id")
            and not any(observed))


def handover_predecessor(state, latest):
    """Retain the reservation route when a failed handover reported no session."""
    _order, _path, request, run = latest
    carried = request.get("handover")
    work = _entrance()
    requested = request.get("requested")
    if not isinstance(requested, dict):
        return None
    observed = any(a.get("observed", {}).get("session_id") for a in run.get("attempts", [])
                   if isinstance(a, dict) and isinstance(a.get("observed"), dict))
    if (not isinstance(carried, dict) or observed or run.get("session_identity")
            or run.get("session_identity_error") or run.get("recovery_error")
            or run.get("cleanup_proven") is False or run.get("launch_unresolved")
            or requested.get("vendor") != "claude"
            or run.get("actual_vendor") != "claude"
            or work._version_key(request.get("producer_version")) is None
            or lifecycle.liveness(run) != "stopped"):
        return None
    for row in launches(state, request["stage"]):
        if row[1] == carried.get("from_bundle"):
            prior_root = row[2].get("root")
            prior_branch = row[2].get("lineage_branch")
            if request.get("stage") == "artifact":
                try:
                    copy = artifact_tree.provenance(request, latest[1])
                    prior_copy = artifact_tree.provenance(row[2], row[1])
                except artifact_tree.ArtifactTreeError:
                    return None
                prior_root = (prior_copy["handover_root"] if prior_copy else prior_root)
                current_root = copy["handover_root"] if copy else request.get("root")
            else:
                current_root = request.get("root")
            if (prior_root and (not isinstance(prior_root, str)
                               or not isinstance(current_root, str)
                               or not work._same_path(Path(prior_root), Path(current_root)))):
                return None
            if prior_branch and request.get("lineage_branch") != prior_branch:
                return None
            return row
    return None


def latest_stopped(state, stage):
    rows = launches(state, stage)
    return rows[-1] if rows and lifecycle.stopped(rows[-1][3]) else None


def stopped_source(state, stage):
    work = _entrance()
    latest = latest_stopped(state, stage)
    if latest is None:
        return None
    order, path, request, run = latest
    if handover_predecessor(state, latest) is not None:
        return None  # The existing reserved-session recovery route owns this failure.
    try:
        session = lifecycle.recovery_session(request, run)
    except ValueError as exc:
        raise work.WorkError(f"stopped bundle {path}: {exc}") from exc
    if not work.SESSION_ID.fullmatch(session):
        raise work.WorkError(f"stopped bundle {path}: invalid session identity")
    validate_target(state, stage, request, path)
    return work.ResumeSource(order, path, request, run, session)


def validate_target(state, stage, request, path, *, include_released=False):
    work = _entrance()
    root_value = request.get("root")
    if not isinstance(root_value, str) or not root_value:
        raise work.WorkError(f"stopped bundle {path}: missing recipient root")
    root = Path(root_value).resolve()
    if work._version_key(request.get("producer_version")) is None:
        raise work.WorkError(f"stopped bundle {path}: producer version is missing or invalid")
    if stage != "artifact":
        rows = work._change_rows(state.repo, state.issue_number, state.instalment, active_only=not include_released)
        if include_released:
            rows = [row for row in rows if work._same_path(root, Path(str(row.get("root") or "")))
                    and row.get("branch") == request.get("lineage_branch")]
        if len(rows) != 1:
            scope = "matching" if include_released else "active"
            raise work.WorkError(f"stopped bundle {path}: expected one {scope} implementation registration")
        holder = state.holder_root or Path(str(rows[0].get("holder_root") or ""))
        registered, branch = work._validate_implementation_row(rows[0], holder)
        if not work._same_path(root, registered) or request.get("lineage_branch") != branch:
            raise work.WorkError(f"stopped bundle {path}: registered root or branch mismatch")
    else:
        try:
            # Legacy roots are evidence only: execution makes a fresh committed copy.
            artifact_tree.validate_resume(request, {}, path, holder=state.holder_root,
                work=f"{state.repo}#{state.issue_number}", instalment=state.instalment)
        except artifact_tree.ArtifactTreeError as exc:
            raise work.WorkError(f"stopped bundle {path}: {exc}") from exc
    current_pr = state.pr.get("number") if state.pr else None
    prior_pr = request.get("lineage_pull_request")
    if prior_pr is not None and prior_pr != current_pr:
        raise work.WorkError(f"stopped bundle {path}: implementing pull request mismatch")
    if state.pr and stage != "artifact":
        head = state.pr.get("head") or {}
        if request.get("lineage_branch") != head.get("ref"):
            raise work.WorkError(f"stopped bundle {path}: pull-request branch mismatch")


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
            "stage_ceiling_seconds": request.get("stage_ceiling_seconds"),
            "recipient_allocation_seconds": request.get("recipient_allocation_seconds"),
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
        if source is None:
            reservation = latest[2]["handover"]
            return work._reported_decision(state, work.Decision(
                selected_stage, False, "resume", "stopped-handover-unresolved",
                f"Inspect the reserved Claude session; if it exists, run {selected_stage} "
                f"--handover-recovery-session {reservation['replacement_session']}; "
                f"retained stopped bundle {latest[1]}", status="holder-owned"))
        recovery = info(state, source)
    except (work.WorkError, OSError, TimeoutError) as exc:
        route = (f"; holder may run {selected_stage} --restart-unresolved-reason TEXT "
                 "to record an explicit fresh replacement in the registered tree"
                 if restartable(latest[2], latest[3]) else "")
        return work._reported_decision(state, work.Decision(
            selected_stage, False, None, "stopped-run-unresolved", str(exc) + route, status="holder-owned"))
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

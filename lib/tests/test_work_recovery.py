import json
from dataclasses import replace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_lifecycle as lifecycle
import work
import work_recovery as recovery
from test_work import state, repository, registry_row, git, dispatch_bundle, MECHANICAL, AFFIRMED, SESSION


@pytest.mark.parametrize("stage", ["artifact", "build", "floor", "use", "cold-seat"])
def test_unfinished_success_claim_cannot_supply_completed_stage_evidence(tmp_path, stage):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage=stage)
    path = store / stage / "result.md.run.json"
    before = path.read_bytes()
    assert len(work._matching_bundles("example/product#12", {stage}, store)) == 1
    unfinished = json.loads(before)
    unfinished.pop("completed_at")
    unfinished["lifecycle"] = "running"
    path.write_bytes(json.dumps(unfinished).encode())
    retained = path.read_bytes()
    assert work._matching_bundles("example/product#12", {stage}, store) == []
    assert path.read_bytes() == retained
    # Historical schema-2 completion needs no newly added lifecycle fields.
    path.write_bytes(before)
    assert len(work._matching_bundles("example/product#12", {stage}, store)) == 1


@pytest.fixture
def stopped_build(tmp_path, monkeypatch):
    original_snapshot = lifecycle.content_snapshot
    def snapshot(root, *, timeout=20):
        return original_snapshot(root, timeout=timeout if lifecycle.current_deadline() else max(timeout, 120))
    monkeypatch.setattr(lifecycle, "content_snapshot", snapshot)
    holder = repository(tmp_path, "holder")
    root = tmp_path / "builder"
    git(holder, "worktree", "add", "-b", "change", str(root))
    store = tmp_path / "dispatches"
    store.mkdir()
    baseline = lifecycle.content_snapshot(root)
    identity = lifecycle.process_identity()
    identity["birth"] += "dead"
    request = {"schema_version": 2, "dispatch_id": "stopped", "work": "example/product#12",
               "stage": "build", "producer_version": work.records.producer_version(),
               "root": str(root), "lineage_branch": "change", "lineage_pull_request": None,
               "launched_at": "2026-10-03T10:00:00+00:00", "caller_limit_seconds": 7200,
               "recipient_allocation_seconds": 7140, "launch_snapshot": baseline,
               "requested": {"vendor": "codex", "session_id": None, "continuity": "fresh"}}
    run = {"schema_version": 2, "dispatch_id": "stopped", "actual_vendor": "codex",
           "launcher_process": identity, "session_identity": {"session_id": SESSION},
           "elapsed_checkpoint_seconds": 20, "attempts": []}
    row = registry_row(root, holder, "change")
    monkeypatch.setattr(work, "read_registry", lambda: {"schema_version": 2, "worktrees": [row]})
    fixture = state(MECHANICAL)
    fixture.record_root, fixture.holder_root = store, holder
    def save():
        (store / "stopped.request.json").write_bytes(json.dumps(request).encode())
        (store / "stopped.run.json").write_bytes(json.dumps(run).encode())
    save()
    return fixture, root, request, run, save


@pytest.mark.parametrize("configuration", ["repository-session", "adopter"])
@pytest.mark.parametrize("has_pr", [False, True])
@pytest.mark.parametrize("stage", ["build", "floor", "review-disposition"])
def test_stopped_builder_keeps_identity_root_and_branch(stopped_build, stage, has_pr, configuration):
    fixture, root, request, run, save = stopped_build
    fixture.config = replace(fixture.config,
        product_repositories=frozenset({"example/consumer"}) if configuration == "repository-session" else frozenset())
    if has_pr:
        fixture.pr = {"number": 99, "head": {"ref": "change"}}
        request["lineage_pull_request"] = 99
    request["stage"] = stage
    (root / "fixture.txt").write_bytes(b"productive edit")
    save()
    source = recovery.stopped_source(fixture, stage)
    assert source.session == SESSION
    assert source.request["root"] == str(root)
    assert source.request["lineage_branch"] == "change"
    info = recovery.info(fixture, source)
    assert info["progress"] == "changed"
    assert info["vendor"] == "codex" and info["continuity"] == "resume"
    assert b"Previous run stopped" in recovery.instruction(info, 100)
    decision = recovery.recommend(fixture, work.Decision("build", True, "fresh", "pull-request-absent"))
    assert decision.dispatch and decision.continuity == "resume" and decision.stage == stage


@pytest.mark.parametrize("stage, elapsed, reason, launched", [
    ("build", 14400, None, False),
    ("build", None, None, False),
    ("build", 14400, "finish the remaining checks", True),
    ("build", 14000, None, True),
    ("floor", 20000, None, True),
])
def test_named_budget_guards_before_launch_and_excludes_repairs(stopped_build, monkeypatch,
                                                              stage, elapsed, reason, launched):
    import subprocess
    fixture, root, request, run, save = stopped_build
    request["stage"] = stage
    run.update(lifecycle="completed", completed_at="2026-10-03T11:00:00Z", outcome="interrupted",
               interruption_cause="ceiling", attempts=[{"launched": True, "elapsed_seconds": elapsed}])
    if elapsed is None:
        request.pop("recipient_allocation_seconds")
    save()
    commands, metadata = [], []
    original = subprocess.run
    def capture(command, *args, **kwargs):
        if len(command) > 1 and Path(command[1]).name == "dispatch_implementer.py":
            commands.append(command)
            metadata.append(json.loads(Path(command[command.index("--lifecycle-input") + 1]).read_bytes()))
            return subprocess.CompletedProcess(command, 0)
        return original(command, *args, **kwargs)
    monkeypatch.setattr(work.subprocess, "run", capture)
    monkeypatch.setattr(work, "_recipient_run", capture, raising=False)
    result = work.execute_stage(fixture, work.Decision(stage, True, "resume", "holder-named-stage"),
                                fixture.holder_root, None, "holder-session", codex_path=Path(sys.executable),
                                budget_override_reason=reason,
                                floor_command="python fixture-check.py" if stage == "floor" else None)
    assert result == 0
    assert bool(commands) is launched
    if launched:
        assert commands[0][commands[0].index("--resume") + 1] == SESSION
        assert metadata[0]["budget_override_reason"] == reason
        if stage == "floor":
            assert metadata[0]["budget_account_before"]["upper_seconds"] == 0
        elif elapsed == 14000:
            assert metadata[0]["budget_account_before"]["remaining_seconds"] == 400
            assert 0 < metadata[0]["recipient_allocation_seconds"] <= 400
        else:
            assert metadata[0]["budget_account_before"]["remaining_seconds"] == 0


@pytest.mark.parametrize("stage", ["build", "floor"])
def test_no_progress_handback_still_supplies_named_resume(stopped_build, stage):
    fixture, root, request, run, save = stopped_build
    request["stage"] = stage
    save()
    decision = recovery.recommend(fixture, work.Decision("build", True, "fresh", "pull-request-absent"))
    assert not decision.dispatch and decision.status == "holder-owned"
    assert decision.reason == "stopped-run-no-progress"
    assert recovery.stopped_source(fixture, stage).session == SESSION


@pytest.mark.parametrize("unfinished", [False, True])
@pytest.mark.parametrize("elapsed", [14000, 14400])
def test_second_look_866_further_stopped_build_after_merge_resumes_and_keeps_budget(
        stopped_build, monkeypatch, unfinished, elapsed):
    import subprocess
    fixture, root, request, run, save = stopped_build
    fixture.merged_pr = {"number": 7, "state": "closed", "merged_at": "2026-10-03T09:00:00Z"}
    (root / "fixture.txt").write_bytes(b"productive further build")
    run.update(lifecycle="completed", completed_at="2026-10-03T11:00:00Z", outcome="interrupted",
               interruption_cause="ceiling", attempts=[{"launched": True, "elapsed_seconds": elapsed}])
    if unfinished:
        run.pop("completed_at")
        run["elapsed_checkpoint_seconds"] = elapsed
        run["recipient_process"] = run["launcher_process"]
    save()
    recommendation = work.decide(fixture, {"schema_version": 1, "rules": []})
    assert work._named_continuity(fixture, "build", recommendation) == "resume"
    captured = []
    def launch(command, **_kwargs):
        metadata = json.loads(Path(command[command.index("--lifecycle-input") + 1]).read_bytes())
        assert command[command.index("--resume") + 1] == SESSION
        assert Path(command[command.index("--root") + 1]) == root
        assert metadata["budget_account_before"]["lower_seconds"] == elapsed
        assert 0 < metadata["recipient_allocation_seconds"] <= 400
        captured.append(command)
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(work, "_recipient_run", launch)
    monkeypatch.setattr(work, "create_implementation_root", lambda *_a: pytest.fail("replaced stopped tree"))
    assert work.execute_stage(fixture, work.Decision("build", True, "fresh", "holder-named-stage"),
                              fixture.holder_root, None, "holder-session", codex_path=Path(sys.executable)) == 0
    assert bool(captured) is (elapsed < 14400)


@pytest.mark.parametrize("elapsed", [14400, None])
def test_progress_does_not_hide_exhausted_or_unknown_build_budget(stopped_build, elapsed):
    fixture, root, request, run, save = stopped_build
    (root / "fixture.txt").write_bytes(b"productive edit")
    run.update(lifecycle="completed", completed_at="2026-10-03T11:00:00Z", outcome="interrupted",
               interruption_cause="ceiling", attempts=[{"launched": True, "elapsed_seconds": elapsed}])
    if elapsed is None:
        request.pop("recipient_allocation_seconds")
    save()
    recommendation = recovery.recommend(fixture, work.Decision("build", True, "fresh", "pull-request-absent"))
    assert not recommendation.dispatch and recommendation.status == "holder-owned"
    assert recommendation.reason == "stopped-run-build-budget"
    assert json.loads(recommendation.detail)["progress"] == "changed"


@pytest.mark.parametrize("configuration", ["repository-session", "adopter"])
def test_proved_dead_checkpoint_budget_reaches_entrance_recommendation(stopped_build, configuration):
    fixture, root, request, run, save = stopped_build
    fixture.config = replace(fixture.config,
        product_repositories=frozenset({"example/consumer"}) if configuration == "repository-session" else frozenset())
    run.update(elapsed_checkpoint_seconds=74.7, recipient_process=run["launcher_process"])
    request["recipient_allocation_seconds"] = 7134.7
    (root / "fixture.txt").write_bytes(b"productive edit")
    save()
    prior_request = {**request, "dispatch_id": "previous", "launched_at": "2026-10-03T09:00:00Z"}
    prior_run = {"schema_version": 2, "dispatch_id": "previous", "completed_at": "2026-10-03T09:59:00Z",
                 "outcome": "success", "attempts": [{"launched": True, "elapsed_seconds": 8000}]}
    (fixture.record_root / "previous.request.json").write_bytes(json.dumps(prior_request).encode())
    (fixture.record_root / "previous.run.json").write_bytes(json.dumps(prior_run).encode())
    decision = recovery.recommend(fixture, work.Decision("build", True, "fresh", "fixture"))
    assert decision.dispatch and decision.continuity == "resume"
    assert decision.reason == "stopped-run-resume"
    budget = json.loads(decision.detail)["build_runtime"]
    assert budget["lower_seconds"] == 8074.7
    assert budget["upper_seconds"] == pytest.approx(8084.95)
    assert budget["remaining_seconds"] == pytest.approx(6315.05)
    assert lifecycle.allocation(budget, 7140) == pytest.approx(6315.05)
    stopped = next(row for row in budget["runs"] if row["dispatch_id"] == "stopped")
    assert stopped["lower_basis"] == "last durable elapsed checkpoint"
    assert "both processes proved dead" in stopped["upper_basis"]


def test_artifact_stays_in_affirmed_term(stopped_build):
    fixture, root, request, run, save = stopped_build
    fixture.issue_comments[0]["body"] = AFFIRMED
    fixture.issue_comments[0]["created_at"] = "2026-10-03T09:00:00Z"
    request["stage"] = "artifact"
    request["root"] = str(fixture.holder_root)
    request["lineage_branch"] = None
    save()
    assert recovery.stopped_source(fixture, "artifact").session == SESSION
    fixture.issue_comments[0]["created_at"] = "2026-10-03T11:00:00Z"
    assert recovery.stopped_source(fixture, "artifact") is None


@pytest.mark.parametrize("problem", ["missing-session", "mismatch", "live", "unresolved", "root", "branch", "pr", "schema"])
def test_latest_unproved_run_refuses_another_writer(stopped_build, problem):
    fixture, root, request, run, save = stopped_build
    if problem == "missing-session":
        run.pop("session_identity")
    elif problem == "mismatch":
        run["session_identity_error"] = "reported session mismatch"
    elif problem == "live":
        run["launcher_process"] = lifecycle.process_identity()
    elif problem == "unresolved":
        run.pop("launcher_process")
    elif problem in {"root", "branch", "pr"}:
        key = {"root": "root", "branch": "lineage_branch", "pr": "lineage_pull_request"}[problem]
        request[key] = 99 if problem == "pr" else "different"
    else:
        run["schema_version"] = 1
    save()
    with pytest.raises(work.WorkError, match="stopped bundle"):
        recovery.stopped_source(fixture, "build")


@pytest.mark.parametrize("explicit_instalment", [False, True])
@pytest.mark.parametrize("mode", ["repository-session", "adopter"])
def test_sibling_stopped_attempt_cannot_replace_selected_instalment(stopped_build, monkeypatch, explicit_instalment, mode):
    fixture, root, request, run, save = stopped_build
    fixture.instalment = "B"
    fixture.config = replace(fixture.config, product_repositories=frozenset({"example/consumer"}) if mode == "repository-session" else frozenset())
    own = registry_row(root, fixture.holder_root, "change")
    own["instalment"] = "B"
    other_root = root.parent / "sibling"
    other = registry_row(other_root, fixture.holder_root, "sibling-change")
    other["instalment"] = "A"
    monkeypatch.setattr(work, "read_registry", lambda: {"schema_version": 2, "worktrees": [other, own]})
    sibling = {**request, "dispatch_id": "sibling", "root": str(other_root),
               "lineage_branch": "sibling-change", "launched_at": "2026-10-03T12:00:00Z"}
    if explicit_instalment:
        sibling["instalment"] = "A"
    (fixture.record_root / "sibling.request.json").write_bytes(json.dumps(sibling).encode())
    (fixture.record_root / "sibling.run.json").write_bytes(json.dumps({
        "schema_version": 2, "dispatch_id": "sibling", "launcher_process": lifecycle.process_identity()}).encode())
    source = recovery.stopped_source(fixture, "floor")
    assert source.session == SESSION and source.request["root"] == str(root)
    selected = work._resume_source("example/product#12", "floor", fixture.record_root, state=fixture)
    assert selected == source


def test_dead_unidentified_failure_has_an_explicit_recorded_restart(stopped_build, monkeypatch):
    import subprocess
    fixture, root, request, run, save = stopped_build
    run.pop("session_identity")
    request["budget_lineage"] = "original-budget"
    run.update(lifecycle="completed", completed_at="2026-10-03T11:00:00Z", outcome="error",
               attempts=[{"launched": True, "elapsed_seconds": 3}])
    save()
    recommendation = recovery.recommend(fixture, work.Decision("build", True, "fresh", "fixture"))
    assert not recommendation.dispatch and "--restart-unresolved-reason" in recommendation.detail
    commands, metadata = [], []
    monkeypatch.setattr(work, "_dispatch_root", lambda *_a, **_k: (root, "change", False))
    original = subprocess.run
    def capture(command, *args, **kwargs):
        if len(command) > 1 and Path(command[1]).name == "dispatch_implementer.py":
            commands.append(command)
            metadata.append(json.loads(Path(command[command.index("--lifecycle-input") + 1]).read_bytes()))
            return subprocess.CompletedProcess(command, 0)
        return original(command, *args, **kwargs)
    monkeypatch.setattr(work.subprocess, "run", capture)
    monkeypatch.setattr(work, "_recipient_run", capture, raising=False)
    decision = work.Decision("build", True, "resume", "holder-named-stage")
    assert work.execute_stage(fixture, decision, fixture.holder_root, None, "holder-session",
        codex_path=Path(sys.executable), restart_unresolved_reason="verified no saved session") == 0
    assert len(commands) == 1 and "--resume" not in commands[0]
    assert metadata[0]["recovery_restart_reason"] == "verified no saved session"
    assert metadata[0]["budget_lineage"] == "original-budget"
    assert metadata[0]["budget_account_before"]["upper_seconds"] == 3


@pytest.mark.parametrize("problem", ["live", "uncertain", "identity", "cleanup", "unfinished"])
def test_restart_cannot_replace_unproved_or_existing_session(stopped_build, problem):
    fixture, root, request, run, save = stopped_build
    run.pop("session_identity")
    run.update(lifecycle="completed", completed_at="2026-10-03T11:00:00Z", outcome="error",
               attempts=[{"launched": True, "elapsed_seconds": 3}])
    if problem == "live":
        run["launcher_process"] = lifecycle.process_identity()
    elif problem == "uncertain":
        run.pop("launcher_process")
    elif problem == "identity":
        run["session_identity"] = {"session_id": SESSION}
    elif problem == "cleanup":
        run["cleanup_proven"] = False
    else:
        run.pop("completed_at")
    save()
    with pytest.raises(work.WorkError, match="restart requires"):
        work.execute_stage(fixture, work.Decision("build", True, "resume", "holder-named-stage"),
            fixture.holder_root, None, "holder-session", restart_unresolved_reason="replace")


@pytest.mark.parametrize("completed", [False, True])
def test_unproved_descendant_cleanup_cannot_supply_resume(stopped_build, completed):
    fixture, root, request, run, save = stopped_build
    run["cleanup_proven"] = False
    if completed:
        run.update(lifecycle="completed", completed_at="2026-10-03T11:00:00Z", outcome="interrupted",
                   attempts=[{"launched": True, "elapsed_seconds": 20}])
    save()
    with pytest.raises(work.WorkError, match="descendant cleanup is unproved"):
        recovery.stopped_source(fixture, "build")


@pytest.mark.parametrize("origin", [-100, 0, 1, 100])
def test_entrance_wait_includes_child_recording_but_reserves_its_own_return(monkeypatch, origin):
    import subprocess
    monkeypatch.setattr(lifecycle.time, "monotonic", lambda: origin)
    deadline = lifecycle.Deadline(30, started=origin)
    monkeypatch.setattr(lifecycle.time, "monotonic", lambda: origin + 3)
    calls = []
    def capture(command, **kwargs):
        calls.append(kwargs)
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(work, "_recipient_run", capture, raising=False)
    # The old unbounded route returns without calling the contained recipient seam.
    monkeypatch.setattr(work.subprocess, "run", capture)
    assert work._invoke_recipient(["launcher"], deadline) == 0
    assert calls[0]["timeout"] == 24.5
    assert calls[0]["cleanup_deadline"] == origin + 28.75
    assert calls[0]["timeout"] > deadline.remaining()


def test_entrance_stops_a_stuck_launcher_and_its_descendant_before_caller_limit(tmp_path, monkeypatch, record_property):
    import subprocess
    import time
    child_pid = tmp_path / "child-pid"
    child_code = ("import json,sys,time; from pathlib import Path; "
                  f"sys.path.insert(0,{str(Path(__file__).resolve().parents[1])!r}); "
                  "import run_lifecycle as lifecycle; "
                  f"pending=Path({str(child_pid.with_suffix('.pending'))!r}); "
                  "pending.write_bytes(json.dumps(lifecycle.process_identity()).encode()); "
                  f"pending.replace({str(child_pid)!r}); "
                  "time.sleep(60)")
    code = ("import pathlib, subprocess, sys, time; "
            f"child=subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
            "print('launcher blocked', flush=True); time.sleep(60)")
    started = time.monotonic()
    deadline = lifecycle.Deadline(15, started=started)
    original = work._recipient_run
    def short_trigger(command, *, timeout, cleanup_deadline):
        # The adjacent allocation test proves the entrance's deadline math.
        # Exercise its real tree cancellation here with a two-second trigger.
        assert 0 < timeout < 15
        return original(command, timeout=min(timeout, 2), cleanup_deadline=cleanup_deadline)
    monkeypatch.setattr(work, "_recipient_run", short_trigger)
    with pytest.raises(work.WorkError, match="bounded recording allowance"):
        work._invoke_recipient([sys._base_executable, "-c", code], deadline)
    elapsed = time.monotonic() - started
    record_property("entrance_elapsed_seconds", elapsed)
    print(f"entrance exit {elapsed:.3f}s / 15s")
    assert elapsed < 15
    assert child_pid.is_file()
    identity = json.loads(child_pid.read_bytes())
    until = started + 5  # Bounded death observation, not a survival sleep.
    while lifecycle.liveness({"launcher_process": identity}) != "stopped" and time.monotonic() < until:
        time.sleep(0.01)
    assert lifecycle.liveness({"launcher_process": identity}) == "stopped"



def test_completed_cleanup_proves_death_after_a_short_lived_process(stopped_build):
    fixture, root, request, run, save = stopped_build
    run.pop("session_identity")
    run.update(lifecycle="completed", completed_at="2026-10-03T11:00:00Z", outcome="error",
               cleanup_proven=True, recipient_process={"pid": 42, "unavailable_reason": "exited before identity read"},
               attempts=[{"launched": True, "elapsed_seconds": 3}])
    save()
    assert recovery.restartable(request, run)
    run["cleanup_proven"] = False
    assert not recovery.restartable(request, run)


def test_sibling_copy_conflict_cannot_hide_selected_dispatch(stopped_build, monkeypatch):
    fixture, root, request, run, save = stopped_build
    fixture.instalment = "B"
    sibling = {**request, "instalment": "A"}
    row = ("2026-10-03T12:00:00Z", "conflicted.run.json", sibling,
           {**run, "recovery_error": "conflicting copied requests"})
    monkeypatch.setattr(lifecycle, "launch_bundles", lambda *_a, **_k: [row])
    decision = recovery.recommend(fixture, work.Decision("build", True, "fresh", "fixture"))
    assert not decision.dispatch and "conflicting copied requests" in decision.detail
    row[3].pop("recovery_error")
    assert recovery.latest_stopped(fixture, "build") is None

import json
from dataclasses import replace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_lifecycle as lifecycle
import work
import work_recovery as recovery
from test_work import state, repository, registry_row, git, MECHANICAL, AFFIRMED, SESSION


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
    result = work.execute_stage(fixture, work.Decision(stage, True, "resume", "holder-named-stage"),
                                fixture.holder_root, None, "holder-session", codex_path=Path(sys.executable),
                                budget_override_reason=reason)
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

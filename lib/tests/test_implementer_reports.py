"""The entrance retains failed/latest/historical evidence in its normal scope."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest

import implementer_environment as environment
import work


def bundle(store, name, *, stage="build", root="/implementation", branch="tradecraft/886-impl",
           instalment=None, outcome="success", env=None, work_id="owner/repo#886"):
    request = {"schema_version": 2, "dispatch_id": name, "work": work_id, "stage": stage,
        "root": root, "lineage_branch": branch, "instalment": instalment,
        "launched_at": "2026-10-10T10:00:00+00:00"}
    run = {"schema_version": 2, "dispatch_id": name, "actual_vendor": "codex",
        "lifecycle": "completed", "completed_at": "2026-10-10T10:01:00+00:00", "outcome": outcome,
        "attempts": [{"vendor": "codex", "outcome": outcome, **({"environment": env} if env else {})}]}
    path = store / (name + ".request.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(request).encode())
    path.with_name(name + ".run.json").write_bytes(json.dumps(run).encode())
    return path


@pytest.mark.parametrize("stage", ["artifact", "build", "floor", "review-disposition"])
@pytest.mark.parametrize("outcome", ["success", "error", "interrupted", "completed_no_output"])
def test_reports_all_builder_stages_outcomes_and_actual_excess(tmp_path, monkeypatch, stage, outcome):
    observed = environment.unknown("missing", vendor="codex")
    observed["excess"] = [{"category": "plugins", "identity": "foreign@market"}]
    bundle(tmp_path, "current", stage=stage, outcome=outcome, env=observed)
    bundle(tmp_path, "seat", stage="cold-seat", env=observed)
    bundle(tmp_path, "foreign", work_id="other/repo#886", env=observed)
    state = work.WorkState("owner/repo", 886, {}, record_root=tmp_path)
    monkeypatch.setattr(work, "_change_rows", lambda *_a, **_k: [])
    result = work._implementer_environments(state)
    assert [v["dispatch_id"] for v in result["attempts"]] == ["current"]
    assert result["attempts"][0]["outcome"] == outcome
    assert result["attempts"][0]["environment"]["excess"][0]["identity"] == "foreign@market"


def test_history_missing_and_malformed_latest_remain_visible_without_rewrite(tmp_path, monkeypatch):
    historical = bundle(tmp_path, "old")
    before = {p: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    latest = bundle(tmp_path, "latest", outcome="error")
    latest.with_name("latest.run.json").write_bytes(b"malformed")
    state = work.WorkState("owner/repo", 886, {}, record_root=tmp_path)
    monkeypatch.setattr(work, "_change_rows", lambda *_a, **_k: [])
    result = work._implementer_environments(state)
    assert {v["dispatch_id"] for v in result["attempts"]} == {"old", "latest"}
    assert next(v for v in result["attempts"] if v["dispatch_id"] == "latest")["record_error"]
    assert all(v["environment"]["categories"]["plugins"]["status"] == "unknown" for v in result["attempts"])
    assert {p: p.read_bytes() for p in before} == before


def test_scope_keeps_relevant_released_lineage_and_excludes_sibling_instalment(tmp_path, monkeypatch):
    holder, sibling = tmp_path / "holder", tmp_path / "sibling"
    own, other = tmp_path / "own", tmp_path / "other"
    registrations = [{"holder_root": str(holder), "root": str(own), "branch": "tradecraft/886-impl", "instalment": "a", "active": False},
        {"holder_root": str(sibling), "root": str(other), "branch": "tradecraft/886-other", "instalment": "b", "active": True}]
    bundle(tmp_path / "records", "own", root=str(own), instalment="a")
    bundle(tmp_path / "records", "sibling", root=str(other), branch="tradecraft/886-other", instalment="b")
    state = work.WorkState("owner/repo", 886, {}, record_root=tmp_path / "records",
        holder_root=holder, instalment="a", pr={"head": {"ref": "tradecraft/886-impl"}})
    monkeypatch.setattr(work, "_change_rows", lambda *_a, **_k: registrations)
    assert [v["dispatch_id"] for v in work._implementer_environments(state)["attempts"]] == ["own"]


def test_copied_bundles_are_deduplicated_and_conflicts_not_cleaned(tmp_path, monkeypatch):
    import shutil
    bundle(tmp_path / "a", "current")
    shutil.copytree(tmp_path / "a", tmp_path / "b")
    state = work.WorkState("owner/repo", 886, {}, record_root=tmp_path)
    monkeypatch.setattr(work, "_change_rows", lambda *_a, **_k: [])
    assert len(work._implementer_environments(state)["attempts"]) == 1
    path = tmp_path / "b/current.run.json"
    value = json.loads(path.read_bytes())
    value["outcome"] = "error"
    path.write_bytes(json.dumps(value).encode())
    result = work._implementer_environments(state)
    assert len(result["attempts"]) == 1
    assert result["attempts"][0]["record_error"] == "conflicting copied completions"


def test_malformed_environment_cannot_certify_clean_inventory(tmp_path, monkeypatch):
    bundle(tmp_path, "malformed", env={"schema_version": 1, "categories": {"plugins": {"status": "known", "values": []}}})
    state = work.WorkState("owner/repo", 886, {}, record_root=tmp_path)
    monkeypatch.setattr(work, "_change_rows", lambda *_a, **_k: [])
    observed = work._implementer_environments(state)["attempts"][0]["environment"]
    assert observed["categories"]["plugins"]["status"] == "unknown"
    assert observed["categories"]["plugins"]["reason"] == "malformed observed launch environment"


@pytest.mark.parametrize("sources", [None, [], [{}], [{"path": "stdout", "line": True, "field": "plugins"}]])
def test_complete_record_without_runtime_coordinates_cannot_certify_empty(tmp_path, monkeypatch, sources):
    observed = environment.unknown("not reported", vendor="claude")
    observed["categories"]["plugins"] = {"status": "known", "values": [], "reason": None, "sources": sources}
    bundle(tmp_path, "damaged", env=observed)
    state = work.WorkState("owner/repo", 886, {}, record_root=tmp_path)
    monkeypatch.setattr(work, "_change_rows", lambda *_a, **_k: [])
    reported = work._implementer_environments(state)["attempts"][0]["environment"]
    assert reported["categories"]["plugins"]["status"] == "unknown"
    assert reported["categories"]["plugins"]["reason"] == "malformed observed launch environment"


def test_explicit_empty_inventory_with_runtime_coordinates_remains_known(tmp_path, monkeypatch):
    observed = environment.unknown("not reported", vendor="claude")
    observed["categories"]["plugins"] = environment.category("known", [], None,
        environment.coordinate("native.stdout", 2, "plugins"))
    bundle(tmp_path, "complete", env=observed)
    state = work.WorkState("owner/repo", 886, {}, record_root=tmp_path)
    monkeypatch.setattr(work, "_change_rows", lambda *_a, **_k: [])
    reported = work._implementer_environments(state)["attempts"][0]["environment"]
    assert reported["categories"]["plugins"]["status"] == "known"
    assert reported["categories"]["plugins"]["values"] == []


def test_damaged_memory_category_preserves_valid_plugin_excess_and_record_bytes(tmp_path, monkeypatch):
    observed = environment.unknown("not reported", vendor="claude")
    environment.claude_init(observed, {"type": "system", "subtype": "init",
        "plugins": [{"name": "foreign@market"}]}, path="native.stdout", line=1)
    observed["categories"]["memory"] = {"status": "known", "values": [], "sources": []}
    request = bundle(tmp_path, "current", env=observed)
    run = request.with_name("current.run.json")
    before = run.read_bytes()
    state = work.WorkState("owner/repo", 886, {}, record_root=tmp_path)
    monkeypatch.setattr(work, "_change_rows", lambda *_a, **_k: [])
    attempt = work._implementer_environments(state)["attempts"][0]
    assert attempt["outcome"] == "success"
    assert attempt["environment"]["categories"]["memory"]["status"] == "unknown"
    assert attempt["environment"]["categories"]["plugins"]["status"] == "known"
    assert attempt["environment"]["excess"][0]["identity"] == "foreign@market"
    assert run.read_bytes() == before


def test_partial_positive_inventory_without_source_stays_unknown(tmp_path, monkeypatch):
    observed = environment.unknown("not reported", vendor="claude")
    observed["categories"]["plugins"] = environment.category("partial", ["foreign@market"], "partial catalog")
    bundle(tmp_path, "damaged", env=observed)
    state = work.WorkState("owner/repo", 886, {}, record_root=tmp_path)
    monkeypatch.setattr(work, "_change_rows", lambda *_a, **_k: [])
    reported = work._implementer_environments(state)["attempts"][0]["environment"]
    assert reported["categories"]["plugins"]["status"] == "unknown"


@pytest.mark.parametrize("stage", ["artifact", "build", "floor", "review-disposition"])
def test_report_shows_each_claude_instruction_file_and_history_reads_unknown(tmp_path, monkeypatch, stage):
    observed = environment.unknown("not reported", vendor="claude")
    session = "f0cb89b1-e040-4e6e-919b-4b4e58c717d2"
    native = tmp_path / "projects" / "slug" / f"{session}.jsonl"
    native.parent.mkdir(parents=True)
    native.write_bytes((json.dumps({"type": "attachment", "sessionId": session, "attachment": {
        "type": "instructions", "files": [
            {"path": "/tree/AGENTS.md", "type": "Project", "content": "rules"},
            {"path": "/tree/.git/tradecraft-instructions-1/CLAUDE.md", "type": "Project",
             "content": "@../../AGENTS.md"}]}}) + "\n").encode())
    environment.claude_instructions(observed, projects=tmp_path / "projects", session=session, offset=0,
        resumed=False, shim="/tree/.git/tradecraft-instructions-1")
    bundle(tmp_path / "records", "current", stage=stage, env=observed)
    historical = bundle(tmp_path / "records", "historical", stage=stage)
    before = historical.with_name("historical.run.json").read_bytes()
    state = work.WorkState("owner/repo", 886, {}, record_root=tmp_path / "records")
    monkeypatch.setattr(work, "_change_rows", lambda *_a, **_k: [])
    attempts = {v["dispatch_id"]: v for v in work._implementer_environments(state)["attempts"]}
    assert attempts["current"]["instructions"] == {"status": "known", "reason": None, "files": [
        {"path": "/tree/AGENTS.md", "runtime_type": "Project",
         "sha256": hashlib.sha256(b"rules").hexdigest(), "delivered": "this-invocation", "launcher_shim": False},
        {"path": "/tree/.git/tradecraft-instructions-1/CLAUDE.md", "runtime_type": "Project",
         "sha256": hashlib.sha256(b"@../../AGENTS.md").hexdigest(), "delivered": "this-invocation",
         "launcher_shim": True}]}
    assert attempts["historical"]["instructions"]["status"] == "unknown"
    assert attempts["historical"]["instructions"]["files"] == []
    assert historical.with_name("historical.run.json").read_bytes() == before


def test_887_R4_2_report_names_launch_controls_and_stream_check(tmp_path, monkeypatch):
    import dispatch_lifecycle as lifecycle
    from test_launch_controls import daemon_face
    notice = lifecycle.claude_launch_notice(900)
    controls = lifecycle.claude_launch_controls(900, notice, disallowed=lifecycle.CLAUDE_DISALLOWED_TOOLS)
    check = lifecycle.stream_check_record(lifecycle.claude_stream_check(daemon_face()))
    for name, protected in (("protected", True), ("older", False)):
        path = bundle(tmp_path, name, outcome="work_outlived_return" if protected else "success")
        request = json.loads(path.read_bytes())
        request["requested"] = {"vendor": "claude"}
        if protected:
            request["launch_controls"] = controls
        path.write_bytes(json.dumps(request).encode())
        run_path = path.with_name(name + ".run.json")
        run = json.loads(run_path.read_bytes())
        run["actual_vendor"] = "claude"
        run["attempts"][0]["vendor"] = "claude"
        if protected:
            run["attempts"][0]["stream_check"] = check
        before = json.dumps(run).encode()
        run_path.write_bytes(before)
    bundle(tmp_path, "codex")
    state = work.WorkState("owner/repo", 886, {}, record_root=tmp_path)
    monkeypatch.setattr(work, "_change_rows", lambda *_a, **_k: [])
    rows = {v["dispatch_id"]: v for v in work._implementer_environments(state)["attempts"]}
    protected = rows["protected"]
    assert protected["outcome"] == "work_outlived_return"
    assert protected["launch_controls"] == {"status": "recorded", "background_tasks": "disabled",
        "background_tasks_source": "child process environment CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1",
        "command_ceiling_ms": 900000, "command_ceiling_source": "child process environment BASH_MAX_TIMEOUT_MS",
        "disallowed_tools": ["Monitor", "ScheduleWakeup", "CronCreate", "Workflow"],
        "notice_sha256": hashlib.sha256(notice).hexdigest()}
    assert protected["stream_check"]["status"] == "work_outlived_return"
    assert protected["stream_check"]["return_line"] == 6
    assert {c["kind"] for c in protected["stream_check"]["causes"]} == {
        "task_event_after_return", "task_running_at_return"}
    assert rows["older"]["launch_controls"] == {"status": "not recorded: launched before #887"}
    assert rows["older"]["stream_check"] == {"status": "not recorded: launched before #887"}
    assert run_path.read_bytes() == before
    assert rows["codex"]["launch_controls"] is None and rows["codex"]["stream_check"] is None

"""Public artifact entrance acceptance checks (A1, A3-A5)."""
import base64
import json
import stat
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import artifact_tree as trees
import dispatch_implementer as implementer
import run_lifecycle as lifecycle
import work
from test_work import CONFIG, POLICY_PATH, PRODUCER, git, policy_repository, registry_row, repository
from test_dispatch_implementer import ARTIFACT_BRIEF, artifact_text, native_artifact_result

SESSION = "0199a213-81c0-7800-8aa1-bbab2a035a53"


class ArtifactTransport:
    def get(self, endpoint, *, paginate=False):
        if endpoint.endswith("/comments"):
            return [{"id": 751, "body": ARTIFACT_BRIEF,
                     "created_at": "2026-09-19T00:00:00Z",
                     "html_url": "https://github.example/issue#issuecomment-751",
                     "user": {"login": PRODUCER}}]
        if "/pulls?" in endpoint:
            return []
        return {"number": 12, "state": "open", "body": "", "labels": [],
                "user": {"login": PRODUCER}}


@pytest.fixture
def entrance(tmp_path, monkeypatch):
    holder = policy_repository(tmp_path, "holder")
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.setattr(work, "load_work_config", lambda *_a: CONFIG)
    store, scenario = tmp_path / "dispatches", tmp_path / "scenario.json"
    monkeypatch.setattr(work.records, "default_record_root", lambda: store)
    monkeypatch.setattr(work, "_selected_runtime_argument", lambda *_a: [])
    monkeypatch.setattr(implementer.records, "runtime_version", lambda *_a: "fixture runtime")
    commands = []
    def launch(command, **_kwargs):
        commands.append(command)
        status = implementer.run_implementer(implementer.parser().parse_args(command[2:]))
        return subprocess.CompletedProcess(command, status)
    monkeypatch.setattr(work, "_recipient_run", launch)
    def setup(vendor, custom=False, returned=None, *, fail=None, probe=False, identity=SESSION):
        setting = Path.home() / ".tradecraft/implementer-vendor"
        setting.parent.mkdir(parents=True, exist_ok=True)
        setting.write_bytes(vendor.encode())
        capture = tmp_path / ("capture-" + str(len(commands)) + ".json")
        native = native_artifact_result(vendor, artifact_text("combined") if returned is None else returned, identity)
        native.update(author_writes=True, capture_path=str(capture), resume_probe_only=probe)
        if fail == "runtime":
            native["exit"] = 1
            native["stdout"] = (json.dumps({"type": "thread.started", "thread_id": SESSION}) + "\n" +
                json.dumps({"type": "turn.failed"})) if vendor == "codex" else json.dumps(
                    {"type": "result", "is_error": True, "session_id": SESSION, "result": "failed"})
        scenario.write_bytes(json.dumps({vendor: native}).encode())
        monkeypatch.setattr(implementer, "resolve_command", lambda *_a: [
            sys.executable, str(Path(__file__).parent / "seat_cli.py"), vendor, str(scenario)])
        dispatch = tmp_path / "holder-dispatch.md"
        dispatch.write_bytes(b"Exact holder dispatch.\r\nReturn full artifact.\r\n")
        args = work.parser().parse_args(["run", "artifact", "--repo", "example/product", "--issue", "12",
            "--root", str(holder), "--holder-session-id", "holder",
            *(["--dispatch", str(dispatch)] if custom else [])])
        return args, capture, dispatch
    yield holder, store, commands, setup
    # Only allocations positively attributed by this fixture are cleanup targets.
    for record_path in store.rglob("*.artifact-copy.json"):
        copy = trees._read(record_path)["artifact_copy"]
        if Path(copy["root"]).exists():
            trees.dispose(copy)


def bundles(store):
    return sorted(lifecycle.launch_bundles(store, "example/product#12", {"artifact"}))


def snapshot(root):
    return {"content": lifecycle.content_snapshot(root), "refs": git(root, "show-ref").stdout,
            "index": git(root, "ls-files", "--stage").stdout}


def test_public_partial_clone_fetch_failure_names_cause_and_writes_no_author_bundle(
        entrance, capsys):
    origin, store, commands, setup = entrance
    (origin / "payload.bin").write_bytes(b"captured blob remains missing\n")
    git(origin, "add", "payload.bin")
    git(origin, "-c", "user.name=f", "-c", "user.email=f@x", "commit", "-m", "payload")
    remote = store.parent / "promisor.git"
    git(origin, "clone", "--bare", str(origin), str(remote))
    git(remote, "config", "uploadpack.allowFilter", "true")
    holder = store.parent / "partial-holder"
    git(origin, "clone", "--filter=blob:none", "--no-checkout", remote.as_uri(), str(holder))
    # Preflight reads policy files; leave the partial object database untouched.
    for relative in (POLICY_PATH, ".tradecraft/work.json"):
        path = holder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((origin / relative).read_bytes())
    assert b"?" in git(holder, "rev-list", "--objects", "--missing=print", "HEAD").stdout
    git(holder, "remote", "set-url", "origin", (store.parent / "absent-promisor.git").as_uri())
    args, _, _ = setup("codex", probe=True)
    args.root = holder
    with pytest.raises(work.WorkError, match="missing blobs.*promisor"):
        work.run(args, transport=ArtifactTransport())
    assert not commands and not bundles(store)
    assert not list(store.rglob("*.request.json"))
    records = list(store.rglob("*.artifact-copy.json"))
    assert len(records) == 1 and trees._read(records[0])["state"] == "removed"
    assert "artifact-copy:" in capsys.readouterr().out


@pytest.mark.parametrize("vendor", ["codex", "claude"])
def test_public_lfs_pointer_policy_and_count_are_reported(entrance, monkeypatch, capsys, vendor):
    holder, store, commands, setup = entrance
    pointer = b"version https://git-lfs.github.com/spec/v1\noid sha256:" + b"0" * 64 + b"\nsize 123\n"
    (holder / ".gitattributes").write_bytes(b"*.bin filter=lfs -text\n")
    (holder / "asset.bin").write_bytes(pointer)
    git(holder, "-c", "filter.lfs.clean=", "-c", "filter.lfs.required=false", "add", ".")
    git(holder, "-c", "user.name=f", "-c", "user.email=f@x", "commit", "-m", "pointer")
    config = store.parent / "lfs-global.config"
    config.write_text('[filter "lfs"]\n    smudge = missing-tradecraft-lfs-runtime\n'
                      '    process =\n    required = true\n', encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    original = work._recipient_run
    def inspect(command, **kwargs):
        root = Path(command[command.index("--root") + 1])
        assert (root / "asset.bin").read_bytes() == pointer
        assert trees.git(root, "remote") == ""
        return original(command, **kwargs)
    monkeypatch.setattr(work, "_recipient_run", inspect)
    before = snapshot(holder)
    args, capture, _ = setup(vendor, probe=True)
    assert work.run(args, transport=ArtifactTransport()) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if line.startswith("work: launch_settings "))
    plan = json.loads(line.removeprefix("work: launch_settings "))
    assert plan["artifact_copy"]["lfs_mode"] == "pointers"
    assert plan["artifact_copy"]["lfs_pointer_count"] == 1
    request = bundles(store)[-1][2]
    assert trees._read(request["artifact_copy"]["lifecycle_record"])["lfs_pointer_count"] == 1
    assert b"1 tracked pointer paths" in base64.b64decode(json.loads(capture.read_bytes())["stdin"])
    assert snapshot(holder) == before


@pytest.mark.parametrize("vendor", ["codex", "claude"])
@pytest.mark.parametrize("damage", ["missing", "tree", "blob", "head", "config"])
def test_public_lost_copy_resumes_same_author_in_new_copy_and_reports_loss(
        entrance, capsys, vendor, damage):
    holder, store, commands, setup = entrance
    args, _, _ = setup(vendor, custom=True, returned="/tmp/artifact.md")
    assert work.run(args, transport=ArtifactTransport()) == 1
    _, prior_path, prior, _ = bundles(store)[-1]
    prior_bytes = Path(prior_path).read_bytes()
    root = Path(prior["root"])
    if damage == "missing":
        assert trees.dispose(prior["artifact_copy"])["state"] == "removed"
    elif damage == "head":
        (root / ".git/HEAD").unlink()
    elif damage == "config":
        (root / ".git/config").unlink()
    else:
        object_id = git(root, "rev-parse", "HEAD^{tree}" if damage == "tree" else
                        "HEAD:author-commit.txt").stdout.decode().strip()
        target = root / ".git/objects" / object_id[:2] / object_id[2:]
        assert target.resolve().is_relative_to(root.resolve())
        target.chmod(stat.S_IWRITE | stat.S_IREAD)
        target.unlink()
    (holder / "holder-moved.txt").write_bytes(b"new holder commit\n")
    git(holder, "add", "holder-moved.txt")
    git(holder, "-c", "user.name=f", "-c", "user.email=f@x", "commit", "-m", "holder moved")
    head = git(holder, "rev-parse", "HEAD").stdout.decode().strip()
    before = snapshot(holder)
    capsys.readouterr()
    args, capture, dispatch = setup(vendor, custom=True, probe=True)
    assert work.run(args, transport=ArtifactTransport()) == 0
    _, _, resumed, result = bundles(store)[-1]
    seen = json.loads(capture.read_bytes())
    assert resumed["requested"]["session_id"] == SESSION
    assert resumed["predecessor_bundle"] == prior_path and resumed["root"] != str(root)
    assert seen["draft_before"] is None and seen["git_before"]["head"] == head
    assert resumed["artifact_copy"]["source_commit"] == head
    prompt = base64.b64decode(seen["stdin"]).decode()
    assert "earlier artifact copy" in prompt and "working files" in prompt and "lost" in prompt
    assert Path(resumed["input"]).read_bytes() == dispatch.read_bytes()
    report = capsys.readouterr().out.replace("\\\\", "\\")
    assert "artifact_copy_recovery" in report and str(root) in report and "working_files_lost" in report
    record = trees._read(resumed["artifact_copy"]["lifecycle_record"])
    assert record["recovery"]["working_files_lost"] is True and record["recovery"]["root"] == str(root)
    if damage != "missing":
        assert str(root) in record["residues"] and root.exists()
    assert result["outcome"] == "success" and snapshot(holder) == before
    assert Path(prior_path).read_bytes() == prior_bytes


def repair_state(holder, store):
    fixture = work._read_policy_state(ArtifactTransport(), "example/product", 12, CONFIG, {"rules": []}, "fixture")
    fixture.holder_root, fixture.record_root = holder, store
    fixture.issue_comments.append({"id": 752, "body": "<!-- tradecraft:artifact:v1 status=draft -->\n" + artifact_text("combined"),
        "created_at": datetime.now(timezone.utc).isoformat(), "user": {"login": PRODUCER}})
    fixture.validated_markers, fixture.artifact_phase = None, None
    work.validate_marker_claims(fixture)
    return fixture


@pytest.mark.parametrize("failure", ["unavailable", "error", "interrupted"])
@pytest.mark.parametrize("removal_fails", [False, True])
def test_unlaunched_artifact_attempt_disposes_unused_copy_and_does_not_block_author(
        entrance, monkeypatch, capsys, failure, removal_fails):
    holder, store, commands, setup = entrance
    args, _, _ = setup("codex")
    assert work.run(args, transport=ArtifactTransport()) == 0
    accepted_path = bundles(store)[-1][1]
    fixture = repair_state(holder, store)
    decision = work.Decision("artifact", True, "resume", "cold-repair")
    original_dispose, original_process = trees.dispose, implementer.run_process
    if removal_fails:
        monkeypatch.setattr(trees, "dispose", lambda copy, **_k: {
            "state": "removal_failed", "remaining_path": copy["root"], "reason": "injected unused removal failure"})
    if failure == "unavailable":
        monkeypatch.setattr(work, "_selected_runtime_argument", lambda *_a: ["--codex-unavailable-reason", "fixture unavailable"])
    else:
        def refuse_launch(*_a, **_k):
            if failure == "interrupted":
                raise TimeoutError("caller limit has no useful launch window")
            raise OSError("fixture launch refused")
        monkeypatch.setattr(implementer, "run_process", refuse_launch)
    assert work.execute_stage(fixture, decision, holder, None, "holder") == 1
    _, failed_path, unused_request, unused_run = bundles(store)[-1]
    unused_root = Path(unused_request["root"])
    assert unused_run["outcome"] == failure and unused_run["attempts"][0]["launched"] is False
    if failure == "interrupted":
        assert unused_run["interruption_cause"] == "ceiling"
    assert work._resume_source("example/product#12", "artifact", store, state=fixture).path == accepted_path
    copy_record = trees._read(unused_request["artifact_copy"]["lifecycle_record"])
    assert copy_record["state"] == ("removal_failed" if removal_fails else "removed")
    if removal_fails:
        assert str(unused_root) in capsys.readouterr().out.replace("\\\\", "\\")
    old_bundle = Path(failed_path).read_bytes()
    monkeypatch.setattr(trees, "dispose", original_dispose)
    monkeypatch.setattr(implementer, "run_process", original_process)
    monkeypatch.setattr(work, "_selected_runtime_argument", lambda *_a: [])
    args, capture, _ = setup("codex", probe=True)
    assert work.execute_stage(fixture, decision, holder, None, "holder") == 0
    resumed = bundles(store)[-1][2]
    assert resumed["requested"]["session_id"] == SESSION
    assert resumed["predecessor_bundle"] == accepted_path and resumed["root"] != str(unused_root)
    assert json.loads(capture.read_bytes())["draft_before"] is None
    assert Path(failed_path).read_bytes() == old_bundle


@pytest.mark.parametrize("vendor", ["codex", "claude"])
@pytest.mark.parametrize("failure", ["unavailable", "error", "interrupted"])
def test_public_unlaunched_retry_resumes_failed_author_and_preserves_its_copy(
        entrance, monkeypatch, vendor, failure):
    holder, store, commands, setup = entrance
    args, _, _ = setup(vendor, returned="/tmp/artifact.md")
    assert work.run(args, transport=ArtifactTransport()) == 1
    _, author_path, request, author_run = bundles(store)[-1]
    assert author_run["outcome"] == "invalid_artifact_return"
    root = Path(request["root"])
    before, author_bytes = snapshot(root), Path(author_path).read_bytes()
    source_commit = request["artifact_copy"]["source_commit"]
    original_process = implementer.run_process
    if failure == "unavailable":
        monkeypatch.setattr(work, "_selected_runtime_argument", lambda *_a: [
            "--" + vendor + "-unavailable-reason", "fixture unavailable"])
    else:
        def refuse_launch(*_a, **_k):
            if failure == "interrupted":
                raise TimeoutError("caller limit has no useful launch window")
            raise OSError("fixture launch refused")
        monkeypatch.setattr(implementer, "run_process", refuse_launch)
    args, _, _ = setup(vendor, probe=True)
    assert work.run(args, transport=ArtifactTransport()) == 1
    _, unused_path, unused_request, unused_run = bundles(store)[-1]
    assert unused_run["outcome"] == failure and unused_run["attempts"][0]["launched"] is False
    assert unused_request["root"] == str(root) and snapshot(root) == before
    assert trees._read(unused_request["artifact_copy"]["lifecycle_record"])["state"] == "retained"
    unused_bytes = Path(unused_path).read_bytes()
    monkeypatch.setattr(implementer, "run_process", original_process)
    monkeypatch.setattr(work, "_selected_runtime_argument", lambda *_a: [])
    (holder / "new-holder.txt").write_bytes(b"holder moved after failed author")
    git(holder, "add", "new-holder.txt")
    git(holder, "-c", "user.name=f", "-c", "user.email=f@x", "commit", "-m", "holder move")
    args, capture, _ = setup(vendor, probe=True)
    assert work.run(args, transport=ArtifactTransport()) == 0
    _, _, resumed, passed = bundles(store)[-1]
    captured = json.loads(capture.read_bytes())
    assert resumed["requested"]["continuity"] == "resume"
    assert resumed["requested"]["session_id"] == SESSION
    assert resumed["predecessor_bundle"] == author_path and captured["cwd"] == str(root)
    assert captured["draft_before"] == b"unfinished draft\n".hex()
    assert captured["git_before"]["head"] == before["content"]["head"]
    assert captured["git_before"]["index"].encode() == before["index"].strip()
    assert captured["git_before"]["refs"].encode() == before["refs"].strip()
    assert resumed["artifact_copy"]["source_commit"] == source_commit
    assert Path(author_path).read_bytes() == author_bytes and Path(unused_path).read_bytes() == unused_bytes
    assert passed["outcome"] == "success" and not root.exists()


def test_public_restart_after_prelaunch_ceiling_reaches_latest_launched_author(entrance, monkeypatch):
    holder, store, commands, setup = entrance
    args, _, _ = setup("codex", fail="runtime", identity=None)
    assert work.run(args, transport=ArtifactTransport()) == 1
    _, author_path, request, run = bundles(store)[-1]
    run.pop("session_identity", None)
    run.pop("session_identity_error", None)
    for attempt in run["attempts"]:
        attempt["observed"].pop("session_id", None)
    dead = lifecycle.process_identity()
    dead["birth"] += "dead"
    run["launcher_process"] = run["recipient_process"] = dead
    Path(author_path).write_bytes(work.records.json_bytes(run))
    before = snapshot(Path(request["root"]))
    original_process = implementer.run_process
    def expired(*_a, **_k):
        raise TimeoutError("caller limit has no useful launch window")
    monkeypatch.setattr(implementer, "run_process", expired)
    args, _, _ = setup("codex", probe=True)
    args.restart_unresolved_reason = "dead author reported no native session"
    assert work.run(args, transport=ArtifactTransport()) == 1
    _, unused_path, unused_request, unused_run = bundles(store)[-1]
    assert unused_run["outcome"] == "interrupted" and unused_run["attempts"][0]["launched"] is False
    fixture = repair_state(holder, store)
    assert work.work_recovery.latest_stopped(fixture, "artifact")[1] == author_path
    assert trees._read(unused_request["artifact_copy"]["lifecycle_record"])["state"] == "removed"
    assert snapshot(Path(request["root"])) == before
    assert trees.dispose(request["artifact_copy"])["state"] == "removed"
    monkeypatch.setattr(implementer, "run_process", original_process)
    args, capture, _ = setup("codex", probe=True)
    args.restart_unresolved_reason = "dead author reported no native session"
    assert work.run(args, transport=ArtifactTransport()) == 0
    resumed = bundles(store)[-1][2]
    assert resumed["recovery_restart_bundle"] == author_path
    assert resumed["requested"]["continuity"] == "fresh" and resumed["root"] != request["root"]
    assert json.loads(capture.read_bytes())["draft_before"] is None


@pytest.mark.parametrize("pinned", ["codex", "claude"])
def test_legacy_artifact_handover_execution_keeps_recorded_branch(entrance, tmp_path, pinned):
    holder, store, commands, setup = entrance
    old = repository(tmp_path, "legacy-author")
    store.mkdir()
    fixture = repair_state(holder, store)
    reserved = "f0cb89b1-e040-4e6e-919b-4b4e58c717d2"
    source_path = str(store / "legacy.run.json")
    handover_path = work._handover_path(fixture, "artifact_author", old, "registered-branch")
    handover_path.parent.mkdir(parents=True, exist_ok=True)
    reservation = {"schema_version": 1, "from_bundle": source_path, "from_vendor": "codex",
                   "from_session": SESSION, "to_vendor": "claude",
                   "replacement_session": reserved, "phase": "running"}
    handover_path.write_bytes(work.records.json_bytes(reservation))
    request = {"schema_version": 2, "dispatch_id": "legacy", "work": "example/product#12", "stage": "artifact",
        "producer_version": "0.186.0", "root": str(old), "lineage_branch": "registered-branch",
        "launched_at": "2026-10-04T10:00:00Z", "requested": {"vendor": pinned, "session_id": None, "continuity": "fresh"}}
    if pinned == "claude":
        request["handover"] = {"state": str(handover_path), **reservation, "phase": "resume"}
    run = {"schema_version": 2, "dispatch_id": "legacy", "actual_vendor": pinned,
        "outcome": "invalid_artifact_return", "completed_at": "2026-10-04T11:00:00Z",
        "attempts": [{"vendor": pinned, "launched": True, "observed": {
            "session_id": reserved if pinned == "claude" else SESSION,
            "session_id_source": "claude JSON result.session_id" if pinned == "claude" else "codex JSONL thread.started.thread_id"}}]}
    (store / "legacy.request.json").write_bytes(work.records.json_bytes(request))
    Path(source_path).write_bytes(work.records.json_bytes(run))
    args, capture, _ = setup("claude", identity=reserved, probe=True)
    decision = work.Decision("artifact", True, "resume", "cold-repair")
    recovery = reserved if pinned == "codex" else None
    plan = work._launch_plan(fixture, decision, root=holder, recovery_session=recovery)
    assert plan["handover"]["state"] == str(handover_path)
    assert work.execute_stage(fixture, decision, holder, None, "holder", handover_recovery_session=recovery) == 0
    latest = bundles(store)[-1][2]
    assert latest["handover"]["state"] == str(handover_path)
    assert latest["requested"]["session_id"] == reserved and latest["root"] != str(old)
    assert json.loads(capture.read_bytes())["cwd"] == latest["root"]
    assert not work._handover_path(fixture, "artifact_author", old, None).exists()
    # The new-mechanism successor carries the same legacy reservation identity.
    assert work._launch_plan(fixture, decision, root=holder)["handover"]["state"] == str(handover_path)
    setup("claude", identity=reserved, probe=True)
    assert work.execute_stage(fixture, decision, holder, None, "holder") == 0
    assert bundles(store)[-1][2]["artifact_copy"]["handover_branch"] == "registered-branch"


@pytest.mark.parametrize("copy_exists", [False, True])
def test_sessionless_artifact_restart_uses_fresh_copy_without_proving_old_copy(entrance, capsys, copy_exists):
    holder, store, commands, setup = entrance
    args, _, _ = setup("codex", fail="runtime", identity=None)
    assert work.run(args, transport=ArtifactTransport()) == 1
    _, failed_path, request, run = bundles(store)[-1]
    # A dead native launch with no identity is restartable, never resumable.
    run.pop("session_identity", None)
    run.pop("session_identity_error", None)
    for attempt in run["attempts"]:
        attempt["observed"].pop("session_id", None)
    dead = lifecycle.process_identity()
    dead["birth"] += "dead"
    run["launcher_process"] = run["recipient_process"] = dead
    Path(failed_path).write_bytes(work.records.json_bytes(run))
    old_root = Path(request["root"])
    before = snapshot(old_root)
    if not copy_exists:
        assert trees.dispose(request["artifact_copy"])["state"] == "removed"
    fixture = repair_state(holder, store)
    args, capture, _ = setup("codex", probe=True)
    decision = work.Decision("artifact", True, "resume", "stopped")
    assert work.execute_stage(fixture, decision, holder, None, "holder",
        restart_unresolved_reason="dead run had no saved native session") == 0
    latest = bundles(store)[-1][2]
    assert latest["root"] != str(old_root) and latest["requested"]["continuity"] == "fresh"
    assert latest["recovery_restart_bundle"] == failed_path
    assert json.loads(capture.read_bytes())["draft_before"] is None
    if copy_exists:
        assert snapshot(old_root) == before
        assert str(old_root) in capsys.readouterr().out.replace("\\\\", "\\")


@pytest.mark.parametrize("vendor", ["codex", "claude"])
@pytest.mark.parametrize("custom", [False, True])
@pytest.mark.parametrize("registration", ["active", "historical", "legacy"])
def test_public_author_edits_only_its_copy_for_both_routes_and_vendors(entrance, tmp_path, monkeypatch,
                                                                     capsys, vendor, custom, registration):
    holder, store, commands, setup = entrance
    builder = repository(tmp_path, "builder")
    row = registry_row(builder, holder, "fixture", active=registration != "historical")
    if registration == "legacy":
        row.pop("holder_root")
        row.pop("branch")
    registry = {"schema_version": 2, "worktrees": [row]}
    monkeypatch.setattr(work, "read_registry", lambda: registry)
    monkeypatch.setattr(work, "write_registry", lambda *_a: pytest.fail("artifact mutated registry"))
    monkeypatch.setattr(work, "resolve_implementation_root", lambda *_a: pytest.fail("artifact resolved build root"))
    monkeypatch.setattr(work, "publish_implementation_branch", lambda *_a: pytest.fail("artifact published branch"))
    before = snapshot(holder), snapshot(builder), json.dumps(registry)
    args, capture_path, dispatch = setup(vendor, custom)
    assert work.run(args, transport=ArtifactTransport()) == 0
    assert (snapshot(holder), snapshot(builder), json.dumps(registry)) == before
    _, path, request, run = bundles(store)[0]
    copy = request["artifact_copy"]
    plan_line = next(line for line in capsys.readouterr().out.splitlines()
                     if line.startswith("work: launch_settings "))
    plan = json.loads(plan_line.removeprefix("work: launch_settings "))
    assert plan["artifact_copy"]["verified"] is True
    assert {key: plan["artifact_copy"][key] for key in copy} == copy
    captured = json.loads(capture_path.read_bytes())
    assert request["root"] == captured["cwd"] == copy["root"]
    assert copy["holder_root"] == str(holder) and copy["source_commit"] == before[0]["content"]["head"]
    assert captured["git_before"]["remotes"] == "" and captured["git_bindings"] == {}
    assert captured["git_before"]["git_dir"] == captured["git_before"]["common_dir"]
    assert Path(captured["git_before"]["git_dir"]).parent == Path(copy["root"])
    assert captured["git_after"]["head"] != captured["git_before"]["head"]
    assert Path(run["result"]["published_output"]).read_bytes() == artifact_text("combined").replace("\r\n", "\n").encode()
    assert not Path(copy["root"]).exists()
    assert trees._read(copy["lifecycle_record"])["state"] == "removed"
    if custom:
        assert Path(request["input"]).read_bytes() == dispatch.read_bytes()
    native_command = request["requested"]["command"]
    if vendor == "codex":
        assert native_command[native_command.index("--cd") + 1] == copy["root"]
        assert "--add-dir" not in native_command
        assert 'sandbox_mode="workspace-write"' in native_command
        assert "sandbox_workspace_write.writable_roots=[]" in native_command
        assert "sandbox_workspace_write.exclude_slash_tmp=true" in native_command
        assert "sandbox_workspace_write.exclude_tmpdir_env_var=true" in native_command
    else:
        assert "no OS write sandbox" in request["requested"]["permission_boundary"]
        assert "no OS write sandbox" in plan["permission_boundary"]
    assert "--output" in commands[0]
    assert str(path) == trees._read(copy["lifecycle_record"])["bundle"]


@pytest.mark.parametrize("vendor", ["codex", "claude"])
@pytest.mark.parametrize("failure", ["pointer", "empty", "runtime"])
def test_public_failure_resumes_same_copy_with_draft_index_and_git_state(entrance, vendor, failure):
    holder, store, commands, setup = entrance
    args, capture, _dispatch = setup(vendor, returned="/tmp/artifact.md" if failure == "pointer" else "",
                                     fail="runtime" if failure == "runtime" else None)
    assert work.run(args, transport=ArtifactTransport()) == 1
    _, failed_path, request, run = bundles(store)[0]
    old_bytes = Path(failed_path).read_bytes()
    root = Path(request["root"])
    before = snapshot(root)
    source_commit = request["artifact_copy"]["source_commit"]
    (holder / "new-holder.txt").write_bytes(b"holder moved after failure")
    git(holder, "add", "new-holder.txt")
    git(holder, "-c", "user.name=f", "-c", "user.email=f@x", "commit", "-m", "holder move")
    args, capture, _dispatch = setup(vendor, probe=True)
    assert work.run(args, transport=ArtifactTransport()) == 0
    captured = json.loads(capture.read_bytes())
    _, _, resumed, passed = bundles(store)[-1]
    assert captured["cwd"] == str(root)
    assert captured["draft_before"] == b"unfinished draft\n".hex()
    assert captured["git_before"]["head"] == before["content"]["head"]
    assert captured["git_before"]["index"].encode() == before["index"].strip()
    assert resumed["artifact_copy"]["source_commit"] == source_commit
    assert resumed["requested"]["session_id"] == SESSION
    assert Path(failed_path).read_bytes() == old_bytes and not root.exists()
    assert passed["outcome"] == "success"


@pytest.mark.parametrize("vendor", ["codex", "claude"])
@pytest.mark.parametrize("removal", ["normal", "permission", "deadline"])
def test_accepted_repair_resumes_native_session_in_fresh_copy_and_reports_residue(entrance, monkeypatch,
                                                                               capsys, vendor, removal):
    holder, store, commands, setup = entrance
    args, _, _ = setup(vendor)
    original = trees.dispose
    if removal != "normal":
        monkeypatch.setattr(trees, "dispose", lambda copy, **_k: {
            "state": "removal_failed", "remaining_path": copy["root"], "reason": "injected " + removal})
    assert work.run(args, transport=ArtifactTransport()) == 0
    _, prior_path, request, _run = bundles(store)[0]
    first_root = Path(request["root"])
    monkeypatch.setattr(trees, "dispose", original)
    if removal != "normal":
        assert str(first_root) in capsys.readouterr().out.replace("\\\\", "\\")
    (holder / "new.txt").write_bytes(b"new source commit")
    git(holder, "add", "new.txt")
    git(holder, "-c", "user.name=f", "-c", "user.email=f@x", "commit", "-m", "holder update")
    # A substantive cold repair has resume continuity even after an accepted run.
    args, capture, _ = setup(vendor, probe=True)
    fixture = work._read_policy_state(ArtifactTransport(), "example/product", 12, CONFIG, {"rules": []}, "fixture")
    fixture.holder_root, fixture.record_root = holder, store
    fixture.issue_comments.append({"id": 752, "body": "<!-- tradecraft:artifact:v1 status=draft -->\n" + artifact_text("combined"),
        "created_at": datetime.now(timezone.utc).isoformat(), "user": {"login": PRODUCER}})
    fixture.validated_markers = None
    fixture.artifact_phase = None
    work.validate_marker_claims(fixture)
    assert work.execute_stage(fixture, work.Decision("artifact", True, "resume", "cold-repair"),
                              holder, None, "holder") == 0
    _, _, resumed, _ = bundles(store)[-1]
    captured = json.loads(capture.read_bytes())
    assert resumed["root"] != str(first_root)
    assert captured["draft_before"] is None
    assert resumed["artifact_copy"]["source_commit"] == git(holder, "rev-parse", "HEAD").stdout.strip().decode()
    assert resumed["requested"]["session_id"] == SESSION
    assert resumed["predecessor_bundle"] == prior_path
    assert artifact_text("combined").replace("\r\n", "\n").encode() in Path(resumed["input"]).read_bytes().replace(b"\r\n", b"\n")
    if removal != "normal":
        assert trees._read(resumed["artifact_copy"]["lifecycle_record"])["predecessor_residue"] == str(first_root)
        assert first_root.exists()


def test_read_only_artifact_plan_creates_nothing_and_claims_only_planned_copy(entrance):
    holder, store, _, _ = entrance
    fixture = work.WorkState("example/product", 12, {}, holder_root=holder, record_root=store, config=CONFIG)
    before = list(store.rglob("*"))
    plan = work._launch_plan(fixture, work.Decision("artifact", True, "fresh", "fixture"))
    assert plan["artifact_copy"]["root"] is None and plan["artifact_copy"]["verified"] is False
    assert plan["artifact_copy"]["remotes"] is None
    assert plan["artifact_copy"]["source_commit"] == git(holder, "rev-parse", "HEAD").stdout.strip().decode()
    assert list(store.rglob("*")) == before


@pytest.mark.parametrize("problem", ["swapped", "provenance", "remote", "session", "live", "newer-unproved"])
def test_latest_failed_copy_refuses_unproved_resume_without_replacement(entrance, monkeypatch, problem):
    holder, store, commands, setup = entrance
    args, _, _ = setup("codex", returned="/tmp/artifact.md")
    assert work.run(args, transport=ArtifactTransport()) == 1
    _, bundle, request, run = bundles(store)[0]
    root = Path(request["root"])
    original_identity = trees._identity
    request_path = Path(str(bundle).removesuffix(".run.json") + ".request.json")
    if problem == "swapped":
        monkeypatch.setattr(trees, "_identity", lambda _root: {"device": 0, "inode": 0})
    elif problem == "provenance":
        request["artifact_copy"]["source_commit"] = "f" * 40
        request_path.write_bytes(work.records.json_bytes(request))
    elif problem == "remote":
        trees.git(root, "remote", "add", "holder", str(holder))
    elif problem == "session":
        run["attempts"][0]["observed"]["session_id"] = None
        run.pop("session_identity", None)
        Path(bundle).write_bytes(work.records.json_bytes(run))
    elif problem == "live":
        run.pop("completed_at")
        run["lifecycle"] = "running"
        run["launcher_process"] = lifecycle.process_identity()
        run.pop("cleanup_proven", None)
        Path(bundle).write_bytes(work.records.json_bytes(run))
    else:
        request["dispatch_id"] = "newer-unproved"
        request["launched_at"] = "2099-01-01T00:00:00Z"
        newer = store / "newer"
        newer.mkdir()
        (newer / "result.md.request.json").write_bytes(work.records.json_bytes(request))
    count = len(commands)
    # Every refusal returns to the holder; it never clones a replacement draft.
    args, _, _ = setup("codex", probe=True)
    assert work.run(args, transport=ArtifactTransport()) == 0
    assert len(commands) == count
    monkeypatch.setattr(trees, "_identity", original_identity)


def test_public_hard_stopped_author_keeps_copy_and_resumes_its_state(entrance):
    holder, store, commands, setup = entrance
    args, _, _ = setup("codex", returned="/tmp/artifact.md")
    assert work.run(args, transport=ArtifactTransport()) == 1
    _, bundle, request, run = bundles(store)[0]
    root = Path(request["root"])
    # A killed launcher leaves its growing bundle, exact native identity and tree.
    run.pop("completed_at")
    run.pop("cleanup_proven", None)
    run["lifecycle"] = "running"
    dead = lifecycle.process_identity()
    dead["birth"] += "dead"
    run["launcher_process"] = run["recipient_process"] = dead
    Path(bundle).write_bytes(work.records.json_bytes(run))
    record = trees._read(request["artifact_copy"]["lifecycle_record"])
    record["state"] = "running"
    trees._atomic(Path(request["artifact_copy"]["lifecycle_record"]), record)
    before = snapshot(root)
    args, capture, _ = setup("codex", probe=True)
    assert work.run(args, transport=ArtifactTransport()) == 0
    captured = json.loads(capture.read_bytes())
    assert captured["cwd"] == str(root)
    assert captured["git_before"]["head"] == before["content"]["head"]
    assert captured["draft_before"] == b"unfinished draft\n".hex()


@pytest.mark.parametrize("legacy_version", ["0.185.0", "0.186.0"])
def test_legacy_session_recovery_never_imports_or_disposes_old_root(entrance, tmp_path, capsys, legacy_version):
    holder, store, commands, setup = entrance
    old = repository(tmp_path, "legacy-author")
    (old / "old-loose-file").write_bytes(b"legacy state stays here")
    store.mkdir()
    request = {"schema_version": 2, "dispatch_id": "legacy", "work": "example/product#12", "stage": "artifact",
               "producer_version": legacy_version, "root": str(old), "launched_at": "2026-10-04T10:00:00Z",
               "requested": {"vendor": "codex", "session_id": None, "continuity": "fresh"}}
    run = {"schema_version": 2, "dispatch_id": "legacy", "actual_vendor": "codex", "outcome": "invalid_artifact_return",
           "completed_at": "2026-10-04T11:00:00Z", "attempts": [{"observed": {"session_id": SESSION}}]}
    (store / "legacy.request.json").write_bytes(work.records.json_bytes(request))
    (store / "legacy.run.json").write_bytes(work.records.json_bytes(run))
    before = snapshot(old)
    args, capture, _ = setup("codex", probe=True)
    assert work.run(args, transport=ArtifactTransport()) == 0
    latest = bundles(store)[-1][2]
    assert latest["requested"]["session_id"] == SESSION and latest["root"] != str(old)
    assert snapshot(old) == before and (old / "old-loose-file").read_bytes() == b"legacy state stays here"
    assert trees._read(latest["artifact_copy"]["lifecycle_record"])["legacy_recovery"] is True
    assert "loose_files_imported" in capsys.readouterr().out


@pytest.mark.parametrize("problem", ["publication", "unfinished", "termination", "validation"])
def test_disposal_requires_exact_accepted_published_stopped_bundle(entrance, monkeypatch, problem):
    holder, store, commands, setup = entrance
    args, _, _ = setup("codex")
    original_finish = trees.finish
    def unfinished(copy, output, **kwargs):
        run_path = work.records.sidecar(output, ".run.json")
        if run_path.exists():
            run = trees._read(run_path)
            if problem == "unfinished":
                run.pop("completed_at")
            elif problem == "termination":
                run["cleanup_proven"] = False
            elif problem == "validation":
                run["result"]["return_validation"]["status"] = "fail"
            run_path.write_bytes(work.records.json_bytes(run))
        return original_finish(copy, output, **kwargs)
    if problem == "publication":
        def refuse(*_a):
            raise OSError("injected publication failure")
        monkeypatch.setattr(implementer.records, "publish_output", refuse)
        with pytest.raises(OSError, match="publication"):
            work.run(args, transport=ArtifactTransport())
    else:
        monkeypatch.setattr(trees, "finish", unfinished)
        assert work.run(args, transport=ArtifactTransport()) == 0
    request = bundles(store)[-1][2]
    assert Path(request["root"]).exists()
    assert trees._read(request["artifact_copy"]["lifecycle_record"])["state"] == "retained"


def test_artifact_clears_holder_git_bindings_for_launcher_and_native_runtime(entrance, monkeypatch):
    holder, store, _, setup = entrance
    args, capture, _ = setup("codex")
    for key, value in {"GIT_DIR": str(holder / ".git"), "GIT_WORK_TREE": str(holder),
                       "GIT_COMMON_DIR": str(holder / ".git"), "GIT_INDEX_FILE": str(holder / ".git/index"),
                       "GIT_OBJECT_DIRECTORY": str(holder / ".git/objects"),
                       "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(holder / ".git/objects")}.items():
        monkeypatch.setenv(key, value)
    assert work.run(args, transport=ArtifactTransport()) == 0
    captured = json.loads(capture.read_bytes())
    request, run = bundles(store)[-1][2:]
    assert captured["git_bindings"] == {}
    assert request["revision_before"] == request["artifact_copy"]["source_commit"]
    assert run["revision_after"] == captured["git_after"]["head"]


@pytest.mark.parametrize("vendor", ["codex", "claude"])
def test_accepted_uncontinuable_author_return_is_still_disposable(entrance, vendor):
    _holder, store, _commands, setup = entrance
    args, _, _ = setup(vendor, identity=None)
    assert work.run(args, transport=ArtifactTransport()) == 1
    request, run = bundles(store)[-1][2:]
    assert run["outcome"] == "success_uncontinuable" and trees.accepted(run)
    assert not Path(request["root"]).exists()
    assert trees._read(request["artifact_copy"]["lifecycle_record"])["state"] == "removed"


def test_unresolved_vendor_handover_recovers_reserved_session_in_its_retained_copy(entrance, monkeypatch):
    holder, store, _commands, setup = entrance
    args, _, _ = setup("codex")
    assert work.run(args, transport=ArtifactTransport()) == 0
    first_path = bundles(store)[-1][1]
    fixture = work._read_policy_state(ArtifactTransport(), "example/product", 12, CONFIG, {"rules": []}, "fixture")
    fixture.holder_root, fixture.record_root = holder, store
    fixture.issue_comments.append({"id": 752, "body": "<!-- tradecraft:artifact:v1 status=draft -->\n" + artifact_text("combined"),
        "created_at": datetime.now(timezone.utc).isoformat(), "user": {"login": PRODUCER}})
    fixture.validated_markers, fixture.artifact_phase = None, None
    work.validate_marker_claims(fixture)
    args, _, _ = setup("claude")
    monkeypatch.setattr(work, "_selected_runtime_argument", lambda vendor, _path: ["--" + vendor, sys.executable])
    scenario_path = store.parent / "scenario.json"
    scenario = json.loads(scenario_path.read_bytes())
    scenario["claude"].update(stdout=json.dumps({"type": "result", "is_error": True, "result": "failed without identity"}), exit=1)
    scenario_path.write_bytes(json.dumps(scenario).encode())
    decision = work.Decision("artifact", True, "resume", "cold-repair")
    assert work.execute_stage(fixture, decision, holder, None, "holder") == 1
    latest = bundles(store)[-1]
    failed_root = Path(latest[2]["root"])
    reserved = latest[2]["handover"]["replacement_session"]
    assert latest[2]["handover"]["from_bundle"] == first_path
    assert not latest[3].get("session_identity")
    dead = lifecycle.process_identity()
    dead["birth"] += "dead"
    latest[3]["launcher_process"] = latest[3]["recipient_process"] = dead
    Path(latest[1]).write_bytes(work.records.json_bytes(latest[3]))
    args, capture, _ = setup("claude", identity=reserved, probe=True)
    assert work.execute_stage(fixture, decision, holder, None, "holder", handover_recovery_session=reserved) == 0
    captured = json.loads(capture.read_bytes())
    assert captured["cwd"] == str(failed_root) and captured["draft_before"] == b"unfinished draft\n".hex()
    resumed = bundles(store)[-1][2]
    assert resumed["requested"]["session_id"] == reserved and not failed_root.exists()

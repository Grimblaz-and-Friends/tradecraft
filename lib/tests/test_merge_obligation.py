"""Composition-time merge obligations through real Git and the launch endpoint."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import work
from test_catch_up import SPEC, RULES, graph, registered, git, commit
from test_catch_up import duplicate_member_conflict, invalid_version_stage, INVALID_VERSION_STAGES, masked_merge_results
from test_work import AFFIRMED, ARTIFACT, WOULD, HOLDER, SESSION, state, dispatch_bundle


@pytest.fixture
def launch(registered, tmp_path, monkeypatch):
    holder, implementation, branch, remote, transport, _state = registered
    git(holder, "config", "core.autocrlf", "false")
    brief = AFFIRMED + "\nAFFIRMED SENTINEL"
    artifact = ("<!-- tradecraft:artifact:v1 status=settled route=unobtainable -->\n"
        + "\n".join("> " + line for line in brief.splitlines())
        + "\nThe artifact describes the complete implementation decisions and their executable acceptance criteria.\n")
    fixture = state(brief, ARTIFACT, artifact, HOLDER + "\nREADING SENTINEL", pr=True)
    fixture.pr = transport.get("repos/example/product/pulls/7")
    fixture.record_root = tmp_path / "records"
    dispatch_bundle(fixture.record_root)
    request_path = fixture.record_root / "build" / "result.md.request.json"
    request = json.loads(request_path.read_bytes())
    request.update(root=str(implementation), lineage_branch=branch, lineage_pull_request=7)
    request_path.write_bytes(json.dumps(request).encode("utf-8"))
    monkeypatch.setattr(work, "_runtime_argument", lambda vendor, explicit=None: [f"--{vendor}", "fixture"])
    inputs = []

    def capture(command, **kwargs):
        assert Path(command[1]).name == "dispatch_implementer.py"
        prompt = Path(command[command.index("--dispatch") + 1]).read_bytes()
        context = Path(command[command.index("--context") + 1]).read_bytes()
        metadata = json.loads(Path(command[command.index("--lifecycle-input") + 1]).read_bytes())
        inputs.append({"prompt": prompt, "effective": context + b"\n\n" + prompt,
                       "metadata": metadata, "command": command})
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(work, "_recipient_run", capture)

    def compose(stage="build", *, rules=RULES, dispatch=None, continuity="resume"):
        decision = work.Decision(stage, True, continuity, "holder-named-stage")
        assert work.execute_stage(fixture, decision, holder, None, "holder-id",
            transport=transport, rules=rules, dispatch_path=dispatch,
            floor_command="python exact-fixture-floor.py") == 0
        return inputs[-1] if inputs else None

    return registered, fixture, inputs, compose


def mixed(registered, *, outside=False, version_path="version.json"):
    holder, implementation, branch, remote, transport, fixture = registered
    commit(implementation, version_path, '{"version":"1.3.0","name":"own"}\n')
    commit(holder, version_path, '{"version":"1.4.0","name":"' + ("base" if outside else "fixture") + '"}\n')
    commit(holder, "src/own", "incoming\n")
    git(implementation, "push")
    git(holder, "push", "origin", "main")
    return git(holder, "rev-parse", "HEAD")


def outside_paths(prompt):
    section = prompt.decode("utf-8").split("Files requiring builder conflict resolution:\n", 1)[1].split("\n\n", 1)[0]
    return [] if section.startswith("None:") else [json.loads(line) for line in section.splitlines()]


def follow_merge_input(registered, prompt, *, resolutions=None):
    """Fixture builder takes its target, paths and version from the actual input."""
    holder, implementation, branch, remote, transport, fixture = registered
    text = prompt.decode("utf-8")
    command = shlex.split(re.search(r"^Run: (.+)$", text, re.M)[1])
    assert command[:4] == ["git", "merge", "--no-commit", "--no-ff"]
    start = git(implementation, "rev-parse", "HEAD")
    git(implementation, *command[1:], check=False)
    for path in outside_paths(prompt):
        (implementation / path).write_bytes((resolutions or {}).get(path, b"resolved implementation and base\n"))
        git(implementation, "add", "--", path)
    adjustment = re.search(r'^Set (".*")\x27s top-level JSON field (".*") to (".*") in this merge\.$', text, re.M)
    if adjustment:
        path, field, value = [json.loads(part) for part in adjustment.groups()]
        content = json.loads(git(implementation, "show", f":2:{path}"))
        content[field] = value
        (implementation / path).write_bytes((json.dumps(content) + "\n").encode("utf-8"))
        git(implementation, "add", "--", path)
    script = LIB.parent / "skills" / "persist-changes" / "scripts" / "persist.py"
    result = subprocess.run([sys.executable, str(script), "--expect-branch", branch,
        "-m", "Resolve the composed pinned merge before fixture repairs"], cwd=implementation,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode == 0, result.stdout + result.stderr
    head = git(implementation, "rev-parse", "HEAD")
    assert git(implementation, "show", "-s", "--format=%P", head).split() == [start, command[-1]]
    assert git(holder, "ls-remote", "--heads", str(remote), f"refs/heads/{branch}").split()[0] == head
    return head


def snapshot(root):
    index = Path(git(root, "rev-parse", "--git-path", "index"))
    if not index.is_absolute():
        index = root / index
    merge = Path(git(root, "rev-parse", "--git-path", "MERGE_HEAD"))
    if not merge.is_absolute():
        merge = root / merge
    return (git(root, "rev-parse", "HEAD"), index.read_bytes(),
            git(root, "--no-optional-locks", "status", "--porcelain"),
            {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*")
             if path.is_file() and ".git" not in path.relative_to(root).parts
             and path.relative_to(root).parts[:2] != (".claude", "worktrees")}, merge.exists())


def assert_obligation(record, pinned, paths, value="1.5.0"):
    prompt = record["prompt"]
    assert prompt.startswith(b"Merge obligation: do this before the implementation or reviewer repairs")
    assert f"Run: git merge --no-commit --no-ff {pinned}".encode() in prompt
    assert b"Do not rebase." in prompt
    assert outside_paths(prompt) == paths
    assert (f'to "{value}" in this merge.'.encode() in prompt) if value else b"Declared version adjustment:" not in prompt
    assert record["metadata"]["prompt_composition"]["dispatch_sha256"] == hashlib.sha256(prompt).hexdigest()


def test_C1_C6_mixed_catch_up_then_composed_builder_lands(launch, monkeypatch, capsys):
    registered, fixture, inputs, compose = launch
    holder, implementation, branch, remote, transport, catch_state = registered
    pinned = mixed(registered)
    before = snapshot(implementation)
    original = work._catch_up_version_conflict
    observed = []
    def resolved(*args):
        original(*args)
        observed.append((work._catch_up_conflicts(implementation), json.loads((implementation / "version.json").read_bytes())))
    monkeypatch.setattr(work, "_catch_up_version_conflict", resolved)
    work._execute_catch_up(transport, catch_state, holder, None, "holder-id", RULES)
    refused = json.loads(capsys.readouterr().out)
    assert refused["reason"] == "builder-required"
    assert refused["conflicts"] == ["src/own"] and "version.json" not in refused["detail"]
    assert refused["next"] == {"stage": "build", "continuity": "resume"}
    assert observed == [(["src/own"], {"version": "1.5.0", "name": "own"})]
    after = snapshot(implementation)
    assert after[0] == before[0] and after[2:] == before[2:]
    assert git(implementation, "ls-files", "-u") == ""
    record = compose()
    assert_obligation(record, pinned, refused["conflicts"])
    head = follow_merge_input(registered, record["prompt"])
    assert json.loads((implementation / "version.json").read_bytes()) == {"version": "1.5.0", "name": "own"}
    assert (implementation / "src/own").read_bytes() == b"resolved implementation and base\n"


def test_C2_skipped_catch_up_and_cached_mergeable_still_owes_merge(launch):
    registered, fixture, inputs, compose = launch
    pinned = mixed(registered)
    assert fixture.pr["mergeable"] is True
    common = work._git_common_directory(registered[1])
    assert not (common / "tradecraft-catch-up").exists()
    assert_obligation(compose(), pinned, ["src/own"])
    assert not (common / "tradecraft-catch-up").exists()


@pytest.mark.parametrize("increment,expected", [("major", "3.0.0"), ("minor", "2.8.0"), ("patch", "2.7.10")])
def test_C3_composition_pins_new_base_after_catch_up(launch, capsys, increment, expected):
    registered, fixture, inputs, compose = launch
    holder, implementation, branch, remote, transport, catch_state = registered
    first = mixed(registered)
    work._execute_catch_up(transport, catch_state, holder, None, "holder-id", RULES)
    assert json.loads(capsys.readouterr().out)["pinned_base"] == first
    fixture.pr["base"]["sha"] = first
    second = commit(holder, "version.json", '{"version":"2.7.9","name":"fixture"}\n')
    git(holder, "push", "origin", "main")
    git(holder, "update-ref", "refs/remotes/origin/main", first)
    record = compose(rules={**RULES, "version": {**SPEC, "increment": increment}})
    assert_obligation(record, second, ["src/own"], expected)
    assert f"Run: git merge --no-commit --no-ff {first}".encode() not in record["prompt"]
    follow_merge_input(registered, record["prompt"])
    assert json.loads((implementation / "version.json").read_bytes())["version"] == expected


@pytest.mark.parametrize("control", ["no-declaration", "unchanged-file", "changed-other-member"])
def test_C3_version_adjustment_uses_declared_file_change(launch, control):
    registered, fixture, inputs, compose = launch
    holder, implementation, branch, remote, transport, catch_state = registered
    pinned = commit(holder, "src/own", "incoming\n")
    rules = RULES
    expected = None
    if control == "no-declaration":
        rules = {key: value for key, value in RULES.items() if key != "version"}
    elif control == "changed-other-member":
        pinned = commit(holder, "version.json", '{"version":"1.2.3","name":"base"}\n')
        expected = "1.3.0"
    git(holder, "push", "origin", "main")
    assert_obligation(compose(rules=rules), pinned, ["src/own"], expected)


@pytest.mark.parametrize("stage", ["build", "review-disposition"])
@pytest.mark.parametrize("case", ["contained", "behind-clean", "diverged-clean", "version-only"])
def test_C4_clean_and_version_only_actual_inputs(launch, stage, case):
    registered, fixture, inputs, compose = launch
    holder, implementation, branch, remote, transport, catch_state = registered
    if case == "contained":
        pinned = git(holder, "rev-parse", "main")
    elif case == "behind-clean":
        git(implementation, "reset", "--hard", "main")
        pinned = commit(holder, "src/other", "incoming\n")
    elif case == "diverged-clean":
        pinned = commit(holder, "src/other", "incoming\n")
    else:
        commit(implementation, "version.json", '{"version":"1.3.0","name":"fixture"}\n')
        pinned = commit(holder, "version.json", '{"version":"1.4.0","name":"fixture"}\n')
    git(holder, "push", "origin", "main")
    before = snapshot(implementation), snapshot(holder)
    record = compose(stage)
    if case == "version-only":
        assert_obligation(record, pinned, [])
        assert b"None: no conflicts outside the declared field." in record["prompt"]
    else:
        for absent in (b"Merge obligation:", b"git merge --no-commit", b"Declared version adjustment:"):
            assert absent not in record["prompt"]
    assert (snapshot(implementation), snapshot(holder)) == before


def test_C5_probe_preserves_pending_local_progress_and_checkout(launch):
    registered, fixture, inputs, compose = launch
    holder, implementation, branch, remote, transport, catch_state = registered
    pinned = mixed(registered)
    local = commit(implementation, "local-progress", "committed stopped-turn work\n")
    (implementation / "src/other").write_bytes(b"staged pending\n")
    git(implementation, "add", "src/other")
    (implementation / "src/other").write_bytes(b"unstaged pending\n")
    (holder / "src/other").write_bytes(b"holder pending\n")
    before = snapshot(implementation), snapshot(holder)
    assert_obligation(compose(), pinned, ["src/own"])
    assert git(implementation, "rev-parse", "HEAD") == local != fixture.pr["head"]["sha"]
    assert (snapshot(implementation), snapshot(holder)) == before


@pytest.mark.parametrize("stage", ["build", "review-disposition"])
@pytest.mark.parametrize("failure", ["metadata", "closed", "base-read", "invalid-pin", "wrong-pr-branch", "fetch", "moved-pin", "head", "history", "tree", "blob", "conflict-blob", "git-error", "malformed", "unterminated-tree", "empty-conflicts", "clean-with-stages", "stage-record", "stage-terminator", "duplicate-stage", "undecodable", "merge-file", "merge-file-empty", "timeout", "declaration", "base-blob", "base-value"])
def test_C5_inability_refuses_before_launch_and_preserves_tree(launch, monkeypatch, capsys, stage, failure):
    registered, fixture, inputs, compose = launch
    holder, implementation, branch, remote, transport, catch_state = registered
    mixed(registered)
    if failure == "base-blob":
        git(holder, "rm", "version.json")
        git(holder, "commit", "-m", "unreadable declared base file")
        git(holder, "push", "origin", "main")
    if failure == "base-value":
        commit(holder, "version.json", '{"version":"wrong","name":"fixture"}\n')
        git(holder, "push", "origin", "main")
    (implementation / "src/other").write_bytes(b"staged\n")
    git(implementation, "add", "src/other")
    (implementation / "src/other").write_bytes(b"unstaged\n")
    before = snapshot(implementation), snapshot(holder), work.registry_path().read_bytes()
    original_get, original_git = transport.get, work._git
    def get(endpoint, paginate=False):
        result = original_get(endpoint, paginate)
        if endpoint.endswith("/pulls/7") and failure == "metadata":
            result.pop("base")
        if endpoint.endswith("/pulls/7") and failure == "closed":
            result["state"] = "closed"
        if endpoint.endswith("/pulls/7") and failure == "wrong-pr-branch":
            result["head"]["ref"] = "another-branch"
        if "/git/ref/heads/" in endpoint and failure == "base-read":
            raise work.WorkError("fixture base unreadable")
        if "/git/ref/heads/" in endpoint and failure == "moved-pin":
            result["object"]["sha"] = git(holder, "merge-base", "main", branch)
        if "/git/ref/heads/" in endpoint and failure == "invalid-pin":
            result["object"]["sha"] = "not-a-commit"
        return result
    blob_reads = 0
    def probe(arguments, cwd):
        nonlocal blob_reads
        if arguments[:2] == ["cat-file", "blob"]:
            blob_reads += 1
        arm = ((failure == "fetch" and arguments[0] == "fetch")
            or (failure == "head" and arguments[:2] == ["rev-parse", "--verify"])
            or (failure == "history" and arguments[0] == "merge-base")
            or (failure == "tree" and arguments[:2] == ["cat-file", "-e"])
            or (failure == "blob" and arguments[:2] == ["cat-file", "blob"])
            or (failure == "conflict-blob" and arguments[:2] == ["cat-file", "blob"] and blob_reads > 1)
            or (failure == "merge-file" and arguments[0] == "merge-file"))
        if arm:
            observed = original_git(arguments, cwd)
            return subprocess.CompletedProcess(arguments, 255, observed.stdout, b"fixture unavailable")
        if failure == "merge-file-empty" and arguments[0] == "merge-file":
            return subprocess.CompletedProcess(arguments, 1, b"", b"fixture unusable")
        if failure == "timeout" and arguments[0] == "merge-tree":
            raise subprocess.TimeoutExpired(arguments, 0.01)
        result = original_git(arguments, cwd)
        if arguments[0] == "merge-tree":
            if failure == "git-error":
                return subprocess.CompletedProcess(arguments, 129, result.stdout, b"unsupported option")
            if failure == "malformed":
                return subprocess.CompletedProcess(arguments, 1, b"bad result", b"")
            if failure == "unterminated-tree":
                return subprocess.CompletedProcess(arguments, 0, result.stdout.split(b"\0")[0], b"")
            if failure == "empty-conflicts":
                result.stdout = result.stdout.split(b"\0")[0] + b"\0"
            if failure == "clean-with-stages":
                result.returncode = 0
            if failure == "stage-record":
                result.stdout = result.stdout.replace(b"100644 ", b"999999 ", 1)
            if failure == "stage-terminator":
                result.stdout = result.stdout[:-1]
            if failure == "duplicate-stage":
                result.stdout += result.stdout.split(b"\0")[1] + b"\0"
            if failure == "undecodable":
                result.stdout = result.stdout.replace(b"src/own", b"src/\xff")
        return result
    monkeypatch.setattr(transport, "get", get)
    monkeypatch.setattr(work, "_git", probe)
    root_setups = []
    original_root = work._stage_root
    def setup(*args, **kwargs):
        root_setups.append(True)
        return original_root(*args, **kwargs)
    monkeypatch.setattr(work, "_stage_root", setup)
    selected_rules = {**RULES, "version": {**SPEC, "increment": "unknown"}} if failure == "declaration" else RULES
    assert compose(stage, rules=selected_rules) is None
    report = json.loads(capsys.readouterr().out)
    assert report["stage"] == stage and report["dispatch"] is False and report["status"] == "refused"
    assert report["reason"] == f"stage-input-invalid-for-{stage}"
    assert report["detail"]
    cause = {"metadata": "metadata", "closed": "still-open", "base-read": "base unreadable",
        "invalid-pin": "no full revision", "wrong-pr-branch": "registered repository and branch",
        "fetch": "cannot fetch", "moved-pin": "moved during fetch", "head": "implementation head",
        "history": "read merge base", "tree": "result tree", "blob": "policy", "conflict-blob": "version conflict blob",
        "git-error": "dry run failed", "malformed": "dry-run tree result",
        "unterminated-tree": "dry-run tree result", "empty-conflicts": "no affected paths",
        "clean-with-stages": "clean merge-obligation result", "stage-record": "stage record",
        "stage-terminator": "NUL terminator", "duplicate-stage": "duplicate path and stage",
        "undecodable": "not UTF-8", "merge-file": "classify version conflict",
        "merge-file-empty": "classify version conflict", "timeout": "timed out",
        "declaration": "version increment", "base-blob": "base version file",
        "base-value": "three integer parts"}[failure]
    assert cause in report["detail"]
    assert not inputs
    assert not root_setups
    assert (snapshot(implementation), snapshot(holder), work.registry_path().read_bytes()) == before


def test_C5_initial_refusal_precedes_legacy_migration(launch, monkeypatch, capsys):
    registered, fixture, inputs, compose = launch
    mixed(registered)
    registry = work.read_registry()
    registry["worktrees"][0].pop("holder_root")
    registry["worktrees"][0].pop("branch")
    work.write_registry(registry)
    before = work.registry_path().read_bytes()
    monkeypatch.setattr(work, "_pin_merge_base", lambda *_a: (_ for _ in ()).throw(work.WorkError("base unreadable")))
    assert compose() is None
    assert "base unreadable" in json.loads(capsys.readouterr().out)["detail"]
    assert work.registry_path().read_bytes() == before


def test_C5_fresh_preflight_refusal_precedes_root_creation_publication(launch, monkeypatch, capsys):
    registered, fixture, inputs, compose = launch
    mixed(registered)
    work.write_registry({"schema_version": 1, "worktrees": []})
    before = snapshot(registered[0]), work.registry_path().read_bytes()
    monkeypatch.setattr(work, "_pin_merge_base", lambda *_a: (_ for _ in ()).throw(work.WorkError("base unreadable")))
    monkeypatch.setattr(work, "_stage_root", lambda *_a, **_k: pytest.fail("refusal created a root"))
    assert compose(continuity="fresh") is None
    assert "base unreadable" in json.loads(capsys.readouterr().out)["detail"]
    assert (snapshot(registered[0]), work.registry_path().read_bytes()) == before


@pytest.mark.parametrize("problem", ["wrong-branch", "wrong-holder", "missing", "lineage"])
def test_C5_preserves_existing_root_and_resume_lineage_refusals(launch, monkeypatch, capsys, problem):
    registered, fixture, inputs, compose = launch
    mixed(registered)
    registry = work.read_registry()
    if problem == "wrong-branch":
        registry["worktrees"][0]["branch"] = "wrong-branch"
    elif problem == "wrong-holder":
        registry["worktrees"][0]["holder_root"] = str(registered[1])
    elif problem == "missing":
        registry["worktrees"] = []
    else:
        path = fixture.record_root / "build" / "result.md.request.json"
        request = json.loads(path.read_bytes())
        request["root"] = str(registered[0])
        path.write_bytes(json.dumps(request).encode("utf-8"))
    work.write_registry(registry)
    monkeypatch.setattr(work, "_pin_merge_base", lambda *_a: pytest.fail("invalid root probed base"))
    assert compose() is None
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "implementation-root-unproved-for-build"
    assert report["dispatch"] is False


def test_C3_base_ref_encoding_and_selected_transport(launch, monkeypatch):
    registered, fixture, inputs, compose = launch
    holder, implementation, branch, remote, transport, catch_state = registered
    pinned = mixed(registered)
    ref = "release/" + chr(0xE9)
    git(holder, "remote", "rename", "origin", "shipping")
    git(holder, "push", "shipping", f"HEAD:refs/heads/{ref}")
    original_get, original_git = transport.get, work._git
    seen = []
    endpoints = []
    def get(endpoint, paginate=False):
        endpoints.append(endpoint)
        result = original_get(endpoint, paginate)
        if endpoint.endswith("/pulls/7"):
            result["base"]["ref"] = ref
        return result
    def probe(arguments, cwd):
        if arguments[0] == "fetch":
            seen.append(arguments)
        return original_git(arguments, cwd)
    monkeypatch.setattr(transport, "get", get)
    monkeypatch.setattr(work, "_git", probe)
    assert_obligation(compose(), pinned, ["src/own"])
    assert seen == [["fetch", "--no-tags", "shipping", f"refs/heads/{ref}"]]
    assert "repos/example/product/git/ref/heads/release%2F%C3%A9" in endpoints


def test_C5_fresh_probe_uses_committed_destination_attributes(launch):
    registered, fixture, inputs, compose = launch
    holder, implementation, branch, remote, transport, catch_state = registered
    pinned = mixed(registered)
    own = git(implementation, "rev-parse", "HEAD")
    git(holder, "switch", "--detach", own)
    (holder / ".gitattributes").write_bytes(b"src/own merge=union\n")
    work.write_registry({"schema_version": 1, "worktrees": []})
    before = snapshot(holder)
    record = compose(continuity="fresh")
    assert_obligation(record, pinned, ["src/own"])
    assert snapshot(holder) == before
    new_root = Path(record["command"][record["command"].index("--root") + 1])
    assert not (new_root / ".gitattributes").exists()
    assert git(new_root, "rev-parse", "HEAD") == own


@pytest.mark.parametrize("stage", ["build", "review-disposition"])
def test_C7_residual_version_member_is_in_actual_prompt(launch, stage):
    registered, fixture, inputs, compose = launch
    pinned = mixed(registered, outside=True)
    assert_obligation(compose(stage), pinned, ["src/own", "version.json"])


@pytest.mark.parametrize("kind", ["invalid-json", "delete", "mode", "symlink", "add-add"])
def test_C7_unsupported_version_shape_stays_in_composed_paths(launch, kind):
    registered, fixture, inputs, compose = launch
    holder, implementation, branch, remote, transport, catch_state = registered
    if kind == "delete":
        git(implementation, "rm", "version.json")
        git(implementation, "commit", "-m", "fixture deletion")
    elif kind == "symlink":
        oid = git(implementation, "rev-parse", "HEAD:src/own")
        git(implementation, "update-index", "--cacheinfo", f"120000,{oid},version.json")
        git(implementation, "commit", "-m", "fixture symlink replacement")
    elif kind == "add-add":
        common = git(holder, "merge-base", "main", branch)
        git(implementation, "reset", "--hard", common)
        git(holder, "rm", "version.json")
        git(holder, "commit", "-m", "fixture no version ancestor")
        git(implementation, "merge", "--ff-only", "main")
        commit(implementation, "version.json", '{"version":"1.3.0","name":"fixture"}\n')
    else:
        content = "invalid JSON\n" if kind == "invalid-json" else '{"version":"1.3.0","name":"fixture"}\n'
        commit(implementation, "version.json", content)
        if kind == "mode":
            git(implementation, "update-index", "--chmod=+x", "version.json")
            git(implementation, "commit", "-m", "fixture mode change")
    pinned = commit(holder, "version.json", '{"version":"1.4.0","name":"fixture"}\n')
    git(holder, "push", "origin", "main")
    record = compose()
    expected = ["version.json", f"version.json~{pinned}"] if kind == "symlink" else ["version.json"]
    assert_obligation(record, pinned, expected)


@pytest.mark.parametrize("stage", ["build", "review-disposition"])
def test_C7_clean_masked_merge_with_duplicate_member_is_in_actual_prompt(
        launch, masked_merge_results, capsys, stage):
    registered, fixture, inputs, compose = launch
    pinned = duplicate_member_conflict(registered)
    before = snapshot(registered[1]), snapshot(registered[0])
    record = compose(stage)
    assert record is not None, capsys.readouterr().out
    assert len(masked_merge_results) == 1
    assert masked_merge_results[0].returncode == 0
    assert masked_merge_results[0].stdout.count(b'"homepage"') == 2
    assert_obligation(record, pinned, ["version.json"])
    assert (snapshot(registered[1]), snapshot(registered[0])) == before


@pytest.mark.parametrize("stage", ["build", "review-disposition"])
@pytest.mark.parametrize("content", INVALID_VERSION_STAGES)
def test_C7_invalid_stage_document_is_in_actual_prompt(launch, stage, content):
    registered, fixture, inputs, compose = launch
    pinned = invalid_version_stage(registered, content)
    assert_obligation(compose(stage), pinned, ["version.json"])


def test_C7_spaces_and_unicode_paths_are_exact(launch, capsys):
    registered, fixture, inputs, compose = launch
    holder, implementation, branch, remote, transport, catch_state = registered
    path = "a space " + chr(0x96EA) + ".json"
    source_path = "source space " + chr(0x96EA) + ".txt"
    git(holder, "mv", "version.json", path)
    git(holder, "commit", "-m", "fixture version path")
    commit(holder, source_path, "common\n")
    git(implementation, "merge", "--no-ff", "-m", "fixture version path", "main")
    commit(implementation, source_path, "ours\n")
    commit(holder, source_path, "theirs\n")
    pinned = mixed(registered, version_path=path)
    rules = {**RULES, "version": {**SPEC, "path": path}}
    work._execute_catch_up(transport, catch_state, holder, None, "holder-id", rules)
    report = json.loads(capsys.readouterr().out)
    expected = sorted([source_path, "src/own"])
    assert sorted(report["conflicts"]) == expected
    record = compose(rules=rules)
    assert_obligation(record, pinned, expected)
    assert json.dumps(path).encode() in record["prompt"]


@pytest.mark.parametrize("stage", ["build", "review-disposition", "floor"])
def test_C10_custom_dispatch_bytes_and_floor_skip_probe(launch, tmp_path, monkeypatch, stage):
    registered, fixture, inputs, compose = launch
    mixed(registered)
    monkeypatch.setattr(work, "_compose_merge_obligation", lambda *_a, **_k: pytest.fail("excluded route probed merge"))
    monkeypatch.setattr(registered[4], "get", lambda *_a, **_k: pytest.fail("unavailable base consulted"))
    dispatch = tmp_path / "holder-dispatch.txt"
    supplied = ('  Holder merge obligation: merge my pinned commit.\r\n\r\n' + chr(0x96EA) + '  \r\n').encode("utf-8")
    dispatch.write_bytes(supplied)
    assert compose(stage, dispatch=dispatch)["prompt"] == supplied
    if stage == "floor":
        prompt = compose(stage)["prompt"]
        assert b"python exact-fixture-floor.py" in prompt
        assert b"READING SENTINEL" in prompt and b"AFFIRMED SENTINEL" in prompt
        assert b"Merge obligation:" not in prompt


def test_C11_legacy_recomposition_retains_final_obligation_and_sources(launch, monkeypatch):
    registered, fixture, inputs, compose = launch
    holder, implementation, branch, remote, transport, catch_state = registered
    first = mixed(registered)
    registry = work.read_registry()
    registry["worktrees"][0].pop("holder_root")
    registry["worktrees"][0].pop("branch")
    work.write_registry(registry)
    original = work.resolve_implementation_root
    second = []
    def migrate(*args, **kwargs):
        result = original(*args, **kwargs)
        if kwargs.get("migrate", True) and result and result[2]:
            second.append(commit(holder, "version.json", '{"version":"1.6.0","name":"fixture"}\n'))
            git(holder, "push", "origin", "main")
        return result
    monkeypatch.setattr(work, "resolve_implementation_root", migrate)
    record = compose()
    assert_obligation(record, second[0], ["src/own"], "1.7.0")
    assert f"Run: git merge --no-commit --no-ff {first}".encode() not in record["prompt"]
    assert work.MIGRATION_NOTICE.encode() in record["prompt"]
    assert b"READING SENTINEL" in record["prompt"] and b"AFFIRMED SENTINEL" in record["prompt"]
    assert work.build_reach.PRESERVATION.encode() in record["prompt"]
    assert b"map every artifact acceptance criterion" in record["prompt"]
    assert b"Remain on that branch" in record["prompt"]

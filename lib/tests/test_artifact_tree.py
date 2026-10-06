"""Real-Git acceptance checks for independent artifact copies (A2-A5)."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import artifact_tree as trees
import run_lifecycle as lifecycle
from test_work import repository, git


@pytest.mark.parametrize("change", [
    {"completed_at": None}, {"lifecycle": "running"}, {"cleanup_proven": False},
    {"launch_unresolved": True}, {"recovery_error": "unsupported dispatch schema"},
    {"attempts": [{"launched": True}]}, {"attempts": [{}]}, {"attempts": []},
    {"recipient_process": {"pid": 1}},
])
def test_unlaunched_attempt_requires_explicit_complete_no_launch_evidence(change):
    run = {"schema_version": 2, "lifecycle": "completed", "completed_at": "2026-10-06T00:00:00Z",
           "outcome": "error", "attempts": [{"launched": False, "observed": {"session_id": "inherited"}}]}
    assert trees.unlaunched(run)
    assert not trees.unlaunched({**run, **change})


@pytest.mark.parametrize("linked", [False, True])
def test_source_probes_retry_dubious_ownership_with_only_scoped_trust(tmp_path, monkeypatch, linked):
    holder = repository(tmp_path)
    if linked:
        target = tmp_path / "linked"
        git(holder, "worktree", "add", "-b", "linked", str(target))
        holder = target
    git_dir = Path(git(holder, "rev-parse", "--absolute-git-dir").stdout.decode().strip()).resolve()
    commit = git(holder, "rev-parse", "HEAD").stdout.decode().strip()
    original = trees.run_process
    commands = []
    def different_owner(command, **kwargs):
        if command[0] == "git" and command[command.index("-C") + 1] == str(holder):
            kwargs["env"] = {**kwargs["env"], "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"}
            commands.append(command)
        return original(command, **kwargs)
    monkeypatch.setattr(trees, "run_process", different_owner)
    # Negative control establishes the real Git ownership refusal being repaired.
    with pytest.raises(trees.ArtifactTreeError, match="dubious ownership"):
        trees.git(holder, "rev-parse", "--show-toplevel")
    with trees.checkout(holder, tmp_path / "bundle/result.md", work="fixture#1", instalment=None,
                        holder_session_id="holder") as (copy, _invoked, _record):
        assert copy["source_commit"] == commit
        assert trees.git(Path(copy["root"]), "remote") == ""
    trusted = [command for command in commands if any(value.startswith("safe.directory=") for value in command)]
    assert trusted
    for command in trusted:
        assert [value for value in command if value.startswith("safe.directory=")] == [
            "safe.directory=" + holder.as_posix(), "safe.directory=" + git_dir.as_posix()]
        assert "--global" not in command and "safe.directory=*" not in command


@pytest.mark.parametrize("shape", ["ordinary", "linked", "detached", "borrowed"])
def test_copy_has_committed_tree_history_and_no_inherited_git_route(tmp_path, monkeypatch, shape):
    holder = repository(tmp_path)
    ancestor = git(holder, "rev-parse", "HEAD").stdout.strip().decode()
    (holder / ".gitignore").write_bytes(b"ignored-note\n")
    (holder / "fixture.txt").write_bytes(b"committed second revision\n")
    git(holder, "add", ".")
    git(holder, "-c", "user.name=fixture", "-c", "user.email=f@x", "commit", "-m", "second")
    if shape == "linked":
        source = tmp_path / "linked"
        git(holder, "worktree", "add", "-b", "linked", str(source))
        holder = source
    elif shape == "borrowed":
        source = tmp_path / "borrowed"
        git(holder, "clone", "--shared", str(holder), str(source))
        holder = source
        assert (holder / ".git/objects/info/alternates").is_file()
    elif shape == "detached":
        git(holder, "checkout", "--detach")
    commit = git(holder, "rev-parse", "HEAD").stdout.strip().decode()
    (holder / "fixture.txt").write_bytes(b"staged note\n")
    git(holder, "add", "fixture.txt")
    (holder / "fixture.txt").write_bytes(b"unstaged note\n")
    (holder / "loose-note").write_bytes(b"untracked")
    (holder / "ignored-note").write_bytes(b"ignored")
    before = lifecycle.content_snapshot(holder)
    other = repository(tmp_path, "other")
    bindings = {"GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other),
                "GIT_COMMON_DIR": str(other / ".git"), "GIT_INDEX_FILE": str(other / ".git/index"),
                "GIT_OBJECT_DIRECTORY": str(other / ".git/objects"),
                "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(other / ".git/objects")}
    for key, value in bindings.items():
        monkeypatch.setenv(key, value)
    with trees.checkout(holder, tmp_path / "bundle/result.md", work="fixture#1", instalment=None,
                        holder_session_id="holder") as (copy, _invoked, _record):
        root = Path(copy["root"])
        assert copy["source_commit"] == commit
        assert (root / "fixture.txt").read_bytes().replace(b"\r\n", b"\n") == b"committed second revision\n"
        assert not (root / "loose-note").exists() and not (root / "ignored-note").exists()
        assert trees.git(root, "cat-file", "-e", ancestor + "^{commit}") == ""
        assert trees.git(root, "remote") == ""
        assert trees.git(root, "rev-parse", "--abbrev-ref", "HEAD") == "HEAD"
        assert trees.git(root, "config", "--local", "core.longpaths") == "true"
        assert trees.git(root, "status", "--porcelain=v1") == ""
        assert not (root / ".git/objects/info/alternates").exists()
    assert not root.exists()
    with trees.isolated_git_environment():
        assert lifecycle.content_snapshot(holder) == before
    assert all(os.environ[key] == value for key, value in bindings.items())


def test_failed_copy_keeps_draft_index_branches_and_changed_head(tmp_path):
    holder = repository(tmp_path)
    output = tmp_path / "bundle/result.md"
    with trees.checkout(holder, output, work="fixture#1", instalment=None,
                        holder_session_id="holder") as (copy, invoked, _record):
        root = Path(copy["root"])
        invoked["value"] = True
        trees.git(root, "switch", "-c", "author")
        (root / "draft").write_bytes(b"author working state")
        trees.git(root, "add", "draft")
        trees.git(root, "-c", "user.name=f", "-c", "user.email=f@x", "commit", "-m", "draft")
        (root / "staged").write_bytes(b"staged state")
        trees.git(root, "add", "staged")
        before = lifecycle.content_snapshot(root)
    try:
        assert root.exists()
        assert lifecycle.content_snapshot(root) == before
        assert trees._read(copy["lifecycle_record"])["state"] == "retained"
        trees.prove(copy)  # Changed HEAD and dirty index remain lawful for resume.
    finally:
        assert trees.dispose(copy)["state"] == "removed"


def test_retained_author_can_prune_original_commit_without_losing_its_git_state(tmp_path):
    holder = repository(tmp_path)
    with trees.checkout(holder, tmp_path / "bundle/result.md", work="fixture#1", instalment=None,
                        holder_session_id="holder") as (copy, invoked, _record):
        invoked["value"] = True
        root = Path(copy["root"])
        trees.git(root, "switch", "--orphan", "author-orphan")
        (root / "draft").write_bytes(b"orphan author draft")
        trees.git(root, "add", "draft")
        trees.git(root, "-c", "user.name=f", "-c", "user.email=f@x", "commit", "-m", "orphan draft")
        for ref in trees.git(root, "for-each-ref", "--format=%(refname)", "refs/heads", "refs/tags").splitlines():
            if ref != "refs/heads/author-orphan":
                trees.git(root, "update-ref", "-d", ref)
        trees.git(root, "reflog", "expire", "--expire=now", "--all")
        trees.git(root, "gc", "--prune=now")
        assert git(root, "cat-file", "-e", copy["source_commit"], check=False).returncode != 0
        before = lifecycle.content_snapshot(root)
    try:
        trees.prove(copy)
        assert lifecycle.content_snapshot(root) == before
        assert trees._read(copy["lifecycle_record"])["artifact_copy"]["source_commit"] == copy["source_commit"]
    finally:
        assert trees.dispose(copy)["state"] == "removed"


@pytest.mark.parametrize("damage", ["remote", "alternates", "worktree", "external-worktree", "substituted", "linked-storage"])
def test_resume_proof_refuses_route_back_or_substituted_directory(tmp_path, damage):
    holder = repository(tmp_path)
    with trees.checkout(holder, tmp_path / "bundle/result.md", work="fixture#1", instalment=None,
                        holder_session_id="holder") as (copy, invoked, _record):
        invoked["value"] = True
    root = Path(copy["root"])
    try:
        if damage == "remote":
            trees.git(root, "remote", "add", "holder", str(holder))
        elif damage == "alternates":
            (root / ".git/objects/info/alternates").write_bytes(str(holder / ".git/objects").encode())
        elif damage == "worktree":
            (root / ".git/worktrees").mkdir()
        elif damage == "external-worktree":
            trees.git(root, "config", "core.worktree", str(holder))
        elif damage == "linked-storage":
            pack = root / ".git/objects/pack"
            pack.rmdir()
            if os.name == "nt":
                result = subprocess.run(["cmd", "/c", "mklink", "/J", str(pack), str(holder / ".git/objects/pack")],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                assert result.returncode == 0
            else:
                pack.symlink_to(holder / ".git/objects/pack", target_is_directory=True)
        else:
            copy = {**copy, "directory_identity": {"device": 0, "inode": 0}}
        with pytest.raises(trees.ArtifactTreeError):
            trees.prove(copy)
    finally:
        if damage == "substituted":
            copy["directory_identity"] = trees._identity(root)
        assert trees.dispose(copy)["state"] == "removed"
        assert (holder / "fixture.txt").read_bytes() == b"fixture\n"


def test_disposal_positive_and_protected_negative_controls(tmp_path):
    holder = repository(tmp_path)
    with trees.checkout(holder, tmp_path / "bundle/result.md", work="fixture#1", instalment=None,
                        holder_session_id="holder") as (copy, invoked, _record):
        invoked["value"] = True
    bad = {**copy, "root": str(holder), "temporary_parent": str(holder.parent),
           "directory_identity": trees._identity(holder)}
    assert trees.dispose(bad)["state"] == "removal_failed"
    assert trees.dispose(copy, forbidden=[Path(copy["root"])])["state"] == "removal_failed"
    assert holder.exists() and Path(copy["root"]).exists()
    assert trees.dispose(copy)["state"] == "removed"


def test_disposal_does_not_follow_nested_directory_link(tmp_path):
    holder = repository(tmp_path)
    with trees.checkout(holder, tmp_path / "bundle/result.md", work="fixture#1", instalment=None,
                        holder_session_id="holder") as (copy, _invoked, _record):
        root = Path(copy["root"])
        link = root / "holder-link"
        if os.name == "nt":
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(holder)],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            assert result.returncode == 0
        else:
            link.symlink_to(holder, target_is_directory=True)
    assert not root.exists()
    assert (holder / "fixture.txt").read_bytes() == b"fixture\n"


@pytest.mark.parametrize("failure", ["permission", "deadline"])
def test_bounded_removal_failure_names_residue(tmp_path, monkeypatch, failure):
    holder = repository(tmp_path)
    with trees.checkout(holder, tmp_path / "bundle/result.md", work="fixture#1", instalment=None,
                        holder_session_id="holder") as (copy, invoked, _record):
        invoked["value"] = True
    with monkeypatch.context() as m:
        def refusal(*_args, **_kwargs):
            raise PermissionError("injected permission refusal") if failure == "permission" else TimeoutError("spent cleanup window")
        if failure == "permission":
            m.setattr(trees, "run_process", refusal)
        else:
            m.setattr(lifecycle, "probe_timeout", refusal)
        result = trees.dispose(copy)
        assert result["state"] == "removal_failed" and result["remaining_path"] == copy["root"]
        assert result["reason"]
    assert trees.dispose(copy)["state"] == "removed"


@pytest.mark.parametrize("legacy_version", ["0.185.0", "0.186.0"])
def test_legacy_provenance_is_distinct_from_corrupt_new_record(tmp_path, legacy_version):
    bundle = tmp_path / "result.md.run.json"
    assert trees.provenance({"producer_version": legacy_version}, bundle) is None
    with pytest.raises(trees.ArtifactTreeError, match="conflicting artifact copy provenance"):
        trees.provenance({"producer_version": legacy_version, "artifact_copy": {}}, bundle)
    with pytest.raises(trees.ArtifactTreeError, match="lacks artifact provenance"):
        trees.provenance({"producer_version": trees.MECHANISM_VERSION}, bundle)


@pytest.mark.parametrize("removal_fails", [False, True])
def test_prelaunch_clone_failure_never_launches_and_names_partial_residue(tmp_path, monkeypatch, capsys, removal_fails):
    holder = repository(tmp_path)
    original_git, original_dispose = trees.git, trees.dispose
    output = tmp_path / "bundle/result.md"
    def failed_clone(root, *args, **kwargs):
        if args[0] == "clone":
            raise trees.ArtifactTreeError("injected clone failure")
        return original_git(root, *args, **kwargs)
    with monkeypatch.context() as m:
        m.setattr(trees, "git", failed_clone)
        if removal_fails:
            m.setattr(trees, "dispose", lambda copy, **_k: {"state": "removal_failed",
                "remaining_path": copy["root"], "reason": "injected permission failure"})
        with pytest.raises(trees.ArtifactTreeError, match="clone failure"):
            with trees.checkout(holder, output, work="fixture#1", instalment=None, holder_session_id="holder"):
                pytest.fail("partial clone launched an author")
    record = trees._read(str(output) + ".artifact-copy.json")
    root = Path(record["artifact_copy"]["root"])
    assert record["state"] == ("removal_failed" if removal_fails else "removed")
    assert str(root) in capsys.readouterr().out.replace("\\\\", "\\")
    if removal_fails:
        assert root.exists() and original_dispose(record["artifact_copy"])["state"] == "removed"


def test_git_copy_operations_obey_caller_deadline_and_clear_config_binding(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.worktree")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(tmp_path))
    def captured(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, b"done", b"")
    monkeypatch.setattr(trees, "run_process", captured)
    with lifecycle.deadline_scope(lifecycle.Deadline(30)):
        assert trees.git(tmp_path, "clone", "source", "copy") == "done"
    assert 0 < calls[0][1]["timeout"] <= 20
    assert not any(trees._binding(key) for key in calls[0][1]["env"])


def test_unproved_clone_process_stop_retains_partial_copy_without_launch(tmp_path, monkeypatch, capsys):
    holder = repository(tmp_path)
    original = trees.run_process
    output = tmp_path / "bundle/result.md"
    def unproved(command, **kwargs):
        if "clone" in command:
            result = subprocess.CompletedProcess(command, 0, b"", b"")
            result.cleanup_proven = False
            return result
        return original(command, **kwargs)
    with monkeypatch.context() as m:
        m.setattr(trees, "run_process", unproved)
        with pytest.raises(trees.ArtifactTreeError, match="cleanup is unproved"):
            with trees.checkout(holder, output, work="fixture#1", instalment=None, holder_session_id="holder"):
                pytest.fail("unproved clone launched an author")
    record = trees._read(str(output) + ".artifact-copy.json")
    copy = record["artifact_copy"]
    assert record["state"] == "retained" and Path(copy["root"]).exists()
    assert copy["root"] in capsys.readouterr().out.replace("\\\\", "\\")
    assert trees.dispose(copy)["state"] == "removed"


def test_disposal_requires_proved_helper_stop_even_after_directory_removal(tmp_path, monkeypatch):
    holder = repository(tmp_path)
    with trees.checkout(holder, tmp_path / "bundle/result.md", work="fixture#1", instalment=None,
                        holder_session_id="holder") as (copy, invoked, _record):
        invoked["value"] = True
    original = trees.run_process
    def unproved(*args, **kwargs):
        result = original(*args, **kwargs)
        result.cleanup_proven = False
        return result
    with monkeypatch.context() as m:
        m.setattr(trees, "run_process", unproved)
        result = trees.dispose(copy)
    assert result["state"] == "removal_failed" and "cleanup is unproved" in result["reason"]
    assert result["remaining_path"] == copy["root"] and not Path(copy["root"]).exists()


def test_independent_copy_cannot_substitute_for_another_bundle_authority(tmp_path):
    holder = repository(tmp_path)
    copies = []
    for name in ("first", "second"):
        with trees.checkout(holder, tmp_path / name / "result.md", work="fixture#1", instalment=None,
                            holder_session_id="holder") as (copy, invoked, _record):
            invoked["value"] = True
            copies.append(copy)
    try:
        first, second = copies
        substituted = {**second, "lifecycle_record": first["lifecycle_record"]}
        request = {"root": second["root"], "artifact_copy": substituted, "work": "fixture#1",
                   "instalment": None, "holder_session_id": "holder"}
        bundle = str(first["lifecycle_record"]).removesuffix(".artifact-copy.json") + ".run.json"
        trees.prove(substituted)  # An independent Git root alone is insufficient authority.
        with pytest.raises(trees.ArtifactTreeError, match="conflicts with work or holder"):
            trees.provenance(request, bundle)
    finally:
        for copy in copies:
            assert trees.dispose(copy)["state"] == "removed"


def test_temporary_directory_inside_holder_is_refused_before_allocation(tmp_path, monkeypatch):
    holder = repository(tmp_path)
    before = set(holder.iterdir())
    monkeypatch.setattr(trees.tempfile, "gettempdir", lambda: str(holder))
    with pytest.raises(trees.ArtifactTreeError, match="overlaps"):
        with trees.checkout(holder, tmp_path / "bundle/result.md", work="fixture#1", instalment=None,
                            holder_session_id="holder"):
            pytest.fail("allocated a copy inside the holder")
    assert set(holder.iterdir()) == before

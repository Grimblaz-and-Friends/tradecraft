"""Real Git graph and publication checks for overlap and holder catch-up."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import work
import use_history
import version_policy
import holder_tree_guard


SPEC = {"path": "version.json", "field": "version", "increment": "minor"}
RULES = {"schema_version": 1, "rules": [{"include": ["src/**", "version.json"], "exclude": []}],
         "version": SPEC}


def git(root, *args, check=True):
    result = subprocess.run(["git", "-C", str(root), *args], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check:
        assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout.decode("utf-8").strip()


def commit(root, path, content, message="fixture change"):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content.encode())
    git(root, "add", "--", path)
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


class PublicGit:
    """Present public REST graph/blob facts derived from actual Git objects."""
    def __init__(self, root):
        self.root = root
        self.calls = []

    def get(self, endpoint, paginate=False):
        self.calls.append(endpoint)
        suffix = endpoint.split("example/product/", 1)[-1]
        if suffix.startswith("compare/"):
            left, right = suffix.removeprefix("compare/").split("...")
            common = git(self.root, "merge-base", left, right)
            revisions = git(self.root, "rev-list", "--reverse", f"{left}..{right}").splitlines()
            behind = git(self.root, "rev-list", "--count", f"{right}..{left}")
            status = "identical" if left == right else "ahead" if common == left else "behind" if common == right else "diverged"
            files = []
            for line in git(self.root, "diff", "--name-status", "-M", common, right).splitlines():
                fields = line.split("\t")
                item = {"filename": fields[-1], "status": "renamed" if fields[0].startswith("R") else {"A": "added", "D": "removed"}.get(fields[0], "modified")}
                if fields[0].startswith("R"):
                    item["previous_filename"] = fields[1]
                files.append(item)
            return {"status": status, "ahead_by": len(revisions), "behind_by": int(behind),
                    "merge_base_commit": {"sha": common}, "commits": [{"sha": sha} for sha in revisions],
                    "files": files}
        if suffix.startswith("commits/"):
            revision = suffix.split("/", 1)[1].split("?")[0]
            parents = git(self.root, "show", "-s", "--format=%P", revision).split()
            paths = git(self.root, "diff", "--name-status", "-M", parents[0], revision).splitlines() if parents else []
            files = []
            for line in paths:
                fields = line.split("\t")
                item = {"filename": fields[-1], "status": "renamed" if fields[0].startswith("R") else {"A": "added", "D": "removed"}.get(fields[0], "modified")}
                if fields[0].startswith("R"):
                    item["previous_filename"] = fields[1]
                files.append(item)
            return {"parents": [{"sha": sha} for sha in parents], "files": files}
        if suffix.startswith("contents/"):
            path, revision = suffix.removeprefix("contents/").split("?ref=")
            raw = subprocess.run(["git", "-C", str(self.root), "show", f"{revision}:{path}"],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if raw.returncode:
                raise ValueError("declared contents unavailable")
            return {"encoding": "base64", "content": base64.b64encode(raw.stdout).decode()}
        if suffix.startswith("git/trees/"):
            revision = suffix.split("git/trees/", 1)[1].split("?")[0]
            entries = []
            for line in git(self.root, "ls-tree", "-r", revision).splitlines():
                identity, path = line.split("\t")
                mode, kind, sha = identity.split()
                entries.append({"path": path, "mode": mode, "type": kind, "sha": sha})
            return {"truncated": False, "tree": entries}
        if suffix.startswith("git/blobs/"):
            raw = subprocess.run(["git", "-C", str(self.root), "cat-file", "blob", suffix.split("/")[-1]],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
            return {"encoding": "base64", "content": base64.b64encode(raw).decode()}
        raise KeyError(endpoint)


def current_paths(root, base, head):
    common = git(root, "merge-base", base, head)
    paths = set()
    for line in git(root, "diff", "--name-status", "-M", common, head).splitlines():
        fields = line.split("\t")
        paths.update(fields[1:])
    return sorted(paths)


def apply(transport, repo, ancestor, head, base, rules, buys):
    return use_history.application(transport, repo, ancestor, head, base, rules, buys,
                                   current_paths(transport.root, base, head))


@pytest.fixture
def graph(tmp_path):
    root = tmp_path / "holder"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.test")
    commit(root, "version.json", '{"version":"1.2.3","name":"fixture"}\n')
    commit(root, "src/own", "old\n")
    commit(root, "src/other", "old\n")
    branch = "tradecraft/12-fixture"
    implementation = tmp_path / "implementation"
    git(root, "worktree", "add", "-b", branch, str(implementation))
    own = commit(implementation, "src/own", "own\n")
    return root, implementation, branch, own


def application(graph, incoming_path="src/other", content="incoming\n", extra=None):
    root, implementation, branch, ancestor = graph
    base = commit(root, incoming_path, content)
    git(implementation, "merge", "--no-commit", "--no-ff", base, check=False)
    if extra:
        (implementation / extra).write_bytes(b"extra runtime edit\n")
        git(implementation, "add", extra)
    git(implementation, "commit", "-m", "import base")
    head = git(implementation, "rev-parse", "HEAD")
    return apply(PublicGit(root), "example/product", ancestor, head, base, RULES, work.use_required)


def test_disjoint_import_carries_and_reports_the_observed_graph(graph):
    result = application(graph)
    assert result["applicable"] and result["carried"]
    assert result["evidence_head"] == graph[3]
    assert result["current_head"] == git(graph[1], "rev-parse", "HEAD")
    assert result["incoming_commits"][0] == {"sha": result["observed_base"], "paths": ["src/other"], "overlap": [], "origin": "base"}
    assert "src/own" in result["changed_paths"]
    assert result["merge_commits"] == [{"sha": result["current_head"],
                                        "brought_paths": ["src/other"], "own_paths": []}]


def test_same_file_overlap_rebuys_even_on_separate_lines(graph):
    root, implementation, branch, _ = graph
    # Use a shared file with nonconflicting edits on both sides.
    common = git(root, "merge-base", "main", branch)
    git(implementation, "reset", "--hard", common)
    commit(root, "src/shared", "one\n" + "gap\n" * 12 + "two\n")
    git(implementation, "merge", "--ff-only", "main")
    ancestor = commit(implementation, "src/shared", "own\n" + "gap\n" * 12 + "two\n")
    result = application((root, implementation, branch, ancestor), "src/shared", "one\n" + "gap\n" * 12 + "incoming\n")
    assert not result["applicable"]
    assert result["incoming_commits"][0]["overlap"] == ["src/shared"]


def test_authored_resolution_edit_cannot_hide_in_import(graph):
    result = application(graph, extra="src/own")
    assert not result["applicable"] and "authored merge edit" in result["reason"]
    assert result["merge_commits"][-1]["brought_paths"] == ["src/other"]
    assert result["merge_commits"][-1]["own_paths"] == ["src/own"]


def test_merge_restoring_file_to_base_rebuys_without_current_overlap(graph):
    result = application(graph, extra="src/own")
    # Rebuild the merge to use base's unchanged content instead of an extra blob.
    root, implementation, _, ancestor = graph
    base = result["observed_base"]
    git(implementation, "reset", "--hard", ancestor)
    git(implementation, "merge", "--no-commit", "--no-ff", base)
    (implementation / "src/own").write_bytes(b"old\n")
    git(implementation, "add", "src/own")
    git(implementation, "commit", "-m", "hidden authored restore")
    result = apply(PublicGit(root), "example/product", ancestor,
                                    git(implementation, "rev-parse", "HEAD"), base, RULES, work.use_required)
    assert not result["applicable"] and "src/own" not in result["changed_paths"]
    assert result["merge_commits"][-1]["own_paths"] == ["src/own"]
    assert "authored merge edit" in result["reason"]


def test_merge_other_parent_not_base_reachable_gets_no_split(graph):
    root, implementation, _, ancestor = graph
    base = git(root, "rev-parse", "HEAD")
    git(root, "switch", "-c", "unrelated-side")
    side = commit(root, "src/own", "outside base\n")
    git(implementation, "merge", "--no-commit", "--no-ff", side, check=False)
    (implementation / "src/own").write_bytes(b"old\n")
    git(implementation, "add", "src/own")
    git(implementation, "commit", "-m", "resolve unrelated side to base content")
    result = apply(PublicGit(root), "example/product", ancestor,
                   git(implementation, "rev-parse", "HEAD"), base, RULES, work.use_required)
    assert not result["applicable"]
    assert result["incoming_commits"] == []
    assert result["merge_commits"][-1] == {"sha": result["current_head"],
                                          "brought_paths": [], "own_paths": ["src/own"]}


def test_merge_both_sides_changed_and_resolved_to_base_keeps_known_residual(graph):
    root, implementation, _, ancestor = graph
    base = commit(root, "src/own", "incoming\n")
    git(implementation, "merge", "--no-commit", "--no-ff", base, check=False)
    (implementation / "src/own").write_bytes(b"incoming\n")
    git(implementation, "add", "src/own")
    git(implementation, "commit", "-m", "resolve both sides to base")
    result = apply(PublicGit(root), "example/product", ancestor,
                   git(implementation, "rev-parse", "HEAD"), base, RULES, work.use_required)
    assert result["applicable"] and "src/own" not in result["changed_paths"]
    assert result["merge_commits"][-1]["brought_paths"] == ["src/own"]
    assert result["merge_commits"][-1]["own_paths"] == []


@pytest.mark.parametrize("missing", ["files", "merge-base", "truncated"])
def test_unavailable_merge_side_history_grants_no_carry(graph, missing):
    root, implementation, _, ancestor = graph
    result = application(graph)
    transport = PublicGit(root)
    original = transport.get
    common = git(root, "merge-base", ancestor, result["observed_base"])
    def unavailable(endpoint, paginate=False):
        value = original(endpoint, paginate)
        if missing == "merge-base" and endpoint.endswith(f"compare/{ancestor}...{result['observed_base']}"):
            value.pop("merge_base_commit")
        if endpoint.endswith(f"compare/{common}...{result['observed_base']}"):
            if missing == "files":
                value.pop("files")
            elif missing == "truncated":
                value["files"] *= 300
        return value
    transport.get = unavailable
    with pytest.raises(ValueError, match="merge-side file list"):
        apply(transport, "example/product", ancestor, result["current_head"],
              result["observed_base"], RULES, work.use_required)


def test_touched_then_reverted_authored_work_rebuys(graph):
    root, implementation, _, ancestor = graph
    commit(implementation, "src/own", "later\n")
    commit(implementation, "src/own", "own\n")
    result = apply(PublicGit(root), "example/product", ancestor,
                                    git(implementation, "rev-parse", "HEAD"), git(root, "rev-parse", "HEAD"), RULES, work.use_required)
    assert not result["applicable"]


@pytest.mark.parametrize("operation", ["rename", "delete", "revert"])
def test_reverted_authored_path_does_not_overlap_incoming_history(graph, operation):
    root, implementation, branch, ancestor = graph
    # Author touches the matching path before use, including a reverted edit.
    ancestor = commit(implementation, "src/other", "authored\n")
    ancestor = commit(implementation, "src/other", "old\n")
    if operation == "rename":
        git(root, "mv", "src/other", "renamed.txt")
        git(root, "commit", "-am", "rename")
    elif operation == "delete":
        git(root, "rm", "src/other")
        git(root, "commit", "-m", "delete")
    else:
        commit(root, "src/other", "changed\n")
        commit(root, "src/other", "old\n")
    base = git(root, "rev-parse", "HEAD")
    git(implementation, "merge", "--no-ff", "-m", "import", base)
    result = apply(PublicGit(root), "example/product", ancestor,
                                    git(implementation, "rev-parse", "HEAD"), base, RULES, work.use_required)
    assert result["applicable"]
    assert all("src/other" not in item["overlap"] for item in result["incoming_commits"])


@pytest.mark.parametrize("extra", [False, True])
def test_only_declared_version_member_leaves_overlap(graph, extra):
    root, implementation, branch, ancestor = graph
    ancestor = commit(implementation, "version.json", '{"version":"1.3.0","name":"' + ("own" if extra else "fixture") + '"}\n')
    base = commit(root, "version.json", '{"version":"1.4.0","name":"' + ("changed" if extra else "fixture") + '"}\n')
    git(implementation, "merge", "--no-commit", "--no-ff", base, check=False)
    (implementation / "version.json").write_bytes(('{"version":"1.5.0","name":"' + ("changed" if extra else "fixture") + '"}\n').encode())
    git(implementation, "add", "version.json")
    git(implementation, "commit", "-m", "version catch-up")
    result = apply(PublicGit(root), "example/product", ancestor,
                                    git(implementation, "rev-parse", "HEAD"), base, RULES, work.use_required)
    assert result["applicable"] is (not extra)
    assert result["merge_commits"][-1]["brought_paths"] == ["version.json"]
    assert result["merge_commits"][-1]["own_paths"] == []


def test_ordinary_authored_version_bump_still_buys_use(graph):
    root, implementation, _, ancestor = graph
    head = commit(implementation, "version.json", '{"version":"1.3.0","name":"fixture"}\n')
    result = apply(PublicGit(root), "example/product", ancestor, head,
                                    git(root, "rev-parse", "HEAD"), RULES, work.use_required)
    assert not result["applicable"]


def test_modified_version_contents_ignore_mode_as_the_gate_does(graph):
    root, implementation, _, ancestor = graph
    ancestor = commit(implementation, "version.json", '{"version":"1.3.0","name":"fixture"}\n')
    (root / "version.json").write_bytes(b'{"version":"1.4.0","name":"fixture"}\n')
    git(root, "add", "version.json")
    git(root, "update-index", "--chmod=+x", "version.json")
    git(root, "commit", "-m", "base version content and mode")
    base = git(root, "rev-parse", "HEAD")
    git(implementation, "merge", "--no-commit", "--no-ff", base, check=False)
    (implementation / "version.json").write_bytes(b'{"version":"1.5.0","name":"fixture"}\n')
    git(implementation, "add", "version.json")
    git(implementation, "commit", "-m", "version catch-up")
    result = apply(PublicGit(root), "example/product", ancestor,
                   git(implementation, "rev-parse", "HEAD"), base, RULES, work.use_required)
    assert result["applicable"]


def test_other_member_in_version_file_still_overlaps_current_pr(graph):
    root, implementation, _, ancestor = graph
    ancestor = commit(implementation, "version.json", '{"version":"1.3.0","name":"fixture"}\n')
    base = commit(root, "version.json", '{"version":"1.4.0","name":"incoming"}\n')
    git(implementation, "merge", "--no-commit", "--no-ff", base, check=False)
    (implementation / "version.json").write_bytes(b'{"version":"1.5.0","name":"incoming"}\n')
    git(implementation, "add", "version.json")
    git(implementation, "commit", "-m", "import another member with prescribed bump")
    result = apply(PublicGit(root), "example/product", ancestor,
                                    git(implementation, "rev-parse", "HEAD"), base, RULES, work.use_required)
    assert not result["applicable"]
    assert result["incoming_commits"][0]["paths"] == ["version.json"]
    assert result["incoming_commits"][0]["overlap"] == ["version.json"]


@pytest.mark.parametrize("part,expected", [("major", "2.0.0"), ("minor", "1.3.0"), ("patch", "1.2.4")])
def test_increment_preserves_other_bytes(part, expected):
    spec = {**SPEC, "increment": part}
    original = b'{ "name": {"version": "nested"}, "version" : "1.2.3" }\r\n'
    version = version_policy.increment(original, spec)
    assert version == expected
    assert version_policy.replace_field(original, spec, version) == original.replace(b'"1.2.3"', json.dumps(version).encode())


@pytest.mark.parametrize("patch", [{"path": "../escape"}, {"path": "C:/escape"}, {"path": "x\\y"},
                                   {"increment": "build"}, {"increment": []}, {"field": ""}, {"field": " "}, {"path": " "}, {"path": "bad\npath"}])
def test_invalid_declaration_is_refused(patch):
    with pytest.raises(ValueError):
        version_policy.declaration({"version": {**SPEC, **patch}})


class CatchTransport(PublicGit):
    def __init__(self, root, implementation, branch, remote):
        super().__init__(root)
        self.implementation, self.branch, self.remote = implementation, branch, remote

    def get(self, endpoint, paginate=False):
        if endpoint.endswith("/pulls/7"):
            remote_head = git(self.root, "ls-remote", "--heads", str(self.remote), f"refs/heads/{self.branch}").split()[0]
            return {"number": 7, "state": "open", "draft": True, "mergeable": True,
                    "head": {"sha": remote_head, "ref": self.branch, "repo": {"full_name": "example/product"}},
                    "base": {"sha": git(self.root, "rev-parse", "main"), "ref": "main",
                             "repo": {"id": 1, "full_name": "example/product"}}}
        if "/git/ref/heads/" in endpoint:
            return {"object": {"sha": git(self.root, "rev-parse", "main")}}
        return super().get(endpoint, paginate)


@pytest.fixture
def registered(graph, tmp_path, monkeypatch):
    root, implementation, branch, ancestor = graph
    remote = tmp_path / "remote.git"
    git(root, "init", "--bare", str(remote))
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "-u", "origin", "main")
    git(implementation, "push", "-u", "origin", branch)
    monkeypatch.setattr(work, "registry_path", lambda: tmp_path / "registry.json")
    work.register_worktree(implementation, "example/product", 12, None, "holder-id", holder_root=root, branch=branch)
    transport = CatchTransport(root, implementation, branch, remote)
    def fresh_state(*args):
        state = work.WorkState("example/product", 12, {"state": "open"}, pr=transport.get("repos/example/product/pulls/7"))
        state.synchronization = {"base": {"sha": git(root, "rev-parse", "main")}, "behind": False,
                                 "strict": False, "mergeability_known": True, "uncertainties": []}
        return state
    monkeypatch.setattr(work, "read_state", fresh_state)
    state = fresh_state()
    return root, implementation, branch, remote, transport, state


@pytest.mark.parametrize("version,conflict", [(False, False), (True, False), (True, True)])
def test_holder_catch_up_lands_checked_merge_without_launch(registered, version, conflict, monkeypatch, capsys):
    root, implementation, branch, remote, transport, state = registered
    if version:
        commit(root, "version.json", '{"version":"1.4.0","name":"fixture"}\n')
        if conflict:
            commit(implementation, "version.json", '{"version":"1.3.0","name":"fixture"}\n')
            git(implementation, "push")
    else:
        commit(root, "src/other", "incoming\n")
    git(root, "push", "origin", "main")
    start = git(implementation, "rev-parse", "HEAD")
    monkeypatch.setattr(work, "_implementer_vendor", lambda *args, **kw: pytest.fail("catch-up consulted recipient settings"))
    rules = RULES if version else {key: value for key, value in RULES.items() if key != "version"}
    assert work._execute_catch_up(transport, state, root, None, "holder-id", rules) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "holder-owned" and result["dispatch"] is False
    head = git(implementation, "rev-parse", "HEAD")
    assert git(implementation, "show", "-s", "--format=%P", head).split() == [start, result["pinned_base"]]
    assert git(root, "ls-remote", "--heads", str(remote), f"refs/heads/{branch}").split()[0] == head
    assert git(implementation, "branch", "--show-current") == branch
    if version:
        assert json.loads((implementation / "version.json").read_bytes())["version"] == "1.5.0"
    assert work._execute_catch_up(transport, state, root, None, "holder-id", rules) == 0
    assert json.loads(capsys.readouterr().out)["reason"] == "already-up-to-date"
    assert git(implementation, "rev-parse", "HEAD") == head


@pytest.mark.parametrize("collision", ["none", "clean", "conflict"])
def test_catch_up_adjusts_only_base_changed_version_and_carries_use(registered, collision, capsys):
    root, implementation, branch, remote, transport, state = registered
    if collision != "clean":
        own_version = "1.8.0" if collision == "none" else "1.3.0"
        commit(implementation, "version.json", json.dumps({"version": own_version, "name": "fixture"}) + "\n")
        git(implementation, "push")
    if collision == "none":
        commit(root, "src/other", "incoming\n")
    else:
        commit(root, "version.json", '{"version":"1.4.0","name":"fixture"}\n')
    git(root, "push", "origin", "main")
    start = git(implementation, "rev-parse", "HEAD")
    work._execute_catch_up(transport, state, root, None, "holder-id", RULES)
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "holder-owned"
    head = git(implementation, "rev-parse", "HEAD")
    expected = "1.8.0" if collision == "none" else "1.5.0"
    assert json.loads((implementation / "version.json").read_bytes())["version"] == expected
    assert report["version_adjustment"] == (None if collision == "none" else {**SPEC, "value": expected})
    carry = apply(transport, "example/product", start, head, report["pinned_base"], RULES, work.use_required)
    assert carry["applicable"] and carry["carried"], carry
    if collision == "none":
        assert "version.json" not in carry["merge_commits"][0]["own_paths"]


def test_catch_up_fetch_uses_selected_remote_and_refuses_a_moved_pin(registered, monkeypatch):
    root, implementation, branch, remote, transport, state = registered
    commit(root, "src/other", "incoming\n")
    git(root, "push", "origin", "main")
    start = git(implementation, "rev-parse", "HEAD")
    original = work._git
    fetches = []
    def move_before_fetch(arguments, cwd):
        if arguments[:2] == ["fetch", "--no-tags"]:
            fetches.append(arguments)
            commit(root, "src/other", "base advanced\n")
            git(root, "push", "origin", "main")
        return original(arguments, cwd)
    monkeypatch.setattr(work, "_git", move_before_fetch)
    with pytest.raises(work.WorkError, match="base moved during fetch"):
        work._execute_catch_up(transport, state, root, None, "holder-id", RULES)
    assert fetches == [["fetch", "--no-tags", "origin", "refs/heads/main"]]
    assert git(implementation, "rev-parse", "HEAD") == start
    assert git(implementation, "status", "--porcelain") == ""


def test_precommit_failure_aborts_uncommitted_catch_up_and_allows_retry(registered, capsys):
    root, implementation, branch, remote, transport, state = registered
    commit(root, "src/other", "incoming\n")
    git(root, "push", "origin", "main")
    start = git(implementation, "rev-parse", "HEAD")
    hook = Path(git(implementation, "rev-parse", "--git-path", "hooks/pre-commit"))
    if not hook.is_absolute():
        hook = implementation / hook
    hook.write_bytes(b"#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    work._execute_catch_up(transport, state, root, None, "holder-id", RULES)
    refused = json.loads(capsys.readouterr().out)
    assert refused["status"] == "refused"
    assert git(implementation, "rev-parse", "HEAD") == start
    assert git(implementation, "status", "--porcelain") == ""
    assert not (implementation / git(implementation, "rev-parse", "--git-path", "MERGE_HEAD")).exists()
    assert git(root, "ls-remote", "--heads", str(remote), f"refs/heads/{branch}").split()[0] == start
    hook.unlink()
    work._execute_catch_up(transport, state, root, None, "holder-id", RULES)
    landed = json.loads(capsys.readouterr().out)
    assert landed["status"] == "holder-owned"
    assert git(implementation, "show", "-s", "--format=%P", landed["head"]).split() == [start, landed["pinned_base"]]
    assert git(root, "ls-remote", "--heads", str(remote), f"refs/heads/{branch}").split()[0] == landed["head"]


def test_failed_landing_preserves_merge_after_another_head_move(registered, monkeypatch, capsys):
    root, implementation, branch, remote, transport, state = registered
    pinned = commit(root, "src/other", "incoming\n")
    git(root, "push", "origin", "main")
    original = subprocess.run
    def failed_landing(arguments, **kwargs):
        if len(arguments) > 1 and Path(arguments[1]).name == "persist.py":
            git(implementation, "update-ref", f"refs/heads/{branch}", pinned)
            return subprocess.CompletedProcess(arguments, 1, b"not-persisted: branch moved\n", b"")
        return original(arguments, **kwargs)
    monkeypatch.setattr(work.subprocess, "run", failed_landing)
    work._execute_catch_up(transport, state, root, None, "holder-id", RULES)
    assert json.loads(capsys.readouterr().out)["status"] == "refused"
    assert git(implementation, "rev-parse", "HEAD") == pinned
    assert (implementation / git(implementation, "rev-parse", "--git-path", "MERGE_HEAD")).exists()


@pytest.mark.parametrize("path", ["src/own", "version.json"])
def test_non_version_conflict_aborts_and_returns_builder(registered, path, capsys):
    root, implementation, branch, remote, transport, state = registered
    if path == "version.json":
        commit(implementation, path, '{"version":"1.3.0","name":"own"}\n')
        git(implementation, "push")
        commit(root, path, '{"version":"1.4.0","name":"base"}\n')
    else:
        commit(root, path, "conflicting\n")
    git(root, "push", "origin", "main")
    start = git(implementation, "rev-parse", "HEAD")
    work._execute_catch_up(transport, state, root, None, "holder-id", RULES)
    result = json.loads(capsys.readouterr().out)
    assert result["reason"] == "builder-required"
    assert result["next"] == {"stage": "build", "continuity": "resume"}
    assert git(implementation, "rev-parse", "HEAD") == start
    assert git(implementation, "status", "--porcelain") == ""


def test_dirty_and_wrong_holder_are_refused(registered):
    root, implementation, branch, remote, transport, state = registered
    with pytest.raises(work.WorkError, match="holder identity"):
        work._execute_catch_up(transport, state, root, None, "another", RULES)
    (implementation / "unrelated").write_bytes(b"pending")
    with pytest.raises(work.WorkError, match="dirty content"):
        work._execute_catch_up(transport, state, root, None, "holder-id", RULES)


def test_failed_push_retry_never_merges_or_bumps_again(registered, capsys):
    root, implementation, branch, remote, transport, state = registered
    commit(root, "version.json", '{"version":"1.4.0","name":"fixture"}\n')
    git(root, "push", "origin", "main")
    hook = remote / "hooks" / "pre-receive"
    hook.write_bytes(b"#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    work._execute_catch_up(transport, state, root, None, "holder-id", RULES)
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "refused" and "push failed" in result["landing"]
    head = git(implementation, "rev-parse", "HEAD")
    assert len(git(implementation, "show", "-s", "--format=%P", head).split()) == 2
    work._execute_catch_up(transport, state, root, None, "holder-id", RULES)
    assert json.loads(capsys.readouterr().out)["reason"] == "checked-commit-publication-recovery-required"
    assert git(implementation, "rev-parse", "HEAD") == head


def test_holder_guard_accepts_entrance_and_refuses_direct_write(registered):
    root, implementation, branch, remote, transport, state = registered
    payload = {"tool_name": "Bash", "cwd": str(root), "tool_input": {
        "command": f'python "{LIB / "work.py"}" run catch-up --repo example/product --issue 12 --root "{root}" --holder-session-id holder-id'}}
    assert holder_tree_guard.decision(payload, [implementation]) is None
    payload = {"tool_name": "Write", "cwd": str(root), "tool_input": {"file_path": str(implementation / "src/own")}}
    assert "holder write denied" in holder_tree_guard.decision(payload, [implementation])


@pytest.mark.parametrize("bad", [b"not-json", b'[]', b'{"version": NaN}',
                                 b'{"version":"1.2.3","version":"1.2.4"}'])
def test_invalid_version_json_grants_no_exemption(bad):
    with pytest.raises(ValueError):
        version_policy.only_version(b'{"version":"1.2.3"}', bad, SPEC)


def test_version_comparison_masks_additions_and_removals_but_not_other_types():
    assert version_policy.only_version(b'{}', b'{"version": "release"}', SPEC)
    assert version_policy.only_version(b'{"version": "release"}', b'{}', SPEC)
    assert not version_policy.only_version(b'{"version":"1.2.3","other":true}', b'{"version":"1.2.4","other":1}', SPEC)
    assert not version_policy.only_version(b'{"version":"1.2.3","nested":{"version":"a"}}', b'{"version":"1.2.4","nested":{"version":"b"}}', SPEC)


@pytest.mark.parametrize("kind", ["incomplete", "unknown-parent"])
def test_incomplete_public_graph_grants_no_carry(graph, kind):
    root, implementation, branch, ancestor = graph
    result = application(graph)
    transport = PublicGit(root)
    original = transport.get
    def incomplete(endpoint, paginate=False):
        value = original(endpoint, paginate)
        if kind == "incomplete" and "/compare/" in endpoint:
            value["ahead_by"] += 1
        if kind == "unknown-parent" and "/commits/" in endpoint:
            value.pop("parents")
        return value
    transport.get = incomplete
    result = apply(transport, "example/product", ancestor, result["current_head"],
                   result["observed_base"], RULES, work.use_required)
    assert not result["applicable"]


def test_base_movement_aborts_only_this_endpoints_merge(registered, capsys):
    root, implementation, branch, remote, transport, state = registered
    commit(root, "src/other", "incoming\n")
    git(root, "push", "origin", "main")
    start = git(implementation, "rev-parse", "HEAD")
    original = transport.get
    reads = 0
    def moved(endpoint, paginate=False):
        nonlocal reads
        if endpoint.endswith("git/ref/heads/main"):
            reads += 1
            if reads == 2:
                return {"object": {"sha": "f" * 40}}
        return original(endpoint, paginate)
    transport.get = moved
    with pytest.raises(work.WorkError, match="moved before landing"):
        work._execute_catch_up(transport, state, root, None, "holder-id", RULES)
    assert git(implementation, "rev-parse", "HEAD") == start
    assert git(implementation, "status", "--porcelain") == ""


def test_hook_rewrite_is_not_published_and_remains_reviewable(registered, capsys):
    root, implementation, branch, remote, transport, state = registered
    commit(root, "src/other", "incoming\n")
    git(root, "push", "origin", "main")
    start = git(implementation, "rev-parse", "HEAD")
    hook = Path(git(implementation, "rev-parse", "--git-path", "hooks/pre-commit"))
    if not hook.is_absolute():
        hook = implementation / hook
    hook.write_bytes(b"#!/bin/sh\nprintf 'hook rewrite\\n' > src/other\ngit add src/other\n")
    hook.chmod(0o755)
    work._execute_catch_up(transport, state, root, None, "holder-id", RULES)
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "refused" and "differs from staged" in result["landing"]
    assert git(root, "ls-remote", "--heads", str(remote), f"refs/heads/{branch}").split()[0] == start
    assert (implementation / "src/other").read_bytes() == b"hook rewrite\n"


def test_shared_public_fixtures_have_the_same_entrance_interpretation():
    path = LIB.parent / "skills" / "work" / "references" / "proof-fixtures" / "v1-ancestor-use.json"
    for case in json.loads(path.read_bytes())["cases"]:
        class Transport:
            def get(self, endpoint, paginate=False):
                return deepcopy(case["records"][endpoint])
        result = use_history.application(Transport(), case["repository"], case["evidence_head"],
                                        case["head"], case["base"], case["policy"], work.use_required, case["changed_paths"])
        assert result["applicable"] is case["applicable"], case["name"]
        assert result["merge_commits"] == case["merge_commits"], case["name"]

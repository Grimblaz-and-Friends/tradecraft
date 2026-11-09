"""A launch's helpers stay in its tree, and its working copies and branches are compared (#963)."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import launch_bound
import tree_write_guard as guard

SESSION = "f3e5084f-7317-4d52-9d4f-fa0cdffc3775"
OWN = "a" * 32


# --- Row 1: the helper guard -------------------------------------------------

@pytest.fixture
def helper_config(tmp_path):
    root = tmp_path / "Tree"
    (root / ".claude" / "agents").mkdir(parents=True)
    dirs = {"user": tmp_path / "user-agents", "plugin": tmp_path / "plugin" / "agents",
            "builtin": tmp_path / "builtin" / "agents"}
    for path in dirs.values():
        path.mkdir(parents=True)
    agents = [{"path": str(dirs["user"]), "namespace": None},
              {"path": str(root / ".claude" / "agents"), "namespace": None},
              {"path": str(dirs["plugin"]), "namespace": "tradecraft"},
              {"path": str(dirs["builtin"]), "namespace": "helper"}]
    env = {"CLAUDE_CODE_TMPDIR": str(tmp_path / "t"), "USERPROFILE": str(tmp_path),
           "HOME": str(tmp_path)}
    config = launch_bound.guard_config(root, SESSION, env, tmp_path / "log.jsonl", agents)
    return {"config": config, "root": root.resolve(), "dirs": {**dirs, "tree": root / ".claude" / "agents"}}


def define(directory, name, isolation=None):
    lines = ["---", f"name: {name}", "description: x"]
    if isolation is not None:
        lines.append(f"isolation: {isolation}")
    (directory / f"{name}.md").write_bytes(("\n".join([*lines, "---", "body", ""])).encode("utf-8"))


def ask(config, tool="Agent", **tool_input):
    return guard.decide({"tool_name": tool, "tool_use_id": "toolu_h", "tool_input": tool_input,
                         "cwd": config["root"]}, config)


def three_parts(reason, root):
    """What was asked and why, where to work, and the alternative (AC1-AC3)."""
    return ("separate working copy" in reason and f"Work inside {root}" in reason
            and "general-purpose" in reason and "is refused because" in reason)


@pytest.mark.parametrize("value", ["worktree", "remote"])
@pytest.mark.parametrize("tool", ["Agent", "Task"])
def test_ac1_every_isolation_value_is_refused_with_its_reason(helper_config, value, tool):
    result = ask(helper_config["config"], tool, prompt="x", isolation=value)
    assert result["decision"] == "deny" and result["raw"] == value
    assert f'isolation "{value}"' in result["reason"]
    assert three_parts(result["reason"], helper_config["root"])


@pytest.mark.parametrize("source", ["user", "tree", "plugin", "builtin"])
def test_ac2_a_definition_that_sets_isolation_is_refused_in_every_source(helper_config, source):
    define(helper_config["dirs"][source], "copier", "worktree")
    name = {"plugin": "tradecraft:copier", "builtin": "helper:copier"}.get(source, "copier")
    for asked in {name, "copier"}:
        result = ask(helper_config["config"], prompt="x", subagent_type=asked)
        assert result["decision"] == "deny", (source, asked)
        assert "copier.md" in result["reason"] and three_parts(result["reason"], helper_config["root"])


def test_ac2_an_unknown_type_is_refused_and_known_safe_types_are_allowed(helper_config):
    config = helper_config["config"]
    unknown = ask(config, prompt="x", subagent_type="mystery")
    assert unknown["decision"] == "deny" and "unknown type" in unknown["reason"]
    assert three_parts(unknown["reason"], helper_config["root"])
    define(helper_config["dirs"]["tree"], "reviewer")
    define(helper_config["dirs"]["user"], "quoted", "''")
    for tool_input in ({"prompt": "x"}, {"prompt": "x", "subagent_type": "general-purpose"},
                       {"prompt": "x", "subagent_type": "reviewer"},
                       {"prompt": "x", "subagent_type": "quoted"},
                       {"prompt": "x", "isolation": None}, {"prompt": "x", "isolation": ""}):
        assert ask(config, **tool_input)["decision"] == "allow", tool_input


def test_ac2_an_unparseable_definition_fails_closed(helper_config):
    (helper_config["dirs"]["user"] / "broken.md").write_bytes(b"---\nname: broken\n")
    with pytest.raises(guard.Refusal):
        ask(helper_config["config"], prompt="x", subagent_type="anything")


@pytest.mark.parametrize("form", [{"name": "x"}, {"path": "/elsewhere/x"}])
def test_ac3_every_enter_worktree_call_is_refused_with_its_reason(helper_config, form):
    result = ask(helper_config["config"], "EnterWorktree", **form)
    assert result["decision"] == "deny"
    assert "entering a working copy" in result["reason"] and str(next(iter(form.values()))) in result["reason"]
    assert three_parts(result["reason"], helper_config["root"])


def run_hook(config_path, payload):
    return subprocess.run([sys.executable, str(LIB / "tree_write_guard.py"), "--config", str(config_path)],
                          input=json.dumps(payload).encode("utf-8"), capture_output=True, check=True)


def test_ac4_ac5_hook_logs_helper_decisions_and_the_outcome_lists_them(helper_config, tmp_path):
    config = helper_config["config"]
    config_path = tmp_path / "config.json"
    config_path.write_bytes(json.dumps(config).encode("utf-8"))
    allowed = run_hook(config_path, {"tool_name": "Agent", "tool_use_id": "a1",
                                     "tool_input": {"prompt": "x"}, "cwd": config["root"]})
    assert allowed.stdout == b""
    denied = run_hook(config_path, {"tool_name": "Agent", "tool_use_id": "a2",
                                    "tool_input": {"prompt": "x", "isolation": "worktree"},
                                    "cwd": config["root"]})
    assert b'"permissionDecision":"deny"' in denied.stdout
    outside = str(tmp_path / "outside.txt")
    run_hook(config_path, {"tool_name": "Edit", "tool_use_id": "e1",
                           "tool_input": {"file_path": outside}, "cwd": config["root"]})
    stream = b"\n".join(json.dumps({"type": "assistant", "message": {"content": [block]}}).encode()
                        for block in (
        {"type": "tool_use", "id": "a1", "name": "Agent", "input": {"prompt": "x"}},
        {"type": "tool_use", "id": "a2", "name": "Agent", "input": {"prompt": "x", "isolation": "worktree"}},
        {"type": "tool_use", "id": "e1", "name": "Edit", "input": {"file_path": outside}},
        {"type": "tool_use", "id": "a3", "name": "Agent", "input": {"prompt": "y"}},
        {"type": "tool_use", "id": "w1", "name": "EnterWorktree", "input": {"name": "z"}}))
    record, reason = launch_bound.guard_outcome(stream, config["log"])
    assert {(r["tool"], r["raw"]) for r in record["refusals"]} == {("Agent", "worktree"), ("Edit", outside)}
    assert {(u["tool"], u["tool_use_id"]) for u in record["unguarded"]} == {("Agent", "a3"),
                                                                          ("EnterWorktree", "w1")}
    assert "launch bound refused Agent worktree" in reason
    assert set(launch_bound.GUARD_MATCHER.split("|")) >= {"Agent", "Task", "EnterWorktree", "Write"}


def test_ac7_a_guard_that_allows_a_helper_copy_fails_its_self_test(tmp_path, monkeypatch):
    root = tmp_path / "Tree"
    root.mkdir()
    env = {**os.environ, "CLAUDE_CODE_TMPDIR": str(tmp_path / "t")}
    lenient = tmp_path / "lenient_guard.py"
    lenient.write_bytes(b"import sys, json\ndata = json.loads(sys.stdin.read())\n"
                        b"if data['tool_name'] in ('Write',) and 'outside' in data['tool_input']['file_path']:\n"
                        b"    print('{\"permissionDecision\":\"deny\"}')\n"
                        b"elif data['tool_name'] == 'Write' and '.claude' in data['tool_input']['file_path']:\n"
                        b"    print('{\"permissionDecision\":\"deny\"}')\n")
    monkeypatch.setattr(launch_bound, "GUARD", lenient)
    temporary = tmp_path / "invocation"
    temporary.mkdir()
    with pytest.raises(launch_bound.BoundError, match="isolated helper"):
        launch_bound.prepare_guard(temporary, root, SESSION, env, None)


# --- Row 2 and 3: working copies and branches --------------------------------

def git(cwd, *arguments):
    return subprocess.run(["git", "-C", str(cwd), *arguments], capture_output=True, check=True,
                          stdin=subprocess.DEVNULL).stdout.decode("utf-8").strip()


def commit(cwd, message="c"):
    git(cwd, "-c", "user.name=t", "-c", "user.email=t@x", "commit", "--allow-empty", "-q", "-m", message)
    return git(cwd, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A main checkout on ``trunk`` with the run's root as a linked copy beneath it."""
    home = tmp_path / "home"
    (home / ".tradecraft" / "dispatches").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    main = tmp_path / "product"
    main.mkdir()
    git(main, "init", "-q", "-b", "trunk")
    commit(main, "base")
    root = main / ".claude" / "worktrees" / "build"
    git(main, "worktree", "add", "-q", "-b", "feature-b", str(root))
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    own_request = tmp_path / "records" / "own.md.request.json"
    own_request.parent.mkdir()
    own_request.write_bytes(b"{}")
    return {"main": main, "root": root, "home": home, "plugin": plugin, "own_request": own_request,
            "tmp": tmp_path}


def start(repo, root=None):
    value = launch_bound.Comparison(root=root or repo["root"], env={}, launcher_plugin=repo["plugin"],
                                    own_output=repo["own_request"].with_name("own.md"),
                                    own_request=repo["own_request"], holder_session_id=None,
                                    dispatch_id=OWN, refs=True)
    value.take_before(60)
    return value


def stream(repo, *commands, helper="toolu_parent", tool="Bash", key="command"):
    lines = []
    for index, command in enumerate(commands):
        lines.append(json.dumps({"type": "assistant", "parent_tool_use_id": helper, "message": {
            "content": [{"type": "tool_use", "id": f"toolu_{index}", "name": tool,
                         "input": {key: command}}]}}))
    path = repo["tmp"] / "run.claude.stdout.log"
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return path


def entries(result, kind):
    return {(entry["kind"], entry.get("branch") or Path(entry["path"]).name, entry["change"])
            for entry in result[kind] if "kind" in entry}


def test_ac8_a_helpers_named_shell_worktree_holds_with_path_branch_and_tip(repo):
    value = start(repo)
    copy = repo["tmp"] / "copy-x"
    command = f"git worktree add {copy} -b helper-b"
    git(repo["main"], "worktree", "add", "-q", "-b", "helper-b", str(copy))
    result = value.finish(60, record=stream(repo, "ls", command))
    assert result["status"] == "findings"
    [held] = [entry for entry in result["findings"] if entry.get("kind") == "working-copy"]
    assert Path(held["path"]) == copy and held["branch_after"] == "helper-b"
    assert held["tip_after"] == git(copy, "rev-parse", "HEAD") and held["change"] == "added"
    assert held["folded_branch"]["branch"] == "helper-b" and "toolu_1" in held["reason"]
    assert [entry for entry in result["findings"] if entry.get("kind") == "branch"] == []
    # Row 3: nothing found is removed.
    assert git(copy, "rev-parse", "HEAD") == held["tip_after"]


def test_ac8a_relative_forms_and_a_named_base_hold(repo):
    value = start(repo)
    sibling = repo["root"].parent / "x"
    git(repo["root"], "worktree", "add", "-q", str(sibling))
    deeper = repo["tmp"] / "far" / "y"
    deeper.parent.mkdir()
    git(repo["main"], "worktree", "add", "-q", "-b", "y-branch", str(deeper))
    result = value.finish(60, record=stream(repo, "git worktree add ../x", f"cd {deeper.parent}",
                                            "git -C y log"))
    held = {Path(entry["path"]).name: entry for entry in result["findings"]}
    assert held["x"]["branch_after"] == "x" and held["x"]["folded_branch"]["branch"] == "x"
    assert "y" in held


def test_ac9_a_named_branch_and_a_moved_copy_in_each_path_form_hold(repo):
    other = repo["tmp"] / "other"
    git(repo["main"], "worktree", "add", "-q", "-b", "other-b", str(other))
    value = start(repo)
    git(repo["main"], "branch", "made-here")
    commit(other, "moved")
    path = str(other)
    result = value.finish(60, record=stream(repo, "git branch made-here",
                                            f"git -C {path.replace(os.sep, '/')} commit"))
    assert entries(result, "findings") >= {("branch", "made-here", "added"),
                                           ("working-copy", "other", "moved")}
    for form in (path, path.replace("\\", "/")):
        calls = [{"id": "t", "name": "Bash", "agent": None, "strings": [f"cat {form}/file"]}]
        named = launch_bound.named_targets(calls, root=repo["root"], copies=[path, str(repo["main"])],
                                           branches=[], home=str(repo["home"]))
        assert "copy:" + path in named, form


def test_ac9_git_bash_and_home_forms_name_a_windows_copy():
    copies = ["D:/Code/product", "D:/Code/product/.claude/worktrees/b", "C:/Users/me/work"]
    for text in ("cd /d/code/product && git commit", "git -C D:\\Code\\Product status",
                 "ls ~/work/sub", "ls $HOME/work", "dir $env:USERPROFILE\\work"):
        calls = [{"id": "t", "name": "Bash", "agent": None, "strings": [text]}]
        named = launch_bound.named_targets(calls, root=Path("D:/Code/product/.claude/worktrees/b"),
                                           copies=copies, branches=[], home="C:/Users/me", windows=True)
        assert any(key in named for key in ("copy:D:/Code/product", "copy:C:/Users/me/work")), text


def test_ac10_an_unnamed_copy_or_one_named_only_in_a_result_is_listed(repo):
    value = start(repo)
    copy = repo["tmp"] / "session-copy"
    git(repo["main"], "worktree", "add", "-q", "-b", "session-b", str(copy))
    record = stream(repo, "git status")
    with open(record, "ab") as handle:
        handle.write(json.dumps({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "toolu_0", "content": f"{copy} session-b"}]}}).encode()
                     + b"\n")
    result = value.finish(60, record=record)
    assert result["status"] == "clean" and result["findings"] == []
    assert ("working-copy", "session-copy", "added") in entries(result, "listed")


def test_ac11_part_of_a_name_never_names(repo):
    copies = [str(repo["main"]), str(repo["tmp"] / "top"), str(repo["tmp"] / "top" / "deep")]
    top = str(repo["tmp"] / "top").replace("\\", "/")
    calls = [{"id": "t", "name": "Bash", "agent": None,
              "strings": [f"ls {top}2/x x2 git branch feature-b-old; ls {top}/deep/file"]}]
    named = launch_bound.named_targets(calls, root=repo["tmp"] / "elsewhere",
                                       copies=copies, branches=["feature-b"], home=str(repo["home"]))
    assert "branch:feature-b" not in named and "copy:" + copies[1] not in named
    assert "copy:" + copies[2] in named
    relative = [{"id": "t", "name": "Bash", "agent": None, "strings": ["ls x2"]}]
    assert launch_bound.named_targets(relative, root=repo["tmp"], copies=[str(repo["tmp"] / "x")],
                                      branches=[], home=str(repo["home"])) == {}


@pytest.mark.parametrize("remote", ["origin", "none"])
@pytest.mark.parametrize("unreadable", [False, True])
def test_ac12_ac18_the_default_branch_never_holds(repo, remote, unreadable):
    if remote == "origin":
        git(repo["main"], "update-ref", "refs/remotes/origin/trunk", "HEAD")
        git(repo["main"], "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
    stray = repo["tmp"] / "stray"
    value = start(repo)
    commit(repo["main"], "another session")
    git(repo["main"], "worktree", "add", "-q", "-b", "stray-b", str(stray))
    if unreadable:
        record = repo["tmp"] / "bad.log"
        record.write_bytes(b'{"type": "system"}\nnot json\n{"type": "system"}\n')
    else:
        record = stream(repo, "git log trunk refs/heads/trunk", f"git -C {repo['main']} log")
    result = value.finish(60, record=record)
    listed = {(entry["kind"], entry["reason"]) for entry in result["listed"]}
    assert ("branch", "default branch") in listed or ("working-copy", "default branch") in listed
    assert all(entry.get("reason") == "default branch" for entry in result["listed"]
               if entry.get("branch") == "trunk" or entry.get("branch_after") == "trunk")
    held = {Path(entry["path"]).name for entry in result["findings"]}
    assert "product" not in held and "refs/heads/trunk" not in {e["path"] for e in result["findings"]}
    if unreadable:
        assert "stray" in held and result["run_record"]["status"] == "unreadable"
        assert all(e["reason"].startswith("run record unreadable") for e in result["findings"])


def test_ac13_paths_inside_the_root_do_not_name_the_main_checkout(repo):
    git(repo["main"], "checkout", "-q", "-b", "side")
    value = start(repo)
    commit(repo["main"], "moved by another session")
    root = str(repo["root"])
    result = value.finish(60, record=stream(repo, f"cat {root}/a.py", "cat lib/b.py ./c.py",
                                            f"cat {root.replace(os.sep, '/')}/d.py"))
    assert result["findings"] == []
    assert ("working-copy", "product", "moved") in entries(result, "listed")


def test_ac14_only_the_root_copy_and_its_branch_are_the_runs_own(repo):
    git(repo["root"], "branch", "unchanged")
    value = start(repo)
    commit(repo["root"], "own work")
    inner = repo["root"] / ".wt" / "x"
    git(repo["root"], "worktree", "add", "-q", "-b", "x", str(inner))
    git(repo["root"], "branch", "loose")
    result = value.finish(60, record=stream(repo, f"git worktree add {inner} -b x"))
    names = {Path(entry["path"]).name for entry in result["findings"]}
    assert "x" in names and "build" not in names
    assert ("branch", "loose", "added") in entries(result, "listed")
    every = result["findings"] + result["listed"]
    assert not any(entry.get("branch") in {"feature-b", "unchanged"} for entry in every)


def test_ac14a_an_independent_roots_own_repository_is_compared(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".tradecraft").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    root = tmp_path / "artifact"
    root.mkdir()
    git(root, "init", "-q", "-b", "trunk")
    commit(root)
    (tmp_path / "plugin").mkdir()
    request = tmp_path / "own.request.json"
    request.write_bytes(b"{}")
    value = launch_bound.Comparison(root=root, env={}, launcher_plugin=tmp_path / "plugin",
                                    own_output=tmp_path / "own.md", own_request=request,
                                    holder_session_id=None, dispatch_id=OWN, refs=True)
    value.take_before(60)
    outside = tmp_path / "outside"
    git(root, "worktree", "add", "-q", "-b", "y", str(outside))
    record = tmp_path / "r.log"
    record.write_bytes(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "t1", "name": "Bash",
         "input": {"command": f"git worktree add {outside} -b y"}}]}}).encode() + b"\n")
    result = value.finish(60, record=record)
    assert {Path(entry["path"]).name for entry in result["findings"]} == {"outside"}


def test_ac15_another_overlapping_runs_root_is_attributed(repo):
    other = repo["tmp"] / "other-run"
    git(repo["main"], "worktree", "add", "-q", "-b", "other-run-b", str(other))
    store = repo["home"] / ".tradecraft" / "dispatches"
    from datetime import datetime, timezone
    request = {"dispatch_id": "b" * 32, "root": str(other),
               "launched_at": datetime.now(timezone.utc).isoformat()}
    (store / "o.md.request.json").write_bytes(json.dumps(request).encode())
    (store / "o.md.run.json").write_bytes(json.dumps({"completed_at": None,
                                                      "elapsed_checkpoint_seconds": 9999}).encode())
    value = launch_bound.Comparison(root=repo["root"], env={}, launcher_plugin=repo["plugin"],
                                    own_output=repo["own_request"].with_name("own.md"),
                                    own_request=repo["own_request"], holder_session_id=None,
                                    dispatch_id=OWN, store=store, refs=True)
    value.take_before(60)
    commit(other, "theirs")
    result = value.finish(60, record=stream(repo, f"git -C {other} log"))
    assert result["findings"] == []
    assert {entry["to"]["dispatch_id"] for entry in result["attributed"]} == {"b" * 32}


def test_ac17a_finish_without_a_record_raises_on_a_refs_plan(repo):
    value = start(repo)
    with pytest.raises(ValueError, match="needs the run's record"):
        value.finish(60)


def test_ac18_a_final_unterminated_line_is_skipped_and_counted(repo):
    record = repo["tmp"] / "killed.log"
    record.write_bytes(b'{"type": "system"}\n{"type": "assist')
    calls, skipped = launch_bound.read_run_record(record)
    assert calls == [] and skipped == 1
    with pytest.raises(ValueError):
        launch_bound.read_run_record(repo["tmp"] / "absent.log")


def test_ac18_an_unreadable_refs_item_is_uncompared(repo, monkeypatch):
    value = start(repo)

    def broken(*_args, **_kwargs):
        raise ValueError("git failed")
    monkeypatch.setattr(launch_bound, "_refs_state", broken)
    result = value.finish(60, record=stream(repo, "ls"))
    assert any(entry["change"] == "uncompared" for entry in result["findings"])


def test_ac17_a_root_outside_any_repository_is_not_a_repository(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".tradecraft").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    root = tmp_path / "seat"
    root.mkdir()
    plan = launch_bound.refs_plan(root, [])
    assert plan[0]["unavailable"] == "not-a-repository"
    before = launch_bound.snapshot(plan, seconds=30, own_output=tmp_path / "x")
    result = launch_bound.compare(plan, before, before, root=root, holder_session_id=None,
                                  store=home, own_dispatch=OWN, before_at=None, after_at=None,
                                  elapsed_seconds=0, record=tmp_path / "absent")
    assert result["status"] == "clean" and result["coverage"][0]["status"] == "not-a-repository"


def test_ac19_the_comparison_runs_no_removing_git_command():
    for name in ("launch_bound.py", "dispatch_implementer.py", "dispatch_seat.py"):
        text = (LIB / name).read_text(encoding="utf-8")
        for word in ('"prune"', '"remove"', '"-D"', '"-d"', '"update-ref"', '"gc"'):
            assert word not in text, (name, word)

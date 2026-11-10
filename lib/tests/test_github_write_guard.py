"""The GitHub write bound's command check and allowance."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))

import github_allowance as allowance_module  # noqa: E402
import github_write_guard as guard  # noqa: E402

CHILD = f'claude --setting-sources user --settings "${guard.CHILD_VARIABLE}"'


def git(cwd, *arguments):
    subprocess.run(["git", "-C", str(cwd), *arguments], check=True, capture_output=True,
                   stdin=subprocess.DEVNULL)


@pytest.fixture()
def tree(tmp_path):
    root = tmp_path / "tree"
    root.mkdir()
    git(root, "init", "-q", "-b", "tradecraft/894-ab")
    git(root, "remote", "add", "origin", "https://github.com/o/r.git")
    git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "x")
    return root


def config(kind, root, *, grants=()):
    allowance = allowance_module.allowance_for(
        {"none": "artifact", "branch": "build", "review-disposition": "review-disposition"}[kind],
        repository="o/r", branch="tradecraft/894-ab", pull_request=12, grants=grants)
    return {"allowance": allowance, "root": str(root), "child_settings": str(root / "child.json"),
            "scope": "parent"}


def decision(command, root, kind, **options):
    return guard.decide(command, str(root), config(kind, root, **options))["decision"]


@pytest.mark.parametrize("command", [
    "git push --force-with-lease=refs/heads/x:abc origin abc123:refs/heads/x",
    "gh issue comment 683",
    'bash -c "gh issue comment 683"',
    "gh api -X POST repos/o/r/issues/5/comments -f body=x",
    "echo $(gh pr comment 12 -b x)",
])
def test_none_refuses_the_writes_on_record(tree, command):
    verdict = guard.decide(command, str(tree), config("none", tree))
    assert verdict["decision"] == "deny"
    assert "`none`" in verdict["reason"] and "**Write requests**" in verdict["reason"]


@pytest.mark.parametrize("command", [
    "git push origin HEAD:refs/heads/other",
    "git push origin --delete tradecraft/894-ab",
    "git push origin :tradecraft/894-ab",
    "git push --force origin HEAD:refs/heads/tradecraft/894-ab",
    "git push origin +HEAD:refs/heads/tradecraft/894-ab",
    "git push --tags origin",
])
def test_branch_refuses_other_refs_deletions_and_forces(tree, command):
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", [
    "git push origin HEAD:refs/heads/tradecraft/894-ab",
    "git push origin HEAD",
    "git push https://github.com/O/R HEAD:tradecraft/894-ab",
])
def test_branch_allows_its_own_push(tree, command):
    assert decision(command, tree, "branch") == "allow"


def test_a_local_push_is_not_a_github_write(tree, tmp_path):
    bare = tmp_path / "bare.git"
    git(tmp_path, "init", "-q", "--bare", str(bare))
    assert decision(f"git push {bare.as_posix()} HEAD:refs/heads/anything", tree, "none") == "allow"


@pytest.mark.parametrize("command", [
    "gh api --method GET repos/o/r/issues/894",
    "gh api -X GET repos/o/r/pulls/12",
    "gh api repos/o/r/issues/894",
    "gh api --method GET --paginate repos/o/r/issues/894/comments",
    "gh pr view 12 --json state",
    "gh api graphql -f query='query{viewer{login}}'",
])
@pytest.mark.parametrize("kind", ["none", "branch", "review-disposition"])
def test_reads_stay_open(tree, command, kind):
    assert decision(command, tree, kind) == "allow"


@pytest.mark.parametrize("command", [
    "gh pr comment 12 --body x",
    "gh api repos/o/r/pulls/12/comments/99/replies -f body=x",
    "gh api repos/o/r/pulls/12/comments -f body=x -F in_reply_to=99",
    "gh api repos/o/r/issues/12/comments -f body=x",
])
def test_review_disposition_allows_its_own_pull_request(tree, command):
    assert decision(command, tree, "review-disposition") == "allow"
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", [
    "gh api repos/o/r/pulls/13/comments/5/replies -f body=x",
    "gh pr comment 13 --body x",
    "gh pr comment 12 --edit-last --body x",
])
def test_review_disposition_refuses_another_pull_request(tree, command):
    assert decision(command, tree, "review-disposition") == "deny"


def test_thread_resolve_is_confirmed_against_the_own_pull_request(tree, monkeypatch):
    import work
    command = work.RESOLVE_THREAD_COMMAND.replace("THREAD_ID", "T1")
    monkeypatch.setattr(guard, "thread_owner", lambda thread: ("o/r", 12))
    assert decision(command, tree, "review-disposition") == "allow"
    monkeypatch.setattr(guard, "thread_owner", lambda thread: ("o/r", 13))
    assert decision(command, tree, "review-disposition") == "deny"
    monkeypatch.setattr(guard, "thread_owner", lambda thread: None)
    assert decision(command, tree, "review-disposition") == "deny"


@pytest.mark.parametrize("kind", ["none", "branch", "review-disposition"])
def test_the_instructed_child_start_is_allowed(tree, kind):
    allowed = allowance_module.CHILD_START + " -p hi"
    assert allowance_module.CHILD_START in allowance_module.sentence(config(kind, tree)["allowance"])
    assert decision(allowed, tree, kind) == "allow"
    literal = f"claude --setting-sources user --settings {(tree / 'child.json').as_posix()} -p hi"
    assert decision(literal, tree, kind) == "allow"
    assert decision("claude --version", tree, kind) == "allow"


@pytest.mark.parametrize("command", [
    "claude -p hi",
    "bash -c 'claude -p hi'",
    f'claude --settings "${guard.CHILD_VARIABLE}" -p hi',
    f'claude --setting-sources user,project --settings "${guard.CHILD_VARIABLE}" -p hi',
    f'claude --setting-sources local --settings "${guard.CHILD_VARIABLE}" -p hi',
    f"claude --safe-mode --setting-sources user --settings \"${guard.CHILD_VARIABLE}\" -p hi",
    f"claude --bare --setting-sources user --settings \"${guard.CHILD_VARIABLE}\" -p hi",
    f"CLAUDE_CODE_SIMPLE=1 {CHILD} -p hi",
    f"{CHILD} --settings x.json -p hi",
    "claude --setting-sources user --settings '{\"disableAllHooks\":true}' -p hi",
    f"TRADECRAFT_CHILD_SETTINGS=x.json {CHILD} -p hi",
    f"env -i {CHILD} -p hi",
    "codex exec hi",
])
@pytest.mark.parametrize("kind", ["none", "branch"])
def test_a_child_outside_the_launch_settings_is_refused(tree, command, kind):
    assert decision(command, tree, kind) == "deny"


@pytest.mark.parametrize("command", [
    "export ENABLE_CLAUDEAI_MCP_SERVERS=true",
    f"ENABLE_CLAUDEAI_MCP_SERVERS=true {CHILD} -p hi",
    "$env:ENABLE_CLAUDEAI_MCP_SERVERS = 'true'",
    "unset ENABLE_CLAUDEAI_MCP_SERVERS",
    f"env -u ENABLE_CLAUDEAI_MCP_SERVERS {CHILD} -p hi",
    "Remove-Item Env:ENABLE_CLAUDEAI_MCP_SERVERS",
])
def test_connectors_cannot_be_turned_back_on(tree, command):
    assert decision(command, tree, "branch") == "deny"
    assert decision(f"ENABLE_CLAUDEAI_MCP_SERVERS=false {CHILD} -p hi", tree, "branch") == "allow"


def test_text_that_cannot_be_parsed_is_refused_only_with_a_signature(tree):
    assert decision("cat <<EOF\nunterminated gh issue comment 1", tree, "none") == "deny"
    assert decision("cat <<EOF\nunterminated hello", tree, "none") == "allow"
    assert decision('echo "unbalanced gh issue comment 1', tree, "none") == "deny"
    assert decision('grep "git push" notes.txt', tree, "none") == "allow"


# The landing script's route: a message passed by -m, whatever it names.
PERSIST = "python scripts/persist.py --expect-branch tradecraft/894-ab"


@pytest.mark.parametrize("command", [
    # The commit and persist routes a builder is shown, with messages naming the writes.
    "git commit -m \"$(cat <<'EOF'\nDon't git push; gh api repos/o/r (#894)\n\n"
    "Co-Authored-By: x <x@y>\nEOF\n)\"",
    PERSIST + " -m \"$(cat <<'EOF'\nIt's a gh issue comment and git push fix (#894)\nEOF\n)\" lib/a.py",
    PERSIST + " -m 'One line naming git push and gh pr comment' lib/a.py",
    PERSIST + ' -m "Multi-line\nnaming git push origin main\nand gh api -X POST" lib/a.py',
    "git commit -F - <<'EOF'\ngit push origin main\ngh issue comment 683\nEOF",
    "cat > msg.txt <<EOF\ngh issue comment 3\nEOF\ngit commit -F msg.txt",
])
def test_commit_and_persist_routes_pass_whatever_the_message_names(tree, command):
    assert decision(command, tree, "branch") == "allow"
    assert decision(command, tree, "none") == "allow"


@pytest.mark.parametrize("command", [
    "bash <<'EOF'\ngh issue comment 683\nEOF",
    "bash -s <<EOF\ngit push origin HEAD:refs/heads/other\nEOF",
    "cat <<EOF\nx\nEOF\ngh issue comment 1",
    'git commit -m "line `gh issue comment 1`"',
])
def test_a_shell_reading_a_here_document_or_a_substitution_is_judged(tree, command):
    assert decision(command, tree, "branch") == "deny"


def test_a_push_grant_permits_exactly_its_ref(tree):
    grant = {"marker": 1, "brief": 2, "row": 4, "stage": "artifact", "write": "push",
             "target": "o/r:refs/heads/probe"}
    assert decision("git push origin HEAD:refs/heads/probe", tree, "none") == "deny"
    assert decision("git push origin HEAD:refs/heads/probe", tree, "none", grants=[grant]) == "allow"
    assert decision("git push origin HEAD:refs/heads/other", tree, "none", grants=[grant]) == "deny"
    granted = config("none", tree, grants=[grant])["allowance"]
    assert allowance_module.permits_push(granted)
    assert not allowance_module.permits_push(config("none", tree)["allowance"])


def test_hook_entry_refuses_and_logs(tmp_path):
    log = tmp_path / "log.jsonl"
    path = tmp_path / "config.json"
    path.write_text(json.dumps({**config("none", tmp_path), "log": str(log)}), encoding="utf-8")
    payload = {"tool_name": "Bash", "tool_input": {"command": "gh issue comment 683"},
               "cwd": str(tmp_path), "session_id": "s"}
    result = subprocess.run([sys.executable, str(LIB / "github_write_guard.py"), "--hook",
                             "--config", str(path)], input=json.dumps(payload).encode(),
                            capture_output=True, timeout=60)
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    refusals = allowance_module.refusals(log)
    assert [r["command"] for r in refusals] == ["gh issue comment 683"]
    assert refusals[0]["allowance"]["kind"] == "none" and refusals[0]["entry"] == "hook"


@pytest.mark.skipif(allowance_module.bash_executable() is None, reason="no bash")
def test_prefix_wrapper_refuses_runs_and_passes_through(tmp_path):
    log = tmp_path / "log.jsonl"
    path = tmp_path / "config.json"
    path.write_text(json.dumps({**config("none", tmp_path), "log": str(log)}), encoding="utf-8")
    wrapper = tmp_path / "prefix.sh"
    allowance_module.write_wrapper(wrapper, path)
    bash = allowance_module.bash_executable()
    marker = tmp_path / "ran"

    def run(*arguments):
        return subprocess.run([bash, str(wrapper), *arguments], capture_output=True, timeout=60,
                              stdin=subprocess.DEVNULL,
                              cwd=tmp_path)

    refused = run(allowance_module.harness_string(f"gh issue comment 683; touch {marker.as_posix()}"))
    assert refused.returncode == 126 and guard.REFUSED.encode() in refused.stderr
    assert not marker.exists()
    passed = run(allowance_module.harness_string("printf 'it'\\''s'; exit 3"))
    assert passed.stdout == b"it's" and passed.returncode == 3
    assert run("a", "b").returncode == 126
    lines = [json.loads(line) for line in log.read_text().splitlines()]
    assert lines[0]["entry"] == "prefix" and lines[0]["decision"] == "deny"
    assert lines[0]["command"].startswith("gh issue comment 683")


def test_without_push_credential_leaves_git_no_password(tmp_path):
    helper = tmp_path / "helper.sh"
    helper.write_text("#!/bin/sh\necho username=u\necho password=fake-secret\n", encoding="utf-8")
    helper.chmod(0o755)
    global_config = tmp_path / "gitconfig"
    global_config.write_text(
        f"[credential \"https://github.com\"]\n\thelper = !sh {helper.as_posix()}\n", encoding="utf-8")
    base = {**os.environ, "GIT_CONFIG_GLOBAL": str(global_config), "GIT_CONFIG_NOSYSTEM": "1"}

    def fill(env):
        return subprocess.run(["git", "credential", "fill"], input=b"protocol=https\nhost=github.com\n\n",
                              capture_output=True, env=env, timeout=60)

    assert b"password=fake-secret" in fill(base).stdout
    stripped = fill(allowance_module.without_push_credential(base))
    assert b"password=" not in stripped.stdout and stripped.returncode != 0


def test_allowance_for_each_stage():
    kinds = {stage: allowance_module.allowance_for(stage, repository="o/r", branch="b",
                                                   pull_request=1)["kind"]
             for stage in ("artifact", "build", "floor", "review-disposition", "use", "source")}
    assert kinds == {"artifact": "none", "build": "branch", "floor": "branch",
                     "review-disposition": "review-disposition", "use": "none", "source": "none"}


BRIEF = """**Rows**

**4. A write outside the allowance is granted only where the affirmed brief names it.**
   - The artifact must test a real push to its probe branch.

**5. Codex launches.**
"""


def grant_body(**overrides):
    values = {"brief": 7, "row": 4, "stage": "artifact", "write": "push", "target": "o/r:refs/heads/probe"}
    values.update(overrides)
    marker = ("<!-- tradecraft:write-grant:v1 brief={brief} row={row} stage={stage} write={write} "
              "target={target} -->").format(**values)
    return marker + "\n> The artifact must test a real push\n"


def test_a_grant_rests_on_an_affirmed_row():
    grant = allowance_module.parse_grant(9, grant_body())
    accepted = allowance_module.validate_grant(grant, brief_comment=7, brief_body=BRIEF,
                                               stage="artifact", resumed=True)
    assert accepted["target"] == "o/r:refs/heads/probe" and accepted["row"] == 4


@pytest.mark.parametrize("body, stage, resumed", [
    (grant_body(brief=8), "artifact", True),
    (grant_body(row=9), "artifact", True),
    (grant_body().replace("a real push", "a real deploy"), "artifact", True),
    (grant_body(), "build", True),
    (grant_body(), "artifact", False),
    (grant_body(target="refs/tags/x"), "artifact", True),
])
def test_a_grant_without_an_affirmed_row_is_refused(body, stage, resumed):
    grant = allowance_module.parse_grant(9, body)
    with pytest.raises(allowance_module.GrantError):
        allowance_module.validate_grant(grant, brief_comment=7, brief_body=BRIEF, stage=stage,
                                        resumed=resumed)


def test_cloud_record_says_the_block_did_not_run():
    record = allowance_module.cloud_record("change", "report")
    assert record["command_check"]["status"] == "not-run"
    assert "remote" in record["command_check"]["reason"]


def _prefix_run(tmp_path, argument):
    log = tmp_path / "log.jsonl"
    path = tmp_path / "config.json"
    path.write_text(json.dumps({**config("none", tmp_path), "log": str(log)}), encoding="utf-8")
    return subprocess.run([sys.executable, str(LIB / "github_write_guard.py"), "--prefix", "--config",
                           str(path), "--", argument], capture_output=True, timeout=60,
                          stdin=subprocess.DEVNULL), log


@pytest.mark.parametrize("argument", [
    "eval 'echo hi'; gh pr merge 1",
    "gh pr merge 1 && eval 'echo hi' < /dev/null",
    "export TEMP=/tmp && eval 'echo hi' < /dev/null && gh issue comment 683",
])
def test_the_prefix_judges_the_whole_string_it_runs(tmp_path, argument):
    result, _log = _prefix_run(tmp_path, argument)
    assert result.returncode == 126 and guard.REFUSED.encode() in result.stderr


def test_the_prefix_allows_the_runtime_wrapper_around_an_allowed_command(tmp_path):
    result, log = _prefix_run(
        tmp_path, "export TEMP=/tmp && eval 'git status' < /dev/null && pwd -P >| /tmp/cwd")
    assert result.returncode == 0
    assert json.loads(log.read_text().splitlines()[0])["command"] == "git status"


@pytest.mark.parametrize("command", [
    "git push -fu origin HEAD:refs/heads/tradecraft/894-ab",
    "git push -uf origin HEAD:refs/heads/tradecraft/894-ab",
    "git push -df origin tradecraft/894-ab",
    "git push origin +HEAD:refs/heads/tradecraft/894-ab",
    "git push origin :refs/heads/tradecraft/894-ab",
    "git push --force-with-lease origin HEAD:refs/heads/tradecraft/894-ab",
    "git push --force-if-includes --force-with-lease origin HEAD:refs/heads/tradecraft/894-ab",
    "git push --all origin",
    "git push --prune origin HEAD:refs/heads/tradecraft/894-ab",
    "git push --mirror origin",
    "git push -o ci.skip origin HEAD:refs/heads/other",
    "git push --push-option ci.skip origin HEAD:refs/heads/other",
    "git push --push-option=ci.skip origin HEAD:refs/heads/other",
    "git push origin HEAD:other",
    "git push origin HEAD:refs/heads/other",
    "git push origin HEAD:refs/tags/v1",
])
def test_judge_push_refuses_every_write_beyond_a_fast_forward_of_the_own_branch(tree, command):
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", [
    "git push -u origin HEAD:refs/heads/tradecraft/894-ab",
    "git push -o ci.skip origin HEAD:refs/heads/tradecraft/894-ab",
    "git push --push-option ci.skip origin HEAD:refs/heads/tradecraft/894-ab",
    "git push --push-option=ci.skip origin HEAD:tradecraft/894-ab",
    "git push -q --set-upstream origin tradecraft/894-ab",
])
def test_judge_push_allows_the_own_branch_with_ordinary_options(tree, command):
    assert decision(command, tree, "branch") == "allow"

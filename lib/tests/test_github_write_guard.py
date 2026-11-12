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

CHILD = guard.CHILD_START


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
def test_none_refuses_a_forced_push_comments_and_a_post(tree, command):
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
    "git -c remote.origin.pushurl=https://github.com/other/x.git push origin HEAD:refs/heads/tradecraft/894-ab",
    "git --config-env=remote.origin.pushurl=URL push origin HEAD:refs/heads/tradecraft/894-ab",
    "git --git-dir=../other/.git push origin HEAD:refs/heads/tradecraft/894-ab",
    "git --work-tree ../other push origin HEAD:refs/heads/tradecraft/894-ab",
    "git --namespace x push origin HEAD:refs/heads/tradecraft/894-ab",
    "GIT_DIR=../other/.git git push origin HEAD:refs/heads/tradecraft/894-ab",
    "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=remote.origin.pushurl GIT_CONFIG_VALUE_0=https://github.com/other/x.git "
    "git push origin HEAD:refs/heads/tradecraft/894-ab",
    "GIT_CONFIG_NOSYSTEM=1 git push origin HEAD:refs/heads/tradecraft/894-ab",
])
def test_a_push_carrying_a_redirecting_git_option_is_refused(tree, command):
    assert decision("git push origin HEAD:refs/heads/tradecraft/894-ab", tree, "branch") == "allow"
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", [
    # git takes the value as a separate word, so HEAD is not the subcommand.
    "git --attr-source HEAD push origin main",
    "git --attr-source=HEAD push origin main",
    # An option this check does not know may swallow a word; a later push is not passed unjudged.
    "git --some-future-option HEAD push origin main",
])
def test_a_push_behind_a_value_taking_global_option_is_judged(tree, command):
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", [
    "git --attr-source HEAD status",
    "git --no-pager --attr-source HEAD log -1",
    # Bare --exec-path prints git's exec path and stops; nothing after it runs.
    "git --exec-path push origin main",
    "git --some-future-option HEAD status",
])
def test_a_harmless_command_behind_a_global_option_passes(tree, command):
    assert decision(command, tree, "branch") == "allow"


def test_a_push_behind_exec_path_with_a_value_is_judged(tree):
    assert decision("git --exec-path=/x push origin main", tree, "branch") == "deny"
    assert decision("git --exec-path=/x push origin HEAD:refs/heads/tradecraft/894-ab", tree,
                    "branch") == "allow"


@pytest.mark.parametrize("setting", [
    ("remote.origin.push", "refs/heads/*:refs/heads/*"),
    ("remote.origin.mirror", "true"),
    ("push.default", "matching"),
])
def test_a_push_naming_no_refspec_is_refused_where_configuration_widens_it(tree, setting):
    git(tree, "config", f"branch.tradecraft/894-ab.remote", "origin")
    git(tree, "config", f"branch.tradecraft/894-ab.merge", "refs/heads/tradecraft/894-ab")
    git(tree, "update-ref", "refs/remotes/origin/tradecraft/894-ab", "HEAD")
    assert decision("git push", tree, "branch") == "allow"
    git(tree, "config", *setting)
    assert decision("git push", tree, "branch") == "deny"
    # A named refspec is judged as itself; git refuses one beside a mirror setting.
    assert decision("git push origin HEAD:refs/heads/tradecraft/894-ab", tree, "branch") == "allow"


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


def test_a_graphql_document_file_is_read_from_the_commands_directory(tree, monkeypatch):
    # Two files of one name: the hook's own directory holds a read, a subdirectory a mutation.
    (tree / "q.graphql").write_text("query{viewer{login}}", encoding="utf-8")
    (tree / "sub").mkdir()
    (tree / "sub" / "q.graphql").write_text(
        'mutation{mergePullRequest(input:{pullRequestId:"P"}){clientMutationId}}', encoding="utf-8")
    monkeypatch.chdir(tree)
    assert decision("gh api graphql -F query=@q.graphql", tree, "branch") == "allow"
    assert decision("gh api graphql -F query=@sub/q.graphql", tree, "branch") == "deny"
    # gh reads the file after the cd, so the mutation it would send is the one judged.
    assert decision("cd sub && gh api graphql -F query=@q.graphql", tree, "branch") == "deny"


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
    literal = (f"claude --setting-sources user --strict-mcp-config --settings "
               f"{(tree / 'child.json').as_posix()} -p hi")
    assert decision(literal, tree, kind) == "allow"
    assert decision("claude --version", tree, kind) == "allow"


@pytest.mark.parametrize("command", [
    "claude -p hi",
    "bash -c 'claude -p hi'",
    f'claude --strict-mcp-config --settings "${guard.CHILD_VARIABLE}" -p hi',
    f'claude --setting-sources user,project --strict-mcp-config --settings "${guard.CHILD_VARIABLE}" -p hi',
    f'claude --setting-sources local --strict-mcp-config --settings "${guard.CHILD_VARIABLE}" -p hi',
    f"claude --safe-mode {CHILD[len('claude '):]} -p hi",
    f"claude --bare {CHILD[len('claude '):]} -p hi",
    # Without --strict-mcp-config, or with a server of its own, a child loads an MCP server.
    f'claude --setting-sources user --settings "${guard.CHILD_VARIABLE}" -p hi',
    f"{CHILD} --mcp-config github.json -p hi",
    f"CLAUDE_CODE_SIMPLE=1 {CHILD} -p hi",
    f"{CHILD} --settings x.json -p hi",
    "claude --setting-sources user --strict-mcp-config --settings '{\"disableAllHooks\":true}' -p hi",
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
    # Every gh command and API host the check judges is a signature, not just the common ones.
    assert decision('echo "unbalanced gh codespace delete', tree, "none") == "deny"
    assert decision('echo "unbalanced https://uploads.github.com/x', tree, "none") == "deny"
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


def test_a_push_grant_counts_only_on_its_own_repository(tree):
    grant = {"marker": 1, "brief": 2, "row": 4, "stage": "build", "write": "push",
             "target": "other/repo:refs/heads/probe"}
    other = "https://github.com/other/repo.git"
    assert decision(f"git push {other} HEAD:refs/heads/probe", tree, "branch", grants=[grant]) == "allow"
    # The step's own branch belongs to the step's repository, not to the grant's.
    assert decision(f"git push {other} HEAD:refs/heads/tradecraft/894-ab", tree, "branch",
                    grants=[grant]) == "deny"
    # And the grant's ref belongs to the grant's repository, not to the step's.
    assert decision("git push origin HEAD:refs/heads/probe", tree, "branch", grants=[grant]) == "deny"
    assert decision("git push origin HEAD:refs/heads/tradecraft/894-ab", tree, "branch",
                    grants=[grant]) == "allow"


def test_a_refusal_the_log_cannot_take_still_refuses_and_says_so(tmp_path):
    unwritable = tmp_path / "log-is-a-directory"
    unwritable.mkdir()
    path = tmp_path / "config.json"
    path.write_text(json.dumps({**config("none", tmp_path), "log": str(unwritable)}), encoding="utf-8")
    payload = {"tool_name": "Bash", "tool_input": {"command": "gh issue comment 683"},
               "cwd": str(tmp_path), "session_id": "s"}
    result = subprocess.run([sys.executable, str(LIB / "github_write_guard.py"), "--hook",
                             "--config", str(path)], input=json.dumps(payload).encode(),
                            capture_output=True, timeout=60)
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert "could not be recorded in the run record" in output["permissionDecisionReason"]


def test_a_lost_refusal_log_reads_as_unknown_not_clean(tmp_path):
    clean = tmp_path / "clean.jsonl"
    clean.write_bytes(b"")
    record = {}
    allowance_module.record_refusals(record, clean)
    assert record == {"github_write_refusals": []}
    for lost in (tmp_path / "missing.jsonl", tmp_path):
        record = {}
        allowance_module.record_refusals(record, lost)
        assert record["github_write_refusals"] == [] and record["github_write_refusals_unknown"]


def test_a_damaged_refusal_log_line_reads_as_unknown(tmp_path):
    refused = {"decision": "deny", "scope": "child", "command": "gh issue comment 1"}
    log = tmp_path / "log.jsonl"
    log.write_bytes((json.dumps(refused) + "\n\n").encode())
    record = {}
    allowance_module.record_refusals(record, log)
    assert "github_write_refusals_unknown" not in record  # an empty line is no damage
    # A line cut short, as by a launch stopped mid-write, may be the refusal that is lost.
    log.write_bytes((json.dumps(refused) + "\n" + '{"decision": "deny", "comm').encode())
    record = {}
    allowance_module.record_refusals(record, log)
    assert [r["command"] for r in record["github_write_refusals"]] == ["gh issue comment 1"]
    assert "could not be read" in record["github_write_refusals_unknown"]


def test_a_dispatch_carrying_the_cloud_sentence_is_refused_locally(tree):
    allowance = config("branch", tree)["allowance"]
    prompt = ("Build.\n\n" + allowance_module.cloud_sentence("build")).encode()
    with pytest.raises(allowance_module.BoundError):
        allowance_module.needs_notice(allowance, prompt)


@pytest.mark.parametrize("command", [
    "nice -n 10 gh pr merge 1",
    "nice --adjustment 10 gh pr merge 1",
    "timeout -k 5 10 gh pr merge 1",
    "timeout --signal KILL 10 gh pr merge 1",
    "timeout --kill-after=5 10 gh pr merge 1",
    # An option nobody listed leaves its value in program position; the signature still refuses it.
    "nice --unlisted 5 gh pr merge 1",
])
def test_a_write_behind_a_pass_through_program_is_judged(tree, command):
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", [
    "env -S 'gh pr merge 1'",
    "env --split-string='gh pr merge 1'",
    "env -S'gh pr merge 1'",
    "env -C . -S 'gh pr merge 1'",
    "env --unlisted 5 gh pr merge 1",
])
def test_a_write_env_runs_is_judged(tree, command):
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", ["env -S 'git status'", "env FOO=1 git status"])
def test_a_harmless_command_env_runs_passes(tree, command):
    assert decision(command, tree, "branch") == "allow"


@pytest.mark.parametrize("command", [
    "echo 1 | xargs --max-args 1 gh pr merge",
    "echo 1 | xargs --delimiter x gh pr merge",
    "echo 1 | xargs --max-args=1 gh pr merge",
    "echo 1 | xargs -n 1 gh pr merge",
    # --replace takes its value only joined by "=", so the word after it is the program.
    "echo 1 | xargs --replace gh pr merge",
    "echo 1 | xargs --unlisted 5 gh pr merge",
])
def test_a_write_xargs_runs_is_judged(tree, command):
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", ["nice -n 10 git status", "timeout -k 5 10 git status",
                                     "nice -n 10 python -c pass",
                                     "echo 1 | xargs --max-args 1 git status"])
def test_a_harmless_command_behind_a_pass_through_program_passes(tree, command):
    assert decision(command, tree, "branch") == "allow"


def test_an_api_grant_matches_with_or_without_the_leading_slash(tree):
    body = grant_body(stage="build", write="api", target="POST /repos/o/r/issues/5/labels")
    accepted = allowance_module.validate_grant(allowance_module.parse_grant(9, body), brief_comment=7,
                                               brief_body=BRIEF, stage="build", resumed=True,
                                               repository="o/r")
    assert accepted["target"] == "POST repos/o/r/issues/5/labels"
    for target in (accepted["target"], "POST /repos/o/r/issues/5/labels"):
        grant = {**accepted, "target": target}
        for command in ("gh api -X POST repos/o/r/issues/5/labels -f labels[]=x",
                        "gh api -X POST /repos/o/r/issues/5/labels -f labels[]=x"):
            assert decision(command, tree, "branch", grants=[grant]) == "allow", (target, command)


def test_a_tag_grant_permits_its_tag_and_no_ref_wide_push(tree):
    grant = {"marker": 1, "brief": 2, "row": 4, "stage": "build", "write": "push",
             "target": "o/r:refs/tags/v1"}
    assert decision("git push origin HEAD:refs/tags/v1", tree, "branch", grants=[grant]) == "allow"
    for command in ("git push --tags origin", "git push origin --tags",
                    "git push --follow-tags origin", "git push --all origin"):
        assert decision(command, tree, "branch", grants=[grant]) == "deny", command


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
    bash = allowance_module.bash_executable()
    allowance_module.write_wrapper(wrapper, path, bash)
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
                                               stage="artifact", resumed=True, repository="o/r")
    assert accepted["target"] == "o/r:refs/heads/probe" and accepted["row"] == 4


@pytest.mark.parametrize("body, stage, resumed", [
    (grant_body(brief=8), "artifact", True),
    (grant_body(row=9), "artifact", True),
    (grant_body().replace("a real push", "a real deploy"), "artifact", True),
    (grant_body(), "build", True),
    (grant_body(), "artifact", False),
    (grant_body(target="refs/tags/x"), "artifact", True),
    # Outside the work's repository, whatever the write.
    (grant_body(target="other/x:refs/heads/probe"), "artifact", True),
    (grant_body(write="comment", target="other/x#5"), "artifact", True),
    (grant_body(write="api", target="POST repos/other/x/issues/5/comments"), "artifact", True),
    (grant_body(write="api", target="PATCH user"), "artifact", True),
])
def test_a_grant_without_an_affirmed_row_is_refused(body, stage, resumed):
    grant = allowance_module.parse_grant(9, body)
    with pytest.raises(allowance_module.GrantError):
        allowance_module.validate_grant(grant, brief_comment=7, brief_body=BRIEF, stage=stage,
                                        resumed=resumed, repository="o/r")


def test_cloud_record_says_the_block_did_not_run():
    record = allowance_module.cloud_record("build", "change", "report")
    assert record["command_check"]["status"] == "not-run"
    assert "remote" in record["command_check"]["reason"]
    assert record["allowance"]["pushes"] == ["change", "report"]


@pytest.mark.parametrize("stage", ["build", "floor", "review-disposition"])
def test_a_cloud_build_or_repair_may_push_the_change_and_report_branches(stage):
    text = allowance_module.cloud_sentence(stage)
    assert "a push to the change branch and to its report branch" in text and "post nothing" in text


def test_a_cloud_author_may_push_only_its_report_branch():
    text = allowance_module.cloud_sentence("artifact")
    assert "change branch" not in text
    assert "a push to its report branch" in text and "post nothing" in text
    assert allowance_module.cloud_record("artifact", "change", "report")["allowance"]["pushes"] == ["report"]


@pytest.mark.skipif(allowance_module.bash_executable() is None, reason="no bash")
def test_the_installed_prefix_names_the_bash_its_self_test_ran(tmp_path):
    env = dict(os.environ)
    allowance = allowance_module.allowance_for("use", repository="o/r", branch=None, pull_request=None)
    bound = allowance_module.prepare(tmp_path, allowance, carrier="shell-prefix", root=tmp_path, env=env)
    wrapper = Path(bound["env"]["CLAUDE_CODE_SHELL_PREFIX"])
    bash = allowance_module.bash_executable(env)
    assert f'exec "{bash.replace(chr(92), "/")}" -c "$1"' in wrapper.read_text(encoding="utf-8")
    # The self-test ran this installed file, and no separate one exists to drift from it.
    assert sorted(p.name for p in tmp_path.glob("*.sh")) == [wrapper.name]
    # Its own refusal went to the launch log, which was emptied before the launch.
    assert Path(bound["log"]).read_bytes() == b""


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


@pytest.mark.parametrize("command", [
    "gh label list", "gh run download 123", "gh pr checkout 12", "gh repo list",
    "gh secret list", "gh variable get NAME", "gh ruleset list", "gh --version", "gh help",
])
@pytest.mark.parametrize("kind", ["none", "branch"])
def test_read_only_gh_subcommands_stay_open(tree, command, kind):
    assert decision(command, tree, kind) == "allow"


@pytest.mark.parametrize("command", [
    "gh label create bug", "gh run rerun 123", "gh release create v1", "gh secret set X",
    "gh variable set X", "gh ruleset delete 1", "gh gist create f", "gh repo create o/x",
])
def test_gh_subcommands_that_write_stay_refused(tree, command):
    assert decision(command, tree, "branch") == "deny"


def _no_password(env):
    result = subprocess.run(["git", "credential", "fill"], input=b"protocol=https\nhost=github.com\n\n",
                            capture_output=True, env=env, timeout=60)
    return b"password=" not in result.stdout and result.returncode != 0


def test_the_credential_removal_survives_an_environment_that_drops_empty_variables(tmp_path):
    helper = tmp_path / "helper.sh"
    helper.write_text("#!/bin/sh\necho username=u\necho password=fake-secret\n", encoding="utf-8")
    helper.chmod(0o755)
    global_config = tmp_path / "gitconfig"
    global_config.write_text(
        f"[credential \"https://github.com\"]\n\thelper = !sh {helper.as_posix()}\n", encoding="utf-8")
    base = {**os.environ, "GIT_CONFIG_GLOBAL": str(global_config), "GIT_CONFIG_NOSYSTEM": "1"}
    removed = allowance_module.without_push_credential(base)
    assert all(value != "" for name, value in removed.items() if name not in base)
    dropped = {name: value for name, value in removed.items() if value != ""}
    assert _no_password(removed) and _no_password(dropped)


def test_a_prepared_codex_environment_keeps_a_consistent_git_config_set(tmp_path, monkeypatch):
    env = {**os.environ, "GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "core.autocrlf",
           "GIT_CONFIG_VALUE_0": "false", "GIT_CONFIG_KEY_1": "credential.helper",
           "GIT_CONFIG_VALUE_1": "", "SOME_EMPTY": ""}
    allowance = allowance_module.allowance_for("artifact", repository="o/r", branch=None, pull_request=None)
    prepared = allowance_module.prepare_codex(allowance, env, None, temporary=tmp_path, root=tmp_path)["env"]
    count = int(prepared["GIT_CONFIG_COUNT"])
    assert all(f"GIT_CONFIG_KEY_{n}" in prepared and f"GIT_CONFIG_VALUE_{n}" in prepared
               for n in range(count))
    assert "'credential.helper='" in prepared["GIT_CONFIG_PARAMETERS"]
    assert "GIT_ASKPASS" not in prepared and prepared["GIT_TERMINAL_PROMPT"] == "0"
    git(tmp_path, "init", "-q")
    assert subprocess.run(["git", "-C", str(tmp_path), "status"], env=prepared, capture_output=True,
                          stdin=subprocess.DEVNULL, timeout=60).returncode == 0


def test_a_self_test_that_ran_and_failed_says_so(tmp_path, monkeypatch):
    cases = allowance_module._self_test_cases()
    label, allowance, command, _expected = cases[0]
    monkeypatch.setattr(allowance_module, "_self_test_cases",
                        lambda: [(label, allowance, command, "deny"), *cases[1:]])
    allowance = allowance_module.allowance_for("artifact", repository="o/r", branch=None, pull_request=None)
    with pytest.raises(allowance_module.BoundError) as failed:
        allowance_module.prepare(tmp_path, allowance, carrier="pretooluse-hook", root=tmp_path,
                                 env=dict(os.environ))
    assert "self-test failed" in str(failed.value) and "could not run" not in str(failed.value)
    assert not isinstance(failed.value, OSError)

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
    "git -c alias.x=push x origin HEAD:refs/heads/main",
    "git -c alias.x=push x origin HEAD:refs/heads/tradecraft/894-ab",
    "git --config-env=alias.x=VAR x origin HEAD:refs/heads/main",
    "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.x GIT_CONFIG_VALUE_0=push git x origin HEAD:refs/heads/main",
    "git config alias.p push; git p origin HEAD:refs/heads/main",
    "git send-pack https://github.com/o/r HEAD:refs/heads/main",
    "git http-push https://github.com/o/r HEAD:refs/heads/main",
    "git subtree push --prefix=x origin main",
    "git-push origin HEAD:refs/heads/main",
    "git-send-pack https://github.com/o/r HEAD:refs/heads/main",
    "setsid git-push origin HEAD:refs/heads/main",
])
def test_a_push_under_another_name_is_refused(tree, command):
    assert decision(command, tree, "branch") == "deny"


def test_a_refspec_naming_no_destination_is_refused_when_the_remote_maps_it(tree):
    # git sends `git push origin <own-branch>` to main once remote.origin.push maps it there.
    git(tree, "config", "remote.origin.push", "refs/heads/tradecraft/894-ab:refs/heads/main")
    assert decision("git push origin tradecraft/894-ab", tree, "branch") == "deny"
    # HEAD is not mapped by git, and an explicit destination is judged as itself.
    assert decision("git push origin HEAD", tree, "branch") == "allow"
    assert decision("git push origin HEAD:refs/heads/tradecraft/894-ab", tree, "branch") == "allow"
    assert decision("git push origin HEAD:refs/heads/main", tree, "branch") == "deny"


@pytest.mark.parametrize("command", [
    "git config remote.origin.push refs/heads/tradecraft/894-ab:refs/heads/main",
    "git config remote.origin.pushurl https://github.com/other/x.git",
    "git config --add remote.origin.push x:y; git push origin tradecraft/894-ab",
    "git config push.default matching",
    "git config url.https://github.com/other/.insteadOf https://github.com/o/",
    "git remote set-url --push origin https://github.com/other/x.git",
    "git remote rename origin old",
])
def test_writing_what_a_later_push_reads_is_refused(tree, command):
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", [
    "git config --get remote.origin.push",
    "git config user.name t",
    "git config --list",
    "git remote -v",
    "git remote add fixture ../fixture.git",
])
def test_reading_config_or_writing_other_keys_passes(tree, command):
    assert decision(command, tree, "branch") == "allow"


def test_env_chdir_holds_for_envs_own_command_only(tree, tmp_path):
    # The other tree's origin is the allowed repository; this tree's points elsewhere.
    other = tmp_path / "other"
    other.mkdir()
    git(other, "init", "-q", "-b", "tradecraft/894-ab")
    git(other, "remote", "add", "origin", "https://github.com/o/r.git")
    git(other, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "x")
    git(tree, "remote", "set-url", "origin", "https://github.com/someone/else.git")
    command = f"env -C {other.as_posix()} true; git push origin HEAD:refs/heads/tradecraft/894-ab"
    assert decision(command, tree, "branch") == "deny"
    # Inside env's own command the directory does hold.
    inside = f"env -C {other.as_posix()} git push origin HEAD:refs/heads/tradecraft/894-ab"
    assert decision(inside, tree, "branch") == "allow"


def test_a_stored_alias_is_judged_as_what_it_runs(tree):
    git(tree, "config", "alias.p", "push")
    git(tree, "config", "alias.sh", "!git push origin HEAD:refs/heads/tradecraft/894-ab")
    git(tree, "config", "alias.st", "status")
    assert decision("git p origin HEAD:refs/heads/main", tree, "branch") == "deny"
    # Judged, not refused: the step's own push through an alias still passes.
    assert decision("git p origin HEAD:refs/heads/tradecraft/894-ab", tree, "branch") == "allow"
    assert decision("git sh", tree, "branch") == "deny"  # a shell alias runs anything
    assert decision("git st", tree, "branch") == "allow"
    assert decision("git-push origin HEAD:refs/heads/tradecraft/894-ab", tree, "branch") == "allow"
    assert decision("git config --get alias.p", tree, "branch") == "allow"


@pytest.mark.parametrize("command", [
    "git --attr-source HEAD status",
    "git --no-pager --attr-source HEAD log -1",
    # Bare --exec-path prints git's exec path and stops; nothing after it runs.
    "git --exec-path push origin main",
    "git --some-future-option HEAD status",
])
def test_a_harmless_command_behind_a_global_option_passes(tree, command):
    assert decision(command, tree, "branch") == "allow"


@pytest.mark.parametrize("command", [
    "git push --repo=./x origin HEAD:refs/heads/main",
    "git push --repo ./x origin HEAD:refs/heads/main",
    "git push origin HEAD:refs/heads/main --repo=./x",
])
def test_a_named_repository_wins_over_repo_as_in_git(tree, command):
    assert decision(command, tree, "branch") == "deny"


def test_repo_names_the_destination_when_no_repository_is_given(tree):
    (tree.parent / "local.git").mkdir()
    assert decision(f"git push --repo={(tree.parent / 'local.git').as_posix()}", tree, "branch") == "allow"


@pytest.mark.parametrize("command", [
    "setsid gh pr merge 1",
    "sudo gh pr merge 1",
    "ionice -c3 gh pr merge 1",
    "flock /tmp/lock gh pr merge 1",
    "chronic gh pr merge 1",
    "unbuffer gh pr merge 1",
    "caffeinate gh pr merge 1",
    "watch -n1 gh pr merge 1",
    "parallel gh pr merge ::: 1",
    "busybox env gh pr merge 1",
    "setsid git push origin HEAD:refs/heads/main",
    "foo-unknown-wrapper gh pr merge 1",
    "setsid bash -c 'gh pr merge 1'",
])
def test_a_write_behind_any_wrapper_is_judged(tree, command):
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", [
    'grep -n "git push" file',
    "grep -rn gh lib",
    "echo gh pr merge 1",
    "python -m pytest -k claude",
    # Behind a wrapper the command is judged, not refused: the step's own push still passes.
    "setsid git push origin HEAD:refs/heads/tradecraft/894-ab",
    "foo-unknown-wrapper git status",
])
def test_a_command_that_only_names_a_judged_program_passes(tree, command):
    assert decision(command, tree, "branch") == "allow"


@pytest.mark.parametrize("command", [
    # shlex joins punctuation run together; the separators inside are still read.
    "true;(gh pr merge 1)",
    "echo x&&(gh pr merge 1)",
    "echo x||(gh pr merge 1)",
    "(echo x);gh pr merge 1",
    # Process substitution runs its body.
    "cat <(gh pr merge 1)",
    "tee >(gh pr merge 1) < /dev/null",
    # A shell with no -c and no script runs what is piped into it.
    "echo 'gh pr merge 1' | bash",
    "echo 'gh pr merge 1' | sh",
    "printf 'git push origin main' | bash -s",
    "(echo 'gh pr merge 1') | bash",
])
def test_a_write_hidden_in_shell_punctuation_or_a_pipe_is_judged(tree, command):
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", [
    "bash < script.sh",
    "cat notes.txt | bash script.sh",
    "echo 'gh pr merge 1' | grep gh",
    "echo hi; bash -c 'git status'",
    "git status && (git log -1)",
    "diff <(git show HEAD:a) a",
])
def test_a_shell_reading_a_script_or_a_harmless_pipe_passes(tree, command):
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


@pytest.mark.parametrize("command", [
    "cat <<EOF\nunterminated gh issue comment 1",
    "cat <<EOF\nunterminated hello",
    'echo "unbalanced gh issue comment 1',
    'echo "unbalanced hello',
    # Writes no signature names, before a later line the check cannot parse.
    'git send-pack https://github.com/o/r HEAD:refs/heads/main\necho "unbalanced',
    'npx @anthropic-ai/claude-code -p hi\necho "unbalanced',
    'git remote rename origin old\necho "unbalanced',
])
def test_text_that_cannot_be_parsed_is_refused_naming_the_cause(tree, command):
    verdict = guard.decide(command, str(tree), config("branch", tree))
    assert verdict["decision"] == "deny"
    assert "could not be parsed (" in verdict["reason"]
    assert decision('grep "git push" notes.txt', tree, "none") == "allow"


@pytest.mark.parametrize("command", ["cat <<< EOF\ngh pr merge 1\nEOF", "cat <<<EOF\ngh pr merge 1\nEOF"])
def test_a_here_string_is_one_word_and_the_lines_after_it_run(tree, command):
    assert decision(command, tree, "branch") == "deny"
    assert decision("grep x <<< 'gh pr merge 1'", tree, "branch") == "allow"


@pytest.mark.parametrize("command, expected", [
    # Spaced, the number is the command's argument: another pull request.
    ("gh pr comment --body x 13 > /dev/null", "deny"),
    ("gh pr comment --body x 13 2>&1", "deny"),
    # Joined, it names the stream redirected.
    ("gh pr comment 12 --body x 2>/dev/null", "allow"),
    ("gh pr comment 12 --body x 2>&1", "allow"),
    ("gh pr comment 12 --body x 1> /dev/null", "allow"),
])
def test_a_number_before_a_redirection_is_a_stream_only_when_joined(tree, command, expected):
    assert decision(command, tree, "review-disposition") == expected


def test_a_redirected_own_push_passes(tree):
    command = "git push origin HEAD:refs/heads/tradecraft/894-ab 2>&1"
    assert decision(command, tree, "branch") == "allow"


def test_an_unquoted_here_documents_substitutions_are_judged(tree):
    assert decision("cat <<EOF\n$(gh issue comment 683 -b x)\nEOF", tree, "none") == "deny"
    assert decision("cat <<EOF\n`gh issue comment 683 -b x`\nEOF", tree, "none") == "deny"
    # Quoted, the body is data; unquoted text with no substitution stays data too.
    assert decision("cat <<'EOF'\n$(gh issue comment 683 -b x)\nEOF", tree, "none") == "allow"
    assert decision("cat > m.txt <<EOF\ngh issue comment 3 and $HOME\nEOF", tree, "none") == "allow"


@pytest.mark.parametrize("command, expected", [
    ("# don't merge yet\ngh pr merge 1\n# it's done", "deny"),
    ("# Let's check\ngit status", "allow"),
    ("git status # it's fine", "allow"),
    ("echo a#b'c'", "allow"),
])
def test_a_comment_is_skipped_to_the_end_of_its_line(tree, command, expected):
    assert decision(command, tree, "branch") == expected


@pytest.mark.parametrize("command", [
    f"ENABLE_CLAUDEAI_MCP_SERVERS=true {CHILD} -p hi\nENABLE_CLAUDEAI_MCP_SERVERS=false",
    "export CLAUDE_CODE_SIMPLE=1; unset CLAUDE_CODE_SIMPLE",
])
def test_a_forbidden_assignment_is_not_taken_back_by_a_later_one(tree, command):
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", [
    "timeout 600 python -m pytest -k claude",
    "env PYTHONPATH=lib python -m pytest -k claude",
    "find . -name '*.py' | xargs grep -n \"git push\"",
])
def test_a_reading_program_behind_a_pass_through_is_placed(tree, command):
    assert decision(command, tree, "none") == "allow"


@pytest.mark.parametrize("command", ["git config remote.origin.url", "git config branch.main.remote"])
def test_a_bare_config_key_is_a_read(tree, command):
    assert decision(command, tree, "branch") == "allow"
    assert decision(command.replace("config ", "config --unset "), tree, "branch") == "deny"


def test_a_stored_follow_tags_refuses_the_own_push(tree):
    own = "git push origin HEAD:refs/heads/tradecraft/894-ab"
    assert decision("git config push.followTags true", tree, "branch") == "deny"
    git(tree, "config", "push.followTags", "true")
    assert decision(own, tree, "branch") == "deny"
    assert decision(own + " --no-follow-tags", tree, "branch") == "allow"


def test_a_push_that_also_pushes_submodules_is_refused(tree):
    own = "git push origin HEAD:refs/heads/tradecraft/894-ab"
    assert decision(own, tree, "branch") == "allow"
    assert decision(own + " --recurse-submodules=on-demand", tree, "branch") == "deny"
    assert decision(own + " --recurse-submodules", tree, "branch") == "deny"
    assert decision(own + " --recurse-submodules=no", tree, "branch") == "allow"
    assert decision("git config push.recurseSubmodules on-demand", tree, "branch") == "deny"
    assert decision("git config submodule.recurse true", tree, "branch") == "deny"
    git(tree, "config", "push.recurseSubmodules", "on-demand")
    assert decision(own, tree, "branch") == "deny"
    assert decision(own + " --recurse-submodules=no", tree, "branch") == "allow"
    git(tree, "config", "--unset", "push.recurseSubmodules")
    git(tree, "config", "submodule.recurse", "true")
    assert decision(own, tree, "branch") == "deny"
    assert decision(own + " --no-recurse-submodules", tree, "branch") == "allow"


def test_a_url_rewritten_by_a_stored_rule_is_refused(tree):
    own = "git push https://github.com/o/r.git HEAD:refs/heads/tradecraft/894-ab"
    assert decision(own, tree, "branch") == "allow"
    git(tree, "config", "url.https://github.com/other/x.git.pushInsteadOf", "https://github.com/o/r.git")
    assert decision(own, tree, "branch") == "deny"


def test_gh_repo_chooses_the_repository_a_comment_goes_to(tree, monkeypatch):
    monkeypatch.delenv("GH_REPO", raising=False)
    assert decision("gh pr comment 12 -b x", tree, "review-disposition") == "allow"
    assert decision("GH_REPO=other/x gh pr comment 12 -b x", tree, "review-disposition") == "deny"
    assert decision("GH_REPO=o/r gh pr comment 12 -b x", tree, "review-disposition") == "allow"
    assert decision("GH_REPO=other/x gh api repos/{owner}/{repo}/issues/12/comments -f body=x",
                    tree, "review-disposition") == "deny"
    monkeypatch.setenv("GH_REPO", "other/x")
    assert decision("gh pr comment 12 -b x", tree, "review-disposition") == "deny"


def test_brackets_in_a_graphql_string_hide_no_mutation(tree, monkeypatch):
    monkeypatch.setattr(guard, "thread_owner", lambda thread: ("o/r", 12))
    document = ('mutation { addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: "T", '
                'body: "("}) { clientMutationId } mergePullRequest(input: {pullRequestId: "P"}) '
                '{ clientMutationId } }')
    assert decision(f"gh api graphql -f query='{document}'", tree, "review-disposition") == "deny"
    reply = ('mutation { addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: "T", '
             'body: "a (b) {c}"}) { clientMutationId } }')
    assert decision(f"gh api graphql -f query='{reply}'", tree, "review-disposition") == "allow"
    # An escaped triple quote does not end a block string; an unterminated string is unknown.
    escaped = ('mutation { addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: "T", '
               'body: """prefix \\""" ("""}) { clientMutationId } mergePullRequest(input: '
               '{pullRequestId: "P"}) { clientMutationId } }')
    assert decision(f"gh api graphql -f query='{escaped}'", tree, "review-disposition") == "deny"
    block = ('mutation { addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: "T", '
             'body: """a \\""" (b"""}) { clientMutationId } }')
    assert decision(f"gh api graphql -f query='{block}'", tree, "review-disposition") == "allow"
    unterminated = ('mutation { addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: "T", '
                    'body: "a}) { clientMutationId } }')
    assert decision(f"gh api graphql -f query='{unterminated}'", tree, "review-disposition") == "deny"


def test_a_thread_id_quoted_in_a_reply_body_is_not_the_thread_judged(tree, monkeypatch):
    monkeypatch.setattr(guard, "thread_owner",
                        lambda thread: ("o/r", 12) if thread == "OWN" else ("o/r", 13))
    hidden = ('mutation { addPullRequestReviewThreadReply(input: { body: """pullRequestReviewThreadId: '
              '"OWN" """, pullRequestReviewThreadId: "OTHER" }) { clientMutationId } }')
    assert decision(f"gh api graphql -f query='{hidden}'", tree, "review-disposition") == "deny"
    quoted = ('mutation { addPullRequestReviewThreadReply(input: { body: "see threadId: \\\\"OTHER\\\\"", '
              'pullRequestReviewThreadId: "OWN" }) { clientMutationId } }')
    assert decision(f"gh api graphql -f query='{quoted}'", tree, "review-disposition") == "allow"
    # Two thread fields are each checked.
    both = ('mutation { addPullRequestReviewThreadReply(input: { pullRequestReviewThreadId: "OWN", '
            'pullRequestReviewThreadId: "OTHER", body: "x" }) { clientMutationId } }')
    assert decision(f"gh api graphql -f query='{both}'", tree, "review-disposition") == "deny"


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


@pytest.mark.parametrize("other", ["local", "cloud"])
def test_a_dispatch_stating_its_own_allowance_and_another_is_refused(tree, other):
    allowance = config("branch", tree)["allowance"]
    own = allowance_module.sentence(allowance)
    another = (allowance_module.sentence(config("none", tree)["allowance"]) if other == "local"
               else allowance_module.cloud_sentence("build"))
    with pytest.raises(allowance_module.BoundError):
        allowance_module.needs_notice(allowance, f"Build.\n\n{own}\n\n{another}".encode())
    assert allowance_module.needs_notice(allowance, f"Build.\n\n{own}".encode()) is False
    # The cloud route refuses the same mix of its own sentence and a local one.
    cloud = allowance_module.cloud_sentence("build")
    with pytest.raises(allowance_module.BoundError):
        allowance_module.cloud_notice("build", f"Build.\n\n{cloud}\n\n{own}".encode())
    assert allowance_module.cloud_notice("build", f"Build.\n\n{cloud}".encode()) == b""


def test_a_record_quoting_the_opening_does_not_refuse_the_launch(tree):
    # A governing record quoting the opening and the request route apart, as a design does.
    allowance = config("branch", tree)["allowance"]
    record = ('`sentence(allowance)` gives one paragraph per kind, containing:\n'
              '- "GitHub writes this step may make: ...", with "none" or the exact list.\n'
              '- "If the work needs any other write, do not make it: end your return with a '
              '**Write requests** section naming each write, why the work needs it, and what it '
              'would leave behind."\n'
              'A cloud run is told "GitHub writes this run may make:" and its pushes.\n')
    assert allowance_module.needs_notice(allowance, f"Build.\n\n{record}".encode()) is True
    own = allowance_module.sentence(allowance)
    assert allowance_module.needs_notice(allowance, f"Build.\n\n{record}\n\n{own}".encode()) is False
    assert allowance_module.cloud_notice("build", record.encode()) != b""


def test_the_hook_entry_names_bash_as_its_shell(tmp_path):
    entry = allowance_module.hook_entry(tmp_path / "config.json")
    assert [hook["shell"] for hook in entry["hooks"]] == ["bash"]


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
    # xargs adds piped words the check never sees, so no writer behind it is judged on its own words.
    "printf ':refs/heads/main' | xargs git push origin",
    "echo 1 | xargs --max-args 1 git status",
])
def test_a_write_xargs_runs_is_judged(tree, command):
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", ["nice -n 10 git status", "timeout -k 5 10 git status",
                                     "nice -n 10 python -c pass",
                                     "echo 1 | xargs --max-args 1 grep -n x"])
def test_a_harmless_command_behind_a_pass_through_program_passes(tree, command):
    assert decision(command, tree, "branch") == "allow"


@pytest.mark.parametrize("command", [
    f"env -i bash -c '{CHILD} -p hi'",
    "env --ignore-environment sh -c 'echo hi'",
    "env - nohup bash -c x",
    f"env -i setsid {CHILD} -p hi",
    f"env -i npx @anthropic-ai/claude-code -p hi",
    "env -i -S 'bash -c x'",
])
def test_env_i_before_a_shell_or_a_looked_through_program_is_refused(tree, command):
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", ["env FOO=1 bash -c 'git status'", "env -i git status",
                                     "env -i grep -n x f", "env -u FOO bash -c 'echo hi'"])
def test_env_without_i_or_before_a_reader_passes(tree, command):
    assert decision(command, tree, "branch") == "allow"


@pytest.mark.parametrize("command", [
    "pwsh -enc ZQBjAGgAbwA=",
    "powershell -EncodedCommand ZQBjAGgAbwA=",
    "pwsh -Comm 'gh pr merge 1'",
    "pwsh -Command:'gh pr merge 1'",
    "powershell git push origin HEAD:refs/heads/main",
    "pwsh -NoProfile -cwa 'gh pr merge 1'",
])
def test_a_powershell_command_in_an_unread_form_is_refused(tree, command):
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", ["pwsh -NoProfile -Command 'git status'",
                                     "powershell -NoProfile -ExecutionPolicy Bypass -File x.ps1",
                                     "pwsh script.ps1", "pwsh -c 'Get-ChildItem'"])
def test_a_powershell_command_in_a_read_form_is_judged(tree, command):
    assert decision(command, tree, "branch") == "allow"
    assert decision("pwsh -Command 'gh pr merge 1'", tree, "branch") == "deny"


def test_a_subcommand_git_does_not_build_in_is_refused_under_a_redirection(tree, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    git(other, "init", "-q")
    git(other, "config", "alias.p", "push origin HEAD:refs/heads/main")
    for command in (f"git --git-dir={other.as_posix()}/.git p", f"GIT_DIR={other.as_posix()}/.git git p",
                    f"GIT_CONFIG_GLOBAL={other.as_posix()}/.git/config git p", "git --exec-path=/x p"):
        assert decision(command, tree, "branch") == "deny", command
    # A read under a redirection still passes, and -C is followed, so its alias is read there.
    assert decision(f"git --git-dir={other.as_posix()}/.git log -1", tree, "branch") == "allow"
    assert decision(f"git -C {tree.as_posix()} status", tree, "branch") == "allow"
    assert decision(f"git -C {other.as_posix()} p", tree, "branch") == "deny"


@pytest.mark.parametrize("command", [
    "curl -sXPOST https://api.github.com/repos/o/r/issues/5/comments",
    "curl -sd@body.json https://api.github.com/repos/o/r/issues/5/comments",
    "curl --unknown-option https://api.github.com/repos/o/r",
    "curl -X DELETE https://api.github.com/repos/o/r/git/refs/heads/main",
    "Invoke-RestMethod -Meth Post https://api.github.com/repos/o/r/issues",
    "Invoke-RestMethod -Method:Post https://api.github.com/repos/o/r/issues",
    "irm -B x https://api.github.com/repos/o/r/issues",
    "iwr -Method Patch -Uri https://api.github.com/repos/o/r",
    "wget --method=POST https://api.github.com/repos/o/r/issues",
    "wget --method POST https://api.github.com/repos/o/r/issues",
    "wget --post-data=x https://api.github.com/repos/o/r/issues",
    "wget --body-file=b.json --method=PATCH https://api.github.com/repos/o/r",
    "wget --unknown-option https://api.github.com/repos/o/r",
    "wget -qE x https://api.github.com/repos/o/r",
])
def test_an_api_request_the_check_cannot_read_as_a_get_is_refused(tree, command):
    assert decision(command, tree, "branch") == "deny"


@pytest.mark.parametrize("command", [
    "curl -sSL https://api.github.com/repos/o/r",
    "curl -s -H 'Accept: application/json' https://api.github.com/repos/o/r",
    "curl -X GET -o out.json https://api.github.com/repos/o/r",
    "Invoke-RestMethod -Uri https://api.github.com/repos/o/r -Headers $h",
    "Invoke-RestMethod -Method Get https://api.github.com/repos/o/r",
    "curl -X POST https://example.com/x",
    "wget -qO- https://api.github.com/repos/o/r",
    "wget -q -O out.json --header 'Accept: application/json' https://api.github.com/repos/o/r",
    "wget --method=GET https://api.github.com/repos/o/r",
])
def test_a_plain_get_or_another_host_passes(tree, command):
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


def test_a_grant_cites_a_table_row_and_never_a_fenced_copy():
    table = "| Row | Why |\n|---|---|\n| **4. The artifact must test a real push.** | x |\n| **5. Other.** | y |\n"
    grant = allowance_module.parse_grant(9, grant_body())
    accepted = allowance_module.validate_grant(grant, brief_comment=7, brief_body=table,
                                               stage="artifact", resumed=True, repository="o/r")
    assert accepted["row"] == 4
    with pytest.raises(allowance_module.GrantError):
        allowance_module.parse_grant(9, "```\n" + grant_body() + "```\n")


def test_a_hook_path_bash_would_expand_is_refused():
    with pytest.raises(allowance_module.BoundError):
        allowance_module.hook_entry(Path("/tmp/$cache/github-write.json"))


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


def test_a_self_test_is_bounded_as_a_whole(tmp_path, monkeypatch):
    # Its own reads stop at the caller's end, as do its entry processes, so a launch reserves one bound.
    monkeypatch.setattr(guard, "READ_END", guard.READ_END)
    token = guard.READ_END.set(0.0)
    try:
        assert guard._read_timeout(20) == 0.001
    finally:
        guard.READ_END.reset(token)
    assert guard._read_timeout(20) == 20
    monkeypatch.setattr(allowance_module, "SELF_TEST_SECONDS", 0.0)
    allowance = allowance_module.allowance_for("artifact", repository="o/r", branch=None, pull_request=None)
    with pytest.raises(allowance_module.BoundError):
        allowance_module.prepare(tmp_path, allowance, carrier="pretooluse-hook", root=tmp_path,
                                 env=dict(os.environ))


@pytest.mark.parametrize("command, expected", [
    ("git --frobnicate send-pack https://github.com/o/r HEAD:refs/heads/main", "deny"),
    ("git --frobnicate value send-pack https://github.com/o/r HEAD:refs/heads/main", "deny"),
    ("git --frobnicate p origin HEAD:refs/heads/main", "deny"),
    ("git --frobnicate value p origin HEAD:refs/heads/main", "deny"),
    ("git --frobnicate subtree push --prefix=x origin main", "deny"),
    ("git --frobnicate HEAD status", "allow"),
    ("git --frobnicate log -1", "allow"),
    ("git --no-pager log -1", "allow"),
])
def test_an_unread_git_option_refuses_every_route_to_a_remote_behind_it(tree, command, expected):
    git(tree, "config", "alias.p", "push")
    assert decision(command, tree, "branch") == expected


@pytest.mark.parametrize("command, expected", [
    ("X=gh; $X issue comment 1 -R o/r --body x", "deny"),
    ("X=gh; ${X} issue comment 1 -R o/r --body x", "deny"),
    ("X='gh issue'; $X comment 1 -R o/r --body x", "deny"),
    ("X=echo; $X hello", "allow"),
    ("X='$X'; $X hello", "allow"),
])
def test_a_variable_assigned_on_the_line_is_judged_as_the_program_it_names(tree, command, expected):
    assert decision(command, tree, "branch") == expected


# --- a stretch builder's own change (#1011) -------------------------------------------------

def stretch_config(root, pull_request=None):
    allowance = allowance_module.allowance_for(
        "stretch", repository="o/r", branch="tradecraft/894-ab", pull_request=pull_request,
        issue=allowance_module.issue_of("o/r#5"))
    return {"allowance": allowance, "root": str(root), "child_settings": str(root / "child.json"),
            "scope": "parent"}


@pytest.fixture()
def stretch(tree, monkeypatch):
    # Pull request 12 was opened from the builder's branch; 13 from another; 14 cannot be read.
    owners = {12: ("o/r", "tradecraft/894-ab"), 13: ("o/r", "other")}
    monkeypatch.setattr(guard, "pull_owner", lambda repository, number: owners.get(number))
    monkeypatch.setattr(guard, "thread_owner", lambda thread: {"T12": ("o/r", 12),
                                                               "T13": ("o/r", 13)}.get(thread))
    (tree / "body.md").write_text("<!-- tradecraft:check-report:v1 stage=use -->\nx\n", encoding="utf-8")
    (tree / "plain.md").write_text("plain\n", encoding="utf-8")
    return tree


def stretch_decision(command, root, pull_request=None):
    return guard.decide(command, str(root), stretch_config(root, pull_request))


def _mutation(name, arguments):
    return "gh api graphql -f query='mutation{%s(input:{%s}){clientMutationId}}'" % (name, arguments)


@pytest.mark.parametrize("command", [
    "git push origin tradecraft/894-ab",
    "gh pr create --head tradecraft/894-ab --title t --body b",
    "gh pr create --head o:tradecraft/894-ab --title t --body b --base main --draft",
    "gh pr create --fill",
    "gh pr ready 12",
    "gh pr ready 12 --undo",
    "gh pr edit 12 --body-file plain.md",
    "gh pr edit 12 --title t",
    "gh api repos/o/r/pulls/12/comments/4242/replies -f body=x",
    "gh api -X POST repos/o/r/pulls/12/comments -F in_reply_to=4242 -f body=x",
    _mutation("addPullRequestReviewThreadReply", 'pullRequestReviewThreadId:"T12",body:"x"'),
    _mutation("resolveReviewThread", 'threadId:"T12"'),
    "gh pr comment 12 --body x",
    "gh issue comment 5 --body x",
    "gh api -X POST repos/o/r/issues/5/comments -f body=x",
    "gh api -X POST repos/o/r/issues/12/comments -f body=x",
    "git add lib/dispatch_seat.py",
    "git diff -- lib/dispatch_seat.py lib/dispatch_record.py",
    "python lib/work.py run use --repo o/r --issue 5",
    "cat lib/dispatch_implementer.py",
])
def test_a_stretch_builder_may_write_to_its_own_change(stretch, command):
    verdict = stretch_decision(command, stretch)
    assert verdict["decision"] == "allow", verdict["reason"]


def test_a_stretch_builder_writes_to_the_pull_request_its_allowance_names(stretch, monkeypatch):
    monkeypatch.setattr(guard, "pull_owner", lambda repository, number: None)
    assert stretch_decision("gh pr ready 20", stretch, pull_request=20)["decision"] == "allow"
    assert stretch_decision("gh pr ready 21", stretch, pull_request=20)["decision"] == "deny"


@pytest.mark.parametrize("command", [
    "gh pr create --head tradecraft/894-ab --title t --body b --label L",
    "gh pr create --head tradecraft/894-ab --title t --body b --reviewer someone",
    "gh pr create --head other --title t --body b",
    "gh pr create --head tradecraft/894-ab --title t --body b --repo other/x",
    "gh pr edit 12 --add-label L",
    "gh issue comment 6 --body x",
    "gh api -X POST repos/o/r/issues/6/comments -f body=x",
    "gh pr comment 13 --body x",
    "gh pr ready 13",
    "gh pr ready 14",
    "gh pr comment 14 --body x",
    "git push origin HEAD:refs/heads/other",
    "gh pr merge 12",
    "gh api -X PUT repos/o/r/pulls/12/merge",
    _mutation("mergePullRequest", 'pullRequestId:"P"'),
    _mutation("enablePullRequestAutoMerge", 'pullRequestId:"P"'),
    _mutation("markPullRequestReadyForReview", 'pullRequestId:"P"'),
    "gh release create v1",
    "gh workflow run ci.yml",
    "gh run rerun 1",
    "gh run cancel 1",
    "gh issue close 5",
    "gh issue edit 5 --title t",
    "gh pr close 12",
    "gh api -X PATCH repos/o/r/issues/comments/1 -f body=x",
    "gh api -X DELETE repos/o/r/issues/comments/1",
    "gh api -X PATCH repos/o/r/pulls/comments/1 -f body=x",
    "gh api -X DELETE repos/o/r/pulls/comments/1",
    "gh issue comment 5 --edit-last --body x",
    "gh pr comment 12 --delete-last",
    "gh issue comment 5 --body '<!-- tradecraft:check-report:v1 stage=use -->'",
    "gh issue comment 5 --body-file body.md",
    "gh pr comment 12 -F body.md",
    "gh issue comment 5 --body-file - <<'X'\n<!-- tradecraft:check-report:v1 -->\nX",
    "gh api -X POST repos/o/r/issues/5/comments -F body=@body.md",
    "gh api -X POST repos/o/r/issues/5/comments -f 'body=<!-- tradecraft:check-report:v1 -->'",
    "gh api repos/o/r/pulls/12/comments/4242/replies -f 'body=<!-- tradecraft:check-report:v1 -->'",
    "gh api repos/o/r/pulls/13/comments/4242/replies -f body=x",
    _mutation("addPullRequestReviewThreadReply",
              'pullRequestReviewThreadId:"T12",body:"<!-- tradecraft:check-report:v1 -->"'),
    _mutation("resolveReviewThread", 'threadId:"T13"'),
    _mutation("resolveReviewThread", 'threadId:"T99"'),
    "gh api repos/o/r/pulls/12/comments/$ID/replies -f body=x",
    *[_mutation(name, 'id:"C"') for name in (
        "updateIssueComment", "deleteIssueComment", "updatePullRequestReviewComment",
        "deletePullRequestReviewComment", "minimizeComment")],
])
def test_a_stretch_builder_is_refused_every_other_write(stretch, command):
    assert stretch_decision(command, stretch)["decision"] == "deny"


@pytest.mark.parametrize("command", [
    "lib/dispatch_seat.py --stage use",
    "python lib/dispatch_seat.py --help",
    "python3 -u lib/dispatch_implementer.py --stage build",
    "py -3 D:/plugin/lib/dispatch_record.py begin",
    "uv run python lib/dispatch_seat.py --help",
    "uv run lib/dispatch_seat.py --help",
    "python -m dispatch_seat --help",
    "python -X utf8 lib/dispatch_seat.py",
    "cd lib && python dispatch_seat.py",
    "bash -c 'python lib/dispatch_seat.py'",
])
def test_a_stretch_builder_is_refused_a_direct_launcher_call(stretch, command):
    verdict = stretch_decision(command, stretch)
    assert verdict["decision"] == "deny"
    assert "through the entrance" in verdict["reason"]


def test_a_direct_launcher_call_stays_open_outside_a_stretch(tree):
    assert decision("python lib/dispatch_seat.py --help", tree, "branch") == "allow"


def test_the_stretch_sentence_names_its_writes_and_how_to_reply():
    allowance = allowance_module.allowance_for("stretch", repository="o/r", branch="B",
                                               pull_request=None, issue=5)
    text = allowance_module.sentence(allowance)
    for part in ("a push to your own branch B of o/r", "opening a pull request from B in o/r",
                 "marking it ready", "editing its title and body", "the one you open from B",
                 "a comment on issue #5 of o/r", "written as digits", "in_reply_to",
                 "An id held in a shell variable is refused", "work.py run STAGE"):
        assert part in text
    assert text.count(allowance_module.SENTENCE_OPENING) == 1
    assert not allowance_module.needs_notice(allowance, text.encode("utf-8"))
    other = allowance_module.allowance_for("build", repository="o/r", branch="B", pull_request=None)
    with pytest.raises(allowance_module.BoundError):
        allowance_module.needs_notice(other, text.encode("utf-8"))
    with pytest.raises(allowance_module.BoundError):
        allowance_module.needs_notice(allowance, allowance_module.sentence(other).encode("utf-8"))
    assert allowance_module.allowance_for("stretch", repository="o/r", branch=None,
                                          pull_request=None, issue=5)["kind"] == "none"

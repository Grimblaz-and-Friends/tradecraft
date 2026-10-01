"""Behavioral tests for persist.py against real git repositories (a bare
origin plus a working clone built per test), on both OSes in CI. The
subdirectory-cwd, non-origin-remote, broad-pathspec, and hook-reset cases
exist because the 2026-08-15 adversarial review proved the original suite
structurally could not reach those shapes (ledger findings M7/M8/M10/M38)."""

import os
import importlib.util
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "persist.py"


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True)


def persist(cwd, *args):
    return run([sys.executable, str(SCRIPT), *args], cwd=cwd)


# Building and checking a bare origin plus a seeded clone produces identical
# content every time, so it is built once per module and copied per test. On
# Windows a launch costs an order of magnitude more than the copy. The one thing
# a copy cannot carry is the clone's `remote.origin.url`, which holds the
# template's absolute path: left alone, every test would push into the template's
# origin and see the others' commits. Rewriting it is the single launch
# `make_repo` still spends, and it is what keeps each test's origin its own.
# Module-scoped because CI runs the suite under `--dist loadfile`, which keeps a
# module on one worker, so the template is built once however many workers there
# are. [#649]
_SEED = None


@pytest.fixture(scope="module", autouse=True)
def _seed_repository(tmp_path_factory):
    """Install the template `make_repo` copies. Autouse so the helper's callers
    keep their signatures."""
    global _SEED
    seed = tmp_path_factory.mktemp("persist-seed")
    origin = seed / "origin.git"
    run(["git", "init", "--bare", "-b", "main", str(origin)], cwd=seed)
    work = seed / "work"
    run(["git", "clone", str(origin), str(work)], cwd=seed)
    run(["git", "config", "user.email", "t@example.com"], cwd=work)
    run(["git", "config", "user.name", "tester"], cwd=work)
    run(["git", "checkout", "-b", "main"], cwd=work)
    (work / "README.md").write_text("seed\n", encoding="utf-8")
    (work / "unrelated.txt").write_bytes(b"seed unrelated\n")
    run(["git", "add", "README.md", "unrelated.txt"], cwd=work)
    assert value(work, "config", "--bool", "maintenance.auto") == "false"
    run(["git", "commit", "-m", "seed commit"], cwd=work)
    run(["git", "push", "-u", "origin", "main"], cwd=work)
    _SEED = seed
    yield
    _SEED = None


def make_repo(tmp_path, origin_name="origin.git", ref_format="files"):
    origin = tmp_path / origin_name
    if ref_format == "reftable":
        work = tmp_path / "work"
        capability = run(["git", "init", "--ref-format=reftable", "-b", "main", str(work)], cwd=tmp_path)
        if capability.returncode:
            pytest.skip("Git cannot create a reftable repository: " + capability.stderr.strip())
        value(tmp_path, "init", "--bare", "--ref-format=reftable", "-b", "main", str(origin))
        value(work, "config", "user.email", "t@example.com")
        value(work, "config", "user.name", "tester")
        (work / "README.md").write_bytes(b"seed\n")
        (work / "unrelated.txt").write_bytes(b"seed unrelated\n")
        value(work, "add", "README.md", "unrelated.txt")
        value(work, "commit", "-m", "seed commit")
        value(work, "remote", "add", "origin", str(origin))
        value(work, "push", "-u", "origin", "main")
        return work
    shutil.copytree(_SEED / "origin.git", origin)
    work = tmp_path / "work"
    shutil.copytree(_SEED / "work", work)
    run(["git", "remote", "set-url", "origin", str(origin)], cwd=work)
    return work


def test_happy_path_pushes_and_verifies(tmp_path):
    work = make_repo(tmp_path)
    (work / "feature.txt").write_text("new\n", encoding="utf-8")
    result = persist(work, "-m", "add feature file for the happy-path test", "feature.txt")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith("persisted: ")
    local = run(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip()
    remote = run(["git", "ls-remote", "origin", "refs/heads/main"], cwd=work).stdout
    assert remote.startswith(local)


def test_root_relative_path_works_from_subdirectory_with_decoy(tmp_path):
    """The M8 shape: same-named file in a subdirectory must NOT be staged."""
    work = make_repo(tmp_path)
    (work / "notes.txt").write_text("root file - the intended one\n", encoding="utf-8")
    sub = work / "sub"
    sub.mkdir()
    (sub / "notes.txt").write_text("decoy\n", encoding="utf-8")
    result = persist(sub, "-m", "stage the root notes.txt from a subdirectory", "notes.txt")
    assert result.returncode == 0, result.stdout + result.stderr
    committed = run(["git", "show", "--name-only", "--format=", "HEAD"], cwd=work).stdout.split()
    assert committed == ["notes.txt"]


def test_repo_root_pathspec_is_refused(tmp_path):
    work = make_repo(tmp_path)
    (work / "feature.txt").write_text("new\n", encoding="utf-8")
    result = persist(work, "-m", "dot must be refused as broad staging", ".")
    assert result.returncode == 1
    assert "repository root is refused" in result.stdout


def test_glob_and_pathspec_magic_are_refused(tmp_path):
    work = make_repo(tmp_path)
    (work / "feature.txt").write_text("new\n", encoding="utf-8")
    for bad, phrase in (("*", "glob patterns are refused"), (":/", "pathspec magic is refused")):
        result = persist(work, "-m", "broad pathspec forms must be refused", bad)
        assert result.returncode == 1, bad
        assert phrase in result.stdout


def test_pushes_to_tracked_remote_not_hardcoded_origin(tmp_path):
    """The M10 shape: branch tracks 'fork'; origin must not receive the push."""
    work = make_repo(tmp_path)
    fork = tmp_path / "fork.git"
    run(["git", "init", "--bare", "-b", "main", str(fork)], cwd=tmp_path)
    run(["git", "remote", "add", "fork", str(fork)], cwd=work)
    run(["git", "push", "-u", "fork", "main"], cwd=work)
    origin_before = run(["git", "ls-remote", "origin", "refs/heads/main"], cwd=work).stdout
    (work / "feature.txt").write_text("new\n", encoding="utf-8")
    result = persist(work, "-m", "push must follow the tracked remote, fork", "feature.txt")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "-> fork/main" in result.stdout
    local = run(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip()
    assert run(["git", "ls-remote", "fork", "refs/heads/main"], cwd=work).stdout.startswith(local)
    assert run(["git", "ls-remote", "origin", "refs/heads/main"], cwd=work).stdout == origin_before


def test_new_remote_branch_is_refused(tmp_path):
    work = make_repo(tmp_path)
    run(["git", "checkout", "-b", "feature/new"], cwd=work)
    (work / "feature.txt").write_text("new\n", encoding="utf-8")
    result = persist(work, "-m", "creating a remote branch must be refused", "feature.txt")
    assert result.returncode == 1
    assert "does not exist" in result.stdout
    assert run(["git", "ls-remote", "origin", "refs/heads/feature/new"], cwd=work).stdout == ""


def test_failed_verification_is_reported(tmp_path):
    """A post-receive hook resets the ref, so the push 'succeeds' but the
    remote head never moves — the verification step must catch it (M12)."""
    work = make_repo(tmp_path)
    hook = tmp_path / "origin.git" / "hooks" / "post-receive"
    hook.write_bytes(b'#!/bin/sh\nwhile read old new ref; do git update-ref "$ref" "$old"; done\n')
    os.chmod(hook, 0o755)
    (work / "feature.txt").write_text("new\n", encoding="utf-8")
    result = persist(work, "-m", "verification must catch a reset remote ref", "feature.txt")
    assert result.returncode == 1
    assert "push not verified" in result.stdout


def test_refuses_preloaded_index(tmp_path):
    work = make_repo(tmp_path)
    (work / "sneaky.txt").write_text("staged by someone else\n", encoding="utf-8")
    run(["git", "add", "sneaky.txt"], cwd=work)
    (work / "feature.txt").write_text("new\n", encoding="utf-8")
    result = persist(work, "-m", "should refuse: index is preloaded", "feature.txt")
    assert result.returncode == 1
    assert "already has staged changes" in result.stdout


def test_refuses_when_nothing_to_commit(tmp_path):
    work = make_repo(tmp_path)
    result = persist(work, "-m", "should refuse: no changes at that path", "README.md")
    assert result.returncode == 1
    assert "nothing to commit" in result.stdout


def test_refuses_short_message(tmp_path):
    work = make_repo(tmp_path)
    (work / "feature.txt").write_text("new\n", encoding="utf-8")
    result = persist(work, "-m", "wip", "feature.txt")
    assert result.returncode == 1
    assert "too short" in result.stdout


def test_refuses_unexpected_branch(tmp_path):
    work = make_repo(tmp_path)
    (work / "feature.txt").write_text("new\n", encoding="utf-8")
    result = persist(work, "-m", "should refuse: branch mismatch", "--expect-branch", "release", "feature.txt")
    assert result.returncode == 1
    assert "expected 'release'" in result.stdout


def test_refuses_detached_head(tmp_path):
    work = make_repo(tmp_path)
    run(["git", "checkout", "--detach"], cwd=work)
    (work / "feature.txt").write_text("new\n", encoding="utf-8")
    result = persist(work, "-m", "should refuse: detached HEAD state", "feature.txt")
    assert result.returncode == 1
    assert "detached HEAD" in result.stdout


def test_rejected_push_fails_on_one_line_and_keeps_local_commit(tmp_path):
    work = make_repo(tmp_path)
    other = tmp_path / "other"
    run(["git", "clone", str(tmp_path / "origin.git"), str(other)], cwd=tmp_path)
    run(["git", "config", "user.email", "o@example.com"], cwd=other)
    run(["git", "config", "user.name", "other"], cwd=other)
    (other / "ahead.txt").write_text("origin moved on\n", encoding="utf-8")
    run(["git", "add", "ahead.txt"], cwd=other)
    run(["git", "commit", "-m", "origin advances"], cwd=other)
    run(["git", "push", "origin", "main"], cwd=other)

    (work / "feature.txt").write_text("new\n", encoding="utf-8")
    result = persist(work, "-m", "push should be rejected as non-fast-forward", "feature.txt")
    assert result.returncode == 1
    assert "push failed" in result.stdout
    assert "exists locally" in result.stdout
    assert len([ln for ln in result.stdout.splitlines() if ln.strip()]) == 1
    log = run(["git", "log", "-1", "--format=%s"], cwd=work).stdout
    assert "push should be rejected" in log


def value(work, *args):
    result = run(["git", *args], cwd=work)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def git_file(work, name):
    return (work / value(work, "rev-parse", "--git-path", name)).resolve()


def hook(work, name, body):
    """Git's shell launches a Python fixture on both Windows and Linux."""
    hooks = git_file(work, "hooks")
    program = hooks / (name + ".py")
    program.write_bytes(("from pathlib import Path\nimport os, subprocess, sys\n"
                         "def git(*args, **kwargs):\n"
                         "    return subprocess.run(['git', *args], stdin=subprocess.DEVNULL,\n"
                         "                          capture_output=True, check=True, **kwargs)\n"
                         + body).encode("utf-8"))
    launcher = hooks / name
    launcher.write_bytes(("#!/bin/sh\nexec " + shlex.quote(Path(sys.executable).as_posix())
                          + " " + shlex.quote(program.as_posix()) + ' "$@"\n').encode("utf-8"))
    os.chmod(launcher, 0o755)


def witness_push(work):
    origin = Path(value(work, "remote", "get-url", "origin"))
    hook(origin, "pre-receive", "Path('receive-attempted').write_bytes(b'push')\n")
    return origin / "receive-attempted"


def checked_change(work):
    start = value(work, "rev-parse", "HEAD")
    (work / "README.md").write_bytes(b"checked\n")
    value(work, "add", "README.md")
    checked = value(work, "write-tree")
    value(work, "reset", "--mixed", start)
    return start, checked


def mismatch_ids(result, checked):
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.startswith("not-persisted: committed content differs")
    assert len(result.stdout.splitlines()) == 1
    assert result.stdout.isascii()
    tree = re.search(r"checked tree ([0-9a-f]{40,64});", result.stdout).group(1)
    commit = re.search(r"run commit ([0-9a-f]{40,64});", result.stdout).group(1)
    assert tree == checked
    assert "restore promptly" in result.stdout and "git gc may prune" in result.stdout
    assert "running again lands the working files exactly as the hook left them" in result.stdout
    assert "run again only after checking and accepting that rewrite" in result.stdout
    assert "for a byte-exact file, take the restore route" in result.stdout
    assert f"git restore --source={tree} --worktree -- <paths>" in result.stdout
    return commit


@pytest.mark.parametrize("ref_format", ["files", "reftable"])
@pytest.mark.parametrize("rewrite", [False, True])
def test_ref_backends_persist_or_undo_hook_rewrite(tmp_path, ref_format, rewrite):
    work = make_repo(tmp_path, ref_format=ref_format)
    start, checked = checked_change(work)
    witness = witness_push(work)
    if rewrite:
        hook(work, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n")
    result = persist(work, "-m", "identify the run through Git's reflog interface", "README.md")
    if rewrite:
        mismatch_ids(result, checked)
        assert "undo completed" in result.stdout
        assert value(work, "rev-parse", "HEAD") == start
        assert value(work, "diff", "--cached", "--name-only") == ""
        assert (work / "README.md").read_bytes() == b"hook output\n"
        assert value(work, "ls-remote", "origin", "refs/heads/main").startswith(start)
        assert not witness.exists()
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        commit = value(work, "rev-parse", "HEAD")
        assert value(work, "rev-parse", f"{commit}^{{tree}}") == checked
        assert value(work, "ls-remote", "origin", "refs/heads/main").startswith(commit)
        assert witness.exists()


def scoped_change(work):
    start = value(work, "rev-parse", "HEAD")
    (work / "src/in/checked.txt").write_bytes(b"checked\n")
    value(work, "add", "src/in/checked.txt")
    checked = value(work, "write-tree")
    value(work, "reset", "HEAD", "--", "src/in/checked.txt")
    hook(work, "pre-commit", "Path('src/in/checked.txt').write_bytes(b'hook output\\n')\n"
         "git('add', 'src/in/checked.txt')\n")
    return start, checked


def scoped_seed(work):
    for name in ("src/in/checked.txt", "src/out/hidden.txt"):
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"seed\n")
    value(work, "add", "src")
    value(work, "commit", "-m", "seed directory-scoped fixture")
    value(work, "push", "origin", "main")


def assert_directory_retry_preserves_hidden_entry(work, start, checked, hidden, before):
    witness = witness_push(work)
    first = persist(work, "-m", "refuse rewrite without losing hidden index state", "src")
    rejected = mismatch_ids(first, checked)
    assert "undo completed" in first.stdout
    assert value(work, "rev-parse", "HEAD") == start
    assert value(work, "ls-files", "--stage", "--debug", "--sparse", "--", hidden) == before
    assert value(work, "diff", "--cached", "--name-only") == ""
    status = value(work, "status", "--porcelain")
    assert hidden not in status and " D " not in status
    assert value(work, "ls-remote", "origin", "refs/heads/main").startswith(start)
    assert not witness.exists()
    # Accept the observed, now checked rewrite and follow the directory route.
    assert (work / "src/in/checked.txt").read_bytes() == b"hook output\n"
    second = persist(work, "-m", "land only the accepted rewrite through a directory", "src")
    assert second.returncode == 0, second.stdout + second.stderr
    assert value(work, "diff", "--name-status", start, "HEAD") == "M\tsrc/in/checked.txt"
    assert value(work, "show", f"HEAD:{hidden}") == "seed"
    assert value(work, "ls-files", "--stage", "--debug", "--sparse", "--", hidden) == before
    assert run(["git", "merge-base", "--is-ancestor", rejected, "HEAD"], cwd=work).returncode == 1
    assert value(work, "ls-remote", "origin", "refs/heads/main").startswith(value(work, "rev-parse", "HEAD"))


@pytest.mark.parametrize("sparse_index", [False, True])
def test_sparse_cone_undo_and_directory_retry_keep_out_of_cone_file(tmp_path, sparse_index):
    work = make_repo(tmp_path)
    scoped_seed(work)
    value(work, "sparse-checkout", "init", "--cone",
          "--sparse-index" if sparse_index else "--no-sparse-index")
    value(work, "sparse-checkout", "set", "src/in")
    hidden = "src/out/hidden.txt"
    assert not (work / hidden).exists()
    sparse_patterns = git_file(work, "info/sparse-checkout").read_bytes()
    sparse_config = value(work, "config", "--get-regexp", "sparse|cone")
    before = value(work, "ls-files", "--stage", "--debug", "--sparse", "--", hidden)
    start, checked = scoped_change(work)
    assert_directory_retry_preserves_hidden_entry(work, start, checked, hidden, before)
    assert not (work / hidden).exists()
    assert git_file(work, "info/sparse-checkout").read_bytes() == sparse_patterns
    assert value(work, "config", "--get-regexp", "sparse|cone") == sparse_config


@pytest.mark.parametrize("flag", ["--skip-worktree", "--assume-unchanged"])
def test_hidden_edit_undo_and_directory_retry_preserve_index_flags(tmp_path, flag):
    work = make_repo(tmp_path)
    scoped_seed(work)
    hidden = "src/out/hidden.txt"
    value(work, "update-index", flag, hidden)
    (work / hidden).write_bytes(b"private local configuration\n")
    before = value(work, "ls-files", "--stage", "--debug", "--sparse", "--", hidden)
    start, checked = scoped_change(work)
    assert_directory_retry_preserves_hidden_entry(work, start, checked, hidden, before)
    assert (work / hidden).read_bytes() == b"private local configuration\n"


def test_post_commit_staging_survives_undo_and_blocks_directory_retry(tmp_path):
    work = make_repo(tmp_path)
    scoped_seed(work)
    start, checked = scoped_change(work)
    witness = witness_push(work)
    hook(work, "post-commit", "Path('unrelated.txt').write_bytes(b'another actor staged this\\n')\n"
         "git('add', 'unrelated.txt')\n"
         "Path('.post-index-entry').write_bytes(git('ls-files', '--stage', '--debug', '--', 'unrelated.txt').stdout)\n")
    first = persist(work, "-m", "retain unrelated staging created before undo", "src")
    mismatch_ids(first, checked)
    assert "undo completed" in first.stdout
    assert "unrelated index entries and flags retained" in first.stdout
    assert value(work, "rev-parse", "HEAD") == start
    assert value(work, "diff", "--cached", "--name-only") == "unrelated.txt"
    assert value(work, "show", ":unrelated.txt") == "another actor staged this"
    entry = run(["git", "ls-files", "--stage", "--debug", "--", "unrelated.txt"], cwd=work)
    assert entry.stdout.encode().replace(b"\r\n", b"\n") == (work / ".post-index-entry").read_bytes()
    assert "M  unrelated.txt" in value(work, "status", "--porcelain")
    second = persist(work, "-m", "do not inherit another actor's staged change", "src")
    assert second.returncode == 1 and "index already has staged changes" in second.stdout
    assert value(work, "diff", "--cached", "--name-only") == "unrelated.txt"
    assert value(work, "ls-remote", "origin", "refs/heads/main").startswith(start)
    assert not witness.exists()


@pytest.mark.parametrize("body", [
    "Path('hook-ran').write_bytes(b'yes')\n",
    "Path('hook-ran').write_bytes(b'yes')\nPath(sys.argv[1]).write_bytes(b'message rewritten by hook\\n')\n",
])
def test_unchanged_tree_and_message_only_hook_persist(tmp_path, body):
    work = make_repo(tmp_path)
    _, checked = checked_change(work)
    name = "commit-msg" if "sys.argv" in body else "pre-commit"
    hook(work, name, body)
    result = persist(work, "-m", "keep content even if message is rewritten", "README.md")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (work / "hook-ran").read_bytes() == b"yes"
    commit = value(work, "rev-parse", "HEAD")
    assert value(work, "rev-parse", f"{commit}^{{tree}}") == checked
    assert value(work, "ls-remote", "origin", "refs/heads/main").startswith(commit)
    if name == "commit-msg":
        assert value(work, "log", "-1", "--format=%s") == "message rewritten by hook"


@pytest.mark.parametrize("body, changed", [
    ("Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n", '"README.md"'),
    ("Path('added.txt').write_bytes(b'added by hook\\n')\ngit('add', 'added.txt')\n", '"added.txt"'),
    ("Path('README.md').unlink()\ngit('add', '-u')\n", '"README.md"'),
    ("git('update-index', '--chmod=+x', 'README.md')\n", '"README.md"'),
    ("Path('.hook-blob').write_bytes(b'hook-only blob\\n')\n"
     "blob = git('hash-object', '-w', '.hook-blob').stdout.decode().strip()\n"
     "git('-c', 'core.protectNTFS=false', 'update-index', '--add', '--cacheinfo', '100644,' + blob + ',odd\\nname-' + chr(233) + '.txt')\n",
     '"odd\\nname-\\u00e9.txt"'),
])
def test_whole_tree_mismatch_never_attempts_push_and_undo_preserves_work(tmp_path, body, changed):
    work = make_repo(tmp_path)
    start, checked = checked_change(work)
    (work / "unrelated.txt").write_bytes(b"unrelated working bytes\n")
    witness = witness_push(work)
    hook(work, "pre-commit", body)
    result = persist(work, "-m", "refuse changes to any part of the staged tree", "README.md")
    rejected = mismatch_ids(result, checked)
    assert changed in result.stdout
    assert "undo completed" in result.stdout
    assert value(work, "rev-parse", "HEAD") == start
    assert value(work, "write-tree") == value(work, "rev-parse", f"{start}^{{tree}}")
    assert value(work, "diff", "--cached", "--name-only") == ""
    assert value(work, "ls-remote", "origin", "refs/heads/main").startswith(start)
    assert not witness.exists()
    assert value(work, "show", f"{checked}:README.md") == "checked"
    assert (work / "unrelated.txt").read_bytes() == b"unrelated working bytes\n"
    assert value(work, "rev-parse", f"{rejected}^{{tree}}") != checked
    if "hook output" in body:
        assert (work / "README.md").read_bytes() == b"hook output\n"
    elif "unlink" in body:
        assert not (work / "README.md").exists()
    elif "added.txt" in body:
        assert (work / "added.txt").read_bytes() == b"added by hook\n"


def test_mismatch_bounds_paths_and_recovers_full_list(tmp_path):
    work = make_repo(tmp_path)
    _, checked = checked_change(work)
    hook(work, "pre-commit", "for n in range(13):\n"
         "    path = f'added-{n:02}.txt'\n"
         "    Path(path).write_bytes(b'hook addition')\n"
         "    git('add', path)\n")
    result = persist(work, "-m", "bound refusal while retaining all path names", "README.md")
    rejected = mismatch_ids(result, checked)
    assert "3 more path(s)" in result.stdout
    assert '"added-09.txt"' in result.stdout and '"added-10.txt"' not in result.stdout
    assert len(value(work, "diff", "--no-renames", "--name-only", checked, rejected).splitlines()) == 13


def test_revalidated_hook_output_can_land_without_rejected_commit(tmp_path):
    work = make_repo(tmp_path)
    _, checked = checked_change(work)
    hook(work, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n")
    first = persist(work, "-m", "refuse first hook rewrite for revalidation", "README.md")
    rejected = mismatch_ids(first, checked)
    assert (work / "README.md").read_bytes() == b"hook output\n"
    second = persist(work, "-m", "land the now checked hook output", "README.md")
    assert second.returncode == 0, second.stdout + second.stderr
    landed = value(work, "rev-parse", "HEAD")
    assert run(["git", "merge-base", "--is-ancestor", rejected, landed], cwd=work).returncode == 1
    assert value(work, "ls-remote", "origin", "refs/heads/main").startswith(landed)


def test_saved_tree_restore_is_path_scoped_and_accounts_for_additions(tmp_path):
    work = make_repo(tmp_path)
    _, checked = checked_change(work)
    # A tracked unrelated edit must survive the undo and the advised restore.
    (work / "unrelated.txt").write_bytes(b"unrelated edit\n")
    hook(work, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\n"
         "Path('added.txt').write_bytes(b'hook addition\\n')\ngit('add', 'README.md', 'added.txt')\n")
    result = persist(work, "-m", "retain the checked copy for path-scoped recovery", "README.md")
    mismatch_ids(result, checked)
    value(work, "restore", f"--source={checked}", "--worktree", "--", "README.md")
    (work / "added.txt").unlink()
    assert (work / "README.md").read_bytes().replace(b"\r\n", b"\n") == b"checked\n"
    assert (work / "unrelated.txt").read_bytes() == b"unrelated edit\n"
    assert value(work, "diff", "--cached", "--name-only") == ""


def descendant_hook(work, inherited=True):
    env = "os.environ.copy()" if inherited else "dict(os.environ, GIT_REFLOG_ACTION='another-session')"
    hook(work, "post-commit", "once = Path('.post-commit-once')\n"
         "if not once.exists():\n"
         "    once.write_bytes(b'yes')\n"
         "    Path('concurrent.txt').write_bytes(b'concurrent work\\n')\n"
         "    git('add', 'concurrent.txt')\n"
         f"    git('commit', '-m', 'concurrent descendant commit', env={env})\n")


@pytest.mark.parametrize("inherited", [True, False])
def test_post_commit_descendant_is_never_undone(tmp_path, inherited):
    work = make_repo(tmp_path)
    start, checked = checked_change(work)
    witness = witness_push(work)
    hook(work, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n")
    descendant_hook(work, inherited)
    result = persist(work, "-m", "retain descendant even when it inherits the token", "README.md")
    rejected = mismatch_ids(result, checked)
    descendant = value(work, "rev-parse", "HEAD")
    assert value(work, "rev-parse", "HEAD^") == rejected
    assert "undo skipped: conditional branch update failed" in result.stdout
    assert "inspect remaining local history/index before retrying" in result.stdout
    assert value(work, "diff", "--cached", "--name-only") == ""
    assert value(work, "show", f"{descendant}:concurrent.txt") == "concurrent work"
    assert value(work, "ls-remote", "origin", "refs/heads/main").startswith(start)
    assert not witness.exists()


def test_equal_tree_but_moved_branch_refuses_before_push(tmp_path):
    work = make_repo(tmp_path)
    start, _ = checked_change(work)
    witness = witness_push(work)
    descendant_hook(work)
    result = persist(work, "-m", "refuse moved head even though checked trees match", "README.md")
    assert result.returncode == 1
    assert "branch moved off run commit" in result.stdout
    assert value(work, "log", "-1", "--format=%s") == "concurrent descendant commit"
    assert value(work, "ls-remote", "origin", "refs/heads/main").startswith(start)
    assert not witness.exists()


def test_reflog_disabled_repository_gains_evidence_without_config_change(tmp_path):
    work = make_repo(tmp_path)
    value(work, "config", "core.logAllRefUpdates", "false")
    shutil.rmtree(git_file(work, "logs"))
    _, checked = checked_change(work)
    hook(work, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n")
    result = persist(work, "-m", "record identity in a repository without reflogs", "README.md")
    mismatch_ids(result, checked)
    assert "undo completed" in result.stdout
    assert git_file(work, "logs/refs/heads/main").exists()
    assert value(work, "config", "core.logAllRefUpdates") == "false"


@pytest.mark.parametrize("effect, phrase", [
    ("log.unlink()\n", "branch reflog unavailable"),
    ("log.write_bytes(log.read_bytes() + log.read_bytes().splitlines()[-1] + b'\\n')\n", "ambiguous"),
])
def test_uncertain_identity_refuses_without_touching_history_or_index(tmp_path, effect, phrase):
    work = make_repo(tmp_path)
    start, _ = checked_change(work)
    witness = witness_push(work)
    hook(work, "post-commit", "log = Path(git('rev-parse', '--git-path', 'logs/refs/heads/main').stdout.decode().strip())\n" + effect)
    result = persist(work, "-m", "refuse uncertain identity without an undo", "README.md")
    assert result.returncode == 1 and phrase in result.stdout
    assert "no undo or push" in result.stdout
    assert value(work, "rev-parse", "HEAD") != start
    assert value(work, "diff", "--cached", "--name-only") == ""
    assert not witness.exists()


def test_held_index_lock_prevents_undo_and_is_not_removed(tmp_path):
    work = make_repo(tmp_path)
    start, checked = checked_change(work)
    witness = witness_push(work)
    hook(work, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n")
    hook(work, "post-commit", "Path(git('rev-parse', '--git-path', 'index.lock').stdout.decode().strip()).write_bytes(b'another owner')\n")
    result = persist(work, "-m", "a lock owned elsewhere must prevent undo", "README.md")
    rejected = mismatch_ids(result, checked)
    assert "undo skipped" in result.stdout
    assert value(work, "rev-parse", "HEAD") == rejected != start
    assert git_file(work, "index.lock").read_bytes() == b"another owner"
    assert not witness.exists()


def test_rejecting_hook_remains_in_force(tmp_path):
    work = make_repo(tmp_path)
    start, _ = checked_change(work)
    witness = witness_push(work)
    hook(work, "pre-commit", "Path('hook-ran').write_bytes(b'yes')\n"
         "sys.stderr.write('repository hook rejected this commit\\n')\nsys.exit(1)\n")
    result = persist(work, "-m", "repository hook rejection must stay effective", "README.md")
    assert result.returncode == 1
    assert result.stdout.startswith("not-persisted: git commit failed: ")
    assert "repository hook rejected this commit" in result.stdout
    assert len(result.stdout.splitlines()) == 1
    assert (work / "hook-ran").read_bytes() == b"yes"
    assert value(work, "rev-parse", "HEAD") == start
    assert not witness.exists()


@pytest.fixture
def implementation(monkeypatch):
    spec = importlib.util.spec_from_file_location("persist_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # The interpreter's capture streams belong to pytest, not this script.
    monkeypatch.setattr(module, "utf8_stdio", lambda: None)
    return module


def invoke_main(module, work, monkeypatch, capsys):
    monkeypatch.chdir(work)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "-m", "check deterministic race or failure", "README.md"])
    with pytest.raises(SystemExit) as stopped:
        module.main()
    return subprocess.CompletedProcess([], stopped.value.code, capsys.readouterr().out, "")


def test_expected_old_update_preserves_a_ref_race_and_exact_index(tmp_path, implementation, monkeypatch, capsys):
    work = make_repo(tmp_path)
    start, checked = checked_change(work)
    witness = witness_push(work)
    hook(work, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n")
    original = implementation.run_git
    observed = {}

    def race(*args, **kwargs):
        if args[0] == "update-ref":
            commit = value(work, "rev-parse", "HEAD")
            observed["index"] = git_file(work, "index").read_bytes()
            observed["head"] = value(work, "commit-tree", f"{start}^{{tree}}", "-p", commit,
                                     "-m", "concurrent ref-only writer")
            value(work, "update-ref", "refs/heads/main", observed["head"], commit)
        return original(*args, **kwargs)

    monkeypatch.setattr(implementation, "run_git", race)
    result = invoke_main(implementation, work, monkeypatch, capsys)
    mismatch_ids(result, checked)
    assert "undo skipped: conditional branch update failed" in result.stdout
    assert value(work, "rev-parse", "HEAD") == observed["head"]
    assert git_file(work, "index").read_bytes() == observed["index"]
    assert not git_file(work, "index.lock").exists() and not witness.exists()


def test_index_install_failure_reports_incomplete_undo(tmp_path, implementation, monkeypatch, capsys):
    work = make_repo(tmp_path)
    start, checked = checked_change(work)
    witness = witness_push(work)
    hook(work, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n")

    def denied(*args):
        raise OSError("injected index replacement failure")

    monkeypatch.setattr(implementation.os, "replace", denied)
    result = invoke_main(implementation, work, monkeypatch, capsys)
    mismatch_ids(result, checked)
    assert "undo incomplete: branch update ran but index restoration failed" in result.stdout
    assert "inspect remaining local history/index before retrying" in result.stdout
    assert value(work, "rev-parse", "HEAD") == start
    assert value(work, "diff", "--cached", "--name-only") == "README.md"
    assert not git_file(work, "index.lock").exists() and not witness.exists()


def test_branch_movement_after_update_reports_observed_incomplete_recovery(tmp_path, implementation, monkeypatch, capsys):
    work = make_repo(tmp_path)
    start, checked = checked_change(work)
    hook(work, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n")
    real_replace = os.replace
    observed = {}

    def move_then_install(source, target):
        observed["head"] = value(work, "commit-tree", f"{start}^{{tree}}", "-p", start,
                                 "-m", "new ref writer after conditional update")
        value(work, "update-ref", "refs/heads/main", observed["head"], start)
        real_replace(source, target)

    monkeypatch.setattr(implementation.os, "replace", move_then_install)
    result = invoke_main(implementation, work, monkeypatch, capsys)
    mismatch_ids(result, checked)
    assert "undo incomplete" in result.stdout and "intervening work was retained" in result.stdout
    assert value(work, "rev-parse", "HEAD") == observed["head"]
    assert value(work, "write-tree") == value(work, "rev-parse", f"{start}^{{tree}}")


def test_push_uses_compared_commit_even_if_branch_moves_after_inspection(tmp_path, implementation, monkeypatch, capsys):
    work = make_repo(tmp_path)
    start, checked = checked_change(work)
    original = implementation.run_git
    observed = {}

    def race(*args, **kwargs):
        if args[0] == "push":
            observed["pushed"] = args[-1].split(":")[0]
            observed["head"] = value(work, "commit-tree", f"{start}^{{tree}}", "-p", observed["pushed"],
                                     "-m", "unchecked concurrent ref")
            value(work, "update-ref", "refs/heads/main", observed["head"], observed["pushed"])
        return original(*args, **kwargs)

    monkeypatch.setattr(implementation, "run_git", race)
    monkeypatch.chdir(work)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "-m", "push the checked object explicitly", "README.md"])
    implementation.main()
    assert capsys.readouterr().out.startswith("persisted:")
    assert value(work, "rev-parse", "HEAD") == observed["head"]
    assert value(work, "ls-remote", "origin", "refs/heads/main").startswith(observed["pushed"])
    assert value(work, "rev-parse", f"{observed['pushed']}^{{tree}}") == checked


def test_linked_worktree_undo_uses_its_own_index(tmp_path):
    work = make_repo(tmp_path)
    linked = tmp_path / "linked"
    value(work, "worktree", "add", "-b", "linked", str(linked))
    value(linked, "push", "-u", "origin", "linked")
    start, checked = checked_change(linked)
    main_index = git_file(work, "index").read_bytes()
    hook(linked, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n")
    result = persist(linked, "-m", "restore only the linked worktree index", "README.md")
    mismatch_ids(result, checked)
    assert "undo completed" in result.stdout
    assert value(linked, "rev-parse", "HEAD") == start
    assert value(linked, "diff", "--cached", "--name-only") == ""
    assert git_file(work, "index").read_bytes() == main_index


def test_changed_symbolic_branch_prevents_undo_of_recorded_branch(tmp_path):
    work = make_repo(tmp_path)
    _, checked = checked_change(work)
    witness = witness_push(work)
    hook(work, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n")
    hook(work, "post-commit", "git('update-ref', 'refs/heads/another', 'HEAD')\n"
         "git('symbolic-ref', 'HEAD', 'refs/heads/another')\n")
    result = persist(work, "-m", "do not undo after symbolic branch movement", "README.md")
    rejected = mismatch_ids(result, checked)
    assert "undo skipped: symbolic branch changed" in result.stdout
    assert value(work, "symbolic-ref", "HEAD") == "refs/heads/another"
    assert value(work, "rev-parse", "refs/heads/main") == rejected
    assert value(work, "diff", "--cached", "--name-only") == ""
    assert not witness.exists()


def test_equal_tree_but_changed_symbolic_branch_refuses_push(tmp_path):
    work = make_repo(tmp_path)
    start, _ = checked_change(work)
    witness = witness_push(work)
    hook(work, "post-commit", "git('update-ref', 'refs/heads/another', 'HEAD')\n"
         "git('symbolic-ref', 'HEAD', 'refs/heads/another')\n")
    result = persist(work, "-m", "refuse equal trees on a changed symbolic branch", "README.md")
    assert result.returncode == 1 and "branch moved off run commit" in result.stdout
    assert value(work, "symbolic-ref", "HEAD") == "refs/heads/another"
    assert value(work, "ls-remote", "origin", "refs/heads/main").startswith(start)
    assert not witness.exists()


def test_inconsistent_reflog_parent_never_authorizes_undo(tmp_path):
    work = make_repo(tmp_path)
    start, _ = checked_change(work)
    witness = witness_push(work)
    hook(work, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n")
    # Retain a real descendant, then leave only a token-matching event with
    # inconsistent old-object evidence. Its parent exposes the inconsistency.
    descendant_hook(work)
    program = git_file(work, "hooks/post-commit.py")
    program.write_bytes(program.read_bytes() +
        ("log = Path(git('rev-parse', '--git-path', 'logs/refs/heads/main').stdout.decode().strip())\n"
         "lines = log.read_bytes().splitlines()\n"
         "if len(lines) >= 2 and os.environ.get('GIT_REFLOG_ACTION', '').startswith('persist-'):\n"
         "    last = lines[-1].split(b' ', 1)\n"
         f"    log.write_bytes(b'{start}' + b' ' + last[1] + b'\\n')\n").encode("ascii"))
    result = persist(work, "-m", "do not trust a token whose parent disagrees", "README.md")
    assert result.returncode == 1
    assert "does not have the recorded start as its sole parent" in result.stdout
    assert "no undo or push" in result.stdout
    assert value(work, "log", "-1", "--format=%s") == "concurrent descendant commit"
    assert value(work, "diff", "--cached", "--name-only") == ""
    assert not witness.exists()


def test_missing_run_event_never_authorizes_undo(tmp_path):
    work = make_repo(tmp_path)
    _, _ = checked_change(work)
    hook(work, "post-commit", "log = Path(git('rev-parse', '--git-path', 'logs/refs/heads/main').stdout.decode().strip())\n"
         "log.write_bytes(log.read_bytes().replace(os.environ['GIT_REFLOG_ACTION'].encode(), b'other-action'))\n")
    result = persist(work, "-m", "missing run event cannot establish identity", "README.md")
    assert result.returncode == 1 and "missing or ambiguous" in result.stdout
    assert "no undo or push" in result.stdout
    assert value(work, "diff", "--cached", "--name-only") == ""


def test_inconsistent_preceding_reflog_event_refuses_identity(tmp_path):
    work = make_repo(tmp_path)
    start, _ = checked_change(work)
    witness = witness_push(work)
    hook(work, "post-commit",
         "log = Path(git('rev-parse', '--git-path', 'logs/refs/heads/main').stdout.decode().strip())\n"
         "lines = log.read_bytes().splitlines()\n"
         f"other = git('commit-tree', 'HEAD^{{tree}}', '-p', '{start}', '-m', 'other event').stdout.strip()\n"
         "fields, message = lines[-2].split(b'\\t', 1)\n"
         "parts = fields.split(b' ')\n"
         "parts[1] = other\n"
         "lines[-2] = b' '.join(parts) + b'\\t' + message\n"
         "log.write_bytes(b'\\n'.join(lines) + b'\\n')\n")
    result = persist(work, "-m", "require parent and preceding reflog evidence to agree", "README.md")
    assert result.returncode == 1 and "reflog transition disagrees" in result.stdout
    assert "no undo or push" in result.stdout
    assert value(work, "rev-parse", "HEAD") != start
    assert value(work, "diff", "--cached", "--name-only") == ""
    assert not witness.exists()


def test_index_preparation_failure_changes_neither_head_nor_index(tmp_path, implementation, monkeypatch, capsys):
    work = make_repo(tmp_path)
    _, checked = checked_change(work)
    hook(work, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n")
    original = implementation.run_git
    observed = {}

    def denied(*args, **kwargs):
        if "read-tree" in args:
            observed["head"] = value(work, "rev-parse", "HEAD")
            observed["index"] = git_file(work, "index").read_bytes()
            return subprocess.CompletedProcess([], 1, b"", b"injected preparation error")
        return original(*args, **kwargs)

    monkeypatch.setattr(implementation, "run_git", denied)
    result = invoke_main(implementation, work, monkeypatch, capsys)
    mismatch_ids(result, checked)
    assert "undo skipped: could not prepare restored index" in result.stdout
    assert value(work, "rev-parse", "HEAD") == observed["head"]
    assert git_file(work, "index").read_bytes() == observed["index"]


@pytest.mark.parametrize("change, reason", [
    ("unrelated", "unrelated index entries or flags would change"),
    ("content", "run's index paths do not match the recorded start"),
    ("flags", "index entry flags would change"),
    ("format", "unrecognized index inspection record"),
])
def test_prepared_index_invariants_refuse_before_moving_ref(tmp_path, implementation, monkeypatch, capsys, change, reason):
    work = make_repo(tmp_path)
    _, checked = checked_change(work)
    witness = witness_push(work)
    hook(work, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n")
    original = implementation.run_git
    observed = {}

    def corrupt_preparation(*args, **kwargs):
        if args[0] == "ls-files" and change == "format" and kwargs.get("env"):
            return subprocess.CompletedProcess([], 0, b"unknown inspection format", b"")
        result = original(*args, **kwargs)
        if args[0] == "read-tree":
            observed["head"] = value(work, "rev-parse", "HEAD")
            observed["index"] = git_file(work, "index").read_bytes()
            env = kwargs["env"]
            if change == "unrelated":
                original("update-index", "--force-remove", "unrelated.txt", env=env)
            elif change == "content":
                blob = value(work, "rev-parse", "HEAD:README.md")
                original("update-index", "--cacheinfo", "100644," + blob + ",README.md", env=env)
            elif change == "flags":
                original("update-index", "--assume-unchanged", "README.md", env=env)
        return result

    monkeypatch.setattr(implementation, "run_git", corrupt_preparation)
    result = invoke_main(implementation, work, monkeypatch, capsys)
    rejected = mismatch_ids(result, checked)
    assert "undo skipped" in result.stdout and reason in result.stdout, result.stdout
    assert value(work, "rev-parse", "HEAD") == rejected
    if change != "format":
        assert git_file(work, "index").read_bytes() == observed["index"]
    assert not git_file(work, "index.lock").exists() and not witness.exists()


def test_index_lock_excludes_normal_git_writes_during_undo(tmp_path, implementation, monkeypatch, capsys):
    work = make_repo(tmp_path)
    start, checked = checked_change(work)
    hook(work, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n")
    real_replace = os.replace
    attempts = []

    def try_git_before_install(source, target):
        (work / "concurrent.txt").write_bytes(b"concurrent working edit\n")
        attempts.append(run(["git", "add", "concurrent.txt"], cwd=work))
        attempts.append(run(["git", "commit", "--allow-empty", "-m", "concurrent writer"], cwd=work))
        real_replace(source, target)

    monkeypatch.setattr(implementation.os, "replace", try_git_before_install)
    result = invoke_main(implementation, work, monkeypatch, capsys)
    mismatch_ids(result, checked)
    assert all(attempt.returncode != 0 and "index.lock" in attempt.stderr for attempt in attempts)
    assert "undo completed" in result.stdout
    assert value(work, "rev-parse", "HEAD") == start
    assert value(work, "diff", "--cached", "--name-only") == ""
    assert (work / "concurrent.txt").read_bytes() == b"concurrent working edit\n"


@pytest.mark.parametrize("move", ["index", "symbolic", "unrelated", "flags"])
def test_final_recovery_verification_detects_later_index_or_symbolic_movement(tmp_path, implementation, monkeypatch, capsys, move):
    work = make_repo(tmp_path)
    start, checked = checked_change(work)
    hook(work, "pre-commit", "Path('README.md').write_bytes(b'hook output\\n')\ngit('add', 'README.md')\n")
    real_replace = os.replace
    observed = {}

    def install_then_move(source, target):
        observed["commit"] = value(work, "reflog", "show", "--format=%H", "-n", "2", "main").splitlines()[-1]
        real_replace(source, target)
        if move == "index":
            value(work, "read-tree", observed["commit"])
        elif move == "symbolic":
            value(work, "update-ref", "refs/heads/another", start)
            value(work, "symbolic-ref", "HEAD", "refs/heads/another")
        elif move == "unrelated":
            (work / "unrelated.txt").write_bytes(b"new staged work after install\n")
            value(work, "add", "unrelated.txt")
        else:
            value(work, "update-index", "--skip-worktree", "unrelated.txt")

    monkeypatch.setattr(implementation.os, "replace", install_then_move)
    result = invoke_main(implementation, work, monkeypatch, capsys)
    rejected = mismatch_ids(result, checked)
    assert "undo incomplete" in result.stdout
    if move == "index":
        assert value(work, "write-tree") == value(work, "rev-parse", f"{rejected}^{{tree}}")
    elif move == "symbolic":
        assert value(work, "symbolic-ref", "HEAD") == "refs/heads/another"
    elif move == "unrelated":
        assert value(work, "show", ":unrelated.txt") == "new staged work after install"
        assert value(work, "diff", "--cached", "--name-only") == "unrelated.txt"
    else:
        assert value(work, "ls-files", "-v", "--", "unrelated.txt") == "S unrelated.txt"

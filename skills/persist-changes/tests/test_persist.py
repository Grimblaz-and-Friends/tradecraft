"""Behavioral tests for persist.py against real git repositories (a bare
origin plus a working clone built per test), on both OSes in CI. The
subdirectory-cwd, non-origin-remote, broad-pathspec, and hook-reset cases
exist because the 2026-08-15 adversarial review proved the original suite
structurally could not reach those shapes (ledger findings M7/M8/M10/M38)."""

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "persist.py"


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True)


def persist(cwd, *args):
    return run([sys.executable, str(SCRIPT), *args], cwd=cwd)


def make_repo(tmp_path, origin_name="origin.git"):
    origin = tmp_path / origin_name
    run(["git", "init", "--bare", "-b", "main", str(origin)], cwd=tmp_path)
    work = tmp_path / "work"
    run(["git", "clone", str(origin), str(work)], cwd=tmp_path)
    run(["git", "config", "user.email", "t@example.com"], cwd=work)
    run(["git", "config", "user.name", "tester"], cwd=work)
    run(["git", "checkout", "-b", "main"], cwd=work)
    (work / "README.md").write_text("seed\n", encoding="utf-8")
    run(["git", "add", "README.md"], cwd=work)
    run(["git", "commit", "-m", "seed commit"], cwd=work)
    run(["git", "push", "-u", "origin", "main"], cwd=work)
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

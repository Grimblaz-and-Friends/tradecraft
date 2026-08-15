"""Behavioral tests for persist.py against real git repositories (a bare
origin plus a working clone built per test), on both OSes in CI."""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "persist.py"


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def persist(work, *args):
    return run([sys.executable, str(SCRIPT), *args], cwd=work)


def make_repo(tmp_path):
    origin = tmp_path / "origin.git"
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


def test_rejected_push_fails_loudly_and_keeps_local_commit(tmp_path):
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
    assert "push rejected" in result.stdout
    assert "exists locally" in result.stdout
    log = run(["git", "log", "-1", "--format=%s"], cwd=work).stdout
    assert "push should be rejected" in log

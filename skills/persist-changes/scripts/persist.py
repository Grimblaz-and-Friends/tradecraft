#!/usr/bin/env python3
"""persist-changes: stage exactly the named paths, commit, push, verify.

Guard rationale and incident records live in the skill's SKILL.md — the
broad-staging guard carries recorded incidents; the others carry service
rationale from the predecessor project, promoted with the skill under
ADR-009 and awaiting their first recorded incident here.

Mechanical contract:
  - operates on the repository containing the caller's cwd; all paths are
    resolved from that repository's root, regardless of where it is invoked
  - refuses detached HEAD, an unexpected branch, and a pre-loaded index
  - stages only the named files/directories; refuses the repo root ('.'),
    pathspec magic (':...'), and glob patterns — there is no broad-staging form
  - pushes to the branch's configured upstream remote (sole remote as the
    fallback); refuses to create a new remote branch; no force flag exists
  - verifies the pushed commit is the remote branch head before claiming success

Output contract: exactly one line — 'persisted: ...' (exit 0) or
'not-persisted: <reason>' (exit 1) — printed safely on any console encoding.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Shared code lives in lib/, which ships beside this cell, so the import
# resolves in a source checkout and an installed plugin alike -- against
# this file's own directory, never the working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from winio import utf8_stdio  # noqa: E402

MIN_MESSAGE_CHARS = 10
GLOB_CHARS = set("*?[")


def emit(line: str) -> None:
    """One-line output that survives legacy console codepages."""
    line = " | ".join(part.strip() for part in line.splitlines() if part.strip())
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", errors="replace").decode("ascii"))


def fail(reason: str) -> None:
    emit(f"not-persisted: {reason}")
    sys.exit(1)


def git(*args: str) -> str:
    proc = subprocess.run(["git", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        fail(f"git {args[0]} failed: {(proc.stderr or proc.stdout).strip()}")
    return proc.stdout.strip()


def resolve_paths(top: Path, raw_paths: list[str]) -> list[str]:
    """Named paths -> repo-root-relative pathspecs, with broad forms refused."""
    resolved = []
    for raw in raw_paths:
        if raw.startswith(":"):
            fail(f"pathspec magic is refused ('{raw}') -- name plain files or directories")
        if GLOB_CHARS & set(raw):
            fail(f"glob patterns are refused ('{raw}') -- name each path explicitly")
        candidate = Path(raw)
        absolute = candidate if candidate.is_absolute() else (top / candidate)
        absolute = Path(os.path.normpath(absolute))
        try:
            rel = absolute.relative_to(top)
        except ValueError:
            fail(f"'{raw}' is outside this repository")
        if str(rel) == ".":
            fail("the repository root is refused -- staging everything is the "
                 "broad form this skill exists to prevent; name the paths")
        resolved.append(rel.as_posix())
    return resolved


def pick_remote(branch: str) -> tuple[str, str]:
    """The branch's upstream remote, or the sole remote; never a guess."""
    proc = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        capture_output=True, text=True,
    )
    if proc.returncode == 0 and "/" in proc.stdout.strip():
        remote, _, remote_branch = proc.stdout.strip().partition("/")
        return remote, remote_branch
    remotes = [r for r in git("remote").splitlines() if r.strip()]
    if len(remotes) == 1:
        return remotes[0], branch
    if not remotes:
        fail("no git remote is configured")
    fail(f"branch '{branch}' has no upstream and {len(remotes)} remotes exist "
         "-- set an upstream (git branch --set-upstream-to) so the push target is explicit")
    raise AssertionError  # unreachable; fail() exits


def main() -> None:
    utf8_stdio()
    parser = argparse.ArgumentParser(description=
        "Stage exactly the paths named, commit, and push -- verifying the push landed. Exits 0 only on a verified push; every other outcome is one line reading not-persisted: <reason>, on exit 1.")
    parser.add_argument("paths", nargs="+", help="files or directories to stage, and nothing else")
    parser.add_argument("-m", "--message", required=True, help="commit message")
    parser.add_argument("--expect-branch", help="refuse to run unless HEAD is this branch")
    args = parser.parse_args()

    if len(args.message.strip()) < MIN_MESSAGE_CHARS:
        fail("commit message is too short to be honest")

    top = Path(git("rev-parse", "--show-toplevel"))
    pathspecs = resolve_paths(top, args.paths)
    os.chdir(top)

    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        fail("detached HEAD -- check out a branch first")
    if args.expect_branch and branch != args.expect_branch:
        fail(f"on branch '{branch}', expected '{args.expect_branch}'")

    pre_staged = git("diff", "--cached", "--name-only")
    if pre_staged:
        first = pre_staged.splitlines()[0]
        fail(f"index already has staged changes ('{first}', ...) -- "
             "unstage them or name them explicitly")

    remote, remote_branch = pick_remote(branch)
    if not git("ls-remote", remote, f"refs/heads/{remote_branch}"):
        fail(f"remote branch {remote}/{remote_branch} does not exist -- "
             "publishing a new branch is outside this skill; push it deliberately first")

    git("add", "--", *pathspecs)
    staged = git("diff", "--cached", "--name-only").splitlines()
    if not staged:
        fail("nothing to commit for the given paths")

    git("commit", "-m", args.message)
    sha = git("rev-parse", "HEAD")

    push = subprocess.run(
        ["git", "push", remote, f"HEAD:refs/heads/{remote_branch}"],
        capture_output=True, text=True,
    )
    if push.returncode != 0:
        detail = (push.stderr or push.stdout).strip()
        fail(f"push failed: {detail} -- commit {sha[:12]} exists locally; "
             "inspect the push error before retrying")

    remote_head = git("ls-remote", remote, f"refs/heads/{remote_branch}")
    if not remote_head.startswith(sha):
        remote_sha = remote_head.split()[0][:12] if remote_head else "absent"
        fail(f"push not verified: remote head is {remote_sha}, local is {sha[:12]}")

    emit(f"persisted: {sha[:12]} -> {remote}/{remote_branch} ({len(staged)} file(s))")


if __name__ == "__main__":
    main()

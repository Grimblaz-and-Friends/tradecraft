#!/usr/bin/env python3
"""persist-changes: stage exactly the named paths, commit, push, verify.

Guards (each from a recorded incident — see SKILL.md):
  - refuses detached HEAD and (optionally) an unexpected branch
  - refuses a pre-loaded index: nothing may be staged before this runs
  - stages only the paths given; there is no broad-staging path
  - force-push does not exist here by construction
  - verifies the pushed commit is the remote branch head before claiming success

Exit 0 only on a verified push; otherwise exit 1 with one loud reason line.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

MIN_MESSAGE_CHARS = 10


def fail(reason: str) -> None:
    print(f"not-persisted: {reason}")
    sys.exit(1)


def git(*args: str) -> str:
    proc = subprocess.run(["git", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        fail(f"git {args[0]} failed: {(proc.stderr or proc.stdout).strip()}")
    return proc.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="files or directories to stage, and nothing else")
    parser.add_argument("-m", "--message", required=True, help="commit message")
    parser.add_argument("--expect-branch", help="refuse to run unless HEAD is this branch")
    args = parser.parse_args()

    if len(args.message.strip()) < MIN_MESSAGE_CHARS:
        fail("commit message is too short to be honest")

    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        fail("detached HEAD — check out a branch first")
    if args.expect_branch and branch != args.expect_branch:
        fail(f"on branch '{branch}', expected '{args.expect_branch}'")

    pre_staged = git("diff", "--cached", "--name-only")
    if pre_staged:
        first = pre_staged.splitlines()[0]
        fail(
            f"index already has staged changes ('{first}', ...) — "
            "unstage them or name them explicitly"
        )

    git("add", "--", *args.paths)
    staged = git("diff", "--cached", "--name-only").splitlines()
    if not staged:
        fail("nothing to commit for the given paths")

    git("commit", "-m", args.message)
    sha = git("rev-parse", "HEAD")

    push = subprocess.run(
        ["git", "push", "origin", f"HEAD:refs/heads/{branch}"],
        capture_output=True,
        text=True,
    )
    if push.returncode != 0:
        fail(
            f"push rejected ({(push.stderr or push.stdout).strip().splitlines()[-1]}) — "
            f"commit {sha[:12]} exists locally; fetch and assess before retrying"
        )

    remote = git("ls-remote", "origin", f"refs/heads/{branch}")
    if not remote.startswith(sha):
        remote_sha = remote.split()[0][:12] if remote else "absent"
        fail(f"push not verified: remote head is {remote_sha}, local is {sha[:12]}")

    print(f"persisted: {sha[:12]} -> origin/{branch} ({len(staged)} file(s))")


if __name__ == "__main__":
    main()

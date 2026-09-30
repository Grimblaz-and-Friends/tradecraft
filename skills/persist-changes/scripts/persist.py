#!/usr/bin/env python3
"""persist-changes: stage named paths, compare committed content, push, verify.

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
  - keeps repository hooks in force; compares the run's committed tree with
    the saved staged tree before pushing the identified commit explicitly
  - retracts only this run's unpushed mismatching commit on its recorded start
    head, using an index lock and an expected-old branch update; working files
    stay untouched; only the run's changed index paths are restored, preserving
    unrelated entries and flags; uncertain state never authorizes an undo
  - commit identity uses a unique reflog action; a repository with reflogs
    disabled gains a branch reflog (no persistent configuration change)
  - verifies the pushed commit is the remote branch head before claiming success

Output contract: exactly one line — 'persisted: ...' (exit 0) or
'not-persisted: <reason>' (exit 1) — printed safely on any console encoding.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import uuid
from contextlib import ExitStack
from pathlib import Path

# Shared code lives in lib/, which ships beside this cell, so the import
# resolves in a source checkout and an installed plugin alike -- against
# this file's own directory, never the working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from winio import utf8_stdio  # noqa: E402

MIN_MESSAGE_CHARS = 10
GLOB_CHARS = set("*?[")
MAX_MISMATCH_PATHS = 10


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


def run_git(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], stdin=subprocess.DEVNULL,
                          capture_output=True, env=env)


def decoded(data: bytes) -> str:
    return data.decode("utf-8", errors="backslashreplace").strip()


def detail(proc: subprocess.CompletedProcess) -> str:
    return decoded(proc.stderr or proc.stdout)


def git(*args: str, env: dict[str, str] | None = None) -> str:
    proc = run_git(*args, env=env)
    if proc.returncode != 0:
        fail(f"git {args[0]} failed: {detail(proc)}")
    return decoded(proc.stdout)


def git_path(name: str) -> Path:
    return Path(git("rev-parse", "--git-path", name)).resolve()


def identify_commit(ref: str, start: str, action: str) -> tuple[str | None, str]:
    """Find this invocation's unique reflog transition from its recorded start.

    Git's reflog interface works with both files and reftable storage. A
    descendant can inherit the token, so require the sole parent to be the
    recorded start, and the preceding event to agree when one is available.
    With reflogs previously disabled, the run can be the first recorded event.
    """
    log = run_git("reflog", "show", "--format=%H%x00%gs", "-z", ref)
    if log.returncode or not log.stdout:
        return None, f"branch reflog unavailable: {detail(log) or 'no recorded events'}"
    fields = log.stdout.split(b"\0")
    if fields[-1] or len(fields) % 2 != 1:
        return None, "branch reflog evidence is malformed"
    events = list(zip(fields[::2], fields[1::2]))
    candidates = []
    matched_token = False
    for position, (obj, message) in enumerate(events):
        if not message.startswith(action.encode("ascii") + b": "):
            continue
        matched_token = True
        commit = obj.decode("ascii", errors="replace")
        parents = run_git("rev-list", "--parents", "-n", "1", commit)
        if not parents.returncode and decoded(parents.stdout).split() == [commit, start]:
            candidates.append((commit, position))
    if len(candidates) != 1:
        if matched_token and not candidates:
            return None, "run's commit does not have the recorded start as its sole parent"
        return None, "run's commit identity is missing or ambiguous"
    commit, position = candidates[0]
    if position + 1 < len(events) and events[position + 1][0] != start.encode("ascii"):
        return None, "run's reflog transition disagrees with the recorded start"
    return commit, ""


def index_entries(env: dict[str, str] | None = None) -> dict:
    """Snapshot content, stat data and every exposed flag, including sparse dirs.

    Compare Git's debug records verbatim rather than interpreting flag bits.
    This format is for inspection and may evolve: an unfamiliar record refuses
    recovery before the ref is moved, rather than weakening the comparison.
    """
    proc = run_git("ls-files", "--stage", "--debug", "--sparse", "-z", env=env)
    if proc.returncode:
        raise ValueError(f"cannot inspect index entries: {detail(proc)}")
    entries = {}
    data = proc.stdout
    while data:
        header, sep, rest = data.partition(b"\0")
        lines = rest.split(b"\n", 5)
        content, tab, path = header.partition(b"\t")
        parts = content.split()
        if (not sep or not tab or len(parts) != 3 or len(lines) != 6
                or b"flags: " not in lines[4]):
            raise ValueError("unrecognized index inspection record")
        flags = lines[4].rpartition(b"flags: ")[2]
        int(flags, 16)  # Unknown output never counts as evidence of preserved flags.
        key = (path, parts[2])
        if key in entries:
            raise ValueError("duplicate index inspection record")
        entries[key] = (content, b"\n".join(lines[:5]), flags)
        data = lines[5]
    return entries


def verify_restored_entries(before: dict, after: dict, start: str, commit: str) -> None:
    changed = run_git("diff", "--no-renames", "--name-only", "-z", start, commit, "--")
    tree = run_git("ls-tree", "-r", "-z", "--full-tree", start)
    if changed.returncode or tree.returncode:
        raise ValueError("cannot establish the run's changed paths and start entries")
    paths = set(changed.stdout.split(b"\0")) - {b""}
    if ({k: v for k, v in before.items() if k[0] not in paths}
            != {k: v for k, v in after.items() if k[0] not in paths}):
        raise ValueError("unrelated index entries or flags would change")
    expected = {}
    for record in tree.stdout.split(b"\0"):
        if not record:
            continue
        fields, _, path = record.partition(b"\t")
        mode, _, obj = fields.split()
        if path in paths:
            expected[(path, b"0")] = mode + b" " + obj + b" 0"
    actual = {k: v[0] for k, v in after.items() if k[0] in paths}
    if actual != expected:
        raise ValueError("the run's index paths do not match the recorded start")
    for key in before.keys() & after.keys():
        if before[key][2] != after[key][2]:
            raise ValueError("index entry flags would change")


def undo_mismatch(ref: str, start: str, commit: str) -> tuple[bool, str]:
    """Restore ref/index under the index lock, without writing working files.

    Copy the live index under its lock, then let Git carry forward unrelated
    entries in a two-tree, index-only merge. Verify content and flags before
    changing the ref. Never retry or undo intervening work.
    """
    index = git_path("index")
    lock = index.with_name(index.name + ".lock")
    owns_lock = False
    moved = False
    installed = False
    try:
        with tempfile.TemporaryDirectory(prefix="persist-index-", dir=index.parent) as scratch, ExitStack() as cleanup:
            prepared = Path(scratch) / "index"
            env = dict(os.environ, GIT_INDEX_FILE=str(prepared))
            with lock.open("xb") as stream:
                owns_lock = True
                cleanup.callback(lambda: lock.unlink() if owns_lock else None)
                prepared.write_bytes(index.read_bytes())
                before = index_entries(env)
                preparation = run_git("read-tree", "-m", "-i", commit, start, env=env)
                if preparation.returncode:
                    return False, f"undo skipped: could not prepare restored index: {detail(preparation)}"
                expected_entries = index_entries(env)
                verify_restored_entries(before, expected_entries, start, commit)
                stream.write(prepared.read_bytes())
                stream.flush()
                os.fsync(stream.fileno())
            symbolic = run_git("symbolic-ref", "-q", "HEAD")
            if symbolic.returncode or decoded(symbolic.stdout) != ref:
                return False, "undo skipped: symbolic branch changed"
            # Identity already established the immutable commit's sole parent.
            # The expected-old update is the head guard, without a redundant
            # check whose answer could change before the write.
            update = run_git("update-ref", "-m", "persist: retract rewritten unpushed commit",
                             ref, start, commit)
            if update.returncode:
                return False, f"undo skipped: conditional branch update failed: {detail(update)}"
            moved = True
            # Close the file before replacing it: Windows cannot rename an
            # open file. The exclusive .lock remains present until replacement.
            os.replace(lock, index)
            owns_lock = False
            installed = True
            actual_entries = index_entries()
            symbolic = run_git("symbolic-ref", "-q", "HEAD")
            head = run_git("rev-parse", ref)
            if (symbolic.returncode or head.returncode
                    or actual_entries != expected_entries
                    or decoded(symbolic.stdout) != ref or decoded(head.stdout) != start):
                return False, ("undo incomplete: branch update and index replacement ran, "
                               "but final branch/index no longer match the verified recovery; "
                               "intervening work was retained")
            return True, (f"undo completed: branch and run's index paths restored to {start}; "
                          "unrelated index entries and flags retained")
    except (OSError, ValueError) as exc:
        state = ("incomplete: branch/index restoration ran but verification or cleanup failed" if installed
                 else "incomplete: branch update ran but index restoration failed" if moved
                 else "skipped")
        return False, f"undo {state}: {exc}"


def refuse_mismatch(ref: str, start: str, commit: str, checked: str, tree: str) -> None:
    paths = run_git("diff", "--no-renames", "--name-only", "-z", checked, tree, "--")
    if paths.returncode:
        changed = f"changed paths unavailable: {detail(paths)}"
    else:
        names = [p for p in paths.stdout.split(b"\0") if p]
        changed = ", ".join(json.dumps(p.decode("utf-8", errors="surrogateescape"),
                                      ensure_ascii=True) for p in names[:MAX_MISMATCH_PATHS])
        if len(names) > MAX_MISMATCH_PATHS:
            changed += f", {len(names) - MAX_MISMATCH_PATHS} more path(s)"
    complete, undo = undo_mismatch(ref, start, commit)
    inspect = "" if complete else "inspect remaining local history/index before retrying; "
    fail(f"committed content differs from staged content: {changed}; "
         f"run commit {commit}; checked tree {checked}; {undo}; "
         f"all paths: git diff --no-renames --name-only {checked} {commit}; "
         f"{inspect}running again lands the working files exactly as the hook left them: "
         "run again only after checking and accepting that rewrite; for a byte-exact file, "
         "take the restore route: restore intended paths "
         f"with git restore --source={checked} --worktree -- <paths> and inspect/remove "
         "hook-only additions; restore promptly: routine git gc may prune the "
         "unreferenced checked tree")


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
    proc = run_git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if proc.returncode == 0 and "/" in decoded(proc.stdout):
        remote, _, remote_branch = decoded(proc.stdout).partition("/")
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
        "Stage named paths, commit with hooks in force, compare committed and staged content, then push the checked commit and verify the remote head. Exits 0 only when both checks pass; refusals read not-persisted: <reason> on exit 1.")
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
    ref = git("symbolic-ref", "-q", "HEAD")
    start = git("rev-parse", ref)

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

    checked = git("write-tree")
    action = f"persist-{uuid.uuid4().hex}"
    commit_run = run_git("-c", "core.logAllRefUpdates=true", "commit", "-m", args.message,
                         env=dict(os.environ, GIT_REFLOG_ACTION=action))
    if commit_run.returncode != 0:
        fail(f"git commit failed: {detail(commit_run)}")
    sha, identity_error = identify_commit(ref, start, action)
    if sha is None:
        fail(f"{identity_error}; no undo or push; checked tree {checked}; "
             "inspect remaining local history/index before retrying")
    tree = git("rev-parse", f"{sha}^{{tree}}")
    if tree != checked:
        refuse_mismatch(ref, start, sha, checked, tree)
    symbolic = run_git("symbolic-ref", "-q", "HEAD")
    if symbolic.returncode or decoded(symbolic.stdout) != ref or git("rev-parse", ref) != sha:
        fail(f"branch moved off run commit {sha} before push; no undo or push; "
             "inspect remaining local history/index before retrying")

    push = run_git("push", remote, f"{sha}:refs/heads/{remote_branch}")
    if push.returncode != 0:
        fail(f"push failed: {detail(push)} -- commit {sha[:12]} exists locally; "
             "inspect the push error before retrying")

    remote_head = git("ls-remote", remote, f"refs/heads/{remote_branch}")
    if not remote_head or remote_head.split()[0] != sha:
        remote_sha = remote_head.split()[0][:12] if remote_head else "absent"
        fail(f"push not verified: remote head is {remote_sha}, local is {sha[:12]}")

    emit(f"persisted: {sha[:12]} -> {remote}/{remote_branch} ({len(staged)} file(s))")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""A PR touching the shipped zone bumps the plugin version (doctrine, "The flow").

Measured as **the pull request against its merge base**, never per-commit: this
repo squash-merges, so the PR is the commit that lands, and a per-commit reading
fails every intermediate commit of a multi-commit branch. A first attempt at this
guard enforced per-branch while citing per-commit; the mismatch was a review
finding, and ADR-003 was corrected rather than the guard.

The file set is that merge-base diff **plus the working tree** — unstaged,
staged, and untracked — and the version is read from the working tree too. So a
local run answers "would this be lawful if I committed everything right now",
which is deliberately *not* the same question CI answers: CI checks out clean,
sees only commits, and will differ from a dirty local run in both directions.

**Two bounds, not one.** The new version must exceed the version at the merge
base *and* the version at the base ref's own tip. The merge base alone answers
"did this branch raise the version it started from", which is not the question
a consumer has: a branch cut before another change landed bumps onto a version
`main` already carries and reads clean, and stays clean right up to the merge
button. That went wrong five recorded times (#110). The tip is what makes the
answer about the version rather than about this branch's history.

Three outcomes, not two — and the third is why this exists at all:

    0  pass          shipped zone untouched, or touched and the version rose
                      past both bounds
    1  fail          shipped zone touched and the version did not rise, or rose
                      onto one the base ref already carries
    2  undetermined  the question could not be answered

**Undetermined is a failure.** The withdrawn predecessor went silent whenever
its merge base had moved — a state every merge into the base produces, so its
most common real condition was the one it could not see — and printed the same
line as a clean pass. Four failure modes were invisible that way. Anything this
script cannot establish, it says out loud and exits non-zero.

Usage:  python tools/check_version_bump.py [--base REF]
Default base is origin/main, then main.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Shared with the shipped zone, which is the lawful direction: repo-only
# code may import shipped code. Resolved from this file rather than the
# working directory, so the script runs from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from winio import utf8_stdio  # noqa: E402
MANIFEST = ".claude-plugin/plugin.json"
# The manifest field whose edit cannot count as a shipped-zone change, because
# raising it is what this guard demands and counting it would make every bump
# its own justification. The exemption is this FIELD and not the file: the
# manifest also carries `name` and `description`, which are consumer-facing
# copy, and excluding the whole file let changed copy ship at an unchanged
# version (#20). The circularity argument reaches one key; it was spending the
# whole file.
EXEMPT_FIELD = "version"
# ADR-004's shipped zone. `.claude-plugin/` is in it; the manifest's exemption
# is applied per-field below rather than by dropping the path here.
SHIPPED = (
    "skills/", "lib/", "commands/", "agents/", "hooks/", ".claude-plugin/",
)

PASS, FAIL, UNDETERMINED = 0, 1, 2
NUL = chr(0)


def _git(*args: str) -> tuple[int, str, str]:
    """Returns (returncode, stdout, stderr).

    `core.quotePath=false` is not optional: git's default octal-escapes any
    non-ASCII path and wraps it in double quotes, so `"skills/cafÃ©.md"`
    never matches `startswith("skills/")` and a shipped-zone file goes unseen —
    a false pass, which is the one outcome this guard exists to refuse. It was
    named in the predecessor guard's own withdrawal list, alongside the
    untracked-files gap, and closing one without the other left it live.

    stderr is returned because an UNDETERMINED that names the command but not
    the failure leaves the operator with nothing to act on.
    """
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "-c", "core.quotePath=false", *args],
        stdin=subprocess.DEVNULL,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, (proc.stdout or ""), (proc.stderr or "").strip()


def _paths(out: str) -> list[str]:
    """Split NUL-delimited git output.

    `-z` rather than line-splitting because `core.quotePath=false` only stops
    git quoting non-ASCII: newlines, double quotes and backslashes in a path are
    C-quoted regardless, and a line-oriented read then misses the shipped-zone
    prefix — a false pass. Deliberately no `.strip()` on stdout either; that
    would eat a trailing space from the final pathname.
    """
    return [f for f in out.split(NUL) if f]


def _resolve_base(explicit: str | None) -> tuple[str | None, str, str, str]:
    """Return (merge-base sha, tip sha, ref name, reason).

    A None merge-base means undetermined. The tip is returned because it is the
    second bound: the ref as it stands now, not where this branch forked from
    it. The earlier version resolved a merge base and dropped the ref, so an
    explicit `--base <sha>` naming a moved tip was silently re-derived back to
    the fork point — probed on PR #107 and found to still pass. Honouring the
    ref means honouring both readings of it.
    """
    candidates = [explicit] if explicit else ["origin/main", "main"]
    tried = []
    for ref in candidates:
        code, tip, _ = _git("rev-parse", "--verify", f"{ref}^{{commit}}")
        tip = tip.strip()
        if code != 0 or not tip:
            tried.append(f"{ref} does not resolve")
            continue
        code, sha, _ = _git("merge-base", "HEAD", ref)
        sha = sha.strip()   # _git returns raw stdout now, for -z path parsing
        if code != 0 or not sha:
            tried.append(f"no merge base between HEAD and {ref}")
            continue
        return sha, tip, ref, f"merge base with {ref} is {sha[:7]}"
    return None, "", "", "; ".join(tried) or "no base ref given"


def _parse_semver(raw: object) -> tuple[int, ...] | None:
    """Three numeric parts, as ints.

    The int cast is the whole comparison. A tuple of strings compares
    lexically, so `"10" < "9"` and the guard inverts on any bump across a
    decade boundary — accepting a decrement and rejecting a rise, both while
    every other check reports green. `0.9.0 -> 0.10.0` was this repository's
    first such bump and no fixture distinguished the two readings (#33); two
    now do.
    """
    if not isinstance(raw, str):
        return None
    parts = raw.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def _manifest_at(ref: str | None) -> tuple[dict | None, str]:
    """The parsed manifest at a ref, or in the working tree when ref is None.

    Split out from the version read because two callers now want different
    parts of the same blob — the version, and every other field — and reading
    it twice per revision would let those two answers disagree about which
    bytes they came from.
    """
    if ref is None:
        path = ROOT / MANIFEST
        if not path.is_file():
            return None, f"{MANIFEST} is absent from the working tree"
        text = path.read_text(encoding="utf-8")
    else:
        code, text, _ = _git("show", f"{ref}:{MANIFEST}")
        if code != 0:
            return None, f"{MANIFEST} is absent at {ref[:7]}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"{MANIFEST} is not valid JSON ({exc.msg})"
    if not isinstance(data, dict):
        return None, f"{MANIFEST} is not a JSON object"
    return data, ""


def _semver_of(data: dict) -> tuple[tuple[int, ...] | None, str]:
    raw = data.get(EXEMPT_FIELD)
    parsed = _parse_semver(raw)
    if parsed is None:
        return None, f"version {raw!r} is not a three-part numeric semver"
    return parsed, ""


def _carried_fields(data: dict) -> dict:
    """Everything the manifest says to a consumer except the version itself."""
    return {k: v for k, v in data.items() if k != EXEMPT_FIELD}


def check(base_ref: str | None = None) -> tuple[int, list[str]]:
    lines: list[str] = []
    base, tip, ref_name, why = _resolve_base(base_ref)
    if base is None:
        return UNDETERMINED, [f"version-bump: cannot determine a base -- {why}"]

    # Two independent mechanisms give the moved-base answer, and either alone
    # suffices: `base` is resolved to a merge base above, AND `...` re-derives
    # one here. Verified by mutation — replacing the merge-base resolution with
    # the ref tip keeps every test green, because `...` rescues it. Redundant on
    # purpose; the withdrawn predecessor had neither and went silent on exactly
    # this state, which every merge into the base produces.
    # Two-dot: base vs the PROJECTED tree (HEAD plus every uncommitted change),
    # not base...HEAD unioned with the tree diffs. Unioning two name-lists cannot
    # represent cancellation — an uncommitted edit reversing a committed one
    # leaves the tree identical to the base while both lists still name the path,
    # so the guard would FAIL a branch that lands no shipped-zone change at all.
    # This is the shape the withdrawn predecessor used, and on this point it was
    # right.
    code, out, err = _git("diff", "--name-only", "--no-renames", "-z", base)
    if code != 0:
        return UNDETERMINED, [
            f"version-bump: could not diff against {base[:7]}"
            + (f" -- {err}" if err else "")
        ]
    changed = _paths(out)

    # Untracked files are the half no diff can see: a whole new skill is
    # invisible until it is added, which is the canonical new-skill case.
    #
    # Folding both in answers "would this be lawful if I committed everything
    # now" — NOT the same question CI answers, and it diverges both ways: a
    # committed edit whose bump is still uncommitted passes here and fails CI,
    # and an untracked scratch file under skills/ fails here and is invisible
    # to CI. The local answer is about the tree you are about to land; CI's is
    # about the commits you did.
    # Untracked files only: the two-dot diff above already carries tracked
    # changes, staged or not.
    for args in (("ls-files", "--others", "--exclude-standard", "-z"),):
        code, out, err = _git(*args)
        if code != 0:
            return UNDETERMINED, [
                "version-bump: could not read the working tree "
                f"({' '.join(args)} failed{': ' + err if err else ''}) -- "
                "refusing to answer from committed history alone"
            ]
        changed.extend(_paths(out))
    touched = sorted({
        f for f in changed
        if any(f.startswith(p) for p in SHIPPED) and f != MANIFEST
    })

    # One read per revision, shared by the field comparison below and the
    # version comparison after it. Two reads could disagree about which bytes
    # they answered from, which is the one thing a guard may not do.
    read: dict[str | None, tuple[dict | None, str]] = {}

    def manifest(rev: str | None) -> tuple[dict | None, str]:
        if rev not in read:
            read[rev] = _manifest_at(rev)
        return read[rev]

    def version(rev: str | None) -> tuple[tuple[int, ...] | None, str]:
        data, err = manifest(rev)
        return (None, err) if data is None else _semver_of(data)

    # The manifest is not exempt as a file, only as a field: an edit that
    # changes `name` or `description` and nothing else is changed consumer copy
    # and counts, while a bump alone still does not. Read only when the manifest
    # is actually in the change set, so the untouched case adds no git calls and
    # keeps the outcome it has today.
    if MANIFEST in changed:
        for rev, label in ((base, "base"), (None, "current")):
            data, err = manifest(rev)
            if data is None:
                return UNDETERMINED, [
                    f"version-bump: {label} manifest unreadable -- {err}"
                ]
        if _carried_fields(read[base][0]) != _carried_fields(read[None][0]):
            touched = sorted([*touched, MANIFEST])

    if not touched:
        return PASS, [f"version-bump: shipped zone untouched ({why})"]

    old, old_err = version(base)
    new, new_err = version(None)
    if old is None:
        return UNDETERMINED, [f"version-bump: base version unreadable -- {old_err}"]
    if new is None:
        return UNDETERMINED, [f"version-bump: current version unreadable -- {new_err}"]
    top, top_err = version(tip)
    if top is None:
        return UNDETERMINED, [
            f"version-bump: base tip version unreadable -- {top_err}"
        ]

    shown = ".".join(map(str, old)), ".".join(map(str, new)), ".".join(map(str, top))
    # The tip is worth saying only when it is not the merge base; when the base
    # has not moved the two bounds are one fact and printing it twice reads as
    # two.
    where = why if tip == base else (
        f"{why}, and {ref_name} has since moved to {tip[:7]} carrying {shown[2]}")
    if new > old and new > top:
        # The names, not just the count. A session that edited only
        # repo-only files still sees a shipped-zone count here -- the unit is
        # the PR against its merge base, not this commit -- and a bare number
        # sends it looking for a mistake it did not make.
        lines.append(
            f"version-bump: {len(touched)} shipped-zone file(s) changed "
            f"({', '.join(sorted(touched))}), "
            f"version {shown[0]} -> {shown[1]} ({where})"
        )
        return PASS, lines
    if new > old:
        # Raised, but onto a number the base ref already published. The merge
        # base cannot see this and neither could this guard until #110: the
        # branch did raise the version it forked from, so the only reading that
        # catches it is the one that asks what the ref carries now.
        lines.append(
            f"version-bump: {len(touched)} shipped-zone file(s) changed and the "
            f"version rose to {shown[1]}, but {ref_name} ALREADY CARRIES "
            f"{shown[2]} at its tip {tip[:7]} -- a consumer cannot tell "
            f"installed from current, and this branch's merge base {base[:7]} "
            f"predates it. The bound is the base ref's tip as well as the merge "
            f"base. Bring {ref_name} into this branch and raise \"version\" in "
            f"{MANIFEST} again (see AGENTS.md, 'The flow'). Note that "
            f"{ref_name} is only as fresh as your last fetch"
        )
        lines.extend(f"    {f}" for f in touched)
        return FAIL, lines
    detail = (f"is unchanged at {shown[1]}" if new == old
              else f"went BACKWARDS, {shown[0]} -> {shown[1]}")
    lines.append(
        f"version-bump: {len(touched)} shipped-zone file(s) changed but "
        f"the plugin version {detail} -- a consumer cannot tell installed from "
        f"current. The unit is this pull request against its merge base, never "
        f"per-commit, so a branch already carrying a bump needs no second one. "
        f"Raise \"version\" in {MANIFEST} (see AGENTS.md, 'The flow')"
    )
    lines.extend(f"    {f}" for f in touched)
    return FAIL, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(
        description=
        "Refuse a pull request whose shipped-zone files changed without a plugin version bump. The version must exceed both the base ref's merge base and its tip, so a bump onto a version the base ref already carries is refused. Three outcomes: PASS, FAIL, and UNDETERMINED when the base cannot be resolved -- UNDETERMINED is a failure, not a pass.",
        # The outcome table is the point of --help; the default formatter
        # collapses it into one run-on line.
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base", default=None, help="base ref (default: origin/main, then main)")
    args = parser.parse_args(argv)
    status, lines = check(args.base)
    for line in lines:
        print(line)
    if status == UNDETERMINED:
        print("version-bump: UNDETERMINED is a failure, not a pass -- the "
              "unit is this pull request against its merge base; see "
              "AGENTS.md, 'The flow'")
    return status


if __name__ == "__main__":
    sys.exit(main())

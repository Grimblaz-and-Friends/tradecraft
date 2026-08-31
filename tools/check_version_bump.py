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
button. Issue #110 records six instances; four are that shape and this bound
closes them at the moment the version is picked. The other two (#113, #155) are
concurrent open pull requests off a base that has not moved, where no bound
reading only HEAD and the base ref can see the collision -- this bound reaches
them only once the sibling lands, which is still earlier than the merge button
where their record says the cost was paid. The tip is what makes the answer
about the version rather than about this branch's history.

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
#
# It names two things on purpose, and they must stay the same key: the field
# the carried-fields comparison excludes, and the field the semver is read
# from. Splitting them into two constants would create two values obliged to
# remain equal, which is the worse failure.
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

    `isdecimal`, not `isdigit`: the two disagree on characters like the
    superscript two, which `isdigit` accepts and `int()` then refuses, so the
    gate admitted a value the cast could not take and the guard died with a
    traceback whose exit code 1 reads as FAIL -- the wrong one of three
    outcomes.

    And `isascii` beside it, because matching the cast is not enough: `int()`
    accepts an Arabic-Indic digit that no consumer reading a version string
    can, and the guard PASSed such a bump while printing it as the ASCII
    version it is not -- `shown` is rebuilt from the parsed ints, so the report
    named a version the manifest did not contain. A false pass is the one
    outcome this guard exists to refuse, and this was the only one anywhere in
    its review.
    """
    if not isinstance(raw, str):
        return None
    parts = raw.split(".")
    if len(parts) != 3 or not all(p.isascii() and p.isdecimal() for p in parts):
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
        # A manifest that is not UTF-8, or that cannot be read at all, is a
        # question this guard cannot answer -- which its own doctrine says to
        # state out loud and exit non-zero. Uncaught, both escaped as a
        # traceback whose exit code 1 reads as FAIL. Found independently by
        # two external reviewers and by this review's own `operational` seat,
        # the third at the neighbouring site in `_parse_semver`.
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return None, f"{MANIFEST} is not valid UTF-8"
        except OSError as exc:
            return None, f"{MANIFEST} could not be read ({exc.strerror})"
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


def _is_remote_tracking(ref: str) -> bool:
    """Does this ref go stale from not fetching?

    Only a remote-tracking ref does. A local branch has no fetch relationship
    and a raw sha cannot move, so the freshness note is a no-op on the first
    and false on the second -- and both reached it verbatim, which trains a
    reader to discount the clause on the one path where it is load-bearing.

    Resolved to a full ref name rather than concatenated onto `refs/remotes/`.
    The first attempt did the latter, so `refs/remotes/origin/main` -- a lawful
    spelling of the same ref, and the spelling `skills/persist-changes` uses
    for its own refs -- became `refs/remotes/refs/remotes/origin/main`, never
    resolved, and silently lost the disclosure on exactly the stale-read path
    the disclosure exists for. A clause that vanishes where it is load-bearing
    is the same defect as one that fires where it is not.
    """
    code, full, _ = _git("rev-parse", "--symbolic-full-name", ref)
    return code == 0 and full.strip().startswith("refs/remotes/")


def _shown_ref(ref: str) -> str:
    """A ref as a reader should see it: a sha abbreviated, a name left alone."""
    return ref[:7] if len(ref) == 40 and all(
        c in "0123456789abcdef" for c in ref) else ref


def check(base_ref: str | None = None) -> tuple[int, list[str]]:
    lines: list[str] = []
    base, tip, ref_name, why = _resolve_base(base_ref)
    if base is None:
        return UNDETERMINED, [f"version-bump: cannot determine a base -- {why}"]

    # One mechanism gives the moved-base answer, not two: `base` is resolved to
    # a merge base above, and the diff below is two-dot against it. An earlier
    # comment here claimed `...` re-derived a merge base as a redundant second
    # mechanism; no `...` has ever appeared in this function, and the paragraph
    # four lines down says so explicitly, so the block contradicted itself and
    # credited the guard with a redundancy it does not have. Inherited from
    # before this change and removed here rather than carried forward.
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
    if MANIFEST in changed and (base_manifest := manifest(base)[0]) is not None:
        # Gated on the base side being readable, and that gate is the whole of
        # what the owner affirmed. The disclosed widening of exit 2 was "a
        # broken manifest as the only change" -- the CURRENT side. An
        # unreadable BASE is a different case, most often a manifest that is
        # simply new, and nothing to compare against is not a question the
        # guard failed to answer.
        #
        # **This gate reaches only the manifest-alone case**, which is what it
        # was ruled to restore. A pull request adding the manifest ALONGSIDE
        # other shipped files -- the shape an adoption actually takes -- makes
        # `touched` non-empty and still exits 2 from the base version read
        # below, with a trailer naming an act nobody can perform. That is
        # inherited rather than introduced (it exits 2 before this change too)
        # and is recorded, not fixed: the remedy decides what "did the version
        # rise" means with nothing on one side, which is a design call.
        data, err = manifest(None)
        if data is None:
            return UNDETERMINED, [
                f"version-bump: current manifest unreadable -- {err}. "
                f"Fix {MANIFEST} so it parses, then re-run"
            ]
        if _carried_fields(base_manifest) != _carried_fields(data):
            touched = sorted([*touched, MANIFEST])

    if not touched:
        note = ("no shipped-zone change to version"
                if MANIFEST in changed else "shipped zone untouched")
        return PASS, [f"version-bump: {note} ({why})"]

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
    seen = _shown_ref(ref_name)
    stale_note = (
        f". Read at {seen} {tip[:7]}, which is only as fresh as your last fetch"
        if _is_remote_tracking(ref_name) else "")
    # Every PASS that consulted the second bound says which revision it
    # consulted, and a remote-tracking one says its answer is only as fresh as
    # the fetch behind it. The disclosure used to live on the FAIL path alone,
    # which is the path where the ref was NOT stale: an unfetched clone gets
    # `tip == base`, the moved-tip clause is suppressed, and the PASS over a
    # live collision reads exactly like a clean one. A session cannot fetch on
    # a warning it never sees.
    where = (f"{why}, and {seen} is at {tip[:7]} carrying {shown[2]}"
             if tip != base else
             f"{why}, which is also {seen}'s tip")
    if new > old and new > top:
        # The names, not just the count. A session that edited only
        # repo-only files still sees a shipped-zone count here -- the unit is
        # the PR against its merge base, not this commit -- and a bare number
        # sends it looking for a mistake it did not make.
        lines.append(
            f"version-bump: {len(touched)} shipped-zone file(s) changed "
            f"({', '.join(sorted(touched))}), "
            f"version {shown[0]} -> {shown[1]} ({where}{stale_note})"
        )
        return PASS, lines
    if new > old:
        # Raised, but not past what the base ref now publishes. The merge base
        # cannot see this and neither could this guard until #110: the branch
        # did raise the version it forked from, so the only reading that
        # catches it is the one that asks what the ref carries now.
        #
        # Two arithmetic cases reach here, and they are different faults. Equal
        # is a collision, where a consumer genuinely cannot tell installed from
        # current. BELOW is not a collision at all -- nobody carries this
        # number -- and saying so of a version 0.22.0 beside a tip at 0.23.0
        # hands a reader who checks a claim they can falsify in one look.
        collision = (
            f"{seen} ALREADY CARRIES {shown[2]} at its tip {tip[:7]}, so a "
            f"consumer could not tell installed from current"
            if new == top else
            f"{seen} is already past it at {shown[2]} (tip {tip[:7]}), so this "
            f"version would land behind the base"
        )
        lines.append(
            f"version-bump: {len(touched)} shipped-zone file(s) changed and the "
            f"version rose to {shown[1]}, but {collision} -- and this branch's "
            f"merge base {base[:7]} predates that tip. The bound is the base "
            f"ref's tip as well as the merge base. Bring {seen} into this "
            f"branch and raise \"version\" in {MANIFEST} again (see AGENTS.md, "
            f"'The flow'){stale_note}"
        )
        lines.extend(f"    {f}" for f in touched)
        return FAIL, lines
    detail = (f"is unchanged at {shown[1]}" if new == old
              else f"went BACKWARDS, {shown[0]} -> {shown[1]}")
    # The unit sentence is true only while the merge base has not moved. Where
    # it has, the base has published a version this branch has not risen above
    # -- and that is the state this guard's own collision remedy ("bring the
    # base in, raise again") walks a session through, as well as the state CI
    # evaluates on a merge ref. Printed unconditionally, the justification
    # contradicted the imperative beside it.
    #
    # **The target is always a bound to clear, never a number already in the
    # file.** The first attempt at this sentence named `shown[1]` here, which
    # is the version the same line has just reported as wrong: the guard's
    # most-printed message told a session to raise the version to the version
    # it already had, and to "raise" a decrement to the decremented value. An
    # act that changes nothing is worse than no act named, because a consumer
    # performs it -- both experience sessions established that they do -- and
    # comes back to the identical red.
    if tip == base:
        unit = (
            "The unit is this pull request against its merge base, never "
            "per-commit, so a branch already carrying a bump needs no second "
            "one. "
        )
        target = f"past {shown[0]}"
    else:
        # NOT "a bump this branch already made has been absorbed": reaching
        # here means the version did not rise above the merge base at all, so
        # the commonest branch in this state never bumped, and telling it
        # otherwise sends it hunting through its own history. That clause was
        # the same defect this block was rewritten to remove, reintroduced in
        # the sibling arm.
        unit = (
            f"The merge base has moved: {seen} is at {tip[:7]} carrying "
            f"{shown[2]}, which this branch has not risen above. "
        )
        target = f"past {shown[2]}"
    # The manifest is not accused of being its own justification. It is here
    # because a field other than the version changed, and nothing else in the
    # output says the exemption is a field rather than the file.
    why_manifest = (
        f" {MANIFEST} counts because a field other than \"{EXEMPT_FIELD}\" "
        f"changed in it; raising the version alone never counts."
        if MANIFEST in touched else "")
    lines.append(
        f"version-bump: {len(touched)} shipped-zone file(s) changed but "
        f"the plugin version {detail} -- a consumer cannot tell installed from "
        f"current. {unit}Raise \"version\" in {MANIFEST} to {target} (see "
        f"AGENTS.md, 'The flow').{why_manifest}"
    )
    lines.extend(f"    {f}" for f in touched)
    return FAIL, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(
        description=
        "Refuse a pull request whose shipped-zone files changed without a plugin version bump. The version must exceed the version at BOTH the base ref's merge base and the base ref's tip, so a bump onto a version the base ref already carries is refused.",
        # The three outcomes are what a caller needs from --help and the
        # description is prose, so the default formatter is right: it wraps to
        # the terminal, which the raw formatter does not. An earlier comment
        # here justified the raw formatter by an outcome table that has never
        # been passed to argparse -- so the formatter produced exactly the
        # run-on line the comment said it avoided, and the tail of the
        # description ran off the right edge.
        epilog=
        "Exit 0 PASS: the shipped zone is untouched, or it changed and the "
        "version rose past both bounds. "
        "Exit 1 FAIL: the shipped zone changed and the version did not rise "
        "past both bounds. "
        "Exit 2 UNDETERMINED: the question could not be answered -- the base "
        "ref would not resolve, git would not answer, or a manifest the guard "
        "had to read did not parse. UNDETERMINED is a failure, not a pass. "
        "The base ref is only as fresh as your last fetch.",
    )
    parser.add_argument("--base", default=None, help="base ref (default: origin/main, then main)")
    args = parser.parse_args(argv)
    status, lines = check(args.base)
    for line in lines:
        print(line)
    if status == UNDETERMINED:
        # Names an act. The old trailer cited AGENTS.md's "The flow", which
        # says nothing about undetermined answers, base resolution or the
        # second bound -- so a session that followed the citation to find out
        # what to do found no corroboration and had to guess.
        print("version-bump: UNDETERMINED is a failure, not a pass -- the "
              "guard could not establish the answer and will not guess. Fix "
              "what the line above names (fetch or name a base ref that "
              "resolves, or repair the manifest it could not read), then "
              "re-run; do not commit on an undetermined answer")
    return status


if __name__ == "__main__":
    sys.exit(main())

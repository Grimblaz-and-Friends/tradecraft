#!/usr/bin/env python3
"""The project roster: make this repository's own cell descriptions load (issue #199).

A cell's `description` is the whole of its triggering surface and is always
loaded -- for an adopter, who installs the plugin. Not here. This repository
never installs itself, so no session working in it held any cell's name or
description, and every trigger deliberately routed to a description over the
last several changes reached every consumer and missed us. Three of four cold
consumers on PR #194 never reached a rule whose trigger lives in one, and two
of them wrote a rule violation into a commit message and a PR body as a direct
result.

Claude Code loads a project's own skills from `.claude/skills/<name>/SKILL.md`
with no install, no settings edit, and no command run. So that is where this
writes: one entry per cell, carrying the cell's frontmatter byte for byte --
which is the part that must load -- over a body that names this generator and
points at the cell itself. The prose keeps one owner; only the triggering
surface is reproduced, and a guard holds the two in step.

**The entry is a pointer, not a copy.** A session that invokes a cell by name
here reaches the pointer and reads the cell, one hop -- exercised by cold
sessions that invoked a cell from its entry, followed the pointer, and applied
the cell. Copying whole bodies would put **78,931 characters** of prose into a
second place, and every cell edit into two diffs, to save that hop -- the sum
over every cell at `8a0c71e` of the file's decoded characters less the block
`frontmatter()` returns.

**Written as bytes, compared as text.** The write half is the substrate cell's
third text-mode rule: a text-mode write would turn every line feed into a
carriage return pair on Windows and not on Linux, so the same tree would hold
different bytes depending on where this last ran. That half is unchanged and
guarded by a test of its own.

The read half cannot be the same, because **the line endings these files carry
on disk are not this repository's to set.** `.gitattributes` pins the checkout
to LF, and git honours it -- but not every file in a worktree arrives through
git. A Claude Code **session** worktree comes up with ten files written in text
mode by the harness: these nine entries and `CLAUDE.md`. The other 108 tracked
files are checked out LF in the same second, `.gitattributes` among them, which
is how the two writers were told apart.

**Which worktrees, precisely, because the wide version is worse than useless.**
Session worktrees do this; `agent-*` subagent worktrees do not, and they are
Claude Code worktrees too. An earlier version of this paragraph said *every*
Claude Code worktree, and all five seats of this change's own review -- every
one of them running in an `agent-*` tree -- checked, found LF, and reported the
cause recorded here as false.

**`CLAUDE.md` is the cheap check, and the only durable one.** Nothing in this
repository ever rewrites it, where `--write` erases the evidence under
`.claude/skills/` the moment anyone clears the red; so its line endings are a
fossil of how a worktree was made. Across the owner's machine: 14 of 15 session
trees CRLF, 0 of 16 `agent-*` trees, source checkout LF.

    python -c "print(open('CLAUDE.md','rb').read())"

So a session starting work in such a worktree met a finding per cell before
touching anything, could not tell that red from one it had caused, and could
not clear it durably: `--write` rewrote the entries LF, git recorded nothing
because the index already held LF, and the next worktree started red again
(#224). `matches()` below is where that is answered, and it says why the
comparison may not be tightened back.

Usage:  python tools/roster.py [--write]

    0  the roster matches the cells -- with --write, it did and now does
    1  a finding remains. `--write` re-verifies after writing and reports
       what it could not repair, so its exit code answers whether the tree
       is lawful rather than whether the loop ran: a cell whose frontmatter
       will not parse, or a file at a cell's name that this script did not
       write, both survive a --write and both keep the exit at 1.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Shared with the shipped zone, which is the lawful direction: repo-only
# code may import shipped code. Resolved from this file rather than the
# working directory, so the script runs from any cwd.
sys.path.insert(0, str(ROOT / "lib"))
from winio import utf8_stdio  # noqa: E402

CELLS = "skills"
ROSTER = ".claude/skills"
CELL_FILE = "SKILL.md"

# What marks a file as this generator's to remove. `.claude/skills/<name>/` is
# the runtime's documented home for a project's own skills -- the very property
# this script depends on -- so the directory is shared, not owned. Without this
# marker the orphan branch's stated remedy unlinked whatever it found there: a
# hand-written project skill, untracked, with no prompt and exit 0, and the lint
# then green over the remains. Found at high in PR #210's review by three seats
# independently, all three having run the deletion.
MARKER = b"Generated by `tools/roster.py`"

# The frontmatter terminator, as `lint._frontmatter_fields` finds it. Bytes
# here rather than characters because the whole file is handled as bytes.
_OPEN = b"---"
_CLOSE = b"\n---"


def _body(name: str) -> bytes:
    """What sits under the copied frontmatter.

    Everything a session opening this file needs in order not to edit it: that
    it is generated, what generates it, and where the cell actually is. That is
    the whole of criterion 6 -- a reader learns it from this file alone, with
    nothing else loaded.
    """
    return (
        f"\n# {name}\n"
        f"\nGenerated by `tools/roster.py` from `{CELLS}/{name}/{CELL_FILE}`, which is"
        f" the `{name}` cell and carries all of it. Read that file now.\n"
        f"\nDo not edit this one: it is the cell's frontmatter copied so that its"
        f" description loads in every Claude Code session working in this"
        f" repository, and `check_project_roster` fails the lint when the two"
        f" fall out of step.\n"
    ).encode("utf-8")


def frontmatter(data: bytes) -> bytes | None:
    """The leading frontmatter block, its terminator, and the one byte after it.

    That byte is the trailing newline **on an LF source**, which is what
    `.gitattributes` pins every file in this repository to. It is not a
    property of the function: on a CRLF source the block ends at the bare
    `\\r`, and on a file ending at its terminator there is no byte to take.
    The bound is stated here because this is where a reader would look for it
    before reusing the function on a source that pin does not cover. [PR #210
    review, M19]

    None when there is no frontmatter to copy. The caller reports that as a finding
    rather than writing an entry with no description: an entry whose
    frontmatter will not parse loads with empty metadata -- no name, no
    trigger, silently -- which is the failure `check_cell_frontmatter` exists
    to catch, and reproducing it here would be this script manufacturing it.
    """
    if not data.startswith(_OPEN):
        return None
    end = data.find(_CLOSE, len(_OPEN))
    if end == -1:
        return None
    return data[:end + len(_CLOSE) + 1]


def cell_names(root: Path) -> list[str]:
    """Every cell a runtime would load from the shipped zone, sorted."""
    directory = root / CELLS
    if not directory.is_dir():
        return []
    return sorted(
        path.name for path in directory.iterdir()
        if (path / CELL_FILE).is_file()
    )


def roster_names(root: Path) -> list[str]:
    """Every entry the roster currently holds, sorted."""
    directory = root / ROSTER
    if not directory.is_dir():
        return []
    return sorted(
        path.name for path in directory.iterdir()
        if (path / CELL_FILE).is_file()
    )


def expected(root: Path, name: str) -> bytes:
    """The bytes this cell's roster entry must hold.

    One definition, two callers -- the writer and the guard. They were never
    two, and this is why: a guard computing its own expectation is a second
    definition, and the two drift the moment either is edited. `_always_on` in
    `tools/figures.py` carries the same lesson from the same repository.
    """
    source = root / CELLS / name / CELL_FILE
    data = source.read_bytes()
    block = frontmatter(data)
    if block is None:
        raise ValueError(
            f"{CELLS}/{name}/{CELL_FILE} has no parseable frontmatter to copy"
        )
    return block + _body(name)


def matches(entry: bytes, want: bytes) -> bool:
    """Whether an entry on disk is the one `expected()` describes.

    **Text identity, not byte identity, and the difference is exactly the line
    endings.** Everything else is compared as it always was: a changed
    description, a reordered field, a stray character, a truncated block all
    still differ here.

    The warrant is that a newline difference at this site is **normally
    invisible to the repository and cannot be repaired in the tree it appears
    in.** `.gitattributes` normalises the entry to LF on the way into the
    index; and the CRLF is written by a copy no command here performs, so
    re-running the writer clears the working tree for as long as that tree
    lives and the next one starts over. Reporting it was therefore a finding
    with no lawful response, on a tree nobody had touched. [#224]

    **"Normally" is doing work, and the bound is real.** Git's `text=auto`
    refuses to normalise **any file holding a lone carriage return** -- one
    bare `\\r` anywhere disables the conversion for that whole file, and every
    CRLF in it is committed verbatim. An entry in that composition is forgiven
    here and recorded by git, where the byte comparison this replaced fired
    and `--write` repaired it. Found the hard way: this change's own first
    draft put two control bytes into its decision-log row, the only CR-bearing
    blob in the repository, past a lint that has no carriage-return check. The
    guard for that class is filed, not built here.

    **Both sides are normalised, not only the entry.** `want` is built from a
    cell git checks out LF, so today only the entry side arrives CRLF from the
    harness copy -- a cell can still reach that state through a Windows
    text-mode write, which `AGENTS.md` calls normal. Normalising one side
    would make an unclearable red possible the moment a cell arrived CRLF too,
    where the symmetric form stays self-consistent whatever either side
    carries. The cost of the symmetry is nothing; the cost of the asymmetry is
    a red that `--write` cannot clear.

    **`\\r\\n` only, never a lone `\\r`.** That pair is what a Windows
    text-mode write produces and what was observed; a bare carriage return is
    not a line ending anything here emits, and treating it as one would
    silently accept a corrupted entry. It takes **two** fixtures to pin, and
    the tests carry both: a stray `\\r` inside an otherwise-CRLF entry kills
    "strip every carriage return", an all-CR entry kills "treat a lone `\\r` as
    a line ending", and either alone leaves the other mutant alive.

    **This is the only site that compares one of these files**, which is the
    whole of the exposure #224 asked about. Two call sites read one at all:
    this one, and the local `read` inside `figure_always_on` in
    `tools/figures.py`, which decodes with universal newlines and counts
    characters. Re-derive that rather than trusting it -- run `python
    tools/lint.py` on whatever tree you are on, under an intercept wrapping
    every route to opening a file, bucketing each hit by whether the resolved
    path is under `.claude/skills/`, and printing the frame and the path. D-231
    carries the command and why it is recorded instead of its answer: two
    drafts of this paragraph named readers that turned out to read **cells**
    under `skills/`, because a census that prints only a count cannot tell the
    two apart.

    `_normalized_chars` in `skills/authoring/scripts/figures.py` reaches for
    the same move for the same stated reason and is worth reading for it. It
    is live code on a path this repository runs constantly -- it does not
    reach a roster **entry**, which is the only claim made about it here.
    """
    return entry.replace(b"\r\n", b"\n") == want.replace(b"\r\n", b"\n")


def inside_roster(root: Path, entry: Path) -> bool:
    """Whether an entry's real location is still under the roster directory.

    `write()` creates directories and files, so a link in the middle of the
    path sends both outside the repository: with `.claude/skills/alpha` linked
    elsewhere, `mkdir(parents=True)` and `write_bytes` follow it and the file
    lands at the link's target. Reproduced.

    **Resolved-path containment rather than `is_symlink()`**, because on
    Windows the reachable form is a *junction* -- `mklink /J` needs no
    privilege, where `mklink /D` is refused without it -- and
    `Path.is_symlink()` returns False for one. A guard reading the obvious
    predicate would pass exactly the case that is easiest to create. Raised by
    the external reviewer against `is_symlink`; the containment check is the
    part that survives contact with this platform.

    Scoped to the roster side. A link under `skills/` is not checked here: this
    script only ever reads a cell, and reading through one escapes nothing.
    """
    base = (root / ROSTER).resolve()
    try:
        return entry.resolve().is_relative_to(base)
    except (OSError, ValueError):
        return False


def is_generated(path: Path) -> bool:
    """Whether this file is one `write()` produced, and so one it may remove.

    Read from the file rather than inferred from its location, because the
    location is shared with whatever project skills a session writes by hand.
    An unreadable file is not this generator's: refusing is the safe answer
    when the question cannot be settled.
    """
    try:
        return MARKER in path.read_bytes()
    except OSError:
        return False


def verify(root: Path) -> list[str]:
    """Findings, by shape rather than by count.

    **What the roster owns is exactly two things: a name that is a cell, and a
    file carrying `MARKER`.** Everything else under `.claude/skills/` belongs
    to whoever put it there. Ownership is checked on **every path that touches
    a file**, not only on removal -- checking it on one path is what let the
    regeneration branch go on destroying hand-written content after the
    removal branch stopped. [PR #210 cycle one, C1-F2/C1-F3]

    Each shape below says what its own message names, and they are named
    rather than counted: a stated count of these has been wrong three times
    running, each time in the sentence written to correct the one before, so
    the arithmetic is gone rather than corrected a fourth time. [PR #210 cycle
    one, C1-F5; cycle two, C2-F1]

    - **outside the roster** -- an entry directory whose real location
      resolves out of `.claude/skills/`, so writing there would land outside
      this repository. Names no command: only a person can remove the link.
    - **missing** -- a cell with no entry. Names `--write`.
    - **out of step** -- a cell whose entry this script wrote and the cell has
      since moved on. Names `--write`. Judged by `matches()`, so an entry
      differing from its cell in line endings alone is not this shape and not
      any other: no command clears that difference durably, so reporting it
      named a fix that did not fix. **A CRLF *cell* is a different matter** --
      `expected()` slices it by raw bytes before `matches()` ever sees it, so
      the block it copies loses a newline and this shape fires truthfully on a
      document that really does differ. See `frontmatter()` for the bound.
    - **orphan** -- an entry this script wrote whose cell is gone. Names
      `--write`.
    - **collision** -- a cell's name taken by a file this script did not
      write. Names the move first and `--write` second, because both are
      needed and only a person can do the first. Reported rather than
      overwritten, and reported rather than ignored: the hand-written
      frontmatter is what loads, so the cell's real description does not,
      which is a silent criterion-1 failure.
    - **unparseable frontmatter** -- a cell `--write` cannot copy. Names no
      command; the cell's frontmatter is what has to change. The same branch
      catches a cell that cannot be **read** at all -- a permission failure, a
      broken link on the `skills/` side -- and carries the OS error with it,
      so read the error before taking the frontmatter advice.
    - **no cell at all** -- nothing under `skills/` to compare against. Names
      no command, for the reason #198 gives about a sibling guard: no cell
      found is indistinguishable from every cell lawful.

    The three that name `--write` alone do so because for them the fix is
    always that command, and a guard reporting a diff without it makes the
    reader derive what the script already knows.

    And one condition that is not a finding at all: **a foreign entry at a
    name that is not a cell**, which is a project skill somebody wrote in the
    runtime's documented place for one. Policing it produced a red the lint
    could never clear on a lawful tree. A directory there holding no
    `SKILL.md` is likewise silent; `write()` reports residue at the moment it
    creates it, which is where that report is useful.
    """
    findings = []
    cells = cell_names(root)
    for name in cells:
        target = root / ROSTER / name / CELL_FILE
        if not inside_roster(root, target.parent):
            findings.append(
                f"roster: {ROSTER}/{name}/ resolves outside {ROSTER}/, so "
                f"writing there would land outside this repository -- no "
                f"command repairs this; remove the link"
            )
            continue
        try:
            want = expected(root, name)
        except (ValueError, OSError) as exc:
            findings.append(
                f"roster: {name}: {exc} -- no command repairs this; fix the "
                f"cell's frontmatter"
            )
            continue
        if not target.is_file():
            findings.append(
                f"roster: {ROSTER}/{name}/{CELL_FILE} is missing, so the "
                f"`{name}` cell's description loads in no session here -- "
                f"run `python tools/roster.py --write`"
            )
            continue
        if matches(target.read_bytes(), want):
            continue
        if is_generated(target):
            findings.append(
                f"roster: {ROSTER}/{name}/{CELL_FILE} is out of step with "
                f"{CELLS}/{name}/{CELL_FILE} -- run "
                f"`python tools/roster.py --write`"
            )
        else:
            findings.append(
                f"roster: {ROSTER}/{name}/{CELL_FILE} was not written by "
                f"tools/roster.py and holds the name of the `{name}` cell, so "
                f"that cell's description loads in no session here and nothing "
                f"will overwrite yours -- move your file out of {ROSTER}/, "
                f"then run `python tools/roster.py --write`"
            )
    for name in roster_names(root):
        if name in cells:
            continue
        if is_generated(root / ROSTER / name / CELL_FILE):
            findings.append(
                f"roster: {ROSTER}/{name}/{CELL_FILE} names no cell under "
                f"{CELLS}/ -- run `python tools/roster.py --write`"
            )
    if not cells:
        findings.append(
            f"roster: no cell found under {CELLS}/, so nothing was compared "
            f"-- an empty roster is not a clean one; no command repairs this"
        )
    return findings


def write(root: Path) -> list[str]:
    """Regenerate the roster; return what happened, in the order it happened.

    Orphans this generator wrote are removed rather than left: an entry naming
    a cell that no longer exists puts a retired trigger in every session's
    context, which is worse than the missing entry this script exists to
    prevent. **An orphan it did not write is left exactly where it is** -- see
    `MARKER`.

    **A cell it cannot read is reported, never raised.** This used to let the
    exception out: entries sorting before the bad cell were already on disk,
    entries after it were untouched, and the removal loop below never ran at
    all -- so the one command every finding named handed back a raw traceback
    and a tree in neither the before nor the after state. Reporting keeps the
    remaining work going and leaves the reader the finding `verify()` would
    have given them. [PR #210 review, M4]
    """
    changed = []
    cells = cell_names(root)
    for name in cells:
        try:
            want = expected(root, name)
        except (ValueError, OSError) as exc:
            changed.append(f"skipped {CELLS}/{name}/{CELL_FILE}: {exc}")
            continue
        target = root / ROSTER / name / CELL_FILE
        if not inside_roster(root, target.parent):
            changed.append(
                f"left {ROSTER}/{name}/: resolves outside {ROSTER}/"
            )
            continue
        if target.is_file():
            if matches(target.read_bytes(), want):
                continue
            # Ownership is checked here too, not only on removal. This branch
            # went on overwriting whatever sat at a cell's name after the
            # removal branch stopped deleting orphans -- the same irreversible
            # loss of untracked, hand-written content, reported as `wrote` and
            # exiting 0. [PR #210 cycle one, C1-F2]
            if not is_generated(target):
                changed.append(
                    f"left {ROSTER}/{name}/{CELL_FILE}: not written by this "
                    f"script, and it holds the `{name}` cell's name"
                )
                continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(want)
        changed.append(f"wrote {ROSTER}/{name}/{CELL_FILE}")
    for name in roster_names(root):
        if name in cells:
            continue
        entry = root / ROSTER / name
        if not is_generated(entry / CELL_FILE):
            changed.append(
                f"left {ROSTER}/{name}/{CELL_FILE}: not written by this script"
            )
            continue
        (entry / CELL_FILE).unlink()
        changed.append(f"removed {ROSTER}/{name}/{CELL_FILE}")
        residue = sorted(p.name for p in entry.iterdir())
        if residue:
            changed.append(
                f"left {ROSTER}/{name}/ holding {', '.join(residue)}"
            )
        else:
            entry.rmdir()
    return changed


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(
        prog="roster.py",
        description="Generate or verify the project roster under .claude/skills, which is what makes this repository's own cell descriptions load.",
    )
    parser.add_argument(
        "--write", action="store_true",
        help="regenerate the roster, then verify it and report what remains",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.write:
        for line in write(ROOT):
            print(f"roster: {line}")
        # Verified after writing rather than trusted: `--write` is what every
        # repairable finding names, so it answers whether the tree is lawful
        # now, not whether the loop ran. A cell it could not read leaves work
        # behind, and exiting 0 there is how a session learns the command
        # worked when it did not.
        remaining = verify(ROOT)
        for finding in remaining:
            print(finding)
        print(f"roster: {len(remaining)} finding(s) remaining")
        return 1 if remaining else 0
    findings = verify(ROOT)
    for finding in findings:
        print(finding)
    print(f"roster: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

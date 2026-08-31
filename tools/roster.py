#!/usr/bin/env python3
"""The project roster: make this repository's own cell descriptions load (issues #199, #258).

A cell's `description` is the whole of its triggering surface and is always
loaded -- for an adopter, who installs the plugin. Not here. This repository
never installs itself, so no session working in it held any cell's name or
description, and every trigger deliberately routed to a description over the
last several changes reached every consumer and missed us. Three of four cold
consumers on PR #194 never reached a rule whose trigger lives in one, and two
of them wrote a rule violation into a commit message and a PR body as a direct
result.

Each runtime loads a project's own skills from exactly one directory, with no
install, no settings edit, and no command run: Claude Code from
`.claude/skills/<name>/SKILL.md`, Codex from `.agents/skills/<name>/SKILL.md`.
So those are where this writes: one entry per cell per surface, carrying the
cell's frontmatter byte for byte -- which is the part that must load -- over a
body that names this generator, names the runtime that copy exists for, and
points at the cell itself. The prose keeps one owner; only the triggering
surface is reproduced, and a guard holds them all in step.

**Neither directory reaches the other runtime**, which is why there are two
rather than one shared with a link. Probed in both directions on a tree
holding both: a Codex session returned the `.agents/skills` entry and not the
`.claude/skills` one; a Claude Code session returned the second and reported
the first as not available to it. Fixing one runtime and reasoning about the
other is exactly how #199's remedy left Codex out for as long as it did. [#258]

**The entry is a pointer, not a copy.** A session that invokes a cell by name
here reaches the pointer and reads the cell, one hop -- exercised by cold
sessions that invoked a cell from its entry, followed the pointer, and applied
the cell. Copying whole bodies would put **78,931 characters** of prose into
*each* further place, and every cell edit into as many diffs as there are
surfaces plus one, to save that hop -- the sum over every cell at `8a0c71e` of
the file's decoded characters less the block `frontmatter()` returns. **The sum
is pinned at that commit; the multiplier is not, and moves with `SURFACES`** --
with the surfaces this file writes today, 157,862 characters and three diffs.
The sentence said "a second place" and "two diffs" for as long as there were
two surfaces, understating the argument it exists to make by half. [PR #278
review, M10]

**Written as bytes**, per the substrate cell's third text-mode rule: a
text-mode write would turn every line feed into a carriage return pair on
Windows and not on Linux, so the same tree would hold different bytes
depending on where this last ran. The copied frontmatter carries the cell's
own line endings by construction; `.gitattributes` pins those to LF on every
platform, so what this writes is the same everywhere.

**Read as bytes and compared line endings aside**, which is a separate
question with a separate answer -- see `in_step`. The write is what keeps the
tree canonical; the comparison has to survive a working copy some other tool
rewrote, and reading that rewrite as drift is what took the lint red in a
worktree nobody had touched. [#229]

Usage:  python tools/roster.py [--write]

    0  every surface matches the cells -- with --write, it did and now does
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
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent

# Shared with the shipped zone, which is the lawful direction: repo-only
# code may import shipped code. Resolved from this file rather than the
# working directory, so the script runs from any cwd.
sys.path.insert(0, str(ROOT / "lib"))
from winio import utf8_stdio  # noqa: E402

CELLS = "skills"
CELL_FILE = "SKILL.md"


class Surface(NamedTuple):
    """One directory a session working in this repository loads descriptions from.

    **A surface is a runtime, not a preference.** Each runtime documents one
    place it discovers a project's own skills and reads no other, which two
    probes established rather than assumed: a Codex session in a tree holding
    both directories returned the entry under `.agents/skills` and not the one
    under `.claude/skills`; a Claude Code session in the same tree returned the
    second and answered that the first was not available to it. So neither
    directory can serve both, and the split is symmetric. [#258]

    `runtime` is written into the entry itself, where a session opening one
    file learns which runtime that file exists for. Naming it beats a
    universal for the reason [PR #210 review, M10] gives: the sentence that
    claimed every session was reached asserted a fix Codex had not received.

    **`doctrine` is the always-on prose that runtime loads, and this generator
    never reads it.** It is here because a `Surface` is the whole of what one
    runtime loads in this repository, and the alternative was a second table
    somewhere else keyed by a runtime's name -- two definitions of one fact,
    which drift the moment either is edited. `tools/figures.py` is its
    consumer. The two runtimes differ: both read `AGENTS.md`, and only Claude
    Code reads `CLAUDE.md`, which is a pointer to it -- the doctrine says so
    itself, and a figure that charged every runtime for both reported the two
    as loading the same amount when they do not. Raised by the external
    reviewer on PR #278 and found by no seat.
    """

    directory: str
    runtime: str
    doctrine: tuple[str, ...]


# In the order a reader meets them: the one #199 bought, then the one #258
# bought. Everything below loops over this, so a third runtime is one row of
# code -- and a number of prose sites name the pair by hand and would each need
# editing. **They are not counted here**, because a count of them was stated
# once and was wrong by at least four in the same commit that stated it, in a
# file whose own `verify()` records that a stated count of its shapes has been
# wrong twice running. **No command finds them either** -- the first attempt
# named a line-based `grep` for the two runtime names, and three of the sites
# carry neither name: check 17's registry line names only the two directories,
# and `tools/figures.py`'s comment and its emitted `basis` string say "both
# read AGENTS.md and only Claude Code reads CLAUDE.md". At the time of writing
# they include this file's module docstring,
# `Surface`'s docstring, `main()`'s argparse description, `tools/lint.py`'s
# check 17 registry line and `check_project_roster` docstring, two sites in
# `tools/figures.py` -- one of them emitted output -- and a comment in
# `tools/tests/test_repo_figures.py`. Deriving them from here was priced and
# declined for a row nobody has asked for. [PR #278 review, M11, F5]
SURFACES = (
    Surface(".claude/skills", "Claude Code", ("AGENTS.md", "CLAUDE.md")),
    Surface(".agents/skills", "Codex", ("AGENTS.md",)),
)

# For callers that need the directories alone -- `tools/lint.py` asks whether a
# path is a generated entry before running a prose guard over it. Derived
# rather than written twice, so a surface cannot be added to one and not the
# other.
ROSTER_DIRS = tuple(surface.directory for surface in SURFACES)

# What marks a file as this generator's to remove. Every surface directory is
# its own runtime's documented home for a project's own skills -- the very
# property this script depends on -- so each of them is shared, not owned, and
# the ownership discipline below is owed on every one rather than on the first. Without this
# marker the orphan branch's stated remedy unlinked whatever it found there: a
# hand-written project skill, untracked, with no prompt and exit 0, and the lint
# then green over the remains. Found at high in PR #210's review by three seats
# independently, all three having run the deletion.
MARKER = b"Generated by `tools/roster.py`"

# The frontmatter terminator, as `lint._frontmatter_fields` finds it. Bytes
# here rather than characters because the whole file is handled as bytes.
_OPEN = b"---"
_CLOSE = b"\n---"


def _body(name: str, surface: Surface) -> bytes:
    """What sits under the copied frontmatter.

    Everything a session opening this file needs in order not to edit it: that
    it is generated, what generates it, and where the cell actually is. That is
    the whole of criterion 6 -- a reader learns it from this file alone, with
    nothing else loaded.

    **It names the runtime this copy exists for**, so the two copies are not
    interchangeable prose sitting in two places. A session that opens the one
    under `.agents/skills/` while working in Claude Code learns from the file
    itself that it is looking at the other runtime's surface, rather than at a
    stray duplicate worth deleting. [#258]
    """
    return (
        f"\n# {name}\n"
        f"\nGenerated by `tools/roster.py` from `{CELLS}/{name}/{CELL_FILE}`, which is"
        f" the `{name}` cell and carries all of it. Read that file now.\n"
        f"\nDo not edit this one: it is the cell's frontmatter copied so that its"
        f" description loads in every {surface.runtime} session working in this"
        f" repository, and `check_project_roster` fails the lint when the two"
        f" fall out of step.\n"
    ).encode("utf-8")


def frontmatter(data: bytes) -> bytes | None:
    """The leading frontmatter block, its terminator, and the line ending after it.

    **The line ending, not one byte.** This used to take a single byte, which
    is the trailing newline on an LF source and the bare carriage return on a
    CRLF one -- so on a CRLF cell the newline was dropped and `expected()`
    produced an entry with no blank line between the terminator and the
    heading. The bound was documented on this function; its consequence was
    documented nowhere [PR #210 review, M19], which is what let it stand. The
    guard reported the cell out of step, truthfully; the session ran the
    command the finding names; `--write` converged to green locally; and the
    committed entry was a content change no diff on that machine could show,
    which reddened Linux CI. A red on the flow's first mandated step, on a
    change whose author has nothing to look at. [#234]

    A source ending at its terminator with no newline at all still yields
    none of one -- there is nothing to take -- and that is the part of the
    old bound that survives.

    **The block keeps the cell's own interior line endings, and that is
    deliberate.** A CRLF cell still copies CRLF into the entry's frontmatter,
    exactly as it always did. The index pin normalizes that away on the way
    in and `in_step` compares as text, so the committed bytes are the same
    wherever the generator last ran -- the property `write()`'s byte
    discipline exists for. What was broken here was never the line ending
    copied; it was the newline that was not.

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
    stop = end + len(_CLOSE)
    for ending in (b"\r\n", b"\n"):
        if data[stop:stop + len(ending)] == ending:
            stop += len(ending)
            break
    return data[:stop]


def in_step(actual: bytes, want: bytes) -> bool:
    """Whether an entry carries what its cell carries, line endings aside.

    **The comparison normalizes CRLF; the write does not.** Those are two
    different questions and this repository has already answered the second:
    `write()` emits bytes so the committed tree holds one set of them
    everywhere, and `.gitattributes` pins the index to LF on every platform.
    What that pin does not pin is the working copy, where a text-mode writer
    outside this repository can turn every line feed into a carriage return
    pair -- the condition [D-186] rules is expected here rather than a defect.

    Read as bytes, this guard was the one place calling that condition a
    defect. A Claude Code worktree whose `.claude/skills/` entries had been
    rewritten in text mode on creation reported every cell out of step, and
    took `python tools/lint.py` red, against a tree git considered clean and
    a commit whose bytes were untouched -- before the session had changed
    anything. Reproduced in this repository at `8b080c8`; `git worktree add`
    from the same commit gives LF on both sides and a clean lint, so the
    rewrite is not git's.

    A drift that is *only* line endings cannot reach a commit through that
    pin, so nothing this guard actually claims is given up by ignoring one.
    Everything else -- a description edited, a name changed, a body replaced
    -- still reports. [#229]

    **The pin has a bound, and it is one character wide.** Git's `text=auto`
    refuses to normalize any file holding a lone carriage return, so every CRLF
    in such a file is committed verbatim. That does not make an entry carrying
    one forgiven here -- this returns False and the finding fires, which two
    tests pin in both polarities. What it reaches is the case where the *cell*
    carries the lone carriage return, so `want` carries it too and the entry is
    that cell's faithful copy: the two agree as text, and git commits the CRLF.
    Measured over four compositions rather than reasoned, and filed. [#233]

    **Which worktrees rewrite these files, since a wide answer is worse than
    none.** A Claude Code **session** worktree comes up with ten files written
    in text mode by the harness -- the nine entries under `.claude/skills/` and
    `CLAUDE.md`; the measurement predates the second surface and says nothing
    about it, and PR #278's seats each report the same nine rewritten and none
    of the others [PR #278 review, F9] -- while
    git checks out the other tracked files LF in the same second, which is how
    the two writers were told apart. `agent-*` subagent worktrees do not do
    this, and they are Claude Code worktrees too. `CLAUDE.md` is the durable
    check: nothing here rewrites it, where `--write` erases the evidence under
    `.claude/skills/` the moment anyone clears the red, so its line endings are
    a fossil of how a worktree was made. Across one machine, 14 of 15 session
    trees carried it CRLF against 0 of 16 agent trees. An earlier draft of this
    said *every* Claude Code worktree, and all five seats of that change's
    review -- every one in an `agent-*` tree -- checked, found LF, and reported
    the cause as false. [#224]

    **Both sides are now covered, and they are covered in two places.** This
    one reaches the entry side. The cell side was `expected()`'s: with the
    *cell* in CRLF, `frontmatter()` lost a byte before this comparison saw
    anything -- its slice took a single byte after the terminator, which on a
    CRLF source is the carriage return rather than the newline -- so `verify`
    reported, `--write` converged to green locally, and the entry it wrote
    differed in content from what an LF checkout produces. Repaired at the
    slice, where the bound was documented, rather than by normalizing in one
    caller and leaving it live for the next. [#234]

    One consequence, accepted: `--write` still repairs a CRLF entry, and nothing
    now tells a session that. The alternative is a line from `verify` in the
    condition this exists to stop reporting, which reinstates the noise. The
    remedy is here instead, where a session asking why its tree looks modified
    will be reading. [PR #232 review, M20]
    """
    return actual.replace(b"\r\n", b"\n") == want.replace(b"\r\n", b"\n")


def cell_names(root: Path) -> list[str]:
    """Every cell a runtime would load from the shipped zone, sorted."""
    directory = root / CELLS
    if not directory.is_dir():
        return []
    return sorted(
        path.name for path in directory.iterdir()
        if (path / CELL_FILE).is_file()
    )


def roster_names(root: Path, surface: Surface) -> list[str]:
    """Every entry one surface currently holds, sorted."""
    directory = root / surface.directory
    if not directory.is_dir():
        return []
    return sorted(
        path.name for path in directory.iterdir()
        if (path / CELL_FILE).is_file()
    )


def expected(root: Path, name: str, surface: Surface) -> bytes:
    """The bytes this cell's entry on this surface must hold.

    One definition, two callers -- the writer and the guard. They were never
    two, and this is why: a guard computing its own expectation is a second
    definition, and the two drift the moment either is edited. `_always_on` in
    `tools/figures.py` carries the same lesson from the same repository.

    **The frontmatter is the same on every surface and the body is not.** What
    has to load is one cell's block copied once per surface; what says why the
    file is there names the runtime that reads it.
    """
    source = root / CELLS / name / CELL_FILE
    data = source.read_bytes()
    block = frontmatter(data)
    if block is None:
        raise ValueError(
            f"{CELLS}/{name}/{CELL_FILE} has no parseable frontmatter to copy"
        )
    return block + _body(name, surface)


def surface_is_where_it_says(root: Path, surface: Surface) -> bool:
    """Whether the surface directory itself is still where it was declared.

    Split out from `inside_roster` because the two conditions need different
    messages and the wrong one shipped for both: with the *base* linked, every
    entry under it reports `resolves outside` and names a path that is not a
    link and often does not exist, under a remedy -- *remove the link* -- that
    no named path can execute. A reader inspects each named directory, finds
    no link at any of them, and holds a red gate with nothing to act on, which
    is the second of the two failure modes the containment check was added to
    close, restated one level up. [PR #278 review, F2]

    It is also the right granularity: one link is one condition, and it drew a
    finding per cell.

    **What this answers is whether the directory resolves where it was
    declared, not whether that directory is a link**, and the message has to
    say the weaker thing. The link can sit at any component of the path: a
    junction at `.claude` pointing into a shared dotfiles directory is an
    ordinary arrangement, and under it `.claude/skills` is neither a link nor
    extant, so a message naming it as the link to remove sends a reader to a
    path they cannot act on. That is this function's own defect one level
    further up, and the first fix for it shipped carrying it. The message also
    stops claiming nothing loads: a junction is transparent to a runtime, so
    the descriptions behind one are read normally and what is actually true is
    that nothing there is this repository's to keep in step.
    [PR #278 review, P1, P2]
    """
    return (root / surface.directory).resolve() == (
        root.resolve() / surface.directory)


def inside_roster(root: Path, entry: Path, surface: Surface) -> bool:
    """Whether an entry's real location is still under its own surface directory.

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

    **The surface directory itself is tested, not only the entries under it.**
    Resolving the base and then asking whether the entry resolves under it
    answers yes whenever the *base* is the link, because both sides resolve
    through it -- so a junction at `.agents/skills` passed containment in both
    of its branches. Pointed at a directory outside the repository, `--write`
    wrote nine entries there, reported paths the files did not go to, and
    exited 0 with the lint green. Pointed at the other surface, it wrote nine
    and then reported nine permanent findings against the surface the session
    had not touched, whose only named remedy was the command that produced
    them -- the mandated gate red with no reachable answer. That second branch
    needs two surfaces for one to be linked to the other, so it was
    unreachable before this repository had them. [PR #278 review, M12]

    So the base is compared to where it was declared to be. The ordinary tree
    passes; a junctioned surface fails; and **a repository that itself lives
    under a junctioned path still passes**, which is the trap in this check
    and the reason the declared side is `root.resolve() / directory` rather
    than the raw `root / directory`: on such a tree the surface genuinely
    resolves elsewhere, and comparing against the unresolved root would red
    every lawful entry on it. A surface that does not exist yet resolves
    lexically to its declared path and so passes, which is what lets `write()`
    create it.

    Scoped to the roster side. A link under `skills/` is not checked here: this
    script only ever reads a cell, and reading through one escapes nothing.
    """
    base = (root / surface.directory).resolve()
    if not surface_is_where_it_says(root, surface):
        return False
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
    file carrying `MARKER`.** Everything else under a surface directory
    belongs to whoever put it there. Ownership is checked on **every path that
    touches a file**, not only on removal -- checking it on one path is what
    let the regeneration branch go on destroying hand-written content after
    the removal branch stopped. [PR #210 cycle one, C1-F2/C1-F3]

    **A shape that is about a surface is reported per surface**, and its
    message names both the directory it found and the runtime that reads it.
    One condition on one surface draws one finding; the same cell stale in
    both draws one for each, because they are two files and repairing one
    leaves the other serving a superseded trigger to the other runtime.
    **The shapes that are about a cell rather than a surface are reported once
    and name neither** -- unparseable frontmatter, and no cell at all. Which
    group a shape is in is stated on the shape below; no count of either group
    is stated anywhere, for the reason the paragraph after them gives about
    counting these shapes at all. An earlier draft of this paragraph said "the
    one exception" and there were two. [#258] [PR #278 review, M7]

    Each shape below says what its own message names. There is no count here:
    a stated count of these has been wrong three times running, each time in
    the sentence written to correct the one before, so the arithmetic is gone
    rather than corrected a fourth time. [PR #210 cycle two, C2-F1]

    - **missing** -- a cell with no entry on a surface, which is the runtime
      that surface serves loading nothing for it. Names `--write` and the
      runtime.
    - **out of step** -- a cell whose entry this script wrote and the cell has
      since moved on. Names `--write`.
    - **orphan** -- an entry this script wrote whose cell is gone. Names
      `--write`.
    - **collision** -- a cell's name taken by a file this script did not
      write. Names the move first and `--write` second, because both are
      needed and only a person can do the first. Reported rather than
      overwritten, and reported rather than ignored: the hand-written
      frontmatter is what loads, so the cell's real description does not,
      which is a silent criterion-1 failure.
    - **unparseable frontmatter** -- a cell `--write` cannot copy anywhere.
      Names no command and no surface; the cell's frontmatter is what has to
      change, and it is one file however many copies of it are owed.
    - **no cell at all** -- nothing under `skills/` to compare against. Names
      no command, for the reason #198 gives about a sibling guard: no cell
      found is indistinguishable from every cell lawful.

    The three that name `--write` alone do so because for them the fix is
    always that command, and a guard reporting a diff without it makes the
    reader derive what the script already knows.

    And one condition that is not a finding at all: **a foreign entry at a
    name that is not a cell**, which is a project skill somebody wrote in the
    runtime's documented place for one -- true of both directories, each
    being its own runtime's documented place. Policing it produced a red the
    lint could never clear on a lawful tree. A directory there holding no
    `SKILL.md` is likewise silent; `write()` reports residue at the moment it
    creates it, which is where that report is useful.

    Named rather than counted on purpose: a stated count of shapes has now
    been wrong twice, and the second time in the sentence written to fix the
    first. [PR #210 cycle one, C1-F5]
    """
    findings = []
    cells = cell_names(root)
    for surface in SURFACES:
        where = surface.directory
        if not surface_is_where_it_says(root, surface):
            # Once for the surface, naming the surface -- the only path a
            # reader can act on. [PR #278 review, F2]
            findings.append(
                f"roster: something on the path to {where} is a link, so "
                f"{where} resolves somewhere other than {where} and writing "
                f"an entry would land there instead -- no {surface.runtime} "
                f"entry here is this repository's to keep in step; no command "
                f"repairs this, remove the link on the path to {where}"
            )
            continue
        for name in cells:
            target = root / where / name / CELL_FILE
            if not inside_roster(root, target.parent, surface):
                findings.append(
                    f"roster: {where}/{name}/ is a link, so it resolves "
                    f"outside {where}/ and writing there would land outside "
                    f"this repository -- the `{name}` cell's description "
                    f"reaches no {surface.runtime} session here; no command "
                    f"repairs this, remove the link at {where}/{name}/"
                )
                continue
            try:
                want = expected(root, name, surface)
            except (ValueError, OSError) as exc:
                # Once per cell, not once per surface. The cell's frontmatter
                # is what has to change, so a second copy of an unrepairable
                # line asks a reader to fix the same file twice.
                line = (f"roster: {name}: {exc} -- no command repairs this; "
                        f"fix the cell's frontmatter")
                if line not in findings:
                    findings.append(line)
                continue
            if not target.is_file():
                findings.append(
                    f"roster: {where}/{name}/{CELL_FILE} is missing, so the "
                    f"`{name}` cell's description loads in no {surface.runtime} "
                    f"session here -- run `python tools/roster.py --write`"
                )
                continue
            if in_step(target.read_bytes(), want):
                continue
            if is_generated(target):
                findings.append(
                    f"roster: {where}/{name}/{CELL_FILE} is out of step with "
                    f"{CELLS}/{name}/{CELL_FILE}, so every {surface.runtime} "
                    f"session here reads the superseded trigger -- run "
                    f"`python tools/roster.py --write`"
                )
            else:
                findings.append(
                    f"roster: {where}/{name}/{CELL_FILE} was not written by "
                    f"tools/roster.py and holds the name of the `{name}` cell, "
                    f"so that cell's description loads in no {surface.runtime} "
                    f"session here and nothing will overwrite yours -- move "
                    f"your file out of {where}/, then run "
                    f"`python tools/roster.py --write`"
                )
        for name in roster_names(root, surface):
            if name in cells:
                continue
            if is_generated(root / where / name / CELL_FILE):
                findings.append(
                    f"roster: {where}/{name}/{CELL_FILE} names no cell under "
                    f"{CELLS}/, so every {surface.runtime} session here loads "
                    f"a retired trigger -- run `python tools/roster.py --write`"
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
    for surface in SURFACES:
        where = surface.directory
        if not surface_is_where_it_says(root, surface):
            changed.append(
                f"left {where}: something on the path to it is a link, so it "
                f"resolves somewhere other than {where}")
            continue
        for name in cells:
            try:
                want = expected(root, name, surface)
            except (ValueError, OSError) as exc:
                # Once per cell, as `verify` reports it. A cell nothing can
                # copy is one file to fix however many surfaces are owed a
                # copy of it, and this loop said so once per surface while
                # the rule it mirrors said once. [PR #278 review, M8]
                line = f"skipped {CELLS}/{name}/{CELL_FILE}: {exc}"
                if line not in changed:
                    changed.append(line)
                continue
            target = root / where / name / CELL_FILE
            if not inside_roster(root, target.parent, surface):
                changed.append(
                    f"left {where}/{name}/: it is a link, so it resolves "
                    f"outside {where}/"
                )
                continue
            if target.is_file():
                # Byte-exact here where `verify` is not: this branch decides
                # whether to rewrite, and rewriting an entry a text-mode tool
                # turned to CRLF restores the canonical bytes -- which is a
                # remedy worth offering, not noise. `verify` decides whether
                # the tree is lawful, and by `in_step` that entry already is.
                if target.read_bytes() == want:
                    continue
                # Ownership is checked here too, not only on removal. This
                # branch went on overwriting whatever sat at a cell's name
                # after the removal branch stopped deleting orphans -- the
                # same irreversible loss of untracked, hand-written content,
                # reported as `wrote` and exiting 0. [PR #210 cycle one,
                # C1-F2]
                if not is_generated(target):
                    changed.append(
                        f"left {where}/{name}/{CELL_FILE}: not written by "
                        f"this script, and it holds the `{name}` cell's name"
                    )
                    continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(want)
            changed.append(f"wrote {where}/{name}/{CELL_FILE}")
        for name in roster_names(root, surface):
            if name in cells:
                continue
            entry = root / where / name
            if not is_generated(entry / CELL_FILE):
                changed.append(
                    f"left {where}/{name}/{CELL_FILE}: not written by this "
                    f"script"
                )
                continue
            (entry / CELL_FILE).unlink()
            changed.append(f"removed {where}/{name}/{CELL_FILE}")
            residue = sorted(item.name for item in entry.iterdir())
            if residue:
                changed.append(
                    f"left {where}/{name}/ holding {', '.join(residue)}"
                )
            else:
                entry.rmdir()
    return changed


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(
        prog="roster.py",
        description="Generate or verify the project roster under .claude/skills and .agents/skills, which is what makes this repository's own cell descriptions load in Claude Code and in Codex.",
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

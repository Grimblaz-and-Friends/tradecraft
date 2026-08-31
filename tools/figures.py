#!/usr/bin/env python3
"""This repo's write-up figures, derived rather than recalled (issue #137).

The general engine ships in the authoring skill; this wrapper is the
repo-specific application: it feeds the engine this repository's parameters
and adds the figures that reach a repo-only guard: the census, which reuses
check_entry_references' own resolution, the description ceiling, which is
check_cell_frontmatter's, and the cell total, which exists because
check_doctrine caps a cell's body and a body cap is dodgeable one
directory down. The budgets are the guards' own constants. Dependencies point
the lawful direction — repo-only code importing shipped code — and the numbers
that must agree with a guard come from the guard:

  - the doc budget is imported from tools/lint.py, so the headroom figure can
    never drift from what check_doctrine enforces;
  - the decision-log census reuses check_entry_references' own reference
    extraction and resolution, with both recorded sets ignored — the derivation
    D-135 prescribes: "Empty both recorded sets in `tools/lint.py` and count
    what `check_entry_references` reports" — pinned references excluded
    because a pin is a lawful form, not a recorded exemption.

Usage:  python tools/figures.py [--base REF] [--cell PATH --cell-budget N]
                                [--json]

Always emitted, in this order:

  1. figure_tests -- the suite, over tools/tests and skills
  2. figure_doc -- AGENTS.md against its ceiling
  3. figure_charter -- the charter's body against its ceiling
  4. figure_always_on -- the always-on total, for both audiences
  5. figure_census -- the decision log

With --base, figure_delta adds the governing-prose delta (AGENTS.md, CLAUDE.md,
and the .md files under skills/) against that ref. With --cell, figure_cell,
figure_cell_total and figure_cell_description add that cell's three figures --
the body against its budget, the cell's whole prose unbudgeted, and the
always-on description. Both the delta's base and a cell's budget are
caller decisions neither script will default.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Shared with the shipped zone, which is the lawful direction: repo-only
# code may import shipped code. Resolved from this file rather than the
# working directory, so the script runs from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from winio import utf8_stdio  # noqa: E402
import lint  # noqa: E402
import roster  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "authoring_figures", ROOT / "skills" / "authoring" / "scripts" / "figures.py"
)
engine = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(engine)

SUITE_PATHS = ["tools/tests", "skills"]
DOC = "AGENTS.md"
POINTER = "CLAUDE.md"
# `charter` is deliberate and not dead: a delta measured against a base that
# predates the charter becoming a cell has to see the old path on the base
# side, or the move reads as a reduction. It matches nothing in a current
# working tree, which is why it looks like a leftover.
PROSE_PATHS = ["AGENTS.md", "CLAUDE.md", "charter", "skills"]
PROSE_SUFFIXES = [".md"]


def figure_census(root: Path) -> dict:
    """What check_entry_references would report with both recorded sets empty:
    every unresolved, unpinned reference in the decision entries and the log's
    index, counted as occurrences and as distinct (entry, reference) pairs."""
    directory = root / "docs" / "architecture" / "decisions"
    occurrences = 0
    pairs: set[tuple[str, str]] = set()
    for path in sorted(directory.glob("D-*.md")) + [directory / "README.md"]:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            for ref, _form, pinned in lint._entry_refs(line):
                if pinned or lint._entry_ref_resolves(root, directory, ref):
                    continue
                occurrences += 1
                pairs.add((path.name, ref))
    return {
        "name": "decision-log census",
        "value": (
            f"{occurrences} occurrences, {len(pairs)} distinct "
            f"(entry, reference) pairs"
        ),
        "basis": (
            "check_entry_references' resolution with both recorded sets "
            "emptied; pinned references excluded; entries plus the log's "
            "index, working tree"
        ),
        "data": {"occurrences": occurrences, "pairs": len(pairs)},
    }


def figure_cell_description(root: Path, rel_path: str) -> dict:
    """A cell's always-on surface: the frontmatter field every session loads.

    Separate from the body figure because they are paid at different times and
    move independently -- #169 shed body and grew description in the same
    change, and a body-only figure certified that as "no more to load".
    """
    target = root / rel_path
    if not target.is_file():
        raise SystemExit(f"figures: {rel_path} is not a readable file under {root}")
    fields = lint._frontmatter_fields(
        target.read_text(encoding="utf-8", errors="replace")
    )
    if fields is None or "description" not in fields:
        raise SystemExit(f"figures: {rel_path} has no parseable description")
    chars = len(fields["description"])
    budget = lint.CELL_FIELD_MAX_CHARS["description"]
    return {
        "name": f"cell `{rel_path}` (description)",
        "value": f"{chars:,} of {budget:,} chars, headroom {budget - chars:,}",
        "basis": (
            "decoded UTF-8 characters of the frontmatter description as "
            "check_cell_frontmatter reads it, working tree"
        ),
        "data": {
            "path": rel_path, "chars": chars, "budget": budget,
            "headroom": budget - chars,
        },
    }


def figure_cell_total(root: Path, rel_path: str) -> dict:
    """Every character of prose the cell carries, body and depth together.

    Emitted beside the body figure because a body budget can be satisfied by
    moving prose one directory down, and a body-only figure certifies that as
    a reduction. Deliberately unbudgeted: capping the total would cap
    depth-shedding itself, which is the move the standard wants. What it buys
    is that the dodge is visible to whoever takes it -- #177's ruling.

    Markdown only. A script the cell carries is code a session runs, not prose
    it loads, and counting it would price a test file against a prose ceiling.
    """
    if not is_cell_path(rel_path):
        raise SystemExit(
            f"figures: --cell '{rel_path}' is not a cell -- this figure walks the "
            "naming file's whole directory, so on a non-cell path it reports a "
            "confidently-labelled total for whatever tree happens to sit above it"
        )
    target = root / rel_path
    if not target.is_file():
        raise SystemExit(f"figures: {rel_path} is not a readable file under {root}")
    body = len(engine.frontmatterless(
        target.read_text(encoding="utf-8", errors="replace")
    ))
    depth = sorted(
        p for p in target.parent.rglob("*.md") if p.resolve() != target.resolve()
    )
    depth_chars = sum(
        len(p.read_text(encoding="utf-8", errors="replace")) for p in depth
    )
    return {
        "name": f"cell `{target.parent.relative_to(root).as_posix()}` (total prose)",
        "value": (
            f"{body + depth_chars:,} chars -- body {body:,} + {len(depth)} "
            f"depth file(s) {depth_chars:,}"
        ),
        "basis": (
            "decoded UTF-8 characters, universal-newline read; SKILL.md below "
            "its frontmatter plus every other .md in the cell whole; no budget "
            "-- a ceiling here would cap depth-shedding itself; working tree"
        ),
        "data": {
            "path": rel_path, "body": body, "depth_files": len(depth),
            "depth": depth_chars, "total": body + depth_chars,
        },
    }


def is_cell_path(path: str) -> bool:
    """skills/<cell>/SKILL.md, and nothing deeper.

    One predicate for both readers. They had two -- a one-level glob on the
    working tree and an `endswith("/SKILL.md")` over a recursive listing --
    which agree on every tree that exists today and would count different sets
    the moment a SKILL.md appeared under a cell's own subdirectory. A delta
    whose two halves measure different sets is arithmetic, not a measurement.
    """
    parts = path.split("/")
    return len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md"


def is_roster_path(directory: str):
    """`<directory>/<cell>/SKILL.md`, and nothing deeper.

    One of the repository's own rosters, which is a different set from the
    cells and is why it gets a predicate rather than a widened `is_cell_path`.
    The sets are held equal by `check_project_roster`, not by this file -- and
    a figure that assumed the equality it is meant to report would be the
    defect #199 records, where the roster was counted here and loaded nowhere.

    **What this predicate actually does is bound the depth**, and it is made
    per surface only so it can. Both callers scope the listing before it runs
    -- `figure_always_on` globs one directory, `always_on_at` runs `ls-tree`
    under one prefix -- so a path from one surface is never offered to the
    other's predicate, and a widened predicate could not cross-count if it
    tried. An earlier version of this paragraph said it could; the claim was
    false, and it was stated as one of the design's load-bearing reasons.
    Probed by substituting a widened predicate into both callers: every number
    identical, on this tree and on a divergent one. The live work is the depth
    clause in `always_on_at`, where `ls-tree -r` returns paths deeper than
    `<directory>/<cell>/SKILL.md`. [PR #278 review, M6]
    """
    head = directory.split("/")
    depth = len(head) + 2

    def predicate(path: str) -> bool:
        parts = path.split("/")
        return (len(parts) == depth and parts[:len(head)] == head
                and parts[-1] == "SKILL.md")

    return predicate


def _roster(read, paths: list[str]) -> tuple[int, int]:
    """Name plus description over a set of cell files: (chars, files read).

    Every audience loads a roster; they load it from different directories, so
    the arithmetic is shared and the input is not. An adopter's comes from the
    plugin's `skills/`; a session working in this repository loads what the
    directory for **its own runtime** holds, one per runtime, which is what
    #199 found reported and never read and #258 found reported for one runtime
    only.

    **It counts every `SKILL.md` on the surface, not only the generated
    entries**, because that is what the runtime loads: a project skill written
    by hand at a name that is no cell is lawful there, `check_project_roster`
    says nothing about it, and it is always-on prose all the same. The caller's
    label has to say so; calling this "the roster" and counting more than the
    roster is what [PR #278 review, M20] found.
    """
    chars = files = 0
    for path in paths:
        text = read(path)
        if text is None:
            continue
        files += 1
        fields = lint._frontmatter_fields(text) or {}
        chars += len(fields.get("name", "")) + len(fields.get("description", ""))
    return chars, files


def _always_on(read, cell_paths: list[str],
               roster_paths: dict[str, list[str]]) -> dict:
    """Everything a session reads before it does anything, for both audiences.

    The composition lives here once, and its two callers supply only bytes:
    figure_always_on reads the working tree, always_on_at reads a git
    revision. They were two hand-written copies of this arithmetic, which is
    how a mutation that stopped the base side counting CLAUDE.md left the whole
    suite green -- the two halves of a delta silently measuring different
    surfaces. Nothing compared them, and a delta between two definitions is not
    a delta.

    `read` returns text with newlines already universal, because that is the
    unit every guard here measures in: check_doctrine reads through
    `read_text`, where CRLF is one character. A reader handing back raw bytes
    counts a CRLF tree larger than the guard does, and the delta between the
    two readers reports a change nobody made.

    Three surfaces, and no invocation reported their sum -- so every write-up
    about growth measured one file and read as a reduction while the total
    rose. It rose through two restructures that were each meant to shrink it.

    The two audiences are not the same set, and conflating them is the error
    this figure exists to stop: a plugin's root AGENTS.md and CLAUDE.md land
    in a consumer's cache as inert files and are never loaded, so an adopter
    reads the charter and the roster's descriptions and nothing else, while
    this repository reads its own doctrine on top.

    **Each audience's roster is read from the directory that audience actually
    loads**, which is the correction #199 bought. Both sides used to be
    counted from `skills/` -- true of an adopter, who installs the plugin, and
    false here, where nothing installs it and the descriptions loaded nowhere.
    The figure said 16,241 against 11,351 read, and every trigger routed to a
    description was priced as though it fired here. Now the repo side reads
    the surface directories themselves, so deleting one moves the number
    rather than leaving it to assert what the tree stopped doing.

    **There is no single always-on total here, because the quantity is per
    runtime**: this repository loads one roster directory per runtime, neither
    reaches the other's, and the two do not even read the same doctrine files.
    So `here` carries a row per surface and every surface a reader meets
    prints those rows.

    `repo_total` survives as the one scalar a delta can be taken against, and
    is **the smallest** row: it cannot overstate what some session here reads,
    and reporting the largest would have shown this change's own arrival as no
    movement at all, the base having loaded nothing into Codex. **Nothing
    renders it alone.** An earlier draft argued that a scalar was safe because
    rows would be printed beside it and the rows would agree on any lawful
    tree. Both halves were false: one of the three renderers printed no rows,
    and the rows disagree on trees the guard passes -- a lawful hand-written
    project skill under one surface is loaded, counted, and reported by
    nothing. Probed, both. [#258] [PR #278 review, M1, M21]
    """
    charter = 0
    for path in cell_paths:
        text = read(path)
        if text is not None and path == lint.CHARTER:
            charter = len(lint._frontmatterless(text))
    adopter_roster, cells = _roster(read, cell_paths)
    agents = len(read(DOC) or "")
    # CLAUDE.md counts here for the same reason it has its own budget: this
    # runtime loads it, and leaving it out meant a rule could move from
    # AGENTS.md into it and the total would report a reduction while nothing
    # left the surface -- the failure routing.md's closing paragraph names.
    # It is not in the adopter's total, which omits it on the same ground as
    # AGENTS.md: a plugin root's copy reaches the cache inert.
    pointer = len(read(POINTER) or "")
    adopter = charter + adopter_roster
    # One row per surface, in `roster.SURFACES` order, asked of the generator
    # rather than listed here: a surface this figure did not know about would
    # be a runtime loading a roster nobody prices.
    here = []
    for surface in roster.SURFACES:
        chars, entries = _roster(read, roster_paths.get(surface.directory, []))
        # The doctrine files are this runtime's, not every runtime's: both
        # read AGENTS.md and only Claude Code reads CLAUDE.md, which is a
        # pointer to it. Charging every row for both made the two rows equal
        # on a healthy tree and so suppressed exactly the divergence these
        # rows exist to show. [PR #278 external pass]
        doctrine = sum(len(read(path) or "") for path in surface.doctrine)
        here.append({
            "runtime": surface.runtime,
            "directory": surface.directory,
            "doctrine": doctrine,
            "roster": chars,
            "entries": entries,
            "total": doctrine + charter + chars,
        })
    return {
        # `agents` and `pointer` are the two doctrine files, kept apart
        # because they are governed by two different ceilings and a consumer
        # pricing their sum against either one states a ceiling that does not
        # exist. `doctrine` is their sum and **no total is built from it** --
        # each row is built from `row["doctrine"]`, the files *that* runtime
        # reads, which is not the same set. It survives for the callers that
        # want the pair summed and is not a term in any total. [PR #278
        # review, F8]
        "doctrine": agents + pointer, "agents": agents, "pointer": pointer,
        "charter": charter,
        # `roster` is the adopter's, from the plugin's cells; `here` is this
        # repository's, one row per runtime, from the directory that runtime's
        # sessions load. Equal on a tree the roster guard passes, and reported
        # apart anyway, because a figure that reads one number twice cannot
        # show the tree where they stopped agreeing.
        "roster": adopter_roster, "cells": cells,
        "here": here,
        # Kept as the one scalar a delta can be taken against, and defined as
        # the smallest so it cannot overstate what some session here reads.
        # **Nothing renders it alone any more.** Every surface a reader meets
        # prints the rows, because the quantity is per runtime and a scalar
        # standing for it was read as one runtime's number by whichever
        # session happened to be in the other. [PR #278 review, M1]
        "repo_total": min(row["total"] for row in here),
        "adopter_total": adopter,
    }


def by_runtime(data: dict) -> str:
    """Every runtime's total, decomposed into the terms that compose *it*.

    **Unconditional, and one chain per runtime.** Two things this replaced
    were wrong in the same way. A clause that printed the rows only when they
    disagreed left the surfaces that render this number saying `N chars here`
    on a tree where N was some other runtime's; and a single `+` chain beside
    a single total summed to whichever runtime happened to be long, so the
    sentence was right or wrong according to which surface was short. Both are
    the same defect -- one decomposition standing for a quantity that has one
    value per runtime. [PR #278 review, M1, M13, M19, M21]

    Each chain sums to the total it is printed against, which is the property
    `test_the_callout_line_decomposes_its_own_total` checks, and which no
    single chain could have. The roster term says which directory it counted
    rather than calling itself the roster: it counts every `SKILL.md` the
    runtime loads from that directory, and a hand-written project skill there
    is lawful, loaded, and not the roster's. [PR #278 review, M20]
    """
    return "; ".join(
        f"{row['runtime']} {row['total']:,} = doctrine {row['doctrine']:,}"
        f" + charter body {data['charter']:,}"
        f" + {row['entries']} name/description from {row['directory']}/"
        f" {row['roster']:,}"
        for row in data["here"]
    )


def figure_always_on(root: Path) -> dict:
    """The always-on surface as the working tree has it."""
    def read(path: str) -> str | None:
        target = root / path
        return (target.read_text(encoding="utf-8", errors="replace")
                if target.is_file() else None)

    def listing(directory: str, predicate) -> list[str]:
        base = root / directory
        if not base.is_dir():
            return []
        found = sorted(p.relative_to(root).as_posix()
                       for p in base.glob("*/SKILL.md"))
        return [p for p in found if predicate(p)]

    data = _always_on(
        read,
        listing("skills", is_cell_path),
        {surface.directory: listing(surface.directory,
                                    is_roster_path(surface.directory))
         for surface in roster.SURFACES},
    )
    return {
        "name": "always-on surface",
        "value": (
            f"{by_runtime(data)}; an adopter {data['adopter_total']:,} = "
            f"charter body {data['charter']:,} + {data['cells']} cell "
            f"name/description {data['roster']:,}"
        ),
        "basis": (
            "decoded UTF-8 characters; AGENTS.md and CLAUDE.md whole, the "
            "charter below its frontmatter, and each cell's name plus "
            "description as check_cell_frontmatter reads them; an adopter's "
            "total omits both doctrine files, which reach a plugin cache as "
            "inert files and are never loaded, and counts only what this "
            "practice contributes to their always-on surface; here there is "
            "one total per runtime rather than one for the repository, each "
            "built from the doctrine files that runtime reads, the charter "
            "body, and the skills directory that runtime loads -- both read "
            "AGENTS.md and only Claude Code reads CLAUDE.md, while the "
            "charter is charged to every runtime, and a name/description term "
            "counts every SKILL.md on that surface including a hand-written "
            "project skill; an adopter's is read from skills/, which is what "
            "installing the plugin gives them; working tree"
        ),
        "data": data,
    }


def always_on_at(root: Path, ref: str) -> dict[str, int]:
    """Each runtime's always-on total at another revision, for a delta.

    Reads blobs rather than checking anything out, so it is safe to call from
    a working tree somebody is using. Raises rather than guessing when the ref
    or a path is unreadable -- a delta against a base that could not be read is
    worse than no delta, and the caller states the absence.

    The composition it applies is the working tree's, from `_always_on`, so
    the two halves of a delta cannot drift apart.

    **Runtime to total, not one scalar.** A single number here made the delta
    inherit `repo_total`'s bound: growth in one runtime's surface alone moved
    no scalar, so a change that raised what every Claude Code session loads
    could book `+0` and never trip the outflow rule. Keyed by runtime rather
    than positional, so a caller cannot line two revisions' rows up wrongly
    when `SURFACES` is reordered. [PR #278 review, M22]

    **The keys are the working tree's, on every base**, because the rows come
    from the working tree's `SURFACES` however old the revision is. So a
    runtime this repository did not have at the base reads as a total rather
    than as an absence: at `f9924e3`, the first commit, holding no `AGENTS.md`
    and no `skills/` at all, this returns zero for every runtime. Reading the
    base revision's own `SURFACES` instead is a design change and is not taken
    here; what is corrected is the claim that a caller is told about a missing
    runtime, which it never is. [PR #278 review, F6]
    """
    import subprocess

    def read(path: str) -> str | None:
        out = subprocess.run(
            ["git", "-C", str(root), "show", f"{ref}:{path}"],
            stdin=subprocess.DEVNULL, capture_output=True,
        )
        if out.returncode != 0:
            return None
        # Universal newlines, matching what read_text gives the other reader
        # and what every guard here measures: a tree stored with CRLF would
        # otherwise count larger through git than through the filesystem, and
        # the delta between them would report a change nobody made.
        text = out.stdout.decode("utf-8", errors="replace")
        return text.replace("\r\n", "\n").replace("\r", "\n")

    def listing(prefix: str, predicate) -> list[str]:
        # `ls-tree` on a prefix absent from the revision exits 0 with no
        # output, which is the wanted answer rather than an error: a base
        # predating `.claude/skills/` had no roster, and a delta across this
        # change should show the surface rising by what it did not load.
        out = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "-r", "--name-only", ref, prefix],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True,
        ).stdout.split()
        return [p for p in out if predicate(p)]

    data = _always_on(
        read,
        listing("skills/", is_cell_path),
        {surface.directory: listing(surface.directory + "/",
                                    is_roster_path(surface.directory))
         for surface in roster.SURFACES},
    )
    return {row["runtime"]: row["total"] for row in data["here"]}


def figure_charter(root: Path) -> dict:
    """The charter's body against the one cell budget a guard here enforces.

    The measurement is the engine's -- a cell body is a general shape, not a
    repo-bound one, and reimplementing it here is how a figure drifts from the
    guard judging it. What is repo-bound is the budget and the fact that
    something enforces it, which is what this adds.
    """
    figure = engine.figure_cell(root, lint.CHARTER, lint.CHARTER_BUDGET_CHARS)
    figure["basis"] += (
        " -- here tools/lint.py's own constant, so the figure cannot drift "
        "from what check_doctrine enforces"
    )
    return figure


def build_figures(root: Path, base: str | None,
                  cell: str | None = None, budget: int | None = None) -> list[dict]:
    figures = [
        engine.figure_tests(root, SUITE_PATHS),
        engine.figure_doc(root, DOC, lint.AGENTS_BUDGET_CHARS),
        figure_charter(root),
        figure_always_on(root),
        figure_census(root),
    ]
    if base:
        figures.append(engine.figure_delta(root, base, PROSE_PATHS, PROSE_SUFFIXES))
    if cell:
        if budget is None:
            raise SystemExit(
                "figures: --cell needs --cell-budget; a cell's budget is a "
                "caller decision and picking one silently is how a stated "
                "figure diverges from the guard that judges it"
            )
        enforced = lint.CELL_BODY_BUDGET_CHARS.get(cell)
        if enforced is not None and enforced != budget:
            raise SystemExit(
                f"figures: --cell-budget {budget} disagrees with the {enforced} "
                f"check_doctrine enforces for {cell}. Refusing rather than "
                "defaulting: the caller decides the budget, and a stated headroom "
                "no guard backs is the drift this script exists to stop"
            )
        cell_figure = engine.figure_cell(root, cell, budget)
        if enforced is not None:
            # The budget is now guard-backed for this cell -- the refusal above
            # made it so -- and a basis reading "the budget is the caller's" is
            # byte-identical to what an uncapped cell emits. Same shape the
            # charter's own figure uses, and for the same reason. (Spelled
            # without that function's name on purpose: the docstring
            # enumeration test scans this source for figure_* tokens.)
            cell_figure["basis"] += (
                " -- and here check_doctrine enforces that budget, so the figure "
                "cannot drift from the guard that judges it"
            )
        figures.append(cell_figure)
        figures.append(figure_cell_total(root, cell))
        figures.append(figure_cell_description(root, cell))
    return figures


def body_strip_scan(repo: Path) -> list[str]:
    """What check_body_strip_owner's predicate finds in the corpus it skips.

    That check excludes test files, and the exclusion is its one stated blind
    spot. The size of that blind spot is a count over a corpus the repository
    keeps writing into, so it is a query rather than a number: an earlier
    version of the check stated it as a figure in its own docstring, measured
    under a predicate that was then tightened, and the figure survived the
    predicate by a factor of five. This is the command that answers it on
    whatever tree you are on.

    The sweep itself is `lint.hand_rolled_strips`, which is also what the
    check reports. A second copy here read low the moment the check gained a
    module-scope pass -- an instrument sizing a blind spot must not have one
    of its own.
    """
    hits: list[str] = []
    for dirname in lint.SHIPPED_DIRS + tuple(sorted(lint.REPO_ONLY_NAMES)):
        base = repo / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            if not (path.name.startswith("test_") or "tests" in path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            rel = path.relative_to(repo).as_posix()
            for name, lineno in lint.hand_rolled_strips(tree):
                hits.append(f"{rel}:{lineno} {name}")
    return hits


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(
        prog="figures.py",
        description="This repo's write-up figures, each with its basis inline.",
    )
    parser.add_argument("--base", metavar="REF",
                        help="also emit the governing-prose delta against REF")
    parser.add_argument("--cell", metavar="PATH",
                        help="also emit a cell's body, total-prose and description figures")
    parser.add_argument("--cell-budget", metavar="N", type=int,
                        help="the body budget --cell is measured against")
    parser.add_argument("--json", action="store_true",
                        help="emit JSON instead of markdown")
    parser.add_argument("--body-strip-scan", action="store_true",
                        help="list hand-rolled frontmatter strips in the test "
                             "files check_body_strip_owner skips")
    args = parser.parse_args(argv)
    if args.body_strip_scan:
        hits = body_strip_scan(ROOT)
        for hit in hits:
            print(hit)
        print(f"{len(hits)} hand-rolled strip(s) in the excluded test corpus")
        return 0
    figures = build_figures(ROOT, args.base, args.cell, args.cell_budget)
    stamp = engine.tree_stamp(ROOT)
    command = ("python tools/figures.py " + shlex.join(argv)).rstrip()
    render = engine.render_json if args.json else engine.render_markdown
    print(render(stamp, command, figures))
    return 0


if __name__ == "__main__":
    sys.exit(main())

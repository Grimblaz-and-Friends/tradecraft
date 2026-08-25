#!/usr/bin/env python3
"""This repo's write-up figures, derived rather than recalled (issue #137).

The general engine ships in the authoring skill; this wrapper is the
repo-specific application: it feeds the engine this repository's parameters
and adds the figures that reach a repo-only guard: the census, which reuses
check_entry_references' own resolution, and the description ceiling, which is
check_cell_frontmatter's. The budgets are the guards' own constants. Dependencies point
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
and the .md files under skills/) against that ref. With --cell, figure_cell and
figure_cell_description add that cell's two figures. Both the delta's base and
a cell's budget are caller decisions neither script will default.
"""
from __future__ import annotations

import argparse
import importlib.util
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lint  # noqa: E402

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
    move independently -- #169 shed 25 chars of body and added 147 of
    description, and a body-only figure certified that as "no more to load".
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


def _always_on(read, cell_paths: list[str]) -> dict:
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
    """
    roster = charter = cells = 0
    for path in cell_paths:
        text = read(path)
        if text is None:
            continue
        cells += 1
        fields = lint._frontmatter_fields(text) or {}
        roster += len(fields.get("name", "")) + len(fields.get("description", ""))
        if path == lint.CHARTER:
            charter = len(lint._frontmatterless(text))
    agents = len(read(DOC) or "")
    # CLAUDE.md counts here for the same reason it has its own budget: this
    # runtime loads it, and leaving it out meant a rule could move from
    # AGENTS.md into it and the total would report a reduction while nothing
    # left the surface -- the failure routing.md's closing paragraph names.
    # It is not in the adopter's total, which omits it on the same ground as
    # AGENTS.md: a plugin root's copy reaches the cache inert.
    pointer = len(read(POINTER) or "")
    adopter = charter + roster
    return {
        # `doctrine` is the sum the total is built from; `agents` and
        # `pointer` are the two files it is made of, kept apart because they
        # are governed by two different ceilings and a consumer that prices
        # the sum against either one states a ceiling that does not exist.
        "doctrine": agents + pointer, "agents": agents, "pointer": pointer,
        "charter": charter, "roster": roster, "cells": cells,
        "repo_total": agents + pointer + adopter, "adopter_total": adopter,
    }


def figure_always_on(root: Path) -> dict:
    """The always-on surface as the working tree has it."""
    def read(path: str) -> str | None:
        target = root / path
        return (target.read_text(encoding="utf-8", errors="replace")
                if target.is_file() else None)

    cells = sorted(
        p.relative_to(root).as_posix() for p in (root / "skills").glob("*/SKILL.md")
    ) if (root / "skills").is_dir() else []
    data = _always_on(read, [c for c in cells if is_cell_path(c)])
    return {
        "name": "always-on surface",
        "value": (
            f"{data['repo_total']:,} chars here, {data['adopter_total']:,} "
            f"from this practice for an adopter "
            f"— doctrine {data['doctrine']:,} + charter body {data['charter']:,} + "
            f"{data['cells']} cell name/description {data['roster']:,}"
        ),
        "basis": (
            "decoded UTF-8 characters; AGENTS.md and CLAUDE.md whole, the "
            "charter below its frontmatter, and each cell's name plus "
            "description as check_cell_frontmatter reads them; an adopter's "
            "total omits both doctrine files, which reach a plugin cache as "
            "inert files and are never loaded, and counts only what this "
            "practice contributes to their always-on surface; working tree"
        ),
        "data": data,
    }


def always_on_at(root: Path, ref: str) -> int:
    """The repo-side always-on total at another revision, for a delta.

    Reads blobs rather than checking anything out, so it is safe to call from
    a working tree somebody is using. Raises rather than guessing when the ref
    or a path is unreadable -- a delta against a base that could not be read is
    worse than no delta, and the caller states the absence.

    The composition it applies is the working tree's, from `_always_on`, so
    the two halves of a delta cannot drift apart.
    """
    import subprocess

    def read(path: str) -> str | None:
        out = subprocess.run(
            ["git", "-C", str(root), "show", f"{ref}:{path}"],
            capture_output=True,
        )
        if out.returncode != 0:
            return None
        # Universal newlines, matching what read_text gives the other reader
        # and what every guard here measures: a tree stored with CRLF would
        # otherwise count larger through git than through the filesystem, and
        # the delta between them would report a change nobody made.
        text = out.stdout.decode("utf-8", errors="replace")
        return text.replace("\r\n", "\n").replace("\r", "\n")

    listing = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", "--name-only", ref, "skills/"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    return _always_on(read, [p for p in listing if is_cell_path(p)])["repo_total"]


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
        figures.append(engine.figure_cell(root, cell, budget))
        figures.append(figure_cell_description(root, cell))
    return figures


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(
        prog="figures.py",
        description="This repo's write-up figures, each with its basis inline.",
    )
    parser.add_argument("--base", metavar="REF",
                        help="also emit the governing-prose delta against REF")
    parser.add_argument("--cell", metavar="PATH",
                        help="also emit a cell's body and description figures")
    parser.add_argument("--cell-budget", metavar="N", type=int,
                        help="the body budget --cell is measured against")
    parser.add_argument("--json", action="store_true",
                        help="emit JSON instead of markdown")
    args = parser.parse_args(argv)
    engine.utf8_stdio()
    figures = build_figures(ROOT, args.base, args.cell, args.cell_budget)
    stamp = engine.tree_stamp(ROOT)
    command = ("python tools/figures.py " + shlex.join(argv)).rstrip()
    render = engine.render_json if args.json else engine.render_markdown
    print(render(stamp, command, figures))
    return 0


if __name__ == "__main__":
    sys.exit(main())

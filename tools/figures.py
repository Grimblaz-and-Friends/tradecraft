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

Always emitted: the suite figure (pytest over tools/tests and skills), the
AGENTS.md size/headroom figure, the charter's body against its budget, and
the census. With --base, the governing-prose delta (AGENTS.md, CLAUDE.md,
and the .md files under skills/) against that ref. With --cell, that cell's
body and description figures. Both the delta's base and a cell's budget are
caller decisions neither script will default.
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


def figure_always_on(root: Path) -> dict:
    """Everything a session reads before it does anything, for both audiences.

    Three surfaces, and no invocation reported their sum -- so every write-up
    about growth measured one file and read as a reduction while the total
    rose. It rose through two restructures that were each meant to shrink it.

    The two audiences are not the same set, and conflating them is the error
    this figure exists to stop: a plugin's root AGENTS.md and CLAUDE.md land
    in a consumer's cache as inert files and are never loaded, so an adopter
    reads the charter and the roster's descriptions and nothing else, while
    this repository reads its own doctrine on top.
    """
    cells = sorted((root / "skills").glob("*/SKILL.md")) if (root / "skills").is_dir() else []
    roster = 0
    for cell in cells:
        fields = lint._frontmatter_fields(cell.read_text(encoding="utf-8", errors="replace")) or {}
        roster += len(fields.get("name", "")) + len(fields.get("description", ""))
    agents = root / "AGENTS.md"
    doctrine = len(agents.read_text(encoding="utf-8", errors="replace")) if agents.is_file() else 0
    charter_path = root / lint.CHARTER
    charter = len(lint._frontmatterless(
        charter_path.read_text(encoding="utf-8", errors="replace")
    )) if charter_path.is_file() else 0
    adopter = charter + roster
    return {
        "name": "always-on surface",
        "value": (
            f"{doctrine + adopter:,} chars here, {adopter:,} for an adopter "
            f"— doctrine {doctrine:,} + charter body {charter:,} + "
            f"{len(cells)} cell name/description {roster:,}"
        ),
        "basis": (
            "decoded UTF-8 characters; AGENTS.md whole, the charter below its "
            "frontmatter, and each cell's name plus description as "
            "check_cell_frontmatter reads them; an adopter's total omits "
            "AGENTS.md, which reaches a plugin cache as an inert file and is "
            "never loaded; working tree"
        ),
        "data": {
            "doctrine": doctrine, "charter": charter, "roster": roster,
            "cells": len(cells), "repo_total": doctrine + adopter,
            "adopter_total": adopter,
        },
    }


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

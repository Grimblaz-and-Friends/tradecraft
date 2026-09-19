#!/usr/bin/env python3
"""Derive this repository's suite and decision-log figures.

The general engine ships in the authoring cell. This wrapper adds the
decision-log census by reusing the repository lint's own reference parser and
keeps the pointer-reach report used by that lint. Every rendered figure names
its basis and the tree on which it ran.

Usage: python tools/figures.py [--base REF] [--json]
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
sys.path.insert(0, str(ROOT / "lib"))
from winio import utf8_stdio  # noqa: E402
import lint  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "authoring_figures", ROOT / "skills" / "authoring" / "scripts" / "figures.py"
)
engine = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(engine)

SUITE_PATHS = ["tools/tests", "skills"]
PROSE_PATHS = ["AGENTS.md", "CLAUDE.md", "charter", "skills", "docs/cells"]
PROSE_SUFFIXES = [".md"]


def figure_census(root: Path) -> dict:
    """Unresolved, unpinned decision-log references with records ignored."""
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


def cell_prose(root: Path, rel_path: str) -> dict:
    """A cell's body and markdown depth, using the authoring engine's strip."""
    target = root / rel_path
    body = len(engine.frontmatterless(
        target.read_text(encoding="utf-8", errors="replace")
    ))
    depth = sorted(
        path for path in target.parent.rglob("*.md")
        if path.resolve() != target.resolve()
    )
    depth_chars = sum(
        len(path.read_text(encoding="utf-8", errors="replace")) for path in depth
    )
    return {
        "path": rel_path,
        "body": body,
        "depth_files": len(depth),
        "depth": depth_chars,
        "total": body + depth_chars,
    }


REACH_BASIS = (
    "decoded UTF-8 characters; each cell's SKILL.md below its frontmatter "
    "plus every other .md in the cell whole; a row is its own cell's prose "
    "plus every cell it reaches, each counted once however many pointers "
    "lead to it; no cell reaches the charter, every session having loaded it "
    "already"
)


def pointer_reach_rows(root: Path) -> list[dict]:
    """Every cell and the prose reached by following its pointers."""
    graph = lint.cell_pointer_graph(root)
    sources = lint.cell_sources(root)
    own = {
        name: cell_prose(root, f"{source}/{name}/{lint.CELL_FILE}")["total"]
        for name, source in sources.items()
    }
    rows = []
    for name in sources:
        reached = {name}
        queue = [name]
        while queue:
            for edge in graph.get(queue.pop(), []):
                if edge.target not in reached and edge.target in own:
                    reached.add(edge.target)
                    queue.append(edge.target)
        rows.append({
            "name": name,
            "own": own[name],
            "reach": sum(own[reached_name] for reached_name in reached),
            "reached": sorted(reached - {name}),
        })
    rows.sort(key=lambda row: (-row["reach"], row["name"]))
    return rows


def pointer_reach_block(rows: list[dict]) -> str:
    """Render pointer-reach rows in their derived order."""
    width = max((len(row["name"]) for row in rows), default=0)
    lines = []
    for row in rows:
        reached = (
            "reaches " + ", ".join(row["reached"])
            if row["reached"] else "points at nothing; its own prose only"
        )
        lines.append(f"  {row['name']:<{width}}  {row['reach']:>7,}  {reached}")
    return chr(10).join(lines)


def build_figures(root: Path, base: str | None) -> list[dict]:
    figures = [
        engine.figure_tests(root, SUITE_PATHS),
        figure_census(root),
    ]
    if base:
        figures.append(engine.figure_delta(root, base, PROSE_PATHS, PROSE_SUFFIXES))
    return figures


def body_strip_scan(repo: Path) -> list[str]:
    """What the body-strip guard finds in its excluded test corpus."""
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
    parser.add_argument("--json", action="store_true",
                        help="emit JSON instead of markdown")
    parser.add_argument("--body-strip-scan", action="store_true",
                        help="list hand-rolled frontmatter strips in tests")
    args = parser.parse_args(argv)
    if args.body_strip_scan:
        hits = body_strip_scan(ROOT)
        for hit in hits:
            print(hit)
        print(f"{len(hits)} hand-rolled strip(s) in the excluded test corpus")
        return 0
    figures = build_figures(ROOT, args.base)
    stamp = engine.tree_stamp(ROOT)
    command = ("python tools/figures.py " + shlex.join(argv)).rstrip()
    render = engine.render_json if args.json else engine.render_markdown
    print(render(stamp, command, figures))
    return 0


if __name__ == "__main__":
    sys.exit(main())

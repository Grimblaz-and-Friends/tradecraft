#!/usr/bin/env python3
"""Derive a write-up's recurring figures, each inseparable from its basis.

Hand-derived figures are wrong at a measurable rate: across two consecutive
changes in this practice's home repository, every figure carried forward or
stated from memory was wrong at least once, and every figure computed at the
moment of writing was right. The authoring standard already requires a document
carrying counts to carry the query that produced them; this script is that
rule's mechanism. Each figure prints with what was measured, in what units,
against which tree — so a write-up pastes the block instead of improvising the
arithmetic, and a later reader can re-run the derivation instead of inheriting
the number.

Figures, each requested explicitly:

  --tests PATH [PATH ...]      suite summary from `python -m pytest <paths> -q`,
                               reported verbatim (failures included — a figure
                               that hides red is worse than none)
  --doc PATH --budget N        the file's size in decoded UTF-8 characters and
                               its headroom against the budget. The measure is a
                               universal-newline text read (CRLF counts as one
                               character), because that is the measure a text-
                               mode budget guard applies; the byte count on disk
                               is a different number and stating it as this one
                               is how budget figures go wrong.
  --base REF --delta PATH ...  net character change over the named paths between
                               REF and the working tree: raw base blobs vs
                               working-tree bytes, decoded UTF-8, CRLF
                               normalized to LF. The base is required, never
                               defaulted: a silently chosen basis is how delta
                               figures go wrong. --delta-suffix limits the
                               enumeration (e.g. `.md`).

Output is markdown for pasting (default) or --json for tooling. Every mode
stamps the tree the figures were derived from (commit, and whether the working
tree was dirty) and the exact invocation, so the block carries its own query.

A figure whose inputs are incomplete is a loud refusal (non-zero exit), never
a guess: --doc without --budget, --delta without --base (or the reverse), or no
figure requested at all.

Usage, from the repository the figures describe (or with --repo):

    python figures.py --tests tests --doc NOTES.md --budget 8000
    python figures.py --base origin/main --delta NOTES.md src --delta-suffix .md
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# The pytest -q summary line: counts and outcomes, with the trailing duration
# ("in 1.23s") dropped — a duration is not a figure a write-up states, and
# keeping it would make every derived block differ from every re-derivation.
PYTEST_SUMMARY = re.compile(
    r"^(?P<counts>\d+ [a-z]+(?:, \d+ [a-z]+)*)(?: in [\d.]+m?s(?: .*)?)?$"
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False
    )


def _decoded(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _normalized_chars(data: bytes) -> int:
    """Decoded UTF-8 characters with CRLF normalized to LF — one fixed basis,
    so a file's count cannot depend on which OS checked it out."""
    return len(_decoded(data).replace("\r\n", "\n"))


def tree_stamp(repo: Path) -> dict:
    """The tree the figures describe: commit, and whether anything is uncommitted.
    A figure without its tree is a figure a later reader cannot re-derive."""
    head = _git(repo, "rev-parse", "--short", "HEAD")
    if head.returncode != 0:
        return {"commit": None, "dirty": None}
    status = _git(repo, "status", "--porcelain")
    return {
        "commit": _decoded(head.stdout).strip(),
        "dirty": bool(_decoded(status.stdout).strip()),
    }


def parse_pytest_summary(output: str) -> str:
    """The last summary-shaped line of `pytest -q` output, duration dropped.
    If no line parses, the tail line verbatim — a strange suite reports
    strangely rather than silently."""
    lines = [ln.strip().strip("=").strip() for ln in output.splitlines() if ln.strip()]
    for line in reversed(lines):
        match = PYTEST_SUMMARY.match(line)
        if match:
            return match.group("counts")
    return lines[-1] if lines else "no output"


def figure_tests(repo: Path, paths: list[str]) -> dict:
    command = f"python -m pytest {' '.join(paths)} -q"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *paths, "-q"],
        cwd=str(repo), capture_output=True, check=False,
    )
    summary = parse_pytest_summary(_decoded(proc.stdout))
    return {
        "name": "suite",
        "value": summary,
        "basis": f"`{command}`, exit {proc.returncode}",
        "data": {"summary": summary, "exit": proc.returncode, "command": command},
    }


def figure_doc(repo: Path, path: str, budget: int) -> dict:
    target = repo / path
    # Universal-newline text read: the measure a text-mode budget guard
    # applies. Not the byte count, and not the LF-normalized count above —
    # naming which of the three this is, is the figure's whole job.
    chars = len(target.read_text(encoding="utf-8", errors="replace"))
    headroom = budget - chars
    return {
        "name": f"doc `{path}`",
        "value": f"{chars:,} of {budget:,} chars, headroom {headroom:,}",
        "basis": (
            "decoded UTF-8 characters, universal-newline read "
            "(CRLF counts as one character), working tree"
        ),
        "data": {"path": path, "chars": chars, "budget": budget, "headroom": headroom},
    }


def _base_files(repo: Path, base: str, paths: list[str]) -> list[str]:
    proc = _git(repo, "ls-tree", "-r", "--name-only", base, "--", *paths)
    if proc.returncode != 0:
        raise SystemExit(
            f"figures: cannot enumerate '{base}' — {_decoded(proc.stderr).strip()}"
        )
    return [ln for ln in _decoded(proc.stdout).splitlines() if ln]


def _worktree_files(repo: Path, paths: list[str]) -> list[str]:
    # Tracked plus untracked-unignored, so a file the change adds counts
    # before it is committed; a path listed but deleted from the tree is
    # skipped when read.
    proc = _git(
        repo, "ls-files", "--cached", "--others", "--exclude-standard", "--", *paths
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"figures: cannot enumerate the working tree — "
            f"{_decoded(proc.stderr).strip()}"
        )
    return [ln for ln in _decoded(proc.stdout).splitlines() if ln]


def figure_delta(
    repo: Path, base: str, paths: list[str], suffixes: list[str] | None = None
) -> dict:
    def kept(name: str) -> bool:
        return not suffixes or any(name.endswith(sfx) for sfx in suffixes)

    base_total = 0
    for name in _base_files(repo, base, paths):
        if not kept(name):
            continue
        blob = _git(repo, "cat-file", "blob", f"{base}:{name}")
        if blob.returncode != 0:
            raise SystemExit(
                f"figures: cannot read '{base}:{name}' — "
                f"{_decoded(blob.stderr).strip()}"
            )
        base_total += _normalized_chars(blob.stdout)

    current_total = 0
    for name in _worktree_files(repo, paths):
        target = repo / name
        if kept(name) and target.is_file():
            current_total += _normalized_chars(target.read_bytes())

    delta = current_total - base_total
    suffix_note = f", {'/'.join(suffixes)} files only" if suffixes else ""
    return {
        "name": f"prose delta vs `{base}`",
        "value": f"{delta:+,} chars (base {base_total:,} → current {current_total:,})",
        "basis": (
            f"raw base blobs vs working-tree bytes, decoded UTF-8, CRLF "
            f"normalized to LF{suffix_note}, over: {', '.join(paths)}"
        ),
        "data": {
            "base": base, "paths": paths, "suffixes": suffixes or [],
            "base_chars": base_total, "current_chars": current_total, "delta": delta,
        },
    }


def render_markdown(stamp: dict, command: str, figures: list[dict]) -> str:
    if stamp["commit"] is None:
        tree = "no git tree identified"
    else:
        tree = f"tree `{stamp['commit']}`" + (" (dirty)" if stamp["dirty"] else " (clean)")
    lines = [f"**Figures** — {tree}, derived by `{command}`"]
    for fig in figures:
        lines.append(f"- {fig['name']}: **{fig['value']}** — {fig['basis']}")
    return "\n".join(lines)


def render_json(stamp: dict, command: str, figures: list[dict]) -> str:
    return json.dumps(
        {"tree": stamp, "command": command, "figures": figures}, indent=2
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="figures.py",
        description="Derive a write-up's figures, each with its basis inline.",
    )
    parser.add_argument("--repo", default=".", help="repository root (default: cwd)")
    parser.add_argument("--tests", nargs="+", metavar="PATH",
                        help="test paths for the suite figure")
    parser.add_argument("--doc", metavar="PATH",
                        help="document for the size/headroom figure")
    parser.add_argument("--budget", type=int, metavar="N",
                        help="character budget for --doc (required with it)")
    parser.add_argument("--base", metavar="REF",
                        help="base ref for --delta (required with it, never defaulted)")
    parser.add_argument("--delta", nargs="+", metavar="PATH",
                        help="paths for the prose-delta figure")
    parser.add_argument("--delta-suffix", nargs="+", metavar=".EXT",
                        help="limit --delta to files with these suffixes")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    return parser


def figures_from_args(repo: Path, args: argparse.Namespace) -> list[dict]:
    if (args.doc is None) != (args.budget is None):
        raise SystemExit("figures: --doc and --budget travel together; supply both")
    if (args.delta is None) != (args.base is None):
        raise SystemExit(
            "figures: --delta needs --base and --base needs --delta — "
            "the base is a caller decision, never defaulted"
        )
    if args.delta_suffix and not args.delta:
        raise SystemExit("figures: --delta-suffix without --delta does nothing")
    figures: list[dict] = []
    if args.tests:
        figures.append(figure_tests(repo, args.tests))
    if args.doc:
        figures.append(figure_doc(repo, args.doc, args.budget))
    if args.delta:
        figures.append(figure_delta(repo, args.base, args.delta, args.delta_suffix))
    if not figures:
        raise SystemExit(
            "figures: no figure requested — give --tests, --doc/--budget, "
            "or --base/--delta"
        )
    return figures


def utf8_stdout() -> None:
    """The rendered block is UTF-8; a cp1252 console must not crash the
    derivation it exists to make cheap."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(argv)
    utf8_stdout()
    repo = Path(args.repo).resolve()
    figures = figures_from_args(repo, args)
    stamp = tree_stamp(repo)
    command = "python figures.py " + " ".join(argv)
    render = render_json if args.json else render_markdown
    print(render(stamp, command, figures))
    return 0


if __name__ == "__main__":
    sys.exit(main())

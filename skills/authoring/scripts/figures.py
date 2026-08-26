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

Usage, from anywhere inside the repository the figures describe (or with
--repo; either way paths resolve from the repository's root):

    python path/to/figures.py --tests tests --doc NOTES.md --budget 8000
    python path/to/figures.py --base origin/main --delta NOTES.md src --delta-suffix .md

The emitted block stamps the invocation that actually ran — the script's real
path, arguments shell-quoted — so re-running the stamped line re-derives the
figures.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

# Shared code lives in lib/, which ships beside this cell, so the import
# resolves in a source checkout and an installed plugin alike -- against
# this file's own directory, never the working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from winio import utf8_stdio  # noqa: E402

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
    If no line parses, the tail line — duration still dropped, so no block's
    value differs across re-derivations — a strange suite reports strangely
    rather than silently."""
    lines = [ln.strip().strip("=").strip() for ln in output.splitlines() if ln.strip()]
    for line in reversed(lines):
        match = PYTEST_SUMMARY.match(line)
        if match:
            return match.group("counts")
    if not lines:
        return "no output"
    return re.sub(r"\s+in\s+[\d.]+m?s\b.*$", "", lines[-1])


def figure_tests(repo: Path, paths: list[str]) -> dict:
    command = f"python -m pytest {' '.join(paths)} -q"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *paths, "-q"],
        cwd=str(repo), capture_output=True, check=False,
    )
    summary = parse_pytest_summary(_decoded(proc.stdout))
    # A red suite is reported verbatim — hiding it would be worse than the
    # failure — but a run that measured nothing is an input error, not a
    # figure: pytest exits 4 (usage error, e.g. a mistyped path) and 5 (no
    # tests collected) are refusals, or a typo pastes as a derived figure.
    if proc.returncode in (4, 5):
        raise SystemExit(
            f"figures: pytest measured nothing over '{' '.join(paths)}' "
            f"(exit {proc.returncode}: {summary}) -- check the test paths"
        )
    return {
        "name": "suite",
        "value": summary,
        "basis": f"`{command}`, exit {proc.returncode}",
        "data": {"summary": summary, "exit": proc.returncode, "command": command},
    }


def figure_doc(repo: Path, path: str, budget: int) -> dict:
    target = repo / path
    if not target.is_file():
        raise SystemExit(
            f"figures: --doc '{path}' is not a readable file under {repo}"
        )
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


def frontmatterless(text: str) -> str:
    """Text with a leading YAML frontmatter block removed, if there is one.

    A cell's frontmatter is addressed to the runtime's skill index, not to a
    reader, and a budget on a cell's rules should not be spent by an edit to
    its description -- so the two are measured apart. Public because a guard
    enforcing that budget has to measure the same thing this figure reports;
    a figure that disagrees with the guard judging it is what this whole
    script exists to prevent.
    """
    if not text.startswith("---"):
        return text
    end = text.find(chr(10) + "---", 3)
    return text if end == -1 else text[end + 4:].lstrip(chr(10))


def figure_cell(repo: Path, path: str, budget: int) -> dict:
    """A cell's body against its budget -- the file without its frontmatter.

    `figure_doc` measures a whole file, which is right for a plain document
    and wrong for a cell. Written because a change shedding a cell's depth
    stated a body figure no invocation of this script could produce, so the
    number was derived by hand in the change that ships "derive figures here
    rather than by hand". The budget is the caller's: this script knows of no
    ceiling, and inventing one would be the silent basis it refuses.
    """
    target = repo / path
    if not target.is_file():
        raise SystemExit(
            f"figures: --cell '{path}' is not a readable file under {repo}"
        )
    chars = len(frontmatterless(target.read_text(encoding="utf-8", errors="replace")))
    headroom = budget - chars
    return {
        "name": f"doc `{path}` (body)",
        "value": f"{chars:,} of {budget:,} chars, headroom {headroom:,}",
        "basis": (
            "decoded UTF-8 characters below the frontmatter, universal-newline "
            "read (CRLF counts as one character), working tree; the budget is "
            "the caller's"
        ),
        "data": {"path": path, "chars": chars, "budget": budget, "headroom": headroom},
    }


def _base_files(repo: Path, base: str, paths: list[str]) -> list[str]:
    # NUL-delimited: with git's default core.quotePath, a non-ASCII filename
    # comes back C-escaped in newline output, silently missing every suffix
    # filter — an undercounted delta that reproduces on re-run.
    proc = _git(repo, "ls-tree", "-r", "--name-only", "-z", base, "--", *paths)
    if proc.returncode != 0:
        raise SystemExit(
            f"figures: cannot enumerate '{base}' -- {_decoded(proc.stderr).strip()}"
        )
    return [name for name in _decoded(proc.stdout).split("\0") if name]


def _worktree_files(repo: Path, paths: list[str]) -> list[str]:
    # Tracked plus untracked-unignored, so a file the change adds counts
    # before it is committed; a path listed but deleted from the tree is
    # skipped when read. NUL-delimited for the same reason as the base side.
    proc = _git(
        repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z",
        "--", *paths
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"figures: cannot enumerate the working tree -- "
            f"{_decoded(proc.stderr).strip()}"
        )
    return [name for name in _decoded(proc.stdout).split("\0") if name]


def figure_delta(
    repo: Path, base: str, paths: list[str], suffixes: list[str] | None = None
) -> dict:
    def kept(name: str) -> bool:
        return not suffixes or any(name.endswith(sfx) for sfx in suffixes)

    base_names = [n for n in _base_files(repo, base, paths) if kept(n)]
    current_names = [
        n for n in _worktree_files(repo, paths) if kept(n) and (repo / n).is_file()
    ]
    # Empty on ONE side is a lawful figure (a directory the change adds or
    # deletes); empty on both is a typo'd path or suffix, and a confident
    # +0 from it would be a wrong figure that reproduces on re-run.
    if not base_names and not current_names:
        raise SystemExit(
            f"figures: --delta {' '.join(paths)} matched no files on either "
            f"side -- check the paths and suffixes"
        )

    base_total = 0
    for name in base_names:
        blob = _git(repo, "cat-file", "blob", f"{base}:{name}")
        if blob.returncode != 0:
            raise SystemExit(
                f"figures: cannot read '{base}:{name}' -- "
                f"{_decoded(blob.stderr).strip()}"
            )
        base_total += _normalized_chars(blob.stdout)

    current_total = sum(
        _normalized_chars((repo / name).read_bytes()) for name in current_names
    )

    delta = current_total - base_total
    suffix_note = f", {'/'.join(suffixes)} files only" if suffixes else ""
    return {
        "name": f"prose delta vs `{base}`",
        "value": f"{delta:+,} chars (base {base_total:,} -> current {current_total:,})",
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
    lines = [f"**Figures** -- {tree}, derived by `{command}`"]
    for fig in figures:
        lines.append(f"- {fig['name']}: **{fig['value']}** -- {fig['basis']}")
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
    parser.add_argument("--cell", metavar="PATH",
                        help="a cell whose body is measured against --budget")
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
    if args.doc and args.cell:
        raise SystemExit(
            "figures: --doc and --cell measure the same file two ways; pick one"
        )
    if ((args.doc is None and args.cell is None) != (args.budget is None)):
        raise SystemExit(
            "figures: --doc or --cell travels with --budget; supply both"
        )
    if (args.delta is None) != (args.base is None):
        raise SystemExit(
            "figures: --delta needs --base and --base needs --delta -- "
            "the base is a caller decision, never defaulted"
        )
    if args.delta_suffix and not args.delta:
        raise SystemExit("figures: --delta-suffix without --delta does nothing")
    figures: list[dict] = []
    if args.tests:
        figures.append(figure_tests(repo, args.tests))
    if args.doc:
        figures.append(figure_doc(repo, args.doc, args.budget))
    if args.cell:
        figures.append(figure_cell(repo, args.cell, args.budget))
    if args.delta:
        figures.append(figure_delta(repo, args.base, args.delta, args.delta_suffix))
    if not figures:
        raise SystemExit(
            "figures: no figure requested -- give --tests, --doc/--budget, "
            "--cell/--budget, or --base/--delta"
        )
    return figures


def repo_root(path: Path) -> Path:
    """The repository root containing `path`. Every path this script takes or
    emits is root-relative; resolving the root once is what keeps a run from a
    subdirectory from enumerating one set of names and reading another."""
    proc = _git(path, "rev-parse", "--show-toplevel")
    if proc.returncode == 0:
        return Path(_decoded(proc.stdout).strip())
    return path


def stamped_command(repo: Path, argv: list[str]) -> str:
    """The invocation that actually ran, re-runnable verbatim: the script's
    real path (repo-root-relative where it lives inside the repo), arguments
    shell-quoted. A stamp needing path reconstruction or re-quoting is a query
    the block does not actually carry."""
    script = Path(__file__).resolve()
    try:
        shown = script.relative_to(repo).as_posix()
    except ValueError:
        shown = script.as_posix()
    return "python " + shlex.join([shown, *argv])


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    argv = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(argv)
    repo = repo_root(Path(args.repo).resolve())
    figures = figures_from_args(repo, args)
    stamp = tree_stamp(repo)
    render = render_json if args.json else render_markdown
    print(render(stamp, stamped_command(repo, argv), figures))
    return 0


if __name__ == "__main__":
    sys.exit(main())

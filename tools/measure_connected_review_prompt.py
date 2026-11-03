#!/usr/bin/env python3
"""Reconstruct the connected reviewer's fitting and rejected budget references."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import connected_review as cr  # noqa: E402
from winio import utf8_stdio  # noqa: E402

REFERENCES = (
    ("Grimblaz-and-Friends/tradecraft", "73a58990c455db618882fea5944bcc645ca4a8e4", "f00669abddae448d2775e363454c4bf7fc9b3330"),
    ("Grimblaz-and-Friends/Countdown-Clash", "47816a494ac6cf46959ea1b148196a02716aaec0", "8b15ae6eb0e9816c391b7c5ac098a274806afcca"),
    ("Grimblaz-and-Friends/Countdown-Clash", "47816a494ac6cf46959ea1b148196a02716aaec0", "63dd6a83646166cc60e2f6b99df33ecf2c839e69"),
)
# The heads the over-budget skip held before summaries (#902): Daemon #107, Verra #557
# and Verra #543, each at its skip's run head against the pull request's base.
SUMMARY_REFERENCES = (
    ("Grimblaz-and-Friends/Daemon", "b3250f7bd934e9b7d570fa421b10dac067181904", "27192a8c9ccc5acb8b4a508dde52791e790b0bd1"),
    ("Grimblaz-and-Friends/Organizations-of-Verra", "7b474cc271826fa747b42718f6a41078b7846bdb", "9d2d777bebc0978a2a98a37acce3c20d54020b28"),
    ("Grimblaz-and-Friends/Organizations-of-Verra", "72fa40d8cf14b5c1259023db9e32d14d0c102899", "6f848d18025ec98d82bb7a99584fb095390d58a0"),
)


def _blob_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()


def folder_blob_matches(
    repository: str, base: str, head: str, raw: bytes, summarised: list[dict[str, object]],
) -> dict[str, object]:
    """Compare each rebuilt file's git blob hash with the merge base's tree entry."""
    compare = cr.gh_json(f"repos/{repository}/compare/{base}...{head}?per_page=1")
    merge_base = compare["merge_base_commit"]["sha"]
    tree = cr.gh_json(f"repos/{repository}/git/trees/{merge_base}?recursive=1")
    blobs = {entry["path"]: entry["sha"] for entry in tree["tree"] if entry.get("type") == "blob"}
    with tempfile.TemporaryDirectory(prefix="connected-review-measure-") as temporary:
        folder = Path(temporary) / cr.DELETED_FOLDER_NAME
        cr.write_deleted_files(raw.decode("utf-8", errors="replace"), summarised, folder)
        mismatched = [
            entry["path"] for entry in summarised
            if blobs.get(entry["path"]) != _blob_sha(folder.joinpath(*str(entry["path"]).split("/")).read_bytes())
        ]
    return {
        "merge_base": merge_base, "tree_truncated": bool(tree.get("truncated")),
        "folder_files": len(summarised), "folder_blob_matches": len(summarised) - len(mismatched),
        "folder_blob_mismatches": mismatched,
    }


def measure(repository: str, base: str, head: str, *, check_folder: bool) -> dict[str, object]:
    instructions = (ROOT / "skills/connected-review/references/finder.md").read_text(encoding="utf-8")
    snapshot = Path("C:/review-prompt-budget/reference/snapshot")
    readable = snapshot.with_name(cr.DELETED_FOLDER_NAME)
    name, focus = cr.FINDER_PASSES[0]
    instructions += f"\n\nIndependent finder pass: {name}. " + focus + f" Return at most {cr.MAX_FINDER_CANDIDATES_PER_PASS} candidates."
    raw = cr.gh_bytes(f"repos/{repository}/compare/{base}...{head}", accept="application/vnd.github.v3.diff")
    with io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8", errors="replace") as stream:
        diff = stream.read()
    rules = cr.repository_review_rules(repository, base)
    original = cr._pass_prompt(instructions, snapshot, diff, rules)
    retained, excluded, _lines = cr.select_coverage(diff, cr.base_attribute_material(repository, base, cr.coverage_paths(diff)))
    selected = cr._pass_prompt(instructions, snapshot, retained, rules, exclusions=excluded)
    summarised_diff, summarised = cr.summarise_deleted_files(retained)
    summarised_bytes = len(cr.pass_input_bytes(cr._pass_prompt(
        instructions, snapshot, summarised_diff, rules, exclusions=excluded,
        summarised=summarised, readable=readable,
    ))) if summarised else None
    record: dict[str, object] = {
        "repository": repository, "base": base, "head": head, "snapshot_path": str(snapshot),
        "diff_utf8_bytes": len(diff.encode("utf-8")),
        "unfiltered_finder_stdin_utf8_bytes": len(cr.pass_input_bytes(original)),
        "selected_finder_stdin_utf8_bytes": len(cr.pass_input_bytes(selected)),
        "summarised_finder_stdin_utf8_bytes": summarised_bytes,
        "summarised_files": len(summarised),
        "budget_utf8_bytes": cr.MAX_FINDER_PROMPT_BYTES, "excluded_files": excluded,
    }
    if check_folder and summarised:
        record.update(folder_blob_matches(repository, base, head, raw, summarised))
    return record


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="Reconstruct the connected reviewer's budget references")
    cli.add_argument(
        "--references", choices=("budget", "summary", "all"), default="all",
        help="budget: the fitting and rejected references; summary: the three skipped heads, "
        "with each rebuilt deleted file compared to its merge-base blob",
    )
    return cli


def main(argv: Iterable[str] | None = None) -> int:
    utf8_stdio()
    args = parser().parse_args(argv)
    chosen = []
    if args.references in ("budget", "all"):
        chosen.extend((reference, False) for reference in REFERENCES)
    if args.references in ("summary", "all"):
        chosen.extend((reference, True) for reference in SUMMARY_REFERENCES)
    for (repository, base, head), check_folder in chosen:
        print(json.dumps(measure(repository, base, head, check_folder=check_folder), ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

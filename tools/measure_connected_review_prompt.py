#!/usr/bin/env python3
"""Reconstruct the connected reviewer's fitting and rejected budget references."""
from __future__ import annotations

import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import connected_review as cr  # noqa: E402
from winio import utf8_stdio  # noqa: E402

REFERENCES = (
    ("Grimblaz-and-Friends/tradecraft", "73a58990c455db618882fea5944bcc645ca4a8e4", "f00669abddae448d2775e363454c4bf7fc9b3330"),
    ("Grimblaz-and-Friends/Countdown-Clash", "47816a494ac6cf46959ea1b148196a02716aaec0", "8b15ae6eb0e9816c391b7c5ac098a274806afcca"),
    ("Grimblaz-and-Friends/Countdown-Clash", "47816a494ac6cf46959ea1b148196a02716aaec0", "63dd6a83646166cc60e2f6b99df33ecf2c839e69"),
)


def main() -> int:
    utf8_stdio()
    instructions = (ROOT / "skills/connected-review/references/finder.md").read_text(encoding="utf-8")
    snapshot = Path("C:/review-prompt-budget/reference/snapshot")
    name, focus = cr.FINDER_PASSES[0]
    instructions += f"\n\nIndependent finder pass: {name}. " + focus + f" Return at most {cr.MAX_FINDER_CANDIDATES_PER_PASS} candidates."
    for repository, base, head in REFERENCES:
        raw = cr.gh_bytes(f"repos/{repository}/compare/{base}...{head}", accept="application/vnd.github.v3.diff")
        with io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8", errors="replace") as stream:
            diff = stream.read()
        rules = cr.repository_review_rules(repository, base)
        original = cr._pass_prompt(instructions, snapshot, diff, rules)
        retained, excluded, _lines = cr.select_coverage(diff, cr.base_attribute_material(repository, base, cr.coverage_paths(diff)))
        selected = cr._pass_prompt(instructions, snapshot, retained, rules, exclusions=excluded)
        print(json.dumps({
            "repository": repository, "base": base, "head": head, "snapshot_path": str(snapshot),
            "diff_utf8_bytes": len(diff.encode("utf-8")),
            "unfiltered_finder_stdin_utf8_bytes": len(cr.pass_input_bytes(original)),
            "selected_finder_stdin_utf8_bytes": len(cr.pass_input_bytes(selected)),
            "budget_utf8_bytes": cr.MAX_FINDER_PROMPT_BYTES, "excluded_files": excluded,
        }, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

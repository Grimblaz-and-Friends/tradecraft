#!/usr/bin/env python3
"""tradecraft packaging lint — the constitution's enforcement arm (ADR-004).

Checks, each anchored to the ADR it enforces:

  1. zone wall (ADR-004): no file in the shipped zone may reference the
     repo-only zone (docs/, tools/, .github/). Consumers of the plugin never
     see those paths, so a shipped reference to them is broken on arrival.
  2. sideways deps (ADR-003): no skill may reference another skill. Shared
     code lives only in lib/; composition happens above the cells.
  3. doctrine budget (ADR-003): AGENTS.md stays within budget, and CLAUDE.md
     is a pointer to it, never a fork (ADR-007).

Exit 0 when clean, 1 with findings listed one per line. Run from anywhere:
    python tools/lint.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SHIPPED_DIRS = ("skills", "lib", "commands", "agents", ".claude-plugin")
# A shipped skill needing internal depth uses references/, so a bare
# docs/ or tools/ path inside the shipped zone is always a zone breach.
REPO_ONLY_PATTERN = re.compile(r"(?<![\w/.@-])(docs|tools|\.github)/")
SKILL_REF_PATTERN = re.compile(r"skills/([\w-]+)/")
TEXT_SUFFIXES = {".md", ".py", ".json", ".yml", ".yaml", ".toml", ".txt"}

# ADR-003 "deliberately tiny": the predecessor's root file passed 30k chars in
# eight months because every incident defaulted to a paragraph. The budget is
# the structural counterweight; raising it is an ADR amendment, not an edit.
AGENTS_BUDGET_CHARS = 8_000
POINTER_BUDGET_CHARS = 500


def _text_files(base: Path):
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def check_zone_wall(root: Path) -> list[str]:
    findings = []
    for dirname in SHIPPED_DIRS:
        base = root / dirname
        if not base.is_dir():
            continue
        for path in _text_files(base):
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                match = REPO_ONLY_PATTERN.search(line)
                if match:
                    rel = path.relative_to(root).as_posix()
                    findings.append(
                        f"zone-wall (ADR-004): {rel}:{lineno} references "
                        f"repo-only path '{match.group(0)}'"
                    )
    return findings


def check_sideways_deps(root: Path) -> list[str]:
    findings = []
    skills = root / "skills"
    if not skills.is_dir():
        return findings
    for skill_dir in sorted(p for p in skills.iterdir() if p.is_dir()):
        own = skill_dir.name
        for path in _text_files(skill_dir):
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                for match in SKILL_REF_PATTERN.finditer(line):
                    if match.group(1) != own:
                        rel = path.relative_to(root).as_posix()
                        findings.append(
                            f"sideways-dep (ADR-003): {rel}:{lineno} references "
                            f"skill '{match.group(1)}' from skill '{own}'"
                        )
    return findings


def check_doctrine_budget(root: Path) -> list[str]:
    findings = []
    agents = root / "AGENTS.md"
    if not agents.is_file():
        findings.append("doctrine (ADR-007): AGENTS.md is missing (it is the canonical root file)")
    else:
        size = len(agents.read_text(encoding="utf-8", errors="replace"))
        if size > AGENTS_BUDGET_CHARS:
            findings.append(
                f"doctrine-budget (ADR-003): AGENTS.md is {size} chars, "
                f"budget is {AGENTS_BUDGET_CHARS} — move guidance into the skill it governs"
            )
    pointer = root / "CLAUDE.md"
    if pointer.is_file():
        text = pointer.read_text(encoding="utf-8", errors="replace")
        if len(text) > POINTER_BUDGET_CHARS or "AGENTS.md" not in text:
            findings.append(
                "doctrine-pointer (ADR-007): CLAUDE.md must be a short pointer to "
                "AGENTS.md, never a fork of it"
            )
    return findings


def run(root: Path) -> list[str]:
    return check_zone_wall(root) + check_sideways_deps(root) + check_doctrine_budget(root)


def main() -> int:
    findings = run(ROOT)
    for finding in findings:
        print(finding)
    print(f"lint: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

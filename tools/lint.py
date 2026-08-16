#!/usr/bin/env python3
"""tradecraft packaging lint — the constitution's enforcement arm (ADR-004).

Checks, each anchored to the ADR it enforces:

  1. zone wall (ADR-004): no file in the shipped zone may reference the
     repo-only zone (docs/, tools/, .github/) by any path form — rooted,
     relative (../ or ./), backslashed, or case-shifted. Full web URLs are
     lawful: they resolve for consumers; repo paths do not.
  2. sideways deps (ADR-003): no skill may reference another skill by path
     (rooted or relative), and lib/ may not reference any skill (deps point
     down). Name-form coupling ("load the beta skill") is not machine-
     checkable; it is reviewed, not linted — these checks are the checkable
     subset, not the whole rule.
  3. doctrine (ADR-003/ADR-007): AGENTS.md exists and stays within budget;
     CLAUDE.md exists and is a live @AGENTS.md import — checked by position
     (first non-empty line, unquoted), not substring, because Claude Code
     skips imports inside code spans and loads nothing from an absent file.
  4. ledger (ADR-006): docs/ledger.jsonl, when present, parses and carries
     the required fields per row.

All shipped files are scanned regardless of extension; binary content (NUL
byte in the first 1KB) is skipped. Invoke as `python <repo>/tools/lint.py`
from any cwd — paths resolve from this file's own location.
Exit 0 when clean, 1 with findings listed one per line.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SHIPPED_DIRS = ("skills", "lib", "commands", "agents", ".claude-plugin")
REPO_ONLY_NAMES = {"docs", "tools", ".github"}

# ADR-003 "deliberately tiny": the predecessor's root file passed 30k chars in
# eight months because every incident defaulted to a paragraph. The budget is
# the structural counterweight; raising it is an ADR amendment, not an edit.
AGENTS_BUDGET_CHARS = 8_000
POINTER_BUDGET_CHARS = 500

ROOTED_ZONE = re.compile(r"(docs|tools|\.github)[\\/]", re.IGNORECASE)
ROOTED_SKILL = re.compile(r"skills[\\/]([\w-]+)[\\/]", re.IGNORECASE)
RELATIVE_REF = re.compile(r"(?:\.\.?[\\/])+[\w][\w.\\/\\-]*")
REL_PREFIX_TAIL = re.compile(r"(?:\.\.?[\\/])+$")

LEDGER_FIELDS = {
    "id", "date", "artifact", "severity", "introduced",
    "catchable", "caught", "source", "disposition", "found_by",
}
LEDGER_SEVERITIES = {"high", "medium", "low"}
LEDGER_ARTIFACTS = {
    "constitution", "repo-docs", "skill-prose", "script",
    "lint", "tests", "ci", "packaging",
}
LEDGER_PHASES = {
    "authoring", "authoring-review", "adversarial-review",
    "ci", "post-merge", "consumer",
}
LEDGER_DISPOSITIONS = {"fixed", "reworded", "recorded", "owner-pending"}


def _read_text(path: Path) -> str | None:
    """Return decoded text, or None for binary content (NUL in first 1KB)."""
    data = path.read_bytes()
    if b"\0" in data[:1024]:
        return None
    return data.decode("utf-8", errors="replace")


def _iter_files(base: Path):
    for path in sorted(base.rglob("*")):
        if path.is_file():
            yield path


def _token_before(line: str, start: int) -> str:
    i = start
    while i > 0 and not line[i - 1].isspace():
        i -= 1
    return line[i:start]


def _rooted_zone_hits(line: str):
    """Rooted-form repo-only references: docs/, tools/, .github/ (any case,
    either slash), not preceded by more path (repo/docs/) or a URL host."""
    for match in ROOTED_ZONE.finditer(line):
        before = _token_before(line, match.start())
        if "://" in before:
            continue  # full web URL — lawful, it resolves for consumers
        if REL_PREFIX_TAIL.search(before):
            continue  # relative form — the resolution check owns it
        if before and re.search(r"[\w@\-/\\]$", before):
            continue  # part of a longer path or hyphenated word (foo-docs/)
        yield match.group(0)


def _resolved_relative_targets(root: Path, file_path: Path, line: str):
    """Resolve ../ and ./ references against the file's directory; yield
    (raw_text, parts-relative-to-root) for targets inside the repo."""
    for match in RELATIVE_REF.finditer(line):
        raw = match.group(0)
        candidate = (file_path.parent / raw.replace("\\", "/")).resolve()
        try:
            rel = candidate.relative_to(root.resolve())
        except ValueError:
            continue  # escapes the repo — not this lint's concern
        yield raw, rel.parts


def check_zone_wall(root: Path) -> list[str]:
    findings = []
    for dirname in SHIPPED_DIRS:
        base = root / dirname
        if not base.is_dir():
            continue
        for path in _iter_files(base):
            text = _read_text(path)
            if text is None:
                continue
            rel_file = path.relative_to(root).as_posix()
            for lineno, line in enumerate(text.splitlines(), 1):
                for hit in _rooted_zone_hits(line):
                    findings.append(
                        f"zone-wall (ADR-004): {rel_file}:{lineno} references "
                        f"repo-only path '{hit}'"
                    )
                for raw, parts in _resolved_relative_targets(root, path, line):
                    if parts and parts[0].lower() in REPO_ONLY_NAMES:
                        findings.append(
                            f"zone-wall (ADR-004): {rel_file}:{lineno} relative "
                            f"reference '{raw}' resolves into repo-only '{parts[0]}/'"
                        )
    return findings


def check_sideways_deps(root: Path) -> list[str]:
    findings = []
    skills = root / "skills"
    scan: list[tuple[Path, str | None]] = []
    if skills.is_dir():
        for skill_dir in sorted(p for p in skills.iterdir() if p.is_dir()):
            scan.append((skill_dir, skill_dir.name))
    lib = root / "lib"
    if lib.is_dir():
        scan.append((lib, None))  # lib may reference no skill at all

    for base, own in scan:
        for path in _iter_files(base):
            text = _read_text(path)
            if text is None:
                continue
            rel_file = path.relative_to(root).as_posix()
            for lineno, line in enumerate(text.splitlines(), 1):
                for match in ROOTED_SKILL.finditer(line):
                    target = match.group(1)
                    if own is None or target.lower() != own.lower():
                        findings.append(
                            f"sideways-dep (ADR-003): {rel_file}:{lineno} references "
                            f"skill '{target}'" + (f" from skill '{own}'" if own else " from lib/")
                        )
                for raw, parts in _resolved_relative_targets(root, path, line):
                    if len(parts) >= 2 and parts[0] == "skills":
                        target = parts[1]
                        if own is None or target.lower() != own.lower():
                            findings.append(
                                f"sideways-dep (ADR-003): {rel_file}:{lineno} relative "
                                f"reference '{raw}' resolves into skill '{target}'"
                                + (f" from skill '{own}'" if own else " from lib/")
                            )
    return findings


def check_doctrine(root: Path) -> list[str]:
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
    if not pointer.is_file():
        findings.append(
            "doctrine-pointer (ADR-007): CLAUDE.md is missing — Claude Code loads "
            "no root doctrine without it; it must be a live @AGENTS.md import"
        )
        return findings
    text = pointer.read_text(encoding="utf-8", errors="replace")
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    if first_line != "@AGENTS.md" or len(text) > POINTER_BUDGET_CHARS:
        findings.append(
            "doctrine-pointer (ADR-007): CLAUDE.md must begin with a bare "
            "'@AGENTS.md' import line and stay a short pointer — a backticked or "
            "buried mention does not import, and any fork diverges the runtimes"
        )
    return findings


def check_ledger(root: Path) -> list[str]:
    findings = []
    ledger = root / "docs" / "ledger.jsonl"
    if not ledger.is_file():
        return findings
    for lineno, line in enumerate(
        ledger.read_text(encoding="utf-8", errors="replace").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            findings.append(f"ledger (ADR-006): docs/ledger.jsonl:{lineno} is not valid JSON ({exc.msg})")
            continue
        missing = LEDGER_FIELDS - set(row)
        if missing:
            findings.append(
                f"ledger (ADR-006): docs/ledger.jsonl:{lineno} missing field(s) "
                f"{', '.join(sorted(missing))}"
            )
        # Each present field is validated independently of the others, so one
        # lint run surfaces every defect in a row (single-pass repair).
        vocab_checks = (
            ("severity", LEDGER_SEVERITIES),
            ("artifact", LEDGER_ARTIFACTS),
            ("introduced", LEDGER_PHASES),
            ("catchable", LEDGER_PHASES),
            ("caught", LEDGER_PHASES),
            ("disposition", LEDGER_DISPOSITIONS),
        )
        for field, vocab in vocab_checks:
            if field in row and row[field] not in vocab:
                findings.append(
                    f"ledger (ADR-006): docs/ledger.jsonl:{lineno} {field} "
                    f"'{row[field]}' not in {sorted(vocab)}"
                )
        if "found_by" in row and (
            not isinstance(row["found_by"], str) or not row["found_by"].strip()
        ):
            findings.append(
                f"ledger (ADR-006): docs/ledger.jsonl:{lineno} found_by must be "
                f"a non-empty string naming a seat or stage"
            )
    return findings


def run(root: Path) -> list[str]:
    return (
        check_zone_wall(root)
        + check_sideways_deps(root)
        + check_doctrine(root)
        + check_ledger(root)
    )


def main() -> int:
    findings = run(ROOT)
    for finding in findings:
        print(finding)
    print(f"lint: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

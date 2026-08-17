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
  5. citations (ADR-006): a `§N` citation resolves to a real decision item,
     and a claimed docs/ledger.jsonl row count matches the file. Promoted
     from the review seats on recorded recurrence, not on plausibility; its
     coverage is deliberately narrower than the class it is drawn from and
     the boundary is stated on check_citations itself.

All shipped files are scanned regardless of extension; binary content (NUL
byte in the first 1KB) is skipped. Invoke as `python <repo>/tools/lint.py`
from any cwd — paths resolve from this file's own location.
Exit 0 when clean, 1 with findings listed one per line.
"""
from __future__ import annotations

import datetime
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
    "catchable", "caught", "source", "disposition", "found_by", "ref",
}
LEDGER_SEVERITIES = {"high", "medium", "low"}
LEDGER_ARTIFACTS = {
    "constitution", "repo-docs", "skill-prose", "script",
    "lint", "tests", "ci", "packaging",
}
# Two axes, not one. `introduced` and `catchable` name the artifact *position*
# where the defect was made and where it was earliest catchable; `caught` names
# the review *stage* that actually found it. The single merged set these replace
# mixed both kinds and could express no position earlier than the prose, so all
# three fields held one value across the entire corpus and the axis ADR-006 §5
# governs by was unmeasurable by construction.
#
# `unrecorded` means ONE thing on either axis: not judged. It is not a fallback
# for a judged value that fits nothing listed — that reading restores the double
# duty `authoring` was retired for. A judged value with no lawful slot means the
# vocabulary is short, and the fix is an ADR amendment editing these two sets.
#
# NOTHING CHECKS THAT THESE SETS MATCH ADR-006 §5's PROSE, in either direction:
# widening either set passes the lint. It does NOT pass the suite — a test pins
# these literals exactly, which catches a local edit but still cannot see the
# ADR, so prose and code can drift together. The correspondence is a
# stated, unenforced property (§5 names it alongside the axis ordering and the
# two `ref` properties) rather than a guarded one — ADR-002 earns code by
# recurrence, and a guard here would have to read and parse ADR text.
LEDGER_POSITIONS = {
    "framing", "design", "plan", "implementation", "unrecorded",
}
# post-fix and external are here because they name a review STAGE a defect can
# be caught at. Not every found_by value qualifies: defense, judge and owner are
# equally named by §5's found_by contract and are finders within or outside a
# stage, not stages themselves. Without these two, 29 real catches mapped onto
# `adversarial-review` — precisely the "nearest wrong one" the section forbids.
LEDGER_STAGES = {
    "authoring-review", "adversarial-review", "post-fix", "external",
    "ci", "post-merge", "consumer", "unrecorded",
}
LEDGER_DISPOSITIONS = {"fixed", "reworded", "recorded", "owner-pending"}
LEDGER_DATE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
# found_by is half-open: seat names may be swapped in freely, while the
# non-seat values are closed and grow only by amending ADR-006 §5. The lint
# holds neither half — the check is on form:
# a lowercase token with no whitespace, so "Cold-Read" and "wiring falsifier"
# cannot silently fork one seat's yield across two buckets.
LEDGER_FOUND_BY = re.compile(r"\A[a-z0-9][a-z0-9-]*\Z")


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
    seen_keys: set[tuple] = set()
    for lineno, line in enumerate(
        ledger.read_text(encoding="utf-8", errors="replace").splitlines(), 1
    ):
        if not line.strip():
            continue
        # One malformed row must never silence the rest, so both the decode and
        # the per-field checks report rather than raise — decoding included,
        # since a JSONDecodeError is not the only way a line can fail to parse.
        # Findings already accumulated for the row survive: the checker appends
        # to the shared list rather than returning one.
        try:
            row = json.loads(line)
        except Exception as exc:  # noqa: BLE001 - report, never crash the lint
            findings.append(
                f"ledger (ADR-006): docs/ledger.jsonl:{lineno} is not valid JSON "
                f"({type(exc).__name__}: {exc})"
            )
            continue
        try:
            _check_ledger_row(row, lineno, seen_keys, findings)
        except Exception as exc:  # noqa: BLE001 - report, never crash the lint
            findings.append(
                f"ledger (ADR-006): docs/ledger.jsonl:{lineno} could not be fully "
                f"validated ({type(exc).__name__}: {exc})"
            )
    return findings


def _is_calendar_day(value: str) -> bool:
    """LEDGER_DATE pins the shape; this rejects 2026-13-45 and 2026-02-30."""
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _check_ledger_row(row: dict, lineno: int, seen_keys: set, findings: list) -> None:
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
        ("introduced", LEDGER_POSITIONS),
        ("catchable", LEDGER_POSITIONS),
        ("caught", LEDGER_STAGES),
        ("disposition", LEDGER_DISPOSITIONS),
    )
    for field, vocab in vocab_checks:
        # Membership is tested only on strings: a JSON list or object is
        # unhashable and would raise instead of reporting the finding.
        if field in row and (
            not isinstance(row[field], str) or row[field] not in vocab
        ):
            findings.append(
                f"ledger (ADR-006): docs/ledger.jsonl:{lineno} {field} "
                f"'{row[field]}' not in {sorted(vocab)}"
            )
    if "found_by" in row and (
        not isinstance(row["found_by"], str)
        or not LEDGER_FOUND_BY.match(row["found_by"])
    ):
        findings.append(
            f"ledger (ADR-006): docs/ledger.jsonl:{lineno} found_by "
            f"'{row.get('found_by')}' must be a lowercase name of digits, "
            f"letters and hyphens — one seat, one bucket"
        )
    if "ref" in row and (
        not isinstance(row["ref"], str) or not row["ref"].startswith("https://")
    ):
        findings.append(
            f"ledger (ADR-006): docs/ledger.jsonl:{lineno} ref "
            f"'{row.get('ref')}' must be an https URL to the review's durable record"
        )
    if "date" in row and (
        not isinstance(row["date"], str)
        or not LEDGER_DATE.match(row["date"])
        or not _is_calendar_day(row["date"])
    ):
        findings.append(
            f"ledger (ADR-006): docs/ledger.jsonl:{lineno} date "
            f"'{row.get('date')}' is not an ISO YYYY-MM-DD date"
        )
    # The key is built only from strings: an unhashable id or source would
    # raise here, and a 7 that is sometimes an int would evade the check.
    for field in ("id", "source"):
        if field in row and not isinstance(row[field], str):
            findings.append(
                f"ledger (ADR-006): docs/ledger.jsonl:{lineno} {field} "
                f"must be a string (got {type(row[field]).__name__})"
            )
    if isinstance(row.get("source"), str) and isinstance(row.get("id"), str):
        key = (row["source"], row["id"])
        if key in seen_keys:
            findings.append(
                f"ledger (ADR-006): docs/ledger.jsonl:{lineno} duplicate "
                f"(source, id) pair {key!r} — ids must be unique within a source"
            )
        seen_keys.add(key)


def _adr_decision_items(text: str) -> tuple[list[int], str | None]:
    """Top-level decision items of an ADR, and the first defect breaking them.

    `§N` addresses the Nth entry of the ordered list under `## Decision`. Items
    are counted at column 0 only: an indented `1.` is a sub-list, and the
    continuation paragraphs that carry most of ADR-006 are indented under their
    item.

    Two ways the addressing breaks, and **the second is the one that has
    actually happened** (PR #6's `M3`):

      * the source numbers skip or repeat — visible to anyone reading the file;
      * a non-list line sits at **column 0 between two items**, which terminates
        the list in the renderer and restarts numbering at the next item, while
        the source still reads an unbroken `1.`..`6.`. Nothing about the prose
        looks wrong. This is why the checker models the renderer's rule rather
        than counting the digits it can see: a guard that reads only what the
        source says would pass the exact defect it exists to catch, which is the
        shape this repo has already shipped once.

    Returns the item numbers and a defect description, or None when sound.
    """
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().lower() == "## decision":
            start = i + 1
            break
    if start is None:
        return [], None
    body: list[tuple[int, str]] = []
    for offset, line in enumerate(lines[start:]):
        if line.startswith("## "):
            break  # next top-level section ends the Decision list
        body.append((start + offset + 1, line))

    items: list[int] = []
    first_item_index = None
    for index, (_, line) in enumerate(body):
        if re.match(r"\d+\. ", line):  # column 0 only — no leading space
            items.append(int(re.match(r"(\d+)\. ", line).group(1)))
            if first_item_index is None:
                first_item_index = index
    if not items:
        return [], None
    last_item_index = max(
        i for i, (_, line) in enumerate(body) if re.match(r"\d+\. ", line)
    )

    # A column-0 line that is neither blank nor an item, sitting between the
    # first and last item, is what closes the list in the renderer.
    for lineno, line in body[first_item_index:last_item_index]:
        if not line.strip():
            continue
        if line[:1].isspace() or re.match(r"\d+\. ", line):
            continue
        return items, (
            f"line {lineno} sits at column 0 between decision items "
            f"({line.strip()[:48]!r}...), which closes the ordered list in the "
            f"renderer and restarts numbering below it"
        )
    if items != list(range(1, len(items) + 1)):
        return items, f"source numbering is not contiguous 1..N (reads {items})"
    return items, None


# A citation is `§N`, optionally carrying its own ADR ("ADR-006 §5"). A bare
# `§N` resolves against the ADR it appears in; in a non-ADR file it addresses
# nothing this checker can resolve and is skipped rather than guessed at.
SECTION_CITATION = re.compile(r"(?:ADR-(\d{3})\s*)?§\s*(\d+)")
ADR_FILENAME = re.compile(r"\AADR-(\d{3})-")
# Scanned for citations: the constitution, the repo docs that cite it, the root
# doctrine file, and the shipped zone. lint.py lives in tools/ (repo-only), so
# reading across both zones is lawful for it — ADR-004 binds what the *shipped*
# files may reference, not what this checker may read.
CITATION_SCAN_DIRS = ("docs", "skills", "lib", "commands", "agents")
CITATION_SCAN_FILES = ("AGENTS.md",)


def check_citations(root: Path) -> list[str]:
    """ADR-002 §24 / ADR-006: mechanically decidable citation defects.

    Two classes, each promoted on recorded instances rather than on plausibility
    (ADR-002 earns code by recurrence):

      1. **A `§N` citation that resolves to nothing.** Exhibit: PR #6's `M3` —
         two paragraphs written at column 0 closed ADR-006's Decision list, so
         *"every '§5' citation pointed outside §5"*, and the panel read past it.
         The contiguity check is what catches that class: a broken list
         renumbers, so the defect shows up as items no longer running 1..N,
         which no reader diffing prose would see.
      2. **A stale `docs/ledger.jsonl` row count.** Exhibits: PR #12's `M3`
         (*"'253 rows' is wrong; the ledger holds 261"*) and PR #6's `M25`
         (*"'all 142 rows' where the corpus is 192"*).

    **Coverage is narrower than the class, deliberately, and the boundary is
    stated so the guard is not mistaken for the whole rule.** Not covered:
    directional prose about content position that names no resolvable target
    (PR #12's `M18`, *"both `ref` properties below"* — the referent is a phrase,
    not an anchor); enumerated counts in free prose (PR #6's `PF13`, *"Three
    properties"* introducing four); arithmetic inside a review's own tallies.
    Those stay with the seats. A count claim is checked only where it names
    `ledger.jsonl` within LEDGER_COUNT_WINDOW characters, which is what keeps
    historical and scoped counts ("all 192 rows *then on `main`*") out of scope
    — they are claims about a past tree, and this checker only knows the
    current one.
    """
    findings: list[str] = []
    adr_dir = root / "docs" / "architecture" / "adr"
    items_by_adr: dict[str, tuple[list[int], bool]] = {}
    if adr_dir.is_dir():
        for path in sorted(adr_dir.glob("ADR-*.md")):
            match = ADR_FILENAME.match(path.name)
            if not match:
                continue
            text = _read_text(path)
            if text is None:
                continue
            items, defect = _adr_decision_items(text)
            items_by_adr[match.group(1)] = (items, defect)
            if defect is not None:
                findings.append(
                    f"citation (ADR-006): {path.relative_to(root).as_posix()} "
                    f"Decision list is broken — {defect}; every §N citation "
                    f"into it re-points silently"
                )

    ledger_rows = _ledger_row_count(root)

    for path in _iter_citation_files(root):
        text = _read_text(path)
        if text is None:
            continue
        rel_file = path.relative_to(root).as_posix()
        own = ADR_FILENAME.match(path.name)
        own_adr = own.group(1) if own else None
        for lineno, line in enumerate(text.splitlines(), 1):
            findings.extend(
                _citation_hits(line, lineno, rel_file, own_adr, items_by_adr)
            )
            if ledger_rows is not None:
                findings.extend(
                    _ledger_count_hits(line, lineno, rel_file, ledger_rows)
                )
    return findings


def _iter_citation_files(root: Path):
    for name in CITATION_SCAN_FILES:
        path = root / name
        if path.is_file():
            yield path
    for dirname in CITATION_SCAN_DIRS:
        base = root / dirname
        if base.is_dir():
            for path in _iter_files(base):
                if path.suffix.lower() == ".md":
                    yield path


def _ledger_row_count(root: Path) -> int | None:
    ledger = root / "docs" / "ledger.jsonl"
    if not ledger.is_file():
        return None
    text = _read_text(ledger)
    if text is None:
        return None
    return sum(1 for line in text.splitlines() if line.strip())


def _citation_hits(line, lineno, rel_file, own_adr, items_by_adr):
    for match in SECTION_CITATION.finditer(line):
        target_adr = match.group(1) or own_adr
        if target_adr is None:
            continue  # bare §N outside an ADR — no resolvable target
        entry = items_by_adr.get(target_adr)
        if entry is None:
            continue  # cites an ADR this repo does not carry — not this check
        items, _ = entry
        section = int(match.group(2))
        if section not in items:
            yield (
                f"citation (ADR-006): {rel_file}:{lineno} '{match.group(0)}' "
                f"resolves to nothing — ADR-{target_adr}'s Decision list holds "
                f"items {items}"
            )


# A count claim is checked only when it names the file it is counting, within
# this window. Widening it pulls in historical counts, which are claims about a
# past tree and are not this checker's to judge; narrowing it below the longest
# lawful phrasing silently drops live claims. Measured against the tree at the
# time of writing: no live claim sits between 80 and 200 characters of its
# subject, so the value is not on a cliff in either direction.
LEDGER_COUNT_WINDOW = 80
LEDGER_COUNT_CLAIM = re.compile(r"(\d[\d,]*)\s+rows\b")


def _ledger_count_hits(line, lineno, rel_file, ledger_rows):
    for match in LEDGER_COUNT_CLAIM.finditer(line):
        lo = max(0, match.start() - LEDGER_COUNT_WINDOW)
        hi = min(len(line), match.end() + LEDGER_COUNT_WINDOW)
        if "ledger.jsonl" not in line[lo:hi]:
            continue
        claimed = int(match.group(1).replace(",", ""))
        if claimed != ledger_rows:
            yield (
                f"citation (ADR-006): {rel_file}:{lineno} claims "
                f"'{match.group(0)}' of docs/ledger.jsonl, which holds "
                f"{ledger_rows}"
            )


def run(root: Path) -> list[str]:
    return (
        check_zone_wall(root)
        + check_sideways_deps(root)
        + check_doctrine(root)
        + check_ledger(root)
        + check_citations(root)
    )


def main() -> int:
    findings = run(ROOT)
    for finding in findings:
        print(finding)
    print(f"lint: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

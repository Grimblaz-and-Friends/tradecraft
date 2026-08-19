#!/usr/bin/env python3
"""tradecraft packaging lint — the constitution's enforcement arm (§4).

Checks, each anchored to the ADR it enforces:

  1. zone wall (§4): no file in the shipped zone may reference the
     repo-only zone (docs/, tools/, .github/) by any path form — rooted,
     relative (../ or ./), backslashed, or case-shifted. Full web URLs are
     lawful: they resolve for consumers; repo paths do not.
  2. sideways deps (§3): no skill may reference another skill by path
     (rooted or relative), and lib/ may not reference any skill (deps point
     down). Name-form coupling ("load the beta skill") is not machine-
     checkable; it is reviewed, not linted — these checks are the checkable
     subset, not the whole rule.
  3. doctrine (§3/§9): AGENTS.md exists and stays within budget;
     CLAUDE.md exists and is a live @AGENTS.md import — checked by position
     (first non-empty line, unquoted), not substring, because Claude Code
     skips imports inside code spans and loads nothing from an absent file.
  4. ledger (§8): docs/ledger.jsonl, when present, parses and carries
     the required fields per row.
  5. seat record (§8): docs/seat-record.jsonl, when present, parses and
     carries the required fields per row — per-seat raw/merged/sustained
     counts, the precision axis the defect ledger is structurally silent
     about. It ships with this check rather than owing one: §8's interim
     waiver for hand-written rows *is* the lint.

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

# §3's "deliberately tiny": the predecessor's root file passed 30k chars in
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
# `work-prose` (D-59) is the off-tree half: prose the constitution requires of a
# unit of work and homes outside the tree (in practice an issue or a pull
# request) — the pre-implementation artifact, the affirmation record, the PR
# body, a review's report. Its test is WHERE THE MATERIAL LIVES, not which
# position it sits at; widening `repo-docs` to cover both sides of that line was
# rejected, because one value would then carry two denotations at once. Without
# it, two reviews' sustained findings had no correct value: the design review on
# issue #42 and `DF1`/`M24(a)` on PR #50.
LEDGER_ARTIFACTS = {
    "constitution", "repo-docs", "work-prose", "skill-prose", "script",
    "lint", "tests", "ci", "packaging",
}
# Two axes, not one. `introduced` and `catchable` name the artifact *position*
# where the defect was made and where it was earliest catchable; `caught` names
# the review *stage* that actually found it. The single merged set these replace
# mixed both kinds and could express no position earlier than the prose, so all
# three fields held one value across the entire corpus and the axis §8
# governs by was unmeasurable by construction.
#
# `unrecorded` means ONE thing on either axis: not judged. It is not a fallback
# for a judged value that fits nothing listed — that reading restores the double
# duty `authoring` was retired for. A judged value with no lawful slot means the
# vocabulary is short, and the fix is a decision entry amending these two sets.
#
# NOTHING CHECKS THAT THESE SETS MATCH THE STATUTE'S §8 PROSE, in either direction:
# widening either set passes the lint. It does NOT pass the suite — a test pins
# these literals exactly, which catches a local edit but still cannot see the
# statute, so prose and code can drift together. The correspondence is a
# stated, unenforced property (§8 names it alongside the axis ordering and the
# two `ref` properties) rather than a guarded one — §2 earns code by
# recurrence, and a guard here would have to read and parse ADR text.
LEDGER_POSITIONS = {
    "framing", "design", "plan", "implementation", "unrecorded",
}
# post-fix and external are here because they name a review STAGE a defect can
# be caught at. Not every found_by value qualifies: defense, judge and owner are
# equally named by §8's found_by contract and are finders within or outside a
# stage, not stages themselves. Without these two, 29 real catches mapped onto
# `adversarial-review` — precisely the "nearest wrong one" the section forbids.
LEDGER_STAGES = {
    "authoring-review", "adversarial-review", "post-fix", "external",
    "ci", "post-merge", "consumer", "unrecorded",
}
# `filed` was added 2026-08-17: §7 makes filing the exception and requires both
# other homes rejected, but a finding that lawfully cleared that bar had no value
# to say so and was written `recorded` with an issue named as the reason. That is
# a different claim — `recorded` says nobody will act, `filed` says someone will,
# at the surface `ref` names.
LEDGER_DISPOSITIONS = {"fixed", "reworded", "recorded", "owner-pending", "filed"}
LEDGER_DATE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
# The one form rule for every name-shaped field in both files: `found_by`, and
# the seat record's `seat`, `model`, `runtime`, and the optional `trial`. A
# lowercase token with no whitespace, so one name occupies exactly one bucket and
# `SELECT DISTINCT` over any of them enumerates what is actually in use.
TOKEN = re.compile(r"\A[a-z0-9][a-z0-9-]*\Z")
# found_by is half-open: seat names may be swapped in freely, while the
# non-seat values are closed and grow only by amending the statute's §8. The lint
# holds neither half — the check is on form, and it is TOKEN: one form rule with
# one definition site, because the skill says these fields are tokens "like
# found_by and for the same reason", and two identical regexes would drift
# silently. "Cold-Read" and "wiring falsifier" cannot fork one seat's yield.
LEDGER_FOUND_BY = TOKEN


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
                        f"zone-wall (§4): {rel_file}:{lineno} references "
                        f"repo-only path '{hit}'"
                    )
                for raw, parts in _resolved_relative_targets(root, path, line):
                    if parts and parts[0].lower() in REPO_ONLY_NAMES:
                        findings.append(
                            f"zone-wall (§4): {rel_file}:{lineno} relative "
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
                            f"sideways-dep (§3): {rel_file}:{lineno} references "
                            f"skill '{target}'" + (f" from skill '{own}'" if own else " from lib/")
                        )
                for raw, parts in _resolved_relative_targets(root, path, line):
                    if len(parts) >= 2 and parts[0] == "skills":
                        target = parts[1]
                        if own is None or target.lower() != own.lower():
                            findings.append(
                                f"sideways-dep (§3): {rel_file}:{lineno} relative "
                                f"reference '{raw}' resolves into skill '{target}'"
                                + (f" from skill '{own}'" if own else " from lib/")
                            )
    return findings


def check_doctrine(root: Path) -> list[str]:
    findings = []
    agents = root / "AGENTS.md"
    if not agents.is_file():
        findings.append("doctrine (§9): AGENTS.md is missing (it is the canonical root file)")
    else:
        size = len(agents.read_text(encoding="utf-8", errors="replace"))
        if size > AGENTS_BUDGET_CHARS:
            findings.append(
                f"doctrine-budget (§3): AGENTS.md is {size} chars, "
                f"budget is {AGENTS_BUDGET_CHARS} — move guidance into the skill it governs"
            )
    pointer = root / "CLAUDE.md"
    if not pointer.is_file():
        findings.append(
            "doctrine-pointer (§9): CLAUDE.md is missing — Claude Code loads "
            "no root doctrine without it; it must be a live @AGENTS.md import"
        )
        return findings
    text = pointer.read_text(encoding="utf-8", errors="replace")
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    if first_line != "@AGENTS.md" or len(text) > POINTER_BUDGET_CHARS:
        findings.append(
            "doctrine-pointer (§9): CLAUDE.md must begin with a bare "
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
                f"ledger (§8): docs/ledger.jsonl:{lineno} is not valid JSON "
                f"({type(exc).__name__}: {exc})"
            )
            continue
        try:
            _check_ledger_row(row, lineno, seen_keys, findings)
        except Exception as exc:  # noqa: BLE001 - report, never crash the lint
            findings.append(
                f"ledger (§8): docs/ledger.jsonl:{lineno} could not be fully "
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


def _not_a_mapping(row, where: str, findings: list) -> bool:
    """A JSON array or scalar row must be rejected before any field is read.

    Without this the missing-field set difference runs against a list's *values*
    and reports the row's entries as present fields, which is a false negative
    dressed as a finding. Both row checkers shared the hole; it is closed in one
    place so the twin cannot reopen.
    """
    if not isinstance(row, dict):
        findings.append(
            f"{where} is not a JSON object (got {type(row).__name__}) — a row "
            f"must be a mapping of fields"
        )
        return True
    return False


def _check_ledger_row(row: dict, lineno: int, seen_keys: set, findings: list) -> None:
    if _not_a_mapping(row, f"ledger (§8): docs/ledger.jsonl:{lineno}", findings):
        return
    missing = LEDGER_FIELDS - set(row)
    if missing:
        findings.append(
            f"ledger (§8): docs/ledger.jsonl:{lineno} missing field(s) "
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
                f"ledger (§8): docs/ledger.jsonl:{lineno} {field} "
                f"'{row[field]}' not in {sorted(vocab)}"
            )
    if "found_by" in row and (
        not isinstance(row["found_by"], str)
        or not LEDGER_FOUND_BY.match(row["found_by"])
    ):
        findings.append(
            f"ledger (§8): docs/ledger.jsonl:{lineno} found_by "
            f"'{row.get('found_by')}' must be a lowercase name of digits, "
            f"letters and hyphens — one seat, one bucket"
        )
    # Optional, so absence is lawful; present-but-malformed is not, because a
    # trial that cannot be selected by name attributes nothing (§2's
    # properties 4 and 6 are what this field exists to make dischargeable).
    if "trial" in row and (
        not isinstance(row["trial"], str) or not TOKEN.match(row["trial"])
    ):
        findings.append(
            f"ledger (§8): docs/ledger.jsonl:{lineno} trial "
            f"'{row.get('trial')}' must be a lowercase name of digits, letters "
            f"and hyphens — one trial, one bucket"
        )
    if "ref" in row and (
        not isinstance(row["ref"], str) or not row["ref"].startswith("https://")
    ):
        findings.append(
            f"ledger (§8): docs/ledger.jsonl:{lineno} ref "
            f"'{row.get('ref')}' must be an https URL to the review's durable record"
        )
    if "date" in row and (
        not isinstance(row["date"], str)
        or not LEDGER_DATE.match(row["date"])
        or not _is_calendar_day(row["date"])
    ):
        findings.append(
            f"ledger (§8): docs/ledger.jsonl:{lineno} date "
            f"'{row.get('date')}' is not an ISO YYYY-MM-DD date"
        )
    # The key is built only from strings: an unhashable id or source would
    # raise here, and a 7 that is sometimes an int would evade the check.
    for field in ("id", "source"):
        if field in row and not isinstance(row[field], str):
            findings.append(
                f"ledger (§8): docs/ledger.jsonl:{lineno} {field} "
                f"must be a string (got {type(row[field]).__name__})"
            )
    if isinstance(row.get("source"), str) and isinstance(row.get("id"), str):
        key = (row["source"], row["id"])
        if key in seen_keys:
            findings.append(
                f"ledger (§8): docs/ledger.jsonl:{lineno} duplicate "
                f"(source, id) pair {key!r} — ids must be unique within a source"
            )
        seen_keys.add(key)


SEAT_RECORD_FIELDS = {
    "source", "date", "seat", "model", "runtime",
    "lane", "raw", "merged", "sustained", "status", "isolated",
}
# `clean` ran and found nothing; `failed` was still unusable after its one
# re-dispatch. Both carry zeros, so without this field they are the same row —
# which is the collapse the file exists to close (§8, §2's own
# note that the ledger cannot say a trial ran clean).
SEAT_STATUSES = {"ran", "clean", "failed"}
SEAT_LANES = {"panel", "routine"}
SEAT_COUNTS = ("raw", "merged", "sustained")
SEAT_TOKEN_FIELDS = ("seat", "model", "runtime")


def check_seat_record(root: Path) -> list[str]:
    """§8: per-seat precision counts, the ledger's companion.

    The defect ledger holds only sustained findings, so it measures yield and is
    silent about precision. These rows carry both, and they ship with this check
    rather than owing one: the interim waiver §8 takes for hand-written rows *is*
    the lint, so a format arriving without a validator is §2's day-one-code
    exception being taken rather than discharged.
    """
    findings: list[str] = []
    record = root / "docs" / "seat-record.jsonl"
    if not record.is_file():
        return findings
    seen: set[tuple] = set()
    for lineno, line in enumerate(
        record.read_text(encoding="utf-8", errors="replace").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception as exc:  # noqa: BLE001 - report, never crash the lint
            findings.append(
                f"seat-record (§8): docs/seat-record.jsonl:{lineno} is not "
                f"valid JSON ({type(exc).__name__}: {exc})"
            )
            continue
        try:
            _check_seat_row(row, lineno, seen, findings)
        except Exception as exc:  # noqa: BLE001 - report, never crash the lint
            findings.append(
                f"seat-record (§8): docs/seat-record.jsonl:{lineno} could "
                f"not be fully validated ({type(exc).__name__}: {exc})"
            )
    return findings


def _check_seat_row(row: dict, lineno: int, seen: set, findings: list) -> None:
    where = f"seat-record (§8): docs/seat-record.jsonl:{lineno}"
    if _not_a_mapping(row, where, findings):
        return
    missing = SEAT_RECORD_FIELDS - set(row)
    if missing:
        findings.append(f"{where} missing field(s) {', '.join(sorted(missing))}")
    for field, vocab in (("status", SEAT_STATUSES), ("lane", SEAT_LANES)):
        if field in row and (
            not isinstance(row[field], str) or row[field] not in vocab
        ):
            findings.append(
                f"{where} {field} '{row[field]}' not in {sorted(vocab)}"
            )
    for field in SEAT_TOKEN_FIELDS:
        if field in row and (
            not isinstance(row[field], str) or not TOKEN.match(row[field])
        ):
            findings.append(
                f"{where} {field} '{row.get(field)}' must be a lowercase name of "
                f"digits, letters and hyphens — one name, one bucket"
            )
    if "trial" in row and (
        not isinstance(row["trial"], str) or not TOKEN.match(row["trial"])
    ):
        findings.append(
            f"{where} trial '{row.get('trial')}' must be a lowercase name of "
            f"digits, letters and hyphens"
        )
    for field in SEAT_COUNTS:
        # bool is a subclass of int, so it is excluded explicitly: True would
        # otherwise pass as a count of 1 and read as a real number downstream.
        if field in row and (
            isinstance(row[field], bool)
            or not isinstance(row[field], int)
            or row[field] < 0
        ):
            findings.append(
                f"{where} {field} '{row.get(field)}' must be a non-negative "
                f"integer"
            )
    if "isolated" in row and not isinstance(row["isolated"], bool):
        findings.append(
            f"{where} isolated '{row.get('isolated')}' must be a boolean — the "
            f"field exists to make an omission visible, so 0, 1 and \"false\" "
            f"do not stand in for it"
        )
    if "date" in row and (
        not isinstance(row["date"], str)
        or not LEDGER_DATE.match(row["date"])
        or not _is_calendar_day(row["date"])
    ):
        findings.append(
            f"{where} date '{row.get('date')}' is not an ISO YYYY-MM-DD date"
        )
    if "source" in row and (
        not isinstance(row["source"], str) or not row["source"].strip()
    ):
        findings.append(
            f"{where} source '{row.get('source')}' must be a non-empty string — "
            f"it is the join to the defect ledger and half the duplicate key, so "
            f"an empty one collapses every seat of every review into one bucket"
        )
    # A seat cannot appear twice for one review event: two rows for one seat make
    # every per-seat sum ambiguous, which is the one thing this file is read for.
    if isinstance(row.get("source"), str) and isinstance(row.get("seat"), str):
        key = (row["source"], row["seat"])
        if key in seen:
            findings.append(
                f"{where} duplicate (source, seat) pair {key!r} — one seat, one "
                f"row per review event"
            )
        seen.add(key)
    counts = {
        f: row[f] for f in SEAT_COUNTS
        if isinstance(row.get(f), int) and not isinstance(row.get(f), bool)
    }
    if len(counts) == len(SEAT_COUNTS):
        raw, merged, sustained = (counts[f] for f in SEAT_COUNTS)
        if not raw >= merged >= sustained:
            findings.append(
                f"{where} counts are not nested: raw {raw} >= merged {merged} "
                f">= sustained {sustained} must hold — each is a subset of the "
                f"one before it, and 'raw minus sustained' is the number this "
                f"file exists for"
            )
        if row.get("status") == "ran" and raw == 0:
            findings.append(
                f"{where} status 'ran' with a zero raw count — a run that found "
                f"nothing is 'clean'; leaving both lawful re-admits the very "
                f"ambiguity status was added to remove"
            )
    # `clean` and `failed` both mean "found nothing", so a non-zero count
    # contradicts the status the row carries.
    if row.get("status") in {"clean", "failed"}:
        nonzero = [
            f for f in SEAT_COUNTS
            if isinstance(row.get(f), int) and not isinstance(row.get(f), bool)
            and row[f] != 0
        ]
        if nonzero:
            findings.append(
                f"{where} status '{row['status']}' carries non-zero "
                f"{', '.join(nonzero)} — a seat that found nothing has no counts"
            )


def run(root: Path) -> list[str]:
    return (
        check_zone_wall(root)
        + check_sideways_deps(root)
        + check_doctrine(root)
        + check_ledger(root)
        + check_seat_record(root)
    )


def main() -> int:
    findings = run(ROOT)
    for finding in findings:
        print(finding)
    print(f"lint: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

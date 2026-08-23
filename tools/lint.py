#!/usr/bin/env python3
"""tradecraft packaging lint — enforcement for the doctrine's checkable subset.

Checks:

  1. zone wall: no file in the shipped zone may reference the repo-only zone
     (docs/, tools/, .github/) by any path form — rooted, relative (../ or ./),
     backslashed, or case-shifted. Full web URLs are lawful: they resolve for
     consumers; repo paths do not.
  2. sideways deps: no skill may reference another skill by path (rooted or
     relative), and lib/ may not reference any skill (deps point down).
     Name-form coupling ("load the beta skill") is not machine-checkable; it
     is reviewed, not linted.
  3. doctrine: AGENTS.md exists and stays within budget; CLAUDE.md exists and
     is a live @AGENTS.md import — checked by position (first non-empty line,
     unquoted), because Claude Code skips imports inside code spans and loads
     nothing from an absent file.
  4. doctrine callout: tools/doctrine_callout.py exists and ci.yml still
     declares the job that runs it. The callout cannot catch its own removal,
     because a PR deleting the job touches no doctrine file [D-81].
  5. review index: docs/reviews.jsonl, when present, parses and carries one
     valid row per review — date, artifact, lane, per-seat counts, report URL.

The frozen archive (docs/ledger.jsonl, docs/seat-record.jsonl, the pre-reset
constitution) is not validated: it is history, not a live format (D-74).

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
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent

SHIPPED_DIRS = ("skills", "lib", "commands", "agents", ".claude-plugin")
REPO_ONLY_NAMES = {"docs", "tools", ".github"}

# The predecessor's root file passed 30k chars in eight months because every
# incident defaulted to a paragraph. The budget is the structural counterweight:
# at the limit, adding a line means routing something out (doctrine, "Admitting
# a new requirement").
AGENTS_BUDGET_CHARS = 8_000
POINTER_BUDGET_CHARS = 500

ROOTED_ZONE = re.compile(r"(docs|tools|\.github)[\\/]", re.IGNORECASE)
ROOTED_SKILL = re.compile(r"skills[\\/]([\w-]+)[\\/]", re.IGNORECASE)
# The first segment may itself be dot-leading (`.github`), so the class after
# the prefix admits a dot. Requiring a word character there let every relative
# form of `.github/` through while catching `docs/` and `tools/` -- the one
# repo-only name starting with a dot was the one the docstring above lied about.
# Anchored at a token boundary: a `../` run preceded by a path character is
# the tail of a longer token (`assets/../../docs/x.md`), whose WHOLE path is
# what resolves -- matching the suffix alone resolved it from the wrong base
# and reported a repo-only hit for a path that lands inside the skill. Shared
# with check_sideways_deps, so the same false positive reached both guards.
RELATIVE_REF = re.compile(r"(?<![\w.\\/-])(?:\.\.?[\\/])+[\w.][\w.\\/\\-]*")
REL_PREFIX_TAIL = re.compile(r"(?:\.\.?[\\/])+$")

DATE_SHAPE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
# One form rule for every name-shaped field: a lowercase token with no
# whitespace, so one name occupies exactly one bucket and a query over seat
# names enumerates what is actually in use.
TOKEN = re.compile(r"\A[a-z0-9][a-z0-9-]*\Z")

# The doctrine callout's wiring, matched by position rather than by substring:
# a commented-out job still contains every substring it had when it was live.
JOB_HEADER = "  doctrine-callout:"
# All three lawful spellings of the trigger, and none of `pull_request_target`
# (the `\b` cannot end before an underscore). A guard that fails a required
# check on a lawful reformat blocks lawful work, which fails as hard as
# passing unlawful work.
PR_TRIGGER = re.compile(
    r"^\s*pull_request:\s*$|^\s*-\s*pull_request\s*$|^on:.*\bpull_request\b"
)
RUNS_SCRIPT = re.compile(r"^\s+(?:-\s+)?run:\s*python tools[\\/]doctrine_callout\.py\b")
# The event is named; the gate's exact wording is not, so a lawful rewrite
# (adding `&& !draft`, or moving to ${{ }} form) does not fail a required check.
GATED_ON_PR = re.compile(r"^\s+if:.*pull_request")

REVIEW_FIELDS = {"date", "artifact", "lane", "seats", "report"}
REVIEW_LANES = {"panel", "routine"}
SEAT_COUNTS = ("raw", "merged", "sustained", "high")


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
                        f"zone-wall: {rel_file}:{lineno} references "
                        f"repo-only path '{hit}'"
                    )
                for raw, parts in _resolved_relative_targets(root, path, line):
                    if parts and parts[0].lower() in REPO_ONLY_NAMES:
                        findings.append(
                            f"zone-wall: {rel_file}:{lineno} relative "
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
                    # Same lawful-case guards as the zone wall's rooted branch:
                    # web URLs resolve for consumers, relative forms belong to
                    # the resolution check, and a longer path or hyphenated
                    # token (their-skills/) is not this repo's skills/.
                    before = _token_before(line, match.start())
                    if "://" in before:
                        continue
                    if REL_PREFIX_TAIL.search(before):
                        continue
                    if before and re.search(r"[\w@\-/\\]$", before):
                        continue
                    target = match.group(1)
                    if own is None or target.lower() != own.lower():
                        findings.append(
                            f"sideways-dep: {rel_file}:{lineno} references "
                            f"skill '{target}'" + (f" from skill '{own}'" if own else " from lib/")
                        )
                for raw, parts in _resolved_relative_targets(root, path, line):
                    if len(parts) >= 2 and parts[0] == "skills":
                        target = parts[1]
                        if own is None or target.lower() != own.lower():
                            findings.append(
                                f"sideways-dep: {rel_file}:{lineno} relative "
                                f"reference '{raw}' resolves into skill '{target}'"
                                + (f" from skill '{own}'" if own else " from lib/")
                            )
    return findings


def check_doctrine(root: Path) -> list[str]:
    findings = []
    agents = root / "AGENTS.md"
    if not agents.is_file():
        findings.append("doctrine: AGENTS.md is missing (it is the canonical root file)")
    else:
        size = len(agents.read_text(encoding="utf-8", errors="replace"))
        if size > AGENTS_BUDGET_CHARS:
            findings.append(
                f"doctrine-budget: AGENTS.md is {size} chars, "
                f"budget is {AGENTS_BUDGET_CHARS} — route content out (skill, decision entry, mechanism)"
            )
    pointer = root / "CLAUDE.md"
    if not pointer.is_file():
        findings.append(
            "doctrine-pointer: CLAUDE.md is missing — Claude Code loads "
            "no root doctrine without it; it must be a live @AGENTS.md import"
        )
        return findings
    text = pointer.read_text(encoding="utf-8", errors="replace")
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    if first_line != "@AGENTS.md" or len(text) > POINTER_BUDGET_CHARS:
        findings.append(
            "doctrine-pointer: CLAUDE.md must begin with a bare "
            "'@AGENTS.md' import line and stay a short pointer — a backticked or "
            "buried mention does not import, and any fork diverges the runtimes"
        )
    return findings


def _is_calendar_day(value: str) -> bool:
    """DATE_SHAPE pins the shape; this rejects 2026-13-45 and 2026-02-30."""
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_https_url(value) -> bool:
    """An https URL with a real host.

    `netloc` alone is not that test: it is non-empty for `https://@/x` and
    `https://:443/x`, neither of which names a host a reader can reach.
    `hostname` is None for both. A malformed authority raises from urlsplit,
    which is a failed check rather than a crashed lint.
    """
    if not isinstance(value, str) or not value.startswith("https://"):
        return False
    try:
        return bool(urlsplit(value).hostname)
    except ValueError:
        return False


def _not_a_mapping(row, where: str, findings: list) -> bool:
    """A JSON array or scalar row must be rejected before any field is read."""
    if not isinstance(row, dict):
        findings.append(
            f"{where} is not a JSON object (got {type(row).__name__}) — a row "
            f"must be a mapping of fields"
        )
        return True
    return False


def check_review_index(root: Path) -> list[str]:
    """One row per review: date, artifact, lane, per-seat counts, report URL.

    The row is written once when the review ends and never maintained after —
    it exists so process-weight questions (which seats earn their keep, where
    defects concentrate) are answerable when asked, from the reports it links.
    """
    findings: list[str] = []
    index = root / "docs" / "reviews.jsonl"
    if not index.is_file():
        return findings
    for lineno, line in enumerate(
        index.read_text(encoding="utf-8", errors="replace").splitlines(), 1
    ):
        if not line.strip():
            continue
        where = f"review-index: docs/reviews.jsonl:{lineno}"
        # One malformed row must never silence the rest, so both the decode and
        # the per-field checks report rather than raise.
        try:
            row = json.loads(line)
        except Exception as exc:  # noqa: BLE001 - report, never crash the lint
            findings.append(f"{where} is not valid JSON ({type(exc).__name__}: {exc})")
            continue
        try:
            _check_review_row(row, where, findings)
        except Exception as exc:  # noqa: BLE001 - report, never crash the lint
            findings.append(
                f"{where} could not be fully validated ({type(exc).__name__}: {exc})"
            )
    return findings


def _check_review_row(row, where: str, findings: list) -> None:
    if _not_a_mapping(row, where, findings):
        return
    missing = REVIEW_FIELDS - set(row)
    if missing:
        findings.append(f"{where} missing field(s) {', '.join(sorted(missing))}")
    if "date" in row and (
        not isinstance(row["date"], str)
        or not DATE_SHAPE.match(row["date"])
        or not _is_calendar_day(row["date"])
    ):
        findings.append(f"{where} date '{row.get('date')}' is not an ISO YYYY-MM-DD date")
    if "artifact" in row and (
        not isinstance(row["artifact"], str) or not row["artifact"].strip()
    ):
        findings.append(f"{where} artifact must be a non-empty string naming what was reviewed")
    if "lane" in row and (
        not isinstance(row["lane"], str) or row["lane"] not in REVIEW_LANES
    ):
        findings.append(f"{where} lane '{row.get('lane')}' not in {sorted(REVIEW_LANES)}")
    if "report" in row and not _is_https_url(row["report"]):
        findings.append(
            f"{where} report '{row.get('report')}' must be an https URL to the "
            f"review's report — the row holds counts, the report holds the findings"
        )
    if "seats" in row:
        _check_seats(row["seats"], where, findings)


def _check_seats(seats, where: str, findings: list) -> None:
    if not isinstance(seats, dict) or not seats:
        findings.append(
            f"{where} seats must be a non-empty mapping of seat name to counts"
        )
        return
    for name, counts in seats.items():
        if not isinstance(name, str) or not TOKEN.match(name):
            findings.append(
                f"{where} seat name '{name}' must be a lowercase token of "
                f"letters, digits and hyphens — one seat, one bucket"
            )
        if not isinstance(counts, dict):
            findings.append(f"{where} seat '{name}' counts must be a mapping")
            continue
        missing = set(SEAT_COUNTS) - set(counts)
        if missing:
            findings.append(
                f"{where} seat '{name}' missing count(s) {', '.join(sorted(missing))}"
            )
        bad_type = False
        for field in SEAT_COUNTS:
            value = counts.get(field)
            # bool is a subclass of int and is excluded explicitly: True would
            # otherwise pass as a count of 1.
            if field in counts and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                findings.append(
                    f"{where} seat '{name}' {field} '{value}' must be a "
                    f"non-negative integer"
                )
                bad_type = True
        if bad_type or set(SEAT_COUNTS) - set(counts):
            continue
        raw, merged, sustained, high = (counts[f] for f in SEAT_COUNTS)
        # Both `merged >= sustained` and `raw >= sustained` are deliberately
        # absent [D-102]: the terminal stage's docket carries anything in a
        # seat's report that no merged finding carries, and a declined
        # examination is not a finding, so it is in neither count. A
        # zero-finding seat with one sustained decline is raw 0, sustained 1.
        # `sustained` therefore has no upper bound expressible in these four
        # fields. Re-adding either conjunct looks right and is wrong.
        if not (raw >= merged and sustained >= high):
            findings.append(
                f"{where} seat '{name}' counts are not nested: raw {raw} >= "
                f"merged {merged} and sustained {sustained} >= high {high} "
                f"must hold"
            )


def check_doctrine_callout(root: Path) -> list[str]:
    """The callout must still be wired into CI.

    Its own mechanism cannot catch its own removal: a PR that deletes the job
    touches neither doctrine file, so no callout fires, nothing goes red, and
    the mechanism disappears exactly as silently as the CODEOWNERS callout it
    replaced. Loud-on-failure and pinned-when-present are different guarantees
    and the script only carries the first. This is the second, and it lives in
    the lint because the lint is a required status check.
    """
    findings = []
    script = root / "tools" / "doctrine_callout.py"
    workflow = root / ".github" / "workflows" / "ci.yml"
    if not script.is_file():
        findings.append(
            "doctrine-callout: tools/doctrine_callout.py is missing — nothing "
            "would flag a doctrine change for the owner's merge-time read [D-81]"
        )
    if not workflow.is_file():
        findings.append("doctrine-callout: .github/workflows/ci.yml is missing")
        return findings
    lines = workflow.read_text(encoding="utf-8", errors="replace").splitlines()

    # Scoped to the job's own block, not searched over the whole file. A
    # whole-file search for the gate matches the version-bump step's identical
    # `if:` line and passes a workflow whose callout job is disabled; and a
    # plain substring passes a job that has merely been commented out, which is
    # the most ordinary CI edit in the set. Both were measured.
    block = []
    for i, line in enumerate(lines):
        if line == JOB_HEADER:
            for tail in lines[i + 1:]:
                if tail.strip() and not tail.startswith("    "):
                    break
                block.append(tail)
            break
    else:
        findings.append(
            "doctrine-callout: no live `doctrine-callout:` job in "
            ".github/workflows/ci.yml — the callout would stop firing with "
            "nothing going red [D-81]"
        )
        return findings

    for pattern, why in (
        (RUNS_SCRIPT, "does not run tools/doctrine_callout.py"),
        (GATED_ON_PR, "is not gated on a pull_request event"),
    ):
        if not any(pattern.match(line) for line in block):
            findings.append(
                f"doctrine-callout: the doctrine-callout job {why} [D-81]"
            )
    # The trigger is file-level, and switching it (to pull_request_target, say)
    # would skip the job silently while both required checks still report.
    if not any(PR_TRIGGER.match(line) for line in lines):
        findings.append(
            "doctrine-callout: .github/workflows/ci.yml has no `pull_request:` "
            "trigger — the callout job would never run [D-81]"
        )
    return findings


def check_decision_index(root: Path) -> list[str]:
    """Every decision entry has a row in the log's index, and every row a file.

    The row is part of landing, written once in the PR that lands the entry and
    never maintained after. Without it the entry is unreachable: the shipped
    rule carries at most a bare `[D-N]` marker, so the index is the only route
    a later session has from a decision's number to its reasoning.
    """
    findings: list[str] = []
    directory = root / "docs" / "architecture" / "decisions"
    index = directory / "README.md"
    if not index.is_file():
        return findings
    entries = {
        path.name for path in directory.glob("D-*.md") if path.name != "README.md"
    }
    listed = set(re.findall(r"^\| \[D-[^\]]+\]\(([^)]+)\)", index.read_text(
        encoding="utf-8", errors="replace"
    ), re.MULTILINE))
    for name in sorted(entries - listed):
        findings.append(
            f"decision-index: {name} has no row in "
            f"docs/architecture/decisions/README.md \u2014 the entry is unreachable "
            f"from its number"
        )
    for name in sorted(listed - entries):
        findings.append(
            f"decision-index: docs/architecture/decisions/README.md links {name}, "
            f"which does not exist"
        )
    return findings


def run(root: Path) -> list[str]:
    return (
        check_zone_wall(root)
        + check_sideways_deps(root)
        + check_doctrine(root)
        + check_doctrine_callout(root)
        + check_review_index(root)
        + check_decision_index(root)
    )


def main() -> int:
    findings = run(ROOT)
    for finding in findings:
        print(finding)
    print(f"lint: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

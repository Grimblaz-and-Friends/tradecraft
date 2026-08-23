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
  6. decision index: every decision entry has a row in the log's index, and
     every row a file.
  7. entry references: every path reference and relative link a decision entry
     or the log's index writes resolves, is pinned to the commit it shipped at,
     or is recorded with a reason. Unlike check 1, this one reads shape rather
     than any path form: `A/B` is prose, not a reference.

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

# A decision entry's references. Markdown links claim to resolve outright;
# backticked paths are the form entries actually use most, and are what PR #104
# and PR #132 stranded. An optional title is admitted in the link form, and
# either separator in the path form -- every other pattern in this file accepts
# `[\/]`, and the one that did not was the newest.
ENTRY_LINK = re.compile(r"""\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+["'(][^)]*)?\)""")
ENTRY_PATH = re.compile(r"`([\w.-]+(?:[\\/][\w.-]+)+(?::\d+)?)`")

# What makes a slash-joined token a path claim rather than ordinary prose. A
# content filter cannot tell `A/B` -- this repo's own word for its spike
# pattern -- from `docs/x.md`, so the test is shape: a known extension, or a
# first segment that is a real root of this repository. Without it the guard
# fails lawful work, which is as bad as passing unlawful work, and the only
# escape is to write the reference less precisely.
REPO_ROOTS = frozenset({
    "skills", "tools", "docs", "lib", "commands", "agents",
    ".github", ".claude", ".", "..",
})
REF_EXTENSIONS = frozenset({
    ".md", ".py", ".yml", ".yaml", ".json", ".jsonl", ".txt", ".toml", ".cfg",
    ".ini", ".sh", ".ps1",
})

# A pin names the commit a reference shipped at, so no later move can falsify
# it. Backticks are required and a pure-decimal run is refused: this repo cites
# GitHub comment ids constantly, and `at 5380976787` is not a commit.
PINNED_REF = re.compile(r"\bat\s+`(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}`")

# References dead when this guard landed, keyed by the line that carries them
# because one entry can hold both a repairable and an unrepairable occurrence
# of the same path -- D-119 did, at :19 and :66, and a key without the line
# could not say so. Each row states why it is here.
#
# THIS SET MAY ONLY SHRINK, and the guard enforces that rather than asserting
# it: a row whose reference has come back to life is reported as stale and must
# be removed. It is a baseline, not an exemption list -- a reference added here
# is a dead reference nobody had to repair, which is the failure this guard
# exists to make impossible.
BASELINE_UNRESOLVABLE = {
    # Each states where the file WAS when its entry was written, so repointing
    # falsifies the sentence rather than repairing it.
    ("D-80-2026-08-19-spikes.md", 15, "skills/authoring/references/spikes.md"):
        "states where D-80 itself placed the file",
    ("D-102-2026-08-21-merged-list-is-an-index.md", 50,
     "skills/authoring/references/spikes.md"):
        "cites the path as evidence a references/ directory existed",
    ("D-104-2026-08-22-engagement-cell.md", 36, "engagement/references/spikes.md"):
        "states where PR #104 moved the file",
    ("D-132-2026-08-23-spikes-graduate.md", 19, "engagement/references/spikes.md"):
        "states where the file was before PR #132 moved it",
    # D-119:19 quotes "a mechanism nobody has executed", a phrase PR #132
    # deleted while moving the file, so repointing would leave the sentence
    # quoting words its target does not contain. Line 66 of the same entry was
    # a see-also whose characterization survives the move, and was repointed.
    ("D-119-2026-08-23-cost-estimate-outside-the-artifact.md", 19,
     "skills/engagement/references/spikes.md"):
        "quotes a phrase PR #132 deleted while moving the target",
    # Renamed by PR #74's reset, not deleted -- but D-53:15 calls the target
    # the "always-current statute", which repointing to an -archived path
    # would falsify.
    ("D-53-2026-08-18-log-and-statute.md", 15, "docs/architecture/constitution.md"):
        "calls the target the always-current statute; renamed to -archived",
    ("D-53-2026-08-18-log-and-statute.md", 75, "docs/architecture/evidence.md"):
        "pre-reset frozen archive; target renamed to -archived",
    # Deleted outright by the same reset. D-53 correctly records what it built.
    ("D-53-2026-08-18-log-and-statute.md", 64, "tools/check_constitution.py"):
        "target deleted by PR #74; the entry records what it built",
    ("D-53-2026-08-18-log-and-statute.md", 64,
     "tools/tests/test_check_constitution.py"):
        "target deleted by PR #74; the entry records what it built",
    # D-53 through D-69 are the pre-reset frozen archive, and nothing directs a
    # reader into it to act -- the reason this pair was dropped from the carve
    # the owner had approved.
    ("D-69-2026-08-18-trial-instrument-and-exception.md", 19, "../evidence.md"):
        "pre-reset frozen archive; target renamed to -archived",
    ("D-69-2026-08-18-trial-instrument-and-exception.md", 94, "../evidence.md"):
        "pre-reset frozen archive; target renamed to -archived",
    # Never in this repository: a path on the owner's own machine, and a
    # directory a spike created and did not commit.
    ("D-90-2026-08-20-dispatch-contract.md", 25,
     "Documents/Design/review-dispatch-overhead-measurement.md"):
        "never in this repository; the predecessor's local path",
    ("D-99-2026-08-21-dispatch-prompt-caching.md", 37, ".claude/agents"):
        "names a directory a spike created and did not commit",
}

# The fourth lawful disposition, and the one the rule was missing. A reference
# can become unrepairable AFTER this guard landed: its target is retired rather
# than moved, or a change moves the target and rewrites the text the entry
# quotes. Neither has a repoint, and the entry is frozen, so without this a
# required check reds with no compliant answer -- a guard blocking lawful work.
#
# Unlike the baseline above this may grow, because that is what makes the
# deadlock lawful. It is not an open exemption list: every row states its own
# reason, the reason is enforced non-empty, and a row is one visible line of
# diff on the pull request that created the situation.
UNREPAIRABLE_AFTER_LANDING: dict[tuple[str, int, str], str] = {}

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
    entries = {path.name for path in directory.glob("D-*.md")}
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


def check_entry_references(root: Path) -> list[str]:
    """Every reference a decision entry makes resolves, is pinned, or is recorded.

    An entry is frozen on landing but for a moved reference: the change that
    moves a target repoints every entry reference to it, and that repair is
    only lawful inside the moving change. This guard is what makes the
    permission fire at that moment -- without it the mover has no signal, and
    by the time anyone notices, no change is the mover any more. PR #104
    stranded three references that way and PR #132 stranded three more the next
    day, the second time reproducing a spike's rehearsal exactly.

    A reference is lawful four ways. It resolves. It is pinned -- written with
    the commit it shipped at, which no later move can break. It is in
    BASELINE_UNRESOLVABLE, dead before this guard existed. Or it is in
    UNREPAIRABLE_AFTER_LANDING, the disposition for a reference a later change
    made unrepairable: a retired target, or a move that also rewrote the text
    the entry quotes. Without that fourth form the guard reds with no compliant
    answer, which blocks lawful work -- as bad as passing unlawful work.

    Both recorded sets are checked for staleness: a row whose reference has
    come back to life is reported, so the baseline can only shrink and the
    record cannot rot into an exemption list nobody rereads.
    """
    findings: list[str] = []
    directory = root / "docs" / "architecture" / "decisions"
    if not directory.is_dir():
        return findings
    seen: set[tuple[str, int, str]] = set()
    # The index is scanned with the entries: it carries references of its own,
    # and unlike an entry it is editable, so its repair has an obvious home.
    paths = sorted(directory.glob("D-*.md")) + [directory / "README.md"]
    for path in paths:
        # A directory named like an entry would raise here and take down every
        # other check in the run; a traceback is a worse signal than a finding.
        if not path.is_file():
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            for ref, form, pinned in _entry_refs(line):
                key = (path.name, lineno, ref)
                seen.add(key)
                if key in BASELINE_UNRESOLVABLE or key in UNREPAIRABLE_AFTER_LANDING:
                    continue
                if pinned or _entry_ref_resolves(root, directory, ref):
                    continue
                findings.append(
                    f"entry-reference: docs/architecture/decisions/{path.name}:"
                    f"{lineno} {form} '{ref}' resolves to nothing. If you moved "
                    f"its target, repoint it here in the same change — unless "
                    f"this sentence quotes or characterises the target, in "
                    f"which case record it in UNREPAIRABLE_AFTER_LANDING with "
                    f"a reason. Do not add a pin to a landed entry. The bound "
                    f"is in docs/architecture/decisions/README.md"
                )
    findings.extend(_check_recorded_rows(root, directory, seen))
    return findings


def _check_recorded_rows(root: Path, directory: Path, seen) -> list[str]:
    """A recorded row must still name a real, still-dead reference, and a row
    in the growable set must say why. Otherwise the record rots: a stale row
    silently exempts nothing, and an unexplained one is the exemption list the
    baseline exists not to be."""
    findings: list[str] = []
    for label, rows in (
        ("BASELINE_UNRESOLVABLE", BASELINE_UNRESOLVABLE),
        ("UNREPAIRABLE_AFTER_LANDING", UNREPAIRABLE_AFTER_LANDING),
    ):
        for key, reason in sorted(rows.items()):
            name, lineno, ref = key
            if not str(reason).strip():
                findings.append(
                    f"entry-reference: {label} row {name}:{lineno} '{ref}' has "
                    f"no reason — every recorded reference states why it stands"
                )
            # A row naming an entry this tree does not contain is not stale, it
            # is inapplicable: the same module lints partial trees and fixtures.
            if not (directory / name).is_file():
                continue
            if key not in seen:
                findings.append(
                    f"entry-reference: {label} row {name}:{lineno} '{ref}' "
                    f"matches no reference in the tree — remove the stale row"
                )
            elif _entry_ref_resolves(root, directory, ref):
                findings.append(
                    f"entry-reference: {label} row {name}:{lineno} '{ref}' "
                    f"resolves again — remove the row; this record only shrinks"
                )
    return findings


def _entry_refs(line: str):
    """Repo references a decision entry makes, each with whether it is pinned.

    A bare filename is not a reference -- it names a thing in prose and claims
    nothing about where it lives, so it has nothing to repoint. A slash-joined
    token is a reference only if its shape says so (REPO_ROOTS / REF_EXTENSIONS):
    `A/B` is this repo's own name for its spike pattern, and a guard that reds
    it blocks lawful work while teaching authors to write references less
    precisely.

    The pin is scoped to the reference it follows, never to the line. Entries
    are written one paragraph per line, so a line-wide pin exempted every
    reference in a paragraph -- and one pin in the tree already sat on a line
    carrying three.
    """
    found = []
    for match in ENTRY_LINK.finditer(line):
        target = match.group(1).split("#")[0].strip()
        if target and not target.startswith(("http://", "https://", "mailto:")):
            found.append((match.end(), target, "link"))
    for match in ENTRY_PATH.finditer(line):
        # A `:N` line anchor is not part of the path it anchors into.
        ref = match.group(1).split(":")[0]
        if _is_reference_shaped(ref):
            found.append((match.end(), ref, "path"))
    found.sort()
    for index, (end, ref, form) in enumerate(found):
        # A pin covers the reference it follows and stops at the next one, so
        # `a` at <sha>; also `b` pins a and leaves b exposed.
        limit = found[index + 1][0] - len(str(found[index + 1][1])) if index + 1 < len(found) else len(line)
        window = line[end:max(end, limit)]
        yield ref, form, PINNED_REF.search(window) is not None


def _is_reference_shaped(ref: str) -> bool:
    """Shape, not content: a known extension, or a first segment that is a real
    root of this repository."""
    first = ref.replace("\\", "/").split("/")[0]
    if first in REPO_ROOTS:
        return True
    return any(ref.endswith(ext) for ext in REF_EXTENSIONS)


def _entry_ref_resolves(root: Path, directory: Path, ref: str) -> bool:
    """Resolved from the repo root, from the entry's own directory, or under
    `skills/` -- entries write the skills-relative shorthand routinely, and a
    guard that failed it would be reporting a reference a reader follows fine.

    A reference that escapes the repository never resolves, whatever sits
    beside the checkout: a sibling worktree exists locally and not in CI, and a
    guard whose answer depends on that is a guard with two answers.
    """
    ref = ref.replace("\\", "/")
    if not ref or ref.startswith("/"):
        return False
    for base in (root, directory, root / "skills"):
        candidate = base / ref
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if not _within(resolved, root):
            continue
        if candidate.exists():
            return True
    return False


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return False
    return True


def run(root: Path) -> list[str]:
    return (
        check_zone_wall(root)
        + check_sideways_deps(root)
        + check_doctrine(root)
        + check_doctrine_callout(root)
        + check_review_index(root)
        + check_decision_index(root)
        + check_entry_references(root)
    )


def main() -> int:
    findings = run(ROOT)
    for finding in findings:
        print(finding)
    print(f"lint: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

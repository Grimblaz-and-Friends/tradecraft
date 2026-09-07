"""Classify the board's intake by stated provenance, for the review trial's close-out.

The trial on #360 asks one question its cost rows cannot answer: whether the
defects that reach this repository through use went up or down once the review
stopped after its first round. Answering it means splitting every issue filed
in a window by where it came from -- found in use by a consumer or an
instrument run, routed by a review, or filed by the owner -- and comparing the
use-found rate in the trial window against the weeks before it.

This script does the mechanical half. It reads the issues, finds the sentence
each body uses to state its own provenance, and classifies on that sentence:

  use       an experience session, a cold consumer or seat, a dispatched
            recipient, or an A/B run found it
  review    a review seat surfaced or sustained it, a terminal stage or judge
            routed it, or an external reviewer raised it
  owner     the owner directed it or it came out of a design sitting
  ambiguous the provenance text names more than one of the above; the row
            shows every phrase matched and a human decides
  unstated  no provenance phrase found anywhere in the body

The judgment half stays with the close-out session: every row prints the
phrase it matched, so a classification can be checked and overridden by
reading, and an ambiguous row is never counted as any class.

Two tiers of phrase decide. A STRONG phrase is a verb of provenance -- who
found or filed the thing -- and counts anywhere in the body. A WEAK phrase
only names a mechanism, the judge, the cold seat, and counts only inside the
body's own provenance section, because a filing that discusses a mechanism
is about it, not from it. A body with no provenance section and no strong
phrase is unstated, whatever it discusses.

Reads through the GitHub CLI, or from a JSON file for tests and offline runs.
Output is ASCII; the stream setup is the shipped shim's.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from winio import utf8_stdio  # noqa: E402

# The trial opened when change A merged; the interim on #360 fixes the instant.
TRIAL_OPENED = "2026-09-04T22:34:00Z"
BASELINE_WEEKS = 3

# Two tiers. STRONG phrases state provenance wherever they appear -- a verb
# that says who found or filed the thing. WEAK phrases name the mechanism and
# only count inside a body's own provenance section, because a body that
# *discusses* the judge or the cold seat is about them, not from them.
# STRONG holds verbs of provenance only. A mechanism noun never belongs here:
# the review of PR #451 found `A/B run` and `design sitting` in this tier and
# showed them classifying a negative A/B result the owner directed as use-found.
STRONG_PATTERNS: dict[str, re.Pattern[str]] = {
    "use": re.compile(
        r"(?:cold |a |the )?consumer (?:hit|met|broke on|reached|read past)"
        r"|experience session(?:s)? (?:met|found|hit|reported|disputed|ran into)"
        r"|filed from (?:PR )?#?\d+'?s? .{0,30}experience session"
        r"|found by (?:a |the |two )?(?:cold |dispatched )?(?:consumer|seat|recipient)s?",
        re.IGNORECASE,
    ),
    "review": re.compile(
        r"surfaced by|sustained by|raised by codex|coderabbit (?:posted|raised|flagged)"
        r"|filed from (?:PR )?#?\d+'?s? .{0,20}review|found by (?:all |the )?(?:\w+ )?seats?\b"
        r"|the judge (?:routed|ruled|sent)|judge routed|ruled a decision there",
        re.IGNORECASE,
    ),
    "owner": re.compile(
        r"owner-directed|owner-stated|owner-affirmed|the owner (?:asked for|directed|requested)"
        r"|filed at the owner's (?:direction|request)|on the owner's (?:specific )?(?:instruction|direction|request)",
        re.IGNORECASE,
    ),
}

WEAK_PATTERNS: dict[str, re.Pattern[str]] = {
    "use": re.compile(
        r"experience session|cold consumer|cold seat|cold-seat|cold check|dispatched (?:seat|recipient)|A/B run",
        re.IGNORECASE,
    ),
    "review": re.compile(
        r"terminal stage|review of PR|own review|seat of PR|the judge|review'?s? (?:fix batch|finding)",
        re.IGNORECASE,
    ),
    "owner": re.compile(
        r"the owner (?:asked|ruled|named)|owner's own|at the owner's|design sitting",
        re.IGNORECASE,
    ),
}

# Where a body states its provenance, in the forms this repository's filings
# use. Headings are matched by name and their section runs to the next `## `
# heading; inline lead-ins are one line each. The census in PR #451's review:
# `## Why it will get picked up` 198 bodies, `**Warrant:**` 34, `## Provenance`
# 13, `## Why this will get picked up` 9, `**Provenance:**` 3, plus the two
# `might` variants.
PROVENANCE_SECTION_HEADING = re.compile(
    r"^(?:provenance|why (?:it|this) (?:will|might) get picked up\b.*)$", re.IGNORECASE)
PROVENANCE_INLINE = re.compile(r"^\s*\*\*(?:Warrant|Provenance):?\*\*.*$", re.IGNORECASE | re.MULTILINE)
HEADING_LINE = re.compile(r"^## +(.*?)\s*$", re.MULTILINE)


class IntakeError(Exception):
    pass


def gh(args: list[str]) -> str:
    proc = subprocess.run(
        ["gh", *args], capture_output=True, text=True, encoding="utf-8",
        errors="replace", stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        raise IntakeError(f"gh {' '.join(args)} failed: {proc.stderr.strip()[:400]}")
    return proc.stdout


def parse_when(text: str) -> datetime:
    """An ISO 8601 instant. The tool is UTC throughout, so a value with no
    offset is read as UTC -- never as the machine's zone, which shifted the
    trial window by the machine's offset in PR #451's review."""
    when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc)


def provenance_text(body: str) -> str:
    """The part of a body that states where the filing came from, or '' if none is marked."""
    pieces: list[str] = [m.group(0) for m in PROVENANCE_INLINE.finditer(body)]
    headings = list(HEADING_LINE.finditer(body))
    for i, match in enumerate(headings):
        if PROVENANCE_SECTION_HEADING.match(match.group(1)):
            end = headings[i + 1].start() if i + 1 < len(headings) else len(body)
            pieces.append(body[match.end():end])
    return "\n".join(pieces)


def _hits(scope: str, tiers: list[dict[str, re.Pattern[str]]]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for tier in tiers:
        for name, pattern in tier.items():
            seen = {m.group(0).lower(): m.group(0) for m in pattern.finditer(scope)}
            if seen:
                hits.setdefault(name, [])
                hits[name].extend(v for k, v in sorted(seen.items()) if v not in hits[name])
    return hits


def _verdict(hits: dict[str, list[str]], basis: str) -> tuple[str, list[str], str]:
    if not hits:
        return "unstated", [], basis
    if len(hits) > 1:
        return "ambiguous", [f"{name}: {', '.join(v)}" for name, v in hits.items()], basis
    (name, phrases), = hits.items()
    return name, phrases, basis


def classify(body: str) -> tuple[str, list[str], str]:
    """Return (class, phrases matched, basis) for one body.

    basis is 'provenance' when the classification came from the body's own
    provenance section, where both tiers count, and 'body' when no such
    section exists and only a STRONG phrase anywhere in the text may decide.
    """
    body = body or ""
    section = provenance_text(body)
    if section.strip():
        hits = _hits(section, [STRONG_PATTERNS, WEAK_PATTERNS])
        if hits:
            return _verdict(hits, "provenance")
    return classify_whole(body)


def classify_whole(body: str) -> tuple[str, list[str], str]:
    """Strong phrases only, anywhere in the body; topic words never decide here."""
    return _verdict(_hits(body or "", [STRONG_PATTERNS]), "body")


FETCH_LIMIT = 1000  # GitHub's search cap; gh returns exactly this many, silently, when it binds


def fetch_issues(repo: str | None, since: datetime) -> list[dict]:
    args = ["issue", "list", "--state", "all", "--limit", str(FETCH_LIMIT),
            "--search", f"created:>={since.date().isoformat()}",
            "--json", "number,title,createdAt,state,body"]
    if repo:
        args[2:2] = ["--repo", repo]
    issues = dedupe(json.loads(gh(args)))
    if len(issues) >= FETCH_LIMIT:
        print(f"trial_intake: the search returned {FETCH_LIMIT} rows, which is GitHub's cap; "
              f"the baseline may be truncated -- narrow --baseline-weeks or pin a corpus", file=sys.stderr)
    return issues


def dedupe(issues: list[dict]) -> list[dict]:
    """Paginated search has returned the same issue twice; a count is the only product here."""
    seen: set[int] = set()
    out = []
    for issue in issues:
        if issue["number"] in seen:
            continue
        seen.add(issue["number"])
        out.append(issue)
    return out


def load_issues(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def window_rows(issues: list[dict], start: datetime, end: datetime) -> list[dict]:
    rows = []
    for issue in issues:
        when = parse_when(issue["createdAt"])
        if not (start <= when < end):
            continue
        cls, phrases, basis = classify(issue.get("body") or "")
        rows.append({
            "number": issue["number"], "title": issue.get("title", ""),
            "createdAt": issue["createdAt"], "state": issue.get("state", ""),
            "class": cls, "phrases": phrases, "basis": basis,
        })
    rows.sort(key=lambda r: r["number"])
    return rows


def summarize(rows: list[dict], start: datetime, end: datetime, *, clamped_from: datetime | None = None) -> dict:
    days = max((end - start).total_seconds() / 86400.0, 1e-9)
    counts = {name: 0 for name in ("use", "review", "owner", "ambiguous", "unstated")}
    for row in rows:
        counts[row["class"]] += 1
    return {
        "start": start.isoformat(), "end": end.isoformat(), "days": round(days, 2),
        "clamped_from": clamped_from.isoformat() if clamped_from else None,
        "total": len(rows), "counts": counts,
        "per_day": {name: round(n / days, 3) for name, n in counts.items()},
    }


def earliest_created(issues: list[dict]) -> datetime | None:
    whens = [parse_when(i["createdAt"]) for i in issues if i.get("createdAt")]
    return min(whens) if whens else None


def render(name: str, summary: dict, rows: list[dict], *, verbose: bool, only: str | None = None) -> str:
    # The full instants, not dates: a window that prints as a date hides an
    # end that defaulted to now, which is what made two runs of one pinned
    # corpus disagree in the experience session on the fix batch.
    out = [f"== {name}: {summary['start']} to {summary['end']} "
           f"({summary['days']} days, {summary['total']} issues)"]
    if summary.get("clamped_from"):
        out.append(f"  (window start clamped to the earliest issue in the corpus; "
                   f"it would have begun {summary['clamped_from']})")
    out.append("  class      count  per day")
    for cls in ("use", "review", "owner", "ambiguous", "unstated"):
        out.append(f"  {cls:<10} {summary['counts'][cls]:>5}  {summary['per_day'][cls]:>7.3f}")
    if verbose:
        out.append("  " + BASIS_NOTE)
        out.append("  issue  class      basis       phrase(s) matched")
        for row in rows:
            if only and row["class"] != only:
                continue
            phrases = "; ".join(row["phrases"]) if row["phrases"] else "-"
            out.append(f"  #{row['number']:<5} {row['class']:<10} {row['basis']:<11} {phrases[:90]}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Classify the intake by stated provenance for the review trial's close-out.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Instants without an offset are read as UTC.\n" + CAVEAT + "\n" + BASIS_NOTE)
    parser.add_argument("--repo", metavar="OWNER/REPO", help="repository to read; inferred from the checkout")
    parser.add_argument("--from-file", metavar="PATH", type=Path,
                        help="read issues from a corpus file written by --dump instead of the CLI")
    parser.add_argument("--dump", metavar="PATH", type=Path,
                        help="fetch the issues and write them as a corpus file for --from-file, then classify as usual")
    parser.add_argument("--opened", metavar="ISO8601", default=TRIAL_OPENED,
                        help=f"instant the trial opened (default {TRIAL_OPENED})")
    parser.add_argument("--until", metavar="ISO8601", help="end of the trial window (default: now)")
    parser.add_argument("--baseline-weeks", type=int, default=BASELINE_WEEKS,
                        help=f"weeks before --opened that form the baseline (default {BASELINE_WEEKS})")
    parser.add_argument("--rows", action="store_true", help="print every issue with the phrase it matched")
    parser.add_argument("--only", metavar="CLASS", choices=["use", "review", "owner", "ambiguous", "unstated"],
                        help="with --rows, print only rows of this class; the counts still cover every row")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    opened = parse_when(args.opened)
    until = parse_when(args.until) if args.until else datetime.now(timezone.utc)
    baseline_start = opened - timedelta(weeks=args.baseline_weeks)

    try:
        issues = load_issues(args.from_file) if args.from_file else fetch_issues(args.repo, baseline_start)
    except IntakeError as exc:
        print(f"trial_intake: {exc}", file=sys.stderr)
        return 2
    if not isinstance(issues, list) or (issues and not isinstance(issues[0], dict) or issues and "body" not in issues[0]):
        print("trial_intake: --from-file wants a corpus written by --dump (a list of issues with bodies); "
              "a --json report cannot be read back", file=sys.stderr)
        return 2
    if args.dump:
        args.dump.write_bytes(json.dumps(issues, indent=1).encode("ascii"))

    # A baseline that begins before the repository's first issue counts days
    # with nothing to file in; clamp to the earliest issue and say so.
    first = earliest_created(issues)
    clamped_from = None
    if first is not None and first > baseline_start:
        clamped_from, baseline_start = baseline_start, first

    windows = {
        "baseline": (baseline_start, opened),
        "trial": (opened, until),
    }
    result = {}
    for name, (start, end) in windows.items():
        rows = window_rows(issues, start, end)
        result[name] = {"summary": summarize(rows, start, end,
                                             clamped_from=clamped_from if name == "baseline" else None),
                        "rows": rows}

    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    for name in ("baseline", "trial"):
        print(render(name, result[name]["summary"], result[name]["rows"], verbose=args.rows, only=args.only))
        print()
    ambiguous = sum(result[n]["summary"]["counts"]["ambiguous"] for n in result)
    unstated = sum(result[n]["summary"]["counts"]["unstated"] for n in result)
    print(f"{ambiguous} ambiguous and {unstated} unstated rows need a reader; "
          f"run with --rows to see the phrases each row matched.")
    print(CAVEAT)
    return 0


CAVEAT = ("Classification reads issue bodies as they are now, and bodies get edited, so the same window "
          "gives different counts on different days. To compare runs, pin both the corpus and the window: "
          "--dump corpus.json once, then --from-file corpus.json --until <instant> every time. "
          "(--json emits this report, not a corpus; it cannot be read back.)")

BASIS_NOTE = ("basis: 'provenance' means the class came from the body's own provenance section, where "
              "mechanism words count too; 'body' means no such section was found and only a verb of "
              "provenance anywhere in the text decided.")


if __name__ == "__main__":
    raise SystemExit(main())

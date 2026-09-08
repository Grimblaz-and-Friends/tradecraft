"""Classify the board's intake by stated provenance, for the review trial's close-out.

The trial on #360 asks one question its cost rows cannot answer: whether the
defects that reach this repository through use went up or down once the review
stopped after its first round. Answering it means splitting every issue filed
in a window by where it came from -- found in use by a consumer or an
instrument run, routed by a review, or filed by the owner -- and comparing the
use-found rate in the trial window against the weeks before it.

This script does the mechanical half. It reads the issues, finds where each
body states its own provenance, and classifies on that:

  use        an experience session, a cold consumer or seat, a dispatched
             recipient, or an A/B run found it
  review     a review seat surfaced or sustained it, a terminal stage or judge
             routed it, or an external reviewer raised it
  owner      the owner directed it or it came out of a design sitting
  session    a session noticed it while doing other work
  instrument a script or a guard raised it
  ambiguous  the provenance text names more than one of the above; the row
             shows every phrase matched and a human decides
  unstated   no provenance phrase found anywhere in the body

A body carrying the element `skills/filing/SKILL.md` requires -- one line under
`**Provenance:**` whose first word is one of the five origins -- is classified
on that word alone, and the row's basis reads `stated`. Nothing else in the
body can move it, which is the point: the origin is a key, not a phrase to be
inferred from the prose around it. The heading may open its line or follow a
list marker, and the origin may sit on the heading's line or the next; a fenced
span is an example of the element and never the body's own.

A body that carries the heading and misses the origin is classified by phrase
like any pre-element body -- moving it would reclassify every pre-element body
that carries the heading -- but the row prints `malformed-element:` and the
line, so the close-out can tell *never wrote it* from *wrote it and missed*.

The judgment half stays with the close-out session: every row prints the
phrase it matched, so a classification can be checked and overridden by
reading, and an ambiguous row is never counted as any class.

Where no origin is stated, two tiers of phrase decide. A STRONG phrase is a
verb of provenance -- who found or filed the thing -- and counts anywhere in
the body. A WEAK phrase only names a mechanism, the judge, the cold seat, and
counts only inside the body's own provenance section, because a filing that
discusses a mechanism is about it, not from it. A body with no provenance
section and no strong phrase is unstated, whatever it discusses.

The tiers stay because every body in the baseline window predates the element:
dropping them would classify the whole baseline `unstated` and empty the
comparison this script exists to make. No phrase pattern is written for the two
newer origins, so a body without the element can never be classified into
either -- they did not exist to be stated.

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

# The closed list of origins `skills/filing/SKILL.md` states, and the classes a
# row may take. The origins are the first five: `ambiguous` and `unstated` are
# what the classifier says about a body, never what a body says about itself.
ORIGINS = ("use", "review", "owner", "session", "instrument")
CLASSES = ORIGINS + ("ambiguous", "unstated")

# The element itself. The heading, then the origin as the first word after it.
# `.` as well as `:` on the heading, because bodies here already write both, and
# a classifier that refused one would report the filer's punctuation as a
# missing origin. A leading list marker and an origin on the *following* line
# are accepted too: the rule says "one line under the heading", which is the
# ordinary markdown reading of a heading with its content beneath, and a filer
# who takes it produced `unstated` -- the one class the element exists to end.
# A blockquote marker is deliberately not accepted, because `>` is how a quoted
# example is written and accepting it would widen the fenced-example hole below.
STATED_PATTERN = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?\*\*Provenance[:.]?\*\*[ \t:.\u2014\u2013-]*"
    r"(?:\r?\n[ \t]*)?[`*_]*(" + "|".join(ORIGINS) + r")\b",
    re.IGNORECASE | re.MULTILINE,
)

# The same heading with no origin behind it -- a filer who wrote the element and
# missed its first word. Reported rather than classified: see `classify`.
HEADING_PATTERN = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?\*\*Provenance[:.]?\*\*.*$",
    re.IGNORECASE | re.MULTILINE,
)

# A fenced span is an example of the element, never the body's own. Blanked to
# newlines rather than removed, so every offset and line anchor outside it holds.
FENCE_PATTERN = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)


def outside_fences(body: str) -> str:
    """`body` with every fenced span blanked, line structure preserved."""
    return FENCE_PATTERN.sub(lambda m: "\n" * m.group(0).count("\n"), body)

# Two tiers, the fallback for bodies filed before the element existed. STRONG
# phrases state provenance wherever they appear -- a verb that says who found
# or filed the thing. WEAK phrases name the mechanism and
# only count inside a body's own provenance section, because a body that
# *discusses* the judge or the cold seat is about them, not from them.
STRONG_PATTERNS: dict[str, re.Pattern[str]] = {
    "use": re.compile(
        r"(?:cold |a |the )?consumer (?:hit|met|broke on|reached|read past)"
        r"|experience session(?:s)? (?:met|found|hit|reported|disputed|ran into)"
        r"|filed from (?:PR )?#?\d+'?s? .{0,30}experience session"
        r"|found by (?:a |the |two )?(?:cold |dispatched )?(?:consumer|seat|recipient)s?"
        r"|A/B run",
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
        r"|filed at the owner's (?:direction|request)|design sitting",
        re.IGNORECASE,
    ),
}

WEAK_PATTERNS: dict[str, re.Pattern[str]] = {
    "use": re.compile(
        r"experience session|cold consumer|cold seat|cold-seat|cold check|dispatched (?:seat|recipient)",
        re.IGNORECASE,
    ),
    "review": re.compile(
        r"terminal stage|review of PR|own review|seat of PR|the judge|review'?s? (?:fix batch|finding)",
        re.IGNORECASE,
    ),
    "owner": re.compile(
        r"the owner (?:asked|ruled|named)|owner's own|at the owner's",
        re.IGNORECASE,
    ),
}

# Where a body states its provenance, in the forms this repository's filings use.
PROVENANCE_HEADINGS = (
    re.compile(r"^\s*\*\*Warrant:?\*\*.*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^## Why it will get picked up\s*$(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL),
    re.compile(r"^\s*\*\*Provenance:?\*\*.*$", re.IGNORECASE | re.MULTILINE),
)


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
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def provenance_text(body: str) -> str:
    """The part of a body that states where the filing came from, or '' if none is marked."""
    pieces: list[str] = []
    for pattern in PROVENANCE_HEADINGS:
        for match in pattern.finditer(body):
            pieces.append(match.group(1) if match.lastindex else match.group(0))
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


def stated_origins(body: str) -> dict[str, list[str]]:
    """Every origin the body states outright, as {origin: [the lines that state it]}.

    Empty for a body filed before the element existed, which is what sends the
    classification down to the phrase tiers. Fenced spans do not count: a filing
    *about* the origin list carries an example of the element, and reading that
    as the body's own origin fabricates one on the `stated` basis -- the one
    basis this tool tells the close-out nothing can move.
    """
    hits: dict[str, list[str]] = {}
    for match in STATED_PATTERN.finditer(outside_fences(body)):
        hits.setdefault(match.group(1).lower(), []).append(" ".join(match.group(0).split()))
    return hits


def malformed_elements(body: str) -> list[str]:
    """Provenance headings outside fences that carry no origin from the list.

    A body that carries the element and misses its first word classifies by
    phrase exactly like a body that never carried one, so the close-out cannot
    separate *never wrote it* from *wrote it and missed* -- and the element's
    adoption rate is the thing it exists to make readable. These lines are
    reported in the phrase column; they never change the class or the basis,
    which is what keeps every pre-element body classifying as it did.
    """
    scope = outside_fences(body)
    stated = {match.start() for match in STATED_PATTERN.finditer(scope)}
    return [" ".join(m.group(0).split()) for m in HEADING_PATTERN.finditer(scope)
            if m.start() not in stated]


def classify(body: str) -> tuple[str, list[str], str]:
    """Return (class, phrases matched, basis) for one body.

    basis is 'stated' when the body carries the provenance element and named
    its own origin, which nothing else in the body can override; 'provenance'
    when no origin was stated and the classification came from the body's own
    provenance section, where both tiers count; and 'body' when there is no
    such section either and only a STRONG phrase anywhere in the text decides.
    """
    body = body or ""
    stated = stated_origins(body)
    if stated:
        return _verdict(stated, "stated")
    section = provenance_text(body)
    if section.strip():
        hits = _hits(section, [STRONG_PATTERNS, WEAK_PATTERNS])
        if hits:
            return _flagged(_verdict(hits, "provenance"), body)
    return _flagged(classify_whole(body), body)


def _flagged(verdict: tuple[str, list[str], str], body: str) -> tuple[str, list[str], str]:
    """Prepend any malformed element to the phrases, leaving class and basis."""
    bad = malformed_elements(body)
    if not bad:
        return verdict
    name, phrases, basis = verdict
    return name, [f"malformed-element: {line}" for line in bad] + phrases, basis


def classify_whole(body: str) -> tuple[str, list[str], str]:
    """Strong phrases only, anywhere in the body; topic words never decide here."""
    return _verdict(_hits(body or "", [STRONG_PATTERNS]), "body")


def fetch_issues(repo: str | None, since: datetime) -> list[dict]:
    args = ["issue", "list", "--state", "all", "--limit", "1000",
            "--search", f"created:>={since.date().isoformat()}",
            "--json", "number,title,createdAt,state,body"]
    if repo:
        args[2:2] = ["--repo", repo]
    return json.loads(gh(args))


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


def summarize(rows: list[dict], start: datetime, end: datetime) -> dict:
    days = max((end - start).total_seconds() / 86400.0, 1e-9)
    counts = {name: 0 for name in CLASSES}
    for row in rows:
        counts[row["class"]] += 1
    return {
        "start": start.isoformat(), "end": end.isoformat(), "days": round(days, 2),
        "total": len(rows), "counts": counts,
        "per_day": {name: round(n / days, 3) for name, n in counts.items()},
    }


def render(name: str, summary: dict, rows: list[dict], *, verbose: bool, only: str | None = None) -> str:
    out = [f"== {name}: {summary['start'][:10]} to {summary['end'][:10]} "
           f"({summary['days']} days, {summary['total']} issues)"]
    out.append("  class      count  per day")
    for cls in CLASSES:
        out.append(f"  {cls:<10} {summary['counts'][cls]:>5}  {summary['per_day'][cls]:>7.3f}")
    if verbose:
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
        description="Classify the intake by stated provenance for the review trial's close-out.")
    parser.add_argument("--repo", metavar="OWNER/REPO", help="repository to read; inferred from the checkout")
    parser.add_argument("--from-file", metavar="PATH", type=Path,
                        help="read issues from a JSON dump (gh issue list --json number,title,createdAt,state,body) instead of the CLI")
    parser.add_argument("--opened", metavar="ISO8601", default=TRIAL_OPENED,
                        help=f"instant the trial opened (default {TRIAL_OPENED})")
    parser.add_argument("--until", metavar="ISO8601", help="end of the trial window (default: now)")
    parser.add_argument("--baseline-weeks", type=int, default=BASELINE_WEEKS,
                        help=f"weeks before --opened that form the baseline (default {BASELINE_WEEKS})")
    parser.add_argument("--rows", action="store_true", help="print every issue with the phrase it matched")
    parser.add_argument("--only", metavar="CLASS", choices=list(CLASSES),
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

    windows = {
        "baseline": (baseline_start, opened),
        "trial": (opened, until),
    }
    result = {}
    for name, (start, end) in windows.items():
        rows = window_rows(issues, start, end)
        result[name] = {"summary": summarize(rows, start, end), "rows": rows}

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

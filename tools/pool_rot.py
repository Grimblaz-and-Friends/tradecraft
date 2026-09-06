#!/usr/bin/env python3
"""Evidence rot in the pool: filings whose evidence the tree no longer holds (#434).

A filing carries evidence so that a session picking it up can confirm the
problem is real without redoing the discovery that found it. Evidence decays:
the file moves, the sentence is rewritten, the rule it quoted is deleted by the
very change that made the filing moot. A pool full of filings whose evidence is
gone is a pool nobody can act on, and nothing else in this repository looks.

**This is repo-only, and it has to be.** It needs the tree, which the shipped
pool script must not assume it has, and it needs the issue bodies, which
`tools/lint.py` must not fetch -- that guard runs offline by construction. So it
sits here, reads the pool through the shipped script's own policy, and reports.

**Both halves are approximate, and the second is not the one that surprised.**
Whether a quoted sentence is still findable is obviously approximate, since a
quotation may have been reflowed. The path half looked exact -- a path resolves
or it does not -- and the first run over this repository's own pool showed it is
not: of eight hits, most were filings naming a path *deliberately*, one they
propose should exist or one whose moving is what the filing is about. Skipping
fenced blocks, placeholder segments and partial matches took eight to two.

**So it closes nothing, and that is a measurement rather than caution.** A close
on this predicate would discard live filings. The only close the fade performs is
the one at the floor, where quiet is measured from `updatedAt` rather than
inferred from a pattern; `fade.closes` does not reach this command.

Usage:  python tools/pool_rot.py [--repo OWNER/REPO] [--quote-check]

  --quote-check   also look for each quoted sentence in the file beside it,
                  which is the approximate half and is off unless asked for
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "lib"))
from winio import utf8_stdio  # noqa: E402

# The pool's transport ships in the filing skill. Repo-only code importing
# shipped code is the lawful direction, and reading the policy from there rather
# than restating it is what keeps one owner for the label names.
_POOL_PATH = ROOT / "skills" / "filing" / "scripts" / "pool.py"
_spec = importlib.util.spec_from_file_location("filing_pool", _POOL_PATH)
pool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pool)

# A repository path as this repository's prose writes one: a known top-level
# directory, then a path, optionally with a line number. Anchored on the zone
# names rather than on "anything with a slash", because an issue body is full of
# URLs, `owner/repo` pairs and command fragments that are not paths in this tree.
ZONES = ("skills", "docs", "tools", "lib", "hooks", "commands", "agents", ".github", ".claude-plugin")
PATH_RE = re.compile(
    r"(?<![\w/.-])((?:%s)/[\w./-]*[\w]+\.[\w]+)(?::\d+)?" % "|".join(re.escape(z) for z in ZONES)
)

# Fenced blocks carry commands, probe transcripts and worked examples, which
# routinely name files that never existed and are not claims about the tree.
# Measured on this repository's own pool: skipping them removed two of eight
# hits, both invented filenames inside a probe.
FENCE_RE = re.compile(r"```.*?```", re.S)

# A placeholder segment, not a path: `NAME.instructions.md`, `<file>`, a bare N.
PLACEHOLDER_RE = re.compile(r"(^|/)(?:[A-Z]{2,}|<[^>]+>|N)(?=[./]|$)")

# A quoted sentence: a markdown blockquote line, or an italic or bold-italic run
# long enough not to be a passing emphasis.
QUOTE_RE = re.compile(r"^>\s+(.{40,})$", re.MULTILINE)

# Sentences an issue body quotes from ITSELF rather than from the tree -- the
# tie block's own vocabulary. Excluded so the report is about evidence.
SKIP_QUOTE_PREFIXES = ("**In plain terms:**", "In plain terms:")


class RotError(Exception):
    """A refusal a caller can act on. Printed without a traceback."""


def gh(args: list[str]) -> str:
    return pool.gh(args)


def pool_bodies(policy: dict, repo: str | None) -> list[dict]:
    """Every open, unframed issue with its body: the pool, as filings."""
    raw = gh([
        "issue", "list", *(["--repo", repo] if repo else []), "--state", "open",
        "--limit", str(pool.ISSUE_READ_LIMIT), "--json", "number,title,body,labels",
    ])
    issues = json.loads(raw)
    if len(issues) >= pool.ISSUE_READ_LIMIT:
        raise RotError(
            f"the open-issue read came back at its limit of {pool.ISSUE_READ_LIMIT}, "
            f"so it may be short and a filing past it would go unchecked"
        )
    framed = policy["framed"]["label"]
    return [it for it in issues
            if framed not in {lb["name"] for lb in it.get("labels", [])}]


def named_paths(body: str) -> list[str]:
    """Every repository path a filing names outside a fence, deduplicated.

    Three narrowings, each because the first run over this repository's own pool
    produced a false positive it removes: fenced blocks are skipped, placeholder
    segments are skipped, and a path must end in a file extension -- without
    that last one the pattern matched `docs/architecture/decisions/D` out of the
    middle of a citation.
    """
    seen, out = set(), []
    for match in PATH_RE.finditer(FENCE_RE.sub(" ", body or "")):
        path = match.group(1)
        if path in seen or PLACEHOLDER_RE.search(path):
            continue
        seen.add(path)
        out.append(path)
    return out


def quoted(body: str) -> list[str]:
    """Every quoted sentence long enough to look for."""
    out = []
    for match in QUOTE_RE.finditer(body or ""):
        text = match.group(1).strip()
        if any(text.startswith(prefix) for prefix in SKIP_QUOTE_PREFIXES):
            continue
        out.append(text)
    return out


def normalise(text: str) -> str:
    """Collapse whitespace and drop markdown emphasis, so a reflowed or
    re-emphasised sentence still matches the one that was quoted."""
    text = re.sub(r"[*`_]", "", text)
    return " ".join(text.split())


def rot(root: Path, issues: list[dict], quote_check: bool) -> list[dict]:
    """One row per filing with something missing. Exact paths, approximate quotes."""
    findings = []
    for item in issues:
        body = item.get("body") or ""
        gone = [p for p in named_paths(body) if not (root / p).exists()]
        missing_quotes = []
        if quote_check:
            haystacks = {}
            for path in named_paths(body):
                target = root / path
                if target.is_file():
                    try:
                        haystacks[path] = normalise(target.read_text(encoding="utf-8"))
                    except (OSError, UnicodeDecodeError):
                        continue
            if haystacks:
                for text in quoted(body):
                    needle = normalise(text)
                    if len(needle) >= 40 and not any(needle in h for h in haystacks.values()):
                        missing_quotes.append(text)
        if gone or missing_quotes:
            findings.append({
                "number": item["number"],
                "title": item.get("title", ""),
                "gone": gone,
                "missing_quotes": missing_quotes,
            })
    return findings


def cmd_rot(repo: str | None, quote_check: bool) -> int:
    policy = pool.load_policy(pool.find_policy(ROOT))
    issues = pool_bodies(policy, repo)
    findings = rot(ROOT, issues, quote_check)
    print(f"pool: {len(issues)}   naming something the tree no longer holds: {len(findings)}")
    for row in findings:
        print("")
        print(f"#{row['number']}  {row['title'][:70]}")
        for path in row["gone"]:
            print(f"  path gone:  {path}")
        for text in row["missing_quotes"]:
            print(f"  not found:  {text[:90]}")
    print("")
    if not findings:
        print("every path a filing names still resolves")
        return 0
    # **Nothing here closes, and the reason is a measurement rather than caution.**
    # The intent was that the path half is exact enough to close on. Run over
    # this repository's own pool it was not: after skipping fences, placeholders
    # and partial matches, the surviving hits were still mostly filings that name
    # a path deliberately -- one they propose should exist, or one that moved and
    # whose filing is about the move. A close on that predicate would discard live
    # filings. So this reports and a person decides, and the only close the fade
    # performs is the one at the floor, where quiet is measured rather than
    # inferred. `fade.closes` does not reach this command.
    print("nothing above was closed. A filing may name a path deliberately -- one "
          "it proposes, or one whose moving is what it is about -- so this reports "
          "and the reading is yours")
    return 0


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(
        prog="pool_rot.py",
        description="Filings in the pool whose evidence the tree no longer holds.",
    )
    parser.add_argument("--repo", metavar="OWNER/REPO")
    parser.add_argument("--quote-check", action="store_true")
    args = parser.parse_args(argv)
    try:
        return cmd_rot(args.repo, args.quote_check)
    except (RotError, pool.PoolError) as exc:
        print(f"pool-rot: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

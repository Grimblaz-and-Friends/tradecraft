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

**The path half looked exact and is not, and the numbers say where it goes
wrong.** A path resolves or it does not, so the intent was to close on this. Run
over this repository's own pool (106 filings, 314 paths named): eight filings hit
before any narrowing, two after. **Every one of the six that went was removed by a
filter on the path's *form*, not by any judgment about intent** -- three sat
inside fenced blocks, two lacked a file extension and were fragments out of the
middle of a citation, one was a placeholder segment. So the narrowings work and
the earlier reading of them -- that most of the eight were filings naming a path
deliberately -- was wrong about its own measurement.

**Where it does go wrong is the two that survive**, and there it is one in two:
`#195` names `hooks/emit_charter.py` and is genuine rot, and `#265` names a
filename invented inside a probe. A close on a predicate with that false-positive
rate would discard live filings, so it reports and a person reads. The only close
the fade performs is the one at the floor, where quiet is measured from
`updatedAt` rather than inferred from a pattern; `fade.closes` does not reach
this command.

Usage:  python tools/pool_rot.py [--repo OWNER/REPO]
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


class RotError(Exception):
    """A refusal a caller can act on. Printed without a traceback."""


# The pool's transport ships in the filing skill. Repo-only code importing
# shipped code is the lawful direction, and reading the policy from there rather
# than restating it is what keeps one owner for the label names.
#
# Loaded on demand rather than at import, which `tools/board.py` already paid to
# learn: at module level a tree without `skills/` -- a partial checkout, a sparse
# clone -- gives every command a raw `FileNotFoundError` traceback before
# argparse runs, `--help` included, where every other failure here is a typed
# `RotError` naming what to do.
_POOL_PATH = ROOT / "skills" / "filing" / "scripts" / "pool.py"
_pool = None


def pool_engine():
    """The shipped pool script, loaded once, with a typed refusal if it is absent."""
    global _pool
    if _pool is None:
        if not _POOL_PATH.is_file():
            raise RotError(
                f"the pool's transport is missing at {_POOL_PATH}. This check "
                f"reads the pool through the shipped script's own policy, so it "
                f"cannot run without that skill. A partial checkout is the usual "
                f"cause"
            )
        spec = importlib.util.spec_from_file_location("filing_pool", _POOL_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _pool = module
    return _pool


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
# Measured on this repository's own pool: skipping them removes three of the
# eight filings that hit before any narrowing. Two are invented filenames inside
# a probe; the third, `#359`, is a rename the filing is proposing -- so this
# skips more than invented names, which is the argument for keeping it.
FENCE_RE = re.compile(r"```.*?```", re.S)

# A placeholder segment, not a path: `NAME.instructions.md`, `<file>`, a bare N.
#
# **Named tokens rather than "any run of capitals".** The first spelling of this
# was `[A-Z]{2,}`, which reads `SKILL` out of every `.../SKILL.md`. Measured over
# this repository's own pool: of the 314 paths its filings name, that discarded
# 104 -- a third of them, silently, in the check whose whole job is to notice
# evidence nobody is checking. This spelling discards one, and the recovered 103
# all resolve, which is why the headline count is unchanged and the corpus is
# three times the size.
#
# The two spellings fail in opposite directions and only one fails quietly: a
# placeholder token this list has not met yet gets *reported*, and a person reads
# one row too many, where a real filename mistaken for a placeholder is a hit
# nobody ever sees. So the tokens are enumerated.
PLACEHOLDER_TOKENS = ("NAME", "OWNER", "REPO", "PATH", "FILE", "N", "X")
PLACEHOLDER_RE = re.compile(
    r"(^|/)(?:%s|<[^>]+>)(?=[./]|$)" % "|".join(PLACEHOLDER_TOKENS)
)


def gh(args: list[str]) -> str:
    return pool_engine().gh(args)


def pool_bodies(policy: dict, repo: str | None) -> list[dict]:
    """Every open, unframed issue with its body: the pool, as filings."""
    raw = gh([
        "issue", "list", *(["--repo", repo] if repo else []), "--state", "open",
        "--limit", str(pool_engine().ISSUE_READ_LIMIT), "--json", "number,title,body,labels",
    ])
    issues = json.loads(raw)
    if len(issues) >= pool_engine().ISSUE_READ_LIMIT:
        raise RotError(
            f"the open-issue read came back at its limit of {pool_engine().ISSUE_READ_LIMIT}, "
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


def rot(root: Path, issues: list[dict]) -> list[dict]:
    """One row per filing naming a path the tree no longer holds.

    **Paths only.** A quote half shipped here for one revision and is gone: it
    was off unless asked for, no procedure asked for it, and it searched the
    union of every file a filing named rather than the file beside the quote, so
    a sentence found anywhere counted as found. An approximate check nothing
    runs is weight, not cover.
    """
    findings = []
    for item in issues:
        body = item.get("body") or ""
        gone = [p for p in named_paths(body) if not (root / p).exists()]
        if gone:
            findings.append({
                "number": item["number"],
                "title": item.get("title", ""),
                "gone": gone,
            })
    return findings


def cmd_rot(repo: str | None) -> int:
    policy = pool_engine().load_policy(pool_engine().find_policy(ROOT))
    issues = pool_bodies(policy, repo)
    findings = rot(ROOT, issues)
    print(f"pool: {len(issues)}   naming something the tree no longer holds: {len(findings)}")
    for row in findings:
        print("")
        print(f"#{row['number']}  {row['title'][:70]}")
        for path in row["gone"]:
            print(f"  path gone:  {path}")
    print("")
    if not findings:
        print("every path a filing names still resolves")
        return 0
    # **Nothing here closes, and the reason is a measurement rather than caution.**
    # The intent was that the path half is exact enough to close on. Run over this
    # repository's own pool it is not, and the rate is what decides it: of the two
    # filings that survive every narrowing, one is genuine rot and one names a
    # filename invented inside a probe. One in two would discard a live filing.
    # So this reports and a person decides, and the only close the fade performs
    # is the one at the floor, where quiet is measured rather than inferred.
    # `fade.closes` does not reach this command.
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
    args = parser.parse_args(argv)
    try:
        return cmd_rot(args.repo)
    except RotError as exc:
        print(f"pool-rot: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # The shipped script's own refusal, named without calling the loader
        # again: where the missing transport is itself the failure, re-entering
        # `pool_engine()` here would raise over the refusal it is meant to print.
        if _pool is None or not isinstance(exc, _pool.PoolError):
            raise
        print(f"pool-rot: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

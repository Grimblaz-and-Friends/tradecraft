#!/usr/bin/env python3
"""Raise a pool item for every cell body over its ceiling (#455).

The owner ruled that the standard is splitting and the ceiling directs to
filing, not cutting content, and that it may not tell a session not to add text.
So nothing here refuses anything: this runs after a merge, reads what
`lint.cells_over_ceiling` returns, and makes sure the pool carries one open item
per cell that is over.

**Filing is not left to a session choosing to file.** Two closed issues aimed at
this behaviour by writing the rule down better -- #245 and #302 -- and the
largest cell body more than doubled between them. A rule a session may quietly
not follow is the thing that failed; a step that runs on merge is not.

**One item per cell, never one per commit.** A cell that keeps growing while its
item is open needs no second issue: the item is already open and the growth
touches it, which is what keeps the pool's quiet-window fade off it. What the
accrual reads is the number of symptoms under the cause, and a symptom is a
cell, so the cause climbs a band per two cells rather than per two commits.

Ratings are a proposal like any filer's. Severity is fixed at the scale's lower
middle because what is at stake is the same for every cell -- a session loading
prose it has no use for -- and urgency at the bottom because nothing here bites
on the next run: the item exists to be picked up, not to interrupt. The owner
confirms ratings only on the few raised to them.

**Two setup steps, named here because nothing else names them.** The cause is
passed as `--cause`, and `ci.yml` reads it from the `CELL_CEILING_CAUSE`
repository variable -- unset, the job prints one line and exits 0, so an
unarmed mechanism is indistinguishable from one with nothing to file (#482).
And the ratings below are labels this script does not create: a repository
that has not run `python skills/filing/scripts/pool.py labels` fails at
`issue create` and files nothing.

Usage:  python tools/ceiling_filing.py --cause N [--repo OWNER/REPO] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "lib"))

from winio import utf8_stdio  # noqa: E402

import lint  # noqa: E402

#: Written into every raised body so a later run recognises its own item without
#: parsing a title, which is prose and will be reworded.
MARKER = "ceiling-item:"

RATINGS = ("sev:2", "urg:1")


def marker_for(rel: str) -> str:
    """The line that identifies an item as this cell's, exactly."""
    return f"{MARKER} {rel}"


def needs_filing(over: list[tuple[str, int, int]], open_markers: set[str]) -> list[tuple[str, int, int]]:
    """The rows with no open item yet.

    Split out from every network call so the decision this script makes is
    testable without one -- the guard that matters is that a cell already
    carrying an open item is never filed twice.
    """
    return [row for row in over if marker_for(row[0]) not in open_markers]


def body_for(rel: str, size: int, ceiling: int) -> str:
    """The item's body. The measurement is its evidence and says so.

    The provenance element sits with the measurement, under `## The
    observation`, because that is where `skills/filing/references/what-a-filing-carries.md` puts it and
    this body is the worked example every filer here copies.
    """
    return (
        f"{marker_for(rel)}\n\n"
        f"> **In plain terms:** this skill's main file has grown past where it "
        f"stood when we last split it. Nothing is wrong yet and nothing was "
        f"blocked -- this is the reminder to move the parts that only matter "
        f"for one job into a side file, so a session doing any other job stops "
        f"loading them.\n\n"
        f"## The observation\n\n"
        f"`{rel}` measures **{size}** characters of body against a ceiling of "
        f"**{ceiling}**, set to where that body stood when the ratchet landed.\n\n"
        f"```\npython -c \"import sys;sys.path.insert(0,'tools');import lint,pathlib;"
        f"print(lint.cells_over_ceiling(pathlib.Path('.')))\"\n```\n\n"
        f"**Provenance:** instrument -- raised by `tools/ceiling_filing.py` on "
        f"merge.\n\n"
        f"## What it is evidence of\n\n"
        f"A ceiling here is a record of where a body stood, never a claim about "
        f"where it should be. Passing it means the cell has taken on prose since, "
        f"and the standard `skills/authoring/references/cell-structure.md` states "
        f"is that what one trigger among several needs belongs in `references/`. "
        f"The disqualifier decides which paragraphs, and that is a judgment this "
        f"item does not make.\n\n"
        f"Its whole evidence is the measurement above, which is the carve-out "
        f"`skills/filing/references/what-a-filing-carries.md` names -- there is no incident to attach, "
        f"because nothing has gone wrong yet.\n"
    )


def title_for(rel: str) -> str:
    cell = rel.rsplit("/", 2)[-2]
    return f"{cell}'s body has grown past where it stood, and one-trigger prose is what it owes"


def _gh(args: list[str], repo: str | None) -> str:
    cmd = ["gh"] + args + (["--repo", repo] if repo else [])
    # All three named, per the substrate cell: an unnamed stdin resolves
    # through a std-handle table on Windows that can still name a closed
    # handle, so the launch fails intermittently for a reason that is not
    # the command's. gh is given nothing to read.
    done = subprocess.run(cmd, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, encoding="utf-8")
    if done.returncode != 0:
        raise SystemExit(f"gh failed: {' '.join(cmd)}\n{done.stderr.strip()}")
    return done.stdout


def open_markers(repo: str | None) -> set[str]:
    """Every marker already carried by an open issue."""
    out = _gh(["issue", "list", "--state", "open", "--limit", "1000",
               "--search", MARKER, "--json", "body"], repo)
    return {
        line.strip()
        for issue in json.loads(out or "[]")
        for line in (issue.get("body") or "").splitlines()
        if line.strip().startswith(MARKER)
    }


def node_id(number: str, repo: str | None) -> str:
    """An issue's node id, which the sub-issue mutation takes instead of a number."""
    return json.loads(_gh(["issue", "view", number, "--json", "id"], repo))["id"]


def link_sub_issue(cause_id: str, symptom: str, repo: str | None) -> None:
    """Link the raised item under the standing cause.

    No `gh` subcommand sets this link -- checked against 2.80.0, where neither
    `issue create` nor `issue edit` carries a parent flag -- so it is a mutation
    over the two node ids, which is the route `skills/filing/references/naming-a-tie.md` documents.
    GitHub refuses a second parent, so re-running this on an item already linked
    is an error rather than a silent no-op, and the caller only reaches it for an
    item it just created.

    The cause's node id arrives already resolved, because resolving it here
    would put the lookup after the write it gates.
    """
    query = ("mutation($cause:ID!,$sub:ID!){addSubIssue(input:{issueId:$cause,"
             "subIssueId:$sub}){subIssue{number}}}")
    _gh(["api", "graphql", "-f", f"query={query}",
         "-F", f"cause={cause_id}",
         "-F", f"sub={node_id(symptom, repo)}"], repo)


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(description="Raise a pool item per cell over its ceiling.")
    parser.add_argument("--cause", required=True, help="issue number of the standing cause")
    parser.add_argument("--repo", default=None, metavar="OWNER/REPO")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be raised and write nothing")
    args = parser.parse_args(argv)

    over = lint.cells_over_ceiling(ROOT)
    if not over:
        print("ceiling-filing: no cell body is over its ceiling")
        return 0

    # **The cause is resolved before the first write, not after it.** The
    # ordering used to be create-then-link, so an unresolvable cause left an
    # issue created, unparented, and carrying its marker -- which the next
    # run's dedupe then reads as already filed, so the job goes green and the
    # orphan is permanent. One call up front costs a round trip and closes it.
    cause_id = None if args.dry_run else node_id(args.cause, args.repo)

    # **--dry-run consults the dedupe too.** Skipping it made the one
    # affordance for previewing this job report the opposite of what a real
    # run does in the steady state, where every over-ceiling cell already
    # carries an item.
    existing = open_markers(args.repo)
    todo = needs_filing(over, existing)
    for rel, size, ceiling in todo:
        if args.dry_run:
            print(f"ceiling-filing: would raise {rel} ({size} of {ceiling})")
            continue
        url = _gh(["issue", "create", "--title", title_for(rel),
                   "--body", body_for(rel, size, ceiling),
                   *[a for r in RATINGS for a in ("--label", r)]], args.repo).strip()
        number = url.rsplit("/", 1)[-1]
        link_sub_issue(cause_id, number, args.repo)
        print(f"ceiling-filing: raised {url} for {rel} ({size} of {ceiling})")

    for rel, size, ceiling in over:
        if (rel, size, ceiling) not in todo:
            print(f"ceiling-filing: {rel} is over ({size} of {ceiling}) and already has an open item")
    return 0


if __name__ == "__main__":
    sys.exit(main())

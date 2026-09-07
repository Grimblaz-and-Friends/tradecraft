#!/usr/bin/env python3
"""The ask declaration: every pull request body says what it needs from the
owner, or says it needs nothing.

The engagement cell makes the mark what puts an ask -- an ask that is not
marked is not put, and nothing that later happens to what carries it rules on
it. That rule fires when a session writes the ask. This fires later, at the one
moment the whole pull request body is in front of somebody, and it exists
because the failure it addresses is an ask that never announced itself: a
question carried inside a pull request body, ruled by the merge, with nothing
showing it was read (#423).

**What is checked is presence, never truth.** Whether an unmarked ask is buried
in a body is a content judgement, and content judgements do not survive
automation here: over the briefs posted to this repository every mechanical
disqualifier was clean and four of seven carried a content one, for the reason
that nothing but a reader can see them (#428). A guard grepping for
question-shaped prose would fire on nearly every body in this repository. So
this asks only that the author answered the question, and a green check is not
evidence the answer is right.

**What it buys is the moment, not the check.** A session that has just written
three options and a recommendation into a body, and must then write that it is
waiting on nothing, has to assert something false rather than merely omit
something.

This cannot live in `tools/lint.py`, which shells out to `git` alone and never
to `gh`, so it cannot see a pull request at all.

Usage:  python tools/check_ask_declaration.py --pr N [--repo OWNER/NAME]
        python tools/check_ask_declaration.py --body-file PATH

`--body-file` reads a body from disk instead of from GitHub. It is what the
tests drive and what a session checks a draft body with before opening
anything; it needs no network and no `gh`.

Requires the `gh` CLI, authenticated, for `--pr` only (CI: `GH_TOKEN`).

    0  the body carries a declaration
    1  it does not, or the body could not be read
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Shared with the shipped zone, which is the lawful direction: repo-only code
# may import shipped code. Resolved from this file rather than the working
# directory, so the script runs from any cwd.
sys.path.insert(0, str(ROOT / "lib"))
from winio import utf8_stdio  # noqa: E402

# The exact opener. Bold, because the body is markdown and the line has to be
# visible to a human skimming it -- this guard is the enforcement of a habit,
# and a marker nobody sees in the rendered body would enforce a habit nobody
# performs. Matched on the stripped line so list markers and blockquote
# prefixes do not defeat it, and case-sensitively: a marker that drifts in
# case is a marker with two spellings, and the next session copies the wrong
# one.
MARKER = "**Waiting on you:**"

WHAT_TO_WRITE = (
    "Add a line to the pull request body naming what waits on the owner, or "
    "saying that nothing does:\n"
    f"    {MARKER} nothing -- no ask is marked on this change.\n"
    f"    {MARKER} the tie question, marked on #123.\n"
    "An ask is put by marking what carries it; this line is where the change "
    "says whether it did."
)


class DeclarationError(Exception):
    """A body that could not be read. Distinct from a body that lacks one."""


def declaration(body: str) -> str | None:
    """The declaration's content, or None where the body carries none.

    A line whose stripped form opens with the marker and has something after
    it. The remainder is required: an empty declaration would be a check that
    cannot fail, which is the one shape of guard this repository treats as
    worse than no guard at all.
    """
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(MARKER):
            rest = stripped[len(MARKER):].strip()
            if rest:
                return rest
    return None


def _gh(*args: str) -> str:
    """Run `gh`, returning stdout; any non-zero exit raises."""
    try:
        proc = subprocess.run(
            ["gh", *args], stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8",
        )
    except OSError as exc:                      # gh absent from the runner
        raise DeclarationError(f"could not run `gh {' '.join(args)}`: {exc}") from exc
    if proc.returncode != 0:
        raise DeclarationError(
            f"`gh {' '.join(args)}` failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout


def body_from_pr(number: str, repo: str | None) -> str:
    args = ["pr", "view", number, "--json", "body"]
    if repo:
        args += ["--repo", repo]
    try:
        payload = json.loads(_gh(*args))
    except json.JSONDecodeError as exc:
        raise DeclarationError(f"`gh pr view` returned no JSON body: {exc}") from exc
    body = payload.get("body")
    if body is None:
        raise DeclarationError(f"pull request {number} carries no body field")
    return body


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pr", help="pull request number to read from GitHub")
    source.add_argument("--body-file", help="read the body from this file instead")
    parser.add_argument("--repo", help="OWNER/NAME; defaults to the checkout's remote")
    args = parser.parse_args(argv)

    try:
        if args.body_file:
            body = Path(args.body_file).read_text(encoding="utf-8")
        else:
            body = body_from_pr(args.pr, args.repo)
    except DeclarationError as exc:
        print(f"ask declaration: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ask declaration: could not read body file: {exc}", file=sys.stderr)
        return 1

    found = declaration(body)
    if found is None:
        print("ask declaration: missing.", file=sys.stderr)
        print(WHAT_TO_WRITE, file=sys.stderr)
        return 1

    print(f"ask declaration: present -- {found}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

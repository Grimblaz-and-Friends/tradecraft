#!/usr/bin/env python3
"""The doctrine callout: label and speak on any PR that changes `AGENTS.md`.

The owner reads the doctrine diff himself before merging (doctrine, "The two
ceremony moments"). The first mechanism for that was `.github/CODEOWNERS`,
which fires by auto-requesting a review — and GitHub never requests a review
from a PR's own author. Every PR in this repo is authored by the owner's
account, so the callout structurally could not reach the one human who merges:
#74, #77 and #78 all touched `AGENTS.md` and all returned `reviewRequests: []`.
CODEOWNERS stays for the shield icon and for a future non-owner contributor;
this is what actually reaches him, on the two surfaces he is looking at when he
merges — the label in the PR header, and a comment that lands in notifications.

Idempotent by marker, not by memory: the comment carries `MARKER`, and a re-run
that finds it leaves the thread alone. A PR that stops touching doctrine has
the label removed and the comment edited to say so, because a callout that
outlives its reason is the same defect this script exists to fix.

**Every failure is loud.** Unreadable paths, a rejected label call, a rejected
comment call — each exits non-zero and turns the check red. The withdrawn
version-bump predecessor failed open four ways while printing a clean pass, and
a callout that silently no-ops is not a milder form of this bug: it *is* this
bug. Nothing here degrades to "probably fine".

Usage:  python tools/doctrine_callout.py --pr N [--repo OWNER/NAME] [--dry-run]
Requires the `gh` CLI, authenticated (CI: `GH_TOKEN: ${{ github.token }}` with
`pull-requests: write` and `issues: write`).

    0  the PR's state matches its diff — labelled and commented, or neither
    1  something could not be established or could not be applied
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

# Matches `.github/CODEOWNERS`. Widening this to skills or decisions is a
# different requirement and wants its own incident.
DOCTRINE_PATHS = ("AGENTS.md", "CLAUDE.md")

LABEL = "doctrine"
LABEL_COLOR = "5319e7"
LABEL_DESC = "Changes AGENTS.md or CLAUDE.md — read the diff before merging"

# The comment's identity lives in the body, not in a stored id: a marker
# survives a lost workflow run, a re-run, and a re-created check, none of which
# a side-channel record would.
MARKER = "<!-- tradecraft:doctrine-callout -->"
# A second marker rather than a prose match: the withdrawn state has to be
# machine-readable, and matching the visible sentence would break the moment
# someone reworded it.
WITHDRAWN_MARKER = "<!-- tradecraft:doctrine-callout:withdrawn -->"

CALLOUT = f"""{MARKER}
**This PR changes the doctrine.** Read the `AGENTS.md` diff before merging — \
that reading is the release gate, and nothing else performs it.

Touched: {{files}}

<sub>Posted by `tools/doctrine_callout.py`. `CODEOWNERS` cannot request a \
review from a PR's own author, and every PR here is the owner's.</sub>"""

WITHDRAWN = f"""{MARKER}{WITHDRAWN_MARKER}
~~This PR changes the doctrine.~~ **Withdrawn:** the PR no longer touches \
`AGENTS.md` or `CLAUDE.md`. Nothing here needs the owner's doctrine read.

<sub>Posted by `tools/doctrine_callout.py`.</sub>"""

OK, FAILED = 0, 1


class CalloutError(RuntimeError):
    """Something could not be established or applied. Never swallowed."""


def _gh(*args: str) -> str:
    """Run `gh`, returning stdout; any non-zero exit raises `CalloutError`.

    stderr rides in the message because a failure that names the call but not
    the reason leaves the operator with nothing to act on — and this script is
    read only when it has gone red.
    """
    try:
        proc = subprocess.run(
            ["gh", *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except OSError as exc:                      # gh absent from the runner
        raise CalloutError(f"could not run `gh {' '.join(args)}`: {exc}") from exc
    if proc.returncode != 0:
        raise CalloutError(
            f"`gh {' '.join(args)}` failed ({proc.returncode})"
            + (f": {(proc.stderr or '').strip()}" if proc.stderr else "")
        )
    return proc.stdout or ""


def touched_doctrine(paths: list[str]) -> list[str]:
    """The doctrine files among a PR's changed paths, in DOCTRINE_PATHS order.

    Exact match on the repo-root path. A `docs/AGENTS.md` would not be the
    doctrine, and matching by basename would call out a PR that never touched
    it — a false callout trains the owner to ignore the true one.
    """
    changed = set(paths)
    return [p for p in DOCTRINE_PATHS if p in changed]


def changed_paths(pr: str, repo: str | None) -> list[str]:
    """The PR's changed paths, from GitHub's own diff.

    Deliberately not a local merge-base diff: CI checks out a merge commit and
    the base ref must be fetched deep enough for a merge base to exist, so a
    local reading has two ways to be quietly wrong about the very question
    this script answers. GitHub already knows the answer; ask it.
    """
    args = ["pr", "diff", pr, "--name-only"]
    if repo:
        args += ["--repo", repo]
    out = _gh(*args)
    return [line.strip() for line in out.splitlines() if line.strip()]


def find_callout(comments: list[dict]) -> dict | None:
    """The existing callout comment, if the marker is on the thread."""
    for comment in comments:
        if MARKER in (comment.get("body") or ""):
            return comment
    return None


def _slug(repo: str | None) -> str:
    """`{owner}/{repo}` are gh's own placeholders, filled from the checkout."""
    return repo or "{owner}/{repo}"


def _state(pr: str, repo: str | None) -> tuple[list[dict], set[str]]:
    """The PR's comments and label names.

    REST rather than `gh pr view --json comments`, because that view returns
    each comment's GraphQL node id and the edit endpoint takes the numeric REST
    id — a mismatch that would only surface on the withdrawal path, which is
    the rarest one and therefore the last to be noticed. `--paginate` with a
    `--jq` projection yields one JSON object per line across every page; a bare
    `--paginate` concatenates page arrays into something `json.loads` refuses.
    """
    slug = _slug(repo)
    labels = _json(_gh("api", f"repos/{slug}/issues/{pr}",
                       "--jq", "[.labels[].name]"), "the PR's labels")
    if not isinstance(labels, list):
        raise CalloutError("the PR's labels came back as something other than a list")

    comments = []
    for line in _gh("api", "--paginate", f"repos/{slug}/issues/{pr}/comments?per_page=100",
                    "--jq", ".[] | {id, body}").splitlines():
        if line.strip():
            comments.append(_json(line, "a PR comment"))
    return comments, set(labels)


def _json(raw: str, what: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CalloutError(f"could not parse {what}: {exc}") from exc


def _ensure_label(repo: str | None) -> None:
    """Create the label if absent. `--force` makes an existing label a no-op.

    The mechanism must not depend on a label a human can delete from the repo's
    settings; that would be a second silent-failure road.
    """
    args = ["label", "create", LABEL, "--color", LABEL_COLOR,
            "--description", LABEL_DESC, "--force"]
    if repo:
        args += ["--repo", repo]
    _gh(*args)


def _edit_label(pr: str, repo: str | None, *, add: bool) -> None:
    args = ["pr", "edit", pr, "--add-label" if add else "--remove-label", LABEL]
    if repo:
        args += ["--repo", repo]
    _gh(*args)


def _body(touched: list[str]) -> str:
    return CALLOUT.format(files=", ".join(f"`{f}`" for f in touched))


def _edit_comment(comment_id: object, repo: str | None, body: str) -> None:
    if comment_id is None:
        raise CalloutError("the callout comment came back without an id — cannot edit it")
    _gh("api", "--method", "PATCH",
        f"repos/{_slug(repo)}/issues/comments/{comment_id}", "-f", f"body={body}")


def run(pr: str, repo: str | None, *, dry_run: bool = False) -> tuple[int, list[str]]:
    """Bring the PR's label and comment into agreement with its diff."""
    lines: list[str] = []
    touched = touched_doctrine(changed_paths(pr, repo))
    comments, labels = _state(pr, repo)
    existing = find_callout(comments)

    if not touched:
        lines.append(f"doctrine-callout: PR #{pr} touches no doctrine file")
        if LABEL in labels:
            lines.append(f"doctrine-callout: removing the {LABEL} label")
            if not dry_run:
                _edit_label(pr, repo, add=False)
        if existing is None:
            return OK, lines
        # The PR dropped its doctrine change after the callout went out. Left
        # standing, it would be exactly what this script exists to end: a
        # notice describing something that is not so.
        lines.append("doctrine-callout: withdrawing the callout that no longer applies")
        if not dry_run:
            _edit_comment(existing.get("id"), repo, WITHDRAWN)
        return OK, lines

    lines.append(f"doctrine-callout: PR #{pr} touches {', '.join(touched)}")
    if LABEL in labels:
        lines.append(f"doctrine-callout: {LABEL} label already applied")
    else:
        lines.append(f"doctrine-callout: applying the {LABEL} label")
        if not dry_run:
            _ensure_label(repo)
            _edit_label(pr, repo, add=True)

    if existing is not None:
        # A callout withdrawn earlier and then re-earned: restore it, or the
        # marker's own idempotence would pin the thread to the withdrawn text.
        if WITHDRAWN_MARKER in (existing.get("body") or ""):
            lines.append("doctrine-callout: reinstating a callout withdrawn earlier")
            if not dry_run:
                _edit_comment(existing.get("id"), repo, _body(touched))
        else:
            lines.append("doctrine-callout: callout already on the thread, not duplicated")
        return OK, lines

    lines.append("doctrine-callout: posting the callout")
    if not dry_run:
        args = ["pr", "comment", pr, "--body", _body(touched)]
        if repo:
            args += ["--repo", repo]
        _gh(*args)
    return OK, lines



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--pr", required=True, help="pull request number")
    parser.add_argument("--repo", default=None, help="OWNER/NAME (default: the checkout's)")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change; touch nothing")
    args = parser.parse_args(argv)
    try:
        status, lines = run(args.pr, args.repo, dry_run=args.dry_run)
    except CalloutError as exc:
        print(f"doctrine-callout: {exc}", file=sys.stderr)
        print("doctrine-callout: FAILED — the owner's doctrine callout did not "
              "go out. This is not a warning; see tools/doctrine_callout.py",
              file=sys.stderr)
        return FAILED
    for line in lines:
        print(line)
    return status


if __name__ == "__main__":
    sys.exit(main())

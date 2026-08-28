#!/usr/bin/env python3
"""The doctrine callout: label and speak on any PR that changes the doctrine.

The owner reads the doctrine diff himself before merging (doctrine, "The
ceremony moments, here"; the charter states the rule it applies). The first mechanism for that was `.github/CODEOWNERS`,
which fires by auto-requesting a review — and GitHub never requests a review
from a pull request's own author (exactly so for an individual code-owner
entry; a team entry containing the author is still requested). Sessions here
run as the owner's account, so today every PR is authored by the one human who
merges, and the callout structurally could not reach him: the issue timelines
of #74, #77 and #78 carry no `review_requested` event at all. CODEOWNERS stays
for the shield icon and for a future non-owner contributor; this is what
actually reaches him, on the two surfaces he is looking at when he merges — the
label in the PR header, and a comment that lands in notifications.

Idempotent by content, not by memory: the callout is found by `MARKER` and then
rendered fresh each run, and the comment is edited only when what it says has
stopped matching what the PR does. One rule covers withdrawal, reinstatement,
and a `Touched:` list that a later push made stale — a callout that outlives its
reason is the same defect as one that never fires.

**Ownership is checked, not assumed.** A comment carrying the marker but written
by anyone else is not ours: we neither treat it as the callout nor ever edit it.
The accidental case is the common one — this repo posts review reports as PR
comments, and a report about this mechanism quotes the marker. Against such a
comment the callout still fires, with the unexpected author named in the log.
The degradation is deliberately toward speaking: this exists because a callout
did not fire, so a duplicate is noise while a missing one is the bug.

**Every failure is loud.** Unreadable paths, an empty change set, a rejected
label call, a rejected comment call — each exits non-zero, turns the check red,
and emits a workflow error annotation. The withdrawn version-bump predecessor
failed open four ways while printing a clean pass, and a callout that silently
no-ops is not a milder form of this bug: it *is* this bug.

Usage:  python tools/doctrine_callout.py --pr N [--repo OWNER/NAME] [--dry-run]
Requires the `gh` CLI, authenticated (CI: `GH_TOKEN` from the workflow token,
with `pull-requests: write`, `issues: write` and `contents: read`).

    0  the PR's state matches its diff — labelled and commented, or neither
    1  something could not be established or could not be applied
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Shared with the shipped zone, which is the lawful direction: repo-only
# code may import shipped code. Resolved from this file rather than the
# working directory, so the script runs from any cwd.
sys.path.insert(0, str(ROOT / "lib"))
from winio import utf8_stdio  # noqa: E402

# Matches `.github/CODEOWNERS`. Widening this to skills or decisions is a
# different requirement and wants its own incident. The charter cell is
# not a widening: it holds the half of the doctrine that moved out of
# `AGENTS.md`, and it also ships to consumers, so omitting it would shrink
# the owner's read at the moment the material became more consequential.
DOCTRINE_PATHS = ("AGENTS.md", "CLAUDE.md", "skills/charter/SKILL.md")

LABEL = "doctrine"
LABEL_COLOR = "5319e7"
LABEL_DESC = "Changes the doctrine or the shipped charter -- read the diff before merging"

# The one standing coupling to an identity. Its tripwire is the log line in
# `run()`: under a future identity change (a PAT, a GitHub App) the callout
# double-posts AND names the unexpected author, which is a loud wrong answer
# rather than a silent one.
EXPECTED_AUTHOR = "github-actions[bot]"

# The callout's identity lives in its body, not in a stored id: a marker
# survives a lost workflow run, a re-run, and a re-created check, none of which
# a side-channel record would.
MARKER = "<!-- tradecraft:doctrine-callout -->"

CALLOUT = f"""{MARKER}
**This PR changes the doctrine.** Read the {{files}} diff before merging -- \
nothing else performs that read.

Touched: {{files}}

{{always_on}}

<sub>Posted by `tools/doctrine_callout.py`. `CODEOWNERS` cannot request a \
review from a pull request's own author, and today every PR here is the \
owner's.</sub>"""

WITHDRAWN = f"""{MARKER}
~~This PR changes the doctrine.~~ **Withdrawn:** the PR no longer touches \
`AGENTS.md`, `CLAUDE.md` or the charter cell. Nothing here needs the
owner's doctrine read.

<sub>Posted by `tools/doctrine_callout.py`.</sub>"""

OK, FAILED = 0, 1

# A rejected write puts the whole comment body in the argv, which would bury
# the reason under six lines of markdown in the one log an operator reads only
# when it has already gone red.
ARG_ELIDE = 60


class CalloutError(RuntimeError):
    """Something could not be established or applied. Never swallowed."""


def _say(lines: list[str], message: str) -> None:
    """Record a progress line and emit it now.

    Printed as it happens rather than collected and returned: `run()` raising
    loses everything it accumulated, so a red check would name the failing call
    without showing which stage had been reached.
    """
    lines.append(message)
    print(message, flush=True)


def _shown(args: tuple[str, ...]) -> str:
    """The argv, flattened to one line and long values elided.

    Flattened first: truncating a markdown body at a character count still
    leaves the newlines inside the surviving prefix, which is the burial this
    exists to prevent — the reason has to be on the same line as the call.
    """
    out = []
    for arg in args:
        flat = " ".join(arg.split())
        out.append(flat if len(flat) <= ARG_ELIDE
                   else f"{flat[:ARG_ELIDE]}...[{len(arg)} chars]")
    return " ".join(out)


def _gh(*args: str) -> str:
    """Run `gh`, returning stdout; any non-zero exit raises `CalloutError`.

    stderr rides in the message because a failure that names the call but not
    the reason leaves the operator with nothing to act on — and long arguments
    are elided so the reason is not the seventh line of the message.
    """
    try:
        proc = subprocess.run(
            ["gh", *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except OSError as exc:                      # gh absent from the runner
        raise CalloutError(f"could not run `gh {_shown(args)}`: {exc}") from exc
    if proc.returncode != 0:
        raise CalloutError(
            f"`gh {_shown(args)}` failed ({proc.returncode})"
            + (f": {(proc.stderr or '').strip()}" if proc.stderr else "")
        )
    return proc.stdout or ""


def touched_doctrine(paths: list[str]) -> list[str]:
    """The doctrine files among a PR's changed paths, in DOCTRINE_PATHS order.

    Exact match on the repo-root path. A `docs/AGENTS.md` would not be the
    doctrine, and matching by basename would call out a PR that never touched
    it — a false callout trains the owner to ignore the true one. A rename out
    of any of them escapes this match (git reports only the new path, at
    similarity as low as 83% on this repo's own #74), and is caught instead by
    `tools/lint.py`, which fails a required check when `AGENTS.md`, `CLAUDE.md`
    or the charter cell goes missing -- the last of those only since the
    charter got a guard of its own; before that this sentence named a backstop
    that did not exist for it.
    """
    changed = set(paths)
    return [p for p in DOCTRINE_PATHS if p in changed]


def changed_paths(pr: str, repo: str | None) -> list[str]:
    """The PR's changed paths, from GitHub's own diff.

    Deliberately not a local merge-base diff: CI checks out a merge commit and
    the base ref must be fetched deep enough for a merge base to exist, so a
    local reading has two ways to be quietly wrong about the very question this
    script answers. GitHub already knows the answer; ask it.

    An empty result raises rather than reading as "no doctrine files" — but not
    because it is ambiguous. `gh pr diff` exits non-zero on every read failure
    (a missing PR, a missing repo, no credentials), and `_gh` already raises on
    that, so an empty list at exit 0 does mean a genuinely fileless diff. It
    happens: a branch of only empty commits, or one whose changes are fully
    reverted within it. Such a PR is refused because the alternative is to run
    the withdrawal path on it, and a wrong withdrawal writes a false statement
    onto the PR, while a red check on a job no ruleset requires is re-runnable.
    """
    args = ["pr", "diff", str(pr), "--name-only"]
    if repo:
        args += ["--repo", repo]
    paths = [line.strip() for line in _gh(*args).splitlines() if line.strip()]
    if not paths:
        raise CalloutError(
            f"`gh pr diff {pr} --name-only` returned no paths, so this PR "
            "changes no files at all. Refused rather than treated as a dropped "
            "doctrine change, which would withdraw the callout and state "
            "something false on the PR. Re-run once the PR has a diff"
        )
    return paths


def find_callout(comments: list[dict]) -> tuple[dict | None, list[str]]:
    """Return (our callout, the authors of marker-bearing comments that are not).

    Ownership is half the identity. Without it, anyone who can comment — the
    repo is public, so anyone at all — suppresses the callout by quoting the
    marker, and the edit path overwrites a comment we did not write.
    """
    ours, foreign = None, []
    for comment in comments:
        if MARKER not in (comment.get("body") or ""):
            continue
        if comment.get("author") == EXPECTED_AUTHOR:
            if ours is None:
                ours = comment
        else:
            foreign.append(str(comment.get("author")))
    return ours, foreign


def _slug(repo: str | None) -> str:
    """`{owner}/{repo}` are gh's own placeholders, filled from the checkout."""
    return repo or "{owner}/{repo}"


def _json(raw: str, what: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CalloutError(f"could not parse {what}: {exc}") from exc


def _state(pr: str, repo: str | None) -> tuple[list[dict], set[str]]:
    """The PR's comments (id, body, author) and label names.

    REST rather than `gh pr view --json comments`, because that view returns
    each comment's GraphQL node id and the edit endpoint takes the numeric REST
    id — a mismatch that would surface only on the edit path, the rarest one and
    therefore the last to be noticed. `--paginate` walks past the 30-per-page
    default that would otherwise hide the callout behind a long thread, and the
    `--jq` projection is what makes those pages parseable one object per line.
    """
    slug = _slug(repo)
    labels = _json(_gh("api", f"repos/{slug}/issues/{pr}",
                       "--jq", "[.labels[].name]"), "the PR's labels")
    if not isinstance(labels, list):
        raise CalloutError("the PR's labels came back as something other than a list")

    comments = []
    for line in _gh("api", "--paginate", f"repos/{slug}/issues/{pr}/comments?per_page=100",
                    "--jq", ".[] | {id, body, author: .user.login}").splitlines():
        if line.strip():
            comments.append(_json(line, "a PR comment"))
    return comments, set(labels)


def _ensure_label(repo: str | None) -> None:
    """Create the label, or update it in place where the repo already has it.

    `--force` is what makes the call idempotent: without it `label create`
    errors on the second doctrine PR and turns a lawful change red. It also
    means a human's edit to the label's color or description is reverted here.

    The mechanism must not depend on a label a human can delete from the repo's
    settings; that would be a second silent-failure road.
    """
    args = ["label", "create", LABEL, "--color", LABEL_COLOR,
            "--description", LABEL_DESC, "--force"]
    if repo:
        args += ["--repo", repo]
    _gh(*args)


def _edit_label(pr: str, repo: str | None, *, add: bool) -> None:
    args = ["pr", "edit", str(pr), "--add-label" if add else "--remove-label", LABEL]
    if repo:
        args += ["--repo", repo]
    _gh(*args)


# What the callout prices, and against what. Each row is a size and the
# ceiling that governs *exactly* that size -- the doctrine's two-file sum was
# once rendered against AGENTS.md's budget alone, asserting a ceiling that did
# not exist. Module level so a test can name the binding rather than infer it
# from a rendered string: the label carries the ceiling, so reordering rows is
# harmless and substituting one size for another is not.
PRICED = (
    # label,          lint constant,            figure_always_on data key
    ("AGENTS.md",     "AGENTS_BUDGET_CHARS",    "agents"),
    ("CLAUDE.md",     "POINTER_BUDGET_CHARS",   "pointer"),
    ("charter body",  "CHARTER_BUDGET_CHARS",   "charter"),
)


def _always_on_line(root: Path | None = None, base: str | None = None) -> str:
    """The size of what every session reads, where the owner is when he merges.

    A budget only bites where somebody sees it, and this one has always been
    read after the fact -- in a write-up, by a session that had already decided
    what to add. The merge surface is the one moment the number can still
    change an outcome.

    The delta is the half that answers his actual question. An absolute total
    cannot tell him whether this PR grew the surface or shrank it, and growth
    is the thing the ceiling exists to resist -- a number with no direction
    reproduces the defect it was added to end.

    `root` resolves at call time rather than as a default, because a default
    binds at definition and a test patching the module attribute would silently
    measure the real repository instead.

    A failure to derive is stated rather than dropped, with the exception's own
    message: a callout that quietly loses its figure is one nobody can trust
    the rest of, and one that loses the reason cannot be acted on either.
    """
    root = ROOT if root is None else root
    try:
        spec = importlib.util.spec_from_file_location(
            "repo_figures", root / "tools" / "figures.py"
        )
        figures = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(figures)
        data = figures.figure_always_on(root)["data"]
        priced = [
            (label, data[key], getattr(figures.lint, const))
            for label, const, key in PRICED
        ]
        movement = _always_on_delta(figures, root, base)
    except Exception as exc:  # noqa: BLE001 -- reported, never swallowed
        return f"_Always-on surface: not derived ({type(exc).__name__}: {exc})._"
    return (
        f"Always-on surface: **{data['repo_total']:,}** chars here{movement}, "
        f"**{data['adopter_total']:,}** from this practice for an adopter -- "
        + ", ".join(f"{label} {size:,} of {budget:,}" for label, size, budget in priced)
        # `entries`/`roster_here`, never `cells`/`roster`: the total this
        # sentence opens with is built from the roster THIS repository loads,
        # under `.claude/skills/`, and the adopter's roster under `skills/` is
        # a different set. Printing the second as the breakdown of the first
        # decomposed to a number the sentence did not state -- invisible while
        # the two agree, and wrong exactly on the trees where the roster guard
        # is red, which this job posts on because it carries no `needs:` on
        # `lint-and-test`. Same class as the two-file sum this line once
        # rendered against one file's budget. [PR #210 review, M1]
        + f", {data['entries']} roster name/description {data['roster_here']:,}."
    )


def _always_on_delta(figures, root: Path, base: str | None) -> str:
    """This PR's own movement, or why it could not be measured.

    A delta against a guessed base would be worse than none, so an unreadable
    base still yields no number. What it no longer yields is silence. This
    returned an empty string on any failure, which renders byte-identically to
    a run that was given no base at all -- so a base that could not be read
    looked exactly like a caller that never asked, and the callout shipped for
    a full cycle without its delta in the one environment that runs it. Nobody
    could have seen it from the comment. Its sibling `_always_on_line` names
    its own failures for this reason; one function answering the same question
    two opposite ways is how the gap survived.

    The base is named because it is the actionable half: the failure is
    essentially always that the object is not in this clone.
    """
    if not base:
        return ""
    try:
        before = figures.always_on_at(root, base)
    except Exception as exc:  # noqa: BLE001 -- reported, never swallowed
        return f" (movement not derived: {type(exc).__name__} reading {base})"
    change = figures.figure_always_on(root)["data"]["repo_total"] - before
    return f" ({change:+,} this PR)"


def _body_from(files: str, base: str | None = None) -> str:
    """The rendered callout for an already-joined file list.

    Split out so a test can build the exact body the callout posts without
    re-deriving the join -- the previous shape let a test format the template
    directly, which meant a new field could be added to the body and the test
    would keep asserting the old one.
    """
    return CALLOUT.format(files=files, always_on=_always_on_line(base=base))


def _body(touched: list[str], base: str | None = None) -> str:
    return _body_from(", ".join(f"`{f}`" for f in touched), base=base)


def _edit_comment(comment_id: object, repo: str | None, body: str) -> None:
    if comment_id is None:
        raise CalloutError("the callout comment came back without an id -- cannot edit it")
    _gh("api", "--method", "PATCH",
        f"repos/{_slug(repo)}/issues/comments/{comment_id}", "-f", f"body={body}")


def _post_comment(pr: str, repo: str | None, body: str) -> None:
    args = ["pr", "comment", str(pr), "--body", body]
    if repo:
        args += ["--repo", repo]
    _gh(*args)


def run(pr: str, repo: str | None, *, dry_run: bool = False,
        base: str | None = None) -> tuple[int, list[str]]:
    """Bring the PR's label and comment into agreement with its diff."""
    lines: list[str] = []
    touched = touched_doctrine(changed_paths(pr, repo))
    comments, labels = _state(pr, repo)
    ours, foreign = find_callout(comments)

    for author in foreign:
        _say(lines, "doctrine-callout: ignoring a marker-bearing comment by "
                    f"{author} (expected {EXPECTED_AUTHOR})")

    if touched:
        _say(lines, f"doctrine-callout: PR #{pr} touches {', '.join(touched)}")
    else:
        _say(lines, f"doctrine-callout: PR #{pr} touches no doctrine file")

    # The label tracks the diff in both directions.
    if touched and LABEL not in labels:
        _say(lines, f"doctrine-callout: applying the {LABEL} label")
        if not dry_run:
            _ensure_label(repo)
            _edit_label(pr, repo, add=True)
    elif not touched and LABEL in labels:
        _say(lines, f"doctrine-callout: removing the {LABEL} label")
        if not dry_run:
            _edit_label(pr, repo, add=False)

    # One rule for the comment: render what the PR deserves right now, and make
    # the thread say that. Posting, withdrawing, reinstating and refreshing a
    # stale `Touched:` list are the same operation seen at four moments.
    if touched:
        desired = _body(touched, base=base)
    elif ours is not None:
        desired = WITHDRAWN          # it says something that is no longer so
    else:
        desired = None               # nothing to say, and nothing said

    if desired is None:
        return OK, lines
    if ours is None:
        _say(lines, "doctrine-callout: posting the callout")
        if not dry_run:
            _post_comment(pr, repo, desired)
    elif (ours.get("body") or "").strip() != desired.strip():
        _say(lines, "doctrine-callout: updating the callout to match the PR")
        if not dry_run:
            _edit_comment(ours.get("id"), repo, desired)
    else:
        _say(lines, "doctrine-callout: callout already says this, not duplicated")
    return OK, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(
        description=
        "Label and comment on a pull request that changes the doctrine or the shipped charter, so the owner reads the diff before merging. Exit 0 when the PR state matches its diff; non-zero turns the check red.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--pr", required=True, type=int, help="pull request number")
    parser.add_argument("--repo", default=None, help="OWNER/NAME (default: the checkout's)")
    parser.add_argument("--base", default=None,
                        help="revision to measure the always-on delta against; "
                             "omitted, the callout states the total and no delta")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change; touch nothing")
    args = parser.parse_args(argv)
    try:
        status, _ = run(args.pr, args.repo, dry_run=args.dry_run, base=args.base)
    except CalloutError as exc:
        reason = " ".join(str(exc).split())
        # A workflow error annotation, so the reason reaches the checks panel
        # and the run summary rather than only the expanded step log.
        print(f"::error title=doctrine-callout::{reason}", flush=True)
        print(f"doctrine-callout: {reason}", file=sys.stderr)
        print("doctrine-callout: FAILED -- the owner's doctrine callout did not "
              "go out. Re-running the job is safe and posts at most one comment; "
              "if it fails again, check the job's permissions block.",
              file=sys.stderr)
        return FAILED
    return status


if __name__ == "__main__":
    sys.exit(main())

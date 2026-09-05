#!/usr/bin/env python3
"""The doctrine callout: label and speak on any PR that changes what the
owner reads before merging -- the doctrine, the shipped charter, a repo-only
cell, or any other cell's name and description.

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

Usage:  python tools/doctrine_callout.py --pr N --base SHA [--head SHA]
            [--repo OWNER/NAME] [--dry-run]
**`--base` is not optional in practice.** It is the revision the frontmatter
arm compares against, so without it this refuses any PR touching a shipped
cell rather than degrading -- see `run()`. CI passes it; a hand run wants
`--base $(git merge-base HEAD origin/main)`.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roster  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Shared with the shipped zone, which is the lawful direction: repo-only
# code may import shipped code. Resolved from this file rather than the
# working directory, so the script runs from any cwd.
sys.path.insert(0, str(ROOT / "lib"))
from winio import utf8_stdio  # noqa: E402

# Matches `.github/CODEOWNERS`. **The widening this comment once deferred has
# happened, and it went to frontmatter only.** The owner ruled on 2026-08-31
# that a cell's name and description are flagged -- they load in every session
# whether or not the cell fires, and PR #269 had merged such an edit with
# nothing raised [#277]. (That is one incident, not three: [D-107] and
# [D-230] left the same description stale by *body* edits, and #230 was
# flagged anyway because it touched AGENTS.md and the charter. PR #320 is a
# second, found by this change's own review.) He ruled on 2026-09-05 that
# *other* shipped cells' bodies are not [#386] -- other, because the charter
# sits in the tuple below and its body is matched entire. Measured over the
# 40 then-most-recent merged
# pull requests, the flag fires on 15 today and on 17 once frontmatter is in,
# but on 35 if bodies are, and a flag on seven of every eight pull requests is
# one nobody reads. So bodies stay out by a ruling, not by an omission, and
# what licenses reopening it is a further ruling rather than an incident.
# `touched_frontmatter` is the frontmatter arm; this tuple is still paths
# alone. The charter cell is
# not a widening: it holds the half of the doctrine that moved out of
# `AGENTS.md`, and it also ships to consumers, so omitting it would shrink
# the owner's read at the moment the material became more consequential.
# **The repo-only cells are in here because the material moved, not because
# the gate widened.** The flow, this repository's records rules and its
# content-routing map used to live in AGENTS.md and reached the owner through
# this list every time a PR touched them. Moving them under `docs/cells/`
# without adding them here would have taken a PR rewriting the flow out of his
# merge-time read silently, while the Release bullet went on describing the
# wider read -- a narrower gate arriving with nothing saying so. [#260]
DOCTRINE_PATHS = ("AGENTS.md", "CLAUDE.md", "skills/charter/SKILL.md")
DOCTRINE_PREFIXES = (roster.REPO_CELLS + "/",)

JQ_RENAMED = '.[] | select(.status == "renamed") | .previous_filename'

# The seventh surface stating this mechanism's reach, and a module constant
# rather than an argparse literal so a test can address it. It was the one
# surface the round-one panel found unpinned, because the test that claimed to
# check it read `main.__doc__` -- which is None, `main` having no docstring.
CLI_DESCRIPTION = (
    "Label and comment on a pull request that changes the doctrine, the shipped "
    "charter, a repo-only cell, or any other cell's name and description, so the "
    "owner reads the diff before merging. Exit 0 when the PR state matches its "
    "diff; non-zero turns the check red."
)

LABEL = "doctrine"
LABEL_COLOR = "5319e7"
# GitHub caps a label description at 100 characters; a test measures this.
LABEL_DESC = "Changes the doctrine or charter, a repo-only cell, or a cell's description -- read before merging"

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
**This PR changes what you read before merging.** Read the {{files}} diff \
now -- nothing else performs that read. The reach is the doctrine, the \
charter and repo-only cells entire, plus any other cell's name and \
description.

Touched: {{files}}

{{always_on}}

<sub>Posted by `tools/doctrine_callout.py`. `CODEOWNERS` cannot request a \
review from a pull request's own author, and today every PR here is the \
owner's.</sub>"""

WITHDRAWN = f"""{MARKER}
~~This PR changes the doctrine.~~ **Withdrawn:** the PR no longer touches \
the doctrine or the charter, a repo-only cell, or any cell's description.
Nothing here needs the owner's doctrine read.

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
            ["gh", *args], stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
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
    of any of them is reached, but not here: GitHub's `--name-only` diff
    reports only a rename's destination (at similarity as low as 83% on this
    repo's own #74), so this function never sees the source and cannot -- it
    matches the paths it is handed. `run()` hands it `changed_paths` plus
    `renamed_from`, and the latter exists for exactly that. `tools/lint.py`
    remains the backstop it always was, failing a required check when
    `AGENTS.md`, `CLAUDE.md` or the charter cell goes missing; it is now the
    second line of defence rather than the only one, and it never covered a
    repo-only cell at all. [#293]
    """
    changed = set(paths)
    exact = [p for p in DOCTRINE_PATHS if p in changed]
    # **Prefix, not exact, for the repo-only cells**, because their names are
    # not a fixed list the way the three files are: a cell is added by making a
    # directory, and a gate keyed to names enumerated here would silently miss
    # the next one. Sorted so the callout reads the same twice.
    under = sorted(
        path for path in changed
        if any(path.startswith(prefix) for prefix in DOCTRINE_PREFIXES)
    )
    return exact + under


# The frontmatter arm's exclusions, and one rule covers both: the path arm
# already reports these entire, so naming them here would put the same cell in
# `Touched:` twice. Repo-only cells are covered by DOCTRINE_PREFIXES; the
# charter by its exact entry in DOCTRINE_PATHS -- which is also the reason the
# charter is the one shipped cell whose *body* is flagged, and the reason every
# sentence this repository renders about bodies says "other shipped cell
# bodies". A wording that drops the "other" is false of this constant. [#386]
FRONTMATTER_EXCLUDED = ("charter",)


def renamed_from(pr: str, repo: str | None) -> list[str]:
    """Every path a rename in this PR moved *out of*.

    `changed_paths`' argument for `gh pr diff --name-only` stands untouched;
    this is a second, narrower lookup beside it, for the one datum that read
    structurally cannot carry. GitHub reports a rename by its destination
    alone, so a doctrine file renamed *out* of the doctrine appeared to touch
    no doctrine at all: the owner's merge-time read was skipped and nothing
    said so. The exact-match half had `tools/lint.py` as a backstop; the prefix
    half had one only in the sense that the roster guard reddens on a
    repo-only cell renamed away -- and `python tools/roster.py --write`, the
    ordinary next step for whoever moved it, clears that finding and leaves
    nothing. Probed: the rename reddens lint with 2 findings, and 0 after the
    regeneration. [#293]

    `--paginate`, because this endpoint pages at 30 by default and a large PR
    would drop the rename off the end -- the very failure this closes,
    reintroduced one page down. Pagination is confined to this call, which is
    what buys leaving the primary read alone.

    An empty list is the ordinary answer: most pull requests rename nothing.
    """
    raw = _gh("api", "--paginate",
              f"repos/{_slug(repo)}/pulls/{pr}/files?per_page=100",
              "--jq", JQ_RENAMED)
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _require_ref(root: Path, ref: str) -> None:
    """Establish that `ref` resolves, before anything reads paths at it.

    **What this buys is the message, not the loudness.** `_cell_names_at` runs
    before any `_frontmatter_at` and already raises on a ref that will not
    resolve, so neutering the raise below changes no outcome -- probed, and the
    suite stays green. What it adds is a sentence naming the pull request's
    base sha and a shallow fetch, where `_cell_names_at` passes git's raw
    `fatal: not a tree object` up to an operator who then has to work out which
    of two revisions git meant. It also catches the one input `_cell_names_at`
    accepts and should not: a tree-ish that is not a commit.

    An earlier wording claimed that without this an unreadable base would read
    as every cell absent and fire on every pull request. That is false of the
    code below it, and the test named for this guard passed with the guard
    removed.
    """
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", "--quiet",
         f"{ref}^{{commit}}"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise CalloutError(
            f"could not resolve `{ref}` in this clone, so no cell's frontmatter "
            "could be compared against it. In CI this is the pull request's base "
            "sha and the usual cause is a shallow fetch"
        )


def _blob(root: Path, ref: str | None, path: str) -> bytes | None:
    """One file's bytes at `ref`, or from the working tree when `ref` is None.

    None means the file is not there, which is a real answer rather than a
    failure: a cell that exists at one revision and not the other is exactly
    what a rename out of `skills/` looks like from here. `_require_ref` is what
    keeps that reading honest.
    """
    if ref is None:
        here = root / path
        return here.read_bytes() if here.is_file() else None
    proc = subprocess.run(
        ["git", "-C", str(root), "show", f"{ref}:{path}"],
        stdin=subprocess.DEVNULL, capture_output=True,
    )
    return proc.stdout if proc.returncode == 0 else None


def _cell_names_at(root: Path, ref: str | None) -> set[str]:
    """Every shipped cell name at `ref`, or in the working tree when None."""
    if ref is None:
        return set(roster.names_under(root, roster.CELLS))
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", "--name-only", ref,
         roster.CELLS + "/"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise CalloutError(
            f"could not list `{roster.CELLS}/` at `{ref}`: "
            + " ".join((proc.stderr or "").split())
        )
    names = set()
    for line in proc.stdout.splitlines():
        parts = line.strip().split("/")
        if len(parts) == 3 and parts[0] == roster.CELLS and parts[2] == roster.CELL_FILE:
            names.add(parts[1])
    return names


def _frontmatter_at(root: Path, ref: str | None, path: str) -> bytes | None:
    """A cell's frontmatter block at one revision, line endings normalised.

    **Normalised, and the scope of what that buys is narrower than it looks.**
    `.gitattributes` is `* text=auto eol=lf` and the job runs on ubuntu, so a
    fresh checkout is LF on both sides and an un-normalised compare would agree
    anyway. What it protects is the *local* run on Windows after a text-mode
    write has left CRLF on disk -- which the doctrine names as expected rather
    than a defect. There the un-normalised compare differs on every file such a
    write touched, and reports cells whose descriptions never moved. An earlier
    wording here said it would differ "on every cell on every run" and flag
    every pull request; that is not reproducible in either environment, and a
    justification nobody can reproduce is how a correct guard gets deleted.

    `roster.frontmatter` rather than a second definition of what a description
    is: it returns exactly the block that loads, and #277 named its reuse as
    what makes the mechanism available without a rival notion of the same
    thing. It returns the whole block; every cell's block here is `name` plus
    `description`, so a cell that ever gained a third key would widen this
    silently -- recorded, not narrowed, because narrowing it would be that
    rival notion.
    """
    data = _blob(root, ref, path)
    if data is None:
        return None
    block = roster.frontmatter(data)
    if block is None:
        return None
    return block.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def touched_frontmatter(root: Path, base: str, head: str | None = None) -> list[str]:
    """Shipped cells whose frontmatter block differs between two revisions.

    The arm that answers *the description changed*, which no path match can
    express -- which is why adding cell paths to `DOCTRINE_PATHS` was the wrong
    fix and was declined on #277: it would have fired on every body edit, the
    thing the owner ruled against on #386.

    **Both sides are named revisions**, `head` defaulting to the working tree.
    CI passes no head and reads the checked-out merge commit, exactly as
    `_always_on_delta` does. The parameter exists so any past pull request can
    be replayed from one checkout by naming its base and head: a working-tree
    head compares every base against the same tree, which reports changes
    belonging to other pull requests as though they belonged to this one, and
    makes the claim this arm supports unfalsifiable.

    **The iteration set is the union of both revisions' cells**, so a cell's
    disappearance is visible: a shipped cell renamed out of `skills/` has a
    block at the base and none at the head, which is a difference and is
    reported. That is what makes the rename claim true for a shipped cell,
    where `renamed_from` makes it true for the watched paths.

    Sorted, so the callout reads the same twice.
    """
    _require_ref(root, base)
    if head is not None:
        _require_ref(root, head)
    names = (_cell_names_at(root, base) | _cell_names_at(root, head))
    changed = []
    for name in sorted(names - set(FRONTMATTER_EXCLUDED)):
        path = f"{roster.CELLS}/{name}/{roster.CELL_FILE}"
        if _frontmatter_at(root, base, path) != _frontmatter_at(root, head, path):
            changed.append(path)
    return changed


def _is_shipped_cell(path: str) -> bool:
    """Is this a shipped cell's own file, the frontmatter arm's exclusions aside?"""
    parts = path.split("/")
    return (len(parts) == 3 and parts[0] == roster.CELLS
            and parts[2] == roster.CELL_FILE
            and parts[1] not in FRONTMATTER_EXCLUDED)


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
# **CLAUDE.md is priced here and the rows are priced by `by_runtime`.** It is a
# member of the Claude Code row -- the row's doctrine term is AGENTS.md plus
# this file -- and it also keeps a bound of its own, because that bound is on a
# pointer file's *shape* rather than on its share of the surface, and it is the
# thing capping an AGENTS.md-to-CLAUDE.md relocation. An earlier wording said
# it was "not a share of the always-on surface", which is false, and left
# criterion 10's "no surviving per-file ceiling" reported satisfied on it.
# [#291] AGENTS.md and the charter body are
# now members of the always-on rows, which the row line beside this prices, and
# a row per member here would reassert the ceilings that priced a move between
# them as a saving. [#260]
PRICED = (
    # label,          lint constant,            figure_always_on data key
    ("CLAUDE.md",     "POINTER_BUDGET_CHARS",   "pointer"),
)


def _always_on_line(root: Path | None = None, base: str | None = None) -> str:
    """The size of what a session reads, per runtime, where the owner merges.

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
        f"Always-on surface here, per runtime: **{figures.by_runtime(data)}**"
        f"{movement}. **{data['adopter_total']:,} of "
        # **Priced, like the rows beside it.** The per-runtime half of this
        # sentence inherited the admitted composition for free by routing
        # through `by_runtime`; this half interpolated the constant and did
        # not, so on a tree carrying an adopter admission it rendered a
        # printed exceedance -- `11,547 of 11,508` -- while the required lint
        # check was green, in the same sentence whose first half was correct.
        # Four of PR #346's five seats found it independently. Same class as
        # the two incidents this file already records at PR #210 M1 and
        # PR #278 M13: a renderer stating a number its sentence did not
        # compose. [#334]
        f"{figures.priced(figures.lint.ALWAYS_ON_ADOPTER_BUDGET_CHARS, data['admitted']['always-on-adopter'])}** "
        f"from this practice "
        f"for an adopter. Against their ceilings: "
        + ", ".join(f"{label} {size:,} of {budget:,}" for label, size, budget in priced)
        + "."
        # `by_runtime`, never `cells`/`roster`: the totals this sentence opens
        # with are built from what THIS repository's runtimes load, and the
        # adopter's roster under `skills/` is a different set. Printing the
        # second as the breakdown of the first decomposed to a number the
        # sentence did not state -- invisible while they agree, and wrong
        # exactly on the trees where the roster guard is red, which this job
        # posts on because it carries no `needs:` on `lint-and-test`. Same
        # class as the two-file sum this line once rendered against one file's
        # budget. [PR #210 review, M1]
        #
        # **The ceilings are listed apart from the decomposition, and that is
        # the repair for a second instance of the same class.** A single `+`
        # chain summed to whichever runtime happened to be long while the
        # sentence stated another's total, and CLAUDE.md sat in it for a
        # runtime that does not read the file. `by_runtime` composes each
        # total from its own terms; this clause prices files against budgets,
        # which is a different question and now looks like one. [PR #278
        # review, M13]
        #
        # **Every renderer of these figures is the figure's own**, and there
        # are three of them -- this one, `figure_always_on`'s value, and
        # `tools/lint.py`'s `always_on_note`. An earlier comment here said
        # there were two, in the commit that shipped the third as a
        # hand-written copy. [PR #278 review, F5]
        #
        # The temporary-ceiling note that sat here is gone with the ceilings
        # it described: the owner approval recorded at issue #260 raised
        # AGENTS.md's and the charter body's per-file budgets, and landing
        # that issue replaced both with a ceiling on the always-on rows
        # themselves. Nothing here is raised under an approval any more, so a
        # note saying so would be the raise outliving its condition in the one
        # surface written to prevent exactly that. [PR #280 review, M5, F4]
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

    **One movement per runtime.** A single delta off `repo_total` inherited
    that scalar's bound: growth in one runtime's surface alone moved nothing,
    so a change that raised what every Claude Code session here loads could
    book `+0` against the ceiling the outflow rule defends. [PR #278 review,
    M22]

    **A runtime is never missing from either side**, because `always_on_at`
    keys its rows off the working tree's `SURFACES` on every base -- so the
    change that introduced a second runtime here books it as `Codex +5,039`
    against a base row of its own, not as an arrival. The two branches below
    are unreachable by construction and are kept as the honest answer if that
    keying is ever made base-derived; a draft of this paragraph claimed they
    described this very change, and the callout it renders disproves it.
    [PR #278 review, F6]
    """
    if not base:
        return ""
    try:
        before = figures.always_on_at(root, base)
    except Exception as exc:  # noqa: BLE001 -- reported, never swallowed
        return f" (movement not derived: {type(exc).__name__} reading {base})"
    now = figures.figure_always_on(root)["data"]["here"]
    moves = []
    for row in now:
        # Unreachable while `always_on_at` keys off the working tree's
        # SURFACES, which it does; see this function's docstring.
        was = before.get(row["runtime"])
        if was is None:
            moves.append(f"{row['runtime']} new at {row['total']:,}")
        else:
            moves.append(f"{row['runtime']} {row['total'] - was:+,}")
    for runtime in before:
        if not any(row["runtime"] == runtime for row in now):
            moves.append(f"{runtime} no longer loaded")
    return " (" + ", ".join(moves) + " this PR)"


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
        base: str | None = None, head: str | None = None) -> tuple[int, list[str]]:
    """Bring the PR's label and comment into agreement with its diff.

    **Two arms, unioned here.** `touched_doctrine` matches paths, which is what
    answers *the doctrine changed*; `touched_frontmatter` compares blocks,
    which is the only thing that can answer *a description changed* -- a path
    cannot say it, and firing on the path would fire on every body edit, which
    the owner ruled against [#386]. The path arm keeps its order (DOCTRINE_PATHS
    order, then the prefix matches sorted) and the frontmatter arm's additions
    arm are appended sorted, so the callout reads the same twice.

    **The dedup below cannot fire today, and is kept as defence in depth.**
    `touched_frontmatter` returns only `skills/<name>/SKILL.md` for a name that
    is not `charter`; the path arm returns the three watched files, the charter,
    or paths under `docs/cells/`. The two sets are disjoint by construction, so
    the guard is there against a future widening rather than against anything
    reachable now -- stated because a reader who assumes it fires will conclude
    the arms overlap, and they do not.
    """
    lines: list[str] = []
    paths = changed_paths(pr, repo) + renamed_from(pr, repo)
    touched = touched_doctrine(paths)

    # **No base, and a shipped cell changed, is a refusal rather than a pass.**
    # The frontmatter question cannot be answered without a revision to compare
    # against, and answering it "no" by default is how PR #269's description
    # edit merged unflagged [#277] -- one such incident before the filing, not
    # three; the constant above carries the count and why it is not three.
    # Loud, like every other failure here.
    if base is None:
        unanswerable = [path for path in paths if _is_shipped_cell(path)]
        if unanswerable:
            raise CalloutError(
                "this PR changes " + ", ".join(sorted(unanswerable))
                + ", so whether a cell's description moved decides the callout -- "
                "and no --base was given to compare against. Pass the base sha "
                "(CI passes the pull request's own) and re-run"
            )
    else:
        for path in touched_frontmatter(ROOT, base, head):
            if path not in touched:
                touched.append(path)

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
        description=CLI_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--pr", required=True, type=int, help="pull request number")
    parser.add_argument("--repo", default=None, help="OWNER/NAME (default: the checkout's)")
    parser.add_argument("--base", default=None,
                        help="the PR's base sha. Both the revision the frontmatter "
                             "arm compares against and the one the always-on delta "
                             "is measured from; omit it and this refuses any PR "
                             "touching a shipped cell rather than guessing")
    parser.add_argument("--head", default=None,
                        help="revision holding this PR's cells; omitted, the "
                             "working tree is read, which is what CI wants. Name "
                             "it to replay a past PR without checking it out")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change; touch nothing")
    args = parser.parse_args(argv)
    # **A bulk replay must not write.** `--head` exists so a past pull request
    # can be evaluated without checking it out, and the procedure that uses it
    # is a loop over forty merged pull requests. Without `--dry-run` that loop
    # labels and comments on every one of them, each carrying an always-on
    # figure derived from the current working tree, since `_always_on_line`
    # takes no head. Refused rather than trusted to the caller's flag order.
    if args.head is not None and not args.dry_run:
        print("::error title=doctrine-callout::--head is for replaying a past "
              "pull request and must be given with --dry-run; without it a "
              "replay writes a label and a comment to every PR it visits",
              flush=True)
        print("doctrine-callout: --head requires --dry-run", file=sys.stderr)
        return FAILED
    # **And --head without --base does nothing at all, silently.** `run()` takes
    # the `base is None` branch, never calls `touched_frontmatter`, and discards
    # the head -- so a replay reports path-arm findings only while the operator
    # believes both arms ran. The shipped-cell refusal below catches most of it
    # by accident, because a frontmatter edit usually puts the cell path in the
    # diff; it misses a replay whose diff holds no shipped-cell path, and names
    # the wrong flag when it does fire. Raised by the external pass on this PR.
    if args.head is not None and args.base is None:
        print("::error title=doctrine-callout::--head names the head side of a "
              "comparison whose base side is --base, so without --base the "
              "frontmatter arm does not run and the head is read by nothing",
              flush=True)
        print("doctrine-callout: --head requires --base", file=sys.stderr)
        return FAILED
    try:
        status, _ = run(args.pr, args.repo, dry_run=args.dry_run,
                        base=args.base, head=args.head)
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

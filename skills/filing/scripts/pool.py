#!/usr/bin/env python3
"""The pool's transport: what has been filed but not yet decided on (issue #434).

A filing used to become work the moment it landed -- onto the board, ranked
beside things somebody had actually decided to do, with no way to tell the two
apart. The pool is the state between noticing and doing. An open issue is in it
unless it carries the framed label, so nothing has to be written to put a
filing there and a filer who forgets cannot lose one; framing is the single
write that moves an issue onto the board.

The session supplies the judgment -- what a filing's ratings should be, which
of the raised few is worth doing, what the case against each one is. This
supplies everything that is not judgment.

**Every label name, every rating value, the ordering, the shortlist size and
the accrual, fade and assessment numbers live in the policy file.**
`pool-policy.json` beside this script carries the defaults; a repository
overrides them with a file of that name at its own root, and the override is
read instead of the default rather than merged into it, so what a repository
states is the whole policy and no field it did not write can surprise it later.

**No label the policy does not name is ever written.** `writable_labels` is the
only place that set is computed, and every command that edits an issue's labels
routes through `edit_labels`, which enforces it. `cmd_labels` creates labels
rather than editing an issue, so it does not route through that function; what
makes it safe is that it can only ever offer names `label_specs` derived from
the same policy.

**`--repo` and `--policy` go before the subcommand**, being options of the
top-level parser. **They belong together:** `--repo` steers only the wire, while
the policy is resolved from the working directory, so reading another repository
without naming its policy partitions its issues by this one's labels. Every
command prints the policy it resolved for that reason.

Usage:  python scripts/pool.py [--repo OWNER/REPO] [--policy PATH] <command>

        python scripts/pool.py list      [--limit N]
        python scripts/pool.py show      N
        python scripts/pool.py shortlist [--count N] [--unassessed]
        python scripts/pool.py cycle     [--dry-run]
        python scripts/pool.py assess    N --none
        python scripts/pool.py framed
        python scripts/pool.py policy
        python scripts/pool.py labels    [--dry-run]
        python scripts/pool.py rate      N --rating LABEL [--rating LABEL]
        python scripts/pool.py frame     N
        python scripts/pool.py unframe   N

  list       the pool, highest-rated first, with each item's ratings
  show       one issue: whether it is framed, and what it is rated
  shortlist  the few worth raising, at the policy's size; refuses over an
             unassessed top, so that what it raises are causes
  cycle      what has risen from its symptoms, what has faded to the floor, and
             the next bounded few to assess
  assess     record that an issue was asked and is its own cause
  framed     the framed set, which is what the board holds
  policy     the resolved policy and the file it came from
  labels     create the policy's labels in the repository, idempotently
  rate       set an issue's rating on one axis or on every axis
  frame      record that this is decided work
  unframe    return a framed issue to the pool
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Shared code lives in lib/, which ships beside this cell, so the import
# resolves in a source checkout and an installed plugin alike -- against this
# file's own directory, never the working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from winio import utf8_stdio  # noqa: E402

POLICY_NAME = "pool-policy.json"
DEFAULT_POLICY = Path(__file__).resolve().parent / POLICY_NAME

# `gh issue list` returns at most what it is asked for and says nothing about
# what it left behind, so a read that comes back exactly full is the short-read
# hazard rather than a full board. Refused rather than warned: every command
# here partitions the whole open set, and a partition over a truncated read is
# wrong in a way its own output cannot show.
ISSUE_READ_LIMIT = 1000

# The same hazard on the label read `cmd_labels` performs: a truncated list
# makes an existing label read as missing, and creating it then fails partway
# through with an error blaming the wrong thing.
LABEL_READ_LIMIT = 500

# The causation read pages 100 issues at a time. This bounds it, so a
# `hasNextPage` that never goes false is a refusal rather than a hang.
PAGE_LIMIT = 100

UNRATED = "-"

# The width of the issue-number column, shared by the header and every row.
ISSUE_COL = 8


class PoolError(Exception):
    """A refusal a caller can act on. Printed without a traceback."""


# --------------------------------------------------------------- the policy


def find_policy(start: Path | None = None) -> Path:
    """The override at the repository root if there is one, else the default.

    The root is found by walking up for `.git`, not by trusting the working
    directory: a session running this from a subdirectory would otherwise get
    the shipped default while a file it wrote two directories up sat unread,
    and nothing in the output would say so. `.git` is a file rather than a
    directory inside a worktree, so this tests existence and not kind.
    """
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists():
            override = candidate / POLICY_NAME
            return override if override.is_file() else DEFAULT_POLICY
    override = here / POLICY_NAME
    return override if override.is_file() else DEFAULT_POLICY


def load_policy(path: Path) -> dict:
    """Read and validate a policy. Every field the script reads is checked here.

    Validated on load rather than at each use, because the failure this
    prevents is silent: an axis whose values are not distinct, or an `order`
    naming an axis that does not exist, produces an ordering that is merely
    wrong rather than one that fails. A repository editing this file gets told
    what it broke at the next command instead of at the next disagreement.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PoolError(f"cannot read the policy at {path}: {exc}") from None
    try:
        policy = json.loads(raw)
    except ValueError as exc:
        raise PoolError(f"{path} is not valid JSON: {exc}") from None
    if not isinstance(policy, dict):
        raise PoolError(f"{path} must hold a JSON object")

    axes = policy.get("axes")
    if not isinstance(axes, dict) or not axes:
        raise PoolError(f"{path}: 'axes' must be a non-empty object")
    seen: dict[str, str] = {}
    for name, axis in axes.items():
        if not isinstance(axis, dict):
            raise PoolError(f"{path}: axis '{name}' must be an object")
        values = axis.get("values")
        if not isinstance(values, dict) or not values:
            raise PoolError(f"{path}: axis '{name}' has no 'values'")
        ranked: dict[int, str] = {}
        for label, value in values.items():
            if not isinstance(value, int) or isinstance(value, bool):
                raise PoolError(
                    f"{path}: axis '{name}' maps '{label}' to something that "
                    f"is not a whole number, so nothing can be ordered by it"
                )
            # The docstring above promises this check by name, and for a while
            # it was only promised: two labels sharing a number order as a tie,
            # so a repository believes it configured distinct bands while the
            # axis silently collapses them and a later axis or the issue number
            # decides the shortlist.
            if value in ranked:
                raise PoolError(
                    f"{path}: axis '{name}' gives '{ranked[value]}' and "
                    f"'{label}' the same value {value}, so the two bands are "
                    f"indistinguishable to the ordering"
                )
            ranked[value] = label
            _check_label_name(path, label)
            if label in seen:
                raise PoolError(
                    f"{path}: '{label}' is named by axis '{seen[label]}' and "
                    f"by axis '{name}', so an issue carrying it has two "
                    f"meanings and neither can be read off it"
                )
            seen[label] = name

    order = policy.get("order")
    if not isinstance(order, list) or not order:
        raise PoolError(f"{path}: 'order' must list the axes, most significant first")
    if sorted(order) != sorted(axes):
        raise PoolError(
            f"{path}: 'order' names {sorted(order)} and 'axes' names "
            f"{sorted(axes)} -- every axis is ordered by, exactly once"
        )

    framed = policy.get("framed")
    if not isinstance(framed, dict) or not isinstance(framed.get("label"), str) \
            or not framed["label"].strip():
        raise PoolError(f"{path}: 'framed' must carry a 'label' naming one label")
    _check_label_name(path, framed["label"])
    if framed["label"] in seen:
        raise PoolError(
            f"{path}: '{framed['label']}' is both the framed label and a "
            f"rating on axis '{seen[framed['label']]}'"
        )

    for key in ("cause", "assessed"):
        block = policy.get(key)
        if not isinstance(block, dict) or not isinstance(block.get("label"), str):
            raise PoolError(
                f"{path}: '{key}' must carry a 'label' naming one label. A policy "
                f"written before the accrual and the fade landed does not have it: "
                f"add 'cause', 'assessed', 'accrual', 'fade' and 'assessment'"
            )
        _check_label_name(path, block["label"])
        if block["label"] in seen or block["label"] == framed["label"]:
            raise PoolError(
                f"{path}: '{block['label']}' is the '{key}' label and is already "
                f"in use, so an issue carrying it has two meanings"
            )
        seen[block["label"]] = key

    size = policy.get("shortlist_size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise PoolError(f"{path}: 'shortlist_size' must be a whole number of at least 1")

    _whole(policy, path, "accrual", "symptoms_per_band", least=1)
    _whole(policy, path, "fade", "quiet_days", least=1)
    # `least=1`, not 0. Zero is the value a repository reaches for to switch the
    # gate off, and it loaded without complaint while `max(len(raised), 0)`
    # discarded it and every shortlist went on refusing -- a floor the validator
    # invited and the mechanism did not honour. The gate is not switchable off
    # per-policy; `--unassessed` is the per-invocation escape and the refusal
    # names it.
    _whole(policy, path, "assessment", "before_shortlist", least=1)
    _whole(policy, path, "assessment", "per_cycle", least=1)

    closes = policy.get("fade", {}).get("closes")
    if not isinstance(closes, bool):
        raise PoolError(
            f"{path}: 'fade.closes' must be true or false. It is what decides "
            f"whether the fade closes anything at all, so it is stated rather "
            f"than defaulted"
        )

    return policy


def _whole(policy: dict, path: Path, block: str, key: str, *, least: int) -> None:
    """One policy number, validated where every other one is.

    Named rather than inlined four times because the message a repository reads
    when it edits this file wrongly is the whole value of validating on load.
    """
    values = policy.get(block)
    if not isinstance(values, dict):
        raise PoolError(
            f"{path}: '{block}' must be an object. A policy written before the "
            f"accrual and the fade landed does not have it: add 'cause', "
            f"'assessed', 'accrual', 'fade' and 'assessment'"
        )
    value = values.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < least:
        raise PoolError(
            f"{path}: '{block}.{key}' must be a whole number of at least {least}"
        )


def _check_label_name(path: Path, label: str) -> None:
    """A label name a write can carry intact, and nothing else.

    `gh issue edit --add-label` and `--remove-label` split their argument on
    commas -- the CLI's own help demonstrates it with `"bug,help wanted"` -- so
    a policy naming a label with a comma in it would have that one value write
    two labels the policy never named and leave the intended one unset. That is
    the write rail defeated by a name rather than by a call site, which is why
    it is refused here, where the vocabulary is admitted, rather than at the
    edit. Blank and whitespace-only names are refused for the same reason: what
    reaches the wire would not be the name.
    """
    if not label.strip():
        raise PoolError(f"{path}: a label name is blank")
    if "," in label:
        raise PoolError(
            f"{path}: the label '{label}' contains a comma, which `gh issue "
            f"edit` reads as a separator -- writing it would touch labels the "
            f"policy does not name and leave this one unset"
        )


def writable_labels(policy: dict) -> frozenset[str]:
    """Every label this script may write, and the only place that set is computed.

    The brief's rail is that no label outside the policy is ever written. One
    function rather than a check at each call site: a command added later
    routes through `edit_labels` and inherits the rail, where a per-site rule
    would be inherited only by whoever remembered it.
    """
    names = {label for axis in policy["axes"].values() for label in axis["values"]}
    names.add(policy["framed"]["label"])
    # `assess` writes this one, so the rail has to admit it or the one write
    # stage two adds is refused by the guard stage one built.
    names.add(policy["assessed"]["label"])
    return frozenset(names)


# ------------------------------------------------------------------ the wire


def gh(args: list[str]) -> str:
    """One launch shape for every call: all three streams named, none inherited."""
    try:
        proc = subprocess.run(
            ["gh", *args], capture_output=True, text=True, encoding="utf-8",
            errors="replace", stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise PoolError(
            "the GitHub CLI ('gh') is not on PATH. The pool is issues and "
            "labels, so there is nothing to read without it"
        ) from None
    if proc.returncode != 0:
        raise PoolError(f"gh {' '.join(args)} failed: {proc.stderr.strip()[:400]}")
    return proc.stdout


def _in_checkout(start: Path | None = None) -> bool:
    """Whether there is a git checkout above here for `gh` to infer a repo from."""
    here = (start or Path.cwd()).resolve()
    return any((c / ".git").exists() for c in (here, *here.parents))


def _repo_args(repo: str | None) -> list[str]:
    """Nothing when no repository is named, so `gh` infers it from the checkout.

    **Outside a checkout this refuses here rather than letting `gh` try.** The
    first command anyone runs is `list`, which reaches the wire directly, and
    what came back was git's own message -- `failed to run git: fatal: not a git
    repository` -- naming neither this script's problem nor its remedy. A
    consumer met exactly that and had to read the source to find the sentence
    the script already had, which lived in `_infer_repo` and fires only on the
    causation read. The check is a walk up for `.git`, as `find_policy` does, so
    it costs no round trip.
    """
    if repo:
        return ["--repo", repo]
    if not _in_checkout():
        raise PoolError(
            "there is no git checkout here, so which repository this is cannot "
            "be worked out. Name it with --repo OWNER/REPO"
        )
    return []


def open_issues(repo: str | None = None) -> list[dict]:
    """Every open issue with its labels and its last-touched time, in one call.

    Labels come back in the same read as the numbers because every command
    here needs both, and a second call per issue over a hundred-item board is
    a hundred round trips for something one query already carries.

    `updatedAt` is here because the fade is read from it. It is the one field
    that makes a decay derivable with nothing stored: GitHub maintains it, and
    a decay that had to be written would bump the very field it reads.
    """
    raw = gh([
        "issue", "list", *_repo_args(repo), "--state", "open",
        "--limit", str(ISSUE_READ_LIMIT), "--json", "number,title,labels,updatedAt",
    ])
    issues = json.loads(raw)
    if len(issues) >= ISSUE_READ_LIMIT:
        raise PoolError(
            f"the open-issue read came back at its limit of {ISSUE_READ_LIMIT}, "
            f"so it may be short and every partition below it would be wrong "
            f"without saying so. Raise ISSUE_READ_LIMIT and run again"
        )
    return issues


def issue_labels(number: int, repo: str | None = None) -> list[str]:
    """The labels one issue carries, as `gh` reports them."""
    raw = gh(["issue", "view", str(number), *_repo_args(repo), "--json", "labels"])
    return [lb["name"] for lb in json.loads(raw).get("labels", [])]


def causal_parents(policy: dict, repo: str | None = None) -> dict[int, int]:
    """Open symptom -> its open, labelled cause, paged.

    GraphQL rather than `gh issue list`: neither `parent` nor `issueType` is in
    that command's field set, so the one-call read above cannot carry this.

    **A repository's own board transport may perform the same read, and the
    repetition is the wall rather than an oversight.** Such a transport is
    repo-only and this script ships, so it may not be imported from here. The
    label's name is in the policy this reads, and a repo-only transport may read
    it from there too -- **this repository's has not been changed to**, so the
    name still has more than one home and a repository renaming it in its policy
    would get an accrual on the new name beside a guard reading the old one. A parent that is closed,
    or carries no cause label, yields nothing -- the first because a closed
    cause accrues nothing, the second because an unlabelled link is an ordinary
    task decomposition and means something else entirely.
    """
    owner_repo = repo or _infer_repo()
    owner, _, name = owner_repo.partition("/")
    label = policy["cause"]["label"]
    parents: dict[int, int] = {}
    # **The cursor is a variable, and the loop is bounded.** Interpolating the
    # server's `endCursor` into the query string puts a value this script does
    # not control into the query it sends; `_graphql` already passes variables
    # over `-f` and explains why, so the cursor goes the same way. And the loop
    # had no bound at all, where the issue read above refuses at a limit rather
    # than running on: a `hasNextPage` that stays true with a null `endCursor`
    # asks for `after:"None"` forever, and a hang says less than a refusal.
    cursor: str | None = None
    pages = 0
    while True:
        pages += 1
        if pages > PAGE_LIMIT:
            raise PoolError(
                f"the causation read passed {PAGE_LIMIT} pages of 100 issues "
                f"without finishing, which it should never do -- treat this as "
                f"the read failing rather than as a very large repository"
            )
        data = _graphql(
            "query($o:String!,$r:String!,$after:String){repository(owner:$o,name:$r){"
            "issues(states:OPEN,first:100,after:$after){pageInfo{hasNextPage endCursor}"
            "nodes{number parent{number state labels(first:50){nodes{name}}}}}}}",
            o=owner, r=name, after=cursor,
        )["repository"]["issues"]
        for node in data["nodes"]:
            parent = node.get("parent")
            if not parent or parent["state"] != "OPEN":
                continue
            if label in {lb["name"] for lb in parent["labels"]["nodes"]}:
                parents[node["number"]] = parent["number"]
        cursor = data["pageInfo"]["endCursor"]
        if not data["pageInfo"]["hasNextPage"] or cursor is None:
            return parents


def _infer_repo() -> str:
    """OWNER/REPO for the checkout, when no --repo was given.

    A checkout with no remote cannot answer. Raw `gh` says only `no git remotes
    found`; what names a command the caller never typed is this script's own
    `gh()` wrapper, which prefixes every failure with the arguments it sent. So
    the refusal below adds what could not be worked out and what to pass
    instead, and the wrapper's shape survives inside it -- the general repair
    belongs at `gh()` and is not this one call site's to make.
    """
    try:
        raw = gh(["repo", "view", "--json", "nameWithOwner"])
    except PoolError as exc:
        raise PoolError(
            f"cannot work out which repository this is, so the causation read "
            f"has nowhere to go: {exc}. Name it with --repo OWNER/REPO"
        ) from None
    return json.loads(raw)["nameWithOwner"]


def _graphql(query: str, **variables: object) -> dict:
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        # A `None` is left out rather than sent. `-f` stringifies, so passing it
        # would send the four characters `None` where the query wants null --
        # which is exactly the first page of a paged read, whose cursor is null.
        if value is None:
            continue
        # -f, never -F: -F applies magic type conversion, reading a value
        # beginning "@" as a filename and expanding {owner}/{repo} from the
        # working directory. Every variable here is a String.
        args += ["-f", f"{key}={value}"]
    data = json.loads(gh(args))
    if "errors" in data:
        raise PoolError(f"graphql: {json.dumps(data['errors'])[:400]}")
    return data["data"]


def edit_labels(number: int, policy: dict, *, add: list[str], remove: list[str],
                repo: str | None = None) -> None:
    """The one write path, and the one place the policy's rail is enforced."""
    allowed = writable_labels(policy)
    for label in [*add, *remove]:
        if label not in allowed:
            raise PoolError(
                f"'{label}' is not a label the policy names, and this writes "
                f"none that it does not. The policy names: "
                f"{', '.join(sorted(allowed))}"
            )
    args = ["issue", "edit", str(number), *_repo_args(repo)]
    for label in add:
        args += ["--add-label", label]
    for label in remove:
        args += ["--remove-label", label]
    if not add and not remove:
        return
    gh(args)


# ------------------------------------------------------------------ reading


def rating_of(labels: list[str], axis: dict) -> tuple[str | None, bool]:
    """One axis read off an issue's labels: the label carried, and whether it clashes.

    A clash is reported rather than resolved. Picking the higher of two would
    make an issue that is rated twice look like one that is rated once, and the
    thing worth knowing about it is that somebody has to choose.
    """
    carried = [label for label in labels if label in axis["values"]]
    if not carried:
        return None, False
    return carried[0], len(carried) > 1


def read_pool(policy: dict, repo: str | None = None) -> tuple[list[dict], list[dict]]:
    """Partition the open set into the pool and the framed, each item rated.

    Returns `(pool, framed)`. The pool is ordered; the framed set is left in
    the order the issue list gave it, the board being what orders that half.
    """
    framed_label = policy["framed"]["label"]
    assessed_label = policy["assessed"]["label"]
    pool: list[dict] = []
    framed: list[dict] = []
    by_number: dict[int, dict] = {}
    for issue in open_issues(repo):
        labels = [lb["name"] for lb in issue.get("labels", [])]
        item = {
            "number": issue["number"],
            "title": issue.get("title", ""),
            "ratings": {},
            "clashes": [],
            "assessed": assessed_label in labels,
            "updated_at": _stamp(issue.get("updatedAt")),
            "symptoms": [],
        }
        for name, axis in policy["axes"].items():
            label, clashed = rating_of(labels, axis)
            item["ratings"][name] = label
            if clashed:
                item["clashes"].append(name)
        by_number[item["number"]] = item
        if framed_label in labels:
            framed.append(item)
        else:
            pool.append(item)

    # The accrual's input, read once for the whole set rather than per item.
    #
    # **Unconditionally**, which this comment used to deny. It claimed the read
    # happened "only where something might accrue"; what is conditional is the
    # loop body, and the walk itself runs for every command that reads the pool
    # -- including `show`, which asks about one issue and pays a `gh repo view`
    # plus a paged GraphQL read over the whole repository to answer. Gating it
    # costs another wire call to find out whether any cause label exists, so the
    # cost is stated here rather than hidden or paid for twice.
    for symptom, cause in causal_parents(policy, repo).items():
        parent, child = by_number.get(cause), by_number.get(symptom)
        if parent is not None and child is not None:
            parent["symptoms"].append({"number": symptom, "values": _bare(child, policy)})
            # **The link is an answer to the assessment question, and this is
            # where it is read.** There are three answers -- not asked, asked and
            # it is its own, asked and here is its cause -- and only the first
            # two have a label, the third being the sub-issue link the `filing`
            # cell governs. Reading the flag from the label alone made the third
            # read as the first: the gate named the symptom, its refusal offered
            # `link it under its cause` as the first remedy, and taking that
            # remedy changed nothing the gate could see, so a session doing
            # exactly as instructed looped with no exit but `--unassessed`. The
            # only thing that cleared the item was `assess <N> --none`, which
            # asserts the opposite of the true answer.
            #
            # This stores nothing and writes nothing: the link stays the sole
            # record and `assessed` becomes a derived read of it, exactly as
            # effective severity and the fade are derived from that same link
            # and that same `updatedAt`. A second *representation* would be a
            # second thing written down, which is what this cannot disagree with.
            child["assessed"] = True

    for item in (*pool, *framed):
        item["effective"] = effective(item, policy)
    pool.sort(key=lambda it: sort_key(it, policy))
    return pool, framed


def _bare(item: dict, policy: dict) -> dict[str, int | None]:
    """One item's own band values, with nothing derived.

    A symptom contributes what a person rated it, not what it accrued: letting
    accrual feed accrual would make a chain of causes climb without limit and
    for no reason anybody wrote down.
    """
    out: dict[str, int | None] = {}
    for name, axis in policy["axes"].items():
        label = item["ratings"].get(name)
        out[name] = None if (label is None or name in item["clashes"]) else axis["values"][label]
    return out


def _stamp(raw: str | None) -> "datetime | None":
    """GitHub's ISO-8601 timestamp, or None where a payload carries none."""
    if not raw:
        return None
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    # A stamp with no offset parses cleanly and then dies at the subtraction in
    # `quiet_windows` with a raw `TypeError`, which escapes the refusal contract
    # this module prints without a traceback. An older payload, or a date with
    # no time, is the case the line above anticipates and this one survives.
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def quiet_windows(item: dict, policy: dict, now: datetime | None = None) -> int:
    """How many whole quiet windows have passed since the issue was last touched.

    Read from `updatedAt` rather than counted per run, so the fade needs no
    stored state and no run has to have happened. An issue with no `updatedAt`
    -- a stub in a test, an older payload -- has faded by zero rather than by
    an amount nobody can check.
    """
    stamp = item.get("updated_at")
    if not stamp:
        return 0
    moment = (now or datetime.now(timezone.utc))
    days = (moment - stamp).days
    return max(0, days // policy["fade"]["quiet_days"])


def effective(item: dict, policy: dict,
              now: datetime | None = None) -> dict[str, int | None]:
    """The pair the pool orders by: accrual applied, then the fade.

    **Neither is ever written back.** A cause's own labels stay what a person
    proposed, and the fade in particular could not be written without resetting
    the signal it reads.

    Accrual first, then the fade, because a cause with live symptoms is rarely
    quiet and a cause whose symptoms have all gone quiet should fade with them.
    """
    axes, order = policy["axes"], policy["order"]
    values: dict[str, int | None] = {}
    # Per axis, not over the whole clash list. Testing the list meant one
    # clashed axis discarded every clean rating the item had, so an issue at the
    # top of the severity scale with a stray second urgency label sorted below
    # the mildest thing in the pool on issue number alone. The incident's lesson
    # sits here because this is where an axis becomes unusable; everything
    # downstream reads the answer rather than the labels.
    for name in order:
        label = item["ratings"].get(name)
        if label is None or name in item["clashes"]:
            values[name] = None
        else:
            values[name] = axes[name]["values"][label]

    symptoms = item.get("symptoms", [])
    if symptoms:
        top = order[0]
        # A cause is at least as bad as the worst thing it produces.
        #
        # **Only where the cause carries a band of its own.** A `None` here means
        # one of two things -- nobody rated the axis, or somebody rated it twice
        # -- and filling it from the symptoms resolved both. That put an issue
        # with two severity labels at the top of the pool at a value nobody
        # wrote, its row saying only `CLASH`, which is the one signal meaning a
        # human still has to choose; and it made an unrated cause sort in the
        # rated tier while `is_rated` and the header count both called it
        # unrated. D-438 decision 3 is that two values on one axis are reported
        # rather than resolved, since taking the higher hides that somebody has
        # to choose, and accrual is not an exception to it. An unrated axis stays
        # unrated: accrual raises a rating, it does not supply one.
        worst = [s for s in (sym["values"].get(top) for sym in symptoms) if s is not None]
        if worst and values.get(top) is not None:
            values[top] = max(values[top], max(worst))
        # And it climbs on the second axis as they accumulate.
        if len(order) > 1:
            second = order[1]
            if values.get(second) is not None:
                bands = len(symptoms) // policy["accrual"]["symptoms_per_band"]
                cap = max(axes[second]["values"].values())
                values[second] = min(cap, values[second] + bands)

    if len(order) > 1:
        second = order[1]
        if values.get(second) is not None:
            floor = min(axes[second]["values"].values())
            values[second] = max(floor, values[second] - quiet_windows(item, policy, now))
    return values


def at_floor(item: dict, policy: dict, values: dict[str, int | None],
             now: datetime | None = None) -> bool:
    """Whether the fade has taken this item to the bottom of the decaying axis.

    Takes the same clock its sibling does. Without it this re-derived quiet
    against the wall while judging values computed at an injected `now`, so the
    two disagreed about one item: `effective(item, policy, now=X)` floored it and
    `at_floor` handed those very values denied it.
    """
    order = policy["order"]
    if len(order) < 2:
        return False
    second = order[1]
    if values.get(second) is None:
        return False
    floor = min(policy["axes"][second]["values"].values())
    return values[second] <= floor and quiet_windows(item, policy, now) > 0


def sort_key(item: dict, policy: dict) -> tuple:
    """Rated above unrated, then each axis in the policy's order, then oldest first.

    Unrated is not zero. An issue nobody has rated has not been judged
    harmless; it has not been judged. Sorting it below every rated item says
    that, where a zero would assert the bottom of the scale.
    """
    order = policy["order"]
    derived = item.get("effective") or effective(item, policy)
    values = []
    complete = True
    for name in order:
        # Per axis. Which axes are unusable is `effective`'s to say, and this
        # reads its answer one axis at a time rather than re-deriving it.
        value = derived.get(name)
        if value is None:
            complete = False
            values.append(0)
        else:
            values.append(value)
    return (0 if complete else 1, *[-v for v in values], item["number"])


def is_rated(item: dict, policy: dict) -> bool:
    return all(item["ratings"].get(name) for name in policy["axes"]) and not item["clashes"]


# ----------------------------------------------------------------- printing


def _widths(policy: dict) -> list[int]:
    """One column per axis, wide enough for the axis name and every label it has.

    Computed from the policy rather than fixed, because a repository naming its
    axes or its values differently would otherwise get a header that no longer
    sits over the column it names.
    """
    return [max(len(name), len("CLASH"),
                *(len(f"{v}>{max(policy['axes'][name]['values'].values())}")
                  for v in policy["axes"][name]["values"]))
            for name in policy["order"]]


def _line(item: dict, policy: dict) -> str:
    cells = []
    derived = item.get("effective") or effective(item, policy)
    for name, width in zip(policy["order"], _widths(policy)):
        label = item["ratings"].get(name) or UNRATED
        if name in item["clashes"]:
            label = "CLASH"
        elif label != UNRATED:
            # An arrow where the derived value differs from the labelled one, so
            # the order a reader sees is explained by the row rather than by
            # having read the policy.
            own = policy["axes"][name]["values"][label]
            if derived.get(name) is not None and derived[name] != own:
                label = f"{label}>{derived[name]}"
        cells.append(label.ljust(width))
    # In its own column, under its own header. Appended to the joined cells it
    # sat under no header, hard against the last rating where it read as part of
    # that value, and moved the title two columns between an assessed row and an
    # unassessed one.
    mark = " " if item.get("assessed") else "?"
    prefix = f"#{item['number']:<{ISSUE_COL - 2}} "
    return f"{prefix}{'  '.join(cells)}  {mark}  {item['title'][:70]}"


def _header(policy: dict) -> str:
    # `ISSUE_COL`, not a literal run of spaces: the header read `"issue    "`
    # against a row prefix of `#` plus six, so every column heading sat one to
    # the right of the column it named. One constant, so they cannot drift.
    cells = [name.ljust(width) for name, width in zip(policy["order"], _widths(policy))]
    return "issue".ljust(ISSUE_COL) + "  ".join(cells) + "  ?  title"


def cmd_list(policy: dict, repo: str | None, limit: int | None) -> int:
    if limit is not None and limit < 1:
        raise PoolError("--limit must be a whole number of at least 1")
    pool, framed = read_pool(policy, repo)
    unrated = [it for it in pool if not is_rated(it, policy)]
    print(f"pool: {len(pool)}   framed: {len(framed)}   unrated in pool: {len(unrated)}")
    print(_header(policy))
    for item in (pool[:limit] if limit is not None else pool):
        print(_line(item, policy))
    return 0


def cmd_framed(policy: dict, repo: str | None) -> int:
    pool, framed = read_pool(policy, repo)
    print(f"framed: {len(framed)}   pool: {len(pool)}")
    for item in sorted(framed, key=lambda it: it["number"]):
        print(_line(item, policy))
    return 0


def cmd_show(policy: dict, repo: str | None, number: int) -> int:
    pool, framed = read_pool(policy, repo)
    for item in framed:
        if item["number"] == number:
            print(f"#{number} is framed -- decided work, which the board holds "
                  f"from the next sync")
            _print_ratings(item, policy)
            return 0
    for item in pool:
        if item["number"] == number:
            print(f"#{number} is in the pool -- filed, not yet decided on")
            _print_ratings(item, policy)
            return 0
    raise PoolError(
        f"#{number} is not an open issue, so it is in neither the pool nor "
        f"the framed set. A closed issue leaves the pool by closing"
    )


def _print_ratings(item: dict, policy: dict) -> None:
    """One issue as `list` reads it, in sentences rather than columns.

    **Everything `list` distinguishes, this distinguishes.** It printed the
    labelled value alone, so two issues differing only in the assessment read
    byte-identical here and a faded issue asserted its label as its current
    value -- while the row for the same issue in `list` carried both the arrow
    and the mark. `show` is the command a session runs about one issue, which
    made it the one place in the tool that answered the question it exists to
    answer with the one fact that had changed left out.
    """
    derived = item.get("effective") or effective(item, policy)
    for name in policy["order"]:
        label = item["ratings"].get(name)
        axis = policy["axes"][name]
        meaning = axis.get("meaning", name)
        if name in item["clashes"]:
            print(f"  {name}: CLASH -- more than one of {sorted(axis['values'])}")
        elif label is None:
            print(f"  {name}: unrated ({meaning})")
        else:
            own, now = axis["values"][label], derived.get(name)
            moved = "" if now is None or now == own else f" -- reads as {now} now"
            print(f"  {name}: {label} = {own} ({meaning}){moved}")
    if item.get("assessed"):
        print("  assessed: asked whether it has a cause")
    else:
        print("  not assessed: nobody has asked whether it has a cause")
    if item.get("symptoms"):
        under = " ".join(f"#{s['number']}" for s in item["symptoms"])
        print(f"  {len(item['symptoms'])} open symptom(s) under it: {under}")
    print(f"  {item['title']}")


def cmd_shortlist(policy: dict, repo: str | None, count: int | None,
                  unassessed: bool = False) -> int:
    # `shortlist_size` is validated on load; the flag that overrides it was not,
    # and a negative sliced from the end -- raising most of the pool under a
    # header saying it was raising a few, with the unrated caveat suppressed
    # because `len(rated) < size` is false for a negative.
    if count is not None and count < 1:
        raise PoolError("--count must be a whole number of at least 1")
    size = count if count is not None else policy["shortlist_size"]
    pool, _ = read_pool(policy, repo)
    raised = pool[:size]

    # The amendment has the pool work out the causes behind the highest-rated
    # unassessed things BEFORE a session brings the owner a few, so that what it
    # brings are causes. An advisory line does not do that -- a session reads it
    # and raises the symptoms anyway -- so this refuses, names exactly which
    # items block and the command that answers for each, and leaves `--unassessed`
    # as the stated escape. Bounded to what is being raised, at least as deep as
    # the policy says, so `--count` cannot outrun the gate.
    depth = max(len(raised), policy["assessment"]["before_shortlist"])
    blocking = [it for it in pool[:depth] if not it["assessed"]]
    if blocking and not unassessed:
        listed = " ".join(f"#{it['number']}" for it in blocking)
        raise PoolError(
            f"{len(blocking)} of the top {min(depth, len(pool))} in the pool have "
            f"never been asked whether they have a cause: {listed}. A shortlist "
            f"raised over them raises symptoms. Ask why for each, then either link "
            f"it under its cause as a sub-issue or record that it is its own with "
            f"`assess <N> --none`. To raise them anyway, pass --unassessed"
        )
    rated = [it for it in pool if is_rated(it, policy)]
    # Against what is actually being raised, not against the size asked for: a
    # pool of two fully-rated items under a size of five is not partly unrated,
    # and saying so told a reader to discount a ranking that was sound.
    unrated_raised = [it for it in raised if not is_rated(it, policy)]
    print(f"pool: {len(pool)}   rated: {len(rated)}   raising: {len(raised)}")
    if unrated_raised:
        print(
            "fewer rated items than the shortlist holds, so what follows is "
            "partly the oldest unrated filings rather than the highest-rated. "
            "Rate what belongs in contention before reading this as a ranking."
        )
    print(_header(policy))
    for item in raised:
        print(_line(item, policy))
    print("")
    print("Each of these is put to the owner with its one-line case and the "
          "case against; neither is this script's to write.")
    return 0


def cmd_policy(policy: dict, source: Path) -> int:
    print(f"policy: {source}")
    print(f"default: {DEFAULT_POLICY}")
    # Both sets, because printing only the writable one had this command and
    # `labels` saying different things about `cause`: created here, never
    # written onto an issue by anything, and absent from the one line a reader
    # checks to find out which labels this tool touches.
    created = sorted({spec[0] for spec in label_specs(policy)})
    print(f"labels it creates: {', '.join(created)}")
    print(f"labels it writes onto an issue: {', '.join(sorted(writable_labels(policy)))}")
    print(json.dumps(policy, indent=2, sort_keys=True))
    return 0


# ------------------------------------------------------------------ writing


def label_specs(policy: dict) -> list[tuple[str, str, str]]:
    """Name, colour and description for every label the policy names.

    **Every one, including the two this script never writes.** `cause` is read
    rather than written and `assessed` is written only by `assess`, but a label
    a command needs and does not create is a setup step nobody is told about:
    the gate instructs `assess <N> --none`, which fails at the wire against a
    label the repository does not have, and the accrual reads a `cause` label
    that has to be hand-made before anything accrues. Creating a label is not
    the same act as writing one onto an issue, and the write rail is
    `writable_labels`, which is deliberately narrower than this.
    """
    specs = []
    for name, axis in policy["axes"].items():
        meaning = axis.get("meaning", name)
        colour = axis.get("color", "")
        for label, value in sorted(axis["values"].items(), key=lambda kv: kv[1]):
            specs.append((label, colour, f"Pool rating -- {meaning} ({value})"))
    for key, fallback in (("framed", "decided work, on the board"),
                          ("cause", "observed cause of the issues linked under it"),
                          ("assessed", "asked whether it has a cause, and it is its own")):
        block = policy[key]
        specs.append((block["label"], block.get("color", ""),
                      block.get("meaning", fallback)))
    return specs


def cmd_labels(policy: dict, repo: str | None, dry_run: bool) -> int:
    """Create what the policy names and is missing; never touch what exists.

    Not `gh label create --force`: that is the idempotent form and it also
    rewrites the colour and description of a label already there, so a
    repository that had customised one would have the customisation quietly
    replaced by running a command whose whole point was that it changes
    nothing it does not have to.
    """
    raw = json.loads(
        gh(["label", "list", *_repo_args(repo), "--limit",
            str(LABEL_READ_LIMIT), "--json", "name"])
    )
    if len(raw) >= LABEL_READ_LIMIT:
        raise PoolError(
            f"the label read came back at its limit of {LABEL_READ_LIMIT}, so "
            f"a label that exists may read as missing and creating it would "
            f"fail. Raise LABEL_READ_LIMIT and run again"
        )
    existing = {lb["name"] for lb in raw}
    specs = label_specs(policy)
    # Both lines read the same set, so they cannot disagree about a label.
    # Reading "already present" off the write rail and "to create" off the
    # specs meant a label this command creates and never writes was absent
    # from one line and present in the other.
    missing = [spec for spec in specs if spec[0] not in existing]
    present = sorted({spec[0] for spec in specs} & existing)
    print(f"already present: {', '.join(present) or 'none'}")
    print(f"to create:       {', '.join(s[0] for s in missing) or 'none'}")
    if dry_run:
        return 0
    for label, colour, description in missing:
        args = ["label", "create", label, *_repo_args(repo), "--description", description]
        if colour:
            args += ["--color", colour]
        gh(args)
        print(f"created {label}")
    return 0


def resolve_ratings(policy: dict, labels: list[str]) -> dict[str, str]:
    """Each label to the axis that names it, refusing two on one axis.

    The command takes labels rather than an axis flag per axis, because the
    axes are the policy's and a flag named after one would be the script
    holding a vocabulary the policy is supposed to hold alone: a repository
    that renamed an axis would find a flag that no longer matched anything.
    """
    chosen: dict[str, str] = {}
    for label in labels:
        owner = next((name for name, axis in policy["axes"].items()
                      if label in axis["values"]), None)
        if owner is None:
            raise PoolError(
                f"'{label}' is not a rating this policy names. It names: "
                f"{', '.join(sorted(l for a in policy['axes'].values() for l in a['values']))}"
            )
        if owner in chosen:
            raise PoolError(
                f"'{chosen[owner]}' and '{label}' are both on axis '{owner}', "
                f"and an issue carries one value per axis"
            )
        chosen[owner] = label
    return chosen


def cmd_rate(policy: dict, repo: str | None, number: int,
             chosen: dict[str, str]) -> int:
    add, remove = [], []
    # Once, not per axis: the read does not depend on which axis is being set,
    # so rating both in one call used to make two identical `gh issue view`s.
    carried = set(issue_labels(number, repo))
    for axis_name, label in chosen.items():
        axis = policy["axes"][axis_name]
        add.append(label)
        # Only the values the issue actually carries come off, which costs one
        # read. An earlier version removed every other value on the axis and
        # argued the read away: `gh issue edit --remove-label` on a label the
        # issue does not have is accepted. That is true, and it is not the
        # case that bites. Probed against a live repository on 2026-09-06:
        #
        #   gh issue edit N --remove-label bug        -> exit 0   (issue lacks it)
        #   gh issue edit N --remove-label sev:1      -> exit 1   ('sev:1' not found)
        #
        # The second is a label the REPOSITORY does not have, which is exactly
        # the state before `labels` has been run -- so the unconditional form
        # made the first `rate` in any repository fail at the wire, on the one
        # command the cell tells a filer to use.
        remove += [other for other in axis["values"]
                   if other != label and other in carried]
    edit_labels(number, policy, add=add, remove=remove, repo=repo)
    print(f"#{number} rated {', '.join(sorted(add))}")
    return 0


def cmd_assess(policy: dict, repo: str | None, number: int) -> int:
    """Record that an issue was asked whether it has a cause, and is its own.

    Only this half is a label. Where the answer is that it *has* a cause, the
    record is the sub-issue link the `filing` cell governs, and duplicating that
    here would give one relationship two representations that could disagree.

    There is no third state: an issue never asked carries nothing, exactly as an
    issue in the pool carries nothing. The difference between asked-and-none and
    never-asked is what the amendment required be visible, and it is the presence
    or absence of this one label.
    """
    edit_labels(number, policy, add=[policy["assessed"]["label"]], remove=[], repo=repo)
    print(f"#{number} assessed: asked, and it is its own cause")
    return 0


def cmd_cycle(policy: dict, repo: str | None, dry_run: bool = False) -> int:
    """The fade, the accrual and the assessment bound, in one pass.

    It writes nothing except the closes `fade.closes` licenses, and it names
    every one of those before it makes it -- but only within a single run, which
    is no use to somebody deciding whether to turn the switch on. `--dry-run`
    is how that list is read first, as `labels` has one and the board's `apply`
    has one; a command whose only write is a close and which had neither was the
    odd one out.
    """
    pool, _ = read_pool(policy, repo)
    order = policy["order"]
    # Carrying a symptom is not rising, and neither is having moved. The first
    # spelling of this listed every item with a symptom, so items the accrual
    # had not touched printed under a heading saying what rose. The second
    # tested `effective != _bare`, which is worse in a way the first was not:
    # `effective` applies the fade after the accrual, so an item with one
    # symptom (zero bands) that has been quiet for a window differs from its
    # bare pair by having gone *down*, and printed as risen. What rising means
    # is an increase, so that is what this asks.
    def _rose(item: dict) -> bool:
        bare = _bare(item, policy)
        return any(item["effective"].get(name) is not None
                   and bare.get(name) is not None
                   and item["effective"][name] > bare[name]
                   for name in order)

    risen = [it for it in pool if it.get("symptoms") and _rose(it)]
    floored = [it for it in pool if at_floor(it, policy, it["effective"])]
    unassessed = [it for it in pool if not it["assessed"]]
    nxt = unassessed[:policy["assessment"]["per_cycle"]]

    print(f"pool: {len(pool)}   risen: {len(risen)}   at the floor: {len(floored)}   "
          f"never assessed: {len(unassessed)}")

    if risen:
        print("")
        print("risen, from the symptoms under them:")
        for item in risen:
            print(f"  {_line(item, policy)}   ({len(item['symptoms'])} open)")

    if floored:
        print("")
        # `order[1]`, not `order[-1]`: with two axes they are the same and
        # with three they are not, so this header named an axis that had not
        # moved over rows the fade had floored on a different one.
        print(f"at the floor of {order[1]}, having been quiet:")
        for item in floored:
            print(f"  {_line(item, policy)}")

    if nxt:
        print("")
        print(f"next to assess, {len(nxt)} of {len(unassessed)} never asked:")
        for item in nxt:
            print(f"  {_line(item, policy)}")
        print("  ask why for each, then link it under its cause or "
              "`assess <N> --none`")

    print("")
    if not floored:
        print("nothing has reached the floor, so nothing is closable")
    elif not policy["fade"]["closes"]:
        print("fade.closes is false, so nothing above was closed. A repository "
              "that wants the fade to close sets it true in its own policy")
    elif dry_run:
        for item in floored:
            print(f"would close #{item['number']} as not planned")
        print("--dry-run, so nothing above was closed")
    else:
        for item in floored:
            print(f"closing #{item['number']} as not planned; its body and every "
                  f"comment stay, so the next symptom reopens it")
            gh(["issue", "close", str(item["number"]), *_repo_args(repo),
                "--reason", "not planned"])
    return 0


def cmd_frame(policy: dict, repo: str | None, number: int) -> int:
    edit_labels(number, policy, add=[policy["framed"]["label"]], remove=[], repo=repo)
    print(f"#{number} is marked framed -- it leaves the pool, and the board "
          f"holds it from the next sync if the issue is open")
    return 0


def cmd_unframe(policy: dict, repo: str | None, number: int) -> int:
    edit_labels(number, policy, add=[], remove=[policy["framed"]["label"]], repo=repo)
    print(f"#{number} returns to the pool -- the board drops it at the next sync")
    return 0


# --------------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pool.py",
        description="The pool: what has been filed but not yet decided on.",
    )
    parser.add_argument("--repo", metavar="OWNER/REPO",
                        help="the repository to read; inferred from the checkout otherwise")
    parser.add_argument("--policy", metavar="PATH", type=Path,
                        help="a policy file to use instead of the resolved one")
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list", help="the pool, highest-rated first")
    listing.add_argument("--limit", type=int, help="show only this many")

    show = sub.add_parser("show", help="one issue's pool state and ratings")
    show.add_argument("number", type=int)

    shortlist = sub.add_parser("shortlist", help="the few worth raising")
    shortlist.add_argument("--count", type=int, help="override the policy's size")
    shortlist.add_argument("--unassessed", action="store_true",
                           help="raise even where the top of the pool is unassessed")

    cycle = sub.add_parser(
        "cycle", help="what has risen, what has floored, what to assess next")
    cycle.add_argument("--dry-run", action="store_true",
                       help="name the closes fade.closes would make, and make none")

    assess = sub.add_parser("assess", help="record that an issue is its own cause")
    assess.add_argument("number", type=int)
    assess.add_argument("--none", action="store_true", required=True,
                        help="the answer: it was asked, and it has no cause but itself")

    sub.add_parser("framed", help="the framed set, which is what the board holds")
    sub.add_parser("policy", help="the resolved policy and where it came from")

    labels = sub.add_parser("labels", help="create the policy's labels, idempotently")
    labels.add_argument("--dry-run", action="store_true")

    rate = sub.add_parser("rate", help="set an issue's ratings")
    rate.add_argument("number", type=int)
    rate.add_argument("--rating", metavar="LABEL", action="append", default=[],
                      help="a rating label the policy names; repeat for each axis")

    frame = sub.add_parser("frame", help="record that this is decided work")
    frame.add_argument("number", type=int)

    unframe = sub.add_parser("unframe", help="return a framed issue to the pool")
    unframe.add_argument("number", type=int)
    return parser


def dispatch(args: argparse.Namespace) -> int:
    source = args.policy if args.policy else find_policy()
    policy = load_policy(source)
    if args.command == "policy":
        return cmd_policy(policy, source)
    # Every command says which policy it resolved, before it acts. `--repo`
    # steers the wire and the policy comes from the working directory, so a
    # write against another repository carries this one's vocabulary -- and the
    # commands that write are the ones that used to say nothing at all.
    print(f"policy: {source}")
    if args.command == "list":
        return cmd_list(policy, args.repo, args.limit)
    if args.command == "framed":
        return cmd_framed(policy, args.repo)
    if args.command == "show":
        return cmd_show(policy, args.repo, args.number)
    if args.command == "shortlist":
        return cmd_shortlist(policy, args.repo, args.count, args.unassessed)
    if args.command == "cycle":
        return cmd_cycle(policy, args.repo, args.dry_run)
    if args.command == "assess":
        return cmd_assess(policy, args.repo, args.number)
    if args.command == "labels":
        return cmd_labels(policy, args.repo, args.dry_run)
    if args.command == "frame":
        return cmd_frame(policy, args.repo, args.number)
    if args.command == "unframe":
        return cmd_unframe(policy, args.repo, args.number)
    if args.command == "rate":
        if not args.rating:
            raise PoolError(
                "rate needs at least one --rating; 'policy' prints the labels "
                "this policy names"
            )
        return cmd_rate(policy, args.repo, args.number,
                        resolve_ratings(policy, args.rating))
    raise PoolError(f"no such command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        return dispatch(args)
    except PoolError as exc:
        print(f"pool: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

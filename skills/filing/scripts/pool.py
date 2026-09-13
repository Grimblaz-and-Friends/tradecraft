#!/usr/bin/env python3
"""The pool: pitches waiting for the owner to buy work.

An open issue is pooled unless it carries the policy's framed label. Ratings
are proposals, ordered by the policy; they neither accrue nor decay. The
explicit `fade` command closes quiet unframed pitches as not planned, with
`--dry-run` for a preview. Reads and shortlisting never close anything.

Run `python scripts/pool.py --help` for the commands. Global `--repo` and
`--policy` options precede the subcommand: the former steers GitHub, the latter
the vocabulary and closing policy. A repository's whole-file policy overrides
the shipped default, and every command prints the policy it resolved.

Only labels named by the retained policy are written. Retired assessment and
push state on existing issues is left intact and no longer read or written.
"""
from __future__ import annotations

import argparse
import json
import math
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

UNRATED = "-"

# The width of the issue-number column, shared by the header and every row.
ISSUE_COL = 8

# The policy chooses among implemented tie-break keys; the issue number
# supplies a total order after those keys. Missing activity sorts last.
TIE_BREAKS = {
    "recent": ("most recently touched",
               lambda it: -it["updated_at"].timestamp()
               if it.get("updated_at") else math.inf,
               lambda it: _stamp_shown(it.get("updated_at"))),
}


def _stamp_shown(stamp: "datetime | None") -> str:
    """One stamp as the shortlist prints it, at a precision that distinguishes it.

    Seconds where that is the whole of it, the full instant where a fraction
    would otherwise be truncated away. The sort term compares full precision,
    so a display that always truncated could name `recent` as what separated
    two items and then print two identical values beside it -- a line refuting
    its own claim, which is worse than no line. GitHub's `updatedAt` is
    second-granular; `_stamp` exists to survive payloads that are not.
    """
    if stamp is None:
        return "no stamp"
    stamp = stamp.astimezone(timezone.utc)
    if stamp.microsecond:
        return stamp.isoformat().replace("+00:00", "Z")
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


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

    for key in ("cause",):
        block = policy.get(key)
        if not isinstance(block, dict) or not isinstance(block.get("label"), str):
            raise PoolError(
                f"{path}: '{key}' must carry a 'label' naming one label"
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

    _whole(policy, path, "fade", "quiet_days", least=1)

    tie_break = policy.get("tie_break")
    # An override states its whole retained policy; no shipped defaults merge in.
    if tie_break is None:
        raise PoolError(
            f"{path}: 'tie_break' is missing. It lists the keys that order "
            f"items the axes leave equal, most significant first, and it is "
            f"required rather than defaulted -- this file states the whole "
            f"policy. Write [] to leave equals to the issue number and have "
            f"the shortlist say so. {_tie_break_keys()}"
        )
    # A separate refusal from the one above, because they are separate
    # mistakes: a policy that has the field in the wrong shape was told "does
    # not have it: add 'tie_break'" and sent to look at a file that plainly
    # has it.
    if not isinstance(tie_break, list) or any(not isinstance(key, str)
                                              for key in tie_break):
        raise PoolError(
            f"{path}: 'tie_break' is {tie_break!r}, which is not a list of key "
            f"names. It lists the keys that order items the axes leave equal, "
            f"most significant first -- [] to leave them to the issue number. "
            f"{_tie_break_keys()}"
        )
    if "symptoms" in tie_break:
        print(f"pool: {path}: tie_break 'symptoms' is retired and ignored; "
              "remove it from this policy", file=sys.stderr)
        tie_break = [key for key in tie_break if key != "symptoms"]
        policy["tie_break"] = tie_break
    unknown = [key for key in tie_break if key not in TIE_BREAKS]
    if unknown:
        raise PoolError(
            f"{path}: 'tie_break' names {', '.join(repr(k) for k in unknown)}, "
            f"which this script cannot compute -- a tie-break key is code and "
            f"not a name. {_tie_break_keys()}"
        )
    repeated = sorted({key for key in tie_break if tie_break.count(key) > 1})
    if repeated:
        raise PoolError(
            f"{path}: 'tie_break' names {', '.join(repeated)} more than once, "
            f"and a key consulted twice decides nothing the first look did not"
        )

    closes = policy.get("fade", {}).get("closes")
    if not isinstance(closes, bool):
        raise PoolError(
            f"{path}: 'fade.closes' must be true or false. It is what decides "
            f"whether the fade closes anything at all, so it is stated rather "
            f"than defaulted"
        )

    return policy


def _tie_break_keys() -> str:
    """Name the recency key and its meaning in a policy refusal.

    Recency is the only supported key; an empty list omits that tie-break.
    The refusal describes the vocabulary rather than supplying a policy value.
    """
    keys = ", ".join(f"{name} ({TIE_BREAKS[name][0]})" for name in sorted(TIE_BREAKS))
    return (f"Its keys are {keys}, and the sequence you write is the order "
            f"they are consulted in")


def _whole(policy: dict, path: Path, block: str, key: str, *, least: int) -> None:
    """Validate a required whole-number setting before a command acts."""
    values = policy.get(block)
    if not isinstance(values, dict):
        raise PoolError(f"{path}: '{block}' must be an object")
    value = values.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < least:
        raise PoolError(f"{path}: '{block}.{key}' must be a whole number of at least {least}")


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
    """The only labels issue-edit commands may write, including removals."""
    names = {label for axis in policy["axes"].values() for label in axis["values"]}
    names.add(policy["framed"]["label"])
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

    `updatedAt` is here because **two** mechanisms are read from it: the fade,
    and the `recent` tie-break key that orders items the ratings leave equal.
    GitHub maintains it; no separate activity record is written. **Dropping it does not fail loudly** -- every `recent` term
    becomes `math.inf`, every pair ties on that key, the ordering falls back to
    the issue number, and the shortlist reports that collapse as a fact rather
    than as a broken read. The tests stub this function, so the pin on the
    field list is what stands between a later fade rework and that silence.
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


def _infer_repo() -> str:
    """Name the checkout's repository for callers that compare local and remote state."""
    try:
        raw = gh(["repo", "view", "--json", "nameWithOwner"])
    except PoolError as exc:
        raise PoolError(
            f"cannot work out which repository this is: {exc}. "
            "Name it with --repo OWNER/REPO"
        ) from None
    return json.loads(raw)["nameWithOwner"]


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
    """Partition open issues once; only the pool takes the advisory order."""
    pooled, framed = [], []
    for issue in open_issues(repo):
        item = _item(issue, policy)
        (framed if item["framed"] else pooled).append(item)
    pooled.sort(key=lambda it: sort_key(it, policy))
    return pooled, framed


def _item(issue: dict, policy: dict) -> dict:
    labels = [label["name"] for label in issue.get("labels", [])]
    item = {"number": issue["number"], "title": issue.get("title", ""),
            "ratings": {}, "clashes": [],
            "framed": policy["framed"]["label"] in labels,
            "updated_at": _stamp(issue.get("updatedAt"))}
    for name, axis in policy["axes"].items():
        label, clashed = rating_of(labels, axis)
        item["ratings"][name] = label
        if clashed:
            item["clashes"].append(name)
    return item


def rating_values(item: dict, policy: dict) -> dict[str, int | None]:
    """Read each proposed band without resolving missing or clashing ratings."""
    return {name: None if item["ratings"].get(name) is None or name in item["clashes"]
            else axis["values"][item["ratings"][name]]
            for name, axis in policy["axes"].items()}


def _stamp(raw: str | None) -> datetime | None:
    """An offset-bearing activity instant, or unknown; never guess a closing clock."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.utcoffset() is not None else None


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


def rating_key(item: dict, policy: dict) -> tuple:
    """The part of the order the ratings decide: everything before the tie-break.

    Unrated is not zero. An issue nobody has rated has not been judged
    harmless; it has not been judged. Sorting it below every rated item says
    that, where a zero would assert the bottom of the scale.

    Named rather than inlined in `sort_key` because two items are *tied* when
    this much of their keys agree, and the shortlist has to say whether its cut
    fell inside a tie. A second spelling of what a tie is would drift from the
    one that sorts.
    """
    order = policy["order"]
    derived = rating_values(item, policy)
    values = []
    complete = True
    for name in order:
        # Per axis. Which axes are unusable is `rating_values`'s to say; this
        # reads its answer one axis at a time rather than re-deriving it.
        value = derived.get(name)
        if value is None:
            complete = False
            values.append(0)
        else:
            values.append(value)
    return (0 if complete else 1, *[-v for v in values])


def tie_terms(item: dict, policy: dict) -> tuple:
    """What orders two items the ratings left equal, in the policy's sequence."""
    return tuple(TIE_BREAKS[name][1](item) for name in policy["tie_break"])


def sort_key(item: dict, policy: dict) -> tuple:
    """The ratings, then the policy's tie-break, then the issue number.

    **The number is the last resort and not the rule.** A sort needs a total
    order and the number is what supplies one; it used to be the only thing
    consulted once two items agreed on both ratings, which made the first five
    a shortlist raised out of a nineteen-way tie the five oldest and nothing
    more. It is still here, still last, and the shortlist now says when it was
    what decided.
    """
    return (*rating_key(item, policy), *tie_terms(item, policy), item["number"])


def is_rated(item: dict, policy: dict) -> bool:
    return all(item["ratings"].get(name) for name in policy["axes"]) and not item["clashes"]


# ----------------------------------------------------------------- printing


def _widths(policy: dict) -> list[int]:
    return [max(len(name), len("CLASH"), *(len(v) for v in policy["axes"][name]["values"]))
            for name in policy["order"]]


def _line(item: dict, policy: dict) -> str:
    cells = []
    for name, width in zip(policy["order"], _widths(policy)):
        label = "CLASH" if name in item["clashes"] else item["ratings"].get(name) or UNRATED
        cells.append(label.ljust(width))
    prefix = f"#{item['number']:<{ISSUE_COL - 2}} "
    stamp = _stamp_shown(item.get("updated_at"))
    return (f"{prefix}{'  '.join(cells)}  {stamp:<27}  "
            f"{fade_status(item, policy):<8}  {item['title'][:70]}")


def _header(policy: dict) -> str:
    cells = [name.ljust(width) for name, width in zip(policy["order"], _widths(policy))]
    return ("issue".ljust(ISSUE_COL) + "  ".join(cells)
            + "  " + "last activity (UTC)".ljust(27) + "  fade      title")


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
    """Show the proposal and the activity the fade uses for this issue."""
    for name in policy["order"]:
        label = item["ratings"].get(name)
        axis = policy["axes"][name]
        if name in item["clashes"]:
            print(f"  {name}: CLASH -- more than one of {sorted(axis['values'])}")
        elif label is None:
            print(f"  {name}: unrated ({axis.get('meaning', name)})")
        else:
            print(f"  {name}: {label} = {axis['values'][label]} ({axis.get('meaning', name)})")
    print(f"  last activity: {_stamp_shown(item.get('updated_at'))}")
    print(f"  fade: {fade_status(item, policy)}; quiet window {policy['fade']['quiet_days']} days; "
          f"closes={policy['fade']['closes']}")
    print(f"  {item['title']}")


def cmd_shortlist(policy: dict, repo: str | None, count: int | None) -> int:
    # `shortlist_size` is validated on load; the flag that overrides it was not,
    # and a negative sliced from the end -- raising most of the pool under a
    # header saying it was raising a few, with the unrated caveat suppressed
    # because `len(rated) < size` is false for a negative.
    if count is not None and count < 1:
        raise PoolError("--count must be a whole number of at least 1")
    size = count if count is not None else policy["shortlist_size"]
    pool, _ = read_pool(policy, repo)
    few = pool[:size]

    rated = [it for it in pool if is_rated(it, policy)]
    # Against what is actually being raised, not against the size asked for: a
    # pool of two fully-rated items under a size of five is not partly unrated,
    # and saying so told a reader to discount a ranking that was sound.
    unrated_few = [it for it in few if not is_rated(it, policy)]
    print(f"pool: {len(pool)}   rated: {len(rated)}   raising: {len(few)}")
    if unrated_few:
        print(
            "fewer rated items than the shortlist holds, so what follows is "
            "partly unrated filings rather than the highest-rated -- ordered "
            "among themselves by the policy's tie-break like everything else, "
            "not by age. These are candidates for judgment, not purchases."
        )
    print(_header(policy))
    for item in few:
        print(_line(item, policy))
    print(cut_line(pool, few, policy))
    print("")
    print("When there is room, choose the strongest pitches to put to the owner "
          "with the case for and against; this shortlist buys nothing.")
    return 0


def cut_line(pool: list[dict], few: list[dict], policy: dict) -> str:
    """What decided the boundary between the last item raised and the first not.

    **The cut is the only place the tie-break decides who the owner sees**, so
    it is what this reports rather than every tie in the pool. And it is
    reported in every case, including the cases where no tie-break ran: a line
    that appeared only sometimes would leave a reader unable to tell a cut the
    ratings made from a tie-break that had silently stopped working.

    It names the two issues at the cut so the claim is checkable against the
    rows above it, and it names a key only where that key's own value actually
    differs across the cut -- naming the policy's first key regardless would be
    a judgment asserted rather than one made. **And it carries that key's two
    values**, because a key that separated the pair by four seconds and one
    that separated them by a month read identically without them.
    """
    if not pool:
        return "the pool is empty, so nothing was chosen over anything"
    if len(few) >= len(pool):
        return ("the shortlist holds the whole pool, so nothing was chosen "
                "over anything")
    last, first = few[-1], pool[len(few)]
    tie = rating_key(last, policy)
    if rating_key(first, policy) != tie:
        return (f"nothing is tied at the cut: the ratings alone chose these "
                f"{len(few)}")
    tied = [it for it in pool if rating_key(it, policy) == tie]
    here = [it for it in few if rating_key(it, policy) == tie]
    # `tie[0]` is the tier, which is 0 only where every axis carries a usable
    # band. Below it are the items nobody rated and the ones rated twice, and
    # what they share is that nobody chose -- not that anybody chose alike.
    level = ("are tied on the ratings" if tie[0] == 0 else
             "carry no usable rating on every axis, so the ratings separate "
             "none of them")
    head = (f"{len(tied)} in the pool {level}, and this shortlist holds "
            f"{len(here)} of them")
    if not policy["tie_break"]:
        return (f"{head}; no tie-break key is configured, so the lower issue "
                f"number is what put #{last['number']} above "
                f"#{first['number']}")
    for name in policy["tie_break"]:
        shown, term, show = TIE_BREAKS[name]
        if term(last) != term(first):
            return (f"{head}; {shown} is what put #{last['number']} above "
                    f"#{first['number']}, {show(last)} against {show(first)}")
    return (f"{head}; no tie-break key separated these two, so the lower "
            f"issue number is what put #{last['number']} above "
            f"#{first['number']} -- which says nothing about the rest of "
            f"the tie")


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
    """Provision ratings, framing, and the cause label used by existing board groups."""
    specs = []
    for name, axis in policy["axes"].items():
        for label, value in sorted(axis["values"].items(), key=lambda kv: kv[1]):
            specs.append((label, axis.get("color", ""),
                          f"Pool rating -- {axis.get('meaning', name)} ({value})"))
    for key in ("framed", "cause"):
        block = policy[key]
        specs.append((block["label"], block.get("color", ""), block.get("meaning", key)))
    return specs


def existing_labels(repo: str | None) -> set[str]:
    """Every label name the repository has.

    Shared by the command that creates the missing ones and the command that
    refuses to write one that is missing, so the two cannot disagree about what
    the repository has -- and so the read's own limit is guarded once.
    """
    raw = json.loads(
        gh(["label", "list", *_repo_args(repo), "--limit",
            str(LABEL_READ_LIMIT), "--json", "name"])
    )
    if len(raw) >= LABEL_READ_LIMIT:
        raise PoolError(
            f"the label read came back at its limit of {LABEL_READ_LIMIT}, so "
            f"a label that exists may read as missing. Raise LABEL_READ_LIMIT "
            f"and run again"
        )
    return {lb["name"] for lb in raw}


def cmd_labels(policy: dict, repo: str | None, dry_run: bool) -> int:
    """Create what the policy names and is missing; never touch what exists.

    Not `gh label create --force`: that is the idempotent form and it also
    rewrites the colour and description of a label already there, so a
    repository that had customised one would have the customisation quietly
    replaced by running a command whose whole point was that it changes
    nothing it does not have to.
    """
    existing = existing_labels(repo)
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


def fade_status(item: dict, policy: dict, now: datetime | None = None) -> str:
    """Closing eligibility is independent of ratings and excludes bought work."""
    if item.get("framed"):
        return "framed"
    stamp = item.get("updated_at")
    moment = now or datetime.now(timezone.utc)
    if stamp is None:
        return "unknown"
    if stamp > moment:
        return "future"
    return "due" if quiet_windows(item, policy, moment) >= 1 else "active"


def cmd_fade(policy: dict, repo: str | None, dry_run: bool = False) -> int:
    """Preview or close quiet pitches, rechecking each candidate before writing."""
    pooled, _ = read_pool(policy, repo)
    due = [it for it in pooled if fade_status(it, policy) == "due"]
    for item in pooled:
        status = fade_status(item, policy)
        if status in {"unknown", "future"}:
            print(f"#{item['number']} skipped: {status} activity; no closing clock")
    print(f"pool: {len(pooled)}   due: {len(due)}   quiet window: {policy['fade']['quiet_days']} days")
    for item in due:
        print(f"#{item['number']} due: last activity {_stamp_shown(item['updated_at'])}")
    if dry_run or not policy["fade"]["closes"]:
        for item in due:
            print(f"would close #{item['number']} as not planned")
        print("--dry-run: nothing closed" if dry_run else "fade.closes is false: nothing closed")
        return 0
    for item in due:
        number = item["number"]
        fresh = json.loads(gh(["issue", "view", str(number), *_repo_args(repo),
                              "--json", "number,title,state,labels,updatedAt"]))
        if fresh.get("number") != number or not isinstance(fresh.get("labels"), list):
            raise PoolError(f"#{number}: incomplete issue reread; nothing closed for this item")
        if fresh.get("state") != "OPEN":
            print(f"#{number} skipped: no longer open, or state unavailable")
            continue
        current = _item(fresh, policy)
        status = fade_status(current, policy)
        if status != "due":
            print(f"#{number} skipped after reread: {status}")
            continue
        reason = (f"Lapsed: no activity for at least {policy['fade']['quiet_days']} days "
                  f"(last activity {_stamp_shown(current['updated_at'])}); no work was purchased.")
        gh(["issue", "close", str(number), *_repo_args(repo),
            "--reason", "not planned", "--comment", reason])
        print(f"#{number} closed as not planned. {reason}")
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

    shortlist = sub.add_parser(
        "shortlist", help="the few worth putting to the owner")
    shortlist.add_argument("--count", type=int, help="override the policy's size")
    fade = sub.add_parser("fade", help="close quiet unframed pitches as not planned")
    fade.add_argument("--dry-run", action="store_true", help="preview without closing")

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
        return cmd_shortlist(policy, args.repo, args.count)
    if args.command == "fade":
        return cmd_fade(policy, args.repo, args.dry_run)
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

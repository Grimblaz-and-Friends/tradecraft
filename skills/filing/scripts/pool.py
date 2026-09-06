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

**Every label name, every rating value, the ordering and the shortlist size
live in the policy file.** `pool-policy.json` beside this script carries the
defaults; a
repository overrides them with a file of that name at its own root, and the
override is read instead of the default rather than merged into it, so what a
repository states is the whole policy and no field it did not write can
surprise it later.

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
        python scripts/pool.py shortlist [--count N]
        python scripts/pool.py framed
        python scripts/pool.py policy
        python scripts/pool.py labels    [--dry-run]
        python scripts/pool.py rate      N --rating LABEL [--rating LABEL]
        python scripts/pool.py frame     N
        python scripts/pool.py unframe   N

  list       the pool, highest-rated first, with each item's ratings
  show       one issue: whether it is framed, and what it is rated
  shortlist  the few worth raising, at the policy's size
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

    size = policy.get("shortlist_size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise PoolError(f"{path}: 'shortlist_size' must be a whole number of at least 1")

    return policy


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


def _repo_args(repo: str | None) -> list[str]:
    """Nothing when no repository is named, so `gh` infers it from the checkout."""
    return ["--repo", repo] if repo else []


def open_issues(repo: str | None = None) -> list[dict]:
    """Every open issue with its labels, in one call.

    Labels come back in the same read as the numbers because every command
    here needs both, and a second call per issue over a hundred-item board is
    a hundred round trips for something one query already carries.
    """
    raw = gh([
        "issue", "list", *_repo_args(repo), "--state", "open",
        "--limit", str(ISSUE_READ_LIMIT), "--json", "number,title,labels",
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
    pool: list[dict] = []
    framed: list[dict] = []
    for issue in open_issues(repo):
        labels = [lb["name"] for lb in issue.get("labels", [])]
        item = {
            "number": issue["number"],
            "title": issue.get("title", ""),
            "ratings": {},
            "clashes": [],
        }
        for name, axis in policy["axes"].items():
            label, clashed = rating_of(labels, axis)
            item["ratings"][name] = label
            if clashed:
                item["clashes"].append(name)
        if framed_label in labels:
            framed.append(item)
        else:
            pool.append(item)
    pool.sort(key=lambda it: sort_key(it, policy))
    return pool, framed


def sort_key(item: dict, policy: dict) -> tuple:
    """Rated above unrated, then each axis in the policy's order, then oldest first.

    Unrated is not zero. An issue nobody has rated has not been judged
    harmless; it has not been judged. Sorting it below every rated item says
    that, where a zero would assert the bottom of the scale.
    """
    axes = policy["axes"]
    order = policy["order"]
    values = []
    complete = True
    for name in order:
        label = item["ratings"].get(name)
        # Per axis, not over the whole clash list. Testing the list meant one
        # clashed axis discarded every clean rating the item had, so an issue
        # at the top of the severity scale with a stray second urgency label
        # sorted below the mildest thing in the pool on issue number alone.
        if label is None or name in item["clashes"]:
            complete = False
            values.append(0)
        else:
            values.append(axes[name]["values"][label])
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
    return [max(len(name), len("CLASH"), *(len(v) for v in policy["axes"][name]["values"]))
            for name in policy["order"]]


def _line(item: dict, policy: dict) -> str:
    cells = []
    for name, width in zip(policy["order"], _widths(policy)):
        label = item["ratings"].get(name) or UNRATED
        if name in item["clashes"]:
            label = "CLASH"
        cells.append(label.ljust(width))
    return f"#{item['number']:<6} {'  '.join(cells)}  {item['title'][:72]}"


def _header(policy: dict) -> str:
    cells = [name.ljust(width) for name, width in zip(policy["order"], _widths(policy))]
    return "issue    " + "  ".join(cells) + "  title"


def cmd_list(policy: dict, source: Path, repo: str | None, limit: int | None) -> int:
    if limit is not None and limit < 1:
        raise PoolError("--limit must be a whole number of at least 1")
    pool, framed = read_pool(policy, repo)
    unrated = [it for it in pool if not is_rated(it, policy)]
    print(f"policy: {source}")
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
    for name in policy["order"]:
        label = item["ratings"].get(name)
        axis = policy["axes"][name]
        if name in item["clashes"]:
            print(f"  {name}: CLASH -- more than one of {sorted(axis['values'])}")
        elif label is None:
            print(f"  {name}: unrated ({axis.get('meaning', name)})")
        else:
            print(f"  {name}: {label} = {axis['values'][label]} "
                  f"({axis.get('meaning', name)})")
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
    raised = pool[:size]
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
    print(f"writable labels: {', '.join(sorted(writable_labels(policy)))}")
    print(json.dumps(policy, indent=2, sort_keys=True))
    return 0


# ------------------------------------------------------------------ writing


def label_specs(policy: dict) -> list[tuple[str, str, str]]:
    """Name, colour and description for every label the policy names."""
    specs = []
    for name, axis in policy["axes"].items():
        meaning = axis.get("meaning", name)
        colour = axis.get("color", "")
        for label, value in sorted(axis["values"].items(), key=lambda kv: kv[1]):
            specs.append((label, colour, f"Pool rating -- {meaning} ({value})"))
    framed = policy["framed"]
    specs.append((framed["label"], framed.get("color", ""),
                  framed.get("meaning", "decided work, on the board")))
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
    allowed = writable_labels(policy)
    missing = [spec for spec in label_specs(policy) if spec[0] not in existing]
    present = sorted(allowed & existing)
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
        carried = set(issue_labels(number, repo))
        remove += [other for other in axis["values"]
                   if other != label and other in carried]
    edit_labels(number, policy, add=add, remove=remove, repo=repo)
    print(f"#{number} rated {', '.join(sorted(add))}")
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
    if args.command == "list":
        return cmd_list(policy, source, args.repo, args.limit)
    if args.command == "framed":
        return cmd_framed(policy, args.repo)
    if args.command == "show":
        return cmd_show(policy, args.repo, args.number)
    if args.command == "shortlist":
        return cmd_shortlist(policy, args.repo, args.count)
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

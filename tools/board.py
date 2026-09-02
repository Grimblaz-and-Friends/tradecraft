#!/usr/bin/env python3
"""The board's transport: read it, reconcile it, settle it, write it (issue #83).

The maintaining agent supplies the judgment -- what the order should be, which
issues one change would close together, what the refresh note says. This script
supplies everything that is not judgment, so that judgment is what the agent's
context is spent on.

Two jobs a single membership comparison cannot do at once, and the reason the
run order below is what it is. *Reconciling* asks whether the board holds the
open set; *settling* asks whether the ordered read has caught up with the
board. They return opposite answers about the same newly added issue --
reconcile says place it, settle says wait for it -- so they are separate steps
with separate failure behaviour, and only settling may halt.

Neither read of the board is authoritative, and the target membership always
comes from `gh issue list` for that reason. The ordered read is the worse of
the two: after a write it returns a short list *and* a matching short
`totalCount`, so its incompleteness is undetectable from the connection's own
count. The unordered read was observed carrying the full membership at a
moment the ordered one was short -- which is why step 1 uses it, and is an
observed run rather than a deduction, since `ProjectV2.items` declares a
`defaultValue` of `{field: POSITION, direction: ASC}` for `orderBy` and the
two queries should therefore be identical. But it lags too: a trial run's
second pass read 78 of 86 items from it. **So the run order is not safe
because any read is trusted.** It is safe because step 2 is idempotent --
`addProjectV2ItemById` on an item already present is a no-op, so a stale
step-1 read costs a redundant add and never a duplicate -- and because step 3
is the gate that everything downstream waits on.

Usage:  python tools/board.py show   [--plan PATH]
        python tools/board.py sync   [--dry-run]
        python tools/board.py apply  --plan PATH [--dry-run]
        python tools/board.py note   --body PATH
        python tools/board.py next
        python tools/board.py notes  [--limit N]
        python tools/board.py init

  next   the answer: the first item not already being worked, with its title
  show   read the board and write the current state as a plan file
  sync   steps 1-3: reconcile membership against the open set, then settle
  apply  step 4: order and label the board from a plan file
  note   step 5: post the refresh note as a project status update
  notes  read the refresh notes back, newest first
  init   create the board and its fields, once
"""
from __future__ import annotations

import argparse
import json
import re
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from winio import utf8_stdio  # noqa: E402

OWNER = os.environ.get("TRADECRAFT_BOARD_OWNER", "Grimblaz-and-Friends")
REPO = os.environ.get("TRADECRAFT_BOARD_REPO", "tradecraft")

# Overridable so the transport can be pointed at a board that is not the live
# one -- a scratch board for a trial run, or a second repository's. The title
# is the only handle: the project is found by matching it, so two projects
# sharing a title under one owner is the ambiguity this also lets a caller
# avoid.
BOARD_TITLE = os.environ.get("TRADECRAFT_BOARD_TITLE", "tradecraft board")

BANDS = ["Standing", "Front", "Bundles", "Review-set", "Tail"]
STATUSES = ["Queued", "In progress", "In flight", "Blocked", "Deferred"]

# The statuses that take an item out of contention. The answer to "what next"
# is the first item carrying none of them, so this set and that rule are one
# thing and are defined once -- a second copy is how the two drift apart.
UNAVAILABLE = frozenset(STATUSES[1:])

# `Standing` means an item is not in contention, which is a claim about
# availability -- and availability is Status's job, not Band's. The pair
# Standing + Queued asserts both at once, and the reading rule cannot see Band,
# so such a row silently BECOMES the answer. A trial run placed two of them at
# positions 1 and 2 and the board confidently offered work its author had not
# ranked at all. Refused at the plan rather than documented.
STANDING = "Standing"

# How long the ordered read is given to catch up with the board's membership,
# and how often it is asked. Exceeding the bound is a loud halt: nothing writes
# an ordering from a read that never settled.
SETTLE_TIMEOUT_S = 60.0
SETTLE_INTERVAL_S = 2.0

EMPTY = "-"

# What a bundle name may contain. `options_payload` interpolates it into a
# GraphQL string with only a quote-strip for escaping, so a quote silently
# creates a differently-named option that `set_field` then fails to find --
# after every position move has already landed -- and a backslash or a brace
# malforms the query outright. Validated at parse time, before any mutation,
# which is also what makes `--dry-run` catch it. The live board's names all
# pass: "PR G - decision-log", "Post-#260 redraw", "Front 3 - PR J
# seat/dispatch hygiene".
BUNDLE_CHARS = re.compile(r"^[A-Za-z0-9 #/_.()-]+$")


class BoardError(Exception):
    """A condition the caller must see rather than a traceback."""


# ---------------------------------------------------------------- plan format


class Row:
    """One issue's placement. Order is the row's position in the file."""

    __slots__ = ("issue", "band", "bundle", "status")

    def __init__(self, issue: int, band: str, bundle: str, status: str) -> None:
        self.issue = issue
        self.band = band
        self.bundle = bundle
        self.status = status

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Row) and self.as_tuple() == other.as_tuple()

    def __repr__(self) -> str:
        return f"Row({self.issue}, {self.band!r}, {self.bundle!r}, {self.status!r})"

    def as_tuple(self) -> tuple[int, str, str, str]:
        return (self.issue, self.band, self.bundle, self.status)


def parse_plan(text: str) -> list[Row]:
    """Parse a plan file. Order is file order; blank and '#' lines are ignored.

    Raises BoardError rather than returning a partial plan: a plan that lost a
    row to a typo would silently drop that issue off the board.
    """
    rows: list[Row] = []
    seen: set[int] = set()
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("\t")]
        if len(parts) != 4:
            raise BoardError(
                f"line {lineno}: expected 4 tab-separated fields, got {len(parts)}: {raw!r}"
            )
        number, band, bundle, status = parts
        if not number.isdigit():
            raise BoardError(f"line {lineno}: issue must be a bare number, got {number!r}")
        issue = int(number)
        if issue in seen:
            raise BoardError(f"line {lineno}: issue #{issue} appears twice")
        if band not in BANDS:
            raise BoardError(f"line {lineno}: unknown band {band!r}; known: {BANDS}")
        if status not in STATUSES:
            raise BoardError(f"line {lineno}: unknown status {status!r}; known: {STATUSES}")
        if band == STANDING and status not in UNAVAILABLE:
            raise BoardError(
                f"line {lineno}: #{issue} is in the {STANDING!r} band with status {status!r}. "
                f"{STANDING} says an item is not in contention; the reading rule cannot see Band "
                f"and would offer this as the answer. Give it a status that excludes it "
                f"({sorted(UNAVAILABLE)}), or put it in a band that does not claim otherwise"
            )
        if not BUNDLE_CHARS.match(bundle):
            raise BoardError(
                f"line {lineno}: bundle {bundle!r} is empty or holds a character that does not "
                f"survive being sent to GitHub. Use letters, digits, spaces and any of "
                f"#/_.()- , or {EMPTY!r} for standalone"
            )
        seen.add(issue)
        rows.append(Row(issue, band, bundle, status))
    if not rows:
        raise BoardError("plan is empty")
    return rows


def format_plan(rows: list[Row]) -> str:
    """Render rows as a plan file. Round-trips through parse_plan."""
    out = [
        "# One issue per line, in board order. Reorder lines to reorder the board.",
        "# issue\tband\tbundle\tstatus",
        f"# bands:    {', '.join(BANDS)}",
        f"# statuses: {', '.join(STATUSES)}",
        f"# bundle '{EMPTY}' means standalone.",
    ]
    for r in rows:
        out.append(f"{r.issue}\t{r.band}\t{r.bundle}\t{r.status}")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------- the jobs


def reconcile(board: list[int], open_issues: list[int]) -> tuple[list[int], list[int]]:
    """Step 2. What to add to the board, and what to archive off it.

    Never raises. An open issue absent from the board is ordinary work -- it is
    the normal state after any filing -- and a board item no longer open is
    ordinary too. The caller does both and does not stop for either.
    """
    board_set, open_set = set(board), set(open_issues)
    return (
        sorted(open_set - board_set),
        sorted(board_set - open_set),
    )


def settle(read_ordered, target: list[int], *, timeout_s: float = SETTLE_TIMEOUT_S,
           interval_s: float = SETTLE_INTERVAL_S, sleep=time.sleep,
           clock=time.monotonic) -> list[int]:
    """Step 3. Poll the ordered read until it carries exactly the target membership.

    The only step that halts. A short read here is expected rather than
    anomalous -- step 2's own adds are the usual cause of it -- so a mismatch
    polls rather than failing. Exceeding the bound raises, naming what never
    appeared, and no ordering is written.
    """
    want = set(target)
    deadline = clock() + timeout_s
    while True:
        got = read_ordered()
        if set(got) == want:
            return got
        if clock() >= deadline:
            missing = sorted(want - set(got))
            extra = sorted(set(got) - want)
            raise BoardError(
                f"ordered read did not settle within {timeout_s:g}s; "
                f"missing from it: {missing or 'none'}; unexpected in it: {extra or 'none'}. "
                "No ordering was written."
            )
        sleep(interval_s)



def is_available(row: Row) -> bool:
    """The reading rule, in one place: can this item be picked up?

    An unset status is excluded as well as the four that take an item out of
    contention. `sync` adds items without writing any field, so between a sync
    and the apply that ranks them every new item carries EMPTY -- unranked, not
    available. It is excluded here rather than added to UNAVAILABLE, which
    would put "-" into the remedy list `parse_plan` prints at a reader.
    """
    return row.status not in UNAVAILABLE and row.status != EMPTY


def moves_for(current: list[int], target: list[int]) -> list[tuple[int, int | None]]:
    """Step 4's ordering walk, minimised: (issue, put-after-issue-or-None).

    Everything already sitting in the target's relative order is left alone;
    only the rest is moved. That is the difference between a refresh that
    touches a handful of items and one that rewrites the whole board, and the
    board's own cost is roughly linear in moves.

    The kept set is a longest increasing subsequence of the current order,
    indexed by target position -- the largest set of items no move is needed
    for. Items are moved in target order so each one's anchor is already final.
    """
    rank = {issue: i for i, issue in enumerate(target)}
    seq = [rank[i] for i in current if i in rank]

    # Longest increasing subsequence, by index, over seq.
    tails: list[int] = []          # tails[k] = index into seq of the LIS of length k+1
    back: list[int | None] = [None] * len(seq)
    for i, value in enumerate(seq):
        lo, hi = 0, len(tails)
        while lo < hi:
            mid = (lo + hi) // 2
            if seq[tails[mid]] < value:
                lo = mid + 1
            else:
                hi = mid
        back[i] = tails[lo - 1] if lo > 0 else None
        if lo == len(tails):
            tails.append(i)
        else:
            tails[lo] = i
    keep: set[int] = set()
    node = tails[-1] if tails else None
    while node is not None:
        keep.add(seq[node])
        node = back[node]

    moves: list[tuple[int, int | None]] = []
    for i, issue in enumerate(target):
        if i in keep:
            continue
        moves.append((issue, target[i - 1] if i > 0 else None))
    return moves


def diff_state(before: list[Row], after: list[Row]) -> dict:
    """Step 5's material: everything the run changed, for the note to be written against.

    A note authored against membership alone cannot say what moved, so position
    and field changes are reported too.
    """
    b_by = {r.issue: r for r in before}
    a_by = {r.issue: r for r in after}
    b_pos = {r.issue: i for i, r in enumerate(before)}
    a_pos = {r.issue: i for i, r in enumerate(after)}

    added = sorted(set(a_by) - set(b_by))
    dropped = sorted(set(b_by) - set(a_by))
    moved, relabelled = [], []
    for issue in sorted(set(a_by) & set(b_by)):
        if b_pos[issue] != a_pos[issue]:
            moved.append({"issue": issue, "from": b_pos[issue] + 1, "to": a_pos[issue] + 1})
        old, new = b_by[issue], a_by[issue]
        fields = {
            name: {"from": getattr(old, name), "to": getattr(new, name)}
            for name in ("band", "bundle", "status")
            if getattr(old, name) != getattr(new, name)
        }
        if fields:
            relabelled.append({"issue": issue, **fields})
    return {
        "added": added,
        "dropped": dropped,
        "moved": moved,
        "relabelled": relabelled,
        "unchanged": not (added or dropped or moved or relabelled),
    }


# ------------------------------------------------------------------- the wire


def gh(args: list[str]) -> str:
    proc = subprocess.run(
        ["gh", *args], capture_output=True, text=True, encoding="utf-8",
        errors="replace", stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        raise BoardError(f"gh {' '.join(args)} failed: {proc.stderr.strip()[:400]}")
    return proc.stdout


def gql(query: str, **variables: object) -> dict:
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        # -f, never -F. `gh api -F` applies magic type conversion: a value
        # starting with "@" is read as a filename, and {owner}/{repo}/{branch}
        # are expanded from the cwd's repository. A refresh note beginning "@",
        # or quoting a command template, would be rewritten before landing on an
        # append-only surface. Every variable here is String! or ID!, so none
        # needs typing.
        args += ["-f", f"{key}={value}"]
    data = json.loads(gh(args))
    if "errors" in data:
        raise BoardError(f"graphql: {json.dumps(data['errors'])[:400]}")
    return data["data"]


def open_issues() -> dict[int, str]:
    """The target membership, number -> node id, in one call.

    Always the issue list, never the board's own count: the board's ordered
    connection reports a short list and a matching short `totalCount` together,
    so it cannot be asked whether it is complete.
    """
    raw = gh([
        "issue", "list", "--repo", f"{OWNER}/{REPO}", "--state", "open",
        "--limit", "1000", "--json", "number,id",
    ])
    return {item["number"]: item["id"] for item in json.loads(raw)}


def org_projects() -> list[dict]:
    """Every project the owner holds, paged.

    Unpaged, a lookup past the first page reports the board missing -- and
    `pick_project`'s not-found message tells the caller to run `init`, which
    would create a duplicate and brick every command. The page bound and the
    existence check have to hold together or neither does.
    """
    nodes: list[dict] = []
    cursor = "null"
    while True:
        data = gql(
            "query($l:String!){organization(login:$l){projectsV2(first:100,after:%s)"
            "{pageInfo{hasNextPage endCursor} nodes{id title}}}}" % cursor,
            l=OWNER,
        )["organization"]["projectsV2"]
        nodes.extend(n for n in data["nodes"] if n)
        if not data["pageInfo"]["hasNextPage"]:
            return nodes
        cursor = '"%s"' % data["pageInfo"]["endCursor"]


def pick_project(nodes: list[dict], title: str) -> str:
    """The project id for `title`, or a BoardError naming what went wrong.

    Two projects sharing a title is the case worth refusing rather than
    guessing at: picking the first would write an ordering into whichever the
    API happened to list first, and the caller would see a plausible-looking
    board that is not the one they meant.
    """
    match = [n for n in nodes if n.get("title") == title]
    if not match:
        seen = sorted(n.get("title", "") for n in nodes)
        raise BoardError(
            f"no project titled {title!r}. Run 'python tools/board.py init', "
            f"or set TRADECRAFT_BOARD_TITLE to one of: {seen or 'none found'}"
        )
    if len(match) > 1:
        raise BoardError(
            f"{len(match)} projects are titled {title!r}; the title is the only handle this "
            "has, so rename all but one or point TRADECRAFT_BOARD_TITLE at a distinct title"
        )
    return match[0]["id"]


class Board:
    """The project, its fields, and the reads and writes the run order needs."""

    ITEM_FIELDS = """
      id
      content { ... on Issue { number } }
      fieldValues(first: 20) { nodes { ... on ProjectV2ItemFieldSingleSelectValue {
        name field { ... on ProjectV2FieldCommon { name } } } } }
    """

    def __init__(self) -> None:
        found = {"projectsV2": {"nodes": org_projects()}}
        self.project_id = pick_project(found["projectsV2"]["nodes"], BOARD_TITLE)
        self.fields = self._read_fields()

    def _read_fields(self) -> dict[str, dict]:
        nodes = gql(
            'query($p:ID!){node(id:$p){... on ProjectV2{fields(first:50){nodes{'
            '... on ProjectV2SingleSelectField{id name options{id name color description}}}}}}}',
            p=self.project_id,
        )["node"]["fields"]["nodes"]
        return {
            n["name"]: {"id": n["id"], "options": {o["name"]: o for o in n["options"]}}
            for n in nodes
            if n and n.get("name")
        }

    # The items connection refuses more than 100 per page. This board seeded at
    # 84, so the cursor branch below has never executed -- paging is here
    # against a board that outgrows one page, not because one has.
    PAGE = 100

    def _pages(self, order_by: str, selection: str) -> list[dict]:
        nodes: list[dict] = []
        cursor = "null"
        while True:
            data = gql(
                "query($p:ID!){node(id:$p){... on ProjectV2{items(first:%d,after:%s%s){"
                "pageInfo{hasNextPage endCursor} nodes{%s}}}}}"
                % (self.PAGE, cursor, order_by, selection),
                p=self.project_id,
            )["node"]["items"]
            nodes.extend(n for n in data["nodes"] if n)
            if not data["pageInfo"]["hasNextPage"]:
                return nodes
            cursor = '"%s"' % data["pageInfo"]["endCursor"]

    def members(self) -> list[int]:
        """Membership, from the read WITHOUT orderBy -- the less stale of the two.

        Not authoritative: it has been seen short as well. What makes acting
        on it safe is that its only consumer is the add/archive decision, and
        adding an item already present is a no-op.
        """
        nodes = self._pages("", "content{... on Issue{number}}")
        return sorted(n["content"]["number"] for n in nodes if n.get("content"))

    def ordered(self) -> list[dict]:
        """The ordered read. Lags its own writes; only settle() may act on a mismatch."""
        nodes = self._pages(",orderBy:{field:POSITION,direction:ASC}", self.ITEM_FIELDS)
        out = []
        for n in nodes:
            if not n.get("content"):
                continue
            values = {
                v["field"]["name"]: v["name"]
                for v in n["fieldValues"]["nodes"]
                if v and v.get("field")
            }
            # An unset field reports as EMPTY, never as the first valid option:
            # defaulting it to a real value would make a diff read "already
            # correct" for exactly the items whose value was never written.
            out.append({
                "item_id": n["id"],
                "issue": n["content"]["number"],
                "band": values.get("Band", EMPTY),
                "bundle": values.get("Bundle", EMPTY),
                "status": values.get("Status", EMPTY),
            })
        return out

    def rows(self) -> list[Row]:
        return [Row(i["issue"], i["band"], i["bundle"], i["status"]) for i in self.ordered()]

    def add(self, content_id: str) -> str:
        return gql(
            'mutation($p:ID!,$c:ID!){addProjectV2ItemById(input:{projectId:$p,contentId:$c})'
            "{item{id}}}",
            p=self.project_id, c=content_id,
        )["addProjectV2ItemById"]["item"]["id"]

    def archive(self, item_id: str) -> None:
        gql(
            'mutation($p:ID!,$i:ID!){archiveProjectV2Item(input:{projectId:$p,itemId:$i})'
            "{clientMutationId}}",
            p=self.project_id, i=item_id,
        )

    def move(self, item_id: str, after_id: str | None) -> None:
        if after_id is None:
            gql(
                'mutation($p:ID!,$i:ID!){updateProjectV2ItemPosition('
                "input:{projectId:$p,itemId:$i}){clientMutationId}}",
                p=self.project_id, i=item_id,
            )
        else:
            gql(
                'mutation($p:ID!,$i:ID!,$a:ID!){updateProjectV2ItemPosition('
                "input:{projectId:$p,itemId:$i,afterId:$a}){clientMutationId}}",
                p=self.project_id, i=item_id, a=after_id,
            )

    def set_field(self, item_id: str, field: str, value: str) -> None:
        spec = self.fields[field]
        option = spec["options"].get(value)
        if option is None:
            raise BoardError(f"field {field!r} has no option {value!r}; known: {sorted(spec['options'])}")
        gql(
            'mutation($p:ID!,$i:ID!,$f:ID!,$v:String!){updateProjectV2ItemFieldValue('
            "input:{projectId:$p,itemId:$i,fieldId:$f,value:{singleSelectOptionId:$v}})"
            "{projectV2Item{id}}}",
            p=self.project_id, i=item_id, f=spec["id"], v=option["id"],
        )

    def read_notes(self, limit: int) -> list[dict]:
        """The refresh notes, newest first.

        A session inheriting the board reads the last note to inherit the
        reasoning behind the order it is looking at -- which is the whole
        point of keeping the notes.

        `first`, never `last`, and the ordering is stated rather than assumed.
        `statusUpdates` declares `orderBy: {field: CREATED_AT, direction:
        DESC}`, so Relay's `last: N` slices the tail of a newest-first list --
        the N *oldest* notes. Three notes posted in sequence to a scratch board
        returned NOTE-ONE for `last:1` and NOTE-THREE for `first:1`. Under the
        old form this command silently served the seed note forever.
        """
        nodes = gql(
            "query($p:ID!){node(id:$p){... on ProjectV2{statusUpdates(first:%d,"
            "orderBy:{field:CREATED_AT,direction:DESC})"
            "{nodes{createdAt body}}}}}" % max(1, min(limit, 50)),
            p=self.project_id,
        )["node"]["statusUpdates"]["nodes"]
        return [n for n in nodes if n]

    def post_note(self, body: str) -> str:
        return gql(
            'mutation($p:ID!,$b:String!){createProjectV2StatusUpdate('
            "input:{projectId:$p,body:$b}){statusUpdate{createdAt}}}",
            p=self.project_id, b=body,
        )["createProjectV2StatusUpdate"]["statusUpdate"]["createdAt"]


def cmd_init() -> int:
    # Refuse rather than create a second board. `createProjectV2` is happy to
    # make a duplicate title, and `pick_project` then refuses every command
    # until someone deletes a project by hand -- while its own not-found
    # message is what sends a caller here. The check that would have caught it
    # already exists; init just never called it.
    existing = [n for n in org_projects() if n.get("title") == BOARD_TITLE]
    if existing:
        raise BoardError(
            f"a project titled {BOARD_TITLE!r} already exists under {OWNER}. init creates a "
            "second one, which leaves the title ambiguous and every command refusing. "
            "Nothing was created"
        )
    owner_id = gql('query($l:String!){organization(login:$l){id}}', l=OWNER)["organization"]["id"]
    project = gql(
        'mutation($o:ID!,$t:String!){createProjectV2(input:{ownerId:$o,title:$t})'
        "{projectV2{id number}}}",
        o=owner_id, t=BOARD_TITLE,
    )["createProjectV2"]["projectV2"]
    repo_id = gql(
        'query($o:String!,$r:String!){repository(owner:$o,name:$r){id}}', o=OWNER, r=REPO
    )["repository"]["id"]
    gql(
        'mutation($p:ID!,$r:ID!){linkProjectV2ToRepository(input:{projectId:$p,repositoryId:$r})'
        "{clientMutationId}}",
        p=project["id"], r=repo_id,
    )
    for name, options in (("Band", BANDS), ("Bundle", [EMPTY])):
        gql(
            "mutation($p:ID!){createProjectV2Field(input:{projectId:$p,"
            'dataType:SINGLE_SELECT,name:"%s",singleSelectOptions:[%s]})'
            "{projectV2Field{... on ProjectV2SingleSelectField{id}}}}"
            % (name, options_payload([], options)),
            p=project["id"],
        )

    # Status is provisioned by GitHub as Todo/In Progress/Done. Its options are
    # rewritten here rather than added to, because the provisioned three are
    # not the states this board distinguishes and no item carries one yet --
    # the wholesale overwrite is safe exactly once, before the board has items.
    status = [
        n for n in gql(
            'query($p:ID!){node(id:$p){... on ProjectV2{fields(first:50){nodes{'
            "... on ProjectV2SingleSelectField{id name}}}}}}",
            p=project["id"],
        )["node"]["fields"]["nodes"]
        if n and n.get("name") == "Status"
    ]
    if not status:
        raise BoardError("GitHub did not provision a Status field; create it before seeding")
    gql(
        "mutation($f:ID!){updateProjectV2Field(input:{fieldId:$f,singleSelectOptions:[%s]})"
        "{projectV2Field{... on ProjectV2SingleSelectField{id}}}}" % options_payload([], STATUSES),
        f=status[0]["id"],
    )
    print(f"created project #{project['number']} titled {BOARD_TITLE!r}, linked to {OWNER}/{REPO}")
    print(f"fields: Band {BANDS}, Bundle, Status {STATUSES}")
    return 0


def options_payload(existing: list[dict], new_names: list[str]) -> str:
    """Render a singleSelectOptions list that ADDS rather than resets.

    `updateProjectV2Field` overwrites the option list wholesale, and an
    existing option re-sent without its id is recreated under a new one --
    which silently clears every item field value pointing at the old id. The
    schema says so in as many words: "Include this to preserve the option's
    identity during updates, preventing item field values from being cleared."

    So an addition sends every existing option WITH its id, and only the new
    ones without. Sending names alone is how this field gets wiped, and it
    fails silently: the write succeeds, the options look right, and every
    value that referenced them is gone.
    """
    parts = [
        '{id:"%s",name:"%s",color:%s,description:"%s"}'
        % (o["id"], o["name"].replace('"', ""),
           o.get("color") or "GRAY", (o.get("description") or "").replace('"', ""))
        for o in existing
    ]
    parts += ['{name:"%s",color:GRAY,description:""}' % n.replace('"', "") for n in new_names]
    return ",".join(parts)


def ensure_options(board: "Board", field: str, values: list[str]) -> None:
    """Add every option `values` needs, in one write, preserving what is there.

    Called once before any item is labelled rather than per new value: each
    option-list write is a chance to clear the field, so the fewer the better.
    """
    spec = board.fields[field]
    missing = [v for v in dict.fromkeys(values) if v not in spec["options"]]
    if not missing:
        return
    existing = list(spec["options"].values())
    gql(
        "mutation($f:ID!){updateProjectV2Field(input:{fieldId:$f,singleSelectOptions:[%s]})"
        "{projectV2Field{... on ProjectV2SingleSelectField{id}}}}"
        % options_payload(existing, missing),
        f=spec["id"],
    )
    board.fields = board._read_fields()


def cmd_show(plan_path: Path | None) -> int:
    text = format_plan(Board().rows())
    if plan_path:
        plan_path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {plan_path}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_sync(dry_run: bool) -> int:
    board = Board()
    members = board.members()
    node_ids = open_issues()
    target = sorted(node_ids)
    to_add, to_archive = reconcile(members, target)
    # Flushed because the halt below is raised through stderr, and a caller
    # merging the two streams otherwise sees the failure printed before the
    # summary that explains it -- which reads as though the adds never ran.
    print(f"board: {len(members)}   open: {len(target)}")
    print(f"to add:     {to_add or 'none'}")
    print(f"to archive: {to_archive or 'none'}", flush=True)
    if dry_run:
        return 0
    # Resolved before the adds, because the adds are what make the ordered read
    # short. Reading afterwards can miss an archive target, skip it silently,
    # and leave settle waiting out its whole bound on an item nobody will
    # remove. A target is on the board already by construction, so this read
    # always has it.
    by_issue = {i["issue"]: i["item_id"] for i in board.ordered()} if to_archive else {}
    for number in to_add:
        board.add(node_ids[number])
    for number in to_archive:
        if number in by_issue:
            board.archive(by_issue[number])
        else:
            print(f"warning: #{number} is due for archiving and was not on the read; "
                  "it stays on the board and the next sync will remove it")
    settled = settle(lambda: [i["issue"] for i in board.ordered()], target)
    print(f"settled: ordered read carries all {len(settled)} items", flush=True)
    return 0


def cmd_apply(plan_path: Path, dry_run: bool) -> int:
    plan = parse_plan(plan_path.read_text(encoding="utf-8"))
    board = Board()
    # One ordered read, not two. The second one used to be taken separately for
    # its item ids, so the guards were computed against one read and the writes
    # addressed another -- and an item archived between them yields a raw
    # KeyError partway through a half-applied board. Keeping the read once
    # removes that divergence and halves this command's API cost.
    current = board.ordered()
    before = [Row(i["issue"], i["band"], i["bundle"], i["status"]) for i in current]
    by_issue = {i["issue"]: i for i in current}
    on_board = {r.issue for r in before}
    unknown = [r.issue for r in plan if r.issue not in on_board]
    if unknown:
        raise BoardError(
            f"plan names issues not on the board: {unknown}. Run 'sync' first."
        )
    absent = sorted(on_board - {r.issue for r in plan})
    if absent:
        raise BoardError(
            f"plan omits issues the board holds: {absent}. A plan is the whole board."
        )

    target = [r.issue for r in plan]
    moves = moves_for([r.issue for r in before], target)
    was = {r.issue: r for r in before}
    relabels = [
        (r, name)
        for r in plan
        for name in ("Band", "Bundle", "Status")
        if getattr(was[r.issue], name.lower()) != getattr(r, name.lower())
    ]
    print(f"moves: {len(moves)}   relabels: {len(relabels)}")
    if not dry_run:
        ensure_options(board, "Bundle", [r.bundle for r in plan])
    if dry_run:
        for issue, after in moves:
            print(f"  move #{issue} after {'top' if after is None else '#' + str(after)}")
        for row, name in relabels:
            print(f"  set #{row.issue} {name} -> {getattr(row, name.lower())}")
        return 0

    for issue, after in moves:
        board.move(by_issue[issue]["item_id"], None if after is None else by_issue[after]["item_id"])
    for row, name in relabels:
        board.set_field(by_issue[row.issue]["item_id"], name, getattr(row, name.lower()))

    after_rows = board.rows()
    print(json.dumps(diff_state(before, after_rows), indent=2))
    return 0




def cmd_next(count: int) -> int:
    """Print the answer, so no reader has to re-derive the rule that finds it.

    The rule is one line and every consumer would otherwise apply it by hand
    against a column of bare issue numbers -- a trial run reported that reading
    the board still cost a second query just to learn what the answer was
    about.
    """
    rows = Board().rows()
    titles = {}
    raw = gh([
        "issue", "list", "--repo", f"{OWNER}/{REPO}", "--state", "open",
        "--limit", "1000", "--json", "number,title",
    ])
    for item in json.loads(raw):
        titles[item["number"]] = item["title"]

    available = [r for r in rows if is_available(r)]
    if not available:
        print("nothing on the board is available: every item is in progress, in flight, "
              "blocked or deferred")
        return 0
    held = [r for r in rows if r.status in UNAVAILABLE][:count]
    first, rest = available[0], available[1:count + 1]
    print(f"next: #{first.issue}  {titles.get(first.issue, '(title unavailable)')}")
    print(f"      band {first.band} | bundle {first.bundle} | {first.status}")
    if rest:
        print()
        print("behind it:")
        for r in rest:
            print(f"  #{r.issue}  {titles.get(r.issue, '')[:66]}")
    if held:
        print()
        print("not in contention:")
        for r in held:
            print(f"  #{r.issue}  [{r.status}]  {titles.get(r.issue, '')[:56]}")
    return 0


def cmd_notes(limit: int) -> int:
    notes = Board().read_notes(limit)
    if not notes:
        print("no refresh notes yet")
        return 0
    for note in notes:
        print(f"--- {note['createdAt']} " + "-" * 40)
        print(note["body"].rstrip())
        print()
    return 0


def cmd_note(body_path: Path) -> int:
    created = Board().post_note(body_path.read_text(encoding="utf-8"))
    print(f"status update posted at {created}")
    return 0


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("next", "show", "sync", "apply", "note", "notes", "init"):
        p = sub.add_parser(name)
        if name == "notes":
            p.add_argument("--limit", type=int, default=3)
        if name == "next":
            p.add_argument("--count", type=int, default=5)
        if name in ("show", "apply"):
            p.add_argument("--plan", type=Path, required=(name == "apply"))
        if name == "note":
            p.add_argument("--body", type=Path, required=True)
        if name in ("sync", "apply"):
            p.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            return cmd_init()
        if args.command == "next":
            return cmd_next(args.count)
        if args.command == "show":
            return cmd_show(args.plan)
        if args.command == "sync":
            return cmd_sync(args.dry_run)
        if args.command == "apply":
            return cmd_apply(args.plan, args.dry_run)
        if args.command == "notes":
            return cmd_notes(args.limit)
        return cmd_note(args.body)
    except BoardError as exc:
        print(f"board: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

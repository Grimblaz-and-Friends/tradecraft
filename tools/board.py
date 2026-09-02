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

The read that must not lag is the one without `orderBy`. This is an observed
behaviour, not a deduction: `ProjectV2.items` declares a `defaultValue` of
`{field: POSITION, direction: ASC}` for `orderBy`, so passing it explicitly
should be identical to omitting it, and observably is not -- immediately after
an add, the ordered read returns a short list *and* a matching short
`totalCount`, while the same query with `orderBy` omitted returns the full
membership. A short read is therefore undetectable from the connection's own
count, which is why the target membership always comes from `gh issue list`
and never from the board.

Usage:  python tools/board.py show   [--plan PATH]
        python tools/board.py sync   [--dry-run]
        python tools/board.py apply  --plan PATH [--dry-run]
        python tools/board.py note   --body PATH
        python tools/board.py init

  show   read the board and write the current state as a plan file
  sync   steps 1-3: reconcile membership against the open set, then settle
  apply  step 4: order and label the board from a plan file
  note   step 5: post the refresh note as a project status update
  init   create the board and its fields, once
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from winio import utf8_stdio  # noqa: E402

OWNER = "Grimblaz-and-Friends"
REPO = "tradecraft"
BOARD_TITLE = "tradecraft board"

BANDS = ["Standing", "Front", "Bundles", "Review-set", "Tail"]
STATUSES = ["Queued", "In progress", "In flight", "Blocked", "Deferred"]

# How long the ordered read is given to catch up with the board's membership,
# and how often it is asked. Exceeding the bound is a loud halt: nothing writes
# an ordering from a read that never settled.
SETTLE_TIMEOUT_S = 60.0
SETTLE_INTERVAL_S = 2.0

EMPTY = "-"


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
        seen.add(issue)
        rows.append(Row(issue, band, EMPTY if bundle == EMPTY else bundle, status))
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
        args += ["-F", f"{key}={value}"]
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


class Board:
    """The project, its fields, and the reads and writes the run order needs."""

    ITEM_FIELDS = """
      id
      content { ... on Issue { number } }
      fieldValues(first: 20) { nodes { ... on ProjectV2ItemFieldSingleSelectValue {
        name field { ... on ProjectV2FieldCommon { name } } } } }
    """

    def __init__(self) -> None:
        found = gql(
            'query($l:String!){organization(login:$l){id '
            'projectsV2(first:50){nodes{id title}}}}',
            l=OWNER,
        )["organization"]
        self.owner_id = found["id"]
        match = [p for p in found["projectsV2"]["nodes"] if p["title"] == BOARD_TITLE]
        if not match:
            raise BoardError(
                f"no project titled {BOARD_TITLE!r} under {OWNER}. Run: python tools/board.py init"
            )
        self.project_id = match[0]["id"]
        self.fields = self._read_fields()

    def _read_fields(self) -> dict[str, dict]:
        nodes = gql(
            'query($p:ID!){node(id:$p){... on ProjectV2{fields(first:50){nodes{'
            '... on ProjectV2SingleSelectField{id name options{id name}}}}}}}',
            p=self.project_id,
        )["node"]["fields"]["nodes"]
        return {
            n["name"]: {"id": n["id"], "options": {o["name"]: o["id"] for o in n["options"]}}
            for n in nodes
            if n and n.get("name")
        }

    # The items connection refuses more than 100 per page, and this board passed
    # 80 the day it was seeded, so paging is load-bearing rather than defensive.
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
        """Membership, from the read WITHOUT orderBy -- the one that does not lag."""
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
            p=self.project_id, i=item_id, f=spec["id"], v=option,
        )

    def post_note(self, body: str) -> str:
        return gql(
            'mutation($p:ID!,$b:String!){createProjectV2StatusUpdate('
            "input:{projectId:$p,body:$b}){statusUpdate{createdAt}}}",
            p=self.project_id, b=body,
        )["createProjectV2StatusUpdate"]["statusUpdate"]["createdAt"]


def cmd_init() -> int:
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
        '{id:"%s",name:"%s",color:GRAY,description:""}'
        % (o["id"], o["name"].replace('"', ""))
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
    existing = [{"id": oid, "name": name} for name, oid in spec["options"].items()]
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
    print(f"board: {len(members)}   open: {len(target)}")
    print(f"to add:     {to_add or 'none'}")
    print(f"to archive: {to_archive or 'none'}")
    if dry_run:
        return 0
    for number in to_add:
        board.add(node_ids[number])
    if to_archive:
        by_issue = {i["issue"]: i["item_id"] for i in board.ordered()}
        for number in to_archive:
            if number in by_issue:
                board.archive(by_issue[number])
    settled = settle(lambda: [i["issue"] for i in board.ordered()], target)
    print(f"settled: ordered read carries all {len(settled)} items")
    return 0


def cmd_apply(plan_path: Path, dry_run: bool) -> int:
    plan = parse_plan(plan_path.read_text(encoding="utf-8"))
    board = Board()
    before = board.rows()
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
    by_issue = {i["issue"]: i for i in board.ordered()}
    current = {r.issue: r for r in before}
    relabels = [
        (r, name)
        for r in plan
        for name in ("Band", "Bundle", "Status")
        if getattr(current[r.issue], name.lower()) != getattr(r, name.lower())
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




def cmd_note(body_path: Path) -> int:
    created = Board().post_note(body_path.read_text(encoding="utf-8"))
    print(f"status update posted at {created}")
    return 0


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("show", "sync", "apply", "note", "init"):
        p = sub.add_parser(name)
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
        if args.command == "show":
            return cmd_show(args.plan)
        if args.command == "sync":
            return cmd_sync(args.dry_run)
        if args.command == "apply":
            return cmd_apply(args.plan, args.dry_run)
        return cmd_note(args.body)
    except BoardError as exc:
        print(f"board: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

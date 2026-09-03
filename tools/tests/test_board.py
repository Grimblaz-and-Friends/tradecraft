"""Tests for the board transport (issue #83).

Everything here runs offline. The four functions under test are the ones that
decide what happens rather than the ones that talk to GitHub, and separating
them that way is what makes the run order provable at all.

Two of them are guard-shaped and are probed in both polarities. `settle` must
halt on a read that never catches up and must stay quiet on one that does --
the second is the case that matters, because the ordered read lags its own
writes as a matter of course, and a settle that treated the ordinary lag as a
failure would halt the board after every filing. `parse_plan` must reject a
malformed plan and accept a well-formed one, because a plan that lost a row to
a typo would silently drop that issue off the board.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import board as q  # noqa: E402

NL = chr(10)
TAB = chr(9)


def plan_text(*rows: str) -> str:
    return NL.join(rows) + NL


def line(issue: int, band: str = "Front", bundle: str = "-", status: str = "Queued") -> str:
    return TAB.join([str(issue), band, bundle, status])


# ------------------------------------------------------------------ the plan


def test_parse_plan_accepts_a_well_formed_plan():
    rows = q.parse_plan(plan_text(
        "# a comment",
        "",
        line(260, "Front", "Front 1", "Queued"),
        line(83, "Standing", "-", "In progress"),
    ))
    assert [r.as_tuple() for r in rows] == [
        (260, "Front", "Front 1", "Queued"),
        (83, "Standing", "-", "In progress"),
    ]


def test_parse_plan_round_trips_through_format_plan():
    rows = q.parse_plan(plan_text(line(1), line(2, "Tail"), line(3, "Bundles", "PR G")))
    assert q.parse_plan(q.format_plan(rows)) == rows


@pytest.mark.parametrize(
    "bad, because",
    [
        (line(1) + TAB + "extra", "wrong field count"),
        (TAB.join(["12a", "Front", "-", "Queued"]), "issue is not a bare number"),
        (TAB.join(["1", "Nowhere", "-", "Queued"]), "unknown band"),
        (TAB.join(["1", "Front", "-", "Shipped"]), "unknown status"),
        (plan_text(line(7), line(7)), "the same issue twice"),
        ("# only comments" + NL, "empty plan"),
    ],
)
def test_parse_plan_rejects_a_malformed_plan(bad, because):
    with pytest.raises(q.BoardError):
        q.parse_plan(bad if bad.endswith(NL) else bad + NL)


# ----------------------------------------------------------------- reconcile


def test_reconcile_reports_both_directions_and_never_raises():
    to_add, to_archive = q.reconcile(board=[1, 2, 3], open_issues=[2, 3, 4])
    assert (to_add, to_archive) == ([4], [1])


def test_reconcile_is_quiet_when_the_board_already_matches():
    assert q.reconcile([3, 1, 2], [1, 2, 3]) == ([], [])


# -------------------------------------------------------------------- settle


def test_settle_returns_once_the_ordered_read_catches_up():
    """The lawful polarity, and the one that matters: a lag is not a failure.

    The first read is short by exactly the item a preceding add put there,
    which is the ordinary state of every refresh following a filing.
    """
    reads = iter([[1, 2], [1, 2], [1, 2, 3]])
    slept = []
    got = q.settle(lambda: next(reads), [1, 2, 3], timeout_s=60,
                   interval_s=2, sleep=slept.append, clock=lambda: 0.0)
    assert got == [1, 2, 3]
    assert slept == [2, 2], "polled rather than failing on the short reads"


def test_settle_halts_when_the_read_never_catches_up():
    ticks = iter([0.0, 5.0, 99.0])
    with pytest.raises(q.BoardError) as caught:
        q.settle(lambda: [1, 2], [1, 2, 3], timeout_s=10, interval_s=1,
                 sleep=lambda _: None, clock=lambda: next(ticks))
    message = str(caught.value)
    assert "3" in message, "names what never appeared"
    assert "No ordering was written" in message


def test_settle_does_not_poll_when_the_first_read_is_already_settled():
    slept = []
    assert q.settle(lambda: [2, 1], [1, 2], sleep=slept.append, clock=lambda: 0.0) == [2, 1]
    assert slept == []


# --------------------------------------------------------------------- moves


def test_moves_for_is_empty_when_the_order_already_holds():
    assert q.moves_for([1, 2, 3], [1, 2, 3]) == []


def test_moves_for_moves_only_what_is_out_of_place():
    """The whole cost argument for adjusting rather than rebuilding.

    One item promoted to the top is one move, not a rewrite of the board.
    """
    assert q.moves_for([1, 2, 3, 4], [4, 1, 2, 3]) == [(4, None)]


def test_moves_for_reproduces_the_target_when_replayed():
    current = [5, 3, 1, 4, 2]
    target = [1, 2, 3, 4, 5]
    order = list(current)
    for issue, after in q.moves_for(current, target):
        order.remove(issue)
        order.insert(0 if after is None else order.index(after) + 1, issue)
    assert order == target


def test_moves_for_ignores_items_absent_from_the_target():
    """An item mid-archive is not an anchor, and must not become one."""
    assert [issue for issue, _ in q.moves_for([9, 1, 2], [1, 2])] == []


# ---------------------------------------------------------------------- diff


def rows(*specs) -> list:
    return [q.Row(*s) for s in specs]


def test_diff_state_reports_an_unchanged_run_as_unchanged():
    before = rows((1, "Front", "-", "Queued"), (2, "Tail", "-", "Queued"))
    assert q.diff_state(before, list(before))["unchanged"] is True


def test_diff_state_reports_membership_movement_and_relabelling():
    before = rows((1, "Front", "-", "Queued"), (2, "Tail", "-", "Queued"))
    after = rows((2, "Front", "PR G", "In flight"), (3, "Tail", "-", "Queued"))
    diff = q.diff_state(before, after)
    assert diff["added"] == [3]
    assert diff["dropped"] == [1]
    assert diff["moved"] == [{"issue": 2, "from": 2, "to": 1}]
    assert diff["relabelled"] == [{
        "issue": 2,
        "band": {"from": "Tail", "to": "Front"},
        "bundle": {"from": "-", "to": "PR G"},
        "status": {"from": "Queued", "to": "In flight"},
    }]
    assert diff["unchanged"] is False


def test_diff_state_sees_a_move_that_changed_no_field():
    """A note authored from membership alone could not say this happened."""
    before = rows((1, "Front", "-", "Queued"), (2, "Front", "-", "Queued"))
    after = rows((2, "Front", "-", "Queued"), (1, "Front", "-", "Queued"))
    diff = q.diff_state(before, after)
    assert diff["unchanged"] is False
    assert {m["issue"] for m in diff["moved"]} == {1, 2}
    assert diff["added"] == [] and diff["dropped"] == []


# ------------------------------------------------------------ stated defaults


def test_the_seeded_vocabularies_are_what_the_plan_validates_against():
    """The parser and the board must not drift apart on what a value may be.

    Statuses are paired off-by-one against bands so that `Standing` never
    draws `Queued`, which the trap rule below refuses -- the pairing here is
    arbitrary and only has to exercise every value once.
    """
    statuses = q.STATUSES[1:] + q.STATUSES[:1]
    rows_ = q.parse_plan(plan_text(*(
        line(i, band, "-", status)
        for i, (band, status) in enumerate(zip(q.BANDS, statuses), start=1)
    )))
    assert [r.band for r in rows_] == q.BANDS
    assert sorted({r.status for r in rows_}) == sorted(set(q.STATUSES))


# ----------------------------------------------------- single-select options


def test_options_payload_sends_existing_options_with_their_ids():
    """The behaviour that clears a whole field when it is got wrong.

    `updateProjectV2Field` overwrites the option list wholesale, and an option
    re-sent without its id is recreated under a new one -- clearing every item
    value that pointed at the old id, with a successful-looking write and no
    error. This seeded board lost every Bundle value that way once.
    """
    payload = q.options_payload([{"id": "opt_1", "name": "Figures"}], ["Records"])
    assert 'id:"opt_1"' in payload, "the existing option keeps its identity"
    assert payload.count("id:") == 1, "the new option is sent without one"
    assert payload.index('name:"Figures"') < payload.index('name:"Records"')


def test_options_payload_creating_a_field_sends_no_ids():
    payload = q.options_payload([], q.BANDS)
    assert "id:" not in payload
    assert all(f'name:"{band}"' in payload for band in q.BANDS)


# ------------------------------------------------------------ project lookup


def test_pick_project_finds_the_one_with_the_title():
    nodes = [{"id": "a", "title": "other"}, {"id": "b", "title": "tradecraft board"}]
    assert q.pick_project(nodes, "tradecraft board") == "b"


def test_pick_project_refuses_a_duplicate_title_rather_than_guessing():
    """Guessing would write an ordering into a board the caller did not mean."""
    nodes = [{"id": "a", "title": "dup"}, {"id": "b", "title": "dup"}]
    with pytest.raises(q.BoardError) as caught:
        q.pick_project(nodes, "dup")
    assert "2 projects" in str(caught.value)


def test_pick_project_names_what_is_there_when_nothing_matches():
    with pytest.raises(q.BoardError) as caught:
        q.pick_project([{"id": "a", "title": "other"}], "missing")
    assert "other" in str(caught.value), "says what titles exist, so the caller can point at one"


# ------------------------------------------------- the Standing/Queued trap


def test_parse_plan_refuses_a_standing_item_that_is_available():
    """The trap a trial run walked into.

    The reading rule is positional over Status and cannot see Band, so a
    Queued item in the Standing band silently becomes the board's answer. A
    consumer placed two and the board confidently offered work nobody ranked.
    """
    with pytest.raises(q.BoardError) as caught:
        q.parse_plan(plan_text(line(220, "Standing", "-", "Queued")))
    message = str(caught.value)
    assert "Standing" in message and "220" in message
    assert "In progress" in message, "says what statuses would resolve it"


@pytest.mark.parametrize("status", sorted(q.UNAVAILABLE))
def test_parse_plan_accepts_a_standing_item_that_is_out_of_contention(status):
    """The lawful polarity: Standing is fine for anything genuinely not available."""
    rows = q.parse_plan(plan_text(line(83, "Standing", "-", status)))
    assert rows[0].status == status


def test_unavailable_is_every_status_but_queued():
    """The reading rule and this set are one thing; a second copy is how they drift."""
    assert q.UNAVAILABLE == frozenset(q.STATUSES) - {"Queued"}
    assert "Queued" not in q.UNAVAILABLE


# ------------------------------------------------------ the bundle charset


@pytest.mark.parametrize("bundle", ["PR G - decision-log", "Post-#260 redraw",
                                    "Front 3 - PR J seat/dispatch hygiene", "-", "Figures"])
def test_parse_plan_accepts_the_bundle_names_the_board_actually_carries(bundle):
    """The lawful polarity, drawn from the live board rather than invented."""
    assert q.parse_plan(plan_text(line(1, "Front", bundle)))[0].bundle == bundle


@pytest.mark.parametrize("bundle", ['PR "G"', "A" + chr(92), "X},{name:" + chr(34) + "INJECTED", ""])
def test_parse_plan_refuses_a_bundle_that_would_not_survive_the_wire(bundle):
    """options_payload escapes by stripping quotes, so these reach GraphQL malformed.

    A quote creates a differently-named option that set_field then cannot find
    -- after every position move has landed. Refused at parse time, which is
    also what makes --dry-run catch it.
    """
    with pytest.raises(q.BoardError) as caught:
        q.parse_plan(plan_text(line(1, "Front", bundle)))
    assert "bundle" in str(caught.value)


# ------------------------------------------------- settle's own defaults


def test_settle_uses_its_module_defaults_when_the_caller_names_none():
    """The constants are the contract; every other test passes them explicitly.

    A zeroed SETTLE_TIMEOUT_S turns every ordinary lag into a halt, which is
    the failure the whole reconcile/settle split exists to prevent, and it
    would not have reddened anything.
    """
    assert q.SETTLE_TIMEOUT_S >= 30, "a short bound makes an ordinary lag a halt"
    assert q.SETTLE_INTERVAL_S > 0, "a zero interval busy-spins GitHub"
    slept = []
    reads = iter([[1], [1, 2]])
    got = q.settle(lambda: next(reads), [1, 2], sleep=slept.append, clock=lambda: 0.0)
    assert got == [1, 2]
    assert slept == [q.SETTLE_INTERVAL_S], "polled at the module's own interval"


def test_settle_names_missing_and_extra_the_right_way_round():
    """The halt message is the operator's only diagnostic, and one has read it.

    Swapping the two used to leave the suite green while telling the operator
    the read carries something it should not, when in fact it lacks something
    it should.
    """
    ticks = iter([0.0, 99.0])
    with pytest.raises(q.BoardError) as caught:
        q.settle(lambda: [1, 9], [1, 2], timeout_s=10, interval_s=1,
                 sleep=lambda _: None, clock=lambda: next(ticks))
    message = str(caught.value)
    missing_at = message.index("missing from it")
    extra_at = message.index("unexpected in it")
    assert missing_at < message.index("[2]") < extra_at, \
        "2 is absent from the read, so it is the missing one"
    assert message.index("[9]") > extra_at, "9 is present unexpectedly, so it is the extra one"


# ------------------------------------------- the plan header is guidance


def test_format_plan_header_advertises_the_vocabularies_the_parser_enforces():
    """The header is the only guidance the human editing a plan file gets.

    parse_plan discards comment lines, so the round-trip test cannot see it and
    it advertised whatever it liked.
    """
    header = [ln for ln in q.format_plan([q.Row(1, "Front", "-", "Queued")]).splitlines()
              if ln.startswith("#")]
    blob = NL.join(header)
    for band in q.BANDS:
        assert band in blob, "header omits a band the parser accepts: " + band
    for status in q.STATUSES:
        assert status in blob, "header omits a status the parser accepts: " + status
    assert q.EMPTY in blob


# --------------------------------------------------- the wire, faked once


class FakeWire:
    """Records queries and returns canned payloads, so the wire paths get a test.

    Nineteen functions in this module talk to GitHub and nothing outside a
    session running the cell ever calls them, so before this they were covered
    by nothing at all. One fake reaches read_notes, ensure_options and _pages.
    """

    def __init__(self, payloads):
        self.payloads, self.queries = list(payloads), []

    def __call__(self, query, **variables):
        self.queries.append((query, variables))
        return self.payloads.pop(0)


def board_without_network(fields=None):
    board = object.__new__(q.Board)
    board.project_id = "PVT_test"
    board.fields = fields or {}
    return board


def test_read_notes_asks_for_the_newest_and_does_not_reverse(monkeypatch):
    """statusUpdates is newest-first, so `last:N` would return the N OLDEST.

    Under the old form this command served the seed note forever from the
    second refresh on -- the failure the command was added to end.
    """
    wire = FakeWire([{"node": {"statusUpdates": {"nodes": [
        {"createdAt": "2026-09-03", "body": "newest"},
        {"createdAt": "2026-09-02", "body": "older"},
    ]}}}])
    monkeypatch.setattr(q, "gql", wire)
    notes = board_without_network().read_notes(2)
    query = wire.queries[0][0]
    assert "first:" in query and "last:" not in query, "last:N slices the oldest"
    assert "direction:DESC" in query, "the ordering is stated rather than inherited"
    assert [n["body"] for n in notes] == ["newest", "older"]


def test_ensure_options_sends_existing_options_with_their_ids_and_appearance(monkeypatch):
    """The call site, not just the renderer.

    Dropping the ids here is what wiped this board's whole Bundle column once,
    with a successful-looking write and no error -- and the renderer's own test
    could not see it, because the renderer was never the thing that decided.
    """
    wire = FakeWire([{"updateProjectV2Field": {"projectV2Field": {"id": "F"}}},
                     {"node": {"fields": {"nodes": []}}}])
    monkeypatch.setattr(q, "gql", wire)
    board = board_without_network({"Bundle": {"id": "F", "options": {
        "Figures": {"id": "opt_fig", "name": "Figures", "color": "BLUE", "description": "d"},
    }}})
    q.ensure_options(board, "Bundle", ["Figures", "Records"])
    payload = wire.queries[0][0]
    assert 'id:"opt_fig"' in payload, "the existing option keeps its identity"
    assert "color:BLUE" in payload and 'description:"d"' in payload, \
        "and keeps what the owner set in the project UI"
    assert 'name:"Records"' in payload and payload.count("id:") == 1


def test_ensure_options_writes_nothing_when_every_option_exists(monkeypatch):
    """The lawful polarity: each option-list write is a chance to clear the field."""
    wire = FakeWire([])
    monkeypatch.setattr(q, "gql", wire)
    board = board_without_network({"Bundle": {"id": "F", "options": {
        "Figures": {"id": "opt_fig", "name": "Figures", "color": "GRAY", "description": ""},
    }}})
    q.ensure_options(board, "Bundle", ["Figures", "Figures"])
    assert wire.queries == []


def test_pages_follows_the_cursor_past_the_first_page(monkeypatch):
    """The items connection caps at 100 and this board has never reached it.

    So the cursor branch has never executed anywhere, including in production.
    """
    wire = FakeWire([
        {"node": {"items": {"pageInfo": {"hasNextPage": True, "endCursor": "CUR1"},
                            "nodes": [{"content": {"number": 1}}]}}},
        {"node": {"items": {"pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [{"content": {"number": 2}}]}}},
    ])
    monkeypatch.setattr(q, "gql", wire)
    nodes = board_without_network()._pages("", "content{... on Issue{number}}")
    assert [n["content"]["number"] for n in nodes] == [1, 2]
    assert "after:null" in wire.queries[0][0]
    assert 'after:"CUR1"' in wire.queries[1][0], "the second page is asked for by cursor"




def test_init_proceeds_when_no_board_carries_that_title(monkeypatch):
    """The lawful polarity: a guard that blocks the first run fails as hard."""
    monkeypatch.setattr(q, "org_projects", lambda: [{"id": "P", "title": "something else"}])
    calls = []
    monkeypatch.setattr(q, "gql", lambda query, **kw: calls.append(query) or _init_payload(query))
    assert q.cmd_init() == 0
    assert any("createProjectV2" in c for c in calls), "it got past the guard and created"


def _init_payload(query):
    if "organization(login:$l){id}" in query:
        return {"organization": {"id": "O"}}
    if "createProjectV2" in query:
        return {"createProjectV2": {"projectV2": {"id": "P", "number": 9}}}
    if "repository(owner:$o,name:$r)" in query:
        return {"repository": {"id": "R"}}
    if "linkProjectV2ToRepository" in query:
        return {"linkProjectV2ToRepository": {"clientMutationId": None}}
    if "createProjectV2Field" in query:
        return {"createProjectV2Field": {"projectV2Field": {"id": "F"}}}
    if "fields(first:50)" in query:
        return {"node": {"fields": {"nodes": [{"id": "S", "name": "Status"}]}}}
    return {"updateProjectV2Field": {"projectV2Field": {"id": "S"}}}


# ------------------------------------------------------- the reading rule


def test_is_available_excludes_the_four_states_and_an_unset_one():
    """The rule the whole board turns on, including the case sync creates.

    Between a sync and the apply that ranks them, every newly added item
    carries no status at all. Counting that as available is the same defect the
    Standing refusal exists to stop, reached by a route no plan passes through.
    """
    assert q.is_available(q.Row(1, "Front", "-", "Queued")) is True
    for status in sorted(q.UNAVAILABLE):
        assert q.is_available(q.Row(1, "Front", "-", status)) is False, status
    assert q.is_available(q.Row(1, "Front", "-", q.EMPTY)) is False,         "an item sync just added is unranked, not available"


# ------------------------------------------- what cycle one's look found


@pytest.fixture(autouse=True)
def fence_the_wire(monkeypatch):
    """Every test in this module starts fenced off the network. Nobody opts in.

    This is the third form of this fence and the first that does not depend on
    being remembered. The first pinned `gql` and left `gh` open -- `gql` is a
    convenience over `gh`, and `gh` is the only thing that transmits. The
    second pinned `gql`, `gh` and `subprocess.run`, and was a function three of
    sixty-five tests called; the one test that drives `createProjectV2` was not
    among them, so a mutation routed onto `gh` still transmitted, and a review
    proved it by watching a real request go out. Each fix closed the instance
    in front of it and left the generalisation one step out.

    Autouse closes it: a test needing a stub overrides the one route it stubs
    and stays fenced on the others, so the failure mode is a test that cannot
    reach the wire rather than one that quietly does. Scoped to this module
    rather than a conftest because the other suites here run real subprocesses
    on purpose.
    """
    def refuse(kind):
        def _refuse(*args, **kwargs):
            raise AssertionError(
                f"this test reached the network via {kind}: {str(args)[:90]}"
            )
        return _refuse

    monkeypatch.setattr(q, "gql", refuse("gql"))
    monkeypatch.setattr(q, "gh", refuse("gh"))
    monkeypatch.setattr(q.subprocess, "run", refuse("subprocess"))


def test_init_refuses_when_a_board_with_that_title_already_exists(monkeypatch):
    """init used to create unconditionally, manufacturing the one condition
    pick_project refuses -- and pick_project's own message is what sent callers there."""
    monkeypatch.setattr(q, "org_projects", lambda: [{"id": "P", "title": q.BOARD_TITLE}])
    with pytest.raises(q.BoardError) as caught:
        q.cmd_init()
    assert "already exists" in str(caught.value)
    assert "Nothing was created" in str(caught.value)


def test_option_color_falls_back_rather_than_emitting_a_bad_enum():
    """The colour is interpolated as a bare enum, so a bad one is a syntax error.

    It comes off the live board, where a person set it in the project UI.
    """
    assert q.option_color({"color": "BLUE"}) == "BLUE"
    assert q.option_color({"color": "blue"}) == "BLUE"
    assert q.option_color({"color": "chartreuse"}) == "GRAY"
    assert q.option_color({}) == "GRAY"
    assert q.option_color({"color": None}) == "GRAY"


@pytest.mark.parametrize("raw, safe", [
    ('a"b', "ab"),
    ("a" + chr(92) + "b", "ab"),
    ("a" + chr(10) + "b", "ab"),
    (None, ""),
    ("plain text", "plain text"),
])
def test_option_text_strips_what_would_malform_the_query(raw, safe):
    """Descriptions never pass through parse_plan, so the bundle charset never sees them."""
    assert q.option_text(raw) == safe


def test_options_payload_never_emits_an_unquoted_stray(monkeypatch):
    """The whole payload, over a hostile existing option, stays well formed."""
    payload = q.options_payload(
        [{"id": "o1", "name": 'PR "G"', "color": "not-a-colour",
          "description": 'x"y' + chr(92) + chr(10)}],
        ["Records"],
    )
    # A property, not a count: every quote opens or closes a value, so they
    # pair, and nothing that would end a string early survives.
    assert payload.count('"') % 2 == 0, payload
    # The EXISTING option's colour, not the new one's -- the new option always
    # emits GRAY, so asserting on the payload as a whole passes while a bad
    # colour rides through on the option that came off the live board.
    existing_chunk = payload.split("},{")[0]
    assert "color:GRAY" in existing_chunk, existing_chunk
    assert "not-a-colour" not in payload
    assert chr(92) not in payload and chr(10) not in payload
    for field in ("name", "description"):
        for chunk in payload.split(field + ':"')[1:]:
            assert chunk.split('"')[0].isprintable(), payload


def test_org_projects_follows_the_cursor_past_the_first_page(monkeypatch):
    """The second paging loop the fix batch added, and did not test.

    It runs on every command, via Board.__init__, and a truncated scan defeats
    init's duplicate guard silently -- which re-manufactures the duplicate that
    guard exists to prevent.
    """
    wire = FakeWire([
        {"organization": {"projectsV2": {"pageInfo": {"hasNextPage": True, "endCursor": "C1"},
                                         "nodes": [{"id": "a", "title": "one"}]}}},
        {"organization": {"projectsV2": {"pageInfo": {"hasNextPage": False, "endCursor": None},
                                         "nodes": [{"id": "b", "title": "two"}]}}},
    ])
    monkeypatch.setattr(q, "gql", wire)
    assert [n["title"] for n in q.org_projects()] == ["one", "two"]
    assert "after:null" in wire.queries[0][0]
    assert 'after:"C1"' in wire.queries[1][0]


def test_next_says_unranked_rather_than_in_flight_when_nothing_is_placed(capsys, monkeypatch):
    """The state init+sync leaves, which is the first thing an adopter reaches.

    The old message told the operator every item was being worked, when in fact
    none had been placed -- and the remedy it implied was not the right one.
    """
    rows = [q.Row(n, q.EMPTY, q.EMPTY, q.EMPTY) for n in (1, 2, 3)]
    monkeypatch.setattr(q.Board, "__init__", lambda self: None)
    monkeypatch.setattr(q.Board, "rows", lambda self: rows)
    monkeypatch.setattr(q, "gh", lambda args: "[]")
    assert q.cmd_next(5) == 0
    out = capsys.readouterr().out
    assert "unranked" in out and "3 of 3" in out
    assert "in progress" not in out.split("unranked")[0]


def test_next_still_reports_a_genuinely_saturated_board(capsys, monkeypatch):
    """The lawful polarity: when every item really is being worked, say so."""
    rows = [q.Row(1, "Front", "-", "In progress"), q.Row(2, "Front", "-", "Blocked")]
    monkeypatch.setattr(q.Board, "__init__", lambda self: None)
    monkeypatch.setattr(q.Board, "rows", lambda self: rows)
    monkeypatch.setattr(q, "gh", lambda args: "[]")
    assert q.cmd_next(5) == 0
    out = capsys.readouterr().out
    assert "in progress, in flight, blocked or deferred" in out
    assert "unranked" not in out


def test_every_wire_route_is_fenced_without_the_test_asking():
    """The fence's own probe, and it opts into nothing.

    A fence that stops `gql` and lets `gh` through looks identical from a green
    suite, and every `gql` call reaches GitHub through `gh`. Each route is
    provoked separately, because pinning one and assuming the others is exactly
    the mistake this replaced twice.
    """
    with pytest.raises(AssertionError, match="via gql"):
        q.gql("query{x}")
    with pytest.raises(AssertionError, match="via gh"):
        q.gh(["api", "graphql"])
    with pytest.raises(AssertionError, match="via subprocess"):
        q.subprocess.run(["gh", "api"])


def test_open_issues_cannot_transmit_under_the_fence():
    """A gh-routed call site, not a gql-routed one -- the route the first fence left open."""
    with pytest.raises(AssertionError, match="via gh"):
        q.open_issues()


def test_next_reports_an_empty_board_as_empty(capsys, monkeypatch):
    """Neither saturated nor unranked: the state init leaves before the first sync."""
    monkeypatch.setattr(q.Board, "__init__", lambda self: None)
    monkeypatch.setattr(q.Board, "rows", lambda self: [])
    monkeypatch.setattr(q, "gh", lambda args: "[]")
    assert q.cmd_next(5) == 0
    out = capsys.readouterr().out
    assert "no items at all" in out
    assert "in progress" not in out and "unranked" not in out


def test_options_payload_sanitises_the_name_as_well_as_the_description():
    """Both come off the live board; only one used to be guarded."""
    payload = q.options_payload(
        [{"id": "o1", "name": "PR" + chr(92) + "G" + chr(10), "color": "BLUE",
          "description": "d"}],
        ["New" + chr(92) + "Name"],
    )
    assert chr(92) not in payload and chr(10) not in payload
    assert payload.count('"') % 2 == 0, payload


def test_options_payload_guards_every_interpolated_value_including_the_id():
    """All four, not three. The id is GitHub-generated today and that is not a guarantee."""
    payload = q.options_payload(
        [{"id": "a" + chr(92), "name": "b" + chr(92), "color": "BLUE",
          "description": "c" + chr(92)}],
        [],
    )
    assert chr(92) not in payload, payload
    assert payload.count('"') % 2 == 0, payload


def test_sync_warns_and_does_not_claim_the_run_will_halt(capsys, monkeypatch):
    """cmd_sync had no test at all, and its warning had been wrong twice.

    An archive target missing from the pre-add read is skipped; a read still
    missing it then matches the target and settles green, so the run returns 0
    with a closed issue still on the board. The warning must say that, and must
    not promise a halt that does not come.
    """
    # The class is patched before it is replaced by the factory, or the factory
    # is what setattr walks into.
    monkeypatch.setattr(q.Board, "members", lambda self: [1, 2, 3])
    monkeypatch.setattr(q.Board, "ordered", lambda self: [
        {"item_id": "x1", "issue": 1, "band": "-", "bundle": "-", "status": "-"},
        {"item_id": "x2", "issue": 2, "band": "-", "bundle": "-", "status": "-"},
    ])
    monkeypatch.setattr(q.Board, "add", lambda self, cid: "new")
    monkeypatch.setattr(q.Board, "archive", lambda self, iid: None)
    board = board_without_network()
    monkeypatch.setattr(q, "Board", lambda: board)
    monkeypatch.setattr(q, "open_issues", lambda: {1: "I1", 2: "I2"})

    assert q.cmd_sync(dry_run=False) == 0
    out = capsys.readouterr().out
    assert "#3" in out and "NOT removed" in out
    assert "will halt" not in out, "the run returns 0; promising a halt made it contradict itself"
    assert "Run sync again" in out
    # And it must not claim the opposite either. The warning's whole job is to
    # say the run's own result is not evidence about this item, so pinning only
    # the absence of a halt-claim leaves it free to promise success instead.
    assert "does not tell you whether it worked" in out

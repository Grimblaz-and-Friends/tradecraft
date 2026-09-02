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
        (TAB.join(["#1", "Front", "-", "Queued"]), "issue is not a bare number"),
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
    """The parser and the board must not drift apart on what a value may be."""
    rows_ = q.parse_plan(plan_text(*(
        line(i, band, "-", status)
        for i, (band, status) in enumerate(zip(q.BANDS, q.STATUSES), start=1)
    )))
    assert [r.band for r in rows_] == q.BANDS
    assert [r.status for r in rows_] == q.STATUSES


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

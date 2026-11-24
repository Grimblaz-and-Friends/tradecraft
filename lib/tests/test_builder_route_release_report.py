"""The release report's builder_route on a launched, a hand-started and a mechanical-lane builder ready at head.

Guards what the report adds for the default's first runs: what a ready record left owed, the holder's quiet and
later launches, the reviewers' declines, each stretch's length and the vendor and model, read from the launch's
or the hand record's own fields, and row 2's checks on the mechanical lane.
Design: lib/DESIGN.md#the-builder-route
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import launch_tree  # noqa: E402
import route_fixture  # noqa: E402
import route_report  # noqa: E402
import work  # noqa: E402

ROW_ORDER = ["1.1", "1.2", "1.3", "2.1", "2.2", "2.3", "3.1", "3.2", "3.3", "4.1", "4.2", "5.2", "5.3", "5.4", "5.5",
             "6.2", "6.3", "7.1", "7.2", "7.3"]
# What the route fixture's scenarios set on the entrance in place of GitHub and the holder's gates.
STOOD_IN = ("GitHubREST", "_read_policy_state", "_cold_reading_decision", "_evaluate_reach", "_emit_report",
            "_current_marker", "decide", "_release_gate_status", "_merge_readiness")
NO_SESSION = "names no holder session"


@pytest.fixture
def restored(monkeypatch):
    """Each stand-in the fixture sets on the entrance is put back after the test."""
    for name in STOOD_IN:
        monkeypatch.setattr(work, name, getattr(work, name))
    monkeypatch.setattr(launch_tree, "holds", launch_tree.holds)


def mechanical_ready(fixture: route_fixture.Fixture) -> object:
    """A hand-started builder on the mechanical lane, ready at the head with its floor run and no use owed."""
    source, head = fixture.source()
    fixture.pull_request(head, route_fixture.CLEAR)
    builder = fixture.hand_stretch(source, owed=True)["dispatch_id"]
    floor = fixture.post(f"<!-- tradecraft:floor:v1 head={head} status=pass -->\n\n```\n{route_fixture.FLOOR}\n"
                         "```\n\n1 passed\n")
    fixture.launch_tree.complete_hand_record(fixture.store, builder, completed_by="the builder's readiness record",
                                             now=route_fixture.START + timedelta(minutes=20))
    fixture.readiness(builder, head, started_by="hand", checks=[
        {"stage": "floor", "criterion": None, "row": None, "dispatch": None, "head": head, "report": floor,
         "relaunch_of": None}])
    return fixture.state()


def release_report(tmp_path, kind: str) -> dict:
    fixture = route_fixture.Fixture(tmp_path, mechanical=kind == "mechanical")
    try:
        state = {"launched": route_fixture.ready_launched,
                 "hand": lambda made: route_fixture.ready_at_head(made, route_fixture.CLEAR, owed=True),
                 "mechanical": mechanical_ready}[kind](fixture)
        return work._builder_route_report(state, route_fixture.RULES)
    finally:
        fixture.stop()


def readings(report: dict) -> dict:
    return {entry["check"]: entry for entry in report["row_checks"]}


@pytest.mark.parametrize("kind", ["launched", "hand", "mechanical"])
def test_the_release_report_carries_the_builder_routes_new_fields_and_row_checks_in_row_order(tmp_path, restored,
                                                                                            kind):
    report = release_report(tmp_path, kind)
    assert set(report["owed_at_ready"]) == {"first", "last"}
    for name in ("holder_quiet", "holder_after_ready"):
        assert isinstance(report[name], dict) and report[name]
    assert isinstance(report["reviewer_declines"], list)
    assert report["readiness"]["vendor_model"]["vendor"] == "claude"
    assert report["readiness"]["vendor_model"]["model"] == "fixture"
    [stretch] = report["stretch_seconds"]
    assert stretch["dispatch"] == report["readiness"]["dispatch"]
    assert [entry["check"] for entry in report["row_checks"]] == ROW_ORDER
    # A transcript the fixture never wrote reads unknown for its reason, never for a session the record lacks.
    assert report["holder_quiet"]["status"] == "unknown"
    assert NO_SESSION not in report["holder_quiet"]["reason"]
    assert "transcript" in report["holder_quiet"]["reason"]
    assert NO_SESSION not in report["holder_after_ready"]["transcript"]["reason"]
    assert report["holder_after_ready"]["bundles"] == []
    for check in ("1.3", "4.1"):
        assert readings(report)[check]["reading"] == "unknown"
        assert "transcript" in readings(report)[check]["reason"]


def test_a_launched_builders_stretch_length_is_measured_beside_its_limit(tmp_path, restored):
    report = release_report(tmp_path, "launched")
    [stretch] = report["stretch_seconds"]
    # The fixture's stretch launched five minutes in and completed at twenty.
    assert stretch["elapsed_seconds"] == 900.0 and "limit_seconds" in stretch and "status" not in stretch
    checks = readings(report)
    assert checks["2.1"]["reading"] == "holds" and checks["2.1"]["asserts"] == route_report.ROW_CHECKS["2.1"]
    assert checks["2.2"]["reading"] == "holds"
    assert (checks["5.5"]["reading"], checks["6.2"]["reading"]) == ("not-applicable", "not-applicable")


def test_a_hand_started_builders_stretch_reads_not_applicable_and_its_owed_checks_come_from_the_hand_record(
        tmp_path, restored):
    report = release_report(tmp_path, "hand")
    [stretch] = report["stretch_seconds"]
    assert stretch["status"] == "not-applicable"
    assert stretch["reason"] == "a builder started by hand has no launch whose length the entrance measured"
    # The hand record's handoff block owes the cold reader and the criterion with a fresh reader; the record named
    # only use, so 1.1 fails on what it left.
    owed = report["owed_at_ready"]["last"]
    assert isinstance(owed, list)
    assert {(entry["stage"], entry["criterion"]) for entry in owed} >= {("cold-reader", None),
                                                                        ("acceptance-criterion", "C2")}
    assert all(entry["reason"] == "owed-unnamed" for entry in owed)
    assert report["owed_at_ready"]["first"] == owed
    assert readings(report)["1.1"]["reading"] == "fails"
    assert (readings(report)["5.5"]["reading"], readings(report)["6.2"]["reading"]) == ("holds", "holds")


def test_the_mechanical_lanes_row_two_reads_the_affirmed_brief_and_owes_no_use(tmp_path, restored):
    report = release_report(tmp_path, "mechanical")
    assert report["lane"] == route_report.MECHANICAL_LANE
    checks = readings(report)
    assert checks["2.1"]["reading"] == "holds" and checks["2.1"]["field"] == "handoff_plan.reading"
    assert "affirmed brief" in checks["2.1"]["asserts"] and "settled plan" not in checks["2.1"]["asserts"]
    assert (checks["2.2"]["reading"], checks["2.2"]["reason"]) == ("not-applicable", route_report.MECHANICAL_NO_USE)
    assert checks["2.3"]["reading"] == "holds" and checks["2.3"]["asserts"] == route_report.ROW_CHECKS["2.3"]
    # Every row is owed its own reader at the record's head, and this record has none.
    unread = {entry["row"] for entry in report["owed_at_ready"]["last"] if entry["reason"] == "row-unread"}
    assert unread == set(range(1, 8)) and checks["1.1"]["reading"] == "fails"


def test_what_a_ready_record_left_owed_names_each_owed_check_once(tmp_path, restored):
    owed = release_report(tmp_path, "hand")["owed_at_ready"]["last"]
    named = [(entry["stage"], entry["criterion"], entry["row"]) for entry in owed]
    assert len(named) == len(set(named)), named


def test_a_ready_record_whose_handoff_names_no_owed_checks_reads_them_unread_not_clear(tmp_path, restored):
    fixture = route_fixture.Fixture(tmp_path)
    try:
        # The hand record's block leaves out its owed checks, as one written before they were recorded would.
        state = route_fixture.ready_at_head(fixture, route_fixture.CLEAR)
        fixture.decision(state)
        made = fixture.reports[0]
        # Whatever the chain still owes, the checks the handoff owed are said unread, never counted clear.
        assert made["stage"] == "final-pass" and made["reason"] in ("ready-reported", "owed-at-ready")
        owed = __import__("json").loads(made["detail"])["owed_list"]
        assert owed["status"] == "unknown" and "names no owed checks" in owed["reason"]
        line = work._owed_line(work.Decision(made["stage"], False, None, made["reason"], made["detail"]))
        assert "the handoff's owed checks could not be read" in line
        report = work._builder_route_report(state, route_fixture.RULES)
        assert report["owed_at_ready"]["last"]["status"] == "unknown"
        [one_one] = [entry for entry in report["row_checks"] if entry["check"] == "1.1"]
        assert one_one["reading"] == "unknown"
    finally:
        fixture.stop()

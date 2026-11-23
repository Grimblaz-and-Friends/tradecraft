"""The release report's builder-route payload: its row-check readings and the placement of its parts."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import route_report


PRICED = {"status": "priced", "usd": 1.0}
REFUSAL = {"command": "gh pr merge", "reason": "not allowed", "then": "returned it"}


def inputs(**changes):
    value = {
        "route": {"name": "builder", "reason": "default", "marker": None, "overruled": None},
        "readiness": {
            "record": 11, "status": "ready", "launched_by_builder": True, "reconciled": True,
            "relaunches": {"pairs": [], "unpaired": []}, "stop": None,
            "vendor_model": {"source": "observed", "log": "readable"},
            "builder": {"vendor": "claude", "model": "opus", "started_by": "launch", "usage_log": None},
            "declines": [{"report": 5, "finding": "F1", "disposition": "declined", "reason": "out of scope"},
                         {"report": 5, "finding": "F2", "disposition": "declined", "reason": "out of scope"},
                         {"report": 6, "finding": "F1", "disposition": "declined", "reason": "wrong premise"}],
            "decisions": [{"text": "which name", "recommendation": "short", "row": 2},
                          {"text": "a spacing", "recommendation": "two", "row": None}],
        },
        "owed_at_ready": {"last": []},
        "send_back": {"count": 0},
        "catch_up_resumes": [],
        "reviewer_declines": [{"comment": 900, "reason": "out of scope"}],
        "holder_after_ready": {"bundles": [{"class": "send-back"}], "transcript": {"status": "found", "calls": []}},
        "holder_quiet": {"status": "quiet", "calls": [], "unprompted": []},
        "handoff_plan": {"reading": "composed"},
        "plan_writer_launches": [],
        "limits": ["a limit"],
        "cost_split": {"holder_before": PRICED, "holder_after": PRICED, "builder": PRICED},
        "route_comparison": {"due": True},
        "refusals": {"stretch": [REFUSAL], "reported": [REFUSAL]},
        "hand_record": None,
        "check_dispatches": [{"stage": "use", "status": "composed", "dispatch": "d1"},
                             {"stage": "floor", "status": "composed", "dispatch": "d2"}],
        "check_reports": [{"builder": "b1", "invalid": []}],
        "stretch_outcome": "success",
    }
    value.update(changes)
    return value


def reading(check, **changes):
    payload = route_report.builder_route(**inputs(**changes))
    return next(entry for entry in payload["row_checks"] if entry["check"] == check)


def with_readiness(**changes):
    value = deepcopy(inputs()["readiness"])
    value.update(changes)
    return value


HOLDS_AND_OTHER = [
    ("1.1", {}, {"owed_at_ready": {"last": ["use"]}}, "fails"),
    ("1.2", {}, {"readiness": with_readiness(launched_by_builder=False)}, "fails"),
    ("1.3", {}, {"holder_quiet": {"status": "not-quiet", "calls": [{"tool": "x"}], "unprompted": []}}, "fails"),
    ("2.1", {}, {"handoff_plan": {"reading": "differs", "reason": "holder-written"}}, "fails"),
    ("2.2", {}, {"check_dispatches": [{"stage": "use", "status": "differs", "dispatch": "d1"}]}, "fails"),
    ("2.3", {}, {"plan_writer_launches": [{"dispatch": "p"}]}, "fails"),
    ("3.1", {}, {"readiness": with_readiness(reconciled=False)}, "fails"),
    ("3.2", {}, {"check_reports": [{"builder": "b1", "invalid": ["store-and-posted-differ"]}]}, "fails"),
    ("3.3", {}, {"check_dispatches": [{"stage": "use", "status": "composed", "dispatch": "d1"},
                                      {"stage": "floor", "status": "differs", "dispatch": "d2"}]}, "fails"),
    ("4.1", {}, {"holder_after_ready": {"bundles": [{"class": "other"}],
                                        "transcript": {"status": "found", "calls": []}}}, "fails"),
    ("4.2", {"send_back": {"count": 1}}, {"send_back": {"count": 2}}, "fails"),
    ("5.2", {}, {"refusals": {"stretch": [REFUSAL], "reported": []}}, "fails"),
    ("5.3", {}, {"refusals": {"stretch": [], "reported": []}}, "not-occurred"),
    ("5.4", {}, {"readiness": with_readiness(relaunches={"pairs": [], "unpaired": [{"dispatch": "d"}]})}, "fails"),
    ("5.5", {"hand_record": {"ran_under": "codex"}}, {}, "not-applicable"),
    ("6.2", {"hand_record": {"ran_under": "codex"}}, {}, "not-applicable"),
    ("6.3", {}, {"readiness": with_readiness(vendor_model={"source": "declared", "log": None})}, "not-stated"),
    ("7.1", {}, {"route": {"name": "relay", "reason": "in-flight"}}, "not-applicable"),
    ("7.2", {"route": {"name": "relay", "reason": "owner-asked"}}, {}, "not-applicable"),
    ("7.3", {}, {"cost_split": {"holder_before": PRICED, "holder_after": PRICED,
                                "builder": {"status": "unknown", "reason": "no usage log"}}}, "not-stated"),
]


@pytest.mark.parametrize("check, holding, other, other_reading", HOLDS_AND_OTHER,
                         ids=[case[0] for case in HOLDS_AND_OTHER])
def test_each_row_check_reads_holds_and_another_reading_from_its_field(check, holding, other, other_reading):
    assert reading(check, **holding)["reading"] == "holds"
    result = reading(check, **other)
    assert result["reading"] == other_reading
    assert result["reason"]


def test_every_computed_row_check_is_listed_once():
    checks = [entry["check"] for entry in route_report.builder_route(**inputs())["row_checks"]]
    assert checks == [case[0] for case in HOLDS_AND_OTHER]


def test_the_payload_carries_every_input_under_its_name():
    given = inputs()
    payload = route_report.builder_route(**given)
    assert {key: payload[key] for key in given} == given


def test_a_hand_started_builder_that_stopped_unable_to_launch_a_named_check_holds():
    stopped = with_readiness(status="stopped", stop={"kind": "cannot-launch", "check": "use", "reason": "r"})
    assert reading("6.2", readiness=stopped, hand_record={"ran_under": "x"})["reading"] == "holds"
    shaped = with_readiness(status="stopped", stop={"kind": "shape", "check": None, "reason": "r"})
    assert reading("6.2", readiness=shaped, hand_record={"ran_under": "x"})["reading"] == "fails"


def test_a_hand_record_without_ran_under_fails():
    assert reading("5.5", hand_record={"ran_under": None})["reading"] == "fails"


def test_a_stretch_with_refusals_that_did_not_succeed_fails():
    assert reading("5.3", stretch_outcome="error")["reading"] == "fails"


def test_declared_vendor_model_with_a_readable_log_fails():
    declared = with_readiness(vendor_model={"source": "declared", "log": "readable"})
    assert reading("6.3", readiness=declared)["reading"] == "fails"


def test_the_route_comparison_due_is_echoed_in_the_cost_entry():
    assert reading("7.3")["due"] is True
    assert reading("7.3", route_comparison=None)["due"] is None


def test_unknown_statuses_read_unknown():
    assert reading("1.3", holder_quiet={"status": "unknown", "reason": "unreadable"})["reading"] == "unknown"
    unread = {"bundles": [], "transcript": {"status": "unknown", "reason": "gone"}}
    assert reading("4.1", holder_after_ready=unread)["reading"] == "unknown"


def test_missing_inputs_read_unknown_with_a_reason_and_never_raise():
    payload = route_report.builder_route()
    by_check = {entry["check"]: entry for entry in payload["row_checks"]}
    for check in ("1.1", "1.2", "1.3", "2.1", "2.2", "2.3", "3.1", "3.2", "3.3", "4.1", "4.2",
                  "5.2", "5.3", "5.4", "6.3", "7.1", "7.2", "7.3"):
        assert by_check[check]["reading"] == "unknown", check
        assert by_check[check]["reason"], check
    assert by_check["5.5"]["reading"] == "not-applicable"


def test_malformed_inputs_read_unknown():
    payload = route_report.builder_route(**inputs(
        owed_at_ready={"last": "x"}, readiness={"record": 1, "relaunches": "x", "vendor_model": 3},
        send_back={"count": "1"}, check_dispatches="x", check_reports=[1], cost_split={"builder": PRICED},
        refusals={"stretch": None}, route={"name": None}))
    readings = {entry["check"]: entry["reading"] for entry in payload["row_checks"]}
    for check in ("1.1", "1.2", "2.2", "3.1", "3.2", "3.3", "4.2", "5.2", "5.3", "5.4", "6.3", "7.1", "7.3"):
        assert readings[check] == "unknown", check


def test_placement_puts_a_differing_decline_under_needs_decision_and_an_agreed_one_under_declined_findings():
    payload = route_report.builder_route(**inputs())
    views = {"5:F1": "agrees", "5:F2": "agrees", "6:F1": "differs", "900": "agrees"}
    placed = route_report.placement(payload, views)
    needs = placed["needs_decision"]
    assert [entry["key"] for entry in needs["declines"]] == ["6:F1"]
    assert needs["declines"][0]["holder_view"] == "differs"
    groups = {group["reason"]: [entry["key"] for entry in group["declines"]]
              for group in placed["declined_findings"]}
    assert groups == {"out of scope": ["5:F1", "5:F2", "900"]}
    assert needs["remaining_declines"].startswith("3 other decline(s)")


def test_placement_sends_cannot_judge_and_unviewed_declines_to_needs_decision():
    payload = route_report.builder_route(**inputs())
    placed = route_report.placement(payload, {"5:F1": "cannot-judge"})
    assert {entry["key"]: entry["holder_view"] for entry in placed["needs_decision"]["declines"]} == {
        "5:F1": "cannot-judge", "5:F2": "not-given", "6:F1": "not-given", "900": "not-given"}
    assert placed["declined_findings"] == []


def test_every_decline_appears_uncollapsed():
    payload = route_report.builder_route(**inputs())
    for views in ({}, {"5:F1": "agrees", "900": "differs"}, {key: "agrees" for key in ("5:F1", "5:F2", "6:F1", "900")}):
        placed = route_report.placement(payload, views)
        shown = [entry["key"] for entry in placed["needs_decision"]["declines"]]
        shown += [entry["key"] for group in placed["declined_findings"] for entry in group["declines"]]
        assert sorted(shown) == ["5:F1", "5:F2", "6:F1", "900"]
        assert "declines" not in placed["settled_by_checks"]


def test_placement_names_row_decisions_and_a_differing_handoff_and_settles_the_rest():
    differs = {"reading": "differs", "reason": "holder-written"}
    payload = route_report.builder_route(**inputs(handoff_plan=differs))
    placed = route_report.placement(payload, {})
    assert placed["needs_decision"]["decisions"] == [{"text": "which name", "recommendation": "short", "row": 2}]
    assert placed["needs_decision"]["handoff_plan"] == differs
    assert route_report.placement(route_report.builder_route(**inputs()), {})["needs_decision"]["handoff_plan"] is None
    settled = placed["settled_by_checks"]
    assert set(settled) == {"route", "cost_split", "limits", "catch_up_resumes", "row_checks"}
    assert settled["row_checks"] == payload["row_checks"]


def test_placement_of_an_empty_payload_does_not_raise():
    placed = route_report.placement(route_report.builder_route(), None)
    assert placed["needs_decision"]["declines"] == [] and placed["declined_findings"] == []

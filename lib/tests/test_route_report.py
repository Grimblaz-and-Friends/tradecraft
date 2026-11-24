"""The release report's builder-route payload: its row-check readings."""
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
            "builder": {"vendor": "claude", "model": "opus", "started_by": "launch", "usage_log": None}},
        "owed_at_ready": {"first": [], "last": []},
        "send_back": {"count": 0},
        "catch_up_resumes": [],
        "reviewer_declines": [{"comment": 900, "reason": "out of scope"}],
        "holder_after_ready": {"bundles": [{"class": "send-back"}, {"class": "catch-up-resume"}],
                               "transcript": {"status": "none", "calls": [], "reason": None}},
        "holder_quiet": {"status": "quiet", "calls": [], "launches": [], "unprompted": [], "reason": None},
        "handoff_plan": {"reading": "composed"},
        "plan_writer_launches": [],
        "limits": ["a limit"],
        "cost_split": {"holder_before": PRICED, "holder_after": PRICED, "builder": PRICED},
        "route_comparison": {"due": True},
        "refusals": {"stretch": [REFUSAL], "launches": [{"logged": [REFUSAL], "reported": [REFUSAL]}]},
        "hand_record": None,
        "check_dispatches": [{"stage": "use", "status": "composed", "dispatch": "d1"},
                             {"stage": "floor", "status": "composed", "dispatch": "d2"}],
        "check_reports": [{"builder": "b1", "invalid": []}],
        "stretch_outcome": "success",
        "stretch_seconds": [{"dispatch": "s1", "seconds": 3600, "limit_seconds": 28800}],
        "lane": None,
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
    ("1.1", {}, {"owed_at_ready": {"first": [], "last": [{"stage": "use"}]}}, "fails"),
    ("1.2", {}, {"readiness": with_readiness(launched_by_builder=False)}, "fails"),
    ("1.3", {}, {"holder_quiet": {"status": "not-quiet", "calls": [{"tool": "x"}], "launches": [],
                                  "unprompted": []}}, "fails"),
    ("2.1", {}, {"handoff_plan": {"reading": "differs", "reason": "holder-written"}}, "fails"),
    ("2.2", {}, {"check_dispatches": [{"stage": "use", "status": "differs", "dispatch": "d1"}]}, "fails"),
    ("2.3", {}, {"plan_writer_launches": [{"dispatch": "p"}]}, "fails"),
    ("3.1", {}, {"readiness": with_readiness(reconciled=False)}, "fails"),
    ("3.2", {}, {"check_reports": [{"builder": "b1", "invalid": ["store-and-posted-differ"]}]}, "fails"),
    ("3.3", {}, {"check_dispatches": [{"stage": "use", "status": "composed", "dispatch": "d1"},
                                      {"stage": "floor", "status": "differs", "dispatch": "d2"}]}, "fails"),
    ("4.1", {}, {"holder_after_ready": {"bundles": [{"class": "other"}],
                                        "transcript": {"status": "none", "calls": []}}}, "fails"),
    ("4.2", {"send_back": {"count": 1}}, {"send_back": {"count": 2}}, "fails"),
    ("5.2", {}, {"refusals": {"stretch": [REFUSAL], "launches": [{"logged": [REFUSAL], "reported": []}]}}, "fails"),
    ("5.3", {}, {"refusals": {"stretch": [], "launches": []}}, "not-occurred"),
    ("5.4", {}, {"readiness": with_readiness(relaunches={"pairs": [], "unpaired": [{"dispatch": "d"}]})}, "fails"),
    ("5.5", {"hand_record": {"ran_under": "codex"}}, {}, "not-applicable"),
    ("6.2", {"hand_record": {"ran_under": "codex"}}, {}, "not-applicable"),
    ("6.3", {}, {"readiness": with_readiness(vendor_model={"source": "declared", "log": "readable"})}, "fails"),
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


def test_every_computed_row_check_is_listed_once_in_row_order_and_says_what_it_asserts():
    entries = route_report.builder_route(**inputs())["row_checks"]
    order = ["1.1", "1.2", "1.3", "2.1", "2.2", "2.3", "3.1", "3.2", "3.3", "4.1", "4.2",
             "5.2", "5.3", "5.4", "5.5", "6.2", "6.3", "7.1", "7.2", "7.3"]
    assert [entry["check"] for entry in entries] == [case[0] for case in HOLDS_AND_OTHER] == order
    assert list(route_report.ROW_CHECKS) == order
    assert [entry["asserts"] for entry in entries] == list(route_report.ROW_CHECKS.values())


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


def test_nothing_owed_reads_not_occurred_without_a_ready_record_and_unknown_with_the_owed_readers_reason():
    assert reading("1.1", owed_at_ready={"first": None, "last": None})["reading"] == "not-occurred"
    unread = {"status": "unknown", "reason": "the hand record's handoff block names no owed checks"}
    for owed in (unread, {"first": [], "last": unread}):
        entry = reading("1.1", owed_at_ready=owed)
        assert (entry["reading"], entry["reason"]) == ("unknown", unread["reason"])
    assert "1 check(s)" in reading("1.1", owed_at_ready={"first": [], "last": [{"stage": "floor"}]})["reason"]


@pytest.mark.parametrize("name", ["calls", "launches", "unprompted"])
def test_the_holder_is_quiet_only_when_its_calls_launches_and_unprompted_replies_are_all_empty(name):
    quiet = {"status": "not-quiet", "calls": [], "launches": [], "unprompted": [], "reason": None}
    assert reading("1.3", holder_quiet=quiet | {name: [{"timestamp": "t"}]})["reading"] == "fails"
    assert reading("1.3", holder_quiet={key: value for key, value in quiet.items() if key != name}
                   )["reading"] == "unknown"


def test_a_holder_after_ready_with_a_send_back_and_a_catch_up_holds_and_a_listed_call_fails():
    allowed = [{"class": name} for name in ("bought-panel", "source-verification", "send-back", "catch-up-resume")]
    after = {"bundles": allowed, "transcript": {"status": "none", "calls": [], "reason": None}}
    assert reading("4.1", holder_after_ready=after)["reading"] == "holds"
    called = after | {"transcript": {"status": "found", "calls": [{"tool": "Agent"}], "reason": None}}
    assert reading("4.1", holder_after_ready=called)["reading"] == "fails"


def test_a_declared_vendor_model_with_no_readable_log_is_not_stated_with_its_reason():
    declared = with_readiness(vendor_model={"source": "declared", "log": "absent", "reason": "no usage log named"})
    entry = reading("6.3", readiness=declared)
    assert (entry["reading"], entry["reason"]) == ("not-stated", "no usage log named")
    unreadable = with_readiness(vendor_model={"source": "declared", "log": "unreadable"})
    assert reading("6.3", readiness=unreadable)["reading"] == "not-stated"


def test_the_route_checks_hold_only_for_their_own_route_and_reason():
    assert reading("7.1", route={"name": "builder", "reason": "in-flight"})["reading"] == "not-applicable"
    assert reading("7.2", route={"name": "relay", "reason": "owner-asked"})["reading"] == "holds"
    assert reading("7.1", route={"name": "unknown", "error": "switch broken"})["reason"] == "switch broken"


def test_on_the_mechanical_lane_the_handoff_is_read_against_the_affirmed_brief_and_no_use_is_owed():
    mechanical = route_report.builder_route(**inputs(lane="mechanical", check_dispatches=[
        {"stage": "acceptance-criterion", "status": "composed", "dispatch": "r1"}]))
    by_check = {entry["check"]: entry for entry in mechanical["row_checks"]}
    assert by_check["2.1"]["reading"] == "holds" and by_check["2.1"]["field"] == "handoff_plan.reading"
    assert by_check["2.1"]["asserts"] == route_report.MECHANICAL_ROW_CHECKS["2.1"]
    assert "affirmed brief" in by_check["2.1"]["asserts"] and "settled plan" not in by_check["2.1"]["asserts"]
    assert by_check["2.2"]["reading"] == "not-applicable" and "mechanical lane owes no use" in by_check["2.2"]["reason"]
    assert by_check["2.3"] == reading("2.3")
    differs = route_report.builder_route(**inputs(lane="mechanical", handoff_plan={"reading": "differs"}))
    assert differs["row_checks"][3]["reading"] == "fails"
    assert differs["row_checks"][3]["asserts"] == route_report.MECHANICAL_ROW_CHECKS["2.1"]
    assert reading("2.1")["asserts"] == route_report.ROW_CHECKS["2.1"]


def test_the_route_comparison_due_is_echoed_in_the_cost_entry():
    assert reading("7.3")["due"] is True
    assert reading("7.3", route_comparison=None)["due"] is None


def test_unknown_statuses_read_unknown_with_their_reason():
    entry = reading("1.3", holder_quiet={"status": "unknown", "reason": "the hand record names no holder session"})
    assert (entry["reading"], entry["reason"]) == ("unknown", "the hand record names no holder session")
    unread = {"bundles": [], "transcript": {"status": "unknown", "calls": [], "reason": "gone"}}
    assert reading("4.1", holder_after_ready=unread)["reading"] == "unknown"
    assert reading("4.1", holder_after_ready={"status": "unknown", "reason": "no session"})["reason"] == "no session"
    # Something that already fails 4.1 is not hidden behind an unread transcript.
    failing = {"bundles": [{"class": "other"}], "transcript": {"status": "unknown", "reason": "gone"}}
    assert reading("4.1", holder_after_ready=failing)["reading"] == "fails"


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


def test_refusals_pair_in_order_whatever_their_wording():
    worded = {"command": "a merge", "reason": "the stretch may not merge"}
    entry = reading("5.2", refusals={"stretch": [REFUSAL], "launches": [{"logged": [REFUSAL], "reported": [worded]}]})
    assert entry["reading"] == "holds"
    assert entry["pairs"] == [{"dispatch": None, "logged": REFUSAL, "reported": worded}]


def test_a_logged_refusal_with_no_reported_entry_fails():
    second = {"command": "gh pr close", "reason": "not allowed"}
    entry = reading("5.2", refusals={"stretch": [REFUSAL, second], "launches": [{"logged": [REFUSAL, second], "reported": [REFUSAL]}]})
    assert entry["reading"] == "fails" and "gh pr close" in entry["reason"]
    assert entry["pairs"][1] == {"dispatch": None, "logged": second, "reported": None}


def test_each_launch_pairs_its_refusals_with_its_own_record():
    sent_back = {"command": "gh pr close", "reason": "not allowed"}
    entry = reading("5.2", refusals={"stretch": [REFUSAL, sent_back], "launches": [
        {"dispatch": "a", "logged": [REFUSAL], "reported": [REFUSAL]},
        {"dispatch": "b", "logged": [sent_back], "reported": [sent_back]}]})
    assert entry["reading"] == "holds" and [pair["dispatch"] for pair in entry["pairs"]] == ["a", "b"]

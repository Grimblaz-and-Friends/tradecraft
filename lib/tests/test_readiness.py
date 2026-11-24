"""The readiness record's form, its check reports' counted findings, and their reconciliation."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cold_reader
import readiness


HEAD = "a" * 40
DISPATCH = "0123456789abcdef0123456789abcdef"
OTHER = "fedcba9876543210fedcba9876543210"
EM = chr(0x2014)


def record(**changes):
    value = {
        "schema_version": 1,
        "builder": {"vendor": "claude", "model": "opus", "started_by": "launch", "usage_log": None},
        "checks": [{"stage": "acceptance-criterion", "criterion": "B3", "row": None, "dispatch": DISPATCH,
                    "head": HEAD, "report": 123, "relaunch_of": None}],
        "findings": [{"report": 123, "finding": "F1", "disposition": "fixed", "commit": "b" * 40},
                     {"report": 123, "finding": "F2", "disposition": "declined", "reason": "out of scope"}],
        "rows": [{"row": 2, "carried_by": "test", "where": "lib/tests/test_x.py"}],
        "decisions": [{"text": "which name", "recommendation": "the short one", "row": None}],
        "refusals": [{"command": "git push", "reason": "not allowed", "then": "returned it as a request"}],
        "stop": None,
    }
    value.update(changes)
    return value


def body(value):
    return "Readiness.\n\n```json\n" + json.dumps(value) + "\n```\n"


def attributes(**changes):
    value = {"head": HEAD, "status": "ready", "dispatch": DISPATCH}
    value.update(changes)
    return value


def test_1011_a_whole_ready_record_reads():
    assert readiness.payload(body(record()), "ready") == record()
    assert readiness.marker_error(attributes(head="c" * 64), body(record())) is None
    reach = {**record()["checks"][0], "stage": "reach", "criterion": None, "report": None}
    assert readiness.payload(body(record(checks=[reach])), "ready")["checks"] == [reach]
    with pytest.raises(readiness.ReadinessError, match="check report must be a comment id"):
        readiness.payload(body(record(checks=[{**reach, "stage": "use"}])), "ready")


def test_1011_a_stopped_record_carries_its_stop():
    stop = {"kind": "cannot-launch", "reason": "no seat", "check": "use"}
    assert readiness.payload(body(record(stop=stop)), "stopped")["stop"] == stop
    shape = {"kind": "shape", "reason": "brief cannot be built", "check": None}
    assert readiness.marker_error(attributes(status="stopped"), body(record(stop=shape))) is None


def mutate(path, value):
    def apply(target):
        target = deepcopy(target)
        holder = target
        for key in path[:-1]:
            holder = holder[key]
        if value is KeyError:
            del holder[path[-1]]
        else:
            holder[path[-1]] = value
        return target
    return apply


BROKEN = {
    "unknown top field": mutate(("extra",), 1),
    "missing top field": mutate(("rows",), KeyError),
    "schema version": mutate(("schema_version",), 2),
    "schema version bool": mutate(("schema_version",), True),
    "builder unknown key": mutate(("builder", "seat"), "x"),
    "builder started_by": mutate(("builder", "started_by"), "owner"),
    "builder empty usage log": mutate(("builder", "usage_log"), ""),
    "checks not list": mutate(("checks",), {}),
    "check stage": mutate(("checks", 0, "stage"), "panel"),
    "check stage not a string": mutate(("checks", 0, "stage"), ["use"]),
    "finding disposition not a string": mutate(("findings", 0, "disposition"), ["fixed"]),
    "check criterion missing": mutate(("checks", 0, "criterion"), None),
    "check criterion empty": mutate(("checks", 0, "criterion"), " "),
    "check row": mutate(("checks", 0, "row"), "2"),
    "check row bool": mutate(("checks", 0, "row"), True),
    "check dispatch": mutate(("checks", 0, "dispatch"), DISPATCH.upper()),
    "check relaunch_of": mutate(("checks", 0, "relaunch_of"), "x"),
    "check head": mutate(("checks", 0, "head"), "abc"),
    "check report": mutate(("checks", 0, "report"), 0),
    "check unknown key": mutate(("checks", 0, "seat"), 1),
    "finding disposition": mutate(("findings", 0, "disposition"), "deferred"),
    "fixed finding with reason": mutate(("findings", 0, "reason"), "x"),
    "fixed finding commit": mutate(("findings", 0, "commit"), "HEAD"),
    "finding id": mutate(("findings", 0, "finding"), "1"),
    "declined reason type": mutate(("findings", 1, "reason"), None),
    "duplicate finding": mutate(("findings", 1), {"report": 123, "finding": "F1", "disposition": "declined",
                                                  "reason": "x"}),
    "rows carried_by": mutate(("rows", 0, "carried_by"), "hope"),
    "rows where": mutate(("rows", 0, "where"), ""),
    "decision row": mutate(("decisions", 0, "row"), "3"),
    "decision recommendation": mutate(("decisions", 0, "recommendation"), ""),
    "refusal then": mutate(("refusals", 0, "then"), ""),
    "ready with stop": mutate(("stop",), {"kind": "shape", "reason": "x", "check": None}),
}


@pytest.mark.parametrize("name", sorted(BROKEN))
def test_1011_each_malformed_record_is_refused(name):
    with pytest.raises(readiness.ReadinessError):
        readiness.payload(body(BROKEN[name](record())), "ready")


@pytest.mark.parametrize("stop", [
    None,
    {"kind": "cannot-launch", "reason": "no seat", "check": None},
    {"kind": "cannot-launch", "reason": "no seat", "check": " "},
    {"kind": "giving-up", "reason": "x", "check": None},
    {"kind": "shape", "reason": "", "check": None},
    {"kind": "shape", "reason": "x"},
])
def test_1011_a_stopped_record_needs_a_whole_stop(stop):
    with pytest.raises(readiness.ReadinessError):
        readiness.payload(body(record(stop=stop)), "stopped")


@pytest.mark.parametrize("text", [
    "no block",
    body(record()) + body(record()),
    "```json\n{\"schema_version\": 1, \"schema_version\": 1}\n```\n",
    "```json\n{not json}\n```\n",
    "```json\n[]\n```\n",
])
def test_1011_the_body_needs_exactly_one_readable_object(text):
    with pytest.raises(readiness.ReadinessError):
        readiness.payload(text, "ready")


def test_1011_an_unknown_status_is_refused():
    with pytest.raises(readiness.ReadinessError):
        readiness.payload(body(record()), "open")


@pytest.mark.parametrize("change, expected", [
    ({"head": "abc"}, "head"),
    ({"status": "open"}, "status"),
    ({"dispatch": DISPATCH.upper()}, "dispatch"),
    ({"dispatch": DISPATCH[:-1]}, "dispatch"),
    ({"extra": "1"}, "exactly"),
])
def test_1011_marker_attributes_are_checked(change, expected):
    assert expected in readiness.marker_error(attributes(**change), body(record()))


def test_1011_marker_names_the_payload_error_and_status_must_match():
    assert "stop" in readiness.marker_error(attributes(status="stopped"), body(record()))
    assert "fenced" in readiness.marker_error(attributes(), "nothing")


def test_1011_every_counting_stage_has_a_tail():
    assert set(readiness.RETURN_TAILS) == {"acceptance-criterion", "use", "cold-reader"}
    assert "`Result: unable`" in readiness.RETURN_TAILS["acceptance-criterion"]
    assert "`Findings: none`" in readiness.RETURN_TAILS["use"]
    assert "`Can tell: no`" in readiness.RETURN_TAILS["cold-reader"]


UNREADABLE = [{"finding": "F0", "text": "findings-unreadable"}]


@pytest.mark.parametrize("text, expected", [
    ("\nResult: pass\nAll good.", []),
    ("Result: fail\nThe criterion's case is not handled.",
     [{"finding": "F1", "text": "The criterion's case is not handled."}]),
    ("Result: unable", [{"finding": "F1", "text": "Result: unable"}]),
    ("I think it passes.\nResult: pass", UNREADABLE),
    ("", UNREADABLE),
])
def test_1011_criterion_returns_count(text, expected):
    assert readiness.report_findings("acceptance-criterion", text) == expected


@pytest.mark.parametrize("text, expected", [
    ("Used it.\n\nFindings: none\n", []),
    ("Used it.\nFindings:\nF1. The flag is ignored.\n- F3. Help text is wrong.",
     [{"finding": "F1", "text": "The flag is ignored."}, {"finding": "F3", "text": "Help text is wrong."}]),
    ("Findings: none\nlater the real list\nFindings:\nF1. Broken.", [{"finding": "F1", "text": "Broken."}]),
    ("Used it, all fine.", UNREADABLE),
    ("Findings:\n", UNREADABLE),
    ("Findings:\nF1. Broken.\nand more prose", UNREADABLE),
    ("Findings:\nF1. Broken.\nF1. Again.", UNREADABLE),
    ("Findings: none\nF1. Broken.", UNREADABLE),
])
def test_1011_use_returns_count(text, expected):
    assert readiness.report_findings("use", text) == expected


def account(flags, tell):
    return ("## Sections\nlib/x.py:1-4 does x.\n\n## Flags\n" + flags + "\n\n## Why this change was made\n"
            "Can tell: " + tell + "\nFrom the design document.\n\n## Worth a look\nlib/x.py:2 the core.\n")


def test_1011_cold_reader_returns_count_with_its_own_parser():
    flags = (f"lib/x.py:2 {EM} missing-reason {EM} no reason given\n"
             f"lib/y.py {EM} history {EM} names a past run")
    found = readiness.report_findings("cold-reader", account(flags, "no"))
    parsed = cold_reader.parse_account(account(flags, "no"))["flags"]
    assert found == [{"finding": "F1", "text": cold_reader.flag_line(parsed[0])},
                     {"finding": "F2", "text": cold_reader.flag_line(parsed[1])},
                     {"finding": "F3", "text": "Can tell: no"}]
    assert readiness.report_findings("cold-reader", account("none", "yes")) == []
    assert readiness.report_findings("cold-reader", account("none", "no")) == [
        {"finding": "F1", "text": "Can tell: no"}]


@pytest.mark.parametrize("text", ["Looks fine to me.", account("lib/x.py is odd", "yes"),
                                  account("none", "maybe")])
def test_1011_an_unreadable_cold_reader_account_counts_f0(text):
    assert readiness.report_findings("cold-reader", text) == UNREADABLE


def test_1011_an_uncounted_stage_is_refused():
    with pytest.raises(readiness.ReadinessError):
        readiness.report_findings("floor", "anything")


def report(number=123, findings=("F1", "F2"), named=True, stage="use"):
    return {"report": number, "stage": stage, "findings": list(findings), "named": named}


def reachable(commit):
    return commit == "b" * 40


def test_1011_a_fully_answered_record_reconciles():
    assert readiness.reconcile(record(), [report()], reachable) == {
        "reconciled": True, "unreconciled": [], "reachability": "checked"}


def problems(value, reports):
    result = readiness.reconcile(value, reports, reachable)
    assert result["reconciled"] is (not result["unreconciled"])
    return [(item["report"], item["finding"], item["problem"]) for item in result["unreconciled"]]


def test_1011_a_finding_without_an_entry_is_missing():
    assert problems(record(), [report(findings=("F1", "F2", "F3"))]) == [(123, "F3", "missing")]


def test_1011_a_fix_must_be_reachable():
    value = record()
    value["findings"][0]["commit"] = "c" * 40
    assert problems(value, [report()]) == [(123, "F1", "unreachable")]


def test_1011_a_decline_needs_a_reason():
    value = record()
    value["findings"][1]["reason"] = "  "
    assert problems(value, [report()]) == [(123, "F2", "reasonless")]


def test_1011_an_entry_for_no_counted_finding_is_extra():
    value = record()
    value["findings"].append({"report": 999, "finding": "F1", "disposition": "declined", "reason": "x"})
    assert problems(value, [report()]) == [(999, "F1", "extra")]
    assert problems(record(), [report(findings=("F1",))]) == [(123, "F2", "extra")]


def test_1011_a_second_entry_for_one_finding_is_extra():
    value = record()
    value["findings"].append({"report": 123, "finding": "F1", "disposition": "declined", "reason": "x"})
    assert problems(value, [report()]) == [(123, "F1", "extra")]


def test_1011_a_report_the_record_leaves_out_is_named_once_and_still_answered():
    reports = [report(), report(number=456, findings=("F1", "F2"), named=False)]
    assert problems(record(), reports) == [(456, None, "left-out-of-record"), (456, "F1", "missing"),
                                           (456, "F2", "missing")]
    assert problems(record(), [report(), report(number=456, findings=(), named=False)]) == []


def test_1011_an_unreadable_report_is_answered_as_f0():
    value = record(findings=[{"report": 7, "finding": "F0", "disposition": "declined", "reason": "rerun"}])
    assert problems(value, [report(number=7, findings=("F0",))]) == []


def check(dispatch, relaunch_of=None):
    return {"stage": "use", "criterion": None, "row": None, "dispatch": dispatch, "head": HEAD,
            "report": 1, "relaunch_of": relaunch_of}


def test_1011_an_errored_check_pairs_with_its_later_relaunch():
    third = "1" * 32
    checks = [check(DISPATCH), check(OTHER, relaunch_of=DISPATCH), check(third), check(None)]
    result = readiness.relaunches(checks, [DISPATCH, third])
    assert result == {"pairs": [[checks[0], checks[1]]], "unpaired": [checks[2]]}
    # An errored launch the record leaves out is unpaired, and a relaunch must name its launch.
    assert readiness.relaunches([check(None, relaunch_of=OTHER)], [OTHER]) == {
        "pairs": [], "unpaired": [{"dispatch": OTHER}]}


def test_1011_a_relaunch_must_come_after_the_failure():
    checks = [check(OTHER, relaunch_of=DISPATCH), check(DISPATCH)]
    assert readiness.relaunches(checks, [DISPATCH]) == {"pairs": [], "unpaired": [checks[1]]}



def test_a_row_reader_names_its_row_and_leaves_the_criterion_null():
    row = {**record()["checks"][0], "criterion": None, "row": 3}
    assert readiness.payload(body(record(checks=[row])), "ready")["checks"] == [row]
    for criterion, number in ((None, None), (None, 0), (None, True)):
        with pytest.raises(readiness.ReadinessError):
            readiness.payload(body(record(checks=[{**row, "criterion": criterion, "row": number}])), "ready")


def test_a_criterion_check_with_a_row_beside_it_reads_as_the_criterions_check():
    named = record()["checks"][0]
    assert readiness.payload(body(record(checks=[{**named, "row": 2}])), "ready")["checks"] == [named]


def test_unmapped_rows_are_the_affirmed_rows_nothing_carries():
    mapped = record(rows=[{"row": 2, "carried_by": "test", "where": "lib/tests/test_x.py"}])
    assert readiness.unmapped_rows(mapped, [1, 2, 3, 3]) == [1, 3]
    assert readiness.unmapped_rows(record(rows=[]), [2]) == [2]
    assert readiness.unmapped_rows(mapped, [2]) == []


def test_a_fix_whose_commit_could_not_be_asked_is_unverified_and_reachability_incomplete():
    value = record()
    value["findings"][0]["commit"] = "c" * 40
    result = readiness.reconcile(value, [report()], lambda commit: None)
    assert result == {"reconciled": False, "reachability": "incomplete",
                      "unreconciled": [{"report": 123, "finding": "F1", "problem": "unverified"}]}


def test_a_fix_whose_commit_is_not_in_the_head_is_unreachable_and_reachability_checked():
    value = record()
    value["findings"][0]["commit"] = "c" * 40
    result = readiness.reconcile(value, [report()], lambda commit: False)
    assert result["reconciled"] is False and result["reachability"] == "checked"
    assert result["unreconciled"] == [{"report": 123, "finding": "F1", "problem": "unreachable"}]


def test_each_distinct_commit_is_asked_once():
    asked = []
    fixed = [{"report": 123, "finding": finding, "disposition": "fixed", "commit": "b" * 40}
             for finding in ("F1", "F2", "F3")]
    value = record(findings=fixed + [{"report": 456, "finding": "F1", "disposition": "fixed", "commit": "d" * 40}])
    reports = [report(findings=("F1", "F2", "F3")), report(number=456, findings=("F1",))]
    result = readiness.reconcile(value, reports, lambda commit: asked.append(commit) or True)
    assert result["reconciled"] is True and result["reachability"] == "checked"
    assert asked == ["b" * 40, "d" * 40]


def test_a_record_with_no_fix_reads_reachability_checked():
    value = record(findings=[{"report": 123, "finding": "F1", "disposition": "declined", "reason": "x"}])
    assert readiness.reconcile(value, [report(findings=("F1",))], lambda commit: None)["reachability"] == "checked"

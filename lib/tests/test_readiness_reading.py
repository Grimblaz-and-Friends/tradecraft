"""The entrance's reading of a builder's readiness record against the check reports it launched."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import work  # noqa: E402
from test_route import BRIEF, decision, ended_stretch, fixture, launch, post, readiness_record  # noqa: E402

HEAD = "a" * 40
COMMIT = "b" * 40


def record(dispatch, *, status="ready", checks=(), findings=(), stop=None):
    payload = {"schema_version": 1,
               "builder": {"vendor": "claude", "model": "m", "started_by": "launch", "usage_log": None},
               "checks": list(checks), "findings": list(findings), "rows": [], "decisions": [],
               "refusals": [], "stop": stop}
    return (f"<!-- tradecraft:readiness:v1 head={HEAD} status={status} dispatch={dispatch} -->\n\n"
            f"```json\n{json.dumps(payload)}\n```\n")


def check(report, dispatch):
    return {"stage": "use", "criterion": None, "row": None, "dispatch": dispatch, "head": HEAD,
            "report": report, "relaunch_of": None}


def accounting(builder, seat, *, findings=("F1", "F2")):
    """builder_checks' output for one counting use report of the builder's."""
    return {"check_dispatches": [{"bundle": "b", "stage": "use", "status": "composed", "dispatch": seat,
                                  "outcome": "success", "builder": builder}],
            "check_reports": [{"comment": 900, "dispatch": seat, "counts": True, "invalid": [], "stage": "use",
                               "builder": builder, "head": HEAD, "criterion": None, "findings": list(findings)}],
            "quotations": []}


def test_1011_a_record_answering_every_finding_reads_reconciled(tmp_path):
    state = fixture(tmp_path, BRIEF)
    builder, seat = launch(state, "stretch", 1), "c" * 32
    state = fixture(tmp_path, BRIEF, record(builder, checks=[check(900, seat)], findings=[
        {"report": 900, "finding": "F1", "disposition": "fixed", "commit": COMMIT},
        {"report": 900, "finding": "F2", "disposition": "declined", "reason": "Out of the brief's rows."}]))
    reading = work.readiness_reading(state, accounting(builder, seat))
    assert reading["reconciled"] is True and reading["unreconciled"] == []
    assert reading["dispatch_is_this_works_stretch"] and reading["launched_by_builder"]
    assert [entry["finding"] for entry in reading["declines"]] == ["F2"]
    assert reading["status"] == "ready" and reading["stop"] is None and reading["reachability"] == "unchecked"


def test_1011_a_report_the_record_leaves_out_is_listed_and_its_findings_owed(tmp_path):
    state = fixture(tmp_path, BRIEF)
    builder, seat = launch(state, "stretch", 1), "c" * 32
    state = fixture(tmp_path, BRIEF, record(builder))
    reading = work.readiness_reading(state, accounting(builder, seat, findings=("F1",)))
    assert reading["reconciled"] is False
    assert {entry["problem"] for entry in reading["unreconciled"]} == {"left-out-of-record", "missing"}


def test_1011_another_builders_reports_are_not_this_records(tmp_path):
    state = fixture(tmp_path, BRIEF)
    builder, seat = launch(state, "stretch", 1), "c" * 32
    state = fixture(tmp_path, BRIEF, record(builder))
    assert work.readiness_reading(state, accounting("d" * 32, seat))["reconciled"] is True


def test_1011_a_stopped_record_reports_its_stop(tmp_path):
    state = fixture(tmp_path, BRIEF)
    builder = launch(state, "stretch", 1)
    stop = {"kind": "cannot-launch", "reason": "gh is not signed in", "check": "use"}
    state = fixture(tmp_path, BRIEF, record(builder, status="stopped", stop=stop))
    reading = work.readiness_reading(state, None)
    assert reading["status"] == "stopped" and reading["stop"] == stop


def test_1011_no_record_reads_nothing_and_an_unlawful_one_is_listed(tmp_path):
    assert work.readiness_reading(fixture(tmp_path, BRIEF), None) is None
    broken = record("e" * 32).replace("\"schema_version\": 1", "\"schema_version\": 2")
    reading = work.readiness_reading(fixture(tmp_path, BRIEF, broken), None)
    assert reading["record"] is None and len(reading["invalid"]) == 1


def test_1011_a_record_reads_its_terms_reports_and_names_one_of_its_stretches(tmp_path):
    state = fixture(tmp_path, BRIEF)
    before, builder, seat = launch(state, "stretch", -5), launch(state, "stretch", 1), "c" * 32
    resumed = launch(state, "stretch", 9, handoff={"resume_of": builder})
    state = fixture(tmp_path, BRIEF, record(before), record(resumed))
    reading = work.readiness_reading(state, accounting(builder, seat, findings=("F1",)))
    assert reading["dispatch"] == resumed and reading["reconciled"] is False
    assert [entry["reason"] for entry in reading["invalid"]] == ["dispatch is no stretch of this term"]
    state, _builder = ended_stretch(tmp_path / "decided")
    post(state, readiness_record(before), 30)
    assert decision(state)[:3] == ("stretch-stopped", "holder-owned", "builder-stopped")


def test_1011_each_named_check_is_tied_to_its_own_launch_and_report(tmp_path):
    state = fixture(tmp_path, BRIEF)
    builder, seat = launch(state, "stretch", 1), "c" * 32
    floor = {**check(None, None), "stage": "floor", "report": 901}
    cases = {"tied": ([check(900, seat), floor], True), "another head": ([{**check(900, seat), "head": COMMIT}], False),
             "another stage": ([{**check(900, seat), "stage": "cold-reader"}], False),
             "no launch named": ([check(900, None)], False)}
    for name, (checks, expected) in cases.items():
        state = fixture(tmp_path, BRIEF, record(builder, checks=checks))
        assert work.readiness_reading(state, accounting(builder, seat))["launched_by_builder"] is expected, name

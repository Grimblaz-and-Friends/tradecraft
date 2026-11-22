"""The route a change takes, read from the cloud switch, its first launch and the owner's marker."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import uuid

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))

import work  # noqa: E402

PRODUCER = "producer"
CONFIG = work.WorkConfig(marker_producers=frozenset({PRODUCER}))
WORK = "o/r#5"
START = datetime(2026, 11, 22, tzinfo=timezone.utc)
BRIEF = "<!-- tradecraft:affirmed-brief:v1 -->\n\n## Purpose\n\nA change.\n"


def route_marker(route, words="> Take this one by the route I named."):
    return f"<!-- tradecraft:route:v1 route={route} -->\n\n{words}\n"


def fixture(tmp_path, *texts):
    comments = [{"id": 100 + index, "body": text, "user": {"login": PRODUCER},
                 "created_at": (START + timedelta(minutes=index)).isoformat()}
                for index, text in enumerate(texts)]
    return work.WorkState("o/r", 5, {"number": 5, "state": "open", "body": "", "labels": [],
                                     "user": {"login": PRODUCER}},
                          issue_comments=comments, config=CONFIG, record_root=tmp_path / "store")


def launch(state, stage, minutes, **request_fields):
    """A bundle written as the launcher writes one, launched the given minutes after the start."""
    dispatch_id = uuid.uuid4().hex
    request = work.records.request_record(
        dispatch_id=dispatch_id, work=WORK, stage=stage, settings_source="fixture",
        settings_scope="implementer", vendor="claude", model="fixture", effort="fixture",
        continuity="fresh", permission_boundary="fixture", root=None,
        now=START + timedelta(minutes=minutes))
    request.update(request_fields)
    output = state.record_root / f"{stage}-{dispatch_id}" / "result.md"
    output.parent.mkdir(parents=True)
    work.records.write_json(work.records.sidecar(output, ".request.json"), request)
    work.records.write_json(work.records.sidecar(output, ".run.json"), {
        "schema_version": work.records.SCHEMA_VERSION, "dispatch_id": dispatch_id, "outcome": "success",
        "completed_at": (START + timedelta(minutes=minutes + 1)).isoformat()})
    return dispatch_id


def reading(state):
    return work._route(state)


def test_1011_nothing_launched_reads_the_builder_by_default(tmp_path):
    assert reading(fixture(tmp_path, BRIEF)) == {
        "name": "builder", "reason": "default", "marker": None, "overruled": None}


def test_1011_an_owners_relay_marker_with_nothing_launched_reads_relay(tmp_path):
    assert reading(fixture(tmp_path, BRIEF, route_marker("relay"))) == {
        "name": "relay", "reason": "owner-asked", "marker": 101, "overruled": None}


def test_1011_the_latest_route_marker_governs(tmp_path):
    state = fixture(tmp_path, BRIEF, route_marker("relay"), route_marker("builder"))
    assert reading(state)["name"] == "builder" and reading(state)["marker"] == 102


def test_1011_a_first_stretch_launch_holds_the_builder_route(tmp_path):
    state = fixture(tmp_path, BRIEF)
    launch(state, "stretch", 5)
    assert reading(state)["name"] == "builder" and reading(state)["reason"] == "in-flight"
    # A builder-session marker, a later build and a second affirmed brief change nothing.
    state.issue_comments.append({"id": 200, "body": "<!-- tradecraft:builder-session:v1 session=s -->\n",
                                 "user": {"login": PRODUCER}, "created_at": (START + timedelta(hours=1)).isoformat()})
    launch(state, "build", 90)
    state.issue_comments.append({"id": 201, "body": BRIEF, "user": {"login": PRODUCER},
                                 "created_at": (START + timedelta(hours=2)).isoformat()})
    assert reading(state) == {"name": "builder", "reason": "in-flight", "marker": None, "overruled": None}


def test_1011_a_hand_started_record_reads_as_a_stretch(tmp_path):
    state = fixture(tmp_path, BRIEF)
    launch(state, "stretch", 5, started_by="hand")
    assert reading(state)["name"] == "builder"


def test_1011_a_first_build_launch_holds_the_relay_route_after_an_amended_brief(tmp_path):
    state = fixture(tmp_path, BRIEF)
    launch(state, "build", 5)
    launch(state, "stretch", 30)
    state.issue_comments.append({"id": 201, "body": BRIEF.replace("A change.", "An amended change."),
                                 "user": {"login": PRODUCER}, "created_at": (START + timedelta(hours=2)).isoformat()})
    assert reading(state) == {"name": "relay", "reason": "in-flight", "marker": None, "overruled": None}


def test_1011_a_first_artifact_author_launch_is_the_relay_and_seats_decide_nothing(tmp_path):
    state = fixture(tmp_path, BRIEF)
    for stage in ("cold-seat", "cold-reader", "use", "floor", "review-disposition"):
        launch(state, stage, 1)
    assert reading(state)["reason"] == "default"
    launch(state, "artifact", 5)
    assert reading(state)["name"] == "relay" and reading(state)["reason"] == "in-flight"


def test_1011_a_builder_session_marker_without_a_build_does_not_make_the_relay(tmp_path):
    state = fixture(tmp_path, BRIEF, "<!-- tradecraft:builder-session:v1 session=s -->\n")
    assert reading(state)["name"] == "builder" and reading(state)["reason"] == "default"


def test_1011_an_ask_for_the_builder_on_a_relay_change_is_overruled(tmp_path):
    state = fixture(tmp_path, BRIEF, route_marker("builder"))
    launch(state, "build", 5)
    assert reading(state) == {"name": "relay", "reason": "in-flight", "marker": None,
                              "overruled": {"asked": "builder", "marker": 101}}


def test_1011_an_ask_for_the_relay_on_a_builder_change_is_overruled(tmp_path):
    state = fixture(tmp_path, BRIEF, route_marker("relay"))
    launch(state, "stretch", 5)
    assert reading(state)["overruled"] == {"asked": "relay", "marker": 101}
    assert reading(state)["name"] == "builder"


def test_1011_a_cloud_repository_keeps_the_relay(tmp_path, monkeypatch):
    monkeypatch.setattr(work.cloud_build, "route_for",
                        lambda work_value: ({"practice": {"repository": "x/y"}}, "fixture"))
    state = fixture(tmp_path, BRIEF, route_marker("builder"))
    launch(state, "stretch", 5)
    assert reading(state) == {"name": "relay", "reason": "cloud", "marker": None,
                              "overruled": {"asked": "builder", "marker": 101}}


def test_1011_a_broken_cloud_switch_reads_unknown_in_the_report(tmp_path, monkeypatch, capsys):
    def broken(work_value):
        raise work.cloud_build.CloudError("unreadable switch")
    monkeypatch.setattr(work.cloud_build, "route_for", broken)
    state = fixture(tmp_path, BRIEF)
    monkeypatch.setattr(work, "_evaluate_reach", lambda state: None)
    monkeypatch.setattr(work, "_implementer_environments", lambda state: None)
    monkeypatch.setattr(work, "_evaluate_launch_findings", lambda state: None)
    monkeypatch.setattr(work, "_github_write_report", lambda state: None)
    work._emit_report({}, state)
    route = json.loads(capsys.readouterr().out)["route"]
    assert route["name"] is None and route["reason"] == "unknown" and "unreadable switch" in route["error"]


def test_1011_the_report_carries_the_route(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(work, "_evaluate_reach", lambda state: None)
    monkeypatch.setattr(work, "_implementer_environments", lambda state: None)
    monkeypatch.setattr(work, "_evaluate_launch_findings", lambda state: None)
    monkeypatch.setattr(work, "_github_write_report", lambda state: None)
    work._emit_report({}, fixture(tmp_path, BRIEF, route_marker("relay")))
    assert json.loads(capsys.readouterr().out)["route"]["name"] == "relay"


def test_1011_an_invalid_route_marker_is_invalid(tmp_path):
    unknown = fixture(tmp_path, BRIEF, route_marker("cloud"))
    bare = fixture(tmp_path, BRIEF, "<!-- tradecraft:route:v1 route=relay -->\n\nNo quotation here.\n")
    for state, reason in ((unknown, "route must be relay or builder"), (bare, "route marker quotes no owner's words")):
        work.validate_marker_claims(state)
        assert [claim["reason"] for claim in state.invalid_marker_claims if claim["name"] == "route"] == [reason]
        assert reading(state)["reason"] == "default"


def test_1011_a_lawful_route_marker_validates(tmp_path):
    state = fixture(tmp_path, BRIEF, route_marker("relay"))
    work.validate_marker_claims(state)
    assert [marker.name for marker in state.validated_markers if marker.name == "route"] == ["route"]

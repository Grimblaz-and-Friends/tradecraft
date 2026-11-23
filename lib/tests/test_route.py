"""The route a change takes, read from the cloud switch, its first launch and the owner's marker."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import uuid

import pytest

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


# The decision and the named stages on the builder route.

MECHANICAL = "<!-- tradecraft:affirmed-brief:v1 -->\nReview risk: ordinary\nReview lane: mechanical\n"
RULES = {"schema_version": 1, "rules": [{"name": "fixture", "include": ["lib/**"], "exclude": []}]}
HEAD = "a" * 40
CLEAR = {"behind": False, "strict": False, "conflict": False, "mergeability_known": True,
         "merge_state": "clean", "uncertainties": []}


def readiness_record(dispatch, *, status="ready", head=HEAD, stop=None):
    payload = {"schema_version": 1,
               "builder": {"vendor": "claude", "model": "m", "started_by": "launch", "usage_log": None},
               "checks": [], "findings": [], "rows": [], "decisions": [], "refusals": [], "stop": stop}
    return (f"<!-- tradecraft:readiness:v1 head={head} status={status} dispatch={dispatch} -->\n\n"
            f"```json\n{json.dumps(payload)}\n```\n")


def with_pull_request(state, synchronization=CLEAR):
    state.pr = {"number": 7, "state": "open", "draft": True, "merged_at": None, "mergeable": True,
                "mergeable_state": "clean", "head": {"sha": HEAD}, "base": {"ref": "main", "sha": "b" * 40}}
    state.synchronization = dict(synchronization)
    return state


def post(state, body, minutes):
    state.issue_comments.append({"id": 300 + len(state.issue_comments), "body": body, "user": {"login": PRODUCER},
                                 "created_at": (START + timedelta(minutes=minutes)).isoformat()})
    state.validated_markers = None


def decision(state):
    made = work.decide(state, RULES)
    return made.stage, made.status, made.reason, made.detail


def ended_stretch(tmp_path, *texts):
    state = with_pull_request(fixture(tmp_path, MECHANICAL, *texts))
    return state, launch(state, "stretch", 5)


def test_1011_a_settled_plan_with_no_stretch_is_handed_off(tmp_path):
    stage, status, reason, _detail = decision(fixture(tmp_path, MECHANICAL))
    assert (stage, status, reason) == ("handoff", "holder-owned", "handoff-due")


def test_1011_a_live_stretch_is_with_the_builder(tmp_path):
    from comparison_window import stretch_launch
    state = fixture(tmp_path, MECHANICAL)
    pointer = stretch_launch(state.record_root, root=tmp_path / "implementation")
    stage, status, reason, detail = decision(state)
    assert (stage, status, reason) == ("with-builder", "waiting", "builder-live")
    assert pointer["dispatch_id"] in detail


def test_1011_an_ended_stretch_with_no_record_has_stopped(tmp_path):
    state, _builder = ended_stretch(tmp_path)
    assert decision(state)[:3] == ("stretch-stopped", "holder-owned", "builder-stopped")


def test_1011_a_ready_record_at_the_head_reaches_the_final_pass(tmp_path):
    state, builder = ended_stretch(tmp_path)
    state.pr["draft"] = False
    post(state, readiness_record(builder), 30)
    # The ready record continues into today's chain; the proof the builder owed is named under the final pass.
    stage, status, reason, detail = decision(state)
    assert (stage, status, reason) == ("final-pass", "holder-owned", "owed-at-ready")
    assert json.loads(detail)["reconciled"] is True and json.loads(detail)["unreconciled"] == []


def test_1011_a_stopped_record_that_could_not_launch_a_check_is_named(tmp_path):
    state, builder = ended_stretch(tmp_path)
    stop = {"kind": "cannot-launch", "reason": "gh is not signed in", "check": "use"}
    post(state, readiness_record(builder, status="stopped", stop=stop), 30)
    stage, _status, reason, detail = decision(state)
    assert (stage, reason) == ("stretch-stopped", "cannot-launch") and json.loads(detail)["stop"] == stop


def test_1011_a_ready_record_behind_the_head_is_not_ready(tmp_path):
    state, builder = ended_stretch(tmp_path)
    post(state, readiness_record(builder, head="c" * 40), 30)
    assert decision(state)[:3] == ("stretch-stopped", "holder-owned", "ready-record-not-at-head")


def test_1011_a_base_that_moved_after_the_ready_record_is_caught_up(tmp_path):
    state, builder = ended_stretch(tmp_path)
    state.synchronization = {**CLEAR, "behind": True, "strict": True, "merge_state": "behind"}
    post(state, readiness_record(builder), 30)
    assert decision(state)[:3] == ("catch-up", "holder-owned", "base-moved-after-ready")


def test_1011_the_builder_route_artifact_is_the_holders_to_write(tmp_path):
    connected = MECHANICAL.replace("mechanical", "connected")
    made = work.decide(fixture(tmp_path, connected), RULES)
    assert (made.stage, made.dispatch, made.status) == ("artifact", False, "holder-owned")
    assert "`author=holder`" in made.detail


def test_1011_a_relay_change_keeps_todays_chain(tmp_path):
    asked = work.decide(fixture(tmp_path, MECHANICAL, route_marker("relay")), RULES)
    in_flight = fixture(tmp_path / "flight", MECHANICAL)
    launch(in_flight, "build", 5)
    for made in (asked, work.decide(in_flight, RULES)):
        assert (made.stage, made.dispatch, made.continuity, made.reason) == (
            "build", True, "fresh", "pull-request-absent")
    connected = MECHANICAL.replace("mechanical", "connected")
    made = work.decide(fixture(tmp_path / "plan", connected, route_marker("relay")), RULES)
    assert (made.stage, made.dispatch, made.continuity, made.status) == ("artifact", True, "fresh", "runnable")


class NoTransport:
    """Any GitHub call fails the test: the refusal comes before any read beyond the state."""

    def __getattr__(self, name):
        raise AssertionError(f"read GitHub ({name}) after the state")


def named(tmp_path, monkeypatch, state, stage):
    """A holder's named run of STAGE over STATE: its refusal's code and text, or None."""
    root = tmp_path / "holder"
    (root / ".github").mkdir(parents=True, exist_ok=True)
    (root / ".github" / "change-proof.json").write_text(json.dumps(RULES), encoding="utf-8")
    state.version_obligation = {}
    monkeypatch.setattr(work, "_read_policy_state", lambda *a, **k: state)
    monkeypatch.setattr(work, "_capture_policy_snapshot", lambda *a, **k: None)
    args = work.parser().parse_args(["run", stage, "--repo", "o/r", "--issue", "5", "--root", str(root)])
    try:
        work.run(args, transport=NoTransport(), executor=lambda *a, **k: pytest.fail("launched"))
    except work.RouteRefused as refusal:
        return refusal.code, str(refusal)
    return None


@pytest.fixture()
def stored(tmp_path):
    """A fixture over the store a named run reads, the machine's default one."""
    def make(*texts):
        state = fixture(tmp_path, *texts)
        state.record_root = work.records.default_record_root()
        return state
    return make


@pytest.mark.parametrize("stage", ["build", "artifact", "floor", "review-disposition"])
def test_1011_the_relays_launches_are_refused_on_the_builder_route(tmp_path, monkeypatch, stored, stage):
    code, message = named(tmp_path, monkeypatch, stored(MECHANICAL), stage)
    assert code == "route-is-builder" and message.startswith("route-is-builder: ")
    assert "<!-- tradecraft:route:v1 route=relay -->" in message
    stopped = stored(MECHANICAL)
    launch(stopped, "stretch", 5)
    assert work._route(stopped)["name"] == "builder"
    assert named(tmp_path, monkeypatch, stopped, stage)[0] == "route-is-builder"


def test_1011_proof_is_the_builders_on_the_builder_route(tmp_path, monkeypatch, stored):
    assert named(tmp_path, monkeypatch, stored(MECHANICAL), "proof")[0] == "stage-is-the-builders"


def test_1011_the_release_report_waits_for_a_ready_record_at_the_head(tmp_path, monkeypatch, stored):
    state = with_pull_request(stored(MECHANICAL))
    builder = launch(state, "stretch", 5)
    assert named(tmp_path, monkeypatch, state, "release-report")[0] == "no-ready-record-at-head"
    post(state, readiness_record(builder, head="c" * 40), 30)
    assert named(tmp_path, monkeypatch, state, "release-report")[0] == "no-ready-record-at-head"
    post(state, readiness_record(builder), 40)
    assert work._refuse_off_route(state, "release-report") is None


def test_1011_a_relay_change_is_refused_nothing(stored):
    state = stored(MECHANICAL, route_marker("relay"))
    for stage in ("build", "artifact", "floor", "review-disposition", "proof", "release-report"):
        assert work._refuse_off_route(state, stage) is None


def test_1011_an_unreadable_route_holds_the_decision_and_refuses_each_stage(tmp_path, monkeypatch):
    monkeypatch.setattr(work.cloud_build, "launch_route", lambda *_a: (None, None, "the cloud switch is unreadable"))
    state = with_pull_request(fixture(tmp_path, MECHANICAL))
    assert decision(state) == ("route", "holder-owned", "route-unreadable", "the cloud switch is unreadable")
    with pytest.raises(work.RouteRefused) as caught:
        work._refuse_off_route(state, "build")
    assert caught.value.code == "route-unreadable"

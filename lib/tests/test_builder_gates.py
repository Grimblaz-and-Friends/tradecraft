"""The holder-written plan and the gates a ready record continues into, on the builder route and the relay."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import timedelta
import json
from pathlib import Path
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(LIB / "tests"))

import work  # noqa: E402
from route_fixture import BRIEF as CONNECTED, DRAFT, SETTLED  # noqa: E402
from test_route import (  # noqa: E402
    CLEAR, HEAD, MECHANICAL, RULES, START, WORK, decision, fixture, launch, post, readiness_record,
    route_marker, with_pull_request,
)

RELAY = route_marker("relay")


def draft(**attributes):
    words = "".join(f" {key}={value}" for key, value in attributes.items())
    return DRAFT.replace("status=draft", "status=draft" + words, 1)


READING = "<!-- tradecraft:holder-reading:v1 result=no-amendment -->"


def invalid(state):
    _lawful, claims = work.validate_marker_claims(state)
    return {(claim["name"], claim["reason"]) for claim in claims}


# The holder-written plan.

def test_1011_a_draft_may_name_its_holder_author_and_vendor(tmp_path):
    for index, attributes in enumerate(({"author": "holder", "vendor": "claude"}, {"author": "holder"},
                                        {"vendor": "codex"}, {})):
        state = fixture(tmp_path / str(index), CONNECTED, draft(**attributes))
        assert invalid(state) == set()


@pytest.mark.parametrize("attributes, reason", [
    ({"author": "owner"}, "artifact draft author must be holder"),
    ({"author": "holder", "vendor": "gemini"}, "artifact draft vendor must be claude or codex"),
    ({"route": "would"}, "artifact draft cannot name a settlement route"),
])
def test_1011_a_draft_names_only_a_holder_and_a_known_vendor(tmp_path, attributes, reason):
    assert ("artifact", reason) in invalid(fixture(tmp_path, CONNECTED, draft(**attributes)))


def test_1011_a_settlement_names_no_author_or_vendor(tmp_path):
    for word in ("author=holder", "vendor=claude"):
        settled = SETTLED.replace("route=unobtainable", f"route=unobtainable {word}")
        state = fixture(tmp_path / word.split("=")[0], CONNECTED, draft(author="holder", vendor="claude"), settled)
        assert ("artifact", "artifact settlement cannot name author or vendor") in invalid(state)


def test_1011_a_holder_draft_is_invalid_on_the_relay_route(tmp_path):
    relay = fixture(tmp_path / "relay", CONNECTED, RELAY, draft(author="holder", vendor="claude"))
    assert ("artifact", "holder-draft-on-relay-route") in invalid(relay)
    builder = fixture(tmp_path / "builder", CONNECTED, draft(author="holder", vendor="claude"))
    assert invalid(builder) == set()


def test_1011_a_holder_reading_counts_for_nothing_on_the_builder_route(tmp_path):
    builder = fixture(tmp_path / "builder", CONNECTED, draft(author="holder", vendor="claude"), SETTLED, READING)
    assert ("holder-reading", "not-read-on-builder-route") in invalid(builder)
    relay = fixture(tmp_path / "relay", CONNECTED, RELAY, draft(), SETTLED, READING)
    assert invalid(relay) == set()


def test_1011_a_builder_route_settlement_owes_no_holder_reading(tmp_path):
    made = work.decide(fixture(tmp_path / "builder", CONNECTED, draft(author="holder", vendor="claude"),
                               SETTLED), RULES)
    assert (made.stage, made.reason) == ("handoff", "handoff-due")
    relay = work.decide(fixture(tmp_path / "relay", CONNECTED, RELAY, draft(), SETTLED), RULES)
    assert (relay.stage, relay.reason) == ("holder-read", "whole-change-holder-reading-absent")


def test_1011_a_holder_plans_producer_is_its_draft_markers_vendor(tmp_path, monkeypatch):
    state = fixture(tmp_path, CONNECTED, draft(author="holder", vendor="codex"))
    [plan] = [marker for marker in state.issue_markers if marker.name == "artifact"]
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    assert work._plan_producer_vendor(state, plan, in_run=True) == ("codex", f"holder-written draft marker {plan.source_id}")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "11111111-1111-1111-1111-111111111111")
    with pytest.raises(work.WorkError, match="^holder-vendor-disagrees: "):
        work._plan_producer_vendor(state, plan, in_run=True)
    # Judging a verdict already given reads the marker alone; the session running now proves nothing of it.
    assert work._plan_producer_vendor(state, plan)[0] == "codex"
    unnamed = fixture(tmp_path / "unnamed", CONNECTED, draft(author="holder"))
    with pytest.raises(work.WorkError, match="names no vendor"):
        work._plan_producer_vendor(unnamed, unnamed.issue_markers[-1])


def capture_seat(monkeypatch):
    launches = []
    original_run = subprocess.run

    def run(command, *args, **kwargs):
        if len(command) > 1 and Path(command[1]).name == "dispatch_seat.py":
            launches.append(list(command))
            return subprocess.CompletedProcess(command, 0)
        return original_run(command, *args, **kwargs)
    monkeypatch.setattr(work.subprocess, "run", run)
    monkeypatch.setattr(work, "_recipient_run", run)
    return launches


@pytest.mark.parametrize("holder", [True, False])
def test_1011_a_claude_seat_on_a_claude_holders_plan_records_why(tmp_path, monkeypatch, holder):
    texts = (CONNECTED, draft(author="holder", vendor="claude")) if holder else (CONNECTED, RELAY, draft())
    state = fixture(tmp_path, *texts)
    work.validate_marker_claims(state)
    monkeypatch.setattr(work, "judging_root", lambda _root: nullcontext(tmp_path))
    monkeypatch.setattr(work, "_git_snapshot", lambda _root: (HEAD, ""))
    if not holder:
        monkeypatch.setattr(work, "_producer_vendor", lambda *_a, **_k: ("claude", "artifact bundle"))
    launches = capture_seat(monkeypatch)
    runtime = Path(sys.executable).resolve()
    assert work.execute_stage(state, work.Decision("cold-seat", True, "fresh", "fixture"), tmp_path, None,
                              claude_path=runtime, codex_path=runtime, timeout_seconds=1800,
                              floor_command="python fixture-check.py") == 0
    [command] = launches
    assert command[command.index("--own-vendor") + 1] == "claude"
    assert command[command.index("--vendor") + 1] == "claude"
    assert command[command.index("--same-vendor-reason") + 1] == (
        "holder-written-plan" if holder else "owner-selected-claude-implementer")
    source = command[command.index("--own-vendor-source") + 1]
    assert source.startswith("holder-written draft marker ") if holder else source == "artifact bundle"


# The gates a ready record continues into.

def ready(tmp_path, *texts, draft_pr=False):
    state = with_pull_request(fixture(tmp_path, MECHANICAL, *texts))
    state.pr["draft"] = draft_pr
    builder = launch(state, "stretch", 5)
    post(state, readiness_record(builder), 30)
    return state, builder


def test_1011_a_ready_record_on_a_draft_pull_request_names_ready_reviewers_as_the_builders(tmp_path):
    # On this route the builder readies reviewers, so a draft pull request at ready leaves it owed.
    state, _builder = ready(tmp_path, draft_pr=True)
    stage, _status, reason, detail = decision(state)
    assert (stage, reason) == ("final-pass", "owed-at-ready")
    assert json.loads(detail)["owed_at_ready"]["stage"] == "ready-reviewers"


def test_1011_proof_owed_at_ready_is_named_under_the_final_pass(tmp_path):
    state, _builder = ready(tmp_path)
    stage, status, reason, detail = decision(state)
    assert (stage, status, reason) == ("final-pass", "holder-owned", "owed-at-ready")
    detail = json.loads(detail)
    assert detail["owed_at_ready"]["stage"] == "proof" and detail["reconciled"] is True
    # The relay's same evidence asks the holder for its proof run, as it does today.
    relay = with_pull_request(fixture(tmp_path / "relay", MECHANICAL, RELAY))
    relay.pr["draft"] = False
    made = work.decide(relay, RULES)
    assert made.stage != "final-pass"


def test_1011_a_review_thread_owed_at_ready_is_the_builders(tmp_path, monkeypatch):
    state, _builder = ready(tmp_path)
    monkeypatch.setattr(work, "_undisposed_threads", lambda _state: ([41], []))
    stage, _status, reason, detail = decision(state)
    assert (stage, reason) == ("final-pass", "owed-at-ready")
    assert json.loads(detail)["owed_at_ready"]["stage"] == "review-disposition"


def test_1011_no_gate_before_the_ready_record_reads_the_chain(tmp_path):
    state = with_pull_request(fixture(tmp_path, MECHANICAL))
    state.pr["draft"] = False
    launch(state, "stretch", 5)
    assert decision(state)[:3] == ("stretch-stopped", "holder-owned", "builder-stopped")


def test_1011_a_ready_builder_without_a_pull_request_owes_one(tmp_path):
    state = fixture(tmp_path, MECHANICAL)
    builder = launch(state, "stretch", 5)
    post(state, readiness_record(builder), 30)
    assert decision(state)[:3] == ("open-pull-request", "holder-owned", "builder-returned-without-pull-request")


def test_1011_a_builder_floor_counts_with_its_handoff_command_and_output(tmp_path):
    floor = f"<!-- tradecraft:floor:v1 head={HEAD} status=pass -->\n\n"
    command = "python -B -m pytest -q"
    state = with_pull_request(fixture(tmp_path, MECHANICAL, floor + f"```\n{command}\n```\n\n3 passed\n",
                                      floor + f"```\n{command}\n```\n", floor + "3 passed\n"))
    launch(state, "stretch", 5, handoff={"floor_command": command})
    reasons = [claim["reason"] for claim in work.validate_marker_claims(state)[1] if claim["name"] == "floor"]
    assert len(reasons) == 2 and all("handoff's floor command" in reason for reason in reasons)
    assert [marker.body.endswith("3 passed\n") for marker in state.markers if marker.name == "floor"] == [True]
    # On the relay the same marker still needs its floor bundle.
    relay = with_pull_request(fixture(tmp_path / "relay", MECHANICAL, RELAY,
                                      floor + f"```\n{command}\n```\n\n3 passed\n"))
    assert [claim["name"] for claim in work.validate_marker_claims(relay)[1]] == ["floor"]


def stretch_with_session(state, session):
    """A completed stretch whose run record observed SESSION, written as the launcher writes its records."""
    dispatch_id = "0" * 31 + "1"
    request = work.records.request_record(
        dispatch_id=dispatch_id, work=WORK, stage="stretch", settings_source="fixture",
        settings_scope="implementer", vendor="claude", model="fixture", effort="fixture",
        continuity="fresh", permission_boundary="fixture", root=None, now=START + timedelta(minutes=5))
    output = state.record_root / f"stretch-{dispatch_id}" / "result.md"
    output.parent.mkdir(parents=True)
    work.records.write_json(work.records.sidecar(output, ".request.json"), request)
    work.records.write_json(work.records.sidecar(output, ".run.json"), {
        "schema_version": work.records.SCHEMA_VERSION, "dispatch_id": dispatch_id, "outcome": "success",
        "actual_vendor": "claude", "attempts": [{"observed": {"session_id": session}}],
        "completed_at": (START + timedelta(minutes=6)).isoformat()})


def test_1011_a_builder_session_agrees_with_a_stretch_bundle(tmp_path):
    session = "22222222-2222-2222-2222-222222222222"
    marker = f"<!-- tradecraft:builder-session:v1 session={session} -->"
    state = fixture(tmp_path, MECHANICAL)
    stretch_with_session(state, session)
    post(state, marker, 30)
    assert not [claim for claim in work.validate_marker_claims(state)[1] if claim["name"] == "builder-session"]
    post(state, marker.replace(session, "33333333-3333-3333-3333-333333333333"), 40)
    assert [claim["reason"] for claim in work.validate_marker_claims(state)[1]] == [
        "builder-session claim disagrees with its build bundle"]


def test_1011_the_stretch_makes_a_cold_reading_due(tmp_path):
    state = fixture(tmp_path, MECHANICAL)
    assert work._cold_reading_due(state) is False
    launch(state, "stretch", 5)
    assert work._cold_reading_due(state) is True


def test_1011_a_builders_catch_up_takes_the_holder_session_from_its_launch(tmp_path):
    state = fixture(tmp_path, MECHANICAL)
    launch(state, "stretch", 5, holder_session_id="44444444-4444-4444-4444-444444444444")
    request = next(state.record_root.rglob("*.request.json"))
    assert work._holding_launch_holder_session({"request": str(request)}) == "44444444-4444-4444-4444-444444444444"
    hand = work.launch_tree.write_hand_record(
        tmp_path / "hand", work="o/r#5", vendor="codex", model="m",
        handoff={"tree": str(tmp_path), "holder_session_id": "55555555-5555-5555-5555-555555555555"})
    assert work._holding_launch_holder_session({"request": str(hand["request"])}) == (
        "55555555-5555-5555-5555-555555555555")
    bare = fixture(tmp_path / "bare", MECHANICAL)
    launch(bare, "stretch", 5)
    with pytest.raises(work.WorkError, match="names no holder session"):
        work._holding_launch_holder_session({"request": str(next(bare.record_root.rglob("*.request.json")))})


def test_1011_a_builders_catch_up_refuses_a_holder_session_on_its_command_line(tmp_path, monkeypatch):
    state = with_pull_request(fixture(tmp_path, MECHANICAL), {**CLEAR, "behind": True})
    monkeypatch.setattr(work, "builder_mode", lambda: {"request": str(tmp_path / "absent.json")})
    monkeypatch.setattr(work, "_version_refusal", lambda *_a, **_k: None)
    work.validate_marker_claims(state)
    with pytest.raises(work.WorkError, match="give no --holder-session-id"):
        work.execute_stage(state, work.Decision("catch-up", False, None, "fixture"), tmp_path, None,
                           holder_session_id="66666666-6666-6666-6666-666666666666",
                           transport=object(), rules=RULES)


def test_1011_a_builder_floor_counts_only_at_the_head_and_from_a_producer(tmp_path):
    shown = "\n\n```\npytest\n```\n\n3 passed\n"
    state = with_pull_request(fixture(tmp_path, MECHANICAL, f"<!-- tradecraft:floor:v1 head={'c' * 40} status=pass -->"
                                      + shown))
    state.issue_comments.append({"id": 400, "body": f"<!-- tradecraft:floor:v1 head={HEAD} status=pass -->" + shown,
                                 "user": {"login": "someone"}, "created_at": START.isoformat()})
    launch(state, "stretch", 5, handoff={"floor_command": "pytest"})
    assert ("floor", "marker producer is not authorized: someone") in invalid(state)
    assert work.floor_evaluation(state)["outcome"] == "builder-missing"

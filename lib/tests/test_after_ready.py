"""After a ready record on the builder route: one send-back, the catch-up resume, the final pass's refusals,
and the release report's builder_route payload."""

from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(LIB / "tests"))

import work  # noqa: E402
from test_handoff_stage import (  # noqa: E402,F401
    HOLDER_SESSION, claude_machine, hand_requests, holder, no_spawn, quiet_report, stored, stub,
)
from test_route import (  # noqa: E402
    CLEAR, MECHANICAL, RULES, START, launch, post, readiness_record, route_marker, with_pull_request,
)

SESSION = "77777777-7777-7777-7777-777777777777"


class Recorder:
    """Records each comment posted; any other GitHub call fails the test."""

    def __init__(self):
        self.posted = []

    def post(self, endpoint, payload):
        self.posted.append((endpoint, payload["body"]))
        return {"id": 900 + len(self.posted)}

    def __getattr__(self, name):
        raise AssertionError(f"read GitHub ({name})")


def run(monkeypatch, holder, state, stage, *extra, transport=None):
    monkeypatch.setattr(work, "_read_policy_state", lambda *a, **k: state)
    monkeypatch.setattr(work, "_capture_policy_snapshot", lambda *a, **k: None)
    monkeypatch.setattr(work, "_evaluate_reach", lambda state: setattr(state, "reach", {"state": "not-due"}))
    state.validated_markers = None
    args = work.parser().parse_args(["run", stage, "--repo", "o/r", "--issue", "5", "--root", str(holder),
                                     "--holder-session-id", HOLDER_SESSION, *extra])
    return work.run(args, transport=transport or Recorder(), executor=lambda *a, **k: pytest.fail("launched"))


def refused(monkeypatch, holder, state, stage, *extra, transport=None):
    with pytest.raises(work.RouteRefused) as caught:
        run(monkeypatch, holder, state, stage, *extra, transport=transport)
    return caught.value.code


def words(tmp_path, text="Point 1: the floor skips lib/new.py.\n"):
    path = tmp_path / "send-back.txt"
    path.write_bytes(text.encode("utf-8"))
    return str(path)


def ready_hand(tmp_path, monkeypatch, holder):
    """A hand-started builder whose ready record stands at the head: the final pass."""
    state = with_pull_request(stored(tmp_path, MECHANICAL))
    state.pr["draft"] = False
    assert run(monkeypatch, holder, state, "handoff", "--by-hand", "gemini:any-model") == 0
    [request] = hand_requests()
    post(state, readiness_record(request["dispatch_id"]), 30)
    work._complete_readied_hand_records(state)
    return state, request


def test_1011_a_relay_change_has_no_send_back(tmp_path, monkeypatch, holder, quiet_report, no_spawn):
    state = stored(tmp_path, MECHANICAL, route_marker("relay"))
    assert refused(monkeypatch, holder, state, "send-back", "--dispatch", words(tmp_path)) == "route-is-relay"


def test_1011_the_final_pass_launches_nothing_but_one_send_back(
        tmp_path, monkeypatch, holder, quiet_report, no_spawn, capsys):
    state, first = ready_hand(tmp_path, monkeypatch, holder)
    assert work.decide(state, RULES).stage == "final-pass"
    for stage in ("cold-seat", "use", "cold-reader", "acceptance-criterion", "handoff"):
        assert refused(monkeypatch, holder, state, stage) == "final-pass-launches-nothing", stage
    assert refused(monkeypatch, holder, state, "send-back") == "dispatch-absent"
    assert refused(monkeypatch, holder, state, "send-back", "--dispatch", words(tmp_path),
                   "--timeout-seconds", "3601") == "limit-above-default"
    capsys.readouterr()
    transport = Recorder()
    assert run(monkeypatch, holder, state, "send-back", "--dispatch", words(tmp_path), transport=transport) == 0
    out = capsys.readouterr().out
    second = next(request for request in hand_requests() if request["dispatch_id"] != first["dispatch_id"])
    assert second["handoff"]["resume_of"] == first["dispatch_id"]
    assert second["handoff"]["send_back"]["timeout_seconds"] == 3600
    assert ("Re-run the checks your changes make stale, answer each point, and post a new readiness record.\n\n"
            "Point 1: the floor skips lib/new.py.\n") in out and second["dispatch_id"] in out
    [(endpoint, body)] = transport.posted
    assert endpoint == "repos/o/r/issues/5/comments"
    assert body == (f"<!-- tradecraft:send-back:v1 dispatch={second['dispatch_id']} -->\n\n"
                    "Point 1: the floor skips lib/new.py.\n")
    post(state, body, 40)
    assert refused(monkeypatch, holder, state, "send-back", "--dispatch", words(tmp_path)) == "with-builder"
    post(state, readiness_record(second["dispatch_id"]), 50)
    spent = Recorder()
    assert refused(monkeypatch, holder, state, "send-back", "--dispatch", words(tmp_path),
                   transport=spent) == "send-back-spent"
    assert spent.posted == [] and len(hand_requests()) == 2


def test_1011_a_send_back_waits_for_the_final_pass(tmp_path, monkeypatch, holder, quiet_report, no_spawn):
    state = with_pull_request(stored(tmp_path, MECHANICAL))
    launch(state, "stretch", 5)
    assert refused(monkeypatch, holder, state, "send-back", "--dispatch", words(tmp_path)) == "not-at-final-pass"


def resumable(state, tmp_path):
    """A completed launched stretch whose run observed SESSION, with its ready record at the head."""
    dispatch = launch(state, "stretch", 5, root=str(tmp_path / "implementation"),
                      lineage_branch="tradecraft/5-fixture", holder_session_id=HOLDER_SESSION)
    run_path = work.records.sidecar(state.record_root / f"stretch-{dispatch}" / "result.md", ".run.json")
    run_path.unlink()
    work.records.write_json(run_path, {
        "schema_version": work.records.SCHEMA_VERSION, "dispatch_id": dispatch, "outcome": "success",
        "actual_vendor": "claude", "attempts": [{"observed": {"session_id": SESSION}}],
        "completed_at": (START + timedelta(minutes=6)).isoformat()})
    post(state, readiness_record(dispatch), 30)
    return dispatch


@pytest.mark.parametrize("stage", ["send-back", "catch-up"])
def test_1011_a_launched_builder_is_resumed_in_its_own_session(
        tmp_path, monkeypatch, holder, quiet_report, stub, stage):
    claude_machine()
    stub()
    behind = {**CLEAR, "behind": True, "strict": True, "merge_state": "behind"}
    state = with_pull_request(stored(tmp_path, MECHANICAL), behind if stage == "catch-up" else CLEAR)
    state.pr["draft"] = False
    first = resumable(state, tmp_path)
    if stage == "send-back":
        assert refused(monkeypatch, holder, state, "catch-up") == "catch-up-not-due"
    transport = Recorder()
    extra = ("--dispatch", words(tmp_path)) if stage == "send-back" else ()
    assert run(monkeypatch, holder, state, stage, *extra, transport=transport) == 0
    [pointer] = [json.loads(path.read_bytes()) for path in
                 work.launch_tree.pointer_directory(work.records.default_record_root()).glob("*.json")]
    argv = json.loads((Path(pointer["request"]).parent / "argv.json").read_bytes())
    assert argv[argv.index("--resume") + 1] == SESSION and argv[argv.index("--timeout-seconds") + 1] == "3600"
    sent = Path(argv[argv.index("--dispatch") + 1]).read_bytes()
    request = json.loads(Path(pointer["request"]).read_bytes())
    assert request["handoff"]["resume_of"] == first
    if stage == "catch-up":
        assert sent == work.CATCH_UP_LINE and transport.posted == []
        assert "catch_up_resume" in request["handoff"]
    else:
        assert sent.startswith(work.SEND_BACK_HEADER) and sent.endswith(b"lib/new.py.\n")
        assert transport.posted[0][1].startswith(f"<!-- tradecraft:send-back:v1 dispatch={pointer['dispatch_id']} -->")


def received(state, tmp_path, *, holder_written=False, altered=False, **block):
    """A first stretch whose kept dispatch is the composed handoff, or an altered one."""
    common = {"branch": "tradecraft/5-fixture", "holder_root": tmp_path, "notify": None, "floor_command": None}
    composed = work.compose_handoff_for(state, plugin_root=LIB.parent, **common)
    dispatch = launch(state, "stretch", 5, lineage_branch=common["branch"], handoff={
        "holder_written": holder_written, "notify": None, "floor_command": None, "pull_request": 7, **block})
    output = state.record_root / f"stretch-{dispatch}" / "result.md"
    work.records.sidecar(output, ".dispatch.bin").write_bytes(composed + (b"more\n" if altered else b""))
    return dispatch


@pytest.mark.parametrize("kind, expected", [
    ({}, ("composed", None)), ({"altered": True}, ("differs", "altered")),
    ({"holder_written": True}, ("differs", "holder-written"))])
def test_1011_the_release_report_reads_the_handoff_it_received(tmp_path, kind, expected):
    state = with_pull_request(stored(tmp_path, MECHANICAL))
    state.holder_root = tmp_path
    received(state, tmp_path, **kind)
    plan = work._builder_route_report(state)["handoff_plan"]
    assert (plan["reading"], plan["reason"]) == expected


def test_1011_the_release_report_carries_the_builder_route(tmp_path, monkeypatch):
    monkeypatch.setattr(work.change_cost, "route_split", lambda **_k: (_ for _ in ()).throw(
        work.change_cost.CostError("no transcript")))
    state = with_pull_request(stored(tmp_path, MECHANICAL))
    state.holder_root = tmp_path
    first = received(state, tmp_path, timeout_seconds=30000.0, override_reason="a long change")
    launch(state, "artifact", 6)
    resumed = launch(state, "stretch", 40, handoff={"resume_of": first, "timeout_seconds": 30000.0,
                                                     "send_back": {"timeout_seconds": 7200.0,
                                                                   "override_reason": "a wide fix"}})
    caught = launch(state, "stretch", 60, handoff={"resume_of": resumed, "catch_up_resume": {}})
    post(state, readiness_record(first), 30)
    post(state, f"<!-- tradecraft:send-back:v1 dispatch={resumed} -->\n\nPoint 1.\n", 35)
    post(state, readiness_record(caught), 70)
    report = work._builder_route_report(state)
    assert report["route"]["name"] == "builder" and report["readiness"]["dispatch"] == caught
    assert report["send_back"] == {"count": 1, "marker": "302", "second_ready_head": "a" * 40}
    assert [(entry["stage"], entry["override_reason"]) for entry in report["limits"]] == [
        ("handoff", "a long change"), ("send-back", "a wide fix")]
    assert [entry["dispatch"] for entry in report["catch_up_resumes"]] == [caught]
    assert len(report["plan_writer_launches"]) == 1 and report["stretch_outcome"] == "success"
    assert report["cost_split"]["builder"]["status"] == "unknown"
    assert report["hand_record"] is None and report["refusals"] == {"stretch": [], "reported": []}
    rows = {entry["check"]: entry["reading"] for entry in report["row_checks"]}
    assert rows["2.1"] == "holds" and rows["2.3"] == "fails" and rows["4.2"] == "holds"


@pytest.mark.parametrize("stage", ["send-back", "catch-up"])
def test_1011_a_resume_above_its_default_needs_an_override_reason(stage):
    above = SimpleNamespace(stage=stage, timeout_seconds=3601.0, budget_override_reason=None)
    with pytest.raises(work.RouteRefused, match="limit-above-default.*--budget-override-reason"):
        work._resume_limit(above)
    assert work._resume_limit(SimpleNamespace(stage=stage, timeout_seconds=7200.0,
                                              budget_override_reason="a long merge")) == 7200.0

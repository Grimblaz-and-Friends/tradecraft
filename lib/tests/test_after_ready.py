"""After a ready record on the builder route: one send-back, the catch-up resume, the final pass's refusals,
and the release report's builder_route payload."""

from __future__ import annotations

from dataclasses import replace
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
    CLEAR, MECHANICAL, PLANNED, RULES, START, launch, post, readiness_record, route_marker, with_pull_request,
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
    state = with_pull_request(stored(tmp_path, *PLANNED))
    state.pr["draft"] = False
    state.floor_public = {"outcome": "ci-met", "head": state.pr["head"]["sha"]}  # The CI floor passed.
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
    assert ("Re-run the checks your changes make stale, answer each point, post proof and then a new readiness record.\n\n"
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
    state = with_pull_request(stored(tmp_path, *PLANNED))
    launch(state, "stretch", 5)
    assert refused(monkeypatch, holder, state, "send-back", "--dispatch", words(tmp_path)) == "not-at-final-pass"


def test_1011_a_send_back_does_not_wait_on_a_connected_reviewer(
        tmp_path, monkeypatch, holder, quiet_report, no_spawn):
    state, _first = ready_hand(tmp_path, monkeypatch, holder)
    state.config = replace(state.config, connected_reviewers=frozenset({"reviewer-bot"}))
    monkeypatch.setattr(work, "_reviewer_ran", lambda _state: False)
    assert work.decide(state, RULES).reason == "required-connected-reviewer-has-not-run"
    # The final pass has begun, so the holder still launches nothing while the chain waits.
    assert refused(monkeypatch, holder, state, "cold-seat") == "final-pass-launches-nothing"
    transport = Recorder()
    assert run(monkeypatch, holder, state, "send-back", "--dispatch", words(tmp_path), transport=transport) == 0
    assert len(transport.posted) == 1 and len(hand_requests()) == 2


def test_1011_a_stopped_record_completes_a_hand_started_record(
        tmp_path, monkeypatch, holder, quiet_report, no_spawn, capsys):
    state = stored(tmp_path, *PLANNED)
    assert run(monkeypatch, holder, state, "handoff", "--by-hand", "gemini:any-model") == 0
    [request] = hand_requests()
    stop = {"kind": "cannot-launch", "reason": "gh is not signed in", "check": "use"}
    post(state, readiness_record(request["dispatch_id"], status="stopped", stop=stop), 30)
    work._complete_readied_hand_records(state)
    made = work.decide(state, RULES)
    assert (made.stage, made.reason, json.loads(made.detail)["stop"]) == ("stretch-stopped", "cannot-launch", stop)
    capsys.readouterr()
    assert run(monkeypatch, holder, state, "handoff", "--resume-reason", "gh is signed in now") == 0
    assert "gh is signed in now" in capsys.readouterr().out and len(hand_requests()) == 2


def resumable(state, tmp_path, *, ready=True, session=SESSION, **handoff):
    """A completed launched stretch whose run observed SESSION, with its ready record at the head."""
    dispatch = launch(state, "stretch", 5, root=str(tmp_path / "implementation"),
                      lineage_branch="tradecraft/5-fixture", holder_session_id=HOLDER_SESSION,
                      **({"handoff": handoff} if handoff else {}))
    run_path = work.records.sidecar(state.record_root / f"stretch-{dispatch}" / "result.md", ".run.json")
    run_path.unlink()
    work.records.write_json(run_path, {
        "schema_version": work.records.SCHEMA_VERSION, "dispatch_id": dispatch, "outcome": "success",
        "actual_vendor": "claude", "attempts": [{"observed": {"session_id": session}}],
        "completed_at": (START + timedelta(minutes=6)).isoformat()})
    if ready:
        post(state, readiness_record(dispatch), 30)
    return dispatch


def stub_argv():
    [pointer] = [json.loads(path.read_bytes()) for path in
                 work.launch_tree.pointer_directory(work.records.default_record_root()).glob("*.json")]
    return json.loads((Path(pointer["request"]).parent / "argv.json").read_bytes()), pointer


def test_1011_a_stopped_builder_resumes_with_the_limit_its_resume_declares(
        tmp_path, monkeypatch, holder, quiet_report, stub):
    claude_machine()
    stub()
    state = with_pull_request(stored(tmp_path, *PLANNED))
    resumable(state, tmp_path, ready=False)
    assert run(monkeypatch, holder, state, "handoff", "--resume-reason", "go on", "--timeout-seconds", "30000",
               "--budget-override-reason", "a long change") == 0
    argv, pointer = stub_argv()
    assert argv[argv.index("--resume") + 1] == SESSION and argv[argv.index("--timeout-seconds") + 1] == "30000"
    request = json.loads(Path(pointer["request"]).read_bytes())
    assert request["handoff"]["resume_limit"] == {"timeout_seconds": 30000.0, "override_reason": "a long change"}


def test_1011_a_recovery_restart_composes_from_what_its_handoff_carried(
        tmp_path, monkeypatch, holder, quiet_report, stub):
    claude_machine()
    stub()
    monkeypatch.setattr(work.work_recovery, "restartable", lambda *_a: True)
    state = with_pull_request(stored(tmp_path, *PLANNED))
    resumable(state, tmp_path, ready=False, session=None, floor_command="make check", notify="Start 5")
    assert run(monkeypatch, holder, state, "handoff", "--resume-reason", "start again") == 0
    argv, _pointer = stub_argv()
    sent = Path(argv[argv.index("--dispatch") + 1]).read_text(encoding="utf-8")
    assert "```text\nmake check\n```" in sent and "named `Start 5`" in sent


@pytest.mark.parametrize("stage", ["send-back", "catch-up"])
def test_1011_a_launched_builder_is_resumed_in_its_own_session(
        tmp_path, monkeypatch, holder, quiet_report, stub, stage):
    claude_machine()
    stub()
    behind = {**CLEAR, "behind": True, "strict": True, "merge_state": "behind"}
    state = with_pull_request(stored(tmp_path, *PLANNED), behind if stage == "catch-up" else CLEAR)
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


def received(state, tmp_path, *, holder_written=False, altered=False, version=None, **block):
    """A first stretch whose kept dispatch is the composed handoff, or an altered one."""
    common = {"branch": "tradecraft/5-fixture", "holder_root": tmp_path, "notify": None, "floor_command": None}
    composed = work.compose_handoff_for(state, plugin_root=LIB.parent, **common)
    dispatch = launch(state, "stretch", 5, lineage_branch=common["branch"], handoff={
        "holder_written": holder_written, "notify": None, "floor_command": None, "pull_request": 7, **block},
        **({"producer_version": version} if version else {}))
    output = state.record_root / f"stretch-{dispatch}" / "result.md"
    work.records.sidecar(output, ".dispatch.bin").write_bytes(composed + (b"more\n" if altered else b""))
    return dispatch


@pytest.mark.parametrize("kind, expected", [
    ({}, ("composed", None)), ({"altered": True}, ("differs", "altered")),
    ({"holder_written": True}, ("differs", "holder-written")), ({"version": "0.0.1"}, (
        "unknown", f"composed-by-another-version: 0.0.1 composed it and {work.records.producer_version()} runs"))])
def test_1011_the_release_report_reads_the_handoff_it_received(tmp_path, kind, expected):
    state = with_pull_request(stored(tmp_path, *PLANNED))
    state.holder_root = tmp_path
    received(state, tmp_path, **kind)
    plan = work._builder_route_report(state)["handoff_plan"]
    assert (plan["reading"], plan["reason"]) == expected


def test_1011_a_handoff_read_from_another_checkout_recomposes_with_its_own_roots(tmp_path):
    state = with_pull_request(stored(tmp_path, *PLANNED))
    received(state, tmp_path, holder_root=str(tmp_path), plugin_root=str(LIB.parent))
    state.holder_root = tmp_path / "another-checkout"
    assert work._builder_route_report(state)["handoff_plan"]["reading"] == "composed"


def test_1011_the_release_report_carries_the_builder_route(tmp_path, monkeypatch):
    monkeypatch.setattr(work.change_cost, "route_split", lambda **_k: (_ for _ in ()).throw(
        work.change_cost.CostError("no transcript")))
    state = with_pull_request(stored(tmp_path, *PLANNED))
    state.holder_root = tmp_path
    first = received(state, tmp_path, timeout_seconds=30000.0, override_reason="a long change")
    launch(state, "artifact", 6)
    resumed = launch(state, "stretch", 40, handoff={"resume_of": first, "timeout_seconds": 30000.0,
                                                     "send_back": {"timeout_seconds": 7200.0,
                                                                   "override_reason": "a wide fix"}})
    caught = launch(state, "stretch", 60, handoff={"resume_of": resumed, "catch_up_resume": {}})
    post(state, readiness_record(first), 30)
    post(state, f"<!-- tradecraft:send-back:v1 dispatch={resumed} -->\n\nPoint 1.\n", 35)
    post(state, readiness_record(resumed), 50)
    post(state, readiness_record(caught), 70)
    report = work._builder_route_report(state)
    assert report["route"]["name"] == "builder" and report["readiness"]["dispatch"] == caught
    assert report["send_back"] == {"count": 1, "marker": "305", "second_ready_head": "a" * 40}
    assert [(entry["stage"], entry["override_reason"]) for entry in report["limits"]] == [
        ("handoff", "a long change"), ("send-back", "a wide fix")]
    assert [entry["dispatch"] for entry in report["catch_up_resumes"]] == [caught]
    assert len(report["plan_writer_launches"]) == 1 and report["stretch_outcome"] == "success"
    assert report["cost_split"]["builder"]["status"] == "unknown"
    assert report["hand_record"] is None and report["refusals"]["stretch"] == []
    rows = {entry["check"]: entry["reading"] for entry in report["row_checks"]}
    assert rows["2.1"] == "holds" and rows["2.3"] == "fails" and rows["4.2"] == "holds"


@pytest.mark.parametrize("stage", ["send-back", "catch-up"])
def test_1011_a_resume_above_its_default_needs_an_override_reason(stage):
    above = SimpleNamespace(stage=stage, timeout_seconds=3601.0, budget_override_reason=None)
    with pytest.raises(work.RouteRefused, match="limit-above-default.*--budget-override-reason"):
        work._resume_limit(above)
    assert work._resume_limit(SimpleNamespace(stage=stage, timeout_seconds=7200.0,
                                              budget_override_reason="a long merge")) == 7200.0


class Failing(Recorder):
    def post(self, endpoint, payload):
        raise work.WorkError("502")


def test_1011_each_resume_is_reported_once_and_a_send_back_is_spent_by_its_launch(
        tmp_path, monkeypatch, holder, quiet_report, no_spawn):
    state, first = ready_hand(tmp_path, monkeypatch, holder)
    state.synchronization = {**CLEAR, "behind": True, "strict": True, "base": {"sha": "c" * 40}}
    assert run(monkeypatch, holder, state, "catch-up", "--timeout-seconds", "7200",
               "--budget-override-reason", "a long merge") == 0
    [caught] = [request["dispatch_id"] for request in hand_requests() if request != first]
    post(state, readiness_record(caught), 40)
    work._complete_readied_hand_records(state)
    state.synchronization = dict(CLEAR)
    assert run(monkeypatch, holder, state, "send-back", "--dispatch", words(tmp_path), transport=Failing()) == 1
    [sent] = [request for request in hand_requests() if request["dispatch_id"] not in (first["dispatch_id"], caught)]
    assert "catch_up_resume" not in sent["handoff"]
    assert refused(monkeypatch, holder, state, "send-back", "--dispatch",
                   words(tmp_path, "Point 9.")) == "send-back-text-differs"
    transport = Recorder()
    assert run(monkeypatch, holder, state, "send-back", "--dispatch", words(tmp_path), transport=transport) == 0
    assert len(hand_requests()) == 3 and f"dispatch={sent['dispatch_id']} -->" in transport.posted[0][1]
    report = work._builder_route_report(state)
    assert [(entry["dispatch"], entry["base"]) for entry in report["catch_up_resumes"]] == [(caught, "c" * 40)]
    assert [entry["stage"] for entry in report["limits"]] == ["catch-up"]


def test_1011_a_clean_ready_report_is_the_final_pass_until_the_release_report(
        tmp_path, monkeypatch, holder, quiet_report, no_spawn, capsys):
    state, first = ready_hand(tmp_path, monkeypatch, holder)
    proof = work._current_marker
    monkeypatch.setattr(work, "_current_marker", lambda s, name, **k: name == "proof" or proof(s, name, **k))
    monkeypatch.setattr(work, "_release_gate_status", lambda *_a: {"verdict": "none", "reason": "none",
                                                                   "head": None, "requirement_known": True})
    monkeypatch.setattr(work, "_merge_readiness", lambda *_a: {"reason": "ready", "detail": "", "ready": True})
    state.proof_current = None  # the run above found no proof policy to compare
    made = work.decide(state, RULES)
    assert (made.stage, made.reason, json.loads(made.detail)["send_back_spent"]) == (
        "final-pass", "ready-reported", False)
    assert work._governing_terms_decision(state) is None
    transport = Recorder()
    assert run(monkeypatch, holder, state, "send-back", "--dispatch", words(tmp_path), transport=transport) == 0
    [sent] = [request for request in hand_requests() if request["dispatch_id"] != first["dispatch_id"]]
    post(state, transport.posted[0][1], 40)
    post(state, readiness_record(sent["dispatch_id"]), 50)
    work._complete_readied_hand_records(state)
    assert json.loads(work.decide(state, RULES).detail)["send_back_spent"] is True
    assert refused(monkeypatch, holder, state, "send-back", "--dispatch", words(tmp_path)) == "send-back-spent"
    capsys.readouterr()
    assert work.execute_stage(state, work.Decision("release-report", False, None, "holder-named-stage"),
                              holder, None) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["stage"] == "release-report" and report["builder_route"]["send_back"]["count"] == 1
    monkeypatch.setattr(work, "_term_stretches", lambda _s: [{"handoff": {"brief_comment": "999"}}])
    assert work._governing_terms_decision(state).reason == "governing-record-not-handed"


def test_1011_a_ready_builder_is_resumed_only_by_the_send_back_or_a_catch_up(
        tmp_path, monkeypatch, holder, quiet_report, no_spawn):
    state, _first = ready_hand(tmp_path, monkeypatch, holder)
    for synchronization, way in ((CLEAR, "run send-back"), ({**CLEAR, "behind": True, "strict": True}, "run catch-up")):
        state.synchronization = dict(synchronization)
        with pytest.raises(work.WorkError, match="^builder-not-stopped: .*" + way):
            run(monkeypatch, holder, state, "handoff", "--resume-reason", "more")
    assert len(hand_requests()) == 1


def test_1011_no_holder_usage_record_reads_the_holder_unknown(tmp_path):
    state = with_pull_request(stored(tmp_path, *PLANNED))
    state.holder_root = tmp_path
    received(state, tmp_path)
    split = work._builder_route_report(state)["cost_split"]
    assert all(split[name]["status"] == "unknown" and "no holder usage record" in split[name]["reason"]
               for name in ("holder_before", "holder_after"))

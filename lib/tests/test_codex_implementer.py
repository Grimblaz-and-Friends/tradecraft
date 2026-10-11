"""Native turn correlation, source returns and honest usage without a model."""
from argparse import Namespace
import io
import json

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import codex_implementer as native
import implementer_environment as env

SESSION = "0199a213-81c0-7800-8aa1-bbab2a035a53"
TURN = "0199a214-81c0-7800-8aa1-bbab2a035a53"


def turn(tmp_path, resume=None, *, acknowledge_turn=True):
    observed = []
    transcript = io.BytesIO()
    instance = native.NativeTurn(args=Namespace(root=tmp_path, resume=resume, model="model", effort="high"),
        prompt="Exactly one stage.\nSource text.".encode(), intent={"thread_config": {"mcp_servers": {"foreign.server": {"enabled": False}}},
            "disabled_plugin_ids": ["foreign@market"], "allowed_plugins": []},
        environment=env.unknown("not observed"), stdout_path=tmp_path / "stdout",
        observe=lambda *v: observed.append(v), transcript=transcript)
    responses = [{"id": 1, "result": {}}, {"id": 2, "result": {
        "thread": {"id": SESSION}, "instructionSources": ["/owner/AGENTS.md"]}}]
    if acknowledge_turn:
        responses.append({"id": 3, "result": {"turn": {"id": TURN}}})
    for value in responses:
        instance.output("stdout", native.encode(value))
    return instance, observed, transcript


def event(instance, method, *, turn_id=TURN, **params):
    instance.output("stdout", native.encode({"method": method,
        "params": {"threadId": SESSION, "turnId": turn_id, **params}}))


@pytest.mark.parametrize("resume", [None, SESSION])
def test_exact_start_resume_frozen_prompt_and_every_turn_exclusion(tmp_path, resume):
    instance, observed, transcript = turn(tmp_path, resume)
    requests = [json.loads(line) for line in transcript.getvalue().splitlines()]
    start = requests[2]
    assert start["method"] == ("thread/resume" if resume else "thread/start")
    assert start["params"]["config"]["mcp_servers"] == {"foreign.server": {"enabled": False}}
    assert start["params"]["approvalsReviewer"] == "auto_review"
    if resume:
        assert start["params"]["threadId"] == resume
    assert requests[3]["method"] == "turn/start"
    assert requests[3]["params"]["disabledPluginIds"] == ["foreign@market"]
    assert requests[3]["params"]["input"] == [{"type": "text", "text": "Exactly one stage.\nSource text.", "text_elements": []}]
    assert observed == [(SESSION, f"Codex native {start['method']} response.thread.id")]


def test_completion_after_transient_error_uses_current_last_message_and_total(tmp_path):
    instance, _, _ = turn(tmp_path)
    event(instance, "item/completed", turn_id="historical", item={"type": "agentMessage", "text": "old"})
    event(instance, "thread/tokenUsage/updated", turn_id="historical", tokenUsage={"total": {"inputTokens": 9000}})
    event(instance, "error", error={"message": "reconnecting"})
    event(instance, "item/completed", item={"type": "agentMessage", "text": "first"})
    event(instance, "item/completed", item={"type": "agentMessage", "text": "whole\nreturn"})
    event(instance, "thread/tokenUsage/updated", tokenUsage={"total": {"inputTokens": 10, "outputTokens": 20, "specialTokens": 3},
        "last": {"inputTokens": 1}})
    event(instance, "thread/tokenUsage/updated", tokenUsage={"total": {"inputTokens": 30, "outputTokens": 40, "specialTokens": 5},
        "last": {"inputTokens": 2}})
    event(instance, "turn/completed", turn={"id": TURN, "status": "completed"})
    assert instance.valid and instance.completed and instance.final_message == "whole\nreturn"
    assert instance.evidence("fresh")["normalized"] == {"scope": "invocation", "input_tokens": 30, "output_tokens": 40}
    assert instance.evidence("fresh")["additional_native_classes"] == {"specialTokens": 5}
    assert instance.evidence("resume")["normalized"] is None


@pytest.mark.parametrize("status", ["failed", "interrupted", "inProgress"])
def test_failed_terminal_status_does_not_publish_success(tmp_path, status):
    instance, _, _ = turn(tmp_path)
    event(instance, "turn/completed", turn={"id": TURN, "status": status})
    assert not instance.completed and instance.error


def test_malformed_partial_eof_keeps_observed_identity(tmp_path):
    instance, observed, _ = turn(tmp_path)
    instance.output("stdout", b'{"method":')
    instance.finish()
    assert not instance.valid and not instance.completed
    assert instance.session == SESSION and observed
    assert instance.environment["categories"]["instructions"]["values"] == [{"path": "/owner/AGENTS.md"}]


@pytest.mark.parametrize("resume", [None, SESSION])
def test_startup_instructions_survive_failure_before_current_turn_acknowledgement(tmp_path, resume):
    instance, _, _ = turn(tmp_path, resume, acknowledge_turn=False)
    instance.output("stdout", native.encode({"id": 3, "error": {"message": "failed turn startup"}}))
    instance.finish()
    assert not instance.valid and instance.session == SESSION and instance.turn is None
    instructions = instance.environment["categories"]["instructions"]
    assert instructions["status"] == "partial"
    assert instructions["values"] == [{"path": "/owner/AGENTS.md"}]
    assert instructions["sources"] == [{"path": str(tmp_path / "stdout"), "line": 2,
        "field": "result.instructionSources"}]


@pytest.mark.parametrize("sources", [None, {"unsupported": True}, True, [None]])
def test_optional_startup_observation_shape_does_not_refuse_a_valid_turn(tmp_path, sources):
    instance = native.NativeTurn(args=Namespace(root=tmp_path, resume=None, model="model", effort="low"),
        prompt=b"One stage", intent={"thread_config": {}, "disabled_plugin_ids": [], "allowed_plugins": []},
        environment=env.unknown("not reported"), stdout_path=tmp_path / "stdout")
    for value in ({"id": 1, "result": {}}, {"id": 2, "result": {
            "thread": {"id": SESSION, "path": {"unsupported": True}}, "instructionSources": sources}},
            {"id": 3, "result": {"turn": {"id": TURN}}}):
        instance.output("stdout", native.encode(value))
    event(instance, "item/completed", item={"type": "agentMessage", "text": "valid return"})
    event(instance, "turn/completed", turn={"id": TURN, "status": "completed"})
    assert instance.valid and instance.completed and instance.final_message == "valid return"
    assert instance.environment["categories"]["instructions"]["status"] == "unknown"


def test_unsupported_person_request_returns_error_never_approval(tmp_path):
    instance, _, transcript = turn(tmp_path)
    instance.output("stdout", native.encode({"id": "approval-1", "method": "item/commandExecution/requestApproval", "params": {}}))
    reply = json.loads(transcript.getvalue().splitlines()[-1])
    assert reply["id"] == "approval-1" and "error" in reply and "result" not in reply
    assert not instance.valid and instance.input.closed


def test_historical_terminal_and_missing_message_are_distinct(tmp_path):
    instance, _, _ = turn(tmp_path)
    event(instance, "turn/completed", turn={"id": "historical", "status": "completed"})
    assert not instance.completed
    event(instance, "turn/completed", turn={"id": TURN, "status": "completed"})
    assert instance.completed and instance.final_message is None


def test_native_resume_identity_mismatch_stops_before_turn(tmp_path):
    instance, observed, transcript = turn(tmp_path, "0299a213-81c0-7800-8aa1-bbab2a035a53")
    assert not instance.valid and instance.session == SESSION and observed
    assert not any(json.loads(v).get("method") == "turn/start" for v in transcript.getvalue().splitlines())


@pytest.mark.parametrize("malformed", [{"id": 99, "result": None},
    {"method": "turn/completed", "params": None},
    {"method": "item/completed", "params": {"threadId": SESSION, "turnId": TURN, "item": None}}])
def test_malformed_native_shapes_do_not_escape_or_erase_identity(tmp_path, malformed):
    instance, observed, _ = turn(tmp_path)
    instance.output("stdout", native.encode(malformed))
    assert not instance.valid and instance.session == SESSION and observed


def test_unsupported_token_shape_stays_raw_and_usage_unknown(tmp_path):
    instance, _, _ = turn(tmp_path)
    event(instance, "thread/tokenUsage/updated", tokenUsage={"total": []})
    evidence = instance.evidence("fresh")
    assert evidence["raw"] == {"total": []} and evidence["normalized"] is None


def test_record_parser_requires_explicit_native_format_and_preserves_exec_default(tmp_path):
    import dispatch_record as records
    instance, _, _ = turn(tmp_path)
    event(instance, "item/completed", item={"type": "agentMessage", "text": "native return"})
    event(instance, "turn/completed", turn={"id": TURN, "status": "completed"})
    raw = b"".join(native.encode(e) for e in instance.events)
    native_result = records.codex_stream_result(raw, source_format="app-server")
    assert native_result.valid and native_result.completed and native_result.final_message == "native return"
    assert records.codex_stream_result(raw, source_format="codex-app-server-v2").completed
    assert not records.codex_stream_result(raw).completed
    old = b'{"type":"turn.completed","usage":{"input_tokens":3}}\n'
    assert records.codex_stream_result(old).completed
    assert not records.codex_stream_result(old, source_format="app-server").completed
    malformed = raw + native.encode({"method": "turn/completed", "params": None})
    assert not records.codex_stream_result(malformed, source_format="app-server").valid

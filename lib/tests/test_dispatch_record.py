import argparse
import json
from pathlib import Path
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import dispatch_record as records


NATIVE_SOURCES = {
    "vendor_source": "native route",
    "model_source": "fixture settings",
    "effort_source": "fixture settings",
    "classification_source": "fixture role",
    "continuity_source": "native route (fresh)",
    "permission_boundary_source": "native route",
}


def request_values(**changes):
    values = {
        "dispatch_id": "builder-dispatch", "work": "issue", "stage": "build",
        "settings_source": "fixture", "settings_scope": "build", "vendor": "codex",
        "model": "model", "effort": "xhigh", "continuity": "fresh",
        "permission_boundary": "workspace-write", "root": None,
    }
    values.update(changes)
    return values


def test_holder_identity_cannot_also_identify_dispatch_or_resumed_builder():
    with pytest.raises(records.RecordError, match="dispatch id cannot also identify"):
        records.request_record(**request_values(holder_session_id="builder-dispatch"))
    with pytest.raises(records.RecordError, match="builder session cannot also identify"):
        records.request_record(**request_values(
            continuity="resume", requested_session_id="holder-session",
            holder_session_id="holder-session",
        ))


def test_request_records_work_and_shared_producer_version():
    request = records.request_record(**request_values())
    assert request["work"] == "issue"
    assert request["producer_version"] == records.producer_version()


def test_claude_usage_keeps_models_while_money_stays_out_of_observed_usage():
    payload = {
        "type": "result", "is_error": False, "subtype": "success",
        "total_cost_usd": 1.25,
        "modelUsage": {
            "claude-opus-5": {
                "inputTokens": 100, "cacheReadInputTokens": 80,
                "cacheCreationInputTokens": 10, "outputTokens": 20,
            },
            "claude-fable-5": {"inputTokens": 5, "outputTokens": 2},
        },
    }
    evidence = records.runtime_evidence("claude", json.dumps(payload).encode(), "fresh")
    assert evidence["reported_models"] == ["claude-fable-5", "claude-opus-5"]
    assert evidence["normalized"]["models"]["claude-opus-5"] == {
        "inputTokens": 100, "cacheReadInputTokens": 80,
        "cacheCreationInputTokens": 10, "outputTokens": 20,
    }
    assert "runtime_cost" not in evidence
    assert "total" not in evidence["normalized"]


def test_missing_usage_is_unknown_rather_than_zero():
    evidence = records.runtime_evidence(
        "codex", b'{"type":"turn.completed"}\n', "fresh"
    )
    assert evidence["normalized"] is None
    assert evidence["raw"] == []
    assert "no turn.completed usage" in evidence["normalized_unavailable_reason"]


def test_codex_stream_result_keeps_recovered_errors_and_last_agent_message():
    raw = b"\n".join((
        b'{"type":"error","message":"reconnecting"}',
        b'{"type":"item.completed","item":{"type":"agent_message","text":"first"}}',
        b'{"type":"item.completed","item":{"type":"agent_message","text":"final"}}',
        b'{"type":"turn.completed"}',
    ))
    result = records.codex_stream_result(raw)
    assert result.valid is True
    assert result.completed is True
    assert result.failed_events == ()
    assert len(result.error_events) == 1
    assert result.final_message == "final"
    evidence = records.runtime_evidence("codex", raw, "fresh")
    assert evidence["recovered_error_count"] == 1


@pytest.mark.parametrize("raw", [b"not-json\n", b'{"type":"turn.failed"}\n'])
def test_codex_stream_result_does_not_complete_invalid_or_failed_streams(raw):
    result = records.codex_stream_result(raw)
    assert not (result.valid and result.completed and not result.failed_events)


def test_claude_resume_usage_keeps_its_scope_unestablished():
    payload = {
        "type": "result", "total_cost_usd": 1.25,
        "modelUsage": {"opus": {"inputTokens": 100, "outputTokens": 20}},
    }
    evidence = records.runtime_evidence("claude", json.dumps(payload).encode(), "resume")
    assert evidence["raw"] == payload["modelUsage"]
    assert evidence["normalized"] is None
    assert "resume usage scope is not established" in evidence["normalized_unavailable_reason"]
    assert "runtime_cost" not in evidence


def test_native_claude_usage_keeps_the_returned_model_and_tokens():
    payload = {
        "type": "result", "model": "claude-opus-5", "total_cost_usd": 1.8841,
        "usage": {
            "input_tokens": 8, "cache_read_input_tokens": 5,
            "cache_creation_input_tokens": 2, "output_tokens": 3,
        },
    }
    evidence = records.runtime_evidence("claude", json.dumps(payload).encode(), "fresh")
    assert evidence["reported_models"] == ["claude-opus-5"]
    assert evidence["normalized"] == {
        "scope": "invocation",
        "models": {"claude-opus-5": payload["usage"]},
    }
    assert "runtime_cost" not in evidence


def test_git_revision_timeout_is_unknown(monkeypatch, tmp_path):
    monkeypatch.setattr(
        records.subprocess, "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired(["git", "rev-parse"], 20)
        ),
    )
    assert records.git_revision(tmp_path) is None


def test_native_begin_records_unavailable_input_and_launch_time(tmp_path):
    output = tmp_path / "result.md"
    args = records.parser().parse_args([
        "begin", "--work", "issue", "--stage", "experience",
        "--settings-source", "mixed sources", "--settings-scope", "this dispatch",
        "--vendor", "claude", "--vendor-source", "native route",
        "--model", "claude-opus-5", "--model-source", "owner issue choice",
        "--effort", "xhigh", "--effort-source", "ordinary effort default",
        "--classification", "ordinary", "--classification-source", "experience route",
        "--continuity-source", "native route (fresh)",
        "--permission-boundary", "native tool", "--permission-boundary-source", "native route",
        "--input-unavailable-reason", "source dispatcher did not expose the exact input",
        "--launched-at-unavailable-reason", "source dispatcher did not expose launch time",
        "--output", str(output),
    ])
    records.begin_native(args)
    request = json.loads(records.sidecar(output, ".request.json").read_bytes())
    assert request["input"] is None
    assert request["input_unavailable_reason"] == "source dispatcher did not expose the exact input"
    assert request["launched_at"] is None
    assert request["launched_at_unavailable_reason"] == "source dispatcher did not expose launch time"
    assert request["recorded_at"]
    assert not records.sidecar(output, ".dispatch.bin").exists()
    assert request["requested"]["sources"] == {
        "vendor": "native route",
        "model": "owner issue choice",
        "effort": "ordinary effort default",
        "classification": "experience route",
        "continuity": "native route (fresh)",
        "permission_boundary": "native route",
    }


def test_native_begin_finish_and_attachment_survive_source_removal(tmp_path):
    output = tmp_path / "store" / "result.md"
    recipient = tmp_path / "recipient"
    recipient.mkdir()
    begin = argparse.Namespace(
        output=output, work="issue-592", stage="experience", settings_source="default",
        settings_scope="the experience dispatch",
        vendor="claude", model="opus", effort="xhigh", continuity="fresh",
        classification="ordinary", session_id=None, permission_boundary="native tool",
        root=recipient, retry_of=None, runtime_version="native fixture 1.0",
        input_file=tmp_path / "dispatch.md", input_unavailable_reason=None,
        launched_at=None, launched_at_unavailable_reason=None,
        **NATIVE_SOURCES,
    )
    begin.input_file.write_bytes(b"Use the result as its consumer.\n")
    assert records.begin_native(begin) == output.absolute()
    request = json.loads(records.sidecar(output, ".request.json").read_bytes())
    assert request["requested"]["effort"] == "xhigh"
    assert request["runtime_version"] == "native fixture 1.0"
    assert records.sidecar(output, ".dispatch.bin").read_bytes() == begin.input_file.read_bytes()
    returned = tmp_path / "tool-return.json"
    returned.write_bytes(json.dumps({
        "type": "result", "modelUsage": {"opus": {"inputTokens": 4}},
        "total_cost_usd": 0.02,
    }).encode())
    final = tmp_path / "final.md"
    final.write_bytes(b"consumer result\n")
    finish = argparse.Namespace(
        output=output, vendor="claude", return_file=returned,
        final_file=final, outcome="success", elapsed_seconds=214.773,
        elapsed_unavailable_reason=None,
    )
    run_path = records.finish_native(finish)
    returned.unlink()
    final.unlink()
    assert output.read_bytes() == b"consumer result\n"
    run = json.loads(run_path.read_bytes())
    assert "runtime_cost" not in run["attempts"][0]["observed"]
    assert b'"total_cost_usd": 0.02' in Path(run["attempts"][0]["source_return"]).read_bytes()
    assert run["schema_version"] == 2
    assert run["attempts"][0]["usage"]["runtime_version"] == "native fixture 1.0"
    assert run["attempts"][0]["elapsed_seconds"] == 214.773
    assert Path(run["result"]["source_output"]).read_bytes() == b"consumer result\n"
    product = tmp_path / "uncommitted-artifact.md"
    product.write_bytes(b"draft bytes\n")
    metadata = records.attach_file(output, product, "product")
    product.unlink()
    attachment = json.loads(metadata.read_bytes())
    assert Path(attachment["content"]).read_bytes() == b"draft bytes\n"
    assert attachment["bytes"] == len(b"draft bytes\n")


def test_native_completion_refuses_to_overwrite(tmp_path):
    output = tmp_path / "result.md"
    output.write_bytes(b"existing")
    args = argparse.Namespace(
        output=output, work="issue", stage="stage", settings_source="default",
        settings_scope="stage",
        vendor="tool", model="model", effort="effort", continuity="fresh",
        classification=None, session_id=None, permission_boundary="read-only", root=None,
        retry_of=None, runtime_version=None, input_file=tmp_path / "dispatch.md",
        input_unavailable_reason=None, launched_at=None,
        launched_at_unavailable_reason=None, **NATIVE_SOURCES,
    )
    args.input_file.write_bytes(b"dispatch")
    with pytest.raises(records.RecordError, match="refusing existing"):
        records.begin_native(args)


def _native_job(tmp_path, outcome):
    output = tmp_path / f"{outcome}.md"
    dispatch = tmp_path / f"{outcome}-dispatch.md"
    dispatch.write_bytes(b"dispatch")
    begin = argparse.Namespace(
        output=output, work="issue", stage="stage", settings_source="explicit fixture",
        settings_scope="stage", vendor="claude", model="opus", effort="xhigh",
        continuity="fresh", classification="ordinary", session_id=None,
        permission_boundary="native tool", root=None, retry_of=None,
        runtime_version="fixture", input_file=dispatch, input_unavailable_reason=None,
        launched_at=None, launched_at_unavailable_reason=None, **NATIVE_SOURCES,
    )
    records.begin_native(begin)
    returned = tmp_path / f"{outcome}-return.json"
    returned.write_bytes(b'{"type":"result","modelUsage":{"opus":{"inputTokens":1}}}')
    final = tmp_path / f"{outcome}-final.md"
    final.write_bytes(b"consumer result\n")
    finish = argparse.Namespace(
        output=output, vendor="claude", return_file=returned,
        final_file=final, outcome=outcome, elapsed_seconds=None,
        elapsed_unavailable_reason="fixture returned no duration",
    )
    return output, finish


@pytest.mark.parametrize("outcome,launched", [("error", True), ("unavailable", False)])
def test_native_failed_completion_retains_return_without_publishing(tmp_path, outcome, launched):
    output, finish = _native_job(tmp_path, outcome)
    run_path = records.finish_native(finish)
    run = json.loads(run_path.read_bytes())
    attempt = run["attempts"][0]
    assert attempt["launched"] is launched
    assert Path(attempt["source_return"]).read_bytes().startswith(b'{"type":"result"')
    assert run["result"]["source_output"] is None
    assert run["result"]["published_output"] is None
    assert not output.exists()
    assert not records.sidecar(output, ".source.bin").exists()
    if not launched:
        assert attempt["observed"]["normalized"] is None
        assert "runtime_cost" not in attempt["observed"]
        assert attempt["usage"]["tokens"] is None


def test_native_finish_refuses_collisions_after_a_successful_begin(tmp_path):
    output, finish = _native_job(tmp_path, "success")
    collision = records.sidecar(output, ".run.json")
    collision.write_bytes(b"existing completion")
    with pytest.raises(records.RecordError, match="colliding dispatch output"):
        records.finish_native(finish)
    assert collision.read_bytes() == b"existing completion"


def test_native_begin_reserves_source_output_before_dispatch(tmp_path):
    output = tmp_path / "result.md"
    source = records.sidecar(output, ".source.bin")
    source.write_bytes(b"earlier source")
    dispatch = tmp_path / "dispatch.md"
    dispatch.write_bytes(b"dispatch")
    begin = argparse.Namespace(
        output=output, work="issue", stage="stage", settings_source="fixture",
        settings_scope="stage", vendor="claude", model="opus", effort="xhigh",
        continuity="fresh", classification="ordinary", session_id=None,
        permission_boundary="native tool", root=None, retry_of=None,
        runtime_version="fixture", input_file=dispatch, input_unavailable_reason=None,
        launched_at=None, launched_at_unavailable_reason=None, **NATIVE_SOURCES,
    )
    with pytest.raises(records.RecordError, match="refusing existing"):
        records.begin_native(begin)
    assert source.read_bytes() == b"earlier source"
    assert not records.sidecar(output, ".request.json").exists()


def test_native_publication_failure_is_recorded_without_a_false_path(tmp_path, monkeypatch):
    output, finish = _native_job(tmp_path, "success")
    monkeypatch.setattr(
        records, "publish_output",
        lambda *_args: (_ for _ in ()).throw(OSError("hard link failed")),
    )
    with pytest.raises(OSError, match="hard link failed"):
        records.finish_native(finish)
    run = json.loads(records.sidecar(output, ".run.json").read_bytes())
    assert run["outcome"] == "error"
    assert run["attempts"][0]["outcome"] == "success"
    assert run["result"]["published_output"] is None
    assert "hard link failed" in run["result"]["published_output_unavailable_reason"]
    assert not output.exists()


def test_attachment_uuid_does_not_need_an_unreachable_existence_guard(monkeypatch, tmp_path):
    output, finish = _native_job(tmp_path, "success")
    records.finish_native(finish)
    source = tmp_path / "attachment.md"
    source.write_bytes(b"attachment")
    monkeypatch.setattr(records.uuid, "uuid4", lambda: type("Fixed", (), {"hex": "a" * 32})())
    metadata = records.attach_file(output, source, "product")
    assert metadata.is_file()


def test_native_output_inside_recipient_root_is_rejected(tmp_path):
    recipient = tmp_path / "recipient"
    recipient.mkdir()
    dispatch = tmp_path / "dispatch.md"
    dispatch.write_bytes(b"dispatch")
    args = argparse.Namespace(
        output=recipient / "result.md", work="issue", stage="stage",
        settings_source="default", settings_scope="stage", vendor="tool",
        model="model", effort="effort", continuity="fresh", classification=None,
        session_id=None, permission_boundary="native tool", root=recipient,
        retry_of=None, runtime_version=None, input_file=dispatch,
        input_unavailable_reason=None, launched_at=None,
        launched_at_unavailable_reason=None, **NATIVE_SOURCES,
    )
    with pytest.raises(records.RecordError, match="outside the recipient root"):
        records.begin_native(args)

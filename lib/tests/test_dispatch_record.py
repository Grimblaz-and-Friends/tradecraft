import argparse
import json
from pathlib import Path
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import dispatch_record as records


def test_claude_usage_keeps_models_and_returned_cost_without_double_counting():
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
    assert evidence["runtime_cost"] == {
        "currency": "USD", "amount": 1.25, "source": "total_cost_usd"
    }
    assert "total" not in evidence["normalized"]


def test_missing_usage_is_unknown_rather_than_zero():
    evidence = records.runtime_evidence(
        "codex", b'{"type":"turn.completed"}\n', "fresh"
    )
    assert evidence["normalized"] is None
    assert evidence["raw"] == []
    assert "no turn.completed usage" in evidence["normalized_unavailable_reason"]


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
        input_file=tmp_path / "dispatch.md",
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
        final_file=final, outcome="success",
    )
    run_path = records.finish_native(finish)
    returned.unlink()
    final.unlink()
    assert output.read_bytes() == b"consumer result\n"
    run = json.loads(run_path.read_bytes())
    assert run["attempts"][0]["observed"]["runtime_cost"]["amount"] == 0.02
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
    )
    args.input_file.write_bytes(b"dispatch")
    with pytest.raises(records.RecordError, match="refusing existing"):
        records.begin_native(args)


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
    )
    with pytest.raises(records.RecordError, match="outside the recipient root"):
        records.begin_native(args)

import json
from pathlib import Path
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import dispatch_implementer as implementer
import vendor_cli


@pytest.fixture
def job(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    root = tmp_path / "root with spaces"
    root.mkdir()
    dispatch = tmp_path / "dispatch.md"
    dispatch.write_bytes(b"Build the settled artifact and report the result.\n")
    scenario = tmp_path / "scenario.json"
    scenario.write_bytes(b"{}")
    output = tmp_path / "records" / "result.md"
    args = implementer.parser().parse_args([
        "--dispatch", str(dispatch), "--root", str(root),
        "--work", "issue-592", "--stage", "build",
        "--settings-source", "issuecomment-5655702442",
        "--settings-scope", "Codex turns after the artifact",
        "--output", str(output), "--timeout-seconds", "10",
    ])
    monkeypatch.setattr(
        implementer, "resolve_command",
        lambda *_: [sys.executable, str(LIB / "tests/seat_cli.py"), "codex", str(scenario)],
    )
    monkeypatch.setattr(implementer.records, "runtime_version", lambda *_: "codex-cli test")
    return args, scenario


def configure(job, value):
    job[1].write_bytes(json.dumps({"codex": value}).encode("utf-8"))


def record(args):
    return json.loads(implementer.records.sidecar(args.output, ".run.json").read_bytes())


def seen(args):
    return json.loads((args.root / "seen-codex.json").read_bytes())


def success_events(session_id="0199a213-81c0-7800-8aa1-bbab2a035a53"):
    return "\n".join((
        json.dumps({"type": "thread.started", "thread_id": session_id}),
        json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 120, "cached_input_tokens": 80,
            "output_tokens": 12, "reasoning_output_tokens": 3,
        }}),
    ))


def test_fresh_launch_is_recorded_and_resumable(job):
    args, _ = job
    configure(job, {"stdout": success_events(), "message": "built\n"})
    assert implementer.run_implementer(args) == 0
    flags = seen(args)["argv"]
    assert flags[:3] == ["exec", "--approve-for-me", "--json"]
    assert "--ephemeral" not in flags
    assert "--sandbox" not in flags
    assert "--last" not in flags
    assert "resume" not in flags
    assert flags[-1] == "-"
    assert flags[flags.index("--model") + 1] == "gpt-6.1-sol"
    assert 'model_reasoning_effort="xhigh"' in flags
    logged = record(args)
    attempt = logged["attempts"][0]
    assert logged["outcome"] == "success"
    assert attempt["observed"]["session_id"] == "0199a213-81c0-7800-8aa1-bbab2a035a53"
    assert attempt["observed"]["normalized"] == {
        "scope": "invocation", "input_tokens": 120, "cached_input_tokens": 80,
        "output_tokens": 12, "reasoning_output_tokens": 3,
    }
    assert attempt["usage"]["tokens"] == {
        "input": 120, "cached_input": 80, "output": 12, "reasoning_output": 3,
    }
    assert attempt["usage"]["scope"] == "invocation"
    assert attempt["usage"]["dispatch"]["staffing_status"] == "qualified"
    request = json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())
    assert request["work"] == "issue-592"
    assert request["producer_version"] == implementer.records.producer_version()
    assert request["runtime_version"] == "codex-cli test"
    assert request["settings_source"] == "issuecomment-5655702442"
    assert args.output.read_bytes() == b"built\n"
    assert Path(logged["result"]["source_output"]).read_bytes() == b"built\n"


def test_direct_fresh_launch_reads_machine_vendor_and_records_its_source(job, tmp_path, monkeypatch):
    args, scenario = job
    home = tmp_path / "home"
    setting = home / ".tradecraft" / "implementer-vendor"
    setting.parent.mkdir(parents=True)
    setting.write_bytes(b"claude\n")
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(
        implementer, "resolve_command",
        lambda vendor, _path: [sys.executable, str(LIB / "tests/seat_cli.py"), vendor, str(scenario)],
    )
    session = "f0cb89b1-e040-4e6e-919b-4b4e58c717d2"
    scenario.write_bytes(json.dumps({"claude": {"stdout": json.dumps({
        "type": "result", "subtype": "success", "is_error": False,
        "session_id": session, "result": "built on Claude",
    })}}).encode())

    assert implementer.run_implementer(args) == 0
    request = json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())
    assert request["requested"]["vendor"] == "claude"
    assert request["requested"]["sources"]["vendor"] == f"machine file {setting}: claude"
    assert request["requested"]["model"] == "claude-opus-5-5"
    assert record(args)["actual_vendor"] == "claude"
    assert args.output.read_bytes() == b"built on Claude"


def test_direct_explicit_vendor_wins_but_invalid_machine_file_refuses(job, tmp_path, monkeypatch):
    args, _scenario = job
    home = tmp_path / "home"
    setting = home / ".tradecraft" / "implementer-vendor"
    setting.parent.mkdir(parents=True)
    setting.write_bytes(b"claude\n")
    monkeypatch.setattr(Path, "home", lambda: home)
    args.vendor = "codex"
    configure(job, {"stdout": success_events(), "message": "built\n"})
    assert implementer.run_implementer(args) == 0
    request = json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())
    assert request["requested"]["vendor"] == "codex"
    assert request["requested"]["sources"]["vendor"] == "explicit --vendor codex"

    args.output = tmp_path / "records" / "invalid.md"
    setting.write_bytes(b"CLAUDE\n")
    with pytest.raises(implementer.ImplementerError, match="implementer vendor setting"):
        implementer.run_implementer(args)
    assert not list(args.output.parent.glob("invalid.md*"))


def test_direct_resume_requires_the_recorded_vendor_before_reserving_output(job):
    args, _ = job
    args.resume = "0199a213-81c0-7800-8aa1-bbab2a035a53"
    with pytest.raises(implementer.ImplementerError, match="direct resume requires --vendor"):
        implementer.run_implementer(args)
    assert not args.output.parent.exists()


def test_reconnect_uses_stream_message_and_keeps_success_reason_empty(job):
    args, _ = job
    stdout = "\n".join((
        json.dumps({"type": "thread.started", "thread_id": "0199a213-81c0-7800-8aa1-bbab2a035a53"}),
        json.dumps({"type": "error", "message": "reconnecting"}),
        json.dumps({"type": "item.completed", "item": {
            "type": "agent_message", "text": "built from stream\n",
        }}),
        json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1}}),
    ))
    configure(job, {"stdout": stdout, "message": ""})
    assert implementer.run_implementer(args) == 0
    logged = record(args)
    attempt = logged["attempts"][0]
    assert logged["outcome"] == attempt["outcome"] == "success"
    assert attempt["reason"] == ""
    assert attempt["observed"]["recovered_error_count"] == 1
    assert args.output.read_bytes() == b"built from stream\n"


def test_completed_turn_without_any_message_is_non_error_and_resumable(job):
    args, _ = job
    configure(job, {"stdout": success_events(), "message": ""})
    assert implementer.run_implementer(args) == 1
    logged = record(args)
    attempt = logged["attempts"][0]
    assert logged["outcome"] == attempt["outcome"] == "completed_no_output"
    assert attempt["reason"] == "turn completed without a final message"
    assert attempt["observed"]["session_id"]
    assert logged["result"]["source_output"] is None
    assert not args.output.exists()


def test_implementer_runs_the_shared_automatic_resolution_result(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    dispatch = tmp_path / "dispatch.md"
    dispatch.write_bytes(b"Build the settled artifact and report the result.\n")
    scenario = tmp_path / "scenario.json"
    scenario.write_bytes(json.dumps({"codex": {"stdout": success_events(), "message": "built\n"}}).encode())
    output = tmp_path / "records" / "result.md"
    args = implementer.parser().parse_args([
        "--dispatch", str(dispatch), "--root", str(root), "--work", "issue-609", "--stage", "build",
        "--settings-source", "brief", "--settings-scope", "shared resolver", "--output", str(output),
    ])
    automatic_result = [sys.executable, str(LIB / "tests/seat_cli.py"), "codex", str(scenario)]
    monkeypatch.setattr(implementer, "resolve_command", lambda *_: automatic_result)
    monkeypatch.setattr(
        vendor_cli,
        "resolve_codex",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("do not bypass shared resolution")),
    )
    monkeypatch.setattr(implementer.records, "runtime_version", lambda *_: "codex-cli test")
    assert implementer.run_implementer(args) == 0
    assert seen(args)["argv"][:3] == ["exec", "--approve-for-me", "--json"]
    assert output.read_bytes() == b"built\n"


def test_explicit_unavailable_reason_records_an_unavailable_attempt(job, monkeypatch):
    args, _ = job
    args.codex_unavailable_reason = "Codex CLI was not found by the entrance"
    monkeypatch.setattr(
        implementer, "resolve_command",
        lambda *_args, **_kwargs: pytest.fail("an unavailable runtime must not be rediscovered"),
    )

    assert implementer.run_implementer(args) == 1

    request = json.loads(
        implementer.records.sidecar(args.output, ".request.json").read_bytes()
    )
    logged = record(args)
    assert request["requested"]["command"] is None
    assert request["runtime_version"] is None
    assert request["runtime_version_unavailable_reason"] == args.codex_unavailable_reason
    assert logged["outcome"] == "unavailable"
    assert logged["attempts"][0]["outcome"] == "unavailable"
    assert logged["attempts"][0]["reason"] == args.codex_unavailable_reason
    assert logged["attempts"][0]["launched"] is False
    assert not args.output.exists()


def test_resume_names_exact_session_and_keeps_usage_scope_unknown(job):
    args, _ = job
    session = "0199a213-81c0-7800-8aa1-bbab2a035a53"
    args.resume = session
    args.vendor = "codex"
    args.model = "gpt-6-astra"
    configure(job, {"stdout": success_events(session), "message": "fixed\n"})
    assert implementer.run_implementer(args) == 0
    flags = seen(args)["argv"]
    assert flags[-3:] == ["resume", session, "-"]
    assert flags[flags.index("--model") + 1] == "gpt-6-astra"
    observed = record(args)["attempts"][0]["observed"]
    assert observed["raw"]
    assert observed["normalized"] is None
    assert "scope is not established" in observed["normalized_unavailable_reason"]


def test_resume_mismatch_is_error_and_never_publishes(job):
    args, _ = job
    args.resume = "0199a213-81c0-7800-8aa1-bbab2a035a53"
    args.vendor = "codex"
    configure(job, {
        "stdout": success_events("0299a213-81c0-7800-8aa1-bbab2a035a53"),
        "message": "wrong thread\n",
    })
    assert implementer.run_implementer(args) == 1
    assert record(args)["outcome"] == "error"
    assert not args.output.exists()


def test_holder_session_cannot_be_resumed_as_builder(job):
    args, _ = job
    args.resume = "0199a213-81c0-7800-8aa1-bbab2a035a53"
    args.vendor = "codex"
    args.holder_session_id = args.resume
    with pytest.raises(implementer.ImplementerError, match="cannot also identify"):
        implementer.run_implementer(args)
    assert not args.output.parent.exists()


def test_fresh_runtime_returning_holder_identity_is_not_published(job):
    args, _ = job
    args.holder_session_id = "0199a213-81c0-7800-8aa1-bbab2a035a53"
    configure(job, {"stdout": success_events(args.holder_session_id), "message": "wrong identity\n"})
    assert implementer.run_implementer(args) == 1
    logged = record(args)
    assert logged["outcome"] == "error"
    assert logged["attempts"][0]["observed"]["session_id"] is None
    assert not args.output.exists()


def test_completed_turn_without_identity_retains_result_but_is_not_resumable(job):
    args, _ = job
    stdout = json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1}})
    configure(job, {"stdout": stdout, "message": "useful result\n"})
    assert implementer.run_implementer(args) == 1
    assert record(args)["outcome"] == "success_uncontinuable"
    assert args.output.read_bytes() == b"useful result\n"


def test_output_inside_recipient_root_is_rejected_before_launch(job):
    args, _ = job
    args.output = args.root / "record.md"
    with pytest.raises(implementer.records.RecordError, match="outside the recipient root"):
        implementer.run_implementer(args)
    assert not (args.root / "seen-codex.json").exists()


def test_relocated_implementer_has_no_repo_only_dependency(tmp_path):
    import shutil
    import subprocess
    copied = tmp_path / "installed" / "lib"
    shutil.copytree(LIB, copied, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    result = subprocess.run(
        [sys.executable, str(copied / "dispatch_implementer.py"), "--help"],
        cwd=tmp_path, stdin=subprocess.DEVNULL, capture_output=True,
    )
    assert result.returncode == 0
    assert b"--settings-source" in result.stdout


def test_launch_failure_is_a_complete_observed_attempt(job, monkeypatch, capsys):
    args, _ = job
    monkeypatch.setattr(
        implementer, "run_process", lambda *_a, **_k: (_ for _ in ()).throw(OSError("launch broke"))
    )
    assert implementer.run_implementer(args) == 1
    logged = record(args)
    attempt = logged["attempts"][0]
    assert logged["outcome"] == "error"
    assert logged["error"] == "cannot launch codex: launch broke"
    assert attempt["launched"] is False
    assert attempt["reason"] == logged["error"]
    assert attempt["observed"]["normalized"] is None
    assert attempt["elapsed_seconds"] is None
    assert logged["result"]["published_output"] is None
    output = capsys.readouterr().out
    assert logged["dispatch_id"] in output
    assert str(args.output) in output


def test_invalid_request_leaves_no_zero_byte_bundle(job):
    args, _ = job
    args.work = ""
    with pytest.raises(implementer.records.RecordError, match="work must be nonempty"):
        implementer.run_implementer(args)
    assert not list(args.output.parent.glob("result.md*"))


def test_stderr_session_header_is_retained_when_jsonl_has_no_thread_event(job):
    args, _ = job
    session = "0199a213-81c0-7800-8aa1-bbab2a035a53"
    configure(job, {
        "stdout": json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1}}),
        "stderr": f"session id: {session}\n",
        "message": "built\n",
    })
    assert implementer.run_implementer(args) == 0
    observed = record(args)["attempts"][0]["observed"]
    assert observed["session_id"] == session
    assert observed["session_id_source"] == "codex stderr session id header"


def test_setting_sources_distinguish_defaults_from_explicit_values(job):
    args, _ = job
    args.effort = "high"
    configure(job, {"stdout": success_events(), "message": "built\n"})
    assert implementer.run_implementer(args) == 0
    request = json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())
    sources = request["requested"]["sources"]
    assert sources["model"] == "dispatch_implementer default"
    assert sources["effort"] == "issuecomment-5655702442"
    assert sources["continuity"] == "launcher route (fresh)"


def test_explicit_model_and_effort_sources_are_recorded_separately(job):
    args, _ = job
    args.model = "gpt-owner"
    args.effort = "high"
    args.model_source = "issue-comment:model"
    args.effort_source = "issue-comment:effort"
    configure(job, {"stdout": success_events(), "message": "built\n"})
    assert implementer.run_implementer(args) == 0
    request = json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())
    assert request["requested"]["sources"]["model"] == "issue-comment:model"
    assert request["requested"]["sources"]["effort"] == "issue-comment:effort"


@pytest.mark.parametrize("field", ["model", "effort"])
def test_explicit_empty_setting_is_rejected_without_a_bundle(job, field):
    args, _ = job
    setattr(args, field, "")
    with pytest.raises(implementer.ImplementerError, match=f"--{field} must be nonempty"):
        implementer.run_implementer(args)
    assert not list(args.output.parent.glob("result.md*"))


def test_publication_failure_is_recorded_without_a_false_published_path(job, monkeypatch):
    args, _ = job
    configure(job, {"stdout": success_events(), "message": "built\n"})
    monkeypatch.setattr(
        implementer.records, "publish_output",
        lambda *_args: (_ for _ in ()).throw(OSError("hard link failed")),
    )
    with pytest.raises(OSError, match="hard link failed"):
        implementer.run_implementer(args)
    logged = record(args)
    assert logged["outcome"] == "error"
    assert logged["attempts"][0]["outcome"] == "success"
    assert logged["result"]["published_output"] is None
    assert "hard link failed" in logged["result"]["published_output_unavailable_reason"]
    assert not args.output.exists()


def test_claude_author_uses_auto_user_settings_and_separate_context(job, monkeypatch):
    args, scenario = job
    monkeypatch.setattr(implementer, "resolve_command",
                        lambda *_: [sys.executable, str(LIB / "tests/seat_cli.py"), "claude", str(scenario)])
    args.vendor = "claude"
    args.stage = "artifact"
    args.vendor_source = "machine file: claude"
    context = args.dispatch.with_name("context.md")
    context.write_bytes(b"Read the root instructions before authoring.\n")
    args.context = context
    session = "f0cb89b1-e040-4e6e-919b-4b4e58c717d2"
    scenario.write_bytes(json.dumps({"claude": {
        "stdout": json.dumps({
            "type": "result", "subtype": "success", "is_error": False,
            "session_id": session, "result": "artifact written",
            "modelUsage": {"claude-opus-5-5": {"inputTokens": 5}},
            "permission_denials": [], "total_cost_usd": 0.12,
        }),
    }}).encode())
    assert implementer.run_implementer(args) == 0
    flags = json.loads((args.root / "seen-claude.json").read_bytes())["argv"]
    assert flags[:2] == ["-p", "--model"]
    assert flags[flags.index("--model") + 1] == "claude-opus-5-5"
    assert flags[flags.index("--effort") + 1] == "high"
    assert flags[flags.index("--permission-mode") + 1] == "auto"
    assert flags[flags.index("--setting-sources") + 1] == "user"
    assert "--no-session-persistence" not in flags
    assert "--safe-mode" not in flags
    request = json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())
    assert request["requested"]["vendor"] == "claude"
    assert request["requested"]["sources"]["vendor"] == "machine file: claude"
    assert request["implementer_role"] == "artifact_author"
    assert implementer.records.sidecar(args.output, ".dispatch.bin").read_bytes() == args.dispatch.read_bytes()
    assert implementer.records.sidecar(args.output, ".context.bin").read_bytes() == context.read_bytes()
    assert record(args)["attempts"][0]["observed"]["session_id"] == session


def test_claude_resume_keeps_identity_and_unknown_usage_scope(job, monkeypatch):
    args, scenario = job
    monkeypatch.setattr(implementer, "resolve_command",
                        lambda *_: [sys.executable, str(LIB / "tests/seat_cli.py"), "claude", str(scenario)])
    args.vendor = "claude"
    args.resume = "f0cb89b1-e040-4e6e-919b-4b4e58c717d2"
    scenario.write_bytes(json.dumps({"claude": {
        "stdout": json.dumps({
            "type": "result", "subtype": "success", "is_error": False,
            "session_id": args.resume, "result": "fixed",
            "modelUsage": {"claude-opus-5-5": {"inputTokens": 7}},
        }),
    }}).encode())
    assert implementer.run_implementer(args) == 0
    flags = json.loads((args.root / "seen-claude.json").read_bytes())["argv"]
    assert flags[-2:] == ["--resume", args.resume]
    observed = record(args)["attempts"][0]["observed"]
    assert observed["normalized"] is None
    assert "scope is not established" in observed["normalized_unavailable_reason"]


@pytest.mark.parametrize("payload", [
    "not json",
    json.dumps({"type": "result", "is_error": True, "subtype": "error_during_execution",
                "result": "permission denied"}),
    json.dumps({"type": "result", "is_error": False, "subtype": "success",
                "session_id": "f0cb89b1-e040-4e6e-919b-4b4e58c717d2", "result": None}),
])
def test_claude_bad_completion_never_publishes(job, payload, monkeypatch):
    args, scenario = job
    monkeypatch.setattr(implementer, "resolve_command",
                        lambda *_: [sys.executable, str(LIB / "tests/seat_cli.py"), "claude", str(scenario)])
    args.vendor = "claude"
    scenario.write_bytes(json.dumps({"claude": {"stdout": payload}}).encode())
    assert implementer.run_implementer(args) == 1
    assert record(args)["outcome"] == "error"
    assert not args.output.exists()


def test_claude_permission_denial_is_an_error_even_with_success_result(job, monkeypatch):
    args, scenario = job
    args.vendor = "claude"
    monkeypatch.setattr(implementer, "resolve_command",
                        lambda *_: [sys.executable, str(LIB / "tests/seat_cli.py"), "claude", str(scenario)])
    scenario.write_bytes(json.dumps({"claude": {"stdout": json.dumps({
        "type": "result", "subtype": "success", "is_error": False,
        "session_id": "f0cb89b1-e040-4e6e-919b-4b4e58c717d2",
        "result": "I could not edit that file.",
        "permission_denials": [{"tool_name": "Write", "reason": "denied"}],
    })}}).encode())

    assert implementer.run_implementer(args) == 1
    logged = record(args)
    assert logged["outcome"] == "error"
    assert logged["attempts"][0]["permission_denials"] == [
        {"tool_name": "Write", "reason": "denied"},
    ]
    assert "permission denial" in logged["attempts"][0]["reason"]
    assert not args.output.exists()


def test_unavailable_claude_handover_attempt_keeps_predecessor_without_reservation(
        job, monkeypatch, capsys):
    args, _ = job
    args.vendor = "claude"
    args.claude_unavailable_reason = "Claude CLI not installed"
    args.handover_from = "predecessor-bundle"
    monkeypatch.setattr(implementer, "resolve_command",
                        lambda *_: pytest.fail("unavailable runtime must not be resolved"))

    assert implementer.run_implementer(args) == 1
    request = json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())
    logged = record(args)
    assert request["handover"] == logged["handover"] == {
        "from_bundle": "predecessor-bundle", "to_vendor": "claude",
        "replacement_session": None, "phase": "unavailable",
    }
    assert logged["outcome"] == "unavailable"
    assert not args.output.exists()
    assert "claude (source explicit --vendor claude) unavailable" in capsys.readouterr().err


def test_fresh_claude_handover_moves_reservation_to_completed_only_after_publication(
        job, monkeypatch):
    args, scenario = job
    monkeypatch.setattr(implementer, "resolve_command",
                        lambda *_: [sys.executable, str(LIB / "tests/seat_cli.py"), "claude", str(scenario)])
    args.vendor = "claude"
    args.session_id = "f0cb89b1-e040-4e6e-919b-4b4e58c717d2"
    args.handover_state = args.dispatch.with_name("handover.json")
    args.handover_from = "predecessor-bundle"
    args.handover_state.write_bytes(json.dumps({
        "replacement_session": args.session_id, "phase": "reserved",
    }).encode())
    scenario.write_bytes(json.dumps({"claude": {"stdout": json.dumps({
        "type": "result", "subtype": "success", "is_error": False,
        "session_id": args.session_id, "result": "continued",
    })}}).encode())
    assert implementer.run_implementer(args) == 0
    assert json.loads(args.handover_state.read_bytes())["phase"] == "completed"
    assert record(args)["handover"]["from_bundle"] == "predecessor-bundle"
    assert args.output.read_bytes() == b"continued"


@pytest.mark.parametrize(("result_text", "expected_phase", "expected_code"), [
    ("continued", "completed", 0),
    (None, "unresolved", 1),
])
def test_resumed_claude_handover_updates_the_same_reservation(
        job, monkeypatch, result_text, expected_phase, expected_code):
    args, scenario = job
    monkeypatch.setattr(implementer, "resolve_command",
                        lambda *_: [sys.executable, str(LIB / "tests/seat_cli.py"), "claude", str(scenario)])
    args.vendor = "claude"
    args.resume = "f0cb89b1-e040-4e6e-919b-4b4e58c717d2"
    args.handover_state = args.dispatch.with_name("handover.json")
    args.handover_from = "predecessor-bundle"
    args.handover_state.write_bytes(json.dumps({
        "replacement_session": args.resume, "phase": "unresolved",
    }).encode())
    scenario.write_bytes(json.dumps({"claude": {"stdout": json.dumps({
        "type": "result", "subtype": "success", "is_error": False,
        "session_id": args.resume, "result": result_text,
    })}}).encode())

    assert implementer.run_implementer(args) == expected_code
    assert json.loads(args.handover_state.read_bytes())["phase"] == expected_phase
    assert record(args)["handover"]["phase"] == "resume"

import json
from pathlib import Path
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import dispatch_implementer as implementer


@pytest.fixture
def job(tmp_path, monkeypatch):
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
    assert flags[flags.index("--model") + 1] == "gpt-6-astra"
    assert 'model_reasoning_effort="xhigh"' in flags
    logged = record(args)
    attempt = logged["attempts"][0]
    assert logged["outcome"] == "success"
    assert attempt["observed"]["session_id"] == "0199a213-81c0-7800-8aa1-bbab2a035a53"
    assert attempt["observed"]["normalized"] == {
        "scope": "invocation", "input_tokens": 120, "cached_input_tokens": 80,
        "output_tokens": 12, "reasoning_output_tokens": 3,
    }
    request = json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())
    assert request["runtime_version"] == "codex-cli test"
    assert request["settings_source"] == "issuecomment-5655702442"
    assert args.output.read_bytes() == b"built\n"
    assert Path(logged["result"]["source_output"]).read_bytes() == b"built\n"


def test_resume_names_exact_session_and_keeps_usage_scope_unknown(job):
    args, _ = job
    session = "0199a213-81c0-7800-8aa1-bbab2a035a53"
    args.resume = session
    args.model = "gpt-5.6-sol"
    configure(job, {"stdout": success_events(session), "message": "fixed\n"})
    assert implementer.run_implementer(args) == 0
    flags = seen(args)["argv"]
    assert flags[-3:] == ["resume", session, "-"]
    assert flags[flags.index("--model") + 1] == "gpt-5.6-sol"
    observed = record(args)["attempts"][0]["observed"]
    assert observed["raw"]
    assert observed["normalized"] is None
    assert "scope is not established" in observed["normalized_unavailable_reason"]


def test_resume_mismatch_is_error_and_never_publishes(job):
    args, _ = job
    args.resume = "0199a213-81c0-7800-8aa1-bbab2a035a53"
    configure(job, {
        "stdout": success_events("0299a213-81c0-7800-8aa1-bbab2a035a53"),
        "message": "wrong thread\n",
    })
    assert implementer.run_implementer(args) == 1
    assert record(args)["outcome"] == "error"
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

import json
import hashlib
import subprocess
import os
from pathlib import Path
import sys
import tomllib

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import dispatch_implementer as implementer
import vendor_cli


ARTIFACT_BRIEF = """<!-- tradecraft:affirmed-brief:v1 -->
# Implementation brief - the author returns the design inline

**Shape:** the recipient returns the whole design to its holder in the final message.
The holder needs the text to post it whole and preserve its source through judgment.

> **In plain terms:** the author writes a design, then sends the design itself.
> A location in another account's temporary directory cannot carry that document.

**R1. Require the final-message carrier.** The dispatch names the recipient's return.
- *Why:* later readers consume the recorded text without fetching private files.
- *Holder:* posts the whole source and checks fidelity before posting.
- *Builder:* opens the design with the affirmed brief quoted verbatim.
- *Judging seat:* reads that source in the existing inline carrier.

**R2. Preserve the author on failure.** A pointer does not close the artifact stage.
- *Why:* a repeated entrance command must resume the same recorded author.
- *Holder:* finds the failed bundle, session and native usage in the diagnostic.
- *Builder:* a fresh turn never replaces the author merely because text is absent.
- *Judging seat:* never receives a pointer instead of the design.

**Not this:** exact quotation checking or automatic stage retries.
Review risk: ordinary
Review lane: connected
""".replace("the design inline", "the design inline" + chr(0x2014) + "whole")

MECHANICAL_BRIEF = """<!-- tradecraft:affirmed-brief:v1 -->
Review risk: ordinary
Review lane: mechanical
"""
TINY_BRIEF = """<!-- tradecraft:affirmed-brief:v1 -->
# Mechanical brief
Return all text!!
"""

ARTIFACT_BODY = "\n**Purpose:** implement the inline design return.\nBody and falsifiers.\n"


def artifact_text(kind="exact"):
    brief = ARTIFACT_BRIEF
    if kind in {"corrupted", "combined"}:
        brief = brief.replace(chr(0x2014), "".join(map(chr, (0xE2, 0x20AC, 0x201D))), 1)
    if kind in {"blockquote", "combined"}:
        brief = "\n".join("> " + line for line in brief.splitlines()) + "\n"
    text = brief + ARTIFACT_BODY
    if kind == "leading-whitespace":
        text = " \n\t\n  " + text
    if kind == "long-preamble":
        text = "Introductory prose.\n" * 80 + text
    return text.replace("\n", "\r\n") if kind in {"crlf", "combined"} else text


def native_artifact_result(vendor, text, session="0199a213-81c0-7800-8aa1-bbab2a035a53"):
    if vendor == "codex":
        return {"stdout": success_events(session), "message": text}
    return {"stdout": json.dumps({
        "type": "result", "subtype": "success", "is_error": False,
        "session_id": session, "result": text,
        "modelUsage": {"claude-opus-5-5": {"inputTokens": 120, "outputTokens": 12}},
    })}


def supply_artifact_brief(args):
    args.artifact_brief = args.dispatch.with_name("brief.md")
    args.artifact_brief.write_bytes(ARTIFACT_BRIEF.encode("utf-8"))
    args.artifact_brief_source = "issue-comment:affirmed"


@pytest.fixture
def job(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.delenv("CODEX_HOME", raising=False)
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
        "--output", str(output), "--timeout-seconds", "60",
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


@pytest.mark.parametrize("resume", [None, "0199a213-81c0-7800-8aa1-bbab2a035a53"])
def test_artifact_codex_permissions_select_only_copy_without_broad_temp_roots(job, resume):
    args, _ = job
    args.stage, args.resume = "artifact", resume
    args.model, args.effort = implementer.PROFILES["artifact_author"]["codex"]
    command = implementer.build_command(args, ["codex"], args.output)
    assert command[command.index("--cd") + 1] == str(args.root.resolve())
    assert "--add-dir" not in command
    assert "--approve-for-me" in command
    assert 'sandbox_mode="workspace-write"' in command
    assert "sandbox_workspace_write.writable_roots=[]" in command
    assert "sandbox_workspace_write.exclude_slash_tmp=true" in command
    assert "sandbox_workspace_write.exclude_tmpdir_env_var=true" in command
    if resume:
        assert command[-3:] == ["resume", resume, "-"]
    args.stage = "build"
    builder = implementer.build_command(args, ["codex"], args.output)
    assert not any(value.startswith("sandbox_") for value in builder)


@pytest.mark.parametrize("limit", [5, 10])
def test_caller_limit_with_no_launch_window_starts_no_implementer(job, monkeypatch, limit):
    args, _ = job
    args.timeout_seconds = limit
    monkeypatch.setattr(implementer, "run_process", lambda *_a, **_k: pytest.fail("launched without a useful window"))
    with pytest.raises(TimeoutError, match="no useful launch window"):
        implementer.run_implementer(args)
    assert not args.output.exists()
    assert not (args.root / "seen-codex.json").exists()


def success_events(session_id="0199a213-81c0-7800-8aa1-bbab2a035a53"):
    return "\n".join((
        json.dumps({"type": "thread.started", "thread_id": session_id}),
        json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 120, "cached_input_tokens": 80,
            "output_tokens": 12, "reasoning_output_tokens": 3,
        }}),
    ))


@pytest.mark.parametrize("resume", [False, True])
@pytest.mark.parametrize("inherited", [None, "", '-q -k "passing or policy" --basetemp="C:\\test roots\\run"'])
def test_codex_launch_and_resume_supply_pytest_policy(job, monkeypatch, resume, inherited):
    args, _ = job
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    if inherited is not None:
        monkeypatch.setenv("PYTEST_ADDOPTS", inherited)
    before = dict(os.environ)
    args.vendor = "codex"
    if resume:
        args.resume = "0199a213-81c0-7800-8aa1-bbab2a035a53"
    configure(job, {"stdout": success_events(), "message": "built\n"})

    assert implementer.run_implementer(args) == 0

    flags = seen(args)["argv"]
    overrides = [flags[index + 1] for index, flag in enumerate(flags) if flag == "-c"]
    policy = [tomllib.loads(value)["shell_environment_policy"] for value in overrides
              if value.startswith("shell_environment_policy.")]
    expected = f"{inherited} -p no:cacheprovider" if inherited else "-p no:cacheprovider"
    assert policy == [{"set": {"PYTEST_ADDOPTS": expected}}]
    if resume:
        assert flags[-3:] == ["resume", args.resume, "-"]
    else:
        assert "resume" not in flags
        assert flags[-1] == "-"
    # On Windows this empty Python environment entry is absent in the child.
    child_value = None if os.name == "nt" and inherited == "" else inherited
    assert seen(args)["pytest_addopts"] == child_value
    assert dict(os.environ) == before


@pytest.mark.parametrize("resume", [False, True])
@pytest.mark.parametrize(("config_text", "base", "extra"), [
    ('[shell_environment_policy.set]\nPYTEST_ADDOPTS = "-x --tb=short"\n',
     "-x --tb=short", {}),
    ('[shell_environment_policy]\ninherit = "core"\n', "", {}),
    ('[shell_environment_policy]\ninherit = "none"\n', "", {}),
    ('[shell_environment_policy]\nexclude = ["p?test_*"]\n', "", {}),
    ('[shell_environment_policy.filters]\n"PyTeSt_*" = "exclude"\n', "", {}),
    ('[shell_environment_policy]\ninclude_only = ["PATH", "HOME"]\n',
     '-q -k "passing or policy"', {"include_only": ["PATH", "HOME", "PYTEST_ADDOPTS"]}),
    ('[shell_environment_policy.filters]\n"PATH" = "include"\n',
     '-q -k "passing or policy"', {"filters": {"PYTEST_ADDOPTS": "include"}}),
    ('[shell_environment_policy]\ninclude_only = ["p?TEST_*"]\n',
     '-q -k "passing or policy"', {}),
    ('[shell_environment_policy.filters]\n"p?TEST_*" = "include"\n',
     '-q -k "passing or policy"', {}),
    ('[shell_environment_policy.filters]\n"PATH" = "exclude"\n',
     '-q -k "passing or policy"', {}),
    ('[shell_environment_policy]\ninclude_only = []\n',
     '-q -k "passing or policy"', {}),
    ('[shell_environment_policy]\ninherit = "none"\n'
     '[shell_environment_policy.set]\nPYTEST_ADDOPTS = "-x"\n', "-x", {}),
    ('[shell_environment_policy]\nexclude = ["PYTEST_*"]\n'
     '[shell_environment_policy.set]\nPYTEST_ADDOPTS = "-x"\n', "-x", {}),
    ('[shell_environment_policy.set]\nPYTEST_ADDOPTS = ""\n', "", {}),
    ('[shell_environment_policy.filters]\n"PATH" = "include"\n'
     '"pytest_addopts" = "exclude"\n', "", {"filters": {"PYTEST_ADDOPTS": "include"}}),
    ('[shell_environment_policy]\nexclude = ["[PYTEST]*"]\n',
     '-q -k "passing or policy"', {}),
    ('[profiles.other.shell_environment_policy.set]\nPYTEST_ADDOPTS = "-x"\n',
     '-q -k "passing or policy"', {}),
], ids=["set", "core", "none", "legacy-exclude", "filter-exclude", "legacy-allowlist",
        "filter-allowlist", "legacy-matches", "filter-matches", "no-includes",
        "empty-allowlist", "set-after-none", "set-after-exclude", "empty-set",
        "replace-case-insensitive-filter", "literal-brackets", "ignore-profiles"])
def test_codex_launch_and_resume_preserve_user_pytest_policy(
    job, monkeypatch, resume, config_text, base, extra
):
    args, _ = job
    codex_home = args.root.parent / "codex-home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_bytes(config_text.encode("utf-8"))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("PYTEST_ADDOPTS", '-q -k "passing or policy"')
    before = dict(os.environ)
    args.vendor = "codex"
    if resume:
        args.resume = "0199a213-81c0-7800-8aa1-bbab2a035a53"
    configure(job, {"stdout": success_events(), "message": "built\n"})

    assert implementer.run_implementer(args) == 0

    flags = seen(args)["argv"]
    overrides = [flags[index + 1] for index, flag in enumerate(flags) if flag == "-c"]
    policy = tomllib.loads("\n".join(overrides))["shell_environment_policy"]
    expected = f"{base} -p no:cacheprovider" if base else "-p no:cacheprovider"
    assert policy == {"set": {"PYTEST_ADDOPTS": expected}, **extra}
    assert dict(os.environ) == before


@pytest.mark.parametrize("source", ["missing", "invalid-toml", "invalid-utf8", "unreadable"])
def test_codex_launch_keeps_inherited_pytest_options_when_config_is_unusable(
    job, monkeypatch, source
):
    args, _ = job
    codex_home = args.root.parent / "codex-home"
    codex_home.mkdir()
    config = codex_home / "config.toml"
    if source != "missing":
        config.write_bytes(b"[broken" if source == "invalid-toml" else
                           b"\xff" if source == "invalid-utf8" else
                           b'[shell_environment_policy]\ninherit = "none"\n')
    if source == "unreadable":
        read_bytes = Path.read_bytes

        def denied(path):
            if path == config:
                raise PermissionError("fixture denied the read")
            return read_bytes(path)

        monkeypatch.setattr(Path, "read_bytes", denied)
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("PYTEST_ADDOPTS", "-x")
    args.vendor = "codex"
    configure(job, {"stdout": success_events(), "message": "built\n"})

    assert implementer.run_implementer(args) == 0

    assert 'shell_environment_policy.set.PYTEST_ADDOPTS="-x -p no:cacheprovider"' in seen(args)["argv"]


@pytest.mark.parametrize("codex_home", [None, ""])
def test_codex_launch_reads_default_user_pytest_policy(job, monkeypatch, codex_home):
    args, _ = job
    config = Path.home() / ".codex" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_bytes(b'[shell_environment_policy.set]\nPYTEST_ADDOPTS = "-x"\n')
    if codex_home is not None:
        monkeypatch.setenv("CODEX_HOME", codex_home)
    monkeypatch.setenv("PYTEST_ADDOPTS", "-q")
    args.vendor = "codex"
    configure(job, {"stdout": success_events(), "message": "built\n"})

    assert implementer.run_implementer(args) == 0

    assert 'shell_environment_policy.set.PYTEST_ADDOPTS="-x -p no:cacheprovider"' in seen(args)["argv"]


@pytest.mark.parametrize("resume", [False, True])
def test_claude_launch_and_resume_keep_pytest_environment(job, monkeypatch, resume):
    args, scenario = job
    inherited = '-q -k "passing or policy"'
    monkeypatch.setenv("PYTEST_ADDOPTS", inherited)
    before = dict(os.environ)
    args.vendor = "claude"
    session = "f0cb89b1-e040-4e6e-919b-4b4e58c717d2"
    if resume:
        args.resume = session
    monkeypatch.setattr(
        implementer, "resolve_command",
        lambda *_: [sys.executable, str(LIB / "tests/seat_cli.py"), "claude", str(scenario)],
    )
    scenario.write_bytes(json.dumps({"claude": native_artifact_result("claude", "built", session)}).encode())

    assert implementer.run_implementer(args) == 0

    observed = json.loads((args.root / "seen-claude.json").read_bytes())
    expected = [
        "-p", "--model", "claude-opus-5-5", "--effort", "high",
        "--output-format", "stream-json", "--verbose", "--permission-mode", "auto",
        "--setting-sources", "user", "--plugin-dir", str(LIB.parent),
    ]
    if resume:
        expected.extend(("--resume", session))
    assert observed["argv"] == expected
    assert observed["pytest_addopts"] == inherited
    assert dict(os.environ) == before


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


def test_elapsed_accounting_does_not_clip_a_measured_overrun(job, monkeypatch):
    args, _ = job
    clock = [100.0]
    monkeypatch.setattr(implementer.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(implementer.records, "git_revision", lambda *_: None)
    monkeypatch.setattr(implementer.lifecycle, "content_snapshot", lambda *a, **k: {"digest": "fixture"})
    def returned(command, **kwargs):
        clock[0] += kwargs["timeout"] + 0.1
        Path(command[command.index("--output-last-message") + 1]).write_bytes(b"built\n")
        return subprocess.CompletedProcess(command, 0, success_events().encode(), b"")
    monkeypatch.setattr(implementer, "run_process", returned)
    assert implementer.run_implementer(args) == 0
    request = json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())
    assert record(args)["attempts"][0]["elapsed_seconds"] > request["recipient_allocation_seconds"]


@pytest.mark.parametrize("vendor", ["codex", "claude"])
def test_ceiling_reason_distinguishes_caller_allocation_and_elapsed(job, monkeypatch, vendor):
    args, _ = job
    args.vendor, args.timeout_seconds = vendor, 120
    args.lifecycle_input = args.dispatch.with_name("lifecycle.json")
    args.lifecycle_input.write_bytes(json.dumps({"recipient_allocation_seconds": 90.78}).encode())
    clock = [100.0]
    monkeypatch.setattr(implementer.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(implementer.records, "git_revision", lambda *_: None)
    snapshots = []
    def snapshot(*_a, **_k):
        if not snapshots:
            clock[0] += 20.2  # Preflight consumes part of the same caller window.
        snapshots.append(True)
        return {"digest": "fixture"}
    monkeypatch.setattr(implementer.lifecycle, "content_snapshot", snapshot)
    def stopped(command, **kwargs):
        clock[0] += kwargs["timeout"]
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=b"", stderr=b"")
    monkeypatch.setattr(implementer, "run_process", stopped)
    assert implementer.run_implementer(args) == 1
    request = json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())
    attempt = record(args)["attempts"][0]
    assert request["recipient_allocation_seconds"] == 90.78
    assert attempt["allocation_seconds"] == pytest.approx(87.8)
    assert attempt["elapsed_seconds"] == pytest.approx(87.8)
    assert attempt["reason"] == (
        f"{vendor} stopped at the recipient ceiling; caller limit 120s; "
        "recipient allocation 87.80s; measured elapsed 87.80s")


def test_claude_ceiling_with_truncated_utf8_retains_interruption_and_identity(job, monkeypatch):
    args, _ = job
    args.vendor = "claude"
    session = "0199a213-81c0-7800-8aa1-bbab2a035a53"
    raw = json.dumps({"type": "system", "subtype": "init", "session_id": session}).encode() + b"\n\xe2"
    def stopped(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=raw, stderr=b"")
    monkeypatch.setattr(implementer, "run_process", stopped)
    assert implementer.run_implementer(args) == 1
    saved = record(args)
    assert saved["outcome"] == "interrupted" and saved["interruption_cause"] == "ceiling"
    assert saved["session_identity"]["session_id"] == session
    assert "stopped at the recipient ceiling" in saved["attempts"][0]["reason"]
    assert Path(saved["attempts"][0]["stdout"]).read_bytes() == raw
    assert not args.output.exists()


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
    supply_artifact_brief(args)
    args.vendor_source = "machine file: claude"
    context = args.dispatch.with_name("context.md")
    context.write_bytes(b"Read the root instructions before authoring.\n")
    args.context = context
    session = "f0cb89b1-e040-4e6e-919b-4b4e58c717d2"
    scenario.write_bytes(json.dumps({"claude": {
        "stdout": json.dumps({
            "type": "result", "subtype": "success", "is_error": False,
            "session_id": session, "result": artifact_text(),
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


@pytest.mark.parametrize("stage", ["artifact", "build"])
@pytest.mark.parametrize("vendor", ["codex", "claude"])
def test_direct_ruling_launch_prints_before_process_and_retains_source(job, monkeypatch, capsys, stage, vendor):
    args, _ = job
    args.stage, args.vendor = stage, vendor
    if stage == "artifact":
        supply_artifact_brief(args)
    role = "artifact_author" if stage == "artifact" else "implementer"
    model, effort = implementer.PROFILES[role][vendor]
    path = Path.home() / ".tradecraft" / "model-rulings.json"
    path.parent.mkdir(parents=True)
    entry = {"id": "direct-ruling", "role": role, "vendor": vendor,
             "replaces": {"model": model, "effort": effort},
             "model": "direct-ruled", "effort": "direct-effort", "source": "ruling-record"}
    path.write_bytes(json.dumps({"schema_version": 1, "entries": [entry]}).encode())
    configure(job, {"stdout": success_events(), "message": "built\n"})
    original = implementer.run_process
    def launch(command, **kwargs):
        output = capsys.readouterr().out
        plan = json.loads(next(line.split("launch_settings ", 1)[1] for line in output.splitlines()
                               if line.startswith("implementer: launch_settings ")))
        primary = plan["primary"]
        assert primary["model"] == command[command.index("--model") + 1] == "direct-ruled"
        assert primary["effort"] == "direct-effort"
        assert json.loads(primary["sources"]["model"].removeprefix("model ruling ")) == {
            "path": str(path.resolve()), **entry}
        return original(command, **kwargs)
    monkeypatch.setattr(implementer, "run_process", launch)
    # Fixture runtime returns Codex-shaped output for either command; the request is the boundary tested.
    implementer.run_implementer(args)
    path.unlink()
    request = json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())
    assert request["requested"]["model"] == "direct-ruled"
    assert "direct-ruling" in request["requested"]["sources"]["model"]
    assert "ruling-record" in request["requested"]["sources"]["effort"]


@pytest.mark.parametrize("vendor", ["codex", "claude"])
@pytest.mark.parametrize("text", [
    r"C:\Users\author\Temp\artifact.md", "/tmp/author/artifact.md",
    "The artifact is in /tmp/author/artifact.md; retrieve it there.",
    "[Artifact](C:/Users/author/Temp/artifact.md)",
    "I wrote the Implementation brief - the author returns the design inline. "
    "<!-- tradecraft:affirmed-brief:v1 --> " + "Fetch the document from /tmp/artifact.md. " * 50,
    "<!-- tradecraft:affirmed-brief:v1 -->",
    "# Implementation brief - the author returns the design inline",
], ids=["windows-path", "unix-path", "pointer", "file-link", "long-pointer",
        "marker-only", "title-only"])
def test_artifact_pointer_return_fails_with_retained_native_evidence(job, monkeypatch, capsys, vendor, text):
    args, scenario = job
    args.stage, args.vendor = "artifact", vendor
    supply_artifact_brief(args)
    monkeypatch.setattr(implementer, "resolve_command", lambda *_: [
        sys.executable, str(LIB / "tests/seat_cli.py"), vendor, str(scenario)])
    scenario.write_bytes(json.dumps({vendor: native_artifact_result(vendor, text)}).encode())
    assert implementer.run_implementer(args) == 1
    logged = record(args)
    attempt = logged["attempts"][0]
    assert logged["outcome"] == "invalid_artifact_return"
    assert attempt["outcome"] == "success"
    assert attempt["observed"]["session_id"] == "0199a213-81c0-7800-8aa1-bbab2a035a53"
    tokens = attempt["usage"]["tokens"]
    assert (tokens if vendor == "codex" else tokens["models"]["claude-opus-5-5"])["input"] == 120
    assert len(logged["attempts"]) == 1
    assert logged["result"]["return_validation"]["status"] == "fail"
    assert Path(logged["result"]["source_output"]).read_bytes() == text.encode("utf-8")
    assert args.output.read_bytes() == text.encode("utf-8")
    diagnostic = capsys.readouterr()
    assert "session 0199" not in diagnostic.out
    assert str(implementer.records.sidecar(args.output, ".run.json")) in diagnostic.err
    assert attempt["observed"]["session_id"] in diagnostic.err
    assert "repeat run artifact" in diagnostic.err


@pytest.mark.parametrize("brief", [TINY_BRIEF, MECHANICAL_BRIEF, ARTIFACT_BRIEF], ids=["75-character", "mechanical", "sub-2000"])
@pytest.mark.parametrize("prefix", [
    "I'm the artifact author. Below is the complete design for the holder.\n",
    "<!-- tradecraft:artifact:v1 status=draft -->\n",
    "# Artifact design\n", " \n\t\n",
], ids=["preamble", "artifact-marker", "heading", "whitespace"])
@pytest.mark.parametrize("omit_marker", [False, True])
def test_artifact_review_tolerates_preface_short_drift_and_omitted_comment(brief, prefix, omit_marker):
    assert len(TINY_BRIEF) == 75
    assert len(MECHANICAL_BRIEF) == 84
    assert len(ARTIFACT_BRIEF) < 2000
    corruption = "".join(map(chr, (0xE2, 0x20AC, 0x201D)))
    corrupted = (brief.replace("ordinary", corruption + "rdinary", 1) if "ordinary" in brief
                 else brief.replace("Return", corruption + "eturn", 1))
    if omit_marker:
        corrupted = corrupted.split("\n", 1)[1]
    quoted = "\n".join("> " + line for line in corrupted.splitlines())
    returned = (prefix + quoted + ARTIFACT_BODY).replace("\n", "\r\n")
    assert implementer.artifact_opening_carries_brief(brief, returned)


@pytest.mark.parametrize("repetitions", [80, 800])
def test_artifact_review_searches_the_whole_return(repetitions):
    preamble = "Introductory prose.\n" * repetitions
    assert len(" ".join(preamble.split())) > 1024
    assert implementer.artifact_opening_carries_brief(
        ARTIFACT_BRIEF, preamble + artifact_text("combined"))


@pytest.mark.parametrize("vendor", ["codex", "claude"])
@pytest.mark.parametrize("tail", [
    "", "/tmp/artifact.md", r"C:\Users\author\Temp\artifact.md",
    "[Artifact](artifact.md)", "Fetch the entire document from /tmp/artifact.md.",
    "The artifact is in the file I wrote. Please retrieve it there.",
    "# The entire artifact design is available for the holder to read\n/tmp/artifact.md",
], ids=["brief-only", "unix-path", "windows-path", "file-link", "pointer", "pointer-without-path", "heading-and-path"])
def test_artifact_review_rejects_a_brief_without_a_non_location_body(job, monkeypatch, capsys, vendor, tail):
    args, scenario = job
    args.stage, args.vendor = "artifact", vendor
    supply_artifact_brief(args)
    text = ARTIFACT_BRIEF + "\n" + tail
    monkeypatch.setattr(implementer, "resolve_command", lambda *_: [
        sys.executable, str(LIB / "tests/seat_cli.py"), vendor, str(scenario)])
    scenario.write_bytes(json.dumps({vendor: native_artifact_result(vendor, text)}).encode())
    assert implementer.run_implementer(args) == 1
    assert record(args)["outcome"] == "invalid_artifact_return"
    assert args.output.read_bytes() == text.encode("utf-8")
    diagnostic = capsys.readouterr().err
    assert "expected the affirmed brief" in diagnostic
    assert "artifact body" in diagnostic


def test_artifact_review_missing_brief_input_names_the_required_file(job):
    args, _ = job
    args.stage = "artifact"
    with pytest.raises(implementer.ImplementerError, match="--artifact-brief FILE.*affirmed brief comment"):
        implementer.run_implementer(args)


@pytest.mark.parametrize("vendor", ["codex", "claude"])
def test_artifact_review_custom_dispatch_stays_exact_and_explains_missing_brief(job, monkeypatch, capsys, vendor):
    args, scenario = job
    args.stage, args.vendor = "artifact", vendor
    supply_artifact_brief(args)
    custom = b"Write the design in your final message.\r\n"
    args.dispatch.write_bytes(custom)
    monkeypatch.setattr(implementer, "resolve_command", lambda *_: [
        sys.executable, str(LIB / "tests/seat_cli.py"), vendor, str(scenario)])
    scenario.write_bytes(json.dumps({vendor: native_artifact_result(vendor, ARTIFACT_BODY)}).encode())
    assert implementer.run_implementer(args) == 1
    assert implementer.records.sidecar(args.output, ".dispatch.bin").read_bytes() == custom
    diagnostic = capsys.readouterr().err
    assert "expected the affirmed brief" in diagnostic and "anywhere in the return" in diagnostic
    assert "artifact body" in diagnostic


def test_artifact_review_body_requires_eight_prose_words():
    seven = "Alpha bravo charlie delta echo foxtrot golf"
    assert not implementer.artifact_opening_carries_brief(ARTIFACT_BRIEF, ARTIFACT_BRIEF + seven)
    assert implementer.artifact_opening_carries_brief(ARTIFACT_BRIEF, ARTIFACT_BRIEF + seven + " hotel")
    assert implementer.artifact_opening_carries_brief(
        ARTIFACT_BRIEF, ARTIFACT_BRIEF + "[Design](artifact.md)\n" + seven + " hotel")


@pytest.mark.parametrize("vendor", ["codex", "claude"])
@pytest.mark.parametrize("kind", ["exact", "blockquote", "crlf", "corrupted", "combined", "leading-whitespace", "long-preamble"])
def test_artifact_inline_return_passes_and_retains_exact_sources(job, monkeypatch, vendor, kind):
    args, scenario = job
    args.stage, args.vendor = "artifact", vendor
    supply_artifact_brief(args)
    text = artifact_text(kind)
    monkeypatch.setattr(implementer, "resolve_command", lambda *_: [
        sys.executable, str(LIB / "tests/seat_cli.py"), vendor, str(scenario)])
    scenario.write_bytes(json.dumps({vendor: native_artifact_result(vendor, text)}).encode())
    assert implementer.run_implementer(args) == 0
    assert record(args)["outcome"] == "success"
    assert record(args)["result"]["return_validation"] == {"status": "pass", "reason": ""}
    assert args.output.read_bytes() == text.replace("\r\n", "\n").encode("utf-8")
    request = json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())
    retained = request["artifact_brief"]
    assert retained["source"] == "issue-comment:affirmed"
    args.artifact_brief.unlink()
    assert Path(retained["path"]).read_bytes() == ARTIFACT_BRIEF.encode("utf-8")
    assert retained["sha256"] == hashlib.sha256(ARTIFACT_BRIEF.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("vendor", ["codex", "claude"])
@pytest.mark.parametrize("text", ["", " \r\n\t "])
def test_artifact_empty_return_preserves_identity_and_reports_failed_bundle(job, monkeypatch, capsys, vendor, text):
    args, scenario = job
    args.stage, args.vendor = "artifact", vendor
    supply_artifact_brief(args)
    monkeypatch.setattr(implementer, "resolve_command", lambda *_: [
        sys.executable, str(LIB / "tests/seat_cli.py"), vendor, str(scenario)])
    scenario.write_bytes(json.dumps({vendor: native_artifact_result(vendor, text)}).encode())
    assert implementer.run_implementer(args) == 1
    logged = record(args)
    assert logged["outcome"] == "completed_no_output"
    assert logged["result"]["return_validation"]["status"] == "fail"
    assert logged["result"]["source_output"] is None
    assert not args.output.exists()
    assert len(logged["attempts"]) == 1
    attempt = logged["attempts"][0]
    tokens = attempt["usage"]["tokens"]
    assert (tokens if vendor == "codex" else tokens["models"]["claude-opus-5-5"])["input"] == 120
    diagnostic = capsys.readouterr().err
    assert str(implementer.records.sidecar(args.output, ".run.json")) in diagnostic
    assert attempt["observed"]["session_id"] in diagnostic
    assert "repeat run artifact" in diagnostic


@pytest.mark.parametrize("content", [None, b"", b" \r\n", b"\xff"])
def test_artifact_brief_input_is_validated_before_launch(job, monkeypatch, content):
    args, _ = job
    args.stage = "artifact"
    if content is not None:
        supply_artifact_brief(args)
        args.artifact_brief.write_bytes(content)
    monkeypatch.setattr(implementer, "run_process", lambda *_a, **_k: pytest.fail("launched invalid input"))
    with pytest.raises((implementer.ImplementerError, UnicodeError)):
        implementer.run_implementer(args)
    assert not args.output.parent.exists()


@pytest.mark.parametrize("vendor", ["codex", "claude"])
@pytest.mark.parametrize("text", ["/tmp/private/artifact.md", ""])
def test_failed_artifact_without_native_identity_reports_unavailable(job, monkeypatch, capsys, vendor, text):
    args, scenario = job
    args.stage, args.vendor = "artifact", vendor
    supply_artifact_brief(args)
    monkeypatch.setattr(implementer, "resolve_command", lambda *_: [
        sys.executable, str(LIB / "tests/seat_cli.py"), vendor, str(scenario)])
    scenario.write_bytes(json.dumps({vendor: native_artifact_result(vendor, text, None)}).encode())
    assert implementer.run_implementer(args) == 1
    logged = record(args)
    assert logged["outcome"] == ("invalid_artifact_return" if text else "completed_no_output")
    assert logged["attempts"][0]["observed"]["session_id"] is None
    assert "author session unavailable" in capsys.readouterr().err


@pytest.mark.parametrize("text", ["/tmp/private/artifact.md", ""])
def test_failed_artifact_handover_keeps_the_proved_native_identity(job, monkeypatch, text):
    args, scenario = job
    args.stage, args.vendor = "artifact", "claude"
    supply_artifact_brief(args)
    args.session_id = "f0cb89b1-e040-4e6e-919b-4b4e58c717d2"
    args.handover_state = args.dispatch.with_name("handover.json")
    args.handover_from = "predecessor-bundle"
    args.handover_state.write_bytes(json.dumps({
        "replacement_session": args.session_id, "phase": "reserved",
    }).encode())
    monkeypatch.setattr(implementer, "resolve_command", lambda *_: [
        sys.executable, str(LIB / "tests/seat_cli.py"), "claude", str(scenario)])
    scenario.write_bytes(json.dumps({"claude": native_artifact_result("claude", text, args.session_id)}).encode())
    assert implementer.run_implementer(args) == 1
    assert record(args)["attempts"][0]["observed"]["session_id"] == args.session_id
    assert json.loads(args.handover_state.read_bytes())["phase"] == "completed"


@pytest.mark.parametrize("failure", ["identity", "runtime", "publication"])
def test_artifact_validation_preserves_stronger_failures(job, monkeypatch, failure):
    args, scenario = job
    args.stage, args.vendor = "artifact", "codex"
    supply_artifact_brief(args)
    native = native_artifact_result("codex", "/tmp/private/artifact.md")
    if failure == "identity":
        args.resume = "01234567-89ab-cdef-0123-456789abcdef"
    elif failure == "runtime":
        native["stdout"] = json.dumps({"type": "turn.failed"})
    else:
        def refuse(*_args):
            raise OSError("publication refused")
        monkeypatch.setattr(implementer.records, "publish_output", refuse)
    scenario.write_bytes(json.dumps({"codex": native}).encode())
    if failure == "publication":
        with pytest.raises(OSError, match="publication refused"):
            implementer.run_implementer(args)
    else:
        assert implementer.run_implementer(args) == 1
        assert "return_validation" not in record(args)["result"]
    assert record(args)["outcome"] == "error"
    assert not args.output.exists()


def test_partial_direct_choice_does_not_bridge_explicit_default(job):
    args, _ = job
    args.model = implementer.PROFILES["implementer"]["codex"][0]
    args.model_source = "explicit --model"
    path = Path.home() / ".tradecraft" / "model-rulings.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(json.dumps({"schema_version": 1, "entries": [{
        "id": "partial", "role": "implementer", "vendor": "codex",
        "replaces": {"model": args.model, "effort": "xhigh"},
        "model": "ruled", "effort": "ruled-effort", "source": "source-record",
    }]}).encode())
    configure(job, {"stdout": success_events(), "message": "built\n"})
    assert implementer.run_implementer(args) == 0
    request = json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())["requested"]
    assert request["model"] == implementer.DEFAULT_MODEL
    assert request["sources"]["model"] == "explicit --model"
    assert request["effort"] == "ruled-effort" and "partial" in request["sources"]["effort"]


def test_malformed_bridge_implementer_refuses_before_bundle(job):
    args, _ = job
    path = Path.home() / ".tradecraft" / "model-rulings.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"{")
    with pytest.raises(implementer.launch_settings.SettingsError):
        implementer.run_implementer(args)
    assert not args.output.parent.exists()



def test_unavailable_bridged_request_retains_provenance_without_observation(job):
    args, _ = job
    path = Path.home() / ".tradecraft" / "model-rulings.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(json.dumps({"schema_version": 1, "entries": [{
        "id": "unavailable-ruling", "role": "implementer", "vendor": "codex",
        "replaces": {"model": implementer.DEFAULT_MODEL, "effort": "xhigh"},
        "model": "requested-only", "effort": "requested-effort", "source": "ruling-source",
    }]}).encode())
    args.codex_unavailable_reason = "fixture executable unavailable"
    assert implementer.run_implementer(args) == 1
    path.unlink()
    requested = json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())["requested"]
    assert requested["model"] == "requested-only"
    assert "unavailable-ruling" in requested["sources"]["model"]
    attempt = record(args)["attempts"][0]
    assert attempt["launched"] is False
    assert attempt["observed"]["reported_models"] == []
    assert attempt["observed"]["reported_effort"] is None


def test_deadline_expiry_is_a_ceiling_not_a_spawn_error(job, monkeypatch):
    args, _scenario = job
    def expired(*_a, **_k):
        raise TimeoutError("caller limit has no useful launch window")
    monkeypatch.setattr(implementer, "run_process", expired)
    assert implementer.run_implementer(args) == 1
    run = json.loads(implementer.records.sidecar(args.output, ".run.json").read_bytes())
    assert run["outcome"] == "interrupted" and run["interruption_cause"] == "ceiling"
    assert not run["attempts"][0]["launched"]
    assert "cannot launch" not in run["attempts"][0]["reason"]



def test_real_missing_vendor_does_not_credit_an_implementer_launch(job, monkeypatch):
    args, _scenario = job
    monkeypatch.setattr(implementer, "resolve_command", lambda *_a: [str(args.root / "missing-vendor")])
    assert implementer.run_implementer(args) == 1
    run = json.loads(implementer.records.sidecar(args.output, ".run.json").read_bytes())
    assert not run["attempts"][0]["launched"]
    assert not implementer.lifecycle.stopped(run)

"""Pins the deterministic half of the real Codex compatibility probe."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_codex_compat as compat  # noqa: E402


def _executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("codex", encoding="utf-8")
    return path


def test_explicit_binary_wins_over_path(tmp_path):
    explicit = _executable(tmp_path / "chosen" / "codex.exe")
    other = _executable(tmp_path / "other" / "codex.exe")
    found = compat.resolve_codex(
        str(explicit), path_lookup=lambda _: str(other), platform="nt"
    )
    assert found == explicit.resolve()


def test_path_binary_precedes_the_windows_bundle(tmp_path):
    on_path = _executable(tmp_path / "path" / "codex.exe")
    _executable(tmp_path / "OpenAI" / "Codex" / "bin" / "hash" / "codex.exe")
    found = compat.resolve_codex(
        None,
        env={"LOCALAPPDATA": str(tmp_path)},
        path_lookup=lambda _: str(on_path),
        platform="nt",
    )
    assert found == on_path.resolve()


def test_windows_bundle_resolves_when_codex_is_absent_from_path(tmp_path):
    bundled = _executable(
        tmp_path / "OpenAI" / "Codex" / "bin" / "build-id" / "codex.exe"
    )
    found = compat.resolve_codex(
        None,
        env={"LOCALAPPDATA": str(tmp_path)},
        path_lookup=lambda _: None,
        platform="nt",
    )
    assert found == bundled.resolve()


def test_missing_binary_is_a_named_precondition(tmp_path):
    with pytest.raises(compat.CompatError, match="Codex CLI not found"):
        compat.resolve_codex(
            None,
            env={"LOCALAPPDATA": str(tmp_path)},
            path_lookup=lambda _: None,
            platform="nt",
        )


def test_probe_launch_pins_isolation_and_staffing(tmp_path):
    command = compat.build_probe_command(
        tmp_path / "codex.exe",
        tmp_path / "consumer",
        tmp_path / "last.txt",
        model="gpt-5.6-sol",
        reasoning="high",
    )
    assert command[1] == "exec"
    assert "--ephemeral" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--json" in command
    assert command[command.index("--model") + 1] == "gpt-5.6-sol"
    assert 'model_reasoning_effort="high"' in command
    assert command[command.index("-C") + 1].endswith("consumer")
    assert "--skip-git-repo-check" not in command
    assert command[-1] == compat.PROMPT
    assert "TRADECRAFT_CODEX_COMPAT_" not in compat.PROMPT
    evidence = compat._charter_evidence()
    assert evidence["opening"] not in compat.PROMPT
    assert evidence["tail"] not in compat.PROMPT
    assert all(ceremony not in compat.PROMPT for ceremony in evidence["ceremonies"])
    assert "nine descriptions" not in compat.PROMPT


def test_adoption_file_names_the_single_supported_flow(tmp_path):
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    path = compat.write_adoption_file(consumer, "TRADECRAFT_CODEX_COMPAT_TEST")
    content = path.read_bytes().decode("utf-8")
    assert "load and read the installed `tradecraft:charter`" in content
    assert "completely" in content
    assert "If it is unavailable, stop and tell the owner" in content
    assert "TRADECRAFT_CODEX_COMPAT_TEST" in content
    assert "hooks" not in content.casefold()


def test_consumer_boundary_rejects_the_source_tree_and_accepts_a_sibling(tmp_path):
    source = tmp_path / "source"
    inside = source / "consumer"
    sibling = tmp_path / "consumer"
    assert compat._is_within(inside, source)
    assert not compat._is_within(source, source)
    assert not compat._is_within(sibling, source)


def test_plugin_check_requires_the_tree_version(monkeypatch):
    payload = {
        "installed": [{
            "pluginId": "tradecraft@tradecraft",
            "version": "0.50.0",
            "installed": True,
            "enabled": True,
        }]
    }

    def captured(_command, *, cwd=None):
        return type("Result", (), {
            "returncode": 0,
            "stdout": json.dumps(payload),
            "stderr": "",
        })()

    monkeypatch.setattr(compat, "_capture", captured)
    compat._assert_plugin(Path("codex"), "0.50.0")
    with pytest.raises(compat.CompatError, match="this tree"):
        compat._assert_plugin(Path("codex"), "0.51.0")


@pytest.mark.parametrize("payload", [[], None])
def test_plugin_check_rejects_json_that_is_not_an_object(monkeypatch, payload):
    def captured(_command, *, cwd=None):
        return type("Result", (), {
            "returncode": 0,
            "stdout": json.dumps(payload),
            "stderr": "",
        })()

    monkeypatch.setattr(compat, "_capture", captured)
    with pytest.raises(compat.CompatError, match="must be an object"):
        compat._assert_plugin(Path("codex"), "0.50.0")


def test_capture_translates_launch_failure(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise OSError("binary unavailable")

    monkeypatch.setattr(compat.subprocess, "run", unavailable)
    with pytest.raises(compat.CompatError, match="cannot launch codex.*binary unavailable"):
        compat._capture(["codex", "--version"])


def test_binary_capture_preserves_non_utf8_bytes(monkeypatch):
    raw = b"good\xffbytes"
    monkeypatch.setattr(
        compat.subprocess, "run",
        lambda *_a, **kwargs: subprocess.CompletedProcess(["codex"], 0, raw, b"\xfe"),
    )
    result = compat._capture(["codex"], binary=True)
    assert result.stdout == raw
    assert result.stderr == b"\xfe"


def test_nested_session_timeout_is_a_named_failure(tmp_path, monkeypatch):
    class FixedTemporaryDirectory:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return str(tmp_path)

        def __exit__(self, *_args):
            return False

    def captured(command, *, cwd=None, timeout=None, binary=False):
        if command[:2] == ["git", "init"]:
            assert timeout is None
            return subprocess.CompletedProcess(command, 0, "", "")
        assert timeout == 17
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(compat.tempfile, "TemporaryDirectory", FixedTemporaryDirectory)
    monkeypatch.setattr(compat, "_capture", captured)
    monkeypatch.setattr(compat, "ROOT", tmp_path / "source")
    record_output = tmp_path.parent / f"{tmp_path.name}-timeout-records" / "timeout.md"
    with pytest.raises(
        compat.CompatError,
        match="timed out after 17 seconds before returning a result",
    ):
        compat.run_probe(
            Path("codex"), model="gpt-5.6-sol", reasoning="high", timeout_seconds=17,
            record_output=record_output,
        )
    run = json.loads(compat.records.sidecar(record_output, ".run.json").read_bytes())
    assert run["outcome"] == "error"
    assert run["attempts"][0]["reason"].startswith("nested Codex session timed out")
    assert run["attempts"][0]["stdout_encoding"] == "utf-8"
    assert run["result"]["published_output"] is None


def test_nested_session_success_pins_completion_and_timeout_scope(tmp_path, monkeypatch):
    class FixedTemporaryDirectory:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return str(tmp_path)

        def __exit__(self, *_args):
            return False

    source = tmp_path / "source"
    charter = source / "skills" / "charter" / "SKILL.md"
    charter.parent.mkdir(parents=True)
    charter.write_text(
        (compat.ROOT / "skills" / "charter" / "SKILL.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    timeouts = []

    def captured(command, *, cwd=None, timeout=None, binary=False):
        timeouts.append(timeout)
        if command[:2] == ["git", "init"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        adoption = (Path(cwd) / "AGENTS.md").read_text(encoding="utf-8")
        marker = adoption.split("Compatibility marker: ", 1)[1].strip()
        last_message = Path(command[command.index("--output-last-message") + 1])
        last_message.write_text(
            json.dumps(compat._expected_probe_payload(marker), ensure_ascii=False),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(compat.tempfile, "TemporaryDirectory", FixedTemporaryDirectory)
    monkeypatch.setattr(compat, "_capture", captured)
    monkeypatch.setattr(compat, "ROOT", source)
    record_output = tmp_path.parent / f"{tmp_path.name}-success-records" / "success.md"
    compat.run_probe(
        Path("codex"), model="gpt-5.6-sol", reasoning="high", timeout_seconds=17,
        record_output=record_output,
    )
    assert timeouts == [None, 17]
    run = json.loads(compat.records.sidecar(record_output, ".run.json").read_bytes())
    assert run["outcome"] == "success"
    assert run["attempts"][0]["stdout_encoding"] == "utf-8"
    assert Path(run["result"]["source_output"]).read_bytes()
    assert Path(run["result"]["published_output"]).read_bytes()


def test_semantic_failure_is_retained_and_not_published(tmp_path, monkeypatch):
    class FixedTemporaryDirectory:
        def __init__(self, **_kwargs):
            pass
        def __enter__(self):
            return str(tmp_path)
        def __exit__(self, *_args):
            return False

    source = tmp_path / "source"
    charter = source / "skills" / "charter" / "SKILL.md"
    charter.parent.mkdir(parents=True)
    charter.write_text(
        (compat.ROOT / "skills" / "charter" / "SKILL.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    def captured(command, *, cwd=None, timeout=None, binary=False):
        if command[:2] == ["git", "init"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        last_message = Path(command[command.index("--output-last-message") + 1])
        last_message.write_bytes(b'{"wrong":"answer"}')
        return subprocess.CompletedProcess(command, 0, b'{"type":"turn.completed"}\n', b"")

    monkeypatch.setattr(compat.tempfile, "TemporaryDirectory", FixedTemporaryDirectory)
    monkeypatch.setattr(compat, "_capture", captured)
    monkeypatch.setattr(compat, "ROOT", source)
    record_output = tmp_path.parent / f"{tmp_path.name}-semantic-records" / "semantic.md"
    with pytest.raises(compat.CompatError, match="did not match"):
        compat.run_probe(
            Path("codex"), model="gpt-5.6-sol", reasoning="high",
            record_output=record_output,
        )
    run = json.loads(compat.records.sidecar(record_output, ".run.json").read_bytes())
    assert run["outcome"] == "semantic_failure"
    assert Path(run["result"]["source_output"]).read_bytes() == b'{"wrong":"answer"}'
    assert run["result"]["published_output"] is None
    assert not record_output.exists()


def test_probe_answer_rejects_a_truncated_charter_tail():
    marker = "TRADECRAFT_CODEX_COMPAT_TEST"
    payload = compat._expected_probe_payload(marker)
    payload["tail"] = str(payload["tail"])[:-1]
    with pytest.raises(compat.CompatError, match="source charter evidence"):
        compat._assert_probe_answer(json.dumps(payload), marker)


def test_tail_requires_prose_even_when_the_charter_ends_in_public_skill_names(tmp_path, monkeypatch):
    charter = tmp_path / "skills/charter/SKILL.md"
    charter.parent.mkdir(parents=True)
    charter.write_text(
        "# Charter\n\n**Purpose:** fixture\n\nOpening prose.\n\n"
        "- **Convergence.** Settle the purpose.\n- **Release.** Human merges.\n\n"
        "This closing paragraph is\nnot available from the skill index.\n\n"
        "## Cells\n\n- `alpha` cell\n- `beta` cell\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(compat, "ROOT", tmp_path)
    marker = "TRADECRAFT_CODEX_COMPAT_TEST"
    payload = compat._expected_probe_payload(marker)
    assert payload["tail"] == "This closing paragraph is not available from the skill index."
    compat._assert_probe_answer(json.dumps(payload), marker)
    payload["tail"] = "- `alpha` cell - `beta` cell"
    with pytest.raises(compat.CompatError, match="source charter evidence"):
        compat._assert_probe_answer(json.dumps(payload), marker)


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_timeout_must_be_positive(value):
    with pytest.raises(
        compat.argparse.ArgumentTypeError,
        match="finite number greater than zero",
    ):
        compat._positive_timeout(value)


def test_timeout_accepts_fractional_seconds():
    assert compat._positive_timeout("2.5") == 2.5

"""Pins the deterministic half of the real Codex compatibility probe."""
from __future__ import annotations

import json
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
    assert command[command.index("--model") + 1] == "gpt-5.6-sol"
    assert 'model_reasoning_effort="high"' in command
    assert command[command.index("-C") + 1].endswith("consumer")
    assert "--skip-git-repo-check" in command
    assert command[-1] == compat.PROMPT


def test_plugin_check_requires_the_tree_version(monkeypatch):
    payload = {
        "installed": [{
            "pluginId": "tradecraft@tradecraft",
            "version": "0.49.0",
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
    compat._assert_plugin(Path("codex"), "0.49.0")
    with pytest.raises(compat.CompatError, match="this tree"):
        compat._assert_plugin(Path("codex"), "0.50.0")

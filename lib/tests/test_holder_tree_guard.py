import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import holder_tree_guard as guard


@pytest.fixture
def roots(tmp_path):
    protected = tmp_path / "Implementation Tree"
    outside = tmp_path / "holder"
    protected.mkdir()
    outside.mkdir()
    registry = tmp_path / "implementation-worktrees.json"
    registry.write_bytes((json.dumps({
        "schema_version": 1,
        "worktrees": [{"root": str(protected), "active": True}],
    }) + "\n").encode())
    return protected.resolve(), outside.resolve(), guard.active_roots(registry)


@pytest.mark.parametrize(("tool", "field"), [
    ("Edit", "file_path"), ("Write", "file_path"), ("NotebookEdit", "notebook_path"),
])
def test_each_file_tool_is_denied_inside_and_has_no_decision_outside(roots, tool, field):
    protected, outside, registered = roots
    inside_payload = {"tool_name": tool, "tool_input": {field: str(protected / "target.txt")}}
    outside_payload = {"tool_name": tool, "tool_input": {field: str(outside / "target.txt")}}
    assert "denied under registered" in guard.decision(inside_payload, registered)
    assert guard.decision(outside_payload, registered) is None


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_write_capable_shell_is_denied_inside_and_unanswered_outside(roots, tool):
    protected, outside, registered = roots
    command = "Set-Content target.txt changed" if tool == "PowerShell" else "echo changed > target.txt"
    assert guard.decision({"tool_name": tool, "cwd": str(protected),
                           "tool_input": {"command": command}}, registered)
    assert guard.decision({"tool_name": tool, "cwd": str(outside),
                           "tool_input": {"command": command}}, registered) is None


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_shell_command_naming_registered_target_is_denied_from_outside(roots, tool):
    protected, outside, registered = roots
    target = protected / "target.txt"
    command = f"Set-Content '{target}' changed" if tool == "PowerShell" else f"echo changed > '{target}'"
    assert guard.decision({"tool_name": tool, "cwd": str(outside),
                           "tool_input": {"command": command}}, registered)


@pytest.mark.parametrize("command", [
    "git status --porcelain", "git diff --stat", "Get-Content README.md", "Test-Path README.md",
])
def test_finite_read_only_commands_are_allowed_inside_registered_root(roots, command):
    protected, _outside, registered = roots
    assert guard.decision({"tool_name": "PowerShell", "cwd": str(protected),
                           "tool_input": {"command": command}}, registered) is None


@pytest.mark.parametrize("command", [
    "git status > state.txt", "git status; Set-Content x y", "pwsh -Command 'Get-Content x'",
    "python -c 'print(1)'", "Get-Content x | Set-Content y",
])
def test_unproved_or_nested_commands_are_denied_inside_registered_root(roots, command):
    protected, _outside, registered = roots
    assert guard.decision({"tool_name": "PowerShell", "cwd": str(protected),
                           "tool_input": {"command": command}}, registered)


def test_path_case_and_separator_normalization_matches_on_windows(roots):
    protected, _outside, registered = roots
    variant = str(protected / "nested" / "target.txt")
    if os.name == "nt":
        variant = variant.upper().replace("\\", "/")
    payload = {"tool_name": "Write", "tool_input": {"file_path": variant}}
    assert guard.decision(payload, registered)


def test_hook_reads_registry_afresh_for_each_call(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    target = tmp_path / "tree"
    target.mkdir()
    registry = guard.registry_path()
    registry.parent.mkdir()
    registry.write_bytes(b'{"schema_version":1,"worktrees":[]}\n')
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(target / "x")}}
    assert guard.decision(payload, guard.active_roots()) is None
    registry.write_bytes((json.dumps({"schema_version": 1, "worktrees": [
        {"root": str(target), "active": True}
    ]}) + "\n").encode())
    assert guard.decision(payload, guard.active_roots())


def test_main_emits_ascii_deny_json_and_silence_for_outside(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    protected = tmp_path / "tree"
    protected.mkdir()
    registry = guard.registry_path()
    registry.parent.mkdir()
    registry.write_bytes((json.dumps({"schema_version": 1, "worktrees": [
        {"root": str(protected), "active": True}
    ]}) + "\n").encode())
    payload = json.dumps({"tool_name": "Write", "tool_input": {
        "file_path": str(protected / ("snow-" + chr(0x2603)))
    }}).encode()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(payload), encoding="utf-8"))
    assert guard.main() == 0
    output = capsys.readouterr().out.encode("ascii")
    parsed = json.loads(output)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_configured_hook_process_denies_without_changing_revision_or_status(tmp_path):
    protected = tmp_path / "tree"
    protected.mkdir()
    subprocess.run(["git", "init", str(protected)], stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    before_revision = subprocess.run(
        ["git", "-C", str(protected), "rev-parse", "HEAD"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout
    before_status = subprocess.run(
        ["git", "-C", str(protected), "status", "--porcelain"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout
    registry = tmp_path / ".tradecraft" / "implementation-worktrees.json"
    registry.parent.mkdir()
    registry.write_bytes((json.dumps({"schema_version": 1, "worktrees": [
        {"root": str(protected), "active": True}
    ]}) + "\n").encode())
    payload = json.dumps({"tool_name": "Write", "tool_input": {
        "file_path": str(protected / "blocked.txt")
    }}).encode()
    result = subprocess.run(
        [sys.executable, str(LIB / "holder_tree_guard.py")], input=payload,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        env={**os.environ, "USERPROFILE": str(tmp_path)},
    )
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert not (protected / "blocked.txt").exists()
    assert subprocess.run(
        ["git", "-C", str(protected), "rev-parse", "HEAD"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout == before_revision
    assert subprocess.run(
        ["git", "-C", str(protected), "status", "--porcelain"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout == before_status

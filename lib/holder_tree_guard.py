#!/usr/bin/env python3
"""Refuse holder writes under a registered implementation worktree."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import sys

from winio import utf8_stdio

FILE_TOOLS = {"Edit": "file_path", "Write": "file_path", "NotebookEdit": "notebook_path"}
SHELL_TOOLS = {"Bash", "PowerShell"}
READ_ONLY_GIT = {
    "branch", "diff", "grep", "log", "rev-parse", "show", "status",
}
READ_ONLY_COMMANDS = {
    "get-childitem", "get-content", "ls", "pwd", "resolve-path", "select-string", "test-path",
}
SHELL_EFFECT = re.compile(r"(?:^|\s)(?:>|>>|<|2>|&>|tee\b|set-content\b|add-content\b|out-file\b)", re.I)
NESTED_OR_CHAINED = re.compile(r"(?:\$\(|`|&&|\|\||;|\r|\n)")
WINDOWS_ABSOLUTE = re.compile(r"(?i)(?:^|[\s'\"])([a-z]:[\\/][^'\"\r\n|;&<>]*)")


class GuardError(RuntimeError):
    """The registry or hook input cannot be read without weakening the guard."""


def registry_path() -> Path:
    return Path.home() / ".tradecraft" / "implementation-worktrees.json"


def canonical(path: Path, cwd: Path | None = None) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = (cwd or Path.cwd()) / candidate
    return candidate.resolve(strict=False)


def path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def contains(root: Path, target: Path) -> bool:
    root_key = path_key(root)
    target_key = path_key(target)
    try:
        return os.path.commonpath((root_key, target_key)) == root_key
    except ValueError:
        return False


def active_roots(path: Path | None = None) -> list[Path]:
    source = path or registry_path()
    try:
        value = json.loads(source.read_bytes())
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        raise GuardError(f"cannot read implementation worktree registry: {source}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("worktrees"), list):
        raise GuardError("implementation worktree registry has an unsupported shape")
    roots = []
    for row in value["worktrees"]:
        if not isinstance(row, dict) or row.get("active") is not True or not isinstance(row.get("root"), str):
            continue
        roots.append(canonical(Path(row["root"])))
    return roots


def _cwd(payload: dict[str, object], tool_input: dict[str, object]) -> Path:
    value = tool_input.get("cwd") or payload.get("cwd")
    return canonical(Path(value)) if isinstance(value, str) and value else Path.cwd().resolve()


def _command_paths(command: str, cwd: Path) -> list[Path]:
    found: list[Path] = []
    for match in WINDOWS_ABSOLUTE.finditer(command):
        found.append(canonical(Path(match.group(1).strip()), cwd))
    try:
        tokens = shlex.split(command, posix=False)
    except ValueError:
        tokens = []
    for token in tokens:
        value = token.strip("'\"(),")
        if not value or value.startswith("-"):
            continue
        if "/" not in value and "\\" not in value and not value.startswith("."):
            continue
        try:
            found.append(canonical(Path(value), cwd))
        except OSError:
            continue
    return found


def _read_only_shell(command: str) -> bool:
    stripped = command.strip()
    if not stripped or SHELL_EFFECT.search(stripped) or NESTED_OR_CHAINED.search(stripped):
        return False
    try:
        words = shlex.split(stripped, posix=False)
    except ValueError:
        return False
    if not words:
        return False
    executable = Path(words[0].strip("'\"")).name.lower()
    if executable in {"git", "git.exe"}:
        index = 1
        while index < len(words) and words[index] == "-C":
            index += 2
        return index < len(words) and words[index].lower() in READ_ONLY_GIT
    return executable in READ_ONLY_COMMANDS


def decision(payload: dict[str, object], roots: list[Path]) -> str | None:
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool, str) or not isinstance(tool_input, dict):
        raise GuardError("hook input must name tool_name and object tool_input")
    cwd = _cwd(payload, tool_input)
    if tool in FILE_TOOLS:
        value = tool_input.get(FILE_TOOLS[tool])
        if not isinstance(value, str) or not value:
            raise GuardError(f"{tool} input has no absolute target path")
        target = canonical(Path(value), cwd)
        if any(contains(root, target) for root in roots):
            return f"holder write denied under registered implementation root: {target}"
        return None
    if tool in SHELL_TOOLS:
        command = tool_input.get("command")
        if not isinstance(command, str):
            raise GuardError(f"{tool} input has no command")
        matched = any(contains(root, cwd) for root in roots)
        if not matched:
            matched = any(contains(root, path) for root in roots for path in _command_paths(command, cwd))
        if matched and not _read_only_shell(command):
            return "holder shell write denied under registered implementation root"
        return None
    return None


def denial(reason: str) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def main() -> int:
    utf8_stdio()
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise GuardError("hook input must be a JSON object")
        reason = decision(payload, active_roots())
    except (OSError, UnicodeError, ValueError, GuardError) as exc:
        reason = f"holder guard could not prove this write safe: {exc}"
    if reason:
        print(json.dumps(denial(reason), ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


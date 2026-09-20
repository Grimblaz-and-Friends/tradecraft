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
GIT_GLOBAL_FLAGS = {"--literal-pathspecs", "--no-optional-locks", "--no-pager", "-P"}
GIT_FLAGS = {
    "branch": {
        "--", "--all", "--contains", "--format", "--list", "--merged", "--no-color",
        "--no-contains", "--no-merged", "--points-at", "--remotes", "--show-current",
        "--sort", "--verbose", "-a", "-r", "-v", "-vv",
    },
    "diff": {
        "--", "--binary", "--cached", "--check", "--color", "--exit-code",
        "--ignore-all-space", "--ignore-blank-lines", "--ignore-space-at-eol",
        "--ignore-space-change", "--name-only", "--name-status", "--no-color",
        "--no-ext-diff", "--no-index", "--no-prefix", "--no-textconv", "--numstat",
        "--patch", "--quiet", "--raw", "--relative", "--shortstat", "--staged", "--stat",
        "--summary", "--text", "--unified", "--word-diff", "-p", "-s", "-u",
    },
    "grep": {
        "--", "--all-match", "--break", "--cached", "--count", "--files-with-matches",
        "--files-without-match", "--fixed-strings", "--full-name", "--heading",
        "--ignore-case", "--invert-match", "--line-number", "--name-only", "--quiet",
        "--show-function", "--text", "--word-regexp", "-F", "-L", "-l", "-n", "-q",
        "-v", "-w",
    },
    "log": {
        "--", "--all", "--author", "--branches", "--date", "--decorate", "--first-parent",
        "--follow", "--format", "--grep", "--max-count", "--merges", "--name-only",
        "--name-status", "--no-color", "--no-decorate", "--no-merges", "--no-patch",
        "--oneline", "--patch", "--pretty", "--remotes", "--reverse", "--shortstat",
        "--since", "--stat", "--tags", "--until", "-n", "-p", "-s",
    },
    "rev-parse": {
        "--", "--abbrev-ref", "--absolute-git-dir", "--git-common-dir", "--is-bare-repository",
        "--is-inside-git-dir", "--is-inside-work-tree", "--show-cdup", "--show-prefix",
        "--show-superproject-working-tree", "--show-toplevel", "--short", "--verify",
    },
    "show": {
        "--", "--binary", "--color", "--format", "--name-only", "--name-status", "--no-color",
        "--no-ext-diff", "--no-patch", "--no-textconv", "--numstat", "--oneline", "--patch",
        "--pretty", "--raw", "--shortstat", "--stat", "--summary", "--text", "--unified",
        "--word-diff", "-p", "-s", "-u",
    },
    "status": {
        "--", "--branch", "--ignore-submodules", "--long", "--no-ahead-behind", "--porcelain",
        "--short", "--show-stash", "--untracked-files", "-b", "-s",
    },
}
GIT_FLAG_PREFIXES = {
    "branch": ("--color=", "--format=", "--sort="),
    "diff": ("--color=", "--relative=", "--stat=", "--submodule=", "--unified=", "--word-diff=", "-U"),
    "grep": ("--context=", "--max-count=", "-A", "-B", "-C"),
    "log": ("--author=", "--date=", "--format=", "--grep=", "--max-count=", "--pretty=", "--since=", "--until="),
    "rev-parse": ("--short=",),
    "show": ("--color=", "--format=", "--pretty=", "--stat=", "--unified=", "--word-diff=", "-U"),
    "status": ("--ignore-submodules=", "--porcelain=", "--untracked-files="),
}
READ_ONLY_COMMAND_FLAGS = {
    "get-childitem": {
        "-attributes", "-depth", "-directory", "-exclude", "-file", "-filter", "-follow-symlink",
        "-force", "-hidden", "-include", "-literalpath", "-name", "-path", "-readonly",
        "-recurse", "-system",
    },
    "get-content": {
        "-delimiter", "-encoding", "-exclude", "-filter", "-force", "-include", "-literalpath",
        "-path", "-raw", "-readcount", "-stream", "-tail", "-totalcount", "-wait",
    },
    "ls": {"--all", "--directory", "--human-readable", "--long", "-1", "-a", "-al", "-d", "-h", "-l", "-la"},
    "pwd": {"-l", "-p"},
    "resolve-path": {"-literalpath", "-path", "-relative", "-relativebasepath"},
    "select-string": {
        "-allmatches", "-casesensitive", "-context", "-encoding", "-exclude", "-include", "-list",
        "-literalpath", "-notmatch", "-path", "-pattern", "-quiet", "-raw", "-simplematch",
    },
    "test-path": {"-isvalid", "-literalpath", "-newerthan", "-olderthan", "-path", "-pathtype"},
}
DANGEROUS_GIT_LONG = {
    "--config-env", "--exec-path", "--ext-diff", "--git-dir", "--output",
    "--output-directory", "--textconv", "--work-tree",
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
    for token in tokens[1:]:
        value = token.strip("'\"(),")
        if value.startswith("-") and "=" in value:
            value = value.split("=", 1)[1].strip("'\"")
        if not value or value.startswith("-"):
            continue
        try:
            found.append(canonical(Path(value), cwd))
        except OSError:
            continue
    return found


def _word(token: str) -> str:
    return token.strip("'\"")


def _dangerous_git_option(token: str) -> bool:
    if token == "-c" or (token.startswith("-c") and not token.startswith("--")):
        return True
    if token == "-o" or (token.startswith("-o") and not token.startswith("--")):
        return True
    return any(token == option or token.startswith(option + "=")
               for option in DANGEROUS_GIT_LONG)


def _read_only_git(words: list[str]) -> bool:
    index = 1
    while index < len(words):
        token = _word(words[index])
        if token == "-C":
            if index + 1 >= len(words) or _word(words[index + 1]).startswith("-"):
                return False
            index += 2
            continue
        if _dangerous_git_option(token):
            return False
        if token in GIT_GLOBAL_FLAGS:
            index += 1
            continue
        if token.startswith("-"):
            return False
        break
    if index >= len(words):
        return False
    subcommand = _word(words[index]).lower()
    if subcommand not in READ_ONLY_GIT:
        return False
    flags = GIT_FLAGS[subcommand]
    prefixes = GIT_FLAG_PREFIXES[subcommand]
    options_ended = False
    positional = []
    for raw in words[index + 1:]:
        token = _word(raw)
        if options_ended:
            positional.append(token)
            continue
        if token == "--":
            options_ended = True
            continue
        if _dangerous_git_option(token):
            return False
        if token.startswith("-") and token not in flags and not any(
            token.startswith(prefix) and len(token) > len(prefix) for prefix in prefixes
        ):
            return False
        if not token.startswith("-"):
            positional.append(token)
    if subcommand == "branch" and positional and "--list" not in words[index + 1:]:
        return False
    return True


def _read_only_command(executable: str, words: list[str]) -> bool:
    flags = READ_ONLY_COMMAND_FLAGS.get(executable)
    if flags is None:
        return False
    return all(
        not _word(raw).startswith("-") or _word(raw).lower() in flags
        for raw in words[1:]
    )


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
        return _read_only_git(words)
    return _read_only_command(executable, words)


def _registry_boundary() -> tuple[Path, Path]:
    registry = canonical(registry_path())
    return registry, registry.parent


def _shell_names_registry(command: str, cwd: Path) -> bool:
    registry, directory = _registry_boundary()
    lowered = command.lower().replace("\\", "/")
    named = (str(registry).lower().replace("\\", "/"),
             str(directory).lower().replace("\\", "/"),
             registry.name.lower(), directory.name.lower())
    if any(value and value in lowered for value in named):
        return True
    return any(contains(directory, path) for path in _command_paths(command, cwd))


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
        _registry, registry_directory = _registry_boundary()
        if contains(registry_directory, target):
            return "holder write denied: implementation worktree registry is not the holder's to edit"
        if any(contains(root, target) for root in roots):
            return f"holder write denied under registered implementation root: {target}"
        return None
    if tool in SHELL_TOOLS:
        command = tool_input.get("command")
        if not isinstance(command, str):
            raise GuardError(f"{tool} input has no command")
        read_only = _read_only_shell(command)
        _registry, registry_directory = _registry_boundary()
        if (_shell_names_registry(command, cwd)
                or (contains(registry_directory, cwd) and not read_only)):
            return "holder write denied: implementation worktree registry is not the holder's to edit"
        matched = any(contains(root, cwd) for root in roots)
        if not matched:
            matched = any(contains(root, path) for root in roots for path in _command_paths(command, cwd))
        if matched and not read_only:
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

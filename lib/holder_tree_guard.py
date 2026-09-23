#!/usr/bin/env python3
"""Refuse holder writes under a registered implementation worktree."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
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
        "--name-status", "--no-color", "--no-decorate", "--no-ext-diff", "--no-merges",
        "--no-patch", "--no-textconv", "--oneline", "--patch", "--pretty", "--remotes",
        "--reverse", "--shortstat", "--since", "--stat", "--tags", "--until", "-n",
        "-p", "-s",
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
GIT_HELPER_GUARDS = ("--no-textconv", "--no-ext-diff")
GIT_LOG_DIFF_FLAGS = {
    "--name-only", "--name-status", "--patch", "--shortstat", "--stat", "-p",
}
NESTED_SHELL_FLAGS = {
    "pwsh": {"-c", "-command"}, "powershell": {"-c", "-command"},
    "cmd": {"/c"},
}
POSIX_NESTED_SHELLS = {"bash", "sh", "zsh"}
POSIX_NESTED_OPTION_CHARS = frozenset("celx")
NESTED_BODY_DENIAL = (
    "holder shell write denied: nested command body cannot be identified "
    "or cannot be split"
)
DIRECTORY_COMMANDS = {"cd", "chdir", "pushd", "set-location"}
SHELL_EFFECT = re.compile(r"(?:^|\s)(?:>|>>|<|2>|&>|tee\b|set-content\b|add-content\b|out-file\b)", re.I)
NESTED_OR_CHAINED = re.compile(r"(?:\$\(|`|&&|\|\||;|\r|\n)")
NESTED_SHELL_TEXT = re.compile(
    r"(?i)(?:^|\s)(?:[^\s'\"]*[\\/])?"
    r"(?:bash|sh|zsh|pwsh|powershell|cmd)(?:\.exe)?(?:\s|$)"
    r"|(?:^|\s)eval\b"
)
WINDOWS_ABSOLUTE = re.compile(
    r'''(?ix)"([a-z]:[\\/][^"\r\n|;&<>]*)"'''
    r'''|'([a-z]:[\\/][^'\r\n|;&<>]*)'|(?<![\w.])([a-z]:[\\/][^\s'"\r\n|;&<>]*)'''
)
POSIX_ABSOLUTE = re.compile(
    r'''(?x)"(/[^"\r\n|;&<>]*)"'''
    r'''|'(/[^'\r\n|;&<>]*)'|(?<![\w.])(/[^\s'"\r\n|;&<>]*)'''
)


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


def _command_words(command: str) -> list[str] | None:
    words: list[str] = []
    current: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(command):
        character = command[index]
        if quote:
            if character == quote:
                quote = None
            elif character == "\\" and index + 1 < len(command) and command[index + 1] == quote:
                current.append(command[index + 1])
                index += 1
            else:
                current.append(character)
        elif character in {"'", '"'}:
            quote = character
        elif character == "\\" and index + 1 < len(command) and command[index + 1].isspace():
            current.append(command[index + 1])
            index += 1
        elif character.isspace():
            if current:
                words.append("".join(current))
                current = []
        else:
            current.append(character)
        index += 1
    if quote:
        return None
    if current:
        words.append("".join(current))
    return words


def _executable_name(value: str) -> str:
    name = value.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name.removesuffix(".exe")


def _split_commands(command: str) -> list[str] | None:
    commands: list[str] = []
    current: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(command):
        character = command[index]
        if quote:
            current.append(character)
            if character == quote:
                quote = None
        elif character in {"'", '"'}:
            quote = character
            current.append(character)
        elif character in {";", "\n", "\r"} or command[index:index + 2] in {"&&", "||"}:
            segment = "".join(current).strip()
            if not segment:
                return None
            commands.append(segment)
            current = []
            if command[index:index + 2] in {"&&", "||"}:
                index += 1
        else:
            current.append(character)
        index += 1
    if quote:
        return None
    segment = "".join(current).strip()
    if not segment:
        return None
    commands.append(segment)
    return commands


def _absolute_command_paths(command: str, cwd: Path) -> list[Path]:
    found = []
    for pattern in (WINDOWS_ABSOLUTE, POSIX_ABSOLUTE):
        for match in pattern.finditer(command):
            value = next(group for group in match.groups() if group is not None)
            found.append(canonical(Path(value), cwd))
    return found


def _quoted_paths(text: str, cwd: Path) -> list[Path]:
    found = []
    for match in re.finditer(r'''"([^"\r\n]+)"|'([^'\r\n]+)' ''', text, re.X):
        value = next(group for group in match.groups() if group is not None)
        try:
            found.append(canonical(Path(value), cwd))
        except OSError:
            continue
    return found


def _command_paths(command: str, cwd: Path) -> list[Path]:
    found = _absolute_command_paths(command, cwd)
    words = _command_words(command) or []
    for token in words[1:]:
        value = token.strip("(),")
        if value.startswith("-") and "=" in value:
            value = value.split("=", 1)[1]
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


def _git_subcommand(words: list[str]) -> tuple[int, str] | None:
    index = 1
    while index < len(words):
        token = _word(words[index])
        if token == "-C":
            index += 2
            continue
        if token in GIT_GLOBAL_FLAGS:
            index += 1
            continue
        if token.startswith("-"):
            return None
        return index, token.lower()
    return None


def _missing_git_helper_guards(words: list[str]) -> tuple[str, ...]:
    located = _git_subcommand(words)
    if located is None:
        return ()
    index, subcommand = located
    arguments = {_word(word).lower() for word in words[index + 1:]}
    helper_sensitive = subcommand == "diff"
    helper_sensitive = helper_sensitive or (
        subcommand == "show" and "--no-patch" not in arguments
    )
    helper_sensitive = helper_sensitive or (
        subcommand == "log" and bool(arguments & GIT_LOG_DIFF_FLAGS)
    )
    if not helper_sensitive:
        return ()
    return tuple(flag for flag in GIT_HELPER_GUARDS if flag not in arguments)


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
    if _missing_git_helper_guards(words):
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
    words = _command_words(stripped)
    if not words:
        return False
    executable = _executable_name(words[0])
    if executable == "git":
        return _read_only_git(words)
    return _read_only_command(executable, words)


def _nested_shell_body(words: list[str]) -> tuple[bool, str | None]:
    executable = _executable_name(words[0])
    if executable == "eval":
        return True, " ".join(words[1:]) if len(words) > 1 else None
    if executable in POSIX_NESTED_SHELLS:
        for index, word in enumerate(words[1:], 1):
            if not word.startswith("-") or word.startswith("--"):
                return True, None
            options = word[1:]
            if not options or any(option not in POSIX_NESTED_OPTION_CHARS for option in options):
                return True, None
            if "c" not in options:
                continue
            if index + 1 >= len(words) or index + 2 != len(words):
                return True, None
            return True, words[index + 1]
        return True, None
    flags = NESTED_SHELL_FLAGS.get(executable)
    if flags is None:
        return False, None
    if len(words) < 3 or words[1].lower() not in flags:
        return True, None
    return True, " ".join(words[2:])


def _inline_interpreter_text(words: list[str], command: str) -> str | None:
    executable = _executable_name(words[0])
    python = re.fullmatch(r"python(?:[0-9]+(?:\.[0-9]+)?)?", executable)
    flags = {"-c", "-"} if python else ({"-e", "-"} if executable in {"node", "perl"} else None)
    if flags is None:
        return None
    for index, word in enumerate(words[1:], 1):
        if word.lower() in flags:
            if word == "-":
                return command
            return " ".join(words[index + 1:]) or command
    return None


def _directory_target(words: list[str], cwd: Path) -> Path | None:
    if not words or _executable_name(words[0]) not in DIRECTORY_COMMANDS:
        return None
    arguments = words[1:]
    while arguments and arguments[0].lower() in {"-path", "-literalpath", "/d"}:
        arguments = arguments[1:]
    if not arguments:
        return None
    return canonical(Path(arguments[0]), cwd)


def _matches_root(paths: list[Path], roots: list[Path]) -> bool:
    return any(contains(root, path) for root in roots for path in paths)


def _shell_decision(command: str, cwd: Path, roots: list[Path], depth: int = 0) -> str | None:
    if depth > 12:
        return "holder shell write denied: nested command depth cannot be proved safe"
    words = _command_words(command)
    if words is None:
        if NESTED_SHELL_TEXT.search(command):
            return NESTED_BODY_DENIAL
        if _matches_root(_command_paths(command, cwd), roots):
            return "holder shell write denied under registered implementation root"
        return None

    is_nested, nested_body = _nested_shell_body(words)
    if is_nested:
        if not nested_body:
            return NESTED_BODY_DENIAL
        if _command_words(nested_body) is None or _split_commands(nested_body) is None:
            return NESTED_BODY_DENIAL
        reason = _shell_decision(nested_body, cwd, roots, depth + 1)
        if reason:
            return reason
        return None

    interpreter_text = _inline_interpreter_text(words, command)
    if interpreter_text is not None:
        paths = _command_paths(interpreter_text, cwd) + _quoted_paths(interpreter_text, cwd)
        if _matches_root(paths, roots):
            return "holder shell write denied: inline interpreter names an implementation root"

    segments = _split_commands(command)
    if segments is None:
        return "holder shell write denied: command sequence cannot be split"
    first_words = _command_words(segments[0]) or []
    if len(segments) > 1 or _directory_target(first_words, cwd) is not None:
        active_cwd = cwd
        for segment in segments:
            segment_words = _command_words(segment)
            if not segment_words:
                return "holder shell write denied: command sequence cannot be split"
            target = _directory_target(segment_words, active_cwd)
            if target is not None:
                active_cwd = target
                continue
            reason = _shell_decision(segment, active_cwd, roots, depth + 1)
            if reason:
                return reason
        return None

    read_only = _read_only_shell(command)
    matched = any(contains(root, cwd) for root in roots)
    if not matched:
        matched = _matches_root(_command_paths(command, cwd), roots)
    if matched and not read_only:
        missing = _missing_git_helper_guards(words)
        if missing:
            return "holder git read denied: add " + " and ".join(missing)
        return "holder shell write denied under registered implementation root"
    return None


def _registry_boundary() -> tuple[Path, Path]:
    registry = canonical(registry_path())
    return registry, registry.parent


def _shell_resolves_registry(command: str, cwd: Path) -> bool:
    _registry, directory = _registry_boundary()
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
        if (not read_only and (
                _shell_resolves_registry(command, cwd)
                or contains(registry_directory, cwd))):
            return "holder write denied: implementation worktree registry is not the holder's to edit"
        if not roots:
            return None
        return _shell_decision(command, cwd, roots)
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

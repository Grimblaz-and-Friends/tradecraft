#!/usr/bin/env python3
"""Refuse a dispatched session's GitHub writes outside its step's allowance.

Usage (the launcher supplies one of these; nobody runs it by hand):
    python <plugin-root>/lib/github_write_guard.py --hook --config FILE
    python <plugin-root>/lib/github_write_guard.py --prefix --config FILE -- COMMAND

``--hook`` is a PreToolUse command hook on Bash and PowerShell: it reads the
hook input on stdin and prints a deny decision for a refused command.
``--prefix`` is the use consumer's carrier, reached through the launch's
``CLAUDE_CODE_SHELL_PREFIX`` wrapper, because settings hooks do not run under
``--safe-mode``: it exits ``PREFIX_REFUSED_EXIT`` with the refusal on stderr, or 0 to let the
wrapper run the command. Every decision is one JSON line in the config's log,
so a refusal reaches the run record and the entrance report.

This is a tripwire on an unfenced shell, not a fence: a write made from inside
a script the shell starts is not seen. Design: lib/DESIGN.md#the-github-write-bound
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

from holder_tree_guard import contains, denial, path_key
from winio import utf8_stdio

REFUSED = "tradecraft GitHub write bound refused"
REQUEST_ROUTE = ("return this write to the holder as a request in a **Write requests** section "
                 "of your final message: the write, why the work needs it, and what it would leave behind")
CHILD_VARIABLE = "TRADECRAFT_CHILD_SETTINGS"
# A shell gives 126 to a command it found but could not run, so a refused command reads as one
# that never ran, apart from any exit code of the command's own.
PREFIX_REFUSED_EXIT = 126
CHILD_START = f'claude --setting-sources user --strict-mcp-config --settings "${CHILD_VARIABLE}"'
# Each changes where or what a git push writes, so a push carrying one is refused rather than
# judged from the stored configuration it overrides; a step's own push never needs one.
REDIRECTING_GIT_OPTIONS = {"-c", "--config-env", "--git-dir", "--work-tree", "--namespace"}
REDIRECTING_GIT_VARIABLES = {"GIT_DIR", "GIT_WORK_TREE", "GIT_NAMESPACE"}
# Every GIT_CONFIG* variable chooses or adds the configuration a push reads, so all are refused
# by prefix rather than by a list the next one would slip past.
REDIRECTING_GIT_PREFIX = "GIT_CONFIG"
# git's global options that take the next word as their value, and those that take none. An
# option in neither set ahead of the subcommand may have swallowed a word, so the subcommand
# cannot be read from what follows it.
GIT_VALUE_OPTIONS = {"--attr-source", "--super-prefix"}
GIT_FLAG_OPTIONS = {"-p", "--paginate", "-P", "--no-pager", "--no-replace-objects", "--no-lazy-fetch",
                    "--no-optional-locks", "--no-advice", "--bare", "--literal-pathspecs",
                    "--glob-pathspecs", "--noglob-pathspecs", "--icase-pathspecs"}
# Each prints something and exits, or runs help or version, so nothing after it is written.
GIT_ENDING_OPTIONS = {"--exec-path", "--html-path", "--man-path", "--info-path", "--version",
                      "--help", "-h", "-v"}
# Each writes refs to a remote outside `git push`; a step's own push goes through git push, so
# these are refused rather than judged.
GIT_OTHER_PUSHES = {"send-pack", "http-push"}
# git's own commands, which no alias can replace, so a subcommand outside them is looked up as
# a stored alias before it is judged.
GIT_BUILTINS = {
    "add", "am", "annotate", "apply", "archive", "bisect", "blame", "branch", "bundle", "cat-file",
    "check-attr", "check-ignore", "checkout", "cherry", "cherry-pick", "clean", "clone", "commit",
    "commit-tree", "config", "count-objects", "credential", "describe", "diff", "diff-files",
    "diff-index", "diff-tree", "fetch", "fetch-pack", "for-each-ref", "format-patch", "fsck", "gc",
    "grep", "hash-object", "help", "init", "log", "ls-files", "ls-remote", "ls-tree", "maintenance",
    "merge", "merge-base", "mv", "name-rev", "notes", "pull", "push", "range-diff", "read-tree",
    "rebase", "reflog", "remote", "request-pull", "reset", "restore", "rev-list", "rev-parse", "revert",
    "rm", "shortlog", "show", "show-ref", "sparse-checkout", "stash", "status", "submodule", "switch",
    "symbolic-ref", "tag", "update-index", "update-ref", "var", "version", "whatchanged", "worktree",
    "write-tree", "send-pack", "http-push", "subtree"}
CONNECTORS = "ENABLE_CLAUDEAI_MCP_SERVERS"
# Each turns off the command check or the connector switch in a session started
# from the shell, so no command may set or remove it.
GUARDED_VARIABLES = (CHILD_VARIABLE, "CLAUDE_CODE_SIMPLE", "CLAUDE_CODE_SHELL_PREFIX")
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "git-bash"}
POWERSHELLS = {"pwsh", "powershell"}
PASS_THROUGH = {"command", "exec", "nohup", "time", "builtin", "stdbuf", "timeout", "nice",
                "xargs"}
# Each option takes the next word as its value, which would otherwise sit where the program
# the pass-through runs is expected.
PASS_THROUGH_VALUES = {"nice": {"-n", "--adjustment"},
                       "timeout": {"-k", "--kill-after", "-s", "--signal"},
                       "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"},
                       "exec": {"-a"}, "time": {"-f", "--format", "-o", "--output"},
                       # GNU and BSD xargs. --eof, --replace and --max-lines take a value only
                       # joined by "=", so a separate word after them is the program.
                       "xargs": {"-a", "--arg-file", "-d", "--delimiter", "-E", "-I", "-L", "-n",
                                 "--max-args", "-P", "--max-procs", "-s", "--max-chars",
                                 "--process-slot-var", "-J", "-R", "-S"}}
# Each never runs a later word as a command, so a judged program's name among its arguments
# is text it reads, prints or passes to a script, not a command it starts.
INERT_PROGRAMS = {"echo", "printf", "grep", "egrep", "fgrep", "rg", "cat", "ls", "dir", "head",
                  "tail", "wc", "which", "where", "type", "less", "more", "diff", "sort", "uniq",
                  "cut", "tr", "test", "[", "true", "false", "sed", "awk", "jq", "pwd", "mkdir",
                  "touch", "cp", "mv", "rm", "tee", "dirname", "basename", "realpath", "stat",
                  "file", "python", "python3", "py", "pytest", "node", "get-content", "gc",
                  "select-string", "sls", "write-output", "write-host", "get-childitem", "gci",
                  "test-path", "set-content", "add-content", "out-file"}
REDIRECTS = {">", ">>", "<", ">&", "&>", "<&", ">|", "&>>", "<>", "<<<"}
SEPARATORS = {";", "&", "&&", "||", "|", "|&", "(", ")", ";;", ";&"}
GH_READS = {
    ("pr", "view"), ("pr", "list"), ("pr", "diff"), ("pr", "checks"), ("pr", "status"),
    ("issue", "view"), ("issue", "list"), ("issue", "status"),
    ("run", "view"), ("run", "list"), ("run", "watch"),
    ("workflow", "view"), ("workflow", "list"),
    ("repo", "view"), ("repo", "clone"),
    ("release", "view"), ("release", "list"), ("release", "download"),
    ("auth", "status"),
    # Read-only on GitHub: they list or download, and pr checkout writes only the local tree.
    ("label", "list"), ("run", "download"), ("pr", "checkout"), ("repo", "list"),
    ("gist", "list"), ("gist", "view"), ("secret", "list"), ("variable", "list"),
    ("variable", "get"), ("cache", "list"), ("ruleset", "list"), ("ruleset", "view"),
    ("ruleset", "check"),
}
GH_READ_COMMANDS = {"search", "status", "browse", "help", "version"}
GH_API_VALUE_FLAGS = {"-X", "--method", "-f", "--raw-field", "-F", "--field", "-H", "--header",
                      "--input", "-q", "--jq", "-t", "--template", "--hostname", "-p", "--preview",
                      "--cache", "-R", "--repo"}
GH_FIELD_FLAGS = {"-f", "--raw-field", "-F", "--field"}
REVIEW_MUTATIONS = {"resolveReviewThread", "addPullRequestReviewThreadReply"}
THREAD_ARGUMENTS = ("threadId", "pullRequestReviewThreadId")
TRIPWIRE = re.compile(
    r"\bgit\b.*\bpush\b|\bgh\s+[a-z]|(?:api|uploads)\.github\.com|"
    r"(?:^|[\s;&|(`$])(?:claude|codex)(?:\.exe)?(?:\s|$)",
    re.IGNORECASE | re.MULTILINE)
GITHUB_HOSTS = {"github.com", "www.github.com", "ssh.github.com"}
THREAD_LOOKUP = ("query($n:ID!){node(id:$n){... on PullRequestReviewThread"
                 "{pullRequest{number repository{nameWithOwner}}}}}")


class Unparsed(ValueError):
    """The text cannot be split into simple commands the check understands."""


@dataclass
class Context:
    cwd: str | None
    config: dict
    assigned: dict[str, str | None] = field(default_factory=dict)
    cleared: bool = False
    depth: int = 0
    docs: list[str] = field(default_factory=list)
    # The words of the commands piped into this one, which a shell reading stdin runs.
    piped: str = ""


@dataclass
class Finding:
    write: str
    reason: str


# --- splitting ----------------------------------------------------------------

HEREDOC_WORD = "__tradecraft_heredoc_{}__"
HEREDOC = re.compile(r"__tradecraft_heredoc_(\d+)__")
DELIMITER = re.compile(r"[ \t]*(?:'([^'\n]+)'|\"([^\"\n]+)\"|\\?([^\s;&|<>()'\"]+))")


def _scan(text: str, start: int = 0, closer: str | None = None
          ) -> tuple[str, list[str], list[str], int]:
    """Turn unquoted newlines into ';', and lift out substitutions and here-documents.

    Returns the outer text with each ``$( )`` or backtick body replaced by a
    placeholder word and each here-document operator replaced by a numbered
    placeholder word; the substitution bodies (each judged as its own command
    text); the here-document bodies, by number; and where scanning stopped.
    A here-document body is data unless a shell reads it, so a commit message
    that mentions ``git push`` is never mistaken for one.
    """
    out: list[str] = []
    subs: list[str] = []
    docs: list[str] = []
    pending: list[tuple[str, bool, int]] = []
    quote = None
    depth = 0
    i = start
    while i < len(text):
        char = text[i]
        if quote == "'":
            out.append(char)
            if char == "'":
                quote = None
            i += 1
            continue
        if char == "\\" and i + 1 < len(text):
            if text[i + 1] == "\n":
                i += 2
                continue
            out.append(text[i:i + 2])
            i += 2
            continue
        if char in "$<>" and text[i + 1:i + 2] == "(" and not (char in "<>" and quote):
            # $( ) runs its body, and so do <( ) and >( ), whose output stands in as a file.
            _out, _subs, _docs, end = _scan(text, i + 2, ")")
            subs.append(text[i + 2:end])
            out.append("__tradecraft_substitution__")
            i = end + 1
            continue
        if char == "`":
            end = text.find("`", i + 1)
            if end < 0:
                raise Unparsed("unbalanced backtick")
            subs.append(text[i + 1:end])
            out.append("__tradecraft_substitution__")
            i = end + 1
            continue
        if quote == '"':
            out.append(char)
            if char == '"':
                quote = None
            i += 1
            continue
        if closer and char == "(":
            depth += 1
        elif closer and char == ")":
            if depth == 0:
                if pending:
                    raise Unparsed("a here-document with no body")
                return "".join(out), subs, docs, i
            depth -= 1
        if char in "'\"":
            quote = char
        elif char == "<" and text[i + 1:i + 2] == "<" and text[i + 2:i + 3] != "<":
            j = i + 2
            strip = text[j:j + 1] == "-"
            if strip:
                j += 1
            match = DELIMITER.match(text, j)
            if not match:
                raise Unparsed("a here-document with no delimiter")
            delimiter = match.group(1) or match.group(2) or match.group(3)
            pending.append((delimiter, strip, len(docs)))
            docs.append("")
            out.append(" " + HEREDOC_WORD.format(len(docs) - 1) + " ")
            i = match.end()
            continue
        elif char == "\n":
            i += 1
            for delimiter, strip, index in pending:
                body: list[str] = []
                while True:
                    if i >= len(text):
                        raise Unparsed("an unterminated here-document")
                    end = text.find("\n", i)
                    line = text[i:] if end < 0 else text[i:end]
                    i = len(text) if end < 0 else end + 1
                    if (line.lstrip("\t") if strip else line) == delimiter:
                        break
                    body.append(line)
                docs[index] = "\n".join(body)
            pending = []
            out.append(";")
            continue
        out.append(char)
        i += 1
    if quote:
        raise Unparsed("unbalanced quote")
    if closer:
        raise Unparsed("unbalanced $( )")
    if pending:
        raise Unparsed("a here-document with no body")
    return "".join(out), subs, docs, i


OPERATORS = sorted(SEPARATORS | REDIRECTS, key=len, reverse=True)


def _operators(token: str) -> list[str]:
    """The separators and redirections a run of shell punctuation is made of.

    shlex joins adjacent punctuation into one token, so ``;(`` or ``&&(`` would otherwise
    hide the separator it holds and leave the next command inside the one before it.
    """
    found = []
    i = 0
    while i < len(token):
        for operator in OPERATORS:
            if token.startswith(operator, i):
                found.append(operator)
                i += len(operator)
                break
        else:
            raise Unparsed(f"shell punctuation {token!r} the check cannot read")
    return found


def split_commands(text: str) -> tuple[list[list[str]], list[str], list[str], list[str]]:
    """Simple commands as word lists, their command substitutions, here-document bodies, and
    for each command the words piped into it from earlier in its pipeline."""
    outer, subs, docs, _end = _scan(text)
    lexer = shlex.shlex(outer, posix=True, punctuation_chars="();<>|&")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError as exc:
        raise Unparsed(str(exc)) from exc
    commands: list[list[str]] = []
    feeds: list[str] = []
    pipeline: list[str] = []
    current: list[str] = []
    skip = False

    def close(operator: str) -> None:
        nonlocal current, pipeline
        if current:
            commands.append(current)
            feeds.append(" ".join(pipeline))
            pipeline = pipeline + current
        # A pipe, or a bracket around part of a pipeline, carries output on to what follows.
        if operator not in ("|", "|&", "(", ")"):
            pipeline = []
        current = []

    for token in tokens:
        if skip:
            skip = False
            continue
        if token and set(token) <= set("();<>|&"):
            for operator in _operators(token):
                if operator in SEPARATORS:
                    close(operator)
                    skip = False
                else:
                    if current and current[-1].isdigit():
                        current.pop()
                    skip = True
        else:
            current.append(token)
    close(";")
    return commands, subs, docs, feeds


def program(word: str) -> str:
    name = re.split(r"[\\/]", word)[-1].lower()
    for suffix in (".exe", ".cmd", ".bat", ".ps1"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.S)


def _record_assignment(ctx: Context, name: str, value: str | None) -> None:
    ctx.assigned[name] = value


# --- the decision ----------------------------------------------------------------

def decide(command: str, cwd: str | None, config: dict) -> dict[str, object]:
    """Allow or refuse one shell command text; never raises for a bad text."""
    ctx = Context(cwd=cwd, config=config)
    findings = judge_text(command, ctx)
    findings.extend(_variable_findings(ctx))
    if findings:
        first = findings[0]
        reason = (f"{REFUSED}: {first.reason}. This step's allowance is "
                  f"{describe(config['allowance'])}; {REQUEST_ROUTE}.")
        return {"decision": "deny", "reason": reason, "write": first.write}
    return {"decision": "allow", "reason": "no GitHub write outside the allowance", "write": None}


def _variable_findings(ctx: Context) -> list[Finding]:
    findings = []
    for name, value in ctx.assigned.items():
        if name == CONNECTORS and value != "false":
            findings.append(Finding(f"change {CONNECTORS}",
                f"{CONNECTORS} keeps claude.ai connectors off in every session this one starts; "
                "it may not be changed or removed"))
        elif name in GUARDED_VARIABLES:
            findings.append(Finding(f"change {name}",
                f"{name} carries the command check into a started session; it may not be "
                "set or removed"))
    return findings


def judge_text(text: str, ctx: Context) -> list[Finding]:
    # No command a step runs nests shells this deep; the limit bounds the recursion.
    if ctx.depth > 8:
        return [Finding("deeply nested command", "the command nests shells too deeply to judge")]
    try:
        commands, subs, docs, feeds = split_commands(text)
    except Unparsed as exc:
        return _tripwire(text, str(exc))
    outer_docs, ctx.docs = ctx.docs, docs
    findings: list[Finding] = []
    for sub in subs:
        findings.extend(judge_text(sub, Context(ctx.cwd, ctx.config, ctx.assigned, ctx.cleared,
                                                ctx.depth + 1)))
    outer_piped = ctx.piped
    for words, fed in zip(commands, feeds):
        ctx.piped = fed
        findings.extend(judge_simple(words, ctx))
    ctx.piped = outer_piped
    ctx.docs = outer_docs
    return findings


def _tripwire(text: str, why: str) -> list[Finding]:
    """Refuse text that cannot be split when it carries a signature of anything the check judges.

    The signatures cover every write and start the check refuses (a git push, any gh
    command, the GitHub API hosts, a Claude or Codex start), so text carrying none of them
    holds nothing the check would refuse and passes. An internal error is different: it
    leaves even a parsed command unjudged, so the entries fail closed on it.
    """
    if TRIPWIRE.search(text):
        return [Finding("unparsed command",
                        f"the command could not be parsed ({why}) and carries an unparsed "
                        "GitHub-write or session-start signature")]
    return []


SHELL_VALUE_OPTIONS = {"-o", "+o", "-O", "+O", "--rcfile", "--init-file"}


def _shell_script(arguments: list[str]) -> str | None:
    """The script operand a shell runs, or None when it reads its commands from stdin."""
    words = list(arguments)
    while words:
        word = words.pop(0)
        if word == "--":
            return words[0] if words else None
        if word in SHELL_VALUE_OPTIONS:
            if words:
                words.pop(0)
        elif word.startswith(("-", "+")) or HEREDOC.fullmatch(word):
            if word.startswith("-") and not word.startswith("--") and "s" in word[1:]:
                return None  # -s reads commands from stdin even with operands after it
        else:
            return word
    return None


def _inner(ctx: Context, text: str) -> list[Finding]:
    inner = Context(ctx.cwd, ctx.config, ctx.assigned, ctx.cleared, ctx.depth + 1)
    found = judge_text(text, inner)
    ctx.cleared = ctx.cleared or inner.cleared
    return found


def _split_string(words: list[str]) -> str | None:
    """Take env's -S/--split-string value off the front of ``words``, or None when it is not there."""
    flag = words[0]
    if flag in ("-S", "--split-string") and len(words) > 1:
        value = words[1]
        del words[:2]
        return value
    if flag.startswith("--split-string="):
        words.pop(0)
        return flag.split("=", 1)[1]
    if flag.startswith("-S") and len(flag) > 2:
        words.pop(0)
        return flag[2:]
    return None


# The pass-through fallback's test: after env or a pass-through program, a word outside this
# set stands where a program was expected, so the command is refused on its signature.
JUDGED_PROGRAMS = {"git", "gh", "claude", "codex", "cmd", "eval", "invoke-expression", "iex",
                   "curl", "wget", "invoke-restmethod", "irm", "invoke-webrequest", "iwr",
                   "npx", "bunx", "pnpx", "pnpm", "yarn", *SHELLS, *POWERSHELLS}


def judge_simple(words: list[str], ctx: Context) -> list[Finding]:
    words = list(words)
    local_cleared = False
    passed_through = False
    while words:
        match = ASSIGNMENT.match(words[0])
        if match and not words[0].startswith("-"):
            _record_assignment(ctx, match.group(1), match.group(2))
            words.pop(0)
            continue
        name = program(words[0])
        if name == "env":
            words.pop(0)
            passed_through = True
            while words:
                split = _split_string(words)
                if split is not None:
                    # env splits the string and runs it, with any words after it, as a command.
                    saved, ctx.cleared = ctx.cleared, ctx.cleared or local_cleared
                    try:
                        return _inner(ctx, " ".join([split, *(shlex.quote(word) for word in words)]))
                    finally:
                        ctx.cleared = saved
                if words[0] in ("-i", "--ignore-environment", "-"):
                    local_cleared = True
                    words.pop(0)
                elif words[0] in ("-u", "--unset") and len(words) > 1:
                    _record_assignment(ctx, words[1], None)
                    del words[:2]
                elif words[0].startswith("--unset="):
                    _record_assignment(ctx, words[0].split("=", 1)[1], None)
                    words.pop(0)
                elif words[0] in ("-C", "--chdir") and len(words) > 1:
                    ctx.cwd = _resolve_dir(ctx.cwd, words[1])
                    del words[:2]
                elif words[0].startswith("-"):
                    words.pop(0)
                elif ASSIGNMENT.match(words[0]):
                    match = ASSIGNMENT.match(words[0])
                    _record_assignment(ctx, match.group(1), match.group(2))
                    words.pop(0)
                else:
                    break
            continue
        if name in PASS_THROUGH:
            words.pop(0)
            passed_through = True
            while words and words[0].startswith("-"):
                flag = words.pop(0)
                if flag in PASS_THROUGH_VALUES.get(name, ()) and words:
                    words.pop(0)
            if name == "timeout" and words:
                _duration = words.pop(0)
            continue
        break
    if not words:
        return []
    first = words[0]
    name = program(first)
    if passed_through and name not in JUDGED_PROGRAMS:
        # A pass-through option nobody listed leaves its value where the program should be,
        # so a write after it is refused on its signature rather than passed unjudged.
        found = _tripwire(" ".join(words), f"{first!r} stands where a pass-through command's "
                                           "program was expected")
        if found:
            return found
    if first.startswith("$") and not first.lower().startswith("$env:"):
        return _tripwire(" ".join(words), "a variable in program position")
    cleared = ctx.cleared or local_cleared
    if name in ("export", "declare", "typeset", "local", "readonly"):
        for word in words[1:]:
            match = ASSIGNMENT.match(word)
            if match:
                _record_assignment(ctx, match.group(1), match.group(2))
        return []
    if name == "unset":
        for word in words[1:]:
            if not word.startswith("-"):
                _record_assignment(ctx, word, None)
        return []
    if first.lower().startswith("$env:"):
        variable = first[5:]
        if len(words) >= 3 and words[1] == "=":
            _record_assignment(ctx, variable, words[2])
        elif len(words) >= 2 and words[1].startswith("="):
            _record_assignment(ctx, variable, words[1][1:] or (words[2] if len(words) > 2 else ""))
        return []
    if name in ("remove-item", "ri", "del", "rm", "set-item", "si", "new-item", "ni"):
        targets = [w for w in words[1:] if w.lower().startswith("env:")]
        if targets:
            variable = targets[0][4:]
            value = None
            if name in ("set-item", "si", "new-item", "ni"):
                rest = [w for w in words[1:] if not w.lower().startswith("env:")]
                if "-Value" in rest or "-value" in [w.lower() for w in rest]:
                    lowered = [w.lower() for w in rest]
                    position = lowered.index("-value")
                    value = rest[position + 1] if position + 1 < len(rest) else ""
                else:
                    value = next((w for w in rest if not w.startswith("-")), "")
            _record_assignment(ctx, variable, value)
        return []
    if name in ("cd", "pushd", "set-location", "sl", "chdir"):
        target = next((w for w in words[1:] if not w.startswith("-")), None)
        if target:
            ctx.cwd = _resolve_dir(ctx.cwd, target)
        return []
    if name in SHELLS:
        for index, word in enumerate(words[1:], 1):
            if word.startswith("-") and not word.startswith("--") and "c" in word[1:]:
                if index + 1 < len(words):
                    return _inner(ctx, words[index + 1])
                return []
        # A shell reading a here-document runs its body; any other program reads it as data.
        found: list[Finding] = []
        reads_heredoc = False
        for word in words[1:]:
            match = HEREDOC.fullmatch(word)
            if match and int(match.group(1)) < len(ctx.docs):
                reads_heredoc = True
                found.extend(_inner(ctx, ctx.docs[int(match.group(1))]))
        if not reads_heredoc and ctx.piped and _shell_script(words[1:]) is None:
            # With no -c and no script, a shell runs what is piped into it; text piped from
            # earlier in this command line is in view, so its signatures are judged. A script
            # file read from stdin, as with bash < script.sh, stays out of reach.
            found.extend(_tripwire(ctx.piped, "a shell reading commands piped into it"))
        return found
    if name in POWERSHELLS:
        for index, word in enumerate(words[1:], 1):
            if word.lower() in ("-c", "-command", "/c", "/command"):
                return _inner(ctx, " ".join(words[index + 1:]))
            if word.lower() in ("-encodedcommand", "-ec", "-e"):
                return [Finding("encoded PowerShell command",
                                "an encoded PowerShell command cannot be judged")]
        return []
    if name == "cmd":
        for index, word in enumerate(words[1:], 1):
            if word.lower() in ("/c", "/k"):
                return _inner(ctx, " ".join(words[index + 1:]))
        return []
    if name in ("eval", "invoke-expression", "iex"):
        return _inner(ctx, " ".join(words[1:]))
    if name == "git":
        return judge_git(words[1:], ctx)
    if name.startswith("git-") and len(name) > 4:
        # git-push and its kin are git's own commands, named directly.
        return judge_git([name[4:], *words[1:]], ctx)
    if name == "gh":
        return judge_gh(words[1:], ctx)
    if name in ("curl", "wget", "invoke-restmethod", "irm", "invoke-webrequest", "iwr"):
        return judge_http(name, words[1:])
    if name in ("npx", "bunx", "pnpx", "pnpm", "yarn"):
        rest = [w for w in words[1:] if not w.startswith("-")]
        rest = rest[1:] if rest[:1] in (["dlx"], ["exec"]) else rest
        if rest and re.match(r"^@anthropic-ai/claude-code(@.*)?$", rest[0]):
            return judge_claude(words[words.index(rest[0]) + 1:], ctx, cleared)
        if rest and re.match(r"^@openai/codex(@.*)?$", rest[0]):
            return judge_codex(words[words.index(rest[0]) + 1:], ctx)
        return []
    if name == "claude":
        return judge_claude(words[1:], ctx, cleared)
    if name == "codex":
        return judge_codex(words[1:], ctx)
    if name not in INERT_PROGRAMS:
        # Any other program may run a later word as a command, as setsid, sudo or watch do, so
        # a judged program standing as its own word after it is judged as the command it starts.
        for index in range(1, len(words)):
            named = program(words[index])
            if named in JUDGED_PROGRAMS | PASS_THROUGH | {"env"} or named.startswith("git-"):
                found = judge_simple(words[index:], ctx)
                if found:
                    return found
    return []


# Git Bash writes drive C: as /c/, a path Windows itself cannot open, so it is converted.
GIT_BASH_DRIVE = re.compile(r"^/[A-Za-z]/")


def _resolve_dir(cwd: str | None, target: str) -> str | None:
    if target == "-":
        return cwd
    target = os.path.expanduser(target)
    if os.path.isabs(target) or re.match(r"^[A-Za-z]:[\\/]", target):
        return os.path.normpath(target)
    if GIT_BASH_DRIVE.match(target):
        return os.path.normpath(target[1] + ":" + target[2:])
    return os.path.normpath(os.path.join(cwd, target)) if cwd else None


def _run_git(cwd: str | None, *arguments: str) -> str | None:
    try:
        result = subprocess.run(["git", *(["-C", cwd] if cwd else []), *arguments],
                                capture_output=True, timeout=20, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode:
        return None
    return result.stdout.decode("utf-8", "replace").strip()


# --- git ------------------------------------------------------------------------

def _stored_alias(cwd: str | None, name: str) -> tuple[str, str | None]:
    """("none", None), ("alias", value), or ("unreadable", None) for a stored git alias."""
    try:
        result = subprocess.run(["git", *(["-C", cwd] if cwd else []), "config", "--get",
                                 f"alias.{name}"], capture_output=True, timeout=20,
                                stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return "unreadable", None
    if result.returncode == 1:
        return "none", None
    if result.returncode:
        return "unreadable", None
    return "alias", result.stdout.decode("utf-8", "replace").strip()


def judge_git(arguments: list[str], ctx: Context, expansions: int = 0) -> list[Finding]:
    """Judge every route git offers to write a remote: push, an alias, and the other pushes.

    A push made by any other program, or from inside a script, stays out of reach.
    """
    cwd = ctx.cwd
    words = list(arguments)
    redirecting: list[str] = []
    while words and words[0].startswith("-"):
        flag = words.pop(0)
        stem = flag.split("=", 1)[0]
        if flag == "-C" and words:
            cwd = _resolve_dir(cwd, words.pop(0))
        elif stem in REDIRECTING_GIT_OPTIONS:
            redirecting.append(stem)
            value = flag.split("=", 1)[1] if "=" in flag else (words.pop(0) if words else "")
            if stem in ("-c", "--config-env") and value.lower().startswith("alias."):
                # An alias defined on the command line can make any subcommand a push.
                return [Finding("git alias", "a git alias defined on the command line, which can "
                                "run a push or a shell under another name")]
        elif flag in GIT_ENDING_OPTIONS:
            # Bare --exec-path takes no value: like these others, git prints and stops there.
            return []
        elif stem in GIT_VALUE_OPTIONS or stem == "--exec-path":
            if "=" not in flag and words:
                words.pop(0)
        elif flag not in GIT_FLAG_OPTIONS:
            if "push" in words:
                return [Finding("git push", f"git push behind {stem}, an option this check cannot "
                                "read, so which subcommand runs is not known")]
            return []
    if any(name.startswith(REDIRECTING_GIT_PREFIX) and "alias." in str(value).lower()
           for name, value in ctx.assigned.items()):
        return [Finding("git alias", "a git alias defined in the environment, which can run a "
                        "push or a shell under another name")]
    if not words:
        return []
    subcommand = words[0]
    if subcommand == "config" and any(word.lower().startswith("alias.") for word in words[1:]) and not (
            {"--get", "--get-all", "--get-regexp", "-l", "--list"} & set(words[1:])
            or words[1:2] in (["get"], ["list"])):
        # A stored alias is resolved when it runs, but one stored and run in the same command
        # is not stored yet when the command is judged.
        return [Finding("git config alias", "storing a git alias, which can run a push or a shell "
                        "under another name")]
    if subcommand in GIT_OTHER_PUSHES or (subcommand == "subtree" and "push" in words[1:]):
        return [Finding(f"git {subcommand}", f"`git {subcommand}`, which writes refs to a remote; "
                        "a step's own push goes through git push")]
    if subcommand not in GIT_BUILTINS:
        found, value = _stored_alias(cwd, subcommand)
        if found == "unreadable":
            return [Finding(f"git {subcommand}", f"`git {subcommand}`, which may be an alias "
                            "whose configuration could not be read")]
        if found == "alias":
            if value.startswith("!") or expansions >= 5 or redirecting:
                return [Finding(f"git {subcommand}", f"the git alias {subcommand}, which runs a "
                                "shell command, nests too deeply, or runs under a redirecting option")]
            try:
                expanded = shlex.split(value)
            except ValueError:
                return [Finding(f"git {subcommand}", f"the git alias {subcommand}, which cannot be read")]
            prefix = ["-C", cwd] if cwd else []
            return judge_git([*prefix, *expanded, *words[1:]], ctx, expansions + 1)
    if subcommand != "push":
        return []
    redirecting.extend(name for name in ctx.assigned if name in REDIRECTING_GIT_VARIABLES
                       or name.startswith(REDIRECTING_GIT_PREFIX))
    if redirecting:
        return [Finding("git push", f"git push with {', '.join(sorted(set(redirecting)))}, which can "
                        "change where or what it writes")]
    return judge_push(words[1:], cwd, ctx.config)


def _github_repository(url: str) -> str | None:
    """owner/name of a GitHub URL, lowercased, or None for another host."""
    match = (re.match(r"^(?:https?|ssh|git)://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+?)/?$", url)
             or re.match(r"^(?:[^@/]+@)?([^/:]+):(?!//)(.+?)/?$", url))
    if not match or match.group(1).lower() not in GITHUB_HOSTS:
        return None
    path = match.group(2)
    if path.lower().endswith(".git"):
        path = path[:-4]
    parts = path.strip("/").split("/")
    return "/".join(parts[-2:]).lower() if len(parts) >= 2 else None


def _is_local(destination: str) -> bool:
    if destination.startswith("file://"):
        return True
    if "://" in destination:
        return False
    if re.match(r"^[A-Za-z]:[\\/]", destination) or destination.startswith(("/", "./", "../", "~")):
        return True
    return not re.match(r"^(?:[^@/]+@)?[^/:]+:", destination)


def judge_push(arguments: list[str], cwd: str | None, config: dict) -> list[Finding]:
    allowance = config["allowance"]
    always: list[str] = []
    positional: list[str] = []
    words = list(arguments)
    repo_option = None
    while words:
        word = words.pop(0)
        if word == "--":
            positional.extend(words)
            break
        if word.startswith("--"):
            stem = word.split("=", 1)[0]
            # Even onto the step's own branch: a forced or ref-wide push can erase history
            # others read, and the step needs only a fast-forward.
            if stem in ("--force", "--force-with-lease", "--force-if-includes", "--all",
                        "--mirror", "--tags", "--follow-tags", "--delete", "--prune", "--branches"):
                always.append(stem)
            elif stem == "--repo":
                repo_option = word.split("=", 1)[1] if "=" in word else (words.pop(0) if words else "")
            elif stem in ("--push-option", "--receive-pack", "--exec") and "=" not in word and words:
                # Each takes its value as the next word; --signed takes none.
                words.pop(0)
        elif word.startswith("-") and len(word) > 1:
            for letter in word[1:]:
                if letter == "f":
                    always.append("--force")
                elif letter == "d":
                    always.append("--delete")
            # A value-taking short option must end its cluster, so only a cluster ending in
            # -o (--push-option) takes the next word as its value.
            if word[-1] == "o" and words:
                words.pop(0)
        else:
            positional.append(word)
    # As git does: a repository named on the command line wins over --repo.
    destination = positional[0] if positional else repo_option
    refspecs = positional[1:] if positional else []
    if destination is None:
        current = _run_git(cwd, "symbolic-ref", "--short", "-q", "HEAD")
        remote = None
        if current:
            remote = (_run_git(cwd, "config", f"branch.{current}.pushRemote")
                      or _run_git(cwd, "config", "remote.pushDefault")
                      or _run_git(cwd, "config", f"branch.{current}.remote"))
        destination = remote or "origin"
    if _is_url_or_path(destination):
        urls = [destination]
    else:
        resolved = _run_git(cwd, "remote", "get-url", "--push", "--all", destination)
        if resolved:
            urls = resolved.splitlines()
        elif cwd and os.path.isdir(os.path.join(cwd, destination)):
            urls = [os.path.join(cwd, destination)]
        else:
            return [Finding(f"git push to {destination}",
                            f"push destination {destination} could not be resolved")]
    if all(_is_local(url) for url in urls):
        return []
    write = f"git push to {destination}"
    target = (allowance.get("repository") or "").lower()
    repositories = []
    for url in urls:
        if _is_local(url):
            continue
        repository = _github_repository(url)
        if repository is None:
            return [Finding(write, f"push destination {url} is not a GitHub repository this step may write")]
        grant_refs = _push_grant_refs(allowance, repository)
        if not permits_push(allowance) or (repository != target and not grant_refs):
            return [Finding(write, f"a push to {repository}")]
        repositories.append(repository)
    if always:
        # No grant lifts these: a grant allows exactly its own ref, and a ref-wide push such as
        # --tags pushes every local ref of its kind, not just the granted one.
        return [Finding(write, f"git push with {', '.join(sorted(set(always)))}")]
    destinations = _destination_refs(refspecs, cwd, destination)
    if destinations is None:
        return [Finding(write, "the push's destination ref could not be resolved")]
    for repository in repositories:
        # Each ref counts only on its own repository: a grant's on the grant's, and the step's
        # branch on the step's, so a grant elsewhere never carries the step's branch there.
        allowed = set(_push_grant_refs(allowance, repository))
        if (repository == target and allowance.get("kind") in ("branch", "review-disposition")
                and allowance.get("branch")):
            allowed.add("refs/heads/" + allowance["branch"])
        for ref, problem in destinations:
            if problem:
                return [Finding(write, problem)]
            if ref not in allowed:
                return [Finding(write, f"a push to {ref}")]
    return []


def _is_url_or_path(destination: str) -> bool:
    return ("://" in destination or bool(re.match(r"^[^@/\s]+@[^/:]+:", destination))
            or bool(re.match(r"^[A-Za-z]:[\\/]", destination))
            or destination.startswith(("/", "./", "../", "~", ".\\", "..\\")))


def _destination_refs(refspecs: list[str], cwd: str | None, remote: str
                      ) -> list[tuple[str, str | None]] | None:
    if not refspecs:
        # Configuration can make a push that names no refspec write more than @{push}, deletions
        # included, so it is judged as @{push} only when nothing widens it.
        if _run_git(cwd, "config", "--get-all", f"remote.{remote}.push"):
            return [("", f"a push naming no refspec, which remote.{remote}.push widens")]
        if _run_git(cwd, "config", "--type=bool", "--get", f"remote.{remote}.mirror") == "true":
            return [("", f"a push naming no refspec, which remote.{remote}.mirror makes a mirror")]
        if (_run_git(cwd, "config", "--get", "push.default") or "").lower() == "matching":
            return [("", "a push naming no refspec under push.default=matching, which pushes every "
                         "matching branch")]
        current = _run_git(cwd, "symbolic-ref", "--short", "-q", "HEAD")
        push = _run_git(cwd, "rev-parse", "--symbolic-full-name", "@{push}")
        if not current or not push:
            return None
        prefix = f"refs/remotes/{remote}/"
        if not push.startswith(prefix):
            return None
        return [("refs/heads/" + push[len(prefix):], None)]
    refs: list[tuple[str, str | None]] = []
    for spec in refspecs:
        if spec.startswith("+"):
            refs.append(("", f"a forced refspec {spec}"))
            continue
        if ":" in spec:
            source, destination = spec.split(":", 1)
            if not destination:
                refs.append(("", f"a deletion refspec {spec}"))
                continue
            if not destination.startswith("refs/"):
                destination = "refs/heads/" + destination
            if not source:
                refs.append(("", f"a deletion refspec {spec}"))
                continue
        elif spec == "HEAD":
            current = _run_git(cwd, "symbolic-ref", "--short", "-q", "HEAD")
            if not current:
                return None
            destination = "refs/heads/" + current
        elif spec.startswith("refs/"):
            destination = spec
        elif _run_git(cwd, "rev-parse", "--verify", "--quiet", "refs/heads/" + spec):
            destination = "refs/heads/" + spec
        elif _run_git(cwd, "rev-parse", "--verify", "--quiet", "refs/tags/" + spec):
            destination = "refs/tags/" + spec
        else:
            return None
        # A tag needs no case of its own: its ref is matched against the grants like any other,
        # so only a granted tag passes.
        refs.append((destination, None))
    return refs


def permits_push(allowance: dict) -> bool:
    return allowance.get("kind") in ("branch", "review-disposition") or any(
        grant.get("write") == "push" for grant in allowance.get("grants") or ())


def _push_grant_refs(allowance: dict, repository: str) -> list[str]:
    refs = []
    for grant in allowance.get("grants") or ():
        if grant.get("write") != "push":
            continue
        owner_name, _, ref = str(grant.get("target", "")).partition(":")
        if owner_name.lower() == repository.lower():
            refs.append(ref)
    return refs


# --- gh ---------------------------------------------------------------------------

def _gh_parts(words: list[str]) -> tuple[list[str], dict[str, list[str]], list[str]]:
    """Positional words, flag values, and boolean flags of a gh command."""
    positional: list[str] = []
    values: dict[str, list[str]] = {}
    booleans: list[str] = []
    rest = list(words)
    while rest:
        word = rest.pop(0)
        if word.startswith("-") and len(word) > 1:
            if "=" in word and word.startswith("--"):
                flag, value = word.split("=", 1)
                values.setdefault(flag, []).append(value)
            elif word in GH_API_VALUE_FLAGS or word in ("-b", "--body", "--body-file", "-t",
                                                         "--title", "-B", "--base", "-H", "--head"):
                values.setdefault(word, []).append(rest.pop(0) if rest else "")
            elif re.match(r"^-[fFXHRbq].+", word):
                values.setdefault(word[:2], []).append(word[2:])
            else:
                booleans.append(word)
        else:
            positional.append(word)
    return positional, values, booleans


def judge_gh(arguments: list[str], ctx: Context) -> list[Finding]:
    allowance = ctx.config["allowance"]
    positional, values, booleans = _gh_parts(arguments)
    if not positional:
        return []
    command = positional[0]
    if command in GH_READ_COMMANDS:
        return []
    if command == "api":
        return judge_gh_api(positional[1:], values, ctx)
    sub = positional[1] if len(positional) > 1 else ""
    if (command, sub) in GH_READS:
        return []
    write = "gh " + " ".join(positional[:2])
    if command in ("pr", "issue") and sub == "comment":
        if "--edit-last" in booleans or "--delete-last" in booleans:
            return [Finding(write, "editing or deleting an earlier comment")]
        repository = _gh_repository(values, ctx)
        if repository is None:
            return [Finding(write, "a comment whose repository is not this step's registered tree")]
        target = positional[2] if len(positional) > 2 else None
        number = _number_of(target, repository)
        if number is None and target is None and command == "pr":
            current = _run_git(ctx.cwd, "symbolic-ref", "--short", "-q", "HEAD")
            if current and current == allowance.get("branch"):
                number = allowance.get("pull_request")
        if number is not None and _comment_granted(allowance, repository, number):
            return []
        if (command == "pr" and allowance.get("kind") == "review-disposition"
                and repository == (allowance.get("repository") or "").lower()
                and number is not None and number == allowance.get("pull_request")):
            return []
        where = f"{repository}#{number}" if number is not None else repository
        return [Finding(write, f"a comment on {where}")]
    return [Finding(write, f"`{write}`, a GitHub write")]


def _gh_repository(values: dict[str, list[str]], ctx: Context) -> str | None:
    explicit = (values.get("-R") or values.get("--repo") or [None])[-1]
    if explicit:
        repo = explicit.strip()
        repo = re.sub(r"^https?://github\.com/", "", repo).removesuffix(".git").lower()
        return repo
    return _tree_repository(ctx)


def _tree_repository(ctx: Context) -> str | None:
    """The registered repository, when the effective directory is the registered tree."""
    root = ctx.config.get("root")
    if not root or not ctx.cwd or not contains(Path(root), Path(ctx.cwd)):
        return None
    return (ctx.config["allowance"].get("repository") or "").lower() or None


def _number_of(target: str | None, repository: str) -> int | None:
    if target is None:
        return None
    if target.isdigit():
        return int(target)
    match = re.match(r"^https?://github\.com/([^/]+/[^/]+)/(?:pull|issues)/(\d+)", target)
    if match and match.group(1).lower() == repository:
        return int(match.group(2))
    return None


def _comment_granted(allowance: dict, repository: str, number: int) -> bool:
    return any(grant.get("write") == "comment"
               and str(grant.get("target", "")).lower() == f"{repository}#{number}"
               for grant in allowance.get("grants") or ())


def api_target(target: str) -> str:
    """An api grant's ``METHOD path``, its path without the leading slash gh api drops too."""
    method, _, path = target.partition(" ")
    return f"{method} {path.lstrip('/')}"


def _api_granted(allowance: dict, method: str, path: str) -> bool:
    return any(grant.get("write") == "api" and api_target(str(grant.get("target", ""))) == f"{method} {path}"
               for grant in allowance.get("grants") or ())


def _fields(values: dict[str, list[str]]) -> dict[str, str]:
    fields = {}
    for flag in GH_FIELD_FLAGS:
        for value in values.get(flag, ()):
            name, _, content = value.partition("=")
            fields[name] = content
    return fields


def judge_gh_api(positional: list[str], values: dict[str, list[str]], ctx: Context) -> list[Finding]:
    allowance = ctx.config["allowance"]
    endpoint = positional[0] if positional else ""
    method = ((values.get("-X") or values.get("--method") or [None])[-1] or "").upper()
    fields = _fields(values)
    has_body = bool(fields) or "--input" in values
    if not method:
        # As gh does: given fields or --input and no method, it sends POST.
        method = "POST" if has_body else "GET"
    if endpoint == "graphql":
        return judge_graphql(fields, ctx)
    if method == "GET":
        return []
    path = endpoint.lstrip("/")
    if "{owner}" in path or "{repo}" in path:
        repository = _tree_repository(ctx)
        if repository is None:
            return [Finding(f"gh api {method} {endpoint}",
                            "{owner}/{repo} placeholders outside this step's registered tree")]
        owner, _, name = repository.partition("/")
        path = path.replace("{owner}", owner).replace("{repo}", name)
    write = f"gh api {method} {path}"
    if _api_granted(allowance, method, path):
        return []
    match = re.match(r"^repos/([^/]+/[^/]+)/issues/(\d+)/comments$", path, re.I)
    if method == "POST" and match and _comment_granted(allowance, match.group(1).lower(), int(match.group(2))):
        return []
    if method == "POST" and allowance.get("kind") == "review-disposition":
        own = f"repos/{allowance.get('repository')}".lower()
        number = allowance.get("pull_request")
        lowered = path.lower()
        if number is not None and (
                lowered == f"{own}/issues/{number}/comments"
                or re.fullmatch(re.escape(f"{own}/pulls/{number}/comments/") + r"\d+/replies", lowered)
                or (lowered == f"{own}/pulls/{number}/comments" and "in_reply_to" in fields)):
            return []
    return [Finding(write, f"`{write}`")]


def _graphql_document(fields: dict[str, str], cwd: str | None) -> str | None:
    query = fields.get("query")
    if query is None:
        return None
    if query.startswith("@"):
        # gh reads the file from the command's own directory, after any cd, not the hook's;
        # with no directory known, a relative file cannot be read as gh would read it.
        path = _resolve_dir(cwd, query[1:])
        if path is None:
            return None
        try:
            return Path(path).read_text(encoding="utf-8")
        except OSError:
            return None
    return query


def _mutation_fields(document: str) -> list[tuple[str, str]] | None:
    """Each top-level field of each mutation operation, with its argument text."""
    found: list[tuple[str, str]] = []
    for match in re.finditer(r"\bmutation\b[^{]*\{", document):
        depth, i = 1, match.end()
        start = i
        while i < len(document) and depth:
            if document[i] == "{":
                depth += 1
            elif document[i] == "}":
                depth -= 1
            i += 1
        body = document[start:i - 1]
        level = 0
        j = 0
        while j < len(body):
            char = body[j]
            if char in "{(":
                level += 1
            elif char in "})":
                level -= 1
            elif level == 0 and (char.isalpha() or char == "_"):
                name_match = re.match(r"[A-Za-z_]\w*(?:\s*:\s*([A-Za-z_]\w*))?", body[j:])
                name = name_match.group(1) or name_match.group(0)
                j += name_match.end()
                arguments = ""
                rest = body[j:].lstrip()
                if rest.startswith("("):
                    k = body.index("(", j)
                    depth_args, m = 1, k + 1
                    while m < len(body) and depth_args:
                        if body[m] == "(":
                            depth_args += 1
                        elif body[m] == ")":
                            depth_args -= 1
                        m += 1
                    arguments = body[k:m]
                    j = m
                found.append((name, arguments))
                continue
            j += 1
    return found


def judge_graphql(fields: dict[str, str], ctx: Context) -> list[Finding]:
    allowance = ctx.config["allowance"]
    document = _graphql_document(fields, ctx.cwd)
    if document is None:
        return [Finding("gh api graphql", "a GraphQL request whose document could not be read")]
    if not re.search(r"\bmutation\b", document):
        return []
    mutations = _mutation_fields(document) or [("unknown", "")]
    write = "gh api graphql mutation " + ", ".join(name for name, _ in mutations)
    if allowance.get("kind") != "review-disposition":
        return [Finding(write, f"the GraphQL mutation {', '.join(n for n, _ in mutations)}")]
    for name, arguments in mutations:
        if name not in REVIEW_MUTATIONS:
            return [Finding(write, f"the GraphQL mutation {name}")]
        match = re.search(r"\b(?:%s)\s*:\s*(\"([^\"]*)\"|\$(\w+))" % "|".join(THREAD_ARGUMENTS),
                          arguments)
        if not match:
            return [Finding(write, f"a {name} whose thread could not be read")]
        thread = match.group(2) if match.group(2) is not None else fields.get(match.group(3))
        if not thread:
            return [Finding(write, f"a {name} whose thread id variable has no value")]
        owner = thread_owner(thread)
        expected = (str(allowance.get("repository") or "").lower(), allowance.get("pull_request"))
        if owner is None or owner != expected:
            where = f"{owner[0]}#{owner[1]}" if owner else "an unconfirmed pull request"
            return [Finding(write, f"a {name} on a thread of {where}")]
    return []


def thread_owner(thread: str) -> tuple[str, int] | None:
    """(owner/name, number) of a review thread, read from GitHub; None when unreadable.

    A thread's id names no pull request, so this read is the only way to hold a reply or
    resolve to the allowance's own; an unreadable answer leaves it unconfirmed, and refused.
    """
    try:
        result = subprocess.run(["gh", "api", "graphql", "-f", f"query={THREAD_LOOKUP}",
                                 "-f", f"n={thread}"], capture_output=True, timeout=30,
                                stdin=subprocess.DEVNULL)
        value = json.loads(result.stdout)
        pull = value["data"]["node"]["pullRequest"]
        return pull["repository"]["nameWithOwner"].lower(), int(pull["number"])
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return None


# --- other HTTP clients and session starts ------------------------------------------

def judge_http(name: str, arguments: list[str]) -> list[Finding]:
    if not any(re.search(r"(?:api|uploads)\.github\.com", word, re.I) for word in arguments):
        return []
    lowered = [word.lower() for word in arguments]
    write = f"{name} to the GitHub API"
    if name in ("curl",):
        for index, word in enumerate(arguments):
            if word in ("-X", "--request") and index + 1 < len(arguments) \
                    and arguments[index + 1].upper() not in ("GET", "HEAD"):
                return [Finding(write, f"{write} with method {arguments[index + 1]}")]
            if re.match(r"^-X(?!GET$|HEAD$).+", word) or word.startswith("--request=") and \
                    word.split("=", 1)[1].upper() not in ("GET", "HEAD"):
                return [Finding(write, f"{write} with a non-GET method")]
            if word in ("-d", "-F", "-T", "--json", "--form", "--upload-file") or \
                    word.startswith(("--data", "-d", "--form", "--json")):
                return [Finding(write, f"{write} with a request body")]
        return []
    if name == "wget":
        if any(word.startswith(("--method", "--post-", "--body-")) and
               not re.match(r"--method=(?:GET|HEAD)$", word, re.I) for word in arguments):
            return [Finding(write, f"{write} with a non-GET method or body")]
        return []
    for index, word in enumerate(lowered):
        if word == "-method" and index + 1 < len(lowered) and lowered[index + 1] not in ("get", "head"):
            return [Finding(write, f"{write} with method {arguments[index + 1]}")]
        if word in ("-body", "-infile"):
            return [Finding(write, f"{write} with a request body")]
    return []


def _same_path(left: str, right: str) -> bool:
    return path_key(Path(left.replace("\\", "/"))) == path_key(Path(right.replace("\\", "/")))


def judge_claude(arguments: list[str], ctx: Context, cleared: bool) -> list[Finding]:
    write = "start a Claude session"
    head = [word for word in arguments if not word.startswith("-")][:2]
    if arguments[:1] and arguments[0] in ("--version", "-v", "--help", "-h"):
        return []
    if head[:1] == ["mcp"] and head[1:2] in (["list"], ["get"]):
        # These start no session, so nothing they run inherits the login.
        return []
    settings: list[str] = []
    sources: list[str] = []
    problems: list[str] = []
    strict = False
    words = list(arguments)
    while words:
        word = words.pop(0)
        stem, _, inline = word.partition("=")
        if stem == "--settings":
            settings.append(inline if inline else (words.pop(0) if words else ""))
        elif stem == "--setting-sources":
            sources.append(inline if inline else (words.pop(0) if words else ""))
        elif stem in ("--safe-mode", "--bare"):
            problems.append(f"{stem} turns off the launch's command check")
        elif stem == "--strict-mcp-config":
            strict = True
        elif stem == "--mcp-config":
            problems.append("--mcp-config loads an MCP server, a write path the command check never sees")
    expected = ctx.config.get("child_settings")
    if len(settings) != 1:
        problems.append("it must carry exactly one --settings, the launch's own child settings")
    else:
        value = settings[0].strip()
        if value.startswith("{"):
            problems.append("an inline --settings")
        elif value not in ("$" + CHILD_VARIABLE, "${" + CHILD_VARIABLE + "}", "$env:" + CHILD_VARIABLE) \
                and not (expected and _same_path(value, expected)):
            problems.append("its --settings is not the launch's own child settings")
    named = {part.strip() for value in sources for part in value.split(",")}
    if "user" not in named or named & {"project", "local"}:
        problems.append("it must carry --setting-sources user and name neither project nor local")
    if not strict:
        # Without it a child loads the owner's MCP servers, a write path this check never sees,
        # as the connectors are.
        problems.append("it must carry --strict-mcp-config, so it loads no MCP server")
    if cleared:
        problems.append("env -i drops the launch environment")
    if problems:
        return [Finding(write, "a Claude session start outside the launch's settings: "
                        + "; ".join(problems) + f"; start a child only as `{CHILD_START} ...`")]
    return []


def judge_codex(arguments: list[str], ctx: Context) -> list[Finding]:
    if arguments[:1] and arguments[0] in ("--version", "-V", "--help", "-h"):
        return []
    if arguments[:2] == ["execpolicy", "check"]:
        # It judges a command against rules and starts no session, so nothing inherits the login.
        return []
    return [Finding("start a Codex session",
                    "a Codex session start: no Codex session started from a dispatched step "
                    "can carry the launch's command check")]


def describe(allowance: dict) -> str:
    kind = allowance.get("kind")
    repository = allowance.get("repository")
    branch = allowance.get("branch")
    number = allowance.get("pull_request")
    if kind == "branch":
        text = f"`branch`: a push to refs/heads/{branch} of {repository}"
    elif kind == "review-disposition":
        text = (f"`review-disposition`: a push to refs/heads/{branch} of {repository}, a reply on "
                f"and a resolve of a review thread of {repository}#{number}, and a conversation "
                f"comment on {repository}#{number}")
    else:
        text = "`none`: no GitHub write"
    grants = [f"{grant.get('write')} {grant.get('target')}" for grant in allowance.get("grants") or ()]
    return text + (", with granted " + "; ".join(grants) if grants else "")


# --- entries ---------------------------------------------------------------------------

def _harness_command(argument: str) -> str:
    """The command the harness wrapped inside ``eval '<command>'``, or the whole string.

    Used only to name the command in the log: the decision judges the whole string,
    because the wrapper runs the whole string, eval body and anything around it.
    """
    match = re.search(r"\beval '((?:[^']|'\\'')*)'", argument)
    return match.group(1).replace("'\\''", "'") if match else argument


def _log(config: dict, entry: dict) -> str | None:
    """Append the decision to the launch's log; return why it could not be, or None."""
    log = config.get("log") if isinstance(config, dict) else None
    if not isinstance(log, str):
        return "the check's configuration names no log"
    try:
        with open(log, "ab") as stream:
            stream.write((json.dumps(entry, ensure_ascii=True) + "\n").encode("utf-8"))
    except OSError as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def _unrecorded(verdict: dict, problem: str | None) -> dict:
    """A refusal the log lost still refuses, and its own message says it reached no record."""
    if problem is None or verdict["decision"] != "deny":
        return verdict
    return {**verdict, "reason": f"{verdict['reason']} (this refusal could not be recorded in the "
                                 f"run record: {problem})"}


def _entry(config: dict, entry_kind: str, session, tool, command, verdict) -> dict:
    return {"at": datetime.now(timezone.utc).isoformat(), "scope": config.get("scope"),
            "entry": entry_kind, "session": session, "tool": tool, "command": command,
            "decision": verdict["decision"], "reason": verdict["reason"],
            "allowance": config.get("allowance")}


def run_hook(config_path: str) -> int:
    config: dict = {}
    command = None
    session = tool = None
    try:
        config = json.loads(Path(config_path).read_bytes())
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        tool = payload.get("tool_name")
        session = payload.get("session_id")
        tool_input = payload.get("tool_input") or {}
        command = tool_input.get("command")
        if tool not in ("Bash", "PowerShell"):
            return 0
        if not isinstance(command, str):
            raise ValueError("the tool input names no command")
        cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
        verdict = decide(command, cwd, config)
    except Exception as exc:  # Fail closed: an unjudged command is refused.
        verdict = {"decision": "deny",
                   "reason": f"{REFUSED}: the check could not evaluate this command: {exc}"}
    verdict = _unrecorded(verdict, _log(config, _entry(config, "hook", session, tool, command, verdict)))
    if verdict["decision"] == "deny":
        print(json.dumps(denial(str(verdict["reason"])), ensure_ascii=True, separators=(",", ":")))
    return 0


def run_prefix(config_path: str, arguments: list[str]) -> int:
    config: dict = {}
    command = None
    try:
        config = json.loads(Path(config_path).read_bytes())
        if len(arguments) != 1:
            verdict = {"decision": "deny", "reason": f"{REFUSED}: unexpected prefix form "
                       f"({len(arguments)} arguments)"}
        else:
            command = _harness_command(arguments[0])
            verdict = decide(arguments[0], os.getcwd(), config)
    except Exception as exc:
        verdict = {"decision": "deny",
                   "reason": f"{REFUSED}: the check could not evaluate this command: {exc}"}
    verdict = _unrecorded(verdict, _log(config, _entry(config, "prefix", config.get("session"), "Bash",
                                                       command, verdict)))
    if verdict["decision"] == "deny":
        sys.stderr.write(str(verdict["reason"]) + "\n")
        sys.stderr.flush()
        return PREFIX_REFUSED_EXIT
    return 0


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    rest: list[str] = []
    if "--" in argv:
        index = argv.index("--")
        argv, rest = argv[:index], argv[index + 1:]
    cli = argparse.ArgumentParser(description="GitHub write bound command check.")
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument("--hook", action="store_true")
    mode.add_argument("--prefix", action="store_true")
    cli.add_argument("--config", required=True)
    args = cli.parse_args(argv)
    if args.hook:
        return run_hook(args.config)
    return run_prefix(args.config, rest)


if __name__ == "__main__":
    raise SystemExit(main())

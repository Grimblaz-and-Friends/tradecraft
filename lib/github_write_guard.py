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
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import urllib.parse

from holder_tree_guard import contains, denial, path_key
from winio import utf8_stdio

REFUSED = "tradecraft GitHub write bound refused"
# The monotonic end a caller sets for the check's own reads, as a self-test bounded as a whole
# does; a session's check sets none, and each read keeps its own bound.
READ_END: ContextVar[float | None] = ContextVar("tradecraft_github_check_read_end", default=None)
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
# git's own commands that can write a remote: push, the other pushes, and subtree's push.
GIT_REMOTE_WRITERS = GIT_OTHER_PUSHES | {"push", "subtree"}
# Configuration a push reads when it runs. Writing one is refused even with no push beside it: it
# changes what every later push writes, in a later command, step or started session too, none of
# which this command's judgment sees, and a step's own work never needs to change one.
PUSH_SHAPING_KEY = re.compile(
    r"^(alias\..+|remote\..+\.(push|pushurl|url|mirror)|remote\.pushdefault|push\.default"
    r"|push\.followtags|push\.recursesubmodules|submodule\.recurse"
    r"|branch\..+\.(pushremote|remote)|url\..+\.(insteadof|pushinsteadof))$")
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
# is text it reads, prints or passes to a script, not a command it starts. Some (python, node,
# sed, awk) can run commands from their own program text; the check reads commands, not what a
# program's own code runs, the limit lib/DESIGN.md#the-github-write-bound records.
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
    # An `env -i` ran ahead of this text, so what it starts runs without the bound's variables.
    cleared: bool = False
    depth: int = 0
    docs: list[str] = field(default_factory=list)
    # The words of the commands piped into this one, which a shell reading stdin runs.
    piped: str = ""
    # A variable's value is being judged in program position, which is followed only once.
    expanding: bool = False
    # Kept so a comment body given on standard input is read as the comment GitHub will post.
    inputs: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Finding:
    write: str
    reason: str


# --- splitting ----------------------------------------------------------------

HEREDOC_WORD = "__tradecraft_heredoc_{}__"
HEREDOC = re.compile(r"__tradecraft_heredoc_(\d+)__")
# What a command substitution leaves in its word: its output, which the check never sees.
SUBSTITUTION_WORD = "__tradecraft_substitution__"
# Their targets are read as a comment's body, which reaches gh on standard input.
STDIN_REDIRECTS = {"<", "<>", "<<<", "<&"}
DELIMITER = re.compile(r"[ \t]*(?:'([^'\n]+)'|\"([^\"\n]+)\"|\\?([^\s;&|<>()'\"]+))")


class HereDocument(str):
    """A here-document's body; ``expands`` when its delimiter was unquoted, so bash expands it."""
    expands = False


def _scan(text: str, start: int = 0, closer: str | None = None
          ) -> tuple[str, list[str], list[str], int]:
    """Turn unquoted newlines into ';', and lift out substitutions and here-documents.

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
            out.append(SUBSTITUTION_WORD)
            i = end + 1
            continue
        if char == "`":
            end = text.find("`", i + 1)
            if end < 0:
                raise Unparsed("unbalanced backtick")
            subs.append(text[i + 1:end])
            out.append(SUBSTITUTION_WORD)
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
        if char == "#" and (not out or out[-1][-1:] in (" ", "\t", ";", "&", "|", "(", ")")):
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
            continue
        if char in "<>":
            _drop_stream_number(out)
        if char in "'\"":
            quote = char
        elif text.startswith("<<<", i):
            # A here-string's data is its next word only; the lines after it are commands.
            out.append("<<<")
            i += 3
            continue
        elif char == "<" and text[i + 1:i + 2] == "<":
            j = i + 2
            strip = text[j:j + 1] == "-"
            if strip:
                j += 1
            match = DELIMITER.match(text, j)
            if not match:
                raise Unparsed("a here-document with no delimiter")
            delimiter = match.group(1) or match.group(2) or match.group(3)
            quoted = match.group(3) is None or text[match.start(3) - 1] == "\\"
            pending.append((delimiter, strip, len(docs), quoted))
            docs.append("")
            out.append(" " + HEREDOC_WORD.format(len(docs) - 1) + " ")
            i = match.end()
            continue
        elif char == "\n":
            i += 1
            for delimiter, strip, index, quoted in pending:
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
                docs[index] = HereDocument("\n".join(body))
                docs[index].expands = not quoted
                if not quoted:
                    # bash runs the substitutions of an unquoted body before the command starts.
                    subs.extend(_body_substitutions(docs[index]))
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


def _body_substitutions(body: str) -> list[str]:
    found = []
    i = 0
    while i < len(body):
        if body[i] == "\\":
            i += 2
        elif body.startswith("$(", i):
            _out, _subs, _docs, end = _scan(body, i + 2, ")")
            found.append(body[i + 2:end])
            i = end + 1
        elif body[i] == "`":
            end = body.find("`", i + 1)
            if end < 0:
                raise Unparsed("unbalanced backtick in a here-document")
            found.append(body[i + 1:end])
            i = end + 1
        else:
            i += 1
    return found


def _drop_stream_number(out: list[str]) -> None:
    """Drop a number joined to the redirection that follows, which names a stream, not an argument.

    Only a number that starts its word is one: ``x 13 > f`` passes 13 to the command.
    """
    k = len(out)
    while k and len(out[k - 1]) == 1 and out[k - 1].isdigit():
        k -= 1
    if k < len(out) and (k == 0 or out[k - 1][-1:] in (" ", "\t", ";", "&", "|", "(", ")")):
        del out[k:]


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


def split_commands(text: str) -> tuple[list[list[str]], list[str], list[str], list[str],
                                       list[list[tuple[str, str]]]]:
    """Each simple command's words, the substitutions and here-documents, the words piped into
    each command, and the (redirection, target) pairs that feed each command's standard input."""
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
    inputs: list[list[tuple[str, str]]] = []
    pipeline: list[str] = []
    current: list[str] = []
    current_inputs: list[tuple[str, str]] = []
    redirect: str | None = None  # The redirection whose target is the next token.

    def close(operator: str) -> None:
        nonlocal current, pipeline, current_inputs
        if current:
            commands.append(current)
            feeds.append(" ".join(pipeline))
            inputs.append(current_inputs)
            pipeline = pipeline + current
        # A pipe, or a bracket around part of a pipeline, carries output on to what follows.
        if operator not in ("|", "|&", "(", ")"):
            pipeline = []
        current = []
        current_inputs = []

    for token in tokens:
        if redirect:
            if redirect in STDIN_REDIRECTS:
                current_inputs.append((redirect, token))
            redirect = None
            continue
        if token and set(token) <= set("();<>|&"):
            for operator in _operators(token):
                if operator in SEPARATORS:
                    close(operator)
                    redirect = None
                else:
                    redirect = operator
        else:
            current.append(token)
            if HEREDOC.fullmatch(token):
                current_inputs.append(("<<", token))
    close(";")
    return commands, subs, docs, feeds, inputs


def program(word: str) -> str:
    name = re.split(r"[\\/]", word)[-1].lower()
    for suffix in (".exe", ".cmd", ".bat", ".ps1"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.S)


def _record_assignment(ctx: Context, name: str, value: str | None) -> None:
    # A later assignment cannot take back the value an earlier command already ran with.
    if name in ctx.assigned and _forbidden(name, ctx.assigned[name]):
        return
    ctx.assigned[name] = value


def _forbidden(name: str, value: str | None) -> bool:
    return (name == CONNECTORS and value != "false") or name in GUARDED_VARIABLES


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
        commands, subs, docs, feeds, inputs = split_commands(text)
    except Unparsed as exc:
        # A signature scan would pass a write it does not name, such as git send-pack.
        return [Finding("unparsed command", f"the command could not be parsed ({exc}), so what it "
                        "runs cannot be judged")]
    outer_docs, ctx.docs = ctx.docs, docs
    findings: list[Finding] = []
    for sub in subs:
        findings.extend(judge_text(sub, Context(ctx.cwd, ctx.config, ctx.assigned, ctx.cleared,
                                                ctx.depth + 1)))
    outer_piped, outer_inputs = ctx.piped, ctx.inputs
    for words, fed, given in zip(commands, feeds, inputs):
        ctx.piped, ctx.inputs = fed, given
        findings.extend(judge_simple(words, ctx))
    ctx.piped, ctx.inputs = outer_piped, outer_inputs
    ctx.docs = outer_docs
    return findings


def _tripwire(text: str, why: str) -> list[Finding]:
    """Refuse words the check cannot place when they carry a common write or start signature.

    These words parse but stand where the check cannot tell what runs. The signatures name the
    common routes, not every one, so refusing outright would refuse many ordinary commands to
    catch the rare one that writes.
    """
    if TRIPWIRE.search(text):
        return [Finding("unplaced command",
                        f"{why}, and the words carry a GitHub-write or session-start signature")]
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
    return judge_text(text, Context(ctx.cwd, ctx.config, ctx.assigned, ctx.cleared, ctx.depth + 1))


# PowerShell's parameters as the check reads them, spelled out in full or by their documented
# aliases. PowerShell also takes any unambiguous prefix, a colon-joined value and, in Windows
# PowerShell, a command given as plain words; the check cannot read those, so it refuses them.
POWERSHELL_COMMAND = {"-c", "-command", "/c", "/command"}
POWERSHELL_FILE = {"-f", "-file", "/f", "/file"}
POWERSHELL_FLAGS = {"-noprofile", "-nop", "-nologo", "-noninteractive", "-noni", "-noexit", "-sta",
                    "-mta", "-login", "-l", "-help", "-?", "-h", "-version", "-v"}
POWERSHELL_VALUES = {"-executionpolicy", "-ep", "-ex", "-windowstyle", "-w", "-workingdirectory",
                     "-wd", "-outputformat", "-of", "-o", "-inputformat", "-if", "-configurationname",
                     "-config", "-settingsfile"}


def _judge_powershell(name: str, words: list[str], ctx: Context) -> list[Finding]:
    rest = words[1:]
    while rest:
        word = rest.pop(0)
        lowered = word.lower()
        if lowered in POWERSHELL_COMMAND:
            return _inner(ctx, " ".join(rest))
        if lowered in POWERSHELL_FILE or (name == "pwsh" and not word.startswith(("-", "/"))):
            # A script file stays out of reach, as with bash script.sh; pwsh reads a bare word so.
            return []
        if lowered in POWERSHELL_FLAGS:
            continue
        if lowered in POWERSHELL_VALUES and rest:
            rest.pop(0)
            continue
        return [Finding(f"{name} {word}", f"{name} with {word}, a form whose command the check cannot "
                        "read (an encoded, abbreviated or positional command)")]
    return []


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


# Programs that start no session of their own, or whose start is judged as cleared, so an
# `env -i` ahead of them clears nothing the bound needs; a session a reader's own program text
# starts is the script limit INERT_PROGRAMS states.
CLEARED_PROGRAMS = INERT_PROGRAMS | {"git", "gh", "curl", "wget", "invoke-restmethod", "irm",
                                     "invoke-webrequest", "iwr", "claude", "codex"}
# The pass-through fallback's test: after env or a pass-through program, a word outside this
# set stands where a program was expected, so the command is refused on its signature.
JUDGED_PROGRAMS = {"git", "gh", "claude", "codex", "cmd", "eval", "invoke-expression", "iex",
                   "curl", "wget", "invoke-restmethod", "irm", "invoke-webrequest", "iwr",
                   "npx", "bunx", "pnpx", "pnpm", "yarn", *SHELLS, *POWERSHELLS}


def judge_simple(words: list[str], ctx: Context) -> list[Finding]:
    words = list(words)
    local_cleared = False
    passed_through = False
    appended = False
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
                elif (words[0] in ("-C", "--chdir") and len(words) > 1) or words[0].startswith("--chdir="):
                    target = words[0].split("=", 1)[1] if "=" in words[0] else words[1]
                    del words[:1 if "=" in words[0] else 2]
                    # The directory holds for env's own command, not for later ones on the line.
                    saved = ctx.cwd
                    ctx.cwd = _resolve_dir(ctx.cwd, target)
                    try:
                        return judge_simple(["env", *(["-i"] if local_cleared else []), *words], ctx)
                    finally:
                        ctx.cwd = saved
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
            appended = appended or name == "xargs"
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
    cleared = ctx.cleared or local_cleared
    if ctx.config["allowance"].get("kind") == "stretch":
        # Before the inert-program shortcut, which would pass `python <launcher>` unjudged.
        launcher = _launcher_call(words)
        if launcher:
            return [Finding(f"a direct call of {launcher}", LAUNCHER_REFUSED)]
    if appended and name not in INERT_PROGRAMS:
        # xargs adds words read from its input to the command, and the check sees none of them:
        # `printf ':refs/heads/main' | xargs git push origin` deletes a branch it never names.
        return [Finding(f"{first} behind xargs", f"{first} behind xargs, which runs it with words "
                        "the check cannot see")]
    if cleared and name not in CLEARED_PROGRAMS and not name.startswith("git-"):
        # Without the bound's variables, a shell or any program the check looks through can start
        # a session that carries no check; a Claude or Codex start is judged as cleared itself.
        return [Finding(f"env -i {first}", f"{first} under env -i, which clears the variables that "
                        "carry the command check into a session it may start")]
    if passed_through and name not in JUDGED_PROGRAMS and name not in INERT_PROGRAMS:
        # A pass-through option nobody listed leaves its value where the program should be,
        # so a write after it is refused on its signature rather than passed unjudged.
        found = _tripwire(" ".join(words), f"{first!r} stands where a pass-through command's "
                                           "program was expected")
        if found:
            return found
    if first.startswith("$") and not first.lower().startswith("$env:"):
        variable = re.fullmatch(r"\$(?:\{(\w+)\}|(\w+))", first)
        value = (ctx.assigned.get(variable.group(1) or variable.group(2))
                 if variable and not ctx.expanding else None)
        if value:
            # Assigned earlier on this command line, so the program it names is known; it is judged
            # as that program, once, so a value naming another variable is not followed further.
            try:
                expanded = shlex.split(value)
            except ValueError:
                expanded = []
            if expanded:
                ctx.expanding = True
                try:
                    return judge_simple([*expanded, *words[1:]], ctx)
                finally:
                    ctx.expanding = False
        return _tripwire(" ".join(words), "a variable in program position")
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
        return _judge_powershell(name, words, ctx)
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


def _read_timeout(seconds: float) -> float:
    end = READ_END.get()
    return seconds if end is None else max(0.001, min(seconds, end - time.monotonic()))


def _run_git(cwd: str | None, *arguments: str) -> str | None:
    try:
        result = subprocess.run(["git", *(["-C", cwd] if cwd else []), *arguments],
                                capture_output=True, timeout=_read_timeout(20), stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode:
        return None
    return result.stdout.decode("utf-8", "replace").strip()


# --- git ------------------------------------------------------------------------

def _stored_alias(cwd: str | None, name: str) -> tuple[str, str | None]:
    try:
        result = subprocess.run(["git", *(["-C", cwd] if cwd else []), "config", "--get",
                                 f"alias.{name}"], capture_output=True, timeout=_read_timeout(20),
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
    exec_moved: list[str] = []
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
            if stem == "--exec-path":
                # It moves where git finds a command it does not build in.
                exec_moved.append(stem)
            if "=" not in flag and words:
                words.pop(0)
        elif flag not in GIT_FLAG_OPTIONS:
            # The option may have taken the next word as its value, so the subcommand is either
            # of the next two words. Neither may be a route to a remote the check reads elsewhere:
            # a push, another push, subtree's push, or a stored alias (or one it cannot read).
            candidates = [word for word in words[:2] if not word.startswith("-")]
            if "push" in words or any(
                    word in GIT_REMOTE_WRITERS
                    or (word not in GIT_BUILTINS and _stored_alias(cwd, word)[0] != "none")
                    for word in candidates):
                return [Finding(f"git {stem}", f"git behind {stem}, an option this check cannot "
                                "read, so which subcommand runs is not known")]
            return []
    if any(name.startswith(REDIRECTING_GIT_PREFIX) and "alias." in str(value).lower()
           for name, value in ctx.assigned.items()):
        return [Finding("git alias", "a git alias defined in the environment, which can run a "
                        "push or a shell under another name")]
    if not words:
        return []
    subcommand = words[0]
    redirected = redirecting + exec_moved + [name for name in ctx.assigned if name in REDIRECTING_GIT_VARIABLES
                                or name.startswith(REDIRECTING_GIT_PREFIX) or name == "GIT_EXEC_PATH"]
    if redirected and subcommand not in GIT_BUILTINS:
        # The alias lookup reads the tree's own configuration, not the redirected one, so a
        # subcommand that may be an alias there cannot be read; a -C directory is followed instead.
        return [Finding(f"git {subcommand}", f"`git {subcommand}` under {', '.join(sorted(set(redirected)))}, "
                        "which may run an alias from a configuration the check does not read")]
    config_keys = [word for word in words[1:] if not word.startswith("-")]
    if subcommand == "config" and any(PUSH_SHAPING_KEY.match(word.lower()) for word in words[1:]) and not (
            {"--get", "--get-all", "--get-regexp", "-l", "--list"} & set(words[1:])
            or words[1:2] in (["get"], ["list"])
            # A key alone, with no value and no writing option, is git's short read form.
            or (len(config_keys) == 1 and not {"--unset", "--unset-all", "--add", "--replace-all",
                                               "--remove-section", "--rename-section", "--edit",
                                               "-e"} & set(words[1:]))):
        # Refused alone, not only beside a push: see PUSH_SHAPING_KEY.
        return [Finding("git config", "storing an alias or a push mapping, which changes what a "
                        "later push writes or runs")]
    if subcommand == "remote" and words[1:2] in (["set-url"], ["rename"]):
        # Refused alone for PUSH_SHAPING_KEY's reason: it changes where every later push writes.
        return [Finding(f"git remote {words[1]}", "changing a remote, which changes where a later "
                        "push writes")]
    if subcommand in GIT_OTHER_PUSHES or (subcommand == "subtree" and "push" in words[1:]):
        return [Finding(f"git {subcommand}", f"`git {subcommand}`, which writes refs to a remote; "
                        "a step's own push goes through git push")]
    if subcommand not in GIT_BUILTINS:
        found, value = _stored_alias(cwd, subcommand)
        if found == "unreadable":
            return [Finding(f"git {subcommand}", f"`git {subcommand}`, which may be an alias "
                            "whose configuration could not be read")]
        if found == "alias":
            # An alias may name another alias, which is followed here by hand; the limit, well
            # past any chain a step defines, bounds the recursion, a loop included.
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
            elif stem == "--recurse-submodules" and word != "--recurse-submodules=no":
                # It pushes submodule commits to their own remotes, other repositories.
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
        # git rewrites a URL by url.<base>.insteadOf and pushInsteadOf before it connects, and the
        # rewritten destination is not the one this check reads, so a matching rule refuses.
        rules = _run_git(cwd, "config", "--get-regexp", r"^url\..*\.(pushinsteadof|insteadof)$") or ""
        for line in rules.splitlines():
            prefix = line.split(" ", 1)[1] if " " in line else ""
            if prefix and destination.startswith(prefix):
                return [Finding(f"git push to {destination}", f"a push to {destination}, which a "
                                "stored URL rewrite sends elsewhere")]
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
    if "--no-follow-tags" not in arguments and _run_git(
            cwd, "config", "--type=bool", "--get", "push.followTags") == "true":
        # Stored, it pushes missing tags beside the branch, as --follow-tags does.
        return [Finding(write, "git push with push.followTags set, which also pushes tags")]
    if not {"--recurse-submodules=no", "--no-recurse-submodules"} & set(arguments) and (
            _run_git(cwd, "config", "--get", "push.recurseSubmodules") not in (None, "", "no")
            or _run_git(cwd, "config", "--type=bool", "--get", "submodule.recurse") == "true"):
        # Stored, either pushes submodule commits to their own remotes, as --recurse-submodules does.
        return [Finding(write, "git push with push.recurseSubmodules or submodule.recurse set, which "
                        "also pushes submodule commits to other repositories")]
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
        if (repository == target and allowance.get("kind") in ("branch", "review-disposition", "stretch")
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
    mapped = _run_git(cwd, "config", "--get-all", f"remote.{remote}.push")
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
        elif spec != "HEAD" and mapped:
            # git sends a named ref with no destination where remote.<name>.push maps it, which
            # this check does not read, so the push is refused rather than judged as same-named.
            # HEAD is not mapped: git sends it to the current branch.
            refs.append(("", f"a refspec {spec} naming no destination, which remote.{remote}.push maps"))
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
    return allowance.get("kind") in ("branch", "review-disposition", "stretch") or any(
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
    if allowance.get("kind") == "stretch" and command in ("pr", "issue"):
        return judge_gh_stretch(command, sub, arguments, positional, values, ctx)
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
    chosen = ctx.assigned["GH_REPO"] if "GH_REPO" in ctx.assigned else os.environ.get("GH_REPO")
    if chosen:
        return re.sub(r"^https?://github\.com/", "", chosen.strip()).removesuffix(".git").lower()
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
    # ASCII digits only: str.isdigit() also takes digits such as "²", which int() then rejects.
    if re.fullmatch(r"[0-9]+", target):
        return int(target)
    match = re.match(r"^https?://github\.com/([^/]+/[^/]+)/(?:pull|issues)/([0-9]+)", target)
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
        return judge_graphql(fields, ctx, values)
    if method == "GET":
        return []
    path = endpoint.lstrip("/")
    if "{owner}" in path or "{repo}" in path:
        repository = _gh_repository({}, ctx)
        if repository is None:
            return [Finding(f"gh api {method} {endpoint}",
                            "{owner}/{repo} placeholders outside this step's registered tree")]
        owner, _, name = repository.partition("/")
        path = path.replace("{owner}", owner).replace("{repo}", name)
    write = f"gh api {method} {path}"
    if _api_granted(allowance, method, path):
        return []
    if allowance.get("kind") == "stretch":
        return _judge_api_stretch(method, path, fields, values, ctx)
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


def _graphql_document(fields: dict[str, str], ctx: Context) -> str | None:
    query = fields.get("query")
    if query is None:
        return None
    if query.startswith("@"):
        # gh reads the file from the command's own directory, after any cd, not the hook's, so it
        # is read as a body file is: a regular file only, and none when no directory is known.
        return _body_file(ctx, query[1:])[0]
    return query


def _mutation_fields(document: str) -> list[tuple[str, str]] | None:
    found: list[tuple[str, str]] = []
    original = document
    # Brackets inside a string or a comment are content, so they are blanked for the structure
    # scan; the arguments are still sliced from the original text. A block string may hold an
    # escaped \""" without ending.
    document = re.sub(r'"""(?:\\"""|[\s\S])*?"""|"(?:\\.|[^"\\\n])*"|#[^\n]*',
                      lambda m: re.sub(r'[{}()"]', " ", m.group(0)), document)
    # A quote left over, or brackets that do not pair, leaves the mutation set unknown.
    if '"' in document or any(document.count(o) != document.count(c) for o, c in ("{}", "()")):
        return None
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
                    arguments = original[start + k:start + m]
                    j = m
                found.append((name, arguments))
                continue
            j += 1
    return found


def judge_graphql(fields: dict[str, str], ctx: Context,
                  values: dict[str, list[str]] | None = None) -> list[Finding]:
    allowance = ctx.config["allowance"]
    document = _graphql_document(fields, ctx)
    if document is None:
        return [Finding("gh api graphql", "a GraphQL request whose document could not be read")]
    if not re.search(r"\bmutation\b", document):
        return []
    mutations = _mutation_fields(document) or [("unknown", "")]
    write = "gh api graphql mutation " + ", ".join(name for name, _ in mutations)
    if allowance.get("kind") == "stretch":
        problem = _graphql_body_refusal(fields, values or {}, ctx)
        if problem:
            return [Finding(write, problem)]
    if allowance.get("kind") not in ("review-disposition", "stretch"):
        return [Finding(write, f"the GraphQL mutation {', '.join(n for n, _ in mutations)}")]
    for name, arguments in mutations:
        if name not in REVIEW_MUTATIONS:
            return [Finding(write, f"the GraphQL mutation {name}")]
        threads = _thread_values(arguments, fields)
        if not threads:
            return [Finding(write, f"a {name} whose thread could not be read")]
        for thread in threads:
            if not thread:
                return [Finding(write, f"a {name} whose thread id could not be read")]
            owner = thread_owner(thread)
            expected = (str(allowance.get("repository") or "").lower(), allowance.get("pull_request"))
            if allowance.get("kind") == "stretch":
                if owner is not None and owner[0] == expected[0] and _own_pull(allowance, owner[1]):
                    continue
                where = f"{owner[0]}#{owner[1]}" if owner else "an unconfirmed pull request"
                return [Finding(write, f"a {name} on a thread of {where}")]
            if owner is None or owner != expected:
                where = f"{owner[0]}#{owner[1]}" if owner else "an unconfirmed pull request"
                return [Finding(write, f"a {name} on a thread of {where}")]
    return []


def _thread_values(arguments: str, fields: dict[str, str]) -> list[str | None]:
    # Field names are found only outside strings and comments, so a reply body quoting
    # "threadId: ..." never stands in for the thread GitHub acts on; every one found is checked.
    masked = re.sub(r'"""(?:\\"""|[\s\S])*?"""|"(?:\\.|[^"\\\n])*"|#[^\n]*',
                    lambda m: (m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[-1]
                               if m.group(0).startswith('"') else " " * len(m.group(0))), arguments)
    values: list[str | None] = []
    for match in re.finditer(r"\b(?:%s)\s*:\s*" % "|".join(THREAD_ARGUMENTS), masked):
        value = re.match(r'"((?:\\.|[^"\\\n])*)"(?!")|\$(\w+)', arguments[match.end():])
        if not value:
            values.append(None)
        else:
            values.append(value.group(1) if value.group(1) is not None else fields.get(value.group(2)))
    return values


def thread_owner(thread: str) -> tuple[str, int] | None:
    """(owner/name, number) of a review thread, read from GitHub; None when unreadable.

    A thread's id names no pull request, so this read is the only way to hold a reply or
    resolve to the allowance's own; an unreadable answer leaves it unconfirmed, and refused.
    """
    try:
        result = subprocess.run(["gh", "api", "graphql", "-f", f"query={THREAD_LOOKUP}",
                                 "-f", f"n={thread}"], capture_output=True, timeout=_read_timeout(30),
                                stdin=subprocess.DEVNULL)
        value = json.loads(result.stdout)
        pull = value["data"]["node"]["pullRequest"]
        return pull["repository"]["nameWithOwner"].lower(), int(pull["number"])
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return None


# --- a stretch builder's own change ----------------------------------------------------
# Design: lib/DESIGN.md#a-builders-own-checks-and-writes

LAUNCHER_FILES = ("dispatch_seat.py", "dispatch_implementer.py", "dispatch_record.py")
LAUNCHER_REFUSED = ("a builder launches checks through the entrance (work.py run STAGE); a direct "
                    "launcher call is refused")
REPORT_MARKER = "tradecraft:check-report"
REPORT_REFUSED = ("a comment carrying tradecraft:check-report, which only the entrance posts from "
                  "the run that launched the check")
SEND_BACK_MARKER = "tradecraft:send-back"
SEND_BACK_REFUSED = ("a comment carrying tradecraft:send-back, which only the entrance posts when it "
                     "returns a change to its builder")
EDIT_REFUSED = "editing or deleting a comment, which keeps a posted report as the entrance posted it"
# Every name Python runs a script under: a versioned or windowless interpreter (`python3.12`,
# `pythonw`, `pyw`) runs one as `python` and `py` do.
PYTHON_NAME = re.compile(r"pythonw?(?:\d+(?:\.\d+)*)?|pyw?")


def _is_python(name: str) -> bool:
    return PYTHON_NAME.fullmatch(name) is not None


# Python's long options that take the next word as their value; any other long option takes none.
PYTHON_VALUE_OPTIONS = {"--check-hash-based-pycs"}
# Python's short options that take a value, from the rest of their word or else the next word.
PYTHON_VALUE_LETTERS = set("XWQ")
# A launcher given to one of these runs as it would under its own name.
MODULE_RUNNERS = {"cProfile", "profile", "pdb", "trace", "runpy", "coverage"}
# No label, reviewer or assignee: the reviewer label is `ready-reviewers`' write, not the builder's.
PR_CREATE_OPTIONS = {"--fill", "-f", "--title", "-t", "--body", "-b", "--body-file", "-F",
                     "--base", "-B", "--draft", "-d", "--head", "-H", "--repo", "-R"}
PR_EDIT_OPTIONS = {"--title", "-t", "--body", "-b", "--body-file", "-F", "--repo", "-R"}
GH_VALUE_OPTIONS = {"--title", "-t", "--body", "-b", "--body-file", "-F", "--base", "-B", "--head",
                    "-H", "--repo", "-R", "--label", "-l", "--reviewer", "-r", "--assignee", "-a",
                    "--milestone", "-m", "--project", "-p", "--add-label", "--remove-label",
                    "--add-reviewer", "--remove-reviewer", "--add-assignee", "--remove-assignee",
                    "--add-project", "--remove-project", "--template", "-T", "--recover"}
PULL_LOOKUP_JQ = "[.head.repo.full_name,.head.ref]"
BODY_ROUTE = "write the body to a file and pass it as --body-file FILE (gh api: -F body=@FILE)"
BODY_EXPANDED = ("a comment body holding `$` or a command substitution, which the shell may expand "
                 f"into text the check never sees; {BODY_ROUTE}")
BODY_PIPED = f"a comment body piped in from another command, whose output the check cannot read; {BODY_ROUTE}"
BODY_NO_INPUT = ("a comment body read from standard input with no here-document or file the check can "
                 f"read feeding it; {BODY_ROUTE}")
REPLY_ID_REFUSED = "a reply whose in_reply_to is not a comment id written as digits"
# JSON and GraphQL strings both decode \uXXXX; GraphQL also reads \u{X...}.
UNICODE_ESCAPE = re.compile(r"\\u(?:\{([0-9A-Fa-f]{1,6})\}|([0-9A-Fa-f]{4}))")
GRAPHQL_STRING = re.compile(r'"""(?:\\"""|[\s\S])*?"""|"(?:\\.|[^"\\\n])*"')


def _is_launcher(word: str) -> bool:
    return re.split(r"[\\/]", word)[-1].lower() in LAUNCHER_FILES


def _launcher_name(word: str) -> str | None:
    """The launcher file a word names, as a script path or as a module, or None."""
    if _is_launcher(word):
        return re.split(r"[\\/]", word)[-1]
    module = word.rsplit(".", 1)[-1] + ".py"
    return module if module in LAUNCHER_FILES else None


def _module_launcher(module: str, arguments: list[str]) -> str | None:
    """The launcher a `-m module` run calls: the module itself, or one a runner module is given."""
    name = module.rsplit(".", 1)[-1]
    if name + ".py" in LAUNCHER_FILES:
        return name + ".py"
    if name in MODULE_RUNNERS:
        # A runner's own options can't be told from its script, so any argument naming a launcher is one.
        return next(filter(None, map(_launcher_name, arguments)), None)
    return None


def _launcher_call(words: list[str]) -> str | None:
    """The launcher file a command runs as its program or as its interpreter's script, or None.

    A launcher named only as data, as in `git add lib/dispatch_seat.py`, is not a call.
    """
    if not words:
        return None
    if _is_launcher(words[0]):
        return re.split(r"[\\/]", words[0])[-1]
    name = program(words[0])
    if name == "uv":
        return _uv_launcher(words[1:])
    return _python_launcher(words[1:]) if _is_python(name) else None


def _python_launcher(words: list[str]) -> str | None:
    """The launcher an interpreter's arguments run: its script, its -m module, or one its -c code names.

    Short options cluster as Python reads them (`-um x`, `-Xutf8`): a letter that takes a value
    takes the rest of its word, or the next word when nothing is left, and -m and -c end the options.
    """
    rest = list(words)
    while rest:
        word = rest.pop(0)
        if word == "--":
            return re.split(r"[\\/]", rest[0])[-1] if rest and _is_launcher(rest[0]) else None
        if word.startswith("--"):
            if word in PYTHON_VALUE_OPTIONS and rest:
                rest.pop(0)
            continue
        if word.startswith("-") and len(word) > 1:
            for index, letter in enumerate(word[1:], 2):
                if letter in "mc" or letter in PYTHON_VALUE_LETTERS:
                    value = word[index:] or (rest.pop(0) if rest else "")
                    if letter == "m":
                        return _module_launcher(value, rest) if value else None
                    if letter == "c":
                        # Code can't be told from data, so a launcher named anywhere in it is a call.
                        return next((f for f in LAUNCHER_FILES if f[:-3] in value), None)
                    break
            continue
        return re.split(r"[\\/]", word)[-1] if _is_launcher(word) else None
    return None


def _uv_launcher(words: list[str]) -> str | None:
    """The launcher a uv command calls through `uv run`, after any of uv's own options, or None."""
    for index, word in enumerate(words):
        if word == "run":
            return _uv_run_launcher(words[index + 1:])
        if word.startswith("-"):
            continue
        # A word after an option may be that option's value (`uv --directory lib run`).
        if index and words[index - 1].startswith("-") and "=" not in words[index - 1]:
            continue
        return None
    return None


def _uv_run_launcher(words: list[str]) -> str | None:
    """The launcher the command after `uv run`'s own options calls, or None.

    Some of uv's options take a value (`--with pkg`) and the check cannot tell which, so each word
    after an option is read both ways: as that option's value, and as the program. Either reading
    that is a launcher call refuses. The first word that follows no option is the program, and
    what comes after it is judged as that program's own command, so a launcher named as data there
    (`uv run git add lib/dispatch_seat.py`) passes.
    """
    previous_is_option = False  # A word with no option before it is the program.
    for index, word in enumerate(words):
        if word == "--":
            return _launcher_call(words[index + 1:])
        module = None
        if word == "--module" or word.startswith("--module="):
            module = word.split("=", 1)[1] if "=" in word else (words[index + 1] if index + 1 < len(words) else "")
            after = words[index + 1 + ("=" not in word):]
        elif word.startswith("-") and not word.startswith("--") and "m" in word[1:]:
            # A short cluster ending in m takes the next word; one with text after m takes that text.
            tail = word[word.index("m", 1) + 1:]
            module = tail or (words[index + 1] if index + 1 < len(words) else "")
            after = words[index + 1 + (not tail):]
        if module:
            found = _module_launcher(module, after)
            if found:
                return found
        if word.startswith("-"):
            previous_is_option = True
            continue
        found = _launcher_call(words[index:])
        if found or not previous_is_option:
            return found
        previous_is_option = False
    return None


def _expands(word: str) -> bool:
    # Quotes are gone by the time a word is judged, so a `$` the shell left alone in single quotes
    # can't be told from one it expanded, and both are refused.
    return "$" in word or SUBSTITUTION_WORD in word


def _stdin_body(ctx: Context) -> tuple[str | None, str | None]:
    """The text a command reads on standard input, or why the check can't read it."""
    if ctx.piped:
        return None, BODY_PIPED
    if not ctx.inputs:
        return None, BODY_NO_INPUT
    texts = []
    for redirect, target in ctx.inputs:
        if redirect == "<<":
            index = int(HEREDOC.fullmatch(target).group(1))
            if index >= len(ctx.docs):
                return None, BODY_NO_INPUT
            doc = ctx.docs[index]
            # bash expands $ and backticks in a here-document whose delimiter was not quoted.
            if getattr(doc, "expands", False) and ("$" in doc or "`" in doc):
                return None, BODY_EXPANDED
            texts.append(doc)
        elif redirect == "<<<":
            if _expands(target):
                return None, BODY_EXPANDED
            texts.append(target)
        elif redirect == "<&":
            return None, f"a comment body read from a duplicated stream, which the check cannot read; {BODY_ROUTE}"
        else:
            text, problem = _body_file(ctx, target)
            if problem:
                return None, problem
            texts.append(text)
    return "\n".join(texts), None


def _body_file(ctx: Context, name: str) -> tuple[str | None, str | None]:
    """The text of a body file (``-`` for standard input), or why the check can't read it."""
    if name == "-":
        return _stdin_body(ctx)
    if _expands(name):
        return None, BODY_EXPANDED
    path = _resolve_dir(ctx.cwd, name)
    unread = (f"a comment body read from {name}, which the check could not read as a file; pass a "
              "readable file holding the body")
    try:
        # Only a regular file: a device or pipe such as /dev/stdin is not the text gh will read.
        if path is None or not Path(path).is_file():
            return None, unread
        return Path(path).read_text(encoding="utf-8", errors="replace"), None
    except OSError:
        return None, unread


def _unescaped(text: str) -> str:
    def decode(match: re.Match) -> str:
        try:
            return chr(int(match.group(1) or match.group(2), 16))
        except ValueError:
            return match.group(0)
    return UNICODE_ESCAPE.sub(decode, text)


def _json_strings(text: str) -> list[str]:
    """The text with its \\u escapes decoded, and every string a JSON request body holds as GitHub decodes it."""
    found = [_unescaped(text)]
    try:
        # Pairs rather than a dict, so a key given twice keeps both values.
        stack = [json.loads(text, object_pairs_hook=lambda pairs: pairs)]
    except (ValueError, RecursionError):
        return found
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            found.append(item)
        elif isinstance(item, (list, tuple)):
            stack.extend(item)
    return found


def _body_refusal(ctx: Context, texts=(), files=(), inputs=(), scanned=()) -> str | None:
    """Why the body a comment would post is refused, or None when the check can read it and it
    carries no marker only the entrance posts.

    ``texts`` are bodies written in the command, ``files`` names whose text gh posts as it is
    (``-`` for standard input), ``inputs`` --input request bodies, whose JSON GitHub decodes, and
    ``scanned`` other text that only has to be free of the marker.
    """
    if any(_expands(text) for text in texts):
        return BODY_EXPANDED
    bodies = [*texts, *scanned, *ctx.docs, ctx.piped]
    for name in files:
        text, problem = _body_file(ctx, name)
        if problem:
            return problem
        bodies.append(text)
    for name in inputs:
        text, problem = _body_file(ctx, name)
        if problem:
            return problem
        bodies.extend([text, *_json_strings(text)])
    if any(REPORT_MARKER in body for body in bodies):
        return REPORT_REFUSED
    return SEND_BACK_REFUSED if any(SEND_BACK_MARKER in body for body in bodies) else None


def _field_entries(values: dict[str, list[str]]) -> list[tuple[str, str, str]]:
    """Every (flag, name, value) gh api fields carry, a name given twice included."""
    return [(flag, *value.partition("=")[::2]) for flag in ("-f", "--raw-field", "-F", "--field")
            for value in values.get(flag, ())]


def _field_bodies(values: dict[str, list[str]], skip=()) -> tuple[list[str], list[str]]:
    """The field values gh posts as written, and the files -F reads for `name=@file`."""
    texts, files = [], []
    for flag, name, value in _field_entries(values):
        if name in skip:
            continue
        if flag in ("-F", "--field") and value.startswith("@"):
            files.append(value[1:])
        else:
            texts.append(value)
    return texts, files


def _graphql_body_refusal(fields: dict[str, str], values: dict[str, list[str]], ctx: Context) -> str | None:
    """Why a stretch builder's GraphQL request is refused for its body, or None."""
    texts, files = _field_bodies(values, skip={"query"})
    query = fields.get("query", "")
    if query.startswith("@"):
        # A query file is sent as written, so its strings are read as an inline query's are.
        document, problem = _body_file(ctx, query[1:])
        if problem:
            return problem
        return _body_refusal(ctx, texts, files, scanned=[document, _unescaped(document)])
    # A `$` in a string, or a `$name` no field supplies, is the shell's expansion, not a variable.
    outside = GRAPHQL_STRING.sub(" ", query)
    if (SUBSTITUTION_WORD in query or any("$" in found.group(0) for found in GRAPHQL_STRING.finditer(query))
            or any(name not in fields for name in re.findall(r"\$(\w*)", outside))):
        return BODY_EXPANDED
    return _body_refusal(ctx, texts, files, scanned=[query, _unescaped(query)])


def _options(arguments: list[str]) -> list[str]:
    """The options a gh pr or issue command uses, skipping each value-taking option's value."""
    found, rest = [], list(arguments)
    while rest:
        word = rest.pop(0)
        if word == "--":
            break
        if word.startswith("-") and len(word) > 1:
            flag = word.split("=", 1)[0] if word.startswith("--") else word[:2]
            found.append(flag)
            if flag in GH_VALUE_OPTIONS and word == flag and rest:
                rest.pop(0)
    return found


def pull_owner(repository: str, number: int) -> tuple[str, str] | None:
    """(owner/name, branch) of a pull request's head, read from GitHub; None when unreadable.

    Like thread_owner, this read is the only way to hold a write to the pull request the builder
    opened after its launch; an unreadable answer leaves it unconfirmed, and refused.
    """
    try:
        result = subprocess.run(["gh", "api", "--method", "GET", f"repos/{repository}/pulls/{number}",
                                 "--jq", PULL_LOOKUP_JQ], capture_output=True,
                                timeout=_read_timeout(30), stdin=subprocess.DEVNULL)
        value = json.loads(result.stdout)
        return str(value[0]).lower(), str(value[1])
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError, IndexError):
        return None


def branch_pulls(repository: str, owner: str, branch: str) -> list[int] | None:
    """The numbers of the open pull requests in ``repository`` whose head is ``owner:branch``, read
    from GitHub; None when unreadable.

    Like pull_owner, this read is the only way to know which pull request a command that names
    none acts on; an unreadable answer leaves it unknown, and refused.
    """
    head = urllib.parse.quote(f"{owner}:{branch}", safe=":/")
    try:
        result = subprocess.run(["gh", "api", "--method", "GET",
                                 f"repos/{repository}/pulls?head={head}&state=open",
                                 "--jq", "[.[].number]"], capture_output=True,
                                timeout=_read_timeout(30), stdin=subprocess.DEVNULL)
        value = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if result.returncode or not isinstance(value, list) or any(type(n) is not int for n in value):
        return None
    return value


def _tracks_own_branch(ctx: Context, branch: str, repository: str) -> bool:
    """Whether gh, naming no pull request, looks for one headed by ``branch`` in ``repository``.

    gh takes the head from the branch's configuration: its merge ref (refs/pull/N/head names N
    outright) and the owner of the remote it pushes to or tracks.
    """
    merge = _run_git(ctx.cwd, "config", "--get", f"branch.{branch}.merge")
    if merge and merge != f"refs/heads/{branch}":
        return False
    for key in (f"branch.{branch}.pushRemote", "remote.pushDefault", f"branch.{branch}.remote"):
        remote = _run_git(ctx.cwd, "config", "--get", key)
        if remote and remote != ".":
            url = _run_git(ctx.cwd, "remote", "get-url", remote)
            if not url or _github_repository(url) != repository:
                return False
    return True


def _current_pull(ctx: Context, repository: str) -> int | None:
    """The pull request a gh pr command naming none acts on, where the check can establish it is
    the builder's own: the current branch is the builder's, gh looks it up as that branch of this
    repository, and exactly one open pull request there has it as its head. None otherwise."""
    branch = ctx.config["allowance"].get("branch")
    if not branch or _run_git(ctx.cwd, "symbolic-ref", "--short", "-q", "HEAD") != branch:
        return None
    if not _tracks_own_branch(ctx, branch, repository):
        return None
    numbers = branch_pulls(repository, repository.partition("/")[0], branch)
    return numbers[0] if numbers is not None and len(numbers) == 1 else None


def _own_pull(allowance: dict, number: int | None) -> bool:
    """Whether pull request ``number`` is the builder's own: the allowance's, or one opened from its branch."""
    if number is None:
        return False
    # The allowance's own number is confirmed by the same read: the launch was told it, not shown it.
    repository = str(allowance.get("repository") or "").lower()
    return pull_owner(repository, number) == (repository, allowance.get("branch"))


def _positive(text: str) -> bool:
    return re.fullmatch(r"[0-9]+", text) is not None and int(text) > 0


def judge_gh_stretch(command: str, sub: str, arguments: list[str], positional: list[str],
                     values: dict[str, list[str]], ctx: Context) -> list[Finding]:
    """A stretch builder's gh pr or gh issue command: its own pull request and issue only."""
    allowance = ctx.config["allowance"]
    write = f"gh {command} {sub}".strip()
    if (command, sub) in GH_READS:
        return []
    start = arguments.index(sub) + 1 if sub in arguments else len(arguments)
    options = _options(arguments[start:])
    if "--edit-last" in options or "--delete-last" in options:
        return [Finding(write, EDIT_REFUSED)]
    repository = _gh_repository(values, ctx)
    own_repository = str(allowance.get("repository") or "").lower()
    if repository is None or repository != own_repository:
        return [Finding(write, f"a write in {repository or 'a repository outside this step tree'}")]
    files = [*values.get("--body-file", ()), *values.get("-F", ())]
    bodies = [*values.get("--body", ()), *values.get("-b", ())]
    # A here-document stands in the words as a placeholder, not as the number a command names.
    positional = [word for word in positional if not HEREDOC.fullmatch(word)]
    target = positional[2] if len(positional) > 2 else None
    number = _number_of(target, repository)
    if command == "issue":
        if sub == "comment" and number is not None and number == allowance.get("issue"):
            problem = _body_refusal(ctx, bodies, files)
            return [Finding(write, problem)] if problem else []
        where = f" on {repository}#{target}" if target else ""
        return [Finding(write, f"`{write}`{where}, a write outside this step's own issue")]
    if sub == "create":
        unknown = sorted(set(options) - PR_CREATE_OPTIONS)
        if unknown:
            return [Finding(write, f"gh pr create with {', '.join(unknown)}")]
        heads = [*values.get("--head", ()), *values.get("-H", ())]
        branch = allowance.get("branch")
        owner = own_repository.partition("/")[0]
        if heads:
            head = heads[-1]
            if head.lower().startswith(owner + ":"):
                head = head.split(":", 1)[1]
            if head != branch:
                return [Finding(write, f"a pull request from {heads[-1]}")]
        elif _run_git(ctx.cwd, "symbolic-ref", "--short", "-q", "HEAD") != branch:
            return [Finding(write, "a pull request from a branch other than this step's own")]
        return []
    if sub not in ("ready", "comment", "edit"):
        return [Finding(write, f"`{write}`, a GitHub write")]
    if sub == "edit" and set(options) - PR_EDIT_OPTIONS:
        return [Finding(write, f"gh pr edit with {', '.join(sorted(set(options) - PR_EDIT_OPTIONS))}")]
    if sub == "ready" and set(options) - {"--undo", "--repo", "-R"}:
        return [Finding(write, "gh pr ready with an option other than --undo")]
    if target is None:
        # gh acts on the current branch's pull request, which only a live read can name.
        if _current_pull(ctx, repository) is None:
            return [Finding(write, f"a write on the current branch's pull request, which the check could "
                                   f"not establish as the one open pull request from {allowance.get('branch')} "
                                   f"in {repository}; name the pull request number")]
    elif not _own_pull(allowance, number):
        shown = number if number is not None else target
        return [Finding(write, f"a write on {repository}#{shown}, which is not this step's own "
                               "pull request")]
    if sub == "comment":
        problem = _body_refusal(ctx, bodies, files)
        if problem:
            return [Finding(write, problem)]
    return []


def _judge_api_stretch(method: str, path: str, fields: dict[str, str],
                       values: dict[str, list[str]], ctx: Context) -> list[Finding]:
    """A stretch builder's non-GET REST call: comments on its own issue and pull request, and thread replies."""
    allowance = ctx.config["allowance"]
    write = f"gh api {method} {path}"
    lowered = path.lower()
    if method in ("PATCH", "DELETE") and re.search(r"/comments(?:/|$)", lowered):
        return [Finding(write, EDIT_REFUSED)]
    if method != "POST":
        return [Finding(write, f"`{write}`")]
    own = f"repos/{allowance.get('repository')}".lower()
    texts, files = _field_bodies(values, skip={"in_reply_to"})
    problem = _body_refusal(ctx, texts, files, values.get("--input", ()))
    if problem:
        return [Finding(write, problem)]
    issue = re.fullmatch(re.escape(own) + r"/issues/([0-9]+)/comments", lowered)
    if issue:
        number = int(issue.group(1))
        if number == allowance.get("issue") or _own_pull(allowance, number):
            return []
        return [Finding(write, f"a comment on {allowance.get('repository')}#{number}")]
    pull = re.fullmatch(re.escape(own) + r"/pulls/([0-9]+)/comments(?:/([0-9]+)/replies)?", lowered)
    if pull:
        replies = [value for _flag, name, value in _field_entries(values) if name == "in_reply_to"]
        if pull.group(2) is None and replies and not all(map(_positive, replies)):
            return [Finding(write, REPLY_ID_REFUSED)]
        reply = _positive(pull.group(2)) if pull.group(2) is not None else bool(replies)
        if reply and _own_pull(allowance, int(pull.group(1))):
            return []
    return [Finding(write, f"`{write}`")]


# --- other HTTP clients and session starts ------------------------------------------

def judge_http(name: str, arguments: list[str]) -> list[Finding]:
    if not any(re.search(r"(?:api|uploads)\.github\.com", word, re.I) for word in arguments):
        return []
    write = f"{name} to the GitHub API"
    if name in ("curl",):
        problem = _curl_unread(arguments)
        return [Finding(write, f"{write} with {problem}")] if problem else []
    if name == "wget":
        problem = _wget_unread(arguments)
        return [Finding(write, f"{write} with {problem}")] if problem else []
    problem = _web_cmdlet_unread(arguments)
    return [Finding(write, f"{write} with {problem}")] if problem else []


# curl's options that send nothing and change no method, as single letters and long names, and
# those of them that take a value. Any other option may send a body or a method, so a request
# carrying one is read as a write.
CURL_READ_LETTERS = set("sSLfiIvkgq#")
CURL_READ_VALUE_LETTERS = set("HoAwmeurbcxzE")
CURL_READ_LONG = {"--silent", "--show-error", "--location", "--fail", "--include", "--head",
                  "--verbose", "--insecure", "--compressed", "--globoff", "--fail-with-body",
                  "--no-progress-meter", "--location-trusted"}
CURL_READ_LONG_VALUES = {"--header", "--output", "--user-agent", "--write-out", "--max-time",
                         "--user", "--retry", "--connect-timeout", "--referer", "--url", "--range",
                         "--cookie", "--cookie-jar", "--proxy", "--oauth2-bearer", "--cacert",
                         "--retry-delay", "--retry-max-time", "--max-redirs"}


def _curl_unread(arguments: list[str]) -> str | None:
    """Why a curl request cannot be read as a GET with no body, or None when it can."""
    words = list(arguments)
    while words:
        word = words.pop(0)
        if word == "--":
            return None
        if word.startswith("--"):
            stem, _, joined = word.partition("=")
            if stem == "--request":
                method = joined or (words.pop(0) if words else "")
                if method.upper() not in ("GET", "HEAD"):
                    return f"method {method}"
            elif stem in CURL_READ_LONG_VALUES:
                if not joined and words:
                    words.pop(0)
            elif stem not in CURL_READ_LONG:
                return f"the option {word}"
        elif word.startswith("-") and len(word) > 1:
            for index, letter in enumerate(word[1:], 1):
                if letter == "X" or letter in CURL_READ_VALUE_LETTERS:
                    value = word[index + 1:] or (words.pop(0) if words else "")
                    if letter == "X" and value.upper() not in ("GET", "HEAD"):
                        return f"method {value}"
                    break
                if letter not in CURL_READ_LETTERS:
                    return f"the option -{letter}"
    return None


# wget's options that send nothing and change no method, read the same way as curl's.
WGET_READ_LETTERS = set("qSvN")
WGET_READ_VALUE_LETTERS = set("OUTtoa")
WGET_READ_SHORT = {"-nv", "-nc", "-nd", "-nH"}
WGET_READ_LONG = {"--quiet", "--verbose", "--no-verbose", "--server-response", "--spider",
                  "--no-check-certificate", "--no-clobber", "--timestamping"}
WGET_READ_LONG_VALUES = {"--output-document", "--header", "--user-agent", "--timeout", "--tries",
                         "--output-file", "--append-output", "--user", "--password",
                         "--ca-certificate", "--max-redirect", "--wait"}


def _wget_unread(arguments: list[str]) -> str | None:
    """Why a wget request cannot be read as a GET with no body, or None when it can."""
    words = list(arguments)
    while words:
        word = words.pop(0)
        if word == "--":
            return None
        if word in WGET_READ_SHORT:
            continue
        if word.startswith("--"):
            stem, _, joined = word.partition("=")
            if stem == "--method":
                method = joined or (words.pop(0) if words else "")
                if method.upper() not in ("GET", "HEAD"):
                    return f"method {method}"
            elif stem in WGET_READ_LONG_VALUES:
                if not joined and words:
                    words.pop(0)
            elif stem not in WGET_READ_LONG:
                return f"the option {word}"
        elif word.startswith("-") and len(word) > 1:
            for index, letter in enumerate(word[1:], 1):
                if letter in WGET_READ_VALUE_LETTERS:
                    if not word[index + 1:] and words:
                        words.pop(0)
                    break
                if letter not in WGET_READ_LETTERS:
                    return f"the option -{letter}"
    return None


# Invoke-RestMethod and Invoke-WebRequest parameters that send nothing, spelled out in full.
# PowerShell also takes an abbreviated or colon-joined parameter; the check reads neither, so a
# request carrying one is read as a write.
WEB_CMDLET_READS = {"-uri", "-headers", "-outfile", "-usebasicparsing", "-timeoutsec", "-useragent",
                    "-maximumredirection", "-passthru", "-skipcertificatecheck", "-authentication",
                    "-token", "-credential", "-erroraction", "-sessionvariable", "-websession",
                    "-contenttype", "-method"}
WEB_CMDLET_SWITCHES = {"-usebasicparsing", "-passthru", "-skipcertificatecheck"}


def _web_cmdlet_unread(arguments: list[str]) -> str | None:
    words = list(arguments)
    while words:
        word = words.pop(0)
        if not word.startswith("-"):
            continue
        lowered = word.lower()
        if lowered not in WEB_CMDLET_READS:
            return f"the parameter {word}"
        if lowered in WEB_CMDLET_SWITCHES:
            continue
        value = words.pop(0) if words else ""
        if lowered == "-method" and value.lower() not in ("get", "head"):
            return f"method {value}"
    return None


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
    elif kind == "stretch":
        own = f"#{number}" if number is not None else f"the one opened from {branch}"
        text = (f"`stretch`: a push to refs/heads/{branch} of {repository}; opening, readying and "
                f"editing the title and body of a pull request from {branch}; a conversation comment "
                f"on, and a reply on and a resolve of a review thread of, that pull request ({own}); "
                f"and a comment on issue #{allowance.get('issue')} of {repository}")
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

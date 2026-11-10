"""Each dispatched step's GitHub write allowance, and the launch block that holds it.

A dispatched session that can write (the artifact author, the builder, the use
consumer) makes only the GitHub writes its own step needs, and returns any
other as a request. This module derives the allowance from the stage, writes
the sentence that tells the session, prepares the command check
(``github_write_guard``) a launch carries, removes git's push credential where
no push is allowed, and reads the refusals back for the run record.
Design: lib/DESIGN.md#the-github-write-bound
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import github_write_guard as guard

GUARD = Path(guard.__file__).resolve()
SCHEMA_VERSION = 1
MATCHER = "Bash|PowerShell"
CONNECTORS = guard.CONNECTORS
CHILD_VARIABLE = guard.CHILD_VARIABLE
SHELL_PREFIX = "CLAUDE_CODE_SHELL_PREFIX"
PUSH_STAGES = {"build", "floor"}
GRANT_MARKER = re.compile(
    r"<!--\s*tradecraft:write-grant:v1\s+brief=(\d+)\s+row=(\d+)\s+stage=([\w-]+)\s+"
    r"write=(push|comment|api)\s+target=(.+?)\s*-->")
CHILD_START = f'claude --setting-sources user --settings "${CHILD_VARIABLE}"'
CLOUD_NOT_RUN = "the launch block runs on this machine; a cloud builder runs on a remote one"


class BoundError(OSError):
    """The command check could not be prepared; nothing launches unchecked."""


class GrantError(ValueError):
    """A write grant does not rest on a row of the affirmed brief."""


def repository_of(work: str) -> str:
    """owner/name of an ``owner/name#n`` work value."""
    return work.split("#", 1)[0]


def allowance_for(stage: str, *, repository: str, branch: str | None,
                  pull_request: int | None, grants=()) -> dict[str, object]:
    """The step's allowance. Stages other than build, floor and review-disposition get none."""
    if stage in PUSH_STAGES and branch:
        kind = "branch"
    elif stage == "review-disposition" and branch:
        kind = "review-disposition"
    else:
        kind = "none"
    return {"kind": kind, "repository": repository, "branch": branch if kind != "none" else None,
            "pull_request": pull_request if kind == "review-disposition" else None,
            "grants": list(grants)}


def permits_push(allowance: dict) -> bool:
    return guard.permits_push(allowance)


def without_push_credential(env: dict[str, str]) -> dict[str, str]:
    """A copy of ``env`` in which git finds no credential and ssh offers no key.

    The gh login stays: reads are open to every step, and the command check
    refuses gh writes.
    """
    child = dict(env)
    try:
        count = int(child.get("GIT_CONFIG_COUNT", "0"))
    except ValueError:
        count = 0
    for key, value in (("credential.helper", ""), ("core.askPass", "")):
        child[f"GIT_CONFIG_KEY_{count}"] = key
        child[f"GIT_CONFIG_VALUE_{count}"] = value
        count += 1
    child["GIT_CONFIG_COUNT"] = str(count)
    child.update({"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", "GIT_ASKPASS": "",
                  "SSH_ASKPASS": "",
                  "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o IdentitiesOnly=yes "
                                     "-o IdentityAgent=none -o IdentityFile=none"})
    child.pop("SSH_AUTH_SOCK", None)
    return child


def _writes(allowance: dict) -> str:
    kind = allowance.get("kind")
    repository = allowance.get("repository")
    branch = allowance.get("branch")
    number = allowance.get("pull_request")
    if kind == "branch":
        text = f"a push to your own branch {branch} of {repository}, and nothing else"
    elif kind == "review-disposition":
        text = (f"a push to your own branch {branch} of {repository}; a reply on, and a resolve "
                f"of, a review thread of your own pull request {repository}#{number}; and a "
                f"conversation comment on {repository}#{number} answering a body finding")
    else:
        text = "none"
    grants = [f"the granted {g.get('write')} {g.get('target')}" for g in allowance.get("grants") or ()]
    if grants:
        text += "; and " + "; ".join(grants)
    return text


def sentence(allowance: dict) -> str:
    """The instruction every bounded step receives, in its prompt or launcher notice.

    One sentence for both vendors: a Codex launch's children get the same child
    settings, so the same child start is checked there too.
    """
    start = (f"Start a Claude session only as `{CHILD_START} ...`, without `--safe-mode` or "
             f"`--bare` and without changing `{CONNECTORS}`; it may make no GitHub write. "
             "Start no Codex session.")
    return (f"GitHub writes this step may make: {_writes(allowance)}. Make no other GitHub write "
            "- no comment, pull request, branch, branch deletion, tag, release, workflow run or "
            "setting. GitHub reads (`gh api --method GET`, fetches) stay open. " + start
            + " If the work needs any other write, do not make it: end your return with a "
            "**Write requests** section naming each write, why the work needs it, and what it "
            "would leave behind.")


SENTENCE_OPENING = "GitHub writes this step may make:"


def needs_notice(allowance: dict, prompt: bytes) -> bool:
    """Whether a launch must append its allowance notice to this dispatch.

    A dispatch already stating this allowance is not told twice. One stating any other
    allowance is refused, because a session told two allowances cannot know which holds.
    """
    if sentence(allowance).encode("utf-8") in prompt:
        return False
    if SENTENCE_OPENING.encode("utf-8") in prompt:
        raise BoundError("the dispatch states a GitHub write allowance other than the one this "
                         "launch holds; recompose it, or print the right sentence with the work "
                         "entrance's allowance command")
    return True


def cloud_sentence() -> str:
    return ("GitHub writes this run may make: a push to the change branch and to its report "
            "branch, and nothing else; post nothing. If the work needs any other write, do not "
            "make it: end your report with a **Write requests** section naming each write, why "
            "the work needs it, and what it would leave behind.")


def notice(allowance: dict) -> bytes:
    return ("Launcher GitHub write bound: " + sentence(allowance)
            + " A refused command fails and is recorded; your turn goes on.\n").encode("utf-8")


# --- the launch block -----------------------------------------------------------

def _quoted(path) -> str:
    return '"' + str(path).replace("\\", "/") + '"'


def hook_entry(config_path: Path) -> dict[str, object]:
    command = f"{_quoted(sys.executable)} {_quoted(GUARD)} --hook --config {_quoted(config_path)}"
    return {"matcher": MATCHER, "hooks": [{"type": "command", "command": command}]}


def _write_json(path: Path, value: object) -> None:
    path.write_bytes((json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode("utf-8"))


def _config(allowance: dict, *, scope: str, root, log: Path, child_settings: Path,
            session: str | None = None) -> dict[str, object]:
    return {"schema_version": SCHEMA_VERSION, "scope": scope, "allowance": allowance,
            "root": str(Path(root).resolve(strict=False)) if root else None, "log": str(log),
            "child_settings": str(child_settings), "codex_child_arguments": None,
            "session": session}


def bash_executable(env: dict[str, str] | None = None) -> str | None:
    """The bash the Claude runtime uses: Git Bash on Windows, never the WSL launcher."""
    env = os.environ if env is None else env
    supplied = env.get("CLAUDE_CODE_GIT_BASH_PATH")
    if supplied and Path(supplied).is_file():
        return supplied
    if os.name == "nt":
        git = shutil.which("git")
        if git:
            for parent in Path(git).resolve().parents:
                candidate = parent / "bin" / "bash.exe"
                if candidate.is_file():
                    return str(candidate)
        return None
    return shutil.which("bash")


def _self_test_cases(allowance: dict) -> list[tuple[str, dict, str]]:
    fixture = {"kind": "branch", "repository": "tradecraft-self-test/fixture",
               "branch": "self-test", "pull_request": None, "grants": []}
    none = {**fixture, "kind": "none", "branch": None}
    return [
        ("local push", none, "git push ./tradecraft-self-test.git HEAD:refs/heads/x", "allow"),
        ("own-branch push", fixture,
         "git push https://github.com/tradecraft-self-test/fixture.git HEAD:refs/heads/self-test",
         "allow"),
        ("read", none, "gh api --method GET repos/tradecraft-self-test/fixture/issues/1", "allow"),
        ("child start", none, CHILD_START + " -p hi", "allow"),
        ("forced push of a commit to another ref", none,
         "git push --force-with-lease=refs/heads/x:abc https://github.com/tradecraft-self-test/"
         "fixture.git abc123:refs/heads/x", "deny"),
        ("wrapped comment", none, 'bash -c "gh issue comment 683"', "deny"),
        ("bare child", none, "claude -p hi", "deny"),
        ("safe-mode child", none,
         f'claude --setting-sources user --safe-mode --settings "${CHILD_VARIABLE}" -p x', "deny"),
        ("child without sources", none, f'claude --settings "${CHILD_VARIABLE}" -p x', "deny"),
    ]


def harness_string(command: str) -> str:
    """The one argument the Claude runtime hands a shell prefix: the command inside eval."""
    return "eval '" + command.replace("'", "'\\''") + "' < /dev/null"


def self_test(directory: Path, root, child_settings: Path, *, carrier: str,
              wrapper_for=None, env: dict[str, str] | None = None) -> str:
    """Prove the check allows and refuses as it must, and that the launch's entry carries it.

    Every case is judged by the check's own decision; one refusal (and, for the
    shell prefix, one pass-through) runs through the entry the launch uses, so
    the self-test costs one or two processes rather than one per case.
    """
    directory.mkdir()
    failures = []
    entry_case = None
    for index, (label, allowance, command, expected) in enumerate(_self_test_cases({})):
        config = _config(allowance, scope="self-test", root=directory,
                         log=directory / "self-test.log.jsonl", child_settings=child_settings)
        decided = guard.decide(command, str(directory), config)["decision"]
        if decided != expected:
            failures.append(f"{label}: expected {expected}, got {decided}")
        if label == "wrapped comment":
            entry_case = (directory / f"case-{index}.json", config, command)
    config_path, config, command = entry_case
    _write_json(config_path, config)
    if carrier == "pretooluse-hook":
        payload = {"tool_name": "Bash", "tool_input": {"command": command},
                   "cwd": str(directory), "session_id": "self-test"}
        result = subprocess.run([sys.executable, str(GUARD), "--hook", "--config", str(config_path)],
                                input=json.dumps(payload).encode("utf-8"), capture_output=True,
                                timeout=60, cwd=directory)
        if b'"deny"' not in result.stdout:
            failures.append("hook entry: a wrapped comment was not refused")
    else:
        wrapper = wrapper_for(config_path)
        result = subprocess.run([wrapper["bash"], wrapper["path"], harness_string(command)],
                                capture_output=True, timeout=60, cwd=directory, env=env,
                                stdin=subprocess.DEVNULL)
        if result.returncode != 126 or guard.REFUSED.encode() not in result.stderr:
            failures.append(f"prefix entry: a wrapped comment exited {result.returncode}, not 126")
        result = subprocess.run([wrapper["bash"], wrapper["path"], harness_string("printf ok; exit 3")],
                                capture_output=True, timeout=60, cwd=directory, env=env,
                                stdin=subprocess.DEVNULL)
        if result.stdout != b"ok" or result.returncode != 3:
            failures.append(f"pass-through: expected 'ok' and exit 3, got {result.stdout!r} "
                            f"and exit {result.returncode}")
    if failures:
        raise BoundError("GitHub write check self-test failed: " + "; ".join(failures))
    return "passed"


def write_wrapper(path: Path, config_path: Path) -> None:
    """The use consumer's single-path shell prefix: judge, then run the original string."""
    text = ("#!/bin/sh\n"
            f"{_quoted(sys.executable)} {_quoted(GUARD)} --prefix --config {_quoted(config_path)} "
            "-- \"$@\" || exit $?\n"
            'exec bash -c "$1"\n')
    path.write_bytes(text.encode("utf-8"))
    if os.name != "nt":
        path.chmod(0o700)


def prepare(temporary, allowance: dict, *, carrier: str, root, env: dict[str, str],
            enabled_plugins: dict | None = None, session: str | None = None) -> dict[str, object]:
    """Write the configs, child settings and log; self-test; return hooks, env and record.

    ``carrier`` is ``pretooluse-hook`` for an implementer or ``shell-prefix`` for
    the use consumer. The returned environment turns connectors off, names the
    child settings, and drops git's credential when the allowance permits no push.
    """
    temporary = Path(temporary)
    config_path = temporary / "github-write.json"
    child_path = temporary / "github-write-child.json"
    child_settings = temporary / "child-settings.json"
    log = temporary / "github-write.log.jsonl"
    for path in (sys.executable, GUARD, config_path, child_settings):
        if '"' in str(path):
            raise BoundError(f"GitHub write check path contains a double quote: {path}")
    _write_json(config_path, _config(allowance, scope="parent", root=root, log=log,
                                     child_settings=child_settings, session=session))
    child_allowance = {"kind": "none", "repository": allowance.get("repository"), "branch": None,
                       "pull_request": None, "grants": []}
    _write_json(child_path, _config(child_allowance, scope="child", root=root, log=log,
                                    child_settings=child_settings))
    _write_json(child_settings, {"enabledPlugins": dict(enabled_plugins or {}),
                                 "disableAllHooks": False,
                                 "hooks": {"PreToolUse": [hook_entry(child_path)]}})
    bash = bash_executable(env) if carrier == "shell-prefix" else None
    wrapper_path = temporary / "github-write-prefix.sh"

    def wrapper_for(config):
        if bash is None:
            raise BoundError("no bash was found to carry the use consumer's command check")
        write_wrapper(temporary / "github-write-self-test-prefix.sh", config)
        return {"bash": bash, "path": str(temporary / "github-write-self-test-prefix.sh")}

    try:
        result = self_test(temporary / "github-write-self-test", root, child_settings,
                           carrier=carrier, wrapper_for=wrapper_for, env=env)
    except (OSError, subprocess.SubprocessError) as exc:
        raise BoundError(f"GitHub write check self-test could not run: {exc}") from exc
    log.write_bytes(b"")
    child = dict(env)
    child[CONNECTORS] = "false"
    child[CHILD_VARIABLE] = str(child_settings)
    if carrier == "shell-prefix":
        write_wrapper(wrapper_path, config_path)
        child[SHELL_PREFIX] = str(wrapper_path)
    keep = permits_push(allowance)
    if not keep:
        child = without_push_credential(child)
    record = bound_record(allowance, carrier=carrier, status="armed", reason=None,
                          self_test=result, push_credential="kept" if keep else "removed",
                          child_settings=str(child_settings))
    return {"hooks": [hook_entry(config_path)] if carrier == "pretooluse-hook" else [],
            "env": child, "record": record, "log": str(log), "config_path": str(config_path),
            "child_settings": str(child_settings)}


def prepare_codex(allowance: dict, env: dict[str, str], version: str | None, *,
                  temporary=None, root=None) -> dict[str, object]:
    """The Codex block: environment removal, child settings, and a record that no check ran.

    The installed Codex loads execpolicy rules only from user or project ``.rules``
    files and ``requirements.toml``; no source can be supplied for one launch
    without writing into the product tree, the owner's Codex home or the
    machine's policy, so the parent's own commands go unchecked and its record
    says so. A Claude session it starts carries the same child settings.
    """
    # An inherited environment drops an empty variable on Windows; this explicit copy
    # does the same, so a Codex child sees what an inheriting one would.
    child = {key: value for key, value in env.items() if value != "" or os.name != "nt"}
    child[CONNECTORS] = "false"
    child_settings = None
    if temporary is not None:
        temporary = Path(temporary)
        child_settings = temporary / "child-settings.json"
        log = temporary / "github-write.log.jsonl"
        child_path = temporary / "github-write-child.json"
        child_allowance = {"kind": "none", "repository": allowance.get("repository"), "branch": None,
                           "pull_request": None, "grants": []}
        _write_json(child_path, _config(child_allowance, scope="child", root=root, log=log,
                                        child_settings=child_settings))
        # No plugin exclusions: a Codex launch runs no Claude plugin discovery to take them
        # from, so its Claude child keeps the owner's user plugins; the command check, not
        # the plugin list, is what holds that child's GitHub writes.
        _write_json(child_settings, {"disableAllHooks": False,
                                     "hooks": {"PreToolUse": [hook_entry(child_path)]}})
        log.write_bytes(b"")
        child[CHILD_VARIABLE] = str(child_settings)
    keep = permits_push(allowance)
    if not keep:
        child = without_push_credential(child)
    record = bound_record(allowance, carrier="none", status="not-run",
                          reason=f"the installed Codex ({version or 'version unknown'}) offers no "
                                 "per-launch rule source", self_test=None,
                          push_credential="kept" if keep else "removed",
                          child_settings=str(child_settings) if child_settings else None)
    return {"env": child, "record": record,
            "log": str(Path(temporary) / "github-write.log.jsonl") if temporary is not None else None}


def bound_record(allowance: dict, *, carrier: str, status: str, reason, self_test,
                 push_credential: str, child_settings) -> dict[str, object]:
    return {"schema_version": SCHEMA_VERSION, "allowance": allowance,
            "command_check": {"carrier": carrier, "status": status, "reason": reason,
                              "self_test": self_test},
            "push_credential": push_credential, "connectors": "disabled-by-environment",
            "child_settings": child_settings}


def cloud_record(change_branch: str | None, report_branch: str | None) -> dict[str, object]:
    return {"schema_version": SCHEMA_VERSION, "route": "cloud",
            "command_check": {"status": "not-run", "reason": CLOUD_NOT_RUN},
            "push_credential": "not-applicable",
            "allowance": {"kind": "cloud-routine", "pushes": [change_branch, report_branch],
                          "posts": "none"}}


def refusals(log) -> list[dict[str, object]]:
    """The refused decisions in a launch's command-check log."""
    try:
        raw = Path(log).read_bytes()
    except OSError:
        return []
    found = []
    for line in raw.splitlines():
        try:
            entry = json.loads(line)
        except (UnicodeError, ValueError):
            continue
        if isinstance(entry, dict) and entry.get("decision") == "deny":
            found.append({key: entry.get(key) for key in (
                "at", "scope", "entry", "session", "tool", "command", "reason", "allowance")})
    return found


# --- grants ----------------------------------------------------------------------

def _normalized(text: str) -> str:
    return " ".join(re.sub(r"[*_`>]", " ", text).split()).lower()


def brief_row(brief: str, number: int) -> str | None:
    """The text of row ``number`` in an affirmed brief, up to the next row or section."""
    lines = brief.splitlines()
    start = None
    for index, line in enumerate(lines):
        if re.match(rf"^\s*\**\s*{number}\.\s", line):
            start = index
            break
    if start is None:
        return None
    # A row runs to the next numbered row, or to the brief's "Not this" list, the one
    # section a brief puts after its rows.
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if re.match(r"^\s*\**\s*\d+\.\s", lines[index]) or re.match(r"^\s*\**Not this", lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


def parse_grant(comment_id: int, body: str) -> dict[str, object]:
    match = GRANT_MARKER.search(body)
    if not match:
        raise GrantError(f"comment {comment_id} carries no write-grant marker")
    brief, row, stage, write, target = match.groups()
    quote = "\n".join(line.lstrip()[1:].strip() for line in body[match.end():].splitlines()
                      if line.lstrip().startswith(">"))
    return {"marker": comment_id, "brief": int(brief), "row": int(row), "stage": stage,
            "write": write, "target": target.strip(), "quote": quote}


def validate_grant(grant: dict, *, brief_comment: int, brief_body: str, stage: str,
                   resumed: bool) -> dict[str, object]:
    """Accept a grant only when it rests on a row of the affirmed brief; raise otherwise."""
    if not resumed:
        raise GrantError("a write grant is accepted only for a turn that resumes its step")
    if grant["brief"] != brief_comment:
        raise GrantError(f"grant {grant['marker']} cites comment {grant['brief']}, not the affirmed "
                         f"brief {brief_comment}")
    row = brief_row(brief_body, grant["row"])
    if row is None:
        raise GrantError(f"grant {grant['marker']} cites row {grant['row']}, which the brief lacks")
    if not grant["quote"].strip() or _normalized(grant["quote"]) not in _normalized(row):
        raise GrantError(f"grant {grant['marker']} quotes words that row {grant['row']} does not carry")
    if grant["stage"] != stage:
        raise GrantError(f"grant {grant['marker']} is for stage {grant['stage']}, not {stage}")
    target = grant["target"]
    if grant["write"] == "push" and not re.match(r"^[^/\s]+/[^/:\s]+:refs/(?:heads|tags)/\S+$", target):
        raise GrantError("a push grant's target is owner/name:refs/heads/x or owner/name:refs/tags/x")
    if grant["write"] == "comment" and not re.match(r"^[^/\s]+/[^/#\s]+#\d+$", target):
        raise GrantError("a comment grant's target is owner/name#n")
    if grant["write"] == "api" and not re.match(r"^[A-Z]+ \S+$", target):
        raise GrantError("an api grant's target is METHOD path")
    return {key: grant[key] for key in ("marker", "brief", "row", "stage", "write", "target")}

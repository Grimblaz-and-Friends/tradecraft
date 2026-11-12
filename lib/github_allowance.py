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
import shlex
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
# The cloud stages that may push the change branch: those that may push it locally.
CLOUD_CHANGE_STAGES = {"build", "floor", "review-disposition"}
GRANT_MARKER = re.compile(
    r"<!--\s*tradecraft:write-grant:v1\s+brief=(\d+)\s+row=(\d+)\s+stage=([\w-]+)\s+"
    r"write=(push|comment|api)\s+target=(.+?)\s*-->")
CHILD_START = guard.CHILD_START
CLOUD_NOT_RUN = "the launch block runs on this machine; a cloud builder runs on a remote one"


class BoundError(RuntimeError):
    """The bound cannot hold for this launch, so nothing launches.

    Raised when the command check could not be prepared or its self-test failed, and when a
    dispatch states an allowance other than the launch's own. It is not an OSError, so a
    self-test that ran and failed is never reported as one that could not run.
    """


class RefusalLogDamaged(ValueError):
    """A line of a command-check log could not be read, so a refusal it held may be lost."""

    def __init__(self, found: list, damaged: int):
        super().__init__(f"{damaged} line(s) of the refusal log could not be read")
        self.found = found


class GrantError(ValueError):
    """A write grant does not rest on a row of the affirmed brief."""


def repository_of(work: str) -> str:
    """owner/name of an ``owner/name#n`` work value."""
    return work.split("#", 1)[0]


def allowance_for(stage: str, *, repository: str, branch: str | None,
                  pull_request: int | None, grants=()) -> dict[str, object]:
    """The step's allowance; a stage that may push gets none without its registered branch."""
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
    refuses gh writes. No variable it sets is empty: the empty helper value that clears
    git's credential helpers travels inside ``GIT_CONFIG_PARAMETERS``, and the askpass
    variables are removed rather than emptied, so an environment that drops empty
    variables on the way to a child still carries the removal whole.
    """
    child = dict(env)
    cleared = "'credential.helper=' 'core.askpass='"
    existing = child.get("GIT_CONFIG_PARAMETERS")
    child["GIT_CONFIG_PARAMETERS"] = f"{existing} {cleared}" if existing else cleared
    child.update({"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never",
                  "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o IdentitiesOnly=yes "
                                     "-o IdentityAgent=none -o IdentityFile=none"})
    for name in ("GIT_ASKPASS", "SSH_ASKPASS", "SSH_AUTH_SOCK"):
        child.pop(name, None)
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
CLOUD_SENTENCE_OPENING = "GitHub writes this run may make:"


def needs_notice(allowance: dict, prompt: bytes) -> bool:
    """Whether a launch must append its allowance notice to this dispatch.

    A dispatch already stating this allowance is not told twice. One stating any other
    allowance is refused, because a session told two allowances cannot know which holds.
    """
    if sentence(allowance).encode("utf-8") in prompt:
        return False
    # The cloud sentence states an allowance too, so a local launch refuses it the same way.
    if any(opening.encode("utf-8") in prompt for opening in (SENTENCE_OPENING, CLOUD_SENTENCE_OPENING)):
        raise BoundError("the dispatch states a GitHub write allowance other than the one this "
                         "launch holds; recompose it, or print the right sentence with the work "
                         "entrance's allowance command")
    return True


def cloud_sentence(stage: str) -> str:
    """A cloud run's allowance, the only bound it carries, since the launch block runs locally.

    Every cloud run pushes its report branch, because that is how its return travels; only
    a stage that may push the change branch locally may push it there.
    """
    pushes = ("a push to the change branch and to its report branch" if stage in CLOUD_CHANGE_STAGES
              else "a push to its report branch, which carries its return")
    return (f"{CLOUD_SENTENCE_OPENING} {pushes}, and nothing else; post nothing. If the "
            "work needs any other write, do not make it: end your report with a **Write "
            "requests** section naming each write, why the work needs it, and what it would "
            "leave behind.")


def cloud_notice(stage: str, prompt: bytes) -> bytes:
    """What a cloud run's prompt needs appended: its route's sentence, unless it already states it.

    A prompt stating any other allowance is refused, as a local launch refuses one.
    """
    stated = cloud_sentence(stage)
    if stated.encode("utf-8") in prompt:
        return b""
    if any(opening.encode("utf-8") in prompt for opening in (SENTENCE_OPENING, CLOUD_SENTENCE_OPENING)):
        raise BoundError("the dispatch states a GitHub write allowance other than the cloud route's; "
                         "print the cloud route's sentence with the work entrance's allowance command "
                         "and --cloud")
    return ("Launcher GitHub write bound: " + stated + "\n").encode("utf-8")


def notice(allowance: dict) -> bytes:
    return ("Launcher GitHub write bound: " + sentence(allowance)
            + " A refused command fails and is recorded; your turn goes on.\n").encode("utf-8")


# --- the launch block -----------------------------------------------------------

def _quoted(path) -> str:
    # Hook commands and the prefix wrapper run under bash, where a backslash inside double
    # quotes can escape the next character; Windows takes these paths with forward slashes.
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
            "child_settings": str(child_settings), "session": session}


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


def _self_test_cases() -> list[tuple[str, dict, str, str]]:
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
         f'claude --setting-sources user --strict-mcp-config --safe-mode --settings "${CHILD_VARIABLE}" -p x',
         "deny"),
        ("child without sources", none, f'claude --settings "${CHILD_VARIABLE}" -p x', "deny"),
    ]


def harness_string(command: str) -> str:
    """The one argument the Claude runtime hands a shell prefix: the command inside eval."""
    return "eval '" + command.replace("'", "'\\''") + "' < /dev/null"


def self_test(directory: Path, root, child_settings: Path, *, carrier: str,
              wrapper: dict | None = None, env: dict[str, str] | None = None) -> str:
    """Prove the check allows and refuses as it must, and that the launch's entry carries it.

    Every case is judged by the check's own decision; one refusal (and, for the
    shell prefix, one pass-through) runs through the entry the launch uses, so
    the self-test costs one or two processes rather than one per case.
    """
    directory.mkdir()
    failures = []
    entry_case = None
    for index, (label, allowance, command, expected) in enumerate(_self_test_cases()):
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
        # The command string a launch installs as its hook, split as a shell splits it, so the
        # interpreter, script and quoting the hook carries are the ones proved.
        result = subprocess.run(shlex.split(hook_entry(config_path)["hooks"][0]["command"]),
                                input=json.dumps(payload).encode("utf-8"), capture_output=True,
                                timeout=60, cwd=directory)
        if b'"deny"' not in result.stdout:
            failures.append("hook entry: a wrapped comment was not refused")
    else:
        # The installed wrapper itself, so the file the launch runs is the file proved.
        result = subprocess.run([wrapper["bash"], wrapper["path"], harness_string(command)],
                                capture_output=True, timeout=60, cwd=directory, env=env,
                                stdin=subprocess.DEVNULL)
        if result.returncode != guard.PREFIX_REFUSED_EXIT or guard.REFUSED.encode() not in result.stderr:
            failures.append(f"prefix entry: a wrapped comment exited {result.returncode}, "
                            f"not {guard.PREFIX_REFUSED_EXIT}")
        result = subprocess.run([wrapper["bash"], wrapper["path"], harness_string("printf ok; exit 3")],
                                capture_output=True, timeout=60, cwd=directory, env=env,
                                stdin=subprocess.DEVNULL)
        if result.stdout != b"ok" or result.returncode != 3:
            failures.append(f"pass-through: expected 'ok' and exit 3, got {result.stdout!r} "
                            f"and exit {result.returncode}")
    if failures:
        raise BoundError("GitHub write check self-test failed: " + "; ".join(failures))
    return "passed"


def write_wrapper(path: Path, config_path: Path, bash: str) -> None:
    """The use consumer's single-path shell prefix: judge, then run the original string.

    It names the bash it runs, because on Windows the first bash on PATH can be WSL's,
    which would run the consumer's commands in another system.
    """
    text = ("#!/bin/sh\n"
            f"{_quoted(sys.executable)} {_quoted(GUARD)} --prefix --config {_quoted(config_path)} "
            "-- \"$@\" || exit $?\n"
            f'exec {_quoted(bash)} -c "$1"\n')
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
    # The hook command and the wrapper put every path inside double quotes, and nothing there
    # escapes one, so a path holding one would end its quoting early.
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
    wrapper = None
    wrapper_path = temporary / "github-write-prefix.sh"
    if carrier == "shell-prefix":
        bash = bash_executable(env)
        if bash is None:
            raise BoundError("no bash was found to carry the use consumer's command check")
        write_wrapper(wrapper_path, config_path, bash)
        wrapper = {"bash": bash, "path": str(wrapper_path)}
    try:
        # Through the installed wrapper the self-test's refusal lands in the launch's own
        # log, which is emptied below before the launch starts.
        result = self_test(temporary / "github-write-self-test", root, child_settings,
                           carrier=carrier, wrapper=wrapper, env=env)
    except (OSError, subprocess.SubprocessError) as exc:
        # Only a self-test that could not start lands here; one that ran and failed raises
        # BoundError naming its failure, which is not an OSError.
        raise BoundError(f"GitHub write check self-test could not run: {exc}") from exc
    log.write_bytes(b"")
    child = dict(env)
    child[CONNECTORS] = "false"
    child[CHILD_VARIABLE] = str(child_settings)
    if carrier == "shell-prefix":
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
                  temporary, root) -> dict[str, object]:
    """The Codex block: environment removal, child settings, and a record that no check ran.

    The installed Codex loads execpolicy rules only from user or project ``.rules``
    files and ``requirements.toml``; no source can be supplied for one launch
    without writing into the product tree, the owner's Codex home or the
    machine's policy, so the parent's own commands go unchecked and its record
    says so. A Claude session it starts carries the same child settings.
    """
    # An inherited environment drops an empty variable on Windows; this explicit copy
    # does the same, so a Codex child sees what an inheriting one would. An inherited
    # GIT_CONFIG_VALUE_n stays even when empty, because its GIT_CONFIG_COUNT names it.
    child = {key: value for key, value in env.items()
             if value != "" or os.name != "nt" or key.startswith("GIT_CONFIG_VALUE_")}
    child[CONNECTORS] = "false"
    temporary = Path(temporary)
    child_settings = temporary / "child-settings.json"
    for path in (sys.executable, GUARD, child_settings):
        if '"' in str(path):
            raise BoundError(f"GitHub write check path contains a double quote: {path}")
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
    try:
        # The parent's commands go unchecked, but a Claude child's hook is the same entry a
        # Claude launch installs, so it is proved the same way before the launch starts.
        result = self_test(temporary / "github-write-self-test", root, child_settings,
                           carrier="pretooluse-hook")
    except (OSError, subprocess.SubprocessError) as exc:
        raise BoundError(f"GitHub write check self-test could not run: {exc}") from exc
    log.write_bytes(b"")
    child[CHILD_VARIABLE] = str(child_settings)
    keep = permits_push(allowance)
    if not keep:
        child = without_push_credential(child)
    record = bound_record(allowance, carrier="none", status="not-run",
                          reason=f"the installed Codex ({version or 'version unknown'}) offers no "
                                 "per-launch rule source", self_test=result,
                          push_credential="kept" if keep else "removed",
                          child_settings=str(child_settings))
    return {"env": child, "record": record, "log": str(log)}


def bound_record(allowance: dict, *, carrier: str, status: str, reason, self_test,
                 push_credential: str, child_settings) -> dict[str, object]:
    return {"schema_version": SCHEMA_VERSION, "allowance": allowance,
            "command_check": {"carrier": carrier, "status": status, "reason": reason,
                              "self_test": self_test},
            "push_credential": push_credential, "connectors": "disabled-by-environment",
            "child_settings": child_settings}


def cloud_record(stage: str, change_branch: str | None, report_branch: str | None
                 ) -> dict[str, object]:
    return {"schema_version": SCHEMA_VERSION, "route": "cloud",
            "command_check": {"status": "not-run", "reason": CLOUD_NOT_RUN},
            "push_credential": "not-applicable",
            "allowance": {"kind": "cloud-routine",
                          "pushes": ([change_branch, report_branch] if stage in CLOUD_CHANGE_STAGES
                                     else [report_branch]),
                          "posts": "none"}}


def record_refusals(record: dict, log) -> None:
    """Fill a run record's ``github_write_refusals`` from the launch's log.

    Preparation creates the log empty, so a missing or unreadable one has lost what it
    held: the record then says so in ``github_write_refusals_unknown``, and the entrance
    report reads the bound as unknown rather than as a run in which nothing was refused.
    """
    try:
        record["github_write_refusals"] = refusals(log)
    except RefusalLogDamaged as exc:
        record["github_write_refusals"] = exc.found
        record["github_write_refusals_unknown"] = str(exc)
    except OSError as exc:
        record["github_write_refusals"] = []
        record["github_write_refusals_unknown"] = f"{type(exc).__name__}: {exc}"


def refusals(log) -> list[dict[str, object]]:
    """The refused decisions in a launch's command-check log.

    OSError when the log cannot be read. A line that will not parse raises
    ``RefusalLogDamaged`` carrying the refusals that did: a line cut short, as by a launch
    stopped mid-write, may be the refusal that is lost. An empty line is no damage.
    """
    raw = Path(log).read_bytes()
    found = []
    damaged = 0
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except (UnicodeError, ValueError):
            damaged += 1
            continue
        if isinstance(entry, dict) and entry.get("decision") == "deny":
            found.append({key: entry.get(key) for key in (
                "at", "scope", "entry", "session", "tool", "command", "reason", "allowance")})
    if damaged:
        raise RefusalLogDamaged(found, damaged)
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


# A quote is at least a phrase of the row, so it shows which of the row's words name the
# write; a single word or letter would occur in almost any row.
MIN_QUOTE_WORDS = 3


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:['\-][a-z0-9]+)*", _normalized(text))


def _grant_repository(write: str, target: str) -> str | None:
    """owner/name a grant's target writes to, lowercased, or None when it names none."""
    if write == "push":
        return target.split(":", 1)[0].lower()
    if write == "comment":
        return target.split("#", 1)[0].lower()
    match = re.match(r"^[A-Z]+ /?repos/([^/\s]+/[^/\s]+)(?:/|$)", target)
    return match.group(1).lower() if match else None


def _quotes_row(quote: str, row: str) -> bool:
    """Whether the quote is a run of at least MIN_QUOTE_WORDS whole words of the row."""
    wanted, words = _words(quote), _words(row)
    return len(wanted) >= MIN_QUOTE_WORDS and any(
        words[i:i + len(wanted)] == wanted for i in range(len(words) - len(wanted) + 1))


def validate_grant(grant: dict, *, brief_comment: int, brief_body: str, stage: str,
                   resumed: bool, repository: str) -> dict[str, object]:
    """Accept a grant only when it rests on a row of the affirmed brief; raise otherwise."""
    # A grant answers a request the step itself returned, so only that step's next,
    # resumed turn can carry it.
    if not resumed:
        raise GrantError("a write grant is accepted only for a turn that resumes its step")
    if grant["brief"] != brief_comment:
        raise GrantError(f"grant {grant['marker']} cites comment {grant['brief']}, not the affirmed "
                         f"brief {brief_comment}")
    row = brief_row(brief_body, grant["row"])
    if row is None:
        raise GrantError(f"grant {grant['marker']} cites row {grant['row']}, which the brief lacks")
    if not _quotes_row(grant["quote"], row):
        raise GrantError(f"grant {grant['marker']} does not quote at least {MIN_QUOTE_WORDS} whole "
                         f"words that row {grant['row']} carries")
    if grant["stage"] != stage:
        raise GrantError(f"grant {grant['marker']} is for stage {grant['stage']}, not {stage}")
    target = grant["target"]
    if grant["write"] == "push" and not re.match(r"^[^/\s]+/[^/:\s]+:refs/(?:heads|tags)/\S+$", target):
        raise GrantError("a push grant's target is owner/name:refs/heads/x or owner/name:refs/tags/x")
    if grant["write"] == "comment" and not re.match(r"^[^/\s]+/[^/#\s]+#\d+$", target):
        raise GrantError("a comment grant's target is owner/name#n")
    if grant["write"] == "api" and not re.match(r"^[A-Z]+ \S+$", target):
        raise GrantError("an api grant's target is METHOD path")
    # A grant answers a write the change's own step needs, in the change's own repository;
    # nothing in the affirmed work provides for a grant to write anywhere else.
    if _grant_repository(grant["write"], target) != repository.lower():
        raise GrantError(f"grant {grant['marker']} targets {target}, outside the work's repository "
                         f"{repository}")
    accepted = {key: grant[key] for key in ("marker", "brief", "row", "stage", "write", "target")}
    if grant["write"] == "api":
        accepted["target"] = guard.api_target(target)
    return accepted

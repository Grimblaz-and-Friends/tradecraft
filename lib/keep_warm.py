#!/usr/bin/env python3
"""Keep a waiting local Claude builder or author in the model's one-hour cache.

Usage: python -B <plugin-root>/lib/keep_warm.py run --state DIR
       python -B <plugin-root>/lib/keep_warm.py deny
       python -B <plugin-root>/lib/keep_warm.py ping-now --state DIR
       python -B <plugin-root>/lib/keep_warm.py status [--work OWNER/REPO#N]

When a local Claude turn ends and the entrance may resume its session, a
runner outside every launch's process tree resumes that session about every
55 minutes with a one-line prompt that saves nothing, so the next real turn
reads its conversation from the cache instead of writing all of it again.
A ping only ever reads; anything else ends keep-warm for that session until
its next real turn, and nothing here holds a stage.

Design: lib/DESIGN.md#keeping-a-waiting-session-warm
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import holder_transcript as transcripts  # noqa: E402
import implementer_environment as environments  # noqa: E402
import change_cost  # noqa: E402
import run_lifecycle as lifecycle  # noqa: E402
from winio import utf8_stdio  # noqa: E402

SCHEMA_VERSION = 1
# Inside the one-hour cache.
INTERVAL_SECONDS = 3300
# No ping once the session's last call is older than this; the margin under
# the hour leaves room for the ping's own start-up.
LAPSE_SECONDS = 3420
DEFAULT_CAP_HOURS = 8
# The largest cap the machine setting accepts: a session nobody resumed within a
# day is not coming back, so pings past it buy nothing.
MAX_CAP_HOURS = 24
# A ping still running then is killed and recorded failed, because a stuck ping
# must not hold the session's lock against its next real turn.
PING_TIMEOUT_SECONDS = 300
# A first call that read nothing paid for the whole conversation, so it is a
# miss whatever it wrote. Otherwise the allowance absorbs the one-time write at
# a session's first resume.
WRITE_ALLOWANCE_TOKENS = 20000
WRITE_SHARE = 0.05
# No ping when the last call's context is at least this share of the window:
# resuming it would compact, paying for a compaction the ping throws away.
CONTEXT_SHARE = 0.90
# A turn that reported no window is read against the largest window the models
# offer, so an unknown never refuses a ping a known window would allow.
FALLBACK_CONTEXT_WINDOW = 1000000
# Mirrors the entrance's RESUME_SOURCE_STAGES; a test pins the two equal.
STAGE_GROUPS = {"artifact": "artifact", "build": "build", "floor": "build",
                "review-disposition": "build"}
# Mirrors the entrance's RESUMABLE_BUNDLE_OUTCOMES, plus the two outcomes
# recovery resumes in their own session.
RESUMABLE_OUTCOMES = frozenset({"success", "success_uncontinuable", "completed_no_output",
                                "invalid_artifact_return", "work_outlived_return",
                                "interrupted", "error"})
PROMPT = ("Keep-warm ping from the tradecraft launcher. Reply with the single word ok "
          "and use no tools.")
DENY_REASON = "keep-warm ping: every tool is refused"
# The variables a launch itself sets in its child's environment; any other
# difference from the launcher's own environment refuses a keep-warm.
LAUNCH_ENV_NAMES = ("CLAUDE_CODE_ENABLE_FUNCTION_HOOKS",
                    "CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD",
                    "CLAUDE_CODE_DISABLE_AUTO_MEMORY", "BASH_MAX_TIMEOUT_MS",
                    "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS", "GIT_LFS_SKIP_SMUDGE",
                    "GIT_NO_LAZY_FETCH")
# The launch strips these inherited plugin directories from its child, so their
# absence is the launch's own change, not a foreign one.
REMOVABLE_ENV_NAMES = ("CLAUDE_CODE_PLUGIN_DIR", "CLAUDE_CODE_PLUGIN_DIRS")
STARTER_SECONDS = 30
GH_SECONDS = 30
UNREADABLE_RETRY_SECONDS = 60
# A starter that never produced a runner process is gone after this long.
START_GRACE_SECONDS = 300
CLEANUP_DAYS = 7
# Names the generation release stopped, so its runner records a release, not a launch.
RELEASED = "released"
CREATE_NO_WINDOW = 0x08000000
# Whether what keep-warm starts must be windowless Windows processes; one
# name, so the rule is tested on every platform.
WINDOWS = os.name == "nt"
WORK = re.compile(r"\A([^/\s#]+/[^/\s#]+)#([1-9][0-9]*)\Z")
SESSION = re.compile(r"\A[0-9a-f]{8}-[0-9a-f-]{27,}\Z", re.I)


class KeepWarmError(RuntimeError):
    """A keep-warm cannot start or ping on evidence it can trust."""


class LockBusy(OSError):
    """Another process holds a session's ping lock."""


# --- Paths, setting and record ---------------------------------------------

def state_root() -> Path:
    return Path.home() / ".tradecraft" / "keep-warm"


def setting_path() -> Path:
    return Path.home() / ".tradecraft" / "keep-warm.json"


def parse_work(work: object) -> tuple[str, int] | None:
    match = WORK.match(work) if isinstance(work, str) else None
    return (match[1], int(match[2])) if match else None


def record_path(repo: str, issue: int) -> Path:
    # The change's own cost records, never the dispatch store; the cost report reads the same path.
    return change_cost.default_keep_warm(repo, issue)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _moment(value: object) -> float | None:
    parsed = transcripts.timestamp(value)
    return parsed.timestamp() if parsed is not None else None


def append_row(work: str, kind: str, row: dict[str, object], *, at: float | None = None) -> None:
    """One row in one write, so concurrent appenders cannot interleave."""
    parsed = parse_work(work)
    if parsed is None:
        return
    value = {"schema_version": SCHEMA_VERSION, "kind": kind, "session": row.pop("session", None),
             "work": work, "group": row.pop("group", None),
             "at": (datetime.fromtimestamp(at, timezone.utc).isoformat() if at is not None else _now()),
             "generation": row.pop("generation", None), **row}
    path = record_path(*parsed)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as stream:
            stream.write((json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8"))
    except OSError:
        pass  # A record that cannot be written must not hold a launch.


def fault(work: str, stage: str, reason: str, *, session=None, group=None, generation=None,
          command=None, output="") -> None:
    append_row(work, "fault", {"session": session, "group": group, "generation": generation,
                               "stage": stage, "reason": reason, "command": command,
                               "output": str(output or "")[:2000]})


def read_cap_hours() -> tuple[float, str | None]:
    """The machine setting: absent is the default cap, 0 is off, anything unreadable is off."""
    path = setting_path()
    try:
        value = json.loads(path.read_bytes())
    except FileNotFoundError:
        return DEFAULT_CAP_HOURS, None
    except (OSError, UnicodeError, ValueError) as exc:
        return 0, f"keep-warm setting {path} is unreadable: {exc}"
    cap = value.get("cap_hours") if isinstance(value, dict) else None
    if (isinstance(cap, bool) or not isinstance(cap, (int, float)) or not math.isfinite(cap)
            or cap < 0 or cap > MAX_CAP_HOURS):
        return 0, f"keep-warm setting {path} must be {{\"cap_hours\": N}} with 0 <= N <= {MAX_CAP_HOURS}"
    return cap, None


def max_pings(cap_hours: float) -> int:
    return math.floor(cap_hours * 3600 / INTERVAL_SECONDS)


def _write_json(path: Path, value: object) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".kw-", delete=False) as stream:
        staged = Path(stream.name)
        stream.write((json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode("utf-8"))
    try:
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def _read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


# --- Locks -----------------------------------------------------------------

@contextmanager
def session_lock(path: Path, timeout: float = 0):
    """An OS advisory lock, released even when its owner dies; LockBusy past timeout."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        end = time.monotonic() + timeout
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= end:
                    raise LockBusy(f"lock is held: {path}") from exc
                time.sleep(0.05)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


# --- Start, at a local Claude turn's end ---------------------------------

def eligible(turn: dict) -> str | None:
    """Why this turn gets no keep-warm, or None. The root is not a condition."""
    if turn.get("vendor") != "claude":
        return "not a Claude turn"
    if turn.get("cloud"):
        return "a cloud-route turn"
    if not turn.get("launched"):
        return "the attempt did not launch"
    session = turn.get("session")
    if not isinstance(session, str) or not SESSION.match(session) or turn.get("observed_session") != session:
        return "observed session differs from the requested or reserved one"
    if turn.get("outcome") not in RESUMABLE_OUTCOMES:
        return f"outcome {turn.get('outcome')} is not resumed"
    if turn.get("cleanup_proven") is not True or turn.get("launch_unresolved") or turn.get("session_identity_error"):
        return "cleanup, spawn or session identity is unproved"
    if turn.get("stage") not in STAGE_GROUPS:
        return f"stage {turn.get('stage')} is never resumed"
    if parse_work(turn.get("work")) is None:
        return "work is not OWNER/REPO#N"
    return None


def launch_env_changes(start: dict[str, str], child: dict[str, str]) -> tuple[dict, list, list]:
    """The launch's own changes: what it set, what it removed, and anything else."""
    from artifact_tree import _binding
    set_, unset, other = {}, [], []
    for name in sorted(set(start) | set(child)):
        if name in child and start.get(name) != child[name]:
            (set_.__setitem__(name, child[name]) if name in LAUNCH_ENV_NAMES else other.append(name))
        elif name not in child:
            (unset.append(name) if _binding(name) or name in REMOVABLE_ENV_NAMES else other.append(name))
    return set_, unset, other


def ping_argv(command: list[str], settings: Path) -> list[str]:
    """The turn's argv with exactly three changes.

    Design: lib/DESIGN.md#keeping-a-waiting-session-warm
    """
    argv = list(command)
    for index, value in enumerate(argv[:-1]):
        if value == "--settings":
            argv[index + 1] = str(settings)
        elif value == "--session-id":
            # A ping must resume the session, never start one.
            argv[index] = "--resume"
    if "--settings" not in argv:
        raise KeepWarmError("turn command has no --settings")
    argv.append("--no-session-persistence")
    return argv


def _stream_events(raw: bytes) -> list[dict]:
    events = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except (UnicodeError, ValueError):
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _calls(events: list[dict]) -> list[dict]:
    """Each assistant call's native usage once, by message id, in the order calls began.

    A call's later events repeat its id; the last carries its whole usage (output
    counted to the end), and its input-side counters are the same in every event.
    """
    order, usage = [], {}
    for event in events:
        message = event.get("message") if event.get("type") == "assistant" else None
        if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
            continue
        key = message.get("id") or f"anonymous-{len(order)}"
        if key not in usage:
            order.append(key)
        usage[key] = message["usage"]
    return [usage[key] for key in order]


def turn_context(stdout: bytes, model: str) -> tuple[int | None, int | None]:
    """The last call's context and the turn's reported window."""
    events = _stream_events(stdout)
    calls = _calls(events)
    tokens = None
    if calls:
        last = calls[-1]
        try:
            tokens = sum(int(last.get(name) or 0) for name in (
                "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        except (TypeError, ValueError):
            tokens = None
    window = None
    for event in events:
        if event.get("type") == "result" and isinstance(event.get("modelUsage"), dict):
            usage = event["modelUsage"]
            entries = [usage[model]] if isinstance(usage.get(model), dict) else list(usage.values())
            windows = [entry.get("contextWindow") for entry in entries if isinstance(entry, dict)
                       and isinstance(entry.get("contextWindow"), int)]
            window = max(windows) if windows else window
    return tokens, window


def last_call_sent_at(transcript: Path) -> float | None:
    """When the session's last model call was sent.

    The cache entry's hour runs from the send, and a final call can stream for
    minutes; the transcript writes the entry that call answered just before
    sending it, so that entry's time bounds the send from below.
    """
    try:
        with transcript.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            stream.seek(max(0, stream.tell() - 4 * 1024 * 1024))
            tail = stream.read()
    except OSError:
        return None
    reply = None
    for line in reversed(tail.splitlines()):
        try:
            entry = json.loads(line)
        except (UnicodeError, ValueError):
            continue
        if not isinstance(entry, dict):
            continue
        moment = _moment(entry.get("timestamp"))
        if entry.get("type") == "assistant":
            reply = moment if moment is not None else reply
        elif reply is not None and moment is not None:
            return min(moment, reply)
    return reply


def runner_python() -> str:
    """pythonw.exe beside this Python on Windows, so no console window opens."""
    if WINDOWS:
        windowless = Path(sys.executable).with_name("pythonw.exe")
        if windowless.is_file():
            return str(windowless)
    return sys.executable


def after_turn(turn: dict) -> Path | None:
    """Write a waiting session's spec at its turn's end; never raises.

    Returns the state directory whose runner the caller starts, or None. With
    ``starter == "entrance"`` it writes ``start.pending`` instead, for the
    entrance to start after its own cleanup (see ``start_pending``).
    """
    work = turn.get("work")
    try:
        if eligible(turn) is not None:
            return None
        cap, problem = read_cap_hours()
        if problem:
            fault(work, "setting", problem, session=turn["session"])
        if cap <= 0:
            return None
        return _write_spec(turn, cap)
    except Exception as exc:  # A keep-warm fault never changes a launch.
        fault(work, "start", f"{type(exc).__name__}: {exc}", session=turn.get("session"))
        return None


def _write_spec(turn: dict, cap: float) -> Path | None:
    work, session = turn["work"], turn["session"]
    repo, issue = parse_work(work)
    group = STAGE_GROUPS[turn["stage"]]
    env_set, env_unset, other = launch_env_changes(turn["env_start"], turn["env_child"])
    if other:
        fault(work, "start", "the launch changed variables outside its own set: " + ", ".join(other),
              session=session, group=group)
        return None
    if isinstance(turn.get("settings_bytes"), str):
        raise KeepWarmError(turn["settings_bytes"])
    if not turn.get("command") or not turn.get("settings_bytes"):
        raise KeepWarmError("turn has no recorded command or prepared settings")
    prepared = json.loads(turn["settings_bytes"])
    projects = Path(turn["projects"])
    transcript, reason = environments.claude_transcript(projects, session)
    if transcript is None:
        raise KeepWarmError(f"session transcript not found: {reason}")
    stdout = b""
    if turn.get("stdout_path"):
        try:
            stdout = Path(turn["stdout_path"]).read_bytes()
        except OSError:
            stdout = b""
    tokens, window = turn_context(stdout, turn.get("model") or "")
    directory = state_root() / session
    directory.mkdir(parents=True, exist_ok=True)
    ended_at = turn.get("completed_at") or _now()
    last_call = last_call_sent_at(transcript) or _moment(ended_at) or time.time()
    generation = uuid.uuid4().hex
    plugin = Path(turn.get("plugin_root") or Path(__file__).resolve().parent.parent)
    spec = {
        "schema_version": SCHEMA_VERSION, "generation": generation, "work": work, "repo": repo,
        "issue": issue, "instalment": turn.get("instalment"), "stage": turn["stage"],
        "group": group, "session": session,
        "root": str(turn["root"]), "fallback_root": turn.get("fallback_root"),
        "plugin_root": str(plugin),
        "ping_argv": ping_argv(turn["command"], directory / "ping-settings.json"),
        "settings": {"enabledPlugins": prepared.get("enabledPlugins", {})},
        "env_set": env_set, "env_unset": env_unset, "shim": turn.get("shim"),
        "python": runner_python(), "hook_python": sys.executable,
        "gh": shutil.which("gh"),
        "lineage_pull_request": turn.get("lineage_pull_request"),
        "turn_dispatch_id": turn.get("dispatch_id"), "turn_ended_at": ended_at,
        "last_call_at": datetime.fromtimestamp(last_call, timezone.utc).isoformat(),
        "context_tokens": tokens, "context_window": window,
        "transcript": str(transcript), "transcript_size": transcript.stat().st_size,
        "model": turn.get("model"), "cap_hours": cap,
    }
    state = {"schema_version": SCHEMA_VERSION, "generation": generation, "work": work,
             "instalment": turn.get("instalment"), "group": group, "session": session, "created_at": _now(), "process": None,
             "pings": 0, "last_call_at": spec["last_call_at"], "ended": None}
    _write_json(directory / "state.json", state)
    (directory / RELEASED).unlink(missing_ok=True)
    _write_json(directory / "spec.json", spec)
    if turn.get("starter") == "entrance":
        (directory / "start.pending").write_bytes(str(turn.get("start_token") or "").encode("ascii"))
    return directory


def runner_command(directory: Path, python: str | None = None) -> list[str]:
    return [python or runner_python(), "-B", str(Path(__file__).resolve()), "run",
            "--state", str(directory)]


def _windows_spawn(argv: list[str], cwd: Path, env: dict[str, str]) -> int:
    """Create the runner through WMI, outside every job; the environment goes in memory.

    WMI's Win32_Process.Create makes a process no caller's kill-on-close job
    holds, where a breakaway from the launcher's job is refused. The
    environment travels on PowerShell's stdin, never a command line or file.
    """
    script = (
        "$ErrorActionPreference='Stop';"
        "$in=[Console]::In.ReadToEnd()|ConvertFrom-Json;"
        "$vars=[string[]]@($in.env.PSObject.Properties|ForEach-Object{$_.Name+'='+$_.Value});"
        "$startup=New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly "
        "-Property @{ShowWindow=[uint16]0;EnvironmentVariables=$vars};"
        "$r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
        "@{CommandLine=$in.cmd;CurrentDirectory=$in.dir;ProcessStartupInformation=$startup};"
        "if($r.ReturnValue -ne 0){[Console]::Error.WriteLine('Win32_Process.Create returned '+$r.ReturnValue);exit 1};"
        "[Console]::Out.WriteLine($r.ProcessId)"
    )
    payload = json.dumps({"cmd": subprocess.list2cmdline(argv), "dir": str(cwd), "env": env},
                         ensure_ascii=True).encode("ascii")
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=STARTER_SECONDS, creationflags=CREATE_NO_WINDOW)
    if result.returncode != 0:
        raise KeepWarmError("WMI start failed: " + result.stderr.decode("utf-8", "replace").strip()[:1000])
    return int(result.stdout.decode("ascii", "replace").strip().splitlines()[-1])


DETACH = ("import subprocess,sys;"
          "subprocess.Popen(sys.argv[2:],cwd=sys.argv[1],stdin=subprocess.DEVNULL,"
          "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)")


def _posix_spawn(argv: list[str], cwd: Path, env: dict[str, str]) -> int:
    """The standard double fork: an intermediate child in a new session starts the runner and exits.

    The runner is then reparented to the nearest subreaper, the entrance
    itself once its own cleanup has run, so a later cleanup's baseline holds it.
    """
    intermediate = subprocess.Popen([sys.executable, "-B", "-c", DETACH, str(cwd), *argv],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, close_fds=True, env=env,
                                    start_new_session=True)
    code = intermediate.wait(timeout=STARTER_SECONDS)
    if code != 0:
        raise KeepWarmError(f"runner starter exited {code}")
    return 0


def spawn(argv: list[str], cwd: Path, env: dict[str, str]) -> int:
    return (_windows_spawn if WINDOWS else _posix_spawn)(argv, cwd, env)


def start_runner(directory: Path, env: dict[str, str] | None = None, *, spawner=None) -> bool:
    """Start the runner for a written spec; a failure is a fault row, never raised."""
    spec = _read_json(directory / "spec.json") or {}
    work = spec.get("work")
    command = runner_command(directory, spec.get("python"))
    try:
        environment = dict(os.environ if env is None else env)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        (spawner or spawn)(command, directory, environment)
        return True
    except Exception as exc:
        fault(work, "spawn", f"{type(exc).__name__}: {exc}", session=spec.get("session"),
              group=spec.get("group"), generation=spec.get("generation"),
              command=subprocess.list2cmdline(command))
        return False


def start_pending(token: str, env: dict[str, str] | None = None, *, spawner=None) -> None:
    """The entrance starts the runner its launcher left pending, after its own cleanup."""
    try:
        if not token or not state_root().is_dir():
            return
        for marker in state_root().glob("*/start.pending"):
            try:
                if marker.read_bytes().decode("ascii") != token:
                    continue
                marker.unlink()
            except (OSError, UnicodeError):
                continue
            start_runner(marker.parent, env, spawner=spawner)
    except Exception:
        pass  # A keep-warm fault never changes the entrance's result.


def discard_pending(token: str) -> None:
    """A launch the entrance could not see finish starts no runner; its pending start is ended.

    Its run record may be unfinished, so the session is not known to be
    resumable, and a ping must not chase it; never raises.
    """
    try:
        if not token or not state_root().is_dir():
            return
        for marker in state_root().glob("*/start.pending"):
            try:
                if marker.read_bytes().decode("ascii") != token:
                    continue
            except (OSError, UnicodeError):
                continue
            directory = marker.parent
            spec = _read_json(directory / "spec.json") or {}
            (directory / "spec.json").unlink(missing_ok=True)
            marker.unlink(missing_ok=True)
            state = _read_json(directory / "state.json") or {}
            if state.get("generation") == spec.get("generation") and not state.get("ended"):
                state["ended"] = {"reason": "launch-unfinished", "at": _now()}
                _write_json(directory / "state.json", state)
            append_row(spec.get("work"), "end", {"session": spec.get("session"), "group": spec.get("group"),
                                                   "generation": spec.get("generation"),
                                                   "reason": "launch-unfinished", "pings": 0})
    except Exception:
        pass  # A keep-warm fault never changes the entrance's result.


# --- Stop, at the next launch, and release -------------------------------

def _states():
    root = state_root()
    if not root.is_dir():
        return
    for directory in sorted(root.iterdir()):
        if directory.is_dir():
            yield directory


def mark_gone(directory: Path) -> bool:
    """Record a runner killed after it started, exactly once."""
    with session_lock(directory / "state.lock", timeout=5):
        state = _read_json(directory / "state.json")
        if not state or state.get("ended") or not state.get("generation"):
            return False
        process = state.get("process")
        if process:
            if lifecycle._identity_liveness(process) != "stopped":
                return False
        else:
            created = _moment(state.get("created_at"))
            pending = (directory / "start.pending").exists()
            if pending or created is None or time.time() - created < START_GRACE_SECONDS:
                return False
        state["ended"] = {"reason": "runner-gone", "at": _now()}
        _write_json(directory / "state.json", state)
    append_row(state.get("work"), "end", {"session": state.get("session"), "group": state.get("group"),
                                          "generation": state.get("generation"),
                                          "reason": "runner-gone", "pings": state.get("pings", 0)})
    return True


def _in_scope(owner: dict, work: str, instalment: str | None) -> bool:
    """The work's session, in the named instalment; no instalment names the whole change."""
    if str(owner.get("work")).casefold() != work.casefold():
        return False
    return instalment is None or owner.get("instalment") == instalment


@contextmanager
def stop_for_launch(work: str, stage: str, resume: str | None, *, wait_seconds: float | None = None,
                    instalment: str | None = None):
    """Drop the work's waiting sessions in this stage group; hold a resumed session's ping lock.

    It runs at the launcher's start, before any route or vendor split, so a
    replacing launch of any kind ends the old keep-warm.
    """
    group = STAGE_GROUPS.get(stage)
    try:
        directories = list(_states()) if group else []
    except Exception as exc:
        directories = []
        fault(work, "stop", f"{type(exc).__name__}: {exc}", group=group)
    for directory in directories:
        # One session's fault leaves every other matching session still stopped.
        try:
            spec = _read_json(directory / "spec.json")
            state = _read_json(directory / "state.json") or {}
            owner = spec or state
            if not _in_scope(owner, work, instalment) or owner.get("group") != group:
                continue
            (directory / "spec.json").unlink(missing_ok=True)
            (directory / "start.pending").unlink(missing_ok=True)
            mark_gone(directory)
        except Exception as exc:  # A keep-warm fault never changes a launch.
            fault(work, "stop", f"{type(exc).__name__}: {exc}", session=directory.name, group=group)
    directory = state_root() / resume if resume and SESSION.match(resume) else None
    if directory is None or not directory.is_dir():
        yield
        return
    with ExitStack() as held:
        try:
            # A ping in flight ends by its own timeout; the margin covers killing it
            # and writing its row.
            limit = PING_TIMEOUT_SECONDS + 60
            if wait_seconds is not None:
                limit = max(0.0, min(limit, wait_seconds))
            held.enter_context(session_lock(directory / "ping.lock", timeout=limit))
        except Exception as exc:
            fault(work, "lock", f"a ping still held the lock: {exc}" if isinstance(exc, LockBusy)
                  else f"{type(exc).__name__}: {exc}", session=resume, group=group)
        yield


def drop_work(work: str, instalment: str | None = None) -> None:
    """A released change's (or instalment's) waiting sessions get no further ping; each runner ends `released` at its next step."""
    try:
        for directory in list(_states()):
            spec = _read_json(directory / "spec.json")
            if spec and _in_scope(spec, work, instalment):
                (directory / RELEASED).write_bytes(str(spec.get("generation") or "").encode("ascii"))
                (directory / "spec.json").unlink(missing_ok=True)
                (directory / "start.pending").unlink(missing_ok=True)
    except Exception as exc:
        fault(work, "stop", f"{type(exc).__name__}: {exc}")


# --- The ping ---------------------------------------------------------------

def ping_settings(spec: dict) -> dict:
    hook = (f"{_quoted(spec.get('hook_python') or sys.executable)} -B "
            f"{_quoted(Path(spec['plugin_root']) / 'lib' / 'keep_warm.py')} deny")
    return {"enabledPlugins": spec["settings"]["enabledPlugins"],
            "hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": hook}]}]}}


def _quoted(path) -> str:
    # The launch guard's form: one string works under Git Bash and cmd.
    return '"' + str(path).replace("\\", "/") + '"'


def ping_environment(spec: dict, base: dict[str, str] | None = None) -> dict[str, str]:
    """The turn's child environment: the starter's own, with the launch's changes."""
    env = dict(os.environ if base is None else base)
    env.update(spec.get("env_set") or {})
    for name in spec.get("env_unset") or []:
        env.pop(name, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


@contextmanager
def ping_plan(spec: dict, directory: Path):
    """The ping's directory and argv, with its instruction shim while it runs."""
    root, fallback = Path(spec["root"]), spec.get("fallback_root")
    argv = list(spec["ping_argv"])
    if root.is_dir():
        cwd = root
    elif fallback and Path(fallback).is_dir():
        # An accepted author's copy is disposed; its next copy comes from this checkout.
        cwd = Path(fallback)
        argv = _replace_add_dir(argv, str(root), str(cwd))
    else:
        raise KeepWarmError("root-removed")
    shim = spec.get("shim")
    made = None
    if shim:
        # The launch's own instruction file, re-created whole, so the ping is sent what its turns were.
        original = Path(shim["directory"])
        text = shim["text"]
        if original.parent.is_dir() and cwd == root:
            made = original
        else:
            # A relative import resolves only from its own directory; the
            # absolute form is the launcher's own second placement. Only the
            # launcher's import, its file's last line, moves, so every other
            # line still sends what the turns were sent.
            made = directory / original.name
            absolute = "@" + (cwd / "AGENTS.md").as_posix().replace(" ", "\\ ") + "\n"
            lines = text.splitlines(keepends=True)
            if lines and lines[-1].startswith("@"):
                lines[-1] = absolute
            text = "".join(lines)
            argv = _replace_add_dir(argv, str(original), str(made))
        if made.exists():
            made = None  # A directory already there is not the ping's to write or remove.
        else:
            made.mkdir()
            (made / "CLAUDE.md").write_bytes(text.encode("utf-8"))
    try:
        yield cwd, argv
    finally:
        if made is not None:
            shutil.rmtree(made, ignore_errors=True)


def _replace_add_dir(argv: list[str], old: str, new: str) -> list[str]:
    result = list(argv)
    for index, value in enumerate(result[:-1]):
        if value == "--add-dir" and result[index + 1] == old:
            result[index + 1] = new
    return result


# A ping that never reached the model: a known zero, not an unknown.
NOTHING_SPENT = {"calls": [], "total": {name: 0 for name in (
    "input", "output", "cache_read", "cache_creation", "cache_write_5m", "cache_write_1h")},
    "complete": True}


def ping_outcome(returncode: int | None, stdout: bytes, *, timed_out: bool = False
                 ) -> tuple[str, str, dict]:
    """``read``, ``wrote``, ``compacted`` or ``failed``, with a reason and per-call usage."""
    events = _stream_events(stdout)
    calls, problem = [], None
    for usage in _calls(events):
        try:
            calls.append(transcripts.call_classes(usage)[0])
        except transcripts.TranscriptError as exc:
            problem = str(exc)
    complete = problem is None
    total = {name: sum(call.get(name, 0) for call in calls)
             for name in ("input", "output", "cache_read", "cache_creation", "cache_write_5m", "cache_write_1h")}
    # Incomplete usage is priced unknown; a complete empty one spent nothing.
    usage = {"calls": calls, "total": total, "complete": complete}
    results = [event for event in events if event.get("type") == "result"]
    tool_use = any(isinstance(block, dict) and block.get("type") == "tool_use"
                   for event in events if event.get("type") == "assistant"
                   for block in ((event.get("message") or {}).get("content") or []))
    if timed_out:
        return "failed", f"ping exceeded {PING_TIMEOUT_SECONDS} seconds", usage
    if returncode != 0:
        return "failed", f"ping exited {returncode}", usage
    if not results:
        return "failed", "ping returned no result event", usage
    if results[-1].get("is_error"):
        return "failed", "ping result is an error: " + str(results[-1].get("result") or "")[:500], usage
    if tool_use:
        return "failed", "the model tried a tool, which was refused", usage
    if any(event.get("type") == "system" and event.get("subtype") == "compact_boundary" for event in events):
        return "compacted", "resuming the session compacted it", usage
    if problem or not calls:
        return "failed", problem or "ping made no model call", usage
    first = calls[0]
    if first["cache_read"] == 0:
        return "wrote", f"first call read nothing and wrote {first['cache_creation']}", usage
    if first["cache_creation"] > max(WRITE_ALLOWANCE_TOKENS, WRITE_SHARE * first["cache_read"]):
        return "wrote", (f"first call wrote {first['cache_creation']} against a read of "
                         f"{first['cache_read']}"), usage
    return "read", "", usage


def run_ping(spec: dict, directory: Path) -> tuple[str, str, dict]:
    """Resume the session once, saving nothing, with every tool refused."""
    _write_json(directory / "ping-settings.json", ping_settings(spec))
    try:
        plan = ping_plan(spec, directory)
        cwd, argv = plan.__enter__()
    except (KeepWarmError, OSError) as exc:
        return "failed", str(exc), NOTHING_SPENT
    try:
        posix = not WINDOWS
        process = subprocess.Popen(argv, cwd=cwd, env=ping_environment(spec), stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=posix,
                                   creationflags=0 if posix else CREATE_NO_WINDOW)
        timed_out = False
        try:
            stdout, _stderr = process.communicate(PROMPT.encode("utf-8"), timeout=PING_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_tree(process)
            stdout, _stderr = process.communicate()
        try:
            (directory / "last-ping.stdout.jsonl").write_bytes(stdout)
        except OSError:
            pass
        return ping_outcome(process.returncode, stdout, timed_out=timed_out)
    except OSError as exc:
        return "failed", f"cannot run the ping: {exc}", NOTHING_SPENT
    finally:
        plan.__exit__(None, None, None)


def _kill_tree(process: subprocess.Popen) -> None:
    if WINDOWS:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW, timeout=30)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


# --- Change state ------------------------------------------------------------

def registry_released(work: str, instalment: str | None = None) -> bool:
    """The worktree registry has rows for the work (its instalment, where it has one) and none is active."""
    repo, issue = parse_work(work)
    path = Path.home() / ".tradecraft" / "implementation-worktrees.json"
    value = _read_json(path) or {}
    rows = [row for row in value.get("worktrees") or [] if isinstance(row, dict)
            and str(row.get("repository") or "").casefold() == repo.casefold() and row.get("issue") == issue
            and (instalment is None or row.get("instalment") == instalment)]
    return bool(rows) and not any(row.get("active") is True for row in rows)


def _gh(spec: dict, endpoint: str) -> dict | None:
    gh = spec.get("gh") or shutil.which("gh")
    if not gh:
        return None
    try:
        result = subprocess.run([gh, "api", endpoint], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=GH_SECONDS,
                                creationflags=CREATE_NO_WINDOW if WINDOWS else 0)
        value = json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, UnicodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def change_state(spec: dict) -> str | None:
    """``open``, ``closed``, ``merged`` or ``released``; None when it cannot be read."""
    if registry_released(spec["work"], spec.get("instalment")):
        return "released"
    issue = _gh(spec, f"repos/{spec['repo']}/issues/{spec['issue']}")
    if issue is None:
        return None
    if str(issue.get("state") or "").lower() == "closed":
        return "closed"
    number = spec.get("lineage_pull_request")
    if isinstance(number, int):
        pull = _gh(spec, f"repos/{spec['repo']}/pulls/{number}")
        if pull is None:
            return None
        if pull.get("merged_at"):
            return "merged"
        if str(pull.get("state") or "").lower() == "closed":
            return "closed"
    return "open"


# --- The runner ----------------------------------------------------------------

class Runner:
    """One waiting session's keep-warm; every collaborator can be a stub."""

    def __init__(self, directory: Path, *, clock=time.time, sleep=time.sleep, ping=run_ping,
                 state_reader=change_state, lock=session_lock, identity=lifecycle.process_identity):
        self.directory = Path(directory)
        self.clock, self.sleep, self.ping = clock, sleep, ping
        self.state_reader, self.lock, self.identity = state_reader, lock, identity
        self.spec: dict = {}
        self.generation = None

    # The state file is shared by a session's generations; only the current one writes it.
    def _state(self) -> dict:
        return _read_json(self.directory / "state.json") or {}

    def _save(self, state: dict) -> None:
        if self._state().get("generation") in (None, self.generation):
            _write_json(self.directory / "state.json", state)

    def _row(self, kind: str, **fields) -> None:
        append_row(self.spec["work"], kind, {"session": self.spec["session"], "group": self.spec["group"],
                                             "generation": self.generation, **fields}, at=self.clock())

    def _end(self, state: dict, reason: str) -> str:
        self._row("end", reason=reason, pings=state.get("pings", 0))
        state["ended"] = {"reason": reason, "at": _now()}
        self._save(state)
        return reason

    def _spec_changed(self) -> str | None:
        current = _read_json(self.directory / "spec.json")
        if current is None:
            try:
                released = (self.directory / RELEASED).read_bytes().decode("ascii") == self.generation
            except (OSError, UnicodeError):
                released = False
            return "released" if released else "stopped-by-launch"
        if current.get("generation") != self.generation:
            return "superseded"
        return None

    def _cap(self) -> float:
        cap, _problem = read_cap_hours()
        return min(cap, self.spec.get("cap_hours", DEFAULT_CAP_HOURS))

    def guards(self, state: dict, now: float, cap: float, *, timer: bool = True) -> str | None:
        """The first guard that refuses, in order, or None."""
        spec = self.spec
        if timer and (now >= (_moment(spec["turn_ended_at"]) or 0) + cap * 3600
                      or state.get("pings", 0) >= max_pings(cap)):
            return "cap"
        if now - (_moment(state["last_call_at"]) or 0) > LAPSE_SECONDS:
            return "lapsed"
        if not Path(spec["root"]).is_dir() and not (spec.get("fallback_root")
                                                   and Path(spec["fallback_root"]).is_dir()):
            return "root-removed"
        try:
            size = Path(spec["transcript"]).stat().st_size
        except OSError:
            size = None
        if size != spec["transcript_size"]:
            return "outside-use"
        window = spec.get("context_window") or FALLBACK_CONTEXT_WINDOW
        if spec.get("context_tokens") is not None and spec["context_tokens"] >= CONTEXT_SHARE * window:
            return "too-large"
        status = self.state_reader(spec)
        if status is None:
            # One GitHub read timing out is common; read once more after a wait.
            if self.clock() + UNREADABLE_RETRY_SECONDS - (_moment(state["last_call_at"]) or 0) > LAPSE_SECONDS:
                return "lapsed"
            self.sleep(UNREADABLE_RETRY_SECONDS)
            changed = self._spec_changed()
            if changed:
                return changed
            status = self.state_reader(spec)
            if status is None:
                return "change-state-unreadable"
            if self.clock() - (_moment(state["last_call_at"]) or 0) > LAPSE_SECONDS:
                return "lapsed"
        if status != "open":
            return status
        return None

    def ping_once(self, state: dict) -> str:
        """Ping under the session's lock; returns the outcome or the reason none was sent."""
        try:
            with self.lock(self.directory / "ping.lock", 0):
                changed = self._spec_changed()
                if changed:
                    return changed
                started = self.clock()
                outcome, reason, usage = self.ping(self.spec, self.directory)
                self._row("ping", model=self.spec.get("model"),
                          idle_seconds=round(started - (_moment(state["last_call_at"]) or started), 3),
                          usage=usage, outcome=outcome, reason=reason)
                state["pings"] = state.get("pings", 0) + 1
                state["last_call_at"] = datetime.fromtimestamp(started, timezone.utc).isoformat()
                self._save(state)
                return outcome
        except LockBusy:
            return "turn-running"

    def begin(self) -> dict | None:
        self.spec = _read_json(self.directory / "spec.json") or {}
        self.generation = self.spec.get("generation")
        if not self.generation or not self.spec.get("work"):
            return None
        state = self._state()
        if state.get("generation") != self.generation:
            state = {"schema_version": SCHEMA_VERSION, "generation": self.generation,
                     "work": self.spec["work"], "group": self.spec["group"],
                     "session": self.spec["session"], "created_at": _now(), "pings": 0,
                     "last_call_at": self.spec["last_call_at"], "ended": None}
        try:
            state["process"] = self.identity()
        except (OSError, ProcessLookupError):
            state["process"] = None
        self._save(state)
        return state

    def run(self) -> str | None:
        state = self.begin()
        if state is None:
            return None
        _cleanup_ended(self.clock())
        while True:
            changed = self._spec_changed()
            if changed:
                return self._end(state, changed)
            cap = self._cap()
            if cap <= 0:
                return self._end(state, "setting-off")
            now = self.clock()
            due = (_moment(state["last_call_at"]) or now) + INTERVAL_SECONDS
            if now < due:
                self.sleep(min(60, due - now))  # Wall-clock steps: a machine sleep counts.
                continue
            refused = self.guards(state, now, cap)
            if refused:
                return self._end(state, refused)
            outcome = self.ping_once(state)
            if outcome != "read":
                return self._end(state, outcome)

    def ping_now(self) -> dict:
        """One guarded ping now, for probes: every guard but the timer."""
        state = self._state()
        self.spec = _read_json(self.directory / "spec.json") or {}
        self.generation = self.spec.get("generation")
        if not self.generation:
            return {"sent": False, "reason": "no spec"}
        refused = self.guards(state, self.clock(), self._cap(), timer=False)
        if refused:
            return {"sent": False, "reason": refused}
        outcome = self.ping_once(state)
        return {"sent": outcome in {"read", "wrote", "compacted", "failed"}, "outcome": outcome}


def _cleanup_ended(now: float) -> None:
    for directory in list(_states()):
        state = _read_json(directory / "state.json") or {}
        ended = _moment((state.get("ended") or {}).get("at"))
        if ended is not None and now - ended > CLEANUP_DAYS * 86400 and not (directory / "spec.json").exists():
            shutil.rmtree(directory, ignore_errors=True)


def status(work: str | None = None) -> list[dict]:
    """Every keep-warm state; a dead runner found here is recorded runner-gone."""
    listing = []
    for directory in list(_states()):
        state = _read_json(directory / "state.json") or {}
        spec = _read_json(directory / "spec.json")
        if work is not None and (spec or state).get("work") != work:
            continue
        try:
            mark_gone(directory)
        except OSError:
            pass
        state = _read_json(directory / "state.json") or state
        listing.append({"session": directory.name, "work": (spec or state).get("work"),
                        "group": (spec or state).get("group"), "waiting": spec is not None,
                        "pings": state.get("pings"), "last_call_at": state.get("last_call_at"),
                        "process": state.get("process"), "ended": state.get("ended")})
    return listing


def deny() -> int:
    try:
        sys.stdin.read()
    except (OSError, ValueError, AttributeError):
        pass
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": DENY_REASON}}))
    return 0


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    cli = argparse.ArgumentParser(description="Keep a waiting local Claude session in the one-hour cache.")
    commands = cli.add_subparsers(dest="command", required=True)
    for name in ("run", "ping-now"):
        command = commands.add_parser(name)
        command.add_argument("--state", type=Path, required=True)
    commands.add_parser("deny")
    listing = commands.add_parser("status")
    listing.add_argument("--work")
    args = cli.parse_args(argv)
    if args.command == "deny":
        return deny()
    if args.command == "status":
        print(json.dumps(status(args.work), ensure_ascii=True, indent=2))
        return 0
    runner = Runner(args.state)
    if args.command == "run":
        runner.run()
        return 0
    print(json.dumps(runner.ping_now(), ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

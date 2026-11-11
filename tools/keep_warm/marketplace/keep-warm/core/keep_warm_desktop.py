#!/usr/bin/env python3
"""The desktop keep-warm's decisions: when a short turn keeps a session's cache warm.

Design: tools/keep_warm/README.md#how-it-behaves

Lab-only tooling (#983). The `keep-warm` mod's hooks module is wiring: it runs
this file as `python keep_warm_desktop.py <subcommand> --session <id> ...` and
reads one JSON object from standard output. Whether a session is kept warm,
when a keep-warm turn is due, and whether one that ran broke the rules are all
decided here, so the behaviour is testable with pytest and without Claude Code.

State lives in one directory: `--state-dir`, else KEEP_WARM_LAB_STATE_DIR,
else `~/.tradecraft-lab/keep-warm`. It holds `sessions/<id>.json` per session
and `log.jsonl`. Probe-only timings are refused against the default directory,
so a probe can neither leave state in nor change the live sessions' timings.

Standard library only: the plugin folder is all the mod loads.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

STATE_ENV = "KEEP_WARM_LAB_STATE_DIR"

# The production values, the shipped keep-warm's own: a turn just inside the
# cache's hour, at most eight of them over at most eight hours.
INTERVAL_SECONDS = 3300
LAPSE_SECONDS = 3420
CAP_SECONDS = 8 * 3600
CAP_TURNS = 8
TICK_SECONDS = 60
MISS_FLOOR_TOKENS = 20_000
MISS_SHARE = 0.05
CONTEXT_SHARE = 0.90
FALLBACK_WINDOW = 1_000_000

# Settings only a probe may change, each with the production value it replaces.
PROBE_ENV = {
    "KEEP_WARM_DESKTOP_INTERVAL_SECONDS": ("interval_seconds", INTERVAL_SECONDS),
    "KEEP_WARM_DESKTOP_LAPSE_SECONDS": ("lapse_seconds", LAPSE_SECONDS),
    "KEEP_WARM_DESKTOP_CAP_SECONDS": ("cap_seconds", CAP_SECONDS),
    "KEEP_WARM_DESKTOP_TICK_SECONDS": ("tick_seconds", TICK_SECONDS),
}

MARK = "[tradecraft keep-warm]"
TEXT = (f"{MARK} This turn is the practice's keep-warm, not the owner speaking. "
        "Answer with one word and use no tools.")

# A transcript is read from its end; the whole file only when the tail lacks what is sought.
TAIL_BYTES = 4 * 1024 * 1024

Runner = Callable[..., Any]


class KeepWarmError(Exception):
    """A fault the caller must see, named in plain words."""


class Ctx:
    """What the core reads from the machine: the state directory, clock, environment and git."""

    def __init__(self, state_dir: Path, *, now: float | None = None,
                 environ: dict[str, str] | None = None, runner: Runner | None = None,
                 settings: dict[str, int] | None = None) -> None:
        self.state_dir = state_dir
        self._now = now
        self.environ = environ if environ is not None else dict(os.environ)
        self.runner = runner if runner is not None else subprocess.run
        self.settings = settings if settings is not None else production()

    def now(self) -> float:
        return self._now if self._now is not None else time.time()


# --- the state directory and its settings ------------------------------------------

def default_state_dir() -> Path:
    return Path.home() / ".tradecraft-lab" / "keep-warm"


def resolve_state_dir(flag: str | None, environ: dict[str, str] | None = None) -> Path:
    environ = os.environ if environ is None else environ
    chosen = flag or environ.get(STATE_ENV) or None
    return Path(chosen).expanduser() if chosen else default_state_dir()


def is_default_dir(path: Path) -> bool:
    return os.path.normcase(os.path.abspath(path)) == os.path.normcase(
        os.path.abspath(default_state_dir()))


def production() -> dict[str, int]:
    return {key: value for key, value in PROBE_ENV.values()}


def settings_for(state_dir: Path, env_values: dict[str, str]) -> dict[str, int]:
    """The timings in force: production, or a probe's, which the default directory refuses."""
    given = {name: value for name, value in env_values.items() if value not in (None, "")}
    unknown = sorted(set(given) - set(PROBE_ENV))
    if unknown:
        raise KeepWarmError("unknown setting(s): " + ", ".join(unknown))
    if given and is_default_dir(state_dir):
        raise KeepWarmError(
            "probe-only setting(s) " + ", ".join(sorted(given))
            + " refused against the default state directory " + str(state_dir)
            + "; set --state-dir or " + STATE_ENV + " to a probe directory")
    settings = production()
    for name, value in given.items():
        try:
            settings[PROBE_ENV[name][0]] = int(value)
        except ValueError:
            raise KeepWarmError(f"{name} is not a whole number of seconds: {value!r}") from None
    return settings


# --- small file helpers ------------------------------------------------------------

def _safe(session_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", session_id)[:128] or "_"


def session_path(ctx: Ctx, session_id: str) -> Path:
    return ctx.state_dir / "sessions" / f"{_safe(session_id)}.json"


def iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    temp.write_bytes((json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    os.replace(temp, path)


def load_state(ctx: Ctx, session_id: str) -> dict[str, Any] | None:
    try:
        value = json.loads(session_path(ctx, session_id).read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def save_state(ctx: Ctx, session_id: str, state: dict[str, Any]) -> None:
    _write_json(session_path(ctx, session_id), state)


def log(ctx: Ctx, session_id: str, event: str, **detail: Any) -> None:
    """Append one line to `log.jsonl`: the probes and the owner read what happened there."""
    entry = {"at": iso(ctx.now()), "session": session_id, "event": event, **detail}
    path = ctx.state_dir / "log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        stream.write((json.dumps(entry, sort_keys=True) + "\n").encode("utf-8"))


# --- the session's transcript --------------------------------------------------------

def claude_projects(environ: dict[str, str]) -> Path:
    """The transcript root the session writes: CLAUDE_CONFIG_DIR's, else ~/.claude's."""
    configured = environ.get("CLAUDE_CONFIG_DIR", "")
    return (Path(configured).expanduser() if configured else Path.home() / ".claude") / "projects"


def transcript_path(ctx: Ctx, session_id: str) -> Path | None:
    """The one transcript for the session; none when it is absent or not one file."""
    try:
        found = list(claude_projects(ctx.environ).glob(f"*/{_safe(session_id)}.jsonl"))
    except OSError:
        return None
    return found[0] if len(found) == 1 else None


def _entries(path: Path, whole: bool = False) -> list[dict[str, Any]]:
    try:
        with path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            start = 0 if whole else max(0, size - TAIL_BYTES)
            stream.seek(start)
            data = stream.read()
    except OSError:
        return []
    lines = data.split(b"\n")
    if start > 0:
        lines = lines[1:]  # the first line read from a tail is partial
    entries = []
    for line in lines:
        try:
            value = json.loads(line.decode("utf-8"))
        except ValueError:
            continue
        if isinstance(value, dict):
            entries.append(value)
    return entries


def _is_call(entry: dict[str, Any]) -> bool:
    """A model call the session made: a main-loop assistant entry with usage, not a synthetic one."""
    message = entry.get("message")
    return (entry.get("type") == "assistant" and not entry.get("isSidechain")
            and isinstance(message, dict) and isinstance(message.get("usage"), dict)
            and message.get("model") != "<synthetic>")


def _user_text(entry: dict[str, Any]) -> str:
    if entry.get("type") != "user":
        return ""
    content = (entry.get("message") or {}).get("content") if isinstance(
        entry.get("message"), dict) else None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(block.get("text", "")) for block in content
                         if isinstance(block, dict) and block.get("type") == "text")
    return ""


def last_call(ctx: Ctx, session_id: str) -> float | None:
    """When the session's last model call was answered, from its transcript."""
    path = transcript_path(ctx, session_id)
    if path is None:
        return None
    for whole in (False, True):
        for entry in reversed(_entries(path, whole)):
            if _is_call(entry):
                return _epoch(entry.get("timestamp"))
    return None


def own_turn(ctx: Ctx, session_id: str) -> list[dict[str, Any]] | None:
    """The transcript from the last keep-warm prompt onward; none when it can't be found."""
    path = transcript_path(ctx, session_id)
    if path is None:
        return None
    for whole in (False, True):
        entries = _entries(path, whole)
        for index in range(len(entries) - 1, -1, -1):
            if MARK in _user_text(entries[index]):
                return entries[index:]
    return None


def missed(read: int, written: int) -> bool:
    """The write rule: a first call that read nothing missed, whatever it wrote."""
    return read == 0 or written > max(MISS_FLOOR_TOKENS, MISS_SHARE * read)


# --- the decisions --------------------------------------------------------------------

def main_checkout(ctx: Ctx, root: Path) -> Path:
    """The checkout git lists first, which is the main one; else the root itself."""
    try:
        completed = ctx.runner(["git", "-C", str(root), "worktree", "list", "--porcelain"],
                               stdin=subprocess.DEVNULL, capture_output=True)
    except OSError:
        return root
    text = completed.stdout.decode("utf-8", errors="replace") if isinstance(
        completed.stdout, bytes) else str(completed.stdout or "")
    if completed.returncode == 0:
        for line in text.splitlines():
            if line.startswith("worktree "):
                return Path(line[len("worktree "):].strip())
    return root


def _fresh(session_id: str) -> dict[str, Any]:
    return {"schema_version": 1, "session_id": session_id, "inert": True, "root": None,
            "main_checkout": None, "last_real_end": None, "stopped": None, "count": 0,
            "turn_open": False, "opened_at": None}


def load(ctx: Ctx, session_id: str, root: str) -> dict[str, Any]:
    """Session start: inert unless the root's main checkout has adopted the practice."""
    checkout = main_checkout(ctx, Path(root))
    inert = not (checkout / ".tradecraft" / "work.json").is_file()
    state = load_state(ctx, session_id)
    if state is None:
        state = _fresh(session_id)
        state["last_real_end"] = last_call(ctx, session_id)
    if state.get("turn_open"):
        # A start opens no turn of ours: one left open belongs to a process that has gone.
        state["turn_open"] = False
        log(ctx, session_id, "turn-closed-at-load", opened_at=state.get("opened_at"))
    state.update({"inert": inert, "root": str(root), "main_checkout": str(checkout)})
    save_state(ctx, session_id, state)
    return {"inert": inert, "main_checkout": str(checkout), **ctx.settings}


def _stop(ctx: Ctx, session_id: str, state: dict[str, Any], reason: str, **detail: Any) -> None:
    state["stopped"] = {"reason": reason, "at": iso(ctx.now()), **detail}
    log(ctx, session_id, "stopped", reason=reason, **detail)


def due(ctx: Ctx, session_id: str, turn_running: bool, context_tokens: int,
        window: int | None = None) -> dict[str, Any]:
    """Whether a keep-warm turn is due now, and its text when it is."""
    settings = ctx.settings
    state = load_state(ctx, session_id)

    def no(reason: str, **extra: Any) -> dict[str, Any]:
        return {"submit": False, "reason": reason, **extra}

    if state is None or state.get("inert", True):
        return no("inert")
    if turn_running:
        return no("turn-running")
    if state.get("turn_open"):
        return no("turn-open")
    stopped = state.get("stopped")
    if stopped:
        return no("stopped", why=stopped.get("reason") if isinstance(stopped, dict) else None)
    now = ctx.now()
    called = last_call(ctx, session_id)
    if called is None:
        return no("no-call")
    if now - called > settings["lapse_seconds"]:
        # Past the cache's life the prefix is gone; a turn now would pay to rebuild it.
        _stop(ctx, session_id, state, "lapsed", last_call=iso(called))
        save_state(ctx, session_id, state)
        return no("lapsed")
    if now - called < settings["interval_seconds"]:
        return no("not-yet")
    if int(state.get("count") or 0) >= CAP_TURNS:
        return no("cap-turns")
    real = state.get("last_real_end")
    if not isinstance(real, (int, float)):
        return no("no-real-turn")
    if now - real >= settings["cap_seconds"]:
        return no("cap-hours")
    limit = window if isinstance(window, int) and window > 0 else FALLBACK_WINDOW
    if context_tokens >= CONTEXT_SHARE * limit:
        return no("context")
    return {"submit": True, "text": TEXT}


def submitted(ctx: Ctx, session_id: str) -> dict[str, Any]:
    state = load_state(ctx, session_id) or _fresh(session_id)
    state["turn_open"] = True
    state["opened_at"] = iso(ctx.now())
    state["count"] = int(state.get("count") or 0) + 1
    save_state(ctx, session_id, state)
    log(ctx, session_id, "submitted", count=state["count"])
    return {"turn_open": True, "count": state["count"]}


def _check_own_turn(ctx: Ctx, session_id: str, state: dict[str, Any]) -> str | None:
    """Read the keep-warm turn back: a tool call or a missed first call stops the session."""
    entries = own_turn(ctx, session_id)
    if entries is None:
        _stop(ctx, session_id, state, "unverified", detail="the keep-warm prompt is not in "
              "the transcript")
        return "unverified"
    names = []
    for entry in entries:
        message = entry.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if entry.get("type") == "assistant" and isinstance(content, list):
            names += [str(block.get("name")) for block in content
                      if isinstance(block, dict) and block.get("type") == "tool_use"]
    if names:
        _stop(ctx, session_id, state, "tool-use", tools=names)
        return "tool-use"
    calls = [entry for entry in entries if _is_call(entry)]
    if not calls:
        _stop(ctx, session_id, state, "unverified", detail="no call answered the keep-warm prompt")
        return "unverified"
    usage = calls[0]["message"]["usage"]
    read = int(usage.get("cache_read_input_tokens") or 0)
    written = int(usage.get("cache_creation_input_tokens") or 0)
    if missed(read, written):
        _stop(ctx, session_id, state, "miss", cache_read=read, cache_write=written)
        return "miss"
    log(ctx, session_id, "warm", cache_read=read, cache_write=written)
    return None


def turn_end(ctx: Ctx, session_id: str, own: bool) -> dict[str, Any]:
    state = load_state(ctx, session_id) or _fresh(session_id)
    fault = None
    if own:
        fault = _check_own_turn(ctx, session_id, state)
    else:
        state["last_real_end"] = ctx.now()
        state["stopped"] = None
        state["count"] = 0
    state["turn_open"] = False
    save_state(ctx, session_id, state)
    return {"own": own, "fault": fault, "stopped": state.get("stopped")}


def fault(ctx: Ctx, session_id: str, text: str) -> dict[str, Any]:
    """The module's own faults: it writes no file, so it hands them here."""
    log(ctx, session_id, "module-fault", text=text[:500])
    return {"logged": True}


# --- the command line ----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="The desktop keep-warm's decisions (#983); one JSON object out.")
    sub = parser.add_subparsers(dest="command", required=True)

    def command(name: str, help_text: str) -> argparse.ArgumentParser:
        one = sub.add_parser(name, help=help_text, description=help_text)
        one.add_argument("--session", required=True)
        one.add_argument("--state-dir", help="local state directory (default: the "
                         f"{STATE_ENV} variable, else ~/.tradecraft-lab/keep-warm)")
        one.add_argument("--env", action="append", default=[], metavar="NAME=VALUE",
                         help="a probe-only timing; refused against the default directory")
        return one

    one = command("load", "session start: decide whether the session is kept warm")
    one.add_argument("--root", required=True)
    one = command("due", "whether a keep-warm turn is due now")
    one.add_argument("--turn-running", type=int, choices=(0, 1), required=True)
    one.add_argument("--context-tokens", type=int, required=True)
    one.add_argument("--window", type=int)
    command("submitted", "record that a keep-warm turn was submitted")
    one = command("turn-end", "a main turn ended: check an own turn, or record a real one")
    one.add_argument("--own", type=int, choices=(0, 1), required=True)
    one = command("fault", "log a fault the module met")
    one.add_argument("--text", required=True)
    return parser


def run(args: argparse.Namespace, ctx: Ctx | None = None) -> dict[str, Any]:
    if ctx is None:
        state_dir = resolve_state_dir(args.state_dir)
        values = dict(item.split("=", 1) for item in args.env if "=" in item)
        ctx = Ctx(state_dir, settings=settings_for(state_dir, values))
    if args.command == "load":
        return load(ctx, args.session, args.root)
    if args.command == "due":
        return due(ctx, args.session, bool(args.turn_running), args.context_tokens, args.window)
    if args.command == "submitted":
        return submitted(ctx, args.session)
    if args.command == "turn-end":
        return turn_end(ctx, args.session, bool(args.own))
    if args.command == "fault":
        return fault(ctx, args.session, args.text)
    raise KeepWarmError(f"unknown command {args.command}")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", newline="")
    args = build_parser().parse_args(argv)
    try:
        value = run(args)
    except KeepWarmError as error:
        sys.stdout.write(json.dumps({"error": str(error)}, sort_keys=True) + "\n")
        return 2
    sys.stdout.write(json.dumps(value, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

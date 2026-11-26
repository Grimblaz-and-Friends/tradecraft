"""How a launched builder is doing, read from its launch's own records, and the holder's wait that prints it.

The wait is a read, never a stage: it is not the builder's parent, takes no lock, writes no file and
reads only files on this machine, so a holder runs it in its runtime's background, the owner sees it
there as a running task, and only its end wakes the holder. The "with builder" decision reads the
same facts through `reading`, so the two never disagree.
Design: lib/DESIGN.md#the-builder-route
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shlex
import sys
import time

import launch_tree
import run_lifecycle as lifecycle

# Each step shows soon after the builder takes it; a poll opens, reads and closes each file once, so a launcher
# replacing its run record is never held off for longer than one read.
POLL_SECONDS = 5.0
# Often enough that an owner opening the task sees a recent line, rarely enough not to bury the steps.
STATUS_SECONDS = 300.0
# A read that fails while the launcher replaces its record is retried silently; one failing this long is said.
UNREADABLE_SECONDS = 60.0
# Long enough together to outlast a launcher's replace of its record, short enough that a wait with no builder
# still ends at once.
LISTING_TRIES = 3
LISTING_PAUSE_SECONDS = 0.5
# A wait started mid-build, after a restart, opens with the builder's last few steps, enough to show where it
# is without replaying hours of them.
EARLIER_STEPS = 3
WHAT_LIMIT = 120
CLAUDE_FORM = "claude-stream-json"
# The record types of Claude's stream form; a log whose first record is none of them is in another form.
CLAUDE_TYPES = frozenset({"system", "assistant", "user", "tool_progress", "result", "rate_limit_event",
                          "stream_event"})
# What a step acts on, the target before its scope: a file before a folder, a search pattern before the folder it
# searches, so the line names the thing the builder is working on.
MAIN_ARGUMENTS = ("file_path", "notebook_path", "pattern", "path", "skill", "command", "url", "query", "prompt")
HAND_NOT_MEASURED = ("a builder started by hand isn't measured: the owner started that session and sees it "
                     "there, and no launch records its time, limit or steps")
WAIT_SENTENCE = ("Start this in your runtime's background, so that only its end wakes you; don't read its lines "
                 "or check on the builder while it runs. The builder's own closing message still comes when it "
                 "ends on its own, where its handoff named you with --notify; when the wait ends with no message "
                 "from it, read the decision once and tell the owner what it says; where that decision still reads "
                 "with-builder, start the wait again once, and no more.")


def wait_command(repo: str, issue: int, holder_root, plugin_root, instalment: str | None = None) -> str:
    """The command a holder starts in its background for this work, written as the handoff writes its commands.

    Its quoting is POSIX's, which the Bash and PowerShell a holder's runtime runs on Windows both read the same
    for a path with no apostrophe in it, and it names `python` as every entrance command does.
    """
    argv = ["python", "-B", str(plugin_root).rstrip("/\\") + "/lib/work.py", "wait", "--repo", repo,
            "--issue", str(issue), "--root", str(holder_root), *(["--instalment", instalment] if instalment else [])]
    return " ".join(shlex.quote(part) for part in argv)


def _moment(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    # A time with no zone can't be set against the clock without guessing its zone, so it reads as unread.
    return moment if moment.tzinfo is not None else None


def _number(value) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else None


def _what(tool_input) -> str:
    """The step's own one-line account where it gave one, else its main argument, on one line and cut short."""
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    text = tool_input.get("description")
    if not isinstance(text, str) or not text.strip():
        text = next((tool_input[key] for key in MAIN_ARGUMENTS
                     if isinstance(tool_input.get(key), str) and tool_input[key].strip()), "")
        if text == tool_input.get("command"):
            # A command runs one line after another, so its first is what it starts with; a mark says more followed.
            lines = text.strip().splitlines()
            text = lines[0] + (" ..." if len(lines) > 1 else "") if lines else ""
    text = " ".join(text.split())
    return text if len(text) <= WHAT_LIMIT else text[:WHAT_LIMIT - 3] + "..."


class Step:
    def __init__(self, tool: str, what: str, helper: bool, at: datetime | None, identity: str | None):
        self.tool, self.what, self.helper, self.at, self.identity = tool, what, helper, at, identity

    def text(self) -> str:
        return f"{self.tool}: {self.what}" if self.what else self.tool


class Log:
    """A builder's log read forward from where the last read stopped: its steps, and when it last did anything.

    Each read opens, reads and closes the file. ``form`` is the attempt's ``source_format``, which the launcher
    names as it starts the attempt; a record that names none is read by its first record rather than refused, so
    a log from a writer that records no format still shows its steps if it is Claude's stream form.
    """

    def __init__(self, path, form: str | None = None):
        self.path = Path(path) if path else None
        self.offset, self.partial = 0, b""
        self.steps: list[Step] = []
        self.seen: set[str] = set()
        self.finished: set[str] = set()
        self.activity: datetime | None = None
        self.readable = None if form is None else form == CLAUDE_FORM

    def read(self) -> list[Step]:
        """The steps appended since the last read; OSError when the file can't be read."""
        if self.path is None:
            raise OSError("the run record names no builder log yet")
        with self.path.open("rb") as stream:
            stream.seek(self.offset)
            data = stream.read()
        self.offset += len(data)
        lines = (self.partial + data).split(b"\n")
        self.partial = lines.pop()
        new = []
        for raw in lines:
            if not raw.strip():
                continue
            try:
                record = json.loads(raw)
            except ValueError:
                record = None
            if self.readable is None:
                self.readable = isinstance(record, dict) and record.get("type") in CLAUDE_TYPES
            if self.readable and isinstance(record, dict):
                new.extend(self._record(record))
        return new

    def _record(self, record: dict) -> list[Step]:
        kind = record.get("type")
        if kind not in ("assistant", "user"):
            return []  # Heartbeats and system records keep the file fresh while nothing begins or ends.
        at = _moment(record.get("timestamp"))
        if at is not None and (self.activity is None or at > self.activity):
            self.activity = at
        message = record.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        blocks = [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []
        if kind == "user":
            self.finished.update(block.get("tool_use_id") for block in blocks
                                 if block.get("type") == "tool_result" and isinstance(block.get("tool_use_id"), str))
            return []
        new = []
        for block in blocks:
            if block.get("type") != "tool_use":
                continue
            identity = block.get("id") if isinstance(block.get("id"), str) else None
            # Counted by its id, so a record written twice is one step and the count matches the log's ids.
            if identity is not None and identity in self.seen:
                continue
            if identity is not None:
                self.seen.add(identity)
            step = Step(str(block.get("name") or "tool"), _what(block.get("input")),
                        record.get("parent_tool_use_id") is not None, at, identity)
            self.steps.append(step)
            new.append(step)
        return new


class Launch:
    """One launched builder's pointer, request and run record: the run record read whole on every read, the
    request once, since the launcher writes it once."""

    def __init__(self, pointer: dict):
        self.pointer = pointer
        self.request: dict | None = None
        self.run: dict = {}
        self.run_written: datetime | None = None
        self.log: Log | None = None

    def read_request(self) -> None:
        if self.request is None:
            value = json.loads(Path(self.pointer["request"]).read_bytes())
            if not isinstance(value, dict):
                raise ValueError("the request record is not an object")
            self.request = value

    def read_run(self) -> None:
        """The run record as it stands; a launch whose launcher hasn't written it yet reads as empty."""
        path = Path(self.pointer["run"])
        try:
            value = json.loads(path.read_bytes())
            written = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        except FileNotFoundError:
            value, written = {}, None
        if not isinstance(value, dict):
            raise ValueError("the run record is not an object")
        self.run, self.run_written = value, written
        attempts = value.get("attempts")
        attempt = attempts[-1] if isinstance(attempts, list) and attempts and isinstance(attempts[-1], dict) else {}
        path = attempt.get("stdout")
        if path and (self.log is None or self.log.path != Path(path)):
            # A new attempt writes a new log; its steps are read from its start, and the builder was last active
            # when the attempt before it was, not when the launch began. A first read of a retried launch reads
            # that earlier log once for it, so a fresh read and a long wait agree.
            previous = self.log
            self.log = Log(path, attempt.get("source_format"))
            if previous is None and len(attempts) > 1 and isinstance(attempts[-2], dict) and attempts[-2].get("stdout"):
                previous = Log(attempts[-2]["stdout"], attempts[-2].get("source_format"))
                try:
                    previous.read()
                except OSError:
                    pass
            if previous is not None:
                self.log.activity = previous.activity

    @property
    def started(self) -> datetime | None:
        return _moment(self.run.get("launched_at")) or _moment((self.request or {}).get("launched_at"))

    @property
    def limit(self) -> float | None:
        # The launch's own limit first: a resume carries the first launch's handoff block, whose limit isn't its own.
        request = self.request or {}
        handoff = request.get("handoff") if isinstance(request.get("handoff"), dict) else {}
        return _number(request.get("caller_limit_seconds")) or _number(handoff.get("timeout_seconds"))

    @property
    def builder_started(self) -> datetime | None:
        """When the builder itself started, which can be minutes after the launch while its launcher prepares.

        The launcher counts its elapsed checkpoint from that start and rewrites the record with it, so the record's
        write time less that count is the start. It is held between the launch and the end of the launch's
        preflight cap, the latest the launcher may start it, so a launcher that stopped writing can't move it on.
        """
        launched = self.started
        elapsed = _number(self.run.get("elapsed_checkpoint_seconds"))
        if launched is None or elapsed is None or self.run_written is None:
            return launched
        cap = (self.request or {}).get("preflight_cap")
        cap = _number(cap.get("seconds")) if isinstance(cap, dict) else None
        latest = launched + timedelta(seconds=cap or lifecycle.PREFLIGHT_CAP_SECONDS)
        return min(max(self.run_written - timedelta(seconds=elapsed), launched), latest)

    @property
    def bound(self) -> datetime | None:
        """The builder's own start plus its limit plus the stage's cleanup reserve, after which the wait ends.

        The launcher stops its builder at that limit, counted from the builder's start, and completes the record
        within the reserve, so the wait ends no earlier than the builder and runs no later than its window.
        """
        start = self.builder_started
        if start is None or self.limit is None:
            return None
        return start + timedelta(seconds=self.limit + lifecycle.cleanup_reserve(self.limit))

    @property
    def completed(self) -> bool:
        return bool(self.run.get("completed_at"))

    def stopped(self) -> bool:
        # A run record not yet written names no launcher, and with none the launch would read as stopped at once;
        # the pointer names it from the launch's start.
        state = dict(self.run)
        state.setdefault("launcher_process", self.pointer.get("launcher_process"))
        return lifecycle.liveness(state) == "stopped"


def reading(launch: Launch, now: datetime) -> dict[str, object]:
    """The facts the wait's status line and the "with builder" decision both show, from one read of the records.

    Running time is counted to the run's completion where it completed; quiet is since the log's latest
    assistant or user record, when the builder last began or finished a step or wrote a reply, never the log's
    last write, which heartbeats keep fresh.
    """
    end = _moment(launch.run.get("completed_at")) or now
    started = launch.started
    log = launch.log
    last = log.steps[-1] if log and log.steps else None
    since = (log.activity if log and log.activity else None) or started
    running_step = None
    if (last is not None and last.identity is not None and last.identity not in log.finished and last.at is not None
            and not launch.completed):
        running_step = max(0, int((end - last.at).total_seconds()))
    readable = None if log is None else log.readable
    return {
        "started_at": started.isoformat() if started else None,
        "running_seconds": max(0, int((end - started).total_seconds())) if started else None,
        "limit_seconds": launch.limit,
        "quiet_seconds": max(0, int((end - since).total_seconds())) if since else None,
        # A launch with no log yet has taken no step; only a log in another form has steps that can't be read.
        "steps": 0 if log is None else len(log.steps) if readable is not False else None,
        "last_step": last.text() if last is not None else None,
        "last_step_running_seconds": running_step,
    }


def read_once(pointer: dict, now: datetime | None = None) -> dict[str, object]:
    """``reading`` of a live launch from one read of its records, or ``reading_error`` saying what couldn't be read."""
    launch = Launch(pointer)
    try:
        launch.read_request()
        launch.read_run()
        if launch.log is not None:
            launch.log.read()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"reading_error": f"{exc}"}
    return reading(launch, now or datetime.now(timezone.utc))


def _span(seconds) -> str:
    minutes = int(seconds) // 60
    return f"{minutes // 60}h{minutes % 60:02d}m" if minutes >= 60 else f"{minutes}m"


def status_line(work: str, values: dict) -> str:
    running = "running " + (_span(values["running_seconds"]) if values["running_seconds"] is not None else "for an "
                            "unread time")
    limit = f" of {_span(values['limit_seconds'])}" if values["limit_seconds"] else " of an unread limit"
    quiet = f"quiet {_span(values['quiet_seconds'])}" if values["quiet_seconds"] is not None else "quiet unread"
    steps = ("steps unreadable" if values["steps"] is None else
             f"{values['steps']} step" + ("" if values["steps"] == 1 else "s"))
    line = f"builder for {work}: {running}{limit}, {quiet}, {steps}"
    if values["last_step"]:
        line += f"; last: {values['last_step']}"
        if values["last_step_running_seconds"] is not None:
            line += f" (running {_span(values['last_step_running_seconds'])})"
    return line


class Waiter:
    """The wait's loop over one launch: steps as they come, a status line every ``STATUS_SECONDS``, and one end line."""

    def __init__(self, work: str, launch: Launch, *, out, clock, sleep):
        self.work, self.launch, self.out, self.clock, self.sleep = work, launch, out, clock, sleep
        self.failing: dict[str, list] = {}
        self.form_said = False
        self.earlier_steps_shown = False

    def say(self, text: str) -> None:
        self.out.write(f"{self.clock().astimezone().strftime('%H:%M:%S')} {text}\n")
        self.out.flush()

    def _try(self, name: str, path, action) -> bool:
        """Run one read; a failure is said once it has lasted ``UNREADABLE_SECONDS``, and again only after a success."""
        try:
            action()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            since = self.failing.setdefault(name, [self.clock(), False])
            if not since[1] and (self.clock() - since[0]).total_seconds() >= UNREADABLE_SECONDS:
                since[1] = True
                self.say(f"can't read the {name} {path}: {exc}; still trying")
            return False
        self.failing.pop(name, None)
        return True

    def _steps(self, log: Log | None = None) -> None:
        log = log or self.launch.log
        if log is None:
            return
        before = len(log.steps)
        if not self._try("builder log", log.path, log.read):
            return
        if log.readable is False and not self.form_said:
            self.form_said = True
            self.say("the builder's log isn't in Claude's stream form, so its steps can't be read; status lines only")
        if not self.earlier_steps_shown:
            # A log the wait couldn't read at its start opens as a start would, rather than replaying every step.
            self.earlier_steps_shown = True
            for step in log.steps[-EARLIER_STEPS:]:
                self.say(f"earlier step: {step.text()}")
            return
        for step in log.steps[before:]:
            self.say(f"{'helper step' if step.helper else 'step'}: {step.text()}")

    def _status(self) -> None:
        self.say(status_line(self.work, reading(self.launch, self.clock())))

    def _ended(self, text: str) -> int:
        self._steps()
        self.say(f"{text}; {status_line(self.work, reading(self.launch, self.clock()))}")
        return 0

    def run(self) -> int:
        launch = self.launch
        self._try("request record", launch.pointer.get("request"), launch.read_request)
        self._try("run record", launch.pointer.get("run"), launch.read_run)
        log = launch.log
        self.earlier_steps_shown = log is not None and self._try("builder log", log.path, log.read)
        if self.earlier_steps_shown and log.readable is False:
            self.form_said = True
            self.say("the builder's log isn't in Claude's stream form, so its steps can't be read; "
                     "status lines only")
        self._status()
        for step in (log.steps[-EARLIER_STEPS:] if self.earlier_steps_shown else []):
            self.say(f"earlier step: {step.text()}")
        next_status = self.clock() + timedelta(seconds=STATUS_SECONDS)
        while True:
            if launch.request is None:
                self._try("request record", launch.pointer.get("request"), launch.read_request)
            had_log = launch.log
            self._try("run record", launch.pointer.get("run"), launch.read_run)
            if launch.log is not had_log and had_log is not None:
                # A step can land in the old log after the last poll and before the switch, so its unread tail
                # is shown first, and its activity stands until the new log shows any.
                self._steps(had_log)
                launch.log.activity = max(filter(None, (launch.log.activity, had_log.activity)), default=None)
                self.say("the builder started a new attempt; its steps follow from the new log")
            if launch.completed:
                return self._ended(self._outcome())
            if launch.stopped():
                # The launcher may have completed the record as it exited; read it once more before saying it didn't.
                self._try("run record", launch.pointer.get("run"), launch.read_run)
                if launch.completed:
                    return self._ended(self._outcome())
                return self._ended("the builder's launch ended without completing its record")
            now = self.clock()
            bound = launch.bound
            if bound is not None and now >= bound:
                return self._ended(f"the builder's limit has passed: {_span(launch.limit)} and the "
                                   f"{lifecycle.cleanup_reserve(launch.limit):g}-second reserve since it started; "
                                   "the wait ends without stopping it")
            self._steps()
            if self.clock() >= next_status:
                self._status()
                next_status = self.clock() + timedelta(seconds=STATUS_SECONDS)
            pause = POLL_SECONDS
            if bound is not None:
                # A sleep past the bound would keep the wait running after the builder's limit and reserve.
                pause = min(pause, max(0.0, (bound - self.clock()).total_seconds()))
            self.sleep(pause)

    def _outcome(self) -> str:
        run = self.launch.run
        cause = f", {run['interruption_cause']}" if run.get("interruption_cause") else ""
        return (f"the builder's run ended: {run.get('lifecycle') or 'completed'}, "
                f"{run.get('outcome') or 'no outcome recorded'}{cause}")


def _launched(store: Path, work: str, instalment: str | None) -> tuple[list[dict], list[dict]]:
    """This work's live launched builders and live hand-started records, scoped by instalment when one is named."""
    found = [pointer for pointer in launch_tree.live_launches(store)
             if str(pointer.get("work", "")).lower() == work.lower()]
    if instalment is not None:
        found = [pointer for pointer in found if launch_instalment(pointer) == instalment]
    return ([pointer for pointer in found if pointer.get("hand") is not True],
            [pointer for pointer in found if pointer.get("hand") is True])


def _last_ended(store: Path, work: str) -> str | None:
    """How this work's latest builder launch ended; one that died leaves its record open, and is named as such."""
    bundles = lifecycle.launch_bundles(store, work, {"stretch"})
    if not bundles:
        return None
    _order, _path, request, run = bundles[-1]
    if not run.get("completed_at"):
        return f"its latest builder launch, {request.get('dispatch_id')}, ended without completing its record"
    cause = f", {run['interruption_cause']}" if run.get("interruption_cause") else ""
    return (f"its latest builder launch, {request.get('dispatch_id')}, ended at {run['completed_at']}: "
            f"{run.get('lifecycle') or 'completed'}, {run.get('outcome') or 'no outcome recorded'}{cause}")


def wait(store, repo: str, issue: int, *, instalment: str | None = None, out=None, clock=None, sleep=None) -> int:
    """Watch this work's launched builder until it ends or its limit passes; one line and exit 0 when none runs.

    Exits nonzero only when the record store can't be opened, or several launched builders of this work
    run and no instalment names one.
    """
    out = out or sys.stdout
    clock = clock or (lambda: datetime.now(timezone.utc))
    sleep = sleep or time.sleep
    work = f"{repo}#{issue}"
    store = Path(store)

    def say(text):
        out.write(f"{clock().astimezone().strftime('%H:%M:%S')} {text}\n")
        out.flush()

    directory = launch_tree.pointer_directory(store)
    try:
        if store.exists():
            if not store.is_dir():
                raise NotADirectoryError(f"{store} is not a directory")
            if directory.exists():
                os.listdir(directory)
    except OSError as exc:
        say(f"can't open the record store {store}: {exc}")
        return 1
    # A launcher rewrites its run record by replace, and a listing that meets one skips the launch as unreadable,
    # so the launches are read again before the wait says none runs.
    for attempt in range(LISTING_TRIES):
        launched, hand = _launched(store, work, instalment)
        if launched or hand or attempt == LISTING_TRIES - 1:
            break
        sleep(LISTING_PAUSE_SECONDS)
    if len(launched) > 1:
        say(f"{len(launched)} launched builders of {work} are running ("
            + ", ".join(pointer["dispatch_id"] for pointer in launched) + "); name one with --instalment")
        return 2
    if launched:
        return Waiter(work, Launch(launched[0]), out=out, clock=clock, sleep=sleep).run()
    if hand:
        say(f"the builder of {work} was started by hand and isn't watched: the owner started that session and "
            "sees it there")
        return 0
    ended = _last_ended(store, work)
    say(f"no launched builder of {work} is running" + (f"; {ended}" if ended else ""))
    return 0


def launch_instalment(pointer: dict) -> str | None:
    """The instalment a launch's request names, or its handoff block, so its wait command watches that launch."""
    try:
        request = json.loads(Path(pointer["request"]).read_bytes())
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(request, dict):
        return None
    handoff = request.get("handoff") if isinstance(request.get("handoff"), dict) else {}
    return request.get("instalment") or handoff.get("instalment")

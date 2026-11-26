"""The holder's wait on a launched builder, and the facts it shares with the "with builder" decision.

Each launch here is written by the launchers' own writers, and its launcher is a live child process, so the
wait's liveness reading is the real one; the wait's clock and sleep are a stand-in that moves time forward
and lets the stand-in builder write between polls.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
import uuid

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import builder_wait  # noqa: E402
from dispatch_lifecycle import atomic_record  # noqa: E402
import dispatch_record as records  # noqa: E402
import launch_tree  # noqa: E402
import run_lifecycle as lifecycle  # noqa: E402
import work  # noqa: E402

T0 = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
WORK = "o/r#5"
LIMIT = 28800.0
RESERVE = lifecycle.cleanup_reserve(LIMIT)
REPLAY = LIB / "tests" / "fixtures" / "builder-stream.jsonl"


def stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Clock:
    """The wait's clock and sleep: each sleep runs the builder's writes due before it ends, then moves time on."""

    def __init__(self, start: datetime):
        self.now, self.events, self.sleeps, self.latest = start, [], [], start

    def __call__(self) -> datetime:
        self.latest = max(self.latest, self.now)
        return self.now

    def at(self, seconds: float, action) -> None:
        self.events.append((T0 + timedelta(seconds=seconds), action))
        self.events.sort(key=lambda event: event[0])

    def sleep(self, seconds: float) -> None:
        assert seconds >= 0
        self.sleeps.append(seconds)
        target = self.now + timedelta(seconds=seconds)
        while self.events and self.events[0][0] <= target:
            moment, action = self.events.pop(0)
            self.now = max(self.now, moment)
            action()
        self.now = target
        assert self.now < T0 + timedelta(hours=2), "the wait ran on"


class Out:
    """The wait's output, each line kept with the moment it was printed."""

    def __init__(self, clock: Clock):
        self.clock, self.lines = clock, []

    def write(self, text: str) -> None:
        for line in text.splitlines():
            self.lines.append((self.clock.now, line.split(" ", 1)[1]))

    def flush(self) -> None:
        pass

    def texts(self, prefix: str = "") -> list[str]:
        return [text for _at, text in self.lines if text.startswith(prefix)]


@pytest.fixture()
def launcher():
    """A live child standing in for the stretch launcher; killed after the test."""
    children = []

    def start():
        child = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(600)"],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        children.append(child)
        return child
    yield start
    for child in children:
        if child.poll() is None:
            child.kill()
        child.wait()


class Builder:
    """One launched stretch: its request, run record and pointer written by the launchers' own writers, and a log."""

    def __init__(self, clock: Clock, child, *, launched: datetime, limit: float = LIMIT,
                 form: str | None = builder_wait.CLAUDE_FORM, instalment=None, run_record: bool = True,
                 handed_limit: float | None = None):
        self.clock, self.child, self.launched = clock, child, launched
        self.store = records.default_record_root()
        self.dispatch_id = uuid.uuid4().hex
        output = self.store / f"handoff-{self.dispatch_id}" / "result.md"
        output.parent.mkdir(parents=True)
        request = records.request_record(
            dispatch_id=self.dispatch_id, work=WORK, stage="stretch", settings_source="fixture",
            settings_scope="implementer", vendor="claude", model="fixture", effort="fixture", continuity="fresh",
            permission_boundary="fixture", root=None, now=launched)
        request.update(handoff={"timeout_seconds": handed_limit or limit}, caller_limit_seconds=limit,
                       instalment=instalment)
        self.request = records.sidecar(output, ".request.json")
        records.write_json(self.request, request)
        self.run = records.sidecar(output, ".run.json")
        self.log = records.sidecar(output, ".claude.stdout.log")
        self.log.write_bytes(b"")
        self.record = {"schema_version": 2, "dispatch_id": self.dispatch_id, "launched_at": launched.isoformat(),
                       "launcher_process": lifecycle.process_identity(child.pid), "lifecycle": "running",
                       "elapsed_checkpoint_seconds": 0,
                       "attempts": [{"vendor": "claude", "stdout": str(self.log),
                                     **({"source_format": form} if form else {})}]}
        if run_record:
            self.checkpoint()
        self.pointer = launch_tree.write_pointer(
            self.store, dispatch_id=self.dispatch_id, work=WORK, request=self.request, run=self.run,
            session_id=None, launcher=lifecycle.process_identity(child.pid), root=Path("implementation"))
        self.calls = 0

    def checkpoint(self) -> None:
        self.record["elapsed_checkpoint_seconds"] = (self.clock.now - self.launched).total_seconds()
        atomic_record(self.run, self.record)

    def append(self, record: dict) -> None:
        with self.log.open("ab") as stream:
            stream.write((json.dumps(record) + "\n").encode("utf-8"))

    def step(self, tool: str, tool_input: dict, *, helper: str | None = None, result: bool = True) -> str:
        self.calls += 1
        identity = f"toolu_{self.calls:03d}"
        self.append({"type": "assistant", "parent_tool_use_id": helper, "timestamp": stamp(self.clock.now),
                     "message": {"content": [{"type": "tool_use", "id": identity, "name": tool, "input": tool_input}]}})
        if result:
            self.result(identity, helper=helper)
        return identity

    def result(self, identity: str, *, helper: str | None = None) -> None:
        self.append({"type": "user", "parent_tool_use_id": helper, "timestamp": stamp(self.clock.now),
                     "message": {"content": [{"type": "tool_result", "tool_use_id": identity, "content": "ok"}]}})

    def heartbeat(self) -> None:
        self.append({"type": "tool_progress", "tool_use_id": "beat", "heartbeat": True})

    def complete(self, outcome: str, cause: str | None = None) -> None:
        self.record.update(lifecycle="completed", outcome=outcome, completed_at=self.clock.now.isoformat())
        if cause:
            self.record["interruption_cause"] = cause
        self.checkpoint()

    def crash(self) -> None:
        self.child.kill()
        self.child.wait()


def watch(clock: Clock, **kwargs) -> tuple[int, Out]:
    out = Out(clock)
    code = builder_wait.wait(records.default_record_root(), "o/r", 5, out=out, clock=clock, sleep=clock.sleep, **kwargs)
    return code, out


def minutes(text: str, word: str) -> int:
    """The span a status line gives after WORD, in minutes."""
    found = re.search(rf"{word} (?:(\d+)h)?(\d+)m", text)
    return int(found.group(1) or 0) * 60 + int(found.group(2))


# --- The wait ends with the builder ---------------------------------------------------------------------------

@pytest.mark.parametrize("way", ["ready", "stopped", "limit", "crash"])
def test_the_wait_ends_no_earlier_than_its_builder_and_within_a_minute_after(launcher, way):
    clock = Clock(T0)
    launched = T0 - timedelta(seconds=LIMIT - 40) if way == "limit" else T0 - timedelta(hours=2)
    builder = Builder(clock, launcher(), launched=launched)
    clock.at(0, lambda: builder.step("Bash", {"command": "make", "description": "Build the job"}))
    end = {"ready": 43, "stopped": 43, "limit": 41, "crash": 43}[way]
    clock.at(end, {"ready": lambda: builder.complete("success"), "stopped": lambda: builder.complete("failed"),
                   # The launcher stops its builder at the limit and completes the record within its reserve.
                   "limit": lambda: builder.complete("interrupted", "ceiling"), "crash": builder.crash}[way])
    code, out = watch(clock)
    assert code == 0
    ended = T0 + timedelta(seconds=end)
    assert ended <= clock.now <= ended + timedelta(minutes=1)
    last = out.texts()[-1]
    assert last.startswith({"ready": "the builder's run ended: completed, success",
                            "stopped": "the builder's run ended: completed, failed",
                            "limit": "the builder's run ended: completed, interrupted, ceiling",
                            "crash": "the builder's launch ended without completing its record"}[way])
    if way == "crash":
        assert "completed_at" not in json.loads(builder.run.read_bytes())


def test_a_builder_past_its_limit_ends_the_wait_at_the_limit_and_the_reserve_never_after(launcher):
    clock = Clock(T0)
    # The bound falls between two polls, so only a last poll scheduled at it ends there exactly.
    builder = Builder(clock, launcher(), launched=T0 - timedelta(seconds=LIMIT + RESERVE - 33))
    bound = builder.launched + timedelta(seconds=LIMIT + RESERVE)
    for second in range(0, 120, 3):
        clock.at(second, builder.heartbeat)
    code, out = watch(clock)
    assert code == 0 and clock.now == bound and clock.latest == bound
    assert out.texts()[-1].startswith(f"the builder's limit has passed: 8h00m and the {RESERVE:g}-second reserve")
    assert builder.child.poll() is None  # Ending stops nothing.


def test_a_run_record_that_names_no_source_format_still_reads_its_steps(launcher):
    """Where the attempt names no source format, the log's first record decides that it is Claude's stream form."""
    clock = Clock(T0)
    builder = Builder(clock, launcher(), launched=T0 - timedelta(hours=1), form=None)
    builder.step("Read", {"file_path": "lib/a.py"})
    clock.at(10, lambda: builder.step("Bash", {"command": "ls", "description": "List the tree"}))
    clock.at(20, lambda: builder.complete("success"))
    code, out = watch(clock)
    assert code == 0 and out.texts("earlier step:") == ["earlier step: Read: lib/a.py"]
    assert out.texts("step:") == ["step: Bash: List the tree"]


# --- The wait writes nothing and stopping it stops nothing ----------------------------------------------------

def tree_bytes(*roots: Path) -> dict[str, bytes]:
    return {str(path): path.read_bytes() for root in roots if root.exists()
            for path in sorted(root.rglob("*")) if path.is_file()}


def test_a_wait_run_to_its_end_writes_nothing_but_the_builder_writes(launcher, tmp_path):
    clock = Clock(T0)
    holder = tmp_path / "holder"
    holder.mkdir()
    (holder / "kept.txt").write_bytes(b"holder checkout\n")
    registry = work.registry_path()
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_bytes(b'{"schema_version": 1, "worktrees": []}\n')
    builder = Builder(clock, launcher(), launched=T0 - timedelta(hours=1))
    before = tree_bytes(Path.home(), holder)
    clock.at(5, lambda: builder.step("Bash", {"command": "ls"}))
    clock.at(12, lambda: builder.complete("success"))
    assert watch(clock)[0] == 0
    after = tree_bytes(Path.home(), holder)
    changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    assert changed <= {str(builder.run), str(builder.log)}


def test_killing_the_wait_leaves_the_builder_running_and_its_records_as_they_were(launcher):
    clock = Clock(datetime.now(timezone.utc))
    builder = Builder(clock, launcher(), launched=datetime.now(timezone.utc) - timedelta(hours=1))
    builder.step("Bash", {"command": "ls", "description": "List the tree"})
    before = tree_bytes(records.default_record_root())
    command = builder_wait.wait_command("o/r", 5, Path.home(), LIB.parent)
    wait = subprocess.Popen([sys.executable, *shlex.split(command)[1:]], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=dict(os.environ))
    try:
        first = wait.stdout.readline().decode("utf-8")
        assert f"builder for {WORK}: running 1h00m of 8h00m" in first
    finally:
        wait.kill()
        wait.wait()
    time.sleep(0.5)
    assert builder.child.poll() is None
    assert tree_bytes(records.default_record_root()) == before


# --- The lines say how the builder is doing -------------------------------------------------------------------

def replay_steps() -> list[tuple[str, str, bool]]:
    found = []
    for line in REPLAY.read_bytes().splitlines():
        record = json.loads(line)
        if record.get("type") == "assistant":
            found += [(block["name"], block["input"], record.get("parent_tool_use_id") is not None)
                      for block in record["message"]["content"] if block.get("type") == "tool_use"]
    return found


def test_a_replayed_log_prints_each_step_once_in_order_within_a_minute_with_status_lines(launcher):
    clock = Clock(T0)
    builder = Builder(clock, launcher(), launched=T0 - timedelta(hours=3))
    appended = []

    def append(raw: bytes) -> None:
        record = json.loads(raw)
        if "timestamp" in record:
            record["timestamp"] = stamp(clock.now)
        if record.get("type") == "assistant" and any(block.get("type") == "tool_use"
                                                      for block in record["message"]["content"]):
            appended.append(clock.now)
        builder.append(record)
        builder.checkpoint()
    replayed = REPLAY.read_bytes().splitlines()
    for index, raw in enumerate(replayed):
        # Slow enough that the replay outlasts a status interval and prints a second status line.
        clock.at(7 * index + 1, lambda raw=raw: append(raw))
    clock.at(7 * len(replayed) + 5, lambda: builder.complete("success"))
    code, out = watch(clock)
    assert code == 0
    printed = [(at, text) for at, text in out.lines if text.startswith(("step:", "helper step:"))]
    expected = [("helper step: " if helper else "step: ") + f"{tool}: {builder_wait._what(tool_input)}"
                for tool, tool_input, helper in replay_steps()]
    assert [text for _at, text in printed] == expected
    assert all(timedelta(0) <= at - when <= timedelta(minutes=1) for (at, _text), when in zip(printed, appended))
    # The step's own account where it gave one, else its main argument; a helper's step is marked as one.
    assert "step: Bash: Orient in the tree" in expected and "step: Read: lib/job.py" in expected
    assert "helper step: Grep: def run_job" in expected and "step: Skill: tradecraft:persist-changes" in expected
    assert "step: Bash: git push origin HEAD" in expected
    status = [(at, text) for at, text in out.lines if text.startswith("builder for ")]
    assert status[0][0] == T0 and len(status) >= 2
    run = json.loads(builder.run.read_bytes())
    for at, text in status:
        running = minutes(text, "running")
        assert running == int((at - builder.launched).total_seconds()) // 60
    assert abs(run["elapsed_checkpoint_seconds"] // 60 - minutes(out.texts()[-1], "running")) <= 1


def test_a_quiet_span_shows_as_quiet_though_heartbeats_keep_coming(launcher):
    clock = Clock(T0)
    builder = Builder(clock, launcher(), launched=T0 - timedelta(hours=1))
    running = {}
    clock.at(2, lambda: running.setdefault("id", builder.step("Bash", {"command": "make", "description": "Build"},
                                                               result=False)))
    for second in range(4, 7 * 60, 10):
        clock.at(second, lambda: (builder.heartbeat(), builder.checkpoint()))
    clock.at(7 * 60, lambda: builder.result(running["id"]))
    clock.at(7 * 60 + 4, lambda: builder.complete("success"))
    code, out = watch(clock)
    [(at, line)] = [(at, text) for at, text in out.lines[1:] if text.startswith("builder for ")]
    assert at == T0 + timedelta(seconds=300)
    assert minutes(line, "quiet") == (300 - 2) // 60 and minutes(line, r"\(running") == (300 - 2) // 60
    assert line.endswith("last: Bash: Build (running 4m)")


def test_one_failed_read_says_nothing_and_a_minute_of_them_says_which_file(launcher, monkeypatch):
    clock = Clock(T0)
    builder = Builder(clock, launcher(), launched=T0 - timedelta(hours=1))
    failing = {"once": True, "until": None}
    read = Path.read_bytes

    def flaky(path):
        if path == builder.run:
            if failing["once"] and clock.now >= T0 + timedelta(seconds=10):
                failing["once"] = False
                raise PermissionError(13, "Permission denied", str(path))
            if failing["until"] and clock.now < failing["until"]:
                raise PermissionError(13, "Permission denied", str(path))
        return read(path)
    monkeypatch.setattr(Path, "read_bytes", flaky)
    clock.at(100, lambda: failing.update(until=T0 + timedelta(seconds=200)))
    clock.at(150, lambda: builder.step("Bash", {"command": "ls", "description": "Still working"}))
    clock.at(230, lambda: builder.complete("success"))
    code, out = watch(clock)
    said = out.texts("can't read")
    assert code == 0 and len(said) == 1
    assert said[0].startswith(f"can't read the run record {builder.run}: ") and "Permission denied" in said[0]
    [(at, _text)] = [line for line in out.lines if line[1].startswith("can't read")]
    assert T0 + timedelta(seconds=160) <= at <= T0 + timedelta(seconds=170)
    # The log stayed readable, so the builder's step still showed while the record couldn't be read.
    assert out.texts("step:") == ["step: Bash: Still working"]


def test_a_log_in_another_form_gets_status_lines_and_one_line_saying_so(launcher):
    clock = Clock(T0)
    builder = Builder(clock, launcher(), launched=T0 - timedelta(hours=1), form="codex-jsonl")
    builder.append({"type": "thread.started"})
    clock.at(400, lambda: builder.complete("success"))
    code, out = watch(clock)
    assert code == 0
    assert out.texts("the builder's log isn't") == [
        "the builder's log isn't in Claude's stream form, so its steps can't be read; status lines only"]
    assert len(out.texts("builder for ")) == 2 and "steps unreadable" in out.texts("builder for ")[0]


def test_no_builder_a_hand_started_one_and_an_unopenable_store(launcher, tmp_path):
    clock = Clock(T0)
    code, out = watch(clock)
    assert code == 0 and out.texts() == [f"no launched builder of {WORK} is running"]
    launch_tree.write_hand_record(records.default_record_root(), work=WORK, vendor="codex", model="m",
                                  handoff={"tree": str(tmp_path)})
    code, out = watch(clock)
    assert code == 0 and out.texts()[0].startswith(f"the builder of {WORK} was started by hand and isn't watched")
    blocked = tmp_path / "not-a-store"
    blocked.write_bytes(b"")
    out = Out(clock)
    assert builder_wait.wait(blocked, "o/r", 5, out=out, clock=clock, sleep=clock.sleep) == 1
    assert out.texts()[0].startswith(f"can't open the record store {blocked}")


def test_an_instalment_names_which_of_two_builders_to_watch(launcher):
    clock = Clock(T0)
    first = Builder(clock, launcher(), launched=T0 - timedelta(hours=1), instalment="a")
    Builder(clock, launcher(), launched=T0 - timedelta(hours=2), instalment="b")
    code, out = watch(clock)
    assert code == 2 and "name one with --instalment" in out.texts()[0]
    clock.at(5, lambda: first.complete("success"))
    code, out = watch(clock, instalment="a")
    assert code == 0 and "running 1h00m" in out.texts()[0]


# --- The "with builder" reading carries the same facts ------------------------------------------------------

def test_the_with_builder_reading_agrees_with_the_records_and_the_wait(launcher, tmp_path):
    from test_route import MECHANICAL, fixture
    now = datetime.now(timezone.utc)
    clock = Clock(now - timedelta(minutes=3))
    builder = Builder(clock, launcher(), launched=now - timedelta(hours=2, minutes=5))
    builder.step("Read", {"file_path": "lib/a.py"})
    clock.now = now - timedelta(minutes=2)
    builder.step("Bash", {"command": "make\nmore", "description": "Build the job"}, result=False)
    clock.now = now
    builder.checkpoint()
    state = fixture(tmp_path, MECHANICAL)
    state.record_root, state.holder_root = records.default_record_root(), tmp_path / "holder"
    decided = work._builder_route_decision(state)
    detail = json.loads(decided.detail)
    run = json.loads(builder.run.read_bytes())
    request = json.loads(builder.request.read_bytes())
    assert (decided.stage, decided.reason) == ("with-builder", "builder-live")
    assert detail["started_at"] == run["launched_at"]
    assert detail["limit_seconds"] == request["handoff"]["timeout_seconds"]
    assert abs(detail["running_seconds"] - (datetime.now(timezone.utc) - builder.launched).total_seconds()) < 60
    assert abs(detail["running_seconds"] - run["elapsed_checkpoint_seconds"]) < 60
    assert abs(detail["quiet_seconds"] - 120) < 60
    assert detail["steps"] == 2 and detail["last_step"] == "Bash: Build the job"
    assert abs(detail["last_step_running_seconds"] - 120) < 60
    assert detail["wait"] == builder_wait.wait_command("o/r", 5, tmp_path / "holder", LIB.parent)
    line = builder_wait.status_line(WORK, builder_wait.read_once(json.loads(builder.pointer.read_bytes())))
    assert line.startswith(f"builder for {WORK}: running 2h05m of 8h00m, quiet 2m, 2 steps; last: Bash: Build the job")
    assert minutes(line, "running") == detail["running_seconds"] // 60
    assert minutes(line, "quiet") == detail["quiet_seconds"] // 60


def test_a_hand_started_builder_is_not_measured(tmp_path):
    from test_route import MECHANICAL, fixture
    state = fixture(tmp_path, MECHANICAL)
    state.record_root, state.holder_root = records.default_record_root(), tmp_path
    launch_tree.write_hand_record(state.record_root, work=WORK, vendor="codex", model="m",
                                  handoff={"tree": str(tmp_path)})
    detail = json.loads(work._builder_route_decision(state).detail)
    assert detail["measured"] is False and detail["reason"] == builder_wait.HAND_NOT_MEASURED
    assert not {"running_seconds", "quiet_seconds", "steps", "limit_seconds", "wait"} & detail.keys()


# --- The wait opens no connection, runs no GitHub command and starts no model session ----------------------

def test_the_wait_tries_no_connection_no_program_and_no_lookup_of_gh_or_claude(launcher, monkeypatch, tmp_path):
    clock = Clock(T0)
    builder = Builder(clock, launcher(), launched=T0 - timedelta(hours=1))
    clock.at(5, lambda: builder.step("Bash", {"command": "gh pr view", "description": "Read the pull request"}))
    clock.at(9, lambda: builder.complete("success"))
    tried = []

    def spy(name):
        def refused(*args, **kwargs):
            tried.append((name, args[:2]))
            raise OSError(f"test: {name} refused")
        return refused
    monkeypatch.setattr(socket.socket, "connect", spy("socket.connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", spy("socket.connect_ex"))
    monkeypatch.setattr(socket, "create_connection", spy("socket.create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", spy("socket.getaddrinfo"))
    monkeypatch.setattr(subprocess.Popen, "__init__", spy("subprocess.Popen"))
    for name in ("system", "startfile", "posix_spawn", "posix_spawnp", "spawnv", "spawnve", "spawnl", "spawnle",
                 "spawnlp", "spawnvp", "execv", "execve", "execl", "execle", "execlp", "execvp", "execvpe", "popen"):
        if hasattr(os, name):
            monkeypatch.setattr(os, name, spy(f"os.{name}"))
    which = shutil.which

    def looked_up(command, *args, **kwargs):
        if Path(str(command)).stem.lower() in ("gh", "claude", "codex"):
            tried.append(("shutil.which", (command,)))
        return which(command, *args, **kwargs)
    monkeypatch.setattr(shutil, "which", looked_up)
    args = work.parser().parse_args(shlex.split(builder_wait.wait_command("o/r", 5, tmp_path, LIB.parent))[3:])
    monkeypatch.setattr(builder_wait.time, "sleep", clock.sleep)
    monkeypatch.setattr(builder_wait, "datetime", type("Clocked", (datetime,), {"now": staticmethod(
        lambda tz=None: clock())}))
    assert work.run(args) == 0
    # Where the platform has no /proc, the builder check and the liveness lookup read a process with `ps`;
    # nothing else runs.
    assert [attempt for attempt in tried if not (attempt[0] == "subprocess.Popen" and not Path("/proc").is_dir()
                                                 and "ps" in str(attempt[1]))] == []


def test_a_resume_is_read_against_its_own_limit_not_the_first_launchs(launcher):
    """A send-back resume carries the first launch's longer block and runs under its own shorter limit."""
    clock = Clock(T0)
    builder = Builder(clock, launcher(), launched=T0 - timedelta(minutes=50), limit=3600.0, handed_limit=LIMIT)
    code, out = watch(clock)
    assert code == 0 and "running 50m of 1h00m" in out.texts()[0]
    assert clock.now == builder.launched + timedelta(seconds=3600 + lifecycle.cleanup_reserve(3600))
    assert out.texts()[-1].startswith("the builder's limit has passed: 1h00m")


def test_a_new_attempt_is_quiet_since_the_builder_last_did_anything_not_since_the_launch(launcher):
    clock = Clock(T0)
    builder = Builder(clock, launcher(), launched=T0 - timedelta(hours=3))
    builder.step("Bash", {"command": "make", "description": "Build"})
    retry = builder.log.with_name("retry.stdout.log")

    def new_attempt():
        retry.write_bytes(b"")
        builder.record["attempts"].append({"vendor": "claude", "stdout": str(retry),
                                           "source_format": builder_wait.CLAUDE_FORM})
        builder.checkpoint()
    # A step lands in the old log after the wait last read it, and before the switch.
    clock.at(58, lambda: builder.step("Bash", {"command": "make test", "description": "Test before the retry"}))
    clock.at(60, new_attempt)
    fresh = {}
    clock.at(300, lambda: fresh.update(builder_wait.read_once(json.loads(builder.pointer.read_bytes()), clock.now)))
    clock.at(400, lambda: builder.complete("success"))
    code, out = watch(clock)
    assert code == 0 and out.texts("the builder started a new attempt")
    assert out.texts("step: ") == ["step: Bash: Test before the retry"]
    [later] = [text for at, text in out.lines[1:] if text.startswith("builder for ")]
    assert minutes(later, "quiet") == 4 and "0 steps" in later
    # A fresh read, as the decision makes, takes the activity from the attempt before too.
    assert fresh["quiet_seconds"] // 60 == 4 and fresh["steps"] == 0


def test_two_live_builders_each_get_a_wait_command_for_their_own_instalment(launcher, tmp_path):
    from test_route import MECHANICAL, fixture
    clock = Clock(datetime.now(timezone.utc))
    Builder(clock, launcher(), launched=clock.now - timedelta(hours=1), instalment="a")
    Builder(clock, launcher(), launched=clock.now - timedelta(hours=2), instalment="b")
    state = fixture(tmp_path, MECHANICAL)
    state.record_root, state.holder_root = records.default_record_root(), tmp_path / "holder"
    detail = json.loads(work._builder_route_decision(state).detail)
    assert sorted(entry["wait"].rsplit(" ", 2)[1:] for entry in detail["builders"]) == [
        ["--instalment", "a"], ["--instalment", "b"]]


def test_a_step_with_no_id_is_not_read_as_running_and_no_log_yet_is_no_step(launcher):
    clock = Clock(T0)
    builder = Builder(clock, launcher(), launched=T0 - timedelta(hours=1))
    builder.append({"type": "assistant", "timestamp": stamp(T0), "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"description": "No id"}}]}})
    values = builder_wait.read_once(json.loads(builder.pointer.read_bytes()), T0 + timedelta(minutes=3))
    assert values["last_step"] == "Bash: No id" and values["last_step_running_seconds"] is None
    builder.record["attempts"] = []
    builder.checkpoint()
    values = builder_wait.read_once(json.loads(builder.pointer.read_bytes()), T0)
    assert values["steps"] == 0 and "0 steps" in builder_wait.status_line(WORK, values)


def test_a_listing_that_meets_the_launchers_replace_reads_again_before_saying_none_runs(launcher, monkeypatch):
    clock = Clock(T0)
    builder = Builder(clock, launcher(), launched=T0 - timedelta(hours=1))
    clock.at(5, lambda: builder.complete("success"))
    read, blocked = Path.read_bytes, {"once": True}

    def replaced(path):
        if path == builder.run and blocked.pop("once", False):
            raise PermissionError(13, "Permission denied", str(path))
        return read(path)
    monkeypatch.setattr(Path, "read_bytes", replaced)
    code, out = watch(clock)
    assert code == 0 and out.texts()[0].startswith(f"builder for {WORK}: running 1h00m")


def test_a_log_unread_at_the_start_opens_with_its_last_steps_rather_than_replaying_them(launcher, monkeypatch):
    clock = Clock(T0)
    builder = Builder(clock, launcher(), launched=T0 - timedelta(hours=1))
    for number in range(10):
        builder.step("Bash", {"command": "ls", "description": f"Step {number}"})
    clock.at(10, lambda: builder.step("Bash", {"command": "ls", "description": "A new step"}))
    clock.at(17, lambda: builder.complete("success"))
    read, blocked = Path.open, {"once": True}

    def replaced(path, *args, **kwargs):
        if path == builder.log and blocked.pop("once", False):
            raise PermissionError(13, "Permission denied", str(path))
        return read(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", replaced)
    code, out = watch(clock)
    assert code == 0
    assert out.texts("earlier step:") == [f"earlier step: Bash: {text}" for text in ("Step 7", "Step 8", "Step 9")]
    assert out.texts("step:") == ["step: Bash: A new step"]

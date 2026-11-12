"""Keep-warm for a waiting local Claude builder or author (#983, rows 1 to 3)."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import keep_warm  # noqa: E402
import dispatch_implementer as implementer
from test_dispatch_implementer import LIB, job, native_artifact_result  # noqa: F401

SESSION = "5f0c2c1e-8a3b-4d6e-9f10-2b3c4d5e6f70"
WORK = "owner/repo#5"
T0 = datetime(2026, 11, 11, 6, 0, tzinfo=timezone.utc).timestamp()


def iso(moment):
    return datetime.fromtimestamp(moment, timezone.utc).isoformat()


class Clock:
    def __init__(self, start=T0):
        self.now = start
        self.hooks = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        for hook in list(self.hooks):
            hook(self)


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".tradecraft").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return home


def transcript(home, session=SESSION, at=T0):
    path = home / ".claude" / "projects" / "D--tree" / f"{session}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps({"type": "assistant", "timestamp": iso(at),
                                  "message": {"id": "m1"}}) + "\n").encode())
    return path


def stream(*calls, compact=False, tool=False, result=True, is_error=False):
    events = []
    if compact:
        events.append({"type": "system", "subtype": "compact_boundary"})
    for index, (read, wrote) in enumerate(calls):
        content = [{"type": "tool_use", "id": "t", "name": "Bash", "input": {}}] if tool else [
            {"type": "text", "text": "ok"}]
        events.append({"type": "assistant", "message": {"id": f"msg{index}", "content": content, "usage": {
            "input_tokens": 3, "output_tokens": 2, "cache_read_input_tokens": read,
            "cache_creation_input_tokens": wrote,
            "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": wrote}}}})
    if result:
        events.append({"type": "result", "subtype": "success", "is_error": is_error, "result": "ok",
                       "session_id": SESSION})
    return "\n".join(json.dumps(event) for event in events).encode() + b"\n"


COMMAND = [sys.executable, "claude", "-p", "--model", "claude-opus-5-5", "--effort", "high",
           "--output-format", "stream-json", "--verbose", "--permission-mode", "auto",
           "--setting-sources", "user", "--plugin-dir", str(LIB.parent), "--strict-mcp-config",
           "--no-chrome", "--add-dir", "ROOT",
           "--disallowedTools=Monitor,ScheduleWakeup,CronCreate,Workflow",
           "--settings", "PREPARED", "--resume", SESSION]


def turn(home, tmp_path, **overrides):
    root = tmp_path / "tree"
    root.mkdir(exist_ok=True)
    transcript(home, overrides.get("session", SESSION), overrides.pop("transcript_at", T0))
    stdout = tmp_path / "turn.stdout.log"
    stdout.write_bytes(stream((60000, 100)) + json.dumps(
        {"type": "result", "modelUsage": {"claude-opus-5-5": {"contextWindow": 1000000}}}).encode() + b"\n")
    command = [value.replace("ROOT", str(root)) for value in COMMAND]
    value = {
        "vendor": "claude", "cloud": False, "launched": True, "session": SESSION,
        "observed_session": SESSION, "outcome": "success", "cleanup_proven": True,
        "launch_unresolved": None, "session_identity_error": None, "stage": "build",
        "work": WORK, "root": str(root), "fallback_root": None, "plugin_root": str(LIB.parent),
        "command": command,
        "settings_bytes": json.dumps({"enabledPlugins": {"other@market": False},
                                      "hooks": {"PreToolUse": []}}).encode(),
        "env_start": {"PATH": "p", "ANTHROPIC_API_KEY": "fake-key"},
        "env_child": {"PATH": "p", "ANTHROPIC_API_KEY": "fake-key",
                      "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "0"},
        "shim": None, "lineage_pull_request": None, "dispatch_id": "d1", "completed_at": iso(T0),
        "stdout_path": str(stdout), "projects": str(home / ".claude" / "projects"),
        "model": "claude-opus-5-5", "starter": None, "start_token": None,
    }
    value.update(overrides)
    return value


def rows(home, kind=None):
    path = home / ".tradecraft" / "changes" / "owner" / "repo" / "5" / "keep-warm.jsonl"
    found = [json.loads(line) for line in path.read_bytes().splitlines()] if path.exists() else []
    return [row for row in found if kind is None or row["kind"] == kind]


def runner(directory, clock, *, outcomes=None, state="open", pings=None):
    pings = [] if pings is None else pings

    def ping(spec, _directory):
        pings.append(clock())
        outcome = (outcomes or ["read"])[min(len(pings) - 1, len(outcomes or ["read"]) - 1)]
        return outcome, "" if outcome == "read" else "forced", {"calls": [], "total": {}}
    reader = state if callable(state) else (lambda _spec: state)
    return keep_warm.Runner(directory, clock=clock, sleep=clock.sleep, ping=ping, state_reader=reader,
                            identity=lambda: {"pid": os.getpid(), "host": "fixture", "birth": "1"}), pings


# --- Pins against the entrance --------------------------------------------------

def test_groups_and_outcomes_mirror_the_entrance():
    import work
    assert {stage: frozenset(s for s, g in keep_warm.STAGE_GROUPS.items()
                             if g == keep_warm.STAGE_GROUPS[stage]) for stage in keep_warm.STAGE_GROUPS} \
        == work.RESUME_SOURCE_STAGES
    assert keep_warm.RESUMABLE_OUTCOMES == work.RESUMABLE_BUNDLE_OUTCOMES | {"interrupted", "error"}


# --- Row 1 -------------------------------------------------------------------------

def test_ac2_ac5_ping_argv_differs_only_where_permitted(home, tmp_path):
    fresh = [*COMMAND[:-2], "--session-id", SESSION]
    for command in (COMMAND, fresh):
        argv = keep_warm.ping_argv(command, tmp_path / "ping-settings.json")
        assert argv[argv.index("--resume") + 1] == SESSION
        assert "--session-id" not in argv and "--fork-session" not in argv
        assert argv[-1] == "--no-session-persistence"
        differences = [(a, b) for a, b in zip(command, argv) if a != b]
        allowed = {("PREPARED", str(tmp_path / "ping-settings.json")), ("--session-id", "--resume")}
        assert set(differences) <= allowed and len(argv) == len(command) + 1
        for flag in ("--model", "--effort", "--permission-mode"):
            assert argv[argv.index(flag) + 1] == command[command.index(flag) + 1]
        assert [v for v in argv if v.startswith("--disallowedTools")] == [
            "--disallowedTools=Monitor,ScheduleWakeup,CronCreate,Workflow"]
        assert not any(v.startswith(("--allowedTools", "--tools")) for v in argv)


def test_ac5_ping_settings_keep_plugins_and_add_only_the_deny_hook(home, tmp_path):
    directory = keep_warm.after_turn(turn(home, tmp_path))
    spec = json.loads((directory / "spec.json").read_bytes())
    settings = keep_warm.ping_settings(spec)
    assert settings["enabledPlugins"] == {"other@market": False}
    assert set(settings) == {"enabledPlugins", "hooks"}
    hook = settings["hooks"]["PreToolUse"]
    assert len(hook) == 1 and hook[0]["matcher"] == "*"
    assert hook[0]["hooks"][0]["command"].endswith('keep_warm.py" deny')
    assert " -B " in hook[0]["hooks"][0]["command"]


def test_ac5_a_disposed_author_moves_only_its_root_directory(home, tmp_path):
    holder = tmp_path / "holder"
    holder.mkdir()
    directory = keep_warm.after_turn(turn(home, tmp_path, stage="artifact", fallback_root=str(holder)))
    spec = json.loads((directory / "spec.json").read_bytes())
    root = spec["root"]
    with keep_warm.ping_plan(spec, directory) as (cwd, argv):
        assert cwd == Path(root) and argv == spec["ping_argv"]
    Path(root).rmdir()
    with keep_warm.ping_plan(spec, directory) as (cwd, argv):
        assert cwd == holder
        assert [(a, b) for a, b in zip(spec["ping_argv"], argv) if a != b] == [(root, str(holder))]


@pytest.mark.parametrize("tool", ["Write", "Bash", "mcp__server__tool"])
def test_ac3_the_deny_hook_refuses_every_tool(tool):
    payload = json.dumps({"tool_name": tool, "tool_input": {}}).encode()
    result = subprocess.run([sys.executable, "-B", str(LIB / "keep_warm.py"), "deny"], input=payload,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    assert result.returncode == 0
    decision = json.loads(result.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert decision["hookEventName"] == "PreToolUse"


def test_ac4_setting_off_or_invalid_starts_nothing(home, tmp_path):
    setting = home / ".tradecraft" / "keep-warm.json"
    setting.write_bytes(b'{"cap_hours": 0}')
    assert keep_warm.after_turn(turn(home, tmp_path)) is None
    assert not (home / ".tradecraft" / "keep-warm" / SESSION).exists()
    assert rows(home) == []
    for bad in (b'{"cap_hours": 25}', b'{"cap_hours": "8"}', b"not json"):
        setting.write_bytes(bad)
        assert keep_warm.after_turn(turn(home, tmp_path)) is None
        assert not (home / ".tradecraft" / "keep-warm" / SESSION).exists()
    assert [row["stage"] for row in rows(home, "fault")] == ["setting"] * 3
    setting.write_bytes(b'{"cap_hours": 2}')
    assert keep_warm.after_turn(turn(home, tmp_path)) is not None


@pytest.mark.parametrize("change", [
    {"vendor": "codex"}, {"cloud": True}, {"stage": "cold-seat"}, {"stage": "use-consumer"},
    {"cleanup_proven": False}, {"launch_unresolved": True}, {"observed_session": "other"},
    {"session_identity_error": "differs"}, {"outcome": "unavailable"}, {"launched": False},
    {"work": "issue-592"},
])
def test_ac6_only_a_resumable_local_claude_turn_starts(home, tmp_path, change):
    assert keep_warm.after_turn(turn(home, tmp_path, **change)) is None
    assert not (home / ".tradecraft" / "keep-warm").exists()


RULE = implementer.LAUNCH_HELPER_RULE


@pytest.mark.parametrize("text", [RULE + "\n\n@../../tree/AGENTS.md\n", RULE + "\n"])
def test_ac8_the_launchs_instruction_file_is_recreated_whole_and_removed(home, tmp_path, text):
    git_dir = tmp_path / "gitdir"
    original = git_dir / "tradecraft-instructions-d1"
    git_dir.mkdir()
    directory = keep_warm.after_turn(turn(home, tmp_path, shim={"directory": str(original), "text": text}))
    spec = json.loads((directory / "spec.json").read_bytes())
    spec["ping_argv"] = [*spec["ping_argv"][:-1], "--add-dir", str(original), "--no-session-persistence"]
    with keep_warm.ping_plan(spec, directory) as (_cwd, argv):
        assert (original / "CLAUDE.md").read_bytes() == text.encode()
        assert str(original) in argv
    assert not original.exists()
    git_dir.rmdir()
    with keep_warm.ping_plan(spec, directory) as (_cwd, argv):
        placed = directory / original.name
        assert str(placed) in argv and str(original) not in argv
        moved = (placed / "CLAUDE.md").read_bytes().decode()
        assert moved.startswith(RULE + "\n")
        expected = "@" + (Path(spec["root"]) / "AGENTS.md").as_posix() + "\n" if "@" in text else ""
        assert moved == RULE + "\n" + ("\n" + expected if expected else "")
    assert not placed.exists()


def test_ac8_the_launcher_records_its_instruction_file_whole(tmp_path):
    shim = tmp_path / "tradecraft-instructions-d1"
    shim.mkdir()
    text = RULE + "\n\n@../AGENTS.md\n"
    (shim / "CLAUDE.md").write_bytes(text.encode())
    assert implementer._shim_record(shim) == {"directory": str(shim), "text": text}


def test_ac42_the_ping_runs_under_the_turns_login_and_writes_no_credential(home, tmp_path, monkeypatch):
    start = {"PATH": "p", "ANTHROPIC_API_KEY": "sk-fake-123", "CLAUDE_CODE_OAUTH_TOKEN": "oauth-fake-456",
             "CLAUDE_CONFIG_DIR": str(home / ".claude"), "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64000",
             "GIT_DIR": "x", "CLAUDE_CODE_PLUGIN_DIR": "y"}
    child = {key: value for key, value in start.items() if key not in {"GIT_DIR", "CLAUDE_CODE_PLUGIN_DIR"}}
    child.update({"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "0", "BASH_MAX_TIMEOUT_MS": "1000",
                  "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1", "GIT_LFS_SKIP_SMUDGE": "1"})
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    directory = keep_warm.after_turn(turn(home, tmp_path, env_start=start, env_child=child))
    spec = json.loads((directory / "spec.json").read_bytes())
    seen = {}
    monkeypatch.setattr(keep_warm, "spawn", lambda argv, cwd, env: seen.update(argv=argv, env=env) or 1)
    assert keep_warm.start_runner(directory, start)
    assert seen["env"] == {**start, "PYTHONDONTWRITEBYTECODE": "1"}
    assert keep_warm.ping_environment(spec, seen["env"]) == {**child, "PYTHONDONTWRITEBYTECODE": "1"}
    for path in (home / ".tradecraft").rglob("*"):
        if path.is_file():
            assert b"sk-fake-123" not in path.read_bytes() and b"oauth-fake-456" not in path.read_bytes()
    assert "sk-fake-123" not in " ".join(seen["argv"])
    other = {**child, "UNEXPECTED": "1"}
    assert keep_warm.after_turn(turn(home, tmp_path, env_start=start, env_child=other)) is None
    assert "UNEXPECTED" in rows(home, "fault")[-1]["reason"]


def test_ac44_nothing_started_on_windows_opens_a_window(home, tmp_path, monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(kwargs.get("creationflags"))
        return subprocess.CompletedProcess(argv, 0, b"1234\n", b"")
    monkeypatch.setattr(keep_warm.subprocess, "run", fake_run)
    monkeypatch.setattr(keep_warm, "WINDOWS", True)
    keep_warm._windows_spawn(["x"], tmp_path, {})
    monkeypatch.setattr(keep_warm, "shutil", type("S", (), {"which": staticmethod(lambda _n: "gh")}))
    keep_warm._gh({"gh": "gh"}, "repos/owner/repo/issues/5")
    assert calls == [keep_warm.CREATE_NO_WINDOW] * 2
    popen = []

    class Fake:
        returncode = 0
        pid = 1

        def __init__(self, argv, **kwargs):
            popen.append(kwargs)

        def communicate(self, *_a, **_k):
            return stream((60000, 10)), b""
    monkeypatch.setattr(keep_warm.subprocess, "Popen", Fake)
    directory = keep_warm.after_turn(turn(home, tmp_path))
    spec = json.loads((directory / "spec.json").read_bytes())
    assert keep_warm.run_ping(spec, directory)[0] == "read"
    assert popen[0]["creationflags"] == keep_warm.CREATE_NO_WINDOW


def test_ac44_the_windows_runner_is_windowless_python(monkeypatch, tmp_path):
    fake = tmp_path / "python.exe"
    (tmp_path / "pythonw.exe").write_bytes(b"")
    monkeypatch.setattr(keep_warm, "WINDOWS", True)
    monkeypatch.setattr(keep_warm.sys, "executable", str(fake))
    assert keep_warm.runner_python() == str(tmp_path / "pythonw.exe")
    assert keep_warm.runner_command(tmp_path)[1] == "-B"


# --- Row 2 ---------------------------------------------------------------------------

@pytest.mark.parametrize("cap,expected", [(8, 8), (2, 2)])
def test_ac10_pings_on_time_and_never_after_the_cap(home, tmp_path, cap, expected):
    (home / ".tradecraft" / "keep-warm.json").write_bytes(json.dumps({"cap_hours": cap}).encode())
    directory = keep_warm.after_turn(turn(home, tmp_path))
    clock = Clock()
    run, pings = runner(directory, clock)
    assert run.run() == "cap"
    assert [round((at - T0) / 60) for at in pings] == [55 * n for n in range(1, expected + 1)]
    assert rows(home, "end")[-1]["pings"] == expected


@pytest.mark.parametrize("status", ["closed", "merged", "released"])
def test_ac11_a_finished_change_gets_no_further_ping(home, tmp_path, status):
    directory = keep_warm.after_turn(turn(home, tmp_path))
    run, pings = runner(directory, Clock(), state=status)
    assert run.run() == status and pings == []


def test_ac11_change_state_reads_issue_pull_and_registry(home, tmp_path, monkeypatch):
    spec = {"work": WORK, "repo": "owner/repo", "issue": 5, "lineage_pull_request": 7}
    answers = {}
    monkeypatch.setattr(keep_warm, "_gh", lambda _spec, endpoint: answers.get(endpoint.rsplit("/", 2)[-2]))
    answers.update(issues={"state": "closed"})
    assert keep_warm.change_state(spec) == "closed"
    answers.update(issues={"state": "open"}, pulls={"state": "closed", "merged_at": "2026-11-11T00:00:00Z"})
    assert keep_warm.change_state(spec) == "merged"
    answers.update(pulls={"state": "closed", "merged_at": None})
    assert keep_warm.change_state(spec) == "closed"
    answers.update(pulls={"state": "open"})
    assert keep_warm.change_state(spec) == "open"
    (home / ".tradecraft" / "implementation-worktrees.json").write_bytes(json.dumps({
        "schema_version": 1, "worktrees": [{"repository": "Owner/Repo", "issue": 5, "active": False}]}).encode())
    assert keep_warm.change_state(spec) == "released"


def test_ac11_release_stops_a_sleeping_runner_without_a_ping(home, tmp_path):
    directory = keep_warm.after_turn(turn(home, tmp_path))
    clock = Clock()
    clock.hooks.append(lambda c: c.now > T0 + 600 and keep_warm.drop_work("Owner/Repo#5"))
    run, pings = runner(directory, clock)
    # The record names the release, not a launch.
    assert run.run() == "released" and pings == []
    assert rows(home, "end")[-1]["reason"] == "released"
    # A later turn's spec clears the release, so its own runner is not read as released.
    fresh = keep_warm.after_turn(turn(home, tmp_path))
    assert not (fresh / keep_warm.RELEASED).exists()


def test_ac12_a_real_turn_restarts_the_count(home, tmp_path):
    directory = keep_warm.after_turn(turn(home, tmp_path))
    clock = Clock()
    run, pings = runner(directory, clock)
    restarted = []

    def relaunch(c):
        if len(pings) == 3 and not restarted:
            with keep_warm.stop_for_launch(WORK, "floor", SESSION):
                pass
            restarted.append(keep_warm.after_turn(turn(home, tmp_path, completed_at=iso(c.now + 100),
                                                       transcript_at=c.now + 100)))
    clock.hooks.append(relaunch)
    assert run.run() in {"stopped-by-launch", "superseded"}
    assert len(pings) == 3
    fresh, more = runner(restarted[0], clock)
    assert fresh.run() == "cap" and len(more) == 8
    state = json.loads((directory / "state.json").read_bytes())
    assert state["pings"] == 8


@pytest.mark.parametrize("stage,work,dropped", [
    ("build", WORK, True), ("floor", WORK, True), ("review-disposition", WORK, True),
    ("artifact", WORK, False), ("build", "owner/repo#6", False)])
def test_ac13_a_replaced_session_is_dropped(home, tmp_path, stage, work, dropped):
    directory = keep_warm.after_turn(turn(home, tmp_path))
    clock = Clock()
    run, pings = runner(directory, clock)

    launched = []

    def launch(_clock):
        if not launched:
            launched.append(True)
            with keep_warm.stop_for_launch(work, stage, None):
                pass
    clock.hooks.append(launch)
    result = run.run()
    assert (directory / "spec.json").exists() is not dropped
    if dropped:
        assert (result, pings) == ("stopped-by-launch", [])
    else:
        assert result == "cap" and len(pings) == 8


# --- Row 3 ----------------------------------------------------------------------------

def test_ac14_a_clock_past_the_hour_sends_nothing(home, tmp_path):
    directory = keep_warm.after_turn(turn(home, tmp_path))
    clock = Clock()
    clock.hooks.append(lambda c: setattr(c, "now", max(c.now, T0 + 70 * 60)))
    run, pings = runner(directory, clock)
    assert run.run() == "lapsed" and pings == []


@pytest.mark.parametrize("outcome", ["wrote", "compacted", "failed"])
def test_ac15_a_ping_that_misses_is_the_last(home, tmp_path, outcome):
    directory = keep_warm.after_turn(turn(home, tmp_path))
    run, pings = runner(directory, Clock(), outcomes=[outcome])
    assert run.run() == outcome and len(pings) == 1
    assert [row["kind"] for row in rows(home)] == ["ping", "end"]
    assert rows(home, "ping")[0]["outcome"] == outcome and rows(home, "ping")[0]["reason"]


@pytest.mark.parametrize("raw,code,timed_out,expected", [
    (stream((0, 66038)), 0, False, "wrote"),
    (stream((0, 5000)), 0, False, "wrote"),
    (stream((60000, 9500)), 0, False, "read"),
    (stream((500000, 21000)), 0, False, "read"),
    (stream((100000, 21000)), 0, False, "wrote"),
    (stream((60000, 10), compact=True), 0, False, "compacted"),
    (stream((60000, 10)), 1, False, "failed"),
    (stream((60000, 10), is_error=True), 0, False, "failed"),
    (stream((60000, 10)), 0, True, "failed"),
    (stream((60000, 10), tool=True), 0, False, "failed"),
    (stream((60000, 10), result=False), 0, False, "failed"),
])
def test_ac15_ping_outcomes(raw, code, timed_out, expected):
    outcome, reason, usage = keep_warm.ping_outcome(code, raw, timed_out=timed_out)
    assert outcome == expected
    assert bool(reason) == (expected != "read")
    if expected != "failed" or code == 0 and not timed_out and b'"tool_use"' not in raw:
        assert usage["total"]["cache_read"] == usage["calls"][0]["cache_read"]


def test_ac16_pings_continue_through_the_wait_before_a_launch(home, tmp_path):
    directory = keep_warm.after_turn(turn(home, tmp_path))
    clock = Clock()
    run, pings = runner(directory, clock)
    # The stage is called at 50 minutes; its launcher starts 69 minutes later.
    clock.hooks.append(lambda c: c.now >= T0 + 119 * 60 and (directory / "spec.json").unlink(missing_ok=True))
    assert run.run() == "stopped-by-launch"
    assert [round((at - T0) / 60) for at in pings] == [55, 110]


def test_ac17_a_recorded_fault_changes_no_decision(home, tmp_path):
    import work
    keep_warm.fault(WORK, "spawn", "forced fault")
    assert rows(home, "fault")
    # The entrance reads no keep-warm record: nothing in its decision path names one.
    source = Path(work.__file__).read_text(encoding="utf-8")
    assert "keep-warm.jsonl" not in source
    assert [line.strip() for line in source.splitlines() if "keep_warm." in line] == [
        "keep_warm.drop_work(f\"{repo}#{issue}\", instalment)", "keep_warm.discard_pending(keep_warm_token)",
        "keep_warm.start_pending(keep_warm_token)"]


def test_ac18_a_launch_waits_for_a_ping_in_flight(home, tmp_path):
    directory = keep_warm.after_turn(turn(home, tmp_path))
    holder = subprocess.Popen([sys.executable, "-B", "-c", textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, {str(LIB)!r})
        import keep_warm
        from pathlib import Path
        with keep_warm.session_lock(Path({str(directory / 'ping.lock')!r})):
            print('held', flush=True)
            time.sleep(2)
        print(time.time(), flush=True)
    """)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert holder.stdout.readline().strip() == b"held"
    with keep_warm.stop_for_launch(WORK, "build", SESSION):
        started = time.time()
    ended = float(holder.stdout.readline())
    holder.wait(10)
    assert started >= ended
    assert not (directory / "spec.json").exists()


def test_ac18_a_held_lock_means_no_ping_while_a_turn_runs(home, tmp_path):
    directory = keep_warm.after_turn(turn(home, tmp_path))
    clock = Clock()
    run, pings = runner(directory, clock)
    with keep_warm.session_lock(directory / "ping.lock"):
        assert run.run() == "turn-running"
    assert pings == []


def test_ac19_nothing_keep_warm_writes_is_in_launch_coverage(home, tmp_path):
    import launch_bound
    from holder_tree_guard import contains
    directory = keep_warm.after_turn(turn(home, tmp_path))
    plan = launch_bound.coverage_plan(root=tmp_path / "tree", home=home, env={}, launcher_plugin=LIB.parent,
                                      store=home / ".tradecraft" / "dispatches",
                                      own_request=tmp_path / "own.request.json")
    written = [directory, directory / "ping-settings.json", directory / "ping.lock",
               keep_warm.record_path("owner", 5).parent / "keep-warm.jsonl", directory / "tradecraft-instructions-d1"]
    for item in plan:
        for path in written:
            assert not contains(Path(item["path"]), path), (item, path)
    assert keep_warm.runner_command(directory)[1] == "-B"
    assert any(item["item"] == "keep-warm-switch" for item in plan)


def test_ac20_no_ping_to_a_session_near_compaction(home, tmp_path):
    for tokens, window, expected in ((900000, 1000000, "too-large"), (890000, 1000000, "cap"),
                                     (900000, None, "too-large")):
        directory = keep_warm.after_turn(turn(home, tmp_path))
        spec = json.loads((directory / "spec.json").read_bytes())
        spec.update(context_tokens=tokens, context_window=window, cap_hours=1)
        (directory / "spec.json").write_bytes(json.dumps(spec).encode())
        run, pings = runner(directory, Clock())
        assert run.run() == expected
        assert len(pings) == (0 if expected == "too-large" else 1)


def test_ac21_an_outside_turn_stops_keep_warm(home, tmp_path):
    directory = keep_warm.after_turn(turn(home, tmp_path))
    with transcript(home).open("ab") as stream_:
        stream_.write(b'{"type":"user"}\n{"type":"user"}\n')
    run, pings = runner(directory, Clock())
    assert run.run() == "outside-use" and pings == []


def test_ac22_a_running_keep_warm_is_never_a_launch(home, tmp_path):
    import run_lifecycle as lifecycle
    store = home / ".tradecraft" / "dispatches"
    store.mkdir(parents=True)
    before = sorted(store.rglob("*"))
    directory = keep_warm.after_turn(turn(home, tmp_path))
    run, _pings = runner(directory, Clock())
    run.ping_once(json.loads((directory / "state.json").read_bytes()))
    assert sorted(store.rglob("*")) == before
    assert lifecycle.launch_bundles(store, WORK, {"build", "floor", "review-disposition"}) == []
    assert not list((home / ".tradecraft" / "keep-warm").rglob("*.request.json"))
    assert not list((home / ".tradecraft" / "keep-warm").rglob("*.run.json"))


def test_ac43_a_dead_runner_is_recorded_once(home, tmp_path):
    directory = keep_warm.after_turn(turn(home, tmp_path))
    dead = subprocess.Popen([sys.executable, "-c", "pass"], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    dead.wait(30)
    import run_lifecycle as lifecycle
    state = json.loads((directory / "state.json").read_bytes())
    state["process"] = {"pid": dead.pid, "host": __import__("socket").gethostname(), "birth": "0"}
    (directory / "state.json").write_bytes(json.dumps(state).encode())
    keep_warm.status()
    keep_warm.status()
    with keep_warm.stop_for_launch(WORK, "build", None):
        pass
    assert [row["reason"] for row in rows(home, "end")] == ["runner-gone"]
    live = keep_warm.after_turn(turn(home, tmp_path, session="6f0c2c1e-8a3b-4d6e-9f10-2b3c4d5e6f71",
                                     observed_session="6f0c2c1e-8a3b-4d6e-9f10-2b3c4d5e6f71"))
    state = json.loads((live / "state.json").read_bytes())
    state["process"] = lifecycle.process_identity()
    (live / "state.json").write_bytes(json.dumps(state).encode())
    keep_warm.status()
    assert len(rows(home, "end")) == 1


def test_holder_reading_an_unreadable_state_is_read_once_more(home, tmp_path):
    directory = keep_warm.after_turn(turn(home, tmp_path))
    answers = iter([None, "open"])
    run, pings = runner(directory, Clock(), state=lambda _spec: next(answers, "closed"))
    assert run.run() == "closed" and len(pings) == 1
    directory = keep_warm.after_turn(turn(home, tmp_path))
    run, pings = runner(directory, Clock(), state=lambda _spec: None)
    assert run.run() == "change-state-unreadable" and pings == []
    assert rows(home, "end")[-1]["reason"] == "change-state-unreadable"


def test_holder_reading_a_retry_that_would_lapse_ends_lapsed(home, tmp_path):
    directory = keep_warm.after_turn(turn(home, tmp_path))
    clock = Clock()
    clock.hooks.append(lambda c: c.now >= T0 + 3300 and setattr(c, "now", max(c.now, T0 + 3400)))
    run, pings = runner(directory, clock, state=lambda _spec: None)
    assert run.run() == "lapsed" and pings == []


# --- AC9: a runner outlives every launch's containment ---------------------------------

CHILD = textwrap.dedent("""
    import os, sys, time
    time.sleep(3)
    with open(sys.argv[1], "w") as stream:
        stream.write(os.environ.get("KW_PASSED", "") + "|" + os.environ.get("KW_UNPASSED", ""))
""")


@pytest.mark.skipif(os.name != "nt", reason="the WMI starter is Windows only")
def test_ac9_windows_runner_outlives_a_kill_on_close_job(tmp_path):
    child = tmp_path / "child.py"
    child.write_text(CHILD)
    marker = tmp_path / "marker.txt"
    parent = tmp_path / "parent.py"
    parent.write_text(textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {str(LIB)!r})
        import keep_warm
        env = {{k: v for k, v in os.environ.items() if k != "KW_UNPASSED"}}
        env["KW_PASSED"] = "yes"
        keep_warm.spawn([sys.executable, {str(child)!r}, {str(marker)!r}], {str(tmp_path)!r}, env)
    """))
    env = {**os.environ, "KW_UNPASSED": "leak"}
    result = subprocess.run([sys.executable, str(LIB / "seat_process.py"), str(tmp_path / "failure.json"),
                             sys.executable, str(parent)], env=env, timeout=120, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert result.returncode == 0
    for _ in range(60):
        if marker.exists() and marker.read_text():
            break
        time.sleep(0.5)
    assert marker.read_text() == "yes|"


@pytest.mark.skipif(not Path("/proc/self/task").is_dir(), reason="the subreaper is Linux only")
@pytest.mark.parametrize("inside", [False, True])
def test_ac9_linux_runner_survives_the_entrances_cleanup(tmp_path, home, inside):
    from posix_tree import Descendants
    from seat_process import run_inherited_process
    child = tmp_path / "child.py"
    child.write_text(CHILD)
    marker = tmp_path / "marker.txt"
    directory = home / ".tradecraft" / "keep-warm" / SESSION
    directory.mkdir(parents=True)
    (directory / "spec.json").write_text(json.dumps({"python": sys.executable}))
    (directory / "start.pending").write_text("token")
    launcher = tmp_path / "launcher.py"
    launcher.write_text(textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {str(LIB)!r})
        import keep_warm
        if {inside!r}:
            keep_warm.spawn([sys.executable, {str(child)!r}, {str(marker)!r}], {str(tmp_path)!r},
                            {{**os.environ, "KW_PASSED": "yes"}})
    """))
    Descendants()
    run_inherited_process([sys.executable, str(launcher)], cwd=tmp_path, timeout=60,
                          cleanup_deadline=time.monotonic() + 5)
    if not inside:
        keep_warm.start_pending("token", {**os.environ, "KW_PASSED": "yes"}, spawner=lambda _argv, cwd, env:
                                keep_warm.spawn([sys.executable, str(child), str(marker)], cwd, env))
    Descendants().finish(time.monotonic() + 1)
    # Poll with a bound; the arm that asserts absence waits the whole bound.
    end = time.monotonic() + 20
    while time.monotonic() < end and not marker.exists():
        time.sleep(0.25)
    assert marker.exists() is not inside


def test_ac9_posix_starter_shape(monkeypatch, tmp_path):
    seen = {}

    class Fake:
        def __init__(self, argv, **kwargs):
            seen.update(argv=argv, **kwargs)

        def wait(self, timeout):
            return 0
    monkeypatch.setattr(keep_warm.subprocess, "Popen", Fake)
    keep_warm._posix_spawn(["runner", "-B"], tmp_path, {"A": "1"})
    assert seen["start_new_session"] is True and seen["close_fds"] is True
    assert seen["stdin"] == seen["stdout"] == seen["stderr"] == subprocess.DEVNULL
    assert seen["argv"][1] == "-B" and seen["argv"][-2:] == ["runner", "-B"]
    assert "DEVNULL" in keep_warm.DETACH


# --- The launcher's own calls ---------------------------------------------------------------

@pytest.fixture
def claude(job, monkeypatch):
    args, scenario = job
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    args.vendor = "claude"
    args.work = WORK
    args.resume = SESSION
    monkeypatch.setattr(implementer, "resolve_command",
                        lambda *_: [sys.executable, str(LIB / "tests/seat_cli.py"), "claude", str(scenario)])
    scenario.write_bytes(json.dumps({"claude": native_artifact_result("claude", "built", SESSION)}).encode())
    home = Path.home()
    transcript(home)
    spawned = []
    monkeypatch.setattr(keep_warm, "spawn", lambda argv, cwd, env: spawned.append((argv, env)) or 1)
    return args, home, spawned


def test_launcher_writes_the_spec_and_starts_the_runner_last(claude):
    args, home, spawned = claude
    assert implementer.run_implementer(args) == 0
    spec = json.loads((home / ".tradecraft" / "keep-warm" / SESSION / "spec.json").read_bytes())
    request = json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())
    assert keep_warm.ping_argv(request["requested"]["command"], home / ".tradecraft" / "keep-warm" / SESSION
                               / "ping-settings.json") == spec["ping_argv"]
    assert spec["turn_dispatch_id"] == request["dispatch_id"]
    # Every launch's own instruction file is recorded whole, and the ping's argv names it.
    assert spec["shim"]["text"].startswith(RULE + "\n")
    assert spec["shim"]["directory"] in spec["ping_argv"]
    assert len(spawned) == 1 and spawned[0][0][-1] == str(home / ".tradecraft" / "keep-warm" / SESSION)
    assert set(spec["env_set"]) <= set(keep_warm.LAUNCH_ENV_NAMES)


def test_launcher_with_the_entrance_starter_leaves_a_pending_start(claude):
    args, home, spawned = claude
    args.keep_warm_starter, args.keep_warm_token = "entrance", "tok"
    assert implementer.run_implementer(args) == 0
    assert spawned == []
    assert (home / ".tradecraft" / "keep-warm" / SESSION / "start.pending").read_text() == "tok"
    keep_warm.start_pending("other")
    assert spawned == []
    keep_warm.start_pending("tok")
    assert len(spawned) == 1
    assert not (home / ".tradecraft" / "keep-warm" / SESSION / "start.pending").exists()


def test_ac4_launcher_with_the_setting_off_starts_nothing(claude):
    args, home, spawned = claude
    (home / ".tradecraft").mkdir(parents=True, exist_ok=True)
    (home / ".tradecraft" / "keep-warm.json").write_bytes(b'{"cap_hours": 0}')
    assert implementer.run_implementer(args) == 0
    assert spawned == [] and not (home / ".tradecraft" / "keep-warm" / SESSION).exists()


@pytest.mark.parametrize("broken", ["spawn", "lock", "after_turn"])
def test_ac23_a_keep_warm_fault_never_changes_a_launch(claude, monkeypatch, capsys, broken):
    args, home, spawned = claude
    directory = home / ".tradecraft" / "keep-warm" / SESSION
    directory.mkdir(parents=True)

    def boom(*_a, **_k):
        raise OSError("forced keep-warm fault")
    if broken == "spawn":
        monkeypatch.setattr(keep_warm, "spawn", boom)
    elif broken == "lock":
        monkeypatch.setattr(keep_warm, "session_lock", boom)
    else:
        monkeypatch.setattr(keep_warm, "_write_spec", boom)
    assert implementer.run_implementer(args) == 0
    run = json.loads(implementer.records.sidecar(args.output, ".run.json").read_bytes())
    assert run["outcome"] == "success"
    assert "keep-warm" not in capsys.readouterr().out
    assert rows(home, "fault")[-1]["reason"].endswith("forced keep-warm fault")


def test_ac23_start_pending_never_raises(home, monkeypatch):
    monkeypatch.setattr(keep_warm, "state_root", lambda: (_ for _ in ()).throw(OSError("boom")))
    keep_warm.start_pending("tok")


def test_ac41_an_accepted_author_is_kept_warm_after_its_copy_is_disposed(home, tmp_path):
    holder = tmp_path / "holder"
    holder.mkdir()
    directory = keep_warm.after_turn(turn(home, tmp_path, stage="artifact", fallback_root=str(holder)))
    spec = json.loads((directory / "spec.json").read_bytes())
    Path(spec["root"]).rmdir()  # artifact_tree.finish disposes the accepted copy.
    seen = []
    clock = Clock()

    def ping(spec_, directory_):
        with keep_warm.ping_plan(spec_, directory_) as (cwd, argv):
            seen.append((cwd, argv[argv.index("--add-dir") + 1]))
        return "read", "", {"calls": [], "total": {}}
    run = keep_warm.Runner(directory, clock=clock, sleep=clock.sleep, ping=ping,
                           state_reader=lambda _s: "open", identity=lambda: None)
    clock.hooks.append(lambda c: c.now > T0 + 4000 and keep_warm.stop_for_launch(WORK, "artifact", None)
                       .__enter__())
    assert run.run() == "stopped-by-launch"
    assert seen == [(holder, str(holder))]
    holder.rmdir()
    directory = keep_warm.after_turn(turn(home, tmp_path, stage="artifact", fallback_root=str(holder)))
    Path(json.loads((directory / "spec.json").read_bytes())["root"]).rmdir()
    plain, pings = runner(directory, Clock())
    assert plain.run() == "root-removed" and pings == []


def test_status_lists_waiting_sessions(home, tmp_path):
    keep_warm.after_turn(turn(home, tmp_path))
    listed = keep_warm.status(WORK)
    assert [entry["session"] for entry in listed] == [SESSION] and listed[0]["waiting"]
    assert keep_warm.status("owner/repo#6") == []


def test_discarded_pending_start_is_ended_and_never_read_as_gone(home, tmp_path):
    """A launch the entrance could not see finish leaves no pending start and starts no runner."""
    directory = keep_warm.after_turn(turn(home, tmp_path, starter="entrance", start_token="tok"))
    assert (directory / "start.pending").exists()
    started = []
    keep_warm.discard_pending("other")
    assert (directory / "start.pending").exists()
    keep_warm.discard_pending("tok")
    assert not (directory / "start.pending").exists() and not (directory / "spec.json").exists()
    keep_warm.start_pending("tok", spawner=lambda *a: started.append(a))
    assert started == []
    assert [row["reason"] for row in rows(home, "end")] == ["launch-unfinished"]
    keep_warm.status()
    assert [row["reason"] for row in rows(home, "end")] == ["launch-unfinished"]


def test_the_lock_wait_is_bounded_by_the_launchs_deadline(home, tmp_path):
    """A ping in flight is waited for only within what the launch's own deadline leaves."""
    directory = keep_warm.after_turn(turn(home, tmp_path))
    with keep_warm.session_lock(directory / "ping.lock"):
        started = time.monotonic()
        with keep_warm.stop_for_launch(WORK, "build", SESSION, wait_seconds=0.3):
            waited = time.monotonic() - started
    assert waited < 5
    assert "a ping still held the lock" in rows(home, "fault")[-1]["reason"]


def test_an_unreadable_prepared_settings_file_is_a_keep_warm_fault_not_a_failed_launch(claude, monkeypatch):
    """Row 3: the settings read only keep-warm needs can never fail the launch's preparation."""
    args, home, spawned = claude
    real = Path.read_bytes

    def refuse(self):
        if self.name == "claude-settings.json":
            raise PermissionError("forced: settings unreadable")
        return real(self)
    monkeypatch.setattr(Path, "read_bytes", refuse)
    assert implementer.run_implementer(args) == 0
    run = json.loads(real(implementer.records.sidecar(args.output, ".run.json")))
    assert run["outcome"] == "success"
    assert spawned == [] and not (home / ".tradecraft" / "keep-warm" / SESSION / "spec.json").exists()
    assert "forced: settings unreadable" in rows(home, "fault")[-1]["reason"]


def test_a_ping_that_reached_no_model_spent_a_known_nothing():
    """A ping that launched nothing records complete zero usage; one with an unreadable call is incomplete."""
    assert keep_warm.NOTHING_SPENT["complete"] is True and not any(keep_warm.NOTHING_SPENT["total"].values())
    good = keep_warm.ping_outcome(0, stream((60000, 10)))[2]
    assert good["complete"] is True
    broken = json.dumps({"type": "assistant", "message": {"id": "x", "usage": {
        "input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 5,
        "cache_creation_input_tokens": 3}}}).encode() + b"\n" + stream((60000, 10))
    assert keep_warm.ping_outcome(0, broken)[2]["complete"] is False


def test_instalments_scope_stop_release_and_registry(home, tmp_path):
    """A session's keep-warm is stopped, dropped and read as released by its own instalment."""
    a = keep_warm.after_turn(turn(home, tmp_path, instalment="a"))
    other = "6f0c2c1e-8a3b-4d6e-9f10-2b3c4d5e6f71"
    b = keep_warm.after_turn(turn(home, tmp_path, instalment="b", session=other, observed_session=other))
    with keep_warm.stop_for_launch(WORK, "build", None, instalment="b"):
        pass
    assert (a / "spec.json").exists() and not (b / "spec.json").exists()
    keep_warm.drop_work(WORK, "b")
    assert (a / "spec.json").exists()
    keep_warm.drop_work(WORK, "a")
    assert not (a / "spec.json").exists()
    (home / ".tradecraft" / "implementation-worktrees.json").write_text(json.dumps({
        "schema_version": 1, "worktrees": [
            {"repository": "owner/repo", "issue": 5, "instalment": "a", "active": False},
            {"repository": "owner/repo", "issue": 5, "instalment": "b", "active": True}]}))
    assert keep_warm.registry_released(WORK, "a") and not keep_warm.registry_released(WORK, "b")
    assert not keep_warm.registry_released(WORK)


def test_no_instalment_named_scopes_the_whole_change(home, tmp_path):
    a = keep_warm.after_turn(turn(home, tmp_path, instalment="a"))
    with keep_warm.stop_for_launch(WORK, "build", None):
        pass
    assert not (a / "spec.json").exists()


def test_the_first_ping_is_timed_from_when_the_last_call_was_sent(home, tmp_path):
    """A final call that streamed for minutes: the hour runs from its send, not its last output."""
    lines = [{"type": "user", "timestamp": iso(T0 - 600)},
             {"type": "assistant", "timestamp": iso(T0 - 590), "message": {"id": "m1"}},
             {"type": "assistant", "timestamp": iso(T0), "message": {"id": "m1"}}]
    facts = turn(home, tmp_path)
    path = transcript(home)
    path.write_bytes("".join(json.dumps(line) + "\n" for line in lines).encode())
    assert keep_warm.last_call_sent_at(path) == T0 - 600
    directory = keep_warm.after_turn(facts)
    state = json.loads((directory / "state.json").read_bytes())
    assert keep_warm._moment(state["last_call_at"]) == T0 - 600
    run, pings = runner(directory, Clock())
    assert run.run() == "cap"
    assert round((pings[0] - (T0 - 600)) / 60) == 55


def test_a_busy_session_does_not_stop_the_others_being_stopped(home, tmp_path):
    a = keep_warm.after_turn(turn(home, tmp_path))
    other = "6f0c2c1e-8a3b-4d6e-9f10-2b3c4d5e6f71"
    b = keep_warm.after_turn(turn(home, tmp_path, session=other, observed_session=other))
    real = keep_warm.mark_gone

    def busy(directory):
        if directory == a:
            raise keep_warm.LockBusy("held")
        return real(directory)
    keep_warm.mark_gone = busy
    try:
        with keep_warm.stop_for_launch(WORK, "build", None):
            pass
    finally:
        keep_warm.mark_gone = real
    assert not (a / "spec.json").exists() and not (b / "spec.json").exists()
    assert rows(home, "fault")[-1]["stage"] == "stop"


def test_ping_plan_moves_only_the_launchers_import_and_leaves_a_directory_it_did_not_make(home, tmp_path):
    git_dir = tmp_path / "gitdir"
    git_dir.mkdir()
    original = git_dir / "tradecraft-instructions-d1"
    text = "@an-earlier-line-that-is-not-the-import\n\n@../../tree/AGENTS.md\n"
    directory = keep_warm.after_turn(turn(home, tmp_path, shim={"directory": str(original), "text": text}))
    spec = json.loads((directory / "spec.json").read_bytes())
    spec["ping_argv"] = [*spec["ping_argv"][:-1], "--add-dir", str(original), "--no-session-persistence"]
    original.mkdir()
    (original / "CLAUDE.md").write_text("someone else's")
    with keep_warm.ping_plan(spec, directory):
        assert (original / "CLAUDE.md").read_text() == "someone else's"
    assert original.exists()
    shutil.rmtree(original)
    git_dir.rmdir()
    with keep_warm.ping_plan(spec, directory):
        moved = (directory / original.name / "CLAUDE.md").read_text().splitlines()
    assert moved[0] == "@an-earlier-line-that-is-not-the-import"
    assert moved[-1] == "@" + (Path(spec["root"]) / "AGENTS.md").as_posix()


@pytest.mark.parametrize("exit_", ["unavailable", "preparation", "existing-output", "no-window"])
def test_a_launch_that_starts_nothing_leaves_the_waiting_keep_warm(claude, tmp_path, monkeypatch, exit_):
    """The session stays the one the entrance resumes next, so its keep-warm stays."""
    args, home, spawned = claude
    other = "6f0c2c1e-8a3b-4d6e-9f10-2b3c4d5e6f71"
    waiting = keep_warm.after_turn(turn(home, tmp_path, session=other, observed_session=other))
    if exit_ == "unavailable":
        args.claude_unavailable_reason = "forced: no executable"
        monkeypatch.setattr(implementer, "resolve_command", lambda *_: pytest.fail("rediscovered"))
        assert implementer.run_implementer(args) == 1
    elif exit_ == "preparation":
        monkeypatch.setattr(implementer.policy, "claude_prepare",
                            lambda *_a, **_k: (_ for _ in ()).throw(OSError("forced preparation failure")))
        assert implementer.run_implementer(args) == 1
    elif exit_ == "existing-output":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("earlier")
        with pytest.raises(implementer.ImplementerError):
            implementer.run_implementer(args)
    else:
        args.timeout_seconds = 0.001
        with pytest.raises(TimeoutError):
            implementer.run_implementer(args)
    assert (waiting / "spec.json").exists()


def test_a_launch_that_starts_its_process_ends_the_waiting_keep_warm(claude, tmp_path):
    args, home, spawned = claude
    other = "6f0c2c1e-8a3b-4d6e-9f10-2b3c4d5e6f71"
    waiting = keep_warm.after_turn(turn(home, tmp_path, session=other, observed_session=other))
    assert implementer.run_implementer(args) == 0
    assert not (waiting / "spec.json").exists()


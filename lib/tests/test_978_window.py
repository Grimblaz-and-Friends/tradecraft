"""A run's window and the entrance's cap: lib/DESIGN.md#a-runs-window-and-the-entrances-cap"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import run_lifecycle as lifecycle
import work


def at(monkeypatch, value):
    clock = [float(value)]
    monkeypatch.setattr(lifecycle.time, "monotonic", lambda: clock[0])
    return clock


@pytest.mark.parametrize("allotted", [6, 600, 3600, 7200])
@pytest.mark.parametrize("spent", [0, 100, 899, 900])
def test_978_reserve_after_the_window(monkeypatch, allotted, spent):
    clock = at(monkeypatch, 1000)
    deadline = lifecycle.stage_deadline("build", allotted)
    reserve = min(60.0, max(10.0, allotted / 10))
    assert deadline.reserve == reserve
    assert deadline.latest_end == 1000 + 900 + allotted + reserve
    clock[0] = 1000 + spent
    deadline.open_window()
    # The recipient gets its whole limit; the reserve after it is today's.
    assert deadline.remaining() == allotted
    assert deadline.end - (1000 + spent + allotted) == reserve
    assert deadline.end - deadline.wait_end == reserve / 4
    assert deadline.end - deadline.cleanup_end == reserve / 2
    assert deadline.wait_end - deadline.final_write_at == reserve / 8
    assert deadline.end <= deadline.latest_end
    if spent == 900:
        assert deadline.end == deadline.latest_end


def test_978_before_the_window_reads_are_cut_at_the_cap(monkeypatch):
    clock = at(monkeypatch, 1000)
    deadline = lifecycle.stage_deadline("build", 7200)
    assert not deadline.in_window
    assert deadline.remaining() == 900
    assert deadline.probe(20) == 20
    clock[0] = 1000 + 895
    assert deadline.probe(20) == 5
    clock[0] = 1000 + 900
    with pytest.raises(lifecycle.PreflightCapExceeded, match="900-second cap"):
        deadline.remaining()
    # A refusal's own cleanup still has half the reserve after the cap.
    assert deadline.probe(60, cleanup=True) == pytest.approx(30)


def test_978_require_cap_withdraw_and_a_late_window(monkeypatch):
    clock = at(monkeypatch, 1000)
    deadline = lifecycle.stage_deadline("cold-seat", 600)
    deadline.require_cap(285)
    clock[0] = 1000 + 900 - 285
    with pytest.raises(lifecycle.PreflightCapExceeded):
        deadline.require_cap(285)
    deadline.open_window()
    assert deadline.in_window and deadline.remaining() == 600
    deadline.withdraw_window()
    assert not deadline.in_window and deadline.end == deadline.latest_end
    # A window opened after the cap's end keeps the printed latest return.
    clock[0] = 1000 + 950
    deadline.open_window()
    assert deadline.end == deadline.latest_end
    assert deadline.window_opened_late_seconds == 50


def test_978_write_timeout_before_the_window(monkeypatch):
    clock = at(monkeypatch, 1000)
    short = lifecycle.stage_deadline("build", 1)
    clock[0] = 1000 + 899
    # A write is not cut at the cap's end, only where it would outlast the printed return.
    assert short.write_timeout(300) == pytest.approx(2)
    clock[0] = 1000 + 900
    with pytest.raises(lifecycle.PreflightCapExceeded):
        short.write_timeout(300)
    default = lifecycle.stage_deadline("build", 7200)
    clock[0] = 1000 + 899
    assert default.write_timeout(300) == 300


def test_978_limit_phrases(monkeypatch):
    at(monkeypatch, 1000)
    deadline = lifecycle.stage_deadline("build", 7200, declared=True)
    assert lifecycle.limit_phrase(deadline) == (
        "the entrance's 900-second cap before the recipient starts (the default)")
    declared = lifecycle.stage_deadline("build", 7200, cap=1800, cap_reason="large repository")
    assert "1800-second cap" in lifecycle.limit_phrase(declared)
    assert "declared by --preflight-cap-seconds" in lifecycle.limit_phrase(declared)
    deadline.open_window()
    assert lifecycle.limit_phrase(deadline) == (
        "the 7200-second limit (declared by --timeout-seconds), counted from the recipient's start")
    proof = lifecycle.stage_deadline("proof", 3600, declared=False)
    proof.open_window()
    assert lifecycle.limit_phrase(proof).endswith("counted from the start of the stage's own work")
    floor = lifecycle.stage_deadline("floor", 10800)
    floor.open_window()
    assert lifecycle.limit_phrase(floor) == "the floor stage's 3600-second ceiling, counted from the launch"
    reason = lifecycle.cap_refusal(deadline)
    assert "the entrance's 900-second cap" in reason
    assert "--preflight-cap-seconds" in reason and "--preflight-cap-reason" in reason


@pytest.mark.parametrize("stage", ["floor", "review-disposition"])
def test_978_floor_ceiling(monkeypatch, stage):
    at(monkeypatch, 1000)
    deadline = lifecycle.stage_deadline(stage, 10800, started=1000 - 600, declared=True)
    line = lifecycle.window_line(deadline)
    assert line["stage_ceiling_seconds"] == 3600 and line["allotted_seconds"] == 3600
    for text in ("ceiling is 3600 seconds", "counted from the launch", "not the declared 10800"):
        assert text in line["ceiling_note"]
    assert line["latest_return_seconds"] == 900 + 3600 + 60
    # Ten minutes spent before the launch still leave the recipient its whole hour.
    deadline.open_window()
    assert deadline.allotted == 3600 and deadline.remaining() == 3600


@pytest.mark.parametrize("seconds, reason", [
    (1800, None), (None, "x"), (1800, "  "), (900, "x"), (float("inf"), "x")])
def test_978_a_declared_cap_needs_both_flags_a_reason_and_more_than_the_default(seconds, reason):
    with pytest.raises(ValueError):
        lifecycle.validate_cap_flags(seconds, reason)


def test_978_declared_cap_sets_the_return_time(monkeypatch):
    at(monkeypatch, 1000)
    deadline = lifecycle.stage_deadline("build", 7200, cap=1800, cap_reason="large repository")
    line = lifecycle.window_line(deadline)
    assert line["preflight_cap"] == {"seconds": 1800, "source": "declared", "reason": "large repository"}
    assert line["latest_return_seconds"] == 1800 + 7200 + 60


ENTRANCE_STAGES = ["artifact", "build", "cold-seat", "use", "floor", "review-disposition", "proof",
                   "ready-reviewers", "release-report", "catch-up", "cold-reader"]


@pytest.mark.parametrize("stage", ENTRANCE_STAGES)
def test_978_first_line_is_the_window(tmp_path, capsys, stage):
    # The root has no change-proof policy, so the stage refuses at once; the line must come first anyway.
    code = work.main(["run", stage, "--repo", "owner/repo", "--issue", "1", "--root", str(tmp_path)])
    assert code == 1
    first = capsys.readouterr().out.splitlines()[0]
    assert first.startswith("work: window ")
    line = json.loads(first.removeprefix("work: window "))
    assert line["stage"] == stage
    assert line["latest_return_seconds"] == (
        line["preflight_cap"]["seconds"] + line["allotted_seconds"] + line["reserve_seconds"])
    assert line["preflight_cap"] == {"seconds": 900, "source": "default", "reason": None}
    assert line["cap_record"] is None


@pytest.mark.parametrize("flags", [
    ["--preflight-cap-seconds", "1800"], ["--preflight-cap-reason", "x"],
    ["--preflight-cap-seconds", "1800", "--preflight-cap-reason", " "],
    ["--preflight-cap-seconds", "900", "--preflight-cap-reason", "x"]])
def test_978_an_invalid_cap_is_refused_before_any_read(tmp_path, capsys, flags):
    code = work.main(["run", "build", "--repo", "owner/repo", "--issue", "1", "--root", str(tmp_path), *flags])
    assert code == 1
    captured = capsys.readouterr()
    assert "work: window" not in captured.out
    assert "preflight-cap" in captured.err


def test_978_declared_cap_record(tmp_path, capsys, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(work, "_records_home", lambda _state: home)
    root = tmp_path / "root"
    root.mkdir()
    code = work.main(["run", "proof", "--repo", "owner/repo", "--issue", "7", "--root", str(root),
                      "--preflight-cap-seconds", "1800", "--preflight-cap-reason", "large repository"])
    assert code == 1
    line = json.loads(capsys.readouterr().out.splitlines()[0].removeprefix("work: window "))
    files = list((home / "preflight-caps" / "owner-repo-7").glob("*.json"))
    assert [str(path) for path in files] == [line["cap_record"]]
    record = json.loads(files[0].read_bytes())
    assert record["stage"] == "proof" and record["called_at"] == line["called_at"]
    assert record["preflight_cap"] == {"seconds": 1800, "source": "declared", "reason": "large repository"}
    # The run failed before its decision; the record says so and keeps the figure and the reason.
    assert record["outcome"] == "failed"
    rows = work.declared_caps("owner/repo#7", None)
    assert [(row["stage"], row["outcome"]) for row in rows] == [("proof", "failed")]


def test_978_cap_refusal_names_the_cap_and_records_it(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(work, "_records_home", lambda _state: home)

    def spent(args, **_kwargs):
        lifecycle.current_deadline().remaining()
        return 0
    monkeypatch.setattr(work, "_run", spent)
    assert work.run(work.parser().parse_args([
        "run", "build", "--repo", "owner/repo", "--issue", "7", "--root", str(tmp_path),
        "--preflight-cap-seconds", "1800", "--preflight-cap-reason", "large repository"])) == 0
    # In process the run's start is now; a spent cap is made by a run whose clock started long ago.
    with work.preflight.scope(started=time.monotonic() - 1801):
        with pytest.raises(lifecycle.PreflightCapExceeded, match="1800-second cap"):
            work.run(work.parser().parse_args([
                "run", "build", "--repo", "owner/repo", "--issue", "7", "--root", str(tmp_path),
                "--preflight-cap-seconds", "1800", "--preflight-cap-reason", "large repository"]))
    outcomes = sorted(json.loads(path.read_bytes())["outcome"]
                      for path in (home / "preflight-caps" / "owner-repo-7").glob("*.json"))
    assert outcomes == ["held", "refused-at-cap"]


def test_978_the_entrance_allots_the_whole_limit(monkeypatch):
    # Ten minutes spent before the launch take nothing from the builder's 7200 seconds.
    deadline = lifecycle.stage_deadline("build", 7200, started=time.monotonic() - 600)
    assert deadline.allotted == 7200
    account = {"remaining_seconds": 14400}
    assert lifecycle.allocation(account, deadline.allotted) == 7200
    assert lifecycle.allocation({"remaining_seconds": 1000}, deadline.allotted) == 1000


def seat(tmp_path, *extra):
    return subprocess.run(
        [sys.executable, str(LIB / "dispatch_seat.py"), "--dispatch", str(tmp_path / "missing.json"),
         "--root", str(tmp_path), "--vendor", "claude", "--own-vendor", "claude", "--work", "1",
         "--stage", "cold-seat", "--settings-source", "fixture", "--settings-scope", "seat",
         "--classification", "cold", "--requires", "read",
         "--hold-file", str(tmp_path / "holds.json"), "--output", str(tmp_path / "out" / "result.json"),
         *extra],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", timeout=120)


def test_978_a_launcher_past_its_cap_refuses_and_leaves_nothing(tmp_path):
    result = seat(tmp_path, "--invocation-started-monotonic", str(time.monotonic() - 901))
    assert result.returncode == 1, result.stderr
    refusal = next(line for line in result.stderr.splitlines() if line.startswith("seat: refusal "))
    body = json.loads(refusal.removeprefix("seat: refusal "))
    assert "the entrance's 900-second cap" in body["reason"]
    assert "--preflight-cap-seconds" in body["reason"] and "--preflight-cap-reason" in body["reason"]
    assert body["preflight"]["until"] == "handoff"
    assert not (tmp_path / "out").exists() or not any((tmp_path / "out").iterdir())


def test_978_a_launcher_called_directly_prints_its_window_first(tmp_path):
    result = seat(tmp_path, "--timeout-seconds", "1800")
    first = result.stdout.splitlines()[0]
    assert first.startswith("seat: window ")
    line = json.loads(first.removeprefix("seat: window "))
    assert line["allotted_seconds"] == 1800 and line["latest_return_seconds"] == 900 + 1800 + 60
    # Started by the entrance, the launcher prints none: the entrance's line is the stage's first.
    handoff = tmp_path / "handoff.json"
    handoff.write_text(json.dumps({"schema_version": 1, "started_monotonic": time.monotonic()}),
                       encoding="utf-8")
    result = seat(tmp_path, "--preflight-input", str(handoff))
    assert "seat: window" not in result.stdout


NOTICE_LAUNCHER = """
import json, os, sys, time
notice = sys.argv[sys.argv.index("--launch-notice") + 1]
def write(opened):
    with open(notice + ".tmp", "w", encoding="utf-8") as stream:
        json.dump({"schema_version": 1, "window_opened_monotonic": opened}, stream)
    os.replace(notice + ".tmp", notice)
for step in sys.argv[1].split(","):
    if step == "open":
        write(time.monotonic())
    elif step == "withdraw":
        write(None)
    else:
        time.sleep(float(step))
time.sleep(120)
"""


@pytest.mark.parametrize("steps, cap", [("open", 900), ("open,1,withdraw", 3), ("open,1,withdraw,2,open", 900)])
def test_978_entrance_wait_follows_the_window(tmp_path, monkeypatch, steps, cap):
    script = tmp_path / "launcher.py"
    script.write_text(NOTICE_LAUNCHER, encoding="utf-8")
    monkeypatch.setattr(lifecycle, "PREFLIGHT_CAP_SECONDS", cap)
    deadline = lifecycle.stage_deadline("build", 6)
    reserve = deadline.reserve
    called = time.monotonic()
    with pytest.raises(work.WorkError, match="bounded recording allowance"):
        work._invoke_recipient([sys.executable, str(script), steps], deadline)
    stopped = time.monotonic()
    if steps.endswith("open"):
        # Stopped by the last window's start, plus the limit and the reserve, less a quarter of it.
        expected = deadline.window_opened + 6 + reserve - reserve / 4
    else:
        expected = deadline.latest_end - reserve / 4
    assert expected - 1.5 <= stopped <= expected + 1.5, (stopped - called, expected - called)


def test_978_write_in_flight_at_the_cap(monkeypatch):
    calls = []

    def slow_write(command, **kwargs):
        calls.append((time.monotonic(), kwargs["timeout"]))
        time.sleep(min(4, kwargs["timeout"]))
        return subprocess.CompletedProcess(command, 0, b"", b"")
    monkeypatch.setattr(work, "run_read", slow_write)
    for limit, runs in ((1, 3), (7200, 4)):
        calls.clear()
        # Two seconds of the cap are left when the worktree is made.
        deadline = lifecycle.stage_deadline("build", limit, started=time.monotonic() - 898)
        with lifecycle.deadline_scope(deadline):
            with pytest.raises(lifecycle.PreflightCapExceeded):
                work._git(["worktree", "add", "fixture"], Path.cwd())
            ended = time.monotonic()
            # A queued second write is never begun after the cap.
            with pytest.raises(lifecycle.PreflightCapExceeded):
                work._git(["push", "origin", "HEAD"], Path.cwd())
        [(begun, bound)] = calls
        if limit == 1:
            # Cut where it would outlast the printed return less the reserve: the cap's end plus the limit.
            assert bound == pytest.approx(deadline.cap_end + 1 - begun, abs=0.2)
            assert ended <= deadline.cap_end + 1 + 0.5
            assert ended < deadline.latest_end
        else:
            # At a default limit the write runs its whole time, past the cap's end, then the run refuses.
            assert bound == 120
            assert ended - begun >= runs - 0.2


def test_978_slow_copy_refuses_at_the_cap(tmp_path, monkeypatch):
    import artifact_tree as trees
    calls = []

    def slow(command, **kwargs):
        calls.append(kwargs["timeout"])
        time.sleep(min(4, kwargs["timeout"]))
        return subprocess.CompletedProcess(command, 0, b"", b"")
    monkeypatch.setattr(trees, "run_read", slow)
    # Three seconds of the cap are left when the copy is made; its first step takes four.
    deadline = lifecycle.stage_deadline("artifact", 3600, started=time.monotonic() - 897)
    with lifecycle.deadline_scope(deadline):
        trees.git(tmp_path, "rev-parse", "HEAD")
        # The copy's next step meets the spent cap as the stage's refusal at the cap, not as a failed copy.
        with pytest.raises(lifecycle.PreflightCapExceeded, match="900-second cap"):
            trees.git(tmp_path, "checkout", "--detach", "HEAD", writes=True)
    assert len(calls) == 1 and calls[0] <= 3
    declared = lifecycle.stage_deadline("artifact", 3600, started=time.monotonic() - 897,
                                        cap=1800, cap_reason="large repository")
    with lifecycle.deadline_scope(declared):
        trees.git(tmp_path, "rev-parse", "HEAD")
        trees.git(tmp_path, "checkout", "--detach", "HEAD", writes=True)


def test_978_a_fractional_cap_reaches_the_launcher_unrounded(monkeypatch):
    import dispatch_implementer as implementer
    commands = []
    monkeypatch.setattr(work, "_recipient_run",
                        lambda command, **_k: commands.append(list(command)) or subprocess.CompletedProcess(command, 0))
    cap = 1800.123456789
    deadline = lifecycle.stage_deadline("build", 7200, cap=cap, cap_reason="large repository")
    assert work._invoke_recipient(["python", "dispatch_implementer.py"], deadline) == 0
    [command] = commands
    args = implementer.parser().parse_args([
        "--dispatch", "d", "--root", "r", "--work", "o/r#1", "--stage", "build", "--settings-source", "s",
        "--settings-scope", "s", *command[2:]])
    assert args.preflight_cap_seconds == cap
    launcher = lifecycle.stage_deadline("build", 7200, started=args.invocation_started_monotonic,
                                        cap=args.preflight_cap_seconds, cap_reason=args.preflight_cap_reason)
    printed = lifecycle.window_line(deadline)
    launcher.called_epoch = deadline.called_epoch  # The handoff carries the call's wall-clock time.
    assert lifecycle.window_line(launcher)["latest_return_at"] == printed["latest_return_at"]


def test_978_a_notice_change_that_keeps_its_time_is_still_followed(tmp_path, monkeypatch):
    clock = at(monkeypatch, 1000)
    deadline = lifecycle.stage_deadline("build", 6)
    notice = tmp_path / "launch-notice.json"
    follow = work._window_follower(notice, deadline)
    opened = lifecycle.stage_deadline("build", 6, started=1000)
    opened.open_window(1001)
    lifecycle.write_launch_notice(notice, opened)
    stamp = notice.stat().st_mtime_ns
    assert follow()[0] == 1001 + 6 + deadline.reserve - deadline.reserve / 4
    # The launcher withdraws and reopens within the filesystem's time resolution: the time is unchanged.
    clock[0] = 1003
    opened.withdraw_window()
    opened.open_window(1003)
    lifecycle.write_launch_notice(notice, opened)
    os.utime(notice, ns=(stamp, stamp))
    assert follow()[0] == 1003 + 6 + deadline.reserve - deadline.reserve / 4

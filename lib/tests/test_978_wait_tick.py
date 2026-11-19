"""A launch wait whose window moves while the child runs: lib/DESIGN.md#a-runs-window-and-the-entrances-cap"""
from pathlib import Path
import subprocess
import sys
import time

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import run_lifecycle
import seat_process as process

# The child records its own pid, then sleeps this long unless stopped.
HOLD_SECONDS = 30
SLEEPER = "import os, pathlib, sys, time; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(float(sys.argv[2]))"


def alive(pid):
    try:
        run_lifecycle.process_identity(pid)
    except ProcessLookupError:
        return False
    return True


def recorded_pid(path):
    for _ in range(200):
        if path.is_file() and path.read_text():
            return int(path.read_text())
        time.sleep(0.05)
    raise AssertionError("the child never recorded its pid")


def test_978_wait_tick_ends_at_the_moved_wait_end_and_stops_the_child(tmp_path):
    pid_file = tmp_path / "pid"
    start = time.monotonic()
    ticks = []

    def on_tick():
        ticks.append(time.monotonic())
        # Each early tick names a later end than the call's own; once moved, the end is start + 2.
        return (start + 1.0, start + 3.0) if len(ticks) <= 2 else (start + 2.0, start + 3.0)

    with pytest.raises(subprocess.TimeoutExpired):
        process.run_inherited_process([sys.executable, "-c", SLEEPER, str(pid_file), str(HOLD_SECONDS)],
                                      cwd=tmp_path, timeout=0.5, cleanup_deadline=start + 1.5,
                                      on_tick=on_tick)
    elapsed = time.monotonic() - start
    assert 2.0 <= elapsed <= 3.5
    assert len(ticks) >= 3
    pid = recorded_pid(pid_file)
    end = time.monotonic() + 5
    while alive(pid) and time.monotonic() < end:
        time.sleep(0.05)
    assert not alive(pid)


def test_978_wait_tick_extends_the_wait_past_the_calls_own_end(tmp_path):
    start = time.monotonic()
    result = process.run_inherited_process(
        [sys.executable, "-c", SLEEPER, str(tmp_path / "pid"), "1.5"], cwd=tmp_path, timeout=0.5,
        cleanup_deadline=start + 1.0, on_tick=lambda: (start + 10.0, start + 11.0))
    assert result.returncode == 0
    assert time.monotonic() - start < 10.0

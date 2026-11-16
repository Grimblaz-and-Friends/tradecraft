"""A run's clock starts at its process's creation: lib/DESIGN.md#a-runs-window-and-the-entrances-cap"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import preflight

# The interpreter's start-up is held this long before any of the launcher's code runs.
STARTUP_DELAY = 2


def refusal_split(stderr):
    for line in stderr.splitlines():
        if line.startswith("seat: refusal "):
            return json.loads(line.removeprefix("seat: refusal "))["preflight"]
    raise AssertionError(f"no refusal line in: {stderr!r}")


def test_978_clock_starts_at_the_call(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "sitecustomize.py").write_text(f"import time\ntime.sleep({STARTUP_DELAY})\n", encoding="utf-8")
    environment = dict(os.environ, PYTHONPATH=str(site))
    # The stage's role disagrees with its classification, so the launcher refuses before any read.
    result = subprocess.run(
        [sys.executable, str(LIB / "dispatch_seat.py"), "--dispatch", str(tmp_path / "missing.json"),
         "--root", str(tmp_path), "--vendor", "claude", "--own-vendor", "claude", "--work", "1",
         "--stage", "cold-seat", "--settings-source", "fixture", "--settings-scope", "seat",
         "--classification", "ordinary", "--requires", "read",
         "--hold-file", str(tmp_path / "holds.json"), "--output", str(tmp_path / "result.json")],
        env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
        timeout=60)
    assert result.returncode == 1, result.stderr
    split = refusal_split(result.stderr)
    assert split["clock_start"] == "process"
    assert split["total_seconds"] >= STARTUP_DELAY


@pytest.mark.skipif(os.name != "nt" and not sys.platform.startswith("linux"),
                    reason="the creation time is read only on Windows and Linux")
def test_978_process_started_is_this_process_on_the_monotonic_clock():
    # A fresh process: the test runner's own may be older than the age a creation time is trusted to.
    probe = ("import sys, time; sys.path.insert(0, sys.argv[1]); import preflight; "
             "started = preflight.process_started(); now = time.monotonic(); "
             "print(repr(None if started is None else now - started))")
    result = subprocess.run([sys.executable, "-c", probe, str(LIB)], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                            timeout=60)
    assert result.returncode == 0, result.stderr
    age = eval(result.stdout.strip())  # noqa: S307 - the probe prints a float's repr or None.
    assert isinstance(age, float)
    assert 0 <= age < 60


@pytest.mark.parametrize("age", [preflight.PROCESS_AGE_LIMIT_SECONDS + 1, -1.0, float("nan")])
def test_978_an_untrusted_creation_time_falls_back_to_entry(monkeypatch, age):
    # A process older than the limit, or a clock that disagrees, is measured from its scope's opening.
    monkeypatch.setattr(preflight, "_windows_process_age", lambda: age)
    monkeypatch.setattr(preflight, "_linux_process_age", lambda: age)
    started = preflight.process_started()
    assert started is None
    with preflight.scope(started=started, clock_start="process" if started is not None else None) as opened:
        assert opened.snapshot("report")["clock_start"] == "entry"


def test_978_a_scope_without_a_creation_time_starts_at_entry():
    assert preflight.Scope().snapshot("report")["clock_start"] == "entry"
    with preflight.scope(started=None, clock_start=None) as opened:
        assert opened.snapshot("report")["clock_start"] == "entry"


def test_978_a_seeded_scope_and_its_combined_line_keep_the_seeds_clock():
    entrance = preflight.Scope(started=time.monotonic() - 1, clock_start="process")
    assert entrance.snapshot("handoff")["clock_start"] == "process"
    seed = json.loads(json.dumps(entrance.handoff()))
    assert seed["clock_start"] == "process"
    # The launcher's own creation time does not replace the entrance's clock.
    launcher = preflight.Scope(seed=seed, started=time.monotonic(), clock_start="entry")
    record = launcher.snapshot("request-record")
    assert record["clock_start"] == "process"
    assert preflight.combine(record, 0.5, {})["clock_start"] == "process"
    # A handoff or record from before the clock was named reads as measured from entry.
    older = {key: value for key, value in seed.items() if key != "clock_start"}
    assert preflight.Scope(seed=older).clock_start == "entry"
    assert preflight.combine({key: value for key, value in record.items() if key != "clock_start"},
                             0.5, {})["clock_start"] == "entry"

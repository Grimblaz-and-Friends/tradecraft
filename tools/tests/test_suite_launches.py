"""Pins for the suite's launch guard.

Every arm is probed in both polarities, because a guard that only ever passes is
indistinguishable from one that cannot fail. The refusal arms matter most: this
guard's whole value is that it stops a pull request, and a message that named
one number would leave the reader unable to act on it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import suite_launches as sl  # noqa: E402


class _Option:
    """Stands in for pytest's parsed options; absent attributes read as unset."""

    def __init__(self, **values):
        for name, value in values.items():
            setattr(self, name, value)


# --- what counts as a whole-suite run ----------------------------------------

def test_the_invocation_ci_runs_is_a_whole_suite_run():
    assert sl.whole_suite(list(sl.FULL_SUITE), _Option()) is True


def test_a_bare_run_from_the_repository_root_is_a_whole_suite_run():
    assert sl.whole_suite([], _Option()) is True


def test_windows_separators_and_trailing_slashes_do_not_hide_the_whole_suite():
    args = [arg.replace("/", "\\") + "\\" for arg in sl.FULL_SUITE]
    assert sl.whole_suite(args, _Option()) is True


def test_running_one_directory_is_not_a_whole_suite_run():
    assert sl.whole_suite(["tools/tests"], _Option()) is False


def test_running_one_module_is_not_a_whole_suite_run():
    assert sl.whole_suite(["tools/tests/test_suite_launches.py"], _Option()) is False


def test_a_keyword_filter_over_the_whole_suite_is_not_a_whole_suite_run():
    """The paths are right and the population is not -- the arm a path-only
    check would wave through."""
    assert sl.whole_suite(list(sl.FULL_SUITE), _Option(keyword="launches")) is False


def test_last_failed_over_the_whole_suite_is_not_a_whole_suite_run():
    assert sl.whole_suite(list(sl.FULL_SUITE), _Option(lf=True)) is False


# --- the verdict, in both polarities -----------------------------------------

def test_a_partial_run_reports_its_count_and_compares_nothing():
    ok, line = sl.verdict(12, {"Windows": 99}, "Windows", collected_all=False)
    assert ok is True
    assert "12 launches" in line and "not compared" in line


def test_a_platform_with_no_baseline_is_told_what_to_write():
    """The bootstrap arm. It must pass -- the real number can only come from a
    run -- and it must not pass silently, or the guard is disarmed by an empty
    file and nobody finds out."""
    ok, line = sl.verdict(2738, {}, "Linux", collected_all=True)
    assert ok is True
    assert "not compared" in line
    assert '{"Linux": 2738}' in line
    assert sl.BASELINE_PATH.name in line


def test_a_count_at_its_baseline_passes():
    ok, line = sl.verdict(2738, {"Windows": 2738}, "Windows", collected_all=True)
    assert ok is True
    assert "at its baseline" in line


def test_a_count_above_its_baseline_refuses_and_names_both_numbers():
    ok, line = sl.verdict(2740, {"Windows": 2738}, "Windows", collected_all=True)
    assert ok is False
    assert "2740" in line and "2738" in line and "above" in line
    assert sl.BASELINE_PATH.name in line


def test_a_count_below_its_baseline_refuses_too():
    """A baseline the suite has outgrown downward describes nothing. The pull
    request that reduced the count is already editing this file."""
    ok, line = sl.verdict(2700, {"Windows": 2738}, "Windows", collected_all=True)
    assert ok is False
    assert "2700" in line and "2738" in line and "below" in line


def test_one_platforms_baseline_is_not_read_for_another():
    ok, _ = sl.verdict(10, {"Linux": 10}, "Windows", collected_all=True)
    assert ok is True, "no Windows entry means not compared, never compared to Linux's"


def test_an_unreadable_baseline_file_is_an_absent_one_not_a_crash(tmp_path):
    broken = tmp_path / "suite-launch-baseline.json"
    broken.write_text("{not json", encoding="utf-8")
    assert sl.read_baseline(broken) == {}
    assert sl.read_baseline(tmp_path / "missing.json") == {}


# --- the counter ---------------------------------------------------------

def test_every_launch_helper_is_counted_exactly_once():
    """`run`, `check_output` and `check_call` all construct a `Popen`, so one
    wrapper sees each of them once -- and nothing sees them twice."""
    counter = sl.Counter()
    counter.install()
    try:
        before = counter.launches
        subprocess.run([sys.executable, "-c", "pass"],
                       stdin=subprocess.DEVNULL, capture_output=True)
        subprocess.check_output([sys.executable, "-c", "pass"],
                                stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.check_call([sys.executable, "-c", "pass"], stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        counter.uninstall()
    assert counter.launches - before == 3


def test_uninstall_puts_the_real_constructor_back():
    original = subprocess.Popen.__init__
    counter = sl.Counter()
    counter.install()
    assert subprocess.Popen.__init__ is not original
    counter.uninstall()
    assert subprocess.Popen.__init__ is original


def test_a_second_install_does_not_wrap_the_wrapper():
    """Double-wrapping would count one launch twice and inflate every number
    the guard compares."""
    original = subprocess.Popen.__init__
    counter = sl.Counter()
    counter.install()
    counter.install()
    try:
        subprocess.run([sys.executable, "-c", "pass"],
                       stdin=subprocess.DEVNULL, capture_output=True)
    finally:
        counter.uninstall()
    assert counter.launches == 1
    assert subprocess.Popen.__init__ is original

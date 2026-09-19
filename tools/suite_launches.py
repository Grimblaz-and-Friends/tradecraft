"""Count the subprocess launches one full suite run makes, and hold them to a number.

**Why a count and not a clock.** This repository's CI spent about seven minutes
on its Windows leg against ninety seconds on Ubuntu, for the same tests at the
same commit, and nothing measured it while it grew. Wall-clock is the thing that
hurts, but it is not the thing to bound: a runner's seconds move with the
machine, so a ceiling on them fires on noise and goes quiet on real growth. The
launch count is deterministic -- the same tree gives the same number, launch for
launch -- and it is what the wall-clock is made of, because almost all of that
wall is `git` starting up. [#649]

**Why it refuses rather than reports.** A number nothing enforces is the state
the work was filed about. The baseline is a committed number, so raising it is a
line in the diff that a reviewer sees; the guard's job is to make sure somebody
writes that line deliberately.

**It refuses in both directions.** A count that falls without the baseline
following it leaves a number in the tree that no longer describes the suite,
which is the same defect as a count that rises -- the file stops meaning
anything. A pull request that reduces launches is already editing this file.

**Per platform**, because the two legs of the matrix need not agree, and measured
they do not: 2,854 on Linux against 2,849 on Windows at the same commit.

**Enforced in CI and reported everywhere else**, because the same measurement
shows a count is deterministic per machine and not across them -- a local
Windows checkout of that commit counted 2,851 against CI's 2,849. See
`enforced_here`.

**Nothing here is shipped.** This module and the root `conftest.py` that loads it
sit outside the shipped zone, so a repository that installs the practice as a
plugin receives neither.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
from pathlib import Path

import pytest

BASELINE_PATH = Path(__file__).resolve().parent / "suite-launch-baseline.json"

# The invocation CI runs and the landing flow names. A run over exactly these
# roots, or a bare run from the repository root, collects the whole suite; both
# were checked to collect the same tests.
FULL_SUITE = ("tools/tests", "skills", "lib/tests")

# Options that narrow what runs. A narrowed run counts a different population,
# so comparing it to the baseline would redden a correct tree.
NARROWING = ("keyword", "markexpr", "deselect", "lf", "failedfirst", "last_failed")


def whole_suite(args, option) -> bool:
    """Did this invocation collect the whole suite?

    `args` are pytest's positional arguments; `option` is its parsed options.
    Anything narrower reports its count and is not compared -- running part of
    the suite is an ordinary act and must not fail on a number about all of it.
    """
    selected = {str(arg).replace("\\", "/").rstrip("/") for arg in args if str(arg).strip()}
    if selected and selected != set(FULL_SUITE):
        return False
    for name in NARROWING:
        if getattr(option, name, None):
            return False
    return True


def read_baseline(path: Path = BASELINE_PATH) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def enforced_here(environ=None) -> bool:
    """Is this the environment the baseline describes?

    The baseline records the CI legs, and it is enforced there. It is **not**
    enforced on a developer's machine, because the count is deterministic per
    machine and not identical across machines: the CI Windows leg counted 2,849
    where a local Windows checkout of the same commit counted 2,851. Enforcing a
    CI number everywhere would fail honest local runs of a correct tree -- and
    the landing flow has every session run the whole suite before every commit,
    so that trap would spring constantly. What the row bought is that a pull
    request goes red before it merges, and CI is where that happens. [#649]
    """
    environ = os.environ if environ is None else environ
    return bool(environ.get("CI"))


def verdict(measured: int, baseline: dict, system: str, collected_all: bool,
            enforced: bool = True) -> tuple[bool, str]:
    """(ok, one line for the reader). Never raises: a guard that dies is a guard
    that stops guarding, and this one runs after every suite run there is.
    """
    if not collected_all:
        return True, (f"suite-launches: {measured} launches, not compared -- this run did not "
                      f"collect the whole suite, and the baseline describes all of it")
    if not enforced:
        recorded = baseline.get(system)
        against = (f" The recorded {system} leg is {recorded}."
                   if recorded is not None else "")
        return True, (f"suite-launches: {measured} launches on {system}, not compared -- the "
                      f"baseline records the CI legs, where it is enforced, and a count is "
                      f"deterministic per machine rather than across machines.{against}")
    expected = baseline.get(system)
    if expected is None:
        return True, (f"suite-launches: {measured} launches on {system}, not compared -- no "
                      f"baseline recorded for {system}. Write {{\"{system}\": {measured}}} into "
                      f"{BASELINE_PATH.name} to hold it there.")
    if measured == expected:
        return True, f"suite-launches: {measured} launches on {system}, at its baseline"
    direction = "above" if measured > expected else "below"
    return False, (f"suite-launches: {measured} launches on {system}, {abs(measured - expected)} "
                   f"{direction} the baseline of {expected}. If the change is intended, set "
                   f"\"{system}\" to {measured} in {BASELINE_PATH.name} in this same pull "
                   f"request, so the number keeps describing the suite.")


class Counter:
    """Wraps `Popen.__init__`, which every launch funnels through.

    `subprocess.run`, `check_output` and `check_call` all construct a `Popen`,
    so one wrapper counts each launch exactly once and no caller can route
    around it by preferring a different helper.
    """

    def __init__(self) -> None:
        self.launches = 0
        self._real_init = None

    def install(self) -> None:
        if self._real_init is not None:
            return
        self._real_init = subprocess.Popen.__init__
        counter = self

        def counting_init(popen_self, *args, **kwargs):
            counter.launches += 1
            return counter._real_init(popen_self, *args, **kwargs)

        subprocess.Popen.__init__ = counting_init

    def uninstall(self) -> None:
        if self._real_init is not None:
            subprocess.Popen.__init__ = self._real_init
            self._real_init = None


class Plugin:
    """Counts in whatever process it is loaded in, and sums the workers.

    Under `-n`, the launches happen in worker processes and the controller makes
    almost none. A counter that reported only the controller's would report
    nearly zero and pass forever, so each worker hands its count up through
    `workeroutput` and the controller adds them as each worker finishes.
    """

    def __init__(self) -> None:
        self.counter = Counter()
        self.from_workers = 0
        self.saw_workers = False

    def pytest_configure(self, config) -> None:
        self.counter.install()

    # `optionalhook` because this hook belongs to xdist: a serial run has no
    # xdist installed, and pluggy refuses an unknown hook outright rather than
    # ignoring it -- which took down collection entirely the first time.
    @pytest.hookimpl(optionalhook=True)
    def pytest_testnodedown(self, node, error) -> None:
        # Controller side, once per worker.
        self.saw_workers = True
        output = getattr(node, "workeroutput", None) or {}
        self.from_workers += int(output.get("suite_launches", 0))

    def pytest_sessionfinish(self, session, exitstatus) -> None:
        self.counter.uninstall()
        config = session.config
        workeroutput = getattr(config, "workeroutput", None)
        if workeroutput is not None:
            # Worker side: hand the count up and judge nothing.
            workeroutput["suite_launches"] = self.counter.launches
            return
        measured = self.from_workers if self.saw_workers else self.counter.launches
        ok, line = verdict(
            measured,
            read_baseline(),
            platform.system(),
            whole_suite(config.args, config.option),
            enforced_here(),
        )
        # Written through the terminal reporter so it survives capture and lands
        # with the rest of the run's summary rather than ahead of it.
        reporter = config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line(line)
        else:
            print(line)
        if not ok and session.exitstatus == 0:
            session.exitstatus = 1

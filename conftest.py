"""Loads the suite's launch counter. The logic is `tools/suite_launches.py`.

Thin on purpose: a `conftest.py` cannot be imported as a module from a test, so
a guard written here could never be probed in both polarities. Everything that
decides anything lives next door, where its own tests reach it. [#649]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

from suite_launches import Plugin  # noqa: E402


def pytest_configure(config):
    config.pluginmanager.register(Plugin(), "suite-launches")

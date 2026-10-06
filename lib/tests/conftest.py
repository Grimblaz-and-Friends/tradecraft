"""Isolate library tests and their children from user settings and maintenance."""
import os
from pathlib import Path
import tempfile

import pytest


def artifact_copy_directories(parent):
    return {path for path in parent.glob("tradecraft-artifact-*") if path.is_dir()}


def assert_no_new_artifact_copies(parent, before):
    added = artifact_copy_directories(parent) - before
    assert not added, "Tests leaked artifact copies into system temp: " + ", ".join(
        sorted(str(path) for path in added))


def pytest_configure(config):
    if not hasattr(config, "workerinput"):
        # The coordinator checks after every worker stops, so another worker's
        # live allocation cannot be mistaken for a leftover. Never sweep copies.
        parent = Path(tempfile.gettempdir()).resolve()
        config._artifact_copy_temp_snapshot = parent, artifact_copy_directories(parent)


def pytest_sessionfinish(session, exitstatus):
    if not hasattr(session.config, "workerinput"):
        parent, before = session.config._artifact_copy_temp_snapshot
        try:
            assert_no_new_artifact_copies(parent, before)
        except AssertionError as exc:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
            reporter = session.config.pluginmanager.get_plugin("terminalreporter")
            if reporter is not None:
                reporter.write_sep("=", str(exc), red=True)


@pytest.fixture
def artifact_copy_guard():
    return assert_no_new_artifact_copies


@pytest.fixture(autouse=True)
def isolated_artifact_copy_parent(tmp_path, monkeypatch):
    parent = tmp_path
    # Redirect Python's cached temp parent and child processes' discovery. A
    # retained or deliberately unremovable copy stays inside this test's tree.
    monkeypatch.setattr(tempfile, "tempdir", str(parent))
    for variable in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(variable, str(parent))


@pytest.fixture(scope="session", autouse=True)
def disabled_git_maintenance(request):
    # Session scope precedes the module templates' commits. Environment config
    # reaches child processes without writing any Git configuration file.
    # Both conftests expose this fixture, so share one override per session.
    if getattr(request.session, "_tradecraft_git_maintenance_disabled", False):
        yield
        return
    count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(f"GIT_CONFIG_KEY_{count}", "maintenance.auto")
        patch.setenv(f"GIT_CONFIG_VALUE_{count}", "false")
        patch.setenv("GIT_CONFIG_COUNT", str(count + 1))
        request.session._tradecraft_git_maintenance_disabled = True
        yield


@pytest.fixture(autouse=True)
def isolated_machine_home(tmp_path, monkeypatch):
    home = tmp_path / "machine-home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

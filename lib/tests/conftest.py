"""Isolate library tests and their children from user settings and maintenance."""
import os
from pathlib import Path

import pytest


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

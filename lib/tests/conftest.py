"""Keep library tests and their children away from the user's settings."""
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_machine_home(tmp_path, monkeypatch):
    home = tmp_path / "machine-home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

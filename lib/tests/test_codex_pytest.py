import os
from pathlib import Path
import sys
import tomllib

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
from codex_pytest import pytest_addopts_override


@pytest.mark.parametrize("inherited", [
    None, "", "-q", '-k "passing or policy" --basetemp="C:\\test roots\\run"',
    " \t\r\n-q  ", "-p no:cacheprovider",
    "--label=" + chr(0xE9) + chr(0x1F680),
    "".join(chr(code) for code in range(1, 32)) + chr(127),
])
def test_override_round_trips_inherited_text_without_mutating_environment(monkeypatch, inherited):
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    if inherited is not None:
        monkeypatch.setenv("PYTEST_ADDOPTS", inherited)
    before = dict(os.environ)

    override = pytest_addopts_override()

    policy = tomllib.loads(override)["shell_environment_policy"]
    expected = f"{inherited} -p no:cacheprovider" if inherited else "-p no:cacheprovider"
    assert policy == {"set": {"PYTEST_ADDOPTS": expected}}
    assert dict(os.environ) == before

import os
from pathlib import Path
import subprocess
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


def test_env_override_keeps_cache_options_registered_without_writing_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    (tmp_path / "pyproject.toml").write_bytes(
        b'[tool.pytest.ini_options]\naddopts = "--ff --sw"\ncache_dir = "cache-output"\n'
    )
    (tmp_path / "test_passing.py").write_bytes(
        b'def test_passing(pytestconfig):\n'
        b'    assert not pytestconfig.pluginmanager.has_plugin("cacheprovider")\n'
        b'    assert pytestconfig.getoption("failedfirst")\n'
        b'    assert pytestconfig.getoption("stepwise")\n'
    )
    env = os.environ.copy()
    env["PYTEST_ADDOPTS"] = tomllib.loads(pytest_addopts_override())[
        "shell_environment_policy"]["set"]["PYTEST_ADDOPTS"]

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--strict-config"], cwd=tmp_path, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
    )

    assert result.returncode == 0, result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace")
    assert not (tmp_path / "cache-output").exists()
    assert not (tmp_path / ".pytest_cache").exists()

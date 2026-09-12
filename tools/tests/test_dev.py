"""Exercises environment isolation, version failures and temporary ownership."""
import importlib.util
import json
from collections import namedtuple
from pathlib import Path
import subprocess
import sys
import venv

import pytest

SPEC = importlib.util.spec_from_file_location("dev", Path(__file__).parents[1] / "dev.py")
dev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dev)


def test_wrong_interpreter_reports_required_version(tmp_path):
    (tmp_path / ".python-version").write_text("0.0", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Use Python 0.0"):
        dev.require_version(tmp_path)


def test_missing_environment_does_not_fall_back_to_global_python(tmp_path):
    with pytest.raises(RuntimeError, match="No worktree environment"):
        dev.verify_environment(tmp_path, "3.14")


def test_setup_keeps_an_existing_environment_and_uses_its_python(tmp_path, monkeypatch):
    folder = tmp_path / ".venv"
    folder.mkdir()
    sentinel = folder / "consumer-work"
    sentinel.write_text("keep", encoding="utf-8")
    python = dev.environment_python(tmp_path)
    monkeypatch.setattr(dev, "verify_environment", lambda root, wanted: python)
    calls = []
    monkeypatch.setattr(dev.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)))
    assert dev.setup(tmp_path, "3.14") == 0
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert calls[0][0][0] == str(python)
    assert calls[0][0][-1] == str(tmp_path / "requirements-dev.txt")


def test_wrong_environment_is_rejected_before_install(tmp_path, monkeypatch):
    python = dev.environment_python(tmp_path)
    python.parent.mkdir(parents=True)
    python.touch()
    (tmp_path / ".venv/pyvenv.cfg").write_text("include-system-site-packages = false\n", encoding="utf-8")
    info = {"version": "3.12", "prefix": str(tmp_path / ".venv"), "base_prefix": "elsewhere"}
    monkeypatch.setattr(dev.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 0, json.dumps(info), ""))
    with pytest.raises(RuntimeError, match="Move it aside"):
        dev.setup(tmp_path, "3.14")
    assert python.exists()


def test_partial_environment_names_recovery_and_preserves_contents(tmp_path):
    folder = tmp_path / ".venv"
    folder.mkdir()
    sentinel = folder / "consumer-work"
    sentinel.write_text("keep", encoding="utf-8")
    for _ in range(2):
        with pytest.raises(RuntimeError, match="Move it aside"):
            dev.setup(tmp_path, "3.14")
        assert sentinel.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("system_packages", [False, True])
def test_real_environment_isolation_is_required(tmp_path, system_packages):
    venv.EnvBuilder(with_pip=False, system_site_packages=system_packages).create(tmp_path / ".venv")
    if system_packages:
        with pytest.raises(RuntimeError, match="isolated worktree environment"):
            dev.verify_environment(tmp_path, "3.14")
    else:
        assert dev.verify_environment(tmp_path, "3.14") == dev.environment_python(tmp_path)


def test_environment_interpreter_must_belong_to_this_worktree(tmp_path, monkeypatch):
    venv.EnvBuilder(with_pip=False).create(tmp_path / ".venv")
    monkeypatch.setattr(dev, "environment_python", lambda root: Path(sys.executable))
    with pytest.raises(RuntimeError, match="isolated worktree environment"):
        dev.verify_environment(tmp_path, "3.14")


def test_existing_environment_can_be_selected_by_an_older_outer_python(tmp_path, monkeypatch):
    (tmp_path / ".python-version").write_text("3.14", encoding="utf-8")
    venv.EnvBuilder(with_pip=False).create(tmp_path / ".venv")
    monkeypatch.setattr(dev, "ROOT", tmp_path)
    version = namedtuple("Version", "major minor micro releaselevel serial")(3, 12, 0, "final", 0)
    monkeypatch.setattr(sys, "version_info", version)
    seen = []
    monkeypatch.setattr(dev, "run_checks", lambda root, python, action, extra: seen.append(python) or 0)
    assert dev.main(["test"]) == 0
    assert seen == [dev.environment_python(tmp_path)]


def test_setup_still_requires_the_declared_python_for_creation(tmp_path, monkeypatch):
    (tmp_path / ".python-version").write_text("0.0", encoding="utf-8")
    monkeypatch.setattr(dev, "ROOT", tmp_path)
    assert dev.main(["setup"]) == 1
    assert not (tmp_path / ".venv").exists()


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("relative", [".", "scratch/../scratch"])
def test_scratch_in_checkout_is_refused_before_pytest(tmp_path, monkeypatch, explicit, relative):
    scratch = tmp_path / relative
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.delenv("PYTEST_DEBUG_TEMPROOT", raising=False)
    if explicit:
        monkeypatch.setenv("PYTEST_DEBUG_TEMPROOT", str(scratch))
    else:
        monkeypatch.setattr(dev.tempfile, "gettempdir", lambda: str(scratch))
    def unexpected(*args, **kwargs):
        pytest.fail("pytest must not run with scratch inside the checkout")
    monkeypatch.setattr(dev.subprocess, "run", unexpected)
    with pytest.raises(RuntimeError, match="outside this checkout"):
        dev.run_checks(tmp_path, Path(sys.executable), "test", [])


def test_nested_test_runs_have_separate_scratch_and_forward_arguments(tmp_path, monkeypatch):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setenv("PYTEST_DEBUG_TEMPROOT", str(scratch))
    root = tmp_path / "checkout"
    root.mkdir()
    seen = []
    python = Path(sys.executable)

    def launch(command, *, cwd, env):
        current = Path(env["PYTEST_DEBUG_TEMPROOT"])
        assert current.is_dir()
        assert current.parent == scratch
        assert not current.is_relative_to(root)
        assert cwd == root
        assert command == [str(python), "-m", "pytest", "chosen_test.py", "-q"]
        seen.append(current)
        if len(seen) == 1:
            assert dev.run_checks(root, python, "test", ["chosen_test.py", "-q"]) == 7
            assert current.is_dir()
        return subprocess.CompletedProcess(command, 7)

    monkeypatch.setattr(dev.subprocess, "run", launch)
    assert dev.run_checks(root, python, "test", ["chosen_test.py", "-q"]) == 7
    assert seen[0] != seen[1]
    assert all(not path.exists() for path in seen)


def test_failed_lint_prevents_later_checks(tmp_path, monkeypatch):
    calls = []

    def launch(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 4)

    monkeypatch.setattr(dev.subprocess, "run", launch)
    assert dev.run_checks(tmp_path, Path(sys.executable), "check", []) == 4
    assert len(calls) == 1

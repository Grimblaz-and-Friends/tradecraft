"""Exercises environment isolation, version failures and temporary ownership."""
import importlib.util
from pathlib import Path
import subprocess
import sys

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
    monkeypatch.setattr(dev.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 0, "3.12\n", ""))
    with pytest.raises(RuntimeError, match="Move it aside"):
        dev.setup(tmp_path, "3.14")
    assert python.exists()


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

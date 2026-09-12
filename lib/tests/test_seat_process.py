import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import seat_process as process


def test_worker_preserves_binary_streams_exit_status_and_missing_launch(tmp_path):
    content = bytes(range(256)) * 1000
    command = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read()); sys.stderr.buffer.write(b'diagnostic'); sys.exit(7)"]
    result = process.run_process(command, input=content, cwd=tmp_path, timeout=10)
    assert result.args == command
    assert result.returncode == 7
    assert result.stdout == content
    assert result.stderr == b"diagnostic"
    with pytest.raises(FileNotFoundError):
        process.run_process([str(tmp_path / "missing-program")], input=b"", cwd=tmp_path, timeout=10)


def test_containment_failure_never_launches_the_vendor(tmp_path, monkeypatch):
    error = tmp_path / "error.json"
    calls = []
    def denied():
        raise PermissionError("cannot establish containment")
    monkeypatch.setattr(process, "_join_kill_on_close_job", denied)
    monkeypatch.setattr(process.subprocess, "run", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(sys, "argv", ["worker", str(error), "vendor"])
    assert process.main() == 1
    assert not calls
    assert json.loads(error.read_bytes()) == {"missing": False, "message": "cannot establish containment"}

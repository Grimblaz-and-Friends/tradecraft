import json
import io
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

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


def test_incremental_capture_checkpoints_while_stdin_blocks(tmp_path):
    output, ticks, launched = [], [], []
    child = [sys.executable, "-c", "import sys,time; print('identity',flush=True); sys.stderr.write('diagnostic'); sys.stderr.flush(); time.sleep(30)"]
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        process.run_process(child, input=b'x' * 1000000, cwd=tmp_path, timeout=5,
                            on_output=lambda *event: output.append(event),
                            on_tick=lambda: ticks.append(time.monotonic()),
                            on_launch=launched.append)
    assert time.monotonic() - started < 6
    assert launched and len(ticks) > 2
    assert b'identity' in caught.value.stdout
    assert b'diagnostic' in caught.value.stderr
    assert b'identity' in b''.join(data for name, data in output if name == 'stdout')


def test_incremental_capture_drains_both_full_pipes(tmp_path):
    output = []
    child = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'o'*200000); sys.stderr.buffer.write(b'e'*200000); sys.stdin.buffer.read()"]
    result = process.run_process(child, input=b'x' * 200000, cwd=tmp_path, timeout=5,
                                 on_output=lambda *event: output.append(event))
    assert result.stdout == b'o' * 200000 and result.stderr == b'e' * 200000
    assert result.returncode == 0 and len(output) > 2


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


def test_posix_timeout_bounds_drain_and_keeps_captured_bytes(tmp_path, monkeypatch):
    class EscapedPipe:
        pid = 123
        def __init__(self):
            self.stdin, self.stdout, self.stderr = io.BytesIO(), io.BytesIO(), io.BytesIO()
            self.calls = 0
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def communicate(self, input=None, timeout=None):
            self.calls += 1
            if self.calls == 2:
                assert timeout is not None and timeout <= 1, "Post-timeout drain must be bounded."
            raise subprocess.TimeoutExpired(["vendor"], timeout, output=b"already captured", stderr=b"diagnostic")
    child = EscapedPipe()
    killed = []
    monkeypatch.setattr(process, "os", SimpleNamespace(name="posix", killpg=lambda *a: killed.append(a)))
    monkeypatch.setattr(process, "signal", SimpleNamespace(SIGKILL=9))
    monkeypatch.setattr(process.subprocess, "Popen", lambda *a, **k: child)
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        process.run_process(["vendor"], input=b"", cwd=tmp_path, timeout=0.1)
    assert caught.value.output == b"already captured"
    assert caught.value.stderr == b"diagnostic"
    assert child.stdout.closed and child.stderr.closed and child.stdin.closed
    assert killed


@pytest.mark.skipif(os.name != "posix", reason="POSIX setsid escape")
def test_detached_descendant_cannot_hold_timeout_drain_open(tmp_path):
    child = tmp_path / "detached.py"
    child.write_bytes(b"import os,time\nfrom pathlib import Path\nos.setsid()\nPath('child-pid').write_text(str(os.getpid()))\nprint('detached output',flush=True)\ntime.sleep(20)\nPath('finished').write_bytes(b'yes')\n")
    wrapper = "import subprocess,sys,time; subprocess.Popen([sys.executable,sys.argv[1]],stdin=sys.stdin,stdout=sys.stdout,stderr=sys.stderr); time.sleep(30)"
    timeout = 5
    started = time.monotonic()
    try:
        with pytest.raises(subprocess.TimeoutExpired) as caught:
            process.run_process([sys.executable, "-c", wrapper, str(child)], input=b"", cwd=tmp_path, timeout=timeout)
        assert (tmp_path / "child-pid").exists(), "The detached child must actually start."
        assert time.monotonic() - started < timeout + 1
        assert b"detached output" in caught.value.output
    finally:
        pid = tmp_path / "child-pid"
        if pid.exists() and not (tmp_path / "finished").exists():
            try:
                os.kill(int(pid.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass

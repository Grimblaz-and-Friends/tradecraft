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


def test_failed_vendor_spawn_does_not_report_a_launch(tmp_path):
    launched = []
    with pytest.raises(FileNotFoundError):
        process.run_process([str(tmp_path / "missing-vendor")], input=b"", cwd=tmp_path,
                            timeout=20, on_launch=launched.append)
    assert launched == []


def test_successful_vendor_spawn_acknowledges_the_containment_owner(tmp_path, monkeypatch):
    launched = []
    owners = []
    original = process.subprocess.Popen
    def spawn(*args, **kwargs):
        child = original(*args, **kwargs)
        owners.append(child.pid)
        return child
    monkeypatch.setattr(process.subprocess, "Popen", spawn)
    result = process.run_process([sys._base_executable, "-c", "import os; print(os.getpid())"],
        input=b"", cwd=tmp_path, timeout=20, on_launch=launched.append)
    assert launched == owners
    assert int(result.stdout) > 0 and result.returncode == 0


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
    child = [sys._base_executable, "-c", "import sys,time; print('identity',flush=True); sys.stderr.write('diagnostic'); sys.stderr.flush(); time.sleep(30)"]
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        process.run_process(child, input=b'x' * 1000000, cwd=tmp_path, timeout=3,
                            on_output=lambda *event: output.append(event),
                            on_tick=lambda: ticks.append(time.monotonic()),
                            on_launch=launched.append)
    assert time.monotonic() - started < 5
    assert launched and len(ticks) > 2
    assert b'identity' in caught.value.stdout
    assert b'diagnostic' in caught.value.stderr
    assert b'identity' in b''.join(data for name, data in output if name == 'stdout')


def test_incremental_capture_drains_both_full_pipes(tmp_path):
    output = []
    child = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'o'*200000); sys.stderr.buffer.write(b'e'*200000); sys.stdin.buffer.read()"]
    # This verifies complete capture, not a five-second startup guarantee under
    # the full parallel suite. Deadline enforcement has its own fixture above.
    result = process.run_process(child, input=b'x' * 200000, cwd=tmp_path, timeout=20,
                                 on_output=lambda *event: output.append(event))
    assert result.stdout == b'o' * 200000 and result.stderr == b'e' * 200000
    assert result.returncode == 0 and len(output) > 2


@pytest.mark.parametrize("slow_callback", ["tick", "output"])
def test_completed_capture_keeps_unread_bytes_during_slow_recording(tmp_path, monkeypatch, slow_callback):
    native_clock = process.time.monotonic
    offset = [0.0]
    monkeypatch.setattr(process.time, "monotonic", lambda: native_clock() + offset[0])
    original_spawn = process.subprocess.Popen

    def already_exited(*args, **kwargs):
        child = original_spawn(*args, **kwargs)
        # Both small pipe payloads fit without a reader. Synchronize on exit,
        # rather than depending on whether a loaded runner schedules us first.
        child.wait(timeout=60)
        return child

    monkeypatch.setattr(process.subprocess, "Popen", already_exited)
    output = []

    def slow_tick():
        if slow_callback == "tick":
            offset[0] += 0.4

    def retain(name, chunk):
        output.append((name, chunk))
        if slow_callback == "output":
            offset[0] += 0.4

    command = [sys._base_executable, "-c",
               "import sys; sys.stdout.buffer.write(b'final result'); sys.stderr.buffer.write(b'diagnostic')"]
    result = process.run_process(command, input=b"", cwd=tmp_path, timeout=60,
                                 on_output=retain, on_tick=slow_tick)
    assert result.returncode == 0
    assert result.stdout == b"final result" and result.stderr == b"diagnostic"
    assert b"".join(chunk for name, chunk in output if name == "stdout") == result.stdout
    assert b"".join(chunk for name, chunk in output if name == "stderr") == result.stderr


@pytest.mark.parametrize("cleanup_end", [None, 0.15])
@pytest.mark.parametrize("queued", [False, True])
def test_incremental_drain_and_wait_share_one_cleanup_allowance(tmp_path, monkeypatch, cleanup_end, queued):
    current = [0.0]
    monkeypatch.setattr(process.time, "monotonic", lambda: current[0])
    class Child:
        pid = 123
        stdin, stdout, stderr = io.BytesIO(), io.BytesIO(), io.BytesIO()
        def poll(self):
            return None
        def wait(self, timeout):
            current[0] += timeout
            raise subprocess.TimeoutExpired(["vendor"], timeout)
    class Events:
        emitted = False
        remaining = 3 if queued else 0
        def get(self, timeout):
            current[0] += timeout
            if not self.emitted:
                self.emitted = True
                return "stdout", b"received before stop"
            raise process.queue.Empty
        def empty(self):
            return not self.remaining
        def get_nowait(self):
            self.remaining -= 1
            current[0] += 0.1
            return "stdout", b"queued after drain allowance"
    monkeypatch.setattr(process, "os", SimpleNamespace(name="posix", killpg=lambda *_: None))
    monkeypatch.setattr(process, "signal", SimpleNamespace(SIGKILL=9))
    monkeypatch.setattr(process.subprocess, "Popen", lambda *_a, **_k: Child())
    monkeypatch.setattr(process.queue, "Queue", Events)
    monkeypatch.setattr(process.threading, "Thread", lambda **_k: SimpleNamespace(start=lambda: None))
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        process.run_process(["vendor"], input=b"", cwd=tmp_path, timeout=0.05,
                            on_tick=lambda: None, cleanup_deadline=cleanup_end)
    assert caught.value.output == b"received before stop"
    assert current[0] <= (0.30 if cleanup_end is None else cleanup_end) + 0.000001


def test_slow_output_recording_cannot_extend_the_absolute_cleanup_deadline(tmp_path, monkeypatch):
    current = [0.0]
    monkeypatch.setattr(process.time, "monotonic", lambda: current[0])

    class Child:
        pid, returncode = 123, 0
        stdin, stdout, stderr = io.BytesIO(), io.BytesIO(), io.BytesIO()
        def poll(self):
            return self.returncode
        def wait(self, timeout):
            current[0] += timeout
            return self.returncode

    class Events:
        def get(self, timeout):
            # An inherited writer keeps supplying bytes after the parent exits.
            return "stdout", b"received"
        def empty(self):
            return True

    monkeypatch.setattr(process, "os", SimpleNamespace(name="posix", killpg=lambda *_: None))
    monkeypatch.setattr(process, "signal", SimpleNamespace(SIGKILL=9))
    monkeypatch.setattr(process.subprocess, "Popen", lambda *_a, **_k: Child())
    monkeypatch.setattr(process.queue, "Queue", Events)
    monkeypatch.setattr(process.threading, "Thread", lambda **_k: SimpleNamespace(start=lambda: None))
    monkeypatch.setattr(process, "Descendants", lambda: SimpleNamespace(kill=lambda: None, finish=lambda *_: True))

    def recording(*_args):
        current[0] += 0.1

    result = process.run_process(["vendor"], input=b"", cwd=tmp_path, timeout=10,
                                 on_output=recording, cleanup_deadline=0.5)
    assert result.stdout == b"received" * 5
    assert current[0] <= 0.500001


def test_slow_recording_does_not_renew_timeout_cleanup(tmp_path, monkeypatch):
    current = [0.0]
    monkeypatch.setattr(process.time, "monotonic", lambda: current[0])

    class Child:
        pid = 123
        stdin, stdout, stderr = io.BytesIO(), io.BytesIO(), io.BytesIO()
        def poll(self):
            return None
        def wait(self, timeout):
            current[0] += timeout
            raise subprocess.TimeoutExpired(["vendor"], timeout)

    class Events:
        def get(self, timeout):
            current[0] += timeout
            return "stdout", b"received"
        def empty(self):
            return True

    monkeypatch.setattr(process, "os", SimpleNamespace(name="posix", killpg=lambda *_: None))
    monkeypatch.setattr(process, "signal", SimpleNamespace(SIGKILL=9))
    monkeypatch.setattr(process.subprocess, "Popen", lambda *_a, **_k: Child())
    monkeypatch.setattr(process.queue, "Queue", Events)
    monkeypatch.setattr(process.threading, "Thread", lambda **_k: SimpleNamespace(start=lambda: None))
    monkeypatch.setattr(process, "Descendants", lambda: SimpleNamespace(kill=lambda: None, finish=lambda *_: True))

    def recording(*_args):
        current[0] += 0.1

    with pytest.raises(subprocess.TimeoutExpired):
        process.run_process(["vendor"], input=b"", cwd=tmp_path, timeout=0.05,
                            on_output=recording, cleanup_deadline=1)
    assert current[0] < 0.5



def test_checkpoint_cannot_renew_the_process_wait(tmp_path, monkeypatch):
    current = [0.0]
    waits = []
    monkeypatch.setattr(process.time, "monotonic", lambda: current[0])
    class Child:
        pid = 123
        stdin, stdout, stderr = io.BytesIO(), io.BytesIO(), io.BytesIO()
        def poll(self):
            return None
        def wait(self, timeout):
            current[0] += timeout
            raise subprocess.TimeoutExpired(["vendor"], timeout)
    class Events:
        def get(self, timeout):
            waits.append(timeout)
            current[0] += timeout
            raise process.queue.Empty
        def empty(self):
            return True
    monkeypatch.setattr(process, "os", SimpleNamespace(name="posix", killpg=lambda *_: None))
    monkeypatch.setattr(process, "signal", SimpleNamespace(SIGKILL=9))
    monkeypatch.setattr(process.subprocess, "Popen", lambda *_a, **_k: Child())
    monkeypatch.setattr(process.queue, "Queue", Events)
    monkeypatch.setattr(process.threading, "Thread", lambda **_k: SimpleNamespace(start=lambda: None))
    def checkpoint():
        current[0] = 0.1
    with pytest.raises(subprocess.TimeoutExpired):
        process.run_process(["vendor"], input=b"", cwd=tmp_path, timeout=0.05,
                            on_tick=checkpoint, cleanup_deadline=0.1)
    assert not waits, "Recording must not extend an already expired wait."
    assert current[0] == 0.1


def test_expired_drain_does_not_close_a_pipe_owned_by_a_reader(tmp_path, monkeypatch):
    # Model a Windows synchronous read whose close waits for its pipe owner.
    # EOF deliberately arrives only after the caller has finished cleanup.
    started = process.threading.Event()
    release = process.threading.Event()
    closed = process.threading.Event()
    class Pipe:
        def fileno(self):
            return 42
        def close(self):
            release.wait(3)
            closed.set()
    class Child:
        pid = 123
        stdin, stdout, stderr = io.BytesIO(), Pipe(), io.BytesIO()
        def poll(self):
            return None
        def wait(self, timeout):
            raise subprocess.TimeoutExpired(["vendor"], timeout)
    child = Child()
    def read(fd, size):
        started.set()
        release.wait(3)
        return b""
    monkeypatch.setattr(process, "os", SimpleNamespace(name="posix", killpg=lambda *_: None, read=read))
    monkeypatch.setattr(process, "signal", SimpleNamespace(SIGKILL=9))
    monkeypatch.setattr(process.subprocess, "Popen", lambda *_a, **_k: child)
    beginning = time.monotonic()
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            process.run_process(["vendor"], input=b"", cwd=tmp_path, timeout=0.1,
                                on_launch=lambda _: None,
                                cleanup_deadline=beginning + 0.3)
        assert started.is_set()
        assert time.monotonic() - beginning < 1
        assert not closed.is_set(), "The blocked reader must retain close ownership."
    finally:
        release.set()
        assert closed.wait(3), "The reader must release its handle after EOF."


@pytest.mark.skipif(os.name != "nt", reason="Windows anonymous-pipe polling")
def test_windows_polling_does_not_read_a_silent_pipe_with_a_live_writer():
    handles = [os.pipe(), os.pipe()]
    streams = [os.fdopen(read, "rb", buffering=0) for read, _ in handles]
    child = SimpleNamespace(stdout=streams[0], stderr=streams[1])
    ended = set()
    reader = process._windows_pipe_reader(child, ended)
    try:
        with pytest.raises(process.queue.Empty):
            reader(0)  # Writers still own both pipes: no EOF and no blocked read.
        os.write(handles[0][1], b"stdout")
        os.write(handles[1][1], b"stderr")
        assert reader(0) == ("stdout", b"stdout")
        assert reader(0) == ("stderr", b"stderr")
        for _, write in handles:
            os.close(write)
        handles = []
        for name in ("stdout", "stderr"):
            assert reader(0) == (name, None)
            ended.add(name)
        with pytest.raises(process.queue.Empty):
            reader(0)
    finally:
        for _, write in handles:
            os.close(write)
        for stream in streams:
            stream.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows polling needs no reader threads")
def test_windows_empty_input_capture_never_starts_a_reader_thread(tmp_path, monkeypatch):
    monkeypatch.setattr(process.threading, "Thread", lambda **_k: pytest.fail("started a reader for a bounded probe"))
    output = []
    result = process.run_process([sys.executable, "-c", "print('ready')"], input=b"", cwd=tmp_path,
                                 timeout=10, on_output=lambda *event: output.append(event))
    assert result.returncode == 0 and b"ready" in result.stdout
    assert b"ready" in b"".join(data for name, data in output if name == "stdout")


def test_pipe_setup_failure_still_stops_the_owned_process(tmp_path, monkeypatch):
    stopped, waited = [], []
    class Child:
        pid = 123
        stdin, stdout, stderr = io.BytesIO(), io.BytesIO(), io.BytesIO()
        def poll(self):
            return 1 if stopped else None
        def kill(self):
            stopped.append(self.pid)
        def wait(self, timeout):
            waited.append(timeout)
            return 1
    child = Child()
    def failed(*_args):
        raise OSError("pipe setup failed")
    monkeypatch.setattr(process, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(process.subprocess, "Popen", lambda *_a, **_k: child)
    monkeypatch.setattr(process, "_windows_pipe_reader", failed)
    with pytest.raises(OSError, match="pipe setup failed"):
        process.run_process(["vendor"], input=b"", cwd=tmp_path, timeout=1, on_launch=lambda _: None)
    assert stopped == [123] and waited
    assert child.stdout.closed and child.stderr.closed


def test_stopped_recipient_drain_never_runs_another_checkpoint(tmp_path, monkeypatch):
    current, ticks = [0.0], []
    monkeypatch.setattr(process.time, "monotonic", lambda: current[0])
    class Child:
        pid = 123
        stdin, stdout, stderr = io.BytesIO(), io.BytesIO(), io.BytesIO()
        def poll(self):
            return None
        def wait(self, timeout):
            current[0] += timeout
            raise subprocess.TimeoutExpired(["vendor"], timeout)
    class Events:
        def get(self, timeout):
            current[0] += timeout
            raise process.queue.Empty
        def empty(self):
            return True
    monkeypatch.setattr(process, "os", SimpleNamespace(name="posix", killpg=lambda *_: None))
    monkeypatch.setattr(process, "signal", SimpleNamespace(SIGKILL=9))
    monkeypatch.setattr(process.subprocess, "Popen", lambda *_a, **_k: Child())
    monkeypatch.setattr(process.queue, "Queue", Events)
    monkeypatch.setattr(process.threading, "Thread", lambda **_k: SimpleNamespace(start=lambda: None))
    def checkpoint():
        assert current[0] < 0.05, "A stopped recipient must leave recording to completion."
        ticks.append(current[0])
        current[0] += 0.05
    with pytest.raises(subprocess.TimeoutExpired):
        process.run_process(["vendor"], input=b"", cwd=tmp_path, timeout=0.05,
                            on_tick=checkpoint, cleanup_deadline=0.3)
    assert len(ticks) == 1 and current[0] <= 0.3

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
    timeout = 2
    started = time.monotonic()
    try:
        with pytest.raises(subprocess.TimeoutExpired) as caught:
            process.run_process([sys._base_executable, "-c", wrapper, str(child)], input=b"", cwd=tmp_path, timeout=timeout)
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


@pytest.mark.skipif(os.name == "nt", reason="POSIX setsid descendant")
@pytest.mark.parametrize("incremental", [False, True])
def test_setsid_descendant_is_dead_or_cleanup_is_explicitly_unproved(tmp_path, incremental):
    import run_lifecycle
    escaped_pid = tmp_path / "escaped-pid"
    escaped_code = ("import os, pathlib, time; os.setsid(); "
                    f"pathlib.Path({str(escaped_pid)!r}).write_text(str(os.getpid())); "
                    "os.close(0); os.close(1); os.close(2); time.sleep(30)")
    command = [sys.executable, "-c", "import subprocess, sys, time; "
               f"subprocess.Popen([sys.executable, '-c', {escaped_code!r}]); time.sleep(30)"]
    try:
        with pytest.raises(subprocess.TimeoutExpired) as caught:
            process.run_process(command, input=b"", cwd=tmp_path, timeout=2,
                                **({"on_tick": lambda: None} if incremental else {}))
        assert escaped_pid.is_file()
        if caught.value.cleanup_proven:
            with pytest.raises(ProcessLookupError):
                run_lifecycle.process_identity(int(escaped_pid.read_text()))
        else:
            assert caught.value.cleanup_proven is False
        if sys.platform.startswith("linux"):
            assert caught.value.cleanup_proven, "Linux must reap adopted escapees, even without open pipes."
    finally:
        if escaped_pid.is_file():
            try:
                os.kill(int(escaped_pid.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass



def test_worker_ack_failure_retains_proof_that_vendor_spawned(tmp_path, monkeypatch):
    error = tmp_path / "error.json"
    monkeypatch.setattr(process, "_join_kill_on_close_job", lambda: None)
    monkeypatch.setattr(process.subprocess, "Popen", lambda *_a, **_k: SimpleNamespace(pid=42))
    original = Path.write_bytes
    def write(path, data):
        if path.suffix == ".tmp":
            raise PermissionError("acknowledgement unavailable")
        return original(path, data)
    monkeypatch.setattr(Path, "write_bytes", write)
    monkeypatch.setattr(sys, "argv", ["worker", str(error), "vendor"])
    assert process.main() == 1
    assert json.loads(error.read_bytes())["launched"] is True
    assert process._launch_error(error).launched is True



def test_contained_entrance_inherits_binary_streams_and_exit_status(tmp_path):
    payload = bytes(range(256)) * 100
    child = "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read()); sys.stderr.buffer.write(bytes([255])+b'diagnostic'); sys.exit(7)"
    caller = (f"import sys, time; sys.path.insert(0, {str(Path(process.__file__).parent)!r}); "
              "from seat_process import run_inherited_process; "
              f"result=run_inherited_process([sys.executable, '-c', {child!r}], "
              f"cwd={str(tmp_path)!r}, timeout=20, cleanup_deadline=time.monotonic()+21); "
              "sys.exit(result.returncode)")
    result = subprocess.run([sys.executable, "-c", caller], input=payload,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=tmp_path, timeout=30)
    assert result.returncode == 7 and result.stdout == payload
    assert result.stderr == b"\xffdiagnostic"

"""Capture a seat while keeping its descendants inside the attempt lifetime."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time

# The isolated Windows worker does not inherit the script directory on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from winio import utf8_stdio


def _join_kill_on_close_job():
    """Join a worker-owned Windows job before starting any vendor process."""
    import ctypes
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
            ("flags", wintypes.DWORD), ("minimum_working_set", ctypes.c_size_t),
            ("maximum_working_set", ctypes.c_size_t), ("active_processes", wintypes.DWORD),
            ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
            ("scheduling", wintypes.DWORD),
        ]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("basic", BasicLimits), ("io_counters", ctypes.c_ulonglong * 6),
            ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
            ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([wintypes.LPVOID, wintypes.LPCWSTR], wintypes.HANDLE),
        "SetInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD], wintypes.BOOL),
        "AssignProcessToJobObject": ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
        "GetCurrentProcess": ([], wintypes.HANDLE),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = arguments, result
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = ExtendedLimits()
    limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway.
    if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
        raise ctypes.WinError(ctypes.get_last_error())
    # This worker owns the sole non-inherited handle. Its exit (including a
    # timeout kill) closes it and stops the job. Closing it here kills us too.
    return handle


def _worker(command):
    _join_kill_on_close_job()
    return subprocess.run(command, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr).returncode


def _buffered_process(command, *, input, cwd, timeout, env=None):
    """Return captured bytes or raise after terminating the owned process tree."""
    if os.name == "nt":
        with tempfile.TemporaryDirectory(prefix="tradecraft-launch-") as temporary:
            failure = Path(temporary) / "launch-error.json"
            worker = [sys.executable, "-I", "-S", str(Path(__file__).resolve()), str(failure), *command]
            result = subprocess.run(worker, input=input, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, cwd=cwd, timeout=timeout, env=env)
            if failure.exists():
                error = json.loads(failure.read_bytes())
                kind = FileNotFoundError if error["missing"] else OSError
                raise kind(error["message"])
            return subprocess.CompletedProcess(command, result.returncode, result.stdout, result.stderr)
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, env=env, start_new_session=True) as process:
        def stop_tree():
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            stdout, stderr = process.communicate(input, timeout=timeout)
        except subprocess.TimeoutExpired as initial:
            stop_tree()
            try:
                stdout, stderr = process.communicate(timeout=0.25)
            except subprocess.TimeoutExpired as drain:
                # A descendant can leave the group with setsid() while keeping
                # our pipes. Bound cleanup without discarding received bytes.
                stdout = drain.output if drain.output is not None else initial.output or b""
                stderr = drain.stderr if drain.stderr is not None else initial.stderr or b""
                for stream in (process.stdin, process.stdout, process.stderr):
                    stream.close()
            raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr) from None
        finally:
            stop_tree()
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _windows_pipe_reader(process, ended):
    """Read only available bytes; never leave a synchronous pipe read pending."""
    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.PeekNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                                    wintypes.LPVOID, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel.PeekNamedPipe.restype = wintypes.BOOL
    streams = [(name, getattr(process, name)) for name in ("stdout", "stderr")]
    handles = {name: msvcrt.get_osfhandle(stream.fileno()) for name, stream in streams}
    def read_event(timeout):
        for name, stream in streams:
            if name in ended:
                continue
            available = wintypes.DWORD()
            if not kernel.PeekNamedPipe(handles[name], None, 0, None, ctypes.byref(available), None):
                error = ctypes.get_last_error()
                if error in (109, 232):  # Broken pipe / no data: all writers closed.
                    return name, None
                raise ctypes.WinError(error)
            if available.value:
                # Only this thread reads; bytes reported by PeekNamedPipe cannot
                # disappear before this read. Alternate streams to avoid starvation.
                streams.reverse()
                return name, os.read(stream.fileno(), min(available.value, 65536))
        if timeout:
            time.sleep(timeout)
        raise queue.Empty
    return read_event


def run_process(command, *, input, cwd, timeout, on_output=None, on_tick=None,
                on_launch=None, env=None, cleanup_deadline=None):
    """Drain both pipes while input is supplied independently of the deadline.

    Callbacks run serially on the calling thread. A blocked stdin or silent
    descendant therefore cannot prevent capture or elapsed checkpoints.
    """
    if on_output is None and on_tick is None and on_launch is None and cleanup_deadline is None:
        return _buffered_process(command, input=input, cwd=cwd, timeout=timeout, env=env)
    deadline = time.monotonic() + timeout
    with tempfile.TemporaryDirectory(prefix="tradecraft-launch-") as temporary:
        failure = Path(temporary) / "launch-error.json"
        worker = ([sys.executable, "-I", "-S", str(Path(__file__).resolve()),
                   str(failure), *command] if os.name == "nt" else command)
        process = subprocess.Popen(
            worker, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd=cwd, env=env, bufsize=0,
            start_new_session=os.name != "nt",
        )
        events = queue.Queue()
        captured = {"stdout": bytearray(), "stderr": bytearray()}

        def drain(name):
            try:
                while chunk := os.read(getattr(process, name).fileno(), 65536):
                    events.put((name, chunk))
            except (OSError, ValueError):
                pass
            finally:
                # The reader owns closure; a descendant can retain this pipe
                # after bounded cleanup ends. Never close its pending read from
                # the deadline thread.
                getattr(process, name).close()
                events.put((name, None))

        def supply():
            try:
                view = memoryview(input)
                while view:
                    written = process.stdin.write(view)
                    view = view[written:]
            except (BrokenPipeError, OSError, ValueError):
                pass
            finally:
                process.stdin.close()

        def stop_tree():
            if os.name == "nt":
                if process.poll() is None:
                    process.kill()  # Worker closes its kill-on-close job.
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

        ended = set()
        stopped = False
        drain_deadline = None

        def drain_end(current):
            end = current + 0.25
            return min(end, cleanup_deadline) if cleanup_deadline is not None else end

        try:
            if os.name == "nt":
                # Thread.start itself waits for its new thread to be scheduled.
                # Poll Windows pipes in the deadline thread, including short Git
                # probes, instead of spending their reserve starting blocked readers.
                threads = []
                read_event = _windows_pipe_reader(process, ended)
            else:
                threads = [threading.Thread(target=drain, args=(name,), daemon=True)
                           for name in captured]
                read_event = events.get
            if input:
                threads.append(threading.Thread(target=supply, daemon=True))
            else:
                process.stdin.close()
            if on_launch:
                on_launch(process.pid)
            for thread in threads:
                thread.start()
            while len(ended) < 2 or process.poll() is None:
                current = time.monotonic()
                if current >= deadline and not stopped:
                    stopped = True
                    stop_tree()
                    drain_deadline = drain_end(current)
                # Even a normally exited parent may leave inherited pipes open.
                if process.poll() is not None and drain_deadline is None:
                    stop_tree()
                    drain_deadline = drain_end(current)
                if drain_deadline is not None and current >= drain_deadline:
                    break
                if on_tick and not stopped:
                    on_tick()
                # A checkpoint can consume the remaining allowance. Recheck
                # after it instead of renewing a wait using the earlier clock.
                current = time.monotonic()
                if not stopped and current >= deadline:
                    continue
                wait_end = drain_deadline if drain_deadline is not None else deadline
                if current >= wait_end:
                    break
                try:
                    name, chunk = read_event(timeout=min(0.05, wait_end - current))
                except queue.Empty:
                    continue
                if chunk is None:
                    ended.add(name)
                else:
                    captured[name].extend(chunk)
                    if on_output:
                        on_output(name, chunk)
            # Retain queued bytes at the bounded drain's edge too.
            while not events.empty():
                if drain_deadline is not None and time.monotonic() >= drain_deadline:
                    break
                name, chunk = events.get_nowait()
                if chunk is not None:
                    captured[name].extend(chunk)
                    if on_output:
                        on_output(name, chunk)
        finally:
            stop_tree()
            # Draining and waiting share one allowance, rather than adding a
            # fresh wait after the drain or after the caller's cleanup deadline.
            wait_end = drain_deadline if drain_deadline is not None else drain_end(time.monotonic())
            try:
                process.wait(timeout=max(0, wait_end - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
            if os.name == "nt":
                # Polling leaves no outstanding read to make close wait for EOF.
                process.stdout.close()
                process.stderr.close()
            # POSIX reader threads close their own handles once reads finish.
            # Never acquire their close/read lock after the drain has expired.
        stdout, stderr = bytes(captured["stdout"]), bytes(captured["stderr"])
        if stopped:
            raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
        if failure.exists():
            error = json.loads(failure.read_bytes())
            kind = FileNotFoundError if error["missing"] else OSError
            raise kind(error["message"])
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def main():
    utf8_stdio()
    failure = Path(sys.argv[1])
    try:
        return _worker(sys.argv[2:])
    except OSError as exc:
        failure.write_bytes(json.dumps({"missing": isinstance(exc, FileNotFoundError), "message": str(exc)}).encode("utf-8"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

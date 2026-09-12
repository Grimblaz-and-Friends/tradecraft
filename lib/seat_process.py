"""Capture a seat while keeping its descendants inside the attempt lifetime."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

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


def run_process(command, *, input, cwd, timeout):
    """Return captured bytes or raise after terminating the owned process tree."""
    if os.name == "nt":
        with tempfile.TemporaryDirectory(prefix="tradecraft-launch-") as temporary:
            failure = Path(temporary) / "launch-error.json"
            worker = [sys.executable, "-I", "-S", str(Path(__file__).resolve()), str(failure), *command]
            result = subprocess.run(worker, input=input, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, cwd=cwd, timeout=timeout)
            if failure.exists():
                error = json.loads(failure.read_bytes())
                kind = FileNotFoundError if error["missing"] else OSError
                raise kind(error["message"])
            return subprocess.CompletedProcess(command, result.returncode, result.stdout, result.stderr)
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, start_new_session=True) as process:
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

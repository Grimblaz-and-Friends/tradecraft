"""Pause only a fixture's Windows tree before its external, noncooperative kill."""
from contextlib import contextmanager
import os

import run_lifecycle as lifecycle


@contextmanager
def frozen_tree(pid):
    """Keep waiting parents from exiting between taskkill's descendant kills.

    SuspendThread runs no recipient code. Hold the process/thread handles until
    the kill returns; resume our suspension on failure before ordinary cleanup.
    The caller must already have synchronized on its blocked fixture.
    """
    if os.name != "nt":
        yield []
        return
    import ctypes
    from ctypes import wintypes

    class ProcessEntry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD),
                    ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t),
                    ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                    ("parent", wintypes.DWORD), ("priority", wintypes.LONG),
                    ("flags", wintypes.DWORD), ("name", wintypes.WCHAR * 260)]

    class ThreadEntry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD),
                    ("tid", wintypes.DWORD), ("pid", wintypes.DWORD),
                    ("priority", wintypes.LONG), ("delta", wintypes.LONG),
                    ("flags", wintypes.DWORD)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateToolhelp32Snapshot": ([wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
        "Process32FirstW": ([wintypes.HANDLE, ctypes.POINTER(ProcessEntry)], wintypes.BOOL),
        "Process32NextW": ([wintypes.HANDLE, ctypes.POINTER(ProcessEntry)], wintypes.BOOL),
        "Thread32First": ([wintypes.HANDLE, ctypes.POINTER(ThreadEntry)], wintypes.BOOL),
        "Thread32Next": ([wintypes.HANDLE, ctypes.POINTER(ThreadEntry)], wintypes.BOOL),
        "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
        "OpenThread": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
        "SuspendThread": ([wintypes.HANDLE], wintypes.DWORD),
        "ResumeThread": ([wintypes.HANDLE], wintypes.DWORD),
        "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
    }
    for name, (arguments, result) in signatures.items():
        getattr(kernel, name).argtypes = arguments
        getattr(kernel, name).restype = result

    def entries(flag, entry_type, first, following, fields):
        handle = kernel.CreateToolhelp32Snapshot(flag, 0)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = entry_type()
            entry.size = ctypes.sizeof(entry)
            found = first(handle, ctypes.byref(entry))
            rows = []
            while found:
                rows.append(tuple(getattr(entry, field) for field in fields))
                entry.size = ctypes.sizeof(entry)
                found = following(handle, ctypes.byref(entry))
            if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                raise ctypes.WinError(ctypes.get_last_error())
            return rows
        finally:
            kernel.CloseHandle(handle)

    processes, threads, identities, older = [], [], {}, set()

    def pause(target, parent=None):
        assert target != os.getpid(), "The fixture cannot suspend its test runner."
        handle = kernel.OpenProcess(0x101000, False, target)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        processes.append(handle)
        identity = lifecycle.process_identity(target)
        if parent is not None and int(identity["birth"]) < int(identities[parent]["birth"]):
            # Windows retains parent IDs after an exit. A reused PID does not
            # make an older orphan part of this newly launched fixture.
            older.add(target)
            return
        owned = [tid for tid, owner in entries(
            4, ThreadEntry, kernel.Thread32First, kernel.Thread32Next, ("tid", "pid")
        ) if owner == target]
        assert owned, f"Fixture process {target} exited before suspension."
        for tid in owned:
            thread = kernel.OpenThread(0x2, False, tid)  # THREAD_SUSPEND_RESUME
            if not thread:
                raise ctypes.WinError(ctypes.get_last_error())
            if kernel.SuspendThread(thread) == 0xFFFFFFFF:
                error = ctypes.get_last_error()
                kernel.CloseHandle(thread)
                raise ctypes.WinError(error)
            threads.append(thread)
        assert lifecycle.liveness({"launcher_process": identity}) == "active", identity
        identities[target] = identity

    try:
        pause(pid)
        # Freeze parents first, then discover children again. A paused parent
        # cannot spawn another generation or react to a child's termination.
        while True:
            children = [(child, parent) for child, parent in entries(
                2, ProcessEntry, kernel.Process32FirstW, kernel.Process32NextW, ("pid", "parent")
            ) if parent in identities and child not in identities and child not in older]
            if not children:
                break
            for child, parent in children:
                pause(child, parent)
        yield list(identities.values())
    finally:
        for thread in reversed(threads):
            kernel.ResumeThread(thread)
            kernel.CloseHandle(thread)
        for process in processes:
            kernel.CloseHandle(process)

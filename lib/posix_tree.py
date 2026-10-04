"""Reap Linux session-escaping descendants; report unproved containment elsewhere."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import time


class Descendants:
    def __init__(self):
        self.available = False
        self.baseline = set()
        if not Path("/proc/self/task").is_dir():
            return
        try:
            import ctypes
            libc = ctypes.CDLL(None, use_errno=True)
            # Orphans from this invocation reparent here even after setsid().
            # This stays in the caller's process tree, without a supervisor.
            if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
                return
            self.baseline = self.children()
            self.available = True
        except (AttributeError, OSError, ValueError):
            pass

    def children(self):
        children = set()
        for task in Path("/proc/self/task").iterdir():
            try:
                children.update(map(int, (task / "children").read_bytes().split()))
            except FileNotFoundError:
                continue  # A reader thread exited while enumerating tasks.
        return children

    def kill(self):
        if not self.available:
            return False
        try:
            for pid in self.children() - self.baseline:
                try:
                    # pidfd pins the process across the scan/kill race.
                    fd = os.pidfd_open(pid)
                    try:
                        signal.pidfd_send_signal(fd, signal.SIGKILL)
                    finally:
                        os.close(fd)
                except ProcessLookupError:
                    pass
            return True
        except (AttributeError, OSError, ValueError):
            self.available = False
            return False

    def finish(self, end):
        if not self.kill():
            return False
        while True:
            try:
                children = self.children() - self.baseline
                live = []
                for pid in children:
                    try:
                        fields = Path(f"/proc/{pid}/stat").read_bytes().rsplit(b")", 1)[1].split()
                        if fields[0] == b"Z":
                            os.waitpid(pid, os.WNOHANG)
                        else:
                            live.append(pid)
                    except (FileNotFoundError, ChildProcessError):
                        pass
                if not live:
                    return True
                if time.monotonic() >= end:
                    return False
                self.kill()  # A killed escapee can leave another adopted child.
                time.sleep(min(0.005, max(0, end - time.monotonic())))
            except (OSError, ValueError, IndexError):
                return False

"""Portable checks for bounded descendant proof; real setsid tests live beside the runner."""
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import posix_tree


def test_adopted_grandchildren_are_killed_without_touching_existing_children(monkeypatch):
    owned = {101}
    killed = []
    guard = posix_tree.Descendants.__new__(posix_tree.Descendants)
    guard.available, guard.baseline = True, {7}
    guard.children = lambda: {7} | owned
    def kill(pid, _signal):
        killed.append(pid)
        owned.discard(pid)
        if pid == 101:
            owned.add(102)
    monkeypatch.setattr(posix_tree, "os", SimpleNamespace(pidfd_open=lambda pid: pid,
        close=lambda _fd: None, waitpid=lambda *_a: None, WNOHANG=1))
    monkeypatch.setattr(posix_tree, "signal", SimpleNamespace(pidfd_send_signal=kill, SIGKILL=9))
    monkeypatch.setattr(posix_tree, "Path", lambda _p: SimpleNamespace(read_bytes=lambda: b"name) R"))
    assert guard.finish(posix_tree.time.monotonic() + 1)
    assert killed == [101, 102] and owned == set()


def test_failed_descendant_inspection_is_unproved(monkeypatch):
    guard = posix_tree.Descendants.__new__(posix_tree.Descendants)
    guard.available, guard.baseline = True, set()
    def unreadable():
        raise PermissionError("cannot enumerate adopted descendants")
    guard.children = unreadable
    assert guard.finish(posix_tree.time.monotonic() + 1) is False


def test_live_descendant_does_not_renew_cleanup_allowance(monkeypatch):
    guard = posix_tree.Descendants.__new__(posix_tree.Descendants)
    guard.available, guard.baseline = True, set()
    guard.children = lambda: {101}
    monkeypatch.setattr(posix_tree, "os", SimpleNamespace(pidfd_open=lambda pid: pid,
        close=lambda _fd: None))
    monkeypatch.setattr(posix_tree, "signal", SimpleNamespace(pidfd_send_signal=lambda *_a: None, SIGKILL=9))
    monkeypatch.setattr(posix_tree, "Path", lambda _p: SimpleNamespace(read_bytes=lambda: b"name) R"))
    assert guard.finish(posix_tree.time.monotonic() - 1) is False

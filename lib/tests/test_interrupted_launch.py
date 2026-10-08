import json
from contextlib import nullcontext
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_lifecycle as lifecycle
import work
from test_work import state, registry_row, MECHANICAL
from fixtures.frozen_tree import FrozenTree, frozen_tree

LIB = Path(__file__).resolve().parents[1]


def exit_clock():
    """Measure Windows process exit, independently of the observer's scheduling."""
    if os.name != "nt":
        return lambda child, started: time.monotonic() - started
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetSystemTimePreciseAsFileTime.argtypes = [ctypes.POINTER(wintypes.FILETIME)]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    anchors = []
    for _ in range(3):
        anchor = wintypes.FILETIME()
        kernel.GetSystemTimePreciseAsFileTime(ctypes.byref(anchor))
        # Each later monotonic reading is an upper bound. Pick the tightest
        # calibration so a descheduled observer cannot enlarge that bound.
        monotonic = time.monotonic()
        ticks = anchor.dwHighDateTime << 32 | anchor.dwLowDateTime
        anchors.append((monotonic, ticks))
    anchor_monotonic, anchor_ticks = min(anchors, key=lambda pair: pair[0] - pair[1] / 10000000)
    def elapsed(child, started):
        assert child.returncode is not None, "The launcher must have exited."
        values = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(int(child._handle), *(ctypes.byref(v) for v in values)):
            raise ctypes.WinError(ctypes.get_last_error())
        exit_ticks = values[1].dwHighDateTime << 32 | values[1].dwLowDateTime
        assert exit_ticks > anchor_ticks
        return anchor_monotonic - started + (exit_ticks - anchor_ticks) / 10000000
    return elapsed


@pytest.mark.skipif(os.name != "nt", reason="Windows native process exit timestamp")
def test_exit_clock_excludes_delay_after_the_launcher_has_exited(tmp_path):
    elapsed = exit_clock()
    started = time.monotonic()
    with subprocess.Popen([sys.executable, "-c", "pass"], cwd=tmp_path,
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:
        child.communicate(timeout=10)
        measured = elapsed(child, started)
        observed_exit = time.monotonic()
        time.sleep(0.2)
        assert elapsed(child, started) == measured
        assert time.monotonic() - observed_exit >= 0.19


def kill_tree(tree):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.TerminateProcess.restype = wintypes.BOOL
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        failures = []
        for identity in tree:
            pid = identity["pid"]
            handle = tree.handles[pid]
            terminated = kernel.TerminateProcess(handle, 1)
            error = ctypes.get_last_error() if not terminated else 0
            waited = kernel.WaitForSingleObject(handle, 5000)
            if waited == 0xFFFFFFFF:  # WAIT_FAILED
                error = ctypes.get_last_error()
            elif waited != 0 and not error:
                error = waited
            if waited != 0:
                failures.append({"pid": pid, "windows_error": error, "wait_result": waited})
        assert not failures, failures
    else:
        pid = tree.pid
        snapshot = subprocess.run(["ps", "-eo", "pid=,ppid="],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, check=True).stdout
        pairs = [tuple(map(int, row.split())) for row in snapshot.splitlines()]
        owned = {pid}
        while descendants := {child for child, parent in pairs if parent in owned} - owned:
            owned.update(descendants)
        for child in owned:
            try:
                os.kill(child, signal.SIGKILL)
            except ProcessLookupError:
                pass


def hard_kill_blocked_launch(process, saved, identities):
    """An exited launcher is a failed setup, never a successful hard kill."""
    assert process.poll() is None, {"error": "launcher exited before hard kill", "run": saved}
    assert saved.get("session_identity", {}).get("session_id"), "Session was not durably recorded."
    assert not saved.get("completed_at"), "Launcher completed before hard kill."
    assert all(lifecycle.liveness({"launcher_process": identity}) == "active"
               for identity in identities), "The fixture was no longer blocked."
    with frozen_tree(process.pid) as frozen:
        if os.name == "nt":
            assert saved["launcher_process"] in frozen, "The recorded writer was outside the killed tree."
            assert all(identity in frozen for identity in identities), "Blocked descendants left the tree."
        kill_tree(frozen)
        process.wait(timeout=5)
        return frozen


@pytest.mark.parametrize("failure", ["exited", "missing-session", "completed", "dead-descendant"])
def test_hard_kill_refuses_unproved_setup(monkeypatch, failure):
    class Process:
        pid = 123

        def poll(self):
            return 1 if failure == "exited" else None

    saved = {"session_identity": {"session_id": "observed-session"}, "launcher_process": {"pid": 123}}
    if failure == "missing-session":
        saved["session_identity"] = {}
    if failure == "completed":
        saved["completed_at"] = "2026-10-03T00:00:00Z"
    monkeypatch.setattr(lifecycle, "liveness", lambda *_: "stopped" if failure == "dead-descendant" else "active")
    monkeypatch.setattr(sys.modules[__name__], "frozen_tree", lambda *_: nullcontext([{"pid": 123}, {"pid": 456}]))
    monkeypatch.setattr(sys.modules[__name__], "kill_tree", lambda *_: pytest.fail("An unproved setup was killed."))
    with pytest.raises(AssertionError):
        hard_kill_blocked_launch(Process(), saved, [{"pid": 456}])


@pytest.mark.skipif(os.name != "nt", reason="Windows native tree termination")
def test_native_tree_kill_uses_each_held_handle_and_waits(monkeypatch):
    import ctypes
    identities = [{"pid": pid, "birth": str(pid)} for pid in (123, 456, 789)]
    tree = FrozenTree(123, identities, {123: 101, 456: 202, 789: 303})
    calls = []

    def terminate(handle, code):
        calls.append(("terminate", handle, code))
        return True

    def wait(handle, timeout):
        calls.append(("wait", handle, timeout))
        return 0

    kernel = SimpleNamespace(TerminateProcess=terminate, WaitForSingleObject=wait)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_a, **_k: kernel)
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: pytest.fail("The kill must use held handles."))
    kill_tree(tree)
    assert calls == [(operation, handle, value) for handle in (101, 202, 303)
                     for operation, value in (("terminate", 1), ("wait", 5000))]
    assert tree == identities
    assert all(actual is expected for actual, expected in zip(tree, identities))


@pytest.mark.skipif(os.name != "nt", reason="Windows native tree termination")
def test_native_tree_kill_accepts_already_exited_member_on_signalled_handle(monkeypatch):
    import ctypes
    calls = []

    def wait(handle, timeout):
        calls.append((handle, timeout))
        return 0

    kernel = SimpleNamespace(TerminateProcess=lambda *_: False, WaitForSingleObject=wait)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_a, **_k: kernel)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 5)
    kill_tree(FrozenTree(123, [{"pid": 123}], {123: 456}))
    assert calls == [(456, 5000)]


@pytest.mark.skipif(os.name != "nt", reason="Windows native tree termination diagnostics")
@pytest.mark.parametrize("operation, error", [("terminate", 5), ("wait", 6), ("timeout", 258)])
def test_native_tree_kill_failure_names_pid_and_windows_error(monkeypatch, operation, error):
    import ctypes
    # Fake a failed native terminate with a live process, a failed wait, or a
    # timed-out wait after successful termination; none proves the process died.
    kernel = SimpleNamespace(
        TerminateProcess=lambda *_: operation != "terminate",
        WaitForSingleObject=lambda *_: 0xFFFFFFFF if operation == "wait" else 258,
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_a, **_k: kernel)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error)
    with pytest.raises(AssertionError) as failure:
        kill_tree(FrozenTree(123, [{"pid": 123}], {123: 456}))
    assert "'pid': 123" in str(failure.value)
    assert f"'windows_error': {error}" in str(failure.value)


@pytest.mark.skipif(os.name != "nt", reason="Windows native tree termination diagnostics")
@pytest.mark.parametrize("failed_handles", [(101,), (101, 303)], ids=["first-fails", "two-fail"])
def test_native_tree_kill_attempts_later_members_before_reporting_failures(monkeypatch, failed_handles):
    import ctypes
    tree = FrozenTree(123, [{"pid": pid} for pid in (123, 456, 789)], {123: 101, 456: 202, 789: 303})
    calls = []
    errors = {101: 5, 303: 6}
    last_error = [0]

    def terminate(handle, code):
        calls.append(("terminate", handle, code))
        last_error[0] = errors[handle] if handle in failed_handles else 0
        return handle not in failed_handles

    def wait(handle, timeout):
        calls.append(("wait", handle, timeout))
        return 258 if handle in failed_handles else 0

    kernel = SimpleNamespace(TerminateProcess=terminate, WaitForSingleObject=wait)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_a, **_k: kernel)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: last_error[0])
    with pytest.raises(AssertionError) as failure:
        kill_tree(tree)
    assert calls == [(operation, handle, value) for handle in (101, 202, 303)
                     for operation, value in (("terminate", 1), ("wait", 5000))]
    message = str(failure.value)
    assert "'pid': 123" in message and "'windows_error': 5" in message
    assert "'pid': 456" not in message
    if 303 in failed_handles:
        assert "'pid': 789" in message and "'windows_error': 6" in message
    else:
        assert "'pid': 789" not in message


@pytest.mark.skipif(os.name != "nt", reason="Windows held process handles")
@pytest.mark.parametrize("older_child, deny_terminate", [(False, False), (True, False), (True, True)],
                         ids=["owned-child", "stale-parent-id", "older-terminate-denied"])
def test_frozen_tree_carries_only_owned_process_handles(tmp_path, monkeypatch, older_child, deny_terminate):
    import ctypes
    from ctypes import wintypes
    ready = tmp_path / "ready"
    code = ("import subprocess,sys,time; from pathlib import Path; "
            "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(90)'], "
            "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
            "ready=Path(sys.argv[1]); staged=ready.with_suffix('.pending'); "
            "staged.write_bytes(str(child.pid).encode()); staged.replace(ready); time.sleep(90)")
    process = subprocess.Popen([sys._base_executable, "-c", code, str(ready)],
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    child = None
    identities = {}
    read_identity = lifecycle.process_identity
    if deny_terminate:
        native = ctypes.WinDLL("kernel32", use_last_error=True)
        native.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        native.OpenProcess.restype = wintypes.HANDLE

        class Kernel:
            def __getattr__(self, name):
                return getattr(native, name)

        def open_process(access, inherit, pid):
            if deny_terminate and pid == child and access & 1:
                ctypes.set_last_error(5)
                return None
            return native.OpenProcess(access, inherit, pid)

        kernel = Kernel()
        kernel.OpenProcess = open_process
        monkeypatch.setattr(ctypes, "WinDLL", lambda *_a, **_k: kernel)

    def identity(pid):
        value = read_identity(pid)
        if older_child and pid == child:
            value["birth"] = "0"
        identities.setdefault(pid, value)
        return value

    monkeypatch.setattr(lifecycle, "process_identity", identity)
    try:
        until = time.monotonic() + 10
        while not ready.exists() and process.poll() is None and time.monotonic() < until:
            time.sleep(0.05)
        assert ready.exists(), "The fixture never became ready."
        child = int(ready.read_text())
        if deny_terminate:
            assert not kernel.OpenProcess(0x101001, False, child)
            assert ctypes.get_last_error() == 5
            identity(child)  # Retain its identity even if the pre-fix freeze raises.
        with frozen_tree(process.pid) as frozen:
            expected = {process.pid} if older_child else {process.pid, child}
            assert set(frozen.handles) == expected
            assert {member["pid"] for member in frozen} == expected
            assert all(member is identities[member["pid"]] for member in frozen)
            assert frozen == [identities[member["pid"]] for member in frozen]
            kill_tree(frozen)
        process.communicate(timeout=5)
        if older_child:
            assert lifecycle.liveness({"launcher_process": identities[child]}) == "active"
    finally:
        deny_terminate = False  # Ordinary teardown owns this simulated orphan.
        if child is not None and lifecycle.liveness({"launcher_process": identities.get(child)}) == "active":
            with frozen_tree(child) as frozen:
                kill_tree(frozen)
        if process.poll() is None:
            with frozen_tree(process.pid) as frozen:
                kill_tree(frozen)
        process.communicate(timeout=5)


@pytest.mark.skipif(os.name != "nt" or sys.executable == sys._base_executable,
                    reason="Windows virtual-environment waiting-bootstrap race")
@pytest.mark.parametrize("older_child", [False, True], ids=["owned-child", "stale-parent-id"])
def test_frozen_parent_cannot_exit_after_its_child_is_terminated(tmp_path, monkeypatch, older_child):
    import ctypes
    from ctypes import wintypes
    ready = tmp_path / "ready"
    code = ("import json,os,sys,threading,time; from pathlib import Path; "
            "ready=Path(sys.argv[1]); staged=ready.with_suffix('.pending'); "
            "staged.write_bytes(json.dumps({'pid':os.getpid(),'tid':threading.get_native_id()}).encode()); "
            "os.replace(staged,ready); time.sleep(90)")
    process = subprocess.Popen([sys.executable, "-c", code, str(ready)],
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=subprocess.HIGH_PRIORITY_CLASS)
    try:
        until = time.monotonic() + 10
        while not ready.exists() and process.poll() is None and time.monotonic() < until:
            time.sleep(0.05)
        assert ready.exists(), "The native child never became ready."
        child_info = json.loads(ready.read_bytes())
        child = child_info["pid"]
        # A Windows virtual environment has a waiting native bootstrap.
        assert child != process.pid
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenThread.restype = wintypes.HANDLE
        kernel.SuspendThread.argtypes = [wintypes.HANDLE]
        kernel.SuspendThread.restype = wintypes.DWORD
        kernel.ResumeThread.argtypes = [wintypes.HANDLE]
        if older_child:
            read_identity = lifecycle.process_identity

            def stale_parent_id(pid):
                identity = read_identity(pid)
                if pid == child:
                    identity["birth"] = "0"
                return identity

            monkeypatch.setattr(lifecycle, "process_identity", stale_parent_id)
        with frozen_tree(process.pid) as frozen:
            expected = {process.pid} if older_child else {process.pid, child}
            assert {identity["pid"] for identity in frozen} == expected
            thread = kernel.OpenThread(0x2, False, child_info["tid"])
            assert thread
            try:
                previous = kernel.SuspendThread(thread)
                assert previous != 0xFFFFFFFF
                kernel.ResumeThread(thread)
                assert previous == (0 if older_child else 1)
            finally:
                kernel.CloseHandle(thread)
            handle = kernel.OpenProcess(0x100001, False, child)
            assert handle
            try:
                assert kernel.TerminateProcess(handle, 1)
                assert kernel.WaitForSingleObject(handle, 5000) == 0
                time.sleep(0.1)
                assert process.poll() is None, "The waiting parent escaped the remaining frozen tree."
            finally:
                kernel.CloseHandle(handle)
            kill_tree(frozen)
            process.communicate(timeout=5)
    finally:
        if process.poll() is None:
            with frozen_tree(process.pid) as frozen:
                kill_tree(frozen)
        process.communicate(timeout=5)


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE).stdout


@pytest.mark.parametrize("kind", ["implementer", "seat"])
@pytest.mark.parametrize("vendor", ["codex", "claude"])
@pytest.mark.parametrize("termination", ["hard-kill", "ceiling", "ceiling-slow-final-probe"])
def test_hard_killed_real_launcher_keeps_session_and_output(tmp_path, monkeypatch, record_property, kind, vendor, termination):
    root = tmp_path / "tree"
    root.mkdir()
    git(root, "init")
    git(root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.test",
        "commit", "--allow-empty", "-m", "Fixture")
    holder = root
    branch = git(root, "symbolic-ref", "--short", "HEAD").decode().strip()
    if kind == "implementer":
        root = tmp_path / "builder"
        branch = "change"
        git(holder, "worktree", "add", "-b", branch, str(root))
    if kind == "seat":
        git(root, "checkout", "--detach")
    # This fixture never edits its tree. Capture it once; content-change and
    # snapshot-deadline contracts have separate executable tests.
    snapshot = lifecycle.content_snapshot(root)
    assert snapshot["digest"]
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_bytes(json.dumps(snapshot).encode())
    monkeypatch.setattr(lifecycle, "content_snapshot", lambda *_a, **_k: dict(snapshot))
    dispatch = tmp_path / "dispatch"
    prompt = b"Perform this stage and return.\n"
    if kind == "seat":
        prompt = b"<!-- tradecraft:artifact:v1 status=draft -->\n" + prompt
    dispatch.write_bytes(prompt)
    store = tmp_path / "vendor-state"
    store.mkdir()
    (store / "nonce").write_bytes(b"retained-before-hard-kill")
    output = tmp_path / "bundle" / "return"
    ceiling = termination.startswith("ceiling")
    # Keep one native deadline per launcher, including a real slow final probe.
    # Five seconds remain for startup after the production ten-second reserve.
    production_ceiling = (termination, kind, vendor) in {
        ("ceiling", "implementer", "claude"),
        ("ceiling-slow-final-probe", "seat", "codex"),
    }
    caller_limit = 15 if production_ceiling else 60
    command = [sys._base_executable, str(LIB / "tests/fixtures/interrupted_launcher.py"), kind, vendor, str(store),
               "--dispatch", str(dispatch), "--root", str(root), "--vendor", vendor,
               "--work", "example/product#12", "--stage", "build" if kind == "implementer" else "cold-seat",
               "--settings-source", "fixture", "--settings-scope", "fixture",
               "--output", str(output), "--timeout-seconds", str(caller_limit),
               "--snapshot-fixture", str(snapshot_path)]
    if termination == "ceiling-slow-final-probe":
        command.append("--slow-final-probe")
    if ceiling and not production_ceiling:
        command.append("--fast-ceiling")
    if kind == "implementer":
        command.extend(["--lineage-branch", branch, "--holder-session-id", "holder-session"])
    if kind == "seat":
        command.extend(["--classification", "cold", "--requires", "read", "--draft-comment", "20",
                        "--own-vendor", "claude" if vendor == "codex" else "codex"])
    measured_exit = exit_clock()
    started = time.monotonic()
    command.extend(["--invocation-started-monotonic", str(started)])
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    run_path = Path(str(output) + ".run.json")
    saved = {}
    try:
        until = time.monotonic() + 60  # Hang guard, never the stop trigger.
        while not (store / "blocked.json").exists() and time.monotonic() < until:
            if process.poll() is not None:
                break
            time.sleep(0.05)
        assert (store / "blocked.json").exists(), process.communicate(timeout=1) if process.poll() is not None else "vendor never reached blocked command"
        identities = json.loads((store / "blocked-identities.json").read_bytes())
        # Wait for the launcher's flush, without giving it a chance to finish.
        while time.monotonic() < until:
            try:
                saved = json.loads(run_path.read_bytes())
                if saved.get("session_identity", {}).get("session_id"):
                    break
            except (OSError, ValueError):
                pass
            if process.poll() is not None:
                break
            time.sleep(0.05)
        if termination == "hard-kill":
            identities.extend(hard_kill_blocked_launch(process, saved, identities))
        else:
            (store / "ceiling-ready").write_bytes(b"ready")
        stdout, stderr = process.communicate(timeout=caller_limit if ceiling else 5)
        if ceiling:
            elapsed = measured_exit(process, started)
            record_property("observer_elapsed_seconds", time.monotonic() - started)
            record_property("launcher_elapsed_seconds", elapsed)
            record_property("caller_limit_seconds", caller_limit)
            record_property("production_reserve", production_ceiling)
            assert elapsed < caller_limit, f"whole invocation took {elapsed:.3f}s against the declared {caller_limit}s limit"
        saved = json.loads(run_path.read_bytes())
        if kind == "seat":
            request = json.loads(Path(str(output) + ".request.json").read_bytes())
            assert saved["judged_draft"] == request["judged_draft"]
            assert saved["judged_draft"]["comment_id"] == "20"
        assert saved["session_identity"]["session_id"] == "0199a213-81c0-7800-8aa1-bbab2a035a53"
        if termination == "hard-kill":
            assert not saved.get("completed_at")
        else:
            assert saved.get("completed_at") and saved["outcome"] == "interrupted", {
                "outcome": saved.get("outcome"), "error": saved.get("error"),
                "stdout": stdout, "stderr": stderr,
                "attempts": [{key: attempt.get(key) for key in ("outcome", "reason", "exit_code")}
                             for attempt in saved["attempts"]],
            }
            assert saved["interruption_cause"] == "ceiling"
            attempt = saved["attempts"][0]
            assert f"caller limit {caller_limit}s" in attempt["reason"]
            assert f"recipient allocation {attempt['allocation_seconds']:.2f}s" in attempt["reason"]
            assert f"measured elapsed {attempt['elapsed_seconds']:.2f}s" in attempt["reason"]
            assert f"timed out after {caller_limit}s" not in attempt["reason"]
        if termination == "ceiling-slow-final-probe":
            assert saved["revision_after"] is None
            if kind == "implementer":
                assert saved["stop_snapshot"]["digest"] is None
                assert saved["stop_snapshot"]["unavailable_reason"]
        assert not output.exists()
        assert Path(saved["attempts"][0]["stdout"]).read_bytes().strip()
        identities.append(saved["launcher_process"])
        until_dead = time.monotonic() + 5
        while time.monotonic() < until_dead and any(lifecycle.liveness({"launcher_process": identity}) != "stopped" for identity in identities):
            time.sleep(0.05)
        assert all(lifecycle.liveness({"launcher_process": identity}) == "stopped" for identity in identities), [
            (identity, lifecycle.liveness({"launcher_process": identity})) for identity in identities]
        assert lifecycle.liveness(saved) == "stopped"
        if kind == "implementer":
            fixture = state(MECHANICAL)
            fixture.record_root, fixture.holder_root = output.parent, holder
            row = registry_row(root, holder, branch)
            monkeypatch.setattr(work, "read_registry", lambda: {"schema_version": 2, "worktrees": [row]})
            monkeypatch.setattr(work, "_selected_runtime_argument", lambda *_a, **_k: [])
            setting = Path.home() / ".tradecraft" / "implementer-vendor"
            setting.parent.mkdir(parents=True, exist_ok=True)
            setting.write_bytes(vendor.encode())
            (store / "nonce").unlink()
            resumed = output.parent / "resumed"
            original_run = subprocess.run
            original_recipient = work._recipient_run
            launches = []
            def launch(command, *args, **kwargs):
                if len(command) > 1 and Path(command[1]).name == "dispatch_implementer.py":
                    launches.append(command)
                    actual = [sys._base_executable, str(LIB / "tests/fixtures/interrupted_launcher.py"),
                              "implementer", vendor, str(store), *command[2:], "--output", str(resumed),
                              "--snapshot-fixture", str(snapshot_path)]
                    return original_recipient(actual, **kwargs)
                return original_run(command, *args, **kwargs)
            monkeypatch.setattr(work, "_recipient_run", launch)
            recommendation = work.decide(fixture, {"schema_version": 1, "rules": []})
            continuity = work._named_continuity(fixture, "build", recommendation)
            assert continuity == "resume"
            decision = work.Decision("build", True, continuity, "holder-named-stage")
            # Give the resumed turn its own useful preflight window under load.
            assert work.execute_stage(fixture, decision, holder, None, "holder-session", timeout_seconds=60) == 0
            assert len(launches) == 1
            assert launches[0][launches[0].index("--resume") + 1] == saved["session_identity"]["session_id"]
            assert b"retained-before-hard-kill" in resumed.read_bytes()
            assert len(list(output.parent.glob("*.run.json"))) == 2
    finally:
        if process.poll() is None:
            with frozen_tree(process.pid) as frozen:
                kill_tree(frozen)
        process.communicate(timeout=5)

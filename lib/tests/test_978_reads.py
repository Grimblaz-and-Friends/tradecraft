"""The read route: one contained process per read, stopped at its bound."""
import ast
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import preflight
import run_lifecycle
import seat_process as process

PYTHON = getattr(sys, "_base_executable", sys.executable)
# The child starts a 60-second grandchild that shares its pipes, records its pid, and sleeps.
PARENT = ("import pathlib, subprocess, sys, time; "
          "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']{streams}); "
          "pathlib.Path(sys.argv[1]).write_text(str(g.pid)); "
          "print('started', flush=True); time.sleep(60)")
SHARED = PARENT.format(streams="")
# A stream's grandchild holds no pipe, so an uncontained stream still reaches its end.
DETACHED = PARENT.format(streams=", stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
                                 "stderr=subprocess.DEVNULL")


def alive(pid):
    try:
        run_lifecycle.process_identity(pid)
    except ProcessLookupError:
        return False
    return True


def gone(pid, within):
    end = time.monotonic() + within
    while alive(pid):
        if time.monotonic() >= end:
            return False
        time.sleep(0.05)
    return True


def kill(pid):
    try:
        os.kill(pid, signal.SIGKILL if hasattr(signal, "SIGKILL") else signal.SIGTERM)
    except (OSError, ProcessLookupError):
        pass


def grandchild(path):
    for _ in range(100):
        if path.is_file() and path.read_text():
            return int(path.read_text())
        time.sleep(0.05)
    pytest.fail("the read never started its grandchild")


def read_until_bound(tmp_path, code, bound=2.0, stream=False):
    pid_file = tmp_path / f"grandchild-{time.monotonic_ns()}"
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        if stream:
            with process.stream_read([PYTHON, "-c", code, str(pid_file)], cwd=tmp_path,
                                     timeout=bound) as read:
                assert read.stdout.readline().strip() == b"started"
                read.stdout.read(1)  # Blocks until the bound stops the tree.
                read.remaining()
        else:
            process.run_read([PYTHON, "-c", code, str(pid_file)], cwd=tmp_path, timeout=bound)
    return time.monotonic() - started, grandchild(pid_file)


@pytest.mark.parametrize("stream", [False, True], ids=["run_read", "stream_read"])
def test_978_read_bound_stops_what_it_started(tmp_path, monkeypatch, stream):
    code = DETACHED if stream else SHARED
    elapsed, pid = read_until_bound(tmp_path, code, stream=stream)
    assert elapsed < 2.0 + 1.5
    assert not alive(pid), "a contained read left its grandchild running"
    # The survival control: without containment the same grandchild outlives the read.
    monkeypatch.setattr(process, "_CONTAIN", False)
    elapsed, pid = read_until_bound(tmp_path, code, stream=stream)
    try:
        assert elapsed < 2.0 + 1.5
        assert alive(pid), "the control's grandchild should have survived an uncontained read"
    finally:
        kill(pid)


@pytest.mark.parametrize("stream", [False, True], ids=["run_read", "stream_read"])
def test_978_read_never_passes_cleanup_end(tmp_path, stream):
    # A 12-second stage two seconds old has its cleanup end five seconds away.
    deadline = run_lifecycle.stage_deadline("build", 12, started=time.monotonic() - 2)
    pid_file = tmp_path / "grandchild"
    code = DETACHED if stream else SHARED
    with run_lifecycle.deadline_scope(deadline):
        with pytest.raises(subprocess.TimeoutExpired):
            if stream:
                with process.stream_read([PYTHON, "-c", code, str(pid_file)], cwd=tmp_path, timeout=30,
                                         cleanup_deadline=run_lifecycle.cleanup_deadline()) as read:
                    read.stdout.readline()
                    read.stdout.read(1)
            else:
                process.run_read([PYTHON, "-c", code, str(pid_file)], cwd=tmp_path, timeout=30,
                                 cleanup_deadline=run_lifecycle.cleanup_deadline())
        returned = time.monotonic()
    pid = grandchild(pid_file)
    try:
        assert returned <= deadline.cleanup_end + 0.1, f"returned {returned - deadline.cleanup_end:.2f}s late"
        # The tree was stopped before the return; a loaded runner may finish its exit just after.
        assert gone(pid, within=1.0)
    finally:
        kill(pid)


def test_978_refused_containment_falls_back(tmp_path, monkeypatch):
    def refused(*_args):
        raise OSError("job assignment refused by the test")
    monkeypatch.setattr(process, "_assign_read", refused)
    through_worker = []
    original = process.run_process
    def recorded(command, **kwargs):
        through_worker.append(kwargs.get("on_tick") is not None)
        return original(command, **kwargs)
    monkeypatch.setattr(process, "run_process", recorded)
    with preflight.scope() as scope:
        # The worker's own start takes a second or more on a loaded Windows runner.
        elapsed, pid = read_until_bound(tmp_path, SHARED, bound=5.0)
        assert elapsed < 5.0 + 1.5
        # The worker's job closes as the worker dies, so its tree goes just after the return.
        assert gone(pid, within=2.0)
        route = scope.read_route()
    if os.name == "nt":
        assert through_worker == [True], "the refused read must take the worker route"
        assert route["fallback"] >= 1 and route["contained"] == 0
        assert any("job assignment refused" in reason for reason in route["fallback_reasons"])
        with preflight.scope() as scope:
            with pytest.raises(process.ContainmentRefused):
                with process.stream_read([PYTHON, "-c", "print(1)"], cwd=tmp_path, timeout=5):
                    pytest.fail("a refused stream ran")
            assert scope.read_route()["fallback"] == 1
    else:
        # POSIX has no second route: the process group is the only one, and nothing falls back.
        assert through_worker == [True]
        assert route == {"contained": 1, "fallback": 0, "fallback_reasons": []}


_AUDIT = {"on": False, "seen": []}


def _audit(event, arguments):
    if event == "subprocess.Popen" and _AUDIT["on"]:
        _AUDIT["seen"].append(arguments)


def test_978_one_process_per_read(tmp_path):
    import dispatch_record
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=60)
    if not getattr(sys, "_tradecraft_978_audit", False):
        sys.addaudithook(_audit)  # Hooks cannot be removed; the flag keeps it silent elsewhere.
        sys._tradecraft_978_audit = True
    deadline = run_lifecycle.stage_deadline("build", 120)
    _AUDIT["seen"].clear()
    _AUDIT["on"] = True
    try:
        with run_lifecycle.deadline_scope(deadline):
            dispatch_record._git_probe(tmp_path, ("rev-parse", "--git-dir"), "utf-8")
    finally:
        _AUDIT["on"] = False
    assert len(_AUDIT["seen"]) == 1, _AUDIT["seen"]
    arguments = _AUDIT["seen"][0][1]
    # Windows audits the joined command line; POSIX audits the argument list.
    first = arguments.split()[0] if isinstance(arguments, str) else os.fsdecode(arguments[0])
    assert first == "git", arguments
    assert Path(first).name != Path(sys.executable).name


# The modules whose processes are the entrance's and its launchers' reads. A start here is
# `run_read` or `stream_read` unless KEPT_ROUTES names it, so a read added on another route fails.
READ_MODULES = ("dispatch_record", "implementer_policy", "launch_bound", "artifact_tree", "cold_draft",
                "recipient_tree", "cloud_build", "work", "run_lifecycle", "dispatch_seat")
KEPT_ROUTES = {
    # Artifact-copy disposal is a child script, not a read.
    ("artifact_tree", "dispose", "run_process"),
    # The landing script near the `--expect-branch` call is not a read.
    ("work", "_execute_catch_up", "run"),
    # The vendor command keeps its route.
    ("cloud_build", "Transport.cli", "run"),
    # The recipient's own launch, with its callbacks.
    ("dispatch_seat", "_run_dispatch", "run_process"),
}


def process_starts(module):
    tree = ast.parse((LIB / f"{module}.py").read_text(encoding="utf-8"))
    found = []

    def visit(node, scope):
        for child in ast.iter_child_nodes(node):
            inner = scope
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                inner = [*scope, child.name]
            if isinstance(child, ast.Call):
                function = child.func
                name = (function.attr if isinstance(function, ast.Attribute)
                        else function.id if isinstance(function, ast.Name) else None)
                bare_run = name == "run" and not (isinstance(function, ast.Attribute)
                                                  and isinstance(function.value, ast.Name)
                                                  and function.value.id == "subprocess")
                if name in ("run", "Popen", "run_process") and not bare_run:
                    found.append((module, ".".join(inner), name, child.lineno))
            visit(child, inner)

    visit(tree, [])
    return found


def test_978_read_sites():
    stray = [f"{module}.py:{line} {where} calls {name}("
             for module in READ_MODULES for module, where, name, line in process_starts(module)
             if (module, where, name) not in KEPT_ROUTES]
    assert not stray, "a read outside run_read or stream_read:\n" + "\n".join(stray)


# The child exits at once, leaving a 60-second grandchild that holds its stdout.
EXITS = ("import pathlib, subprocess, sys; "
         "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
         "stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr{session}); "
         "pathlib.Path(sys.argv[1]).write_text(str(g.pid)); print('child', flush=True)")


def reap(pid):
    kill(pid)
    if os.name != "nt":
        try:
            os.waitpid(pid, 0)  # The subreaper adopted it; leave no zombie for later baselines.
        except ChildProcessError:
            pass


def test_978_read_is_whole_or_refused(tmp_path, monkeypatch):
    command = [PYTHON, "-c", EXITS.format(session=""), str(tmp_path / "contained")]
    # Contained, the job (or process group) stops the grandchild as the child exits, so its pipe closes.
    started = time.monotonic()
    result = process.run_read(command, cwd=tmp_path, timeout=30)
    pid = grandchild(tmp_path / "contained")
    try:
        assert time.monotonic() - started < 10
        assert (result.returncode, result.stdout.strip()) == (0, b"child")
        assert gone(pid, within=1.0)
    finally:
        reap(pid)

    # A holder the stop does not reach: the read refuses its part rather than answering with it.
    if os.name == "nt":
        monkeypatch.setattr(process, "_stop_job", lambda *_args: None)
    else:
        monkeypatch.setattr(process.Descendants, "kill", lambda self: False)
        command = [PYTHON, "-c", EXITS.format(session=", start_new_session=True"), str(tmp_path / "escaped")]
    command[-1] = str(tmp_path / "escaped")
    with pytest.raises(process.ReadCutShort, match="cut short") as raised:
        process.run_read(command, cwd=tmp_path, timeout=30)
    pid = grandchild(tmp_path / "escaped")
    try:
        assert raised.value.output.strip() == b"child" and isinstance(raised.value, OSError)
        if os.name == "nt":
            # Closing the job as the read returns still stops what the read started.
            assert gone(pid, within=1.0)
    finally:
        reap(pid)
    monkeypatch.undo()

    # Uncontained, the grandchild survives with the pipe, and the read still refuses.
    monkeypatch.setattr(process, "_CONTAIN", False)
    command[-1] = str(tmp_path / "uncontained")
    with pytest.raises(process.ReadCutShort):
        process.run_read(command, cwd=tmp_path, timeout=30)
    reap(grandchild(tmp_path / "uncontained"))


def test_978_a_write_that_exited_0_is_done_even_when_its_pipe_was_held(tmp_path, monkeypatch):
    """The same held pipe that refuses a read leaves a write that already happened standing."""
    if os.name == "nt":
        monkeypatch.setattr(process, "_stop_job", lambda *_args: None)
        command = [PYTHON, "-c", EXITS.format(session=""), str(tmp_path / "write")]
    else:
        monkeypatch.setattr(process.Descendants, "kill", lambda self: False)
        command = [PYTHON, "-c", EXITS.format(session=", start_new_session=True"), str(tmp_path / "write")]
    with pytest.raises(process.ReadCutShort):
        process.run_read(command, cwd=tmp_path, timeout=30)
    reap(grandchild(tmp_path / "write"))
    command[-1] = str(tmp_path / "write-done")
    result = process.run_read(command, cwd=tmp_path, timeout=30, writes=True)
    try:
        assert result.returncode == 0 and result.output_complete is False
        assert result.stdout.strip() == b"child"
    finally:
        reap(grandchild(tmp_path / "write-done"))


def test_978_git_writes_are_marked_as_writes(tmp_path, monkeypatch):
    """The cloud route and the recipient tree mark exactly their Git writes as writes."""
    import cloud_build
    import recipient_tree
    seen = []

    def recorded(command, **keywords):
        seen.append((command[3], keywords.get("writes", False)))
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(cloud_build.seat_process, "run_read", recorded)
    monkeypatch.setattr(recipient_tree, "run_read", recorded)
    for verb in ("push", "fetch", "merge", "rev-parse", "status"):
        cloud_build.Transport().git(tmp_path, verb)
    for verb in ("init", "config", "commit", "checkout", "rev-parse", "ls-files"):
        recipient_tree._git(tmp_path, verb)
    assert seen == [("push", True), ("fetch", True), ("merge", True), ("rev-parse", False), ("status", False),
                    ("init", True), ("config", True), ("commit", True), ("checkout", True),
                    ("rev-parse", False), ("ls-files", False)]

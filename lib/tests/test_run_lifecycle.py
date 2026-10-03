import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dispatch_lifecycle as capture
import dispatch_record as records
import run_lifecycle as lifecycle


@pytest.fixture(autouse=True)
def functional_snapshot_allowance(monkeypatch):
    original = lifecycle.content_snapshot
    # Content assertions do not buy a startup deadline. Preserve declared
    # invocation deadlines; allow read-only fixture Git under parallel load.
    def snapshot(root, *, timeout=20):
        return original(root, timeout=timeout if lifecycle.current_deadline() else max(timeout, 120))
    monkeypatch.setattr(lifecycle, "content_snapshot", snapshot)


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE).stdout


@pytest.fixture
def tree(tmp_path):
    git(tmp_path, "init")
    git(tmp_path, "config", "user.name", "Fixture")
    git(tmp_path, "config", "user.email", "fixture@example.test")
    (tmp_path / "file").write_bytes(b"initial\n")
    (tmp_path / ".gitignore").write_bytes(b"cache\n")
    git(tmp_path, "add", "file", ".gitignore")
    git(tmp_path, "commit", "-m", "Initial")
    return tmp_path


@pytest.mark.parametrize("change", ["head", "index", "working", "modified", "untracked", "ignored", "check"])
@pytest.mark.parametrize("stage", ["build", "floor"])
def test_git_progress_uses_content(tree, change, stage):
    if change == "modified":
        (tree / "file").write_bytes(b"first edit")
    before = lifecycle.content_snapshot(tree)
    if change in {"head", "index", "working", "modified"}:
        (tree / "file").write_bytes(b"second edit")
        if change in {"index", "head"}:
            git(tree, "add", "file")
        if change == "head":
            git(tree, "commit", "-m", "Change")
    elif change == "untracked":
        (tree / "new").write_bytes(b"new content")
    elif change == "ignored":
        (tree / "cache").write_bytes(b"cache content")
    else:
        git(tree, "status", "--porcelain")
    after = lifecycle.content_snapshot(tree)
    assert lifecycle.progress(before, after) == ("unchanged" if change in {"ignored", "check"} else "changed"), {"before": before, "after": after}
    if change == "untracked":
        (tree / "new").write_bytes(b"different content")
        assert lifecycle.progress(after, lifecycle.content_snapshot(tree)) == "changed"


def test_unreadable_snapshot_is_unknown(tmp_path):
    current = lifecycle.content_snapshot(tmp_path)
    assert current["unavailable_reason"]
    assert lifecycle.progress({"digest": "before"}, current) == "unknown"


def test_default_deadline_and_invalid_limits(monkeypatch):
    monkeypatch.setattr(lifecycle.time, "monotonic", lambda: 10)
    window = lifecycle.Deadline(lifecycle.DEFAULT_BUILD_TIMEOUT_SECONDS)
    assert window.remaining() == 7140
    assert window.remaining(cleanup=True) == 7200
    assert lifecycle.TOTAL_BUILD_BUDGET_SECONDS == 14400
    short = lifecycle.Deadline(5)
    assert short.remaining() == 4.5
    for bad in [0, -1, float("nan"), float("inf")]:
        with pytest.raises(ValueError):
            lifecycle.Deadline(bad)
    monkeypatch.setattr(lifecycle.time, "monotonic", lambda: 15)
    with pytest.raises(TimeoutError):
        short.remaining()


def bundle(dispatch, stage, elapsed, *, unfinished=False, allocation=1000, reason=None):
    request = {"dispatch_id": dispatch, "stage": stage, "recipient_allocation_seconds": allocation,
               "budget_lineage": "lineage", "budget_override_reason": reason}
    run = {"attempts": [{"launched": True, "elapsed_seconds": elapsed}],
           "elapsed_checkpoint_seconds": elapsed}
    if not unfinished:
        run["completed_at"] = "2026-10-03T10:00:00Z"
    return "order", dispatch, request, run


@pytest.mark.parametrize("stage", ["floor", "review-disposition"])
def test_repair_run_keeps_stage_ceiling_and_shorter_caller_limit(monkeypatch, stage):
    import dispatch_implementer as implementer
    from types import SimpleNamespace
    monkeypatch.setattr(lifecycle.time, "monotonic", lambda: 10)
    seen = []
    monkeypatch.setattr(implementer, "_run_implementer", lambda args, deadline: seen.append(deadline) or 0)
    for caller in [8000, 30]:
        window = lifecycle.stage_deadline(stage, caller)
        assert window.remaining() == (3540 if caller == 8000 else 27)
        args = SimpleNamespace(stage=stage, timeout_seconds=caller)
        assert implementer.run_implementer(args) == 0
        assert seen[-1].end == window.end
    assert lifecycle.stage_deadline("build", 7200).remaining() == 7140


def test_build_budget_excludes_repairs_deduplicates_and_retains_uncertainty():
    first = bundle("first", "build", 7000)
    repair = bundle("repair", "floor", 20000)
    stopped = bundle("second", "build", 50, unfinished=True, allocation=1000)
    override = bundle("third", "build", 7000, reason="finish remaining work")
    account = lifecycle.runtime_account([first, repair, first, stopped, override], lineage="lineage")
    assert account["lower_seconds"] == 14050
    assert account["upper_seconds"] == 15000
    assert account["remaining_seconds"] == 0
    assert len(account["runs"]) == 4
    assert account["runs"][1]["excluded"]
    assert account["runs"][-1]["override_reason"] == "finish remaining work"
    stopped[2].pop("recipient_allocation_seconds")
    account = lifecycle.runtime_account([stopped])
    assert account["upper_seconds"] is None and account["remaining_seconds"] is None


def test_allocation_bounds_and_holder_override():
    account = lifecycle.runtime_account([bundle("first", "build", 14000)])
    assert lifecycle.allocation(account, 7140) == 400
    assert lifecycle.allocation(account, 7140, override_reason="finish the checks") == 7140
    for remaining in [None, 0]:
        account["remaining_seconds"] = remaining
        with pytest.raises(ValueError, match="override-reason"):
            lifecycle.allocation(account, 7140)
        assert lifecycle.allocation(account, 7140, override_reason="holder's call") == 7140
    with pytest.raises(ValueError):
        lifecycle.allocation(account, 7140, override_reason=" ")


def test_another_completed_copy_cannot_hide_conflicting_requests(tmp_path):
    request = {"schema_version": 2, "work": "example/product#12", "stage": "build",
               "dispatch_id": "same", "launched_at": "2026-10-03T10:00:00Z",
               "recipient_allocation_seconds": 1000}
    for name, allocation, complete in [("a", 500, False), ("b", 1000, False), ("c", 1000, True)]:
        copied = {**request, "recipient_allocation_seconds": allocation}
        run = {"schema_version": 2, "dispatch_id": "same"}
        if complete:
            run.update(completed_at="2026-10-03T10:10:00Z", attempts=[{"elapsed_seconds": 20}])
        (tmp_path / f"{name}.request.json").write_bytes(json.dumps(copied).encode())
        (tmp_path / f"{name}.run.json").write_bytes(json.dumps(run).encode())
    rows = lifecycle.launch_bundles(tmp_path, "example/product#12", {"build"})
    assert len(rows) == 1
    assert rows[0][3]["recovery_error"] == "conflicting copied requests"
    assert lifecycle.stopped(rows[0][3])
    assert lifecycle.runtime_account(rows)["remaining_seconds"] is None
    with pytest.raises(ValueError, match="conflicting copied"):
        lifecycle.recovery_session(rows[0][2], rows[0][3])


def test_newest_launch_is_visible_without_a_final_write(tmp_path):
    for name, complete, session in [("earlier", True, "identity"), ("latest", False, None)]:
        request = {"schema_version": 2, "work": "example/product#12", "stage": "build",
                   "dispatch_id": name, "launched_at": "2026-10-03T10:00:00Z" if complete else "2026-10-03T11:00:00Z"}
        run = {"schema_version": 2, "dispatch_id": name, "outcome": "success", "session_identity": session}
        if complete:
            run["completed_at"] = "2026-10-03T10:30:00Z"
        (tmp_path / (name + ".request.json")).write_bytes(json.dumps(request).encode())
        (tmp_path / (name + ".run.json")).write_bytes(json.dumps(run).encode())
    bundles = lifecycle.launch_bundles(tmp_path, "example/product#12", {"build"})
    assert bundles[-1][2]["dispatch_id"] == "latest"
    assert lifecycle.stopped(bundles[-1][3])


def test_liveness_distinguishes_a_live_process_dead_process_and_missing_proof():
    identity = lifecycle.process_identity()
    assert lifecycle.liveness({"launcher_process": identity}) == "active"
    assert lifecycle.liveness({}) == "unresolved"
    identity["birth"] += "different"
    assert lifecycle.liveness({"launcher_process": identity}) == "stopped"
    assert lifecycle.liveness({"launcher_process": identity,
                               "recipient_process": lifecycle.process_identity()}) == "active"
    assert lifecycle.liveness({"launcher_process": identity,
                               "recipient_process": {"pid": 1}}) == "unresolved"


@pytest.mark.parametrize("problem", ["missing", "mismatch", "active", "unresolved", "newest-unproved"])
def test_recovery_refuses_unproved_identity_and_liveness(problem):
    session = "0199a213-81c0-7800-8aa1-bbab2a035a53"
    request = {"requested": {"vendor": "codex", "session_id": session}}
    identity = lifecycle.process_identity()
    identity["birth"] += "old"
    run = {"actual_vendor": "codex", "launcher_process": identity,
           "session_identity": {"session_id": session}}
    assert lifecycle.recovery_session(request, run) == session
    if problem in {"missing", "newest-unproved"}:
        run.pop("session_identity")
    elif problem == "mismatch":
        run["session_identity"]["session_id"] = "89abcdef-0123-4567-89ab-cdef01234567"
    elif problem == "active":
        run["launcher_process"] = lifecycle.process_identity()
    else:
        run.pop("launcher_process")
    with pytest.raises(ValueError):
        lifecycle.recovery_session(request, run)


@pytest.mark.parametrize("vendor", ["codex", "claude"])
def test_growing_record_keeps_identity_after_malformed_partial_events(tmp_path, vendor):
    output = tmp_path / "return"
    run_path = records.sidecar(output, ".run.json")
    out = records.sidecar(output, ".stdout.log")
    err = records.sidecar(output, ".stderr.log")
    session = "0199a213-81c0-7800-8aa1-bbab2a035a53"
    attempt, run = {}, {"attempts": []}
    run["attempts"].append(attempt)
    with records.reserve_bundle([output, run_path, out, err], output) as streams:
        streams.mark_ready()
        growing = capture.GrowingRun(run_path, run, streams)
        growing.begin_attempt(attempt, vendor, out, err)
        event = ({"type": "thread.started", "thread_id": session} if vendor == "codex"
                 else {"type": "system", "subtype": "init", "session_id": session})
        raw = json.dumps(event).encode() + b"\nmalformed\npartial"
        growing.output("stdout", raw[:9])
        assert "session_identity" not in json.loads(run_path.read_bytes())
        growing.output("stdout", raw[9:])
        saved = json.loads(run_path.read_bytes())
        assert saved["session_identity"]["session_id"] == session
        assert "completed_at" not in saved
        assert out.read_bytes() == raw
        growing.finish_attempt()
        growing.finish()
        assert json.loads(run_path.read_bytes())["lifecycle"] == "completed"
        with pytest.raises(RuntimeError):
            growing.checkpoint()



def test_stream_chunks_record_identity_immediately_without_redundant_writes(tmp_path, monkeypatch):
    output = tmp_path / "return"
    run_path = records.sidecar(output, ".run.json")
    out, err = records.sidecar(output, ".stdout.log"), records.sidecar(output, ".stderr.log")
    current, writes = [10.0], []
    monkeypatch.setattr(capture.time, "monotonic", lambda: current[0])
    original = capture.atomic_record
    def recording(path, value):
        original(path, value)
        writes.append(json.loads(path.read_bytes()))
    monkeypatch.setattr(capture, "atomic_record", recording)
    with records.reserve_bundle([output, run_path, out, err], output) as streams:
        streams.mark_ready()
        run, attempt = {}, {}
        growing = capture.GrowingRun(run_path, run, streams)
        growing.begin_attempt(attempt, "codex", out, err)
        growing.launched(os.getpid())
        writes.clear()
        growing.output("stdout", b"diagnostic\n")
        assert len(writes) == 1
        growing.output("stdout", b"more diagnostic\n")
        assert len(writes) == 1
        current[0] += 0.1  # Earlier than the elapsed checkpoint interval.
        event = b'{"type":"thread.started","thread_id":"0199a213-81c0-7800-8aa1-bbab2a035a53"}\n'
        growing.output("stdout", event)
        assert len(writes) == 2 and writes[-1]["session_identity"]["session_id"]
        current[0] += 0.25
        growing.tick()
        assert len(writes) == 3 and writes[-1]["elapsed_checkpoint_seconds"] > 0
        current[0] += 1
        growing.finish_attempt()
        assert len(writes) == 3, "Completion must not pay for another timer fsync."
        growing.finish()
        assert len(writes) == 4 and writes[-1]["lifecycle"] == "completed"
        assert out.read_bytes() == b"diagnostic\nmore diagnostic\n" + event


@pytest.mark.parametrize("failure", ["transient", "persistent", "permission", "expired"])
def test_atomic_record_replacement_retry_is_bounded_and_preserves_previous_record(tmp_path, monkeypatch, failure):
    path = tmp_path / "run.json"
    path.write_bytes(b'{"prior":true}')
    current, calls = [100.0], []
    monkeypatch.setattr(capture.time, "monotonic", lambda: current[0])
    monkeypatch.setattr(capture.time, "sleep", lambda delay: current.__setitem__(0, current[0] + delay))
    deadline = lifecycle.Deadline(1)
    if failure == "expired":
        current[0] = deadline.end
    original = capture.os.replace
    def replace(source, target):
        calls.append(current[0])
        if failure == "transient" and len(calls) > 1:
            return original(source, target)
        error = PermissionError("replacement denied")
        error.winerror = 1314 if failure == "permission" else 32
        raise error
    monkeypatch.setattr(capture.os, "replace", replace)
    with lifecycle.deadline_scope(deadline):
        if failure == "transient" and os.name == "nt":
            capture.atomic_record(path, {"new": True})
            assert json.loads(path.read_bytes()) == {"new": True} and len(calls) == 2
        else:
            with pytest.raises(PermissionError):
                capture.atomic_record(path, {"new": True})
            assert json.loads(path.read_bytes()) == {"prior": True}
    bound = deadline.end if failure == "expired" else deadline.end - deadline.reserve / 4
    assert current[0] <= bound + 0.000001
    if failure in {"permission", "expired"}:
        assert len(calls) == 1
    assert not list(tmp_path.glob(".run-*"))

def test_claude_stream_terminal_and_historical_json():
    result = {"type": "result", "result": "final", "is_error": False}
    raw = json.dumps(result).encode()
    assert capture.claude_terminal(raw) == result
    assert capture.claude_terminal(b'{"type":"system"}\n' + raw + b'\n') == result


def test_malformed_usage_and_expired_probes_stay_unknown(monkeypatch, tmp_path):
    evidence = records.runtime_evidence("claude", b'bad\xff', "fresh")
    assert evidence["normalized"] is None and evidence["normalized_unavailable_reason"]
    monkeypatch.setattr(lifecycle.time, "monotonic", lambda: 10)
    deadline = lifecycle.Deadline(1)
    monkeypatch.setattr(lifecycle.time, "monotonic", lambda: 12)
    with lifecycle.deadline_scope(deadline):
        assert records.runtime_version(["never-launched"]) is None
        assert records.git_revision(tmp_path) is None



@pytest.mark.parametrize("probe_seconds", [0.1, 0.9])
def test_cleanup_does_not_start_a_probe_that_previously_outlasted_its_window(tmp_path, monkeypatch, probe_seconds):
    current, calls = [100.0], []
    monkeypatch.setattr(lifecycle.time, "monotonic", lambda: current[0])
    deadline = lifecycle.Deadline(15)
    def probe(command, **kwargs):
        calls.append(command)
        current[0] += probe_seconds
        return subprocess.CompletedProcess(command, 0, b"fixture-head", b"")
    monkeypatch.setattr(records, "run_process", probe)
    with lifecycle.deadline_scope(deadline):
        assert records.git_revision(tmp_path) == "fixture-head"
        assert deadline.probe_seconds == pytest.approx(probe_seconds)
        current[0] = 113.5
        with lifecycle.cleanup_scope():
            assert records.git_revision(tmp_path) == ("fixture-head" if probe_seconds < 0.75 else None)
    assert len(calls) == (2 if probe_seconds < 0.75 else 1)

def test_cleanup_probes_leave_time_for_the_completion_write(monkeypatch, tmp_path):
    current = [100.0]
    monkeypatch.setattr(lifecycle.time, "monotonic", lambda: current[0])
    deadline = lifecycle.Deadline(15)
    with lifecycle.deadline_scope(deadline):
        current[0] = 113.5  # The recipient has reached its stopping ceiling.
        with pytest.raises(TimeoutError):
            lifecycle.probe_timeout()
        with lifecycle.cleanup_scope():
            assert lifecycle.probe_timeout() == 0.75
            assert lifecycle.cleanup_deadline() == 114.25
            current[0] = 114.3
            monkeypatch.setattr(records, "run_process", lambda *_a, **_k: pytest.fail("launched after cleanup allowance"))
            assert records.git_revision(tmp_path) is None
        assert deadline.remaining(cleanup=True) > 0  # Final recording still has its allowance.


@pytest.mark.parametrize("paths", [1, 100])
def test_snapshot_bounds_deleted_path_traversal(monkeypatch, tmp_path, paths):
    current = [0.0]
    def clock():
        current[0] += 0.01
        return current[0]
    monkeypatch.setattr(lifecycle.time, "monotonic", clock)
    def git(command, **_kwargs):
        if "rev-parse" in command:
            output = b"fixture-head"
        elif "--stage" in command:
            output = b""
        else:
            output = b"\0".join(f"deleted-{i}".encode() for i in range(paths))
        return subprocess.CompletedProcess(command, 0, output, b"")
    monkeypatch.setattr(lifecycle, "run_process", git)
    with lifecycle.deadline_scope(lifecycle.Deadline(1)):
        snapshot = lifecycle.content_snapshot(tmp_path, timeout=0.1)
    if paths == 1:
        assert snapshot["digest"]
    else:
        assert snapshot["digest"] is None
        assert "content snapshot deadline" in snapshot["unavailable_reason"]


@pytest.mark.parametrize("entry", ["runtime-version", "entrance-probe"])
def test_slow_preflight_probe_stops_its_tree_within_the_caller_limit(tmp_path, entry):
    import work
    trace = tmp_path / "probe-processes.json"
    probe = tmp_path / "slow-version.py"
    lib = str(Path(__file__).resolve().parents[1])
    probe.write_text(
        "import json,os,subprocess,sys,time\nfrom pathlib import Path\n"
        f"sys.path.insert(0,{lib!r})\nimport run_lifecycle as lifecycle\n"
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(90)'],"
        "stdin=subprocess.DEVNULL,stdout=sys.stdout,stderr=sys.stderr)\n"
        f"Path({str(trace)!r}).write_bytes(json.dumps([lifecycle.process_identity(),"
        "lifecycle.process_identity(child.pid)]).encode())\n"
        "print('version probe still running',flush=True)\ntime.sleep(90)\n",
        encoding="utf-8", newline="\n")
    started = time.monotonic()
    with lifecycle.deadline_scope(lifecycle.Deadline(15)):
        if entry == "runtime-version":
            assert records.runtime_version([sys.executable, str(probe)]) is None
        else:
            with pytest.raises(subprocess.TimeoutExpired):
                work._run_probe([sys.executable, str(probe)], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=lifecycle.probe_timeout(), env=os.environ.copy())
    assert time.monotonic() - started < 15
    identities = json.loads(trace.read_bytes())
    until_dead = time.monotonic() + 2
    while time.monotonic() < until_dead and any(
            lifecycle.liveness({"launcher_process": identity}) != "stopped" for identity in identities):
        time.sleep(0.05)
    assert all(lifecycle.liveness({"launcher_process": identity}) == "stopped" for identity in identities)


def test_mismatch_remains_evidence_without_replacing_canonical_session(tmp_path):
    output = tmp_path / "return"
    run_path = records.sidecar(output, ".run.json")
    out, err = tmp_path / "stdout", tmp_path / "stderr"
    expected = "0199a213-81c0-7800-8aa1-bbab2a035a53"
    other = "89abcdef-0123-4567-89ab-cdef01234567"
    record, attempt = {}, {}
    with records.reserve_bundle([output, run_path, out, err], output) as streams:
        streams.mark_ready()
        growing = capture.GrowingRun(run_path, record, streams, expected=expected,
                                    retained=expected, retained_source="predecessor")
        growing.begin_attempt(attempt, "codex", out, err)
        growing.output("stdout", json.dumps({"type": "thread.started", "thread_id": other}).encode() + b"\n")
        saved = json.loads(run_path.read_bytes())
        assert saved["session_identity_error"]
        assert saved["session_identity"]["session_id"] == expected
        assert saved["session_identity"]["reported_session_id"] == other

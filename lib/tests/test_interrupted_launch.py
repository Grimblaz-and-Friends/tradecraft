import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_lifecycle as lifecycle
import work
from test_work import state, registry_row, MECHANICAL

LIB = Path(__file__).resolve().parents[1]


def kill_tree(pid):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=10, check=True)
    else:
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
    dispatch = tmp_path / "dispatch"
    dispatch.write_bytes(b"Perform this stage and return.\n")
    store = tmp_path / "vendor-state"
    store.mkdir()
    (store / "nonce").write_bytes(b"retained-before-hard-kill")
    output = tmp_path / "bundle" / "return"
    ceiling = termination.startswith("ceiling")
    caller_limit = 15 if ceiling else 60
    command = [sys.executable, str(LIB / "tests/fixtures/interrupted_launcher.py"), kind, vendor, str(store),
               "--dispatch", str(dispatch), "--root", str(root), "--vendor", vendor,
               "--work", "example/product#12", "--stage", "build" if kind == "implementer" else "cold-seat",
               "--settings-source", "fixture", "--settings-scope", "fixture",
               "--output", str(output), "--timeout-seconds", str(caller_limit)]
    if termination == "ceiling-slow-final-probe":
        command.append("--slow-final-probe")
    if kind == "implementer":
        command.extend(["--lineage-branch", branch, "--holder-session-id", "holder-session"])
    if kind == "seat":
        command.extend(["--classification", "cold", "--requires", "read", "--own-vendor", "claude" if vendor == "codex" else "codex"])
    started = time.monotonic()
    command.extend(["--invocation-started-monotonic", str(started)])
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    run_path = Path(str(output) + ".run.json")
    try:
        until = time.monotonic() + 25
        while not (store / "blocked.json").exists() and time.monotonic() < until:
            if process.poll() is not None:
                break
            time.sleep(0.05)
        assert (store / "blocked.json").exists(), process.communicate(timeout=1) if process.poll() is not None else "vendor never reached blocked command"
        pids = json.loads((store / "blocked.json").read_bytes())
        identities = [lifecycle.process_identity(pid) for pid in pids]
        # Wait for the launcher's flush, without giving it a chance to finish.
        while time.monotonic() < until:
            try:
                saved = json.loads(run_path.read_bytes())
                if saved.get("session_identity", {}).get("session_id"):
                    break
            except (OSError, ValueError):
                pass
            time.sleep(0.05)
        if termination == "hard-kill":
            kill_tree(process.pid)
        process.communicate(timeout=20 if ceiling else 5)
        if ceiling:
            elapsed = time.monotonic() - started
            record_property("launcher_elapsed_seconds", elapsed)
            record_property("caller_limit_seconds", caller_limit)
            assert elapsed < caller_limit, f"whole invocation took {elapsed:.3f}s against the declared {caller_limit}s limit"
        saved = json.loads(run_path.read_bytes())
        assert saved["session_identity"]["session_id"] == "0199a213-81c0-7800-8aa1-bbab2a035a53"
        if termination == "hard-kill":
            assert not saved.get("completed_at")
        else:
            assert saved["completed_at"] and saved["outcome"] == "interrupted"
            assert saved["interruption_cause"] == "ceiling"
            attempt = saved["attempts"][0]
            assert "caller limit 15s" in attempt["reason"]
            assert f"recipient allocation {attempt['allocation_seconds']:.2f}s" in attempt["reason"]
            assert f"measured elapsed {attempt['elapsed_seconds']:.2f}s" in attempt["reason"]
            assert "timed out after 15s" not in attempt["reason"]
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
            launches = []
            def launch(command, *args, **kwargs):
                if len(command) > 1 and Path(command[1]).name == "dispatch_implementer.py":
                    launches.append(command)
                    actual = [sys.executable, str(LIB / "tests/fixtures/interrupted_launcher.py"),
                              "implementer", vendor, str(store), *command[2:], "--output", str(resumed)]
                    return original_run(actual, *args, **kwargs)
                return original_run(command, *args, **kwargs)
            monkeypatch.setattr(work.subprocess, "run", launch)
            recommendation = work.decide(fixture, {"schema_version": 1, "rules": []})
            continuity = work._named_continuity(fixture, "build", recommendation)
            assert continuity == "resume"
            decision = work.Decision("build", True, continuity, "holder-named-stage")
            assert work.execute_stage(fixture, decision, holder, None, "holder-session", timeout_seconds=30) == 0
            assert len(launches) == 1
            assert launches[0][launches[0].index("--resume") + 1] == saved["session_identity"]["session_id"]
            assert b"retained-before-hard-kill" in resumed.read_bytes()
            assert len(list(output.parent.glob("*.run.json"))) == 2
    finally:
        if process.poll() is None:
            kill_tree(process.pid)
        process.communicate(timeout=5)

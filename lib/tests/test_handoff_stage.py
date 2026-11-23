"""run handoff: the holder hands a builder-route change to its builder, launched or started by hand."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import work  # noqa: E402
from test_route import MECHANICAL, RULES, fixture, launch, route_marker  # noqa: E402

HOLDER_SESSION = "holder-session"
STUB = r'''
import json, sys, time, uuid
from pathlib import Path
sys.path.insert(0, {lib!r})
import dispatch_record as records
import launch_tree
import run_lifecycle as lifecycle
arguments = sys.argv[1:]
def option(name):
    return arguments[arguments.index(name) + 1]
output = Path(option("--output"))
(output.parent / "argv.json").write_text(json.dumps(arguments), encoding="utf-8")
if {fail!r}:
    print("stub launcher refuses", file=sys.stderr)
    raise SystemExit(3)
metadata = json.loads(Path(option("--lifecycle-input")).read_bytes())
dispatch_id = uuid.uuid4().hex
request = records.request_record(
    dispatch_id=dispatch_id, work=option("--work"), stage="stretch", settings_source="stub launcher",
    settings_scope="implementer", vendor="claude", model="stub", effort="stub",
    continuity="resume" if "--resume" in arguments else "fresh", permission_boundary="stub",
    root=Path(option("--root")))
request.update(handoff=metadata["handoff"], lineage_branch=option("--lineage-branch"),
               caller_limit_seconds=float(option("--timeout-seconds")))
print("implementer: window " + json.dumps({{"latest_return_at": "stub"}}), flush=True)
request_path = records.sidecar(output, ".request.json")
records.write_json(request_path, request)
launch_tree.write_pointer(records.default_record_root(), dispatch_id=dispatch_id, work=option("--work"),
                          request=request_path, run=records.sidecar(output, ".run.json"),
                          session_id="stub-session", launcher=lifecycle.process_identity(),
                          root=Path(option("--root")))
time.sleep(60)
'''


def git(root, *arguments):
    return subprocess.run(["git", "-C", str(root), *arguments], stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout.decode().strip()


@pytest.fixture()
def holder(tmp_path):
    """A holder checkout with its change-proof policy, published to a bare remote."""
    root = tmp_path / "holder"
    root.mkdir()
    git(root, "init", "-q")
    (root / ".gitignore").write_text(".claude/worktrees/\n", encoding="utf-8")
    (root / ".github").mkdir()
    (root / ".github" / "change-proof.json").write_text(json.dumps(RULES), encoding="utf-8")
    git(root, "add", ".")
    git(root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com", "commit", "-qm", "fixture")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "-q", "--set-upstream", "origin", "HEAD")
    return root


@pytest.fixture()
def quiet_report(monkeypatch):
    monkeypatch.setattr(work, "_evaluate_reach", lambda state: None)
    monkeypatch.setattr(work, "_implementer_environments", lambda state: None)
    monkeypatch.setattr(work, "_evaluate_launch_findings", lambda state: {"status": "clear"})
    monkeypatch.setattr(work, "_github_write_report", lambda state: None)


class NoTransport:
    def __getattr__(self, name):
        raise AssertionError(f"read GitHub ({name})")


def stored(tmp_path, *texts):
    state = fixture(tmp_path, *texts)
    state.record_root = work.records.default_record_root()
    state.version_obligation = {}
    return state


def run(monkeypatch, holder, state, stage="handoff", *extra):
    monkeypatch.setattr(work, "_read_policy_state", lambda *a, **k: state)
    monkeypatch.setattr(work, "_capture_policy_snapshot", lambda *a, **k: None)
    args = work.parser().parse_args(["run", stage, "--repo", "o/r", "--issue", "5", "--root", str(holder),
                                     "--holder-session-id", HOLDER_SESSION, *extra])
    return work.run(args, transport=NoTransport(), executor=lambda *a, **k: pytest.fail("launched"))


def refused(monkeypatch, holder, state, *extra, stage="handoff"):
    with pytest.raises(work.RouteRefused) as caught:
        run(monkeypatch, holder, state, stage, *extra)
    assert str(caught.value).startswith(caught.value.code + ": ")
    return caught.value.code


def nothing_made(holder):
    assert not (holder / ".claude" / "worktrees").exists() or not any((holder / ".claude" / "worktrees").iterdir())
    assert git(holder, "branch", "--list", "tradecraft/*") == ""
    registry = work.registry_path()
    assert not registry.exists() or json.loads(registry.read_bytes())["worktrees"] == []


def no_bundle():
    store = work.records.default_record_root()
    return not store.exists() or not list(store.glob("handoff-*"))


@pytest.fixture()
def no_spawn(monkeypatch):
    monkeypatch.setattr(work.detached, "spawn", lambda *a, **k: pytest.fail("started a process"))


@pytest.fixture()
def stub(tmp_path, monkeypatch):
    """A stand-in launcher that writes its request record and pointer, then sleeps; killed after the test."""
    def make(fail=False):
        script = tmp_path / ("stub-fail.py" if fail else "stub.py")
        script.write_text(STUB.format(lib=str(LIB), fail=fail), encoding="utf-8")
        monkeypatch.setattr(work, "_stretch_launcher", lambda: [sys.executable, "-B", str(script)])
        return script
    yield make
    for pointer in work.launch_tree.pointer_directory(work.records.default_record_root()).glob("*.json"):
        process = json.loads(pointer.read_bytes()).get("launcher_process") or {}
        if process.get("pid"):
            try:
                os.kill(process["pid"], signal.SIGTERM)
            except OSError:
                pass


def test_1011_a_relay_change_is_refused_route_is_relay_with_or_without_a_dispatch(
        tmp_path, monkeypatch, holder, quiet_report, no_spawn):
    state = stored(tmp_path, MECHANICAL, route_marker("relay"))
    assert refused(monkeypatch, holder, state) == "route-is-relay"
    written = tmp_path / "dispatch.txt"
    written.write_text("the holder's own handoff\n", encoding="utf-8")
    assert refused(monkeypatch, holder, state, "--dispatch", str(written)) == "route-is-relay"
    nothing_made(holder)
    assert no_bundle()


def test_1011_a_plan_lane_with_no_settled_plan_is_refused(tmp_path, monkeypatch, holder, quiet_report, no_spawn):
    state = stored(tmp_path, MECHANICAL.replace("mechanical", "connected"))
    assert refused(monkeypatch, holder, state) == "plan-unsettled"
    nothing_made(holder)
    assert no_bundle()


def test_1011_a_live_builder_refuses_another_handoff(tmp_path, monkeypatch, holder, quiet_report, no_spawn):
    state = stored(tmp_path, MECHANICAL)
    # The launcher is a live child, so this process isn't inside the launch's tree on POSIX.
    child = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(120)"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        store = work.records.default_record_root()
        output = store / "stretch-live" / "result.md"
        output.parent.mkdir(parents=True)
        request = work.records.sidecar(output, ".request.json")
        work.records.write_json(request, work.records.request_record(
            dispatch_id="a" * 32, work="o/r#5", stage="stretch", settings_source="fixture launch",
            settings_scope="this stretch launch", vendor="claude", model="m", effort="e",
            continuity="fresh", permission_boundary="fixture boundary", root=tmp_path / "implementation"))
        work.launch_tree.write_pointer(
            store, dispatch_id="a" * 32, work="o/r#5", request=request, run=work.records.sidecar(output, ".run.json"),
            session_id="s", launcher=work.lifecycle.process_identity(child.pid), root=tmp_path / "implementation")
        _live_builder_refusals(monkeypatch, holder, state)
    finally:
        child.kill()
        child.wait()


def _live_builder_refusals(monkeypatch, holder, state):
    assert refused(monkeypatch, holder, state) == "builder-live"
    assert refused(monkeypatch, holder, state, "--ended-reason", "gone") == "ended-reason-is-for-a-hand-record"
    nothing_made(holder)
    assert no_bundle()


def test_1011_a_spent_handoff_is_refused(tmp_path, monkeypatch, holder, quiet_report, no_spawn):
    state = stored(tmp_path, MECHANICAL)
    launch(state, "stretch", 5)
    assert refused(monkeypatch, holder, state) == "handoff-spent"
    nothing_made(holder)


def test_1011_a_limit_above_the_stretch_default_needs_an_override_reason(
        tmp_path, monkeypatch, holder, quiet_report, no_spawn):
    assert work.DEFAULT_STRETCH_TIMEOUT_SECONDS == 28800
    state = stored(tmp_path, MECHANICAL)
    assert refused(monkeypatch, holder, state, "--timeout-seconds", "30000") == "limit-above-default"
    nothing_made(holder)
    with pytest.raises(work.WorkError, match="--budget-override-reason requires"):
        run(monkeypatch, holder, state, "ready-reviewers", "--budget-override-reason", "long")
    with pytest.raises(work.WorkError, match="--by-hand requires run handoff"):
        run(monkeypatch, holder, state, "ready-reviewers", "--by-hand", "gemini:m")


def hand_requests():
    store = work.records.default_record_root()
    return [json.loads(path.read_bytes()) for path in store.rglob("*.request.json")
            if "stretch-hand" in path.parent.name]


def test_1011_a_hand_started_builder_is_recorded_printed_and_ended(
        tmp_path, monkeypatch, holder, quiet_report, no_spawn, capsys):
    state = stored(tmp_path, MECHANICAL)
    assert run(monkeypatch, holder, state, "handoff", "--by-hand", "gemini:any-model",
               "--timeout-seconds", "30000", "--budget-override-reason", "a long change") == 0
    out = capsys.readouterr().out
    [request] = hand_requests()
    block = request["handoff"]
    assert request["requested"]["vendor"] == "gemini" and request["requested"]["model"] == "any-model"
    assert block["timeout_seconds"] == 30000 and block["override_reason"] == "a long change"
    assert block["holder_session_id"] == HOLDER_SESSION and block["holder_written"] is False
    assert f"TRADECRAFT_STRETCH_DISPATCH={block['dispatch']}" in out
    assert block["tree"] in out and block["branch"] in out
    assert Path(block["tree"]).is_dir()
    state.validated_markers = None
    assert work.decide(state, RULES).stage == "with-builder"
    assert refused(monkeypatch, holder, state, stage="ready-reviewers") == "with-builder"
    assert run(monkeypatch, holder, state, "handoff", "--ended-reason", "the owner stopped it") == 0
    state.validated_markers = None
    assert work.decide(state, RULES).stage == "stretch-stopped"


def test_1011_a_codex_machine_builder_is_started_by_hand(tmp_path, monkeypatch, holder, quiet_report, no_spawn):
    state = stored(tmp_path, MECHANICAL)
    assert run(monkeypatch, holder, state) == 0
    [request] = hand_requests()
    assert request["requested"]["vendor"] == "codex" and request["handoff"]["timeout_seconds"] == 28800


def claude_machine():
    path = Path.home() / ".tradecraft" / "implementer-vendor"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("claude\n", encoding="utf-8")


def test_1011_a_claude_builder_is_launched_detached_and_the_holder_waits_for_it(
        tmp_path, monkeypatch, holder, quiet_report, stub, capsys):
    claude_machine()
    stub()
    state = stored(tmp_path, MECHANICAL)
    assert run(monkeypatch, holder, state) == 0
    out = capsys.readouterr().out
    pointers = list(work.launch_tree.pointer_directory(work.records.default_record_root()).glob("*.json"))
    [pointer] = [json.loads(path.read_bytes()) for path in pointers]
    assert pointer["dispatch_id"] in out and "implementer: window" in out
    assert work.launch_tree.live_launches(work.records.default_record_root())  # The stub still runs.
    request = json.loads(Path(pointer["request"]).read_bytes())
    assert request["handoff"]["timeout_seconds"] == 28800 and request["handoff"]["holder_written"] is False
    argv = json.loads((Path(pointer["request"]).parent / "argv.json").read_bytes())
    assert argv[argv.index("--stage") + 1] == "stretch"
    assert argv[argv.index("--holder-session-id") + 1] == HOLDER_SESSION
    assert argv[argv.index("--timeout-seconds") + 1] == "28800"
    assert argv[argv.index("--work") + 1] == "o/r#5"
    state.validated_markers = None
    assert work.decide(state, RULES).stage == "with-builder"
    assert refused(monkeypatch, holder, state, stage="ready-reviewers") == "with-builder"
    assert refused(monkeypatch, holder, state) == "builder-live"


def test_1011_a_launcher_that_does_not_start_takes_the_tree_it_was_given_away(
        tmp_path, monkeypatch, holder, quiet_report, stub):
    claude_machine()
    stub(fail=True)
    state = stored(tmp_path, MECHANICAL)
    assert refused(monkeypatch, holder, state) == "launcher-did-not-start"
    nothing_made(holder)
    assert git(holder, "ls-remote", "--heads", "origin", "tradecraft/*") == ""


def test_1011_a_stopped_hand_started_builder_resumes_only_by_the_holders_reason(
        tmp_path, monkeypatch, holder, quiet_report, no_spawn, capsys):
    state = stored(tmp_path, MECHANICAL)
    assert run(monkeypatch, holder, state, "handoff", "--by-hand", "gemini:any-model") == 0
    assert run(monkeypatch, holder, state, "handoff", "--ended-reason", "the session closed") == 0
    assert refused(monkeypatch, holder, state) == "handoff-spent"
    capsys.readouterr()
    assert run(monkeypatch, holder, state, "handoff", "--resume-reason", "carry on from the stop") == 0
    out = capsys.readouterr().out
    first, second = sorted(hand_requests(), key=lambda request: request["launched_at"])
    assert second["handoff"]["resume_of"] == first["dispatch_id"]
    assert second["handoff"]["resume_reason"] == "carry on from the stop"
    assert "carry on from the stop" in out and second["dispatch_id"] in out
    state.validated_markers = None
    assert work.decide(state, RULES).stage == "with-builder"

"""Builder mode: which stretch launch holds a process, and what the entrance does inside one (#1011)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))

import launch_tree  # noqa: E402
import run_lifecycle as lifecycle  # noqa: E402
import seat_process  # noqa: E402

PROBE = ("import json, sys; sys.path.insert(0, sys.argv[1]); import launch_tree; "
         "h = launch_tree.stretch_holding(sys.argv[2]); "
         "print(json.dumps({'state': h.state, 'dispatch': (h.launch or {}).get('dispatch_id'), "
         "'reason': h.reason}))")


def pointer(store, *, run_value=None, launcher=None, work="o/r#5", session="s"):
    dispatch_id = uuid.uuid4().hex
    run = Path(store) / f"{dispatch_id}.run.json"
    run.parent.mkdir(parents=True, exist_ok=True)
    run.write_text(json.dumps(run_value if run_value is not None else {}), encoding="utf-8")
    launch_tree.write_pointer(Path(store), dispatch_id=dispatch_id, work=work,
                              request=run.with_name(f"{dispatch_id}.request.json"), run=run,
                              session_id=session, launcher=launcher or lifecycle.process_identity(),
                              root=Path(store))
    return dispatch_id


def held_probe(store, dispatch_id, *, inside):
    """Run the tree check from a child that is, or is not, inside the named launch's tree."""
    command = [sys.executable, "-c", PROBE, str(LIB), str(store)]
    env = launch_tree.without_variables(dict(os.environ))
    if inside and os.name == "nt":
        env[launch_tree.JOB_VARIABLE] = dispatch_id
        result = seat_process.run_process(command, input=b"", cwd=str(store), timeout=60, env=env,
                                          on_tick=lambda *_: None)
    else:
        # On POSIX this test process is the pointer's recorded launcher, so its child is below it;
        # on Windows a plain child is in no job of the launch's name.
        result = subprocess.run(command, capture_output=True, env=env, timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.decode().strip().splitlines()[-1])


def test_no_live_stretch_reads_nothing_but_the_store(tmp_path):
    assert launch_tree.stretch_holding(tmp_path).state == "none"


def test_a_completed_or_dead_stretch_holds_nothing(tmp_path):
    pointer(tmp_path, run_value={"completed_at": "2026-11-22T00:00:00+00:00"})
    dead = dict(lifecycle.process_identity())
    dead["birth"] = "0"
    pointer(tmp_path, launcher=dead)
    assert launch_tree.live_launches(tmp_path) == []
    assert launch_tree.stretch_holding(tmp_path).state == "none"


def test_a_process_inside_a_stretch_tree_is_held_by_that_launch(tmp_path):
    dispatch_id = pointer(tmp_path)
    found = held_probe(tmp_path, dispatch_id, inside=True)
    assert found == {"state": "held", "dispatch": dispatch_id, "reason": ""}


@pytest.mark.skipif(os.name != "nt", reason="on POSIX, a test child is always below its launcher")
def test_a_process_outside_the_named_job_is_not_held(tmp_path):
    dispatch_id = pointer(tmp_path)
    # No job of that name exists for this child, so the launch does not hold it.
    assert held_probe(tmp_path, dispatch_id, inside=False)["state"] == "none"


def test_a_tree_check_that_errors_reads_unknown(tmp_path, monkeypatch):
    dispatch_id = pointer(tmp_path)

    def failing(launch):
        raise launch_tree.TreeUnknown("the job could not be queried")

    monkeypatch.setattr(launch_tree, "holds", failing)
    holding = launch_tree.stretch_holding(tmp_path)
    assert holding.state == "unknown" and holding.launch["dispatch_id"] == dispatch_id
    assert holding.record()["reason"] == "the job could not be queried"


@pytest.mark.skipif(os.name != "nt", reason="Windows names a stretch launch's job")
def test_a_second_job_of_the_same_name_is_refused(tmp_path):
    dispatch_id = uuid.uuid4().hex
    env = dict(os.environ, **{launch_tree.JOB_VARIABLE: dispatch_id})
    inner = [sys.executable, "-I", "-S", str(LIB / "seat_process.py"), str(tmp_path / "inner.json"),
             sys.executable, "-c", "pass"]
    # The outer worker drops the name before its recipient starts, so the recipient sets it again.
    outer = [sys.executable, "-c",
             "import os, subprocess, sys; sys.exit(subprocess.run(sys.argv[2:], env={**os.environ, "
             f"{launch_tree.JOB_VARIABLE!r}: sys.argv[1]}}).returncode)", dispatch_id, *inner]
    result = seat_process.run_process(outer, input=b"", cwd=str(tmp_path), timeout=60, env=env,
                                      on_tick=lambda *_: None)
    assert result.returncode == 1
    assert "already exists" in json.loads((tmp_path / "inner.json").read_bytes())["message"]


def test_the_worker_drops_the_job_name_before_the_recipient_starts(tmp_path):
    env = dict(os.environ, **{launch_tree.JOB_VARIABLE: uuid.uuid4().hex})
    command = [sys.executable, "-c",
               f"import os; print(os.environ.get({launch_tree.JOB_VARIABLE!r}, 'absent'))"]
    result = seat_process.run_process(command, input=b"", cwd=str(tmp_path), timeout=60, env=env,
                                      on_tick=lambda *_: None)
    assert result.stdout.decode().strip() == "absent"


def test_without_variables_names_no_stretch():
    env = {launch_tree.DISPATCH_VARIABLE: "x", launch_tree.WORK_VARIABLE: "o/r#5",
           launch_tree.JOB_VARIABLE: "x", "PATH": "p"}
    assert launch_tree.without_variables(env) == {"PATH": "p"}


# --- the entrance in builder mode -------------------------------------------------------------

import work  # noqa: E402

SESSION = "0199a213-81c0-7800-8aa1-bbab2a035a53"
HOLDER_STAGES = ["artifact", "cold-seat", "build", "floor", "review-disposition", "release-report"]


class NoTransport:
    """Any GitHub call fails the test: a refused builder-mode run reads nothing."""

    def __getattr__(self, name):
        raise AssertionError(f"builder mode read GitHub ({name}) before refusing")


def arguments(*words, issue=5, root="holder"):
    return work.parser().parse_args([*words, "--repo", "o/r", "--issue", str(issue), "--root", root])


@pytest.fixture()
def holding(monkeypatch, tmp_path):
    """A live stretch launch of o/r#5 holds this process; no registry exists."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    launch = {"dispatch_id": "a" * 32, "work": "o/r#5", "session_id": SESSION,
              "root": str(tmp_path / "implementation"), "request": str(tmp_path / "r.request.json")}
    state = {"value": launch_tree.Holding("held", launch)}
    monkeypatch.setattr(launch_tree, "stretch_holding", lambda store: state["value"])
    for name in (*launch_tree.VARIABLES, "CLAUDE_CODE_SESSION_ID"):
        monkeypatch.delenv(name, raising=False)
    return state


def refused(args):
    with pytest.raises(work.BuilderRefused) as caught:
        work.run(args, transport=NoTransport(), executor=lambda *a, **k: pytest.fail("executed"))
    return caught.value.code


@pytest.mark.parametrize("variable", [True, False])
@pytest.mark.parametrize("words", [*(["run", stage] for stage in HOLDER_STAGES), ["tree"],
                                   ["tree", "--mode", "adopter", "--path", "x"], ["release"], ["adopt"],
                                   ["allowance", "build", "--grant", "1"]])
def test_a_builder_is_refused_the_holders_stages_before_any_read(holding, monkeypatch, variable, words):
    if variable:
        monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, "a" * 32)
    assert refused(arguments(*words)) == "stage-not-the-builders"


@pytest.mark.parametrize("stage", sorted(work.BUILDER_STAGES - {"acceptance-criterion"}))
def test_a_builders_own_stages_reach_their_root_check(holding, stage):
    # No registry names the launch's root, so each permitted stage stops at the root, not the table.
    assert refused(arguments("run", stage)) == "builder-root-mismatch"


def test_a_builder_names_the_holder_checkout_its_root_is_registered_under(holding, tmp_path, monkeypatch):
    registry = work.registry_path()
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({"schema_version": 1, "worktrees": [
        {"root": str(tmp_path / "implementation"), "holder_root": str(tmp_path / "holder")}]}),
        encoding="utf-8")
    assert refused(arguments("run", "use", root=str(tmp_path / "elsewhere"))) == "builder-root-mismatch"
    args = arguments("run", "proof", root=str(tmp_path / "holder"))
    seen = {}

    def entry(args, transport, executor):
        seen["builder"] = work.builder_mode()
        seen["variables"] = [name for name in launch_tree.VARIABLES if name in os.environ]
        return 0

    monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, "a" * 32)
    monkeypatch.setattr(work, "_run_entry", entry)
    assert work.run(args, transport=NoTransport()) == 0
    assert seen["builder"]["dispatch_id"] == "a" * 32 and seen["builder"]["identity"] == "declared"
    assert seen["variables"] == []
    assert work.builder_mode() is None


@pytest.mark.parametrize("case", ["other-dispatch", "other-work", "other-session", "unheld"])
def test_a_run_whose_identity_does_not_hold_is_refused(holding, monkeypatch, case):
    monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, "b" * 32 if case == "other-dispatch" else "a" * 32)
    issue = 6 if case == "other-work" else 5
    if case == "other-session":
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "f0cb89b1-e040-4e6e-919b-4b4e58c717d2")
    if case == "unheld":
        holding["value"] = launch_tree.Holding("none")
    assert refused(arguments("run", "use", issue=issue)) == "builder-identity-unproved"


def test_a_tree_check_that_errors_refuses_only_with_the_variable_set(holding, monkeypatch, capsys):
    holding["value"] = launch_tree.Holding("unknown", {"dispatch_id": "a" * 32, "request": "r"}, "job unreadable")
    monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, "a" * 32)
    assert refused(arguments("run", "build")) == "launch-tree-unknown"
    monkeypatch.delenv(launch_tree.DISPATCH_VARIABLE)
    seen = {}
    monkeypatch.setattr(work, "_run_entry", lambda args, **_: seen.setdefault("mode", work.builder_mode()) or 0)
    assert work.run(arguments("run", "build"), transport=NoTransport()) == 0
    assert seen["mode"] is None
    assert '"request": "r"' in capsys.readouterr().out


def test_outside_every_tree_the_run_is_the_holders(holding, monkeypatch):
    holding["value"] = launch_tree.Holding("none")
    monkeypatch.setattr(work, "_run_entry", lambda args, **_: 0 if work.builder_mode() is None else 1)
    assert work.run(arguments("run", "build"), transport=NoTransport()) == 0


def test_a_live_builder_process_is_refused_a_holder_stage_whatever_its_variable(tmp_path):
    """A real child inside a stretch launch's tree: its job on Windows, below its launcher on POSIX."""
    store = tmp_path / "home" / ".tradecraft" / "dispatches"
    dispatch_id = pointer(store)
    env = launch_tree.without_variables(dict(os.environ))
    env.update(HOME=str(tmp_path / "home"), USERPROFILE=str(tmp_path / "home"))
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    if os.name == "nt":
        env[launch_tree.JOB_VARIABLE] = dispatch_id
    command = [sys.executable, str(LIB / "work.py"), "run", "build", "--repo", "o/r", "--issue", "5",
               "--root", str(tmp_path)]
    for variable in (dispatch_id, None):
        child = dict(env)
        if variable:
            child[launch_tree.DISPATCH_VARIABLE] = variable
        result = seat_process.run_process(command, input=b"", cwd=str(tmp_path), timeout=120, env=child,
                                          on_tick=lambda *_: None)
        assert result.returncode == 1
        assert b"stage-not-the-builders" in result.stderr
    # From a shell outside the launch, the same live launch's id set by hand is refused.
    outside = dict(env, **{launch_tree.DISPATCH_VARIABLE: dispatch_id})
    outside.pop(launch_tree.JOB_VARIABLE, None)
    if os.name == "nt":
        result = subprocess.run(command, capture_output=True, env=outside, timeout=120)
        assert result.returncode == 1 and b"builder-identity-unproved" in result.stderr

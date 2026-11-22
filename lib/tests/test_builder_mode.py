"""Builder mode: which stretch launch holds a process, and what the entrance does inside one.

Design: lib/DESIGN.md#a-builders-own-checks-and-writes
"""
from __future__ import annotations

import json
import os
import re
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
        result = subprocess.run(command, capture_output=True, env=env, timeout=60,
                                stdin=subprocess.DEVNULL)
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


@pytest.mark.parametrize("words", [*(["run", stage] for stage in HOLDER_STAGES), ["tree"],
                                   ["tree", "--mode", "adopter", "--path", "x"],
                                   ["allowance", "build", "--grant", "1"]])
def test_a_live_builder_process_is_refused_a_holder_stage_whatever_its_variable(tmp_path, words):
    """A real child inside a stretch launch's tree: its job on Windows, below its launcher on POSIX."""
    store = tmp_path / "home" / ".tradecraft" / "dispatches"
    dispatch_id = pointer(store)
    env = launch_tree.without_variables(dict(os.environ))
    env.update(HOME=str(tmp_path / "home"), USERPROFILE=str(tmp_path / "home"))
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    if os.name == "nt":
        env[launch_tree.JOB_VARIABLE] = dispatch_id
    command = [sys.executable, str(LIB / "work.py"), *words, "--repo", "o/r", "--issue", "5",
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
        result = subprocess.run(command, capture_output=True, env=outside, timeout=120,
                                stdin=subprocess.DEVNULL)
        assert result.returncode == 1 and b"builder-identity-unproved" in result.stderr


# --- who launched a seat ------------------------------------------------------------------------

LAUNCH = {"dispatch_id": "a" * 32, "work": "o/r#5", "session_id": SESSION, "request": "r"}


@pytest.fixture()
def tree_state(monkeypatch):
    state = {"value": launch_tree.Holding("held", dict(LAUNCH))}
    monkeypatch.setattr(launch_tree, "stretch_holding", lambda store: state["value"])
    for name in (*launch_tree.VARIABLES, "CLAUDE_CODE_SESSION_ID"):
        monkeypatch.delenv(name, raising=False)
    return state


@pytest.mark.parametrize("variable", [None, "a" * 32])
@pytest.mark.parametrize("session, identity", [(SESSION, "proved"), (None, "declared")])
def test_a_seat_inside_a_stretch_tree_is_the_builders_whatever_its_variable(tree_state, monkeypatch,
                                                                            variable, session, identity):
    if variable:
        monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, variable)
    if session:
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", session)
    fields = launch_tree.attribution(Path("store"))
    assert fields == {"launched_by": {"role": "builder", "dispatch_id": "a" * 32, "session_id": SESSION,
                                      "identity": identity}, "dispatch_origin": "caller"}
    entrance = launch_tree.attribution(Path("store"), dispatch="a" * 32, session=SESSION, origin="entrance")
    assert entrance["dispatch_origin"] == "entrance" and "launched_by_ignored" not in entrance


def test_forged_builder_flags_are_ignored_and_noted(tree_state):
    fields = launch_tree.attribution(Path("store"), dispatch="b" * 32, session="forged", origin="entrance")
    assert fields["launched_by"]["dispatch_id"] == "a" * 32
    assert fields["launched_by_ignored"] == {"dispatch": "b" * 32, "session": "forged"}


def test_outside_every_tree_a_seat_is_the_holders_and_builder_flags_are_refused(tree_state, monkeypatch):
    tree_state["value"] = launch_tree.Holding("none")
    assert launch_tree.attribution(Path("store")) == {}
    with pytest.raises(launch_tree.LaunchRefused, match="launched-by-outside-a-stretch"):
        launch_tree.attribution(Path("store"), dispatch="a" * 32, origin="entrance")
    monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, "a" * 32)
    with pytest.raises(launch_tree.LaunchRefused, match="builder-identity-unproved"):
        launch_tree.attribution(Path("store"))


def test_an_unknown_tree_refuses_a_seat_only_with_the_variable_set(tree_state, monkeypatch):
    tree_state["value"] = launch_tree.Holding("unknown", dict(LAUNCH), "job unreadable")
    assert launch_tree.attribution(Path("store"))["stretch_tree_check"]["request"] == "r"
    monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, "a" * 32)
    with pytest.raises(launch_tree.LaunchRefused, match="launch-tree-unknown"):
        launch_tree.attribution(Path("store"))



def test_an_unknown_tree_refuses_a_seat_or_record_given_the_entrances_flags(tree_state):
    import dispatch_record
    import dispatch_seat as seat
    tree_state["value"] = launch_tree.Holding("unknown", dict(LAUNCH), "job unreadable")
    for dispatch, origin in (("a" * 32, None), (None, "entrance")):
        with pytest.raises(launch_tree.LaunchRefused, match="launch-tree-unknown"):
            launch_tree.attribution(Path("store"), dispatch=dispatch, origin=origin)
    # Both refuse before any bundle: neither reads a field past the flags.
    flags = {"launched_by_dispatch": "a" * 32, "launched_by_session": SESSION, "dispatch_origin": "entrance"}
    with pytest.raises(seat.DispatchError, match="launch-tree-unknown"):
        seat.run_dispatch(SimpleNamespace(**flags))
    with pytest.raises(dispatch_record.RecordError, match="launch-tree-unknown"):
        dispatch_record.begin_native(SimpleNamespace(**flags))
    assert launch_tree.attribution(Path("store"))["stretch_tree_check"]["state"] == "unknown"


BEGIN = ("import sys; sys.path.insert(0, sys.argv[1]); import dispatch_record as r; "
         "raise SystemExit(r.main(sys.argv[2:]))")


def test_a_record_begun_from_inside_a_stretch_tree_with_the_variable_cleared_is_the_builders(tmp_path):
    home = tmp_path / "home"
    store = home / ".tradecraft" / "dispatches"
    dispatch_id = pointer(store)
    (tmp_path / "dispatch.md").write_bytes(b"Judge the built result.\n")
    env = launch_tree.without_variables(dict(os.environ))
    env.update(HOME=str(home), USERPROFILE=str(home))
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    if os.name == "nt":
        env[launch_tree.JOB_VARIABLE] = dispatch_id
    output = tmp_path / "records" / "seat.md"
    command = [sys.executable, "-c", BEGIN, str(LIB), "begin", "--work", "o/r#5", "--stage", "use",
               "--settings-source", "fixture", "--settings-scope", "this seat",
               "--vendor", "claude", "--vendor-source", "fixture", "--model", "opus",
               "--model-source", "fixture", "--effort", "max", "--effort-source", "fixture",
               "--classification", "cold", "--classification-source", "fixture",
               "--continuity-source", "fixture", "--permission-boundary", "native tool",
               "--permission-boundary-source", "fixture", "--input-file", str(tmp_path / "dispatch.md"),
               "--output", str(output), "--launched-by-dispatch", "b" * 32, "--dispatch-origin", "entrance"]
    result = seat_process.run_process(command, input=b"", cwd=str(tmp_path), timeout=120, env=env,
                                      on_tick=lambda *_: None)
    assert result.returncode == 0, result.stderr
    request = json.loads(output.with_name("seat.md.request.json").read_bytes())
    assert request["launched_by"] == {"role": "builder", "dispatch_id": dispatch_id, "session_id": "s",
                                      "identity": "declared"}
    assert request["dispatch_origin"] == "entrance"
    assert request["launched_by_ignored"] == {"dispatch": "b" * 32}


# --- what a builder's checks are told and read ---------------------------------------------------

ARTIFACT = (
    "# Plan\r\n\r\n"
    "## Use session job\r\n\r\n"
    "```text\r\nUse the tree as an adopter would.\r\nReport what broke.\r\n```\r\n\r\n"
    "## Consumer tree declaration use\r\n\r\n"
    "```json\n{\"mode\": \"adopter\", \"paths\": [\"skills\"]}\n```\n\n"
    "## Criteria\n\n"
    "**C1.** The allowance names its writes. *Check:* a test.\n\n"
    "- **C2.** A builder's report is posted by the entrance.\n"
    "  Fresh reader: execute consumer tree use\n\n"
    "**C2.1** is prose, not an opening.\n\n"
    "## After\n"
)


def test_the_use_job_is_the_fenced_block_under_its_heading_with_its_line_endings():
    assert work.artifact_use_job(ARTIFACT) == b"Use the tree as an adopter would.\r\nReport what broke.\r\n"


@pytest.mark.parametrize("artifact", [ARTIFACT.replace("## Use session job", "## Use job"),
                                      ARTIFACT + "\n## Use session job\n\n```\nagain\n```\n",
                                      ARTIFACT.replace("```text\r\nUse", "Prose first.\r\n```text\r\nUse")])
def test_a_missing_duplicated_or_unfenced_use_job_refuses(artifact):
    with pytest.raises(work.BuilderRefused) as caught:
        work.artifact_use_job(artifact)
    assert caught.value.code == "artifact-use-job-absent"


def test_a_criterion_runs_from_its_opening_to_the_next_opening_or_heading():
    assert work.artifact_criterion(ARTIFACT, "C1") == "**C1.** The allowance names its writes. *Check:* a test.\n"
    second = work.artifact_criterion(ARTIFACT, "C2")
    assert second.startswith("- **C2.** A builder's") and "C2.1" in second and "## After" not in second
    assert work.criterion_reader(second) == ("execute", "use")
    with pytest.raises(work.BuilderRefused) as caught:
        work.criterion_reader(work.artifact_criterion(ARTIFACT, "C1"))
    assert caught.value.code == "criterion-owes-no-fresh-reader"


@pytest.mark.parametrize("identifier, artifact", [("C9", ARTIFACT), ("C1", ARTIFACT + "\n**C1.** again\n")])
def test_a_criterion_found_zero_times_or_twice_refuses(identifier, artifact):
    with pytest.raises(work.BuilderRefused) as caught:
        work.artifact_criterion(artifact, identifier)
    assert caught.value.code == "artifact-criterion-unresolved"


def test_a_tree_declaration_carries_only_the_callers_parameters():
    declared = work.artifact_tree_declaration(ARTIFACT, "use")
    assert declared["mode"] == "adopter" and declared["paths"] == ["skills"]
    assert len(declared["block_sha256"]) == 64
    for artifact in (ARTIFACT.replace('"paths"', '"output"'), ARTIFACT.replace('"mode": "adopter", ', "")):
        with pytest.raises(work.BuilderRefused) as caught:
            work.artifact_tree_declaration(artifact, "use")
        assert caught.value.code == "artifact-tree-declaration-unresolved"
    with pytest.raises(work.BuilderRefused):
        work.artifact_tree_declaration(ARTIFACT, "other")


def test_a_check_dispatch_is_composed_from_its_inputs_alone():
    job = work.artifact_use_job(ARTIFACT)
    use = work.compose_check_dispatch("use", {"job": job, "head": "abc", "tree": "T"})
    assert use.startswith(job) and use == work.compose_check_dispatch("use", {"job": job, "head": "abc", "tree": "T"})
    criterion = work.artifact_criterion(ARTIFACT, "C2")
    composed = work.compose_check_dispatch("acceptance-criterion", {
        "criterion": criterion, "capability": "execute", "head": "abc", "tree": "T"}).decode("utf-8")
    assert composed.startswith(work.CRITERION_PREAMBLE) and composed.endswith(criterion)
    assert "Head: abc" in composed and "Capability: execute" in composed
    # Each ends its conditions with the return tail its findings are counted from.
    assert work.readiness.RETURN_TAILS["acceptance-criterion"] in composed
    assert work.readiness.RETURN_TAILS["use"].encode("utf-8") in use


@pytest.mark.parametrize("extra, code", [
    (["--dispatch", "job.md"], "builder-may-not-write-a-check's-instructions"),
    (["--tree-metadata", "tree.json"], "stage-composes-its-own-tree"),
])
def test_a_builder_supplies_no_use_dispatch_or_tree(holding, tmp_path, extra, code):
    registry = work.registry_path()
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({"schema_version": 1, "worktrees": [
        {"root": str(tmp_path / "implementation"), "holder_root": str(tmp_path / "holder")}]}),
        encoding="utf-8")
    assert refused(arguments("run", "use", *extra, root=str(tmp_path / "holder"))) == code


# --- a composed check: its tree, its seat's frame and its posted report ---------------------------

from types import SimpleNamespace  # noqa: E402

import dispatch_seat  # noqa: E402

CHECK_ARTIFACT = (
    "## Use session job\n\n```text\nUse the job as an adopter would.\n```\n\n"
    "## Consumer tree declaration use\n\n"
    "```json\n{\"mode\": \"adopter\", \"paths\": [\"job\"], \"loading_surfaces\": [\"skill/SKILL.md\"]}\n```\n\n"
    "## Criteria\n\n"
    "**C2.** The job runs.\nFresh reader: execute consumer tree use\n"
)


def git_in(root, *words):
    return subprocess.run(["git", "-C", str(root), *words], capture_output=True, check=True,
                          stdin=subprocess.DEVNULL)


@pytest.fixture()
def check_source(tmp_path):
    root = tmp_path / "source"
    (root / "job").mkdir(parents=True)
    (root / "skill").mkdir()
    (root / ".gitattributes").write_bytes(b"* text=auto eol=lf\n")
    (root / "job" / "job.md").write_bytes(b"run the consumer\n")
    (root / "skill" / "SKILL.md").write_bytes(b"loading surface\n")
    git_in(root, "init", "-q")
    git_in(root, "add", "--all")
    git_in(root, "-c", "user.name=f", "-c", "user.email=f@f", "commit", "-q", "-m", "fixture")
    return root.resolve()


class PostingTransport:
    def __init__(self, failures=0):
        self.posts, self.failures = [], failures

    def post(self, endpoint, payload):
        if self.failures:
            self.failures -= 1
            raise WorkErrorForTests("post failed")
        self.posts.append((endpoint, payload["body"]))
        return {"id": len(self.posts)}


class WorkErrorForTests(OSError):
    pass


FRAME_SCRIPT = ("import sys, types; sys.path.insert(0, sys.argv[1]); import dispatch_seat as d; "
                "print('seat: noise'); d._write_return_frame(types.SimpleNamespace("
                "frame_return=sys.argv[2].encode(), frame_record={'outcome': sys.argv[3], "
                "'staffing_status': 'degraded', 'staffing_qualification': "
                "{'same_vendor_reason': 'owner-selected-claude-implementer'}}, "
                "frame_dispatch_sha256=sys.argv[4], frame_dispatch_id='d' * 32))")


@pytest.fixture()
def composed(holding, check_source, tmp_path, monkeypatch):
    """A builder's composed check whose seat is a stand-in printing a frame; returns what it saw."""
    seen = {"reports": []}
    # The entrance names the tree under the system temporary folder, which must not hold its records.
    (tmp_path / "temp").mkdir()
    monkeypatch.setattr(work.tempfile, "tempdir", str(tmp_path / "temp"))
    state = SimpleNamespace(
        repo="o/r", issue_number=5, pr={"number": 12}, instalment=None, raw_output="", validated_markers=[],
        artifact_phase=SimpleNamespace(settled_artifact=SimpleNamespace(body=CHECK_ARTIFACT, source_id="77"),
                                       source_error=None))
    monkeypatch.setattr(work, "resolve_implementation_root", lambda *a, **k: (check_source, "tradecraft/zz-builder", False))
    # A builder's first check: no completed producer bundle exists, so this lookup must not be reached.
    monkeypatch.setattr(work, "_producer_vendor", lambda *a, **k: pytest.fail("read a completed producer bundle"))
    monkeypatch.setattr(work, "_launch_account_refusal", lambda state, stage: seen.get("account"))
    monkeypatch.setattr(work, "_version_refusal", lambda state, decision, *a: seen.get("version"))
    from comparison_window import held_builder, stretch_launch
    launch = stretch_launch(tmp_path / "launch-store", root=check_source, session_id=SESSION)
    monkeypatch.setattr(work, "_seat_launch_arguments", lambda *a, **k: [])
    monkeypatch.setattr(work, "_held_by_cold_reading", lambda *a, **k: False)
    monkeypatch.setattr(work, "_synchronization_decision", lambda state: seen.get("sync"))
    monkeypatch.setattr(work, "_launch_plan", lambda *a, **k: {"vendors": {"claude": {}, "codex": {}}})
    monkeypatch.setattr(work, "_reported_decision", lambda state, decision: decision)
    monkeypatch.setattr(work, "_emit_report", lambda payload, *a, **k: seen["reports"].append(payload))
    behaviour = {"outcome": "success", "return": "The job ran.\n", "edit": False}

    def recipient(command, deadline, runner=None):
        dispatch = Path(command[command.index("--dispatch") + 1])
        seen["dispatch"] = dispatch.read_bytes()
        seen["command"] = list(command)
        tree = Path(command[command.index("--root") + 1])
        seen["tree"] = tree
        if behaviour["edit"]:
            (tree / "job" / "job.md").write_bytes(b"edited while the seat ran\n")
        if behaviour.get("beside"):
            # A reader that runs commands writes in the folder around its tree, its working space.
            (tree.parent / "probe-evidence.txt").write_bytes(b"what the job printed\n")
        digest = __import__("hashlib").sha256(seen["dispatch"]).hexdigest()
        # The store copy the seat launcher keeps, at the output it resolves for this check.
        output = work.records.resolved_output(None, "o/r#5", command[command.index("--stage") + 1])
        output.parent.mkdir(parents=True, exist_ok=True)
        seen["store_copy"] = work.records.sidecar(output, ".source.bin")
        seen["store_copy"].write_bytes(behaviour["return"].encode())
        return runner([sys.executable, "-c", FRAME_SCRIPT, str(LIB), behaviour["return"],
                       behaviour["outcome"], digest], timeout=60, cleanup_deadline=None).returncode

    monkeypatch.setattr(work, "_invoke_recipient", recipient)
    work._BUILDER.set(held_builder(launch))
    yield state, behaviour, seen
    work._BUILDER.set(None)


def run_check(state, *words, transport):
    args = arguments("run", *words)
    return work._builder_check(state, args, Path("holder"), transport, "60")


def test_a_builders_use_check_is_composed_built_and_posted_from_its_frame(composed):
    state, _behaviour, seen = composed
    transport = PostingTransport()
    assert run_check(state, "use", "--job-from-artifact", transport=transport) == 0
    job = work.artifact_use_job(CHECK_ARTIFACT)
    head = git_in(work.resolve_implementation_root()[0], "rev-parse", "HEAD").stdout.decode().strip()
    assert seen["dispatch"] == work.compose_check_dispatch("use", {"job": job, "head": head, "tree": seen["tree"]})
    assert seen["command"][seen["command"].index("--launched-by-dispatch") + 1] == "a" * 32
    assert "--return-frame" in seen["command"] and "entrance" in seen["command"]
    (endpoint, body), = transport.posts
    assert endpoint == "repos/o/r/issues/5/comments"
    marker, text = body.split("\n\n", 1)
    assert text == "The job ran.\n"
    assert "stage=use" in marker and "tree=held" in marker and "outcome=success" in marker
    assert f"head={head}" in marker and "dispatch_sha256=" in marker and "staffing_status=degraded" in marker
    origin = json.loads((seen["reports"][-1] and Path(seen["reports"][-1]["tree_metadata"])).parent.parent
                        .joinpath("tree-origins", Path(seen["reports"][-1]["tree_metadata"]).name).read_bytes())
    assert origin["built_by"] == {"dispatch_id": "a" * 32}
    assert origin["declaration"]["name"] == "use" and origin["declaration"]["artifact_comment"] == "77"
    assert str(seen["tree"].name).startswith("tradecraft-tree-")


def test_a_tree_edited_while_its_seat_ran_is_reported_changed(composed):
    state, behaviour, _seen = composed
    behaviour["edit"] = True
    transport = PostingTransport()
    run_check(state, "use", "--job-from-artifact", transport=transport)
    assert "tree=changed" in transport.posts[0][1]


def test_a_criterion_check_carries_the_criterion_and_a_failed_seat_posts_error(composed):
    state, behaviour, seen = composed
    behaviour["outcome"] = "error"
    behaviour["return"] = ""
    transport = PostingTransport()
    run_check(state, "acceptance-criterion", "--criterion", "C2", transport=transport)
    assert seen["dispatch"].decode().startswith(work.CRITERION_PREAMBLE)
    assert work.artifact_criterion(CHECK_ARTIFACT, "C2").encode() in seen["dispatch"]
    assert seen["command"][seen["command"].index("--requires") + 1] == "execute"
    body = transport.posts[0][1]
    assert "criterion=C2" in body and "outcome=error" in body
    assert body.endswith(work.NO_RETURN_LINE)


def test_a_second_launch_posts_a_second_report(composed):
    state, _behaviour, _seen = composed
    transport = PostingTransport()
    run_check(state, "use", "--job-from-artifact", transport=transport)
    run_check(state, "use", "--job-from-artifact", transport=transport)
    assert len(transport.posts) == 2


def test_a_report_whose_post_fails_three_times_is_unposted(composed):
    state, _behaviour, seen = composed
    transport = PostingTransport(failures=3)
    assert run_check(state, "use", "--job-from-artifact", transport=transport) == 1
    assert seen["reports"][-1]["check_report"]["status"] == "check-report-unposted"
    retried = PostingTransport(failures=2)
    assert run_check(state, "use", "--job-from-artifact", transport=retried) == 0
    assert len(retried.posts) == 1


def test_a_frame_is_read_whole_or_not_at_all():
    value = b"line one\nline two\n"
    header = {"bytes": len(value), "sha256": __import__("hashlib").sha256(value).hexdigest(), "outcome": "success"}
    output = b"seat: x\n\n" + dispatch_seat.FRAME_OPENING + json.dumps(header).encode() + b"\n" + value
    assert dispatch_seat.read_return_frame(output)["return"] == value
    assert dispatch_seat.read_return_frame(output[:-1]) is None
    assert dispatch_seat.read_return_frame(b"no frame here") is None


# --- which posted reports count ---------------------------------------------------------------------

def write_bundle(store, name, request, run=None, files=None):
    output = store / name / "result.md"
    output.parent.mkdir(parents=True)
    work.records.write_json(work.records.sidecar(output, ".request.json"), {
        "schema_version": 2, "work": "o/r#5", "launched_at": "2026-11-22T00:00:00+00:00", **request})
    work.records.write_json(work.records.sidecar(output, ".run.json"),
                            {"schema_version": 2, "dispatch_id": request["dispatch_id"], **(run or {})})
    for suffix, content in (files or {}).items():
        work.records.sidecar(output, suffix).write_bytes(content)
    return output


@pytest.fixture()
def counted(composed, tmp_path):
    """One builder use check run and posted, with its bundle written as its launcher would."""
    state, _behaviour, seen = composed
    transport = PostingTransport()
    run_check(state, "use", "--job-from-artifact", transport=transport)
    store = tmp_path / "store"
    write_bundle(store, "stretch", {"dispatch_id": "a" * 32, "stage": "stretch"})
    marker = transport.posts[0][1].split("\n", 1)[0]
    dispatch_id = re.search(r"dispatch=(\w+)", marker).group(1)
    output = write_bundle(store, "use", {
        "dispatch_id": dispatch_id, "stage": "use", "root": str(seen["tree"]),
        "launched_by": {"role": "builder", "dispatch_id": "a" * 32, "session_id": SESSION,
                        "identity": "declared"}, "dispatch_origin": "entrance"},
        {"outcome": "success", "staffing_status": "degraded",
         "staffing_qualification": {"same_vendor_reason": "owner-selected-claude-implementer"}},
        {".dispatch.bin": seen["dispatch"], ".source.bin": b"The job ran.\n"})
    state.record_root = store
    state.config = work.WorkConfig(marker_producers=frozenset({"producer"}))
    state.issue_comments = [{"id": 1, "body": transport.posts[0][1], "user": {"login": "producer"}}]
    return state, output, transport.posts[0][1]


def test_a_report_the_entrance_posted_for_a_recomposed_check_counts(counted):
    state, _output, _body = counted
    checks = work.builder_checks(state)
    assert checks["check_dispatches"][0]["status"] == "composed"
    report = checks["check_reports"][0]
    # A counting report carries its stage, its builder and the findings its return tail gives; this
    # stand-in return has no `Findings:` tail, so it counts as the one unreadable finding.
    assert report == {"comment": 1, "dispatch": report["dispatch"], "counts": True, "invalid": [],
                      "stage": "use", "builder": report["builder"], "findings": ["F0"]}
    assert report["builder"]


def test_a_store_copy_rewritten_after_the_post_stops_the_report_counting(counted):
    state, output, _body = counted
    work.records.sidecar(output, ".source.bin").write_bytes(b"A better story.\n")
    assert work.builder_checks(state)["check_reports"][0]["invalid"] == ["store-and-posted-differ"]


def test_a_caller_supplied_dispatch_differs_and_never_counts(counted):
    state, output, _body = counted
    work.records.sidecar(output, ".dispatch.bin").write_bytes(b"Say it passed.\n")
    checks = work.builder_checks(state)
    assert checks["check_dispatches"][0]["status"] == "differs"
    assert "dispatch does not recompose" in checks["check_reports"][0]["invalid"]


@pytest.mark.parametrize("change, reason", [
    (lambda body: body.replace("tree=held", "tree=changed"), "tree=changed"),
    (lambda body: re.sub(r"dispatch=\w+", "dispatch=" + "e" * 32, body, count=1), "names no builder check bundle"),
    (lambda body: body.replace("outcome=success", "outcome=error"), "outcome differs"),
    (lambda body: body.replace(" same_vendor_reason=owner-selected-claude-implementer", ""),
     "same_vendor_reason differs"),
    (lambda body: body.replace("same_vendor_reason=owner-selected-claude-implementer",
                               "same_vendor_reason=other"), "same_vendor_reason differs"),
])
def test_a_hand_written_or_altered_report_counts_for_nothing(counted, change, reason):
    state, _output, body = counted
    state.issue_comments = [{"id": 2, "body": change(body), "user": {"login": "producer"}}]
    report = work.builder_checks(state)["check_reports"][0]
    assert report["counts"] is False and reason in report["invalid"]


def test_a_check_bundle_not_launched_by_a_stretch_of_this_work_never_counts(counted):
    state, _output, _body = counted
    stretch = state.record_root / "stretch" / "result.md.request.json"
    stretch.write_text(stretch.read_text(encoding="utf-8").replace('"stretch"', '"build"'), encoding="utf-8")
    assert "not a stretch builder's of this work" in work.builder_checks(state)["check_reports"][0]["invalid"]


def test_a_relay_report_carries_no_builder_checks(tmp_path):
    state = SimpleNamespace(repo="o/r", issue_number=5, record_root=tmp_path / "store", issue_comments=[])
    assert work.builder_checks(state) is None


@pytest.mark.parametrize("dispatch, status", [(b"composed reading", "composed"), (b"forged reading", "differs")])
def test_a_cold_reader_bundle_is_recomposed_from_its_reading_record(holding, tmp_path, monkeypatch,
                                                                     dispatch, status):
    monkeypatch.setattr(work, "_recompose_reading", lambda state, root, home: (b"composed reading", "h", ""))
    store = tmp_path / "store"
    write_bundle(store, "stretch", {"dispatch_id": "a" * 32, "stage": "stretch"})
    write_bundle(store, "reading", {"dispatch_id": "c" * 32, "stage": "cold-reader", "root": str(tmp_path),
                                    "launched_by": {"dispatch_id": "a" * 32}},
                 {"outcome": "success"}, {".dispatch.bin": dispatch})
    state = SimpleNamespace(repo="o/r", issue_number=5, record_root=store, issue_comments=[])
    assert work.builder_checks(state)["check_dispatches"][0]["status"] == status


# --- the checks a builder runs through the entrance, against its own launch comparison ------------

import launch_bound  # noqa: E402


@pytest.mark.parametrize("words", [("use", "--job-from-artifact"), ("acceptance-criterion", "--criterion", "C2")])
def test_a_builders_composed_checks_leave_its_launch_comparison_clean(composed, check_source, tmp_path, words):
    """Each check builds trees, records and seat bundles inside a stretch comparison of its own."""
    from comparison_window import comparison_window
    state, _behaviour, seen = composed
    store = Path.home() / ".tradecraft" / "dispatches"
    holder = tmp_path / "holder"
    (holder / ".git").mkdir(parents=True)
    (holder / "tracked.txt").write_bytes(b"x")
    with comparison_window(root=check_source, tmp_path=tmp_path, checkouts=[holder]) as window:
        for words in (words,):
            run_check(state, *words, transport=PostingTransport())
            # The bundle its seat launcher writes, beside the trees and records the entrance wrote.
            write_bundle(store, uuid.uuid4().hex, {
                "dispatch_id": uuid.uuid4().hex, "stage": words[0], "root": str(seen["tree"]),
                "launched_by": {"dispatch_id": "a" * 32}}, {"outcome": "success", "completed_at": "t"},
                {".dispatch.bin": seen["dispatch"], ".source.bin": b"x"})
        state.record_root, state.issue_comments = store, []
        work.builder_checks(state)
    assert any(item["item"].startswith("checkout:") for item in window["plan"])
    assert window["unchanged"]["findings"] == [], window["unchanged"]["findings"]


@pytest.mark.parametrize("change", ["removed", "rewritten"])
def test_a_stretch_pointer_removed_or_rewritten_during_its_launch_is_a_finding(tmp_path, monkeypatch, change):
    home = tmp_path / "home"
    store = home / ".tradecraft" / "dispatches"
    store.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    root = tmp_path / "root"
    root.mkdir()
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    dispatch_id = uuid.uuid4().hex
    pointer_path = launch_tree.write_pointer(store, dispatch_id=dispatch_id, work="o/r#5",
                                             request=store / "x.request.json", run=store / "x.run.json",
                                             session_id="s", launcher=lifecycle.process_identity(), root=root)
    comparison = launch_bound.Comparison(root=root, env={}, launcher_plugin=plugin,
                                         own_output=store / "x", own_request=store / "x.request.json",
                                         holder_session_id=None, dispatch_id=dispatch_id,
                                         own_pointer=pointer_path)
    comparison.take_before(60)
    if change == "removed":
        pointer_path.unlink()
    else:
        pointer_path.write_text("{}", encoding="utf-8")
    result = comparison.finish(60)
    assert [finding["item"] for finding in result["findings"]] == ["own-pointer"]


def test_a_seat_launcher_names_no_stretch_to_anything_it_starts(monkeypatch):
    monkeypatch.setattr(launch_tree, "attribution", lambda *a, **k: {})
    for name in launch_tree.VARIABLES:
        monkeypatch.setenv(name, "a" * 32)
    args = SimpleNamespace(preflight_cap_seconds=None, preflight_cap_reason=None, stage="use",
                           timeout_seconds=0.0)
    with pytest.raises(dispatch_seat.DispatchError):
        dispatch_seat.run_dispatch(args)  # A zero limit stops it before any launch.
    assert [name for name in launch_tree.VARIABLES if name in os.environ] == []


# --- a criterion read on the change's own tree, and a reading recomposed from its source --------------

def commit_change(source):
    """Commit one change on the fixture source; returns (base, head)."""
    base = git_in(source, "rev-parse", "HEAD").stdout.decode().strip()
    (source / "job" / "job.md").write_bytes(b"run the consumer twice\n")
    git_in(source, "-c", "user.name=f", "-c", "user.email=f@f", "commit", "-q", "-am", "change")
    return base, git_in(source, "rev-parse", "HEAD").stdout.decode().strip()


def test_a_criterion_on_the_changes_own_tree_reads_it_at_head(composed, check_source):
    state, behaviour, seen = composed
    base, head = commit_change(check_source)
    state.pr = {"number": 12, "base": {"sha": base}}
    state.artifact_phase.settled_artifact.body = CHECK_ARTIFACT + (
        "\n**C3.** The job runs twice.\nFresh reader: read tree\n")
    transport = PostingTransport()
    run_check(state, "acceptance-criterion", "--criterion", "C3", transport=transport)
    assert (seen["tree"] / "job" / "job.md").read_bytes() == b"run the consumer twice\n"
    assert seen["command"][seen["command"].index("--requires") + 1] == "read"
    assert f"head={head}" in transport.posts[0][1] and "tree=held" in transport.posts[0][1]
    behaviour["edit"] = True
    edited = PostingTransport()
    run_check(state, "acceptance-criterion", "--criterion", "C3", transport=edited)
    assert "tree=changed" in edited.posts[0][1]


def reading(source, tmp_path):
    base, head = commit_change(source)
    metadata_path = work.cold_reader.build_tree(
        source=source, output=tmp_path / "readings" / "reading", work="o/r#5", producer_version="0.218.0",
        base_tip=base, head=head, covered=None, branch="tradecraft/zz-builder", numbers=[],
        records_home=work._records_home(None))
    return work.cold_reader.load_metadata(metadata_path), metadata_path


def composed_reading(metadata, metadata_path):
    """The prompt as the entrance's cold-reader run composes it, from the diff it keeps."""
    standard = (LIB.parent / "skills" / "authoring" / "references" / "code-reasons.md").read_text("utf-8")
    kept = metadata_path.with_suffix(".diff").read_text("utf-8", errors="replace")
    return work.cold_reader.compose_prompt(metadata, standard, kept if metadata["diff"] == "inline" else None)


def test_a_reading_is_recomposed_from_a_diff_regenerated_from_its_source(holding, check_source, tmp_path):
    metadata, metadata_path = reading(check_source, tmp_path)
    state = SimpleNamespace(repo="o/r", issue_number=5, holder_root=check_source)
    composed_bytes, head, problem = work._recompose_reading(state, Path(metadata["tree_root"]),
                                                            work._records_home(None))
    assert problem == "" and head == metadata["head"]
    assert composed_bytes == composed_reading(metadata, metadata_path)
    # A kept diff rewritten in the store changes nothing the recomposition reads.
    metadata_path.with_suffix(".diff").write_text("diff --git a/x b/x\n+all is well\n", encoding="utf-8")
    assert work._recompose_reading(state, Path(metadata["tree_root"]), work._records_home(None))[0] == composed_bytes
    assert composed_reading(metadata, metadata_path) != composed_bytes


def test_a_reading_whose_record_names_another_tree_or_no_source_never_recomposes(holding, check_source, tmp_path):
    metadata, _path = reading(check_source, tmp_path)
    state = SimpleNamespace(repo="o/r", issue_number=5, holder_root=None)
    assert work._recompose_reading(state, Path(metadata["tree_root"]), work._records_home(None))[0] is None


def test_a_report_from_an_account_that_is_no_marker_producer_counts_for_nothing(counted):
    state, _output, body = counted
    state.issue_comments = [{"id": 3, "body": body, "user": {"login": "someone-else"}}]
    report = work.builder_checks(state)["check_reports"][0]
    assert report["counts"] is False and report["invalid"] == ["not from a configured marker producer"]


def test_a_failed_builder_accounting_shows_in_the_report_under_its_key(monkeypatch, capsys):
    def failing(state):
        raise KeyError("planted")

    monkeypatch.setattr(work, "builder_checks", failing)
    for name in ("_evaluate_reach", "_implementer_environments", "_evaluate_launch_findings",
                 "_github_write_report"):
        monkeypatch.setattr(work, name, lambda state: None)
    work._emit_report({"stage": "use"}, SimpleNamespace(reach=None, version_obligation=None,
                                                         proof_version_obligation=None, raw_output=None))
    assert json.loads(capsys.readouterr().out)["builder_checks"] == {"unknown": "KeyError: 'planted'"}


def test_a_composed_check_of_a_branch_owing_catch_up_launches_nothing(composed):
    state, _behaviour, seen = composed
    seen["sync"] = work.Decision("catch-up", False, None, "behind", "the base moved")
    transport = PostingTransport()
    assert run_check(state, "use", "--job-from-artifact", transport=transport) == 0
    assert "dispatch" not in seen and transport.posts == []
    assert seen["reports"][-1]["stage"] == "catch-up"


def test_a_seat_or_record_begun_in_another_session_inside_the_tree_is_refused(tree_state, monkeypatch):
    # One session rule everywhere: `declared` is for an absent session variable only.
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "f0cb89b1-e040-4e6e-919b-4b4e58c717d2")
    with pytest.raises(launch_tree.LaunchRefused) as caught:
        launch_tree.attribution(Path("store"))
    assert caught.value.code == "builder-identity-unproved"


def test_the_launch_worker_names_its_job_as_the_tree_check_opens_it():
    assert seat_process.STRETCH_JOB_VARIABLE == launch_tree.JOB_VARIABLE
    assert launch_tree.job_name("a" * 32) == "Local\\tradecraft-stretch-" + "a" * 32


def test_a_keep_warm_ping_carries_no_stretch_variable():
    import keep_warm
    assert set(launch_tree.VARIABLES) == set(keep_warm.STRETCH_ENV_NAMES)
    child = {"PATH": "p", **{name: "a" * 32 for name in launch_tree.VARIABLES}}
    env_set, env_unset, other = keep_warm.launch_env_changes({"PATH": "p"}, child)
    assert env_set == {} and other == []
    assert keep_warm.ping_environment({"env_set": env_set, "env_unset": env_unset}, {"PATH": "p"}) == {
        "PATH": "p", "PYTHONDONTWRITEBYTECODE": "1"}


def test_a_store_return_rewritten_before_the_post_is_never_posted(composed, tmp_path, monkeypatch):
    state, _behaviour, seen = composed
    original = dispatch_seat.read_return_frame

    def rewritten_after_frame(output):
        frame = original(output)
        # The builder's shell, between the frame and the post, rewrites the launched check's store copy.
        seen["store_copy"].write_bytes(b"A better story.\n")
        return frame

    monkeypatch.setattr(dispatch_seat, "read_return_frame", rewritten_after_frame)
    transport = PostingTransport()
    run_check(state, "use", "--job-from-artifact", transport=transport)
    assert seen["store_copy"].read_bytes() == b"A better story.\n"
    assert transport.posts[0][1].endswith("\n\nThe job ran.\n") and "better story" not in transport.posts[0][1]


def test_a_second_launch_keeps_the_first_launchs_tree_and_report(composed):
    state, _behaviour, seen = composed
    transport = PostingTransport()
    run_check(state, "use", "--job-from-artifact", transport=transport)
    first = seen["reports"][-1]["tree_metadata"]
    run_check(state, "use", "--job-from-artifact", transport=transport)
    assert seen["reports"][-1]["tree_metadata"] != first and Path(first).is_file()
    assert len(transport.posts) == 2


@pytest.mark.parametrize("change, credited", [
    ({"revision_before": "b", "status_before": "s2"}, True),
    ({"revision_before": "b", "branch": "other"}, False),
    ({"holder_root": "elsewhere"}, False),
])
def test_only_the_own_rows_re_snapshot_is_credited(tmp_path, change, credited):
    own = tmp_path / "implementation"
    before = {"root": str(own), "revision_before": "a", "status_before": "s1", "branch": "b1", "holder_root": "h"}
    entry = {"item": "registry", "change": "row-changed", "path": str(own), "rows": (before, {**before, **change})}
    assert launch_bound._own_row_resnapshot(entry, own) is credited
    elsewhere = {**entry, "rows": ({**before, "root": "x"}, {**before, **change, "root": "x"})}
    assert launch_bound._own_row_resnapshot(elsewhere, own) is False


def test_a_builders_check_follows_its_launchers_window():
    # The child outlives the first bound; the window the launcher opens keeps the wait for it.
    captured = bytearray()
    moved = []

    def follower():
        if not moved:
            moved.append(lifecycle.time.monotonic())
            return moved[0] + 30, moved[0] + 31
        return None

    command = [sys.executable, "-c", "import time; time.sleep(1.5); print('returned')"]
    result = work._framed_recipient_run(captured)(command, timeout=0.5,
                                                  cleanup_deadline=lifecycle.time.monotonic() + 0.75,
                                                  on_tick=follower)
    assert result.returncode == 0 and moved and captured.strip() == b"returned"


def test_a_builders_first_check_takes_its_vendor_from_its_own_launch(composed):
    state, _behaviour, seen = composed
    run_check(state, "use", "--job-from-artifact", transport=PostingTransport())
    command = seen["command"]
    assert command[command.index("--own-vendor") + 1] == "claude"
    assert command[command.index("--own-vendor-source") + 1].startswith("holding stretch launch request")


@pytest.mark.parametrize("hold", ["account", "version"])
@pytest.mark.parametrize("words", [("use", "--job-from-artifact"), ("acceptance-criterion", "--criterion", "C2")])
def test_a_composed_check_passes_the_holds_a_named_stage_passes(composed, hold, words):
    state, _behaviour, seen = composed
    seen[hold] = work.Decision("launch-account", False, None, f"{hold}-hold", "", status="holder-owned")
    transport = PostingTransport()
    assert run_check(state, *words, transport=transport) == 0
    assert "dispatch" not in seen and transport.posts == []
    assert seen["reports"][-1]["reason"] == f"{hold}-hold"


def test_a_failed_settlement_supplies_no_artifact(composed):
    state, _behaviour, seen = composed
    state.artifact_phase.source_error = "artifact settlement: the latest marker is invalid"
    with pytest.raises(work.BuilderRefused) as caught:
        run_check(state, "use", "--job-from-artifact", transport=PostingTransport())
    assert caught.value.code == "artifact-source-unusable" and "dispatch" not in seen


def test_a_builders_check_runs_only_on_its_own_launchs_root(composed, tmp_path, monkeypatch):
    state, _behaviour, seen = composed
    monkeypatch.setattr(work, "resolve_implementation_root",
                        lambda *a, **k: (tmp_path / "another", "tradecraft/zz-other", False))
    with pytest.raises(work.BuilderRefused) as caught:
        run_check(state, "use", "--job-from-artifact", transport=PostingTransport())
    assert caught.value.code == "builder-root-mismatch" and "dispatch" not in seen


def test_a_builders_instalment_is_its_own_registration(holding, tmp_path, monkeypatch):
    registry = work.registry_path()
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({"schema_version": 1, "worktrees": [
        {"root": str(tmp_path / "implementation"), "holder_root": str(tmp_path / "holder"), "instalment": "1"}]}),
        encoding="utf-8")
    holder = str(tmp_path / "holder")
    assert refused(arguments("run", "proof", "--instalment", "2", root=holder)) == "builder-root-mismatch"
    seen = {}
    monkeypatch.setattr(work, "_run_entry", lambda args, transport, executor: seen.setdefault("args", args) and 0)
    args = arguments("run", "proof", root=holder)
    assert work.run(args, transport=NoTransport()) == 0
    assert seen["args"].instalment == "1"


def test_a_tree_built_from_an_earlier_declaration_does_not_recompose(counted):
    state, _output, _body = counted
    phase = state.artifact_phase
    phase.settled_artifact = SimpleNamespace(body=phase.settled_artifact.body.replace(
        '"paths": ["job"]', '"paths": ["job", "skill"]'), source_id="78")
    checks = work.builder_checks(state)
    assert checks["check_dispatches"][0]["status"] == "differs"
    assert "earlier declaration use" in checks["check_dispatches"][0]["reason"]
    assert checks["check_reports"][0]["counts"] is False


def test_a_heading_or_opening_inside_a_fenced_example_is_not_the_plans_own():
    example = "~~~markdown\n## Use session job\n\n```text\nnot this\n```\n~~~\n\n"
    artifact = "## How a plan reads\n\n" + example + ARTIFACT.replace("\r\n", "\n")
    assert work.artifact_use_job(artifact) == b"Use the tree as an adopter would.\nReport what broke.\n"
    criterion = ("**C3.** The command works:\n\n```bash\n# set up\n**C4.** quoted\npython x.py\n```\n"
                 "Fresh reader: execute tree\n\n## After\n")
    text = work.artifact_criterion(criterion, "C3")
    assert "python x.py" in text and work.criterion_reader(text) == ("execute", None)


@pytest.mark.parametrize("session", ["", None])
def test_an_empty_session_variable_is_an_absent_one(holding, tree_state, monkeypatch, session):
    tree_state["value"] = launch_tree.Holding("held", dict(LAUNCH))
    if session is not None:
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", session)
    # The seat launcher and a record begin read who launched them through attribution.
    assert launch_tree.attribution(Path("store"))["launched_by"]["identity"] == "declared"
    holding["value"] = launch_tree.Holding("held", {**dict(LAUNCH), "root": None})
    assert work._builder_identity(arguments("run", "use"))["identity"] == "declared"


def test_a_reader_that_writes_beside_its_tree_holds_and_inside_it_reads_changed(composed):
    state, behaviour, seen = composed
    behaviour["beside"] = True
    transport = PostingTransport()
    run_check(state, "use", "--job-from-artifact", transport=transport)
    assert "tree=held" in transport.posts[0][1]
    assert (seen["tree"].parent / "probe-evidence.txt").is_file()
    told = seen["dispatch"].decode()
    assert f"Write what you make in {seen['tree'].parent}" in told and "with shell commands" in told
    assert "session scratchpad for file-tool writes" in told and "write nothing in it" in told and "-B" in told
    assert seen["tree"].parent.name.startswith("tradecraft-check-")
    behaviour["edit"] = True
    run_check(state, "use", "--job-from-artifact", transport=transport)
    assert "tree=changed" in transport.posts[1][1]


def test_a_read_only_criterion_is_told_its_return_bound_and_not_the_working_space(composed):
    told = work.compose_check_dispatch("acceptance-criterion", {
        "criterion": "**C9.** x\nFresh reader: read tree\n", "capability": "read", "head": "h", "tree": "/t/tree"})
    assert b"Return at most 240,000 UTF-8 bytes." in told and b"must stay as built" not in told


def test_a_return_too_large_to_post_posts_its_size_and_never_counts(composed, monkeypatch):
    state, _behaviour, _seen = composed
    original = work.check_report_body
    size = work.COMMENT_LIMIT_BYTES + 10
    # The frame's return, grown past GitHub's limit (a command line can't carry one that large).
    monkeypatch.setattr(work, "check_report_body", lambda **k: original(**k).partition("\n\n")[0]
                        + "\n\n" + "x" * size)
    transport = PostingTransport()
    assert run_check(state, "use", "--job-from-artifact", transport=transport) == 1
    (endpoint, body), = transport.posts
    marker, text = body.split("\n\n", 1)
    assert "tradecraft:check-report:v1" in marker
    assert text == f"The return was too large to post: {size} bytes."
    assert len(body.encode("utf-8")) < work.COMMENT_LIMIT_BYTES
    assert _seen["reports"][-1]["check_report"]["status"] == "check-report-oversized"


def test_a_refused_check_leaves_no_tree_behind(composed, tmp_path):
    state, _behaviour, seen = composed
    Path(work.builder_mode()["request"]).unlink()  # The holding launch's vendor can't be read.
    with pytest.raises(work.WorkError, match="could not be read"):
        run_check(state, "use", "--job-from-artifact", transport=PostingTransport())
    assert "dispatch" not in seen and not list((tmp_path / "temp").iterdir())


def test_a_builders_reading_takes_its_vendor_from_its_own_launch(composed, monkeypatch):
    monkeypatch.setattr(work, "_producer_vendor", lambda *a, **k: pytest.fail("read a completed producer bundle"))
    vendor, source = work._cold_reading_builder_vendor(SimpleNamespace(), "h")
    assert vendor == "claude" and source.startswith("holding stretch launch request")


def test_a_check_whose_tree_cant_be_built_leaves_no_folder_behind(composed, tmp_path, monkeypatch):
    state, _behaviour, seen = composed

    def unbuildable(**_kwargs):
        raise work.recipient_tree.RecipientTreeError("fixture: the declaration names no file")

    monkeypatch.setattr(work.recipient_tree, "create_consumer_tree", unbuildable)
    with pytest.raises(work.WorkError, match="could not be built"):
        run_check(state, "use", "--job-from-artifact", transport=PostingTransport())
    assert "dispatch" not in seen and not list((tmp_path / "temp").iterdir())


def test_1011_a_comment_that_quotes_the_report_marker_is_set_aside_not_counted(counted):
    state, _output, body = counted
    marker = body.split("\n", 1)[0]
    quoting = {
        2: f"The entrance posted `{marker}` above.\n",
        3: f"```text\n{marker}\n```\n",
        4: f"An example:\n\n    {marker}\n",
        5: f"> {marker}\n>\n> The job ran.\n",
    }
    state.issue_comments = [{"id": 1, "body": body, "user": {"login": "producer"}}] + [
        {"id": identity, "body": text, "user": {"login": "producer"}} for identity, text in quoting.items()]
    checks = work.builder_checks(state)
    assert [report["comment"] for report in checks["check_reports"]] == [1]
    assert checks["check_reports"][0]["counts"] is True
    assert [quotation["source"]["id"] for quotation in checks["quotations"]] == [2, 3, 4, 5]
    assert {quotation["name"] for quotation in checks["quotations"]} == {"check-report"}

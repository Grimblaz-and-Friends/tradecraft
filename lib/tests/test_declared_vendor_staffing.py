"""A builder-mode seat is staffed against its builder's vendor: a hand-started builder's declared one, ignoring
case, and a launched builder's observed one, with the seat itself always launched on its own vendor.

Design: lib/DESIGN.md#the-builder-route
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import dispatch_seat  # noqa: E402
import launch_tree  # noqa: E402
import work  # noqa: E402
# The builder-mode check fixtures, reused so these seats run the same composed check those tests drive.
from test_builder_mode import arguments, check_source, composed, holding, PostingTransport  # noqa: E402,F401

STAND_IN = Path(__file__).resolve().parent / "seat_cli.py"
# The holding fixture replaces the tree check; a hand-started record is held only by the real one.
TREE_CHECK = launch_tree.stretch_holding
CHECKS = {"use": ("use", "--job-from-artifact"), "acceptance-criterion": ("acceptance-criterion", "--criterion", "C2")}


@pytest.fixture()
def seated(composed, tmp_path, monkeypatch, capfd):
    """The composed check with its real seat launcher run in this process, its vendor CLI the stand-in."""
    state, _behaviour, seen = composed
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps({"claude": {"message": "The job ran.\n"}}), encoding="utf-8")
    monkeypatch.setattr(dispatch_seat, "resolve_command", lambda vendor, _explicit: [
        sys.executable, str(STAND_IN), vendor, str(scenario)])
    monkeypatch.setattr(dispatch_seat.records, "runtime_version", lambda *_: "fixture-cli 1.0")
    monkeypatch.setattr(dispatch_seat, "is_windows", lambda: False)

    def invoke(command, deadline, runner=None):
        # The seat's stdout reaches the entrance as the framed runner keeps it, which is the buffer here.
        seen["command"] = list(command)
        code = dispatch_seat.run_dispatch(dispatch_seat.parser().parse_args(command[2:]))
        seen["stdout"] = capfd.readouterr().out
        runner.extend(seen["stdout"].encode("utf-8"))
        return code

    monkeypatch.setattr(work, "_framed_recipient_run", lambda captured: captured)
    monkeypatch.setattr(work, "_invoke_recipient", invoke)
    return state, seen


def hand_builder(monkeypatch, root, vendor):
    """Hold this process as a builder the owner started by hand, declaring ``vendor``, as the entrance reads one."""
    made = launch_tree.write_hand_record(work.records.default_record_root(), work="o/r#5", vendor=vendor,
                                         model="declared-model", handoff={"tree": str(root)})
    monkeypatch.setattr(launch_tree, "stretch_holding", TREE_CHECK)
    monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, made["dispatch_id"])
    builder = work._builder_identity(arguments("run", "use", "--job-from-artifact"))
    assert builder is not None and builder["dispatch_id"] == made["dispatch_id"]
    work._BUILDER.set(builder)
    return builder


def seat_records(stage):
    """The seat's request and run records, from the store its launcher wrote them to."""
    [request_path] = [path for path in work.records.default_record_root().rglob("*.request.json")
                      if json.loads(path.read_bytes()).get("stage") == stage]
    run_path = request_path.with_name(request_path.name[:-len(".request.json")] + ".run.json")
    return json.loads(request_path.read_bytes()), json.loads(run_path.read_bytes())


def printed_plans(stdout):
    """The launch plans the entrance and its seat print, by label; each attempt's own line is not a plan."""
    plans = (line.split(": launch_settings ", 1) for line in stdout.splitlines())
    return {pair[0]: json.loads(pair[1]) for pair in plans if len(pair) == 2 and pair[0] in ("work", "seat")}


def option(command, name):
    return command[command.index(name) + 1] if name in command else None


def run_seat(state, stage):
    transport = PostingTransport()
    assert work._builder_check(state, arguments("run", *CHECKS[stage]), Path("holder"), transport, "60") == 0
    (_endpoint, body), = transport.posts
    return body.split("\n\n", 1)[0]


@pytest.mark.parametrize("stage", sorted(CHECKS))
def test_a_seat_under_a_hand_builder_declaring_claude_is_degraded_for_the_declared_vendor(
        seated, check_source, monkeypatch, stage):
    state, seen = seated
    hand_builder(monkeypatch, check_source, "claude")
    marker = run_seat(state, stage)
    command = seen["command"]
    assert option(command, "--vendor") == "claude" and option(command, "--own-vendor") == "claude"
    assert option(command, "--same-vendor-reason") == "declared-builder-vendor"
    assert option(command, "--builder-vendor-source") == "declared"
    request, run = seat_records(stage)
    assert request["builder_vendor_source"] == "declared" and request["comparison_vendor"] == "claude"
    assert (run["actual_vendor"], run["staffing_status"]) == ("claude", "degraded")
    assert run["staffing_qualification"]["same_vendor_reason"] == "declared-builder-vendor"
    assert "builder_vendor=declared" in marker and "staffing_status=degraded" in marker
    assert "same_vendor_reason=declared-builder-vendor" in marker


@pytest.mark.parametrize("stage", sorted(CHECKS))
@pytest.mark.parametrize("declared, compared", [("Gemini", "gemini"), ("codex", "codex")])
def test_a_seat_under_a_hand_builder_declaring_another_vendor_stays_on_claude_and_is_cross_vendor(
        seated, check_source, monkeypatch, stage, declared, compared):
    state, seen = seated
    hand_builder(monkeypatch, check_source, declared)
    marker = run_seat(state, stage)
    command = seen["command"]
    assert option(command, "--vendor") == "claude" and option(command, "--own-vendor") == compared
    assert "--same-vendor-reason" not in command and option(command, "--builder-vendor-source") == "declared"
    request, run = seat_records(stage)
    assert request["builder_vendor_source"] == "declared" and request["comparison_vendor"] == compared
    assert (run["actual_vendor"], run["staffing_status"]) == ("claude", "qualified")
    assert run["staffing_qualification"]["same_vendor_reason"] is None
    assert "builder_vendor=declared" in marker and "staffing_status=qualified" in marker
    assert "same_vendor_reason=" not in marker
    plans = printed_plans(seen["stdout"])
    assert set(plans) == {"work", "seat"}
    assert plans["seat"]["fallback"]["vendor"] == compared
    if compared == "gemini":
        # A vendor with no launcher here is compared against and never launched, in either plan.
        assert [plan["fallback"].get("vendor") for plan in plans.values()] == ["gemini", "gemini"]
        assert [plan["fallback"]["eligible"] for plan in plans.values()] == [False, False]
        assert all("gemini" in plan["fallback"]["unavailable_reason"] for plan in plans.values())


@pytest.mark.parametrize("stage", sorted(CHECKS))
def test_a_seat_under_a_launched_claude_builder_keeps_the_owner_selected_reason_without_the_fields(
        seated, stage):
    state, seen = seated
    marker = run_seat(state, stage)
    command = seen["command"]
    assert option(command, "--vendor") == "claude" and option(command, "--own-vendor") == "claude"
    assert option(command, "--same-vendor-reason") == "owner-selected-claude-implementer"
    assert "--builder-vendor-source" not in command
    request, run = seat_records(stage)
    assert "builder_vendor_source" not in request
    assert run["staffing_qualification"]["same_vendor_reason"] == "owner-selected-claude-implementer"
    assert "builder_vendor=" not in marker


# --- the staffing every builder-mode seat takes, and the launcher's side of it -------------------------


@pytest.mark.parametrize("declared, seat, staffing", [
    ("claude", "claude", ["--builder-vendor-source", "declared", "--same-vendor-reason", "declared-builder-vendor"]),
    ("Claude", "claude", ["--builder-vendor-source", "declared", "--same-vendor-reason", "declared-builder-vendor"]),
    ("Gemini", "claude", ["--builder-vendor-source", "declared"]),
    ("codex", "claude", ["--builder-vendor-source", "declared"]),
    # A cold reader the owner moved to Codex is degraded under a builder declaring Codex.
    ("Codex", "codex", ["--builder-vendor-source", "declared", "--same-vendor-reason", "declared-builder-vendor"]),
])
def test_a_hand_builders_seat_is_compared_with_its_declared_vendor_ignoring_case(
        holding, tmp_path, monkeypatch, declared, seat, staffing):
    builder = hand_builder(monkeypatch, tmp_path, declared)
    own_vendor, _source = work._holding_launch_vendor(builder)
    assert own_vendor == declared
    assert work._seat_staffing(builder, own_vendor, seat, "owner-selected-claude-implementer") == (
        declared.lower(), staffing)


@pytest.mark.parametrize("reason, staffing", [
    ("owner-selected-claude-implementer", ["--same-vendor-reason", "owner-selected-claude-implementer"]),
    (None, [])])
def test_a_launched_builders_seat_keeps_its_launched_reason(holding, tmp_path, reason, staffing):
    from comparison_window import held_builder, stretch_launch
    builder = held_builder(stretch_launch(tmp_path / "store", root=tmp_path))
    assert work._seat_staffing(builder, "claude", "claude", reason) == ("claude", staffing)
    assert work._seat_staffing(None, "codex", "claude", reason) == ("codex", staffing)


def seat_arguments(*extra):
    return dispatch_seat.parser().parse_args([
        "--dispatch", "d", "--root", "r", "--vendor", "claude", "--work", "o/r#5", "--stage", "cold-reader",
        "--settings-source", "s", "--settings-scope", "s", "--classification", "cold", "--requires", "read", *extra])


def test_the_launcher_takes_any_declared_vendor_lower_cased_and_never_falls_back_to_one_it_cannot_launch():
    args = seat_arguments("--own-vendor", "Gemini", "--builder-vendor-source", "declared")
    assert (args.own_vendor, args.builder_vendor_source) == ("gemini", "declared")
    plan = dispatch_seat.fallback_plan("claude", "gemini", "read")
    assert plan["eligible"] is False and "gemini" in plan["unavailable_reason"]
    assert dispatch_seat.fallback_plan("claude", "claude", "read")["eligible"] is False
    assert seat_arguments("--own-vendor", "codex").builder_vendor_source is None
    with pytest.raises(SystemExit):
        seat_arguments("--own-vendor", "codex", "--builder-vendor-source", "observed")


# --- a builder's cold reading, staffed the same way -----------------------------------------------------

from test_cold_reader import change, clean  # noqa: E402,F401


def builder_reading(change, monkeypatch, capfd, declared):
    """A builder runs a whole `run cold-reader`: one started by hand declaring ``declared``, or with None a launched
    Claude builder. Returns its seat's command, its request and run records, and its posted report's marker."""
    import preflight
    import run_lifecycle as lifecycle
    scenario = change.tmp / "scenario.json"
    scenario.write_text(json.dumps({"claude": {"message": clean()}}), encoding="utf-8")
    output = change.store / "seat-reading" / "result.md"
    # The entrance resolves each vendor before launch, so a machine without either CLI still reaches the stand-in.
    monkeypatch.setattr(work, "_runtime_argument", lambda vendor, _explicit=None: [f"--{vendor}", str(STAND_IN)])
    monkeypatch.setattr(dispatch_seat, "resolve_command", lambda vendor, _explicit: [
        sys.executable, str(STAND_IN), vendor, str(scenario)])
    monkeypatch.setattr(dispatch_seat.records, "runtime_version", lambda *_: "fixture-cli 1.0")
    monkeypatch.setattr(dispatch_seat, "is_windows", lambda: False)
    commands = []

    def invoke(command, deadline, runner=None):
        commands.append(command)
        code = dispatch_seat.run_dispatch(dispatch_seat.parser().parse_args(
            [*command[2:], "--invocation-started-monotonic", str(deadline.started)]))
        runner.extend(capfd.readouterr().out.encode("utf-8"))
        return code

    monkeypatch.setattr(work, "_framed_recipient_run", lambda captured: captured)
    monkeypatch.setattr(work, "_invoke_recipient", invoke)
    # A builder's reading takes its comparison vendor from its own record, never a completed bundle.
    monkeypatch.setattr(work, "_producer_vendor", lambda *_a, **_k: pytest.fail("read a completed producer bundle"))
    monkeypatch.setattr(work.records, "resolved_output", lambda *_a: output)
    fixture = change.state()
    work.validate_marker_claims(fixture)
    if declared is None:
        # A launched Claude builder, whose vendor its own launch observed.
        from comparison_window import held_builder, stretch_launch
        launch = stretch_launch(change.tmp / "launch-store", root=change.tmp, vendor="claude",
                                work_id=f"{fixture.repo}#{fixture.issue_number}")
        monkeypatch.setattr(launch_tree, "stretch_holding", lambda store: launch_tree.Holding("held", launch))
        builder = held_builder(launch)
    else:
        made = launch_tree.write_hand_record(work.records.default_record_root(), vendor=declared,
                                             model="declared-model", work=f"{fixture.repo}#{fixture.issue_number}",
                                             handoff={"tree": str(change.root)})
        monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, made["dispatch_id"])
        builder = work._builder_identity(SimpleNamespace(repo=fixture.repo, issue=fixture.issue_number))
        assert builder is not None and builder["dispatch_id"] == made["dispatch_id"]
    posts = []

    class Posting:
        def post(self, endpoint, payload):
            posts.append(payload["body"])
            return {"id": 1}

    token = work._BUILDER.set(builder)
    try:
        with preflight.scope(started=lifecycle.time.monotonic()) as opened:
            deadline = lifecycle.stage_deadline("cold-reader", 1800, started=opened.started, declared=True)
            with lifecycle.deadline_scope(deadline):
                assert work._execute_cold_reader(
                    fixture, work.Decision("cold-reader", True, "fresh", "holder-named-stage"),
                    dispatch_path=None, tree_metadata=None, timeout_seconds=1800,
                    claude_path=None, codex_path=None, transport=Posting()) == 0
    finally:
        work._BUILDER.reset(token)
    [command] = commands
    [body] = posts
    return (command, json.loads(output.with_name("result.md.request.json").read_bytes()),
            json.loads(output.with_name("result.md.run.json").read_bytes()), body.split("\n\n", 1)[0])


@pytest.mark.cold_reading
@pytest.mark.parametrize("declared, compared, status, reason", [
    ("claude", "claude", "degraded", "declared-builder-vendor"),
    ("Gemini", "gemini", "qualified", None),
    ("codex", "codex", "qualified", None)])
def test_a_hand_builders_cold_reading_is_staffed_against_its_declared_vendor(
        change, monkeypatch, capfd, declared, compared, status, reason):
    command, request, run, marker = builder_reading(change, monkeypatch, capfd, declared)
    assert option(command, "--vendor") == "claude" and option(command, "--own-vendor") == compared
    assert option(command, "--same-vendor-reason") == reason
    assert option(command, "--builder-vendor-source") == "declared"
    assert request["builder_vendor_source"] == "declared" and request["comparison_vendor"] == compared
    assert (run["actual_vendor"], run["staffing_status"]) == ("claude", status)
    assert run["staffing_qualification"]["same_vendor_reason"] == reason
    assert "stage=cold-reader" in marker and "builder_vendor=declared" in marker
    assert f"staffing_status={status}" in marker and ("same_vendor_reason=" in marker) is (reason is not None)


@pytest.mark.cold_reading
def test_a_launched_claude_builders_cold_reading_keeps_the_owner_selected_reason_without_the_fields(
        change, monkeypatch, capfd):
    command, request, run, marker = builder_reading(change, monkeypatch, capfd, None)
    assert option(command, "--vendor") == "claude" and option(command, "--own-vendor") == "claude"
    assert option(command, "--same-vendor-reason") == "owner-selected-claude-implementer"
    assert "--builder-vendor-source" not in command and "builder_vendor_source" not in request
    assert run["staffing_qualification"]["same_vendor_reason"] == "owner-selected-claude-implementer"
    assert "builder_vendor=" not in marker

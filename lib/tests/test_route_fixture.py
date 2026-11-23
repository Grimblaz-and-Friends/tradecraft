"""The route fixture runs from an exported copy of lib/ and prints the decision each scenario names."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import route_fixture  # noqa: E402

STAGES = {"handoff-due": "handoff", "handoff": "handoff", "with-builder": "with-builder",
          "stretch-stopped": "stretch-stopped", "cannot-launch": "stretch-stopped",
          "final-pass": "final-pass", "ready-reported": "final-pass", "catch-up": "catch-up",
          "hand-started": "with-builder",
          # Today's relay chain: with the plan settled and no pull request, a build is next.
          "relay-in-flight": "build", "relay-default": "build"}


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    """lib/ alone, copied outside every registered worktree, as the use session's declared tree holds it."""
    export = tmp_path_factory.mktemp("export")
    root = export / "lib"
    shutil.copytree(LIB, root, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return root


def fixture_run(exported, *words):
    return subprocess.run([sys.executable, "-B", str(exported / "tests" / "route_fixture.py"), *words],
                          capture_output=True, stdin=subprocess.DEVNULL, timeout=240, cwd=str(exported.parent))


def test_list_names_every_scenario(exported):
    result = fixture_run(exported, "--list")
    assert result.returncode == 0, result.stderr
    assert result.stdout.decode("ascii").split("\n") == [*route_fixture.SCENARIOS, ""]
    assert set(route_fixture.SCENARIOS) == set(STAGES)


@pytest.mark.parametrize("name", sorted(STAGES))
def test_each_scenario_prints_the_decision_it_names(exported, name):
    result = fixture_run(exported, name)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    report = json.loads(result.stdout.decode("utf-8").split("\n", 1)[0])
    assert report["stage"] == STAGES[name]
    assert report["route"]["name"] == ("relay" if "relay" in name else "builder")
    if name == "final-pass":
        detail = json.loads(report["detail"])
        # The stand-in builder reported ready on a draft pull request, so readying reviewers is still its own.
        assert {key: detail[key] for key in ("record", "reconciled", "unreconciled")} == {
            "record": report["readiness"]["record"], "reconciled": True, "unreconciled": []}
        assert detail["owed_at_ready"]["stage"] == "ready-reviewers"
        assert [entry["counts"] for entry in report["builder_checks"]["check_reports"]] == [True]
    if name == "cannot-launch":
        assert report["reason"] == "cannot-launch"
    if name == "ready-reported":
        # Reach was read from the holder's Git rather than stubbed, and the payload follows the decision.
        assert (report["reason"], report["reach"]["state"]) == ("ready-reported", "clear")
        payload = json.loads(result.stdout.decode("utf-8").split("builder_route ---\n", 1)[1])
        assert payload["route"]["name"] == "builder" and payload["handoff_plan"]["reading"] == "composed"


def test_the_handoff_carries_the_brief_the_plan_and_the_floor_command(exported):
    result = fixture_run(exported, "handoff")
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    text = result.stdout.decode("utf-8").split("--- composed handoff ---\n", 1)[1]
    assert "A stand-in product change whose job an adopter runs." in text
    assert route_fixture.PLAN.strip() in text
    assert "```text\n" + route_fixture.FLOOR + "\n```" in text
    assert "--criterion C2" in text and "--job-from-artifact" in text


def test_1011_a_builder_route_proof_takes_its_use_and_floor_from_the_builders_evidence(tmp_path):
    fixture = route_fixture.Fixture(tmp_path)
    try:
        state = route_fixture.ready_at_head(fixture, route_fixture.CLEAR)
        work = fixture.work
        state.changed_paths = ["job/job.md"]
        state.policy_sources = {key: {"repository": route_fixture.REPO, "path": key, "revision": "a" * 40,
                                      "sha256": "1" * 64} for key in ("work_configuration", "use_rules")}
        work.validate_marker_claims(state)
        work._prepare_builder_use(state, None, route_fixture.RULES, state.pr["head"]["sha"])
        composed = work.compose_proof(state, route_fixture.RULES)
    finally:
        fixture.stop()
    work.proof_document.validate(composed)
    assert not {item["code"] for item in composed["diagnostics"]} & {"use-missing", "floor-missing"}
    assert [(item["stage"], item["status"]) for item in composed["declarations"]] == [
        ("floor", "declared"), ("use", "declared")]

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
          "final-pass": "final-pass", "catch-up": "catch-up", "hand-started": "with-builder",
          # Today's relay chain: with the plan settled and no pull request, a build is next.
          "relay-in-flight": "build", "relay-default": "build"}


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    """lib/ and the plugin manifest it reads its version from, copied outside every registered worktree."""
    export = tmp_path_factory.mktemp("export")
    root = export / "lib"
    shutil.copytree(LIB, root, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    shutil.copytree(LIB.parent / ".claude-plugin", export / ".claude-plugin")
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


def test_the_handoff_carries_the_brief_the_plan_and_the_floor_command(exported):
    result = fixture_run(exported, "handoff")
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    text = result.stdout.decode("utf-8").split("--- composed handoff ---\n", 1)[1]
    assert "A stand-in product change whose job an adopter runs." in text
    assert route_fixture.PLAN.strip() in text
    assert "```text\n" + route_fixture.FLOOR + "\n```" in text
    assert "--criterion C2" in text and "--job-from-artifact" in text

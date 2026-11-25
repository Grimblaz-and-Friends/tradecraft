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
import work  # noqa: E402

STAGES = {"handoff-due": "handoff", "handoff": "handoff", "with-builder": "with-builder",
          "stretch-stopped": "stretch-stopped", "cannot-launch": "stretch-stopped",
          "final-pass": "final-pass", "ready-reported": "final-pass", "catch-up": "catch-up",
          "hand-started": "with-builder", "reviewers-read": "final-pass",
          # The stand-in stretch ran under a write bound and recorded no comparison, so the holder owes its account.
          "launch-account-held": "launch-account",
          # Today's relay chain: with the plan settled and no pull request, a build is next.
          "relay-in-flight": "build", "owner-asked-relay": "build"}
# The step each moment of one change is given, as (stage, reason): on the builder route the one the live builder's
# read-back names first, on the relay route the decision itself.
STEPS = {"builder-built": ("ready-reviewers", "floor-complete-pr-draft"),
         "builder-reporting": ("acceptance-criterion", "criterion-report-absent"),
         "builder-reported": ("review-disposition", "reviewer-thread-lacks-disposition"),
         "builder-answered": ("cold-reader", "cold-reading-absent"),
         "relay-built": ("ready-reviewers", "floor-complete-pr-draft"),
         "relay-reporting": ("use", "pull-request-use-absent"),
         "relay-reported": ("review-disposition", "reviewer-thread-lacks-disposition"),
         "relay-answered": ("cold-reader", "cold-reading-absent")}
PRINTED = {}


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


def printed(exported, name: str) -> str:
    """What scenario NAME prints, run once in each worker, since several tests read one run."""
    if name not in PRINTED:
        result = fixture_run(exported, name)
        assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
        PRINTED[name] = result.stdout.decode("utf-8")
    return PRINTED[name]


def test_list_names_every_scenario(exported):
    result = fixture_run(exported, "--list")
    assert result.returncode == 0, result.stderr
    assert result.stdout.decode("ascii").split("\n") == [*route_fixture.SCENARIOS, ""]
    assert set(route_fixture.SCENARIOS) == set(STAGES) | set(STEPS)


@pytest.mark.parametrize("name", sorted(STAGES))
def test_each_scenario_prints_the_decision_it_names(exported, name):
    text = printed(exported, name)
    report = json.loads(text.split("\n", 1)[0])
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
    if name == "launch-account-held":
        assert report["reason"] == "launch-findings-unaccounted"
        assert [bundle["state"] for bundle in report["launch_findings"]["bundles"]] == ["unrecorded"]
    if name == "ready-reported":
        # Reach was read from the holder's Git rather than stubbed, and the payload follows the decision.
        assert (report["reason"], report["reach"]["state"]) == ("ready-reported", "clear")
        section, payload = text.split("reviewers_read ---\n", 1)[1].split("--- the release report's builder_route")
        payload = json.loads(payload.split("\n", 1)[1])
        assert payload["route"]["name"] == "builder" and payload["handoff_plan"]["reading"] == "composed"
        # Nothing followed the head marked ready, so the reviewers read what merges.
        assert json.loads(section)["changed_after"]["nothing_changed"] is True


def step(report: dict) -> tuple[str, str]:
    """The decision's stage and reason, or for a live builder the first step its ``if_ended`` reading owes."""
    if report["stage"] != "with-builder":
        return report["stage"], report["reason"]
    ended = json.loads(report["detail"])["if_ended"]
    assert (ended["stage"], ended["reason"]) == ("final-pass", "owed-at-ready")
    owed = json.loads(ended["detail"])["owed_at_ready"]
    return owed["stage"], owed["reason"]


@pytest.mark.parametrize("name", sorted(STEPS))
def test_each_moment_of_a_change_prints_the_step_the_entrance_gives_it(exported, name):
    report = json.loads(printed(exported, name).split("\n", 1)[0])
    assert report["route"]["name"] == name.split("-", 1)[0]
    assert step(report) == STEPS[name]


def test_the_relay_ready_step_says_what_ready_means(exported):
    report = json.loads(printed(exported, "relay-built").split("\n", 1)[0])
    assert report["detail"] == work._draft_ready_detail(False)


def test_the_relay_answers_and_reading_wait_in_words_for_the_readers_the_entrance_cannot_read(exported):
    answers = json.loads(printed(exported, "relay-reported").split("\n", 1)[0])
    assert answers["detail"] == "501; " + work._relay_batch_detail(False)
    reading = json.loads(printed(exported, "relay-answered").split("\n", 1)[0])
    assert json.loads(reading["detail"])["before_reading"] == work._relay_reading_detail(False)


def test_a_cold_reading_named_before_the_reports_is_refused_naming_the_step_first(exported):
    refusal = json.loads(printed(exported, "builder-reporting").split("--- run cold-reader, named now ---\n", 1)[1])
    assert (refusal["status"], refusal["reason"]) == ("refused", "cold-reading-not-yet-owed")
    assert "take acceptance-criterion (criterion-report-absent) first" in refusal["detail"]


def test_the_release_report_says_what_changed_after_the_head_the_reviewers_read(exported):
    report, section = printed(exported, "reviewers-read").split("\n--- the release report's reviewers_read ---\n")
    assert json.loads(report)["reason"] == "ready-reported"
    section = json.loads(section)
    changed = section["changed_after"]
    assert (section["head"]["commit"], changed["to"]) == (changed["from"], json.loads(report)["floor"]["head"])
    assert ([entry["path"] for entry in changed["files"]], changed["nothing_changed"]) == (["job/job.md"], False)
    # The fix followed the reviewer's report on that head, but this stand-in's handoff records no owed checks, so
    # the criterion reports are unread and the field can't read false.
    fix = section["fix_before_last_report"]
    assert fix["status"] == "unknown" and "the handoff names no owed checks" in fix["reason"]
    assert "1 file and +1/-1 lines changed between it and" in section["sentence"]


def test_the_handoff_carries_the_brief_the_plan_and_the_floor_command(exported):
    result = fixture_run(exported, "handoff")
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    text = result.stdout.decode("utf-8").split("--- composed handoff ---\n", 1)[1]
    assert "A stand-in product change whose job an adopter runs." in text
    assert route_fixture.PLAN.strip() in text
    assert "```text\n" + route_fixture.FLOOR + "\n```" in text
    assert "--criterion C2" in text and "--job-from-artifact" in text


@pytest.mark.parametrize("mechanical", [False, True])
def test_the_handoff_decision_names_the_builder_its_printed_text_is_for(exported, mechanical):
    result = fixture_run(exported, "handoff", *(["--mechanical"] if mechanical else []))
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    report, text = result.stdout.decode("utf-8").split("\n--- composed handoff ---\n", 1)
    settings = json.loads(report.split("\n", 1)[0])["launch_settings"]
    assert (settings["vendor"], settings["started_by"]) == ("claude", "launch")
    assert '"started_by": "launch"' in text and "## Where you work" not in text
    # The stop rule names the brief's Shape sentence, so the stand-in brief the text carries has one.
    assert "**Shape:**" in text


def test_a_builders_proof_posted_while_its_launch_runs_stays_current_after_it_ends(tmp_path, monkeypatch, capsys):
    fixture = route_fixture.Fixture(tmp_path)
    work, posted, proofs = fixture.work, [], []
    for name in ("GitHubREST", "_read_policy_state", "_cold_reading_decision", "_evaluate_reach"):
        monkeypatch.setattr(work, name, getattr(work, name))  # restored after the fixture's decision sets it
    monkeypatch.setattr(work, "_release_gate_status", lambda *_a: {"verdict": "none", "head": None})
    monkeypatch.setattr(work, "_merge_readiness", lambda *_a: {"reason": "ready", "detail": "", "ready": True})
    sources = {key: {"repository": "o/r", "path": key, "revision": "a" * 40, "sha256": "1" * 64}
               for key in ("work_configuration", "use_rules")}

    def proof(head):
        checked = fixture.state()
        checked.changed_paths, checked.policy_sources, checked.pr_comments = ["job/job.md"], sources, posted
        work.validate_marker_claims(checked)
        work._prepare_builder_use(checked, None, route_fixture.RULES, head)
        proofs.append(work.proof_document.canonical_json(work.compose_proof(checked, route_fixture.RULES)))
        return checked

    def post_proof(head):
        # Posted on the pull request while the launch runs, as the builder's `run proof` posts it.
        proof(head)
        posted.append({"id": 900, "body": work.proof_document.document(json.loads(proofs[0])),
                       "user": {"login": route_fixture.PRODUCER}, "created_at": "2026-11-01T00:15:00+00:00"})

    try:
        state = route_fixture.ready_at_head(fixture, route_fixture.CLEAR, post_proof)
        fixture.pr["draft"] = False
        capsys.readouterr()
        fixture.decision(proof(state.pr["head"]["sha"]))
    finally:
        fixture.stop()
    decision = json.loads(capsys.readouterr().out.split("\n", 1)[0])
    composed = work.proof_document.validate(json.loads(proofs[1]))  # use and floor from the builder's evidence
    assert not {item["code"] for item in composed["diagnostics"]} & {"use-missing", "floor-missing"}
    assert [(item["stage"], item["status"]) for item in composed["declarations"]] == [
        ("floor", "declared"), ("use", "declared")] and proofs[0] == proofs[1]
    assert (decision["stage"], decision["reason"]) == ("final-pass", "ready-reported"), decision["detail"]


def test_the_mechanical_handoff_carries_a_row_reader_per_row_and_no_plan(exported):
    result = fixture_run(exported, "handoff", "--mechanical")
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    report, text = result.stdout.decode("utf-8").split("\n--- composed handoff ---\n", 1)
    decision = json.loads(report.split("\n", 1)[0])
    assert (decision["stage"], decision["reason"]) == ("handoff", "handoff-due")
    assert "## The mechanical lane" in text and "The settled plan" not in text
    assert "Review lane: mechanical" in text and "--job-from-artifact" not in text
    rows = [line.rsplit("--row ", 1)[1] for line in text.splitlines() if " --row " in line]
    assert rows == [str(number) for number in range(1, 8)]


def test_mechanical_applies_only_to_the_handoff_scenarios(exported):
    assert fixture_run(exported, "with-builder", "--mechanical").returncode == 2


@pytest.mark.unlisted_builder_reason
def test_a_decision_flagged_with_an_unlisted_builder_reason_fails_the_run(tmp_path, monkeypatch, capsys):
    fixture = route_fixture.Fixture(tmp_path)
    work = fixture.work
    for name in ("GitHubREST", "_read_policy_state"):
        monkeypatch.setattr(work, name, getattr(work, name))  # restored after the fixture's decision sets it
    # With no reason listed, the live builder's `if_ended` reading is one the handoff's steps don't answer.
    monkeypatch.setattr(work, "BUILDER_MODE_REASONS", frozenset())
    try:
        fixture.live_stretch()
        code = fixture.decision(fixture.state())
    finally:
        fixture.stop()
        work.UNLISTED_BUILDER_REASONS.clear()
    flagged = route_fixture.unlisted_builder_reason(fixture.reports[0])
    assert flagged and code != 0
    assert f"unlisted_builder_reason {flagged}" in capsys.readouterr().err


def test_the_flag_is_read_from_the_decision_or_its_if_ended():
    read = route_fixture.unlisted_builder_reason
    assert read({"unlisted_builder_reason": "x", "detail": ""}) == "x"
    assert read({"detail": json.dumps({"if_ended": {"reason": "y", "unlisted_builder_reason": "y"}})}) == "y"
    assert read({"detail": json.dumps({"if_ended": {"reason": "y"}})}) is None
    assert read({"detail": "not json"}) is None


@pytest.mark.parametrize("name", [name for name in sorted(STEPS) if name.startswith("builder-")])
def test_a_builders_owed_list_names_each_check_once(exported, name):
    report = json.loads(printed(exported, name).split("\n", 1)[0])
    owed = json.loads(json.loads(report["detail"])["if_ended"]["detail"])["owed_list"]
    named = [(entry["stage"], entry.get("criterion"), entry.get("row")) for entry in owed]
    assert len(named) == len(set(named)), named

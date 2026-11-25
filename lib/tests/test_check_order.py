"""The order the entrance gives a change's checks once its floor passes: the ready step, then the criterion readers
and use at that head while the reviewers read, one batch of answers, then the cold reading, use at the head where
today's rule owes it, and proof.

Each test here runs the real cold-reading gate over a change with Git history, so the order is read, not stood in.
Design: lib/DESIGN.md#the-cold-reader
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_work  # noqa: E402
import work  # noqa: E402
from test_cold_reader import Change, clean, covered, flagged, settled  # noqa: E402

pytestmark = pytest.mark.cold_reading

A_FIX = {"a.py": "# Design: design/x.md#s\nA = 2\n"}


@pytest.fixture
def change(tmp_path, monkeypatch):
    return Change(tmp_path, monkeypatch)


def held(change, stage, draft=False):
    """Whether the cold reading holds STAGE at the change's head, as the stage itself asks."""
    fixture = change.state(draft)
    work.validate_marker_claims(fixture)
    return work._held_by_cold_reading(fixture, stage)


def reader_run(change, monkeypatch, capsys):
    """`run cold-reader` as a holder names it: its report, with no seat allowed to launch."""
    monkeypatch.setattr(work, "_invoke_recipient", lambda *_a: pytest.fail("no seat may launch"))
    fixture = change.state()
    work.validate_marker_claims(fixture)
    capsys.readouterr()
    code = work._execute_cold_reader(fixture, work.Decision("cold-reader", True, "fresh", "holder-named-stage"),
                                     dispatch_path=None, tree_metadata=None, timeout_seconds=600,
                                     claude_path=None, codex_path=None, rules=test_work.RULES)
    assert code == 0
    return [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")][-1]


def thread(identity, body="The second line restates the code."):
    return {"id": identity, "body": body, "commit_id": None, "user": {"login": test_work.REVIEWER, "type": "Bot"}}


def answer(identity, word="fixed"):
    return {"id": identity + 1000, "in_reply_to_id": identity, "body": word, "user": {"login": test_work.PRODUCER}}


# The ready step: a finished build reaches its reviewers and use whatever its reading says.

@pytest.mark.parametrize("reading", ["absent", "open", "stale"])
def test_a_finished_build_is_told_to_mark_ready_whatever_its_reading(change, reading, capsys):
    if reading == "open":
        change.read(flagged("a.py"))
        change.post_open(flagged("a.py"))
    elif reading == "stale":
        change.reviewed(clean())
        change.post_clean()
        change.commit(A_FIX)
    decision = change.decide(draft=True)
    assert (decision.stage, decision.reason) == ("ready-reviewers", "floor-complete-pr-draft")
    # Readying the reviewers and running use are not held on the reading; proof still is.
    assert not held(change, "ready-reviewers", draft=True) and not held(change, "use", draft=True)
    assert held(change, "proof", draft=True)
    capsys.readouterr()


def test_the_ready_step_says_what_ready_means_and_asks_no_account_of_the_criteria(change):
    detail = change.decide(draft=True).detail
    assert "the planned build is complete" in detail and "no cold reading is owed before this step" in detail
    assert "account for every" not in detail


def test_marking_ready_is_not_refused_while_a_reading_is_owed(monkeypatch, capsys):
    config = work.WorkConfig(connected_reviewers=frozenset({test_work.REVIEWER}),
                             marker_producers=frozenset({test_work.PRODUCER}), reviewer_label="reviewers")
    fixture = test_work.state(test_work.AFFIRMED, test_work.ARTIFACT, test_work.WOULD, test_work.HOLDER,
                              test_work.FLOOR, pr=True, config=config)
    fixture.pr["node_id"] = "PR_fixture"
    work.validate_marker_claims(fixture)
    # This fixture's heads have no Git objects, so a reading owed at its head stands in for the gate's.
    owed = work.Decision("cold-reader", True, "fresh", "cold-reading-absent", '{"covered": ["a.py"]}')
    monkeypatch.setattr(work, "_cold_reading_decision", lambda *_a: owed)
    transport = test_work.ReadyTransport()
    assert work._execute_ready_reviewers(transport, fixture, test_work.RULES, None, None) == 0
    assert [operation[0] for operation in transport.operations] == ["label", "ready"]
    assert json.loads(capsys.readouterr().out)["ready"] is True


# The reports: every one is in before any fix is named, and a catch-up never waits.

def test_after_the_ready_step_every_report_comes_before_any_fix(tmp_path, monkeypatch):
    change = Change(tmp_path, monkeypatch, brief=test_work.AFFIRMED)
    settled(change)
    change.reviewer_ran = False
    assert (change.decide().stage, change.decide().reason) == ("use", "pull-request-use-absent")
    change.post_use(changed="true")
    assert (change.decide().stage, change.decide().reason) == ("waiting", "required-connected-reviewer-has-not-run")
    change.review_comments.append(thread(41))
    decision = change.decide()
    assert (decision.stage, decision.reason) == ("review-disposition", "reviewer-thread-lacks-disposition")
    # On the relay route the entrance reads no criterion report, so the first fix stage says to wait for them.
    assert decision.detail.startswith("41 ") and work._relay_batch_detail(False) in decision.detail
    change.review_comments.append(answer(41))
    # The use that changed something is a fix too, named only once the reviewers have run and been answered.
    decision = change.decide()
    assert (decision.stage, decision.reason) == ("build", "use-finding-changed-behavior-or-instructions")
    assert decision.detail == work._relay_batch_detail(False)


def test_a_use_that_changed_something_waits_for_the_reviewers_on_the_relay_route(tmp_path, monkeypatch):
    change = Change(tmp_path, monkeypatch, brief=test_work.AFFIRMED)
    settled(change)
    change.reviewer_ran = False
    change.post_use(changed="true")
    assert change.decide().stage == "waiting"


@pytest.mark.parametrize("outstanding", ["use", "reviewer", "thread"])
def test_a_branch_behind_its_base_catches_up_whatever_is_outstanding(tmp_path, monkeypatch, outstanding):
    change = Change(tmp_path, monkeypatch, brief=test_work.AFFIRMED)
    settled(change)
    if outstanding != "use":
        change.post_use()
    change.reviewer_ran = outstanding != "reviewer"
    if outstanding == "thread":
        change.review_comments.append(thread(41))
    change.behind = True
    assert change.decide().stage == "catch-up"


# The cold reading: neither named nor launchable until the rest is answered.

@pytest.mark.parametrize("outstanding", ["draft", "reviewer", "thread", "body", "use"])
def test_nobody_is_told_to_run_the_cold_reader_or_can_until_the_rest_is_answered(
        tmp_path, monkeypatch, capsys, outstanding):
    change = Change(tmp_path, monkeypatch, brief=test_work.AFFIRMED)
    settled(change)
    if outstanding != "use":
        change.post_use()
    change.reviewer_ran = outstanding != "reviewer"
    if outstanding == "thread":
        change.review_comments.append(thread(41))
    if outstanding == "body":
        # A finding in a review's body, unanswered; its parsing has its own suite.
        finding = work.review_findings.BodyFinding(test_work.REVIEWER, "cr-comment:v1:x", [{"id": 9}])
        monkeypatch.setattr(work, "_body_findings", lambda _state: work.review_findings.Classification(
            [finding], [], []))
    draft = outstanding == "draft"
    decision = change.decide(draft=draft)
    assert decision.stage not in {"cold-reader", "cold-reading-post", "cold-reading-close"}
    if not draft:
        report = reader_run(change, monkeypatch, capsys)
        assert (report["status"], report["reason"]) == ("refused", "cold-reading-not-yet-owed")
        assert f"take {decision.stage} ({decision.reason.split(';')[0]}) first" in report["detail"]


def test_the_reading_is_named_and_launchable_once_every_report_is_answered(tmp_path, monkeypatch, capsys):
    change = Change(tmp_path, monkeypatch, brief=test_work.AFFIRMED)
    settled(change)
    change.post_use()
    change.review_comments += [thread(41), answer(41)]
    decision = change.decide()
    assert (decision.stage, decision.reason) == ("cold-reader", "cold-reading-absent")
    # The relay holder holds the reading on the criterion readers the entrance can't read.
    assert json.loads(decision.detail)["before_reading"] == work._relay_reading_detail(False)
    assert covered(decision) == ["a.py", "b.py"]


def test_a_draft_pull_request_refuses_a_named_reading(change, monkeypatch, capsys):
    monkeypatch.setattr(work, "_invoke_recipient", lambda *_a: pytest.fail("no seat may launch"))
    fixture = change.state(draft=True)
    work.validate_marker_claims(fixture)
    capsys.readouterr()
    work._execute_cold_reader(fixture, work.Decision("cold-reader", True, "fresh", "holder-named-stage"),
                              dispatch_path=None, tree_metadata=None, timeout_seconds=600, claude_path=None,
                              codex_path=None, rules=test_work.RULES)
    report = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")][-1]
    assert report["reason"] == "cold-reading-not-yet-owed"
    assert "take ready-reviewers (floor-complete-pr-draft) first" in report["detail"]


# Proof: still held on a clean reading at the head, and a later commit owes a reread of what it changed.

@pytest.mark.parametrize("reading", ["absent", "open", "stale"])
def test_proof_and_the_release_report_stay_held_without_a_clean_reading_at_the_head(change, reading, capsys):
    if reading == "open":
        change.read(flagged("a.py"))
        change.post_open(flagged("a.py"))
    elif reading == "stale":
        change.reviewed(clean())
        change.post_clean()
        change.commit(A_FIX)
    assert held(change, "proof") and held(change, "release-report")
    capsys.readouterr()


def test_a_commit_after_a_clean_reading_owes_a_reread_of_what_it_changed(change):
    change.reviewed(clean())
    change.post_clean()
    assert change.decide().stage == "proof"
    change.commit(A_FIX)
    decision = change.decide()
    assert (decision.stage, decision.reason, covered(decision)) == ("cold-reader", "cold-reading-stale", ["a.py"])


# Use: once on the first build, and again only where today's rule makes it stale.

def test_use_runs_again_only_where_a_commit_made_it_stale(tmp_path, monkeypatch):
    change = Change(tmp_path, monkeypatch, brief=test_work.AFFIRMED)
    settled(change)
    change.post_use()
    change.review_comments += [thread(41), answer(41)]
    change.commit(A_FIX)
    # The answers are in and use has reported on this pull request, so the reading comes before any second use.
    assert change.decide().stage == "cold-reader"
    change.reviewed(clean())
    change.post_clean()
    # The use marker reads an earlier head; today's rule names use at the head once the reading is clean.
    assert (change.decide().stage, change.decide().reason) == ("use", "current-head-use-absent")
    change.post_use()
    assert change.decide().stage == "proof"


# A change in flight: a reading already clean before the ready step is kept and nothing is redone.

def test_a_clean_reading_before_the_ready_step_is_kept_through_the_reviewers(change):
    change.reviewed(clean())
    change.post_clean()
    assert change.decide(draft=True).stage == "ready-reviewers"
    change.reviewer_ran = False
    assert change.decide().stage == "waiting"
    change.reviewer_ran = True
    change.review_comments += [thread(41), answer(41, "declined - the comment says why")]
    # No commit followed, so the reading still stands at the head and proof is next.
    assert change.decide().stage == "proof"
    change.commit(A_FIX)
    decision = change.decide()
    assert (decision.stage, covered(decision)) == ("cold-reader", ["a.py"])


def test_an_open_reading_awaiting_review_before_the_ready_step_reads_the_ready_step_first(change):
    change.read(flagged("a.py"))
    change.post_open(flagged("a.py"))
    assert change.decide(draft=True).stage == "ready-reviewers"
    assert change.decide().stage == "build"  # its review, once the reviewers have been answered

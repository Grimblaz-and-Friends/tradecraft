"""A builder who takes the handoff's steps in order is led by the entrance's read-back from each to a later one.

Guards the walk G10 asks of the handoff's table: driven through ``handoff.BUILDER_STEPS`` with a base that requires
resolved review threads and a fixed commit after the floor ran, the read-back never names a step the builder has
already taken, names thread resolution and the floor again where they fall due, and ends at `final-pass` /
`ready-reported`. Every decision it reads is one the drift guard's flag watches.
Design: lib/DESIGN.md#the-builder-route
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import handoff  # noqa: E402
import route_fixture  # noqa: E402
import work  # noqa: E402

KEYS = [step.key for step in handoff.BUILDER_STEPS]
REVIEWER = "reviewer-bot"
# What the route fixture's decision sets on the entrance in place of GitHub.
STOOD_IN = ("GitHubREST", "_read_policy_state", "_emit_report")


class Walk:
    """One hand-started builder's change, and what the stand-ins for GitHub-only evidence read at each step."""

    def __init__(self, fixture: route_fixture.Fixture):
        self.fixture = fixture
        self.cold_clean = self.reach_clear = self.proof = False
        self.threads = []
        self.checks, self.findings = [], []

    def cold_reading(self, _state, _sha):
        # The cold reader's report and its `clean` are bundles of a launched seat over Git objects the fixture
        # doesn't hold, so the walk stands in for the gate's reading: absent until the step is taken.
        return None if self.cold_clean else work.Decision("cold-reader", True, "fresh", "cold-reading-absent", "{}")

    def reach(self, checked):
        # Reach is read from the holder's Git history, which this fixture's change doesn't keep.
        checked.reach = {"state": "clear" if self.reach_clear else "pending", "turns": [], "diagnostics": []}

    def state(self):
        state = self.fixture.state()
        # Thread resolution and the review threads are read from GitHub's GraphQL alone.
        state.synchronization = {**route_fixture.CLEAR, "thread_resolution": {"required": True},
                                 "review_threads": {"status": "read", "threads": [dict(t) for t in self.threads]}}
        return state

    def ready(self, builder: str, head: str) -> None:
        """The record the builder posts, then reads back, at HEAD with what it has run so far."""
        self.fixture.readiness(builder, head, checks=self.checks, findings=self.findings, started_by="hand")

    def read_back(self) -> tuple[str, dict]:
        """The step the read-back names: the decision's own reason, or its `if_ended` while the builder is live."""
        fixture = self.fixture
        fixture.decision(self.state())
        report = fixture.reports[0]
        if report["stage"] == "with-builder":
            report = json.loads(report["detail"])["if_ended"]
        reason = report["reason"].split(";", 1)[0]
        if reason == "owed-at-ready":
            first = json.loads(report["detail"])["owed_at_ready"]
            # An owed check the record doesn't name is answered at the step that launches it.
            step = (handoff.CHECK_STEPS[first["stage"]] if first["reason"] == "owed-unnamed"
                    else handoff.ANSWERS[first["reason"]])
            return step, {"stage": report["stage"], "reason": reason, "why": first["reason"]}
        return handoff.ANSWERS[reason], {"stage": report["stage"], "reason": reason, "why": reason}


@pytest.fixture
def walk(tmp_path, monkeypatch):
    for name in STOOD_IN:
        monkeypatch.setattr(work, name, getattr(work, name))
    fixture = route_fixture.Fixture(tmp_path)
    walking = Walk(fixture)
    monkeypatch.setattr(work, "_cold_reading_decision", walking.cold_reading)
    monkeypatch.setattr(work, "_evaluate_reach", walking.reach)
    current = work._current_marker
    # Proof is composed from policy sources the fixture doesn't serve; the walk stands in for its marker.
    monkeypatch.setattr(work, "_current_marker", lambda checked, name, **k: (
        walking.proof if name == "proof" else current(checked, name, **k)))
    decide = work.decide
    monkeypatch.setattr(work, "decide", lambda checked, rules: decide(
        work.replace(checked, proof_current=bool(walking.proof)), rules))
    # The connected reviewer's run receipt, the required gate and the merge's verdict are GitHub's alone.
    monkeypatch.setattr(work, "_reviewer_ran", lambda _state: True)
    monkeypatch.setattr(work, "_release_gate_status", lambda *_a: {"verdict": "none", "reason": "none", "head": None,
                                                                   "requirement_known": True})
    monkeypatch.setattr(work, "_merge_readiness", lambda *_a: {"reason": "ready", "detail": "", "ready": True})
    try:
        yield walking
    finally:
        fixture.stop()


def floor(fixture, head: str) -> dict:
    """The handoff's floor command run at HEAD with its marker posted, as the record names it."""
    posted = fixture.post(f"<!-- tradecraft:floor:v1 head={head} status=pass -->\n\n```\n{route_fixture.FLOOR}\n"
                          "```\n\n1 passed\n")
    return {"stage": "floor", "criterion": None, "row": None, "dispatch": None, "head": head, "report": posted,
            "relaunch_of": None}


def test_a_builder_taking_the_handoffs_steps_in_order_is_led_to_ready_reported(walk, capsys):
    fixture = walk.fixture
    source, head = fixture.source()
    builder = fixture.hand_stretch(source)["dispatch_id"]
    fixture.connected_reviewers = frozenset({REVIEWER})
    taken, named = [], []

    def took(key: str, head: str) -> tuple[str, dict]:
        """Record KEY as taken, post the record at HEAD and read it back: the step named is one not yet taken."""
        taken.append(key)
        walk.ready(builder, head)
        step, decision = walk.read_back()
        if step == "floor-again" and "floor" not in taken:
            # One reason names a floor missing at the head, which before the first floor run is step 5's.
            step = "floor"
        named.append((key, step, decision))
        # Resolving an answered thread is step 8's second half, owed once the decision names it.
        unfinished = step == "answer-reviewers" and decision["why"] == "reviewer-thread-answered-unresolved"
        assert step not in taken or unfinished, named
        return step, decision

    fixture.pull_request(head, route_fixture.CLEAR)
    assert took("open-pull-request", head)[0] == "floor"

    walk.cold_clean = True
    took("cold-reader", head)
    # The stand-in plan's criterion C2 is owed a fresh reader only through the handoff's owed checks, which this
    # record's hand block leaves out (route_fixture.hand_stretch), so the step posts nothing the entrance reads.
    took("criteria", head)

    report, dispatch = fixture.use_report(fixture.state(), source, builder)
    walk.checks.append({"stage": "use", "criterion": None, "row": None, "dispatch": dispatch, "head": head,
                        "report": report, "relaunch_of": None})
    walk.findings.append({"report": report, "finding": "F1", "disposition": "fixed", "commit": head})
    took("use", head)

    walk.checks.append(floor(fixture, head))
    assert took("floor", head)[0] == "reach"

    walk.reach_clear = True
    assert took("reach", head)[0] == "ready-reviewers"

    fixture.pr["draft"] = False
    # The connected reviewer posts one inline finding on the readied pull request, its thread open.
    fixture.review_comments.append({"id": 501, "in_reply_to_id": None, "user": {"login": REVIEWER},
                                    "body": "The job's line is wrong.", "path": "job/job.md",
                                    "html_url": f"https://github.invalid/{route_fixture.REPO}/pull/7#discussion_r501"})
    walk.threads.append({"comment_id": 501, "thread_id": "PRRT_fixture", "resolved": False, "outdated": False,
                         "author": REVIEWER})
    step, decision = took("ready-reviewers", head)
    assert (step, decision["why"]) == ("answer-reviewers", "reviewer-thread-lacks-disposition"), named

    # The builder fixes the finding in a commit after the floor ran, and answers the thread.
    (source / "job" / "job.md").write_bytes(b"run the job as corrected\n")
    route_fixture.git(source, "commit", "-q", "-am", "fix the job's line")
    fixed = route_fixture.git(source, "rev-parse", "HEAD")
    fixture.pr["head"]["sha"] = fixed
    fixture.review_comments.append({"id": 502, "in_reply_to_id": 501, "user": {"login": route_fixture.PRODUCER},
                                    "body": f"fixed - corrected in {fixed}",
                                    "html_url": f"https://github.invalid/{route_fixture.REPO}/pull/7#discussion_r502"})
    step, decision = took("answer-reviewers", fixed)
    # The fixed commit came after the floor ran, so the floor is owed again at the new head first.
    assert (step, decision["why"]) == ("floor-again", "current-head-floor-missing-or-red"), named

    walk.checks.append(floor(fixture, fixed))
    step, decision = took("floor-again", fixed)
    # The thread is answered but open, and the base requires resolution: the read-back names resolving it.
    assert (step, decision["why"]) == ("answer-reviewers", "reviewer-thread-answered-unresolved"), named
    walk.threads[0]["resolved"] = True  # the resolve command's effect, which only GitHub records
    step, decision = took("answer-reviewers", fixed)
    assert (step, decision["why"]) == ("proof", "current-head-proof-absent-or-outdated"), named

    walk.proof = True
    step, decision = took("proof", fixed)
    # Nothing is owed at the head: the read-back reads what the final pass will, while the builder is still live.
    assert (step, decision["stage"], decision["why"]) == ("read-back", "final-pass", "ready-reported"), named
    took("readiness-record", fixed)

    # The builder's record stands and its hand record completes; the holder's decision is the final pass itself.
    taken.append("read-back")
    fixture.launch_tree.complete_hand_record(fixture.store, builder, completed_by="the builder's readiness record")
    fixture.decision(walk.state())
    assert (fixture.reports[0]["stage"], fixture.reports[0]["reason"]) == ("final-pass", "ready-reported")
    assert "unlisted_builder_reason" not in fixture.reports[0]
    # Every step of the table was taken, in the table's order.
    assert [key for key in dict.fromkeys(taken)] == KEYS
    # The entrance holds the floor before the cold reading and the chain, so until the floor runs every read-back
    # names it; from there each names the table's next step, the floor again after the fix, and the thread's
    # resolution once that floor stands.
    assert [(key, step) for key, step, _decision in named] == [
        ("open-pull-request", "floor"), ("cold-reader", "floor"), ("criteria", "floor"), ("use", "floor"),
        ("floor", "reach"), ("reach", "ready-reviewers"), ("ready-reviewers", "answer-reviewers"),
        ("answer-reviewers", "floor-again"), ("floor-again", "answer-reviewers"), ("answer-reviewers", "proof"),
        ("proof", "read-back"), ("readiness-record", "read-back")]
    capsys.readouterr()

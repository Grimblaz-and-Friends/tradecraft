"""A builder who takes the handoff's steps in order is led by the entrance's read-back from each to the next.

Guards that the handoff's table and the entrance agree on the order: driven through ``handoff.BUILDER_STEPS`` with a
base that requires resolved review threads and a fixed commit after the floor ran, the read-back at each step names
the table's next step, except for the steps the test names with their reasons, and the walk ends at `final-pass` /
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

    def read_back(self, taken: list[str]) -> tuple[str, dict]:
        """The step the read-back names: from the decision's own reason, or its `if_ended` while the builder is
        live. Where it lists several owed steps the builder takes the earliest in the table's order, as the
        read-back step says; a floor missing at the head is the floor step until the floor has first run."""
        fixture = self.fixture
        fixture.decision(self.state())
        report = fixture.reports[0]
        if report["stage"] == "with-builder":
            report = json.loads(report["detail"])["if_ended"]
        reason = report["reason"].split(";", 1)[0]
        entries = ([{"reason": reason}] if reason != "owed-at-ready" else
                   json.loads(report["detail"]).get("owed_list") or [json.loads(report["detail"])["owed_at_ready"]])
        steps = []
        for entry in entries:
            # An owed check the record doesn't name is answered at the step that launches it.
            step = (handoff.CHECK_STEPS[entry["stage"]] if entry["reason"] in ("owed-unnamed", "row-unread")
                    else handoff.ANSWERS[entry["reason"]])
            steps.append("floor" if step == "floor-again" and "floor" not in taken else step)
        step = min(steps, key=KEYS.index)
        why = entries[[*steps].index(step)]["reason"]
        return step, {"stage": report["stage"], "reason": reason, "why": why}


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
    # The record names the owed checks the handoff gave it, so the entrance names each where it falls.
    builder = fixture.hand_stretch(source, owed=True)["dispatch_id"]
    fixture.connected_reviewers = frozenset({REVIEWER})
    taken, named = [], []

    def took(key: str, head: str) -> tuple[str, dict]:
        """Take KEY, post the record at HEAD and read it back."""
        taken.append(key)
        walk.ready(builder, head)
        step, decision = walk.read_back(taken)
        named.append((key, step, decision["why"]))
        return step, decision

    def check(stage: str, at: str, **fields) -> None:
        """A check the builder ran at AT, named in its record with the report it answered."""
        report = fixture.post(f"the {stage} report")
        walk.checks.append({"stage": stage, "criterion": None, "row": None, "dispatch": None, "head": at,
                            "report": report, "relaunch_of": None, **fields})

    fixture.pull_request(head, route_fixture.CLEAR)
    took("open-pull-request", head)
    walk.checks.append(floor(fixture, head))
    took("floor", head)
    walk.cold_clean = True
    check("cold-reader", head)
    took("cold-reader", head)
    check("acceptance-criterion", head, criterion="C2")
    took("criteria", head)
    report, dispatch = fixture.use_report(fixture.state(), source, builder)
    walk.checks.append({"stage": "use", "criterion": None, "row": None, "dispatch": dispatch, "head": head,
                        "report": report, "relaunch_of": None})
    walk.findings.append({"report": report, "finding": "F1", "disposition": "fixed", "commit": head})
    took("use", head)
    walk.reach_clear = True
    took("reach", head)
    fixture.pr["draft"] = False
    fixture.review_comments.append({"id": 501, "in_reply_to_id": None, "user": {"login": REVIEWER},
                                    "body": "The job's line is wrong.", "path": "job/job.md",
                                    "html_url": f"https://github.invalid/{route_fixture.REPO}/pull/7#discussion_r501"})
    walk.threads.append({"comment_id": 501, "thread_id": "PRRT_fixture", "resolved": False, "outdated": False,
                         "author": REVIEWER})
    took("ready-reviewers", head)
    (source / "job" / "job.md").write_bytes(b"run the job as corrected\n")
    route_fixture.git(source, "commit", "-q", "-am", "fix the job's line")
    fixed = route_fixture.git(source, "rev-parse", "HEAD")
    fixture.pr["head"]["sha"] = fixed
    fixture.review_comments.append({"id": 502, "in_reply_to_id": 501, "user": {"login": route_fixture.PRODUCER},
                                    "body": f"fixed - corrected in {fixed}",
                                    "html_url": f"https://github.invalid/{route_fixture.REPO}/pull/7#discussion_r502"})
    took("answer-reviewers", fixed)
    walk.checks.append(floor(fixture, fixed))
    took("floor-again", fixed)
    walk.threads[0]["resolved"] = True  # the resolve command's effect, which only GitHub records
    took("resolve-threads", fixed)
    walk.proof = True
    took("proof", fixed)
    took("readiness-record", fixed)

    # Each read-back names the table's next step, but where the entrance never names one: use, which this
    # fixture's paths don't owe, so criteria are followed by reach; and the readiness record, which the walk
    # posts at every step, so proof is followed by the read-back.
    skipped = {"use": "the change's paths owe no use", "readiness-record": "the record already stands"}
    order = [key for key in KEYS if key not in skipped]
    expected = [(key, order[order.index(key) + 1]) for key in order[:-1]] + [("readiness-record", "read-back")]
    assert [(key, step) for key, step, _why in named if key != "use"] == expected, named
    assert dict((key, why) for key, _step, why in named)["floor-again"] == "reviewer-thread-answered-unresolved"
    assert dict((key, why) for key, _step, why in named)["answer-reviewers"] == "current-head-floor-missing-or-red"
    # Every step of the table was taken, in the table's order.
    assert taken == KEYS[:-1]

    # The builder's record stands and its hand record completes; the holder's decision is the final pass itself.
    fixture.launch_tree.complete_hand_record(fixture.store, builder, completed_by="the builder's readiness record")
    fixture.decision(walk.state())
    assert (fixture.reports[0]["stage"], fixture.reports[0]["reason"]) == ("final-pass", "ready-reported")
    assert "unlisted_builder_reason" not in fixture.reports[0]
    capsys.readouterr()

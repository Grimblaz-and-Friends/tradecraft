"""The drift guard between the entrance's builder reasons and the handoff's steps.

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

BUILDER = {"dispatch": "0123456789abcdef0123456789abcdef", "session": "builder-session", "identity": "checked"}


def composed(*, mechanical: bool) -> str:
    """A handoff as the entrance composes it, on the plan lane or the mechanical one."""
    checks = handoff.owed_checks(criteria=[] if mechanical else ["C1"], use_owed=not mechanical,
                                 floor_command="python -B -m pytest -q", mechanical=mechanical,
                                 rows=[(number, f"**{number}. Row {number}.**") for number in range(1, 8)])
    return handoff.compose_handoff(
        brief="The brief.\n", artifact=None if mechanical else "The plan.\n",
        lane_reason=work.MECHANICAL_HANDOFF_REASON if mechanical else None, checks=checks,
        allowance="You may push the branch.", repo="o/r", issue=5, holder_root="/holder", plugin_root="/plugin",
        notify=None).decode("utf-8")


def test_every_listed_builder_reason_has_a_step_whose_sentence_the_handoff_carries():
    assert set(work.BUILDER_MODE_REASONS) <= set(handoff.ANSWERS)
    assert set(handoff.ANSWERS.values()) <= {step.key for step in handoff.BUILDER_STEPS}
    texts = {"plan": composed(mechanical=False), "mechanical": composed(mechanical=True)}
    missing = [(lane, reason) for reason in sorted(work.BUILDER_MODE_REASONS) for lane, text in texts.items()
               # Use is never owed on the mechanical lane, so its step is the plan lane's alone.
               if not (lane == "mechanical" and handoff.ANSWERS[reason] == "use")
               and handoff.step_sentence(handoff.ANSWERS[reason]) not in text]
    assert missing == []


@pytest.mark.unlisted_builder_reason
def test_an_unlisted_reason_returned_to_a_builder_is_flagged_and_collected(monkeypatch):
    monkeypatch.setattr(work, "builder_mode", lambda: BUILDER)
    work.UNLISTED_BUILDER_REASONS.clear()
    try:
        assert work._unlisted_builder_reason("not-a-listed-reason") == "not-a-listed-reason"
        assert work.UNLISTED_BUILDER_REASONS == {"not-a-listed-reason"}
        # A reason's detail after its first `;` is no part of the reason.
        assert work._unlisted_builder_reason("builder-live; detail") is None
        assert work._unlisted_builder_reason(sorted(work.BUILDER_MODE_REASONS)[0]) is None
        assert work.UNLISTED_BUILDER_REASONS == {"not-a-listed-reason"}
    finally:
        work.UNLISTED_BUILDER_REASONS.clear()


@pytest.mark.unlisted_builder_reason
def test_the_decision_carries_the_flag_only_in_builder_mode(monkeypatch):
    returned = work.Decision("final-pass", False, None, "not-a-listed-reason", "{}", status="holder-owned")
    monkeypatch.setattr(work, "_decide_unflagged", lambda state, rules: returned)
    try:
        monkeypatch.setattr(work, "builder_mode", lambda: None)
        assert work._decide(None, {}).unlisted_builder_reason is None
        assert work.UNLISTED_BUILDER_REASONS == set()
        monkeypatch.setattr(work, "builder_mode", lambda: BUILDER)
        flagged = work._decide(None, {})
        # The flag is report data: the decision is otherwise the one the entrance returned, and nothing refuses.
        assert flagged.unlisted_builder_reason == "not-a-listed-reason"
        assert (flagged.stage, flagged.reason, flagged.status) == ("final-pass", "not-a-listed-reason", "holder-owned")
        assert work.UNLISTED_BUILDER_REASONS == {"not-a-listed-reason"}
    finally:
        work.UNLISTED_BUILDER_REASONS.clear()


def test_the_flag_is_report_data_on_the_decisions_dictionary():
    flagged = work.Decision("final-pass", False, None, "x", None, unlisted_builder_reason="x").as_dict()
    assert flagged["unlisted_builder_reason"] == "x"
    assert "unlisted_builder_reason" not in work.Decision("final-pass", False, None, "x", None).as_dict()


def live_if_ended(tmp_path, monkeypatch):
    """The `if_ended` a holder's decision reports of a live stretch, read through the route fixture."""
    fixture = route_fixture.Fixture(tmp_path)
    for name in ("GitHubREST", "_read_policy_state"):
        monkeypatch.setattr(work, name, getattr(work, name))  # restored after the fixture's decision sets it
    try:
        fixture.live_stretch()
        code = fixture.decision(fixture.state())
    finally:
        fixture.stop()
    return code, json.loads(fixture.reports[0]["detail"])["if_ended"]


@pytest.mark.unlisted_builder_reason
def test_a_listed_reason_removed_from_the_list_is_flagged_when_a_scenario_returns_it(tmp_path, monkeypatch, capsys):
    code, ended = live_if_ended(tmp_path / "listed", monkeypatch)
    assert code == 0 and "unlisted_builder_reason" not in ended and work.UNLISTED_BUILDER_REASONS == set()
    reason = ended["reason"].split(";", 1)[0]
    # Seeded drift: the reason the scenario returns is dropped from the list.
    monkeypatch.setattr(work, "BUILDER_MODE_REASONS", work.BUILDER_MODE_REASONS - {reason})
    try:
        code, ended = live_if_ended(tmp_path / "dropped", monkeypatch)
        assert ended["unlisted_builder_reason"] == reason and code != 0
        assert work.UNLISTED_BUILDER_REASONS == {reason}
    finally:
        work.UNLISTED_BUILDER_REASONS.clear()
    capsys.readouterr()

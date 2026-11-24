"""The builder route's wiring: row readers, reach readings, reviewer declines, after-ready classes, the handoff's
lock and allowance, owed checks and the builder's observed model.

Design: lib/DESIGN.md#the-builder-route
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(LIB / "tests"))

import work  # noqa: E402
from test_route import (  # noqa: E402
    CONNECTED, HEAD, MECHANICAL, PRODUCER, RULES, fixture, launch, post, readiness_record, with_pull_request,
)
from test_readiness_reading import CompareGitHub, record  # noqa: E402

# A mechanical brief with seven bold decision rows, so a row reader has rows 1-7 to read and no row 9.
ROWS = MECHANICAL + "\n" + "".join(f"**{number}. Row {number} holds.** Its words.\n\n" for number in range(1, 8))


def row_args(row=2, criterion=None):
    return argparse.Namespace(stage="acceptance-criterion", row=row, criterion=criterion)


def refusal(state, args, builder):
    with pytest.raises(work.BuilderRefused) as caught:
        work._row_to_read(state, args, builder)
    return caught.value.code


def test_a_row_reader_is_refused_off_the_builder_off_the_lane_or_past_the_briefs_rows(tmp_path):
    builder = {"dispatch_id": "d" * 32}
    assert refusal(fixture(tmp_path, ROWS), row_args(), None) == "stage-not-the-builders"
    assert refusal(fixture(tmp_path, ROWS), row_args(criterion="C1"), builder) == "row-and-criterion"
    assert refusal(fixture(tmp_path, CONNECTED), row_args(), builder) == "row-reader-off-lane"
    assert refusal(fixture(tmp_path, ROWS), row_args(row=9), builder) == "brief-row-absent"
    number, text = work._row_to_read(fixture(tmp_path, ROWS), row_args(), builder)
    assert number == 2 and "Row 2 holds." in text
    # A criterion run names no row, so it is no row reader's.
    assert work._row_to_read(fixture(tmp_path, ROWS), row_args(row=None, criterion="C1"), None) is None


def test_a_row_readers_dispatch_is_recomposed_from_the_brief_as_it_stands(tmp_path):
    state = fixture(tmp_path, ROWS)
    _number, text = work._row_to_read(state, row_args(), {"dispatch_id": "d" * 32})
    tree = tmp_path / "tree"
    composed = work.compose_check_dispatch("acceptance-criterion",
                                           {"row": 2, "row_text": text, "head": HEAD, "tree": tree})
    decoded = composed.decode("utf-8")
    assert decoded.startswith(work.ROW_PREAMBLE) and text in decoded
    assert work.readiness.RETURN_TAILS["acceptance-criterion"] in decoded
    again, head, why = work._recompose_row(state, decoded, HEAD, tree)
    assert (again, head, why) == (composed, HEAD, "")
    amended = fixture(tmp_path, ROWS.replace("Row 2 holds.", "Row 2 now says otherwise."))
    changed, _head, _why = work._recompose_row(amended, decoded, HEAD, tree)
    assert changed is not None and changed != composed


def reach_reading(head=HEAD):
    account = {"schema_version": 1, "turns": []}
    return f"<!-- tradecraft:reach-reading:v1 head={head} -->\n\n```json\n{json.dumps(account)}\n```\n"


def reach_entry(report):
    return {"stage": "reach", "criterion": None, "row": None, "dispatch": None, "head": HEAD, "report": report,
            "relaunch_of": None}


@pytest.mark.parametrize("reading, report, expected", [
    (reach_reading(), 101, True),  # The reading posted as comment 101, at the record's head.
    (reach_reading(), 100, False),  # Comment 100 is the brief, no reach reading.
    (reach_reading("c" * 40), 101, False),  # A reading at another head answers another head.
])
def test_a_reach_entry_counts_as_launched_only_with_its_own_reading_at_that_head(
        tmp_path, monkeypatch, reading, report, expected):
    monkeypatch.setattr(work, "GitHubREST", CompareGitHub)
    state = fixture(tmp_path, MECHANICAL)
    builder = launch(state, "stretch", 5)
    state = fixture(tmp_path, MECHANICAL, reading, record(builder, checks=[reach_entry(report)]))
    assert work.readiness_reading(state, None)["launched_by_builder"] is expected


def test_each_connected_reviewers_declined_finding_is_listed_with_its_reason_and_link(tmp_path):
    state = fixture(tmp_path, MECHANICAL)
    state.config = work.WorkConfig(marker_producers=frozenset({PRODUCER}),
                                   connected_reviewers=frozenset({"reviewer-bot"}))
    bot, producer = {"login": "reviewer-bot"}, {"login": PRODUCER}
    review = "https://github.com/o/r/pull/7#pullrequestreview-"
    state.reviews = [{"id": 55, "user": bot}, {"id": 56, "user": bot}]
    state.review_comments = [
        {"id": 10, "user": bot, "body": "This line is wrong."},
        {"id": 11, "user": producer, "in_reply_to_id": 10, "body": "declined - not in scope",
         "html_url": "https://github.com/o/r/pull/7#discussion_r11"}]
    state.pr_comments = [
        {"id": 20, "user": producer, "body": f"declined - wrong; [cr-comment:v1:abc]({review}55)",
         "html_url": "https://github.com/o/r/pull/7#issuecomment-20"},
        {"id": 21, "user": producer, "body": f"declined - fine; [unidentified review]({review}56)",
         "html_url": "https://github.com/o/r/pull/7#issuecomment-21"},
        {"id": 22, "user": producer, "body": f"fixed - done; [cr-comment:v1:def]({review}55)",
         "html_url": "https://github.com/o/r/pull/7#issuecomment-22"}]
    declines = work._reviewer_declines(state)
    assert [(entry["kind"], entry["reviewer"], entry["finding"], entry["reason"]) for entry in declines] == [
        ("inline", "reviewer-bot", "thread 10", "not in scope"),
        ("body-finding", "reviewer-bot", "cr-comment:v1:abc", "wrong"),
        ("whole-review", "reviewer-bot", f"{review}56", "fine")]
    assert [entry["link"] for entry in declines] == [
        "https://github.com/o/r/pull/7#discussion_r11", "https://github.com/o/r/pull/7#issuecomment-20",
        "https://github.com/o/r/pull/7#issuecomment-21"]


@pytest.mark.parametrize("request_record, expected", [
    ({"handoff": {"send_back": "the stop"}, "stage": "stretch"}, "send-back"),
    ({"handoff": {"catch_up_resume": True}, "stage": "stretch"}, "catch-up-resume"),
    ({"stage": "panel"}, "bought-panel"),
    ({"stage": "source-verification"}, "source-verification"),
    ({"stage": "build"}, "other"),
])
def test_a_launch_after_a_ready_record_is_classed_by_its_stage_or_role(request_record, expected):
    assert work._after_ready_class(request_record) == expected


def test_a_fenced_fresh_reader_line_is_an_example_never_the_criterions_reader():
    criterion = ("**C1.** The row holds.\n\n```text\nFresh reader: execute consumer tree x\n```\n\n"
                 "Fresh reader: read tree\n")
    assert work.criterion_reader(criterion) == ("read", None)


def test_one_handoff_holds_the_lock_and_a_stale_lock_is_removed(tmp_path):
    store = tmp_path / "store"
    with work._handoff_lock(store, "o/r#5") as held:
        assert held.exists()
        with pytest.raises(work.HandoffRefused) as caught:
            with work._handoff_lock(store, "O/R#5"):
                pass
        assert caught.value.code == "handoff-in-progress"
    assert not held.exists()
    held.write_text("1", encoding="ascii")
    old = time.time() - work.HANDOFF_LOCK_STALE_SECONDS - 60
    os.utime(held, (old, old))
    with work._handoff_lock(store, "o/r#5") as again:
        assert again == held and again.stat().st_mtime > old
    assert not held.exists()


def test_the_handed_allowance_is_the_one_the_handoff_carried_not_todays_pull_request(tmp_path):
    state = with_pull_request(fixture(tmp_path, MECHANICAL))
    assert "reason" in work._handed_allowance(state, "o/r", 5)
    launch(state, "stretch", 5, lineage_branch="tradecraft/5-x",
           handoff={"branch": None, "pull_request": None})
    expected = work.github_allowance.allowance_for("stretch", repository="o/r", branch="tradecraft/5-x",
                                                   pull_request=None, issue=5)
    assert state.pr["number"] == 7
    assert work._handed_allowance(state, "o/r", 5) == work.github_allowance.sentence(expected)
    launch(state, "stretch", 9, started_by="hand", handoff={"branch": "tradecraft/5-y", "pull_request": None})
    by_hand = work.github_allowance.allowance_for("stretch", repository="o/r", branch="tradecraft/5-y",
                                                  pull_request=None, issue=5)
    assert work._handed_allowance(state, "o/r", 5) == work.github_allowance.sentence(by_hand, hand=True)


def test_an_owed_check_the_record_leaves_out_is_listed_and_no_owed_list_reads_unknown(tmp_path):
    state = fixture(tmp_path, CONNECTED)  # A planned lane: its criteria are owed, not the brief's rows.
    owed = [{"stage": "cold-reader", "criterion": None, "row": None},
            {"stage": "acceptance-criterion", "criterion": "B2", "row": None}]
    payload = {"checks": [{"stage": "cold-reader", "criterion": None, "row": None}], "rows": []}
    listed = work._owed_unnamed(state, payload, HEAD, {"handoff": {"owed_checks": owed}}, use_owed=False)
    assert listed == [{"stage": "acceptance-criterion", "criterion": "B2", "row": None, "reason": "owed-unnamed"}]
    unknown = work._owed_unnamed(state, payload, HEAD, {"started_by": "hand", "handoff": {}}, use_owed=False)
    assert unknown["status"] == "unknown" and "hand record's" in unknown["reason"]
    assert work._owed_unnamed(state, payload, HEAD, {}, use_owed=False)["status"] == "unknown"


def builder_payload(model="m"):
    return {"builder": {"vendor": "claude", "model": model, "started_by": "launch", "usage_log": None}}


def test_a_hand_builders_model_with_no_usage_log_reads_declared(tmp_path):
    read = work._readiness_vendor_model(builder_payload(), {"started_by": "hand"}, None)
    assert (read["source"], read["log"], read["model"], read["declared_differs"]) == ("declared", "absent", "m", None)


def test_a_launched_builders_model_is_observed_in_its_log_and_a_differing_declaration_is_named(tmp_path):
    state = fixture(tmp_path, MECHANICAL)
    builder = launch(state, "stretch", 5)
    request, run_path = work._record_launch(state, builder)
    assert run_path is not None
    stdout = work._bundle_file(run_path, f".{request['requested']['vendor']}.stdout.log")
    lines = [{"type": "system", "subtype": "init", "model": "claude-observed"},
             {"type": "result", "modelUsage": {"claude-observed": {"inputTokens": 1, "outputTokens": 1}}}]
    stdout.write_bytes(b"".join(json.dumps(line).encode("utf-8") + b"\n" for line in lines))
    same = work._readiness_vendor_model(builder_payload("claude-observed"), request, run_path)
    assert (same["source"], same["log"], same["model"], same["declared_differs"]) == (
        "observed", "readable", "claude-observed", None)
    differs = work._readiness_vendor_model(builder_payload("m"), request, run_path)
    assert differs["source"] == "observed" and differs["declared_differs"] == {"vendor": "claude", "model": "m"}


def row_reports(rows, head=HEAD):
    """The check accounting as the entrance reads it: one counting row reader's report per row, at HEAD."""
    return {"check_dispatches": [], "quotations": [], "check_reports": [
        {"comment": 500 + row, "dispatch": "e" * 32, "counts": True, "invalid": [], "builder": "d" * 32,
         "stage": "acceptance-criterion", "head": head, "criterion": None, "row": row, "outcome": "success",
         "findings": []} for row in rows]}


def mapped(*rows):
    return [{"row": row, "carried_by": "test", "where": f"lib/tests/test_row_{row}.py"} for row in rows]


def test_a_mechanical_record_owes_each_unread_row_and_each_row_it_maps_to_nothing(tmp_path, monkeypatch):
    state = fixture(tmp_path, ROWS)
    request = {"handoff": {"owed_checks": []}}
    monkeypatch.setattr(work, "builder_checks", lambda _state: None)
    listed = work._owed_unnamed(state, {"checks": [], "rows": mapped(1, 2, 4, 5, 6, 7)}, HEAD, request,
                                use_owed=False)
    assert [(entry["row"], entry["reason"]) for entry in listed if entry["reason"] == "row-unmapped"] == [
        (3, "row-unmapped")]
    assert [entry["row"] for entry in listed if entry["reason"] == "row-unread"] == list(range(1, 8))
    # A report at another head reads no row at the record's.
    monkeypatch.setattr(work, "builder_checks", lambda _state: row_reports(range(1, 8), head="c" * 40))
    listed = work._owed_unnamed(state, {"checks": [], "rows": mapped(*range(1, 8))}, HEAD, request, use_owed=False)
    assert [entry["row"] for entry in listed if entry["reason"] == "row-unread"] == list(range(1, 8))
    monkeypatch.setattr(work, "builder_checks", lambda _state: row_reports(range(1, 8)))
    assert work._owed_unnamed(state, {"checks": [], "rows": mapped(*range(1, 8))}, HEAD, request,
                              use_owed=False) == []


@pytest.mark.parametrize("merge", [
    {"reason": None, "detail": "", "ready": True},
    {"reason": "merge-blocked-required-gate", "detail": "the required gate is red", "ready": False},
])
def test_the_owed_list_at_ready_is_the_same_whether_the_merge_is_clean_or_blocked(tmp_path, monkeypatch, merge):
    state = with_pull_request(fixture(tmp_path, MECHANICAL))  # A lane with no rows, so only the owed check is owed.
    state.pr["draft"] = False
    builder = launch(state, "stretch", 5, handoff={"owed_checks": [
        {"stage": "cold-reader", "criterion": None, "row": None}]})
    post(state, readiness_record(builder), 30)
    # The floor, the holder's proof and the gate stand clear, so the chain reaches GitHub's merge reading.
    proof = work._current_marker
    monkeypatch.setattr(work, "_current_marker",
                        lambda s, name, **k: name in ("floor", "proof") or proof(s, name, **k))
    monkeypatch.setattr(work, "_release_gate_status", lambda *_a: {"verdict": "none", "reason": "none",
                                                                   "head": None, "requirement_known": True})
    asked = []
    monkeypatch.setattr(work, "_merge_readiness", lambda *_a: asked.append(merge) or dict(merge))
    made = work.decide(state, RULES)
    assert (made.stage, made.reason) == ("final-pass", "owed-at-ready"), made.detail
    assert json.loads(made.detail)["owed_list"] == [
        {"stage": "cold-reader", "criterion": None, "row": None, "reason": "owed-unnamed"}]
    assert asked, "the chain never read the merge, so the case proves nothing"


def test_a_launched_stretchs_window_opens_at_its_launch_under_the_holders_session():
    request = work.records.request_record(
        dispatch_id="d" * 32, work="o/r#5", stage="stretch", settings_source="fixture", settings_scope="implementer",
        vendor="claude", model="m", effort="e", continuity="fresh", permission_boundary="fixture", root=None,
        holder_session_id="holder")
    assert work._handoff_window(request) == ("holder", request["launched_at"], None)
    unnamed = work.records.request_record(
        dispatch_id="d" * 32, work="o/r#5", stage="stretch", settings_source="fixture", settings_scope="implementer",
        vendor="claude", model="m", effort="e", continuity="fresh", permission_boundary="fixture", root=None)
    assert work._handoff_window(unnamed) == (
        None, None, "the stretch's request names no holder session or launch time")


def test_a_later_ready_record_says_the_first_records_chain_stage_was_not_read(tmp_path):
    state = fixture(tmp_path, CONNECTED)
    builder = launch(state, "stretch", 1, handoff={"owed_checks": []})
    chain = {"stage": "proof", "reason": "current-head-proof-absent-or-outdated", "detail": None}
    post(state, readiness_record(builder), 30)
    alone = work._owed_at_ready(state, chain, use_owed=False)
    # One ready record: the chain stage read at the current head is its own, and nothing is said missing.
    assert alone["first"] == alone["last"] == [chain] and "first_chain" not in alone
    post(state, readiness_record(builder), 40)
    both = work._owed_at_ready(state, chain, use_owed=False)
    assert both["first"] == [] and both["last"] == [chain]
    assert both["first_chain"]["status"] == "not-read" and "current head only" in both["first_chain"]["reason"]

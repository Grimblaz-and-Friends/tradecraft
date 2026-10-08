from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cold_draft
import dispatch_implementer
import work
from test_work import (AFFIRMED, ARTIFACT, HOLDER, PRODUCER, RULES, SOURCE_DRAFT, SOURCE_REVISED,
                       WHOLE_ARTIFACT, SESSION, SHA, state, _source_settlement, _assert_source_consumers)

VERDICT = "<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=qualified -->"
AMENDED = "<!-- tradecraft:holder-reading:v1 result=amended -->\n"


def comments(fixture):
    for index, comment in enumerate(fixture.issue_comments):
        comment.setdefault("id", (index + 1) * 10)
        comment.setdefault("created_at", (datetime(2026, 10, 7, 9, tzinfo=timezone.utc)
                                         + timedelta(minutes=index)).isoformat())
        comment.setdefault("html_url", f"https://github.com/example/product/issues/12#issuecomment-{comment['id']}")
    return fixture


def judgment(fixture, tmp_path, *, verdict_index=2, body=SOURCE_DRAFT, draft_id="20",
             version=cold_draft.BINDING_VERSION, name="cold", malformed=None,
             returned=None, post_return=True):
    fixture.record_root = tmp_path / "records"
    folder = fixture.record_root / name
    folder.mkdir(parents=True)
    dispatch = folder / "result.md.dispatch.bin"
    dispatch.write_bytes(b"Judge the inlined draft.\n" + body.encode() + b"\nReturn a verdict.\n")
    binding = cold_draft.freeze(draft_id, body, dispatch.read_bytes())
    source = folder / "result.md.source.md"
    returned = returned if returned is not None else f"Seat {name}: the whole judgment.\nAll reader cells considered.\n"
    source.write_bytes(returned.encode("utf-8"))
    if post_return:
        fixture.issue_comments[verdict_index]["body"] += "\n" + returned
    request = {"schema_version": 2, "work": "example/product#12", "stage": "cold-seat",
               "producer_version": version, "input": str(dispatch), "judged_draft": binding,
               "requested": {"vendor": "claude"}}
    completed = datetime.fromisoformat(fixture.issue_comments[verdict_index]["created_at"]) - timedelta(seconds=1)
    run = {"schema_version": 2, "outcome": "success", "completed_at": completed.isoformat(),
           "staffing_status": "qualified", "judged_draft": deepcopy(binding), "attempts": [],
           "result": {"source_output": str(source)}}
    if version.startswith("0.189"):
        request.pop("judged_draft")
        run.pop("judged_draft")
    if malformed == "missing":
        request.pop("judged_draft", None)
        run.pop("judged_draft", None)
    if malformed == "disagreement": run["judged_draft"]["comment_id"] = "99"
    if malformed == "fields": run["judged_draft"]["body_offset"] = True
    if malformed == "input": dispatch.write_bytes(b"Other bytes")
    (folder / "result.md.request.json").write_bytes(work.records.json_bytes(request))
    (folder / "result.md.run.json").write_bytes(work.records.json_bytes(run))
    return folder / "result.md.run.json"


def bound_fixture(tmp_path, *, version=cold_draft.BINDING_VERSION):
    fixture = comments(state(AFFIRMED, SOURCE_DRAFT, VERDICT, _source_settlement("would"), HOLDER))
    judgment(fixture, tmp_path, version=version)
    return fixture


@pytest.mark.parametrize("settlement_digest", ["original", "edited", "third"])
def test_C1_876_edited_draft_refuses_every_digest_and_every_builder_endpoint(
        tmp_path, monkeypatch, capsys, settlement_digest):
    fixture = bound_fixture(tmp_path)
    edited = SOURCE_DRAFT.replace("original decision", "unjudged decision")
    fixture.issue_comments[1]["body"] = edited
    selected = {"original": cold_draft.artifact_digest(SOURCE_DRAFT),
                "edited": cold_draft.artifact_digest(edited), "third": "0" * 64}[settlement_digest]
    fixture.issue_comments[3]["body"] = _source_settlement("would").replace(cold_draft.artifact_digest(SOURCE_DRAFT), selected)
    decision = work.decide(fixture, RULES)
    assert decision.reason == "artifact-source-unusable" and not decision.dispatch
    assert "was edited after its verdict" in decision.detail
    assert "verdict " + fixture.issue_comments[2]["html_url"] in decision.detail
    assert "{'name': 'cold-verdict'" not in decision.detail
    assert decision.artifact_interpretation["qualifying_verdicts"][0]["verdict_source"] == fixture.issue_comments[2]["html_url"]
    assert "Restore the judged text, or post a new draft for a fresh cold seat" in decision.detail
    assert "miscopied" not in decision.detail
    assert str(tmp_path / "records" / "cold" / "result.md.run.json") in decision.detail
    monkeypatch.setattr(work, "_invoke_recipient", lambda *_: pytest.fail("unjudged draft launched"))
    for stage in ("build", "floor", "review-disposition"):
        work._execute_stage(fixture, work.Decision(stage, True, "fresh", "fixture"), tmp_path, None)
        report = json.loads(capsys.readouterr().out)
        assert not report["dispatch"] and "edited after its verdict" in report["detail"]
    fixture.issue_comments[1]["body"] = SOURCE_DRAFT
    fixture.issue_comments[3]["body"] = _source_settlement("would")
    assert work.decide(fixture, RULES).stage == "build"
    prompt = work._stage_prompt(fixture, work.Decision("build", True, "fresh", "fixture"))
    assert SOURCE_DRAFT.encode() in prompt and edited.encode() not in prompt
    fixture.issue_comments.append({"body": edited, "user": {"login": PRODUCER}, "id": 60})
    comments(fixture)
    assert work.decide(fixture, RULES).stage == "cold-seat"


def test_C1_876_equal_text_in_another_comment_is_not_the_judged_source(tmp_path):
    fixture = bound_fixture(tmp_path)
    path = tmp_path / "records" / "cold" / "result.md.request.json"
    request = json.loads(path.read_bytes())
    request["judged_draft"]["comment_id"] = "99"
    path.write_bytes(work.records.json_bytes(request))
    run_path = path.with_name("result.md.run.json")
    run = json.loads(run_path.read_bytes())
    run["judged_draft"] = request["judged_draft"]
    run_path.write_bytes(work.records.json_bytes(run))
    decision = work.decide(fixture, RULES)
    assert not decision.dispatch and "differs from the judgment's draft 99" in decision.detail


def test_C1_C4_selected_bundle_is_shared_and_another_seat_cannot_substitute(tmp_path, monkeypatch):
    fixture = bound_fixture(tmp_path)
    # The older successful judgment of A cannot rescue a later judgment of B.
    edited = SOURCE_DRAFT.replace("original decision", "other judged decision")
    later = judgment(fixture, tmp_path, body=edited, name="later")
    earlier = tmp_path / "records" / "cold" / "result.md.run.json"
    old = json.loads(earlier.read_bytes())
    old["completed_at"] = (datetime.fromisoformat(fixture.issue_comments[1]["created_at"]) - timedelta(seconds=1)).isoformat()
    earlier.write_bytes(work.records.json_bytes(old))
    calls = []
    matching = work._matching_bundles
    def select(*args, **kwargs):
        if args[1] == {"cold-seat"}: calls.append(args)
        return matching(*args, **kwargs)
    monkeypatch.setattr(work, "_matching_bundles", select)
    decision = work.decide(fixture, RULES)
    assert "was edited after its verdict" in decision.detail and str(later) in decision.detail
    assert len(calls) == 1
    evidence = decision.artifact_interpretation["qualifying_verdicts"][0]
    assert evidence["bundle"] == str(later) and evidence["sha256"] == cold_draft.artifact_digest(edited)
    # Same completion makes the claim ambiguous rather than legacy-compatible.
    old["completed_at"] = json.loads(later.read_bytes())["completed_at"]
    earlier.write_bytes(work.records.json_bytes(old))
    (earlier.parent / "result.md.source.md").write_bytes((later.parent / "result.md.source.md").read_bytes())
    decision = work.decide(fixture, RULES)
    assert any("ambiguous" in row["reason"] for row in decision.invalid_markers)
    assert not decision.artifact_interpretation["qualifying_verdicts"]


@pytest.mark.parametrize("failure", ["missing", "wrong-kind", "wrong-draft", "partial", "bad-digest", "unsupported-route"])
def test_C6_876_semantic_reference_failures_cannot_anchor_a_later_valid_source(tmp_path, failure):
    fixture = bound_fixture(tmp_path, version="0.189.0")
    good = _source_settlement("would")
    bad = {
        "missing": good.replace("draft_comment=20", "draft_comment=999"),
        "wrong-kind": good.replace("draft_comment=20", "draft_comment=10"),
        "wrong-draft": good.replace("draft_comment=20", "draft_comment=30"),
        "partial": good.replace("draft_sha256=" + cold_draft.artifact_digest(SOURCE_DRAFT), ""),
        "bad-digest": good.replace(cold_draft.artifact_digest(SOURCE_DRAFT), "0" * 64),
        "unsupported-route": good.replace("route=would", "route=discharge"),
    }[failure]
    fixture.issue_comments[3]["body"] = bad
    fixture.issue_comments[4]["body"] = AMENDED + "MUST NOT INHERIT"
    fixture.issue_comments.append({"body": good, "user": {"login": PRODUCER}})
    comments(fixture)
    assert work.decide(fixture, RULES).stage == "holder-read"
    assert not fixture.artifact_phase.holder_readings
    assert fixture.artifact_phase.settlement_origin is fixture.artifact_phase.latest_settlement


def test_C6_876_omitted_reference_cannot_anchor_an_edited_or_wrong_judgment(tmp_path):
    fixture = bound_fixture(tmp_path)
    work.validate_marker_claims(fixture)
    brief, draft, verdict = fixture.raw_markers[:3]
    evidence = work._cold_judgment(fixture, verdict)
    pointer = work.markers([("<!-- tradecraft:artifact:v1 status=settled route=would -->", PRODUCER)])[0]
    assert work._settlement_identity(fixture, pointer, brief, draft, "would", evidence)
    for wrong in ({**evidence, "comment_id": "99"}, {**evidence, "sha256": "0" * 64}):
        assert work._settlement_identity(fixture, pointer, brief, draft, "would", wrong) is None


@pytest.mark.parametrize("attributes", ["draft_comment=20", "draft_comment=20 draft_sha256=bad"])
def test_C6_876_malformed_current_reference_cannot_fall_back_to_an_older_settlement(tmp_path, attributes):
    fixture = bound_fixture(tmp_path)
    fixture.issue_comments.append({
        "body": f"<!-- tradecraft:artifact:v1 status=settled route=would {attributes} -->",
        "user": {"login": PRODUCER},
    })
    comments(fixture)
    decision = work.decide(fixture, RULES)
    assert not decision.dispatch and decision.reason == "artifact-source-unusable"
    assert "artifact settlement" in decision.detail
    assert any(row["source_id"] == "60" for row in decision.invalid_markers)


@pytest.mark.parametrize("route", ["cap", "discharge", "unobtainable"])
def test_C6_876_unlawful_current_route_cannot_fall_back_to_an_older_settlement(
        tmp_path, monkeypatch, capsys, route):
    fixture = bound_fixture(tmp_path)
    fixture.issue_comments.append({
        "body": _source_settlement(route), "user": {"login": PRODUCER},
    })
    comments(fixture)
    decision = work.decide(fixture, RULES)
    assert not decision.dispatch and decision.reason == "artifact-source-unusable"
    assert "artifact settlement" in decision.detail and "route=" + route in decision.detail
    monkeypatch.setattr(work, "_invoke_recipient", lambda *_: pytest.fail("older settlement launched"))
    for stage in ("build", "floor", "review-disposition"):
        work._execute_stage(fixture, work.Decision(stage, True, "fresh", "fixture"), tmp_path, None)
        report = json.loads(capsys.readouterr().out)
        assert not report["dispatch"] and "route=" + route in report["detail"]
    fixture.issue_comments[-1]["body"] = _source_settlement("would")
    assert work.decide(fixture, RULES).stage == "build"
    assert fixture.artifact_phase.settlement_origin.source_id == "40"
    assert [row.source_id for row in fixture.artifact_phase.holder_readings] == ["50"]


def test_C2_876_miscopy_correction_and_restatement_never_spend_the_anchor(tmp_path):
    fixture = bound_fixture(tmp_path)
    good = _source_settlement("would")
    fixture.issue_comments[3]["body"] = good.replace(cold_draft.artifact_digest(SOURCE_DRAFT), "0" * 64)
    fixture.issue_comments[4]["body"] = AMENDED + "Keep the existing direction."
    decision = work.decide(fixture, RULES)
    assert not decision.dispatch and "miscopied while draft comment 20 is unchanged" in decision.detail
    assert "Re-settle with the judged digest " + cold_draft.artifact_digest(SOURCE_DRAFT) in decision.detail
    assert "a new cold seat is unnecessary" in decision.detail and "was edited" not in decision.detail
    assert decision.as_dict()["detail"] == decision.detail
    for identity in (60, 70):
        fixture.issue_comments.append({"id": identity, "body": good, "user": {"login": PRODUCER}})
        comments(fixture)
        decision = work.decide(fixture, RULES)
        assert decision.stage == "build"
        assert fixture.artifact_phase.settlement_origin.source_id == "40"
        assert fixture.artifact_phase.latest_settlement.source_id == str(identity)
        for stage in ("build", "floor", "review-disposition"):
            prompt = work._stage_prompt(fixture, work.Decision(stage, True, "fresh", "fixture"),
                                        floor_command="python fixture-check.py")
            assert b"Keep the existing direction." in prompt
        assert any("miscopied" in row["reason"] for row in decision.invalid_markers)
        assert decision.artifact_interpretation["qualifying_verdicts"][0]["binding_status"] == "bound"


@pytest.mark.parametrize("route", ["would", "discharge", "cap"])
@pytest.mark.parametrize("whole", [False, True])
def test_C4_876_old_referenced_whole_and_adverse_records_keep_visible_warnings(tmp_path, route, whole):
    support = [VERDICT] if route == "would" else [VERDICT.replace("verdict=would", "verdict=not-settleable")]
    if route == "cap": support = [VERDICT.replace("verdict=would", "verdict=would-not")] * 2
    fixture = comments(state(AFFIRMED, SOURCE_DRAFT, *support,
                             _source_settlement(route, reference=not whole), HOLDER))
    for index in range(len(support)):
        judgment(fixture, tmp_path, verdict_index=2 + index, version="0.189.0", name=f"old-{index}")
    decision = work.decide(fixture, RULES)
    assert decision.stage == "build"
    evidence = decision.artifact_interpretation["qualifying_verdicts"]
    assert len(evidence) == len(support)
    assert all(row["binding_status"] == "judged digest unrecorded" and row["sha256"] is None for row in evidence)
    assert all(row["bundle"] for row in evidence)
    assert json.dumps(decision.as_dict()).count("judged digest unrecorded") == len(support)


@pytest.mark.parametrize("malformed", ["missing", "disagreement", "fields", "input"])
def test_C4_876_modern_bad_binding_refuses_instead_of_becoming_compatibility(tmp_path, malformed):
    fixture = comments(state(AFFIRMED, SOURCE_DRAFT, VERDICT, _source_settlement("would"), HOLDER))
    judgment(fixture, tmp_path, malformed=malformed)
    decision = work.decide(fixture, RULES)
    assert decision.stage != "build"
    assert any(row["name"] == "cold-verdict" and "cold verdict bundle" in row["reason"] for row in decision.invalid_markers)


def test_C4_876_old_mismatch_is_unknown_and_bound_whole_artifact_cannot_bypass_reference(tmp_path):
    fixture = bound_fixture(tmp_path, version="0.189.0")
    fixture.issue_comments[3]["body"] = _source_settlement("would").replace(cold_draft.artifact_digest(SOURCE_DRAFT), "0" * 64)
    decision = work.decide(fixture, RULES)
    assert "preventing distinction between editing and copying" in decision.detail
    assert "Do not use the observed digest to re-settle: restore the judged text, or post a new draft for a fresh cold seat." in decision.detail
    assert "was edited" not in decision.detail and "was miscopied" not in decision.detail
    modern = bound_fixture(tmp_path / "modern")
    modern.issue_comments[3]["body"] = _source_settlement("would", reference=False)
    decision = work.decide(modern, RULES)
    assert not decision.dispatch and "bound would judgment requires draft_comment and draft_sha256" in decision.detail


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("same_time", [False, True])
def test_C5_C8_876_484_sequence_keeps_all_readings_through_repeated_forms(tmp_path, reverse, same_time):
    original = "<!-- tradecraft:artifact:v1 status=settled route=would -->\n" + VERDICT + "\nSee the draft for the artifact."
    first, second = AMENDED + "Direction one: keep A.", AMENDED + "Direction two: keep B."
    fixture = comments(state(AFFIRMED, SOURCE_DRAFT, AMENDED + "PRE-ANCHOR", original, first, second,
                             _source_settlement("would"), first, second, _source_settlement("would")))
    identities = [10, 20, 30, 5982701617, 5990000001, 5990000002, 6030116310, 6031381638, 6031381898, 6032000000]
    for comment, identity in zip(fixture.issue_comments, identities):
        comment["id"] = identity
    if same_time:
        for comment in fixture.issue_comments[3:]: comment["created_at"] = "2026-10-07T10:00:00+00:00"
    judgment(fixture, tmp_path, verdict_index=3, version="0.189.0")
    if reverse: fixture.issue_comments.reverse()
    decision = work.decide(fixture, RULES)
    assert decision.stage == "build"
    phase = fixture.artifact_phase
    assert phase.settlement_origin.source_id == "5982701617"
    assert [row.source_id for row in phase.holder_readings] == ["5990000001", "5990000002", "6031381638", "6031381898"]
    assert [row.body for row in phase.holder_readings] == [first, second, first, second]
    assert any(row["source_id"] == "5982701617" and "names no draft" in row["reason"] for row in decision.invalid_markers)
    for stage in ("build", "floor", "review-disposition"):
        prompt = work._stage_prompt(fixture, work.Decision(stage, True, "fresh", "fixture"),
                                    floor_command="python fixture-check.py")
        assert b"PRE-ANCHOR" not in prompt
        assert prompt.count(first.encode()) == prompt.count(second.encode()) == 2
        assert b"The newest governs where readings differ from each other." in prompt
    later = {"id": 6033000000, "body": AMENDED + "Direction two now changes to C.",
             "created_at": "2026-10-07T11:00:00+00:00", "user": {"login": PRODUCER}}
    fixture.issue_comments.append(later)
    work.decide(fixture, RULES)
    assert fixture.artifact_phase.holder_readings[-1].body == later["body"]


@pytest.mark.parametrize("barrier", ["brief", "draft", "verdict", "companion"])
def test_C6_876_every_lawful_barrier_ends_inheritance(tmp_path, barrier):
    fixture = bound_fixture(tmp_path)
    fixture.issue_comments[4]["body"] = AMENDED + "OLD READING"
    if barrier == "brief":
        fixture.issue_comments.extend({"body": body, "user": {"login": PRODUCER}} for body in (AFFIRMED, SOURCE_DRAFT))
        comments(fixture)
        new_id = str(fixture.issue_comments[-1]["id"])
    elif barrier == "draft":
        fixture.issue_comments.append({"body": SOURCE_DRAFT, "user": {"login": PRODUCER}})
        comments(fixture)
        new_id = str(fixture.issue_comments[-1]["id"])
    else: new_id = "20"
    if barrier != "companion":
        fixture.issue_comments.append({"body": VERDICT, "user": {"login": PRODUCER}})
        comments(fixture)
        judgment(fixture, tmp_path, verdict_index=len(fixture.issue_comments) - 1, draft_id=new_id, name="new")
        body = _source_settlement("would", draft_id=new_id)
    else: body = _source_settlement("would") + "\n" + VERDICT
    fixture.issue_comments.append({"body": body, "user": {"login": PRODUCER}})
    comments(fixture)
    if barrier == "companion":
        judgment(fixture, tmp_path, verdict_index=len(fixture.issue_comments) - 1, name="new")
    fixture.issue_comments.append({"body": HOLDER + "\nNEW READING", "user": {"login": PRODUCER}})
    comments(fixture)
    assert work.decide(fixture, RULES).stage == "build"
    assert [row.body for row in fixture.artifact_phase.holder_readings] == [HOLDER + "\nNEW READING"]
    assert fixture.artifact_phase.settlement_origin is fixture.artifact_phase.latest_settlement


@pytest.mark.parametrize("noise", ["> " + SOURCE_DRAFT, "prose\n" + VERDICT, "<!-- tradecraft:artifact:v1 status=bad -->",
                                  "ordinary comment", HOLDER, VERDICT.replace("qualified", "degraded")])
@pytest.mark.parametrize("unauthorized", [False, True])
def test_C6_876_nonqualifying_events_never_end_inheritance(tmp_path, noise, unauthorized):
    fixture = bound_fixture(tmp_path)
    fixture.issue_comments.append({"body": noise, "user": {"login": "outsider" if unauthorized else PRODUCER}})
    fixture.issue_comments.append({"body": _source_settlement("would"), "user": {"login": PRODUCER}})
    comments(fixture)
    assert work.decide(fixture, RULES).stage == "build"
    assert fixture.artifact_phase.settlement_origin.source_id == "40"
    assert fixture.artifact_phase.holder_readings[0].source_id == "50"


@pytest.mark.parametrize("route", ["discharge", "cap"])
@pytest.mark.parametrize("change", ["claim", "criterion", "whitespace", "unicode"])
def test_C7_876_carried_text_identity_excludes_transport_but_preserves_all_artifact_bytes(tmp_path, route, change):
    support = [VERDICT.replace("verdict=would", "verdict=not-settleable")]
    if route == "cap": support = [VERDICT.replace("verdict=would", "verdict=would-not")] * 2
    a = SOURCE_REVISED + "\nClaim A; criterion A; Unicode " + chr(0xE9) + ".  \n"
    b = {"claim": a.replace("Claim A", "Claim B"), "criterion": a.replace("criterion A", "criterion B"),
         "whitespace": a.replace(".  ", ". "), "unicode": a.replace(chr(0xE9), "e" + chr(0x301))}[change]
    first = _source_settlement(route, revised=a)
    fixture = comments(state(AFFIRMED, SOURCE_DRAFT, *support, first, AMENDED + "KEEP ORIGINAL"))
    for index in range(len(support)): judgment(fixture, tmp_path, verdict_index=2 + index, name=f"cold-{index}")
    original_id = str(fixture.issue_comments[-2]["id"])
    # Both routes ignore even missing named comments and wrong copied digests.
    second = _source_settlement(route, draft_id=99999, revised=a).replace(cold_draft.artifact_digest(SOURCE_DRAFT), "0" * 64)
    second = second.replace("SETTLEMENT EXPLANATION SENTINEL", "DIFFERENT OUTER TRANSPORT")
    fixture.issue_comments.append({"body": second, "user": {"login": PRODUCER}})
    comments(fixture)
    assert work.decide(fixture, RULES).stage == "build"
    assert fixture.artifact_phase.settlement_origin.source_id == original_id
    assert fixture.artifact_phase.holder_readings
    fixture.issue_comments.append({"body": _source_settlement(route, revised=b), "user": {"login": PRODUCER}})
    comments(fixture)
    assert work.decide(fixture, RULES).stage == "holder-read"
    assert not fixture.artifact_phase.holder_readings
    fixture.issue_comments.append({"body": second, "user": {"login": PRODUCER}})
    comments(fixture)
    assert work.decide(fixture, RULES).stage == "build"
    assert fixture.artifact_phase.settlement_origin.source_id == original_id
    assert fixture.artifact_phase.holder_readings[0].body == AMENDED + "KEEP ORIGINAL"


@pytest.mark.parametrize("route", ["discharge", "cap"])
def test_C7_876_bare_revision_pointer_has_no_anchor(tmp_path, route):
    support = [VERDICT.replace("verdict=would", "verdict=not-settleable")]
    if route == "cap": support = [VERDICT.replace("verdict=would", "verdict=would-not")] * 2
    pointer = f"<!-- tradecraft:artifact:v1 status=settled route={route} -->\nSee the draft."
    fixture = comments(state(AFFIRMED, SOURCE_DRAFT, *support, pointer, HOLDER, _source_settlement(route)))
    for index in range(len(support)): judgment(fixture, tmp_path, verdict_index=2 + index, name=f"seat-{index}")
    assert work.decide(fixture, RULES).stage == "holder-read"
    assert not fixture.artifact_phase.holder_readings


@pytest.mark.parametrize("route", ["discharge", "cap"])
def test_C7_quoted_blank_lines_remain_exact_carried_artifact_bytes(tmp_path, route):
    support = [VERDICT.replace("verdict=would", "verdict=not-settleable")]
    if route == "cap": support = [VERDICT.replace("verdict=would", "verdict=would-not")] * 2
    first = SOURCE_REVISED.replace("> Review risk", "> \n> Review risk")
    changed = SOURCE_REVISED.replace("> Review risk", "> \n> \n> Review risk")
    fixture = comments(state(AFFIRMED, SOURCE_DRAFT, *support,
                             _source_settlement(route, revised=first), AMENDED + "OLD READING"))
    for index in range(len(support)):
        judgment(fixture, tmp_path, verdict_index=2 + index, name=f"seat-{index}")
    fixture.issue_comments.append({"body": _source_settlement(route, revised=changed), "user": {"login": PRODUCER}})
    comments(fixture)
    assert work.decide(fixture, RULES).stage == "holder-read"
    assert not fixture.artifact_phase.holder_readings


@pytest.mark.parametrize("body,accepted", [(SOURCE_REVISED, True), ("missing body", False), ("> " + AFFIRMED, False),
                                          ("preamble\n" + SOURCE_REVISED, True),
                                          (SOURCE_REVISED.replace("\n", "\r\n"), True),
                                          (SOURCE_REVISED.replace("> Review risk", "> \n> Review risk"), True)])
def test_C7_raw_span_keeps_recognition_parity(body, accepted):
    span = dispatch_implementer.artifact_carried_span(AFFIRMED, body)
    assert dispatch_implementer.artifact_opening_carries_brief(AFFIRMED, body) is accepted
    assert (span is not None) is accepted
    if span:
        raw = body[span[0]:span[1]]
        assert raw.startswith("> <!-- tradecraft:affirmed-brief:v1 -->")
        assert raw.encode() in body.encode()


@pytest.mark.parametrize("route", ["discharge", "cap"])
def test_C7_882_trailing_note_is_carried_text_with_a_new_position(tmp_path, route):
    support = [VERDICT.replace("verdict=would", "verdict=not-settleable")]
    if route == "cap": support = [VERDICT.replace("verdict=would", "verdict=would-not")] * 2
    original = _source_settlement(route)
    fixture = comments(state(AFFIRMED, SOURCE_DRAFT, *support, original, AMENDED + "ORIGINAL DIRECTION"))
    for index in range(len(support)):
        judgment(fixture, tmp_path, verdict_index=2 + index, name=f"seat-{index}")
    original_id = str(fixture.issue_comments[-2]["id"])
    fixture.issue_comments.append({"body": original.replace("SETTLEMENT EXPLANATION SENTINEL", "NOTE ABOVE ARTIFACT"),
                                   "user": {"login": PRODUCER}})
    comments(fixture)
    assert work.decide(fixture, RULES).stage == "build"
    assert fixture.artifact_phase.settlement_origin.source_id == original_id
    trailing = original + "\nRe-posted to correct the digest; text unchanged."
    fixture.issue_comments.append({"body": trailing, "user": {"login": PRODUCER}})
    comments(fixture)
    assert work.decide(fixture, RULES).stage == "holder-read"
    assert fixture.artifact_phase.settlement_origin is fixture.artifact_phase.latest_settlement
    assert not fixture.artifact_phase.holder_readings
    assert fixture.artifact_phase.settled_artifact.body == trailing


@pytest.mark.parametrize("route", ["would", "unobtainable"])
@pytest.mark.parametrize("same_text", [False, True])
def test_C5_C7_882_compatibility_whole_artifact_uses_its_carried_identity(tmp_path, route, same_text):
    support = [VERDICT] if route == "would" else []
    x = SOURCE_REVISED + "\nCOMPATIBILITY TEXT X"
    y = x if same_text else SOURCE_REVISED + "\nCOMPATIBILITY TEXT Y"
    fixture = comments(state(AFFIRMED, SOURCE_DRAFT, *support,
                             _source_settlement(route, reference=False, revised=x), AMENDED + "READING AGAINST X"))
    if support: judgment(fixture, tmp_path, version="0.189.0")
    origin = str(fixture.issue_comments[-2]["id"])
    fixture.issue_comments.append({"body": _source_settlement(route, reference=False, revised=y),
                                   "user": {"login": PRODUCER}})
    comments(fixture)
    decision = work.decide(fixture, RULES)
    phase = fixture.artifact_phase
    assert decision.stage == ("build" if same_text else "holder-read")
    assert phase.settlement_origin.source_id == (origin if same_text else str(fixture.issue_comments[-1]["id"]))
    assert bool(phase.holder_readings) is same_text
    assert phase.settled_artifact.body == fixture.issue_comments[-1]["body"]
    for stage in ("build", "floor", "review-disposition"):
        prompt = work._stage_prompt(fixture, work.Decision(stage, True, "fresh", "fixture"), floor_command="fixture-check")
        assert (b"READING AGAINST X" in prompt) is same_text


@pytest.mark.parametrize("route", ["would", "unobtainable"])
@pytest.mark.parametrize("carried", [False, True])
@pytest.mark.parametrize("reference", [False, True])
def test_C5_C7_882_route_omission_keeps_draft_and_carried_correction_positions(
        tmp_path, route, carried, reference):
    support = [VERDICT] if route == "would" else []
    original = "<!-- tradecraft:artifact:v1 status=settled -->" + (
        SOURCE_REVISED if carried else "\nSee the judged draft.")
    corrected = _source_settlement(route, reference=reference)
    fixture = comments(state(AFFIRMED, SOURCE_DRAFT, *support, original,
                             AMENDED + "RETAIN THIS DIRECTION", corrected))
    if support:
        judgment(fixture, tmp_path, version="0.189.0")
    decision = work.decide(fixture, RULES)
    # A bare pointer establishes only the applicable draft, never carried text.
    inherited = reference or carried
    assert decision.stage == ("build" if inherited else "holder-read")
    phase = fixture.artifact_phase
    assert bool(phase.holder_readings) is inherited
    assert phase.settlement_origin.source_id == str(fixture.issue_comments[-3 if inherited else -1]["id"])
    assert any("route is missing" in row["reason"] for row in decision.invalid_markers)
    expected = SOURCE_DRAFT if reference else corrected
    assert phase.settled_artifact.body == expected
    for stage in ("build", "floor", "review-disposition"):
        prompt = work._stage_prompt(fixture, work.Decision(stage, True, "fresh", "fixture"),
                                    floor_command="fixture-check")
        assert (b"RETAIN THIS DIRECTION" in prompt) is inherited
        assert expected.encode() in prompt


@pytest.mark.parametrize("failure", ["historical-mismatch", "malformed-reference"])
def test_C6_C9_882_supported_route_with_broken_source_stays_unusable_for_revision(tmp_path, failure):
    fixture = bound_fixture(tmp_path, version="0.189.0" if failure == "historical-mismatch" else "0.190.0")
    if failure == "historical-mismatch":
        fixture.issue_comments[3]["body"] = _source_settlement("would", reference=False)
        fixture.issue_comments[1]["body"] = SOURCE_DRAFT.replace("original decision", "edited decision")
        broken = _source_settlement("would")
        diagnostic = "body does not match"
    else:
        broken = _source_settlement("would").replace(
            " draft_sha256=" + cold_draft.artifact_digest(SOURCE_DRAFT), "")
        diagnostic = "draft_sha256"
    fixture.issue_comments.extend({"body": body, "user": {"login": PRODUCER}}
                                 for body in (broken, AFFIRMED, AFFIRMED))
    comments(fixture)
    decision = work.decide(fixture, RULES)
    assert decision.stage == "artifact-source" and not decision.dispatch
    assert diagnostic in decision.detail
    assert fixture.artifact_phase.prior_artifact is None
    assert diagnostic in fixture.artifact_phase.prior_artifact_error
    with pytest.raises(work.WorkError, match=diagnostic):
        work._stage_prompt(fixture, work.Decision("artifact", True, "fresh", "fixture"))


@pytest.mark.parametrize("route", ["unobtainable", "discharge", "cap"])
def test_C6_C9_882_artifact_revision_keeps_last_effective_settlement_after_invalid_route(tmp_path, route):
    fixture = bound_fixture(tmp_path)
    fixture.issue_comments[4]["body"] = AMENDED + "S1 READING"
    fixture.issue_comments.extend({"body": body, "user": {"login": PRODUCER}} for body in (
        _source_settlement(route), AMENDED + "READING AFTER INVALID CLAIM"))
    comments(fixture)
    assert work.decide(fixture, RULES).reason == "artifact-source-unusable"
    fixture.issue_comments.append({"body": AFFIRMED + "\nAMENDED TERM", "user": {"login": PRODUCER}})
    comments(fixture)
    decision = work.decide(fixture, RULES)
    assert decision.stage == "artifact" and decision.dispatch
    phase = fixture.artifact_phase
    assert phase.prior_artifact.body == SOURCE_DRAFT and phase.prior_artifact_error is None
    assert [reading.body for reading in phase.prior_holder_readings] == [AMENDED + "S1 READING", AMENDED + "READING AFTER INVALID CLAIM"]
    assert work._artifact_source_problem(fixture, "artifact") is None
    prompt = work._stage_prompt(fixture, decision)
    assert SOURCE_DRAFT.encode() in prompt
    assert prompt.index(b"S1 READING") < prompt.index(b"READING AFTER INVALID CLAIM")


def test_C1_C4_882_two_unreported_seats_cannot_lend_the_second_digest_to_the_first_verdict(tmp_path):
    fixture = bound_fixture(tmp_path)
    original = tmp_path / "records" / "cold" / "result.md.run.json"
    first = json.loads(original.read_bytes())
    first["completed_at"] = (datetime.fromisoformat(first["completed_at"]) - timedelta(seconds=5)).isoformat()
    original.write_bytes(work.records.json_bytes(first))
    edited = SOURCE_DRAFT.replace("original decision", "rejected edit")
    second = judgment(fixture, tmp_path, body=edited, name="second-would-not", post_return=False)
    fixture.issue_comments[1]["body"] = edited
    fixture.issue_comments[3]["body"] = _source_settlement("would").replace(cold_draft.artifact_digest(SOURCE_DRAFT), cold_draft.artifact_digest(edited))
    decision = work.decide(fixture, RULES)
    assert not decision.dispatch or decision.stage != "build"
    assert decision.reason == "artifact-source-unusable" and "was edited after its verdict" in decision.detail
    evidence = decision.artifact_interpretation["qualifying_verdicts"]
    assert len(evidence) == 1 and evidence[0]["bundle"] == str(original)
    assert evidence[0]["sha256"] == cold_draft.artifact_digest(SOURCE_DRAFT)
    # A later, ordinary comment can report seat two without backdating anything.
    fixture.issue_comments.append({"body": VERDICT.replace("verdict=would", "verdict=would-not")
                                   + "\n" + (second.parent / "result.md.source.md").read_bytes().decode(),
                                   "user": {"login": PRODUCER}})
    comments(fixture)
    decision = work.decide(fixture, RULES)
    evidence = decision.artifact_interpretation["qualifying_verdicts"]
    assert len(evidence) == 2
    assert [row["bundle"] for row in evidence] == [str(original), str(second)]
    assert not any("ambiguous" in row["reason"] for row in decision.invalid_markers)


def test_C1_C4_882_unposted_seat_before_new_draft_does_not_poison_content_pairing(tmp_path):
    fixture = comments(state(AFFIRMED, SOURCE_DRAFT, VERDICT, SOURCE_DRAFT, VERDICT,
                             _source_settlement("would", draft_id=40), HOLDER))
    judgment(fixture, tmp_path, name="reported")
    older = judgment(fixture, tmp_path, verdict_index=3, name="unreported-old-draft", post_return=False)
    newer = judgment(fixture, tmp_path, verdict_index=4, draft_id="40", name="new-draft")
    decision = work.decide(fixture, RULES)
    assert decision.stage == "build"
    evidence = decision.artifact_interpretation["qualifying_verdicts"]
    assert [row["bundle"] for row in evidence] == [str(tmp_path / "records/reported/result.md.run.json"), str(newer)]
    assert str(older) not in [row["bundle"] for row in evidence]


def test_C1_C3_882_rejected_degraded_seat_does_not_deadlock_qualified_rerun(tmp_path):
    fixture = bound_fixture(tmp_path)
    unposted = tmp_path / "records/cold/result.md.run.json"
    run = json.loads(unposted.read_bytes())
    run.update(staffing_status="degraded", completed_at=(datetime.fromisoformat(run["completed_at"])
                                                       - timedelta(seconds=5)).isoformat())
    unposted.write_bytes(work.records.json_bytes(run))
    fixture.issue_comments[2]["body"] = VERDICT
    accepted = judgment(fixture, tmp_path, name="qualified-rerun")
    decision = work.decide(fixture, RULES)
    assert decision.stage == "build"
    evidence = decision.artifact_interpretation["qualifying_verdicts"]
    assert len(evidence) == 1 and evidence[0]["bundle"] == str(accepted)
    assert not any(row["name"] == "cold-verdict" for row in decision.invalid_markers)


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
def test_C1_C3_882_content_pairing_normalizes_lines_and_trailing_whitespace_only(tmp_path, ending):
    fixture = comments(state(AFFIRMED, SOURCE_DRAFT, VERDICT, _source_settlement("would"), HOLDER))
    source = ("Whole judgment with Unicode " + chr(0xE9) + ".  \nSecond line.\t\n").replace("\n", ending)
    selected = judgment(fixture, tmp_path, returned=source, post_return=False)
    fixture.issue_comments[2]["body"] += "\nWhole judgment with Unicode " + chr(0xE9) + ".\nSecond line.\n"
    assert work.decide(fixture, RULES).stage == "build"
    assert fixture.artifact_phase.judgments[0]["bundle"] == str(selected)
    fixture.issue_comments[2]["body"] = fixture.issue_comments[2]["body"].replace(chr(0xE9), "e" + chr(0x301))
    refusal = work.decide(fixture, RULES)
    assert any("post the seat's whole return" in row["reason"] for row in refusal.invalid_markers)


@pytest.mark.parametrize("problem", ["excerpt", "empty", "missing-result", "bad-result", "missing-path", "bad-path", "unreadable", "non-utf8", "oversized", "published-only"])
def test_C1_C4_882_modern_verdict_requires_the_whole_retained_source_return(tmp_path, monkeypatch, problem):
    fixture = bound_fixture(tmp_path)
    path = tmp_path / "records/cold/result.md.run.json"
    source = path.parent / "result.md.source.md"
    run = json.loads(path.read_bytes())
    if problem == "excerpt": fixture.issue_comments[2]["body"] = VERDICT + "\nSeat cold: the whole judgment.\n"
    elif problem == "empty": source.write_bytes(b" \t\n")
    elif problem == "missing-result": run.pop("result")
    elif problem == "bad-result": run["result"] = []
    elif problem == "missing-path": run["result"].pop("source_output")
    elif problem == "bad-path": run["result"]["source_output"] = {"path": str(source)}
    elif problem == "unreadable": source.unlink()
    elif problem == "non-utf8": source.write_bytes(b"\xff")
    elif problem == "oversized": monkeypatch.setattr(cold_draft, "MAX_INPUT_BYTES", 1)
    else:
        published = path.parent / "result.md"
        published.write_bytes(source.read_bytes())
        run["result"]["published_output"] = str(published)
        source.write_bytes(b"Another retained return.\n")
    path.write_bytes(work.records.json_bytes(run))
    decision = work.decide(fixture, RULES)
    assert decision.stage != "build" and not decision.artifact_interpretation["qualifying_verdicts"]
    error = next(row["reason"] for row in decision.invalid_markers if row["name"] == "cold-verdict")
    assert "post the seat's whole return with the marker" in error and str(path) in error


@pytest.mark.parametrize("routeless", [False, True])
def test_C5_C6_882_bound_reference_form_omission_keeps_reading_for_correction(
        tmp_path, monkeypatch, routeless):
    fixture = bound_fixture(tmp_path)
    fixture.issue_comments[3]["body"] = "<!-- tradecraft:artifact:v1 status=settled" + (
        "" if routeless else " route=would") + " -->" + SOURCE_REVISED
    fixture.issue_comments[4]["body"] = AMENDED + "FIRST APPLICABLE READING"
    fixture.issue_comments.append({"body": AMENDED + "SECOND APPLICABLE READING", "user": {"login": PRODUCER}})
    fixture.issue_comments.extend({"body": _source_settlement("would"), "user": {"login": PRODUCER}}
                                 for _ in range(2))
    comments(fixture)
    decision = work.decide(fixture, RULES)
    assert decision.stage == "build"
    phase = fixture.artifact_phase
    assert phase.settlement_origin.source_id == "40"
    assert [row.source_id for row in phase.holder_readings] == ["50", "60"]
    diagnostic = "route is missing" if routeless else "bound would judgment requires draft_comment and draft_sha256"
    assert any(diagnostic in row["reason"]
               and row["source_id"] == "40" for row in decision.invalid_markers)
    _assert_source_consumers(fixture, SOURCE_DRAFT, tmp_path, monkeypatch)


@pytest.mark.parametrize("problem", ["edited", "other-draft"])
def test_C5_C6_882_bound_form_omission_cannot_anchor_another_judged_text(tmp_path, problem):
    fixture = bound_fixture(tmp_path)
    fixture.issue_comments[3]["body"] = "<!-- tradecraft:artifact:v1 status=settled -->" + SOURCE_REVISED
    if problem == "edited":
        fixture.issue_comments[1]["body"] = SOURCE_DRAFT.replace("original decision", "edited decision")
    else:
        for suffix in (".request.json", ".run.json"):
            path = tmp_path / "records/cold" / ("result.md" + suffix)
            record = json.loads(path.read_bytes())
            record["judged_draft"]["comment_id"] = "99"
            path.write_bytes(work.records.json_bytes(record))
    work.validate_marker_claims(fixture)
    brief, draft, verdict, omitted = fixture.raw_markers[:4]
    evidence = work._cold_judgment(fixture, verdict)
    for infer_draft in (False, True):
        assert work._settlement_identity(fixture, omitted, brief, draft, "would", evidence,
                                         infer_draft=infer_draft) is None
    fixture.issue_comments.append({"body": _source_settlement("would"), "user": {"login": PRODUCER}})
    comments(fixture)
    decision = work.decide(fixture, RULES)
    assert decision.stage != "build" and fixture.artifact_phase.settlement_origin is None


def test_C4_882_historical_verdict_keeps_latest_time_selection_without_retained_return(tmp_path):
    fixture = bound_fixture(tmp_path, version="0.189.0")
    earlier = tmp_path / "records/cold/result.md.run.json"
    first = json.loads(earlier.read_bytes())
    first["completed_at"] = (datetime.fromisoformat(first["completed_at"]) - timedelta(seconds=5)).isoformat()
    first.pop("result")
    earlier.write_bytes(work.records.json_bytes(first))
    later = judgment(fixture, tmp_path, version="0.189.0", name="historical-later", post_return=False)
    run = json.loads(later.read_bytes())
    run.pop("result")
    later.write_bytes(work.records.json_bytes(run))
    fixture.issue_comments[2]["body"] = VERDICT
    decision = work.decide(fixture, RULES)
    assert decision.stage == "build"
    evidence = decision.artifact_interpretation["qualifying_verdicts"][0]
    assert evidence["bundle"] == str(later) and evidence["sha256"] is None
    assert evidence["binding_status"] == "judged digest unrecorded"


@pytest.mark.parametrize("version", [None, "unknown"])
def test_C4_882_unproved_latest_producer_version_cannot_pair_as_historical(tmp_path, version):
    fixture = bound_fixture(tmp_path)
    request_path = tmp_path / "records/cold/result.md.request.json"
    request = json.loads(request_path.read_bytes())
    request["producer_version"] = version
    request_path.write_bytes(work.records.json_bytes(request))
    decision = work.decide(fixture, RULES)
    assert decision.stage != "build" and not decision.artifact_interpretation["qualifying_verdicts"]
    assert any("no proved producer version" in row["reason"] for row in decision.invalid_markers)


def test_C4_882_unproved_older_bundle_does_not_replace_a_valid_content_pair(tmp_path):
    fixture = bound_fixture(tmp_path)
    older = judgment(fixture, tmp_path, name="unproved-older", post_return=False)
    request_path = older.with_name("result.md.request.json")
    request = json.loads(request_path.read_bytes())
    request.pop("producer_version")
    request_path.write_bytes(work.records.json_bytes(request))
    run = json.loads(older.read_bytes())
    run["completed_at"] = (datetime.fromisoformat(run["completed_at"]) - timedelta(seconds=5)).isoformat()
    older.write_bytes(work.records.json_bytes(run))
    decision = work.decide(fixture, RULES)
    assert decision.stage == "build"
    assert fixture.artifact_phase.judgments[0]["bundle"] == str(tmp_path / "records/cold/result.md.run.json")

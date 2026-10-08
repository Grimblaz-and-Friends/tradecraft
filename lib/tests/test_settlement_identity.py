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
                       WHOLE_ARTIFACT, SESSION, SHA, state, _source_settlement)

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
             version=cold_draft.BINDING_VERSION, name="cold", malformed=None):
    fixture.record_root = tmp_path / "records"
    folder = fixture.record_root / name
    folder.mkdir(parents=True)
    dispatch = folder / "result.md.dispatch.bin"
    dispatch.write_bytes(b"Judge the inlined draft.\n" + body.encode() + b"\nReturn a verdict.\n")
    binding = cold_draft.freeze(draft_id, body, dispatch.read_bytes())
    request = {"schema_version": 2, "work": "example/product#12", "stage": "cold-seat",
               "producer_version": version, "input": str(dispatch), "judged_draft": binding,
               "requested": {"vendor": "claude"}}
    completed = datetime.fromisoformat(fixture.issue_comments[verdict_index]["created_at"]) - timedelta(seconds=1)
    run = {"schema_version": 2, "outcome": "success", "completed_at": completed.isoformat(),
           "staffing_status": "qualified", "judged_draft": deepcopy(binding), "attempts": []}
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
    old["completed_at"] = (datetime.fromisoformat(old["completed_at"]) - timedelta(seconds=5)).isoformat()
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

"""CLI/report integration against independent duration and subagent ledgers."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys

import pytest

from test_holder_transcript import at, reply, write_lines, LIB
import change_cost as cost
import holder_transcript as ht


def card(start="2026-01-01T00:00:00Z", multiplier=1):
    return {"vendor": "claude", "model": "claude-opus-5-5", "effective_from": start,
            "effective_to": None, "currency": "USD", "per_tokens": 1000,
            "classes": {name: value * multiplier for name, value in {
                "input": 1, "output": 2, "cache_read": 3, "cache_creation": 11,
                "cache_write_5m": 5, "cache_write_1h": 7}.items()},
            "source_url": "https://example.test/card", "retrieved_at": at(0).isoformat()}


@pytest.fixture
def inputs(tmp_path):
    rates = tmp_path / "rates.json"
    rates.write_bytes(json.dumps({"schema_version": 1, "rates": [card()]}).encode())
    return {"repo": "acme/widget", "issue": 12, "dispatch_root": tmp_path / "dispatches",
            "rates_path": rates, "terms_path": tmp_path / "terms", "gauges_path": tmp_path / "gauges",
            "holder_path": tmp_path / "holder-usage.jsonl"}


@pytest.fixture
def transcript(tmp_path):
    projects = tmp_path / "projects"
    main = projects / "slug" / "holder.jsonl"
    write_lines(main, [reply("main")])
    child = main.parent / "holder" / "subagents" / "agent-child.jsonl"
    write_lines(child, [reply("child-reply", second=2, agent="child")])
    return projects, main, child


def close(inputs, transcript, second=10):
    return cost.holder_close(inputs["repo"], inputs["issue"], "claude", "requested-not-observed",
                             None, None, inputs["holder_path"], now=at(second),
                             session_id="holder", claude_projects=transcript[0])


def report(inputs):
    return cost.report(**inputs)


def holder_price(result):
    return next(row["value"] for row in result["dated_rate_card_equivalent"]
                if row["dispatch_id"].startswith("holder-close-"))


def bundle(inputs, identity="child", *, known=True, native=True, start=0, end=5, foreign=False,
           input=10, launched=True):
    folder = inputs["dispatch_root"] / "native"
    folder.mkdir(parents=True, exist_ok=True)
    request = {"schema_version": 2, "dispatch_id": "native", "work": "acme/widget#13" if foreign else "acme/widget#12",
               "requested": {"vendor": "claude", "model": "claude-opus-5-5", "continuity": "fresh", "session_id": None},
               "launched_at": at(start).isoformat(), "holder_session_id": "holder"}
    if native:
        request["recorded_at"] = at(start).isoformat()
    usage = {"change": {"repository": "acme/widget", "issue": 13 if foreign else 12},
             "dispatch": {"id": "native", "actual_vendor": "claude", "requested_vendor": "claude", "stage": "use",
                          "continuity": "fresh", "launched_at": at(start).isoformat(), "completed_at": at(end).isoformat()},
             "model": {"requested": "claude-opus-5-5", "reported": ["claude-opus-5-5"]},
             "tokens": {"models": {"claude-opus-5-5": {"input": input, "output": 3, "cache_read": 4, "cache_creation": 7}}} if known else None,
             "tokens_unknown_reason": None if known else "native counters unavailable", "scope": "invocation"}
    observed = {"source": "usage", "raw": {}, "normalized": {}, "thread_ids": [identity] if identity else []}
    if not launched:
        usage["tokens"] = None
        observed.update(source=None, raw=None, normalized=None)
    attempt = {"usage": usage, "observed": observed, "elapsed_seconds": 5 if launched else None}
    for name, value in [("answer.request.json", request), ("answer.run.json", {
            "schema_version": 2, "completed_at": at(end).isoformat(), "attempts": [attempt]})]:
        (folder / name).write_bytes(json.dumps(value).encode())
    return folder


def test_source_free_cli_named_session_and_report_select_actual_models(inputs, transcript, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "distractor")
    command = [sys.executable, str(LIB / "change_cost.py"), "holder-close", "--repo", inputs["repo"],
               "--issue", "12", "--vendor", "claude", "--model", "requested-not-observed",
               "--session-id", "holder", "--claude-projects", str(transcript[0]), "--output", str(inputs["holder_path"])]
    result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.isascii() and result.stderr == b""
    row = json.loads(result.stdout)
    assert row["model"]["reported"] == ["claude-opus-5-5"] and row["holder"]["session_id"] == "holder"
    value = holder_price(report(inputs))
    assert Decimal(value["amount"]) == Decimal(".146") and not value["floor"]
    other = transcript[1].parent / "other.jsonl"
    write_lines(other, [reply("other-reply", session="other")])
    cost.holder_close(inputs["repo"], 12, "claude", None, None, None, inputs["holder_path"],
                      session_id="other", claude_projects=transcript[0], now=at(10))
    assert Decimal(report(inputs)["total"]["known_amount"]) == Decimal(".219")


@pytest.mark.parametrize("case", ["unrecorded", "covered", "unknown", "foreign", "not-launched", "other-agent",
                                  "parent", "no-identity", "partial-counts", "partial-time", "late-completion", "copied"])
def test_subagent_coverage_recomputed_without_changing_dispatch_prices(inputs, transcript, tmp_path, case):
    if case not in {"unrecorded", "late-completion"}:
        folder = bundle(inputs, identity={"parent": "holder", "no-identity": None, "other-agent": "different"}.get(case, "child"),
                        known=case != "unknown", foreign=case == "foreign", launched=case != "not-launched",
                        input=1 if case == "partial-counts" else 10, start=3 if case == "partial-time" else 0)
        if case == "copied":
            import shutil
            shutil.copytree(folder, inputs["dispatch_root"] / "copied")
    row = close(inputs, transcript)
    result = report(inputs)
    value = holder_price(result)
    if case in {"covered", "copied"}:
        assert Decimal(value["amount"]) == Decimal(".073") and not value["floor"]
        assert value["dispatch_exclusions"] == [{"reply_id": "child-reply", "status": "excluded", "agent_id": "child",
                                                 "dispatch_id": "native", "attempt_index": 0}]
        assert Decimal(result["total"]["known_amount"]) == Decimal(".178")
    elif case in {"parent", "no-identity", "partial-counts"}:
        assert Decimal(value["amount"]) == Decimal(".073") and value["floor"]
        assert not value["dispatch_exclusions"]
        assert value["effective_agent_inclusion"][0]["candidate_dispatches"]
        assert any("overlap" in reason for reason in result["total"]["floor_reasons"])
    else:
        assert Decimal(value["amount"]) == Decimal(".146") and not value["floor"]
        assert not value["dispatch_exclusions"]
    if case == "late-completion":
        bundle(inputs)
        current = report(inputs)
        assert Decimal(holder_price(current)["amount"]) == Decimal(".073")
        assert current["raw_usage"][-1]["tokens"] == row["tokens"]
    if case == "unknown":
        assert result["total"]["unknown_dispatches"] == 1
        bundle(inputs, known=True)
        assert Decimal(holder_price(report(inputs))["amount"]) == Decimal(".073")


def test_agent_running_across_windows_only_excludes_priced_coverage(inputs, transcript):
    write_lines(transcript[2], [reply("child-later", 12, agent="child")], append=True)
    bundle(inputs, end=5)
    first = close(inputs, transcript)
    second = close(inputs, transcript, second=20)
    result = report(inputs)
    values = {row["dispatch_id"]: row["value"] for row in result["dated_rate_card_equivalent"]}
    assert Decimal(values[first["dispatch"]["id"]]["amount"]) == Decimal(".073")
    assert Decimal(values[second["dispatch"]["id"]]["amount"]) == Decimal(".073")
    assert values[second["dispatch"]["id"]]["effective_agent_inclusion"][0]["status"] == "included"


@pytest.mark.parametrize("recovered_first", [False, True])
@pytest.mark.parametrize("reverse_entries", [False, True])
def test_late_child_identity_refines_original_reply_without_another_charge(
        inputs, transcript, tmp_path, monkeypatch, recovered_first, reverse_entries):
    child_record = reply("child-reply", second=2)
    transcript[2].unlink()
    write_lines(transcript[1], [reply("main"), *([] if recovered_first else [child_record])])
    original = close(inputs, transcript)
    later = {**inputs, "issue": 13, "holder_path": tmp_path / "later-usage.jsonl"}
    if recovered_first:
        write_lines(transcript[1], [child_record], append=True)
        close(later, transcript, second=15)
    write_lines(transcript[2], [reply("child-reply", second=2, agent="child")])
    if reverse_entries:
        entries = ht._entries
        monkeypatch.setattr(ht, "_entries", lambda *args: list(reversed(entries(*args))))
    refined = close(later, transcript, second=20)
    assert refined["holder"]["recovered_closes"][0]["close_id"] == original["dispatch"]["id"]
    bundle(inputs)
    result = report(inputs)
    value = holder_price(result)
    assert Decimal(value["amount"]) == Decimal(".073") and not value["floor"]
    assert value["dispatch_exclusions"][0]["reply_id"] == "child-reply"
    assert Decimal(result["total"]["known_amount"]) == Decimal(".178")
    raw = next(row for row in result["raw_usage"] if row["dispatch"]["id"] == original["dispatch"]["id"])
    assert len(raw["holder"]["replies"]) == 2
    assert original["holder"]["replies"][-1]["agent_id"] is None
    repeated = close(later, transcript, second=30)
    assert repeated["holder"]["recovered_closes"] == []
    assert Decimal(report(later)["total"]["known_amount"]) == 0

    transcript[2].unlink()
    disappeared = close(later, transcript, second=35)
    assert disappeared["holder"]["recovered_closes"] == []
    assert not holder_price(report(inputs))["floor"]
    other = transcript[2].with_name("agent-other.jsonl")
    write_lines(other, [reply("child-reply", second=2, agent="other")])
    close(later, transcript, second=40)
    conflicted = holder_price(report(inputs))
    assert Decimal(conflicted["amount"]) == Decimal(".073") and conflicted["floor"]
    assert any("conflicting" in reason for reason in conflicted["floor_reasons"])

    receipt_path = Path(refined["holder"]["recovered_closes"][0]["journal"])
    incompatible = json.loads(receipt_path.read_bytes())
    incompatible["id"] = "late-replies-incompatible-agent"
    incompatible["row"]["dispatch"]["id"] = incompatible["id"]
    incompatible["row"]["holder"]["replies"][0]["agent_id"] = "other"
    ht._publish(receipt_path.parent, incompatible)
    assert holder_price(report(inputs))["status"] == "unknown"
    assert "conflicting late reply" in holder_price(report(inputs))["reason"]


def test_asymmetric_decimal_duration_prices_and_reply_date_selection(inputs, transcript):
    transcript[2].unlink()
    records = [reply("old", 1), reply("new", 12)]
    for record in records:
        record["message"]["usage"].update(iterations=[{"input_tokens": 999999}],
                                          output_tokens_details={"thinking_tokens": 3}, thinking_tokens=3)
    write_lines(transcript[1], records)
    first, second = card(), card(at(10).isoformat(), multiplier=2)
    first["effective_to"] = at(10).isoformat()
    inputs["rates_path"].write_bytes(json.dumps({"schema_version": 1, "rates": [first, second]}).encode())
    row = close(inputs, transcript, second=20)
    value = holder_price(report(inputs))
    # (10*1 + 3*2 + 4*3 + 2*5 + 5*7)/1000, then twice that.
    assert Decimal(value["amount"]) == Decimal(".073") + Decimal(".146")
    assert value["timestamp_basis"] == "reply time" and not value["floor"]
    assert [slice["effective_from"] for slice in value["rate_sources"]] == [first["effective_from"], second["effective_from"]]
    supplied = deepcopy(row)
    supplied.pop("holder")
    supplied["tokens"] = {"models": {"claude-opus-5-5": {"input": 10, "output": 3, "cache_read": 4, "cache_creation": 7}}}
    assert Decimal(cost.rate_card_equivalent(supplied, [first, second])["amount"]) == Decimal(".210")


def test_unmapped_native_count_and_compaction_are_named_floors_only_in_their_window(inputs, transcript):
    transcript[2].unlink()
    record = reply("main")
    record["message"]["usage"]["server_tool_use"] = {"web_search_requests": 1}
    boundary = {"type": "system", "subtype": "compact_boundary", "sessionId": "holder",
                "timestamp": at(3).isoformat(), "compactMetadata": {"preTokens": 999999, "postTokens": 10}, "durationMs": 12345}
    # A normal recorded reply near a boundary has no proof that it is the
    # internal summarization request. It counts once, and the limit stays named.
    write_lines(transcript[1], [record, boundary, {"type": "user", "isCompactSummary": True, "timestamp": at(4).isoformat()}, reply("ordinary", 5)])
    first = close(inputs, transcript)
    assert first["additional_native_classes"] == {"claude-opus-5-5": {"server_tool_use": {"web_search_requests": 1}}}
    value = holder_price(report(inputs))
    assert Decimal(value["amount"]) == Decimal(".146") and value["floor"]
    assert any("compaction request" in why for why in value["floor_reasons"])
    assert any("server_tool_use" in why for why in value["floor_reasons"])
    write_lines(transcript[1], [reply("later", 12)], append=True)
    second = close(inputs, transcript, second=20)
    assert not second["holder"]["gaps"]
    values = {entry["dispatch_id"]: entry["value"] for entry in report(inputs)["dated_rate_card_equivalent"]}
    assert not values[second["dispatch"]["id"]]["floor"]
    assert values[first["dispatch"]["id"]]["floor"]


def test_missing_child_and_identity_conflict_do_not_hide_main_amount(inputs, transcript, monkeypatch):
    original = Path.read_bytes
    def unreadable(path):
        if path == transcript[2]:
            raise PermissionError("child inaccessible")
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", unreadable)
    first = close(inputs, transcript)
    value = holder_price(report(inputs))
    assert Decimal(value["amount"]) == Decimal(".073") and value["floor"]
    assert "cannot read subagent" in first["holder"]["gaps"][0]["reason"]
    monkeypatch.setattr(Path, "read_bytes", original)
    write_lines(transcript[2], [reply("wrong-child", 12, agent="other")])
    second = close(inputs, transcript, second=20)
    assert "identity disagree" in second["holder"]["gaps"][0]["reason"]


def test_referenced_child_missing_from_snapshot_is_a_named_gap(inputs, transcript):
    transcript[2].unlink()
    write_lines(transcript[1], [{"type": "user", "timestamp": at(2).isoformat(),
                                "toolUseResult": {"agentId": "child", "status": "async_launched"}}], append=True)
    row = close(inputs, transcript)
    assert any("subagent child has no readable" in gap["reason"] for gap in row["holder"]["gaps"])
    assert holder_price(report(inputs))["floor"]


def test_torn_materialization_report_recovers_committed_row_and_respects_selected_destination(inputs, transcript):
    row = close(inputs, transcript)
    inputs["holder_path"].write_bytes(b'{"partial"')
    result = report(inputs)
    assert result["raw_usage"][0] == row and Decimal(result["total"]["known_amount"]) == Decimal(".146")
    assert result["total"]["floor"] and result["skipped_records"]
    alternate = {**inputs, "holder_path": inputs["holder_path"].with_name("alternate")}
    assert report(alternate)["raw_usage"] == []
    assert report({**inputs, "repo": "Acme/widget"})["raw_usage"] == []


def test_unsupported_automatic_vendor_is_actionable_and_parser_keeps_manual_sources(inputs):
    with pytest.raises(cost.CostError, match="--tokens-file or --unknown-reason"):
        cost.holder_close("acme/widget", 12, "codex", None, None, None, inputs["holder_path"])
    with pytest.raises(SystemExit):
        cost.parser().parse_args(["holder-close", "--repo", "a/b", "--issue", "12", "--vendor", "claude",
                                  "--tokens-file", "file", "--unknown-reason", "reason"])


def test_historical_claude_supplied_counters_stay_readable_and_overlap_is_named(inputs, transcript, tmp_path):
    supplied = tmp_path / "supplied"
    supplied.write_bytes(json.dumps({"tokens": {"models": {"claude-opus-5-5": {
        "input": 10, "output": 3, "cache_read": 4, "cache_creation": 7}}}, "scope": "invocation"}).encode())
    old = cost.holder_close("acme/widget", 12, "claude", None, supplied, None, inputs["holder_path"], now=at(1))
    assert "holder" not in old
    current = close(inputs, transcript)
    result = report(inputs)
    values = {row["dispatch_id"]: row["value"] for row in result["dated_rate_card_equivalent"]}
    assert Decimal(values[old["dispatch"]["id"]]["amount"]) == Decimal(".105")
    assert values[current["dispatch"]["id"]]["overlap_warnings"][0]["holder_close_ids"] == [old["dispatch"]["id"]]
    assert len(result["raw_usage"]) == 2


def test_transcript_population_without_duration_rate_stays_unpriced(inputs, transcript):
    transcript[2].unlink()
    rates = {"schema_version": 1, "rates": [card()]}
    del rates["rates"][0]["classes"]["cache_write_5m"]
    inputs["rates_path"].write_bytes(json.dumps(rates).encode())
    close(inputs, transcript)
    value = holder_price(report(inputs))
    assert value["status"] == "unknown" and "amount" not in value
    assert "cache_write_5m" in value["reason"]


@pytest.mark.parametrize("corruption", ["duration", "negative", "boolean", "extra"])
def test_retained_transcript_populations_are_validated_again_at_report_time(inputs, transcript, corruption):
    row = close(inputs, transcript)
    transcript[2].unlink()
    row["holder"]["replies"] = row["holder"]["replies"][:1]
    counts = row["holder"]["replies"][0]["tokens"]
    if corruption == "duration":
        counts["cache_write_5m"] = 99
    elif corruption == "negative":
        counts["output"] = -1
    elif corruption == "boolean":
        counts["input"] = True
    else:
        counts["new_billable_tokens"] = 3
    value = cost.rate_card_equivalent(row, [card()])
    assert value["status"] == "unknown" and "invalid duration/token" in value["reason"]


def test_late_compaction_evidence_marks_original_window_once(inputs, transcript, tmp_path):
    first = close(inputs, transcript)
    write_lines(transcript[1], [{"type": "system", "subtype": "compact_boundary", "timestamp": at(3).isoformat()}], append=True)
    second_destination = tmp_path / "another-change"
    second = cost.holder_close("acme/other", 99, "claude", None, None, None, second_destination,
                               now=at(20), session_id="holder", claude_projects=transcript[0])
    assert not second["holder"]["gaps"]
    assert second["holder"]["recovered_closes"][0]["close_id"] == first["dispatch"]["id"]
    value = holder_price(report(inputs))
    assert value["floor"] and any("compaction" in reason for reason in value["floor_reasons"])
    third = close(inputs, transcript, second=30)
    assert third["holder"]["recovered_closes"] == []
    values = {row["dispatch_id"]: row["value"] for row in report(inputs)["dated_rate_card_equivalent"]}
    assert len(values[first["dispatch"]["id"]]["late_recording_receipts"]) == 1


@pytest.mark.parametrize("damage", ["gap-null", "reply-null", "duplicate-reply", "bad-time", "bad-gap-reply-id"])
def test_malformed_selected_transcript_ledger_is_unknown_in_successful_report(inputs, transcript, damage):
    row = close(inputs, transcript)
    Path(row["holder"]["journal"]).unlink()
    if damage == "gap-null":
        row["holder"]["gaps"] = [None]
    elif damage == "reply-null":
        row["holder"]["replies"] = [None]
    elif damage == "duplicate-reply":
        row["holder"]["replies"].append(deepcopy(row["holder"]["replies"][0]))
    elif damage == "bad-time":
        row["holder"]["replies"][0]["timestamp"] = "invalid"
    else:
        row["holder"]["gaps"] = [{"source": "fixture", "timestamp": None, "reason": "conflict", "reply_id": []}]
    write_lines(inputs["holder_path"], [row])
    result = report(inputs)
    assert holder_price(result)["status"] == "unknown" and result["total"]["unknown_dispatches"] == 1


def test_conflicting_native_session_identities_cannot_prove_child_exclusion(inputs, transcript):
    folder = bundle(inputs)
    request_path = folder / "answer.request.json"
    request = json.loads(request_path.read_bytes())
    request["requested"]["session_id"] = "holder"
    request_path.write_bytes(json.dumps(request).encode())
    close(inputs, transcript)
    value = holder_price(report(inputs))
    assert not value["dispatch_exclusions"] and value["floor"]
    assert value["effective_agent_inclusion"][0]["status"] == "unresolved"


def test_transcript_normalization_retains_counts_without_vendor_money(inputs, transcript):
    transcript[2].unlink()
    record = reply("main")
    record["message"]["usage"].update(costUSD=123, server_tool_use={"web_search_requests": 1, "costUSD": 50})
    write_lines(transcript[1], [record])
    row = close(inputs, transcript)
    assert not cost._contains_money_key(row)
    assert row["additional_native_classes"] == {"claude-opus-5-5": {"server_tool_use": {"web_search_requests": 1}}}


def test_readable_native_counters_with_unknown_price_cannot_exclude_child(inputs, transcript):
    folder = bundle(inputs)
    path = folder / "answer.run.json"
    run = json.loads(path.read_bytes())
    run["attempts"][0]["usage"]["additional_native_classes"] = {"claude-opus-5-5": {"web_search_requests": 1}}
    path.write_bytes(json.dumps(run).encode())
    close(inputs, transcript)
    result = report(inputs)
    assert result["total"]["unknown_dispatches"] == 1
    value = holder_price(result)
    assert Decimal(value["amount"]) == Decimal(".146") and not value["floor"]
    assert value["effective_agent_inclusion"][0]["status"] == "included"


@pytest.mark.parametrize("case", ["later-replay", "original-time-replay", "rewritten-usage",
                                  "earlier-timestamp", "malformed-replay", "late-recovered-reply"])
def test_later_contradiction_unprices_only_affected_reply_in_its_original_close(inputs, transcript, tmp_path, case):
    transcript[2].unlink()
    bad = reply("contradicted", second=3, input=900)
    good = reply("independent", second=2)
    write_lines(transcript[1], [good] if case == "late-recovered-reply" else [good, bad])
    first = close(inputs, transcript)
    if case == "late-recovered-reply":
        write_lines(transcript[1], [bad], append=True)
        close(inputs, transcript, second=15)
    replacement = reply("contradicted", second=18 if case in {"later-replay", "late-recovered-reply"} else 3, input=10)
    if case == "earlier-timestamp":
        replacement = reply("contradicted", second=1, input=900)
    elif case == "malformed-replay":
        replacement["message"]["usage"]["output_tokens"] = -1
    write_lines(transcript[1], [good, replacement] if case == "rewritten-usage" else [replacement],
                append=case != "rewritten-usage")
    second = cost.holder_close("acme/other", 99, "claude", None, None, None, tmp_path / "other",
                               now=at(20), session_id="holder", claude_projects=transcript[0])
    assert second["holder"]["recovered_closes"][0]["close_id"] == first["dispatch"]["id"]
    assert not second["holder"]["gaps"]
    def original_price(result):
        return next(row["value"] for row in result["dated_rate_card_equivalent"]
                    if row["dispatch_id"] == first["dispatch"]["id"])
    result = report(inputs)
    value = original_price(result)
    assert value["status"] == "known" and value["floor"]
    assert Decimal(value["amount"]) == Decimal(".073")
    assert value["unresolved_reply_ids"] == ["contradicted"]
    assert [row["reply_id"] for row in value["rate_sources"]] == ["independent"]
    original = next(row for row in result["raw_usage"] if row["dispatch"]["id"] == first["dispatch"]["id"])
    assert {row["id"] for row in original["holder"]["replies"]} == {"independent", "contradicted"}
    assert original["holder"]["window"] == first["holder"]["window"]
    assert close(inputs, transcript, second=30)["holder"]["recovered_closes"] == []
    assert original_price(report(inputs))["amount"] == value["amount"]


def test_contradiction_of_only_committed_reply_is_unknown_not_positive_floor(inputs, transcript):
    transcript[2].unlink()
    first = close(inputs, transcript)
    write_lines(transcript[1], [reply("main", second=15, input=1)], append=True)
    close(inputs, transcript, second=20)
    value = next(row["value"] for row in report(inputs)["dated_rate_card_equivalent"]
                 if row["dispatch_id"] == first["dispatch"]["id"])
    assert value["status"] == "unknown" and "amount" not in value
    assert value["unresolved_reply_ids"] == ["main"] and value["late_recording_receipts"]
    assert value["window"] == first["holder"]["window"]


@pytest.mark.parametrize("case", ["nested-uncovered", "nested-scalar-dispatch", "flat-uncovered", "flat-partial",
                                  "flat-covered", "retained-negative"])
def test_subagent_exclusion_requires_priced_coverage_of_additional_native_counts(inputs, transcript, case):
    count = {"server_tool_use": {"web_search_requests": 1}} if case.startswith("nested") else {"billable_extra_tokens": 2}
    record = reply("child-reply", second=2, agent="child")
    record["message"]["usage"].update(count)
    write_lines(transcript[2], [record])
    rates = card()
    rates["classes"]["billable_extra_tokens"] = 5
    rates["classes"]["server_tool_use"] = 5
    inputs["rates_path"].write_bytes(json.dumps({"schema_version": 1, "rates": [rates]}).encode())
    folder = bundle(inputs)
    if case in {"flat-partial", "flat-covered", "retained-negative", "nested-scalar-dispatch"}:
        path = folder / "answer.run.json"
        run = json.loads(path.read_bytes())
        run["attempts"][0]["usage"]["additional_native_classes"] = {"claude-opus-5-5": {
            "server_tool_use": 1} if case == "nested-scalar-dispatch" else {
                "billable_extra_tokens": 1 if case == "flat-partial" else 2}}
        path.write_bytes(json.dumps(run).encode())
    row = close(inputs, transcript)
    if case == "retained-negative":
        Path(row["holder"]["journal"]).unlink()
        next(r for r in row["holder"]["replies"] if r["agent_id"])["additional_native_classes"]["billable_extra_tokens"] = -1
        write_lines(inputs["holder_path"], [row])
    result = report(inputs)
    value = holder_price(result)
    assert Decimal(value["amount"]) == Decimal(".073")
    if case == "flat-covered":
        assert not value["floor"] and value["dispatch_exclusions"]
        assert Decimal(result["total"]["known_amount"]) == Decimal(".188")
    else:
        assert value["floor"] and not value["dispatch_exclusions"]
        assert result["total"]["floor"] and any("additional native counts not covered" in r for r in value["floor_reasons"])
        assert value["effective_agent_inclusion"][0]["status"] == "unresolved"


@pytest.mark.parametrize("covered", [False, True])
def test_dated_card_can_price_additional_flat_native_counts_without_pricing_aggregate_writes_twice(inputs, transcript, covered):
    transcript[2].unlink()
    record = reply("main")
    record["message"]["usage"]["billable_extra_tokens"] = 2
    write_lines(transcript[1], [record])
    if covered:
        rates = card()
        rates["classes"]["billable_extra_tokens"] = 5
        inputs["rates_path"].write_bytes(json.dumps({"schema_version": 1, "rates": [rates]}).encode())
    close(inputs, transcript)
    value = holder_price(report(inputs))
    assert Decimal(value["amount"]) == Decimal(".083" if covered else ".073")
    assert value["floor"] is not covered


@pytest.mark.parametrize("name,count", [("billable_extra_tokens", -1), ("billable_extra_tokens", True),
                                      ("input", 10), ("input", 0), ("unpriced_tokens", 0)])
def test_retained_native_extra_counts_cannot_reduce_or_duplicate_observed_token_price(inputs, transcript, name, count):
    transcript[2].unlink()
    row = close(inputs, transcript)
    row["holder"]["replies"][0]["additional_native_classes"] = {name: count}
    rates = card()
    rates["classes"]["billable_extra_tokens"] = 5
    value = cost.rate_card_equivalent(row, [rates])
    assert Decimal(value["amount"]) == Decimal(".073")
    assert value["floor"] is (count != 0)


@pytest.mark.parametrize("fault", ["torn", "non-object", "naive-time", "unreadable-child"])
def test_untimed_gap_is_attributed_once_and_later_empty_close_is_known_zero(inputs, transcript, tmp_path, monkeypatch, fault):
    if fault == "unreadable-child":
        read_bytes = Path.read_bytes
        def unreadable(path):
            if path == transcript[2]:
                raise PermissionError("child inaccessible")
            return read_bytes(path)
        monkeypatch.setattr(Path, "read_bytes", unreadable)
    else:
        transcript[2].unlink()
        if fault == "torn":
            with transcript[1].open("ab") as stream:
                stream.write(b'{"partial":')
        elif fault == "non-object":
            write_lines(transcript[1], [None], append=True)
        else:
            broken = reply("naive")
            broken["timestamp"] = "2026-10-10T12:00:02"
            write_lines(transcript[1], [broken], append=True)
    first = close(inputs, transcript)
    assert first["holder"]["gaps"] and holder_price(report(inputs))["floor"]
    later = {**inputs, "issue": 13, "holder_path": tmp_path / "later.jsonl"}
    for second in (20, 30):
        row = close(later, transcript, second=second)
        assert row["holder"]["observed_empty"] and not row["holder"]["gaps"]
        assert row["holder"]["recovered_closes"] == []
    result = report(later)
    assert result["total"]["known_amount"] == "0" and not result["total"]["floor"]
    assert all(price["value"]["status"] == "known" for price in result["dated_rate_card_equivalent"])
    assert holder_price(report(inputs))["floor"]


@pytest.mark.parametrize("damage", ["history", "branched", "lock", "invalid-identity"])
@pytest.mark.parametrize("supplied", ["tokens", "unknown"])
def test_explicit_claude_cli_records_when_boundary_registration_is_unavailable(inputs, transcript, tmp_path, monkeypatch, damage, supplied):
    from contextlib import nullcontext
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "holder")
    original = close(inputs, transcript)
    journal = Path(original["holder"]["journal"])
    if damage == "history":
        journal.write_bytes(b"{}")
    elif damage == "branched":
        entry = json.loads(journal.read_bytes())
        entry["id"] = entry["row"]["dispatch"]["id"] = "holder-close-branch"
        (journal.parent / (entry["id"] + ".json")).write_bytes(json.dumps(entry).encode())
    elif damage == "invalid-identity":
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "../holder")
    before = {str(path): path.read_bytes() for path in ht.default_state_root().rglob("*.json")}
    destination = tmp_path / "manual.jsonl"
    command = [sys.executable, str(LIB / "change_cost.py"), "holder-close", "--repo", inputs["repo"],
               "--issue", "12", "--vendor", "claude", "--output", str(destination)]
    if supplied == "tokens":
        attachment = tmp_path / "tokens.json"
        attachment.write_bytes(json.dumps({"tokens": {"models": {"claude-opus-5-5": {
            "input": 10, "output": 3, "cache_read": 4, "cache_creation": 7}}}, "scope": "invocation"}).encode())
        command.extend(["--tokens-file", str(attachment)])
    else:
        command.extend(["--unknown-reason", "explicit caller reason"])
    with ht.session_lock(journal.parent) if damage == "lock" else nullcontext():
        completed = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    row = json.loads(completed.stdout)
    assert completed.stdout.isascii() and completed.stderr == b""
    assert row["holder"]["source_kind"] == "supplied"
    assert not row["holder"]["window"]["boundary_registered"]
    assert row["holder"]["window"]["boundary_unknown_reason"]
    assert "journal" not in row["holder"]
    assert [json.loads(line) for line in destination.read_bytes().splitlines() if line.strip()] == [row]
    assert before == {str(path): path.read_bytes() for path in ht.default_state_root().rglob("*.json")}
    value = holder_price(report({**inputs, "holder_path": destination}))
    if supplied == "tokens":
        assert Decimal(value["amount"]) == Decimal(".105")
    else:
        assert value["status"] == "unknown" and "explicit caller reason" in value["reason"]


@pytest.mark.parametrize("agent", [False, True])
@pytest.mark.parametrize("count", ["bad", None, [], {}, True, -1, 1.5])
def test_malformed_retained_token_count_is_unknown_even_with_priced_child_coverage(inputs, transcript, agent, count):
    bundle(inputs)
    original = close(inputs, transcript)
    assert not holder_price(report(inputs))["floor"]
    Path(original["holder"]["journal"]).unlink()
    selected = next(reply for reply in original["holder"]["replies"] if bool(reply["agent_id"]) == agent)
    selected["tokens"]["input"] = count
    write_lines(inputs["holder_path"], [original])
    result = report(inputs)
    value = holder_price(result)
    assert value["status"] == "unknown" and "invalid duration/token" in value["reason"]
    assert result["total"]["unknown_dispatches"] == 1 and result["total"]["floor"]


@pytest.mark.parametrize("fault", ["damaged", "unreadable"])
def test_unattributed_journal_problem_warns_once_without_flooring_unrelated_change(inputs, transcript, tmp_path, monkeypatch, fault):
    original = close(inputs, transcript)
    unrelated = {**inputs, "repo": "elsewhere/product", "issue": 99, "holder_path": tmp_path / "unrelated.jsonl"}
    other_main = transcript[1].parent / "other.jsonl"
    write_lines(other_main, [reply("other-reply", session="other")])
    cost.holder_close(unrelated["repo"], unrelated["issue"], "claude", None, None, None, unrelated["holder_path"],
                      now=at(10), session_id="other", claude_projects=transcript[0])
    journal = Path(original["holder"]["journal"])
    if fault == "damaged":
        journal.write_bytes(b"{}")
    else:
        read_bytes = Path.read_bytes
        def unreadable(path):
            if path == journal:
                raise PermissionError("unreadable session journal")
            return read_bytes(path)
        monkeypatch.setattr(Path, "read_bytes", unreadable)
    result = report(unrelated)
    assert Decimal(result["total"]["known_amount"]) == Decimal(".073")
    assert not result["total"]["floor"] and result["skipped_records"] == []
    assert len(result["warnings"]) == 1 and result["warnings"][0]["path"] == str(journal.parent)
    # The original destination is identifiable from its materialized close.
    selected = report(inputs)
    assert selected["total"]["floor"] and selected["skipped_records"]


@pytest.mark.parametrize("input_count,extra", [(0, None), (1, None), (0, 1)])
def test_unrated_synthetic_reply_needs_a_rate_only_for_positive_billable_counts(inputs, transcript, input_count, extra):
    transcript[2].unlink()
    synthetic = reply("synthetic", model="<synthetic>", input=input_count, output=0, read=0, five=0, hour=0)
    if extra is not None:
        synthetic["message"]["usage"]["billable_extra_tokens"] = extra
    write_lines(transcript[1], [synthetic])
    close(inputs, transcript)
    result = report(inputs)
    value = holder_price(result)
    if input_count or extra:
        assert value["status"] == "unknown" and "no dated rate" in value["reason"]
        assert result["total"]["floor"]
    else:
        assert value["status"] == "known" and value["amount"] == "0" and not value["floor"]
        assert not result["total"]["floor"]


@pytest.mark.parametrize("optional", [None, {}, {"web_search_requests": 0}])
def test_null_optional_server_tool_usage_keeps_the_reply_price(inputs, transcript, optional):
    transcript[2].unlink()
    record = reply("main")
    record["message"]["usage"]["server_tool_use"] = optional
    write_lines(transcript[1], [record])
    row = close(inputs, transcript)
    value = holder_price(report(inputs))
    assert {reply["id"] for reply in row["holder"]["replies"]} == {"main"}
    assert not row["holder"]["gaps"]
    assert Decimal(value["amount"]) == Decimal(".073") and not value["floor"]


def test_unregistered_supplied_boundary_is_visible_if_automatic_capture_later_succeeds(inputs, transcript, tmp_path, monkeypatch):
    transcript[2].unlink()
    attachment = tmp_path / "supplied.json"
    attachment.write_bytes(json.dumps({"tokens": {"models": {"claude-opus-5-5": {
        "input": 10, "output": 3, "cache_read": 4, "cache_creation": 7}}}, "scope": "invocation"}).encode())
    def unavailable(*args, **kwargs):
        raise ht.TranscriptError("holder session lock timed out; no close recorded")
    with monkeypatch.context() as patch:
        patch.setattr(ht, "session_lock", unavailable)
        manual = cost.holder_close(inputs["repo"], 12, "claude", None, attachment, None,
                                   inputs["holder_path"], session_id="holder", now=at(10))
    automatic = close(inputs, transcript, second=20)
    assert automatic["holder"]["window"]["previous_close_id"] is None
    values = {row["dispatch_id"]: row["value"] for row in report(inputs)["dated_rate_card_equivalent"]}
    assert values[automatic["dispatch"]["id"]]["overlap_warnings"] == [{
        "reason": "supplied Claude counters have no registered session boundary; overlap with transcript usage cannot be established",
        "holder_close_ids": [manual["dispatch"]["id"]]}]


def test_documented_supplied_source_command_selects_codex_vendor_and_prices_its_counters(inputs, tmp_path):
    import re
    import shlex
    text = (LIB.parent / "skills" / "engagement" / "references" / "dispatch-records.md").read_text(encoding="utf-8")
    commands = re.findall(r"`(python <plugin-root>/lib/change_cost.py holder-close [^`]+)`", text)
    manual = next((command for command in commands if "--tokens-file FILE" in command), None)
    assert manual is not None, "The supplied-source procedure needs its own command and vendor."
    attachment = tmp_path / "codex-tokens.json"
    attachment.write_bytes(json.dumps({"model": "gpt-6.1-sol", "tokens": {
        "input_tokens": 20, "cached_input_tokens": 10, "cache_write_input_tokens": 0, "output_tokens": 4,
        "reasoning_output_tokens": 1}, "scope": "invocation"}).encode())
    replacements = {"python": sys.executable, "<plugin-root>/lib/change_cost.py": str(LIB / "change_cost.py"),
                    "OWNER/REPO": inputs["repo"], "N": "12", "VENDOR": "codex", "MODEL": "gpt-6.1-sol", "FILE": str(attachment)}
    command = [replacements.get(part, part) for part in shlex.split(manual)]
    command.extend(["--output", str(inputs["holder_path"])])
    completed = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    row = json.loads(completed.stdout)
    assert row["dispatch"]["actual_vendor"] == "codex"
    value = cost.rate_card_equivalent(row, cost.load_rates(LIB / "rates.json"))
    assert value["status"] == "known", value


@pytest.mark.parametrize("extra", [None, False, "", [], {}])
def test_zero_reply_does_not_assume_malformed_retained_native_counts_are_free(inputs, transcript, extra):
    transcript[2].unlink()
    write_lines(transcript[1], [reply("zero", model="<synthetic>", input=0, output=0, read=0, five=0, hour=0)])
    row = close(inputs, transcript)
    row["holder"]["replies"][0]["additional_native_classes"] = {"billable_extra_tokens": extra}
    value = cost.rate_card_equivalent(row, [card()])
    assert value["status"] == "unknown"


def test_zero_child_has_no_monetary_overlap_to_resolve(inputs, transcript):
    write_lines(transcript[2], [reply("child-reply", second=2, agent="child", input=0, output=0, read=0, five=0, hour=0)])
    bundle(inputs, identity=None)
    close(inputs, transcript)
    result = report(inputs)
    value = holder_price(result)
    assert Decimal(value["amount"]) == Decimal(".073") and not value["floor"]
    assert value["effective_agent_inclusion"][0]["status"] == "included"
    assert not result["total"]["floor"]

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import change_cost as cost
import dispatch_record as records


WHEN = "2026-09-19T12:00:00+00:00"


def usage(vendor="codex", model="gpt-fixture", tokens=None, scope="invocation",
          dispatch_id="dispatch-1", stage="build"):
    return {
        "change": {"repository": "acme/widget", "issue": 12, "unknown_reason": None},
        "dispatch": {
            "id": dispatch_id, "requested_vendor": vendor, "actual_vendor": vendor,
            "stage": stage, "continuity": "fresh", "launched_at": WHEN,
            "completed_at": WHEN, "staffing_status": "qualified",
        },
        "model": {"requested": model, "reported": [model], "reported_unknown_reason": None},
        "tokens": tokens or {"input": 100, "cached_input": 20, "output": 10,
                              "reasoning_output": 5},
        "tokens_unknown_reason": None, "additional_native_classes": {}, "scope": scope,
        "source_field": "turn.completed.usage", "raw_source": "fixture.stdout.log",
        "runtime_version": "fixture 1", "runtime_version_unknown_reason": None,
    }


def rate(model="gpt-fixture"):
    return {
        "vendor": "codex", "model": model,
        "effective_from": "2026-01-01T00:00:00+00:00", "effective_to": None,
        "currency": "USD", "per_tokens": 1000,
        "classes": {"input": 1, "cached_input": 0.5, "output": 2,
                    "reasoning_output": 2, "cache_read": None,
                    "cache_write_5m": None, "cache_write_1h": None},
        "source_url": "https://example.test/rates", "retrieved_at": WHEN,
    }


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value) + "\n").encode())


@pytest.fixture
def report_inputs(tmp_path):
    rates_path = tmp_path / "rates.json"
    write_json(rates_path, {"schema_version": 1, "rates": [rate()]})
    return {
        "repo": "acme/widget", "issue": 12,
        "dispatch_root": tmp_path / "dispatches", "rates_path": rates_path,
        "terms_path": tmp_path / "terms.json", "gauges_path": tmp_path / "gauges.jsonl",
        "holder_path": tmp_path / "holder.jsonl",
    }


def report_arguments(inputs):
    return [
        "report", "--repo", inputs["repo"], "--issue", str(inputs["issue"]),
        "--dispatch-root", str(inputs["dispatch_root"]), "--rates", str(inputs["rates_path"]),
        "--plan-terms", str(inputs["terms_path"]), "--gauges", str(inputs["gauges_path"]),
        "--holder-usage", str(inputs["holder_path"]),
    ]


def report_cli(inputs):
    return subprocess.run(
        [sys.executable, str(LIB / "change_cost.py"), *report_arguments(inputs)],
        stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8", timeout=60,
    )


def write_bundle(inputs, name, work="acme/widget#12", rows=None, completion=None):
    # Suffix pairing must work for caller-selected output names.
    output = inputs["dispatch_root"] / name / "answer.v2.txt"
    request = records.request_record(
        dispatch_id=name, work=work, stage="use", settings_source="fixture",
        settings_scope="use", vendor="claude", model="requested-only", effort="xhigh",
        continuity="fresh", permission_boundary="fixture", root=None,
        now=datetime.fromisoformat(WHEN),
    )
    request_path = records.sidecar(output, ".request.json")
    run_path = records.sidecar(output, ".run.json")
    write_json(request_path, request)
    if completion is None:
        write_json(run_path, {"schema_version": 2, "attempts": [
            {"usage": row} for row in (rows if rows is not None else [usage()])
        ]})
    else:
        run_path.write_bytes(completion)
    return request_path, run_path, request


@pytest.mark.parametrize("work", ["acme/widget#13", "other/widget#12", "12", "issue-12"])
@pytest.mark.parametrize("completion", [b"", b"{", b'{"schema_version": 2, "attempts": []}'])
def test_foreign_and_unqualified_requests_never_open_completions(
        report_inputs, monkeypatch, work, completion):
    target_request, target_path, _ = write_bundle(report_inputs, "target")
    request_path, foreign_path, _ = write_bundle(
        report_inputs, "acme-widget-12-suggestive", work=work, completion=completion,
    )
    baseline = cost.report(**report_inputs)
    reads = []
    original = Path.read_bytes

    def checked_read(path):
        reads.append(path)
        assert path != foreign_path, "an unrelated completion was opened"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", checked_read)
    result = cost.report(**report_inputs)
    assert request_path in reads and target_path in reads
    assert reads.index(target_request) < reads.index(target_path)
    assert result == baseline
    assert result["raw_usage"] == [usage()]
    assert result["skipped_records"] == []


@pytest.mark.parametrize("failure", ["empty", "malformed", "read-error"])
def test_target_gap_is_one_unknown_attempt_in_successful_cli_report(
        report_inputs, monkeypatch, capsys, failure):
    write_bundle(report_inputs, "a-readable")
    _, path, request = write_bundle(
        report_inputs, "b-gap", completion=b"{" if failure == "malformed" else b"",
    )
    if failure == "read-error":
        original = Path.read_bytes

        def unavailable(candidate):
            if candidate == path:
                raise PermissionError("injected completion read failure")
            return original(candidate)

        monkeypatch.setattr(Path, "read_bytes", unavailable)
    assert cost.main(report_arguments(report_inputs)) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["raw_usage"][0] == usage()
    assert len(result["raw_usage"]) == 2
    row = result["raw_usage"][1]
    assert row["change"] == usage()["change"]
    assert row["dispatch"]["id"] == request["dispatch_id"]
    assert row["dispatch"]["stage"] == request["stage"]
    assert row["dispatch"]["requested_vendor"] == "claude"
    assert row["dispatch"]["actual_vendor"] is None
    assert row["dispatch"]["launched_at"] == WHEN
    assert row["dispatch"]["completed_at"] is None
    assert row["model"]["requested"] == "requested-only"
    assert row["model"]["reported"] == []
    assert row["model"]["reported_unknown_reason"]
    assert row["raw_source"] == str(path)
    assert row["scope"] == "unknown" and row["tokens"] is None
    assert "may still be running or have been interrupted" in row["tokens_unknown_reason"]
    assert str(path) in row["tokens_unknown_reason"]
    if failure == "read-error":
        assert "injected completion read failure" in row["tokens_unknown_reason"]
    assert result["grouped_by_stage_and_vendor"] == [
        {"stage": "build", "vendor": "codex", "attempts": 1},
        {"stage": "use", "vendor": "unknown", "attempts": 1},
    ]
    assert result["dated_rate_card_equivalent"][0]["value"]["amount"] == "0.14"
    gap_price = result["dated_rate_card_equivalent"][1]
    assert gap_price["dispatch_id"] == request["dispatch_id"]
    assert gap_price["value"]["status"] == "unknown"
    assert gap_price["value"]["reason"] and "amount" not in gap_price["value"]
    assert [row["vendor"] for row in result["bill_plan_status"]] == ["codex"]
    assert result["skipped_records"] == []


@pytest.mark.parametrize("request_bytes", [None, b"", b"{", b"[]", b"null"])
def test_unattributable_completions_are_sorted_skipped_gaps_without_usage(
        report_inputs, request_bytes):
    write_bundle(report_inputs, "target")
    baseline = cost.report(**report_inputs)
    paths = []
    for name in ("z-gap", "a-gap"):
        request_path, run_path, _ = write_bundle(report_inputs, name, completion=b"")
        if request_bytes is None:
            request_path.unlink()
        else:
            request_path.write_bytes(request_bytes)
        paths.append(str(run_path))
    (report_inputs["dispatch_root"] / "empty-folder").mkdir()
    result = cost.report(**report_inputs)
    skipped = result.pop("skipped_records")
    assert result == {key: value for key, value in baseline.items() if key != "skipped_records"}
    assert [row["path"] for row in skipped] == sorted(paths)
    assert all("Completion usage and request attribution are unavailable" in row["reason"]
               for row in skipped)
    assert all("dispatch completion" in row["reason"] and "dispatch request" in row["reason"]
               for row in skipped)


@pytest.mark.parametrize("request_kind", ["readable", "missing", "malformed", "read-error"])
def test_readable_evidence_preserves_attempts_eligibility_order_prices_and_holder(
        report_inputs, monkeypatch, request_kind):
    first = usage(dispatch_id="actual-1")
    unavailable = usage(dispatch_id="actual-1", scope="unknown")
    unavailable["tokens"] = None
    unavailable["tokens_unknown_reason"] = "runtime did not report usage"
    foreign = usage(dispatch_id="foreign")
    foreign["change"]["repository"] = "other/widget"
    request_path, path, _ = write_bundle(report_inputs, "a-multiple", rows=[first, unavailable, foreign])
    value = json.loads(path.read_bytes())
    value["attempts"].extend([None, {"usage": None}, {"usage": {"change": None}}])
    write_json(path, value)
    if request_kind == "missing":
        request_path.unlink()
    elif request_kind == "malformed":
        request_path.write_bytes(b"{")
    elif request_kind == "read-error":
        original = Path.read_bytes

        def unavailable_request(candidate):
            if candidate == request_path:
                raise PermissionError("injected request read failure")
            return original(candidate)

        monkeypatch.setattr(Path, "read_bytes", unavailable_request)
    second = usage(dispatch_id="actual-2", stage="floor")
    write_bundle(report_inputs, "b-second", rows=[second])
    _, old_path, _ = write_bundle(report_inputs, "c-old-schema")
    write_json(old_path, {"schema_version": 1, "attempts": [{"usage": usage()}]})
    holder = cost.holder_close(
        "acme/widget", 12, "codex", None, None, "holder usage unavailable",
        report_inputs["holder_path"], now=datetime.fromisoformat(WHEN),
    )
    result = cost.report(**report_inputs)
    assert result["raw_usage"] == [first, unavailable, second, holder]
    assert result["dated_rate_card_equivalent"] == [
        {"dispatch_id": row["dispatch"]["id"], "value": cost.rate_card_equivalent(row, [rate()])}
        for row in [first, unavailable, second, holder]
    ]
    assert result["dated_rate_card_equivalent"][0]["value"]["amount"] == "0.14"
    assert result["grouped_by_stage_and_vendor"] == [
        {"stage": "build", "vendor": "codex", "attempts": 2},
        {"stage": "floor", "vendor": "codex", "attempts": 1},
        {"stage": "holder-close", "vendor": "codex", "attempts": 1},
    ]
    assert result["bill_plan_status"] == cost.bill_plan_status(
        [first, unavailable, second, holder], report_inputs["terms_path"], report_inputs["gauges_path"],
    )
    assert result["skipped_records"] == []


def test_subprocess_cli_renders_mixed_store_and_leaves_bundle_bytes_unchanged(report_inputs):
    write_bundle(report_inputs, "a-target")
    write_bundle(report_inputs, "b-target-gap", completion=b"")
    request_path, skipped_path, _ = write_bundle(report_inputs, "c-unattributable", completion=b"{")
    request_path.unlink()
    write_bundle(report_inputs, "d-foreign", work="other/widget#12", completion=b"")
    write_bundle(report_inputs, "e-bare", work="12", completion=b"")
    store = report_inputs["dispatch_root"]
    before = {path.relative_to(store): path.read_bytes() for path in store.rglob("*") if path.is_file()}
    completed = report_cli(report_inputs)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    result = json.loads(completed.stdout)
    assert result == cost.report(**report_inputs)
    assert len(result["raw_usage"]) == 2
    assert [row["path"] for row in result["skipped_records"]] == [str(skipped_path)]
    assert {path.relative_to(store): path.read_bytes() for path in store.rglob("*") if path.is_file()} == before


def test_unknown_dispatch_alone_does_not_create_bill_plan_vendor(report_inputs):
    write_bundle(report_inputs, "gap", completion=b"")
    result = cost.report(**report_inputs)
    assert len(result["raw_usage"]) == 1
    assert result["bill_plan_status"] == []
    assert result["dated_rate_card_equivalent"][0]["value"]["status"] == "unknown"


@pytest.mark.parametrize("input_key,diagnostic", [
    ("rates_path", "cannot read rate card"), ("terms_path", "cannot read plan terms"),
    ("holder_path", "cannot read JSON lines"), ("gauges_path", "cannot read JSON lines"),
])
def test_invalid_non_dispatch_inputs_still_fail_cli(report_inputs, input_key, diagnostic):
    write_bundle(report_inputs, "target")
    write_bundle(report_inputs, "gap", completion=b"")
    report_inputs[input_key].write_bytes(b"{")
    completed = report_cli(report_inputs)
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert f"change-cost: {diagnostic}: {report_inputs[input_key]}" in completed.stderr


def test_missing_rate_card_remains_a_cli_failure(report_inputs):
    report_inputs["rates_path"].unlink()
    completed = report_cli(report_inputs)
    assert completed.returncode == 1 and completed.stdout == ""
    assert "change-cost:" in completed.stderr


def test_shipped_rate_card_prices_recorded_claude_classes_and_leaves_unknown_model():
    rates = cost.load_rates(LIB / "rates.json")
    assert {row["model"] for row in rates} == {
        "claude-fable-5-1", "claude-opus-5",
    }
    assert all(row["vendor"] == "claude" for row in rates)
    assert all(set(row["classes"]) == {
        "input", "output", "cache_creation", "cache_read",
    } for row in rates)
    assert all(row["effective_from"] == "2026-09-20T00:00:00Z" for row in rates)
    assert all(row["effective_to"] is None for row in rates)
    assert all(row["currency"] == "USD" and row["per_tokens"] == 1_000_000
               for row in rates)
    assert all(row["source_url"] == "https://claude.com/pricing" for row in rates)
    assert all(row["retrieved_at"] == "2026-09-20T20:04:42Z" for row in rates)
    recorded = usage(
        vendor="claude", model="claude-opus-5", tokens={"models": {
            "claude-opus-5": {
                "input": 1_000_000, "output": 1_000_000,
                "cache_creation": 1_000_000, "cache_read": 1_000_000,
            },
        }},
    )
    recorded["dispatch"]["launched_at"] = "2026-09-20T12:00:00+00:00"
    priced = cost.rate_card_equivalent(recorded, rates)
    assert priced["status"] == "known"
    assert priced["currency"] == "USD"
    assert priced["amount"] == "36.75"

    unrecorded = cost.rate_card_equivalent(usage(
        vendor="claude", model="claude-sonnet-5", tokens={"models": {
            "claude-sonnet-5": {"input": 1},
        }},
    ), rates)
    assert unrecorded["status"] == "unknown"
    assert unrecorded["reason"] == "no dated rate matches claude claude-sonnet-5"
    assert not any(row["vendor"] == "codex" for row in rates)


def test_schema_v2_usage_has_context_classes_source_and_no_money():
    payload = {
        "type": "result", "total_cost_usd": 9.25,
        "modelUsage": {"claude-fixture": {
            "inputTokens": 8, "cacheReadInputTokens": 5,
            "cacheCreationInputTokens": 2, "outputTokens": 3,
            "thinkingTokens": 1, "costUSD": 9.25,
        }},
    }
    observed = records.runtime_evidence("claude", json.dumps(payload).encode(), "fresh")
    request = records.request_record(
        dispatch_id="dispatch", work="acme/widget#12", stage="use",
        settings_source="fixture", settings_scope="use", vendor="claude",
        model="requested-alias", effort="xhigh", continuity="fresh",
        permission_boundary="native", root=None,
        now=datetime.fromisoformat(WHEN),
    )
    request["runtime_version"] = "claude 2.1.261"
    row = records.usage_record(
        {"vendor": "claude", "observed": observed, "source_return": "raw.json"},
        request, completed_at=WHEN, staffing_status="qualified",
    )
    assert row["change"] == {"repository": "acme/widget", "issue": 12,
                              "unknown_reason": None}
    assert row["dispatch"]["stage"] == "use"
    assert row["model"] == {
        "requested": "requested-alias", "reported": ["claude-fixture"],
        "reported_unknown_reason": None,
    }
    assert row["tokens"] == {"models": {"claude-fixture": {
        "input": 8, "cache_read": 5, "cache_creation": 2, "output": 3,
    }}}
    assert row["additional_native_classes"] == {"claude-fixture": {"thinkingTokens": 1}}
    assert row["source_field"] == "modelUsage"
    assert row["runtime_version"] == "claude 2.1.261"
    serialized = json.dumps(row).lower()
    assert all(word not in serialized for word in ("cost", "currency", "usd", "price"))


def test_native_tool_usage_records_unknown_with_reason_not_requested_model():
    observed = records.runtime_evidence("native-tool", b"opaque", "fresh")
    request = records.request_record(
        dispatch_id="native", work="acme/widget#12", stage="use",
        settings_source="fixture", settings_scope="use", vendor="native-tool",
        model="requested-only", effort="ordinary", continuity="fresh",
        permission_boundary="native", root=None,
    )
    row = records.usage_record(
        {"vendor": "native-tool", "observed": observed}, request,
        completed_at=WHEN, staffing_status="qualified",
    )
    assert row["model"]["reported"] == []
    assert row["model"]["reported_unknown_reason"] == "no extractor for this tool"
    assert row["tokens"] is None
    assert row["tokens_unknown_reason"] == "no extractor for this tool"


def test_dated_rate_card_computes_only_when_every_class_and_model_match():
    value = cost.rate_card_equivalent(usage(), [rate()])
    assert value == {
        "status": "known", "currency": "USD", "amount": "0.14",
        "rate_sources": [{"model": "gpt-fixture",
                          "source_url": "https://example.test/rates",
                          "retrieved_at": WHEN}],
    }
    missing_model = cost.rate_card_equivalent(usage(model="unknown-model"), [rate()])
    assert missing_model["status"] == "unknown"
    assert "no dated rate" in missing_model["reason"]
    assert "amount" not in missing_model


def test_missing_token_rate_and_unknown_scope_never_render_zero():
    missing = rate()
    missing["classes"]["reasoning_output"] = None
    no_rate = cost.rate_card_equivalent(usage(), [missing])
    no_scope = cost.rate_card_equivalent(usage(scope="unknown"), [rate()])
    assert no_rate["status"] == no_scope["status"] == "unknown"
    assert "0" not in {no_rate.get("amount"), no_scope.get("amount")}


def test_report_labels_three_quantities_groups_rows_and_keeps_unknowns(tmp_path):
    dispatch_root = tmp_path / "dispatches"
    run_path = dispatch_root / "one" / "result.md.run.json"
    write_json(run_path, {"schema_version": 2, "attempts": [{"usage": usage()}]})
    holder_path = tmp_path / "holder.jsonl"
    holder = cost.holder_close(
        "acme/widget", 12, "codex", None, None,
        "holder host exposed no class breakdown", holder_path,
        now=datetime.fromisoformat(WHEN),
    )
    rates_path = tmp_path / "rates.json"
    write_json(rates_path, {"schema_version": 1, "rates": []})
    terms_path = tmp_path / "missing-plan-terms.json"
    gauges_path = tmp_path / "missing-gauges.jsonl"
    result = cost.report(
        "acme/widget", 12, dispatch_root, rates_path, terms_path, gauges_path, holder_path
    )
    assert result["marker"] == "change-cost:v1"
    assert set(result) >= {
        "raw_usage", "dated_rate_card_equivalent", "bill_plan_status",
    }
    assert len(result["raw_usage"]) == 2
    assert holder in result["raw_usage"]
    assert result["grouped_by_stage_and_vendor"] == [
        {"stage": "build", "vendor": "codex", "attempts": 1},
        {"stage": "holder-close", "vendor": "codex", "attempts": 1},
    ]
    assert all(row["value"]["status"] == "unknown"
               for row in result["dated_rate_card_equivalent"])
    plan = result["bill_plan_status"][0]
    assert plan["plan_terms"]["status"] == "unknown"
    assert plan["gauge"]["status"] == "unknown"
    assert plan["change_allocation"]["status"] == "unknown"


def test_plan_terms_and_latest_gauge_remain_separate_from_rate_price(tmp_path):
    terms = tmp_path / "plan-terms.json"
    write_json(terms, {"schema_version": 1, "terms": [{
        "vendor": "codex", "effective_from": "2026-01-01T00:00:00+00:00",
        "effective_to": None, "billing_basis": "subscription",
        "recurring_charge": {"currency": "USD", "amount": "20"},
        "source": "owner plan page",
    }]})
    gauges = tmp_path / "gauges.jsonl"
    first = {"vendor": "codex", "captured_at": "2026-09-18T00:00:00+00:00",
             "displayed_value": {"used_percent": 20}}
    latest = {"vendor": "codex", "captured_at": WHEN,
              "displayed_value": {"used_percent": 30}}
    gauges.write_bytes((json.dumps(first) + "\n" + json.dumps(latest) + "\n").encode())
    value = cost.bill_plan_status([usage()], terms, gauges)[0]
    assert value["plan_terms"]["billing_basis"] == "subscription"
    assert value["gauge"] == latest
    assert value["change_allocation"]["status"] == "unknown"


def test_holder_close_rejects_money_and_always_appends_unknown_row(tmp_path):
    destination = tmp_path / "holder.jsonl"
    row = cost.holder_close(
        "acme/widget", 12, "codex", None, None, "host supplied no tokens",
        destination, now=datetime.fromisoformat(WHEN),
    )
    assert row["tokens"] is None
    assert row["tokens_unknown_reason"] == "host supplied no tokens"
    assert cost._read_jsonl(destination) == [row]
    monetary = tmp_path / "money.json"
    write_json(monetary, {"tokens": {"input": 1}, "cost_usd": 1})
    with pytest.raises(cost.CostError, match="cannot contain money"):
        cost.holder_close(
            "acme/widget", 12, "codex", None, monetary, None, destination,
            now=datetime.fromisoformat(WHEN),
        )


def test_codex_gauge_preserves_displayed_window_without_token_or_invoice_conversion():
    row = cost.gauge_from_codex_response({"rateLimits": {"primary": {
        "usedPercent": 71, "windowDurationMins": 10080, "resetsAt": 1789990842,
    }}}, datetime.fromisoformat(WHEN))
    assert row["displayed_window"] == {
        "duration_minutes": 10080, "resets_at": 1789990842,
    }
    assert row["displayed_value"] == {"used_percent": 71}
    assert row["unknowns"]["token_conversion"]
    assert row["unknowns"]["invoice_conversion"]


def test_capture_gauge_uses_app_server_and_claude_usage_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(cost, "codex_rate_limits", lambda _executable: {
        "rateLimits": {"primary": {"usedPercent": 7}}
    })
    codex_path = tmp_path / "codex.jsonl"
    codex = cost.capture_gauge(
        "codex", codex_path, None, datetime.fromisoformat(WHEN), "codex-fixture"
    )
    assert codex["source"] == "codex app-server account/rateLimits/read"
    claude_path = tmp_path / "claude.jsonl"
    claude = cost.capture_gauge(
        "claude", claude_path, None, datetime.fromisoformat(WHEN)
    )
    assert claude["source"] == "interactive /usage capture absent"
    assert "no plan window" in claude["unknowns"]["gauge"]


def test_parser_exposes_measurement_without_budget_or_halt_controls():
    options = {option for action in cost.parser()._actions for option in action.option_strings}
    assert all("budget" not in option and "halt" not in option for option in options)

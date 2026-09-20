from datetime import datetime, timezone
import json
from pathlib import Path
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

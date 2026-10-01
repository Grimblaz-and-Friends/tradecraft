from datetime import datetime, timedelta, timezone
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import shutil
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
    requested = (rows[0] if rows else usage()) if completion is None else None
    request = records.request_record(
        dispatch_id=name, work=work, stage="use", settings_source="fixture",
        settings_scope="use", vendor=requested["dispatch"]["actual_vendor"] if requested else "claude",
        model=requested["model"]["requested"] if requested else "requested-only", effort="xhigh",
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
    assert result["dated_rate_card_equivalent"][0]["value"]["amount"] == "0.11"
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
    skipped = result["skipped_records"]
    for key in ("raw_usage", "dated_rate_card_equivalent", "dispatch_totals", "bill_plan_status"):
        assert result[key] == baseline[key]
    assert result["total"]["unknown_dispatches"] == 0
    assert result["total"]["skipped_record_count"] == 2
    assert result["total"]["floor"]
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
    old_unknown = result["raw_usage"][3]
    expected = [first, unavailable, second, old_unknown, holder]
    assert old_unknown["dispatch"]["id"] == "c-old-schema"
    assert result["raw_usage"] == expected
    for row, price in zip(expected, result["dated_rate_card_equivalent"]):
        control = cost.rate_card_equivalent(row, [rate()])
        assert price["value"]["status"] == control["status"]
        if control["status"] == "known":
            assert price["value"]["amount"] == control["amount"]
        else:
            assert set(price["value"]["reasons"]) == set(control["reasons"])
    assert result["dated_rate_card_equivalent"][0]["value"]["amount"] == "0.11"
    assert result["grouped_by_stage_and_vendor"] == [
        {"stage": "build", "vendor": "codex", "attempts": 2},
        {"stage": "floor", "vendor": "codex", "attempts": 1},
        {"stage": "holder-close", "vendor": "codex", "attempts": 1},
        {"stage": "use", "vendor": "unknown", "attempts": 1},
    ]
    assert result["bill_plan_status"] == cost.bill_plan_status(
        expected, report_inputs["terms_path"], report_inputs["gauges_path"],
    )
    assert result["skipped_records"] == [{"path": str(old_path), "reason": "unsupported dispatch completion schema"}]


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
        "claude-fable-5-1", "claude-opus-5", "claude-opus-5-5",
        "gpt-6-astra", "gpt-6-sol", "gpt-6-luna", "gpt-5.6-sol", "gpt-6.1-sol",
    }
    assert all(row["currency"] == "USD" and row["per_tokens"] == 1_000_000 for row in rates)
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
    assert priced["amount"] == "40.5"

    unrecorded = cost.rate_card_equivalent(usage(
        vendor="claude", model="claude-sonnet-5", tokens={"models": {
            "claude-sonnet-5": {"input": 1},
        }},
    ), rates)
    assert unrecorded["status"] == "unknown"
    assert "no dated rate matches claude claude-sonnet-5" in unrecorded["reasons"]


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
    assert {key: value[key] for key in ("status", "currency", "amount", "rate_sources")} == {
        "status": "known", "currency": "USD", "amount": "0.11",
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
    missing["classes"]["output"] = None
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


FIXTURES = Path(__file__).with_name("fixtures") / "change_cost"


def fixture_inputs(tmp_path, group="440", issue=440):
    root = tmp_path / "bundles"
    shutil.copytree(FIXTURES / group, root)
    return {
        "repo": "Grimblaz-and-Friends/Organizations-of-Verra" if group == "440" else "Grimblaz-and-Friends/tradecraft",
        "issue": issue, "dispatch_root": root, "rates_path": LIB / "rates.json",
        "terms_path": tmp_path / "no-terms.json", "gauges_path": tmp_path / "no-gauges.jsonl",
        "holder_path": FIXTURES / "empty-holder.jsonl",
    }


def fixture_paths(inputs, suffix):
    folder = next(path for path in inputs["dispatch_root"].iterdir() if path.name.endswith(suffix))
    return folder / "result.md.request.json", folder / "result.md.run.json"


def fixture_prices(inputs):
    result = cost.report(**inputs)
    return result, {row["dispatch_id"]: row["value"] for row in result["dated_rate_card_equivalent"]}


def test_recorded_codex_prices_session_shares_and_read_only_reporting(tmp_path):
    inputs = fixture_inputs(tmp_path)
    root = inputs["dispatch_root"]
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    result, prices = fixture_prices(inputs)
    assert format(Decimal(prices["d8847832be3344cca8de67bcd07d90cd"]["amount"]), ".2f") == "3.83"
    assert format(Decimal(prices["92aa0a262e6e4876b783d8f86be4e3c2"]["amount"]), ".2f") == "15.48"
    repair = prices["8c1ce0c713ab49abb277b46f5fd4732a"]
    assert format(Decimal(repair["amount"]), ".2f") == "11.70"
    assert repair["predecessor_dispatch_id"] == "b72f2db86198461d8bd22f58bbdc386b"
    assert repair["dispatch_token_share"]["input"] == str(52407925 - 31055506)
    total = sum((Decimal(value["amount"]) for key, value in prices.items()
                 if key != "d8847832be3344cca8de67bcd07d90cd"), Decimal(0))
    assert format(total, ".2f") == "30.45"
    assert all(value["floor"] and value["model_basis"] == "requested model" for value in prices.values())
    assert all(row["model"]["reported"] == [] for row in result["raw_usage"])
    assert {path: path.read_bytes() for path in before} == before
    # Discovery order and an unrelated session cannot select a different predecessor.
    for number, folder in enumerate(list(root.iterdir())):
        folder.rename(root / f"shuffled-{10 - number}")
    assert fixture_prices(inputs)[1] == prices


def test_requested_model_and_final_native_snapshot_control_codex_price(tmp_path):
    inputs = fixture_inputs(tmp_path)
    request_path, completion_path = fixture_paths(inputs, "440-artifact-dfd2848aaf6d")
    request = json.loads(request_path.read_bytes())
    request["requested"]["model"] = "gpt-6-luna"
    write_json(request_path, request)
    completion = json.loads(completion_path.read_bytes())
    observed = completion["attempts"][0]["observed"]
    observed["raw"].insert(0, deepcopy(observed["raw"][-1]))
    write_json(completion_path, completion)
    value = fixture_prices(inputs)[1][request["dispatch_id"]]
    assert value["rate_sources"][0]["model"] == "gpt-6-luna"
    assert Decimal(value["amount"]) == Decimal("0.03830632")


@pytest.mark.parametrize("fault,expected", [
    ("missing", "missing or excluded"), ("broken", "unreadable or inconsistent baseline"),
    ("identity", "identities disagree"), ("decreased", "counters decreased"),
    ("overlap", "overlaps or is ambiguous"), ("counter", "unavailable"),
    ("timestamp", "chronology is ambiguous"),
    ("reasoning-share", "reasoning exceeds output in the dispatch share"),
])
def test_resume_baseline_failures_never_bridge_older_evidence(tmp_path, fault, expected):
    inputs = fixture_inputs(tmp_path)
    initial_request, initial_run = fixture_paths(inputs, "440-build-7676f416bd3c")
    prior_request, prior_run = fixture_paths(inputs, "440-floor-32e0b689ce84")
    current_request, current_run = fixture_paths(inputs, "440-build-20d60c90286c")
    if fault == "missing":
        shutil.rmtree(initial_run.parent)
        value = fixture_prices(inputs)[1]["b72f2db86198461d8bd22f58bbdc386b"]
    else:
        request = json.loads(current_request.read_bytes())
        completion = json.loads(current_run.read_bytes())
        if fault == "broken":
            prior_run.write_bytes(b"{")
        elif fault == "identity":
            request["requested"]["session_id"] = "wrong-session"
            write_json(current_request, request)
        elif fault == "decreased":
            completion["attempts"][0]["observed"]["raw"][-1]["input_tokens"] = 0
            write_json(current_run, completion)
        elif fault == "counter":
            del completion["attempts"][0]["observed"]["raw"][-1]["output_tokens"]
            write_json(current_run, completion)
        elif fault == "reasoning-share":
            completion["attempts"][0]["observed"]["raw"][-1]["reasoning_output_tokens"] = 120000
            write_json(current_run, completion)
        elif fault == "overlap":
            prior = json.loads(prior_run.read_bytes())
            prior["attempts"][0]["usage"]["dispatch"]["completed_at"] = "2026-09-28T14:00:00Z"
            write_json(prior_run, prior)
        elif fault == "timestamp":
            prior = json.loads(prior_run.read_bytes())
            prior["attempts"][0]["usage"]["dispatch"]["launched_at"] = None
            write_json(prior_run, prior)
        value = fixture_prices(inputs)[1]["8c1ce0c713ab49abb277b46f5fd4732a"]
    assert value["status"] == "unknown" and "amount" not in value
    assert expected in value["reason"]


def test_resume_subtracts_tokens_then_prices_at_current_requested_model(tmp_path):
    inputs = fixture_inputs(tmp_path)
    request_path, _ = fixture_paths(inputs, "440-build-20d60c90286c")
    request = json.loads(request_path.read_bytes())
    request["requested"]["model"] = "gpt-6-sol"
    write_json(request_path, request)
    value = fixture_prices(inputs)[1][request["dispatch_id"]]
    assert Decimal(value["amount"]) == Decimal("11.6978408") / 2


def test_readable_snapshot_can_anchor_later_share_when_its_own_share_is_unknown(tmp_path):
    inputs = fixture_inputs(tmp_path)
    _, path = fixture_paths(inputs, "440-floor-32e0b689ce84")
    path.write_bytes(b"{")
    _, prices = fixture_prices(inputs)
    assert prices["8c1ce0c713ab49abb277b46f5fd4732a"]["status"] == "unknown"
    later = prices["a718baf184b54171a7a8e5c4574414e0"]
    assert later["predecessor_dispatch_id"] == "8c1ce0c713ab49abb277b46f5fd4732a"
    assert Decimal(later["amount"]) == Decimal("0.7690472")


@pytest.mark.parametrize("issue,identity,amount", [
    (684, "4b12826f7c38498d8a036d6dc2fe27de", "2.4033375"),
    (694, "702b03109d96417094577082eef34d26", "3.2170122"),
])
def test_real_claude_prices_thinking_limits_and_card_fallback(tmp_path, issue, identity, amount):
    inputs = fixture_inputs(tmp_path, "claude", issue)
    result, prices = fixture_prices(inputs)
    value = prices[identity]
    assert value["card_amount"] == amount
    assert abs(Decimal(value["runtime_amount"]) - Decimal(amount)) < Decimal("0.000000000001")
    assert value["source"] == "runtime-list-price" and value["flags"] == []
    assert result["raw_usage"][0]["additional_native_classes"]
    completion_path = next(path for path in inputs["dispatch_root"].rglob("*.run.json")
                           if json.loads(path.read_bytes())["dispatch_id"] == identity)
    completion = json.loads(completion_path.read_bytes())
    assert completion["attempts"][0]["observed"]["reported_effort"] is None
    for population in completion["attempts"][0]["observed"]["raw"].values():
        population.pop("costUSD")
    write_json(completion_path, completion)
    fallback = fixture_prices(inputs)[1][identity]
    assert fallback["amount"] == amount and fallback["source"] == "rate-card"


@pytest.mark.parametrize("difference,source", [
    ("0.009", "runtime-list-price"), ("0.01", "runtime-list-price"),
    ("0.010001", "rate-card"), ("-0.010001", "rate-card"),
])
def test_claude_mismatch_threshold_and_total_selection(tmp_path, difference, source):
    inputs = fixture_inputs(tmp_path, "claude", 694)
    _, path = fixture_paths(inputs, "694-use-5add0519e1f6")
    completion = json.loads(path.read_bytes())
    runtime = Decimal("3.2170122") + Decimal(difference)
    completion["attempts"][0]["observed"]["raw"]["claude-opus-5-5"]["costUSD"] = str(runtime)
    write_json(path, completion)
    result, prices = fixture_prices(inputs)
    value = next(iter(prices.values()))
    assert value["source"] == source
    assert Decimal(value["runtime_amount"]) == runtime
    assert value["card_amount"] == "3.2170122"
    assert bool(value["flags"]) == (source == "rate-card")
    if value["flags"]:
        assert "claude-opus-5-5" in value["flags"][0]
    assert result["total"]["known_amount"] == value["amount"]


def test_claude_resume_remains_unknown_even_with_runtime_money(tmp_path):
    inputs = fixture_inputs(tmp_path, "claude", 694)
    _, path = fixture_paths(inputs, "694-use-5add0519e1f6")
    completion = json.loads(path.read_bytes())
    completion["attempts"][0]["usage"]["dispatch"]["continuity"] = "resume"
    write_json(path, completion)
    value = next(iter(fixture_prices(inputs)[1].values()))
    assert value["status"] == "unknown" and "resumed Claude" in value["reason"]


def synthetic_rate():
    value = rate()
    value["per_tokens"] = 1_000_000
    value["classes"] = {"input": 1, "cached_input": .1, "cache_write_input": 2, "output": 10}
    return value


@pytest.mark.parametrize("reasoning", [0, 3000, 5000])
def test_amended_synthetic_tokens_are_counted_once(reasoning):
    row = usage(tokens={"input": 100000, "cached_input": 80000, "output": 5000,
                        "reasoning_output": reasoning})
    value = cost.rate_card_equivalent(row, [synthetic_rate()])
    assert value["amount"] == "0.078"
    row["additional_native_classes"] = {"cache_write_input_tokens": 10000}
    assert cost.rate_card_equivalent(row, [synthetic_rate()])["amount"] == "0.088"


def test_zero_extras_allow_pricing_and_independent_unknowns_are_accumulated():
    row = usage()
    row["additional_native_classes"] = {"unfamiliar_tokens": 0, "cache_write_input_tokens": 0}
    assert cost.rate_card_equivalent(row, [rate()])["status"] == "known"
    row["additional_native_classes"]["unfamiliar_tokens"] = 10
    row["dispatch"]["launched_at"] = None
    row["model"]["requested"] = "unlisted-local-model"
    value = cost.rate_card_equivalent(row, [rate()])
    assert value["status"] == "unknown"
    assert "timestamp" in value["reason"] and "unlisted-local-model" in value["reason"]
    assert "unfamiliar_tokens" in value["reason"]
    assert len(value["reasons"]) >= 3


@pytest.mark.parametrize("name,count", [("input", -1), ("output", float("inf")),
                                         ("cached_input", True), ("cached_input", 101),
                                         ("reasoning_output", 11)])
def test_invalid_counts_and_overlaps_stay_unknown(name, count):
    row = usage()
    row["tokens"][name] = count
    value = cost.rate_card_equivalent(row, [rate()])
    assert value["status"] == "unknown" and "amount" not in value


def test_missing_counter_is_not_reported_zero():
    row = usage()
    del row["tokens"]["cached_input"]
    assert "cached_input" in cost.rate_card_equivalent(row, [rate()])["reason"]


def test_792_total_counts_the_unfinished_record_and_copies_once(tmp_path):
    inputs = fixture_inputs(tmp_path, "792", 792)
    result, prices = fixture_prices(inputs)
    assert abs(Decimal(result["total"]["known_amount"]) - Decimal("16.13")) <= Decimal("0.01")
    assert result["total"]["unknown_dispatches"] == 1
    assert result["total"]["priced_dispatches"] == 15 and result["total"]["floor"]
    assert prices["26767f600fe549669a2363c43ede55f5"]["status"] == "unknown"
    shutil.copytree(inputs["dispatch_root"], inputs["dispatch_root"] / "copy")
    assert cost.report(**inputs) == result


def test_fallback_attempts_partial_subtotals_and_conflicting_copies(report_inputs):
    first = usage(dispatch_id="a-fallback")
    second = usage(dispatch_id="a-fallback", model="other-model")
    second_rate = rate("other-model")
    second_rate["classes"]["input"] = 2
    write_json(report_inputs["rates_path"], {"schema_version": 1, "rates": [rate(), second_rate]})
    _, path, _ = write_bundle(report_inputs, "a-fallback", rows=[first, second])
    completion = json.loads(path.read_bytes())
    for model, attempt in zip(("gpt-fixture", "other-model"), completion["attempts"]):
        attempt["model"] = model
    write_json(path, completion)
    result = cost.report(**report_inputs)
    assert result["total"]["known_amount"] == "0.30" and result["total"]["priced_dispatches"] == 1
    assert len(result["dated_rate_card_equivalent"]) == 2
    copy = path.parent.parent / "b-copy"
    shutil.copytree(path.parent, copy)
    assert cost.report(**report_inputs) == result
    completion["attempts"][1]["usage"]["tokens"] = None
    completion["attempts"][1]["usage"]["tokens_unknown_reason"] = "interrupted fallback"
    write_json(path, completion)
    conflict = cost.report(**report_inputs)
    assert conflict["total"]["unknown_dispatches"] == 1
    assert "conflicting" in conflict["dated_rate_card_equivalent"][0]["value"]["reason"]
    shutil.rmtree(copy)
    partial = cost.report(**report_inputs)
    assert partial["total"]["known_amount"] == "0.11" and partial["total"]["unknown_dispatches"] == 1
    assert partial["dispatch_totals"][0]["status"] == "unknown"


def test_complete_copy_can_supply_an_empty_reservation(report_inputs):
    _, path, _ = write_bundle(report_inputs, "same")
    copy = path.parent.parent / "z-copy"
    shutil.copytree(path.parent, copy)
    path.write_bytes(b"")
    result = cost.report(**report_inputs)
    assert result["total"]["priced_dispatches"] == 1
    assert result["total"]["known_amount"] == "0.11"


@pytest.mark.parametrize("completion", [b'{"schema_version": 99}', b'{"schema_version": 2, "attempts": {}}',
                                          b'{"schema_version": 2, "attempts": [null]}'])
def test_unfamiliar_and_malformed_records_are_visible(report_inputs, completion):
    _, target, _ = write_bundle(report_inputs, "target", completion=completion)
    request, anonymous, _ = write_bundle(report_inputs, "anonymous", completion=completion)
    request.unlink()
    result = cost.report(**report_inputs)
    assert {row["path"] for row in result["skipped_records"]} == {str(target), str(anonymous)}
    assert result["total"]["unknown_dispatches"] == 1 and result["total"]["floor"]


def _assert_default_rate_coverage(rates):
    import dispatch_implementer
    import dispatch_seat
    import connected_review
    defaults = [(role, vendor, profile[0]) for role, vendors in dispatch_implementer.PROFILES.items()
                for vendor, profile in vendors.items()]
    defaults.extend(("seat (primary and fallback)", vendor, model)
                    for vendor, model in dispatch_seat.DEFAULT_MODELS.items())
    defaults.append(("connected reviewer", "claude", connected_review.DEFAULT_MODEL))
    missing = [f"{role}: {vendor} {model}" for role, vendor, model in defaults
               if not any(row["vendor"] == vendor and row["model"] == model for row in rates)]
    assert not missing, "shipped defaults have no price row: " + "; ".join(missing)


def test_shipped_default_price_coverage_ignores_expiry():
    rates = cost.load_rates(LIB / "rates.json")
    _assert_default_rate_coverage(rates)
    for row in rates:
        row["effective_to"] = "2000-01-01T00:00:00Z"
    _assert_default_rate_coverage(rates)


def test_card_transcription_matches_the_retained_price_observations():
    expected = {
        "gpt-6-astra": (10, 1, 12.5, 50), "gpt-6-sol": (2, .2, 2.5, 10),
        "gpt-6-luna": (.1, .01, .125, .5), "gpt-5.6-sol": (4, .4, 5, 20),
        "gpt-6.1-sol": (2, .1, 2.5, 10), "claude-fable-5-1": (10, .25, 20, 50),
        "claude-opus-5": (5, .5, 10, 25), "claude-opus-5-5": (4, .2, 8, 20),
    }
    for row in cost.load_rates(LIB / "rates.json"):
        classes = ("input", "cached_input", "cache_write_input", "output") if row["vendor"] == "codex" else (
            "input", "cache_read", "cache_creation", "output")
        assert tuple(row["classes"][name] for name in classes) == expected[row["model"]]
        assert "backfilled" in row["applicability_basis"]
        if row["vendor"] == "codex":
            assert row["retrieved_at"] == ("2026-09-29" if row["model"] == "gpt-6.1-sol" else "2026-09-28")
            assert "issuecomment-" in row["retrieval_record"]
        else:
            assert row["retrieved_at"].startswith("2026-10-01")


@pytest.mark.parametrize("role,vendor", [
    (role, vendor) for role in ("artifact_author", "implementer", "seat") for vendor in ("codex", "claude")
] + [("connected reviewer", "claude")])
def test_default_coverage_names_each_missing_role_and_model(monkeypatch, role, vendor):
    import dispatch_implementer
    import dispatch_seat
    import connected_review
    if role in dispatch_implementer.PROFILES:
        monkeypatch.setitem(dispatch_implementer.PROFILES[role], vendor, ("missing-model", "xhigh"))
    elif role == "seat":
        monkeypatch.setitem(dispatch_seat.DEFAULT_MODELS, vendor, "missing-model")
    else:
        monkeypatch.setattr(connected_review, "DEFAULT_MODEL", "missing-model")
    with pytest.raises(AssertionError, match=role + ".*missing-model"):
        _assert_default_rate_coverage(cost.load_rates(LIB / "rates.json"))


def test_multi_model_claude_sums_runtime_once_and_flags_a_total_mismatch(report_inputs):
    populations = {model: {"input": 1000, "cache_read": 0, "cache_creation": 0, "output": 0}
                   for model in ("claude-first", "claude-second")}
    row = usage(vendor="claude", model="claude-first", tokens={"models": populations}, dispatch_id="multi")
    _, path, _ = write_bundle(report_inputs, "multi", rows=[row])
    completion = json.loads(path.read_bytes())
    attempt = completion["attempts"][0]
    attempt["native_cost"] = 100
    attempt["observed"] = {"source": "modelUsage", "raw": {
        model: {"costUSD": "0.007", "costBasis": "list"} for model in populations}}
    write_json(path, completion)
    rates = []
    for model in populations:
        entry = rate(model)
        entry.update(vendor="claude", per_tokens=1_000_000)
        entry["classes"] = {"input": 1, "cache_read": .1, "cache_creation": 2, "output": 10}
        rates.append(entry)
    write_json(report_inputs["rates_path"], {"schema_version": 1, "rates": rates})
    result = cost.report(**report_inputs)
    value = result["dated_rate_card_equivalent"][0]["value"]
    assert value["runtime_amount"] == "0.014" and value["card_amount"] == "0.002"
    assert value["source"] == "rate-card" and len(value["flags"]) == 2
    assert result["total"]["known_amount"] == "0.002"
    for model in populations:
        attempt["observed"]["raw"][model]["costUSD"] = "0.001"
    write_json(path, completion)
    value = cost.report(**report_inputs)["dated_rate_card_equivalent"][0]["value"]
    assert value["source"] == "runtime-list-price" and value["amount"] == "0.002"


def test_native_claude_invalid_and_unfamiliar_counts_are_not_lost_in_normalization(tmp_path):
    inputs = fixture_inputs(tmp_path, "claude", 694)
    _, path = fixture_paths(inputs, "694-use-5add0519e1f6")
    completion = json.loads(path.read_bytes())
    native = completion["attempts"][0]["observed"]["raw"]["claude-opus-5-5"]
    native["inputTokens"] = -1
    native["unfamiliarTokens"] = 20
    write_json(path, completion)
    value = next(iter(fixture_prices(inputs)[1].values()))
    assert value["status"] == "unknown"
    assert "input" in value["reason"] and "nonnegative" in value["reason"]
    assert "unfamiliarTokens" in value["reason"]


def test_foreign_request_cannot_supply_a_session_baseline(tmp_path, monkeypatch):
    inputs = fixture_inputs(tmp_path)
    request_path, completion_path = fixture_paths(inputs, "440-build-7676f416bd3c")
    request = json.loads(request_path.read_bytes())
    request["work"] = "other/repo#1"
    write_json(request_path, request)
    read_bytes = Path.read_bytes

    def isolated(path):
        assert path != completion_path, "foreign predecessor completion was opened"
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", isolated)
    value = fixture_prices(inputs)[1]["b72f2db86198461d8bd22f58bbdc386b"]
    assert value["status"] == "unknown" and "missing or excluded" in value["reason"]


@pytest.mark.parametrize("launched,known", [
    ("2026-11-21T23:59:59Z", True), ("2026-11-22T00:00:00Z", False),
    ("2026-11-22T01:00:00+01:00", False), ("2026-11-21T18:59:59-05:00", True),
    ("2026-11-23T00:00:00Z", False),
])
def test_promotional_price_uses_launch_date_and_replacement(launched, known):
    rates = cost.load_rates(LIB / "rates.json")
    row = usage(model="gpt-5.6-sol")
    row["dispatch"]["launched_at"] = launched
    value = cost.rate_card_equivalent(row, rates)
    assert (value["status"] == "known") == known
    if not known:
        assert "gpt-5.6-sol" in value["reason"] and "re-read the posted page" in value["reason"]
        replacement = deepcopy(next(rate for rate in rates if rate["model"] == "gpt-5.6-sol"))
        replacement.update(effective_from="2026-11-22T00:00:00Z", effective_to=None)
        assert cost.rate_card_equivalent(row, [*rates, replacement])["status"] == "known"


def test_close_commands_default_holder_inclusion_override_and_exact_repo(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cost.Path, "home", classmethod(lambda cls: tmp_path))
    tokens = tmp_path / "tokens.json"
    write_json(tokens, {"tokens": {"input": 100, "cached_input": 20, "output": 10}, "scope": "invocation"})
    assert cost.main(["holder-close", "--repo", "acme/widget", "--issue", "12", "--vendor", "codex",
                      "--model", "gpt-6.1-sol", "--tokens-file", str(tokens)]) == 0
    holder = json.loads(capsys.readouterr().out)
    assert holder["dispatch"]["launched_at"] == holder["dispatch"]["completed_at"]
    assert not any(key in holder for key in ("amount", "currency", "cost"))
    assert cost.main(["report", "--repo", "acme/widget", "--issue", "12"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["raw_usage"] == [holder]
    assert result["total"]["priced_dispatches"] == 1
    assert result["dated_rate_card_equivalent"][0]["value"]["timestamp_basis"] == "close capture time"
    assert cost.main(["report", "--repo", "ACME/widget", "--issue", "12"]) == 0
    assert json.loads(capsys.readouterr().out)["raw_usage"] == []
    unknown_path = tmp_path / "alternate.jsonl"
    assert cost.main(["holder-close", "--repo", "acme/widget", "--issue", "12", "--vendor", "claude",
                      "--unknown-reason", "host has no usage", "--output", str(unknown_path)]) == 0
    unknown_holder = json.loads(capsys.readouterr().out)
    assert cost.main(["report", "--repo", "acme/widget", "--issue", "12",
                      "--holder-usage", str(unknown_path)]) == 0
    alternative = json.loads(capsys.readouterr().out)
    assert alternative["raw_usage"] == [unknown_holder] and alternative["total"]["unknown_dispatches"] == 1


def test_native_codex_omitted_cache_writes_price_fresh_and_resumed_shares(tmp_path):
    inputs = fixture_inputs(tmp_path)
    expected, _ = fixture_prices(inputs)
    for path in inputs["dispatch_root"].rglob("*.run.json"):
        completion = json.loads(path.read_bytes())
        for attempt in completion["attempts"]:
            for snapshot in attempt["observed"]["raw"]:
                snapshot.pop("cache_write_input_tokens", None)
            attempt["usage"]["additional_native_classes"].pop("cache_write_input_tokens", None)
        write_json(path, completion)
    result, prices = fixture_prices(inputs)
    assert all(value["status"] == "known" for value in prices.values())
    assert result["total"] == expected["total"]
    assert prices["8c1ce0c713ab49abb277b46f5fd4732a"]["dispatch_token_share"]["cache_write_input"] == "0"


@pytest.mark.parametrize("counter", ["input_tokens", "cached_input_tokens", "output_tokens"])
def test_native_codex_required_counters_remain_required(tmp_path, counter):
    inputs = fixture_inputs(tmp_path)
    _, path = fixture_paths(inputs, "440-artifact-dfd2848aaf6d")
    completion = json.loads(path.read_bytes())
    del completion["attempts"][0]["observed"]["raw"][-1][counter]
    write_json(path, completion)
    value = fixture_prices(inputs)[1]["d8847832be3344cca8de67bcd07d90cd"]
    assert value["status"] == "unknown" and "unavailable" in value["reason"]


@pytest.mark.parametrize("foreign_work", ["issue-677", "other/repo#677"])
@pytest.mark.parametrize("continuity", ["fresh", "resume"])
@pytest.mark.parametrize("placement", ["between", "after", "other-session", "same-time"])
def test_foreign_request_never_bridges_an_older_same_change_snapshot(
        tmp_path, monkeypatch, foreign_work, continuity, placement):
    inputs = fixture_inputs(tmp_path)
    inputs.update(repo="Grimblaz-and-Friends/tradecraft", issue=677)
    for path in inputs["dispatch_root"].rglob("*.request.json"):
        request = json.loads(path.read_bytes())
        request["work"] = "Grimblaz-and-Friends/tradecraft#677"
        write_json(path, request)
    for path in inputs["dispatch_root"].rglob("*.run.json"):
        completion = json.loads(path.read_bytes())
        for attempt in completion["attempts"]:
            attempt["usage"]["change"].update(repository=inputs["repo"], issue=677)
        write_json(path, completion)
    request_path, foreign_run = fixture_paths(inputs, "440-floor-32e0b689ce84")
    current_request, _ = fixture_paths(inputs, "440-build-20d60c90286c")
    request = json.loads(request_path.read_bytes())
    request["work"] = foreign_work
    request["requested"]["continuity"] = continuity
    if placement in {"after", "same-time"}:
        current = json.loads(current_request.read_bytes())
        request["launched_at"] = (datetime.fromisoformat(current["launched_at"]) +
                                  timedelta(days=1 if placement == "after" else 0)).isoformat()
    elif placement == "other-session":
        request["requested"]["session_id"] = "unrelated-session"
    write_json(request_path, request)
    read_bytes = Path.read_bytes

    def isolated(path):
        assert path != foreign_run, "foreign completion was opened"
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", isolated)
    result, prices = fixture_prices(inputs)
    value = prices["8c1ce0c713ab49abb277b46f5fd4732a"]
    assert prices["92aa0a262e6e4876b783d8f86be4e3c2"]["status"] == "known"
    assert request["dispatch_id"] not in prices
    if placement in {"between", "same-time"}:
        assert value["status"] == "unknown"
        assert "foreign dispatch" in value["reason"] and request["dispatch_id"] in value["reason"]
        assert result["total"]["unknown_dispatches"] == 1
    else:
        assert value["status"] == "known"


@pytest.mark.parametrize("charge", ["webSearchRequests", "otherBillableRequests"])
@pytest.mark.parametrize("count", [0, 1, 2])
def test_positive_non_token_claude_charges_need_card_coverage(tmp_path, charge, count):
    inputs = fixture_inputs(tmp_path, "claude", 694)
    _, path = fixture_paths(inputs, "694-use-5add0519e1f6")
    completion = json.loads(path.read_bytes())
    native = completion["attempts"][0]["observed"]["raw"]["claude-opus-5-5"]
    native[charge] = count
    native["costUSD"] = str(Decimal("3.2170122") + Decimal("0.01") * count)
    write_json(path, completion)
    result, prices = fixture_prices(inputs)
    value = next(iter(prices.values()))
    if count:
        assert value["status"] == "unknown" and charge in value["reason"]
        assert result["total"]["unknown_dispatches"] == 1 and result["total"]["known_amount"] == "0"
    else:
        assert value["status"] == "known" and value["source"] == "runtime-list-price"
        assert result["total"]["unknown_dispatches"] == 0


@pytest.mark.parametrize("launched", [None, "elapsed-zero", "elapsed-positive", "observation"])
def test_unlaunched_attempt_is_listed_without_poisoning_successful_fallback(report_inputs, launched):
    model = "claude-fixture"
    fallback = usage(vendor="claude", model=model, dispatch_id="fallback", tokens={"models": {
        model: {"input": 100, "cache_read": 20, "cache_creation": 0, "output": 10}}})
    fallback_rate = rate(model)
    fallback_rate.update(vendor="claude", classes={"input": 1, "cache_read": .5,
                                                  "cache_creation": 2, "output": 2})
    write_json(report_inputs["rates_path"], {"schema_version": 1, "rates": [fallback_rate]})
    _, path, request = write_bundle(report_inputs, "fallback", rows=[usage(), fallback])
    attempt = {"vendor": "codex", "model": "unavailable-model"}
    records.add_unobserved(attempt, "executable unavailable before launch")
    attempt["usage"] = records.usage_record(attempt, request, completed_at=WHEN, staffing_status="degraded")
    if launched == "elapsed-zero":
        attempt["elapsed_seconds"] = 0
    elif launched == "elapsed-positive":
        attempt["elapsed_seconds"] = 1
    elif launched == "observation":
        attempt["observed"]["source"] = "runtime-return"
    completion = json.loads(path.read_bytes())
    completion["attempts"][0] = attempt
    write_json(path, completion)
    result = cost.report(**report_inputs)
    value = result["dated_rate_card_equivalent"][0]["value"]
    assert len(result["raw_usage"]) == 2 and len(result["dated_rate_card_equivalent"]) == 2
    assert result["total"]["known_amount"] == "0.13"
    if launched is None:
        assert value["status"] == "not-launched"
        assert result["total"]["unknown_dispatches"] == 0 and result["total"]["priced_dispatches"] == 1
        assert not result["total"]["floor"] and result["total"]["floor_reasons"] == []
        assert result["dispatch_totals"][0]["unknown_attempts"] == 0
        completion["attempts"] = [attempt]
        write_json(path, completion)
        unlaunched = cost.report(**report_inputs)
        assert unlaunched["total"]["priced_dispatches"] == unlaunched["total"]["unknown_dispatches"] == 0
        assert not unlaunched["total"]["floor"]
        assert unlaunched["dispatch_totals"][0]["status"] == "not-launched"
    else:
        assert value["status"] == "unknown" and result["total"]["unknown_dispatches"] == 1
        assert result["total"]["floor"]


@pytest.mark.parametrize("dispatch", [None, [], [1], "", "malformed", 1, True])
def test_malformed_holder_dispatch_is_an_unknown_cli_contribution(report_inputs, dispatch):
    row = usage(stage="holder-close")
    row["dispatch"] = dispatch
    report_inputs["holder_path"].write_bytes((json.dumps(row) + "\n").encode())
    completed = report_cli(report_inputs)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["raw_usage"] == [row]
    value = result["dated_rate_card_equivalent"][0]["value"]
    assert value["status"] == "unknown" and "no dispatch" in value["reason"]
    assert result["total"]["unknown_dispatches"] == 1 and result["total"]["floor"]

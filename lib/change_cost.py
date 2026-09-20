#!/usr/bin/env python3
"""Record plan gauges and render a change's three-part cost report."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import uuid

from winio import utf8_stdio
from vendor_cli import CliError, resolve_command


class CostError(RuntimeError):
    """Cost evidence cannot be read without turning unknown into a guess."""


def unknown(reason: str) -> dict[str, str]:
    return {"status": "unknown", "reason": reason}


def default_dispatch_root() -> Path:
    return Path.home() / ".tradecraft" / "dispatches"


def default_plan_terms() -> Path:
    return Path.home() / ".tradecraft" / "plan-terms.json"


def change_root(repo: str, issue: int) -> Path:
    return Path.home() / ".tradecraft" / "changes" / Path(repo) / str(issue)


def default_gauges(repo: str, issue: int) -> Path:
    return change_root(repo, issue) / "gauges.jsonl"


def default_holder_usage(repo: str, issue: int) -> Path:
    return change_root(repo, issue) / "holder-usage.jsonl"


def _read_json(path: Path, description: str) -> object:
    try:
        return json.loads(path.read_bytes())
    except FileNotFoundError:
        raise
    except (OSError, ValueError) as exc:
        raise CostError(f"cannot read {description}: {path}") from exc


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    rows = []
    try:
        for number, line in enumerate(path.read_bytes().splitlines(), 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise CostError(f"{path}:{number}: expected a JSON object")
            rows.append(value)
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, CostError):
            raise
        raise CostError(f"cannot read JSON lines: {path}") from exc
    return rows


def _append_jsonl(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")
    with path.open("ab") as stream:
        stream.write(content)
        stream.flush()


def usage_rows(dispatch_root: Path, repo: str, issue: int,
               holder_path: Path | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if dispatch_root.is_dir():
        for path in sorted(dispatch_root.rglob("*.run.json")):
            value = _read_json(path, "dispatch completion")
            if not isinstance(value, dict) or value.get("schema_version") != 2:
                continue
            attempts = value.get("attempts")
            if not isinstance(attempts, list):
                continue
            for attempt in attempts:
                usage = attempt.get("usage") if isinstance(attempt, dict) else None
                change = usage.get("change") if isinstance(usage, dict) else None
                if isinstance(change, dict) and change.get("repository") == repo and change.get("issue") == issue:
                    rows.append(usage)
    rows.extend(_read_jsonl(holder_path or default_holder_usage(repo, issue)))
    return rows


def load_rates(path: Path) -> list[dict[str, object]]:
    value = _read_json(path, "rate card")
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("rates"), list):
        raise CostError("rate card must be a schema-version-1 object with a rates list")
    required = {"vendor", "model", "effective_from", "effective_to", "currency",
                "per_tokens", "classes", "source_url", "retrieved_at"}
    for row in value["rates"]:
        if not isinstance(row, dict) or not required.issubset(row):
            raise CostError("each rate row must carry the complete dated rate-card shape")
    return value["rates"]


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.utcoffset() is not None else None


def _rate_for(rates: list[dict[str, object]], vendor: str, model: str,
              when: datetime) -> dict[str, object] | None:
    matches = []
    for row in rates:
        start = _timestamp(row.get("effective_from"))
        end = _timestamp(row.get("effective_to")) if row.get("effective_to") is not None else None
        if row.get("vendor") == vendor and row.get("model") == model and start is not None:
            if start <= when and (end is None or when < end):
                matches.append((start, row))
    return max(matches, key=lambda item: item[0])[1] if matches else None


def _class_price(tokens: dict[str, object], rate: dict[str, object], model: str) -> tuple[Decimal | None, str | None]:
    classes = rate.get("classes")
    per_tokens = rate.get("per_tokens")
    if not isinstance(classes, dict) or not isinstance(per_tokens, int) or per_tokens <= 0:
        return None, f"rate row for {model} has invalid classes or per_tokens"
    total = Decimal(0)
    for name, count in tokens.items():
        if isinstance(count, bool) or not isinstance(count, (int, float)) or count < 0:
            return None, f"token class {name} for {model} is invalid"
        value = classes.get(name)
        if value is None:
            return None, f"token class {name} for {model} has no dated rate"
        try:
            total += Decimal(str(count)) * Decimal(str(value)) / Decimal(per_tokens)
        except (InvalidOperation, TypeError):
            return None, f"token class {name} for {model} has an invalid dated rate"
    return total, None


def rate_card_equivalent(usage: dict[str, object], rates: list[dict[str, object]]) -> dict[str, object]:
    dispatch = usage.get("dispatch")
    model = usage.get("model")
    if not isinstance(dispatch, dict) or not isinstance(model, dict):
        return unknown("usage row has no dispatch or model object")
    when = _timestamp(dispatch.get("launched_at"))
    if when is None:
        return unknown("dispatch timestamp is unavailable")
    vendor = dispatch.get("actual_vendor")
    if not isinstance(vendor, str):
        return unknown("actual vendor is unavailable")
    if usage.get("scope") not in {"invocation", "cumulative"}:
        return unknown("usage scope is unknown")
    tokens = usage.get("tokens")
    if not isinstance(tokens, dict):
        return unknown(str(usage.get("tokens_unknown_reason") or "token classes are unavailable"))
    additional = usage.get("additional_native_classes")
    if isinstance(additional, dict) and additional:
        return unknown("additional native token classes have no normalized rate mapping")
    if vendor == "claude":
        models = tokens.get("models")
        if not isinstance(models, dict) or not models:
            return unknown("Claude per-model token classes are unavailable")
        populations = models
    else:
        reported = model.get("reported")
        if not isinstance(reported, list) or len(reported) != 1:
            return unknown(str(model.get("reported_unknown_reason") or "exact runtime model is ambiguous"))
        populations = {reported[0]: tokens}
    total = Decimal(0)
    currency = None
    sources = []
    for exact_model, classes in populations.items():
        if not isinstance(exact_model, str) or not isinstance(classes, dict):
            return unknown("model token population is invalid")
        rate = _rate_for(rates, vendor, exact_model, when)
        if rate is None:
            return unknown(f"no dated rate matches {vendor} {exact_model}")
        if currency is not None and rate.get("currency") != currency:
            return unknown("matched rate rows use different currencies")
        currency = rate.get("currency")
        amount, reason = _class_price(classes, rate, exact_model)
        if reason:
            return unknown(reason)
        total += amount
        sources.append({"model": exact_model, "source_url": rate.get("source_url"),
                        "retrieved_at": rate.get("retrieved_at")})
    return {
        "status": "known", "currency": currency,
        "amount": format(total, "f"), "rate_sources": sources,
    }


def _plan_terms(path: Path) -> tuple[list[dict[str, object]], str | None]:
    try:
        value = _read_json(path, "plan terms")
    except FileNotFoundError:
        return [], f"plan terms file is absent: {path}"
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("terms"), list):
        raise CostError("plan terms must be a schema-version-1 object with a terms list")
    required = {"vendor", "effective_from", "effective_to", "billing_basis", "source"}
    rows = []
    for row in value["terms"]:
        if not isinstance(row, dict) or not required.issubset(row):
            raise CostError("each plan term must carry vendor, effective interval, billing basis and source")
        if "recurring_charge" not in row and "credit_terms" not in row:
            raise CostError("each plan term must carry recurring charge or credit terms, including unknown")
        rows.append(row)
    return rows, None


def _latest_gauges(path: Path) -> dict[str, dict[str, object]]:
    latest = {}
    for row in _read_jsonl(path):
        vendor = row.get("vendor")
        if isinstance(vendor, str):
            latest[vendor] = row
    return latest


def bill_plan_status(rows: list[dict[str, object]], terms_path: Path,
                     gauges_path: Path) -> list[dict[str, object]]:
    terms, terms_reason = _plan_terms(terms_path)
    gauges = _latest_gauges(gauges_path)
    vendors = sorted({
        str(row.get("dispatch", {}).get("actual_vendor")) for row in rows
        if isinstance(row.get("dispatch"), dict) and row["dispatch"].get("actual_vendor")
    })
    answer = []
    for vendor in vendors:
        dispatch_times = [
            _timestamp(row["dispatch"].get("launched_at")) for row in rows
            if isinstance(row.get("dispatch"), dict)
            and row["dispatch"].get("actual_vendor") == vendor
        ]
        dispatch_times = [when for when in dispatch_times if when is not None]
        when = max(dispatch_times) if dispatch_times else None
        matching = []
        if when is not None:
            for term in terms:
                start = _timestamp(term.get("effective_from"))
                end = _timestamp(term.get("effective_to")) if term.get("effective_to") is not None else None
                if term.get("vendor") == vendor and start is not None:
                    if start <= when and (end is None or when < end):
                        matching.append((start, term))
        term_value: object = max(matching, key=lambda item: item[0])[1] if matching else unknown(
            terms_reason or f"no plan term matches vendor {vendor}"
        )
        answer.append({
            "vendor": vendor,
            "plan_terms": term_value,
            "change_allocation": unknown("subscription or credit allocation cannot be divided by change"),
            "gauge": gauges.get(vendor) or unknown(f"no gauge snapshot exists for vendor {vendor}"),
        })
    return answer


def report(repo: str, issue: int, dispatch_root: Path, rates_path: Path,
           terms_path: Path, gauges_path: Path, holder_path: Path) -> dict[str, object]:
    rows = usage_rows(dispatch_root, repo, issue, holder_path)
    rates = load_rates(rates_path)
    prices = [{
        "dispatch_id": row.get("dispatch", {}).get("id") if isinstance(row.get("dispatch"), dict) else None,
        "value": rate_card_equivalent(row, rates),
    } for row in rows]
    groups: dict[tuple[str, str], int] = {}
    for row in rows:
        dispatch = row.get("dispatch")
        if isinstance(dispatch, dict):
            key = (str(dispatch.get("stage") or "unknown"), str(dispatch.get("actual_vendor") or "unknown"))
            groups[key] = groups.get(key, 0) + 1
    return {
        "marker": "change-cost:v1",
        "change": {"repository": repo, "issue": issue},
        "grouped_by_stage_and_vendor": [
            {"stage": stage, "vendor": vendor, "attempts": count}
            for (stage, vendor), count in sorted(groups.items())
        ],
        "raw_usage": rows,
        "dated_rate_card_equivalent": prices,
        "bill_plan_status": bill_plan_status(rows, terms_path, gauges_path),
    }


def _contains_money_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(word in lowered for word in ("amount", "cost", "currency", "usd", "price")):
                return True
            if _contains_money_key(child):
                return True
    if isinstance(value, list):
        return any(_contains_money_key(child) for child in value)
    return False


def holder_close(repo: str, issue: int, vendor: str, model: str | None,
                 tokens_file: Path | None, unknown_reason: str | None,
                 destination: Path, now: datetime | None = None) -> dict[str, object]:
    if (tokens_file is None) == (unknown_reason is None):
        raise CostError("holder close names exactly one of tokens file or unknown reason")
    captured = now or datetime.now(timezone.utc)
    tokens = None
    scope = "unknown"
    additional = {}
    reported = []
    reason = unknown_reason
    source = None
    if tokens_file is not None:
        value = _read_json(tokens_file, "holder usage")
        if not isinstance(value, dict) or not isinstance(value.get("tokens"), dict):
            raise CostError("holder usage file must contain a tokens object")
        if _contains_money_key(value):
            raise CostError("holder normalized usage cannot contain money fields")
        tokens = value["tokens"]
        scope = str(value.get("scope") or "unknown")
        if scope not in {"invocation", "cumulative", "unknown"}:
            raise CostError("holder usage scope must be invocation, cumulative or unknown")
        additional = value.get("additional_native_classes") or {}
        runtime_model = value.get("model")
        reported = [runtime_model] if isinstance(runtime_model, str) else []
        reason = None
        source = str(tokens_file.resolve())
    row = {
        "change": {"repository": repo, "issue": issue, "unknown_reason": None},
        "dispatch": {
            "id": "holder-close-" + uuid.uuid4().hex, "requested_vendor": vendor,
            "actual_vendor": vendor, "stage": "holder-close", "continuity": "fresh",
            "launched_at": captured.isoformat(), "completed_at": captured.isoformat(),
            "staffing_status": "qualified",
        },
        "model": {
            "requested": model, "reported": reported,
            "reported_unknown_reason": None if reported else "holder host supplied no runtime model",
        },
        "tokens": tokens, "tokens_unknown_reason": reason,
        "additional_native_classes": additional, "scope": scope,
        "source_field": "holder close attachment", "raw_source": source,
        "runtime_version": None,
        "runtime_version_unknown_reason": "holder host supplied no runtime version",
    }
    _append_jsonl(destination, row)
    return row


def gauge_from_codex_response(result: dict[str, object], captured_at: datetime) -> dict[str, object]:
    rate_limits = result.get("rateLimits")
    if not isinstance(rate_limits, dict):
        raise CostError("app-server response has no rateLimits object")
    primary = rate_limits.get("primary")
    if not isinstance(primary, dict):
        primary = {}
    return {
        "vendor": "codex", "captured_at": captured_at.isoformat(),
        "displayed_window": {
            "duration_minutes": primary.get("windowDurationMins"),
            "resets_at": primary.get("resetsAt"),
        },
        "displayed_value": {"used_percent": primary.get("usedPercent")},
        "source": "codex app-server account/rateLimits/read",
        "unknowns": {
            "remaining": "vendor response supplied used percent only",
            "token_conversion": "vendor supplied no token mapping",
            "invoice_conversion": "vendor supplied no invoice mapping",
        },
    }


def codex_rate_limits(explicit: str | None = None, timeout: float = 20) -> dict[str, object]:
    executable = resolve_command("codex", explicit)
    process = subprocess.Popen(
        [*executable, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if process.stdin is None or process.stdout is None or process.stderr is None:
        raise CostError("app-server pipes were not created")
    output: queue.Queue[bytes] = queue.Queue()

    def read_stdout() -> None:
        for line in iter(process.stdout.readline, b""):
            output.put(line)

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout

    def receive(identity: int) -> dict[str, object]:
        while time.monotonic() < deadline:
            try:
                line = output.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty as exc:
                raise CostError("Codex app-server rate-limit read timed out") from exc
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict) and value.get("id") == identity:
                if isinstance(value.get("error"), dict):
                    raise CostError(f"Codex app-server returned an error for request {identity}")
                result = value.get("result")
                if not isinstance(result, dict):
                    raise CostError(f"Codex app-server returned no object for request {identity}")
                return result
        raise CostError("Codex app-server rate-limit read timed out")

    def send(value: dict[str, object]) -> None:
        process.stdin.write((json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n").encode())
        process.stdin.flush()

    try:
        send({"id": 1, "method": "initialize", "params": {
            "clientInfo": {"name": "tradecraft-change-cost", "version": "1"},
            "capabilities": {"experimentalApi": True},
        }})
        receive(1)
        send({"method": "initialized"})
        send({"id": 2, "method": "account/rateLimits/read",
              "params": {"excludeResetCreditDetails": True}})
        return receive(2)
    finally:
        process.stdin.close()
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        reader.join(timeout=1)


def capture_gauge(vendor: str, destination: Path, display_file: Path | None,
                  now: datetime | None = None, codex_executable: str | None = None) -> dict[str, object]:
    captured = now or datetime.now(timezone.utc)
    if vendor == "codex":
        try:
            row = gauge_from_codex_response(codex_rate_limits(codex_executable), captured)
        except (OSError, CostError) as exc:
            if display_file is None:
                row = {
                    "vendor": vendor, "captured_at": captured.isoformat(),
                    "displayed_window": None, "displayed_value": None,
                    "source": "interactive /status capture absent",
                    "unknowns": {"gauge": f"app-server read failed: {exc}; /status capture not supplied"},
                }
            else:
                row = {
                    "vendor": vendor, "captured_at": captured.isoformat(),
                    "displayed_window": None, "displayed_value": None,
                    "source": "interactive /status",
                    "display": display_file.read_text(encoding="utf-8", errors="backslashreplace"),
                    "unknowns": {"structured_values": "interactive display was retained without conversion"},
                }
    elif vendor == "claude":
        row = {
            "vendor": vendor, "captured_at": captured.isoformat(),
            "displayed_window": None, "displayed_value": None,
            "source": "interactive /usage" if display_file else "interactive /usage capture absent",
            "unknowns": {"gauge": "Claude print JSON supplies no plan window; /usage capture not supplied"},
        }
        if display_file:
            row["display"] = display_file.read_text(encoding="utf-8", errors="backslashreplace")
            row["unknowns"] = {"structured_values": "interactive display was retained without conversion"}
    else:
        raise CostError(f"unsupported gauge vendor: {vendor}")
    _append_jsonl(destination, row)
    return row


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="Record plan gauges or render a read-time change cost report.")
    commands = cli.add_subparsers(dest="command", required=True)
    report_parser = commands.add_parser("report", help="render the three separately labelled quantities")
    report_parser.add_argument("--repo", required=True)
    report_parser.add_argument("--issue", required=True, type=int)
    report_parser.add_argument("--dispatch-root", type=Path, default=default_dispatch_root())
    report_parser.add_argument("--rates", type=Path, default=Path(__file__).with_name("rates.json"))
    report_parser.add_argument("--plan-terms", type=Path, default=default_plan_terms())
    report_parser.add_argument("--gauges", type=Path)
    report_parser.add_argument("--holder-usage", type=Path)
    close = commands.add_parser("holder-close", help="attach the holder's own usage at change close")
    close.add_argument("--repo", required=True)
    close.add_argument("--issue", required=True, type=int)
    close.add_argument("--vendor", required=True)
    close.add_argument("--model")
    source = close.add_mutually_exclusive_group(required=True)
    source.add_argument("--tokens-file", type=Path)
    source.add_argument("--unknown-reason")
    close.add_argument("--output", type=Path)
    gauge = commands.add_parser("capture-gauge", help="append a vendor plan-window snapshot")
    gauge.add_argument("--repo", required=True)
    gauge.add_argument("--issue", required=True, type=int)
    gauge.add_argument("--vendor", choices=("codex", "claude"), required=True)
    gauge.add_argument("--display-file", type=Path)
    gauge.add_argument("--codex")
    gauge.add_argument("--output", type=Path)
    return cli


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    args = parser().parse_args(argv)
    try:
        if args.command == "report":
            value = report(
                args.repo, args.issue, args.dispatch_root, args.rates, args.plan_terms,
                args.gauges or default_gauges(args.repo, args.issue),
                args.holder_usage or default_holder_usage(args.repo, args.issue),
            )
        elif args.command == "holder-close":
            value = holder_close(
                args.repo, args.issue, args.vendor, args.model, args.tokens_file,
                args.unknown_reason, args.output or default_holder_usage(args.repo, args.issue),
            )
        else:
            value = capture_gauge(
                args.vendor, args.output or default_gauges(args.repo, args.issue),
                args.display_file, codex_executable=args.codex,
            )
        print(json.dumps(value, ensure_ascii=True, indent=2))
        return 0
    except (OSError, UnicodeError, ValueError, CliError, CostError) as exc:
        print(f"change-cost: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

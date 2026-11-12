#!/usr/bin/env python3
"""Record plan gauges and render a change's three-part cost report.

Pricing a run from the shipped and repository price files. Design: lib/DESIGN.md#pricing-a-run
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import uuid

import holder_transcript as transcripts

from winio import utf8_stdio
from vendor_cli import CliError, resolve_command
from dispatch_record import _change
import run_lifecycle as lifecycle


class CostError(RuntimeError):
    """Cost evidence cannot be read without turning unknown into a guess."""


def unknown(reason: str) -> dict[str, str]:
    return {"status": "unknown", "reason": reason}


def _unknown_price(reasons: list[str]) -> dict[str, object]:
    reasons = list(dict.fromkeys(reasons))
    return {"status": "unknown", "reason": "; ".join(reasons), "reasons": reasons}


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


@dataclass
class _Attempt:
    usage: dict
    request: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    baseline_problems: list[str] = field(default_factory=list)
    position: int = 0
    bundle_id: str | None = None
    predecessor: str | None = None
    snapshot: dict | None = None
    share: dict | None = None
    foreign: bool = False


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


def _dispatch_json(path: Path, description: str) -> tuple[object, str | None]:
    try:
        return _read_json(path, description), None
    except (OSError, CostError) as exc:
        return None, f"cannot read {description}: {path}: {exc.__cause__ or exc}"


def _unknown_dispatch(request: dict[str, object], path: Path,
                      failure: str) -> dict[str, object]:
    reason = (
        "Dispatch completion is empty or unreadable; the dispatch may still be running "
        f"or have been interrupted: {path}. {failure}"
    )
    requested = request.get("requested")
    if not isinstance(requested, dict):
        requested = {}
    runtime_version = request.get("runtime_version")
    return {
        "change": _change(str(request.get("work") or "")),
        "dispatch": {
            "id": request.get("dispatch_id"), "stage": request.get("stage"),
            "requested_vendor": requested.get("vendor"), "actual_vendor": None,
            "continuity": requested.get("continuity"),
            "launched_at": request.get("launched_at"), "completed_at": None,
            "staffing_status": "unknown",
        },
        "model": {
            "requested": requested.get("model"), "reported": [],
            "reported_unknown_reason": reason,
        },
        "tokens": None, "tokens_unknown_reason": reason,
        "additional_native_classes": {}, "scope": "unknown",
        "source_field": None, "raw_source": str(path),
        "runtime_version": runtime_version if isinstance(runtime_version, str) else None,
        "runtime_version_unknown_reason": None if isinstance(runtime_version, str) else reason,
    }


def _belongs(usage: object, repo: str, issue: int) -> bool:
    change = usage.get("change") if isinstance(usage, dict) else None
    return isinstance(change, dict) and change.get("repository") == repo and change.get("issue") == issue


def _signature(attempts: list[_Attempt]) -> object:
    # Transport paths differ in copies; only pricing evidence decides equality.
    return [{"usage": {key: value for key, value in item.usage.items() if key != "raw_source"},
             "observed": item.evidence.get("observed"),
             "native_cost": item.evidence.get("native_cost"),
             "model": item.evidence.get("model")}
            for item in attempts]


def _request_signature(request: dict) -> dict:
    selected = request.get("requested") or {}
    if not isinstance(selected, dict):
        selected = {}
    return {"work": request.get("work"), "launched_at": request.get("launched_at"),
            "requested": {key: selected.get(key) for key in
                          ("vendor", "model", "continuity", "session_id")}}


def _contexts(dispatch_root: Path, repo: str, issue: int, holder_path: Path,
              skipped: list[dict[str, str]], *,
              foreign_requests: list[dict] | None = None) -> list[_Attempt]:
    bundles: dict[str, tuple[list[_Attempt], bool, dict]] = {}
    paths = set(dispatch_root.rglob("*.run.json")) if dispatch_root.is_dir() else set()
    if dispatch_root.is_dir():
        paths.update(path.with_name(path.name[:-len(".request.json")] + ".run.json")
                     for path in dispatch_root.rglob("*.request.json"))
    for path in sorted(paths):
        request_path = path.with_name(path.name[:-len(".run.json")] + ".request.json")
        request, request_failure = _dispatch_json(request_path, "dispatch request")
        if request_failure is None and not isinstance(request, dict):
            request_failure = f"dispatch request is not a JSON object: {request_path}"
        if request_failure is None:
            change = _change(str(request.get("work") or ""))
            if change["repository"] != repo or change["issue"] != issue:
                if foreign_requests is not None:
                    metadata = _request_signature(request)
                    metadata["dispatch_id"] = request.get("dispatch_id")
                    metadata["requested"]["vendor"] = _mapping(request.get("requested")).get("vendor")
                    foreign_requests.append(metadata)
                continue
        else:
            request = {}
        value, failure = _dispatch_json(path, "dispatch completion")
        malformed = None
        if failure is None:
            if not isinstance(value, dict) or value.get("schema_version") != 2:
                malformed = "unsupported dispatch completion schema"
            elif not isinstance(value.get("attempts"), list) or not value["attempts"]:
                malformed = "dispatch completion has no readable attempts"
            elif not value.get("completed_at"):
                malformed = "dispatch has no completion write; interrupted usage is unknown"
        if malformed:
            skipped.append({"path": str(path), "reason": malformed})
            failure = malformed
        items = []
        complete = failure is None
        if failure:
            if request_failure is None:
                items = [_Attempt(_unknown_dispatch(request, path, failure), request)]
            elif not malformed:
                skipped.append({"path": str(path), "reason": (
                    "Completion usage and request attribution are unavailable: "
                    f"{failure}; {request_failure}"
                )})
        else:
            for position, attempt in enumerate(value["attempts"]):
                usage = attempt.get("usage") if isinstance(attempt, dict) else None
                if _belongs(usage, repo, issue):
                    if not isinstance(usage.get("dispatch"), dict) or not isinstance(usage.get("model"), dict):
                        usage = None
                    else:
                        items.append(_Attempt(usage, request, attempt, position=position))
                        continue
                # A valid foreign usage row cannot establish target attribution.
                if isinstance(usage, dict) and isinstance(usage.get("change"), dict):
                    continue
                reason = f"attempt {position} has no readable normalized usage"
                skipped.append({"path": str(path), "reason": reason})
                complete = False
                if request_failure is None:
                    items.append(_Attempt(_unknown_dispatch(request, path, reason), request,
                                          position=position))
            if not items and request_failure is None:
                reason = "dispatch completion has no attributable usage"
                skipped.append({"path": str(path), "reason": reason})
                items = [_Attempt(_unknown_dispatch(request, path, reason), request)]
                complete = False
        if not items:
            continue
        identity = request.get("dispatch_id") or (value.get("dispatch_id") if isinstance(value, dict) else None)
        identity = identity or _mapping(items[0].usage.get("dispatch")).get("id")
        if not identity:
            skipped.append({"path": str(path), "reason": "dispatch id is unavailable; copies cannot be identified"})
            continue
        key = str(identity)
        for item in items:
            item.bundle_id = key
        if key not in bundles:
            bundles[key] = (items, complete, request)
            continue
        previous, was_complete, previous_request = bundles[key]
        requests_conflict = bool(request and previous_request and
                                _request_signature(request) != _request_signature(previous_request))
        conflict = requests_conflict or (any(item.evidence for item in items)
                                        and any(item.evidence for item in previous)
                                        and _signature(items) != _signature(previous))
        if complete and not was_complete:
            carried = [problem for item in previous for problem in item.problems]
            for item in items:
                item.problems.extend(carried)
            bundles[key] = (items, complete, request)
            previous = items
        if conflict:
            reason = f"conflicting bundle evidence for dispatch {key}"
            for item in previous:
                item.problems.append(reason)
            skipped.append({"path": str(path), "reason": reason})
    result = [item for items, _, _ in bundles.values() for item in items]
    holders: dict[str, _Attempt] = {}
    holder_evidence, holder_skipped = transcripts.holder_rows(holder_path)
    skipped.extend(holder_skipped)
    for key, usage, problems in holder_evidence:
        if not _belongs(usage, repo, issue):
            continue
        item = _Attempt(usage, bundle_id=key, problems=problems)
        if key in holders:
            if _signature([item]) != _signature([holders[key]]):
                holders[key].problems.append(f"conflicting holder usage for dispatch {key}")
        else:
            holders[key] = item
    result.extend(holders.values())
    return result


def usage_rows(dispatch_root: Path, repo: str, issue: int,
               holder_path: Path | None = None, *,
               skipped_records: list[dict[str, str]] | None = None) -> list[dict[str, object]]:
    skipped = skipped_records if skipped_records is not None else []
    return [item.usage for item in _contexts(
        dispatch_root, repo, issue, holder_path or default_holder_usage(repo, issue), skipped)]


_RATE_FIELDS = ("vendor", "model", "effective_from", "effective_to", "currency",
                "per_tokens", "classes", "source_url", "retrieved_at")


def _tier_problem(row: dict) -> str | None:
    tiers = row.get("prompt_tiers")
    if tiers is None:
        return None
    if not isinstance(tiers, list) or not tiers:
        return "prompt_tiers must be a nonempty list"
    thresholds = []
    for tier in tiers:
        if not isinstance(tier, dict) or not isinstance(tier.get("classes"), dict):
            return "each prompt tier must carry a classes object"
        threshold = tier.get("above_prompt_tokens")
        if type(threshold) is not int or threshold <= 0:
            return "each prompt tier's above_prompt_tokens must be a positive integer"
        thresholds.append(threshold)
    if len(set(thresholds)) != len(thresholds):
        return "prompt tier thresholds must be distinct"
    return None


def load_rates(path: Path) -> list[dict[str, object]]:
    value = _read_json(path, "rate card")
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("rates"), list):
        raise CostError("rate card must be a schema-version-1 object with a rates list")
    for row in value["rates"]:
        if not isinstance(row, dict) or not set(_RATE_FIELDS).issubset(row):
            raise CostError("each rate row must carry the complete dated rate-card shape")
        problem = _tier_problem(row)
        if problem:
            raise CostError(f"rate row for {row.get('model')}: {problem}")
    return value["rates"]


_PRICING_PAGES = {"claude": "https://platform.claude.com/docs/en/about-claude/pricing",
                  "codex": "https://developers.openai.com/api/docs/pricing"}
_ENTRY_CLASSES = {
    "claude": {"input": "Base input tokens", "cache_write_5m": "5m cache writes",
               "cache_write_1h": "1h cache writes", "cache_creation": "1h cache writes price again",
               "cache_read": "Cache hits and refreshes", "output": "Output tokens"},
    "codex": {"input": "Input", "cached_input": "Cached input",
              "cache_write_input": "30m write", "output": "Output"},
}
_ENTRY_PROCESSING = {
    "claude": "standard; duration-specific cache writes; legacy cache_creation retains one-hour interpretation",
    "codex": "standard; short context",
}
_REPOSITORY_RATES = Path(".tradecraft") / "rates.json"


def _placeholder(value: object, where: str = "") -> str | None:
    if isinstance(value, str) and value.startswith("FILL"):
        return where or "value"
    if isinstance(value, dict):
        for key, child in value.items():
            found = _placeholder(child, f"{where}.{key}" if where else str(key))
            if found:
                return found
    if isinstance(value, list):
        for number, child in enumerate(value):
            found = _placeholder(child, f"{where}[{number}]")
            if found:
                return found
    return None


def _repository_row_problem(row: object) -> str | None:
    if not isinstance(row, dict):
        return "entry is not a JSON object"
    missing = [name for name in _RATE_FIELDS if name not in row]
    if missing:
        return "missing field " + ", ".join(missing)
    placeholder = _placeholder(row)
    if placeholder:
        return f"{placeholder} still holds a FILL placeholder; replace it from the pricing page"
    if not isinstance(row["vendor"], str) or not isinstance(row["model"], str):
        return "vendor and model must be strings"
    if _timestamp(row["effective_from"]) is None:
        return "effective_from is not a timestamp with a zone, such as 2026-11-12T00:00:00Z"
    if row["effective_to"] is not None and _timestamp(row["effective_to"]) is None:
        return "effective_to must be null or a timestamp with a zone"
    denominator = _number(row["per_tokens"])
    if denominator is None or denominator <= 0:
        return "per_tokens must be a positive number"
    tiers = row.get("prompt_tiers") if isinstance(row.get("prompt_tiers"), list) else []
    for name, classes in [("classes", row["classes"]),
                          *((f"prompt_tiers[{n}].classes", _mapping(t).get("classes")) for n, t in enumerate(tiers))]:
        if not isinstance(classes, dict) or not classes:
            return f"{name} must be a nonempty object"
        for key, price in classes.items():
            if isinstance(price, bool) or not isinstance(price, (int, float)) or _number(price) is None:
                return f"{name}.{key} must be a finite nonnegative number"
    return _tier_problem(row)


def repository_rates(path: Path | None) -> tuple[list[dict], dict[str, object]]:
    """Read a repository's own price file; a bad paste is named and set aside so it can't take every other figure."""
    if path is None:
        return [], {"path": None, "status": "no-repository",
                    "reason": "no repository top level was found; run from inside the repository or pass --root",
                    "rejected": []}
    status = {"path": str(path), "status": "read", "rejected": []}
    try:
        value = json.loads(path.read_bytes())
    except FileNotFoundError:
        return [], {**status, "status": "absent"}
    except (OSError, ValueError) as exc:
        return [], {**status, "status": "unreadable", "reason": f"cannot read the file as JSON: {exc}"}
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("rates"), list):
        return [], {**status, "status": "unreadable",
                    "reason": "the file must be a schema-version-1 object with a rates list"}
    rows = []
    for row in value["rates"]:
        problem = _repository_row_problem(row)
        if problem:
            status["rejected"].append({"model": _mapping(row).get("model"), "reason": problem})
        else:
            rows.append(row)
    return rows, status


def repository_rates_path(root: Path | None) -> Path | None:
    """The repository's price file; it lives in the repository so a plugin update keeps it."""
    if root is None:
        try:
            completed = subprocess.run(["git", "rev-parse", "--show-toplevel"], stdin=subprocess.DEVNULL,
                                       capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return None
        text = completed.stdout.decode("utf-8", errors="backslashreplace").strip()
        if completed.returncode or not text:
            return None
        root = Path(text)
    return root.expanduser().resolve() / _REPOSITORY_RATES


class _Card:
    """The shipped rows, then the repository's own rows for a use the shipped card does not price."""

    def __init__(self, shipped, repository=(), repository_path=None):
        self.shipped = list(shipped)
        self.repository = list(repository)
        self.repository_path = repository_path
        self.now_shipped: dict[tuple[str, str], dict] = {}

    def lookup(self, vendor, model, when):
        row = _rate_for(self.shipped, vendor, model, when)
        local = _rate_for(self.repository, vendor, model, when) if self.repository else None
        if row is not None:
            # A shipped price is checked against the posted page by the practice; a pasted one is not.
            if local is not None:
                self.now_shipped.setdefault((vendor, model), {
                    "vendor": vendor, "model": model, "path": self.repository_path,
                    "note": "the shipped card now prices this model for these uses; "
                            "this repository entry can be removed"})
            return row, "shipped"
        return (local, "repository") if local is not None else (None, None)

    def ended_page(self, vendor, model, when):
        for row in [*self.shipped, *self.repository]:
            end = _timestamp(row.get("effective_to"))
            if row.get("vendor") == vendor and row.get("model") == model and end is not None and when >= end:
                return row.get("source_url")
        return None

    def origin(self, label):
        if label == "repository":
            return {"price_file": "repository", "price_file_path": self.repository_path}
        return {"price_file": "shipped"}


def _card(rates) -> _Card:
    return rates if isinstance(rates, _Card) else _Card(rates)


def _missing_reason(card: _Card, vendor, model, when, subject: str) -> str:
    reason = f"no price for {vendor} {model}; {subject} excluded from the known amount"
    page = card.ended_page(vendor, model, when) if when else None
    if page:
        reason += f"; price interval for {model} has ended; re-read the posted page: {page}"
    return reason


def _prompt_tier(rate: dict, prompt: Decimal) -> tuple[dict, str]:
    """The posted page prices tokens "over" its threshold, so a prompt exactly at it takes the lower prices."""
    chosen = None
    for tier in rate.get("prompt_tiers") or []:
        if prompt > tier["above_prompt_tokens"] and (
                chosen is None or tier["above_prompt_tokens"] > chosen["above_prompt_tokens"]):
            chosen = tier
    if chosen is None:
        return rate, "base"
    return {**rate, "classes": chosen["classes"]}, f"above {chosen['above_prompt_tokens']}"


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


def _number(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and number >= 0 else None
    except InvalidOperation:
        return None


_CODEX_NAMES = {"input_tokens": "input", "cached_input_tokens": "cached_input",
                "cache_write_input_tokens": "cache_write_input", "output_tokens": "output",
                "reasoning_output_tokens": "reasoning_output", "inputTokens": "input",
                "cachedInputTokens": "cached_input", "outputTokens": "output",
                "reasoningOutputTokens": "reasoning_output", "totalTokens": "total_tokens"}
_CLAUDE_NAMES = {"inputTokens": "input", "input_tokens": "input",
                 "cacheReadInputTokens": "cache_read", "cache_read_input_tokens": "cache_read",
                 "cacheCreationInputTokens": "cache_creation", "cache_creation_input_tokens": "cache_creation",
                 "outputTokens": "output", "output_tokens": "output",
                 "thinkingTokens": "thinking", "thinking_tokens": "thinking"}
_LIMITS = {"maxOutputTokens", "max_output_tokens", "maxInputTokens", "max_input_tokens"}
_CLAUDE_METADATA = {"costUSD", "costBasis", "contextWindow", "canonicalModel", "provider"}


def _counts(classes: dict, aliases: dict, required: tuple[str, ...],
            reasons: list[str], model: str) -> dict[str, Decimal]:
    result = {}
    for name, value in classes.items():
        if name in _LIMITS:
            continue
        name = aliases.get(name, name)
        number = _number(value)
        if number is None:
            reasons.append(f"token class {name} for {model} is not finite and nonnegative")
        elif name in result and result[name] != number:
            reasons.append(f"token class {name} for {model} has conflicting counts")
        else:
            result[name] = number
    for name in required:
        if name not in result:
            reasons.append(f"token class {name} for {model} is unavailable")
    return result


def _codex_counts(item: _Attempt, reasons: list[str]) -> dict | None:
    observed = item.evidence.get("observed") or {}
    if not isinstance(observed, dict):
        observed = {}
    native = observed.get("raw")
    if isinstance(native, list) and native and isinstance(native[-1], dict):
        classes = dict(native[-1])
    elif (observed.get("source") == "Codex native thread/tokenUsage/updated.params.tokenUsage.total"
            and isinstance(native, dict) and isinstance(native.get("total"), dict)):
        classes = dict(native["total"])
    else:
        classes = item.usage.get("tokens")
        if not isinstance(classes, dict):
            reasons.append(str(item.usage.get("tokens_unknown_reason") or "token classes are unavailable"))
            return None
        classes = dict(classes)
        extras = item.usage.get("additional_native_classes") or {}
        if isinstance(extras, dict):
            classes.update(extras)
        else:
            reasons.append("additional native token classes are malformed")
    model = str(_mapping(item.usage.get("model")).get("requested") or "unknown model")
    counts = _counts(classes, _CODEX_NAMES, ("input", "cached_input", "output"), reasons, model)
    counts.setdefault("cache_write_input", Decimal(0))
    counts.setdefault("reasoning_output", Decimal(0))
    if counts.get("cached_input", 0) + counts["cache_write_input"] > counts.get("input", 0):
        reasons.append(f"cached input and cache writes exceed total input for {model}")
    if counts["reasoning_output"] > counts.get("output", 0):
        reasons.append(f"reasoning exceeds output for {model}")
    if "total_tokens" in counts:
        if counts["total_tokens"] != counts.get("input", 0) + counts.get("output", 0):
            reasons.append(f"total tokens disagree with input plus output for {model}")
        counts.pop("total_tokens")
    return counts


def _session_ids(item: _Attempt) -> set[str]:
    requested = item.request.get("requested") or {}
    observed = item.evidence.get("observed") or {}
    if not isinstance(requested, dict):
        requested = {}
    if not isinstance(observed, dict):
        observed = {}
    threads = observed.get("thread_ids")
    values = [requested.get("session_id"), observed.get("session_id"),
              *(threads if isinstance(threads, list) else [])]
    return {value for value in values if isinstance(value, str) and value}


def _not_launched(item: _Attempt) -> bool:
    observed = item.evidence.get("observed")
    return (isinstance(observed, dict) and observed.get("source") is None
            and observed.get("raw") is None and observed.get("normalized") is None
            and item.evidence.get("elapsed_seconds") is None
            and item.usage.get("tokens") is None
            and not item.usage.get("additional_native_classes"))


def _session_shares(items: list[_Attempt], foreign_requests: list[dict] | None = None) -> None:
    histories: dict[str, list[_Attempt]] = {}
    for item in items:
        dispatch = _mapping(item.usage.get("dispatch"))
        vendor = dispatch.get("actual_vendor") or dispatch.get("requested_vendor")
        if vendor != "codex" or dispatch.get("stage") == "holder-close" or _not_launched(item):
            continue
        problems = []
        item.snapshot = _codex_counts(item, problems)
        item.problems.extend(problems)
        item.baseline_problems = list(item.problems)
        identities = _session_ids(item)
        if len(identities) > 1:
            item.problems.append("requested and observed session identities disagree")
            item.baseline_problems.append("requested and observed session identities disagree")
        if not identities and dispatch.get("continuity") == "resume":
            item.problems.append("resumed Codex dispatch has no session identity")
        for identity in identities:
            histories.setdefault(identity, []).append(item)
    seen_foreign = set()
    for request in foreign_requests or []:
        requested = _mapping(request.get("requested"))
        identity = requested.get("session_id")
        if requested.get("vendor") != "codex" or not isinstance(identity, str) or identity not in histories:
            continue
        signature = json.dumps([request.get("dispatch_id"), _request_signature(request)], sort_keys=True)
        if signature in seen_foreign:
            continue
        seen_foreign.add(signature)
        # Request-only barriers preserve isolation: no foreign completion is opened.
        histories[identity].append(_Attempt(
            {"dispatch": {"launched_at": request.get("launched_at")}}, request,
            bundle_id=request.get("dispatch_id"), foreign=True))
    for history in histories.values():
        bad_time = any(_timestamp(_mapping(item.usage.get("dispatch")).get("launched_at")) is None
                       for item in history)
        ordered = sorted(history, key=lambda item: (
            _timestamp(_mapping(item.usage.get("dispatch")).get("launched_at"))
            or datetime.min.replace(tzinfo=timezone.utc),
            not item.foreign,
            item.position))
        previous = None
        for item in ordered:
            if item.foreign:
                previous = item
                continue
            dispatch = _mapping(item.usage.get("dispatch"))
            if dispatch.get("continuity") == "resume":
                if previous is not None and previous.foreign:
                    item.predecessor = previous.bundle_id
                    item.problems.append(
                        "preceding Codex session snapshot is missing or excluded: "
                        f"intervening foreign dispatch {previous.bundle_id} belongs to another change")
                if bad_time:
                    item.problems.append("session chronology is ambiguous because a launch timestamp is unavailable")
                elif previous is None:
                    item.problems.append("preceding Codex session snapshot is missing or excluded")
                elif not previous.foreign:
                    item.predecessor = previous.bundle_id
                    start = _timestamp(dispatch.get("launched_at"))
                    prior_dispatch = _mapping(previous.usage.get("dispatch"))
                    prior_start = _timestamp(prior_dispatch.get("launched_at"))
                    prior_end = _timestamp(prior_dispatch.get("completed_at"))
                    if prior_start >= start or prior_end is None or prior_end > start:
                        item.problems.append("preceding session chronology overlaps or is ambiguous")
                    if prior_start >= start or (prior_end is not None and prior_end > start):
                        item.baseline_problems.append("preceding session chronology overlaps or is ambiguous")
                    if previous.baseline_problems or previous.snapshot is None:
                        item.problems.append(f"preceding dispatch {previous.bundle_id} has an unreadable or inconsistent baseline")
                    elif item.snapshot is not None:
                        if set(item.snapshot) != set(previous.snapshot):
                            item.problems.append("preceding session snapshot has missing or incomparable counters")
                        else:
                            share = {key: value - previous.snapshot[key] for key, value in item.snapshot.items()}
                            if any(value < 0 for value in share.values()):
                                item.problems.append("session counters decreased from the preceding snapshot")
                                item.baseline_problems.append("session counters decreased from the preceding snapshot")
                            else:
                                item.share = share
            previous = item


def _class_price(classes: dict, rate: dict, model: str,
                 reasons: list[str]) -> Decimal:
    prices = rate.get("classes")
    denominator = _number(rate.get("per_tokens"))
    if not isinstance(prices, dict) or denominator is None or denominator <= 0:
        reasons.append(f"rate row for {model} has invalid classes or token denominator")
        return Decimal(0)
    total = Decimal(0)
    for name, count in classes.items():
        if count == 0:
            continue
        value = _number(prices.get(name))
        if value is None:
            reasons.append(f"token class {name} for {model} has no valid dated rate")
        else:
            total += count * value / denominator
    return total


def _runtime_prices(item: _Attempt, models: dict) -> dict[str, Decimal]:
    observed = item.evidence.get("observed") or {}
    if not isinstance(observed, dict):
        return {}
    raw = observed.get("raw")
    if observed.get("source") != "modelUsage" or not isinstance(raw, dict):
        return {}
    prices = {}
    for model in models:
        values = raw.get(model)
        if isinstance(values, dict) and values.get("costBasis") == "list":
            amount = _number(values.get("costUSD"))
            if amount is not None:
                prices[model] = amount
    return prices


def _price(item: _Attempt, rates: list[dict]) -> dict:
    if _mapping(item.usage.get("holder")).get("source_kind") == "transcript":
        return _transcript_price(item, rates)
    if _not_launched(item):
        return {"status": "not-launched", "reason": "attempt did not reach a runtime", "reasons": []}
    usage = item.usage
    dispatch = _mapping(usage.get("dispatch"))
    model = _mapping(usage.get("model"))
    reasons = list(item.problems)
    if not dispatch or not model:
        reasons.append("usage row has no dispatch or model object")
    when = _timestamp(dispatch.get("launched_at"))
    if when is None:
        reasons.append("dispatch timestamp is unavailable")
    vendor = dispatch.get("actual_vendor")
    if not isinstance(vendor, str):
        reasons.append("actual vendor is unavailable")
        vendor = dispatch.get("requested_vendor")
    resume = dispatch.get("continuity") == "resume"
    if usage.get("source") == "cloud-stop-hook":
        # A cloud attempt's tokens are its share of the session's running total, so a
        # resumed session is priced once across its attempts.
        ledger = _mapping(usage.get("ledger_check"))
        if vendor != "claude" or usage.get("scope") != "session-delta":
            reasons.append("cloud usage is not a Claude session delta")
        elif ledger.get("ok") is not True:
            reasons.append("cloud usage ledger disagrees: " + "; ".join(
                str(fault) for fault in ledger.get("faults") or ["no ledger check recorded"]))
    elif resume and vendor == "claude":
        reasons.append("resumed Claude usage scope is not established")
    elif resume and vendor == "codex" and item.share is None:
        reasons.append("resumed Codex share has no usable preceding snapshot")
    elif usage.get("scope") not in {"invocation", "cumulative"} and item.share is None:
        reasons.append("usage scope is unknown")
    populations = {}
    if vendor == "codex":
        exact_model = (item.evidence.get("model") or _mapping(item.request.get("requested")).get("model")
                       or model.get("requested"))
        if not isinstance(exact_model, str) or not exact_model:
            reasons.append("requested Codex model is unavailable")
        counts = item.share if item.share is not None else _codex_counts(item, reasons)
        classes = dict(counts or {})
        if classes.get("reasoning_output", 0) > classes.get("output", 0):
            reasons.append("reasoning exceeds output in the dispatch share")
        classes.pop("reasoning_output", None)
        if "input" in classes:
            classes["input"] -= classes.get("cached_input", 0) + classes.get("cache_write_input", 0)
            if classes["input"] < 0:
                reasons.append("cached input and cache writes exceed total input in the dispatch share")
        populations[exact_model] = classes
    elif vendor == "claude":
        tokens = usage.get("tokens")
        models = tokens.get("models") if isinstance(tokens, dict) else None
        extras = usage.get("additional_native_classes") or {}
        if not isinstance(extras, dict):
            reasons.append("additional native token classes are malformed")
            extras = {}
        observed = item.evidence.get("observed")
        native = observed.get("raw") if isinstance(observed, dict) and observed.get("source") == "modelUsage" else None
        if not isinstance(models, dict) or not models:
            reasons.append(str(usage.get("tokens_unknown_reason") or "Claude per-model token classes are unavailable"))
            models = {name: {} for name in model.get("reported", [])}
        for exact_model, raw_classes in models.items():
            if not isinstance(raw_classes, dict):
                reasons.append(f"model token population is invalid for {exact_model}")
                raw_classes = {}
            classes = dict(raw_classes)
            extra_classes = extras.get(exact_model) or {}
            if isinstance(extra_classes, dict):
                classes.update(extra_classes)
            else:
                reasons.append(f"additional native classes for {exact_model} are malformed")
            if isinstance(native, dict) and isinstance(native.get(exact_model), dict):
                # Read original counts too: normalization deliberately omits invalid values.
                for name, count in native[exact_model].items():
                    if name in _CLAUDE_NAMES or name.endswith("Tokens") or name.endswith("_tokens"):
                        classes[name] = count
                    elif name not in _CLAUDE_METADATA and name not in _LIMITS:
                        number = _number(count)
                        if number is not None and number > 0:
                            reasons.append(f"billable native count {name} for {exact_model} has no card rate mapping")
            counts = _counts(classes, _CLAUDE_NAMES,
                             ("input", "cache_read", "cache_creation", "output"), reasons, str(exact_model))
            thinking = counts.pop("thinking", Decimal(0))
            if thinking > counts.get("output", 0):
                reasons.append(f"thinking exceeds output for {exact_model}")
            populations[exact_model] = counts
    else:
        reasons.append(f"no token interpretation for vendor {vendor}")
    card = _card(rates)
    total = Decimal(0)
    currency = None
    sources = []
    card_models = {}
    five_minute = {}
    unpriced = {}
    for exact_model, classes in populations.items():
        if not isinstance(exact_model, str) or not exact_model:
            continue
        if when is None:
            reasons.append(f"no price can be dated for {vendor} {exact_model} without the dispatch timestamp")
            known_classes = {"input", "cached_input", "cache_write_input", "output"} if vendor == "codex" else {
                "input", "cache_read", "cache_creation", "output"}
            for name, count in classes.items():
                if name not in known_classes and count > 0:
                    reasons.append(f"billable token class {name} for {exact_model} has no rate mapping")
            continue
        rate, origin = card.lookup(vendor, exact_model, when)
        # One unpriced model must not cost the run every share the card does price.
        if rate is None:
            unpriced[exact_model] = {"model": exact_model, "vendor": vendor, "cause": "no-price",
                                     "first_use": when.isoformat(),
                                     "reason": _missing_reason(card, vendor, exact_model, when, "its usage is")}
            continue
        if rate.get("prompt_tiers"):
            # Totals cannot show which requests crossed a threshold, so neither tier is guessed.
            unpriced[exact_model] = {"model": exact_model, "vendor": vendor, "cause": "per-request-tiers",
                                     "reason": f"{exact_model} is priced per request by prompt length, and this "
                                               "run recorded only totals; its usage is excluded from the known amount"}
            continue
        if currency is not None and rate.get("currency") != currency:
            reasons.append("matched rate rows use different currencies")
        currency = rate.get("currency")
        card_models[exact_model] = _class_price(classes, rate, exact_model, reasons)
        prices = _mapping(rate.get("classes"))
        if (classes.get("cache_creation", 0) > 0 and "cache_write_5m" not in classes
                and "cache_write_1h" not in classes and _number(prices.get("cache_write_5m")) is not None
                and _number(prices.get("cache_write_1h")) is not None):
            # The aggregate cannot say which duration was written; helpers write five-minute cache.
            shorter = {("cache_write_5m" if name == "cache_creation" else name): count
                       for name, count in classes.items()}
            five_minute[exact_model] = _class_price(shorter, rate, exact_model, [])
        total += card_models[exact_model]
        sources.append({"model": exact_model, "source_url": rate.get("source_url"),
                        "retrieved_at": rate.get("retrieved_at"), **card.origin(origin)})
    runtime = _runtime_prices(item, populations) if vendor == "claude" else {}
    for entry in unpriced.values():
        # Only a runtime figure marked as a list price is trusted: an older runtime prices an
        # unknown model at another model's rates and marks that figure otherwise.
        entry["share"] = "runtime-list-price" if entry["model"] in runtime else "excluded"
        if entry["share"] == "runtime-list-price":
            entry["runtime_amount"] = format(runtime[entry["model"]], "f")
    excluded = [entry["reason"] for entry in unpriced.values() if entry["share"] == "excluded"]
    if currency not in (None, "USD") and any(entry["share"] == "runtime-list-price" for entry in unpriced.values()):
        reasons.append(f"a runtime list charge in USD cannot be added to a {currency} card figure")
    if reasons:
        value = _unknown_price(reasons)
    else:
        # With no card row matched, every share is a runtime list charge, which is in USD, or excluded
        # and so zero; claiming USD lets that figure count in the change total like any other.
        value = {"status": "known", "currency": currency or "USD", "amount": format(total, "f"),
                 "rate_sources": sources, "basis": "API list-price equivalence",
                 "source": "rate-card", "floor": vendor == "codex" or bool(excluded),
                 "floor_reasons": list(excluded), "reasons": []}
        if vendor == "codex":
            value["model_basis"] = "requested model"
            value["floor_reasons"] = ["Codex short-context rates are a floor; requests are not separated",
                                      *excluded]
        else:
            flags = []
            comparisons = []
            selected = Decimal(0)
            readings = {}
            for exact_model, amount in card_models.items():
                native = runtime.get(exact_model)
                shorter = five_minute.get(exact_model)
                if (native is not None and shorter is not None and abs(native - amount) > Decimal("0.01")
                        and abs(native - shorter) <= Decimal("0.01")):
                    readings[exact_model] = ("5m", shorter)
                else:
                    readings[exact_model] = ("1h" if shorter is not None else None, amount)
            matched = sum((amount for _, amount in readings.values()), Decimal(0))
            covered = [runtime[name] for name in card_models if name in runtime]
            whole_mismatch = len(covered) == len(card_models) and abs(
                sum(covered, Decimal(0)) - matched) > Decimal("0.01")
            for exact_model, (reading, amount) in readings.items():
                native = runtime.get(exact_model)
                mismatch = native is not None and (whole_mismatch or abs(native - amount) > Decimal("0.01"))
                if mismatch:
                    flags.append(f"runtime/card list-price mismatch above one cent; model population {exact_model}")
                selected += native if native is not None and not mismatch else amount
                comparison = {"model": exact_model, "card_amount": format(amount, "f"),
                              "runtime_amount": format(native, "f") if native is not None else None,
                              "source": "runtime-list-price" if native is not None and not mismatch else "rate-card"}
                if reading is not None:
                    comparison["card_cache_write_reading"] = reading
                comparisons.append(comparison)
            for entry in unpriced.values():
                if entry["share"] == "runtime-list-price":
                    selected += runtime[entry["model"]]
                    comparisons.append({"model": entry["model"], "card_amount": None,
                                        "runtime_amount": entry["runtime_amount"],
                                        "source": "runtime-list-price",
                                        "basis": "runtime list charge; no card price"})
            value["amount"] = format(selected, "f")
            value["model_prices"] = comparisons
            value["flags"] = flags
            value["source"] = ("runtime-list-price" if comparisons and all(
                row["source"] == "runtime-list-price" for row in comparisons) else "rate-card"
                if all(row["source"] == "rate-card" for row in comparisons) else "runtime-and-rate-card")
            value["card_amount"] = format(matched, "f")
            if populations and set(runtime) >= {name for name in populations if isinstance(name, str) and name}:
                value["runtime_amount"] = format(sum(runtime.values(), Decimal(0)), "f")
    if unpriced:
        value["unpriced_models"] = [{key: entry[key] for key in entry if key != "reason"}
                                    for entry in unpriced.values()]
    if item.predecessor is not None:
        value["predecessor_dispatch_id"] = item.predecessor
    if item.share is not None:
        value["dispatch_token_share"] = {key: format(count, "f") for key, count in item.share.items()}
    if dispatch.get("stage") == "holder-close":
        value["timestamp_basis"] = "close capture time"
    return value


def _agent_contributions(holder, items, prices):
    """Use exact native identity and priced invocation coverage, never resemblance."""
    decisions = {}
    replies = holder.get("replies", [])
    for agent in sorted({reply.get("agent_id") for reply in replies if reply.get("agent_id")}):
        children = [reply for reply in replies if reply.get("agent_id") == agent]
        covered, unresolved, observations = {}, {}, []
        for attempt, price in zip(items, prices):
            dispatch = _mapping(attempt.usage.get("dispatch"))
            if dispatch.get("stage") == "holder-close" or dispatch.get("actual_vendor") != "claude":
                continue
            # Unknown and not-launched prices carry no currency. This single
            # check also keeps non-USD contributions out of a USD exclusion.
            if price.get("currency") != "USD":
                if agent in _session_ids(attempt):
                    observations.append({"dispatch_id": attempt.bundle_id, "attempt_index": attempt.position,
                                         "status": "not already priced", "reason": price.get("reason")})
                continue
            observed = _mapping(attempt.evidence.get("observed"))
            threads = observed.get("thread_ids")
            native_ids = {value for value in [observed.get("session_id"),
                          *(threads if isinstance(threads, list) else [])] if isinstance(value, str) and value}
            recorded_ids = _session_ids(attempt)
            ids = recorded_ids - {holder.get("session_id")}
            exact = agent in native_ids and recorded_ids == {agent}
            # begin_native records this field; CLI launches have a separate
            # native session and cannot be a parent session's transcript child.
            potential_native = "recorded_at" in attempt.request and (not ids or agent in ids)
            if not exact and not potential_native:
                continue
            start, end = _timestamp(dispatch.get("launched_at")), _timestamp(dispatch.get("completed_at"))
            # A model whose share the dispatch excluded is priced, or floored, in the holder row instead.
            left_out = {entry.get("model") for entry in price.get("unpriced_models") or []
                        if entry.get("share") == "excluded"}
            matching_models = {name: counts for name, counts in
                               _mapping(_mapping(attempt.usage.get("tokens")).get("models")).items()
                               if name not in left_out}
            selected = [reply for reply in children if (start is None or end is None or
                        start <= _timestamp(reply["timestamp"]) <= end)
                        and reply["model"] in matching_models]
            if not selected:
                continue
            marker = {"dispatch_id": attempt.bundle_id, "attempt_index": attempt.position}
            proof = exact and start is not None and end is not None and attempt.usage.get("scope") == "invocation"
            required = transcripts.aggregate(selected)["models"]
            extra_required = transcripts.additional_counts(selected)
            missing_extras = []
            for model, counts in required.items():
                normalized = _counts(matching_models[model], _CLAUDE_NAMES,
                                     ("input", "output", "cache_read", "cache_creation"), [], model)
                if any(normalized.get(name, Decimal(-1)) < count for name, count in counts.items()
                       if name in {"input", "output", "cache_read", "cache_creation"}):
                    proof = False
                available = _mapping(_mapping(attempt.usage.get("additional_native_classes")).get(model))
                for name, count in extra_required.get(model, {}).items():
                    observed_count = _number(available.get(name))
                    if (type(count) is not int or count < 0 or observed_count is None or observed_count < count):
                        proof = False
                        missing_extras.append(name)
            if missing_extras:
                marker["uncovered_native_classes"] = sorted(set(missing_extras))
            for reply in selected:
                if proof:
                    covered[reply["id"]] = marker
                else:
                    unresolved.setdefault(reply["id"], []).append(marker)
        for reply in children:
            identity = reply["id"]
            if identity in covered:
                decisions[identity] = {"status": "excluded", "agent_id": agent, **covered[identity]}
            elif identity in unresolved:
                extra_names = sorted({name for candidate in unresolved[identity]
                                      for name in candidate.get("uncovered_native_classes", [])})
                decisions[identity] = {"status": "unresolved", "agent_id": agent,
                                       "candidate_dispatches": unresolved[identity],
                                       "reason": f"subagent {agent} has unresolved priced native overlap"
                                       + ("; additional native counts not covered: " + ",".join(extra_names) if extra_names else "")}
            else:
                decisions[identity] = {"status": "included", "agent_id": agent,
                                       "observations": observations}
    return decisions


def _transcript_price(item, rates, agent_decisions=None):
    usage = item.usage
    holder = _mapping(usage.get("holder"))
    if item.problems:
        return _unknown_price(item.problems)
    problem = transcripts.ledger_problem(holder)
    if problem:
        return _unknown_price([problem])
    replies = holder.get("replies")
    if not isinstance(replies, list):
        return _unknown_price(["transcript row has no retained reply ledger"])
    gaps = [str(gap.get("reason")) for gap in holder.get("gaps", [])]
    unresolved_replies = {gap["reply_id"] for gap in holder["gaps"] if gap.get("reply_id") is not None}
    if usage.get("tokens_unknown_reason"):
        gaps.append(str(usage["tokens_unknown_reason"]))
    decisions = agent_decisions or {}
    card = _card(rates)
    total, slices, exclusions, effective, reasons = Decimal(0), [], [], [], list(gaps)
    computable = False
    missing: dict[str, dict] = {}
    for reply in replies:
        if reply["id"] in unresolved_replies:
            continue
        counts = reply["tokens"]
        extras = reply["additional_native_classes"]
        zero_billable = not any(counts.values()) and all(type(count) is int and count == 0 for count in extras.values())
        decision = decisions.get(reply.get("id"), {"status": "included"})
        if zero_billable and decision["status"] == "unresolved":
            decision = {**decision, "status": "included", "reason": "zero billable populations; no monetary overlap"}
        if reply.get("agent_id"):
            effective.append({"reply_id": reply.get("id"), **decision})
        if decision["status"] == "excluded":
            exclusions.append({"reply_id": reply["id"], **decision})
            continue
        if decision["status"] == "unresolved":
            reasons.append(decision["reason"])
            continue
        when, model = _timestamp(reply.get("timestamp")), reply.get("model")
        if zero_billable:
            computable = True
            slices.append({"reply_id": reply["id"], "model": model, "timestamp": reply["timestamp"],
                           "amount": "0", "basis": "zero billable populations; no rate required"})
            continue
        if when is None:
            reasons.append(f"reply {reply.get('id')} has no readable timestamp")
            continue
        rate, origin = card.lookup("claude", model, when)
        malformed = [name for name, count in extras.items() if type(count) is not int or count < 0]
        if rate is None:
            entry = missing.setdefault(model, {"replies": 0, "first": when, "last": when})
            entry["replies"] += 1
            entry["first"], entry["last"] = min(entry["first"], when), max(entry["last"], when)
            # A malformed count is a fault of its own; a missing price must not hide it.
            reasons.extend(f"reply {reply['id']} has unmapped or invalid billable native count: {name}"
                           for name in malformed)
            continue
        required = transcripts.TOKEN_CLASSES
        classes = {name: Decimal(count) for name, count in counts.items() if name != "cache_creation"}
        # Each reply is one request, so a tiered row is priced on this reply's own prompt.
        prompt = sum((classes.get(name, Decimal(0)) for name in
                      ("input", "cache_read", "cache_write_5m", "cache_write_1h")), Decimal(0))
        rate, tier = _prompt_tier(rate, prompt)
        price_reasons = []
        amount = _class_price(classes, rate, model, price_reasons)
        if rate.get("currency") != "USD":
            price_reasons.append(f"reply {reply.get('id')} rate currency is not USD")
        if price_reasons:
            reasons.extend(price_reasons)
            continue
        for name, count in extras.items():
            if type(count) is not int or count < 0:
                reasons.append(f"reply {reply['id']} has unmapped or invalid billable native count: {name}")
            elif count:
                if name in required:
                    reasons.append(f"reply {reply['id']} native count {name} overlaps a canonical token population")
                    continue
                extra_reasons = []
                extra_amount = _class_price({name: Decimal(count)}, rate, model, extra_reasons)
                if extra_reasons:
                    reasons.append(f"reply {reply['id']} has unmapped billable native count: {name}")
                    reasons.extend(extra_reasons)
                else:
                    amount += extra_amount
        computable = True
        total += amount
        slices.append({"reply_id": reply["id"], "model": model, "timestamp": reply["timestamp"],
                       "amount": format(amount, "f"), "source_url": rate.get("source_url"),
                       "retrieved_at": rate.get("retrieved_at"), "effective_from": rate.get("effective_from"),
                       "duration_rates_retrieved_at": rate.get("duration_rates_retrieved_at"),
                       "prompt_tier": tier, **card.origin(origin)})
    reasons = list(dict.fromkeys(reasons))
    price_gaps = []
    for model, entry in missing.items():
        count = entry["replies"]
        subject = "1 reply on it is" if count == 1 else f"{count} replies on it are"
        price_gaps.append(_missing_reason(card, "claude", model, entry["last"], subject))
    if reasons and not computable:
        value = _unknown_price(reasons + price_gaps)
    else:
        # A missing price is no fault in the evidence, so it lowers the figure to a floor rather than voiding it.
        floor_reasons = reasons + price_gaps
        value = {"status": "known", "currency": "USD", "amount": format(total, "f"),
                 "basis": "API list-price equivalence", "source": "rate-card",
                 "floor": bool(floor_reasons), "floor_reasons": floor_reasons, "reasons": [],
                 "rate_sources": slices}
    if missing:
        value["unpriced_models"] = [{"model": model, "vendor": "claude", "cause": "no-price",
                                     "share": "excluded", "replies": entry["replies"],
                                     "first_use": entry["first"].isoformat()}
                                    for model, entry in missing.items()]
    value.update(timestamp_basis="reply time", attribution="attributed by time",
                 window=holder.get("window"), session_id=holder.get("session_id"),
                 dispatch_exclusions=exclusions, effective_agent_inclusion=effective,
                 unresolved_reply_ids=sorted(unresolved_replies),
                 late_recording_receipts=holder.get("late_recording_receipts", []))
    return value


def rate_card_equivalent(usage: dict[str, object], rates: list[dict[str, object]]) -> dict[str, object]:
    return _price(_Attempt(usage), rates)


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


def runtime_report(repo, issue, dispatch_root):
    bundles = lifecycle.launch_bundles(dispatch_root, f"{repo}#{issue}",
                                      {"build", "floor", "review-disposition"}, exact_work=True)
    # Attribution retains the cost report's exact repository spelling.
    bundles = [row for row in bundles if row[2].get("work") == f"{repo}#{issue}"]
    groups = {}
    for row in bundles:
        request = row[2]
        root = request.get("root")
        root = Path(root).resolve() if isinstance(root, str) and root else root
        # The entrance charges this registered tree across stages and handovers.
        # Older schema-2 requests lack the new budget identifier; that cannot
        # split their consumption away from the resumed builder's report.
        key = (root, request.get("lineage_branch"))
        groups.setdefault(key, []).append(row)
    reports = []
    for (root, branch), rows in groups.items():
        identities = sorted({row[2]["budget_lineage"] for row in rows
                             if isinstance(row[2].get("budget_lineage"), str)})
        reports.append({"lineage": identities[0] if len(identities) == 1 else None,
                        "lineage_identifiers": identities,
                        "lineage_basis": "registered root and branch",
                        "root": str(root) if isinstance(root, Path) else root, "branch": branch,
                        **lifecycle.runtime_account(rows)})
    return reports


def _entry_template(vendor: str, model: str, first_use: datetime) -> dict[str, object]:
    unit = "USD per million tokens, as a number"
    names = _ENTRY_CLASSES.get(vendor, {})
    return {
        "vendor": vendor, "model": model,
        # Midnight of the earliest affected use, so the filled entry covers the run that asked for it.
        "effective_from": first_use.astimezone(timezone.utc).strftime("%Y-%m-%dT00:00:00Z"),
        "effective_to": None, "currency": "USD", "per_tokens": 1000000,
        "classes": {name: f"FILL: the {column} column's price for {model}, {unit}"
                    for name, column in names.items()},
        "source_url": _PRICING_PAGES.get(vendor),
        "retrieved_at": "FILL: the UTC time you read the page, such as 2026-11-12T05:21:04Z",
        "processing": _ENTRY_PROCESSING.get(vendor, "standard"),
        "applicability_basis": "backfilled list-price equivalence; applicability is separate from retrieval",
    }


_GUIDANCE = (
    "Look the model up on pricing_page, replace every FILL value in entry from the column it names, "
    "set retrieved_at to the time you read the page, and add entry to the rates list in paste_into "
    "(or save new_file there when it is given); the next report prices these uses. If the page prices "
    "the model by prompt length, add to entry \"prompt_basis\": \"a request's input, cache-read and "
    "cache-write tokens, each request priced on its own\" and \"prompt_tiers\": [{\"above_prompt_tokens\": "
    "100000, \"classes\": {...the same class names, at the prices for prompts over that many tokens...}}], "
    "keeping entry's own classes as the prices at or below it. Then send the filled entry to the practice "
    "repository named by the installed plugin's homepage, so that the shipped card carries it."
)


def _missing_prices(prices: list[dict], files: dict) -> list[dict[str, object]]:
    found: dict[tuple[str, str], dict] = {}
    for price in prices:
        for entry in price["value"].get("unpriced_models") or []:
            if entry.get("cause") != "no-price":
                continue
            key = (entry["vendor"], entry["model"])
            target = found.setdefault(key, {"uses": [], "first": _timestamp(entry["first_use"])})
            use = {"dispatch_id": price["dispatch_id"], "attempt_index": price["attempt_index"]}
            if "replies" in entry:
                use["replies"] = entry["replies"]
            target["uses"].append(use)
            target["first"] = min(target["first"], _timestamp(entry["first_use"]))
    repository = files["repository"]
    paste_into = repository["path"] or str(Path("<repository top level>") / _REPOSITORY_RATES)
    answer = []
    for (vendor, model), target in sorted(found.items()):
        entry = _entry_template(vendor, model, target["first"])
        value = {"vendor": vendor, "model": model, "uses": target["uses"],
                 "pricing_page": _PRICING_PAGES.get(vendor), "paste_into": paste_into, "entry": entry}
        if value["pricing_page"] is None:
            value["pricing_page_reason"] = f"no posted pricing page is known for vendor {vendor}"
        if repository["status"] == "no-repository":
            value["paste_into_note"] = "run the report from inside the repository, or pass --root"
        if repository["status"] in {"absent", "no-repository"}:
            value["new_file"] = {"schema_version": 1, "rates": [entry]}
        value["instructions"] = _GUIDANCE
        answer.append(value)
    return answer


def report(repo: str, issue: int, dispatch_root: Path, rates_path: Path,
           terms_path: Path, gauges_path: Path, holder_path: Path, *,
           repository_rates_path: Path | None = None) -> dict[str, object]:
    skipped_records: list[dict[str, str]] = []
    foreign_requests: list[dict] = []
    items = _contexts(dispatch_root, repo, issue, holder_path, skipped_records,
                      foreign_requests=foreign_requests)
    warnings = [{key: value for key, value in entry.items() if key != "report_warning"}
                for entry in skipped_records if entry.get("report_warning")]
    skipped_records = [entry for entry in skipped_records if not entry.get("report_warning")]
    rows = [item.usage for item in items]
    local_rows, repository_status = repository_rates(repository_rates_path)
    price_files = {"shipped": str(rates_path), "repository": repository_status}
    rates = _Card(load_rates(rates_path), local_rows, repository_status["path"])
    _session_shares(items, foreign_requests)
    prices = [{
        "dispatch_id": _mapping(item.usage.get("dispatch")).get("id"),
        "attempt_index": item.position,
        "value": _price(item, rates),
    } for item in items]
    for item, price in zip(items, prices):
        holder = _mapping(item.usage.get("holder"))
        if holder.get("source_kind") == "transcript":
            decisions = (_agent_contributions(holder, items, [row["value"] for row in prices])
                         if not item.problems and transcripts.ledger_problem(holder) is None else {})
            price["value"] = _transcript_price(item, rates, decisions)
            historical = [candidate.bundle_id for candidate in items
                          if _mapping(candidate.usage.get("dispatch")).get("stage") == "holder-close"
                          and _mapping(candidate.usage.get("dispatch")).get("actual_vendor") == "claude"
                          and candidate.usage.get("tokens") is not None
                          and not _mapping(candidate.usage.get("holder")).get("session_id")
                          and _mapping(candidate.usage.get("holder")).get("source_kind") != "transcript"]
            if historical:
                price["value"]["overlap_warnings"] = [{
                    "reason": "historical supplied Claude counters lack session identity; overlap with transcript usage cannot be established",
                    "holder_close_ids": historical}]
            unregistered = [candidate.bundle_id for candidate in items
                            if _mapping(candidate.usage.get("dispatch")).get("stage") == "holder-close"
                            and _mapping(candidate.usage.get("dispatch")).get("actual_vendor") == "claude"
                            and candidate.usage.get("tokens") is not None
                            and _mapping(candidate.usage.get("holder")).get("session_id")
                            and _mapping(_mapping(candidate.usage.get("holder")).get("window")).get("boundary_registered") is False]
            if unregistered:
                price["value"].setdefault("overlap_warnings", []).append({
                    "reason": "supplied Claude counters have no registered session boundary; overlap with transcript usage cannot be established",
                    "holder_close_ids": unregistered})
    summaries = {}
    floor_reasons = []
    for item, price in zip(items, prices):
        identity = item.bundle_id
        summary = summaries.setdefault(identity, {
            "dispatch_id": identity, "known_amount": Decimal(0), "attempts": 0,
            "unknown_attempts": 0, "not_launched_attempts": 0, "reasons": [],
        })
        summary["attempts"] += 1
        value = price["value"]
        if value["status"] == "not-launched":
            summary["not_launched_attempts"] += 1
        elif value["status"] == "known" and value.get("currency") == "USD":
            summary["known_amount"] += Decimal(value["amount"])
            floor_reasons.extend(value.get("floor_reasons") or [])
        else:
            summary["unknown_attempts"] += 1
            summary["reasons"].extend(value.get("reasons") or ["contribution currency is not USD"])
    runtime_models = sorted({entry["model"] for price in prices if price["value"]["status"] == "known"
                             for entry in price["value"].get("unpriced_models") or []
                             if entry.get("share") == "runtime-list-price"})
    unknown_count = sum(summary["unknown_attempts"] > 0 for summary in summaries.values())
    known_total = sum((summary["known_amount"] for summary in summaries.values()), Decimal(0))
    if unknown_count:
        floor_reasons.append("dispatches with unknown contributions are excluded from the known amount")
    if skipped_records:
        floor_reasons.append("skipped evidence may contain additional contributions")
    for summary in summaries.values():
        summary["status"] = ("not-launched" if summary["not_launched_attempts"] == summary["attempts"]
                             else "unknown" if summary["unknown_attempts"] else "known")
        summary["currency"] = "USD"
        summary["known_amount"] = format(summary["known_amount"], "f")
        summary["reasons"] = list(dict.fromkeys(summary["reasons"]))
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
        "runtime_lineages": runtime_report(repo, issue, dispatch_root),
        "skipped_records": skipped_records,
        "warnings": warnings,
        "dated_rate_card_equivalent": prices,
        "dispatch_totals": list(summaries.values()),
        "total": {
            "basis": "API list-price equivalence; not plan or subscription billing",
            "currency": "USD", "known_amount": format(known_total, "f"),
            "display_amount": format(known_total, ".2f"),
            "priced_dispatches": sum(summary["status"] == "known" for summary in summaries.values()),
            "unknown_dispatches": unknown_count,
            "floor": bool(floor_reasons), "floor_reasons": list(dict.fromkeys(floor_reasons)),
            "skipped_record_count": len(skipped_records),
            "runtime_list_price_models": runtime_models,
        },
        "price_files": price_files,
        "missing_prices": _missing_prices(prices, price_files),
        "repository_entries_now_shipped": [rates.now_shipped[key] for key in sorted(rates.now_shipped)],
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
                 destination: Path, now: datetime | None = None, *, session_id=None,
                 claude_projects=None, state_root=None) -> dict[str, object]:
    if tokens_file is not None and unknown_reason is not None:
        raise CostError("holder close accepts only one of tokens file or unknown reason")
    if tokens_file is None and unknown_reason is None:
        if vendor != "claude":
            raise CostError("automatic holder close requires --vendor claude; supply --tokens-file or --unknown-reason")
        return transcripts.close(repo, issue, destination, model=model, session_id=session_id,
                                 projects=claude_projects, state_root=state_root, now=now)
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
    if vendor == "claude" and (session_id is not None or os.environ.get("CLAUDE_CODE_SESSION_ID")):
        return transcripts.close(repo, issue, destination, model=model, session_id=session_id,
                                 projects=claude_projects, state_root=state_root, now=now, supplied_row=row)
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
    report_parser.add_argument("--root", type=Path,
                               help="repository top level whose .tradecraft/rates.json adds prices; "
                                    "defaults to the current directory's repository")
    close = commands.add_parser("holder-close", help="attach the holder's own usage at change close")
    close.add_argument("--repo", required=True)
    close.add_argument("--issue", required=True, type=int)
    close.add_argument("--vendor", required=True)
    close.add_argument("--model")
    source = close.add_mutually_exclusive_group()
    source.add_argument("--tokens-file", type=Path)
    source.add_argument("--unknown-reason")
    close.add_argument("--output", type=Path)
    close.add_argument("--session-id", help="actual Claude transcript session, instead of the current environment identity")
    close.add_argument("--claude-projects", type=Path, help="projects directory; overrides CLAUDE_CONFIG_DIR/projects and home")
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
                repository_rates_path=repository_rates_path(args.root),
            )
        elif args.command == "holder-close":
            value = holder_close(
                args.repo, args.issue, args.vendor, args.model, args.tokens_file,
                args.unknown_reason, args.output or default_holder_usage(args.repo, args.issue),
                session_id=args.session_id, claude_projects=args.claude_projects,
            )
        else:
            value = capture_gauge(
                args.vendor, args.output or default_gauges(args.repo, args.issue),
                args.display_file, codex_executable=args.codex,
            )
        print(json.dumps(value, ensure_ascii=True, indent=2))
        return 0
    except (OSError, UnicodeError, ValueError, CliError, CostError, transcripts.TranscriptError) as exc:
        print(f"change-cost: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

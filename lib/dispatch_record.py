#!/usr/bin/env python3
"""Retain one dispatch request, its source return, and reported usage.

The default store is machine-local and survives worktree removal. CLI launchers
use the bundle helpers directly; native dispatch tools use the ``begin`` and
``finish`` commands around the tool call, then ``attach`` for later products or
assessments.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid

from winio import utf8_stdio

SCHEMA_VERSION = 2
CONTINUITIES = ("fresh", "resume")
CLASSIFICATIONS = ("ordinary", "cold", "terminal")
SEMANTIC_VERSION = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?\Z"
)


class RecordError(RuntimeError):
    """A dispatch record cannot be created without losing its contract."""


def producer_version() -> str:
    """Return the validated version of the plugin that produced a record."""
    manifest = Path(__file__).resolve().parent.parent / ".claude-plugin" / "plugin.json"
    try:
        value = json.loads(manifest.read_bytes())
    except (OSError, UnicodeError, ValueError) as exc:
        raise RecordError(f"cannot read plugin version: {manifest}") from exc
    version = value.get("version") if isinstance(value, dict) else None
    if not isinstance(version, str) or SEMANTIC_VERSION.fullmatch(version) is None:
        raise RecordError(f"plugin manifest has an invalid semantic version: {manifest}")
    return version


def sidecar(output: Path, suffix: str) -> Path:
    return output.with_name(output.name + suffix)


def default_record_root() -> Path:
    return Path.home() / ".tradecraft" / "dispatches"


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return cleaned[:48] or "dispatch"


def default_output_path(work: str, stage: str) -> Path:
    parent = default_record_root().expanduser().resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{stamp}-{_slug(work)}-{_slug(stage)}-{uuid.uuid4().hex[:12]}"
    return parent / name / "result.md"


def resolved_output(output: Path | None, work: str, stage: str) -> Path:
    chosen = output if output is not None else default_output_path(work, stage)
    return chosen.expanduser().absolute()


def require_output_outside_root(output: Path, root: Path | None) -> None:
    if root is None:
        return
    try:
        output.resolve().relative_to(root.resolve())
    except ValueError:
        return
    raise RecordError(f"dispatch output must be outside the recipient root: {output}")


def runtime_version(executable: list[str]) -> str | None:
    try:
        result = subprocess.run(
            [*executable, "--version"], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    try:
        return result.stdout.decode("utf-8").strip() or None
    except UnicodeError:
        return None


def git_revision(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    try:
        return result.stdout.decode("ascii").strip() or None
    except UnicodeError:
        return None


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def write_bytes(path: Path, content: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(content)


def write_json(path: Path, value: object) -> None:
    write_bytes(path, json_bytes(value))


def finalize_reserved_json(path: Path, value: object) -> None:
    """Atomically replace an empty reservation with one complete JSON record."""
    if not path.is_file() or path.stat().st_size:
        raise RecordError(f"dispatch reservation is absent or already filled: {path}")
    with tempfile.TemporaryDirectory(prefix=".tradecraft-record-", dir=path.parent) as temporary:
        staged = Path(temporary) / "record.json"
        with staged.open("xb") as stream:
            stream.write(json_bytes(value))
            stream.flush()
        os.replace(staged, path)


def publish_output(path: Path, content: bytes) -> None:
    """Publish complete bytes atomically without replacing another caller."""
    with tempfile.TemporaryDirectory(prefix=".tradecraft-publish-", dir=path.parent) as temporary:
        staged = Path(temporary) / "result"
        write_bytes(staged, content)
        os.link(staged, path)


class ReservedBundle:
    """Reserved sidecar streams whose immutable request is not yet complete."""

    def __init__(self, streams: dict[Path, object]):
        self.streams = streams
        self.ready = False

    def __getitem__(self, path: Path):
        return self.streams[path]

    def values(self):
        return self.streams.values()

    def mark_ready(self) -> None:
        """Keep the bundle after its request and dispatch input are durable."""
        self.ready = True


@contextmanager
def reserve_bundle(destinations: list[Path], output: Path):
    """Prove exact-path creation before usage, keeping sidecars reserved."""
    streams: dict[Path, object] = {}
    created: list[Path] = []
    reservation = ReservedBundle(streams)
    try:
        for path in destinations:
            streams[path] = path.open("xb")
            created.append(path)
        streams.pop(output).close()
        with tempfile.TemporaryDirectory(prefix=".tradecraft-publish-", dir=output.parent) as temporary:
            os.link(output, Path(temporary) / "probe")
        output.unlink()
        yield reservation
    finally:
        for stream in streams.values():
            stream.close()
        if not reservation.ready:
            for path in created:
                path.unlink(missing_ok=True)


def log_bytes(raw: bytes) -> tuple[bytes, str]:
    try:
        return raw.decode("utf-8").replace("\r\n", "\n").encode("utf-8"), "utf-8"
    except UnicodeError:
        encoded = {"encoding": "base64", "data": base64.b64encode(raw).decode("ascii")}
        return json_bytes(encoded), "base64-json"


def request_record(
    *,
    dispatch_id: str,
    work: str,
    stage: str,
    settings_source: str,
    settings_scope: str,
    vendor: str,
    model: str,
    effort: str,
    continuity: str,
    permission_boundary: str,
    root: Path | None,
    classification: str | None = None,
    requested_session_id: str | None = None,
    command: list[str] | None = None,
    setting_sources: dict[str, str] | None = None,
    retry_of: str | None = None,
    holder_session_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    for name, value in (
        ("dispatch id", dispatch_id),
        ("work", work), ("stage", stage), ("settings source", settings_source),
        ("settings scope", settings_scope), ("vendor", vendor), ("model", model),
        ("effort", effort), ("permission boundary", permission_boundary),
    ):
        if not value.strip():
            raise RecordError(f"{name} must be nonempty")
    if continuity not in CONTINUITIES:
        raise RecordError(f"continuity must be one of: {', '.join(CONTINUITIES)}")
    if classification is not None and classification not in CLASSIFICATIONS:
        raise RecordError(f"classification must be one of: {', '.join(CLASSIFICATIONS)}")
    if continuity == "resume" and not (requested_session_id and requested_session_id.strip()):
        raise RecordError("resume continuity requires an explicit session id")
    if continuity == "fresh" and requested_session_id is not None:
        raise RecordError("fresh continuity cannot request an existing session id")
    if retry_of is not None and not retry_of.strip():
        raise RecordError("retry dispatch id must be nonempty")
    if holder_session_id is not None and not holder_session_id.strip():
        raise RecordError("holder session id must be nonempty")
    if holder_session_id == dispatch_id:
        raise RecordError("a dispatch id cannot also identify the holder session")
    if holder_session_id is not None and holder_session_id == requested_session_id:
        raise RecordError("a builder session cannot also identify the holder session")
    for name, source in (setting_sources or {}).items():
        if not name.strip() or not source.strip():
            raise RecordError("setting source names and values must be nonempty")
    when = now or datetime.now(timezone.utc)
    return {
        "schema_version": SCHEMA_VERSION,
        "dispatch_id": dispatch_id,
        "work": work,
        "producer_version": producer_version(),
        "stage": stage,
        "settings_source": settings_source,
        "settings_scope": settings_scope,
        "retry_of": retry_of,
        "holder_session_id": holder_session_id,
        "requested": {
            "vendor": vendor,
            "model": model,
            "effort": effort,
            "classification": classification,
            "continuity": continuity,
            "session_id": requested_session_id,
            "permission_boundary": permission_boundary,
            "command": command,
            "sources": setting_sources or {},
        },
        "root": str(root.resolve()) if root is not None else None,
        "launched_at": when.astimezone(timezone.utc).isoformat(),
    }


@dataclass(frozen=True)
class CodexStreamResult:
    """The completion and final-message facts owned by one Codex JSONL stream."""

    valid: bool
    events: tuple[dict[str, object], ...]
    completed: bool
    failed_events: tuple[dict[str, object], ...]
    error_events: tuple[dict[str, object], ...]
    final_message: str | None


def codex_stream_result(raw: bytes) -> CodexStreamResult:
    """Parse a Codex JSONL stream once without treating recovered errors as failure."""
    try:
        values = [json.loads(line) for line in raw.decode("utf-8").splitlines()
                  if line.strip()]
    except (UnicodeError, ValueError):
        return CodexStreamResult(False, (), False, (), (), None)
    if not all(isinstance(item, dict) for item in values):
        return CodexStreamResult(False, (), False, (), (), None)
    events = tuple(values)
    completed = any(event.get("type") == "turn.completed" for event in events)
    failed = tuple(event for event in events if event.get("type") == "turn.failed")
    errors = tuple(event for event in events if event.get("type") == "error")
    messages: list[str] = []
    for event in events:
        item = event.get("item")
        if (event.get("type") == "item.completed" and isinstance(item, dict)
                and item.get("type") == "agent_message"
                and isinstance(item.get("text"), str)):
            messages.append(item["text"])
    return CodexStreamResult(
        True, events, completed, failed, errors, messages[-1] if messages else None,
    )


def _number(value: object) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _reported_fields(raw: dict[str, object], names: tuple[str, ...]) -> dict[str, int | float]:
    return {name: value for name in names if (value := _number(raw.get(name))) is not None}


def _codex_evidence(raw: bytes, continuity: str) -> dict[str, object]:
    stream = codex_stream_result(raw)
    events = list(stream.events)
    completed = [event for event in events if event.get("type") == "turn.completed"]
    usage = [event.get("usage") for event in completed if isinstance(event.get("usage"), dict)]
    thread_ids = [event.get("thread_id") for event in events
                  if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str)]
    turn_ids = [event.get("turn_id") for event in events if isinstance(event.get("turn_id"), str)]
    observed_models = sorted({str(event["model"]) for event in events if event.get("model")})
    normalized = None
    reason = "runtime returned no turn.completed usage"
    if usage:
        source = usage[-1]
        fields = _reported_fields(source, (
            "input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"
        ))
        if continuity == "fresh":
            normalized = {"scope": "invocation", **fields}
            reason = None
        else:
            reason = "resume usage scope is not established for this runtime version"
    additional = {}
    if usage:
        known = {"input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"}
        additional = {
            key: value for key, value in usage[-1].items()
            if key not in known and key.endswith("_tokens") and _number(value) is not None
        }
    return {
        "source": "turn.completed.usage",
        "raw": usage,
        "normalized": normalized,
        "normalized_unavailable_reason": reason,
        "additional_native_classes": additional,
        "reported_models": observed_models,
        "reported_models_unavailable_reason": None if observed_models else "runtime returned no model identifier",
        "reported_effort": None,
        "reported_effort_unavailable_reason": "runtime returned no effort field",
        "thread_ids": thread_ids,
        "turn_ids": turn_ids,
        "stream_valid": stream.valid,
        "turn_completed": stream.completed,
        "turn_failed_count": len(stream.failed_events),
        "recovered_error_count": len(stream.error_events),
    }


def _claude_evidence(raw: bytes, continuity: str) -> dict[str, object]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        payload = None
    if not isinstance(payload, dict):
        return {
            "source": "claude JSON result",
            "raw": None,
            "normalized": None,
            "normalized_unavailable_reason": "runtime returned no valid JSON result",
            "additional_native_classes": {},
            "reported_models": [],
            "reported_models_unavailable_reason": "runtime returned no valid JSON result",
            "reported_effort": None,
            "reported_effort_unavailable_reason": "runtime returned no valid JSON result",
            "thread_ids": [],
            "turn_ids": [],
        }
    model_usage = payload.get("modelUsage")
    models: dict[str, dict[str, int | float]] = {}
    source = "modelUsage"
    source_usage = model_usage
    additional: dict[str, dict[str, int | float]] = {}
    if isinstance(model_usage, dict):
        names = ("inputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "outputTokens")
        for model, values in model_usage.items():
            if isinstance(model, str) and isinstance(values, dict):
                models[model] = _reported_fields(values, names)
                extras = {
                    key: value for key, value in values.items()
                    if key not in names and key.endswith("Tokens") and _number(value) is not None
                }
                if extras:
                    additional[model] = extras
    native_usage = payload.get("usage")
    native_model = payload.get("model")
    if not models and isinstance(native_usage, dict) and isinstance(native_model, str):
        names = (
            "input_tokens", "cache_read_input_tokens",
            "cache_creation_input_tokens", "output_tokens",
        )
        models[native_model] = _reported_fields(native_usage, names)
        source = "usage"
        source_usage = native_usage
        additional_native = {
            key: value for key, value in native_usage.items()
            if key not in names and key.endswith("_tokens") and _number(value) is not None
        }
        if additional_native:
            additional[native_model] = additional_native
    effort = payload.get("effort") if isinstance(payload.get("effort"), str) else None
    session_id = payload.get("session_id") if isinstance(payload.get("session_id"), str) else None
    normalized = {"scope": "invocation", "models": models} if models else None
    normalized_reason = None if models else "runtime returned no modelUsage or usage values"
    if continuity == "resume":
        normalized = None
        normalized_reason = "resume usage scope is not established for this runtime version"
    return {
        "source": source,
        "raw": source_usage,
        "normalized": normalized,
        "normalized_unavailable_reason": normalized_reason,
        "additional_native_classes": additional,
        "reported_models": sorted(models),
        "reported_models_unavailable_reason": (
            None if models else "runtime returned no modelUsage or top-level model identifier"
        ),
        "reported_effort": effort,
        "reported_effort_unavailable_reason": None if effort else "runtime returned no effort field",
        "thread_ids": [session_id] if session_id else [],
        "turn_ids": [],
    }


def runtime_evidence(vendor: str, raw_stdout: bytes, continuity: str) -> dict[str, object]:
    if vendor == "codex":
        return _codex_evidence(raw_stdout, continuity)
    if vendor == "claude":
        return _claude_evidence(raw_stdout, continuity)
    return {
        "source": "native tool return",
        "raw": None,
        "normalized": None,
        "normalized_unavailable_reason": "no extractor for this tool",
        "additional_native_classes": {},
        "reported_models": [],
        "reported_models_unavailable_reason": "no extractor for this tool",
        "reported_effort": None,
        "reported_effort_unavailable_reason": "no extractor for this tool",
        "thread_ids": [],
        "turn_ids": [],
    }


def add_runtime_evidence(attempt: dict[str, object], vendor: str, raw_stdout: bytes,
                         continuity: str, elapsed_seconds: float) -> None:
    attempt["observed"] = runtime_evidence(vendor, raw_stdout, continuity)
    attempt["elapsed_seconds"] = elapsed_seconds


def add_unobserved(attempt: dict[str, object], reason: str) -> None:
    """Complete an attempt that never reached a runtime observation."""
    attempt["observed"] = {
        "source": None, "raw": None, "normalized": None,
        "normalized_unavailable_reason": reason,
        "additional_native_classes": {},
        "reported_models": [], "reported_models_unavailable_reason": reason,
        "reported_effort": None, "reported_effort_unavailable_reason": reason,
        "thread_ids": [], "turn_ids": [],
    }
    attempt["elapsed_seconds"] = None
    attempt["elapsed_seconds_unavailable_reason"] = reason


def _change(work: str) -> dict[str, object]:
    match = re.fullmatch(r"(.+?)#([0-9]+)", work)
    if match:
        return {
            "repository": match.group(1), "issue": int(match.group(2)),
            "unknown_reason": None,
        }
    issue = re.fullmatch(r"issue-([0-9]+)", work, re.IGNORECASE)
    return {
        "repository": None,
        "issue": int(issue.group(1)) if issue else None,
        "unknown_reason": "work identifier did not contain repository#issue",
    }


def _normalized_tokens(vendor: str, observed: dict[str, object]) -> tuple[object, str | None, str]:
    normalized = observed.get("normalized")
    if not isinstance(normalized, dict):
        return None, str(observed.get("normalized_unavailable_reason") or "runtime usage unavailable"), "unknown"
    scope = str(normalized.get("scope") or "unknown")
    if vendor == "codex":
        mapping = {
            "input_tokens": "input", "cached_input_tokens": "cached_input",
            "output_tokens": "output", "reasoning_output_tokens": "reasoning_output",
        }
        tokens = {target: normalized[source] for source, target in mapping.items() if source in normalized}
        return tokens, None, scope
    if vendor == "claude":
        native_models = normalized.get("models")
        models = {}
        mapping = {
            "inputTokens": "input", "cacheReadInputTokens": "cache_read",
            "cacheCreationInputTokens": "cache_creation", "outputTokens": "output",
            "input_tokens": "input", "cache_read_input_tokens": "cache_read",
            "cache_creation_input_tokens": "cache_creation", "output_tokens": "output",
        }
        if isinstance(native_models, dict):
            for model, values in native_models.items():
                if isinstance(values, dict):
                    models[model] = {
                        target: values[source] for source, target in mapping.items() if source in values
                    }
        return {"models": models}, None, scope
    return None, "no normalized token-class extractor for this tool", "unknown"


def usage_record(attempt: dict[str, object], request: dict[str, object], *,
                 completed_at: str, staffing_status: str) -> dict[str, object]:
    observed = attempt.get("observed")
    if not isinstance(observed, dict):
        observed = {}
    requested = request.get("requested")
    if not isinstance(requested, dict):
        requested = {}
    vendor = str(attempt.get("vendor") or requested.get("vendor") or "unknown")
    tokens, tokens_unknown, scope = _normalized_tokens(vendor, observed)
    reported_models = observed.get("reported_models")
    if not isinstance(reported_models, list):
        reported_models = []
    runtime_version_value = attempt.get("runtime_version") or request.get("runtime_version")
    runtime_version = runtime_version_value if isinstance(runtime_version_value, str) else None
    raw_source = attempt.get("stdout") or attempt.get("source_return")
    return {
        "change": _change(str(request.get("work") or "")),
        "dispatch": {
            "id": request.get("dispatch_id"),
            "requested_vendor": requested.get("vendor"),
            "actual_vendor": vendor,
            "stage": request.get("stage"),
            "continuity": requested.get("continuity"),
            "launched_at": request.get("launched_at"),
            "completed_at": completed_at,
            "staffing_status": staffing_status,
        },
        "model": {
            "requested": attempt.get("model") or requested.get("model"),
            "reported": reported_models,
            "reported_unknown_reason": (
                None if reported_models else observed.get("reported_models_unavailable_reason")
            ),
        },
        "tokens": tokens,
        "tokens_unknown_reason": tokens_unknown,
        "additional_native_classes": observed.get("additional_native_classes") or {},
        "scope": scope if scope in {"invocation", "cumulative", "unknown"} else "unknown",
        "source_field": observed.get("source"),
        "raw_source": raw_source,
        "runtime_version": runtime_version,
        "runtime_version_unknown_reason": None if runtime_version else (
            attempt.get("runtime_version_unavailable_reason")
            or request.get("runtime_version_unavailable_reason")
            or "runtime version unavailable"
        ),
    }


def add_usage_record(attempt: dict[str, object], request: dict[str, object], *,
                     completed_at: str, staffing_status: str) -> None:
    attempt["usage"] = usage_record(
        attempt, request, completed_at=completed_at, staffing_status=staffing_status
    )


def _attachment_paths(output: Path, kind: str) -> tuple[Path, Path]:
    identity = uuid.uuid4().hex
    base = sidecar(output, f".attachment.{_slug(kind)}.{identity}")
    return base.with_name(base.name + ".bin"), base.with_name(base.name + ".json")


def attach_file(output: Path, source: Path, kind: str) -> Path:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise RecordError(f"attachment source is not a file: {source}")
    output = output.expanduser().absolute()
    request_path = sidecar(output, ".request.json")
    if not request_path.is_file():
        raise RecordError(f"dispatch request is absent: {request_path}")
    request = json.loads(request_path.read_bytes())
    content_path, metadata_path = _attachment_paths(output, kind)
    content_path.parent.mkdir(parents=True, exist_ok=True)
    write_bytes(content_path, source.read_bytes())
    import hashlib
    write_json(metadata_path, {
        "schema_version": SCHEMA_VERSION,
        "dispatch_id": request["dispatch_id"],
        "dispatch": str(output.expanduser().absolute()),
        "kind": kind,
        "source": str(source),
        "content": str(content_path),
        "sha256": hashlib.sha256(content_path.read_bytes()).hexdigest(),
        "bytes": content_path.stat().st_size,
    })
    return metadata_path


def begin_native(args: argparse.Namespace) -> Path:
    output = resolved_output(args.output, args.work, args.stage)
    require_output_outside_root(output, args.root)
    input_file = getattr(args, "input_file", None)
    input_unavailable_reason = getattr(args, "input_unavailable_reason", None)
    if (input_file is None) == (input_unavailable_reason is None):
        raise RecordError("name exactly one of input file or input unavailable reason")
    if input_unavailable_reason is not None and not input_unavailable_reason.strip():
        raise RecordError("input unavailable reason must be nonempty")
    input_content = input_file.expanduser().resolve().read_bytes() if input_file else None
    output.parent.mkdir(parents=True, exist_ok=True)
    source_names = (
        "vendor", "model", "effort", "classification", "continuity", "permission_boundary"
    )
    setting_sources = {
        name: getattr(args, name + "_source", None) for name in source_names
    }
    missing_sources = [name for name, source in setting_sources.items() if not source or not source.strip()]
    if missing_sources:
        raise RecordError(f"setting sources must be nonempty: {', '.join(missing_sources)}")
    request = request_record(
        dispatch_id=uuid.uuid4().hex, work=args.work, stage=args.stage,
        settings_source=args.settings_source, settings_scope=args.settings_scope,
        vendor=args.vendor, model=args.model,
        effort=args.effort, continuity=args.continuity,
        permission_boundary=args.permission_boundary, root=args.root,
        classification=args.classification, requested_session_id=args.session_id,
        retry_of=args.retry_of,
        holder_session_id=getattr(args, "holder_session_id", None),
        setting_sources=setting_sources,
    )
    recorded_at = request["launched_at"]
    request["recorded_at"] = recorded_at
    launched_at = getattr(args, "launched_at", None)
    launched_at_unavailable_reason = getattr(args, "launched_at_unavailable_reason", None)
    if launched_at is not None and launched_at_unavailable_reason is not None:
        raise RecordError("name at most one of launched at or launched-at unavailable reason")
    if launched_at_unavailable_reason is not None:
        if not launched_at_unavailable_reason.strip():
            raise RecordError("launched-at unavailable reason must be nonempty")
        request["launched_at"] = None
        request["launched_at_unavailable_reason"] = launched_at_unavailable_reason
    else:
        request["launched_at"] = (
            launched_at.astimezone(timezone.utc).isoformat() if launched_at else recorded_at
        )
        request["launched_at_unavailable_reason"] = None
    request["runtime_version"] = args.runtime_version
    request["runtime_version_unavailable_reason"] = (
        None if args.runtime_version else "native dispatcher supplied no runtime version"
    )
    request["revision_before"] = git_revision(args.root) if args.root else None
    request_path = sidecar(output, ".request.json")
    input_path = sidecar(output, ".dispatch.bin")
    run_path = sidecar(output, ".run.json")
    raw_path = sidecar(output, ".native.return.log")
    source_path = sidecar(output, ".source.bin")
    future = [output, request_path, run_path, raw_path, source_path]
    if input_content is not None:
        future.append(input_path)
    if any(path.exists() or path.is_symlink() for path in future):
        raise RecordError(f"refusing existing dispatch output: {output}")
    request["input"] = str(input_path) if input_content is not None else None
    request["input_unavailable_reason"] = input_unavailable_reason
    request["reserved_source_output"] = str(source_path)
    with reserve_bundle(future, output) as streams:
        streams[request_path].write(json_bytes(request))
        streams[request_path].flush()
        if input_content is not None:
            streams[input_path].write(input_content)
            streams[input_path].flush()
        streams.mark_ready()
    return output


def _fill_reservation(path: Path, content: bytes) -> None:
    if not path.is_file() or path.stat().st_size:
        raise RecordError(f"dispatch reservation is absent or already filled: {path}")
    with path.open("r+b") as stream:
        stream.write(content)
        stream.flush()


def finish_native(args: argparse.Namespace) -> Path:
    output = args.output.expanduser().absolute()
    request_path = sidecar(output, ".request.json")
    if not request_path.is_file():
        raise RecordError(f"dispatch request is absent: {request_path}")
    returned = args.return_file.expanduser().resolve().read_bytes()
    raw_path = sidecar(output, ".native.return.log")
    run_path = sidecar(output, ".run.json")
    source_path = sidecar(output, ".source.bin")
    if output.exists() or any(
        not path.is_file() or path.stat().st_size for path in (raw_path, run_path, source_path)
    ):
        raise RecordError(f"refusing completed or colliding dispatch output: {output}")
    _fill_reservation(raw_path, returned)
    succeeded = args.outcome == "success"
    final = (
        args.final_file.expanduser().resolve().read_bytes() if args.final_file else returned
    ) if succeeded else None
    if final is not None:
        _fill_reservation(source_path, final)
    request = json.loads(request_path.read_bytes())
    completed = datetime.now(timezone.utc)
    launched = args.outcome != "unavailable"
    elapsed = getattr(args, "elapsed_seconds", None) if launched else None
    elapsed_reason = getattr(args, "elapsed_unavailable_reason", None)
    if not launched:
        if getattr(args, "elapsed_seconds", None) is not None:
            raise RecordError("an unavailable native attempt cannot report elapsed seconds")
        elapsed_reason = "native outcome was unavailable"
    elif elapsed is None:
        elapsed_reason = elapsed_reason or "native dispatcher supplied no elapsed duration"
    elif not math.isfinite(elapsed) or elapsed < 0:
        raise RecordError("elapsed seconds must be finite and nonnegative")
    attempt = {
        "vendor": args.vendor, "launched": launched, "outcome": args.outcome,
        "source_return": str(raw_path), "elapsed_seconds": elapsed,
        "elapsed_seconds_unavailable_reason": elapsed_reason if elapsed is None else None,
    }
    if launched:
        attempt["observed"] = runtime_evidence(
            args.vendor, returned, request["requested"]["continuity"]
        )
    else:
        add_unobserved(attempt, "native outcome was unavailable; no runtime launched")
    run = {
        "schema_version": SCHEMA_VERSION,
        "dispatch_id": request["dispatch_id"],
        "request": str(request_path),
        "outcome": args.outcome,
        "completed_at": completed.isoformat(),
        "revision_after": git_revision(Path(request["root"])) if request.get("root") else None,
        "attempts": [attempt],
        "result": {
            "source_output": str(source_path) if succeeded else None,
            "source_output_unavailable_reason": None if succeeded else f"native outcome was {args.outcome}",
            "published_output": None,
            "published_output_unavailable_reason": (
                "publication has not succeeded" if succeeded else f"native outcome was {args.outcome}"
            ),
            "assessment": "unassessed",
        },
    }
    add_usage_record(
        attempt, request, completed_at=run["completed_at"],
        staffing_status="qualified" if succeeded else "unfilled",
    )
    if final is not None:
        try:
            publish_output(output, final)
        except OSError as exc:
            run["outcome"] = "error"
            run["error"] = f"could not publish native result: {exc}"
            run["result"]["published_output_unavailable_reason"] = run["error"]
            finalize_reserved_json(run_path, run)
            raise
        run["result"]["published_output"] = str(output)
        run["result"]["published_output_unavailable_reason"] = None
    else:
        source_path.unlink(missing_ok=True)
    try:
        finalize_reserved_json(run_path, run)
    except Exception:
        if final is not None:
            output.unlink(missing_ok=True)
        raise
    return run_path


def _aware_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an ISO 8601 timestamp") from exc
    if parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("must include a UTC offset")
    return parsed


def _nonnegative_seconds(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("must be finite and nonnegative")
    return parsed


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="Retain evidence for a native agent dispatch.")
    commands = cli.add_subparsers(dest="command", required=True)
    begin = commands.add_parser("begin", help="write the immutable launch request")
    begin.add_argument("--work", required=True)
    begin.add_argument("--stage", required=True)
    begin.add_argument("--settings-source", required=True, help="summary source for this request")
    begin.add_argument("--settings-scope", required=True, help="scope governed by the summary source")
    begin.add_argument("--vendor", required=True)
    begin.add_argument("--vendor-source", required=True, help="where this vendor choice came from")
    begin.add_argument("--model", required=True)
    begin.add_argument("--model-source", required=True, help="where this model choice came from")
    begin.add_argument("--effort", required=True)
    begin.add_argument("--effort-source", required=True, help="where this effort choice came from")
    begin.add_argument("--continuity", choices=CONTINUITIES, default="fresh")
    begin.add_argument("--continuity-source", required=True, help="where fresh or resume came from")
    begin.add_argument("--classification", choices=CLASSIFICATIONS)
    begin.add_argument("--classification-source", required=True, help="where the role classification came from")
    begin.add_argument("--session-id")
    begin.add_argument("--retry-of")
    begin.add_argument("--holder-session-id")
    begin.add_argument("--runtime-version")
    begin.add_argument("--permission-boundary", required=True)
    begin.add_argument(
        "--permission-boundary-source", required=True,
        help="where the actual tool and permission boundary came from",
    )
    begin.add_argument("--root", type=Path)
    input_source = begin.add_mutually_exclusive_group(required=True)
    input_source.add_argument("--input-file", type=Path, help="file containing the exact dispatch input")
    input_source.add_argument(
        "--input-unavailable-reason", help="why the exact input was not available; never a paraphrase",
    )
    launched_at = begin.add_mutually_exclusive_group()
    launched_at.add_argument("--launched-at", type=_aware_datetime, help="actual ISO 8601 launch time")
    launched_at.add_argument(
        "--launched-at-unavailable-reason", help="why actual launch time was unavailable",
    )
    begin.add_argument("--output", type=Path)
    finish = commands.add_parser("finish", help="retain the source return and completion")
    finish.add_argument("--output", type=Path, required=True)
    finish.add_argument("--vendor", required=True)
    finish.add_argument("--return-file", type=Path, required=True)
    finish.add_argument("--final-file", type=Path)
    finish.add_argument("--outcome", choices=("success", "error", "unavailable"), required=True)
    elapsed = finish.add_mutually_exclusive_group()
    elapsed.add_argument("--elapsed-seconds", type=_nonnegative_seconds, help="actual runtime duration")
    elapsed.add_argument(
        "--elapsed-unavailable-reason", help="why actual runtime duration was unavailable",
    )
    attach = commands.add_parser("attach", help="copy a product or later assessment")
    attach.add_argument("--output", type=Path, required=True)
    attach.add_argument("--source", type=Path, required=True)
    attach.add_argument("--kind", required=True)
    return cli


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    args = parser().parse_args(argv)
    try:
        if args.command == "begin":
            output = begin_native(args)
            request = json.loads(sidecar(output, ".request.json").read_bytes())
            print(f"dispatch-record: dispatch {request['dispatch_id']} -> {output}")
        elif args.command == "finish":
            print(finish_native(args))
        else:
            print(attach_file(args.output, args.source, args.kind))
        return 0
    except (OSError, UnicodeError, ValueError, RecordError) as exc:
        print(f"dispatch-record: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

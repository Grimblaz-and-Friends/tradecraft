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

SCHEMA_VERSION = 1
CONTINUITIES = ("fresh", "resume")
CLASSIFICATIONS = ("ordinary", "cold", "terminal")


class RecordError(RuntimeError):
    """A dispatch record cannot be created without losing its contract."""


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
        )
    except OSError:
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
    for name, source in (setting_sources or {}).items():
        if not name.strip() or not source.strip():
            raise RecordError("setting source names and values must be nonempty")
    when = now or datetime.now(timezone.utc)
    return {
        "schema_version": SCHEMA_VERSION,
        "dispatch_id": dispatch_id,
        "work": work,
        "stage": stage,
        "settings_source": settings_source,
        "settings_scope": settings_scope,
        "retry_of": retry_of,
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


def _json_lines(raw: bytes) -> list[dict[str, object]]:
    try:
        values = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    except (UnicodeError, ValueError):
        return []
    return values if all(isinstance(item, dict) for item in values) else []


def _number(value: object) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _reported_fields(raw: dict[str, object], names: tuple[str, ...]) -> dict[str, int | float]:
    return {name: value for name in names if (value := _number(raw.get(name))) is not None}


def _codex_evidence(raw: bytes, continuity: str) -> dict[str, object]:
    events = _json_lines(raw)
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
    return {
        "source": "codex JSONL turn.completed.usage",
        "raw": usage,
        "normalized": normalized,
        "normalized_unavailable_reason": reason,
        "reported_models": observed_models,
        "reported_models_unavailable_reason": None if observed_models else "runtime returned no model identifier",
        "reported_effort": None,
        "reported_effort_unavailable_reason": "runtime returned no effort field",
        "thread_ids": thread_ids,
        "turn_ids": turn_ids,
        "runtime_cost": None,
        "runtime_cost_unavailable_reason": "Codex JSONL returned no monetary field",
        "runtime_cost_scope_unavailable_reason": "Codex JSONL returned no monetary field",
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
            "reported_models": [],
            "reported_models_unavailable_reason": "runtime returned no valid JSON result",
            "reported_effort": None,
            "reported_effort_unavailable_reason": "runtime returned no valid JSON result",
            "thread_ids": [],
            "turn_ids": [],
            "runtime_cost": None,
            "runtime_cost_unavailable_reason": "runtime returned no valid JSON result",
            "runtime_cost_scope_unavailable_reason": "runtime returned no valid JSON result",
        }
    model_usage = payload.get("modelUsage")
    models: dict[str, dict[str, int | float]] = {}
    if isinstance(model_usage, dict):
        names = ("inputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "outputTokens")
        for model, values in model_usage.items():
            if isinstance(model, str) and isinstance(values, dict):
                models[model] = _reported_fields(values, names)
    cost = _number(payload.get("total_cost_usd"))
    effort = payload.get("effort") if isinstance(payload.get("effort"), str) else None
    session_id = payload.get("session_id") if isinstance(payload.get("session_id"), str) else None
    normalized = {"scope": "invocation", "models": models} if models else None
    normalized_reason = None if models else "runtime returned no modelUsage values"
    cost_scope = "invocation"
    cost_scope_reason = None
    if continuity == "resume":
        normalized = None
        normalized_reason = "resume usage scope is not established for this runtime version"
        cost_scope = "unestablished"
        cost_scope_reason = "resume cost scope is not established for this runtime version"
    return {
        "source": "claude JSON result.modelUsage",
        "raw": model_usage,
        "normalized": normalized,
        "normalized_unavailable_reason": normalized_reason,
        "reported_models": sorted(models),
        "reported_models_unavailable_reason": None if models else "runtime returned no modelUsage identifiers",
        "reported_effort": effort,
        "reported_effort_unavailable_reason": None if effort else "runtime returned no effort field",
        "thread_ids": [session_id] if session_id else [],
        "turn_ids": [],
        "runtime_cost": {
            "currency": "USD", "amount": cost, "source": "total_cost_usd", "scope": cost_scope,
        } if cost is not None else None,
        "runtime_cost_unavailable_reason": None if cost is not None else "runtime returned no total_cost_usd",
        "runtime_cost_scope_unavailable_reason": cost_scope_reason,
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
        "reported_models": [],
        "reported_models_unavailable_reason": "no extractor for this tool",
        "reported_effort": None,
        "reported_effort_unavailable_reason": "no extractor for this tool",
        "thread_ids": [],
        "turn_ids": [],
        "runtime_cost": None,
        "runtime_cost_unavailable_reason": "no extractor for this tool",
        "runtime_cost_scope_unavailable_reason": "no extractor for this tool",
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
        "reported_models": [], "reported_models_unavailable_reason": reason,
        "reported_effort": None, "reported_effort_unavailable_reason": reason,
        "thread_ids": [], "turn_ids": [],
        "runtime_cost": None, "runtime_cost_unavailable_reason": reason,
        "runtime_cost_scope_unavailable_reason": reason,
    }
    attempt["elapsed_seconds"] = None
    attempt["elapsed_seconds_unavailable_reason"] = reason


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
    input_content = args.input_file.expanduser().resolve().read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    request = request_record(
        dispatch_id=uuid.uuid4().hex, work=args.work, stage=args.stage,
        settings_source=args.settings_source, settings_scope=args.settings_scope,
        vendor=args.vendor, model=args.model,
        effort=args.effort, continuity=args.continuity,
        permission_boundary=args.permission_boundary, root=args.root,
        classification=args.classification, requested_session_id=args.session_id,
        retry_of=args.retry_of,
        setting_sources={
            name: args.settings_source for name in (
                "vendor", "model", "effort", "classification", "continuity", "permission_boundary"
            )
        },
    )
    request["runtime_version"] = args.runtime_version
    request["runtime_version_unavailable_reason"] = (
        None if args.runtime_version else "native dispatcher supplied no runtime version"
    )
    request["revision_before"] = git_revision(args.root) if args.root else None
    request_path = sidecar(output, ".request.json")
    input_path = sidecar(output, ".dispatch.bin")
    future = (output, request_path, input_path, sidecar(output, ".run.json"),
              sidecar(output, ".native.return.log"))
    if any(path.exists() or path.is_symlink() for path in future):
        raise RecordError(f"refusing existing dispatch output: {output}")
    request["input"] = str(input_path)
    write_json(request_path, request)
    write_bytes(input_path, input_content)
    return output


def finish_native(args: argparse.Namespace) -> Path:
    output = args.output.expanduser().absolute()
    request_path = sidecar(output, ".request.json")
    if not request_path.is_file():
        raise RecordError(f"dispatch request is absent: {request_path}")
    returned = args.return_file.expanduser().resolve().read_bytes()
    raw_path = sidecar(output, ".native.return.log")
    run_path = sidecar(output, ".run.json")
    source_path = sidecar(output, ".source.bin")
    if raw_path.exists() or run_path.exists() or source_path.exists() or output.exists():
        raise RecordError(f"refusing completed or colliding dispatch output: {output}")
    write_bytes(raw_path, returned)
    succeeded = args.outcome == "success"
    final = (
        args.final_file.expanduser().resolve().read_bytes() if args.final_file else returned
    ) if succeeded else None
    if final is not None:
        write_bytes(source_path, final)
    request = json.loads(request_path.read_bytes())
    evidence = runtime_evidence(args.vendor, returned, request["requested"]["continuity"])
    completed = datetime.now(timezone.utc)
    try:
        launched = datetime.fromisoformat(request["launched_at"])
        elapsed = max(0.0, (completed - launched).total_seconds())
    except (KeyError, TypeError, ValueError):
        elapsed = None
    launched = args.outcome != "unavailable"
    write_json(run_path, {
        "schema_version": SCHEMA_VERSION,
        "dispatch_id": request["dispatch_id"],
        "request": str(request_path),
        "outcome": args.outcome,
        "completed_at": completed.isoformat(),
        "revision_after": git_revision(Path(request["root"])) if request.get("root") else None,
        "attempts": [{
            "vendor": args.vendor, "launched": launched, "outcome": args.outcome,
            "observed": evidence, "source_return": str(raw_path),
            "elapsed_seconds": elapsed if launched else None,
            "elapsed_seconds_unavailable_reason": None if launched else "native outcome was unavailable",
        }],
        "result": {
            "source_output": str(source_path) if succeeded else None,
            "source_output_unavailable_reason": None if succeeded else f"native outcome was {args.outcome}",
            "published_output": str(output) if succeeded else None,
            "published_output_unavailable_reason": None if succeeded else f"native outcome was {args.outcome}",
            "assessment": "unassessed",
        },
    })
    if final is not None:
        publish_output(output, final)
    return run_path


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="Retain evidence for a native agent dispatch.")
    commands = cli.add_subparsers(dest="command", required=True)
    begin = commands.add_parser("begin", help="write the immutable launch request")
    begin.add_argument("--work", required=True)
    begin.add_argument("--stage", required=True)
    begin.add_argument("--settings-source", required=True)
    begin.add_argument("--settings-scope", required=True)
    begin.add_argument("--vendor", required=True)
    begin.add_argument("--model", required=True)
    begin.add_argument("--effort", required=True)
    begin.add_argument("--continuity", choices=CONTINUITIES, default="fresh")
    begin.add_argument("--classification", choices=CLASSIFICATIONS)
    begin.add_argument("--session-id")
    begin.add_argument("--retry-of")
    begin.add_argument("--runtime-version")
    begin.add_argument("--permission-boundary", required=True)
    begin.add_argument("--root", type=Path)
    begin.add_argument("--input-file", type=Path, required=True)
    begin.add_argument("--output", type=Path)
    finish = commands.add_parser("finish", help="retain the source return and completion")
    finish.add_argument("--output", type=Path, required=True)
    finish.add_argument("--vendor", required=True)
    finish.add_argument("--return-file", type=Path, required=True)
    finish.add_argument("--final-file", type=Path)
    finish.add_argument("--outcome", choices=("success", "error", "unavailable"), required=True)
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

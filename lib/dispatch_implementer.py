#!/usr/bin/env python3
"""Launch or resume an implementer and retain the dispatch evidence.

Usage: python <plugin-root>/lib/dispatch_implementer.py --dispatch FILE --root DIR
       --work ISSUE --stage NAME --settings-source SOURCE --settings-scope SCOPE
       [--resume SESSION_ID]

Every invocation is a separate record. ``--resume`` is explicit; ``--last`` and
``--ephemeral`` are deliberately absent because either can defeat continuity.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid

import dispatch_record as records
from seat_process import run_process
from vendor_cli import CliError, resolve_command
from winio import utf8_stdio

# Ruled for #758: Astra 6 authors artifacts and Sol 6 builds at xhigh.
# Claude Opus 5.5 at high is the switch profile; authoring remains interim.
PROFILES = {
    "artifact_author": {
        "codex": ("gpt-6-astra", "xhigh"),
        "claude": ("claude-opus-5-5", "high"),
    },
    "implementer": {
        "codex": ("gpt-6-sol", "xhigh"),
        "claude": ("claude-opus-5-5", "high"),
    },
}
DEFAULT_MODEL = PROFILES["implementer"]["codex"][0]
DEFAULT_EFFORT = "xhigh"
SESSION = re.compile(r"(?im)^session id:\s*([0-9a-f]{8}-[0-9a-f-]{27,})\s*$")


class ImplementerError(RuntimeError):
    """The implementer launch cannot produce trustworthy continuation evidence."""


def read_machine_vendor(setting_path: Path | None = None) -> tuple[str, str]:
    """Read the fresh implementer vendor once, including its reportable source."""
    path = setting_path or Path.home() / ".tradecraft" / "implementer-vendor"
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return "codex", f"absent machine file: {path}"
    except OSError as exc:
        raise ImplementerError(f"cannot read implementer vendor setting {path}: {exc}") from exc
    try:
        vendor = content.decode("utf-8").strip()
    except UnicodeError as exc:
        raise ImplementerError(f"invalid UTF-8 in implementer vendor setting {path}") from exc
    if vendor not in {"codex", "claude"}:
        raise ImplementerError(f"implementer vendor setting {path} must contain codex or claude")
    return vendor, f"machine file {path}: {vendor}"


def build_command(args: argparse.Namespace, executable: list[str], last_message: Path) -> list[str]:
    if args.vendor == "claude":
        command = [
            *executable, "-p", "--model", args.model, "--effort", args.effort,
            "--output-format", "json", "--permission-mode", "auto",
            "--setting-sources", "user", "--plugin-dir",
            str(Path(__file__).resolve().parent.parent),
        ]
        if args.resume:
            command.extend(("--resume", args.resume))
        elif args.session_id:
            command.extend(("--session-id", args.session_id))
        return command
    command = [
        *executable, "exec", "--approve-for-me", "--json", "--color", "never",
        "--model", args.model, "-c", f'model_reasoning_effort="{args.effort}"',
        "--cd", str(args.root.resolve()), "--output-last-message", str(last_message),
    ]
    if args.resume:
        command.extend(("resume", args.resume, "-"))
    else:
        command.append("-")
    return command


def _claude_result(raw: bytes) -> tuple[bool, bytes, str | None, str]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        return False, b"", None, "claude returned invalid JSON"
    if not isinstance(value, dict) or value.get("type") != "result":
        return False, b"", None, "claude returned no final result"
    session = value.get("session_id")
    if not isinstance(session, str) or not re.fullmatch(r"[0-9a-f-]{36}", session, re.I):
        session = None
    if value.get("permission_denials"):
        return False, b"", session, "Claude reported a tool permission denial; see its stdout log"
    if value.get("is_error") is not False or value.get("subtype") != "success":
        return False, b"", session, str(value.get("result") or "claude reported an error")
    message = value.get("result")
    if not isinstance(message, str):
        return False, b"", session, "claude result lacks final text"
    return True, message.encode("utf-8"), session, ""


def _handover_phase(path: Path, session: str, phase: str) -> None:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeError, ValueError) as exc:
        raise ImplementerError(f"cannot read handover reservation: {path}") from exc
    if not isinstance(value, dict) or value.get("replacement_session") != session:
        raise ImplementerError(f"handover reservation does not match selected session: {path}")
    value["phase"] = phase
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".handover-", delete=False) as stream:
        staged = Path(stream.name)
        stream.write(records.json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def _thread_id(events: list[dict[str, object]], stderr: bytes) -> tuple[str | None, str]:
    ids = [event.get("thread_id") for event in events
           if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str)]
    if ids:
        return ids[-1], "codex JSONL thread.started.thread_id"
    match = SESSION.search(stderr.decode("utf-8", errors="replace"))
    return (match.group(1), "codex stderr session id header") if match else (None, "")


def run_implementer(args: argparse.Namespace) -> int:
    role = "artifact_author" if args.stage == "artifact" else "implementer"
    machine_vendor, machine_source = read_machine_vendor()
    if args.vendor is None:
        if args.resume:
            raise ImplementerError("direct resume requires --vendor from the recorded session")
        if args.vendor_source:
            raise ImplementerError("--vendor-source requires --vendor")
        args.vendor, args.vendor_source = machine_vendor, machine_source
    elif not args.vendor_source:
        args.vendor_source = f"explicit --vendor {args.vendor}"
    if args.vendor not in ("codex", "claude"):
        raise ImplementerError(f"unknown implementer vendor: {args.vendor}")
    model_defaulted = args.model is None
    effort_defaulted = args.effort is None
    if args.model is not None and not args.model.strip():
        raise ImplementerError("--model must be nonempty when supplied")
    if args.effort is not None and not args.effort.strip():
        raise ImplementerError("--effort must be nonempty when supplied")
    selected_path = getattr(args, args.vendor)
    unavailable_reason = getattr(args, f"{args.vendor}_unavailable_reason")
    if selected_path and unavailable_reason:
        raise ImplementerError(f"{args.vendor} cannot be both explicit and unavailable")
    explicit_executable = resolve_command(args.vendor, selected_path) if selected_path else None
    profile_model, profile_effort = PROFILES[role][args.vendor]
    args.model = profile_model if model_defaulted else args.model
    args.effort = profile_effort if effort_defaulted else args.effort
    root = args.root.expanduser().resolve()
    dispatch = args.dispatch.expanduser().resolve()
    if not root.is_dir():
        raise ImplementerError(f"root is not a directory: {root}")
    prompt = dispatch.read_bytes()
    if not prompt.decode("utf-8").strip():
        raise ImplementerError(f"dispatch is empty: {dispatch}")
    context = (args.context.read_bytes() if args.context else b"")
    if context:
        context.decode("utf-8")
    effective_prompt = context + b"\n\n" + prompt if context else prompt
    if args.resume and not args.resume.strip():
        raise ImplementerError("--resume must be a nonempty explicit session id")
    if args.resume and args.session_id:
        raise ImplementerError("--session-id is for a fresh session")
    if args.session_id and args.vendor != "claude":
        raise ImplementerError("--session-id is only supported for Claude")
    if args.handover_state and (not args.handover_from or not (args.session_id or args.resume)):
        raise ImplementerError("handover requires a predecessor bundle and replacement session")
    if (args.handover_from and not args.handover_state
            and not (args.vendor == "claude" and unavailable_reason is not None
                     and not args.resume and not args.session_id)):
        raise ImplementerError("handover without a reservation requires an unavailable Claude attempt")
    if args.holder_session_id and args.resume == args.holder_session_id:
        raise ImplementerError("a builder session cannot also identify the holder session")
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        raise ImplementerError("--timeout-seconds must be finite and positive")
    output = records.resolved_output(args.output, args.work, args.stage)
    records.require_output_outside_root(output, root)
    args.output = output
    request_path = records.sidecar(output, ".request.json")
    record_path = records.sidecar(output, ".run.json")
    input_path = records.sidecar(output, ".dispatch.bin")
    source_path = records.sidecar(output, ".source.bin")
    stdout_path = records.sidecar(output, f".{args.vendor}.stdout.log")
    stderr_path = records.sidecar(output, f".{args.vendor}.stderr.log")
    context_path = records.sidecar(output, ".context.bin") if context else None
    destinations = [
        output, request_path, record_path, input_path, source_path, stdout_path, stderr_path
    ]
    if context_path:
        destinations.append(context_path)
    for path in destinations:
        if path.resolve() == dispatch:
            raise ImplementerError(f"output destination is also the dispatch input: {path}")
        if path.exists() or path.is_symlink():
            raise ImplementerError(f"refusing existing output: {path}")
    output.parent.mkdir(parents=True, exist_ok=True)
    continuity = "resume" if args.resume else "fresh"
    with records.reserve_bundle(destinations, output) as streams:
        with tempfile.TemporaryDirectory(prefix="tradecraft-implementer-") as temporary:
            last_message = Path(temporary) / "last.txt"
            executable = explicit_executable
            if executable is None and unavailable_reason is None:
                try:
                    executable = resolve_command(args.vendor, None)
                except CliError as exc:
                    unavailable_reason = str(exc)
            command = (
                build_command(args, executable, last_message)
                if executable is not None else None
            )
            request = records.request_record(
                dispatch_id=uuid.uuid4().hex, work=args.work, stage=args.stage,
                settings_source=args.settings_source, settings_scope=args.settings_scope,
                vendor=args.vendor, model=args.model,
                effort=args.effort, continuity=continuity,
                permission_boundary=(
                    "workspace-write with automatic approval review (--approve-for-me)"
                    if args.vendor == "codex" else
                    "Claude auto permission mode; user settings only; no OS write sandbox"
                ),
                root=root, requested_session_id=args.resume, command=command,
                retry_of=args.retry_of,
                holder_session_id=args.holder_session_id,
                setting_sources={
                    "vendor": args.vendor_source,
                    "model": (args.model_source or (
                        "dispatch_implementer default" if model_defaulted else args.settings_source
                    )),
                    "effort": (args.effort_source or (
                        "dispatch_implementer default" if effort_defaulted else args.settings_source
                    )),
                    "continuity": f"launcher route ({continuity})",
                    "permission_boundary": "dispatch_implementer route",
                },
            )
            request["implementer_role"] = role
            request["lineage_branch"] = args.lineage_branch
            request["lineage_pull_request"] = args.lineage_pull_request
            request["context"] = (
                {"path": str(context_path), "sha256": hashlib.sha256(context).hexdigest()}
                if context_path else None
            )
            request["effective_input_sha256"] = hashlib.sha256(effective_prompt).hexdigest()
            if args.handover_state:
                request["handover"] = {
                    "state": str(args.handover_state), "from_bundle": args.handover_from,
                    "to_vendor": args.vendor, "replacement_session": args.session_id or args.resume,
                    "phase": "fresh" if args.session_id else "resume",
                }
            elif args.handover_from and unavailable_reason and args.vendor == "claude":
                request["handover"] = {
                    "from_bundle": args.handover_from, "to_vendor": "claude",
                    "replacement_session": None, "phase": "unavailable",
                }
            request["runtime_version"] = (
                records.runtime_version(executable) if executable is not None else None
            )
            request["runtime_version_unavailable_reason"] = (
                unavailable_reason if executable is None else
                None if request["runtime_version"] else "runtime version command returned no value"
            )
            request["revision_before"] = records.git_revision(root)
            request["input"] = str(input_path)
            streams[request_path].write(records.json_bytes(request))
            streams[request_path].flush()
            streams[input_path].write(prompt)
            streams[input_path].flush()
            if context_path:
                streams[context_path].write(context)
                streams[context_path].flush()
            streams.mark_ready()
            print(f"implementer: dispatch {request['dispatch_id']} -> {output}")
            attempt: dict[str, object] = {
                "vendor": args.vendor, "launched": False, "exit_code": None,
                "outcome": "error", "reason": "",
                "stdout": str(stdout_path), "stderr": str(stderr_path),
            }
            record: dict[str, object] = {
                "schema_version": records.SCHEMA_VERSION,
                "dispatch_id": request["dispatch_id"], "request": str(request_path),
                "actual_vendor": args.vendor, "attempts": [attempt],
                "result": {"source_output": None,
                           "source_output_unavailable_reason": "no completed final source return",
                           "published_output": None,
                           "published_output_unavailable_reason": "no completed final source return",
                           "assessment": "unassessed"},
            }
            if "handover" in request:
                record["handover"] = request["handover"]
            if unavailable_reason is not None:
                attempt.update(outcome="unavailable", reason=unavailable_reason)
                records.add_unobserved(attempt, unavailable_reason)
                record["outcome"] = "unavailable"
                record["completed_at"] = datetime.now(timezone.utc).isoformat()
                record["revision_after"] = records.git_revision(root)
                records.add_usage_record(
                    attempt, request, completed_at=record["completed_at"],
                    staffing_status="unfilled",
                )
                record_stream = streams.streams.pop(record_path)
                record_stream.close()
                for stream in streams.values():
                    stream.close()
                streams.streams.clear()
                records.finalize_reserved_json(record_path, record)
                print(
                    f"implementer: {args.vendor} (source {args.vendor_source}) unavailable: "
                    f"{unavailable_reason}", file=sys.stderr,
                )
                return 1
            verdict: bytes | None = None
            source_ready = False
            publication_error: OSError | None = None
            published = False
            return_code = 1
            started = time.monotonic()
            try:
                try:
                    if args.handover_state and args.session_id:
                        _handover_phase(args.handover_state, args.session_id, "running")
                    result = run_process(command, input=effective_prompt, cwd=root, timeout=args.timeout_seconds)
                except subprocess.TimeoutExpired as exc:
                    result = subprocess.CompletedProcess(command, -1, exc.stdout or b"", exc.stderr or b"")
                    reason = f"{args.vendor} timed out after {args.timeout_seconds:g}s"
                    attempt["launched"] = True
                except OSError as exc:
                    result = subprocess.CompletedProcess(command, -1, b"", str(exc).encode("utf-8"))
                    reason = f"cannot launch {args.vendor}: {exc}"
                    record["error"] = reason
                else:
                    reason = ""
                    attempt["launched"] = True
                elapsed = time.monotonic() - started
                attempt["exit_code"] = result.returncode
                for path, raw, name in (
                    (stdout_path, result.stdout, "stdout"), (stderr_path, result.stderr, "stderr")
                ):
                    content, encoding = records.log_bytes(raw)
                    streams[path].write(content)
                    streams[path].flush()
                    attempt[name + "_encoding"] = encoding
                if args.vendor == "claude":
                    complete, message, session_id, failure_reason = _claude_result(result.stdout)
                    session_source = "claude JSON result.session_id" if session_id else ""
                    if result.returncode != 0:
                        complete = False
                        failure_reason = f"claude exited {result.returncode}: {failure_reason}"
                else:
                    stream = records.codex_stream_result(result.stdout)
                    events = list(stream.events)
                    if stream.valid and stream.completed and not stream.failed_events:
                        # Completion is owned by the stream; process status remains evidence.
                        reason = ""
                    session_id, session_source = _thread_id(events, result.stderr)
                    message = last_message.read_bytes() if last_message.is_file() else b""
                    if not message.strip() and stream.final_message is not None:
                        message = stream.final_message.encode("utf-8")
                    complete = stream.valid and stream.completed and not stream.failed_events
                    if not stream.valid:
                        failure_reason = "codex returned invalid JSONL"
                    elif stream.failed_events:
                        failure_reason = "codex stream reported turn.failed"
                    elif not stream.completed:
                        failure_reason = "codex stream returned no turn.completed"
                    else:
                        failure_reason = f"codex turn could not be accepted (exit {result.returncode})"
                if args.holder_session_id and session_id == args.holder_session_id:
                    reason = "runtime returned the holder session as the builder session"
                    session_id = None
                    session_source = ""
                if attempt["launched"]:
                    records.add_runtime_evidence(attempt, args.vendor, result.stdout, continuity, elapsed)
                    if args.vendor == "claude":
                        try:
                            native = json.loads(result.stdout.decode("utf-8"))
                        except (UnicodeError, ValueError):
                            native = None
                        if isinstance(native, dict):
                            attempt["permission_denials"] = native.get("permission_denials")
                            attempt["model_usage"] = native.get("modelUsage")
                            attempt["native_cost"] = native.get("total_cost_usd")
                else:
                    records.add_unobserved(attempt, reason)
                attempt["observed"]["session_id"] = session_id
                attempt["observed"]["session_id_source"] = session_source or None
                if args.resume and session_id and session_id != args.resume:
                    reason = f"returned session id {session_id} does not match requested resume {args.resume}"
                if args.session_id and session_id and session_id != args.session_id:
                    reason = f"returned session id {session_id} does not match reserved session {args.session_id}"
                if complete and message.strip() and not reason:
                    verdict = message.replace(b"\r\n", b"\n")
                    if session_id:
                        attempt.update(outcome="success", reason="")
                        record["outcome"] = "success"
                        return_code = 0
                    else:
                        attempt.update(
                            outcome="success_uncontinuable",
                            reason=f"{args.vendor} completed but returned no session identity; this turn cannot be resumed",
                        )
                        record["outcome"] = "success_uncontinuable"
                elif complete and not message.strip() and not reason:
                    attempt.update(
                        outcome="completed_no_output",
                        reason="turn completed without a final message",
                    )
                    record["outcome"] = "completed_no_output"
                else:
                    attempt.update(
                        outcome="error",
                        reason=reason or failure_reason,
                    )
                    record["outcome"] = "error"
                if verdict is not None:
                    streams[source_path].write(verdict)
                    streams[source_path].flush()
                    source_ready = True
                    record["result"]["source_output"] = str(source_path)
                    record["result"]["source_output_unavailable_reason"] = None
            finally:
                record.setdefault("outcome", "error")
                if attempt["outcome"] == "error" and not attempt["reason"]:
                    attempt["reason"] = str(record.get("error") or "implementer did not complete")
                if "observed" not in attempt:
                    records.add_unobserved(attempt, attempt["reason"])
                record["completed_at"] = datetime.now(timezone.utc).isoformat()
                record["revision_after"] = records.git_revision(root)
                records.add_usage_record(
                    attempt, request, completed_at=record["completed_at"],
                    staffing_status=(
                        "qualified" if record["outcome"] in {
                            "success", "success_uncontinuable", "completed_no_output",
                        }
                        else "unfilled"
                    ),
                )
                record_stream = streams.streams.pop(record_path)
                record_stream.close()
                for stream in streams.values():
                    stream.close()
                streams.streams.clear()
                if source_ready:
                    try:
                        records.publish_output(output, verdict)
                    except OSError as exc:
                        publication_error = exc
                        record["outcome"] = "error"
                        record["error"] = f"could not publish implementer result: {exc}"
                        record["result"]["published_output_unavailable_reason"] = record["error"]
                        return_code = 1
                    else:
                        published = True
                        record["result"]["published_output"] = str(output)
                        record["result"]["published_output_unavailable_reason"] = None
                try:
                    records.finalize_reserved_json(record_path, record)
                except Exception:
                    if published:
                        output.unlink(missing_ok=True)
                    raise
                if args.handover_state and args.session_id:
                    _handover_phase(
                        args.handover_state, args.session_id,
                        "completed" if return_code == 0 and published else "unresolved",
                    )
            if publication_error is not None:
                raise publication_error
            if source_ready:
                session_note = attempt["observed"].get("session_id") or "unavailable"
                print(f"implementer: {args.vendor} ({args.model}, {args.effort}; source {request['requested']['sources']['vendor']}) session {session_note} -> {output}")
            else:
                print(f"implementer: {attempt['reason']}", file=sys.stderr)
            return return_code


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        description="Run a recorded Codex or Claude implementer turn; resume an explicit session id.",
        epilog=(
            "A fresh direct launch reads ~/.tradecraft/implementer-vendor unless --vendor is "
            "supplied; a named resume requires --vendor from its recorded session. Codex uses "
            "--approve-for-me and JSONL; Claude uses auto mode and a JSON result. Neither route "
            "uses --ephemeral, --last, a read-only sandbox, or vendor fallback. Outputs default "
            "to the machine-local .tradecraft dispatch store and must be new. A successful turn "
            "without a returned session id publishes its result but exits nonzero because it "
            "cannot be continued."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    cli.add_argument("--dispatch", type=Path, required=True)
    cli.add_argument("--root", type=Path, required=True)
    cli.add_argument("--work", required=True)
    cli.add_argument("--stage", required=True)
    cli.add_argument("--settings-source", required=True)
    cli.add_argument("--settings-scope", required=True)
    cli.add_argument("--retry-of", help="dispatch id of an earlier whole-invocation retry")
    cli.add_argument("--holder-session-id", help="holding session that must remain distinct")
    cli.add_argument("--output", type=Path)
    cli.add_argument("--resume")
    cli.add_argument("--session-id", help="reserved identity for a fresh Claude handover")
    cli.add_argument("--vendor", choices=("codex", "claude"),
                     help="explicit vendor; a fresh direct launch otherwise reads the machine file")
    cli.add_argument("--vendor-source", help="source of the selected implementer vendor")
    cli.add_argument("--context", type=Path, help="separate launcher context, retained beside dispatch bytes")
    cli.add_argument("--handover-state", type=Path)
    cli.add_argument("--handover-from", help="predecessor bundle for a recorded handover")
    cli.add_argument("--lineage-branch", help="registered branch carrying this lineage")
    cli.add_argument("--lineage-pull-request", type=int, help="implementing pull request")
    cli.add_argument("--model", help=f"requested model (default: {DEFAULT_MODEL})")
    cli.add_argument("--effort", help=f"requested effort (default: {DEFAULT_EFFORT})")
    cli.add_argument("--model-source", help="source of the explicitly selected model")
    cli.add_argument("--effort-source", help="source of the explicitly selected effort")
    cli.add_argument("--codex", help="explicit Codex CLI executable")
    cli.add_argument("--claude", help="explicit Claude CLI executable")
    cli.add_argument("--codex-unavailable-reason",
                     help="refuse without rediscovering a missing Codex executable")
    cli.add_argument("--claude-unavailable-reason",
                     help="refuse without rediscovering a missing Claude executable")
    cli.add_argument("--timeout-seconds", type=float, default=3600)
    return cli


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    try:
        return run_implementer(parser().parse_args(argv))
    except (OSError, UnicodeError, ValueError, CliError, records.RecordError, ImplementerError) as exc:
        print(f"implementer: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

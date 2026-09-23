#!/usr/bin/env python3
"""Launch or resume a Codex implementer and retain the dispatch evidence.

Usage: python <plugin-root>/lib/dispatch_implementer.py --dispatch FILE --root DIR
       --work ISSUE --stage NAME --settings-source SOURCE --settings-scope SCOPE
       [--resume SESSION_ID]

Every invocation is a separate record. ``--resume`` is explicit; ``--last`` and
``--ephemeral`` are deliberately absent because either can defeat continuity.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import math
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

# gpt-5.6-sol: preferred blind over gpt-6-astra and gpt-5.6-terra on artifact
# authorship, and separated from neither on the owner's code-task pilot [D-645].
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_EFFORT = "xhigh"
SESSION = re.compile(r"(?im)^session id:\s*([0-9a-f]{8}-[0-9a-f-]{27,})\s*$")


class ImplementerError(RuntimeError):
    """The implementer launch cannot produce trustworthy continuation evidence."""


def build_command(args: argparse.Namespace, executable: list[str], last_message: Path) -> list[str]:
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


def _thread_id(events: list[dict[str, object]], stderr: bytes) -> tuple[str | None, str]:
    ids = [event.get("thread_id") for event in events
           if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str)]
    if ids:
        return ids[-1], "codex JSONL thread.started.thread_id"
    match = SESSION.search(stderr.decode("utf-8", errors="replace"))
    return (match.group(1), "codex stderr session id header") if match else (None, "")


def run_implementer(args: argparse.Namespace) -> int:
    model_defaulted = args.model is None
    effort_defaulted = args.effort is None
    if args.model is not None and not args.model.strip():
        raise ImplementerError("--model must be nonempty when supplied")
    if args.effort is not None and not args.effort.strip():
        raise ImplementerError("--effort must be nonempty when supplied")
    if args.codex and args.codex_unavailable_reason:
        raise ImplementerError("Codex cannot be both explicit and unavailable")
    if args.codex_unavailable_reason:
        raise ImplementerError(args.codex_unavailable_reason)
    args.model = DEFAULT_MODEL if model_defaulted else args.model
    args.effort = DEFAULT_EFFORT if effort_defaulted else args.effort
    root = args.root.expanduser().resolve()
    dispatch = args.dispatch.expanduser().resolve()
    if not root.is_dir():
        raise ImplementerError(f"root is not a directory: {root}")
    prompt = dispatch.read_bytes()
    if not prompt.decode("utf-8").strip():
        raise ImplementerError(f"dispatch is empty: {dispatch}")
    if args.resume and not args.resume.strip():
        raise ImplementerError("--resume must be a nonempty explicit session id")
    if args.holder_session_id and args.resume == args.holder_session_id:
        raise ImplementerError("a builder session cannot also identify the holder session")
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        raise ImplementerError("--timeout-seconds must be finite and positive")
    executable = resolve_command("codex", args.codex)
    output = records.resolved_output(args.output, args.work, args.stage)
    records.require_output_outside_root(output, root)
    args.output = output
    request_path = records.sidecar(output, ".request.json")
    record_path = records.sidecar(output, ".run.json")
    input_path = records.sidecar(output, ".dispatch.bin")
    source_path = records.sidecar(output, ".source.bin")
    stdout_path = records.sidecar(output, ".codex.stdout.log")
    stderr_path = records.sidecar(output, ".codex.stderr.log")
    destinations = [
        output, request_path, record_path, input_path, source_path, stdout_path, stderr_path
    ]
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
            command = build_command(args, executable, last_message)
            request = records.request_record(
                dispatch_id=uuid.uuid4().hex, work=args.work, stage=args.stage,
                settings_source=args.settings_source, settings_scope=args.settings_scope,
                vendor="codex", model=args.model,
                effort=args.effort, continuity=continuity,
                permission_boundary="workspace-write with automatic approval review (--approve-for-me)",
                root=root, requested_session_id=args.resume, command=command,
                retry_of=args.retry_of,
                holder_session_id=args.holder_session_id,
                setting_sources={
                    "vendor": "dispatch_implementer route",
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
            request["runtime_version"] = records.runtime_version(executable)
            request["runtime_version_unavailable_reason"] = (
                None if request["runtime_version"] else "runtime version command returned no value"
            )
            request["revision_before"] = records.git_revision(root)
            request["input"] = str(input_path)
            streams[request_path].write(records.json_bytes(request))
            streams[request_path].flush()
            streams[input_path].write(prompt)
            streams[input_path].flush()
            streams.mark_ready()
            print(f"implementer: dispatch {request['dispatch_id']} -> {output}")
            attempt: dict[str, object] = {
                "vendor": "codex", "launched": False, "exit_code": None,
                "outcome": "error", "reason": "",
                "stdout": str(stdout_path), "stderr": str(stderr_path),
            }
            record: dict[str, object] = {
                "schema_version": records.SCHEMA_VERSION,
                "dispatch_id": request["dispatch_id"], "request": str(request_path),
                "actual_vendor": "codex", "attempts": [attempt],
                "result": {"source_output": None,
                           "source_output_unavailable_reason": "no completed final source return",
                           "published_output": None,
                           "published_output_unavailable_reason": "no completed final source return",
                           "assessment": "unassessed"},
            }
            verdict: bytes | None = None
            source_ready = False
            publication_error: OSError | None = None
            published = False
            return_code = 1
            started = time.monotonic()
            try:
                try:
                    result = run_process(command, input=prompt, cwd=root, timeout=args.timeout_seconds)
                except subprocess.TimeoutExpired as exc:
                    result = subprocess.CompletedProcess(command, -1, exc.stdout or b"", exc.stderr or b"")
                    reason = f"codex timed out after {args.timeout_seconds:g}s"
                    attempt["launched"] = True
                except OSError as exc:
                    result = subprocess.CompletedProcess(command, -1, b"", str(exc).encode("utf-8"))
                    reason = f"cannot launch codex: {exc}"
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
                stream = records.codex_stream_result(result.stdout)
                events = list(stream.events)
                if stream.valid and stream.completed and not stream.failed_events:
                    # Completion is owned by the stream; the process status remains evidence.
                    reason = ""
                session_id, session_source = _thread_id(events, result.stderr)
                if args.holder_session_id and session_id == args.holder_session_id:
                    reason = "runtime returned the holder session as the builder session"
                    session_id = None
                    session_source = ""
                if attempt["launched"]:
                    records.add_runtime_evidence(attempt, "codex", result.stdout, continuity, elapsed)
                else:
                    records.add_unobserved(attempt, reason)
                attempt["observed"]["session_id"] = session_id
                attempt["observed"]["session_id_source"] = session_source or None
                if args.resume and session_id and session_id != args.resume:
                    reason = f"returned session id {session_id} does not match requested resume {args.resume}"
                message = last_message.read_bytes() if last_message.is_file() else b""
                if not message.strip() and stream.final_message is not None:
                    message = stream.final_message.encode("utf-8")
                complete = stream.valid and stream.completed and not stream.failed_events
                if complete and message.strip() and not reason:
                    verdict = message.replace(b"\r\n", b"\n")
                    if session_id:
                        attempt.update(outcome="success", reason="")
                        record["outcome"] = "success"
                        return_code = 0
                    else:
                        attempt.update(
                            outcome="success_uncontinuable",
                            reason="Codex completed but returned no session identity; this turn cannot be resumed",
                        )
                        record["outcome"] = "success_uncontinuable"
                elif complete and not message.strip() and not reason:
                    attempt.update(
                        outcome="completed_no_output",
                        reason="turn completed without a final message",
                    )
                    record["outcome"] = "completed_no_output"
                else:
                    if not stream.valid:
                        failure_reason = "codex returned invalid JSONL"
                    elif stream.failed_events:
                        failure_reason = "codex stream reported turn.failed"
                    elif not stream.completed:
                        failure_reason = "codex stream returned no turn.completed"
                    else:
                        failure_reason = f"codex turn could not be accepted (exit {result.returncode})"
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
            if publication_error is not None:
                raise publication_error
            if source_ready:
                session_note = attempt["observed"].get("session_id") or "unavailable"
                print(f"implementer: codex ({args.model}, {args.effort}) session {session_note} -> {output}")
            else:
                print(f"implementer: {attempt['reason']}", file=sys.stderr)
            return return_code


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        description="Run a recorded Codex implementer turn; resume only an explicit session id.",
        epilog=(
            "The launcher always uses --approve-for-me and JSONL. It never uses --ephemeral, "
            "--last, a read-only sandbox, or vendor fallback. Outputs default to the machine-local "
            ".tradecraft dispatch store and must be new. A successful turn without a returned "
            "session id publishes its result but exits nonzero because it cannot be continued."
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
    cli.add_argument("--model", help=f"requested model (default: {DEFAULT_MODEL})")
    cli.add_argument("--effort", help=f"requested effort (default: {DEFAULT_EFFORT})")
    cli.add_argument("--model-source", help="source of the explicitly selected model")
    cli.add_argument("--effort-source", help="source of the explicitly selected effort")
    cli.add_argument("--codex", help="explicit Codex CLI executable")
    cli.add_argument("--codex-unavailable-reason",
                     help="refuse without rediscovering a missing Codex executable")
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

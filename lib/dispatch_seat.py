#!/usr/bin/env python3
"""Dispatch a fresh, bounded seat and publish its final message.

Usage: python <plugin>/lib/dispatch_seat.py --dispatch FILE --root DIR
       --vendor claude --own-vendor codex --work ISSUE --stage NAME
       --settings-source SOURCE --settings-scope SCOPE --classification cold
       --requires read|execute [--output NEW_FILE]

Availability is discovered by trying or reading a machine-local expiring hold.
Only availability failures permit one attempt on the caller's own vendor.
Every job declares whether it requires reading or execution. Claude read mode
exposes Read,Glob,Grep; Claude execute mode also exposes Bash. Claude supplies
no OS sandbox in either mode. The launcher verifies a detached recipient root
and records each attempted boundary. The dispatch owns its job context.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
from vendor_cli import CliError, CliNotFound, resolve_command
from seat_process import run_process
from winio import utf8_stdio

VENDORS = ("codex", "claude")
# Each default names what it rests on. A default no comparison supports stands
# as un-compared, which is a fact about the evidence and not a finding for it.
# Codex was preferred blind on artifact authorship over gpt-6-astra and
# gpt-5.6-terra; the owner's code-task pilot separated none of the three [D-645].
DEFAULT_MODELS = {
    "codex": "gpt-5.6-sol",
    "claude": "opus",  # un-compared: no run has compared it with any Claude sibling
}
DEFAULT_CODEX_EFFORT = "xhigh"
CLAUDE_EFFORTS = {"ordinary": "xhigh", "cold": "max", "terminal": "max"}
CLAUDE_READ_TOOLS = "Read,Glob,Grep"
CLAUDE_EXECUTE_TOOLS = "Read,Glob,Grep,Bash"
GIT_ENVIRONMENT_KEYS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")


class DispatchError(RuntimeError):
    """A dispatch failed without evidence permitting vendor fallback."""


def default_hold_file() -> Path:
    return Path.home() / ".tradecraft" / "vendor-holds"


def read_holds(path: Path) -> dict[str, datetime]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    holds = {}
    for number, line in enumerate(content.splitlines(), 1):
        if not line.strip():
            continue
        try:
            vendor, timestamp = line.split()
            reset = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if vendor not in VENDORS or vendor in holds or reset.utcoffset() is None:
                raise ValueError()
        except ValueError as exc:
            raise DispatchError(
                f"{path}:{number}: expected one row per vendor: "
                "codex|claude ISO-8601-reset-with-timezone (no comments)"
            ) from exc
        holds[vendor] = reset.astimezone(timezone.utc)
    return holds


def build_command(vendor, executable, root, last_message, model, effort, required_capability):
    if vendor == "codex":
        return [*executable, "exec", "--strict-config", "--ignore-user-config",
                "--ephemeral", "--sandbox", "read-only",
                "--json", "--color", "never", "--model", model,
                "-c", "apps._default.enabled=false",
                "-c", f'model_reasoning_effort="{effort}"', "-C", str(root),
                "--skip-git-repo-check", "--output-last-message", str(last_message), "-"]
    if required_capability == "read":
        tools = CLAUDE_READ_TOOLS
    elif required_capability == "execute":
        tools = CLAUDE_EXECUTE_TOOLS
    else:
        raise DispatchError(f"unknown required capability: {required_capability}")
    return [*executable, "-p", "--model", model, "--effort", effort,
            "--output-format", "json", "--no-session-persistence", "--safe-mode",
            "--tools", tools, "--allowedTools", tools,
            "--permission-mode", "dontAsk", "--strict-mcp-config"]


def can_supply(vendor, required_capability):
    if required_capability == "read":
        return True
    if required_capability == "execute":
        return vendor == "claude"
    raise DispatchError(f"unknown required capability: {required_capability}")


def capability_refusal(vendor, required_capability):
    return f"{vendor} cannot supply required capability {required_capability}; no process was launched"


def permission_boundary(vendor, required_capability, root):
    if vendor == "claude":
        if required_capability == "read":
            tools = CLAUDE_READ_TOOLS
        elif required_capability == "execute":
            tools = CLAUDE_EXECUTE_TOOLS
        else:
            raise DispatchError(f"unknown required capability: {required_capability}")
        return (
            f"Claude tools={tools}; safe_mode=true; permission_mode=dontAsk; "
            f"strict_mcp_config=true; os_sandbox=none; detached_root_verified={root}"
        )
    return (
        "Codex sandbox=read-only; user_config=ignored; apps=disabled-by-config; "
        f"detached_root_verified={root}"
    )


def git_environment():
    return {key: value for key, value in os.environ.items() if key not in GIT_ENVIRONMENT_KEYS}


def git_diagnostic(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="backslashreplace").strip()
    return text.encode("ascii", errors="backslashreplace").decode("ascii")


def detached_worktree_root(root):
    """Return None for a lawful root, otherwise the reason for its refusal."""
    try:
        toplevel = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20,
            env=git_environment(),
        )
        head = subprocess.run(
            ["git", "-C", str(root), "symbolic-ref", "-q", "HEAD"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20,
            env=git_environment(),
        )
    except subprocess.TimeoutExpired:
        return "Git root probe timed out"
    except OSError as exc:
        detail = str(exc).encode("ascii", errors="backslashreplace").decode("ascii")
        return f"Git root probe could not start: {detail}"
    if toplevel.returncode != 0:
        diagnostic = git_diagnostic(toplevel.stderr)
        if "not a git repository" in diagnostic.lower():
            return "root is not a Git worktree"
        return f"Git root probe failed: {diagnostic or f'exit {toplevel.returncode}'}"
    try:
        reported_root = Path(toplevel.stdout.decode("utf-8").strip()).resolve()
    except (UnicodeError, OSError):
        return "Git root probe returned an unreadable worktree path"
    if reported_root != root:
        return f"root is not the worktree top level (Git reports {reported_root})"
    if head.returncode == 0:
        return "HEAD is attached to a branch"
    if head.returncode != 1:
        diagnostic = git_diagnostic(head.stderr)
        return f"Git HEAD probe failed: {diagnostic or f'exit {head.returncode}'}"
    return None


def diagnostic_reason(text: str) -> str | None:
    """Recognize complete runtime diagnostic forms, never a keyword in prose."""
    text = text.strip().replace(chr(8217), "'")
    auth = r"(?:Not logged in|Invalid API key|Login expired)(?:\s*[\u00b7.]?\s*Please run /login)?"
    quota = (
        r"(?:You(?:'ve| have) hit your (?:usage |session |weekly |Opus |Sonnet )?limit"
        r"|Usage limit (?:reached|exceeded)|Rate limit (?:reached|exceeded))"
        r"(?:\. Try again (?:tomorrow|later)\.)?"
    )
    if re.fullmatch(auth, text, re.IGNORECASE):
        return "authentication unavailable"
    if re.fullmatch(quota, text, re.IGNORECASE):
        return "usage or rate limit"
    if re.fullmatch(r"API Error: (?:401|429)", text, re.IGNORECASE):
        return "authentication unavailable" if "401" in text[:16] else "usage or rate limit"
    return None


def error_reason(value) -> str | None:
    """Read only a runtime error field/event, not an arbitrary transcript."""
    if isinstance(value, dict):
        code = value.get("code") or value.get("type")
        if code in {"rate_limit", "rate_limit_error", "rate_limit_exceeded", "usage_limit_reached", "insufficient_quota"}:
            return "usage or rate limit"
        if code in {"authentication_failed", "authentication_error", "invalid_api_key", "unauthorized"}:
            return "authentication unavailable"
        for key in ("message", "error"):
            reason = error_reason(value.get(key))
            if reason:
                return reason
    elif isinstance(value, list):
        return next((reason for item in value if (reason := error_reason(item))), None)
    elif isinstance(value, str):
        # Observed Codex failed-event messages. Never apply these prefixes to
        # successful final prose, where the status can be quoted evidence.
        if re.match(r"unexpected status 401 Unauthorized(?::|$)", value):
            return "authentication unavailable"
        if re.match(r"(?:unexpected status 429 Too Many Requests|exceeded retry limit, last status: 429 Too Many Requests)(?::|$)", value):
            return "usage or rate limit"
        if value in {"rate_limit", "rate_limit_error", "rate_limit_exceeded", "usage_limit_reached", "insufficient_quota"}:
            return "usage or rate limit"
        if value in {"authentication_failed", "authentication_error", "invalid_api_key", "unauthorized"}:
            return "authentication unavailable"
        return diagnostic_reason(value)
    return None


def interpret(vendor, result, last_message):
    """Return (outcome, reason, verdict); an adverse judgement is still success."""
    stdout = result.stdout.decode("utf-8")
    stderr = result.stderr.decode("utf-8", errors="replace")
    message = ""
    failure = None
    if vendor == "claude":
        try:
            payload = json.loads(stdout)
        except ValueError:
            payload = None
        if isinstance(payload, dict) and payload.get("type") == "result":
            message = payload.get("result")
            message = message if isinstance(message, str) else ""
            success = payload.get("is_error") is False and payload.get("subtype") == "success"
            if not success:
                failure = error_reason(payload.get("errors")) or error_reason(payload.get("error"))
                if payload.get("api_error_status") in {401, 429}:
                    failure = "authentication unavailable" if payload["api_error_status"] == 401 else "usage or rate limit"
            if payload.get("permission_denials"):
                return "error", "Claude reported a tool permission denial; see its stdout log", ""
        else:
            success = False
    else:
        events = []
        try:
            events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
            valid = all(isinstance(event, dict) for event in events)
        except ValueError:
            valid = False
        if valid:
            completed = any(event.get("type") == "turn.completed" for event in events)
            failed = [event for event in events if event.get("type") == "turn.failed"]
            success = completed and not failed
            if not success:
                errors = failed or [event for event in events if event.get("type") == "error"]
                failure = error_reason(errors)
        else:
            success = False
        if last_message.is_file():
            message = last_message.read_bytes().decode("utf-8")
    # Some CLI versions return a runtime diagnostic as a zero-exit final result.
    failure = failure or diagnostic_reason(message)
    if failure:
        return "unavailable", failure, ""
    if result.returncode == 0 and success and message.strip():
        return "success", "", message
    # Plain launch diagnostics have no JSON envelope. Do not scan echoed prompts.
    for diagnostic in (stdout, stderr):
        reason = diagnostic_reason(diagnostic)
        if reason:
            return "unavailable", reason, ""
    return "error", f"{vendor} failed or returned no valid final result (exit {result.returncode}); see logs", ""


sidecar = records.sidecar


def selected_effort(args, vendor):
    if vendor == "claude" and args.claude_effort is None:
        return CLAUDE_EFFORTS[args.classification]
    if vendor == "codex" and args.codex_effort is None:
        return DEFAULT_CODEX_EFFORT
    return getattr(args, vendor + "_effort")


def selected_model(args, vendor):
    value = getattr(args, vendor + "_model")
    return DEFAULT_MODELS[vendor] if value is None else value


def setting_sources(args, vendor):
    return {
        "vendor": args.settings_source,
        "model": (
            args.settings_source if getattr(args, vendor + "_model") is not None
            else "dispatch_seat default"
        ),
        "effort": (
            args.settings_source if getattr(args, vendor + "_effort") is not None
            else "classification mapping" if vendor == "claude"
            else "dispatch_seat default"
        ),
        "classification": args.settings_source,
        "continuity": "dispatch_seat route (fresh)",
        "permission_boundary": args.settings_source,
        "required_capability": args.settings_source,
    }


def run_dispatch(args, *, now=None) -> int:
    dispatch = args.dispatch.expanduser().resolve()
    root = args.root.expanduser().resolve()
    output = records.resolved_output(args.output, args.work, args.stage)
    args.output = output
    hold_file = args.hold_file.expanduser().resolve()
    if not root.is_dir():
        raise DispatchError(f"Root is not a directory: {root}")
    root_refusal = detached_worktree_root(root)
    if root_refusal:
        raise DispatchError(f"Root must be the top level of a detached Git worktree: {root}; {root_refusal}")
    if not can_supply(args.vendor, args.requires) and (
        args.own_vendor == args.vendor or not can_supply(args.own_vendor, args.requires)
    ):
        raise DispatchError(capability_refusal(args.vendor, args.requires))
    records.require_output_outside_root(output, root)
    prompt = dispatch.read_bytes()
    if not prompt.decode("utf-8").strip():
        raise DispatchError(f"Dispatch is empty: {dispatch}")
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        raise DispatchError("--timeout-seconds must be finite and positive")
    read_holds(hold_file)
    for vendor in VENDORS:
        effort = selected_effort(args, vendor)
        if not selected_model(args, vendor).strip() or not effort.strip():
            raise DispatchError(f"{vendor} model and effort must be nonempty")
        explicit = getattr(args, vendor)
        if explicit and can_supply(vendor, args.requires):
            resolve_command(vendor, explicit)  # invalid overrides fail before spending
    record_path = sidecar(output, ".run.json")
    request_path = sidecar(output, ".request.json")
    input_path = sidecar(output, ".dispatch.bin")
    source_path = sidecar(output, ".source.bin")
    destinations = [output, record_path, request_path, input_path, source_path, *[
        sidecar(output, f".{vendor}.{stream}.log")
        for vendor in VENDORS for stream in ("stdout", "stderr")
    ]]
    for path in destinations:
        if path.resolve() in {dispatch, hold_file}:
            raise DispatchError(f"Output destination is also an input: {path}")
        if path.exists() or path.is_symlink():
            raise DispatchError(f"Refusing existing output: {path}. Choose a new --output path.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with records.reserve_bundle(destinations, output) as streams:
        record_stream = streams[record_path]
        request = records.request_record(
            dispatch_id=uuid.uuid4().hex, work=args.work, stage=args.stage,
            settings_source=args.settings_source, settings_scope=args.settings_scope,
            vendor=args.vendor,
            model=selected_model(args, args.vendor), effort=selected_effort(args, args.vendor),
            continuity="fresh",
            permission_boundary=permission_boundary(args.vendor, args.requires, root),
            root=root, classification=args.classification, retry_of=args.retry_of,
            setting_sources=setting_sources(args, args.vendor),
        )
        request["requested"]["required_capability"] = args.requires
        request["revision_before"] = records.git_revision(root)
        request["input"] = str(input_path)
        streams[request_path].write(records.json_bytes(request))
        streams[request_path].flush()
        streams[input_path].write(prompt)
        streams[input_path].flush()
        streams.mark_ready()
        print(f"seat: dispatch {request['dispatch_id']} -> {output}")
        record = {"schema_version": records.SCHEMA_VERSION,
                  "dispatch_id": request["dispatch_id"], "request": str(request_path),
                  "requested_vendor": args.vendor, "own_vendor": args.own_vendor,
                  "actual_vendor": None, "fallback_reason": None, "attempts": [],
                  "staffing_status": "unfilled", "staffing_reason": None,
                  "staffing_qualification": {
                      "cross_vendor_satisfied": False, "same_vendor_reason": None,
                  },
                  "result": {"source_output": None,
                             "source_output_unavailable_reason": "no successful final source return",
                             "published_output": None,
                             "published_output_unavailable_reason": "no successful final source return",
                             "assessment": "unassessed"}}
        pending_logs = {}
        verdict = None
        publication_error = None
        published = False

        def flush_logs():
            for path in list(pending_logs):
                streams[path].write(pending_logs.pop(path))
                streams[path].flush()

        try:
            vendors = [args.vendor]
            if args.own_vendor != args.vendor:
                vendors.append(args.own_vendor)
            for vendor in vendors:
                model = selected_model(args, vendor)
                effort = selected_effort(args, vendor)
                attempt = {"vendor": vendor, "model": model, "effort": effort,
                           "classification": args.classification, "launched": False,
                           "exit_code": None, "outcome": "error", "reason": "",
                           "permission_boundary": None,
                           "permission_boundary_unavailable_reason": "attempt was not launched",
                           "setting_sources": setting_sources(args, vendor)}
                attempt["runtime_version"] = None
                attempt["runtime_version_unavailable_reason"] = "attempt was not launched"
                record["attempts"].append(attempt)
                reset = read_holds(hold_file).get(vendor)
                current = now if now is not None else datetime.now(timezone.utc)
                message = ""
                if not can_supply(vendor, args.requires):
                    outcome, reason = "unavailable", capability_refusal(vendor, args.requires)
                elif reset and reset > current:
                    outcome, reason = "unavailable", f"owner hold until {reset.isoformat()}"
                else:
                    try:
                        executable = resolve_command(vendor, getattr(args, vendor))
                    except CliNotFound as exc:
                        outcome, reason = "unavailable", str(exc)
                    else:
                        with tempfile.TemporaryDirectory(prefix="tradecraft-seat-") as temp:
                            last_message = Path(temp) / "last.txt"
                            command = build_command(
                                vendor, executable, root, last_message, model, effort, args.requires
                            )
                            boundary = permission_boundary(vendor, args.requires, root)
                            attempt["command"] = command
                            attempt["runtime_version"] = records.runtime_version(executable)
                            attempt["runtime_version_unavailable_reason"] = (
                                None if attempt["runtime_version"] else "runtime version command returned no value"
                            )
                            returned = False
                            started = time.monotonic()
                            try:
                                result = run_process(command, input=prompt, cwd=root, timeout=args.timeout_seconds)
                            except subprocess.TimeoutExpired as exc:
                                result = subprocess.CompletedProcess(command, -1, exc.stdout or b"", exc.stderr or b"")
                                outcome, reason = "error", f"{vendor} timed out after {args.timeout_seconds:g}s; no fallback"
                                attempt["launched"] = True
                                attempt["permission_boundary"] = boundary
                                attempt["permission_boundary_unavailable_reason"] = None
                            except FileNotFoundError as exc:
                                result = subprocess.CompletedProcess(command, -1, b"", str(exc).encode("utf-8"))
                                outcome, reason = "unavailable", f"{vendor} executable disappeared before launch"
                            except OSError as exc:
                                reason = (
                                    f"Cannot launch {vendor}: {exc}. From native Codex on Windows, "
                                    "use approval-managed host execution for the user's CLI/login. "
                                    "The script never elevates itself."
                                )
                                outcome = "error"
                                attempt.update(outcome=outcome, reason=reason)
                                attempt["permission_boundary_unavailable_reason"] = reason
                                records.add_unobserved(attempt, reason)
                                raise DispatchError(reason) from exc
                            else:
                                returned = True
                                attempt["launched"] = True
                                attempt["permission_boundary"] = boundary
                                attempt["permission_boundary_unavailable_reason"] = None
                            elapsed = time.monotonic() - started
                            attempt["exit_code"] = result.returncode
                            for stream in ("stdout", "stderr"):
                                log = sidecar(output, f".{vendor}.{stream}.log")
                                pending_logs[log], encoding = records.log_bytes(getattr(result, stream))
                                attempt[stream] = str(log)
                                attempt[stream + "_encoding"] = encoding
                            if returned:
                                try:
                                    outcome, reason, message = interpret(vendor, result, last_message)
                                except (UnicodeError, ValueError) as exc:
                                    reason = f"could not interpret {vendor} return: {exc}"
                                    attempt.update(outcome="error", reason=reason)
                                    records.add_runtime_evidence(
                                        attempt, vendor, result.stdout, "fresh", elapsed
                                    )
                                    raise
                            if attempt["launched"]:
                                records.add_runtime_evidence(
                                    attempt, vendor, result.stdout, "fresh", elapsed
                                )
                attempt.update(outcome=outcome, reason=reason)
                if attempt["permission_boundary"] is None:
                    attempt["permission_boundary_unavailable_reason"] = reason
                if "observed" not in attempt:
                    records.add_unobserved(attempt, reason)
                if outcome == "success":
                    record["actual_vendor"] = vendor
                    if record["fallback_reason"]:
                        message = f"Fallback: {args.vendor} -> {vendor}; reason: {record['fallback_reason']}.\n\n" + message
                    verdict = message.replace("\r\n", "\n").encode("utf-8")
                    break
                print(f"seat: {vendor}: {reason}", file=sys.stderr)
                if outcome != "unavailable":
                    break
                if vendor == args.vendor:
                    record["fallback_reason"] = reason
                    if "authentication" in reason:
                        if vendor == "claude":
                            print("seat: Claude launches omit --bare because it skips OAuth login lookup.", file=sys.stderr)
                        print("seat: On native Windows Codex, use approval-managed host execution.", file=sys.stderr)
            # No later seat can read this attempt's transcript from its tree.
            flush_logs()
        except (OSError, UnicodeError, ValueError, CliError, DispatchError) as exc:
            record["error"] = str(exc)
            raise
        finally:
            try:
                flush_logs()
            finally:
                record["completed_at"] = datetime.now(timezone.utc).isoformat()
                record["revision_after"] = records.git_revision(root)
                if verdict is not None:
                    degraded = record["actual_vendor"] != record["requested_vendor"]
                    record["staffing_status"] = "degraded" if degraded else "qualified"
                    record["staffing_reason"] = record["fallback_reason"] if degraded else None
                    record["staffing_qualification"] = {
                        "cross_vendor_satisfied": not degraded or bool(args.same_vendor_reason),
                        "same_vendor_reason": args.same_vendor_reason if degraded else None,
                    }
                    record["outcome"] = "success"
                    streams[source_path].write(verdict)
                    streams[source_path].flush()
                    record["result"]["source_output"] = str(source_path)
                    record["result"]["source_output_unavailable_reason"] = None
                elif record.get("error") or any(
                    attempt["outcome"] == "error" for attempt in record["attempts"]
                ):
                    record["outcome"] = "error"
                else:
                    record["outcome"] = "unavailable"
                streams.streams.pop(record_path)
                record_stream.close()
                for stream in streams.values():
                    stream.close()
                streams.streams.clear()
                if verdict is not None:
                    try:
                        records.publish_output(output, verdict)
                    except OSError as exc:
                        publication_error = exc
                        record["outcome"] = "error"
                        record["error"] = f"could not publish seat result: {exc}"
                        record["result"]["published_output_unavailable_reason"] = record["error"]
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
        if verdict is not None:
            print(f"seat: {vendor} ({model}, {effort}) -> {output}")
            return 0 if published else 1
        return 1


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        description=(
            "Run a fresh capability-declaring seat; an unavailable vendor falls back once only "
            "when the fallback can supply that capability."
        ),
        epilog=("Holds: one row per vendor, for example 'claude 2026-09-13T00:00:00Z'. "
                "Timezone required; no comments; expired holds are ignored. Keep this file "
                "machine-local and uncommitted. The script only reads it. Both modes use safe mode, "
                "permission mode dontAsk and strict MCP configuration, "
                "and neither has an OS sandbox. Put the job and any evidence already available in the "
                "dispatch; an execute job may produce its own probe evidence. --bare is omitted to "
                "preserve OAuth. "
                "From native Windows Codex use approval-managed host execution for login. "
                "Outputs must be new: verdict, .request.json, .dispatch.bin, .source.bin, "
                ".run.json, and per-vendor .stdout.log/.stderr.log. "
                "Sidecar suffixes append to the full --output filename, including its extension. "
                "Sidecars are reserved before launch; transcript contents appear after the last attempt. "
                "The source verdict is flushed before atomic publication, which requires same-filesystem hard links. "
                "The run record claims publication only after it succeeds and removes the verdict if finalizing the record fails. "
                "Malformed log bytes use a JSON base64 envelope named by the run record's encoding field. "
                "The run record normalizes runtime model and usage where their scope is known; "
                "the source-native values remain in the logs. Unknown failures and timeouts "
                "do not fall back. The launcher does not elevate or buy credits."),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    cli.add_argument("--dispatch", type=Path, required=True)
    cli.add_argument("--root", type=Path, required=True)
    cli.add_argument("--vendor", choices=VENDORS, required=True)
    cli.add_argument("--own-vendor", choices=VENDORS, required=True)
    cli.add_argument("--work", required=True, help="issue or other work identifier")
    cli.add_argument("--stage", required=True, help="dispatch stage")
    cli.add_argument("--settings-source", required=True, help="issue comment or named default")
    cli.add_argument("--settings-scope", required=True,
                     help="stages and vendor reached by the issue choice or named default")
    cli.add_argument("--retry-of", help="dispatch id of an earlier whole-invocation retry")
    cli.add_argument(
        "--same-vendor-reason",
        help="stage-local reason a degraded same-vendor return may satisfy this cross-vendor stage",
    )
    cli.add_argument("--classification", choices=records.CLASSIFICATIONS, required=True,
                     help="ordinary, protected cold, or terminal judgment")
    cli.add_argument(
        "--requires", choices=("read", "execute"), required=True,
        help=(
            "Capability the job consumes: read supplies file tools only; execute also supplies command "
            "execution. Existing callers must add --requires read unless the governing lens or assignment "
            "requires commands, in which case add --requires execute. Omission is an error, not a "
            "compatibility default."
        ),
    )
    cli.add_argument("--output", type=Path,
                     help="result path; defaults to the machine-local dispatch store")
    cli.add_argument("--hold-file", type=Path, default=default_hold_file(), help="shared availability holds")
    cli.add_argument(
        "--timeout-seconds", type=float, default=900,
        help="timeout per launched seat; size execute work beyond the default where its job needs it",
    )
    for vendor, model in DEFAULT_MODELS.items():
        cli.add_argument("--" + vendor, help="explicit CLI executable")
        cli.add_argument("--" + vendor + "-model", help=f"requested model (default: {model})")
        effort_default = "classification" if vendor == "claude" else DEFAULT_CODEX_EFFORT
        cli.add_argument("--" + vendor + "-effort",
                         help=f"requested reasoning effort (default: {effort_default})")
    return cli


def main(argv=None) -> int:
    utf8_stdio()
    try:
        return run_dispatch(parser().parse_args(argv))
    except (OSError, UnicodeError, CliError, records.RecordError, DispatchError) as exc:
        print(f"seat: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

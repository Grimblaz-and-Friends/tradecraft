#!/usr/bin/env python3
"""Dispatch a fresh, bounded seat and publish its final message.

Usage: python <plugin>/lib/dispatch_seat.py --dispatch FILE --root DIR
       --vendor claude --own-vendor codex --output NEW_FILE

Availability is discovered by trying or reading a machine-local expiring hold.
Only availability failures permit one attempt on the caller's own vendor.
Claude exposes file-reading tools, not a shell or an OS sandbox; provide any
executable probe evidence in the dispatch. The dispatch owns its job context.
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

from vendor_cli import CliError, CliNotFound, resolve_command
from seat_process import run_process
from winio import utf8_stdio

VENDORS = ("codex", "claude")
DEFAULTS = {"codex": ("gpt-6-astra", "xhigh"), "claude": ("opus", "max")}
FILE_TOOLS = "Read,Glob,Grep"


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


def build_command(vendor, executable, root, last_message, model, effort):
    if vendor == "codex":
        return [*executable, "exec", "--ephemeral", "--sandbox", "read-only",
                "--json", "--color", "never", "--model", model,
                "-c", f'model_reasoning_effort="{effort}"', "-C", str(root),
                "--skip-git-repo-check", "--output-last-message", str(last_message), "-"]
    return [*executable, "-p", "--model", model, "--effort", effort,
            "--output-format", "json", "--no-session-persistence", "--safe-mode",
            "--tools", FILE_TOOLS, "--allowedTools", FILE_TOOLS,
            "--permission-mode", "dontAsk", "--strict-mcp-config"]


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


def sidecar(output: Path, suffix: str) -> Path:
    return output.with_name(output.name + suffix)


def write_bytes(path: Path, content: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(content)


def publish_verdict(path: Path, content: bytes) -> None:
    """Publish complete bytes atomically, refusing any existing destination."""
    with tempfile.TemporaryDirectory(prefix=".tradecraft-publish-", dir=path.parent) as temporary:
        staged = Path(temporary) / "verdict"
        write_bytes(staged, content)
        # A same-filesystem link creates the final name atomically and, unlike
        # POSIX rename/replace, never overwrites a concurrent caller's file.
        os.link(staged, path)


@contextmanager
def reserve_bundle(destinations, output):
    """Prove exact-path creation before usage, keeping sidecars reserved."""
    streams = {}
    created = []
    ready = False
    try:
        for path in destinations:
            streams[path] = path.open("xb")
            created.append(path)
        # This empty preflight reservation carries no response; remove it
        # before a runtime starts. Only the completed verdict is published.
        streams.pop(output).close()
        with tempfile.TemporaryDirectory(prefix=".tradecraft-publish-", dir=output.parent) as temporary:
            os.link(output, Path(temporary) / "probe")
        output.unlink()
        ready = True
        yield streams
    finally:
        for stream in streams.values():
            stream.close()
        if not ready:
            for path in created:
                path.unlink(missing_ok=True)


def log_bytes(raw):
    try:
        return raw.decode("utf-8").replace("\r\n", "\n").encode("utf-8"), "utf-8"
    except UnicodeError:
        encoded = {"encoding": "base64", "data": base64.b64encode(raw).decode("ascii")}
        return (json.dumps(encoded) + "\n").encode("utf-8"), "base64-json"


def run_dispatch(args, *, now=None) -> int:
    dispatch = args.dispatch.expanduser().resolve()
    root = args.root.expanduser().resolve()
    output = args.output.expanduser().absolute()
    hold_file = args.hold_file.expanduser().resolve()
    if not root.is_dir():
        raise DispatchError(f"Root is not a directory: {root}")
    prompt = dispatch.read_bytes()
    if not prompt.decode("utf-8").strip():
        raise DispatchError(f"Dispatch is empty: {dispatch}")
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        raise DispatchError("--timeout-seconds must be finite and positive")
    read_holds(hold_file)
    for vendor in VENDORS:
        if not getattr(args, vendor + "_model").strip() or not getattr(args, vendor + "_effort").strip():
            raise DispatchError(f"{vendor} model and effort must be nonempty")
        explicit = getattr(args, vendor)
        if explicit:
            resolve_command(vendor, explicit)  # invalid overrides fail before spending
    record_path = sidecar(output, ".run.json")
    destinations = [output, record_path, *[
        sidecar(output, f".{vendor}.{stream}.log")
        for vendor in VENDORS for stream in ("stdout", "stderr")
    ]]
    for path in destinations:
        if path.resolve() in {dispatch, hold_file}:
            raise DispatchError(f"Output destination is also an input: {path}")
        if path.exists() or path.is_symlink():
            raise DispatchError(f"Refusing existing output: {path}. Choose a new --output path.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with reserve_bundle(destinations, output) as streams:
        record_stream = streams[record_path]
        record = {"requested_vendor": args.vendor, "own_vendor": args.own_vendor,
                  "actual_vendor": None, "fallback_reason": None, "attempts": []}
        pending_logs = {}
        verdict = None

        def flush_logs():
            for path in list(pending_logs):
                streams[path].write(pending_logs.pop(path))
                streams[path].flush()

        try:
            vendors = [args.vendor]
            if args.own_vendor != args.vendor:
                vendors.append(args.own_vendor)
            for vendor in vendors:
                model = getattr(args, vendor + "_model")
                effort = getattr(args, vendor + "_effort")
                attempt = {"vendor": vendor, "model": model, "effort": effort,
                           "exit_code": None, "outcome": "error", "reason": ""}
                record["attempts"].append(attempt)
                reset = read_holds(hold_file).get(vendor)
                current = now if now is not None else datetime.now(timezone.utc)
                message = ""
                if reset and reset > current:
                    outcome, reason = "unavailable", f"owner hold until {reset.isoformat()}"
                else:
                    try:
                        executable = resolve_command(vendor, getattr(args, vendor))
                    except CliNotFound as exc:
                        outcome, reason = "unavailable", str(exc)
                    else:
                        with tempfile.TemporaryDirectory(prefix="tradecraft-seat-") as temp:
                            last_message = Path(temp) / "last.txt"
                            command = build_command(vendor, executable, root, last_message, model, effort)
                            returned = False
                            try:
                                result = run_process(command, input=prompt, cwd=root, timeout=args.timeout_seconds)
                            except subprocess.TimeoutExpired as exc:
                                result = subprocess.CompletedProcess(command, -1, exc.stdout or b"", exc.stderr or b"")
                                outcome, reason = "error", f"{vendor} timed out after {args.timeout_seconds:g}s; no fallback"
                            except FileNotFoundError as exc:
                                result = subprocess.CompletedProcess(command, -1, b"", str(exc).encode("utf-8"))
                                outcome, reason = "unavailable", f"{vendor} executable disappeared before launch"
                            except OSError as exc:
                                raise DispatchError(
                                    f"Cannot launch {vendor}: {exc}. From native Codex on Windows, "
                                    "use approval-managed host execution for the user's CLI/login. "
                                    "The script never elevates itself."
                                ) from exc
                            else:
                                returned = True
                            attempt["exit_code"] = result.returncode
                            for stream in ("stdout", "stderr"):
                                log = sidecar(output, f".{vendor}.{stream}.log")
                                pending_logs[log], encoding = log_bytes(getattr(result, stream))
                                attempt[stream] = str(log)
                                attempt[stream + "_encoding"] = encoding
                            if returned:
                                outcome, reason, message = interpret(vendor, result, last_message)
                attempt.update(outcome=outcome, reason=reason)
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
        except (OSError, UnicodeError, CliError, DispatchError) as exc:
            record["error"] = str(exc)
            raise
        finally:
            try:
                flush_logs()
            finally:
                record_stream.write((json.dumps(record, ensure_ascii=True, indent=2) + "\n").encode("utf-8"))
                record_stream.flush()
                for stream in streams.values():
                    stream.close()
        if verdict is not None:
            publish_verdict(output, verdict)
            print(f"seat: {vendor} ({model}, {effort}) -> {output}")
            return 0
        return 1


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        description="Run a fresh seat; unavailable vendors fall back once to --own-vendor.",
        epilog=("Holds: one row per vendor, for example 'claude 2026-09-13T00:00:00Z'. "
                "Timezone required; no comments; expired holds are ignored. Keep this file "
                "machine-local and uncommitted. The script only reads it. Claude uses only "
                "Read/Glob/Grep in safe mode (no commands or OS sandbox); put required context "
                "and probe evidence in the dispatch. --bare is omitted to preserve OAuth. "
                "From native Windows Codex use approval-managed host execution for login. "
                "Outputs must be new: verdict, .run.json, and per-vendor .stdout.log/.stderr.log. "
                "Sidecar suffixes append to the full --output filename, including its extension. "
                "Sidecars are reserved before launch; transcript contents appear after the last attempt. "
                "The run record is flushed before atomic verdict publication, which requires same-filesystem hard links. "
                "Malformed log bytes use a JSON base64 envelope named by the run record's encoding field. "
                "Runtime model and usage data remain in the logs. Unknown failures and timeouts "
                "do not fall back. The launcher does not elevate or buy credits."),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    cli.add_argument("--dispatch", type=Path, required=True)
    cli.add_argument("--root", type=Path, required=True)
    cli.add_argument("--vendor", choices=VENDORS, required=True)
    cli.add_argument("--own-vendor", choices=VENDORS, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--hold-file", type=Path, default=default_hold_file(), help="shared availability holds")
    cli.add_argument("--timeout-seconds", type=float, default=900, help="timeout per launched seat")
    for vendor, (model, effort) in DEFAULTS.items():
        cli.add_argument("--" + vendor, help="explicit CLI executable")
        cli.add_argument("--" + vendor + "-model", default=model, help="requested model")
        cli.add_argument("--" + vendor + "-effort", default=effort, help="requested reasoning effort")
    return cli


def main(argv=None) -> int:
    utf8_stdio()
    try:
        return run_dispatch(parser().parse_args(argv))
    except (OSError, UnicodeError, CliError, DispatchError) as exc:
        print(f"seat: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Launch or resume an implementer and retain the dispatch evidence.

Usage: python <plugin-root>/lib/dispatch_implementer.py --dispatch FILE --root DIR
       --work ISSUE --stage NAME --settings-source SOURCE --settings-scope SCOPE
       [--resume SESSION_ID --vendor VENDOR] [--artifact-brief FILE]

Artifact launches and resumes require --artifact-brief FILE containing the
affirmed brief comment's text, independently of the dispatch instructions.

Every invocation is a separate record. ``--resume`` is explicit; ``--last`` and
``--ephemeral`` are deliberately absent because either can defeat continuity.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from difflib import SequenceMatcher
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

import dispatch_record as records
import artifact_tree
from dispatch_lifecycle import (CLAUDE_DISALLOWED_ARGUMENT, CLAUDE_DISALLOWED_TOOLS,
                                claude_launch_controls, claude_launch_env, claude_launch_notice,
                                claude_stream_check, claude_terminal, stream_check_reason,
                                stream_check_record)
import launch_settings
import run_lifecycle as lifecycle
from codex_pytest import implementer_pytest_overrides
from seat_process import run_process
import implementer_environment as environments
import implementer_policy as policy
import codex_implementer as native_codex
from vendor_cli import CliError, resolve_command
from winio import utf8_stdio

# Builds use Sol 6.1 at xhigh under the owner's 2026-09-29 ruling
# (#758, issue comment 5899421625). Artifacts follow the 2026-09-30 ruling
# (#737, issue comment 5920638420): Sol 6.1 at xhigh.
# Claude Opus 5.5 at high is the switch profile; authoring remains interim.
PROFILES = {
    "artifact_author": {
        "codex": ("gpt-6.1-sol", "xhigh"),
        "claude": ("claude-opus-5-5", "high"),
    },
    "implementer": {
        "codex": ("gpt-6.1-sol", "xhigh"),
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


INSTRUCTION_SHIM_PREFIX = environments.INSTRUCTION_SHIM_PREFIX


def _import_path(path: str) -> str:
    """A Claude ``@`` import ends at an unescaped space; a backslash keeps it whole."""
    return path.replace(" ", "\\ ")


def instruction_shim_plan(tree: Path, git_dir: Path | None) -> list[tuple[Path | None, str]]:
    """Where an AGENTS.md-only tree's one-line CLAUDE.md shim may live, in order.

    The runtime loads a tree's own CLAUDE.md through ``--add-dir``; a tree whose
    rules live only in AGENTS.md gets a shim importing it (#893 R2). The first
    placement is the tree's git directory with a relative import; the second is
    the invocation's temporary directory (``None``) with an absolute import. An
    import containing ``#`` did not deliver in any spiked form, so it is never
    offered. A tree that needs a shim and has no placement refuses the launch.
    """
    if (tree / "CLAUDE.md").exists() or (tree / ".claude" / "CLAUDE.md").exists():
        return []
    target = tree / "AGENTS.md"
    if not target.exists():
        return []
    candidates: list[tuple[Path | None, str]] = []
    if git_dir is not None:
        try:
            relative = os.path.relpath(target, git_dir / (INSTRUCTION_SHIM_PREFIX + "x"))
        except ValueError:
            relative = None  # another drive has no relative path
        if relative is not None and "#" not in relative:
            candidates.append((git_dir, "@" + _import_path(relative.replace("\\", "/"))))
    if "#" not in target.as_posix():
        candidates.append((None, "@" + _import_path(target.as_posix())))
    if not candidates:
        raise ImplementerError(
            f"refusing the Claude launch: tree {tree} has AGENTS.md and no CLAUDE.md, and neither "
            "shim placement can import AGENTS.md without '#' in the import path, which the runtime "
            "does not load; relaunch on Codex or move the tree")
    return candidates


@contextmanager
def instruction_shim(candidates: list[tuple[Path | None, str]], temporary: Path, dispatch_id: str):
    """Write the shim for this invocation only and remove it when it ends."""
    if not candidates:
        yield None
        return
    errors = []
    for parent, line in candidates:
        directory = (parent or temporary) / (INSTRUCTION_SHIM_PREFIX + dispatch_id)
        try:
            directory.mkdir()
        except OSError as exc:
            errors.append(f"{directory}: {exc}")
            continue
        try:
            (directory / "CLAUDE.md").write_bytes((line + "\n").encode("utf-8"))
            yield directory
        finally:
            shutil.rmtree(directory, ignore_errors=True)
        return
    raise ImplementerError("cannot write the AGENTS.md instruction shim: " + "; ".join(errors))


def build_command(args: argparse.Namespace, executable: list[str], last_message: Path) -> list[str]:
    if args.vendor == "claude":
        command = [
            *executable, "-p", "--model", args.model, "--effort", args.effort,
            "--output-format", "stream-json", "--verbose", "--permission-mode", "auto",
            "--setting-sources", "user", "--plugin-dir",
            str(Path(__file__).resolve().parent.parent),
            "--strict-mcp-config", "--no-chrome",
            # With the child's ADDITIONAL_CLAUDE_MD, the runtime loads this
            # tree's own root instructions and imports; nothing above it.
            "--add-dir", str(Path(args.root).expanduser().resolve()),
            # One =-joined argument: the flag is variadic and would otherwise
            # swallow whatever argument follows it.
            CLAUDE_DISALLOWED_ARGUMENT,
        ]
        if getattr(args, "instruction_shim", None):
            command.extend(("--add-dir", str(args.instruction_shim)))
        if getattr(args, "launch_settings_path", None):
            command.extend(("--settings", args.launch_settings_path))
        if args.resume:
            command.extend(("--resume", args.resume))
        elif args.session_id:
            command.extend(("--session-id", args.session_id))
        return command
    return native_codex.command(executable, implementer_pytest_overrides(),
                                artifact=getattr(args, "stage", None) == "artifact")


def _claude_result(raw: bytes, check: dict | None = None) -> tuple[bool, bytes, str | None, str]:
    check = claude_stream_check(raw) if check is None else check
    value = check["return"] or claude_terminal(raw)
    if value is None:
        return False, b"", None, "claude returned invalid JSON"
    if not isinstance(value, dict) or value.get("type") != "result":
        return False, b"", None, "claude returned no final result"
    session = value.get("session_id")
    if not isinstance(session, str) or not re.fullmatch(r"[0-9a-f-]{36}", session, re.I):
        session = None
    if check["status"] == "work_outlived_return":
        return False, b"", session, stream_check_reason(check)
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


ARTIFACT_BODY_WORDS = 8
ARTIFACT_RETURN_MAX_BYTES = 240_000
ARTIFACT_RETURN_INSTRUCTION = (
    f"Return the whole artifact in at most {ARTIFACT_RETURN_MAX_BYTES:,} UTF-8 bytes, "
    "including the quoted affirmed brief and all artifact text. The bound counts the whole "
    "final message encoded as UTF-8, including whitespace and line endings. Preserve every decision and "
    "acceptance criterion when condensing. If this turn resumes an oversized return, condense "
    "it to the bound and return the whole revised artifact."
)
ARTIFACT_RETURN_REQUIREMENT = (
    "expected the affirmed brief anywhere in the return and an artifact body after it with at least "
    f"{ARTIFACT_BODY_WORDS} non-location words"
)


def _artifact_body_present(tail: str) -> bool:
    """Count prose outside headings, location lines and retrieval instructions."""
    prose = []
    for line in tail.splitlines():
        if re.match(r"^\s*#", line):
            continue
        if re.search(
            r"https?://|file://|[A-Za-z]:[\\/]|(?:^|\s)[/~]\S|"
            r"(?:[\w.-]+[\\/])+[\w.-]+|[\w.-]+\.(?:md|txt|docx|pdf)\b|"
            r"\[[^\]]*\]\([^)]*\)", line, re.IGNORECASE,
        ):
            continue
        if re.search(
            r"\b(?:fetch|retrieve|open|read|see|download|find)\b.*"
            r"\b(?:file|document|artifact|path|link|there|here)\b|"
            r"\b(?:artifact|document|draft|file)\s+(?:is|was|has been)\s+"
            r"(?:in|at|saved|written|located|available|attached)\b", line, re.IGNORECASE,
        ):
            continue
        prose.append(line)
    return len(re.findall(r"[^\W\d_]{2,}", "\n".join(prose))) >= ARTIFACT_BODY_WORDS


def artifact_carried_span(expected: str, returned: str) -> tuple[int, int] | None:
    """Recognize the existing brief/body form and expose its original carried span."""
    def normalize(text: str) -> tuple[str, list[int]]:
        characters, origins = [], []
        offset = 0
        for match in re.finditer(r"[^\r\n]*(?:\r\n|\r|\n|$)", text):
            raw_line = match.group()
            line = raw_line.rstrip("\r\n")
            prefix = re.match(r"^\s*(?:>\s*)+", line)
            start = prefix.end() if prefix else 0
            characters.extend(line[start:])
            origins.extend(range(offset + start, offset + len(line)))
            if len(raw_line) > len(line):
                characters.append("\n")
                origins.append(offset + len(line))
            offset += len(raw_line)
        unquoted = "".join(characters)
        excluded = set()
        for match in re.finditer(r"<!--.*?-->", unquoted, flags=re.DOTALL):
            excluded.update(range(match.start(), match.end()))
        return ("".join(char for index, char in enumerate(characters) if index not in excluded),
                [origin for index, origin in enumerate(origins) if index not in excluded])

    def close(left: str, right: str) -> bool:
        comparison = SequenceMatcher(None, left, right, autojunk=False)
        if comparison.ratio() >= 0.98:
            return True
        edits = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2
                    in comparison.get_opcodes() if tag != "equal")
        return edits <= 4

    words = normalize(expected)[0].split()
    if not words:
        return None
    text, origins = normalize(returned)
    tokens = list(re.finditer(r"\S+", text))
    brief = " ".join(words)
    anchor_size = min(8, len(words))
    anchor = " ".join(words[:anchor_size])
    for start in range(len(tokens) - len(words) + 1):
        candidate = [token.group() for token in tokens[start:start + len(words)]]
        if close(anchor, " ".join(candidate[:anchor_size])) and close(brief, " ".join(candidate)):
            tail = text[tokens[start + len(words) - 1].end():]
            if _artifact_body_present(tail):
                raw_start = origins[tokens[start].start()]
                # Include the full first brief line, preserving its quote prefix.
                raw_start = max(returned.rfind("\n", 0, raw_start), returned.rfind("\r", 0, raw_start)) + 1
                before = returned[:raw_start].splitlines(keepends=True)
                while before and re.fullmatch(r"\s*(?:>\s*)*", before[-1]):
                    before.pop()
                if before and re.fullmatch(
                        r"\s*(?:>\s*)*<!--\s*tradecraft:affirmed-brief:v1\s*-->\s*", before[-1]):
                    raw_start = sum(len(line) for line in before[:-1])
                return raw_start, len(returned)
    return None


def artifact_opening_carries_brief(expected: str, returned: str) -> bool:
    """Keep the completeness recognizer's boolean calling contract."""
    return artifact_carried_span(expected, returned) is not None


def validate_artifact_return(expected: str, returned: str | bytes) -> dict[str, object]:
    """Bound the native final message before comparing its brief and following prose."""
    message = returned if isinstance(returned, bytes) else returned.encode("utf-8")
    count = len(message)
    if count > ARTIFACT_RETURN_MAX_BYTES:
        reason = (
            f"artifact return has {count:,} UTF-8 bytes; maximum is "
            f"{ARTIFACT_RETURN_MAX_BYTES:,} UTF-8 bytes"
        )
    else:
        text = message.decode("utf-8", errors="replace")
        reason = "" if artifact_opening_carries_brief(expected, text) else (
            ARTIFACT_RETURN_REQUIREMENT if text.strip() else
            "artifact turn completed without final text; " + ARTIFACT_RETURN_REQUIREMENT)
    return {
        "status": "fail" if reason else "pass", "reason": reason,
        "maximum_bytes": ARTIFACT_RETURN_MAX_BYTES,
        "observed_bytes": count,
    }


def run_implementer(args: argparse.Namespace) -> int:
    if args.timeout_seconds is None:
        args.timeout_seconds = lifecycle.DEFAULT_BUILD_TIMEOUT_SECONDS if args.stage == "build" else lifecycle.DEFAULT_STAGE_TIMEOUT_SECONDS
    deadline = lifecycle.stage_deadline(args.stage, args.timeout_seconds,
                                         started=getattr(args, "invocation_started_monotonic", None))
    with lifecycle.deadline_scope(deadline):
        if args.stage == "artifact":
            with artifact_tree.isolated_git_environment():
                return _run_implementer(args, deadline)
        return _run_implementer(args, deadline)


def _run_implementer(args: argparse.Namespace, deadline) -> int:
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
    bridge = (launch_settings.read_bridge() if args.model is None or args.effort is None
              else launch_settings.Bridge(launch_settings.default_path().resolve()))
    settings = launch_settings.resolve(
        role, args.vendor, profile_model, profile_effort,
        "dispatch_implementer default", "dispatch_implementer default", bridge=bridge,
        explicit_model=args.model, explicit_effort=args.effort,
        explicit_model_source=args.model_source or args.settings_source,
        explicit_effort_source=args.effort_source or args.settings_source,
    )
    args.model, args.effort = settings.model, settings.effort
    launch_settings.print_plan({
        "stage": args.stage, "role": role, "continuity": "resume" if args.resume else "fresh",
        "primary": settings.as_dict(args.vendor, args.vendor_source),
    }, label="implementer")
    root = args.root.expanduser().resolve()
    dispatch = args.dispatch.expanduser().resolve()
    if not root.is_dir():
        raise ImplementerError(f"root is not a directory: {root}")
    prompt = dispatch.read_bytes()
    if not prompt.decode("utf-8").strip():
        raise ImplementerError(f"dispatch is empty: {dispatch}")
    artifact_brief = b""
    if args.stage == "artifact":
        if args.artifact_brief is None:
            raise ImplementerError(
                "artifact stage requires --artifact-brief FILE containing the affirmed brief comment's text"
            )
        artifact_brief = args.artifact_brief.read_bytes()
        if not artifact_brief.decode("utf-8").strip():
            raise ImplementerError("artifact brief must be nonempty UTF-8 text")
    elif args.artifact_brief is not None:
        raise ImplementerError("--artifact-brief is only valid for the artifact stage")
    context = (args.context.read_bytes() if args.context else b"")
    if context:
        context.decode("utf-8")
    if args.stage == "artifact":
        instruction = ARTIFACT_RETURN_INSTRUCTION.encode("utf-8")
        context = context + b"\n\n" + instruction if context else instruction
    effective_prompt = context + b"\n\n" + prompt if context else prompt
    input_composed_at = datetime.now(timezone.utc).isoformat()
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
    metadata = {}
    lifecycle_input = getattr(args, "lifecycle_input", None)
    if lifecycle_input:
        metadata = json.loads(lifecycle_input.read_bytes())
        if not isinstance(metadata, dict):
            raise ImplementerError("lifecycle input must be an object")
    copy = metadata.get("artifact_copy")
    if args.stage == "artifact" and copy is None:
        raise ImplementerError("artifact requires entrance-owned copy lifecycle; use work.py run artifact")
    if copy is not None:
        if args.stage != "artifact":
            raise ImplementerError("artifact copy provenance is only valid for artifact")
        try:
            output = records.resolved_output(args.output, args.work, args.stage)
            artifact_tree.provenance({"artifact_copy": copy, "root": str(root), "work": args.work,
                "instalment": metadata.get("instalment"), "holder_session_id": args.holder_session_id},
                str(records.sidecar(output, ".run.json")))
            artifact_tree.prove(copy)
        except (artifact_tree.ArtifactTreeError, KeyError, TypeError) as exc:
            raise ImplementerError(f"invalid artifact copy: {exc}") from exc
        if str(root) != copy["root"]:
            raise ImplementerError("launcher root disagrees with artifact copy")
    composition = metadata.get("prompt_composition")
    if composition is not None:
        if (not isinstance(composition, dict) or composition.get("origin") != "entrance"
                or composition.get("dispatch_sha256") != hashlib.sha256(prompt).hexdigest()
                or not isinstance(composition.get("sources"), list)):
            raise ImplementerError("entrance composition evidence differs from frozen dispatch")
        try:
            composed = datetime.fromisoformat(composition["composed_at"].replace("Z", "+00:00"))
            frozen = datetime.fromisoformat(input_composed_at)
            if composed > frozen:
                raise ValueError("unproved prompt boundary")
        except (KeyError, AttributeError, TypeError, ValueError) as exc:
            raise ImplementerError("entrance composition time is invalid") from exc
        composition = dict(composition)
    else:
        # Holder dispatches keep their supplied bytes and responsibility. This
        # clock proves when their effective input froze, not source inclusion.
        composition = {"origin": "holder", "composed_at": input_composed_at,
                       "dispatch_sha256": hashlib.sha256(prompt).hexdigest()}
    composition["effective_input_sha256"] = hashlib.sha256(effective_prompt).hexdigest()
    budget_reason = getattr(args, "budget_override_reason", None) or metadata.get("budget_override_reason")
    if budget_reason is not None and (args.stage != "build" or not isinstance(budget_reason, str) or not budget_reason.strip()):
        raise ImplementerError("budget override requires a build stage and a nonempty reason")
    if copy is None:
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
    brief_path = records.sidecar(output, ".artifact-brief.bin") if artifact_brief else None
    protocol_path = records.sidecar(output, ".codex.stdin.jsonl") if args.vendor == "codex" else None
    destinations = [
        output, request_path, record_path, input_path, source_path, stdout_path, stderr_path
    ]
    if context_path:
        destinations.append(context_path)
    if brief_path:
        destinations.append(brief_path)
    if protocol_path:
        destinations.append(protocol_path)
    inputs = {dispatch}
    if brief_path:
        inputs.add(args.artifact_brief.resolve())
    for path in destinations:
        if path.resolve() in inputs:
            raise ImplementerError(f"output destination is also an input: {path}")
        if path.exists() or path.is_symlink():
            raise ImplementerError(f"refusing existing output: {path}")
    executable = explicit_executable
    if executable is None and unavailable_reason is None:
        try:
            executable = resolve_command(args.vendor, None)
        except CliError as exc:
            unavailable_reason = str(exc)
    # Only a launch that will start a Claude process plans its shim; an
    # unavailable attempt keeps its recorded bundle and handover phase.
    shim_plan = (instruction_shim_plan(root, records.git_directory(root))
                 if args.vendor == "claude" and executable is not None and unavailable_reason is None
                 else [])
    dispatch_id = uuid.uuid4().hex
    output.parent.mkdir(parents=True, exist_ok=True)
    continuity = "resume" if args.resume else "fresh"
    with records.reserve_bundle(destinations, output) as streams:
        with tempfile.TemporaryDirectory(prefix=environments.INVOCATION_TEMPORARY_PREFIX) as temporary, \
                instruction_shim(shim_plan, Path(temporary), dispatch_id) as shim:
            args.instruction_shim = shim
            last_message = Path(temporary) / "last.txt"
            child_env = artifact_tree.environment() if args.stage == "artifact" else None
            intent = {"status": "unprepared", "disabled_plugin_ids": [], "allowed_plugins": []}
            preparation_error = None
            if executable is not None and unavailable_reason is None:
                try:
                    if args.vendor == "claude":
                        intent, child_env = policy.claude_prepare(executable, root, deadline, temporary,
                            Path(__file__).resolve().parent.parent, env=child_env)
                        args.launch_settings_path = intent["settings_path"]
                    else:
                        intent = policy.codex_prepare(executable, root, deadline, env=child_env)
                        config = native_codex.read_config(build_command(args, executable, last_message),
                                                         root, deadline, env=child_env)
                        intent["thread_config"] = policy.restriction_config(config, intent)
                        intent["discovery_sources"].append("Codex native config/read for recipient cwd")
                    intent["status"] = "prepared"
                except TimeoutError:
                    # No useful launch window is not a prepared failed attempt.
                    # Keep the reservation unpublished so prior stopped work
                    # remains the latest resumable invocation.
                    raise
                except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, AttributeError, UnicodeError) as exc:
                    # A probe stopped at the edge of the caller's window is the
                    # same missing launch window; only a failure leaving a
                    # useful window is an ordinary recorded preparation failure.
                    deadline.remaining()
                    preparation_error = "implementer preparation failed: " + str(exc)
                    intent["status"] = "failed"
                    intent["reason"] = preparation_error
            command = (
                build_command(args, executable, last_message)
                if executable is not None else None
            )
            request = records.request_record(
                dispatch_id=dispatch_id, work=args.work, stage=args.stage,
                settings_source=args.settings_source, settings_scope=args.settings_scope,
                vendor=args.vendor, model=args.model,
                effort=args.effort, continuity=continuity,
                permission_boundary=(
                    "workspace-write with native on-request/auto_review"
                    if args.vendor == "codex" else
                    "Claude auto permission mode; user settings only; no OS write sandbox"
                ),
                root=root, requested_session_id=args.resume, command=command,
                retry_of=args.retry_of,
                holder_session_id=args.holder_session_id,
                setting_sources={
                    "vendor": args.vendor_source,
                    "model": settings.model_source,
                    "effort": settings.effort_source,
                    "continuity": f"launcher route ({continuity})",
                    "permission_boundary": "dispatch_implementer route",
                },
            )
            request["implementer_role"] = role
            request["environment_request"] = intent
            request["transport"] = "codex-app-server-v2" if args.vendor == "codex" else "claude-stream-json"
            request["lineage_branch"] = args.lineage_branch
            request["lineage_pull_request"] = args.lineage_pull_request
            request.update({key: metadata[key] for key in (
                "instalment", "recovery_restart_reason", "recovery_restart_bundle",
                "budget_lineage", "budget_account_before", "budget_override_reason",
                "progress_baseline", "predecessor_bundle", "predecessor_stop_snapshot",
                "retained_session_id", "retained_session_source",
                "artifact_copy",
            ) if key in metadata})
            request["caller_limit_seconds"] = args.timeout_seconds
            request["stage_ceiling_seconds"] = (
                lifecycle.DEFAULT_STAGE_TIMEOUT_SECONDS if args.stage in lifecycle.REPAIR_STAGES else None)
            allocation = 0 if preparation_error else deadline.remaining()
            supplied = metadata.get("recipient_allocation_seconds")
            if supplied is not None:
                if not isinstance(supplied, (int, float)) or not math.isfinite(supplied) or supplied <= 0:
                    raise ImplementerError("recipient allocation must be finite and positive")
                allocation = min(allocation, supplied)
            request["recipient_allocation_seconds"] = allocation
            request["budget_override_reason"] = budget_reason
            if args.vendor == "claude" and command is not None and not preparation_error:
                # The notice is part of the effective input; its digest covers it.
                notice = claude_launch_notice(allocation)
                effective_prompt = effective_prompt + b"\n\n" + notice
                composition["effective_input_sha256"] = hashlib.sha256(effective_prompt).hexdigest()
                child_env = claude_launch_env(child_env, allocation)
                request["launch_controls"] = claude_launch_controls(
                    allocation, notice, disallowed=CLAUDE_DISALLOWED_TOOLS)
            if args.stage != "artifact":
                request.setdefault("budget_lineage", hashlib.sha256(
                    (args.work + str(root) + str(args.lineage_branch)).encode("utf-8")).hexdigest())
                snapshot_timeout = deadline.probe()
                try:
                    request["launch_snapshot"] = lifecycle.content_snapshot(root, timeout=snapshot_timeout)
                except TimeoutError as exc:
                    deadline.remaining()  # A slow snapshot is recorded; an exhausted window is not.
                    request["launch_snapshot"] = {"digest": None, "unavailable_reason": str(exc)}
                request.setdefault("progress_baseline", request["launch_snapshot"])
            request["context"] = (
                {"path": str(context_path), "sha256": hashlib.sha256(context).hexdigest()}
                if context_path else None
            )
            request["effective_input_sha256"] = hashlib.sha256(effective_prompt).hexdigest()
            request["prompt_composition"] = composition
            if brief_path:
                request["artifact_brief"] = {
                    "path": str(brief_path),
                    "source": args.artifact_brief_source or str(args.artifact_brief.resolve()),
                    "sha256": hashlib.sha256(artifact_brief).hexdigest(),
                }
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
            if copy is not None:
                try:
                    artifact_tree.provenance(request, record_path)
                except artifact_tree.ArtifactTreeError as exc:
                    raise ImplementerError(str(exc)) from exc
            request["input"] = str(input_path)
            streams[request_path].write(records.json_bytes(request))
            streams[request_path].flush()
            streams[input_path].write(prompt)
            streams[input_path].flush()
            if context_path:
                streams[context_path].write(context)
                streams[context_path].flush()
            if brief_path:
                streams[brief_path].write(artifact_brief)
                streams[brief_path].flush()
            # Version and revision probes swallow their own timeouts. Recheck
            # the window before publishing, so an exhausted caller limit leaves
            # no bundle that would displace an earlier stopped, resumable run.
            deadline.remaining()
            streams.mark_ready()
            print(f"implementer: dispatch {request['dispatch_id']} -> {output}")
            attempt: dict[str, object] = {
                "vendor": args.vendor, "launched": False, "exit_code": None,
                "outcome": "error", "reason": "",
                "stdout": str(stdout_path), "stderr": str(stderr_path),
                "source_format": request["transport"],
                "environment": environments.unknown("runtime not yet observed", vendor=args.vendor,
                                                       version=request["runtime_version"]),
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
            record["launched_at"] = request["launched_at"]
            growing = records.GrowingRun(record_path, record, streams,
                expected=args.resume or args.session_id, holder=args.holder_session_id,
                retained=request.get("retained_session_id"),
                retained_source=request.get("retained_session_source"))
            growing.begin_attempt(attempt, args.vendor, stdout_path, stderr_path)
            if unavailable_reason is not None or preparation_error:
                failure = preparation_error or unavailable_reason
                outcome = "error" if preparation_error else "unavailable"
                attempt.update(outcome=outcome, reason=failure)
                attempt["environment"] = environments.unknown("unlaunched: " + failure,
                    vendor=args.vendor, version=request["runtime_version"])
                records.add_unobserved(attempt, failure)
                record["outcome"] = outcome
                record["completed_at"] = datetime.now(timezone.utc).isoformat()
                record["revision_after"] = records.git_revision(root)
                records.add_usage_record(
                    attempt, request, completed_at=record["completed_at"],
                    staffing_status="unfilled",
                )
                for stream in streams.values():
                    stream.close()
                streams.streams.clear()
                growing.finish()
                print(
                    f"implementer: {args.vendor} (source {args.vendor_source}) unavailable: "
                    f"{failure}", file=sys.stderr,
                )
                return 1
            verdict: bytes | None = None
            source_ready = False
            publication_error: OSError | None = None
            published = False
            return_code = 1
            started = time.monotonic()
            ceiling = False
            native = None
            if args.vendor == "codex":
                native = native_codex.NativeTurn(args=args, prompt=effective_prompt, intent=intent,
                    environment=attempt["environment"], stdout_path=stdout_path,
                    observe=growing.observe, transcript=streams[protocol_path], cwd=root)
            if args.vendor == "claude":
                projects = environments.claude_projects(child_env)
                known = args.resume or args.session_id
                offset = environments.transcript_size(projects, known) if known else 0
                if offset is None and not args.resume:
                    offset = 0
            pending_environment = b""
            environment_line = 0
            def capture(name, chunk):
                nonlocal pending_environment, environment_line
                if native:
                    native.output(name, chunk)
                elif name == "stdout":
                    pending_environment += chunk
                    while b"\n" in pending_environment:
                        line, pending_environment = pending_environment.split(b"\n", 1)
                        environment_line += 1
                        try:
                            event = json.loads(line)
                        except (UnicodeError, ValueError):
                            continue
                        if isinstance(event, dict) and environments.claude_init(attempt["environment"], event,
                                path=stdout_path, line=environment_line,
                                allowed=[v["id"] for v in intent["allowed_plugins"]]):
                            growing.identity_changed = True
                growing.output(name, chunk)
            def checkpoint():
                if native:
                    native.refresh()
                growing.tick()
            try:
                try:
                    if args.handover_state:
                        _handover_phase(
                            args.handover_state, args.session_id or args.resume, "running"
                        )
                    allocation = min(allocation, deadline.remaining())
                    attempt["allocation_seconds"] = allocation
                    result = run_process(command, input=native.input if native else effective_prompt, cwd=root, timeout=allocation,
                                         env=child_env,
                                         on_output=capture, on_tick=checkpoint,
                                         on_launch=growing.launched,
                                         cleanup_deadline=deadline.cleanup_end)
                except subprocess.TimeoutExpired as exc:
                    if hasattr(exc, "cleanup_proven"):
                        record["cleanup_proven"] = exc.cleanup_proven
                    ceiling = True
                    record["interruption_cause"] = "ceiling"
                    result = subprocess.CompletedProcess(command, -1, exc.stdout or b"", exc.stderr or b"")
                    reason = ""
                    attempt["launched"] = getattr(exc, "launched", True)
                    if getattr(exc, "launch_unresolved", False):
                        record["launch_unresolved"] = True
                except TimeoutError as exc:
                    ceiling = True
                    record["interruption_cause"] = "ceiling"
                    result = subprocess.CompletedProcess(command, -1, b"", b"")
                    reason = str(exc)
                    allocation = 0
                except OSError as exc:
                    if hasattr(exc, "cleanup_proven"):
                        record["cleanup_proven"] = exc.cleanup_proven
                    attempt["launched"] = getattr(exc, "launched", attempt["launched"])
                    result = subprocess.CompletedProcess(command, -1, b"", str(exc).encode("utf-8"))
                    reason = f"cannot launch {args.vendor}: {exc}"
                    record["error"] = reason
                else:
                    if hasattr(result, "cleanup_proven"):
                        record["cleanup_proven"] = result.cleanup_proven
                    reason = ""
                    attempt["launched"] = True
                for name, path in (("stdout", stdout_path), ("stderr", stderr_path)):
                    if streams[path].tell() == 0 and getattr(result, name):
                        capture(name, getattr(result, name))
                growing.finish_attempt()
                if native:
                    native.finish()
                elif pending_environment.strip():
                    try:
                        event = json.loads(pending_environment)
                    except (UnicodeError, ValueError):
                        event = None
                    if isinstance(event, dict):
                        environments.claude_init(attempt["environment"], event, path=stdout_path,
                            line=environment_line + 1,
                            allowed=[v["id"] for v in intent["allowed_plugins"]])
                elapsed = time.monotonic() - started
                if ceiling:
                    reason = lifecycle.ceiling_reason(args.vendor, caller_limit=args.timeout_seconds,
                                                       allocation=allocation, elapsed=elapsed)
                attempt["exit_code"] = result.returncode
                outlived = False
                if args.vendor == "claude":
                    check = claude_stream_check(result.stdout)
                    if attempt["launched"]:
                        attempt["stream_check"] = stream_check_record(check)
                    outlived = check["status"] == "work_outlived_return"
                    complete, message, session_id, failure_reason = _claude_result(result.stdout, check)
                    session_source = "claude JSON result.session_id" if session_id else ""
                    if outlived:
                        pass
                    elif result.returncode != 0:
                        complete = False
                        failure_reason = f"claude exited {result.returncode}: {failure_reason}"
                else:
                    if native.valid and native.completed and not ceiling:
                        # Completion is owned by the stream; process status remains evidence.
                        reason = ""
                    # Only a session this invocation's runtime returned carries
                    # the native label; an inherited id keeps its own source.
                    session_id = native.session
                    session_source = "Codex native startup response.thread.id" if session_id else ""
                    message = (native.final_message or "").encode("utf-8")
                    complete = native.valid and native.completed
                    failure_reason = native.error or "Codex native stream returned no completed current turn"
                retained = record.get("session_identity", {})
                if not session_id:
                    session_id = retained.get("session_id")
                    session_source = (retained.get("source") or "") if session_id else ""
                reason = record.get("session_identity_error") or reason
                if args.holder_session_id and session_id == args.holder_session_id:
                    reason = "runtime returned the holder session as the builder session"
                    session_id = None
                    session_source = ""
                if attempt["launched"]:
                    if native:
                        attempt["observed"] = native.evidence(continuity)
                        attempt["elapsed_seconds"] = elapsed
                    else:
                        records.add_runtime_evidence(attempt, args.vendor, result.stdout, continuity, elapsed)
                    if args.vendor == "claude":
                        terminal = claude_terminal(result.stdout)
                        if isinstance(terminal, dict):
                            attempt["permission_denials"] = terminal.get("permission_denials")
                            attempt["model_usage"] = terminal.get("modelUsage")
                            attempt["native_cost"] = terminal.get("total_cost_usd")
                else:
                    records.add_unobserved(attempt, reason)
                    attempt["environment"] = environments.unknown("unlaunched: " + reason,
                        vendor=args.vendor, version=request["runtime_version"])
                attempt["observed"]["session_id"] = session_id
                attempt["observed"]["session_id_source"] = session_source or None
                if args.vendor == "claude" and attempt["launched"]:
                    environments.claude_instructions(attempt["environment"], projects=projects,
                        session=session_id, offset=offset, resumed=bool(args.resume), shim=shim,
                        git_dir=records.git_directory(root))
                if args.resume and session_id and session_id != args.resume:
                    reason = f"returned session id {session_id} does not match requested resume {args.resume}"
                if args.session_id and session_id and session_id != args.session_id:
                    reason = f"returned session id {session_id} does not match reserved session {args.session_id}"
                if complete and message.strip() and not reason:
                    verdict = (message if artifact_brief else message.replace(b"\r\n", b"\n"))
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
                elif outlived and not ceiling and not reason:
                    # Never success, but still this session's resume source.
                    attempt.update(outcome="work_outlived_return", reason=failure_reason)
                    record["outcome"] = "work_outlived_return"
                else:
                    attempt.update(
                        outcome="interrupted" if ceiling else "error",
                        reason=reason or failure_reason,
                    )
                    record["outcome"] = "interrupted" if ceiling else "error"
                if artifact_brief and complete and not reason:
                    validation = validate_artifact_return(
                        artifact_brief.decode("utf-8"), message
                    )
                    record["result"]["return_validation"] = validation
                    if validation["status"] == "fail" and message.strip():
                        record["outcome"] = "invalid_artifact_return"
                        record["reason"] = validation["reason"]
                        return_code = 1
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
                with lifecycle.cleanup_scope():
                    record["revision_after"] = records.git_revision(root)
                    if args.stage != "artifact":
                        try:
                            record["stop_snapshot"] = lifecycle.content_snapshot(root, timeout=deadline.probe(cleanup=True))
                        except TimeoutError as exc:
                            record["stop_snapshot"] = {"digest": None, "unavailable_reason": str(exc)}
                records.add_usage_record(
                    attempt, request, completed_at=record["completed_at"],
                    staffing_status=(
                        "qualified" if record["outcome"] in {
                            "success", "success_uncontinuable", "completed_no_output",
                            "invalid_artifact_return", "work_outlived_return",
                        }
                        else "unfilled"
                    ),
                )
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
                    growing.finish()
                except Exception:
                    if published:
                        output.unlink(missing_ok=True)
                    raise
                if args.handover_state:
                    _handover_phase(
                        args.handover_state, args.session_id or args.resume,
                        "completed" if (
                            return_code == 0 and published
                            or (attempt["observed"].get("session_id") == (args.session_id or args.resume)
                                and record["outcome"] in {"invalid_artifact_return", "completed_no_output",
                                                         "work_outlived_return"})
                        ) else "unresolved",
                    )
            if publication_error is not None:
                raise publication_error
            validation = record["result"].get("return_validation")
            if isinstance(validation, dict) and validation["status"] == "fail":
                session_note = attempt["observed"].get("session_id") or "unavailable"
                print(
                    f"implementer: failed artifact return: {validation['reason']}; "
                    f"bundle {record_path}; author session {session_note}; "
                    "holder: repeat run artifact to resume the recorded author",
                    file=sys.stderr,
                )
            elif record["outcome"] == "work_outlived_return":
                session_note = attempt["observed"].get("session_id") or "unavailable"
                print(
                    f"implementer: refused turn: {attempt['reason']}; bundle {record_path}; "
                    f"session {session_note}; nothing was published, and the next run of this "
                    "stage resumes this session",
                    file=sys.stderr,
                )
            elif source_ready:
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
            "native app-server with automatic approval review; Claude uses auto mode and stream-json. Neither route "
            "uses --ephemeral, --last, a read-only sandbox, or vendor fallback. Outputs default "
            "to the machine-local .tradecraft dispatch store and must be new. A successful turn "
            "without a returned session id publishes its result but exits nonzero because it "
            "cannot be continued."
            " Artifact launches and resumes require --artifact-brief FILE containing the "
            "affirmed brief comment's text."
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
    cli.add_argument("--artifact-brief", type=Path,
                     help="required for artifact launches and resumes: affirmed brief comment text as a file, retained verbatim")
    cli.add_argument("--artifact-brief-source", help="source locator of the authorized affirmed brief")
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
    cli.add_argument("--timeout-seconds", type=float,
                     help="declared caller limit; build defaults to 7200, other stages to 3600")
    cli.add_argument("--invocation-started-monotonic", type=float, help=argparse.SUPPRESS)
    cli.add_argument("--lifecycle-input", type=Path, help=argparse.SUPPRESS)
    cli.add_argument("--budget-override-reason")
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

#!/usr/bin/env python3
"""Run the reproducible Codex compatibility check for this plugin.

Preconditions:

* `python` resolves to a real interpreter rather than the Windows Store alias.
* `git` can initialize the temporary consumer repository.
* The Codex CLI is authenticated and may reach its service.
* The tradecraft plugin version in this tree is installed and enabled in Codex.

The probe creates a temporary consumer repository outside this source tree and
gives it the supported adoption instruction in its own AGENTS.md. A pass proves
that Codex loaded the repository instruction and the installed charter in full.
The nested session is ephemeral and read-only, and its model, reasoning effort,
and timeout are explicit launch inputs.

Usage: python tools/check_codex_compat.py [--codex PATH] [--timeout-seconds N]
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))
from winio import utf8_stdio  # noqa: E402
import dispatch_record as records  # noqa: E402
from vendor_cli import CliError as CompatError, resolve_codex  # noqa: E402

# The cell-body strip is the engine's, not this script's. The hand-rolled
# `text.split("---", 2)[2]` that stood here kept the two newlines after the
# frontmatter that the engine strips -- harmless where the result is only split
# into paragraphs, and exactly the drift check_body_strip_owner now refuses;
# tools/tests/test_lint.py::test_the_hand_rolled_strip_this_script_dropped_read_high
# is what shows it. Loaded the way tools/figures.py loads it: repo-only code
# importing shipped code, resolved from this file rather than the working directory.
_ENGINE_SPEC = importlib.util.spec_from_file_location(
    "authoring_figures", ROOT / "skills" / "authoring" / "scripts" / "figures.py"
)
engine = importlib.util.module_from_spec(_ENGINE_SPEC)
_ENGINE_SPEC.loader.exec_module(engine)

MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_REASONING = "high"
DEFAULT_TIMEOUT_SECONDS = 300.0

ADOPTION_TEMPLATE = """## Tradecraft

Before substantive action, load and read the installed `tradecraft:charter`
skill completely. If it is unavailable, stop and tell the owner that Tradecraft
is not installed or enabled.

Compatibility marker: {marker}
"""

PROMPT = """You are a compatibility probe. Follow the repository instructions
already supplied in context. Do not open or search files in the working
repository; you may read installed Tradecraft skill files. After loading the
installed tradecraft charter completely, respond with one JSON object and
nothing else. It must have exactly these keys:

* `marker`: the value after `Compatibility marker:` in the repository
  instructions;
* `opening`: the charter's first prose paragraph after its purpose header,
  with internal whitespace collapsed to single spaces and Markdown preserved;
* `concepts`: the six numbered concept headings, in order and without their
  leading numbers;
* `tail`: the charter's final prose paragraph (not a heading or list), with
  internal whitespace collapsed to single spaces and Markdown preserved.

Do not use code fences. If the charter is unavailable, respond instead with
TRADECRAFT_COMPAT_FAIL followed by a short reason.
"""


def _capture(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: float | None = None,
    binary: bool = False,
) -> subprocess.CompletedProcess:
    try:
        options = {
            "cwd": str(cwd) if cwd else None,
            "stdin": subprocess.DEVNULL,
            "capture_output": True,
            "text": not binary,
            "timeout": timeout,
        }
        if not binary:
            options.update(encoding="utf-8", errors="strict")
        return subprocess.run(command, **options)
    except OSError as exc:
        binary = command[0] if command else "<empty command>"
        raise CompatError(f"cannot launch {binary}: {exc}") from exc


def _manifest_version() -> str:
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompatError(f"cannot read {MANIFEST}: {exc}") from exc
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise CompatError(f"{MANIFEST} has no string version")
    return version


def _codex_version(codex: Path) -> str:
    result = _capture([str(codex), "--version"])
    if result.returncode != 0 or not result.stdout.strip():
        detail = (result.stderr or result.stdout).strip()
        raise CompatError(f"codex --version failed ({result.returncode}): {detail}")
    return result.stdout.strip()


def _assert_plugin(codex: Path, expected_version: str) -> None:
    result = _capture([str(codex), "plugin", "list", "--json"])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise CompatError(f"codex plugin list failed ({result.returncode}): {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CompatError(f"codex plugin list did not return JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise CompatError("codex plugin list JSON must be an object")
    installed = payload.get("installed", [])
    if not isinstance(installed, list):
        raise CompatError("codex plugin list JSON field 'installed' must be a list")
    matches = [
        plugin for plugin in installed
        if isinstance(plugin, dict) and plugin.get("pluginId") == "tradecraft@tradecraft"
    ]
    if not matches:
        raise CompatError("tradecraft@tradecraft is not installed")
    plugin = matches[0]
    if not plugin.get("enabled"):
        raise CompatError("tradecraft@tradecraft is installed but disabled")
    actual = plugin.get("version")
    if actual != expected_version:
        raise CompatError(
            f"installed tradecraft version is {actual!r}; this tree is "
            f"{expected_version!r}"
        )


def build_probe_command(
    codex: Path,
    consumer: Path,
    last_message: Path,
    *,
    model: str,
    reasoning: str,
) -> list[str]:
    """Build the launch so tests can pin every isolation and staffing input."""
    return [
        str(codex),
        "exec",
        "--ephemeral",
        "--sandbox", "read-only",
        "--json",
        "--model", model,
        "-c", f'model_reasoning_effort="{reasoning}"',
        "-C", str(consumer),
        "--color", "never",
        "--output-last-message", str(last_message),
        PROMPT,
    ]


def _is_within(path: Path, parent: Path) -> bool:
    """Whether resolved `path` is strictly below resolved `parent`."""
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return path.resolve() != parent.resolve()


def write_adoption_file(consumer: Path, marker: str) -> Path:
    """Write the canonical consumer instruction as stable UTF-8/LF bytes."""
    adoption = consumer / "AGENTS.md"
    content = ADOPTION_TEMPLATE.format(marker=marker)
    adoption.write_bytes(content.encode("utf-8"))
    return adoption


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _charter_evidence() -> dict[str, object]:
    """Derive source-sensitive anchors without placing their values in PROMPT."""
    charter = ROOT / "skills" / "charter" / "SKILL.md"
    try:
        text = charter.read_text(encoding="utf-8")
    except OSError as exc:
        raise CompatError(f"cannot read source charter {charter}: {exc}") from exc

    body = engine.frontmatterless(text)
    if text.startswith("---") and body == text:
        raise CompatError(f"source charter {charter} has incomplete frontmatter")

    paragraphs = [
        _collapse_whitespace(block)
        for block in re.split(r"\r?\n\s*\r?\n", body)
        if block.strip()
    ]
    opening = next(
        (
            block for block in paragraphs
            if not block.startswith("#") and not block.startswith("**Purpose:**")
        ),
        None,
    )
    numbered_sections = re.findall(r"(?m)^## ([1-6])\. (.+)$", body)
    tail = next(
        (block for block in reversed(paragraphs)
         if not re.match(r"^(?:#|[-*+]\s|\d+[.)]\s)", block)),
        None,
    )
    if (
        opening is None
        or [number for number, _ in numbered_sections] != list("123456")
        or tail is None
    ):
        raise CompatError(f"source charter {charter} has no stable compatibility anchors")
    return {
        "opening": opening,
        "concepts": [heading for _, heading in numbered_sections],
        "tail": tail,
    }


def _expected_probe_payload(marker: str) -> dict[str, object]:
    return {"marker": marker, **_charter_evidence()}


def _assert_probe_answer(answer: str, marker: str) -> None:
    if answer.startswith("TRADECRAFT_COMPAT_FAIL"):
        raise CompatError(f"nested Codex session reported: {answer}")
    try:
        payload = json.loads(answer)
    except json.JSONDecodeError as exc:
        raise CompatError(f"nested Codex result is not JSON: {exc}") from exc
    expected = _expected_probe_payload(marker)
    if payload != expected:
        raise CompatError(
            "nested Codex result did not match the source charter evidence: "
            f"{payload!r}"
        )


def _init_consumer(consumer: Path) -> None:
    try:
        result = _capture(["git", "init", "--quiet"], cwd=consumer)
    except OSError as exc:
        raise CompatError(f"cannot start git for consumer repository: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise CompatError(
            f"git init failed for consumer repository ({result.returncode}): {detail}"
        )


def run_probe(
    codex: Path,
    *,
    model: str,
    reasoning: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    record_output: Path | None = None,
    runtime_version: str | None = None,
) -> None:
    output = records.resolved_output(record_output, "tradecraft-compat", "codex")
    request_path = records.sidecar(output, ".request.json")
    run_path = records.sidecar(output, ".run.json")
    stdout_path = records.sidecar(output, ".codex.stdout.log")
    stderr_path = records.sidecar(output, ".codex.stderr.log")
    input_path = records.sidecar(output, ".dispatch.bin")
    source_path = records.sidecar(output, ".source.bin")
    destinations = [
        output, request_path, run_path, input_path, source_path, stdout_path, stderr_path
    ]
    if any(path.exists() or path.is_symlink() for path in destinations):
        raise CompatError(f"compatibility dispatch output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tradecraft-codex-compat-") as raw:
        base = Path(raw)
        if _is_within(base, ROOT):
            raise CompatError(
                "temporary consumer resolved inside the source tree; choose a "
                "system temporary directory outside the checkout"
            )
        consumer = base / "consumer"
        consumer.mkdir()
        _init_consumer(consumer)
        records.require_output_outside_root(output, base)
        marker = "TRADECRAFT_CODEX_COMPAT_" + secrets.token_hex(16).upper()
        write_adoption_file(consumer, marker)
        last_message = base / "last-message.txt"
        command = build_probe_command(
            codex, consumer, last_message, model=model, reasoning=reasoning
        )
        request = records.request_record(
            dispatch_id=secrets.token_hex(16), work="tradecraft-compat", stage="codex",
            settings_source="compatibility probe defaults or explicit CLI arguments",
            settings_scope="the Codex compatibility probe",
            vendor="codex", model=model, effort=reasoning, continuity="fresh",
            permission_boundary="ephemeral read-only Codex session", root=consumer,
            classification="ordinary", command=command,
            setting_sources={
                "vendor": "compatibility probe route",
                "model": "compatibility probe argument/default resolution",
                "effort": "compatibility probe argument/default resolution",
                "classification": "compatibility probe route",
                "continuity": "compatibility probe route (fresh)",
                "permission_boundary": "compatibility probe route",
            },
        )
        request["runtime_version"] = runtime_version
        request["runtime_version_unavailable_reason"] = (
            None if runtime_version else "caller supplied no verified runtime version"
        )
        request["revision_before"] = records.git_revision(consumer)
        request["input"] = str(input_path)
        failure: CompatError | None = None
        answer_bytes = b""
        with records.reserve_bundle(destinations, output) as streams:
            streams[request_path].write(records.json_bytes(request))
            streams[request_path].flush()
            streams[input_path].write(PROMPT.encode("utf-8"))
            streams[input_path].flush()
            streams.mark_ready()
            print(f"codex-compat: dispatch {request['dispatch_id']} -> {output}")
            started = time.monotonic()
            launched = False
            try:
                result = _capture(command, cwd=consumer, timeout=timeout_seconds, binary=True)
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout or b""
                stderr = exc.stderr or b""
                stdout = stdout.encode("utf-8") if isinstance(stdout, str) else stdout
                stderr = stderr.encode("utf-8") if isinstance(stderr, str) else stderr
                result = subprocess.CompletedProcess(command, -1, stdout, stderr)
                failure = CompatError(
                    "nested Codex session timed out after "
                    f"{timeout_seconds:g} seconds before returning a result"
                )
                launched = True
            except CompatError as exc:
                result = subprocess.CompletedProcess(
                    command, -1, b"", str(exc).encode("utf-8")
                )
                failure = exc
            else:
                launched = True
            elapsed = time.monotonic() - started
            encodings = {}
            for path, content, name in (
                (stdout_path, result.stdout, "stdout"), (stderr_path, result.stderr, "stderr")
            ):
                logged, encoding = records.log_bytes(content)
                streams[path].write(logged)
                streams[path].flush()
                encodings[name] = encoding
            attempt = {
                "vendor": "codex", "launched": launched, "exit_code": result.returncode,
                "outcome": "error", "reason": "", "stdout": str(stdout_path),
                "stderr": str(stderr_path), "stdout_encoding": encodings["stdout"],
                "stderr_encoding": encodings["stderr"],
            }
            if launched:
                records.add_runtime_evidence(attempt, "codex", result.stdout, "fresh", elapsed)
            else:
                records.add_unobserved(attempt, str(failure))
            if failure is None and result.returncode != 0:
                detail = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
                failure = CompatError(f"nested Codex session failed ({result.returncode}): {detail}")
            if failure is None and not last_message.is_file():
                failure = CompatError("nested Codex session wrote no final-message record")
            semantic_failure = False
            if last_message.is_file():
                answer_bytes = last_message.read_bytes()
                try:
                    answer = answer_bytes.decode("utf-8").strip()
                except UnicodeDecodeError as exc:
                    failure = failure or CompatError(f"nested Codex result is not UTF-8: {exc}")
                else:
                    if failure is None:
                        try:
                            _assert_probe_answer(answer, marker)
                        except CompatError as exc:
                            failure = exc
                            semantic_failure = True
            if failure is None:
                attempt.update(outcome="success", reason="")
                outcome = "success"
            else:
                attempt.update(outcome="semantic_failure" if semantic_failure else "error",
                               reason=str(failure))
                outcome = attempt["outcome"]
            if answer_bytes:
                streams[source_path].write(answer_bytes)
                streams[source_path].flush()
            record_stream = streams.streams.pop(run_path)
            record_stream.close()
            for stream in streams.values():
                stream.close()
            streams.streams.clear()
            published = False
            if failure is None and answer_bytes:
                try:
                    records.publish_output(output, answer_bytes.replace(b"\r\n", b"\n"))
                except OSError as exc:
                    failure = CompatError(f"could not publish compatibility result: {exc}")
                    outcome = "error"
                else:
                    published = True
            run = {
                "schema_version": records.SCHEMA_VERSION,
                "dispatch_id": request["dispatch_id"], "request": str(request_path),
                "outcome": outcome, "attempts": [attempt],
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "revision_after": records.git_revision(consumer),
                "result": {"source_output": str(source_path) if answer_bytes else None,
                           "source_output_unavailable_reason": (
                               None if answer_bytes else "runtime returned no final source text"
                           ),
                           "published_output": str(output) if published else None,
                           "published_output_unavailable_reason": (
                               None if published else str(failure)
                           ),
                           "assessment": "compatibility assertion", "passed": failure is None},
            }
            if failure is not None and outcome == "error":
                run["error"] = str(failure)
            try:
                records.finalize_reserved_json(run_path, run)
            except Exception:
                if published:
                    output.unlink(missing_ok=True)
                raise
        if failure is not None:
            raise failure


def _positive_timeout(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prove the installed tradecraft plugin in a real Codex session.",
        epilog=(
            "Preconditions: authenticated Codex CLI with network access; this "
            "tree's tradecraft version installed and enabled; git and a real "
            "Python interpreter on PATH."
        ),
    )
    parser.add_argument("--codex", help="Exact Codex executable; discovery is the default.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning", default=DEFAULT_REASONING)
    parser.add_argument(
        "--record-output", type=Path,
        help="retained result path; defaults to the machine-local dispatch store",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=_positive_timeout,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Bound the nested session (default: {DEFAULT_TIMEOUT_SECONDS:g}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    args = _parser().parse_args(argv)
    try:
        codex = resolve_codex(args.codex)
        version = _codex_version(codex)
        plugin_version = _manifest_version()
        _assert_plugin(codex, plugin_version)
        print(f"codex-compat: binary {codex}")
        print(f"codex-compat: version {version}")
        print(f"codex-compat: plugin tradecraft {plugin_version} enabled")
        print(
            "codex-compat: launch "
            f"model={args.model} reasoning={args.reasoning} "
            f"timeout-seconds={args.timeout_seconds:g} "
            "sandbox=read-only ephemeral=true "
            "consumer=temporary-adopting-repository outside-source=true"
        )
        run_probe(
            codex,
            model=args.model,
            reasoning=args.reasoning,
            timeout_seconds=args.timeout_seconds,
            record_output=args.record_output,
            runtime_version=version,
        )
    except (CompatError, records.RecordError, OSError, UnicodeError) as exc:
        print(f"codex-compat: FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "codex-compat: PASS: native AGENTS adoption and the complete installed "
        "charter reached the session"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

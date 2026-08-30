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
import importlib.util
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Mapping

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))
from winio import utf8_stdio  # noqa: E402

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
* `ceremonies`: the two bold ceremony labels, in order and without punctuation;
* `tail`: the charter's final prose paragraph, with internal whitespace
  collapsed to single spaces and Markdown preserved.

Do not use code fences. If the charter is unavailable, respond instead with
TRADECRAFT_COMPAT_FAIL followed by a short reason.
"""


class CompatError(RuntimeError):
    """A compatibility precondition or probe failed."""


def resolve_codex(
    explicit: str | None,
    *,
    env: Mapping[str, str] | None = None,
    path_lookup: Callable[[str], str | None] = shutil.which,
    platform: str = os.name,
) -> Path:
    """Resolve Codex explicitly, from PATH, or from the Windows app bundle."""
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.is_file():
            return candidate.resolve()
        raise CompatError(f"--codex does not name a file: {candidate}")

    on_path = path_lookup("codex")
    if on_path and Path(on_path).is_file():
        return Path(on_path).resolve()

    values = os.environ if env is None else env
    if platform == "nt" and values.get("LOCALAPPDATA"):
        bundle = Path(values["LOCALAPPDATA"]) / "OpenAI" / "Codex" / "bin"
        candidates = [path for path in bundle.glob("*/codex.exe") if path.is_file()]
        if candidates:
            return max(
                candidates,
                key=lambda path: (path.stat().st_mtime_ns, str(path).casefold()),
            ).resolve()

    raise CompatError(
        "Codex CLI not found: pass --codex, put it on PATH, or install the "
        "Windows Codex app bundle"
    )


def _capture(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
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
    ceremonies = re.findall(r"(?m)^- \*\*([^*]+)\.\*\*", body)
    if opening is None or len(ceremonies) != 2 or not paragraphs:
        raise CompatError(f"source charter {charter} has no stable compatibility anchors")
    return {
        "opening": opening,
        "ceremonies": ceremonies,
        "tail": paragraphs[-1],
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
) -> None:
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
        marker = "TRADECRAFT_CODEX_COMPAT_" + secrets.token_hex(16).upper()
        write_adoption_file(consumer, marker)
        last_message = base / "last-message.txt"
        command = build_probe_command(
            codex, consumer, last_message, model=model, reasoning=reasoning
        )
        try:
            result = _capture(command, cwd=consumer, timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            raise CompatError(
                "nested Codex session timed out after "
                f"{timeout_seconds:g} seconds before returning a result"
            ) from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise CompatError(f"nested Codex session failed ({result.returncode}): {detail}")
        if not last_message.is_file():
            raise CompatError("nested Codex session wrote no final-message record")
        try:
            answer = last_message.read_bytes().decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise CompatError(f"nested Codex result is not UTF-8: {exc}") from exc
        _assert_probe_answer(answer, marker)


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
        )
    except CompatError as exc:
        print(f"codex-compat: FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "codex-compat: PASS: native AGENTS adoption and the complete installed "
        "charter reached the session"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

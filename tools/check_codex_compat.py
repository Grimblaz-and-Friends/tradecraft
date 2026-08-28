#!/usr/bin/env python3
"""Run the reproducible Codex compatibility check for this plugin.

Preconditions:

* `python` resolves to a real interpreter rather than the Windows Store alias.
* The Codex CLI is authenticated and may reach its service.
* The tradecraft plugin version in this tree is installed and enabled in Codex.
* The installed plugin's hook has been inspected and trusted through `/hooks`.

The probe runs in an empty consumer directory. It therefore cannot receive the
charter through this repository's AGENTS.md; a pass demonstrates that the
trusted SessionStart hook supplied the charter and that the installed skill
catalog supplied all nine tradecraft cells. The nested session is ephemeral and
read-only, and its model and reasoning effort are explicit launch inputs.

Usage: python tools/check_codex_compat.py [--codex PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Mapping

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))
from winio import utf8_stdio  # noqa: E402

MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
SENTINEL = "TRADECRAFT_CODEX_COMPAT_OK"
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_REASONING = "high"

PROMPT = f"""You are a compatibility probe. Do not call tools or read files.
Examine only context that was already present before this prompt. Respond with
exactly {SENTINEL} and nothing else only if both conditions hold:
1. The full tradecraft charter body was supplied at SessionStart, including the
   sentence 'Capability wrappers are deliberately not in it.'
2. The skill catalog contains all nine tradecraft cells, and each description
   reaches its final non-trigger clause rather than ending mid-description.
Otherwise respond with TRADECRAFT_CODEX_COMPAT_FAIL followed by a short reason.
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


def _capture(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


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
    matches = [
        plugin for plugin in payload.get("installed", [])
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
        "--skip-git-repo-check",
        "--color", "never",
        "--output-last-message", str(last_message),
        PROMPT,
    ]


def run_probe(codex: Path, *, model: str, reasoning: str) -> None:
    scratch = ROOT / ".tmp"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="codex-compat-", dir=scratch) as raw:
        base = Path(raw)
        consumer = base / "consumer"
        consumer.mkdir()
        last_message = base / "last-message.txt"
        command = build_probe_command(
            codex, consumer, last_message, model=model, reasoning=reasoning
        )
        result = _capture(command, cwd=consumer)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise CompatError(f"nested Codex session failed ({result.returncode}): {detail}")
        if not last_message.is_file():
            raise CompatError("nested Codex session wrote no final-message record")
        answer = last_message.read_text(encoding="utf-8").strip()
        if answer != SENTINEL:
            raise CompatError(f"nested Codex session reported: {answer or '<empty>'}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prove the installed tradecraft plugin in a real Codex session.",
        epilog=(
            "Preconditions: authenticated Codex CLI with network access; this "
            "tree's tradecraft version installed and enabled; its hook inspected "
            "and trusted through /hooks; a real Python interpreter on PATH."
        ),
    )
    parser.add_argument("--codex", help="Exact Codex executable; discovery is the default.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning", default=DEFAULT_REASONING)
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
            "sandbox=read-only ephemeral=true consumer=empty"
        )
        run_probe(codex, model=args.model, reasoning=args.reasoning)
    except CompatError as exc:
        print(f"codex-compat: FAIL: {exc}", file=sys.stderr)
        return 1
    print("codex-compat: PASS: trusted hook and nine skill descriptions reached the session")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Find seat CLIs without depending on a runtime or the source checkout."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Callable, Mapping


class CliError(RuntimeError):
    """A CLI path or launch configuration cannot be used."""


class CliNotFound(CliError):
    """The vendor is not installed in a discoverable location."""


def which_on_path(command: str) -> str | None:
    """Honor PATH without Windows implicitly prepending the current directory."""
    if os.name != "nt":
        return shutil.which(command)
    configured = os.environ.get("PATH", "")
    if not configured:
        return None
    for directory in configured.split(os.pathsep):
        # A qualified candidate bypasses which()'s implicit cwd search. An
        # explicit empty/relative PATH entry still has its configured meaning.
        candidate = shutil.which(str(Path(directory).resolve() / command))
        if candidate:
            return candidate
    return None


def resolve_codex(
    explicit: str | None,
    *,
    env: Mapping[str, str] | None = None,
    path_lookup: Callable[[str], str | None] = which_on_path,
    platform: str = os.name,
) -> Path:
    """Resolve Codex explicitly, from PATH, or from the Windows app bundle."""
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.is_file():
            return candidate.resolve()
        raise CliError(f"--codex does not name a file: {candidate}")
    on_path = path_lookup("codex")
    if on_path and Path(on_path).is_file():
        return Path(on_path).resolve()
    values = os.environ if env is None else env
    if platform == "nt" and values.get("LOCALAPPDATA"):
        bundle = Path(values["LOCALAPPDATA"]) / "OpenAI" / "Codex" / "bin"
        candidates = [path for path in bundle.glob("*/codex.exe") if path.is_file()]
        if candidates:
            return max(candidates, key=lambda path: (
                path.stat().st_mtime_ns, str(path).casefold()
            )).resolve()
    raise CliNotFound(
        "Codex CLI not found: pass --codex, put it on PATH, or install the "
        "Windows Codex app bundle"
    )


def resolve_claude(explicit: str | None) -> Path:
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.is_file():
            return candidate.resolve()
        raise CliError(f"--claude does not name a file: {candidate}")
    on_path = which_on_path("claude")
    if on_path and Path(on_path).is_file():
        return Path(on_path).resolve()
    raise CliNotFound("Claude CLI not found: install Claude or pass --claude PATH")


def executable_command(vendor: str, path: Path, *, platform: str = os.name) -> list[str]:
    """Resolve npm's Windows launcher to its payload; never invoke a batch shell."""
    if platform != "nt" or path.suffix.lower() not in {".cmd", ".bat", ".ps1"}:
        return [str(path)]
    package = path.parent / "node_modules" / (
        "@anthropic-ai/claude-code" if vendor == "claude" else "@openai/codex"
    )
    native = package / "bin" / f"{vendor}.exe"
    if native.is_file():
        return [str(native)]
    script = package / ("cli.js" if vendor == "claude" else "bin/codex.js")
    node = path.parent / "node.exe"
    node_path = str(node) if node.is_file() else which_on_path("node")
    if node_path and Path(node_path).suffix.lower() in {".cmd", ".bat", ".ps1"}:
        raise CliError("Node must be a native executable; batch shells are not used.")
    if script.is_file() and node_path:
        return [node_path, str(script)]
    raise CliError(
        f"Cannot resolve {vendor}'s Windows shim {path}. "
        f"Pass --{vendor} with the native executable path; batch shells are not used."
    )


def resolve_command(vendor: str, explicit: str | None) -> list[str]:
    path = resolve_codex(explicit) if vendor == "codex" else resolve_claude(explicit)
    return executable_command(vendor, path)

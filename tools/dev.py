#!/usr/bin/env python3
"""Set up a worktree and run its checks with its own Python environment."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
from winio import utf8_stdio  # noqa: E402


def environment_python(root: Path) -> Path:
    folder = "Scripts" if os.name == "nt" else "bin"
    name = "python.exe" if os.name == "nt" else "python"
    return root / ".venv" / folder / name


def require_version(root: Path) -> str:
    wanted = (root / ".python-version").read_text(encoding="utf-8").strip()
    actual = f"{sys.version_info.major}.{sys.version_info.minor}"
    if actual != wanted:
        raise RuntimeError(
            f"Use Python {wanted}; this command is running {actual}. "
            f"On Windows run: py -{wanted} tools/dev.py setup. "
            f"On Linux/macOS run: python{wanted} tools/dev.py setup."
        )
    return wanted


def verify_environment(root: Path, wanted: str) -> Path:
    folder = root / ".venv"
    python = environment_python(root)
    if not folder.exists():
        raise RuntimeError("No worktree environment. Run: python tools/dev.py setup")
    recovery = "Move it aside, then run: python tools/dev.py setup. Nothing was deleted."
    if not python.is_file():
        raise RuntimeError("The existing .venv has no interpreter. " + recovery)
    try:
        config = {}
        for line in (folder / "pyvenv.cfg").read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator:
                config[key.strip().lower()] = value.strip().lower()
        result = subprocess.run(
            [str(python), "-c", "import json, sys; print(json.dumps({"
             "'version': f'{sys.version_info.major}.{sys.version_info.minor}', "
             "'prefix': sys.prefix, 'base_prefix': sys.base_prefix}))"],
            cwd=root, stdin=subprocess.DEVNULL, capture_output=True,
            encoding="utf-8", errors="replace", check=True,
        )
        info = json.loads(result.stdout)
        version = info["version"]
        isolated = (config.get("include-system-site-packages") == "false"
                    and Path(info["prefix"]).resolve() == folder.resolve()
                    and info["prefix"] != info["base_prefix"])
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("Cannot use the existing .venv. " + recovery) from exc
    if version != wanted:
        raise RuntimeError(
            f"The existing .venv does not use Python {wanted}. " + recovery
        )
    if not isolated:
        raise RuntimeError("The existing .venv is not an isolated worktree environment. " + recovery)
    return python


def setup(root: Path, wanted: str) -> int:
    folder = root / ".venv"
    if folder.exists():
        python = verify_environment(root, wanted)
    else:
        require_version(root)
        venv.EnvBuilder(with_pip=True).create(folder)
        python = verify_environment(root, wanted)
    subprocess.run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check",
         "-r", str(root / "requirements-dev.txt")], cwd=root, check=True,
    )
    print("Environment ready. Run: python tools/dev.py check")
    return 0


def run_checks(root: Path, python: Path, action: str, extra: list[str]) -> int:
    if action in {"lint", "check"}:
        for script in ("lint.py", "check_version_bump.py"):
            result = subprocess.run([str(python), str(root / "tools" / script)], cwd=root)
            if result.returncode:
                return result.returncode
        if action == "lint":
            return 0
    # Stay outside the checkout: fixtures testing non-repository behavior must
    # not discover this worktree's .git by walking up from their scratch path.
    # Each invocation owns its parent, so parallel cleanup cannot cross runs.
    scratch = Path(os.environ.get("PYTEST_DEBUG_TEMPROOT") or tempfile.gettempdir()).resolve()
    if scratch.is_relative_to(root.resolve()):
        raise RuntimeError(
            "Test temporary storage must be outside this checkout. "
            "Set PYTEST_DEBUG_TEMPROOT to an external writable directory."
        )
    with tempfile.TemporaryDirectory(prefix="tradecraft-pytest-", dir=scratch) as base:
        env = os.environ.copy()
        env["PYTEST_DEBUG_TEMPROOT"] = base
        return subprocess.run(
            [str(python), "-m", "pytest", *(extra or ["tools/tests", "skills", "-q"])],
            cwd=root, env=env,
        ).returncode


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(description="Set up and validate this worktree.")
    parser.add_argument("action", choices=("setup", "test", "lint", "check"))
    args, extra = parser.parse_known_args(argv)
    if extra and args.action != "test":
        parser.error("additional arguments are supported only for test")
    try:
        wanted = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
        if args.action == "setup":
            return setup(ROOT, wanted)
        return run_checks(ROOT, verify_environment(ROOT, wanted), args.action, extra)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"dev: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

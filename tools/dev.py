#!/usr/bin/env python3
"""Set up a worktree and run its checks with its own Python environment."""
from __future__ import annotations

import argparse
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
    python = environment_python(root)
    if not python.is_file():
        raise RuntimeError("No worktree environment. Run: python tools/dev.py setup")
    result = subprocess.run(
        [str(python), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
        cwd=root, stdin=subprocess.DEVNULL, capture_output=True,
        encoding="utf-8", errors="replace", check=True,
    )
    if result.stdout.strip() != wanted:
        raise RuntimeError(
            f"The existing .venv does not use Python {wanted}. "
            "Move it aside, then run setup with the required Python. Nothing was deleted."
        )
    return python


def setup(root: Path, wanted: str) -> int:
    folder = root / ".venv"
    if folder.exists():
        python = verify_environment(root, wanted)
    else:
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
    with tempfile.TemporaryDirectory(
        prefix="tradecraft-pytest-", dir=os.environ.get("PYTEST_DEBUG_TEMPROOT"),
    ) as base:
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
        wanted = require_version(ROOT)
        if args.action == "setup":
            return setup(ROOT, wanted)
        return run_checks(ROOT, verify_environment(ROOT, wanted), args.action, extra)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"dev: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

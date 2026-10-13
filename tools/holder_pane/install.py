#!/usr/bin/env python3
"""Install or uninstall the lab-only holder pane in one checkout, at local scope.

Lab tooling (#888). Every Claude Code CLI call this makes carries
`--scope local`, so nothing reaches user settings and no builder or seat
launched with `--setting-sources user` loads the mod. The hooks-module opt-in
goes in the same checkout's `.claude/settings.local.json`, which must be
untracked and ignored there: a checkout that tracks it (Windgust, until it
stops) is refused before any command runs.

    python tools/holder_pane/install.py install --checkout <main checkout>
    python tools/holder_pane/install.py uninstall --checkout <main checkout>
    python tools/holder_pane/install.py install --worktree <existing holder worktree>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
MARKETPLACE_DIR = HERE / "marketplace"
MARKETPLACE = "tradecraft-lab"
PLUGIN = "holder-pane"
PLUGIN_REF = f"{PLUGIN}@{MARKETPLACE}"
OPT_IN = "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS"
LOCAL = Path(".claude") / "settings.local.json"
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

Runner = Callable[..., Any]


class Refused(Exception):
    """The checkout cannot take a local-scope install without touching history."""


def newest_desktop_claude(environ: dict[str, str] | None = None) -> Path | None:
    """The newest desktop-app Claude Code: the runtime holder sessions load in."""
    environ = environ if environ is not None else dict(os.environ)
    appdata = environ.get("APPDATA")
    if not appdata:
        return None
    base = Path(appdata) / "Claude" / "claude-code"
    found = []
    try:
        for version in base.iterdir():
            if not VERSION.match(version.name):
                continue
            for build in version.iterdir():
                exe = build / "claude.exe"
                if exe.is_file():
                    found.append((tuple(int(part) for part in version.name.split(".")), exe))
    except OSError:
        return None
    return max(found)[1] if found else None


def _git(runner: Runner, checkout: Path, *args: str) -> int:
    completed = runner(["git", "-C", str(checkout), *args], stdin=subprocess.DEVNULL,
                       capture_output=True)
    return int(completed.returncode)


def check_local_file(checkout: Path, runner: Runner = subprocess.run) -> None:
    """Refuse unless `.claude/settings.local.json` is untracked and ignored there."""
    relative = LOCAL.as_posix()
    if _git(runner, checkout, "ls-files", "--error-unmatch", "--", relative) == 0:
        raise Refused(f"{checkout}: {relative} is tracked; installing would put a lab-only "
                      f"setting into its history (row 8). Stop tracking it first.")
    if _git(runner, checkout, "check-ignore", "-q", "--", relative) != 0:
        raise Refused(f"{checkout}: {relative} is not ignored; add it to .gitignore first.")


def _read_settings(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes().decode("utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict):
        raise Refused(f"{path} does not hold a JSON object")
    return value


def _write_settings(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2) + "\n").encode("utf-8"))


def _install_record_path() -> Path:
    return Path.home() / ".tradecraft" / "status" / ".pane" / "installs.json"


def _install_records() -> dict[str, Any]:
    try:
        value = json.loads(_install_record_path().read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _remember(checkout: Path, added_opt_in: bool) -> None:
    records = _install_records()
    records[str(checkout)] = {"added_opt_in": added_opt_in}
    path = _install_record_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(records, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _forget(checkout: Path) -> bool:
    """Drop the checkout's install record; answer whether this installer added the opt-in."""
    records = _install_records()
    record = records.pop(str(checkout), None)
    path = _install_record_path()
    if path.exists():
        path.write_bytes((json.dumps(records, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return isinstance(record, dict) and record.get("added_opt_in") is True


def set_opt_in(path: Path) -> bool:
    """Set the opt-in; answer whether it was absent before (so this installer added it)."""
    settings = _read_settings(path)
    env = settings.get("env")
    env = dict(env) if isinstance(env, dict) else {}
    added = OPT_IN not in env
    env[OPT_IN] = "1"
    settings["env"] = env
    _write_settings(path, settings)
    return added


def clear_opt_in(path: Path) -> None:
    if not path.exists():
        return
    settings = _read_settings(path)
    env = settings.get("env")
    if isinstance(env, dict) and OPT_IN in env:
        env = {key: value for key, value in env.items() if key != OPT_IN}
        if env:
            settings["env"] = env
        else:
            settings.pop("env", None)
        _write_settings(path, settings)


def _claude(runner: Runner, claude: Path, checkout: Path, *args: str) -> None:
    argv = [str(claude), *args]
    completed = runner(argv, cwd=str(checkout), stdin=subprocess.DEVNULL, capture_output=True)
    if completed.returncode != 0:
        detail = completed.stderr
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="replace")
        raise RuntimeError(f"{' '.join(args)} exited {completed.returncode}: {detail}".strip())


def install(checkout: Path, claude: Path, runner: Runner = subprocess.run,
            marketplace: Path = MARKETPLACE_DIR) -> None:
    check_local_file(checkout, runner)
    _claude(runner, claude, checkout, "plugin", "marketplace", "add", str(marketplace),
            "--scope", "local")
    _claude(runner, claude, checkout, "plugin", "install", PLUGIN_REF, "--scope", "local")
    added = set_opt_in(checkout / LOCAL)
    # A reinstall keeps the first install's answer: the opt-in it found is not its own.
    if str(checkout) not in _install_records():
        _remember(checkout, added)


def uninstall(checkout: Path, claude: Path, runner: Runner = subprocess.run) -> None:
    _claude(runner, claude, checkout, "plugin", "uninstall", PLUGIN_REF, "--scope", "local")
    _claude(runner, claude, checkout, "plugin", "marketplace", "remove", MARKETPLACE,
            "--scope", "local")
    # Other function hooks in the checkout may rely on an opt-in that predates this install.
    if _forget(checkout):
        clear_opt_in(checkout / LOCAL)


def install_worktree(worktree: Path, main_checkout: Path, runner: Runner = subprocess.run) -> None:
    """Copy the main checkout's install keys into an existing worktree's local file."""
    check_local_file(worktree, runner)
    source = _read_settings(main_checkout / LOCAL)
    plugins = source.get("enabledPlugins")
    marketplaces = source.get("extraKnownMarketplaces")
    if not (isinstance(plugins, dict) and plugins.get(PLUGIN_REF) is True
            and isinstance(marketplaces, dict) and MARKETPLACE in marketplaces):
        raise Refused(f"{main_checkout}: no enabled {PLUGIN_REF} install found in "
                      f"{LOCAL.as_posix()}; install the main checkout first.")
    target_path = worktree / LOCAL
    target = _read_settings(target_path)
    for key, name, entry in (("extraKnownMarketplaces", MARKETPLACE, marketplaces[MARKETPLACE]),
                             ("enabledPlugins", PLUGIN_REF, True)):
        merged = dict(target.get(key) or {})
        merged[name] = entry
        target[key] = merged
    env = dict(target.get("env") or {})
    env[OPT_IN] = "1"
    target["env"] = env
    _write_settings(target_path, target)


def _main_checkout(worktree: Path, runner: Runner) -> Path:
    completed = runner(["git", "-C", str(worktree), "rev-parse", "--path-format=absolute",
                        "--git-common-dir"], stdin=subprocess.DEVNULL, capture_output=True)
    text = completed.stdout.decode("utf-8") if isinstance(completed.stdout, bytes) else str(
        completed.stdout)
    if completed.returncode != 0 or not text.strip():
        raise Refused(f"{worktree}: not a git worktree")
    return Path(text.strip()).parent


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", newline="")
    parser = argparse.ArgumentParser(
        description="Install or uninstall the lab-only holder pane at local scope.")
    parser.add_argument("action", choices=("install", "uninstall"))
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--checkout", type=Path, help="a lab repository's main checkout")
    where.add_argument("--worktree", type=Path,
                       help="an existing holder worktree (install only): copy the keys")
    parser.add_argument("--claude", type=Path,
                        help="the Claude Code executable (default: the newest desktop one)")
    args = parser.parse_args(argv)
    try:
        if args.worktree is not None:
            if args.action != "install":
                parser.error("--worktree is for install only")
            worktree = args.worktree.resolve()
            install_worktree(worktree, _main_checkout(worktree, subprocess.run))
            print(f"installed in {worktree}; restart that session")
            return 0
        claude = args.claude or newest_desktop_claude()
        if claude is None:
            print("no desktop Claude Code found; pass --claude", file=sys.stderr)
            return 2
        checkout = args.checkout.resolve()
        if args.action == "install":
            install(checkout, claude)
        else:
            uninstall(checkout, claude)
    except (Refused, RuntimeError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    print(f"{args.action}ed {PLUGIN_REF} at local scope in {checkout}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

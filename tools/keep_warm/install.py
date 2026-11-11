#!/usr/bin/env python3
"""Install or uninstall the lab-only desktop keep-warm in one checkout, at local scope.

Design: tools/keep_warm/README.md#install

Lab tooling (#983). The steps and refusals are the holder pane's installer's,
run under this mod's own names: the marketplace `tradecraft-keep-warm` and the
plugin `keep-warm`, so no install here can repoint the Steward's wake
(`steward-wake@tradecraft-lab`) or the pane (`holder-pane@tradecraft-holder-pane`).
Every call carries `--scope local`; the hooks-module opt-in goes in the
checkout's `.claude/settings.local.json`, which must be untracked and ignored.

    python tools/keep_warm/install.py install --checkout <main checkout>
    python tools/keep_warm/install.py uninstall --checkout <main checkout>
"""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKETPLACE_DIR = HERE / "marketplace"
MARKETPLACE = "tradecraft-keep-warm"
PLUGIN = "keep-warm"
PLUGIN_REF = f"{PLUGIN}@{MARKETPLACE}"


def _load_mechanics():
    """The pane installer's shared mechanics; tools/ is no package, so it is loaded by path."""
    path = HERE.parent / "holder_pane" / "install.py"
    spec = importlib.util.spec_from_file_location("holder_pane_install_mechanics", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mechanics = _load_mechanics()
Refused = mechanics.Refused
OPT_IN = mechanics.OPT_IN
Runner = mechanics.Runner


def _install_record_path() -> Path:
    return Path.home() / ".tradecraft-lab" / "keep-warm" / "installs.json"


def install(checkout: Path, claude: Path, runner: Runner = subprocess.run,
            marketplace: Path = MARKETPLACE_DIR) -> None:
    mechanics.install_mod(checkout, claude, runner, marketplace_dir=marketplace,
                          marketplace=MARKETPLACE, plugin=PLUGIN,
                          records=_install_record_path())


def uninstall(checkout: Path, claude: Path, runner: Runner = subprocess.run) -> list[str]:
    """Uninstall here; keep the shared marketplace while another checkout still has the mod."""
    return mechanics.uninstall_mod(checkout, claude, runner, marketplace=MARKETPLACE,
                                   plugin=PLUGIN, records=_install_record_path())


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", newline="")
    parser = argparse.ArgumentParser(
        description="Install or uninstall the lab-only desktop keep-warm at local scope.")
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--checkout", type=Path, required=True,
                        help="a practice repository's main checkout")
    parser.add_argument("--claude", type=Path,
                        help="the Claude Code executable (default: the newest desktop one)")
    args = parser.parse_args(argv)
    claude = args.claude or mechanics.newest_desktop_claude()
    if claude is None:
        print("no desktop Claude Code found; pass --claude", file=sys.stderr)
        return 2
    checkout = args.checkout.resolve()
    try:
        if args.action == "install":
            install(checkout, claude)
        else:
            for message in uninstall(checkout, claude):
                print(message)
    except (Refused, RuntimeError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    print(f"{args.action}ed {PLUGIN_REF} at local scope in {checkout}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

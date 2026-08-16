#!/usr/bin/env python3
"""Shipped-zone changes must bump the plugin version (ADR-003).

The version is a consumer's only signal that their installed copy differs from
current, so a shipped-zone edit that leaves it alone ships silently. ADR-003
states the rule and deferred the guard until a third instance proved recurrence;
that condition was met on PR #4, where the rule's own author broke it on the PR
after writing it. Rows: `source: pr4-standard-2026-08-16` in docs/ledger.jsonl.

Compares the working tree against a base ref (default `origin/main`): if any
shipped-zone path differs, `.claude-plugin/plugin.json`'s version must differ
too. Deliberately narrow — it asks only "did this number change", never whether
the change was the right size, because semver judgment is not checkable and
ADR-002 keeps unstable rules out of code.

Usage: python tools/check_version_bump.py [base-ref]
Exit 0 when clean or when the base ref is unavailable, 1 with the finding.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHIPPED_DIRS = ("skills", "lib", "commands", "agents", ".claude-plugin")
MANIFEST = ".claude-plugin/plugin.json"


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.stdout.strip()


def _version_at(ref: str) -> str | None:
    blob = _git("show", f"{ref}:{MANIFEST}")
    return _version_of(blob)


def _version_now() -> str | None:
    """The working tree's version, so the guard is usable before committing —
    AGENTS.md tells authors to run their checks first, and a guard that only
    answers after the commit answers too late to act on."""
    path = ROOT / MANIFEST
    if not path.is_file():
        return None
    return _version_of(path.read_text(encoding="utf-8"))


def _version_of(blob: str | None) -> str | None:
    if blob is None:
        return None
    try:
        return json.loads(blob).get("version")
    except json.JSONDecodeError:
        return None


def run(base: str = "origin/main") -> list[str]:
    changed = _git("diff", "--name-only", base)
    if changed is None:
        return []  # no base to compare against (shallow clone, fork, no git)
    paths = [p for p in changed.splitlines() if p.strip()]
    shipped = [
        p for p in paths
        if any(p == d or p.startswith(d + "/") for d in SHIPPED_DIRS)
        and p != MANIFEST
    ]
    if not shipped:
        return []
    before, after = _version_at(base), _version_now()
    if before is None or after is None or before != after:
        return []
    return [
        f"version-bump (ADR-003): {len(shipped)} shipped-zone file(s) changed "
        f"against {base} while {MANIFEST} stayed at {after} - a consumer cannot "
        f"tell their copy is stale. First changed: {shipped[0]}"
    ]


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    findings = run(base)
    for f in findings:
        print(f)
    print(f"version-bump: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

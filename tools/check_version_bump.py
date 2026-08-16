#!/usr/bin/env python3
"""ADR-003 §25: a PR touching the shipped zone bumps the plugin version.

Measured as **the pull request against its merge base**, never per-commit: this
repo squash-merges, so the PR is the commit that lands, and a per-commit reading
fails every intermediate commit of a multi-commit branch. A first attempt at this
guard enforced per-branch while citing per-commit; the mismatch was a review
finding, and ADR-003 was corrected rather than the guard.

Three outcomes, not two — and the third is why this exists at all:

    0  pass          shipped zone untouched, or touched and the version rose
    1  fail          shipped zone touched and the version did not rise
    2  undetermined  the question could not be answered

**Undetermined is a failure.** The withdrawn predecessor went silent whenever
its merge base had moved — a state every merge into the base produces, so its
most common real condition was the one it could not see — and printed the same
line as a clean pass. Four failure modes were invisible that way. Anything this
script cannot establish, it says out loud and exits non-zero.

Usage:  python tools/check_version_bump.py [--base REF]
Default base is origin/main, then main.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ".claude-plugin/plugin.json"
# ADR-004's shipped zone. The manifest itself is excluded: bumping the version
# is what this guard demands, so counting it as a shipped-zone change would make
# every bump its own justification.
SHIPPED = ("skills/", "lib/", "commands/", "agents/", ".claude-plugin/")

PASS, FAIL, UNDETERMINED = 0, 1, 2


def _git(*args: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, (proc.stdout or "").strip()


def _resolve_base(explicit: str | None) -> tuple[str | None, str]:
    """Return (merge-base sha, reason). A None sha means undetermined."""
    candidates = [explicit] if explicit else ["origin/main", "main"]
    tried = []
    for ref in candidates:
        code, _ = _git("rev-parse", "--verify", f"{ref}^{{commit}}")
        if code != 0:
            tried.append(f"{ref} does not resolve")
            continue
        code, sha = _git("merge-base", "HEAD", ref)
        if code != 0 or not sha:
            tried.append(f"no merge base between HEAD and {ref}")
            continue
        return sha, f"merge base with {ref} is {sha[:7]}"
    return None, "; ".join(tried) or "no base ref given"


def _parse_semver(raw: object) -> tuple[int, ...] | None:
    if not isinstance(raw, str):
        return None
    parts = raw.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def _version_at(ref: str | None) -> tuple[tuple[int, ...] | None, str]:
    """Version at a ref, or in the working tree when ref is None."""
    if ref is None:
        path = ROOT / MANIFEST
        if not path.is_file():
            return None, f"{MANIFEST} is absent from the working tree"
        text = path.read_text(encoding="utf-8")
    else:
        code, text = _git("show", f"{ref}:{MANIFEST}")
        if code != 0:
            return None, f"{MANIFEST} is absent at {ref[:7]}"
    try:
        raw = json.loads(text).get("version")
    except json.JSONDecodeError as exc:
        return None, f"{MANIFEST} is not valid JSON ({exc.msg})"
    parsed = _parse_semver(raw)
    if parsed is None:
        return None, f"version {raw!r} is not a three-part numeric semver"
    return parsed, ""


def check(base_ref: str | None = None) -> tuple[int, list[str]]:
    lines: list[str] = []
    base, why = _resolve_base(base_ref)
    if base is None:
        return UNDETERMINED, [f"version-bump (ADR-003): cannot determine a base — {why}"]

    # Two independent mechanisms give the moved-base answer, and either alone
    # suffices: `base` is resolved to a merge base above, AND `...` re-derives
    # one here. Verified by mutation — replacing the merge-base resolution with
    # the ref tip keeps every test green, because `...` rescues it. Redundant on
    # purpose; the withdrawn predecessor had neither and went silent on exactly
    # this state, which every merge into the base produces.
    code, out = _git("diff", "--name-only", f"{base}...HEAD")
    if code != 0:
        return UNDETERMINED, [f"version-bump (ADR-003): could not diff against {base[:7]}"]
    changed = [f for f in out.splitlines() if f.strip()]
    touched = sorted(
        f for f in changed
        if any(f.startswith(p) for p in SHIPPED) and f != MANIFEST
    )
    if not touched:
        return PASS, [f"version-bump (ADR-003): shipped zone untouched ({why})"]

    old, old_err = _version_at(base)
    new, new_err = _version_at(None)
    if old is None:
        return UNDETERMINED, [f"version-bump (ADR-003): base version unreadable — {old_err}"]
    if new is None:
        return UNDETERMINED, [f"version-bump (ADR-003): current version unreadable — {new_err}"]

    shown = ".".join(map(str, old)), ".".join(map(str, new))
    if new > old:
        lines.append(
            f"version-bump (ADR-003): {len(touched)} shipped-zone file(s) changed, "
            f"version {shown[0]} -> {shown[1]} ({why})"
        )
        return PASS, lines
    verb = "unchanged at" if new == old else f"went BACKWARDS {shown[0]} -> "
    lines.append(
        f"version-bump (ADR-003): {len(touched)} shipped-zone file(s) changed but "
        f"the plugin version {verb}{shown[1] if new == old else shown[1]} — "
        f"a consumer cannot tell installed from current"
    )
    lines.extend(f"    {f}" for f in touched)
    return FAIL, lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=None, help="base ref (default: origin/main, then main)")
    args = parser.parse_args(argv)
    status, lines = check(args.base)
    for line in lines:
        print(line)
    if status == UNDETERMINED:
        print("version-bump (ADR-003): UNDETERMINED is a failure, not a pass — see ADR-003 §25")
    return status


if __name__ == "__main__":
    sys.exit(main())

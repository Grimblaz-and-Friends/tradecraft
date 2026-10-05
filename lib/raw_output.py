"""Report repository-declared raw-output paths without changing merge proof."""
from __future__ import annotations

import fnmatch
import json
from pathlib import Path


STATUSES = frozenset({"added", "modified", "changed", "copied", "renamed", "removed", "unchanged"})
REFUSALS = frozenset({"blocked", "unverifiable"})


def declaration(policy: dict, source: str) -> list[str]:
    patterns = policy.get("raw_output_patterns", [])
    if not isinstance(patterns, list) or any(
            not isinstance(pattern, str) or not pattern.strip() for pattern in patterns):
        raise ValueError(
            f"raw_output_patterns must be an array of nonblank strings: {source}"
        )
    return list(patterns)


def report(status: str, message: str, source: str | None,
           patterns=(), paths=()) -> dict[str, object]:
    return {"status": status, "message": message, "policy": source,
            "patterns": list(patterns), "paths": list(paths)}


def _path(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        return None
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or any(part in {"", ".", ".."} for part in normalized.split("/")):
        return None
    return normalized


def evaluate(policy: dict, source: str, *, pr: dict | None = None,
             files: list | None = None, inventory_error: str | None = None) -> dict[str, object]:
    try:
        patterns = declaration(policy, source)
    except ValueError as exc:
        return report("unverifiable", str(exc), source)
    if not patterns:
        return report("undeclared", "No raw-output patterns are declared.", source)
    if pr is None:
        return report("not-evaluated", "No implementing pull-request inventory to check.", source, patterns)

    def uncertain(reason):
        return report("unverifiable", reason + "; recollect the PR file inventory and retry.", source, patterns)

    if inventory_error:
        return uncertain(inventory_error)
    count = pr.get("changed_files")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        return uncertain("Pull request changed_files is missing or invalid")
    if files is None or len(files) != count:
        return uncertain(f"Pull request reports {count} changed files; retrieved {len(files) if files is not None else 'no inventory'}")
    seen: set[str] = set()
    matched: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            return uncertain("PR file record is not an object")
        name = _path(item.get("filename"))
        if name is None:
            return uncertain("PR file record has no usable filename")
        if name in seen:
            return uncertain(f"Duplicate PR filename: {name}")
        seen.add(name)
        status = item.get("status")
        if not isinstance(status, str) or status not in STATUSES:
            return uncertain(f"Missing or unknown PR file status for {name}: {status!r}")
        if status == "removed":
            continue
        names = [name]
        if status == "renamed":
            previous = _path(item.get("previous_filename"))
            if previous is None:
                return uncertain(f"Renamed PR file has no previous_filename: {name}")
            names.append(previous)
        matched.update(path for path in names if any(
            fnmatch.fnmatchcase(path, pattern) for pattern in patterns
        ))
    if matched:
        paths = sorted(matched)
        return report("blocked", "Declared raw-output paths changed: " + ", ".join(paths), source, patterns, paths)
    return report("clear", "No declared raw-output paths are added or changed.", source, patterns)


def inspect_policy(path: Path) -> dict[str, object]:
    """Registration/tree reporting never imposes use-policy prerequisites."""
    source = str(path)
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return evaluate({}, source)
    except OSError as exc:
        return report("unverifiable", f"Cannot read raw-output policy {source}: {exc}", source)
    try:
        policy = json.loads(content)
        if not isinstance(policy, dict):
            raise ValueError("policy must be an object")
    except (UnicodeError, ValueError) as exc:
        return report("unverifiable", f"Cannot parse raw-output policy {source}: {exc}", source)
    return evaluate(policy, source)

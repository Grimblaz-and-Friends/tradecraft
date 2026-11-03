#!/usr/bin/env python3
"""Refuse a launched Claude's file-tool writes outside its tree and scratchpad.

Usage (a PreToolUse command hook the launcher supplies in its own settings):
    python <plugin-root>/lib/tree_write_guard.py --config FILE

The config names the canonical tree, the session scratchpad and the decision
log. Every decision, allow or deny, is appended to that log so the launcher can
prove afterwards that each completed file-tool call was checked (#906).
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

from holder_tree_guard import contains, denial, path_key
from winio import utf8_stdio

FILE_TOOLS = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path",
              "NotebookEdit": "notebook_path"}
ENVIRONMENT_FORM = re.compile(r"%[^%]*%|\$[A-Za-z_{]")
DRIVE_RELATIVE = re.compile(r"[A-Za-z]:(?![\\/])")
LONG_SLUG_SUFFIX = re.compile(r"[0-9a-z]+")


class Refusal(ValueError):
    """The target cannot be decided by where the runtime will write it."""


def resolve_target(raw: str, cwd: str | None) -> Path:
    """Resolve a tool's raw target the way the runtime will, or refuse it.

    Forms whose runtime resolution could diverge from this one are refused
    rather than guessed, because refusing is the safe direction.
    """
    if not raw or "\x00" in raw:
        raise Refusal("empty target or a NUL character")
    if raw[:2] in {"\\\\", "//", "\\/", "/\\"}:
        raise Refusal("device, UNC or namespace path form")
    if DRIVE_RELATIVE.match(raw):
        raise Refusal("drive-relative path form")
    if raw.startswith("~") and len(raw) > 1 and raw[1] not in "/\\":
        raise Refusal("a '~' form other than the home directory")
    if ENVIRONMENT_FORM.search(raw):
        raise Refusal("an environment-variable form")
    if raw == "~" or raw[:2] in {"~/", "~\\"}:
        raw = os.path.expanduser(raw)
    candidate = Path(raw)
    if not candidate.is_absolute():
        if not cwd:
            raise Refusal("a relative target with no working directory in the hook input")
        candidate = Path(cwd) / candidate
    target = candidate.resolve(strict=False)
    try:
        status = target.lstat()
    except FileNotFoundError:
        return target
    if target.is_file() and status.st_nlink > 1:
        raise Refusal("hard-linked file")
    return target


def in_scratchpad(config: dict, target: Path) -> bool:
    exact = config.get("scratchpad")
    if config.get("scratchpad_form") != "long-prefix":
        return bool(exact) and contains(Path(exact), target)
    parent = Path(config["scratchpad_parent"])
    if not contains(parent, target) or path_key(parent) == path_key(target):
        return False
    parts = Path(os.path.relpath(path_key(target), path_key(parent))).parts
    prefix = os.path.normcase(config["scratchpad_slug_prefix"])
    if len(parts) < 3 or not parts[0].startswith(prefix):
        return False
    return (LONG_SLUG_SUFFIX.fullmatch(parts[0][len(prefix):]) is not None
            and parts[1] == os.path.normcase(config["session"])
            and parts[2] == os.path.normcase("scratchpad"))


def decide(payload: dict, config: dict) -> dict[str, object]:
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    entry: dict[str, object] = {"tool": tool, "tool_use_id": payload.get("tool_use_id"),
                                "raw": None, "canonical": None}
    if tool not in FILE_TOOLS:
        return {**entry, "decision": "allow", "reason": "not a file-editing tool"}
    if not isinstance(tool_input, dict):
        raise Refusal("hook input has no object tool_input")
    raw = tool_input.get(FILE_TOOLS[tool])
    entry["raw"] = raw
    if not isinstance(raw, str):
        raise Refusal(f"{tool} input names no target path")
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    try:
        target = resolve_target(raw, cwd)
    except Refusal as exc:
        return {**entry, "decision": "deny",
                "reason": f"launch write bound: {tool} target {raw} refused: {exc}"}
    entry["canonical"] = str(target)
    root = Path(config["root"])
    if contains(root, target) or in_scratchpad(config, target):
        return {**entry, "decision": "allow", "reason": "inside the tree or session scratchpad"}
    scratchpad = config.get("scratchpad") or config.get("scratchpad_pattern")
    return {**entry, "decision": "deny",
            "reason": (f"launch write bound: {tool} target {raw} resolves to {target}, "
                       f"outside tree {root} and scratchpad {scratchpad}")}


def append_log(path: str, entry: dict[str, object]) -> None:
    with open(path, "ab") as stream:
        stream.write((json.dumps(entry, ensure_ascii=True) + "\n").encode("utf-8"))
        stream.flush()


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    cli = argparse.ArgumentParser(description="Launch write bound PreToolUse hook.")
    cli.add_argument("--config", required=True)
    args = cli.parse_args(argv)
    config: dict = {}
    entry: dict[str, object] = {"tool": None, "tool_use_id": None, "raw": None, "canonical": None}
    try:
        config = json.loads(Path(args.config).read_bytes())
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        if not isinstance(payload, dict) or not isinstance(config, dict):
            raise Refusal("hook input and config must be JSON objects")
        entry.update(tool=payload.get("tool_name"), tool_use_id=payload.get("tool_use_id"))
        entry = decide(payload, config)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        # Fail closed, as the holder guard does: an unevaluated call is refused.
        entry = {**entry, "decision": "deny",
                 "reason": f"launch write bound could not evaluate this tool call: {exc}"}
    log = config.get("log") if isinstance(config, dict) else None
    if isinstance(log, str) and entry.get("tool") in FILE_TOOLS:
        try:
            append_log(log, entry)
        except OSError:
            pass  # An allow without a logged decision fails the turn afterwards.
    if entry["decision"] == "deny":
        print(json.dumps(denial(str(entry["reason"])), ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

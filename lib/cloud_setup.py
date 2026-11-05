#!/usr/bin/env python3
"""One-time cloud setup for a product repository: the create body and its read-back check.

Usage: python <plugin-root>/lib/cloud_setup.py body --repo OWNER/REPO --environment ENV_ID
           [--practice-repo R] [--practice-branch B]
       python <plugin-root>/lib/cloud_setup.py verify --repo OWNER/REPO --environment ENV_ID
           --readback FILE --phase created|complete [--token-file PATH] [--routine-id ID]
           [--practice-repo R] [--practice-branch B]

The holder creates and reads the routine with its RemoteTrigger tool; this
script writes what is sent and makes "differs from what was sent" mechanical.
Only a clean ``complete`` writes the machine record entry (#938 row 3).
Design: <plugin-root>/skills/work/references/cloud-builds.md.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

import cloud_build as cloud
from winio import utf8_stdio

DEFAULT_PRACTICE = "Grimblaz-and-Friends/tradecraft"
EXCLUDES = ["/CLAUDE.md", "/AGENTS.md", "/.claude/"]


class SetupError(RuntimeError):
    pass


def refuse_practice(repo: str, practice: str) -> None:
    if cloud.is_practice_repository(repo, practice):
        raise SetupError(cloud.PRACTICE_OWN_REFUSAL)


def _source(repository: str, revision: str | None = None, excludes: list[str] | None = None) -> dict:
    value: dict[str, object] = {"url": f"https://github.com/{repository}"}
    if revision is not None:
        value["revision"] = revision
    if excludes is not None:
        value["sparse_checkout_exclude_patterns"] = list(excludes)
    return {"git_repository": value}


def create_body(repo: str, environment: str, practice: str, branch: str) -> dict[str, object]:
    """The routine as the API stores it: no schedule, no connectors, two sources."""
    refuse_practice(repo, practice)
    prompt = cloud.ROUTINE_PROMPT.format(practice_name=cloud.practice_name(practice))
    return {
        "name": f"tradecraft builder: {repo}",
        "cron_expression": "",
        "clear_mcp_connections": True,
        "job_config": {"ccr": {
            "environment_id": environment,
            "events": [{"data": {
                "message": {"content": prompt, "role": "user"}, "parent_tool_use_id": None,
                "session_id": "", "type": "user",
                "uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"tradecraft-builder:{repo}"))}}],
            "session_context": {
                "sources": [_source(repo), _source(practice, branch, EXCLUDES)],
                "disallowed_tools": ["PushNotification"],
            },
        }},
    }


def _get(value: object, *path: object) -> object:
    for key in path:
        if isinstance(key, int):
            value = value[key] if isinstance(value, list) and len(value) > key else None
        else:
            value = value.get(key) if isinstance(value, dict) else None
    return value


def _sources(value: object) -> list[dict] | None:
    """Each source's url, revision and exclusions, whichever of the two forms it reads in."""
    if not isinstance(value, list):
        return None
    result = []
    for row in value:
        row = row.get("git_repository", row) if isinstance(row, dict) else {}
        result.append({"url": row.get("url"), "revision": row.get("revision") or None,
                       "sparse_checkout_exclude_patterns": sorted(row.get("sparse_checkout_exclude_patterns") or [])})
    return result


def compare(sent: dict, readback: dict, *, phase: str, token_file: str | None) -> list[str]:
    """Every difference between the sent body and the read-back, by field.

    The read-back paths are those a `RemoteTrigger get` returned on 2026-11-05;
    no field shows the API trigger, so the first launch proves it (AC-1.1, AC-2.2).
    """
    faults = []
    context = ("job_config", "ccr", "session_context")

    def differ(field, want, got):
        if want != got:
            faults.append(f"{field}: sent {json.dumps(want)[:200]}, read back {json.dumps(got)[:200]}")

    differ("name", sent["name"], readback.get("name"))
    if readback.get("mcp_connections") or _get(readback, "session_request", "config", "mcp_servers"):
        faults.append("connectors: sent none, read back " + json.dumps(
            readback.get("mcp_connections") or _get(readback, "session_request", "config", "mcp_servers"))[:200])
    for key in ("cron_expression", "run_once_at"):
        if readback.get(key):
            faults.append(f"{key}: sent none, read back {readback[key]}")
    differ("environment_id", _get(sent, "job_config", "ccr", "environment_id"),
           _get(readback, "job_config", "ccr", "environment_id"))
    differ("prompt", _get(sent, "job_config", "ccr", "events", 0, "data", "message", "content"),
           _get(readback, "job_config", "ccr", "events", 0, "data", "message", "content"))
    differ("sources", _sources(_get(sent, *context, "sources")), _sources(_get(readback, *context, "sources")))
    tools = _get(readback, *context, "disallowed_tools")
    if not isinstance(tools, list) or "PushNotification" not in tools:
        faults.append(f"disallowed_tools: sent ['PushNotification'], read back {tools}")
    if phase == "complete":
        model, effort = _get(readback, *context, "model"), _get(readback, *context, "effort_level")
        if model != cloud.PROFILE_MODEL:
            faults.append(f"model: required {cloud.PROFILE_MODEL}, read back {model}")
        if effort != cloud.PROFILE_EFFORT:
            faults.append(f"effort_level: required {cloud.PROFILE_EFFORT}, read back {effort}")
        if token_file is None:
            faults.append("token_file: required at complete")
        else:
            try:
                cloud.read_token(token_file)
            except cloud.CloudError as exc:
                faults.append(f"token_file: {exc}")
    return faults


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def ensure_pin(transport, practice: str, branch: str, commit: str) -> str:
    """Create the shared pin at the installed commit when it is absent; never move it here."""
    status, _value = transport.github("GET", f"repos/{practice}/git/ref/heads/{branch}")
    if status == 200:
        return "existing"
    if status != 404:
        raise SetupError(f"cannot read pin {practice}@{branch}: HTTP {status}")
    status, value = transport.github("POST", f"repos/{practice}/git/refs",
                                     {"ref": f"refs/heads/{branch}", "sha": commit})
    if status // 100 != 2:
        raise SetupError(f"cannot create pin {practice}@{branch}: HTTP {status} {str(value)[:200]}")
    return f"created at {commit}"


def verify(args, *, home: Path | None = None, transport=None, plugin: Path | None = None,
           install_path: Path | None = None) -> int:
    sent = create_body(args.repo, args.environment, args.practice_repo, args.practice_branch)
    text = Path(args.readback).read_text("utf-8")
    # A saved `RemoteTrigger get` response opens with its status line.
    readback = json.loads(text[text.index("{"):] if text.lstrip().startswith("HTTP") else text)
    if isinstance(readback, dict) and isinstance(readback.get("data"), list) and len(readback["data"]) == 1:
        readback = readback["data"][0]
    faults = compare(sent, readback, phase=args.phase, token_file=args.token_file)
    home = home or Path.home()
    owner, name = args.repo.split("/", 1)
    setup_path = home / ".tradecraft" / "cloud-setup" / f"{owner}__{name}.json"
    _write(setup_path, {"phase": args.phase, "sent": sent, "readback": readback, "diff": faults,
                        "verified_at": datetime.now(timezone.utc).isoformat()})
    if faults:
        for fault in faults:
            print(f"setup FAILED: {fault}", file=sys.stderr)
        return 1
    if args.phase == "created":
        print(f"setup created: read-back matches; record {setup_path}")
        return 0
    routine = args.routine_id or readback.get("id")
    if not isinstance(routine, str) or not routine:
        print("setup FAILED: routine id: none given or read back", file=sys.stderr)
        return 1
    practice = cloud.installed_practice(plugin or cloud.plugin_root(),
                                        install_path or cloud.install_record_path())
    pin = ensure_pin(transport or cloud.Transport(), args.practice_repo, args.practice_branch,
                     practice["commit"])
    path = cloud.record_path(home)
    record = cloud.read_record(path) or {"schema_version": cloud.RECORD_SCHEMA,
                                         "practice": {"repository": args.practice_repo,
                                                      "branch": args.practice_branch},
                                         "repositories": {}}
    if record["practice"] != {"repository": args.practice_repo, "branch": args.practice_branch}:
        print(f"setup FAILED: practice: record names {record['practice']}, setup names "
              f"{args.practice_repo}@{args.practice_branch}", file=sys.stderr)
        return 1
    record["repositories"][args.repo] = {
        "routine_id": routine, "token_file": str(Path(args.token_file).resolve()),
        "setup_record": str(setup_path), "set_up_at": datetime.now(timezone.utc).isoformat()}
    _write(path, record)
    print(f"setup complete: {args.repo} builds in the cloud; pin {pin}; record {path}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("body", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--repo", required=True)
        command.add_argument("--environment", required=True)
        command.add_argument("--practice-repo", default=DEFAULT_PRACTICE)
        command.add_argument("--practice-branch", default=cloud.DEFAULT_PIN_BRANCH)
        if name == "verify":
            command.add_argument("--readback", required=True)
            command.add_argument("--phase", choices=("created", "complete"), required=True)
            command.add_argument("--token-file")
            command.add_argument("--routine-id")
    return result


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    args = parser().parse_args(argv)
    try:
        if args.command == "body":
            print(json.dumps(create_body(args.repo, args.environment, args.practice_repo,
                                         args.practice_branch), indent=2))
            return 0
        return verify(args)
    except (SetupError, cloud.CloudError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

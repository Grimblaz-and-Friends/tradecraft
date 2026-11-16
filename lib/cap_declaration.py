"""The record of a declared preflight cap, written before the run's first read whatever the run does next.

A declaration file is not a bundle, so a refusal at the cap keeps it.
Design: lib/DESIGN.md#a-runs-window-and-the-entrances-cap
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

import dispatch_record as records
import run_lifecycle as lifecycle


def records_home() -> Path:
    """The entrance's records home: the dispatch store's parent, `~/.tradecraft` by default."""
    return records.default_record_root().expanduser().resolve().parent


def folder(home: Path, work: str) -> Path:
    repo, _, issue = work.partition("#")
    return Path(home) / "preflight-caps" / f"{repo.replace('/', '-')}-{issue}"


def write(home: Path, work: str, stage: str, deadline, window: dict) -> Path:
    """Write the declaration with an unknown outcome; called before the run's first read."""
    target = folder(home, work)
    target.mkdir(parents=True, exist_ok=True)
    stamp = re.sub(r"[^0-9TZ]", "", window["called_at"])
    path = target / f"{stamp}-{stage}-{os.getpid()}.json"
    record = {"schema_version": 1, "work": work, "stage": stage, "called_at": window["called_at"],
              "preflight_cap": deadline.cap_record(), "limit_seconds": deadline.limit,
              "latest_return_at": window["latest_return_at"],
              "producer_version": records.producer_version(), "outcome": None}
    # Exclusive creation, so two runs called in the same instant never overwrite one another.
    with path.open("xb") as stream:
        stream.write(records.json_bytes(record))
    return path


def outcome(path: Path | None, result: dict) -> None:
    """Add what the run did; a run stopped first leaves the outcome unset and the figure recorded."""
    if path is None:
        return
    try:
        record = json.loads(Path(path).read_bytes())
        record.update(result)
        sibling = Path(path).with_name(Path(path).name + ".tmp")
        sibling.write_bytes(records.json_bytes(record))
        os.replace(sibling, path)
    except (OSError, ValueError):
        pass


def read(home: Path, work: str) -> list[dict]:
    rows = []
    found = folder(home, work)
    for path in sorted(found.glob("*.json")) if found.is_dir() else []:
        try:
            record = json.loads(path.read_bytes())
        except (OSError, ValueError):
            continue
        if isinstance(record, dict):
            rows.append({"record": str(path), **{key: record.get(key) for key in (
                "stage", "called_at", "preflight_cap", "outcome", "bundle", "reason_code", "error")}})
    return rows


def launcher_run(args, deadline, body, label):
    """Run a launcher's body. Called directly, it records a declared cap and then prints its window first;
    started by the entrance it does neither, because the entrance's record and line cover the run."""
    path = None
    if getattr(args, "print_window", False):
        window = lifecycle.window_line(deadline)
        if deadline.cap_declared:
            path = write(records_home(), args.work, args.stage, deadline, window)
        window["cap_record"] = str(path) if path else None
        print(f"{label}: window " + json.dumps(window, ensure_ascii=True), flush=True)
    try:
        code = body()
    except BaseException as exc:
        cause = exc if isinstance(exc, lifecycle.PreflightCapExceeded) else exc.__cause__
        at_cap = isinstance(cause, lifecycle.PreflightCapExceeded)
        outcome(path, {"outcome": "refused-at-cap"} if at_cap else {"outcome": "failed", "error": str(exc)})
        if at_cap:
            try:
                lifecycle.write_launch_notice(getattr(args, "launch_notice", None), deadline, refused_at_cap=True)
            except OSError:
                pass  # The entrance then records a plain refusal; the launcher's own line names the cap.
        raise
    output = getattr(args, "output", None)
    if getattr(args, "request_recorded", False) and output:
        outcome(path, {"outcome": "launched", "bundle": str(records.sidecar(output, ".run.json"))})
    else:
        outcome(path, {"outcome": "held" if code == 0 else "refused"})
    return code

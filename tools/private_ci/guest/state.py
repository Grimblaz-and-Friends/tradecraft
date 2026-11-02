#!/usr/bin/env python3
"""Both runner instances' state, read by root without trusting the account's tree (#929).

`provision.sh state` runs this as root. Every job runs as the runner account,
and that account can change anything under its home, so each read there opens
one path component at a time with O_NOFOLLOW and never follows a symlink. What
`.runner` holds is untrusted text: only three short string fields are kept, and
anything else in it, or a file that isn't valid JSON, is dropped.

Standard library only. Prints one line of ASCII JSON.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time

ACCOUNT = "ci-runner"
ORG = "Grimblaz-and-Friends"
INSTANCES = (1, 2)
RUNNER_FIELDS = ("agentName", "poolName", "gitHubUrl")
FIELD_LIMIT = 200
FILE_LIMIT = 64 * 1024


def runner_home() -> str:
    return os.environ.get("TRADECRAFT_CI_RUNNER_HOME", f"/home/{ACCOUNT}")


def unit_name(n: int) -> str:
    return f"actions.runner.{ORG}.blaz-top-wsl-{n}.service"


def open_dir(path: str) -> int | None:
    """An fd for path, walked from / one component at a time without following a symlink."""
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open("/", flags)
    try:
        for part in [p for p in path.split("/") if p]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
    except OSError:
        os.close(fd)
        return None
    return fd


def entry(dir_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    except OSError:
        return None


def read_runner(dir_fd: int) -> dict | None:
    """The three fields setup.py matches on, from `.runner`, as untrusted text."""
    try:
        # O_NONBLOCK, so a named pipe planted as .runner can't hang root here.
        fd = os.open(".runner", os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                     | getattr(os, "O_NONBLOCK", 0), dir_fd=dir_fd)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        data = os.read(fd, FILE_LIMIT)
    finally:
        os.close(fd)
    try:
        record = json.loads(data.decode("utf-8-sig", errors="replace"))
    except ValueError:
        return None
    if not isinstance(record, dict):
        return None
    lowered = {str(key).lower(): value for key, value in record.items()}
    kept = {}
    for field in RUNNER_FIELDS:
        value = lowered.get(field.lower())
        if isinstance(value, str):
            kept[field] = value[:FIELD_LIMIT]
    return kept or None


def last_worker(dir_fd: int) -> int:
    """The newest Worker_*.log's mtime under _diag, read without following links."""
    try:
        diag = os.open("_diag", os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
                       dir_fd=dir_fd)
    except OSError:
        return 0
    newest = 0
    try:
        for name in os.listdir(diag):
            if name.startswith("Worker_") and name.endswith(".log"):
                found = entry(diag, name)
                if found is not None and stat.S_ISREG(found.st_mode):
                    newest = max(newest, int(found.st_mtime))
    finally:
        os.close(diag)
    return newest


def account_side(n: int) -> dict:
    fd = open_dir(f"{runner_home()}/runner-{n}")
    if fd is None:
        return {"unpacked": False, "runner": None, "last_worker_epoch": 0}
    try:
        config = entry(fd, "config.sh")
        unpacked = bool(config is not None and stat.S_ISREG(config.st_mode)
                        and config.st_mode & 0o111)
        return {"unpacked": unpacked, "runner": read_runner(fd),
                "last_worker_epoch": last_worker(fd)}
    finally:
        os.close(fd)


def run_systemctl(argv: list[str]) -> str:
    try:
        proc = subprocess.run(["systemctl", *argv], stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.decode("utf-8", errors="replace").strip()


def enter_epoch(text: str, run=subprocess.run) -> int:
    if not text or text == "n/a":
        return 0
    try:
        proc = run(["date", "-d", text, "+%s"], stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
        return int(proc.stdout.decode("ascii", errors="replace").strip() or 0)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def state(systemctl=run_systemctl, to_epoch=enter_epoch) -> dict:
    instances = []
    for n in INSTANCES:
        unit = unit_name(n)
        instances.append({
            "n": n, "unit": unit,
            "active": systemctl(["is-active", unit]),
            "no_new_privileges": systemctl(["show", "-p", "NoNewPrivileges", "--value", unit]),
            "active_enter_epoch": to_epoch(
                systemctl(["show", "-p", "ActiveEnterTimestamp", "--value", unit])),
            **account_side(n),
        })
    return {"instances": instances, "now_epoch": int(time.time())}


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", newline="")
    sys.stdout.write(json.dumps(state(), ensure_ascii=True, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

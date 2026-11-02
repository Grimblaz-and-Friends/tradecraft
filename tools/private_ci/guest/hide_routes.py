#!/usr/bin/env python3
"""Hide WSL's three routes into Windows from every process in the distribution (#929).

`/dev/dxg` is the GPU paravirtualization device into the Windows host, and
`/usr/lib/wsl` and `/mnt/wslg` are WSL's driver library and WSLg's directory.
WSL creates them whatever `[gpu]` and `guiApplications` say. Hiding them only in
the runner units' own mount namespaces wasn't enough: a job reached them through
any other process of the account, by its `/proc/<pid>/root` (holder reading 10).
So root hides them in the distribution's own mount namespace, which every process
starts from: it bind-mounts a root-owned placeholder of mode 0 over each, so no
account can open, list or traverse it, through any process's view.

The `tradecraft-private-ci-hide` unit runs this at every boot, before the runner
units (which require it) and before any login session. Each runner unit runs it
again before it starts, and provision.sh before every process it starts as the
account. It is idempotent: a path already hidden, or absent, is left alone. A
path that is a symlink, or of a type with no placeholder, fails, and so does
every unit that requires this.

Standard library only. Prints one line of ASCII JSON.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys

ROUTES = ("/dev/dxg", "/usr/lib/wsl", "/mnt/wslg")
PLACEHOLDERS = "/run/tradecraft-private-ci/hidden"


def is_hidden(info: os.stat_result) -> bool:
    return info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0


def make_placeholder(kind: str, base: str = PLACEHOLDERS) -> str:
    """A root-owned node of mode 0 under /run, which is mounted nodev."""
    os.makedirs(base, mode=0o700, exist_ok=True)
    path = os.path.join(base, kind)
    if not os.path.lexists(path):
        if kind == "dir":
            os.mkdir(path, 0)
        elif kind == "chr":
            os.mknod(path, stat.S_IFCHR, os.makedev(0, 0))
        else:
            os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0))
    # The directory above is root's alone (0700, under root-owned /run), so no
    # account can plant a link here.
    os.chmod(path, 0)
    return path


def run_mount(source: str, target: str) -> None:
    proc = subprocess.run(["mount", "--bind", source, target], stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
    if proc.returncode != 0:
        raise OSError(proc.stderr.decode("utf-8", errors="replace").strip()
                      or f"mount exited {proc.returncode}")


def hide(routes=ROUTES, *, lstat=os.lstat, mount=run_mount, make=make_placeholder) -> dict:
    hidden: dict[str, str] = {}
    failures: list[str] = []
    for route in routes:
        try:
            info = lstat(route)
        except FileNotFoundError:
            hidden[route] = "absent"
            continue
        if stat.S_ISLNK(info.st_mode):
            failures.append(f"{route} is a symlink")
            continue
        if is_hidden(info):
            hidden[route] = "hidden"
            continue
        kind = ("dir" if stat.S_ISDIR(info.st_mode) else
                "chr" if stat.S_ISCHR(info.st_mode) else
                "reg" if stat.S_ISREG(info.st_mode) else None)
        if kind is None:
            failures.append(f"{route} is of a type with no placeholder")
            continue
        try:
            mount(make(kind), route)
            after = lstat(route)
        except OSError as exc:
            failures.append(f"{route}: {exc}")
            continue
        if is_hidden(after):
            hidden[route] = "newly hidden"
        else:
            failures.append(f"{route} is still reachable after the mount")
    return {"hidden": hidden, "failures": failures, "ok": not failures}


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", newline="")
    found = hide()
    sys.stdout.write(json.dumps(found, ensure_ascii=True, sort_keys=True) + "\n")
    return 0 if found["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

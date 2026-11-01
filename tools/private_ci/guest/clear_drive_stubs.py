#!/usr/bin/env python3
"""Remove the empty /mnt/<letter> directories WSL's first boot leaves behind (#929).

The distribution's first boot automounts the Windows drives before `base` writes
`[automount] enabled=false`. After the restart that applies it, `/mnt/c` and its
siblings stay behind as empty directories that are no longer mount points, and
row 1's check fails on any `/mnt/<letter>` that exists. `setup.py install` runs
this as root after that restart, on every run.

Only an empty directory that isn't a mount point is removed. A mount point, a
directory holding anything, a symlink or a file is kept, and the check then
fails on it, because that is a real exposure rather than a stub.

Standard library only. Prints one line of ASCII JSON.
"""

from __future__ import annotations

import json
import os
import string
import sys
from pathlib import Path


def clear_drive_stubs(mnt_root: Path, is_mount=os.path.ismount) -> dict:
    """Remove each empty, unmounted /mnt/<letter>; report what was kept and why."""
    removed, kept = [], []
    for letter in string.ascii_lowercase:
        path = mnt_root / letter
        if not os.path.lexists(path):
            continue
        if path.is_symlink() or not path.is_dir():
            kept.append({"path": str(path), "reason": "not a directory"})
        elif is_mount(str(path)):
            kept.append({"path": str(path), "reason": "a mount point"})
        elif any(path.iterdir()):
            kept.append({"path": str(path), "reason": "not empty"})
        else:
            path.rmdir()
            removed.append(str(path))
    return {"removed": removed, "kept": kept}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", newline="")
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else Path("/mnt")
    sys.stdout.write(json.dumps(clear_drive_stubs(root), ensure_ascii=True,
                                sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

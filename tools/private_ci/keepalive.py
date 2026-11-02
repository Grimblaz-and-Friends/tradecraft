"""Hold the tradecraft-ci distribution up for as long as the owner is logged on (C12).

The start task runs this from the installed copy under `pythonw.exe` at the
owner's logon. It starts one hidden `wsl.exe` that sleeps for good, and waits
on it. WSL keeps a distribution running while a `wsl.exe` process is attached,
and systemd starts both runner services when the distribution boots, so the
global idle timeouts stay at their defaults for every other distribution.

It names root as its user. Without `-u`, WSL would open a login session of the
distribution's default user, and a session of the runner account brings its
user manager and processes that a job could use to step outside the units'
sandbox (holder reading 10).

Anything that stops WSL (`wsl --shutdown`, or `install`'s own restart) ends
the `wsl.exe` this waits on, so this returns and the hold is gone until the
owner's next logon. `install` starts the task again itself; after a shutdown
of his own, `schtasks /Run /TN tradecraft-lab-private-ci-start` restores it. It
deliberately doesn't relaunch in a loop: it would fight a shutdown the owner
asked for, and boot the distribution he just stopped.

Standard library only.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "lib"))
from winio import utf8_stdio  # noqa: E402

DISTRO = "tradecraft-ci"
COMMAND = ["wsl.exe", "-d", DISTRO, "-u", "root", "--exec", "/bin/sleep", "infinity"]


def main() -> int:
    utf8_stdio()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    proc = subprocess.Popen(COMMAND, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, creationflags=flags)
    return proc.wait()


if __name__ == "__main__":
    sys.exit(main())

"""Start a process nobody waits on, outside every caller's containment.

Design: lib/DESIGN.md#the-builder-route
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

STARTER_SECONDS = 30
CREATE_NO_WINDOW = 0x08000000
WINDOWS = os.name == "nt"


class DetachError(RuntimeError):
    """The process could not be started detached."""


DETACH = ("import subprocess,sys;"
          "subprocess.Popen(sys.argv[2:],cwd=sys.argv[1],stdin=subprocess.DEVNULL,"
          "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)")
# DETACH with each stream appended to a file when one is named; an empty name is
# the null device, and one file named twice is opened once so the two streams
# interleave rather than overwrite.
DETACH_TO_FILES = ("import subprocess,sys;a=sys.argv;o,e=a[2],a[3];"
                   "out=open(o,'ab') if o else subprocess.DEVNULL;"
                   "err=subprocess.STDOUT if e and e==o else open(e,'ab') if e else subprocess.DEVNULL;"
                   "subprocess.Popen(a[4:],cwd=a[1],stdin=subprocess.DEVNULL,stdout=out,stderr=err,"
                   "close_fds=True)")


def windows_spawn(argv: list[str], cwd: Path, env: dict[str, str]) -> int:
    """Create the process through WMI, outside every job; the environment goes in memory.

    WMI's Win32_Process.Create makes a process no caller's kill-on-close job
    holds, where a breakaway from the launcher's job is refused. The
    environment travels on PowerShell's stdin, never a command line or file.
    """
    script = (
        "$ErrorActionPreference='Stop';"
        "$in=[Console]::In.ReadToEnd()|ConvertFrom-Json;"
        "$vars=[string[]]@($in.env.PSObject.Properties|ForEach-Object{$_.Name+'='+$_.Value});"
        "$startup=New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly "
        "-Property @{ShowWindow=[uint16]0;EnvironmentVariables=$vars};"
        "$r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
        "@{CommandLine=$in.cmd;CurrentDirectory=$in.dir;ProcessStartupInformation=$startup};"
        "if($r.ReturnValue -ne 0){[Console]::Error.WriteLine('Win32_Process.Create returned '+$r.ReturnValue);exit 1};"
        "[Console]::Out.WriteLine($r.ProcessId)"
    )
    payload = json.dumps({"cmd": subprocess.list2cmdline(argv), "dir": str(cwd), "env": env},
                         ensure_ascii=True).encode("ascii")
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=STARTER_SECONDS, creationflags=CREATE_NO_WINDOW)
    if result.returncode != 0:
        raise DetachError("WMI start failed: " + result.stderr.decode("utf-8", "replace").strip()[:1000])
    return int(result.stdout.decode("ascii", "replace").strip().splitlines()[-1])


def posix_spawn(argv: list[str], cwd: Path, env: dict[str, str], *,
                stdout: str | Path | None = None, stderr: str | Path | None = None) -> int:
    """The standard double fork: an intermediate child in a new session starts the process and exits.

    The process is then reparented to the nearest subreaper, the entrance
    itself once its own cleanup has run, so a later cleanup's baseline holds it.
    """
    if stdout is None and stderr is None:
        starter = [DETACH, str(cwd)]
    else:
        starter = [DETACH_TO_FILES, str(cwd), str(stdout or ""), str(stderr or "")]
    intermediate = subprocess.Popen([sys.executable, "-B", "-c", *starter, *argv],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, close_fds=True, env=env,
                                    start_new_session=True)
    code = intermediate.wait(timeout=STARTER_SECONDS)
    if code != 0:
        raise DetachError(f"starter exited {code}")
    return 0


def spawn(command: list[str], *, cwd: str | Path | None = None, env: dict[str, str] | None = None,
          stdout: str | Path | None = None, stderr: str | Path | None = None) -> int:
    """Start `command` detached on this platform and return once it has started, not ended.

    `stdout` and `stderr` name files the process's output is appended to; an
    unnamed stream goes to the null device. Returns the started process's id
    on Windows (that of the small starter that opens the files, when either is
    named) and 0 on POSIX, where the double fork hides it.
    """
    directory = Path.cwd() if cwd is None else Path(cwd)
    environment = dict(os.environ if env is None else env)
    if not WINDOWS:
        return posix_spawn(command, directory, environment, stdout=stdout, stderr=stderr)
    if stdout is not None or stderr is not None:
        # WMI cannot redirect a stream, so a starter it creates opens the files.
        command = [sys.executable, "-B", "-c", DETACH_TO_FILES, str(directory), str(stdout or ""),
                   str(stderr or ""), *command]
    return windows_spawn(command, directory, environment)

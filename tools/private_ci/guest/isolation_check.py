#!/usr/bin/env python3
"""Row 1's check: nothing a job runs can reach the owner's Windows side (#929).

Runs inside the `tradecraft-ci` distribution, with Ubuntu 24.04's system
python3 and nothing else: in a `private-ci` job (`--context job`), from
`setup.py verify` as the runner account under the unit's privilege settings
(`--context verify`), and, with `--root-settings`, from `verify` as root.

It prints one JSON object and exits 1 when any probe reports `reachable` or
`unknown`, so a probe that cannot decide fails closed. Every probe takes its
paths and its process runner as parameters, so the tests feed it loosened
states without a distribution.

Standard library only. Output is ASCII JSON.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ACCOUNT = "ci-runner"
WINDOWS_FS = ("9p", "drvfs", "virtiofs", "cifs", "smb3")
# C9: the allowlist of Windows-backed mounts is empty. A mount added here must be
# read-only, serve no drive root and no profile path, and be recorded in the PR.
MOUNT_ALLOWLIST: tuple[str, ...] = ()
WSLG_VARIABLES = ("DISPLAY", "WAYLAND_DISPLAY", "PULSE_SERVER")
# WSL's routes into Windows, which hide_routes.py hides for the whole distribution.
HIDDEN_ROUTES = (("gpu", "dev/dxg"), ("wsl-lib", "usr/lib/wsl"), ("wslg", "mnt/wslg"))
LIVE_UNIT_STATES = ("active", "activating", "reloading", "refreshing", "deactivating")
WINDOWS_PROGRAMS = ("cmd.exe", "powershell.exe", "pwsh.exe", "explorer.exe", "wsl.exe")
ROOT_GROUPS = ("root", "sudo", "admin", "wheel", "docker", "lxd", "incus",
               "incus-admin", "disk", "libvirt")
ROOT_OWNED = ("/etc/fstab", "/etc/wsl.conf", "/etc/sudoers", "/etc/sudoers.d", "/etc/passwd")
CANARY = (".tradecraft-lab", "private-ci", "canary.txt")
NO_RIGHTS = re.compile(r"User ci-runner is not allowed to run sudo on \S+\.\n?")
GRANTS = "may run the following commands"

BLOCKED, REACHABLE, UNKNOWN, INFO = "blocked", "reachable", "unknown", "info"


def result(probe: str, failures: list[str], unknowns: list[str] | None = None,
           detail: dict | None = None) -> dict:
    unknowns = unknowns or []
    state = REACHABLE if failures else (UNKNOWN if unknowns else BLOCKED)
    return {"probe": probe, "result": state, "failures": failures + unknowns,
            "detail": detail or {}}


def run_command(argv: list[str], env: dict | None = None) -> tuple[int, str]:
    """Run argv with every stream named; return (exit code, stdout + stderr)."""
    proc = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, env=env, timeout=30)
    return proc.returncode, proc.stdout.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- probes


def probe_mounts(mountinfo: Path, fstab: Path) -> dict:
    """No Windows-backed mount is live, and fstab names none."""
    failures = []
    unknowns = []
    try:
        lines = mountinfo.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        lines = []
        unknowns.append(f"mountinfo unreadable: {exc.strerror}")
    for line in lines:
        head, sep, tail = line.partition(" - ")
        if not sep:
            continue
        fields = head.split()
        rest = tail.split()
        if len(fields) < 5 or not rest:
            continue
        mount_point, fs_type = fields[4], rest[0]
        source = rest[1] if len(rest) > 1 else ""
        if fs_type in WINDOWS_FS and mount_point not in MOUNT_ALLOWLIST:
            failures.append(f"mount:{mount_point} ({fs_type} {source})")
    try:
        entries = fstab.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        entries = []
    except OSError as exc:
        entries = []
        unknowns.append(f"fstab unreadable: {exc.strerror}")
    for entry in entries:
        parts = entry.split("#", 1)[0].split()
        if len(parts) >= 3 and parts[2] in WINDOWS_FS:
            failures.append(f"fstab entry:{parts[1]} ({parts[2]})")
    return result("mounts", failures, unknowns)


def probe_drives(mnt_root: Path, win_user: str | None) -> dict:
    """No drive letter under /mnt, and the owner's profile canary can't be opened."""
    # lexists, so a dangling symlink at /mnt/<letter> counts as present.
    failures = [f"drive:{mnt_root / letter}" for letter in "abcdefghijklmnopqrstuvwxyz"
                if os.path.lexists(mnt_root / letter)]
    unknowns = []
    if not win_user:
        unknowns.append("canary: no --win-user given")
    else:
        canary = mnt_root.joinpath("c", "Users", win_user, *CANARY)
        try:
            with open(canary, "rb"):
                failures.append(f"canary readable:{canary}")
        except OSError:
            pass
    return result("drives", failures, unknowns)


def _exec_mz(scratch_dir: str | None, executor) -> str:
    """Execute a file that opens with MZ; ENOEXEC means no interop handler took it."""
    handle, path = tempfile.mkstemp(dir=scratch_dir, prefix="mz-", suffix=".exe")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(b"MZ" + b"\0" * 62)
        os.chmod(path, 0o700)
        try:
            executor([path])
        except OSError as exc:
            return BLOCKED if exc.errno == errno.ENOEXEC else f"{UNKNOWN}:{exc.strerror}"
        return REACHABLE
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _default_executor(argv: list[str]) -> None:
    subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=10)


def probe_interop(binfmt_dir: Path, environ: dict, scratch_dir: str | None = None,
                  executor=_default_executor) -> dict:
    """No interop handler is registered or enabled, and no Windows program resolves."""
    failures = []
    unknowns = []
    if binfmt_dir.is_dir():
        for entry in sorted(binfmt_dir.glob("WSLInterop*")):
            try:
                first = entry.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0]
            except OSError:
                first = "unreadable"
            if first.strip() != "disabled":
                failures.append(f"interop:binfmt {entry.name} {first.strip()}")
    if environ.get("WSL_INTEROP"):
        failures.append("interop:WSL_INTEROP set")
    outcome = _exec_mz(scratch_dir, executor)
    if outcome == REACHABLE:
        failures.append("interop:an MZ file executed")
    elif outcome != BLOCKED:
        unknowns.append(f"interop:MZ exec {outcome}")
    entries = [entry for entry in environ.get("PATH", "").split(":") if entry]
    for entry in entries:
        if entry.startswith("/mnt/"):
            failures.append(f"appendWindowsPath: PATH entry {entry}")
    for program in WINDOWS_PROGRAMS:
        for entry in entries:
            candidate = os.path.join(entry, program)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                failures.append(f"program resolves:{candidate}")
    return result("interop", failures, unknowns)


def _reaches(base: Path) -> list[tuple[str, str]]:
    """Which of WSL's routes open from this view of the filesystem: (name, path)."""
    found = []
    for name, relative in HIDDEN_ROUTES:
        path = base / relative
        if relative == "dev/dxg":
            for flags in (os.O_RDWR, os.O_RDONLY):
                try:
                    handle = os.open(path, flags | getattr(os, "O_NONBLOCK", 0)
                                     | getattr(os, "O_NOCTTY", 0))
                except OSError:
                    continue
                os.close(handle)
                found.append((name, str(path)))
                break
        else:
            try:
                os.listdir(path)
            except OSError:
                continue
            found.append((name, str(path)))
    return found


def probe_wslg(root: Path, environ: dict) -> dict:
    """No WSLg display, audio or clipboard bridge, and no GPU route into the host.

    WSLg's sockets are its route into the owner's session, so the probe tests them
    and the display variables a job would use, whatever `.wslconfig` says. The GPU
    device `/dev/dxg`, WSL's library and WSLg's directory must not open either.
    They are hidden for the whole distribution, so this holds in every context,
    `verify`'s included (holder reading 10).
    """
    failures = []
    for name in WSLG_VARIABLES:
        if environ.get(name):
            failures.append(f"wslg:{name} set")
    # WSLg serves display :0. A job's own Xvfb (display :99 under xvfb-run) is the
    # distribution's, not a bridge to Windows, so only X0 counts.
    if os.path.lexists(root / "tmp" / ".X11-unix" / "X0"):
        failures.append(f"wslg:socket {root / 'tmp' / '.X11-unix' / 'X0'}")
    wslg = root / "mnt" / "wslg"
    for relative in ("PulseServer", "runtime-dir/wayland-0", ".X11-unix/X0"):
        if os.path.lexists(wslg / relative):
            failures.append(f"wslg:socket {wslg / relative}")
    for name, path in _reaches(root):
        failures.append(f"{name}:{path} opens")
    return result("wslg", failures)


def _connects(path: Path) -> bool:
    if not hasattr(socket, "AF_UNIX"):
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(3)
            sock.connect(str(path))
            return True
    except OSError:
        return False


def probe_same_uid(proc_dir: Path, uid: int, run_user: Path, connects=_connects) -> dict:
    """No other process of this account opens a way out of the job's sandbox.

    A process of the same uid lends a job its view of the filesystem through
    `/proc/<pid>/root`, and one without no_new_privs is a way round it. The user
    manager, if it answers, starts services outside the unit (holder reading 10).
    """
    failures = []
    try:
        pids = sorted(int(entry) for entry in os.listdir(proc_dir) if entry.isdigit())
    except OSError as exc:
        return result("same-uid", [], [f"proc unreadable: {exc.strerror}"])
    seen = 0
    for pid in pids:
        try:
            status = (proc_dir / str(pid) / "status").read_text(encoding="utf-8",
                                                                  errors="replace")
        except OSError:
            continue  # it ended, or isn't ours to read
        fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
        if str(uid) not in fields.get("Uid", "").split()[:2]:
            continue
        seen += 1
        name = fields.get("Name", "?").strip()
        if fields.get("NoNewPrivs", "").strip() != "1":
            failures.append(f"same-uid:pid {pid} ({name}) runs without no_new_privs")
        for route, path in _reaches(proc_dir / str(pid) / "root"):
            failures.append(f"same-uid:pid {pid} ({name}) opens {route} at {path}")
    for path in (run_user / str(uid) / "systemd" / "private", run_user / str(uid) / "bus"):
        if connects(path):
            failures.append(f"user-manager:{path} answers")
    return result("same-uid", failures, detail={"processes": seen})


def _owner(path: str):
    try:
        return os.stat(path).st_uid
    except OSError:
        return None


def _writable(path: str) -> bool:
    return os.access(path, os.W_OK)


def probe_root(status_file: Path, euid: int, groups: list[str], docker_socket: str,
               runner=run_command, owner_of=_owner, writable=_writable,
               files=ROOT_OWNED) -> dict:
    """The job can't be root or become root, by a setuid binary, a group or a file."""
    failures = []
    unknowns = []
    if euid == 0:
        failures.append("uid 0")
    try:
        status = status_file.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        status = ""
        unknowns.append(f"status unreadable: {exc.strerror}")
    fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    if status and fields.get("NoNewPrivs", "").strip() != "1":
        failures.append(f"NoNewPrivs: {fields.get('NoNewPrivs', 'absent').strip()}")
    if status and fields.get("CapEff", "").strip().strip("0") != "":
        failures.append(f"CapEff: {fields.get('CapEff', 'absent').strip()}")
    try:
        code, _ = runner(["sudo", "-n", "true"])
        if code == 0:
            failures.append("sudo -n true succeeded")
    except FileNotFoundError:
        pass
    except (OSError, subprocess.SubprocessError) as exc:
        unknowns.append(f"sudo probe: {exc}")
    for group in groups:
        if group in ROOT_GROUPS:
            failures.append(f"group:{group}")
    if hasattr(socket, "AF_UNIX") and os.path.exists(docker_socket):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(3)
                sock.connect(docker_socket)
                failures.append(f"docker socket opens:{docker_socket}")
        except OSError:
            pass
    for path in files:
        uid = owner_of(path)
        if uid is None:
            if path in ("/etc/fstab", "/etc/wsl.conf", "/etc/sudoers", "/etc/passwd"):
                unknowns.append(f"file:{path} missing")
            continue
        if uid != 0:
            failures.append(f"file:{path} owned by uid {uid}")
        if writable(path):
            failures.append(f"file:{path} writable")
    return result("root", failures, unknowns)


def probe_local_services(port: int | None, hosts=("127.0.0.1", "::1")) -> dict:
    """A Windows service listening only on loopback can't be reached."""
    if port is None:
        return result("local-services", [], ["no --local-port given"])
    failures = []
    for host in hosts:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        try:
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(3)
                sock.connect((host, port))
                failures.append(f"loopback:{host}:{port} connected")
        except OSError:
            pass
    return result("local-services", failures)


def probe_settings(meminfo: Path, environ: dict) -> dict:
    """Facts printed for `setup.py probe` to judge (A14); never a failure here."""
    try:
        threads = len(os.sched_getaffinity(0))  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        threads = os.cpu_count()
    mem_kib = None
    try:
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                mem_kib = int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return {"probe": "settings", "result": INFO, "failures": [],
            "detail": {"nproc": threads, "mem_total_kib": mem_kib,
                       "runner_name": environ.get("RUNNER_NAME")}}


def probe_root_settings(euid: int, shadow: Path, runner=run_command) -> dict:
    """As root: sudo's own answer for ci-runner's rights, and root's password field."""
    if euid != 0:
        return result("root-settings", [], ["not run as uid 0"])
    failures = []
    unknowns = []
    env = {"LC_ALL": "C", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"}
    try:
        _, output = runner(["sudo", "-l", "-U", ACCOUNT], env=env)
    except (OSError, subprocess.SubprocessError) as exc:
        output = None
        unknowns.append(f"sudoers: sudo -l failed to run ({exc})")
    if output is not None and not NO_RIGHTS.fullmatch(output):
        if GRANTS in output:
            failures.append("sudoers: ci-runner has sudo rights")
        else:
            unknowns.append("sudoers: unexpected sudo -l output")
    try:
        lines = shadow.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        lines = []
        unknowns.append(f"root-password: shadow unreadable ({exc.strerror})")
    root_line = next((line for line in lines if line.startswith("root:")), None)
    if lines and root_line is None:
        unknowns.append("root-password: no root entry")
    elif root_line is not None:
        field = root_line.split(":")[1]
        if not (field == "*" or field.startswith("!")):
            failures.append("root-password: " + ("empty" if field == "" else "usable hash"))
    return result("root-settings", failures, unknowns)


def account_uid() -> int | None:
    try:
        import pwd
        return pwd.getpwnam(ACCOUNT).pw_uid
    except (ImportError, KeyError):
        return None


def probe_account_sessions(euid: int, linger_dir: Path, uid: int | None,
                           runner=run_command) -> dict:
    """As root: the account has no login session, no user manager and no linger."""
    if euid != 0:
        return result("sessions", [], ["not run as uid 0"])
    if uid is None:
        return result("sessions", [], [f"no {ACCOUNT} account"])
    failures = []
    unknowns = []
    env = {"LC_ALL": "C", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"}
    if os.path.lexists(linger_dir / ACCOUNT):
        failures.append(f"linger: {linger_dir / ACCOUNT} exists")
    try:
        code, output = runner(["loginctl", "list-sessions", "--no-legend"], env=env)
    except (OSError, subprocess.SubprocessError) as exc:
        code, output = None, ""
        unknowns.append(f"login-session: loginctl failed to run ({exc})")
    if code not in (None, 0):
        unknowns.append(f"login-session: loginctl exited {code}")
    for line in output.splitlines():
        fields = line.split()
        if ACCOUNT in fields[1:3] or str(uid) in fields[1:3]:
            failures.append(f"login-session: {' '.join(fields[:3])}")
    try:
        _, state = runner(["systemctl", "is-active", f"user@{uid}.service"], env=env)
    except (OSError, subprocess.SubprocessError) as exc:
        state = ""
        unknowns.append(f"user-manager: systemctl failed to run ({exc})")
    state = (state.strip().splitlines() or [""])[-1]
    if state in LIVE_UNIT_STATES:
        failures.append(f"user-manager: user@{uid}.service is {state}")
    return result("sessions", failures, unknowns)


# ---------------------------------------------------------------- the check


def group_names() -> list[str]:
    try:
        import grp
    except ImportError:
        return []
    names = []
    for gid in sorted(set(os.getgroups()) | {os.getegid()}):
        try:
            names.append(grp.getgrgid(gid).gr_name)
        except KeyError:
            names.append(str(gid))
    return names


def run_check(args: argparse.Namespace, *, root: Path = Path("/"), environ=None,
              euid: int | None = None, groups: list[str] | None = None,
              runner=run_command, executor=_default_executor,
              owner_of=_owner, writable=_writable, connects=_connects,
              uid_of_account=account_uid) -> dict:
    environ = dict(os.environ if environ is None else environ)
    euid = os.geteuid() if euid is None else euid  # type: ignore[attr-defined]
    if args.root_settings:
        probes = [probe_root_settings(euid, root / "etc" / "shadow", runner),
                  probe_account_sessions(euid, root / "var" / "lib" / "systemd" / "linger",
                                         uid_of_account(), runner)]
    else:
        files = tuple(str(root / path.lstrip("/")) for path in ROOT_OWNED)
        probes = [
            probe_mounts(root / "proc" / "self" / "mountinfo", root / "etc" / "fstab"),
            probe_drives(root / "mnt", args.win_user),
            probe_interop(root / "proc" / "sys" / "fs" / "binfmt_misc", environ,
                          args.scratch_dir, executor),
            probe_root(root / "proc" / "self" / "status", euid,
                       group_names() if groups is None else groups,
                       str(root / "var" / "run" / "docker.sock"), runner,
                       owner_of, writable, files),
            probe_local_services(args.local_port),
            probe_wslg(root, environ),
            probe_same_uid(root / "proc", euid, root / "run" / "user", connects),
            probe_settings(root / "proc" / "meminfo", environ),
        ]
    failed = [p["probe"] for p in probes if p["result"] in (REACHABLE, UNKNOWN)]
    return {"check": "private-ci-isolation", "context": args.context,
            "root_settings": bool(args.root_settings), "ok": not failed,
            "failed": failed, "probes": probes}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prove a private-ci job cannot reach the owner's Windows side.")
    parser.add_argument("--context", choices=("job", "verify"), default="job")
    parser.add_argument("--win-user", help="the owner's Windows profile folder name")
    parser.add_argument("--local-port", type=int, help="the Windows loopback listener's port")
    parser.add_argument("--root-settings", action="store_true",
                        help="as root: read ci-runner's sudo rights and root's password")
    parser.add_argument("--scratch-dir", help="where the MZ probe writes its file")
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", newline="")
    args = build_parser().parse_args(argv)
    report = run_check(args)
    sys.stdout.write("PRIVATE-CI-CHECK " + json.dumps(report, ensure_ascii=True,
                                                      sort_keys=True) + "\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

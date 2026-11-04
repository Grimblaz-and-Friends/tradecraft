"""Tests for tools/private_ci: the private repositories' runner on BLAZ-TOP (#929).

Nothing here touches a distribution, a scheduled task or GitHub. The isolation
check is fed loosened states through injectable paths and runners; the setup
runs against a recording fake for wsl.exe, schtasks.exe, git and PowerShell;
the watch and the re-run run against a fake that models run attempts.
Criterion ids (A1 ...) are the settled artifact's on #929.
"""

from __future__ import annotations

import argparse
import errno
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent
PRIVATE_CI = TOOLS / "private_ci"
sys.path.insert(0, str(PRIVATE_CI))
sys.path.insert(0, str(TOOLS))
import steward_watch as sw  # noqa: E402
import watch as pw  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ic = _load("private_ci_isolation_check", PRIVATE_CI / "guest" / "isolation_check.py")
ps = _load("private_ci_setup", PRIVATE_CI / "setup.py")
cds = _load("private_ci_clear_drive_stubs", PRIVATE_CI / "guest" / "clear_drive_stubs.py")

NOW = datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)
CC = "Grimblaz-and-Friends/Countdown-Clash"
VERRA = "Grimblaz-and-Friends/Organizations-of-Verra"
DAEMON = "Grimblaz-and-Friends/Daemon"
WIND = "Grimblaz-and-Friends/Windgust-Questbook"
REPOS = [VERRA, DAEMON, CC, WIND]
NO_RIGHTS = "User ci-runner is not allowed to run sudo on BLAZ-TOP.\n"
# Ubuntu 24.04 ships sudo 1.9.15p5 (1.9.15p5-3ubuntu5.24.04.4). These listings
# follow that version's plugins/sudoers/display.c (display_privs: the Defaults
# header, then "User %s may run the following commands on %s:", then one
# "    (runas) tags: commands" line per entry; with no entries, only
# "User %s is not allowed to run sudo on %s.").
DEFAULTS = ("Matching Defaults entries for ci-runner on BLAZ-TOP:\n"
            "    env_reset, mail_badpass,\n"
            "    secure_path=/usr/local/sbin\\:/usr/local/bin\\:/usr/sbin\\:/usr/bin\\:/sbin\\:/bin\\:/snap/bin,\n"
            "    use_pty\n\n")
SUDOERS_D_GRANT = (DEFAULTS + "User ci-runner may run the following commands on BLAZ-TOP:\n"
                   "    (ALL) NOPASSWD: ALL\n")
GROUP_RULE = (DEFAULTS + "User ci-runner may run the following commands on BLAZ-TOP:\n"
              "    (ALL) ALL\n")
SUDO_ERROR = "sudo: unable to open /etc/sudoers: Permission denied\nsudo: no valid sudoers sources found, quitting\n"


# ---------------------------------------------------------------- the isolation check (A1, A2)


def good_root(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    (root / "proc" / "self").mkdir(parents=True)
    (root / "proc" / "self" / "mountinfo").write_text(
        "23 1 8:32 / / rw,relatime - ext4 /dev/sdc rw\n"
        "30 23 0:6 / /dev rw,nosuid - devtmpfs none rw\n"
        "40 23 0:30 / /mnt/wsl rw,relatime shared:1 - tmpfs none rw\n", encoding="utf-8")
    (root / "proc" / "self" / "status").write_text(
        "Name:\tpython3\nNoNewPrivs:\t1\nCapEff:\t0000000000000000\n", encoding="utf-8")
    (root / "proc" / "meminfo").write_text("MemTotal:       12266000 kB\n", encoding="utf-8")
    (root / "proc" / "sys" / "fs" / "binfmt_misc").mkdir(parents=True)
    (root / "proc" / "sys" / "fs" / "binfmt_misc" / "status").write_text("enabled\n")
    (root / "etc").mkdir()
    (root / "etc" / "fstab").write_text("LABEL=cloudimg-rootfs / ext4 defaults 0 1\n")
    (root / "etc" / "shadow").write_text("root:*:20000:0:99999:7:::\nci-runner:!:20000::::::\n")
    (root / "mnt" / "wsl").mkdir(parents=True)
    return root


def no_exec(argv):
    raise OSError(errno.ENOEXEC, "Exec format error")


def sudo_refuses(argv, env=None):
    if argv[:2] == ["sudo", "-n"]:
        return 1, "sudo: The \"no new privileges\" flag is set, which prevents sudo from running as root.\n"
    return 0, NO_RIGHTS


def args(**overrides) -> argparse.Namespace:
    values = {"context": "job", "win_user": "Micah", "local_port": 1, "root_settings": False,
              "scratch_dir": None}
    values.update(overrides)
    return argparse.Namespace(**values)


@pytest.fixture
def quiet_loopback(monkeypatch):
    monkeypatch.setattr(ic, "probe_local_services",
                        lambda port, hosts=("127.0.0.1", "::1"): ic.result("local-services", []))


def check(root: Path, tmp_path: Path, *, environ=None, groups=None, euid=1001,
          runner=sudo_refuses, executor=no_exec, owner_of=lambda p: 0,
          writable=lambda p: False, **arg_overrides) -> dict:
    return ic.run_check(args(scratch_dir=str(tmp_path), **arg_overrides), root=root,
                        environ=environ or {"PATH": "/usr/local/bin:/usr/bin:/bin"},
                        euid=euid, groups=groups or ["ci-runner"], runner=runner,
                        executor=executor, owner_of=owner_of, writable=writable)


def failures_of(report: dict, probe: str) -> list[str]:
    return next(p for p in report["probes"] if p["probe"] == probe)["failures"]



def test_a1_a_correct_state_passes(tmp_path, quiet_loopback):
    report = check(good_root(tmp_path), tmp_path)
    assert report["ok"], report["failed"]
    assert all(p["result"] in ("blocked", "info") for p in report["probes"])


@pytest.mark.parametrize("loosen, probe, named", [
    ("drvfs_mount", "mounts", "mount:/mnt/c (drvfs"),
    ("fstab_entry", "mounts", "fstab entry:/mnt/c (drvfs)"),
    ("drive_dir", "drives", "drive:"),
    ("interop_on", "interop", "interop:binfmt WSLInterop enabled"),
    ("wsl_interop_env", "interop", "interop:WSL_INTEROP set"),
    ("mz_runs", "interop", "interop:an MZ file executed"),
    ("windows_path", "interop", "appendWindowsPath: PATH entry /mnt/c/Windows"),
    ("docker_group", "root", "group:docker"),
    ("no_new_privs_off", "root", "NoNewPrivs: 0"),
    ("caps", "root", "CapEff: 00000000a80425fb"),
    ("sudo_works", "root", "sudo -n true succeeded"),
    ("uid0", "root", "uid 0"),
    ("fstab_writable", "root", "fstab writable"),
    ("fstab_not_root", "root", "fstab owned by uid 1001"),
])
def test_a2_each_loosened_setting_fails_naming_it(tmp_path, quiet_loopback, loosen, probe, named):
    root = good_root(tmp_path)
    kwargs: dict = {}
    if loosen == "drvfs_mount":
        with open(root / "proc" / "self" / "mountinfo", "a", encoding="utf-8") as stream:
            stream.write("50 23 0:40 / /mnt/c rw,noatime - 9p drvfs rw,aname=drvfs;path=C:\\\n")
            stream.write("51 23 0:41 / /mnt/c rw,noatime - drvfs C:\\ rw\n")
    elif loosen == "fstab_entry":
        with open(root / "etc" / "fstab", "a", encoding="utf-8") as stream:
            stream.write("C: /mnt/c drvfs defaults 0 0\n")
    elif loosen == "drive_dir":
        (root / "mnt" / "c").mkdir()
    elif loosen == "interop_on":
        (root / "proc" / "sys" / "fs" / "binfmt_misc" / "WSLInterop").write_text(
            "enabled\ninterpreter /init\nflags: PF\noffset 0\nmagic 4d5a\n")
    elif loosen == "wsl_interop_env":
        kwargs["environ"] = {"PATH": "/usr/bin:/bin", "WSL_INTEROP": "/run/WSL/1_interop"}
    elif loosen == "mz_runs":
        kwargs["executor"] = lambda argv: None
    elif loosen == "windows_path":
        kwargs["environ"] = {"PATH": "/usr/bin:/bin:/mnt/c/Windows"}
    elif loosen == "docker_group":
        kwargs["groups"] = ["ci-runner", "docker"]
    elif loosen == "no_new_privs_off":
        (root / "proc" / "self" / "status").write_text("NoNewPrivs:\t0\nCapEff:\t0000000000000000\n")
    elif loosen == "caps":
        (root / "proc" / "self" / "status").write_text("NoNewPrivs:\t1\nCapEff:\t00000000a80425fb\n")
    elif loosen == "sudo_works":
        kwargs["runner"] = lambda argv, env=None: (0, "")
    elif loosen == "uid0":
        kwargs["euid"] = 0
    elif loosen == "fstab_writable":
        kwargs["writable"] = lambda path: path.replace("\\", "/").endswith("etc/fstab")
    elif loosen == "fstab_not_root":
        kwargs["owner_of"] = lambda path: 1001 if path.replace("\\", "/").endswith("etc/fstab") else 0
    report = check(root, tmp_path, **kwargs)
    assert not report["ok"]
    assert probe in report["failed"]
    assert any(named in failure for failure in failures_of(report, probe)), failures_of(report, probe)


def test_drive_stubs_go_and_real_exposures_stay(tmp_path):
    """The owner's install at 10d5009: WSL's first boot left /mnt/c and /mnt/d as empty,
    unmounted directories, and the drives probe failed on them."""
    mnt = tmp_path / "mnt"
    for letter in "cde":
        (mnt / letter).mkdir(parents=True)
    (mnt / "d" / "file.txt").write_text("something")
    (mnt / "wsl").mkdir()
    mounted = str(mnt / "e")
    before = ic.probe_drives(mnt, "Micah")
    assert before["result"] == "reachable"
    found = cds.clear_drive_stubs(mnt, is_mount=lambda path: path == mounted)
    assert found["removed"] == [str(mnt / "c")]
    assert found["kept"] == [{"path": str(mnt / "d"), "reason": "not empty"},
                             {"path": mounted, "reason": "a mount point"}]
    assert not (mnt / "c").exists() and (mnt / "d").exists() and (mnt / "e").exists()
    assert (mnt / "wsl").exists()
    after = ic.probe_drives(mnt, "Micah")
    assert after["result"] == "reachable"
    assert sorted(after["failures"]) == [f"drive:{mnt / 'd'}", f"drive:{mnt / 'e'}"]
    (mnt / "d" / "file.txt").unlink()
    again = cds.clear_drive_stubs(mnt, is_mount=lambda path: path == mounted)
    assert again["removed"] == [str(mnt / "d")]
    os.rmdir(mounted)  # the mount is gone; the empty directory is now a stub
    cds.clear_drive_stubs(mnt, is_mount=lambda path: False)
    assert ic.probe_drives(mnt, "Micah")["result"] == "blocked"


def test_a2_canary_readable_fails(tmp_path, quiet_loopback):
    root = good_root(tmp_path)
    canary = root.joinpath("mnt", "c", "Users", "Micah", ".tradecraft-lab", "private-ci")
    canary.mkdir(parents=True)
    (canary / "canary.txt").write_text("secret")
    report = check(root, tmp_path)
    assert any("canary readable" in f for f in failures_of(report, "drives"))


def test_a1_missing_inputs_fail_closed(tmp_path, quiet_loopback):
    report = check(good_root(tmp_path), tmp_path, win_user=None)
    assert "drives" in report["failed"]


def test_a1_loopback_probe_without_a_port_is_unknown():
    assert ic.probe_local_services(None)["result"] == "unknown"


def test_a2_mz_probe_other_error_is_unknown(tmp_path, quiet_loopback):
    def denied(argv):
        raise OSError(errno.EACCES, "Permission denied")
    report = check(good_root(tmp_path), tmp_path, executor=denied)
    assert "interop" in report["failed"]


def test_a1_loopback_probe_detects_a_real_listener():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        found = ic.probe_local_services(port, hosts=("127.0.0.1",))
    assert found["result"] == "reachable"
    assert found["failures"] == [f"loopback:127.0.0.1:{port} connected"]


@pytest.mark.parametrize("output, named, state", [
    (SUDOERS_D_GRANT, "sudoers", "reachable"),
    (GROUP_RULE, "sudoers", "reachable"),
    (SUDO_ERROR, "sudoers", "unknown"),
])
def test_a2_sudoers_rules_fail_root_settings(tmp_path, output, named, state):
    root = good_root(tmp_path)
    found = ic.probe_root_settings(0, root / "etc" / "shadow",
                                   runner=lambda argv, env=None: (0, output))
    assert found["result"] == state
    assert any(f.startswith(named) for f in found["failures"])


@pytest.mark.parametrize("field, named", [("$6$salt$hash", "root-password: usable hash"),
                                          ("", "root-password: empty")])
def test_a2_root_password_fails_root_settings(tmp_path, field, named):
    shadow = tmp_path / "shadow"
    shadow.write_text(f"root:{field}:20000:0:99999:7:::\n")
    found = ic.probe_root_settings(0, shadow, runner=lambda argv, env=None: (0, NO_RIGHTS))
    assert named in found["failures"]


def test_a2_root_settings_asks_sudo_itself_as_root_with_lc_all_c(tmp_path):
    seen = []

    def runner(argv, env=None):
        seen.append((argv, env))
        return 0, NO_RIGHTS
    shadow = tmp_path / "shadow"
    shadow.write_text("root:!:20000:0:99999:7:::\n")
    assert ic.probe_root_settings(0, shadow, runner=runner)["result"] == "blocked"
    assert seen == [(["sudo", "-l", "-U", "ci-runner"],
                     {"LC_ALL": "C", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"})]
    assert ic.probe_root_settings(1001, shadow, runner=runner)["result"] == "unknown"


def test_a3_verify_context_passes_exactly_where_job_does(tmp_path, quiet_loopback):
    root = good_root(tmp_path)
    job = check(root, tmp_path, context="job")
    verify = check(root, tmp_path, context="verify")
    assert job["ok"] and verify["ok"]
    assert [p["result"] for p in job["probes"]] == [p["result"] for p in verify["probes"]]


# ---------------------------------------------------------------- settings read back (A2, A3)


GOOD_WSL_CONF = (PRIVATE_CI / "guest" / "wsl.conf").read_text(encoding="utf-8")
GOOD_WSLCONFIG = "[wsl2]\nprocessors=8\nmemory=12GB\nguiApplications=false\n"


@pytest.mark.parametrize("old, new, named", [
    ("[interop]\nenabled=false", "[interop]\nenabled=true", "wsl.conf interop.enabled=true"),
    ("mountFsTab=false", "mountFsTab=true", "wsl.conf automount.mountFsTab=true"),
    ("appendWindowsPath=false", "appendWindowsPath=true", "interop.appendWindowsPath=true"),
    ("[automount]\nenabled=false", "[automount]\nenabled=true", "automount.enabled=true"),
    ("[gpu]\nenabled=false", "[gpu]\nenabled=true", "gpu.enabled=true"),
    ("default=root", "default=ci-runner", "user.default=ci-runner"),
])
def test_a2_wsl_conf_loosened_fails(old, new, named):
    assert ps.check_wsl_conf(GOOD_WSL_CONF) == []
    assert old in GOOD_WSL_CONF
    failures = ps.check_wsl_conf(GOOD_WSL_CONF.replace(old, new))
    assert any(named in f for f in failures), failures


@pytest.mark.parametrize("text, named", [
    (GOOD_WSLCONFIG + "networkingMode=mirrored\n", ".wslconfig wsl2.networkingMode=mirrored"),
    ("[wsl2]\nprocessors=8\nmemory=12GB\n", ".wslconfig wsl2.guiApplications absent"),
    ("[wsl2]\nprocessors=16\nmemory=12GB\nguiApplications=false\n", "wsl2.processors=16"),
    (None, ".wslconfig wsl2.memory absent"),
])
def test_a2_wslconfig_loosened_fails(text, named):
    assert ps.check_wslconfig(GOOD_WSLCONFIG) == []
    assert ps.check_wslconfig(GOOD_WSLCONFIG + "networkingMode=nat\n") == []
    assert any(named in f for f in ps.check_wslconfig(text))


def test_a2_unit_without_no_new_privileges_fails():
    assert ps.check_unit(1, "yes\n") == []
    assert ps.check_unit(2, "no") == ["unit blaz-top-wsl-2 NoNewPrivileges=no"]


def test_a3_wslconfig_merge_keeps_the_owners_lines_and_refuses_conflicts():
    merged, conflicts = ps.merge_wslconfig("# mine\n[wsl2]\nswap=0\n\n[experimental]\nx=1\n")
    assert conflicts == []
    assert merged == ("# mine\n[wsl2]\nswap=0\nprocessors=8\nmemory=12GB\n"
                      "guiApplications=false\n\n[experimental]\nx=1\n")
    assert ps.merge_wslconfig(None)[0] == GOOD_WSLCONFIG
    assert ps.merge_wslconfig(merged) == (merged, [])
    for text, key in (("[wsl2]\nmemory=16GB\n", "wsl2.memory=16GB"),
                      ("[wsl2]\nnetworkingMode=mirrored\n", "wsl2.networkingMode=mirrored"),
                      ("[wsl2]\nprocessors=4\n", "wsl2.processors=4")):
        _, conflicts = ps.merge_wslconfig(text)
        assert any(c.startswith(key) for c in conflicts)


def test_c16_verify_runs_the_check_under_setpriv_as_the_units_account():
    argv = ps.verify_check_argv("Micah", 5000)
    assert argv[:6] == ["setpriv", "--reuid=ci-runner", "--regid=ci-runner", "--init-groups",
                        "--no-new-privs", "--reset-env"]
    assert argv[-6:] == ["--context", "verify", "--win-user", "Micah", "--local-port", "5000"]
    assert ps.root_settings_argv()[2:] == ["--context", "verify", "--root-settings"]
    # The root-side run reports itself as verify's, not as a job's (reading 7).
    report = ic.run_check(ic.build_parser().parse_args(ps.root_settings_argv()[2:]),
                          euid=1001, runner=lambda argv, env=None: (0, ""))
    assert report["context"] == "verify" and report["root_settings"] is True


# ---------------------------------------------------------------- the fake Windows host


def check_line(ok=True, failures=(), nproc=8, mem=12249308) -> str:
    probes = [{"probe": "root", "result": "reachable" if failures else "blocked",
               "failures": list(failures), "detail": {}},
              {"probe": "settings", "result": "info", "failures": [],
               "detail": {"nproc": nproc, "mem_total_kib": mem}}]
    return "PRIVATE-CI-CHECK " + json.dumps({"ok": ok, "failed": [] if ok else ["root"],
                                             "probes": probes}) + "\n"


class FakeWindows:
    """wsl.exe, git, PowerShell and tasklist, recording every argv and stdin."""

    def __init__(self):
        self.calls: list[tuple[list[str], bytes | None]] = []
        self.distros: dict[str, str] = {}
        self.instances = {n: {"n": n, "unit": ps.unit_name(n), "unpacked": False,
                              "active": "inactive", "no_new_privileges": "yes",
                              "active_enter_epoch": 0, "last_worker_epoch": 0,
                              "runner": None} for n in ps.INSTANCES}
        self.keepalive = False
        self.wsl_conf = GOOD_WSL_CONF
        self.nnp = "yes"
        self.hidden = "-/dev/dxg -/usr/lib/wsl -/mnt/wslg"
        self.lib_listing = (f"d root root 755 {ps.GUEST_LIB}\n" + "".join(
            f"f root root 755 {dest}\n" for _, dest, _ in ps.GUEST_FILES))
        self.root_report = check_line()
        self.verify_report = check_line()
        self.dirty = ""
        self.stubs = ["/mnt/c", "/mnt/d"]
        self.journal = lambda unit, reads: "-- No entries --\n"
        self.journal_reads = 0
        self.hide_state = "active"

    def __call__(self, argv, stdin_bytes=None):
        self.calls.append((list(argv), stdin_bytes))
        if argv[:2] == ["wsl.exe", "--version"]:
            return 0, "WSL version: 2.6.1.0\r\nKernel version: 6.6.87.2-1\r\n".encode("utf-16-le"), b""
        if argv[:3] == ["wsl.exe", "-l", "-v"]:
            rows = "".join(f"  {name}    {state}    2\r\n" for name, state in self.distros.items())
            text = ("  NAME    STATE    VERSION\r\n" + rows) if rows else \
                "Windows Subsystem for Linux has no installed distributions.\r\n"
            return 0, text.encode("utf-16-le"), b""
        if argv[:2] == ["wsl.exe", "--install"]:
            self.distros[ps.DISTRO] = "Stopped"
            return 0, b"", b""
        if argv[:2] in (["wsl.exe", "--shutdown"], ["wsl.exe", "--terminate"]):
            for name in self.distros:
                self.distros[name] = "Stopped"
            self.keepalive = False
            return 0, b"", b""
        if argv[:3] == ["wsl.exe", "-d", ps.DISTRO]:
            self.distros[ps.DISTRO] = "Running"
            return self.guest(argv[6:], stdin_bytes)
        if argv[0] == "git":
            if "rev-parse" in argv:
                return 0, b"0123456789abcdef0123456789abcdef01234567\n", b""
            return 0, self.dirty.encode("ascii"), b""
        if argv[0] == "powershell.exe":
            line = f"wsl.exe {ps.KEEPALIVE_ARGS}\r\n" if self.keepalive else ""
            return 0, line.encode("ascii"), b""
        if argv[0] == "tasklist.exe":
            return 0, b"INFO: No tasks are running which match the specified criteria.\r\n", b""
        raise AssertionError(f"unexpected argv {argv}")

    def guest(self, argv, stdin_bytes):
        if argv[:2] == ["/bin/sh", "-c"]:
            return 0, b"", b""
        if argv[:2] == ["/bin/bash", ps.PROVISION]:
            sub, rest = argv[2], argv[3:]
            if sub == "unpack":
                self.instances[int(rest[0])]["unpacked"] = True
            elif sub == "register":
                n = int(rest[0])
                self.instances[n]["runner"] = {"AgentName": ps.runner_name(n),
                                               "PoolName": "private-ci",
                                               "GitHubUrl": ps.ORG_URL}
            elif sub == "service":
                self.instances[int(rest[0])]["active"] = "active"
            elif sub == "fresh":
                self.instances[int(rest[0])]["unpacked"] = True
                self.instances[int(rest[0])]["runner"] = None
            elif sub == "quiesce":
                for item in self.instances.values():
                    item["active"] = "inactive"
            elif sub == "start":
                for item in self.instances.values():
                    item["active"] = "active"
            elif sub == "state":
                data = {"instances": list(self.instances.values()), "now_epoch": 1_000_000}
                return 0, (json.dumps(data) + "\n").encode("utf-8"), b""
            elif sub == "workers":
                return 0, b"0\n", b""
            return 0, b"", b""
        if argv[:2] == ["cat", "/etc/wsl.conf"]:
            return 0, self.wsl_conf.encode("utf-8"), b""
        if argv[0] == "journalctl":
            self.journal_reads += 1
            return 0, self.journal(argv[2], self.journal_reads).encode("utf-8"), b""
        if argv[:2] == ["find", "/usr"]:
            return 0, "".join(f"d root root 755 {path}\n"
                              for path in ps.GUEST_LIB_PARENTS).encode("ascii"), b""
        if argv[:2] == ["find", ps.GUEST_LIB]:
            return 0, self.lib_listing.encode("ascii"), b""
        if argv == ["systemctl", "is-active", ps.HIDE_UNIT]:
            return 0, (self.hide_state + "\n").encode("ascii"), b""
        if argv[0] == "systemctl" and "InaccessiblePaths" in argv:
            return 0, (self.hidden + "\n").encode("ascii"), b""
        if argv[0] == "systemctl":
            return 0, (self.nnp + "\n").encode("ascii"), b""
        if argv == ps.clear_stubs_argv():
            removed, self.stubs = self.stubs, []
            return 0, (json.dumps({"removed": removed, "kept": []}) + "\n").encode("utf-8"), b""
        if argv == ps.root_settings_argv():
            return 0, self.root_report.encode("utf-8"), b""
        if argv[0] == "setpriv":
            return 0, self.verify_report.encode("utf-8"), b""
        raise AssertionError(f"unexpected guest argv {argv}")

    def entered(self) -> list[list[str]]:
        return [argv for argv, _ in self.calls if argv[:3] == ["wsl.exe", "-d", ps.DISTRO]]


class FakeTasks:
    def __init__(self, windows: FakeWindows):
        self.windows = windows
        self.tasks: dict[str, bool] = {}
        self.calls: list[list[str]] = []

    def __call__(self, args):
        self.calls.append(list(args))
        if args[0] == "/Query":
            if args[2] not in self.tasks:
                raise pw.WatchError("schtasks /Query exited 1: not found")
        elif args[0] == "/Create":
            self.tasks[args[2]] = True
        elif args[0] == "/Run":
            self.windows.keepalive = True
        elif args[0] == "/Delete":
            self.tasks.pop(args[2], None)
        return "SUCCESS"


@pytest.fixture
def windows(tmp_path, monkeypatch):
    profile_dir = tmp_path / "profile" / "Micah"
    profile_dir.mkdir(parents=True)
    monkeypatch.setenv("USERPROFILE", str(profile_dir))
    return FakeWindows()


TOKEN = "AABBCCTESTTOKEN0123456789"


def run_install(windows: FakeWindows, state_dir: Path, prompts: list[str]):
    tasks = FakeTasks(windows)

    def prompt(reasons):
        prompts.append("asked")
        windows.calls.append((["<prompt>", *reasons], None))
        return TOKEN
    result = ps.install(ps.Host(windows), state_dir, prompt=prompt, sleep=lambda s: None,
                        schtasks=tasks, now=NOW)
    return result, tasks


def test_a3_a16_a17_a23_install_then_reinstall(windows, tmp_path):
    state_dir = tmp_path / "state"
    prompts: list[str] = []
    first, tasks = run_install(windows, state_dir, prompts)
    assert first["ok"], first["verify"]["failures"]
    assert prompts == ["asked"]
    assert first["prompted_for_token"] is True
    assert (Path(ps.profile()) / ".wslconfig").read_text(encoding="utf-8") == GOOD_WSLCONFIG
    assert sorted(tasks.tasks) == [ps.START_TASK, pw.TASK_NAME]
    stubs = next(s for s in first["steps"] if s["step"] == "drive stubs")
    assert stubs["changed"] and stubs["removed"] == ["/mnt/c", "/mnt/d"]
    calls = [argv for argv, _ in windows.calls]
    restart = next(i for i, argv in enumerate(calls) if argv[:2] == ["wsl.exe", "--shutdown"])
    clear = next(i for i, argv in enumerate(calls) if argv[6:] == ps.clear_stubs_argv())
    assert restart < clear, "the stubs are removed only after the restart that applies wsl.conf"

    # A16: the token appears only in the stdin piped to the two register calls.
    carriers = [(argv, data) for argv, data in windows.calls if data and TOKEN.encode() in data]
    assert [argv[6:10] for argv, _ in carriers] == [
        ["/bin/bash", ps.PROVISION, "register", "1"], ["/bin/bash", ps.PROVISION, "register", "2"]]
    assert all(TOKEN not in " ".join(argv) for argv, _ in windows.calls)
    assert TOKEN not in json.dumps(first)
    for path in list(state_dir.rglob("*")) + list(tmp_path.joinpath("profile").rglob("*")):
        if path.is_file():
            assert TOKEN.encode() not in path.read_bytes(), path

    # A23: the registration request is recorded, labels and group, with no token.
    record = json.loads((state_dir / "install.json").read_text(encoding="utf-8"))
    for n in ps.INSTANCES:
        held = record["instances"][str(n)]
        assert held["labels"] == ["private-ci"] and held["group"] == "private-ci"
        assert held["no_default_labels"] is True
        assert "--no-default-labels" in held["request"]

    # A17: a second run over the complete install prompts for nothing and changes nothing.
    windows.calls.clear()
    # Item 5 (reading 8): three days later, so a day in the task's definition would show.
    second = ps.install(ps.Host(windows), state_dir, prompt=lambda r: pytest.fail("prompted"),
                        sleep=lambda s: None, schtasks=tasks, now=NOW + timedelta(days=3))
    assert second["ok"]
    assert second["prompted_for_token"] is False
    assert [s for s in second["steps"] if s["changed"]] == []
    assert not any("register" in argv for argv, _ in windows.calls)


def test_a3_install_refuses_a_conflicting_wslconfig_and_writes_nothing(windows, tmp_path):
    target = ps.profile() / ".wslconfig"
    target.write_text("[wsl2]\nnetworkingMode=mirrored\n", encoding="utf-8")
    with pytest.raises(ps.SetupError, match="networkingMode=mirrored"):
        run_install(windows, tmp_path / "state", [])
    assert target.read_text(encoding="utf-8") == "[wsl2]\nnetworkingMode=mirrored\n"
    assert windows.entered() == []


@pytest.mark.parametrize("loosen, named", [
    ("wsl_conf", "wsl.conf interop.enabled=true"),
    ("unit", "unit blaz-top-wsl-1 NoNewPrivileges=no"),
    ("root", "root-settings: sudoers: ci-runner has sudo rights"),
    ("job", "root: NoNewPrivs: 0"),
])
def test_a3_verify_fails_on_each_mismatch(windows, loosen, named):
    if loosen == "wsl_conf":
        windows.wsl_conf = GOOD_WSL_CONF.replace("[interop]\nenabled=false", "[interop]\nenabled=true")
    elif loosen == "unit":
        windows.nnp = "no"
    elif loosen == "root":
        windows.root_report = check_line(False, ["sudoers: ci-runner has sudo rights"])
    else:
        windows.verify_report = check_line(False, ["NoNewPrivs: 0"])
    good = ps.verify(ps.Host(FakeWindows()), wslconfig_text=GOOD_WSLCONFIG)
    assert good["ok"], good["failures"]
    found = ps.verify(ps.Host(windows), wslconfig_text=GOOD_WSLCONFIG)
    assert not found["ok"]
    assert any(named in f for f in found["failures"]), found["failures"]
    root_calls = [argv for argv in windows.entered() if argv[6:] == ps.root_settings_argv()]
    assert root_calls and root_calls[0][3:5] == ["-u", "root"]


REAL_SHELL = os.name != "nt" and shutil.which("bash") and shutil.which("systemctl")


def run_provision(subcommand: str, home: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "TRADECRAFT_CI_RUNNER_HOME": str(home)}
    return subprocess.run(["bash", str(PRIVATE_CI / "guest" / "provision.sh"), subcommand],
                          stdin=subprocess.DEVNULL, capture_output=True, env=env, timeout=60)


@pytest.mark.skipif(not REAL_SHELL, reason="needs Linux bash and systemctl")
def test_provision_state_reports_a_fresh_install_and_exits_0(tmp_path):
    """The owner's first install: `state` ran before any instance was unpacked, and
    `find` on the missing `_diag` ended the script under `set -euo pipefail` after
    it had printed only `{"instances": [`."""
    proc = run_provision("state", tmp_path)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    lines = proc.stdout.decode("utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert [item["n"] for item in data["instances"]] == [1, 2]
    for item in data["instances"]:
        assert item["unpacked"] is False and item["runner"] is None
        assert item["active_enter_epoch"] == 0 and item["last_worker_epoch"] == 0
        assert not ps.instance_matches(item["n"], item)
    assert isinstance(data["now_epoch"], int)


@pytest.mark.skipif(not REAL_SHELL, reason="needs Linux bash and systemctl")
def test_provision_workers_prints_a_count_and_exits_0(tmp_path):
    proc = run_provision("workers", tmp_path)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert proc.stdout.decode("utf-8").strip().isdigit()


def test_a11_registration_carries_only_the_private_ci_label():
    request = ps.registration_request(1)
    joined = " ".join(request)
    assert "--runnergroup private-ci --labels private-ci --no-default-labels" in joined
    assert "--token" not in request
    script = (PRIVATE_CI / "guest" / "provision.sh").read_text(encoding="utf-8")
    assert "--runnergroup private-ci --labels private-ci --no-default-labels" in script
    assert "--token" not in script
    assert "ACTIONS_RUNNER_INPUT_TOKEN" in script


def test_a12_nothing_names_the_windows_runner():
    """The only Windows-runner observation is C18's process-name query."""
    forbidden = re.compile(r"BLAZ-TOP|actions-runner\\|svc\.cmd|config\.cmd|"
                           r"actions\.runner\.(?!%s|\{ORG\}|service\.template)"
                           % re.escape("%s."))
    for path in PRIVATE_CI.rglob("*"):
        if path.suffix in (".py", ".sh", ".yml", ".conf", ".json"):
            text = path.read_text(encoding="utf-8")
            assert not forbidden.search(text), (path, forbidden.search(text))
    setup_text = (PRIVATE_CI / "setup.py").read_text(encoding="utf-8")
    assert setup_text.count('"Runner.Listener.exe"') == 1
    assert setup_text.count('"Runner.Worker.exe"') == 1


def test_a15_probe_never_enters_a_stopped_distribution(windows, tmp_path):
    windows.distros[ps.DISTRO] = "Stopped"
    windows.keepalive = False
    for options in ({"require_idle": 30}, {"after_restart": True}):
        windows.calls.clear()
        github = pw.GitHub(runner=lambda *a, **k: pytest.fail("probe reached GitHub"))
        found = ps.probe(ps.Host(windows), github, state_dir=tmp_path, sleep=lambda s: None,
                         **options)
        assert found["ok"] is False
        assert any("as Stopped, not Running" in f for f in found["failures"])
        assert any("no keepalive" in f for f in found["failures"])
        assert windows.entered() == []


def test_a4_the_check_is_read_from_anywhere_in_a_long_job_log():
    """Run 41272485277: each local job's log held the report early, behind a timestamp,
    and `probe` reported `no check output`."""
    report = {"ok": True, "failed": [], "context": "job",
              "probes": [{"probe": "settings", "result": "info", "failures": [],
                          "detail": {"nproc": 8, "mem_total_kib": 12249308}}]}
    lines = ["2026-11-01T04:18:30.1000000Z ##[group]Run python3 isolation_check.py",
             "2026-11-01T04:18:31.2000000Z " + ps.CHECK_PREFIX + json.dumps(report)]
    lines += [f"2026-11-01T04:18:{32 + i % 20:02d}.0000000Z post-step noise line {i}"
              for i in range(200)]
    log = "\n".join(lines) + "\n"
    assert len(log) > 9000 and ps.CHECK_PREFIX not in log[-2000:]
    assert ps.parse_check(log) == report
    missing = ps.parse_check("\n".join(lines[2:]))
    assert missing["failed"] == ["no check output"] and len(missing["output"]) == 2000


def job_span(name, start, end, runner):
    return {"name": name, "conclusion": "success", "runner_name": runner,
            "created_at": f"2026-11-01T04:18:{start:02d}Z",
            "started_at": f"2026-11-01T04:18:{start:02d}Z",
            "completed_at": f"2026-11-01T04:{end // 60 + 18:02d}:{end % 60:02d}Z"}


def test_a14_the_two_local_jobs_must_overlap():
    smoke = {"name": "smoke", "conclusion": "success", "runner_name": "blaz-top-wsl-1"}
    together = [job_span("local (1)", 0, 61, "blaz-top-wsl-1"),
                job_span("local (2)", 1, 62, "blaz-top-wsl-2"), smoke]
    assert ps.judge_jobs(together, timed=False) == []
    # Run 41272485277: local (2) began on the other instance as local (1) ended.
    in_turn = [job_span("local (1)", 0, 32, "blaz-top-wsl-2"),
               {**job_span("local (2)", 0, 0, "blaz-top-wsl-1"),
                "started_at": "2026-11-01T04:18:32Z", "completed_at": "2026-11-01T04:19:33Z"},
               smoke]
    assert ps.judge_jobs(in_turn, timed=False) == ["local: the two jobs did not run at the same time"]


def test_a15_the_probe_waits_for_both_runners_to_reconnect(windows):
    lines = {1: "1793505400.000000 host runsvc.sh[1]: A session for this runner already exists.\n",
             2: "1793505479.500000 host runsvc.sh[1]: 2026-11-01 04:17:59Z: Listening for Jobs\n"}
    windows.journal = lambda unit, reads: lines[1] + (lines[2] if reads > 2 else "")
    states = {1: {"active_enter_epoch": 1793505385}, 2: {"active_enter_epoch": 1793505385}}
    ticks = iter(range(0, 10_000, 10))
    found, waiting = ps.wait_until_listening(ps.Host(windows), states, sleep=lambda s: None,
                                             monotonic=lambda: next(ticks))
    assert waiting == [] and found == {"blaz-top-wsl-1": 94.5, "blaz-top-wsl-2": 94.5}
    assert ps.listening_epoch(lines[2], 1793505500) is None  # before the last start


def test_a15_a_runner_that_never_reconnects_fails_before_any_push(windows, tmp_path):
    windows.distros[ps.DISTRO] = "Running"
    windows.keepalive = True
    ticks = iter(range(0, 10_000, 10))
    github = pw.GitHub(runner=lambda *a, **k: pytest.fail("probe reached GitHub"))
    found = ps.probe(ps.Host(windows), github, after_restart=True, state_dir=tmp_path,
                     sleep=lambda s: None, monotonic=lambda: next(ticks))
    assert found["ok"] is False
    assert any("not connected to GitHub within 300 s" in f and "blaz-top-wsl-1" in f
               for f in found["failures"])
    assert found["reconnect_seconds"] == {}


def test_a4_probe_refuses_a_dirty_tree(windows, tmp_path):
    windows.dirty = " M tools/private_ci/setup.py\n"
    github = pw.GitHub(runner=lambda *a, **k: pytest.fail("probe reached GitHub"))
    with pytest.raises(ps.SetupError, match="dirty"):
        ps.probe(ps.Host(windows), github, state_dir=tmp_path)
    assert windows.entered() == []


def test_a10_a19_the_probe_workflow():
    files = ps.probe_files("Micah", 5123, "abc1234")
    workflow = files[ps.PROBE_PATH].decode("utf-8")
    assert "__" not in workflow
    for job in ("local:", "smoke:"):
        block = workflow.split(f"\n  {job}\n", 1)[1].split("\n  labels:", 1)[0]
        assert re.search(r"^    runs-on: private-ci$", block, re.M), job
    assert "--win-user 'Micah' --local-port 5123" in workflow
    assert "pair: [self-hosted, Linux, X64, Windows]" in workflow
    smoke_block = workflow.split("\n  smoke:\n", 1)[1].split("\n  labels:", 1)[0]
    assert re.search(r"^    needs: local$", smoke_block, re.M), \
        "smoke waits for local, so the two local jobs must hold both instances at once"
    assert 'runs-on: [private-ci, "${{ matrix.pair }}"]' in workflow
    assert "dotnet-version: '8.0.x'" in workflow and "pwsh -NoProfile" in workflow
    smoke = files["smoke.sh"].decode("utf-8")
    assert "playwright install chromium" in smoke
    assert "--with-deps" not in smoke.split("\n", 5)[-1] and "install-deps" not in smoke.split("set -euo", 1)[1]
    assert files["isolation_check.py"] == (PRIVATE_CI / "guest" / "isolation_check.py").read_bytes()


def test_a7_task_definitions():
    xml = pw.watch_task_xml("C:\\py\\pythonw.exe", "C:\\state\\bin\\watch.py", "C:\\state\\bin",
                            "BOX\\owner")
    assert "<LogonTrigger>" in xml and "<UserId>BOX\\owner</UserId>" in xml
    assert "<StartBoundary>2026-11-01T09:00:00</StartBoundary>" in xml
    # Item 6: a state directory other than the default reaches the task.
    elsewhere = pw.watch_task_xml("C:\\py\\pythonw.exe", "C:\\state\\bin\\watch.py",
                                  "C:\\state\\bin", "BOX\\owner", state_dir="D:\\lab state")
    assert "&quot;C:\\state\\bin\\watch.py&quot; --state-dir &quot;D:\\lab state&quot; logon" \
        in elsewhere
    assert pw.build_parser().parse_args(
        ["--state-dir", "D:\\lab state", "logon"]).state_dir == "D:\\lab state"
    assert "<DaysInterval>1</DaysInterval>" in xml
    assert "&quot;C:\\state\\bin\\watch.py&quot; logon" in xml
    assert "<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>" in xml
    assert "<ExecutionTimeLimit>PT5H</ExecutionTimeLimit>" in xml
    assert "<StartWhenAvailable>true</StartWhenAvailable>" in xml
    start = ps.start_task_xml("C:\\py\\pythonw.exe", "C:\\state\\bin\\keepalive.py",
                              "C:\\state\\bin", "BOX\\owner")
    assert "<LogonTrigger>" in start and "<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>" in start
    assert "keepalive.py" in start
    keepalive = (PRIVATE_CI / "keepalive.py").read_text(encoding="utf-8")
    assert '["wsl.exe", "-d", DISTRO, "-u", "root", "--exec", "/bin/sleep", "infinity"]' \
        in keepalive
    assert ps.KEEPALIVE_ARGS == "-d tradecraft-ci -u root --exec /bin/sleep infinity"


def test_a7_logon_runs_rerun_then_watch_then_follow(monkeypatch, tmp_path):
    order = []
    monkeypatch.setattr(pw, "rerun_dropped",
                        lambda github, state_dir, follow_minutes=0, **k:
                        order.append(("rerun", follow_minutes)) or {})
    monkeypatch.setattr(pw, "watch", lambda github, state_dir, moment, **k:
                        order.append(("watch", None)) or {})
    pw.logon(None, tmp_path, clock=lambda: NOW)
    assert order == [("rerun", 0), ("watch", None), ("rerun", 240)]


# ---------------------------------------------------------------- the watch (A5, A8, A9, A13)


def stamp(hours_ago: float) -> str:
    return pw.iso(NOW - timedelta(hours=hours_ago))


def job(job_id, name, *, run_id=1, attempt=1, labels=("ubuntu-latest",), runner="GitHub Actions 1",
        group=0, conclusion="success", status="completed", created=2.0, seconds=30,
        steps=None, never_ran=False):
    created_at = NOW - timedelta(hours=created)
    record = {"id": job_id, "run_id": run_id, "run_attempt": attempt, "name": name,
              "status": status, "conclusion": conclusion if status == "completed" else None,
              "labels": list(labels), "runner_id": 0 if never_ran else 7,
              "runner_name": "" if never_ran else runner, "runner_group_id": 0 if never_ran else group,
              "created_at": pw.iso(created_at), "started_at": pw.iso(created_at),
              "completed_at": pw.iso(created_at + timedelta(seconds=seconds))
              if status == "completed" else None,
              "steps": steps if steps is not None else ([] if never_ran else [{"name": "x"}])}
    return record


class FakeActions:
    """A small Actions API: runs with attempts, their jobs, and every call made."""

    def __init__(self, shape="carried"):
        self.runs: dict[tuple[str, int], dict] = {}
        self.jobs: dict[tuple[str, int], list[dict]] = {}
        self.calls: list[str] = []
        self.comments: list[dict] = []
        self.shape = shape
        self.notes: dict[int, list[dict]] = {}

    def add_run(self, repo, run_id, path, jobs, *, status="completed", attempt=1, created=30.0):
        self.runs[(repo, run_id)] = {"id": run_id, "path": path, "status": status,
                                     "run_attempt": attempt, "created_at": stamp(created),
                                     "html_url": f"https://github.com/{repo}/actions/runs/{run_id}"}
        self.jobs[(repo, run_id)] = jobs

    def runs_of(self, repo):
        return [dict(run) for (r, _), run in sorted(self.runs.items()) if r == repo]

    def run_of(self, repo, run_id):
        return dict(self.runs[(repo, run_id)])

    def jobs_of(self, repo, run_id, which="all"):
        held = self.jobs[(repo, run_id)]
        if which == "all":
            return [dict(j) for j in held]
        attempt = self.runs[(repo, run_id)]["run_attempt"]
        return [dict(j) for j in held if j["run_attempt"] == attempt]

    def send(self, method, endpoint, payload=None):
        self.calls.append(f"{method} {endpoint}")
        if endpoint.endswith("/comments"):
            comment = {"id": 9000 + len(self.comments), "user": {"login": "Grimblaz"},
                       "body": payload["body"], "html_url": "https://example.invalid/c"}
            self.comments.append(comment)
            return comment
        repo = "/".join(endpoint.split("/")[1:3])
        if "/runs/" in endpoint:
            run_id = int(endpoint.split("/runs/")[1].split("/")[0])
        else:
            job_id = int(endpoint.split("/jobs/")[1].split("/")[0])
            run_id = next(j["run_id"] for (r, _), jobs in self.jobs.items() if r == repo
                          for j in jobs if j["id"] == job_id)
        run = self.runs[(repo, run_id)]
        run["run_attempt"] += 1
        run["status"] = "queued"
        return None

    def complete_attempt(self, repo, run_id, results: dict[str, dict]):
        """GitHub finishes the new attempt: re-run jobs get these records."""
        run = self.runs[(repo, run_id)]
        attempt = run["run_attempt"]
        held = self.jobs[(repo, run_id)]
        previous = {j["name"]: j for j in held if j["run_attempt"] == attempt - 1}
        next_id = max(j["id"] for j in held) + 1
        for name, record in results.items():
            held.append({**record, "id": next_id, "run_attempt": attempt, "run_id": run_id})
            next_id += 1
        if self.shape == "carried":
            for name, record in previous.items():
                if name not in results:
                    held.append({**record, "id": record["id"], "run_attempt": attempt})
        run["status"] = "completed"


class GitHubView:
    """Adapts FakeActions to the method names watch.py calls."""

    def __init__(self, actions: FakeActions):
        self.actions = actions

    def runs(self, repo, since):
        return self.actions.runs_of(repo)

    def run(self, repo, run_id):
        return self.actions.run_of(repo, run_id)

    def jobs(self, repo, run_id, which="all"):
        return self.actions.jobs_of(repo, run_id, which)

    def send(self, method, endpoint, payload=None):
        return self.actions.send(method, endpoint, payload)

    def annotations(self, repo, job_id):
        return list(self.actions.notes.get(job_id, []))

    def comments(self, repo, issue):
        return list(self.actions.comments)


HOSTED = pw.load_hosted()
GATE = ".github/workflows/self-change-proof.yml"
REVIEW = ".github/workflows/connected-review.yml"
CI = ".github/workflows/ci.yml"


def test_a5_the_declared_list_is_the_gate_and_the_reviewers_two_hosted_jobs():
    assert [(e["path"], e["job"]) for e in HOSTED] == [
        (GATE, "Change proof (required) / Change proof"),
        (REVIEW, "connected-review / prepare"),
        (REVIEW, "connected-review / report"),
        (CI, "Deploy to GitHub Pages")]


def october(actions: FakeActions) -> None:
    """About 210 gate runs and 89 reviewer runs of two hosted jobs, each under a minute."""
    run_id = 1000
    for index in range(210):
        run_id += 1
        actions.add_run(DAEMON, run_id, GATE, [job(run_id * 10, "Change proof (required) / Change proof",
                                                   run_id=run_id, seconds=30, created=1 + index)])
    for index in range(89):
        run_id += 1
        actions.add_run(VERRA, run_id, REVIEW, [
            job(run_id * 10, "connected-review / prepare", run_id=run_id, seconds=20, created=1 + index),
            job(run_id * 10 + 1, "connected-review / review", run_id=run_id, labels=("self-hosted",),
                runner="BLAZ-TOP", group=1, seconds=300, created=1 + index),
            job(run_id * 10 + 2, "connected-review / report", run_id=run_id, seconds=20, created=1 + index)])


def moved(actions: FakeActions, repo: str, run_id: int) -> None:
    actions.add_run(repo, run_id, CI, [job(run_id * 10, "build", run_id=run_id, labels=("private-ci",),
                                          runner="blaz-top-wsl-1", group=5, seconds=600)])


def test_a8_quiet_on_octobers_declared_volumes(tmp_path):
    actions = FakeActions()
    october(actions)
    found = pw.watch(GitHubView(actions), tmp_path, NOW, repos=REPOS, hosted=HOSTED)
    assert found["minutes"] == 210 + 89 * 2  # each job rounded up to one minute
    assert found["alerts"] == [] and found["posted"] is None
    # October's fixture runs no Pages deploy, so only that entry goes unmatched.
    assert [(e["path"], e["job"]) for e in found["declared"] if not e["matched"]] == [
        (CI, "Deploy to GitHub Pages")]
    assert actions.calls == []


def test_a8_alerts_on_an_undeclared_hosted_job_in_a_moved_repository(tmp_path):
    actions = FakeActions()
    moved(actions, DAEMON, 50)
    actions.add_run(DAEMON, 51, ".github/workflows/nightly.yml",
                    [job(510, "sweep", run_id=51, seconds=125)])
    found = pw.watch(GitHubView(actions), tmp_path, NOW, repos=REPOS, hosted=HOSTED)
    key = f"unlisted:{DAEMON}:.github/workflows/nightly.yml:sweep:2026-10"
    assert found["would_alert"] == [key]
    body = actions.comments[0]["body"]
    assert body.startswith(f"<!-- lab:private-ci-watch:v1 keys={key} -->\n")
    assert f"`{DAEMON}` `.github/workflows/nightly.yml` job `sweep`, 3 min" in body
    # dedupe: the same key is never alerted twice
    again = pw.watch(GitHubView(actions), tmp_path, NOW, repos=REPOS, hosted=HOSTED)
    assert again["would_alert"] == [] and len(actions.comments) == 1


def test_a8_alerts_when_the_month_is_on_pace_past_1500(tmp_path):
    actions = FakeActions()
    for run_id in range(1, 61):
        actions.add_run(VERRA, run_id, GATE, [job(run_id, "Change proof (required) / Change proof",
                                                  run_id=run_id, seconds=60 * 25)])
    found = pw.watch(GitHubView(actions), tmp_path, NOW, repos=REPOS, hosted=HOSTED)
    assert found["minutes"] == 1500 and found["projected"] > 1500
    assert found["would_alert"] == ["pace:2026-10"]
    assert "projected" in actions.comments[0]["body"]


def test_c7_the_pace_floor_stops_a_busy_first_morning():
    early = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)
    assert pw.projection(300, early) == pytest.approx(300 * 30 / 7)
    assert pw.projection(300, early) < 1500


def test_a8_quiet_for_an_awaiting_carrier_repository_including_probe_only_jobs(tmp_path):
    actions = FakeActions()
    actions.add_run(CC, 70, pw.PROBE_PATH, [job(700, "local (1)", run_id=70, labels=("private-ci",),
                                               runner="blaz-top-wsl-1", group=5)])
    actions.add_run(CC, 71, CI, [job(710, "Validate", run_id=71, seconds=200)])
    found = pw.watch(GitHubView(actions), tmp_path, NOW, repos=REPOS, hosted=HOSTED)
    assert CC in found["awaiting_carrier"] and CC not in found["moved"]
    assert found["alerts"] == []


def test_a13_the_review_job_on_the_windows_runner_is_never_hosted():
    on_windows = job(1, "connected-review / review", labels=("self-hosted",), runner="BLAZ-TOP", group=1)
    dropped = job(2, "connected-review / review", labels=("self-hosted",), never_ran=True)
    assert not pw.is_hosted(on_windows) and not pw.is_hosted(dropped)
    billing_stop = job(3, "Change proof (required) / Change proof", never_ran=True)
    assert pw.is_hosted(billing_stop) and pw.job_minutes(billing_stop) == 0


def test_a9_an_alert_reaches_the_steward_as_intake():
    body = pw.alert_body([{"key": "pace:2026-10", "minutes": 900, "projected": 1600,
                           "top": [{"repo": VERRA, "path": CI, "job": "e2e", "minutes": 400}]}])
    watermark = {"id": 100, "user": {"login": "Grimblaz"},
                 "body": sw.watermark_body(100, 3, "2026-10-30T00:00:00Z", 950)}
    alert = {"id": 101, "user": {"login": "Grimblaz"}, "body": body}
    assert sw.classify_comment(alert) is None
    page = sw.Page(sw.LAB_REPO, 683, [watermark, alert])
    _, mark = page.watermark()
    assert [c["id"] for c in page.intake(mark["handled"])] == [101]
    assert pw.alerted_keys([alert]) == {"pace:2026-10"}
    assert pw.alerted_keys([{**alert, "user": {"login": "someone"}}]) == set()


# ---------------------------------------------------------------- the re-run (A6)


def dropped(job_id, name, run_id, labels=("private-ci",)):
    return job(job_id, name, run_id=run_id, labels=labels, never_ran=True, conclusion="failure",
               created=30, seconds=24 * 3600)


def ran(job_id, name, run_id, conclusion="success", attempt=1):
    return job(job_id, name, run_id=run_id, attempt=attempt, labels=("private-ci",),
               runner="blaz-top-wsl-1", group=5, conclusion=conclusion, created=30)


def rerun(actions, state_dir):
    return pw.rerun_pass(GitHubView(actions), state_dir, NOW, repos=REPOS)


@pytest.fixture
def state(tmp_path):
    return tmp_path / "state"


def test_a6a_a_lone_dropped_product_job_gets_one_run_level_call(state):
    actions = FakeActions()
    actions.add_run(CC, 1, CI, [dropped(11, "Validate", 1)])
    assert [c["kind"] for c in rerun(actions, state)["calls"]] == ["run"]
    assert actions.calls == [f"POST repos/{CC}/actions/runs/1/rerun-failed-jobs"]


def test_a6b_a_lone_dropped_review_job_gets_one_run_level_call(state):
    actions = FakeActions()
    actions.add_run(VERRA, 2, REVIEW, [
        job(21, "connected-review / prepare", run_id=2, created=30),
        dropped(22, "connected-review / review", 2, labels=("self-hosted",)),
        job(23, "connected-review / report", run_id=2, conclusion="skipped", created=30)])
    rerun(actions, state)
    assert actions.calls == [f"POST repos/{VERRA}/actions/runs/2/rerun-failed-jobs"]


def test_a6c_three_dropped_jobs_get_one_run_level_call_and_no_job_call(state):
    actions = FakeActions()
    actions.add_run(VERRA, 3, CI, [dropped(31, "fast-checks", 3), dropped(32, "tests", 3),
                                   dropped(33, "build", 3)])
    rerun(actions, state)
    assert actions.calls == [f"POST repos/{VERRA}/actions/runs/3/rerun-failed-jobs"]
    rerun(actions, state)  # the new attempt is queued: nothing more
    assert len(actions.calls) == 1


@pytest.mark.parametrize("shape", ["carried", "earlier"])
def test_a6d_a_mixed_run_gets_one_job_call_per_completed_attempt(state, shape):
    actions = FakeActions(shape)
    actions.add_run(VERRA, 4, CI, [dropped(41, "fast-checks", 4), dropped(42, "tests", 4),
                                   ran(43, "build", 4, conclusion="failure")])
    rerun(actions, state)
    assert actions.calls == [f"POST repos/{VERRA}/actions/jobs/41/rerun"]
    for status in ("queued", "in_progress"):
        actions.runs[(VERRA, 4)]["status"] = status
        rerun(actions, state)
        assert len(actions.calls) == 1
    # completed, but GitHub has not started the new attempt yet
    actions.runs[(VERRA, 4)].update(status="completed", run_attempt=1)
    rerun(actions, state)
    assert len(actions.calls) == 1
    actions.runs[(VERRA, 4)]["run_attempt"] = 2
    actions.complete_attempt(VERRA, 4, {"fast-checks": ran(0, "fast-checks", 4, attempt=2)})
    rerun(actions, state)
    assert actions.calls == [f"POST repos/{VERRA}/actions/jobs/41/rerun",
                             f"POST repos/{VERRA}/actions/jobs/42/rerun"]
    assert not any("/43/" in call or "rerun-failed-jobs" in call for call in actions.calls)


@pytest.mark.parametrize("near_miss", ["cancelled_by_person", "got_a_runner", "latest_ran",
                                       "probe", "under_24_hours"])
def test_a6e_near_misses_get_no_call(state, near_miss):
    actions = FakeActions()
    if near_miss == "cancelled_by_person":
        jobs = [job(51, "Validate", run_id=5, labels=("private-ci",), never_ran=True,
                    conclusion="cancelled", created=30, seconds=3600)]
    elif near_miss == "got_a_runner":
        jobs = [ran(51, "Validate", 5, conclusion="failure")]
    elif near_miss == "latest_ran":
        jobs = [dropped(51, "Validate", 5), ran(52, "Validate", 5, attempt=2)]
    elif near_miss == "probe":
        jobs = [dropped(51, "local (1)", 5)]
    else:
        jobs = [job(51, "Validate", run_id=5, labels=("private-ci",), never_ran=True,
                    conclusion="failure", created=30, seconds=20 * 3600)]
    actions.add_run(CC, 5, pw.PROBE_PATH if near_miss == "probe" else CI, jobs,
                    attempt=2 if near_miss == "latest_ran" else 1)
    assert rerun(actions, state)["calls"] == []
    assert actions.calls == []


def test_a6_follow_takes_up_the_next_owed_job_once_the_attempt_completes(state):
    actions = FakeActions("earlier")
    actions.add_run(VERRA, 6, CI, [dropped(61, "a", 6), dropped(62, "b", 6),
                                   ran(63, "c", 6, conclusion="failure")])
    ticks = []

    def sleep(seconds):
        ticks.append(seconds)
        run = actions.runs[(VERRA, 6)]
        if run["status"] == "queued":
            name = "a" if len(actions.calls) == 1 else "b"
            actions.complete_attempt(VERRA, 6, {name: ran(0, name, 6, attempt=run["run_attempt"])})
    found = pw.rerun_dropped(GitHubView(actions), state, follow_minutes=30, repos=REPOS,
                             clock=lambda: NOW, sleep=sleep)
    assert [c["endpoint"] for c in found["calls"]] == ["actions/jobs/61/rerun",
                                                       "actions/jobs/62/rerun"]
    assert found["pending"] == []


# ---------------------------------------------------------------- holder reading 8 (PR #931)


st = _load("private_ci_state", PRIVATE_CI / "guest" / "state.py")
PROVISION_TEXT = (PRIVATE_CI / "guest" / "provision.sh").read_text(encoding="utf-8")
ALLOWED_ROOT_LINES = (
    re.compile(r'^dir=\$\(runner_dir "\$n"\)$'),
    re.compile(r'^"(ExecStart|WorkingDirectory)=\$dir(/runsvc\.sh)?" \\$'),
    re.compile(r'^"Environment=(DOTNET_INSTALL_DIR=\$dir/_dotnet|TMPDIR=\$dir/_tmp)"'),
    re.compile(r"^' _ \"\$dir\"$"),
)


def code_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")]


def test_item1_root_never_works_in_the_account_tree():
    """Every line naming the runner tree runs as the account, or is unit text root writes.

    At 2b71440 root ran bin/installdependencies.sh and svc.sh from the tree, created
    _dotnet and _tmp in it with `install -d -o`, and touched, appended to and chowned
    .env there; each follows a symlink a job can plant.
    """
    offending = [line for line in code_lines(PROVISION_TEXT)
                 if "$dir" in line and "as_account" not in line
                 and not any(pattern.match(line) for pattern in ALLOWED_ROOT_LINES)]
    assert offending == []
    code = "\n".join(code_lines(PROVISION_TEXT))
    assert "installdependencies.sh" not in code and not re.search(r"\bsvc\.sh", code)
    assert not re.search(r"\bchown\b[^\n]*\$dir|install -d -o[^\n]*\$dir|>>\s*\"\$dir", code)
    # The instance settings live in the root-owned drop-in, beside the device it hides.
    assert "'InaccessiblePaths=-/dev/dxg -/usr/lib/wsl -/mnt/wslg'" in code
    assert '"Environment=DOTNET_INSTALL_DIR=$dir/_dotnet"' in code
    assert 'exec python3 "$(dirname "$0")/state.py"' in code
    # The packages installdependencies.sh would have installed are in base's list.
    for package in ("libkrb5-3", "zlib1g", "liblttng-ust1t64", "libssl3t64", "libicu74"):
        assert re.search(rf"\s{re.escape(package)}(\s|$)", PROVISION_TEXT)


linux_only = pytest.mark.skipif(os.name == "nt" or not hasattr(os, "O_NOFOLLOW"),
                                reason="O_NOFOLLOW and dir_fd are POSIX")


@linux_only
def test_item1_state_reads_no_symlink_and_keeps_only_three_fields(tmp_path, monkeypatch):
    home = tmp_path / "home"
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps({"agentName": "blaz-top-wsl-1", "poolName": "private-ci",
                                  "gitHubUrl": "https://github.com/Grimblaz-and-Friends"}))
    one = home / "runner-1"
    one.mkdir(parents=True)
    (one / "config.sh").write_text("#!/bin/sh\n")
    os.chmod(one / "config.sh", 0o755)
    (one / ".runner").symlink_to(secret)              # a symlinked .runner is not read
    (one / "_diag").symlink_to(tmp_path)              # nor is a symlinked _diag
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "config.sh").write_text("#!/bin/sh\n")
    os.chmod(elsewhere / "config.sh", 0o755)
    (home / "runner-2").symlink_to(elsewhere)         # nor a symlinked runner directory
    monkeypatch.setenv("TRADECRAFT_CI_RUNNER_HOME", str(home))
    found = st.state(systemctl=lambda argv: "", to_epoch=lambda text: 0)
    first, second = found["instances"]
    assert first["unpacked"] is True and first["runner"] is None
    assert first["last_worker_epoch"] == 0
    assert second["unpacked"] is False and second["runner"] is None
    # A real .runner is untrusted text: three short strings survive, nothing else.
    (one / ".runner").unlink()
    (one / ".runner").write_text(json.dumps({"AgentName": "blaz-top-wsl-1" + "x" * 500,
                                             "PoolName": "private-ci", "injected": {"a": 1},
                                             "gitHubUrl": 7}))
    kept = st.state(systemctl=lambda argv: "", to_epoch=lambda text: 0)["instances"][0]["runner"]
    assert kept == {"agentName": "blaz-top-wsl-1" + "x" * 186, "poolName": "private-ci"}
    (one / ".runner").write_text("{ not json")
    assert st.state(systemctl=lambda argv: "", to_epoch=lambda t: 0)["instances"][0]["runner"] is None


def lib(lines: list[str]) -> str:
    return "".join(f"d root root 755 {p}\n" for p in ps.GUEST_LIB_PARENTS) + "\n".join(lines)


@pytest.mark.parametrize("entry, named", [
    (f"l root root 777 {ps.GUEST_LIB}", "is a symlink"),
    (f"f ci-runner ci-runner 755 {ps.CHECK}", "is ci-runner:ci-runner, not root:root"),
    (f"f root root 775 {ps.CHECK}", "writable by others than root (775)"),
    (f"d root root 757 {ps.GUEST_LIB}", "writable by others than root (757)"),
])
def test_item1_an_unsafe_guest_library_fails(entry, named):
    good = [f"d root root 755 {ps.GUEST_LIB}", f"f root root 755 {ps.CHECK}"]
    assert ps.check_guest_lib(lib(good), require_present=True) == []
    failures = ps.check_guest_lib(lib(good + [entry]), require_present=True)
    assert any(named in f for f in failures), failures
    assert ps.check_guest_lib(lib([]), require_present=True) == [
        f"guest library: {ps.GUEST_LIB} is missing"]
    assert ps.check_guest_lib(lib([]), require_present=False) == []


def test_item1_install_refuses_an_unsafe_library_and_verify_names_it(windows, tmp_path):
    windows.lib_listing = (f"d root root 755 {ps.GUEST_LIB}\n"
                           f"f ci-runner ci-runner 755 {ps.CHECK}\n")
    with pytest.raises(ps.SetupError, match="isn't root's alone"):
        run_install(windows, tmp_path / "state", [])
    assert not any(argv[6:8] == ["/bin/sh", "-c"] for argv in windows.entered())
    found = ps.verify(ps.Host(windows), wslconfig_text=GOOD_WSLCONFIG)
    assert f"guest library: {ps.CHECK} is ci-runner:ci-runner, not root:root" in found["failures"]


def test_item4_verify_needs_the_device_hidden_and_the_caps_in_effect(windows):
    windows.hidden = ""
    windows.verify_report = check_line(nproc=16, mem=16_000_000)
    found = ps.verify(ps.Host(windows), wslconfig_text=GOOD_WSLCONFIG)
    assert "unit blaz-top-wsl-1 InaccessiblePaths lacks /dev/dxg" in found["failures"]
    assert any(f.startswith("caps: nproc 16, not 8") for f in found["failures"])
    assert any(f.startswith("caps: MemTotal 16000000 KiB") for f in found["failures"])


def test_item4_install_is_not_ok_while_wslconfig_waits_on_a_full_restart(windows, tmp_path):
    windows.distros["Ubuntu"] = "Running"
    result, _ = run_install(windows, tmp_path / "state", [])
    assert result["verify"]["ok"] and result["ok"] is False
    assert result["pending"] and "wsl --shutdown" in result["pending"][0]
    assert ["wsl.exe", "--shutdown"] not in [argv for argv, _ in windows.calls]


@pytest.mark.parametrize("loosen, named", [
    ("display", "wslg:DISPLAY set"),
    ("x0", "wslg:socket"),
    ("pulse", "PulseServer"),
    ("dxg", "gpu:"),
])
def test_item4_the_check_fails_on_each_wslg_route(tmp_path, quiet_loopback, loosen, named):
    root = good_root(tmp_path)
    environ = {"PATH": "/usr/bin:/bin"}
    if loosen == "display":
        environ["DISPLAY"] = ":0"
    elif loosen == "x0":
        (root / "tmp" / ".X11-unix").mkdir(parents=True)
        (root / "tmp" / ".X11-unix" / "X0").write_text("")
    elif loosen == "pulse":
        (root / "mnt" / "wslg").mkdir()
        (root / "mnt" / "wslg" / "PulseServer").write_text("")
    else:
        (root / "dev").mkdir()
        (root / "dev" / "dxg").write_text("")
    report = check(root, tmp_path, environ=environ)
    assert "wslg" in report["failed"]
    assert any(named in f for f in failures_of(report, "wslg"))
    if loosen == "dxg":
        # Hidden for the whole distribution, so verify's own process tests it too.
        assert "wslg" in check(root, tmp_path, environ=environ, context="verify")["failed"]
    # A job's own Xvfb on :99 is the distribution's display, not WSLg's.
    clean = good_root(tmp_path / "again")
    (clean / "tmp" / ".X11-unix").mkdir(parents=True)
    (clean / "tmp" / ".X11-unix" / "X99").write_text("")
    assert "wslg" not in check(clean, tmp_path, environ={"PATH": "/usr/bin"})["failed"]


def test_item13_a_dangling_drive_symlink_fails(tmp_path):
    mnt = tmp_path / "mnt"
    mnt.mkdir()
    try:
        (mnt / "c").symlink_to(tmp_path / "gone")
    except OSError:
        pytest.skip("creating a symlink needs a privilege this host lacks")
    assert not (mnt / "c").exists()
    assert ic.probe_drives(mnt, "Micah")["failures"] == [f"drive:{mnt / 'c'}"]


def test_item15_registration_names_the_organization():
    record = {"AgentName": "blaz-top-wsl-1", "PoolName": "private-ci",
              "GitHubUrl": "https://github.com/someone-else"}
    assert not ps.instance_registered(1, {"runner": record})
    assert ps.instance_registered(1, {"runner": {**record, "GitHubUrl": ps.ORG_URL + "/"}})


def test_item16_an_apostrophe_in_the_user_name_survives_the_shell():
    import shlex
    workflow = ps.probe_files("O'Brien", 5123, "abc1234")[ps.PROBE_PATH].decode("utf-8")
    line = next(l for l in workflow.splitlines() if "isolation_check.py" in l)
    argv = shlex.split(line.split("run:", 1)[1])
    assert argv[argv.index("--win-user") + 1] == "O'Brien"


def test_item17_only_the_two_provisioned_runners_count():
    smoke = {"name": "smoke", "conclusion": "success", "runner_name": "blaz-top-wsl-1"}
    jobs = [job_span("local (1)", 0, 61, "blaz-top-wsl-1"),
            job_span("local (2)", 1, 62, "blaz-top-wsl-3"), smoke]
    assert any("not ['blaz-top-wsl-1', 'blaz-top-wsl-2']" in f
               for f in ps.judge_jobs(jobs, timed=False))


class ProbeGitHub:
    """Enough of GitHub for the probe to push and find its run, then fail reading jobs."""

    def __init__(self):
        self.sent = []

    def send(self, method, endpoint, payload=None):
        self.sent.append(f"{method} {endpoint}")
        return {"sha": "0" * 40}

    def get(self, endpoint):
        if "/git/ref/" in endpoint:
            return {}
        return {"workflow_runs": [{"id": 77, "html_url": "https://example.invalid/run/77"}]}

    def jobs(self, repo, run_id, which="all"):
        raise pw.WatchError("gh api exited 1: rate limited")


LISTENING_LINE = "1793505479.500000 host runsvc.sh[1]: 2026-11-01 04:17:59Z: Listening for Jobs\n"


def test_item18_a_failure_after_the_run_exists_still_cancels_it(windows, tmp_path):
    github = ProbeGitHub()
    windows.journal = lambda unit, reads: LISTENING_LINE
    with pytest.raises(pw.WatchError, match="rate limited"):
        ps.probe(ps.Host(windows), github, state_dir=tmp_path, sleep=lambda s: None)
    assert github.sent[-1] == f"POST repos/{ps.PROBE_REPO}/actions/runs/77/cancel"


# ---------------------------------------------------------------- the watch, reading 8


def test_item2_jobs_before_the_move_never_alert(state):
    actions = FakeActions()
    actions.add_run(DAEMON, 60, ".github/workflows/nightly.yml",
                    [job(600, "sweep", run_id=60, seconds=125, created=100)], created=100)
    actions.add_run(DAEMON, 61, CI, [job(610, "build", run_id=61, labels=("private-ci",),
                                         runner="blaz-top-wsl-1", group=5, created=50)],
                    created=50)
    found = pw.watch(GitHubView(actions), state, NOW, repos=REPOS, hosted=HOSTED)
    assert found["alerts"] == [] and DAEMON in found["moved"]
    assert json.loads((state / "moved.json").read_text())[DAEMON] == stamp(50)
    actions.add_run(DAEMON, 62, ".github/workflows/nightly.yml",
                    [job(620, "sweep", run_id=62, seconds=125, created=10)], created=10)
    after = pw.watch(GitHubView(actions), state, NOW, repos=REPOS, hosted=HOSTED)
    assert after["would_alert"] == [f"unlisted:{DAEMON}:.github/workflows/nightly.yml:sweep:2026-10"]
    assert after["alerts"][0]["minutes"] == 3  # the post-move job only


def test_item2_a_moved_list_from_before_the_repair_still_reads(state):
    state.mkdir(parents=True)
    (state / "moved.json").write_text(json.dumps([DAEMON]))
    assert pw.load_moved(state / "moved.json") == {DAEMON: "1970-01-01T00:00:00Z"}


def test_item3_a_rejected_run_call_falls_back_to_the_job_call(state):
    actions = FakeActions()
    actions.add_run(CC, 1, CI, [dropped(11, "Validate", 1)])
    original = actions.send
    actions.reject = {f"repos/{CC}/actions/runs/1/rerun-failed-jobs"}

    def send(method, endpoint, payload=None):
        if endpoint in actions.reject:
            raise pw.WatchError("gh api exited 1: HTTP 422")
        return original(method, endpoint, payload)
    actions.send = send
    found = rerun(actions, state)
    assert [c["endpoint"] for c in found["calls"]] == [f"actions/jobs/11/rerun"]
    assert actions.calls == [f"POST repos/{CC}/actions/jobs/11/rerun"]


def test_item3_a_run_whose_calls_are_both_rejected_is_recorded_and_left(state):
    actions = FakeActions()
    actions.add_run(CC, 1, CI, [dropped(11, "Validate", 1)])
    actions.add_run(CC, 2, CI, [dropped(21, "Validate", 2)])

    def send(method, endpoint, payload=None):
        if "/runs/1/" in endpoint or "/jobs/11/" in endpoint:
            raise pw.WatchError("gh api exited 1: HTTP 403")
        return FakeActions.send(actions, method, endpoint, payload)
    actions.send = send
    first = rerun(actions, state)
    assert [c["kind"] for c in first["calls"]] == ["failed", "run"]  # run 2 still went
    recorded = json.loads((state / "rerun-failures.json").read_text())
    assert recorded[f"{CC}#1"]["attempt"] == 1 and len(recorded[f"{CC}#1"]["rejected"]) == 2
    second = rerun(actions, state)
    assert second["calls"] == []  # not retried while the run has no new attempt


def test_item3_logon_goes_on_when_the_rerun_raises(monkeypatch, tmp_path):
    order = []

    def boom(*a, **k):
        order.append("rerun")
        raise pw.WatchError("gh api exited 1: HTTP 500")
    monkeypatch.setattr(pw, "rerun_dropped", boom)
    monkeypatch.setattr(pw, "watch", lambda *a, **k: order.append("watch") or {})
    steps = pw.logon(None, tmp_path, clock=lambda: NOW)
    assert order == ["rerun", "watch", "rerun"]
    assert steps["errors"] == ["rerun: gh api exited 1: HTTP 500",
                               "follow: gh api exited 1: HTTP 500"]


def test_item7_alert_keys_with_spaces_and_commas_read_back():
    alerts = [{"key": "unlisted:A/B:.github/workflows/x.yml:Change proof (required) / "
                      "Change proof:2026-11", "repo": "A/B", "path": "p", "job": "j",
               "run_url": "u", "minutes": 1},
              {"key": "unlisted:A/B:p:a, b:2026-11", "repo": "A/B", "path": "p",
               "job": "j", "run_url": "u", "minutes": 1}]
    body = pw.alert_body(alerts)
    first = body.split("\n", 1)[0]
    assert pw.ALERT_MARKER.fullmatch(first)
    comment = {"user": {"login": "Grimblaz"}, "body": body}
    assert pw.alerted_keys([comment]) == {alert["key"] for alert in alerts}


def test_item8_a_run_from_last_month_billing_this_month_counts(state):
    actions = FakeActions()
    last_month = 24 * 35
    actions.add_run(VERRA, 80, CI, [job(800, "e2e", run_id=80, created=last_month, seconds=600),
                                    job(801, "e2e", run_id=80, attempt=2, created=5,
                                        seconds=600)], created=last_month, attempt=2)
    found = pw.watch(GitHubView(actions), state, NOW, repos=REPOS, hosted=HOSTED, post=False)
    assert found["minutes"] == 10  # the re-run this month, not the September attempt
    assert pw.RERUN_LOOKBACK_DAYS == 30


def test_item9_a_cancellation_github_annotates_as_a_persons_is_never_rerun(state):
    actions = FakeActions()
    actions.add_run(CC, 9, CI, [job(91, "Validate", run_id=9, labels=("private-ci",),
                                    never_ran=True, conclusion="cancelled", created=30,
                                    seconds=24 * 3600 - 120)])
    actions.notes[91] = [{"message": "The run was canceled by @Grimblaz."}]
    assert rerun(actions, state)["calls"] == []
    actions.notes[91] = []  # GitHub's own 24-hour drop leaves no such annotation
    assert [c["kind"] for c in rerun(actions, state)["calls"]] == ["run"]


# ---------------------------------------------------------------- holder reading 9 (PR #931)


def guest_subs(windows: FakeWindows) -> list[str]:
    """The provision.sh subcommands and the prompt, in the order they happened."""
    order = []
    for argv, _ in windows.calls:
        if argv[:1] == ["<prompt>"]:
            order.append("prompt")
        elif argv[6:8] == ["/bin/bash", ps.PROVISION]:
            order.append(" ".join(argv[8:10]) if argv[8] in ("fresh", "register", "service",
                                                            "unpack") else argv[8])
    return order


def test_finding1_no_account_process_runs_while_the_token_is_in_the_guest(windows, tmp_path):
    """The token is asked for only after both units stop and the account's processes end,
    and each instance registers from a fresh extraction, before any unit starts again."""
    prompts: list[str] = []
    run_install(windows, tmp_path / "state", prompts)
    order = [step for step in guest_subs(windows) if step not in ("base", "state")]
    assert order == ["quiesce", "prompt", "fresh 1", "register 1", "fresh 2", "register 2",
                     "service 1", "service 2", "start"]
    reasons = next(argv[1:] for argv, _ in windows.calls if argv[:1] == ["<prompt>"])
    assert reasons == ["blaz-top-wsl-1: its .runner record is missing or unreadable",
                       "blaz-top-wsl-2: its .runner record is missing or unreadable"]


def test_finding1_a_changed_record_is_named_before_the_prompt_and_rebuilt(windows, tmp_path):
    state_dir = tmp_path / "state"
    _, tasks = run_install(windows, state_dir, [])
    windows.instances[2]["runner"]["PoolName"] = "Default"   # a job edited .runner
    windows.calls.clear()
    seen = []

    def prompt(reasons):
        seen.extend(reasons)
        windows.calls.append((["<prompt>", *reasons], None))
        return TOKEN
    ps.install(ps.Host(windows), state_dir, prompt=prompt, sleep=lambda s: None,
               schtasks=tasks, now=NOW)
    assert seen == ["blaz-top-wsl-2: poolName is 'Default', not 'private-ci'"]
    order = [step for step in guest_subs(windows) if step != "state"]
    assert order == ["quiesce", "prompt", "fresh 2", "register 2", "service 2", "start"]


def test_finding1_the_guest_side_stops_everything_and_extracts_afresh():
    code = "\n".join(code_lines(PROVISION_TEXT))
    quiesce = code.split("quiesce() {", 1)[1].split("\n}", 1)[0]
    assert 'systemctl stop "$(unit_name "$n")"' in quiesce and "for n in 1 2" in quiesce
    assert 'pkill -KILL -u "$ACCOUNT"' in quiesce and 'pkill -KILL -U "$ACCOUNT"' in quiesce
    assert 'pgrep -u "$ACCOUNT"' in quiesce and quiesce.rstrip().endswith("return 1")
    assert 'crontab -r -u "$ACCOUNT"' in quiesce
    fresh = code.split("fresh() {", 1)[1].split("\n}", 1)[0]
    assert fresh.index('as_account rm -rf "$(runner_dir "$n")"') < fresh.index(
        'unpack "$n" "$version" "$sha" force')
    assert '[ -z "$force" ] && as_account test -x "$dir/config.sh"' in code
    assert re.search(r'for deny in /etc/cron\.deny /etc/at\.deny', code)


@linux_only
def test_finding2_a_fifo_planted_as_runner_cannot_hang_state(tmp_path, monkeypatch):
    import threading
    one = tmp_path / "home" / "runner-1"
    one.mkdir(parents=True)
    os.mkfifo(one / ".runner")
    monkeypatch.setenv("TRADECRAFT_CI_RUNNER_HOME", str(tmp_path / "home"))
    found = {}
    worker = threading.Thread(target=lambda: found.update(
        st.state(systemctl=lambda argv: "", to_epoch=lambda text: 0)), daemon=True)
    worker.start()
    worker.join(timeout=10)
    assert not worker.is_alive(), "state blocked opening a FIFO"
    assert found["instances"][0]["runner"] is None


def test_finding3_a_plain_probe_waits_for_both_runners_to_listen(windows, tmp_path):
    windows.journal = lambda unit, reads: LISTENING_LINE if reads > 2 else "-- No entries --\n"
    github = ProbeGitHub()
    ticks = iter(range(0, 10_000, 10))
    with pytest.raises(pw.WatchError, match="rate limited"):
        ps.probe(ps.Host(windows), github, state_dir=tmp_path, sleep=lambda s: None,
                 monotonic=lambda: next(ticks))
    assert windows.journal_reads >= 3        # it waited a round before pushing
    assert any("/git/blobs" in call for call in github.sent)


def test_finding3_a_plain_probe_pushes_nothing_while_a_runner_never_listens(windows, tmp_path):
    windows.journal = lambda unit, reads: "-- No entries --\n"
    ticks = iter(range(0, 10_000, 10))
    github = pw.GitHub(runner=lambda *a, **k: pytest.fail("probe reached GitHub"))
    found = ps.probe(ps.Host(windows), github, state_dir=tmp_path, sleep=lambda s: None,
                     monotonic=lambda: next(ticks))
    assert found["ok"] is False and found["reconnect_seconds"] == {}
    assert any("not connected to GitHub within 300 s" in f
               and "blaz-top-wsl-1, blaz-top-wsl-2" in f for f in found["failures"])


# ---------------------------------------------------------------- holder reading 10 (PR #931)


hr = _load("private_ci_hide_routes", PRIVATE_CI / "guest" / "hide_routes.py")


def test_r10_neither_the_keepalive_nor_the_default_user_is_the_runner_account():
    """At e70c280 the keepalive ran without -u under `[user] default=ci-runner`, so WSL
    opened a ci-runner login session and its user manager."""
    keepalive = _load("private_ci_keepalive", PRIVATE_CI / "keepalive.py")
    command = keepalive.COMMAND
    assert command[command.index("-u") + 1] == "root"
    assert command.index("-u") < command.index("--exec")
    assert ps.KEEPALIVE_ARGS == "-d tradecraft-ci -u root --exec /bin/sleep infinity"
    assert ps.KEEPALIVE_ARGS in " ".join(command)
    assert "default=root\n" in GOOD_WSL_CONF and "default=ci-runner" not in GOOD_WSL_CONF
    assert ps.WSL_CONF_EXPECTED[("user", "default")] == "root"
    assert any("user.default=ci-runner" in f for f in
               ps.check_wsl_conf(GOOD_WSL_CONF.replace("default=root", "default=ci-runner")))


def outside_process(root: Path, pid: int, uid: int, *, nnp: str = "1", reaches: bool = True):
    """A process in the fixture's /proc whose root view holds WSL's routes, or doesn't."""
    proc = root / "proc" / str(pid)
    (proc / "root").mkdir(parents=True)
    (proc / "status").write_text(f"Name:\tsleep\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n"
                                 f"NoNewPrivs:\t{nnp}\n", encoding="utf-8")
    if reaches:
        (proc / "root" / "dev").mkdir()
        (proc / "root" / "dev" / "dxg").write_text("")
        (proc / "root" / "usr" / "lib" / "wsl").mkdir(parents=True)
        (proc / "root" / "mnt" / "wslg").mkdir(parents=True)


def test_r10_the_check_fails_through_an_outside_same_uid_process(tmp_path, quiet_loopback):
    """The holder opened /dev/dxg through the keepalive's /proc/666/root from inside a unit."""
    root = good_root(tmp_path)
    outside_process(root, 666, 1001)
    report = check(root, tmp_path)
    assert "same-uid" in report["failed"]
    failures = failures_of(report, "same-uid")
    for route in ("gpu", "wsl-lib", "wslg"):
        assert any(f.startswith(f"same-uid:pid 666 (sleep) opens {route} at ") for f in failures)
    # The same view in a process of another account, or a same-uid process whose view
    # hides them, lends a job nothing.
    clean = good_root(tmp_path / "clean")
    outside_process(clean, 666, 0)
    outside_process(clean, 777, 1001, reaches=False)
    found = check(clean, tmp_path)
    assert found["ok"], found["failed"]
    assert next(p for p in found["probes"] if p["probe"] == "same-uid")["detail"] == {
        "processes": 1}


def test_r10_the_check_fails_on_a_same_uid_process_without_no_new_privs(tmp_path, quiet_loopback):
    root = good_root(tmp_path)
    outside_process(root, 812, 1001, nnp="0", reaches=False)
    assert failures_of(check(root, tmp_path), "same-uid") == [
        "same-uid:pid 812 (sleep) runs without no_new_privs"]


def test_r10_the_check_fails_when_the_user_manager_answers(tmp_path):
    root = good_root(tmp_path)
    answering = str(root / "run" / "user" / "1001" / "bus")
    found = ic.probe_same_uid(root / "proc", 1001, root / "run" / "user",
                              connects=lambda path: str(path) == answering)
    assert found["failures"] == [f"user-manager:{answering} answers"]
    assert ic.probe_same_uid(root / "proc", 1001, root / "run" / "user",
                             connects=lambda path: False)["result"] == "blocked"


def test_r10_the_routes_fail_in_verify_context_too(tmp_path, quiet_loopback):
    """Hidden for the whole distribution, so verify's own process tests them directly."""
    root = good_root(tmp_path)
    (root / "usr" / "lib" / "wsl").mkdir(parents=True)
    report = check(root, tmp_path, context="verify")
    assert any(f.startswith("wsl-lib:") and f.endswith(" opens")
               for f in failures_of(report, "wslg"))


SESSION = "      3  999 ci-runner -    pts/1 active no -\n"


@pytest.mark.parametrize("loosen, named", [
    ("session", "login-session: 3 999 ci-runner"),
    ("manager", "user-manager: user@999.service is active"),
    ("linger", "linger: "),
])
def test_r10_verify_fails_on_a_session_a_user_manager_or_linger(tmp_path, loosen, named):
    linger = tmp_path / "linger"
    linger.mkdir()

    def runner(argv, env=None):
        if argv[0] == "loginctl":
            return 0, SESSION if loosen == "session" else ""
        return (0, "active\n") if loosen == "manager" else (3, "inactive\n")
    if loosen == "linger":
        (linger / "ci-runner").write_text("")
    found = ic.probe_account_sessions(0, linger, 999, runner)
    assert found["result"] == "reachable"
    assert any(f.startswith(named) for f in found["failures"]), found["failures"]
    (linger / "ci-runner").unlink(missing_ok=True)
    quiet = ic.probe_account_sessions(
        0, linger, 999, lambda argv, env=None: (0, "") if argv[0] == "loginctl"
        else (3, "inactive\n"))
    assert quiet["result"] == "blocked"
    assert ic.probe_account_sessions(1001, linger, 999, runner)["result"] == "unknown"
    # verify's root-side run reads it beside sudo's answer.
    report = ic.run_check(ic.build_parser().parse_args(ps.root_settings_argv()[2:]),
                          root=tmp_path, euid=0, uid_of_account=lambda: 999,
                          runner=lambda argv, env=None: (0, NO_RIGHTS) if argv[0] == "sudo"
                          else runner(argv, env))
    assert [p["probe"] for p in report["probes"]] == ["root-settings", "sessions"]


def test_r10_verify_names_the_hide_unit_when_it_is_not_active(windows):
    windows.hide_state = "failed"
    found = ps.verify(ps.Host(windows), wslconfig_text=GOOD_WSLCONFIG)
    assert any(f.startswith("tradecraft-private-ci-hide.service is failed, not active")
               for f in found["failures"])


def fake_tree(entries: dict[str, int]):
    """An lstat over a dict of path -> st_mode, uid 0, that a fake bind mount rewrites."""
    def lstat(path):
        if path not in entries:
            raise FileNotFoundError(path)
        return os.stat_result((entries[path], 0, 0, 1, 0, 0, 0, 0, 0, 0))
    return lstat


def test_r10_hide_routes_mounts_a_mode_0_placeholder_over_each_route():
    import stat as st_mod
    entries = {"/dev/dxg": st_mod.S_IFCHR | 0o666, "/usr/lib/wsl": st_mod.S_IFDIR | 0o755,
               "/mnt/wslg": st_mod.S_IFDIR | 0o755}
    mounts = []

    def mount(source, target):
        mounts.append((source, target))
        entries[target] = st_mod.S_IFMT(entries[target])   # the placeholder's mode 0
    found = hr.hide(lstat=fake_tree(entries), mount=mount, make=lambda kind: f"/ph/{kind}")
    assert found["ok"] and mounts == [("/ph/chr", "/dev/dxg"), ("/ph/dir", "/usr/lib/wsl"),
                                      ("/ph/dir", "/mnt/wslg")]
    assert set(found["hidden"].values()) == {"newly hidden"}
    # Every boot and every account process runs it again: a hidden route is left alone.
    again = hr.hide(lstat=fake_tree(entries), mount=lambda s, t: pytest.fail("remounted"),
                    make=lambda kind: f"/ph/{kind}")
    assert again["ok"] and set(again["hidden"].values()) == {"hidden"}
    # Absent is fine; a symlink, or a mount that leaves the route open, fails closed.
    del entries["/mnt/wslg"]
    entries["/usr/lib/wsl"] = st_mod.S_IFLNK | 0o777
    entries["/dev/dxg"] = st_mod.S_IFCHR | 0o666
    bad = hr.hide(lstat=fake_tree(entries), mount=lambda s, t: None,
                  make=lambda kind: f"/ph/{kind}")
    assert bad["ok"] is False and bad["hidden"] == {"/mnt/wslg": "absent"}
    assert bad["failures"] == ["/dev/dxg is still reachable after the mount",
                               "/usr/lib/wsl is a symlink"]


def test_r10_the_whole_distribution_hides_before_any_account_process_starts():
    """Direction 3's mechanism: hidden at every boot before the runners and any login,
    each runner unit requires it and hides again first, and every account process the
    setup starts hides first."""
    code = "\n".join(code_lines(PROVISION_TEXT))
    for line in ("'DefaultDependencies=no'", "'Before=sysinit.target systemd-user-sessions.service'",
                 "'WantedBy=sysinit.target'", '"ExecStart=/usr/bin/python3 $LIB/hide_routes.py"',
                 'systemctl enable "$HIDE_UNIT"', 'systemctl start "$HIDE_UNIT"',
                 '"Requires=$HIDE_UNIT"', '"After=$HIDE_UNIT"',
                 '"ExecStartPre=+/usr/bin/python3 $LIB/hide_routes.py"',
                 'rm -f "/var/lib/systemd/linger/$ACCOUNT"'):
        assert line in code, line
    # Never restarted: the runner units require it, so a restart would restart them.
    assert 'systemctl restart "$HIDE_UNIT"' not in code
    assert "HIDE_UNIT=tradecraft-private-ci-hide.service" in code
    assert ps.HIDE_UNIT == "tradecraft-private-ci-hide.service"
    as_account = code.split("as_account() {", 1)[1].split("\n}", 1)[0]
    assert as_account.index('python3 "$LIB/hide_routes.py"') < as_account.index("setpriv")
    assert "exit 1" in as_account
    assert (f"{ps.GUEST_LIB}/hide_routes.py" in [dest for _, dest, _ in ps.GUEST_FILES])
    # The routes are hidden in the units' own namespaces too.
    assert "'InaccessiblePaths=-/dev/dxg -/usr/lib/wsl -/mnt/wslg'" in code


def test_r10_finding2_register_checks_for_account_processes_just_before_the_token():
    code = "\n".join(code_lines(PROVISION_TEXT))
    register = code.split("register() {", 1)[1].split("\n}", 1)[0]
    assert register.index("running=$(account_processes)") < register.index(
        "IFS= read -r ACTIONS_RUNNER_INPUT_TOKEN")
    assert register.index("exit 1") < register.index("IFS= read -r")
    helper = code.split("account_processes() {", 1)[1].split("\n}", 1)[0]
    assert 'pgrep -a "$flag" "$ACCOUNT"' in helper and "for flag in -u -U" in helper
    # A pgrep that fails reads as a process found, so register fails closed.
    assert "pgrep %s failed" in helper


def test_r10_finding2_the_prompt_says_ci_is_paused(monkeypatch, capsys):
    monkeypatch.setattr(ps.getpass, "getpass", lambda text: TOKEN)
    assert ps.ask_token(["blaz-top-wsl-2: its .runner record is missing or unreadable"]) == TOKEN
    said = capsys.readouterr().err
    assert "Both runners are stopped now, so private CI is paused" in said
    assert "they start again when install finishes" in said

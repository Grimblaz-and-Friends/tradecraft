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
    ("default=ci-runner", "default=root", "user.default=root"),
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
    assert ps.root_settings_argv()[-1] == "--root-settings"


# ---------------------------------------------------------------- the fake Windows host


def check_line(ok=True, failures=()) -> str:
    probes = [{"probe": "root", "result": "reachable" if failures else "blocked",
               "failures": list(failures), "detail": {}}]
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
        self.root_report = check_line()
        self.verify_report = check_line()
        self.dirty = ""

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
            elif sub == "state":
                data = {"instances": list(self.instances.values()), "now_epoch": 1_000_000}
                return 0, (json.dumps(data) + "\n").encode("utf-8"), b""
            elif sub == "workers":
                return 0, b"0\n", b""
            return 0, b"", b""
        if argv[:2] == ["cat", "/etc/wsl.conf"]:
            return 0, self.wsl_conf.encode("utf-8"), b""
        if argv[0] == "systemctl":
            return 0, (self.nnp + "\n").encode("ascii"), b""
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

    def prompt():
        prompts.append("asked")
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
    second = ps.install(ps.Host(windows), state_dir, prompt=lambda: pytest.fail("prompted"),
                        sleep=lambda s: None, schtasks=tasks, now=NOW)
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
                           r"actions\.runner\.(?!%s|\{ORG\})" % re.escape("%s."))
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
    assert 'runs-on: [private-ci, "${{ matrix.pair }}"]' in workflow
    assert "dotnet-version: '8.0.x'" in workflow and "pwsh -NoProfile" in workflow
    smoke = files["smoke.sh"].decode("utf-8")
    assert "playwright install chromium" in smoke
    assert "--with-deps" not in smoke.split("\n", 5)[-1] and "install-deps" not in smoke.split("set -euo", 1)[1]
    assert files["isolation_check.py"] == (PRIVATE_CI / "guest" / "isolation_check.py").read_bytes()


def test_a7_task_definitions():
    xml = pw.watch_task_xml("C:\\py\\pythonw.exe", "C:\\state\\bin\\watch.py", "C:\\state\\bin",
                            "BOX\\owner", NOW)
    assert "<LogonTrigger>" in xml and "<UserId>BOX\\owner</UserId>" in xml
    assert "<StartBoundary>2026-10-31T09:00:00</StartBoundary>" in xml
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
    assert '["wsl.exe", "-d", DISTRO, "--exec", "/bin/sleep", "infinity"]' in keepalive
    assert ps.KEEPALIVE_ARGS == "-d tradecraft-ci --exec /bin/sleep infinity"


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
        (REVIEW, "connected-review / report")]


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
    assert all(entry["matched"] for entry in found["declared"])
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

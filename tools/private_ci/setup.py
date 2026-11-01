"""Set up, verify and probe the private repositories' Linux runner on the owner's laptop (#929).

  install    re-runnable: .wslconfig caps, the tradecraft-ci distribution, the
             runner account and packages, two runner instances registered with
             only the private-ci label, the start and watch tasks, then verify.
  verify     read back every setting and run row 1's check under the unit's
             own privilege settings (C16).
  probe      push the probe workflow to Countdown-Clash's lab/private-ci-probe
             and judge its run: isolation in a real job, two instances, the
             smoke steps, and the label jobs left queued through an all-idle
             hold. `--after-restart` and `--require-idle MINUTES` first prove
             from outside that the distribution is already up (C17).
  status     what is installed, without changing anything.
  uninstall  remove the two tasks; the README lists what stays the owner's.

Run from the owner's terminal on Windows, from a tradecraft checkout at the
pull request's head. The registration token is asked for with no echo, only
when an instance needs registering, and reaches the distribution on stdin
alone (C10). Local state lives in `~/.tradecraft-lab/private-ci/`.

Standard library only. Prints one line of ASCII JSON per command.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(HERE))
from winio import utf8_stdio  # noqa: E402

import watch  # noqa: E402

DISTRO = "tradecraft-ci"
IMAGE = "Ubuntu-24.04"
ACCOUNT = "ci-runner"
LABEL = "private-ci"
GROUP = "private-ci"
ORG = "Grimblaz-and-Friends"
ORG_URL = f"https://github.com/{ORG}"
INSTANCES = (1, 2)
RUNNER_VERSION = "2.338.0"
# From the v2.338.0 release notes' SHA-256 list (actions/runner, published 2026-10-06).
RUNNER_SHA256 = "af4b794c1bc41d73d40535e3fe092a39f9679cd8d965954c2aca25a05ca41d32"
# Organizations-of-Verra's package-lock.json resolves playwright 1.57.0 (7b474cc).
PLAYWRIGHT_VERSION = "1.57.0"
START_TASK = "tradecraft-lab-private-ci-start"
PROBE_REPO = f"{ORG}/Countdown-Clash"
PROBE_BRANCH = "lab/private-ci-probe"
PROBE_PATH = watch.PROBE_PATH
GUEST_LIB = "/usr/local/lib/tradecraft-private-ci"
CHECK = f"{GUEST_LIB}/isolation_check.py"
PROVISION = f"{GUEST_LIB}/provision.sh"
KEEPALIVE_ARGS = f"-d {DISTRO} --exec /bin/sleep infinity"
GUEST_FILES = (("guest/provision.sh", PROVISION, "0755"),
               ("guest/isolation_check.py", CHECK, "0755"),
               ("guest/wsl.conf", f"{GUEST_LIB}/wsl.conf", "0644"))
BIN_FILES = ("watch.py", "hosted.json", "keepalive.py")
WSLCONFIG_EXPECTED = {"processors": "8", "memory": "12GB", "guiApplications": "false"}
WSL_CONF_EXPECTED = {
    ("boot", "systemd"): "true",
    ("automount", "enabled"): "false",
    ("automount", "mountFsTab"): "false",
    ("interop", "enabled"): "false",
    ("interop", "appendWindowsPath"): "false",
    ("gpu", "enabled"): "false",
    ("user", "default"): ACCOUNT,
}
HOLD_SECONDS = 300
HOLD_DEADLINE_SECONDS = 1800
SAMPLE_SECONDS = 10
JOB_WAIT_SECONDS = 3600
START_WITHIN_SECONDS = 120
CHECK_PREFIX = "PRIVATE-CI-CHECK "


class SetupError(Exception):
    """A step that cannot go on; the message names what to do."""


def default_state_dir() -> Path:
    return Path.home() / ".tradecraft-lab" / "private-ci"


def runner_name(n: int) -> str:
    return f"blaz-top-wsl-{n}"


def unit_name(n: int) -> str:
    return f"actions.runner.{ORG}.{runner_name(n)}.service"


def registration_request(n: int) -> list[str]:
    """The config.sh arguments for instance n; the token never appears here (C10)."""
    return ["./config.sh", "--unattended", "--url", ORG_URL, "--runnergroup", GROUP,
            "--labels", LABEL, "--no-default-labels", "--name", runner_name(n),
            "--work", "_work", "--replace"]


# ---------------------------------------------------------------- running programs


def run_program(argv: list[str], stdin_bytes: bytes | None = None,
                timeout: float = 1800) -> tuple[int, bytes, bytes]:
    """Run one program with every stream named and no console window."""
    feed = {"input": stdin_bytes} if stdin_bytes is not None else {"stdin": subprocess.DEVNULL}
    try:
        proc = subprocess.run(argv, **feed, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout, creationflags=watch.no_window())
    except FileNotFoundError as exc:
        raise SetupError(f"{argv[0]} was not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SetupError(f"{argv[0]} timed out after {int(timeout)} s") from exc
    return proc.returncode, proc.stdout, proc.stderr


def decode(data: bytes) -> str:
    """wsl.exe writes UTF-16LE on its own list and status commands; Linux writes UTF-8."""
    if len(data) >= 2 and (data[:2] == b"\xff\xfe" or b"\x00" in data[1:200:2]):
        text = data.decode("utf-16-le", errors="replace")
    else:
        text = data.decode("utf-8", errors="replace")
    return text.replace("\x00", "").lstrip(chr(0xFEFF))


class Host:
    """Every program this script runs, through one runner the tests replace."""

    def __init__(self, runner=None):
        self.runner = runner or run_program

    def run(self, argv: list[str], stdin_bytes: bytes | None = None,
            check: bool = True) -> tuple[int, str]:
        code, out, err = self.runner(argv, stdin_bytes)
        text = decode(out) + decode(err)
        if check and code != 0:
            tail = text.strip().splitlines()
            raise SetupError(f"{' '.join(argv[:6])} exited {code}: "
                             + (tail[-1] if tail else "no message"))
        return code, text

    def guest(self, *argv: str, user: str = "root", stdin_bytes: bytes | None = None,
              check: bool = True) -> tuple[int, str]:
        """Run a command inside the distribution. This boots it if it is stopped."""
        return self.run(["wsl.exe", "-d", DISTRO, "-u", user, "--exec", *argv],
                        stdin_bytes, check)


def distributions(host: Host) -> dict[str, str]:
    """`wsl -l -v` parsed to {name: state}. Reading the list never boots one."""
    _, text = host.run(["wsl.exe", "-l", "-v"], check=False)
    states = {}
    for line in text.splitlines():
        parts = line.replace("*", " ").split()
        if len(parts) == 3 and parts[2].isdigit() and parts[0] != "NAME":
            states[parts[0]] = parts[1]
    return states


def win_user() -> str:
    return Path(os.environ.get("USERPROFILE", str(Path.home()))).name


def profile() -> Path:
    return Path(os.environ.get("USERPROFILE", str(Path.home())))


# ---------------------------------------------------------------- settings (rows 1, 5)


def _sections(lines: list[str]) -> list[tuple[str, int, int]]:
    """(section name lowercased, first line index, end index) for an INI text."""
    found = []
    for index, line in enumerate(lines):
        match = re.fullmatch(r"\s*\[([^\]]+)\]\s*", line)
        if match:
            if found:
                found[-1] = (found[-1][0], found[-1][1], index)
            found.append((match.group(1).strip().lower(), index, len(lines)))
    return found


def _keys(lines: list[str], start: int, end: int) -> dict[str, tuple[int, str]]:
    keys = {}
    for index in range(start + 1, end):
        text = lines[index].split("#", 1)[0].split(";", 1)[0]
        if "=" in text:
            key, value = text.split("=", 1)
            keys[key.strip().lower()] = (index, value.strip())
    return keys


def merge_wslconfig(text: str | None) -> tuple[str, list[str]]:
    """The .wslconfig with the caps merged in, and every key the owner set otherwise.

    Lines are kept as they are, comments included; a missing key is added at the
    end of `[wsl2]`. A conflicting key is reported and never overwritten.
    """
    lines = (text or "").splitlines()
    sections = _sections(lines)
    wsl2 = next((s for s in sections if s[0] == "wsl2"), None)
    present = _keys(lines, wsl2[1], wsl2[2]) if wsl2 else {}
    conflicts = []
    for key, value in WSLCONFIG_EXPECTED.items():
        held = present.get(key.lower())
        if held and held[1].lower() != value.lower():
            conflicts.append(f"wsl2.{key}={held[1]} (the setup needs {value})")
    mode = present.get("networkingmode")
    if mode and mode[1].lower() != "nat":
        conflicts.append(f"wsl2.networkingMode={mode[1]} (the setup needs WSL's default NAT)")
    missing = [f"{key}={value}" for key, value in WSLCONFIG_EXPECTED.items()
               if key.lower() not in present]
    if wsl2 is None:
        lines = lines + ([""] if lines else []) + ["[wsl2]"] + missing
    else:
        end = wsl2[2]
        while end > wsl2[1] + 1 and not lines[end - 1].strip():
            end -= 1
        lines = lines[:end] + missing + lines[end:]
    return "\n".join(lines) + "\n", conflicts


def check_wslconfig(text: str | None) -> list[str]:
    """Each .wslconfig setting row 1 or row 5 needs that isn't applied."""
    lines = (text or "").splitlines()
    wsl2 = next((s for s in _sections(lines) if s[0] == "wsl2"), None)
    present = _keys(lines, wsl2[1], wsl2[2]) if wsl2 else {}
    failures = []
    for key, value in WSLCONFIG_EXPECTED.items():
        held = present.get(key.lower())
        if held is None:
            failures.append(f".wslconfig wsl2.{key} absent (needs {value})")
        elif held[1].lower() != value.lower():
            failures.append(f".wslconfig wsl2.{key}={held[1]} (needs {value})")
    mode = present.get("networkingmode")
    if mode and mode[1].lower() != "nat":
        failures.append(f".wslconfig wsl2.networkingMode={mode[1]} (needs NAT)")
    return failures


def check_wsl_conf(text: str) -> list[str]:
    """Each /etc/wsl.conf setting row 1 needs that isn't applied."""
    lines = text.splitlines()
    failures = []
    for (section, key), value in WSL_CONF_EXPECTED.items():
        found = next((s for s in _sections(lines) if s[0] == section.lower()), None)
        held = _keys(lines, found[1], found[2]).get(key.lower()) if found else None
        if held is None:
            failures.append(f"wsl.conf {section}.{key} absent (needs {value})")
        elif held[1].lower() != value.lower():
            failures.append(f"wsl.conf {section}.{key}={held[1]} (needs {value})")
    return failures


def check_unit(n: int, value: str) -> list[str]:
    value = value.strip()
    return [] if value == "yes" else [f"unit {runner_name(n)} NoNewPrivileges={value or 'unset'}"]


# ---------------------------------------------------------------- the check's command lines


def verify_check_argv(user: str, port: int) -> list[str]:
    """Row 1's check as the unit's account with no_new_privs, run from root (C16)."""
    return ["setpriv", f"--reuid={ACCOUNT}", f"--regid={ACCOUNT}", "--init-groups",
            "--no-new-privs", "--reset-env", "/usr/bin/python3", CHECK,
            "--context", "verify", "--win-user", user, "--local-port", str(port)]


def root_settings_argv() -> list[str]:
    return ["/usr/bin/python3", CHECK, "--root-settings"]


def parse_check(text: str) -> dict:
    for line in text.splitlines():
        if line.startswith(CHECK_PREFIX):
            return json.loads(line[len(CHECK_PREFIX):])
    return {"ok": False, "failed": ["no check output"], "probes": [], "output": text[-2000:]}


class Listener:
    """A Windows-side listener on 127.0.0.1 that records every connection it accepts."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.sock.settimeout(0.5)
        self.port = self.sock.getsockname()[1]
        self.accepted: list[str] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn, peer = self.sock.accept()
            except OSError:
                continue
            self.accepted.append(f"{peer[0]}:{peer[1]}")
            conn.close()

    def __enter__(self) -> "Listener":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        self.sock.close()


# ---------------------------------------------------------------- verify


def read_wslconfig() -> str | None:
    try:
        return (profile() / ".wslconfig").read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return None


def verify(host: Host, *, listener_factory=Listener, wslconfig_text=None) -> dict:
    """Row 1's settings read back, then the check as root and as the unit's account."""
    failures = []
    failures += check_wslconfig(read_wslconfig() if wslconfig_text is None else wslconfig_text)
    _, conf = host.guest("cat", "/etc/wsl.conf", check=False)
    failures += check_wsl_conf(conf)
    for n in INSTANCES:
        _, value = host.guest("systemctl", "show", "-p", "NoNewPrivileges", "--value",
                              unit_name(n), check=False)
        failures += check_unit(n, value)
    _, root_text = host.guest(*root_settings_argv(), check=False)
    root_report = parse_check(root_text)
    failures += [f"root-settings: {f}" for p in root_report.get("probes", [])
                 for f in p.get("failures", [])] or ([] if root_report.get("ok")
                                                     else ["root-settings: check failed"])
    with listener_factory() as listener:
        _, text = host.guest(*verify_check_argv(win_user(), listener.port), check=False)
        accepted = list(listener.accepted)
    report = parse_check(text)
    failures += [f"{p['probe']}: {f}" for p in report.get("probes", [])
                 for f in p.get("failures", [])]
    if not report.get("ok") and not any(p.get("failures") for p in report.get("probes", [])):
        failures.append("check: " + ",".join(report.get("failed", [])))
    if accepted:
        failures.append(f"local-services: the Windows listener accepted {accepted}")
    return {"command": "verify", "ok": not failures, "failures": failures,
            "check": report, "root_settings": root_report, "listener_accepted": accepted}


# ---------------------------------------------------------------- install


def digest(paths: list[Path]) -> str:
    hasher = hashlib.sha256()
    for path in paths:
        hasher.update(path.name.encode("ascii") + b"\0" + path.read_bytes())
    return hasher.hexdigest()


def tradecraft_commit(host: Host) -> str:
    _, text = host.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"])
    return text.strip()


def instance_state(host: Host) -> dict[int, dict]:
    _, text = host.guest("/bin/bash", PROVISION, "state")
    data = json.loads(text.strip().splitlines()[-1])
    return {int(item["n"]): item for item in data["instances"]}


def _field(record: dict | None, name: str):
    for key, value in (record or {}).items():
        if key.lower() == name.lower():
            return value
    return None


def instance_matches(n: int, state: dict) -> bool:
    """Registered here as instance n, in the private-ci group, and its service active."""
    record = state.get("runner")
    url = str(_field(record, "gitHubUrl") or "")
    return (str(_field(record, "agentName") or "") == runner_name(n)
            and str(_field(record, "poolName") or "") == GROUP
            and url.rstrip("/").lower() == ORG_URL.lower()
            and state.get("active") == "active")


def start_task_xml(interpreter: str, launcher: str, working_dir: str, user: str) -> str:
    """The logon task that holds the distribution up (C12): no time limit, no overlap."""
    return watch.task_xml("tradecraft lab: hold the tradecraft-ci WSL distribution up so "
                          "the private-ci runners stay online (#929).",
                          watch.logon_trigger(user), interpreter, f'"{launcher}"',
                          working_dir, "PT0S")


def install(host: Host, state_dir: Path, *, prompt=None, sleep=time.sleep,
            schtasks=watch.schtasks, now=None) -> dict:
    """Bring the install to its settled state; a re-run over a complete one changes nothing."""
    prompt = prompt or (lambda: getpass.getpass(
        "Registration token from Settings > Actions > Runners (typed here only): "))
    steps: list[dict] = []
    record = watch.read_json(state_dir / "install.json", {})

    _, version = host.run(["wsl.exe", "--version"], check=False)
    if not re.search(r"WSL[^\n:]*:\s*2\.", version):
        raise SetupError("WSL 2 is required; `wsl --version` did not report it")

    current = read_wslconfig()
    merged, conflicts = merge_wslconfig(current)
    if conflicts:
        raise SetupError("%UserProfile%\\.wslconfig holds a setting you chose that the "
                         "runner's caps would change; decide it and re-run: "
                         + "; ".join(conflicts))
    wslconfig_changed = merged != (current or "")
    if wslconfig_changed:
        (profile() / ".wslconfig").write_text(merged, encoding="utf-8", newline="\n")
    steps.append({"step": "wslconfig", "changed": wslconfig_changed})

    installed = DISTRO in distributions(host)
    if not installed:
        host.run(["wsl.exe", "--install", IMAGE, "--name", DISTRO, "--no-launch"])
    steps.append({"step": "distribution", "changed": not installed})

    guest_digest = digest([HERE / src for src, _, _ in GUEST_FILES])
    base_needed = (not installed) or record.get("base_digest") != guest_digest
    if base_needed:
        for src, dest, mode in GUEST_FILES:
            host.guest("/bin/sh", "-c", f"mkdir -p {GUEST_LIB} && cat > {dest} && "
                       f"chown root:root {dest} && chmod {mode} {dest}",
                       stdin_bytes=(HERE / src).read_bytes())
        host.guest("/bin/bash", PROVISION, "base")
        record["base_digest"] = guest_digest
    steps.append({"step": "base", "changed": base_needed})

    canary = profile().joinpath(".tradecraft-lab", "private-ci", "canary.txt")
    canary_needed = not canary.exists()
    if canary_needed:
        canary.parent.mkdir(parents=True, exist_ok=True)
        canary.write_text(secrets.token_hex(16) + "\n", encoding="ascii")
    steps.append({"step": "canary", "changed": canary_needed})

    if wslconfig_changed or base_needed:
        others = [name for name in distributions(host) if name != DISTRO]
        if others:
            host.run(["wsl.exe", "--terminate", DISTRO], check=False)
            steps.append({"step": "restart", "changed": True,
                          "note": "the .wslconfig caps take effect at WSL's next full "
                                  "restart, because other distributions are installed"})
        else:
            host.run(["wsl.exe", "--shutdown"], check=False)
            steps.append({"step": "restart", "changed": True})
        sleep(8)

    token = None
    prompted = False
    states = instance_state(host)
    record.setdefault("instances", {})
    for n in INSTANCES:
        state = states.get(n, {})
        changed = False
        if not state.get("unpacked"):
            host.guest("/bin/bash", PROVISION, "unpack", str(n), RUNNER_VERSION, RUNNER_SHA256)
            changed = True
        if not instance_matches(n, state):
            if not instance_registered(n, state):
                if token is None:
                    token = prompt().strip()
                    prompted = True
                    if not token:
                        raise SetupError("no registration token was entered")
                host.guest("/bin/bash", PROVISION, "register", str(n), ORG_URL,
                           stdin_bytes=(token + "\n").encode("ascii"))
                record["instances"][str(n)] = {
                    "name": runner_name(n), "group": GROUP, "labels": [LABEL],
                    "no_default_labels": True, "request": registration_request(n),
                    "registered_at": watch.iso(now or watch.now_utc())}
            host.guest("/bin/bash", PROVISION, "service", str(n))
            changed = True
        steps.append({"step": f"instance {runner_name(n)}", "changed": changed})
    token = None

    bin_dir = state_dir / "bin"
    commit = tradecraft_commit(host)
    sources = {name: HERE / name for name in BIN_FILES}
    sources["winio.py"] = ROOT / "lib" / "winio.py"
    bin_changed = False
    for name, source in sources.items():
        target = bin_dir / name
        if not target.exists() or target.read_bytes() != source.read_bytes():
            bin_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            bin_changed = True
    repos = json.dumps(watch.product_repos(), indent=2) + "\n"
    if not (bin_dir / "repos.json").exists() or \
            (bin_dir / "repos.json").read_text(encoding="utf-8") != repos:
        (bin_dir / "repos.json").write_text(repos, encoding="utf-8", newline="\n")
        bin_changed = True
    watch.write_json_atomic(bin_dir / "stamp.json", {"tradecraft_commit": commit})
    steps.append({"step": "installed copy", "changed": bin_changed, "commit": commit})

    interpreter = watch.windowless_interpreter()
    user = watch.owner_account()
    tasks = {
        START_TASK: start_task_xml(interpreter, str(bin_dir / "keepalive.py"),
                                   str(bin_dir), user),
        watch.TASK_NAME: watch.watch_task_xml(interpreter, str(bin_dir / "watch.py"),
                                              str(bin_dir), user, now or watch.now_utc()),
    }
    record.setdefault("tasks", {})
    for name, xml in tasks.items():
        task_digest = hashlib.sha256(xml.encode("utf-8")).hexdigest()
        present = task_present(name, schtasks)
        if not present or record["tasks"].get(name) != task_digest:
            watch.register_task(name, xml, schtasks)
            record["tasks"][name] = task_digest
            steps.append({"step": f"task {name}", "changed": True})
        else:
            steps.append({"step": f"task {name}", "changed": False})

    if not keepalive_running(host):
        schtasks(["/Run", "/TN", START_TASK])
        steps.append({"step": "keepalive", "changed": True})
    else:
        steps.append({"step": "keepalive", "changed": False})

    record["tradecraft_commit"] = commit
    watch.write_json_atomic(state_dir / "install.json", record)
    result = verify(host)
    return {"command": "install", "ok": result["ok"], "steps": steps,
            "prompted_for_token": prompted,
            "verify": result}


def instance_registered(n: int, state: dict) -> bool:
    """A `.runner` for this instance in the private-ci group: registration is done."""
    record = state.get("runner")
    return (str(_field(record, "agentName") or "") == runner_name(n)
            and str(_field(record, "poolName") or "") == GROUP)


def task_present(name: str, schtasks=watch.schtasks) -> bool:
    try:
        schtasks(["/Query", "/TN", name])
        return True
    except watch.WatchError:
        return False


def keepalive_running(host: Host) -> bool:
    """A Windows wsl.exe whose command line holds the keepalive's arguments (C17)."""
    _, text = host.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name='wsl.exe'\" | "
                        "ForEach-Object { $_.CommandLine }"], check=False)
    return any(KEEPALIVE_ARGS in line for line in text.splitlines())


# ---------------------------------------------------------------- probe


def windows_process_running(host: Host, image: str) -> bool:
    """Whether a Windows process of this image name runs; nothing else is read (C18)."""
    _, text = host.run(["tasklist.exe", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
                       check=False)
    return image.lower() in text.lower()


def guest_workers(host: Host) -> int:
    _, text = host.guest("/bin/bash", PROVISION, "workers", check=False)
    try:
        return int(text.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return 1


def probe_files(user: str, port: int, commit: str) -> dict[str, bytes]:
    template = (HERE / "probe" / "private-ci-probe.yml").read_text(encoding="utf-8")
    workflow = (template.replace("__WIN_USER__", user).replace("__LOCAL_PORT__", str(port))
                .replace("__PLAYWRIGHT__", PLAYWRIGHT_VERSION)
                .replace("__TRADECRAFT__", commit))
    return {PROBE_PATH: workflow.encode("utf-8"),
            "isolation_check.py": (HERE / "guest" / "isolation_check.py").read_bytes(),
            "smoke.sh": (HERE / "probe" / "smoke.sh").read_bytes()}


def push_probe(github: watch.GitHub, files: dict[str, bytes], commit: str) -> str:
    """A parentless commit holding only the probe files, moved onto the probe branch."""
    tree = []
    for path, data in files.items():
        blob = github.send("POST", f"repos/{PROBE_REPO}/git/blobs",
                           {"content": base64.b64encode(data).decode("ascii"),
                            "encoding": "base64"})
        tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    tree_sha = github.send("POST", f"repos/{PROBE_REPO}/git/trees", {"tree": tree})["sha"]
    made = github.send("POST", f"repos/{PROBE_REPO}/git/commits",
                       {"message": f"private-ci probe at tradecraft {commit} (#929)",
                        "tree": tree_sha, "parents": []})
    try:
        github.get(f"repos/{PROBE_REPO}/git/ref/heads/{PROBE_BRANCH}")
        github.send("PATCH", f"repos/{PROBE_REPO}/git/refs/heads/{PROBE_BRANCH}",
                    {"sha": made["sha"], "force": True})
    except watch.WatchError:
        github.send("POST", f"repos/{PROBE_REPO}/git/refs",
                    {"ref": f"refs/heads/{PROBE_BRANCH}", "sha": made["sha"]})
    return made["sha"]


def outside_in(host: Host) -> list[str]:
    """C17: the distribution is Running and the keepalive alive, read without entering."""
    failures = []
    state = distributions(host).get(DISTRO)
    if state != "Running":
        failures.append(f"wsl -l -v shows {DISTRO} as {state or 'absent'}, not Running")
    if not keepalive_running(host):
        failures.append("no keepalive wsl.exe holds the distribution")
    return failures


def judge_jobs(jobs: list[dict], timed: bool) -> list[str]:
    failures = []
    local = [j for j in jobs if j["name"].startswith("local")]
    names = {j.get("runner_name") or "" for j in local}
    if len(local) != 2 or any(j.get("conclusion") != "success" for j in local):
        failures.append("local: both jobs must succeed")
    if len(names) != 2 or not all(n.startswith("blaz-top-wsl-") for n in names):
        failures.append(f"local: ran on {sorted(names)}, not two distinct blaz-top-wsl-*")
    smoke = [j for j in jobs if j["name"] == "smoke"]
    if not smoke or smoke[0].get("conclusion") != "success":
        failures.append("smoke: did not succeed")
    if timed:
        for job in local:
            created = watch.parse_time(job.get("created_at"))
            started = watch.parse_time(job.get("started_at"))
            if not created or not started or \
                    (started - created).total_seconds() > START_WITHIN_SECONDS:
                failures.append(f"{job['name']}: did not start within "
                                f"{START_WITHIN_SECONDS} s of being queued")
    return failures


def probe(host: Host, github: watch.GitHub, *, require_idle: int | None = None,
          after_restart: bool = False, state_dir: Path | None = None,
          sleep=time.sleep, monotonic=time.monotonic) -> dict:
    """Push the probe, judge its run, and print everything the holder records (§3.6)."""
    _, dirty = host.run(["git", "-C", str(ROOT), "status", "--porcelain"])
    if dirty.strip():
        raise SetupError("the tradecraft working tree is dirty; commit or remove the changes "
                         "so the probe's commit names what ran")
    commit = tradecraft_commit(host)
    summary: dict = {"command": "probe", "tradecraft_commit": commit, "failures": []}
    timed = bool(require_idle) or after_restart
    if timed:
        failures = outside_in(host)
        summary["outside_in"] = {"failures": failures}
        if failures:
            summary["failures"] = failures
            summary["ok"] = False
            return summary
        states = instance_state(host)
        summary["units"] = states
        if require_idle:
            now_epoch = max(int(s.get("now_epoch", 0) or 0) for s in states.values()) or \
                int(time.time())
            limit = require_idle * 60
            for n, state in states.items():
                enter = int(state.get("active_enter_epoch") or 0)
                last = int(state.get("last_worker_epoch") or 0)
                if not enter or now_epoch - enter < limit:
                    summary["failures"].append(f"{runner_name(n)}: unit started less than "
                                               f"{require_idle} min ago")
                if last and now_epoch - last < limit:
                    summary["failures"].append(f"{runner_name(n)}: ran a job in the last "
                                               f"{require_idle} min")
    summary["registration"] = watch.read_json((state_dir or default_state_dir()) / "install.json",
                                              {}).get("instances", {})
    with Listener() as listener:
        sha = push_probe(github, probe_files(win_user(), listener.port, commit), commit)
        summary["probe_commit"] = sha
        run = None
        deadline = monotonic() + JOB_WAIT_SECONDS
        while run is None and monotonic() < deadline:
            found = github.get(f"repos/{PROBE_REPO}/actions/runs?head_sha={sha}&event=push")
            run = (found.get("workflow_runs") or [None])[0]
            if run is None:
                sleep(15)
        if run is None:
            raise SetupError("the probe's run never appeared")
        summary["run_url"] = run.get("html_url")
        jobs: list[dict] = []
        while monotonic() < deadline:
            jobs = github.jobs(PROBE_REPO, run["id"], "latest")
            done = [j for j in jobs if (j["name"].startswith("local") or j["name"] == "smoke")
                    and j.get("status") == "completed"]
            if len(done) == 3:
                break
            sleep(15)
        hold = 0
        listener_up = True
        hold_start = monotonic()
        while hold < HOLD_SECONDS and monotonic() - hold_start < HOLD_DEADLINE_SECONDS:
            busy = (windows_process_running(host, "Runner.Worker.exe")
                    or guest_workers(host) > 0)
            listener_up = listener_up and windows_process_running(host, "Runner.Listener.exe")
            hold = 0 if busy else hold + SAMPLE_SECONDS
            sleep(SAMPLE_SECONDS)
        jobs = github.jobs(PROBE_REPO, run["id"], "latest")
        labels = {j["name"]: j.get("status") for j in jobs if j["name"].startswith("labels")}
        github.send("POST", f"repos/{PROBE_REPO}/actions/runs/{run['id']}/cancel")
        accepted = list(listener.accepted)
    checks = {}
    for job in jobs:
        if job["name"].startswith("local") and job.get("status") == "completed":
            try:
                checks[job["name"]] = parse_check(github.get_text(
                    f"repos/{PROBE_REPO}/actions/jobs/{job['id']}/logs"))
            except watch.WatchError as exc:
                checks[job["name"]] = {"ok": False, "failed": [f"log unreadable: {exc}"]}
    summary.update({
        "jobs": [{"name": j["name"], "runner": j.get("runner_name"), "status": j.get("status"),
                  "conclusion": j.get("conclusion")} for j in jobs],
        "checks": checks, "listener_accepted": accepted,
        "hold": {"all_idle_seconds": hold, "completed": hold >= HOLD_SECONDS,
                 "windows_listener_running": listener_up},
        "label_jobs_at_cancel": labels,
    })
    failures = summary["failures"] + judge_jobs(jobs, timed)
    for name, report in checks.items():
        if not report.get("ok"):
            failures.append(f"{name}: check failed {report.get('failed')}")
        settings = next((p for p in report.get("probes", []) if p["probe"] == "settings"), None)
        detail = (settings or {}).get("detail", {})
        if detail.get("nproc") != 8:
            failures.append(f"{name}: nproc {detail.get('nproc')}, not 8")
        if not detail.get("mem_total_kib") or detail["mem_total_kib"] > 12 * 1024 * 1024:
            failures.append(f"{name}: MemTotal {detail.get('mem_total_kib')} KiB over 12 GiB")
    if accepted:
        failures.append(f"local-services: the Windows listener accepted {accepted}")
    if hold < HOLD_SECONDS:
        failures.append("hold: inconclusive, the runners were never idle for 5 minutes")
    if not listener_up:
        failures.append("hold: the Windows runner's listener was not running throughout")
    if len(labels) != 4 or any(state != "queued" for state in labels.values()):
        failures.append(f"labels: a label job was placed or missing {labels}")
    summary["failures"] = failures
    summary["ok"] = not failures
    return summary


# ---------------------------------------------------------------- status and uninstall


def status(host: Host, state_dir: Path, schtasks=watch.schtasks) -> dict:
    return {"command": "status", "install": watch.read_json(state_dir / "install.json", None),
            "distributions": distributions(host),
            "tasks": {name: task_present(name, schtasks)
                      for name in (START_TASK, watch.TASK_NAME)},
            "keepalive": keepalive_running(host)}


def uninstall(host: Host, *, unregister_distribution: bool, schtasks=watch.schtasks) -> dict:
    removed = {}
    for name in (START_TASK, watch.TASK_NAME):
        removed[name] = task_present(name, schtasks)
        if removed[name]:
            schtasks(["/Delete", "/TN", name, "/F"])
    if unregister_distribution:
        host.run(["wsl.exe", "--unregister", DISTRO])
    return {"command": "uninstall", "tasks_removed": removed,
            "distribution_unregistered": unregister_distribution,
            "yours": ["remove blaz-top-wsl-1 and blaz-top-wsl-2 under Settings > Actions > "
                      "Runners", "delete the private-ci runner group if nothing else uses it",
                      "remove processors, memory and guiApplications from .wslconfig if you "
                      "want WSL's defaults back"]}


# ---------------------------------------------------------------- command line


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install, verify and probe the private-ci Linux runner (#929).")
    parser.add_argument("--state-dir", help="local state (default ~/.tradecraft-lab/private-ci)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("install", help="re-runnable install, ending in verify")
    sub.add_parser("verify", help="read back every setting and run row 1's check")
    probe_parser = sub.add_parser("probe", help="push the probe workflow and judge its run")
    when = probe_parser.add_mutually_exclusive_group()
    when.add_argument("--require-idle", type=int, metavar="MINUTES")
    when.add_argument("--after-restart", action="store_true")
    sub.add_parser("status", help="what is installed")
    remove = sub.add_parser("uninstall", help="remove the tasks")
    remove.add_argument("--unregister-distribution", action="store_true",
                        help="also delete the tradecraft-ci distribution and everything in it")
    return parser


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    args = build_parser().parse_args(argv)
    state_dir = Path(args.state_dir) if args.state_dir else default_state_dir()
    host = Host()
    try:
        if args.command == "install":
            value = install(host, state_dir)
        elif args.command == "verify":
            value = verify(host)
        elif args.command == "probe":
            value = probe(host, watch.GitHub(), require_idle=args.require_idle,
                          after_restart=args.after_restart, state_dir=state_dir)
        elif args.command == "status":
            value = status(host, state_dir)
        else:
            value = uninstall(host, unregister_distribution=args.unregister_distribution)
    except (SetupError, watch.WatchError, OSError, ValueError, KeyError) as exc:
        watch.emit({"command": args.command, "ok": False, "error": str(exc)})
        return 1
    watch.emit({"ok": value.get("ok", True), **value})
    return 0 if value.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())

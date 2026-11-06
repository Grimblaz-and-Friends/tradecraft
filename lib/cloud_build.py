"""The Claude implementer as a cloud session for a set-up repository.

A set-up repository's Claude launches (artifact, build, repairs) fire that
repository's routine, wait for the run's report branch, and read its report,
usage and checks into the same bundle a local launch writes. Nothing here falls
back to a local builder. Design: lib/DESIGN.md#the-cloud-route
"""
from __future__ import annotations

import base64
import importlib.util
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

import dispatch_record as records

RECORD_SCHEMA = 1
DEFAULT_PIN_BRANCH = "cloud-practice"
# A routine run may push to `claude/` branches without being told; report branches live there.
REPORT_PREFIX = "claude/tradecraft-report-"


def _load_hook():
    # The hook runs alone in the cloud with no lib on its path, and it writes the
    # report branch's format, so the launcher reads the shared constants from it.
    path = Path(__file__).resolve().parents[1] / "hooks" / "cloud.py"
    spec = importlib.util.spec_from_file_location("tradecraft_cloud_hook", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_HOOK = _load_hook()
CLOUD_DIR = _HOOK.PREFIX
HEADER = _HOOK.HEADER
FIGURES = _HOOK.FIGURES
CLOUD_SESSION = re.compile(r"cse_[A-Za-z0-9]+\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
# A run whose transcript names no effort can't be shown to have run at the profile.
NO_EFFORT_LABEL = "none recorded: the transcript names no effort"
FIRE_URL = "https://api.anthropic.com/v1/claude_code/routines/{routine}/fire"
FIRE_HEADERS = {"anthropic-beta": "experimental-cc-routine-2026-04-01",
                "anthropic-version": "2023-06-01"}
POLL_SECONDS = 30
COMMENT_LIMIT = 60_000
FIRE_TEXT_LIMIT = 65_536
COMPARISON_REASON = ("not run: a cloud builder runs on a remote machine and cannot reach "
                     "this one")
INSTRUCTIONS_APPLIED = ("product CLAUDE.md/AGENTS.md from the cloned repository; no repository's "
                        "committed hooks or permission rules apply, because the session starts "
                        "above its clones")
PRACTICE_OWN_REFUSAL = (
    "refused: the practice's own repository is not set up for cloud builds; its product and "
    "practice clones would share /home/user/tradecraft and its committed guard would govern a "
    "single-source build, which is untested")

# The saved prompt every set-up routine carries; setup embeds and verifies it.
ROUTINE_PROMPT = """You are a tradecraft cloud implementer run.

Act only when this run's message carries a `TRADECRAFT-CLOUD-RUN v1` payload. Otherwise reply "no payload; nothing done" and stop.

With a payload, in this order:
1. First run `python3 /home/user/{practice_name}/hooks/cloud.py check --expect <practice-commit> --report-branch <report-branch> --repository <repository>`, with the payload's values. If it fails, stop: do nothing else.
2. In the clone of <repository>, fetch <report-branch> and read the file the payload names as `task-file` on that branch. That file is your task.
3. Check out what `checkout` names: the branch, or the commit (detached) for an artifact.
4. Do the task.
5. Write two files and push them to <report-branch> together, in one commit whose message ends `[skip ci]`:
   - `tradecraft-cloud/report.md`: your whole final return and nothing else, exactly as a local return of the same stage would be (an artifact draft opens with its quoted affirmed brief);
   - `tradecraft-cloud/instructions.md`: the list of instruction files (CLAUDE.md, AGENTS.md and their imports) this session loaded, one path per line.

Never comment on the issue, never message another session, and never push any branch other than the change branch and <report-branch>.
"""


class CloudError(RuntimeError):
    """A cloud launch that cannot proceed; it is recorded and starts nothing local."""


class CloudRefusal(CloudError):
    """A refusal named before anything was fired."""


# ---- the machine-local record ---------------------------------------------

def record_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".tradecraft" / "cloud-builds.json"


def repository_of(work: str) -> str:
    match = re.fullmatch(r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([1-9][0-9]*)", work or "")
    if match is None:
        raise CloudError(f"work must be OWNER/REPO#N: {work!r}")
    return match.group(1)


def practice_name(repository: str) -> str:
    return repository.split("/")[-1]


def is_practice_repository(repository: str, practice: str) -> bool:
    """The practice itself, or any repository whose clone folder would collide with it."""
    return (repository.lower() == practice.lower()
            or practice_name(repository).lower() == practice_name(practice).lower())


def read_record(path: Path) -> dict | None:
    """The parsed switch, or None when absent; a broken switch refuses rather than meaning local."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise CloudRefusal(f"cloud record {path} is unreadable: {exc}") from exc
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise CloudRefusal(f"cloud record {path} is malformed: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != RECORD_SCHEMA:
        raise CloudRefusal(f"cloud record {path} has an unknown schema")
    practice = value.get("practice")
    if (not isinstance(practice, dict) or not isinstance(practice.get("repository"), str)
            or "/" not in practice["repository"]):
        raise CloudRefusal(f"cloud record {path} names no practice repository")
    practice.setdefault("branch", DEFAULT_PIN_BRANCH)
    if not isinstance(practice["branch"], str) or not practice["branch"]:
        raise CloudRefusal(f"cloud record {path} has an invalid practice branch")
    repositories = value.get("repositories")
    if not isinstance(repositories, dict):
        raise CloudRefusal(f"cloud record {path} has no repositories object")
    for name, entry in repositories.items():
        if is_practice_repository(name, practice["repository"]):
            raise CloudRefusal(f"cloud record {path} names {name}: {PRACTICE_OWN_REFUSAL}")
        if not isinstance(entry, dict):
            raise CloudRefusal(f"cloud record {path} entry {name} is not an object")
        for key in ("routine_id", "token_file", "setup_record", "set_up_at"):
            if not isinstance(entry.get(key), str) or not entry[key]:
                raise CloudRefusal(f"cloud record {path} entry {name} is missing {key}")
    return value


def route_for(work: str, path: Path | None = None) -> tuple[dict | None, str]:
    """The record entry routing this work to the cloud, or None for the local route."""
    path = path or record_path()
    record = read_record(path)
    if record is None:
        return None, "no entry: absent record " + str(path)
    try:
        repository = repository_of(work)
    except CloudError:
        return None, f"no entry: work {work!r} names no repository"
    entry = record["repositories"].get(repository)
    if entry is None:
        return None, f"no entry: {repository} not in {path}"
    return {"repository": repository, "practice": dict(record["practice"]), **entry}, (
        f"record {path} entry {repository}")


# ---- the token ------------------------------------------------------------

def read_token(path: str | Path) -> str:
    """One line of printable ASCII; nothing from the file is ever echoed."""
    location = Path(path)
    try:
        raw = location.read_bytes()
    except OSError as exc:
        name = type(exc).__name__ if exc.errno is None else _errno_name(exc.errno)
        raise CloudRefusal(f"cloud launch refused: token file {location} is missing or unreadable ({name})") from None
    text = raw.strip(b"\r\n")
    if not text:
        raise CloudRefusal(f"cloud launch refused: token file {location} is missing or unreadable (empty)")
    if b"\n" in text or b"\r" in text or any(byte < 0x21 or byte > 0x7e for byte in text):
        raise CloudRefusal(f"cloud launch refused: token file {location} is missing or unreadable "
                           "(not one line of printable ASCII)")
    return text.decode("ascii")


def _errno_name(number: int) -> str:
    import errno
    return errno.errorcode.get(number, f"errno {number}")


# ---- the practice version ---------------------------------------------------

def plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def launcher_version(root: Path) -> tuple[str, str]:
    """The version and name in the plugin.json the launcher runs from."""
    try:
        value = json.loads((root / ".claude-plugin" / "plugin.json").read_text("utf-8"))
        return value["version"], value["name"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CloudRefusal(f"cannot read the launcher's plugin.json under {root}: {exc}") from exc


def install_record_path(env: dict | None = None) -> Path:
    env = os.environ if env is None else env
    config = Path(env.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return Path(env.get("CLAUDE_CODE_PLUGIN_CACHE_DIR") or config / "plugins") / "installed_plugins.json"


def _version_key(value: str, where: str) -> tuple[int, ...]:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(\.[0-9]+)*", value):
        raise CloudRefusal(f"version {value!r} in {where} is not numeric")
    return tuple(int(part) for part in value.split("."))


def installed_practice(root: Path, path: Path, *, refuse_older: bool = True) -> dict[str, str]:
    """The install record's commit and version for this launcher's plugin."""
    version, name = launcher_version(root)
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise CloudRefusal(f"plugin install record {path}: {exc}") from exc
    plugins = value.get("plugins") if isinstance(value, dict) else None
    if not isinstance(plugins, dict):
        raise CloudRefusal(f"plugin install record {path} has no plugins object")
    candidates = [entry for key, entries in plugins.items() if key.split("@")[0] == name
                  and isinstance(entries, list) for entry in entries if isinstance(entry, dict)]
    if not candidates:
        raise CloudRefusal(f"plugin install record {path} has no {name} entry")
    own = [entry for entry in candidates if isinstance(entry.get("installPath"), str)
           and _same_path(entry["installPath"], root)]
    if own:
        chosen = own[0]
    else:
        users = [entry for entry in candidates if entry.get("scope") == "user"]
        if len(users) != 1:
            raise CloudRefusal(f"plugin install record {path} has {len(users)} user-scope {name} entries; "
                               "expected exactly one")
        chosen = users[0]
    commit = chosen.get("gitCommitSha")
    if not isinstance(commit, str) or SHA.fullmatch(commit) is None:
        raise CloudRefusal(f"plugin install record {path}: gitCommitSha is not 40 hex characters")
    installed = chosen.get("version")
    if refuse_older and _version_key(version, "the launcher's plugin.json") < _version_key(installed, str(path)):
        raise CloudRefusal(
            f"this session's practice {version} is older than the installed {installed}; ask the owner "
            "to reload this session (/reload-plugins or restart), then launch again")
    return {"commit": commit, "launcher_version": version, "installed_version": installed,
            "install_record": str(path)}


def _same_path(a: str, b: Path) -> bool:
    try:
        return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(b.resolve()))
    except OSError:
        return False


# ---- names and the fire header ----------------------------------------------

def report_branch(issue: int | str, stage: str, dispatch_id: str) -> str:
    return f"{REPORT_PREFIX}{issue}-{stage}-{dispatch_id[:12]}"


def header(*, work: str, stage: str, dispatch_id: str, checkout: str, practice_commit: str,
           branch: str) -> str:
    return "\n".join((
        HEADER, f"work: {work}", f"stage: {stage}", f"dispatch: {dispatch_id}",
        f"repository: {repository_of(work)}", f"checkout: {checkout}",
        f"practice-commit: {practice_commit}", f"report-branch: {branch}",
        f"task-file: {CLOUD_DIR}dispatch.md", ""))


# ---- what the report branch says -----------------------------------------------

def git_blob_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(content) + content).hexdigest()


def finished(files: dict[str, bytes | None]) -> bool:
    """The finish signal: a report and a usage record naming that report's blob."""
    report, usage = files.get("report.md"), files.get("usage.json")
    if report is None or usage is None:
        return False
    try:
        value = json.loads(usage)
    except ValueError:
        return False
    return isinstance(value, dict) and value.get("report_blob") == git_blob_sha(report)


def builder_profile(stage: str = "build") -> tuple[str, str]:
    """The Claude model and effort the local launch defaults to, which the routine must match."""
    import dispatch_implementer  # Deferred: it imports this module.
    role = "artifact_author" if stage == "artifact" else "implementer"
    return dispatch_implementer.PROFILES[role]["claude"]


def cloud_profile(usage: dict, profile: tuple[str, str] | None = None) -> dict[str, object]:
    """The main session's model and effort, against the builder profile."""
    expected_model, expected_effort = profile or builder_profile()
    seen = usage.get("profile") if isinstance(usage.get("profile"), dict) else {}
    models = [value for value in seen.get("models") or [] if isinstance(value, str)]
    efforts = [value for value in seen.get("efforts") or [] if isinstance(value, str)]
    reasons = []
    if not models:
        reasons.append("no main-session model recorded")
    elif models != [expected_model]:
        reasons.append("main-session models " + ", ".join(models) + f" differ from {expected_model}")
    if not efforts:
        effort = NO_EFFORT_LABEL
        reasons.append(NO_EFFORT_LABEL)
    elif efforts == [expected_effort]:
        effort = expected_effort
    else:
        effort = efforts[0] if len(efforts) == 1 else efforts
        reasons.append("main-session efforts " + ", ".join(efforts) + f" differ from {expected_effort}")
    mode = usage.get("permission_mode") if isinstance(usage.get("permission_mode"), dict) else {}
    return {"model": models, "effort": effort, "profile": f"{expected_model}/{expected_effort}",
            "off_profile": bool(reasons), "reason": "; ".join(reasons),
            "permission_mode": mode.get("values") or ["unknown"]}




def ledger_check(usage: dict, previous: list[dict] | None,
                 recorded_deltas: list[dict] | None = None) -> dict[str, object]:
    """Checks (a)–(e) of the hook's reading, without the transcript, which the launcher can't read."""
    faults = []
    ledger = usage.get("ledger") if isinstance(usage.get("ledger"), list) else []
    totals = usage.get("totals_by_model") if isinstance(usage.get("totals_by_model"), dict) else {}
    sums: dict[str, dict[str, int]] = {}
    ids = set()
    for row in ledger:
        if not isinstance(row, dict):
            faults.append("(a) a ledger row is not an object")
            continue
        if row.get("id") in ids:
            faults.append(f"(b) ledger id {row.get('id')} repeats")
        ids.add(row.get("id"))
        model_sums = sums.setdefault(str(row.get("model")), {})
        for key in FIGURES:
            if key in row:
                model_sums[key] = model_sums.get(key, 0) + row[key]
    if sums != {model: {key: value for key, value in figures.items()}
                for model, figures in totals.items() if isinstance(figures, dict)}:
        faults.append("(a) ledger sums differ from totals_by_model")
    if previous is not None:
        current = {row.get("id"): row for row in ledger if isinstance(row, dict)}
        for row in previous:
            if current.get(row.get("id")) != row:
                faults.append(f"(c) earlier ledger row {row.get('id')} is missing or changed")
                break
    if recorded_deltas is not None:
        summed: dict[str, dict[str, int]] = {}
        for delta in recorded_deltas:
            for model, figures in delta.items():
                for key, value in figures.items():
                    summed.setdefault(model, {})[key] = summed.setdefault(model, {}).get(key, 0) + value
        if _nonzero(summed) != _nonzero(totals):
            faults.append("(d) recorded deltas do not sum to the running total")
    unread = usage.get("files_unread") or []
    read = {row.get("file") for row in usage.get("files_read") or [] if isinstance(row, dict)}
    missing = [name for name in usage.get("files_present") or [] if name not in read]
    if unread or missing:
        faults.append("(e) listed files went unread: "
                      + ", ".join([str(row.get("file") if isinstance(row, dict) else row) for row in unread]
                                  + [name for name in missing if name not in
                                     {row.get("file") for row in unread if isinstance(row, dict)}]))
    return {"ok": not faults, "faults": faults}


def _nonzero(totals: dict) -> dict:
    return {model: {key: value for key, value in figures.items() if value}
            for model, figures in totals.items() if isinstance(figures, dict)
            and any(figures.values())}


def delta(current: dict, previous: dict | None) -> dict[str, dict[str, int]]:
    """This attempt's share of the session's running total."""
    previous = previous or {}
    result = {}
    for model, figures in current.items():
        before = previous.get(model) or {}
        result[model] = {key: value - before.get(key, 0) for key, value in figures.items()}
    return result


def skip_ci_check(commits: list[dict]) -> dict[str, object]:
    """Every report-branch commit after the dispatch commit carries ``[skip ci]``.

    A repository whose CI runs on every push would otherwise spend its runner on
    each report commit, so a commit without the marker is held for the holder.
    """
    missing = [commit["sha"] for commit in commits if "[skip ci]" not in commit.get("message", "")]
    return {"ok": not missing, "commits_without_marker": missing}


def change_branch_check(tip_at_fire: str | None, tip_after: str | None, commits: list[str],
                        status: str | None, *, repair: bool) -> dict[str, object]:
    """The run worked on the change's branch; a repair's range is recorded only."""
    value = {"tip_at_fire": tip_at_fire, "tip_after": tip_after, "commits": commits,
             "compare_status": status}
    if repair:
        return {**value, "ok": True, "checked": False,
                "reason": "a disposition can rightly make no commit"}
    faults = []
    if tip_after is None or tip_after == tip_at_fire:
        faults.append("the change branch's tip is unchanged")
    if not commits:
        faults.append("no commit lies in tip_at_fire..tip_after")
    if status not in {"ahead", "identical"} or (status == "identical" and tip_after != tip_at_fire):
        faults.append("tip_after does not descend from tip_at_fire")
    return {**value, "ok": not faults, "checked": True, "faults": faults}


def practice_record_check(check: dict | None, usage: dict) -> dict[str, object]:
    """The usage record copies a recorded practice check that agrees with it."""
    copied = usage.get("practice_check")
    if check is None:
        return {"ok": False, "reason": "no practice-check.json on the report branch"}
    if not isinstance(copied, dict) or copied.get("ok") is None:
        return {"ok": False, "reason": "usage.json carries no recorded practice check"}
    if copied != check:
        return {"ok": False, "reason": "usage.json's practice_check differs from practice-check.json"}
    return {"ok": bool(check.get("ok")), "reason": "" if check.get("ok") else "practice mismatch"}


# ---- transport ------------------------------------------------------------

class Transport:
    """GitHub, the fire endpoint, the CLI and git; tests substitute a fake."""

    def github(self, method: str, path: str, body: object | None = None) -> tuple[int, object]:
        command = ["gh", "api", "-i", "--method", method, path]
        data = None
        if body is not None:
            command += ["--input", "-"]
            data = json.dumps(body).encode("utf-8")
        result = subprocess.run(command, input=data if data is not None else b"", capture_output=True,
                                timeout=120)
        raw = result.stdout.replace(b"\r\n", b"\n")
        head, _, payload = raw.partition(b"\n\n")
        match = re.match(rb"HTTP/[0-9.]+ ([0-9]{3})", head)
        if match is None:
            raise CloudError(f"gh api {method} {path} failed: "
                             + result.stderr.decode("utf-8", "replace").strip()[:300])
        try:
            value = json.loads(payload) if payload.strip() else None
        except ValueError:
            value = payload.decode("utf-8", "replace")
        return int(match.group(1)), value

    def fire(self, routine: str, token: str, text: str) -> tuple[int, str]:
        request = urllib.request.Request(
            FIRE_URL.format(routine=routine), method="POST",
            data=json.dumps({"text": text}).encode("utf-8"),
            headers={**FIRE_HEADERS, "Authorization": f"Bearer {token}",
                     "content-type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    def cli(self, argv: list[str], env: dict) -> tuple[int, bytes]:
        try:
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, env=env, timeout=120)
        except FileNotFoundError:
            return 127, b""
        return result.returncode, result.stdout

    def git(self, root: Path, *arguments: str) -> tuple[int, str]:
        result = subprocess.run(["git", "-C", str(root), *arguments], stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=300)
        return result.returncode, (result.stdout or result.stderr).decode("utf-8", "replace").strip()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def _ok(status: int, value: object, what: str) -> object:
    if status // 100 != 2:
        raise CloudError(f"{what}: HTTP {status} {str(value)[:300]}")
    return value


# ---- GitHub steps ---------------------------------------------------------

def compare_pin(transport: Transport, practice: dict, installed: str) -> str:
    """Fast-forward the shared pin to the installed commit, never back."""
    repo, branch = practice["repository"], practice["branch"]
    status, ref = transport.github("GET", f"repos/{repo}/git/ref/heads/{branch}")
    pin = _ok(status, ref, f"read pin {repo}@{branch}")["object"]["sha"]
    status, value = transport.github("GET", f"repos/{repo}/compare/{pin}...{installed}")
    if status == 404:
        raise CloudRefusal(f"installed commit {installed} is absent from {repo}; keep the fork level "
                           "with the release you install, then launch again")
    state = _ok(status, value, "compare pin")["status"]
    if state == "identical":
        return "unchanged"
    if state == "behind":
        raise CloudRefusal(
            f"this session's practice {installed} is older than {pin} on {repo}@{branch}; ask the owner "
            "to reload this session (/reload-plugins or restart), then launch again; if the installed "
            "plugin itself is older, update it first")
    if state != "ahead":
        raise CloudRefusal(f"installed commit {installed} has diverged from {pin} on {repo}@{branch}")
    status, value = transport.github("PATCH", f"repos/{repo}/git/refs/heads/{branch}",
                                     {"sha": installed, "force": False})
    _ok(status, value, "fast-forward pin")
    return f"fast-forwarded {pin}..{installed}"


def remote_tip(transport: Transport, repo: str, branch: str) -> str:
    status, value = transport.github("GET", f"repos/{repo}/git/ref/heads/{branch}")
    return _ok(status, value, f"read {repo}@{branch}")["object"]["sha"]


def create_report_branch(transport: Transport, repo: str, branch: str, base: str,
                         dispatch: bytes, dispatch_id: str) -> str:
    status, value = transport.github("GET", f"repos/{repo}/git/commits/{base}")
    tree = _ok(status, value, f"read commit {base}")["tree"]["sha"]
    status, value = transport.github("POST", f"repos/{repo}/git/blobs", {
        "content": base64.b64encode(dispatch).decode("ascii"), "encoding": "base64"})
    blob = _ok(status, value, "create dispatch blob")["sha"]
    status, value = transport.github("POST", f"repos/{repo}/git/trees", {
        "base_tree": tree, "tree": [{"path": CLOUD_DIR + "dispatch.md", "mode": "100644",
                                      "type": "blob", "sha": blob}]})
    new_tree = _ok(status, value, "create dispatch tree")["sha"]
    status, value = transport.github("POST", f"repos/{repo}/git/commits", {
        "message": f"tradecraft cloud dispatch {dispatch_id} [skip ci]", "tree": new_tree,
        "parents": [base]})
    commit = _ok(status, value, "create dispatch commit")["sha"]
    status, value = transport.github("POST", f"repos/{repo}/git/refs",
                                     {"ref": f"refs/heads/{branch}", "sha": commit})
    _ok(status, value, f"create report branch {branch}")
    return commit


def read_branch_file(transport: Transport, repo: str, branch: str, name: str) -> bytes | None:
    status, value = transport.github("GET", f"repos/{repo}/contents/{CLOUD_DIR}{name}?ref={branch}")
    if status == 404:
        return None
    value = _ok(status, value, f"read {name}")
    if isinstance(value, dict) and value.get("encoding") == "base64":
        return base64.b64decode(value.get("content") or "")
    if isinstance(value, dict) and value.get("sha"):
        status, blob = transport.github("GET", f"repos/{repo}/git/blobs/{value['sha']}")
        return base64.b64decode(_ok(status, blob, f"read blob {name}")["content"])
    raise CloudError(f"unexpected contents response for {name}")


def branch_commits(transport: Transport, repo: str, base: str, tip: str) -> list[dict]:
    status, value = transport.github("GET", f"repos/{repo}/compare/{base}...{tip}")
    value = _ok(status, value, "list report-branch commits")
    return [{"sha": row["sha"], "message": row["commit"]["message"]} for row in value.get("commits") or []]


def delete_report_branch(transport: Transport, request: dict) -> None:
    """Delete only the name composed from this request's own dispatch id."""
    cloud = request.get("cloud") or {}
    expected = report_branch(cloud.get("issue"), request.get("stage"), request.get("dispatch_id") or "")
    name = cloud.get("report_branch")
    if name != expected or not str(name).startswith(REPORT_PREFIX):
        raise CloudError(f"refusing to delete {name!r}: not the report branch named for this dispatch")
    status, value = transport.github("DELETE", f"repos/{repository_of(request['work'])}/git/refs/heads/{name}")
    _ok(status, value, f"delete {name}")


def post_report(transport: Transport, work: str, stage: str, session_url: str, branch: str,
                tip: str, report: bytes) -> list[str]:
    repo = repository_of(work)
    issue = work.split("#")[1]
    text = report.decode("utf-8", "replace")
    first = f"Cloud {stage} report - session {session_url}, report branch {branch} at {tip}"
    parts = [text[index:index + COMMENT_LIMIT] for index in range(0, len(text), COMMENT_LIMIT)] or [""]
    urls = []
    for number, part in enumerate(parts, 1):
        label = first if len(parts) == 1 else f"{first} (part {number} of {len(parts)})"
        status, value = transport.github("POST", f"repos/{repo}/issues/{issue}/comments",
                                         {"body": label + "\n\n" + part})
        urls.append(_ok(status, value, "post report")["html_url"])
    return urls


# ---- the follow-up's session record ------------------------------------------

def session_attempts(record_root: Path, session: str) -> list[tuple[dict, dict]]:
    """Every recorded (request, run) for this cloud session, oldest first."""
    found = []
    for path in sorted(record_root.rglob("*.request.json")):
        try:
            request = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        cloud = request.get("cloud") if isinstance(request, dict) else None
        if not isinstance(cloud, dict) or cloud.get("session_id") != session:
            continue
        run_path = path.with_name(path.name[:-len(".request.json")] + ".run.json")
        try:
            run = json.loads(run_path.read_text("utf-8"))
        except (OSError, ValueError):
            run = {}
        found.append((request, run))
    found.sort(key=lambda pair: pair[0].get("launched_at") or "")
    return found


def loaded_commit(attempts: list[tuple[dict, dict]], session: str) -> tuple[dict, str]:
    """The commit the session loaded, from the attempt that started it."""
    starts = [pair for pair in attempts
              if (pair[0].get("requested") or {}).get("continuity") == "fresh"]
    if len(starts) != 1:
        raise CloudError(f"cloud session {session}: {len(starts)} starting attempts recorded; expected one")
    request, run = starts[0]
    commit = ((request.get("cloud") or {}).get("practice") or {}).get("commit")
    attempt = (run.get("attempts") or [{}])[0]
    checked = ((attempt.get("cloud") or {}).get("practice_check") or {}).get("commit")
    if not isinstance(commit, str) or SHA.fullmatch(commit) is None or checked != commit:
        raise CloudError(f"cloud session {session}: the starting attempt's practice commit is missing "
                         "or disagrees with its recorded practice check")
    return request, commit


def login_check(transport: Transport, env: dict) -> None:
    """A follow-up uses the owner's claude.ai login."""
    code, raw = transport.cli(["claude", "auth", "status", "--json"], env)
    method = None
    if code == 127:
        method = "no claude executable"
    else:
        try:
            method = json.loads(raw).get("authMethod")
        except (ValueError, AttributeError):
            match = re.search(rb"authMethod\W+([A-Za-z_.]+)", raw or b"")
            method = match.group(1).decode() if match else None
    if method != "claude.ai":
        raise CloudRefusal(f"cloud follow-up refused: no claude.ai login on this machine "
                           f"(authMethod: {method}); run claude /login")


def followup_env() -> dict:
    # With an OAuth token set the CLI authenticates by it, and the sessions service
    # refuses to continue a session; only the claude.ai login can send a follow-up.
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    return env


# ---- one cloud attempt -------------------------------------------------------

REPAIR_STAGES = frozenset({"review-disposition", "floor"})


def _usage_tokens(figures: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    """Per-model classes in the shape change_cost prices; a split cache write keeps its rates."""
    result = {}
    for model, values in figures.items():
        classes = {key: values.get(key, 0) for key in ("input", "output", "cache_read", "cache_creation")}
        for key in ("cache_write_5m", "cache_write_1h"):
            if key in values:
                classes[key] = values[key]
        result[model] = classes
    return result


def _previous_usage(attempts: list[tuple[dict, dict]], dispatch_id: str) -> tuple[dict | None, list[dict]]:
    """The session's latest recorded usage and every delta recorded before this attempt."""
    latest, deltas = None, []
    for request, run_record in attempts:
        if request.get("dispatch_id") == dispatch_id:
            continue
        for attempt in run_record.get("attempts") or []:
            cloud = attempt.get("cloud") if isinstance(attempt, dict) else None
            if isinstance(cloud, dict) and isinstance(cloud.get("usage"), dict):
                latest = cloud["usage"]
                if isinstance(cloud.get("delta"), dict):
                    deltas.append(cloud["delta"])
    return latest, deltas


def run(args, deadline, *, entry: dict | None, route_source: str, effective_prompt: bytes,
        prompt: bytes, context: bytes, artifact_brief: bytes, metadata: dict, composition: dict,
        settings_sources: dict, validate, transport: Transport | None = None,
        record_root: Path | None = None, plugin: Path | None = None,
        install_path: Path | None = None, preset_failure: str | None = None) -> int:
    """Fire (or follow up) one cloud attempt and record it like a local bundle."""
    import uuid
    from dispatch_lifecycle import GrowingRun
    import launch_bound

    transport = transport or Transport()
    record_root = record_root or records.default_record_root()
    plugin = plugin or plugin_root()
    root = args.root.expanduser().resolve()
    output = args.output
    dispatch_id = uuid.uuid4().hex
    follow_up = bool(args.resume)
    issue = args.work.split("#")[1]
    repo = repository_of(args.work)
    request_path = records.sidecar(output, ".request.json")
    run_path = records.sidecar(output, ".run.json")
    input_path = records.sidecar(output, ".dispatch.bin")
    source_path = records.sidecar(output, ".source.bin")
    stdout_path = records.sidecar(output, ".claude-cloud.stdout.log")
    stderr_path = records.sidecar(output, ".claude-cloud.stderr.log")
    context_path = records.sidecar(output, ".context.bin") if context else None
    brief_path = records.sidecar(output, ".artifact-brief.bin") if artifact_brief else None
    destinations = [output, request_path, run_path, input_path, source_path, stdout_path, stderr_path]
    destinations += [path for path in (context_path, brief_path) if path]
    for path in destinations:
        if path.exists() or path.is_symlink():
            raise CloudError(f"refusing existing output: {path}")
    branch = report_branch(issue, args.stage, dispatch_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    request = records.request_record(
        dispatch_id=dispatch_id, work=args.work, stage=args.stage,
        settings_source=args.settings_source, settings_scope=args.settings_scope,
        vendor="claude", model=args.model, effort=args.effort,
        continuity="resume" if follow_up else "fresh",
        permission_boundary="Claude Code cloud session in auto mode on a remote machine",
        root=root, requested_session_id=args.resume, command=None, retry_of=args.retry_of,
        holder_session_id=args.holder_session_id,
        setting_sources={**settings_sources, "continuity": "launcher route ("
                         + ("resume" if follow_up else "fresh") + ")",
                         "permission_boundary": "cloud route"})
    request.update({
        "implementer_role": "artifact_author" if args.stage == "artifact" else "implementer",
        "route": "cloud", "route_source": route_source, "transport": "claude-cloud-routine",
        "lineage_branch": args.lineage_branch,
        "lineage_pull_request": args.lineage_pull_request,
        "write_bound": {"route": "cloud", "comparison": COMPARISON_REASON},
        "instructions_applied": INSTRUCTIONS_APPLIED,
        "caller_limit_seconds": args.timeout_seconds,
        "budget_override_reason": metadata.get("budget_override_reason"),
    })
    request.update({key: metadata[key] for key in (
        "instalment", "recovery_restart_reason", "recovery_restart_bundle", "budget_lineage",
        "budget_account_before", "progress_baseline", "predecessor_bundle",
        "predecessor_stop_snapshot", "retained_session_id", "retained_session_source",
        "artifact_copy") if key in metadata})
    if args.stage != "artifact":
        request.setdefault("budget_lineage", hashlib.sha256(
            (args.work + str(root) + str(args.lineage_branch)).encode("utf-8")).hexdigest())
    request["context"] = ({"path": str(context_path), "sha256": hashlib.sha256(context).hexdigest()}
                          if context_path else None)
    request["effective_input_sha256"] = hashlib.sha256(effective_prompt).hexdigest()
    request["prompt_composition"] = composition
    if brief_path:
        request["artifact_brief"] = {"path": str(brief_path),
                                     "source": args.artifact_brief_source or str(args.artifact_brief.resolve()),
                                     "sha256": hashlib.sha256(artifact_brief).hexdigest()}
    request["runtime_version"] = None
    request["runtime_version_unavailable_reason"] = "the runtime runs in the cloud session"
    request["revision_before"] = records.git_revision(root)
    request["input"] = str(input_path)
    cloud: dict[str, object] = {"issue": int(issue), "report_branch": branch,
                                "routine_id": (entry or {}).get("routine_id"),
                                "token_file": (entry or {}).get("token_file"),
                                "follow_up": follow_up}
    request["cloud"] = cloud
    failure, refused, token, env = None, False, None, None
    copy = metadata.get("artifact_copy") or {}
    try:
        if preset_failure is not None:
            raise CloudRefusal(preset_failure)
        if follow_up:
            if CLOUD_SESSION.fullmatch(args.resume) is None:
                raise CloudError(f"cloud follow-up needs a cse_ session id: {args.resume!r}")
            env = followup_env()
            login_check(transport, env)
            _start, loaded = loaded_commit(session_attempts(record_root, args.resume), args.resume)
            try:
                installed = installed_practice(plugin, install_path or install_record_path(),
                                               refuse_older=False)["commit"]
            except CloudRefusal as exc:
                # The install record is reported, never a reason to refuse a follow-up.
                installed = f"unavailable: {exc}"
            cloud["practice"] = {"session_loaded": loaded, "installed_at_send": installed,
                                 "drift": installed != loaded, "commit": loaded}
            cloud["session_id"] = args.resume
            cloud["session_url"] = f"https://claude.ai/code/{args.resume}"
        else:
            token = read_token(entry["token_file"])
            practice = installed_practice(plugin, install_path or install_record_path())
            action = compare_pin(transport, entry["practice"], practice["commit"])
            cloud["practice"] = {"repository": entry["practice"]["repository"],
                                 "branch": entry["practice"]["branch"], **practice,
                                 "pin_action": action}
        if args.stage == "artifact":
            holder = copy.get("source_commit") or request["revision_before"]
            status, _value = transport.github("GET", f"repos/{repo}/commits/{holder}")
            if status != 200:
                raise CloudRefusal(f"holder commit {holder} is not on {repo}; push it, then launch again")
            checkout, base = f"commit {holder}", holder
            cloud["holder_commit"] = holder
        else:
            if not args.lineage_branch:
                raise CloudError("a cloud build needs the registered implementation branch")
            local = records.git_revision(root)
            code, text = transport.git(root, "push", "origin", f"HEAD:refs/heads/{args.lineage_branch}")
            if code:
                raise CloudError(f"cannot publish implementation branch: {text[:300]}")
            base = remote_tip(transport, repo, args.lineage_branch)
            if base != local:
                raise CloudError(f"implementation branch at {base} on {repo}, expected {local}")
            checkout = f"branch {args.lineage_branch}"
            cloud["change_branch"] = {"name": args.lineage_branch, "tip_at_fire": base}
        cloud["dispatch_commit"] = create_report_branch(transport, repo, branch, base,
                                                        effective_prompt, dispatch_id)
        text = header(work=args.work, stage=args.stage, dispatch_id=dispatch_id, checkout=checkout,
                      practice_commit=cloud["practice"]["commit"], branch=branch)
        if follow_up:
            code, raw = transport.cli(["claude", "-p", text, "--cloud", args.resume,
                                       "--output-format", "json"], env)
            try:
                value = json.loads(raw)
            except ValueError:
                value = {}
            if code or not isinstance(value, dict) or value.get("ok") is not True \
                    or value.get("session_id") != args.resume:
                raise CloudError(f"follow-up send failed: exit {code} {raw[:300]!r}")
        else:
            # Never retried: a second fire cannot be told apart from a second session.
            status, body = transport.fire(entry["routine_id"], token, text)
            try:
                value = json.loads(body)
            except ValueError:
                value = {}
            session = value.get("claude_code_session_id") if isinstance(value, dict) else None
            if status != 200 or not isinstance(session, str) or CLOUD_SESSION.fullmatch(session) is None:
                raise CloudError(f"fire failed: HTTP {status} {body[:300]}")
            cloud["session_id"] = session
            cloud["session_url"] = value.get("claude_code_session_url")
    except CloudRefusal as exc:
        failure, refused = str(exc), True
    except (CloudError, OSError, subprocess.SubprocessError, KeyError, TypeError, ValueError) as exc:
        failure = str(exc) if isinstance(exc, CloudError) else f"{type(exc).__name__}: {exc}"
    token = None
    attempt: dict[str, object] = {
        "vendor": "claude", "launched": failure is None, "exit_code": None,
        "outcome": "error", "reason": "", "source_format": "claude-cloud-routine",
        "environment": {"status": "cloud", "route": "cloud", "instructions_applied": INSTRUCTIONS_APPLIED},
        "cloud": {"session_id": cloud.get("session_id"), "report_branch": branch},
    }
    run_record: dict[str, object] = {
        "schema_version": records.SCHEMA_VERSION, "dispatch_id": dispatch_id,
        "request": str(request_path), "actual_vendor": "claude", "attempts": [attempt],
        "result": {"source_output": None, "source_output_unavailable_reason": "no completed final source return",
                   "published_output": None,
                   "published_output_unavailable_reason": "no completed final source return",
                   "assessment": "unassessed"},
        "route": "cloud", "launch_comparison": launch_bound.cloud_not_run(),
    }
    published = None
    with records.reserve_bundle(destinations, output) as streams:
        streams[request_path].write(records.json_bytes(request))
        streams[input_path].write(prompt)
        if context_path:
            streams[context_path].write(context)
        if brief_path:
            streams[brief_path].write(artifact_brief)
        for path in (request_path, input_path, context_path, brief_path):
            if path:
                streams[path].flush()
        streams.mark_ready()
        run_record["launched_at"] = request["launched_at"]
        print(f"implementer: dispatch {dispatch_id} -> {output} (cloud route)")
        growing = GrowingRun(run_path, run_record, streams)
        growing.begin_attempt(attempt, "claude", stdout_path, stderr_path)
        if cloud.get("session_id"):
            source = "recorded cloud session" if follow_up else "routine fire response"
            run_record["session_identity"] = {"session_id": cloud["session_id"], "source": source}
            attempt["observed"] = {"session_id": cloud["session_id"], "session_id_source": source,
                                   "source": "cloud-stop-hook"}
        try:
            if failure is not None:
                attempt.update(outcome="refused" if refused else "error", reason=failure)
                run_record["outcome"] = attempt["outcome"]
            else:
                growing.checkpoint()
                published = _finish(args, transport, request, run_record, attempt, growing, deadline,
                                    repo, branch, root, record_root, artifact_brief, validate, streams,
                                    source_path)
        finally:
            run_record.setdefault("outcome", attempt["outcome"])
            if "observed" not in attempt:
                records.add_unobserved(attempt, attempt["reason"] or "cloud attempt did not complete")
            run_record["completed_at"] = datetime.now(timezone.utc).isoformat()
            run_record["revision_after"] = records.git_revision(root)
            records.add_usage_record(attempt, request, completed_at=run_record["completed_at"],
                                     # A practice mismatch stopped before the task, so it filled no seat.
                                     staffing_status="qualified" if run_record["outcome"] in {
                                         "success", "invalid_artifact_return"}
                                     else "unfilled")
            _cloud_usage(attempt)
            for stream in streams.values():
                stream.close()
            streams.streams.clear()
            if published is not None:
                records.publish_output(output, published)
                run_record["result"]["published_output"] = str(output)
                run_record["result"]["published_output_unavailable_reason"] = None
            growing.finish()
    if run_record["outcome"] == "success":
        print(f"implementer: claude cloud session {cloud.get('session_url')} -> {output}")
        return 0
    print(f"implementer: cloud attempt {run_record['outcome']}: {attempt['reason']}", file=sys.stderr)
    return 1


def _cloud_usage(attempt: dict) -> None:
    """The hook's delta as the attempt's usage, in the shape change_cost reads for Claude."""
    cloud = attempt.get("cloud") or {}
    usage = attempt.get("usage")
    if not isinstance(usage, dict) or not isinstance(cloud.get("delta"), dict):
        return
    usage.update({"tokens": {"models": _usage_tokens(cloud["delta"])}, "tokens_unknown_reason": None,
                  "source": "cloud-stop-hook", "scope": "session-delta",
                  "running_total": cloud.get("running_total"), "delta": cloud["delta"],
                  "ledger_check": cloud.get("ledger_check")})
    usage["model"]["reported"] = sorted(cloud["delta"])


def _finish(args, transport, request, run_record, attempt, growing, deadline, repo, branch, root,
            record_root, artifact_brief, validate, streams, source_path) -> bytes | None:
    """Wait for the finish signal, read and check the branch, then post and delete it."""
    cloud = request["cloud"]
    record_cloud = attempt["cloud"]
    while True:
        try:
            left = deadline.remaining()
        except TimeoutError:
            attempt.update(outcome="interrupted",
                           reason=f"no report branch finish signal before the deadline; session "
                                  f"{cloud.get('session_url')}; branch {branch} kept")
            run_record["outcome"] = "interrupted"
            return None
        files = {name: read_branch_file(transport, repo, branch, name)
                 for name in ("report.md", "usage.json")}
        if finished(files):
            break
        growing.tick()
        transport.sleep(min(POLL_SECONDS, max(left - 1, 0.1)))
    for name in ("instructions.md", "practice-check.json"):
        files[name] = read_branch_file(transport, repo, branch, name)
    usage = json.loads(files["usage.json"])
    tip = remote_tip(transport, repo, branch)
    check = json.loads(files["practice-check.json"]) if files["practice-check.json"] else None
    instructions = files["instructions.md"]
    record_cloud["report_tip"] = tip
    record_cloud["instructions_loaded"] = (
        [line.strip() for line in instructions.decode("utf-8", "replace").splitlines() if line.strip()]
        if instructions is not None else None)
    record_cloud["practice_check"] = check
    mismatch = isinstance(check, dict) and check.get("ok") is False
    checks = {"practice": practice_record_check(check, usage) if not mismatch
              else {"ok": True, "reason": "practice mismatch recorded"},
              "skip_ci": skip_ci_check(branch_commits(transport, repo, cloud["dispatch_commit"], tip))}
    if args.stage != "artifact" and not mismatch:
        after = remote_tip(transport, repo, args.lineage_branch)
        status, value = transport.github(
            "GET", f"repos/{repo}/compare/{cloud['change_branch']['tip_at_fire']}...{after}")
        value = value if status == 200 and isinstance(value, dict) else {}
        checks["change_branch"] = change_branch_check(
            cloud["change_branch"]["tip_at_fire"], after,
            [row["sha"] for row in value.get("commits") or []], value.get("status"),
            repair=args.stage in REPAIR_STAGES or bool(args.resume))
    record_cloud["cloud_checks"] = checks
    previous, deltas = _previous_usage(session_attempts(record_root, cloud["session_id"]),
                                       request["dispatch_id"])
    totals = usage.get("totals_by_model") or {}
    this_delta = delta(totals, (previous or {}).get("totals_by_model"))
    record_cloud.update(usage=usage, running_total=totals, delta=this_delta,
                        ledger_check=ledger_check(usage, (previous or {}).get("ledger"),
                                                  [*deltas, this_delta]),
                        profile=cloud_profile(usage, builder_profile(args.stage)))
    if not record_cloud["ledger_check"]["ok"]:
        # A cost the practice cannot stand behind is unknown; the attempt itself stands.
        attempt["fault"] = "cloud usage ledger disagrees: " + "; ".join(record_cloud["ledger_check"]["faults"])
    report = files["report.md"]
    if mismatch:
        attempt.update(outcome="practice_mismatch", reason=report.decode("utf-8", "replace").strip())
        run_record["outcome"] = "practice_mismatch"
    else:
        attempt.update(outcome="success", reason="")
        run_record["outcome"] = "success"
    # An artifact is compared byte for byte with its brief, as a local return is;
    # other returns fold CRLF the way the local launcher does.
    published = report if artifact_brief else report.replace(b"\r\n", b"\n")
    streams[source_path].write(published)
    streams[source_path].flush()
    run_record["result"]["source_output"] = str(source_path)
    run_record["result"]["source_output_unavailable_reason"] = None
    if artifact_brief and not mismatch:
        validation = validate(artifact_brief.decode("utf-8"), report)
        run_record["result"]["return_validation"] = validation
        if validation["status"] == "fail":
            run_record["outcome"] = "invalid_artifact_return"
            run_record["reason"] = validation["reason"]
    if args.stage != "artifact" and not mismatch:
        code, text = transport.git(root, "fetch", "origin", args.lineage_branch)
        if not code:
            code, text = transport.git(root, "merge", "--ff-only", "FETCH_HEAD")
        record_cloud["local_tree"] = {"status": "error" if code else "fast-forwarded", "detail": text[:300]}
        if code:
            run_record["error"] = f"local tree did not follow the cloud branch: {text[:300]}"
    try:
        record_cloud["comment_urls"] = post_report(transport, args.work, args.stage,
                                                   cloud.get("session_url"), branch, tip, report)
        delete_report_branch(transport, request)
        record_cloud["report_branch_deleted"] = True
    except CloudError as exc:
        record_cloud["report_branch_deleted"] = False
        record_cloud["post_or_delete_error"] = str(exc)
    return published

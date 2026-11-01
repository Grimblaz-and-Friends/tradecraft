"""The private repositories' hosted-minutes watch and the logon re-run (#929).

  watch          read every job this UTC month in the four product repositories
                 and post one alert comment on the standing page (#683) when a
                 hosted job is undeclared in a moved repository (condition 1) or
                 the month's hosted minutes are on pace past 1,500 (condition 2).
  rerun-dropped  re-run every private-repository job GitHub dropped after 24
                 hours queued, with one call per run per pass (row 2).
  logon          rerun-dropped, then watch, then rerun-dropped --follow 240.
  status         what the watch sees now, and what it would alert.
  task           register or unregister the scheduled task that runs `logon`.

It runs from a scheduled task under the owner's `gh`, from the installed copy
under `~/.tradecraft-lab/private-ci/bin/` (C6), which carries this file,
`hosted.json`, `repos.json` and `winio.py`. Local state lives in
`~/.tradecraft-lab/private-ci/` unless `--state-dir` names another directory.

Standard library only. Machine-read output is ASCII JSON.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "lib"))
from winio import utf8_stdio  # noqa: E402

OWNER = "Grimblaz-and-Friends"
LAB_REPO = f"{OWNER}/tradecraft"
STANDING_PAGE = 683
OWNER_LOGIN = "Grimblaz"
LABEL = "private-ci"
PROBE_PATH = ".github/workflows/private-ci-probe.yml"
PACE_LIMIT = 1500
PACE_FLOOR_DAYS = 7
QUEUE_LIMIT = timedelta(hours=24) - timedelta(minutes=10)
RERUN_LOOKBACK_DAYS = 14
FOLLOW_INTERVAL_SECONDS = 120
LOGON_FOLLOW_MINUTES = 240
TASK_NAME = "tradecraft-lab-private-ci-watch"
GH_TIMEOUT_SECONDS = 60
HOSTED_IMAGES = re.compile(r"(ubuntu|windows|macos)-")
MULTIPLIER = {"ubuntu": 1, "windows": 2, "macos": 10}
ALERT_MARKER = re.compile(r"<!-- lab:private-ci-watch:v1 keys=(?P<keys>\S+) -->")
QUIET = ("success", "skipped", "neutral")
BOM = chr(0xFEFF)  # built at runtime: a byte-order mark GitHub may keep


class WatchError(Exception):
    """A read or write the watch could not complete."""


# ---------------------------------------------------------------- plumbing


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_state_dir() -> Path:
    return Path.home() / ".tradecraft-lab" / "private-ci"


def write_json_atomic(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("ascii")
    handle, temp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def read_json(path: Path, default):
    try:
        return json.loads(path.read_bytes().decode("utf-8"))
    except FileNotFoundError:
        return default


def no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def gh_run(args: list[str], input_text: str | None = None,
           timeout: float = GH_TIMEOUT_SECONDS) -> str:
    """Run gh with all three streams named and no console window."""
    feed = ({"input": input_text.encode("utf-8")} if input_text is not None
            else {"stdin": subprocess.DEVNULL})
    try:
        proc = subprocess.run(["gh", *args], **feed, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout,
                              creationflags=no_window())
    except subprocess.TimeoutExpired as exc:
        raise WatchError(f"gh {args[0]} timed out after {int(timeout)} s") from exc
    except OSError as exc:
        raise WatchError(f"gh could not be launched: {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip().splitlines()
        raise WatchError(f"gh {' '.join(args[:4])} exited {proc.returncode}: "
                         + (detail[-1] if detail else "no message"))
    return proc.stdout.decode("utf-8", errors="replace")


def parse_pages(text: str) -> list:
    """Flatten `gh api --paginate` output: one JSON value per page, back to back."""
    decoder = json.JSONDecoder()
    values: list = []
    index = 0
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return values
        value, index = decoder.raw_decode(text, index)
        values.append(value)


class GitHub:
    """Every read and write the watch makes, through one gh runner."""

    def __init__(self, runner=None):
        self.runner = runner or gh_run

    def get(self, endpoint: str):
        return json.loads(self.runner(["api", "--method", "GET", endpoint]))

    def get_text(self, endpoint: str) -> str:
        return self.runner(["api", "--method", "GET", endpoint])

    def get_pages(self, endpoint: str) -> list:
        return parse_pages(self.runner(["api", "--method", "GET", "--paginate", endpoint]))

    def send(self, method: str, endpoint: str, payload: dict | None = None):
        if payload is None:
            text = self.runner(["api", "--method", method, endpoint])
        else:
            text = self.runner(["api", "--method", method, endpoint, "--input", "-"],
                               input_text=json.dumps(payload))
        return json.loads(text) if text.strip() else None

    def runs(self, repo: str, since: datetime) -> list[dict]:
        pages = self.get_pages(f"repos/{repo}/actions/runs?per_page=100"
                               f"&created=%3E%3D{since.strftime('%Y-%m-%d')}")
        return [run for page in pages for run in page.get("workflow_runs", [])]

    def run(self, repo: str, run_id: int) -> dict:
        return self.get(f"repos/{repo}/actions/runs/{run_id}")

    def jobs(self, repo: str, run_id: int, which: str = "all") -> list[dict]:
        pages = self.get_pages(f"repos/{repo}/actions/runs/{run_id}/jobs"
                               f"?filter={which}&per_page=100")
        return [job for page in pages for job in page.get("jobs", [])]

    def comments(self, repo: str, issue: int) -> list[dict]:
        return [c for page in self.get_pages(f"repos/{repo}/issues/{issue}/comments?per_page=100")
                for c in (page if isinstance(page, list) else [page])]


def product_repos() -> list[str]:
    """The four product repositories: the installed copy's list, else work.json."""
    installed = HERE / "repos.json"
    if installed.exists():
        return list(json.loads(installed.read_bytes().decode("utf-8")))
    config = json.loads((ROOT / ".tradecraft" / "work.json").read_bytes().decode("utf-8"))
    return list(config["product_repositories"])


def load_hosted(path: Path | None = None) -> list[dict]:
    data = json.loads((path or HERE / "hosted.json").read_bytes().decode("utf-8"))
    return list(data["hosted"])


# ---------------------------------------------------------------- reading jobs


def got_runner(job: dict) -> bool:
    return bool(job.get("runner_name"))


def is_hosted(job: dict) -> bool:
    """Whether a job ran, or would have run, on a GitHub-hosted runner.

    A job that got a runner is hosted when its runner group id is 0, `GitHub
    Actions`. A job that never got one also reads group 0 (Daemon run
    40055997670, attempt 2), so it is judged by what it asked for: hosted only
    when every requested label names a GitHub-hosted image.
    """
    if got_runner(job):
        return job.get("runner_group_id") == 0
    labels = job.get("labels") or []
    return bool(labels) and all(HOSTED_IMAGES.match(label) for label in labels)


def job_minutes(job: dict) -> int:
    """Billed minutes: each job rounded up to a whole minute, times its image's rate."""
    if not got_runner(job) or not is_hosted(job):
        return 0
    started, completed = parse_time(job.get("started_at")), parse_time(job.get("completed_at"))
    if started is None or completed is None:
        return 0
    minutes = max(1, math.ceil((completed - started).total_seconds() / 60))
    image = next((label for label in job.get("labels") or [] if HOSTED_IMAGES.match(label)), "")
    return minutes * MULTIPLIER.get(image.split("-", 1)[0], 1)


def month_start(moment: datetime) -> datetime:
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def days_in_month(moment: datetime) -> int:
    following = (moment.replace(day=28) + timedelta(days=4)).replace(day=1)
    return (following - timedelta(days=1)).day


def projection(minutes: int, moment: datetime) -> float:
    """C7: minutes so far x days in the month / max(days elapsed, 7)."""
    elapsed = (moment - month_start(moment)).total_seconds() / 86400
    return minutes * days_in_month(moment) / max(elapsed, PACE_FLOOR_DAYS)


def collect_month(github: GitHub, repo: str, moment: datetime, cache_dir: Path) -> list[dict]:
    """Every job of every run created this UTC month, across all attempts.

    A completed run's jobs are cached by its attempt number, so each attempt is
    read once and a re-run's new attempt is read when it appears.
    """
    jobs = []
    for run in github.runs(repo, month_start(moment)):
        created = parse_time(run.get("created_at"))
        if created is None or created < month_start(moment):
            continue
        cache = cache_dir / repo.replace("/", "__") / f"{run['id']}.json"
        held = read_json(cache, None)
        if held and held.get("run_attempt") == run.get("run_attempt"):
            run_jobs = held["jobs"]
        else:
            run_jobs = github.jobs(repo, run["id"])
            if run.get("status") == "completed":
                write_json_atomic(cache, {"run_attempt": run.get("run_attempt"),
                                          "jobs": [slim(job) for job in run_jobs]})
        for job in run_jobs:
            jobs.append({**slim(job), "repo": repo, "path": run.get("path"),
                         "run_url": run.get("html_url")})
    return jobs


def slim(job: dict) -> dict:
    keep = ("id", "run_id", "run_attempt", "name", "status", "conclusion", "labels",
            "runner_id", "runner_name", "runner_group_id", "created_at", "started_at",
            "completed_at", "html_url")
    return {key: job.get(key) for key in keep}


def moved_now(jobs: list[dict]) -> set[str]:
    """C8: a repository has moved once a non-probe job ran on a private-ci runner."""
    return {job["repo"] for job in jobs
            if LABEL in (job.get("labels") or []) and got_runner(job)
            and job.get("path") != PROBE_PATH}


def evaluate(jobs: list[dict], hosted: list[dict], moved: set[str], moment: datetime) -> dict:
    """Both alert conditions over one month's jobs; no I/O."""
    declared = {(entry["path"], entry["job"]) for entry in hosted}
    month = moment.strftime("%Y-%m")
    unlisted: dict[str, dict] = {}
    total = 0
    contributors: dict[tuple, int] = {}
    matched = set()
    for job in jobs:
        if not is_hosted(job):
            continue
        minutes = job_minutes(job)
        total += minutes
        where = (job["repo"], job.get("path"), job.get("name"))
        contributors[where] = contributors.get(where, 0) + minutes
        if (job.get("path"), job.get("name")) in declared:
            matched.add((job.get("path"), job.get("name")))
            continue
        if job.get("path") == PROBE_PATH or job["repo"] not in moved:
            continue
        key = f"unlisted:{job['repo']}:{job.get('path')}:{job.get('name')}:{month}"
        entry = unlisted.setdefault(key, {"key": key, "repo": job["repo"],
                                          "path": job.get("path"), "job": job.get("name"),
                                          "run_url": job.get("run_url"), "minutes": 0})
        entry["minutes"] += minutes
    projected = projection(total, moment)
    top = sorted(contributors.items(), key=lambda item: (-item[1], item[0]))[:3]
    alerts = list(unlisted.values())
    if projected > PACE_LIMIT:
        alerts.append({"key": f"pace:{month}", "minutes": total,
                       "projected": round(projected),
                       "top": [{"repo": r, "path": p, "job": j, "minutes": m}
                               for (r, p, j), m in top]})
    return {"month": month, "minutes": total, "projected": round(projected, 1),
            "alerts": alerts,
            "declared": [{"path": e["path"], "job": e["job"],
                          "matched": (e["path"], e["job"]) in matched} for e in hosted]}


def alerted_keys(comments: list[dict]) -> set[str]:
    """Keys an earlier watch comment on the page named, honoured from the owner only."""
    keys = set()
    for comment in comments:
        if (comment.get("user") or {}).get("login") != OWNER_LOGIN:
            continue
        first = (comment.get("body") or "").lstrip(BOM).split("\n", 1)[0].strip()
        match = ALERT_MARKER.fullmatch(first)
        if match:
            keys.update(match.group("keys").split(","))
    return keys


def alert_body(alerts: list[dict]) -> str:
    """The alert comment. Its marker is not the Steward's, so the wake reads it as intake."""
    lines = [f"<!-- lab:private-ci-watch:v1 keys={','.join(a['key'] for a in alerts)} -->",
             "**Private-CI watch (#929).** Verify with `python tools/private_ci/watch.py "
             "status`; the Steward's `references/private-ci.md` says which one-line move "
             "to bring the owner.", ""]
    for alert in alerts:
        if alert["key"].startswith("unlisted:"):
            lines.append(f"- Hosted job not on the declared list: `{alert['repo']}` "
                         f"`{alert['path']}` job `{alert['job']}`, {alert['minutes']} min "
                         f"this month ({alert['run_url']}).")
        else:
            top = "; ".join(f"`{t['repo']}` `{t['path']}` `{t['job']}` {t['minutes']} min"
                            for t in alert["top"])
            lines.append(f"- Hosted minutes on pace past {PACE_LIMIT}: {alert['minutes']} "
                         f"min so far, projected {alert['projected']} for the month. "
                         f"Largest: {top}.")
    return "\n".join(lines) + "\n"


def watch(github: GitHub, state_dir: Path, moment: datetime, *, post: bool = True,
          repos: list[str] | None = None, hosted: list[dict] | None = None) -> dict:
    repos = repos if repos is not None else product_repos()
    hosted = hosted if hosted is not None else load_hosted()
    jobs = []
    for repo in repos:
        jobs.extend(collect_month(github, repo, moment, state_dir / "jobs"))
    moved = set(read_json(state_dir / "moved.json", [])) | moved_now(jobs)
    if post:
        write_json_atomic(state_dir / "moved.json", sorted(moved))
    result = evaluate(jobs, hosted, moved, moment)
    seen = alerted_keys(github.comments(LAB_REPO, STANDING_PAGE))
    seen |= set(read_json(state_dir / "alerted.json", []))
    fresh = [alert for alert in result["alerts"] if alert["key"] not in seen]
    posted = None
    if fresh and post:
        comment = github.send("POST", f"repos/{LAB_REPO}/issues/{STANDING_PAGE}/comments",
                              {"body": alert_body(fresh)})
        posted = (comment or {}).get("html_url")
        write_json_atomic(state_dir / "alerted.json",
                          sorted(seen | {alert["key"] for alert in fresh}))
    return {**result, "moved": sorted(moved),
            "awaiting_carrier": sorted(set(repos) - moved),
            "would_alert": [a["key"] for a in fresh], "posted": posted}


# ---------------------------------------------------------------- the re-run (row 2)


def latest_occurrences(jobs: list[dict]) -> dict[str, dict]:
    """Each job name's record with the highest run attempt (then the highest id)."""
    latest: dict[str, dict] = {}
    for job in jobs:
        held = latest.get(job["name"])
        if held is None or (job.get("run_attempt") or 0, job["id"]) > \
                (held.get("run_attempt") or 0, held["id"]):
            latest[job["name"]] = job
    return latest


def owed(job: dict, path: str | None) -> bool:
    """A job GitHub dropped for queue time: never got a runner, ended after ~24 hours."""
    if path == PROBE_PATH:
        return False
    if got_runner(job) or (job.get("runner_id") or 0) != 0:
        return False
    if job.get("status") != "completed" or job.get("conclusion") not in ("failure", "cancelled"):
        return False
    if job.get("steps"):
        return False
    created, completed = parse_time(job.get("created_at")), parse_time(job.get("completed_at"))
    return created is not None and completed is not None and completed - created >= QUEUE_LIMIT


def plan_call(run: dict, all_jobs: list[dict], latest_jobs: list[dict]) -> dict | None:
    """The one call a pass makes on a completed run, or None when nothing is owed."""
    path = run.get("path")
    latest = latest_occurrences(all_jobs)
    owing = sorted((job for job in latest.values() if owed(job, path)), key=lambda j: j["id"])
    if not owing:
        return None
    owed_ids = {job["id"] for job in owing}
    names = {job["name"] for job in latest_jobs}
    failed = [job for job in latest_jobs if job.get("conclusion") not in QUIET]
    if names >= set(latest) and all(job["id"] in owed_ids for job in failed):
        return {"kind": "run", "endpoint": f"actions/runs/{run['id']}/rerun-failed-jobs",
                "jobs": [job["name"] for job in owing]}
    first = owing[0]
    return {"kind": "job", "endpoint": f"actions/jobs/{first['id']}/rerun",
            "jobs": [first["name"]]}


def rerun_pass(github: GitHub, state_dir: Path, moment: datetime, *,
               repos: list[str] | None = None, only: set[tuple] | None = None) -> dict:
    """One pass: at most one call per run; returns calls made and runs still owing."""
    repos = repos if repos is not None else product_repos()
    ledger = read_json(state_dir / "reruns.json", {})
    calls, owing, waiting = [], [], []
    since = moment - timedelta(days=RERUN_LOOKBACK_DAYS)
    for repo in repos:
        if only is not None:
            runs = [github.run(repo, run_id) for (r, run_id) in sorted(only) if r == repo]
        else:
            runs = github.runs(repo, since)
        for run in runs:
            key = f"{repo}#{run['id']}"
            if run.get("path") == PROBE_PATH:
                continue
            if run.get("status") != "completed":
                if key in ledger:
                    waiting.append((repo, run["id"]))
                continue
            if key in ledger and (run.get("run_attempt") or 1) <= ledger[key]:
                waiting.append((repo, run["id"]))
                continue
            all_jobs = github.jobs(repo, run["id"], "all")
            plan = plan_call(run, all_jobs, github.jobs(repo, run["id"], "latest"))
            if plan is None:
                continue
            github.send("POST", f"repos/{repo}/{plan['endpoint']}")
            ledger[key] = run.get("run_attempt") or 1
            write_json_atomic(state_dir / "reruns.json", ledger)
            calls.append({"repo": repo, "run": run["id"], **plan})
            owing.append((repo, run["id"]))
    return {"calls": calls, "pending": sorted(set(owing) | set(waiting))}


def rerun_dropped(github: GitHub, state_dir: Path, *, follow_minutes: int = 0,
                  repos: list[str] | None = None, clock=now_utc, sleep=time.sleep) -> dict:
    first = rerun_pass(github, state_dir, clock(), repos=repos)
    calls, pending = list(first["calls"]), set(first["pending"])
    deadline = time.monotonic() + follow_minutes * 60
    while follow_minutes and pending and time.monotonic() < deadline:
        sleep(FOLLOW_INTERVAL_SECONDS)
        result = rerun_pass(github, state_dir, clock(), repos=repos, only=pending)
        calls.extend(result["calls"])
        pending = set(result["pending"])
    return {"calls": calls, "pending": [f"{r}#{n}" for r, n in sorted(pending)]}


# ---------------------------------------------------------------- tasks


def xml_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def task_xml(description: str, triggers: str, command: str, arguments: str,
             working_dir: str, limit: str) -> str:
    """A Task Scheduler definition: least privilege, no window, no overlap."""
    return (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
        "  <RegistrationInfo>\n"
        f"    <Description>{xml_escape(description)}</Description>\n"
        "  </RegistrationInfo>\n"
        f"  <Triggers>\n{triggers}  </Triggers>\n"
        "  <Principals>\n"
        '    <Principal id="Author">\n'
        "      <LogonType>InteractiveToken</LogonType>\n"
        "      <RunLevel>LeastPrivilege</RunLevel>\n"
        "    </Principal>\n"
        "  </Principals>\n"
        "  <Settings>\n"
        "    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n"
        "    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n"
        "    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n"
        "    <StartWhenAvailable>true</StartWhenAvailable>\n"
        f"    <ExecutionTimeLimit>{limit}</ExecutionTimeLimit>\n"
        "    <Enabled>true</Enabled>\n"
        "  </Settings>\n"
        '  <Actions Context="Author">\n'
        "    <Exec>\n"
        f"      <Command>{xml_escape(command)}</Command>\n"
        f"      <Arguments>{xml_escape(arguments)}</Arguments>\n"
        f"      <WorkingDirectory>{xml_escape(working_dir)}</WorkingDirectory>\n"
        "    </Exec>\n"
        "  </Actions>\n"
        "</Task>\n"
    )


def logon_trigger(user: str) -> str:
    return ("    <LogonTrigger>\n"
            f"      <UserId>{xml_escape(user)}</UserId>\n"
            "      <Enabled>true</Enabled>\n"
            "    </LogonTrigger>\n")


def watch_task_xml(interpreter: str, script: str, working_dir: str, user: str,
                   start: datetime) -> str:
    """The watch task: `logon` at the owner's logon and daily at 09:00 local."""
    daily = ("    <CalendarTrigger>\n"
             f"      <StartBoundary>{start.strftime('%Y-%m-%d')}T09:00:00</StartBoundary>\n"
             "      <ScheduleByDay>\n"
             "        <DaysInterval>1</DaysInterval>\n"
             "      </ScheduleByDay>\n"
             "      <Enabled>true</Enabled>\n"
             "    </CalendarTrigger>\n")
    return task_xml("tradecraft lab: re-run private-repository jobs GitHub dropped after "
                    "24 hours queued, and watch hosted minutes (#929). No model runs.",
                    logon_trigger(user) + daily, interpreter, f'"{script}" logon',
                    working_dir, "PT5H")


def windowless_interpreter() -> str:
    candidate = Path(sys.executable).with_name("pythonw.exe")
    return str(candidate if candidate.exists() else Path(sys.executable))


def owner_account() -> str:
    domain = os.environ.get("USERDOMAIN", "")
    user = os.environ.get("USERNAME", "")
    return f"{domain}\\{user}" if domain else user


def schtasks(args: list[str]) -> str:
    proc = subprocess.run(["schtasks.exe", *args], stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=60, creationflags=no_window())
    out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        raise WatchError(f"schtasks {args[0]} exited {proc.returncode}: {out}")
    return out


def register_task(name: str, xml: str, run=schtasks) -> str:
    handle, path = tempfile.mkstemp(suffix=".xml")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(xml.encode("utf-16"))
        return run(["/Create", "/TN", name, "/XML", path, "/F"])
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ---------------------------------------------------------------- commands


def emit(value) -> None:
    if sys.stdout is not None:
        sys.stdout.write(json.dumps(value, ensure_ascii=True, sort_keys=True) + "\n")
        sys.stdout.flush()


def logon(github: GitHub, state_dir: Path, *, clock=now_utc, sleep=time.sleep,
          repos: list[str] | None = None, hosted: list[dict] | None = None) -> dict:
    """At logon: re-run, then watch, then follow the re-run for 240 minutes."""
    steps = {}
    steps["rerun"] = rerun_dropped(github, state_dir, repos=repos, clock=clock, sleep=sleep)
    steps["watch"] = watch(github, state_dir, clock(), repos=repos, hosted=hosted)
    steps["follow"] = rerun_dropped(github, state_dir, follow_minutes=LOGON_FOLLOW_MINUTES,
                                    repos=repos, clock=clock, sleep=sleep)
    return steps


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Watch the private repositories' hosted minutes and re-run dropped jobs.")
    parser.add_argument("--state-dir", help="local state (default ~/.tradecraft-lab/private-ci)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("watch", help="read this month's jobs and alert on #683")
    rerun = sub.add_parser("rerun-dropped", help="re-run jobs dropped after 24 hours queued")
    rerun.add_argument("--follow", type=int, default=0, metavar="MINUTES")
    sub.add_parser("logon", help="rerun-dropped, watch, then rerun-dropped --follow 240")
    sub.add_parser("status", help="what the watch sees, posting nothing")
    task = sub.add_parser("task", help="register or unregister the watch task")
    group = task.add_mutually_exclusive_group(required=True)
    group.add_argument("--register", action="store_true")
    group.add_argument("--unregister", action="store_true")
    return parser


def run_command(args: argparse.Namespace, github: GitHub, state_dir: Path) -> dict:
    moment = now_utc()
    if args.command == "watch":
        return watch(github, state_dir, moment)
    if args.command == "rerun-dropped":
        return rerun_dropped(github, state_dir, follow_minutes=args.follow)
    if args.command == "logon":
        return logon(github, state_dir)
    if args.command == "status":
        seen = watch(github, state_dir, moment, post=False)
        ledger = read_json(state_dir / "reruns.json", {})
        return {**seen, "reruns_recorded": ledger,
                "last_run": read_json(state_dir / "last-run.json", None),
                "last_success": read_json(state_dir / "last-success.json", None)}
    if args.unregister:
        return {"unregistered": schtasks(["/Delete", "/TN", TASK_NAME, "/F"])}
    xml = watch_task_xml(windowless_interpreter(), str(HERE / "watch.py"), str(HERE),
                         owner_account(), moment)
    return {"registered": register_task(TASK_NAME, xml)}


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    args = build_parser().parse_args(argv)
    state_dir = Path(args.state_dir) if args.state_dir else default_state_dir()
    github = GitHub()
    started = iso(now_utc())
    record = args.command in ("watch", "rerun-dropped", "logon")
    try:
        value = run_command(args, github, state_dir)
    except (WatchError, ValueError, KeyError, OSError) as exc:
        if record:
            write_json_atomic(state_dir / "last-run.json",
                              {"command": args.command, "at": started, "ok": False,
                               "error": str(exc)})
        emit({"ok": False, "error": str(exc)})
        return 1
    if record:
        write_json_atomic(state_dir / "last-run.json",
                          {"command": args.command, "at": started, "ok": True})
        write_json_atomic(state_dir / "last-success.json",
                          {"command": args.command, "at": started})
    emit({"ok": True, **value})
    return 0


if __name__ == "__main__":
    sys.exit(main())

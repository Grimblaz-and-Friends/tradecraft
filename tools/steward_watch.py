"""The Steward's wake, handover and cover: every decision, none of the wiring.

The Steward is one standing session that the owner and holders message by
name. Three mechanisms keep it answering without a model call while nothing is
new (#890):

  signal    every comment the Steward posts on the standing page opens with a
            `lab:steward:v1` marker, and one marked comment -- the watermark --
            records the last page comment it has handled, the last read with
            its cutoff, and the alert issue. An unmarked comment above the
            watermark is intake.
  wake      the `steward-wake` mod runs `wake` on a timer and starts one turn
            per new trigger: a read that has come due, or a piece of intake.
  handover  past a token threshold, at a quiet moment, the Steward writes a
            state file, the mod clears the session in place, and the cleared
            session resumes from that file.
  cover     an hourly task with no model runs `cover`, which has a tradecraft
            workflow mention the owner when lab work has waited unanswered.

The mod under `tools/steward-wake/` only runs timers, observes the session,
calls this script and acts on what it prints, so the logic lives here where CI
can reach it. Every local write goes through this script, under one state
directory: `--state-dir`, else the environment variable STEWARD_LAB_STATE_DIR,
else `~/.tradecraft-lab/steward`. Probe-only settings are refused against that
default, so a probe can neither leave state in nor suppress the live Steward's.

Standard library only. Machine-read output is ASCII JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))
from winio import utf8_stdio  # noqa: E402

OWNER = "Grimblaz-and-Friends"
LAB_REPO = f"{OWNER}/tradecraft"
STANDING_PAGE = 683
OWNER_LOGIN = "Grimblaz"
ALERT_BOT = "github-actions[bot]"
ALERT_WORKFLOW = "steward-alert.yml"
WORK_CONFIG = ROOT / ".tradecraft" / "work.json"
PRACTICE_REPOS = (f"{OWNER}/tradecraft", f"{OWNER}/change-proof")
STATE_ENV = "STEWARD_LAB_STATE_DIR"
CELL = "docs/cells/steward/SKILL.md"
DEPTH = "docs/cells/steward/references/wake-and-cover.md"

READ_MERGES = 5
INTAKE_WAIT_SECONDS = 3600
READ_WAIT_SECONDS = 3 * 3600
COVER_STALE_SECONDS = 7200
HANDOVER_TOKENS = 250_000
OWNER_QUIET_SECONDS = 3600
SETTLE_SECONDS = 60
STATE_FILE_WAIT_SECONDS = 15 * 60
CLEAR_WAIT_SECONDS = 120
RETRY_HOLD_SECONDS = 3600
GH_TIMEOUT_SECONDS = 60
COVER_DEADLINE_SECONDS = 240
LOCK_STALE_SECONDS = 600
ORIGINS_KEPT = 500
TASK_NAME = "tradecraft-lab-steward-cover"
GH_COMMAND = ["gh"]
BOM = chr(0xFEFF)  # built at runtime: a byte-order mark GitHub may keep

# Settings only a probe may change. The mod passes their values to `config`.
PROBE_ENV = (
    "STEWARD_WAKE_TICK_SECONDS",
    "STEWARD_WAKE_HANDOVER_TOKENS",
    "STEWARD_WAKE_OWNER_QUIET_SECONDS",
    "STEWARD_WAKE_SETTLE_SECONDS",
    "STEWARD_WAKE_SIMULATE_CLEAR_REFUSED",
    "STEWARD_WAKE_PAGE",
)

# Prompt origins that are not the owner speaking. Every other kind -- named or
# not, `unclassified` included -- counts as the owner, so an unsure guard delays
# a handover rather than firing one within an hour of his last message.
NON_OWNER_ORIGINS = frozenset({
    "plugin", "peer", "peer-send-message", "task-notification",
    "scheduled-trigger", "projects-relay", "coordinator", "observer",
    "observer-activity",
})

HANDOVER_HEADINGS = (
    "In progress",
    "Promises and deadlines",
    "Running tasks and output paths",
    "The owner's unrecorded words, verbatim",
)
FOUR_RECORDS = "#683, the memory store, the open issues and the owner board"

MARKER = re.compile(
    r"<!-- lab:steward:v1 kind=(?P<kind>post|read-note|watermark)(?P<attrs>(?: [a-z]+=\S+)*) -->")
ATTR = re.compile(r" ([a-z]+)=(\S+)")
KIND_ATTRS = {
    "post": (),
    "read-note": ("read",),
    "watermark": ("handled", "read", "cutoff", "alerts"),
}
HANDOVER_HEADER = re.compile(
    r"<!-- lab:steward-handover:v1 id=(?P<id>\S+) old_session=(?P<old>\S+) "
    r"written=(?P<written>\S+) -->")
ALERTS_ISSUE_MARKER = "<!-- lab:steward-alerts:v1 -->"
ALERT_MARKER = re.compile(r"<!-- lab:steward-alert:v1 items=(?P<items>\S+) -->")
ITEMS = re.compile(r"(?:intake|read|probe):\d+(?:,(?:intake|read|probe):\d+)*")


class WatchError(Exception):
    """A fault the caller must see, named in plain words."""


# ---------------------------------------------------------------- time


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- state directory


def default_state_dir() -> Path:
    return Path.home() / ".tradecraft-lab" / "steward"


def resolve_state_dir(flag: str | None, environ=None) -> Path:
    environ = os.environ if environ is None else environ
    chosen = flag or environ.get(STATE_ENV) or None
    return Path(chosen).expanduser() if chosen else default_state_dir()


def is_default_dir(path: Path) -> bool:
    return os.path.normcase(os.path.abspath(path)) == os.path.normcase(
        os.path.abspath(default_state_dir()))


def refuse_probe_against_default(state_dir: Path, probe_settings: list[str]) -> None:
    """Probe-only settings may never touch the production state directory."""
    if probe_settings and is_default_dir(state_dir):
        raise WatchError(
            "probe-only setting(s) " + ", ".join(sorted(probe_settings))
            + " refused against the default state directory " + str(state_dir)
            + "; set --state-dir or " + STATE_ENV + " to a probe directory")


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


# ---------------------------------------------------------------- GitHub


def _no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def gh_run(args: list[str], input_text: str | None = None,
           timeout: float = GH_TIMEOUT_SECONDS) -> str:
    """Run gh with all three streams named and no console window."""
    # `input` opens stdin as a pipe itself, so stdin is named either way.
    feed = ({"input": input_text.encode("utf-8")} if input_text is not None
            else {"stdin": subprocess.DEVNULL})
    try:
        proc = subprocess.run(
            [*GH_COMMAND, *args], **feed,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, creationflags=_no_window())
    except subprocess.TimeoutExpired as exc:
        raise WatchError(f"gh {args[0]} timed out after {int(timeout)} s") from exc
    except OSError as exc:
        raise WatchError(f"gh could not be launched: {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip().splitlines()
        raise WatchError(f"gh {' '.join(args[:3])} exited {proc.returncode}: "
                         + (detail[-1] if detail else "no message"))
    return proc.stdout.decode("utf-8", errors="replace")


class GitHub:
    """Every read and write this script makes, through one gh runner."""

    def __init__(self, runner=None, deadline: float | None = None):
        self.runner = runner or gh_run
        self.deadline = deadline

    def _timeout(self) -> float:
        if self.deadline is None:
            return GH_TIMEOUT_SECONDS
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise WatchError("the run's deadline passed")
        return min(GH_TIMEOUT_SECONDS, left)

    def get_all(self, endpoint: str) -> list:
        text = self.runner(["api", "--method", "GET", "--paginate", endpoint],
                           timeout=self._timeout())
        return parse_pages(text)

    def get(self, endpoint: str):
        text = self.runner(["api", "--method", "GET", endpoint], timeout=self._timeout())
        return json.loads(text)

    def send(self, method: str, endpoint: str, payload: dict):
        text = self.runner(["api", "--method", method, endpoint, "--input", "-"],
                           input_text=json.dumps(payload), timeout=self._timeout())
        return json.loads(text) if text.strip() else None

    def comments(self, repo: str, issue: int) -> list[dict]:
        return self.get_all(f"repos/{repo}/issues/{issue}/comments")

    def merges_since(self, repo: str, cutoff: str) -> list[dict]:
        text = self.runner(
            ["pr", "list", "--repo", repo, "--state", "merged", "--search",
             f"merged:>={cutoff}", "--json", "number,mergedAt,url", "--limit", "100"],
            timeout=self._timeout())
        return json.loads(text) if text.strip() else []

    def dispatch_alert(self, issue: int, items: list[str]) -> None:
        self.runner(["workflow", "run", ALERT_WORKFLOW, "--repo", LAB_REPO, "--ref", "main",
                     "-f", f"issue={issue}", "-f", f"items={','.join(items)}"],
                    timeout=self._timeout())


def parse_pages(text: str) -> list:
    """Flatten `gh api --paginate` output: one JSON array per page, back to back."""
    decoder = json.JSONDecoder()
    items: list = []
    index = 0
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return items
        value, index = decoder.raw_decode(text, index)
        if isinstance(value, list):
            items.extend(value)
        else:
            items.append(value)


def lab_repos() -> list[str]:
    config = json.loads(WORK_CONFIG.read_bytes().decode("utf-8"))
    return list(PRACTICE_REPOS) + list(config["product_repositories"])


# ---------------------------------------------------------------- signal (row 1)


def first_line(body: str | None) -> str:
    text = (body or "").lstrip(BOM)
    return text.split("\n", 1)[0].rstrip()


def classify(body: str | None) -> dict | None:
    """The Steward marker on a comment's first line, parsed, or None.

    Only the first line counts, and only in the exact grammar: a marker quoted
    later in a comment does not make that comment the Steward's.
    """
    match = MARKER.fullmatch(first_line(body))
    if not match:
        return None
    attrs = dict(ATTR.findall(match.group("attrs")))
    kind = match.group("kind")
    if tuple(attrs) != KIND_ATTRS[kind]:
        return None
    for name in ("handled", "read", "alerts"):
        if name in attrs and not attrs[name].isdigit():
            return None
    if "cutoff" in attrs:
        try:
            parse_time(attrs["cutoff"])
        except ValueError:
            return None
    return {"kind": kind, **attrs}


def marker_line(kind: str, **attrs) -> str:
    parts = "".join(f" {name}={attrs[name]}" for name in KIND_ATTRS[kind])
    return f"<!-- lab:steward:v1 kind={kind}{parts} -->"


WATERMARK_PROSE = (
    "The Steward's watermark for this page: the last comment it has handled, "
    "the last read and its cutoff, and the alert issue. It is edited in place.")


def watermark_body(handled: int, read: int, cutoff: str, alerts: int) -> str:
    return marker_line("watermark", handled=handled, read=read, cutoff=cutoff,
                       alerts=alerts) + "\n" + WATERMARK_PROSE + "\n"


class Page:
    """One standing page's comments, read once and classified."""

    def __init__(self, repo: str, number: int, comments: list[dict]):
        self.repo = repo
        self.number = number
        self.comments = sorted(comments, key=lambda c: int(c["id"]))
        self.marks = {int(c["id"]): classify(c.get("body")) for c in self.comments}

    def watermark(self) -> tuple[dict, dict]:
        found = [c for c in self.comments
                 if (self.marks[int(c["id"])] or {}).get("kind") == "watermark"]
        if len(found) != 1:
            raise WatchError(
                f"{self.repo}#{self.number} carries {len(found)} watermark comments; "
                "exactly one is required (seed one at install, or delete the extras)")
        comment = found[0]
        mark = self.marks[int(comment["id"])]
        return comment, {"comment_id": int(comment["id"]), "handled": int(mark["handled"]),
                         "read": int(mark["read"]), "cutoff": mark["cutoff"],
                         "alerts": int(mark["alerts"])}

    def intake(self, handled: int) -> list[dict]:
        return [c for c in self.comments
                if self.marks[int(c["id"])] is None and int(c["id"]) > handled]

    def read_note_exists(self, read: int) -> bool:
        return any(mark and mark["kind"] == "read-note" and int(mark["read"]) == read
                   for mark in self.marks.values())

    def link(self, comment_id: int | None = None) -> str:
        base = f"https://github.com/{self.repo}/issues/{self.number}"
        return base if comment_id is None else f"{base}#issuecomment-{comment_id}"


def load_page(github: GitHub, page: int) -> Page:
    return Page(LAB_REPO, page, github.comments(LAB_REPO, page))


# ---------------------------------------------------------------- reads (row 2 and 4)


def read_merges(github: GitHub, cutoff: str, repos: list[str]) -> tuple[list[dict], dict]:
    """Merges strictly after the cutoff, across the lab, and each repo's reach."""
    bound = parse_time(cutoff)
    merges: list[dict] = []
    reach: dict[str, str] = {}
    for repo in repos:
        try:
            rows = github.merges_since(repo, cutoff)
        except WatchError as exc:
            reach[repo] = f"error: {exc}"
            continue
        reach[repo] = f"ok ({len(rows)} rows)"
        for row in rows:
            if parse_time(row["mergedAt"]) > bound:
                merges.append({"repo": repo, "number": row["number"], "mergedAt": row["mergedAt"]})
    merges.sort(key=lambda row: parse_time(row["mergedAt"]))
    return merges, reach


def read_due(merges: list[dict]) -> str | None:
    """When the read came due: the fifth merge after the cutoff, or None."""
    if len(merges) < READ_MERGES:
        return None
    return merges[READ_MERGES - 1]["mergedAt"]


# ---------------------------------------------------------------- wake (row 2)


def page_scope(page: int) -> str:
    return f"{LAB_REPO}#{page}/"


def woken_keys(state_dir: Path) -> list[str]:
    return list(read_json(state_dir / "woken.json", {"keys": []}).get("keys", []))


def save_woken(state_dir: Path, keys: list[str]) -> None:
    write_json_atomic(state_dir / "woken.json", {"schema_version": 1, "keys": sorted(set(keys))})


def cover_state(state_dir: Path, now: datetime) -> dict:
    record = read_json(state_dir / "cover-last-success.json", None)
    last = record.get("at") if isinstance(record, dict) else None
    stale = last is None or (now - parse_time(last)).total_seconds() > COVER_STALE_SECONDS
    return {"last_success": last, "stale": stale,
            "key": f"cover-stale:{last or 'none'}" if stale else None}


def handover_state(state_dir: Path) -> dict:
    return read_json(state_dir / "handover-state.json", {"state": "idle"})


def compute_triggers(page: Page, mark: dict, merges: list[dict]) -> list[dict]:
    triggers = []
    if read_due(merges) is not None:
        number = mark["read"] + 1
        triggers.append({
            "key": f"read:{number}",
            "text": (f"steward-wake: read {number} is due ({len(merges)} merges since "
                     f"{mark['cutoff']}). See {CELL}."),
            "link": page.link(),
        })
    for comment in page.intake(mark["handled"]):
        link = page.link(int(comment["id"]))
        triggers.append({
            "key": f"intake:{comment['id']}",
            "text": f"steward-wake: new intake on #{page.number}: {link}",
            "link": link,
        })
    return triggers


def wake(github: GitHub, state_dir: Path, page_number: int, now: datetime,
         repos: list[str] | None = None) -> dict:
    cover = cover_state(state_dir, now)
    if handover_state(state_dir).get("state") == "active":
        return {"schema_version": 1, "paused": "handover active", "triggers": [],
                "cover": cover, "error": None}
    page = load_page(github, page_number)
    _, mark = page.watermark()
    merges, reach = read_merges(github, mark["cutoff"], repos or lab_repos())
    failed = sorted(repo for repo, result in reach.items() if not result.startswith("ok"))
    if failed:
        raise WatchError("merge read failed for " + ", ".join(failed)
                         + "; nothing woken and nothing pruned")
    triggers = compute_triggers(page, mark, merges)
    scope = page_scope(page_number)
    present = {scope + t["key"] for t in triggers}
    if cover["key"]:
        present.add(scope + cover["key"])
    stored = woken_keys(state_dir)
    kept = [key for key in stored if not key.startswith(scope) or key in present]
    if kept != stored:
        save_woken(state_dir, kept)
    fresh = [t for t in triggers if scope + t["key"] not in kept]
    if cover["key"] and scope + cover["key"] in kept:
        cover = {**cover, "noted": True}
    return {"schema_version": 1, "paused": None, "triggers": fresh, "cover": cover, "error": None}


def mark_woken(state_dir: Path, page_number: int, key: str) -> None:
    keys = woken_keys(state_dir)
    keys.append(page_scope(page_number) + key)
    save_woken(state_dir, keys)


# ---------------------------------------------------------------- handover (row 3)


def origin_is_owner(kind: str) -> bool:
    return kind not in NON_OWNER_ORIGINS


def record_origin(state_dir: Path, kind: str, owner: bool, now: datetime) -> None:
    path = state_dir / "origins.log"
    state_dir.mkdir(parents=True, exist_ok=True)
    try:
        lines = path.read_bytes().decode("ascii", errors="replace").splitlines()
    except FileNotFoundError:
        lines = []
    safe = re.sub(r"[^A-Za-z0-9_.:-]", "?", kind)[:64] or "?"
    lines.append(f"{iso(now)} {safe} owner={'yes' if owner else 'no'}")
    data = ("\n".join(lines[-ORIGINS_KEPT:]) + "\n").encode("ascii")
    handle, temp = tempfile.mkstemp(dir=str(state_dir), prefix="origins.", suffix=".tmp")
    with os.fdopen(handle, "wb") as stream:
        stream.write(data)
    os.replace(temp, path)


# Each gate condition is named, so a test can delete one and watch its row flip.
GATE_CONDITIONS = (
    ("tokens", lambda f: f["tokens"] > f["threshold"] or f["skip_tokens"]),
    ("turn-running", lambda f: not f["turn_running"]),
    ("settle", lambda f: f["since_turn_complete"] >= f["settle"] and not f["turn_started_since"]),
    ("background", lambda f: f["background_tasks"] == 0 and f["crons"] == 0 and f["agents_busy"] == 0),
    ("owner-quiet", lambda f: f["since_owner"] >= f["owner_quiet"]),
    ("disabled", lambda f: not f["disabled"]),
)


def handover_due(facts: dict, conditions=GATE_CONDITIONS) -> dict:
    blocking = [name for name, holds in conditions if not holds(facts)]
    return {"due": not blocking, "blocking": blocking}


def handover_path(state_dir: Path) -> Path:
    return state_dir / "handover.md"


def handover_check(state_dir: Path, handover_id: str, since: str) -> dict:
    path = handover_path(state_dir)
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except FileNotFoundError:
        return {"ok": False, "present": False, "problems": [f"{path} does not exist"],
                "written": None, "old_session": None}
    problems = []
    header = HANDOVER_HEADER.fullmatch(first_line(text))
    written = old = None
    if not header:
        problems.append("first line is not the lab:steward-handover:v1 header")
    else:
        written, old = header.group("written"), header.group("old")
        if header.group("id") != handover_id:
            problems.append(f"header id {header.group('id')} is not this handover's {handover_id}")
        try:
            if parse_time(written) <= parse_time(since):
                problems.append(f"written={written} is not after the request at {since}")
        except ValueError:
            problems.append(f"written={written} is not a time")
    headings = {line.strip().lstrip("#").strip()
                for line in text.splitlines() if line.lstrip().startswith("#")}
    for heading in HANDOVER_HEADINGS:
        if heading not in headings:
            problems.append(f"missing heading: {heading}")
    return {"ok": not problems, "present": True, "problems": problems,
            "written": written, "old_session": old}


def request_text(state_dir: Path, handover_id: str, old_session: str, threshold: int) -> str:
    path = handover_path(state_dir)
    headings = "\n".join(f"## {heading}" for heading in HANDOVER_HEADINGS)
    return (
        f"steward-wake: handover {handover_id}. Your context has passed {threshold:,} tokens, "
        f"so this session hands over now ({CELL}, 'The handover'). Write {path} and then "
        "end your turn without starting anything else. Its first line is exactly:\n"
        f"<!-- lab:steward-handover:v1 id={handover_id} old_session={old_session} "
        "written=<the UTC time you write it, YYYY-MM-DDTHH:MM:SSZ> -->\n"
        f"followed by these four headings:\n{headings}\n"
        f"Under each, put only what {FOUR_RECORDS} do not already carry -- work in progress, "
        "promises with their deadlines, any running task with its output path, and the "
        "owner's in-session words not yet recorded, verbatim -- or the word none. "
        "After your turn ends the mod checks the file, clears this session in place and "
        "queues a turn that resumes from it."
    )


def resume_text(state_dir: Path, handover_id: str, old_session: str | None,
                intervened_since: str | None, check: dict | None = None) -> str:
    path = handover_path(state_dir)
    lines = [
        f"steward-wake: resume from handover {handover_id}. This session was cleared to keep "
        f"the Steward's context small. Read {CELL}, then read the state file {path}.",
        f"Confirm each item in it against {FOUR_RECORDS}, and record anything you cannot "
        "confirm. Then take up keeping the owner board current.",
        f"The old conversation is {old_session or 'unknown'}; \"Resume previous session\" "
        "retrieves it.",
    ]
    if intervened_since:
        lines.append(
            f"A turn ran after the state file was written ({intervened_since}) and before the "
            f"clear: read that last exchange in conversation {old_session or 'unknown'}.")
    if check is not None and not check.get("ok"):
        lines.append(
            "The state file failed its check (" + "; ".join(check.get("problems", []))
            + "). Rebuild what you owe from the old conversation before anything else.")
    return "\n".join(lines)


def refusal_text(state_dir: Path, reason: str) -> str:
    return (
        f"steward-wake: the in-place clear was refused ({reason}). Ask the owner, in your reply "
        "and on the owner board, to type /clear in this session. Until he does, the wake keeps "
        f"running: before ending every turn, bring {handover_path(state_dir)} up to date and "
        "rewrite its written= time. When /clear arrives the mod resumes from that file.")


UPDATE_NOTE = (
    "steward-wake: a handover is waiting on the owner's /clear. Before ending this turn, "
    "bring the state file {path} up to date and rewrite its written= time.")


def handover_step(state_dir: Path, event: str, now: datetime, *, session: str = "unknown",
                  reason: str = "", last_turn_start: str | None = None,
                  threshold: int = HANDOVER_TOKENS) -> dict:
    """Advance the handover's state machine by one event and name the mod's action."""
    path = state_dir / "handover-state.json"
    state = handover_state(state_dir)
    current = state.get("state", "idle")

    def result(action: str, text: str = "", status: str = "") -> dict:
        return {"action": action, "text": text, "status": status,
                "state": state.get("state", "idle")}

    def abandon(why: str) -> dict:
        state.clear()
        state.update({"state": "idle", "abandoned_at": iso(now), "abandoned_why": why})
        write_json_atomic(path, state)
        return result("none", status=f"handover abandoned: {why}; not retried for an hour")

    if event == "load":
        if current == "active":
            return abandon("the mod reloaded mid-handover")
        return result("none")

    if event == "gate-yes":
        if current != "idle":
            return result("none")
        abandoned = state.get("abandoned_at")
        if abandoned and (now - parse_time(abandoned)).total_seconds() < RETRY_HOLD_SECONDS:
            return result("none", status="handover held after an abandoned attempt")
        target = handover_path(state_dir)
        if target.exists():
            os.replace(target, state_dir / "handover.prev.md")
        handover_id = now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
        state.clear()
        state.update({"state": "active", "id": handover_id, "requested_at": iso(now),
                      "old_session": session})
        write_json_atomic(path, state)
        return result("submit", request_text(state_dir, handover_id, session, threshold),
                      status=f"handover {handover_id} requested")

    if event in ("turn-settled", "tick"):
        if current != "active":
            return result("none")
        requested = parse_time(state["requested_at"])
        if state.get("clear_at"):
            if (now - parse_time(state["clear_at"])).total_seconds() > CLEAR_WAIT_SECONDS:
                return handover_step(state_dir, "clear-timeout", now, session=session)
            return result("none")
        check = handover_check(state_dir, state["id"], state["requested_at"])
        if check["ok"]:
            state["clear_at"] = iso(now)
            write_json_atomic(path, state)
            return result("clear", status=f"handover {state['id']}: clearing")
        if check["present"] and event == "turn-settled":
            return abandon("the state file failed its check: " + "; ".join(check["problems"]))
        if (now - requested).total_seconds() > STATE_FILE_WAIT_SECONDS:
            return abandon("no valid state file within 15 minutes")
        return result("none")

    if event in ("clear-rejected", "clear-timeout"):
        if current != "active":
            return result("none")
        why = reason or ("no /clear arrived within 120 s" if event == "clear-timeout"
                         else "the clear command was rejected")
        state["state"] = "awaiting-clear"
        state["refused"] = why
        state.pop("clear_at", None)
        write_json_atomic(path, state)
        return result("submit", refusal_text(state_dir, why),
                      status="handover waiting on the owner's /clear")

    if event == "prompt":
        if current == "awaiting-clear":
            return result("note", UPDATE_NOTE.format(path=handover_path(state_dir)))
        return result("none")

    if event == "session-end-clear":
        if current not in ("active", "awaiting-clear"):
            return result("none")
        check = handover_check(state_dir, state["id"], state["requested_at"])
        intervened = None
        if last_turn_start and check.get("written"):
            try:
                if parse_time(last_turn_start) > parse_time(check["written"]):
                    intervened = check["written"]
            except ValueError:
                intervened = None
        text = resume_text(state_dir, state["id"], check.get("old_session") or state.get("old_session"),
                           intervened, check)
        finished = state["id"]
        state.clear()
        state.update({"state": "idle", "last_handover": finished, "resumed_at": iso(now)})
        write_json_atomic(path, state)
        return result("submit", text, status=f"handover {finished}: resumed")

    raise WatchError(f"unknown handover event: {event}")


# ---------------------------------------------------------------- cover (row 4)


def alerted_keys(alert_comments: list[dict]) -> set[str]:
    keys: set[str] = set()
    for comment in alert_comments:
        if (comment.get("user") or {}).get("login") != ALERT_BOT:
            continue
        match = ALERT_MARKER.fullmatch(first_line(comment.get("body")))
        if match:
            keys.update(match.group("items").split(","))
    return keys


def waiting_items(page: Page, mark: dict, merges: list[dict], alerted: set[str],
                  now: datetime) -> list[str]:
    items = []
    for comment in page.intake(mark["handled"]):
        age = (now - parse_time(comment["created_at"])).total_seconds()
        if age > INTAKE_WAIT_SECONDS:
            items.append(f"intake:{comment['id']}")
    due = read_due(merges)
    number = mark["read"] + 1
    if (due is not None and (now - parse_time(due)).total_seconds() > READ_WAIT_SECONDS
            and mark["read"] < number and not page.read_note_exists(number)):
        items.append(f"read:{number}")
    return [item for item in items if item not in alerted]


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_lock(state_dir: Path, now: datetime) -> Path:
    """Refuse a second live run; replace a lock whose run is dead or too old."""
    state_dir.mkdir(parents=True, exist_ok=True)
    lock = state_dir / "cover.lock"
    record = json.dumps({"pid": os.getpid(), "started": iso(now)}).encode("ascii")
    for _ in range(2):
        try:
            handle = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            held = read_json(lock, {}) if lock.exists() else {}
            started = held.get("started")
            age = (now - parse_time(started)).total_seconds() if started else LOCK_STALE_SECONDS + 1
            if pid_alive(int(held.get("pid", 0))) and age <= LOCK_STALE_SECONDS:
                raise WatchError(f"another cover run holds {lock} (pid {held.get('pid')})")
            try:
                os.unlink(lock)
            except FileNotFoundError:
                pass
            continue
        with os.fdopen(handle, "wb") as stream:
            stream.write(record)
        return lock
    raise WatchError(f"could not take {lock}")


def cover(github: GitHub, state_dir: Path, page_number: int, now: datetime, *,
          dry_run: bool = False, repos: list[str] | None = None,
          probe_hold: float = 0, probe_hang: bool = False) -> dict:
    lock = acquire_lock(state_dir, now)
    outcome: dict = {"schema_version": 1, "at": iso(now), "dry_run": dry_run,
                     "reach": {}, "waiting": [], "dispatched": [], "error": None}
    try:
        try:
            page = load_page(github, page_number)
            _, mark = page.watermark()
            merges, outcome["reach"] = read_merges(github, mark["cutoff"], repos or lab_repos())
            alerted = alerted_keys(github.comments(LAB_REPO, mark["alerts"]))
            fresh = waiting_items(page, mark, merges, alerted, now)
            outcome["waiting"] = fresh
            if probe_hang:
                time.sleep(24 * 3600)
            if probe_hold:
                time.sleep(probe_hold)
            failed = [r for r, v in outcome["reach"].items() if not v.startswith("ok")]
            if failed:
                raise WatchError("read failed for " + ", ".join(sorted(failed)))
            if fresh and not dry_run:
                github.dispatch_alert(mark["alerts"], fresh)
                outcome["dispatched"] = fresh
        except WatchError as exc:
            outcome["error"] = str(exc)
        if not dry_run:
            write_json_atomic(state_dir / "cover-last-run.json", outcome)
            if outcome["error"] is None:
                write_json_atomic(state_dir / "cover-last-success.json",
                                  {"schema_version": 1, "at": iso(now)})
        return outcome
    finally:
        try:
            os.unlink(lock)
        except FileNotFoundError:
            pass


def alert_body(page: int, items: list[str]) -> str:
    lines = [f"<!-- lab:steward-alert:v1 items={','.join(items)} -->",
             f"@{OWNER_LOGIN} the Steward hasn't answered lab work:", ""]
    base = f"https://github.com/{LAB_REPO}/issues/{page}"
    for item in items:
        kind, number = item.split(":")
        if kind == "intake":
            lines.append(f"- `{item}`: {base}#issuecomment-{number}")
        elif kind == "read":
            lines.append(f"- `{item}`: read {number} is due, {base}")
        else:
            lines.append(f"- `{item}`: a probe of this alert route; nothing is waiting")
    return "\n".join(lines) + "\n"


def post_alert(github: GitHub, issue: str, items: str, page: int) -> dict:
    if not issue.isdigit():
        raise WatchError(f"alert issue {issue!r} is not a number")
    if not ITEMS.fullmatch(items):
        raise WatchError(f"items {items!r} is not a comma list of intake:N, read:N or probe:N")
    target = github.get(f"repos/{LAB_REPO}/issues/{issue}")
    if first_line(target.get("body")) != ALERTS_ISSUE_MARKER:
        raise WatchError(f"issue {issue} does not open with {ALERTS_ISSUE_MARKER}")
    keys = items.split(",")
    posted = github.send("POST", f"repos/{LAB_REPO}/issues/{issue}/comments",
                         {"body": alert_body(page, keys)})
    return {"posted": (posted or {}).get("html_url"), "items": keys}


def xml_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def task_xml(interpreter: str, script: str, arguments: str, working_dir: str, *,
             start: datetime, interval: str = "PT1H", limit: str = "PT5M",
             end: datetime | None = None) -> str:
    """The cover's Task Scheduler definition: no window, no overlap, a time limit."""
    expiry = ""
    delete_after = ""
    if end is not None:
        expiry = f"      <EndBoundary>{end.strftime('%Y-%m-%dT%H:%M:%S')}</EndBoundary>\n"
        delete_after = "    <DeleteExpiredTaskAfter>PT0S</DeleteExpiredTaskAfter>\n"
    command_args = f'"{script}" cover {arguments}'.strip()
    return (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
        "  <RegistrationInfo>\n"
        "    <Description>tradecraft lab: alert the owner when the Steward has left lab work "
        "unanswered (#890). No model runs.</Description>\n"
        "  </RegistrationInfo>\n"
        "  <Triggers>\n"
        "    <TimeTrigger>\n"
        f"      <StartBoundary>{start.strftime('%Y-%m-%dT%H:%M:%S')}</StartBoundary>\n"
        f"{expiry}"
        "      <Repetition>\n"
        f"        <Interval>{interval}</Interval>\n"
        "        <StopAtDurationEnd>false</StopAtDurationEnd>\n"
        "      </Repetition>\n"
        "      <Enabled>true</Enabled>\n"
        "    </TimeTrigger>\n"
        "  </Triggers>\n"
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
        f"{delete_after}"
        "    <Enabled>true</Enabled>\n"
        "  </Settings>\n"
        '  <Actions Context="Author">\n'
        "    <Exec>\n"
        f"      <Command>{xml_escape(interpreter)}</Command>\n"
        f"      <Arguments>{xml_escape(command_args)}</Arguments>\n"
        f"      <WorkingDirectory>{xml_escape(working_dir)}</WorkingDirectory>\n"
        "    </Exec>\n"
        "  </Actions>\n"
        "</Task>\n"
    )


def windowless_interpreter() -> str:
    candidate = Path(sys.executable).with_name("pythonw.exe")
    return str(candidate if candidate.exists() else Path(sys.executable))


def schtasks(args: list[str]) -> str:
    proc = subprocess.run(["schtasks.exe", *args], stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=60, creationflags=_no_window())
    out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        raise WatchError(f"schtasks {args[0]} exited {proc.returncode}: {out}")
    return out


# ---------------------------------------------------------------- the Steward's commands


def post(github: GitHub, page: int, kind: str, read: int | None, body: str) -> dict:
    if kind == "read-note" and read is None:
        raise WatchError("a read-note needs --read N")
    if kind == "post" and read is not None:
        raise WatchError("--read applies to read-note only")
    attrs = {"read": read} if kind == "read-note" else {}
    text = marker_line(kind, **attrs) + "\n" + body.lstrip(BOM)
    posted = github.send("POST", f"repos/{LAB_REPO}/issues/{page}/comments", {"body": text})
    return {"posted": (posted or {}).get("html_url"), "id": (posted or {}).get("id")}


def update_watermark(github: GitHub, page: Page, **changes) -> dict:
    comment, mark = page.watermark()
    fields = {k: mark[k] for k in ("handled", "read", "cutoff", "alerts")}
    fields.update(changes)
    github.send("PATCH", f"repos/{LAB_REPO}/issues/comments/{comment['id']}",
                {"body": watermark_body(**fields)})
    return fields


def handled(github: GitHub, page_number: int, comment_id: int) -> dict:
    page = load_page(github, page_number)
    _, mark = page.watermark()
    ids = {int(c["id"]) for c in page.comments}
    if comment_id not in ids:
        raise WatchError(f"{comment_id} is not a comment on {LAB_REPO}#{page_number}")
    if comment_id < mark["handled"]:
        raise WatchError(f"{comment_id} is below the watermark's handled={mark['handled']}")
    covered = [{"id": int(c["id"]), "link": page.link(int(c["id"])),
                "first_line": first_line(c.get("body"))[:120]}
               for c in page.intake(mark["handled"]) if int(c["id"]) <= comment_id]
    fields = update_watermark(github, page, handled=comment_id)
    return {"watermark": fields, "newly_handled": covered}


def read_recorded(github: GitHub, page_number: int, read: int, cutoff: str) -> dict:
    page = load_page(github, page_number)
    _, mark = page.watermark()
    if read < mark["read"]:
        raise WatchError(f"read {read} is below the watermark's read={mark['read']}")
    stamp = iso(parse_time(cutoff))
    return {"watermark": update_watermark(github, page, read=read, cutoff=stamp)}


def seed(github: GitHub, page_number: int, handled_id: int, read: int, cutoff: str,
         alerts: int) -> dict:
    page = load_page(github, page_number)
    existing = [c for c in page.comments
                if (page.marks[int(c["id"])] or {}).get("kind") == "watermark"]
    if existing:
        raise WatchError(f"{LAB_REPO}#{page_number} already carries a watermark comment")
    body = watermark_body(handled_id, read, iso(parse_time(cutoff)), alerts)
    posted = github.send("POST", f"repos/{LAB_REPO}/issues/{page_number}/comments", {"body": body})
    return {"posted": (posted or {}).get("html_url")}


def status(github: GitHub, state_dir: Path, page_number: int, now: datetime) -> dict:
    page = load_page(github, page_number)
    _, mark = page.watermark()
    merges, reach = read_merges(github, mark["cutoff"], lab_repos())
    return {
        "watermark": mark,
        "intake": [{"id": int(c["id"]), "link": page.link(int(c["id"])),
                    "created_at": c.get("created_at")} for c in page.intake(mark["handled"])],
        "read": {"next": mark["read"] + 1, "merges_after_cutoff": len(merges),
                 "due_since": read_due(merges)},
        "reach": reach,
        "cover": cover_state(state_dir, now),
        "handover": handover_state(state_dir),
    }


def config(state_dir: Path, page: int, env_values: dict[str, str]) -> dict:
    given = {k: v for k, v in env_values.items() if v not in (None, "")}
    unknown = sorted(set(given) - set(PROBE_ENV))
    if unknown:
        raise WatchError("unknown setting(s): " + ", ".join(unknown))
    refuse_probe_against_default(state_dir, list(given) + (["--page"] if page != STANDING_PAGE else []))

    def number(name: str, default: int) -> int:
        return int(given[name]) if name in given else default

    page_value = number("STEWARD_WAKE_PAGE", page)
    if page_value != STANDING_PAGE:
        refuse_probe_against_default(state_dir, ["STEWARD_WAKE_PAGE"])
    return {
        "schema_version": 1,
        "state_dir": str(state_dir),
        "default_state_dir": is_default_dir(state_dir),
        "page": page_value,
        "tick_seconds": number("STEWARD_WAKE_TICK_SECONDS", 300),
        "handover_tokens": number("STEWARD_WAKE_HANDOVER_TOKENS", HANDOVER_TOKENS),
        "owner_quiet_seconds": number("STEWARD_WAKE_OWNER_QUIET_SECONDS", OWNER_QUIET_SECONDS),
        "settle_seconds": number("STEWARD_WAKE_SETTLE_SECONDS", SETTLE_SECONDS),
        "simulate_clear_refused": given.get("STEWARD_WAKE_SIMULATE_CLEAR_REFUSED", "") not in ("", "0"),
    }


# ---------------------------------------------------------------- command line


def emit(value) -> None:
    if sys.stdout is not None:
        sys.stdout.write(json.dumps(value, ensure_ascii=True, sort_keys=True) + "\n")
        sys.stdout.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="The Steward's signal, wake, handover and cover (tradecraft #890).")
    sub = parser.add_subparsers(dest="command", required=True)

    def command(name: str, help_text: str) -> argparse.ArgumentParser:
        one = sub.add_parser(name, help=help_text, description=help_text)
        one.add_argument("--state-dir", help="local state directory (default: the "
                         f"{STATE_ENV} variable, else ~/.tradecraft-lab/steward)")
        one.add_argument("--page", type=int, default=STANDING_PAGE,
                         help="standing page issue number; anything but 683 is probe-only")
        return one

    one = command("config", "resolve the mod's settings; probe-only ones are refused "
                  "against the default state directory")
    one.add_argument("--env", action="append", default=[], metavar="NAME=VALUE")
    one = command("post", "post a Steward-marked comment on the page")
    one.add_argument("--kind", choices=("post", "read-note"), required=True)
    one.add_argument("--read", type=int)
    one.add_argument("--body-file", required=True)
    one = command("handled", "move the watermark's handled id forward")
    one.add_argument("comment_id", type=int)
    one = command("read-recorded", "record the last read and its cutoff in the watermark")
    one.add_argument("--read", type=int, required=True)
    one.add_argument("--cutoff", required=True)
    command("status", "print the watermark, intake, read and cover state")
    one = command("seed", "create the page's watermark comment (install only)")
    one.add_argument("--handled", type=int, required=True)
    one.add_argument("--read", type=int, required=True)
    one.add_argument("--cutoff", required=True)
    one.add_argument("--alerts", type=int, required=True)
    command("wake", "list new triggers for the mod")
    one = command("mark-woken", "record that a trigger has woken the Steward")
    one.add_argument("key")
    one = command("origin-is-owner", "say whether a prompt origin counts as the owner")
    one.add_argument("kind")
    one.add_argument("--record", action="store_true")
    one = command("handover-due", "evaluate the handover gate")
    for flag in ("--tokens", "--since-turn-complete", "--background-tasks", "--crons",
                 "--agents-busy", "--since-owner"):
        one.add_argument(flag, type=float, required=flag in ("--tokens",
                         "--since-turn-complete", "--since-owner"), default=0)
    one.add_argument("--turn-running", type=int, choices=(0, 1), default=0)
    one.add_argument("--turn-started-since", type=int, choices=(0, 1), default=0)
    one.add_argument("--skip-token-test", action="store_true")
    one.add_argument("--handover-tokens", type=int)
    one.add_argument("--owner-quiet-seconds", type=int)
    one.add_argument("--settle-seconds", type=int)
    one = command("handover-step", "advance the handover state machine")
    one.add_argument("--event", required=True, choices=(
        "load", "gate-yes", "turn-settled", "tick", "clear-rejected", "clear-timeout",
        "prompt", "session-end-clear"))
    one.add_argument("--session", default="unknown")
    one.add_argument("--reason", default="")
    one.add_argument("--last-turn-start")
    one.add_argument("--handover-tokens", type=int)
    one = command("handover-check", "check the state file for one handover")
    one.add_argument("--id", required=True)
    one.add_argument("--since", required=True)
    one = command("resume-text", "print the resume prompt for one handover")
    one.add_argument("--id", required=True)
    one.add_argument("--old-session")
    one.add_argument("--intervened-since")
    one = command("cover", "the hourly cover run")
    one.add_argument("--dry-run", action="store_true")
    one.add_argument("--probe-hold", type=float, help="probe only: sleep this long mid-run")
    one.add_argument("--probe-hang", action="store_true", help="probe only: hang mid-run")
    one = command("post-alert", "post the bot alert (run by the steward-alert workflow)")
    one.add_argument("--issue", required=True)
    one.add_argument("--items", required=True)
    one = command("cover-task", "print, register or unregister the hourly cover task")
    action = one.add_mutually_exclusive_group(required=True)
    action.add_argument("--xml", action="store_true")
    action.add_argument("--register", action="store_true")
    action.add_argument("--unregister", action="store_true")
    one.add_argument("--name", default=TASK_NAME)
    one.add_argument("--args", default="", help="extra cover arguments; a probe's must "
                     "carry --state-dir")
    one.add_argument("--interval", default="PT1H")
    one.add_argument("--limit", default="PT5M")
    one.add_argument("--expire-minutes", type=int)
    one.add_argument("--interpreter")
    return parser


def probe_settings(args: argparse.Namespace) -> list[str]:
    found = []
    if args.page != STANDING_PAGE:
        found.append("--page")
    for name in ("probe_hold", "probe_hang", "handover_tokens", "owner_quiet_seconds",
                 "settle_seconds"):
        if getattr(args, name, None) not in (None, False):
            found.append("--" + name.replace("_", "-"))
    if args.command == "cover-task" and (args.name != TASK_NAME or args.args
                                         or args.expire_minutes is not None
                                         or args.interval != "PT1H" or args.limit != "PT5M"):
        found.append("cover-task probe options")
    return found


def run(args: argparse.Namespace, github: GitHub | None = None,
        now: datetime | None = None) -> object:
    state_dir = resolve_state_dir(args.state_dir)
    now = now or now_utc()
    if args.command == "config":
        values = dict(item.split("=", 1) for item in args.env if "=" in item)
        return config(state_dir, args.page, values)
    refuse_probe_against_default(state_dir, probe_settings(args))
    deadline = time.monotonic() + COVER_DEADLINE_SECONDS if args.command == "cover" else None
    github = github or GitHub(deadline=deadline)
    page = args.page
    if args.command == "post":
        body = Path(args.body_file).read_bytes().decode("utf-8")
        return post(github, page, args.kind, args.read, body)
    if args.command == "handled":
        return handled(github, page, args.comment_id)
    if args.command == "read-recorded":
        return read_recorded(github, page, args.read, args.cutoff)
    if args.command == "status":
        return status(github, state_dir, page, now)
    if args.command == "seed":
        return seed(github, page, args.handled, args.read, args.cutoff, args.alerts)
    if args.command == "wake":
        return wake(github, state_dir, page, now)
    if args.command == "mark-woken":
        mark_woken(state_dir, page, args.key)
        return {"marked": page_scope(page) + args.key}
    if args.command == "origin-is-owner":
        owner = origin_is_owner(args.kind)
        if args.record:
            record_origin(state_dir, args.kind, owner, now)
        return {"kind": args.kind, "owner": owner}
    if args.command == "handover-due":
        facts = {
            "tokens": args.tokens, "threshold": args.handover_tokens or HANDOVER_TOKENS,
            "skip_tokens": args.skip_token_test, "turn_running": bool(args.turn_running),
            "since_turn_complete": args.since_turn_complete,
            "turn_started_since": bool(args.turn_started_since),
            "settle": args.settle_seconds if args.settle_seconds is not None else SETTLE_SECONDS,
            "background_tasks": args.background_tasks, "crons": args.crons,
            "agents_busy": args.agents_busy, "since_owner": args.since_owner,
            "owner_quiet": (args.owner_quiet_seconds if args.owner_quiet_seconds is not None
                            else OWNER_QUIET_SECONDS),
            "disabled": (state_dir / "handover-disabled").exists(),
        }
        return handover_due(facts)
    if args.command == "handover-step":
        return handover_step(state_dir, args.event, now, session=args.session,
                             reason=args.reason, last_turn_start=args.last_turn_start,
                             threshold=args.handover_tokens or HANDOVER_TOKENS)
    if args.command == "handover-check":
        return handover_check(state_dir, args.id, args.since)
    if args.command == "resume-text":
        check = handover_check(state_dir, args.id, "1970-01-01T00:00:00Z")
        old = args.old_session or check.get("old_session") or handover_state(state_dir).get("old_session")
        return {"text": resume_text(state_dir, args.id, old, args.intervened_since)}
    if args.command == "cover":
        return cover(github, state_dir, page, now, dry_run=args.dry_run,
                     probe_hold=args.probe_hold or 0, probe_hang=args.probe_hang)
    if args.command == "post-alert":
        return post_alert(github, args.issue, args.items, page)
    if args.command == "cover-task":
        return cover_task(args, state_dir, now)
    raise WatchError(f"unknown command {args.command}")


def cover_task(args: argparse.Namespace, state_dir: Path, now: datetime) -> dict:
    if args.name != TASK_NAME and "--state-dir" not in args.args:
        raise WatchError("a probe task's --args must carry --state-dir")
    if args.unregister:
        return {"unregistered": args.name, "output": schtasks(["/Delete", "/TN", args.name, "/F"])}
    local_start = datetime.now().replace(microsecond=0) + timedelta(minutes=1)
    end = local_start + timedelta(minutes=args.expire_minutes) if args.expire_minutes else None
    xml = task_xml(args.interpreter or windowless_interpreter(), str(Path(__file__).resolve()),
                   args.args, str(ROOT), start=local_start, interval=args.interval,
                   limit=args.limit, end=end)
    if args.xml:
        return {"xml": xml}
    handle, temp = tempfile.mkstemp(suffix=".xml")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(xml.encode("utf-16"))
        output = schtasks(["/Create", "/TN", args.name, "/XML", temp, "/F"])
    finally:
        os.unlink(temp)
    return {"registered": args.name, "output": output}


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        value = run(args)
    except WatchError as exc:
        emit({"schema_version": 1, "error": str(exc)})
        return 2
    emit(value)
    if isinstance(value, dict) and value.get("error"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

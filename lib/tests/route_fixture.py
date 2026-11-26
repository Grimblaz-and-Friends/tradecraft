"""Stand-in states of one product change on the builder route, and what the built entrance prints for each.

A holder's use session runs this from an exported copy of the tree, under `python -B`. `--list`
names the scenarios; a scenario's name puts the practice in that state and prints the read-only
decision's report as the entrance prints it, then any composed text the scenario is about.

Each run makes its own temporary home, record store and temporary folder and removes them after:
no real home or store is read or written, no socket may connect, and no `gh` runs, because the
entrance's GitHub is an in-process stand-in serving the scenario's issue records. Every launch
record is written by the launchers' own writers, so the state is the shape they write.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid

LIB = Path(__file__).resolve().parents[1]
REPO, ISSUE, PRODUCER = "o/r", 5, "producer"
WORK = f"{REPO}#{ISSUE}"
START = datetime(2026, 11, 1, tzinfo=timezone.utc)
FLOOR = "python -B -m pytest -q"
RULES = {"schema_version": 1, "rules": [{"name": "fixture", "include": ["job/**"], "exclude": []}]}
# Each brief carries a Shape sentence, because the handoff's stop rule is worded on what it says the change is.
BRIEF = ("<!-- tradecraft:affirmed-brief:v1 -->\n\n**Shape:** a job an adopter runs, built and proved by use.\n\n"
         "## Purpose\n\nA stand-in product change whose job an adopter runs.\n\n"
         "| Row | Outcome |\n|---|---|\n| 1 | The job runs as an adopter would run it. |\n\n"
         "Review risk: ordinary\nReview lane: connected\n")
PLAN = ("\n## Plan\n\nBuild row 1 and prove it by use.\n\n"
        "## Use session job\n\n```text\nUse the job as an adopter would.\n```\n\n"
        "## Consumer tree declaration use\n\n"
        "```json\n{\"mode\": \"adopter\", \"paths\": [\"job\"], \"loading_surfaces\": [\"skill/SKILL.md\"]}\n```\n\n"
        "## Criteria\n\n**C1.** Row 1 is built. *Check:* a test.\n\n"
        "**C2.** The job runs.\nFresh reader: execute consumer tree use\n")
# The owner-affirmed mechanical lane: a determinate correction in rows, with no plan owed.
MECHANICAL_BRIEF = ("<!-- tradecraft:affirmed-brief:v1 -->\nReview risk: ordinary\nReview lane: mechanical\n\n"
                    "**Shape:** seven of the job's lines corrected as written, and nothing else.\n\n"
                    "## Purpose\n\nA stand-in correction to the job's wording.\n\n## Rows\n\n"
                    + "".join(f"**{number}. The job's line {number} reads as corrected.** It says what it does.\n\n"
                              for number in range(1, 8)))
QUOTED = "\n" + "\n".join("> " + line for line in BRIEF.splitlines())
DRAFT = "<!-- tradecraft:artifact:v1 status=draft -->" + QUOTED + PLAN
# Settled where no cold seat could be obtained, so the settlement stands without a seat's bundle.
SETTLED = "<!-- tradecraft:artifact:v1 status=settled route=unobtainable -->" + QUOTED + PLAN
HOLDER_READING = "<!-- tradecraft:holder-reading:v1 result=no-amendment -->"
RELAY_ASK = "<!-- tradecraft:route:v1 route=relay -->\n\n> Take this one by today's route.\n"
CLEAR = {"behind": False, "strict": False, "conflict": False, "mergeability_known": True,
         "merge_state": "clean", "uncertainties": []}
USE_RETURN = "The job ran and printed one warning.\n\nFindings:\nF1. The job printed a stray warning.\n"
SAME_VENDOR = "owner-selected-claude-implementer"
# The holder's session a handoff records, in a stretch's request or a hand record; no transcript of it exists.
HOLDER_SESSION = "fixture-holder-session"

SCENARIOS = {
    "handoff-due": "an affirmed brief and a settled plan, nothing launched",
    "handoff": "the same state, with the handoff the entrance composes for its builder (--mechanical: a "
               "seven-row brief on the mechanical lane and no plan)",
    "with-builder": "a live stretch launch of the change",
    "stretch-stopped": "a completed stretch and no readiness record",
    "cannot-launch": "a stopped readiness record whose builder could not launch a check",
    "final-pass": "a ready readiness record at the head, with one counting use report reconciled",
    "ready-reported": "a launched builder's ready record, reach read from Git, then the release report's payload",
    "catch-up": "the ready record at the head after the base moved",
    "relay-in-flight": "a first build launch, so today's relay chain",
    "owner-asked-relay": "the owner's route=relay marker, nothing launched",
    "hand-started": "a builder the owner started by hand, its record still open",
    "launch-account-held": "a completed stretch launched under a write bound whose comparison no launch-account names",
    "watch-ready": "a launched builder's stand-in, some hours into the stretch's default limit, watched by the "
                   "holder's wait until it ends ready",
    "watch-stopped": "the same, until the stand-in's run ends failed",
    "watch-limit": "the same, until its launcher stops it at that limit",
    "watch-crash": "the same, until the stand-in dies without completing its record",
    "watch-replay": "the same, the stand-in appending the recorded-form log tests/fixtures/builder-stream.jsonl line by "
                    "line, until it ends ready",
    "watch-hand": "a builder the owner started by hand, its record open, and the wait run against it",
    "watch-none": "no builder running, one earlier stretch completed, and the wait run against it",
}
WATCHED = {"watch-ready": "ready", "watch-stopped": "stopped", "watch-limit": "limit", "watch-crash": "crash",
           "watch-replay": "ready"}
# The stand-in reaches its limit this many seconds after it starts, in the middle of its quiet span.
LIMIT_AT = 18.0
STAND_IN_RUNNING_SECONDS = 7200.0
REPLAY_LOG = Path("fixtures") / "builder-stream.jsonl"


def _refused_connection(*_args, **_kwargs):
    raise OSError("route_fixture: no network; the fixture's GitHub is in-process")


def isolate(base: Path) -> None:
    """Point this process's home, temporary folder and Git at ``base`` before any practice module loads."""
    home, temp = base / "home", base / "temp"
    home.mkdir()
    temp.mkdir()
    # The machine's builder is Claude, as every stand-in launch record is, so the decision's launch plan names the
    # launched builder whose handoff the `handoff` scenario prints; with no machine file it would be Codex, by hand.
    (home / ".tradecraft").mkdir()
    (home / ".tradecraft" / "implementer-vendor").write_bytes(b"claude")
    os.environ["HOME"] = os.environ["USERPROFILE"] = str(home)
    for name in ("TMPDIR", "TEMP", "TMP"):
        os.environ[name] = str(temp)
    tempfile.tempdir = str(temp)
    # No caller's session, stretch launch or Claude settings may be read as this fixture's.
    for name in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_CONFIG_DIR", "TRADECRAFT_STRETCH_DISPATCH",
                 "TRADECRAFT_STRETCH_WORK", "TRADECRAFT_STRETCH_JOB"):
        os.environ.pop(name, None)
    count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
    os.environ[f"GIT_CONFIG_KEY_{count}"] = "maintenance.auto"
    os.environ[f"GIT_CONFIG_VALUE_{count}"] = "false"
    os.environ["GIT_CONFIG_COUNT"] = str(count + 1)
    socket.socket.connect = _refused_connection
    socket.create_connection = _refused_connection


class Fixture:
    """One scenario's issue, store and holder checkout, and the entrance's report of them."""

    def __init__(self, base: Path, *, mechanical: bool = False):
        sys.path.insert(0, str(LIB))
        import work
        import dispatch_record as records
        import launch_tree
        import run_lifecycle as lifecycle
        self.work, self.records, self.launch_tree, self.lifecycle = work, records, launch_tree, lifecycle
        self.base = base
        self.store = records.default_record_root()
        self.holder = base / "holder"
        (self.holder / ".github").mkdir(parents=True)
        (self.holder / ".github" / "change-proof.json").write_text(json.dumps(RULES), encoding="utf-8")
        self.comments = []
        self.pr = None
        self.synchronization = None
        self.children = []
        self.cold_reading_clean = False
        self.reports = []
        # The pull request's inline review comments and the reviewers configured to post them.
        self.review_comments = []
        self.connected_reviewers = frozenset()
        for text in ((MECHANICAL_BRIEF,) if mechanical else (BRIEF, DRAFT, SETTLED, HOLDER_READING)):
            self.post(text)

    def post(self, body: str) -> int:
        identity = 100 + len(self.comments)
        self.comments.append({"id": identity, "body": body, "user": {"login": PRODUCER},
                              "created_at": (START + timedelta(minutes=len(self.comments))).isoformat(),
                              "html_url": f"https://github.invalid/{REPO}/issues/{ISSUE}#issuecomment-{identity}"})
        return identity

    def pull_request(self, head: str, synchronization: dict) -> None:
        self.pr = {"number": 7, "state": "open", "draft": True, "merged_at": None, "mergeable": True,
                   "mergeable_state": "clean", "head": {"sha": head, "ref": "tradecraft/5-fixture"},
                   "base": {"ref": "main", "sha": "b" * 40}}
        self.synchronization = dict(synchronization)

    def state(self):
        work = self.work
        state = work.WorkState(REPO, ISSUE, {"number": ISSUE, "state": "open", "body": "", "labels": [],
                                             "user": {"login": PRODUCER}},
                               issue_comments=[dict(comment) for comment in self.comments], pr=self.pr,
                               review_comments=[dict(comment) for comment in self.review_comments],
                               config=work.WorkConfig(marker_producers=frozenset({PRODUCER}),
                                                      connected_reviewers=self.connected_reviewers),
                               record_root=self.store)
        state.synchronization = self.synchronization
        state.version_obligation = work._assess_version(state, RULES, "fixture change-proof policy", None)
        return state

    # --- launch records, each written by its launcher's own writers ---------------------------------

    def _request(self, stage: str, minutes: int, root=None, holder_session=None,
                 at: datetime | None = None) -> tuple[str, Path, dict]:
        dispatch_id = uuid.uuid4().hex
        request = self.records.request_record(
            dispatch_id=dispatch_id, work=WORK, stage=stage, settings_source="route fixture",
            settings_scope="implementer", vendor="claude", model="fixture", effort="fixture",
            continuity="fresh", permission_boundary="route fixture", root=root,
            now=at or START + timedelta(minutes=minutes), holder_session_id=holder_session)
        output = self.store / f"{stage}-{dispatch_id}" / "result.md"
        output.parent.mkdir(parents=True)
        return dispatch_id, output, request

    def completed(self, stage: str, minutes: int) -> str:
        """A bundle of STAGE launched MINUTES after the start and completed a minute later."""
        dispatch_id, output, request = self._request(stage, minutes)
        self.records.write_json(self.records.sidecar(output, ".request.json"), request)
        self.records.write_json(self.records.sidecar(output, ".run.json"), {
            "schema_version": self.records.SCHEMA_VERSION, "dispatch_id": dispatch_id, "lifecycle": "completed",
            "outcome": "success", "completed_at": (START + timedelta(minutes=minutes + 1)).isoformat()})
        return dispatch_id

    def bounded_stretch(self, minutes: int) -> str:
        """A completed stretch launched under a write bound whose run ended before its comparison was recorded.

        The bound is the one the seat launcher records when it has no file-tool guard to record, so the
        entrance owes the holder's launch-account for the unrecorded comparison before anything else.
        """
        import launch_bound
        dispatch_id, output, request = self._request("stretch", minutes, root=self.base / "implementation")
        request["write_bound"] = launch_bound.write_bound_record(
            file_tools=None, memory=launch_bound.memory_record(), comparison=None,
            comparison_error="the stand-in launch planned no comparison")
        self.records.write_json(self.records.sidecar(output, ".request.json"), request)
        self.records.write_json(self.records.sidecar(output, ".run.json"), {
            "schema_version": self.records.SCHEMA_VERSION, "dispatch_id": dispatch_id, "lifecycle": "completed",
            "outcome": "success", "completed_at": (START + timedelta(minutes=minutes + 1)).isoformat()})
        return dispatch_id

    def live_stretch(self) -> str:
        """A stretch whose launcher is a live child, so the decision reads it running and this process isn't its builder."""
        child = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(300)"],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.children.append(child)
        dispatch_id, output, request = self._request("stretch", 5, root=self.base / "implementation")
        request_path = self.records.sidecar(output, ".request.json")
        self.records.write_json(request_path, request)
        self.launch_tree.write_pointer(self.store, dispatch_id=dispatch_id, work=WORK, request=request_path,
                                       run=self.records.sidecar(output, ".run.json"), session_id=None,
                                       launcher=self.lifecycle.process_identity(child.pid),
                                       root=self.base / "implementation")
        return dispatch_id

    def watched_stretch(self, mode: str, replay: Path | None = None) -> dict:
        """A launched stretch whose launcher is the stand-in builder, live and writing its run record and log.

        Its request carries the stretch's default limit. It was launched some hours ago, so its lines show a
        builder well into its run as a holder sees one; for ``limit``, so that its limit falls ``LIMIT_AT`` seconds
        after it starts. The pointer is written once its run record
        exists, so the wait finds the launch whole.
        """
        now = datetime.now(timezone.utc)
        limit = self.work.DEFAULT_STRETCH_TIMEOUT_SECONDS
        launched = now - timedelta(seconds=limit - LIMIT_AT if mode == "limit" else STAND_IN_RUNNING_SECONDS)
        root = self.base / "implementation"
        dispatch_id, output, request = self._request("stretch", 0, root=root, holder_session=HOLDER_SESSION,
                                                     at=launched)
        request.update(handoff={"timeout_seconds": limit, "holder_root": str(self.holder),
                                "plugin_root": str(LIB.parent)}, caller_limit_seconds=limit)
        request_path, run_path = (self.records.sidecar(output, ".request.json"),
                                  self.records.sidecar(output, ".run.json"))
        log = self.records.sidecar(output, ".claude.stdout.log")
        read = self.records.sidecar(output, ".read")
        self.records.write_json(request_path, request)
        child = subprocess.Popen(
            [sys.executable, "-B", str(LIB / "tests" / "stand_in_builder.py"), "--run", str(run_path),
             "--dispatch", dispatch_id, "--log", str(log), "--mode", mode, "--launched", launched.isoformat(),
             *(["--limit-at", f"{LIMIT_AT:g}"] if mode == "limit" else []),
             "--hold-until", str(read),
             *(["--replay", str(replay)] if replay is not None else [])],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.children.append(child)
        end = time.monotonic() + 30
        while not run_path.is_file():
            if child.poll() is not None or time.monotonic() > end:
                raise RuntimeError("route fixture: the stand-in builder wrote no run record")
            time.sleep(0.1)
        self.launch_tree.write_pointer(self.store, dispatch_id=dispatch_id, work=WORK, request=request_path,
                                       run=run_path, session_id=None,
                                       launcher=self.lifecycle.process_identity(child.pid), root=root)
        return {"child": child, "dispatch_id": dispatch_id, "run": run_path, "log": log, "request": request_path,
                "read": read}

    def hand_stretch(self, tree: Path, *, owed: bool = False) -> dict:
        """A hand-started record whose handoff block is the one `run handoff --by-hand` writes, digest and the
        holder's session included.

        The scenarios' stand-in builder launches no cold reader or criterion reader, so its block leaves out the
        owed checks unless ``owed`` asks for them, as a release report reading what a record left owed does.
        """
        work = self.work
        hand = {"tree": str(tree), "branch": "tradecraft/5-fixture", "store": str(self.store),
                "dispatch": uuid.uuid4().hex}
        state = self.state()
        common = {"branch": hand["branch"], "holder_root": self.holder, "plugin_root": LIB.parent, "notify": None,
                  "floor_command": FLOOR}
        text = work.compose_handoff_for(state, **common, hand=hand)
        args = argparse.Namespace(floor_command=FLOOR, dispatch=None, notify=None, budget_override_reason=None)
        block = work._handoff_block(state, args, text, work.DEFAULT_STRETCH_TIMEOUT_SECONDS, common)
        block.update(hand, holder_session_id=HOLDER_SESSION)
        if not owed:
            del block["owed_checks"]
        return self.launch_tree.write_hand_record(self.store, work=WORK, vendor="claude", model="fixture",
                                                  now=START + timedelta(minutes=5), handoff=block)

    def source(self) -> tuple[Path, str]:
        """The change's built source: one committed job file, whose commit is the pull request's head."""
        root = self.base / "source"
        (root / "job").mkdir(parents=True)
        (root / ".gitattributes").write_bytes(b"* text=auto eol=lf\n")
        (root / "job" / "job.md").write_bytes(b"run the job\n")
        (root / "skill").mkdir()
        (root / "skill" / "SKILL.md").write_bytes(b"how an adopter loads the job\n")
        for words in (["init", "-q"], ["add", "--all"],
                      ["-c", "user.name=fixture", "-c", "user.email=fixture@invalid", "commit", "-q", "-m", "job"]):
            subprocess.run(["git", "-C", str(root), *words], check=True, capture_output=True, stdin=subprocess.DEVNULL)
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True,
                              stdin=subprocess.DEVNULL).stdout.decode("ascii").strip()
        return root.resolve(), head

    def use_report(self, state, source: Path, builder: str) -> tuple[int, str]:
        """The builder's use check as the entrance composes, records and posts it; its comment and dispatch."""
        work, records = self.work, self.records
        artifact, comment = work._settled_artifact_text(state, "artifact-use-job-absent")
        root, _metadata, claim = work._check_tree(state, source, artifact, comment, "use", builder)
        head = claim["source_revision"]
        dispatch = work.compose_check_dispatch("use", {"job": work.artifact_use_job(artifact), "head": head,
                                                       "tree": root})
        dispatch_id, output, request = self._request("use", 10, root=root)
        # What the seat launcher records of who launched it, read from the open hand-started record.
        request.update(self.launch_tree.attribution(self.store, dispatch=builder, origin="entrance"))
        records.write_json(records.sidecar(output, ".request.json"), request)
        records.write_bytes(records.sidecar(output, ".dispatch.bin"), dispatch)
        records.write_bytes(records.sidecar(output, ".source.bin"), USE_RETURN.encode("utf-8"))
        records.write_json(records.sidecar(output, ".run.json"), {
            "schema_version": records.SCHEMA_VERSION, "dispatch_id": dispatch_id, "lifecycle": "completed",
            "outcome": "success", "staffing_status": "degraded",
            "staffing_qualification": {"same_vendor_reason": SAME_VENDOR},
            "completed_at": (START + timedelta(minutes=11)).isoformat()})
        body = work.check_report_body(stage="use", head=head, tree="held", criterion=None, frame={
            "dispatch_id": dispatch_id, "dispatch_sha256": hashlib.sha256(dispatch).hexdigest(),
            "staffing_status": "degraded", "same_vendor_reason": SAME_VENDOR, "outcome": "success",
            "return": USE_RETURN.encode("utf-8")})
        return self.post(body), dispatch_id

    def readiness(self, builder: str, head: str, *, status: str = "ready", stop=None, checks=(), findings=(),
                  started_by: str = "launch") -> int:
        payload = {"schema_version": 1,
                   "builder": {"vendor": "claude", "model": "fixture", "started_by": started_by, "usage_log": None},
                   "checks": list(checks), "findings": list(findings), "rows": [], "decisions": [],
                   "refusals": [], "stop": stop}
        return self.post(f"<!-- tradecraft:readiness:v1 head={head} status={status} dispatch={builder} -->\n\n"
                         f"```json\n{json.dumps(payload, indent=2)}\n```\n")

    # --- the entrance ---------------------------------------------------------------------------------

    def decision(self, state) -> int:
        """The read-only decision as `work.py --repo --issue --root` prints it, over this scenario's state."""
        work = self.work

        class FixtureGitHub:
            """The entrance's GitHub in this process: the issue's records are the state, and nothing else is served."""

            def __getattr__(self, name):
                raise work.WorkError(f"route fixture: GitHub {name} is not served beyond the issue's records")

        work.GitHubREST = FixtureGitHub
        work._read_policy_state = lambda *_args, **_kwargs: state
        if self.cold_reading_clean:
            # The stand-in builder's cold reading stands clear, since no reader ran; so does reach where the fixture
            # keeps no Git history to read it by.
            work._cold_reading_decision = lambda *_args: None
            if self.cold_reading_clean != "reach-read":
                work._evaluate_reach = lambda checked: setattr(checked, "reach", {"state": "not-due"})
        emit, self.reports = work._emit_report, []

        def recorded(payload, *args, **kwargs):
            self.reports.append(payload)
            return emit(payload, *args, **kwargs)

        work._emit_report = recorded
        try:
            code = work.main(["--repo", REPO, "--issue", str(ISSUE), "--root", str(self.holder)])
        finally:
            work._emit_report = emit
        # A reason the entrance returned a builder that its list lacks fails the run, as it fails the suite.
        flagged = [reason for reason in map(unlisted_builder_reason, self.reports) if reason]
        if flagged:
            sys.stderr.write(f"route_fixture: the decision carries unlisted_builder_reason {flagged[0]}\n")
            return code or 1
        return code

    def stop(self) -> None:
        for child in self.children:
            if child.poll() is None:
                child.kill()
            child.wait()


def unlisted_builder_reason(report: dict) -> str | None:
    """The flag a printed decision carries, on the decision itself or on its detail's ``if_ended``."""
    if report.get("unlisted_builder_reason"):
        return report["unlisted_builder_reason"]
    try:
        detail = json.loads(report.get("detail") or "")
    except (TypeError, ValueError):
        return None
    ended = detail.get("if_ended") if isinstance(detail, dict) else None
    return ended.get("unlisted_builder_reason") if isinstance(ended, dict) else None


def ready_at_head(fixture: Fixture, synchronization: dict, live=lambda head: None, *, owed: bool = False) -> object:
    """``live`` runs while the hand-started builder is live, as its proof would; ``owed`` as in ``hand_stretch``."""
    source, head = fixture.source()
    fixture.pull_request(head, synchronization)
    hand = fixture.hand_stretch(source, owed=owed)
    builder = hand["dispatch_id"]
    fixture.cold_reading_clean = True
    report, dispatch = fixture.use_report(fixture.state(), source, builder)
    # The handoff's floor command, run at the head as the handoff says, with its output.
    fixture.post(f"<!-- tradecraft:floor:v1 head={head} status=pass -->\n\n```\n{FLOOR}\n```\n\n1 passed\n")
    live(head)
    fixture.launch_tree.complete_hand_record(fixture.store, builder, completed_by="the builder's readiness record",
                                             now=START + timedelta(minutes=20))
    fixture.readiness(builder, head, checks=[{"stage": "use", "criterion": None, "row": None, "dispatch": dispatch,
                                              "head": head, "report": report, "relaunch_of": None}],
                      findings=[{"report": report, "finding": "F1", "disposition": "fixed", "commit": head}],
                      started_by="hand")
    return fixture.state()


def git(root: Path, *words: str) -> str:
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=fixture", "-c", "user.email=fixture@invalid",
                           *words], check=True, capture_output=True, stdin=subprocess.DEVNULL).stdout.decode().strip()


def ready_launched(fixture: Fixture) -> object:
    """A launched builder ready at the head of a holder checkout with Git history, so reach is read, not stubbed."""
    work, records, root = fixture.work, fixture.records, fixture.holder
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "--all")
    git(root, "commit", "-q", "-m", "base")
    base = git(root, "rev-parse", "HEAD")
    git(root, "checkout", "-q", "-b", "tradecraft/5-fixture")
    for path, text in (("job/job.md", "run the job\n"), ("skill/SKILL.md", "how an adopter loads the job\n")):
        (root / path).parent.mkdir(exist_ok=True)
        (root / path).write_text(text, encoding="utf-8")
    git(root, "add", "--all")
    git(root, "commit", "-q", "-m", "job")
    head = git(root, "rev-parse", "HEAD")
    fixture.pull_request(head, CLEAR)
    fixture.pr.update(draft=False, base={"ref": "main", "sha": base})
    state = fixture.state()
    brief, _artifact, comment, _checks = work._handoff_inputs(state, FLOOR)
    text = work.compose_handoff_for(state, branch="tradecraft/5-fixture", holder_root=root, plugin_root=LIB.parent,
                                    notify=None, floor_command=FLOOR)
    builder, output, request = fixture._request("stretch", 5, root=root, holder_session=HOLDER_SESSION)
    request.update(revision_before=base, lineage_branch="tradecraft/5-fixture", handoff={
        "brief_comment": brief.source_id, "artifact_comment": comment, "floor_command": FLOOR, "notify": None,
        "holder_root": str(root), "plugin_root": str(LIB.parent), "pull_request": 7, "holder_written": False})
    request_path = records.sidecar(output, ".request.json")
    records.write_json(request_path, request)
    records.write_bytes(records.sidecar(output, ".dispatch.bin"), text)
    fixture.launch_tree.write_pointer(fixture.store, dispatch_id=builder, work=WORK, request=request_path,
                                      run=records.sidecar(output, ".run.json"), session_id=None,
                                      launcher=fixture.lifecycle.process_identity(), root=root)
    # This process stands in the launch's tree, as the builder's own run would, while its use seat starts.
    holds, fixture.launch_tree.holds = fixture.launch_tree.holds, lambda launch: launch["dispatch_id"] == builder
    try:
        report, dispatch = fixture.use_report(state, root, builder)
    finally:
        fixture.launch_tree.holds = holds
    fixture.post(f"<!-- tradecraft:floor:v1 head={head} status=pass -->\n\n```\n{FLOOR}\n```\n\n1 passed\n")
    records.write_json(records.sidecar(output, ".run.json"), {
        "schema_version": records.SCHEMA_VERSION, "dispatch_id": builder, "lifecycle": "completed",
        "outcome": "success", "revision_after": head, "completed_at": (START + timedelta(minutes=20)).isoformat()})
    fixture.readiness(builder, head, checks=[{"stage": "use", "criterion": None, "row": None, "dispatch": dispatch,
                                              "head": head, "report": report, "relaunch_of": None}],
                      findings=[{"report": report, "finding": "F1", "disposition": "fixed", "commit": head}])
    fixture.cold_reading_clean = "reach-read"
    # The holder's proof, gate and merge readings stand clear: the fixture serves no policy sources to compose a
    # proof from and no GitHub to read the others by, and this scenario's subject is the builder's own records.
    work._current_marker = (lambda current: lambda checked, name, **k: name == "proof" or current(
        checked, name, **k))(work._current_marker)
    work.decide = (lambda decide: lambda checked, rules: decide(replace(checked, proof_current=True), rules))(
        work.decide)
    work._release_gate_status = lambda *_a: {"verdict": "none", "reason": "none", "head": None,
                                             "requirement_known": True}
    work._merge_readiness = lambda *_a: {"reason": "ready", "detail": "", "ready": True}
    return fixture.state()


def _clock() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


def _wait_argv(fixture: Fixture) -> tuple[str, list[str]]:
    """The command the handed-off report prints for this work, and the same words run by this interpreter."""
    import builder_wait
    command = builder_wait.wait_command(REPO, ISSUE, fixture.holder, LIB.parent)
    return command, [sys.executable, *shlex.split(command)[1:]]


def watch(name: str, fixture: Fixture) -> int:
    """Start a stand-in builder and the wait on it, print the wait's lines as they come, take the decision while
    the builder runs, then print the stand-in's records and when the stand-in and the wait each ended."""
    lock = threading.Lock()

    def say(text: str) -> None:
        with lock:
            sys.stdout.write(text)
            sys.stdout.flush()

    replay = LIB / "tests" / REPLAY_LOG if name == "watch-replay" else None
    stretch = fixture.watched_stretch(WATCHED[name], replay)
    child, dispatch_id, run_path, log = stretch["child"], stretch["dispatch_id"], stretch["run"], stretch["log"]
    started = time.monotonic()
    say(f"--- {_clock()} the stand-in builder started: dispatch {dispatch_id}, log {log} ---\n")
    if replay is not None:
        say(f"--- the stand-in appends {replay} line by line ---\n")
    command, argv = _wait_argv(fixture)
    say(f"--- {_clock()} the wait, by the command a handed-off report prints, run by this interpreter: {command} ---\n")
    wait = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    ended: dict[str, str] = {}

    def pump() -> None:
        for line in wait.stdout:
            say("wait| " + line.decode("utf-8", "replace").rstrip("\r\n") + "\n")

    def builder_end() -> None:
        child.wait()
        ended["builder"] = _clock()

    threads = [threading.Thread(target=pump, daemon=True), threading.Thread(target=builder_end, daemon=True)]
    for thread in threads:
        thread.start()
    # Mid-way through the replay; for the others in the stand-in's quiet span, with its last step running.
    time.sleep(max(0.0, (5 if replay is not None else 13) - (time.monotonic() - started)))
    with lock:
        sys.stdout.write(f"--- {_clock()} the read-only decision, taken while the builder runs ---\n")
        sys.stdout.flush()
        code = fixture.decision(fixture.state())
        request = json.loads(stretch["request"].read_bytes())
        sys.stdout.write("--- the stand-in's own records at that moment ---\n"
                         + json.dumps({"request_limit_seconds": request["handoff"]["timeout_seconds"],
                                       "run": json.loads(run_path.read_bytes())}, indent=2) + "\n")
        sys.stdout.flush()
    # The decision is read; the stand-in may now end.
    stretch["read"].write_bytes(b"")
    try:
        wait.wait(timeout=120)
    except subprocess.TimeoutExpired:
        wait.kill()
        wait.wait()
        say("route_fixture: the wait ran on for two minutes and was stopped\n")
        code = code or 1
    ended["wait"] = _clock()
    for thread in threads:
        thread.join(timeout=10)
    say("--- the stand-in's run record as it ended ---\n" + json.dumps(json.loads(run_path.read_bytes()), indent=2)
        + "\n")
    say(f"--- the stand-in builder ended at {ended.get('builder', 'not yet')}; the wait ended at {ended['wait']}, "
        f"exit {wait.returncode} ---\n")
    return code or wait.returncode


def wait_once(fixture: Fixture) -> int:
    """The decision, then the wait run once against it, its lines printed as it prints them."""
    code = fixture.decision(fixture.state())
    command, argv = _wait_argv(fixture)
    sys.stdout.write(f"--- {_clock()} the wait, by the command a handed-off report prints, run by this interpreter: "
                     f"{command} ---\n")
    sys.stdout.flush()
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
    sys.stdout.write("".join("wait| " + line + "\n" for line in
                             (result.stdout + result.stderr).decode("utf-8", "replace").splitlines()))
    sys.stdout.write(f"--- {_clock()} the wait ended, exit {result.returncode} ---\n")
    sys.stdout.flush()
    return code or result.returncode


def scenario(name: str, fixture: Fixture) -> int:
    head = "a" * 40
    if name in WATCHED:
        return watch(name, fixture)
    if name == "watch-hand":
        fixture.hand_stretch(fixture.base / "implementation")
        return wait_once(fixture)
    if name == "watch-none":
        fixture.completed("stretch", 5)
        return wait_once(fixture)
    if name == "ready-reported":
        state = ready_launched(fixture)
        code = fixture.decision(state)
        sys.stdout.write("--- the release report's builder_route ---\n")
        sys.stdout.write(json.dumps(fixture.work._builder_route_report(state), indent=2, default=str) + "\n")
        return code
    if name in ("handoff-due", "handoff"):
        state = fixture.state()
        code = fixture.decision(state)
        if name == "handoff":
            text = fixture.work.compose_handoff_for(
                state, branch="tradecraft/5-fixture", holder_root=fixture.holder, plugin_root=LIB.parent,
                notify=None, floor_command=FLOOR)
            sys.stdout.write("--- composed handoff ---\n")
            sys.stdout.flush()
            sys.stdout.buffer.write(text)
            sys.stdout.buffer.flush()
        return code
    if name == "with-builder":
        fixture.live_stretch()
        return fixture.decision(fixture.state())
    if name == "hand-started":
        fixture.hand_stretch(fixture.base / "implementation")
        return fixture.decision(fixture.state())
    if name == "stretch-stopped":
        fixture.pull_request(head, CLEAR)
        fixture.completed("stretch", 5)
        return fixture.decision(fixture.state())
    if name == "cannot-launch":
        fixture.pull_request(head, CLEAR)
        builder = fixture.completed("stretch", 5)
        fixture.readiness(builder, head, status="stopped",
                          stop={"kind": "cannot-launch", "reason": "gh is not signed in", "check": "use"})
        return fixture.decision(fixture.state())
    if name == "final-pass":
        return fixture.decision(ready_at_head(fixture, CLEAR))
    if name == "catch-up":
        return fixture.decision(ready_at_head(fixture, {**CLEAR, "behind": True, "strict": True,
                                                        "merge_state": "behind"}))
    if name == "launch-account-held":
        fixture.pull_request(head, CLEAR)
        fixture.bounded_stretch(5)
        return fixture.decision(fixture.state())
    if name == "relay-in-flight":
        fixture.completed("build", 5)
        return fixture.decision(fixture.state())
    if name == "owner-asked-relay":
        fixture.post(RELAY_ASK)
        return fixture.decision(fixture.state())
    raise ValueError(f"unknown scenario: {name}")


def _remove(path: Path) -> None:
    """Remove what the run made, read-only Git objects included, which Windows won't delete as they are."""
    def writable(function, name, _error):
        try:
            os.chmod(name, stat.S_IWRITE)
            function(name)
        except OSError:
            pass
    shutil.rmtree(path, **({"onexc": writable} if sys.version_info >= (3, 12) else {"onerror": writable}))


def main(argv: list[str] | None = None) -> int:
    global LIB
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("scenario", nargs="?", choices=sorted(SCENARIOS))
    parser.add_argument("--list", action="store_true", help="print the scenario names, one per line")
    parser.add_argument("--mechanical", action="store_true",
                        help="with handoff or handoff-due: the change is on the ordinary / mechanical lane, no plan")
    args = parser.parse_args(argv)
    if args.mechanical and args.scenario not in ("handoff", "handoff-due"):
        parser.error("--mechanical applies to handoff and handoff-due")
    if args.list or args.scenario is None:
        sys.stdout.buffer.write("".join(f"{name}\n" for name in SCENARIOS).encode("ascii"))
        return 0 if args.list else 2
    # Inside the folder around the tree, with short names under Windows' path limit.
    base = Path(tempfile.mkdtemp(prefix="rf-", dir=LIB.parent.parent)).resolve()
    try:
        isolate(base)
        if not (LIB.parent / ".claude-plugin" / "plugin.json").is_file():
            # A tree of the practice's paths alone has no plugin manifest to read a version from, so the run
            # works on a copy beside a stand-in one.
            LIB = shutil.copytree(LIB, base / "p" / "lib", ignore=shutil.ignore_patterns("__pycache__"))
            (LIB.parent / ".claude-plugin").mkdir()
            (LIB.parent / ".claude-plugin" / "plugin.json").write_text('{"version": "0.0.0"}', encoding="utf-8")
        fixture = Fixture(base, mechanical=args.mechanical)
        try:
            return scenario(args.scenario, fixture)
        finally:
            fixture.stop()
    finally:
        _remove(base)


if __name__ == "__main__":
    raise SystemExit(main())

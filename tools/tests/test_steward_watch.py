"""Tests for tools/steward_watch.py: the Steward's signal, wake, handover and cover (#890).

Every GitHub call goes through a recording fake that serves a small in-memory
lab, so each test states exactly what GitHub held and reads back every argv the
script sent. Every test passes its own state directory; the probe-refusal tests
are the only ones that resolve the default, and they assert it is refused.
Criterion ids (C1 ...) are the settled artifact's on #890.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import steward_watch as sw  # noqa: E402

REPO = sw.LAB_REPO
PAGE = 683
ALERTS = 950
NOW = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
CUTOFF = "2026-10-11T06:35:28Z"
REPOS = list(sw.PRACTICE_REPOS) + [
    "Grimblaz-and-Friends/Organizations-of-Verra", "Grimblaz-and-Friends/Daemon",
    "Grimblaz-and-Friends/Countdown-Clash", "Grimblaz-and-Friends/Windgust-Questbook"]


def at(hours: float) -> str:
    return sw.iso(NOW - timedelta(hours=hours))


def comment(cid: int, body: str, hours_ago: float = 5, login: str = "Grimblaz") -> dict:
    return {"id": cid, "body": body, "created_at": at(hours_ago), "user": {"login": login},
            "html_url": f"https://github.com/{REPO}/issues/{PAGE}#issuecomment-{cid}"}


def watermark(cid: int = 100, handled: int = 100, read: int = 28, cutoff: str = CUTOFF,
              alerts: int = ALERTS) -> dict:
    return comment(cid, sw.watermark_body(handled, read, cutoff, alerts), hours_ago=30)


class FakeLab:
    """An in-memory GitHub the gh runner reads and writes, recording every argv."""

    def __init__(self, page_comments=None, merges=None, alert_comments=None,
                 alerts_body=sw.ALERTS_ISSUE_MARKER + "\nAlerts for the owner.\n",
                 failing_repos=()):
        self.issues = {PAGE: list(page_comments or [watermark()]),
                       ALERTS: list(alert_comments or [])}
        self.bodies = {ALERTS: alerts_body}
        self.merges = merges or {}
        self.failing = set(failing_repos)
        self.calls: list[list[str]] = []
        self.next_id = 5000

    def __call__(self, args, input_text=None, timeout=60):
        self.calls.append(list(args))
        if args[0] == "pr":
            repo = args[args.index("--repo") + 1]
            if repo in self.failing:
                raise sw.WatchError(f"gh pr list exited 1: no access to {repo}")
            bound = sw.parse_time(args[args.index("--search") + 1].split(">=", 1)[1])
            rows = [r for r in self.merges.get(repo, []) if sw.parse_time(r["mergedAt"]) >= bound]
            return json.dumps(rows)
        if args[0] == "workflow":
            return ""
        method = args[args.index("--method") + 1]
        endpoint = [a for a in args if a.startswith("repos/")][0]
        parts = endpoint.split("/")
        if method == "GET" and parts[-1] == "comments":
            items = self.issues.get(int(parts[-2]), [])
            half = len(items) // 2
            return json.dumps(items[:half]) + "\n" + json.dumps(items[half:])
        if method == "GET":
            return json.dumps({"number": int(parts[-1]), "body": self.bodies.get(int(parts[-1]), "")})
        payload = json.loads(input_text)
        if method == "POST":
            self.next_id += 1
            new = comment(self.next_id, payload["body"], hours_ago=0)
            self.issues.setdefault(int(parts[-2]), []).append(new)
            return json.dumps(new)
        if method == "PATCH":
            target = int(parts[-1])
            for items in self.issues.values():
                for item in items:
                    if item["id"] == target:
                        item["body"] = payload["body"]
                        return json.dumps(item)
        raise AssertionError(f"unexpected call {args}")

    def github(self):
        return sw.GitHub(runner=self)


def merges(count: int, first_hours_ago: float = 10, repo: str = REPOS[2]) -> dict:
    rows = [{"number": n, "mergedAt": at(first_hours_ago - n * 0.1), "url": f"u{n}"}
            for n in range(count)]
    return {repo: rows}


def run_cli(argv, lab: FakeLab, now: datetime = NOW):
    args = sw.build_parser().parse_args(argv)
    return sw.run(args, github=lab.github(), now=now)


# ---------------------------------------------------------------- row 1: signal


@pytest.mark.parametrize("body,steward", [
    ("<!-- lab:steward:v1 kind=post -->\nhello", True),
    ("BOM<!-- lab:steward:v1 kind=post -->   \r\nhello".replace("BOM", sw.BOM), True),
    ("<!-- lab:steward:v1 kind=read-note read=28 -->\nread 28", True),
    (sw.watermark_body(1, 2, CUTOFF, 3), True),
    ("a holder's intake\n<!-- lab:steward:v1 kind=post -->", False),  # quoted later
    ("> <!-- lab:steward:v1 kind=post -->\nquoted", False),
    ("<!-- lab:steward:v1 kind=read-note -->", False),  # read= missing
    ("<!-- lab:steward:v1 kind=post read=3 -->", False),  # attribute not in grammar
    ("<!-- lab:steward:v1 kind=watermark handled=x read=1 cutoff=2026-10-11T00:00:00Z alerts=3 -->", False),
    ("<!-- tradecraft:steward:v1 kind=post -->", False),
    ("", False),
])
def test_classifier_reads_only_the_first_line_in_grammar(body, steward):
    """C1: a marked first line is the Steward's; a marker anywhere else is not."""
    assert (sw.classify(body) is not None) is steward


def test_intake_is_unmarked_and_above_handled_in_both_polarities():
    """C1: marked never intake; unmarked above handled always; at or below never."""
    page = sw.Page(REPO, PAGE, [
        watermark(handled=200),
        comment(150, "old holder intake"),
        comment(200, "holder intake exactly at the watermark"),
        comment(201, "<!-- lab:steward:v1 kind=post -->\nthe Steward"),
        comment(202, "new holder intake\n<!-- lab:steward:v1 kind=post -->"),
    ])
    assert [int(c["id"]) for c in page.intake(200)] == [202]


@pytest.mark.parametrize("count", [0, 2])
def test_watermark_count_other_than_one_stops_every_reader(tmp_path, count):
    """C2: zero or two watermarks -> non-zero exit naming the fault; no trigger, alert or success."""
    comments = [watermark(cid=100 + n) for n in range(count)] + [comment(300, "intake", 9)]
    lab = FakeLab(page_comments=comments, merges=merges(6, 20))
    for argv in (["wake"], ["status"], ["cover"], ["handled", "300"]):
        with pytest.raises(sw.WatchError, match="watermark comments"):
            outcome = run_cli(argv + ["--state-dir", str(tmp_path)], lab)
            if isinstance(outcome, dict) and outcome.get("error"):
                raise sw.WatchError(outcome["error"])
    assert not any(c[0] == "workflow" for c in lab.calls)
    assert not (tmp_path / "cover-last-success.json").exists()
    assert not (tmp_path / "woken.json").exists()


def test_cover_cli_exits_non_zero_on_a_bad_watermark(tmp_path, monkeypatch):
    """C2: the exit status is what a scheduled run and the mod see."""
    lab = FakeLab(page_comments=[comment(300, "intake")])
    real = sw.GitHub
    monkeypatch.setattr(sw, "GitHub", lambda deadline=None: real(runner=lab))
    assert sw.main(["cover", "--state-dir", str(tmp_path)]) == 1
    assert sw.main(["wake", "--state-dir", str(tmp_path)]) == 1


def test_handled_refuses_lower_and_foreign_ids_and_lists_what_it_covers(tmp_path):
    """C3: handled moves forward only, onto a page comment, and names each comment it covers."""
    lab = FakeLab(page_comments=[watermark(handled=200), comment(150, "old"), comment(201, "intake A"),
                                 comment(202, "<!-- lab:steward:v1 kind=post -->\nmine"),
                                 comment(203, "intake B"), comment(204, "intake C")])
    with pytest.raises(sw.WatchError, match="below"):
        run_cli(["handled", "150", "--state-dir", str(tmp_path)], lab)
    with pytest.raises(sw.WatchError, match="not a comment"):
        run_cli(["handled", "999", "--state-dir", str(tmp_path)], lab)
    result = run_cli(["handled", "203", "--state-dir", str(tmp_path)], lab)
    assert [c["id"] for c in result["newly_handled"]] == [201, 203]
    patch = [c for c in lab.calls if "PATCH" in c]
    assert patch and patch[-1][3] == f"repos/{REPO}/issues/comments/100"
    assert sw.classify(lab.issues[PAGE][0]["body"])["handled"] == "203"


def test_read_recorded_rewrites_the_one_watermark(tmp_path):
    """C3: read-recorded sets read and cutoff in the single watermark comment."""
    lab = FakeLab()
    run_cli(["read-recorded", "--read", "29", "--cutoff", "2026-10-12T10:00:00+00:00",
             "--state-dir", str(tmp_path)], lab)
    mark = sw.classify(lab.issues[PAGE][0]["body"])
    assert (mark["read"], mark["cutoff"], mark["handled"]) == ("29", "2026-10-12T10:00:00Z", "100")
    with pytest.raises(sw.WatchError, match="below"):
        run_cli(["read-recorded", "--read", "27", "--cutoff", CUTOFF, "--state-dir", str(tmp_path)], lab)


def test_post_prepends_the_marker_and_seed_refuses_a_second_watermark(tmp_path):
    lab = FakeLab()
    body = tmp_path / "note.md"
    body.write_bytes(b"Read 29's note.\n")
    run_cli(["post", "--kind", "read-note", "--read", "29", "--body-file", str(body),
             "--state-dir", str(tmp_path)], lab)
    assert sw.classify(lab.issues[PAGE][-1]["body"]) == {"kind": "read-note", "read": "29"}
    with pytest.raises(sw.WatchError, match="already carries"):
        run_cli(["seed", "--handled", "1", "--read", "28", "--cutoff", CUTOFF, "--alerts", "9",
                 "--state-dir", str(tmp_path)], lab)


# ---------------------------------------------------------------- row 2: wake


def test_read_trigger_boundary_is_five_strictly_after_cutoff(tmp_path):
    """C4: four merges don't trigger, five do, and a merge exactly at the cutoff doesn't count."""
    four = {REPOS[0]: [{"number": n, "mergedAt": at(5 - n * 0.1), "url": ""} for n in range(4)],
            REPOS[1]: [{"number": 9, "mergedAt": CUTOFF, "url": ""}]}
    lab = FakeLab(merges=four)
    assert sw.wake(lab.github(), tmp_path, PAGE, NOW, REPOS)["triggers"] == []
    four[REPOS[3]] = [{"number": 7, "mergedAt": at(1), "url": ""}]
    keys = [t["key"] for t in sw.wake(lab.github(), tmp_path, PAGE, NOW, REPOS)["triggers"]]
    assert keys == ["read:29"]


def test_each_trigger_wakes_once_and_the_next_read_can_wake(tmp_path):
    """C5: keys repeat until mark-woken and never after; intake does not re-raise the read."""
    lab = FakeLab(merges=merges(5, 6))
    github = lab.github()
    first = [t["key"] for t in sw.wake(github, tmp_path, PAGE, NOW, REPOS)["triggers"]]
    again = [t["key"] for t in sw.wake(github, tmp_path, PAGE, NOW, REPOS)["triggers"]]
    assert first == again == ["read:29"]
    sw.mark_woken(tmp_path, PAGE, "read:29")
    assert sw.wake(github, tmp_path, PAGE, NOW, REPOS)["triggers"] == []
    lab.issues[PAGE].append(comment(400, "holder intake", 0.1))
    assert [t["key"] for t in sw.wake(github, tmp_path, PAGE, NOW, REPOS)["triggers"]] == ["intake:400"]
    sw.mark_woken(tmp_path, PAGE, "intake:400")
    for _ in range(3):
        assert sw.wake(github, tmp_path, PAGE, NOW, REPOS)["triggers"] == []
    run_cli(["read-recorded", "--read", "29", "--cutoff", at(5.5), "--state-dir", str(tmp_path)], lab)
    lab.merges = merges(10, 5.4)
    assert [t["key"] for t in sw.wake(github, tmp_path, PAGE, NOW, REPOS)["triggers"]] == ["read:30"]


def test_wake_keys_are_scoped_to_their_page(tmp_path):
    """C5: read:29 woken on page A neither suppresses nor prunes page B's read:29."""
    other = 9001
    lab = FakeLab(merges=merges(5, 6))
    lab.issues[other] = [watermark(cid=700)]
    github = lab.github()
    sw.mark_woken(tmp_path, other, "read:29")
    assert [t["key"] for t in sw.wake(github, tmp_path, PAGE, NOW, REPOS)["triggers"]] == ["read:29"]
    sw.mark_woken(tmp_path, PAGE, "read:29")
    lab.merges = {}
    sw.wake(github, tmp_path, other, NOW, REPOS)  # page B no longer due: prunes only its own
    keys = sw.woken_keys(tmp_path)
    assert sw.page_scope(PAGE) + "read:29" in keys
    assert sw.page_scope(other) + "read:29" not in keys


def test_wake_texts_name_their_trigger_and_never_a_title(tmp_path):
    lab = FakeLab(page_comments=[watermark(), comment(401, "intake")], merges=merges(5, 6))
    triggers = sw.wake(lab.github(), tmp_path, PAGE, NOW, REPOS)["triggers"]
    assert triggers[0]["text"].startswith("steward-wake: read 29 is due (5 merges since")
    assert "#issuecomment-401" in triggers[1]["text"]


def test_a_failed_repository_read_wakes_nothing_and_prunes_nothing(tmp_path):
    lab = FakeLab(merges=merges(5, 6), failing_repos={REPOS[4]})
    sw.mark_woken(tmp_path, PAGE, "read:29")
    found = sw.wake(lab.github(), tmp_path, PAGE, NOW, REPOS)
    assert found["triggers"] == [] and "merge read failed" in found["error"]
    assert sw.woken_keys(tmp_path) == [sw.page_scope(PAGE) + "read:29"]


def test_wake_reads_only(tmp_path):
    """C7's script half: a wake run makes only GET reads and pr list."""
    lab = FakeLab(merges=merges(5, 6))
    sw.wake(lab.github(), tmp_path, PAGE, NOW, REPOS)
    for call in lab.calls:
        assert call[0] == "pr" or call[call.index("--method") + 1] == "GET"


# ---------------------------------------------------------------- row 3: handover


def gate_facts(**changes) -> dict:
    facts = {"tokens": 260_000, "threshold": 250_000, "skip_tokens": False,
             "turn_running": False, "since_turn_complete": 61, "turn_started_since": False,
             "settle": 60, "background_tasks": 0, "crons": 0, "agents_busy": 0,
             "since_owner": 3601, "owner_quiet": 3600, "disabled": False}
    facts.update(changes)
    return facts


FAILING = {
    "tokens": {"tokens": 250_000},
    "turn-running": {"turn_running": True},
    "settle": {"since_turn_complete": 30},
    "background": {"background_tasks": 1},
    "owner-quiet": {"since_owner": 3599},
    "disabled": {"disabled": True},
}


def test_gate_all_true_is_due():
    assert sw.handover_due(gate_facts()) == {"due": True, "blocking": []}


@pytest.mark.parametrize("name", sorted(FAILING))
def test_gate_each_condition_failing_alone_blocks(name):
    """C9: each single failing condition says no, and names itself."""
    assert sw.handover_due(gate_facts(**FAILING[name])) == {"due": False, "blocking": [name]}


@pytest.mark.parametrize("name", sorted(FAILING))
def test_gate_each_guard_is_necessary(name):
    """C9: delete one guard's arm and its failing row flips to yes."""
    without = tuple(c for c in sw.GATE_CONDITIONS if c[0] != name)
    assert sw.handover_due(gate_facts(**FAILING[name]), without)["due"] is True


@pytest.mark.parametrize("facts", [
    {"turn_started_since": True}, {"crons": 1}, {"agents_busy": 1},
    {"since_owner": 0}, {"since_turn_complete": 0},
])
def test_gate_covers_every_background_kind_and_quiet_clock(facts):
    """C13 and C14 through the gate: crons, subagents and a fresh turn each block."""
    assert sw.handover_due(gate_facts(**facts))["due"] is False


def test_gate_cli_reads_the_disabled_switch(tmp_path):
    lab = FakeLab()
    argv = ["handover-due", "--tokens", "300000", "--since-turn-complete", "100",
            "--since-owner", "4000", "--state-dir", str(tmp_path)]
    assert run_cli(argv, lab)["due"] is True
    (tmp_path / "handover-disabled").write_bytes(b"")
    assert run_cli(argv, lab)["blocking"] == ["disabled"]


NON_OWNER = sorted(sw.NON_OWNER_ORIGINS)
OWNER_KINDS = ["composer", "bridge", "unclassified", "auto-continuation", "channel",
               "slack-ping", "sdk", "a-kind-nobody-has-named"]


@pytest.mark.parametrize("kind", NON_OWNER)
def test_non_owner_origins(kind):
    assert sw.origin_is_owner(kind) is False


@pytest.mark.parametrize("kind", OWNER_KINDS)
def test_every_other_origin_counts_as_the_owner(kind):
    """C14: the guard fails closed -- unnamed kinds count as the owner."""
    assert sw.origin_is_owner(kind) is True


def test_origin_record_keeps_kind_time_and_flag_only(tmp_path, monkeypatch):
    monkeypatch.setattr(sw, "ORIGINS_KEPT", 3)
    lab = FakeLab()
    for kind in ("composer", "plugin", "bridge", "weird kind"):
        run_cli(["origin-is-owner", kind, "--record", "--state-dir", str(tmp_path)], lab)
    lines = (tmp_path / "origins.log").read_bytes().decode("ascii").splitlines()
    assert lines == [f"{sw.iso(NOW)} plugin owner=no", f"{sw.iso(NOW)} bridge owner=yes",
                     f"{sw.iso(NOW)} weird?kind owner=yes"]


def write_state_file(state_dir: Path, handover_id: str, written: str,
                     headings=sw.HANDOVER_HEADINGS, old: str = "old-session") -> None:
    body = [f"<!-- lab:steward-handover:v1 id={handover_id} old_session={old} written={written} -->"]
    for heading in headings:
        body += [f"## {heading}", "none", ""]
    (state_dir / "handover.md").write_bytes("\n".join(body).encode("utf-8"))


@pytest.mark.parametrize("problem", ["wrong-id", "old-write", "missing-heading", "absent"])
def test_handover_check_refuses_each_defect(tmp_path, problem):
    """C11: a wrong id, an old write and a missing heading each fail the check."""
    since = sw.iso(NOW)
    if problem == "wrong-id":
        write_state_file(tmp_path, "other", sw.iso(NOW + timedelta(minutes=2)))
    elif problem == "old-write":
        write_state_file(tmp_path, "H1", sw.iso(NOW - timedelta(minutes=2)))
    elif problem == "missing-heading":
        write_state_file(tmp_path, "H1", sw.iso(NOW + timedelta(minutes=2)), sw.HANDOVER_HEADINGS[:3])
    assert sw.handover_check(tmp_path, "H1", since)["ok"] is False
    write_state_file(tmp_path, "H1", sw.iso(NOW + timedelta(minutes=2)))
    assert sw.handover_check(tmp_path, "H1", since)["ok"] is True


QUIET = {"turn_running": False, "since_turn_complete": 61}


def request(state_dir: Path, now: datetime = NOW) -> str:
    step = sw.handover_step(state_dir, "gate-yes", now, session="sess-old")
    assert step["action"] == "submit" and step["state"] == "active"
    return sw.handover_state(state_dir)["id"]


def test_clear_only_after_a_passing_check(tmp_path):
    """C11: turn-settled returns clear only once the file passes; a bad file abandons."""
    hid = request(tmp_path)
    assert sw.handover_step(tmp_path, "turn-settled", NOW + timedelta(minutes=1))["action"] == "none"
    write_state_file(tmp_path, hid, sw.iso(NOW + timedelta(minutes=2)))
    assert sw.handover_step(tmp_path, "turn-settled", NOW + timedelta(minutes=3), **QUIET)["action"] == "clear"


def test_bad_state_file_abandons_and_holds_for_an_hour(tmp_path):
    request(tmp_path)
    write_state_file(tmp_path, "not-this-one", sw.iso(NOW + timedelta(minutes=2)))
    step = sw.handover_step(tmp_path, "turn-settled", NOW + timedelta(minutes=3))
    assert (step["action"], step["state"]) == ("none", "idle") and "abandoned" in step["status"]
    held = sw.handover_step(tmp_path, "gate-yes", NOW + timedelta(minutes=30))
    assert held["action"] == "none" and "held" in held["status"]
    assert sw.handover_step(tmp_path, "gate-yes", NOW + timedelta(minutes=64))["action"] == "submit"


def test_no_state_file_within_fifteen_minutes_abandons(tmp_path):
    request(tmp_path)
    assert sw.handover_step(tmp_path, "tick", NOW + timedelta(minutes=14))["action"] == "none"
    assert sw.handover_step(tmp_path, "tick", NOW + timedelta(minutes=16))["state"] == "idle"


def test_request_moves_the_previous_file_aside(tmp_path):
    (tmp_path / "handover.md").write_bytes(b"older")
    request(tmp_path)
    assert (tmp_path / "handover.prev.md").read_bytes() == b"older"
    assert not (tmp_path / "handover.md").exists()


def test_resume_text_names_every_element(tmp_path):
    """C12: state file, cell, the four records, owner-board duty, old id, intervened line."""
    text = sw.resume_text(tmp_path, "H1", "sess-old", "2026-10-13T12:05:00Z")
    for element in (str(tmp_path / "handover.md"), sw.CELL, "#683", "the memory store",
                    "the open issues", "the owner board", "keeping the owner board current",
                    "sess-old", "A turn ran after the state file was written"):
        assert element in text
    assert "A turn ran" not in sw.resume_text(tmp_path, "H1", "sess-old", None)


@pytest.mark.parametrize("route", ["active", "awaiting-clear"])
def test_session_end_clear_resumes_from_either_state(tmp_path, route):
    """C12: session-end-clear from active or awaiting-clear returns exactly resume-text's text."""
    hid = request(tmp_path)
    write_state_file(tmp_path, hid, sw.iso(NOW + timedelta(minutes=2)), old="sess-old")
    if route == "awaiting-clear":
        sw.handover_step(tmp_path, "clear-rejected", NOW + timedelta(minutes=3), reason="refused")
    step = sw.handover_step(tmp_path, "session-end-clear", NOW + timedelta(minutes=4),
                            last_turn_start=sw.iso(NOW + timedelta(minutes=1)))
    assert step["action"] == "submit" and step["state"] == "idle"
    assert step["text"] == sw.resume_text(tmp_path, hid, "sess-old", None,
                                          sw.handover_check(tmp_path, hid, sw.iso(NOW)))


def test_session_end_clear_names_an_intervening_turn(tmp_path):
    hid = request(tmp_path)
    written = sw.iso(NOW + timedelta(minutes=2))
    write_state_file(tmp_path, hid, written)
    step = sw.handover_step(tmp_path, "session-end-clear", NOW + timedelta(minutes=9),
                            last_turn_start=sw.iso(NOW + timedelta(minutes=5)))
    assert f"A turn ran after the state file was written ({written})" in step["text"]


def test_session_end_clear_from_idle_does_nothing(tmp_path):
    assert sw.handover_step(tmp_path, "session-end-clear", NOW)["action"] == "none"


def test_resume_after_a_failed_check_says_rebuild(tmp_path):
    request(tmp_path)
    step = sw.handover_step(tmp_path, "session-end-clear", NOW + timedelta(minutes=4))
    assert "Rebuild what you owe from the old conversation" in step["text"]


@pytest.mark.parametrize("event", ["clear-rejected", "clear-timeout"])
def test_refused_clear_waits_on_the_owner_and_the_wake_keeps_running(tmp_path, event):
    """C29: refusal moves active to awaiting-clear; the wake runs; every turn gets the note."""
    hid = request(tmp_path)
    lab = FakeLab(merges=merges(5, 6))
    assert sw.wake(lab.github(), tmp_path, PAGE, NOW, REPOS)["paused"] == "handover active"
    step = sw.handover_step(tmp_path, event, NOW + timedelta(minutes=3), reason="Remote Control")
    assert step["state"] == "awaiting-clear" and "type /clear" in step["text"]
    assert [t["key"] for t in sw.wake(lab.github(), tmp_path, PAGE, NOW, REPOS)["triggers"]] == ["read:29"]
    for _ in range(2):
        note = sw.handover_step(tmp_path, "prompt", NOW + timedelta(minutes=5))
        assert note["action"] == "note" and "up to date" in note["text"]
    write_state_file(tmp_path, hid, sw.iso(NOW + timedelta(minutes=20)))
    resumed = sw.handover_step(tmp_path, "session-end-clear", NOW + timedelta(minutes=21))
    assert resumed["action"] == "submit" and "failed its check" not in resumed["text"]
    assert sw.handover_step(tmp_path, "prompt", NOW + timedelta(minutes=22))["action"] == "none"


def test_clear_timeout_arrives_through_tick(tmp_path):
    hid = request(tmp_path)
    write_state_file(tmp_path, hid, sw.iso(NOW + timedelta(minutes=1)))
    assert sw.handover_step(tmp_path, "turn-settled", NOW + timedelta(minutes=2), **QUIET)["action"] == "clear"
    assert sw.handover_step(tmp_path, "tick", NOW + timedelta(minutes=3))["state"] == "active"
    assert sw.handover_step(tmp_path, "tick", NOW + timedelta(minutes=5))["state"] == "awaiting-clear"


def test_load_abandons_active_and_keeps_awaiting(tmp_path):
    """C29: a reload abandons an active attempt and keeps one awaiting the owner."""
    request(tmp_path)
    assert sw.handover_step(tmp_path, "load", NOW)["state"] == "idle"
    other = tmp_path / "b"
    other.mkdir()
    request(other, NOW)
    sw.handover_step(other, "clear-rejected", NOW, reason="x")
    assert sw.handover_step(other, "load", NOW)["state"] == "awaiting-clear"


# ---------------------------------------------------------------- row 4: cover


def cover_lab(**changes) -> FakeLab:
    page = [watermark(handled=100), comment(301, "old intake", hours_ago=1.5),
            comment(302, "fresh intake", hours_ago=0.5)]
    return FakeLab(page_comments=page, **changes)


def test_waiting_items_boundaries():
    """C15: intake waits more than an hour; a read waits more than three since its fifth merge."""
    page = sw.Page(REPO, PAGE, [watermark(), comment(301, "a", 1.01), comment(302, "b", 0.99)])
    _, mark = page.watermark()
    due_old = [{"repo": "r", "number": n, "mergedAt": at(3.01)} for n in range(5)]
    due_new = [{"repo": "r", "number": n, "mergedAt": at(2.99)} for n in range(5)]
    assert sw.waiting_items(page, mark, due_old, set(), NOW) == ["intake:301", "read:29"]
    assert sw.waiting_items(page, mark, due_new, set(), NOW) == ["intake:301"]
    assert sw.waiting_items(page, mark, due_old[:4], set(), NOW) == ["intake:301"]
    assert sw.waiting_items(page, mark, due_old, {"intake:301", "read:29"}, NOW) == []


def test_answered_work_is_silent():
    """C15: a marked read-note or an advanced watermark answers the read; handled intake is quiet."""
    old = [{"repo": "r", "number": n, "mergedAt": at(4)} for n in range(5)]
    noted = sw.Page(REPO, PAGE, [watermark(handled=400), comment(301, "x", 2),
                                 comment(400, "<!-- lab:steward:v1 kind=read-note read=29 -->\nnote")])
    _, mark = noted.watermark()
    assert sw.waiting_items(noted, mark, old, set(), NOW) == []
    advanced = sw.Page(REPO, PAGE, [watermark(read=29, cutoff=at(3.5))])
    _, mark = advanced.watermark()
    after = [m for m in old if sw.parse_time(m["mergedAt"]) > sw.parse_time(mark["cutoff"])]
    assert sw.waiting_items(advanced, mark, after, set(), NOW) == []


def test_cover_dispatches_once_per_item(tmp_path):
    """C19: an item already alerted on the alert issue is not dispatched again."""
    lab = cover_lab(merges=merges(5, 8))
    first = sw.cover(lab.github(), tmp_path, PAGE, NOW, repos=REPOS)
    assert first["dispatched"] == ["intake:301", "read:29"]
    workflow = [c for c in lab.calls if c[0] == "workflow"]
    assert workflow == [["workflow", "run", "steward-alert.yml", "--repo", REPO, "--ref", "main",
                         "-f", f"issue={ALERTS}", "-f", "items=intake:301,read:29"]]
    lab.issues[ALERTS].append(comment(9000, sw.alert_body(PAGE, first["dispatched"]),
                                      login=sw.ALERT_BOT))
    second = sw.cover(lab.github(), tmp_path, PAGE, NOW + timedelta(minutes=10), repos=REPOS)
    assert second["dispatched"] == [] and second["error"] is None
    assert sum(1 for c in lab.calls if c[0] == "workflow") == 1


def test_alert_dedupe_trusts_only_the_bot():
    owner_echo = comment(1, sw.alert_body(PAGE, ["intake:301"]))
    bot = comment(2, sw.alert_body(PAGE, ["read:29"]), login=sw.ALERT_BOT)
    assert sw.alerted_keys([owner_echo, bot]) == {"read:29"}


def test_cover_makes_only_reads_and_one_dispatch(tmp_path):
    """C24: GET reads, pr list, and workflow run -- nothing else."""
    lab = cover_lab(merges=merges(5, 8))
    sw.cover(lab.github(), tmp_path, PAGE, NOW, repos=REPOS)
    for call in lab.calls:
        if call[0] == "api":
            assert call[call.index("--method") + 1] == "GET"
        else:
            assert call[:2] in (["pr", "list"], ["workflow", "run"])


def test_dry_run_writes_nothing_and_reports_reach(tmp_path):
    """C17's offline half and the dry run's contract."""
    lab = cover_lab(merges=merges(5, 8))
    state = tmp_path / "lab-state"
    outcome = sw.cover(lab.github(), state, PAGE, NOW, dry_run=True, repos=REPOS)
    assert outcome["waiting"] == ["intake:301", "read:29"] and outcome["dispatched"] == []
    assert sorted(outcome["reach"]) == sorted(REPOS)
    assert list(state.iterdir()) == []


def test_only_a_full_success_records_last_success(tmp_path):
    """C22: a failed read records the run and not a success."""
    lab = cover_lab(merges=merges(5, 8), failing_repos={REPOS[5]})
    outcome = sw.cover(lab.github(), tmp_path, PAGE, NOW, repos=REPOS)
    assert outcome["error"] and not (tmp_path / "cover-last-success.json").exists()
    assert json.loads((tmp_path / "cover-last-run.json").read_bytes())["error"]
    assert not any(c[0] == "workflow" for c in lab.calls)
    lab.failing.clear()
    sw.cover(lab.github(), tmp_path, PAGE, NOW, repos=REPOS)
    assert json.loads((tmp_path / "cover-last-success.json").read_bytes())["at"] == sw.iso(NOW)


def test_hung_gh_is_killed_and_no_success_is_written(tmp_path, monkeypatch):
    """C21: a gh child that hangs is killed at its timeout; the run exits non-zero."""
    monkeypatch.setattr(sw, "GH_COMMAND", [sys.executable, "-c", "import time; time.sleep(60)"])
    monkeypatch.setattr(sw, "GH_TIMEOUT_SECONDS", 1)
    started = time.monotonic()
    assert sw.main(["cover", "--state-dir", str(tmp_path)]) == 1
    assert time.monotonic() - started < 20
    assert "timed out" in json.loads((tmp_path / "cover-last-run.json").read_bytes())["error"]
    assert not (tmp_path / "cover-last-success.json").exists()


def test_a_live_lock_refuses_a_second_run_and_a_dead_one_is_replaced(tmp_path):
    lock = tmp_path / "cover.lock"
    lock.write_bytes(json.dumps({"pid": sw.os.getpid(), "started": sw.iso(NOW)}).encode())
    lab = cover_lab()
    with pytest.raises(sw.WatchError, match="another cover run"):
        sw.cover(lab.github(), tmp_path, PAGE, NOW, repos=REPOS)
    old = NOW - timedelta(minutes=11)
    lock.write_bytes(json.dumps({"pid": sw.os.getpid(), "started": sw.iso(old)}).encode())
    assert sw.cover(lab.github(), tmp_path, PAGE, NOW, repos=REPOS)["error"] is None
    assert not lock.exists()


def test_cover_staleness_boundary_and_one_note_per_episode(tmp_path):
    """C22: stale beyond 7200 s; the episode's key is noted once."""
    sw.write_json_atomic(tmp_path / "cover-last-success.json", {"at": sw.iso(NOW - timedelta(seconds=7200))})
    assert sw.cover_state(tmp_path, NOW)["stale"] is False
    assert sw.cover_state(tmp_path, NOW + timedelta(seconds=1))["stale"] is True
    later = NOW + timedelta(hours=1)
    lab = FakeLab()
    first = sw.wake(lab.github(), tmp_path, PAGE, later, REPOS)["cover"]
    assert first["stale"] and not first.get("noted")
    sw.mark_woken(tmp_path, PAGE, first["key"])
    assert sw.wake(lab.github(), tmp_path, PAGE, later, REPOS)["cover"]["noted"] is True


def test_alert_body_carries_only_keys_and_public_links():
    """C16: the alert names keys and tradecraft links, and mentions the owner."""
    body = sw.alert_body(PAGE, ["intake:301", "read:29", "probe:1"])
    assert body.splitlines()[0] == "<!-- lab:steward-alert:v1 items=intake:301,read:29,probe:1 -->"
    assert "@Grimblaz" in body
    for url in [w for w in body.split() if "://" in w]:
        assert url.rstrip(",").startswith(f"https://github.com/{REPO}/issues/{PAGE}")


@pytest.mark.parametrize("issue,items,body,fault", [
    ("12a", "intake:1", sw.ALERTS_ISSUE_MARKER, "not a number"),
    (str(ALERTS), "intake:1;rm", sw.ALERTS_ISSUE_MARKER, "comma list"),
    (str(ALERTS), "title:1", sw.ALERTS_ISSUE_MARKER, "comma list"),
    (str(ALERTS), "", sw.ALERTS_ISSUE_MARKER, "comma list"),
    (str(ALERTS), "intake:1", "an ordinary issue", "does not open with"),
])
def test_post_alert_refusals(issue, items, body, fault):
    """C16: malformed items and an issue lacking the alerts marker are refused."""
    lab = FakeLab(alerts_body=body)
    with pytest.raises(sw.WatchError, match=fault):
        sw.post_alert(lab.github(), issue, items, PAGE)
    assert not any("POST" in c for c in lab.calls)


def test_post_alert_posts_one_comment():
    lab = FakeLab()
    sw.post_alert(lab.github(), str(ALERTS), "intake:301,probe:2", PAGE)
    assert sw.alerted_keys([{**lab.issues[ALERTS][-1], "user": {"login": sw.ALERT_BOT}}]) == {
        "intake:301", "probe:2"}


WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "steward-alert.yml"


def test_alert_workflow_is_dispatch_only_and_never_interpolates_inputs():
    """C16, C23 and C24: dispatch only, inputs through env, no secret but github.token."""
    text = WORKFLOW.read_bytes().decode("utf-8")
    on_block = text.split("\non:", 1)[1].split("\n\n", 1)[0]
    assert "workflow_dispatch" in on_block
    for trigger in ("push", "pull_request", "schedule", "issue_comment", "workflow_run"):
        assert f"  {trigger}" not in on_block
    run_lines = [line for line in text.splitlines() if line.strip().startswith(("run:", "- run:"))]
    assert run_lines
    for line in run_lines:
        assert "${{ inputs" not in line and "github.event.inputs" not in line
    assert "secrets." not in text.replace("secrets.GITHUB_TOKEN", "")
    assert "persist-credentials: false" in text


# ---------------------------------------------------------------- the scheduled task


def test_task_definition_settings():
    """C20 and C21: no console interpreter, no overlap, a five-minute limit, interactive only."""
    xml = sw.task_xml(r"C:\Python\pythonw.exe", r"D:\repo\tools\steward_watch.py", "", r"D:\repo",
                      start=datetime(2026, 10, 13, 9, 0, 0))
    for setting in ("<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>",
                    "<ExecutionTimeLimit>PT5M</ExecutionTimeLimit>",
                    "<StartWhenAvailable>true</StartWhenAvailable>",
                    "<LogonType>InteractiveToken</LogonType>",
                    "<Interval>PT1H</Interval>",
                    r"<Command>C:\Python\pythonw.exe</Command>",
                    "<Arguments>&quot;D:\\repo\\tools\\steward_watch.py&quot; cover</Arguments>"):
        assert setting in xml
    assert "EndBoundary" not in xml
    probe = sw.task_xml("p", "s", "--dry-run --state-dir x", "w", start=datetime(2026, 10, 13, 9, 0),
                        interval="PT1M", limit="PT1M", end=datetime(2026, 10, 13, 9, 20))
    assert "<EndBoundary>2026-10-13T09:20:00</EndBoundary>" in probe
    assert "<DeleteExpiredTaskAfter>PT0S</DeleteExpiredTaskAfter>" in probe


def test_probe_task_must_carry_a_state_dir(tmp_path):
    lab = FakeLab()
    with pytest.raises(sw.WatchError, match="must carry --state-dir"):
        run_cli(["cover-task", "--xml", "--name", "probe-890", "--args=--dry-run",
                 "--state-dir", str(tmp_path)], lab)
    out = run_cli(["cover-task", "--xml", "--name", "probe-890",
                   f"--args=--dry-run --state-dir {tmp_path}", "--state-dir", str(tmp_path)], lab)
    assert "pythonw.exe" in out["xml"] or sys.platform != "win32"


# ---------------------------------------------------------------- call 14: the state directory


@pytest.fixture
def fake_default(tmp_path, monkeypatch):
    """The default state directory under a temporary home, never the real one.

    The production install creates the real ~/.tradecraft-lab/steward, so a test
    that read it would fail on the Steward's own machine.
    """
    home = tmp_path / "home" / ".tradecraft-lab" / "steward"
    monkeypatch.setattr(sw, "default_state_dir", lambda: home)
    monkeypatch.delenv(sw.STATE_ENV, raising=False)
    return home


def test_state_dir_resolution_order(tmp_path):
    assert sw.resolve_state_dir(str(tmp_path / "a"), {sw.STATE_ENV: str(tmp_path / "b")}) == tmp_path / "a"
    assert sw.resolve_state_dir(None, {sw.STATE_ENV: str(tmp_path / "b")}) == tmp_path / "b"
    assert sw.resolve_state_dir(None, {}) == sw.default_state_dir()


@pytest.mark.parametrize("name", sw.PROBE_ENV)
def test_every_probe_env_setting_is_refused_against_the_default(name, fake_default):
    """C27: each STEWARD_WAKE_* override is refused when the state directory is the default."""
    with pytest.raises(sw.WatchError, match="refused against the default"):
        sw.config(sw.default_state_dir(), PAGE, {name: "1"})


def test_probe_env_settings_are_accepted_in_a_probe_directory(tmp_path, fake_default):
    settings = sw.config(tmp_path, PAGE, {"STEWARD_WAKE_TICK_SECONDS": "30",
                                          "STEWARD_WAKE_PAGE": "9001",
                                          "STEWARD_WAKE_SIMULATE_CLEAR_REFUSED": "1"})
    assert (settings["tick_seconds"], settings["page"], settings["simulate_clear_refused"]) == (30, 9001, True)
    production = sw.config(sw.default_state_dir(), PAGE, {"STEWARD_WAKE_TICK_SECONDS": ""})
    assert production["tick_seconds"] == 300 and production["default_state_dir"] is True


@pytest.mark.parametrize("argv", [
    ["cover", "--dry-run", "--probe-hold", "5"],
    ["cover", "--dry-run", "--probe-hang"],
    ["wake", "--page", "9001"],
    ["mark-woken", "read:1", "--page", "9001"],
    ["handover-due", "--tokens", "1", "--since-turn-complete", "1", "--since-owner", "1",
     "--handover-tokens", "10"],
    ["handover-due", "--tokens", "1", "--since-turn-complete", "1", "--since-owner", "1",
     "--owner-quiet-seconds", "10"],
    ["handover-due", "--tokens", "1", "--since-turn-complete", "1", "--since-owner", "1",
     "--settle-seconds", "10"],
    ["handover-step", "--event", "gate-yes", "--handover-tokens", "10"],
    ["cover-task", "--xml", "--name", "probe", "--args=--state-dir x"],
])
def test_every_probe_flag_is_refused_against_the_default(argv, fake_default):
    """C27: probe-only flags never touch the default state directory."""
    lab = FakeLab()
    with pytest.raises(sw.WatchError, match="refused against the default"):
        run_cli(argv, lab)
    assert lab.calls == []
    assert not fake_default.exists()


def test_cli_output_is_ascii_json(tmp_path, capsys):
    assert sw.main(["origin-is-owner", "composer", "--state-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    out.encode("ascii")
    assert json.loads(out) == {"kind": "composer", "owner": True}


def test_cover_entry_point_runs_windowless_children(monkeypatch, tmp_path):
    """C20's code half: every gh child is launched with CREATE_NO_WINDOW on Windows."""
    seen = {}

    def fake_run(argv, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, b"[]", b"")

    monkeypatch.setattr(sw.subprocess, "run", fake_run)
    sw.gh_run(["api", "--method", "GET", "x"])
    assert seen["stdout"] is subprocess.PIPE and seen["stderr"] is subprocess.PIPE
    assert seen["stdin"] is subprocess.DEVNULL
    if sys.platform == "win32":
        assert seen["creationflags"] & subprocess.CREATE_NO_WINDOW


MOD = Path(__file__).resolve().parents[1] / "steward-wake" / "hooks" / "register.js"


def test_mod_calls_no_model_writes_nothing_and_passes_the_state_dir():
    """C7 and C27: the mod never calls a model, the store or the file system, and
    hands every script call the probe's state directory when one is set."""
    text = MOD.read_bytes().decode("utf-8")
    for forbidden in ("$.model", "$.store", "$.fs", "writeFile", "require("):
        assert forbidden not in text
    assert "if (state.stateDir) argv.push('--state-dir', state.stateDir)" in text
    assert "STEWARD_LAB_STATE_DIR: await $.env.get('STEWARD_LAB_STATE_DIR')" in text
    for name in sw.PROBE_ENV:
        assert f"'{name}'" in text


def _body(text: str, signature: str) -> str:
    """A top-level function's body in the mod: from its signature to its closing brace."""
    return text.split(signature, 1)[1].split("\n}\n", 1)[0]


def test_only_a_steward_title_reaches_the_script():
    """#915 row 3 (C3.7): the mod loads in every tradecraft session, so `start`, the
    only path to `config` and every later script call, is reached only from the gate,
    and only once the title read answers `Steward`, trimmed and case-insensitive."""
    text = MOD.read_bytes().decode("utf-8")
    calls = [m.start() for m in re.finditer(r"(?<![\w.])start\(", text)
             if not text[:m.start()].endswith("function ")]
    admit_at = text.index("async function admit(host) {")
    admit = _body(text, "async function admit(host) {")
    assert len(calls) == 1 and admit_at < calls[0] < admit_at + len(admit)
    assert admit.index("if (isSteward(read.title)) {") < admit.index("state.gate = 'on'") < admit.index(
        "await start(host, state.cwd)")
    assert "const STEWARD = 'steward'" in text
    assert "title.trim().toLowerCase() === STEWARD" in _body(text, "function isSteward(title) {")
    # Every hook that reaches the script waits on `state.cfg`, which only `start` sets.
    assert text.count("state.cfg = ") == 1 and "state.cfg = await script(['config'" in _body(
        text, "async function start(host, cwd) {")


def test_the_title_read_calls_get_session_only_behind_an_allow():
    """#915 row 3 (C3.7): the read is the pane's: get_session for `self`, called only
    when Claude Code's own check answers `allow`, so it never prompts; anything else
    leaves the wake off with the reason on the status line."""
    text = MOD.read_bytes().decode("utf-8")
    assert "const GET_SESSION = 'mcp__ccd_session_mgmt__get_session'" in text
    assert set(re.findall(r"'(mcp__[a-z_]+)'", text)) == {"mcp__ccd_session_mgmt__get_session"}
    assert text.count("$.tool.call(") == 1 and text.count("host.call(") == 1
    read = _body(text, "async function readTitle(host) {")
    assert "const input = { session_id: 'self' }" in read
    assert (read.index("host.tools()") < read.index("host.check(GET_SESSION, input)")
            < read.index("if (decision !== 'allow') return") < read.index("host.call(GET_SESSION, input)"))
    assert "return { title: null, reason: 'failed' }" in read
    assert "status('steward-wake off: title unreadable (' + read.reason + ')')" in text


def test_handover_check_accepts_a_write_stamped_at_the_request_second(tmp_path):
    """C11's boundary: the unique id carries freshness, so the request's own second passes."""
    write_state_file(tmp_path, "H1", sw.iso(NOW))
    assert sw.handover_check(tmp_path, "H1", sw.iso(NOW))["ok"] is True
    write_state_file(tmp_path, "H1", sw.iso(NOW - timedelta(seconds=1)))
    assert sw.handover_check(tmp_path, "H1", sw.iso(NOW))["ok"] is False


# ---------------------------------------------------------------- review repairs (PR #909)


def test_a_marker_from_another_account_is_intake_and_never_a_watermark(tmp_path):
    """Row 1: tradecraft is public, so only the owner's account can mark a comment.

    A forged kind=post is intake, a forged kind=watermark neither hides itself nor
    creates a second watermark; the owner's marked and unmarked comments are the
    controls."""
    forged_post = comment(301, "<!-- lab:steward:v1 kind=post -->\nhidden?", login="someone")
    forged_mark = comment(302, sw.watermark_body(999, 99, CUTOFF, 1), login="someone")
    owner_post = comment(303, "<!-- lab:steward:v1 kind=post -->\nthe Steward")
    owner_intake = comment(304, "a holder's intake under the owner's token")
    page = sw.Page(REPO, PAGE, [watermark(handled=100), forged_post, forged_mark,
                                owner_post, owner_intake])
    _, mark = page.watermark()
    assert mark["comment_id"] == 100
    assert [int(c["id"]) for c in page.intake(mark["handled"])] == [301, 302, 304]
    forged_note = comment(305, "<!-- lab:steward:v1 kind=read-note read=29 -->", login="someone")
    assert sw.Page(REPO, PAGE, [watermark(), forged_note]).read_note_exists(29) is False
    lab = FakeLab(page_comments=[forged_mark, comment(306, "x")])
    found = sw.wake(lab.github(), tmp_path, PAGE, NOW, REPOS)
    assert "0 watermark comments" in found["error"]


def test_a_failed_wake_still_reports_a_stale_cover(tmp_path, monkeypatch):
    """Row 4: an expired gh login fails the wake's reads; the stale cover still reaches the mod."""
    sw.write_json_atomic(tmp_path / "cover-last-success.json",
                         {"at": sw.iso(NOW - timedelta(hours=3))})
    lab = FakeLab(merges=merges(5, 6), failing_repos=set(REPOS))
    found = sw.wake(lab.github(), tmp_path, PAGE, NOW, REPOS)
    assert found["error"] and found["cover"]["stale"] and not found["cover"].get("noted")
    sw.write_json_atomic(tmp_path / "cover-last-success.json",
                         {"at": sw.iso(sw.now_utc() - timedelta(hours=3))})
    monkeypatch.setattr(sw, "GH_COMMAND", [sys.executable, "-c", "import sys; sys.exit(4)"])
    out = io.StringIO()
    monkeypatch.setattr(sw.sys, "stdout", out)
    assert sw.main(["wake", "--state-dir", str(tmp_path)]) == 1
    reported = json.loads(out.getvalue())
    assert reported["error"] and reported["cover"]["stale"] is True
    assert reported["cover"]["key"].startswith("cover-stale:")


def test_the_stale_note_is_noted_once_across_an_active_handover(tmp_path):
    """Row 4: each stale episode is noted once, on the paused path too."""
    sw.write_json_atomic(tmp_path / "cover-last-success.json",
                         {"at": sw.iso(NOW - timedelta(hours=3))})
    request(tmp_path)
    lab = FakeLab()
    first = sw.wake(lab.github(), tmp_path, PAGE, NOW, REPOS)
    assert first["paused"] and first["cover"]["stale"] and not first["cover"].get("noted")
    sw.mark_woken(tmp_path, PAGE, first["cover"]["key"])
    for _ in range(3):
        again = sw.wake(lab.github(), tmp_path, PAGE, NOW, REPOS)
        assert again["paused"] and again["cover"]["noted"] is True
    failing = FakeLab(failing_repos=set(REPOS))
    sw.handover_step(tmp_path, "load", NOW)  # abandon: the wake reads again, and fails
    assert sw.wake(failing.github(), tmp_path, PAGE, NOW, REPOS)["cover"]["noted"] is True


@pytest.mark.parametrize("event", ["tick", "turn-settled"])
@pytest.mark.parametrize("facts,clears", [
    ({"turn_running": True, "since_turn_complete": 600}, False),   # a turn is running
    ({"turn_running": False, "since_turn_complete": 30}, False),   # inside the settle window
    ({"turn_running": False, "since_turn_complete": None}, False),  # unknown: not quiet
    ({"turn_running": False, "since_turn_complete": 61}, True),
])
def test_clear_only_at_a_quiet_moment_on_every_event(tmp_path, event, facts, clears):
    """Row 3: no /clear while a turn runs or inside the settle window, a tick included."""
    hid = request(tmp_path)
    write_state_file(tmp_path, hid, sw.iso(NOW + timedelta(minutes=1)))
    step = sw.handover_step(tmp_path, event, NOW + timedelta(minutes=2), **facts)
    assert (step["action"] == "clear") is clears
    assert step["state"] == "active"


def test_no_quiet_moment_within_fifteen_minutes_abandons(tmp_path):
    hid = request(tmp_path)
    write_state_file(tmp_path, hid, sw.iso(NOW + timedelta(minutes=1)))
    step = sw.handover_step(tmp_path, "tick", NOW + timedelta(minutes=16), turn_running=True,
                            since_turn_complete=900)
    assert step["state"] == "idle" and "quiet moment" in step["status"]


def test_handover_step_cli_takes_the_turn_facts(tmp_path):
    hid = request(tmp_path)
    write_state_file(tmp_path, hid, sw.iso(NOW + timedelta(minutes=1)))
    base = ["handover-step", "--event", "tick", "--state-dir", str(tmp_path)]
    lab = FakeLab()
    later = NOW + timedelta(minutes=2)
    assert run_cli(base, lab, later)["action"] == "none"
    assert run_cli(base + ["--turn-running", "1", "--since-turn-complete", "90"], lab, later)["action"] == "none"
    assert run_cli(base + ["--since-turn-complete", "90"], lab, later)["action"] == "clear"


def test_a_fresh_install_is_not_stale_until_the_cover_has_had_its_chance(tmp_path):
    """Row 4: no records -> not stale; registered but never run -> stale after two hours."""
    assert sw.cover_state(tmp_path, NOW) == {"last_success": None, "registered": None,
                                             "stale": False, "key": None}
    sw.write_json_atomic(tmp_path / "cover-registered.json", {"at": sw.iso(NOW - timedelta(hours=1))})
    assert sw.cover_state(tmp_path, NOW)["stale"] is False
    sw.write_json_atomic(tmp_path / "cover-registered.json", {"at": sw.iso(NOW - timedelta(hours=2, seconds=1))})
    late = sw.cover_state(tmp_path, NOW)
    assert late["stale"] is True and late["key"] == "cover-stale:none"


def test_staleness_runs_from_the_later_of_registration_and_success(tmp_path):
    sw.write_json_atomic(tmp_path / "cover-last-success.json", {"at": sw.iso(NOW - timedelta(days=3))})
    sw.write_json_atomic(tmp_path / "cover-registered.json", {"at": sw.iso(NOW - timedelta(minutes=10))})
    assert sw.cover_state(tmp_path, NOW)["stale"] is False
    sw.write_json_atomic(tmp_path / "cover-last-success.json", {"at": sw.iso(NOW - timedelta(minutes=5))})
    sw.write_json_atomic(tmp_path / "cover-registered.json", {"at": sw.iso(NOW - timedelta(days=3))})
    assert sw.cover_state(tmp_path, NOW)["stale"] is False


def test_register_records_its_time_and_unregister_removes_it(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(sw, "schtasks", lambda args: calls.append(args) or "SUCCESS")
    lab = FakeLab()
    run_cli(["cover-task", "--register", "--state-dir", str(tmp_path)], lab)
    record = json.loads((tmp_path / "cover-registered.json").read_bytes())
    assert record["at"] == sw.iso(NOW) and record["task"] == sw.TASK_NAME
    assert calls[0][:3] == ["/Create", "/TN", sw.TASK_NAME]
    run_cli(["cover-task", "--unregister", "--state-dir", str(tmp_path)], lab)
    assert not (tmp_path / "cover-registered.json").exists()


def test_install_registers_the_cover_before_the_mod_loads():
    """Row 4: the install order registers the cover first, so the mod's first wake is not stale."""
    depth = (Path(__file__).resolve().parents[2] / "docs" / "cells" / "steward" / "references"
             / "wake-and-cover.md").read_bytes().decode("utf-8")
    install = depth.split("## Install", 1)[1].split("## Undo", 1)[0]
    assert install.index("cover-task --register") < install.index("claude plugin install")


def test_resume_names_where_an_unconfirmed_item_is_recorded(tmp_path):
    """C26 gap 9: the resume says where an item it cannot confirm goes."""
    text = sw.resume_text(tmp_path, "H1", "old", None)
    assert "on #683 with `tools/steward_watch.py post`, naming handover H1" in text
    assert "also goes on the owner board" in text


def test_mod_reads_a_failed_wake_and_gives_every_step_the_turn_facts():
    """Items 2 and 3 in the mod: a failed wake's JSON is still read, and every
    handover step carries whether a turn runs and how long since the last one ended."""
    text = MOD.read_bytes().decode("utf-8")
    assert "await script(['wake'], true)" in text
    assert "(allowError && value.schema_version)" in text
    assert "'--turn-running', state.turnRunning ? '1' : '0'," in text
    assert "'--since-turn-complete', String((Date.now() - state.lastTurnComplete) / 1000)," in text


# ---------------------------------------------------------------- second review repairs (PR #909)


def garbled(lab: FakeLab, repo: str, rows: str):
    """A runner that answers one repository's merge query with the given raw text."""
    def runner(args, input_text=None, timeout=60):
        if args[0] == "pr" and args[args.index("--repo") + 1] == repo:
            lab.calls.append(list(args))
            return rows
        return lab(args, input_text, timeout)
    return sw.GitHub(runner=runner)


@pytest.mark.parametrize("raw,fault", [
    ("<html>not json</html>", "JSONDecodeError"),
    (json.dumps([{"number": 1, "url": "u"}]), "KeyError"),
    (json.dumps([{"number": 1, "mergedAt": "not-a-time", "url": "u"}]), "ValueError"),
])
def test_a_malformed_merge_read_still_reports_the_cover(tmp_path, raw, fault):
    """Row 4: non-JSON gh output or a bad mergedAt is a read fault like any other:
    the wake returns its JSON with the cover's state, and the cover writes its run record."""
    sw.write_json_atomic(tmp_path / "cover-last-success.json",
                         {"at": sw.iso(NOW - timedelta(hours=3))})
    lab = cover_lab(merges=merges(5, 8))
    found = sw.wake(garbled(lab, REPOS[3], raw), tmp_path, PAGE, NOW, REPOS)
    assert found["triggers"] == [] and "merge read failed" in found["error"]
    assert found["cover"]["stale"] is True
    state = tmp_path / "cover"
    outcome = sw.cover(garbled(lab, REPOS[3], raw), state, PAGE, NOW, repos=REPOS)
    assert fault in outcome["reach"][REPOS[3]] and outcome["error"]
    assert json.loads((state / "cover-last-run.json").read_bytes())["error"]
    assert not (state / "cover-last-success.json").exists()
    assert not any(c[0] == "workflow" for c in lab.calls)


def test_a_non_json_page_read_and_an_unreadable_config_are_read_faults(tmp_path, monkeypatch):
    """Faults outside the merge loop take the same path: a page answer that is not
    JSON, and a missing .tradecraft/work.json."""
    def runner(args, input_text=None, timeout=60):
        return "not json"
    found = sw.wake(sw.GitHub(runner=runner), tmp_path, PAGE, NOW, REPOS)
    assert found["error"].startswith("JSONDecodeError") and "cover" in found
    monkeypatch.setattr(sw, "WORK_CONFIG", tmp_path / "missing" / "work.json")
    lab = cover_lab()
    found = sw.wake(lab.github(), tmp_path, PAGE, NOW)
    assert found["error"].startswith("FileNotFoundError")
    outcome = sw.cover(lab.github(), tmp_path / "c", PAGE, NOW)
    assert outcome["error"].startswith("FileNotFoundError")
    assert (tmp_path / "c" / "cover-last-run.json").exists()


def test_the_wake_cli_prints_json_on_a_non_json_gh_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(sw, "GH_COMMAND", [sys.executable, "-c", "print('<html>')"])
    out = io.StringIO()
    monkeypatch.setattr(sw.sys, "stdout", out)
    assert sw.main(["wake", "--state-dir", str(tmp_path)]) == 1
    reported = json.loads(out.getvalue())
    assert reported["error"].startswith("JSONDecodeError") and "cover" in reported


def test_mod_acknowledges_the_stale_note_only_after_delivery():
    """Row 4: the note's key is marked only once the turn carrying it was delivered,
    on the wake-submit path and the prompt.submit path, so a failed delivery leaves
    it eligible on the next tick."""
    text = MOD.read_bytes().decode("utf-8")
    pending = text.split("async function pendingNotes()", 1)[1].split("\n}\n", 1)[0]
    assert "mark-woken" not in pending
    wake_loop = text.split("for (const trigger of found.triggers || []) {", 1)[1].split("\n  }\n", 1)[0]
    assert wake_loop.index("await state.host.submit(") < wake_loop.index("await acknowledge(pending.cover)")
    hook = text.split("on('prompt.submit'", 1)[1].split("\n  })\n", 1)[0]
    assert hook.index("const delivered = await next(") < hook.index("acknowledge(cover)")

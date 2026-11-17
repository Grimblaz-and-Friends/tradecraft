"""The entrance finds pull requests from the issue and says when time ran out."""
import json
from pathlib import Path
import re
import subprocess
import sys
import time

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import preflight
import test_work as base
import work

PRODUCER = "holder-fixture"
CONFIG = work.WorkConfig(marker_producers=frozenset({PRODUCER}))
REPO = "acme/widget"
BASE = f"repos/{REPO}"


def closing_page(numbers, repo=REPO, *, cursor=None):
    return {"data": {"repository": {"issue": {"closedByPullRequestsReferences": {
        "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor},
        "nodes": [{"number": number, "repository": {"nameWithOwner": repo}} for number in numbers],
    }}}}}


def cross_reference(number, repo=REPO):
    return {"event": "cross-referenced", "source": {"type": "issue", "issue": {
        "number": number, "pull_request": {}, "repository": {"full_name": repo}}}}


class Recorder:
    """A fake GitHub that records every request: REST paths and GraphQL query texts."""

    def __init__(self, values, closing=None):
        self.values = values
        self.closing = closing or {None: closing_page([])}
        self.requests = []

    def get(self, endpoint, *, paginate=False):
        self.requests.append(("GET", endpoint))
        value = self.values[endpoint]
        if isinstance(value, Exception):
            raise value
        return value

    def closing_pull_requests(self, query, variables):
        self.requests.append(("GRAPHQL", query))
        assert query == work.CLOSING_PULL_REQUESTS_QUERY
        assert (variables["owner"], variables["name"]) == tuple(REPO.split("/"))
        return self.closing[variables["after"]]


def not_found():
    error = work.WorkError("GitHub GET failed: Not Found (HTTP 404)")
    error.http_status = 404
    return error


def candidates(transport, comments=()):
    issue = {"number": 12, "state": "open", "body": "", "user": {"login": PRODUCER}}
    pulls = work._implementing_candidates(transport, REPO, 12, issue, list(comments), CONFIG)
    return work._candidate_pr_classes(12, issue, list(comments), pulls, CONFIG)


def test_978_candidate_sources():
    timeline = f"{BASE}/issues/12/timeline?per_page=100"
    # A pull request only the timeline reports, its closing reference added by a later edit.
    only_timeline = Recorder({
        timeline: [cross_reference(9)],
        f"{BASE}/pulls/9": {"number": 9, "state": "open", "body": "Edited later\nCloses #12"},
    })
    assert candidates(only_timeline) == ({9}, set())

    # A pull request only the closing graph reports, across two pages.
    only_graph = Recorder({
        timeline: [],
        f"{BASE}/pulls/9": {"number": 9, "state": "closed", "merged_at": "2026-11-01T00:00:00Z",
                            "body": "Fixes #12"},
        f"{BASE}/pulls/10": {"number": 10, "state": "open", "body": "Resolves #12"},
    }, closing={None: closing_page([9], cursor="next"), "next": closing_page([10])})
    assert candidates(only_graph) == ({10}, {9})

    # A timeline pull request whose current body does not close the issue.
    mention = Recorder({
        timeline: [cross_reference(9)],
        f"{BASE}/pulls/9": {"number": 9, "state": "open", "body": "Mentions #12 only"},
    })
    assert candidates(mention) == (set(), set())

    # A cross-reference from another repository is never fetched here, let alone a candidate.
    elsewhere = Recorder({timeline: [cross_reference(158, "other/place")]},
                         closing={None: closing_page([158], "other/place")})
    assert candidates(elsewhere) == (set(), set())
    assert ("GET", f"{BASE}/pulls/158") not in elsewhere.requests

    # The same repository compared without regard to letter case.
    cased = Recorder({
        timeline: [cross_reference(9, "ACME/Widget")],
        f"{BASE}/pulls/9": {"number": 9, "state": "open", "body": "Closes #12"},
    })
    assert candidates(cased) == ({9}, set())

    # A number a marker names that returns 404 is absent rather than an error.
    marker = [{"body": "<!-- tradecraft:implementing-pr:v1 number=44 -->", "user": {"login": PRODUCER}}]
    missing = Recorder({timeline: [], f"{BASE}/pulls/44": not_found()})
    assert candidates(missing, marker) == (set(), set())
    # A 404 for a number only the timeline reports is not swallowed.
    vanished = Recorder({timeline: [cross_reference(9)], f"{BASE}/pulls/9": not_found()})
    with pytest.raises(work.WorkError):
        candidates(vanished)


def test_978_issue_that_is_a_pull_request_skips_the_closing_graph():
    issue = {"number": 12, "state": "open", "body": "", "pull_request": {}}
    transport = Recorder({
        f"{BASE}/issues/12/timeline?per_page=100": [],
        f"{BASE}/pulls/12": {"number": 12, "state": "open", "body": ""},
    })
    pulls = work._implementing_candidates(transport, REPO, 12, issue, [], CONFIG)
    assert work._candidate_pr_classes(12, issue, [], pulls, CONFIG) == ({12}, set())
    assert all(kind == "GET" for kind, _ in transport.requests)


ALLOWED = (
    rf"repos/{REPO}/issues/[0-9]+",
    rf"repos/{REPO}/issues/[0-9]+/(comments|timeline)",
    rf"repos/{REPO}/pulls/[0-9]+(/.+)?",
)


def test_978_state_read_lists_no_pull_requests():
    transport = Recorder({
        f"{BASE}/issues/12": {"number": 12, "state": "open", "body": "", "labels": []},
        f"{BASE}/issues/12/comments": [],
        f"{BASE}/issues/12/timeline?per_page=100": [cross_reference(7), cross_reference(8)],
        f"{BASE}/pulls/7": {"number": 7, "state": "closed", "merged_at": "2026-11-01T00:00:00Z",
                            "body": "Closes #12"},
        f"{BASE}/pulls/8": {"number": 8, "state": "closed", "merged_at": None, "body": "Closes #12"},
    }, closing={None: closing_page([7])})
    state = work.read_state(transport, REPO, 12, CONFIG)
    assert state.merged_pr["number"] == 7 and state.instalment_boundary == "2026-11-01T00:00:00Z"
    for kind, request in transport.requests:
        if kind == "GRAPHQL":
            assert request == work.CLOSING_PULL_REQUESTS_QUERY
            continue
        path = request.split("?", 1)[0]
        assert any(re.fullmatch(pattern, path) for pattern in ALLOWED), request


def owed_refusal(monkeypatch, turns):
    def evaluate(state):
        state.reach = {"state": "reading-required", "current_head": "a" * 40, "turns": turns,
                       "diagnostics": []}
    monkeypatch.setattr(work, "_evaluate_reach", evaluate)
    state = work.WorkState(REPO, 12, {"number": 12, "state": "open", "body": ""}, config=CONFIG)
    return work._reach_refusal(state, "proof")


def turn(reference, uncertainty):
    return {"turn_reference": reference, "after": "b" * 40, "outstanding_paths": [],
            "uncertainty": uncertainty, "state": "unmeasurable", "superset_error": None}


LIMIT = "the 60-second limit (declared by --timeout-seconds)"


def test_978_refusal_advice_by_cause(monkeypatch):
    timed_out = turn("turn-timed", f"ReachTimeout: time ran out before this read finished: {LIMIT}")
    missing = turn("turn-missing", "ReachError: commit object " + "c" * 40
                   + " unavailable: fetch that revision or restore Git read capability")
    detail = owed_refusal(monkeypatch, [timed_out, missing]).detail
    assert f"For turn-timed: time ran out ({LIMIT}); raise the limit and run again." in detail
    restore = re.search(r"For ([^:]+): restore unavailable objects/read capability and retry\.", detail)
    assert restore is not None and restore.group(1) == "turn-missing"
    assert "Account for the computed current-head PR superset." in detail
    assert "should-also-go" in detail

    # Time alone: the advice never says to restore, and the superset sentences carry no restore.
    detail = owed_refusal(monkeypatch, [timed_out]).detail
    advice = detail.split("]. ", 1)[1]
    assert "restore" not in advice.lower() and "fetch" not in advice.lower()
    assert "raise the limit and run again" in advice


def test_978_superset_error_gets_advice_by_cause(monkeypatch):
    def superset_only(reference, error):
        return {**turn(reference, ""), "state": "reading-required", "superset_error": error}

    missing = superset_only("turn-superset", "ReachError: restore required Git objects/read capability "
                            "and retry: blob " + "d" * 40 + " missing")
    detail = owed_refusal(monkeypatch, [missing]).detail
    restore = re.search(r"For ([^:]+): restore unavailable objects/read capability and retry\.", detail)
    assert restore is not None and restore.group(1) == "turn-superset"

    timed = superset_only("turn-superset-timed", f"ReachTimeout: time ran out before this read finished: {LIMIT}")
    advice = owed_refusal(monkeypatch, [timed]).detail.split("]. ", 1)[1]
    assert f"For turn-superset-timed: time ran out ({LIMIT}); raise the limit and run again." in advice
    assert "restore" not in advice.lower()

    # A turn owing a reading with neither trouble adds no advice of its own.
    timed_out = turn("turn-timed", f"ReachTimeout: time ran out before this read finished: {LIMIT}")
    neither = {**turn("turn-plain", ""), "state": "reading-required"}
    alone = owed_refusal(monkeypatch, [timed_out]).detail.split("]. ", 1)[1]
    assert owed_refusal(monkeypatch, [timed_out, neither]).detail.split("]. ", 1)[1] == alone


def test_978_stopped_evaluation_says_time_ran_out(monkeypatch):
    class Stop(work.lifecycle.RunTimeout):
        pass

    def stopped(_state):
        error = Stop("caller deadline exhausted")
        error.limit = LIMIT
        raise error
    monkeypatch.setattr(work, "_reach_readings", stopped)
    state = work.WorkState(REPO, 12, {"number": 12, "state": "open", "body": ""}, config=CONFIG)
    work._evaluate_reach(state)
    uncertainties = [entry["uncertainty"] for entry in state.reach["turns"]]
    assert uncertainties == [f"ReachError: reach evaluation stopped: time ran out: {LIMIT}"]
    assert work._time_ran_out(ValueError("other")) is None


def write_bundle(store, folder, request, run, name="result.md"):
    directory = store / folder
    directory.mkdir(parents=True)
    for suffix, value in ((".request.json", request), (".run.json", run)):
        if value is None:
            continue
        data = value if isinstance(value, bytes) else json.dumps(value).encode("utf-8")
        (directory / (name + suffix)).write_bytes(data)


def test_978_store_readers_answer_the_same_inside_a_scope(tmp_path):
    store = tmp_path / "dispatches"
    schema = work.records.SCHEMA_VERSION
    work_value = f"{REPO}#12"
    done = {"schema_version": schema, "completed_at": "2026-11-01T00:00:00Z", "outcome": "success"}
    write_bundle(store, "a-build", {"schema_version": schema, "work": work_value, "stage": "build"}, done)
    write_bundle(store, "b-other", {"schema_version": schema, "work": "other/repo#1", "stage": "build"}, b"{")
    write_bundle(store, "c-damaged", b"not json", done)
    write_bundle(store, "d-cold-reader-acme-widget-12",
                 {"schema_version": schema, "work": work_value, "stage": "cold-reader"}, b"{broken")
    write_bundle(store, "e-cold-reader-acme-widget-12", None, done)
    outside = (work._matching_bundles(work_value, {"build"}, store),
               work._damaged_cold_reader_record(store, work_value))
    with preflight.scope():
        inside = (work._matching_bundles(work_value, {"build"}, store),
                  work._damaged_cold_reader_record(store, work_value))
        again = (work._matching_bundles(work_value, {"build"}, store),
                 work._damaged_cold_reader_record(store, work_value))
    assert outside == inside == again
    assert [row[1] for row in outside[0]] == [str(store / "a-build" / "result.md.run.json")]
    assert outside[1] is not None


@pytest.mark.parametrize("declared", [None, "90"])
def test_978_main_opens_the_scope_and_the_deadline_shares_its_clock(tmp_path, monkeypatch, declared):
    seen = {}

    def captured(args, **_kwargs):
        seen["scope"], seen["deadline"] = preflight.current(), work.lifecycle.current_deadline()
        return 0
    monkeypatch.setattr(work, "_run", captured)
    argv = ["run", "proof", "--repo", REPO, "--issue", "12", "--root", str(tmp_path)]
    assert work.main(argv + (["--timeout-seconds", declared] if declared else [])) == 0
    assert seen["scope"] is not None and preflight.current() is None
    assert seen["deadline"].started == seen["scope"].started
    assert seen["deadline"].declared is (declared is not None)


def rewrite_run(record_root):
    path = record_root / "build" / "result.md.run.json"
    row = json.loads(path.read_bytes())
    row["attempts"][0]["observed"]["session_id"] = base.OTHER_SESSION
    path.write_bytes(json.dumps(row).encode())


def newer_bundle(record_root):
    base.dispatch_bundle(record_root, name="newer.md", session=base.OTHER_SESSION,
                         completed_at="2026-09-21T10:00:00+00:00")


@pytest.mark.parametrize("change", [rewrite_run, newer_bundle])
def test_978_resume_check_sees_another_writer_inside_a_scope(tmp_path, monkeypatch, change):
    base.ruling_file(tmp_path, monkeypatch)
    fixture = base.state(base.AFFIRMED)
    fixture.record_root = tmp_path / "dispatches"
    base.dispatch_bundle(fixture.record_root)
    root = tmp_path / "implementation"
    root.mkdir()

    # The root is proved after planning and before the check, so the store changes between them.
    def changed_between(*_a, **_k):
        change(fixture.record_root)
        return root, None, False
    monkeypatch.setattr(work, "_dispatch_root", changed_between)
    monkeypatch.setattr(work, "_runtime_argument", lambda vendor, explicit=None: [f"--{vendor}", "fixture"])
    monkeypatch.setattr(work.subprocess, "run", lambda *_a, **_k: pytest.fail("launched a changed source"))
    monkeypatch.setattr(work, "_recipient_run", lambda *_a, **_k: pytest.fail("launched a changed source"))
    with preflight.scope(), pytest.raises(work.WorkError, match="resume source changed after launch planning"):
        work.execute_stage(fixture, work.Decision("floor", True, "resume", "fixture"),
                           tmp_path, None, "holder", floor_command="python fixture-check.py")


def test_978_own_bound_gets_its_own_name_and_advice(monkeypatch):
    stopped = subprocess.TimeoutExpired(["git", "status"], 120)
    with work.lifecycle.deadline_scope(work.lifecycle.stage_deadline("proof", 3600, declared=True)):
        # A read outside the reach adapter is named by the same rule as one inside it.
        own = work._time_ran_out(stopped)
        assert own == work.build_reach._timed_out(stopped).limit == "this read's own 120-second bound"
    advice = owed_refusal(monkeypatch, [turn("turn-own", f"ReachTimeout: time ran out before this read finished: {own}")]
                          ).detail.split("]. ", 1)[1]
    assert f"For turn-own: time ran out ({own}); --timeout-seconds does not lengthen that bound;" in advice
    assert "raise the limit" not in advice and "restore" not in advice.lower()

    spent = work.lifecycle.stage_deadline("proof", 60, started=time.monotonic() - 61, declared=True)
    with work.lifecycle.deadline_scope(spent):
        limit = work._time_ran_out(stopped)
    assert limit == LIMIT
    advice = owed_refusal(monkeypatch, [turn("turn-spent", f"ReachTimeout: time ran out before this read finished: {limit}")]
                          ).detail.split("]. ", 1)[1]
    assert f"For turn-spent: time ran out ({LIMIT}); raise the limit and run again." in advice
    assert "does not lengthen" not in advice


@pytest.mark.parametrize("cursor", [None, ""])
def test_978_closing_page_with_more_and_no_cursor_is_refused(cursor):
    page = closing_page([9])
    page["data"]["repository"]["issue"]["closedByPullRequestsReferences"]["pageInfo"] = {
        "hasNextPage": True, "endCursor": cursor}
    transport = Recorder({}, closing={None: page})
    with pytest.raises(work.WorkError, match="reports another page but names no cursor"):
        work._closing_pull_numbers(transport, REPO, 12)


def test_978_git_writes_are_passed_as_writes_and_reads_stay_strict(tmp_path, monkeypatch):
    seen = []

    def recorded(command, **kwargs):
        seen.append((command[3:], kwargs["writes"]))
        return subprocess.CompletedProcess(command, 0, b"", b"")
    monkeypatch.setattr(work, "run_read", recorded)
    writes = [["worktree", "add", "-b", "branch", str(tmp_path / "copy"), "HEAD"],
              ["push", "--set-upstream", "origin", "HEAD:refs/heads/branch"],
              ["fetch", "--no-tags", "origin", "refs/heads/main"],
              ["merge", "--no-commit", "--no-ff", "a" * 40], ["merge", "--abort"],
              ["add", "--", ":(literal)VERSION"]]
    # write-tree's tree id is read from its output, so it stays strict like any read.
    reads = [["rev-parse", "HEAD"], ["merge-base", "--is-ancestor", "a" * 40, "HEAD"], ["worktree", "list"],
             ["write-tree"], ["merge-file", "--stdout", "a", "b", "c"], ["ls-remote", "--heads", "origin"]]
    for command in writes + reads:
        work._git(command, tmp_path)
    work._git_text(["add", "--", ":(literal)VERSION"], tmp_path, "stage")
    assert seen == [(command, True) for command in writes] + [(command, False) for command in reads] + [
        (["add", "--", ":(literal)VERSION"], True)]

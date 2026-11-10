"""The entrance's hold on launch comparison findings (#906 D7; AC-11, AC-12, AC-14)."""
import json
from pathlib import Path
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(LIB / "tests"))
import launch_bound
import work
from test_work import PRODUCER, RULES, state

DISPATCH = "b" * 32
FINDINGS = [{"id": "3fa9c1d2e0b4", "item": "claude-settings", "path": "s.json", "change": "modified",
             "reason": None},
            {"id": "0a1b2c3d4e5f", "item": "checkout:D:/x", "path": "D:/x/f", "change": "added",
             "reason": None}]


def store_bundle(store, *, write_bound=True, comparison="findings", stage="build"):
    store.mkdir(parents=True, exist_ok=True)
    request = {"schema_version": 2, "dispatch_id": DISPATCH, "work": "example/product#12",
               "stage": stage, "launched_at": "2026-11-03T05:00:00+00:00",
               "requested": {"vendor": "claude"}}
    if write_bound:
        request["write_bound"] = {"file_tools": None, "memory": None, "comparison": {"coverage": []},
                                  "shell": "no OS fence"}
    run = {"schema_version": 2, "dispatch_id": DISPATCH, "lifecycle": "completed",
           "completed_at": "2026-11-03T06:00:00+00:00", "outcome": "success",
           "attempts": [{"vendor": "claude", "launched": True}]}
    if comparison == "findings":
        run["launch_comparison"] = {"schema_version": 1, "status": "findings", "findings": FINDINGS,
                                    "attributed": [], "coverage": []}
    elif comparison == "clean":
        run["launch_comparison"] = {"schema_version": 1, "status": "clean", "findings": [],
                                    "attributed": [], "coverage": []}
    elif isinstance(comparison, dict):
        run["launch_comparison"] = comparison
    (store / "x.md.request.json").write_text(json.dumps(request), encoding="utf-8")
    (store / "x.md.run.json").write_text(json.dumps(run), encoding="utf-8")


def account(*entries, dispatch=DISPATCH):
    return (f"<!-- tradecraft:launch-account:v1 dispatch={dispatch} -->\n\n```json\n"
            + json.dumps({"schema_version": 1, "findings": list(entries)}) + "\n```\n")


OWNER = {"id": "3fa9c1d2e0b4", "party": "owner", "basis": "the owner edited settings"}
SESSION = {"id": "0a1b2c3d4e5f", "party": "session", "basis": "another holder",
           "session": "89abcdef-0123-4567-89ab-cdef01234567"}
DAMAGE = {"id": "0a1b2c3d4e5f", "party": "builder-damage", "basis": "the builder wrote it",
          "owner_report": "told the owner in the holder session",
          "practice_issue": "Grimblaz-and-Friends/tradecraft#999"}


def held(fixture):
    return work._launch_account_refusal(fixture, "use")


def fixture_with(tmp_path, *texts, posted="2026-11-03T07:00:00Z", **bundle):
    fixture = state(*texts)
    for comment in fixture.issue_comments:
        comment["created_at"] = posted  # After the bundle completed at 06:00.
    fixture.record_root = tmp_path / "store"
    store_bundle(fixture.record_root, **bundle)
    work.validate_marker_claims(fixture)
    return fixture


def test_ac11_findings_hold_every_next_stage_and_the_recommendation(tmp_path):
    fixture = fixture_with(tmp_path)
    refusal = held(fixture)
    assert refusal.stage == "launch-account" and refusal.status == "holder-owned"
    assert "3fa9c1d2e0b4" in refusal.detail and "0a1b2c3d4e5f" in refusal.detail
    assert work.decide(fixture, RULES).stage == "launch-account"


@pytest.mark.parametrize("entries", [
    (OWNER,),                                   # misses one id
    (OWNER, SESSION, {**OWNER, "id": "ffffffffffff"}),  # names an extra id
    (OWNER, {k: v for k, v in DAMAGE.items() if k != "owner_report"}),
    (OWNER, {k: v for k, v in DAMAGE.items() if k != "practice_issue"}),
    (OWNER, {k: v for k, v in SESSION.items() if k != "session"}),
    (OWNER, {**SESSION, "extra": "field"}),
    (OWNER, {**SESSION, "party": "nobody"}),
])
def test_ac11_hold_stays_for_an_incomplete_or_invalid_account(tmp_path, entries):
    assert held(fixture_with(tmp_path, account(*entries))) is not None


def test_ac11_hold_stays_for_an_untrusted_author(tmp_path):
    fixture = state()
    fixture.issue_comments = [{"body": account(OWNER, SESSION), "user": {"login": "stranger"}}]
    fixture.record_root = tmp_path / "store"
    store_bundle(fixture.record_root)
    work.validate_marker_claims(fixture)
    assert held(fixture) is not None


@pytest.mark.parametrize("second", [SESSION, DAMAGE])
def test_ac11_hold_releases_only_on_an_exact_account(tmp_path, second):
    fixture = fixture_with(tmp_path, account(OWNER, second))
    assert held(fixture) is None
    report = work._evaluate_launch_findings(fixture)
    assert report["bundles"][0]["state"] == "accounted"
    run = json.loads((fixture.record_root / "x.md.run.json").read_bytes())
    assert run["outcome"] == "success"  # A finding never alters the run.


def test_an_exact_account_posted_before_its_findings_exist_does_not_release(tmp_path):
    early = fixture_with(tmp_path, account(OWNER, SESSION), posted="2026-11-03T05:30:00Z")
    assert held(early) is not None
    assert work._evaluate_launch_findings(early)["bundles"][0]["state"] == "account-required"
    unrecorded = fixture_with(tmp_path / "u", account({"id": "unrecorded", "party": "none-found",
                                                        "basis": "inspected the coverage"}),
                              comparison=None, posted="2026-11-03T04:59:00Z")
    assert held(unrecorded) is not None


@pytest.mark.parametrize("reason", ["coverage could not be planned: boom",
                                    "after-snapshot had no cleanup window: no probe window"])
def test_the_launchers_unrecorded_comparison_shares_the_documented_id(tmp_path, reason):
    comparison = launch_bound.unrecorded(reason)
    assert [finding["id"] for finding in comparison["findings"]] == ["unrecorded"]
    assert comparison["findings"][0]["change"] == "unrecorded"
    assert held(fixture_with(tmp_path, comparison=comparison)) is not None
    released = fixture_with(tmp_path / "r", account({"id": "unrecorded", "party": "none-found",
                                                     "basis": "inspected every covered item"}),
                            comparison=comparison)
    assert held(released) is None


def test_ac11_unrecorded_comparison_is_held_until_named(tmp_path):
    fixture = fixture_with(tmp_path, comparison=None)
    assert held(fixture) is not None
    released = fixture_with(tmp_path, account({"id": "unrecorded", "party": "owner",
                                                "basis": "the launcher was killed"}), comparison=None)
    assert held(released) is None


@pytest.mark.parametrize("basis, releases", [("inspected every covered item; nothing changed", True),
                                               ("", False), ("   ", False)])
def test_none_found_releases_only_with_a_basis(tmp_path, basis, releases):
    entries = [{"id": "unrecorded", "party": "none-found", "basis": basis}]
    fixture = fixture_with(tmp_path, account(*entries), comparison=None)
    assert (held(fixture) is None) is releases
    lawful = fixture_with(tmp_path / "findings", account(
        {**OWNER, "party": "none-found", "basis": "inspected the settings file; unchanged"}, SESSION))
    assert held(lawful) is None


@pytest.mark.parametrize("liveness, held_state", [("active", None), ("stopped", "unrecorded")])
def test_a_running_launch_owes_no_account_until_it_stops(tmp_path, monkeypatch, liveness, held_state):
    fixture = fixture_with(tmp_path, comparison=None)
    run_path = fixture.record_root / "x.md.run.json"
    run = json.loads(run_path.read_bytes())
    run.update(lifecycle="running", completed_at=None)
    run_path.write_text(json.dumps(run), encoding="utf-8")
    monkeypatch.setattr(work.lifecycle, "liveness", lambda _run: liveness)
    entry = work._evaluate_launch_findings(fixture)["bundles"][0]
    if held_state is None:
        assert held(fixture) is None
        assert entry["state"] == "running"
        assert entry["status"] == "not yet recorded: the launch is running"
    else:
        assert held(fixture) is not None and entry["state"] == held_state


def test_ac12_old_records_neither_hold_nor_clear(tmp_path):
    fixture = fixture_with(tmp_path, write_bound=False, comparison=None)
    assert held(fixture) is None
    entry = work._evaluate_launch_findings(fixture)["bundles"][0]
    assert entry == {"bundle": str(fixture.record_root / "x.md.run.json"), "dispatch_id": DISPATCH,
                     "stage": "build", "state": "not-recorded",
                     "status": "not recorded: launched before #906"}


def test_clean_and_use_stage_comparisons_are_clear(tmp_path):
    assert held(fixture_with(tmp_path, comparison="clean", stage="use")) is None


def test_ac14_report_repeats_the_bound_and_comparison():
    request = {"requested": {"vendor": "claude"}, "write_bound": {"shell": "no OS fence"}}
    run = {"lifecycle": "completed", "launch_comparison": {"status": "clean"}}
    attempt = {"vendor": "claude", "launched": True}
    assert work._write_bound_report(request, run, attempt) == {"status": "recorded", "shell": "no OS fence"}
    assert work._launch_comparison_report(request, run, attempt) == {"status": "clean"}
    old = {"requested": {"vendor": "claude"}}
    assert work._write_bound_report(old, run, attempt)["status"] == "not recorded: launched before #906"
    assert work._write_bound_report(old, run, {"vendor": "claude"})["status"].startswith("not applied")
    running = {"lifecycle": "running"}
    assert work._launch_comparison_report(request, running, attempt)["status"].startswith("not yet recorded")
    assert work._launch_comparison_report(request, {"lifecycle": "completed"}, attempt) == {"status": "unrecorded"}
    assert work._write_bound_report({"requested": {"vendor": "codex"}}, run, {"vendor": "codex"}) is None


# An account in parts: comments that count combine, the later naming governs, and the hold says why.
THIRD = {"id": "9e8d7c6b5a40", "item": "checkout:D:/y", "path": "D:/y/g", "change": "modified", "reason": None}
THIRD_COMPARISON = {"schema_version": 1, "status": "findings", "findings": FINDINGS + [THIRD],
                    "attributed": [], "coverage": []}


def posted_in_order(tmp_path, *posts, **bundle):
    """Each post is (body, created_at), or (body, created_at, overrides); ids follow the order given."""
    fixture = fixture_with(tmp_path, **bundle)
    fixture.issue_comments = []
    for number, post in enumerate(posts, start=1):
        body, created = post[0], post[1]
        comment = {"id": number, "body": body, "user": {"login": PRODUCER}, "created_at": created}
        comment.update(post[2] if len(post) > 2 else {})
        if comment.pop("pull_request_comment", False):
            fixture.pr_comments.append(comment)
        else:
            fixture.issue_comments.append(comment)
    work.validate_marker_claims(fixture)
    return fixture


def entry_of(fixture):
    return work._evaluate_launch_findings(fixture)["bundles"][0]


def test_a_split_account_releases(tmp_path):
    fixture = posted_in_order(tmp_path, (account(OWNER), "2026-11-03T07:00:00Z"),
                              (account(SESSION), "2026-11-03T08:00:00Z"))
    assert held(fixture) is None
    entry = entry_of(fixture)
    assert entry["state"] == "accounted" and entry["owed"] == [] and entry["uncounted"] == []
    assert [value["source"] for value in entry["accounts"]] == ["issue-comment:1", "issue-comment:2"]


def test_an_account_over_one_comments_limit_releases_in_parts(tmp_path):
    findings = [{"id": f"{number:012x}", "item": f"checkout:D:/{number}", "path": f"D:/{number}/f",
                 "change": "modified", "reason": None} for number in range(3000)]
    entries = [{**SESSION, "id": finding["id"]} for finding in findings]
    limit = 262144  # GitHub's comment limit in UTF-8 bytes (lib/DESIGN.md#launch-accounts)
    assert len(account(*entries).encode("utf-8")) > limit
    halves = account(*entries[:1500]), account(*entries[1500:])
    assert all(len(half.encode("utf-8")) < limit for half in halves)
    comparison = {"schema_version": 1, "status": "findings", "findings": findings,
                  "attributed": [], "coverage": []}
    fixture = posted_in_order(tmp_path, (halves[0], "2026-11-03T07:00:00Z"),
                              (halves[1], "2026-11-03T08:00:00Z"), comparison=comparison)
    assert held(fixture) is None


def test_a_split_missing_one_finding_holds_and_lists_only_it(tmp_path):
    fixture = posted_in_order(tmp_path, (account(OWNER), "2026-11-03T07:00:00Z"),
                              (account(SESSION), "2026-11-03T08:00:00Z"), comparison=THIRD_COMPARISON)
    refusal = held(fixture)
    assert refusal is not None
    assert refusal.stage == "launch-account" and refusal.reason == "launch-findings-unaccounted"
    assert [finding["id"] for finding in entry_of(fixture)["owed"]] == [THIRD["id"]]
    assert THIRD["id"] in refusal.detail
    assert OWNER["id"] not in refusal.detail and SESSION["id"] not in refusal.detail


@pytest.mark.parametrize("faulty, reason", [
    ((account({**SESSION}, {**OWNER, "id": "ffffffffffff"}), "2026-11-03T08:00:00Z"), "names-unflagged"),
    ((account({k: v for k, v in SESSION.items() if k != "basis"}), "2026-11-03T08:00:00Z"), "malformed"),
    ((account(SESSION), "2026-11-03T08:00:00Z", {"user": {"login": "stranger"}}), "untrusted-author"),
    ((account(SESSION, dispatch="c" * 32), "2026-11-03T08:00:00Z"), "another-launch"),
    ((account(SESSION), "2026-11-03T05:30:00Z"), "before-findings"),
    ((account(SESSION), "2026-11-03T08:00:00Z", {"pull_request_comment": True}), "wrong-surface"),
])
def test_a_comment_that_does_not_count_adds_nothing_and_is_listed_with_why(tmp_path, faulty, reason):
    fixture = posted_in_order(tmp_path, (account(OWNER), "2026-11-03T07:00:00Z"), faulty)
    assert held(fixture) is not None
    entry = entry_of(fixture)
    assert [finding["id"] for finding in entry["owed"]] == [SESSION["id"]]
    assert [(value["source"].rsplit(":", 1)[1], value["reason"]) for value in entry["uncounted"]] == [("2", reason)]
    assert [value["source"] for value in entry["accounts"]] == ["issue-comment:1"]


def test_a_finding_named_twice_releases_with_the_later_comment_governing(tmp_path):
    fixture = posted_in_order(tmp_path, (account(OWNER, SESSION), "2026-11-03T07:00:00Z"),
                              (account(DAMAGE), "2026-11-03T08:00:00Z"))
    assert held(fixture) is None
    entry = entry_of(fixture)
    assert entry["governing"] == {SESSION["id"]: "issue-comment:2"}
    assert [value["source"] for value in entry["accounts"]] == ["issue-comment:1", "issue-comment:2"]


def test_nothing_posted_after_a_release_holds_again(tmp_path):
    posts = [(account(OWNER, SESSION), "2026-11-03T07:00:00Z")]
    assert held(posted_in_order(tmp_path, *posts)) is None
    posts.append((account(OWNER), "2026-11-03T08:00:00Z"))
    fixture = posted_in_order(tmp_path / "b", *posts)
    assert held(fixture) is None and entry_of(fixture)["governing"] == {OWNER["id"]: "issue-comment:2"}
    posts.append((account(OWNER, {**OWNER, "id": "ffffffffffff"}), "2026-11-03T09:00:00Z"))
    fixture = posted_in_order(tmp_path / "c", *posts)
    assert held(fixture) is None
    assert "issue-comment:3" not in [value["source"] for value in entry_of(fixture)["accounts"]]
    posts.append((account({k: v for k, v in OWNER.items() if k != "basis"}), "2026-11-03T10:00:00Z"))
    assert held(posted_in_order(tmp_path / "d", *posts)) is None


def test_an_edit_does_not_reorder_comments(tmp_path):
    # The newer comment has the lower id and comes first, so only created_at can order them.
    fixture = posted_in_order(tmp_path, (account(OWNER, DAMAGE), "2026-11-03T08:00:00Z"),
                              (account(OWNER, SESSION), "2026-11-03T07:00:00Z",
                               {"updated_at": "2026-11-03T09:00:00Z"}))
    assert held(fixture) is None
    assert entry_of(fixture)["governing"][SESSION["id"]] == "issue-comment:1"


def test_a_comment_naming_a_finding_twice_counts_for_nothing(tmp_path):
    fixture = posted_in_order(tmp_path, (account(OWNER, SESSION, OWNER), "2026-11-03T07:00:00Z"),
                              (account(SESSION), "2026-11-03T08:00:00Z"))
    assert held(fixture) is not None
    entry = entry_of(fixture)
    assert [finding["id"] for finding in entry["owed"]] == [OWNER["id"]]
    assert [(value["source"], value["reason"]) for value in entry["uncounted"]] == [("issue-comment:1", "malformed")]


# One comment's text can't break the report; it reads as that comment's fault.
NESTED = (f"<!-- tradecraft:launch-account:v1 dispatch={DISPATCH} -->\n\n```json\n"
          + "[" * 100000 + "]" * 100000 + "\n```\n")
LIST_PARTY = account(OWNER, {**SESSION, "party": []})


@pytest.mark.parametrize("body", [LIST_PARTY, NESTED], ids=["list-party", "nested"])
@pytest.mark.parametrize("author, reason", [("stranger", "untrusted-author"), (PRODUCER, "malformed")])
def test_a_comment_whose_payload_raises_is_listed_and_the_report_stands(tmp_path, body, author, reason):
    fixture = posted_in_order(tmp_path, (account(OWNER, SESSION), "2026-11-03T07:00:00Z"),
                              (body, "2026-11-03T08:00:00Z", {"user": {"login": author}}))
    report = work._evaluate_launch_findings(fixture)
    assert report["status"] == "clear" and held(fixture) is None
    entry = report["bundles"][0]
    assert entry["state"] == "accounted"
    assert [(value["source"], value["reason"]) for value in entry["uncounted"]] == [("issue-comment:2", reason)]


@pytest.mark.parametrize("body", [LIST_PARTY, NESTED], ids=["list-party", "nested"])
def test_a_raising_comment_on_a_change_with_no_launch_leaves_the_report_readable(tmp_path, body):
    fixture = state()
    fixture.issue_comments = [{"id": 1, "body": body, "user": {"login": "stranger"},
                               "created_at": "2026-11-03T08:00:00Z"}]
    fixture.record_root = tmp_path / "empty"
    fixture.record_root.mkdir()
    work.validate_marker_claims(fixture)
    assert work._evaluate_launch_findings(fixture) == {"schema_version": 1, "status": "clear", "bundles": []}


@pytest.mark.parametrize("comparison", [
    {"schema_version": 1, "status": "findings", "findings": [], "attributed": [], "coverage": []},
    {"schema_version": 1, "status": "findings", "findings": ["not a finding"], "attributed": [], "coverage": []},
    {"schema_version": 1, "findings": [], "attributed": [], "coverage": []},
], ids=["empty", "filtered", "no-status"])
def test_a_comparison_that_is_not_clear_holds_with_no_findings_until_a_comment_counts(tmp_path, comparison):
    fixture = fixture_with(tmp_path, comparison=comparison)
    assert held(fixture) is not None
    assert entry_of(fixture)["state"] == "account-required"
    released = posted_in_order(tmp_path / "r", (account(), "2026-11-03T07:00:00Z"), comparison=comparison)
    assert held(released) is None and entry_of(released)["state"] == "accounted"


def test_before_findings_says_which_time_could_not_be_read(tmp_path):
    fixture = posted_in_order(tmp_path, (account(OWNER, SESSION), "not a time"))
    assert "posting time could not be read" in entry_of(fixture)["uncounted"][0]["detail"]
    fixture = posted_in_order(tmp_path / "r", (account(OWNER, SESSION), "2026-11-03T07:00:00Z"))
    run_path = fixture.record_root / "x.md.run.json"
    run = json.loads(run_path.read_bytes())
    run["completed_at"] = None
    run_path.write_text(json.dumps(run), encoding="utf-8")
    entry = entry_of(fixture)
    assert held(fixture) is not None
    assert "findings were recorded could not be read" in entry["uncounted"][0]["detail"]
    assert entry["uncounted"][0]["reason"] == "before-findings"

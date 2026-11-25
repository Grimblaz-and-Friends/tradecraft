"""The release report's section on what the reviewers read, against a real Git history."""
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import reviewers_read as rr


DAY = "2026-11-20T"
READY_AT = DAY + "11:30:00+00:00"


def at(clock):
    return f"{DAY}{clock}:00+00:00"


def git(repo, *arguments, clock=None):
    env = {key: value for key, value in os.environ.items()
           if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"}}
    if clock is not None:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = at(clock)
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
         "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *arguments],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=True)
    return result.stdout.decode("utf-8").strip()


def commit(repo, message, clock):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message, clock=clock)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture(scope="module")
def history(tmp_path_factory):
    """main: A, then D (a base change). The branch: B (the ready head), C (a fix), E (a catch-up merge of main)."""
    repo = tmp_path_factory.mktemp("history")
    git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_bytes(b"one\ntwo\nthree\n")
    (repo / "b.txt").write_bytes(b"base\n")
    (repo / "gone.txt").write_bytes(b"gone\n")
    (repo / "old_name.txt").write_bytes(b"".join(b"line %d\n" % n for n in range(10)))
    (repo / "img.bin").write_bytes(bytes(range(256)))
    shas = {"A": commit(repo, "base", "10:00")}
    git(repo, "checkout", "-q", "-b", "work")
    (repo / "a.txt").write_bytes(b"one\ntwo\nthree\nfour\n")
    shas["B"] = commit(repo, "build", "11:00")
    (repo / "a.txt").write_bytes(b"one\nTWO\nthree\nfour\n")
    (repo / "new.txt").write_bytes(b"new\nfile\n")
    (repo / "gone.txt").unlink()
    (repo / "img.bin").write_bytes(bytes(reversed(range(256))))
    (repo / "old_name.txt").rename(repo / "renamed.txt")
    (repo / "renamed.txt").write_bytes(b"".join(b"line %d\n" % n for n in range(9)) + b"line nine\n")
    shas["C"] = commit(repo, "fix", "13:00")
    git(repo, "checkout", "-q", "main")
    (repo / "b.txt").write_bytes(b"base moved\n")
    shas["D"] = commit(repo, "base moves", "12:00")
    git(repo, "checkout", "-q", "work")
    git(repo, "merge", "-q", "--no-ff", "-m", "catch up", "main", clock="14:00")
    shas["E"] = git(repo, "rev-parse", "HEAD")
    return repo, shas


def git_numstat(repo, old, new):
    """Git's own numstat between two heads, keyed by the path as Git displays it."""
    counts = {}
    for line in git(repo, "diff", "--numstat", "-M", old, new).splitlines():
        added, removed, path = line.split("\t", 2)
        counts[path] = (None if added == "-" else int(added), None if removed == "-" else int(removed))
    return counts


def ready_on(head):
    return {"status": "read", "head": head, "ready_at": READY_AT}


@pytest.fixture(scope="module")
def baseline(history):
    """The ready head's commits and numstat up to the merged head, read once for every section built from them."""
    repo, shas = history
    return {"commits": rr.commits_between(repo, shas["B"], shas["E"], "main"),
            "changed_after": rr.numstat(repo, shas["B"], shas["E"])}


@pytest.fixture
def make(history, baseline):
    """A section of the new order's change, with any input replaced."""
    _, shas = history

    def build(**changes):
        value = {
            "ready": ready_on(shas["B"]),
            "build_began": at("09:30"),
            "cold_launches": [],
            "commits": baseline["commits"],
            "reports": [{"name": "use", "at": at("12:30")}, {"name": "reviewer codex", "at": at("12:00")}],
            "unread_reports": [],
            "first_reading": {"head": shas["C"], "launched_at": at("13:15")},
            "changed_after": baseline["changed_after"],
            "other_reviewer_heads": [],
        }
        value.update(changes)
        return rr.section(**value)
    return build


def test_numstat_counts_the_files_and_lines_git_counts_between_two_heads(history):
    repo, shas = history
    answer = rr.numstat(repo, shas["B"], shas["E"])
    expected = git_numstat(repo, shas["B"], shas["E"])
    shown = {(f"{entry['from']} => {entry['path']}" if "from" in entry else entry["path"]):
             (entry["added"], entry["removed"]) for entry in answer["files"]}
    assert answer["status"] == "read" and shown == expected
    assert answer["added"] == sum(added for added, _ in expected.values() if added is not None)
    assert answer["removed"] == sum(removed for _, removed in expected.values() if removed is not None)
    binary = [entry for entry in answer["files"] if entry.get("binary")]
    assert [entry["path"] for entry in binary] == ["img.bin"] and binary[0]["added"] is None
    assert answer["nothing_changed"] is False and (answer["from"], answer["to"]) == (shas["B"], shas["E"])


def test_reviewers_who_read_the_merged_head_read_nothing_changed_after(history, make):
    repo, shas = history
    answer = rr.numstat(repo, shas["E"], shas["E"])
    assert answer["status"] == "read" and answer["files"] == [] and answer["nothing_changed"] is True
    part = make(ready=ready_on(shas["E"]), commits=[], first_reading=None, changed_after=answer)
    assert "nothing changed between it and the head you merge" in part["sentence"]


def test_a_commit_missing_from_the_objects_is_unknown_naming_it(history, make):
    repo, shas = history
    missing = "0" * 40
    for answer in (rr.numstat(repo, missing, shas["E"]), rr.commits_between(repo, missing, shas["E"], "main")):
        assert answer["status"] == "unknown" and f"commit {missing} is not in the holder's objects" == answer["reason"]
    part = make(changed_after=rr.numstat(repo, missing, shas["E"]))
    assert part["changed_after"]["status"] == "unknown"
    assert "what changed after it is unknown: commit " + missing in part["sentence"]


def test_git_that_cannot_run_leaves_the_numstat_unknown(history):
    repo, shas = history

    def broken(command, root):
        raise OSError("no git here")
    answer = rr.numstat(repo, shas["B"], shas["E"], run=broken)
    assert answer["status"] == "unknown" and "no git here" in answer["reason"]


def test_the_branch_commits_list_its_own_line_and_mark_the_catch_up_merge(history):
    repo, shas = history
    answer = rr.commits_between(repo, shas["B"], shas["E"], "main")
    parents = git(repo, "rev-list", "--parents", "-n", "1", shas["E"]).split()[1:]
    assert parents == [shas["C"], shas["D"]]
    assert answer["status"] == "read"
    assert [(item["sha"], datetime.fromisoformat(item["committed_at"].replace("Z", "+00:00")), item["base_merge"])
            for item in answer["commits"]] == [
        (shas["C"], datetime.fromisoformat(at("13:00")), False), (shas["E"], datetime.fromisoformat(at("14:00")), True)]


def test_a_rewritten_history_leaves_the_commits_unknown(history):
    repo, shas = history
    answer = rr.commits_between(repo, shas["D"], shas["E"], "main")
    assert answer["status"] == "read"
    rewritten = rr.commits_between(repo, shas["C"], shas["D"], "main")
    assert rewritten["status"] == "unknown" and "not an ancestor" in rewritten["reason"]


def test_a_catch_up_merge_is_never_counted_as_a_fix(history, make):
    repo, shas = history
    commits = rr.commits_between(repo, shas["C"], shas["E"], "main")
    assert [commit["base_merge"] for commit in commits["commits"]] == [True]
    part = make(ready=ready_on(shas["C"]), commits=commits, first_reading=None,
                 reports=[{"name": "use", "at": at("15:00")}])
    fix = part["fix_before_last_report"]
    assert fix["status"] == "read" and fix["value"] is False and fix["compared"] == "committer dates"


def test_a_fix_pushed_before_the_last_report_reads_true_naming_it(history, make):
    _, shas = history
    fix = make(reports=[{"name": "use", "at": at("13:30")}])["fix_before_last_report"]
    assert fix["status"] == "read" and fix["value"] is True and fix["commit"] == shas["C"]
    assert fix["last_report"] == {"name": "use", "at": at("13:30")}


def test_an_unread_criterion_report_leaves_no_fix_unknown_and_names_it(history, make):
    _, shas = history
    relay = make(unread_reports=["criterion C3"])["fix_before_last_report"]
    assert relay["status"] == "unknown" and "criterion C3" in relay["reason"] and relay["unread"] == ["criterion C3"]
    assert relay["compared"] == "committer dates"
    found = make(unread_reports=["criterion C3"],
                  reports=[{"name": "use", "at": at("13:30")}])["fix_before_last_report"]
    assert found["status"] == "read" and found["value"] is True and found["commit"] == shas["C"]
    untimed = make(reports=[{"name": "use", "at": at("12:30")},
                            {"name": "criterion C7", "at": None}])["fix_before_last_report"]
    assert untimed["status"] == "unknown" and "criterion C7" in untimed["reason"]
    assert "whether a fix came before the last report is unknown" in make(
        unread_reports=["criterion C3"])["sentence"]


def test_with_every_report_read_and_no_fix_before_them_the_fix_reads_false(make):
    fix = make()["fix_before_last_report"]
    assert fix["status"] == "read" and fix["value"] is False and fix["commit"] is None


def test_the_new_order_reads_no_cold_reading_before_no_fix_before_and_a_reading_that_follows(history, make):
    _, shas = history
    part = make()
    assert part["head"] == {"status": "read", "commit": shas["B"], "ready_at": READY_AT}
    assert part["since_build_began"] == {"status": "read", "seconds": 7200}
    assert part["cold_readings_before"] == {"status": "read", "count": 0}
    assert part["fix_before_last_report"]["value"] is False
    assert part["first_reading"]["head"] == shas["C"] and part["first_reading"]["follows_answers"]["value"] is True
    assert rr.order_of(part) == {"order": "reviewers-first"}
    assert part["sentence"].startswith(
        f"The reviewers read {shas['B'][:7]}, 2.0 hours after the build began and after 0 cold readings; "
        "no fix was pushed before the last report on that head")
    changed = part["changed_after"]
    assert f"{len(changed['files'])} files and +{changed['added']}/-{changed['removed']} lines changed between it " \
           f"and {shas['E'][:7]}, the head you merge (1 binary)" in part["sentence"]


def test_the_earlier_order_reads_a_cold_reading_before_ready_that_precedes_it(history, make):
    _, shas = history
    part = make(cold_launches=[at("11:10"), at("13:15")],
                 first_reading={"head": shas["B"], "launched_at": at("11:10")})
    assert part["cold_readings_before"] == {"status": "read", "count": 1}
    follows = part["first_reading"]["follows_answers"]
    assert follows == {"status": "read", "value": False, "reason": "it precedes the ready step"}
    assert rr.order_of(part) == {"order": "cold-reading-first"}


def test_a_first_reading_of_a_head_before_the_answers_does_not_follow_them(history, make):
    _, shas = history
    stale = make(first_reading={"head": shas["B"], "launched_at": at("13:15")})
    assert stale["first_reading"]["follows_answers"]["value"] is False
    # Launched before the use report came in, so whatever it read it didn't follow the answers to that report.
    early = make(first_reading={"head": shas["B"], "launched_at": at("12:15")})
    assert early["first_reading"]["follows_answers"] == {
        "status": "read", "value": False, "reason": "it was launched before the last report on that head, use"}
    # Launched once every report was in, before any fix: nothing needed answering, so it followed them.
    after_all = make(first_reading={"head": shas["B"], "launched_at": at("12:45")})
    assert after_all["first_reading"]["follows_answers"] == {
        "status": "read", "value": True, "reason": "every report was in and none needed a fix"}
    unread = make(first_reading={"head": shas["C"], "launched_at": at("13:15")}, unread_reports=["criterion C3"])
    assert unread["first_reading"]["follows_answers"]["status"] == "unknown"
    assert "criterion C3" in unread["first_reading"]["follows_answers"]["reason"]
    foreign = make(first_reading={"head": "f" * 40, "launched_at": at("13:15")})
    assert foreign["first_reading"]["follows_answers"]["status"] == "unknown"
    none = make(first_reading=None)
    assert none["first_reading"]["status"] == "none" and "no cold reading has been launched" in none["sentence"]


def test_no_builder_launch_leaves_how_long_after_the_build_began_unknown(make):
    part = make(build_began=None)
    assert part["since_build_began"] == {"status": "unknown", "reason": "no builder launch on record"}
    assert "how long after the build began is unknown: no builder launch on record" in part["sentence"]


def test_unread_cold_launches_leave_the_count_and_the_order_unknown(make):
    part = make(cold_launches=None)
    assert part["cold_readings_before"]["status"] == "unknown" and part["cold_readings_before"]["reason"]
    order = rr.order_of(part)
    assert order["order"] == "unknown" and "were not read" in order["reason"]


def test_an_unreadable_timeline_leaves_every_part_that_needs_the_ready_step_unknown(make):
    part = make(ready=rr.ready_head(None))
    assert part["head"] == {"status": "unknown", "reason": "the pull request's timeline is unreadable"}
    for name in ("since_build_began", "cold_readings_before", "fix_before_last_report"):
        assert part[name]["status"] == "unknown" and part[name]["reason"]
    assert part["first_reading"]["follows_answers"]["status"] == "unknown"
    assert part["sentence"].startswith("Which head the reviewers read is unknown: the pull request's timeline")
    assert rr.order_of(part)["order"] == "unknown"


def test_the_ready_head_is_the_last_commit_before_the_first_ready_event():
    timeline = [
        {"event": "committed", "sha": "1" * 40}, {"event": "committed", "sha": "2" * 40},
        {"event": "ready_for_review", "created_at": READY_AT},
        {"event": "committed", "sha": "3" * 40}, {"event": "convert_to_draft", "created_at": at("12:00")},
        {"event": "ready_for_review", "created_at": at("12:30")},
    ]
    assert rr.ready_head(timeline) == {"status": "read", "head": "2" * 40, "ready_at": READY_AT}


def test_a_pull_request_never_a_draft_has_no_ready_head():
    answer = rr.ready_head([{"event": "committed", "sha": "1" * 40},
                            {"event": "reviewed", "commit_id": "1" * 40, "user": {"login": "codex"}}])
    assert answer["status"] == "unknown" and "never a draft" in answer["reason"]
    early = rr.ready_head([{"event": "ready_for_review", "created_at": READY_AT}])
    assert early["status"] == "unknown" and "no commit precedes" in early["reason"]


def test_each_reviewers_first_review_is_matched_by_login_ignoring_case():
    timeline = [
        {"event": "reviewed", "commit_id": "1" * 40, "submitted_at": at("12:00"),
         "user": {"login": "Codex-Connector[bot]"}},
        {"event": "reviewed", "commit_id": "2" * 40, "submitted_at": at("13:00"),
         "user": {"login": "codex-connector[bot]"}},
        {"event": "reviewed", "commit_id": "3" * 40, "submitted_at": at("12:10"), "user": {"login": "someone"}},
    ]
    reviews = rr.first_reviews(timeline, ["codex-connector[bot]", "absent"])
    assert reviews == {"codex-connector[bot]": {"commit": "1" * 40, "at": at("12:00")}}
    assert rr.other_heads(ready_on("1" * 40), reviews) == []
    assert rr.other_heads(ready_on("9" * 40), reviews) == [{"reviewer": "codex-connector[bot]", "commit": "1" * 40}]


def test_the_timeline_is_read_whole_through_the_transport():
    calls = []

    class Transport:
        def __init__(self, value):
            self.value = value

        def get(self, endpoint, *, paginate=False):
            calls.append((endpoint, paginate))
            return self.value

    assert rr.fetch_timeline(Transport([{"event": "committed"}]), "acme/widget", 7) == [{"event": "committed"}]
    assert calls == [("repos/acme/widget/issues/7/timeline", True)]
    with pytest.raises(ValueError):
        rr.fetch_timeline(Transport({"message": "Not Found"}), "acme/widget", 7)


def test_another_reviewers_head_is_named_in_the_sentence(history, make):
    _, shas = history
    part = make(other_reviewer_heads=[{"reviewer": "claude", "commit": shas["C"]}])
    assert part["other_reviewer_heads"] == [{"reviewer": "claude", "commit": shas["C"]}]
    assert f"(claude read {shas['C'][:7]})" in part["sentence"]


def test_a_merge_carrying_a_change_of_its_own_is_a_fix_not_a_base_merge(tmp_path):
    repo = tmp_path / "evil"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_bytes(b"one\n")
    (repo / "b.txt").write_bytes(b"base\n")
    commit(repo, "base", "10:00")
    git(repo, "checkout", "-q", "-b", "work")
    (repo / "a.txt").write_bytes(b"one\ntwo\n")
    ready = commit(repo, "build", "11:00")
    git(repo, "checkout", "-q", "main")
    (repo / "b.txt").write_bytes(b"base moved\n")
    commit(repo, "base moves", "12:00")
    git(repo, "checkout", "-q", "work")
    git(repo, "merge", "-q", "--no-ff", "--no-commit", "main")
    # The reviewer's fix made inside the catch-up merge, in a file neither side changed that way.
    (repo / "a.txt").write_bytes(b"one\nTWO\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "catch up and fix", clock="13:00")
    merged = git(repo, "rev-parse", "HEAD")
    listed = rr.commits_between(repo, ready, merged, "main")
    assert listed["status"] == "read" and [c["base_merge"] for c in listed["commits"]] == [False]


def test_a_base_git_cannot_place_leaves_the_commits_unknown_not_a_fix(history):
    repo, shas = history
    listed = rr.commits_between(repo, shas["B"], shas["E"], "")
    assert listed["status"] == "unknown" and "merge-base --is-ancestor" in listed["reason"]


def test_a_term_affirmed_after_the_ready_step_leaves_the_builds_start_unknown(make):
    part = make(build_began=at("12:20"))
    assert part["since_build_began"]["status"] == "unknown"
    assert "came after the ready step" in part["since_build_began"]["reason"]
    assert "-" not in part["sentence"].split("after the build began")[0][-12:]


def test_a_reviewers_notice_is_not_taken_for_its_review():
    timeline = [
        {"event": "reviewed", "user": {"login": "coderabbitai[bot]"}, "commit_id": "1" * 40,
         "submitted_at": at("12:00"), "body": "Review skipped: rate limited"},
        {"event": "reviewed", "user": {"login": "coderabbitai[bot]"}, "commit_id": "2" * 40,
         "submitted_at": at("13:00"), "body": "Actionable comments posted: 1"}]
    reviews = rr.first_reviews(timeline, ["coderabbitai[bot]"], counts=lambda event: "skipped" not in event["body"])
    assert reviews == {"coderabbitai[bot]": {"commit": "2" * 40, "at": at("13:00")}}

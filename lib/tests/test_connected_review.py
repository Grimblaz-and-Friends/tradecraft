from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest


LIB = Path(__file__).resolve().parents[1]
ROOT = LIB.parent
FIXTURES = Path(__file__).with_name("fixtures")
sys.path.insert(0, str(LIB))
import connected_review as cr  # noqa: E402


HEAD = "a" * 40
BASE = "b" * 40


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def event() -> dict:
    return fixture("connected_review_event.json")


def pull() -> dict:
    return fixture("connected_review_pull.json")


def api_fixture(monkeypatch, pull_value=None, reviews=None, comments=None):
    pull_value = pull_value or pull()
    reviews = [] if reviews is None else reviews
    comments = [] if comments is None else comments

    def get(endpoint, **_kwargs):
        if endpoint.endswith("/pulls/746"):
            return pull_value
        if endpoint.endswith("/pulls/746/reviews"):
            return reviews
        if endpoint.endswith("/issues/746/comments"):
            return comments
        raise AssertionError(endpoint)

    monkeypatch.setattr(cr, "gh_json", get)
    monkeypatch.setattr(cr, "_configured_reviewers", lambda *_: frozenset({cr.BOT_LOGIN}))


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"draft": True}, "not open and ready"),
        ({"user": {"login": "someone-else"}}, "not authored"),
        ({"head": {"sha": HEAD, "repo": {"id": 77}}}, "fork"),
        ({"head": {"sha": None, "repo": {"id": 908172635}}}, "head or base"),
    ],
)
def test_eligibility_fails_closed_before_secret_work(monkeypatch, change, reason):
    current = pull()
    current.update(change)
    api_fixture(monkeypatch, current)
    result = cr.eligibility(event(), "Grimblaz")
    assert result["admitted"] == "false"
    assert reason in result["reason"]


def test_eligibility_separates_actor_from_pull_request_author(monkeypatch):
    current_event = event()
    current_event["sender"]["login"] = "review-label-bot"
    api_fixture(monkeypatch)
    assert cr.eligibility(current_event, "Grimblaz")["admitted"] == "true"


def test_only_ready_reviewers_label_and_explicit_retry_are_triggers(monkeypatch):
    api_fixture(monkeypatch)
    opened = event()
    opened["action"] = "opened"
    assert cr.eligibility(opened, "Grimblaz")["admitted"] == "false"
    labeled = event()
    labeled["action"] = "labeled"
    labeled["label"] = {"name": "reviewers"}
    assert cr.eligibility(labeled, "Grimblaz")["admitted"] == "true"
    retry = event()
    retry.pop("action")
    retry.pop("pull_request")
    retry["inputs"] = {"pr_number": "746"}
    assert cr.eligibility(retry, "Grimblaz")["admitted"] == "true"


def test_activation_is_read_from_base_configuration(monkeypatch):
    api_fixture(monkeypatch)
    monkeypatch.setattr(cr, "_configured_reviewers", lambda *_: frozenset())
    result = cr.eligibility(event(), "Grimblaz")
    assert result == {
        "admitted": "false",
        "reason": "reviewer is not enabled in the base configuration",
        "repo": "Grimblaz-and-Friends/tradecraft",
        "number": "746",
        "visibility": "public",
        "head": HEAD,
        "base": BASE,
    }


def test_duplicate_suppression_is_scoped_to_current_head(monkeypatch):
    old = fixture("connected_review_reviews.json")
    old[0]["commit_id"] = "c" * 40
    api_fixture(monkeypatch, reviews=old)
    assert cr.eligibility(event(), "Grimblaz")["admitted"] == "true"
    api_fixture(monkeypatch, reviews=fixture("connected_review_reviews.json"))
    result = cr.eligibility(event(), "Grimblaz")
    assert result["admitted"] == "false"
    assert result["reason"] == "current head already has this review"


def test_diff_parser_and_candidate_validator_require_changed_anchor():
    diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -2,2 +2,2 @@
-old
+new
 context
"""
    lines = cr.changed_lines(diff)
    assert lines == {("app.py", "LEFT"): {2}, ("app.py", "RIGHT"): {2}}
    candidate = {
        "id": "one", "path": "app.py", "line": 2, "side": "RIGHT",
        "severity": "P1", "input": "x", "execution_path": "f -> g",
        "wrong_result": "returns old", "evidence": "app.py:2",
    }
    assert cr.validate_candidates({"candidates": [candidate]}, lines) == [candidate]
    candidate["line"] = 3
    with pytest.raises(cr.ReviewError, match="changed line"):
        cr.validate_candidates({"candidates": [candidate]}, lines)


def test_checker_cannot_invent_or_leave_a_candidate_undecided():
    candidate = {
        "id": "one", "path": "app.py", "line": 2, "side": "RIGHT",
        "severity": "P1", "input": "x", "execution_path": "f -> g",
        "wrong_result": "returns old", "evidence": "app.py:2",
    }
    lines = {("app.py", "RIGHT"): {2}}
    invented = {"decisions": [{
        "id": "two", "decision": "keep", "evidence": "proof", "explanation": "shown",
    }]}
    with pytest.raises(cr.ReviewError, match="invented"):
        cr.validate_decisions(invented, [candidate], lines)
    with pytest.raises(cr.ReviewError, match="every finder candidate"):
        cr.validate_decisions({"decisions": []}, [candidate], lines)


def test_checker_drops_uncertain_candidate_and_keeps_proven_one():
    candidates = [
        {"id": name, "path": "app.py", "line": 2, "side": "RIGHT",
         "severity": "P1", "input": "x", "execution_path": "f -> g",
         "wrong_result": "wrong", "evidence": "finder"}
        for name in ("proven", "uncertain")
    ]
    decisions = {"decisions": [
        {"id": "proven", "decision": "keep", "evidence": "app.py:2 proves it",
         "explanation": "the return is observable"},
        {"id": "uncertain", "decision": "drop", "evidence": "",
         "explanation": "the precondition is not established"},
    ]}
    survivors = cr.validate_decisions(decisions, candidates, {("app.py", "RIGHT"): {2}})
    assert [row["id"] for row in survivors] == ["proven"]


def archive_bytes(entries: list[tuple[tarfile.TarInfo, bytes]]) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for info, data in entries:
            archive.addfile(info, io.BytesIO(data))
    return stream.getvalue()


def test_snapshot_export_refuses_traversal_and_represents_symlinks_as_data(tmp_path):
    bad = tarfile.TarInfo("repo/../escape")
    bad.size = 1
    with pytest.raises(cr.ReviewError, match="unsafe path"):
        cr.extract_snapshot(archive_bytes([(bad, b"x")]), tmp_path / "bad")
    link = tarfile.TarInfo("repo/link")
    link.type = tarfile.SYMTYPE
    link.linkname = "../../outside"
    cr.extract_snapshot(archive_bytes([(link, b"")]), tmp_path / "safe")
    assert (tmp_path / "safe" / "link").read_bytes() == b"SPECIAL FILE TARGET: ../../outside\n"
    assert not (tmp_path / "outside").exists()


def test_model_process_has_only_read_tools_and_no_github_credential(tmp_path, monkeypatch):
    snapshot = tmp_path / "snapshot"
    inputs = tmp_path / "input"
    snapshot.mkdir()
    inputs.mkdir()
    monkeypatch.setenv("GH_TOKEN", "must-not-reach-model")
    seen = {}

    def run(command, **kwargs):
        seen.update(command=command, kwargs=kwargs)
        body = {"is_error": False, "structured_output": {"candidates": []}, "usage": {}}
        return subprocess.CompletedProcess(command, 0, json.dumps(body).encode(), b"")

    monkeypatch.setattr(cr, "_run", run)
    value, usage = cr.run_pass(
        "claude", tmp_path / "pass", snapshot, "prompt", cr.FINDER_SCHEMA, "oauth"
    )
    assert value == {"candidates": []}
    assert usage == {}
    command = seen["command"]
    assert command[command.index("--tools") + 1] == "Read,Glob,Grep"
    assert "--restricted" in command and "--safe-mode" in command
    assert command[command.index("--permission-prompts") + 1] == "none"
    environment = seen["kwargs"]["environment"]
    assert environment["CLAUDE_CODE_OAUTH_TOKEN"] == "oauth"
    assert "GH_TOKEN" not in environment


def test_failed_model_process_preserves_observed_usage(tmp_path, monkeypatch):
    snapshot = tmp_path / "snapshot"
    (tmp_path / "input").mkdir()
    snapshot.mkdir()

    def run(command, **_kwargs):
        body = {
            "is_error": True,
            "result": "usage limit reached",
            "usage": {"input_tokens": 17},
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(body).encode(), b"")

    monkeypatch.setattr(cr, "_run", run)
    with pytest.raises(cr.ReviewError, match="usage limit") as raised:
        cr.run_pass("claude", tmp_path / "pass", snapshot, "prompt", cr.FINDER_SCHEMA, "oauth")
    assert raised.value.usage == {"input_tokens": 17}


def test_review_payload_is_one_completed_review_for_clean_or_survivor():
    clean = cr.review_payload([], HEAD, "91-1", {}, {})
    assert clean["event"] == "COMMENT"
    assert clean["commit_id"] == HEAD
    assert clean["comments"] == []
    assert "No candidate survived" in clean["body"]
    survivor = {
        "id": "one", "path": "app.py", "line": 2, "side": "RIGHT",
        "severity": "P1", "input": "x", "execution_path": "f -> g",
        "wrong_result": "returns wrong", "checker_evidence": "app.py:2",
        "checker_explanation": "the bad return is unconditional",
    }
    payload = cr.review_payload([survivor], HEAD, "91-1", {"input_tokens": 1}, {})
    assert len(payload["comments"]) == 1
    assert payload["comments"][0]["path"] == "app.py"
    assert "finder={\"input_tokens\":1}" in payload["body"]


def test_reporter_reconciles_review_and_skip_before_writing(monkeypatch):
    api_fixture(monkeypatch, reviews=fixture("connected_review_reviews.json"))
    assert cr.report_skip(event(), "Grimblaz", "91-1", "failure", None, "91") == {
        "status": "suppressed", "cause": "current head already has this review"
    }
    api_fixture(monkeypatch, comments=fixture("connected_review_comments.json"))
    assert cr.report_skip(event(), "Grimblaz", "91-1", "failure", None, "91") == {
        "status": "already-reported"
    }


def test_reporter_posts_one_cause_specific_notice_and_no_review(monkeypatch):
    calls = []

    def get(endpoint, **kwargs):
        if endpoint.endswith("/pulls/746"):
            return pull()
        if endpoint.endswith("/pulls/746/reviews"):
            return []
        if endpoint.endswith("/issues/746/comments") and kwargs.get("method") == "POST":
            calls.append(kwargs["payload"])
            return {"id": 1}
        if endpoint.endswith("/issues/746/comments"):
            return []
        raise AssertionError(endpoint)

    monkeypatch.setattr(cr, "gh_json", get)
    monkeypatch.setattr(cr, "_configured_reviewers", lambda *_: frozenset({cr.BOT_LOGIN}))
    result = cr.report_skip(
        event(), "Grimblaz", "92-1", "failure", "authentication runtime failure", "92",
        '{"finder":{"input_tokens":17},"checker":{"observed_usage":0,"status":"not-started"}}',
    )
    assert result["status"] == "skipped"
    assert len(calls) == 1
    assert calls[0]["body"].startswith("Review skipped: authentication runtime failure")
    assert "connected-review-attempt:92-1" in calls[0]["body"]
    assert '"input_tokens":17' in calls[0]["body"]


def test_offline_private_worker_gets_the_queue_expiry_cause(monkeypatch):
    monkeypatch.setattr(cr, "gh_json", lambda *_args, **_kwargs: {
        "jobs": [{"name": "review", "conclusion": "cancelled", "runner_name": None}]
    })
    assert cr._job_cause("owner/repo", "92", "cancelled", "private") == (
        "self-hosted review job did not start before GitHub cancelled the queued job"
    )
    assert cr._job_cause("owner/repo", "92", "cancelled", "public") == (
        "hosted review job was cancelled before it started"
    )

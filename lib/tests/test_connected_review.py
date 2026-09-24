from __future__ import annotations

import io
import base64
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
import work  # noqa: E402


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


def test_ready_and_label_events_buy_one_review_per_head(monkeypatch):
    api_fixture(monkeypatch)
    assert cr.eligibility(event(), "Grimblaz")["admitted"] == "true"
    labeled = event()
    labeled["action"] = "labeled"
    labeled["label"] = {"name": "reviewers"}
    api_fixture(monkeypatch, reviews=fixture("connected_review_reviews.json"))
    assert cr.eligibility(labeled, "Grimblaz")["reason"] == (
        "current head already has this review"
    )
    next_head = pull()
    next_head["head"]["sha"] = "c" * 40
    api_fixture(
        monkeypatch, pull_value=next_head,
        reviews=fixture("connected_review_reviews.json"),
    )
    assert cr.eligibility(labeled, "Grimblaz")["admitted"] == "true"


def candidate(**changes):
    value = {
        "id": "one", "path": "app.py", "line": 2, "side": "RIGHT",
        "severity": "P1", "input": "x", "execution_path": "f -> g",
        "wrong_result": "returns old", "evidence": "app.py:2",
    }
    value.update(changes)
    return value


def test_diff_parser_and_candidate_validator_accept_off_diff_finder_anchor():
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
    proposed = candidate(severity="repository-critical")
    assert cr.validate_candidates({"candidates": [proposed]}, lines) == [proposed]
    proposed["line"] = 3
    assert cr.validate_candidates({"candidates": [proposed]}, lines) == [proposed]


def test_diff_parser_anchors_deleted_file_to_old_path():
    diff = """diff --git a/gone.py b/gone.py
deleted file mode 100644
--- a/gone.py
+++ /dev/null
@@ -7,1 +0,0 @@
-removed
"""
    assert cr.changed_lines(diff) == {("gone.py", "LEFT"): {7}}


def test_diff_parser_decodes_git_quoted_paths():
    diff = r'''diff --git "a/sp\303\244 ce.py" "b/sp\303\244 ce.py"
--- "a/sp\303\244 ce.py"
+++ "b/sp\303\244 ce.py"
@@ -1 +1 @@
-old
+new
'''
    decoded = "sp" + chr(0xE4) + " ce.py"
    assert cr.changed_lines(diff) == {
        (decoded, "LEFT"): {1}, (decoded, "RIGHT"): {1},
    }


def test_diff_parser_does_not_count_no_newline_marker():
    diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-old
\\ No newline at end of file
+new
\\ No newline at end of file
"""
    assert cr.changed_lines(diff) == {
        ("app.py", "LEFT"): {1}, ("app.py", "RIGHT"): {1},
    }


def test_diff_parser_uses_hunk_counts_for_header_shaped_content():
    diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -4 +4 @@
--- removed content
+++ added content
diff --git a/next.py b/next.py
--- a/next.py
+++ b/next.py
@@ -1 +1 @@
-old
+new
"""
    assert cr.changed_lines(diff) == {
        ("app.py", "LEFT"): {4}, ("app.py", "RIGHT"): {4},
        ("next.py", "LEFT"): {1}, ("next.py", "RIGHT"): {1},
    }


def test_checker_cannot_invent_or_leave_a_candidate_undecided():
    proposed = candidate()
    lines = {("app.py", "RIGHT"): {2}}
    invented = {"decisions": [{
        "id": "two", "decision": "keep", "evidence": "proof", "explanation": "shown",
    }]}
    with pytest.raises(cr.ReviewError, match="invented"):
        cr.validate_decisions(invented, [proposed], lines)
    with pytest.raises(cr.ReviewError, match="every finder candidate"):
        cr.validate_decisions({"decisions": []}, [proposed], lines)


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


def test_checker_off_diff_survivor_moves_to_single_review_body():
    proposed = candidate(line=99)
    decisions = {"decisions": [{
        "id": "one", "decision": "keep", "evidence": "app.py:99 proves it",
        "explanation": "the wrong result is established",
    }]}
    survivors = cr.validate_decisions(decisions, [proposed], {("app.py", "RIGHT"): {2}})
    assert survivors[0]["inline"] is False
    payload = cr.review_payload(survivors, HEAD, "91", {}, {})
    assert payload["comments"] == []
    assert "`app.py:99`" in payload["body"]


def test_checker_malformed_anchor_still_fails_the_run():
    decisions = {"decisions": [{
        "id": "one", "decision": "keep", "evidence": "proof",
        "explanation": "shown", "line": 0,
    }]}
    with pytest.raises(cr.ReviewError, match="malformed anchor"):
        cr.validate_decisions(decisions, [candidate()], {("app.py", "RIGHT"): {2}})


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
    value, usage, trace = cr.run_pass(
        "claude", tmp_path / "pass", snapshot, "prompt", cr.FINDER_SCHEMA, "oauth",
        effort=cr.FINDER_EFFORT,
    )
    assert value == {"candidates": []}
    assert usage == {}
    assert trace == []
    command = seen["command"]
    assert command[command.index("--tools") + 1] == "Read,Glob,Grep"
    assert command[command.index("--effort") + 1] == cr.FINDER_EFFORT
    assert "--restricted" in command and "--safe-mode" in command
    assert command[command.index("--permission-prompts") + 1] == "none"
    assert json.loads(command[command.index("--mcp-config") + 1]) == {
        "mcpServers": {},
    }
    environment = seen["kwargs"]["environment"]
    assert environment["CLAUDE_CODE_OAUTH_TOKEN"] == "oauth"
    assert "GH_TOKEN" not in environment
    profile = tmp_path / "pass" / "profile"
    assert environment["HOME"] == str(profile)
    assert environment["USERPROFILE"] == str(profile)
    assert environment["XDG_CONFIG_HOME"] == str(profile / "config")
    assert environment["CLAUDE_CONFIG_DIR"] == str(profile / "claude")
    assert Path(seen["kwargs"]["cwd"]) != snapshot
    assert Path(command[command.index("--add-dir") + 1]) == snapshot
    assert seen["kwargs"]["input_bytes"].startswith(b"prompt")


def test_model_stream_keeps_structured_output_tool_uses_and_hook_events(tmp_path, monkeypatch):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    events = [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"content": [{
            "type": "tool_use", "name": "Read", "input": {"file_path": "app.py"},
        }]}},
        {"type": "system", "subtype": "hook_started", "hook_name": "PreToolUse"},
        {
            "type": "result", "is_error": False,
            "structured_output": {"candidates": []},
            "usage": {"input_tokens": 3},
        },
    ]

    def run(command, **_kwargs):
        output = "\n".join(json.dumps(event) for event in events).encode()
        return subprocess.CompletedProcess(command, 0, output, b"")

    monkeypatch.setattr(cr, "_run", run)
    value, usage, trace = cr.run_pass(
        "claude", tmp_path / "pass", snapshot, "prompt", cr.FINDER_SCHEMA, "oauth",
        effort=cr.FINDER_EFFORT,
    )
    assert value == {"candidates": []}
    assert usage == {"input_tokens": 3}
    assert trace == [
        {"tool": "Read", "input": {"file_path": "app.py"}},
        {"event": "hook_started"},
    ]


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
        cr.run_pass(
            "claude", tmp_path / "pass", snapshot, "prompt", cr.FINDER_SCHEMA, "oauth",
            effort=cr.FINDER_EFFORT,
        )
    assert raised.value.usage == {"input_tokens": 17}


def test_subprocess_timeout_becomes_named_review_failure(monkeypatch):
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["claude"], 3600)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(cr.ReviewError, match="command timed out.*3600 seconds"):
        cr._run(["claude"], timeout=3600)


def test_repository_rules_are_only_the_named_base_section(monkeypatch):
    agents = """# Repository

private preface

## Code Review Rules

Use the local severity bar.

### Detail

Deletions count.

## Another section

Do not send this.
"""

    def get(endpoint, **_kwargs):
        assert endpoint.endswith(f"/contents/AGENTS.md?ref={BASE}")
        return {
            "encoding": "base64",
            "content": base64.b64encode(agents.encode()).decode(),
        }

    monkeypatch.setattr(cr, "gh_json", get)
    rules = cr.repository_review_rules("owner/repo", BASE)
    assert rules.startswith("## Code Review Rules")
    assert "Use the local severity bar" in rules and "### Detail" in rules
    assert "private preface" not in rules and "Another section" not in rules


def test_missing_repository_rules_are_named_in_prompt(monkeypatch):
    monkeypatch.setattr(
        cr, "gh_json", lambda *_args, **_kwargs: (
            _ for _ in ()
        ).throw(cr.ReviewError("gh: Not Found (HTTP 404)"))
    )
    assert cr.repository_review_rules("owner/repo", BASE) == (
        "No root ## Code Review Rules section exists at the base revision."
    )


def test_repository_rules_api_failure_is_not_mistaken_for_no_rules(monkeypatch):
    monkeypatch.setattr(
        cr, "gh_json", lambda *_args, **_kwargs: (
            _ for _ in ()
        ).throw(cr.ReviewError("gh: service unavailable (HTTP 503)"))
    )
    with pytest.raises(cr.ReviewError, match="HTTP 503"):
        cr.repository_review_rules("owner/repo", BASE)


def execute_fixture(monkeypatch, tmp_path, pass_results, *, current_head=HEAD, post_error=None):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth")
    monkeypatch.setattr(cr, "eligibility", lambda *_: {
        "admitted": "true", "repo": "owner/repo", "number": "746",
        "visibility": "public", "head": HEAD, "base": BASE,
    })
    monkeypatch.setattr(cr, "completed_review_at_head", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cr, "completed_review_for_attempt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cr, "verify_managed_settings", lambda: None)
    monkeypatch.setattr(cr, "verify_claude_version", lambda *_: None)

    def export(_repo, _head, _base, root):
        snapshot = root / "snapshot"
        inputs = root / "input"
        snapshot.mkdir()
        inputs.mkdir()
        diff = inputs / "pull-request.diff"
        rules = inputs / "repository-rules.md"
        diff.write_text(
            "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
            "@@ -2 +2 @@\n-old\n+new\n",
            encoding="utf-8",
        )
        rules.write_text("## Code Review Rules\n\nLocal rules.\n", encoding="utf-8")
        return snapshot, diff, rules

    monkeypatch.setattr(cr, "export_inputs", export)
    outcomes = iter(pass_results)

    def run(*_args, **_kwargs):
        value = next(outcomes)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(cr, "run_pass", run)

    def gh(endpoint, **kwargs):
        if endpoint.endswith("/pulls/746"):
            return {"head": {"sha": current_head}}
        if endpoint.endswith("/pulls/746/reviews") and kwargs.get("method") == "POST":
            if post_error is not None:
                raise post_error
            return {"id": 1}
        raise AssertionError(endpoint)

    monkeypatch.setattr(cr, "gh_json", gh)
    finder = tmp_path / "finder.md"
    checker = tmp_path / "checker.md"
    finder.write_text("finder", encoding="utf-8")
    checker.write_text("checker", encoding="utf-8")
    return finder, checker


def run_execute(finder, checker):
    return cr.execute_review(
        event(), "Grimblaz", "92", ["claude.cmd"], cr.DEFAULT_CLAUDE_VERSION,
        finder, checker,
    )


def test_execute_review_preserves_both_pass_usages_on_validation_failure(tmp_path, monkeypatch):
    finder, checker = execute_fixture(monkeypatch, tmp_path, [
        ({"candidates": [candidate()]}, {"input_tokens": 11}, []),
        ({"decisions": [{
            "id": "invented", "decision": "keep", "evidence": "x", "explanation": "x",
        }]}, {"input_tokens": 22}, []),
    ])
    with pytest.raises(cr.ReviewError, match="invented") as raised:
        run_execute(finder, checker)
    assert raised.value.usage == {
        "finder": {"input_tokens": 11}, "checker": {"input_tokens": 22},
    }


def test_execute_review_preserves_usage_when_head_turns_stale(tmp_path, monkeypatch):
    finder, checker = execute_fixture(monkeypatch, tmp_path, [
        ({"candidates": []}, {"input_tokens": 11}, []),
        ({"decisions": []}, {"input_tokens": 22}, []),
    ], current_head="c" * 40)
    with pytest.raises(cr.ReviewError, match="head changed") as raised:
        run_execute(finder, checker)
    assert raised.value.usage["finder"] == {"input_tokens": 11}
    assert raised.value.usage["checker"] == {"input_tokens": 22}


def test_execute_review_preserves_usage_on_publication_failure(tmp_path, monkeypatch):
    finder, checker = execute_fixture(monkeypatch, tmp_path, [
        ({"candidates": []}, {"input_tokens": 11}, []),
        ({"decisions": []}, {"input_tokens": 22}, []),
    ], post_error=cr.ReviewError("publication transport failed"))
    with pytest.raises(cr.ReviewError, match="publication transport") as raised:
        run_execute(finder, checker)
    assert raised.value.usage["finder"] == {"input_tokens": 11}
    assert raised.value.usage["checker"] == {"input_tokens": 22}


def test_execute_review_names_timeout_and_preserves_prior_pass_usage(tmp_path, monkeypatch):
    finder, checker = execute_fixture(monkeypatch, tmp_path, [
        ({"candidates": [candidate()]}, {"input_tokens": 11}, []),
        cr.ReviewError("command timed out (claude.cmd) after 3600 seconds"),
    ])
    with pytest.raises(cr.ReviewError, match="command timed out") as raised:
        run_execute(finder, checker)
    assert raised.value.usage == {
        "finder": {"input_tokens": 11}, "checker": {"status": "unavailable"},
    }


def test_review_payload_is_one_completed_review_for_clean_or_survivor():
    clean = cr.review_payload([], HEAD, "91", {}, {})
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
    payload = cr.review_payload([survivor], HEAD, "91", {"input_tokens": 1}, {})
    assert len(payload["comments"]) == 1
    assert payload["comments"][0]["path"] == "app.py"
    assert "finder={\"input_tokens\":1}" in payload["body"]


def test_reporter_reconciles_review_and_skip_before_writing(monkeypatch):
    reviews = fixture("connected_review_reviews.json")
    reviews[0]["commit_id"] = "c" * 40
    api_fixture(monkeypatch, reviews=reviews)
    assert cr.report_skip(event(), "Grimblaz", "91", "failure", None, "91") == {
        "status": "reviewed"
    }
    api_fixture(monkeypatch, comments=fixture("connected_review_comments.json"))
    assert cr.report_skip(event(), "Grimblaz", "91", "failure", None, "91") == {
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
        event(), "Grimblaz", "92", "failure", "authentication runtime failure", "92",
        '{"finder":{"input_tokens":17},"checker":{"observed_usage":0,"status":"not-started"}}',
    )
    assert result["status"] == "skipped"
    assert len(calls) == 1
    assert calls[0]["body"].startswith("Review skipped: authentication runtime failure")
    assert "connected-review-attempt:92" in calls[0]["body"]
    assert '"input_tokens":17' in calls[0]["body"]


def test_reporter_posts_prepare_failure_only_after_rederiving_eligibility(monkeypatch):
    calls = []

    def get(endpoint, **kwargs):
        if endpoint.endswith("/pulls/746"):
            return pull()
        if endpoint.endswith("/pulls/746/reviews"):
            return []
        if endpoint.endswith("/issues/746/comments") and kwargs.get("method") == "POST":
            calls.append(kwargs["payload"]["body"])
            return {"id": 1}
        if endpoint.endswith("/issues/746/comments"):
            return []
        raise AssertionError(endpoint)

    monkeypatch.setattr(cr, "gh_json", get)
    monkeypatch.setattr(cr, "_configured_reviewers", lambda *_: frozenset({cr.BOT_LOGIN}))
    result = cr.report_skip(
        event(), "Grimblaz", "93", "skipped", None, "93",
        prepare_result="failure",
    )
    assert result["status"] == "skipped"
    assert calls[0].startswith("Review skipped: preparation job failure")
    assert '"status":"not-started"' in calls[0]


def test_reporter_prepare_failure_posts_nothing_when_eligibility_is_unreadable(monkeypatch):
    posts = []

    def get(endpoint, **kwargs):
        if endpoint.endswith("/pulls/746/reviews"):
            return []
        if endpoint.endswith("/issues/746/comments") and kwargs.get("method") == "POST":
            posts.append(kwargs["payload"])
            return {"id": 1}
        raise cr.ReviewError("eligibility metadata unavailable")

    monkeypatch.setattr(cr, "gh_json", get)
    with pytest.raises(cr.ReviewError, match="eligibility metadata unavailable"):
        cr.report_skip(
            event(), "Grimblaz", "93", "skipped", None, "93",
            prepare_result="failure",
        )
    assert posts == []


def test_attempt_identity_is_run_id_not_reporter_retry(monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "700")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "4")
    args = cr.parser().parse_args([
        "report", "--event", "event.json", "--owner-login", "Grimblaz",
        "--review-result", "failure", "--run-id", "700",
    ])
    assert args.attempt == "700"


def test_main_resolves_windows_compatible_claude_command(tmp_path, monkeypatch):
    event_path = tmp_path / "event.json"
    finder = tmp_path / "finder.md"
    checker = tmp_path / "checker.md"
    event_path.write_text(json.dumps(event()), encoding="utf-8")
    finder.write_text("finder", encoding="utf-8")
    checker.write_text("checker", encoding="utf-8")
    seen = {}
    monkeypatch.setattr(cr, "resolve_command", lambda vendor, explicit: ["claude.cmd"])

    def execute(*args):
        seen["executable"] = args[3]
        return {"status": "reviewed"}

    monkeypatch.setattr(cr, "execute_review", execute)
    assert cr.main([
        "review", "--event", str(event_path), "--owner-login", "Grimblaz",
        "--attempt", "700", "--finder-prompt", str(finder),
        "--checker-prompt", str(checker),
    ]) == 0
    assert seen["executable"] == ["claude.cmd"]


def test_generated_reviews_and_all_skip_causes_have_correct_entrance_credit():
    config = work.WorkConfig(connected_reviewers=frozenset({cr.BOT_LOGIN}))

    def receipt(*, review_body=None, comment_body=None):
        state = work.WorkState("owner/repo", 746, {}, config=config)
        if review_body is not None:
            state.reviews = [{
                "id": 1, "body": review_body, "user": {"login": cr.BOT_LOGIN},
            }]
        if comment_body is not None:
            state.pr_comments = [{
                "id": 2, "body": comment_body, "user": {"login": cr.BOT_LOGIN},
            }]
        return work._reviewer_receipts(state)[0]["result"]

    clean = cr.review_payload([], HEAD, "700", {}, {})["body"]
    survivor = candidate(inline=True)
    survivor.update({
        "checker_evidence": "proof", "checker_explanation": "shown",
    })
    findings = cr.review_payload([survivor], HEAD, "701", {}, {})["body"]
    assert receipt(review_body=clean) == "present"
    assert receipt(review_body=findings) == "present"
    for cause in (
        "usage limit", "authentication runtime failure", "malformed output",
        "command timed out", "pull request head changed during review",
        "publication transport failure", "self-hosted review job did not start",
        "preparation job failure",
    ):
        body = f"Review skipped: {cause}\n\nUsage unavailable.\n\n<!-- connected-review-attempt:9 -->"
        assert work._review_notice(body) == "review skipped"
        assert receipt(comment_body=body) == "notice-only"


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

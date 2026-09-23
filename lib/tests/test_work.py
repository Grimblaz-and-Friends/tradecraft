from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import work


RULES = work.load_use_rules(LIB / "use-rules.json")
SHA = "a" * 40
AFFIRMED = """<!-- tradecraft:affirmed-brief:v1 -->
Review risk: ordinary
Review lane: connected
"""
ARTIFACT = "<!-- tradecraft:artifact:v1 status=draft -->"
WOULD = "<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=qualified -->"
HOLDER = "<!-- tradecraft:holder-reading:v1 result=no-amendment -->"
FLOOR = f"<!-- tradecraft:floor:v1 head={SHA} status=pass -->"
USE = f"<!-- tradecraft:use:v1 head={SHA} status=pass changed=false staffing_status=qualified -->"
REVIEWED = "<!-- tradecraft:connected-reviewer:v1 name=fixture status=complete -->"
WOULD_NOT = "<!-- tradecraft:cold-verdict:v1 verdict=would-not staffing_status=qualified -->"
PRODUCER = "holder-fixture"
REVIEWER = "reviewer-fixture[bot]"
SESSION = "01234567-89ab-cdef-0123-456789abcdef"
OTHER_SESSION = "89abcdef-0123-4567-89ab-cdef01234567"
CONFIG = work.WorkConfig(
    connected_reviewers=frozenset({REVIEWER}),
    marker_producers=frozenset({PRODUCER}),
)


def git(root, *arguments, check=True):
    return subprocess.run(
        ["git", "-C", str(root), *arguments], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
    )


def repository(tmp_path, name="repository", *, ignore_worktrees=True):
    root = tmp_path / name
    root.mkdir()
    subprocess.run(
        ["git", "init", str(root)], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    (root / "fixture.txt").write_bytes(b"fixture\n")
    tracked = ["fixture.txt"]
    if ignore_worktrees:
        (root / ".gitignore").write_bytes(b".claude/worktrees/\n")
        tracked.append(".gitignore")
    git(root, "add", *tracked)
    git(
        root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "fixture",
    )
    return root.resolve()


def registry_row(root, holder, branch, *, issue=12, active=True):
    return {
        "root": str(root.resolve()), "holder_root": str(holder.resolve()),
        "branch": branch, "repository": "example/product", "issue": issue,
        "instalment": None, "active": active,
        "holder_session_id": "holder-session",
        "holder_write_guard": "unavailable",
        "revision_before": None, "status_before": None,
    }


def write_registry_rows(rows):
    work.write_registry({"schema_version": 1, "worktrees": rows})


def state(*texts, pr=False, draft=True, paths=None, issue_state="open",
          reviewer_ran=False, config=CONFIG):
    comments = [{"body": text, "user": {"login": PRODUCER}} for text in texts]
    pull = None
    if pr:
        pull = {"number": 7, "state": "open", "draft": draft, "merged_at": None,
                "head": {"sha": SHA}}
    fixture = work.WorkState(
        "example/product", 12,
        {"number": 12, "state": issue_state, "body": "", "labels": [],
         "user": {"login": PRODUCER}},
        issue_comments=comments, pr=pull, changed_paths=paths or ["lib/runtime.py"],
        config=config,
    )
    if reviewer_ran:
        fixture.pr_comments = [{"body": "review summary", "user": {"login": REVIEWER}}]
    return fixture


@pytest.mark.parametrize(("fixture", "expected"), [
    (state(), ("convergence", False, None)),
    (state(AFFIRMED), ("artifact", True, "fresh")),
    (state(AFFIRMED, ARTIFACT), ("cold-seat", True, "fresh")),
    (state(AFFIRMED, ARTIFACT, "<!-- tradecraft:cold-verdict:v1 verdict=would-not staffing_status=qualified -->"),
     ("artifact", True, "resume")),
    (state(AFFIRMED, ARTIFACT, WOULD), ("holder-read", False, None)),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER), ("build", True, "fresh")),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, pr=True), ("floor", True, "resume")),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, pr=True), ("use", False, None)),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR,
           f"<!-- tradecraft:use:v1 head={SHA} status=pass changed=true staffing_status=qualified -->", pr=True),
     ("build", True, "resume")),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE, pr=True),
     ("ready-reviewers", False, None)),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE, pr=True, draft=False),
     ("waiting", False, None)),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE, pr=True, draft=False,
           reviewer_ran=True),
     ("release-report", False, None)),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
           "<!-- tradecraft:panel-stage:v1 stage=cold-pass status=complete -->",
           "<!-- tradecraft:panel-stage:v1 stage=defense status=complete -->",
           "<!-- tradecraft:panel-stage:v1 stage=floor-fixes status=complete -->",
           pr=True, draft=False, reviewer_ran=True), ("release-report", False, None)),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
           pr=True, draft=False, reviewer_ran=True, issue_state="closed"),
     ("terminal", False, None)),
])
def test_each_state_table_row_routes_exactly_one_stage(fixture, expected):
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.dispatch, decision.continuity) == expected


def test_would_not_without_a_newer_draft_resumes_artifact():
    decision = work.decide(state(AFFIRMED, ARTIFACT, WOULD_NOT), RULES)
    assert (decision.stage, decision.dispatch, decision.continuity) == (
        "artifact", True, "resume",
    )


def test_newer_artifact_draft_after_would_not_routes_a_fresh_cold_seat():
    fixture = state(AFFIRMED, ARTIFACT, WOULD_NOT, ARTIFACT)
    fixture.issue_comments[1]["created_at"] = "2026-09-23T10:00:00Z"
    fixture.issue_comments[2]["created_at"] = "2026-09-23T11:00:00Z"
    fixture.issue_comments[3]["created_at"] = "2026-09-23T12:00:00Z"
    fixture.issue_comments = [
        fixture.issue_comments[0], fixture.issue_comments[3],
        fixture.issue_comments[1], fixture.issue_comments[2],
    ]
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.dispatch, decision.continuity) == (
        "cold-seat", True, "fresh",
    )
    assert decision.reason == "newer-artifact-draft-after-would-not"


def test_second_would_not_reaches_the_two_round_holder_cap():
    fixture = state(AFFIRMED, ARTIFACT, WOULD_NOT, ARTIFACT, WOULD_NOT)
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.dispatch, decision.continuity, decision.status) == (
        "artifact-cap", False, None, "holder-owned",
    )
    assert decision.reason == "artifact-cold-round-cap-reached"


def test_bought_use_returns_an_actionable_holder_handoff():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, pr=True)
    decision = work.decide(fixture, RULES)

    assert decision.reason == "current-head-use-absent"
    assert decision.detail is not None
    for step in (
        "charter and time-box",
        "build and inspect the consumer tree",
        "dispatch the consumer through lib/dispatch_seat.py",
        "capability the job requires",
        "write the session note",
        "post the current-head use marker",
    ):
        assert step in decision.detail.lower()


def test_red_check_routes_floor_even_with_a_current_head_floor_marker():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, pr=True)
    fixture.checks = [{"conclusion": "failure"}]
    assert work.decide(fixture, RULES).stage == "floor"


@pytest.mark.parametrize("reverse", [False, True])
def test_latest_same_name_check_run_wins_independent_of_api_order(reverse):
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, pr=True)
    checks = [
        {"id": 1, "name": "floor", "started_at": "2026-09-22T10:00:00Z",
         "status": "completed", "conclusion": "failure"},
        {"id": 2, "name": "floor", "started_at": "2026-09-22T11:00:00Z",
         "status": "completed", "conclusion": "success"},
    ]
    fixture.checks = list(reversed(checks)) if reverse else checks
    decision = work.decide(fixture, RULES)
    assert decision.stage == "use"
    assert decision.latest_checks[0]["id"] == 2


def test_latest_pending_check_waits_without_resurrecting_an_older_red():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, pr=True)
    fixture.checks = [
        {"id": 1, "name": "floor", "started_at": "2026-09-22T10:00:00Z",
         "status": "completed", "conclusion": "failure"},
        {"id": 2, "name": "floor", "started_at": "2026-09-22T11:00:00Z",
         "status": "in_progress", "conclusion": None},
    ]
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.reason) == ("waiting", "latest-check-run-pending")


def test_builder_return_without_pull_request_is_a_holder_owned_handoff():
    fixture = state(
        AFFIRMED, ARTIFACT, WOULD, HOLDER,
        f"<!-- tradecraft:builder-session:v1 session={SESSION} -->",
    )
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.dispatch, decision.status) == (
        "open-pull-request", False, "holder-owned",
    )


def test_undisposed_reviewer_thread_routes_only_the_disposition_stage():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False)
    fixture.review_comments = [{
        "id": 41, "body": "finding", "commit_id": SHA,
        "user": {"login": REVIEWER, "type": "Bot"},
    }]
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.continuity, decision.detail) == (
        "review-disposition", "resume", "41",
    )


def test_earlier_head_thread_stays_undisposed_after_reviewer_runs_at_current_head():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False, reviewer_ran=True)
    fixture.review_comments = [{
        "id": 41, "body": "earlier finding", "commit_id": "b" * 40,
        "user": {"login": REVIEWER, "type": "Bot"},
    }]
    assert work.decide(fixture, RULES).stage == "review-disposition"


def test_earlier_head_review_with_a_listed_disposition_reaches_release_report():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False)
    fixture.review_comments = [
        {"id": 41, "body": "earlier finding", "commit_id": "b" * 40,
         "user": {"login": REVIEWER, "type": "Bot"}},
        {"id": 42, "in_reply_to_id": 41, "body": "fixed",
         "user": {"login": PRODUCER}},
    ]
    assert work.decide(fixture, RULES).stage == "release-report"


def test_unlisted_disposition_author_is_ignored_and_named():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False, reviewer_ran=True)
    fixture.review_comments = [
        {"id": 41, "body": "finding", "commit_id": SHA,
         "user": {"login": REVIEWER, "type": "Bot"}},
        {"id": 42, "in_reply_to_id": 41, "body": "fixed",
         "user": {"login": "unlisted-commenter"}},
    ]
    decision = work.decide(fixture, RULES)
    assert decision.stage == "review-disposition"
    assert "ignored-disposition-from=unlisted-commenter" in decision.reason


def test_listed_reviewer_summary_comment_counts_for_the_current_pull_request():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False, reviewer_ran=True)
    assert work.decide(fixture, RULES).stage == "release-report"


def test_unlisted_bot_comment_does_not_count_as_connected_review():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False)
    fixture.pr_comments = [{
        "body": "automation summary",
        "user": {"login": "unlisted-service[bot]", "type": "Bot"},
    }]
    assert work.decide(fixture, RULES).stage == "waiting"


def test_no_connected_reviewer_record_stays_waiting():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False)
    assert work.decide(fixture, RULES).stage == "waiting"


def test_listed_review_on_an_old_head_counts_once_for_the_pull_request():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False)
    fixture.reviews = [{
        "body": "reviewed", "commit_id": "b" * 40,
        "user": {"login": REVIEWER, "type": "Bot"},
    }]
    assert work.decide(fixture, RULES).stage == "release-report"


def test_empty_reviewer_list_requires_no_review_and_says_so():
    config = work.WorkConfig(marker_producers=frozenset({PRODUCER}))
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False, config=config)
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.reason) == (
        "release-report", "all-evidence-complete;no-connected-reviewer-configured",
    )


def test_bought_panel_routes_the_next_stage_named_by_the_lane():
    elevated = AFFIRMED.replace("ordinary", "elevated").replace("connected", "routine-panel")
    fixture = state(elevated, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False, reviewer_ran=True,
                    paths=["/".join(("skills", "work", "SKILL.md"))])
    first = work.decide(fixture, RULES)
    assert (first.stage, first.detail) == ("panel", "cold-pass")
    fixture.issue_comments.append({
        "body": "<!-- tradecraft:panel-stage:v1 stage=cold-pass status=complete -->",
        "user": {"login": PRODUCER},
    })
    assert work.decide(fixture, RULES).detail == "revision-diff"


@pytest.mark.parametrize("marker_name", ["cold-verdict", "use"])
def test_degraded_cross_vendor_evidence_needs_a_stage_local_reason(marker_name):
    if marker_name == "cold-verdict":
        degraded = "<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=degraded -->"
        fixture = state(AFFIRMED, ARTIFACT, degraded)
        assert work.decide(fixture, RULES).stage == "cold-seat"
        fixture.issue_comments[-1]["body"] = degraded.replace(
            " -->", " same_vendor_reason=primary-unavailable -->"
        )
        assert work.decide(fixture, RULES).stage == "holder-read"
    else:
        degraded = f"<!-- tradecraft:use:v1 head={SHA} status=pass changed=false staffing_status=degraded -->"
        fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, degraded, pr=True)
        assert work.decide(fixture, RULES).stage == "use"
        fixture.issue_comments[-1]["body"] = degraded.replace(
            " -->", " same_vendor_reason=primary-unavailable -->"
        )
        assert work.decide(fixture, RULES).stage == "ready-reviewers"


def test_multiple_candidate_pull_requests_refuse_instead_of_choosing():
    fixture = state(AFFIRMED)
    fixture.ambiguous_prs = [7, 8]
    decision = work.decide(fixture, RULES)
    assert {key: decision.as_dict()[key] for key in (
        "stage", "dispatch", "continuity", "reason", "detail"
    )} == {
        "stage": "ambiguous-pr", "dispatch": False, "continuity": None,
        "reason": "multiple-candidate-pull-requests", "detail": "7,8",
    }


def test_closed_completed_issue_is_terminal_before_three_candidate_pull_requests():
    fixture = state(issue_state="closed")
    fixture.issue["state_reason"] = "completed"
    fixture.ambiguous_prs = [666, 667, 668]
    decision = work.decide(fixture, RULES)
    assert {key: decision.as_dict()[key] for key in (
        "stage", "dispatch", "continuity", "reason", "detail"
    )} == {
        "stage": "terminal", "dispatch": False, "continuity": None,
        "reason": "issue-or-pull-request-terminal", "detail": None,
    }


@pytest.mark.parametrize(("risk", "lane"), list(work.LANES.items()))
def test_each_lawful_review_risk_lane_pair_is_affirmed(risk, lane):
    assert work.review_lane(f"Review risk: {risk}\nReview lane: {lane}\n") == (risk, lane)


def test_missing_affirmation_routes_to_the_form_and_presence_check():
    decision = work.decide(state(), RULES)
    assert {key: decision.as_dict()[key] for key in (
        "stage", "dispatch", "continuity", "reason", "detail"
    )} == {
        "stage": "convergence",
        "dispatch": False,
        "continuity": None,
        "reason": "affirmed-brief-marker-absent",
        "detail": work.BRIEF_GUIDANCE,
    }
    for required in (
        "<plugin-root>/skills/engagement/references/the-brief.md",
        "Shape",
        "Readers",
        "decision block",
        "Not this",
        "Review risk / Review lane pair",
        "python <plugin-root>/lib/brief.py --check FILE",
        "presence only",
        "content pass",
    ):
        assert required in decision.detail
    assert work.decide(state(AFFIRMED), RULES).detail is None


@pytest.mark.parametrize("text", [
    "Review lane: connected\n",
    "Review risk: ordinary\n",
    "Review risk: ordinary\nReview lane: substantial-panel\n",
    "Review risk: ordinary\nReview risk: elevated\nReview lane: connected\n",
])
def test_missing_or_crossed_review_rows_cannot_become_affirmed_state(text):
    fixture = state("<!-- tradecraft:affirmed-brief:v1 -->\n" + text)
    assert work.decide(fixture, RULES).stage == "affirmation-invalid"


@pytest.mark.parametrize("extra_row", [
    "Review risk: severe\n",
    "Review lane: bespoke\n",
])
def test_recording_marker_behavior_still_ignores_unrecognised_review_rows(extra_row):
    text = "Review risk: ordinary\nReview lane: connected\n" + extra_row
    assert work.review_lane(text) == ("ordinary", "connected")
    fixture = state("<!-- tradecraft:affirmed-brief:v1 -->\n" + text)
    assert work.decide(fixture, RULES).stage == "artifact"


def test_authorized_marker_advances_the_entrance():
    assert work.decide(state(AFFIRMED), RULES).stage == "artifact"


def test_latest_lawful_model_override_is_one_whole_choice():
    first = (
        "<!-- tradecraft:model-override:v1 "
        "implementer=codex:gpt-fixture:high "
        "ordinary_seat=claude:claude-fixture:high "
        "cold_seat=claude:claude-fixture:max "
        "terminal_seat=claude:claude-fixture:max "
        "use_consumer=claude:claude-fixture:max -->"
    )
    fixture = state(AFFIRMED, first)
    work.validate_marker_claims(fixture)
    assert work._launch_settings(fixture, "implementer", "codex") == work.LaunchSettings(
        "gpt-fixture", "high", "issue-comment:unknown", "issue-comment:unknown",
    )
    assert work._launch_settings(fixture, "cold-seat", "claude", "cold").effort == "max"
    assert work._launch_settings(fixture, "use-consumer", "claude", "cold").model == (
        "claude-fixture"
    )
    fixture.issue_comments.append({
        "body": "<!-- tradecraft:model-override:v1 cold_seat=claude:new-cold:high -->",
        "user": {"login": PRODUCER},
    })
    work.validate_marker_claims(fixture)
    implementer = work._launch_settings(fixture, "implementer", "codex")
    assert (implementer.model, implementer.effort, implementer.model_source) == (
        work.dispatch_implementer.DEFAULT_MODEL,
        work.dispatch_implementer.DEFAULT_EFFORT,
        "dispatch_implementer default",
    )
    assert work._launch_settings(fixture, "cold-seat", "claude", "cold").model == "new-cold"
    fixture.issue_comments.append({
        "body": "<!-- tradecraft:model-override:v1 -->",
        "user": {"login": PRODUCER},
    })
    work.validate_marker_claims(fixture)
    restored = work._launch_settings(fixture, "cold-seat", "claude", "cold")
    assert (restored.model, restored.effort, restored.model_source, restored.effort_source) == (
        work.dispatch_seat.DEFAULT_MODELS["claude"],
        work.dispatch_seat.CLAUDE_EFFORTS["cold"],
        "dispatch_seat default", "classification mapping",
    )


@pytest.mark.parametrize("claim", [
    "<!-- tradecraft:model-override:v1 mystery=codex:model:high -->",
    "<!-- tradecraft:model-override:v1 implementer=codex:model -->",
    "<!-- tradecraft:model-override:v1 implementer=codex:model:high implementer=codex:other:max -->",
])
def test_invalid_model_override_claims_are_reported_and_do_not_change_defaults(claim):
    fixture = state(AFFIRMED, claim)
    decision = work.decide(fixture, RULES)
    assert decision.invalid_markers
    selected = work._launch_settings(fixture, "implementer", "codex")
    assert (selected.model, selected.effort) == (
        work.dispatch_implementer.DEFAULT_MODEL, work.dispatch_implementer.DEFAULT_EFFORT,
    )


def test_wrong_vendor_override_and_narrative_prose_leave_defaults_in_place():
    fixture = state(
        AFFIRMED,
        "The owner discussed implementer=codex:narrative:max in prose.",
        "<!-- tradecraft:model-override:v1 implementer=claude:opus:max -->",
    )
    work.validate_marker_claims(fixture)
    selected = work._launch_settings(fixture, "implementer", "codex")
    assert selected.model == work.dispatch_implementer.DEFAULT_MODEL
    assert selected.model_source == "dispatch_implementer default"


def test_wrong_surface_and_unauthorized_model_overrides_are_reported_invalid():
    marker = "<!-- tradecraft:model-override:v1 implementer=codex:gpt-owner:max -->"
    fixture = state(AFFIRMED)
    fixture.issue["body"] = marker
    fixture.issue_comments.append({
        "body": marker, "user": {"login": "untrusted-commenter"},
    })
    decision = work.decide(fixture, RULES)
    reasons = {claim["reason"] for claim in decision.invalid_markers}
    assert "marker is not permitted on issue" in reasons
    assert "marker producer is not authorized: untrusted-commenter" in reasons


def test_unauthorized_comment_marker_is_ignored_and_names_its_author():
    fixture = state()
    fixture.issue_comments = [{
        "body": AFFIRMED,
        "user": {"login": "untrusted-commenter"},
    }]
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.reason) == (
        "convergence",
        "affirmed-brief-marker-absent;ignored-marker-from=untrusted-commenter",
    )


def test_issue_body_marker_is_checked_against_the_issue_author():
    fixture = state()
    fixture.issue["body"] = AFFIRMED
    fixture.issue["user"] = {"login": "untrusted-author"}
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.reason) == (
        "convergence", "affirmed-brief-marker-absent;ignored-marker-from=untrusted-author",
    )
    fixture.issue["user"] = {"login": PRODUCER}
    decision = work.decide(fixture, RULES)
    assert decision.stage == "convergence"
    assert decision.invalid_markers[0]["reason"] == "marker is not permitted on issue"


def configured_work(tmp_path, repositories, *, reviewers=(REVIEWER,), producers=(PRODUCER,)):
    directory = tmp_path / ".tradecraft"
    directory.mkdir(exist_ok=True)
    (directory / "work.json").write_text(json.dumps({
        "schema_version": 1,
        "product_repositories": repositories,
        "connected_reviewers": list(reviewers),
        "marker_producers": list(producers),
    }), encoding="utf-8")
    return work.load_work_config(tmp_path)


@pytest.mark.parametrize("body", [
    "https://github.com/acme/product-app/issues/91",
    "<!-- tradecraft:product-incident:v1 repo=ACME/PRODUCT-APP issue=91 -->",
])
def test_unlabelled_issue_accepts_a_configured_product_incident_case_insensitively(
        tmp_path, body):
    fixture = state(body)
    fixture.config = configured_work(tmp_path, ["Acme/Product-App"])
    assert work.decide(fixture, RULES).stage == "convergence"


def test_unlisted_commenter_product_incident_is_ignored_and_named(tmp_path):
    fixture = state()
    fixture.issue_comments.append({
        "body": "https://github.com/acme/product-app/issues/91",
        "user": {"login": "unlisted-commenter"},
    })
    fixture.config = configured_work(tmp_path, ["acme/product-app"])
    decision = work.decide(fixture, RULES)
    assert decision.stage == "product-incident-required"
    assert "ignored-product-incident-from=unlisted-commenter" in decision.reason


def test_configured_product_list_refuses_an_unlabelled_issue_without_an_incident(tmp_path):
    fixture = state()
    fixture.config = configured_work(tmp_path, ["acme/product-app"])
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.dispatch) == ("product-incident-required", False)


def test_affirmed_brief_waives_the_configured_product_incident_check(tmp_path):
    fixture = state(AFFIRMED)
    fixture.config = configured_work(tmp_path, ["acme/product-app"])
    assert work.decide(fixture, RULES).stage == "artifact"


def test_pull_request_admission_evidence_does_not_waive_the_issue_check(tmp_path):
    fixture = state(pr=True)
    fixture.pr_comments = [{
        "body": AFFIRMED + "\nhttps://github.com/acme/product-app/issues/91",
        "user": {"login": PRODUCER},
    }]
    fixture.config = configured_work(tmp_path, ["acme/product-app"])
    assert work.decide(fixture, RULES).stage == "product-incident-required"


def test_configured_product_repository_refuses_an_incident_from_elsewhere(tmp_path):
    fixture = state()
    fixture.issue_comments.append({
        "body": "https://github.com/acme/elsewhere/issues/91\n"
                "<!-- tradecraft:product-incident:v1 repo=acme/elsewhere issue=91 -->",
        "user": {"login": PRODUCER},
    })
    fixture.config = configured_work(tmp_path, ["acme/product-app"])
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.dispatch) == ("product-incident-required", False)


@pytest.mark.parametrize("repositories", [None, []])
@pytest.mark.parametrize(("texts", "expected"), [
    (("<!-- tradecraft:practice-facing:v1 -->",), "convergence"),
    ((AFFIRMED,), "artifact"),
    (("https://github.com/acme/product-app/issues/91",), "convergence"),
])
def test_missing_or_empty_product_repository_list_disables_the_check(
        tmp_path, repositories, texts, expected):
    fixture = state(*texts)
    fixture.issue["labels"] = [{"name": "practice-facing"}]
    fixture.config = (work.load_work_config(tmp_path) if repositories is None
                      else configured_work(tmp_path, repositories))
    decision = work.decide(fixture, RULES)
    if repositories == []:
        assert decision.stage == expected
    assert decision.stage != "product-incident-required"


def test_work_configuration_normalizes_all_three_repository_owned_lists(tmp_path):
    config = configured_work(
        tmp_path, ["Acme/Product-App"],
        reviewers=("Review-Service[bot]",), producers=("Release-Holder",),
    )
    assert config == work.WorkConfig(
        product_repositories=frozenset({"acme/product-app"}),
        connected_reviewers=frozenset({"review-service[bot]"}),
        marker_producers=frozenset({"release-holder"}),
    )


def test_path_rules_buy_runtime_use_and_decline_docs_and_tests():
    assert work.use_required(["lib/runtime.py"], RULES) is True
    assert work.use_required(["lib/tests/test_runtime.py", "README.md"], RULES) is False


def test_false_use_branch_requires_marker_and_explicit_line():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR,
                    f"<!-- tradecraft:no-use:v1 head={SHA} -->", pr=True,
                    paths=["README.md"])
    assert work.decide(fixture, RULES).stage == "use"
    fixture.issue_comments[-1]["body"] += "\nUse: not required for changed paths"
    assert work.decide(fixture, RULES).stage == "ready-reviewers"


class FakeTransport:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def get(self, endpoint, *, paginate=False):
        self.calls.append(("GET", endpoint, paginate))
        return self.values[endpoint]


def test_state_reader_uses_get_only_and_reads_all_pr_surfaces():
    base = "repos/acme/widget"
    values = {
        f"{base}/issues/3": {
            "number": 3, "state": "open", "body": "", "labels": [],
            "user": {"login": PRODUCER},
        },
        f"{base}/issues/3/comments": [
            {"body": "<!-- tradecraft:implementing-pr:v1 number=9 -->",
             "user": {"login": PRODUCER}},
        ],
        f"{base}/pulls?state=all&per_page=100": [
            {"number": 9, "state": "open", "body": ""},
        ],
        f"{base}/pulls/9": {"number": 9, "state": "open", "draft": True,
                             "head": {"sha": SHA}},
        f"{base}/issues/9/comments": [],
        f"{base}/pulls/9/reviews": [],
        f"{base}/pulls/9/comments": [],
        f"{base}/pulls/9/files": [{"filename": "lib/runtime.py"}],
        f"{base}/commits/{SHA}/check-runs": {"check_runs": []},
    }
    transport = FakeTransport(values)
    fixture = work.read_state(transport, "acme/widget", 3, CONFIG)
    assert fixture.pr["number"] == 9
    assert fixture.changed_paths == ["lib/runtime.py"]
    assert {method for method, _endpoint, _paginate in transport.calls} == {"GET"}
    assert len(transport.calls) == 9


def test_merged_pull_request_cited_as_evidence_is_not_a_candidate_or_terminal():
    base = "repos/acme/widget"
    values = {
        f"{base}/issues/12": {
            "number": 12, "state": "open", "labels": [],
            "body": "Evidence was recorded in https://github.com/acme/widget/pull/9",
        },
        f"{base}/issues/12/comments": [],
        f"{base}/pulls?state=all&per_page=100": [{
            "number": 9, "state": "closed", "merged_at": "2026-09-01T00:00:00Z",
            "body": "This records evidence and mentions closes #12 inline.",
        }],
    }
    fixture = work.read_state(FakeTransport(values), "acme/widget", 12)
    assert fixture.pr is None
    assert fixture.ambiguous_prs == []
    assert work.decide(fixture, RULES).stage == "convergence"


def test_reopened_issue_retains_its_merged_former_implementing_pull_request():
    issue = {"number": 12, "state": "open", "body": ""}
    pulls = [{
        "number": 9, "state": "closed", "merged_at": "2026-09-01T00:00:00Z",
        "body": "Closes #12",
    }]
    candidates = work._candidate_prs(12, issue, [], pulls, CONFIG)
    fixture = work.WorkState("acme/widget", 12, issue, merged_pr=pulls[0], config=CONFIG)
    assert candidates == {9}
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.dispatch, decision.status) == (
        "merged-pull-request", False, "holder-owned",
    )
    assert decision.detail.startswith("#9:")


def test_fresh_build_after_merged_pull_request_refuses_the_active_registration(
        tmp_path, monkeypatch):
    fixture = state(AFFIRMED)
    fixture.merged_pr = {
        "number": 9, "state": "closed", "merged_at": "2026-09-01T00:00:00Z",
    }
    implementation = tmp_path / "implementation"
    monkeypatch.setattr(
        work, "resolve_implementation_root",
        lambda *_args, **_kwargs: (implementation, "tradecraft/12-former", False),
    )
    monkeypatch.setattr(
        work, "publish_implementation_branch",
        lambda *_args, **_kwargs: pytest.fail("the merged registration must not launch"),
    )

    selected = work._dispatch_root(
        fixture, work.Decision("build", True, "fresh", "holder-named-stage"),
        tmp_path, None, "holder-session",
    )

    assert isinstance(selected, work.Decision)
    assert selected.reason == "fresh-build-requires-released-registration"
    assert "run release" in (selected.detail or "")


def test_closed_issue_keeps_its_merged_implementing_pull_request_terminal():
    issue = {"number": 12, "state": "closed", "body": ""}
    pulls = [{
        "number": 9, "state": "closed", "merged_at": "2026-09-01T00:00:00Z",
        "body": "Closes #12",
    }]
    candidates = work._candidate_prs(12, issue, [], pulls, CONFIG)
    fixture = work.WorkState("acme/widget", 12, issue, pr=pulls[0], config=CONFIG)
    assert candidates == {9}
    assert work.decide(fixture, RULES).stage == "terminal"


def test_open_issue_selects_its_open_implementing_pull_request():
    issue = {"number": 12, "state": "open", "body": ""}
    pulls = [{"number": 9, "state": "open", "body": "Closes #12"}]
    assert work._candidate_prs(12, issue, [], pulls, CONFIG) == {9}


def test_open_implementing_pull_request_wins_over_merged_history():
    issue = {"number": 12, "state": "open", "body": ""}
    pulls = [
        {"number": 8, "state": "closed", "merged_at": "2026-09-01T00:00:00Z",
         "body": "Closes #12"},
        {"number": 9, "state": "open", "merged_at": None, "body": "Closes #12"},
    ]
    assert work._candidate_prs(12, issue, [], pulls, CONFIG) == {9}


def test_multiple_merged_candidates_are_ambiguous_only_without_an_open_candidate():
    base = "repos/acme/widget"
    values = {
        f"{base}/issues/12": {"number": 12, "state": "open", "body": "", "labels": []},
        f"{base}/issues/12/comments": [],
        f"{base}/pulls?state=all&per_page=100": [
            {"number": 7, "state": "closed", "merged_at": "2026-09-01T00:00:00Z",
             "body": "Fixes #12"},
            {"number": 8, "state": "closed", "merged_at": "2026-09-02T00:00:00Z",
             "body": "Fixes #12"},
        ],
    }
    fixture = work.read_state(FakeTransport(values), "acme/widget", 12)
    assert fixture.ambiguous_prs == [7, 8]
    assert work.decide(fixture, RULES).stage == "ambiguous-pr"


def test_closed_unmerged_pull_request_never_counts():
    issue = {"number": 12, "state": "open", "body": ""}
    pulls = [{"number": 9, "state": "closed", "merged_at": None, "body": "Closes #12"}]
    assert work._candidate_prs(12, issue, [], pulls, CONFIG) == set()


def test_pull_request_body_standalone_closing_reference_is_the_candidate():
    candidates = work._candidate_prs(
        12, {"number": 12, "body": ""}, [],
        [{"number": 9, "state": "open", "body": "Context\nCloses #12\nMore context"}],
        CONFIG,
    )
    assert candidates == {9}


def test_unauthorized_implementing_pr_marker_is_not_a_candidate():
    candidates = work._candidate_prs(
        12,
        {"number": 12, "body": "", "user": {"login": PRODUCER}},
        [{"body": "<!-- tradecraft:implementing-pr:v1 number=9 -->",
          "user": {"login": "untrusted-commenter"}}],
        [{"number": 9, "state": "open", "body": "A citation, not a closing reference"}],
        CONFIG,
    )
    assert candidates == set()


def test_two_pull_request_bodies_closing_the_issue_are_ambiguous():
    base = "repos/acme/widget"
    values = {
        f"{base}/issues/12": {"number": 12, "state": "open", "body": "", "labels": []},
        f"{base}/issues/12/comments": [],
        f"{base}/pulls?state=all&per_page=100": [
            {"number": 7, "state": "open", "body": "Fixes #12"},
            {"number": 8, "state": "open", "body": "RESOLVED #12"},
        ],
    }
    fixture = work.read_state(FakeTransport(values), "acme/widget", 12)
    assert fixture.pr is None
    assert fixture.ambiguous_prs == [7, 8]
    assert work.decide(fixture, RULES).stage == "ambiguous-pr"


def test_cross_reference_timeline_is_not_read_as_a_candidate():
    base = "repos/acme/widget"
    values = {
        f"{base}/issues/12": {
            "number": 12, "state": "open", "body": "", "labels": [],
            "timeline_url": "https://api.github.test/repos/acme/widget/issues/12/timeline",
        },
        f"{base}/issues/12/comments": [],
        f"{base}/pulls?state=all&per_page=100": [],
    }
    transport = FakeTransport(values)
    fixture = work.read_state(transport, "acme/widget", 12)
    assert fixture.pr is None
    assert fixture.ambiguous_prs == []
    assert all("timeline" not in endpoint for _method, endpoint, _paginate in transport.calls)


def test_review_disposition_marker_is_part_of_the_entrance_evidence():
    fixture = state()
    fixture.review_comments = [{"body": REVIEWED, "user": {"login": PRODUCER}}]
    assert {marker.name for marker in fixture.markers} == {"connected-reviewer"}


def test_run_reads_the_work_configuration_from_root(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    configured_work(tmp_path, ["acme/product-app"])
    rules_directory = tmp_path / "lib"
    rules_directory.mkdir()
    (rules_directory / "use-rules.json").write_bytes((LIB / "use-rules.json").read_bytes())
    args = work.parser().parse_args([
        "--repo", "example/tradecraft", "--issue", "3", "--root", str(tmp_path),
    ])
    class PracticeTransport:
        def get(self, endpoint, *, paginate=False):
            if endpoint.endswith("/comments"):
                return [{"body": AFFIRMED, "user": {"login": PRODUCER}}]
            if "/pulls?" in endpoint:
                return []
            return {
                "number": 3,
                "state": "open",
                    "body": "https://github.com/ACME/PRODUCT-APP/issues/7",
                "labels": [{"name": "practice-facing"}],
                "user": {"login": PRODUCER},
            }

    assert work.run(args, transport=PracticeTransport()) == 0
    report = json.loads(capsys.readouterr().out)
    assert (report["stage"], report["reason"]) == ("artifact", "artifact-marker-absent")


def test_ordinary_entrance_is_repeatable_and_never_sweeps_or_executes(
        tmp_path, monkeypatch, capsys):
    args = work.parser().parse_args([
        "--repo", "acme/widget", "--issue", "3", "--root", str(tmp_path),
        "--use-rules", str(LIB / "use-rules.json"),
    ])

    class MinimalTransport:
        def get(self, endpoint, *, paginate=False):
            if endpoint.endswith("/comments") or "/pulls?" in endpoint:
                return []
            return {"number": 3, "state": "open", "body": "", "labels": [],
                    "user": {"login": PRODUCER}}

    monkeypatch.setattr(
        work, "sweep_registry",
        lambda *_args: pytest.fail("a decision read must not sweep the registry"),
    )
    executor = lambda *_args: pytest.fail("a decision read must not execute a stage")
    assert work.run(args, transport=MinimalTransport(), executor=executor) == 0
    first = capsys.readouterr().out
    assert work.run(args, transport=MinimalTransport(), executor=executor) == 0
    second = capsys.readouterr().out
    assert first == second
    report = json.loads(first)
    assert report["work"] == "acme/widget#3"
    assert report["producer_version"] == work.records.producer_version()


def test_builder_prompt_names_one_stage_and_forbids_pipeline_dispatch():
    fixture = state(AFFIRMED)
    prompt = work._stage_prompt(fixture, work.Decision("artifact", True, "fresh", "fixture"))
    assert prompt.count(b'"stage": "artifact"') == 1
    assert b"Do not start or dispatch a later stage" in prompt
    evidence = json.loads(prompt.split(b"\n\n")[1])
    assert evidence["work"] == "example/product#12"
    assert AFFIRMED.encode("ascii") in prompt
    assert b"gh api --method GET repos/example/product/issues/12" in prompt


def test_build_prompt_tells_the_holder_to_post_the_builder_session_marker():
    prompt = work._stage_prompt(
        state(AFFIRMED), work.Decision("build", True, "fresh", "fixture")
    )
    assert b"<!-- tradecraft:builder-session:v1 session=SESSION -->" in prompt


def test_unrelated_record_comments_do_not_change_a_composed_prompt():
    first = state(AFFIRMED, ARTIFACT, "unrelated first comment")
    second = state(AFFIRMED, ARTIFACT, "different unrelated comment")
    decision = work.Decision("build", True, "fresh", "holder-named-stage")
    assert work._stage_prompt(first, decision) == work._stage_prompt(second, decision)


def test_use_prompt_is_refused_while_build_omits_the_record():
    criterion = "SECRET ACCEPTANCE CRITERION"
    comment = "SECRET ISSUE COMMENT"
    fixture = state(AFFIRMED + criterion, comment)
    use = work.Decision("use", True, "fresh", "fixture")

    with pytest.raises(work.WorkError, match="does not dispatch the use stage"):
        work._stage_prompt(fixture, use)

    prompt = work._stage_prompt(fixture, work.Decision("build", True, "fresh", "fixture"))
    assert criterion.encode("ascii") in prompt
    assert comment.encode("ascii") not in prompt


def test_cold_seat_prompt_carries_only_artifact_brief_and_check_contract(tmp_path):
    brief = AFFIRMED + "Brief text visible only to the cold seat.\n"
    artifact = ARTIFACT + "\nArtifact text visible only to the cold seat.\n"
    fixture = state(brief, "OTHER COMMENT MUST STAY OUT", artifact)
    artifact_bytes = artifact.encode("utf-8")
    decision = work.Decision("cold-seat", True, "fresh", "fixture")

    with pytest.raises(work.WorkError, match="isolated working root"):
        work._stage_prompt(fixture, decision)
    prompt = work._stage_prompt(fixture, decision, tmp_path)

    assert artifact_bytes in prompt
    assert brief.encode("utf-8") in prompt
    assert hashlib.sha256(artifact_bytes).hexdigest().encode("ascii") in prompt
    assert f"Artifact byte count: {len(artifact_bytes)}".encode("ascii") in prompt
    assert b"OTHER COMMENT MUST STAY OUT" not in prompt
    assert b"The bar is plausible" in prompt
    assert b"Trace both directions" in prompt
    assert b"This list is closed" in prompt


def test_execute_cold_seat_uses_the_bounded_prompt(tmp_path, monkeypatch):
    artifact = ARTIFACT + "\nArtifact body.\n"
    override = "<!-- tradecraft:model-override:v1 cold_seat=claude:cold-owner:max -->"
    fixture = state(AFFIRMED, "OTHER COMMENT MUST STAY OUT", artifact, override)
    captured = []
    monkeypatch.setattr(work, "judging_root", lambda _root: nullcontext(tmp_path))
    monkeypatch.setattr(work, "_git_snapshot", lambda _root: (SHA, ""))

    def run(command):
        dispatch = Path(command[command.index("--dispatch") + 1])
        captured.append((command, dispatch.read_bytes()))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(work.subprocess, "run", run)
    runtime = Path(sys.executable).resolve()
    decision = work.Decision("cold-seat", True, "fresh", "fixture")
    assert work.execute_stage(
        fixture, decision, tmp_path, None, claude_path=runtime, codex_path=runtime,
    ) == 0
    command, prompt = captured[0]
    assert artifact.encode("utf-8") in prompt
    assert AFFIRMED.encode("utf-8") in prompt
    assert b"OTHER COMMENT MUST STAY OUT" not in prompt
    assert b'"issue_comments"' not in prompt
    assert command[command.index("--claude-model") + 1] == "cold-owner"
    assert command[command.index("--claude-effort") + 1] == "max"
    assert command[command.index("--claude-model-source") + 1] == "issue-comment:unknown"
    assert Path(command[command.index("--claude") + 1]) == runtime
    assert Path(command[command.index("--codex") + 1]) == runtime


def dispatch_bundle(record_root, *, work_value="example/product#12", stage="build",
                    session=SESSION, completed_at="2026-09-20T10:00:00+00:00",
                    name="result.md", producer_version=None,
                    request_schema=2, run_schema=2, outcome="success"):
    if producer_version is None:
        producer_version = work.records.producer_version()
    bundle = record_root / stage
    bundle.mkdir(parents=True, exist_ok=True)
    request = bundle / f"{name}.request.json"
    run = bundle / f"{name}.run.json"
    request.write_text(json.dumps({
        "schema_version": request_schema, "work": work_value, "stage": stage,
        "producer_version": producer_version,
    }), encoding="utf-8")
    run.write_text(json.dumps({
        "schema_version": run_schema,
        "outcome": outcome,
        "completed_at": completed_at,
        "attempts": ([] if session is None else [{"observed": {"session_id": session}}]),
    }), encoding="utf-8")


def test_bundle_backed_builder_marker_must_match_the_observed_session(tmp_path):
    marker = f"<!-- tradecraft:builder-session:v1 session={SESSION} -->"
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, marker)
    fixture.issue_comments[2]["created_at"] = "2026-09-20T09:00:00Z"
    fixture.issue_comments[-1]["created_at"] = "2026-09-20T11:00:00Z"
    fixture.record_root = tmp_path / "dispatches"
    cold = fixture.record_root / "cold-seat"
    cold.mkdir(parents=True)
    (cold / "result.md.request.json").write_bytes(json.dumps({
        "schema_version": 2, "work": "example/product#12", "stage": "cold-seat",
        "producer_version": work.records.producer_version(),
    }).encode())
    (cold / "result.md.run.json").write_bytes(json.dumps({
        "schema_version": 2, "outcome": "success",
        "completed_at": "2026-09-20T08:00:00+00:00", "staffing_status": "qualified",
        "staffing_qualification": {"same_vendor_reason": None}, "attempts": [],
    }).encode())
    dispatch_bundle(fixture.record_root, completed_at="2026-09-20T10:00:00+00:00")
    assert work.decide(fixture, RULES).stage == "open-pull-request"

    fixture.issue_comments[-1]["body"] = (
        f"<!-- tradecraft:builder-session:v1 session={OTHER_SESSION} -->"
    )
    decision = work.decide(fixture, RULES)
    assert decision.stage == "build"
    assert any("disagrees" in item["reason"] for item in decision.invalid_markers)


def test_version_refusal_happens_before_any_stage_side_effect(tmp_path, monkeypatch, capsys):
    fixture = state(AFFIRMED)
    monkeypatch.setattr(work.records, "producer_version", lambda: "0.150.0")
    monkeypatch.setattr(
        work, "_dispatch_root",
        lambda *_args, **_kwargs: pytest.fail("unsafe version must not resolve or create a root"),
    )
    decision = work.Decision("build", True, "fresh", "holder-named-stage")
    assert work.execute_stage(fixture, decision, tmp_path, None, "holder") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "unsafe-running-version-for-build"
    assert "stage=build" in report["detail"]
    assert "found=0.150.0" in report["detail"]
    assert "required=0.152.0" in report["detail"]
    assert "mechanism=" in report["detail"]


def test_unstamped_resume_bundle_is_refused_without_marker_fallback(
        tmp_path, monkeypatch, capsys):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="floor")
    request = store / "floor" / "result.md.request.json"
    value = json.loads(request.read_bytes())
    value.pop("producer_version")
    request.write_bytes(json.dumps(value).encode())
    fixture = state(
        AFFIRMED, f"<!-- tradecraft:builder-session:v1 session={OTHER_SESSION} -->", pr=True
    )
    fixture.record_root = store
    monkeypatch.setattr(
        work, "_dispatch_root",
        lambda *_args, **_kwargs: pytest.fail("unstamped bundle must refuse before root access"),
    )
    decision = work.Decision("floor", True, "resume", "holder-named-stage")
    assert work.execute_stage(fixture, decision, tmp_path, None, "holder") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "unsafe-source-version-for-floor"
    assert "found=missing" in report["detail"]


def test_unsupported_matching_bundle_schema_refuses_before_marker_fallback(
        tmp_path, monkeypatch, capsys):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="floor", request_schema=1)
    fixture = state(
        AFFIRMED, f"<!-- tradecraft:builder-session:v1 session={OTHER_SESSION} -->", pr=True
    )
    fixture.record_root = store
    monkeypatch.setattr(
        work, "_dispatch_root",
        lambda *_args, **_kwargs: pytest.fail("unsupported bundle schema must refuse first"),
    )

    decision = work.Decision("floor", True, "resume", "holder-named-stage")
    assert work.execute_stage(fixture, decision, tmp_path, None, "holder") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "resume-bundle-invalid-for-floor"
    assert "unsupported request schema" in report["detail"]


def test_resume_version_check_uses_the_bundle_that_supplies_the_session(
        tmp_path, monkeypatch, capsys):
    store = tmp_path / "dispatches"
    dispatch_bundle(
        store, stage="floor", name="older", producer_version="0.148.0",
        completed_at="2026-09-20T10:00:00+00:00",
    )
    dispatch_bundle(
        store, stage="floor", name="newer", session=None,
        completed_at="2026-09-20T11:00:00+00:00",
    )
    fixture = state(
        AFFIRMED, f"<!-- tradecraft:builder-session:v1 session={OTHER_SESSION} -->", pr=True
    )
    fixture.record_root = store
    monkeypatch.setattr(
        work, "_dispatch_root",
        lambda *_args, **_kwargs: pytest.fail("unsafe selected bundle must refuse first"),
    )

    decision = work.Decision("floor", True, "resume", "holder-named-stage")
    assert work.execute_stage(fixture, decision, tmp_path, None, "holder") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "unsafe-source-version-for-floor"
    assert "found=0.148.0" in report["detail"]


def test_matching_bundles_without_a_session_refuse_instead_of_falling_back(
        tmp_path, monkeypatch, capsys):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="floor", session=None)
    fixture = state(
        AFFIRMED, f"<!-- tradecraft:builder-session:v1 session={SESSION} -->", pr=True
    )
    fixture.record_root = store
    monkeypatch.setattr(
        work, "_dispatch_root",
        lambda *_args, **_kwargs: pytest.fail("sessionless bundle must block marker fallback"),
    )

    decision = work.Decision("floor", True, "resume", "holder-named-stage")
    assert work.execute_stage(fixture, decision, tmp_path, None, "holder") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "resume-bundle-invalid-for-floor"
    assert "no valid session" in report["detail"]


@pytest.mark.parametrize(("running", "fragment"), [
    ("0.152.0-rc.1", "required=0.152.0"),
    ("1.0.0", "incompatible major"),
])
def test_running_version_preserves_semver_boundaries_before_side_effects(
        tmp_path, monkeypatch, capsys, running, fragment):
    monkeypatch.setattr(work.records, "producer_version", lambda: running)
    monkeypatch.setattr(
        work, "_dispatch_root",
        lambda *_args, **_kwargs: pytest.fail("unsafe version must refuse before root access"),
    )
    decision = work.Decision("build", True, "fresh", "holder-named-stage")
    assert work.execute_stage(state(AFFIRMED), decision, tmp_path, None, "holder") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "unsafe-running-version-for-build"
    assert fragment in report["detail"]


def test_resume_source_with_another_major_refuses_before_side_effects(
        tmp_path, monkeypatch, capsys):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="floor", producer_version="1.0.0")
    fixture = state(AFFIRMED, pr=True)
    fixture.record_root = store
    monkeypatch.setattr(
        work, "_dispatch_root",
        lambda *_args, **_kwargs: pytest.fail("incompatible source major must refuse first"),
    )
    decision = work.Decision("floor", True, "resume", "holder-named-stage")
    assert work.execute_stage(fixture, decision, tmp_path, None, "holder") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "unsafe-source-version-for-floor"
    assert "incompatible major" in report["detail"]


def test_resume_session_prefers_matching_bundle_over_issue_marker(tmp_path):
    fixture = state(f"<!-- tradecraft:builder-session:v1 session={OTHER_SESSION} -->")
    store = tmp_path / "dispatches"
    dispatch_bundle(store)
    dispatch_bundle(
        store, work_value="example/elsewhere#12", stage="floor", session=OTHER_SESSION,
        completed_at="2026-09-20T11:00:00+00:00",
    )
    dispatch_bundle(
        store, stage="artifact", session=OTHER_SESSION,
        completed_at="2026-09-20T12:00:00+00:00",
    )
    assert work.resume_session(fixture, "floor", store) == SESSION


def test_artifact_revision_recovers_its_artifact_session(tmp_path):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="artifact")
    assert work.resume_session(state(), "artifact", store) == SESSION


def test_completed_no_output_bundle_with_a_session_remains_resumable(tmp_path):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="build", outcome="completed_no_output")
    assert work.resume_session(state(), "floor", store) == SESSION


def test_completed_no_output_bundle_cannot_validate_a_floor_marker(tmp_path):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="floor", outcome="completed_no_output")
    fixture = state(FLOOR, pr=True)
    fixture.record_root = store

    lawful, invalid = work.validate_marker_claims(fixture)

    assert not any(marker.name == "floor" for marker in lawful)
    floor_claim = next(claim for claim in invalid if claim["name"] == "floor")
    assert floor_claim["reason"] == "no matching successful dispatch bundle"
    assert work.resume_session(fixture, "floor", store) == SESSION


def test_historical_error_bundle_is_never_rejudged_from_its_retained_stream(tmp_path):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="build", outcome="error")
    log = store / "build" / "result.md.codex.stdout.log"
    log.write_bytes(b'\n'.join((
        b'{"type":"item.completed","item":{"type":"agent_message","text":"done"}}',
        b'{"type":"turn.completed"}',
    )))
    before = {path: path.read_bytes() for path in store.rglob("*") if path.is_file()}
    assert work.resume_session(state(), "floor", store) is None
    after = {path: path.read_bytes() for path in store.rglob("*") if path.is_file()}
    assert after == before


def test_resume_session_falls_back_to_authorized_builder_session_marker(tmp_path):
    fixture = state(f"<!-- tradecraft:builder-session:v1 session={SESSION} -->")
    assert work.resume_session(fixture, "floor", tmp_path / "missing") == SESSION


def test_resume_without_bundle_or_marker_returns_a_non_dispatching_decision(
        tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(work, "resume_session", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        work.subprocess, "run",
        lambda *_args, **_kwargs: pytest.fail("a missing resume session must not launch"),
    )
    decision = work.Decision("floor", True, "resume", "current-head-floor-missing-or-red")
    assert work.execute_stage(
        state(AFFIRMED, pr=True), decision, tmp_path, None, "holder-session"
    ) == 0
    returned = json.loads(capsys.readouterr().out)
    assert {key: returned[key] for key in (
        "continuity", "detail", "dispatch", "reason", "stage"
    )} == {
        "continuity": None,
        "detail": (
            "stage=floor; supply=a matching dispatch bundle or authorized "
            "builder-session marker"
        ),
        "dispatch": False,
        "reason": "resume-session-missing-for-floor",
        "stage": "floor",
    }


def test_build_launch_without_holder_identity_is_refused(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        work.subprocess, "run",
        lambda *_args, **_kwargs: pytest.fail("missing holder identity must not launch"),
    )
    decision = work.Decision("build", True, "fresh", "pull-request-absent")
    assert work.execute_stage(state(), decision, tmp_path, None) == 0
    returned = json.loads(capsys.readouterr().out)
    assert returned["reason"] == "holder-session-id-required-for-build"
    assert "--holder-session-id" in returned["detail"]


def test_dispatching_use_without_registration_names_absence_before_prompt_or_launch(
        tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    def fail(*_args, **_kwargs):
        pytest.fail("a use handoff must not build a prompt or launch")

    monkeypatch.setattr(work, "_dispatch_root", fail)
    monkeypatch.setattr(work, "judging_root", fail)
    monkeypatch.setattr(work, "_stage_prompt", fail)
    monkeypatch.setattr(work.subprocess, "run", fail)

    decision = work.Decision("use", True, "fresh", "externally-constructed-use")
    assert work.execute_stage(state(pr=True), decision, tmp_path, None) == 0
    returned = json.loads(capsys.readouterr().out)
    assert (returned["stage"], returned["dispatch"], returned["continuity"],
            returned["reason"]) == ("use", False, None, "use-requires-holder-job-and-tree")
    assert "--dispatch and --tree-metadata" in returned["detail"]
    assert str(tmp_path.resolve()) not in returned["detail"]
    assert SHA not in returned["detail"]


def test_use_handoff_names_registered_implementation_root_and_revision(
        tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    implementation, _branch = work.create_implementation_root(
        holder, "example/product", 12, None, "holder-session"
    )
    revision = git(implementation, "rev-parse", "HEAD").stdout.decode().strip()
    fixture = state(
        AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR.replace(SHA, revision), pr=True
    )
    fixture.pr["head"]["sha"] = revision

    assert work.execute_stage(
        fixture, work.decide(fixture, RULES), holder, None
    ) == 0
    returned = json.loads(capsys.readouterr().out)
    assert (returned["stage"], returned["dispatch"], returned["continuity"],
            returned["reason"]) == ("use", False, None, "current-head-use-absent")
    assert str(implementation) in returned["detail"]
    assert revision in returned["detail"]


def test_use_handoff_migrates_legacy_registration_and_names_the_proof_gap(
        tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    implementation, branch = work.create_implementation_root(
        holder, "example/product", 12, None, "holder-session"
    )
    legacy = registry_row(implementation, holder, branch)
    legacy.pop("holder_root")
    legacy.pop("branch")
    write_registry_rows([legacy])
    revision = git(implementation, "rev-parse", "HEAD").stdout.decode().strip()
    fixture = state(
        AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR.replace(SHA, revision), pr=True
    )
    fixture.pr["head"]["sha"] = revision

    assert work.execute_stage(
        fixture, work.decide(fixture, RULES), holder, None
    ) == 0

    returned = json.loads(capsys.readouterr().out)
    assert (returned["stage"], returned["dispatch"], returned["continuity"]) == (
        "use", False, None,
    )
    assert str(implementation) in returned["detail"]
    assert work.MIGRATION_NOTICE in returned["detail"]
    recorded = work.read_registry()["worktrees"][0]
    assert recorded["holder_root"] == str(holder)
    assert recorded["branch"] == branch


def test_run_use_launches_only_with_the_holder_job_and_validated_tree(
        tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    implementation, _branch = work.create_implementation_root(
        holder, "example/product", 12, None, "holder-session"
    )
    (implementation / "job.md").write_bytes(b"consumer surface\n")
    (implementation / "SKILL.md").write_bytes(b"loading surface\n")
    (implementation / ".gitattributes").write_bytes(b"* text=auto eol=lf\n")
    git(implementation, "add", "job.md", "SKILL.md", ".gitattributes")
    git(implementation, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "consumer")
    output = tmp_path / "consumer"
    metadata = work.recipient_tree.create_consumer_tree(
        source=implementation, output=output, work="example/product#12",
        producer_version=work.records.producer_version(), mode="adopter", paths=["job.md"],
        loading_surfaces=["SKILL.md"], front_page=None, root_instructions=None,
        directed_paths=[], exclusions=[], deny_texts=[],
    )
    dispatch = tmp_path / "use-job.md"
    dispatch.write_bytes(b"Use the result and return a session note.\n")
    launches = []
    original_run = subprocess.run

    def run(command, *args, **kwargs):
        if len(command) > 1 and Path(command[1]).name == "dispatch_seat.py":
            launches.append(command)
            return subprocess.CompletedProcess(command, 0)
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(work.subprocess, "run", run)
    monkeypatch.setattr(
        work, "_runtime_argument", lambda vendor: [f"--{vendor}", f"/{vendor}-fixture"]
    )
    override = (
        "<!-- tradecraft:model-override:v1 "
        "use_consumer=claude:use-owner:max -->"
    )
    assert work.execute_stage(
        state(AFFIRMED, override),
        work.Decision("use", True, "fresh", "holder-named-stage"),
        holder, None, dispatch_path=dispatch, tree_metadata=metadata,
    ) == 0
    assert len(launches) == 1
    command = launches[0]
    assert Path(command[command.index("--dispatch") + 1]) == dispatch.resolve()
    assert Path(command[command.index("--root") + 1]) == output.resolve()
    assert command[command.index("--claude-model") + 1] == "use-owner"
    assert command[command.index("--claude-effort") + 1] == "max"
    assert command[command.index("--claude-effort-source") + 1] == "issue-comment:unknown"
    assert command[command.index("--codex-model") + 1] == work.dispatch_seat.DEFAULT_MODELS["codex"]
    assert command[command.index("--codex-model-source") + 1] == "dispatch_seat default"
    assert command[command.index("--claude") + 1] == "/claude-fixture"


def test_tree_revision_and_run_use_need_no_registration(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    (holder / "job.md").write_bytes(b"consumer surface\n")
    (holder / "SKILL.md").write_bytes(b"loading surface\n")
    (holder / ".gitattributes").write_bytes(b"* text=auto eol=lf\n")
    git(holder, "add", "job.md", "SKILL.md", ".gitattributes")
    git(holder, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "landed consumer")
    revision = git(holder, "rev-parse", "HEAD").stdout.decode().strip()
    branch = git(holder, "symbolic-ref", "--short", "HEAD").stdout.decode().strip()
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    git(holder, "remote", "add", "origin", str(remote))
    git(holder, "push", "--set-upstream", "origin", branch)
    transport = FakeTransport({
        "repos/example/product": {"default_branch": branch},
    })
    output = tmp_path / "consumer"
    args = work.parser().parse_args([
        "tree", "--repo", "example/product", "--issue", "12", "--root", str(holder),
        "--revision", revision, "--mode", "adopter", "--output", str(output),
        "--path", "job.md", "--loading-surface", "SKILL.md",
    ])
    monkeypatch.setattr(
        work, "resolve_implementation_root",
        lambda *_args, **_kwargs: pytest.fail("named revision must not read registration"),
    )
    assert work.run(args, transport=transport) == 0
    metadata = work.recipient_tree.metadata_path(output)
    claim = json.loads(metadata.read_bytes())
    assert claim["source_revision"] == revision
    assert claim["registration_used"] is False

    dispatch = tmp_path / "job.txt"
    dispatch.write_bytes(b"Use the delivered mechanism on a real job.\n")
    launches = []
    monkeypatch.setattr(
        work, "_runtime_argument", lambda vendor: [f"--{vendor}", sys.executable]
    )
    original_run = subprocess.run
    def capture_seat(command, *run_args, **run_kwargs):
        if len(command) > 1 and Path(command[1]).name == "dispatch_seat.py":
            launches.append(command)
            return subprocess.CompletedProcess(command, 0)
        return original_run(command, *run_args, **run_kwargs)
    monkeypatch.setattr(work.subprocess, "run", capture_seat)
    assert work.execute_stage(
        state(AFFIRMED), work.Decision("use", True, "fresh", "holder-named-stage"),
        holder, None, dispatch_path=dispatch, tree_metadata=metadata, transport=transport,
    ) == 0
    assert len(launches) == 1
    assert Path(launches[0][launches[0].index("--root") + 1]) == output.resolve()


def test_run_use_refuses_recomputed_metadata_for_an_unlanded_commit(
        tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    (holder / "job.md").write_bytes(b"landed consumer\n")
    (holder / "SKILL.md").write_bytes(b"loading surface\n")
    (holder / ".gitattributes").write_bytes(b"* text=auto eol=lf\n")
    git(holder, "add", "job.md", "SKILL.md", ".gitattributes")
    git(holder, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "landed consumer")
    branch = git(holder, "symbolic-ref", "--short", "HEAD").stdout.decode().strip()
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    git(holder, "remote", "add", "origin", str(remote))
    git(holder, "push", "--set-upstream", "origin", branch)

    (holder / "job.md").write_bytes(b"unlanded consumer\n")
    git(holder, "add", "job.md")
    git(holder, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "unlanded consumer")
    unlanded = git(holder, "rev-parse", "HEAD").stdout.decode().strip()
    output = tmp_path / "consumer"
    metadata = work.recipient_tree.create_consumer_tree(
        source=holder, output=output, work="example/product#12",
        producer_version=work.records.producer_version(), mode="adopter", paths=["job.md"],
        loading_surfaces=["SKILL.md"], front_page=None, root_instructions=None,
        directed_paths=[], exclusions=[], deny_texts=[], source_revision=unlanded,
        registration_used=False,
    )
    dispatch = tmp_path / "job.txt"
    dispatch.write_bytes(b"Use the delivered mechanism on a real job.\n")
    launches = []
    original_run = subprocess.run

    def capture_seat(command, *run_args, **run_kwargs):
        if len(command) > 1 and Path(command[1]).name == "dispatch_seat.py":
            launches.append(command)
            return subprocess.CompletedProcess(command, 0)
        return original_run(command, *run_args, **run_kwargs)

    monkeypatch.setattr(work.subprocess, "run", capture_seat)
    transport = FakeTransport({
        "repos/example/product": {"default_branch": branch},
    })

    assert work.execute_stage(
        state(AFFIRMED), work.Decision("use", True, "fresh", "holder-named-stage"),
        holder, None, dispatch_path=dispatch, tree_metadata=metadata, transport=transport,
    ) == 0

    returned = json.loads(capsys.readouterr().out)
    assert returned["reason"] == "consumer-tree-unproved-for-use"
    assert "not reachable" in returned["detail"]
    assert launches == []


def test_tree_revision_refuses_an_unlanded_commit_before_creating_output(
        tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    holder = repository(tmp_path, "holder")
    branch = git(holder, "symbolic-ref", "--short", "HEAD").stdout.decode().strip()
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    git(holder, "remote", "add", "origin", str(remote))
    git(holder, "push", "--set-upstream", "origin", branch)
    git(holder, "checkout", "-b", "side")
    (holder / "side.txt").write_bytes(b"not landed\n")
    git(holder, "add", "side.txt")
    git(holder, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "side")
    revision = git(holder, "rev-parse", "HEAD").stdout.decode().strip()
    output = tmp_path / "consumer"
    args = work.parser().parse_args([
        "tree", "--repo", "example/product", "--issue", "12", "--root", str(holder),
        "--revision", revision, "--mode", "adopter", "--output", str(output),
        "--path", "fixture.txt", "--loading-surface", ".gitignore",
    ])
    with pytest.raises(work.WorkError, match="not reachable"):
        work.run(args, transport=FakeTransport({
            "repos/example/product": {"default_branch": branch},
        }))
    assert not output.exists()
    assert not work.recipient_tree.metadata_path(output).exists()


def test_build_launch_forwards_holder_identity_and_default_timeout_to_the_launcher(
        tmp_path, monkeypatch):
    commands = []
    branch = "tradecraft/12-fixture"
    monkeypatch.setattr(work, "_dispatch_root", lambda *_args: (tmp_path, branch, False))
    monkeypatch.setattr(work, "_attached_branch", lambda _root: branch)
    runtime = Path(sys.executable).resolve()
    monkeypatch.setattr(
        work.subprocess, "run",
        lambda command: commands.append(command) or subprocess.CompletedProcess(command, 0),
    )
    decision = work.Decision("build", True, "fresh", "pull-request-absent")
    fixture = state(
        AFFIRMED,
        "<!-- tradecraft:model-override:v1 implementer=codex:gpt-owner:high -->",
    )
    assert work.execute_stage(
        fixture, decision, tmp_path, "2", "stable-holder-token", codex_path=runtime,
    ) == 0
    assert commands[0][-2:] == ["--holder-session-id", "stable-holder-token"]
    assert commands[0][commands[0].index("--root") + 1] == str(tmp_path)
    assert commands[0][commands[0].index("--timeout-seconds") + 1] == "7200"
    assert commands[0][commands[0].index("--model") + 1] == "gpt-owner"
    assert commands[0][commands[0].index("--effort") + 1] == "high"
    assert commands[0][commands[0].index("--model-source") + 1] == "issue-comment:unknown"
    assert commands[0][commands[0].index("--effort-source") + 1] == "issue-comment:unknown"
    assert Path(commands[0][commands[0].index("--codex") + 1]) == runtime


def test_run_parser_accepts_timeout_and_explicit_runtime_paths(tmp_path):
    runtime = Path(sys.executable).resolve()
    args = work.parser().parse_args([
        "run", "build", "--repo", "acme/widget", "--issue", "3",
        "--root", str(tmp_path), "--timeout-seconds", "42.5",
        "--claude", str(runtime), "--codex", str(runtime),
    ])
    assert args.timeout_seconds == 42.5
    assert args.claude == runtime
    assert args.codex == runtime


def test_invalid_explicit_runtime_refuses_before_root_selection(tmp_path, monkeypatch):
    monkeypatch.setattr(
        work, "_dispatch_root",
        lambda *_args, **_kwargs: pytest.fail("invalid runtime must refuse before root access"),
    )

    with pytest.raises(work.WorkError, match="--codex does not name a file"):
        work.execute_stage(
            state(AFFIRMED),
            work.Decision("build", True, "fresh", "holder-named-stage"),
            tmp_path, None, "holder-session", codex_path=tmp_path / "missing-codex",
        )


def test_resume_marker_equal_to_holder_identity_is_rejected(
        tmp_path, monkeypatch, capsys):
    fixture = state(f"<!-- tradecraft:builder-session:v1 session={SESSION} -->", pr=True)
    monkeypatch.setattr(work, "resume_session", lambda *_args, **_kwargs: SESSION)
    monkeypatch.setattr(
        work.subprocess, "run",
        lambda *_args, **_kwargs: pytest.fail("holder session must not resume as builder"),
    )
    decision = work.Decision("floor", True, "resume", "current-head-floor-missing-or-red")
    assert work.execute_stage(fixture, decision, tmp_path, None, SESSION) == 0
    returned = json.loads(capsys.readouterr().out)
    assert returned["reason"] == "resume-session-identifies-holder-for-floor"


def test_execute_stage_passes_the_recovered_session_to_the_implementer(
        tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(work, "resume_session", lambda *_args, **_kwargs: SESSION)
    monkeypatch.setattr(
        work, "_dispatch_root", lambda *_args: (
            tmp_path, "tradecraft/12-fixture", False
        )
    )
    monkeypatch.setattr(work, "_attached_branch", lambda _root: "tradecraft/12-fixture")

    def run(command):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(work.subprocess, "run", run)
    decision = work.Decision("floor", True, "resume", "current-head-floor-missing-or-red")
    assert work.execute_stage(
        state(AFFIRMED, pr=True), decision, tmp_path, None, "holder-session"
    ) == 0
    assert commands[0][-4:] == [
        "--holder-session-id", "holder-session", "--resume", SESSION,
    ]


def test_judging_root_is_empty_detached_and_removes_it_afterward(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", str(root)], stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    (root / "fixture.txt").write_bytes(b"fixture\n")
    subprocess.run(["git", "-C", str(root), "add", "fixture.txt"], stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    subprocess.run([
        "git", "-C", str(root), "-c", "user.name=fixture",
        "-c", "user.email=fixture@example.com", "commit", "-m", "fixture",
    ], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    with work.judging_root(root.resolve()) as recipient:
        recipient_path = recipient
        assert recipient != root.resolve()
        head = subprocess.run(
            ["git", "-C", str(recipient), "symbolic-ref", "-q", "HEAD"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        assert head.returncode == 1
        assert not (recipient / "fixture.txt").exists()
        assert git(recipient, "rev-list", "--count", "HEAD").stdout.strip() == b"1"
        assert git(recipient, "remote").stdout.strip() == b""
        assert (recipient / ".git").resolve() != (root / ".git").resolve()
    assert not recipient_path.exists()


@pytest.mark.parametrize("stage", work.COMMANDS)
def test_power_user_commands_run_one_named_stage(stage, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    args = work.parser().parse_args([
        "run", stage, "--repo", "acme/widget", "--issue", "3", "--root", str(tmp_path),
        "--use-rules", str(LIB / "use-rules.json"),
    ])
    captured = []

    class MinimalTransport:
        def get(self, endpoint, *, paginate=False):
            if endpoint.endswith("/comments") or "/pulls?" in endpoint:
                return []
            return {"number": 3, "state": "open", "body": "", "labels": []}

    assert work.run(
        args, transport=MinimalTransport(),
        executor=lambda state, decision, root, instalment, holder: captured.append(decision) or 0,
    ) == 0
    assert [(item.stage, item.reason) for item in captured] == [(stage, "holder-named-stage")]


def test_power_user_use_is_an_explicit_named_stage(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    args = work.parser().parse_args([
        "run", "use", "--repo", "acme/widget", "--issue", "3", "--root", str(tmp_path),
        "--use-rules", str(LIB / "use-rules.json"),
    ])
    captured = []

    class MinimalTransport:
        def get(self, endpoint, *, paginate=False):
            if endpoint.endswith("/comments") or "/pulls?" in endpoint:
                return []
            return {"number": 3, "state": "open", "body": "", "labels": []}

    assert work.run(
        args, transport=MinimalTransport(),
        executor=lambda state, decision, root, instalment, holder: captured.append(decision) or 0,
    ) == 0
    assert len(captured) == 1
    assert (captured[0].stage, captured[0].dispatch, captured[0].continuity) == (
        "use", True, "fresh",
    )
    assert captured[0].reason == "holder-named-stage"


def test_registry_write_is_atomic_shape_and_canonical(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    holder = tmp_path / "holder"
    holder.mkdir()
    root = tmp_path / "tree"
    root.mkdir()
    work.register_worktree(
        root, "acme/widget", 3, "2", "holder-session",
        holder_root=holder, branch="tradecraft/3-abcdef123456",
        guard_status="unavailable",
    )
    recorded = json.loads(work.registry_path().read_bytes())
    assert recorded == {"schema_version": 1, "worktrees": [{
        "root": str(root.resolve()), "repository": "acme/widget", "issue": 3,
        "instalment": "2", "active": True, "holder_write_guard": "unavailable",
        "holder_session_id": "holder-session",
        "holder_root": str(holder.resolve()), "branch": "tradecraft/3-abcdef123456",
        "revision_before": None, "status_before": None,
    }]}


def test_runtime_without_project_hook_records_enforcement_gap(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_ENTRYPOINT", raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    assert work.holder_guard_status(tmp_path) == "unavailable"


def test_fresh_build_creates_and_reuses_a_branch_worktree_without_touching_holder(
        tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder", ignore_worktrees=False)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    git(holder, "remote", "add", "origin", str(remote))
    (holder / "fixture.txt").write_bytes(b"dirty tracked\n")
    (holder / "untracked.txt").write_bytes(b"dirty untracked\n")
    before = {
        "branch": git(holder, "symbolic-ref", "--short", "HEAD").stdout,
        "head": git(holder, "rev-parse", "HEAD").stdout,
        "status": git(holder, "status", "--porcelain").stdout,
        "tracked": (holder / "fixture.txt").read_bytes(),
        "untracked": (holder / "untracked.txt").read_bytes(),
    }
    launches = []
    original_run = subprocess.run

    def run(command, *args, **kwargs):
        if len(command) > 1 and Path(command[1]).name == "dispatch_implementer.py":
            dispatch = Path(command[command.index("--dispatch") + 1])
            launches.append((command, dispatch.read_bytes()))
            return subprocess.CompletedProcess(command, 0)
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(work.subprocess, "run", run)
    decision = work.Decision("build", True, "fresh", "pull-request-absent")
    assert work.execute_stage(
        state(AFFIRMED), decision, holder, None, "holder-session"
    ) == 0
    assert work.execute_stage(
        state(AFFIRMED), decision, holder, None, "holder-session"
    ) == 0

    recorded = work.read_registry()["worktrees"]
    assert len(recorded) == 1
    row = recorded[0]
    implementation = Path(row["root"])
    assert implementation != holder
    assert implementation.parent == holder / ".claude" / "worktrees"
    exclude = Path(git(holder, "rev-parse", "--git-path", "info/exclude").stdout.decode().strip())
    if not exclude.is_absolute():
        exclude = holder / exclude
    assert b"/.claude/worktrees/" in exclude.resolve().read_bytes().splitlines()
    assert not (holder / ".gitignore").exists()
    assert row["holder_root"] == str(holder)
    assert row["holder_write_guard"] == "unavailable"
    assert git(implementation, "symbolic-ref", "--short", "HEAD").stdout.decode().strip() == row["branch"]
    assert git(implementation, "rev-parse", "HEAD").stdout == before["head"]
    assert [Path(command[command.index("--root") + 1]) for command, _prompt in launches] == [
        implementation, implementation,
    ]
    assert row["branch"].encode() in launches[0][1]
    assert b"do not create or switch to another branch" in launches[0][1]
    assert {
        "branch": git(holder, "symbolic-ref", "--short", "HEAD").stdout,
        "head": git(holder, "rev-parse", "HEAD").stdout,
        "status": git(holder, "status", "--porcelain").stdout,
        "tracked": (holder / "fixture.txt").read_bytes(),
        "untracked": (holder / "untracked.txt").read_bytes(),
    } == before


def test_build_missing_brief_refuses_before_registry_worktree_or_remote_mutation(
        tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder", ignore_worktrees=False)
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    git(holder, "remote", "add", "origin", str(remote))
    registry = work.registry_path()
    registry_before = registry.read_bytes() if registry.exists() else None

    decision = work.Decision("build", True, "fresh", "holder-named-stage")
    assert work.execute_stage(state(), decision, holder, None, "holder-session") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "stage-input-invalid-for-build"
    assert "affirmed brief" in report["detail"]
    assert (registry.read_bytes() if registry.exists() else None) == registry_before
    assert not (holder / ".claude" / "worktrees").exists()
    assert git(remote, "for-each-ref", "--format=%(refname)", "refs/heads").stdout == b""


def test_build_missing_holder_dispatch_refuses_before_root_mutation(
        tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder", ignore_worktrees=False)
    registry = work.registry_path()

    decision = work.Decision("build", True, "fresh", "holder-named-stage")
    assert work.execute_stage(
        state(AFFIRMED), decision, holder, None, "holder-session",
        dispatch_path=tmp_path / "missing-job.txt",
    ) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "stage-input-invalid-for-build"
    assert not registry.exists()
    assert not (holder / ".claude" / "worktrees").exists()


def test_failed_initial_publication_is_retried_and_verified_before_launch(
        tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    git(holder, "remote", "add", "origin", str(remote))
    real_publish = work.publish_implementation_branch
    real_run = subprocess.run
    publish_calls = []
    verified = False
    launches = []

    def publish(root, branch):
        nonlocal verified
        publish_calls.append((root, branch))
        if len(publish_calls) == 1:
            raise work.WorkError(
                "cannot publish implementation branch; repair the remote and retry run build"
            )
        result = real_publish(root, branch)
        verified = True
        return result

    def run(command, *args, **kwargs):
        if len(command) > 1 and Path(command[1]).name == "dispatch_implementer.py":
            assert verified
            launches.append(command)
            return subprocess.CompletedProcess(command, 0)
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(work, "publish_implementation_branch", publish)
    monkeypatch.setattr(work.subprocess, "run", run)
    decision = work.Decision("build", True, "fresh", "holder-named-stage")

    assert work.execute_stage(state(AFFIRMED), decision, holder, None, "holder-session") == 0
    first = json.loads(capsys.readouterr().out)
    assert "retry run build" in first["detail"]
    assert not launches
    assert work.execute_stage(state(AFFIRMED), decision, holder, None, "holder-session") == 0
    assert len(publish_calls) == 2
    assert len(launches) == 1


def test_every_post_build_dispatch_and_judging_stage_uses_registered_root(
        tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    implementation, branch = work.create_implementation_root(
        holder, "example/product", 12, None, "holder-session"
    )
    (implementation / "sentinel.txt").write_bytes(b"implementation only\n")
    git(implementation, "add", "sentinel.txt")
    git(
        implementation, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "sentinel",
    )
    launches = []
    judged_sources = []
    original_run = subprocess.run

    def run(command, *args, **kwargs):
        if len(command) > 1 and Path(command[1]).name in {
                "dispatch_implementer.py", "dispatch_seat.py"}:
            dispatch = Path(command[command.index("--dispatch") + 1])
            launches.append((command, dispatch.read_bytes()))
            return subprocess.CompletedProcess(command, 0)
        return original_run(command, *args, **kwargs)

    def judging(source):
        judged_sources.append(source)
        return nullcontext(source)

    monkeypatch.setattr(work.subprocess, "run", run)
    monkeypatch.setattr(work, "resume_session", lambda *_args, **_kwargs: SESSION)
    fixture = state(AFFIRMED, ARTIFACT, pr=True)
    for stage, continuity in (
        ("artifact", "resume"), ("build", "resume"), ("floor", "resume"),
        ("review-disposition", "resume"), ("release-report", "fresh"),
    ):
        assert work.execute_stage(
            fixture, work.Decision(stage, True, continuity, "fixture"),
            holder, None, "holder-session",
        ) == 0

    monkeypatch.setattr(work, "judging_root", judging)
    assert work.execute_stage(
        fixture, work.Decision("cold-seat", True, "fresh", "fixture"),
        holder, None, "holder-session",
    ) == 0

    implementer_launches = launches[:4]
    assert len(launches) == 5
    assert all(
        Path(command[command.index("--root") + 1]) == implementation
        for command, _prompt in implementer_launches
    )
    assert all(branch.encode() in prompt for _command, prompt in implementer_launches)
    assert (implementation / "sentinel.txt").read_bytes() == b"implementation only\n"
    assert judged_sources == [implementation]


def test_holder_guard_status_requires_the_complete_project_declaration(
        tmp_path, monkeypatch):
    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir()
    complete = {
        "hooks": {"PreToolUse": [{
            "matcher": "Edit|Write|NotebookEdit|Bash|PowerShell",
            "hooks": [
                {"type": "command", "command": "python lib/holder_tree_guard.py"},
                {"type": "command", "command": "python extra.py"},
            ],
        }]},
        "permissions": {"allow": []},
    }
    cases = (
        (None, "unavailable"),
        (b"{malformed", "unavailable"),
        ({"hooks": {"PreToolUse": [{
            "hooks": [{"type": "command", "command": "python lib/holder_tree_guard.py"}],
        }]}}, "available"),
        ({"hooks": {"PreToolUse": [{
            "matcher": "Edit|Write|Bash|PowerShell",
            "hooks": [{"type": "command", "command": "python lib/holder_tree_guard.py"}],
        }]}}, "unavailable"),
        ({"hooks": {"PreToolUse": [{
            "matcher": "Edit|Write|NotebookEdit|Bash|PowerShell",
            "hooks": [{"type": "command", "command": "python unrelated.py"}],
        }]}}, "unavailable"),
        ({"hooks": {"PreToolUse": [{
            "matcher": "Edit|Write|NotebookEdit|Bash|PowerShell",
            "hooks": [{"type": "command", "command": "echo lib/holder_tree_guard.py"}],
        }]}}, "unavailable"),
        (complete, "available"),
    )
    for environment_present in (False, True):
        if environment_present:
            monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "fixture")
            monkeypatch.setenv("CLAUDECODE", "1")
        else:
            monkeypatch.delenv("CLAUDE_CODE_ENTRYPOINT", raising=False)
            monkeypatch.delenv("CLAUDECODE", raising=False)
        for value, expected in cases:
            settings_path.unlink(missing_ok=True)
            if isinstance(value, bytes):
                settings_path.write_bytes(value)
            elif value is not None:
                settings_path.write_text(json.dumps(value), encoding="utf-8")
            assert work.holder_guard_status(tmp_path) == expected


def test_current_root_evidence_refuses_every_invalid_class(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    implementation, branch = work.create_implementation_root(
        holder, "example/product", 12, None, "holder-session"
    )
    valid = registry_row(implementation, holder, branch)
    decision = work.Decision("floor", True, "resume", "fixture")

    def refused(rows):
        write_registry_rows(rows)
        selected = work._dispatch_root(
            state(pr=True), decision, holder, None, "holder-session"
        )
        assert isinstance(selected, work.Decision)
        assert selected.dispatch is False
        return selected.detail

    assert "no active" in refused([])
    assert "multiple active" in refused([valid.copy(), valid.copy()])
    missing = valid.copy()
    missing["root"] = str(tmp_path / "missing")
    assert "is missing" in refused([missing])
    wrong_holder = valid.copy()
    wrong_holder["holder_root"] = str(tmp_path / "another-holder")
    assert "another holder root" in refused([wrong_holder])
    wrong_branch = valid.copy()
    wrong_branch["branch"] = "tradecraft/wrong"
    assert "branch mismatch" in refused([wrong_branch])
    git(implementation, "checkout", "--detach")
    assert "is detached" in refused([valid.copy()])
    git(implementation, "switch", branch)
    foreign = repository(tmp_path, "foreign")
    foreign_row = valid.copy()
    foreign_row["root"] = str(foreign)
    foreign_row["branch"] = work._attached_branch(foreign)
    assert "another Git repository" in refused([foreign_row])

    inactive = valid.copy()
    inactive["active"] = False
    write_registry_rows([inactive])
    artifact = work._dispatch_root(
        state(AFFIRMED), work.Decision("artifact", True, "fresh", "fixture"),
        holder, None, "holder-session",
    )
    assert isinstance(artifact, work.Decision)
    assert "registration history" in artifact.detail


def test_legacy_registration_migrates_before_dispatch_and_names_the_proof_gap(
        tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    implementation, branch = work.create_implementation_root(
        holder, "example/product", 12, None, "holder-session"
    )
    legacy = registry_row(implementation, holder, branch)
    legacy.pop("holder_root")
    legacy.pop("branch")
    write_registry_rows([legacy])
    launches = []
    original_run = subprocess.run

    def run(command, *args, **kwargs):
        if len(command) > 1 and Path(command[1]).name == "dispatch_implementer.py":
            recorded = work.read_registry()["worktrees"][0]
            assert recorded["holder_root"] == str(holder)
            assert recorded["branch"] == branch
            dispatch = Path(command[command.index("--dispatch") + 1])
            launches.append((command, dispatch.read_bytes()))
            return subprocess.CompletedProcess(command, 0)
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(work.subprocess, "run", run)
    monkeypatch.setattr(work, "resume_session", lambda *_args, **_kwargs: SESSION)
    decision = work.Decision("floor", True, "resume", "fixture", "existing detail")

    assert work.execute_stage(
        state(AFFIRMED, pr=True), decision, holder, None, "holder-session"
    ) == 0

    notice = (
        "implementation registration migrated; recorded-holder check was not "
        "enforced on this run"
    )
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["detail"] == f"existing detail; {notice}"
    assert len(launches) == 1
    command, prompt = launches[0]
    assert Path(command[command.index("--root") + 1]) == implementation
    assert notice.encode() in prompt

    other_holder = tmp_path / "other-holder"
    git(holder, "worktree", "add", "-b", "holder-other", str(other_holder), "HEAD")
    with pytest.raises(work.WorkError, match="another holder root"):
        work.resolve_implementation_root(other_holder, "example/product", 12, None)
    git(implementation, "branch", "-m", "tradecraft/12-deadbeefdead")
    with pytest.raises(work.WorkError, match="branch mismatch"):
        work.resolve_implementation_root(holder, "example/product", 12, None)


def test_legacy_migration_refuses_holder_root_and_names_adopt(
        tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    branch = work._attached_branch(holder)
    legacy = registry_row(holder, holder, branch)
    legacy.pop("holder_root")
    legacy.pop("branch")
    write_registry_rows([legacy])
    before = work.registry_path().read_bytes()

    with pytest.raises(work.WorkError, match="run adopt with a distinct"):
        work.resolve_implementation_root(holder, "example/product", 12, None)

    assert work.registry_path().read_bytes() == before


@pytest.mark.parametrize(("case", "message"), [
    ("missing-holder", "invalid holder_root or branch"),
    ("missing-branch", "invalid holder_root or branch"),
    ("empty-holder", "invalid holder_root or branch"),
    ("nonstring-branch", "invalid holder_root or branch"),
    ("missing-root", "is missing"),
    ("nested-root", "not a Git worktree top level"),
    ("detached-root", "is detached"),
    ("foreign-root", "another Git repository"),
])
def test_legacy_migration_refuses_unproved_shapes_without_rewriting_registry(
        tmp_path, monkeypatch, case, message):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    implementation, branch = work.create_implementation_root(
        holder, "example/product", 12, None, "holder-session"
    )
    row = registry_row(implementation, holder, branch)
    if case == "missing-holder":
        row.pop("holder_root")
    elif case == "missing-branch":
        row.pop("branch")
    elif case == "empty-holder":
        row["holder_root"] = ""
    elif case == "nonstring-branch":
        row["branch"] = 12
    else:
        row.pop("holder_root")
        row.pop("branch")
        if case == "missing-root":
            row["root"] = str(tmp_path / "missing")
        elif case == "nested-root":
            nested = implementation / "nested"
            nested.mkdir()
            row["root"] = str(nested)
        elif case == "detached-root":
            git(implementation, "checkout", "--detach")
        elif case == "foreign-root":
            foreign = repository(tmp_path, "foreign")
            row["root"] = str(foreign)
    write_registry_rows([row])
    before = work.registry_path().read_bytes()

    selected = work._dispatch_root(
        state(pr=True), work.Decision("floor", True, "resume", "fixture"),
        holder, None, "holder-session",
    )

    assert isinstance(selected, work.Decision)
    assert selected.dispatch is False
    assert message in selected.detail
    assert work.registry_path().read_bytes() == before


def test_legacy_migration_write_failure_refuses_dispatch_without_changing_registry(
        tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    implementation, branch = work.create_implementation_root(
        holder, "example/product", 12, None, "holder-session"
    )
    legacy = registry_row(implementation, holder, branch)
    legacy.pop("holder_root")
    legacy.pop("branch")
    write_registry_rows([legacy])
    before = work.registry_path().read_bytes()

    def fail_write(_current):
        raise OSError("fixture write failure")

    monkeypatch.setattr(work, "write_registry", fail_write)
    selected = work._dispatch_root(
        state(pr=True), work.Decision("floor", True, "resume", "fixture"),
        holder, None, "holder-session",
    )

    assert isinstance(selected, work.Decision)
    assert selected.dispatch is False
    assert "cannot persist migrated" in selected.detail
    assert work.registry_path().read_bytes() == before


def test_sweep_releases_only_proven_terminal_rows_and_keeps_worktrees(
        tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    states = {
        1: ("open", [{"number": 101, "state": "closed", "merged_at": None,
                       "body": "Fixes #1"}]),
        2: ("open", [{"number": 102, "state": "closed", "merged_at": "now",
                       "body": "Fixes #2"}]),
        3: ("closed", []),
        4: ("open", [{"number": 104, "state": "open", "merged_at": None,
                       "body": "Fixes #4"}]),
        5: ("open", []),
        6: ("open", [
            {"number": 106, "state": "closed", "body": "Fixes #6"},
            {"number": 107, "state": "closed", "body": "Resolves #6"},
        ]),
    }
    values = {}
    rows = []
    roots = {}
    all_pulls = [pull for _issue_state, pulls in states.values() for pull in pulls]
    for issue_number in range(1, 8):
        root = tmp_path / f"kept-{issue_number}"
        root.mkdir()
        roots[issue_number] = root
        rows.append({
            "root": str(root), "repository": "acme/widget", "issue": issue_number,
            "instalment": None, "active": True,
        })
        if issue_number in states:
            issue_state, pulls = states[issue_number]
            base = "repos/acme/widget"
            values[f"{base}/issues/{issue_number}"] = {
                "number": issue_number, "state": issue_state, "body": "",
            }
            values[f"{base}/issues/{issue_number}/comments"] = []
            values[f"{base}/pulls?state=all&per_page=100"] = all_pulls
    write_registry_rows(rows)
    work.sweep_registry(FakeTransport(values))
    recorded = {row["issue"]: row["active"] for row in work.read_registry()["worktrees"]}
    assert recorded == {
        1: True, 2: False, 3: False, 4: True, 5: True, 6: True, 7: True,
    }
    assert all(root.is_dir() for root in roots.values())
    warnings = capsys.readouterr().err
    assert "acme/widget#6" not in warnings
    assert "acme/widget#7" in warnings


@pytest.mark.parametrize(("pull_branch", "merged_at", "expected_active"), [
    ("tradecraft/12-former", "now", True),
    ("tradecraft/12-current", None, True),
    ("tradecraft/12-current", "now", False),
])
def test_sweep_releases_only_a_terminal_pull_request_for_the_registered_branch(
        tmp_path, monkeypatch, pull_branch, merged_at, expected_active):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = tmp_path / "holder"
    holder.mkdir()
    implementation = tmp_path / "implementation"
    implementation.mkdir()
    write_registry_rows([{
        "root": str(implementation), "holder_root": str(holder),
        "branch": "tradecraft/12-current", "repository": "acme/widget",
        "issue": 12, "instalment": None, "active": True,
    }])
    base = "repos/acme/widget"
    values = {
        f"{base}/issues/12": {
            "number": 12, "state": "open", "body": "",
        },
        f"{base}/issues/12/comments": [],
        f"{base}/pulls?state=all&per_page=100": [{
            "number": 112, "state": "closed", "merged_at": merged_at,
            "body": "Fixes #12", "head": {"ref": pull_branch},
        }],
    }

    work.sweep_registry(FakeTransport(values))

    row = work.read_registry()["worktrees"][0]
    assert row["active"] is expected_active
    assert implementation.is_dir()


def test_direct_release_is_idempotent_and_keeps_legacy_worktree(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir()
    write_registry_rows([{
        "root": str(legacy_root), "repository": "acme/widget", "issue": 3,
        "instalment": None, "active": True,
    }])
    assert work.release_registration("acme/widget", 3, legacy_root, None) == legacy_root
    assert work.release_registration("acme/widget", 3, legacy_root, None) == legacy_root
    assert work.read_registry()["worktrees"][0]["active"] is False
    assert legacy_root.is_dir()


def test_direct_release_selects_the_active_registration_from_history(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = tmp_path / "holder"
    holder.mkdir()
    former = tmp_path / "former"
    former.mkdir()
    current = tmp_path / "current"
    current.mkdir()
    write_registry_rows([
        {
            "root": str(former), "holder_root": str(holder),
            "repository": "acme/widget", "issue": 3,
            "instalment": None, "active": False,
        },
        {
            "root": str(current), "holder_root": str(holder),
            "repository": "acme/widget", "issue": 3,
            "instalment": None, "active": True,
        },
    ])

    assert work.release_registration("acme/widget", 3, holder, None) == current
    assert [row["active"] for row in work.read_registry()["worktrees"]] == [False, False]
    assert former.is_dir()
    assert current.is_dir()


def test_direct_release_is_a_noop_with_multiple_historical_registrations(
        tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = tmp_path / "holder"
    holder.mkdir()
    former = tmp_path / "former"
    former.mkdir()
    latest = tmp_path / "latest"
    latest.mkdir()
    write_registry_rows([
        {
            "root": str(former), "holder_root": str(holder),
            "repository": "acme/widget", "issue": 3,
            "instalment": None, "active": False,
        },
        {
            "root": str(latest), "holder_root": str(holder),
            "repository": "acme/widget", "issue": 3,
            "instalment": None, "active": False,
        },
    ])
    before = work.registry_path().read_bytes()

    assert work.release_registration("acme/widget", 3, holder, None) == latest
    assert [row["active"] for row in work.read_registry()["worktrees"]] == [False, False]
    assert work.registry_path().read_bytes() == before
    assert former.is_dir()
    assert latest.is_dir()


def test_direct_release_refuses_multiple_active_registrations(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = tmp_path / "holder"
    holder.mkdir()
    rows = []
    for name in ("first", "second"):
        root = tmp_path / name
        root.mkdir()
        rows.append({
            "root": str(root), "holder_root": str(holder),
            "repository": "acme/widget", "issue": 3,
            "instalment": None, "active": True,
        })
    write_registry_rows(rows)

    with pytest.raises(work.WorkError, match="multiple implementation registrations"):
        work.release_registration("acme/widget", 3, holder, None)

    assert all(row["active"] is True for row in work.read_registry()["worktrees"])


def test_release_command_sweeps_first_and_never_dispatches(tmp_path, monkeypatch, capsys):
    args = work.parser().parse_args([
        "release", "--repo", "acme/widget", "--issue", "3", "--root", str(tmp_path),
    ])
    calls = []
    monkeypatch.setattr(work, "sweep_registry", lambda transport: calls.append(transport))
    monkeypatch.setattr(
        work, "release_registration", lambda *_args: tmp_path / "implementation"
    )
    transport = object()
    assert work.run(
        args, transport=transport,
        executor=lambda *_args: pytest.fail("release must not dispatch"),
    ) == 0
    assert calls == [transport]
    assert "implementation" in capsys.readouterr().out
    assert "release" in work.parser().format_help()


def test_adopt_command_recovers_a_released_tree_without_dispatching_or_moving_it(
        tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    implementation, branch = work.create_implementation_root(
        holder, "example/product", 12, None, "first-holder-session"
    )
    assert work.release_registration("example/product", 12, holder, None) == implementation
    competing = tmp_path / "competing"
    competing.mkdir()
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    current = work.read_registry()
    current["worktrees"].extend([
        {
            "root": str(competing), "repository": "example/product", "issue": 12,
            "instalment": None, "active": True,
        },
        {
            "root": str(unrelated), "repository": "example/product", "issue": 13,
            "instalment": None, "active": True,
        },
    ])
    work.write_registry(current)
    worktrees_before = git(holder, "worktree", "list", "--porcelain").stdout
    calls = []
    monkeypatch.setattr(work, "sweep_registry", lambda transport: calls.append(transport))
    args = work.parser().parse_args([
        "adopt", "--repo", "example/product", "--issue", "12",
        "--root", str(holder), "--implementation-root", str(implementation),
        "--holder-session-id", SESSION,
    ])
    transport = object()

    assert work.run(
        args, transport=transport,
        executor=lambda *_args: pytest.fail("adopt must not dispatch"),
    ) == 0

    assert calls == [transport]
    returned = json.loads(capsys.readouterr().out)
    assert {key: returned[key] for key in ("adopted_root", "branch")} == {
        "adopted_root": str(implementation), "branch": branch,
    }
    rows = work.read_registry()["worktrees"]
    matching = [row for row in rows if row.get("issue") == 12]
    active = [row for row in matching if row.get("active") is True]
    assert len(active) == 1
    assert active[0] == {
        "root": str(implementation), "repository": "example/product", "issue": 12,
        "instalment": None, "active": True, "holder_session_id": SESSION,
        "holder_write_guard": "unavailable", "holder_root": str(holder),
        "branch": branch, "revision_before": active[0]["revision_before"],
        "status_before": "",
    }
    assert active[0]["revision_before"]
    assert all(row.get("active") is False for row in matching[:-1])
    assert next(row for row in rows if row.get("issue") == 13)["active"] is True
    assert work.resolve_implementation_root(
        holder, "example/product", 12, None
    ) == (implementation, branch, False)
    assert git(holder, "worktree", "list", "--porcelain").stdout == worktrees_before
    assert implementation.is_dir()
    assert competing.is_dir()


def test_adopt_accepts_a_non_entrance_branch(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    implementation, _branch = work.create_implementation_root(
        holder, "example/product", 12, None, "first-holder-session"
    )
    git(implementation, "branch", "-m", "legacy-feature")

    adopted_root, adopted_branch = work.adopt_registration(
        holder, implementation, "example/product", 12, None, SESSION
    )

    assert (adopted_root, adopted_branch) == (implementation, "legacy-feature")
    matching = [
        row for row in work.read_registry()["worktrees"]
        if row.get("repository") == "example/product" and row.get("issue") == 12
    ]
    assert sum(row.get("active") is True for row in matching) == 1
    assert matching[-1]["branch"] == "legacy-feature"


def test_adopt_refuses_another_issues_entrance_branch_without_changing_registry(
        tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    implementation, _branch = work.create_implementation_root(
        holder, "example/product", 12, None, "first-holder-session"
    )
    before = work.registry_path().read_bytes()

    with pytest.raises(work.WorkError, match="does not belong to issue 13"):
        work.adopt_registration(
            holder, implementation, "example/product", 13, None, SESSION
        )

    assert work.registry_path().read_bytes() == before


def test_adopt_requires_an_instalment_when_named_registrations_exist(
        tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    implementation, _branch = work.create_implementation_root(
        holder, "example/product", 12, None, "first-holder-session"
    )
    current = work.read_registry()
    named = dict(current["worktrees"][0])
    named["instalment"] = "2"
    current["worktrees"].append(named)
    work.write_registry(current)
    before = work.registry_path().read_bytes()

    with pytest.raises(work.WorkError, match="requires --instalment"):
        work.adopt_registration(
            holder, implementation, "example/product", 12, None, SESSION
        )

    assert work.registry_path().read_bytes() == before


@pytest.mark.parametrize(("case", "message"), [
    ("missing-holder-identity", "requires --holder-session-id"),
    ("holder-root", "distinct from the holder root"),
    ("missing-root", "does not exist"),
    ("nested-root", "not a Git worktree top level"),
    ("detached-root", "is detached"),
    ("foreign-root", "another Git repository"),
])
def test_adopt_refuses_unproved_trees_without_changing_registry(
        tmp_path, monkeypatch, case, message):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    implementation, branch = work.create_implementation_root(
        holder, "example/product", 12, None, "first-holder-session"
    )
    issue = 12
    identity = SESSION
    candidate = implementation
    if case == "missing-holder-identity":
        identity = ""
    elif case == "holder-root":
        candidate = holder
    elif case == "missing-root":
        candidate = tmp_path / "missing"
    elif case == "nested-root":
        candidate = implementation / "nested"
        candidate.mkdir()
    elif case == "detached-root":
        git(implementation, "checkout", "--detach")
    elif case == "foreign-root":
        candidate = repository(tmp_path, "foreign")
        git(candidate, "branch", "-m", "tradecraft/12-fedcba987654")
    before = work.registry_path().read_bytes()

    with pytest.raises(work.WorkError, match=message):
        work.adopt_registration(
            holder, candidate, "example/product", issue, None, identity
        )

    assert work.registry_path().read_bytes() == before
    assert implementation.is_dir()
    assert branch.startswith("tradecraft/12-")


def test_help_distinguishes_direct_commands_from_a_dispatching_stage():
    help_text = " ".join(work.parser().format_help().split())
    assert (
        "Report the next change step without mutation, explicitly run one named stage"
    ) in help_text
    assert (
        "omit to decide read-only; run names one stage; tree builds a consumer root"
    ) in help_text
    assert "--implementation-root IMPLEMENTATION_ROOT" in help_text
    assert "--holder-session-id HOLDER_SESSION_ID" in help_text
    assert "--tree-metadata TREE_METADATA" in help_text
    assert "required by adopt" in help_text

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
WOULD = "<!-- tradecraft:cold-verdict:v1 verdict=would -->"
HOLDER = "<!-- tradecraft:holder-reading:v1 result=no-amendment -->"
FLOOR = f"<!-- tradecraft:floor:v1 head={SHA} status=pass -->"
USE = f"<!-- tradecraft:use:v1 head={SHA} status=pass changed=false -->"
REVIEWED = "<!-- tradecraft:connected-reviewer:v1 name=fixture status=complete -->"
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


def repository(tmp_path, name="repository"):
    root = tmp_path / name
    root.mkdir()
    subprocess.run(
        ["git", "init", str(root)], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    (root / ".gitignore").write_bytes(b".claude/worktrees/\n")
    (root / "fixture.txt").write_bytes(b"fixture\n")
    git(root, "add", ".gitignore", "fixture.txt")
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
    (state(AFFIRMED, ARTIFACT, "<!-- tradecraft:cold-verdict:v1 verdict=would-not -->"),
     ("artifact", True, "resume")),
    (state(AFFIRMED, ARTIFACT, WOULD), ("holder-read", False, None)),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER), ("build", True, "fresh")),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, pr=True), ("floor", True, "resume")),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, pr=True), ("use", True, "fresh")),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR,
           f"<!-- tradecraft:use:v1 head={SHA} status=pass changed=true -->", pr=True),
     ("build", True, "resume")),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE, pr=True),
     ("ready-reviewers", False, None)),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE, pr=True, draft=False),
     ("waiting", False, None)),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE, pr=True, draft=False,
           reviewer_ran=True),
     ("release-report", True, "fresh")),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
           "<!-- tradecraft:panel-stage:v1 stage=cold-pass status=complete -->",
           "<!-- tradecraft:panel-stage:v1 stage=defense status=complete -->",
           "<!-- tradecraft:panel-stage:v1 stage=floor-fixes status=complete -->",
           pr=True, draft=False, reviewer_ran=True), ("release-report", True, "fresh")),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
           pr=True, draft=False, reviewer_ran=True, issue_state="closed"),
     ("terminal", False, None)),
])
def test_each_state_table_row_routes_exactly_one_stage(fixture, expected):
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.dispatch, decision.continuity) == expected


def test_red_check_routes_floor_even_with_a_current_head_floor_marker():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, pr=True)
    fixture.checks = [{"conclusion": "failure"}]
    assert work.decide(fixture, RULES).stage == "floor"


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
    assert decision.as_dict() == {
        "stage": "ambiguous-pr", "dispatch": False, "continuity": None,
        "reason": "multiple-candidate-pull-requests", "detail": "7,8",
    }


def test_closed_completed_issue_is_terminal_before_three_candidate_pull_requests():
    fixture = state(issue_state="closed")
    fixture.issue["state_reason"] = "completed"
    fixture.ambiguous_prs = [666, 667, 668]
    decision = work.decide(fixture, RULES)
    assert decision.as_dict() == {
        "stage": "terminal", "dispatch": False, "continuity": None,
        "reason": "issue-or-pull-request-terminal", "detail": None,
    }


@pytest.mark.parametrize(("risk", "lane"), list(work.LANES.items()))
def test_each_lawful_review_risk_lane_pair_is_affirmed(risk, lane):
    assert work.review_lane(f"Review risk: {risk}\nReview lane: {lane}\n") == (risk, lane)


@pytest.mark.parametrize("text", [
    "Review lane: connected\n",
    "Review risk: ordinary\n",
    "Review risk: ordinary\nReview lane: substantial-panel\n",
    "Review risk: ordinary\nReview risk: elevated\nReview lane: connected\n",
])
def test_missing_or_crossed_review_rows_cannot_become_affirmed_state(text):
    fixture = state("<!-- tradecraft:affirmed-brief:v1 -->\n" + text)
    assert work.decide(fixture, RULES).stage == "affirmation-invalid"


def test_authorized_marker_advances_the_entrance():
    assert work.decide(state(AFFIRMED), RULES).stage == "artifact"


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
    assert work.decide(fixture, RULES).stage == "artifact"


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


def test_reopened_issue_ignores_its_merged_former_implementing_pull_request():
    issue = {"number": 12, "state": "open", "body": ""}
    pulls = [{
        "number": 9, "state": "closed", "merged_at": "2026-09-01T00:00:00Z",
        "body": "Closes #12",
    }]
    candidates = work._candidate_prs(12, issue, [], pulls, CONFIG)
    fixture = work.WorkState("acme/widget", 12, issue, config=CONFIG)
    assert candidates == set()
    assert work.decide(fixture, RULES).stage == "convergence"


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


def test_run_reads_the_work_configuration_from_root(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    configured_work(tmp_path, ["acme/product-app"])
    rules_directory = tmp_path / "lib"
    rules_directory.mkdir()
    (rules_directory / "use-rules.json").write_bytes((LIB / "use-rules.json").read_bytes())
    args = work.parser().parse_args([
        "--repo", "example/tradecraft", "--issue", "3", "--root", str(tmp_path),
    ])
    captured = []

    class PracticeTransport:
        def get(self, endpoint, *, paginate=False):
            if endpoint.endswith("/comments") or "/pulls?" in endpoint:
                return []
            return {
                "number": 3,
                "state": "open",
                "body": AFFIRMED + "\nhttps://github.com/ACME/PRODUCT-APP/issues/7",
                "labels": [{"name": "practice-facing"}],
                "user": {"login": PRODUCER},
            }

    assert work.run(
        args, transport=PracticeTransport(),
        executor=lambda state, decision, root, instalment, holder: captured.append(decision) or 0,
    ) == 0
    assert [(decision.stage, decision.reason) for decision in captured] == [
        ("artifact", "artifact-marker-absent"),
    ]


def test_builder_prompt_names_one_stage_and_forbids_pipeline_dispatch():
    fixture = state(AFFIRMED)
    prompt = work._stage_prompt(fixture, work.Decision("artifact", True, "fresh", "fixture"))
    assert prompt.count(b'"stage": "artifact"') == 1
    assert b"Do not start or dispatch a later stage" in prompt
    evidence = json.loads(prompt.split(b"\n\n", 1)[1])
    assert evidence["github"]["issue_comments"][0]["body"] == AFFIRMED


def test_build_prompt_tells_the_holder_to_post_the_builder_session_marker():
    prompt = work._stage_prompt(
        state(AFFIRMED), work.Decision("build", True, "fresh", "fixture")
    )
    assert b"<!-- tradecraft:builder-session:v1 session=SESSION -->" in prompt


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
    fixture = state(AFFIRMED, "OTHER COMMENT MUST STAY OUT", artifact)
    captured = []
    monkeypatch.setattr(work, "judging_root", lambda _root: nullcontext(tmp_path))
    monkeypatch.setattr(work, "_git_snapshot", lambda _root: (SHA, ""))

    def run(command):
        dispatch = Path(command[command.index("--dispatch") + 1])
        captured.append(dispatch.read_bytes())
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(work.subprocess, "run", run)
    decision = work.Decision("cold-seat", True, "fresh", "fixture")
    assert work.execute_stage(fixture, decision, tmp_path, None) == 0
    assert artifact.encode("utf-8") in captured[0]
    assert AFFIRMED.encode("utf-8") in captured[0]
    assert b"OTHER COMMENT MUST STAY OUT" not in captured[0]
    assert b'"issue_comments"' not in captured[0]


def dispatch_bundle(record_root, *, work_value="example/product#12", stage="build",
                    session=SESSION, completed_at="2026-09-20T10:00:00+00:00"):
    bundle = record_root / stage
    bundle.mkdir(parents=True, exist_ok=True)
    request = bundle / "result.md.request.json"
    run = bundle / "result.md.run.json"
    request.write_text(json.dumps({
        "schema_version": 2, "work": work_value, "stage": stage,
    }), encoding="utf-8")
    run.write_text(json.dumps({
        "schema_version": 2,
        "completed_at": completed_at,
        "attempts": [{"observed": {"session_id": session}}],
    }), encoding="utf-8")


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
        state(pr=True), decision, tmp_path, None, "holder-session"
    ) == 0
    returned = json.loads(capsys.readouterr().out)
    assert returned == {
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


def test_build_launch_forwards_holder_identity_to_the_implementation_root(
        tmp_path, monkeypatch):
    commands = []
    branch = "tradecraft/12-fixture"
    monkeypatch.setattr(work, "_dispatch_root", lambda *_args: (tmp_path, branch))
    monkeypatch.setattr(work, "_attached_branch", lambda _root: branch)
    monkeypatch.setattr(
        work.subprocess, "run",
        lambda command: commands.append(command) or subprocess.CompletedProcess(command, 0),
    )
    decision = work.Decision("build", True, "fresh", "pull-request-absent")
    assert work.execute_stage(
        state(), decision, tmp_path, "2", "stable-holder-token"
    ) == 0
    assert commands[0][-2:] == ["--holder-session-id", "stable-holder-token"]
    assert commands[0][commands[0].index("--root") + 1] == str(tmp_path)


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
        work, "_dispatch_root", lambda *_args: (tmp_path, "tradecraft/12-fixture")
    )
    monkeypatch.setattr(work, "_attached_branch", lambda _root: "tradecraft/12-fixture")

    def run(command):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(work.subprocess, "run", run)
    decision = work.Decision("floor", True, "resume", "current-head-floor-missing-or-red")
    assert work.execute_stage(
        state(pr=True), decision, tmp_path, None, "holder-session"
    ) == 0
    assert commands[0][-4:] == [
        "--holder-session-id", "holder-session", "--resume", SESSION,
    ]


def test_judging_root_detaches_an_attached_tree_and_removes_it_afterward(tmp_path):
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
        assert (recipient / "fixture.txt").read_bytes().replace(b"\r\n", b"\n") == b"fixture\n"
    assert not recipient_path.exists()


@pytest.mark.parametrize("command", work.COMMANDS)
def test_power_user_commands_run_one_named_stage(command, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    args = work.parser().parse_args([
        command, "--repo", "acme/widget", "--issue", "3", "--root", str(tmp_path),
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
    assert [(item.stage, item.reason) for item in captured] == [(command, "power-user-stage-command")]


def test_registry_write_is_atomic_shape_and_canonical(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    root = tmp_path / "tree"
    root.mkdir()
    work.register_worktree(
        root, "acme/widget", 3, "2", "holder-session", guard_status="unavailable"
    )
    recorded = json.loads(work.registry_path().read_bytes())
    assert recorded == {"schema_version": 1, "worktrees": [{
        "root": str(root.resolve()), "repository": "acme/widget", "issue": 3,
        "instalment": "2", "active": True, "holder_write_guard": "unavailable",
        "holder_session_id": "holder-session",
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
    holder = repository(tmp_path, "holder")
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
        state(), decision, holder, None, "holder-session"
    ) == 0
    assert work.execute_stage(
        state(), decision, holder, None, "holder-session"
    ) == 0

    recorded = work.read_registry()["worktrees"]
    assert len(recorded) == 1
    row = recorded[0]
    implementation = Path(row["root"])
    assert implementation != holder
    assert implementation.parent == holder / ".claude" / "worktrees"
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
    for stage in ("cold-seat", "use"):
        assert work.execute_stage(
            fixture, work.Decision(stage, True, "fresh", "fixture"),
            holder, None, "holder-session",
        ) == 0

    implementer_launches = launches[:5]
    assert all(
        Path(command[command.index("--root") + 1]) == implementation
        for command, _prompt in implementer_launches
    )
    assert all(branch.encode() in prompt for _command, prompt in implementer_launches)
    assert (implementation / "sentinel.txt").read_bytes() == b"implementation only\n"
    assert judged_sources == [implementation, implementation]


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


def test_unproved_root_evidence_refuses_every_invalid_class(tmp_path, monkeypatch):
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
    legacy = valid.copy()
    legacy.pop("holder_root")
    legacy.pop("branch")
    assert "legacy evidence" in refused([legacy])
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
        1: False, 2: False, 3: False, 4: True, 5: True, 6: True, 7: True,
    }
    assert all(root.is_dir() for root in roots.values())
    warnings = capsys.readouterr().err
    assert "acme/widget#6" in warnings
    assert "acme/widget#7" in warnings


@pytest.mark.parametrize(("pull_branch", "merged_at", "expected_active"), [
    ("tradecraft/12-former", "now", True),
    ("tradecraft/12-current", None, False),
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


def test_help_distinguishes_release_from_a_dispatching_stage():
    help_text = " ".join(work.parser().format_help().split())
    assert "run exactly one change stage, or release one registration" in help_text
    assert (
        "use release to make one registration inactive without dispatching or "
        "deleting its worktree"
    ) in help_text

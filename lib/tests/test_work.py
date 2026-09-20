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


def test_listed_review_on_an_old_head_does_not_count():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False)
    fixture.reviews = [{
        "body": "reviewed", "commit_id": "b" * 40,
        "user": {"login": REVIEWER, "type": "Bot"},
    }]
    assert work.decide(fixture, RULES).stage == "waiting"


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
        f"{base}/pulls?state=all&per_page=100": [{"number": 9, "body": ""}],
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


def test_pull_request_body_standalone_closing_reference_is_the_candidate():
    candidates = work._candidate_prs(
        12, {"number": 12, "body": ""}, [],
        [{"number": 9, "body": "Context\nCloses #12\nMore context"}],
        CONFIG,
    )
    assert candidates == {9}


def test_unauthorized_implementing_pr_marker_is_not_a_candidate():
    candidates = work._candidate_prs(
        12,
        {"number": 12, "body": "", "user": {"login": PRODUCER}},
        [{"body": "<!-- tradecraft:implementing-pr:v1 number=9 -->",
          "user": {"login": "untrusted-commenter"}}],
        [{"number": 9, "body": "A citation, not a closing reference"}],
        CONFIG,
    )
    assert candidates == set()


def test_two_pull_request_bodies_closing_the_issue_are_ambiguous():
    base = "repos/acme/widget"
    values = {
        f"{base}/issues/12": {"number": 12, "state": "open", "body": "", "labels": []},
        f"{base}/issues/12/comments": [],
        f"{base}/pulls?state=all&per_page=100": [
            {"number": 7, "body": "Fixes #12"},
            {"number": 8, "body": "RESOLVED #12"},
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


def test_run_reads_the_work_configuration_from_root(tmp_path):
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
        executor=lambda state, decision, root, instalment: captured.append(decision) or 0,
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
    assert work.execute_stage(state(pr=True), decision, tmp_path, None) == 0
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


def test_execute_stage_passes_the_recovered_session_to_the_implementer(
        tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(work, "resume_session", lambda *_args, **_kwargs: SESSION)

    def run(command):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(work.subprocess, "run", run)
    decision = work.Decision("floor", True, "resume", "current-head-floor-missing-or-red")
    assert work.execute_stage(state(pr=True), decision, tmp_path, None) == 0
    assert commands[0][-2:] == ["--resume", SESSION]


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
def test_power_user_commands_run_one_named_stage(command, tmp_path):
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

    assert work.run(args, transport=MinimalTransport(),
                    executor=lambda state, decision, root, instalment: captured.append(decision) or 0) == 0
    assert [(item.stage, item.reason) for item in captured] == [(command, "power-user-stage-command")]


def test_registry_write_is_atomic_shape_and_canonical(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    root = tmp_path / "tree"
    root.mkdir()
    work.register_worktree(root, "acme/widget", 3, "2", guard_status="unavailable")
    recorded = json.loads(work.registry_path().read_bytes())
    assert recorded == {"schema_version": 1, "worktrees": [{
        "root": str(root.resolve()), "repository": "acme/widget", "issue": 3,
        "instalment": "2", "active": True, "holder_write_guard": "unavailable",
        "revision_before": None, "status_before": None,
    }]}


def test_runtime_without_project_hook_records_enforcement_gap(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_ENTRYPOINT", raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    assert work.holder_guard_status() == "unavailable"

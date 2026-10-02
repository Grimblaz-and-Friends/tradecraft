from contextlib import nullcontext
from copy import deepcopy
import hashlib
from itertools import product
import json
from pathlib import Path
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import work
import launch_settings
import connected_review


# Synthetic entrance policy: these fixtures do not load a repository's rules.
RULES = {
    "schema_version": 1,
    "rules": [{
        "name": "fixture-runtime",
        "include": ["lib/**", "skills/**"],
        "exclude": ["**/tests/**", "**/test_*.py"],
    }],
}
SHA = "a" * 40
BASE_SHA = "c" * 40
GATE_PATH = "/".join((".github", "workflows", "self-change-proof.yml"))
GATE_SOURCE = {
    "repository_id": 2,
    "repository": "example/change-proof",
    "path": GATE_PATH,
    "ref": None,
    "sha": None,
    "rules": [{
        "ruleset_id": 31,
        "ruleset_source": "example",
        "ruleset_source_type": "Organization",
    }],
}
AFFIRMED = """<!-- tradecraft:affirmed-brief:v1 -->
Review risk: ordinary
Review lane: connected
"""
MECHANICAL = AFFIRMED.replace("connected", "mechanical")
ARTIFACT = "<!-- tradecraft:artifact:v1 status=draft -->"
WOULD = """<!-- tradecraft:artifact:v1 status=settled route=would -->
<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=qualified -->"""
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


WORK_CONFIG_BYTES = (
    b'{\n  "schema_version": 1,\n  "product_repositories": [],\n'
    b'  "connected_reviewers": [],\n  "marker_producers": []\n}\n'
)
USE_RULES_BYTES = (
    b'{\n  "schema_version": 1,\n  "rules": [\n    {\n      "name": "fixture",\n'
    b'      "include": ["lib/**"],\n      "exclude": []\n    }\n  ]\n}\n'
)
POLICY_PATH = "/".join((".github", "change-proof.json"))
RENAMED_POLICY_PATH = "/".join((".github", "renamed-rules.json"))


def write_policy(root, rules=RULES, relative=POLICY_PATH):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(rules).encode("utf-8"))
    return path


def policy_repository(tmp_path, name="policy-repository", *, autocrlf="false",
                      work_configuration=True, crlf=False):
    root = tmp_path / name
    root.mkdir()
    git(root, "init")
    git(root, "config", "core.autocrlf", autocrlf)
    (root / ".tradecraft").mkdir()
    (root / ".github").mkdir()
    def content(value):
        return value.replace(b"\n", b"\r\n") if crlf else value
    tracked = []
    if work_configuration:
        (root / ".tradecraft" / "work.json").write_bytes(content(WORK_CONFIG_BYTES))
        tracked.append(".tradecraft/work.json")
    (root / ".github" / "change-proof.json").write_bytes(content(USE_RULES_BYTES))
    tracked.append(POLICY_PATH)
    git(root, "add", *tracked)
    git(
        root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "policies",
    )
    for relative in tracked:
        path = root / relative
        path.unlink()
        git(root, "checkout", "--", relative)
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
                "head": {"sha": SHA},
                "base": {
                    "ref": "main", "sha": BASE_SHA,
                    "repo": {"id": 1, "full_name": "example/product"},
                }}
    fixture = work.WorkState(
        "example/product", 12,
        {"number": 12, "state": issue_state, "body": "", "labels": [],
         "user": {"login": PRODUCER}},
        issue_comments=comments, pr=pull, changed_paths=paths or ["lib/runtime.py"],
        config=config,
    )
    if pr:
        fixture.required_gate = {
            "status": "identified",
            "base": {
                "repository": "example/product", "repository_id": 1,
                "ref": "main", "sha": BASE_SHA,
            },
            "sources": [dict(GATE_SOURCE)],
            "reason": "base-branch rules identify every required workflow source",
        }
    if reviewer_ran:
        fixture.pr_comments = [{"body": "review summary", "user": {"login": REVIEWER}}]
    return fixture


def gate_check(*, identity=91, run_id=81, workflow_id=11, head=SHA,
               conclusion="success", status="completed", name="Change proof / Change proof",
               repository="example/change-proof", path=GATE_PATH):
    return {
        "id": identity, "name": name, "status": status,
        "conclusion": conclusion, "started_at": "2026-09-23T12:00:00Z",
        "details_url": f"https://github.com/example/product/actions/runs/{run_id}/job/{identity}",
        "workflow_run": {
            "workflow_id": workflow_id, "id": run_id, "head_sha": head,
            "check_suite_node_id": f"CS-{run_id}",
            "html_url": f"https://github.com/example/product/actions/runs/{run_id}",
        },
        "workflow_source": {
            "repository": repository, "path": path,
            "run_id": run_id, "workflow_id": workflow_id,
        },
    }


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
     ("proof", False, "fresh")),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
           "<!-- tradecraft:panel-stage:v1 stage=cold-pass status=complete -->",
           "<!-- tradecraft:panel-stage:v1 stage=defense status=complete -->",
           "<!-- tradecraft:panel-stage:v1 stage=floor-fixes status=complete -->",
           pr=True, draft=False, reviewer_ran=True), ("proof", False, "fresh")),
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
    assert "post-affirmation decision boundary" in decision.detail


@pytest.mark.parametrize("body", [
    "`<!-- tradecraft:affirmed-brief:v1 -->`",
    "``quoted\n<!-- tradecraft:affirmed-brief:v1 -->\nrecord``",
    "```md\n<!-- tradecraft:affirmed-brief:v1 -->\n```",
    "    <!-- tradecraft:affirmed-brief:v1 -->",
    "> <!-- tradecraft:affirmed-brief:v1 -->",
    "# copied record\n<!-- tradecraft:affirmed-brief:v1 -->",
    "The record said:\n<!-- tradecraft:affirmed-brief:v1 -->",
])
def test_quoted_and_nonopening_markers_are_reported_without_advancing(body):
    decision = work.decide(state(body), RULES)

    assert decision.stage == "convergence"
    assert decision.quotations == ({
        "name": "affirmed-brief",
        "source": {
            "kind": "issue-comment", "repository": "example/product",
            "id": None, "url": None,
            "author": PRODUCER, "timestamp": None,
        },
    },)
    assert "body" not in decision.quotations[0]


def test_first_nonblank_line_opens_an_ordinary_marker_claim():
    fixture = state("\n\n" + AFFIRMED)
    assert work.decide(fixture, RULES).stage == "artifact"
    assert fixture.quotation_claims == []


def test_inline_code_masking_reuses_one_candidate_with_forward_searches(monkeypatch):
    real_compile = work.re.compile
    searches = []

    class TrackingPattern:
        def __init__(self, pattern):
            self.pattern = pattern

        def search(self, text, position=0):
            searches.append((id(text), position, len(text)))
            return self.pattern.search(text, position)

    def tracking_compile(pattern, flags=0):
        return TrackingPattern(real_compile(pattern, flags))

    monkeypatch.setattr(work.re, "compile", tracking_compile)
    pieces = [f"`item-{index}`" for index in range(32)]
    body = " ".join(pieces)

    masked = work._mask_markdown_quotations(body)

    assert masked == " ".join(" " * len(piece) for piece in pieces)
    assert searches
    assert len({identity for identity, _position, _length in searches}) == 1
    assert [position for _identity, position, _length in searches] == sorted(
        position for _identity, position, _length in searches
    )
    assert {length for _identity, _position, length in searches} == {len(body)}


@pytest.mark.parametrize("body", ["plain text", "`unterminated", "``unterminated"])
def test_inline_code_masking_leaves_non_code_text_unchanged(body):
    assert work._mask_markdown_quotations(body) == body


def test_travels_with_contract_accepts_only_listed_companions():
    fixture = state(
        AFFIRMED + "\n<!-- tradecraft:product-incident:v1 repo=acme/app issue=3 -->",
        ARTIFACT + "\n<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=qualified -->",
        WOULD,
        (
            f"<!-- tradecraft:proof:v1 head={SHA} -->\n"
            f"<!-- tradecraft:no-use:v1 head={SHA} -->\nUse: not required - fixture."
        ),
        (
            "<!-- tradecraft:implementing-pr:v1 number=7 -->\n"
            f"<!-- tradecraft:builder-session:v1 session={SESSION} -->"
        ),
    )
    fixture.pr_comments = [fixture.issue_comments.pop(3)]
    lawful, _invalid = work.validate_marker_claims(fixture)

    names = [marker.name for marker in lawful]
    assert names.count("cold-verdict") == 1
    assert {"proof", "no-use", "implementing-pr", "builder-session"} <= set(names)
    quotations = {(item["name"], item["source"]["kind"])
                  for item in fixture.quotation_claims}
    assert ("product-incident", "issue-comment") in quotations
    assert ("cold-verdict", "issue-comment") in quotations


def test_implementing_pr_marker_after_prose_does_not_select_a_candidate():
    comments = [{
        "body": "Copied from the handoff:\n<!-- tradecraft:implementing-pr:v1 number=7 -->",
        "user": {"login": PRODUCER},
    }]
    pulls = [{"number": 7, "state": "open", "merged_at": None, "body": ""}]
    issue = {"number": 12, "state": "open", "body": "", "user": {"login": PRODUCER}}

    assert work._candidate_prs(12, issue, comments, pulls, CONFIG) == set()


def test_665_regression_keeps_mid_source_product_markers_as_quotations():
    config = work.WorkConfig(
        product_repositories=frozenset({"organizations-of-verra/product"}),
        marker_producers=frozenset({PRODUCER}),
    )
    fixture = state(config=config)
    fixture.issue["number"] = 665
    fixture.issue["body"] = (
        "Practice defect found while working elsewhere.\n"
        "<!-- tradecraft:product-incident:v1 "
        "repo=organizations-of-verra/product issue=44 -->"
    )
    fixture.issue_comments = [{
        "id": 2,
        "body": "> <!-- tradecraft:product-incident:v1 "
                "repo=organizations-of-verra/product issue=44 -->",
        "user": {"login": PRODUCER},
    }]

    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.reason) == (
        "product-incident-required", "practice-work-has-no-product-incident",
    )
    assert [item["name"] for item in decision.quotations] == [
        "product-incident", "product-incident",
    ]


def test_pull_request_body_uses_the_same_source_classifier():
    fixture = state(AFFIRMED, pr=True)
    fixture.pr.update({
        "id": 70, "body": "Quoted record:\n<!-- tradecraft:floor:v1 "
                         f"head={SHA} status=pass -->",
        "user": {"login": PRODUCER},
    })
    decision = work.decide(fixture, RULES)
    assert decision.stage == "artifact"
    assert any(item["name"] == "floor" and item["source"]["kind"] == "pull-request"
               for item in decision.quotations)


def _settled(route, verdict=None):
    body = f"<!-- tradecraft:artifact:v1 status=settled route={route} -->"
    if verdict is not None:
        body += (
            "\n<!-- tradecraft:cold-verdict:v1 "
            f"verdict={verdict} staffing_status=qualified -->"
        )
    return body


@pytest.mark.parametrize(("comments", "route"), [
    ((ARTIFACT, _settled("would", "would")), "would"),
    ((ARTIFACT, WOULD_NOT, ARTIFACT, WOULD_NOT, _settled("cap")), "cap"),
    ((ARTIFACT, _settled("discharge", "not-settleable")), "discharge"),
    ((ARTIFACT, _settled("unobtainable")), "unobtainable"),
])
def test_each_supported_settlement_route_closes_the_phase(comments, route):
    fixture = state(AFFIRMED, *comments, HOLDER)
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.reason) == ("build", "pull-request-absent")
    artifact = next(marker for marker in decision.lawful_markers
                    if marker["name"] == "artifact"
                    and marker["attributes"].get("route") == route)
    assert artifact["attributes"]["route"] == route


@pytest.mark.parametrize(("comments", "route"), [
    ((ARTIFACT, _settled("would")), "would"),
    ((ARTIFACT, WOULD_NOT, _settled("cap")), "cap"),
    ((ARTIFACT, _settled("discharge", "would")), "discharge"),
    ((ARTIFACT, _settled("unobtainable", "would")), "unobtainable"),
])
def test_each_unsupported_settlement_route_is_invalid_and_does_not_close(comments, route):
    decision = work.decide(state(AFFIRMED, *comments, HOLDER), RULES)
    assert decision.stage != "build"
    reasons = [item["reason"] for item in decision.invalid_markers
               if item["name"] == "artifact"]
    assert any(f"route={route}" in reason for reason in reasons)


def test_routeless_settlement_requests_one_supported_route_repost():
    routeless = (
        "<!-- tradecraft:artifact:v1 status=settled -->\n"
        "<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=qualified -->"
    )
    fixture = state(AFFIRMED, ARTIFACT, routeless)
    lawful, invalid = work.validate_marker_claims(fixture)
    assert not any(marker.name == "artifact" and marker.attributes.get("status") == "settled"
                   for marker in lawful)
    assert any("route is missing" in item["reason"] for item in invalid)

    decision = work.decide(fixture, RULES)
    assert decision.stage == "artifact-settlement"
    reason = next(item["reason"] for item in decision.invalid_markers
                  if item["name"] == "artifact")
    assert "re-post it once" in reason
    assert all(f"route={route}" in reason for route in work.SETTLEMENT_ROUTES)


def test_superseded_routeless_settlement_reports_history_without_repost_guidance():
    routeless = (
        "<!-- tradecraft:artifact:v1 status=settled -->\n"
        "<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=qualified -->"
    )
    decision = work.decide(
        state(AFFIRMED, ARTIFACT, routeless, AFFIRMED), RULES,
    )

    assert (decision.stage, decision.reason) == ("artifact", "artifact-marker-absent")
    reason = next(item["reason"] for item in decision.invalid_markers
                  if item["name"] == "artifact")
    assert "superseded by a later affirmed brief" in reason
    assert "no re-post is needed" in reason
    assert "re-post it once" not in reason


def test_newer_draft_reopens_a_settlement_and_a_later_settlement_closes_it():
    reopened = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, ARTIFACT)
    assert work.decide(reopened, RULES).stage == "cold-seat"

    reopened.issue_comments.extend([
        {"body": WOULD, "user": {"login": PRODUCER}},
        {"body": HOLDER, "user": {"login": PRODUCER}},
    ])
    assert work.decide(reopened, RULES).stage == "build"


def test_new_affirmed_brief_starts_a_new_artifact_term():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, AFFIRMED)
    assert work.decide(fixture, RULES).stage == "artifact"


@pytest.mark.parametrize("route", sorted(work.SETTLEMENT_ROUTES))
def test_settlement_without_a_current_term_draft_is_invalid_for_every_route(route):
    decision = work.decide(state(AFFIRMED, _settled(route), HOLDER), RULES)

    assert (decision.stage, decision.reason) == ("artifact", "artifact-marker-absent")
    reasons = [item["reason"] for item in decision.invalid_markers
               if item["name"] == "artifact"]
    assert reasons == ["artifact settlement requires an artifact draft in the current term"]


def test_unobtainable_settlement_with_a_current_term_draft_closes_the_phase():
    decision = work.decide(
        state(AFFIRMED, ARTIFACT, _settled("unobtainable"), HOLDER), RULES,
    )
    assert (decision.stage, decision.reason) == ("build", "pull-request-absent")


def test_stale_would_verdict_cannot_support_a_newer_draft():
    cold_would = "<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=qualified -->"
    fixture = state(
        AFFIRMED, ARTIFACT, cold_would, ARTIFACT, _settled("would"), HOLDER,
    )
    decision = work.decide(fixture, RULES)
    assert decision.stage == "cold-seat"
    assert any("route=would" in item["reason"] for item in decision.invalid_markers)


def test_would_not_verdicts_across_drafts_support_the_cap_route():
    fixture = state(
        AFFIRMED, ARTIFACT, WOULD_NOT, ARTIFACT, WOULD_NOT,
        _settled("cap"), HOLDER,
    )
    assert work.decide(fixture, RULES).stage == "build"


def test_holder_reading_before_the_latest_settlement_is_stale():
    fixture = state(AFFIRMED, ARTIFACT, HOLDER, _settled("unobtainable"))
    assert work.decide(fixture, RULES).stage == "holder-read"


def test_routed_repost_inherits_routeless_order_across_a_holder_reading():
    routeless = (
        "<!-- tradecraft:artifact:v1 status=settled -->\n"
        "<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=qualified -->"
    )
    fixture = state(
        AFFIRMED, ARTIFACT, routeless, HOLDER, _settled("would"),
    )
    decision = work.decide(fixture, RULES)

    assert decision.stage == "build"
    assert any("route is missing" in item["reason"] for item in decision.invalid_markers)
    routed = [item for item in decision.lawful_markers
              if item["name"] == "artifact" and item["attributes"].get("route") == "would"]
    assert len(routed) == 1


def test_routeless_migration_position_is_spent_after_one_routed_settlement():
    routeless = (
        "<!-- tradecraft:artifact:v1 status=settled -->\n"
        "<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=qualified -->"
    )
    fixture = state(
        AFFIRMED, ARTIFACT, routeless, HOLDER,
        _settled("would"), _settled("would"),
    )

    assert work.decide(fixture, RULES).stage == "holder-read"


@pytest.mark.parametrize("breaker", ["draft", "verdict", "brief"])
def test_term_changing_claim_breaks_routeless_order_inheritance(breaker):
    routeless = (
        "<!-- tradecraft:artifact:v1 status=settled -->\n"
        "<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=qualified -->"
    )
    cold_would = "<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=qualified -->"
    comments = [AFFIRMED, ARTIFACT, routeless, HOLDER]
    if breaker == "draft":
        comments.extend((ARTIFACT, cold_would))
    elif breaker == "verdict":
        comments.append(cold_would)
    else:
        comments.extend((AFFIRMED, ARTIFACT, cold_would))
    comments.append(_settled("would"))

    assert work.decide(state(*comments), RULES).stage == "holder-read"


def test_build_prompt_uses_only_the_latest_terms_settled_artifact():
    first = _settled("would", "would") + "\nFIRST TERM"
    second = _settled("would", "would") + "\nSECOND TERM"
    fixture = state(
        AFFIRMED, ARTIFACT, first, HOLDER,
        AFFIRMED, ARTIFACT, second, HOLDER,
    )
    prompt = work._stage_prompt(
        fixture, work.Decision("build", True, "fresh", "fixture")
    )
    assert b"SECOND TERM" in prompt
    assert b"FIRST TERM" not in prompt


ARTIFACT_PROMPT_TERM_KINDS = ("draft", "routeless", "reading", "empty")
ARTIFACT_PROMPT_TERM_SEQUENCES = tuple(
    sequence
    for length in range(1, 4)
    for sequence in product(ARTIFACT_PROMPT_TERM_KINDS, repeat=length)
)


def _artifact_prompt_term(kind, index):
    draft_token = f"TERM {index} DRAFT"
    draft = ARTIFACT + f"\n{draft_token}"
    if kind == "empty":
        return [], None, None, []
    if kind == "draft":
        return [draft], draft_token.encode("ascii"), None, []
    settlement_token = f"TERM {index} SETTLEMENT"
    if kind == "routeless":
        settlement = (
            "<!-- tradecraft:artifact:v1 status=settled -->\n"
            + settlement_token
        )
        return [draft, settlement], settlement_token.encode("ascii"), None, []
    earlier_reading_token = f"TERM {index} EARLIER HOLDER READING"
    reading_token = f"TERM {index} HOLDER READING"
    settlement = _settled("would", "would") + f"\n{settlement_token}"
    earlier_reading = HOLDER + f"\n{earlier_reading_token}"
    reading = HOLDER + f"\n{reading_token}"
    return (
        [draft, settlement, earlier_reading, reading],
        settlement_token.encode("ascii"),
        reading_token.encode("ascii"),
        [earlier_reading_token.encode("ascii"), reading_token.encode("ascii")],
    )


@pytest.mark.parametrize(
    ("term_sequence", "current_has_draft"),
    [
        pytest.param(
            sequence, current_has_draft,
            id=(
                f"{'-'.join(sequence)}-current-"
                f"{'draft' if current_has_draft else 'empty'}"
            ),
        )
        for sequence in ARTIFACT_PROMPT_TERM_SEQUENCES
        for current_has_draft in (False, True)
    ],
)
def test_artifact_prompt_selects_latest_prior_term_pair(
        term_sequence, current_has_draft):
    comments = []
    artifact_tokens = []
    reading_tokens = []
    expected_artifact = None
    expected_reading = None
    for index, kind in enumerate(term_sequence, start=1):
        comments.append(AFFIRMED)
        term_comments, artifact_token, reading_token, term_reading_tokens = (
            _artifact_prompt_term(kind, index)
        )
        comments.extend(term_comments)
        if artifact_token is not None:
            artifact_tokens.append(artifact_token)
            expected_artifact = artifact_token
            expected_reading = reading_token
        reading_tokens.extend(term_reading_tokens)

    comments.append(AFFIRMED)
    current_token = b"CURRENT TERM DRAFT"
    if current_has_draft:
        comments.append(ARTIFACT + "\n" + current_token.decode("ascii"))
        artifact_tokens.append(current_token)
        expected_artifact = current_token
        expected_reading = None

    fixture = state(*comments)
    recommendation = work.decide(fixture, RULES)
    if current_has_draft:
        assert recommendation.stage == "cold-seat"
        decision = work.Decision("artifact", True, "resume", "holder-named-stage")
    else:
        assert (recommendation.stage, recommendation.reason) == (
            "artifact", "artifact-marker-absent",
        )
        decision = recommendation
    prompt = work._stage_prompt(fixture, decision)

    assert (b"--- artifact under revision begin ---" in prompt) == (
        expected_artifact is not None
    )
    assert b"--- settled artifact begin ---" not in prompt
    for token in artifact_tokens:
        assert (token in prompt) == (token == expected_artifact)
    reading_label = b"holder reading made against artifact under revision"
    assert (reading_label in prompt) == (expected_reading is not None)
    for token in reading_tokens:
        assert (token in prompt) == (token == expected_reading)
    if expected_reading is not None:
        assert prompt.index(reading_label) > prompt.index(
            b"--- artifact under revision end ---"
        )


def test_artifact_prompt_preserves_746_shape_across_four_empty_brief_records():
    settlement_token = b"746 SETTLED ARTIFACT"
    reading_token = b"746 HOLDER READING"
    fixture = state(
        AFFIRMED,
        ARTIFACT + "\n746 DRAFT",
        "<!-- tradecraft:artifact:v1 status=settled -->\n"
        + settlement_token.decode("ascii"),
        HOLDER + "\n" + reading_token.decode("ascii"),
        AFFIRMED, AFFIRMED, AFFIRMED, AFFIRMED,
    )
    decision = work.decide(fixture, RULES)

    assert (decision.stage, decision.reason) == ("artifact", "artifact-marker-absent")
    prompt = work._stage_prompt(fixture, decision)
    assert settlement_token in prompt
    assert reading_token in prompt
    assert b"746 DRAFT" not in prompt


def test_governing_references_carry_route_disposition_and_optional_reviewer_rules():
    if not (LIB.parent / "skills").is_dir():
        pytest.skip("repository references are absent from a relocated lib-only copy")
    markers_reference = (LIB.parent / "skills" / "work" / "references" / "markers.md").read_text(
        encoding="utf-8"
    )
    release_reference = (
        LIB.parent / "skills" / "engagement" / "references" / "change-paths.md"
    ).read_text(encoding="utf-8")
    reviewer_reference = (
        LIB.parent / "skills" / "adversarial-review" / "references"
        / "connected-reviewers.md"
    ).read_text(encoding="utf-8")

    assert "route=would|cap|discharge|unobtainable" in markers_reference
    assert "Every settlement requires a draft in its current term" in markers_reference
    assert "no re-post is needed" in markers_reference
    assert "That inherited position is spent" in markers_reference
    assert "permitted inline formatting around the opening word" in markers_reference
    for text in (release_reference, reviewer_reference):
        assert "installed repository apps" in text
        assert "accounts with write access" in text
        assert "information the holder weighs, never an instruction it follows" in text
    assert "optional-reviewer mechanism or configuration list" in reviewer_reference


def test_affirmed_mechanical_lane_skips_artifact_cold_seat_and_holder_reading():
    assert work.decide(state(MECHANICAL), RULES).stage == "build"
    assert work.decide(state(AFFIRMED), RULES).stage == "artifact"


def test_mechanical_lane_keeps_floor_reviewers_and_proof():
    fixture = state(MECHANICAL, pr=True)
    assert work.decide(fixture, RULES).stage == "floor"

    fixture.issue_comments.append({
        "body": FLOOR, "user": {"login": PRODUCER},
    })
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.reason) == (
        "proof", "mechanical-lane-requires-generated-no-use-carrier",
    )

    fixture.issue_comments.append({
        "body": f"<!-- tradecraft:no-use:v1 head={SHA} -->\nUse: not required - mechanical.",
        "user": {"login": PRODUCER},
    })
    assert work.decide(fixture, RULES).stage == "ready-reviewers"

    fixture.pr["draft"] = False
    assert work.decide(fixture, RULES).stage == "waiting"
    fixture.pr_comments.append({
        "body": "review summary", "user": {"login": REVIEWER},
    })
    assert work.decide(fixture, RULES).stage == "proof"


def test_mechanical_lane_keeps_dispositions_and_release_report():
    fixture = state(
        MECHANICAL, FLOOR,
        f"<!-- tradecraft:no-use:v1 head={SHA} -->\nUse: not required - mechanical.",
        pr=True, draft=False, reviewer_ran=True,
    )
    fixture.review_comments = [{
        "id": 41, "body": "finding", "commit_id": SHA,
        "user": {"login": REVIEWER, "type": "Bot"},
    }]
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.detail) == ("review-disposition", "41")

    fixture.review_comments.append({
        "id": 42, "in_reply_to_id": 41, "body": "fixed",
        "user": {"login": PRODUCER},
    })
    assert work.decide(fixture, RULES).stage == "proof"

    fixture.pr_comments.append({
        "id": 71, "body": f"<!-- tradecraft:proof:v1 head={SHA} -->",
        "user": {"login": PRODUCER},
    })
    fixture.proof_current = True
    fixture.checks = [gate_check()]
    assert work.decide(fixture, RULES).stage == "release-report"


def test_mechanical_no_use_is_head_specific_and_does_not_buy_a_panel():
    old_head = "b" * 40
    fixture = state(
        MECHANICAL, FLOOR,
        f"<!-- tradecraft:no-use:v1 head={old_head} -->\nUse: not required - mechanical.",
        pr=True,
    )
    assert work.decide(fixture, RULES).reason == (
        "mechanical-lane-requires-generated-no-use-carrier"
    )

    fixture.issue_comments[-1]["body"] = (
        f"<!-- tradecraft:no-use:v1 head={SHA} -->\nUse: not required - mechanical."
    )
    fixture.pr["draft"] = False
    fixture.pr_comments.extend((
        {"body": "review summary", "user": {"login": REVIEWER}},
        {"body": f"<!-- tradecraft:proof:v1 head={SHA} -->",
         "user": {"login": PRODUCER}},
    ))
    fixture.proof_current = True
    fixture.checks = [gate_check(conclusion="failure")]

    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.reason) == (
        "waiting", "latest-gate-evaluation-failed",
    )


def test_unauthorized_or_crossed_mechanical_claim_cannot_grant_the_exemption():
    unauthorized = state(AFFIRMED)
    unauthorized.issue_comments.append({
        "body": MECHANICAL, "user": {"login": "unlisted-commenter"},
    })
    assert work.decide(unauthorized, RULES).stage == "artifact"

    crossed = MECHANICAL.replace("ordinary", "elevated")
    assert work.decide(state(crossed), RULES).stage == "affirmation-invalid"


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


def test_same_name_checks_from_different_workflows_remain_separate():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE, pr=True)
    fixture.checks = [
        {"id": 1, "name": "Tests", "started_at": "2026-09-23T10:00:00Z",
         "status": "completed", "conclusion": "success",
         "workflow_run": {"workflow_id": 10}},
        {"id": 2, "name": "Tests", "started_at": "2026-09-23T10:01:00Z",
         "status": "completed", "conclusion": "failure",
         "workflow_run": {"workflow_id": 20}},
        {"id": 3, "name": "Tests", "started_at": "2026-09-23T10:02:00Z",
         "status": "completed", "conclusion": "success",
         "workflow_run": {"workflow_id": 10}},
    ]

    selected = work.latest_checks(fixture)
    assert [item["id"] for item in selected] == [3, 2]
    assert work._checks_red(fixture) is True


def test_same_name_action_runs_without_workflow_metadata_remain_separate():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE, pr=True)
    fixture.checks = [
        {"id": 1, "name": "Tests", "started_at": "2026-09-23T10:00:00Z",
         "status": "completed", "conclusion": "failure",
         "details_url": "https://github.com/x/actions/runs/81/job/1", "app": {"id": 1}},
        {"id": 2, "name": "Tests", "started_at": "2026-09-23T10:01:00Z",
         "status": "completed", "conclusion": "success",
         "details_url": "https://github.com/x/actions/runs/82/job/2", "app": {"id": 1}},
    ]

    selected = work.latest_checks(fixture)
    assert [item["id"] for item in selected] == [1, 2]
    assert work._checks_red(fixture) is True


def test_latest_run_groups_by_runtime_workflow_id_even_with_one_source_file():
    fixture = state(pr=True)
    older = gate_check(identity=1, run_id=81, workflow_id=10, conclusion="failure")
    older["started_at"] = "2026-09-23T10:00:00Z"
    newer = gate_check(identity=2, run_id=82, workflow_id=20, conclusion="success")
    newer["started_at"] = "2026-09-23T11:00:00Z"
    fixture.checks = [newer, older]
    assert [item["id"] for item in work.latest_checks(fixture)] == [1, 2]
    assert work._release_gate_status(fixture)["verdict"] == "red"


def test_gate_rerun_uses_current_head_run_and_workflow_identity():
    fixture = state(AFFIRMED, pr=True)
    fixture.checks = [gate_check(workflow_id=71, conclusion="failure")]

    class GateTransport:
        def __init__(self):
            self.posts = []

        def post(self, endpoint, payload):
            self.posts.append((endpoint, payload))
            return {}

        def get(self, endpoint, *, paginate=False):
            return {"id": 81, "status": "queued", "conclusion": None}

    transport = GateTransport()
    reruns = work._rerun_gate_evaluations(transport, fixture, SHA)
    assert transport.posts == [("repos/example/product/actions/runs/81/rerun", {})]
    assert reruns[0] == {
        "source": GATE_SOURCE,
        "check_id": 91, "run_id": 81, "workflow_id": 71,
        "requested": True, "status": "queued", "conclusion": None,
        "reason": "rerun requested for the identified current-head workflow run",
    }


def test_builder_return_without_pull_request_is_a_holder_owned_handoff():
    fixture = state(
        AFFIRMED, ARTIFACT, WOULD, HOLDER,
        f"<!-- tradecraft:builder-session:v1 session={SESSION} -->",
    )
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.dispatch, decision.status) == (
        "open-pull-request", False, "holder-owned",
    )


def body_review_state(*, proof=False, declaration=None):
    cr_login = "coderabbitai[bot]"
    config = work.WorkConfig(connected_reviewers=frozenset({cr_login}),
                             marker_producers=frozenset({PRODUCER}))
    texts = [AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE]
    fixture = state(*texts, pr=True, draft=False, config=config)
    fixture.reviews = [{
        "id": 100, "state": "COMMENTED", "commit_id": "b" * 40,
        "user": {"login": cr_login},
        "body": declaration or "<!-- cr-comment:v1:alpha -->",
        "html_url": "https://github.com/example/product/pull/7#pullrequestreview-100",
    }, {
        "id": 101, "state": "COMMENTED", "commit_id": SHA,
        "user": {"login": cr_login}, "body": "No findings.",
    }]
    fixture.checks = [gate_check()]
    if proof:
        fixture.pr_comments.append({"id": 71, "user": {"login": PRODUCER},
                                   "body": f"<!-- tradecraft:proof:v1 head={SHA} -->"})
        fixture.proof_current = True
    fixture.policy_sources = {
        key: {"repository": fixture.repo, "path": path, "revision": SHA, "sha256": "1" * 64}
        for key, path in (("work_configuration", ".tradecraft/work.json"),
                          ("use_rules", POLICY_PATH))
    }
    return fixture


@pytest.mark.parametrize("proof", [False, True])
def test_prior_head_body_obligation_precedes_proof_and_legacy_green_gate(proof):
    fixture = body_review_state(proof=proof)
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.dispatch, decision.continuity) == (
        "review-disposition", True, "resume",
    )
    assert "cr-comment:v1:alpha" in decision.detail
    assert fixture.reviews[0]["html_url"] in decision.detail
    fixture.pr_comments.append({"user": {"login": PRODUCER}, "body":
        "declined - this input is already checked; [cr-comment:v1:alpha]"
        "(https://github.com/example/product/pull/7#pullrequestreview-100)"})
    assert work.decide(fixture, RULES).stage == ("release-report" if proof else "proof")


def test_unidentified_review_is_named_and_authorized_whole_answer_resolves_it():
    fixture = body_review_state(declaration="**Actionable comments posted: 1**")
    decision = work.decide(fixture, RULES)
    assert decision.stage == "review-disposition"
    assert "unidentified" in decision.detail and fixture.reviews[0]["html_url"] in decision.detail
    fixture.pr_comments.append({"user": {"login": "outsider"}, "body":
        "fixed - repaired; [unidentified review]"
        "(https://github.com/example/product/pull/7#pullrequestreview-100)"})
    assert "ignored-disposition-from=outsider" in work.decide(fixture, RULES).reason
    fixture.pr_comments[-1]["user"]["login"] = PRODUCER
    assert work.decide(fixture, RULES).stage == "proof"
    assert work._body_findings(fixture).unidentified_reviews[0].answered


def test_body_diagnostics_use_unchanged_proof_contract_before_and_after_answer(tmp_path):
    fixture = body_review_state(declaration=
        "<details><summary>Other comments (2)</summary>\n"
        "<!-- cr-comment:v1:alpha -->\n</details>")
    fixture.record_root = tmp_path / "missing-dispatches"
    first = work.compose_proof(fixture, RULES)
    assert set(first) == {
        "schema_version", "identity", "policy", "floor", "use", "reviewers",
        "dispositions", "declarations", "diagnostics",
    }
    assert first["dispositions"] == []
    assert {item["code"] for item in first["diagnostics"]} >= {
        "body-disposition-missing", "unidentified-review-disposition-missing",
    }
    for label in ("cr-comment:v1:alpha", "unidentified review"):
        fixture.pr_comments.append({"id": 200, "user": {"login": PRODUCER}, "body":
            f"fixed - repaired; [{label}]"
            "(https://github.com/example/product/pull/7#pullrequestreview-100)"})
    after = work.compose_proof(fixture, RULES)
    assert not ({"body-disposition-missing", "unidentified-review-disposition-missing"}
                & {item["code"] for item in after["diagnostics"]})
    assert after["dispositions"] == first["dispositions"]
    assert set(after) == set(first)
    import proof as proof_document
    proof_document.validate(first)
    proof_document.validate(after)


def test_body_identity_does_not_credit_an_unproved_actions_review():
    fixture = body_review_state()
    fixture.config = ACTIONS_CONFIG
    fixture.reviews = [{"id": 100, "state": "COMMENTED", "commit_id": SHA,
        "user": {"login": work.ACTIONS_REVIEWER}, "body":
        "1 validated finding(s).\n<!-- tradecraft-review-finding:v1:91:1 -->"}]
    assert not work._reviewer_ran(fixture)
    assert work.decide(fixture, RULES).stage == "waiting"
    assert work._body_findings(fixture).missing_findings


def test_body_answers_create_no_ready_time_circular_prerequisite():
    fixture = body_review_state()
    fixture.pr["draft"] = True
    assert work.decide(fixture, RULES).stage == "ready-reviewers"


def test_explicit_release_handoff_names_unanswered_bodies_despite_green_gate(tmp_path, capsys):
    fixture = body_review_state(proof=True)
    assert work.execute_stage(fixture, work.Decision(
        "release-report", False, None, "holder-named-stage"), tmp_path, None) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["required_gate"]["verdict"] == "green"
    assert not report["review_dispositions"]["complete"]
    assert "cr-comment:v1:alpha" in report["detail"]
    assert "does not establish release readiness" in report["detail"]


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
    assert work.decide(fixture, RULES).stage == "proof"


@pytest.mark.parametrize("wrapper", ["", "*", "**", "_", "__", "`"])
@pytest.mark.parametrize("body", [
    "fixed",
    "fixed - nothing else found it",
    "fixed in #12",
    "yours - in the release report",
    "declined - outside the brief",
    "duplicate of 41",
    "lapsed - retired rule",
])
def test_every_disposition_accepts_formatting_around_its_opening_word(wrapper, body):
    word, separator, rest = body.partition(" ")
    formatted = f"{wrapper}{word}{wrapper}{separator}{rest}"
    assert work._disposition(formatted)


@pytest.mark.parametrize("body", [
    "**considered** - no action",
    "`reviewed`",
    "_notfixed_ - later",
])
def test_formatting_does_not_make_a_non_disposition_lawful(body):
    assert not work._disposition(body)


def test_disposition_reply_carries_connected_reviewer_marker_in_plain_and_formatted_forms():
    marker = "<!-- tradecraft:connected-reviewer:v1 name=fixture status=complete -->"
    fixture = state()
    fixture.review_comments = [
        {"id": 41, "body": "finding", "user": {"login": REVIEWER}},
        {"id": 42, "in_reply_to_id": 41, "body": f"**Fixed** - done\n{marker}",
         "user": {"login": PRODUCER}},
    ]
    lawful, _invalid = work.validate_marker_claims(fixture)
    assert [item.name for item in lawful] == ["connected-reviewer"]
    assert fixture.quotation_claims == []

    fixture.review_comments[1]["body"] = f"Considered - no action\n{marker}"
    lawful, _invalid = work.validate_marker_claims(fixture)
    assert lawful == []
    assert [item["name"] for item in fixture.quotation_claims] == ["connected-reviewer"]


def test_connected_reviewer_marker_in_an_ordinary_comment_or_quoted_region_does_not_count():
    marker = "<!-- tradecraft:connected-reviewer:v1 name=fixture status=complete -->"
    fixture = state()
    fixture.pr_comments = [{
        "id": 51, "body": f"Fixed - ordinary comment\n{marker}",
        "user": {"login": PRODUCER},
    }]
    fixture.review_comments = [
        {"id": 41, "body": "finding", "user": {"login": REVIEWER}},
        {"id": 42, "in_reply_to_id": 41,
         "body": f"Fixed - done\n`{marker}`", "user": {"login": PRODUCER}},
    ]
    lawful, _invalid = work.validate_marker_claims(fixture)
    assert lawful == []
    assert [item["name"] for item in fixture.quotation_claims] == [
        "connected-reviewer", "connected-reviewer",
    ]


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
    assert work.decide(fixture, RULES).stage == "proof"


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
    assert work.decide(fixture, RULES).stage == "proof"


def test_empty_reviewer_list_requires_no_review_and_says_so():
    config = work.WorkConfig(marker_producers=frozenset({PRODUCER}))
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False, config=config)
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.reason) == (
        "proof", "current-head-proof-absent-or-outdated",
    )


def test_completed_proof_and_successful_gate_reach_release_report():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False, reviewer_ran=True)
    fixture.pr_comments.append({
        "id": 71, "body": f"<!-- tradecraft:proof:v1 head={SHA} -->",
        "user": {"login": PRODUCER},
    })
    fixture.proof_current = True
    fixture.checks = [gate_check()]

    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.reason) == ("release-report", "all-evidence-complete")


@pytest.mark.parametrize(
    ("expected", "run_head", "conclusion", "restate"),
    [
        ("green", SHA, "success", False),
        ("red", SHA, "failure", True),
        ("stale", "b" * 40, "success", True),
        ("absent", None, None, True),
    ],
)
def test_release_report_names_gate_verdict_run_and_path_departure_action(
        expected, run_head, conclusion, restate, tmp_path, capsys):
    fixture = state(pr=True)
    if run_head is not None:
        fixture.checks = [gate_check(head=run_head, conclusion=conclusion)]

    class ReleaseTransport:
        def get(self, endpoint, *, paginate=False):
            assert endpoint == "repos/example/product/pulls/7"
            assert paginate is False
            return fixture.pr

    decision = work.Decision("release-report", False, None, "holder-named-stage")
    assert work.execute_stage(
        fixture, decision, tmp_path, None, transport=ReleaseTransport()
    ) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["required_gate"]["verdict"] == expected
    assert report["required_gate"]["head"] == SHA
    runs = report["required_gate"]["runs"]
    assert len(runs) == (0 if expected == "absent" else 1)
    if runs:
        assert runs[0]["run_id"] == 81
        assert runs[0]["head"] == run_head
    assert report["path_departures"]["restate"] is restate
    instruction = report["path_departures"]["instruction"]
    if restate:
        assert "Restate the **Path departures:** paragraph" in instruction
        assert SHA in instruction
        assert "merging remains the owner's decision" in instruction
    else:
        assert "no gate-bypass restatement is required" in instruction


@pytest.mark.parametrize(("requirement", "verdict", "restate", "phrase"), [
    (
        {"status": "none", "base": {}, "sources": [], "reason": "no required gate"},
        "none", False, "No required gate",
    ),
    (
        {"status": "unidentified", "base": {}, "sources": [],
         "reason": "rules returned 403"},
        "unidentified", True, "Do not claim that a particular required gate was bypassed",
    ),
])
def test_release_report_distinguishes_no_gate_from_unreadable_rules(
        requirement, verdict, restate, phrase, tmp_path, capsys):
    fixture = state(pr=True)
    fixture.required_gate = requirement

    class ReleaseTransport:
        def get(self, endpoint, *, paginate=False):
            return fixture.pr

    assert work.execute_stage(
        fixture, work.Decision("release-report", False, None, "holder-named-stage"),
        tmp_path, None, transport=ReleaseTransport(),
    ) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["required_gate"]["verdict"] == verdict
    assert report["path_departures"]["restate"] is restate
    assert phrase in report["path_departures"]["instruction"]


def test_release_report_refuses_when_base_moves_after_collection(tmp_path):
    fixture = state(pr=True)
    moved = json.loads(json.dumps(fixture.pr))
    moved["base"]["ref"] = "release/other"

    class ReleaseTransport:
        def get(self, endpoint, *, paginate=False):
            return moved

    with pytest.raises(work.WorkError, match="head or base changed"):
        work.execute_stage(
            fixture, work.Decision("release-report", False, None, "holder-named-stage"),
            tmp_path, None, transport=ReleaseTransport(),
        )


def test_pull_coordinates_ignore_an_advancing_base_revision():
    fixture = state(pr=True)
    moved = json.loads(json.dumps(fixture.pr))
    moved["base"]["sha"] = "d" * 40

    assert work._pull_coordinates(moved) == work._pull_coordinates(fixture.pr)


def test_failed_gate_waits_and_does_not_route_back_to_floor():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False, reviewer_ran=True)
    fixture.pr_comments.append({
        "id": 71, "body": f"<!-- tradecraft:proof:v1 head={SHA} -->",
        "user": {"login": PRODUCER},
    })
    fixture.proof_current = True
    fixture.checks = [gate_check(conclusion="failure")]

    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.reason) == ("waiting", "latest-gate-evaluation-failed")


@pytest.mark.parametrize(("gate_conclusion", "copy_conclusion", "stage", "gate_verdict"), [
    ("success", "failure", "floor", "green"),
    ("failure", "success", "waiting", "red"),
])
def test_same_named_local_copy_stays_ordinary(
        gate_conclusion, copy_conclusion, stage, gate_verdict):
    fixture = proof_ready_fixture_without_gate()
    fixture.checks = [
        gate_check(conclusion=gate_conclusion, name="same / name"),
        gate_check(
            identity=92, run_id=82, workflow_id=12, conclusion=copy_conclusion,
            name="same / name", repository="example/product",
        ),
    ]
    decision = work.decide(fixture, RULES)
    assert decision.stage == stage
    assert work._release_gate_status(fixture)["verdict"] == gate_verdict


@pytest.mark.parametrize(("conclusion", "reason"), [
    (None, "latest-gate-evaluation-pending"),
    ("neutral", "latest-gate-evaluation-failed"),
    ("skipped", "latest-gate-evaluation-failed"),
])
def test_gate_requires_an_explicit_success_before_release(conclusion, reason):
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False, reviewer_ran=True)
    fixture.pr_comments.append({
        "id": 71, "body": f"<!-- tradecraft:proof:v1 head={SHA} -->",
        "user": {"login": PRODUCER},
    })
    fixture.proof_current = True
    fixture.checks = [gate_check(conclusion=conclusion)]

    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.reason) == ("waiting", reason)
    if conclusion is None:
        assert decision.detail == "an identified current-head gate evaluation is pending."


@pytest.mark.parametrize(("status", "conclusion"), [
    ("completed", "failure"),
    ("in_progress", None),
])
@pytest.mark.parametrize("rules_readable", [True, False])
def test_unresolved_action_gate_candidate_waits_instead_of_routing_floor(
        status, conclusion, rules_readable):
    fixture = proof_ready_fixture_without_gate()
    unresolved = gate_check(status=status, conclusion=conclusion)
    unresolved.pop("workflow_source")
    unresolved["workflow_source_error"] = "GraphQL file is null"
    fixture.checks = [unresolved]
    if not rules_readable:
        fixture.required_gate = {
            "status": "unidentified", "base": {}, "sources": [],
            "reason": "rules returned 403",
        }

    decision = work.decide(fixture, RULES)

    assert (decision.stage, decision.reason) == ("waiting", "required-gate-unidentified")
    assert work._floor_checks(fixture) == []


def test_unreadable_rules_keep_resolved_red_action_run_out_of_the_floor():
    fixture = proof_ready_fixture_without_gate()
    fixture.required_gate = {
        "status": "unidentified", "base": {}, "sources": [],
        "reason": "rules returned 403",
    }
    fixture.checks = [gate_check(
        conclusion="failure", repository="example/product",
        path="/".join((".github", "workflows", "ordinary.yml")),
    )]

    decision = work.decide(fixture, RULES)

    assert (decision.stage, decision.reason) == ("waiting", "required-gate-unidentified")
    assert decision.dispatch is False
    assert work._floor_checks(fixture) == []


def proof_ready_fixture_without_gate():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False, reviewer_ran=True)
    fixture.pr_comments.append({
        "id": 71, "body": f"<!-- tradecraft:proof:v1 head={SHA} -->",
        "user": {"login": PRODUCER},
    })
    fixture.proof_current = True
    return fixture


def test_conflicting_mergeability_explains_why_no_gate_run_exists():
    fixture = proof_ready_fixture_without_gate()
    fixture.pr["mergeable"] = None
    fixture.pr["mergeable_state"] = "CONFLICTING"

    decision = work.decide(fixture, RULES)
    assert decision.reason == "current-head-gate-evaluation-absent"
    assert "confirmed merge conflict" in decision.detail
    assert "unknown" not in decision.detail.lower()


def test_unknown_mergeability_is_not_reported_as_a_conflict():
    fixture = proof_ready_fixture_without_gate()
    fixture.pr["mergeable"] = None
    fixture.pr["mergeable_state"] = "UNKNOWN"

    decision = work.decide(fixture, RULES)
    assert decision.reason == "current-head-gate-evaluation-absent"
    assert "unknown" in decision.detail.lower()
    assert "confirmed merge conflict" not in decision.detail.lower()


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
        assert work.decide(fixture, RULES).stage == "artifact-settlement"
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


@pytest.mark.parametrize(("risk", "lane"), work.LANES)
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
    "Review risk: elevated\nReview lane: mechanical\n",
    "Review risk: critical\nReview lane: mechanical\n",
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


def test_launch_settings_read_program_b_defaults_with_accurate_sources():
    fixture = state(AFFIRMED)
    work.validate_marker_claims(fixture)

    implementer = work._launch_settings(fixture, "implementer", "codex")
    codex_seat = work._launch_settings(fixture, "ordinary-seat", "codex", "ordinary")
    ordinary = work._launch_settings(fixture, "ordinary-seat", "claude", "ordinary")
    cold = work._launch_settings(fixture, "cold-seat", "claude", "cold")
    terminal = work._launch_settings(fixture, "terminal-seat", "claude", "terminal")
    consumer = work._launch_settings(fixture, "use-consumer", "claude", "cold")

    assert implementer == work.LaunchSettings(
        "gpt-6.1-sol", "xhigh", "dispatch_implementer default",
        "dispatch_implementer default",
    )
    assert codex_seat == work.LaunchSettings(
        "gpt-6.1-sol", "xhigh", "dispatch_seat default", "dispatch_seat default",
    )
    assert ordinary == work.LaunchSettings(
        "claude-opus-5-5", "high", "dispatch_seat default", "classification mapping",
    )
    assert cold == work.LaunchSettings(
        "claude-opus-5-5", "xhigh", "dispatch_seat default", "classification mapping",
    )
    assert terminal == cold
    assert consumer == work.LaunchSettings(
        "claude-opus-5-5", "max", "dispatch_seat default",
        "work entrance use-consumer default",
    )


def test_implementer_vendor_file_and_role_overrides_are_independent(tmp_path):
    setting = tmp_path / "implementer-vendor"
    fixture = state(AFFIRMED)
    work.validate_marker_claims(fixture)
    assert work._implementer_vendor(fixture, "artifact_author", setting_path=setting)[0] == "codex"
    assert work._launch_settings(fixture, "artifact_author", "codex").model == "gpt-6.1-sol"
    setting.write_bytes(b"claude\n")
    assert work._implementer_vendor(fixture, "artifact_author", setting_path=setting)[0] == "claude"
    assert work._launch_settings(fixture, "artifact_author", "claude") == work.LaunchSettings(
        "claude-opus-5-5", "high", "dispatch_implementer default", "dispatch_implementer default",
    )
    fixture = state(AFFIRMED, (
        "<!-- tradecraft:model-override:v1 artifact_author=codex:author:xhigh "
        "implementer=claude:builder:high -->"
    ))
    work.validate_marker_claims(fixture)
    assert work._implementer_vendor(fixture, "artifact_author", setting_path=setting)[0] == "codex"
    assert work._implementer_vendor(fixture, "implementer", setting_path=setting)[0] == "claude"
    assert work._launch_settings(fixture, "artifact_author", "codex").model == "author"
    assert work._launch_settings(fixture, "implementer", "claude").model == "builder"


@pytest.mark.parametrize("content", [b"", b"CLAUDE", b"claude # note", b"\xff", b"codex claude"])
def test_invalid_machine_vendor_refuses_even_with_role_override(tmp_path, content):
    setting = tmp_path / "implementer-vendor"
    setting.write_bytes(content)
    fixture = state(AFFIRMED, "<!-- tradecraft:model-override:v1 implementer=codex:model:high -->")
    work.validate_marker_claims(fixture)
    with pytest.raises(work.WorkError, match="implementer vendor setting"):
        work._implementer_vendor(fixture, "implementer", setting_path=setting)


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


def test_work_configuration_accepts_an_optional_reviewer_label(tmp_path):
    directory = tmp_path / ".tradecraft"
    directory.mkdir()
    (directory / "work.json").write_text(json.dumps({
        "schema_version": 1, "product_repositories": [],
        "connected_reviewers": [], "marker_producers": [],
        "reviewer_label": "reviewers",
    }), encoding="utf-8")
    assert work.load_work_config(tmp_path).reviewer_label == "reviewers"


@pytest.mark.parametrize("label", ["", "   ", "bad\nlabel", 7])
def test_work_configuration_rejects_an_invalid_reviewer_label(tmp_path, label):
    directory = tmp_path / ".tradecraft"
    directory.mkdir()
    (directory / "work.json").write_text(json.dumps({
        "schema_version": 1, "product_repositories": [],
        "connected_reviewers": [], "marker_producers": [],
        "reviewer_label": label,
    }), encoding="utf-8")
    with pytest.raises(work.WorkError, match="reviewer_label"):
        work.load_work_config(tmp_path)


def test_every_configured_reviewer_needs_its_own_receipt():
    config = work.WorkConfig(
        connected_reviewers=frozenset({REVIEWER, "second-reviewer[bot]"}),
        marker_producers=frozenset({PRODUCER}),
    )
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False, reviewer_ran=True, config=config)
    receipts = work._reviewer_receipts(fixture)
    assert {item["login"]: item["result"] for item in receipts} == {
        REVIEWER: "present", "second-reviewer[bot]": "missing",
    }
    assert work.decide(fixture, RULES).reason == "required-connected-reviewer-has-not-run"


def test_notice_of_not_reviewing_does_not_receive_credit():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False)
    fixture.pr_comments = [{
        "id": 72, "body": "Review limit reached", "user": {"login": REVIEWER},
    }]
    assert work._reviewer_receipts(fixture)[0]["result"] == "notice-only"
    assert work.decide(fixture, RULES).stage == "waiting"


@pytest.mark.parametrize("body", [
    "Review summary: rate limited behavior is covered by tests.",
    "| Check | Status |\n| tests | running normally |",
])
def test_review_summary_text_is_not_mistaken_for_a_notice(body):
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False)
    fixture.pr_comments = [{
        "id": 72, "body": body, "user": {"login": REVIEWER},
    }]
    assert work._reviewer_receipts(fixture)[0]["result"] == "present"


def test_notice_only_review_body_does_not_receive_credit():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False)
    fixture.reviews = [{
        "id": 73, "body": "Review skipped", "user": {"login": REVIEWER},
    }]
    assert work._reviewer_receipts(fixture)[0]["result"] == "notice-only"


def test_substantive_review_after_notice_only_review_receives_credit():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False)
    fixture.reviews = [
        {"id": 73, "body": "Review skipped", "user": {"login": REVIEWER}},
        {"id": 74, "body": "Review completed", "user": {"login": REVIEWER}},
    ]
    receipt = work._reviewer_receipts(fixture)[0]
    assert receipt["result"] == "present"
    assert receipt["source"]["id"] == 74
    assert receipt["notices"] == ["review skipped"]


def test_proof_decision_is_holder_owned():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False, reviewer_ran=True)
    decision = work._reported_decision(fixture, work.decide(fixture, RULES))
    assert (decision.stage, decision.status) == ("proof", "holder-owned")


def test_path_rules_buy_runtime_use_and_decline_docs_and_tests():
    assert work.use_required(["lib/runtime.py"], RULES) is True
    assert work.use_required(["lib/tests/test_runtime.py", "README.md"], RULES) is False


def test_effective_policy_uses_the_lane_not_path_smallness_to_exempt_use():
    connected = work.effective_policy(state(AFFIRMED, paths=["lib/runtime.py"]), RULES)
    mechanical = work.effective_policy(state(MECHANICAL, paths=["lib/runtime.py"]), RULES)
    docs_only = work.effective_policy(state(AFFIRMED, paths=["README.md"]), RULES)

    assert (connected.mechanical, connected.path_requires_use, connected.use_required) == (
        False, True, True,
    )
    assert (mechanical.mechanical, mechanical.path_requires_use, mechanical.use_required) == (
        True, True, False,
    )
    assert (docs_only.mechanical, docs_only.path_requires_use, docs_only.use_required) == (
        False, False, False,
    )


def test_mechanical_policy_skips_ancestor_use_collection_even_for_use_paths():
    ancestor = "b" * 40
    marker = (
        f"<!-- tradecraft:use:v1 head={ancestor} status=pass changed=false "
        "staffing_status=qualified -->"
    )
    fixture = state(MECHANICAL, marker, pr=True, paths=["lib/runtime.py"])

    class NoTransport:
        def get(self, *_args, **_kwargs):
            pytest.fail("mechanical classification must not query use ancestry")

    work.prepare_use_evidence(fixture, NoTransport(), RULES)

    assert fixture.applicable_use is None
    assert fixture.use_application is None


def test_false_use_branch_requires_marker_and_explicit_line():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR,
                    f"<!-- tradecraft:no-use:v1 head={SHA} -->", pr=True,
                    paths=["README.md"])
    assert work.decide(fixture, RULES).stage == "proof"
    fixture.issue_comments[-1]["body"] += "\nUse: not required for changed paths"
    assert work.decide(fixture, RULES).stage == "ready-reviewers"


class AncestryTransport:
    def __init__(self, ancestor, head, commits):
        self.ancestor = ancestor
        self.head = head
        self.commits = commits

    def get(self, endpoint, *, paginate=False):
        if "/compare/" in endpoint:
            return {
                "status": "ahead", "ahead_by": len(self.commits),
                "merge_base_commit": {"sha": self.ancestor},
                "commits": [{"sha": revision} for revision in self.commits],
            }
        revision = endpoint.split("/commits/", 1)[1].split("?", 1)[0]
        return {"files": self.commits[revision]}


def test_clean_ancestor_use_applies_but_each_intervening_commit_is_classified():
    ancestor = "b" * 40
    marker = (
        f"<!-- tradecraft:use:v1 head={ancestor} status=pass changed=false "
        "staffing_status=qualified -->"
    )
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, marker, pr=True)
    commits = {
        "c" * 40: [{"filename": "README.md"}],
        "d" * 40: [{"filename": "lib/tests/test_runtime.py"}],
    }
    work.prepare_use_evidence(
        fixture, AncestryTransport(ancestor, SHA, commits), RULES
    )

    assert fixture.applicable_use is not None
    assert fixture.use_application["applicability"] == "ancestor"
    assert [item["sha"] for item in fixture.use_application["intervening_commits"]] == [
        "c" * 40, "d" * 40,
    ]


def test_intervening_bought_path_invalidates_ancestor_even_when_a_rename_hides_it():
    ancestor = "b" * 40
    marker = (
        f"<!-- tradecraft:use:v1 head={ancestor} status=pass changed=false "
        "staffing_status=qualified -->"
    )
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, marker, pr=True)
    commits = {
        "c" * 40: [{"filename": "README.md", "previous_filename": "lib/runtime.py"}],
    }
    work.prepare_use_evidence(
        fixture, AncestryTransport(ancestor, SHA, commits), RULES
    )

    assert fixture.applicable_use is None
    assert fixture.collection_diagnostics[-1]["code"] == "use-evidence-stale"
    assert work.decide(fixture, RULES).stage == "use"


class FakeTransport:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def get(self, endpoint, *, paginate=False):
        self.calls.append(("GET", endpoint, paginate))
        value = self.values[endpoint]
        if isinstance(value, Exception):
            raise value
        return value


ACTIONS_CONFIG = work.WorkConfig(
    connected_reviewers=frozenset({work.ACTIONS_REVIEWER}),
    marker_producers=frozenset({PRODUCER}),
)
REVIEW_SHA = "b" * 40  # A receipt need not be on the current PR head.
REVIEW_RUN = 36672170816


def actions_review(**patch):
    return {
        "id": 41, "user": {"login": work.ACTIONS_REVIEWER},
        "body": f"Review completed.\n<!-- connected-review-attempt:{REVIEW_RUN} -->",
        "state": "COMMENTED", "submitted_at": "2026-09-30T12:07:00Z",
        "commit_id": REVIEW_SHA,
        "html_url": "https://github.com/example/product/pull/7#pullrequestreview-41",
        **patch,
    }


def actions_run(**patch):
    return {
        "id": REVIEW_RUN, "repository": {"full_name": "example/product"},
        "path": "/".join((".github", "workflows", "connected-review.yml")),
        "event": "pull_request_target", "head_sha": REVIEW_SHA,
        "status": "completed", "conclusion": "success", **patch,
    }


def actions_job(**patch):
    return {
        "id": 91, "run_id": REVIEW_RUN, "run_attempt": 1, "name": "review",
        "status": "completed", "conclusion": "success", **patch,
    }


def actions_transport(*, reviews=None, run=None, job_pages=None, config=ACTIONS_CONFIG,
                      run_id=REVIEW_RUN):
    template = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                     pr=True, draft=False, config=config)
    base = "repos/example/product"
    values = {
        f"{base}/issues/12": template.issue,
        f"{base}/issues/12/comments": template.issue_comments,
        f"{base}/pulls?state=all&per_page=100": [{
            "number": 7, "state": "open", "body": "Closes #12",
        }],
        f"{base}/pulls/7": {**template.pr, "changed_files": 1},
        f"{base}/rules/branches/main": [],
        f"{base}/issues/7/comments": [],
        f"{base}/pulls/7/reviews": reviews if reviews is not None else [actions_review()],
        f"{base}/pulls/7/comments": [],
        f"{base}/pulls/7/files": [{"filename": "lib/runtime.py"}],
        f"{base}/commits/{SHA}/check-runs?per_page=100": {"check_runs": []},
        f"{base}/actions/runs/{run_id}": run if run is not None else actions_run(id=run_id),
        f"{base}/actions/runs/{run_id}/jobs?filter=all&per_page=100": (
            job_pages if job_pages is not None else [
                {"total_count": 1, "jobs": [actions_job(run_id=run_id)]}
            ]
        ),
    }
    return FakeTransport(values)


def collect_actions(transport, config=ACTIONS_CONFIG):
    return work.read_state(transport, "example/product", 12, config)


def actions_proof(fixture, tmp_path):
    fixture.record_root = tmp_path / "missing-dispatches"
    fixture.policy_sources = {
        key: {"repository": fixture.repo, "path": path, "revision": SHA, "sha256": "1" * 64}
        for key, path in (("work_configuration", ".tradecraft/work.json"),
                          ("use_rules", POLICY_PATH))
    }
    return work.compose_proof(fixture, RULES)


@pytest.mark.parametrize("patch", [
    {"body": "Review completed; run 36672170816"},
    {"body": "<!-- connected-review-attempt:0 -->"},
    {"body": "<!-- connected-review-attempt:-1 -->"},
    {"body": "<!-- connected-review-attempt:036672170816 -->"},
    {"body": "<!-- connected-review-attempt: 36672170816 -->"},
    {"body": "<!-- connected-review-attempt:36672170816"},
    {"body": "<!-- connected-review-attempt:36672170816 -->\n"
             "<!-- connected-review-attempt:bad -->"},
    {"body": "<!-- connected-review-attempt:36672170816 --> extra text"},
    {"body": " <!-- connected-review-attempt:36672170816 -->"},
    {"body": "> <!-- connected-review-attempt:36672170816 -->"},
    {"body": "<!--connected-review-attempt:36672170816-->"},
    {"state": "PENDING"}, {"state": "DISMISSED"}, {"state": None}, {"state": []},
    {"submitted_at": None}, {"submitted_at": ""},
    {"commit_id": "851159f"}, {"commit_id": None},
])
def test_actions_ineligible_review_waits_without_reading_runs(patch, tmp_path):
    transport = actions_transport(reviews=[actions_review(**patch)])
    fixture = collect_actions(transport)
    assert not work._reviewer_ran(fixture)
    assert work.decide(fixture, RULES).reason == "required-connected-reviewer-has-not-run"
    assert actions_proof(fixture, tmp_path)["reviewers"][0]["result"] == "missing"
    assert not any("/actions/runs/" in endpoint for _, endpoint, _ in transport.calls)
    assert any(item["code"] == "connected-review-receipt-unproven"
               for item in fixture.collection_diagnostics)


@pytest.mark.parametrize("quote", [
    "`connected-review-attempt:`",
    "`<!-- connected-review-attempt:81 -->`",
    "<!-- connected-review-attempt:81 -->",
    "<!-- connected-review-attempt:bad -->",
])
@pytest.mark.parametrize("blank_lines", ["", "\n \t\n"])
def test_actions_generated_review_quotes_are_credited_by_trailing_marker(
        quote, blank_lines, tmp_path):
    payload = connected_review.review_payload([{
        "severity": "P1", "wrong_result": "a genuine review is refused",
        "path": "lib/work.py", "line": 1,
        "input": "a finding quotes marker text", "execution_path": "receipt parsing",
        "evidence": f"The finding quotes {quote}.", "inline": False,
    }], REVIEW_SHA, str(REVIEW_RUN), {})
    transport = actions_transport(reviews=[actions_review(body=payload["body"] + blank_lines)])
    fixture = collect_actions(transport)
    assert set(fixture.connected_review_runs) == {REVIEW_RUN}
    assert work._reviewer_ran(fixture)
    assert work.decide(fixture, RULES).stage == "review-disposition"
    fixture.pr_comments.append({"user": {"login": PRODUCER}, "body":
        f"fixed - repaired; [tradecraft-review-finding:v1:{REVIEW_RUN}:1]"
        "(https://github.com/example/product/pull/7#pullrequestreview-41)"})
    assert work.decide(fixture, RULES).stage == "proof"
    receipt = actions_proof(fixture, tmp_path)["reviewers"][0]
    assert receipt["result"] == "present"
    assert receipt["source"]["id"] == 41
    assert receipt["source"]["revision"] == REVIEW_SHA


@pytest.mark.parametrize("blank_lines", ["", "\n \t\n"])
def test_actions_review_with_only_a_non_trailing_marker_gets_no_credit(blank_lines, tmp_path):
    body = f"<!-- connected-review-attempt:{REVIEW_RUN} -->\nReview completed.{blank_lines}"
    transport = actions_transport(reviews=[actions_review(body=body)])
    fixture = collect_actions(transport)
    assert not work._reviewer_ran(fixture)
    assert work.decide(fixture, RULES).stage == "waiting"
    assert actions_proof(fixture, tmp_path)["reviewers"][0]["result"] == "missing"
    assert not any("/actions/runs/" in endpoint for _, endpoint, _ in transport.calls)


def test_actions_trailing_marker_cannot_fall_back_to_an_earlier_run(tmp_path):
    body = (f"<!-- connected-review-attempt:{REVIEW_RUN} -->\n"
            "<!-- connected-review-attempt:81 -->")
    transport = actions_transport(reviews=[actions_review(body=body)])
    fixture = collect_actions(transport)
    assert set(fixture.connected_review_runs) == {81}
    assert not work._reviewer_ran(fixture)
    assert work.decide(fixture, RULES).stage == "waiting"
    assert actions_proof(fixture, tmp_path)["reviewers"][0]["result"] == "missing"


@pytest.mark.parametrize("patch", [
    {"id": REVIEW_RUN + 1}, {"id": True},
    {"repository": {"full_name": "example/other"}}, {"repository": None},
    {"path": "/".join((".github", "workflows", "mutation.yml"))},
    {"path": "/".join((".github", "workflows", "renamed.yml")) + "@refs/heads/main"},
    {"path": None}, {"event": "push"}, {"event": "workflow_dispatch"}, {"event": []},
    {"head_sha": SHA}, {"head_sha": None},
])
def test_actions_wrong_run_facts_grant_no_credit(patch, tmp_path):
    fixture = collect_actions(actions_transport(run=actions_run(**patch)))
    assert work._reviewer_receipts(fixture)[0]["result"] == "missing"
    assert work.decide(fixture, RULES).stage == "waiting"
    composed = actions_proof(fixture, tmp_path)
    assert composed["reviewers"][0]["source"] is None
    assert any(item["code"] == "connected-review-receipt-unproven"
               for item in composed["diagnostics"])


@pytest.mark.parametrize("patch", [
    {"name": "report"}, {"name": "prepare"}, {"name": "review (matrix)"},
    {"status": "queued"}, {"status": "in_progress"},
    {"conclusion": "failure"}, {"conclusion": "cancelled"}, {"conclusion": "skipped"},
    {"conclusion": None}, {"run_id": REVIEW_RUN + 1}, {"run_id": None},
])
def test_actions_requires_its_successful_completed_review_job(patch, tmp_path):
    fixture = collect_actions(actions_transport(job_pages=[{
        "total_count": 1, "jobs": [actions_job(**patch)],
    }]))
    assert not work._reviewer_ran(fixture)
    assert work.decide(fixture, RULES).stage == "waiting"
    assert actions_proof(fixture, tmp_path)["reviewers"][0]["result"] == "missing"


def test_actions_pull_request_event_gets_no_credit_at_fixed_workflow_path(tmp_path):
    run = actions_run(event="pull_request")
    transport = actions_transport(run=run)
    fixture = collect_actions(transport)
    assert not work._reviewer_ran(fixture)
    assert work.decide(fixture, RULES).reason == "required-connected-reviewer-has-not-run"
    assert actions_proof(fixture, tmp_path)["reviewers"][0]["result"] == "missing"

    run["event"] = "pull_request_target"
    accepted = collect_actions(transport)
    assert work._reviewer_ran(accepted)
    assert work.decide(accepted, RULES).stage == "proof"
    assert actions_proof(accepted, tmp_path)["reviewers"][0]["result"] == "present"


@pytest.mark.parametrize("status", sorted(work.COMPLETED_REVIEWS))
@pytest.mark.parametrize("suffix", ["", "@refs/heads/main"])
def test_actions_real_review_survives_failed_later_attempt_and_report(
        status, suffix, tmp_path):
    run = actions_run(conclusion="failure", run_attempt=2)
    run["path"] += suffix
    transport = actions_transport(
        reviews=[actions_review(state=status)], run=run, job_pages=[
            {"total_count": 3, "jobs": [
                actions_job(id=92, run_attempt=2, conclusion="failure"),
                actions_job(id=93, name="report", conclusion="failure"),
            ]},
            {"total_count": 3, "jobs": [actions_job()]},
        ],
    )
    fixture = collect_actions(transport)
    assert work._reviewer_ran(fixture)
    assert work.decide(fixture, RULES).stage == "proof"
    composed = actions_proof(fixture, tmp_path)
    receipt = composed["reviewers"][0]
    assert receipt["result"] == "present"
    assert receipt["source"]["kind"] == "review"
    assert receipt["source"]["id"] == 41
    assert receipt["source"]["revision"] == REVIEW_SHA != SHA
    assert {method for method, _, _ in transport.calls} == {"GET"}
    assert ("GET", f"repos/example/product/actions/runs/{REVIEW_RUN}"
            "/jobs?filter=all&per_page=100", True) in transport.calls


@pytest.mark.parametrize("endpoint, response", [
    ("run", work.WorkError("403 Actions read denied")), ("run", []),
    ("run", subprocess.TimeoutExpired("gh", 120)),
    ("jobs", work.WorkError("second pagination request failed")), ("jobs", "bad"),
    ("jobs", []), ("jobs", [{}]), ("jobs", [{"total_count": 1, "jobs": "bad"}]),
    ("jobs", [{"total_count": 2, "jobs": [actions_job()]}]),
    ("jobs", [{"total_count": 1, "jobs": [actions_job()]}, "bad later page"]),
    ("jobs", [{"total_count": True, "jobs": [actions_job()]}]),
])
def test_actions_unreadable_evidence_has_diagnostics_and_recovers(
        endpoint, response, tmp_path):
    transport = actions_transport()
    path = f"repos/example/product/actions/runs/{REVIEW_RUN}"
    if endpoint == "jobs":
        path += "/jobs?filter=all&per_page=100"
    valid = transport.values[path]
    transport.values[path] = response
    fixture = collect_actions(transport)
    assert not work._reviewer_ran(fixture)
    assert work.decide(fixture, RULES).stage == "waiting"
    assert any(item["code"] == "connected-review-receipt-unproven"
               for item in actions_proof(fixture, tmp_path)["diagnostics"])
    transport.values[path] = valid
    recovered = collect_actions(transport)
    assert work._reviewer_ran(recovered)
    assert actions_proof(recovered, tmp_path)["reviewers"][0]["result"] == "present"


@pytest.mark.parametrize("surface", ["comments", "inline"])
def test_actions_ordinary_and_inline_comments_cannot_be_receipts(surface):
    transport = actions_transport(reviews=[])
    path = ("repos/example/product/issues/7/comments" if surface == "comments"
            else "repos/example/product/pulls/7/comments")
    transport.values[path] = [actions_review()]
    fixture = collect_actions(transport)
    assert work._reviewer_receipts(fixture)[0]["result"] == "missing"
    assert work.decide(fixture, RULES).stage == "waiting"
    if surface == "inline":
        assert work._undisposed_threads(fixture)[0] == [41]
    assert not any("/actions/runs/" in endpoint for _, endpoint, _ in transport.calls)


def test_actions_invalid_candidate_does_not_hide_valid_review_and_reuses_run():
    transport = actions_transport(reviews=[
        actions_review(id=40, body="ordinary workflow review"),
        actions_review(id=42, commit_id=SHA),
        actions_review(), actions_review(id=43),
    ])
    fixture = collect_actions(transport)
    assert work._reviewer_receipts(fixture)[0]["source"]["id"] == 41
    assert work.decide(fixture, RULES).stage == "proof"
    assert sum(endpoint.endswith(f"/actions/runs/{REVIEW_RUN}")
               for _, endpoint, _ in transport.calls) == 1
    assert sum("/jobs?" in endpoint for _, endpoint, _ in transport.calls) == 1


def test_actions_unreadable_other_run_does_not_hide_valid_receipt():
    transport = actions_transport(reviews=[
        actions_review(id=40, body="<!-- connected-review-attempt:81 -->"),
        actions_review(),
    ])
    fixture = collect_actions(transport)
    assert work._reviewer_receipts(fixture)[0]["source"]["id"] == 41
    assert fixture.connected_review_runs[81].error is not None


def test_actions_failed_run_never_falls_back_to_bot_comments(tmp_path):
    transport = actions_transport(job_pages=[{"total_count": 0, "jobs": []}])
    transport.values["repos/example/product/issues/7/comments"] = [actions_review(id=42)]
    transport.values["repos/example/product/pulls/7/comments"] = [actions_review(id=43)]
    fixture = collect_actions(transport)
    assert work.decide(fixture, RULES).stage == "waiting"
    assert actions_proof(fixture, tmp_path)["reviewers"][0]["result"] == "missing"
    assert work._undisposed_threads(fixture)[0] == [43]


def test_actions_review_run_read_is_reused_for_check_collection():
    transport = actions_transport()
    transport.values[f"repos/example/product/commits/{SHA}/check-runs?per_page=100"] = {
        "check_runs": [{"id": 91, "details_url": (
            f"https://github.com/example/product/actions/runs/{REVIEW_RUN}/job/91"
        )}],
    }
    fixture = collect_actions(transport)
    assert work._reviewer_ran(fixture)
    assert fixture.checks[0]["workflow_run"]["id"] == REVIEW_RUN
    assert sum(endpoint.endswith(f"/actions/runs/{REVIEW_RUN}")
               for _, endpoint, _ in transport.calls) == 1


def test_actions_without_collected_provenance_cannot_receive_manual_credit():
    fixture = state(pr=True, config=ACTIONS_CONFIG)
    fixture.reviews = [actions_review()]
    assert not work._reviewer_ran(fixture)


@pytest.mark.parametrize("surface", ["reviews", "comments"])
def test_actions_notices_keep_notice_only_handling_without_run_reads(surface):
    transport = actions_transport(reviews=[])
    path = ("repos/example/product/pulls/7/reviews" if surface == "reviews"
            else "repos/example/product/issues/7/comments")
    transport.values[path] = [actions_review(body="Review skipped: finder failed")]
    fixture = collect_actions(transport)
    receipt = work._reviewer_receipts(fixture)[0]
    assert receipt["result"] == "notice-only"
    assert receipt["notices"] == ["review skipped"]
    assert not any("/actions/runs/" in endpoint for _, endpoint, _ in transport.calls)


def test_actions_unconfigured_and_other_reviewers_need_no_run_reads():
    transport = actions_transport(config=CONFIG, reviews=[
        actions_review(), actions_review(user={"login": REVIEWER}, body="Review summary"),
    ])
    fixture = collect_actions(transport, CONFIG)
    assert work._reviewer_ran(fixture)
    assert not any("/actions/runs/" in endpoint for _, endpoint, _ in transport.calls)


def test_actions_collector_handles_real_rest_object_pages(monkeypatch):
    pages = [
        {"total_count": 2, "jobs": [actions_job(id=92, conclusion="failure", run_attempt=2)]},
        {"total_count": 2, "jobs": [actions_job()]},
    ]
    commands = []

    def gh(command, **kwargs):
        commands.append(command)
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["stdout"] == kwargs["stderr"] == subprocess.PIPE
        return subprocess.CompletedProcess(command, 0, json.dumps(pages).encode("utf-8"), b"")

    class RESTJobsTransport(FakeTransport):
        def get(self, endpoint, *, paginate=False):
            if "/jobs?" in endpoint:
                return work.GitHubREST().get(endpoint, paginate=paginate)
            return super().get(endpoint, paginate=paginate)

    monkeypatch.setattr(work.subprocess, "run", gh)
    fixture = collect_actions(RESTJobsTransport(actions_transport().values))
    assert work._reviewer_ran(fixture)
    assert commands == [[
        "gh", "api", "--method", "GET",
        f"repos/example/product/actions/runs/{REVIEW_RUN}/jobs?filter=all&per_page=100",
        "--paginate", "--slurp",
    ]]


ACTIONS_FIXTURES = LIB.parent / "skills" / "work" / "references" / "proof-fixtures"
ACTIONS_CASE_PATH = ACTIONS_FIXTURES / "v1-actions-receipts.json"
ACTIONS_CASES = json.loads(ACTIONS_CASE_PATH.read_bytes()) if ACTIONS_CASE_PATH.exists() else None


@pytest.mark.parametrize("case", ACTIONS_CASES["cases"] if ACTIONS_CASES else [],
                         ids=lambda case: case["name"])
def test_actions_interoperability_cases_use_collected_facts(case, tmp_path):
    live = deepcopy(ACTIONS_CASES["live"])
    for key, value in case["live_patch"].items():
        if isinstance(value, dict):
            live[key].update(deepcopy(value))
        else:
            live[key] = deepcopy(value)
    run = live["run"]
    run["path"] = "/".join(live["workflow_path"]["segments"])
    if live["workflow_path"]["ref"] is not None:
        run["path"] += "@" + live["workflow_path"]["ref"]
    transport = actions_transport(reviews=[live["review"]], run=run, job_pages=live["job_pages"])
    fixture = collect_actions(transport)
    assert work._reviewer_ran(fixture) is (case["result"] == "present")
    assert work.decide(fixture, RULES).stage == (
        "proof" if case["result"] == "present" else "waiting"
    )
    assert actions_proof(fixture, tmp_path)["reviewers"][0]["result"] == case["result"]


class GateReadTransport(FakeTransport):
    def __init__(self, values, provenance):
        super().__init__(values)
        self.provenance = provenance
        self.provenance_reads = []

    def workflow_run_files(self, query, variables):
        assert query == work.WORKFLOW_RUN_FILES_QUERY
        check_suite_ids = variables["ids"]
        self.provenance_reads.append(check_suite_ids)
        return self.provenance


def gate_read_values(*, rules, checks, runs, base_ref="release/next",
                     repo="acme/widget"):
    base = f"repos/{repo}"
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
        f"{base}/pulls/9": {
            "number": 9, "state": "open", "draft": True, "changed_files": 1,
            "head": {"sha": SHA},
            "base": {
                "ref": base_ref, "sha": BASE_SHA,
                "repo": {"id": 1, "full_name": repo},
            },
        },
        f"{base}/rules/branches/{base_ref.replace('/', '%2F')}?per_page=100": rules,
        f"{base}/issues/9/comments": [],
        f"{base}/pulls/9/reviews": [],
        f"{base}/pulls/9/comments": [],
        f"{base}/pulls/9/files": [{"filename": "lib/runtime.py"}],
        f"{base}/commits/{SHA}/check-runs?per_page=100": {
            "total_count": len(checks), "check_runs": checks,
        },
    }
    values.update({f"{base}/actions/runs/{identity}": value
                   for identity, value in runs.items()})
    return values


def test_state_reader_uses_base_rules_and_top_level_source_for_all_gate_readers():
    checks = [
        {
            "id": 106986603530, "name": "change-proof / Change proof",
            "status": "completed", "conclusion": "success",
            "started_at": "2026-09-22T23:53:58Z",
            "completed_at": "2026-09-22T23:54:07Z",
            "details_url": (
                "https://github.com/Grimblaz-and-Friends/Daemon/actions/runs/"
                "35790907096/job/106986603530"
            ),
            "check_suite": {"id": 96911736868},
        },
        {
            "id": 106958874507, "name": "Change proof / Change proof",
            "status": "completed", "conclusion": "failure",
            "started_at": "2026-09-22T22:10:30Z",
            "completed_at": "2026-09-22T22:10:39Z",
            "details_url": (
                "https://github.com/Grimblaz-and-Friends/Daemon/actions/runs/"
                "35790907386/job/106958874507"
            ),
            "check_suite": {"id": 96911738155},
        },
    ]
    rules = [
        {
            "ruleset_id": 13437562,
            "ruleset_source": "Grimblaz-and-Friends",
            "ruleset_source_type": "Organization",
            "type": "workflows",
            "parameters": {"workflows": [{
                "repository_id": 1378396361, "path": GATE_PATH,
                "ref": "refs/heads/main",
            }]},
        },
    ]
    values = gate_read_values(
        rules=rules, checks=checks,
        runs={
            35790907386: {
                "id": 35790907386, "workflow_id": 363584200,
                "check_suite_id": 96911738155,
                "check_suite_node_id": "CS_kwDOTqRt0c8AAAAWkGPFKw",
                "head_sha": SHA, "status": "completed", "conclusion": "failure",
                "path": GATE_PATH, "name": "Change proof",
            },
            35790907096: {
                "id": 35790907096, "workflow_id": 362780412,
                "check_suite_id": 96911736868,
                "check_suite_node_id": "CS_kwDOTqRt0c8AAAAWkGPAJA",
                "head_sha": SHA, "status": "completed", "conclusion": "success",
                "path": "/".join((".github", "workflows", "change-proof.yml")),
                "name": "Change proof",
            },
        },
        base_ref="main", repo="Grimblaz-and-Friends/Daemon",
    )
    values["repositories/1378396361"] = {
        "id": 1378396361, "full_name": "Grimblaz-and-Friends/change-proof",
    }
    provenance = {"data": {"nodes": [
        {
            "id": "CS_kwDOTqRt0c8AAAAWkGPFKw", "workflowRun": {
                "databaseId": 35790907386,
                "workflow": {"databaseId": 363584200},
                "file": {
                    "repositoryName": "Grimblaz-and-Friends/change-proof",
                    "path": GATE_PATH,
                },
            },
        },
        {
            "id": "CS_kwDOTqRt0c8AAAAWkGPAJA", "workflowRun": {
                "databaseId": 35790907096,
                "workflow": {"databaseId": 362780412},
                "file": {
                    "repositoryName": "Grimblaz-and-Friends/Daemon",
                    "path": "/".join((".github", "workflows", "change-proof.yml")),
                },
            },
        },
    ]}}
    transport = GateReadTransport(values, provenance)

    fixture = work.read_state(transport, "Grimblaz-and-Friends/Daemon", 3, CONFIG)

    assert fixture.required_gate["status"] == "identified", fixture.required_gate
    assert fixture.required_gate["base"]["ref"] == "main"
    assert fixture.required_gate["sources"][0]["rules"] == [{
        "ruleset_id": 13437562,
        "ruleset_source": "Grimblaz-and-Friends",
        "ruleset_source_type": "Organization",
    }]
    assert [check["id"] for check in work._gate_checks(fixture)] == [106958874507]
    assert [check["id"] for check in work._floor_checks(fixture)] == [106986603530]
    assert work._release_gate_status(fixture)["verdict"] == "red"
    assert work._checks_red(fixture) is False
    assert transport.provenance_reads == [[
        "CS_kwDOTqRt0c8AAAAWkGPAJA", "CS_kwDOTqRt0c8AAAAWkGPFKw",
    ]]


@pytest.mark.parametrize("rules", [
    [],
    [{"id": 40, "type": "required_status_checks", "parameters": {}}],
])
def test_successfully_read_rules_without_workflows_mean_no_required_gate(rules):
    pr = {
        "base": {
            "ref": "main", "sha": BASE_SHA,
            "repo": {"id": 1, "full_name": "person/project"},
        },
    }
    endpoint = "repos/person/project/rules/branches/main?per_page=100"
    requirement = work._collect_required_gate(FakeTransport({endpoint: rules}), pr)
    assert requirement == {
        "status": "none",
        "base": {
            "repository": "person/project", "repository_id": 1,
            "ref": "main", "sha": BASE_SHA,
        },
        "sources": [], "reason": "no required gate",
    }

    fixture = proof_ready_fixture_without_gate()
    fixture.required_gate = requirement
    assert work.decide(fixture, RULES).stage == "release-report"

    class NoMutation:
        def __init__(self):
            self.posts = []

        def post(self, endpoint, payload):
            self.posts.append((endpoint, payload))

    transport = NoMutation()
    assert work._rerun_gate_evaluations(transport, fixture, SHA)[0]["reason"] == (
        "no required gate"
    )
    assert transport.posts == []


@pytest.mark.parametrize("failure", ["forbidden", "later-page", "malformed"])
def test_unreadable_or_malformed_rules_are_unidentified(failure):
    pr = {
        "base": {
            "ref": "main", "sha": BASE_SHA,
            "repo": {"id": 1, "full_name": "acme/widget"},
        },
    }
    endpoint = "repos/acme/widget/rules/branches/main?per_page=100"

    class RulesTransport:
        def get(self, requested, *, paginate=False):
            assert requested == endpoint
            if failure != "malformed":
                raise work.WorkError(failure)
            return [{"id": 31, "type": "workflows", "parameters": {"workflows": [{}]}}]

    requirement = work._collect_required_gate(RulesTransport(), pr)
    assert requirement["status"] == "unidentified"
    assert requirement["reason"]


def test_missing_provenance_prevents_a_green_claim_even_with_a_matched_success():
    fixture = state(pr=True)
    unknown = gate_check(identity=102, run_id=82, workflow_id=12)
    unknown.pop("workflow_source")
    unknown["workflow_source_error"] = "GraphQL file is null"
    fixture.checks = [unknown]
    result = work._release_gate_status(fixture)
    assert result["verdict"] == "unidentified"
    assert result["requirement_known"] is True

    known_copy = gate_check(
        identity=103, run_id=83, workflow_id=13, conclusion="failure",
        repository="acme/widget",
    )
    fixture.checks = [gate_check(), unknown, known_copy]
    result = work._release_gate_status(fixture)
    assert result["verdict"] == "unidentified"
    assert {item["id"] for item in work._floor_checks(fixture)} == {103}


@pytest.mark.parametrize("response", [
    {"data": {"nodes": [{"id": "CS", "workflowRun": None}]},
     "errors": [{"message": "partial"}]},
    {"data": {"nodes": [{
        "id": "CS", "workflowRun": {
            "databaseId": 81, "workflow": {"databaseId": 11},
            "file": {"repositoryName": "example/change-proof", "path": GATE_PATH},
        },
    }]}, "errors": [{"message": "another field failed"}]},
    {"data": {"nodes": [{
        "id": "CS", "workflowRun": {
            "databaseId": 999, "workflow": {"databaseId": 11},
            "file": {"repositoryName": "example/change-proof", "path": GATE_PATH},
        },
    }]}},
])
def test_partial_or_mismatched_graphql_provenance_is_not_guessed(response):
    check = gate_check()
    check.pop("workflow_source")
    check["check_suite"] = {"id": 96911738155}
    check["workflow_run"]["check_suite_node_id"] = "CS"

    class ProvenanceTransport:
        def workflow_run_files(self, query, variables):
            assert query == work.WORKFLOW_RUN_FILES_QUERY
            check_suite_ids = variables["ids"]
            assert check_suite_ids == ["CS"]
            return response

    work._collect_workflow_provenance(ProvenanceTransport(), [check])
    assert "workflow_source" not in check
    assert "workflow_source_error" in check


def test_workflow_provenance_batches_graphql_nodes_at_one_hundred():
    checks = []
    identities = {}
    for offset in range(101):
        run_id = 1000 + offset
        workflow_id = 2000 + offset
        node_id = f"CS-{offset:03d}"
        identities[node_id] = (run_id, workflow_id)
        checks.append({
            "id": 3000 + offset,
            "details_url": f"https://github.com/acme/widget/actions/runs/{run_id}/job/1",
            "check_suite": {"id": 4000 + offset},
            "workflow_run": {
                "id": run_id,
                "workflow_id": workflow_id,
                "check_suite_node_id": node_id,
            },
        })

    class ProvenanceTransport:
        def __init__(self):
            self.reads = []

        def workflow_run_files(self, query, variables):
            assert query == work.WORKFLOW_RUN_FILES_QUERY
            check_suite_ids = variables["ids"]
            self.reads.append(check_suite_ids)
            return {"data": {"nodes": [{
                "id": node_id,
                "workflowRun": {
                    "databaseId": identities[node_id][0],
                    "workflow": {"databaseId": identities[node_id][1]},
                    "file": {
                        "repositoryName": "acme/widget",
                        "path": "/".join((".github", "workflows", f"{node_id}.yml")),
                    },
                },
            } for node_id in check_suite_ids]}}

    transport = ProvenanceTransport()
    work._collect_workflow_provenance(transport, checks)

    assert [len(batch) for batch in transport.reads] == [100, 1]
    assert all("workflow_source" in check for check in checks)


def test_unresolved_required_source_repository_is_unidentified():
    pr = {
        "base": {
            "ref": "main", "sha": BASE_SHA,
            "repo": {"id": 1, "full_name": "acme/widget"},
        },
    }
    rules_endpoint = "repos/acme/widget/rules/branches/main?per_page=100"

    class RepositoryTransport:
        def get(self, endpoint, *, paginate=False):
            if endpoint == rules_endpoint:
                return [{
                    "id": 31, "type": "workflows",
                    "parameters": {"workflows": [{
                        "repository_id": 2, "path": GATE_PATH,
                    }]},
                }]
            raise work.WorkError("repository hidden")

    requirement = work._collect_required_gate(RepositoryTransport(), pr)
    assert requirement["status"] == "unidentified"
    assert "repository 2" in requirement["reason"]


def test_multiple_required_sources_cannot_aggregate_green_while_one_is_missing():
    fixture = state(pr=True)
    second = dict(GATE_SOURCE)
    second.update({
        "repository_id": 3, "repository": "example/other-proof",
        "path": "/".join((".github", "workflows", "other.yml")),
    })
    fixture.required_gate["sources"] = [dict(GATE_SOURCE), second]
    fixture.checks = [gate_check()]

    result = work._release_gate_status(fixture)

    assert result["verdict"] == "absent"
    assert [item["verdict"] for item in result["requirements"]] == ["green", "absent"]


def test_gate_rerun_deduplicates_jobs_from_one_current_run():
    fixture = state(pr=True)
    fixture.checks = [
        gate_check(identity=91, name="proof / first"),
        gate_check(identity=92, name="proof / second"),
    ]

    class GateTransport:
        def __init__(self):
            self.posts = []

        def post(self, endpoint, payload):
            self.posts.append((endpoint, payload))
            return {}

        def get(self, endpoint, *, paginate=False):
            return {"id": 81, "status": "queued", "conclusion": None}

    transport = GateTransport()
    reruns = work._rerun_gate_evaluations(transport, fixture, SHA)
    assert transport.posts == [("repos/example/product/actions/runs/81/rerun", {})]
    assert len(reruns) == 1


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
                             "changed_files": 1,
                             "head": {"sha": SHA}},
        f"{base}/issues/9/comments": [],
        f"{base}/pulls/9/reviews": [],
        f"{base}/pulls/9/comments": [],
        f"{base}/pulls/9/files": [{"filename": "lib/runtime.py"}],
        f"{base}/commits/{SHA}/check-runs?per_page=100": {"check_runs": []},
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
    assert decision.detail == (
        "pull request #9 merged; holder decides what the issue still owes: close it, "
        "run another build, or run a use owed after the merge from a landed commit"
    )


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
    fixture.review_comments = [{
        "id": 42, "in_reply_to_id": 41, "body": "Fixed\n" + REVIEWED,
        "user": {"login": PRODUCER},
    }]
    assert {marker.name for marker in fixture.markers} == {"connected-reviewer"}


def test_run_reads_the_work_configuration_from_root(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    configured_work(tmp_path, ["acme/product-app"])
    write_policy(tmp_path)
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
    write_policy(tmp_path)
    args = work.parser().parse_args([
        "--repo", "acme/widget", "--issue", "3", "--root", str(tmp_path),
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


def adopter_transport():
    base = "repos/acme/widget"
    return FakeTransport({
        f"{base}/issues/3": {
            "number": 3, "state": "open", "body": "", "labels": [],
            "user": {"login": PRODUCER},
        },
        f"{base}/issues/3/comments": [
            {"body": AFFIRMED, "user": {"login": PRODUCER}},
        ],
        f"{base}/pulls?state=all&per_page=100": [
            {"number": 9, "state": "open", "body": "Closes #3"},
        ],
        f"{base}/pulls/9": {
            "number": 9, "state": "open", "draft": True, "changed_files": 1,
            "head": {"sha": SHA},
        },
        f"{base}/issues/9/comments": [],
        f"{base}/pulls/9/reviews": [],
        f"{base}/pulls/9/comments": [],
        f"{base}/pulls/9/files": [{"filename": "product-app/main.py"}],
        f"{base}/commits/{SHA}/check-runs?per_page=100": {"check_runs": []},
    })


PRODUCT_RULES = {
    "schema_version": 1,
    "rules": [{"name": "product-app", "include": ["product-app/**"], "exclude": []}],
}


def run_adopter_read(root, monkeypatch, capsys, *override):
    configured_work(root, [])
    observed = {}
    original_decide = work.decide

    def capture(fixture, rules):
        observed["rules"] = rules
        observed["required"] = work.effective_policy(fixture, rules).use_required
        return original_decide(fixture, rules)

    monkeypatch.setattr(work, "decide", capture)
    transport = adopter_transport()
    args = work.parser().parse_args([
        "--repo", "acme/widget", "--issue", "3", "--root", str(root), *override,
    ])
    assert work.run(args, transport=transport) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["work"] == "acme/widget#3"
    assert {method for method, _endpoint, _paginate in transport.calls} == {"GET"}
    return observed


def test_adopter_default_uses_its_product_policy_without_lib(tmp_path, monkeypatch, capsys):
    write_policy(tmp_path, PRODUCT_RULES)
    assert not (tmp_path / "lib").exists()
    assert work.use_required(["product-app/main.py"], RULES) is False

    observed = run_adopter_read(tmp_path, monkeypatch, capsys)

    assert observed == {"rules": PRODUCT_RULES, "required": True}
    assert not (tmp_path / "lib").exists()


@pytest.mark.parametrize("legacy_trap", [False, True])
@pytest.mark.parametrize("command", [[], ["run", "proof"]], ids=["ordinary", "proof"])
def test_missing_default_names_repository_policy_without_fallback(
        tmp_path, legacy_trap, command):
    root = repository(tmp_path)
    if legacy_trap:
        write_policy(root, PRODUCT_RULES, "/".join(("lib", "use-rules.json")))
    args = work.parser().parse_args([
        *command, "--repo", "acme/widget", "--issue", "3", "--root", str(root),
    ])

    with pytest.raises(work.WorkError) as raised:
        work.run(args, transport=object())

    assert str(raised.value) == (
        f"repository's change-proof policy is missing: {(root / POLICY_PATH).resolve()}"
    )
    assert "use-rules.json" not in str(raised.value)


def test_explicit_setup_override_replaces_absent_default(tmp_path, monkeypatch, capsys):
    alternate = write_policy(tmp_path, PRODUCT_RULES, "setup-rules.json")
    assert not (tmp_path / POLICY_PATH).exists()

    observed = run_adopter_read(
        tmp_path, monkeypatch, capsys, "--use-rules", str(alternate),
    )

    assert observed == {"rules": PRODUCT_RULES, "required": True}


@pytest.mark.parametrize("invalid", [None, b"not json", b'{"schema_version": 2}'])
def test_invalid_override_does_not_fall_back_to_valid_default(tmp_path, invalid):
    write_policy(tmp_path, PRODUCT_RULES)
    alternate = tmp_path / "override.json"
    if invalid is not None:
        alternate.write_bytes(invalid)
    args = work.parser().parse_args([
        "--repo", "acme/widget", "--issue", "3", "--root", str(tmp_path),
        "--use-rules", str(alternate),
    ])

    with pytest.raises(work.WorkError) as raised:
        work.run(args, transport=object())

    assert str(alternate) in str(raised.value)


@pytest.mark.parametrize("relative", [POLICY_PATH, "config/alternate.json"])
@pytest.mark.parametrize("absolute", [False, True], ids=["relative", "absolute"])
def test_override_uses_holder_root_from_conflicting_working_directory(
        tmp_path, monkeypatch, capsys, relative, absolute):
    root = tmp_path / "holder"
    root.mkdir()
    shell = tmp_path / "elsewhere"
    shell.mkdir()
    selected = write_policy(root, PRODUCT_RULES, relative)
    write_policy(shell, RULES, relative)
    if relative != POLICY_PATH:
        write_policy(root, RULES)
    monkeypatch.chdir(shell)
    assert Path.cwd() != root

    observed = run_adopter_read(
        root, monkeypatch, capsys, "--use-rules", str(selected) if absolute else relative,
    )

    assert observed == {"rules": PRODUCT_RULES, "required": True}


def test_override_expands_home_before_rooting_relative_paths(tmp_path, monkeypatch, capsys):
    root = tmp_path / "holder"
    root.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    write_policy(root, RULES, "~/rules.json")
    write_policy(home, PRODUCT_RULES, "rules.json")
    monkeypatch.setattr(Path, "home", lambda: home)
    # expanduser reads the platform environment rather than Path.home().
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))

    observed = run_adopter_read(root, monkeypatch, capsys, "--use-rules", "~/rules.json")

    assert observed == {"rules": PRODUCT_RULES, "required": True}


@pytest.mark.parametrize("stage", ["artifact", "build", "floor", "review-disposition"])
@pytest.mark.parametrize("brief", [AFFIRMED, MECHANICAL])
def test_builder_prompt_names_one_stage_and_forbids_pipeline_dispatch(stage, brief):
    fixture = state(brief)
    prompt = work._stage_prompt(fixture, work.Decision(stage, True, "fresh", "fixture"))
    assert prompt.count(f'"stage": "{stage}"'.encode()) == 1
    assert b"Do not start or dispatch a later stage" in prompt
    assert b"Your final message is your return to the holder." in prompt
    assert b"A path to a file you wrote, or a pointer telling the holder to retrieve that file, is not a return." in prompt
    if stage == "artifact":
        assert b"Return the whole artifact text in your final message" in prompt
        assert b"brief below quoted verbatim as a Markdown blockquote" in prompt
    evidence = json.loads(prompt.split(b"\n\n")[1])
    assert evidence["work"] == "example/product#12"
    assert (evidence["lane_reason"] is None) == (brief == AFFIRMED)
    assert brief.encode("ascii") in prompt
    assert b"gh api --method GET repos/example/product/issues/12" in prompt


def test_build_prompt_tells_the_holder_to_post_the_builder_session_marker():
    prompt = work._stage_prompt(
        state(AFFIRMED), work.Decision("build", True, "fresh", "fixture")
    )
    assert b"<!-- tradecraft:builder-session:v1 session=SESSION -->" in prompt


def test_mechanical_build_prompt_names_the_lane_reason_and_omits_an_old_artifact():
    obsolete = ARTIFACT + "\nOBSOLETE ARTIFACT\n"
    prompt = work._stage_prompt(
        state(MECHANICAL, obsolete), work.Decision("build", True, "fresh", "fixture")
    )
    evidence = json.loads(prompt.split(b"\n\n")[1])

    assert evidence["review_lane"] == "mechanical"
    assert "skips the artifact, cold seat, and use" in evidence["lane_reason"]
    assert MECHANICAL.encode("ascii") in prompt
    assert b"OBSOLETE ARTIFACT" not in prompt


def test_mechanical_explicit_artifact_prompt_keeps_the_draft_and_names_its_authority():
    draft = ARTIFACT + "\nMECHANICAL DRAFT\n"
    prompt = work._stage_prompt(
        state(MECHANICAL, draft), work.Decision("artifact", True, "resume", "fixture")
    )
    evidence = json.loads(prompt.split(b"\n\n")[1])

    assert b"MECHANICAL DRAFT" in prompt
    assert evidence["lane_reason"] == (
        "holder-explicit artifact stage remains authoritative for the owner-affirmed "
        "mechanical lane and advances no later stage"
    )


def test_connected_build_prompt_keeps_its_artifact_and_has_no_lane_exception():
    artifact = ARTIFACT + "\nCONNECTED ARTIFACT\n"
    settled = """<!-- tradecraft:artifact:v1 status=settled route=would -->
CONNECTED ARTIFACT
<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=qualified -->"""
    prompt = work._stage_prompt(
        state(AFFIRMED, artifact, settled),
        work.Decision("build", True, "fresh", "fixture")
    )
    evidence = json.loads(prompt.split(b"\n\n")[1])

    assert b"CONNECTED ARTIFACT" in prompt
    assert evidence["lane_reason"] is None


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


@pytest.mark.parametrize("lane", ["connected", "mechanical"])
def test_explicit_cold_seat_prompt_carries_artifact_brief_and_check_contract(tmp_path, lane):
    brief = AFFIRMED.replace("connected", lane) + "Brief text visible only to the cold seat.\n"
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
    monkeypatch.setattr(work, "_producer_vendor", lambda *_a, **_k: ("codex", "artifact bundle"))
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
        "requested": {"vendor": "codex"},
    }), encoding="utf-8")
    run.write_text(json.dumps({
        "schema_version": run_schema,
        "actual_vendor": "codex",
        "outcome": outcome,
        "completed_at": completed_at,
        "attempts": ([] if session is None else [{"observed": {"session_id": session}}]),
    }), encoding="utf-8")


@pytest.mark.parametrize("merge", [False, True])
def test_use_producer_vendor_accepts_later_commit_or_merge_descendant(tmp_path, merge):
    source = repository(tmp_path, "source")
    if merge:
        base_branch = git(source, "symbolic-ref", "--short", "HEAD").stdout.decode().strip()
        git(source, "switch", "-c", "builder")
    (source / "built.txt").write_bytes(b"built\n")
    git(source, "add", "built.txt")
    git(source, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "builder result")
    producer = git(source, "rev-parse", "HEAD").stdout.decode().strip()
    if merge:
        git(source, "switch", base_branch)
    (source / "later.txt").write_bytes(b"later\n")
    git(source, "add", "later.txt")
    git(source, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "later source")
    unrelated = git(source, "rev-parse", "HEAD").stdout.decode().strip()
    if merge:
        git(source, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
            "merge", "--no-ff", "builder", "-m", "landed merge")
    tree_revision = git(source, "rev-parse", "HEAD").stdout.decode().strip()

    fixture = state(AFFIRMED, pr=True)
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root)
    run_path = fixture.record_root / "build" / "result.md.run.json"
    run = json.loads(run_path.read_bytes())
    run["revision_after"] = producer
    run_path.write_bytes(json.dumps(run).encode())

    vendor, path = work._producer_vendor(
        fixture, work.RESUME_SOURCE_STAGES["build"],
        revision=tree_revision, source_root=source,
    )
    assert vendor == "codex"
    assert path == str(run_path)
    if merge:
        with pytest.raises(work.WorkError, match="no implementation bundle proves"):
            work._producer_vendor(
                fixture, work.RESUME_SOURCE_STAGES["build"],
                revision=unrelated, source_root=source,
            )


def test_use_producer_vendor_follows_a_squash_merge_through_the_pr_head(tmp_path):
    source = repository(tmp_path, "source")
    base_branch = git(source, "symbolic-ref", "--short", "HEAD").stdout.decode().strip()
    git(source, "switch", "-c", "builder")
    (source / "built.txt").write_bytes(b"built\n")
    git(source, "add", "built.txt")
    git(source, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "builder result")
    producer = git(source, "rev-parse", "HEAD").stdout.decode().strip()
    (source / "later.txt").write_bytes(b"later\n")
    git(source, "add", "later.txt")
    git(source, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "PR head")
    pr_head = git(source, "rev-parse", "HEAD").stdout.decode().strip()
    git(source, "switch", base_branch)
    git(source, "merge", "--squash", "builder")
    git(source, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "landed squash")
    merge_commit = git(source, "rev-parse", "HEAD").stdout.decode().strip()
    (source / "subsequent.txt").write_bytes(b"later source\n")
    git(source, "add", "subsequent.txt")
    git(source, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "later source")
    tree_revision = git(source, "rev-parse", "HEAD").stdout.decode().strip()

    fixture = state(AFFIRMED, pr=True)
    fixture.pr["head"]["sha"] = pr_head
    fixture.pr["merge_commit_sha"] = merge_commit
    fixture.pr["merged_at"] = "2026-09-29T12:00:00Z"
    fixture.merged_pr = fixture.pr
    fixture.pr = None
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root)
    run_path = fixture.record_root / "build" / "result.md.run.json"
    run = json.loads(run_path.read_bytes())
    run["revision_after"] = producer
    run_path.write_bytes(json.dumps(run).encode())

    assert work._producer_vendor(
        fixture, work.RESUME_SOURCE_STAGES["build"],
        revision=tree_revision, source_root=source,
    ) == ("codex", str(run_path))


def test_use_producer_vendor_stays_with_its_pull_request_branch(tmp_path):
    source = repository(tmp_path, "source")
    producer = git(source, "rev-parse", "HEAD").stdout.decode().strip()
    (source / "later.txt").write_bytes(b"later\n")
    git(source, "add", "later.txt")
    git(source, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "later source")
    tree_revision = git(source, "rev-parse", "HEAD").stdout.decode().strip()
    fixture = state(AFFIRMED, pr=True)
    fixture.pr["head"]["ref"] = "tradecraft/current"
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root, name="current.md")
    dispatch_bundle(fixture.record_root, name="other.md",
                    completed_at="2026-09-20T11:00:00+00:00")
    for name, branch, vendor in (
            ("current.md", "tradecraft/current", "codex"),
            ("other.md", "tradecraft/other", "claude")):
        request_path = fixture.record_root / "build" / f"{name}.request.json"
        run_path = fixture.record_root / "build" / f"{name}.run.json"
        request = json.loads(request_path.read_bytes())
        request["lineage_branch"] = branch
        request["requested"]["vendor"] = vendor
        request_path.write_bytes(json.dumps(request).encode())
        run = json.loads(run_path.read_bytes())
        run["revision_after"] = producer
        run["actual_vendor"] = vendor
        run_path.write_bytes(json.dumps(run).encode())

    assert work._producer_vendor(
        fixture, work.RESUME_SOURCE_STAGES["build"],
        revision=tree_revision, source_root=source,
    ) == ("codex", str(fixture.record_root / "build" / "current.md.run.json"))


def test_bundle_backed_builder_marker_must_match_the_observed_session(tmp_path):
    marker = f"<!-- tradecraft:builder-session:v1 session={SESSION} -->"
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, marker)
    fixture.issue_comments[2]["created_at"] = "2026-09-20T09:00:00Z"
    fixture.issue_comments[3]["created_at"] = "2026-09-20T09:30:00Z"
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


def test_proof_marks_missing_bundle_unverifiable_instead_of_copying_qualified(tmp_path):
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE, pr=True)
    fixture.record_root = tmp_path / "missing-dispatches"
    fixture.policy_sources = {
        "work_configuration": {
            "repository": fixture.repo, "path": ".tradecraft/work.json",
            "revision": SHA, "sha256": "1" * 64,
        },
        "use_rules": {
            "repository": fixture.repo, "path": POLICY_PATH,
            "revision": SHA, "sha256": "2" * 64,
        },
    }
    work.prepare_use_evidence(fixture, AncestryTransport(SHA, SHA, {}), RULES)

    composed = work.compose_proof(fixture, RULES)
    declarations = {item["stage"]: item for item in composed["declarations"]}
    assert declarations["floor"]["status"] == "unverifiable"
    assert declarations["use"]["status"] == "unverifiable"
    assert declarations["use"]["staffing_status"] is None
    assert "no matching successful dispatch bundle" in declarations["use"]["reason"]


def test_mechanical_proof_is_generated_from_the_affirmed_comment_even_for_use_paths(tmp_path):
    fixture = state(MECHANICAL, FLOOR, pr=True, paths=["lib/runtime.py"])
    fixture.issue_comments[0].update({
        "id": 41,
        "html_url": "https://github.example/issues/12#issuecomment-41",
        "created_at": "2026-09-23T12:00:00Z",
    })
    fixture.record_root = tmp_path / "dispatches"
    fixture.policy_sources = {
        "work_configuration": {
            "repository": fixture.repo, "path": ".tradecraft/work.json",
            "revision": SHA, "sha256": "1" * 64,
        },
        "use_rules": {
            "repository": fixture.repo, "path": POLICY_PATH,
            "revision": SHA, "sha256": "2" * 64,
        },
    }
    work.validate_marker_claims(fixture)

    composed = work.compose_proof(fixture, RULES)

    assert composed["use"] == {
        "required": False,
        "classification": "not-required",
        "evidence_head": SHA,
        "applicability": "generated",
        "source": {
            "kind": "issue-comment", "repository": "example/product", "id": 41,
            "url": "https://github.example/issues/12#issuecomment-41",
            "author": PRODUCER, "timestamp": "2026-09-23T12:00:00Z",
            "revision": None,
        },
        "intervening_commits": [],
        "reason": work.MECHANICAL_USE_REASON,
    }
    assert all(item["stage"] != "use" for item in composed["declarations"])


def test_non_mechanical_generated_proof_has_no_affirmed_source(tmp_path):
    fixture = state(AFFIRMED, FLOOR, pr=True, paths=["README.md"])
    fixture.issue_comments[0].update({
        "id": 42,
        "html_url": "https://github.example/issues/12#issuecomment-42",
        "created_at": "2026-09-23T12:01:00Z",
    })
    fixture.record_root = tmp_path / "dispatches"
    fixture.policy_sources = {
        "work_configuration": {
            "repository": fixture.repo, "path": ".tradecraft/work.json",
            "revision": SHA, "sha256": "1" * 64,
        },
        "use_rules": {
            "repository": fixture.repo, "path": POLICY_PATH,
            "revision": SHA, "sha256": "2" * 64,
        },
    }
    work.validate_marker_claims(fixture)

    composed = work.compose_proof(fixture, RULES)

    assert composed["use"]["required"] is False
    assert composed["use"]["source"] is None
    assert composed["use"]["reason"] == work.PATH_NO_USE_REASON


def test_mechanical_readiness_without_generated_no_use_is_refused():
    fixture = state(MECHANICAL, FLOOR, pr=True)
    work.validate_marker_claims(fixture)

    assert work._ready_evidence_error(fixture, RULES) == (
        "ready-reviewers requires run proof to generate the current-head no-use carrier"
    )


def test_mechanical_readiness_requires_generated_no_use_not_a_use_bundle():
    fixture = state(
        MECHANICAL, FLOOR,
        f"<!-- tradecraft:no-use:v1 head={SHA} -->\nUse: not required - mechanical.",
        pr=True,
    )
    work.validate_marker_claims(fixture)

    assert work._ready_evidence_error(fixture, RULES) is None


@pytest.mark.parametrize(("brief", "paths", "expected_reason"), [
    (MECHANICAL, ["lib/runtime.py"], work.MECHANICAL_USE_REASON),
    (AFFIRMED, ["README.md"], work.PATH_NO_USE_REASON),
])
def test_execute_proof_compatibility_line_uses_the_composed_lane_or_path_reason(
        tmp_path, monkeypatch, capsys, brief, paths, expected_reason):
    root = policy_repository(tmp_path)
    fixture = state(brief, FLOOR, pr=True, paths=paths)
    fixture.issue_comments[0].update({
        "id": 41,
        "html_url": "https://github.example/issues/12#issuecomment-41",
        "created_at": "2026-09-23T12:00:00Z",
    })
    fixture.record_root = tmp_path / "dispatches"
    work.validate_marker_claims(fixture)
    published = []

    class CurrentHeadTransport:
        def get(self, endpoint, *, paginate=False):
            assert endpoint == "repos/example/product/pulls/7"
            assert paginate is False
            return fixture.pr

    monkeypatch.setattr(work, "read_state", lambda *_args, **_kwargs: fixture)
    monkeypatch.setattr(work, "prepare_use_evidence", lambda *_args: None)
    monkeypatch.setattr(
        work, "_publish_proof_comment",
        lambda _transport, _state, body, _head: (
            published.append(body) or {"action": "created", "id": 91, "url": "fixture"}
        ),
    )
    monkeypatch.setattr(work, "_rerun_gate_evaluations", lambda *_args: [])

    assert work._execute_proof(
        CurrentHeadTransport(), fixture, root, RULES, root / ".github" / "change-proof.json",
        None, None,
    ) == 0
    capsys.readouterr()

    assert len(published) == 1
    assert f"Use: not required - {expected_reason}." in published[0]


@pytest.mark.parametrize(("override", "invalid_override"), [
    ("<!-- tradecraft:model-override:v1 ordinary_seat=claude:claude-owner:high -->", False),
    ("<!-- tradecraft:model-override:v1 mystery=claude:claude-owner:high -->", True),
])
def test_proof_does_not_credit_no_output_or_model_override_claims(
        tmp_path, override, invalid_override):
    fixture = state(AFFIRMED, FLOOR, override, pr=True, paths=["README.md"])
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root, stage="floor", outcome="completed_no_output")
    fixture.policy_sources = {
        "work_configuration": {
            "repository": fixture.repo, "path": ".tradecraft/work.json",
            "revision": SHA, "sha256": "1" * 64,
        },
        "use_rules": {
            "repository": fixture.repo, "path": POLICY_PATH,
            "revision": SHA, "sha256": "2" * 64,
        },
    }
    work.validate_marker_claims(fixture)

    composed = work.compose_proof(fixture, RULES)
    declarations = {item["stage"]: item for item in composed["declarations"]}
    diagnostic_messages = [item["message"] for item in composed["diagnostics"]]

    assert declarations["floor"]["status"] == "unverifiable"
    assert declarations["floor"]["dispatch_id"] is None
    assert all(item["stage"] != "model-override" for item in composed["declarations"])
    assert any(message.startswith("floor marker:") for message in diagnostic_messages)
    assert any(message.startswith("model-override marker:")
               for message in diagnostic_messages) is invalid_override


class ProofCommentTransport:
    def __init__(self, comments=()):
        self.comments = list(comments)
        self.mutations = []

    def get(self, endpoint, *, paginate=False):
        if endpoint == "user":
            return {"login": PRODUCER}
        if endpoint.endswith("/issues/7/comments"):
            return self.comments
        raise KeyError(endpoint)

    def post(self, endpoint, payload):
        self.mutations.append(("POST", endpoint))
        item = {
            "id": 90 + len(self.comments), "body": payload["body"],
            "html_url": "https://github.example/proof", "user": {"login": PRODUCER},
        }
        self.comments.append(item)
        return item

    def patch(self, endpoint, payload):
        self.mutations.append(("PATCH", endpoint))
        identity = int(endpoint.rsplit("/", 1)[1])
        item = next(record for record in self.comments if record["id"] == identity)
        item["body"] = payload["body"]
        return item


def test_proof_publication_creates_once_and_is_idempotent():
    fixture = state(AFFIRMED, pr=True)
    body = f"<!-- tradecraft:proof:v1 head={SHA} -->\nproof\n"
    transport = ProofCommentTransport()

    first = work._publish_proof_comment(transport, fixture, body, SHA)
    fixture.pr_comments = transport.comments
    second = work._publish_proof_comment(transport, fixture, body, SHA)

    assert first["action"] == "created"
    assert second["action"] == "unchanged"
    assert [method for method, _endpoint in transport.mutations] == ["POST"]


def test_proof_publication_refuses_competing_authorized_documents():
    comments = [
        {"id": 1, "body": f"<!-- tradecraft:proof:v1 head={SHA} -->\none",
         "user": {"login": PRODUCER}},
        {"id": 2, "body": f"<!-- tradecraft:proof:v1 head={SHA} -->\ntwo",
         "user": {"login": PRODUCER}},
    ]
    fixture = state(AFFIRMED, pr=True)
    fixture.pr_comments = comments
    with pytest.raises(work.WorkError, match="conflicting authorized proof"):
        work._publish_proof_comment(
            ProofCommentTransport(comments), fixture, comments[0]["body"], SHA
        )


@pytest.mark.parametrize("autocrlf", ["true", "false"])
def test_policy_snapshot_hashes_committed_blobs_across_checkout_line_endings(
        tmp_path, autocrlf):
    root = policy_repository(tmp_path, f"policy-{autocrlf}", autocrlf=autocrlf)

    snapshot = work._capture_policy_snapshot(
        root, "example/product", root / ".github" / "change-proof.json",
        enforce_clean=True,
    )

    for name, relative in snapshot.paths.items():
        expected = git(root, "show", f"HEAD:{relative}").stdout
        assert snapshot.blobs[name] == expected
        assert snapshot.sources[name]["sha256"] == hashlib.sha256(expected).hexdigest()
    assert git(root, "status", "--porcelain").stdout == b""


def test_policy_snapshot_preserves_committed_crlf_bytes(tmp_path):
    root = policy_repository(tmp_path, crlf=True)
    snapshot = work._capture_policy_snapshot(
        root, "example/product", root / ".github" / "change-proof.json",
        enforce_clean=True,
    )
    committed = git(root, "show", f"HEAD:{POLICY_PATH}").stdout
    assert b"\r\n" in committed
    assert snapshot.blobs["use_rules"] == committed
    assert snapshot.sources["use_rules"]["sha256"] == hashlib.sha256(committed).hexdigest()


@pytest.mark.parametrize("autocrlf", ["true", "false"])
def test_default_proof_names_and_hashes_committed_repository_policy(
        tmp_path, monkeypatch, capsys, autocrlf):
    root = policy_repository(tmp_path, autocrlf=autocrlf)
    fixture = state(AFFIRMED, pr=True)
    fixture.record_root = tmp_path / "dispatches"
    published = []

    class CurrentHeadTransport:
        def get(self, endpoint, *, paginate=False):
            assert endpoint == "repos/example/product/pulls/7"
            assert paginate is False
            return fixture.pr

    monkeypatch.setattr(work, "read_state", lambda *_args, **_kwargs: fixture)
    monkeypatch.setattr(
        work, "_publish_proof_comment",
        lambda _transport, _state, body, _head: (
            published.append(body) or {"action": "created", "id": 91, "url": "fixture"}
        ),
    )
    args = work.parser().parse_args([
        "run", "proof", "--repo", fixture.repo, "--issue", "12", "--root", str(root),
    ])

    assert work.run(args, transport=CurrentHeadTransport()) == 0
    assert json.loads(capsys.readouterr().out)["stage"] == "proof"
    assert len(published) == 1
    composed = json.loads(published[0].split("```json\n", 1)[1].split("\n```", 1)[0])
    committed = git(root, "show", f"HEAD:{POLICY_PATH}").stdout
    revision = git(root, "rev-parse", "HEAD").stdout.decode().strip()
    assert composed["policy"]["use_rules"] == {
        "repository": fixture.repo, "path": POLICY_PATH, "revision": revision,
        "sha256": hashlib.sha256(committed).hexdigest(),
    }
    assert composed["use"]["required"] is True
    if autocrlf == "true":
        assert (root / POLICY_PATH).read_bytes() != committed


def _dirty_policy(root, condition):
    target = root / ".github" / "change-proof.json"
    if condition == "unstaged":
        target.write_bytes(USE_RULES_BYTES + b" ")
        return POLICY_PATH
    if condition == "staged":
        target.write_bytes(USE_RULES_BYTES + b" ")
        git(root, "add", POLICY_PATH)
        return POLICY_PATH
    if condition == "staged-restored":
        target.write_bytes(USE_RULES_BYTES + b" ")
        git(root, "add", POLICY_PATH)
        target.write_bytes(USE_RULES_BYTES)
        return POLICY_PATH
    if condition == "deleted":
        target.unlink()
        return POLICY_PATH
    if condition == "renamed":
        git(root, "mv", POLICY_PATH, RENAMED_POLICY_PATH)
        return POLICY_PATH
    if condition == "conflicted":
        branch = git(root, "branch", "--show-current").stdout.decode().strip()
        git(root, "checkout", "-b", "policy-side")
        target.write_bytes(b"side\n")
        git(root, "add", POLICY_PATH)
        git(
            root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
            "commit", "-m", "side",
        )
        git(root, "checkout", branch)
        target.write_bytes(b"base\n")
        git(root, "add", POLICY_PATH)
        git(
            root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
            "commit", "-m", "base",
        )
        merge = git(
            root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
            "merge", "--no-edit", "policy-side", check=False,
        )
        assert merge.returncode != 0
        assert git(
            root, "ls-files", "-u", "--", POLICY_PATH
        ).stdout, (merge.stdout + merge.stderr).decode(errors="replace")
        return POLICY_PATH
    raise AssertionError(condition)


@pytest.mark.parametrize(
    "condition",
    ["unstaged", "staged", "staged-restored", "deleted", "renamed", "conflicted"],
)
def test_dirty_tracked_policy_refuses_proof_before_any_github_request(
        tmp_path, condition):
    root = policy_repository(tmp_path, f"dirty-{condition}")
    relative = _dirty_policy(root, condition)

    class NoGitHub:
        def __init__(self):
            self.calls = []

        def get(self, endpoint, *, paginate=False):
            self.calls.append((endpoint, paginate))
            raise AssertionError("proof reached GitHub before policy refusal")

    transport = NoGitHub()
    args = work.parser().parse_args([
        "run", "proof", "--repo", "example/product", "--issue", "3",
        "--root", str(root),
    ])
    refusal = (
        "change-proof policy is missing" if condition in {"deleted", "renamed"}
        else "commit or revert"
    )
    with pytest.raises(work.WorkError, match=refusal) as raised:
        work.run(args, transport=transport)
    assert relative in str(raised.value).replace("\\", "/")
    assert transport.calls == []


@pytest.mark.parametrize("policy_name", ["work_configuration", "use_rules"])
def test_untracked_policy_refuses_proof_before_any_github_request(tmp_path, policy_name):
    root = policy_repository(
        tmp_path, f"untracked-{policy_name}", work_configuration=policy_name != "work_configuration"
    )
    if policy_name == "work_configuration":
        target = root / ".tradecraft" / "work.json"
        target.write_bytes(WORK_CONFIG_BYTES)
    else:
        target = root / ".github" / "change-proof.json"
        git(root, "rm", POLICY_PATH)
        git(
            root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
            "commit", "-m", "remove use policy",
        )
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(USE_RULES_BYTES)

    class NoGitHub:
        def get(self, endpoint, *, paginate=False):
            raise AssertionError("proof reached GitHub before policy refusal")

    with pytest.raises(work.WorkError, match="commit or revert") as raised:
        work._execute_proof(
            NoGitHub(), state(pr=True), root, RULES, root / ".github" / "change-proof.json",
            None, None,
        )
    assert target.relative_to(root).as_posix() in str(raised.value)


def test_gitignored_policy_refuses_proof_before_any_github_request(tmp_path):
    root = policy_repository(tmp_path, "ignored-work-policy", work_configuration=False)
    (root / ".gitignore").write_text(".tradecraft/work.json\n")
    git(root, "add", ".gitignore")
    git(
        root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "ignore local work config",
    )
    target = root / ".tradecraft" / "work.json"
    target.write_bytes(WORK_CONFIG_BYTES)

    class NoGitHub:
        def get(self, endpoint, *, paginate=False):
            raise AssertionError("proof reached GitHub before policy refusal")

    with pytest.raises(work.WorkError, match="commit or revert") as raised:
        work._execute_proof(
            NoGitHub(), state(pr=True), root, RULES, root / ".github" / "change-proof.json",
            None, None,
        )
    assert ".tradecraft/work.json" in str(raised.value)


def test_absent_optional_work_configuration_keeps_unavailable_source(tmp_path):
    root = policy_repository(tmp_path, work_configuration=False)
    snapshot = work._capture_policy_snapshot(
        root, "example/product", root / ".github" / "change-proof.json",
        enforce_clean=True,
    )
    assert snapshot.blobs["work_configuration"] is None
    assert snapshot.sources["work_configuration"] == {
        "repository": "example/product", "path": ".tradecraft/work.json",
        "revision": snapshot.revision, "sha256": "unavailable",
    }
    assert work._work_config_bytes(None, ".tradecraft/work.json") == work.WorkConfig()


def test_policy_snapshot_ignores_unrelated_dirty_files_and_refuses_outside_policy(
        tmp_path):
    root = policy_repository(tmp_path)
    (root / "unrelated.txt").write_bytes(b"dirty\n")
    snapshot = work._capture_policy_snapshot(
        root, "example/product", root / ".github" / "change-proof.json",
        enforce_clean=True,
    )
    assert snapshot.problems == ()

    outside = tmp_path / "outside-rules.json"
    outside.write_bytes(USE_RULES_BYTES)
    with pytest.raises(work.WorkError, match="outside the holder checkout"):
        work._capture_policy_snapshot(
            root, "example/product", outside, enforce_clean=True
        )


def test_run_refuses_root_below_the_repository_top_level(tmp_path):
    root = policy_repository(tmp_path)
    nested = root / "nested"
    nested.mkdir()
    args = work.parser().parse_args([
        "--repo", "example/product", "--issue", "3", "--root", str(nested),
        "--use-rules", str(root / ".github" / "change-proof.json"),
    ])

    with pytest.raises(work.WorkError, match="repository top level"):
        work.run(args, transport=object())


def test_ordinary_read_uses_worktree_policy_while_reporting_dirtiness(
        tmp_path, monkeypatch, capsys):
    root = policy_repository(tmp_path)
    worktree_rules = {
        "schema_version": 1,
        "rules": [{
            "name": "worktree", "include": ["/".join(("docs", "**"))], "exclude": [],
        }],
    }
    (root / ".github" / "change-proof.json").write_text(json.dumps(worktree_rules))
    args = work.parser().parse_args([
        "--repo", "example/product", "--issue", "3", "--root", str(root),
    ])
    observed = {}

    class MinimalTransport:
        def get(self, endpoint, *, paginate=False):
            if endpoint.endswith("/comments") or "/pulls?" in endpoint:
                return []
            return {"number": 3, "state": "open", "body": "", "labels": [],
                    "user": {"login": PRODUCER}}

    original_decide = work.decide

    def capturing_decide(fixture, rules):
        observed["rules"] = rules
        observed["diagnostics"] = fixture.collection_diagnostics
        return original_decide(fixture, rules)

    monkeypatch.setattr(work, "decide", capturing_decide)
    assert work.run(args, transport=MinimalTransport()) == 0
    capsys.readouterr()
    assert observed["rules"] == worktree_rules
    assert any(item["code"] == "policy-uncommitted"
               for item in observed["diagnostics"])


@pytest.mark.parametrize("ignored", [False, True])
def test_ordinary_read_keeps_uncommitted_work_configuration(ignored, tmp_path, monkeypatch,
                                                            capsys):
    root = policy_repository(tmp_path, work_configuration=False)
    if ignored:
        (root / ".gitignore").write_text(".tradecraft/work.json\n")
        git(root, "add", ".gitignore")
        git(
            root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
            "commit", "-m", "ignore local work config",
        )
    local_config = {
        "schema_version": 1,
        "product_repositories": ["example/product"],
        "connected_reviewers": [],
        "marker_producers": ["local-holder"],
    }
    (root / ".tradecraft" / "work.json").write_text(json.dumps(local_config))
    captured = {}

    def read_state(_transport, repo, issue, config):
        captured["config"] = config
        fixture = work.WorkState(
            repo, issue,
            {"number": issue, "state": "open", "body": "", "labels": [],
             "user": {"login": "local-holder"}},
            config=config,
        )
        captured["state"] = fixture
        return fixture

    monkeypatch.setattr(work, "read_state", read_state)
    args = work.parser().parse_args([
        "--repo", "example/product", "--issue", "3", "--root", str(root),
    ])

    assert work.run(args, transport=object()) == 0
    capsys.readouterr()
    assert captured["config"].marker_producers == frozenset({"local-holder"})
    assert any(item["code"] == "policy-uncommitted"
               for item in captured["state"].collection_diagnostics)


def test_dirty_use_policy_does_not_change_proof_freshness_composition(
        tmp_path, monkeypatch, capsys):
    root = policy_repository(tmp_path)
    fixture = state(FLOOR, USE, pr=True)
    snapshot = work._capture_policy_snapshot(
        root, "example/product", root / ".github" / "change-proof.json",
        enforce_clean=True,
    )
    fixture.record_root = work.records.default_record_root().expanduser().resolve()
    fixture.policy_sources = snapshot.sources
    committed_rules = json.loads(USE_RULES_BYTES)
    work.prepare_use_evidence(fixture, object(), committed_rules)
    assert fixture.applicable_use is not None
    current = work.compose_proof(fixture, committed_rules)
    fixture.pr_comments.append({
        "id": 71,
        "body": work.proof_document.document(current, None),
        "user": {"login": PRODUCER},
    })
    worktree_rules = {
        "schema_version": 1,
        "rules": [{
            "name": "worktree", "include": ["/".join(("docs", "**"))], "exclude": [],
        }],
    }
    (root / ".github" / "change-proof.json").write_text(json.dumps(worktree_rules))

    monkeypatch.setattr(work, "read_state", lambda *_args, **_kwargs: fixture)
    args = work.parser().parse_args([
        "--repo", "example/product", "--issue", "3", "--root", str(root),
    ])

    assert work.run(args, transport=object()) == 0
    capsys.readouterr()
    assert fixture.proof_current is True
    assert fixture.applicable_use is None
    assert any(item["code"] == "policy-uncommitted"
               for item in fixture.collection_diagnostics)


def test_policy_change_between_composition_and_publication_refuses_before_write(
        tmp_path, monkeypatch):
    root = policy_repository(tmp_path)
    fixture = state(pr=True)
    published = []

    monkeypatch.setattr(work, "read_state", lambda *_args, **_kwargs: fixture)
    monkeypatch.setattr(work, "prepare_use_evidence", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(work, "compose_proof", lambda *_args, **_kwargs: {
        "identity": {"head": SHA, "pull_request": 7},
        "use": {"required": True},
    })
    monkeypatch.setattr(work.proof_document, "document", lambda *_args: "proof")
    monkeypatch.setattr(
        work, "_publish_proof_comment",
        lambda *_args, **_kwargs: published.append(True),
    )

    class RacingTransport:
        def get(self, endpoint, *, paginate=False):
            assert endpoint == "repos/example/product/pulls/7"
            (root / ".github" / "change-proof.json").write_bytes(USE_RULES_BYTES + b" ")
            return fixture.pr

    with pytest.raises(work.WorkError, match="commit or revert"):
        work._execute_proof(
            RacingTransport(), fixture, root, RULES, root / ".github" / "change-proof.json",
            None, None,
        )
    assert published == []


def test_policy_change_during_publication_reports_the_posted_earlier_state(
        tmp_path, monkeypatch):
    root = policy_repository(tmp_path)
    fixture = state(pr=True)
    published = []

    monkeypatch.setattr(work, "read_state", lambda *_args, **_kwargs: fixture)
    monkeypatch.setattr(work, "prepare_use_evidence", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(work, "compose_proof", lambda *_args, **_kwargs: {
        "identity": {"head": SHA, "pull_request": 7},
        "use": {"required": True},
    })
    monkeypatch.setattr(work.proof_document, "document", lambda *_args: "proof")

    def publish(*_args, **_kwargs):
        published.append(True)
        (root / ".github" / "change-proof.json").write_bytes(USE_RULES_BYTES + b" ")
        return {"action": "created", "id": 1, "url": "https://example.test/proof"}

    monkeypatch.setattr(work, "_publish_proof_comment", publish)

    class RacingTransport:
        def get(self, endpoint, *, paginate=False):
            assert endpoint == "repos/example/product/pulls/7"
            return fixture.pr

    with pytest.raises(work.WorkError, match="posted for the earlier policy state") as raised:
        work._execute_proof(
            RacingTransport(), fixture, root, RULES, root / ".github" / "change-proof.json",
            None, None,
        )
    assert "completion is not current" in str(raised.value)
    assert "before publication" not in str(raised.value)
    assert published == [True]


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


@pytest.mark.parametrize(("stage", "mechanism"), [
    ("artifact", "explicit launch settings"),
    ("cold-seat", "explicit launch settings"),
    ("build", "explicit launch settings"),
    ("floor", "explicit launch settings"),
    ("use", "landed consumer-tree use"),
    ("review-disposition", "explicit launch settings"),
])
def test_truthful_entrance_launches_require_0_154_before_side_effects(
        tmp_path, monkeypatch, capsys, stage, mechanism):
    monkeypatch.setattr(work.records, "producer_version", lambda: "0.153.0")
    monkeypatch.setattr(
        work, "_dispatch_root",
        lambda *_args, **_kwargs: pytest.fail("unsafe version must refuse before root access"),
    )
    decision = work.Decision(stage, True, "fresh", "holder-named-stage")

    assert work.execute_stage(state(AFFIRMED), decision, tmp_path, None, "holder") == 0

    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == f"unsafe-running-version-for-{stage}"
    assert "required=0.154.0" in report["detail"]
    assert f"mechanism={mechanism}" in report["detail"]


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


@pytest.mark.parametrize("outcome", ["invalid_artifact_return", "completed_no_output"])
def test_artifact_review_amendment_starts_a_fresh_author(tmp_path, outcome):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="artifact", outcome=outcome)
    fixture = state(AFFIRMED, AFFIRMED + "Amended whole brief.\n")
    fixture.issue_comments[0]["created_at"] = "2026-09-19T00:00:00Z"
    fixture.issue_comments[1]["created_at"] = "2026-09-21T00:00:00Z"
    fixture.record_root = store
    recommendation = work.decide(fixture, RULES)
    assert recommendation.continuity == "fresh"
    assert work._named_continuity(fixture, "artifact", recommendation) == "fresh"


@pytest.mark.parametrize("outcome", ["success", "success_uncontinuable", "error"])
@pytest.mark.parametrize("session", [SESSION, None])
def test_artifact_review_current_nonfailure_keeps_the_recommendation(tmp_path, outcome, session):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="artifact", outcome=outcome, session=session)
    fixture = state(AFFIRMED)
    fixture.issue_comments[0]["created_at"] = "2026-09-19T00:00:00Z"
    fixture.record_root = store
    recommendation = work.decide(fixture, RULES)
    assert recommendation.continuity == "fresh"
    assert work._named_continuity(fixture, "artifact", recommendation) == "fresh"
    resumed = work.Decision("artifact", True, "resume", "artifact-repair")
    assert work._named_continuity(fixture, "artifact", resumed) == "resume"


@pytest.mark.parametrize("kind", ["old-request", "old-run", "unreadable"])
@pytest.mark.parametrize("current_failure", [False, True])
def test_artifact_review_legacy_bundle_does_not_invalidate_a_draft(tmp_path, kind, current_failure):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="artifact", name="legacy.md",
                    request_schema=1 if kind == "old-request" else 2,
                    run_schema=1 if kind == "old-run" else 2)
    if kind == "unreadable":
        (store / "artifact" / "legacy.md.run.json").write_bytes(b"not JSON")
    if current_failure:
        dispatch_bundle(store, stage="artifact", name="failed.md", outcome="invalid_artifact_return",
                        completed_at="2026-09-21T00:00:00Z")
    fixture = state(AFFIRMED, ARTIFACT)
    fixture.issue_comments[0]["created_at"] = "2026-09-19T00:00:00Z"
    fixture.issue_comments[1]["created_at"] = "2026-09-22T00:00:00Z"
    fixture.record_root = store
    before = {path: path.read_bytes() for path in store.rglob("*.json")}
    lawful, invalid = work.validate_marker_claims(fixture)
    assert any(marker.name == "artifact" for marker in lawful) == (not current_failure)
    if current_failure:
        assert "failed.md.run.json" in next(claim["reason"] for claim in invalid if claim["name"] == "artifact")
    else:
        assert not invalid
    assert before == {path: path.read_bytes() for path in before}


def test_artifact_review_previous_term_failure_cannot_withhold_current_draft(tmp_path):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="artifact", outcome="invalid_artifact_return")
    fixture = state(AFFIRMED, ARTIFACT)
    fixture.issue_comments[0]["created_at"] = "2026-09-21T00:00:00Z"
    fixture.issue_comments[1]["created_at"] = "2026-09-22T00:00:00Z"
    fixture.record_root = store
    lawful, invalid = work.validate_marker_claims(fixture)
    assert any(marker.name == "artifact" for marker in lawful)
    assert not invalid


@pytest.mark.parametrize("outcome", ["success", "success_uncontinuable", "completed_no_output"])
def test_historical_artifact_records_are_not_revalidated(tmp_path, outcome):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="artifact", outcome=outcome)
    fixture = state(AFFIRMED, ARTIFACT)
    fixture.record_root = store
    before = {path: path.read_bytes() for path in store.rglob("*.json")}
    lawful, invalid = work.validate_marker_claims(fixture)
    assert any(marker.name == "artifact" for marker in lawful)
    assert not invalid
    assert work.resume_session(fixture, "artifact", store) == SESSION
    assert before == {path: path.read_bytes() for path in before}


@pytest.mark.parametrize("outcome", ["invalid_artifact_return", "completed_no_output"])
def test_successful_artifact_recovery_supplies_marker_credit(tmp_path, outcome):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="artifact", name="failed.md", outcome=outcome)
    failed_path = store / "artifact" / "failed.md.run.json"
    failed = json.loads(failed_path.read_bytes())
    failed["result"] = {"return_validation": {"status": "fail"}}
    failed_path.write_bytes(json.dumps(failed).encode())
    dispatch_bundle(store, stage="artifact", name="recovered.md", session=OTHER_SESSION,
                    completed_at="2026-09-21T10:00:00+00:00")
    fixture = state(AFFIRMED, ARTIFACT)
    fixture.record_root = store
    before = failed_path.read_bytes()
    successful = work._matching_bundles("example/product#12", {"artifact"}, store)
    assert len(successful) == 1
    assert successful[0][1].endswith("recovered.md.run.json")
    lawful, invalid = work.validate_marker_claims(fixture)
    assert any(marker.name == "artifact" for marker in lawful)
    assert not invalid
    assert work.resume_session(fixture, "artifact", store) == OTHER_SESSION
    assert failed_path.read_bytes() == before


@pytest.mark.parametrize("outcome", ["invalid_artifact_return", "completed_no_output"])
def test_failed_artifact_is_continuity_evidence_without_marker_credit(tmp_path, outcome):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="artifact", outcome=outcome)
    failed_path = store / "artifact" / "result.md.run.json"
    failed = json.loads(failed_path.read_bytes())
    failed["result"] = {"return_validation": {"status": "fail"}}
    failed_path.write_bytes(json.dumps(failed).encode())
    fixture = state(AFFIRMED, ARTIFACT)
    fixture.issue_comments[0]["created_at"] = "2026-09-19T00:00:00Z"
    fixture.record_root = store
    before = {path: path.read_bytes() for path in store.rglob("*.json")}
    lawful, invalid = work.validate_marker_claims(fixture)
    assert not any(marker.name == "artifact" for marker in lawful)
    claim = next(claim for claim in invalid if claim["name"] == "artifact")
    assert claim["reason"] == f"latest artifact dispatch has a failed return: {failed_path}"
    assert work.resume_session(fixture, "artifact", store) == SESSION
    assert before == {path: path.read_bytes() for path in before}
    recommendation = work.decide(fixture, RULES)
    assert recommendation.continuity == "fresh"
    assert work._named_continuity(fixture, "artifact", recommendation) == "resume"


@pytest.mark.parametrize("outcome", ["invalid_artifact_return", "completed_no_output"])
def test_latest_failed_artifact_without_identity_refuses_older_author(tmp_path, monkeypatch, capsys, outcome):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="artifact", name="older.md", session=OTHER_SESSION)
    dispatch_bundle(store, stage="artifact", name="failed.md", session=None, outcome=outcome,
                    completed_at="2026-09-21T10:00:00+00:00")
    fixture = state(AFFIRMED)
    fixture.issue_comments[0]["created_at"] = "2026-09-19T00:00:00Z"
    fixture.record_root = store
    decision = work.Decision("artifact", True, work._named_continuity(
        fixture, "artifact", work.decide(fixture, RULES)), "holder-named-stage")
    monkeypatch.setattr(work, "_dispatch_root", lambda *_a, **_k: pytest.fail("replaced author"))
    assert work.execute_stage(fixture, decision, tmp_path, None, "holder") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "refused"
    assert report["reason"] == "resume-bundle-invalid-for-artifact"
    assert "no valid session" in report["detail"]


def test_invalid_artifact_outcome_cannot_supply_other_stage_continuity(tmp_path):
    store = tmp_path / "dispatches"
    dispatch_bundle(store, stage="build", outcome="invalid_artifact_return")
    assert work._resume_source("example/product#12", "build", store) is None


@pytest.mark.parametrize("vendor", ["codex", "claude"])
@pytest.mark.parametrize("first_return", ["/tmp/private/artifact.md", ""])
@pytest.mark.parametrize("custom_dispatch", [False, True])
def test_public_artifact_repeat_resumes_failed_author_in_a_new_bundle(
        tmp_path, monkeypatch, capsys, vendor, first_return, custom_dispatch):
    import dispatch_implementer as implementer
    from test_dispatch_implementer import ARTIFACT_BRIEF, artifact_text, native_artifact_result

    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    root = policy_repository(tmp_path, "holder")
    monkeypatch.setattr(work, "load_work_config", lambda *_a: CONFIG)
    recipient = repository(tmp_path, "author")
    store = tmp_path / "dispatches"
    scenario = tmp_path / "scenario.json"
    setting = Path.home() / ".tradecraft" / "implementer-vendor"
    setting.parent.mkdir(parents=True)
    setting.write_bytes(vendor.encode())
    monkeypatch.setattr(work.records, "default_record_root", lambda: store)
    monkeypatch.setattr(work, "_dispatch_root", lambda *_a, **_k: (recipient, None, False))
    monkeypatch.setattr(work, "_selected_runtime_argument", lambda *_a: [])
    monkeypatch.setattr(implementer, "resolve_command", lambda *_a: [
        sys.executable, str(LIB / "tests/seat_cli.py"), vendor, str(scenario)])
    monkeypatch.setattr(implementer.records, "runtime_version", lambda *_a: "fixture runtime")
    class ArtifactTransport:
        def get(self, endpoint, *, paginate=False):
            if endpoint.endswith("/comments"):
                return [{"id": 751, "body": ARTIFACT_BRIEF,
                         "created_at": "2026-09-19T00:00:00Z",
                         "html_url": "https://github.example/issue#issuecomment-751",
                         "user": {"login": PRODUCER}}]
            if "/pulls?" in endpoint:
                return []
            return {"number": 12, "state": "open", "body": "", "labels": [],
                    "user": {"login": PRODUCER}}
    dispatch = tmp_path / "holder-job.md"
    dispatch_bytes = b"Holder instructions stay exact.\r\nNo embedded brief.\r\n"
    dispatch.write_bytes(dispatch_bytes)
    args = work.parser().parse_args([
        "run", "artifact", "--repo", "example/product", "--issue", "12", "--root", str(root),
        "--holder-session-id", "holder", *(["--dispatch", str(dispatch)] if custom_dispatch else []),
    ])
    commands = []
    original_run = subprocess.run
    def launch(command, *positional, **keywords):
        if len(command) > 1 and Path(command[1]).name == "dispatch_implementer.py":
            commands.append(command)
            selected_dispatch = Path(command[command.index("--dispatch") + 1]).read_bytes()
            if custom_dispatch:
                assert selected_dispatch == dispatch_bytes
            else:
                assert b"Return the whole artifact text in your final message" in selected_dispatch
            brief = Path(command[command.index("--artifact-brief") + 1])
            assert brief.read_bytes() == ARTIFACT_BRIEF.encode("utf-8")
            status = implementer.run_implementer(implementer.parser().parse_args(command[2:]))
            return subprocess.CompletedProcess(command, status)
        return original_run(command, *positional, **keywords)
    monkeypatch.setattr(work.subprocess, "run", launch)
    session = "0199a213-81c0-7800-8aa1-bbab2a035a53"
    scenario.write_bytes(json.dumps({vendor: native_artifact_result(vendor, first_return, session)}).encode())
    assert work.run(args, transport=ArtifactTransport()) == 1
    failed_path = next(store.rglob("*.run.json"))
    failed_bytes = failed_path.read_bytes()
    failed = json.loads(failed_bytes)
    assert failed["outcome"] == ("invalid_artifact_return" if first_return else "completed_no_output")
    diagnostic = capsys.readouterr().err
    assert str(failed_path) in diagnostic and session in diagnostic
    scenario.write_bytes(json.dumps({vendor: native_artifact_result(vendor, artifact_text("combined"), session)}).encode())
    assert work.run(args, transport=ArtifactTransport()) == 0
    assert len(commands) == 2
    assert "--resume" not in commands[0]
    assert commands[1][commands[1].index("--resume") + 1] == session
    assert failed_path.read_bytes() == failed_bytes
    runs = list(store.rglob("*.run.json"))
    assert len(runs) == 2
    passed = json.loads(next(path for path in runs if path != failed_path).read_bytes())
    assert passed["outcome"] == "success"
    assert passed["attempts"][0]["observed"]["session_id"] == session
    request = json.loads(Path(passed["request"]).read_bytes())
    assert request["requested"]["continuity"] == "resume"
    assert request["artifact_brief"]["source"] == "https://github.example/issue#issuecomment-751"
    assert Path(request["artifact_brief"]["path"]).read_bytes() == ARTIFACT_BRIEF.encode("utf-8")
    assert Path(passed["result"]["source_output"]).read_bytes() == artifact_text("combined").replace("\r\n", "\n").encode("utf-8")


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
    fixture = state(f"<!-- tradecraft:builder-session:v1 session={SESSION} vendor=codex -->")
    assert work.resume_session(fixture, "floor", tmp_path / "missing") == SESSION


def test_vendor_qualified_builder_marker_recovers_without_a_bundle(tmp_path):
    store = tmp_path / "dispatches"
    store.mkdir()
    fixture = state(AFFIRMED, f"<!-- tradecraft:builder-session:v1 session={SESSION} vendor=claude -->")
    fixture.record_root = store
    work.validate_marker_claims(fixture)
    assert any(marker.name == "builder-session" for marker in fixture.issue_markers)
    assert work.resume_session(fixture, "floor", store) == SESSION

    legacy = state(AFFIRMED, f"<!-- tradecraft:builder-session:v1 session={SESSION} -->")
    legacy.record_root = store
    work.validate_marker_claims(legacy)
    assert not any(marker.name == "builder-session" for marker in legacy.issue_markers)


def test_marker_only_codex_session_cannot_handover_without_its_record(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".tradecraft").mkdir(parents=True)
    (home / ".tradecraft" / "implementer-vendor").write_bytes(b"claude\n")
    monkeypatch.setattr(Path, "home", lambda: home)
    store = tmp_path / "dispatches"
    store.mkdir()
    fixture = state(AFFIRMED, f"<!-- tradecraft:builder-session:v1 session={SESSION} vendor=codex -->")
    fixture.record_root = store
    monkeypatch.setattr(work, "_dispatch_root", lambda *_a, **_k: pytest.fail("no root mutation"))
    with pytest.raises(work.WorkError, match="requires the predecessor dispatch bundle"):
        work.execute_stage(
            fixture, work.Decision("floor", True, "resume", "fixture"), tmp_path, None,
            "holder-session",
        )


@pytest.mark.parametrize("stage", ["floor", "artifact"])
@pytest.mark.parametrize(("machine_vendor", "override_vendor", "outcome"), [
    ("absent", "claude", "refuse"),
    ("claude", "claude", "handover"),
    ("claude", "codex", "resume"),
])
def test_codex_lineage_requires_machine_trigger_and_honors_matching_override(
        tmp_path, monkeypatch, stage, machine_vendor, override_vendor, outcome):
    home = tmp_path / "home"
    (home / ".tradecraft").mkdir(parents=True)
    if machine_vendor != "absent":
        (home / ".tradecraft" / "implementer-vendor").write_bytes(
            (machine_vendor + "\n").encode()
        )
    monkeypatch.setattr(Path, "home", lambda: home)
    root = repository(tmp_path, "implementation")
    source_stage = "artifact" if stage == "artifact" else "build"
    role = "artifact_author" if stage == "artifact" else "implementer"
    texts = (AFFIRMED, ARTIFACT) if stage == "artifact" else (AFFIRMED,)
    effort = "high" if override_vendor == "claude" else "xhigh"
    fixture = state(
        *texts,
        f"<!-- tradecraft:model-override:v1 {role}={override_vendor}:chosen:{effort} -->",
    )
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root, stage=source_stage, session=SESSION)
    monkeypatch.setattr(work, "_dispatch_root", lambda *_a, **_k: (root, None, False))
    monkeypatch.setattr(work, "_runtime_argument",
                        lambda vendor, explicit=None: [f"--{vendor}", "fixture"])
    original_run = subprocess.run
    launches = []

    def capture(command, *args, **kwargs):
        if len(command) > 1 and Path(command[1]).name == "dispatch_implementer.py":
            launches.append(command)
            return subprocess.CompletedProcess(command, 0)
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(work.subprocess, "run", capture)
    decision = work.Decision(stage, True, "resume", "fixture")
    handover = work._handover_path(fixture, role, root, None)
    if outcome == "refuse":
        with pytest.raises(work.WorkError, match="machine switch") as error:
            work.execute_stage(fixture, decision, root, None, "holder")
        assert "~/.tradecraft/implementer-vendor" in str(error.value)
        assert launches == []
    else:
        assert work.execute_stage(fixture, decision, root, None, "holder") == 0
        command = launches[-1]
        assert command[command.index("--vendor") + 1] == override_vendor
        assert command[command.index("--model") + 1] == "chosen"
        assert command[command.index("--effort") + 1] == effort
        assert "model-override" in command[command.index("--vendor-source") + 1]
        assert "issue-comment" in command[command.index("--model-source") + 1]
        if outcome == "handover":
            assert command[command.index("--session-id") + 1] != SESSION
            assert "--resume" not in command
            assert json.loads(handover.read_bytes())["trigger"].startswith("machine file")
        else:
            assert command[command.index("--resume") + 1] == SESSION
            assert "--session-id" not in command
        assert len(launches) == 1
    assert handover.exists() == (outcome == "handover")


@pytest.mark.parametrize("stage", ["floor", "artifact"])
def test_codex_to_claude_handover_reserves_once_and_stays_claude_after_flip(
        tmp_path, monkeypatch, stage):
    home = tmp_path / "home"
    (home / ".tradecraft").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    setting = home / ".tradecraft" / "implementer-vendor"
    setting.write_bytes(b"claude\n")
    root = repository(tmp_path, "implementation")
    source_stage = "artifact" if stage == "artifact" else "build"
    role = "artifact_author" if stage == "artifact" else "implementer"
    texts = (AFFIRMED, ARTIFACT) if stage == "artifact" else (AFFIRMED,)
    fixture = state(*texts)
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root, stage=source_stage, session=SESSION)
    monkeypatch.setattr(work, "_dispatch_root", lambda *_a, **_k: (root, None, False))
    monkeypatch.setattr(work, "_runtime_argument", lambda vendor, explicit=None: [f"--{vendor}", "fixture"])
    original_run = subprocess.run
    launches = []

    def capture(command, *args, **kwargs):
        if len(command) > 1 and Path(command[1]).name == "dispatch_implementer.py":
            launches.append(command)
            return subprocess.CompletedProcess(command, 0)
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(work.subprocess, "run", capture)
    decision = work.Decision(stage, True, "resume", "fixture")
    assert work.execute_stage(fixture, decision, root, None, "holder") == 0
    first = launches[-1]
    assert first[first.index("--vendor") + 1] == "claude"
    replacement = first[first.index("--session-id") + 1]
    assert "--resume" not in first
    assert work.execute_stage(fixture, decision, root, None, "holder") == 0
    retry = launches[-1]
    assert retry[retry.index("--session-id") + 1] == replacement
    assert len(launches) == 2
    handover = work._handover_path(fixture, role, root, None)
    value = json.loads(handover.read_bytes())
    value["phase"] = "completed"
    handover.write_bytes(json.dumps(value).encode())
    setting.write_bytes(b"codex\n")
    assert work.execute_stage(fixture, decision, root, None, "holder") == 0
    second = launches[-1]
    assert second[second.index("--vendor") + 1] == "claude"
    assert second[second.index("--resume") + 1] == replacement
    assert len(launches) == 3

    same_vendor = state(
        *texts, f"<!-- tradecraft:model-override:v1 {role}=claude:chosen:high -->"
    )
    same_vendor.record_root = fixture.record_root
    assert work.execute_stage(same_vendor, decision, root, None, "holder") == 0
    overridden = launches[-1]
    assert overridden[overridden.index("--vendor") + 1] == "claude"
    assert overridden[overridden.index("--model") + 1] == "chosen"
    assert overridden[overridden.index("--effort") + 1] == "high"
    assert "issue-comment" in overridden[overridden.index("--model-source") + 1]
    assert "issue-comment" in overridden[overridden.index("--effort-source") + 1]
    assert overridden[overridden.index("--resume") + 1] == replacement
    assert len(launches) == 4

    conflicting = state(
        *texts, f"<!-- tradecraft:model-override:v1 {role}=codex:chosen:xhigh -->"
    )
    conflicting.record_root = fixture.record_root
    before = handover.read_bytes()
    monkeypatch.setattr(
        work, "_handover_context",
        lambda *_a, **_k: pytest.fail("conflicting override must not assemble a handover"),
    )
    with pytest.raises(work.WorkError, match="override.*codex.*pinned Claude"):
        work.execute_stage(conflicting, decision, root, None, "holder")
    assert len(launches) == 4
    assert handover.read_bytes() == before


@pytest.mark.parametrize("stage", ["floor", "artifact"])
@pytest.mark.parametrize("machine_vendor", ["codex", "claude"])
@pytest.mark.parametrize("case", [
    "reserved", "no_launch_record", "observed", "completed_no_output",
    "missing_result", "missing_session",
])
def test_incomplete_handover_keeps_its_replacement_session(
        tmp_path, monkeypatch, stage, machine_vendor, case):
    home = tmp_path / "home"
    (home / ".tradecraft").mkdir(parents=True)
    (home / ".tradecraft" / "implementer-vendor").write_bytes(
        (machine_vendor + "\n").encode()
    )
    monkeypatch.setattr(Path, "home", lambda: home)
    root = repository(tmp_path, "implementation")
    source_stage = "artifact" if stage == "artifact" else "build"
    role = "artifact_author" if stage == "artifact" else "implementer"
    fixture = state(AFFIRMED, ARTIFACT) if stage == "artifact" else state(AFFIRMED)
    store = tmp_path / "dispatches"
    fixture.record_root = store
    dispatch_bundle(store, stage=source_stage, session=SESSION)
    predecessor = str(store / source_stage / "result.md.run.json")
    handover = work._handover_path(fixture, role, root, None)
    handover.parent.mkdir(parents=True)
    handover.write_bytes(json.dumps({
        "schema_version": 1, "from_vendor": "codex", "to_vendor": "claude",
        "from_session": SESSION, "from_bundle": predecessor,
        "replacement_session": OTHER_SESSION,
        "phase": "reserved" if case == "reserved" else "unresolved",
    }).encode())
    attempt_request = store / stage / "handover-attempt.request.json"
    if case != "reserved":
        attempt_request.parent.mkdir(parents=True, exist_ok=True)
        attempt_request.write_bytes(json.dumps({
            "schema_version": 2, "work": "example/product#12", "stage": stage,
            "producer_version": work.records.producer_version(),
            "dispatch_id": "handover-attempt", "root": str(root),
            "requested": {"vendor": "claude"},
            "handover": {
                "state": str(handover), "from_bundle": predecessor,
                "replacement_session": OTHER_SESSION, "phase": "fresh",
            },
        }).encode())
        if case != "missing_result":
            attempt_request.with_name("handover-attempt.run.json").write_bytes(
                json.dumps({
                    "schema_version": 2, "actual_vendor": "claude",
                    "outcome": (
                        "completed_no_output" if case == "completed_no_output" else "error"
                    ),
                    "completed_at": "2026-09-20T11:00:00+00:00",
                    "attempts": [{
                        "vendor": "claude", "launched": case != "no_launch_record",
                        "observed": {
                            "session_id": (
                                OTHER_SESSION if case in {"observed", "completed_no_output"}
                                else None
                            ),
                            "session_id_source": (
                                "claude JSON result.session_id"
                                if case in {"observed", "completed_no_output"} else None
                            ),
                        },
                    }],
                }).encode()
            )
    monkeypatch.setattr(work, "_dispatch_root", lambda *_a, **_k: (root, None, False))
    monkeypatch.setattr(work, "_runtime_argument",
                        lambda vendor, explicit=None: [f"--{vendor}", "fixture"])
    original_run = subprocess.run
    launches = []

    def capture(command, *args, **kwargs):
        if len(command) > 1 and Path(command[1]).name == "dispatch_implementer.py":
            launches.append(command)
            return subprocess.CompletedProcess(command, 0)
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(work.subprocess, "run", capture)
    decision = work.Decision(stage, True, "resume", "fixture")
    if case in {"missing_result", "missing_session"}:
        with pytest.raises(work.WorkError) as error:
            work.execute_stage(fixture, decision, root, None, "holder")
        assert str(attempt_request) in str(error.value)
        assert OTHER_SESSION in str(error.value)
        assert "--handover-recovery-session" in str(error.value)
        assert launches == []
        with pytest.raises(work.WorkError, match="must name that exact session"):
            work.execute_stage(
                fixture, decision, root, None, "holder",
                handover_recovery_session=SESSION,
            )
        assert work.execute_stage(
            fixture, decision, root, None, "holder",
            handover_recovery_session=OTHER_SESSION,
        ) == 0
        recovered = launches[-1]
        assert recovered[recovered.index("--resume") + 1] == OTHER_SESSION
        assert "--session-id" not in recovered
        assert len(launches) == 1
    else:
        assert work.execute_stage(fixture, decision, root, None, "holder") == 0
        command = launches[-1]
        assert command[command.index("--vendor") + 1] == "claude"
        assert command[command.index(
            "--session-id" if case in {"reserved", "no_launch_record"} else "--resume"
        ) + 1] == OTHER_SESSION
        if case == "completed_no_output":
            assert command[command.index("--handover-state") + 1] == str(handover)
        assert len(launches) == 1
    assert json.loads(handover.read_bytes())["replacement_session"] == OTHER_SESSION


def test_unavailable_claude_does_not_reserve_handover_before_a_retry(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".tradecraft").mkdir(parents=True)
    (home / ".tradecraft" / "implementer-vendor").write_bytes(b"claude\n")
    monkeypatch.setattr(Path, "home", lambda: home)
    root = repository(tmp_path, "implementation")
    fixture = state(AFFIRMED)
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root, stage="build", session=SESSION)
    monkeypatch.setattr(work, "_dispatch_root", lambda *_a, **_k: (root, None, False))
    available = False

    def runtime(vendor, explicit=None):
        if vendor == "claude" and not available:
            return ["--claude-unavailable-reason", "Claude CLI not installed"]
        return [f"--{vendor}", "fixture"]

    monkeypatch.setattr(work, "_runtime_argument", runtime)
    original_run = subprocess.run
    launches = []

    def capture(command, *args, **kwargs):
        if len(command) > 1 and Path(command[1]).name == "dispatch_implementer.py":
            launches.append(command)
            return subprocess.CompletedProcess(command, 1 if not available else 0)
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(work.subprocess, "run", capture)
    decision = work.Decision("floor", True, "resume", "fixture")
    assert work.execute_stage(fixture, decision, root, None, "holder") == 1
    handover = work._handover_path(fixture, "implementer", root, None)
    assert not handover.exists()
    assert "--claude-unavailable-reason" in launches[-1]
    available = True
    assert work.execute_stage(fixture, decision, root, None, "holder") == 0
    assert "--session-id" in launches[-1]
    assert json.loads(handover.read_bytes())["phase"] == "reserved"


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


@pytest.mark.parametrize("override,model,effort,source", [
    ("", "claude-opus-5-5", "max", "work entrance use-consumer default"),
    ("<!-- tradecraft:model-override:v1 use_consumer=claude:use-owner:high -->",
     "use-owner", "high", "issue-comment:unknown"),
])
def test_run_use_launches_only_with_the_holder_job_and_validated_tree(
        tmp_path, monkeypatch, override, model, effort, source):
    producer_calls = []

    def producer_vendor(*_args, **kwargs):
        producer_calls.append(kwargs)
        return "codex", "builder bundle"

    monkeypatch.setattr(work, "_producer_vendor", producer_vendor)
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
    assert work.execute_stage(
        state(AFFIRMED, override),
        work.Decision("use", True, "fresh", "holder-named-stage"),
        holder, None, dispatch_path=dispatch, tree_metadata=metadata,
    ) == 0
    assert len(launches) == 1
    assert producer_calls == [{
        "revision": git(implementation, "rev-parse", "HEAD").stdout.decode().strip(),
        "source_root": implementation,
    }]
    command = launches[0]
    assert Path(command[command.index("--dispatch") + 1]) == dispatch.resolve()
    assert Path(command[command.index("--root") + 1]) == output.resolve()
    assert command[command.index("--classification") + 1] == "cold"
    assert command[command.index("--requires") + 1] == "execute"
    assert command[command.index("--claude-model") + 1] == model
    assert command[command.index("--claude-effort") + 1] == effort
    assert command[command.index("--claude-effort-source") + 1] == source
    assert command[command.index("--codex-model") + 1] == work.dispatch_seat.DEFAULT_MODELS["codex"]
    assert command[command.index("--codex-model-source") + 1] == "dispatch_seat default"
    assert command[command.index("--claude") + 1] == "/claude-fixture"


def test_tree_revision_requires_0_154_before_source_resolution(tmp_path, monkeypatch):
    args = work.parser().parse_args([
        "tree", "--repo", "example/product", "--issue", "12", "--root", str(tmp_path),
        "--revision", SHA, "--mode", "adopter", "--output", str(tmp_path / "tree"),
        "--path", "README.md", "--loading-surface", "README.md",
    ])
    monkeypatch.setattr(work.records, "producer_version", lambda: "0.153.0")
    monkeypatch.setattr(
        work, "_landed_revision_source",
        lambda *_args, **_kwargs: pytest.fail("unsafe version must refuse before source access"),
    )

    with pytest.raises(work.WorkError) as raised:
        work._tree_command(args, tmp_path, object())

    assert "required=0.154.0" in str(raised.value)
    assert "mechanism=landed revision consumer tree" in str(raised.value)


def test_registered_tree_keeps_its_earlier_version_boundary(tmp_path, monkeypatch, capsys):
    output = tmp_path / "tree"
    metadata = output.with_name("tree.tradecraft-tree.json")
    args = work.parser().parse_args([
        "tree", "--repo", "example/product", "--issue", "12", "--root", str(tmp_path),
        "--mode", "adopter", "--output", str(output), "--path", "README.md",
        "--loading-surface", "README.md",
    ])
    monkeypatch.setattr(work.records, "producer_version", lambda: "0.153.0")
    monkeypatch.setattr(
        work, "resolve_implementation_root",
        lambda *_args, **_kwargs: (tmp_path / "source", "tradecraft/12-fixture", False),
    )

    def create_consumer_tree(**values):
        assert values["registration_used"] is True
        return metadata

    monkeypatch.setattr(work.recipient_tree, "create_consumer_tree", create_consumer_tree)

    assert work._tree_command(args, tmp_path, object()) == 0
    assert json.loads(capsys.readouterr().out)["producer_version"] == "0.153.0"


def test_tree_revision_and_run_use_need_no_registration(tmp_path, monkeypatch):
    monkeypatch.setattr(work, "_producer_vendor", lambda *_a, **_k: ("codex", "landed builder bundle"))
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


@pytest.mark.parametrize("timeout, expected", [(None, "10800"), (42.5, "42.5")])
def test_build_launch_forwards_holder_identity_and_timeout_to_the_launcher(
        tmp_path, monkeypatch, timeout, expected):
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
        timeout_seconds=timeout,
    ) == 0
    assert commands[0][-2:] == ["--holder-session-id", "stable-holder-token"]
    assert commands[0][commands[0].index("--root") + 1] == str(tmp_path)
    assert commands[0][commands[0].index("--timeout-seconds") + 1] == expected
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
    fixture = state(f"<!-- tradecraft:builder-session:v1 session={SESSION} vendor=codex -->", pr=True)
    monkeypatch.setattr(work, "resume_session", lambda *_args, **_kwargs: SESSION)
    monkeypatch.setattr(
        work.subprocess, "run",
        lambda *_args, **_kwargs: pytest.fail("holder session must not resume as builder"),
    )
    decision = work.Decision("floor", True, "resume", "current-head-floor-missing-or-red")
    assert work.execute_stage(fixture, decision, tmp_path, None, SESSION) == 0
    returned = json.loads(capsys.readouterr().out)
    assert returned["reason"] == "resume-session-identifies-holder-for-floor"


@pytest.mark.parametrize("timeout, expected", [(None, "3600"), (42.5, "42.5")])
def test_execute_stage_passes_the_recovered_session_to_the_implementer(
        tmp_path, monkeypatch, timeout, expected):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    fixture = state(AFFIRMED, pr=True)
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root)
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
        fixture, decision, tmp_path, None, "holder-session", timeout_seconds=timeout,
    ) == 0
    assert commands[0][-4:] == [
        "--holder-session-id", "holder-session", "--resume", SESSION,
    ]
    assert commands[0][commands[0].index("--timeout-seconds") + 1] == expected


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
    root = (
        policy_repository(tmp_path, "proof-command") if stage == "proof" else tmp_path
    )
    if stage != "proof":
        write_policy(root)
    args = work.parser().parse_args([
        "run", stage, "--repo", "acme/widget", "--issue", "3", "--root", str(root),
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
    write_policy(tmp_path)
    args = work.parser().parse_args([
        "run", "use", "--repo", "acme/widget", "--issue", "3", "--root", str(tmp_path),
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


class ReadyTransport:
    def __init__(self, draft=True, labels=()):
        self.draft = draft
        self.head = SHA
        self.labels = set(labels)
        self.operations = []

    def get(self, endpoint, *, paginate=False):
        if "/issues/7" in endpoint:
            return {"labels": [{"name": label} for label in sorted(self.labels)]}
        if "/pulls/7" in endpoint:
            return {"number": 7, "draft": self.draft, "head": {"sha": self.head}}
        raise KeyError(endpoint)

    def post(self, endpoint, payload):
        self.operations.append(("label", endpoint, payload))
        self.labels.update(payload["labels"])
        return {"labels": [{"name": label} for label in sorted(self.labels)]}

    def graphql(self, query, variables):
        self.operations.append(("ready", query, variables))
        self.draft = False
        return {"data": {"markPullRequestReadyForReview": {"pullRequest": {"isDraft": False}}}}


def test_ready_reviewers_applies_configured_label_before_ready(capsys):
    config = work.WorkConfig(
        connected_reviewers=frozenset({REVIEWER}),
        marker_producers=frozenset({PRODUCER}), reviewer_label="reviewers",
    )
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, config=config)
    fixture.pr["node_id"] = "PR_fixture"
    work.validate_marker_claims(fixture)
    transport = ReadyTransport()

    assert work._execute_ready_reviewers(
        transport, fixture, RULES, None, None
    ) == 0
    assert [operation[0] for operation in transport.operations] == ["label", "ready"]
    report = json.loads(capsys.readouterr().out)
    assert report["ready"] is True
    assert report["reviewer_label"] == "reviewers"


def test_ready_reviewers_repairs_label_without_toggling_an_already_ready_pr(capsys):
    config = work.WorkConfig(
        connected_reviewers=frozenset({REVIEWER}),
        marker_producers=frozenset({PRODUCER}), reviewer_label="reviewers",
    )
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, draft=False, config=config)
    work.validate_marker_claims(fixture)
    transport = ReadyTransport(draft=False)

    assert work._execute_ready_reviewers(
        transport, fixture, RULES, None, None
    ) == 0
    assert [operation[0] for operation in transport.operations] == ["label"]
    assert json.loads(capsys.readouterr().out)["ready_changed"] is False


def test_ready_reviewers_refuses_a_head_that_moves_after_label_write():
    config = work.WorkConfig(
        connected_reviewers=frozenset({REVIEWER}),
        marker_producers=frozenset({PRODUCER}), reviewer_label="reviewers",
    )
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE,
                    pr=True, config=config)
    fixture.pr["node_id"] = "PR_fixture"
    work.validate_marker_claims(fixture)

    class MovingHeadTransport(ReadyTransport):
        def post(self, endpoint, payload):
            result = super().post(endpoint, payload)
            self.head = "b" * 40
            return result

    transport = MovingHeadTransport()
    with pytest.raises(work.WorkError, match="head changed"):
        work._execute_ready_reviewers(transport, fixture, RULES, None, None)
    assert [operation[0] for operation in transport.operations] == ["label"]


def test_ready_reviewers_refuses_a_head_that_moves_during_ready_transition():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE, pr=True)
    fixture.pr["node_id"] = "PR_fixture"
    work.validate_marker_claims(fixture)

    class MovingHeadTransport(ReadyTransport):
        def graphql(self, query, variables):
            result = super().graphql(query, variables)
            self.head = "b" * 40
            return result

    with pytest.raises(work.WorkError, match="head changed"):
        work._execute_ready_reviewers(
            MovingHeadTransport(), fixture, RULES, None, None
        )


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
    monkeypatch.setattr(work, "_producer_vendor", lambda *_a, **_k: ("codex", "producer bundle"))
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
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root, stage="build")
    dispatch_bundle(fixture.record_root, stage="artifact")
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
    fixture = state(AFFIRMED, pr=True)
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root)
    decision = work.Decision("floor", True, "resume", "fixture", "existing detail")

    assert work.execute_stage(
        fixture, decision, holder, None, "holder-session"
    ) == 0

    notice = (
        "implementation registration migrated; recorded-holder check was not "
        "enforced on this run"
    )
    emitted = json.loads(capsys.readouterr().out.splitlines()[0])
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


# Launch planning reads the same defaults and bridge as the command route.
def ruling_file(tmp_path, monkeypatch, role="implementer", vendor="codex", replaces=None):
    home = tmp_path / "home"
    (home / ".tradecraft").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    path = home / ".tradecraft" / "model-rulings.json"
    path.write_bytes(json.dumps({"schema_version": 1, "entries": [{
        "id": "test-ruling", "role": role, "vendor": vendor,
        "replaces": replaces or {"model": "gpt-6.1-sol", "effort": "xhigh"},
        "model": "ruled-model", "effort": "ruled-effort", "source": "issuecomment-ruling",
    }]}).encode())
    return path


@pytest.mark.parametrize(("stage", "role", "vendor", "model", "effort"), [
    ("artifact", "artifact_author", "codex", "gpt-6.1-sol", "xhigh"),
    ("build", "implementer", "codex", "gpt-6.1-sol", "xhigh"),
    ("cold-seat", "cold_seat", "claude", "claude-opus-5-5", "xhigh"),
    ("use", "use_consumer", "claude", "claude-opus-5-5", "max"),
])
def test_report_launch_plan_is_read_only(tmp_path, monkeypatch, stage, role, vendor, model, effort):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    fixture = state(AFFIRMED)
    fixture.record_root = tmp_path / "dispatches"
    monkeypatch.setattr(work, "_dispatch_root", lambda *_a, **_k: pytest.fail("report created a root"))
    monkeypatch.setattr(work, "write_registry", lambda *_a: pytest.fail("report wrote registry"))
    monkeypatch.setattr(work, "sweep_registry", lambda *_a: pytest.fail("report swept registry"))
    monkeypatch.setattr(work, "_reserve_handover", lambda *_a, **_k: pytest.fail("report reserved handover"))
    monkeypatch.setattr(work.subprocess, "run", lambda *_a, **_k: pytest.fail("report ran a process"))
    before = sorted(tmp_path.rglob("*"))
    decision = work.Decision(stage, stage != "use", "fresh", "fixture")
    plan = work._reported_decision(fixture, decision).as_dict()["launch_settings"]
    assert plan["status"] == "resolved"
    assert plan["role"] == role
    primary = plan["primary"]
    assert (primary["vendor"], primary["model"], primary["effort"]) == (vendor, model, effort)
    assert set(primary["sources"]) == {"vendor", "model", "effort"}
    assert primary["baseline"] == {"model": model, "effort": effort}
    if stage in {"use", "cold-seat"}:
        assert plan["fallback"]["vendor"] == "codex"
        assert plan["fallback"]["condition"] == "primary availability failure only"
    assert sorted(tmp_path.rglob("*")) == before


def test_report_bridge_issue_precedence_and_whole_choice_clearing(tmp_path, monkeypatch):
    path = ruling_file(tmp_path, monkeypatch)
    fixture = state(AFFIRMED,
        "<!-- tradecraft:model-override:v1 implementer=codex:chosen:chosen-effort -->")
    decision = work.Decision("build", True, "fresh", "fixture")
    plan = work._launch_plan(fixture, decision)
    assert plan["primary"]["model"] == "chosen"
    assert "issue-comment" in plan["primary"]["sources"]["model"]
    fixture.issue_comments.append({"body": "<!-- tradecraft:model-override:v1 -->",
                                   "user": {"login": PRODUCER}})
    restored = work._launch_plan(fixture, decision)
    assert restored["primary"]["model"] == "ruled-model"
    source = restored["primary"]["sources"]["model"]
    assert json.loads(source.removeprefix("model ruling "))["path"] == str(path.resolve())
    assert "test-ruling" in source and "issuecomment-ruling" in source
    entry = json.loads(path.read_bytes())
    entry["entries"][0]["replaces"]["effort"] = "superseded"
    path.write_bytes(json.dumps(entry).encode())
    lapsed = work._launch_plan(fixture, decision)["primary"]
    assert lapsed["model"] == "gpt-6.1-sol"
    assert lapsed["bridge"]["disposition"] == "lapsed"
    assert lapsed["bridge"]["running"] == lapsed["baseline"]


def test_resume_report_keeps_historical_request_and_all_observations(tmp_path, monkeypatch):
    ruling_file(tmp_path, monkeypatch)
    fixture = state(AFFIRMED)
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root)
    request_path = fixture.record_root / "build" / "result.md.request.json"
    run_path = fixture.record_root / "build" / "result.md.run.json"
    requested = json.loads(request_path.read_bytes())
    requested["requested"].update(model="historical-request", effort="historical-effort",
                                   sources={"model": "old-ruling", "effort": "old-effort-source"})
    request_path.write_bytes(json.dumps(requested).encode())
    run = json.loads(run_path.read_bytes())
    run["attempts"][0]["observed"].update(reported_models=["native-one", "native-two"],
                                       reported_effort=None, reported_effort_unavailable_reason="absent")
    run_path.write_bytes(json.dumps(run).encode())
    plan = work._launch_plan(fixture, work.Decision("floor", True, "resume", "fixture"))
    assert plan["primary"]["model"] == "ruled-model"
    assert plan["session"]["id"] == SESSION
    assert plan["session"]["vendor"] == "codex"
    assert plan["session"]["requested"]["model"] == "historical-request"
    assert plan["session"]["requested"]["sources"]["model"] == "old-ruling"
    assert plan["session"]["observations"][0]["reported_models"] == ["native-one", "native-two"]
    assert plan["session"]["observations"][0]["reported_effort"] is None


def test_marker_only_resume_reports_unknown_historical_model(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    fixture = state(AFFIRMED, f"<!-- tradecraft:builder-session:v1 session={SESSION} vendor=claude -->")
    fixture.record_root = tmp_path / "dispatches"
    plan = work._launch_plan(fixture, work.Decision("floor", True, "resume", "fixture"))
    assert plan["primary"]["vendor"] == "claude"
    assert plan["session"]["vendor"] == "claude"
    assert plan["session"]["requested"]["model"] is None
    assert "marker" in plan["session"]["requested"]["unavailable_reason"]


def test_bad_bridge_report_retains_recommendation_and_run_refuses_before_root(tmp_path, monkeypatch):
    path = ruling_file(tmp_path, monkeypatch)
    path.write_bytes(b"{")
    fixture = state(AFFIRMED)
    decision = work.Decision("build", True, "fresh", "fixture")
    report = work._reported_decision(fixture, decision).as_dict()
    assert report["stage"] == "build" and report["dispatch"] is True
    assert report["launch_settings"]["status"] == "unresolved"
    assert str(path.resolve()) in report["launch_settings"]["reason"]
    monkeypatch.setattr(work, "_dispatch_root", lambda *_a, **_k: pytest.fail("created a root"))
    with pytest.raises(launch_settings.SettingsError):
        work.execute_stage(fixture, decision, tmp_path, None, "holder")
    # Holder endpoints have no bridge dependency.
    for stage in ("proof", "ready-reviewers", "release-report", "terminal"):
        assert work._reported_decision(fixture, work.Decision(stage, False, None, "fixture")).launch_settings is None


def test_named_run_plan_is_snapshot_and_agrees_with_command(tmp_path, monkeypatch, capsys):
    path = ruling_file(tmp_path, monkeypatch)
    fixture = state(AFFIRMED)
    root = tmp_path / "implementation"
    root.mkdir()
    def selected_root(*_a, **_k):
        # A concurrent ruling edit after planning cannot alter this command.
        path.write_bytes(b"malformed later file")
        return root, None, False
    monkeypatch.setattr(work, "_dispatch_root", selected_root)
    monkeypatch.setattr(work, "_runtime_argument", lambda vendor, explicit=None: [f"--{vendor}", "fixture"])
    def launch(command):
        printed = capsys.readouterr().out
        plans = [json.loads(line.split("launch_settings ", 1)[1]) for line in printed.splitlines()
                 if line.startswith("work: launch_settings ")]
        assert len(plans) == 1 and plans[0]["stage"] == "build"
        primary = plans[0]["primary"]
        assert command[command.index("--model") + 1] == primary["model"] == "ruled-model"
        assert command[command.index("--effort") + 1] == primary["effort"] == "ruled-effort"
        assert command[command.index("--model-source") + 1] == primary["sources"]["model"]
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(work.subprocess, "run", launch)
    assert work.execute_stage(fixture, work.Decision("build", True, "fresh", "holder-named-stage"),
                              tmp_path, None, "holder") == 0


@pytest.mark.parametrize("root_fields", [{}, {"root": None}, {"root": ""},
                                        {"root": False}, {"root": []}, {"root": {}}])
def test_report_invalid_registration_root_is_unresolved_and_read_only(tmp_path, monkeypatch, root_fields):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    fixture = state(AFFIRMED)
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root)
    row = {"repository": fixture.repo, "issue": fixture.issue_number, "active": True}
    row.update(root_fields)
    write_registry_rows([row])
    before = work.registry_path().read_bytes()
    monkeypatch.setattr(work, "write_registry", lambda *_a: pytest.fail("report wrote registry"))
    monkeypatch.setattr(work, "_dispatch_root", lambda *_a, **_k: pytest.fail("report proved a root"))
    monkeypatch.setattr(work.subprocess, "run", lambda *_a, **_k: pytest.fail("report ran a process"))
    report = work._reported_decision(fixture, work.Decision("floor", True, "resume", "fixture")).as_dict()
    assert report["stage"] == "floor" and report["dispatch"] is True
    assert report["launch_settings"]["status"] == "unresolved"
    assert "invalid root evidence" in report["launch_settings"]["reason"]
    assert work.registry_path().read_bytes() == before


@pytest.mark.parametrize("stage", ["build", "floor", "review-disposition"])
@pytest.mark.parametrize("case", ["multiple", "missing-legacy"])
def test_run_planning_root_failure_retains_structured_refusal(tmp_path, monkeypatch, capsys, stage, case):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    holder = repository(tmp_path, "holder")
    fixture = state(AFFIRMED)
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root)
    row = {"root": str(tmp_path / "missing"), "repository": fixture.repo,
           "issue": fixture.issue_number, "active": True}
    write_registry_rows([row, dict(row)] if case == "multiple" else [row])
    before = work.registry_path().read_bytes()
    monkeypatch.setattr(work, "create_implementation_root", lambda *_a: pytest.fail("created a root"))
    monkeypatch.setattr(work, "_runtime_argument", lambda vendor, explicit=None: [f"--{vendor}", "fixture"])
    assert work.execute_stage(fixture, work.Decision(stage, True, "resume", "fixture"),
                              holder, None, "holder") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["stage"] == stage and report["dispatch"] is False
    assert report["status"] == "refused"
    assert report["reason"] == f"implementation-root-unproved-for-{stage}"
    assert report["detail"]
    assert work.registry_path().read_bytes() == before


def test_resume_plan_source_change_then_reversion_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    fixture = state(AFFIRMED)
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root)
    run_path = fixture.record_root / "build" / "result.md.run.json"
    original = run_path.read_bytes()
    root = tmp_path / "implementation"
    root.mkdir()
    original_plan = work._launch_plan
    def changed_plan(*a, **kw):
        run = json.loads(original)
        run["attempts"][0]["observed"]["session_id"] = OTHER_SESSION
        run_path.write_bytes(json.dumps(run).encode())
        return original_plan(*a, **kw)
    def reverted_source(*_a, **_kw):
        run_path.write_bytes(original)
        return root, None, False
    monkeypatch.setattr(work, "_launch_plan", changed_plan)
    monkeypatch.setattr(work, "_dispatch_root", reverted_source)
    monkeypatch.setattr(work, "_runtime_argument", lambda vendor, explicit=None: [f"--{vendor}", "fixture"])
    monkeypatch.setattr(work.subprocess, "run", lambda *_a, **_kw: pytest.fail("launched a session different from the plan"))
    with pytest.raises(work.WorkError, match="resume source changed after launch planning"):
        work.execute_stage(fixture, work.Decision("floor", True, "resume", "fixture"),
                           tmp_path, None, "holder")


def test_use_report_defers_comparison_until_consumer_tree_is_validated(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    fixture = state(AFFIRMED)
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root, name="codex.md")
    dispatch_bundle(fixture.record_root, name="claude.md", completed_at="2026-09-21T10:00:00+00:00")
    for name, vendor, revision in (("codex", "codex", SHA), ("claude", "claude", BASE_SHA)):
        request_path = fixture.record_root / "build" / f"{name}.md.request.json"
        run_path = fixture.record_root / "build" / f"{name}.md.run.json"
        request = json.loads(request_path.read_bytes())
        request["requested"]["vendor"] = vendor
        request_path.write_bytes(json.dumps(request).encode())
        run = json.loads(run_path.read_bytes())
        run.update(actual_vendor=vendor, revision_after=revision)
        run_path.write_bytes(json.dumps(run).encode())
    assert work._producer_vendor(fixture, work.RESUME_SOURCE_STAGES["build"])[0] == "claude"
    assert work._producer_vendor(fixture, work.RESUME_SOURCE_STAGES["build"], revision=SHA)[0] == "codex"
    monkeypatch.setattr(work, "_producer_vendor", lambda *_a, **_kw: pytest.fail("report guessed the tree's producer"))
    before = sorted(tmp_path.rglob("*"))
    plan = work._reported_decision(fixture, work.Decision("use", False, None, "holder job pending")).launch_settings
    assert plan["fallback"]["comparison_vendor"] is None
    assert plan["fallback"]["comparison_vendor_source"] is None
    assert "validated recipient tree" in plan["fallback"]["comparison_vendor_unavailable_reason"]
    assert sorted(tmp_path.rglob("*")) == before


def test_report_handover_preview_keeps_reservation_and_predecessor(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".tradecraft").mkdir(parents=True)
    (home / ".tradecraft" / "implementer-vendor").write_bytes(b"claude")
    monkeypatch.setattr(Path, "home", lambda: home)
    fixture = state(AFFIRMED)
    fixture.record_root = tmp_path / "dispatches"
    fixture.holder_root = tmp_path / "implementation"
    dispatch_bundle(fixture.record_root)
    decision = work.Decision("floor", True, "resume", "fixture")
    source = work._resume_source("example/product#12", "floor", fixture.record_root)
    path = work._handover_path(fixture, "implementer", fixture.holder_root, None)
    first = work._launch_plan(fixture, decision)
    assert first["continuity"] == "handover"
    assert first["predecessor"]["vendor"] == "codex"
    assert first["handover"]["replacement_session"] is None
    assert not path.exists()
    reservation = {"schema_version": 1, "from_vendor": "codex", "to_vendor": "claude",
                   "from_session": SESSION, "from_bundle": source.path,
                   "replacement_session": OTHER_SESSION, "phase": "unresolved"}
    path.parent.mkdir(parents=True)
    path.write_bytes(json.dumps(reservation).encode())
    original = path.read_bytes()
    second = work._reported_decision(fixture, decision).launch_settings
    assert second["status"] == "unresolved"
    assert second["primary"]["vendor"] == "claude"
    assert second["predecessor"]["id"] == SESSION
    assert second["handover"]["replacement_session"] == OTHER_SESSION
    assert path.read_bytes() == original



def test_named_stage_report_uses_named_role_not_recommendation(tmp_path, monkeypatch):
    ruling_file(tmp_path, monkeypatch)
    write_policy(tmp_path)
    args = work.parser().parse_args([
        "run", "build", "--repo", "acme/widget", "--issue", "3", "--root", str(tmp_path),
    ])
    captured = []
    class Transport:
        def get(self, endpoint, *, paginate=False):
            if endpoint.endswith("/comments") or "/pulls?" in endpoint:
                return []
            return {"number": 3, "state": "open", "body": "", "labels": []}
    work.run(args, transport=Transport(), executor=lambda state, decision, *_a: captured.append(decision) or 0)
    assert captured[0].stage == "build"
    assert "current recommendation: convergence" in captured[0].detail
    assert captured[0].launch_settings["role"] == "implementer"
    assert captured[0].launch_settings["primary"]["model"] == "ruled-model"


def test_resume_plan_refuses_malformed_matching_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    fixture = state(AFFIRMED)
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root, session=None)
    plan = work._reported_decision(fixture, work.Decision("floor", True, "resume", "fixture")).launch_settings
    assert plan["status"] == "unresolved"
    assert "no valid session" in plan["reason"]


def test_use_bridge_compares_entrance_baseline_without_changing_direct_default(tmp_path, monkeypatch):
    ruling_file(tmp_path, monkeypatch, "use_consumer", "claude",
                {"model": "claude-opus-5-5", "effort": "max"})
    fixture = state(AFFIRMED)
    plan = work._launch_plan(fixture, work.Decision("use", False, None, "holder job pending"))
    assert plan["primary"]["effort"] == "ruled-effort"
    assert plan["primary"]["baseline"]["effort"] == "max"
    assert plan["fallback"]["eligible"] is False
    assert "capability execute" in plan["fallback"]["unavailable_reason"]
    direct = launch_settings.resolve("use_consumer", "claude", "claude-opus-5-5", "xhigh",
                                     "model default", "effort default", bridge=launch_settings.read_bridge())
    assert direct.effort == "xhigh"
    assert direct.bridge["disposition"] == "lapsed"


def test_resume_source_change_is_refused_before_recipient(tmp_path, monkeypatch):
    ruling_file(tmp_path, monkeypatch)
    fixture = state(AFFIRMED)
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root)
    root = tmp_path / "implementation"
    root.mkdir()
    def change_source(*_a, **_k):
        path = fixture.record_root / "build" / "result.md.run.json"
        row = json.loads(path.read_bytes())
        row["attempts"][0]["observed"]["session_id"] = OTHER_SESSION
        path.write_bytes(json.dumps(row).encode())
        return root, None, False
    monkeypatch.setattr(work, "_dispatch_root", change_source)
    monkeypatch.setattr(work, "_runtime_argument", lambda vendor, explicit=None: [f"--{vendor}", "fixture"])
    monkeypatch.setattr(work.subprocess, "run", lambda *_a, **_k: pytest.fail("launched changed session"))
    with pytest.raises(work.WorkError, match="resume source changed"):
        work.execute_stage(fixture, work.Decision("floor", True, "resume", "fixture"),
                           tmp_path, None, "holder")



def test_changed_handover_identity_refuses_before_recipient(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".tradecraft").mkdir(parents=True)
    (home / ".tradecraft" / "implementer-vendor").write_bytes(b"claude")
    monkeypatch.setattr(Path, "home", lambda: home)
    root = repository(tmp_path, "implementation")
    fixture = state(AFFIRMED)
    fixture.record_root = tmp_path / "dispatches"
    dispatch_bundle(fixture.record_root)
    source = work._resume_source("example/product#12", "floor", fixture.record_root)
    path = work._handover_path(fixture, "implementer", root, None)
    path.parent.mkdir(parents=True)
    row = {"schema_version": 1, "from_vendor": "codex", "to_vendor": "claude",
           "from_session": SESSION, "from_bundle": source.path,
           "replacement_session": OTHER_SESSION, "phase": "reserved"}
    path.write_bytes(json.dumps(row).encode())
    def change_reservation(*_a, **_k):
        row["replacement_session"] = "11111111-2222-3333-4444-555555555555"
        path.write_bytes(json.dumps(row).encode())
        return root, None, False
    monkeypatch.setattr(work, "_dispatch_root", change_reservation)
    monkeypatch.setattr(work, "_runtime_argument", lambda vendor, explicit=None: [f"--{vendor}", "fixture"])
    original = subprocess.run
    def launch(command, *a, **kw):
        if len(command) > 1 and Path(command[1]).name == "dispatch_implementer.py":
            pytest.fail("launched changed handover identity")
        return original(command, *a, **kw)
    monkeypatch.setattr(work.subprocess, "run", launch)
    with pytest.raises(work.WorkError, match="handover identity changed"):
        work.execute_stage(fixture, work.Decision("floor", True, "resume", "fixture"), root, None, "holder")

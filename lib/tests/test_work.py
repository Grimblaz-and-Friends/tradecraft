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


def state(*texts, pr=False, draft=True, paths=None, issue_state="open"):
    comments = [{"body": text} for text in texts]
    pull = None
    if pr:
        pull = {"number": 7, "state": "open", "draft": draft, "merged_at": None,
                "head": {"sha": SHA}}
    return work.WorkState(
        "example/product", 12,
        {"number": 12, "state": issue_state, "body": "", "labels": []},
        issue_comments=comments, pr=pull, changed_paths=paths or ["lib/runtime.py"],
    )


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
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE, REVIEWED, pr=True, draft=False),
     ("release-report", True, "fresh")),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE, REVIEWED,
           "<!-- tradecraft:panel-stage:v1 stage=cold-pass status=complete -->",
           "<!-- tradecraft:panel-stage:v1 stage=defense status=complete -->",
           "<!-- tradecraft:panel-stage:v1 stage=floor-fixes status=complete -->",
           pr=True, draft=False), ("release-report", True, "fresh")),
    (state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE, REVIEWED,
           pr=True, draft=False, issue_state="closed"), ("terminal", False, None)),
])
def test_each_state_table_row_routes_exactly_one_stage(fixture, expected):
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.dispatch, decision.continuity) == expected


def test_red_check_routes_floor_even_with_a_current_head_floor_marker():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, pr=True)
    fixture.checks = [{"conclusion": "failure"}]
    assert work.decide(fixture, RULES).stage == "floor"


def test_undisposed_reviewer_thread_routes_only_the_disposition_stage():
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, FLOOR, USE, REVIEWED,
                    pr=True, draft=False)
    fixture.review_comments = [{"id": 41, "body": "finding", "user": {"type": "Bot"}}]
    decision = work.decide(fixture, RULES)
    assert (decision.stage, decision.continuity, decision.detail) == (
        "review-disposition", "resume", "41",
    )


def test_bought_panel_routes_the_next_stage_named_by_the_lane():
    elevated = AFFIRMED.replace("ordinary", "elevated").replace("connected", "routine-panel")
    fixture = state(elevated, ARTIFACT, WOULD, HOLDER, FLOOR, USE, REVIEWED,
                    pr=True, draft=False, paths=["/".join(("skills", "work", "SKILL.md"))])
    first = work.decide(fixture, RULES)
    assert (first.stage, first.detail) == ("panel", "cold-pass")
    fixture.issue_comments.append({"body": "<!-- tradecraft:panel-stage:v1 stage=cold-pass status=complete -->"})
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


def configured_products(tmp_path, repositories):
    directory = tmp_path / ".tradecraft"
    directory.mkdir()
    (directory / "product-repos.json").write_text(json.dumps({
        "schema_version": 1,
        "repositories": repositories,
    }), encoding="utf-8")
    return work.load_product_repos(tmp_path)


@pytest.mark.parametrize("body", [
    "https://github.com/acme/product-app/issues/91",
    "<!-- tradecraft:product-incident:v1 repo=ACME/PRODUCT-APP issue=91 -->",
])
def test_configured_product_repository_accepts_its_incident_case_insensitively(tmp_path, body):
    fixture = state(AFFIRMED)
    fixture.repo = "example/tradecraft"
    fixture.issue["labels"] = [{"name": "practice-facing"}]
    fixture.issue_comments.append({"body": body})
    products = configured_products(tmp_path, ["Acme/Product-App"])
    assert work.decide(fixture, RULES, products).stage == "artifact"


def test_configured_product_repository_refuses_an_incident_from_elsewhere(tmp_path):
    fixture = state(AFFIRMED)
    fixture.repo = "example/tradecraft"
    fixture.issue["labels"] = [{"name": "practice-facing"}]
    fixture.issue_comments.append({
        "body": "https://github.com/acme/elsewhere/issues/91\n"
                "<!-- tradecraft:product-incident:v1 repo=acme/elsewhere issue=91 -->",
    })
    products = configured_products(tmp_path, ["acme/product-app"])
    decision = work.decide(fixture, RULES, products)
    assert (decision.stage, decision.dispatch) == ("product-incident-required", False)


def test_absent_product_repository_list_disables_the_check_and_says_so(tmp_path):
    fixture = state(AFFIRMED)
    fixture.repo = "example/tradecraft"
    fixture.issue["labels"] = [{"name": "practice-facing"}]
    products = work.load_product_repos(tmp_path)
    decision = work.decide(fixture, RULES, products)
    assert products is None
    assert (decision.stage, decision.dispatch) == ("artifact", True)
    assert decision.reason == "artifact-marker-absent;product-incident-check-not-configured"


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
        f"{base}/issues/3": {"number": 3, "state": "open", "body": "", "labels": []},
        f"{base}/issues/3/comments": [{"body": "https://github.com/acme/widget/pull/9"}],
        f"{base}/issues/3/timeline": [],
        f"{base}/pulls/9": {"number": 9, "state": "open", "draft": True,
                             "head": {"sha": SHA}},
        f"{base}/issues/9/comments": [],
        f"{base}/pulls/9/reviews": [],
        f"{base}/pulls/9/comments": [],
        f"{base}/pulls/9/files": [{"filename": "lib/runtime.py"}],
        f"{base}/commits/{SHA}/check-runs": {"check_runs": []},
    }
    transport = FakeTransport(values)
    fixture = work.read_state(transport, "acme/widget", 3)
    assert fixture.pr["number"] == 9
    assert fixture.changed_paths == ["lib/runtime.py"]
    assert {method for method, _endpoint, _paginate in transport.calls} == {"GET"}
    assert len(transport.calls) == 9


def test_review_disposition_marker_is_part_of_the_entrance_evidence():
    fixture = state()
    fixture.review_comments = [{"body": REVIEWED}]
    assert {marker.name for marker in fixture.markers} == {"connected-reviewer"}


def test_run_reads_the_product_repository_list_from_root(tmp_path):
    configured_products(tmp_path, ["acme/product-app"])
    args = work.parser().parse_args([
        "--repo", "example/tradecraft", "--issue", "3", "--root", str(tmp_path),
    ])
    captured = []

    class PracticeTransport:
        def get(self, endpoint, *, paginate=False):
            if endpoint.endswith("/comments") or endpoint.endswith("/timeline"):
                return []
            return {
                "number": 3,
                "state": "open",
                "body": AFFIRMED + "\nhttps://github.com/ACME/PRODUCT-APP/issues/7",
                "labels": [{"name": "practice-facing"}],
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
    ])
    captured = []

    class MinimalTransport:
        def get(self, endpoint, *, paginate=False):
            if endpoint.endswith("/comments") or endpoint.endswith("/timeline"):
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

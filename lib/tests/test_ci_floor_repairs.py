"""Regressions for the accepted declared-floor review findings."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import proof
import work
from test_ci_floor import CORPUS, CorpusTransport, corpus_state


def case_named(name):
    return deepcopy(next(case for case in CORPUS["cases"] if case["name"] == name))


def absent_case():
    case = case_named("declaration-absent")
    case["base_policy"] = {"absent": True}
    return case


def collect(case, state=None, transport=None):
    state = state or corpus_state(case)
    transport = transport or CorpusTransport(case, state)
    work.collect_floor(state, transport, observed_at=datetime.fromisoformat(case["observed_at"]))
    return state


class AbsentTreeTransport(CorpusTransport):
    def __init__(self, case, state, *, root=None, subtree=None):
        super().__init__(case, state)
        self.root = root if root is not None else {
            "truncated": False, "tree": [{"path": ".github", "type": "tree", "sha": "d" * 40}]
        }
        self.subtree = subtree if subtree is not None else {"truncated": False, "tree": []}

    def get(self, endpoint, *, paginate=False):
        prefix = f"repos/{self.state.repo}/git/trees/"
        if endpoint == prefix + self.tip + "?recursive=1":
            self.calls.append((endpoint, paginate))
            return {"truncated": True, "tree": []}
        if endpoint == prefix + self.tip:
            self.calls.append((endpoint, paginate))
            return self.root
        if endpoint == prefix + "d" * 40:
            self.calls.append((endpoint, paginate))
            return self.subtree
        return super().get(endpoint, paginate=paginate)


def test_absent_policy_uses_complete_path_trees_despite_truncated_recursive_tree():
    case = absent_case()
    state = corpus_state(case)
    transport = AbsentTreeTransport(case, state)
    collect(case, state, transport)
    assert state.floor_public["outcome"] == "builder"
    assert state.floor_public["policy"] is None
    trees = [endpoint for endpoint, _ in transport.calls if "/git/trees/" in endpoint]
    assert trees == [f"repos/{state.repo}/git/trees/{case['base_tip']}",
                     f"repos/{state.repo}/git/trees/{'d' * 40}"]


@pytest.mark.parametrize("root,subtree,expected", [
    ({"truncated": False, "tree": []}, None, "builder"),
    ({"truncated": True, "tree": []}, None, "unverifiable"),
    (None, {"truncated": True, "tree": []}, "unverifiable"),
    (None, {"truncated": False, "tree": [{"path": "change-proof.json", "type": "blob"}]}, "unverifiable"),
    ({"truncated": False, "tree": [{"path": ".github", "type": "tree", "sha": None}]}, None, "unverifiable"),
])
def test_policy_absence_requires_complete_readable_path(root, subtree, expected):
    case = absent_case()
    state = corpus_state(case)
    collect(case, state, AbsentTreeTransport(case, state, root=root, subtree=subtree))
    assert state.floor_public["outcome"] == expected


@pytest.mark.parametrize("name", ["all-expanded-jobs-success", "repair-current-gate-retains-earlier-tests"])
def test_required_workflow_tests_remain_floor_jobs(name):
    case = case_named(name)
    state = corpus_state(case)
    path = case["base_policy"]["content"]["floor"]["jobs"][0]["workflow"]
    state.required_gate = {"status": "identified", "sources": [{"repository": state.repo, "path": path}]}
    for check in state.checks:
        check["workflow_source"] = {"repository": state.repo, "path": path}
    assert len(work._matched_gate_checks(state)) >= 2
    collect(case, state)
    assert state.floor_public["outcome"] == "ci-met"
    assert [check["id"] for check in state.floor_public["checks"]] == case["expected"]["check_ids"]
    assert work._ready_evidence_error(state, {}) is None


@pytest.mark.parametrize("url", ["missing", None, "not-an-id", 12, {}, []])
def test_irrelevant_job_urls_are_never_parsed(url):
    case = case_named("unreadable-irrelevant-job-record")
    job = case["jobs"][0]["pages"][0]["jobs"][-1]
    job["run_attempt"] = 1
    if url != "missing":
        job["check_run_url"] = url
    state = collect(case)
    assert state.floor_public["outcome"] == "ci-met"


@pytest.mark.parametrize("proof_job", [False, True])
@pytest.mark.parametrize("url", [None, "not-an-id", 12, {}, []])
def test_relevant_job_urls_are_unverifiable(proof_job, url):
    case = case_named("repair-current-gate-retains-earlier-tests" if proof_job else "all-expanded-jobs-success")
    job = case["jobs"][0]["pages"][0]["jobs"][-1 if proof_job else 0]
    job["check_run_url"] = url
    state = corpus_state(case)
    if proof_job:
        path = case["base_policy"]["content"]["floor"]["jobs"][0]["workflow"]
        state.required_gate = {"status": "identified", "sources": [{"repository": state.repo, "path": path}]}
        for check in state.checks:
            check["workflow_source"] = {"repository": state.repo, "path": path}
    collect(case, state)
    assert state.floor_public["outcome"] == "unverifiable"


@pytest.mark.parametrize("failed_read", ["policy", "base-ref", "absence-tree"])
def test_unreadable_policy_is_not_published_as_confirmed_absent(failed_read):
    case = absent_case() if failed_read == "absence-tree" else case_named("base-policy-read-failure")
    state = corpus_state(case)
    class FailedRead(AbsentTreeTransport):
        def get(self, endpoint, *, paginate=False):
            if failed_read == "base-ref" and "/git/ref/" in endpoint:
                raise work.WorkError("HTTP 403 base ref unreadable")
            return super().get(endpoint, paginate=paginate)
    transport = FailedRead(case, state, root={"truncated": True, "tree": []})
    collect(case, state, transport)
    assert state.floor_public["outcome"] == "unverifiable"
    composed = work.compose_proof(state, case["local_override"])
    body = proof.document(composed, floor_context=work.floor_evaluation(state))
    assert "confirmed absent" not in body
    assert "base floor policy could not be read" in body
    assert "floor" not in composed["policy"]


def test_confirmed_absence_is_published_as_null():
    case = absent_case()
    state = corpus_state(case)
    collect(case, state, AbsentTreeTransport(case, state))
    composed = work.compose_proof(state, case["local_override"])
    assert composed["policy"]["floor"] is None
    assert "confirmed absent" in proof.document(composed, floor_context=work.floor_evaluation(state))


def test_malformed_base_confirmation_is_unverifiable():
    case = case_named("all-expanded-jobs-success")
    state = corpus_state(case)
    class MalformedConfirmation(CorpusTransport):
        def get(self, endpoint, *, paginate=False):
            result = super().get(endpoint, paginate=paginate)
            if "/git/ref/" in endpoint and sum("/git/ref/" in call[0] for call in self.calls) == 2:
                return {"object": ["not a ref object"]}
            return result
    collect(case, state, MalformedConfirmation(case, state))
    assert state.floor_public["outcome"] == "unverifiable"

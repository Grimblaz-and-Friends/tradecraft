"""Exercise the entrance against the landed independent gate's public corpus."""
import base64
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci_floor
import proof
import work
import test_work as support

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "skills" / "work" / "references"
LOCAL_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "proof-v1"
CORPUS_PATH = (SHARED / "proof-fixtures" / "v1-ci-floor.json" if SHARED.exists()
               else LOCAL_FIXTURES / "v1-ci-floor.json")
CORPUS = json.loads(CORPUS_PATH.read_bytes())
POLICY_PATH = "/".join((".github", "change-proof.json"))


class CorpusTransport:
    def __init__(self, case, state):
        self.case = case
        self.state = state
        self.calls = []
        self.tip = case["base_tip"]

    def get(self, endpoint, *, paginate=False):
        self.calls.append((endpoint, paginate))
        prefix = f"repos/{self.state.repo}"
        case = self.case
        if endpoint == f"{prefix}/git/ref/heads/main":
            return {"object": {"sha": self.tip}}
        if endpoint == f"{prefix}/contents/{POLICY_PATH}?ref={case['base_tip']}":
            policy = case["base_policy"]
            if "error" in policy:
                raise work.WorkError(policy["error"])
            if policy.get("absent"):
                raise work.WorkError("HTTP 404 Not Found")
            return {"type": "file", "encoding": "base64", "content":
                    base64.b64encode(json.dumps(policy["content"]).encode()).decode()}
        if endpoint == f"{prefix}/git/trees/{case['base_tip']}":
            return {"truncated": False, "tree": []}
        if endpoint == f"{prefix}/pulls/7":
            return self.state.pr
        if endpoint == f"{prefix}/actions/runs?head_sha={case['head']}&per_page=100":
            assert paginate
            return case["workflow_runs"]
        if endpoint == f"{prefix}/commits/{case['head']}/check-runs?filter=all&per_page=100":
            assert paginate
            return case["check_runs"]
        for record in case["runs"]:
            if endpoint == f"{prefix}/actions/runs/{record['id']}":
                if "error" in record:
                    raise ci_floor.ProofError(record["error"])
                return record["record"]
        for record in case["jobs"]:
            if endpoint == f"{prefix}/actions/runs/{record['run_id']}/jobs?filter=all&per_page=100":
                assert paginate
                if "error" in record:
                    raise ci_floor.ProofError(record["error"])
                return record["pages"]
        raise AssertionError(endpoint)


def corpus_state(case):
    texts = [support.AFFIRMED, support.ARTIFACT, support.WOULD, support.HOLDER]
    if case["builder_source"] is not None:
        texts.append(f"<!-- tradecraft:floor:v1 head={case['head']} status=pass -->")
    state = support.state(*texts, pr=True, config=work.WorkConfig(
        marker_producers=frozenset({support.PRODUCER})))
    state.pr["head"]["sha"] = case["head"]
    state.pr["base"]["sha"] = case["base_tip"]
    state.required_gate = {"status": "none", "sources": []}
    state.checks = [deepcopy(check) for page in case["check_runs"] for check in page["check_runs"]]
    for check in state.checks:
        run_id = work._action_run_id(check)
        for run in case["runs"]:
            if run["id"] == run_id and "record" in run:
                check["workflow_run"] = run["record"]
    state.policy_sources = {name: {"repository": state.repo, "path": path,
                                  "revision": case["head"], "sha256": "1" * 64}
                            for name, path in [("use_rules", POLICY_PATH),
                                               ("work_configuration", ".tradecraft/work.json")]}
    return state


@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda case: case["name"])
def test_landed_gate_corpus_collection_routing_proof_and_ready_floor(case, monkeypatch):
    state = corpus_state(case)
    # These cases model the positively identified current proof execution.
    if "current_run_id" in case:
        run_id = case["current_run_id"]
        gates = [check for check in state.checks if work._action_run_id(check) == run_id
                 and ci_floor._is_proof_job(check)]
        monkeypatch.setattr(work, "_matched_gate_checks", lambda _state: gates)
    transport = CorpusTransport(case, state)
    work.collect_floor(state, transport, observed_at=datetime.fromisoformat(case["observed_at"]))
    report = state.floor_public
    expected = case["expected"]
    assert report["outcome"] == expected["outcome"]
    if report.get("declaration", {}) and report["declaration"]["jobs"]:
        assert [check["id"] for check in report["checks"]] == expected["check_ids"]
    if expected["executions"] is not None:
        assert [{key: item[key] for key in wanted} for item, wanted in
                zip(report["executions"], expected["executions"], strict=True)] == expected["executions"]
    if report["policy"] is not None:
        assert report["policy"]["revision"] == case["base_tip"]
        assert report["policy"]["sha256"] == hashlib.sha256(state.floor_policy_bytes).hexdigest()
    composed = work.compose_proof(state, case["local_override"])
    if report["policy_status"] == "unreadable":
        assert "floor" not in composed["policy"]
    else:
        assert composed["policy"]["floor"] == report["policy"]
    if report["outcome"] == "ci-met":
        assert composed["floor"]["head"] == case["head"]
        assert composed["floor"]["source"] is None
        assert not any(item["stage"] == "floor" for item in composed["declarations"])
        assert not any(item["code"] == "floor-missing" for item in composed["diagnostics"])
        assert work._ready_evidence_error(state, support.RULES) is None
    decision = work.decide(state, support.RULES)
    outcome = work.floor_evaluation(state)["outcome"]
    if outcome in {"blocked", "stalled", "unverifiable"}:
        assert decision.stage == "floor-" + outcome
        assert decision.status == "holder-owned"
        assert not decision.dispatch
        assert decision.launch_settings is None
        assert work._ready_evidence_error(state, support.RULES)
    elif outcome == "pending":
        assert decision.stage == "waiting"
        assert not decision.dispatch
        assert work._ready_evidence_error(state, support.RULES)
    elif outcome in {"fallback", "builder-missing", "builder-red"}:
        assert decision.stage == "floor" and decision.dispatch
        assert work._ready_evidence_error(state, support.RULES)
    else:
        assert decision.stage == "ready-reviewers" and not decision.dispatch
        assert "criterion" in decision.detail
    assert "tradecraft:no-use:" not in proof.document(composed)


def test_fixture_bytes_are_the_landed_gate_blobs():
    for path, expected in [(CORPUS_PATH, "4ff396c367e447a4aa9daeadfdc459fc2713f7c5"),
                           (SHARED / "proof-v1.schema.json" if SHARED.exists() else LOCAL_FIXTURES / "proof-v1.schema.json",
                            "876e6441224462168e8db3b07686a23dcc893a27")]:
        data = path.read_bytes()
        assert hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == expected
        assert (LOCAL_FIXTURES / path.name).read_bytes() == data


@pytest.mark.parametrize("stage", ["build", "floor", "review-disposition"])
def test_implementation_turn_prompts_renew_acceptance_and_holder_reader_duty(stage):
    state = support.state(support.AFFIRMED)
    command = "python example-check.py --literal '$argument'"
    prompt = work._stage_prompt(state, work.Decision(stage, True, "resume", "fixture"),
                                floor_command=command).decode()
    assert "Commit executable criteria as tests" in prompt
    assert "tested revision" in prompt
    assert "exact artifact text" in prompt
    assert "do not launch or judge that reader" in prompt
    assert "Repairs renew this duty" in prompt
    if stage == "floor":
        assert command in prompt
        assert "<!-- tradecraft:floor:v1 head=TESTED_HEAD status=pass -->" in prompt
        assert "A failed command produces no passing marker line" in prompt


def test_missing_floor_command_refuses_before_any_mutation(tmp_path, capsys, monkeypatch):
    state = support.state(support.AFFIRMED)
    monkeypatch.setattr(work, "_dispatch_root", lambda *_args: pytest.fail("late refusal"))
    assert work.execute_stage(state, work.Decision("floor", True, "resume", "explicit"),
                              tmp_path, None) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "holder-owned" and not result["dispatch"]
    assert "--floor-command" in result["detail"]


@pytest.mark.parametrize("command", [None, "", " \n\t", "python\0check"])
def test_composed_floor_prompt_requires_a_usable_exact_command(command):
    with pytest.raises(work.WorkError, match="--floor-command"):
        work._stage_prompt(support.state(support.AFFIRMED),
                           work.Decision("floor", True, "resume", "explicit"), floor_command=command)


def test_moved_base_invalidates_collection_and_publication_identity():
    case = CORPUS["cases"][0]
    state = corpus_state(case)
    transport = CorpusTransport(case, state)
    work.collect_floor(state, transport, observed_at=datetime.fromisoformat(case["observed_at"]))
    transport.tip = "c" * 40
    with pytest.raises(work.WorkError, match="base tip moved"):
        work._verify_floor_identity(transport, state, state.pr)
    class Moving(CorpusTransport):
        def get(self, endpoint, *, paginate=False):
            value = super().get(endpoint, paginate=paginate)
            if len([call for call in self.calls if "/git/ref/" in call[0]]) > 1:
                value = {"object": {"sha": "c" * 40}}
            return value
    work.collect_floor(state, Moving(case, state), observed_at=datetime.fromisoformat(case["observed_at"]))
    assert state.floor_public["outcome"] == "unverifiable"


@pytest.mark.parametrize("bad", [None, {}, {"jobs": True}, {"jobs": [], "stall_after_seconds": True},
                                 {"jobs": [], "stall_after_seconds": 0}])
def test_malformed_floor_does_not_become_empty(bad):
    with pytest.raises(ci_floor.ProofError):
        ci_floor.declaration({"floor": bad})


def test_holder_failure_routes_name_execution_and_never_spend_builder_automatically():
    case = next(case for case in CORPUS["cases"] if case["name"] == "declared-matrix-failure")
    state = corpus_state(case)
    work.collect_floor(state, CorpusTransport(case, state), observed_at=datetime.fromisoformat(case["observed_at"]))
    result = work.decide(state, support.RULES)
    assert not result.dispatch
    assert "lint-and-test (windows-latest)" in result.detail
    for text in [case["head"], "run #91", "attempt #1", "outside the change, rerun once",
                 "fix a pull-request-body failure in the body", "only for a failure caused by the change"]:
        assert text in result.detail


class ReadyCorpusTransport(CorpusTransport):
    def __init__(self, case, state, move=None):
        super().__init__(case, state)
        self.operations = []
        self.move = move
        self.labels = set()

    def get(self, endpoint, *, paginate=False):
        prefix = f"repos/{self.state.repo}"
        if endpoint == f"{prefix}/issues/7":
            return {"labels": [{"name": label} for label in self.labels]}
        if endpoint == f"{prefix}/compare/{self.tip}...{self.case['head']}":
            return {"behind_by": 0}
        if endpoint == f"{prefix}/rules/branches/main?per_page=100":
            return []
        if endpoint == f"{prefix}/branches/main/protection":
            return {}
        return super().get(endpoint, paginate=paginate)

    def post(self, endpoint, payload):
        self.operations.append("label")
        self.labels.update(payload["labels"])
        if self.move == "label":
            self.tip = "c" * 40
        return {}

    def graphql(self, query, variables):
        self.operations.append("ready")
        self.state.pr["draft"] = False
        if self.move == "ready":
            self.tip = "c" * 40
        return {}


@pytest.mark.parametrize("move", [None, "before", "label", "ready"])
def test_ready_endpoint_accepts_declared_ci_and_rechecks_base_at_mutations(move, capsys):
    case = CORPUS["cases"][0]
    state = corpus_state(case)
    state.pr["node_id"] = "PR_fixture"
    state.config = work.WorkConfig(marker_producers=frozenset({support.PRODUCER}), reviewer_label="reviewers")
    transport = ReadyCorpusTransport(case, state, move)
    work.collect_floor(state, transport, observed_at=datetime.fromisoformat(case["observed_at"]))
    if move == "before":
        transport.tip = "c" * 40
    if move:
        with pytest.raises(work.WorkError, match="base tip moved"):
            work._execute_ready_reviewers(transport, state, support.RULES, None, None)
        assert transport.operations == {"before": [], "label": ["label"], "ready": ["label", "ready"]}[move]
    else:
        assert work._execute_ready_reviewers(transport, state, support.RULES, None, None) == 0
        assert transport.operations == ["label", "ready"]
        assert json.loads(capsys.readouterr().out)["ready"] is True


@pytest.mark.parametrize("move", ["before", "after"])
def test_proof_publication_rechecks_resolved_base_tip(move, tmp_path, monkeypatch):
    case = CORPUS["cases"][0]
    state = corpus_state(case)
    state.changed_paths = ["README.md"]
    transport = ReadyCorpusTransport(case, state)
    work.collect_floor(state, transport, observed_at=datetime.fromisoformat(case["observed_at"]))
    root = support.policy_repository(tmp_path)
    monkeypatch.setattr(work, "read_state", lambda *_args: state)
    monkeypatch.setattr(work, "prepare_use_evidence", lambda *_args: None)
    published = []
    original = work.compose_proof
    def compose(*args):
        result = original(*args)
        if move == "before":
            transport.tip = "c" * 40
        return result
    monkeypatch.setattr(work, "compose_proof", compose)
    def publish(_transport, _state, body, head):
        published.append(body)
        if move == "after":
            transport.tip = "c" * 40
        return {"action": "created", "id": 1}
    monkeypatch.setattr(work, "_publish_proof_comment", publish)
    monkeypatch.setattr(work, "_rerun_gate_evaluations", lambda *_args: pytest.fail("stale completion"))
    with pytest.raises(work.WorkError, match="base tip moved"):
        work._execute_proof(transport, state, root, support.RULES, root / POLICY_PATH, None, None)
    assert len(published) == (1 if move == "after" else 0)


@pytest.mark.parametrize("mechanical", [False, True])
def test_marker_free_no_use_proof_advances_and_historical_no_use_cannot(mechanical):
    case = CORPUS["cases"][0]
    state = corpus_state(case)
    if mechanical:
        state.issue_comments[0]["body"] = support.MECHANICAL
    state.changed_paths = ["README.md"]
    state.pr["draft"] = False
    state.issue_comments.append({"body": f"<!-- tradecraft:no-use:v1 head={case['head']} -->\nUse: not required - old claim.",
                                 "user": {"login": support.PRODUCER}})
    work.collect_floor(state, CorpusTransport(case, state), observed_at=datetime.fromisoformat(case["observed_at"]))
    assert work.decide(state, support.RULES).stage == "proof"
    composed = work.compose_proof(state, support.RULES)
    body = proof.document(composed, floor_context=work.floor_evaluation(state))
    assert "tradecraft:no-use:" not in body
    assert "no builder floor needed" in body
    assert "attempt #1" in body and case["base_tip"] in body
    state.pr_comments.append({"body": body, "user": {"login": support.PRODUCER}})
    state.validated_markers = None
    work.set_proof_freshness(state, composed)
    assert work.decide(state, support.RULES).stage == "release-report"
    state.required_gate = {"status": "unidentified", "reason": "unreadable branch rules", "sources": []}
    assert work.decide(state, support.RULES).stage == "waiting"

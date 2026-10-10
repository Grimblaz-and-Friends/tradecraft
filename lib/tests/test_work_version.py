from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import work
from version_fixture import (ADVANCED, BASE, FORK, HEAD, REPO, RULES, SPEC,
                             adopted_repository, blob, fixture_state)


def assess(state, transport, rules=RULES):
    return work._assess_version(state, rules, "synthetic selected policy", transport)


def named(stage, state, transport, root, rules=RULES):
    args = work.parser().parse_args([
        "run", stage, "--repo", REPO, "--issue", "12", "--root", str(root)])
    return work.run(args, transport=transport)


@pytest.mark.parametrize("stage", ["ready-reviewers", "proof"])
@pytest.mark.parametrize("draft", [False, True])
@pytest.mark.parametrize("risk,lane", work.LANES)
def test_C3_named_endpoints_refuse_every_lane_before_effects(stage, draft, risk, lane, tmp_path, capsys, monkeypatch):
    state, transport = fixture_state(risk=risk, lane=lane, draft=draft)
    root = tmp_path / "adopter"
    adopted_repository(root)
    original = work.compose_proof
    compositions = []
    monkeypatch.setattr(work, "compose_proof", lambda *a: compositions.append(True) or original(*a))
    assert named(stage, state, transport, root) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "version-obligation-blocked"
    assert report["version_obligation"]["owed"] is True
    assert report["version_obligation"]["met"] is False
    for value in ("package.json", "release", "2.9.9", "2.10.0", "builder", "run build"):
        assert value in report["detail"]
    assert not compositions and not transport.effects


@pytest.mark.parametrize("stage", ["ready-reviewers", "proof"])
@pytest.mark.parametrize("version,files,declared,status", [
    ("2.10.0", [{"filename": "runtime/code.py", "status": "modified"}], True, "satisfied"),
    ("3.0.0", [{"filename": "runtime/code.py", "status": "modified"}], True, "satisfied"),
    ("2.9.9", [{"filename": "README.md", "status": "modified"}], True, "not-required"),
    ("broken", [{"filename": "runtime/code.py", "status": "modified"}], False, "undeclared"),
])
def test_C4_named_passing_controls_reach_real_effects(stage, version, files, declared, status, tmp_path, capsys):
    state, transport = fixture_state(version=version, files=files)
    rules = RULES if declared else {key: value for key, value in RULES.items() if key != "version"}
    root = tmp_path / "adopter"
    adopted_repository(root, rules)
    assert named(stage, state, transport, root, rules) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["version_obligation"]["status"] == status
    if stage == "ready-reviewers":
        assert report["ready"] is True
        assert [effect[0] for effect in transport.effects] == ["POST", "GRAPHQL"]
    else:
        assert report["comment"]["action"] == "created"
        assert any(effect[1].endswith("/comments") for effect in transport.effects)
        document = work._proof_payload(transport.comments[-1]["body"])
        assert "version_obligation" not in document and "version" not in document
    if not declared or status == "not-required":
        assert not any("/contents/package.json" in call[1] for call in transport.calls)


@pytest.mark.parametrize("path,status,previous,expected", [
    ("runtime/code.py", "modified", None, ["runtime/code.py"]),
    ("runtime/gone.py", "removed", None, ["runtime/gone.py"]),
    ("notes/moved.py", "renamed", "runtime/old.py", ["runtime/old.py"]),
    ("runtime/new.py", "renamed", "notes/old.py", ["runtime/new.py"]),
    ("package.json", "modified", None, ["package.json"]),
    ("runtime/tests/unit.py", "added", None, []),
    ("runtime/tests/delivery.py", "added", None, ["runtime/tests/delivery.py"]),
    ("Runtime/code.py", "modified", None, []),
    ("runtime\\code.py", "modified", None, ["runtime/code.py"]),
])
def test_C4_shared_rule_semantics_include_removals_and_rename_sources(path, status, previous, expected):
    files = [{"filename": path, "status": status}]
    if previous:
        files[0]["previous_filename"] = previous
    state, transport = fixture_state(files=files)
    report = assess(state, transport)
    assert report["paths"] == expected
    assert report["status"] == ("blocked" if expected else "not-required")
    assert report["owed"] is bool(expected)
    assert report["met"] is (False if expected else None)


@pytest.mark.parametrize("increment,version,status,target", [
    ("major", "2.99.99", "blocked", "3.0.0"), ("major", "3.0.0", "satisfied", "3.0.0"),
    ("minor", "2.9.10", "blocked", "2.10.0"), ("minor", "2.10.0", "satisfied", "2.10.0"),
    ("minor", "3.0.0", "satisfied", "2.10.0"), ("patch", "2.9.10", "satisfied", "2.9.10"),
])
def test_C4_numeric_targets(increment, version, status, target):
    state, transport = fixture_state(version=version)
    report = assess(state, transport, {**RULES, "version": {**SPEC, "increment": increment}})
    assert (report["status"], report["target"]) == (status, target)


@pytest.mark.parametrize("stage", ["build", "floor", "review-disposition"])
@pytest.mark.parametrize("lane", ["mechanical", "connected"])
@pytest.mark.parametrize("pr,match", [(False, False), (True, False), (True, True)])
def test_C2_C7_every_composed_stage_gets_conditional_target_and_correct_subject(stage, lane, pr, match):
    files = [{"filename": "runtime/code.py" if match else "README.md", "status": "modified"}]
    state, transport = fixture_state(version="3.0.0", files=files, lane=lane, pr=pr, ref="release/2", fork=True)
    work.validate_marker_claims(state)
    instruction = work._compose_version_instruction(state, transport, RULES, "synthetic policy")
    prompt = work._stage_prompt(state, work.Decision(stage, True, "fresh" if not pr else "resume", "fixture"),
                                floor_command="python check.py", version_instruction=instruction).decode()
    for value in ("package.json", "release", BASE, "2.9.9", "2.10.0", "do not downgrade",
                  "including removals", '"exclude": ["runtime/tests/**"]',
                  '"include": ["runtime/tests/delivery.py"]', "within their own group"):
        assert value in prompt
    assert ("actual PR base tip example/product:release/2" if pr else "default-branch tip before a PR exists example/product:main") in prompt
    assert ("runtime/code.py" in instruction.split("Current matching paths:")[1]) is match
    assert work.build_reach.PRESERVATION in prompt
    if lane == "mechanical":
        assert "map each affirmed brief row" in prompt and "artifact acceptance criterion" not in prompt
        for value in ("row number", "command or procedure", "tested revision", "result and limitation",
                      "exact affirmed row text", "required capability", "needed inputs", "holder-launched", "do not launch or judge"):
            assert value in prompt
    else:
        assert "map every artifact acceptance criterion" in prompt
        assert "--- settled artifact begin ---" in prompt
    assert any(f"repos/{REPO}/contents/package.json?ref={BASE}" == call[1] for call in transport.calls)
    assert not transport.effects


def test_C2_fork_head_and_nondefault_current_base_are_read_by_full_sha():
    state, transport = fixture_state(fork=True, ref="release/2", version="2.10.0")
    report = assess(state, transport)
    assert report["status"] == "satisfied"
    assert report["head"] == {"repository": FORK, "sha": HEAD, "value": "2.10.0"}
    assert report["base"]["sha"] == BASE and report["base"]["ref"] == "release/2"
    assert any(call[1] == f"repos/{FORK}/contents/package.json?ref={HEAD}" for call in transport.calls)


def test_C2_unreadable_first_base_refuses_before_allocation_launch_or_publication(tmp_path, monkeypatch, capsys):
    state, transport = fixture_state(pr=False)
    transport.base_version = b'not json'
    root = tmp_path / "adopter"
    adopted_repository(root)
    for function in ("create_implementation_root", "publish_implementation_branch", "_invoke_recipient"):
        monkeypatch.setattr(work, function, lambda *a, **kw: pytest.fail("version preflight allowed an effect"))
    decision = work.Decision("build", True, "fresh", "holder-named-stage")
    assert work.execute_stage(state, decision, root, None, "holder", transport=transport,
                              rules=RULES, use_rules_path=root / ".github" / "change-proof.json") == 0
    report = json.loads(capsys.readouterr().out)
    assert "Cannot compose the conditional version instruction" in report["detail"]
    assert "base version evidence" in report["detail"]
    assert report["version_obligation"]["status"] == "unverifiable"
    assert report["version_obligation"]["declaration"] == SPEC
    assert report["version_obligation"]["base"]["sha"] == BASE
    assert report["version_obligation"]["base"]["value"] is None
    assert report["version_obligation"]["target"] is None
    assert not transport.effects


@pytest.mark.parametrize("files,count,reason", [
    ([{"filename": "README.md", "status": "modified"}], 2, "retrieved 1"),
    ([{"filename": "README.md", "status": "modified"}], None, "missing or invalid"),
    ([{}, {"filename": "runtime/code.py", "status": "modified"}], 2, "usable filename"),
    ([{"filename": "README.md", "status": "unknown"}], 1, "unknown"),
    ([{"filename": "README.md", "status": "modified"}] * 2, 2, "Duplicate"),
    ([{"filename": "README.md", "status": "renamed"}], 1, "previous_filename"),
    ([{"filename": "/runtime/code.py", "status": "added"}], 1, "usable filename"),
    ([None], 1, "not an object"),
])
@pytest.mark.parametrize("stage", ["ready-reviewers", "proof"])
def test_C5_invalid_inventory_withholds_effects(files, count, reason, stage, tmp_path, monkeypatch, capsys):
    state, transport = fixture_state(files=files)
    state.pr["changed_files"] = count
    root = tmp_path / "adopter"
    path = adopted_repository(root)
    # Inject only public state; endpoint policy and version guards remain real.
    monkeypatch.setattr(work, "read_state", lambda *a: deepcopy(state))
    if stage == "proof":
        assert work._execute_proof(transport, state, root, RULES, path, None, None) == 0
    else:
        assert work._execute_ready_reviewers(transport, state, RULES, None, None) == 0
    report = json.loads(capsys.readouterr().out)["version_obligation"]
    assert report["status"] == "unverifiable" and report["met"] is None
    assert reason in report["message"] and not transport.effects
    assert report["owed"] is (True if len(files) > 1 and files[-1].get("filename", "").startswith("runtime/") else None)


@pytest.mark.parametrize("side", ["base", "head"])
@pytest.mark.parametrize("content", [b'not JSON', b'[]', b'{}', b'{"release":7}', b'{"release":null}',
    b'{"release":"2.9"}', b'{"release":"2.9.9","release":"3.0.0"}'])
def test_C5_invalid_version_bytes_preserve_known_context(side, content):
    state, transport = fixture_state()
    setattr(transport, "base_version" if side == "base" else "version", content)
    report = assess(state, transport)
    assert report["status"] == "unverifiable" and report["owed"] is True and report["met"] is None
    assert side + " version evidence" in report["message"]
    if side == "head":
        assert report["base"]["value"] == "2.9.9" and report["target"] == "2.10.0"


@pytest.mark.parametrize("side", ["base", "head"])
def test_C5_unreadable_version_blob_is_unverifiable(side):
    state, transport = fixture_state()
    sha = BASE if side == "base" else HEAD
    transport.overrides[f"repos/{REPO}/contents/package.json?ref={sha}"] = work.WorkError("404 unreadable")
    assert assess(state, transport)["status"] == "unverifiable"


def test_C5_pagination_is_complete_and_preserves_all_matches():
    files = [{"filename": f"runtime/file-{index}.py", "status": "modified"} for index in range(101)]
    state, transport = fixture_state(files=files)
    collected = work._read_policy_state(transport, REPO, 12, state.config, RULES, "fixture")
    assert collected.version_obligation["status"] == "blocked"
    assert len(collected.version_obligation["paths"]) == 101
    assert ("GET", f"repos/{REPO}/pulls/7/files", True) in transport.calls
    state.pr["changed_files"] = 102
    collected = work._read_policy_state(transport, REPO, 12, state.config, RULES, "fixture")
    assert collected.version_obligation["status"] == "unverifiable"
    assert collected.version_obligation["owed"] is True


def test_C5_head_movement_during_inventory_never_becomes_not_required():
    state, transport = fixture_state(files=[{"filename": "README.md", "status": "modified"}])
    def move(endpoint):
        if endpoint.endswith("/files"):
            state.pr["head"]["sha"] = "e" * 40
    transport.before_get = move
    collected = work._read_policy_state(transport, REPO, 12, state.config, RULES, "fixture")
    assert collected.version_obligation["status"] == "unverifiable"
    assert "identity moved" in collected.version_obligation["message"]


def test_C5_head_repository_movement_during_inventory_is_unverifiable():
    state, transport = fixture_state(files=[{"filename": "README.md", "status": "modified"}])
    def move(endpoint):
        if endpoint.endswith("/files"):
            state.pr["head"]["repo"]["full_name"] = FORK
    transport.before_get = move
    collected = work._read_policy_state(transport, REPO, 12, state.config, RULES, "fixture")
    assert collected.version_obligation["status"] == "unverifiable"


@pytest.mark.parametrize("stage", ["ready-reviewers", "proof"])
def test_C5_live_base_advance_invalidates_the_old_sufficient_head(stage, tmp_path, capsys):
    state, transport = fixture_state(version="2.10.0")
    report = assess(state, transport)
    assert report["status"] == "satisfied"
    transport.base_sha = ADVANCED
    transport.base_version = b'{"release":"2.10.0"}'
    root = tmp_path / "adopter"
    adopted_repository(root)
    assert named(stage, state, transport, root) == 0
    report = json.loads(capsys.readouterr().out)["version_obligation"]
    assert report["status"] == "blocked" and report["target"] == "2.11.0"
    assert report["base"]["sha"] == ADVANCED and not transport.effects


@pytest.mark.parametrize("moment", ["before-effect", "after-label"])
def test_C5_base_movement_stops_readiness_at_effect_boundary(moment, tmp_path, capsys):
    state, transport = fixture_state(version="2.10.0")
    root = tmp_path / "adopter"
    adopted_repository(root)
    collected = work._read_policy_state(transport, REPO, 12, state.config, RULES, "fixture")
    if moment == "after-label":
        transport.after_effect = lambda endpoint: setattr(transport, "base_sha", ADVANCED)
    else:
        def move(endpoint):
            if endpoint == f"repos/{REPO}/issues/7":
                transport.base_sha = ADVANCED
        transport.before_get = move
    with pytest.raises(work.WorkError, match="base tip moved"):
        work._execute_ready_reviewers(transport, collected, RULES, None, None)
    assert not any(effect[0] == "GRAPHQL" for effect in transport.effects)
    assert bool(transport.effects) is (moment == "after-label")


def test_C5_movement_during_version_collection_is_unverifiable():
    state, transport = fixture_state(version="2.10.0")
    def move(endpoint):
        if f"ref={HEAD}" in endpoint:
            transport.base_sha = ADVANCED
    transport.before_get = move
    report = assess(state, transport)
    assert report["status"] == "unverifiable" and report["owed"] is True
    assert report["base"]["sha"] == BASE and report["target"] == "2.10.0"


@pytest.mark.parametrize("declared_view", ["checkout", "committed"])
def test_C5_freshness_preserves_each_policy_view_without_composing_blocked_proof(declared_view, tmp_path, monkeypatch, capsys):
    declared = RULES
    undeclared = {key: value for key, value in RULES.items() if key != "version"}
    root = tmp_path / "adopter"
    path = adopted_repository(root, declared if declared_view == "committed" else undeclared)
    path.write_bytes(json.dumps(undeclared if declared_view == "committed" else declared).encode())
    state, transport = fixture_state(draft=False)
    monkeypatch.setattr(work, "compose_proof", lambda *a: pytest.fail("blocked view composed expected proof"))
    args = work.parser().parse_args(["--repo", REPO, "--issue", "12", "--root", str(root)])
    assert work.run(args, transport=transport) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["stage"] == "proof" and "version-obligation-blocked" in report["reason"]
    assert report["version_obligation"]["status"] == ("blocked" if declared_view == "checkout" else "undeclared")
    assert report["proof_version_obligation"]["status"] == ("blocked" if declared_view == "committed" else "undeclared")
    assert report["version_obligation"]["policy_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert not transport.effects


@pytest.mark.parametrize("moment", ["before-effect", "after-label"])
def test_C5_selected_policy_movement_stops_ready(moment, tmp_path, capsys):
    state, transport = fixture_state(version="2.10.0")
    root = tmp_path / "adopter"
    path = adopted_repository(root)
    collected = work._read_policy_state(transport, REPO, 12, state.config, RULES, str(path))
    collected.readiness_policy = (path, path.read_bytes())
    def change(_):
        path.write_bytes(json.dumps({**RULES, "version": {**SPEC, "increment": "major"}}).encode())
    if moment == "after-label":
        transport.after_effect = change
        with pytest.raises(work.WorkError, match="selected policy changed"):
            work._execute_ready_reviewers(transport, collected, RULES, None, None)
        assert collected.version_obligation["status"] == "unverifiable"
    else:
        transport.before_get = lambda endpoint: change(endpoint) if endpoint == f"repos/{REPO}/issues/7" else None
        assert work._execute_ready_reviewers(transport, collected, RULES, None, None) == 0
        assert json.loads(capsys.readouterr().out)["version_obligation"]["status"] == "unverifiable"
    assert not any(effect[0] == "GRAPHQL" for effect in transport.effects)


def test_C2_merge_and_version_instructions_share_pinned_basis():
    state, transport = fixture_state()
    obligation = work.MergeObligation(HEAD, REPO, "main", ADVANCED, (), None)
    with pytest.raises(work.WorkError, match="differs from the pinned merge obligation"):
        work._compose_version_instruction(state, transport, RULES, "fixture", obligation)


@pytest.mark.parametrize("stage", ["build", "floor", "review-disposition"])
def test_C2_execute_composes_version_instruction_before_allocation(stage, tmp_path, monkeypatch, capsys):
    state, transport = fixture_state(pr=False)
    root = tmp_path / "adopter"
    path = adopted_repository(root)
    original = work._stage_prompt
    seen = []
    def capture(*a, **kw):
        seen.append(original(*a, **kw))
        raise work.WorkError("Captured composed prompt before allocation")
    monkeypatch.setattr(work, "_stage_prompt", capture)
    for function in ("create_implementation_root", "publish_implementation_branch", "_invoke_recipient"):
        monkeypatch.setattr(work, function, lambda *a, **kw: pytest.fail("unexpected launch effect"))
    assert work.execute_stage(state, work.Decision(stage, True, "fresh", "fixture"), root, None, "holder",
                              transport=transport, rules=RULES, use_rules_path=path,
                              floor_command="python check.py") == 0
    assert len(seen) == 1 and b"target 2.10.0" in seen[0]
    assert b"map each affirmed brief row" in seen[0]
    assert "Captured composed prompt" in json.loads(capsys.readouterr().out)["detail"]


@pytest.mark.parametrize("moment", ["before-composition", "before-publication", "after-publication"])
def test_C5_proof_basis_movement_withholds_composition_or_remaining_effects(moment, tmp_path, monkeypatch):
    state, transport = fixture_state(version="2.10.0")
    root = tmp_path / "adopter"
    path = adopted_repository(root)
    original_prepare = work.prepare_use_evidence
    original_document = work.proof_document.document
    compositions = []
    original_compose = work.compose_proof
    monkeypatch.setattr(work, "compose_proof", lambda *a: compositions.append(True) or original_compose(*a))
    if moment == "before-composition":
        def prepare(*a):
            original_prepare(*a)
            transport.base_sha = ADVANCED
        monkeypatch.setattr(work, "prepare_use_evidence", prepare)
    elif moment == "before-publication":
        def document(*a, **kw):
            transport.base_sha = ADVANCED
            return original_document(*a, **kw)
        monkeypatch.setattr(work.proof_document, "document", document)
    else:
        transport.after_effect = lambda endpoint: setattr(transport, "base_sha", ADVANCED)
    with pytest.raises(work.WorkError, match="base tip moved") as error:
        work._execute_proof(transport, state, root, RULES, path, None, None)
    assert error.value.version_obligation["status"] == "unverifiable"
    assert error.value.version_obligation["policy_view"] == "committed"
    assert bool(compositions) is (moment != "before-composition")
    assert bool(transport.effects) is (moment == "after-publication")
    if moment == "after-publication":
        assert "proof comment" in str(error.value) and "published and is preserved" in str(error.value)
    assert not any(effect[1].endswith("/rerun") for effect in transport.effects)


def test_C5_policy_movement_before_proof_composition_retains_committed_context(tmp_path, monkeypatch):
    state, transport = fixture_state(version="2.10.0")
    root = tmp_path / "adopter"
    path = adopted_repository(root)
    original_prepare = work.prepare_use_evidence
    def prepare(*a):
        original_prepare(*a)
        path.write_bytes(json.dumps({**RULES, "version": {**SPEC, "increment": "major"}}).encode())
    monkeypatch.setattr(work, "prepare_use_evidence", prepare)
    monkeypatch.setattr(work, "compose_proof", lambda *a: pytest.fail("moving policy composed proof"))
    with pytest.raises(work.WorkError) as error:
        work._execute_proof(transport, state, root, RULES, path, None, None)
    report = error.value.version_obligation
    assert report["status"] == "unverifiable" and report["policy_view"] == "committed"
    assert report["target"] == "2.10.0" and not transport.effects


def test_C3_read_only_routing_refuses_owed_unmet_version(tmp_path, capsys):
    state, transport = fixture_state()
    root = tmp_path / "adopter"
    adopted_repository(root)
    args = work.parser().parse_args(["--repo", REPO, "--issue", "12", "--root", str(root)])
    assert work.run(args, transport=transport) == 0
    report = json.loads(capsys.readouterr().out)
    assert (report["stage"], report["reason"]) == ("ready-reviewers", "version-obligation-blocked")
    assert not transport.effects


def test_C3_custom_dispatch_is_preserved_and_does_not_waive_guard(tmp_path, capsys, monkeypatch):
    state, transport = fixture_state()
    root = tmp_path / "adopter"
    adopted_repository(root)
    dispatch = tmp_path / "custom.txt"
    dispatch.write_bytes(b"Keep these exact custom-dispatch bytes.\r\n")
    before = dispatch.read_bytes()
    # Custom bytes bypass composition, including a base-version read prerequisite.
    monkeypatch.setattr(work, "_compose_version_instruction", lambda *a: pytest.fail("rewrote custom dispatch"))
    monkeypatch.setattr(work, "_stage_prompt", lambda *a, **kw: pytest.fail("rewrote custom dispatch"))
    seen = []
    def allocation(*a, **kw):
        seen.append(dispatch.read_bytes())
        raise work.WorkError("Custom prompt passed preflight")
    monkeypatch.setattr(work, "create_implementation_root", allocation)
    first, _ = fixture_state(pr=False)
    assert work.execute_stage(first, work.Decision("build", True, "fresh", "fixture"), root, None, "holder",
                              dispatch_path=dispatch, transport=transport, rules=RULES) == 0
    assert seen == [before] and "Custom prompt passed preflight" in capsys.readouterr().out
    # A supplied builder dispatch has no authority over the later holder endpoints.
    assert named("ready-reviewers", state, transport, root) == 0
    assert dispatch.read_bytes() == before and not transport.effects
    assert json.loads(capsys.readouterr().out)["reason"] == "version-obligation-blocked"


@pytest.mark.parametrize("moment", ["before-effect", "after-label"])
def test_C5_version_basis_guard_also_protects_a_legacy_floor(moment, tmp_path):
    state, transport = fixture_state(version="2.10.0")
    root = tmp_path / "adopter"
    adopted_repository(root)
    # A legacy authorized floor marker has no public pinned base; the version
    # check therefore protects an input class the floor identity guard cannot.
    work.validate_marker_claims(state)
    assert state.floor_public is None and work.floor_evaluation(state)["satisfied"]
    if moment == "after-label":
        transport.after_effect = lambda endpoint: setattr(transport, "base_sha", ADVANCED)
    else:
        transport.before_get = lambda endpoint: setattr(transport, "base_sha", ADVANCED) if endpoint == f"repos/{REPO}/issues/7" else None
    with pytest.raises(work.WorkError, match="version base tip moved") as error:
        work._execute_ready_reviewers(transport, state, RULES, None, None)
    assert error.value.version_obligation["status"] == "unverifiable"
    assert bool(transport.effects) is (moment == "after-label")
    assert not any(effect[0] == "GRAPHQL" for effect in transport.effects)
    if moment == "after-label":
        assert "reviewer label was applied" in str(error.value)


def test_C5_cached_proof_cannot_be_current_when_head_moves_before_freshness(tmp_path, monkeypatch, capsys):
    state, transport = fixture_state(version="2.10.0", draft=False)
    root = tmp_path / "adopter"
    path = adopted_repository(root)
    assert work._execute_proof(transport, state, root, RULES, path, None, None) == 0
    capsys.readouterr()
    assert transport.comments and transport.effects
    effects = deepcopy(transport.effects)
    original = work._assess_version
    def assess_then_move(*a, **kw):
        report = original(*a, **kw)
        if kw.get("view") == "committed":
            transport.state.pr["head"]["sha"] = "e" * 40
        return report
    monkeypatch.setattr(work, "_assess_version", assess_then_move)
    monkeypatch.setattr(work, "compose_proof", lambda *a: pytest.fail("stale version evidence composed expected proof"))
    args = work.parser().parse_args(["--repo", REPO, "--issue", "12", "--root", str(root)])
    assert work.run(args, transport=transport) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["stage"] == "proof" and report["reason"] == "version-obligation-unverifiable"
    assert report["proof_version_obligation"]["head"]["sha"] == HEAD
    assert "identity moved" in report["proof_version_obligation"]["message"]
    assert transport.effects == effects


@pytest.mark.parametrize("committed", [False, True])
def test_C5_policy_movement_during_inspection_withholds_expected_proof(committed, tmp_path, monkeypatch, capsys):
    state, transport = fixture_state(version="2.10.0", draft=False)
    root = tmp_path / "adopter"
    path = adopted_repository(root)
    original = work.prepare_use_evidence
    moved = []
    def prepare(*a):
        original(*a)
        if not moved:
            moved.append(True)
            path.write_bytes(json.dumps({**RULES, "version": {**SPEC, "increment": "major"}}).encode())
            if committed:
                for command in (["git", "add", "--", str(path.relative_to(root))],
                                ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
                                 "commit", "-m", "fixture policy movement"]):
                    subprocess.run(command, cwd=root, check=True, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    monkeypatch.setattr(work, "prepare_use_evidence", prepare)
    monkeypatch.setattr(work, "compose_proof", lambda *a: pytest.fail("moving policy composed expected proof"))
    args = work.parser().parse_args(["--repo", REPO, "--issue", "12", "--root", str(root)])
    assert work.run(args, transport=transport) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["version_obligation"]["status"] == "unverifiable"
    assert report["version_obligation"]["target"] == "2.10.0"
    assert report["proof_version_obligation"]["status"] == ("unverifiable" if committed else "satisfied")
    assert not transport.effects


def test_C5_committed_policy_moves_while_selected_policy_is_unchanged(tmp_path, monkeypatch, capsys):
    state, transport = fixture_state(version="2.10.0", draft=False)
    root = tmp_path / "adopter"
    path = adopted_repository(root)
    selected = {key: value for key, value in RULES.items() if key != "version"}
    path.write_bytes(json.dumps(selected).encode())
    original = work.prepare_use_evidence
    moved = []
    def prepare(*a):
        original(*a)
        if not moved:
            moved.append(True)
            config = root / ".tradecraft/work.json"
            value = json.loads(config.read_bytes())
            value["marker_producers"].append("extra-fixture-producer")
            config.write_bytes(json.dumps(value).encode())
            for command in (["git", "add", "--", str(config.relative_to(root))],
                            ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
                             "commit", "-m", "fixture committed policy movement"]):
                subprocess.run(command, cwd=root, check=True, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    monkeypatch.setattr(work, "prepare_use_evidence", prepare)
    monkeypatch.setattr(work, "compose_proof", lambda *a: pytest.fail("moving committed view composed expected proof"))
    args = work.parser().parse_args(["--repo", REPO, "--issue", "12", "--root", str(root)])
    assert work.run(args, transport=transport) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["version_obligation"]["status"] == "undeclared"
    assert report["proof_version_obligation"]["status"] == "unverifiable"
    assert "HEAD changed" in report["proof_version_obligation"]["message"]
    assert not transport.effects

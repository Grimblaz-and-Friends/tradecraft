from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import proof


SHA = "a" * 40


def source(kind="pull-request-comment", identity=31):
    return {
        "kind": kind,
        "repository": "example/product",
        "id": identity,
        "url": f"https://github.example/source/{identity}",
        "author": "holder",
        "timestamp": "2026-09-23T12:00:00Z",
        "revision": SHA,
    }


def document():
    return {
        "schema_version": 1,
        "identity": {
            "work": "example/product#12",
            "repository": "example/product",
            "issue": 12,
            "pull_request": 19,
            "head": SHA,
            "producer_version": "0.153.0",
        },
        "policy": {
            "work_configuration": {
                "repository": "example/product", "path": ".tradecraft/work.json",
                "revision": SHA, "sha256": "1" * 64,
            },
            "use_rules": {
                "repository": "example/product", "path": "lib/use-rules.json",
                "revision": SHA, "sha256": "2" * 64,
            },
        },
        "floor": {"head": SHA, "source": source(), "checks": []},
        "use": {
            "required": True,
            "classification": "required",
            "evidence_head": SHA,
            "applicability": "current-head",
            "source": source(identity=32),
            "intervening_commits": [],
            "reason": "a changed path matches the use policy",
        },
        "reviewers": [
            {"login": "z-reviewer[bot]", "result": "missing", "source": None,
             "notices": []},
            {"login": "a-reviewer[bot]", "result": "present", "source": source("review", 33),
             "notices": []},
        ],
        "dispositions": [{
            "thread_id": 40, "reviewer": "a-reviewer[bot]", "source": source("review-comment", 40),
            "reply": None,
        }],
        "declarations": [{
            "stage": "use", "status": "unverifiable", "reason": "no matching bundle",
            "dispatch_id": None, "completed_at": None, "revision": None,
            "requested_vendor": None, "requested_model": None, "requested_effort": None,
            "requested_classification": None, "actual_vendor": None,
            "actual_model": None, "actual_effort": None, "fallback_reason": None,
            "staffing_status": None, "same_vendor_reason": None,
        }],
        "diagnostics": [{
            "code": "reviewer-missing", "message": "z-reviewer[bot] has no receipt",
            "source": None,
        }],
    }


def test_composition_is_deterministic_and_discards_a_typed_success_claim():
    first = document()
    first["verified"] = True
    second = document()
    second["reviewers"].reverse()

    composed_first = proof.compose(first)
    composed_second = proof.compose(second)

    assert "verified" not in composed_first
    assert proof.canonical_json(composed_first) == proof.canonical_json(composed_second)
    assert [item["login"] for item in composed_first["reviewers"]] == [
        "a-reviewer[bot]", "z-reviewer[bot]",
    ]


def test_validation_rejects_a_verification_field_anywhere():
    value = document()
    value["floor"]["verified"] = True
    with pytest.raises(proof.ProofError, match="wrong fields|verification field"):
        proof.validate(value)


def test_document_carries_one_json_object_readable_labels_and_legacy_no_use():
    value = document()
    value["use"].update({
        "required": False, "classification": "not-required", "evidence_head": SHA,
        "applicability": "generated", "source": None,
        "reason": "no changed path matches a use-bought rule",
    })
    rendered = proof.document(value, "Use: not required - no changed path buys use.")
    payload = rendered.split("```json\n", 1)[1].split("\n```", 1)[0]

    assert json.loads(payload) == proof.validate(value)
    assert rendered.count("<!-- tradecraft:proof:v1") == 1
    assert rendered.count("<!-- tradecraft:no-use:v1") == 1
    assert "- evidence:" in rendered
    assert "use reason no changed path matches a use-bought rule; source none" in rendered
    assert "- declared:" in rendered
    assert "- verified:" not in rendered


def test_unverifiable_declaration_requires_a_reason():
    value = document()
    value["declarations"][0]["reason"] = None
    with pytest.raises(proof.ProofError, match="must carry a reason"):
        proof.validate(value)


def test_shipped_positive_fixture_is_canonical_and_negative_cases_name_rejections():
    references = LIB.parent / "skills" / "work" / "references" / "proof-fixtures"
    if not references.exists():
        pytest.skip("proof fixtures are outside a relocated lib-only installation")
    valid = json.loads((references / "v1-valid.json").read_bytes())
    negative = json.loads((references / "v1-negative-cases.json").read_bytes())

    assert proof.validate(valid) == valid
    assert proof.canonical_json(valid).encode("utf-8") == (
        references / "v1-valid.json"
    ).read_bytes()
    assert {case["name"] for case in negative} >= {
        "wrong-head", "substituted-floor-check", "omitted-configured-reviewer",
        "non-review-notice", "unauthorized-disposition", "omitted-thread",
        "declaration-rendered-as-verified", "producer-verification-field",
    }
    for case in negative:
        candidate = deepcopy(valid)
        candidate.update(deepcopy(case["document_patch"]))
        if case["name"] == "producer-verification-field":
            with pytest.raises(proof.ProofError):
                proof.validate(candidate)
        else:
            assert proof.validate(candidate) == candidate

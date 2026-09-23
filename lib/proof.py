"""Compose and validate the version-one change-proof document."""
from __future__ import annotations

from copy import deepcopy
import json
import re


HEAD_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z", re.I)
SOURCE_KEYS = {
    "kind", "repository", "id", "url", "author", "timestamp", "revision",
}
CHECK_KEYS = {
    "id", "name", "app_id", "app_slug", "workflow_id", "run_id", "url",
    "head", "status", "conclusion", "started_at", "completed_at",
}
DECLARATION_KEYS = {
    "stage", "status", "reason", "dispatch_id", "completed_at", "revision",
    "requested_vendor", "requested_model", "requested_effort",
    "requested_classification", "actual_vendor", "actual_model", "actual_effort",
    "fallback_reason", "staffing_status", "same_vendor_reason",
}
TOP_LEVEL_KEYS = {
    "schema_version", "identity", "policy", "floor", "use", "reviewers",
    "dispositions", "declarations", "diagnostics",
}


class ProofError(ValueError):
    """A proof document cannot satisfy the public version-one contract."""


def _object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProofError(f"{name} must be an object")
    return value


def _list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ProofError(f"{name} must be a list")
    return value


def _exact_keys(value: dict[str, object], keys: set[str], name: str) -> None:
    if set(value) != keys:
        missing = sorted(keys - set(value))
        extra = sorted(set(value) - keys)
        detail = []
        if missing:
            detail.append("missing=" + ",".join(missing))
        if extra:
            detail.append("extra=" + ",".join(extra))
        raise ProofError(f"{name} has the wrong fields: {';'.join(detail)}")


def _nullable_text(value: object, name: str) -> None:
    if value is not None and not isinstance(value, str):
        raise ProofError(f"{name} must be text or null")


def _source(value: object, name: str) -> None:
    if value is None:
        return
    source = _object(value, name)
    _exact_keys(source, SOURCE_KEYS, name)
    if not isinstance(source["kind"], str) or not source["kind"]:
        raise ProofError(f"{name}.kind must be nonempty text")
    if not isinstance(source["repository"], str) or not source["repository"]:
        raise ProofError(f"{name}.repository must be nonempty text")
    if source["id"] is not None and not isinstance(source["id"], (str, int)):
        raise ProofError(f"{name}.id must be text, an integer, or null")
    for field in ("url", "author", "timestamp", "revision"):
        _nullable_text(source[field], f"{name}.{field}")


def _policy_source(value: object, name: str) -> None:
    source = _object(value, name)
    _exact_keys(source, {"repository", "path", "revision", "sha256"}, name)
    for field in source:
        if not isinstance(source[field], str) or not source[field]:
            raise ProofError(f"{name}.{field} must be nonempty text")


def _reject_verified(value: object, name: str = "proof") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.casefold().startswith("verified"):
                raise ProofError(f"{name} cannot carry a producer verification field")
            _reject_verified(child, f"{name}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_verified(child, f"{name}[{index}]")


def validate(value: object) -> dict[str, object]:
    """Return a deep copy after validating the strict version-one schema."""
    proof = _object(value, "proof")
    _exact_keys(proof, TOP_LEVEL_KEYS, "proof")
    _reject_verified(proof)
    if proof["schema_version"] != 1:
        raise ProofError("proof.schema_version must be 1")

    identity = _object(proof["identity"], "proof.identity")
    _exact_keys(identity, {
        "work", "repository", "issue", "pull_request", "head", "producer_version",
    }, "proof.identity")
    if not all(isinstance(identity[field], str) and identity[field]
               for field in ("work", "repository", "producer_version")):
        raise ProofError("proof identity text fields must be nonempty")
    if not all(isinstance(identity[field], int) and not isinstance(identity[field], bool)
               and identity[field] > 0 for field in ("issue", "pull_request")):
        raise ProofError("proof issue and pull_request must be positive integers")
    if not isinstance(identity["head"], str) or HEAD_SHA.fullmatch(identity["head"]) is None:
        raise ProofError("proof identity head must be a full revision")

    policy = _object(proof["policy"], "proof.policy")
    _exact_keys(policy, {"work_configuration", "use_rules"}, "proof.policy")
    _policy_source(policy["work_configuration"], "proof.policy.work_configuration")
    _policy_source(policy["use_rules"], "proof.policy.use_rules")

    floor = _object(proof["floor"], "proof.floor")
    _exact_keys(floor, {"head", "source", "checks"}, "proof.floor")
    _nullable_text(floor["head"], "proof.floor.head")
    _source(floor["source"], "proof.floor.source")
    for index, item in enumerate(_list(floor["checks"], "proof.floor.checks")):
        check = _object(item, f"proof.floor.checks[{index}]")
        _exact_keys(check, CHECK_KEYS, f"proof.floor.checks[{index}]")
        if not isinstance(check["name"], str) or not check["name"]:
            raise ProofError(f"proof.floor.checks[{index}].name must be nonempty text")
        for field in CHECK_KEYS - {"name"}:
            if check[field] is not None and not isinstance(check[field], (str, int)):
                raise ProofError(
                    f"proof.floor.checks[{index}].{field} must be text, an integer, or null"
                )

    use = _object(proof["use"], "proof.use")
    _exact_keys(use, {
        "required", "classification", "evidence_head", "applicability", "source",
        "intervening_commits", "reason",
    }, "proof.use")
    if not isinstance(use["required"], bool):
        raise ProofError("proof.use.required must be boolean")
    if use["classification"] not in {"required", "not-required"}:
        raise ProofError("proof.use.classification is invalid")
    if use["applicability"] not in {"current-head", "ancestor", "generated", "missing"}:
        raise ProofError("proof.use.applicability is invalid")
    _nullable_text(use["evidence_head"], "proof.use.evidence_head")
    _nullable_text(use["reason"], "proof.use.reason")
    _source(use["source"], "proof.use.source")
    for index, item in enumerate(_list(
            use["intervening_commits"], "proof.use.intervening_commits")):
        commit = _object(item, f"proof.use.intervening_commits[{index}]")
        _exact_keys(commit, {"sha", "paths"}, f"proof.use.intervening_commits[{index}]")
        if not isinstance(commit["sha"], str) or HEAD_SHA.fullmatch(commit["sha"]) is None:
            raise ProofError("an intervening commit has no full revision")
        if not isinstance(commit["paths"], list) or not all(
                isinstance(path, str) for path in commit["paths"]):
            raise ProofError("an intervening commit path list is invalid")

    for index, item in enumerate(_list(proof["reviewers"], "proof.reviewers")):
        reviewer = _object(item, f"proof.reviewers[{index}]")
        _exact_keys(reviewer, {"login", "result", "source", "notices"},
                    f"proof.reviewers[{index}]")
        if not isinstance(reviewer["login"], str) or not reviewer["login"]:
            raise ProofError("a reviewer login must be nonempty")
        if reviewer["result"] not in {"present", "missing", "notice-only"}:
            raise ProofError("a reviewer result is invalid")
        _source(reviewer["source"], f"proof.reviewers[{index}].source")
        if not isinstance(reviewer["notices"], list) or not all(
                isinstance(notice, str) for notice in reviewer["notices"]):
            raise ProofError("a reviewer notice list is invalid")

    for index, item in enumerate(_list(proof["dispositions"], "proof.dispositions")):
        disposition = _object(item, f"proof.dispositions[{index}]")
        _exact_keys(disposition, {"thread_id", "reviewer", "source", "reply"},
                    f"proof.dispositions[{index}]")
        if not isinstance(disposition["thread_id"], int):
            raise ProofError("a disposition thread id must be an integer")
        if not isinstance(disposition["reviewer"], str):
            raise ProofError("a disposition reviewer must be text")
        _source(disposition["source"], f"proof.dispositions[{index}].source")
        _source(disposition["reply"], f"proof.dispositions[{index}].reply")

    for index, item in enumerate(_list(proof["declarations"], "proof.declarations")):
        declaration = _object(item, f"proof.declarations[{index}]")
        _exact_keys(declaration, DECLARATION_KEYS, f"proof.declarations[{index}]")
        if declaration["status"] not in {"declared", "unverifiable"}:
            raise ProofError("a declaration status is invalid")
        if not isinstance(declaration["stage"], str) or not declaration["stage"]:
            raise ProofError("a declaration stage must be nonempty")
        for field in DECLARATION_KEYS - {"stage", "status"}:
            _nullable_text(declaration[field], f"proof.declarations[{index}].{field}")
        if declaration["status"] == "unverifiable" and not declaration["reason"]:
            raise ProofError("an unverifiable declaration must carry a reason")

    for index, item in enumerate(_list(proof["diagnostics"], "proof.diagnostics")):
        diagnostic = _object(item, f"proof.diagnostics[{index}]")
        _exact_keys(diagnostic, {"code", "message", "source"},
                    f"proof.diagnostics[{index}]")
        if not all(isinstance(diagnostic[field], str) and diagnostic[field]
                   for field in ("code", "message")):
            raise ProofError("a diagnostic code and message must be nonempty")
        _source(diagnostic["source"], f"proof.diagnostics[{index}].source")
    return deepcopy(proof)


def compose(evidence: dict[str, object]) -> dict[str, object]:
    """Compose the contract fields and discard caller-supplied conclusions."""
    proof = {key: deepcopy(evidence[key]) for key in TOP_LEVEL_KEYS}
    proof["schema_version"] = 1
    proof["reviewers"] = sorted(proof["reviewers"], key=lambda item: item["login"])
    proof["dispositions"] = sorted(
        proof["dispositions"], key=lambda item: item["thread_id"]
    )
    proof["declarations"] = sorted(
        proof["declarations"],
        key=lambda item: (item["stage"], item["dispatch_id"] or ""),
    )
    proof["diagnostics"] = sorted(
        proof["diagnostics"], key=lambda item: (item["code"], item["message"])
    )
    proof["floor"]["checks"] = sorted(
        proof["floor"]["checks"],
        key=lambda item: (
            item["name"], item["app_slug"] or "", str(item["workflow_id"] or ""),
            str(item["run_id"] or ""), str(item["id"] or ""),
        ),
    )
    return validate(proof)


def canonical_json(value: dict[str, object]) -> str:
    """Serialize proof content deterministically for publication and fixtures."""
    return json.dumps(validate(value), ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def render(value: dict[str, object]) -> str:
    """Render every proof section without claiming independent verification."""
    proof = validate(value)
    identity = proof["identity"]
    floor = proof["floor"]
    use = proof["use"]
    lines = [
        "### Readable proof",
        "",
        f"- evidence: {identity['work']} pull request #{identity['pull_request']} at {identity['head']}",
        f"- evidence: floor source {('present' if floor['source'] else 'missing')}; "
        f"{len(floor['checks'])} public check record(s)",
        f"- evidence: use classification {use['classification']}; applicability "
        f"{use['applicability']}",
    ]
    for reviewer in proof["reviewers"]:
        lines.append(f"- evidence: reviewer {reviewer['login']}: {reviewer['result']}")
    for disposition in proof["dispositions"]:
        result = "present" if disposition["reply"] else "missing"
        lines.append(f"- evidence: disposition for thread {disposition['thread_id']}: {result}")
    for declaration in proof["declarations"]:
        detail = declaration["dispatch_id"] or declaration["reason"] or "no detail"
        lines.append(
            f"- declared: {declaration['stage']}: {declaration['status']} ({detail})"
        )
    for diagnostic in proof["diagnostics"]:
        lines.append(f"- diagnostic: {diagnostic['code']}: {diagnostic['message']}")
    return "\n".join(lines) + "\n"


def document(value: dict[str, object], no_use_line: str | None = None) -> str:
    """Build the marked comment containing JSON, its rendering, and a legacy carrier."""
    proof = validate(value)
    head = proof["identity"]["head"]
    parts = [
        f"<!-- tradecraft:proof:v1 head={head} -->",
        "```json\n" + canonical_json(proof).rstrip("\n") + "\n```",
        render(proof).rstrip("\n"),
    ]
    if no_use_line is not None:
        parts.append(f"<!-- tradecraft:no-use:v1 head={head} -->\n{no_use_line}")
    return "\n\n".join(parts) + "\n"

import base64
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cold_draft
import source_claims

DRAFT = "<!-- tradecraft:artifact:v1 status=draft -->\nWhole draft with Unicode " + chr(0xE9) + " and trailing spaces.  \n"


def draft_get(endpoint):
    if endpoint.endswith("/.tradecraft/work.json"):
        return {"encoding": "base64", "content": base64.b64encode(json.dumps({
            "schema_version": 1, "marker_producers": ["holder"],
        }).encode()).decode()}
    return {"id": 20, "body": DRAFT, "user": {"login": "holder"},
            "issue_url": "https://api.github.com/repos/example/product/issues/12"}


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
def test_C3_complete_utf8_slice_and_lf_digest_are_different_checks(ending):
    body = DRAFT.replace("\n", ending)
    prompt = b"Outer dispatch\n" + body.encode() + b"\nReturn a verdict.\n"
    binding = cold_draft.freeze("20", body, prompt)
    assert binding == {"comment_id": "20", "sha256": cold_draft.artifact_digest(DRAFT),
                       "sha256_basis": cold_draft.DIGEST_BASIS,
                       "body_offset": len(b"Outer dispatch\n"), "body_bytes": len(body.encode())}
    assert cold_draft.validate(binding, prompt) == binding
    for substitute in [body.strip(), body.replace("  ", " "), body[10:]]:
        with pytest.raises(cold_draft.BindingError, match="whole body byte for byte"):
            cold_draft.freeze("20", body, substitute.encode())
    if ending != "\n":
        with pytest.raises(cold_draft.BindingError, match="byte for byte"):
            cold_draft.freeze("20", body, DRAFT.encode())


@pytest.mark.parametrize("field,value", [
    ("comment_id", 20), ("comment_id", "0"), ("comment_id", "020"),
    ("sha256", "a" * 63), ("sha256", "A" * 64), ("sha256_basis", "whole-dispatch"),
    ("body_offset", True), ("body_offset", -1), ("body_offset", 100000),
    ("body_bytes", False), ("body_bytes", 0), ("body_bytes", 100000),
])
def test_C3_C4_invalid_binding_fields_have_lawful_control(field, value):
    prompt = DRAFT.encode()
    binding = cold_draft.freeze("20", DRAFT, prompt)
    assert cold_draft.validate(binding, prompt) == binding
    binding[field] = value
    with pytest.raises(cold_draft.BindingError):
        cold_draft.validate(binding, prompt)


def test_C3_C4_recomputed_slice_and_request_completion_agreement(tmp_path):
    prompt = DRAFT.encode()
    path = tmp_path / "dispatch.bin"
    path.write_bytes(prompt)
    binding = cold_draft.freeze("20", DRAFT, prompt)
    request = {"producer_version": cold_draft.BINDING_VERSION, "input": str(path), "judged_draft": binding}
    run = {"judged_draft": deepcopy(binding)}
    assert cold_draft.completed_binding(request, run) == binding
    for change in [None, {**binding, "comment_id": "21"}, {**binding, "body_offset": False}]:
        with pytest.raises(cold_draft.BindingError):
            cold_draft.completed_binding(request, {"judged_draft": change})
    path.write_bytes(prompt.replace(b"Whole", b"Other"))
    with pytest.raises(cold_draft.BindingError, match="digest disagrees"):
        cold_draft.completed_binding(request, run)
    path.write_bytes(prompt)
    bad = {**binding, "body_offset": prompt.index(chr(0xE9).encode()) + 1,
           "body_bytes": 1}
    with pytest.raises(cold_draft.BindingError, match="not UTF-8"):
        cold_draft.validate(bad, prompt)


@pytest.mark.parametrize("version,old", [("0.189.0", True), ("0.189.9+build", True),
                                        ("0.190.0", False), ("0.191.0", False)])
def test_C4_actual_introduction_boundary(version, old):
    request = {"producer_version": version}
    if old:
        assert cold_draft.completed_binding(request, {}) is None
    else:
        with pytest.raises(cold_draft.BindingError):
            cold_draft.completed_binding(request, {})


@pytest.mark.parametrize("version", [None, "", "unknown", "0.0189.0"])
def test_C4_missing_provenance_is_not_historical(version):
    with pytest.raises(cold_draft.BindingError, match="proved producer version"):
        cold_draft.completed_binding({"producer_version": version}, {})


@pytest.mark.parametrize("problem", ["wrong-id", "wrong-issue", "no-body", "not-draft", "quoted", "prose-first",
                                   "unknown-attribute", "duplicate", "unauthorized", "unavailable"])
def test_C3_authenticated_resolution_refuses_bad_sources(problem):
    assert cold_draft.resolve_draft("example/product#12", "20", get=draft_get) == ("20", DRAFT)
    def get(endpoint):
        value = draft_get(endpoint)
        if "/issues/comments/" not in endpoint:
            return value
        if problem == "unavailable":
            raise cold_draft.BindingError("GitHub GET failed")
        if problem == "wrong-id": value["id"] = 21
        if problem == "wrong-issue": value["issue_url"] = value["issue_url"].replace("/12", "/13")
        if problem == "no-body": value["body"] = None
        if problem == "not-draft": value["body"] = DRAFT.replace("status=draft", "status=settled")
        if problem == "quoted": value["body"] = "> " + DRAFT
        if problem == "prose-first": value["body"] = "Preamble\n" + DRAFT
        if problem == "unknown-attribute": value["body"] = DRAFT.replace(" -->", " extra=x -->")
        if problem == "duplicate": value["body"] = DRAFT.replace(" -->", " status=draft -->")
        if problem == "unauthorized": value["user"]["login"] = "outsider"
        with_body = source_claims._classify_sources([(value.get("body") or "", "holder")])
        assert with_body is not None
        return value
    with pytest.raises(cold_draft.BindingError):
        cold_draft.resolve_draft("example/product#12", "20", get=get)


@pytest.mark.parametrize("identity", [None, "0", "020", "abc"])
def test_C3_missing_or_invalid_id_refuses_without_get(identity):
    with pytest.raises(cold_draft.BindingError, match="draft-comment"):
        cold_draft.resolve_draft("example/product#12", identity, get=lambda *_: pytest.fail("GET occurred"))


def test_C3_get_is_authenticated_and_names_all_streams(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, json.dumps(draft_get(command[-1])).encode(), b"")
    monkeypatch.setattr(cold_draft.subprocess, "run", run)
    assert cold_draft.resolve_draft("example/product#12", "20") == ("20", DRAFT)
    assert len(calls) == 2
    for command, kwargs in calls:
        assert command[:4] == ["gh", "api", "--method", "GET"]
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["stdout"] == kwargs["stderr"] == subprocess.PIPE


@pytest.mark.parametrize("identity,body", [("0", DRAFT), (None, DRAFT), ("20", ""), ("20", None)])
def test_C3_freeze_requires_canonical_body_and_positive_id(identity, body):
    with pytest.raises(cold_draft.BindingError): cold_draft.freeze(identity, body, DRAFT.encode())


def test_C3_bounded_retained_reads_and_dispatches_have_small_lawful_control(tmp_path, monkeypatch):
    path = tmp_path / "dispatch.bin"
    path.write_bytes(DRAFT.encode())
    monkeypatch.setattr(cold_draft, "MAX_INPUT_BYTES", len(DRAFT.encode()))
    assert cold_draft.read_input(path) == DRAFT.encode()
    assert cold_draft.freeze("20", DRAFT, path.read_bytes())
    path.write_bytes(DRAFT.encode() + b"extra")
    with pytest.raises(cold_draft.BindingError, match="input bound"): cold_draft.read_input(path)
    with pytest.raises(cold_draft.BindingError, match="input bound"):
        cold_draft.freeze("20", DRAFT, path.read_bytes())


@pytest.mark.parametrize("work_value", ["issue-12", "example/product#0", "example/product#12/extra"])
def test_C3_work_identity_is_resolved_before_get(work_value):
    with pytest.raises(cold_draft.BindingError, match="OWNER/REPO#N"):
        cold_draft.resolve_draft(work_value, "20", get=lambda *_: pytest.fail("GET occurred"))


@pytest.mark.parametrize("result", [subprocess.CompletedProcess([], 1, b"{}", b"failed"),
                                  subprocess.CompletedProcess([], 0, b"not JSON", b"")])
def test_C3_failed_get_or_unavailable_canonical_response_refuses(monkeypatch, result):
    monkeypatch.setattr(cold_draft.subprocess, "run", lambda *_a, **_k: result)
    with pytest.raises(cold_draft.BindingError, match="GitHub GET"):
        cold_draft._get("repos/example/product/issues/comments/20")


@pytest.mark.parametrize("failure", [OSError("gh could not launch"), subprocess.TimeoutExpired(["gh", "api"], 120)])
def test_C3_get_launch_failure_and_timeout_are_named_binding_refusals(monkeypatch, failure):
    def run(*_args, **_kwargs):
        raise failure
    monkeypatch.setattr(cold_draft.subprocess, "run", run)
    with pytest.raises(cold_draft.BindingError, match="GitHub GET failed for repos/example/product/issues/comments/20"):
        cold_draft.resolve_draft("example/product#12", "20")


@pytest.mark.parametrize("configuration", [{}, {"encoding": "base64", "content": "not base64"},
                                           {"encoding": "base64", "content": base64.b64encode(b'{}').decode()},
                                           {"encoding": "raw", "content": draft_get("x/.tradecraft/work.json")["content"]},
                                           {"encoding": "base64", "content": base64.b64encode(json.dumps({
                                               "schema_version": 2, "marker_producers": ["holder"],
                                           }).encode()).decode()}])
def test_C3_unproved_producer_configuration_refuses(configuration):
    def get(endpoint):
        return configuration if endpoint.endswith("/.tradecraft/work.json") else draft_get(endpoint)
    with pytest.raises(cold_draft.BindingError, match="authorized draft producers"):
        cold_draft.resolve_draft("example/product#12", "20", get=get)


@pytest.mark.parametrize("binding", [None, [], {"extra": "field"}])
def test_C3_binding_representation_is_exact(binding):
    if isinstance(binding, dict): binding.update(cold_draft.freeze("20", DRAFT, DRAFT.encode()))
    with pytest.raises(cold_draft.BindingError, match="missing or malformed"):
        cold_draft.validate(binding, DRAFT.encode())


@pytest.mark.parametrize("problem", ["missing", "unauthorized", "malformed"])
def test_C3_882_direct_and_native_resolution_name_default_branch_prerequisite(problem):
    def get(endpoint):
        value = draft_get(endpoint)
        if "/issues/comments/" in endpoint:
            if problem == "unauthorized": value["user"]["login"] = "new-holder"
            return value
        if problem == "missing": raise cold_draft.BindingError("GitHub GET failed: 404")
        if problem == "malformed": return {}
        return value
    with pytest.raises(cold_draft.BindingError, match=r"default branch must carry \.tradecraft/work\.json listing the producer"):
        cold_draft.resolve_draft("example/product#12", "20", get=get)


def test_C3_882_entrance_producers_are_authoritative_without_default_branch_lookup():
    calls = []
    def get(endpoint):
        calls.append(endpoint)
        assert "/issues/comments/" in endpoint
        value = draft_get(endpoint)
        value["user"]["login"] = "New-Holder"
        return value
    assert cold_draft.resolve_draft("example/product#12", "20", get=get,
                                   marker_producers=frozenset({"new-holder"})) == ("20", DRAFT)
    assert len(calls) == 1
    with pytest.raises(cold_draft.BindingError, match="producer is not authorized"):
        cold_draft.resolve_draft("example/product#12", "20", get=get,
                                 marker_producers=frozenset({"holder"}))

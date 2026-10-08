"""Freeze and validate the draft bytes an artifact cold seat receives."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess

import run_lifecycle as lifecycle
from source_claims import _classify_sources, attribute_error

BINDING_VERSION = "0.190.0"
DIGEST_BASIS = "whole-comment-body-lf-utf8"
MAX_INPUT_BYTES = 16 * 1024 * 1024
WORK = re.compile(r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([1-9][0-9]*)\Z")
COMMENT_ID = re.compile(r"[1-9][0-9]*\Z")


class BindingError(ValueError):
    """A cold judgment cannot prove which draft it received."""


def artifact_digest(body: str) -> str:
    return hashlib.sha256(body.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")).hexdigest()


def _get(endpoint: str) -> object:
    try:
        result = subprocess.run(
            ["gh", "api", "--method", "GET", endpoint],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=lifecycle.probe_timeout(120),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BindingError(f"GitHub GET failed for {endpoint}: {exc}") from exc
    if result.returncode:
        diagnostic = result.stderr.decode("utf-8", errors="backslashreplace").strip()
        raise BindingError(f"GitHub GET failed for {endpoint}: {diagnostic or result.returncode}")
    try:
        return json.loads(result.stdout)
    except (UnicodeError, ValueError) as exc:
        raise BindingError(f"GitHub GET returned invalid JSON for {endpoint}") from exc


def resolve_draft(work: str, comment_id: str | None, *, get=None) -> tuple[str, str]:
    """Resolve outside the recipient, using the entrance's source-claim grammar."""
    if not isinstance(comment_id, str) or COMMENT_ID.fullmatch(comment_id) is None:
        raise BindingError("cold-seat requires --draft-comment with a positive comment id")
    match = WORK.fullmatch(work)
    if match is None:
        raise BindingError("cold-seat requires --work OWNER/REPO#N")
    repository, issue = match.groups()
    get = get or _get
    source = get(f"repos/{repository}/issues/comments/{comment_id}")
    if not isinstance(source, dict) or str(source.get("id")) != comment_id:
        raise BindingError(f"named draft comment {comment_id} is missing or has the wrong id")
    expected_issue = f"https://api.github.com/repos/{repository}/issues/{issue}"
    if str(source.get("issue_url") or "").lower() != expected_issue.lower():
        raise BindingError(f"named draft comment {comment_id} belongs to another issue")
    body = source.get("body")
    if not isinstance(body, str) or not body:
        raise BindingError(f"named draft comment {comment_id} has no canonical body")
    user = source.get("user")
    author = user.get("login") if isinstance(user, dict) else None
    configuration = get(f"repos/{repository}/contents/.tradecraft/work.json")
    try:
        if not isinstance(configuration, dict) or configuration.get("encoding") != "base64":
            raise ValueError()
        config = json.loads(base64.b64decode(configuration["content"]))
        producers = config["marker_producers"]
        if (config.get("schema_version") != 1 or not isinstance(producers, list)
                or not all(isinstance(value, str) for value in producers)):
            raise ValueError()
    except (KeyError, TypeError, UnicodeError, ValueError) as exc:
        raise BindingError("cold-seat cannot establish authorized draft producers") from exc
    if not isinstance(author, str) or author.lower() not in {value.lower() for value in producers}:
        raise BindingError(f"named draft comment {comment_id} producer is not authorized")
    claims = _classify_sources([(body, author, "issue-comment", comment_id)]).claims
    if (len(claims) != 1 or claims[0].name != "artifact"
            or claims[0].attributes != {"status": "draft"}
            or attribute_error(claims[0], {"required": {"status"}, "optional": set()}) is not None):
        raise BindingError(f"named comment {comment_id} is not a lawful artifact draft")
    return comment_id, body


def freeze(comment_id: str, body: str, dispatch: bytes) -> dict[str, object]:
    if not isinstance(comment_id, str) or COMMENT_ID.fullmatch(comment_id) is None:
        raise BindingError("cold-seat requires a positive draft comment id")
    if not isinstance(body, str) or not body:
        raise BindingError("cold-seat requires the canonical draft body")
    if len(dispatch) > MAX_INPUT_BYTES:
        raise BindingError("cold-seat dispatch exceeds the retained input bound")
    dispatch.decode("utf-8")
    exact = body.encode("utf-8")
    offset = dispatch.find(exact)
    if offset < 0:
        raise BindingError(f"cold-seat dispatch does not carry draft comment {comment_id}'s whole body byte for byte")
    return {
        "comment_id": comment_id, "sha256": artifact_digest(body), "sha256_basis": DIGEST_BASIS,
        "body_offset": offset, "body_bytes": len(exact),
    }


def read_input(path: Path) -> bytes:
    with path.open("rb") as stream:
        content = stream.read(MAX_INPUT_BYTES + 1)
    if len(content) > MAX_INPUT_BYTES:
        raise BindingError("cold-seat retained input exceeds the input bound")
    return content


def validate(binding: object, dispatch: bytes) -> dict[str, object]:
    if not isinstance(binding, dict) or set(binding) != {
            "comment_id", "sha256", "sha256_basis", "body_offset", "body_bytes"}:
        raise BindingError("cold-seat judged_draft binding is missing or malformed")
    identity, digest = binding["comment_id"], binding["sha256"]
    offset, count = binding["body_offset"], binding["body_bytes"]
    if (not isinstance(identity, str) or COMMENT_ID.fullmatch(identity) is None
            or not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or binding["sha256_basis"] != DIGEST_BASIS
            or type(offset) is not int or offset < 0
            or type(count) is not int or count <= 0 or offset + count > len(dispatch)):
        raise BindingError("cold-seat judged_draft binding fields or retained slice are invalid")
    try:
        body = dispatch[offset:offset + count].decode("utf-8")
    except UnicodeError as exc:
        raise BindingError("cold-seat judged_draft slice is not UTF-8") from exc
    if artifact_digest(body) != digest:
        raise BindingError("cold-seat judged_draft digest disagrees with its retained input slice")
    return binding


def _historical(version: object) -> bool:
    if not isinstance(version, str) or re.fullmatch(
            r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
            r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?", version) is None:
        raise BindingError("cold-seat record has no proved producer version for judged-draft compatibility")
    core = tuple(int(value) for value in version.split("+", 1)[0].split("-", 1)[0].split("."))
    return core < tuple(int(value) for value in BINDING_VERSION.split("."))


def request_binding(request: dict[str, object]) -> dict[str, object] | None:
    if "judged_draft" not in request and _historical(request.get("producer_version")):
        return None
    binding = request.get("judged_draft")
    input_path = request.get("input")
    if not isinstance(input_path, str) or not input_path:
        raise BindingError("cold-seat binding requires retained exact input")
    return validate(binding, read_input(Path(input_path)))


def completed_binding(request: dict[str, object], run: dict[str, object]) -> dict[str, object] | None:
    binding = request_binding(request)
    if binding is None and "judged_draft" not in run:
        return None
    if binding is None or run.get("judged_draft") != binding:
        raise BindingError("cold-seat completed judged_draft disagrees with its frozen request")
    # Equality alone accepts bools as ints; validate the completion's types too.
    return validate(run["judged_draft"], read_input(Path(request["input"])))

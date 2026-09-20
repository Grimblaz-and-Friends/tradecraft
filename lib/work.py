#!/usr/bin/env python3
"""Read GitHub work state and dispatch exactly one stage."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass, field
import fnmatch
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Callable

import dispatch_record as records
from winio import utf8_stdio

COMMANDS = (
    "artifact", "cold-seat", "build", "floor", "use",
    "review-disposition", "release-report",
)
LANES = {
    "ordinary": "connected",
    "elevated": "routine-panel",
    "critical": "substantial-panel",
}
DISPOSITIONS = (
    "fixed", "fixed - nothing else found it", "fixed in #", "yours - in the release report",
    "declined -", "duplicate of ", "lapsed -",
)
MARKER = re.compile(r"<!--\s*tradecraft:([a-z-]+):v1(?:\s+([^>]*?))?\s*-->", re.I)
ATTRIBUTE = re.compile(r"([a-z_]+)=([^\s]+)", re.I)
CLOSING_REFERENCE = re.compile(
    r"(?im)^\s*(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?)\s+#([1-9][0-9]*)\s*$"
)
ISSUE_URL = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/issues/([1-9][0-9]*)",
    re.I,
)
REPOSITORY_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
GITHUB_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\[bot\])?\Z")
SESSION_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f-]{27,}\Z", re.I)
WORK_EVIDENCE_MARKERS = frozenset({
    "affirmed-brief", "artifact", "cold-verdict", "holder-reading", "floor", "use",
    "no-use", "connected-reviewer", "panel-stage", "product-incident", "implementing-pr",
    "builder-session",
})
RED_CONCLUSIONS = {
    "action_required", "cancelled", "failure", "stale", "startup_failure", "timed_out",
}
RESUME_SOURCE_STAGES = {
    "artifact": frozenset({"artifact"}),
    "build": frozenset({"build", "floor", "review-disposition"}),
    "floor": frozenset({"build", "floor"}),
    "review-disposition": frozenset({"build", "floor", "review-disposition"}),
}


class WorkError(RuntimeError):
    """The entrance cannot preserve its read-only, single-stage contract."""


@dataclass(frozen=True)
class Marker:
    name: str
    attributes: dict[str, str]
    body: str
    author: str


@dataclass(frozen=True)
class WorkConfig:
    product_repositories: frozenset[str] = frozenset()
    connected_reviewers: frozenset[str] = frozenset()
    marker_producers: frozenset[str] = frozenset()


@dataclass
class WorkState:
    repo: str
    issue_number: int
    issue: dict[str, object]
    issue_comments: list[dict[str, object]] = field(default_factory=list)
    pr: dict[str, object] | None = None
    pr_comments: list[dict[str, object]] = field(default_factory=list)
    reviews: list[dict[str, object]] = field(default_factory=list)
    review_comments: list[dict[str, object]] = field(default_factory=list)
    checks: list[dict[str, object]] = field(default_factory=list)
    changed_paths: list[str] = field(default_factory=list)
    ambiguous_prs: list[int] = field(default_factory=list)
    config: WorkConfig = field(default_factory=WorkConfig)

    @property
    def issue_sources(self) -> list[tuple[str, str]]:
        values = [(str(self.issue.get("body") or ""), _author(self.issue))]
        values.extend((str(item.get("body") or ""), _author(item))
                      for item in self.issue_comments)
        return values

    @property
    def sources(self) -> list[tuple[str, str]]:
        values = self.issue_sources
        for records_from_surface in (self.pr_comments, self.reviews, self.review_comments):
            values.extend((str(item.get("body") or ""), _author(item))
                          for item in records_from_surface)
        return values

    @property
    def issue_markers(self) -> list[Marker]:
        return _authorized_markers(markers(self.issue_sources), self.config.marker_producers)

    @property
    def markers(self) -> list[Marker]:
        return _authorized_markers(markers(self.sources), self.config.marker_producers)

    @property
    def ignored_markers(self) -> list[Marker]:
        return [marker for marker in markers(self.sources)
                if marker.author.lower() not in self.config.marker_producers]


@dataclass(frozen=True)
class Decision:
    stage: str
    dispatch: bool
    continuity: str | None
    reason: str
    detail: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "dispatch": self.dispatch,
            "continuity": self.continuity,
            "reason": self.reason,
            "detail": self.detail,
        }


class GitHubREST:
    """Authenticated GitHub REST reads through the user's gh credential store."""

    def get(self, endpoint: str, *, paginate: bool = False) -> object:
        command = ["gh", "api", "--method", "GET", endpoint]
        if paginate:
            command.extend(("--paginate", "--slurp"))
        result = subprocess.run(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=120,
        )
        if result.returncode:
            diagnostic = result.stderr.decode("utf-8", errors="backslashreplace").strip()
            raise WorkError(f"GitHub GET failed for {endpoint}: {diagnostic or result.returncode}")
        try:
            value = json.loads(result.stdout.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise WorkError(f"GitHub GET returned invalid JSON for {endpoint}") from exc
        if paginate:
            if not isinstance(value, list):
                raise WorkError(f"GitHub paginated GET returned a non-list for {endpoint}")
            pages = value
            if pages and all(isinstance(page, list) for page in pages):
                return [item for page in pages for item in page]
        return value


def _dict(value: object, endpoint: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise WorkError(f"GitHub GET returned a non-object for {endpoint}")
    return value


def _list(value: object, endpoint: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise WorkError(f"GitHub GET returned a non-object list for {endpoint}")
    return value


def _get_list(transport: GitHubREST, endpoint: str) -> list[dict[str, object]]:
    return _list(transport.get(endpoint, paginate=True), endpoint)


def _author(item: dict[str, object]) -> str:
    user = item.get("user")
    login = user.get("login") if isinstance(user, dict) else None
    return str(login).lower() if isinstance(login, str) and login else "unknown"


def _authorized_markers(found: list[Marker], producers: frozenset[str]) -> list[Marker]:
    return [marker for marker in found if marker.author.lower() in producers]


def _candidate_prs(issue_number: int, issue: dict[str, object],
                   comments: list[dict[str, object]], pulls: list[dict[str, object]],
                   config: WorkConfig) -> set[int]:
    found: set[int] = set()
    if isinstance(issue.get("pull_request"), dict):
        found.add(issue_number)
    sources = [(str(issue.get("body") or ""), _author(issue))]
    sources.extend((str(item.get("body") or ""), _author(item)) for item in comments)
    for marker in _authorized_markers(markers(sources), config.marker_producers):
        number = marker.attributes.get("number", "")
        if marker.name == "implementing-pr" and number.isdigit() and int(number) > 0:
            found.add(int(number))
    for pull in pulls:
        number = pull.get("number")
        body = str(pull.get("body") or "")
        if isinstance(number, int) and any(
            int(match.group(1)) == issue_number for match in CLOSING_REFERENCE.finditer(body)
        ):
            found.add(number)
    return found


def read_state(transport: GitHubREST, repo: str, issue_number: int,
               config: WorkConfig | None = None) -> WorkState:
    work_config = config or WorkConfig()
    base = f"repos/{repo}"
    issue_endpoint = f"{base}/issues/{issue_number}"
    issue = _dict(transport.get(issue_endpoint), issue_endpoint)
    issue_comments = _get_list(transport, f"{issue_endpoint}/comments")
    pulls_endpoint = f"{base}/pulls?state=all&per_page=100"
    pulls = _get_list(transport, pulls_endpoint)
    candidates = sorted(_candidate_prs(issue_number, issue, issue_comments, pulls, work_config))
    state = WorkState(repo, issue_number, issue, issue_comments, config=work_config)
    if len(candidates) > 1:
        state.ambiguous_prs = candidates
        return state
    if not candidates:
        return state
    number = candidates[0]
    pr_endpoint = f"{base}/pulls/{number}"
    state.pr = _dict(transport.get(pr_endpoint), pr_endpoint)
    state.pr_comments = _get_list(transport, f"{base}/issues/{number}/comments")
    state.reviews = _get_list(transport, f"{pr_endpoint}/reviews")
    state.review_comments = _get_list(transport, f"{pr_endpoint}/comments")
    files = _get_list(transport, f"{pr_endpoint}/files")
    state.changed_paths = [str(item["filename"]) for item in files if isinstance(item.get("filename"), str)]
    head = state.pr.get("head")
    sha = head.get("sha") if isinstance(head, dict) else None
    if isinstance(sha, str) and sha:
        checks_endpoint = f"{base}/commits/{sha}/check-runs"
        checks_value = _dict(transport.get(checks_endpoint), checks_endpoint)
        state.checks = _list(checks_value.get("check_runs", []), checks_endpoint)
    return state


def markers(sources: list[tuple[str, str]]) -> list[Marker]:
    found: list[Marker] = []
    for text, author in sources:
        for match in MARKER.finditer(text):
            attributes = {key.lower(): value for key, value in ATTRIBUTE.findall(match.group(2) or "")}
            found.append(Marker(match.group(1).lower(), attributes, text, author))
    return found


def review_lane(text: str) -> tuple[str, str] | None:
    risks = re.findall(r"(?im)^Review risk:\s*(ordinary|elevated|critical)\s*$", text)
    lanes = re.findall(
        r"(?im)^Review lane:\s*(connected|routine-panel|substantial-panel)\s*$", text
    )
    if len(risks) != 1 or len(lanes) != 1 or LANES[risks[0].lower()] != lanes[0].lower():
        return None
    return risks[0].lower(), lanes[0].lower()


def load_work_config(root: Path) -> WorkConfig:
    path = root / ".tradecraft" / "work.json"
    if not path.exists():
        return WorkConfig()
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise WorkError(f"cannot read work configuration: {path}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise WorkError("work configuration must be a schema-version-1 object")
    fields = ("product_repositories", "connected_reviewers", "marker_producers")
    if any(not isinstance(value.get(name), list) for name in fields):
        raise WorkError("work configuration must carry product, reviewer and marker-producer lists")
    products: set[str] = set()
    for repository in value["product_repositories"]:
        if not isinstance(repository, str) or REPOSITORY_NAME.fullmatch(repository) is None:
            raise WorkError("each product repository must be an owner/repository string")
        products.add(repository.lower())
    identities: dict[str, frozenset[str]] = {}
    for field_name in ("connected_reviewers", "marker_producers"):
        normalized: set[str] = set()
        for login in value[field_name]:
            if not isinstance(login, str) or GITHUB_LOGIN.fullmatch(login) is None:
                raise WorkError(f"each {field_name} entry must be a GitHub login")
            normalized.add(login.lower())
        identities[field_name] = frozenset(normalized)
    return WorkConfig(
        product_repositories=frozenset(products),
        connected_reviewers=identities["connected_reviewers"],
        marker_producers=identities["marker_producers"],
    )


def has_product_incident(state: WorkState, product_repos: frozenset[str]) -> bool:
    if any(marker.name == "product-incident" and marker.attributes.get("repo", "").lower()
           in product_repos and marker.attributes.get("issue", "").isdigit()
           and int(marker.attributes["issue"]) > 0
           for marker in state.issue_markers):
        return True
    return any(match.group(1).lower() in product_repos
               for text, _author_name in state.issue_sources for match in ISSUE_URL.finditer(text))


def _head_sha(state: WorkState) -> str | None:
    head = state.pr.get("head") if state.pr else None
    sha = head.get("sha") if isinstance(head, dict) else None
    return sha if isinstance(sha, str) and sha else None


def _current_marker(state: WorkState, name: str, **attributes: str) -> Marker | None:
    for marker in reversed(state.markers):
        if marker.name == name and all(marker.attributes.get(key) == value for key, value in attributes.items()):
            return marker
    return None


def staffing_qualified(marker: Marker) -> bool:
    if marker.attributes.get("staffing_status") != "degraded":
        return True
    return bool(marker.attributes.get("same_vendor_reason"))


def load_use_rules(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise WorkError(f"cannot read use rules: {path}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise WorkError("use rules must be a schema-version-1 object")
    rules = value.get("rules")
    if not isinstance(rules, list) or not rules:
        raise WorkError("use rules must contain a nonempty rules list")
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("include"), list) or not isinstance(rule.get("exclude"), list):
            raise WorkError("each use rule must carry include and exclude lists")
    return value


def use_required(paths: list[str], rules: dict[str, object]) -> bool:
    normalized = [path.replace("\\", "/") for path in paths]
    for rule in rules["rules"]:
        includes = rule["include"]
        excludes = rule["exclude"]
        for path in normalized:
            if any(fnmatch.fnmatchcase(path, pattern) for pattern in includes) and not any(
                fnmatch.fnmatchcase(path, pattern) for pattern in excludes
            ):
                return True
    return False


def _checks_red(state: WorkState) -> bool:
    return any(str(check.get("conclusion") or "").lower() in RED_CONCLUSIONS for check in state.checks)


def _review_record_at_head(state: WorkState, item: dict[str, object]) -> bool:
    commit_id = item.get("commit_id")
    head = _head_sha(state)
    return commit_id is None or (isinstance(commit_id, str) and commit_id == head)


def _reviewer_ran(state: WorkState) -> bool:
    for item in (*state.reviews, *state.review_comments, *state.pr_comments):
        if (_author(item) in state.config.connected_reviewers
                and _review_record_at_head(state, item)):
            return True
    return False


def _undisposed_threads(state: WorkState) -> list[int]:
    replies = {int(item["in_reply_to_id"]): item for item in state.review_comments
               if isinstance(item.get("in_reply_to_id"), int)}
    missing: list[int] = []
    for item in state.review_comments:
        identity = item.get("id")
        if not isinstance(identity, int) or item.get("in_reply_to_id") is not None:
            continue
        if (_author(item) not in state.config.connected_reviewers
                or not _review_record_at_head(state, item)):
            continue
        reply = replies.get(identity)
        body = str(reply.get("body") or "").lower().replace(chr(0x2014), "-") if reply else ""
        if not any(body.strip().startswith(prefix) for prefix in DISPOSITIONS):
            missing.append(identity)
    return missing


def _panel_next(state: WorkState, lane: str) -> str | None:
    if lane == "connected":
        return None
    paths = state.changed_paths
    if lane == "routine-panel":
        stages = ["cold-pass"]
        if any(path.startswith("skills/") and path.endswith(".md") for path in paths):
            stages.append("revision-diff")
        stages.extend(("defense", "floor-fixes"))
    else:
        stages = ["four-seat-panel", "defense", "judge", "floor-fixes"]
    completed = {
        marker.attributes.get("stage") for marker in state.markers
        if marker.name == "panel-stage" and marker.attributes.get("status") == "complete"
    }
    return next((stage for stage in stages if stage not in completed), None)


def _ignored_marker_suffix(state: WorkState) -> str:
    authors = sorted({marker.author for marker in state.ignored_markers})
    return f";ignored-marker-from={','.join(authors)}" if authors else ""


def decide(state: WorkState, rules: dict[str, object]) -> Decision:
    def result(stage: str, dispatch: bool, continuity: str | None, reason: str,
               detail: str | None = None) -> Decision:
        return Decision(stage, dispatch, continuity, reason + _ignored_marker_suffix(state), detail)

    if str(state.issue.get("state") or "").lower() == "closed":
        return result("terminal", False, None, "issue-or-pull-request-terminal")
    if state.ambiguous_prs:
        joined = ",".join(str(number) for number in state.ambiguous_prs)
        return result("ambiguous-pr", False, None, "multiple-candidate-pull-requests", joined)
    if state.pr and (state.pr.get("merged_at") or str(state.pr.get("state") or "").lower() == "closed"):
        return result("terminal", False, None, "issue-or-pull-request-terminal")
    affirmed = [marker for marker in state.issue_markers if marker.name == "affirmed-brief"]
    products = state.config.product_repositories
    if products and not affirmed and not has_product_incident(state, products):
        return result("product-incident-required", False, None, "practice-work-has-no-product-incident")
    if not affirmed:
        return result("convergence", False, None, "affirmed-brief-marker-absent")
    lane_pair = review_lane(affirmed[-1].body)
    if lane_pair is None:
        return result("affirmation-invalid", False, None, "review-risk-lane-missing-or-mismatched")
    _risk, lane = lane_pair
    artifacts = [marker for marker in state.markers if marker.name == "artifact"]
    if not artifacts:
        return result("artifact", True, "fresh", "artifact-marker-absent")
    verdicts = [marker for marker in state.markers
                if marker.name == "cold-verdict" and staffing_qualified(marker)]
    if not verdicts:
        return result("cold-seat", True, "fresh", "qualifying-cold-verdict-absent")
    verdict = verdicts[-1]
    if verdict.attributes.get("verdict") == "would-not":
        return result("artifact", True, "resume", "cold-verdict-would-not")
    if verdict.attributes.get("verdict") != "would":
        return result("cold-seat", True, "fresh", "qualifying-cold-verdict-absent")
    if not any(marker.name == "holder-reading" for marker in state.markers):
        return result("holder-read", False, None, "whole-change-holder-reading-absent")
    if state.pr is None:
        return result("build", True, "fresh", "pull-request-absent")
    sha = _head_sha(state)
    if sha is None:
        return result("floor", True, "resume", "pull-request-head-sha-absent")
    floor = _current_marker(state, "floor", head=sha, status="pass")
    if floor is None or _checks_red(state):
        return result("floor", True, "resume", "current-head-floor-missing-or-red")
    latest_use = next((marker for marker in reversed(state.markers) if marker.name == "use"), None)
    if latest_use and latest_use.attributes.get("head") == sha and latest_use.attributes.get("changed") == "true":
        return result("build", True, "resume", "use-finding-changed-behavior-or-instructions")
    bought = use_required(state.changed_paths, rules)
    current_use = _current_marker(state, "use", head=sha, status="pass")
    if bought and (current_use is None or not staffing_qualified(current_use)):
        return result("use", True, "fresh", "current-head-use-absent")
    if not bought:
        no_use = _current_marker(state, "no-use", head=sha)
        if no_use is None or "Use: not required" not in no_use.body:
            return result("use", False, None, "path-rules-require-explicit-no-use-line")
    if bool(state.pr.get("draft")):
        return result("ready-reviewers", False, None, "floor-and-use-complete-pr-draft")
    reviewers = state.config.connected_reviewers
    if reviewers and not _reviewer_ran(state):
        return result("waiting", False, None, "required-connected-reviewer-has-not-run")
    threads = _undisposed_threads(state)
    if threads:
        return result(
            "review-disposition", True, "resume", "reviewer-thread-lacks-disposition",
            ",".join(str(identity) for identity in threads),
        )
    panel_stage = _panel_next(state, lane)
    if panel_stage:
        return result("panel", False, None, "bought-panel-incomplete", panel_stage)
    reason = "all-evidence-complete" if reviewers else "all-evidence-complete;no-connected-reviewer-configured"
    return result("release-report", True, "fresh", reason)


def registry_path() -> Path:
    return Path.home() / ".tradecraft" / "implementation-worktrees.json"


def _git_snapshot(path: Path) -> tuple[str | None, str | None]:
    values = []
    for arguments in (("rev-parse", "HEAD"), ("status", "--porcelain")):
        result = subprocess.run(
            ["git", "-C", str(path), *arguments], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20,
        )
        values.append(result.stdout.decode("utf-8", errors="backslashreplace") if result.returncode == 0 else None)
    revision = values[0].strip() if values[0] else None
    return revision, values[1]


def holder_guard_status() -> str:
    return "available" if any(os.environ.get(name) for name in (
        "CLAUDE_CODE_ENTRYPOINT", "CLAUDECODE",
    )) else "unavailable"


def register_worktree(path: Path, repo: str, issue: int, instalment: str | None,
                      *, guard_status: str | None = None) -> None:
    target = path.expanduser().resolve()
    destination = registry_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        current = json.loads(destination.read_bytes()) if destination.is_file() else {"schema_version": 1, "worktrees": []}
    except (OSError, ValueError) as exc:
        raise WorkError(f"cannot read implementation worktree registry: {destination}") from exc
    if not isinstance(current, dict) or current.get("schema_version") != 1 or not isinstance(current.get("worktrees"), list):
        raise WorkError("implementation worktree registry has an unsupported shape")
    rows = [row for row in current["worktrees"] if not (
        isinstance(row, dict) and str(row.get("root") or "").lower() == str(target).lower()
    )]
    revision, status = _git_snapshot(target)
    rows.append({"root": str(target), "repository": repo, "issue": issue,
                 "instalment": instalment, "active": True,
                 "holder_write_guard": guard_status or holder_guard_status(),
                 "revision_before": revision, "status_before": status})
    current["worktrees"] = rows
    content = (json.dumps(current, ensure_ascii=True, indent=2) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(mode="wb", dir=destination.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
        stream.flush()
    try:
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _stage_prompt(state: WorkState, decision: Decision) -> bytes:
    evidence = {
        "repository": state.repo,
        "issue": state.issue_number,
        "stage": decision.stage,
        "reason": decision.reason,
        "detail": decision.detail,
        "continuity": decision.continuity,
        "github": {
            "issue": state.issue,
            "issue_comments": state.issue_comments,
            "pull_request": state.pr,
            "pull_request_comments": state.pr_comments,
            "reviews": state.reviews,
            "review_comments": state.review_comments,
            "checks": state.checks,
            "changed_paths": state.changed_paths,
        },
    }
    instruction = (
        "Perform exactly the stage named in this dispatch and return to the holder. "
        "Do not start or dispatch a later stage."
    )
    if decision.stage == "build":
        instruction += (
            " Tell the holder to post <!-- tradecraft:builder-session:v1 session=SESSION --> "
            "on the issue using the session id printed by the launcher."
        )
    return (
        instruction + "\n\n" +
        json.dumps(evidence, ensure_ascii=True, indent=2) + "\n"
    ).encode("utf-8")


def _git(command: list[str], root: Path) -> subprocess.CompletedProcess[bytes]:
    environment = {
        key: value for key, value in os.environ.items()
        if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"}
    }
    return subprocess.run(
        ["git", "-C", str(root), *command], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, env=environment,
    )


def _git_failure(result: subprocess.CompletedProcess[bytes]) -> str:
    return result.stderr.decode("utf-8", errors="backslashreplace").strip() or str(result.returncode)


@contextmanager
def judging_root(root: Path):
    attached = _git(["symbolic-ref", "-q", "HEAD"], root)
    if attached.returncode == 1:
        yield root
        return
    if attached.returncode != 0:
        raise WorkError(f"cannot inspect recipient HEAD: {_git_failure(attached)}")
    with tempfile.TemporaryDirectory(prefix="tradecraft-recipient-") as temporary:
        recipient = Path(temporary) / "detached"
        added = _git(["worktree", "add", "--detach", str(recipient), "HEAD"], root)
        if added.returncode:
            raise WorkError(f"cannot create detached judging worktree: {_git_failure(added)}")
        try:
            yield recipient.resolve()
        finally:
            removed = _git(["worktree", "remove", "--force", str(recipient)], root)
            if removed.returncode:
                raise WorkError(f"cannot remove detached judging worktree: {_git_failure(removed)}")


def _json_object(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _bundle_session(work_value: str, stage: str, record_root: Path) -> str | None:
    allowed_stages = RESUME_SOURCE_STAGES.get(stage, frozenset({stage}))
    candidates: list[tuple[str, str, str]] = []
    if not record_root.is_dir():
        return None
    try:
        for run_path in record_root.rglob("*.run.json"):
            run = _json_object(run_path)
            request_name = run_path.name.removesuffix(".run.json") + ".request.json"
            request = _json_object(run_path.with_name(request_name))
            if run is None or request is None:
                continue
            if (request.get("schema_version") != records.SCHEMA_VERSION
                    or run.get("schema_version") != records.SCHEMA_VERSION
                    or str(request.get("work") or "").lower() != work_value.lower()
                    or request.get("stage") not in allowed_stages):
                continue
            attempts = run.get("attempts")
            if not isinstance(attempts, list):
                continue
            sessions: list[str] = []
            for attempt in attempts:
                observed = attempt.get("observed") if isinstance(attempt, dict) else None
                session = observed.get("session_id") if isinstance(observed, dict) else None
                if isinstance(session, str) and SESSION_ID.fullmatch(session):
                    sessions.append(session)
            if sessions:
                completed = str(run.get("completed_at") or "")
                candidates.append((completed, str(run_path), sessions[-1]))
    except OSError:
        return None
    return max(candidates)[-1] if candidates else None


def resume_session(state: WorkState, stage: str, record_root: Path | None = None) -> str | None:
    work_value = f"{state.repo}#{state.issue_number}"
    bundled = _bundle_session(
        work_value, stage, record_root or records.default_record_root().expanduser().resolve()
    )
    if bundled:
        return bundled
    if stage == "artifact":
        return None
    sessions = [marker.attributes.get("session") for marker in state.issue_markers
                if marker.name == "builder-session"]
    return next((session for session in reversed(sessions)
                 if isinstance(session, str) and SESSION_ID.fullmatch(session)), None)


def _missing_resume_decision(state: WorkState, decision: Decision) -> Decision:
    supply = ("a matching artifact dispatch bundle" if decision.stage == "artifact"
              else "a matching dispatch bundle or authorized builder-session marker")
    return Decision(
        decision.stage, False, None,
        f"resume-session-missing-for-{decision.stage}{_ignored_marker_suffix(state)}",
        f"stage={decision.stage}; supply={supply}",
    )


def execute_stage(state: WorkState, decision: Decision, root: Path, instalment: str | None) -> int:
    if not decision.dispatch:
        print(json.dumps(decision.as_dict(), ensure_ascii=True, sort_keys=True))
        return 0
    session = None
    if decision.continuity == "resume":
        session = resume_session(state, decision.stage)
        if session is None:
            print(json.dumps(_missing_resume_decision(state, decision).as_dict(),
                             ensure_ascii=True, sort_keys=True))
            return 0
    if decision.stage == "build" and decision.continuity == "fresh":
        register_worktree(root, state.repo, state.issue_number, instalment)
    here = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="tradecraft-work-") as temporary:
        dispatch = Path(temporary) / "dispatch.txt"
        dispatch.write_bytes(_stage_prompt(state, decision))
        if decision.stage in {"cold-seat", "use"}:
            with judging_root(root) as recipient:
                common = [
                    "--dispatch", str(dispatch), "--root", str(recipient),
                    "--work", f"{state.repo}#{state.issue_number}", "--stage", decision.stage,
                    "--settings-source", f"https://github.com/{state.repo}/issues/{state.issue_number}",
                    "--settings-scope", decision.stage,
                ]
                command = [sys.executable, str(here / "dispatch_seat.py"), *common,
                           "--vendor", "claude", "--own-vendor", "codex",
                           "--classification", "cold" if decision.stage == "cold-seat" else "ordinary",
                           "--requires", "read" if decision.stage == "cold-seat" else "execute"]
                return subprocess.run(command).returncode
        else:
            common = [
                "--dispatch", str(dispatch), "--root", str(root),
                "--work", f"{state.repo}#{state.issue_number}", "--stage", decision.stage,
                "--settings-source", f"https://github.com/{state.repo}/issues/{state.issue_number}",
                "--settings-scope", decision.stage,
            ]
            command = [sys.executable, str(here / "dispatch_implementer.py"), *common]
            if decision.continuity == "resume":
                command.extend(("--resume", session))
            return subprocess.run(command).returncode


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="Read GitHub state and run exactly one change stage.")
    cli.add_argument("command", nargs="?", choices=COMMANDS)
    cli.add_argument("--repo", required=True)
    cli.add_argument("--issue", required=True, type=int)
    cli.add_argument("--root", required=True, type=Path)
    cli.add_argument("--instalment")
    cli.add_argument("--use-rules", type=Path)
    return cli


def run(args: argparse.Namespace, *, transport: GitHubREST | None = None,
        executor: Callable[[WorkState, Decision, Path, str | None], int] = execute_stage) -> int:
    root = args.root.expanduser().resolve()
    config = load_work_config(root)
    state = read_state(transport or GitHubREST(), args.repo, args.issue, config)
    rules = load_use_rules(args.use_rules or root / "lib" / "use-rules.json")
    decision = decide(state, rules)
    if args.command:
        decision = Decision(args.command, True, "fresh", "power-user-stage-command")
    return executor(state, decision, root, args.instalment)


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    try:
        return run(parser().parse_args(argv))
    except (OSError, UnicodeError, ValueError, WorkError) as exc:
        print(f"work: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

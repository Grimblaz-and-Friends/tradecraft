#!/usr/bin/env python3
"""Read GitHub work state and dispatch exactly one stage."""
from __future__ import annotations

import argparse
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
PR_URL = re.compile(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", re.I)
INCIDENT_URL = re.compile(r"https://github\.com/[^/]+/(Elos|Daemon)/issues/(\d+)", re.I)
RED_CONCLUSIONS = {
    "action_required", "cancelled", "failure", "stale", "startup_failure", "timed_out",
}


class WorkError(RuntimeError):
    """The entrance cannot preserve its read-only, single-stage contract."""


@dataclass(frozen=True)
class Marker:
    name: str
    attributes: dict[str, str]
    body: str


@dataclass
class WorkState:
    repo: str
    issue_number: int
    issue: dict[str, object]
    issue_comments: list[dict[str, object]] = field(default_factory=list)
    timeline: list[dict[str, object]] = field(default_factory=list)
    pr: dict[str, object] | None = None
    pr_comments: list[dict[str, object]] = field(default_factory=list)
    reviews: list[dict[str, object]] = field(default_factory=list)
    review_comments: list[dict[str, object]] = field(default_factory=list)
    checks: list[dict[str, object]] = field(default_factory=list)
    changed_paths: list[str] = field(default_factory=list)
    ambiguous_prs: list[int] = field(default_factory=list)

    @property
    def texts(self) -> list[str]:
        values = [str(self.issue.get("body") or "")]
        values.extend(str(item.get("body") or "") for item in self.issue_comments)
        values.extend(str(item.get("body") or "") for item in self.pr_comments)
        return values

    @property
    def markers(self) -> list[Marker]:
        return markers(self.texts)


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


def _candidate_prs(repo: str, issue: dict[str, object], comments: list[dict[str, object]],
                   timeline: list[dict[str, object]]) -> set[int]:
    found: set[int] = set()
    if isinstance(issue.get("pull_request"), dict):
        found.add(int(issue["number"]))
    texts = [str(issue.get("body") or "")]
    texts.extend(str(item.get("body") or "") for item in comments)
    for text in texts:
        for match in PR_URL.finditer(text):
            if match.group(1).lower() == repo.lower():
                found.add(int(match.group(2)))
    for event in timeline:
        source = event.get("source")
        source_issue = source.get("issue") if isinstance(source, dict) else None
        if not isinstance(source_issue, dict) or not isinstance(source_issue.get("pull_request"), dict):
            continue
        repository = source_issue.get("repository")
        full_name = repository.get("full_name") if isinstance(repository, dict) else repo
        if isinstance(full_name, str) and full_name.lower() == repo.lower():
            number = source_issue.get("number")
            if isinstance(number, int):
                found.add(number)
    return found


def read_state(transport: GitHubREST, repo: str, issue_number: int) -> WorkState:
    base = f"repos/{repo}"
    issue_endpoint = f"{base}/issues/{issue_number}"
    issue = _dict(transport.get(issue_endpoint), issue_endpoint)
    issue_comments = _get_list(transport, f"{issue_endpoint}/comments")
    timeline = _get_list(transport, f"{issue_endpoint}/timeline")
    candidates = sorted(_candidate_prs(repo, issue, issue_comments, timeline))
    state = WorkState(repo, issue_number, issue, issue_comments, timeline)
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


def markers(texts: list[str]) -> list[Marker]:
    found: list[Marker] = []
    for text in texts:
        for match in MARKER.finditer(text):
            attributes = {key.lower(): value for key, value in ATTRIBUTE.findall(match.group(2) or "")}
            found.append(Marker(match.group(1).lower(), attributes, text))
    return found


def review_lane(text: str) -> tuple[str, str] | None:
    risks = re.findall(r"(?im)^Review risk:\s*(ordinary|elevated|critical)\s*$", text)
    lanes = re.findall(
        r"(?im)^Review lane:\s*(connected|routine-panel|substantial-panel)\s*$", text
    )
    if len(risks) != 1 or len(lanes) != 1 or LANES[risks[0].lower()] != lanes[0].lower():
        return None
    return risks[0].lower(), lanes[0].lower()


def is_practice_facing(state: WorkState) -> bool:
    if state.repo.rsplit("/", 1)[-1].lower() != "tradecraft":
        return False
    labels = state.issue.get("labels")
    names = {
        str(item.get("name") or "").lower() for item in labels or [] if isinstance(item, dict)
    }
    return "practice-facing" in names or any(marker.name == "practice-facing" for marker in state.markers)


def has_product_incident(state: WorkState) -> bool:
    if any(marker.name == "product-incident" and marker.attributes.get("repo", "").lower()
           in {"elos", "daemon"} and marker.attributes.get("issue", "").isdigit()
           for marker in state.markers):
        return True
    return any(INCIDENT_URL.search(text) for text in state.texts)


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


def _reviewer_ran(state: WorkState) -> bool:
    if _current_marker(state, "connected-reviewer", status="complete"):
        return True
    records = [*state.reviews, *state.review_comments, *state.pr_comments]
    for item in records:
        user = item.get("user")
        login = str(user.get("login") or "").lower() if isinstance(user, dict) else ""
        kind = str(user.get("type") or "").lower() if isinstance(user, dict) else ""
        if kind == "bot" or login.endswith("[bot]") or any(name in login for name in ("coderabbit", "greptile", "codex")):
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
        user = item.get("user")
        login = str(user.get("login") or "").lower() if isinstance(user, dict) else ""
        kind = str(user.get("type") or "").lower() if isinstance(user, dict) else ""
        if kind != "bot" and not login.endswith("[bot]"):
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


def decide(state: WorkState, rules: dict[str, object]) -> Decision:
    if state.ambiguous_prs:
        joined = ",".join(str(number) for number in state.ambiguous_prs)
        return Decision("ambiguous-pr", False, None, "multiple-candidate-pull-requests", joined)
    if str(state.issue.get("state") or "").lower() == "closed" or (
        state.pr and (state.pr.get("merged_at") or str(state.pr.get("state") or "").lower() == "closed")
    ):
        return Decision("terminal", False, None, "issue-or-pull-request-terminal")
    if is_practice_facing(state) and not has_product_incident(state):
        return Decision("product-incident-required", False, None, "practice-work-has-no-product-incident")
    affirmed = [marker for marker in state.markers if marker.name == "affirmed-brief"]
    if not affirmed:
        return Decision("convergence", False, None, "affirmed-brief-marker-absent")
    lane_pair = review_lane(affirmed[-1].body)
    if lane_pair is None:
        return Decision("affirmation-invalid", False, None, "review-risk-lane-missing-or-mismatched")
    _risk, lane = lane_pair
    artifacts = [marker for marker in state.markers if marker.name == "artifact"]
    if not artifacts:
        return Decision("artifact", True, "fresh", "artifact-marker-absent")
    verdicts = [marker for marker in state.markers
                if marker.name == "cold-verdict" and staffing_qualified(marker)]
    if not verdicts:
        return Decision("cold-seat", True, "fresh", "qualifying-cold-verdict-absent")
    verdict = verdicts[-1]
    if verdict.attributes.get("verdict") == "would-not":
        return Decision("artifact", True, "resume", "cold-verdict-would-not")
    if verdict.attributes.get("verdict") != "would":
        return Decision("cold-seat", True, "fresh", "qualifying-cold-verdict-absent")
    if not any(marker.name == "holder-reading" for marker in state.markers):
        return Decision("holder-read", False, None, "whole-change-holder-reading-absent")
    if state.pr is None:
        return Decision("build", True, "fresh", "pull-request-absent")
    sha = _head_sha(state)
    if sha is None:
        return Decision("floor", True, "resume", "pull-request-head-sha-absent")
    floor = _current_marker(state, "floor", head=sha, status="pass")
    if floor is None or _checks_red(state):
        return Decision("floor", True, "resume", "current-head-floor-missing-or-red")
    latest_use = next((marker for marker in reversed(state.markers) if marker.name == "use"), None)
    if latest_use and latest_use.attributes.get("head") == sha and latest_use.attributes.get("changed") == "true":
        return Decision("build", True, "resume", "use-finding-changed-behavior-or-instructions")
    bought = use_required(state.changed_paths, rules)
    current_use = _current_marker(state, "use", head=sha, status="pass")
    if bought and (current_use is None or not staffing_qualified(current_use)):
        return Decision("use", True, "fresh", "current-head-use-absent")
    if not bought:
        no_use = _current_marker(state, "no-use", head=sha)
        if no_use is None or "Use: not required" not in no_use.body:
            return Decision("use", False, None, "path-rules-require-explicit-no-use-line")
    if bool(state.pr.get("draft")):
        return Decision("ready-reviewers", False, None, "floor-and-use-complete-pr-draft")
    if not _reviewer_ran(state):
        return Decision("waiting", False, None, "required-connected-reviewer-has-not-run")
    threads = _undisposed_threads(state)
    if threads:
        return Decision(
            "review-disposition", True, "resume", "reviewer-thread-lacks-disposition",
            ",".join(str(identity) for identity in threads),
        )
    panel_stage = _panel_next(state, lane)
    if panel_stage:
        return Decision("panel", False, None, "bought-panel-incomplete", panel_stage)
    return Decision("release-report", True, "fresh", "all-evidence-complete")


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
    }
    return (
        "Perform exactly the stage named in this dispatch and return to the holder. "
        "Do not start or dispatch a later stage.\n\n" +
        json.dumps(evidence, ensure_ascii=True, indent=2) + "\n"
    ).encode("utf-8")


def execute_stage(state: WorkState, decision: Decision, root: Path, instalment: str | None) -> int:
    if not decision.dispatch:
        print(json.dumps(decision.as_dict(), ensure_ascii=True, sort_keys=True))
        return 0
    if decision.stage == "build" and decision.continuity == "fresh":
        register_worktree(root, state.repo, state.issue_number, instalment)
    here = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="tradecraft-work-") as temporary:
        dispatch = Path(temporary) / "dispatch.txt"
        dispatch.write_bytes(_stage_prompt(state, decision))
        common = [
            "--dispatch", str(dispatch), "--root", str(root),
            "--work", f"{state.repo}#{state.issue_number}", "--stage", decision.stage,
            "--settings-source", f"https://github.com/{state.repo}/issues/{state.issue_number}",
            "--settings-scope", decision.stage,
        ]
        if decision.stage in {"cold-seat", "use"}:
            command = [sys.executable, str(here / "dispatch_seat.py"), *common,
                       "--vendor", "claude", "--own-vendor", "codex",
                       "--classification", "cold" if decision.stage == "cold-seat" else "ordinary",
                       "--requires", "read" if decision.stage == "cold-seat" else "execute"]
        else:
            command = [sys.executable, str(here / "dispatch_implementer.py"), *common]
            if decision.continuity == "resume":
                sessions = [marker.attributes.get("session") for marker in state.markers
                            if marker.name in {"builder", "artifact-writer"} and marker.attributes.get("session")]
                if not sessions:
                    raise WorkError(f"{decision.stage} requires resume but no session marker exists")
                command.extend(("--resume", sessions[-1]))
        return subprocess.run(command).returncode


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="Read GitHub state and run exactly one change stage.")
    cli.add_argument("command", nargs="?", choices=COMMANDS)
    cli.add_argument("--repo", required=True)
    cli.add_argument("--issue", required=True, type=int)
    cli.add_argument("--root", required=True, type=Path)
    cli.add_argument("--instalment")
    cli.add_argument("--use-rules", type=Path, default=Path(__file__).with_name("use-rules.json"))
    return cli


def run(args: argparse.Namespace, *, transport: GitHubREST | None = None,
        executor: Callable[[WorkState, Decision, Path, str | None], int] = execute_stage) -> int:
    state = read_state(transport or GitHubREST(), args.repo, args.issue)
    rules = load_use_rules(args.use_rules)
    decision = decide(state, rules)
    if args.command:
        decision = Decision(args.command, True, "fresh", "power-user-stage-command")
    return executor(state, decision, args.root.expanduser().resolve(), args.instalment)


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    try:
        return run(parser().parse_args(argv))
    except (OSError, UnicodeError, ValueError, WorkError) as exc:
        print(f"work: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

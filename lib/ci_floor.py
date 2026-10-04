"""Read the base declaration and select independently verified Actions executions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

WORKFLOW_DIRECTORY = "/".join((".github", "workflows", ""))


class ProofError(ValueError):
    """The public floor cannot be established."""


@dataclass
class Finding:
    requirement: str
    remedy: str


def _is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _object(value, label):
    if not isinstance(value, dict):
        raise ProofError(f"{label} must be an object")
    return value


def _records(value, label):
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ProofError(f"{label} must contain object records")
    return value


def _workflow_path(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith(WORKFLOW_DIRECTORY)
        and value.endswith((".yml", ".yaml"))
        and not any(character in value for character in "\\:*?[]{}@")
        and not any(ord(character) < 32 or 127 <= ord(character) < 160 for character in value)
        and not any(part in {"", ".", ".."} for part in value.split("/"))
    )


def declaration(policy: dict[str, object]) -> dict[str, object]:
    """Read only the trusted policy; malformed declarations never become absence."""
    if "floor" not in policy:
        return {"jobs": [], "stall_after_seconds": 3600}
    floor = policy["floor"]
    if not isinstance(floor, dict) or not {"jobs"} <= set(floor) <= {
        "jobs", "stall_after_seconds"
    }:
        raise ProofError("floor must carry required jobs and optional stall_after_seconds only")
    jobs = floor["jobs"]
    if not isinstance(jobs, list):
        raise ProofError("floor.jobs must be an array")
    seen: set[tuple[str, str]] = set()
    for item in jobs:
        if not isinstance(item, dict) or set(item) != {"workflow", "job"}:
            raise ProofError("each floor job must carry exactly workflow and job")
        if not _workflow_path(item["workflow"]):
            raise ProofError("floor workflow must be an exact relative Actions workflow .yml or .yaml path")
        name = item["job"]
        if (
            not isinstance(name, str) or not name.strip()
            or any(ord(character) < 32 or 127 <= ord(character) < 160 for character in name)
        ):
            raise ProofError("floor job must be nonblank exact text without control characters")
        pair = (item["workflow"], name)
        if pair in seen:
            raise ProofError("floor.jobs contains a duplicate workflow/job pair")
        seen.add(pair)
    bound = floor.get("stall_after_seconds", 3600)
    if not _is_integer(bound) or bound <= 0:
        raise ProofError("floor.stall_after_seconds must be a positive integer")
    return {"jobs": jobs, "stall_after_seconds": bound}


def _actions_run_id(check_run: dict[str, object], repo: str) -> int | None:
    details_url = check_run.get("details_url")
    if not isinstance(details_url, str):
        return None
    match = re.fullmatch(
        rf"https://github\.com/{re.escape(repo)}/actions/runs/(\d+)(?:/job/\d+)?/?",
        details_url,
        re.I,
    )
    return int(match.group(1)) if match else None


def _paginated_objects(value: object, endpoint: str, key: str) -> list[dict[str, object]]:
    pages = value if isinstance(value, list) else [value]
    records: list[dict[str, object]] = []
    expected_total: int | None = None
    for raw_page in pages:
        page = _object(raw_page, endpoint)
        page_records = _records(page.get(key), endpoint)
        total = page.get("total_count")
        if not _is_integer(total) or total < 0:
            raise ProofError(f"GitHub paginated GET omitted a valid total_count for {endpoint}")
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise ProofError(f"GitHub paginated GET changed total_count for {endpoint}")
        records.extend(page_records)
    if expected_total is None or len(records) != expected_total:
        raise ProofError(
            f"GitHub paginated GET was incomplete for {endpoint}: expected "
            f"{expected_total}, retrieved {len(records)}"
        )
    return records


def _run_references_gate(run: dict[str, object]) -> bool:
    references = run.get("referenced_workflows")
    if not isinstance(references, list):
        return False
    expected = re.compile(
        r"Grimblaz-and-Friends/change-proof/\.github/workflows/change-proof\.yml@[^@\s]+\Z",
        re.I,
    )
    for reference in references:
        if not isinstance(reference, dict):
            continue
        path = reference.get("path") or reference.get("ref")
        if isinstance(path, str) and expected.fullmatch(path):
            return True
    return False


def _run_jobs(transport, repo: str, run_id: int) -> list[dict[str, object]]:
    endpoint = f"repos/{repo}/actions/runs/{run_id}/jobs?filter=all&per_page=100"
    return _paginated_objects(transport.get(endpoint, paginate=True), endpoint, "jobs")


def _is_proof_job(job: dict[str, object]) -> bool:
    name = job.get("name")
    return isinstance(name, str) and (name == "Change proof" or name.endswith(" / Change proof"))


def _job_label(job: dict[str, object]) -> str:
    name = job.get("name")
    check_url = job.get("check_run_url")
    check_id = check_url.rstrip("/").rsplit("/", 1)[-1] if isinstance(check_url, str) else "unknown"
    return f"check #{check_id} name={name!r}"


def _start_instant(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        instant = datetime.fromisoformat(value)
        if instant.tzinfo is None:
            return None
        return instant.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


@dataclass
class DeclaredFloor:
    checks: list[dict[str, object]]
    executions: list[dict[str, object]]
    findings: list[Finding]
    excluded: list[str]
    outcome: str


def _positive_id(value: object, label: str) -> int:
    if not _is_integer(value) or value <= 0:
        raise ProofError(f"{label} must be a positive numeric identity")
    return value


def _run_path(value: object) -> str:
    if not isinstance(value, str):
        raise ProofError("Actions run has no top-level workflow path")
    path, separator, ref = value.partition("@")
    # GitHub-managed dynamic workflows cannot match a repository declaration.
    if not path.startswith(WORKFLOW_DIRECTORY):
        return path
    if not _workflow_path(path) or (separator and (not ref or "@" in ref)):
        raise ProofError(f"Actions run has an unverifiable top-level workflow path: {value!r}")
    return path


def _run_identity(run: dict[str, object], repo: str, head: str) -> int:
    run_id = _positive_id(run.get("id"), "Actions run id")
    repository = run.get("repository")
    full_name = repository.get("full_name") if isinstance(repository, dict) else None
    if not isinstance(full_name, str) or full_name.lower() != repo.lower():
        raise ProofError(f"Actions run #{run_id} has missing or contradictory repository identity")
    if run.get("head_sha") != head:
        raise ProofError(f"Actions run #{run_id} has a contradictory head")
    return run_id


def _run_event(run: dict[str, object]) -> str:
    event = run.get("event")
    if not isinstance(event, str) or not event.strip() or any(
        ord(character) < 32 or 127 <= ord(character) < 160 for character in event
    ):
        raise ProofError(f"Actions run #{run['id']} has unavailable triggering-event provenance")
    return event


def _attempt_start(run: dict[str, object], jobs: list[dict[str, object]], attempt: int) -> object:
    """Do not time a rerun from the original workflow execution's creation."""
    if attempt == run["run_attempt"] and run.get("run_started_at") is not None:
        return run["run_started_at"]
    starts = [job["started_at"] for job in jobs
              if job.get("run_attempt") == attempt and job.get("started_at") is not None]
    if starts:
        instants = [_start_instant(start) for start in starts]
        if any(instant is None for instant in instants):
            raise ProofError(f"run #{run['id']} attempt #{attempt} has an invalid start timestamp")
        return min(starts, key=_start_instant)
    return run.get("created_at") if attempt == 1 else None


def _execution_state(
    status: object, conclusion: object, started_at: object, created_at: object,
    observed_at: datetime, bound: int,
) -> tuple[str, float | None]:
    if not isinstance(status, str) or (conclusion is not None and not isinstance(conclusion, str)):
        raise ProofError("execution has malformed status/conclusion text")
    if status == "completed":
        if conclusion == "success":
            return "success", None
        if conclusion in {"skipped", "neutral"}:
            return "fallback", None
        if conclusion in {
            "failure", "cancelled", "timed_out", "action_required", "startup_failure", "stale"
        }:
            return "blocked", None
        raise ProofError(f"completed execution has unknown conclusion {conclusion!r}")
    if status not in {"queued", "in_progress", "waiting", "pending", "requested"}:
        raise ProofError(f"execution has unknown status {status!r}")
    if conclusion is not None:
        raise ProofError("unfinished execution has a contradictory conclusion")
    clock = _start_instant(started_at if started_at is not None else created_at)
    if clock is None or clock > observed_at:
        raise ProofError("unfinished execution has an invalid or unavailable stall timestamp")
    age = (observed_at - clock).total_seconds()
    return ("stalled" if age >= bound else "pending"), age


def collect(
    transport, repo: str, head: str, declaration: dict[str, object],
    current_run_id: int | None, current_run_attempt: int | None,
    observed_at: datetime, *, gate_run_ids: frozenset[int] = frozenset(),
) -> DeclaredFloor:
    """Select complete public job executions independently of producer claims."""
    result = DeclaredFloor([], [], [], [], "ci-met")
    try:
        _collect_declared_floor(
            transport, repo, head, declaration, current_run_id,
            current_run_attempt, observed_at, result, gate_run_ids,
        )
    except (AttributeError, KeyError, OSError, TypeError, UnicodeError, ValueError) as exc:
        result.outcome = "unverifiable"
        result.findings.append(Finding(
            f"verifiable declared floor at {head}: {str(exc) or type(exc).__name__}",
            "restore the named public execution fact and run proof again",
        ))
    return result


def _collect_declared_floor(
    transport, repo: str, head: str, declaration: dict[str, object],
    current_run_id: int | None, current_run_attempt: int | None,
    observed_at: datetime, result: DeclaredFloor,
    gate_run_ids: frozenset[int],
) -> None:
    if not isinstance(observed_at, datetime) or observed_at.tzinfo is None:
        raise ProofError("floor observation time must be timezone-aware")
    pairs = declaration["jobs"]
    paths = {pair["workflow"] for pair in pairs}
    bound = declaration["stall_after_seconds"]
    runs_endpoint = f"repos/{repo}/actions/runs?head_sha={head}&per_page=100"
    runs = _paginated_objects(
        transport.get(runs_endpoint, paginate=True), runs_endpoint, "workflow_runs"
    )
    checks_endpoint = f"repos/{repo}/commits/{head}/check-runs?filter=all&per_page=100"
    checks = _paginated_objects(
        transport.get(checks_endpoint, paginate=True), checks_endpoint, "check_runs"
    )
    checks_by_id: dict[int, dict[str, object]] = {}
    for check in checks:
        check_id = _positive_id(check.get("id"), "check run id")
        if check_id in checks_by_id:
            raise ProofError(f"duplicate public check #{check_id} across check pages")
        checks_by_id[check_id] = check

    selected: dict[tuple[str, str], dict[str, object]] = {}
    seen_runs: set[int] = set()
    run_paths: dict[int, str] = {}
    for summary in runs:
        run_id = _run_identity(summary, repo, head)
        if run_id in seen_runs:
            raise ProofError(f"duplicate workflow run #{run_id} across run pages")
        seen_runs.add(run_id)
        # Positive unrelated provenance is enough to exclude it without reading jobs.
        if "path" in summary and _run_path(summary["path"]) not in paths:
            run_paths[run_id] = _run_path(summary["path"])
            continue
        endpoint = f"repos/{repo}/actions/runs/{run_id}"
        run = _object(transport.get(endpoint), endpoint)
        if _run_identity(run, repo, head) != run_id:
            raise ProofError(f"Actions run #{run_id} returned a contradictory run id")
        path = _run_path(run.get("path"))
        if "path" in summary and _run_path(summary["path"]) != path:
            raise ProofError(f"Actions run #{run_id} changed its workflow path during collection")
        run_paths[run_id] = path
        if path not in paths:
            continue
        event = _run_event(run)
        if "event" in summary and _run_event(summary) != event:
            raise ProofError(f"Actions run #{run_id} changed its triggering event during collection")
        key = (path, event)
        if key not in selected or run_id > selected[key]["id"]:
            selected[key] = run

    jobs_by_run: dict[int, list[dict[str, object]]] = {}
    for (path, event), run in selected.items():
        run_id = run["id"]
        attempt = _positive_id(run.get("run_attempt"), f"run #{run_id} attempt")
        _positive_id(run.get("workflow_id"), f"run #{run_id} workflow id")
        _positive_id(run.get("check_suite_id"), f"run #{run_id} check suite id")
        html_url = run.get("html_url")
        if not isinstance(html_url, str) or re.fullmatch(
            rf"https://github\.com/{re.escape(repo)}/actions/runs/{run_id}/?", html_url, re.I
        ) is None:
            raise ProofError(f"run #{run_id} has unavailable or contradictory public URL identity")
        jobs = _run_jobs(transport, repo, run_id)
        declared_names = {pair["job"] for pair in pairs if pair["workflow"] == path}
        gate_run = run_id in gate_run_ids or run_id == current_run_id or _run_references_gate(run)
        relevant_jobs: list[dict[str, object]] = []
        seen_jobs: set[int] = set()
        check_jobs: dict[int, list[dict[str, object]]] = {}
        for job in jobs:
            name = job.get("name")
            if isinstance(name, str) and name not in declared_names and not (gate_run and _is_proof_job(job)):
                continue
            if not isinstance(name, str):
                raise ProofError(f"run #{run_id} has a job with unavailable name provenance")
            check_url = job.get("check_run_url")
            origin = getattr(transport, "api_url", "https://api.github.com").rstrip("/")
            match = re.fullmatch(
                rf"{re.escape(origin)}/repos/{re.escape(repo)}/check-runs/([1-9][0-9]*)",
                check_url if isinstance(check_url, str) else "", re.I,
            )
            if match is not None:
                check_jobs.setdefault(int(match.group(1)), []).append(job)
            job_id = _positive_id(job.get("id"), f"job in run #{run_id}")
            job_attempt = _positive_id(job.get("run_attempt"), f"job #{job_id} attempt")
            if job_id in seen_jobs or job_attempt > attempt:
                raise ProofError(f"job #{job_id} has duplicate or contradictory attempt identity")
            seen_jobs.add(job_id)
            if job.get("run_id") != run_id or job.get("head_sha") != head:
                raise ProofError(f"job #{job_id} has contradictory run/head identity")
            if match is None:
                raise ProofError(f"job #{job_id} has an unverifiable check_run_url identity")
            run_url = job.get("run_url")
            if run_url is not None and (
                not isinstance(run_url, str)
                or run_url.lower() != f"{origin}/repos/{repo}/actions/runs/{run_id}".lower()
            ):
                raise ProofError(f"job #{job_id} has contradictory run_url identity")
            relevant_jobs.append(job)
        for check_id, associated in check_jobs.items():
            if len(associated) > 1 and any(job.get("name") in declared_names for job in associated):
                raise ProofError(f"check #{check_id} is ambiguously associated with jobs")
        jobs_by_run[run_id] = relevant_jobs

    for pair in pairs:
        path, name = pair["workflow"], pair["job"]
        pair_runs = [run for (workflow, event), run in selected.items() if workflow == path]
        for run in pair_runs or [None]:
            execution = {"workflow": path, "job": name, "run_id": None, "event": None,
                         "attempt": None, "check_id": None, "state": "fallback",
                         "conclusion": None, "age_seconds": None}
            if run is None:
                result.executions.append(execution)
                continue
            run_id = run["id"]
            run_attempt = run["run_attempt"]
            execution.update(run_id=run_id, attempt=run_attempt, event=run["event"])
            jobs = jobs_by_run[run_id]
            matches = [job for job in jobs if job.get("name") == name]
            newest_attempt = max((job["run_attempt"] for job in matches), default=0)
            matches = [job for job in matches if job["run_attempt"] == newest_attempt]
            current_gate = run_id in gate_run_ids or run_id == current_run_id and (
                current_run_attempt is None or current_run_attempt == run_attempt
            )
            gate_run = run_id in gate_run_ids or run_id == current_run_id or _run_references_gate(run)
            proof_attempt = run_attempt if current_gate else newest_attempt
            proof_jobs = [job for job in jobs
                          if job.get("run_attempt") == proof_attempt and _is_proof_job(job)]
            if gate_run and matches and len(proof_jobs) != 1:
                raise ProofError(
                    f"an unambiguous reusable proof job in run #{run_id} attempt #{proof_attempt}; "
                    f"candidate jobs: {', '.join(_job_label(job) for job in proof_jobs) or 'none'}"
                )
            # An unfinished rerun does not yet prove that a missing job was retained.
            uncertain = run.get("status") != "completed" and newest_attempt < run_attempt
            if current_gate and matches and all(job.get("status") == "completed" for job in matches):
                # This attempt's gate cannot make retained completed tests wait on itself.
                uncertain = False
            if uncertain or not matches:
                state, age = _execution_state(
                    run.get("status"), run.get("conclusion"), None,
                    _attempt_start(run, jobs, run_attempt) if run.get("status") != "completed" else None,
                    observed_at, bound,
                )
                # A successful/skipped run does not establish an omitted job's execution.
                execution.update(state="fallback" if state == "success" else state,
                                 age_seconds=age, conclusion=run.get("conclusion"))
                result.executions.append(execution)
                continue
            for job in matches:
                check_id = int(job["check_run_url"].rsplit("/", 1)[-1])
                if gate_run and _is_proof_job(job):
                    result.excluded.append(
                        f"proof execution run #{run_id} attempt #{newest_attempt} check #{check_id} "
                        "cannot establish its own declared floor"
                    )
                    result.executions.append(dict(execution))
                    continue
                check = checks_by_id.get(check_id)
                if check is None:
                    raise ProofError(f"job #{job['id']} has no visible check #{check_id}")
                app = check.get("app")
                suite = check.get("check_suite")
                if (
                    not isinstance(app, dict) or app.get("slug") != "github-actions"
                    or not _is_integer(app.get("id")) or app["id"] <= 0
                    or not isinstance(suite, dict) or suite.get("id") != run["check_suite_id"]
                    or check.get("head_sha") != head or check.get("name") != name
                    or _actions_run_id(check, repo) != run_id
                    or check.get("status") != job.get("status")
                    or check.get("conclusion") != job.get("conclusion")
                ):
                    raise ProofError(f"check #{check_id} and job #{job['id']} have contradictory identities/results")
                details_url = check.get("details_url")
                if "/job/" in details_url and details_url.rstrip("/").rsplit("/", 1)[-1] != str(job["id"]):
                    raise ProofError(f"check #{check_id} names a contradictory job identity")
                suite_app = suite.get("app")
                if suite_app is not None and (
                    not isinstance(suite_app, dict) or suite_app.get("id") != app["id"]
                    or suite_app.get("slug") != app["slug"]
                ):
                    raise ProofError(f"check #{check_id} names a contradictory suite application")
                suite_repository = suite.get("repository")
                if suite_repository is not None and (
                    not isinstance(suite_repository, dict)
                    or str(suite_repository.get("full_name", "")).lower() != repo.lower()
                ):
                    raise ProofError(f"check #{check_id} names a contradictory suite repository")
                started_at = job.get("started_at") if job.get("started_at") is not None else check.get("started_at")
                attempt_start = (
                    _attempt_start(run, jobs, newest_attempt)
                    if started_at is None and check.get("status") != "completed" else None
                )
                state, age = _execution_state(
                    check.get("status"), check.get("conclusion"), started_at,
                    attempt_start, observed_at, bound,
                )
                result.executions.append(dict(
                    execution, attempt=newest_attempt, check_id=check_id,
                    state=state, conclusion=check.get("conclusion"), age_seconds=age,
                ))
                result.checks.append({
                    "id": check_id, "name": name, "app_id": app["id"], "app_slug": app["slug"],
                    "workflow_id": run["workflow_id"], "run_id": run_id,
                    "url": run["html_url"],
                    "head": head, "status": check.get("status"), "conclusion": check.get("conclusion"),
                    "started_at": check.get("started_at"), "completed_at": check.get("completed_at"),
                })

    relevant_ids = {item["id"] for item in result.checks}
    for check_id, check in checks_by_id.items():
        if check_id in relevant_ids:
            continue
        app = check.get("app")
        run_id = _actions_run_id(check, repo)
        if (
            not isinstance(app, dict) or not isinstance(app.get("slug"), str)
            or not app["slug"] or not _is_integer(app.get("id")) or app["id"] <= 0
        ):
            raise ProofError(f"check #{check_id} has unavailable application provenance")
        if app.get("slug") == "github-actions" and run_id not in run_paths:
            declared_names = {pair["job"] for pair in pairs}
            name = check.get("name")
            if run_id is not None or not isinstance(name, str) or name in declared_names:
                raise ProofError(f"Actions check #{check_id} has unavailable workflow-run provenance")
        result.excluded.append(f"check #{check_id} is outside the selected declared executions")
    result.checks.sort(key=lambda check: check["id"])
    states = {execution["state"] for execution in result.executions}
    result.outcome = next(
        (state for state in ("blocked", "stalled", "pending", "fallback") if state in states),
        "ci-met",
    )
    for execution in result.executions:
        label = (
            f"{execution['workflow']} job {execution['job']!r} at {head} "
            f"event {execution['event']!r} run #{execution['run_id']} "
            f"attempt #{execution['attempt']} check #{execution['check_id']}"
        )
        state = execution["state"]
        if state in {"blocked", "pending", "stalled"}:
            result.findings.append(Finding(
                f"declared floor {state}: {label}; conclusion={execution['conclusion']!r} "
                f"age_seconds={execution['age_seconds']}",
                "resolve the named declared execution; a builder marker cannot override it; run proof again",
            ))

#!/usr/bin/env python3
"""Read the Phase B product-change record and render its close report.

The record family is made of HTML comments in GitHub issue bodies or issue
comments.  Attribute values contain no whitespace.  Records count only when
their GitHub record was created from the opening instant through the closing
instant, inclusive.

``phase-b-window:v1`` has exactly ``opened=TIMESTAMP`` and lives on the record
issue.  Its timestamp is an aware ISO-8601 instant.

``change-followup:v1`` has exactly ``source_pr=NUMBER``.  It lives on an issue;
one issue counts once for the qualifying pull request named by ``source_pr``.

``escaped-defect:v1`` has exactly ``found_by=use source_pr=NUMBER``.  It lives
on an issue created strictly after the named qualifying pull request merged;
one issue counts once.

``owner-ask:v1`` has exactly ``pr=NUMBER``.  Each issue body or issue comment
carrying it is one record for the qualifying pull request named by ``pr``.

Cost is the ``change-cost:v1`` report returned by ``lib/change_cost.py`` at
read time for the product repository and pull-request number.  Raw usage,
dated rate-card price, and bill or plan status remain separate output columns.
An absent cost quantity is rendered as ``unknown`` and never as zero.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Callable, Mapping
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "lib"
sys.path.insert(0, str(LIB))

import change_cost  # noqa: E402
from winio import utf8_stdio  # noqa: E402
from work import ATTRIBUTE, MARKER  # noqa: E402


PRODUCT_REPOSITORIES = (
    "Grimblaz-and-Friends/Organizations-of-Verra",
    "Grimblaz-and-Friends/Daemon",
)
RECORD_REPOSITORY = "Grimblaz-and-Friends/tradecraft"
RECORD_ISSUE = 665
CALENDAR_DAYS = 28
CHANGE_LIMIT = 20
API_HOST = "api.github.com"

LINK = re.compile(r'<([^>]+)>\s*;\s*rel="([^"]+)"')
ISSUE_NUMBER = re.compile(r"/issues/([1-9][0-9]*)/?\Z")


class PhaseBError(RuntimeError):
    """The close report cannot be produced without guessing at its record."""


@dataclass(frozen=True)
class Response:
    body: object
    headers: Mapping[str, str]


Transport = Callable[[str, str], Response]
CostReader = Callable[[str, int], dict[str, object]]


@dataclass(frozen=True)
class Change:
    repository: str
    number: int
    merged_at: datetime
    html_url: str
    pull: dict[str, object]


@dataclass(frozen=True)
class Window:
    opened_at: datetime
    deadline: datetime
    close_at: datetime | None
    changes: tuple[Change, ...]


@dataclass(frozen=True)
class Measures:
    change: Change
    followups: int
    escaped_defects: int
    owner_asks: int
    cost: dict[str, object]


def parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise PhaseBError("timestamp is not a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PhaseBError(f"invalid timestamp: {value}") from exc
    if parsed.utcoffset() is None:
        raise PhaseBError(f"timestamp has no timezone: {value}")
    return parsed.astimezone(timezone.utc)


def _timestamp_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_included(payload: bytes, endpoint: str) -> Response:
    try:
        text = payload.decode("utf-8").replace("\r\n", "\n")
    except UnicodeError as exc:
        raise PhaseBError(f"GitHub GET returned non-UTF-8 data for {endpoint}") from exc
    head, separator, body_text = text.partition("\n\n")
    lines = head.splitlines()
    if not separator or not lines or not lines[0].startswith("HTTP/"):
        raise PhaseBError(f"GitHub GET returned no response headers for {endpoint}")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, found, value = line.partition(":")
        if found:
            headers[name.strip().lower()] = value.strip()
    try:
        body = json.loads(body_text)
    except ValueError as exc:
        raise PhaseBError(f"GitHub GET returned invalid JSON for {endpoint}") from exc
    return Response(body, headers)


class GitHubREST:
    """Authenticated REST reads through the user's GitHub CLI credential store."""

    def __call__(self, method: str, endpoint: str) -> Response:
        if method != "GET":
            raise PhaseBError(f"GitHub transport refuses method {method}")
        result = subprocess.run(
            ["gh", "api", "--method", "GET", "--include", endpoint],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        if result.returncode:
            diagnostic = result.stderr.decode(
                "utf-8", errors="backslashreplace"
            ).strip()
            raise PhaseBError(
                f"GitHub GET failed for {endpoint}: {diagnostic or result.returncode}"
            )
        return _parse_included(result.stdout, endpoint)


class FixtureTransport:
    """Exact-response transport used only by the ``--transport`` test hook."""

    def __init__(self, responses: Mapping[str, Response]):
        self.responses = dict(responses)
        self.requests: list[tuple[str, str]] = []

    @classmethod
    def from_path(cls, path: Path) -> "FixtureTransport":
        try:
            value = json.loads(path.read_bytes())
        except (OSError, UnicodeError, ValueError) as exc:
            raise PhaseBError(f"cannot read transport fixture: {path}") from exc
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise PhaseBError("transport fixture must be a schema-version-1 object")
        raw = value.get("responses")
        if not isinstance(raw, dict):
            raise PhaseBError("transport fixture must contain a responses object")
        responses: dict[str, Response] = {}
        for endpoint, item in raw.items():
            if not isinstance(endpoint, str) or not isinstance(item, dict):
                raise PhaseBError("transport fixture responses have an invalid shape")
            headers = item.get("headers", {})
            if not isinstance(headers, dict) or not all(
                isinstance(key, str) and isinstance(child, str)
                for key, child in headers.items()
            ):
                raise PhaseBError(f"transport fixture headers are invalid for {endpoint}")
            responses[endpoint] = Response(
                item.get("body"), {key.lower(): child for key, child in headers.items()}
            )
        return cls(responses)

    def __call__(self, method: str, endpoint: str) -> Response:
        if method != "GET":
            raise PhaseBError(f"fixture transport refuses method {method}")
        self.requests.append((method, endpoint))
        if endpoint not in self.responses:
            raise PhaseBError(f"transport fixture has no response for {endpoint}")
        return self.responses[endpoint]


def _next_endpoint(headers: Mapping[str, str]) -> str | None:
    value = next(
        (child for name, child in headers.items() if name.lower() == "link"), None
    )
    if not value:
        return None
    for url, relations in LINK.findall(value):
        if "next" not in relations.split():
            continue
        parsed = urlsplit(url)
        if parsed.netloc and parsed.netloc.lower() != API_HOST:
            raise PhaseBError(f"GitHub pagination left {API_HOST}")
        endpoint = parsed.path.lstrip("/")
        return endpoint + (f"?{parsed.query}" if parsed.query else "")
    return None


def _object(transport: Transport, endpoint: str) -> dict[str, object]:
    value = transport("GET", endpoint).body
    if not isinstance(value, dict):
        raise PhaseBError(f"GitHub GET returned a non-object for {endpoint}")
    return value


def _items(
    transport: Transport, endpoint: str, *, field: str | None = None
) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    seen: set[str] = set()
    current: str | None = endpoint
    while current is not None:
        if current in seen:
            raise PhaseBError(f"GitHub pagination repeated {current}")
        seen.add(current)
        response = transport("GET", current)
        value = response.body
        if field is not None:
            if not isinstance(value, dict):
                raise PhaseBError(f"GitHub GET returned a non-object for {current}")
            value = value.get(field)
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise PhaseBError(f"GitHub GET returned a non-object list for {current}")
        found.extend(value)
        current = _next_endpoint(response.headers)
    return found


def _markers(text: object) -> list[tuple[str, dict[str, str]]]:
    if not isinstance(text, str):
        return []
    return [
        (
            match.group(1).lower(),
            {
                key.lower(): value
                for key, value in ATTRIBUTE.findall(match.group(2) or "")
            },
        )
        for match in MARKER.finditer(text)
    ]


def _opened_at(issue: dict[str, object], comments: list[dict[str, object]]) -> datetime:
    valid: set[datetime] = set()
    for source in (issue, *comments):
        for name, attributes in _markers(source.get("body")):
            if name != "phase-b-window" or set(attributes) != {"opened"}:
                continue
            try:
                valid.add(parse_timestamp(attributes["opened"]))
            except PhaseBError:
                # The settled artifact quotes the family as opened=... .  It is
                # documentation, not a timestamp-bearing record.
                continue
    if len(valid) != 1:
        raise PhaseBError(
            f"record issue must contain exactly one valid phase-b-window timestamp; found {len(valid)}"
        )
    return next(iter(valid))


def _change_from_pull(repository: str, pull: dict[str, object]) -> Change | None:
    number = pull.get("number")
    merged = pull.get("merged_at")
    if not isinstance(number, int) or not isinstance(merged, str):
        return None
    merged_at = parse_timestamp(merged)
    html_url = pull.get("html_url")
    if not isinstance(html_url, str):
        html_url = f"https://github.com/{repository}/pull/{number}"
    return Change(repository, number, merged_at, html_url, pull)


def read_window(transport: Transport, now: datetime) -> Window:
    record = f"repos/{RECORD_REPOSITORY}/issues/{RECORD_ISSUE}"
    issue = _object(transport, record)
    comments = _items(transport, f"{record}/comments?per_page=100")
    opened = _opened_at(issue, comments)
    if now < opened:
        raise PhaseBError("current time precedes the Phase B opening timestamp")
    deadline = opened + timedelta(days=CALENDAR_DAYS)
    cutoff = min(now, deadline)
    changes: list[Change] = []
    for repository in PRODUCT_REPOSITORIES:
        endpoint = (
            f"repos/{repository}/pulls?state=closed&sort=updated"
            "&direction=desc&per_page=100"
        )
        for pull in _items(transport, endpoint):
            change = _change_from_pull(repository, pull)
            if change is not None and opened <= change.merged_at <= cutoff:
                changes.append(change)
    changes.sort(key=lambda item: (item.merged_at, item.repository.lower(), item.number))
    changes = changes[:CHANGE_LIMIT]
    close_at = None
    if len(changes) == CHANGE_LIMIT:
        close_at = changes[-1].merged_at
    elif now >= deadline:
        close_at = deadline
    return Window(opened, deadline, close_at, tuple(changes))


def _created_in_window(
    record: dict[str, object], opened: datetime, closed: datetime
) -> bool:
    try:
        created = parse_timestamp(record.get("created_at"))
    except PhaseBError:
        return False
    return opened <= created <= closed


def _issue_number(record: dict[str, object]) -> int | None:
    number = record.get("number")
    if isinstance(number, int):
        return number
    url = record.get("issue_url")
    match = ISSUE_NUMBER.search(url) if isinstance(url, str) else None
    return int(match.group(1)) if match else None


def _valid_pr(attributes: dict[str, str], key: str) -> int | None:
    value = attributes.get(key, "")
    return int(value) if value.isdigit() and int(value) > 0 else None


def _read_change_surfaces(transport: Transport, change: Change) -> None:
    base = f"repos/{change.repository}"
    issue = _object(transport, f"{base}/issues/{change.number}")
    pull = _object(transport, f"{base}/pulls/{change.number}")
    _items(transport, f"{base}/issues/{change.number}/comments?per_page=100")
    _items(transport, f"{base}/pulls/{change.number}/reviews?per_page=100")
    _items(transport, f"{base}/pulls/{change.number}/comments?per_page=100")
    head = pull.get("head")
    sha = head.get("sha") if isinstance(head, dict) else None
    if not isinstance(sha, str) or not sha:
        fallback = change.pull.get("head")
        sha = fallback.get("sha") if isinstance(fallback, dict) else None
    if not isinstance(sha, str) or not sha:
        raise PhaseBError(
            f"qualifying pull request has no head SHA: {change.repository}#{change.number}"
        )
    _items(
        transport,
        f"{base}/commits/{sha}/check-runs?per_page=100",
        field="check_runs",
    )
    if issue.get("number") != change.number or pull.get("number") != change.number:
        raise PhaseBError(
            f"GitHub returned mismatched change records for {change.repository}#{change.number}"
        )


def _repository_measures(
    transport: Transport,
    repository: str,
    changes: tuple[Change, ...],
    opened: datetime,
    closed: datetime,
) -> dict[int, tuple[int, int, int]]:
    base = f"repos/{repository}"
    since = _timestamp_text(opened)
    issues = _items(
        transport, f"{base}/issues?state=all&since={since}&per_page=100"
    )
    comments = _items(
        transport, f"{base}/issues/comments?since={since}&per_page=100"
    )
    for change in changes:
        _read_change_surfaces(transport, change)

    change_by_number = {change.number: change for change in changes}
    issue_by_number = {
        int(issue["number"]): issue
        for issue in issues
        if isinstance(issue.get("number"), int)
    }
    followups = {number: set() for number in change_by_number}
    defects = {number: set() for number in change_by_number}
    asks = {number: set() for number in change_by_number}

    records: list[tuple[str, dict[str, object], dict[str, object] | None]] = []
    for issue in issues:
        if _created_in_window(issue, opened, closed):
            number = _issue_number(issue)
            records.append((f"issue:{number}", issue, issue))
    for comment in comments:
        if _created_in_window(comment, opened, closed):
            number = _issue_number(comment)
            records.append((f"comment:{comment.get('id')}", comment, issue_by_number.get(number)))

    for record_key, record, parent in records:
        parent_number = _issue_number(parent) if parent is not None else None
        parent_is_issue = parent is not None and not isinstance(parent.get("pull_request"), dict)
        for name, attributes in _markers(record.get("body")):
            if name == "change-followup" and set(attributes) == {"source_pr"}:
                source = _valid_pr(attributes, "source_pr")
                if source in followups and parent_is_issue and parent_number is not None:
                    followups[source].add(parent_number)
            elif name == "escaped-defect" and set(attributes) == {"found_by", "source_pr"}:
                source = _valid_pr(attributes, "source_pr")
                if (
                    source in defects
                    and attributes.get("found_by") == "use"
                    and parent_is_issue
                    and parent_number is not None
                ):
                    try:
                        created = parse_timestamp(parent.get("created_at"))
                    except PhaseBError:
                        continue
                    if created > change_by_number[source].merged_at:
                        defects[source].add(parent_number)
            elif name == "owner-ask" and set(attributes) == {"pr"}:
                source = _valid_pr(attributes, "pr")
                if source in asks:
                    asks[source].add(record_key)

    return {
        number: (len(followups[number]), len(defects[number]), len(asks[number]))
        for number in change_by_number
    }


def default_cost_reader(repository: str, number: int) -> dict[str, object]:
    return change_cost.report(
        repository,
        number,
        change_cost.default_dispatch_root(),
        LIB / "rates.json",
        change_cost.default_plan_terms(),
        change_cost.default_gauges(repository, number),
        change_cost.default_holder_usage(repository, number),
    )


def collect_measures(
    transport: Transport, window: Window, cost_reader: CostReader
) -> list[Measures]:
    if window.close_at is None:
        raise PhaseBError("Phase B has not reached a terminus")
    counts: dict[tuple[str, int], tuple[int, int, int]] = {}
    for repository in PRODUCT_REPOSITORIES:
        changes = tuple(
            change for change in window.changes if change.repository == repository
        )
        repo_counts = _repository_measures(
            transport, repository, changes, window.opened_at, window.close_at
        )
        counts.update(
            {
                (repository, number): value
                for number, value in repo_counts.items()
            }
        )
    rows = []
    for change in window.changes:
        followups, defects, asks = counts[(change.repository, change.number)]
        cost = cost_reader(change.repository, change.number)
        if not isinstance(cost, dict) or cost.get("marker") != "change-cost:v1":
            raise PhaseBError(
                f"cost reader returned no change-cost:v1 report for {change.repository}#{change.number}"
            )
        rows.append(Measures(change, followups, defects, asks, cost))
    return rows


def _cell(value: object) -> str:
    if value is None or value == [] or value == {}:
        return "unknown"
    rendered = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return rendered.replace("|", "\\|").replace("\n", "\\n")


def render(rows: list[Measures]) -> str:
    lines = [
        "| Change | Follow-ups created | Escaped defects found in use after merge | Asks put to owner | Cost: raw usage | Cost: rate-card price | Cost: bill or plan status |",
        "| --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in rows:
        change = row.change
        label = f"[{change.repository}#{change.number}]({change.html_url})"
        lines.append(
            "| "
            + " | ".join(
                (
                    label,
                    str(row.followups),
                    str(row.escaped_defects),
                    str(row.owner_asks),
                    _cell(row.cost.get("raw_usage")),
                    _cell(row.cost.get("dated_rate_card_equivalent")),
                    _cell(row.cost.get("bill_plan_status")),
                )
            )
            + " |"
        )
    lines.extend(
        (
            "",
            "| Close record | Link |",
            "| --- | --- |",
            f"| Product-change population | [#652](https://github.com/{RECORD_REPOSITORY}/issues/652) |",
            f"| Phase C decision record | [#360](https://github.com/{RECORD_REPOSITORY}/issues/360) |",
            f"| Phase C vendor record | [#653](https://github.com/{RECORD_REPOSITORY}/issues/653) |",
        )
    )
    return "\n".join(lines)


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        description="Read the Phase B record or render its terminal four-measure table."
    )
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--final", action="store_true")
    cli.add_argument("--now", help="aware ISO-8601 instant used by deterministic tests")
    cli.add_argument(
        "--transport", type=Path, help="schema-version-1 response fixture used by tests"
    )
    return cli


def run(
    args: argparse.Namespace,
    *,
    transport: Transport | None = None,
    cost_reader: CostReader = default_cost_reader,
) -> int:
    now = parse_timestamp(args.now) if args.now else datetime.now(timezone.utc)
    active_transport = transport
    if active_transport is None:
        active_transport = (
            FixtureTransport.from_path(args.transport) if args.transport else GitHubREST()
        )
    window = read_window(active_transport, now)
    if args.status:
        print(f"qualifying changes: {len(window.changes)}")
        print(f"days elapsed: {(now - window.opened_at).days}")
        return 0
    if window.close_at is None:
        print("phase-b: final report is unavailable before a terminus", file=sys.stderr)
        return 1
    print(render(collect_measures(active_transport, window, cost_reader)))
    return 0


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    try:
        return run(parser().parse_args(argv))
    except (OSError, UnicodeError, ValueError, PhaseBError, change_cost.CostError) as exc:
        print(f"score-phase-b: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

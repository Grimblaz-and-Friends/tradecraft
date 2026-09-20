from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import score_phase_b as spb  # noqa: E402


FIXTURE = Path(__file__).with_name("fixtures") / "score_phase_b.json"
OPENED = datetime(2026, 1, 1, tzinfo=timezone.utc)


def args(mode: str, now: datetime) -> argparse.Namespace:
    return argparse.Namespace(
        status=mode == "status",
        final=mode == "final",
        now=now.isoformat(),
        transport=None,
    )


def cost_report(repository: str, number: int) -> dict[str, object]:
    if number == 22:
        return {
            "marker": "change-cost:v1",
            "raw_usage": [],
            "dated_rate_card_equivalent": [],
            "bill_plan_status": [],
        }
    return {
        "marker": "change-cost:v1",
        "raw_usage": [
            {
                "dispatch": {"stage": "build", "actual_vendor": "codex"},
                "tokens": {"input": 100, "output": 20},
            }
        ],
        "dated_rate_card_equivalent": [
            {
                "dispatch_id": "d1",
                "value": {"status": "known", "currency": "USD", "amount": "0.12"},
            }
        ],
        "bill_plan_status": [
            {"vendor": "codex", "change_allocation": {"status": "unknown"}}
        ],
    }


def fixture_run(capsys: pytest.CaptureFixture[str]):
    transport = spb.FixtureTransport.from_path(FIXTURE)
    result = spb.run(
        args("final", OPENED + timedelta(days=28)),
        transport=transport,
        cost_reader=cost_report,
    )
    captured = capsys.readouterr()
    assert result == 0, captured.err
    return transport, captured.out


def test_i5_c1_one_four_measure_table_and_three_close_links(capsys):
    """I5-C1: each change gets the four measures and the close links all three records."""
    _transport, output = fixture_run(capsys)
    lines = output.splitlines()
    header = next(line for line in lines if line.startswith("| Change |"))
    assert output.count("| Change |") == 1
    assert "| Follow-ups created |" in header
    assert "| Escaped defects found in use after merge |" in header
    assert "| Asks put to owner |" in header
    assert header.count("| Cost:") == 3, "the fourth measure has three required subcolumns"
    rows = [line for line in lines if line.startswith("| [Grimblaz-and-Friends/")]
    assert len(rows) == 2
    assert "Organizations-of-Verra#11" in rows[0] and "| 1 | 1 | 2 |" in rows[0]
    assert "Daemon#22" in rows[1] and "| 1 | 1 | 3 |" in rows[1]
    for number in (652, 360, 653):
        assert f"[#{number}](https://github.com/{spb.RECORD_REPOSITORY}/issues/{number})" in output


def test_authorized_exclusion_removes_row_and_is_listed_with_reason(capsys):
    """A holder exclusion removes the matching row visibly in final mode."""
    _transport, output = fixture_run(capsys)
    change_rows = [
        line for line in output.splitlines()
        if line.startswith("| [Grimblaz-and-Friends/")
    ]
    assert all("Organizations-of-Verra#12" not in line for line in change_rows)
    assert (
        "| Excluded product pull request (practice-adoption) | "
        "[Grimblaz-and-Friends/Organizations-of-Verra#12]" in output
    )


def test_exclusion_outside_window_changes_nothing(capsys):
    """An exclusion cannot alter or annotate a pull request outside the window."""
    _transport, output = fixture_run(capsys)
    assert "Organizations-of-Verra#10" not in output
    assert "outside-window" not in output


def test_unauthorized_exclusion_is_ignored_and_named(capsys):
    """An untrusted exclusion leaves the row and is named in the close table."""
    _transport, output = fixture_run(capsys)
    assert any(
        "Daemon#22" in line
        for line in output.splitlines()
        if line.startswith("| [Grimblaz-and-Friends/")
    )
    assert (
        "| Ignored exclusion from untrusted-user (practice-adoption) | "
        "[Grimblaz-and-Friends/Daemon#22]" in output
    )


def test_window_marker_accepts_producer_and_names_ignored_nonproducer(capsys):
    """Only a configured producer can set the opening instant."""
    _transport, output = fixture_run(capsys)
    assert (
        "| Ignored phase-b-window from untrusted-user "
        "(2025-12-01T00:00:00Z) |" in output
    )


def test_window_requires_an_authorized_marker():
    """A valid marker from an unlisted author cannot open the window."""
    transport = spb.FixtureTransport.from_path(FIXTURE)
    endpoint = (
        f"repos/{spb.RECORD_REPOSITORY}/issues/{spb.RECORD_ISSUE}"
        "/comments?per_page=100"
    )
    response = transport.responses[endpoint]
    comments = [dict(item) for item in response.body]
    comments[0]["user"] = {"login": "untrusted-user"}
    transport.responses[endpoint] = spb.Response(comments, response.headers)
    with pytest.raises(spb.PhaseBError, match="found 0"):
        spb.read_window(transport, OPENED + timedelta(days=28))


def test_status_count_is_net_of_authorized_exclusions(capsys):
    """Status keeps its two-line shape and counts only qualifying changes."""
    transport = spb.FixtureTransport.from_path(FIXTURE)
    result = spb.run(
        args("status", OPENED + timedelta(days=28)), transport=transport
    )
    assert result == 0
    assert capsys.readouterr().out == "qualifying changes: 2\ndays elapsed: 28\n"


class BoundaryTransport:
    def __init__(
        self,
        count: int,
        exclude_number: int | None = None,
        exclusion_created_at: datetime | None = None,
    ):
        self.requests: list[tuple[str, str]] = []
        self.exclude_number = exclude_number
        self.exclusion_created_at = exclusion_created_at
        self.pulls = [
            {
                "number": number,
                "merged_at": (OPENED + timedelta(days=1, hours=number)).isoformat(),
                "html_url": f"https://github.com/{spb.PRODUCT_REPOSITORIES[0]}/pull/{number}",
                "head": {"sha": f"sha{number}"},
            }
            for number in range(1, count + 1)
        ]

    def __call__(self, method: str, endpoint: str) -> spb.Response:
        if method != "GET":
            raise spb.PhaseBError(f"test transport refuses method {method}")
        self.requests.append((method, endpoint))
        record = f"repos/{spb.RECORD_REPOSITORY}/issues/{spb.RECORD_ISSUE}"
        if endpoint == record:
            return spb.Response({"number": spb.RECORD_ISSUE, "body": ""}, {})
        if endpoint == f"{record}/comments?per_page=100":
            comments = [
                {
                    "id": 1,
                    "created_at": OPENED.isoformat(),
                    "body": "<!-- tradecraft:phase-b-window:v1 opened=2026-01-01T00:00:00Z -->",
                    "user": {"login": "Grimblaz"},
                }
            ]
            if self.exclude_number is not None:
                comments.append(
                    {
                        "id": 2,
                        "created_at": (
                            self.exclusion_created_at
                            or OPENED + timedelta(days=1, hours=2)
                        ).isoformat(),
                        "body": (
                            "<!-- tradecraft:phase-b-exclude:v1 "
                            f"pr={spb.PRODUCT_REPOSITORIES[0]}#{self.exclude_number} "
                            "reason=practice-adoption -->"
                        ),
                        "user": {"login": "Grimblaz"},
                    }
                )
            return spb.Response(
                comments,
                {},
            )
        pulls_endpoint = (
            f"repos/{spb.PRODUCT_REPOSITORIES[0]}/pulls?state=closed&sort=updated"
            "&direction=desc&per_page=100"
        )
        if endpoint == pulls_endpoint:
            return spb.Response(self.pulls, {})
        other_pulls = (
            f"repos/{spb.PRODUCT_REPOSITORIES[1]}/pulls?state=closed&sort=updated"
            "&direction=desc&per_page=100"
        )
        if endpoint == other_pulls:
            return spb.Response([], {})
        if "/issues?state=all&" in endpoint or "/issues/comments?" in endpoint:
            return spb.Response([], {})
        match = re.search(r"/(issues|pulls)/([1-9][0-9]*)\Z", endpoint)
        if match:
            number = int(match.group(2))
            body: dict[str, object] = {"number": number}
            if match.group(1) == "pulls":
                body["head"] = {"sha": f"sha{number}"}
            return spb.Response(body, {})
        if endpoint.endswith("?per_page=100") and "/commits/" in endpoint:
            return spb.Response({"check_runs": []}, {})
        if endpoint.endswith("?per_page=100"):
            return spb.Response([], {})
        raise AssertionError(f"unrecorded endpoint: {endpoint}")


def unknown_cost(_repository: str, _number: int) -> dict[str, object]:
    return {
        "marker": "change-cost:v1",
        "raw_usage": [],
        "dated_rate_card_equivalent": [],
        "bill_plan_status": [],
    }


def test_i5_c2_both_termini_and_preterminus_silence(capsys):
    """I5-C2: 27 days/19 changes is silent; either 28 days or 20 changes emits once."""
    nineteen = BoundaryTransport(19)
    result = spb.run(
        args("final", OPENED + timedelta(days=27)),
        transport=nineteen,
        cost_reader=unknown_cost,
    )
    captured = capsys.readouterr()
    assert result != 0 and captured.out == ""

    result = spb.run(
        args("final", OPENED + timedelta(days=28)),
        transport=nineteen,
        cost_reader=unknown_cost,
    )
    captured = capsys.readouterr()
    assert result == 0 and captured.out.count("| Change |") == 1

    twenty = BoundaryTransport(20)
    result = spb.run(
        args("final", OPENED + timedelta(days=10)),
        transport=twenty,
        cost_reader=unknown_cost,
    )
    captured = capsys.readouterr()
    assert result == 0 and captured.out.count("| Change |") == 1


def test_excluded_pull_request_does_not_supply_the_twentieth_change(capsys):
    """The change terminus counts the population after authorized exclusions."""
    nineteen_qualifying = BoundaryTransport(20, exclude_number=1)
    result = spb.run(
        args("final", OPENED + timedelta(days=10)),
        transport=nineteen_qualifying,
        cost_reader=unknown_cost,
    )
    captured = capsys.readouterr()
    assert result != 0 and captured.out == ""

    twenty_qualifying = BoundaryTransport(21, exclude_number=1)
    result = spb.run(
        args("final", OPENED + timedelta(days=10)),
        transport=twenty_qualifying,
        cost_reader=unknown_cost,
    )
    captured = capsys.readouterr()
    assert result == 0 and captured.out.count("| Change |") == 1


def test_exclusion_after_twentieth_change_cannot_reopen_closed_window(capsys):
    """A marker created after the terminus is outside the record window."""
    transport = BoundaryTransport(
        20,
        exclude_number=1,
        exclusion_created_at=OPENED + timedelta(days=3),
    )
    result = spb.run(
        args("final", OPENED + timedelta(days=10)),
        transport=transport,
        cost_reader=unknown_cost,
    )
    output = capsys.readouterr().out
    assert result == 0
    assert output.count("| Change |") == 1
    assert "Excluded product pull request" not in output


def test_status_prints_only_count_and_days(capsys):
    transport = BoundaryTransport(19)
    assert spb.run(args("status", OPENED + timedelta(days=27)), transport=transport) == 0
    assert capsys.readouterr().out == "qualifying changes: 19\ndays elapsed: 27\n"
    assert not any("/reviews" in endpoint for _method, endpoint in transport.requests)


def test_i5_c3_fixture_read_needs_no_product_checkout(tmp_path, monkeypatch, capsys):
    """I5-C3: recorded GitHub records supply both products from an unrelated directory."""
    monkeypatch.chdir(tmp_path)
    transport = spb.FixtureTransport.from_path(FIXTURE)
    result = spb.run(
        args("final", OPENED + timedelta(days=28)),
        transport=transport,
        cost_reader=cost_report,
    )
    output = capsys.readouterr().out
    assert result == 0
    assert all(repository in output for repository in spb.PRODUCT_REPOSITORIES)


def test_i5_c5_cost_quantities_are_separate_and_unknown_is_explicit(capsys):
    """I5-C5: raw, rate-card, and bill/plan values do not collapse or become zero."""
    _transport, output = fixture_run(capsys)
    header = next(line for line in output.splitlines() if line.startswith("| Change |"))
    assert "| Cost: raw usage | Cost: rate-card price | Cost: bill or plan status |" in header
    daemon = next(line for line in output.splitlines() if "Daemon#22" in line)
    assert daemon.count('"status":"unknown"') == 3
    assert "actual_vendor" in output and '"amount":"0.12"' in output


def test_cost_uses_work_issue_and_no_issue_has_explicit_unknown_reason(capsys):
    """Cost reads the work issue, while an unlinked pull request remains explicit."""
    seen: list[tuple[str, int]] = []

    def recording_cost_reader(repository: str, issue_number: int) -> dict[str, object]:
        seen.append((repository, issue_number))
        return cost_report(repository, issue_number)

    transport = spb.FixtureTransport.from_path(FIXTURE)
    result = spb.run(
        args("final", OPENED + timedelta(days=28)),
        transport=transport,
        cost_reader=recording_cost_reader,
    )
    output = capsys.readouterr().out
    assert result == 0
    assert seen == [(spb.PRODUCT_REPOSITORIES[0], 91)]
    daemon = next(line for line in output.splitlines() if "Daemon#22" in line)
    assert daemon.count(
        "no work issue found for Grimblaz-and-Friends/Daemon#22"
    ) == 3


def test_work_issue_evidence_accepts_closing_reference_and_authorized_marker():
    """Reverse resolution mirrors both evidence forms and marker authorization."""
    change = spb.Change(
        spb.PRODUCT_REPOSITORIES[0],
        11,
        OPENED + timedelta(days=1),
        "https://example.invalid/pull/11",
        {"body": "Fixes #90"},
    )
    issues = [
        {
            "number": 91,
            "user": {"login": "Grimblaz"},
            "body": "<!-- tradecraft:implementing-pr:v1 number=11 -->",
        },
        {
            "number": 92,
            "user": {"login": "untrusted-user"},
            "body": "<!-- tradecraft:implementing-pr:v1 number=11 -->",
        },
        {
            "number": 93,
            "pull_request": {},
            "user": {"login": "Grimblaz"},
            "body": "<!-- tradecraft:implementing-pr:v1 number=11 -->",
        },
        {"number": 94, "body": "ordinary issue"},
    ]
    comments = [
        {
            "id": 1,
            "issue_url": (
                "https://api.github.com/repos/example/project/issues/94"
            ),
            "user": {"login": "Grimblaz"},
            "body": "<!-- tradecraft:implementing-pr:v1 number=11 -->",
        }
    ]
    assert spb._work_issue_candidates(
        change, issues, comments, frozenset({"grimblaz"})
    ) == (90, 91, 94)


def test_i5_c5_unreadable_cost_report_is_unknown_in_all_three_columns(monkeypatch):
    """I5-C5: an unavailable report stays unknown instead of aborting the close."""
    def unavailable(*_arguments, **_keywords):
        raise spb.change_cost.CostError("unrelated dispatch record is unreadable")

    monkeypatch.setattr(spb.change_cost, "report", unavailable)
    report = spb.default_cost_reader(spb.PRODUCT_REPOSITORIES[0], 11)
    for field in (
        "raw_usage", "dated_rate_card_equivalent", "bill_plan_status"
    ):
        assert report[field] is None


def test_output_has_no_comparative_word_and_keeps_merge_order(capsys):
    """I5-C1 guard: measures do not add a comparison or change chronological ordering."""
    _transport, output = fixture_run(capsys)
    lowered = output.lower()
    assert "rank" not in lowered and "score" not in lowered
    assert output.index("Organizations-of-Verra#11") < output.index("Daemon#22")
    assert "| 1 | 1 | 3 |" in output, "the later row has the larger count total"


def test_i5_c6_transport_is_get_only_and_follows_link_pages(monkeypatch, capsys):
    """I5-C6: every observed API request is GET and mutation is refused before launch."""
    transport, _output = fixture_run(capsys)
    assert transport.requests and {method for method, _endpoint in transport.requests} == {"GET"}
    assert [endpoint for _method, endpoint in transport.requests] == [
        f"repos/{spb.RECORD_REPOSITORY}/issues/{spb.RECORD_ISSUE}",
        f"repos/{spb.RECORD_REPOSITORY}/issues/{spb.RECORD_ISSUE}/comments?per_page=100",
        (
            f"repos/{spb.PRODUCT_REPOSITORIES[0]}/pulls?state=closed&sort=updated"
            "&direction=desc&per_page=100"
        ),
        (
            f"repos/{spb.PRODUCT_REPOSITORIES[1]}/pulls?state=closed&sort=updated"
            "&direction=desc&per_page=100"
        ),
        (
            f"repos/{spb.PRODUCT_REPOSITORIES[0]}/issues?state=all"
            "&per_page=100"
        ),
        (
            f"repos/{spb.PRODUCT_REPOSITORIES[0]}/issues?state=all"
            "&per_page=100&page=2"
        ),
        (
            f"repos/{spb.PRODUCT_REPOSITORIES[0]}/issues/comments"
            "?per_page=100"
        ),
        (
            f"repos/{spb.PRODUCT_REPOSITORIES[1]}/issues?state=all"
            "&per_page=100"
        ),
        (
            f"repos/{spb.PRODUCT_REPOSITORIES[1]}/issues/comments"
            "?per_page=100"
        ),
    ]
    with pytest.raises(spb.PhaseBError, match="refuses method"):
        transport("POST", "repos/example/project/issues/1/comments")

    launched = False

    def subprocess_spy(*_arguments, **_keywords):
        nonlocal launched
        launched = True
        raise AssertionError("a refused method reached the subprocess")

    monkeypatch.setattr(spb.subprocess, "run", subprocess_spy)
    with pytest.raises(spb.PhaseBError, match="refuses method"):
        spb.GitHubREST()("PATCH", "repos/example/project/issues/1")
    assert not launched


def test_owner_asks_count_only_issue_bodies_and_issue_comments(capsys):
    """Owner asks on pull-request bodies and conversations do not count."""
    _transport, output = fixture_run(capsys)
    row = next(line for line in output.splitlines() if "Organizations-of-Verra#11" in line)
    assert "| 1 | 1 | 2 |" in row

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


class BoundaryTransport:
    def __init__(self, count: int):
        self.requests: list[tuple[str, str]] = []
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
            return spb.Response(
                [
                    {
                        "id": 1,
                        "created_at": OPENED.isoformat(),
                        "body": "<!-- tradecraft:phase-b-window:v1 opened=2026-01-01T00:00:00Z -->",
                    }
                ],
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
    assert daemon.endswith("| unknown | unknown | unknown |")
    assert "actual_vendor" in output and '"amount":"0.12"' in output


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
    assert any(endpoint.endswith("&page=2") for _method, endpoint in transport.requests)
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

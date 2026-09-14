"""Behavioral coverage for the complete external-review evidence receipt."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "external_pass.py"

spec = importlib.util.spec_from_file_location("external_pass", SCRIPT)
external_pass = importlib.util.module_from_spec(spec)
spec.loader.exec_module(external_pass)


def source_data():
    """Three sources with an exact-multiple control on review comments."""
    return {
        "issue_comments": [
            {"id": 101, "body": "issue one"},
            {"id": 102, "body": "issue two"},
            {"id": 103, "body": "issue three"},
        ],
        "review_comments": [
            {"id": 201, "body": "inline one"},
            {"id": 202, "body": "inline two"},
        ],
        "reviews": [{"id": 301, "body": "submitted review", "state": "COMMENTED"}],
    }


def endpoint_wire(snapshots, calls):
    """Return paged JSON, moving to the next snapshot at each full pass."""
    endpoints = {
        source["label"]: external_pass.source_endpoint("owner/repo", 17, source)
        for source in external_pass.SOURCES
    }
    reverse = {endpoint: label for label, endpoint in endpoints.items()}
    pass_number = -1

    def wire(endpoint):
        nonlocal pass_number
        parsed = urlsplit(endpoint)
        label = reverse[parsed.path]
        query = parse_qs(parsed.query)
        page = int(query["page"][0])
        size = int(query["per_page"][0])
        if label == "issue_comments" and page == 1:
            pass_number += 1
        snapshot = snapshots[min(pass_number, len(snapshots) - 1)]
        calls.append((pass_number, label, page, size))
        start = (page - 1) * size
        return json.dumps(snapshot[label][start:start + size])

    return wire


def collect(monkeypatch, tmp_path, capsys, data=None):
    """Collect one stable receipt with a small page size that exposes paging."""
    monkeypatch.setattr(external_pass, "PAGE_SIZE", 2)
    data = data or source_data()
    calls = []
    monkeypatch.setattr(external_pass, "gh_api", endpoint_wire([data, data], calls))
    output = tmp_path / "external-pass.json"
    assert external_pass.main([
        "collect", "--repo", "owner/repo", "--pr", "17", "--output", str(output),
    ]) == 0
    return output, calls, capsys.readouterr()


def test_collect_preserves_every_raw_object_proves_terminal_pages_and_prints_receipt(
        monkeypatch, tmp_path, capsys):
    output, calls, captured = collect(monkeypatch, tmp_path, capsys)
    bundle_bytes = output.read_bytes()
    bundle = json.loads(bundle_bytes)

    assert bundle["schema"] == external_pass.SCHEMA
    assert bundle["repository"] == "owner/repo"
    assert bundle["pull_request"] == 17
    for label, objects in source_data().items():
        source = bundle["sources"][label]
        assert source["objects"] == objects
        assert source["completeness"]["page_size"] == 2
        assert source["completeness"]["page_lengths"][-1] < 2

    # `review_comments` is exactly one page long. The empty second page is the
    # control showing that a full page never becomes an invented terminus.
    review_pages = [page for _, label, page, _ in calls if label == "review_comments"]
    assert review_pages == [1, 2, 1, 2]
    digest = hashlib.sha256(bundle_bytes).hexdigest()
    assert f"sha256: {digest}" in captured.out
    assert "issue_comments: 3" in captured.out
    assert "review_comments: 2" in captured.out
    assert "reviews: 1" in captured.out
    assert "total: 6" in captured.out
    assert "verify" in captured.out and str(output) in captured.out
    assert captured.err == ""


def test_collect_accepts_empty_and_single_page_sources(monkeypatch, tmp_path, capsys):
    data = {
        "issue_comments": [],
        "review_comments": [{"id": 2, "body": "one"}],
        "reviews": [],
    }
    output, _, captured = collect(monkeypatch, tmp_path, capsys, data)
    assert output.is_file()
    assert "total: 1" in captured.out


@pytest.mark.parametrize("kind", [
    "gh failure", "malformed JSON", "non-list JSON", "missing id",
    "duplicate id", "safety ceiling", "unstable second drain",
])
def test_collect_refuses_unlawful_sources_without_creating_a_bundle(
        monkeypatch, tmp_path, capsys, kind):
    output = tmp_path / "must-not-exist.json"
    monkeypatch.setattr(external_pass, "PAGE_SIZE", 2)

    if kind == "gh failure":
        def wire(endpoint):
            raise external_pass.ExternalPassError("gh api failed: unavailable")
    elif kind == "malformed JSON":
        wire = lambda endpoint: "{not JSON"
    elif kind == "non-list JSON":
        wire = lambda endpoint: "{}"
    elif kind == "missing id":
        wire = lambda endpoint: json.dumps([{"body": "missing"}])
    elif kind == "duplicate id":
        wire = lambda endpoint: json.dumps([{"id": 1}, {"id": 1}])
    elif kind == "safety ceiling":
        monkeypatch.setattr(external_pass, "PAGE_SIZE", 1)
        monkeypatch.setattr(external_pass, "MAX_PAGES", 2)
        data = source_data()
        data["issue_comments"] = [{"id": 1}, {"id": 2}]
        wire = endpoint_wire([data], [])
    else:
        first = source_data()
        second = source_data()
        second["reviews"] = [{"id": 301, "body": "changed", "state": "COMMENTED"}]
        wire = endpoint_wire([first, second], [])

    monkeypatch.setattr(external_pass, "gh_api", wire)
    assert external_pass.main([
        "collect", "--repo", "owner/repo", "--pr", "17", "--output", str(output),
    ]) == 1
    captured = capsys.readouterr()
    assert not output.exists()
    assert captured.err.startswith("external-pass:")
    assert "Traceback" not in captured.err
    if kind == "unstable second drain":
        assert "reviews" in captured.err and "changed" in captured.err
    if kind == "safety ceiling":
        assert "issue_comments" in captured.err and "safety ceiling" in captured.err


def test_collect_refuses_an_existing_destination_without_replacing_it(
        monkeypatch, tmp_path, capsys):
    output = tmp_path / "already-there.json"
    before = b"previous receipt"
    output.write_bytes(before)
    monkeypatch.setattr(external_pass, "gh_api", lambda endpoint: pytest.fail("must not fetch"))
    assert external_pass.main([
        "collect", "--repo", "owner/repo", "--pr", "17", "--output", str(output),
    ]) == 1
    assert output.read_bytes() == before
    assert "already exists" in capsys.readouterr().err


@pytest.mark.parametrize("mutation, expected", [
    (lambda data: data["issue_comments"].append({"id": 104, "body": "new"}), "added: 104"),
    (lambda data: data["review_comments"].pop(), "removed: 202"),
    (lambda data: data["reviews"].__setitem__(0, {"id": 301, "body": "edited", "state": "COMMENTED"}),
     "changed: 301"),
])
def test_verify_matches_or_reports_source_drift_without_rewriting_the_receipt(
        monkeypatch, tmp_path, capsys, mutation, expected):
    output, _, _ = collect(monkeypatch, tmp_path, capsys)
    before = output.read_bytes()

    unchanged = source_data()
    monkeypatch.setattr(external_pass, "gh_api", endpoint_wire([unchanged, unchanged], []))
    assert external_pass.main(["verify", str(output)]) == 0
    assert hashlib.sha256(before).hexdigest() in capsys.readouterr().out

    changed = source_data()
    mutation(changed)
    monkeypatch.setattr(external_pass, "gh_api", endpoint_wire([changed, changed], []))
    assert external_pass.main(["verify", str(output)]) == 1
    captured = capsys.readouterr()
    assert "source drift" in captured.err
    assert expected in captured.err
    assert output.read_bytes() == before


def test_verify_distinguishes_a_source_failure_from_drift(monkeypatch, tmp_path, capsys):
    output, _, _ = collect(monkeypatch, tmp_path, capsys)
    before = output.read_bytes()

    def wire(endpoint):
        raise external_pass.ExternalPassError("gh api failed: denied")

    monkeypatch.setattr(external_pass, "gh_api", wire)
    assert external_pass.main(["verify", str(output)]) == 1
    captured = capsys.readouterr()
    assert "source failure" in captured.err
    assert "source drift" not in captured.err
    assert output.read_bytes() == before


def test_every_gh_launch_names_all_three_streams(monkeypatch):
    seen = {}

    def run(command, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "[]", "")

    monkeypatch.setattr(external_pass.subprocess, "run", run)
    assert external_pass.gh_api("repos/owner/repo/issues/17/comments?per_page=2&page=1") == "[]"
    assert seen["stdin"] is subprocess.DEVNULL
    assert seen["stdout"] is subprocess.PIPE
    assert seen["stderr"] is subprocess.PIPE
    assert seen["encoding"] == "utf-8"

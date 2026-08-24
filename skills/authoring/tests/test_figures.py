"""Behavioral tests for figures.py: the fixed bases are pinned (universal-
newline doc measure, CRLF-normalized delta), the refusals refuse, and both
renderings carry the basis and the invocation. Fixtures are throwaway git
repositories built per test, on both OSes in CI."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "figures.py"

spec = importlib.util.spec_from_file_location("authoring_figures", SCRIPT)
figures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(figures)


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def cli(cwd, *args):
    return run([sys.executable, str(SCRIPT), *args], cwd=cwd)


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], cwd=repo)
    run(["git", "config", "user.email", "t@example.com"], cwd=repo)
    run(["git", "config", "user.name", "tester"], cwd=repo)
    # core.autocrlf off so the bytes committed are the bytes written — the
    # delta figure's whole claim is that its count is checkout-independent.
    run(["git", "config", "core.autocrlf", "false"], cwd=repo)
    return repo


def commit_all(repo, message):
    run(["git", "add", "-A"], cwd=repo)
    run(["git", "commit", "-m", message], cwd=repo)


# --- doc figure: the measure is a universal-newline text read ---------------

def test_doc_counts_crlf_as_one_character(tmp_path):
    doc = tmp_path / "NOTES.md"
    doc.write_bytes(b"a\r\nb")  # 4 bytes, 3 characters under the stated basis
    fig = figures.figure_doc(tmp_path, "NOTES.md", 100)
    assert fig["data"]["chars"] == 3
    assert fig["data"]["headroom"] == 97
    assert "universal-newline" in fig["basis"]


def test_doc_headroom_goes_negative_over_budget(tmp_path):
    (tmp_path / "NOTES.md").write_bytes(b"abcdef")
    fig = figures.figure_doc(tmp_path, "NOTES.md", 4)
    assert fig["data"]["headroom"] == -2
    assert "-2" in fig["value"]


# --- delta figure: raw blobs, CRLF normalized, explicit base ----------------

def test_delta_normalizes_crlf_on_both_sides(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "NOTES.md").write_bytes(b"x\r\ny")
    commit_all(repo, "base")
    (repo / "NOTES.md").write_bytes(b"x\r\nyz")
    fig = figures.figure_delta(repo, "HEAD", ["NOTES.md"])
    # base "x\ny" = 3 chars, current "x\nyz" = 4 — CRLF never inflates either side
    assert fig["data"] == {
        "base": "HEAD", "paths": ["NOTES.md"], "suffixes": [],
        "base_chars": 3, "current_chars": 4, "delta": 1,
    }
    assert "+1" in fig["value"]


def test_delta_counts_untracked_additions_and_deletions(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "a.md").write_bytes(b"12345")
    commit_all(repo, "base")
    (repo / "a.md").unlink()          # deleted from the working tree
    (repo / "b.md").write_bytes(b"123")  # added, not yet committed
    fig = figures.figure_delta(repo, "HEAD", ["."])
    assert fig["data"]["base_chars"] == 5
    assert fig["data"]["current_chars"] == 3
    assert fig["data"]["delta"] == -2


def test_delta_suffix_filter_limits_both_sides(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "a.md").write_bytes(b"12")
    (repo / "a.py").write_bytes(b"123456789")
    commit_all(repo, "base")
    (repo / "a.py").write_bytes(b"1")
    fig = figures.figure_delta(repo, "HEAD", ["."], [".md"])
    assert fig["data"]["delta"] == 0  # the .py churn is outside the stated basis
    assert ".md" in fig["basis"]


def test_delta_refuses_an_unknown_base_loudly(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "a.md").write_bytes(b"x")
    commit_all(repo, "base")
    result = cli(repo, "--base", "no-such-ref", "--delta", "a.md")
    assert result.returncode != 0
    assert "no-such-ref" in result.stderr


# --- refusals: incomplete inputs never guess --------------------------------

def test_doc_without_budget_refuses(tmp_path):
    (tmp_path / "NOTES.md").write_bytes(b"x")
    result = cli(tmp_path, "--doc", "NOTES.md")
    assert result.returncode != 0
    assert "--budget" in result.stderr


def test_delta_without_base_refuses(tmp_path):
    result = cli(tmp_path, "--delta", "NOTES.md")
    assert result.returncode != 0
    assert "never defaulted" in result.stderr


def test_base_without_delta_refuses(tmp_path):
    result = cli(tmp_path, "--base", "HEAD")
    assert result.returncode != 0


def test_suffix_without_delta_refuses(tmp_path):
    result = cli(tmp_path, "--delta-suffix", ".md")
    assert result.returncode != 0


def test_no_figure_requested_refuses(tmp_path):
    result = cli(tmp_path)
    assert result.returncode != 0
    assert "no figure requested" in result.stderr


# --- suite figure: the summary is reported verbatim, red included -----------

def test_suite_figure_reports_passes(tmp_path):
    (tmp_path / "test_ok.py").write_text(
        "def test_a():\n    assert True\n\n\ndef test_b():\n    assert True\n",
        encoding="utf-8",
    )
    fig = figures.figure_tests(tmp_path, ["test_ok.py"])
    assert fig["value"] == "2 passed"
    assert fig["data"]["exit"] == 0


def test_suite_figure_does_not_hide_failures(tmp_path):
    (tmp_path / "test_red.py").write_text(
        "def test_ok():\n    assert True\n\n\ndef test_no():\n    assert False\n",
        encoding="utf-8",
    )
    fig = figures.figure_tests(tmp_path, ["test_red.py"])
    assert "1 failed" in fig["value"]
    assert "1 passed" in fig["value"]
    assert fig["data"]["exit"] != 0


def test_summary_parser_drops_duration_only():
    assert figures.parse_pytest_summary("184 passed in 1.23s") == "184 passed"
    assert (
        figures.parse_pytest_summary("3 failed, 181 passed in 65.02s")
        == "3 failed, 181 passed"
    )
    assert figures.parse_pytest_summary("== 5 passed in 0.1s ==") == "5 passed"
    assert figures.parse_pytest_summary("something odd\n") == "something odd"
    assert figures.parse_pytest_summary("") == "no output"


# --- renderings: the block carries tree, invocation, and basis --------------

def test_markdown_carries_tree_command_and_basis(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "NOTES.md").write_bytes(b"hello")
    commit_all(repo, "base")
    (repo / "extra.md").write_bytes(b"!")  # dirty tree must be stamped as dirty
    result = cli(repo, "--doc", "NOTES.md", "--budget", "50")
    assert result.returncode == 0, result.stderr
    out = result.stdout
    head = run(["git", "rev-parse", "--short", "HEAD"], cwd=repo).stdout.strip()
    assert f"tree `{head}` (dirty)" in out
    assert "derived by `python figures.py --doc NOTES.md --budget 50`" in out
    assert "**5 of 50 chars, headroom 45**" in out
    assert "universal-newline" in out


def test_json_mode_round_trips(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "NOTES.md").write_bytes(b"hello")
    commit_all(repo, "base")
    result = cli(repo, "--doc", "NOTES.md", "--budget", "50", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["tree"]["dirty"] is False
    assert payload["figures"][0]["data"]["headroom"] == 45


def test_no_git_tree_is_said_not_faked(tmp_path):
    (tmp_path / "NOTES.md").write_bytes(b"x")
    result = cli(tmp_path, "--doc", "NOTES.md", "--budget", "10")
    assert result.returncode == 0, result.stderr
    assert "no git tree identified" in result.stdout

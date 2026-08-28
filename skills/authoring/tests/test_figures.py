"""Behavioral tests for figures.py: the fixed bases are pinned (universal-
newline doc measure, CRLF-normalized delta), the refusals refuse, and both
renderings carry the basis and the invocation. Fixtures are throwaway git
repositories built per test, on both OSes in CI."""

import importlib.util
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_doc_missing_file_is_a_designed_refusal_not_a_traceback(tmp_path):
    result = cli(tmp_path, "--doc", "NO_SUCH.md", "--budget", "100")
    assert result.returncode != 0
    assert "not a readable file" in result.stderr
    assert "Traceback" not in result.stderr


# --- delta figure: raw blobs, CRLF normalized, explicit base ----------------

def test_delta_normalizes_crlf_on_both_sides(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "NOTES.md").write_bytes(b"x\r\ny")
    commit_all(repo, "base")
    (repo / "NOTES.md").write_bytes(b"x\r\nyz")
    fig = figures.figure_delta(repo, "HEAD", ["NOTES.md"])
    base_sha = fig["data"]["base_sha"]
    # base "x\ny" = 3 chars, current "x\nyz" = 4 — CRLF never inflates either side
    assert fig["data"] == {
        "base": "HEAD", "base_sha": base_sha, "paths": ["NOTES.md"], "suffixes": [],
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


def test_delta_refuses_when_no_file_matches_on_either_side(tmp_path):
    # A typo'd path (or suffix) must never paste as a confident +0.
    repo = make_repo(tmp_path)
    (repo / "notes.md").write_bytes(b"x")
    commit_all(repo, "base")
    result = cli(repo, "--base", "HEAD", "--delta", "notse")
    assert result.returncode != 0
    assert "matched no files on either side" in result.stderr
    # ...while one empty side stays lawful: a directory the change adds.
    (repo / "new").mkdir()
    (repo / "new" / "b.md").write_bytes(b"12")
    fig = figures.figure_delta(repo, "HEAD", ["new"])
    assert fig["data"] == {
        "base": "HEAD", "base_sha": fig["data"]["base_sha"], "paths": ["new"],
        "suffixes": [],
        "base_chars": 0, "current_chars": 2, "delta": 2,
    }


def test_delta_counts_non_ascii_filenames_despite_quotepath(tmp_path):
    # git's default core.quotePath C-escapes non-ASCII names in newline
    # output; the NUL-delimited enumeration must keep them in both totals.
    repo = make_repo(tmp_path)
    run(["git", "config", "core.quotePath", "true"], cwd=repo)
    # The character is the subject under test, so it is built rather than
    # written: emitted strings stay ASCII, and the one fixture that must
    # carry a non-ASCII character says so instead of needing an exemption.
    e_acute = chr(0xE9)
    name = f"r{e_acute}sum{e_acute}.md"
    body = f"h{e_acute}llo"
    (repo / name).write_bytes(body.encode("utf-8"))
    commit_all(repo, "base")
    (repo / name).write_bytes((body + "!!").encode("utf-8"))
    fig = figures.figure_delta(repo, "HEAD", ["."], [".md"])
    assert fig["data"]["base_chars"] == 5
    assert fig["data"]["current_chars"] == 7
    assert fig["data"]["delta"] == 2


def test_delta_from_a_subdirectory_resolves_the_repo_root(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "notes.md").write_bytes(b"abc")
    sub = repo / "sub"
    sub.mkdir()
    (sub / "inner.md").write_bytes(b"12")
    commit_all(repo, "base")
    (repo / "notes.md").write_bytes(b"abcd")
    result = cli(sub, "--base", "HEAD", "--delta", ".", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    # Enumerated and read from the repository root, not the subdirectory.
    assert payload["figures"][0]["data"]["delta"] == 1
    assert payload["figures"][0]["data"]["base_chars"] == 5


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
    # The fallback drops the duration too — no block's value may differ
    # across re-derivations, the parser's own stated reason.
    assert figures.parse_pytest_summary("no tests ran in 0.00s") == "no tests ran"


def test_suite_figure_refuses_a_mistyped_test_path(tmp_path):
    # pytest exit 4 (usage error): nothing was measured, so a pasteable
    # block would be a guess-shaped output from an input error.
    with pytest.raises(SystemExit, match="measured nothing"):
        figures.figure_tests(tmp_path, ["no_such_dir"])


def test_suite_figure_refuses_an_empty_collection(tmp_path):
    # pytest exit 5 (no tests collected) is the same class.
    (tmp_path / "empty").mkdir()
    with pytest.raises(SystemExit, match="measured nothing"):
        figures.figure_tests(tmp_path, ["empty"])


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
    assert "derived by `python " in out
    assert "**5 of 50 chars, headroom 45**" in out
    assert "universal-newline" in out


def test_stamped_command_reproduces_verbatim(tmp_path):
    # The block's whole warrant: re-running the stamped line re-derives the
    # figures. Extract the stamp and run it, from the tree the block stamps.
    repo = make_repo(tmp_path)
    (repo / "NOTES.md").write_bytes(b"hello")
    commit_all(repo, "base")
    first = cli(repo, "--doc", "NOTES.md", "--budget", "50")
    assert first.returncode == 0, first.stderr
    stamped = re.search(r"derived by `python ([^`]+)`", first.stdout).group(1)
    second = run([sys.executable, *shlex.split(stamped)], cwd=repo)
    assert second.returncode == 0, second.stderr
    assert second.stdout == first.stdout


def test_stamp_quotes_arguments_with_spaces(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "my notes.md").write_bytes(b"hi")
    commit_all(repo, "base")
    first = cli(repo, "--doc", "my notes.md", "--budget", "50")
    assert first.returncode == 0, first.stderr
    stamped = re.search(r"derived by `python ([^`]+)`", first.stdout).group(1)
    assert "'my notes.md'" in stamped
    second = run([sys.executable, *shlex.split(stamped)], cwd=repo)
    assert second.stdout == first.stdout


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


# --- the cell figure: a body measured apart from its always-on frontmatter ---
#
# These ride here rather than beside the guard because what proves shipped code
# has to travel with it to every consumer. The one test that cannot live here is
# the strip-agreement pin, which compares this engine to a repo-only guard: a
# shipped file may not reach the repo-only zone, so its residence is forced.

CELL = (
    "---\n"
    "name: example\n"
    "description: A cell.\n"
    "---\n"
    "\n"
    "Body line one.\n"
)


def test_cell_measures_the_body_and_not_the_frontmatter(tmp_path):
    (tmp_path / "SKILL.md").write_text(CELL, encoding="utf-8")
    body = len("Body line one.\n")
    result = cli(tmp_path, "--cell", "SKILL.md", "--budget", str(body + 10))
    assert result.returncode == 0, result.stderr
    assert f"{body:,} of {body + 10:,} chars, headroom 10" in result.stdout
    assert "(body)" in result.stdout
    # The whole file is larger; --doc is the figure that says so.
    whole = cli(tmp_path, "--doc", "SKILL.md", "--budget", str(body + 10))
    assert f"{len(CELL):,} of" in whole.stdout


def test_cell_reports_a_negative_headroom_rather_than_refusing(tmp_path):
    """Over budget is a figure, not an error -- the caller is writing it up."""
    (tmp_path / "SKILL.md").write_text(CELL, encoding="utf-8")
    result = cli(tmp_path, "--cell", "SKILL.md", "--budget", "1")
    assert result.returncode == 0, result.stderr
    assert "headroom -14" in result.stdout


def test_frontmatterless_leaves_a_file_without_frontmatter_alone(tmp_path):
    """A plain document measured as a cell is the document, not an error."""
    (tmp_path / "NOTES.md").write_text("Just prose.\n", encoding="utf-8")
    result = cli(tmp_path, "--cell", "NOTES.md", "--budget", "100")
    assert result.returncode == 0, result.stderr
    assert "12 of 100 chars" in result.stdout


def test_cell_refuses_without_a_budget_a_missing_file_and_a_doubled_measure(tmp_path):
    """The three refusals the cell figure added, each in both polarities.

    A budget picked silently is how a stated figure leaves behind the guard
    that judges it, so the script refuses rather than defaulting -- the same
    ground on which it refuses to invent a delta base.
    """
    (tmp_path / "SKILL.md").write_text(CELL, encoding="utf-8")
    no_budget = cli(tmp_path, "--cell", "SKILL.md")
    assert no_budget.returncode != 0 and "--budget" in no_budget.stderr
    missing = cli(tmp_path, "--cell", "nosuch.md", "--budget", "10")
    assert missing.returncode != 0 and "not a readable file" in missing.stderr
    doubled = cli(tmp_path, "--doc", "SKILL.md", "--cell", "SKILL.md", "--budget", "10")
    assert doubled.returncode != 0 and "pick one" in doubled.stderr
    # ...and the lawful spelling of each still works.
    assert cli(tmp_path, "--cell", "SKILL.md", "--budget", "10").returncode == 0
    assert cli(tmp_path, "--doc", "SKILL.md", "--budget", "10").returncode == 0


def test_delta_resolves_a_moving_base_to_a_sha(tmp_path):
    """A moving ref satisfies "given explicitly" and still leaves the figure
    un-recheckable.

    A review found that `--base origin/main` was echoed back exactly as given,
    so a write-up complying with the figure rule in full could still name a base
    that means a different tree tomorrow — which is the basis error the rule was
    written against. The label carries the resolution; the ref alone did not.
    """
    repo = make_repo(tmp_path)
    (repo / "NOTES.md").write_bytes(b"aaa")
    commit_all(repo, "base")
    run(["git", "branch", "moving"], cwd=repo)
    (repo / "NOTES.md").write_bytes(b"aaaa")

    fig = figures.figure_delta(repo, "moving", ["NOTES.md"])
    sha = fig["data"]["base_sha"]
    assert sha and sha != "moving"
    assert f"`moving` ({sha})" in fig["name"], fig["name"]
    # The negative control: a base already given as a sha must not be doubled up.
    # Both spellings, because the first version of this control bound only the
    # abbreviated one and a full sha -- the most pinned base a write-up can name
    # -- was doubled with the control green.
    for pinned in (sha, run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()):
        fixed = figures.figure_delta(repo, pinned, ["NOTES.md"])
        assert fixed["name"] == f"prose delta vs `{pinned}`", fixed["name"]

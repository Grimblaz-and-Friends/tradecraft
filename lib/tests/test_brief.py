import subprocess
import sys
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import brief

SCRIPT = LIB / "brief.py"


def draft(decision="**1. Keep the decision small.**"):
    return (
        "## Shape\n"
        "The result has the agreed shape.\n\n"
        "**Readers.** Owner and builder.\n\n"
        f"{decision}\n\n"
        "## Not this\n\n"
        "Review risk: ordinary\n"
        "Review lane: connected\n"
    )


@pytest.mark.parametrize("decision", [
    "| Decision | Why | Owner |\n| --- | --- | --- |\n| Keep it small | Because | Clear |",
    "## Row 1 - Keep the decision small",
    "**R1. Keep the decision small.**",
    "**1. Keep the decision small.**",
])
def test_each_established_decision_block_shape_is_accepted(decision):
    assert brief.missing_elements(draft(decision)) == ()


def test_heading_labels_may_carry_their_content_on_the_next_line():
    assert brief.missing_elements(draft()) == ()


@pytest.mark.parametrize(("risk", "lane"), list(brief.LANES.items()))
def test_each_lawful_review_pair_is_accepted(risk, lane):
    text = draft().replace("ordinary", risk).replace("connected", lane)
    assert brief.missing_elements(text) == ()


@pytest.mark.parametrize(("needle", "element"), [
    ("## Shape\nThe result has the agreed shape.\n\n", "Shape"),
    ("**Readers.** Owner and builder.\n\n", "Readers"),
    ("**1. Keep the decision small.**\n\n", "decision block"),
    ("## Not this\n\n", "Not this"),
    ("Review risk: ordinary\nReview lane: connected\n", "Review risk / Review lane pair"),
])
def test_each_omission_is_refused_by_name(needle, element):
    assert brief.missing_elements(draft().replace(needle, "")) == (element,)


def test_missing_elements_are_returned_in_stable_form_order():
    assert brief.missing_elements("") == brief.ELEMENTS


@pytest.mark.parametrize("rows", [
    "Review risk: ordinary\n",
    "Review lane: connected\n",
    "Review risk: ordinary\nReview lane: substantial-panel\n",
    "Review risk: ordinary\nReview risk: elevated\nReview lane: connected\n",
    "Review risk: ordinary\nReview lane: connected\nReview lane: connected\n",
])
def test_missing_duplicate_or_crossed_review_rows_are_refused(rows):
    prefix = draft().split("Review risk:", 1)[0]
    assert brief.missing_elements(prefix + rows) == ("Review risk / Review lane pair",)


@pytest.mark.parametrize(("old", "new", "element"), [
    ("## Not this", "## Not in scope", "Not this"),
    ("**1. Keep the decision small.**", "Decision one discusses a row.", "decision block"),
])
def test_near_misses_do_not_satisfy_the_check(old, new, element):
    assert brief.missing_elements(draft().replace(old, new)) == (element,)


def test_presence_does_not_judge_content_reasons_or_reader_cells():
    defective = draft("**1. Bad.**")
    assert brief.missing_elements(defective) == ()


def run_cli(path, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--check", str(path)],
        cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True,
    )


def assert_ascii_output(result):
    result.stdout.decode("ascii")
    result.stderr.decode("ascii")


def test_cli_runs_from_an_arbitrary_directory_and_states_its_limit(tmp_path):
    body = tmp_path / ("brief-" + chr(0x2603) + ".md")
    body.write_text(draft(), encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = run_cli(body, elsewhere)
    assert result.returncode == 0
    assert_ascii_output(result)
    output = result.stdout.decode("ascii")
    assert "required elements present" in output
    assert "content, reasons, and reader cells were not checked" in output


def test_cli_names_every_missing_element_on_standard_error(tmp_path):
    body = tmp_path / "brief.md"
    body.write_text("", encoding="utf-8")
    result = run_cli(body, tmp_path)
    assert result.returncode == 1
    assert result.stdout == b""
    error = result.stderr.decode("ascii")
    for element in brief.ELEMENTS:
        assert element in error


def test_cli_names_an_invalid_utf8_file_with_ascii_output(tmp_path):
    body = tmp_path / ("invalid-" + chr(0x2603) + ".md")
    body.write_bytes(b"\xff")
    result = run_cli(body, tmp_path)
    assert result.returncode == 1
    assert_ascii_output(result)
    assert "invalid-\\u2603.md is not valid UTF-8" in result.stderr.decode("ascii")


@pytest.mark.parametrize("kind", ["missing", "directory"])
def test_cli_names_an_unreadable_input(kind, tmp_path):
    path = tmp_path / ("unreadable-" + chr(0x2603))
    if kind == "directory":
        path.mkdir()
    result = run_cli(path, tmp_path)
    assert result.returncode == 1
    assert_ascii_output(result)
    error = result.stderr.decode("ascii")
    assert "could not read" in error
    assert "unreadable-\\u2603" in error


def test_cli_help_is_ascii_and_successful(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=tmp_path, stdin=subprocess.DEVNULL, capture_output=True,
    )
    assert result.returncode == 0
    assert_ascii_output(result)
    assert "--check FILE" in result.stdout.decode("ascii")

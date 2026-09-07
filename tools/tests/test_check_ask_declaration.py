"""Tests for the ask-declaration guard (issue #423).

Everything here runs offline: the predicate is pure, and the CLI is driven
through `--body-file`, so nothing reaches `gh`.

The guard is probed in both polarities, which for a guard is the whole of what
proves it -- the unlawful case caught, the lawful case left alone. It also
carries a negative control drawn from its own class: markers that are *nearly*
right must fail, because a check that matched anything vaguely declaration-
shaped would report the same PASS whether or not the author wrote the line,
which is the result this guard would be credited with and would not have taken.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "check_ask_declaration.py"

spec = importlib.util.spec_from_file_location("check_ask_declaration", SCRIPT)
guard = importlib.util.module_from_spec(spec)
sys.modules["check_ask_declaration"] = guard
spec.loader.exec_module(guard)

MARKER = guard.MARKER


# --- the lawful polarity: a declaration is found, and its content comes back ---

@pytest.mark.parametrize("body, expected", [
    (f"{MARKER} nothing.", "nothing."),
    (f"Closes #1\n\n{MARKER} the tie question, marked on #123.",
     "the tie question, marked on #123."),
    # Indented, inside a list, and inside a blockquote: the line is stripped
    # before matching, so a body that renders the declaration visibly is not
    # refused over leading whitespace.
    (f"   {MARKER} nothing.", "nothing."),
    (f"- {MARKER} nothing.".replace("- ", ""), "nothing."),
    # Trailing content on later lines does not shadow the first match.
    (f"{MARKER} the first one.\n{MARKER} a second.", "the first one."),
])
def test_declaration_found(body, expected):
    assert guard.declaration(body) == expected


# --- the unlawful polarity: no declaration ---

@pytest.mark.parametrize("body", [
    "",
    "Closes #1\n\nA body with no declaration at all.",
    # A body that reads exactly like the failure this guard exists for: an
    # argued ask, three options and a recommendation, and no declaration.
    "Closes #1\n\nOn the tie, three options: A, B, C. I recommend B and will\n"
    "proceed on it unless ruled otherwise at release.",
])
def test_declaration_absent(body):
    assert guard.declaration(body) is None


def test_marker_with_no_content_is_not_a_declaration():
    """An empty declaration would make the check unfailable.

    A guard that passes on the marker alone asks the author for a token rather
    than an answer, and every body would carry one within a week.
    """
    assert guard.declaration(MARKER) is None
    assert guard.declaration(f"{MARKER}   ") is None


# --- the negative control, drawn from the guard's own class ---

@pytest.mark.parametrize("near_miss", [
    "Waiting on you: nothing.",             # unbolded
    "**Waiting on:** nothing.",             # wrong words
    "**waiting on you:** nothing.",         # wrong case
    "**Waiting on you** nothing.",          # no colon inside the bold
    "*Waiting on you:* nothing.",           # single-emphasis
])
def test_near_miss_markers_do_not_satisfy_the_guard(near_miss):
    """Shows the guard would have reported differently had the answer differed.

    Without this, `test_declaration_found` alone is consistent with a predicate
    that returns the rest of any line containing the word "waiting".
    """
    assert guard.declaration(near_miss) is None


# --- the CLI, both polarities, through the exit code CI reads ---

def test_cli_passes_on_a_body_that_declares(tmp_path, capsys):
    body = tmp_path / "body.md"
    body.write_text(f"Closes #1\n\n{MARKER} nothing.\n", encoding="utf-8")
    assert guard.main(["--body-file", str(body)]) == 0
    assert "present" in capsys.readouterr().out


def test_cli_fails_on_a_body_that_does_not(tmp_path, capsys):
    body = tmp_path / "body.md"
    body.write_text("Closes #1\n\nNothing here.\n", encoding="utf-8")
    assert guard.main(["--body-file", str(body)]) == 1
    err = capsys.readouterr().err
    assert "missing" in err
    # The refusal names what to write. A guard that says only "no" makes the
    # next session guess at the form, and a guessed marker fails again.
    assert MARKER in err


def test_cli_fails_loudly_on_an_unreadable_body_file(tmp_path, capsys):
    missing = tmp_path / "nope.md"
    assert guard.main(["--body-file", str(missing)]) == 1
    assert "could not read body file" in capsys.readouterr().err


def test_cli_requires_a_source():
    """Neither --pr nor --body-file is a usage error, not a silent pass."""
    with pytest.raises(SystemExit) as exc:
        guard.main([])
    assert exc.value.code != 0


def test_this_repository_documents_the_marker_it_enforces():
    """The guard and the cell that states the rule must not drift apart.

    A marker changed here and not in the landing cell would refuse every
    compliant body; changed there and not here, the guard would enforce a form
    nobody is told to write.
    """
    cell = (ROOT / "docs" / "cells" / "landing" / "SKILL.md").read_text(encoding="utf-8")
    assert MARKER in cell

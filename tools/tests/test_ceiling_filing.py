"""The ratchet's filing step, probed without a network call.

Every decision this script makes before it touches `gh` is a pure function, so
the properties that matter are testable here: that a cell already carrying an
open item is never filed twice, that the marker survives a reworded title, and
that the body says what the filing cell's carve-out requires it to say.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ceiling_filing as cf  # noqa: E402


ROWS = [
    ("skills/filing/SKILL.md", 24_158, 23_237),
    ("docs/cells/board/SKILL.md", 18_400, 17_916),
]


def test_a_cell_with_no_open_item_is_filed():
    assert cf.needs_filing(ROWS, set()) == ROWS


def test_a_cell_already_carrying_an_open_item_is_not_filed_twice():
    """One item per cell, never one per commit.

    The pool's accrual counts symptoms under the cause, so a second issue for
    the same cell would climb a band on one cell's growth and misreport how
    wide the problem is.
    """
    seen = {cf.marker_for("skills/filing/SKILL.md")}
    assert cf.needs_filing(ROWS, seen) == [ROWS[1]]


def test_every_cell_already_seen_files_nothing():
    seen = {cf.marker_for(rel) for rel, _, _ in ROWS}
    assert cf.needs_filing(ROWS, seen) == []


def test_the_marker_is_the_path_and_survives_a_reworded_title():
    """Recognition keys on the marker, not on prose that will be reworded."""
    rel = "skills/filing/SKILL.md"
    assert cf.marker_for(rel) == f"{cf.MARKER} {rel}"
    assert cf.marker_for(rel) in cf.body_for(rel, 1, 0)
    assert rel not in cf.title_for(rel), (
        "a title carrying the path would make the marker redundant and the "
        "title load-bearing, which is what keys recognition to prose")


def test_the_body_carries_the_measurement_and_the_command_that_derives_it():
    """The carve-out admits this item on its measurement, so it must carry one."""
    body = cf.body_for("skills/filing/SKILL.md", 24_158, 23_237)
    assert "24158" in body.replace(",", "") or "24_158" in body
    assert "23237" in body.replace(",", "") or "23_237" in body
    assert "cells_over_ceiling" in body, "no command a reader can re-derive it with"


def test_the_body_states_its_own_provenance_as_the_filing_cell_requires():
    """This repository's own filer obeys the element it ships.

    The rule is one line under `**Provenance:**` whose first word is an origin
    from the closed list. A script raising an item is `instrument`, and the
    check is the classifier that reads the element rather than a substring:
    a body that merely mentions the word would pass the second and fail the
    consumer that matters.
    """
    import trial_intake as ti

    body = cf.body_for("skills/filing/SKILL.md", 24_158, 23_237)
    cls, _, basis = ti.classify(body)
    assert (cls, basis) == ("instrument", "stated"), (cls, basis)


def test_the_body_never_tells_a_reader_to_cut():
    """The owner's red line, made executable.

    The ruling is that a ceiling directs to filing, not cutting content, and
    may not tell a session not to add text. An item raised by the ceiling is
    the ceiling speaking, so the prohibition reaches this text too.
    """
    body = cf.body_for("skills/filing/SKILL.md", 24_158, 23_237)
    lowered = body.lower()
    for word in ("do not add", "don't add", "stop adding", "trim", "shrink"):
        assert word not in lowered, f"the raised item says {word!r}"
    assert "nothing was\nblocked" in body or "nothing was blocked" in body.replace("\n", " ")


def test_the_ratings_are_a_pair_the_pool_policy_names():
    """A filing carries two ratings, one per axis, from the policy's own set."""
    import json
    policy = json.loads(
        (ROOT / "skills" / "filing" / "scripts" / "pool-policy.json")
        .read_text(encoding="utf-8"))
    allowed = set(policy["axes"]["severity"]["values"]) | set(policy["axes"]["urgency"]["values"])
    assert len(cf.RATINGS) == 2
    assert set(cf.RATINGS) <= allowed, cf.RATINGS
    axes = {r.split(":")[0] for r in cf.RATINGS}
    assert axes == {"sev", "urg"}, "the two ratings must be one per axis"


# `test_this_repository_is_at_its_ceilings` stood here and was removed.
#
# It asserted `lint.cells_over_ceiling(ROOT) == []` over this repository, to
# catch a baseline measured against a different tree than the one that shipped
# -- which had happened once, when a rebase moved three cell bodies after the
# numbers were taken. But that assertion is true of exactly one tree and false
# on any lawful growth, so it made a cell growing past its ceiling fail a test:
# the refusal the owner's ruling took out of the guard, arriving through the
# suite instead. `test_lint.py::test_the_declared_cell_body_ceilings_are_the_ones_these_tests_pin`
# refuses to pin the ceiling *values* for that exact reason, so the two tests
# landed in one change contradicting each other.
#
# A cold consumer adding a rule to a cell at its ceiling was the first thing to
# trip it, and read the contradiction off the suite itself.
#
# Nothing replaces it. Staleness at landing and growth after it are the same
# observation to any later tree, so no standing test separates them; what the
# baseline is checked against is the measurement the landing session runs.

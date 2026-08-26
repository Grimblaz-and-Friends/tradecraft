"""Tests for the project roster (issue #199).

Each fixture builds a minimal tree in tmp_path, so the generator and the guard
are proven to fire and to stay quiet, per shape. The unlawful shapes are the
point: this guard exists because a roster that is absent, stale, or orphaned
is invisible from inside a session -- the descriptions simply do not load, and
nothing in the transcript says so.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import lint  # noqa: E402
import roster  # noqa: E402

NL = chr(10)


def make_cell(root: Path, name: str, description: str = "A fixture cell.") -> Path:
    """One cell under skills/, with frontmatter a runtime can parse.

    Written as bytes, so the fixture models this repository's tree rather than
    the platform it runs on: `.gitattributes` pins the working tree to LF
    everywhere, and a text-mode write would hand Windows a CRLF cell no
    checkout here produces.
    """
    cell = root / "skills" / name
    cell.mkdir(parents=True, exist_ok=True)
    path = cell / "SKILL.md"
    path.write_bytes(
        ("---" + NL + f"name: {name}" + NL + f"description: {description}" + NL
         + "---" + NL + NL + f"# {name}" + NL + "Body." + NL).encode("utf-8")
    )
    return path


def test_a_generated_roster_verifies_clean(tmp_path):
    """The lawful polarity, which matters as much as the others: a guard that
    reds a tree nobody can fix is a guard somebody deletes."""
    make_cell(tmp_path, "alpha")
    make_cell(tmp_path, "beta")
    roster.write(tmp_path)
    assert roster.verify(tmp_path) == []


def test_a_missing_entry_fires(tmp_path):
    """The defect itself: a cell whose description loads in no session here."""
    make_cell(tmp_path, "alpha")
    findings = roster.verify(tmp_path)
    assert len(findings) == 1
    assert ".claude/skills/alpha/SKILL.md is missing" in findings[0]
    assert "tools/roster.py --write" in findings[0]


def test_an_entry_out_of_step_fires(tmp_path):
    """The one this guard is really for. An edited description is the whole
    triggering surface changing, and the entry keeps serving the old trigger
    to every session until somebody regenerates."""
    make_cell(tmp_path, "alpha", "The first description.")
    roster.write(tmp_path)
    make_cell(tmp_path, "alpha", "A different description entirely.")
    findings = roster.verify(tmp_path)
    assert len(findings) == 1
    assert "out of step" in findings[0]
    roster.write(tmp_path)
    assert roster.verify(tmp_path) == []


def test_an_orphan_entry_fires_and_is_removed(tmp_path):
    """An entry naming a cell that is gone puts a retired trigger in every
    session's context, which is worse than the missing entry above: the
    session acts on a rule the tree no longer carries."""
    make_cell(tmp_path, "alpha")
    make_cell(tmp_path, "beta")
    roster.write(tmp_path)
    (tmp_path / "skills" / "beta" / "SKILL.md").unlink()
    findings = roster.verify(tmp_path)
    assert len(findings) == 1
    assert "names no cell" in findings[0]
    roster.write(tmp_path)
    assert roster.verify(tmp_path) == []
    assert not (tmp_path / ".claude" / "skills" / "beta").exists()


def test_no_cells_is_a_finding_not_a_pass(tmp_path):
    """#198's shape, closed here at the point it would bite. No cell found is
    indistinguishable from every cell lawful, and the cheapest route to green
    must never be deleting what the check reads."""
    findings = roster.verify(tmp_path)
    assert len(findings) == 1
    assert "an empty roster is not a clean one" in findings[0]


def test_the_entry_copies_the_frontmatter_byte_for_byte(tmp_path):
    """The description is what has to load, so it is what has to be identical.
    A paraphrase, a re-wrap, or a re-emitted YAML scalar is a second wording of
    the trigger, and the two would then fire on different things."""
    source = make_cell(tmp_path, "alpha", "Use when the fixture is exercised.")
    roster.write(tmp_path)
    entry = (tmp_path / ".claude" / "skills" / "alpha" / "SKILL.md").read_bytes()
    block = roster.frontmatter(source.read_bytes())
    assert entry.startswith(block)
    assert lint._frontmatter_fields(entry.decode("utf-8")) == (
        lint._frontmatter_fields(source.read_text(encoding="utf-8"))
    )


def test_the_entry_names_its_generator_and_its_source(tmp_path):
    """A session opening the file learns from that file alone that it is
    generated, what generates it, and where the cell is -- with nothing else
    loaded, which is the only state it can count on."""
    make_cell(tmp_path, "alpha")
    roster.write(tmp_path)
    text = (tmp_path / ".claude" / "skills" / "alpha" / "SKILL.md").read_text(
        encoding="utf-8")
    assert "tools/roster.py" in text
    assert "skills/alpha/SKILL.md" in text
    assert "Do not edit this one" in text


def test_a_cell_whose_frontmatter_will_not_parse_is_a_finding(tmp_path):
    """Never write an entry with nothing to load. A frontmatter block a runtime
    cannot parse loads as empty metadata -- no name, no trigger, silently --
    and reproducing that here would be this script manufacturing the failure
    check_cell_frontmatter exists to catch."""
    cell = tmp_path / "skills" / "alpha"
    cell.mkdir(parents=True)
    (cell / "SKILL.md").write_text("# alpha" + NL + "No frontmatter." + NL,
                                   encoding="utf-8")
    findings = roster.verify(tmp_path)
    assert len(findings) == 1
    assert "no parseable frontmatter" in findings[0]
    with pytest.raises(ValueError):
        roster.expected(tmp_path, "alpha")


def test_the_generator_introduces_no_carriage_return_of_its_own(tmp_path):
    """The substrate cell's third text-mode rule, at the site it protects.

    An LF cell must produce an LF entry on every platform. A text-mode write
    would turn each line feed into a carriage return pair on Windows and not
    on Linux, so the same tree would hold different bytes depending on where
    the generator last ran -- and this file is compared byte for byte on every
    lint run. The copied frontmatter carries the source's own line endings by
    construction, which is what `.gitattributes` pins to LF here; what this
    pins is that nothing downstream of the read adds any.
    """
    make_cell(tmp_path, "alpha")
    roster.write(tmp_path)
    assert b"\r" not in (
        tmp_path / ".claude" / "skills" / "alpha" / "SKILL.md").read_bytes()


def test_writing_twice_changes_nothing_the_second_time(tmp_path):
    """Idempotent, so the fix a finding names can be run without reading the
    tree first, and running it on a clean tree reports honestly that it did
    nothing rather than rewriting nine files."""
    make_cell(tmp_path, "alpha")
    assert roster.write(tmp_path) != []
    assert roster.write(tmp_path) == []


def test_the_guard_asks_the_generator_rather_than_recomputing(tmp_path):
    """The coupling that keeps one definition. A guard computing its own copy
    of what a writer produces agrees with it exactly until either is edited --
    the failure `_always_on` in tools/figures.py already records, where two
    hand-written copies of one sum let a mutation through green."""
    make_cell(tmp_path, "alpha")
    make_cell(tmp_path, "beta")
    roster.write(tmp_path)
    (tmp_path / ".claude" / "skills" / "beta" / "SKILL.md").write_bytes(b"drift\n")
    assert lint.check_project_roster(tmp_path) == roster.verify(tmp_path)
    assert lint.check_project_roster(tmp_path) != []


def test_this_repository_carries_a_roster_for_every_cell(tmp_path):
    """The tree this all exists for. Not a restatement of the guard: the guard
    proves the shapes, and this proves the shipped tree is in one of them --
    which is the claim #199 found false and nothing was checking."""
    assert roster.cell_names(ROOT) == roster.roster_names(ROOT)
    assert roster.cell_names(ROOT) != []
    assert roster.verify(ROOT) == []
    for name in roster.roster_names(ROOT):
        entry = ROOT / ".claude" / "skills" / name / "SKILL.md"
        assert b"\r" not in entry.read_bytes(), (
            f"{name}: the tree holds CRLF where .gitattributes pins LF"
        )

"""Tests for the project roster (issue #199).

Each fixture builds a minimal tree in tmp_path, so the generator and the guard
are proven to fire and to stay quiet, per shape. The unlawful shapes are the
point, and they fail in two different ways: an **absent** entry loads nothing,
while a **stale** one loads the superseded trigger to every session until
somebody regenerates. The second is the worse failure and the one this guard
is really for -- an earlier version of this docstring called both of them "the
descriptions simply do not load", which named the milder failure for the shape
its own out-of-step test calls the guard's whole point. [PR #210 review, M20]
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


def test_a_hand_written_project_skill_is_never_removed(tmp_path):
    """The high this review raised, at the site it fires.

    `.claude/skills/<name>/SKILL.md` is the runtime's documented home for a
    project's own skills, which is the whole property this generator depends
    on -- so the directory is shared, not owned. The orphan branch used to
    print `--write` against anything it found there, and `--write` unlinked
    it: an untracked file, no prompt, exit 0, lint green afterwards. Three
    seats ran that deletion independently.
    """
    make_cell(tmp_path, "alpha")
    roster.write(tmp_path)
    helper = tmp_path / ".claude" / "skills" / "repo-helper"
    helper.mkdir(parents=True)
    (helper / "SKILL.md").write_bytes(
        ("---" + NL + "name: repo-helper" + NL
         + "description: Written by hand, not by the generator." + NL
         + "---" + NL + NL + "Real content somebody wrote." + NL).encode("utf-8")
    )
    assert roster.verify(tmp_path) == [], (
        "a project skill at a name that is no cell is not the roster's "
        "business, and reporting it was a red the lint could never clear"
    )
    roster.write(tmp_path)
    assert (helper / "SKILL.md").is_file(), "write() removed a file it did not author"
    assert b"Real content" in (helper / "SKILL.md").read_bytes()


def test_a_hand_written_file_at_a_cells_name_is_reported_not_overwritten(tmp_path):
    """The other half of the same ownership question, and the one the first
    fix missed.

    Removal was guarded and regeneration was not, so a hand-written file whose
    name collided with a cell was still destroyed by the command the guard
    printed -- reported as `wrote`, exit 0, lint green afterwards. `spikes`,
    `filing` and `authoring` are ordinary names for a project skill, so the
    collision is not exotic.

    It is a finding rather than silence, unlike the no-cell case above,
    because the hand-written frontmatter is what the runtime loads: the cell's
    real description loads nowhere, which is criterion 1 failing quietly.
    """
    make_cell(tmp_path, "spikes")
    roster.write(tmp_path)
    entry = tmp_path / ".claude" / "skills" / "spikes" / "SKILL.md"
    entry.write_bytes(
        ("---" + NL + "name: spikes" + NL + "description: Mine, by hand." + NL
         + "---" + NL + NL + "Irreplaceable, untracked." + NL).encode("utf-8")
    )

    findings = roster.verify(tmp_path)
    assert len(findings) == 1
    assert "was not written by tools/roster.py" in findings[0]
    assert "move your file out" in findings[0]

    lines = roster.write(tmp_path)
    assert any("left" in line and "spikes" in line for line in lines)
    assert b"Irreplaceable, untracked." in entry.read_bytes(), (
        "write() overwrote a file it did not author"
    )
    assert roster.verify(tmp_path) != [], "the collision must not go quiet"


def test_a_generated_orphan_is_still_removed(tmp_path):
    """The lawful polarity of the same branch: refusing to touch what it did
    not write must not stop it removing what it did."""
    make_cell(tmp_path, "alpha")
    make_cell(tmp_path, "beta")
    roster.write(tmp_path)
    (tmp_path / "skills" / "beta" / "SKILL.md").unlink()
    roster.write(tmp_path)
    assert not (tmp_path / ".claude" / "skills" / "beta").exists()
    assert roster.verify(tmp_path) == []


def test_residue_left_by_a_removal_is_reported_when_it_is_created(tmp_path):
    """A removed orphan with siblings leaves a directory behind, and `write()`
    says so at the moment it does it -- which is where the report is useful.

    `verify()` says nothing about it afterwards, deliberately. A standing
    finding there would red the lint on any directory a session left under
    `.claude/skills/`, which is the unclearable red the ownership rule exists
    to stop. The accepted residual is that a directory with no `SKILL.md`
    draws no standing red; it holds no skill, so it loads nothing.
    """
    make_cell(tmp_path, "alpha")
    make_cell(tmp_path, "beta")
    roster.write(tmp_path)
    entry = tmp_path / ".claude" / "skills" / "beta"
    (entry / "references").mkdir()
    (entry / "references" / "notes.md").write_bytes(b"depth\n")
    (tmp_path / "skills" / "beta" / "SKILL.md").unlink()
    lines = roster.write(tmp_path)
    assert any("left" in line and "references" in line for line in lines)
    assert roster.verify(tmp_path) == []


def test_deleting_one_entry_reports_one_finding_not_two(tmp_path):
    """The commonest repairable state must not also draw an unrepairable one.

    The residue branch used to fire alongside the missing-entry finding on the
    same condition, so one deletion produced two findings and only one of them
    named a command.
    """
    make_cell(tmp_path, "alpha")
    roster.write(tmp_path)
    (tmp_path / ".claude" / "skills" / "alpha" / "SKILL.md").unlink()
    findings = roster.verify(tmp_path)
    assert len(findings) == 1
    assert "is missing" in findings[0]


def test_write_reports_an_unreadable_cell_and_finishes_the_rest(tmp_path):
    """`--write` is the command every repairable finding names, so it must not
    hand back a traceback and a tree in neither state.

    Ordered so the broken cell sits between two that need work: before the
    fix, `alpha` was written, `zeta` was not, and the orphan survived because
    the removal loop was never reached.
    """
    make_cell(tmp_path, "alpha", "Needs regenerating.")
    make_cell(tmp_path, "zeta", "Also needs regenerating.")
    roster.write(tmp_path)
    make_cell(tmp_path, "alpha", "Edited after generation.")
    make_cell(tmp_path, "zeta", "Edited after generation too.")
    broken = tmp_path / "skills" / "mm-broken"
    broken.mkdir()
    (broken / "SKILL.md").write_bytes(b"# no frontmatter\n")
    orphan = tmp_path / ".claude" / "skills" / "gone"
    orphan.mkdir(parents=True)
    (orphan / "SKILL.md").write_bytes(roster.expected(tmp_path, "alpha"))

    lines = roster.write(tmp_path)

    assert any("skipped" in line and "mm-broken" in line for line in lines)
    for name in ("alpha", "zeta"):
        entry = (tmp_path / ".claude" / "skills" / name / "SKILL.md").read_bytes()
        assert b"Edited after generation" in entry, f"{name} was not regenerated"
    assert not orphan.exists(), "the removal loop was never reached"
    remaining = roster.verify(tmp_path)
    assert len(remaining) == 1 and "no parseable frontmatter" in remaining[0]


def test_every_shape_the_docstring_names_behaves_as_it_says(tmp_path):
    """The docstring names its shapes instead of counting them, because a
    stated count has now been wrong twice -- the second time in the sentence
    written to fix the first. This walks the named list.

    Three name `--write`; two name no command; one condition is silent.
    """
    # Silent: a foreign entry at a name that is no cell.
    make_cell(tmp_path, "alpha")
    roster.write(tmp_path)
    foreign = tmp_path / ".claude" / "skills" / "mine"
    foreign.mkdir(parents=True)
    (foreign / "SKILL.md").write_bytes(b"---\nname: mine\ndescription: d\n---\n\nx\n")
    assert roster.verify(tmp_path) == []
    (foreign / "SKILL.md").unlink()
    foreign.rmdir()

    # Names --write: missing, out of step, generated orphan.
    (tmp_path / ".claude" / "skills" / "alpha" / "SKILL.md").unlink()
    assert all("--write" in f for f in roster.verify(tmp_path))
    roster.write(tmp_path)
    make_cell(tmp_path, "alpha", "Moved on since generation.")
    assert all("--write" in f for f in roster.verify(tmp_path))
    roster.write(tmp_path)
    orphan = tmp_path / ".claude" / "skills" / "gone"
    orphan.mkdir(parents=True)
    (orphan / "SKILL.md").write_bytes(roster.expected(tmp_path, "alpha"))
    assert all("--write" in f for f in roster.verify(tmp_path))
    roster.write(tmp_path)

    # Names no command: collision, and unparseable frontmatter.
    entry = tmp_path / ".claude" / "skills" / "alpha" / "SKILL.md"
    entry.write_bytes(b"---\nname: alpha\ndescription: mine\n---\n\nhand-written\n")
    collision = roster.verify(tmp_path)
    assert len(collision) == 1 and "--write" not in collision[0].split(" -- ")[0]
    assert "move your file out" in collision[0]
    entry.unlink()
    roster.write(tmp_path)
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_bytes(b"# no frontmatter\n")
    unparseable = [f for f in roster.verify(tmp_path) if "parseable" in f]
    assert len(unparseable) == 1 and "--write" not in unparseable[0]
    assert "fix the cell's frontmatter" in unparseable[0]


def test_an_empty_skills_directory_names_no_command_either(tmp_path):
    """#198's shape keeps its own pin: it is a finding, and no command
    repairs it."""
    empty = roster.verify(tmp_path)
    assert len(empty) == 1 and "--write" not in empty[0]


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

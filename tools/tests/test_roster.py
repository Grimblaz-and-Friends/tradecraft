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

# The surfaces by runtime, for fixtures that touch one of them by name. Taken
# from the generator rather than spelled here: a fixture holding its own copy
# of a directory name goes on testing a surface the generator has stopped
# writing.
CLAUDE, CODEX = roster.SURFACES


def entry_of(root: Path, surface: roster.Surface, name: str) -> Path:
    """One cell's entry on one surface."""
    return root / surface.directory / name / roster.CELL_FILE


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


def crlf(path: Path) -> None:
    """Rewrite a file the way a Claude Code session worktree's harness copy does.

    Not a hypothetical: a Claude Code **session** worktree comes up with these
    nine files and `CLAUDE.md` written in text mode by the harness, while git
    checks out the other 108 tracked files LF in the same second. `agent-*`
    subagent worktrees do not do this, and saying "every worktree" is what sent
    all five seats of this change's review to the wrong conclusion. [#224]

    Normalised before converting, so this is a text-mode round trip rather than
    a doubling: applied to something already CRLF it is the identity, which is
    what lets a fixture call it on both a cell and its entry.
    """
    data = path.read_bytes()
    path.write_bytes(data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))


def test_a_generated_roster_verifies_clean(tmp_path):
    """The lawful polarity, which matters as much as the others: a guard that
    reds a tree nobody can fix is a guard somebody deletes."""
    make_cell(tmp_path, "alpha")
    make_cell(tmp_path, "beta")
    roster.write(tmp_path)
    assert roster.verify(tmp_path) == []


def test_a_missing_entry_fires_once_per_runtime(tmp_path):
    """The defect itself: a cell whose description loads in no session here.

    One finding per surface, and each names its own runtime. Collapsing them
    would tell a session that repaired one directory that it was done, which
    is #199's defect with the runtimes swapped. [#258]
    """
    make_cell(tmp_path, "alpha")
    findings = roster.verify(tmp_path)
    assert len(findings) == len(roster.SURFACES)
    for surface, finding in zip(roster.SURFACES, findings):
        assert f"{surface.directory}/alpha/SKILL.md is missing" in finding
        assert surface.runtime in finding
        assert "tools/roster.py --write" in finding


def test_an_entry_out_of_step_fires(tmp_path):
    """The one this guard is really for. An edited description is the whole
    triggering surface changing, and the entry keeps serving the old trigger
    to every session until somebody regenerates."""
    make_cell(tmp_path, "alpha", "The first description.")
    roster.write(tmp_path)
    make_cell(tmp_path, "alpha", "A different description entirely.")
    findings = roster.verify(tmp_path)
    assert len(findings) == len(roster.SURFACES)
    assert all("out of step" in finding for finding in findings)
    roster.write(tmp_path)
    assert roster.verify(tmp_path) == []


def test_an_entry_rewritten_to_crlf_is_still_in_step(tmp_path):
    """The condition [D-186] rules is expected here, which this guard was the
    one place calling a defect.

    A Claude Code worktree arrived with every `.claude/skills/` entry rewritten
    in text mode, and `python tools/lint.py` reported every cell out of step
    against a tree git considered clean -- before the session had changed
    anything. Reading the working copy as bytes is what did that; nothing the
    guard claims needs it, because `.gitattributes` pins the index to LF and a
    drift that is only line endings cannot reach a commit. [#229]
    """
    make_cell(tmp_path, "alpha")
    roster.write(tmp_path)
    entry = entry_of(tmp_path, CLAUDE, "alpha")
    entry.write_bytes(entry.read_bytes().replace(b"\n", b"\r\n"))
    assert b"\r\n" in entry.read_bytes()
    assert roster.verify(tmp_path) == []


def test_crlf_does_not_hide_a_real_drift(tmp_path):
    """The other polarity, and the one that would make the fix a deletion.

    A guard that stopped reporting because it stopped comparing would pass this
    too. The entry here carries CRLF *and* a description its cell no longer
    has, which is the whole triggering surface out of date."""
    make_cell(tmp_path, "alpha", "The first description.")
    roster.write(tmp_path)
    entry = entry_of(tmp_path, CLAUDE, "alpha")
    entry.write_bytes(entry.read_bytes().replace(b"\n", b"\r\n"))
    make_cell(tmp_path, "alpha", "A different description entirely.")
    findings = roster.verify(tmp_path)
    assert len(findings) == len(roster.SURFACES), findings
    assert all("out of step" in finding for finding in findings)
    assert any(CLAUDE.directory in finding for finding in findings), (
        "the CRLF entry is the one this pins, and it must still report"
    )


def test_write_still_restores_the_canonical_bytes(tmp_path):
    """`verify` tolerates the rewrite; `--write` repairs it.

    Two questions, two answers -- and this pins the second, because a `write()`
    that had followed `verify` into normalizing would leave a CRLF entry on
    disk with nothing left in the repository able to say so."""
    make_cell(tmp_path, "alpha")
    roster.write(tmp_path)
    entry = entry_of(tmp_path, CLAUDE, "alpha")
    canonical = entry.read_bytes()
    entry.write_bytes(canonical.replace(b"\n", b"\r\n"))
    changed = roster.write(tmp_path)
    assert entry.read_bytes() == canonical
    assert any("wrote" in line for line in changed), changed


def test_a_stray_carriage_return_is_not_forgiven(tmp_path):
    """The bound on the tolerance, in the direction it could have been written
    too wide -- with a fixture chosen so that it discriminates.

    `\\r\\n` is what a Windows text-mode write produces and what was observed. A
    carriage return standing on its own is not a line ending anything here
    emits, so an entry carrying one is corrupt rather than copied. The entry
    below is the realistic composite -- the copy a worktree produces, plus one
    stray byte -- because that is what tells the two candidate predicates
    apart: a `\\r\\n` normalisation still reports it, and the wider
    "strip every carriage return" forgives it.

    This fixture was added when the all-CR one below was found not to
    discriminate against strip-every-carriage-return. **Both are needed and
    neither replaces the other**: the sibling below kills the mutant this one
    cannot. What that episode established is the method -- running the
    mutation, rather than reading the test, is the only way a
    non-discriminating fixture shows up at all.
    """
    make_cell(tmp_path, "alpha")
    roster.write(tmp_path)
    entry = entry_of(tmp_path, CLAUDE, "alpha")
    crlf(entry)
    entry.write_bytes(entry.read_bytes().replace(b"# alpha", b"\r# alpha"))
    findings = roster.verify(tmp_path)
    assert len(findings) == 1
    assert "out of step" in findings[0]


def test_an_all_carriage_return_entry_is_not_forgiven_either(tmp_path):
    """The other half of the pair, and neither half pins the bound alone.

    This entry's line feeds are *replaced* by carriage returns rather than
    paired with them. A `\\r\\n` normalisation leaves it wholly unlike its cell
    and reports it; the wider "treat a lone `\\r` as a line ending" folds it
    back to the cell and goes silent. So this fixture kills that mutant and
    `test_a_stray_carriage_return_is_not_forgiven` does not -- while that one
    kills "strip every carriage return" and this one does not.

    **This fixture was here, was replaced by the stray-byte one, and had to
    come back.** The replacement was made because the original did not
    discriminate against strip-every-`\\r`; nobody checked what it *had* been
    discriminating against, so the bound `matches()` states went unpinned while
    a mutation matrix in the commit message read as full coverage. The hazard
    is live rather than theoretical: `tools/figures.py` already normalises a
    lone `\\r` to a newline, so a session harmonising the two writes exactly
    this mutant and gets a green suite. [#224 review, M9]
    """
    make_cell(tmp_path, "alpha")
    roster.write(tmp_path)
    entry = entry_of(tmp_path, CLAUDE, "alpha")
    entry.write_bytes(entry.read_bytes().replace(b"\n", b"\r"))
    findings = roster.verify(tmp_path)
    assert len(findings) == 1
    assert "out of step" in findings[0]


def test_a_cell_that_is_itself_crlf_still_matches_its_entry(tmp_path):
    """Why both sides are normalised, and not the entry on disk alone.

    Normalising the entry side alone makes an unclearable red possible: the
    entry normalises, `want` does not, `--write` writes `want`, and the
    re-verify fails again, which is #224's defect rebuilt one layer down.
    Reaching it takes a CRLF cell, because no assertion about an LF cell can
    tell the two predicates apart -- the entry-side-only mutation survives
    every other test in this file.

    It pins `verify()` only. `write()` compares bytes on purpose, so `--write`
    still rewrites a CRLF entry to LF -- [#232]'s decision, taken with its own
    review, and this branch deferred to it rather than re-litigating a landed
    call on the same mechanism.

    **It pins one composition of two.** Here the cell is CRLF *before* the
    entry is generated, so both sides descend from the same bytes. The other
    composition -- a cell that goes CRLF *after* its entry was written -- is
    pinned by `test_a_crlf_cell_no_longer_reds_a_tree_that_linux_agrees_with`
    below, and it matches too. It did not until [#234] was fixed: the slice
    took one byte after the terminator, which on a CRLF source is the carriage
    return rather than the newline, so the copied block lost a blank line that
    no later normalisation could restore. This paragraph described that as
    live for one commit after it was repaired, which is how one file came to
    state two contradictory things about one function. [PR #247 review, M9]
    """
    make_cell(tmp_path, "alpha")
    crlf(tmp_path / "skills" / "alpha" / "SKILL.md")
    roster.write(tmp_path)
    entry = entry_of(tmp_path, CLAUDE, "alpha")
    crlf(entry)
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
    assert len(findings) == len(roster.SURFACES)
    assert all("names no cell" in finding for finding in findings)
    roster.write(tmp_path)
    assert roster.verify(tmp_path) == []
    for surface in roster.SURFACES:
        assert not (tmp_path / surface.directory / "beta").exists()


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
    helper = tmp_path / CLAUDE.directory / "repo-helper"
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
    entry = entry_of(tmp_path, CLAUDE, "spikes")
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
    for surface in roster.SURFACES:
        assert not (tmp_path / surface.directory / "beta").exists()
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
    entry = tmp_path / CLAUDE.directory / "beta"
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
    entry_of(tmp_path, CLAUDE, "alpha").unlink()
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
    orphan = tmp_path / CLAUDE.directory / "gone"
    orphan.mkdir(parents=True)
    (orphan / "SKILL.md").write_bytes(roster.expected(tmp_path, "alpha", CLAUDE))

    lines = roster.write(tmp_path)

    assert any("skipped" in line and "mm-broken" in line for line in lines)
    for surface in roster.SURFACES:
        for name in ("alpha", "zeta"):
            entry = entry_of(tmp_path, surface, name).read_bytes()
            assert b"Edited after generation" in entry, (
                f"{name} was not regenerated on {surface.directory}")
    assert not orphan.exists(), "the removal loop was never reached"
    remaining = roster.verify(tmp_path)
    assert len(remaining) == 1 and "no parseable frontmatter" in remaining[0], (
        "a cell nothing can copy is one defect in one file, not one per "
        "surface owed a copy"
    )


def test_every_shape_the_docstring_names_behaves_as_it_says(tmp_path):
    """The docstring names each shape and what its message names. This walks
    that list and asserts against the **whole** message.

    An earlier version of this test asserted `"--write" not in
    finding.split(" -- ")[0]`, which cuts the string before the remedy clause
    -- the only place a command ever appears. So it passed over a message that
    did name `--write`, while its own docstring claimed the opposite: a guard
    that could not fail on the thing it was named for. That masking is why the
    stated count survived two corrections. [PR #210 cycle two, C2-F1]
    """
    # Silent: a foreign entry at a name that is no cell -- on every surface,
    # each being its own runtime's documented place for a project skill.
    make_cell(tmp_path, "alpha")
    roster.write(tmp_path)
    for surface in roster.SURFACES:
        foreign = tmp_path / surface.directory / "mine"
        foreign.mkdir(parents=True)
        (foreign / "SKILL.md").write_bytes(
            b"---\nname: mine\ndescription: d\n---\n\nx\n")
    assert roster.verify(tmp_path) == []
    for surface in roster.SURFACES:
        foreign = tmp_path / surface.directory / "mine"
        (foreign / "SKILL.md").unlink()
        foreign.rmdir()

    # Names --write: missing, out of step, generated orphan.
    entry_of(tmp_path, CLAUDE, "alpha").unlink()
    assert all("--write" in f for f in roster.verify(tmp_path))
    roster.write(tmp_path)
    make_cell(tmp_path, "alpha", "Moved on since generation.")
    assert all("--write" in f for f in roster.verify(tmp_path))
    roster.write(tmp_path)
    orphan = tmp_path / CLAUDE.directory / "gone"
    orphan.mkdir(parents=True)
    (orphan / "SKILL.md").write_bytes(roster.expected(tmp_path, "alpha", CLAUDE))
    assert all("--write" in f for f in roster.verify(tmp_path))
    roster.write(tmp_path)

    # Collision: names the move first and --write second, both over the whole
    # message. Asserted against the full string, not a prefix of it.
    entry = entry_of(tmp_path, CLAUDE, "alpha")
    entry.write_bytes(b"---\nname: alpha\ndescription: mine\n---\n\nhand-written\n")
    collision = roster.verify(tmp_path)
    assert len(collision) == 1
    assert "move your file out" in collision[0]
    assert "--write" in collision[0], (
        "the collision message names the move and then --write; the docstring "
        "says so, and this asserts the whole message rather than a prefix"
    )
    assert collision[0].index("move your file out") < collision[0].index("--write")
    entry.unlink()
    roster.write(tmp_path)
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_bytes(b"# no frontmatter\n")
    unparseable = [f for f in roster.verify(tmp_path) if "parseable" in f]
    assert len(unparseable) == 1 and "--write" not in unparseable[0]
    assert "fix the cell's frontmatter" in unparseable[0]


def test_the_docstring_states_no_count_of_shapes(tmp_path):
    """The arithmetic is gone rather than corrected again.

    Three successive versions of `verify`'s docstring stated a count of its
    finding shapes and all three were wrong, each in the sentence written to
    correct the one before. This asserts the class cannot recur: no count of
    shapes is stated, so none can be false.
    """
    doc = roster.verify.__doc__
    for word in ("Two shapes", "Three name", "Five shapes", "Four name",
                 "Six shapes", "two name", "three name"):
        assert word not in doc, f"verify()'s docstring counts its shapes again: {word!r}"


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
    entry = entry_of(tmp_path, CLAUDE, "alpha").read_bytes()
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
    text = entry_of(tmp_path, CLAUDE, "alpha").read_text(encoding="utf-8")
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
    for surface in roster.SURFACES:
        with pytest.raises(ValueError):
            roster.expected(tmp_path, "alpha", surface)


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
    cells = roster.cell_names(ROOT)
    assert cells != []
    for surface in roster.SURFACES:
        assert set(cells) <= set(roster.roster_names(ROOT, surface)), (
            f"a cell has no entry under {surface.directory}, so its "
            f"description loads in no {surface.runtime} session here"
        )
    assert roster.verify(ROOT) == []


def test_a_linked_entry_directory_is_refused_rather_than_written_through(tmp_path):
    """`write()` creates directories and files, so a link mid-path sends both
    outside the repository. Reproduced before the guard existed: the bytes
    landed at the link's target.

    The check is resolved-path containment, not `is_symlink()`. On Windows the
    reachable form is a junction -- `mklink /J` needs no privilege where
    `mklink /D` is refused without it -- and `Path.is_symlink()` returns False
    for one, so the obvious predicate passes exactly the easiest case. Raised
    by the external reviewer against `is_symlink`; the containment check is
    what survives contact with this platform.

    Skipped where the platform will not make a link at all, which is its own
    honest answer rather than a silent pass.
    """
    import os
    import subprocess

    make_cell(tmp_path, "alpha")
    outside = tmp_path / "outside"
    outside.mkdir()
    entry = tmp_path / CLAUDE.directory / "alpha"
    entry.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(outside, entry, target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError):
        # Windows refuses an unprivileged symlink but grants a junction, which
        # is why the junction is the reachable form here and why the guard
        # cannot be `is_symlink()`. Falling back rather than skipping keeps
        # this pin live on the platform the repository actually runs on.
        if os.name != "nt":
            pytest.skip("this platform will not create a directory link")
        made = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(entry), str(outside)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
        )
        if made.returncode != 0:
            pytest.skip(f"no directory link available: {made.stdout}{made.stderr}")

    assert not roster.inside_roster(tmp_path, entry, CLAUDE)
    findings = [f for f in roster.verify(tmp_path) if "resolves outside" in f]
    assert len(findings) == 1, (
        "the link is on one surface, so it is one finding -- the other "
        "surface reports its own missing entry, not this"
    )
    assert "--write" not in findings[0]

    lines = roster.write(tmp_path)
    assert any("resolves outside" in line for line in lines)
    assert not (outside / "SKILL.md").exists(), (
        "write() followed the link and created a file outside the repository"
    )


def test_the_ordinary_entry_directory_is_not_refused(tmp_path):
    """The lawful polarity: containment must not reject the normal case, which
    is every entry on every tree this guard actually runs against."""
    make_cell(tmp_path, "alpha")
    roster.write(tmp_path)
    for surface in roster.SURFACES:
        entry = tmp_path / surface.directory / "alpha"
        assert roster.inside_roster(tmp_path, entry, surface)
        assert roster.inside_roster(
            ROOT, ROOT / surface.directory / "filing", surface)
    assert roster.verify(tmp_path) == []


def test_a_crlf_cell_keeps_the_newline_the_slice_used_to_drop(tmp_path):
    """The defect, at the function.

    `frontmatter()` took the block, its terminator and one byte. On a CRLF
    source that byte is the carriage return inside the pair, so the newline
    was dropped and `expected()` produced an entry with no blank line between
    the terminator and the heading. [#234]
    """
    path = make_cell(tmp_path, "alpha")
    lf_block = roster.frontmatter(path.read_bytes())
    assert lf_block.endswith(b"---" + NL.encode())

    crlf(path)
    crlf_block = roster.frontmatter(path.read_bytes())
    assert crlf_block.endswith(b"---" + b"\r" + NL.encode()), (
        "the line ending is taken whole, not one byte of it"
    )
    assert crlf_block.replace(b"\r\n", b"\n") == lf_block, (
        "line endings aside, a CRLF cell yields the block an LF cell yields"
    )


def test_the_lf_slice_is_byte_identical_to_what_it_always_was(tmp_path):
    """The other polarity, and the boundary this change stated: every cell git
    checks out is LF, and the repair must not move that path by a byte.
    """
    path = make_cell(tmp_path, "alpha")
    data = path.read_bytes()
    end = data.find(b"\n---", 3)
    assert roster.frontmatter(data) == data[:end + len(b"\n---") + 1]


def test_a_source_ending_at_its_terminator_still_has_no_newline_to_take(tmp_path):
    """The part of the old documented bound that survives. There is nothing
    after the terminator, so nothing is taken -- and the function must not
    invent one, which would make it emit what no source held.
    """
    path = make_cell(tmp_path, "alpha")
    path.write_bytes(b"---" + NL.encode() + b"name: alpha" + NL.encode() + b"---")
    assert roster.frontmatter(path.read_bytes()) == (
        b"---" + NL.encode() + b"name: alpha" + NL.encode() + b"---"
    )


def test_a_crlf_cell_no_longer_reds_a_tree_that_linux_agrees_with(tmp_path):
    """Composition C end to end -- the cell rewritten CRLF *after* its entry
    was generated, which is the shape that reached a commit.

    Before: `verify` reported, `--write` converged to green locally, and the
    entry it wrote differed in content from what an LF checkout produces, so
    CI went red on a change with no diff its author could read. [#234]
    """
    cell = make_cell(tmp_path, "alpha")
    roster.write(tmp_path)
    entry = entry_of(tmp_path, CLAUDE, "alpha")
    before = entry.read_bytes()

    crlf(cell)
    assert roster.verify(tmp_path) == [], "a cell's line endings are not drift"
    roster.write(tmp_path)
    assert roster.verify(tmp_path) == []
    assert entry.read_bytes().replace(b"\r\n", b"\n") == before.replace(b"\r\n", b"\n"), (
        "the tree the remedy leaves must be the tree a Linux checkout reads"
    )


def test_a_crlf_cell_with_genuine_drift_still_reports(tmp_path):
    """The polarity the fix above must not buy: an edited description on a
    CRLF cell is still drift, and still reported.
    """
    cell = make_cell(tmp_path, "alpha")
    roster.write(tmp_path)
    cell.write_bytes(
        cell.read_bytes().replace(b"A fixture cell.", b"A different trigger.")
    )
    crlf(cell)
    assert len(roster.verify(tmp_path)) == len(roster.SURFACES)


def test_every_surface_gets_an_entry_and_one_short_still_reports(tmp_path):
    """The defect #258 found, at the shape it would come back in.

    A generator that wrote the first surface and stopped is exactly the state
    this repository was in before #258: one runtime holding every description,
    the other holding none, and nothing saying so. (A draft of this docstring
    put a duration on that state and the duration was wrong by twenty-five
    times; the shape is what this pins, and `tools/lint.py` carries the
    derivation. [PR #278 review, M5]) So the pin is
    not that `write()` produces entries -- it is that a tree with one surface
    complete and the other empty is a **finding**, one per cell that is short.
    """
    make_cell(tmp_path, "alpha")
    make_cell(tmp_path, "beta")
    roster.write(tmp_path)
    for surface in roster.SURFACES:
        for name in ("alpha", "beta"):
            assert entry_of(tmp_path, surface, name).is_file(), (
                f"{name} has no entry under {surface.directory}")

    for name in ("alpha", "beta"):
        entry_of(tmp_path, CODEX, name).unlink()
    findings = roster.verify(tmp_path)
    assert len(findings) == 2, findings
    assert all(CODEX.directory in finding and CODEX.runtime in finding
               for finding in findings)
    assert not any(CLAUDE.directory in finding for finding in findings), (
        "the surface that is complete must not report"
    )


def test_the_surfaces_share_a_frontmatter_and_name_their_own_runtimes(tmp_path):
    """What loads is one cell's block; what explains the file is per runtime.

    The frontmatter must be identical because it is the triggering surface and
    two wordings of one trigger fire on different things. The body must not be,
    because a session opening the copy it is not served by needs to learn that
    from the file rather than conclude it is a stray duplicate.
    """
    source = make_cell(tmp_path, "alpha", "Use when the fixture is exercised.")
    roster.write(tmp_path)
    block = roster.frontmatter(source.read_bytes())
    bodies = {}
    for surface in roster.SURFACES:
        data = entry_of(tmp_path, surface, "alpha").read_bytes()
        assert data.startswith(block), (
            f"{surface.directory} does not carry the cell's frontmatter")
        bodies[surface.runtime] = data[len(block):]
        assert surface.runtime.encode("utf-8") in data
    assert len(set(bodies.values())) == len(roster.SURFACES), (
        "the copies name no runtime, or all name the same one"
    )


def test_ownership_holds_on_every_surface_not_just_the_first(tmp_path):
    """The regeneration branch's own recorded failure, one axis further out.

    Checking ownership on one path is what let hand-written content go on
    being destroyed after the removal branch stopped [PR #210 cycle one,
    C1-F2/C1-F3]. A second surface is a second set of those paths, and a loop
    that checked the marker on the first directory only would report `wrote`
    and take the file with it.
    """
    make_cell(tmp_path, "spikes")
    roster.write(tmp_path)
    mine = b"---\nname: spikes\ndescription: Mine, by hand.\n---\n\nKeep me.\n"
    entry_of(tmp_path, CODEX, "spikes").write_bytes(mine)

    findings = roster.verify(tmp_path)
    assert len(findings) == 1
    assert CODEX.directory in findings[0]
    assert "was not written by tools/roster.py" in findings[0]

    roster.write(tmp_path)
    assert entry_of(tmp_path, CODEX, "spikes").read_bytes() == mine, (
        "write() overwrote a hand-written file on the second surface"
    )


def test_write_reports_an_unparseable_cell_once_not_once_per_surface(tmp_path):
    """The rule `verify` states, held on the command a reader actually runs.

    `verify` dedups this line with the reason beside it -- a second copy of an
    unrepairable line asks a reader to fix the same file twice -- and the
    identical `try`/`except` in `write()` had no dedup, so `--write` said it
    twice and a reader could believe two cells were broken. [PR #278 review,
    M8]
    """
    make_cell(tmp_path, "alpha")
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_bytes(
        b"# no frontmatter" + NL.encode() )

    skipped = [line for line in roster.write(tmp_path) if "skipped" in line]
    assert len(skipped) == 1, skipped
    assert "alpha" in skipped[0]

    remaining = [f for f in roster.verify(tmp_path) if "parseable" in f]
    assert len(remaining) == 1, (
        "the guard and the command must report this cell the same number of "
        "times, which is once"
    )


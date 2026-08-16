"""Tests for the packaging lint. Each fixture builds a minimal tree in
tmp_path so every check is proven to fire and to stay quiet, per check.
The evasion-form cases exist because the 2026-08-15 adversarial review
showed the original regexes missed every relative, uppercase, and
backslash form (findings M1/M2/M4/M5/M6 in docs/ledger.jsonl)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lint


def make_clean_tree(root: Path) -> None:
    (root / "AGENTS.md").write_text("# root\nDoctrine pointer lives beside this file.\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    skill = root / "skills" / "example-skill"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "# example-skill\nDepth lives in references/detail.md within skills/example-skill/.\n",
        encoding="utf-8",
    )


def test_clean_tree_passes(tmp_path):
    make_clean_tree(tmp_path)
    assert lint.run(tmp_path) == []


# --- zone wall -------------------------------------------------------------

def test_zone_wall_fires_on_rooted_reference(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    (skill / "SKILL.md").write_text("See docs/architecture/adr/README.md for rules.\n", encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "zone-wall" in findings[0]


def test_zone_wall_fires_on_relative_parent_reference(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    (skill / "SKILL.md").write_text(
        "[the constitution](../../docs/architecture/adr/README.md)\n", encoding="utf-8"
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "zone-wall" in findings[0]


def test_zone_wall_fires_on_uppercase_and_backslash_but_not_own_subdir(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    (skill / "SKILL.md").write_text(
        # ./tools/ inside a skill resolves to the skill's OWN tools/ subdir —
        # self-contained and lawful; the other two are repo-only references.
        "Run ./tools/helper.py first.\nOr see Docs/architecture.\nOr docs\\architecture\\adr.\n",
        encoding="utf-8",
    )
    findings = [f for f in lint.run(tmp_path) if "zone-wall" in f]
    assert len(findings) == 2


def test_zone_wall_ignores_web_urls_and_longer_paths(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    (skill / "SKILL.md").write_text(
        "See https://example.com/docs/guide and https://github.com/o/r/blob/main/docs/x.md\n"
        "The upstream-docs/ convention and their-repo/docs/ layout are fine.\n",
        encoding="utf-8",
    )
    assert lint.run(tmp_path) == []


def test_zone_wall_scans_files_regardless_of_extension(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    (skill / "helper.sh").write_text("cat docs/architecture/adr/README.md\n", encoding="utf-8")
    (skill / "Makefile").write_text("lint:\n\tpython tools/lint.py\n", encoding="utf-8")
    findings = [f for f in lint.run(tmp_path) if "zone-wall" in f]
    assert len(findings) == 2


def test_binary_files_are_skipped(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    (skill / "blob.bin").write_bytes(b"\x00\x01docs/architecture\x00")
    assert lint.run(tmp_path) == []


def test_zone_wall_ignores_repo_only_zone_itself(tmp_path):
    make_clean_tree(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text("Repo docs may reference tools/lint.py freely.\n", encoding="utf-8")
    assert lint.run(tmp_path) == []


# --- sideways deps ---------------------------------------------------------

def test_sideways_dep_fires_and_self_reference_does_not(tmp_path):
    make_clean_tree(tmp_path)
    other = tmp_path / "skills" / "other-skill"
    other.mkdir(parents=True)
    (other / "SKILL.md").write_text("Compose with skills/example-skill/ for setup.\n", encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1
    assert "sideways-dep" in findings[0] and "example-skill" in findings[0]


def test_sideways_dep_fires_on_relative_form(tmp_path):
    make_clean_tree(tmp_path)
    other = tmp_path / "skills" / "other-skill"
    other.mkdir(parents=True)
    (other / "SKILL.md").write_text("Load ../example-skill/SKILL.md first.\n", encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "sideways-dep" in findings[0]


def test_relative_reference_within_own_skill_is_clean(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    (skill / "references" / "detail.md").write_text(
        "Back to ../SKILL.md, and the helper at ../scripts/run.py.\n", encoding="utf-8"
    )
    assert lint.run(tmp_path) == []


def test_lib_may_not_reference_a_skill(tmp_path):
    make_clean_tree(tmp_path)
    libdir = tmp_path / "lib"
    libdir.mkdir()
    (libdir / "core.py").write_text("# see skills/example-skill/SKILL.md\n", encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "sideways-dep" in findings[0] and "from lib/" in findings[0]


# --- doctrine --------------------------------------------------------------

def test_doctrine_budget_fires_when_agents_md_bloats(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "AGENTS.md").write_text("x" * (lint.AGENTS_BUDGET_CHARS + 1), encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "doctrine-budget" in findings[0]


def test_missing_agents_md_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "AGENTS.md").unlink()
    assert any("AGENTS.md is missing" in f for f in lint.run(tmp_path))


def test_missing_claude_md_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "CLAUDE.md").unlink()
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "CLAUDE.md is missing" in findings[0]


def test_backticked_import_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("`@AGENTS.md`\n", encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "doctrine-pointer" in findings[0]


def test_fork_that_name_drops_agents_md_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "CLAUDE.md").write_text(
        "Local rules that contradict the root file. (This repo also has an AGENTS.md.)\n",
        encoding="utf-8",
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "doctrine-pointer" in findings[0]


# --- ledger ----------------------------------------------------------------

def test_ledger_row_missing_field_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "ledger.jsonl").write_text(
        '{"id": "X1", "date": "2026-08-15", "artifact": "lint", "severity": "high"}\n',
        encoding="utf-8",
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "ledger" in findings[0] and "missing field" in findings[0]


def _ledger_row(**overrides: str) -> dict:
    row = {
        "id": "X1", "date": "2026-08-15", "artifact": "lint", "severity": "low",
        "introduced": "design", "catchable": "design",
        "caught": "adversarial-review", "source": "review-2026-08-15",
        "disposition": "fixed", "found_by": "defense",
        "ref": "https://github.com/example/repo/pull/1",
    }
    row.update(overrides)
    return row


def _write_ledger(root: Path, row: dict) -> None:
    make_clean_tree(root)
    docs = root / "docs"
    docs.mkdir()
    (docs / "ledger.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_valid_ledger_row_is_clean(tmp_path):
    _write_ledger(tmp_path, _ledger_row())
    assert lint.run(tmp_path) == []


def test_ledger_row_without_found_by_is_a_finding(tmp_path):
    row = _ledger_row()
    del row["found_by"]
    _write_ledger(tmp_path, row)
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "found_by" in findings[0]


def test_ledger_row_empty_found_by_is_a_finding(tmp_path):
    _write_ledger(tmp_path, _ledger_row(found_by="   "))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "found_by" in findings[0]


def test_ledger_row_bad_severity_is_a_finding_even_with_missing_fields(tmp_path):
    row = _ledger_row(severity="critical")
    del row["found_by"]
    _write_ledger(tmp_path, row)
    findings = lint.run(tmp_path)
    assert any("missing field" in f for f in findings)
    assert any("severity" in f and "critical" in f for f in findings)


def test_ledger_row_bad_vocab_values_are_findings(tmp_path):
    _write_ledger(
        tmp_path,
        _ledger_row(
            artifact="banana", introduced="lunch", catchable="brunch",
            caught="dinner", disposition="vibes",
        ),
    )
    findings = lint.run(tmp_path)
    assert any("artifact" in f and "banana" in f for f in findings)
    assert any("introduced" in f and "lunch" in f for f in findings)
    assert any("catchable" in f and "brunch" in f for f in findings)
    assert any("caught" in f and "dinner" in f for f in findings)
    assert any("disposition" in f and "vibes" in f for f in findings)


def test_ledger_vocabularies_are_exactly_what_the_adr_states():
    """Every value ADR-006 §5 enumerates, pinned. Without this, 7 of the 11
    original values could be deleted from the lint with the suite green and the
    live lint clean — the guard covering only the values the fixtures happen to
    use. Nothing checks these against the ADR's prose (§5 names that as a
    stated-unenforced property), so this is the one place a deletion is caught."""
    assert lint.LEDGER_POSITIONS == {
        "framing", "design", "plan", "implementation", "unrecorded",
    }
    assert lint.LEDGER_STAGES == {
        "authoring-review", "adversarial-review", "post-fix", "external",
        "ci", "post-merge", "consumer", "unrecorded",
    }


def test_ledger_position_fields_reject_stage_values(tmp_path):
    """The two axes are separate vocabularies. Goes red the moment they are
    merged back into one set — the state in which every row held a single value
    per field and ADR-006 §5's own retirement test could not fail."""
    _write_ledger(
        tmp_path,
        _ledger_row(introduced="adversarial-review", catchable="post-merge"),
    )
    findings = lint.run(tmp_path)
    assert any("introduced" in f and "adversarial-review" in f for f in findings)
    assert any("catchable" in f and "post-merge" in f for f in findings)


def test_ledger_caught_accepts_post_fix_stage(tmp_path):
    """`post-fix` discriminates where `design` cannot. The pre-split vocabulary
    rejected it everywhere; the split makes it lawful for `caught`, so this goes
    red against the merged set — which `caught="design"` never did, design being
    rejected before the split too. A pin that cannot fail on the old code pins
    nothing (SKILL.md § evidence standards: red against the pre-fix revision)."""
    _write_ledger(tmp_path, _ledger_row(caught="post-fix"))
    assert lint.run(tmp_path) == []


def test_ledger_caught_rejects_a_position_value(tmp_path):
    """The reverse boundary, which nothing else covers.

    The other pins show positions rejecting a stage and `caught` accepting one.
    None of them shows `caught` *rejecting* a position — so a validator that
    accepted the union of both sets would pass the whole suite. That hole was
    opened by this branch: the test that used to cover it was deleted for not
    discriminating against the pre-split lint, and its coverage was not
    replaced. Found by an external reviewer on PR #6, sustained on that ground.

    Like its sibling below, this is a forward pin, not a discriminating one:
    `implementation` was absent from the pre-split vocabulary too."""
    _write_ledger(tmp_path, _ledger_row(caught="implementation"))
    findings = lint.run(tmp_path)
    assert any("caught" in f and "implementation" in f for f in findings)


def test_ledger_position_rejects_post_fix_stage(tmp_path):
    """The asymmetry's other half: lawful for the stage field, unlawful for a
    position.

    Honest about what this one is: it does **not** go red against the pre-split
    lint, because that vocabulary rejected `post-fix` in every field. It is a
    forward pin — it fires if `post-fix` is ever added to the positions — not a
    discriminating one, and saying so is the point. Its sibling above carries
    the discriminating half. Claiming otherwise is the defect this fix batch was
    correcting, and it would have been reproduced here by silence."""
    _write_ledger(tmp_path, _ledger_row(introduced="post-fix"))
    findings = lint.run(tmp_path)
    assert any("introduced" in f and "post-fix" in f for f in findings)


def test_ledger_retired_authoring_value_is_rejected_in_both_axes(tmp_path):
    """ADR-006 §5: "No value doubles as a judgment and a default." `authoring`
    is gone from both vocabularies because it was doing exactly that — though
    that reading of its history is this repo's own account of the value, not
    something §5 states, so the citation covers the rule and not the diagnosis."""
    _write_ledger(tmp_path, _ledger_row(introduced="authoring", caught="authoring"))
    findings = lint.run(tmp_path)
    assert any("introduced" in f and "authoring" in f for f in findings)
    assert any("caught" in f and "authoring" in f for f in findings)


def test_ledger_unjudged_position_is_lawful(tmp_path):
    """A row that never judged its position says so, rather than asserting the
    last position by default."""
    _write_ledger(tmp_path, _ledger_row(introduced="unrecorded", catchable="unrecorded"))
    assert lint.run(tmp_path) == []


def test_ledger_judged_implementation_position_is_lawful(tmp_path):
    _write_ledger(tmp_path, _ledger_row(introduced="implementation", catchable="implementation"))
    assert lint.run(tmp_path) == []


def test_ledger_unjudged_and_implementation_are_separate_values():
    """No value doubles as a judgment and a default. Goes red if the not-judged
    value is ever collapsed onto a real position. (An earlier version of this
    test also asserted `"unrecorded" != "implementation"` — two string literals,
    constant-true under every state of the code, and inert as a pin.)"""
    assert {"unrecorded", "implementation"} <= lint.LEDGER_POSITIONS


def test_ledger_row_unhashable_vocab_value_is_a_finding_not_a_crash(tmp_path):
    _write_ledger(tmp_path, _ledger_row(artifact=[], caught={"phase": "ci"}))
    findings = lint.run(tmp_path)
    assert any("artifact" in f for f in findings)
    assert any("caught" in f for f in findings)


def test_ledger_unhashable_id_is_a_finding_not_a_crash(tmp_path):
    """A prior fix guarded vocab values but not the (source, id) key, so a
    list-valued id crashed the whole lint and suppressed every other finding.
    https://github.com/Grimblaz-and-Friends/tradecraft/pull/2"""
    make_clean_tree(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    bad_vocab = json.dumps(_ledger_row(id="A", severity="BOGUS"))
    unhashable = json.dumps(_ledger_row(id=["x", "y"]))
    (docs / "ledger.jsonl").write_text(
        bad_vocab + "\n" + unhashable + "\n", encoding="utf-8"
    )
    findings = lint.run(tmp_path)
    assert any("severity" in f and "BOGUS" in f for f in findings)
    assert any("id" in f and "must be a string" in f for f in findings)


def test_ledger_int_and_string_id_do_not_evade_uniqueness(tmp_path):
    _write_ledger(tmp_path, _ledger_row(id=7))
    findings = lint.run(tmp_path)
    assert any("id" in f and "must be a string" in f for f in findings)


def test_ledger_found_by_must_be_a_lowercase_token(tmp_path):
    for n, bad in enumerate(("Cold-Read", "wiring falsifier", "   ")):
        target = tmp_path / f"case{n}"
        target.mkdir()
        _write_ledger(target, _ledger_row(found_by=bad))
        assert any("found_by" in f for f in lint.run(target)), bad


def test_ledger_malformed_row_keeps_partials_and_never_silences_later_rows(tmp_path):
    """Pins the exception boundary itself: a row that raises mid-check must keep
    the findings already gathered for it and must not suppress the rows after it.
    Deleting the boundary turns this red instead of leaving the suite green."""
    make_clean_tree(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "ledger.jsonl").write_text(
        '["not", "a", "row"]\n' + json.dumps(_ledger_row(artifact="banana")) + "\n",
        encoding="utf-8",
    )
    findings = lint.run(tmp_path)
    assert any("could not be fully validated" in f for f in findings)
    assert any("missing field" in f for f in findings)
    assert any("banana" in f for f in findings)


def test_ledger_ref_must_be_a_url(tmp_path):
    for n, bad in enumerate(("", "see PR 3", "F2", 7)):
        target = tmp_path / f"case{n}"
        target.mkdir()
        _write_ledger(target, _ledger_row(ref=bad))
        assert any("ref" in f for f in lint.run(target)), bad


def test_ledger_date_must_be_iso(tmp_path):
    # 2026-02-30 and 2026-13-45 are shape-valid and calendar-invalid: they reach
    # the calendar parse, which nothing else in this list exercises.
    for n, bad in enumerate(
        ("2026-8-15", "not-a-date", 20260815, "2026-02-30", "2026-13-45")
    ):
        target = tmp_path / f"case{n}"
        target.mkdir()
        _write_ledger(target, _ledger_row(date=bad))
        assert any("date" in f for f in lint.run(target)), bad


def test_ledger_duplicate_source_id_pair_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    row = json.dumps(_ledger_row())
    (docs / "ledger.jsonl").write_text(row + "\n" + row + "\n", encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "duplicate" in findings[0]


# --- the live repo obeys its own lint --------------------------------------

def test_live_repo_is_clean():
    assert lint.run(lint.ROOT) == []

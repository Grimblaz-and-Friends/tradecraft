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
        "introduced": "authoring", "catchable": "authoring-review",
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
    for n, bad in enumerate(("2026-8-15", "not-a-date", 20260815)):
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

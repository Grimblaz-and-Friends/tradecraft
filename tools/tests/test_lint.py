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


def test_sideways_dep_ignores_web_urls_and_longer_paths(tmp_path):
    # Both polarities of the M12 fix: the lawful external forms stay quiet...
    make_clean_tree(tmp_path)
    other = tmp_path / "skills" / "other-skill"
    other.mkdir(parents=True)
    (other / "SKILL.md").write_text(
        "See https://github.com/anthropics/skills/tree/main/skills/pdf/SKILL.md\n"
        "The upstream-skills/bar/ layout and their-repo/skills/baz/ are fine.\n",
        encoding="utf-8",
    )
    assert lint.run(tmp_path) == []
    # ...and a true sideways reference still fires.
    (other / "SKILL.md").write_text("Load skills/example-skill/ first.\n", encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "sideways-dep" in findings[0]


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


# --- review index ----------------------------------------------------------

def _review_row(**overrides):
    row = {
        "date": "2026-08-19",
        "artifact": "pr-74",
        "lane": "panel",
        "seats": {
            "cold-read": {"raw": 5, "merged": 4, "sustained": 2, "high": 1},
            "operational": {"raw": 3, "merged": 3, "sustained": 0, "high": 0},
        },
        "report": "https://github.com/example/repo/pull/74#issuecomment-1",
    }
    row.update(overrides)
    return row


def _write_index(root: Path, *rows) -> None:
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "reviews.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )


def test_review_index_absent_is_clean(tmp_path):
    make_clean_tree(tmp_path)
    assert lint.run(tmp_path) == []


def test_valid_review_row_is_clean(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _review_row())
    assert lint.run(tmp_path) == []


def test_review_row_missing_field_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    row = _review_row()
    del row["report"]
    _write_index(tmp_path, row)
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "missing field(s) report" in findings[0]


def test_review_row_bad_json_reports_and_later_rows_still_checked(tmp_path):
    make_clean_tree(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    bad_row = json.dumps(_review_row(lane="nonsense"))
    (docs / "reviews.jsonl").write_text(
        "{not json\n" + bad_row + "\n", encoding="utf-8"
    )
    findings = lint.run(tmp_path)
    assert any("not valid JSON" in f for f in findings)
    assert any("lane 'nonsense'" in f for f in findings)


def test_review_row_non_mapping_is_a_finding_not_a_crash(tmp_path):
    make_clean_tree(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "reviews.jsonl").write_text('["a", "b"]\n', encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "not a JSON object" in findings[0]


def test_review_row_date_must_be_a_real_calendar_day(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _review_row(date="2026-02-30"))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "not an ISO YYYY-MM-DD date" in findings[0]


def test_review_row_artifact_must_be_non_empty(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _review_row(artifact="  "))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "artifact" in findings[0]


def test_review_row_lane_vocabulary(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _review_row(lane="routine"))
    assert lint.run(tmp_path) == []
    _write_index(tmp_path, _review_row(lane="wide"))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "lane 'wide'" in findings[0]


def test_review_row_report_must_be_https(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _review_row(report="see the PR"))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "must be an https URL" in findings[0]


def test_review_row_report_rejects_empty_host(tmp_path):
    make_clean_tree(tmp_path)
    for hostless in ("https://", "https:///report"):
        _write_index(tmp_path, _review_row(report=hostless))
        findings = lint.run(tmp_path)
        assert len(findings) == 1 and "must be an https URL" in findings[0]


def test_review_row_seats_must_be_non_empty_mapping(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _review_row(seats={}))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "non-empty mapping" in findings[0]
    _write_index(tmp_path, _review_row(seats=["cold-read"]))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "non-empty mapping" in findings[0]


def test_review_row_seat_names_must_be_lowercase_tokens(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(
        tmp_path,
        _review_row(seats={"Cold-Read": {"raw": 1, "merged": 1, "sustained": 0, "high": 0}}),
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "lowercase token" in findings[0]


def test_review_row_seat_counts_must_be_complete_ints(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(
        tmp_path,
        _review_row(seats={"cold-read": {"raw": 1, "merged": 1, "sustained": 0}}),
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "missing count(s) high" in findings[0]
    _write_index(
        tmp_path,
        _review_row(seats={"cold-read": {"raw": True, "merged": 1, "sustained": 0, "high": 0}}),
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "non-negative integer" in findings[0]
    _write_index(
        tmp_path,
        _review_row(seats={"cold-read": {"raw": -1, "merged": 0, "sustained": 0, "high": 0}}),
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "non-negative integer" in findings[0]


def test_review_row_seat_counts_must_nest(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(
        tmp_path,
        _review_row(seats={"cold-read": {"raw": 1, "merged": 2, "sustained": 0, "high": 0}}),
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "not nested" in findings[0]
    # highs are broken out of sustained, so high > sustained cannot hold either
    _write_index(
        tmp_path,
        _review_row(seats={"cold-read": {"raw": 3, "merged": 3, "sustained": 1, "high": 2}}),
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "not nested" in findings[0]


def test_review_row_seat_counts_wrong_shape_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _review_row(seats={"cold-read": 7}))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "must be a mapping" in findings[0]


def test_frozen_archive_files_are_not_validated(tmp_path):
    # The pre-reset records are history: a malformed line in them is not a
    # lint finding, because nothing appends to them anymore (D-74).
    make_clean_tree(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "ledger.jsonl").write_text("{not json\n", encoding="utf-8")
    (docs / "seat-record.jsonl").write_text("{not json\n", encoding="utf-8")
    assert lint.run(tmp_path) == []

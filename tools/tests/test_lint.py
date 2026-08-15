"""Tests for the packaging lint. Each fixture builds a minimal tree in
tmp_path so every check is proven to fire and to stay quiet, per check."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lint


def make_clean_tree(root: Path) -> None:
    (root / "AGENTS.md").write_text("# root\nCLAUDE.md points at AGENTS.md.\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    skill = root / "skills" / "example-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "# example-skill\nDepth lives in references/detail.md within skills/example-skill/.\n",
        encoding="utf-8",
    )


def test_clean_tree_passes(tmp_path):
    make_clean_tree(tmp_path)
    assert lint.run(tmp_path) == []


def test_zone_wall_fires_on_shipped_reference_to_repo_only(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    (skill / "SKILL.md").write_text("See docs/architecture/adr/README.md for rules.\n", encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "zone-wall" in findings[0]


def test_zone_wall_ignores_repo_only_zone_itself(tmp_path):
    make_clean_tree(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text("Repo docs may reference tools/lint.py freely.\n", encoding="utf-8")
    assert lint.run(tmp_path) == []


def test_sideways_dep_fires_and_self_reference_does_not(tmp_path):
    make_clean_tree(tmp_path)
    other = tmp_path / "skills" / "other-skill"
    other.mkdir(parents=True)
    (other / "SKILL.md").write_text("Compose with skills/example-skill/ for setup.\n", encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1
    assert "sideways-dep" in findings[0] and "other-skill" in findings[0]


def test_doctrine_budget_fires_when_agents_md_bloats(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "AGENTS.md").write_text("x" * (lint.AGENTS_BUDGET_CHARS + 1), encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "doctrine-budget" in findings[0]


def test_pointer_check_fires_when_claude_md_forks(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("Standalone rules with no pointer.\n", encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "doctrine-pointer" in findings[0]


def test_missing_agents_md_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "AGENTS.md").unlink()
    findings = lint.run(tmp_path)
    assert any("AGENTS.md is missing" in f for f in findings)


def test_live_repo_is_clean():
    assert lint.run(lint.ROOT) == []

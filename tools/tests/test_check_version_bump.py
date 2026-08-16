"""Tests for the shipped-zone version-bump guard (ADR-003).

Each case builds a real git repo in tmp_path so the guard is exercised through
git itself rather than a mocked diff — the guard's whole job is reading git
state, and a mock would pin the mock.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check_version_bump


def _run(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _repo(tmp_path: Path, version: str = "0.1.0") -> Path:
    repo = tmp_path / "repo"
    (repo / ".claude-plugin").mkdir(parents=True)
    (repo / "skills" / "demo").mkdir(parents=True)
    (repo / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "demo", "version": version}), encoding="utf-8"
    )
    (repo / "skills" / "demo" / "SKILL.md").write_text("# demo\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "note.md").write_text("repo-only\n", encoding="utf-8")
    _run(repo, "init", "-q", "-b", "main")
    _run(repo, "config", "user.email", "t@example.com")
    _run(repo, "config", "user.name", "t")
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", "base")
    return repo


def _guard(repo: Path, base: str = "main") -> list[str]:
    original = check_version_bump.ROOT
    check_version_bump.ROOT = repo
    try:
        return check_version_bump.run(base)
    finally:
        check_version_bump.ROOT = original


def _bump(repo: Path, version: str) -> None:
    (repo / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "demo", "version": version}), encoding="utf-8"
    )


def test_shipped_change_without_bump_is_a_finding(tmp_path):
    repo = _repo(tmp_path)
    _run(repo, "checkout", "-qb", "work")
    (repo / "skills" / "demo" / "SKILL.md").write_text("# demo v2\n", encoding="utf-8")
    _run(repo, "commit", "-qam", "edit skill")
    findings = _guard(repo)
    assert len(findings) == 1 and "version-bump" in findings[0]
    assert "skills/demo/SKILL.md" in findings[0]


def test_shipped_change_with_bump_is_clean(tmp_path):
    repo = _repo(tmp_path)
    _run(repo, "checkout", "-qb", "work")
    (repo / "skills" / "demo" / "SKILL.md").write_text("# demo v2\n", encoding="utf-8")
    _bump(repo, "0.2.0")
    _run(repo, "commit", "-qam", "edit skill and bump")
    assert _guard(repo) == []


def test_repo_only_change_needs_no_bump(tmp_path):
    repo = _repo(tmp_path)
    _run(repo, "checkout", "-qb", "work")
    (repo / "docs" / "note.md").write_text("repo-only edit\n", encoding="utf-8")
    _run(repo, "commit", "-qam", "edit docs")
    assert _guard(repo) == []


def test_manifest_only_change_needs_no_bump(tmp_path):
    """Editing the manifest's own non-version fields must not demand a bump —
    otherwise the guard fires on the very commit that fixes a description."""
    repo = _repo(tmp_path)
    _run(repo, "checkout", "-qb", "work")
    (repo / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "demo", "version": "0.1.0", "description": "d"}),
        encoding="utf-8",
    )
    _run(repo, "commit", "-qam", "manifest metadata")
    assert _guard(repo) == []


def test_missing_base_ref_is_silent_not_a_crash(tmp_path):
    repo = _repo(tmp_path)
    assert _guard(repo, base="origin/does-not-exist") == []

"""Pins for the ADR-003 §25 version-bump guard.

The predecessor of this guard was withdrawn because it failed open four ways
while printing a clean-pass line, and because three mutations of its exit path
survived green — nothing tested `main()`. Both gaps are pinned here: every
undetermined branch asserts exit 2, and `main()` is exercised directly.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import check_version_bump as cvb  # noqa: E402

PASS, FAIL, UNDETERMINED = cvb.PASS, cvb.FAIL, cvb.UNDETERMINED


def _run(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


def _manifest(repo: Path, version: str) -> None:
    d = repo / ".claude-plugin"
    d.mkdir(exist_ok=True)
    (d / "plugin.json").write_text(json.dumps({"name": "t", "version": version}),
                                   encoding="utf-8")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A real git repo with a `main` and a branch off it."""
    _run(tmp_path, "init", "-q", "-b", "main")
    _run(tmp_path, "config", "user.email", "t@example.com")
    _run(tmp_path, "config", "user.name", "t")
    _manifest(tmp_path, "1.0.0")
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "a.md").write_text("base\n", encoding="utf-8")
    _run(tmp_path, "add", "-A")
    _run(tmp_path, "commit", "-qm", "base")
    _run(tmp_path, "checkout", "-q", "-b", "work")
    monkeypatch.setattr(cvb, "ROOT", tmp_path)
    return tmp_path


def _commit(repo: Path, msg: str) -> None:
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", msg)


def test_shipped_untouched_passes(repo):
    (repo / "notes.md").write_text("x\n", encoding="utf-8")
    _commit(repo, "docs only")
    status, lines = cvb.check("main")
    assert status == PASS and "untouched" in lines[0]


def test_shipped_touched_without_bump_fails(repo):
    (repo / "skills" / "a.md").write_text("changed\n", encoding="utf-8")
    _commit(repo, "skill edit")
    status, lines = cvb.check("main")
    assert status == FAIL
    assert any("skills/a.md" in line for line in lines)


def test_shipped_touched_with_bump_passes(repo):
    (repo / "skills" / "a.md").write_text("changed\n", encoding="utf-8")
    _manifest(repo, "1.1.0")
    _commit(repo, "skill edit + bump")
    assert cvb.check("main")[0] == PASS


def test_version_decrement_is_not_a_bump(repo):
    """The withdrawn guard accepted a decrement."""
    (repo / "skills" / "a.md").write_text("changed\n", encoding="utf-8")
    _manifest(repo, "0.9.0")
    _commit(repo, "skill edit + decrement")
    status, lines = cvb.check("main")
    assert status == FAIL and "BACKWARDS" in lines[0]


def test_bump_alone_is_not_a_shipped_change(repo):
    """The manifest is excluded from the shipped set, or every bump would
    justify itself."""
    _manifest(repo, "1.1.0")
    _commit(repo, "bump only")
    status, lines = cvb.check("main")
    assert status == PASS and "untouched" in lines[0]


def test_multi_commit_branch_is_measured_as_a_whole(repo):
    """Per-PR, not per-commit: an intermediate commit may touch the shipped zone
    with the bump arriving later in the branch. Per-commit would fail this."""
    (repo / "skills" / "a.md").write_text("changed\n", encoding="utf-8")
    _commit(repo, "skill edit, no bump yet")
    _manifest(repo, "1.1.0")
    _commit(repo, "bump")
    assert cvb.check("main")[0] == PASS


def test_moved_base_still_resolves(repo):
    """The withdrawn guard went silent whenever its base had moved — the state
    every merge into the base produces.

    Honest about what this pins: the *behaviour*, not a mechanism. Two redundant
    mechanisms produce it (explicit merge-base resolution, and `...`), and this
    test stays green if either is removed alone — verified by mutating each. It
    catches the regression that matters and cannot attribute it."""
    _run(repo, "checkout", "-q", "main")
    (repo / "unrelated.md").write_text("moved on\n", encoding="utf-8")
    _commit(repo, "main moves")
    _run(repo, "checkout", "-q", "work")
    (repo / "skills" / "a.md").write_text("changed\n", encoding="utf-8")
    _commit(repo, "skill edit")
    status, _ = cvb.check("main")
    assert status == FAIL  # still sees the real answer, not silence


# --- undetermined must never read as a pass ---

def test_unresolvable_base_is_undetermined(repo):
    status, lines = cvb.check("no-such-ref")
    assert status == UNDETERMINED and "cannot determine a base" in lines[0]


def test_unparseable_version_is_undetermined(repo):
    (repo / "skills" / "a.md").write_text("changed\n", encoding="utf-8")
    (repo / ".claude-plugin" / "plugin.json").write_text('{"version": "one"}',
                                                         encoding="utf-8")
    _commit(repo, "bad version")
    status, lines = cvb.check("main")
    assert status == UNDETERMINED and "not a three-part numeric semver" in lines[0]


def test_malformed_manifest_is_undetermined(repo):
    (repo / "skills" / "a.md").write_text("changed\n", encoding="utf-8")
    (repo / ".claude-plugin" / "plugin.json").write_text("{not json", encoding="utf-8")
    _commit(repo, "broken manifest")
    status, lines = cvb.check("main")
    assert status == UNDETERMINED and "not valid JSON" in lines[0]


def test_absent_manifest_is_undetermined(repo):
    (repo / "skills" / "a.md").write_text("changed\n", encoding="utf-8")
    (repo / ".claude-plugin" / "plugin.json").unlink()
    _commit(repo, "manifest gone")
    status, lines = cvb.check("main")
    assert status == UNDETERMINED and "absent" in lines[0]


# --- main()'s exit path, which the withdrawn guard never tested ---

@pytest.mark.parametrize("setup,expected", [
    ("clean", PASS),
    ("no-bump", FAIL),
    ("no-base", UNDETERMINED),
])
def test_main_returns_the_status_as_exit_code(repo, capsys, setup, expected):
    argv = ["--base", "main"]
    if setup == "no-bump":
        (repo / "skills" / "a.md").write_text("changed\n", encoding="utf-8")
        _commit(repo, "skill edit")
    elif setup == "no-base":
        argv = ["--base", "no-such-ref"]
    assert cvb.main(argv) == expected
    out = capsys.readouterr().out
    assert "version-bump (ADR-003)" in out
    if expected == UNDETERMINED:
        assert "UNDETERMINED is a failure" in out

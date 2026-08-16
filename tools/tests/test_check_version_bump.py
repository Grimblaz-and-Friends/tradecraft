"""Pins for the ADR-003 §25 version-bump guard.

The predecessor of this guard was withdrawn because it failed open four ways
while printing a clean-pass line, and because three mutations of its exit path
survived green — nothing tested `main()`. Both gaps are pinned here: **all five**
undetermined branches assert exit 2, and `main()` is exercised directly.

That claim was false when it was first written — three of the five sites were
unpinned, two inherited and one added by the very commit that made the claim. It
is now held by `test_git_failure_is_undetermined_not_a_pass`, which enumerates
the sites, so the sentence cannot drift from the code again.
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


# --- the working tree, which committed history alone cannot see ---

def test_uncommitted_shipped_edit_is_seen(repo):
    """A local run must answer the question CI will answer. Committed history
    alone reports "untouched" while a shipped-zone edit sits uncommitted in
    front of the author — a false pass, and the shape the predecessor guard was
    withdrawn for. Found by trying to exercise this guard's own FAIL path.

    Disclosed because the honest version is less flattering: the withdrawn guard
    read the working tree deliberately, and this guard's first version lost that
    when it switched to `{base}...HEAD`. So this pin restores a capability rather
    than adding one. (The predecessor's version of it was largely inert anyway —
    any version difference short-circuited it to silence — but that is a reason
    to state the history, not to omit it.)"""
    (repo / "skills" / "a.md").write_text("changed, not committed\n", encoding="utf-8")
    status, lines = cvb.check("main")
    assert status == FAIL
    assert any("skills/a.md" in line for line in lines)


def test_untracked_new_skill_is_seen(repo):
    """The canonical new-skill case: a whole directory `git diff` cannot see
    until it is added. The withdrawn predecessor was blind to exactly this."""
    (repo / "skills" / "brand-new").mkdir()
    (repo / "skills" / "brand-new" / "SKILL.md").write_text("new\n", encoding="utf-8")
    status, lines = cvb.check("main")
    assert status == FAIL
    assert any("skills/brand-new/SKILL.md" in line for line in lines)


def test_uncommitted_edit_with_a_bump_passes(repo):
    """The working tree is read for the bump too, so an uncommitted edit paired
    with an uncommitted bump is lawful — this must not become a false FAIL."""
    (repo / "skills" / "a.md").write_text("changed\n", encoding="utf-8")
    _manifest(repo, "1.1.0")
    assert cvb.check("main")[0] == PASS


# --- every UNDETERMINED site, enumerated so the docstring cannot drift ---

@pytest.mark.parametrize("failing", ["diff-base", "diff-tree", "ls-files"])
def test_git_failure_is_undetermined_not_a_pass(repo, monkeypatch, failing):
    """Three sites answer only when git does, and all three were unpinned —
    mutating any of them to fail open left the whole suite green. The tree-read
    site was added by the commit whose message said every branch was pinned."""
    real = cvb._git

    def fake(*args):
        if failing == "diff-base" and args[0] == "diff" and "..." in args[-1]:
            return 128, "", "fatal: bad revision"
        if failing == "diff-tree" and args[0] == "diff" and args[-1] == "HEAD":
            return 128, "", "fatal: index file smaller than expected"
        if failing == "ls-files" and args[0] == "ls-files":
            return 128, "", "fatal: unable to read index"
        return real(*args)

    monkeypatch.setattr(cvb, "_git", fake)
    (repo / "skills" / "a.md").write_text("changed\n", encoding="utf-8")
    status, lines = cvb.check("main")
    assert status == UNDETERMINED
    assert "fatal:" in lines[0]          # ND1: git's own reason reaches the operator


def test_unreadable_base_version_is_undetermined(repo):
    """The fifth site: the manifest is unparseable *at the merge base*.

    Breaking it on `main` after the fork is not enough — the merge base is the
    fork point, which still holds a good manifest. The branch has to descend
    from the broken commit for the base read to fail, which is the whole reason
    this site is separate from `test_malformed_manifest_is_undetermined`.

    Unlike its six siblings this pin does **not** go red against the pre-fix
    guard: that site was already correct, and this only closes the coverage gap
    the module docstring claimed was closed. Coverage, not discrimination —
    stated because claiming otherwise is the defect this batch is fixing."""
    _run(repo, "checkout", "-q", "main")
    (repo / ".claude-plugin" / "plugin.json").write_text("{broken", encoding="utf-8")
    _commit(repo, "break the base manifest")
    _run(repo, "checkout", "-q", "-b", "work2", "main")
    (repo / "skills" / "a.md").write_text("changed\n", encoding="utf-8")
    status, lines = cvb.check("main")
    assert status == UNDETERMINED and "base version unreadable" in lines[0]


def test_fail_message_names_the_file_and_the_act(repo):
    """The message every real violation prints was unpinned — restoring its
    missing-space defect used to leave the suite green — and it named no remedy."""
    (repo / "skills" / "a.md").write_text("changed\n", encoding="utf-8")
    _commit(repo, "skill edit")
    status, lines = cvb.check("main")
    assert status == FAIL
    assert "is unchanged at 1.0.0" in lines[0]
    assert ".claude-plugin/plugin.json" in lines[0] and "Raise" in lines[0]


def test_non_ascii_shipped_path_is_seen(repo):
    """Git quotes non-ASCII paths by default, so `startswith` missed them — a
    false pass, and the other half of the autopsy sentence that gave us the
    untracked-files fix."""
    (repo / "skills" / "café.md").write_text("new\n", encoding="utf-8")
    status, lines = cvb.check("main")
    assert status == FAIL, lines
    _commit(repo, "add non-ascii skill")
    assert cvb.check("main")[0] == FAIL


def test_shipped_file_moved_out_of_the_zone_is_seen(repo):
    """Rename detection reports only the destination, so a skill moved out of the
    shipped zone read as untouched — a skill vanishing from the bundle."""
    _run(repo, "mv", "skills/a.md", "docs-a.md")
    _commit(repo, "move the skill out of the zone")
    status, lines = cvb.check("main")
    assert status == FAIL
    assert any("skills/a.md" in line for line in lines)


def test_a_file_changed_twice_is_counted_once(repo):
    """Three sources unioned with no dedupe counted one file as two, in both the
    PASS and FAIL messages."""
    (repo / "skills" / "a.md").write_text("committed\n", encoding="utf-8")
    _commit(repo, "skill edit")
    (repo / "skills" / "a.md").write_text("and again, uncommitted\n", encoding="utf-8")
    status, lines = cvb.check("main")
    assert status == FAIL
    assert "1 shipped-zone file(s)" in lines[0]
    assert sum(1 for line in lines if line.strip() == "skills/a.md") == 1

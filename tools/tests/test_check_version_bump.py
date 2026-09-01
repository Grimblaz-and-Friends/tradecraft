"""Pins for the version-bump guard.

The predecessor of this guard was withdrawn because it failed open four ways
while printing a clean-pass line, and because three mutations of its exit path
survived green — nothing tested `main()`. Both gaps are pinned here: **every**
undetermined branch asserts exit 2, and `main()` is exercised directly.

That claim was false when it was first written — three of the then-five sites
were unpinned, two inherited and one added by the very commit that made the
claim. It is now held by `test_git_failure_is_undetermined_not_a_pass`, which
enumerates the sites, so the sentence cannot drift from the code again. The
count is deliberately not restated as a number: the external pass on PR #9
collapsed two sites into one, and a number here would have gone stale again.

**And it drifted anyway, on PR #270**, which added exit-2 sites and edited this
file without extending the enumeration — so the sentence was false a second
time, in the change that touched it. Found by mutation rather than by reading:
a sentinel narrowed to the new arm survived with the suite fully green, where
the unnarrowed one reddens three. The lesson the second failure teaches that
the first did not is that "enumerates the sites" is a claim about a test, and a
test only enumerates what a mutation shows it reaches.
"""
from __future__ import annotations

import io
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
                   stdin=subprocess.DEVNULL, capture_output=True, text=True)


def _manifest(repo: Path, version: str, description: str = "d") -> None:
    """`description` is a parameter because it is the subject of one test.

    The real manifest carries consumer-facing copy beside the version, and a
    fixture holding only `name` and `version` cannot exercise the field the
    wholesale exemption was letting through."""
    d = repo / ".claude-plugin"
    d.mkdir(exist_ok=True)
    (d / "plugin.json").write_text(
        json.dumps({"name": "t", "version": version, "description": description}),
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
    justify itself.

    The wording is pinned as well as the outcome. Once the exemption narrowed
    to the `version` field, saying "shipped zone untouched" of a run whose
    author had just edited the manifest asserted the very thing the change
    stopped being true -- and it is the line a consumer sees most often when it
    touches that file."""
    _manifest(repo, "1.1.0")
    _commit(repo, "bump only")
    status, lines = cvb.check("main")
    assert status == PASS
    assert "no shipped-zone change to version" in lines[0]
    assert "untouched" not in lines[0]


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


# --- two bounds: the merge base AND the base ref's tip (#110) ---

def _base_moves_to(repo: Path, version: str) -> None:
    """Land a shipped-zone change plus `version` on `main`, behind the branch.

    Reproduces the moved-tip shape, which is four of the six instances #110
    records: the branch forked at one version, `main` has since published
    another, and the branch has not merged it in -- so its merge base still
    predates the collision and reports clean. The other two (#113, #155) are
    concurrent open pull requests off a base that never moved, which this
    fixture cannot express and which no bound reading HEAD and the base ref
    can see; that residue is #279.

    Said here as well as eleven lines below because the first correction of
    this file's census landed on the test's docstring and stopped short of the
    builder's, leaving the two contradicting each other."""
    _run(repo, "checkout", "-q", "main")
    (repo / "skills" / "b.md").write_text("landed on main" + chr(10), encoding="utf-8")
    _manifest(repo, version)
    _commit(repo, "a sibling change lands on main")
    _run(repo, "checkout", "-q", "work")


def test_a_version_already_taken_on_the_base_tip_is_refused(repo):
    """The moved-tip shape, which issue #110 records four times: #107, #119,
    the 0.29.0 collision routed from #122, and #262. Merge base 1.0.0, main
    1.1.0, branch 1.1.0 -- the branch did raise the version it forked from, so
    the merge base alone reports a clean bump and exits 0.

    #110's other two instances (#113, #155) are NOT this shape: both are
    concurrent open pull requests off a base that had not moved, which no bound
    reading only HEAD and the base ref can see. They are cited nowhere in this
    fixture. Nor was each caught at the merge button -- #107's was caught by a
    defense mid-review, #113's by a round-one seat, #262's while resolving
    merge conflicts; only #119's was literally at the button."""
    _base_moves_to(repo, "1.1.0")
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "1.1.0")
    _commit(repo, "skill edit + a bump onto a taken version")
    status, lines = cvb.check("main")
    assert status == FAIL, lines
    assert "ALREADY CARRIES 1.1.0" in lines[0]
    assert any("skills/a.md" in line for line in lines)


def test_the_taken_version_message_says_what_to_do_next(repo):
    """A guard that only says no costs the session a search. This one names the
    act -- bring the base in, raise the version again -- and discloses that its
    answer is only as fresh as the last fetch, which is the one thing a session
    cannot see from the output."""
    _base_moves_to(repo, "1.1.0")
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "1.1.0")
    _commit(repo, "skill edit + a bump onto a taken version")
    status, lines = cvb.check("main")
    assert status == FAIL
    assert "Bring main into this branch" in lines[0]
    assert "raise " + chr(34) + "version" + chr(34) in lines[0]
    # And NOT the freshness note: `main` here is a local branch, which has no
    # fetch relationship to go stale. Pointing a session at a fetch it cannot
    # perform trains it to discount the clause on the one path where the clause
    # is load-bearing.
    assert "fresh as your last fetch" not in lines[0]


def test_a_bump_past_the_moved_tip_still_passes(repo):
    """The lawful-work polarity, and the one that matters most: a branch whose
    base moved and which bumps past what the base now carries is doing exactly
    the right thing. A bound that blocked this would make the guard unusable
    the moment `main` moved."""
    _base_moves_to(repo, "1.1.0")
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "1.2.0")
    _commit(repo, "skill edit + a bump past the moved tip")
    status, lines = cvb.check("main")
    assert status == PASS, lines
    assert "1.0.0 -> 1.2.0" in lines[0]
    assert "carrying 1.1.0" in lines[0]   # the moved tip is disclosed, not silent


def test_a_branch_level_with_its_base_is_unaffected(repo):
    """The second bound is a no-op when the base has not moved -- which is the
    common case, and the one every other test in this file runs in. Pinned so
    the tip read cannot start changing the ordinary answer.

    Unlike its siblings this does **not** go red against the pre-fix guard: the
    pre-fix guard had no tip clause to print, so what it asserts held there too.
    It is a regression pin on the quiet case, not a discriminator, and saying so
    is the standard `test_unreadable_base_version_is_undetermined` set in this
    file.

    **It asserted a dead string for two commits.** The wording it named --
    `has since moved` -- was the guard's until the review's first fix batch
    rewrote this block, and the assertion was left pointing at text no revision
    since can produce, so it could not fail in any state while a decision entry
    credited it with holding this path. It now names the clause the guard
    actually prints, and denies the one it must not, so it reds in both
    directions."""
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "1.1.0")
    _commit(repo, "skill edit + bump")
    status, lines = cvb.check("main")
    assert status == PASS, lines
    assert "which is also main's tip" in lines[0]
    assert "carrying" not in lines[0]


def test_an_unreadable_base_tip_version_is_undetermined(repo):
    """The tip is a third revision the guard now depends on, so it is a third
    site that must refuse to answer rather than fall through to a pass. Distinct
    from the merge-base site: `main` is broken only in the commit the branch
    never forked from."""
    _run(repo, "checkout", "-q", "main")
    (repo / ".claude-plugin" / "plugin.json").write_text("{broken", encoding="utf-8")
    _commit(repo, "break the manifest on main, after the fork")
    _run(repo, "checkout", "-q", "work")
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "1.1.0")
    _commit(repo, "skill edit + bump")
    status, lines = cvb.check("main")
    assert status == UNDETERMINED, lines
    assert "base tip version unreadable" in lines[0]


# --- the manifest exemption is a field, not a file (#20) ---

def test_a_description_edit_alone_is_a_shipped_change(repo):
    """`description` is consumer-facing copy. Excluding the whole manifest let
    it change at an unchanged version, so a consumer saw new copy and had no
    signal that installed and current differed. The circularity that earned the
    exemption reaches `version` and nothing else."""
    _manifest(repo, "1.0.0", description="new consumer-facing copy")
    _commit(repo, "description only")
    status, lines = cvb.check("main")
    assert status == FAIL, lines
    assert any(".claude-plugin/plugin.json" in line for line in lines)


def test_a_description_edit_with_a_bump_passes(repo):
    """The other polarity: the copy edit is lawful, it just has to be versioned
    like any other shipped change.

    The named manifest is what makes this discriminate. A PASS alone is what the
    pre-fix guard returned too -- by calling the zone untouched, which is the
    defect. Asserting the file is counted separates the right answer from the
    right answer for the wrong reason."""
    _manifest(repo, "1.1.0", description="new consumer-facing copy")
    _commit(repo, "description + bump")
    status, lines = cvb.check("main")
    assert status == PASS, lines
    assert ".claude-plugin/plugin.json" in lines[0]


def test_an_unreadable_manifest_edit_is_undetermined_not_a_pass(repo):
    """The field comparison reads two revisions, and a read it cannot make is
    the guard's own doctrine: say so and exit non-zero. Without this the
    manifest edit would fall through to "untouched" -- a false pass introduced
    by the very change that closed one."""
    (repo / ".claude-plugin" / "plugin.json").write_text("{not json", encoding="utf-8")
    _commit(repo, "break the manifest, and nothing else")
    status, lines = cvb.check("main")
    assert status == UNDETERMINED, lines
    assert "current manifest unreadable" in lines[0] and "not valid JSON" in lines[0]


# --- the decade boundary, which no fixture distinguished (#33) ---

def _base_at(repo: Path, version: str) -> None:
    """Put `version` on `main` and re-cut the branch from it."""
    _run(repo, "checkout", "-q", "main")
    _manifest(repo, version)
    _commit(repo, "set the base version")
    _run(repo, "checkout", "-q", "-B", "work", "main")


def test_a_minor_bump_across_a_decade_boundary_is_a_bump(repo):
    """0.9.0 -> 0.10.0 was this repository's first decade-crossing bump, and
    every existing fixture (1.0.0 -> 1.1.0, 1.0.0 -> 0.9.0) survives a lexical
    comparison unchanged. Mutate `_parse_semver` to `return tuple(parts)` and
    "10" < "9": this lawful bump is refused, CI turns red, and the whole suite
    plus the lint stay green -- which is what left the int cast unpinned."""
    _base_at(repo, "0.9.0")
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "0.10.0")
    _commit(repo, "skill edit + decade-crossing bump")
    status, lines = cvb.check("main")
    assert status == PASS, lines
    assert "0.9.0 -> 0.10.0" in lines[0]


def test_a_decrement_across_a_decade_boundary_is_not_a_bump(repo):
    """The neighbouring half, and the one that fails OPEN under the same
    mutant: lexically "0.9.0" > "0.10.0", so a real decrement reads as a rise
    and ships. Its sibling above catches the mutant by going red; this one
    catches it by refusing to go green."""
    _base_at(repo, "0.10.0")
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "0.9.0")
    _commit(repo, "skill edit + decade-crossing decrement")
    status, lines = cvb.check("main")
    assert status == FAIL, lines
    assert "BACKWARDS, 0.10.0 -> 0.9.0" in lines[0]


# --- the second bound is only as good as the ref behind it (#110 round one) ---

def _with_remote(repo: Path) -> Path:
    """Give `repo` a real `origin` it can fall behind.

    A local branch cannot go stale, so no fixture built on one can exercise the
    state that produces the defect this guard exists for: the sibling landed
    upstream after you branched, which is also exactly when your
    remote-tracking ref is out of date."""
    origin = repo.parent / (repo.name + "-origin")
    # `-b main`, because `init.defaultBranch` is ambient: under the stock
    # `master` the bare repo's HEAD points at a branch this fixture never
    # creates, the clone comes up on `master`, and the push dies with `src
    # refspec main does not match any` -- a red on a test this change added,
    # reading as a guard defect and caused by the machine's git config. CI has
    # never run on this fixture, which is how it survived to the closing stage.
    _run(repo, "init", "--bare", "-q", "-b", "main", str(origin))
    _run(repo, "remote", "add", "origin", str(origin))
    _run(repo, "push", "-q", "origin", "main")
    _run(repo, "fetch", "-q", "origin")
    return origin


def _upstream_takes(repo: Path, origin: Path, version: str) -> None:
    """Land a shipped-zone change plus `version` on origin/main, from a clone
    that is not this working tree -- so `repo` only learns of it by fetching."""
    other = repo.parent / (repo.name + "-other")
    _run(repo, "clone", "-q", str(origin), str(other))
    _run(other, "config", "user.email", "t@example.com")
    _run(other, "config", "user.name", "t")
    (other / "skills").mkdir(exist_ok=True)
    (other / "skills" / "sibling.md").write_text("landed" + chr(10), encoding="utf-8")
    _manifest(other, version)
    _run(other, "add", "-A")
    _run(other, "commit", "-qm", "a sibling lands upstream")
    _run(other, "push", "-q", "origin", "main")


def test_a_pass_names_the_tip_it_consulted_and_its_freshness(repo):
    """The disclosure has to be on the PASS, because the PASS is the answer the
    stale ref corrupts.

    Round one of this change put the freshness note only on the FAIL -- the
    path taken when the ref was fresh enough to catch the collision. On the
    path that matters the ref is stale, `tip == base`, the moved-tip clause is
    suppressed, and the false PASS is textually identical to a true one. A
    session cannot act on a warning printed only when the warning was
    unnecessary."""
    origin = _with_remote(repo)
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "1.1.0")
    _commit(repo, "skill edit + bump")
    status, lines = cvb.check("origin/main")
    assert status == PASS, lines
    assert "origin/main" in lines[0]
    assert "only as fresh as your last fetch" in lines[0]


def test_the_freshness_note_is_absent_for_a_local_base(repo):
    """The other polarity, and the reason the note is conditional at all: a
    local branch does not go stale, so the note would be a no-op the reader
    learns to skip."""
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "1.1.0")
    _commit(repo, "skill edit + bump")
    status, lines = cvb.check("main")
    assert status == PASS, lines
    assert "fresh as your last fetch" not in lines[0]


def test_a_stale_remote_ref_still_discloses_what_it_read(repo):
    """The live #110 shape, end to end: the sibling landed upstream, this clone
    has not fetched, and the guard passes -- because it cannot see what it was
    not told. What it can do, and now does, is say which revision it read, so a
    session holding a green has something to check."""
    origin = _with_remote(repo)
    _upstream_takes(repo, origin, "1.1.0")          # upstream moves...
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "1.1.0")                        # ...and we take the same number
    _commit(repo, "skill edit + bump onto a number upstream already took")
    status, lines = cvb.check("origin/main")        # no fetch in between
    assert status == PASS, lines                    # honestly blind, and says so
    assert "only as fresh as your last fetch" in lines[0]
    _run(repo, "fetch", "-q", "origin")             # the act the note names
    status, lines = cvb.check("origin/main")
    assert status == FAIL, lines
    assert "ALREADY CARRIES 1.1.0" in lines[0]


def test_a_version_behind_the_moved_tip_is_not_called_a_collision(repo):
    """`new < top` reaches the same branch as `new == top` and is a different
    fault. Telling a session that main ALREADY CARRIES 1.1.0 when main is at
    1.2.0 and nobody carries 1.1.0 hands the reader who verifies -- the
    documented behaviour -- a claim they falsify in one look."""
    _base_moves_to(repo, "1.2.0")
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "1.1.0")
    _commit(repo, "skill edit + a bump that lands behind the base")
    status, lines = cvb.check("main")
    assert status == FAIL, lines
    assert "already past it at 1.2.0" in lines[0]
    assert "ALREADY CARRIES" not in lines[0]


def test_the_no_bump_failure_names_the_moved_tip_it_already_read(repo):
    """Round one spent two guard cycles on information it held in the first.

    `top` is read before either message is composed, so a branch whose base has
    moved and which has not bumped yet was told only "raise the version", took
    the obvious next number, and hit the collision message on the second run.
    It also asserted that a branch already carrying a bump needs no second one
    -- false in exactly this state, and the sentence CI prints on a merge ref.

    The replacement clause is pinned too, and that is this pin's second life:
    the first version of it asserted only the ABSENCE of the old sentence, so
    the clause that replaced it was free to be equally false. It said a bump
    this branch already made had been absorbed -- to a branch, in this very
    fixture, that never bumped at all."""
    _base_moves_to(repo, "1.1.0")
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _commit(repo, "skill edit, no bump")
    status, lines = cvb.check("main")
    assert status == FAIL, lines
    assert "The merge base has moved" in lines[0]
    assert "1.1.0" in lines[0]                       # what the tip carries
    assert "needs no second one" not in lines[0]
    assert "past 1.1.0" in lines[0]                  # the target, not just "raise"
    # This branch made no bump; the message may not say it did.
    assert "already made" not in lines[0]
    assert "has not risen above" in lines[0]


def test_the_unit_sentence_survives_where_it_is_true(repo):
    """The other polarity of the same conditional: with the base unmoved, a
    branch already carrying a bump really does need no second one, and that
    sentence is what stops a multi-commit branch bumping once per commit."""
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _commit(repo, "skill edit, no bump")
    status, lines = cvb.check("main")
    assert status == FAIL, lines
    assert "needs no second one" in lines[0]
    assert "merge base has moved" not in lines[0]


def test_the_manifest_failure_says_why_the_manifest_counts(repo):
    """The narrowed exemption reached its consumer only through the source.

    Without this the message names the manifest as a changed shipped file and
    prescribes editing that same file -- which reads as the circularity the
    exemption exists to prevent, to a reader holding the rule as it stood until
    this change."""
    _manifest(repo, "1.0.0", description="new consumer-facing copy")
    _commit(repo, "description only")
    status, lines = cvb.check("main")
    assert status == FAIL, lines
    assert "field other than" in lines[0] and "version" in lines[0]
    assert "raising the version alone never counts" in lines[0]


def test_an_explicit_sha_is_shown_as_a_sha_not_repeated_whole(repo):
    """A 40-character sha interpolated three times buried the act, and the
    freshness clause is meaningless for a revision that cannot move."""
    _base_moves_to(repo, "1.1.0")
    tip = subprocess.run(["git", "-C", str(repo), "rev-parse", "main"],
                         stdin=subprocess.DEVNULL, capture_output=True,
                         text=True, check=True).stdout.strip()
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "1.1.0")
    _commit(repo, "skill edit + bump onto a taken version")
    status, lines = cvb.check(tip)
    assert status == FAIL, lines
    assert tip not in lines[0], "the full sha should not be repeated whole"
    assert tip[:7] in lines[0]
    assert "fresh as your last fetch" not in lines[0]


def test_a_merge_commit_head_is_the_shape_ci_evaluates(repo):
    """CI checks out `refs/pull/N/merge`, so its HEAD is the branch already
    merged into the base and `merge-base(HEAD, base) == base tip`. Nothing
    pinned that shape, which is the one the guard's only automatic caller
    actually runs against."""
    _base_moves_to(repo, "1.1.0")
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "1.1.0")
    _commit(repo, "skill edit + bump onto a taken version")
    _run(repo, "merge", "-q", "main", "-m", "merge base into branch")
    status, lines = cvb.check("main")
    assert status == FAIL, lines
    # On a merged HEAD the two bounds coincide, so the first one catches it and
    # the message is the no-bump one -- which must therefore be honest here.
    assert "is unchanged at 1.1.0" in lines[0]
    assert "needs no second one" in lines[0]


# --- every exit-2 site, including the ones round one added ---

def test_an_absent_base_manifest_is_not_a_failure_to_answer(repo):
    """An adopting repository's first pull request adds the manifest, so the
    base does not have one -- and no act on the branch can ever give it one.

    Round one read both sides unconditionally and returned exit 2 there. The
    widening the owner affirmed was a broken manifest on the CURRENT side; this
    case was never disclosed and is withdrawn.

    **What this pins is the manifest-alone case, and only that.** A pull
    request adding the manifest alongside the skills being adopted -- the shape
    an adoption actually takes -- makes `touched` non-empty and still exits 2
    from the base version read. That red is inherited (it exits 2 before this
    change too) and recorded rather than fixed; this docstring said "the one
    pull request every adopting session must ship" while pinning the narrower
    half, which is the overstatement the post-fix look caught."""
    _run(repo, "checkout", "-q", "main")
    (repo / ".claude-plugin" / "plugin.json").unlink()
    _commit(repo, "a base with no manifest")
    _run(repo, "checkout", "-q", "-b", "adopt", "main")
    _manifest(repo, "0.1.0")
    _commit(repo, "adopt the plugin: add the manifest")
    status, lines = cvb.check("main")
    assert status == PASS, lines


def test_an_unreadable_manifest_added_to_a_base_that_has_none_is_undetermined(repo):
    """The current side is read whenever the manifest changed, even where the
    base has no manifest to compare against.

    Found by the external pass on the final tree, after three internal stages
    had not. The gate that withdrew the undisclosed base-side widening reached
    one step too far: it gated the CURRENT-side read as well, so a branch adding
    an unreadable manifest to a base that has none was told the zone was
    untouched -- a claim about a file nothing had parsed, and the exact case the
    affirmed artifact disclosed as exit 2. Its sibling below is the same read on
    a base that does have one; this is the half the gate silenced."""
    _run(repo, "checkout", "-q", "main")
    (repo / ".claude-plugin" / "plugin.json").unlink()
    _commit(repo, "a base with no manifest")
    _run(repo, "checkout", "-q", "-b", "adopt", "main")
    (repo / ".claude-plugin").mkdir(exist_ok=True)
    (repo / ".claude-plugin" / "plugin.json").write_text("{not json", encoding="utf-8")
    _commit(repo, "adopt the plugin with a manifest that does not parse")
    status, lines = cvb.check("main")
    assert status == UNDETERMINED, lines
    assert "current manifest unreadable" in lines[0]
    assert "so it parses, then re-run" in lines[0]


def test_an_unreadable_current_manifest_names_the_act(repo):
    """The affirmed half of the widening, with the remedy the ruling required
    of every message this change touched."""
    (repo / ".claude-plugin" / "plugin.json").write_text("{not json", encoding="utf-8")
    _commit(repo, "break the manifest, and nothing else")
    status, lines = cvb.check("main")
    assert status == UNDETERMINED, lines
    assert "current manifest unreadable" in lines[0]
    assert "so it parses, then re-run" in lines[0]


def test_a_manifest_that_is_not_utf8_is_undetermined(repo):
    """`read_text` raised before `_manifest_at` could return its error tuple, so
    the guard died with a traceback whose exit code 1 reads as FAIL -- the
    wrong one of three outcomes. Found independently by both external
    reviewers on this pull request."""
    (repo / ".claude-plugin" / "plugin.json").write_bytes(
        b'{"name": "t", "version": "1.0.0", "description": "\xff\xfe"}')
    _commit(repo, "a manifest that is not utf-8")
    status, lines = cvb.check("main")
    assert status == UNDETERMINED, lines
    assert "not valid UTF-8" in lines[0]


def test_a_manifest_that_is_not_an_object_is_undetermined(repo):
    """The branch that silently repaired a pre-existing crash and was pinned by
    nothing: dropping the isinstance check restored an uncaught AttributeError
    with all forty tests green."""
    (repo / ".claude-plugin" / "plugin.json").write_text("[1, 2, 3]", encoding="utf-8")
    _commit(repo, "a manifest that is a list")
    status, lines = cvb.check("main")
    assert status == UNDETERMINED, lines
    assert "not a JSON object" in lines[0]


def test_a_version_whose_digits_int_cannot_take_is_undetermined(repo):
    """`isdigit` and `int` disagree. The superscript two passes the gate and
    fails the cast, so the guard raised instead of answering -- in the function
    whose docstring this change rewrote to say the cast is the whole
    comparison."""
    superscript_two = chr(0xB2)
    _manifest(repo, "1.0." + superscript_two)
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _commit(repo, "a version int() cannot take")
    status, lines = cvb.check("main")
    assert status == UNDETERMINED, lines
    assert "not a three-part numeric semver" in lines[0]


# --- the target is a bound to clear, never a number already in the file ---

def test_the_no_bump_failure_names_a_target_above_the_current_version(repo):
    """The guard's most-printed message, and the one that told a session to
    raise the version to the version it already had.

    An earlier form named the current version as the target, so a consumer that
    performed the act -- which both experience sessions established consumers
    do -- set the version to what it already was and came back to the identical
    red. This arm was the one the moved-base pin did not cover, so correcting
    it left the whole suite green."""
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _commit(repo, "skill edit, no bump, base unmoved")
    status, lines = cvb.check("main")
    assert status == FAIL, lines
    assert "is unchanged at 1.0.0" in lines[0]
    assert "past 1.0.0" in lines[0]
    assert "to 1.0.0 " not in lines[0], "the target may not be the current version"


def test_a_decrement_is_not_told_to_raise_to_the_decremented_value(repo):
    """The same defect's sharper face: the message reported the version had
    gone BACKWARDS and then named the backwards value as what to raise to."""
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "0.9.0")
    _commit(repo, "skill edit + decrement")
    status, lines = cvb.check("main")
    assert status == FAIL, lines
    assert "BACKWARDS, 1.0.0 -> 0.9.0" in lines[0]
    assert "past 1.0.0" in lines[0]
    assert "to 0.9.0 " not in lines[0], "the target may not be the decremented value"


def test_a_fully_qualified_remote_ref_still_discloses_its_freshness(repo):
    """`refs/remotes/origin/main` is a lawful spelling of the same ref, and the
    spelling this repository's own persist script uses for its refs.

    The predicate was a string-prefix concatenation, so this spelling became
    `refs/remotes/refs/remotes/origin/main`, never resolved, and the freshness
    disclosure vanished -- on the stale-read path the disclosure exists for."""
    _with_remote(repo)
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "1.1.0")
    _commit(repo, "skill edit + bump")
    for spelling in ("origin/main", "refs/remotes/origin/main"):
        status, lines = cvb.check(spelling)
        assert status == PASS, (spelling, lines)
        assert "only as fresh as your last fetch" in lines[0], spelling


def test_a_non_ascii_digit_is_not_a_version(repo):
    """The only false PASS the review found anywhere.

    `int()` accepts an Arabic-Indic digit and no consumer reading a version
    string does, so the guard passed the bump -- and printed it as the ASCII
    version it is not, because the report is rebuilt from the parsed ints. The
    PASS line was byte-identical to a lawful ASCII bump's."""
    arabic_indic_three = chr(0x0663)
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _manifest(repo, "1.0." + arabic_indic_three)
    _commit(repo, "skill edit + a bump no consumer can read")
    status, lines = cvb.check("main")
    assert status == UNDETERMINED, lines
    assert "not a three-part numeric semver" in lines[0]


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
    assert "version-bump:" in out
    if expected == UNDETERMINED:
        assert "UNDETERMINED is a failure" in out


# --- the working tree, which committed history alone cannot see ---

def test_uncommitted_shipped_edit_is_seen(repo):
    """A local run answers "would this be lawful if I committed everything
    now" — deliberately NOT the question CI answers, which is about the commits
    you actually made. Committed history
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

@pytest.mark.parametrize("failing", ["diff", "ls-files"])
def test_git_failure_is_undetermined_not_a_pass(repo, monkeypatch, failing):
    """Both path-listing sites answer only when git does, and both were unpinned
    — mutating either to fail open left the whole suite green. The untracked site
    was added by the commit whose message said every branch was pinned.

    (This was three cases until the external pass on PR #9 collapsed the two
    tracked-file reads into one two-dot diff against the projected tree; a
    union of two name-lists cannot represent a cancellation.)"""
    real = cvb._git

    def fake(*args):
        if failing == "diff" and args[0] == "diff":
            return 128, "", "fatal: bad revision"
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
    # Built rather than written: the character is the subject under test, and
    # a non-docstring string constant stays ASCII. The first attempt wrote
    # f"caf{{chr(0xE9)}}.md" -- doubled braces are an f-string escape, so it
    # produced the ASCII name caf{chr(0xE9)}.md, git never quoted it, and this
    # test passed while pinning nothing at all.
    e_acute = chr(0xE9)
    (repo / "skills" / f"caf{e_acute}.md").write_text("new\n", encoding="utf-8")
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


def test_uncommitted_move_out_of_the_zone_is_seen(repo):
    """The working-tree half of the rename fix, which was unpinned: its sibling
    commits the move, so it exercised only the base diff. This is the half the
    pre-commit line in AGENTS.md actually runs, and dropping `--no-renames`
    there left the whole suite green."""
    _run(repo, "mv", "skills/a.md", "docs-a.md")     # staged, not committed
    status, lines = cvb.check("main")
    assert status == FAIL
    assert any("skills/a.md" in line for line in lines)


def test_git_stderr_reaches_the_operator(repo):
    """The stderr plumbing itself, not its interpolation.

    The parametrized failure test monkeypatches `_git` wholesale, so it pins the
    call sites and never exercises `_git`'s own capture of `proc.stderr` —
    dropping that capture left 79 tests green. This calls the real thing."""
    code, out, err = cvb._git("rev-parse", "--verify", "definitely-not-a-ref")
    assert code != 0
    assert out.strip() == ""
    assert err, "git's own reason must survive _git, or UNDETERMINED says nothing actionable"


def test_an_uncommitted_reversal_cancels(repo):
    """A union of two name-lists cannot represent cancellation.

    Commit a shipped-zone edit, then revert it in the working tree: the
    projected tree is byte-identical to the merge base, so the branch lands no
    shipped-zone change and needs no bump. Unioning `base...HEAD` with the tree
    diff named the path twice and FAILed — a false FAIL that would have sent an
    author chasing a bump their PR does not need. Found by the external pass on
    PR #9; the fix is a two-dot diff against the projected tree."""
    (repo / "skills" / "a.md").write_text("changed\n", encoding="utf-8")
    _commit(repo, "skill edit")
    (repo / "skills" / "a.md").write_text("base\n", encoding="utf-8")   # reverted
    status, lines = cvb.check("main")
    assert status == PASS, lines
    assert "untouched" in lines[0]


def test_a_path_git_must_quote_is_still_seen(repo):
    """`core.quotePath=false` only stops git quoting non-ASCII. A newline, quote
    or backslash in a path is C-quoted regardless, and a line-oriented read then
    misses the shipped-zone prefix — a false pass. `-z` is what makes the read
    safe; this pins the parser rather than the filesystem, since not every OS
    permits such a name."""
    assert cvb._paths("skills/a.md\0skills/we ird.md\0") == [
        "skills/a.md", "skills/we ird.md"]
    # a trailing space in the final name survives: no .strip() on stdout
    assert cvb._paths("skills/trailing .md\0") == ["skills/trailing .md"]


def test_the_failing_message_survives_being_captured(repo, capsysbinary):
    """#147's exact path: the message a Windows harness reads when a PR is unlawful.

    Not a restatement of the lint's emitted-ASCII check, which reads literals.
    This runs the real failing path, so what is asserted is the composed
    message -- literals plus whatever git handed back -- rather than the source.

    What it proves is that no non-ASCII character reaches the stream, which is
    the property that matters: which *byte* such a character becomes depends on
    the capture, and that dependence is the defect. Under pytest's capture it
    encodes UTF-8 (0xE2...); through a real pipe on Windows the same character
    left as the cp1252 byte 0x97, which is what #147 recorded and what a UTF-8
    reader renders as a replacement character. Probed red by restoring the em
    dash to the message: this fails with a UnicodeDecodeError.
    """
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _commit(repo, "skill edit")
    status, lines = cvb.check("main")
    assert status == FAIL
    for line in lines:
        print(line)
    out = capsysbinary.readouterr().out
    assert out.decode("ascii"), "the captured bytes must decode as ASCII"

def test_a_runtime_path_the_repo_did_not_write_survives_capture(repo, monkeypatch):
    """The half no literal check can reach, on both streams.

    The emitted-ASCII rule protects what this repository writes. This is what
    it is handed: a shipped path someone else chose.

    The streams are stood up as real cp1252 wrappers rather than left to
    pytest's capture, and that is the whole reason this test discriminates.
    `capsysbinary` alone does not: pytest's replacement stream is not encoded
    to the platform code page, so removing the fix leaves it green and the
    test pins nothing. Verified by removing utf8_stdio() from main(): with
    these wrappers stdout comes back carrying 0xe9 and the second name raises
    UnicodeEncodeError, killing the report before the offending path prints,
    so the message naming the problem is the message that goes missing.
    """
    streams = {}
    for name in ("stdout", "stderr"):
        buffer = io.BytesIO()
        streams[name] = (buffer, io.TextIOWrapper(buffer, encoding="cp1252", newline=""))
        monkeypatch.setattr(sys, name, streams[name][1])
    e_acute, cjk = chr(0xE9), chr(0x4E2D)
    for name in (f"caf{e_acute}.md", f"{cjk}.md"):
        (repo / "skills" / name).write_text("new" + chr(10), encoding="utf-8")
    status = cvb.main(["--base", "main"])
    for _name, wrapper in streams.values():
        wrapper.flush()
    assert status == 1
    for stream_name, (buffer, _wrapper) in streams.items():
        raw = buffer.getvalue()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AssertionError(
                f"{stream_name} carried a non-UTF-8 byte at {exc.start}: {raw!r}"
            ) from None
        assert "UnicodeEncodeError" not in text
    out = streams["stdout"][0].getvalue().decode("utf-8")
    for name in (e_acute, cjk):
        assert name in out, f"the report never printed the path carrying {name!r}"

# The guard's FAIL text tells a session where the procedure it enforces lives.
# That citation named AGENTS.md's "The flow" until #291 moved the section into
# a repo-only cell, and the string stayed behind pointing at a file where the
# word no longer appears -- read by exactly the session that forgot the bump.
# Nothing caught it, because no test compared the citation against the tree.
# These two do: the first pins the path and its heading, the second pins that
# the FAIL branches actually carry it. [#304]
def test_flow_citation_names_a_path_that_carries_the_flow():
    root = Path(__file__).resolve().parent.parent.parent
    rel = cvb.FLOW_CITATION.split(",")[0]
    target = root / rel
    assert target.is_file(), (
        f"FLOW_CITATION names {rel!r}, which is not a file in this tree -- "
        "the citation was left behind by a move"
    )
    body = target.read_text(encoding="utf-8")
    assert "The flow" in body, (
        f"FLOW_CITATION sends a session to {rel!r} for 'The flow', and that "
        "heading is not there"
    )


def test_the_fail_branches_carry_the_flow_citation(repo):
    (repo / "skills" / "a.md").write_text("changed" + chr(10), encoding="utf-8")
    _commit(repo, "skill edit")
    status, lines = cvb.check("main")
    assert status == FAIL
    assert any(cvb.FLOW_CITATION in line for line in lines), (
        "the unchanged-version FAIL dropped the citation telling a session "
        f"where to look; got {lines!r}"
    )

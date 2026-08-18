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
    # D-59: `artifact` was the one vocabulary in this file with no pin, so a
    # local widening or narrowing of it passed both the suite and the live lint.
    # It is also the set an edit reaches first: it gained a growth rule only in
    # D-53 and took its first new value in the same change that adds this pin.
    assert lint.LEDGER_ARTIFACTS == {
        "constitution", "repo-docs", "work-prose", "skill-prose", "script",
        "lint", "tests", "ci", "packaging",
    }


def test_ledger_accepts_a_defect_made_early_and_detectable_late(tmp_path):
    """`introduced: design, catchable: implementation` — the shape ADR-006 §5
    says the position axis exists to measure, and the one no row has ever held.
    Goes red if anything ever re-imposes the retired rule that set `catchable`
    from `introduced`, which is the amendment's central act and was otherwise
    pinned by nothing: the rule can be reinstated in the lint with every other
    test green, because no other fixture has the two fields differing."""
    _write_ledger(
        tmp_path,
        _ledger_row(introduced="design", catchable="implementation"),
    )
    assert lint.run(tmp_path) == []


def test_ledger_position_fields_reject_stage_values(tmp_path):
    """The two axes are separate vocabularies. Goes red the moment they are
    merged back into one set. That merge was the schema half of what kept the
    retirement test from failing; the rule half outlived it and was retired
    separately (ADR-006 §5), so this pin does not claim to have cured the test."""
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
    # The array row is now rejected as "not a JSON object" rather than diffed
    # against its own values — that older behaviour reported the row's *entries*
    # as present fields, a false negative dressed as a finding. The exception
    # boundary it used to exercise is still pinned, by the unhashable-id test.
    assert any("is not a JSON object" in f for f in findings)
    assert not any("missing field" in f for f in findings)
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


# --- ledger vocabulary added 2026-08-17 ------------------------------------

def test_ledger_filed_disposition_is_lawful(tmp_path):
    """§4 makes filing the exception; a finding that clears that bar had no
    value to say so and was written `recorded`, which is a different claim."""
    _write_ledger(tmp_path, _ledger_row(disposition="filed"))
    assert lint.run(tmp_path) == []


def test_ledger_trial_is_optional_but_form_checked(tmp_path):
    _write_ledger(tmp_path, _ledger_row())  # absent — lawful
    assert lint.run(tmp_path) == []
    for bad in ("Gate Procedure", "Trial-One", "trial one", "", 7, ["x"]):
        target = tmp_path / f"trial{abs(hash(str(bad)))}"
        target.mkdir()
        _write_ledger(target, _ledger_row(trial=bad))
        assert any("trial" in f for f in lint.run(target)), bad


def test_ledger_trial_token_is_accepted(tmp_path):
    _write_ledger(tmp_path, _ledger_row(trial="convergence-gate"))
    assert lint.run(tmp_path) == []


# --- seat record -----------------------------------------------------------
#
# The precision axis. The defect ledger holds only sustained findings, so a seat
# filing thirty to land three reads identically to one filing three; these rows
# carry both numbers. The `status` field is the load-bearing one: `clean` and
# `failed` both carry zeros, and without it they are the same row — the exact
# collapse the file exists to close.

def _seat_row(**overrides):
    row = {
        "source": "pr19-panel-2026-08-17", "date": "2026-08-17",
        "seat": "cold-read", "model": "fable", "runtime": "claude-code",
        "lane": "panel", "raw": 12, "merged": 12, "sustained": 10,
        "status": "ran", "isolated": False,
    }
    row.update(overrides)
    return row


def _write_seat_record(root: Path, *rows) -> None:
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "seat-record.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )


def test_seat_record_absent_is_clean(tmp_path):
    make_clean_tree(tmp_path)
    assert lint.run(tmp_path) == []


def test_valid_seat_row_is_clean(tmp_path):
    make_clean_tree(tmp_path)
    _write_seat_record(tmp_path, _seat_row())
    assert lint.run(tmp_path) == []


def test_seat_row_missing_field_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    row = _seat_row()
    del row["status"]
    _write_seat_record(tmp_path, row)
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "missing field(s) status" in findings[0]


def test_seat_row_bad_status_and_lane_are_findings(tmp_path):
    make_clean_tree(tmp_path)
    _write_seat_record(tmp_path, _seat_row(status="skipped", lane="lite"))
    findings = lint.run(tmp_path)
    assert len(findings) == 2
    assert any("status" in f for f in findings) and any("lane" in f for f in findings)


def test_seat_row_names_must_be_lowercase_tokens(tmp_path):
    make_clean_tree(tmp_path)
    for field, bad in (("seat", "Cold-Read"), ("model", "Fable"), ("runtime", "Claude Code")):
        target = tmp_path / f"case-{field}"
        target.mkdir()
        make_clean_tree(target)
        _write_seat_record(target, _seat_row(**{field: bad}))
        findings = lint.run(target)
        assert len(findings) == 1 and field in findings[0], (field, findings)


def test_seat_row_counts_must_be_non_negative_ints(tmp_path):
    make_clean_tree(tmp_path)
    # True is an int subclass; it must not pass as a count of 1.
    for bad in (-1, "12", 1.5, True, None):
        target = tmp_path / f"count{abs(hash(str(bad)))}"
        target.mkdir()
        make_clean_tree(target)
        _write_seat_record(target, _seat_row(raw=bad))
        assert any("raw" in f for f in lint.run(target)), bad


def test_seat_row_isolated_must_be_boolean(tmp_path):
    """The field exists to make an omission visible, so a string cannot stand
    in for it — that is being absent in spirit while passing the shape check."""
    make_clean_tree(tmp_path)
    _write_seat_record(tmp_path, _seat_row(isolated="false"))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "isolated" in findings[0]


def test_seat_row_clean_status_cannot_carry_counts(tmp_path):
    make_clean_tree(tmp_path)
    _write_seat_record(tmp_path, _seat_row(status="clean", raw=3, merged=0, sustained=0))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "found nothing" in findings[0]


def test_seat_row_clean_and_failed_are_distinguishable(tmp_path):
    """Both carry zeros; the pair is lawful and tells them apart, which is the
    whole reason the file exists alongside the defect ledger."""
    make_clean_tree(tmp_path)
    _write_seat_record(
        tmp_path,
        _seat_row(seat="operational", status="clean", raw=0, merged=0, sustained=0),
        _seat_row(seat="wiring-falsifier", status="failed", raw=0, merged=0, sustained=0),
    )
    assert lint.run(tmp_path) == []


def test_seat_row_duplicate_source_seat_pair_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    _write_seat_record(tmp_path, _seat_row(), _seat_row(sustained=4))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "duplicate" in findings[0]


def test_seat_row_same_seat_different_source_is_clean(tmp_path):
    make_clean_tree(tmp_path)
    _write_seat_record(
        tmp_path, _seat_row(), _seat_row(source="pr20-panel-2026-08-18")
    )
    assert lint.run(tmp_path) == []


def test_seat_row_bad_date_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    _write_seat_record(tmp_path, _seat_row(date="2026-13-45"))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "date" in findings[0]


def test_seat_record_malformed_row_keeps_later_rows(tmp_path):
    make_clean_tree(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "seat-record.jsonl").write_text(
        "{not json\n" + json.dumps(_seat_row(status="skipped")) + "\n",
        encoding="utf-8",
    )
    findings = lint.run(tmp_path)
    assert any("not valid JSON" in f for f in findings)
    assert any("status" in f for f in findings)


def test_seat_record_trial_is_optional_and_form_checked(tmp_path):
    make_clean_tree(tmp_path)
    _write_seat_record(tmp_path, _seat_row(trial="convergence-gate"))
    assert lint.run(tmp_path) == []
    other = tmp_path / "bad"
    other.mkdir()
    make_clean_tree(other)
    _write_seat_record(other, _seat_row(trial="Convergence Gate"))
    findings = lint.run(other)
    assert len(findings) == 1 and "trial" in findings[0]


def test_seat_row_every_count_field_is_checked(tmp_path):
    """PF7: only `raw` was exercised, so narrowing the loop to ("raw",) survived
    the whole suite. Each count gets its own case."""
    make_clean_tree(tmp_path)
    for field in ("raw", "merged", "sustained"):
        target = tmp_path / f"c-{field}"
        target.mkdir()
        make_clean_tree(target)
        _write_seat_record(target, _seat_row(**{field: -1}))
        findings = lint.run(target)
        assert any(field in f and "non-negative" in f for f in findings), (field, findings)


def test_seat_row_failed_status_cannot_carry_counts(tmp_path):
    """PF8: the `failed` half of the status/counts cross-check had no case, so
    narrowing the set to {"clean"} survived."""
    make_clean_tree(tmp_path)
    _write_seat_record(tmp_path, _seat_row(status="failed", raw=3, merged=0, sustained=0))
    findings = lint.run(tmp_path)
    assert any("found nothing" in f for f in findings)


def test_seat_row_counts_must_be_nested(tmp_path):
    """PF9: the fields are defined as nested subsets and "raw minus sustained" is
    the number the file exists for; it must not be able to go negative."""
    make_clean_tree(tmp_path)
    _write_seat_record(tmp_path, _seat_row(raw=0, merged=5, sustained=99))
    findings = lint.run(tmp_path)
    assert any("not nested" in f for f in findings)


def test_seat_row_nested_equal_counts_are_clean(tmp_path):
    """The counterweight: a seat every finding of which survived is raw == merged
    == sustained, which is lawful and is what cold-read did on this review."""
    make_clean_tree(tmp_path)
    _write_seat_record(tmp_path, _seat_row(raw=12, merged=12, sustained=12))
    assert lint.run(tmp_path) == []


def test_seat_row_ran_with_zero_raw_must_be_clean(tmp_path):
    """PF10: `clean` is reserved for a zero-yield run, so allowing `ran` with a
    zero raw count gave that run two lawful encodings — the ambiguity `status`
    was added to remove, re-admitted one level down."""
    make_clean_tree(tmp_path)
    _write_seat_record(tmp_path, _seat_row(status="ran", raw=0, merged=0, sustained=0))
    findings = lint.run(tmp_path)
    assert any("is 'clean'" in f for f in findings)


def test_seat_row_source_must_be_non_empty(tmp_path):
    """PF17: `source` is the join key and half the duplicate key, so an empty one
    silently collapses every seat of every review into one bucket."""
    make_clean_tree(tmp_path)
    for bad in ("", "   ", 7, None):
        target = tmp_path / f"src{abs(hash(str(bad)))}"
        target.mkdir()
        make_clean_tree(target)
        _write_seat_record(target, _seat_row(source=bad))
        assert any("source" in f for f in lint.run(target)), bad


def test_seat_record_array_row_is_rejected_as_a_non_object(tmp_path):
    """PF16: the missing-field diff ran before anything checked the row was a
    mapping, so an array was diffed against its values and its entries were
    reported as present fields. Both checkers had the hole; both are closed."""
    make_clean_tree(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "seat-record.jsonl").write_text(
        '["source", "status"]\n' + json.dumps(_seat_row(status="skipped")) + "\n",
        encoding="utf-8",
    )
    findings = lint.run(tmp_path)
    assert any("is not a JSON object" in f for f in findings)
    assert not any("missing field" in f for f in findings)
    assert any("status" in f for f in findings)  # the later row still checked


def test_seat_record_vocabularies_are_exactly_what_the_adr_states():
    """Pins the literals so a local widening fails here even though nothing can
    read the ADR — the same stated-unenforced gap the ledger sets carry."""
    assert lint.SEAT_STATUSES == {"ran", "clean", "failed"}
    assert lint.SEAT_LANES == {"panel", "routine"}
    assert lint.SEAT_RECORD_FIELDS == {
        "source", "date", "seat", "model", "runtime",
        "lane", "raw", "merged", "sustained", "status", "isolated",
    }
    assert lint.LEDGER_DISPOSITIONS == {
        "fixed", "reworded", "recorded", "owner-pending", "filed",
    }
    # PF18: the loop targets are pinned too. Without these, narrowing either
    # tuple silently removes checks while this test keeps passing.
    assert lint.SEAT_COUNTS == ("raw", "merged", "sustained")
    assert lint.SEAT_TOKEN_FIELDS == ("seat", "model", "runtime")
    # One form rule, one definition site. This has to be checked against the
    # SOURCE, not at runtime: `re.compile` caches, so two identical patterns
    # return the same object and `LEDGER_FOUND_BY is TOKEN` holds even when the
    # duplicate has been reintroduced. An `is` assertion here passes the mutant.
    source = (Path(lint.__file__)).read_text(encoding="utf-8")
    assert source.count('re.compile(r"\\A[a-z0-9][a-z0-9-]*\\Z")') == 1, (
        "the name-token pattern has more than one definition site; the skill says "
        "these fields are tokens 'like found_by and for the same reason', so two "
        "copies would drift silently"
    )


# --- the live repo obeys its own lint --------------------------------------

def test_live_repo_is_clean():
    assert lint.run(lint.ROOT) == []

"""Tests for the packaging lint. Each fixture builds a minimal tree in
tmp_path so every check is proven to fire and to stay quiet, per check.
The evasion-form cases exist because the 2026-08-15 adversarial review
showed the original regexes missed every relative, uppercase, and
backslash form (findings M1/M2/M4/M5/M6 in docs/ledger.jsonl)."""

import json
import sys
from pathlib import Path

import pytest

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
    _wire_callout(root)


def _wire_callout(root: Path) -> None:
    """The doctrine callout, wired the way the real repo wires it."""
    tools = root / "tools"
    tools.mkdir(exist_ok=True)
    (tools / "doctrine_callout.py").write_text("# the callout\n", encoding="utf-8")
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / "ci.yml").write_text(WIRED_CI, encoding="utf-8")


WIRED_CI = (
    "on:\n"
    "  push:\n"
    "    branches: [main]\n"
    "  pull_request:\n"
    "\n"
    "jobs:\n"
    "  lint-and-test:\n"
    "    steps:\n"
    "      - if: github.event_name == 'pull_request'\n"
    "        run: python tools/check_version_bump.py\n"
    "  doctrine-callout:\n"
    "    if: github.event_name == 'pull_request'\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - run: python tools/doctrine_callout.py --pr 1\n"
)


def _ci(root: Path, text: str) -> None:
    (root / ".github" / "workflows" / "ci.yml").write_text(text, encoding="utf-8")


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


def test_review_row_report_rejects_hostless_urls(tmp_path):
    # netloc is non-empty for the userinfo and port-only forms, so the check
    # reads hostname; a malformed authority must report, never raise.
    make_clean_tree(tmp_path)
    hostless = (
        "https://",
        "https:///report",
        "https://@/report",
        "https://:443/report",
        "https://[::1/report",
    )
    for value in hostless:
        _write_index(tmp_path, _review_row(report=value))
        findings = lint.run(tmp_path)
        assert len(findings) == 1
        assert "must be an https URL" in findings[0]
    # ...and a real host still passes.
    _write_index(tmp_path, _review_row(report="https://github.com/o/r/pull/1#issuecomment-2"))
    assert lint.run(tmp_path) == []


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


def test_review_row_sustained_may_exceed_merged(tmp_path):
    """A seat entry the merge did not carry can still be sustained [D-102].

    Red against the pre-fix revision, where `merged >= sustained` was enforced.
    """
    make_clean_tree(tmp_path)
    # PR #90's own shape: revision-diff filed 7, the merge carried 6, and the
    # seventh was sustained as an uncarried docket entry.
    _write_index(
        tmp_path,
        _review_row(seats={"cold-read": {"raw": 7, "merged": 6, "sustained": 7, "high": 1}}),
    )
    assert lint.run(tmp_path) == []
    # The other polarity: what the invariant still has to catch.
    # A zero-finding seat with one sustained declined examination: raw 0,
    # sustained 1. D-102 makes this the normal shape, not an edge case.
    _write_index(
        tmp_path,
        _review_row(seats={"cold-read": {"raw": 0, "merged": 0, "sustained": 1, "high": 0}}),
    )
    assert lint.run(tmp_path) == []
    # The other polarity: what the invariant still has to catch.
    for counts in (
        {"raw": 3, "merged": 4, "sustained": 0, "high": 0},  # merged > raw
        {"raw": 3, "merged": 3, "sustained": 1, "high": 2},  # high > sustained
    ):
        _write_index(tmp_path, _review_row(seats={"cold-read": counts}))
        findings = lint.run(tmp_path)
        assert len(findings) == 1 and "not nested" in findings[0], counts


def test_review_row_seat_counts_wrong_shape_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _review_row(seats={"cold-read": 7}))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "must be a mapping" in findings[0]


def test_doctrine_callout_wired_is_not_a_finding(tmp_path):
    """The lawful polarity: a guard that blocks lawful work fails as hard as
    one that passes unlawful work."""
    make_clean_tree(tmp_path)
    assert lint.run(tmp_path) == []


def test_deleting_the_callout_job_is_a_finding(tmp_path):
    """The callout cannot catch its own removal — a PR deleting the job touches
    no doctrine file, so nothing fires and nothing goes red. This is what makes
    such a PR fail a required check instead."""
    make_clean_tree(tmp_path)
    _ci(tmp_path, "on:\n  pull_request:\n\njobs:\n  lint-and-test:\n"
                  "    steps:\n      - run: python tools/lint.py\n")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "no live `doctrine-callout:` job" in findings[0]


# Every way the callout has been made dead without deleting anything. Each was
# measured against a plain substring check first, and each passed it clean —
# which is why the check reads the job's own block rather than the file.
@pytest.mark.parametrize("name, mutate, expected", [
    ("job commented out",
     lambda t: "".join("#" + ln if ln.startswith("  doctrine-callout:")
                       or ln.startswith("    ") and "doctrine_callout" in ln
                       else ln for ln in t.splitlines(keepends=True)),
     "no live `doctrine-callout:` job"),
    ("gate falsified",
     lambda t: t.replace("  doctrine-callout:\n    if: github.event_name == 'pull_request'",
                         "  doctrine-callout:\n    if: false"),
     "not gated on a pull_request event"),
    ("gate deleted",
     lambda t: t.replace("  doctrine-callout:\n    if: github.event_name == 'pull_request'\n",
                         "  doctrine-callout:\n"),
     "not gated on a pull_request event"),
    ("script call neutered",
     lambda t: t.replace("run: python tools/doctrine_callout.py",
                         "run: echo python tools/doctrine_callout.py"),
     "does not run tools/doctrine_callout.py"),
    ("trigger removed",
     lambda t: t.replace("  pull_request:\n", "", 1),
     "no `pull_request:` trigger"),
    # The escape the review found last: the job's gate no longer matches the
    # event, so it skips in silence while both required checks report green —
    # and checkout would default to the base branch, testing main rather than
    # the PR. The likeliest motive is already on the record (fork coverage).
    ("trigger switched to pull_request_target",
     lambda t: t.replace("  pull_request:\n", "  pull_request_target:\n", 1),
     "no `pull_request:` trigger"),
])
def test_a_dead_callout_job_is_a_finding(tmp_path, name, mutate, expected):
    make_clean_tree(tmp_path)
    _ci(tmp_path, mutate(WIRED_CI))
    findings = lint.run(tmp_path)
    assert any(expected in f for f in findings), f"{name}: {findings}"


# The lawful polarity. A guard that blocks lawful work fails as hard as one
# that passes unlawful work, so the gate's event is named and its wording is not.
@pytest.mark.parametrize("rewrite", [
    lambda t: t.replace("    if: github.event_name == 'pull_request'\n    runs-on",
                        "    if: ${{ github.event_name == 'pull_request' }}\n    runs-on"),
    lambda t: t.replace("    if: github.event_name == 'pull_request'\n    runs-on",
                        "    if: github.event_name == 'pull_request'"
                        " && !github.event.pull_request.draft\n    runs-on"),
    lambda t: t.replace("--pr 1", "--repo o/n --pr 1"),
    lambda t: t.replace("  pull_request:\n", "  pull_request:  \n", 1),   # trailing space
    lambda t: t.replace("on:\n  push:\n    branches: [main]\n  pull_request:\n",
                        "on: [push, pull_request]\n", 1),                 # flow style
    lambda t: t.replace("  pull_request:\n", "  - pull_request\n", 1),    # sequence form
])
def test_lawful_rewordings_of_the_job_pass(tmp_path, rewrite):
    make_clean_tree(tmp_path)
    _ci(tmp_path, rewrite(WIRED_CI))
    assert lint.run(tmp_path) == []


def test_deleting_the_callout_script_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "tools" / "doctrine_callout.py").unlink()
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "doctrine_callout.py is missing" in findings[0]


def test_a_missing_workflow_file_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / ".github" / "workflows" / "ci.yml").unlink()
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "ci.yml is missing" in findings[0]


def test_frozen_archive_files_are_not_validated(tmp_path):
    # The pre-reset records are history: a malformed line in them is not a
    # lint finding, because nothing appends to them anymore (D-74).
    make_clean_tree(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "ledger.jsonl").write_text("{not json\n", encoding="utf-8")
    (docs / "seat-record.jsonl").write_text("{not json\n", encoding="utf-8")
    assert lint.run(tmp_path) == []


def test_zone_wall_fires_on_relative_dot_leading_repo_only_name(tmp_path):
    # `.github` is the one repo-only name that starts with a dot. Every relative
    # form of it slipped the wall until 2026-08-22: the class after the ../
    # prefix required a word character, and a dot is not one.
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    (skill / "SKILL.md").write_text(
        "[ci](../../.github/workflows/ci.yml)\n"
        "See ../../.github/workflows/ci.yml too.\n"
        "Or ..\\..\\.github\\workflows\\ci.yml.\n",
        encoding="utf-8",
    )
    findings = [f for f in lint.run(tmp_path) if "zone-wall" in f]
    assert len(findings) == 3, findings


def test_zone_wall_ignores_relative_dot_leading_path_that_is_not_repo_only(tmp_path):
    # The lawful polarity of the same fix: a dot-leading first segment that is
    # not a repo-only name must still pass, or the guard blocks lawful work.
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    (skill / "SKILL.md").write_text(
        "See ../.config/settings.json and ./.cache/notes.md.\n", encoding="utf-8"
    )
    assert [f for f in lint.run(tmp_path) if "zone-wall" in f] == []


def test_zone_wall_ignores_suffix_match_inside_a_longer_relative_token(tmp_path):
    # `assets/../../docs/x.md` resolves to skills/example-skill/docs/x.md, which
    # is the skill's own subdir and lawful. Matching only the `../../docs/x.md`
    # tail resolved it from the wrong base and reported a repo-only hit, for all
    # three repo-only names. Found by the external pass on 2026-08-22.
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    (skill / "SKILL.md").write_text(
        "See assets/../../.github/workflows/ci.yml.\n"
        "See assets/../../docs/architecture/README.md.\n"
        "See assets/../../tools/lint.py.\n"
        "See [x](assets/../../.github/workflows/ci.yml).\n"
        "See assets\\..\\..\\.github\\ci.yml.\n"
        "See a.b/../../docs/x.md.\n",
        encoding="utf-8",
    )
    assert [f for f in lint.run(tmp_path) if "zone-wall" in f] == []


def test_sideways_dep_ignores_suffix_match_inside_a_longer_relative_token(tmp_path):
    # RELATIVE_REF is shared with check_sideways_deps, so the same suffix match
    # reached both guards; the lawful polarity has to be pinned on both.
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    (skill / "SKILL.md").write_text(
        "See assets/../beta-skill/SKILL.md.\n", encoding="utf-8"
    )
    assert [f for f in lint.run(tmp_path) if "sideways-dep" in f] == []


def _decisions(tmp_path, entries, rows):
    """Build a decision log with `entries` files and `rows` index rows."""
    directory = tmp_path / "docs" / "architecture" / "decisions"
    directory.mkdir(parents=True)
    for name in entries:
        (directory / name).write_text("# entry\n", encoding="utf-8")
    if rows is not None:
        body = "| Entry | Decision |\n| --- | --- |\n" + "".join(
            f"| [{label}]({target}) | why |\n" for label, target in rows
        )
        (directory / "README.md").write_text(body, encoding="utf-8")
    return directory


def test_decision_index_clean_tree_is_silent(tmp_path):
    _decisions(
        tmp_path,
        ["D-1-2026-01-01-a.md"],
        [("D-1", "D-1-2026-01-01-a.md")],
    )
    assert lint.check_decision_index(tmp_path) == []


def test_decision_index_flags_entry_with_no_row(tmp_path):
    _decisions(tmp_path, ["D-1-2026-01-01-a.md", "D-2-2026-01-02-b.md"], [("D-1", "D-1-2026-01-01-a.md")])
    findings = lint.check_decision_index(tmp_path)
    assert len(findings) == 1
    assert "D-2-2026-01-02-b.md" in findings[0]
    assert "no row" in findings[0]


def test_decision_index_flags_row_with_no_entry(tmp_path):
    _decisions(
        tmp_path,
        ["D-1-2026-01-01-a.md"],
        [("D-1", "D-1-2026-01-01-a.md"), ("D-9", "D-9-2026-01-09-ghost.md")],
    )
    findings = lint.check_decision_index(tmp_path)
    assert len(findings) == 1
    assert "D-9-2026-01-09-ghost.md" in findings[0]
    assert "does not exist" in findings[0]


def test_decision_index_absent_is_clean(tmp_path):
    """No index is the same silence check_review_index keeps for its own record.

    Recorded as intended rather than left to be rediscovered: the defect this
    guard closes is a missing *row* written by a landing PR, not a deleted log.
    """
    _decisions(tmp_path, ["D-1-2026-01-01-a.md"], None)
    assert lint.check_decision_index(tmp_path) == []


# --- entry references ------------------------------------------------------

def _write_entry(root: Path, name: str, body: str) -> None:
    """A decision entry plus the index row check_decision_index requires, so
    these tests exercise the reference guard rather than the index one."""
    directory = root / "docs" / "architecture" / "decisions"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(body, encoding="utf-8")
    index = directory / "README.md"
    rows = index.read_text(encoding="utf-8") if index.is_file() else ""
    index.write_text(f"{rows}| [D-1]({name}) | a decision |\n", encoding="utf-8")


def test_entry_reference_that_resolves_is_clean(tmp_path):
    make_clean_tree(tmp_path)
    _write_entry(
        tmp_path, "D-1-2026-08-23-x.md",
        "It moved to `skills/example-skill/SKILL.md`.\n",
    )
    assert lint.run(tmp_path) == []


def test_entry_reference_that_resolves_to_nothing_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    _write_entry(tmp_path, "D-1-2026-08-23-x.md", "See `skills/gone/SKILL.md` for it.\n")
    findings = [f for f in lint.run(tmp_path) if "entry-reference" in f]
    assert len(findings) == 1
    assert "skills/gone/SKILL.md" in findings[0]
    assert "D-1-2026-08-23-x.md:1" in findings[0]


def test_entry_reference_pinned_to_a_commit_is_clean(tmp_path):
    """A pin names the commit the reference shipped at, so no later move can
    falsify it — the one lawful way to cite a file an entry quotes."""
    make_clean_tree(tmp_path)
    _write_entry(
        tmp_path, "D-1-2026-08-23-x.md",
        "The rule as it shipped is `skills/gone/SKILL.md:30` at `65c4540`.\n",
    )
    assert [f for f in lint.run(tmp_path) if "entry-reference" in f] == []


def test_entry_dead_markdown_link_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    _write_entry(tmp_path, "D-1-2026-08-23-x.md", "See [evidence](../evidence.md).\n")
    findings = [f for f in lint.run(tmp_path) if "entry-reference" in f]
    assert len(findings) == 1 and "../evidence.md" in findings[0]


def test_entry_reference_web_url_and_bare_filename_are_not_references(tmp_path):
    """A bare filename names a thing in prose and claims nothing about where it
    lives, so there is nothing to repoint; a web URL resolves for consumers."""
    make_clean_tree(tmp_path)
    _write_entry(
        tmp_path, "D-1-2026-08-23-x.md",
        "`SKILL.md` retires, per [#70](https://github.com/x/y/issues/70).\n",
    )
    assert [f for f in lint.run(tmp_path) if "entry-reference" in f] == []


def test_entry_reference_resolves_under_skills_shorthand(tmp_path):
    """Entries write the skills-relative shorthand routinely; a guard failing it
    would report a reference a reader follows without trouble."""
    make_clean_tree(tmp_path)
    _write_entry(
        tmp_path, "D-1-2026-08-23-x.md",
        "The table cites `example-skill/SKILL.md`.\n",
    )
    assert [f for f in lint.run(tmp_path) if "entry-reference" in f] == []


def test_entry_reference_below_the_first_line_is_found(tmp_path):
    """Every reference this guard exists to catch lives deep in a long entry.
    A scan that stopped after line 1 passed both the suite and CI, because the
    fixtures were all one-liners and nothing runs the lint against a tree that
    is supposed to produce findings."""
    make_clean_tree(tmp_path)
    _write_entry(
        tmp_path, "D-1-2026-08-23-x.md",
        "First line, nothing here.\n\nStill nothing.\n\nSee `skills/gone/SKILL.md`.\n",
    )
    findings = [f for f in lint.run(tmp_path) if "entry-reference" in f]
    assert len(findings) == 1
    assert "D-1-2026-08-23-x.md:5" in findings[0]


def test_entry_reference_recorded_as_unrepairable_is_silent(tmp_path, monkeypatch):
    """The third and fourth lawful forms. Without a pin on this branch the
    whole recorded-reference path was exercised only by the repo-level run."""
    make_clean_tree(tmp_path)
    _write_entry(tmp_path, "D-1-2026-08-23-x.md", "See `skills/gone/SKILL.md`.\n")
    key = ("D-1-2026-08-23-x.md", 1, "skills/gone/SKILL.md")
    monkeypatch.setattr(lint, "BASELINE_UNRESOLVABLE", {key: "target retired"})
    assert [f for f in lint.run(tmp_path) if "entry-reference" in f] == []


def test_recorded_reference_without_a_reason_is_a_finding(tmp_path, monkeypatch):
    """A row with no reason is the exemption list the baseline exists not to be."""
    make_clean_tree(tmp_path)
    _write_entry(tmp_path, "D-1-2026-08-23-x.md", "See `skills/gone/SKILL.md`.\n")
    key = ("D-1-2026-08-23-x.md", 1, "skills/gone/SKILL.md")
    monkeypatch.setattr(lint, "UNREPAIRABLE_AFTER_LANDING", {key: "  "})
    findings = [f for f in lint.run(tmp_path) if "has no reason" in f]
    assert len(findings) == 1


def test_recorded_reference_that_resolves_again_is_a_finding(tmp_path, monkeypatch):
    """This is what makes 'may only shrink' a mechanism rather than a comment:
    a row whose reference came back to life is reported until it is removed."""
    make_clean_tree(tmp_path)
    _write_entry(
        tmp_path, "D-1-2026-08-23-x.md", "See `skills/example-skill/SKILL.md`.\n"
    )
    key = ("D-1-2026-08-23-x.md", 1, "skills/example-skill/SKILL.md")
    monkeypatch.setattr(lint, "BASELINE_UNRESOLVABLE", {key: "was dead once"})
    findings = [f for f in lint.run(tmp_path) if "resolves again" in f]
    assert len(findings) == 1


def test_entry_reference_pin_is_scoped_to_its_own_reference(tmp_path):
    """A pin covers the reference it follows and no other. Computed per line, a
    single pin exempted a whole paragraph — and one line in the real log
    already carried a pin alongside three references."""
    make_clean_tree(tmp_path)
    _write_entry(
        tmp_path, "D-1-2026-08-23-x.md",
        "Shipped as `skills/gone/SKILL.md` at `65c4540`; see `skills/other/SKILL.md`.\n",
    )
    findings = [f for f in lint.run(tmp_path) if "entry-reference" in f]
    assert len(findings) == 1
    assert "skills/other/SKILL.md" in findings[0]


def test_entry_reference_ordinary_prose_is_not_a_path(tmp_path):
    """`A/B` is this repo's own name for its spike pattern. A guard that reds it
    blocks lawful work and teaches authors to write references less precisely,
    which degrades the entries the guard exists to protect."""
    make_clean_tree(tmp_path)
    _write_entry(
        tmp_path, "D-1-2026-08-23-x.md",
        "A cold-seat `A/B` run, `CI/CD` green, `2/3` seats agreed, `n/a`.\n",
    )
    assert [f for f in lint.run(tmp_path) if "entry-reference" in f] == []


def test_entry_reference_directory_named_like_an_entry_does_not_crash(tmp_path):
    """A traceback is a worse signal than a finding, and it took the other six
    checks down with it."""
    make_clean_tree(tmp_path)
    _write_entry(tmp_path, "D-1-2026-08-23-x.md", "Nothing here.\n")
    (tmp_path / "docs" / "architecture" / "decisions" / "D-2-2026-08-23-y.md").mkdir()
    lint.run(tmp_path)  # must not raise


def test_baseline_of_unrepairable_references_may_only_shrink():
    """A baseline row is a dead reference nobody had to repair — the failure
    this guard exists to make impossible. Membership is pinned, not size: a
    same-size swap that retired one row and admitted a fresh dead reference
    passed a length assertion silently."""
    assert set(lint.BASELINE_UNRESOLVABLE) == {
        ("D-102-2026-08-21-merged-list-is-an-index.md", 50, "skills/authoring/references/spikes.md"),
        ("D-104-2026-08-22-engagement-cell.md", 36, "engagement/references/spikes.md"),
        ("D-119-2026-08-23-cost-estimate-outside-the-artifact.md", 19, "skills/engagement/references/spikes.md"),
        ("D-132-2026-08-23-spikes-graduate.md", 19, "engagement/references/spikes.md"),
        ("D-53-2026-08-18-log-and-statute.md", 15, "docs/architecture/constitution.md"),
        ("D-53-2026-08-18-log-and-statute.md", 64, "tools/check_constitution.py"),
        ("D-53-2026-08-18-log-and-statute.md", 64, "tools/tests/test_check_constitution.py"),
        ("D-53-2026-08-18-log-and-statute.md", 75, "docs/architecture/evidence.md"),
        ("D-69-2026-08-18-trial-instrument-and-exception.md", 19, "../evidence.md"),
        ("D-69-2026-08-18-trial-instrument-and-exception.md", 94, "../evidence.md"),
        ("D-80-2026-08-19-spikes.md", 15, "skills/authoring/references/spikes.md"),
        ("D-90-2026-08-20-dispatch-contract.md", 25, "Documents/Design/review-dispatch-overhead-measurement.md"),
    }
    assert all(str(r).strip() for r in lint.BASELINE_UNRESOLVABLE.values())


def test_declared_repo_roots_cover_every_shipped_dir():
    """The shape filter's first-segment test is 'a root this repo declares'.
    `.claude-plugin` was declared, real, and missing, so a reference rooted
    there was invisible."""
    assert set(lint.SHIPPED_DIRS) <= lint.REPO_ROOTS


def test_untracked_directory_does_not_change_the_answer(tmp_path):
    """`python tools/lint.py` is mandatory before every commit, so it may not
    answer differently because a session happened to create an untracked
    directory. `.claude` was in the root set while being untracked and
    ungitignored, which gave the same commit two answers."""
    assert ".claude" not in lint.REPO_ROOTS
    assert not lint._is_reference_shaped(".claude/agents")


def test_recorded_row_in_the_growable_set_is_silent(tmp_path, monkeypatch):
    """The fourth lawful form, and this batch's headline mechanism. Deleting
    its arm from the guard passed both gates while nothing asserted it."""
    make_clean_tree(tmp_path)
    _write_entry(tmp_path, "D-1-2026-08-23-x.md", "See `skills/gone/SKILL.md`.\n")
    key = ("D-1-2026-08-23-x.md", 1, "skills/gone/SKILL.md")
    monkeypatch.setattr(lint, "BASELINE_UNRESOLVABLE", {})
    monkeypatch.setattr(
        lint, "UNREPAIRABLE_AFTER_LANDING", {key: "target retired by this change"}
    )
    assert [f for f in lint.run(tmp_path) if "entry-reference" in f] == []


def test_reference_escaping_the_repository_does_not_resolve(tmp_path):
    """A sibling worktree exists locally and not in CI, so a guard that
    resolved through it would answer differently in the two places."""
    make_clean_tree(tmp_path)
    outside = tmp_path.parent / "outside-the-repo.md"
    outside.write_text("x\n", encoding="utf-8")
    _write_entry(
        tmp_path, "D-1-2026-08-23-x.md", "See `../outside-the-repo.md`.\n"
    )
    findings = [f for f in lint.run(tmp_path) if "entry-reference" in f]
    assert len(findings) == 1


def test_backslashed_reference_is_seen(tmp_path):
    """Every other pattern in the module accepts either separator; the newest
    one did not, so a Windows-authored entry opted out of the guard."""
    make_clean_tree(tmp_path)
    _write_entry(tmp_path, "D-1-2026-08-23-x.md", "See `skills\\gone\\SKILL.md`.\n")
    findings = [f for f in lint.run(tmp_path) if "entry-reference" in f]
    assert len(findings) == 1


def test_titled_markdown_link_is_seen(tmp_path):
    """`[x](path "title")` is ordinary markdown and was invisible."""
    make_clean_tree(tmp_path)
    _write_entry(
        tmp_path, "D-1-2026-08-23-x.md", 'See [x](../gone.md "the registry").\n'
    )
    findings = [f for f in lint.run(tmp_path) if "entry-reference" in f]
    assert len(findings) == 1


def test_the_log_index_is_scanned_too(tmp_path):
    """The index carries references of its own, and unlike an entry it is
    editable, so its repair has an obvious home."""
    make_clean_tree(tmp_path)
    _write_entry(tmp_path, "D-1-2026-08-23-x.md", "Nothing here.\n")
    index = tmp_path / "docs" / "architecture" / "decisions" / "README.md"
    index.write_text(
        index.read_text(encoding="utf-8") + "\nSee `skills/gone/SKILL.md`.\n",
        encoding="utf-8",
    )
    findings = [f for f in lint.run(tmp_path) if "entry-reference" in f]
    assert len(findings) == 1 and "README.md" in findings[0]


def test_a_pin_does_not_reach_past_the_next_reference(tmp_path):
    """The window is bounded by the next match's own start. Reconstructing that
    start by subtracting the reference's length is exact only when the match
    text is the reference — for `[display](target)` it is not, and the window
    swallowed the following link's anchor text."""
    make_clean_tree(tmp_path)
    line = "See `skills/gone/SKILL.md` and [the rule at `65c4540`](../also-gone.md).\n"
    _write_entry(tmp_path, "D-1-2026-08-23-x.md", line)
    findings = [f for f in lint.run(tmp_path) if "entry-reference" in f]
    assert len(findings) == 2


def test_a_pin_in_its_natural_position_still_holds(tmp_path):
    """The counterpart to the test above: narrowing the window must not stop a
    pin covering the reference it actually follows."""
    make_clean_tree(tmp_path)
    _write_entry(
        tmp_path, "D-1-2026-08-23-x.md",
        "Shipped as `skills/gone/SKILL.md` at `65c4540`.\n",
    )
    assert [f for f in lint.run(tmp_path) if "entry-reference" in f] == []


def test_an_all_decimal_short_sha_is_a_pin(tmp_path):
    """Refusing a hex run without a letter refused about one short sha in
    twenty-seven, and the author who wrote one got a silently inert pin. The
    backticks carry the discrimination: the live comment-id case is
    unbackticked."""
    make_clean_tree(tmp_path)
    _write_entry(
        tmp_path, "D-1-2026-08-23-x.md",
        "Shipped as `skills/gone/SKILL.md` at `1234567`.\n",
    )
    assert [f for f in lint.run(tmp_path) if "entry-reference" in f] == []
    assert lint.PINNED_REF.search("at 5380976787") is None


# --- review row: dispositions and staffing ------------------------------


def _row_with_extras(**overrides):
    row = _review_row(date="2026-08-24")
    row["dispositions"] = {"fixed": 3, "routed": 1, "priced_out": 2, "dismissed": 0}
    row["staffing"] = {"model": "Opus 5", "runtime": "Claude Code (Windows)"}
    row.update(overrides)
    return row


def test_row_carrying_dispositions_and_staffing_is_clean(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _row_with_extras())
    assert lint.run(tmp_path) == []


def test_row_on_or_after_the_cutoff_must_carry_both(tmp_path):
    """An optional field can never catch its own omission, and a record that
    silently fails to carry what it promises is the defect this closes."""
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _review_row(date="2026-08-24"))
    findings = lint.run(tmp_path)
    assert len(findings) == 2
    assert any("dispositions" in f for f in findings)
    assert any("staffing" in f for f in findings)


def test_row_before_the_cutoff_needs_neither(tmp_path):
    """Forward-only in fact, not merely in intent: rows already written stay
    valid untouched, including the ones dated the day this landed."""
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _review_row(date="2026-08-23"))
    assert lint.run(tmp_path) == []


def test_disposition_counts_reject_bools_and_negatives(tmp_path):
    """The bar the seat counts already meet: bool subclasses int, so True
    would otherwise pass as a count of one."""
    make_clean_tree(tmp_path)
    row = _row_with_extras()
    row["dispositions"] = {**row["dispositions"], "fixed": True, "routed": -1}
    _write_index(tmp_path, row)
    findings = lint.run(tmp_path)
    assert len(findings) == 2 and all("non-negative integer" in f for f in findings)


def test_dispositions_missing_a_key_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    row = _row_with_extras()
    del row["dispositions"]["dismissed"]
    _write_index(tmp_path, row)
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "dismissed" in findings[0]


def test_dispositions_reject_a_vocabulary_outside_the_terminal_stage(tmp_path):
    """The four are the terminal stage's own. A row inventing a fifth is
    recording something the ruling never produced."""
    make_clean_tree(tmp_path)
    row = _row_with_extras()
    row["dispositions"] = {**row["dispositions"], "dropped": 1}
    _write_index(tmp_path, row)
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "unknown key" in findings[0]


def test_staffing_requires_both_names_and_constrains_neither(tmp_path):
    """No vocabulary: a fixed list would need amending before the first review
    staffed by a new runtime could be recorded at all."""
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _row_with_extras(
        staffing={"model": "some-future-model", "runtime": "some-future-runtime"}
    ))
    assert lint.run(tmp_path) == []
    _write_index(tmp_path, _row_with_extras(staffing={"model": "Opus 5", "runtime": "  "}))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "runtime" in findings[0]


def test_every_row_already_in_the_repo_index_stays_valid(tmp_path):
    """Acceptance criterion 2, checked against the real file rather than a
    fixture: this change may not edit a single landed row."""
    real = Path(__file__).resolve().parents[2] / "docs" / "reviews.jsonl"
    rows = [json.loads(l) for l in real.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert rows, "the real index should not be empty"
    findings = []
    for row in rows:
        lint._check_review_row(row, "row", findings)
    assert findings == []

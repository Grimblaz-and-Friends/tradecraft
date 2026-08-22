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
        "Or ..\..\.github\workflows\ci.yml.\n",
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

"""Tests for the packaging lint. Each fixture builds a minimal tree in
tmp_path so every check is proven to fire and to stay quiet, per check.
The evasion-form cases exist because the 2026-08-15 adversarial review
showed the original regexes missed every relative, uppercase, and
backslash form (findings M1/M2/M4/M5/M6 in docs/ledger.jsonl)."""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lint
import roster


import importlib.util as _ilu

NL = chr(10)
_spec = _ilu.spec_from_file_location(
    "emit_charter",
    Path(__file__).resolve().parents[2] / "hooks" / "emit_charter.py",
)
emit_charter = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(emit_charter)


def _write_cell(skill: Path, body: str) -> None:
    """Write a cell body under valid frontmatter.

    Every cell needs a parseable name and description now -- the runtime indexes
    those and nothing else until the cell fires, and a cell without them loads
    with empty metadata. The fixtures exercise body content, so the header is
    boilerplate here; it is not boilerplate in the tree.
    """
    (skill / "SKILL.md").write_text(
        "---" + NL + f"name: {skill.name}" + NL
        + "description: A fixture cell." + NL + "---" + NL + NL + body,
        encoding="utf-8",
    )
    # A cell without its roster entry is an unlawful tree, so writing one here
    # keeps every other check's fixture about that check. The roster guard is
    # proven by its own tests, which build the unlawful shapes deliberately.
    roster.write(skill.parents[1])


def make_clean_tree(root: Path) -> None:
    (root / "AGENTS.md").write_text(
        "# root" + chr(10) + "@skills/charter/SKILL.md" + chr(10)
        + "Doctrine pointer lives beside this file." + chr(10),
        encoding="utf-8",
    )
    (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    skill = root / "skills" / "example-skill"
    (skill / "references").mkdir(parents=True)
    # The pointer's target exists, because a pointer at nothing is now a
    # finding -- the fixture has to model a conforming cell, not merely a
    # cell whose prose mentions a path.
    (skill / "references" / "detail.md").write_text("Depth.\n", encoding="utf-8")
    _write_cell(skill, "# example-skill\nDepth lives in references/detail.md within skills/example-skill/.\n")
    _wire_callout(root)
    _wire_delivery(root)
    # A conforming tree carries the roster its cells generate, for the same
    # reason the pointer above has a target: the fixture models a lawful tree,
    # not one whose parts merely exist. Generated rather than hand-written, so
    # a fixture cell added later is covered by regenerating rather than by
    # remembering what the entry looks like.
    roster.write(root)


def _wire_delivery(root: Path) -> None:
    """The charter and the hook that emits it, wired the way the repo wires them."""
    charter = root / "skills" / "charter"
    charter.mkdir(parents=True, exist_ok=True)
    (charter / "SKILL.md").write_text(
        "---" + chr(10) + "name: charter" + chr(10)
        + "description: The binding rules." + chr(10) + "---" + chr(10) + chr(10)
        + "# charter" + chr(10) + "The binding half." + chr(10),
        encoding="utf-8",
    )
    hooks = root / "hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "emit_charter.py").write_text("# the emitter\n", encoding="utf-8")
    (hooks / "hooks.json").write_text(
        '{"hooks": {"SessionStart": [{"matcher": "*", "hooks": [{"type": '
        '"command", "command": "python ${CLAUDE_PLUGIN_ROOT}/hooks/emit_charter.py"'
        '}]}]}}\n',
        encoding="utf-8",
    )


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
    "      - uses: actions/checkout@v5\n"
    "        with:\n"
    "          fetch-depth: 0\n"
    "      - env:\n"
    "          BASE_SHA: xyz\n"
    "        run: python tools/doctrine_callout.py --pr 1 --base $BASE_SHA\n"
)


def _ci(root: Path, text: str) -> None:
    (root / ".github" / "workflows" / "ci.yml").write_text(text, encoding="utf-8")


def test_clean_tree_passes(tmp_path):
    make_clean_tree(tmp_path)
    assert lint.run(tmp_path) == []


# --- zone wall -------------------------------------------------------------

def test_delivery_fires_when_the_charter_is_missing(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "skills" / "charter" / "SKILL.md").unlink()
    findings = lint.run(tmp_path)
    assert any("delivery" in f and "missing" in f for f in findings)
    # The import guard fires too, and should: AGENTS.md now names a file
    # that is not there. Two guards, one cause, both worth hearing.
    assert any("doctrine-import" in f for f in findings)


def test_delivery_fires_when_the_charter_is_empty(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "skills" / "charter" / "SKILL.md").write_text("\n\n", encoding="utf-8")
    findings = lint.run(tmp_path)
    # Two guards, one cause: no body to deliver, and no header to index by.
    assert any("delivery" in f and "no body" in f for f in findings)
    assert any("cell-frontmatter" in f for f in findings)


def test_delivery_fires_when_the_hook_config_is_missing(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "hooks" / "hooks.json").unlink()
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "delivers the charter" in findings[0]


def test_delivery_fires_when_the_hook_config_does_not_parse(tmp_path):
    """A malformed hooks.json costs the adopter the skills too, not just the
    charter -- the vendor's own validator calls it breaking the entire plugin
    load -- and `claude plugin validate` cannot see it from a marketplace root."""
    make_clean_tree(tmp_path)
    (tmp_path / "hooks" / "hooks.json").write_text("{ nope", encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "does not parse" in findings[0]


def test_delivery_fires_when_no_session_start_command_is_declared(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "hooks" / "hooks.json").write_text(
        '{"hooks": {"SessionStop": []}}\n', encoding="utf-8"
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "no runnable SessionStart" in findings[0]


def test_delivery_fires_when_the_hook_names_a_path_that_is_not_there(tmp_path):
    """The typo case: the file exists, the config parses, the path is wrong."""
    make_clean_tree(tmp_path)
    (tmp_path / "hooks" / "hooks.json").write_text(
        '{"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": '
        '"python ${CLAUDE_PLUGIN_ROOT}/hooks/emit_chartr.py"}]}]}}\n',
        encoding="utf-8",
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "emit_chartr.py" in findings[0]


def test_delivery_stays_quiet_on_a_wired_tree(tmp_path):
    make_clean_tree(tmp_path)
    assert lint.run(tmp_path) == []


def test_harness_token_fires_on_powershell_and_cmd_spellings_any_case(tmp_path):
    """`$env:` and `%VAR%` are case-insensitive in the shells that read them.

    The first widening matched `$[Ee]nv:` only, so `$ENV:` -- an ordinary
    spelling on the platform half of CI runs on -- slipped both guards.
    """
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "python $ENV:CLAUDE_PLUGIN_ROOT/scripts/run.py" + chr(10)
        + "python $eNv:CLAUDE_PLUGIN_ROOT/scripts/run.py" + chr(10)
        + "python %claude_plugin_root%/scripts/run.py" + chr(10))
    findings = [f for f in lint.run(tmp_path) if "harness-token" in f]
    assert len(findings) == 3


def test_harness_token_case_insensitivity_does_not_reach_the_posix_form(tmp_path):
    """`${VAR}` is case-sensitive in POSIX shells, so a blanket flag would
    fire on a genuinely different lowercase name."""
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "python ${claude_plugin_root}/scripts/run.py" + chr(10))
    assert [f for f in lint.run(tmp_path) if "harness-token" in f] == []


def test_harness_token_covers_the_other_path_roots(tmp_path):
    """Only path roots belong here: a variable that names a port or an
    entrypoint cannot make a calling contract non-portable."""
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "python ${CLAUDE_CONFIG_DIR}/scripts/run.py" + chr(10)
        + "python $CLAUDE_WORKING_DIR/scripts/run.py" + chr(10))
    findings = [f for f in lint.run(tmp_path) if "harness-token" in f]
    assert len(findings) == 2


def test_doctrine_import_fires_when_agents_md_stops_importing_the_charter(tmp_path):
    make_clean_tree(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8").replace("@skills/charter/SKILL.md" + chr(10), ""),
        encoding="utf-8",
    )
    findings = [f for f in lint.run(tmp_path) if "doctrine-import" in f]
    assert len(findings) == 1


def test_doctrine_import_fires_on_a_backticked_mention(tmp_path):
    """A backticked path is prose. It imports nothing, which is the whole
    reason CLAUDE.md's own guard checks by position."""
    make_clean_tree(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8").replace(
            "@skills/charter/SKILL.md", "`@skills/charter/SKILL.md`"
        ),
        encoding="utf-8",
    )
    findings = [f for f in lint.run(tmp_path) if "doctrine-import" in f]
    assert len(findings) == 1


def test_doctrine_budget_fires_when_the_charter_bloats(tmp_path):
    """The charter needs the displacement pressure more than AGENTS.md does:
    an adopter pays for it on every SessionStart event, resume included."""
    make_clean_tree(tmp_path)
    (tmp_path / "skills" / "charter" / "SKILL.md").write_text(
        "x" * (lint.CHARTER_BUDGET_CHARS + 1), encoding="utf-8"
    )
    findings = [f for f in lint.run(tmp_path) if "doctrine-budget" in f]
    assert len(findings) == 1 and "charter" in findings[0]


def test_sideways_deps_reaches_the_charter_and_the_hooks(tmp_path):
    """A skill named by path from `charter/` does not resolve once installed --
    the skills live in a plugin cache, not at `skills/` beside the reader."""
    make_clean_tree(tmp_path)
    (tmp_path / "skills" / "charter" / "SKILL.md").write_text(
        "The bar lives in skills/example-skill/SKILL.md." + chr(10), encoding="utf-8"
    )
    findings = [f for f in lint.run(tmp_path) if "sideways" in f]
    assert len(findings) == 1


def test_the_two_shipped_zone_declarations_agree():
    """`check_version_bump` keeps its own copy, deliberately -- but a copy that
    silently disagrees is how `charter/` and `hooks/` came to be in the zone
    everywhere except the guard that demands a version bump for them."""
    import check_version_bump

    lint_zone = {name.rstrip("/") for name in lint.SHIPPED_DIRS}
    bump_zone = {name.rstrip("/") for name in check_version_bump.SHIPPED}
    assert lint_zone == bump_zone, (
        "the shipped zone is declared twice and the two disagree: "
        f"lint-only={sorted(lint_zone - bump_zone)}, "
        f"version-bump-only={sorted(bump_zone - lint_zone)}"
    )


def test_doctrine_import_fires_on_a_fenced_mention(tmp_path):
    """A fenced import is displayed, not performed -- the same premise the
    backticked case rests on, and the guard once caught only one of them."""
    make_clean_tree(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8").replace(
            "@skills/charter/SKILL.md",
            "```" + chr(10) + "@skills/charter/SKILL.md" + chr(10) + "```",
        ),
        encoding="utf-8",
    )
    findings = [f for f in lint.run(tmp_path) if "doctrine-import" in f]
    assert len(findings) == 1


def test_doctrine_import_allows_a_fenced_example_beside_the_real_line(tmp_path):
    """The other polarity: showing the import in a fence is lawful so long as
    the file also performs it. A guard that failed this would block the one
    document most likely to want to explain itself."""
    make_clean_tree(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8")
        + chr(10)
        + "For example:" + chr(10)
        + "```" + chr(10) + "@skills/charter/SKILL.md" + chr(10) + "```" + chr(10),
        encoding="utf-8",
    )
    assert [f for f in lint.run(tmp_path) if "doctrine-import" in f] == []


def test_delivery_survives_a_non_string_hook_command(tmp_path):
    """A null command once reached the regex and raised, taking down the whole
    run and suppressing every other finding in it. Found by the external pass,
    which is the only party that tried it."""
    make_clean_tree(tmp_path)
    (tmp_path / "hooks" / "hooks.json").write_text(
        '{"hooks": {"SessionStart": [{"hooks": [{"type": "command", '
        '"command": null}]}]}}' + chr(10),
        encoding="utf-8",
    )
    findings = [f for f in lint.run(tmp_path) if "delivery" in f]
    assert len(findings) == 1 and "no runnable SessionStart" in findings[0]


def test_delivery_fires_when_the_command_key_is_absent(tmp_path):
    """`.get("command", "")` made an absent key indistinguishable from a present
    empty one, and the emptiness test looked at the list rather than its
    contents -- so a config declaring no command at all passed green."""
    make_clean_tree(tmp_path)
    (tmp_path / "hooks" / "hooks.json").write_text(
        '{"hooks": {"SessionStart": [{"hooks": [{"type": "command"}]}]}}' + chr(10),
        encoding="utf-8",
    )
    findings = [f for f in lint.run(tmp_path) if "delivery" in f]
    assert len(findings) == 1 and "no runnable SessionStart" in findings[0]


def test_delivery_fires_when_the_named_path_is_a_directory(tmp_path):
    """`exists()` was satisfied by a directory of the right name, which is not
    runnable -- and the finding's own message would have been false about it."""
    make_clean_tree(tmp_path)
    (tmp_path / "hooks" / "emit_charter.py").unlink()
    (tmp_path / "hooks" / "emit_charter.py").mkdir()
    findings = [f for f in lint.run(tmp_path) if "delivery" in f]
    assert len(findings) == 1 and "not a file" in findings[0]


def test_sideways_dep_names_the_directory_it_came_from(tmp_path):
    """The scan list grew past `lib/`, and the label did not, so every finding
    outside it claimed to come from `lib/`. The charter was the first subject;
    it is a cell now and gets a skill's own label, so `hooks/` is what still
    exercises the non-skill branch."""
    make_clean_tree(tmp_path)
    (tmp_path / "hooks" / "README.md").write_text(
        "See skills/example-skill/SKILL.md." + chr(10), encoding="utf-8"
    )
    findings = [f for f in lint.run(tmp_path) if "sideways-dep" in f]
    assert len(findings) == 1 and "from hooks/" in findings[0]


def test_harness_token_fires_on_a_shipped_calling_contract(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, 'python "${CLAUDE_PLUGIN_ROOT}/skills/example-skill/scripts/run.py"\n')
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "harness-token" in findings[0]


def test_harness_token_fires_on_the_bare_and_codex_forms(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "python $CLAUDE_PLUGIN_ROOT/scripts/run.py\n"
        "python ${PLUGIN_ROOT}/scripts/run.py\n"
        "python $CODEX_HOME/scripts/run.py\n")
    findings = [f for f in lint.run(tmp_path) if "harness-token" in f]
    assert len(findings) == 3


def test_harness_token_exempts_hooks_where_the_token_actually_expands(tmp_path):
    """`hooks/` is hook configuration, where the placeholder really expands."""
    make_clean_tree(tmp_path)
    hooks = tmp_path / "hooks"
    (hooks / "hooks.json").write_text(
        '{"hooks": {"SessionStart": [{"matcher": "*", "hooks": [{"type": '
        '"command", "command": "cat ${CLAUDE_PLUGIN_ROOT}/skills/charter/SKILL.md"'
        "}]}]}}\n",
        encoding="utf-8",
    )
    assert lint.run(tmp_path) == []


def test_harness_token_stays_quiet_on_the_relative_contract(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "The script sits beside this file at scripts/run.py; invoke it by that\n"
        "path resolved against the directory this file is in.\n")
    assert lint.run(tmp_path) == []


def test_zone_wall_fires_on_rooted_reference(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "See docs/architecture/adr/README.md for rules.\n")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "zone-wall" in findings[0]


def test_zone_wall_fires_on_relative_parent_reference(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "[the constitution](../../docs/architecture/adr/README.md)\n")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "zone-wall" in findings[0]


def test_zone_wall_fires_on_uppercase_and_backslash_but_not_own_subdir(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, # ./tools/ inside a skill resolves to the skill's OWN tools/ subdir —
        # self-contained and lawful; the other two are repo-only references.
        "Run ./tools/helper.py first.\nOr see Docs/architecture.\nOr docs\\architecture\\adr.\n")
    findings = [f for f in lint.run(tmp_path) if "zone-wall" in f]
    assert len(findings) == 2


def test_zone_wall_ignores_web_urls_and_longer_paths(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "See https://example.com/docs/guide and https://github.com/o/r/blob/main/docs/x.md\n"
        "The upstream-docs/ convention and their-repo/docs/ layout are fine.\n")
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
    _write_cell(other, "Compose with skills/example-skill/ for setup.\n")
    findings = lint.run(tmp_path)
    assert len(findings) == 1
    assert "sideways-dep" in findings[0] and "example-skill" in findings[0]


def test_sideways_dep_fires_on_relative_form(tmp_path):
    make_clean_tree(tmp_path)
    other = tmp_path / "skills" / "other-skill"
    other.mkdir(parents=True)
    _write_cell(other, "Load ../example-skill/SKILL.md first.\n")
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
    _write_cell(other, "See https://github.com/anthropics/skills/tree/main/skills/pdf/SKILL.md\n"
        "The upstream-skills/bar/ layout and their-repo/skills/baz/ are fine.\n")
    assert lint.run(tmp_path) == []
    # ...and a true sideways reference still fires.
    _write_cell(other, "Load skills/example-skill/ first.\n")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "sideways-dep" in findings[0]


def test_lib_may_not_reference_a_skill(tmp_path):
    make_clean_tree(tmp_path)
    libdir = tmp_path / "lib"
    libdir.mkdir()
    (libdir / "core.py").write_text("# see skills/example-skill/SKILL.md\n", encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "sideways-dep" in findings[0] and "from lib/" in findings[0]


# --- the charter's exemption ------------------------------------------------

def test_the_charter_may_reference_any_cell(tmp_path):
    make_clean_tree(tmp_path)
    charter = tmp_path / "skills" / "charter"
    (charter / "SKILL.md").write_text(
        "---" + NL + "name: charter" + NL + "description: The binding rules." + NL
        + "---" + NL + NL
        + "The depth behind this rule lives in the `example-skill` cell." + NL,
        encoding="utf-8",
    )
    assert lint.run(tmp_path) == []


def test_any_cell_may_reference_the_charter(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "The rule itself is stated by the `charter` cell.\n")
    assert lint.run(tmp_path) == []


def test_the_exemption_is_the_name_form_and_not_a_path(tmp_path):
    """The charter may name a cell; it may not point at one's files.

    A rooted skills/ path does not resolve once installed, so exempting it
    would buy the charter a reference that is dead for every consumer.
    """
    make_clean_tree(tmp_path)
    charter = tmp_path / "skills" / "charter"
    (charter / "SKILL.md").write_text(
        "---" + NL + "name: charter" + NL + "description: The binding rules." + NL
        + "---" + NL + NL + "The bar lives at skills/example-skill/SKILL.md." + NL,
        encoding="utf-8",
    )
    findings = [f for f in lint.run(tmp_path) if "sideways-dep" in f]
    assert len(findings) == 1 and "example-skill" in findings[0]


def test_exempting_the_charter_does_not_exempt_cell_to_cell(tmp_path):
    """The exemption's whole risk: buying it by weakening the guard for all.

    Both reference forms are checked, because the name form is what the
    charter's own restored references use -- an exemption that let it through
    for everyone would be indistinguishable from this test's absence.
    """
    make_clean_tree(tmp_path)
    other = tmp_path / "skills" / "other-skill"
    other.mkdir(parents=True)
    _write_cell(other, "Depth lives in the `example-skill` cell.\n")
    findings = lint.run(tmp_path)
    assert len(findings) == 1
    assert "sideways-dep" in findings[0] and "example-skill" in findings[0]


def test_hooks_reach_the_charter_and_no_other_cell(tmp_path):
    """check_delivery mandates the hook depend on the charter, so the
    sideways rule must not forbid what its sibling requires -- and must still
    forbid every other skill, which is what 'deps point down' was for."""
    make_clean_tree(tmp_path)
    readme = tmp_path / "hooks" / "README.md"
    readme.write_text("Emits the `charter` cell on stdout.\n", encoding="utf-8")
    assert lint.run(tmp_path) == []
    readme.write_text("Emits the `example-skill` cell on stdout.\n", encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1
    assert "sideways-dep" in findings[0] and "from hooks/" in findings[0]


def test_a_cell_reference_must_name_a_cell_that_exists(tmp_path):
    """A rename leaves the sentence reading correctly and pointing nowhere."""
    make_clean_tree(tmp_path)
    charter = tmp_path / "skills" / "charter"
    body = ("---" + NL + "name: charter" + NL + "description: The binding rules."
            + NL + "---" + NL + NL + "Depth lives in the `{}` cell." + NL)
    (charter / "SKILL.md").write_text(body.format("example-skill"), encoding="utf-8")
    assert lint.run(tmp_path) == []
    (charter / "SKILL.md").write_text(body.format("renamed-away"), encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1
    assert "cell-reference" in findings[0] and "renamed-away" in findings[0]


def test_a_reference_inside_a_fence_is_displayed_not_made(tmp_path):
    """Both polarities of the fence rule: fenced is inert, bare still fires.

    A cell quoting the reference form in an example is showing it, not making
    it -- the same premise check_doctrine already reasons from about imports.
    Without the lawful arm a later widening of the fence handling would land
    unnoticed.
    """
    make_clean_tree(tmp_path)
    other = tmp_path / "skills" / "other-skill"
    other.mkdir(parents=True)
    _write_cell(other, "Write it like this:" + NL + NL
                + "```" + NL + "the `example-skill` cell" + NL + "```" + NL)
    assert lint.run(tmp_path) == []
    _write_cell(other, "Depth lives in the `example-skill` cell." + NL)
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "sideways-dep" in findings[0]


def test_a_reference_wrapped_across_a_line_break_is_still_a_reference(tmp_path):
    """A reflow is a formatting edit nobody inspects.

    Found under review by reflowing one charter reference and watching the
    rename probe drop from three findings to two -- the reference had left
    both checks without a character of prose changing.
    """
    make_clean_tree(tmp_path)
    other = tmp_path / "skills" / "other-skill"
    other.mkdir(parents=True)
    _write_cell(other, "Depth lives in the `example-skill`" + NL + "cell." + NL)
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "across a line break" in findings[0]
    # Lawful arm: the charter may be named the same way, wrapped or not...
    _write_cell(other, "The rule is the `charter`" + NL + "cell's." + NL)
    assert lint.run(tmp_path) == []
    # ...and a paragraph break is not a wrap.
    _write_cell(other, "Ends with `example-skill`" + NL + NL + "cell." + NL)
    assert lint.run(tmp_path) == []


def test_a_wrapped_reference_must_also_name_a_cell_that_exists(tmp_path):
    make_clean_tree(tmp_path)
    charter = tmp_path / "skills" / "charter"
    (charter / "SKILL.md").write_text(
        "---" + NL + "name: charter" + NL + "description: The binding rules." + NL
        + "---" + NL + NL + "Depth lives in the `renamed-away`" + NL + "cell." + NL,
        encoding="utf-8",
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1
    assert "cell-reference" in findings[0] and "renamed-away" in findings[0]


def test_a_references_pointer_must_resolve_against_its_own_file(tmp_path):
    """The cell-reference failure one level down.

    Depth-shedding makes `references/` the roster-wide standard, so a pointer
    at a file that moved strands a session exactly as a renamed cell does --
    and the body deliberately no longer carries what the pointer promises.
    """
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    assert lint.run(tmp_path) == []
    (skill / "references" / "detail.md").rename(skill / "references" / "moved.md")
    findings = lint.run(tmp_path)
    assert len(findings) == 1
    assert "reference-pointer" in findings[0] and "references/detail.md" in findings[0]


# Every check `run` calls, in call order. Literal on purpose: deriving this
# from `run` would make the test agree with itself, which is what let the list
# say eight while `run` called ten, silently, from #156 until #169 found it.
LINT_CHECKS_IN_ORDER = (
    "check_zone_wall", "check_harness_tokens", "check_delivery",
    "check_cell_frontmatter", "check_project_roster",
    "check_sideways_deps", "check_cell_references",
    "check_doctrine_citations",
    "check_doctrine", "check_doctrine_callout", "check_review_index",
    "check_decision_index", "check_entry_references",
    "check_emitted_ascii", "check_docstring_not_piped",
    "check_stdio_wired",
)


def test_the_module_docstring_enumerates_every_check_run_calls():
    """The check list is the module's contract; nothing pinned it.

    Count and order only, deliberately -- pinning the prose would go red on
    every rewording and be deleted within a release. It does not catch a wrong
    *description* inside an item; that is a separate class, and this change
    carries an instance of it (check 5 said hooks/ may reference no skill at
    all while the code exempts the charter from anywhere).
    """
    import inspect

    called = re.findall(r"check_[a-z_]+", inspect.getsource(lint.run))
    assert tuple(called) == LINT_CHECKS_IN_ORDER, (
        "run() calls checks this list does not name, or in another order"
    )
    numbered = re.findall(r"^\s*(\d+)\.\s", lint.__doc__, re.M)
    assert [int(n) for n in numbered] == list(
        range(1, len(LINT_CHECKS_IN_ORDER) + 1)
    ), "the docstring's numbered checks do not match what run() calls"


def make_entry(root: Path, number: int) -> None:
    """One decision entry, named the way check_doctrine_citations globs it."""
    directory = root / "docs" / "architecture" / "decisions"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ("D-%d-2026-01-01-slug.md" % number)).write_text(
        ("# D-%d" % number) + NL, encoding="utf-8")


def test_a_doctrine_citation_that_resolves_is_not_a_finding(tmp_path):
    """The lawful polarity, and the one that matters most here: the outflow
    rule tells a session to replace prose with a citation, so a guard that
    goes red on a citation that resolves would block the rule it exists to
    serve."""
    make_clean_tree(tmp_path)
    make_entry(tmp_path, 81)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(agents.read_text(encoding="utf-8")
                      + "The callout is the owner's read. [D-81]" + NL,
                      encoding="utf-8")
    assert lint.run(tmp_path) == []


def test_a_doctrine_citation_that_resolves_to_nothing_is_a_finding(tmp_path):
    """A reason compressed into a marker nobody checks is a reason deleted on
    the next renumbering, on the surface every session reads first. All four
    markers in the doctrine resolved to nothing while lint stayed green."""
    make_clean_tree(tmp_path)
    make_entry(tmp_path, 81)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(agents.read_text(encoding="utf-8")
                      + "Compressed to its reason. [D-9999]" + NL,
                      encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1
    assert "doctrine-citation" in findings[0] and "[D-9999]" in findings[0]


def test_the_citation_guard_reads_the_pointer_too(tmp_path):
    """Both doctrine files, because both are always-on here and a rule can
    move between them."""
    make_clean_tree(tmp_path)
    pointer = tmp_path / "CLAUDE.md"
    pointer.write_text(pointer.read_text(encoding="utf-8") + "[D-9999]" + NL,
                       encoding="utf-8")
    findings = [f for f in lint.run(tmp_path) if "doctrine-citation" in f]
    assert len(findings) == 1 and "CLAUDE.md" in findings[0]


def test_the_citation_guard_leaves_the_placeholder_and_fenced_prose_alone(tmp_path):
    """Two lawful forms a naive scan turns red.

    `[D-N]` is how the doctrine names the *form* of a citation, and N is not a
    number; a fenced block is displayed prose, not a live rule. A guard that
    fails a required check on either blocks lawful work, which fails as hard
    as passing unlawful work.
    """
    make_clean_tree(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8")
        + "A rule may cite its decision (`[D-N]`)." + NL
        + "```" + NL + "See [D-9999] for the shape." + NL + "```" + NL,
        encoding="utf-8")
    assert lint.run(tmp_path) == []


@pytest.mark.parametrize("rendering", [
    "fetch-depth: 0",
    "fetch-depth: 0  # full history, for the delta's base",
    "fetch-depth: '0'",
    'fetch-depth: "0"',
])
def test_lawful_renderings_of_full_history_are_not_findings(tmp_path, rendering):
    """A guard that fails a required check on a lawful reformat blocks lawful
    work, which fails as hard as passing unlawful work.

    The first anchor written for this ended at `$` with neither quoting nor a
    comment admitted, so three of these four went red -- on the one key whose
    whole purpose is that a later session not delete it.
    """
    make_clean_tree(tmp_path)
    _ci(tmp_path, WIRED_CI.replace("fetch-depth: 0", rendering))
    assert lint.run(tmp_path) == []


def test_the_lint_reports_the_always_on_total(capsys):
    """The number reaches the session doing the editing, not only the owner
    at the merge button.

    An experience session found the derivation reachable only through frozen
    decision entries, and said the number changed what it did once it had it.
    """
    lint.main()
    out = capsys.readouterr().out
    assert "always-on surface:" in out
    assert "for an adopter" in out and "not derived" not in out


def test_an_underivable_figure_does_not_fail_the_lint(tmp_path, monkeypatch):
    """The other polarity, and the one that matters: this is a required check.
    A tree with no figures module is not a lint finding, and a number that
    cannot be derived must never turn a clean tree red."""
    make_clean_tree(tmp_path)
    note = lint.always_on_note(tmp_path)
    assert note.startswith("always-on surface: not derived")
    assert lint.run(tmp_path) == []


def test_a_fence_closes_only_on_its_own_marker(tmp_path):
    """CommonMark's rule, and the renderer every reader is looking at.

    A naive toggle fails both ways, and both are what a cell teaching
    markdown writes rather than what an adversary supplies: a ``` line quoted
    inside a ```` block ends the fence early, so displayed prose reads as
    live; a ~~~ line inside a ``` block never ends it, so live prose goes
    unread to the end of the file.
    """
    make_clean_tree(tmp_path)
    other = tmp_path / "skills" / "other-skill"
    other.mkdir(parents=True)
    quoted = ("````" + NL + "A fence opens with:" + NL + "```" + NL + "````" + NL
              + NL + "Depth lives in the `example-skill` cell." + NL)
    _write_cell(other, quoted)
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "sideways-dep" in findings[0], (
        "a ``` quoted inside a ```` block must not end the fence"
    )
    mismatched = ("```" + NL + "shown, not made" + NL + "~~~" + NL
                  + NL + "Depth lives in the `example-skill` cell." + NL)
    _write_cell(other, mismatched)
    assert lint.run(tmp_path) == [], (
        "a ~~~ line must not close a ``` fence, so what follows stays fenced"
    )


def test_a_path_inside_a_fence_is_still_a_path(tmp_path):
    """The fence exemption is the name form's alone.

    This repository's fenced blocks are calling contracts and command lines,
    not examples; `check_zone_wall` and `check_harness_tokens` already fire
    inside them, and the portability guard reads a cell's script contract
    through one and requires it to resolve. Exempting paths here would put
    two guards in one tree disagreeing about what a fence means.
    """
    make_clean_tree(tmp_path)
    other = tmp_path / "skills" / "other-skill"
    other.mkdir(parents=True)
    for body, expected in (
        ("```" + NL + "See skills/example-skill/SKILL.md" + NL + "```" + NL, 1),
        ("```" + NL + "python ../example-skill/scripts/x.py" + NL + "```" + NL, 1),
        ("```" + NL + "the `example-skill` cell" + NL + "```" + NL, 0),
    ):
        _write_cell(other, body)
        findings = [f for f in lint.run(tmp_path) if "sideways-dep" in f]
        assert len(findings) == expected, f"{body!r} -> {findings}"


def test_a_references_pointer_guard_leaves_lawful_prose_alone(tmp_path):
    """The lawful cases the rooted-skill branch already names.

    A guard blocking lawful work fails as hard as one passing unlawful work,
    and nothing in shipped prose reserves `references/*.md` the way the cell
    name form is reserved -- so an author citing an upstream URL has no
    warning and no escape.
    """
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    for body in (
        "See https://github.com/x/y/blob/main/references/guide.md for the note.\n",
        "Upstream vendors it at vendor/pkg/references/notes.md today.\n",
    ):
        _write_cell(skill, body)
        assert [f for f in lint.run(tmp_path) if "reference-pointer" in f] == [], body
    _write_cell(skill, "Depth lives in references/detail.md.\n")
    assert lint.run(tmp_path) == []
    _write_cell(skill, "Depth lives in references/gone.md.\n")
    findings = [f for f in lint.run(tmp_path) if "reference-pointer" in f]
    assert len(findings) == 1 and "references/gone.md" in findings[0]


def test_a_pointer_inside_a_fence_is_still_a_pointer(tmp_path):
    """A pointer is a path form; only the name form is fence-exempt.

    Both arms are the pin: before this, the fenced-pointer behaviour was
    asserted in neither direction, so either reading could have been changed
    without a test noticing. A path that does not resolve is broken wherever
    it is written; a name inside a fence is a spelling being shown.
    """
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "```" + NL + "See references/gone.md" + NL + "```" + NL)
    findings = [f for f in lint.run(tmp_path) if "reference-pointer" in f]
    assert len(findings) == 1 and "references/gone.md" in findings[0]
    other = tmp_path / "skills" / "other-skill"
    other.mkdir(parents=True)
    _write_cell(other, "```" + NL + "the `example-skill` cell" + NL + "```" + NL)
    assert [f for f in lint.run(tmp_path) if "sideways-dep" in f] == []


def test_a_code_span_is_not_a_fence_and_a_closing_fence_carries_no_info(tmp_path):
    """CommonMark's two clauses a marker-only match misses.

    A line-initial code span showing a literal fence is a paragraph, and a
    marker with an info string cannot close one. Missing either lets a cell
    documenting markdown silently switch off every reference check for the
    rest of its own file -- or end a fence early and read displayed prose as
    live. The lawful arms are the point: four spellings of a real fence must
    still hide what they enclose.
    """
    make_clean_tree(tmp_path)
    other = tmp_path / "skills" / "other-skill"
    other.mkdir(parents=True)
    for body in (
        "````" + NL + "```" + NL + "````" + NL + NL + "the `example-skill` cell" + NL,
        "```" + NL + "shown" + NL + "```python" + NL + "y" + NL + "```" + NL
        + "the `example-skill` cell" + NL,
    ):
        _write_cell(other, body)
        assert len([f for f in lint.run(tmp_path) if "sideways-dep" in f]) == 1, body
    for fence in ("```", "```text", "~~~", "````"):
        closer = "~~~" if fence == "~~~" else fence.rstrip("text") or "```"
        _write_cell(other, fence + NL + "the `example-skill` cell" + NL + closer + NL)
        assert [f for f in lint.run(tmp_path) if "sideways-dep" in f] == [], fence


def test_a_cell_named_at_the_front_door_must_resolve(tmp_path):
    """The README is the surface an adopter reads before installing.

    It is not a cell and the sideways rule does not reach it, so it may name
    any cell -- but a rename leaves its sentence reading correctly and
    pointing nowhere, which is the failure this check exists for. Its own
    reserved-form references were unguarded until this pin.
    """
    make_clean_tree(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text("The `example-skill` cell carries it." + NL, encoding="utf-8")
    assert lint.run(tmp_path) == []
    readme.write_text("The `renamed-away` cell carries it." + NL, encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1
    assert "cell-reference" in findings[0] and "README.md" in findings[0]


def test_the_exempt_cell_name_is_the_one_these_tests_pin():
    """A test deriving its bound from the constant it tests cannot catch a
    change to that constant [#164]. The exemption is a rule about one named
    cell, so the name is pinned literally here."""
    assert lint.CHARTER_CELL == "charter"


# --- doctrine --------------------------------------------------------------

def test_doctrine_budget_fires_when_agents_md_bloats(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "AGENTS.md").write_text(
        "@skills/charter/SKILL.md" + chr(10) + "x" * (lint.AGENTS_BUDGET_CHARS + 1),
        encoding="utf-8",
    )
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
    # Not a dead job but a blind one, and this is the shape that shipped:
    # the delta's base side reads blobs at another revision, a shallow
    # clone has none, and the read failing costs the callout its figure
    # while every check still reports green. Omitting the key is what
    # produces depth 1, so the default is the trap.
    ("full history dropped",
     lambda t: t.replace("          fetch-depth: 0\n", ""),
     "does not check out full history"),
    # A bounded depth is still a shallow clone and the base sits any
    # distance back, so the pin is `0` rather than evidence that somebody
    # thought about depth at all.
    ("depth bounded instead of full",
     lambda t: t.replace("fetch-depth: 0", "fetch-depth: 50"),
     "does not check out full history"),
    # The delta's request, at both seams. Deleting either leaves the other
    # standing and the command still reading correctly, which is why one
    # pattern on the run line cannot hold this.
    ("the --base flag deleted",
     lambda t: t.replace(" --base $BASE_SHA", ""),
     "does not pass `--base`"),
    ("the BASE_SHA environment line deleted",
     lambda t: t.replace("          BASE_SHA: xyz\n", ""),
     "does not put the base revision in the environment"),
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
    _write_cell(skill, "[ci](../../.github/workflows/ci.yml)\n"
        "See ../../.github/workflows/ci.yml too.\n"
        "Or ..\\..\\.github\\workflows\\ci.yml.\n")
    findings = [f for f in lint.run(tmp_path) if "zone-wall" in f]
    assert len(findings) == 3, findings


def test_zone_wall_ignores_relative_dot_leading_path_that_is_not_repo_only(tmp_path):
    # The lawful polarity of the same fix: a dot-leading first segment that is
    # not a repo-only name must still pass, or the guard blocks lawful work.
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "See ../.config/settings.json and ./.cache/notes.md.\n")
    assert [f for f in lint.run(tmp_path) if "zone-wall" in f] == []


def test_zone_wall_ignores_suffix_match_inside_a_longer_relative_token(tmp_path):
    # `assets/../../docs/x.md` resolves to skills/example-skill/docs/x.md, which
    # is the skill's own subdir and lawful. Matching only the `../../docs/x.md`
    # tail resolved it from the wrong base and reported a repo-only hit, for all
    # three repo-only names. Found by the external pass on 2026-08-22.
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "See assets/../../.github/workflows/ci.yml.\n"
        "See assets/../../docs/architecture/README.md.\n"
        "See assets/../../tools/lint.py.\n"
        "See [x](assets/../../.github/workflows/ci.yml).\n"
        "See assets\\..\\..\\.github\\ci.yml.\n"
        "See a.b/../../docs/x.md.\n")
    assert [f for f in lint.run(tmp_path) if "zone-wall" in f] == []


def test_sideways_dep_ignores_suffix_match_inside_a_longer_relative_token(tmp_path):
    # RELATIVE_REF is shared with check_sideways_deps, so the same suffix match
    # reached both guards; the lawful polarity has to be pinned on both.
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "See assets/../beta-skill/SKILL.md.\n")
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
    row = _review_row()
    row["dispositions"] = {"fixed": 3, "routed": 1, "priced_out": 2, "dismissed": 0}
    row["staffing"] = {"model": "Opus 5", "runtime": "Claude Code (Windows)"}
    row.update(overrides)
    return row


def test_row_carrying_dispositions_and_staffing_is_clean(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _row_with_extras())
    assert lint.run(tmp_path) == []


def test_row_appended_after_the_grandfathered_ones_must_carry_both(tmp_path, monkeypatch):
    """An optional field can never catch its own omission, and a record that
    silently fails to carry what it promises is the defect this closes."""
    make_clean_tree(tmp_path)
    monkeypatch.setattr(lint, "REVIEW_ROWS_GRANDFATHERED", 1)
    _write_index(tmp_path, _review_row(), _review_row(artifact="pr-2"))
    findings = lint.run(tmp_path)
    assert len(findings) == 2
    assert any("dispositions" in f for f in findings)
    assert any("staffing" in f for f in findings)


def test_grandfathered_rows_need_neither(tmp_path, monkeypatch):
    """Forward-only in fact, not merely in intent: rows already written stay
    valid untouched, whatever date they carry."""
    make_clean_tree(tmp_path)
    monkeypatch.setattr(lint, "REVIEW_ROWS_GRANDFATHERED", 1)
    _write_index(tmp_path, _review_row())
    assert lint.run(tmp_path) == []


def test_the_obligation_cannot_be_dodged_by_the_date_written(tmp_path, monkeypatch):
    """It was gated on the row's own date first. An experience session found
    that hole by reaching for "today" before re-reading its brief: one day
    early and both fields go optional, silently, in a file nobody may edit.
    Position is not typo-able."""
    make_clean_tree(tmp_path)
    monkeypatch.setattr(lint, "REVIEW_ROWS_GRANDFATHERED", 1)
    _write_index(
        tmp_path, _review_row(), _review_row(artifact="pr-2", date="1999-01-01")
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 2
    assert all("missing field" in f for f in findings)


def test_blank_lines_do_not_shift_a_row_position(tmp_path, monkeypatch):
    """Rows are counted, not lines. The shape matters: positions only ever
    shift *upward*, so a row already past the boundary stays obliged either
    way and proves nothing. The discriminating case is a row that must stay
    **exempt** and that blank lines would push across."""
    make_clean_tree(tmp_path)
    monkeypatch.setattr(lint, "REVIEW_ROWS_GRANDFATHERED", 2)
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    blanks = "\n" + "\n" + "\n"
    (docs / "reviews.jsonl").write_text(
        json.dumps(_row_with_extras()) + blanks
        + json.dumps(_review_row(artifact="pr-2")) + "\n",
        encoding="utf-8",
    )
    assert lint.check_review_index(tmp_path) == []


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


def _real_index_rows() -> str:
    real = Path(__file__).resolve().parents[2] / "docs" / "reviews.jsonl"
    return real.read_text(encoding="utf-8")


def _index_tree(tmp_path: Path, extra: str = "") -> Path:
    """A clean tree carrying the repository's own review index, so the gate is
    exercised through check_review_index's real position arithmetic."""
    make_clean_tree(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "reviews.jsonl").write_text(_real_index_rows() + extra, encoding="utf-8")
    return tmp_path


def test_every_row_already_in_the_repo_index_stays_valid(tmp_path):
    """Acceptance criterion 2, driven through the real position arithmetic
    rather than the row checker directly — the earlier form called
    `_check_review_row` without a position, so every row validated as
    grandfathered and the assertion could not fail on the gate at all."""
    root = _index_tree(tmp_path)
    assert lint.check_review_index(root) == []


def test_a_row_appended_past_the_grandfathered_ones_is_obliged(tmp_path):
    """The behavioural pin on the constant. Deliberately *not* an assertion
    that it equals the index's row count: that goes stale the moment the next
    row lands, turning the guard into the bookkeeping the tripwire deletes.
    Raising the constant silently exempts real rows, and only this catches it."""
    bare = json.dumps(_review_row(artifact="pr-next")) + "\n"
    root = _index_tree(tmp_path, extra=bare)
    findings = lint.check_review_index(root)
    assert len(findings) == 3
    assert any("dispositions" in f for f in findings)
    assert any("staffing" in f for f in findings)
    assert any("facing" in f for f in findings)


def test_a_row_that_fails_to_parse_does_not_shift_later_rows(tmp_path):
    """Position is the non-blank line's ordinal, counted before the parse. When
    it was counted after, a corrupt row upstream pushed the appended row back
    under the boundary — so its findings vanished while they were actionable
    and would return later, against a row by then landed and unfixable."""
    rows = _real_index_rows().splitlines()
    corrupted = "\n".join(rows[:3] + [rows[3][:40]] + rows[4:]) + "\n"
    bare = json.dumps(_review_row(artifact="pr-next")) + "\n"
    make_clean_tree(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "reviews.jsonl").write_text(corrupted + bare, encoding="utf-8")
    findings = lint.check_review_index(tmp_path)
    assert any("not valid JSON" in f for f in findings)
    assert len([f for f in findings if "missing field" in f]) == 3


def test_staffing_rejects_unknown_keys(tmp_path):
    """The keys are closed even though the values are not. Per-seat staffing is
    the design this change excluded, and an unvalidated field is how it would
    have entered silently — into a record that may never be corrected."""
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _row_with_extras(
        staffing={"model": "Opus 5", "runtime": "Claude Code", "cold-read": "fable"}
    ))
    findings = [f for f in lint.run(tmp_path) if "unknown key" in f]
    assert len(findings) == 1 and "cold-read" in findings[0]


def test_staffing_still_accepts_a_split_in_the_value(tmp_path):
    """The counterpart: an uneven panel must be able to record its split, which
    two rows in the landed record already needed. Rejecting unknown keys must
    not close the path the row actually has."""
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _row_with_extras(
        staffing={"model": "fable (cold-read), opus (rest)", "runtime": "Claude Code"}
    ))
    assert lint.run(tmp_path) == []


def test_non_mapping_dispositions_and_staffing_are_findings(tmp_path):
    """Both branches were correct and neither was pinned, so either could be
    deleted with the suite green."""
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _row_with_extras(dispositions=["fixed"]))
    a = [f for f in lint.run(tmp_path) if "must be a mapping" in f]
    _write_index(tmp_path, _row_with_extras(staffing="Opus 5"))
    b = [f for f in lint.run(tmp_path) if "must be a mapping" in f]
    assert len(a) == 1 and len(b) == 1


# --- review row: the split by consequence shape --------------------------


def _row_with_facing(**overrides):
    """`_row_with_extras` disposes of six rulings, so a lawful split sums to six."""
    row = _row_with_extras()
    row["facing"] = {"artifact": 4, "apparatus": 2}
    row.update(overrides)
    return row


def test_row_carrying_a_reconciling_facing_is_clean(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _row_with_facing())
    assert lint.run(tmp_path) == []


def test_row_appended_past_the_facing_boundary_must_carry_it(tmp_path, monkeypatch):
    make_clean_tree(tmp_path)
    monkeypatch.setattr(lint, "REVIEW_ROWS_GRANDFATHERED", 1)
    monkeypatch.setattr(lint, "REVIEW_ROWS_FACING_GRANDFATHERED", 1)
    _write_index(tmp_path, _review_row(), _row_with_extras(artifact="pr-2"))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "facing" in findings[0]


def test_rows_grandfathered_for_facing_need_none(tmp_path, monkeypatch):
    """Forward-only in fact: a row written before the field existed stays valid
    untouched, in a file the doctrine forbids editing."""
    make_clean_tree(tmp_path)
    monkeypatch.setattr(lint, "REVIEW_ROWS_GRANDFATHERED", 1)
    monkeypatch.setattr(lint, "REVIEW_ROWS_FACING_GRANDFATHERED", 2)
    _write_index(tmp_path, _review_row(), _row_with_extras(artifact="pr-2"))
    assert lint.run(tmp_path) == []


def test_the_two_boundaries_are_independent(tmp_path, monkeypatch):
    """The pin on there being two constants rather than one that moves. A row
    between them owes `dispositions` and `staffing` and does not owe `facing`;
    collapsing the pair would silently un-oblige every row in that band."""
    make_clean_tree(tmp_path)
    monkeypatch.setattr(lint, "REVIEW_ROWS_GRANDFATHERED", 1)
    monkeypatch.setattr(lint, "REVIEW_ROWS_FACING_GRANDFATHERED", 3)
    _write_index(
        tmp_path,
        _review_row(),
        _review_row(artifact="pr-2"),
        _row_with_extras(artifact="pr-3"),
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 2
    assert any("dispositions" in f for f in findings)
    assert any("staffing" in f for f in findings)
    assert not any("facing" in f for f in findings)


def test_facing_must_reconcile_with_the_dispositions_total(tmp_path):
    """The only cross-total this row carries, and the reason it is sound where
    the seat-count one is not: both halves count one entry per terminal ruling.
    Probed in both polarities -- the row that does not add up is caught, and the
    row that does is left alone by the same check."""
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _row_with_facing(facing={"artifact": 4, "apparatus": 1}))
    findings = lint.run(tmp_path)
    assert len(findings) == 1
    assert "facing sums to 5 and dispositions to 6" in findings[0]

    _write_index(tmp_path, _row_with_facing(facing={"artifact": 0, "apparatus": 6}))
    assert lint.run(tmp_path) == []

    # Both arithmetic directions, not just lawful-versus-unlawful: narrowing the
    # comparison to `<` passed the whole suite until this case existed, and the
    # row it then admitted double-counts a ruling -- the error a split derived
    # from report prose is likeliest to make.
    _write_index(tmp_path, _row_with_facing(facing={"artifact": 5, "apparatus": 2}))
    findings = lint.run(tmp_path)
    assert len(findings) == 1
    assert "facing sums to 7 and dispositions to 6" in findings[0]


def test_facing_reconciliation_is_silent_on_a_row_it_cannot_compute(tmp_path):
    """A malformed `dispositions` already has its own finding; adding an
    arithmetic one derived from it would report the same defect twice and name
    a total nobody wrote."""
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _row_with_facing(dispositions={"fixed": 1}))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "dispositions missing" in findings[0]


def test_facing_rejects_bools_and_negatives(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _row_with_facing(facing={"artifact": True, "apparatus": -1}))
    findings = [f for f in lint.run(tmp_path) if "non-negative integer" in f]
    assert len(findings) == 2


def test_facing_missing_a_shape_is_a_finding(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _row_with_facing(facing={"artifact": 6}))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "facing missing apparatus" in findings[0]


def test_facing_rejects_unknown_shapes(tmp_path):
    """Two shapes, closed. Three consumers under an undefined earlier wording
    invented three different taxonomies, which is why the axis is keyed to the
    cited site and why a third key is a finding rather than a refinement."""
    make_clean_tree(tmp_path)
    _write_index(
        tmp_path,
        _row_with_facing(facing={"artifact": 3, "apparatus": 2, "both": 1}),
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "unknown key" in findings[0] and "both" in findings[0]

    # The same silence the malformed-`dispositions` path already keeps, and for
    # the same reason: the third key holds part of the population, so neither
    # total is the writer's arithmetic. Both mappings, because either can carry
    # a ruling out of the counted set.
    # The known keys must sum away from the facing total, or the reconciliation
    # is silent whether the gate fires or not and the assertion cannot see the
    # mutation -- which is how the first version of this pin passed for the
    # wrong reason. Known sum 4 against a facing of 6: without the gate a second
    # finding appears naming a total nobody wrote.
    _write_index(tmp_path, _row_with_facing(
        dispositions={"fixed": 3, "routed": 1, "priced_out": 0, "dismissed": 0, "withdrawn": 2},
    ))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "unknown key" in findings[0]


def test_non_mapping_facing_is_a_finding_not_a_crash(tmp_path):
    make_clean_tree(tmp_path)
    _write_index(tmp_path, _row_with_facing(facing=[4, 2]))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "facing must be a mapping" in findings[0]


def test_a_real_row_appended_without_facing_is_caught(tmp_path):
    """Driven through the repository's own index, so the boundary constant is
    exercised by real position arithmetic rather than a monkeypatched one."""
    row = json.dumps(_row_with_extras(artifact="pr-next")) + "\n"
    root = _index_tree(tmp_path, extra=row)
    findings = lint.check_review_index(root)
    assert len(findings) == 1 and "facing" in findings[0]


FRONTMATTER_CASES = [
    # (label, document, expected body)
    (
        "a normal cell",
        "---" + NL + "name: x" + NL + "description: y" + NL + "---" + NL + NL + "# x" + NL + "Body." + NL,
        "# x" + NL + "Body." + NL,
    ),
    (
        "no frontmatter at all",
        "# x" + NL + "Body." + NL,
        "# x" + NL + "Body." + NL,
    ),
    (
        "a horizontal rule inside the body",
        "---" + NL + "name: x" + NL + "---" + NL + NL + "Above." + NL + "---" + NL + "Below." + NL,
        "Above." + NL + "---" + NL + "Below." + NL,
    ),
    (
        "an unterminated frontmatter block",
        "---" + NL + "name: x" + NL + "still open" + NL,
        "---" + NL + "name: x" + NL + "still open" + NL,
    ),
    (
        "frontmatter and nothing else",
        "---" + NL + "name: x" + NL + "---" + NL,
        "",
    ),
    (
        "blank lines between the block and the body",
        "---" + NL + "name: x" + NL + "---" + NL + NL + NL + "Body." + NL,
        "Body." + NL,
    ),
    (
        "an empty document",
        "",
        "",
    ),
]


@pytest.mark.parametrize(
    "document,expected",
    [(d, e) for _, d, e in FRONTMATTER_CASES],
    ids=[label for label, _, _ in FRONTMATTER_CASES],
)
def test_both_frontmatter_strippers_produce_the_expected_body(document, expected):
    """Two implementations, one table of literal answers.

    `hooks/emit_charter.py` and `tools/lint.py` each carry this parse, and the
    zone wall forces that: `hooks/` is shipped, `tools/` is repo-only, and the
    shared home that would fix it does not exist. What the duplication cost was
    an oracle -- the portability suite checked the emitter's output against the
    lint's function, so setting *both* to identity left every check green while
    the hook emitted raw YAML into every consumer session. The expected values
    below are literal, so neither implementation is the other's answer key.
    """
    assert emit_charter._body(document) == expected
    assert lint._frontmatterless(document) == expected


def test_the_budget_measures_the_body_and_not_the_file(tmp_path):
    """A description edit must not eat the rules' headroom.

    The rule is asserted in a decision entry that freezes on landing, and until
    now nothing pinned it: reverting the budget to measure the whole file left
    the suite green, because the existing budget test writes a cell with no
    frontmatter and so never enters the stripping branch.
    """
    make_clean_tree(tmp_path)
    charter = tmp_path / "skills" / "charter" / "SKILL.md"
    body = "x" * (lint.CHARTER_BUDGET_CHARS - 10)
    charter.write_text(
        "---" + NL + "name: charter" + NL
        + "description: " + "d" * 400 + NL + "---" + NL + NL + body + NL,
        encoding="utf-8",
    )
    # The file is over budget; the body is under it. Only a guard measuring the
    # body stays quiet here.
    assert len(charter.read_text(encoding="utf-8")) > lint.CHARTER_BUDGET_CHARS
    assert [f for f in lint.run(tmp_path) if "doctrine-budget" in f] == []


def _set_description(root: Path, value: str) -> None:
    """Rewrite the charter cell's description, leaving everything else alone."""
    cell = root / "skills" / "charter" / "SKILL.md"
    lines = cell.read_text(encoding="utf-8").splitlines()
    close = lines.index("---", 1)
    kept = [ln for ln in lines[1:close] if not ln.startswith("description:")]
    rebuilt = ["---"] + kept + ["description: " + value] + lines[close:]
    cell.write_text(NL.join(rebuilt) + NL, encoding="utf-8")


HAZARD_CASES = [
    # (label, description value, must the guard fire?)
    ("a plain description", "A perfectly ordinary description.", False),
    ("an unquoted colon-space", "Not a cell: it decides nothing.", True),
    ("a trailing colon", "What this cell is for:", True),
    ("an inline comment", "A description with a # comment in it.", True),
    ("a leading indicator", "- a description that opens as a list item", True),
    # The hole that shipped: a value opening and closing with a quote is not
    # thereby quoted. This is the guard's own printed remedy applied to a
    # description carrying an apostrophe, which most of them do.
    ("a quote-wrapped value with a bare interior quote", "'The owner's rules.'", True),
    ("a correctly closed single-quoted value", "'The owner''s rules.'", False),
    ("a closed double-quoted value", '"The owner rules."', False),
    # A permissive escape rule would accept this; YAML 1.2 does not.
    ("a double-quoted value with an unknown escape", '"a \\x b"', True),
    # The same hole as the single-quoted case above, on the other arm:
    # without this row `_DQ_CLOSED` relaxes to `".*"` with the suite green.
    ("a double-quoted value with a bare interior quote", '"say "hi" now"', True),
    # ns-plain-first: lawful openers. All three load byte-identical under
    # PyYAML and pass the vendor under both line endings. A guard that
    # blocks lawful work fails as hard as one that passes unlawful work.
    ("a dash opening a lawful plain scalar", "-portable and fast", False),
    ("a question mark opening a lawful plain scalar", "?query the index", False),
    ("a colon opening a lawful plain scalar", ":vector math for the win", False),
    ("a question mark followed by a space", "? a description", True),
    ("a bare indicator", "-", True),
    # Not covered by "an inline comment", which pins the ` #` check. A
    # leading `#` loads as null with the vendor silent under both endings,
    # so this guard is the only thing catching it -- and the two-set split
    # is what makes this branch one a mutation can move.
    ("a leading hash", "#leading hash", True),
]


@pytest.mark.parametrize(
    "value,fires",
    [(v, f) for _, v, f in HAZARD_CASES],
    ids=[label for label, _, _ in HAZARD_CASES],
)
def test_cell_frontmatter_hazards(tmp_path, value, fires):
    """Each branch of the scalar check, in both polarities.

    The guard shipped once with only the happy path exercised, which is how a
    false negative survives: a clean tree proves a guard stays quiet and can
    never prove it speaks.
    """
    make_clean_tree(tmp_path)
    _set_description(tmp_path, value)
    findings = [f for f in lint.run(tmp_path) if "cell-frontmatter" in f]
    assert bool(findings) is fires, findings


def test_cell_frontmatter_fires_when_the_description_is_missing(tmp_path):
    make_clean_tree(tmp_path)
    cell = tmp_path / "skills" / "charter" / "SKILL.md"
    cell.write_text(
        cell.read_text(encoding="utf-8").replace(
            "description: The binding rules." + NL, ""),
        encoding="utf-8",
    )
    findings = [f for f in lint.run(tmp_path) if "cell-frontmatter" in f]
    assert len(findings) == 1 and "no description" in findings[0]


def test_cell_frontmatter_fires_when_the_name_disagrees_with_the_directory(tmp_path):
    make_clean_tree(tmp_path)
    cell = tmp_path / "skills" / "charter" / "SKILL.md"
    cell.write_text(
        cell.read_text(encoding="utf-8").replace("name: charter", "name: chartr"),
        encoding="utf-8",
    )
    findings = [f for f in lint.run(tmp_path) if "cell-frontmatter" in f]
    assert len(findings) == 1 and "sits in" in findings[0]


def test_the_declared_description_ceiling_is_the_one_these_tests_pin(tmp_path):
    """Stated as a literal so raising the constant is a deliberate act.

    A test that derives its bound from the constant it is testing cannot catch
    a change to that constant -- and, at a large enough mutation, spends a
    minute writing the file it is about to measure.
    """
    assert lint.CELL_FIELD_MAX_CHARS == {"name": 64, "description": 700}


def test_every_remaining_budget_constant_is_pinned_literally(tmp_path):
    """#164, discharged: the two constants the earlier fix left deriving
    their bounds from themselves.

    Both were mutable with the suite green -- every test that touched them
    built its input out of the constant it was testing, so the bound moved
    with the value it was meant to hold. Literals here, and the behavioural
    arms below, so a change to either is a deliberate act with a red suite
    behind it.
    """
    assert lint.AGENTS_BUDGET_CHARS == 6_000
    assert lint.POINTER_BUDGET_CHARS == 500


def test_a_cell_body_budget_is_enforced_in_both_polarities(tmp_path):
    """The cap #169 stated and nothing held.

    It lived in a command string inside a decision entry that has frozen, so
    the only thing standing between the body and unbounded growth was that
    somebody remembered. The lawful arm is half the pin: a cell at its budget
    must pass, or the guard is a ratchet nobody can land a change through.
    """
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    budget = 200
    monkey = dict(lint.CELL_BODY_BUDGET_CHARS)
    monkey["skills/example-skill/SKILL.md"] = budget
    original = lint.CELL_BODY_BUDGET_CHARS
    try:
        lint.CELL_BODY_BUDGET_CHARS = monkey
        _write_cell(skill, "x" * budget + NL)
        over = [f for f in lint.run(tmp_path) if "doctrine-budget" in f]
        assert len(over) == 1 and "example-skill" in over[0], over
        # Exactly at the budget, not under it: this is the arm that catches a
        # guard drifting to >=, and a cell sitting five chars from its cap
        # makes landing on the boundary an ordinary next edit.
        _write_cell(skill, "x" * budget)
        assert [f for f in lint.run(tmp_path) if "doctrine-budget" in f] == []
    finally:
        lint.CELL_BODY_BUDGET_CHARS = original


def test_every_budgeted_cell_exists_in_this_repository():
    """A rename would drop the budget in silence.

    The guard skips a cell it cannot find, because a tree without that cell is
    an ordinary tree and every fixture is one. That makes absence invisible
    exactly where it matters -- here, against the real tree, where the map's
    keys have an answer.
    """
    root = Path(__file__).resolve().parents[2]
    for rel in lint.CELL_BODY_BUDGET_CHARS:
        assert (root / rel).is_file(), f"{rel} carries a body budget and does not exist"


def test_the_declared_cell_body_budgets_are_the_ones_these_tests_pin():
    assert lint.CELL_BODY_BUDGET_CHARS == {"skills/authoring/SKILL.md": 7_359}


def test_the_declared_charter_budget_is_the_one_these_tests_pin():
    """The rule stated just above, applied to the constant the fix that
    stated it left deriving its bound from itself.
    """
    assert lint.CHARTER_BUDGET_CHARS == 5_600


def test_cell_frontmatter_fires_above_the_description_ceiling(tmp_path):
    make_clean_tree(tmp_path)
    _set_description(tmp_path, "x" * 701)
    findings = [f for f in lint.run(tmp_path) if "cell-frontmatter" in f]
    assert len(findings) == 1 and "budget" in findings[0]


def test_cell_frontmatter_allows_a_description_at_the_ceiling(tmp_path):
    make_clean_tree(tmp_path)
    _set_description(tmp_path, "x" * 700)
    assert [f for f in lint.run(tmp_path) if "cell-frontmatter" in f] == []


def test_the_charter_cell_may_hold_nothing_but_its_skill_file(tmp_path):
    """`skills/authoring` sends a cell's depth to `references/`; for this cell
    that instruction is a trap, because only SKILL.md is delivered, budgeted and
    read by the owner."""
    make_clean_tree(tmp_path)
    depth = tmp_path / "skills" / "charter" / "references"
    depth.mkdir(parents=True)
    (depth / "detail.md").write_text("A binding rule." + NL, encoding="utf-8")
    findings = [f for f in lint.run(tmp_path) if "the charter cell carries" in f]
    assert len(findings) == 1


def test_the_stray_check_compares_paths_rather_than_basenames(tmp_path):
    """`references/SKILL.md` shares the name and is exactly what an author
    following the depth instruction would create."""
    make_clean_tree(tmp_path)
    depth = tmp_path / "skills" / "charter" / "references"
    depth.mkdir(parents=True)
    (depth / "SKILL.md").write_text("A binding rule." + NL, encoding="utf-8")
    findings = [f for f in lint.run(tmp_path) if "the charter cell carries" in f]
    assert len(findings) == 1


def test_a_missing_hook_config_does_not_suppress_the_stray_check(tmp_path):
    """Two unrelated defects must both be reported; the hook config's absence
    once returned early and swallowed the other."""
    make_clean_tree(tmp_path)
    (tmp_path / "hooks" / "hooks.json").unlink()
    depth = tmp_path / "skills" / "charter" / "references"
    depth.mkdir(parents=True)
    (depth / "detail.md").write_text("A binding rule." + NL, encoding="utf-8")
    findings = lint.run(tmp_path)
    assert any("the charter cell carries" in f for f in findings)
    assert any("nothing delivers the charter" in f for f in findings)


def test_the_charter_cell_may_hold_only_its_skill_file_and_stays_quiet(tmp_path):
    make_clean_tree(tmp_path)
    assert [f for f in lint.run(tmp_path) if "the charter cell carries" in f] == []


def test_every_unconditional_yaml_indicator_is_a_hazard(tmp_path):
    """The set is a transcription of an external spec, so its failure mode is a
    silent omission -- a member never written has no per-member row to catch
    it. One loop over the unit catches every single-character drop. Transcribed
    independently on purpose: asserting equality against the production
    constant would share a source of truth with the thing it pins.
    """
    make_clean_tree(tmp_path)
    for c in ",[]{}#&*!|>%@`":
        _set_description(tmp_path, c + "leading value")
        findings = [f for f in lint.run(tmp_path) if "cell-frontmatter" in f]
        assert findings, f"{c!r} cannot open a plain scalar and must fire"


def test_the_conditional_indicators_fire_only_when_nothing_follows(tmp_path):
    """`-`, `?` and `:` are the ns-plain-first exceptions. Both polarities per
    character, which is what separates the two sets from each other."""
    make_clean_tree(tmp_path)
    for c in "-?:":
        # Both whitespace forms. A space is not enough on its own: for `:` the
        # later unquoted-`: ` check masks the drop, so a space-only row leaves
        # `:` unpinned in this set. A tab is caught by no later check.
        for gap in (" ", chr(9)):
            _set_description(tmp_path, c + gap + "a description")
            assert [f for f in lint.run(tmp_path) if "cell-frontmatter" in f], (c, gap)
        _set_description(tmp_path, c + "portable value")
        assert [f for f in lint.run(tmp_path) if "cell-frontmatter" in f] == [], c


def test_cell_frontmatter_checks_the_name_field_and_its_ceiling(tmp_path):
    """The field loop covers name and description; dropping `name` from it left
    the suite green, as did raising the name ceiling tenfold. The directory is
    named to match, so the name/directory check cannot be what fires.
    """
    make_clean_tree(tmp_path)
    over = "x" * 65
    skill = tmp_path / "skills" / over
    skill.mkdir(parents=True)
    _write_cell(skill, "# cell" + NL)
    findings = [f for f in lint.run(tmp_path) if "cell-frontmatter" in f]
    assert findings and not any("sits in" in f for f in findings), findings


def test_a_quoted_name_matching_its_directory_is_lawful(tmp_path):
    """`name: 'charter'` is lawful YAML and is where the guard's own printed
    remedy sends an author. Dropping the quote-strip flips it to firing."""
    make_clean_tree(tmp_path)
    cell = tmp_path / "skills" / "charter" / "SKILL.md"
    cell.write_text(
        cell.read_text(encoding="utf-8").replace(
            "name: charter", "name: 'charter'"),
        encoding="utf-8",
    )
    assert [f for f in lint.run(tmp_path) if "cell-frontmatter" in f] == []


def test_cell_frontmatter_checks_cells_other_than_the_charter(tmp_path):
    """The docstring's first line is a universal -- *every* skill. Narrowing the
    iteration to the charter cell left the suite green and would silently void
    the guard for every other shipped cell."""
    make_clean_tree(tmp_path)
    cell = tmp_path / "skills" / "example-skill" / "SKILL.md"
    cell.write_text(
        cell.read_text(encoding="utf-8").replace(
            "description: A fixture cell.",
            "description: Not a cell: it decides nothing."),
        encoding="utf-8",
    )
    findings = [f for f in lint.run(tmp_path) if "cell-frontmatter" in f]
    assert len(findings) == 1 and "example-skill" in findings[0], findings


# --- check_emitted_ascii ---------------------------------------------------
#
# Both polarities, because a guard that blocks lawful work fails as hard as one
# that passes unlawful work -- and here the lawful case is the interesting one:
# this repository's prose style is full of em dashes, and only the ones that
# can reach a stream are the rule's business.
#
# The fixtures build their non-ASCII character with chr() rather than writing
# it, so this file stays lawful under the check it is testing.

EM_DASH = chr(0x2014)


def _py(root: Path, name: str, body: str) -> None:
    (root / name).write_text(body, encoding="utf-8")


def test_emitted_ascii_catches_a_message_that_cannot_survive_capture(tmp_path):
    """The failing case from #147: a guard's own message, garbled when piped."""
    _py(tmp_path, "guard.py",
        "def fail():" + chr(10)
        + "    print('version-bump: 1 file changed " + EM_DASH + " bump the version')" + chr(10))
    findings = [f for f in lint.check_emitted_ascii(tmp_path) if "emitted-ascii" in f]
    assert len(findings) == 1, findings
    assert "guard.py:2" in findings[0]
    assert "U+2014" in findings[0] and "EM DASH" in findings[0]
    assert findings[0].isascii(), "the finding cannot itself carry what it forbids"


def test_emitted_ascii_leaves_docstrings_and_comments_alone(tmp_path):
    """Neither reaches a stream, so the house style is free in both."""
    _py(tmp_path, "prose.py",
        '"""A module docstring ' + EM_DASH + ' with an em dash."""' + chr(10)
        + "# A comment " + EM_DASH + " also with one." + chr(10)
        + "def f():" + chr(10)
        + '    """A function docstring ' + EM_DASH + ' and another."""' + chr(10)
        + "    return 1" + chr(10))
    assert lint.check_emitted_ascii(tmp_path) == []


def test_emitted_ascii_catches_the_escaped_form(tmp_path):
    """The check reads decoded values, so writing the escape does not evade it.

    This is not hypothetical: one of the messages this change rewrote was
    written as the six-character escape and was invisible to a search for the
    character, while reaching the stream as the character all the same.
    """
    _py(tmp_path, "escaped.py",
        "print('decision-index: no row " + chr(92) + "u2014 unreachable')" + chr(10))
    findings = lint.check_emitted_ascii(tmp_path)
    assert len(findings) == 1, findings
    assert "U+2014" in findings[0]


def test_emitted_ascii_ignores_a_directory_named_like_a_module(tmp_path):
    """`rglob('*.py')` matches directories too, and reading one raises.

    Found by an unrelated delivery test that creates exactly this shape. A
    guard that crashes on a tree is worse than one that misses a finding: it
    takes every other check down with it.
    """
    (tmp_path / "notamodule.py").mkdir()
    assert lint.check_emitted_ascii(tmp_path) == []


# --- check_docstring_not_piped, check_stdio_wired ---------------------------
#
# Both polarities again, and for check 12 the lawful polarity that was missing
# the first time: a non-docstring string that is data rather than output. Its
# absence is not a hypothetical gap -- it is why a fixture got rewritten wrong
# and a regression test went inert while the suite stayed green.


def _zoned(root: Path, rel: str, body: str) -> None:
    """Write a module inside a zone the zone-scoped checks actually walk."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_docstring_piped_to_argparse_is_caught(tmp_path):
    """--help writes __doc__ to stdout before any stream setup can run."""
    _zoned(tmp_path, "tools/script.py",
           '"""Module prose."""' + chr(10)
           + "import argparse" + chr(10)
           + "def main():" + chr(10)
           + "    utf8_stdio()" + chr(10)
           + "    argparse.ArgumentParser(description=__doc__)" + chr(10))
    findings = lint.check_docstring_not_piped(tmp_path)
    assert len(findings) == 1, findings
    assert "tools/script.py" in findings[0] and "docstring-piped" in findings[0]


def test_an_explicit_description_is_left_alone(tmp_path):
    """The lawful form: help text written as help text."""
    _zoned(tmp_path, "tools/script.py",
           '"""Module prose."""' + chr(10)
           + "import argparse" + chr(10)
           + "def main():" + chr(10)
           + "    utf8_stdio()" + chr(10)
           + '    argparse.ArgumentParser(description="What it does.")' + chr(10))
    assert lint.check_docstring_not_piped(tmp_path) == []


def test_stdio_unwired_main_is_caught(tmp_path):
    """A script whose entry point never sets its streams up."""
    _zoned(tmp_path, "tools/script.py",
           "def main():" + chr(10) + "    print('x')" + chr(10))
    findings = lint.check_stdio_wired(tmp_path)
    assert len(findings) == 1, findings
    assert "stdio-unwired" in findings[0]


def test_stdio_wired_late_is_still_unwired(tmp_path):
    """Ordering is the point: --help exits inside parse_args.

    A call placed after argument parsing is a call the help path never reaches,
    which is exactly how one script here kept a helper and leaked anyway.
    """
    _zoned(tmp_path, "tools/script.py",
           "def main():" + chr(10)
           + "    args = parse()" + chr(10)
           + "    utf8_stdio()" + chr(10))
    findings = lint.check_stdio_wired(tmp_path)
    assert len(findings) == 1, findings


def test_stdio_wired_first_is_left_alone(tmp_path):
    """The lawful form, including past a docstring."""
    _zoned(tmp_path, "tools/script.py",
           "from winio import utf8_stdio" + chr(10)
           + "def main():" + chr(10)
           + '    """What it does."""' + chr(10)
           + "    utf8_stdio()" + chr(10)
           + "    print('x')" + chr(10))
    assert lint.check_stdio_wired(tmp_path) == []


def test_a_module_without_main_is_not_asked(tmp_path):
    """Not every module is a script, and a library owes no stream setup."""
    _zoned(tmp_path, "tools/helper.py", "def helper():" + chr(10) + "    return 1" + chr(10))
    assert lint.check_stdio_wired(tmp_path) == []


def test_emitted_ascii_reports_the_line_carrying_the_character(tmp_path):
    """Not the line the constant opens on.

    CPython folds implicit concatenation into one node, which is the shape of
    nearly every message here. Reporting the opening line sent a reader to a
    line with nothing wrong on it -- 12 of the 44 findings on the tree that
    motivated this check.
    """
    _py(tmp_path, "wrapped.py",
        "MSG = (" + chr(10)
        + '    "first line is clean "' + chr(10)
        + '    "second line has ' + EM_DASH + ' one"' + chr(10)
        + ")" + chr(10))
    findings = lint.check_emitted_ascii(tmp_path)
    assert len(findings) == 1, findings
    assert "wrapped.py:3" in findings[0], findings[0]


def test_emitted_ascii_reports_in_line_order(tmp_path):
    """`ast.walk` is breadth-first, so depth beat line and output was unsorted."""
    _py(tmp_path, "many.py",
        "A = " + repr("one " + EM_DASH) + chr(10)
        + "B = [" + repr("two " + EM_DASH) + "]" + chr(10)
        + "C = {'k': [" + repr("three " + EM_DASH) + "]}" + chr(10))
    # Not f.split(":")[1] -- that yields the filename, and on Windows an
    # absolute path would yield the drive letter. The cold consumer who
    # first used this check made exactly that mistake reading its output.
    findings = lint.check_emitted_ascii(tmp_path)
    lines = [int(re.search(r"many\.py:(\d+) ", f).group(1)) for f in findings]
    assert lines == sorted(lines), lines


def test_emitted_ascii_leaves_a_non_emitting_data_string_flagged_but_says_so(tmp_path):
    """The lawful-polarity case the first version of this check never probed.

    A filename fixture cannot reach a stream, and the check flags it anyway --
    it reads literals, not reachability. That is allowed to be true; what is
    not allowed is the message claiming otherwise, because a session that
    believes it reasons about the wrong thing and rewrites the wrong code.
    """
    _py(tmp_path, "data.py", "NAME = " + repr("caf" + chr(0xE9) + ".md") + chr(10))
    findings = lint.check_emitted_ascii(tmp_path)
    assert len(findings) == 1, findings
    assert "non-docstring string constant" in findings[0]
    assert "reach a stream" not in findings[0], (
        "the message must not claim a reachability property the check never computes"
    )


def test_emitted_ascii_reports_a_file_it_cannot_parse(tmp_path):
    """A silent skip is indistinguishable from a clean tree."""
    _py(tmp_path, "broken.py", "def (:" + chr(10))
    findings = lint.check_emitted_ascii(tmp_path)
    assert len(findings) == 1 and "does not parse" in findings[0], findings


def test_emitted_ascii_sees_through_a_utf8_bom(tmp_path):
    """A BOM made `ast.parse` raise, and the file was skipped in silence.

    The compensating control claimed at the time -- that the suite fails on a
    module it cannot import -- was false: CPython strips the BOM when reading
    from disk, so the module ran and emitted the byte.
    """
    (tmp_path / "bommed.py").write_bytes(
        chr(0xFEFF).encode("utf-8") + ("X = " + repr("a " + EM_DASH) + chr(10)).encode("utf-8"))
    findings = lint.check_emitted_ascii(tmp_path)
    assert len(findings) == 1 and "U+2014" in findings[0], findings


def test_emitted_ascii_reports_a_file_that_is_not_utf8(tmp_path):
    """Reported as undecodable, not as stating U+FFFD.

    `errors="replace"` made the check name a character that appears nowhere in
    the file, so the reader had nothing to search for.
    """
    (tmp_path / "latin.py").write_bytes(
        b"# -*- coding: latin-1 -*-" + chr(10).encode() + b"X = 'caf\xe9'" + chr(10).encode())
    findings = lint.check_emitted_ascii(tmp_path)
    assert len(findings) == 1, findings
    assert "not valid UTF-8" in findings[0] and "FFFD" not in findings[0]

def test_a_local_utf8_stdio_does_not_satisfy_the_wiring_check(tmp_path):
    """Position was exact; identity was not, and the prose claimed both.

    A module defining its own no-op utf8_stdio satisfied the call site while
    setting nothing up -- so the guard reported green on precisely the tree it
    exists to catch, and the likeliest route to writing that stub is a reader
    who could not work out the import from the finding message.
    """
    _zoned(tmp_path, "tools/impostor.py",
           "def utf8_stdio():" + chr(10)
           + "    pass" + chr(10)
           + "def main():" + chr(10)
           + "    utf8_stdio()" + chr(10))
    findings = lint.check_stdio_wired(tmp_path)
    assert len(findings) == 1, findings
    assert "never imports it" in findings[0], findings[0]


def test_epilog_piped_to_argparse_is_caught(tmp_path):
    """argparse writes epilog to stdout exactly as it writes description.

    It is also the conventional home for the long-form prose a module
    docstring holds, so it is the compliant-looking route to the same defect.
    """
    _zoned(tmp_path, "tools/script.py",
           '"""Module prose."""' + chr(10)
           + "import argparse" + chr(10)
           + "def main():" + chr(10)
           + "    utf8_stdio()" + chr(10)
           + "    argparse.ArgumentParser(epilog=__doc__)" + chr(10))
    findings = lint.check_docstring_not_piped(tmp_path)
    assert len(findings) == 1, findings
    assert "epilog" in findings[0], findings[0]

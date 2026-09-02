"""Tests for the packaging lint. Each fixture builds a minimal tree in
tmp_path so every check is proven to fire and to stay quiet, per check.
The evasion-form cases exist because the 2026-08-15 adversarial review
showed the original regexes missed every relative, uppercase, and
backslash form (findings M1/M2/M4/M5/M6 in docs/ledger.jsonl)."""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import figures  # noqa: E402
import lint
import roster


NL = chr(10)
BS = chr(92)


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
    _wire_charter(root)
    _write_marketplace(root, "./")
    # A conforming tree carries the roster its cells generate, for the same
    # reason the pointer above has a target: the fixture models a lawful tree,
    # not one whose parts merely exist. Generated rather than hand-written, so
    # a fixture cell added later is covered by regenerating rather than by
    # remembering what the entry looks like.
    roster.write(root)


def _wire_charter(root: Path) -> None:
    """The single charter source, wired the way the repository carries it."""
    charter = root / "skills" / "charter"
    charter.mkdir(parents=True, exist_ok=True)
    (charter / "SKILL.md").write_text(
        "---" + chr(10) + "name: charter" + chr(10)
        + "description: The binding rules." + chr(10) + "---" + chr(10) + chr(10)
        + "# charter" + chr(10) + "The binding half." + chr(10),
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


def _write_marketplace(root: Path, source) -> None:
    marketplace = root / ".claude-plugin"
    marketplace.mkdir(exist_ok=True)
    (marketplace / "marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "tradecraft", "source": source}]}) + NL,
        encoding="utf-8",
    )


def test_clean_tree_passes(tmp_path):
    make_clean_tree(tmp_path)
    assert lint.run(tmp_path) == []


# --- zone wall -------------------------------------------------------------

def test_charter_cell_fires_when_the_charter_is_missing(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "skills" / "charter" / "SKILL.md").unlink()
    findings = lint.run(tmp_path)
    assert any("charter-cell" in f and "missing" in f for f in findings)
    # The import guard fires too, and should: AGENTS.md now names a file
    # that is not there. Two guards, one cause, both worth hearing.
    assert any("doctrine-import" in f for f in findings)


def test_charter_cell_fires_when_the_charter_is_empty(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "skills" / "charter" / "SKILL.md").write_text("\n\n", encoding="utf-8")
    findings = lint.run(tmp_path)
    # Two guards, one cause: no adopted body, and no header to index by.
    assert any("charter-cell" in f and "no body" in f for f in findings)
    assert any("cell-frontmatter" in f for f in findings)


def test_charter_cell_stays_quiet_on_a_wired_tree(tmp_path):
    make_clean_tree(tmp_path)
    assert lint.run(tmp_path) == []


def test_marketplace_source_is_the_exact_codex_discovery_string(tmp_path):
    """Both polarities of the Codex compatibility boundary: Claude's object
    form is valid there but undiscoverable in Codex; the relative string is
    accepted by both runtimes."""
    make_clean_tree(tmp_path)
    _write_marketplace(tmp_path, {"source": "directory", "path": "./"})
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "source must be the string `./`" in findings[0]

    _write_marketplace(tmp_path, "./")
    assert lint.run(tmp_path) == []


def test_marketplace_source_requires_the_manifest_and_tradecraft_entry(tmp_path):
    """The exact-source guard must fail closed when there is no source to inspect."""
    make_clean_tree(tmp_path)
    manifest = tmp_path / ".claude-plugin" / "marketplace.json"
    manifest.unlink()
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "marketplace.json is missing" in findings[0]

    manifest.write_text(json.dumps({"plugins": []}) + NL, encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "no tradecraft plugin entry" in findings[0]


@pytest.mark.parametrize(
    "content, expected",
    [
        ("not json", "not valid JSON"),
        (json.dumps([]), "must be an object"),
        (json.dumps({"plugins": {}}), "'plugins' must be a list"),
    ],
)
def test_marketplace_source_rejects_uninspectable_manifests(tmp_path, content, expected):
    make_clean_tree(tmp_path)
    (tmp_path / ".claude-plugin" / "marketplace.json").write_text(
        content + NL, encoding="utf-8"
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and expected in findings[0]


def test_marketplace_source_reports_a_failed_read(tmp_path, monkeypatch):
    make_clean_tree(tmp_path)
    manifest = tmp_path / ".claude-plugin" / "marketplace.json"
    original_read_text = Path.read_text

    def denied(path, *args, **kwargs):
        if path == manifest:
            raise PermissionError("probe denied")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", denied)
    findings = lint.check_marketplace_source(tmp_path)
    assert len(findings) == 1
    assert "cannot be read" in findings[0] and "probe denied" in findings[0]


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


def test_sideways_deps_reaches_the_charter(tmp_path):
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
    silently disagrees is how new shipped directories can enter the zone
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


def test_sideways_dep_names_the_directory_it_came_from(tmp_path):
    """The scan list grew past `lib/`, and the label did not, so every finding
    outside it claimed to come from `lib/`. A synthetic `hooks/` directory
    exercises the non-skill branch even though this tree ships no hook."""
    make_clean_tree(tmp_path)
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "README.md").write_text(
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


def test_harness_token_has_no_hook_exemption(tmp_path):
    """A hook fallback would fork the adoption flow, so it gets no exception."""
    make_clean_tree(tmp_path)
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "hooks.json").write_text(
        '{"hooks": {"SessionStart": [{"matcher": "*", "hooks": [{"type": '
        '"command", "command": "cat ${CLAUDE_PLUGIN_ROOT}/skills/charter/SKILL.md"'
        "}]}]}}\n",
        encoding="utf-8",
    )
    findings = [f for f in lint.run(tmp_path) if "harness-token" in f]
    assert len(findings) == 1


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


def test_hooks_may_reference_no_skill(tmp_path):
    """A hook is not a cell, so even the charter would be a sideways dependency."""
    make_clean_tree(tmp_path)
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    readme = hooks / "README.md"
    readme.write_text("Emits the `charter` cell on stdout.\n", encoding="utf-8")
    findings = [f for f in lint.run(tmp_path) if "sideways-dep" in f]
    assert len(findings) == 1 and "from hooks/" in findings[0]
    readme.write_text("Emits the `example-skill` cell on stdout.\n", encoding="utf-8")
    findings = [f for f in lint.run(tmp_path) if "sideways-dep" in f]
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
    "check_zone_wall",
    "check_harness_tokens",
    "check_charter_cell",
    "check_cell_frontmatter",
    "check_project_roster",
    "check_sideways_deps",
    "check_cell_references",
    "check_doctrine_citations",
    "check_doctrine_references",
    "check_doctrine",
    "check_doctrine_callout",
    "check_review_index",
    "check_decision_index",
    "check_entry_references",
    "check_emitted_ascii",
    "check_docstring_not_piped",
    "check_stdio_wired",
    "check_subprocess_streams",
    "check_docstring_control_chars",
    "check_hollow_code_span",
    "check_committed_carriage_return",
    "check_marketplace_source",
    "check_body_strip_owner",
    "check_always_on_budget",
)


def test_the_module_docstring_enumerates_every_check_run_calls():
    """The check list is the module's contract; nothing pinned it.

    Count and order only, deliberately -- pinning the prose would go red on
    every rewording and be deleted within a release. It does not catch a wrong
    *description* inside an item; that is a separate class, and this change
    once carried an instance of it (check 5 and its implementation disagreed).

    Read from `lint.CHECKS` rather than scraped out of `run()`'s source. The
    chain became a tuple when the checks were isolated from one another
    (#239), so the source no longer names them -- and the scrape was reading
    prose as well as calls, which a docstring naming a sibling check would
    have broken.
    """
    called = tuple(check.__name__ for check in lint.CHECKS)
    assert called == LINT_CHECKS_IN_ORDER, (
        "CHECKS names checks this list does not, or in another order"
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


def test_a_doctrine_path_that_resolves_is_not_a_finding(tmp_path):
    """The lawful polarity, and the one that decides the guard's worth: the
    doctrine names seven repo paths that all resolve, so a guard reddening on
    any of them would block every future doctrine edit."""
    make_clean_tree(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(agents.read_text(encoding="utf-8")
                      + "Argue it against `docs/values.md`, by number." + NL,
                      encoding="utf-8")
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "values.md").write_text("# Values" + NL,
                                                 encoding="utf-8")
    assert lint.run(tmp_path) == []


def test_a_doctrine_path_that_resolves_to_nothing_is_a_finding(tmp_path):
    """The gap this guard closes, in the shape it was found in: repointing the
    doctrine's own `docs/values.md` mention at a path that does not exist left
    lint green and the suite passing, while the identical break inside a
    decision entry fired. The guarded surface was the frozen record and the
    unguarded one was the live rule."""
    make_clean_tree(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(agents.read_text(encoding="utf-8")
                      + "Argue it against `docs/valuez.md`, by number." + NL,
                      encoding="utf-8")
    findings = lint.run(tmp_path)
    assert len(findings) == 1
    assert "doctrine-reference" in findings[0]
    assert "docs/valuez.md" in findings[0]


def test_a_doctrine_path_broken_from_the_root_is_a_finding(tmp_path):
    """The doctrine writes its paths from the repository root, so that is the
    only base that answers the question. Inheriting the entry resolver's
    `skills/` leniency made the guard blind on `charter/SKILL.md` -- the
    shortened form a session under budget pressure reaches for, and the one
    path whose death takes the charter with it."""
    make_clean_tree(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(agents.read_text(encoding="utf-8")
                      + "Read `charter/SKILL.md` now." + NL, encoding="utf-8")
    findings = lint.run(tmp_path)
    assert any("doctrine-reference" in f and "charter/SKILL.md" in f
               for f in findings)


def test_a_dead_doctrine_path_inside_a_fence_is_a_finding(tmp_path):
    """Fences included, per this module's own rule: a path that does not
    resolve is broken whatever encloses it, and this repository's fenced blocks
    are calling contracts rather than examples."""
    make_clean_tree(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(agents.read_text(encoding="utf-8")
                      + "```" + NL + "run `docs/gone.md`" + NL + "```" + NL,
                      encoding="utf-8")
    findings = lint.run(tmp_path)
    assert any("doctrine-reference" in f and "docs/gone.md" in f
               for f in findings)


def test_the_doctrine_reference_guard_reads_the_pointer_too(tmp_path):
    """Both doctrine files, for the reason the citation guard reads both: a
    rule can move between them and the guard must not follow it only one way."""
    make_clean_tree(tmp_path)
    pointer = tmp_path / "CLAUDE.md"
    pointer.write_text(pointer.read_text(encoding="utf-8")
                       + "See `docs/gone.md`." + NL, encoding="utf-8")
    findings = lint.run(tmp_path)
    assert any("doctrine-reference: CLAUDE.md" in f for f in findings)


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
    assert "always-on surface here, per runtime:" in out
    assert "for an adopter" in out and "not derived" not in out
    # **Every runtime is named, and its own total is beside its name.** This
    # asserted only that the substring was present, so it stayed green while
    # the line printed one scalar that was some other runtime's -- the state
    # every seat of PR #278's panel and the external pass reported, on a tree
    # with zero findings. The number reaching the session doing the editing
    # has to be that session's. [PR #278 review, M1]
    for surface in roster.SURFACES:
        assert surface.runtime in out, (
            f"{surface.runtime} reads this line and is not named on it")
    assert out.count("= doctrine ") == len(roster.SURFACES), (
        "one decomposed total per runtime, so a reader can take its own")


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


def test_depth_pointing_at_its_sibling_depth_is_resolved(tmp_path):
    """The relative form, which the bare-pointer branch cannot see.

    From inside references/ the bare form resolves to
    references/references/x.md, so a cell whose depth cites its own sibling
    depth has to write `../references/x.md` -- and the bare branch skips it,
    reading the `../` prefix as more path and the whole thing as somebody
    else's tree. That skip was silent until #177 shed five files of depth and
    wrote the tree's first sibling pointers: renaming a target left the suite
    green. Both arms, because a guard that fires on a live pointer is as bad
    as one that misses a dead one.
    """
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    depth = skill / "references"
    depth.mkdir(parents=True, exist_ok=True)
    (depth / "detail.md").write_text("# Detail" + NL, encoding="utf-8")
    _write_cell(skill, "Depth lives in references/detail.md." + NL)

    (depth / "sibling.md").write_text(
        "See ../references/detail.md." + NL, encoding="utf-8")
    assert [f for f in lint.run(tmp_path) if "reference-pointer" in f] == []

    # With the full stop that ends the sentence, which is how a pointer is
    # actually written. A suffix test over RELATIVE_REF's match answers "not
    # markdown" here, because its trailing class swallows the stop -- the
    # first version of this guard did exactly that and this arm caught it.
    (depth / "sibling.md").write_text(
        "See ../references/gone.md." + NL, encoding="utf-8")
    findings = [f for f in lint.run(tmp_path) if "reference-pointer" in f]
    assert len(findings) == 1 and "../references/gone.md" in findings[0], findings
    assert "gone.md." not in findings[0], findings


def test_a_relative_reference_out_of_the_cell_is_not_this_guard_s(tmp_path):
    """One defect, one finding.

    A relative reference that leaves the cell is unlawful whether or not it
    resolves -- the zone wall's, or the sideways rule's -- so adding an
    existence check over the same text would price one defect as two. The
    bound is the naming file's own cell, which is why a target one directory
    up inside the same cell still fires above.
    """
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    depth = skill / "references"
    depth.mkdir(parents=True, exist_ok=True)
    other = tmp_path / "skills" / "other-skill"
    other.mkdir(parents=True, exist_ok=True)
    _write_cell(other, "A sibling cell." + NL)
    _write_cell(skill, "Nothing to see." + NL)
    (depth / "sibling.md").write_text(
        "See ../../other-skill/references/gone.md." + NL, encoding="utf-8")
    findings = lint.run(tmp_path)
    assert [f for f in findings if "reference-pointer" in f] == [], findings
    # The other half of the bound, which this test asserted nowhere until #193's
    # review: it is lawful for THIS guard to stay quiet only because another one
    # speaks. Without this line the test passes against the pre-fix lint and
    # would keep passing if check_sideways_deps were later narrowed until
    # nothing caught the text -- turning a deliberate bound into a silent gap.
    assert [f for f in findings if "sideways-dep" in f], findings


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


def test_a_row_appended_past_the_cutover_is_obliged(tmp_path):
    """The behavioural pin on the cutover constant. Deliberately *not* an
    assertion that it equals the index's row count: that goes stale the moment
    the next row lands, turning the guard into the bookkeeping the tripwire
    deletes. Raising the constant silently readmits the retired shape into a
    file nobody may edit, and only this catches it.

    The row appended here is the shape every row before the cutover carries, so
    it is what a session copying the row above it would write."""
    bare = json.dumps(_review_row(artifact="pr-next")) + "\n"
    root = _index_tree(tmp_path, extra=bare)
    findings = lint.check_review_index(root)
    assert len(findings) == 4, findings
    assert any("highs" in f for f in findings)
    assert any("external" in f for f in findings)
    assert any("retired" in f and "seats" in f for f in findings)
    assert any("staffing" in f for f in findings)


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
    # Discriminating only since the cutover: one position earlier the appended
    # row is pre-cutover, so it owes dispositions and facing and carries `seats`
    # lawfully -- the appended row then lacks the new qualitative obligations
    # and carries no retired-shape finding at all.
    assert any("retired" in f for f in findings), findings
    assert len([f for f in findings if "missing field" in f]) == 3, findings


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


def test_a_real_qualitative_row_appended_to_the_index_is_lawful(tmp_path):
    """The green half of the cutover pin, through the repository's own index.

    Were the cutover set past the file's actual row count, the next lawful row
    a session writes would red and the guard would be demanding the very shape
    this change retired. The other direction -- a cutover set too low, which
    re-classes rows already in the file -- is caught by
    `test_every_row_already_in_the_repo_index_stays_valid`, not by the sibling
    immediately above this one."""
    row = json.dumps(_qualitative_row(artifact="pr-next")) + "\n"
    root = _index_tree(tmp_path, extra=row)
    assert lint.check_review_index(root) == []


def test_external_pass_cannot_reenter_the_qualitative_row_as_arithmetic(tmp_path):
    """The external outcome is qualitative, not a revived seat or count."""
    counts = {"raw": 1, "merged": 1, "sustained": 1, "high": 0}
    bad = _qualitative_row(artifact="pr-next", seats={"external": counts})
    root = _index_tree(tmp_path, extra=json.dumps(bad) + NL)
    findings = lint.check_review_index(root)
    assert any("retired counting field(s) seats" in f for f in findings)

    good = _qualitative_row(
        artifact="pr-next",
        external="self-invoked review posted two findings; both were fixed",
    )
    (root / "docs" / "reviews.jsonl").write_text(
        _real_index_rows() + json.dumps(good) + NL,
        encoding="utf-8",
    )
    assert lint.check_review_index(root) == []


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
def test_frontmatter_stripper_produces_the_expected_body(document, expected):
    """Literal answers keep the implementation from becoming its own oracle."""
    assert lint._frontmatterless(document) == expected


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
    assert lint.ALWAYS_ON_ROW_BUDGET_CHARS == 16_345, (
        "ALWAYS_ON_ROW_BUDGET_CHARS is the larger always-on row plus one unit, "
        "and the unit is what a rule costs in the shape this repository makes "
        "rules take -- the median cell's name plus description, to the next "
        "hundred. It is not a rounder number chosen for comfort: headroom and "
        "the largest tolerated relocation are the same quantity, so raising "
        "this admits a larger relocate-then-refill by the same amount. Both "
        "directions have a behavioural arm below; a raise is caught by "
        "test_raising_the_row_budget_admits_a_relocation_it_should_refuse."
    )
    assert lint.ALWAYS_ON_ADOPTER_BUDGET_CHARS == 11_508
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
    assert lint.CELL_BODY_BUDGET_CHARS == {
        "skills/adversarial-review/SKILL.md": 9_000,
        "skills/authoring/SKILL.md": 7_359,
    }


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


# --- check_subprocess_streams -----------------------------------------------
#
# The rule is *redirect nothing, or name all three*, and the first version of
# this check asked only for stdin -- which flagged immune launches and
# prescribed the edit that breaks them (PR #232 review, M1). So the polarities
# here are three, not two: the partial redirect caught, the bare launch left
# alone, and the fully-named launch left alone. Every spelling below that
# escaped the first version is pinned, because each was found by a seat or an
# external reviewer rather than anticipated: the module alias, `stdin=None`,
# `input=None`, and the `getoutput` family. [D-232]


def _streams(root):
    return lint.check_subprocess_streams(root)


def test_a_partial_redirect_is_caught(tmp_path):
    """The shape #229 actually measured: stdout and stderr redirected, stdin
    left to resolve through a std-handle table that may name a closed handle."""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git", "status"], capture_output=True)' + chr(10))
    findings = _streams(tmp_path)
    assert len(findings) == 1, findings
    assert "subprocess-streams" in findings[0]
    assert "tools/script.py:2" in findings[0]
    assert "stdin unnamed" in findings[0]


def test_a_launch_that_redirects_nothing_is_left_alone(tmp_path):
    """The polarity the first version got wrong, and the reason it mattered.

    `_get_handles` returns early when all three are None, so this launch never
    asks `GetStdHandle` anything. Requiring `stdin=` here reddened a call that
    could not fail and prescribed the one edit that makes it fail -- 0/20
    against 20/20 under real pytest capture. A guard that blocks lawful work
    fails as hard as one that passes unlawful work."""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git", "add", "-A"], check=True)' + chr(10))
    assert _streams(tmp_path) == []


def test_all_three_named_is_left_alone(tmp_path):
    """The compliant form every launch in this repository uses."""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git"], stdin=subprocess.DEVNULL,' + chr(10)
           + "               capture_output=True)" + chr(10))
    assert _streams(tmp_path) == []


def test_the_shipped_zone_is_walked_too(tmp_path):
    """`persist.py` and `figures.py` are shipped, and a consumer running one
    on Windows hits this before any test does. A check that only walked the
    repo-only zone would have left the half that reaches consumers open."""
    _zoned(tmp_path, "skills/thing/scripts/thing.py",
           "import subprocess" + chr(10)
           + 'subprocess.Popen(["git"], stdout=subprocess.PIPE)' + chr(10))
    findings = _streams(tmp_path)
    assert len(findings) == 1, findings
    assert "skills/thing/scripts/thing.py" in findings[0]


def test_the_module_alias_is_caught(tmp_path):
    """`import subprocess as sp` -- the hole the first version shipped.

    Three seats and both external reviewers found it independently, which is
    what makes it worth a pin rather than a line in a bounds list."""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess as sp" + chr(10)
           + 'sp.run(["git", "status"], capture_output=True)' + chr(10))
    findings = _streams(tmp_path)
    assert len(findings) == 1, findings
    assert "sp.run" in findings[0]


def test_the_bare_imported_name_is_caught(tmp_path):
    """`from subprocess import run` binds a name no attribute match reaches."""
    _zoned(tmp_path, "tools/script.py",
           "from subprocess import run" + chr(10)
           + 'run(["git", "status"], capture_output=True)' + chr(10))
    findings = _streams(tmp_path)
    assert len(findings) == 1, findings
    assert "calls run redirecting" in findings[0]


def test_the_bare_name_remedy_does_not_name_a_module_it_lacks(tmp_path):
    """The message must not prescribe `subprocess.DEVNULL` into a file with no
    `subprocess` binding.

    It did: the remedied file passed the lint and raised `NameError` on its
    first call, so a green lint positively confirmed a broken edit. [PR #232
    review, M15]"""
    _zoned(tmp_path, "tools/script.py",
           "from subprocess import run" + chr(10)
           + 'run(["git"], capture_output=True)' + chr(10))
    finding = _streams(tmp_path)[0]
    assert "subprocess.DEVNULL" not in finding
    assert "import from subprocess" in finding


def test_an_alias_remedy_names_the_alias(tmp_path):
    """The other half of the same rule: where the module is bound, the message
    names the binding the file actually has."""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess as sp" + chr(10)
           + 'sp.run(["git"], capture_output=True)' + chr(10))
    assert "sp.DEVNULL" in _streams(tmp_path)[0]


def test_stdin_none_does_not_satisfy_it(tmp_path):
    """`stdin=None` is the default spelled out; it redirects nothing.

    Read as merely *named*, it satisfied the first version while meaning
    inherit -- 10/10 failures under a stale table. [PR #232 review, M3]"""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git"], stdin=None, capture_output=True)' + chr(10))
    assert len(_streams(tmp_path)) == 1


def test_input_none_does_not_satisfy_it(tmp_path):
    """`input=None` never reaches `run`'s `if input is not None`, so no PIPE.

    An external reviewer contested this with a cited answer saying `input=None`
    behaves as `input=b''`. `subprocess.run`'s own source says otherwise, and
    the probes agree at 10/10 -- so this pins the source, not the answer."""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git"], input=None, capture_output=True)' + chr(10))
    assert len(_streams(tmp_path)) == 1


def test_a_real_input_covers_stdin(tmp_path):
    """`input=` with something to read implies `stdin=PIPE`.

    Not an accommodation: `check_ignored` in `tools/lint.py` feeds
    `git check-ignore --stdin` exactly this way, and it is one of the sites
    #229 never saw fail."""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git"], input="x", capture_output=True)' + chr(10))
    assert _streams(tmp_path) == []


def test_capture_output_false_redirects_nothing(tmp_path):
    """The literal is read, not merely the keyword: `capture_output=False`
    leaves stdout and stderr inherited, so this launch redirects nothing."""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git"], capture_output=False)' + chr(10))
    assert _streams(tmp_path) == []


def test_the_no_stdin_wrappers_are_named(tmp_path):
    """`getoutput`, `getstatusoutput` and `os.popen` redirect a stream and take
    no stdin argument, so the rule has no compliant form for them.

    Silence there read as permission, and the cell's rule was unsatisfiable
    rather than merely unenforced. [PR #232 review, M4]"""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess" + chr(10)
           + "import os" + chr(10)
           + 'subprocess.getoutput("git rev-parse HEAD")' + chr(10)
           + 'subprocess.getstatusoutput("git status")' + chr(10)
           + 'os.popen("git status").read()' + chr(10))
    findings = _streams(tmp_path)
    assert len(findings) == 3, findings
    assert all("takes no stdin argument" in f for f in findings)


def test_every_launcher_name_is_reached(tmp_path):
    """All five, not the two the first version's fixtures exercised.

    Narrowing `_LAUNCHERS` to `("run", "Popen")` left the whole suite green,
    so the coverage the docstring claimed was asserted and not held. [PR #232
    review, M12]"""
    body = "import subprocess" + chr(10)
    for name in ("run", "Popen", "call", "check_call", "check_output"):
        body += f'subprocess.{name}(["git"], stdout=subprocess.PIPE)' + chr(10)
    _zoned(tmp_path, "tools/script.py", body)
    findings = _streams(tmp_path)
    assert len(findings) == 5, findings
    for name in ("run", "Popen", "call", "check_call", "check_output"):
        assert any(f"subprocess.{name}" in f for f in findings), name


def test_the_message_offers_input_to_nobody_that_rejects_it(tmp_path):
    """`Popen`, `call` and `check_call` take no `input` argument.

    The first version's message offered it to all five, and D-232 rejects an
    alternative design on exactly that ground -- a remedy raising `TypeError`.
    [PR #232 review, M14]"""
    body = "import subprocess" + chr(10)
    for name in ("Popen", "call", "check_call"):
        body += f'subprocess.{name}(["git"], stdout=subprocess.PIPE)' + chr(10)
    _zoned(tmp_path, "tools/script.py", body)
    for finding in _streams(tmp_path):
        assert "input=" not in finding, finding


def test_a_kwargs_forwarder_is_left_alone(tmp_path):
    """The guard's stated bound, held as a test rather than left to the prose.

    Whether a stream is redirected cannot be read off the call, and a guard
    that reddened here would block lawful work -- the polarity the substrate
    cell says fails as hard as the other."""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess" + chr(10)
           + "def launch(cmd, **kwargs):" + chr(10)
           + "    return subprocess.run(cmd, **kwargs)" + chr(10))
    assert _streams(tmp_path) == []


def test_an_unreadable_capture_output_is_left_alone(tmp_path):
    """The bound's other half: a non-literal `capture_output` leaves the guard
    unable to say whether two streams are redirected, and unreadable is
    silence."""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess" + chr(10)
           + "def launch(cmd, quiet):" + chr(10)
           + "    return subprocess.run(cmd, capture_output=quiet)" + chr(10))
    assert _streams(tmp_path) == []


def test_something_else_named_run_is_not_a_launch(tmp_path):
    """`lint.run` exists in this repository and redirects nothing."""
    _zoned(tmp_path, "tools/script.py",
           "import other" + chr(10)
           + "other.run(1, capture_output=True)" + chr(10)
           + "run(2, capture_output=True)" + chr(10))
    assert _streams(tmp_path) == []


def test_check_output_bare_is_partial_not_bare(tmp_path):
    """`check_output` is `run(*popenargs, stdout=PIPE, ...)`, so it redirects a
    stream before any keyword is read.

    The cycle-one guard read "redirects nothing" off the keywords and certified
    this call, which measures 20/20 failures under real capture -- the shape
    the shipped cell calls lawful, reproduced inside the batch that closed the
    class. [PR #232 post-fix, P1]"""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.check_output(["git", "rev-parse", "HEAD"])' + chr(10))
    findings = _streams(tmp_path)
    assert len(findings) == 1, findings
    assert "stdin, stderr unnamed" in findings[0]


def test_check_output_naming_the_other_two_is_left_alone(tmp_path):
    """Its compliant form, measured 0/20 -- and the polarity that disproved the
    remedy of flagging `check_output` unconditionally."""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.check_output(["git"], stdin=subprocess.DEVNULL,' + chr(10)
           + "                        stderr=subprocess.DEVNULL)" + chr(10))
    assert _streams(tmp_path) == []


def test_check_output_is_never_told_to_name_all_three(tmp_path):
    """Naming `stdout` on `check_output` raises `ValueError`, and offering to
    redirect none of them is not on offer either."""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.check_output(["git"])' + chr(10))
    finding = _streams(tmp_path)[0]
    assert "redirect none of them" not in finding
    assert "stdout" not in finding.split("--")[0]


def test_input_none_pipes_on_check_output_but_not_on_run(tmp_path):
    """`check_output` rewrites `input=None` to `b''` before calling `run`, so
    unlike `run` it pipes stdin either way.

    Read uniformly, this reddened a call measured safe at 0/20. [PR #232
    post-fix, D1]"""
    _zoned(tmp_path, "tools/co.py",
           "import subprocess" + chr(10)
           + 'subprocess.check_output(["git"], input=None,' + chr(10)
           + "                        stderr=subprocess.DEVNULL)" + chr(10))
    assert _streams(tmp_path) == []
    _zoned(tmp_path, "tools/r.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git"], input=None, capture_output=True)' + chr(10))
    findings = [f for f in _streams(tmp_path) if "tools/r.py" in f]
    assert len(findings) == 1, findings


def test_capture_output_is_credited_on_run_alone(tmp_path):
    """`Popen`, `call` and `check_call` reject `capture_output` with a
    `TypeError`, so crediting it there certified a call that cannot run.
    [PR #232 post-fix, P3]"""
    body = "import subprocess" + chr(10)
    for name in ("Popen", "call", "check_call"):
        body += (f'subprocess.{name}(["git"], stdin=subprocess.DEVNULL,'
                 + " capture_output=True)" + chr(10))
    _zoned(tmp_path, "tools/script.py", body)
    findings = _streams(tmp_path)
    assert len(findings) == 3, findings


def test_a_positional_stream_is_unread_rather_than_absent(tmp_path):
    """`_redirected` reads keywords, so a positionally-passed stream is unread.

    Silence here is the deliberate kind, and the fixture is chosen so the two
    versions of the guard disagree: with a keyword alongside the positional
    streams, the old predicate saw one covered stream and reported a partial
    redirect, having read none of the positional ones. It reached the right
    verdict on the fixture without them only by luck -- `Popen(cmd, -1, None,
    DEVNULL)` measured 20/20 failures with the guard silent.

    **The trade is stated rather than hidden**: this call is genuinely unsafe
    and the guard now says nothing about it, where before it said something
    accidentally. Silence is the ruled remedy because the alternative reddens
    calls whose redirection cannot be read. [PR #232 post-fix, P2]"""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git"], -1, None, None, subprocess.PIPE,' + chr(10)
           + "               stdin=subprocess.DEVNULL)" + chr(10))
    assert _streams(tmp_path) == []


def test_a_splatted_argument_list_is_unread(tmp_path):
    """The other half of the same criterion."""
    _zoned(tmp_path, "tools/script.py",
           "import subprocess" + chr(10)
           + "def launch(args):" + chr(10)
           + "    return subprocess.run(*args, capture_output=True)" + chr(10))
    assert _streams(tmp_path) == []


def test_os_popen_is_caught_through_every_import_spelling(tmp_path):
    """`from os import popen` and `import os.path` both bind names the cycle-one
    resolution missed -- M2's class, on code the cycle-one fix added.
    [PR #232 post-fix, P2]"""
    _zoned(tmp_path, "tools/a.py",
           "from os import popen" + chr(10) + 'popen("git status")' + chr(10))
    _zoned(tmp_path, "tools/b.py",
           "import os.path" + chr(10) + 'os.popen("git status")' + chr(10))
    findings = _streams(tmp_path)
    assert len(findings) == 2, findings
    assert all("takes no stdin argument" in f for f in findings)


def test_this_repository_names_its_streams_at_every_launch():
    """The tree this exists for, not a restatement of the guard.

    The guard proves the shape; this proves the shipped and repo-only trees are
    in it -- which is the claim #229 found false and nothing was checking."""
    assert lint.check_subprocess_streams(Path(__file__).resolve().parents[2]) == []


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


# --- the qualitative row -----------------------------------------------------

def _qualitative_row(**overrides):
    row = {
        "date": "2026-08-26",
        "artifact": "pr-192",
        "lane": "panel",
        "highs": ["the guard let the retired shape back in"],
        "staffing": {"model": "claude-opus-5", "runtime": "claude-code (windows)"},
        "external": "configured reviewer posted no actionable findings",
        "report": "https://github.com/example/repo/pull/192#issuecomment-9",
    }
    row.update(overrides)
    return row


def _at_cutover(monkeypatch):
    """Every row in the fixture index is past the cutover, and past the
    boundary that obliges staffing."""
    monkeypatch.setattr(lint, "REVIEW_ROWS_QUALITATIVE", 0)
    monkeypatch.setattr(lint, "REVIEW_ROWS_EXTERNAL_QUALITATIVE", 0)
    monkeypatch.setattr(lint, "REVIEW_ROWS_GRANDFATHERED", 0)
    monkeypatch.setattr(lint, "REVIEW_ROWS_FACING_GRANDFATHERED", 0)


def test_qualitative_row_is_clean(tmp_path, monkeypatch):
    """The lawful case. A guard blocking lawful work fails as hard as one
    passing unlawful work, and this shape is what every future row must be."""
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    _write_index(tmp_path, _qualitative_row())
    assert lint.run(tmp_path) == []


def test_qualitative_row_must_name_its_external_outcome(tmp_path, monkeypatch):
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    row = _qualitative_row()
    del row["external"]
    _write_index(tmp_path, row)
    findings = lint.run(tmp_path)
    assert len(findings) == 1, findings
    assert "missing field 'external'" in findings[0], findings[0]


@pytest.mark.parametrize("external", ["", "   ", "2", None, {"raw": 2}, 2])
def test_external_outcome_must_be_qualitative(tmp_path, monkeypatch, external):
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    _write_index(tmp_path, _qualitative_row(external=external))
    findings = lint.run(tmp_path)
    assert len(findings) == 1, findings
    assert "external must be a non-empty qualitative string" in findings[0]


def test_qualitative_row_sustaining_no_high_is_lawful(tmp_path, monkeypatch):
    """Zero findings from all seats is a valid outcome, and an empty list is
    the only way the field can say so."""
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    _write_index(tmp_path, _qualitative_row(highs=[]))
    assert lint.run(tmp_path) == []


def test_qualitative_row_must_name_its_highs(tmp_path, monkeypatch):
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    row = _qualitative_row()
    del row["highs"]
    _write_index(tmp_path, row)
    findings = lint.run(tmp_path)
    assert len(findings) == 1, findings
    assert "highs" in findings[0], findings[0]


@pytest.mark.parametrize(
    "field, value",
    [
        ("seats", {"cold-read": {"raw": 1, "merged": 1, "sustained": 0, "high": 0}}),
        ("dispositions", {"fixed": 1, "routed": 0, "priced_out": 0, "dismissed": 0}),
        ("facing", {"artifact": 1, "apparatus": 0}),
    ],
)
def test_qualitative_row_refuses_the_retired_counting_fields(
    tmp_path, monkeypatch, field, value
):
    """Forbidden, not optional. An optional field lets the shape drift back one
    row at a time, and each row that takes it lands in a file nobody may edit."""
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    _write_index(tmp_path, _qualitative_row(**{field: value}))
    findings = lint.run(tmp_path)
    assert len(findings) == 1, findings
    assert field in findings[0] and "retired" in findings[0], findings[0]


def test_qualitative_row_names_every_retired_field_it_carries(tmp_path, monkeypatch):
    """One finding listing all three, so a row carrying the whole old shape is
    not fixed three times."""
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    _write_index(
        tmp_path,
        _qualitative_row(
            seats={"cold-read": {"raw": 1, "merged": 1, "sustained": 0, "high": 0}},
            dispositions={"fixed": 1, "routed": 0, "priced_out": 0, "dismissed": 0},
            facing={"artifact": 1, "apparatus": 0},
        ),
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1, findings
    assert all(f in findings[0] for f in ("seats", "dispositions", "facing"))


@pytest.mark.parametrize("highs", ["a high", {"one": "high"}, 3])
def test_highs_must_be_a_list(tmp_path, monkeypatch, highs):
    """A bare string is the plausible wrong shape: it is iterable, so a laxer
    check would accept it and record one high per character."""
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    _write_index(tmp_path, _qualitative_row(highs=highs))
    findings = lint.run(tmp_path)
    assert len(findings) == 1, findings
    assert "must be a list" in findings[0], findings[0]


@pytest.mark.parametrize("entry", ["", "   ", None, 7])
def test_each_high_must_be_a_non_empty_string(tmp_path, monkeypatch, entry):
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    _write_index(tmp_path, _qualitative_row(highs=["a real one", entry]))
    findings = lint.run(tmp_path)
    assert len(findings) == 1, findings
    assert "highs[1]" in findings[0], findings[0]


def test_staffing_survives_the_cutover(tmp_path, monkeypatch):
    """The one field on the row that is a fact about who ran the review rather
    than arithmetic about it, and the only queryable home the per-runtime
    evidence has."""
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    row = _qualitative_row()
    del row["staffing"]
    _write_index(tmp_path, row)
    findings = lint.run(tmp_path)
    assert len(findings) == 1, findings
    assert "staffing" in findings[0], findings[0]


def test_dispositions_is_not_owed_past_the_cutover(tmp_path, monkeypatch):
    """The obligation closes where the counting shape does. Without this the
    row would be required to carry a field it is forbidden to carry."""
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    _write_index(tmp_path, _qualitative_row())
    assert not any("dispositions" in f for f in lint.run(tmp_path))


def test_row_before_the_cutover_still_owes_its_seats(tmp_path, monkeypatch):
    """`seats` left the always-required set when the two shapes split, so the
    obligation on the rows that predate the cutover needs its own probe."""
    make_clean_tree(tmp_path)
    monkeypatch.setattr(lint, "REVIEW_ROWS_QUALITATIVE", 5)
    row = _review_row()
    del row["seats"]
    _write_index(tmp_path, row)
    findings = lint.run(tmp_path)
    assert len(findings) == 1, findings
    assert "seats" in findings[0], findings[0]


def test_a_row_before_the_cutover_may_still_carry_counts(tmp_path, monkeypatch):
    """The cutover is forward-only: the rows already written stay valid
    untouched, arithmetic and all."""
    make_clean_tree(tmp_path)
    monkeypatch.setattr(lint, "REVIEW_ROWS_QUALITATIVE", 5)
    _write_index(tmp_path, _review_row())
    assert lint.run(tmp_path) == []


def test_qualitative_row_refuses_arithmetic_under_a_fresh_key(tmp_path, monkeypatch):
    """Naming the three retired fields was never the rule.

    A review found that the same totals under `counts`, `totals`, or any name
    nobody had thought of passed clean, so "the row carries no arithmetic" was
    enforced as "not these three words". The key set is what makes it real.
    """
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    _write_index(
        tmp_path,
        _qualitative_row(counts={"raw": 43, "merged": 29, "sustained": 20, "high": 6}),
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1, findings
    assert "unknown key(s) counts" in findings[0], findings[0]


def test_qualitative_row_names_every_unknown_key_at_once(tmp_path, monkeypatch):
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    _write_index(tmp_path, _qualitative_row(totals={"a": 1}, tally=2))
    findings = lint.run(tmp_path)
    assert len(findings) == 1, findings
    assert "tally, totals" in findings[0], findings[0]


def test_a_retired_field_gets_the_retired_message_not_the_unknown_one(tmp_path, monkeypatch):
    """The specific diagnosis survives the general one: a session that copied
    the row above it is told which shape it copied, not merely that a key is
    unrecognised."""
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    _write_index(
        tmp_path,
        _qualitative_row(facing={"artifact": 1, "apparatus": 0}),
    )
    findings = lint.run(tmp_path)
    assert len(findings) == 1, findings
    assert "retired" in findings[0] and "unknown key" not in findings[0], findings[0]


@pytest.mark.parametrize(
    "field",
    ["notes", "date", "artifact", "lane", "report", "staffing", "highs", "external"],
)
def test_the_closed_key_set_admits_every_field_the_row_is_made_of(
    tmp_path, monkeypatch, field
):
    """The lawful polarity, field by field. `notes` is on the list deliberately:
    the free-text half of the arithmetic problem was priced out, because reading
    prose for totals is the prose-scanning this change's boundary excludes."""
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    row = _qualitative_row(notes="external pass rate-limited; one seat re-dispatched")
    assert field in row
    _write_index(tmp_path, row)
    assert lint.run(tmp_path) == []


def test_a_row_before_the_cutover_may_carry_any_key(tmp_path, monkeypatch):
    """The key set closes forward only. The rows already written carry `round`
    and `notes` and were never held to a schema that did not exist."""
    make_clean_tree(tmp_path)
    monkeypatch.setattr(lint, "REVIEW_ROWS_QUALITATIVE", 5)
    _write_index(tmp_path, _review_row(round="one", notes="whatever it said"))
    assert lint.run(tmp_path) == []


def test_highs_refuses_a_repeated_high(tmp_path, monkeypatch):
    """`len(highs)` is what the record now answers "how many highs" with.

    An external reviewer found this against the fix tree: migrating off per-seat
    counts, a high credited to three seats is the thing most likely to be copied
    three times, and the row is appended and never corrected. The count would be
    permanently wrong in the one field this change made canonical.
    """
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    _write_index(tmp_path, _qualitative_row(highs=["the guard let it back in", "the guard let it back in"]))
    findings = lint.run(tmp_path)
    assert len(findings) == 1, findings
    assert "highs[1] repeats highs[0]" in findings[0], findings[0]


@pytest.mark.parametrize(
    "pair",
    [
        ("A stale sentence", "a stale sentence"),
        ("A stale sentence", "A  stale   sentence"),
        ("A stale sentence", "A stale sentence\n"),
    ],
)
def test_a_repeat_is_caught_through_case_and_whitespace(tmp_path, monkeypatch, pair):
    """The copies this catches are hand-made, so they differ in the ways hand
    copies differ. An exact-match check would pass the realistic case."""
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    _write_index(tmp_path, _qualitative_row(highs=list(pair)))
    findings = lint.run(tmp_path)
    assert len(findings) == 1, findings
    assert "repeats" in findings[0], findings[0]


def test_two_genuinely_different_highs_are_left_alone(tmp_path, monkeypatch):
    """The lawful polarity. A review sustaining several highs is the ordinary
    case, and near-neighbours are not repeats."""
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    _write_index(
        tmp_path,
        _qualitative_row(highs=[
            "the purpose header states the superseded rule",
            "the purpose header omits the tree half",
        ]),
    )
    assert lint.run(tmp_path) == []


def test_a_repeat_does_not_swallow_the_empty_string_finding(tmp_path, monkeypatch):
    """Two blanks are two malformed entries, not a repeat: the repeat check must
    not reach entries the type check already rejected, or one finding replaces
    two and the second blank is fixed only on the next run."""
    make_clean_tree(tmp_path)
    _at_cutover(monkeypatch)
    _write_index(tmp_path, _qualitative_row(highs=["", "  "]))
    findings = lint.run(tmp_path)
    assert len(findings) == 2, findings
    assert all("must be a non-empty string" in f for f in findings), findings


def test_docstring_control_chars_stays_quiet_on_a_lawful_tree(tmp_path):
    """The polarity that matters as much as the other: a guard that reds prose
    written correctly is a guard somebody deletes. A docstring naming a carriage
    return by its escape, doubled, is this repository's convention and passes.
    """
    source = (
        "def f():" + chr(10)
        + "    " + chr(34)*3 + "Names `" + BS*2 + "r` as text, indented" + chr(34)*3 + chr(10)
        + "    return 1" + chr(10)
    )
    (tmp_path / "ok.py").write_bytes(source.encode("utf-8"))
    assert lint.check_docstring_control_chars(tmp_path) == []


def test_docstring_control_chars_catches_the_escape_that_became_the_character(tmp_path):
    """The defect, at the site it fired. One backslash in a non-raw docstring is
    the character at runtime, and on disk it is one byte away from the lawful
    form above -- which is why reading the source rather than the compiled value
    would miss it.
    """
    source = (
        "def f():" + chr(10)
        + "    " + chr(34)*3 + "Names `" + BS + "r` with one backslash." + chr(34)*3 + chr(10)
        + "    return 1" + chr(10)
    )
    assert chr(13) not in source, "the fixture is an escape, not a raw byte"
    (tmp_path / "bad.py").write_bytes(source.encode("utf-8"))
    findings = lint.check_docstring_control_chars(tmp_path)
    assert len(findings) == 1
    assert "bad.py" in findings[0]
    assert "U+000D" in findings[0]


def test_docstring_control_chars_reads_the_compiled_value_not_the_bytes(tmp_path):
    """The distinguishing claim, pinned. The fixture above holds no carriage
    return byte on disk and one in `__doc__`, which is the instance that
    motivated this check and the reason a scan for carriage-return bytes does
    not replace it: that scan reads the bytes and finds nothing.
    """
    source = (
        "def f():" + chr(10)
        + "    " + chr(34)*3 + "Holds `" + BS + "r` as an escape." + chr(34)*3 + chr(10)
        + "    return 1" + chr(10)
    )
    path = tmp_path / "escaped.py"
    path.write_bytes(source.encode("utf-8"))
    assert chr(13).encode() not in path.read_bytes()
    assert lint.check_docstring_control_chars(tmp_path) != []


def test_docstring_control_chars_exempts_the_characters_prose_is_written_in(tmp_path):
    """Line feeds and tabs are how prose is written, so forgiving them is the
    check being usable rather than a hole: a multi-line indented docstring is
    every docstring in this repository.
    """
    source = (
        "def f():" + chr(10)
        + "    " + chr(34)*3 + "First line." + chr(10) + chr(10) + chr(9) + "Indented." + chr(10) + "    " + chr(34)*3 + chr(10)
        + "    return 1" + chr(10)
    )
    (tmp_path / "prose.py").write_bytes(source.encode("utf-8"))
    assert lint.check_docstring_control_chars(tmp_path) == []


def test_docstring_control_chars_leaves_a_non_docstring_string_alone(tmp_path):
    """Scope, stated by probe. A control character in an ordinary string is code
    building a byte deliberately -- the sanctioned route -- and this check is
    about prose a reader is handed, not about what code constructs.
    """
    source = (
        "def f():" + chr(10)
        + "    return " + chr(34) + "a" + chr(92) + "rb" + chr(34) + chr(10)
    )
    (tmp_path / "code.py").write_bytes(source.encode("utf-8"))
    assert lint.check_docstring_control_chars(tmp_path) == []


def test_this_repository_holds_no_control_character_in_any_docstring():
    """The tree this exists for. PR #231 shipped four carriage returns in one
    test's `__doc__` with clean bytes on disk and every guard green; this is
    what would have caught them.
    """
    root = Path(__file__).resolve().parents[2]
    assert lint.check_docstring_control_chars(root) == []


def test_docstring_control_chars_reports_a_module_docstring_without_raising(tmp_path):
    """The crash this guard shipped with, at the shape it teaches about.

    `ast.Module` carries no `lineno`, and formatting it unguarded raised out of
    `run()` -- so a control character in a *module* docstring answered the
    mandated first step of the flow with a traceback and none of the other
    checks' findings. `roster.write` records the same defect at [PR #210
    review, M4]: a cell it cannot read is reported, never raised.
    """
    source = (
        chr(34)*3 + "Names `" + BS + "r` in a module docstring." + chr(34)*3 + chr(10)
        + "def f():" + chr(10)
        + "    return 1" + chr(10)
    )
    (tmp_path / "mod.py").write_bytes(source.encode("utf-8"))
    findings = lint.check_docstring_control_chars(tmp_path)
    assert len(findings) == 1
    assert "(module)" in findings[0]
    assert "U+000D" in findings[0]


def test_emitted_ascii_omits_a_position_it_does_not_have(tmp_path):
    """A `SyntaxError` from a raw NUL carries no line number, and the message
    printed it as `:None` — a position that does not exist, in a module whose
    convention is that `file:lineno` is searchable.
    """
    (tmp_path / "mod.py").write_bytes(b"x = 1" + bytes([0]) + b"2" + NL.encode())
    findings = lint.check_emitted_ascii(tmp_path)
    assert len(findings) == 1
    assert ":None" not in findings[0]
    assert findings[0].startswith("emitted-ascii: mod.py does not parse")


@pytest.mark.parametrize("point, label", [(127, "U+007F"), (133, "U+0085")])
def test_docstring_control_chars_reaches_del_and_the_c1_block(tmp_path, point, label):
    """Scope, matched to what the rule says rather than to `point < 32`.

    The stated rule is *control character*, and DEL and the C1 block are
    control characters -- U+0085 is a line break to `str.splitlines()`, so it
    mis-renders anything paginating a docstring. An earlier predicate exempted
    both in fact while the registration banned them in words.
    """
    source = (
        "def f():" + chr(10)
        + "    " + chr(34)*3 + "Holds " + chr(point) + " here." + chr(34)*3 + chr(10)
        + "    return 1" + chr(10)
    )
    (tmp_path / "c1.py").write_bytes(source.encode("utf-8"))
    findings = lint.check_docstring_control_chars(tmp_path)
    assert len(findings) == 1
    assert label in findings[0]


def test_docstring_control_chars_reports_every_character_not_only_the_first(tmp_path):
    """A guard reporting one offender per file sends a session back for a
    second red it could have fixed in the same pass. An earlier version broke
    out of the loop on the first character, with no wording saying so.

    Both characters arrive as **escapes**, and the first draft of this fixture
    wrote a raw carriage-return byte instead and saw only one finding: Python's
    tokenizer folds a lone carriage return in source to a line feed, so it never
    reaches the compiled value at all.

    **That is true of the carriage return and of nothing else.** A raw vertical
    tab, form feed, ESC, DEL or C1 byte on disk survives into the compiled value
    and is reported. So the gap a byte-level scan would close is one character
    wide, not the whole class -- which is worth stating precisely, because the
    scan is filed on the strength of it (#233).
    """
    source = (
        "def f():" + chr(10)
        + "    " + chr(34)*3 + "Holds " + BS + "r and " + BS + "x0b." + chr(34)*3 + chr(10)
        + "    return 1" + chr(10)
    )
    (tmp_path / "two.py").write_bytes(source.encode("utf-8"))
    findings = lint.check_docstring_control_chars(tmp_path)
    assert len(findings) == 2
    assert {"U+000B", "U+000D"} == {f.split("holds ")[1][:6] for f in findings}


def test_git_ignored_survives_a_non_ascii_path(tmp_path):
    """The ignore filter feeds three checks, and nothing pinned it.

    `text=True` alone encodes stdin with the locale codepage, so on Windows one
    non-ASCII path anywhere raised `UnicodeEncodeError` inside subprocess's
    writer thread -- where it is swallowed. stdin never closed, the call ran to
    its full timeout, and the filter then returned empty: every check using it
    silently scanned ignored trees after a minute's stall. The substrate cell's
    stream rule, at a site three checks share.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_bytes(("skip" + chr(10)).encode("utf-8"))
    (tmp_path / "skip").mkdir()
    plain = tmp_path / "skip" / "plain.py"
    plain.write_bytes(b"x = 1" + chr(10).encode())
    # chr(20013) rather than the character: this file is read by a check that
    # bans non-ASCII in non-docstring literals.
    exotic = tmp_path / (chr(20013) + ".py")
    exotic.write_bytes(b"y = 2" + chr(10).encode())
    ignored = lint._git_ignored(tmp_path, [plain, exotic])
    assert plain in ignored, (
        "the ignored path must still be filtered when a non-ASCII path is present"
    )
    assert exotic not in ignored


def test_git_ignored_filters_an_ordinary_tree(tmp_path):
    """The other polarity: the lawful case still filters, so the fix above is
    not the filter quietly turning itself off.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_bytes(("skip" + chr(10)).encode("utf-8"))
    (tmp_path / "skip").mkdir()
    hidden = tmp_path / "skip" / "a.py"; hidden.write_bytes(b"x = 1" + chr(10).encode())
    shown = tmp_path / "b.py"; shown.write_bytes(b"y = 2" + chr(10).encode())
    ignored = lint._git_ignored(tmp_path, [hidden, shown])
    assert ignored == {hidden}


def _raising(message="simulated: any check that raises"):
    """A check-shaped callable that raises, for the isolation tests below."""
    def check(root):
        raise AttributeError(message)
    check.__name__ = "check_that_raises"
    return check


def test_a_raising_check_does_not_take_the_other_checks_findings_with_it(
    tmp_path, monkeypatch
):
    """The defect: `run()` was one `+` chain, so any check that raised
    discarded every finding computed before it and answered with a traceback.
    A session running the flow's first mandated step could not tell a clean
    tree from a filthy one. [#239]
    """
    make_clean_tree(tmp_path)
    # A genuine finding from a real check, so there is something to lose.
    _write_marketplace(tmp_path, {"source": "./"})
    real = lint.run(tmp_path)
    assert real, "the fixture must produce a finding for this test to mean anything"

    monkeypatch.setattr(lint, "CHECKS", lint.CHECKS + (_raising(),))
    findings = lint.run(tmp_path)

    for finding in real:
        assert finding in findings, "a raising check must not discard what the others found"
    raised = [f for f in findings if f.startswith("check-raised:")]
    assert len(raised) == 1
    assert "check_that_raises" in raised[0]
    assert "AttributeError" in raised[0]


def test_a_raising_check_is_reported_rather_than_raised(tmp_path, monkeypatch):
    """The other half: `run()` returns rather than propagating, on a tree
    where nothing else has anything to say.
    """
    make_clean_tree(tmp_path)
    assert lint.run(tmp_path) == []
    monkeypatch.setattr(lint, "CHECKS", (_raising(),))
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and findings[0].startswith("check-raised:")


def test_a_raising_check_cannot_be_read_as_a_clean_tree(tmp_path, monkeypatch):
    """Exit code, on a tree whose every other check is silent. A raising check
    that exited 0 would relocate the defect rather than end it: the session
    reads green and commits.
    """
    make_clean_tree(tmp_path)
    monkeypatch.setattr(lint, "ROOT", tmp_path)
    monkeypatch.setattr(lint, "CHECKS", (_raising(),))
    assert lint.main() == 1


def test_the_raised_finding_names_the_frame_and_claims_nothing_else(tmp_path, monkeypatch):
    """The message states what was computed and no more.

    It carries the check, the exception and the site -- without the site the
    reader has an exception and nowhere to search, and the traceback that
    carried one is exactly what isolating the check throws away. It must not
    say the tree is clean, which is the trap `check_emitted_ascii`'s docstring
    records: a guard asserting something it never computed.
    """
    make_clean_tree(tmp_path)
    monkeypatch.setattr(lint, "CHECKS", (_raising("boom"),))
    finding = lint.run(tmp_path)[0]
    assert "test_lint.py:" in finding, "the finding names the frame that raised"
    assert "(boom)" in finding, "the exception's own message survives"
    assert "unchecked" in finding
    assert "does not say the tree is clean" in finding


def test_every_check_in_the_chain_is_reachable_by_name():
    """`CHECKS` is the chain, and a check absent from it runs nowhere. The
    tuple replaced a `+` expression where forgetting an entry was equally
    silent, so the property is pinned rather than assumed.
    """
    assert len({c.__name__ for c in lint.CHECKS}) == len(lint.CHECKS)
    for check in lint.CHECKS:
        assert getattr(lint, check.__name__) is check


def test_where_says_so_rather_than_inventing_a_frame():
    """`_where` on an exception that was never raised has no traceback. It
    says so; a guard that filled in a plausible file and line would be
    stating something it never computed.
    """
    assert lint._where(ValueError("never raised")) == "no frame inside this repository"


CR = chr(13)
TICK = chr(96)


def test_hollow_code_span_catches_the_character_that_went_missing(tmp_path):
    """Instance 3's shape: a span written to show a character, with the
    character gone. The sentence still reads as an explanation of a byte and
    names no byte. [#233]
    """
    (tmp_path / "note.md").write_text(
        "The block ends at the bare " + TICK + CR + TICK + ", so verify reports." + NL,
        encoding="utf-8", newline="",
    )
    findings = lint.check_hollow_code_span(tmp_path)
    assert len(findings) == 1
    assert "note.md:1" in findings[0]
    assert "U+000D" in findings[0]


def test_hollow_code_span_reads_across_the_one_line_break_a_span_may_hold(tmp_path):
    """The live instance sat in a docstring where the lost character was a
    line break, so the span crossed a source line. A single-line predicate
    reports the doubled-backtick idiom and misses the only real defect in the
    tree -- measured, which is why this is pinned.
    """
    (tmp_path / "mod.py").write_text(
        "def f():" + NL
        + '    """Ends at the bare ' + TICK + NL + TICK + " -- so it reports." + NL
        + '    """' + NL,
        encoding="utf-8", newline="",
    )
    findings = lint.check_hollow_code_span(tmp_path)
    assert len(findings) == 1 and "U+000A" in findings[0]


def test_hollow_code_span_leaves_the_doubled_backtick_idiom_alone(tmp_path):
    """The other polarity, and the one that decides the predicate.

    Every false positive the strip-to-nothing form produced across this
    repository was this idiom, which is prose about fences and lawful. Its
    inner span is *exactly* empty; the defect's is not. A guard that reported
    it would be refused within a release, which is the failure a guard
    blocking lawful work always is.
    """
    (tmp_path / "note.md").write_text(
        "Pin as " + TICK*2 + " " + TICK + "path" + TICK + " at " + TICK
        + "<sha>" + TICK + " " + TICK*2 + " at authoring time." + NL,
        encoding="utf-8", newline="",
    )
    assert lint.check_hollow_code_span(tmp_path) == []


def test_hollow_code_span_leaves_ordinary_prose_alone(tmp_path):
    """A span with content in it is what every lawful span is."""
    (tmp_path / "note.md").write_text(
        "Run " + TICK + "python tools/lint.py" + TICK + " before committing." + NL,
        encoding="utf-8", newline="",
    )
    assert lint.check_hollow_code_span(tmp_path) == []


def test_hollow_code_span_skips_a_fenced_block(tmp_path):
    """A span inside a fence is being shown, not written -- the premise checks
    5 and 6 already reason from, and the one a fixture demonstrating this
    defect depends on.
    """
    (tmp_path / "note.md").write_text(
        "The defect looks like this:" + NL + NL
        + "```" + NL
        + "ends at the bare " + TICK + CR + TICK + NL
        + "```" + NL,
        encoding="utf-8", newline="",
    )
    assert lint.check_hollow_code_span(tmp_path) == []


def test_this_repository_holds_no_hollow_code_span():
    """The tree this exists for. `tools/roster.py` carried one until the
    change that added this guard; run against the diff base it reports that
    line, and against this revision it is silent.
    """
    root = Path(__file__).resolve().parents[2]
    assert lint.check_hollow_code_span(root) == []


def _git_repo_with(tmp_path, name, data: bytes):
    """A committed fixture repository carrying this repository's own
    `.gitattributes`, so the normalisation under test is the real one.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    attributes = Path(__file__).resolve().parents[2] / ".gitattributes"
    (tmp_path / ".gitattributes").write_bytes(attributes.read_bytes())
    (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / name).write_bytes(data)
    for args in (["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t",
                                 "commit", "-qm", "fixture"]):
        subprocess.run(["git", "-C", str(tmp_path)] + args, check=True,
                       stdin=subprocess.DEVNULL, capture_output=True)
    return tmp_path


def test_committed_carriage_return_catches_the_byte_that_reached_a_commit(tmp_path):
    """Instance 1: a decision-index row appended by a script whose escapes had
    become control bytes. `text=auto` refuses to normalise a file holding a
    lone carriage return, so every line ending in it committed verbatim and
    the row rendered as a truncated row plus an orphan. [#233]
    """
    _git_repo_with(tmp_path, "index.md",
                   ("a lone " + CR + " row" + NL + "next" + NL).encode("utf-8"))
    findings = lint.check_committed_carriage_return(tmp_path)
    assert len(findings) == 1
    assert "index.md" in findings[0]


def test_committed_carriage_return_leaves_a_crlf_working_copy_alone(tmp_path):
    """The polarity that decides whether this guard is usable here at all.

    A CRLF working copy is expected rather than a defect [D-186]: the pin
    normalises it into the index, so nothing reaches the repository. A guard
    reporting it would reinstate the unclearable red #224 was about.
    """
    _git_repo_with(tmp_path, "note.md",
                   ("first" + CR + NL + "second" + CR + NL).encode("utf-8"))
    assert lint.check_committed_carriage_return(tmp_path) == []


def test_committed_carriage_return_leaves_a_genuine_binary_alone(tmp_path):
    """A binary reports `i/-text` exactly as a lone-carriage-return file does.

    A PNG's own file signature *is* a carriage return and a line feed, so
    confirming the byte is not enough on its own: the first image committed
    here would go red for its own header. Binary content is skipped by the NUL
    rule this module applies everywhere, which is what makes the confirmation
    safe rather than merely truthful.
    """
    png = bytes([137, 80, 78, 71, 13, 10, 26, 10]) + bytes([0, 0, 0, 13]) + b"IHDR"
    _git_repo_with(tmp_path, "image.png", png)
    assert lint.check_committed_carriage_return(tmp_path) == [], (
        "a binary is skipped even though its signature holds a carriage return"
    )


def test_committed_carriage_return_still_reads_a_text_file_git_calls_binary(tmp_path):
    """The other polarity of that skip, and the one that matters: git calls a
    lone-carriage-return *text* file binary too, and that file is the whole
    point. The NUL rule is what tells the two apart, not git's classification.
    """
    _git_repo_with(tmp_path, "index.md",
                   ("row" + CR + "orphan" + NL).encode("utf-8"))
    assert len(lint.check_committed_carriage_return(tmp_path)) == 1


def test_committed_carriage_return_is_silent_where_git_cannot_answer(tmp_path):
    """A tree with no git is not a tree with a finding, per `_git_ignored`'s
    reason: these guards may only ever remove noise.
    """
    (tmp_path / "note.md").write_bytes(("a" + CR + "b" + NL).encode("utf-8"))
    assert lint.check_committed_carriage_return(tmp_path) == []


def test_this_repository_commits_no_carriage_return():
    """The tree this exists for, and the state PR #231 restored it to."""
    root = Path(__file__).resolve().parents[2]
    assert lint.check_committed_carriage_return(root) == []


def test_committed_carriage_return_reads_a_staged_file_with_no_commit_yet(tmp_path):
    """`git ls-files --eol` classifies the index, so the confirming read has
    to read the index too.

    This spelled it `HEAD:<path>` first, which answers a different question: a
    file staged and not yet committed has no HEAD copy, so the read failed and
    the check went silent on precisely the file a session is about to commit.
    In a repository with no commits at all it was silent on everything. Found
    by building a tree that had neither, not by reading.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    attributes = Path(__file__).resolve().parents[2] / ".gitattributes"
    (tmp_path / ".gitattributes").write_bytes(attributes.read_bytes())
    (tmp_path / "index.md").write_bytes(("row" + CR + "orphan" + NL).encode("utf-8"))
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True,
                   stdin=subprocess.DEVNULL, capture_output=True)
    findings = lint.check_committed_carriage_return(tmp_path)
    assert len(findings) == 1 and "index.md" in findings[0]


def _cell_with_hollow_span(root, char=CR):
    """A cell whose *description* holds the defect, so the generated entry
    copies it -- the frontmatter block is what `roster.write` copies.
    """
    cell = root / "skills" / "alpha"
    cell.mkdir(parents=True)
    (cell / "SKILL.md").write_bytes(
        ("---" + NL + "name: alpha" + NL
         + "description: Ends at the bare " + TICK + char + TICK + " here." + NL
         + "---" + NL + NL + "# alpha" + NL + "Body." + NL).encode("utf-8")
    )
    roster.write(root)
    return cell


def test_a_cells_defect_is_reported_once_and_not_against_its_generated_copy(tmp_path):
    """One edit, one finding.

    The entry's frontmatter is the cell's byte for byte, so both files hold
    the defect -- but the entry's finding names a file that says *do not edit
    this one*, and a reader acting on it edits a generated file whose next
    `--write` brings the defect back, which is a fix that does not fix.
    """
    _cell_with_hollow_span(tmp_path)
    findings = lint.check_hollow_code_span(tmp_path)
    assert len(findings) == 1
    assert findings[0].startswith("hollow-code-span: skills/alpha/SKILL.md")


def test_a_hand_written_project_skill_in_the_roster_is_still_read(tmp_path):
    """The other polarity, and the one that keeps the skip honest.

    `.claude/skills/` is the runtime's documented home for a project's own
    skills, so the directory is shared rather than owned. A file this
    generator did not write is not its copy of anything, and skipping by
    location rather than by the marker would silence a real defect in one --
    the same reasoning `is_generated` already carries for the removal branch.
    """
    hand = tmp_path / ".claude" / "skills" / "mine"
    hand.mkdir(parents=True)
    (hand / "SKILL.md").write_bytes(
        ("---" + NL + "name: mine" + NL + "description: d." + NL + "---" + NL + NL
         + "Ends at the bare " + TICK + CR + TICK + "." + NL).encode("utf-8")
    )
    findings = lint.check_hollow_code_span(tmp_path)
    assert len(findings) == 1
    assert ".claude/skills/mine/SKILL.md" in findings[0]


# --- PR #247 review, round-one fix batch -------------------------------------


def test_the_generated_entry_skip_reaches_only_the_roster_directory(tmp_path):
    """M1: `roster.is_generated` answers by marker, and `tools/roster.py`
    holds that marker's own literal -- so applying it to every path in the
    repository switched both prose guards off for the file both of their
    motivating instances came out of. The location is tested first now.
    """
    tools = tmp_path / "tools"
    tools.mkdir()
    marker = roster.MARKER.decode("utf-8")
    (tools / "roster.py").write_text(
        chr(34)*3 + NL + "Writes " + marker + " into each entry." + NL
        + "Ends at the bare " + TICK + CR + TICK + "." + NL + chr(34)*3 + NL,
        encoding="utf-8", newline="",
    )
    findings = lint.check_hollow_code_span(tmp_path)
    assert len(findings) == 1, "a file is not a roster entry merely by quoting the marker"
    assert findings[0].startswith("hollow-code-span: tools/roster.py")


def test_this_repositorys_generator_is_still_read_by_the_prose_guards():
    """The same property against the real tree rather than a fixture: the one
    file whose prose is densest in control characters must be in scope.
    """
    root = Path(__file__).resolve().parents[2]
    assert lint._is_generated_entry(root, "tools/roster.py") is False
    assert lint._is_generated_entry(root, ".claude/skills/substrate/SKILL.md") is True


def test_hollow_code_span_counts_the_line_in_the_text_it_matched(tmp_path):
    """M3: the offset comes from the blanked text, so the count has to be
    taken there too. Counting it in the original reported a line too early for
    every file carrying a fence above the span -- eight of the eight such
    files in this repository when the guard shipped.
    """
    (tmp_path / "note.md").write_text(
        TICK*3 + NL + "a" + NL + "b" + NL + TICK*3 + NL
        + "tail " + TICK + CR + TICK + "." + NL,
        encoding="utf-8", newline="",
    )
    findings = lint.check_hollow_code_span(tmp_path)
    assert len(findings) == 1
    assert "note.md:5" in findings[0], "the defect is on line 5, below a four-line fence"


@pytest.mark.parametrize("label, body, want", [
    ("a tilde line inside a backtick block does not close it",
     TICK*3 + NL + "~~~" + NL + TICK*3 + NL, 1),
    ("a triple-backtick fence shown inside a quadruple block is displayed prose",
     TICK*4 + NL + TICK*3 + NL + "x " + TICK + CR + TICK + NL + TICK*3 + NL
     + TICK*4 + NL, 0),
    ("an opening fence may be indented up to three spaces",
     "   " + TICK*3 + NL + "x" + NL + "   " + TICK*3 + NL, 1),
])
def test_hollow_code_span_closes_a_fence_only_on_its_own_marker(
    tmp_path, label, body, want
):
    """M4: an unconditional toggle got all three of these wrong. The second is
    the one that mattered most -- it drew a finding against lawful displayed
    prose, the very construct `test_a_fence_closes_only_on_its_own_marker`
    pins as lawful for checks 5 and 6.

    Each case appends the same defect after the block, so `want` counts only
    what the fence rule decides.
    """
    tail = "tail " + TICK + CR + TICK + "." + NL if want else "after." + NL
    (tmp_path / "note.md").write_text(body + tail, encoding="utf-8", newline="")
    assert len(lint.check_hollow_code_span(tmp_path)) == want, label


def test_hollow_code_span_skips_a_span_holding_two_line_breaks(tmp_path):
    """The exclusion had no test. CommonMark ends a code span at a blank
    line, and in whitespace-only content two line breaks put one there.
    """
    (tmp_path / "note.md").write_text(
        "a " + TICK + NL + NL + TICK + " b" + NL, encoding="utf-8", newline="",
    )
    assert lint.check_hollow_code_span(tmp_path) == []


def test_hollow_code_span_honours_gitignore_at_its_own_call_site(tmp_path):
    """The filter was unpinned where it is used, not where it is defined: a
    regression dropping it would report findings inside a session's `.venv`.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("skip" + NL, encoding="utf-8", newline="")
    (tmp_path / "skip").mkdir()
    defect = "a " + TICK + CR + TICK + "." + NL
    (tmp_path / "skip" / "hidden.md").write_text(defect, encoding="utf-8", newline="")
    (tmp_path / "shown.md").write_text(defect, encoding="utf-8", newline="")
    findings = lint.check_hollow_code_span(tmp_path)
    assert len(findings) == 1 and "shown.md" in findings[0]


def test_read_text_answers_none_for_a_file_it_cannot_open(tmp_path):
    """D1: unreadable is None, not an exception. With the read unguarded, one
    vanished or locked file cost the calling check its entire territory and
    named a frame inside the standard library.
    """
    assert lint._read_text(tmp_path / "not-there.md") is None


def test_hollow_code_span_survives_a_file_that_vanishes_under_it(tmp_path):
    """The same property through the check, which is where it is reached: the
    walk collects paths and the read happens later.
    """
    (tmp_path / "gone.md").write_text("x" + NL, encoding="utf-8", newline="")
    (tmp_path / "kept.md").write_text(
        "a " + TICK + CR + TICK + "." + NL, encoding="utf-8", newline="",
    )
    real = lint._prose_files

    def vanishing(root):
        paths = list(real(root))
        (tmp_path / "gone.md").unlink()
        return paths

    lint._prose_files = vanishing
    try:
        findings = lint.check_hollow_code_span(tmp_path)
    finally:
        lint._prose_files = real
    assert len(findings) == 1 and "kept.md" in findings[0]


def test_the_prose_guards_skip_the_records_doctrine_forbids_editing(tmp_path):
    """M7: a finding must quote the line it names, so a review row about a
    hollow span holds one. Reporting it is a red no lawful edit can clear --
    the shape #224 was about, rebuilt by a guard.
    """
    defect = "row " + TICK + " " + TICK + "." + NL
    for rel in ("docs/reviews.jsonl", "docs/recorded-findings.jsonl",
                "docs/ledger.jsonl", "docs/architecture/adr/ADR-001.md"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(defect, encoding="utf-8", newline="")
    (tmp_path / "docs" / "live.md").write_text(defect, encoding="utf-8", newline="")
    findings = lint.check_hollow_code_span(tmp_path)
    assert len(findings) == 1, "only the file that is not a record is reported"
    assert "docs/live.md" in findings[0]


def test_committed_carriage_return_sees_the_working_tree(tmp_path):
    """M2: `AGENTS.md` runs this command before staging and `persist.py`
    refuses a pre-loaded index, so reading the index alone answered a question
    about the previous commit. The guard could not fire until the run *after*
    the bytes had landed.
    """
    _git_repo_with(tmp_path, "clean.md", ("ok" + NL).encode("utf-8"))
    (tmp_path / "tracked.md").write_bytes(("row" + CR + "orphan" + NL).encode("utf-8"))
    (tmp_path / "untracked.md").write_bytes(("new" + CR + "entry" + NL).encode("utf-8"))
    findings = lint.check_committed_carriage_return(tmp_path)
    assert len(findings) == 2, "the unstaged edit and the new file are both reported"
    assert any("tracked.md" in f for f in findings)
    assert any("untracked.md" in f for f in findings)


def test_committed_carriage_return_reports_one_finding_per_file(tmp_path):
    """A file whose index and working copies both hold the byte is one
    defect. Reporting it twice is the shape the sibling guard's skip exists
    to stop.
    """
    _git_repo_with(tmp_path, "both.md",
                   ("a" + NL + "row" + CR + "x" + NL).encode("utf-8"))
    findings = lint.check_committed_carriage_return(tmp_path)
    assert len(findings) == 1
    assert "both.md:2" in findings[0], "the position is named, not just the file"
    assert "index copy holds one too" in findings[0]


def test_committed_carriage_return_names_a_remedy_that_clears_it(tmp_path):
    """M6: the message told the reader to rewrite a file whose working copy
    was already clean, so following it left the finding standing word for
    word. Staging is what clears that one, and the message now says so.
    """
    _git_repo_with(tmp_path, "note.md", ("row" + CR + "orphan" + NL).encode("utf-8"))
    (tmp_path / "note.md").write_bytes(("row" + NL + "orphan" + NL).encode("utf-8"))
    findings = lint.check_committed_carriage_return(tmp_path)
    assert len(findings) == 1
    assert "the working copy is already clean -- stage it" in findings[0]
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True,
                   stdin=subprocess.DEVNULL, capture_output=True)
    assert lint.check_committed_carriage_return(tmp_path) == [], (
        "the remedy the message names must clear the finding"
    )


def test_committed_carriage_return_leaves_a_binary_whose_nul_is_late(tmp_path):
    """M5: a PDF's header is ASCII and its first NUL sits well past a
    kilobyte, so the NUL rule alone does not reach it. This fixture holds
    *no* lone carriage return -- only pairs -- and the old predicate reported
    it with a message asserting a lone one it had never looked for.
    """
    pdf = ("%PDF-1.4" + CR + NL).encode("utf-8") + b"A" * 1200 \
        + bytes([0]) * 8 + ("%%EOF" + NL).encode("utf-8")
    _git_repo_with(tmp_path, "paper.pdf", pdf)
    assert lint.check_committed_carriage_return(tmp_path) == []


def test_committed_carriage_return_reads_no_blob_for_a_lawful_empty_file(tmp_path):
    """An empty file and one with no trailing terminator both report `i/none`,
    which is lawful. The predicate flagged them and paid a subprocess for
    each, against a docstring saying nothing was read on a lawful tree.
    """
    _git_repo_with(tmp_path, "empty.txt", b"")
    (tmp_path / "noeol.txt").write_bytes(b"text with no trailing newline")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True,
                   stdin=subprocess.DEVNULL, capture_output=True)
    real = subprocess.run
    spawned = []

    def counting(args, **kwargs):
        if isinstance(args, list) and args[:2] == ["git", "cat-file"]:
            spawned.append(args[-1])
        return real(args, **kwargs)

    subprocess.run = counting
    try:
        assert lint.check_committed_carriage_return(tmp_path) == []
    finally:
        subprocess.run = real
    assert spawned == [], "a lawful tree reads no blob"


def test_where_names_the_innermost_frame_inside_this_repository():
    """M8: the innermost frame is often inside the standard library, and a
    bare basename there is unsearchable and reads as a repository path. The
    actionable frame is the innermost one under ROOT.
    """
    try:
        json.loads("{")
    except ValueError as exc:
        where = lint._where(exc)
    assert where.startswith("tools/tests/test_lint.py:"), where


def test_always_on_note_reports_rather_than_raising_on_a_bad_shape(tmp_path):
    """M19: the read was inside the guard and the formatting was not, so a
    `data` missing either key escaped as a KeyError and `main()` answered the
    mandated command with a traceback.
    """
    module = tmp_path / "tools"
    module.mkdir()
    (module / "figures.py").write_text(
        "def figure_always_on(root):" + NL
        + "    return {'data': {'adopter_total': 1}}" + NL,
        encoding="utf-8", newline="",
    )
    note = lint.always_on_note(tmp_path)
    assert note.startswith("always-on surface: not derived (")
    # The shape now fails on the renderer rather than on a key, because the
    # line asks the figure to render its own rows rather than reaching into
    # them. Either way it is reported and never raised, which is what M19
    # bought and what this pins.
    assert "not derived" in note and "Traceback" not in note


def test_hollow_code_span_does_not_walk_the_git_directory(tmp_path):
    """`_prose_files` is the first walk here to take the repository root
    unfiltered, and `.git` is full of text git wrote: commit messages, the
    config, the sample hooks. `_git_ignored` does not exclude it -- git does
    not call its own directory ignored -- so the walk's own clause is the only
    thing keeping it out, and nothing pinned that clause.
    """
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    defect = "a " + TICK + CR + TICK + "." + NL
    (git_dir / "COMMIT_EDITMSG").write_text(defect, encoding="utf-8", newline="")
    (tmp_path / "shown.md").write_text(defect, encoding="utf-8", newline="")
    findings = lint.check_hollow_code_span(tmp_path)
    assert len(findings) == 1 and "shown.md" in findings[0]


# --- PR #247 review, post-fix cycle 1 ----------------------------------------


def test_a_lone_carriage_return_in_a_live_record_is_still_reported(tmp_path):
    """Post-fix 1: the two guards skip for different reasons, and one list
    conflated them.

    A hollow code span in a review row is intended content — a finding must
    quote the line it names — so the prose guard skips it. A lone carriage
    return there is not content at all: it is corruption of the row's own JSON,
    and #233's motivating instance was a row appended by a script whose escapes
    had become control bytes. Sharing one list withdrew the pre-commit catch
    this change's own M2 remedy had just bought.
    """
    _git_repo_with(tmp_path, "docs/note.md", ("ok" + NL).encode("utf-8"))
    for rel in ("docs/reviews.jsonl", "docs/recorded-findings.jsonl",
                "docs/ledger.jsonl"):
        (tmp_path / rel).write_bytes(("{" + chr(34) + "f" + chr(34) + ": "
                                      + chr(34) + "row" + CR + "orphan"
                                      + chr(34) + "}" + NL).encode("utf-8"))
    reported = {f.split(":")[1].strip() for f
                in lint.check_committed_carriage_return(tmp_path)}
    assert "docs/reviews.jsonl" in reported
    assert "docs/recorded-findings.jsonl" in reported
    assert "docs/ledger.jsonl" not in reported, "the frozen archive stays skipped"


def test_a_hollow_span_in_a_live_record_is_still_skipped(tmp_path):
    """The other polarity of the same split, and the reason it exists: a
    finding quoting a hollow span is what gets appended to these files, and
    reporting it would red the lint over a record doctrine forbids repairing.
    """
    defect = "row " + TICK + " " + TICK + "." + NL
    for rel in ("docs/reviews.jsonl", "docs/recorded-findings.jsonl",
                "docs/ledger.jsonl", "docs/live.md"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(defect, encoding="utf-8", newline="")
    findings = lint.check_hollow_code_span(tmp_path)
    assert len(findings) == 1 and "docs/live.md" in findings[0]


def test_the_frozen_archive_is_what_both_guards_skip():
    """The two populations, named apart. A new frozen path goes in one; a new
    append-only record that is still written to goes in the other.

    **The lists are not derived from `AGENTS.md`, and a sibling pin used to
    imply they were.** Deriving them is the real remedy for a frozen path added
    to the doctrine and omitted here, and it was priced as bigger than the
    defect it closes; this pins what the lists hold instead, which is the
    narrower true thing. [PR #247 review, post-fix R3]
    """
    assert lint._frozen("docs/architecture/adr/ADR-001.md")
    assert lint._frozen("docs/ledger.jsonl")
    assert lint._frozen("docs/seat-record.jsonl")
    assert not lint._frozen("docs/reviews.jsonl"), "a live record is not frozen"
    assert lint._unread_as_prose("docs/reviews.jsonl")
    assert lint._unread_as_prose("docs/recorded-findings.jsonl")
    assert not lint._unread_as_prose("docs/values.md")


def test_committed_carriage_return_reads_the_index_copy_not_head(tmp_path):
    """Post-fix 3: `git ls-files --eol` classifies the index, so the confirming
    read must be of the index.

    Spelled `HEAD:<path>` this loses the whole index-only population — a file
    staged and then cleaned on disk, which is the case commit `9a9f221` was
    written for. The earlier pin stopped covering it once the working-tree
    population landed, because its fixture leaves the bytes on disk too.
    """
    _git_repo_with(tmp_path, "note.md", ("clean" + NL).encode("utf-8"))
    staged = tmp_path / "staged.md"
    staged.write_bytes(("row" + CR + "orphan" + NL).encode("utf-8"))
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True,
                   stdin=subprocess.DEVNULL, capture_output=True)
    # the working copy is repaired; only the index still holds the byte
    staged.write_bytes(("row" + NL + "orphan" + NL).encode("utf-8"))
    findings = lint.check_committed_carriage_return(tmp_path)
    assert len(findings) == 1
    assert "staged.md" in findings[0] and "index copy" in findings[0]


def test_committed_carriage_return_uses_gits_own_binary_window(tmp_path):
    """Post-fix 4: this module skips binary content on a NUL in the first
    kilobyte; git's own window is 8000 bytes. A PDF with CR-only line endings
    and its first NUL between the two was classified `-text` by git and text by
    the check, so it drew a finding whose only named remedy would corrupt it.
    """
    pdf = ("%PDF-1.4" + CR).encode("utf-8") + ("obj" + CR).encode("utf-8") * 300 \
        + bytes([0]) * 8 + ("%%EOF" + NL).encode("utf-8")
    assert bytes([0]) not in pdf[:1024], "the fixture's NUL is past the old window"
    assert bytes([0]) in pdf[:lint.BINARY_WINDOW], "and inside git's"
    _git_repo_with(tmp_path, "paper.pdf", pdf)
    assert lint.check_committed_carriage_return(tmp_path) == []


def test_the_carriage_return_remedy_does_not_assume_the_file_is_text(tmp_path):
    """The same class, one construct on: the check cannot prove a flagged file
    is text, so the remedy stops instructing a rewrite unconditionally.
    """
    _git_repo_with(tmp_path, "note.md", ("row" + CR + "orphan" + NL).encode("utf-8"))
    finding = lint.check_committed_carriage_return(tmp_path)[0]
    assert "if it is text, rewrite it with line feeds" in finding


def test_emitted_ascii_reports_a_file_it_cannot_read(tmp_path, monkeypatch):
    """Post-fix 5: `_read_text` learned to answer rather than raise, and these
    two checks read bytes directly and did not. One locked or vanished file
    took the whole check's territory with it.
    """
    (tmp_path / "mod.py").write_text("x = 1" + NL, encoding="utf-8", newline="")
    real = Path.read_bytes

    def denied(self, *args, **kwargs):
        if self.name == "mod.py":
            raise PermissionError(13, "Permission denied")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", denied)
    findings = lint.check_emitted_ascii(tmp_path)
    assert len(findings) == 1
    assert "could not be read" in findings[0] and "mod.py" in findings[0]
    # and its sibling on the same walk stays silent rather than raising
    assert lint.check_docstring_control_chars(tmp_path) == []


def test_hollow_code_span_caps_an_opening_fence_at_three_spaces(tmp_path):
    """Post-fix 7: the divergence the docstring says must be carried into the
    unification was pinned by nothing, so it could be dropped in silence.

    Four spaces makes an indented code block, not a fence — so the marker is
    content, the text after it is ordinary prose, and a defect there reports.
    """
    (tmp_path / "note.md").write_text(
        "intro" + NL + NL + "    " + TICK*3 + NL + "    code" + NL + NL
        + "tail " + TICK + CR + TICK + "." + NL,
        encoding="utf-8", newline="",
    )
    assert len(lint.check_hollow_code_span(tmp_path)) == 1

# --- check_body_strip_owner (#190) ------------------------------------------
#
# The unlawful case is a strip written by hand; the lawful cases are the engine
# that owns it, the recorded exemption, and -- the ones that actually bit --
# a frontmatter *field* reader, and an ordinary long function that merely
# mentions a marker. Every spelling below was executed during the review that
# found it and shown to return the engine's exact body, so these are pins on
# behaviour rather than on shape.


def _strip_module(spelling: str) -> str:
    """A module whose one function strips frontmatter, in a given spelling."""
    return "def body(text):" + NL + spelling


# Each entry is (label, source, caught). Table-driven because the predicate has
# three verb tuples and four receiver forms, and a per-branch pin is what stops
# a later simplification narrowing the guard while the suite stays green -- the
# defect a mutation battery found in this file's first version, where deleting
# rsplit, partition, rpartition, find, index and rfind changed nothing.
BODY_STRIP_CASES = [
    ("inline split-and-index",
     _strip_module('    if not text.startswith("---"):' + NL
                   + "        return text" + NL
                   + '    return text.split("---", 2)[2]' + NL), True),
    ("split into a name, then index",
     _strip_module('    if text.startswith("---"):' + NL
                   + '        parts = text.split("---", 2)' + NL
                   + "        return parts[2]" + NL
                   + "    return text" + NL), True),
    ("find and slice the tail",
     _strip_module('    if not text.startswith("---"):' + NL
                   + "        return text" + NL
                   + '    end = text.find(chr(10) + "---", 3)' + NL
                   + "    return text[end + 4:]" + NL), True),
    ("rsplit",
     _strip_module('    if not text.startswith("---"):' + NL
                   + "        return text" + NL
                   + '    return text.rsplit("---", 1)[1]' + NL), True),
    ("startswith alone, gating a tail slice",
     "OFFSET = 4" + NL
     + _strip_module('    if not text.startswith("---"):' + NL
                     + "        return text" + NL
                     + "    return text[OFFSET:]" + NL), True),
    ("find alone, with no startswith",
     _strip_module('    end = text.find(chr(10) + "---", 3)' + NL
                   + "    return text[end + 4:]" + NL), True),
    ("rfind alone, with no startswith",
     _strip_module('    end = text.rfind(chr(10) + "---")' + NL
                   + "    return text[end + 4:]" + NL), True),
    ("index alone, with no startswith",
     _strip_module('    end = text.index(chr(10) + "---", 3)' + NL
                   + "    return text[end + 4:]" + NL), True),
    ("partition unpacked to a used tail",
     _strip_module('    _h, _s, rest = text.partition(chr(10) + "---" + chr(10))'
                   + NL + "    return rest" + NL), True),
    ("rpartition subscripted",
     _strip_module('    return text.rpartition(chr(10) + "---")[2]' + NL), True),
    ("separator named by keyword",
     _strip_module('    return text.split(sep="---", maxsplit=2)[2]' + NL), True),
    ("marker hoisted to a module constant",
     'MARKER = "---"' + NL
     + _strip_module('    if not text.startswith(MARKER):' + NL
                     + "        return text" + NL
                     + '    end = text.find(chr(10) + MARKER, 3)' + NL
                     + "    return text[end + 4:]" + NL), True),
    ("marker annotated at module scope",
     'MARKER: str = "---"' + NL
     + _strip_module('    if not text.startswith(MARKER):' + NL
                     + "        return text" + NL
                     + '    end = text.find(chr(10) + MARKER, 3)' + NL
                     + "    return text[end + 4:]" + NL), True),
    ("markers bound by a module tuple assignment",
     'OPEN, CLOSE = "---", "---"' + NL
     + _strip_module('    if not text.startswith(OPEN):' + NL
                     + "        return text" + NL
                     + '    end = text.find(chr(10) + CLOSE, 3)' + NL
                     + "    return text[end + 4:]" + NL), True),
    ("bytes marker",
     'OPEN = b"---"' + NL
     + "def body(data):" + NL
     + "    if not data.startswith(OPEN):" + NL
     + "        return data" + NL
     + '    end = data.find(OPEN, 3)' + NL
     + "    return data[end + 4:]" + NL, True),
    ("chained receiver",
     "def body(path):" + NL
     + '    return path.read_text(encoding="utf-8").split("---", 2)[2]' + NL, True),
    ("attribute receiver",
     "class Reader:" + NL
     + "    def body(self):" + NL
     + '        if not self.text.startswith("---"):' + NL
     + "            return self.text" + NL
     + '        end = self.text.find(chr(10) + "---", 3)' + NL
     + "        return self.text[end + 4:]" + NL, True),
    ("module scope, no function at all",
     'RAW = open("x").read()' + NL
     + 'BODY = RAW.split("---", 2)[2]' + NL, True),
    ("lambda",
     'body = lambda text: text.split("---", 2)[2]' + NL, True),
    # --- lawful ---
    ("a frontmatter FIELD reader takes the bounded head",
     "def fields(text):" + NL
     + '    if not text.startswith("---"):' + NL
     + "        return None" + NL
     + '    end = text.find(chr(10) + "---", 3)' + NL
     + "    return text[3:end]" + NL, False),
    ("an ordinary index on the tested text",
     "def check(text):" + NL
     + '    if text.startswith("---") and not text:' + NL
     + '        raise ValueError("incomplete frontmatter")' + NL
     + "    return text[0]" + NL, False),
    ("a byte-wise extractor slicing the head",
     'OPEN = b"---"' + NL
     + "def frontmatter(data):" + NL
     + "    if not data.startswith(OPEN):" + NL
     + "        return None" + NL
     + "    stop = data.find(OPEN, len(OPEN))" + NL
     + "    return data[:stop]" + NL, False),
    ("partition whose tail is thrown away",
     "def head(text):" + NL
     + '    first, _, _ = text.partition(chr(10) + "---" + chr(10))' + NL
     + "    return first" + NL, False),
    ("a marker mentioned but never sliced",
     "def check(text, rows):" + NL
     + '    if text.startswith("---") and not text:' + NL
     + '        raise ValueError("x")' + NL
     + "    return rows[0]" + NL, False),
]


@pytest.mark.parametrize(
    "label,source,caught",
    [pytest.param(c[0], c[1], c[2], id=c[0].replace(" ", "-")) for c in BODY_STRIP_CASES],
)
def test_the_body_strip_predicate_per_spelling(tmp_path, label, source, caught):
    """One pin per branch of the predicate, in both polarities.

    The two lawful byte-wise cases are the live ones: `tools/roster.py`
    extracts frontmatter that way, and an earlier form of this guard reddened
    it. The `text[0]` case came from an external reviewer, whose point was that
    the first lawful-case test used a *different* name and so never exercised
    the same-receiver path at all.
    """
    _zoned(tmp_path, "tools/measure.py", source)
    findings = lint.check_body_strip_owner(tmp_path)
    assert bool(findings) is caught, (label, findings)
    if caught:
        # Both owners, not one. The red arrives at frontmatter-field readers
        # too -- the predicate cannot always tell them from a body strip -- and
        # a message naming only the strip sends them to a function that
        # discards the fields they came for.
        assert "frontmatterless" in findings[0], findings[0]
        assert "_frontmatter_fields" in findings[0], findings[0]


def test_the_engine_that_owns_the_strip_is_not_reported(tmp_path):
    """The owner defining it is the rule, not a breach of it."""
    _zoned(tmp_path, lint.BODY_STRIP_OWNER, _strip_module(
        '    if not text.startswith("---"):' + NL
        + "        return text" + NL
        + '    end = text.find(chr(10) + "---", 3)' + NL
        + "    return text[end + 4:]" + NL))
    assert lint.check_body_strip_owner(tmp_path) == []


def test_a_recorded_exemption_covers_its_function_and_not_its_neighbour(tmp_path):
    """Exemptions are (path, qualified name), so one lawful strip exempts one.

    Recorded by file, a module holding a sanctioned implementation would
    silently license every strip written under it afterwards -- which is the
    module most likely to attract one.
    """
    _zoned(tmp_path, "tools/lint.py",
           "def _frontmatterless(text):" + NL
           + '    if not text.startswith("---"):' + NL
           + "        return text" + NL
           + '    end = text.find(chr(10) + "---", 3)' + NL
           + "    return text[end + 4:]" + NL
           + NL
           + "def newcomer(text):" + NL
           + '    if not text.startswith("---"):' + NL
           + "        return text" + NL
           + '    end = text.find(chr(10) + "---", 3)' + NL
           + "    return text[end + 4:]" + NL)
    findings = lint.check_body_strip_owner(tmp_path)
    assert len(findings) == 1, findings
    assert "newcomer()" in findings[0], findings[0]


def test_an_exempt_name_reused_at_another_scope_is_not_exempt(tmp_path):
    """Python lets a method reuse a module function's name with no collision.

    Matched on the bare name, the exemption for the module-level strip also
    licensed `Reader._frontmatterless`, which is the guard's soft spot
    deliberately widened by an accident of matching.
    """
    _zoned(tmp_path, "tools/lint.py",
           "class Reader:" + NL
           + "    def _frontmatterless(self, text):" + NL
           + '        if not text.startswith("---"):' + NL
           + "            return text" + NL
           + '        end = text.find(chr(10) + "---", 3)' + NL
           + "        return text[end + 4:]" + NL)
    findings = lint.check_body_strip_owner(tmp_path)
    assert len(findings) == 1, findings
    assert "Reader._frontmatterless()" in findings[0], findings[0]


def test_a_nested_strip_is_reported_once_and_names_the_function_holding_it(tmp_path):
    """An enclosing function must not inherit its nested function's hit.

    Reported twice, the first finding names a function that contains no strip
    and cannot be exempted without exempting everything under it.
    """
    _zoned(tmp_path, "tools/measure.py",
           "def outer():" + NL
           + "    def body(text):" + NL
           + '        if not text.startswith("---"):' + NL
           + "            return text" + NL
           + '        return text.split("---", 2)[2]' + NL
           + "    return body" + NL)
    findings = lint.check_body_strip_owner(tmp_path)
    assert len(findings) == 1, findings
    assert "outer.body()" in findings[0], findings[0]


def test_a_strip_inside_a_test_file_is_out_of_scope(tmp_path):
    """The stated blind spot, pinned so it stays deliberate rather than lost."""
    _zoned(tmp_path, "tools/tests/test_thing.py", _strip_module(
        '    if not text.startswith("---"):' + NL
        + "        return text" + NL
        + '    end = text.find(chr(10) + "---", 3)' + NL
        + "    return text[end + 4:]" + NL))
    assert lint.check_body_strip_owner(tmp_path) == []


def test_an_unparseable_file_is_left_to_the_check_that_reports_it(tmp_path):
    """One broken file must not produce a second finding under a second name.

    Three sibling AST checks skip silently for this reason; check_emitted_ascii
    is what reports it, with the consequence clause this check's own message
    did not carry.
    """
    _zoned(tmp_path, "tools/broken.py", "def (" + NL)
    assert lint.check_body_strip_owner(tmp_path) == []


def test_the_recorded_body_strip_set_is_pinned_to_its_exact_membership():
    """Membership is pinned, so an exemption cannot be added quietly.

    This is not a ratchet: nothing reports an entry that has gone stale, and an
    exemption can still be added by editing this literal alongside it. What it
    buys is that doing so is visible in the diff rather than silent. The
    stale-entry report is recorded, not built -- see the review record.
    """
    assert lint.BODY_STRIP_RECORDED == {
        ("tools/lint.py", "_frontmatterless"),
    }


def test_the_repository_itself_hand_rolls_no_strip():
    """The check on the real tree, which is the tree the rule is about."""
    assert lint.check_body_strip_owner(lint.ROOT) == []

def test_the_scan_and_the_check_read_the_same_predicate(tmp_path):
    """The instrument sizing the blind spot must not have one of its own.

    `body_strip_scan` once ran its own scope loop and so was blind to module
    scope, which the check reads -- so the figure that replaced a false count
    read low for exactly the class the same batch had just added. Both now
    call `lint.hand_rolled_strips`, and this pins that they agree on the case
    that separated them.
    """
    module_scope_strip = ('RAW = open("x").read()' + NL
                          + 'BODY = RAW.split("---", 2)[2]' + NL)
    tree = ast.parse(module_scope_strip)
    assert lint.hand_rolled_strips(tree) == [("<module>", 0)]

    _zoned(tmp_path, "tools/measure.py", module_scope_strip)
    assert len(lint.check_body_strip_owner(tmp_path)) == 1

    scan = tmp_path / "tools" / "tests"
    scan.mkdir(parents=True, exist_ok=True)
    (scan / "test_fixture.py").write_text(module_scope_strip, encoding="utf-8")
    assert lint.check_body_strip_owner(tmp_path) == lint.check_body_strip_owner(tmp_path)
    hits = figures.body_strip_scan(tmp_path)
    assert hits == ["tools/tests/test_fixture.py:0 <module>"], hits


def test_the_always_on_row_budget_is_enforced_in_both_polarities(tmp_path,
                                                                 monkeypatch):
    """The ceiling the two per-file ones became, on the tree it governs.

    Both arms run against this repository rather than a fixture, because the
    quantity is composed from this repository's own doctrine files and its two
    generated roster surfaces -- a synthetic tree has no always-on rows to
    measure, which is the same reason the guard gates on this file's presence.

    The lawful arm is half the pin: a tree at its budget must pass, or the
    ceiling is a ratchet nobody can land a change through.
    """
    assert lint.check_always_on_budget(lint.ROOT) == []
    monkeypatch.setattr(lint, "ALWAYS_ON_ROW_BUDGET_CHARS", 1_000)
    findings = lint.check_always_on_budget(lint.ROOT)
    assert findings, "a row far past its budget reported nothing"
    assert all(f.startswith("always-on-budget:") for f in findings), findings
    assert any("Claude Code" in f for f in findings), findings
    assert any("Codex" in f for f in findings), findings


def test_the_adopter_total_is_budgeted_separately(tmp_path, monkeypatch):
    """The adopter surface is not a runtime row and does not share its ceiling.

    It counts the charter body and the shipped roster and neither doctrine
    file, so a change can move a row without moving it -- which is why it is a
    constant of its own rather than a third row under the same one.
    """
    monkeypatch.setattr(lint, "ALWAYS_ON_ADOPTER_BUDGET_CHARS", 1_000)
    findings = lint.check_always_on_budget(lint.ROOT)
    assert any("adopter total" in f for f in findings), findings
    assert not any("Claude Code" in f for f in findings), (
        "the row budget fired on a change to the adopter constant alone", findings
    )


def test_the_budget_reds_rather_than_passing_when_the_figure_is_gone(tmp_path):
    """A ceiling that stops applying when its input breaks is not a ceiling.

    `always_on_note` swallows every exception and returns a string, which is
    right for a note printed beside the findings and wrong here. #134 records
    the shape this arm exists to keep closed: a guard reading its own input's
    absence as clean makes deleting the input the cheapest route past it.
    """
    make_clean_tree(tmp_path)
    (tmp_path / "tools").mkdir(exist_ok=True)
    (tmp_path / "tools" / "lint.py").write_text("# the guard\n", encoding="utf-8")
    findings = lint.check_always_on_budget(tmp_path)
    assert findings, "no figures.py beside the guard reported nothing"
    assert "not derived" in findings[0], findings


def test_a_tree_without_this_guard_is_not_budgeted(tmp_path):
    """The other polarity of the gate above: a fixture is not this repository.

    Every synthetic tree the suite builds writes part of `tools/` without
    writing this file, and reporting there would red all of them for having no
    always-on surface to measure.
    """
    make_clean_tree(tmp_path)
    assert not (tmp_path / "tools" / "lint.py").is_file()
    assert lint.check_always_on_budget(tmp_path) == []


# --- what the automated reviewers found on PR #291, pinned ------------------

def test_an_incomplete_figure_is_not_a_passing_budget(monkeypatch):
    """An empty `here` walks the row loop zero times and applies no ceiling.

    Raised by an automated reviewer against the first draft of the budget
    check, and it was right: the loop was the only thing standing between a
    malformed figure and a silent pass, which is exactly what `always_on_note`
    was rejected for. [#291]
    """
    import types

    def _figure(payload):
        module = types.SimpleNamespace(
            figure_always_on=lambda root: {"data": payload})
        return lambda name, path: types.SimpleNamespace(
            loader=types.SimpleNamespace(exec_module=lambda m: None)), module

    for payload, expect in (
        ({"here": [], "adopter_total": 1}, "no row for"),
        ({"here": [{"runtime": "Codex", "total": 1}], "adopter_total": 1},
         "no row for Claude Code"),
        ({"here": [{"runtime": r.runtime, "total": 1} for r in lint.roster.SURFACES],
          "adopter_total": None}, "adopter total is not a number"),
    ):
        findings = _budget_over(monkeypatch, payload)
        assert findings, f"{payload} reported nothing"
        assert expect in findings[0], findings


def _budget_over(monkeypatch, payload):
    """Run the budget check against a supplied figure payload."""
    import importlib.util
    import types
    module = types.SimpleNamespace(figure_always_on=lambda root: {"data": payload})

    class _Spec:
        loader = types.SimpleNamespace(exec_module=staticmethod(lambda m: None))

    monkeypatch.setattr(importlib.util, "spec_from_file_location",
                        lambda name, path: _Spec())
    monkeypatch.setattr(importlib.util, "module_from_spec", lambda spec: module)
    return lint.check_always_on_budget(lint.ROOT)


def _budgetable_tree(root: Path) -> None:
    """A fixture tree `check_always_on_budget` will actually measure.

    The guard gates on this file's own presence, so a tree without
    `tools/lint.py` is silent by design -- which is right for the fixtures
    every other test builds and wrong for this one. Written rather than
    monkeypatched because the pin is about what the guard measures on a tree,
    and a patched `ROOT` would pin the patch. [#291]
    """
    make_clean_tree(root)
    (root / "tools").mkdir(exist_ok=True)
    (root / "tools" / "lint.py").write_text("# the guard" + NL, encoding="utf-8")


@pytest.mark.parametrize("surface", [s.directory for s in roster.SURFACES])
@pytest.mark.parametrize("spelling,marker", [
    ("block", "description: >-" + NL + "  "),
    ("plain", "description: A short first line." + NL + "  "),
])
def test_an_unmeasurable_description_cannot_hide_from_the_row_budget(
        tmp_path, surface, spelling, marker):
    """A description the runtime loads whole and this reader measures in part.

    Two spellings, because closing one was not closing the class: the first
    fix rejected `>` and `|` and its own docstring claimed "whichever way it
    is spelled", while a plain scalar continued on indented lines walked
    straight through. Probed at the time on this repository -- thousands of
    characters charged as tens, and the always-on row *falling* while the
    surface grew. Both surfaces, because the guard loops over them and one
    arm was previously unexercised. [#291]

    Off the live tree: this pin used to write into the repository's own
    `.claude/skills/`, so an interrupted run left residue that redded the
    flow's mandated pre-commit step against a file nobody wrote.
    """
    _budgetable_tree(tmp_path)
    cell = tmp_path / surface / "hidden"
    cell.mkdir(parents=True)
    (cell / "SKILL.md").write_text(
        "---" + NL + "name: hidden" + NL + marker + ("x" * 4000) + NL
        + "---" + NL + NL + "# hidden" + NL, encoding="utf-8")
    findings = lint.check_always_on_budget(tmp_path)
    assert findings, f"a {spelling} description of 4,000 chars reported nothing"
    assert any("Write the description on one line" in f for f in findings), findings

    # The lawful arm: a one-line description on the same tree draws no
    # description finding. Not `== []`: the fixture carries no
    # `tools/figures.py`, so the row arithmetic reports it cannot derive --
    # which is that branch's own pin, not this one's.
    (cell / "SKILL.md").write_text(
        "---" + NL + "name: hidden" + NL + "description: One line." + NL
        + "---" + NL + NL + "# hidden" + NL, encoding="utf-8")
    assert not [f for f in lint.check_always_on_budget(tmp_path)
                if "description" in f]


def test_raising_the_row_budget_admits_a_relocation_it_should_refuse(tmp_path):
    """The direction budget pressure actually pushes, which nothing caught.

    Mutating the constant *upward* redded exactly one test -- the literal pin
    -- while the both-polarities arm monkeypatched the constant downward and
    its lawful arm was true for every budget at or above the measured row. So
    the assertion message claiming two behavioural arms was false for the
    raise. This is the arm that makes it true: the headroom is the largest
    relocation the budget tolerates, so a raise is not free, and a test that
    only checks a lowering cannot say so. [#291]
    """
    over = lint.ALWAYS_ON_ROW_BUDGET_CHARS - _largest_row() + 1
    assert over > 0, "the tree already exceeds its own budget"
    assert over <= 1_000, (
        "the headroom exceeds one unit, so the budget admits a relocation "
        f"larger than a cell costs: {over} chars of room"
    )


def _largest_row() -> int:
    """The binding always-on row on the live tree, via the guard's own figure."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "repo_figures_pin", lint.ROOT / "tools" / "figures.py")
    figures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(figures)
    data = figures.figure_always_on(lint.ROOT)["data"]
    return max(row["total"] for row in data["here"])


def _repo_cell(root: Path, name: str, body: str) -> Path:
    """A repo-only cell in a fixture tree, frontmatter and all."""
    cell_dir = root / lint.REPO_CELLS / name
    cell_dir.mkdir(parents=True, exist_ok=True)
    (cell_dir / "SKILL.md").write_text(
        "---" + NL + f"name: {name}" + NL
        + f"description: The {name} cell. Use when testing." + NL
        + "---" + NL + NL + f"# {name}" + NL + body + NL,
        encoding="utf-8")
    return cell_dir


def test_one_repo_only_cell_may_not_name_another_by_path(tmp_path):
    """The mesh ban read the name form and not the path form.

    The fence landed on `` `records` cell `` and left
    `docs/cells/records/SKILL.md` unguarded, so the shape it bans could be
    built through the spelling it did not read. Raised by an automated
    reviewer on PR #291. The lawful arm is a cell naming its own depth by
    path, which must stay silent.
    """
    make_clean_tree(tmp_path)
    _repo_cell(tmp_path, "records", "Depth.")
    _repo_cell(tmp_path, "siting",
               "See `" + lint.REPO_CELLS + "/records/SKILL.md` for the log.")
    roster.write(tmp_path)
    findings = [f for f in lint.check_sideways_deps(tmp_path) if "records" in f]
    assert findings, "a path-form reference between repo-only cells reported nothing"
    assert "by path" in findings[0], findings

    _repo_cell(tmp_path, "siting",
               "Depth is in `" + lint.REPO_CELLS + "/siting/references/x.md`.")
    assert not [f for f in lint.check_sideways_deps(tmp_path) if "siting" in f], (
        "a cell naming its own depth by path was reported as sideways"
    )


def test_a_repo_only_cell_resolves_its_own_references_directory(tmp_path):
    """A cell sheds depth into `references/`, and that link is cell-relative.

    The widened doctrine scan resolved it from the repository root, so the one
    lawful way a repo-only cell sheds depth reported as a dead link -- the
    guard forbidding what the cell exists to allow. Both polarities, because
    the fix must not swallow a genuinely dead link. Raised by an automated
    reviewer on PR #291.
    """
    make_clean_tree(tmp_path)
    cell_dir = _repo_cell(tmp_path, "landing", "Depth is in `references/detail.md`.")
    (cell_dir / "references").mkdir()
    (cell_dir / "references" / "detail.md").write_text("Depth." + NL, encoding="utf-8")
    roster.write(tmp_path)
    assert not [f for f in lint.check_doctrine_references(tmp_path)
                if "detail.md" in f], "a lawful cell-local link was reported dead"

    _repo_cell(tmp_path, "landing", "Depth is in `references/missing.md`.")
    assert [f for f in lint.check_doctrine_references(tmp_path)
            if "missing.md" in f], "a genuinely dead cell-local link went unreported"


def test_a_directory_without_a_cell_file_is_not_a_cell(tmp_path):
    """`docs/cells/ghost/` resolved for the guard and loaded in no runtime.

    A reference is meant to be followable; one that satisfies the checker and
    nothing else is the failure the reference form exists to prevent. Raised by
    an automated reviewer on PR #291.
    """
    make_clean_tree(tmp_path)
    (tmp_path / lint.REPO_CELLS / "ghost").mkdir(parents=True)
    _repo_cell(tmp_path, "siting", "The `ghost` cell has it.")
    roster.write(tmp_path)
    findings = [f for f in lint.check_cell_references(tmp_path) if "ghost" in f]
    assert findings, "a directory with no SKILL.md satisfied a cell reference"


def test_only_the_two_sanctioned_imports_are_lawful_in_the_doctrine(tmp_path):
    """An import is not a line, it is the file it names.

    The row budget measures the doctrine files; the runtime inlines whatever
    they `@`-import. Probed on this repository: one added import line moved the
    row 17 characters while the session loaded 5,482 more, with the lint clean
    -- so the move the ceiling exists to refuse was a one-liner, and the
    guard's own message said it was not. Both polarities, because a guard that
    refuses the charter import would break every tree. [#291]
    """
    make_clean_tree(tmp_path)
    assert not [f for f in lint.check_doctrine(tmp_path) if "doctrine-import" in f]

    agents = tmp_path / "AGENTS.md"
    agents.write_text(agents.read_text(encoding="utf-8")
                      + NL + "@docs/values.md" + NL, encoding="utf-8")
    findings = [f for f in lint.check_doctrine(tmp_path) if "doctrine-import" in f]
    assert findings, "an unsanctioned import in AGENTS.md reported nothing"
    assert "@docs/values.md" in findings[0], findings

    # The pointer file, on the same tree: an import lawful in AGENTS.md is not
    # lawful here, because CLAUDE.md's whole job is to import AGENTS.md.
    agents.write_text(agents.read_text(encoding="utf-8")
                      .replace(NL + "@docs/values.md" + NL, NL), encoding="utf-8")
    pointer = tmp_path / "CLAUDE.md"
    pointer.write_text(pointer.read_text(encoding="utf-8")
                       + NL + "@skills/charter/SKILL.md" + NL, encoding="utf-8")
    assert [f for f in lint.check_doctrine(tmp_path) if "doctrine-import" in f], (
        "an import lawful in AGENTS.md is not lawful in the pointer file"
    )


def test_a_repo_only_cell_carries_its_citations_and_paths_at_depth(tmp_path):
    """The scan reaches where this repository tells authors to put depth.

    `cell-structure.md` sanctions shedding into `references/`, so a scan
    stopping at `SKILL.md` is silent in the one place the material directs
    depth to. Identical prose redded one directory up and passed one directory
    down. Both polarities: a resolving citation and a live path stay silent.
    [#291]
    """
    make_clean_tree(tmp_path)
    make_entry(tmp_path, 42)
    cell = _repo_cell(tmp_path, "records", "Depth.")
    (cell / "references").mkdir()
    depth = cell / "references" / "detail.md"
    depth.write_text("As decided in [D-42], see `docs/values.md`." + NL,
                     encoding="utf-8")
    (tmp_path / "docs" / "values.md").write_text("Ranking." + NL, encoding="utf-8")
    roster.write(tmp_path)
    assert not [f for f in lint.check_doctrine_citations(tmp_path) if "detail" in f]
    assert not [f for f in lint.check_doctrine_references(tmp_path) if "detail" in f]

    depth.write_text("As decided in [D-9999], see `docs/gone.md`." + NL,
                     encoding="utf-8")
    assert [f for f in lint.check_doctrine_citations(tmp_path) if "detail" in f], (
        "a dangling citation in a cell's own depth reported nothing"
    )
    assert [f for f in lint.check_doctrine_references(tmp_path) if "detail" in f], (
        "a dead repo path in a cell's own depth reported nothing"
    )


def test_the_always_on_figure_measures_characters_and_not_bytes(tmp_path):
    """CRLF is what keeps the two apart, and this repository expects CRLF.

    The pins holding this were deleted with the per-file ceilings they tested,
    and their fixture constants and explanatory comment survived as dead code.
    Mutating `figure_always_on`'s reader to `read_bytes().decode()` then left
    the whole suite green. On the Windows leg that regression overstates every
    row by one character per line against a headroom of one cell, turning a
    lawful tree red on one leg of the matrix only. [#291]
    """
    import importlib.util

    _budgetable_tree(tmp_path)
    agents = tmp_path / "AGENTS.md"
    body = agents.read_text(encoding="utf-8")
    with open(agents, "wb") as handle:
        handle.write(body.replace(NL, chr(13) + NL).encode("utf-8"))
    raw = agents.read_bytes()
    chars = len(agents.read_text(encoding="utf-8"))
    assert len(raw) > chars, "the fixture did not actually land CRLF on disk"

    spec = importlib.util.spec_from_file_location(
        "repo_figures_crlf", lint.ROOT / "tools" / "figures.py")
    figures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(figures)
    data = figures.figure_always_on(tmp_path)["data"]
    assert data["agents"] == chars, (
        f"the figure measured {data['agents']} against {chars} characters and "
        f"{len(raw)} bytes -- it is counting bytes"
    )


# --- the cell-body report: every cell sized at the mandated checkpoint (#302) -


def _derivable_tree(root: Path) -> None:
    """A fixture tree where `tools/figures.py` actually derives.

    `cell_body_note` loads `root/tools/figures.py` by path, and that file
    reaches `lint`, `winio` and the shipped engine -- so the fixture carries
    the real machinery. A stub would pin the test's own arithmetic instead of
    the derivation, which is the thing under test.
    """
    import shutil

    repo = Path(__file__).resolve().parents[2]
    shutil.copytree(repo / "tools", root / "tools",
                    ignore=shutil.ignore_patterns("tests", "__pycache__"))
    shutil.copytree(repo / "lib", root / "lib",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(repo / "skills" / "authoring" / "scripts",
                    root / "skills" / "authoring" / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__"))


def _shipped_cell(root: Path, name: str, body: str) -> Path:
    """A shipped cell in a fixture tree, frontmatter and all."""
    cell = root / "skills" / name
    cell.mkdir(parents=True, exist_ok=True)
    (cell / "SKILL.md").write_text(
        "---" + NL + f"name: {name}" + NL
        + f"description: The {name} cell. Use when testing." + NL
        + "---" + NL + NL + f"# {name}" + NL + body + NL,
        encoding="utf-8")
    return cell


def _rows(note: str) -> list[tuple[str, int, str]]:
    """Name, body and budget phrase for each row of a rendered report."""
    found = []
    for line in note.splitlines():
        match = re.match(r"^  (\S+)\s+([\d,]+)  (.+)$", line)
        if match:
            found.append((match[1], int(match[2].replace(",", "")), match[3]))
    return found


def test_the_report_sizes_every_cell_of_both_roster_sources(tmp_path):
    """Criterion 1 and 2: the map is not the cells, and neither is one source.

    `check_doctrine` iterates `CELL_BODY_BUDGET_CHARS`, so before this a cell
    absent from it was sized by nothing at either mandated command, the
    charter excepted. A
    shipped-only report would be the hand-written carve-out this change exists
    to avoid, so a repo-only cell is in the fixture and in the assertion.
    """
    _derivable_tree(tmp_path)
    _shipped_cell(tmp_path, "alpha", "Shipped body, a little longer than beta's.")
    _repo_cell(tmp_path, "beta", "Repo-only body.")

    note = lint.cell_body_note(tmp_path)
    names = [name for name, _, _ in _rows(note)]
    assert "alpha" in names, note
    assert "beta" in names, "a repo-only cell went unsized"

    for name, body, _ in _rows(note):
        source = roster.cell_sources(tmp_path)[name]
        text = (tmp_path / source / name / roster.CELL_FILE).read_text(encoding="utf-8")
        assert body == len(lint._frontmatterless(text)), (
            f"{name}'s row is not the body the guard measures")


def test_the_report_is_ordered_by_body_descending(tmp_path):
    """Criterion 3, as a total property rather than a fixture.

    Three cold seats each found a fresh wrong ordering -- by name, by source,
    by budget status -- that the previous fixture admitted. The set of wrong
    orderings a fixture must trap is not closed; the right ordering is one
    condition over the output, so that is what this asserts, here and on the
    repository itself.
    """
    _derivable_tree(tmp_path)
    # Names, sources and sizes deliberately disagree: were the report ordered
    # by any of the three, this fixture would catch it.
    _shipped_cell(tmp_path, "zulu", "z" * 400)
    _shipped_cell(tmp_path, "alpha", "a" * 100)
    _repo_cell(tmp_path, "mike", "m" * 800)

    for tree in (tmp_path, lint.ROOT):
        bodies = [body for _, body, _ in _rows(lint.cell_body_note(tree))]
        assert bodies, tree
        assert bodies == sorted(bodies, reverse=True), (
            f"a row on {tree} is smaller than one beneath it: {bodies}")


def test_a_cell_added_to_either_source_is_sized_without_editing_a_list(tmp_path):
    """Criterion 4. The enumeration reads the roster, not a literal pair."""
    _derivable_tree(tmp_path)
    _shipped_cell(tmp_path, "alpha", "Body.")
    before = [name for name, _, _ in _rows(lint.cell_body_note(tmp_path))]
    assert "later" not in before

    _repo_cell(tmp_path, "later", "Added after the first run.")
    after = [name for name, _, _ in _rows(lint.cell_body_note(tmp_path))]
    assert "later" in after, "a new cell needed a list edited to be sized"


def test_the_report_says_so_when_it_cannot_derive(tmp_path):
    """Criterion 5, first direction.

    A report that vanishes when its input breaks tells the reader nothing and
    reads exactly like a tree with nothing to report. `always_on_note` states
    what it could not derive and moves on; this copies it.
    """
    _shipped_cell(tmp_path, "alpha", "Body.")
    assert not (tmp_path / "tools" / "figures.py").is_file()

    note = lint.cell_body_note(tmp_path)
    assert "not derived" in note, note
    assert not _rows(note), "rows were rendered from a tree that cannot derive"


def test_a_tree_with_no_cells_says_so_rather_than_going_silent(tmp_path):
    """Criterion 5, second direction.

    Nothing to report is not a failure to derive, and silence would say
    neither -- so each state produces its own text.
    """
    _derivable_tree(tmp_path)
    note = lint.cell_body_note(tmp_path)
    assert "no cells" in note, note
    assert "not derived" not in note, "an empty tree reported a derivation failure"


def test_the_charter_row_names_both_budgets_that_bind_it():
    """Criterion 1's charter clause, which a cold seat caught ratified.

    The charter's body is a term in every always-on row and in the adopter
    total, so `check_always_on_budget` reds on it at the same command -- it is
    enforced today while absent from `CELL_BODY_BUDGET_CHARS`. A row reading
    `no budget` would be false, and would be false about the half of the brief
    that promises to say which cells have no limit. Both constants are named
    because the binding one is the adopter total, which a reader reaches
    second.
    """
    assert lint.CHARTER not in lint.CELL_BODY_BUDGET_CHARS, (
        "the charter row must come from the other guard, not a smuggled entry")

    rows = {name: against for name, _, against in _rows(lint.cell_body_note(lint.ROOT))}
    assert "charter" in rows, "the charter was not sized at all"
    against = rows["charter"]
    assert "no budget" not in against, "the charter reported as uncapped, and it is not"
    assert f"{lint.ALWAYS_ON_ROW_BUDGET_CHARS:,}" in against, against
    assert f"{lint.ALWAYS_ON_ADOPTER_BUDGET_CHARS:,}" in against, (
        "the binding budget of the two went unnamed")
    assert "shared" in against, "a shared budget stated as though it were the cell's own"


def test_the_reported_number_is_the_body_and_not_the_cell_total(tmp_path):
    """Criterion 1's number clause.

    `figure_cell_total` is the neighbouring function in the module this report
    is hosted in, and printing it beside a body budget forks the figure from
    the guard that enforces it.
    """
    _derivable_tree(tmp_path)
    cell = _shipped_cell(tmp_path, "alpha", "Short body.")
    (cell / "references").mkdir()
    (cell / "references" / "detail.md").write_text("d" * 5000, encoding="utf-8")

    body = {name: size for name, size, _
            in _rows(lint.cell_body_note(tmp_path))}["alpha"]
    text = (cell / "SKILL.md").read_text(encoding="utf-8")
    assert body == len(lint._frontmatterless(text))
    assert body < 5000, "the row carried the cell total rather than the body"


def test_the_report_carries_nothing_evaluative():
    """Criterion 6's marker clause, as a shape over every row and the header.

    The first version of this pin was beatable three ways and a review found
    all three: a marker in the header, which it sliced away; a marker inside
    the name field, which `\\S+` accepted; and free text on the `shared with`
    tail, where `[^!]+` excluded only the exclamation mark it had been probed
    with. The middle one is the one that mattered -- `engagement-LARGE` keyed
    to an invented 10,000-character threshold rendered green, which is
    criterion 6's falsifier almost verbatim. Every field is bounded now and
    the header is asserted whole rather than discarded. [#302]

    Nothing guards the characters of a cell name, so a cell named outside
    `[a-z][a-z0-9-]*` reds this pin rather than the report. That is the safe
    direction and it is deliberate.
    """
    lawful = re.compile(
        r"^  [a-z][a-z0-9-]*\s+[\d,]+  ("
        r"no body budget"
        r"|of [\d,]+, headroom -?[\d,]+"
        r"|shared with always-on row [\d,]+, adopter total [\d,]+"
        r")$")
    lines = lint.cell_body_note(lint.ROOT).splitlines()
    assert lines[0] == "cell bodies here, largest first:", lines[0]
    assert len(lines) > 1
    for line in lines[1:]:
        assert lawful.match(line), f"row carries something beyond size and budget: {line!r}"


def test_the_lint_prints_every_cell_body_at_the_mandated_command(capsys):
    """Criterion 1, against the command it names and the tree it names.

    Every other pin here calls `cell_body_note` directly and every fixture
    tree carries cells of a few dozen characters, so three separate mutations
    left the whole suite green: deleting the `print` from `main()` (the block
    vanishes from the mandated command); returning a budget a thousand over
    the guard's; and returning `None` for every budget, which prints
    `no body budget` against both genuinely capped cells -- the exact false row
    a cold seat blocked this change's artifact over. The pin thirteen lines
    from the omission records the same incident for the always-on line: *"This
    asserted only that the substring was present, so it stayed green while the
    line printed one scalar that was some other runtime's."* [#302]

    **The expectation is derived from the guard's own constants, never from
    `figures.cell_budgets`** -- reading the renderer's source of truth would
    make this tautological, which is the one way to write it wrong.
    """
    lint.main()
    out = capsys.readouterr().out
    assert "cell bodies here, largest first:" in out, out

    expected = {}
    for name, source in roster.cell_sources(lint.ROOT).items():
        rel = f"{source}/{name}/{roster.CELL_FILE}"
        body = len(lint._frontmatterless(
            (lint.ROOT / rel).read_text(encoding="utf-8", errors="replace")))
        own = lint.CELL_BODY_BUDGET_CHARS.get(rel)
        if own is not None:
            against = f"of {own:,}, headroom {own - body:,}"
        elif rel == lint.CHARTER:
            against = (f"shared with always-on row "
                       f"{lint.ALWAYS_ON_ROW_BUDGET_CHARS:,}, adopter total "
                       f"{lint.ALWAYS_ON_ADOPTER_BUDGET_CHARS:,}")
        else:
            against = "no body budget"
        expected[name] = (body, against)

    printed = {name: (body, against) for name, body, against in _rows(out)}
    assert set(printed) == set(expected), (
        f"missing {set(expected) - set(printed)}, extra {set(printed) - set(expected)}")
    for name, (body, against) in expected.items():
        assert printed[name][0] == body, f"{name}: printed {printed[name][0]}, body is {body}"
        assert printed[name][1] == against, f"{name}: printed {printed[name][1]!r}"


def test_the_report_reports_rather_than_raising_on_a_bad_shape(tmp_path):
    """`cell_body_note`'s own comment cites the pin it did not write.

    That comment points at `always_on_note`'s recorded incident -- the read
    inside the guard and the formatting outside it, so a malformed payload
    escaped as a KeyError and `main()` answered the mandated command with a
    traceback. The hazard is identical here and nothing held it; the defense
    stage of this change's review originated the finding. [#302]
    """
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "figures.py").write_text(
        "def cell_body_rows(root):" + NL
        + "    return [{'name': 'alpha'}]" + NL
        + "def cell_body_block(rows):" + NL
        + "    return rows[0]['body']" + NL,
        encoding="utf-8")

    note = lint.cell_body_note(tmp_path)
    assert "not derived" in note, note
    assert "KeyError" in note, note



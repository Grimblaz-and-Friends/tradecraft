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


NL = chr(10)
BS = chr(92)


def _write_cell(skill: Path, body: str) -> None:
    """Write a cell body under valid frontmatter.

    Every cell needs a parseable name and description now -- the runtime indexes
    those and nothing else until the cell fires, and a cell without them loads
    with empty metadata. The fixtures exercise body content, so the header is
    boilerplate here; it is not boilerplate in the tree.
    """
    # A depth file no body names is an orphan under check_depth_index, and
    # the fixtures that carry one are about other checks. Naming any the
    # caller did not keeps each fixture about its own check.
    ref_dir = skill / "references"
    depth = sorted(f.name for f in ref_dir.glob("*.md")) if ref_dir.is_dir() else []
    unnamed = [n for n in depth if f"references/{n}" not in body]
    if unnamed:
        body = body + NL + "Depth lives in " + ", ".join(
            f"references/{n}" for n in unnamed) + "." + NL
    (skill / "SKILL.md").write_text(
        "---" + NL + f"name: {skill.name}" + NL
        + "description: A fixture cell." + NL + "---" + NL + NL + body,
        encoding="utf-8",
    )


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
    _wire_charter(root)
    _write_marketplace(root, "./")


def _zoned(root: Path, rel: str, body: str) -> None:
    """Write a module in the repository-shaped fixture population."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


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


def test_harness_adapter_uses_shipped_and_repo_cell_contract_populations(tmp_path):
    """The wrapper supplies scope; the shipped predicate supplies detection."""
    make_clean_tree(tmp_path)
    token = "$" + "{CLAUDE_" + "PLUGIN_ROOT}"
    _write_cell(
        tmp_path / "skills" / "example-skill",
        "The shipped contract names " + token + ".\n",
    )
    cell = tmp_path / "docs" / "cells" / "repo-cell"
    cell.mkdir(parents=True)
    (cell / "SKILL.md").write_text("The local contract names " + token + ".\n", encoding="utf-8")
    history = tmp_path / "docs" / "history.md"
    history.write_text("Frozen history names " + token + ".\n", encoding="utf-8")

    findings = lint.check_harness_tokens(tmp_path)

    assert len(findings) == 2, findings
    assert all("history.md" not in finding for finding in findings)


def test_this_repository_names_its_streams_at_every_launch():
    """The wrapper runs the shipped stream predicate against this repository."""
    assert lint.check_subprocess_streams(Path(__file__).resolve().parents[2]) == []


# --- settling index -------------------------------------------------------
















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


def test_zone_wall_fires_on_rooted_reference(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "See docs/architecture/adr/README.md for rules.\n")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "zone-wall" in findings[0]


def test_zone_wall_fires_on_a_decision_marker_in_shipped_prose(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "Keep the boundary because the decision says so [D-9].\n")

    findings = lint.check_zone_wall(tmp_path)

    assert len(findings) == 1
    assert "decision marker '[D-9]' as shipped rationale" in findings[0]


def test_zone_wall_accepts_a_reason_stated_in_shipped_prose(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "Keep the boundary because consumers receive no local files.\n")

    assert lint.check_zone_wall(tmp_path) == []


def test_zone_wall_fires_on_relative_parent_reference(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "[the constitution](../../docs/architecture/adr/README.md)\n")
    findings = lint.run(tmp_path)
    assert len(findings) == 1 and "zone-wall" in findings[0]


def test_zone_wall_fires_on_uppercase_and_backslash_but_not_own_subdir(tmp_path):
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, # ./tools/ inside a skill resolves to the skill's OWN tools/ subdir â€”
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


# --- the charter, which costs nothing to point at ---------------------------

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


def _edges(root: Path, source: str) -> list[str]:
    """The cells `source` points at, as the pointer graph reads them.

    The graph rather than the finding, because a lawful pointer is no longer
    a finding: a fence or a wrap that stopped being read would drop an edge
    from the cycle check and show up in no assertion at all. [#404]
    """
    return sorted({edge.target for edge in lint.cell_pointer_graph(root)[source]})


def test_a_cell_may_point_at_a_sibling_and_a_circle_may_not_close(tmp_path):
    """The permission and its bound, in one fixture.

    What is refused is the shape the pointer rule exists to prevent: two cells
    neither of which can be read or revised without the other.
    """
    make_clean_tree(tmp_path)
    other = tmp_path / "skills" / "other-skill"
    other.mkdir(parents=True)
    _write_cell(other, "Depth lives in the `example-skill` cell.\n")
    assert _edges(tmp_path, "other-skill") == ["example-skill"]
    assert lint.run(tmp_path) == []

    _write_cell(tmp_path / "skills" / "example-skill",
                "Depth lives in references/detail.md, "
                "and the rest in the `other-skill` cell.\n")
    findings = [f for f in lint.run(tmp_path) if "pointer-cycle" in f]
    assert len(findings) == 1, lint.run(tmp_path)
    assert "example-skill" in findings[0] and "other-skill" in findings[0]
    # The hops, not just the members: a finding naming the ring and not the
    # sentences that make it leaves the reader the archaeology.
    assert "skills/other-skill/SKILL.md" in findings[0], findings[0]
    assert "skills/example-skill/SKILL.md" in findings[0], findings[0]


def test_a_rooted_docs_cells_path_is_read_against_the_repo_only_roster(tmp_path):
    """`docs/cells/<name>/` names a repo-only cell or it names nothing.

    A shipped cell's name in that path resolves to no cell at all, so a
    predicate answering from the union of both cell sources reported prose about a
    nonexistent path as a reference to a repo-only cell that does not exist --
    a red lint on lawful prose, which blocks work exactly as hard as passing
    unlawful work. Both polarities, because the whole defect was that the
    unlawful arm kept working while the lawful one broke. Found by an external
    reviewer on PR #437. [#404]
    """
    make_clean_tree(tmp_path)
    _repo_cell(tmp_path, "records", "Depth.")
    _repo_cell(tmp_path, "board", "Depth.")

    # `example-skill` is a shipped cell, so this path names no cell: lawful.
    _repo_cell(tmp_path, "board",
               "The historical path docs/cells/example-skill/SKILL.md is gone.")
    assert [f for f in lint.run(tmp_path) if "sideways-dep" in f] == [], lint.run(tmp_path)

    # A real repo-only cell named by path is still the finding it always was.
    _repo_cell(tmp_path, "board", "See docs/cells/records/SKILL.md.")
    findings = [f for f in lint.run(tmp_path) if "sideways-dep" in f]
    assert len(findings) == 1 and "records" in findings[0], lint.run(tmp_path)








def test_only_a_cell_s_prose_makes_a_pointer(tmp_path):
    """A reserved form in a cell's script is code, not a pointer.

    The graph walked every file in the cell while the figure it feeds counts
    markdown only, so one comment in a `.py` credited a cell the whole of
    another's prose, and two of them redded the command the landing procedure
    mandates -- naming a circle between two files no session reads as prose.
    Both polarities: the same sentence in a `.md` still makes the edge.
    [PR #437 review, M6]
    """
    make_clean_tree(tmp_path)
    other = tmp_path / "skills" / "other-skill"
    (other / "scripts").mkdir(parents=True)
    _write_cell(other, "A sibling cell." + NL)
    (other / "scripts" / "run.py").write_text(
        "# The rule is the `example-skill` cell's." + NL, encoding="utf-8")
    assert _edges(tmp_path, "other-skill") == [], lint.cell_pointer_graph(tmp_path)
    assert lint.run(tmp_path) == []

    (other / "references").mkdir(exist_ok=True)
    (other / "references" / "depth.md").write_text(
        "The rule is the `example-skill` cell's." + NL, encoding="utf-8")
    assert _edges(tmp_path, "other-skill") == ["example-skill"]


def test_the_cycle_finding_names_the_route_in_order(tmp_path):
    """The ordered walk is the half that says which hop to break where.

    Deleting the route from the message left the whole suite green, because
    every pin asserted only that each member's name appeared somewhere in the
    finding -- and the hop clause already carries every member as a target.
    Direction and order in a printed row is the class the experience session
    caught once on the reach block. [PR #437 review, M30]
    """
    make_clean_tree(tmp_path)
    for name in ("beta", "gamma"):
        (tmp_path / "skills" / name).mkdir(parents=True)
    _write_cell(tmp_path / "skills" / "example-skill",
                "Depth lives in references/detail.md, then the `beta` cell." + NL)
    _write_cell(tmp_path / "skills" / "beta", "On to the `gamma` cell." + NL)
    _write_cell(tmp_path / "skills" / "gamma",
                "Back to the `example-skill` cell." + NL)
    findings = [f for f in lint.run(tmp_path) if "pointer-cycle" in f]
    assert len(findings) == 1, lint.run(tmp_path)
    assert "beta -> gamma -> example-skill -> beta" in findings[0], findings[0]
    # And the remedy says a hop is a pair of cells, not the one line named.
    assert "not only the line named here" in findings[0], findings[0]


def test_a_three_cell_circle_names_every_member(tmp_path):
    """A ring longer than two, because a two-cell case passes a guard that
    only looks one hop out -- and because the finding has to name every cell
    a reader must choose between to break the ring."""
    make_clean_tree(tmp_path)
    for name in ("beta", "gamma"):
        (tmp_path / "skills" / name).mkdir(parents=True)
    _write_cell(tmp_path / "skills" / "example-skill",
                "Depth lives in references/detail.md, then the `beta` cell.\n")
    _write_cell(tmp_path / "skills" / "beta", "On to the `gamma` cell.\n")
    _write_cell(tmp_path / "skills" / "gamma",
                "Back to the `example-skill` cell.\n")
    findings = [f for f in lint.run(tmp_path) if "pointer-cycle" in f]
    assert len(findings) == 1, lint.run(tmp_path)
    for name in ("example-skill", "beta", "gamma"):
        assert name in findings[0], findings[0]
    # A chain that is not a ring is lawful however long it is: breaking one
    # hop must clear the finding, which is what makes the finding actionable.
    _write_cell(tmp_path / "skills" / "gamma", "The end of the chain.\n")
    assert lint.run(tmp_path) == []


def test_a_pointer_at_the_charter_closes_no_circle(tmp_path):
    """The charter is loaded before substantive work in every session, so
    following a pointer at it loads nothing and can close no circle of
    loading. Both directions at once, which is the shape that would ring if
    the charter were an ordinary node."""
    make_clean_tree(tmp_path)
    charter = tmp_path / "skills" / "charter"
    (charter / "SKILL.md").write_text(
        "---" + NL + "name: charter" + NL + "description: The binding rules." + NL
        + "---" + NL + NL
        + "The depth behind this rule lives in the `example-skill` cell." + NL,
        encoding="utf-8",
    )
    _write_cell(tmp_path / "skills" / "example-skill",
                "The rule itself is stated by the `charter` cell.\n")
    assert lint.run(tmp_path) == []
    assert _edges(tmp_path, "example-skill") == []
    assert _edges(tmp_path, "charter") == ["example-skill"]


def test_a_cell_naming_itself_is_not_a_pointer(tmp_path):
    """Depth inside one cell is not a dependency between two, and a self-edge
    would make every cell that mentions its own name its own circle."""
    make_clean_tree(tmp_path)
    _write_cell(tmp_path / "skills" / "example-skill",
                "This is the `example-skill` cell, and depth lives in "
                "references/detail.md.\n")
    assert _edges(tmp_path, "example-skill") == []
    assert lint.run(tmp_path) == []


def test_the_walls_refused_direction_is_not_an_edge(tmp_path):
    """A shipped cell naming a repo-only one is check 6's finding.

    Reading it as an edge would price one defect as two and could report a
    circle one of whose hops is a finding rather than a pointer. The lawful
    direction is the other one, and a ring built entirely out of repo-only
    cells still closes.
    """
    make_clean_tree(tmp_path)
    _repo_cell(tmp_path, "records", "Depth.")
    _write_cell(tmp_path / "skills" / "example-skill",
                "Depth lives in references/detail.md, then the `records` cell.\n")
    findings = lint.run(tmp_path)
    assert len(findings) == 1, findings
    assert "cell-reference" in findings[0] and "records" in findings[0]
    assert [f for f in findings if "pointer-cycle" in f] == []
    assert _edges(tmp_path, "example-skill") == []

    # The lawful direction, and then a repo-only ring, which is the mesh the
    # ban's [#260] arm was aimed at and which the cycle check now refuses.
    _write_cell(tmp_path / "skills" / "example-skill",
                "Depth lives in references/detail.md.\n")
    _repo_cell(tmp_path, "records", "The standard is the `example-skill` cell.")
    _repo_cell(tmp_path, "board", "See the `records` cell.")
    assert lint.run(tmp_path) == []
    assert _edges(tmp_path, "records") == ["example-skill"]
    _repo_cell(tmp_path, "records", "See the `board` cell.")
    findings = [f for f in lint.run(tmp_path) if "pointer-cycle" in f]
    assert len(findings) == 1, lint.run(tmp_path)
    assert "records" in findings[0] and "board" in findings[0]


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
    assert _edges(tmp_path, "other-skill") == []
    assert lint.run(tmp_path) == []
    _write_cell(other, "Depth lives in the `example-skill` cell." + NL)
    assert _edges(tmp_path, "other-skill") == ["example-skill"]
    assert lint.run(tmp_path) == []


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
    assert _edges(tmp_path, "other-skill") == ["example-skill"]
    # And it counts as a hop, which is where dropping it would cost something:
    # the wrapped half of a circle must still close it.
    _write_cell(tmp_path / "skills" / "example-skill",
                "Depth lives in references/detail.md, and the `other-skill`"
                + NL + "cell." + NL)
    findings = [f for f in lint.run(tmp_path) if "pointer-cycle" in f]
    assert len(findings) == 1, lint.run(tmp_path)
    assert "other-skill" in findings[0]
    # The wrap still reads as a reference from lib/, where the name form is
    # judged one reference at a time because a hook is not a cell.
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "README.md").write_text(
        "Emits the `example-skill`" + NL + "cell on stdout." + NL, encoding="utf-8")
    wrapped = [f for f in lint.run(tmp_path)
               if "sideways-dep" in f and "across a line break" in f]
    assert len(wrapped) == 1 and "from hooks/" in wrapped[0], lint.run(tmp_path)
    (hooks / "README.md").unlink()
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

    Depth-shedding makes `references/` the cell-wide standard, so a pointer
    at a file that moved strands a session exactly as a renamed cell does --
    and the body deliberately no longer carries what the pointer promises.
    """
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    assert lint.run(tmp_path) == []
    (skill / "references" / "detail.md").rename(skill / "references" / "moved.md")
    findings = lint.run(tmp_path)
    # Two guards see this and both are right: the pointer resolves against
    # nothing, and the index now names a file that is gone while the renamed
    # one is named by nobody. This test owns the first.
    pointer = [f for f in findings if "reference-pointer" in f]
    assert len(pointer) == 1 and "references/detail.md" in pointer[0]
    assert all("reference-pointer" in f or "depth-index" in f for f in findings)


def test_a_references_pointer_resolves_written_with_either_separator(tmp_path):
    """Both polarities on the separator, which is where the guard was blind.

    A Windows session writing the pointer from its own shell produces
    `references\\detail.md`. Matching only the forward form let that name a
    file that need not exist while the lint stayed green -- so the backslash
    form has to fire when the target is gone and stay quiet when it is there,
    exactly as the forward form does. [#337]
    """
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    body = (skill / "SKILL.md").read_text(encoding="utf-8")
    (skill / "SKILL.md").write_text(
        body.replace("references/detail.md", "references\\detail.md"),
        encoding="utf-8",
        newline="\n",
    )
    assert [f for f in lint.run(tmp_path) if "reference-pointer" in f] == []
    (skill / "references" / "detail.md").rename(skill / "references" / "moved.md")
    findings = [f for f in lint.run(tmp_path) if "reference-pointer" in f]
    assert len(findings) == 1
    assert "references\\detail.md" in findings[0]


# Every check `run` calls, in call order. Literal on purpose: deriving this
# from `run` would make the test agree with itself, which is what let the list
# say eight while `run` called ten, silently, from #156 until #169 found it.
LINT_CHECKS_IN_ORDER = (
    "check_zone_wall",
    "check_harness_tokens",
    "check_charter_cell",
    "check_cell_frontmatter",
    "check_sideways_deps",
    "check_cell_references",
    "check_depth_index",
    "check_doctrine_citations",
    "check_doctrine_references",
    "check_doctrine",
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

    A retired slot holds its number because frozen decisions cite these
    identifiers. The sequence has no holes, and every check `run` calls is
    enumerated. A slot is retired by opening with that word.
    """
    called = tuple(check.__name__ for check in lint.CHECKS)
    assert called == LINT_CHECKS_IN_ORDER, (
        "CHECKS names checks this list does not, or in another order"
    )
    items = re.findall(r"^\s*(\d+)\.\s+(\S+)", lint.__doc__, re.M)
    assert [int(n) for n, _ in items] == list(range(1, len(items) + 1)), (
        "the docstring's numbering has a hole in it; a retired check keeps its "
        "number rather than letting the ones below it shift up"
    )
    live = [n for n, first in items if first != "retired."]
    assert len(live) == len(LINT_CHECKS_IN_ORDER), (
        "the docstring's live checks do not match what run() calls -- "
        f"{len(live)} enumerated, {len(LINT_CHECKS_IN_ORDER)} called. If a "
        "slot was just retired, the sentinel is the exact token `retired.` "
        "as the first word after the number; any other spelling counts live"
    )
    retired = {int(number) for number, first in items if first == "retired."}
    assert retired == {8, 12, 13, 19, 26, 27, 28, 29}


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
    assert _edges(tmp_path, "other-skill") == ["example-skill"], (
        "a ``` quoted inside a ```` block must not end the fence"
    )
    mismatched = ("```" + NL + "shown, not made" + NL + "~~~" + NL
                  + NL + "Depth lives in the `example-skill` cell." + NL)
    _write_cell(other, mismatched)
    assert _edges(tmp_path, "other-skill") == [], (
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
        assert _edges(tmp_path, "other-skill") == ["example-skill"], body
    for fence in ("```", "```text", "~~~", "````"):
        closer = "~~~" if fence == "~~~" else fence.rstrip("text") or "```"
        _write_cell(other, fence + NL + "the `example-skill` cell" + NL + closer + NL)
        assert _edges(tmp_path, "other-skill") == [], fence


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
    change to that constant [#164]. The rule is about one named cell -- the
    one whose edges are dropped from the pointer graph -- so the name is
    pinned literally here."""
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















































# Every way the callout has been made dead without deleting anything. Each was
# measured against a plain substring check first, and each passed it clean â€”
# which is why the check reads the job's own block rather than the file.


# The lawful polarity. A guard that blocks lawful work fails as hard as one
# that passes unlawful work, so the gate's event is named and its wording is not.






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
    """No index is clean because the defect this guard closes is a missing row.

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
    falsify it â€” the one lawful way to cite a file an entry quotes."""
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
    single pin exempted a whole paragraph â€” and one line in the real log
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
    """A baseline row is a dead reference nobody had to repair â€” the failure
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


def test_issue_665_retirements_are_derived_from_frozen_entries_and_not_the_index():
    """The retirement record is exactly the parser's frozen population."""
    root = Path(__file__).resolve().parents[2]
    directory = root / "docs" / "architecture" / "decisions"
    retired = set(lint._ISSUE_665_RETIRED_MECHANISMS)

    def references(path):
        found = set()
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            for ref, _form, pinned in lint._entry_refs(line):
                if (ref in retired and not pinned
                        and not lint._entry_ref_resolves(root, path.parent, ref)):
                    found.add((path.name, lineno, ref))
        return found

    frozen = set().union(*(references(path) for path in directory.glob("D-*.md")))
    index = references(directory / "README.md")

    assert frozen == lint._ISSUE_665_RETIRED_REFS
    assert len(frozen) == 97
    assert index == set()
    recorded = {
        key: reason for key, reason in lint.UNREPAIRABLE_AFTER_LANDING.items()
        if key in frozen
    }
    assert set(recorded) == frozen
    for key, reason in recorded.items():
        mechanism = lint._ISSUE_665_RETIRED_MECHANISMS[key[2]]
        assert reason == f"target retired by issue #665 with {mechanism}"


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
    text is the reference â€” for `[display](target)` it is not, and the window
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








def test_cell_frontmatter_fires_above_the_description_ceiling(tmp_path):
    make_clean_tree(tmp_path)
    _set_description(tmp_path, "x" * 701)
    findings = [f for f in lint.run(tmp_path) if "cell-frontmatter" in f]
    assert len(findings) == 1 and "maximum is 700" in findings[0]


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
    checks' findings. A cell it cannot read is reported, never raised.
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
    printed it as `:None` â€” a position that does not exist, in a module whose
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
    """The repository-wide lawful polarity for the prose guard."""
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
    """A cell whose description holds the defect."""
    cell = root / "skills" / "alpha"
    cell.mkdir(parents=True)
    (cell / "SKILL.md").write_bytes(
        ("---" + NL + "name: alpha" + NL
         + "description: Ends at the bare " + TICK + char + TICK + " here." + NL
         + "---" + NL + NL + "# alpha" + NL + "Body." + NL).encode("utf-8")
    )
    return cell


def test_a_cells_defect_is_reported_once(tmp_path):
    """One defective cell produces one finding at the editable source."""
    _cell_with_hollow_span(tmp_path)
    findings = lint.check_hollow_code_span(tmp_path)
    assert len(findings) == 1
    assert findings[0].startswith("hollow-code-span: skills/alpha/SKILL.md")


def test_a_hand_written_project_skill_is_still_read(tmp_path):
    """Repository-wide prose checks include runtime-managed project skills."""
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

    A hollow code span in a review row is intended content â€” a finding must
    quote the line it names â€” so the prose guard skips it. A lone carriage
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

    Spelled `HEAD:<path>` this loses the whole index-only population â€” a file
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


def test_hollow_code_span_caps_an_opening_fence_at_three_spaces(tmp_path):
    """Post-fix 7: the divergence the docstring says must be carried into the
    unification was pinned by nothing, so it could be dropped in silence.

    Four spaces makes an indented code block, not a fence â€” so the marker is
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

    The two lawful byte-wise cases are live frontmatter readers. The `text[0]`
    case came from an external reviewer, whose point was that
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










# --- what the automated reviewers found on PR #291, pinned ------------------













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




# --- the cell-body report: every cell sized at the mandated checkpoint (#302) -




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


















def test_the_lint_prints_the_pointer_reach_at_the_mandated_command(capsys):
    """The figure reaches the session with its reconstructable basis."""
    lint.main()
    out = capsys.readouterr().out
    assert "pointer reach here, largest first" in out, out
    block = out.split("pointer reach here, largest first", 1)[1]
    printed = {name for name, _reach, _via in _rows(block)}
    assert printed == set(lint.cell_sources(lint.ROOT)), printed
    for clause in ("below its frontmatter", "counted once",
                   "its own cell's prose plus every cell it reaches",
                   "no cell reaches the charter"):
        assert clause in block, block
    # Every row states where its reach went, so no row is a bare number.
    for _name, _reach, via in _rows(block):
        assert (via.startswith("reaches ")
                or via == "points at nothing; its own prose only"), via
































# --- what the review cost, and where each high landed ------------------------





























# --- whose record the boundaries belong to -----------------------------------

















# --- what the review's own fix batch pinned -----------------------------------







































def test_an_orphan_depth_file_is_a_finding(tmp_path):
    """The half nothing else in the tree can see.

    A `references/` file no body names loads for nobody, costs nothing anyone
    measures, and is found only by enumerating the directory -- which is what
    no reader does. `check_cell_references` cannot see it: that guard resolves
    pointers that exist, and an orphan is the absence of one.
    """
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "The body names its depth." + NL)
    (skill / "references" / "unnamed.md").write_text("Depth." + NL, encoding="utf-8")

    findings = [f for f in lint.check_depth_index(tmp_path) if "depth-index" in f]
    assert len(findings) == 1, findings
    assert "unnamed.md" in findings[0] and "named nowhere" in findings[0]

    # Lawful arm: naming it clears the finding, and nothing else appears.
    body = (skill / "SKILL.md").read_text(encoding="utf-8")
    (skill / "SKILL.md").write_text(
        body + NL + "Depth lives in references/unnamed.md." + NL, encoding="utf-8")
    assert lint.check_depth_index(tmp_path) == []


def test_a_body_naming_a_depth_file_that_is_not_there_is_a_finding(tmp_path):
    """The other direction, pinned separately because it fails differently.

    A dangling entry reads correctly and leads nowhere. `check_cell_references`
    catches the relative form; this catches the repo-root form it skips as
    somebody else's tree, which is why the two are not redundant.
    """
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "example-skill"
    _write_cell(skill, "See skills/example-skill/references/gone.md." + NL)

    findings = [f for f in lint.check_depth_index(tmp_path) if "depth-index" in f]
    assert len(findings) == 1, findings
    assert "gone.md" in findings[0] and "does not exist" in findings[0]

    (skill / "references" / "gone.md").write_text("Depth." + NL, encoding="utf-8")
    assert lint.check_depth_index(tmp_path) == []


def test_a_cell_with_no_depth_directory_is_not_reached(tmp_path):
    """A cell that has shed nothing yet is not an orphan and not a defect."""
    make_clean_tree(tmp_path)
    skill = tmp_path / "skills" / "no-depth"
    skill.mkdir(parents=True, exist_ok=True)
    _write_cell(skill, "A cell with no references/ directory." + NL)
    assert lint.check_depth_index(tmp_path) == []


def test_this_repository_passes_the_depth_index_guard():
    """The guard over the real tree, which is where it has to hold."""
    assert lint.check_depth_index(lint.ROOT) == []

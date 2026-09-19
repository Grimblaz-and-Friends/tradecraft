"""Pins for the repo-specific figure wrapper."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import lint  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


repo_figures = load("repo_figures", ROOT / "tools" / "figures.py")
engine = repo_figures.engine
NL = chr(10)


def make_decisions_root(tmp_path):
    directory = tmp_path / "docs" / "architecture" / "decisions"
    directory.mkdir(parents=True)
    (directory / "D-1-2026-01-01-fixture.md").write_text(
        "# D-1\n\n"
        "A resolvable reference: `README.md` sits beside this entry.\n\n"
        "A dead reference: `gone/nothing.md` twice on separate lines.\n\n"
        "Here is `gone/nothing.md` again.\n\n"
        "A pinned dead reference: `gone/other.md` at `abc1234` is lawful.\n",
        encoding="utf-8",
    )
    (directory / "README.md").write_text(
        "| [D-1](D-1-2026-01-01-fixture.md) | fixture |\n\n"
        "A dead link: [missing](missing-elsewhere.md).\n",
        encoding="utf-8",
    )
    return tmp_path


def test_census_counts_occurrences_and_distinct_pairs(tmp_path):
    figure = repo_figures.figure_census(make_decisions_root(tmp_path))
    assert figure["data"] == {"occurrences": 3, "pairs": 2}
    assert "3 occurrences, 2 distinct" in figure["value"]


def test_census_equals_the_guard_with_recorded_sets_emptied(tmp_path, monkeypatch):
    root = make_decisions_root(tmp_path)
    monkeypatch.setattr(lint, "BASELINE_UNRESOLVABLE", {})
    monkeypatch.setattr(lint, "UNREPAIRABLE_AFTER_LANDING", {})
    guard_dead = [
        finding for finding in lint.check_entry_references(root)
        if "resolves to nothing" in finding
    ]
    assert len(guard_dead) == repo_figures.figure_census(root)["data"]["occurrences"]


def stub_suite(monkeypatch):
    monkeypatch.setattr(
        repo_figures.engine,
        "figure_tests",
        lambda _repo, paths: {
            "name": "suite",
            "value": "999 passed",
            "basis": f"stub over {' '.join(paths)}",
            "data": {"summary": "999 passed", "exit": 0},
        },
    )


def test_default_wrapper_emits_only_suite_and_decision_log(monkeypatch, capsys):
    stub_suite(monkeypatch)
    assert repo_figures.main([]) == 0
    output = capsys.readouterr().out
    assert "999 passed" in output
    assert "decision-log census" in output
    assert "always-on" not in output
    assert "cell body" not in output
    assert "prose delta" not in output


def test_wrapper_delta_requires_and_uses_the_given_base(monkeypatch, capsys):
    stub_suite(monkeypatch)
    assert repo_figures.main(["--base", "HEAD", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    delta = [figure for figure in payload["figures"] if "prose delta" in figure["name"]]
    assert len(delta) == 1
    assert delta[0]["data"]["base"] == "HEAD"
    assert payload["command"] == "python tools/figures.py --base HEAD --json"


def test_the_body_strip_the_engine_ships_is_the_one_the_guard_applies():
    cells = sorted((ROOT / "skills").glob("*/SKILL.md"))
    assert cells
    for cell in cells:
        text = cell.read_text(encoding="utf-8")
        assert engine.frontmatterless(text) == lint._frontmatterless(text), cell.name


def _cell(root, name, body, depth=None):
    cell = root / "skills" / name
    (cell / "references").mkdir(parents=True, exist_ok=True)
    header = (
        "---" + NL + "name: " + name + NL
        + "description: A fixture cell." + NL + "---" + NL + NL
    )
    (cell / "SKILL.md").write_text(header + body, encoding="utf-8", newline=NL)
    for filename, text in (depth or {}).items():
        (cell / "references" / filename).write_text(
            text, encoding="utf-8", newline=NL
        )


def test_reach_is_a_cells_own_prose_when_it_points_nowhere(tmp_path):
    _cell(tmp_path, "alpha", "# alpha\n")
    rows = repo_figures.pointer_reach_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["reach"] == rows[0]["own"]
    assert rows[0]["reached"] == []


def test_reach_follows_pointers_transitively_and_counts_each_cell_once(tmp_path):
    _cell(tmp_path, "alpha", "The `beta` cell and the `gamma` cell.\n")
    _cell(tmp_path, "beta", "The `gamma` cell.\n")
    _cell(tmp_path, "gamma", "No pointer.\n")
    rows = {row["name"]: row for row in repo_figures.pointer_reach_rows(tmp_path)}
    assert rows["alpha"]["reached"] == ["beta", "gamma"]
    assert rows["alpha"]["reach"] == sum(rows[name]["own"] for name in rows)


def test_reach_survives_a_circle_rather_than_hanging(tmp_path):
    _cell(tmp_path, "alpha", "The `beta` cell.\n")
    _cell(tmp_path, "beta", "The `alpha` cell.\n")
    rows = {row["name"]: row for row in repo_figures.pointer_reach_rows(tmp_path)}
    assert rows["alpha"]["reached"] == ["beta"]
    assert rows["beta"]["reached"] == ["alpha"]


def test_figures_consumes_lints_cell_discovery_definition():
    source = (ROOT / "tools" / "figures.py").read_text(encoding="utf-8")
    assert "lint.cell_sources(root)" in source
    assert "import roster" not in source

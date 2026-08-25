"""Pins for tools/figures.py, the repo-specific application of the shipped
figure engine. Each figure's number comes from the guard that judges it, never
from a parallel arithmetic, and each of those couplings is pinned below by
moving the guard's own constant and watching the figure follow: the AGENTS.md
headroom and the charter's budget against check_doctrine, the description
ceiling against check_cell_frontmatter, and the census against
check_entry_references' resolution with both recorded sets emptied — the
derivation D-135 prescribes. The body measurement is the engine's own, pinned
equal to the guard's strip so shipping it did not fork what "body" means. The suite figure is stubbed in CLI tests because the wrapper's
real suite invocation is the suite these tests run inside."""

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

sys.path.insert(0, str(ROOT / "tools"))
import lint  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


repo_figures = load("repo_figures", ROOT / "tools" / "figures.py")
engine = repo_figures.engine


# --- the headroom figure is check_doctrine's measure, not a lookalike -------

def make_doctrine_root(tmp_path, agents_bytes):
    (tmp_path / "AGENTS.md").write_bytes(agents_bytes)
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    return tmp_path


# Fixture sizes derive from the guard's own constant, so a lawful budget
# change moves the fixtures with it and the pins stay a pure equality check.
# Each b"x\r\n" line is 3 bytes and 2 characters under the guard's
# universal-newline read — CRLF is what keeps bytes and characters apart.
BUDGET = lint.AGENTS_BUDGET_CHARS
OVER_LINES = BUDGET // 2 + 4      # 2 * OVER_LINES chars: over budget
UNDER_LINES = BUDGET // 2 - 1     # 2 * UNDER_LINES chars: under in chars...
assert 3 * UNDER_LINES > BUDGET   # ...while over in bytes, for any real budget


def test_over_budget_chars_equal_the_guards_reported_size(tmp_path):
    root = make_doctrine_root(tmp_path, b"x\r\n" * OVER_LINES)
    findings = [f for f in lint.check_doctrine(root) if "doctrine-budget" in f]
    assert len(findings) == 1
    guard_size = int(re.search(r"is (\d+) chars", findings[0]).group(1))
    fig = repo_figures.engine.figure_doc(root, "AGENTS.md", BUDGET)
    assert fig["data"]["chars"] == guard_size == 2 * OVER_LINES
    assert fig["data"]["headroom"] == BUDGET - guard_size


def test_under_budget_in_chars_over_in_bytes_agrees_with_the_guard(tmp_path):
    root = make_doctrine_root(tmp_path, b"x\r\n" * UNDER_LINES)
    assert not [f for f in lint.check_doctrine(root) if "doctrine-budget" in f]
    fig = repo_figures.engine.figure_doc(root, "AGENTS.md", BUDGET)
    assert fig["data"]["headroom"] == BUDGET - 2 * UNDER_LINES > 0


# --- the census is check_entry_references' resolution, sets emptied ---------

def make_decisions_root(tmp_path):
    directory = tmp_path / "docs" / "architecture" / "decisions"
    directory.mkdir(parents=True)
    entry = directory / "D-1-2026-01-01-fixture.md"
    entry.write_text(
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
    fig = repo_figures.figure_census(make_decisions_root(tmp_path))
    # Two occurrences of one dead pair in the entry, one dead pair in the
    # index; the resolvable and the pinned references count for nothing.
    assert fig["data"] == {"occurrences": 3, "pairs": 2}
    assert "3 occurrences, 2 distinct" in fig["value"]


def test_census_equals_the_guard_with_recorded_sets_emptied(tmp_path, monkeypatch):
    root = make_decisions_root(tmp_path)
    monkeypatch.setattr(lint, "BASELINE_UNRESOLVABLE", {})
    monkeypatch.setattr(lint, "UNREPAIRABLE_AFTER_LANDING", {})
    guard_dead = [
        f for f in lint.check_entry_references(root) if "resolves to nothing" in f
    ]
    assert len(guard_dead) == repo_figures.figure_census(root)["data"]["occurrences"]


def test_census_on_this_repository_reproduces(tmp_path):
    # Whatever the number is today, deriving it twice must agree — the figure
    # exists because recalled numbers and derived numbers kept diverging.
    first = repo_figures.figure_census(ROOT)["data"]
    second = repo_figures.figure_census(ROOT)["data"]
    assert first == second
    assert first["occurrences"] >= first["pairs"] >= 0


# --- the wrapper CLI: repo parameters, guard-imported budget ----------------

def stub_suite(monkeypatch):
    monkeypatch.setattr(
        repo_figures.engine, "figure_tests",
        lambda repo, paths: {
            "name": "suite", "value": "999 passed",
            "basis": f"stub over {' '.join(paths)}",
            "data": {"summary": "999 passed", "exit": 0},
        },
    )


def test_wrapper_emits_suite_doc_and_census(tmp_path, monkeypatch, capsys):
    stub_suite(monkeypatch)
    assert repo_figures.main([]) == 0
    out = capsys.readouterr().out
    assert "999 passed" in out
    assert "stub over tools/tests skills" in out
    assert f"of {lint.AGENTS_BUDGET_CHARS:,} chars" in out  # the guard's budget
    assert "decision-log census" in out
    assert "prose delta" not in out  # no base given, no delta invented


def test_wrapper_delta_requires_and_uses_the_given_base(tmp_path, monkeypatch, capsys):
    stub_suite(monkeypatch)
    assert repo_figures.main(["--base", "HEAD", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    delta = [f for f in payload["figures"] if "prose delta" in f["name"]]
    assert len(delta) == 1
    assert delta[0]["data"]["base"] == "HEAD"
    assert delta[0]["data"]["suffixes"] == [".md"]
    assert payload["command"] == "python tools/figures.py --base HEAD --json"


def test_the_body_strip_the_engine_ships_is_the_one_the_guard_applies():
    """Shipping the cell-body measurement must not fork what "body" means.

    The engine cannot import the lint -- repo-only code is not shipped -- so
    the two strips are separate implementations of one rule. That is exactly
    the shape the authoring cell forbids for prose, and the reason the charter
    figure and check_doctrine agree today. Pinned over the real cells rather
    than a fixture, because the drift that matters is on the files the budgets
    actually judge.
    """
    cells = sorted((ROOT / "skills").glob("*/SKILL.md"))
    assert cells, "no cells to compare"
    for cell in cells:
        text = cell.read_text(encoding="utf-8")
        assert engine.frontmatterless(text) == lint._frontmatterless(text), cell.name


def test_the_description_ceiling_comes_from_the_guard(tmp_path, monkeypatch):
    """The figure reads check_cell_frontmatter's constant, not a copy of it."""
    monkeypatch.setitem(lint.CELL_FIELD_MAX_CHARS, "description", 1234)
    cell = ROOT / "skills" / "charter" / "SKILL.md"
    figure = repo_figures.figure_cell_description(ROOT, str(cell.relative_to(ROOT)))
    assert figure["data"]["budget"] == 1234


def test_a_cell_figure_is_never_invented_and_never_defaults_its_budget(tmp_path, monkeypatch):
    """A budget picked silently is how a stated figure leaves the guard behind.

    Mirrors the delta's base, which the engine also refuses to default.
    """
    monkeypatch.setattr(repo_figures.engine, "figure_tests",
                        lambda *a, **k: {"name": "suite", "value": "stub",
                                         "basis": "stub", "data": {}})
    names = [f["name"] for f in repo_figures.build_figures(ROOT, None)]
    assert not any("(body)" in n and "charter" not in n for n in names)
    assert not any("(description)" in n for n in names)
    try:
        repo_figures.build_figures(ROOT, None, "skills/charter/SKILL.md", None)
    except SystemExit as exit_:
        assert "caller decision" in str(exit_)
    else:
        raise AssertionError("--cell without a budget must refuse, not default")


def test_the_charter_budget_comes_from_the_guard(monkeypatch):
    """The one coupling the batch that rewrote this docstring left unpinned.

    It is the figure with the highest certification load -- emitted into every
    write-up, and the only one asserting a budget a guard actually enforces --
    so a literal here would be the exact drift D-141 exists to prevent, and it
    survived mutation with the whole suite green.
    """
    monkeypatch.setattr(lint, "CHARTER_BUDGET_CHARS", 4321)
    assert repo_figures.figure_charter(ROOT)["data"]["budget"] == 4321

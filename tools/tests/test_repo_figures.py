"""Pins for tools/figures.py, the repo-specific application of the shipped
figure engine. The two couplings the artifact promises are held here: the
headroom figure agrees with check_doctrine's own measure (never a parallel
arithmetic that can drift), and the census agrees with check_entry_references'
resolution when both recorded sets are emptied — the derivation D-135
prescribes. The suite figure is stubbed in CLI tests because the wrapper's
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

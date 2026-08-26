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
NL = chr(10)


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


# --- the always-on figure, the one number the merge comment carries -----------

def test_the_always_on_figure_is_emitted_at_all(tmp_path, monkeypatch):
    """Deleting the call from build_figures left the suite green.

    The cheapest way for this figure to stop being true is for it to stop
    being produced, and nothing noticed. Pinned first because the other
    assertions here all presuppose it.
    """
    monkeypatch.setattr(repo_figures.engine, "figure_tests",
                        lambda *a, **k: {"name": "suite", "value": "stub",
                                         "basis": "stub", "data": {}})
    names = [f["name"] for f in repo_figures.build_figures(ROOT, None)]
    assert "always-on surface" in names


def test_the_two_audiences_are_not_the_same_set():
    """The error the figure exists to stop, pinned.

    `adopter = charter + doctrine` renders a visibly wrong number and passed
    every test in the suite. An adopter's total omits both doctrine files,
    which reach a plugin cache inert; the repo's total counts them.
    """
    data = repo_figures.figure_always_on(ROOT)["data"]
    assert data["adopter_total"] == data["charter"] + data["roster"]
    assert data["repo_total"] == data["doctrine"] + data["adopter_total"]
    assert data["doctrine"] > 0, "the doctrine files are part of the repo total"
    assert data["adopter_total"] < data["repo_total"]


def test_the_repo_total_counts_both_doctrine_files(tmp_path):
    """CLAUDE.md is always-on here and has its own budget because it is.

    Omitting it meant a rule could move from AGENTS.md into it and the total
    would report a reduction while nothing left the surface -- the failure
    routing.md's closing paragraph names, reachable in 489 characters.
    """
    (tmp_path / "AGENTS.md").write_text("a" * 100, encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("b" * 40, encoding="utf-8")
    (tmp_path / "skills").mkdir()
    assert repo_figures.figure_always_on(tmp_path)["data"]["doctrine"] == 140


def test_the_roster_counts_names_as_well_as_descriptions(tmp_path):
    """Descriptions alone read 89 low across eight cells.

    D-169 named this successor error in advance; the callout committed it and
    an external reviewer found it independently. The figure counts both, and
    what it counts is what its label says.
    """
    cell = tmp_path / "skills" / "example"
    cell.mkdir(parents=True)
    (cell / "SKILL.md").write_text(
        "---" + NL + "name: example" + NL + "description: Four." + NL + "---" + NL
        + NL + "Body." + NL, encoding="utf-8")
    assert repo_figures.figure_always_on(tmp_path)["data"]["roster"] == len("example") + len("Four.")


def test_the_charter_is_counted_below_its_frontmatter():
    """The body, not the file -- the same unit the SessionStart hook emits.

    Counting the whole file would double-count the description, which the
    roster already carries, and would price the charter against a unit no
    session receives.
    """
    charter = (ROOT / lint.CHARTER).read_text(encoding="utf-8")
    assert repo_figures.figure_always_on(ROOT)["data"]["charter"] == len(
        lint._frontmatterless(charter))
    assert len(lint._frontmatterless(charter)) < len(charter)


# --- the delta's base side, which shipped guarded by nothing ----------------
#
# `always_on_at` and the delta were added to close "the figure this change
# turns on is guarded by nothing", and arrived with no test of their own. Four
# mutations left the whole suite green: the base side no longer counting
# CLAUDE.md, every delta's sign inverted, `--base` losing its effect entirely,
# and the cell filter widening. The sign one is the reason these exist -- it
# would tell the owner a growing surface shrank, which is the exact reading the
# delta was added to make impossible.

def git_tree(tmp_path):
    """A real repository: always_on_at reads blobs through git, not the disk.

    Isolated from the caller's git configuration, because a repository this
    small inherits whatever the machine has -- `commit.gpgsign` being the one
    that turns a fixture into a hang.
    """
    import subprocess

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            check=True, capture_output=True, text=True,
            env={"GIT_CONFIG_GLOBAL": str(tmp_path / "nonexistent"),
                 "GIT_CONFIG_SYSTEM": str(tmp_path / "nonexistent"),
                 "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                 "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
                 "PATH": __import__("os").environ.get("PATH", "")},
        ).stdout.strip()

    git("init", "-q", "-b", "main")
    return git


def surface(root, agents="a" * 100, pointer="b" * 40, charter_body="Body."):
    (root / "AGENTS.md").write_text(agents, encoding="utf-8")
    (root / "CLAUDE.md").write_text(pointer, encoding="utf-8")
    cell = root / "skills" / "charter"
    cell.mkdir(parents=True, exist_ok=True)
    (cell / "SKILL.md").write_text(
        "---" + NL + "name: charter" + NL + "description: Desc." + NL + "---" + NL
        + NL + charter_body + NL, encoding="utf-8")


def test_the_base_side_reproduces_the_working_tree_figure(tmp_path):
    """One tree, two readers, one number.

    always_on_at re-derived figure_always_on's composition by hand, so the two
    could disagree with nothing comparing them -- and a mutation stopping the
    base side counting CLAUDE.md left 336 tests green. This is the equality
    that mutation breaks.
    """
    git = git_tree(tmp_path)
    surface(tmp_path)
    git("add", "-A")
    git("commit", "-qm", "base")
    head = git("rev-parse", "HEAD")
    assert repo_figures.always_on_at(tmp_path, head) == (
        repo_figures.figure_always_on(tmp_path)["data"]["repo_total"])


def test_the_base_side_counts_both_doctrine_files(tmp_path):
    """The half of the equality above that a single fixture could satisfy by
    accident: measured against a tree whose two doctrine files have different
    sizes, so dropping either one is visible in the number."""
    git = git_tree(tmp_path)
    surface(tmp_path)
    git("add", "-A")
    git("commit", "-qm", "base")
    head = git("rev-parse", "HEAD")
    charter = (tmp_path / "skills" / "charter" / "SKILL.md").read_text(encoding="utf-8")
    expected = (100 + 40 + len("charter") + len("Desc.")
                + len(lint._frontmatterless(charter)))
    assert repo_figures.always_on_at(tmp_path, head) == expected


def test_growth_and_shrink_carry_their_own_sign(tmp_path):
    """A delta whose sign can invert with the suite green is worse than no
    delta: it reports the one direction the ceiling exists to resist as its
    opposite. Both directions, against one base."""
    git = git_tree(tmp_path)
    surface(tmp_path)
    git("add", "-A")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    before = repo_figures.always_on_at(tmp_path, base)

    (tmp_path / "AGENTS.md").write_text("a" * 150, encoding="utf-8")
    grown = repo_figures.figure_always_on(tmp_path)["data"]["repo_total"]
    assert grown - before == 50

    (tmp_path / "AGENTS.md").write_text("a" * 70, encoding="utf-8")
    shrunk = repo_figures.figure_always_on(tmp_path)["data"]["repo_total"]
    assert shrunk - before == -30


def test_the_rendered_delta_says_which_way_the_surface_moved(tmp_path):
    """Sign, not just shape.

    The first pin written for this matched `[-+]` and so stayed green when
    every delta's sign was inverted -- a mutation that tells the owner a
    growing surface shrank, which is the one reading the delta exists to make
    impossible. Both directions, rendered through the callout's own function.
    """
    import doctrine_callout as dc

    git = git_tree(tmp_path)
    surface(tmp_path)
    git("add", "-A")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")

    (tmp_path / "AGENTS.md").write_text("a" * 150, encoding="utf-8")
    assert dc._always_on_delta(repo_figures, tmp_path, base) == " (+50 this PR)"

    (tmp_path / "AGENTS.md").write_text("a" * 70, encoding="utf-8")
    assert dc._always_on_delta(repo_figures, tmp_path, base) == " (-30 this PR)"


def test_a_nested_skill_file_is_not_a_cell(tmp_path):
    """The set both readers count, pinned where they used to differ.

    The working tree globbed one level and the base side matched
    `endswith("/SKILL.md")` over a recursive listing. Nothing in this tree is
    nested, so the two agreed and a mutation widening either left the suite
    green. A cell is `skills/<name>/SKILL.md`; a SKILL.md quoted or drafted
    under a cell's own subdirectory is not a ninth always-on description.
    """
    git = git_tree(tmp_path)
    surface(tmp_path)
    nested = tmp_path / "skills" / "charter" / "references"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text(
        "---" + NL + "name: quoted" + NL + "description: Not a cell." + NL
        + "---" + NL + NL + "An example, not a roster entry." + NL,
        encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "base")
    head = git("rev-parse", "HEAD")

    data = repo_figures.figure_always_on(tmp_path)["data"]
    assert data["cells"] == 1
    assert data["roster"] == len("charter") + len("Desc.")
    assert repo_figures.always_on_at(tmp_path, head) == data["repo_total"]


# Every figure `build_figures` emits unconditionally, in call order. Literal
# for the same reason the lint's check list is: derived from the source, the
# test would agree with itself. The lint's equivalent caught a docstring
# claiming eight checks while run() called ten; this file's docstring is the
# contract for what a write-up gets by default and nothing held it to that.
FIGURES_ALWAYS_EMITTED = (
    "figure_tests", "figure_doc", "figure_charter",
    "figure_always_on", "figure_census",
)
FIGURES_ON_DEMAND = ("figure_delta", "figure_cell", "figure_cell_total",
                     "figure_cell_description")


def test_the_module_docstring_enumerates_every_figure_always_emitted():
    """Count and order only -- pinning the prose would go red on every
    rewording and be deleted within a release. It does not catch a wrong
    description inside an item; that is a separate class."""
    import inspect

    called = re.findall(r"\bfigure_[a-z_]+",
                        inspect.getsource(repo_figures.build_figures))
    assert tuple(called) == FIGURES_ALWAYS_EMITTED + FIGURES_ON_DEMAND, (
        "build_figures emits figures this list does not name, or in another order"
    )
    numbered = re.findall(r"^\s*\d+\.\s+(figure_[a-z_]+)",
                          repo_figures.__doc__, re.M)
    assert tuple(numbered) == FIGURES_ALWAYS_EMITTED, (
        "the docstring's numbered figures do not match what build_figures emits"
    )
    for name in FIGURES_ON_DEMAND:
        assert name in repo_figures.__doc__, name


def test_the_always_emitted_figures_are_what_a_default_run_produces(tmp_path,
                                                                    monkeypatch):
    """The list above names call sites; this one measures the output, so a
    figure that is called and then dropped is still caught."""
    monkeypatch.setattr(repo_figures.engine, "figure_tests",
                        lambda root, paths: {"name": "suite", "value": "stub",
                                             "basis": "stub", "data": {}})
    make_doctrine_root(tmp_path, b"x" * 10)
    surface(tmp_path)
    (tmp_path / "docs" / "architecture" / "decisions").mkdir(parents=True)
    figures = repo_figures.build_figures(tmp_path, None)
    assert len(figures) == len(FIGURES_ALWAYS_EMITTED)
    assert [f["name"] for f in figures] == [
        "suite", "doc `AGENTS.md`", "doc `skills/charter/SKILL.md` (body)",
        "always-on surface", "decision-log census",
    ]


# --- the callout prices each surface against the ceiling that governs it ----
#
# Cycle two found the doctrine's two-file sum rendered against AGENTS.md's
# budget alone, asserting a ceiling that does not exist -- AGENTS.md is capped
# at 6,000 and CLAUDE.md at 500, so no reading of `doctrine 5,758 of 6,000`
# was right. The remedy landed with no pin of any kind, and substituting one
# size for another rebuilt it with the whole suite green, rendering
# `AGENTS.md 5,758 of 6,000` -- worse than the original, because the callout
# no longer shows a doctrine figure, so the 11-character cross-check that
# caught the class once is not available on the surface the owner reads.
#
# Literal on purpose, like the lint's check list: derived from `dc.PRICED`,
# the test would agree with itself.
PRICED_PAIRS = (
    ("AGENTS.md", "AGENTS_BUDGET_CHARS", "agents"),
    ("CLAUDE.md", "POINTER_BUDGET_CHARS", "pointer"),
    ("charter body", "CHARTER_BUDGET_CHARS", "charter"),
)


def test_each_priced_pair_names_the_ceiling_that_governs_it():
    """The binding, not the rendering: which size is priced against which
    constant. Substituting a size, swapping two ceilings, or dropping a row
    each change this set.

    Compared as a set and not as a sequence, deliberately. Each row carries
    its own label, so the order rows are rendered in changes nothing a reader
    can be wrong about -- and a pin that reddened on a reorder would block a
    lawful edit, which fails as hard as passing an unlawful one. The length is
    asserted separately so a duplicated row cannot hide inside the set.
    """
    import doctrine_callout as dc

    assert set(dc.PRICED) == set(PRICED_PAIRS)
    assert len(dc.PRICED) == len(PRICED_PAIRS)
    assert len({label for label, _, _ in dc.PRICED}) == len(dc.PRICED)


def test_every_priced_pair_reaches_the_rendered_callout():
    """And the rendering follows the binding, so a row that is declared and
    then not rendered -- or rendered against a different number than it
    declares -- is caught too.

    Values come from the modules rather than from literals: asserting
    `AGENTS.md 5,747 of 6,000` would go red on every lawful edit to the
    doctrine, which is a guard blocking lawful work on the very surface this
    change exists to make editable.
    """
    import doctrine_callout as dc

    data = repo_figures.figure_always_on(ROOT)["data"]
    body = dc._body(["AGENTS.md"])
    for label, const, key in PRICED_PAIRS:
        expected = f"{label} {data[key]:,} of {getattr(lint, const):,}"
        assert expected in body, (expected, body)


def test_the_ceilings_are_read_from_the_guards_constants(monkeypatch):
    """The other polarity, and the one that keeps these pins honest.

    The sizes move whenever the doctrine is edited, so a pin asserting
    `AGENTS.md 5,747 of 6,000` would go red on every lawful edit -- a guard
    blocking lawful work on the very surface this change exists to make
    editable. Moving the guard's own constant and watching the rendered
    ceiling follow proves the render reads the guard rather than a literal,
    without pinning either number.
    """
    import doctrine_callout as dc

    monkeypatch.setattr(lint, "AGENTS_BUDGET_CHARS", 4_242)
    data = repo_figures.figure_always_on(ROOT)["data"]
    body = dc._body(["AGENTS.md"])
    assert f"AGENTS.md {data['agents']:,} of 4,242" in body
    # and only that one moved
    assert f"CLAUDE.md {data['pointer']:,} of {lint.POINTER_BUDGET_CHARS:,}" in body

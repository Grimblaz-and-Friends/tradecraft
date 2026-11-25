"""The repair fixture builds each arm, prints the entrance's own composed turn, and tells a session's run apart."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "repair_fixture.py"
sys.path.insert(0, str(LIB))

import work  # noqa: E402

REPAIRS = ("a", "b", "d")


def run(*words, cwd=None):
    return subprocess.run([sys.executable, "-B", str(FIXTURE), *map(str, words)], capture_output=True,
                          stdin=subprocess.DEVNULL, timeout=120, cwd=cwd)


def git(product, *words):
    return subprocess.run(["git", *words], cwd=product, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, check=True).stdout.strip()


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    folders = {}
    for arm in ("a", "b", "c", "d", "holder"):
        folder = tmp_path_factory.mktemp("arms") / arm
        result = run("make", arm, folder)
        assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
        folders[arm] = folder
    return folders


def check(folder, name):
    product = folder / "product"
    result = subprocess.run([sys.executable, "-B", f"checks/{name}.py"], cwd=product, capture_output=True,
                            stdin=subprocess.DEVNULL)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")


def verify(folder, arm, text, tmp_path):
    returned = tmp_path / f"return-{arm}.md"
    returned.write_text(text, encoding="utf-8")
    result = run("verify", arm, folder, returned)
    return result.returncode, result.stdout.decode("utf-8")


@pytest.fixture
def fresh(made, tmp_path):
    """Each test starts from the arm as made: an empty ran.log."""
    for folder in made.values():
        (folder / "ran.log").write_text("", encoding="utf-8")
    return made


def test_make_leaves_an_empty_log_a_clean_tree_and_each_arms_history(made):
    for arm, folder in made.items():
        product = folder / "product"
        assert (folder / "ran.log").read_text(encoding="utf-8") == ""
        assert git(product, "status", "--porcelain") == ""
        assert (folder / "plan.md").is_file()
    counts = {arm: len(git(made[arm] / "product", "log", "--format=%H").split()) for arm in made}
    assert counts == {"a": 3, "b": 4, "c": 2, "d": 3, "holder": 4}
    assert not (made["c"] / "earlier-return.md").exists()
    # The fix in each repair arm touches only C1's module; the commit before it in b touches only C2's.
    for arm in REPAIRS:
        assert git(made[arm] / "product", "diff", "--name-only", "HEAD~1", "HEAD") == "ledger/totals.py"
    assert git(made["b"] / "product", "diff", "--name-only", "HEAD~2", "HEAD~1") == "ledger/export.py"
    assert git(made["holder"] / "product", "diff", "--name-only", "HEAD~2", "HEAD~1") == "ledger/export.py"


def test_holder_returns_carry_the_second_check_on_a_reason_the_history_contradicts(made):
    product = made["holder"] / "product"
    earlier, head = git(product, "rev-parse", "HEAD~2"), git(product, "rev-parse", "HEAD")
    repair = (made["holder"] / "repair-return.md").read_text(encoding="utf-8")
    assert f"tested revision {head}" in repair
    assert repair.count(f"Last ran at {earlier}") == 2
    assert f"tested revision {earlier}" in (made["holder"] / "first-return.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("arm", ["a", "b", "c", "d"])
def test_prompt_prints_the_entrances_own_composed_turn(made, arm):
    result = run("prompt", arm, made[arm])
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    text = result.stdout.decode("utf-8")
    assert work._check_account(False) in text
    assert '"continuity": "' + ("fresh" if arm == "c" else "resume") + '"' in text
    assert "--- settled artifact begin ---" in text and "check_export.py" in text
    assert ("result=amended" in text) is (arm == "d")
    # The fixture hands over the entrance's text and retypes none of it.
    assert "builder-executable" not in FIXTURE.read_text(encoding="utf-8")


def test_holder_arm_has_no_turn_and_no_verify(made, tmp_path):
    assert run("prompt", "holder", made["holder"]).returncode != 0
    assert verify(made["holder"], "holder", "C1 C2 C3", tmp_path)[0] != 0


def account(folder, *, earlier=None):
    product = folder / "product"
    head = git(product, "rev-parse", "HEAD")
    text = f"C1: ran at {head}, PASS.\n"
    if earlier:
        return text + f"C2: last ran at {git(product, 'rev-parse', earlier)}, PASS; nothing since touches export.\n"
    return text + f"C2: ran at {head}, PASS.\n"


def test_verify_passes_a_run_that_matches_each_arm(fresh, tmp_path):
    check(fresh["a"], "check_totals")
    assert verify(fresh["a"], "a", account(fresh["a"], earlier="HEAD~1"), tmp_path) == (0, "as expected\n")
    for arm in ("b", "c", "d"):
        check(fresh[arm], "check_totals")
        check(fresh[arm], "check_export")
        assert verify(fresh[arm], arm, account(fresh[arm]), tmp_path) == (0, "as expected\n")


def test_verify_reports_the_opposite_behaviour(fresh, tmp_path):
    a = fresh["a"]
    check(a, "check_totals")
    check(a, "check_export")
    code, out = verify(a, "a", account(a, earlier="HEAD~1"), tmp_path)
    assert code == 1 and "C2's check ran" in out
    for arm in ("b", "c", "d"):
        check(fresh[arm], "check_totals")
        code, out = verify(fresh[arm], arm, account(fresh[arm]), tmp_path)
        assert code == 1 and "C2's check did not run at the head" in out


def test_verify_reports_a_return_missing_a_revision_or_an_id(fresh, tmp_path):
    a = fresh["a"]
    check(a, "check_totals")
    head = git(a / "product", "rev-parse", "HEAD")
    code, out = verify(a, "a", f"C1: ran at {head}, PASS.\nC2: carried; nothing since touches export.\n", tmp_path)
    assert code == 1 and "revision C2 last ran at" in out
    code, out = verify(a, "a", account(a, earlier="HEAD~1").replace(head, "the head"), tmp_path)
    assert code == 1 and "the head's revision" in out
    for arm in ("b", "c", "d"):
        check(fresh[arm], "check_totals")
        check(fresh[arm], "check_export")
        code, out = verify(fresh[arm], arm, account(fresh[arm]).replace("C2:", "The export:"), tmp_path)
        assert code == 1 and "does not name C2" in out

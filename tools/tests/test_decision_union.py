"""The repository's union application, including its first-merge transition."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "lib" / "tests"))
sys.path.insert(0, str(REPOSITORY / "lib"))
import work
from test_catch_up import RULES, graph, registered, git, commit
from test_merge_obligation import launch, outside_paths, follow_merge_input

INDEX = "docs/architecture/decisions/README.md"
HEADER = "| Entry | Decision |\n| --- | --- |\n| old | original |\n"
OWN = "| D-400 | own append |\n"
BASE = "| D-399 | base append |\n"


def seed(registered, *, attribute=True):
    holder, implementation, branch, remote, transport, fixture = registered
    git(holder, "config", "core.autocrlf", "false")
    commit(holder, INDEX, HEADER)
    content = (REPOSITORY / ".gitattributes").read_bytes() if attribute else b"* text=auto eol=lf\n"
    commit(holder, ".gitattributes", content.decode("utf-8"))
    git(implementation, "merge", "--no-ff", "-m", "seed fixture application", "main")
    git(holder, "push", "origin", "main")
    git(implementation, "push")


def appends(registered, *, versions=False):
    holder, implementation, branch, remote, transport, fixture = registered
    commit(implementation, INDEX, HEADER + OWN)
    commit(holder, INDEX, HEADER + BASE)
    if versions:
        commit(implementation, "version.json", '{"version":"1.3.0","name":"fixture"}\n')
        commit(holder, "version.json", '{"version":"1.4.0","name":"fixture"}\n')
    git(holder, "push", "origin", "main")
    git(implementation, "push")
    return git(holder, "rev-parse", "main")


def dry_merge(root, base):
    return subprocess.run(["git", "-C", str(root), "merge-tree", "--write-tree", "--no-messages", "-z", "HEAD", base],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


@pytest.mark.parametrize("method", ["real", "dry"])
def test_C8_actual_attribute_merges_both_appended_rows(registered, method):
    seed(registered)
    holder, implementation, branch, remote, transport, fixture = registered
    base = appends(registered)
    assert git(implementation, "check-attr", "merge", "--", INDEX).endswith("merge: union")
    if method == "dry":
        result = dry_merge(implementation, base)
        assert result.returncode == 0, result.stderr
        tree = result.stdout.split(b"\0")[0].decode("ascii")
        content = git(implementation, "show", f"{tree}:{INDEX}")
    else:
        git(implementation, "merge", "--no-commit", "--no-ff", base)
        assert work._catch_up_conflicts(implementation) == []
        content = (implementation / INDEX).read_text(encoding="utf-8")
        git(implementation, "merge", "--abort")
    assert OWN.strip() in content and BASE.strip() in content


def test_C8_union_and_version_only_catch_up_lands_without_recipient(registered, monkeypatch, capsys):
    seed(registered)
    holder, implementation, branch, remote, transport, fixture = registered
    base = appends(registered, versions=True)
    start = git(implementation, "rev-parse", "HEAD")
    monkeypatch.setattr(work, "_recipient_run", lambda *_a, **_k: pytest.fail("holder merge launched builder"))
    work._execute_catch_up(transport, fixture, holder, None, "holder-id", RULES)
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "holder-owned" and report["dispatch"] is False
    head = git(implementation, "rev-parse", "HEAD")
    assert git(implementation, "show", "-s", "--format=%P", head).split() == [start, base]
    assert git(holder, "ls-remote", "--heads", str(remote), f"refs/heads/{branch}").split()[0] == head
    assert report["version_adjustment"]["value"] == "1.5.0"
    assert json.loads((implementation / "version.json").read_bytes())["version"] == "1.5.0"
    content = (implementation / INDEX).read_text(encoding="utf-8")
    assert OWN.strip() in content and BASE.strip() in content


def test_C9_pre_attribute_branch_first_builder_then_union_catch_up(launch, capsys):
    registered, fixture, inputs, compose = launch
    seed(registered, attribute=False)
    holder, implementation, branch, remote, transport, catch_state = registered
    commit(holder, ".gitattributes", (REPOSITORY / ".gitattributes").read_text(encoding="utf-8"))
    base = appends(registered, versions=True)
    dry = dry_merge(implementation, base)
    assert dry.returncode == 1
    assert INDEX.encode() in dry.stdout
    git(implementation, "merge", "--no-commit", "--no-ff", base, check=False)
    assert INDEX in work._catch_up_conflicts(implementation)
    git(implementation, "merge", "--abort")
    work._execute_catch_up(transport, catch_state, holder, None, "holder-id", RULES)
    refused = json.loads(capsys.readouterr().out)
    assert refused["conflicts"] == [INDEX]
    record = compose()
    assert outside_paths(record["prompt"]) == [INDEX]
    capsys.readouterr()
    merged_index = (HEADER + OWN + BASE).encode("utf-8")
    first = follow_merge_input(registered, record["prompt"], resolutions={INDEX: merged_index})
    assert git(implementation, "check-attr", "merge", "--", INDEX).endswith("merge: union")
    commit(implementation, INDEX, merged_index.decode() + "| D-402 | later own |\n")
    commit(holder, INDEX, HEADER + BASE + "| D-401 | later base |\n")
    commit(holder, "version.json", '{"version":"1.6.0","name":"fixture"}\n')
    git(implementation, "push")
    git(holder, "push", "origin", "main")
    work._execute_catch_up(transport, catch_state, holder, None, "holder-id", RULES)
    landed = json.loads(capsys.readouterr().out)
    assert landed["status"] == "holder-owned" and landed["dispatch"] is False
    content = (implementation / INDEX).read_text(encoding="utf-8")
    for row in (OWN, BASE, "| D-402 | later own |", "| D-401 | later base |"):
        assert row.strip() in content
    assert git(implementation, "merge-base", "--is-ancestor", first, "HEAD") == ""
    assert json.loads((implementation / "version.json").read_bytes())["version"] == "1.7.0"
    assert git(holder, "ls-remote", "--heads", str(remote), f"refs/heads/{branch}").split()[0] == landed["head"]


@pytest.mark.parametrize("method", ["real", "dry"])
def test_C9_union_retains_both_edits_of_existing_row(registered, method):
    seed(registered)
    holder, implementation, branch, remote, transport, fixture = registered
    commit(implementation, INDEX, HEADER.replace("original", "own existing edit"))
    base = commit(holder, INDEX, HEADER.replace("original", "base existing edit"))
    if method == "dry":
        result = dry_merge(implementation, base)
        assert result.returncode == 0
        tree = result.stdout.split(b"\0")[0].decode("ascii")
        content = git(implementation, "show", f"{tree}:{INDEX}")
    else:
        git(implementation, "merge", "--no-commit", "--no-ff", base)
        content = (implementation / INDEX).read_text(encoding="utf-8")
    assert "| old | own existing edit |" in content
    assert "| old | base existing edit |" in content

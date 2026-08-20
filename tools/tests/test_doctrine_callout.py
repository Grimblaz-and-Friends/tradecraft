"""Pins for the doctrine callout.

The defect this script replaces was a mechanism that did nothing and looked
like it worked, so the tests here are weighted toward the two ways that could
recur: a run that should have called out and didn't, and a failure that exits
0. Every `gh` call is stubbed — the `gh` layer is a thin shell around
`subprocess`, and what is worth pinning is the decision above it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import doctrine_callout as dc  # noqa: E402


class Gh:
    """A stub `gh`: answers by argument prefix, records every call."""

    def __init__(self, files: list[str], comments: list[dict], labels: list[str]):
        self.files, self.comments, self.labels = files, comments, labels
        self.calls: list[tuple[str, ...]] = []
        self.fail_on: str | None = None

    def __call__(self, *args: str) -> str:
        self.calls.append(args)
        if self.fail_on and self.fail_on in " ".join(args):
            raise dc.CalloutError(f"stubbed failure on `gh {' '.join(args)}`")
        if args[:2] == ("pr", "diff"):
            return "".join(f"{f}\n" for f in self.files)
        if args[0] == "api" and args[-1] == "[.labels[].name]":
            return json.dumps(self.labels)
        if args[0] == "api" and args[-1] == ".[] | {id, body}":
            return "".join(json.dumps(c) + "\n" for c in self.comments)
        return ""

    def did(self, *prefix: str) -> bool:
        return any(c[:len(prefix)] == prefix for c in self.calls)

    def posted_body(self) -> str:
        for call in self.calls:
            if call[:2] == ("pr", "comment"):
                return call[call.index("--body") + 1]
        raise AssertionError("no comment was posted")

    def patched_body(self) -> str:
        for call in self.calls:
            if call[0] == "api" and "PATCH" in call:
                return call[-1].removeprefix("body=")
        raise AssertionError("no comment was edited")


@pytest.fixture
def gh(monkeypatch):
    def make(files, comments=(), labels=()):
        stub = Gh(list(files), [dict(c) for c in comments], list(labels))
        monkeypatch.setattr(dc, "_gh", stub)
        return stub
    return make


CALLOUT_COMMENT = {"id": 7, "body": dc.CALLOUT.format(files="`AGENTS.md`")}
WITHDRAWN_COMMENT = {"id": 7, "body": dc.WITHDRAWN}
NOISE = {"id": 1, "body": "unrelated review chatter about AGENTS.md"}


# --- which paths count -------------------------------------------------------

@pytest.mark.parametrize("paths, expected", [
    (["AGENTS.md"], ["AGENTS.md"]),
    (["CLAUDE.md"], ["CLAUDE.md"]),
    (["CLAUDE.md", "AGENTS.md"], ["AGENTS.md", "CLAUDE.md"]),   # DOCTRINE_PATHS order
    (["skills/authoring/SKILL.md", "docs/reviews.jsonl"], []),
    # Basename matching would call out a PR that never touched the doctrine,
    # and a false callout trains the owner to ignore the true one.
    (["docs/AGENTS.md"], []),
    (["tools/lint.py/AGENTS.md"], []),
    ([], []),
])
def test_touched_doctrine(paths, expected):
    assert dc.touched_doctrine(paths) == expected


# --- the positive case -------------------------------------------------------

def test_doctrine_pr_gets_label_and_comment(gh):
    stub = gh(["AGENTS.md", "docs/reviews.jsonl"])
    status, lines = dc.run("79", None)
    assert status == dc.OK
    assert stub.did("pr", "edit", "79", "--add-label")
    assert dc.MARKER in stub.posted_body()
    assert "`AGENTS.md`" in stub.posted_body()
    assert any("touches AGENTS.md" in line for line in lines)


def test_label_is_created_before_it_is_applied(gh):
    """The mechanism must not depend on a label a human can delete."""
    stub = gh(["AGENTS.md"])
    dc.run("79", None)
    create = next(i for i, c in enumerate(stub.calls) if c[:2] == ("label", "create"))
    apply_ = next(i for i, c in enumerate(stub.calls) if c[:2] == ("pr", "edit"))
    assert create < apply_


# --- the negative case -------------------------------------------------------

def test_non_doctrine_pr_gets_neither(gh):
    stub = gh(["skills/authoring/SKILL.md", ".claude-plugin/plugin.json"])
    status, _ = dc.run("61", None)
    assert status == dc.OK
    assert not stub.did("pr", "edit")
    assert not stub.did("pr", "comment")
    assert not stub.did("label", "create")


# --- idempotence -------------------------------------------------------------

def test_rerun_does_not_duplicate_the_comment(gh):
    stub = gh(["AGENTS.md"], comments=[NOISE, CALLOUT_COMMENT], labels=[dc.LABEL])
    status, lines = dc.run("79", None)
    assert status == dc.OK
    assert not stub.did("pr", "comment")
    assert not stub.did("pr", "edit")          # label already applied
    assert any("not duplicated" in line for line in lines)


def test_a_lookalike_comment_is_not_the_callout(gh):
    """Identity is the marker, not the prose — otherwise a human quoting the
    callout in review would suppress the real one."""
    stub = gh(["AGENTS.md"], comments=[NOISE])
    dc.run("79", None)
    assert dc.MARKER in stub.posted_body()


# --- drop-back and reinstatement ---------------------------------------------

def test_dropping_the_doctrine_change_withdraws_the_callout(gh):
    stub = gh(["skills/authoring/SKILL.md"],
              comments=[CALLOUT_COMMENT], labels=[dc.LABEL])
    status, _ = dc.run("79", None)
    assert status == dc.OK
    assert stub.did("pr", "edit", "79", "--remove-label")
    assert dc.WITHDRAWN_MARKER in stub.patched_body()


def test_re_earning_the_change_reinstates_the_callout(gh):
    stub = gh(["AGENTS.md"], comments=[WITHDRAWN_COMMENT])
    status, _ = dc.run("79", None)
    assert status == dc.OK
    assert dc.WITHDRAWN_MARKER not in stub.patched_body()
    assert "changes the doctrine" in stub.patched_body()
    assert not stub.did("pr", "comment")       # edited, not a second comment


def test_no_label_to_remove_is_not_a_removal(gh):
    stub = gh(["skills/authoring/SKILL.md"], labels=[])
    dc.run("61", None)
    assert not stub.did("pr", "edit")


# --- dry run -----------------------------------------------------------------

def test_dry_run_touches_nothing(gh):
    stub = gh(["AGENTS.md"])
    status, lines = dc.run("79", None, dry_run=True)
    assert status == dc.OK
    assert any("touches AGENTS.md" in line for line in lines)
    assert not stub.did("pr", "comment")
    assert not stub.did("pr", "edit")
    assert not stub.did("label", "create")


# --- failure is loud ---------------------------------------------------------

@pytest.mark.parametrize("fail_on", [
    "pr diff",                  # the changed paths could not be established
    "issues/79 --jq",           # the PR's labels could not be read
    "issues/79/comments",       # the thread could not be read
    "label create",             # the label could not be created
    "pr edit",                  # the label could not be applied
    "pr comment",               # the callout could not be posted
])
def test_every_failure_exits_non_zero(gh, fail_on, capsys):
    """A callout that silently no-ops is the bug this script replaces, not a
    milder form of it. Each site is enumerated so the claim cannot drift."""
    stub = gh(["AGENTS.md"])
    stub.fail_on = fail_on
    assert dc.main(["--pr", "79"]) == dc.FAILED
    assert "FAILED" in capsys.readouterr().err


def test_unparseable_comment_payload_is_a_failure(gh, monkeypatch):
    stub = gh(["AGENTS.md"])
    monkeypatch.setattr(dc, "_gh", lambda *a: "not json" if a[0] == "api" else stub(*a))
    assert dc.main(["--pr", "79"]) == dc.FAILED


def test_gh_absent_is_a_failure(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise OSError("gh not found")
    monkeypatch.setattr(dc.subprocess, "run", boom)
    assert dc.main(["--pr", "79"]) == dc.FAILED
    assert "gh not found" in capsys.readouterr().err


# --- main() ------------------------------------------------------------------

def test_main_reports_the_clean_path(gh, capsys):
    gh(["AGENTS.md"])
    assert dc.main(["--pr", "79", "--repo", "o/n"]) == dc.OK
    assert "doctrine-callout:" in capsys.readouterr().out


def test_repo_flag_reaches_every_call(gh):
    stub = gh(["AGENTS.md"])
    dc.run("79", "o/n")
    for call in stub.calls:
        if call[0] in ("pr", "label"):
            assert "--repo" in call and "o/n" in call
        if call[0] == "api":
            assert any("repos/o/n/" in a for a in call)

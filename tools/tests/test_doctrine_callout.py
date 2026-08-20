"""Pins for the doctrine callout.

The defect this script replaces was a mechanism that did nothing and looked like
it worked, so the tests are weighted toward the two ways that could recur: a run
that should have called out and didn't, and a failure that exits 0. Its review
found a third, and it is pinned hardest — a comment written by someone else,
carrying the marker, must neither suppress the callout nor ever be edited.

Most tests stub the `gh` layer, because what is worth pinning is the decision
above it. `test_real_gh_raises_on_a_rejected_call` deliberately does not: every
other test replaces `_gh` wholesale, so without it the non-zero-exit branch —
the loudness guarantee itself — is never executed by anything.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import doctrine_callout as dc  # noqa: E402

BOT = dc.EXPECTED_AUTHOR


def test_expected_author_matches_the_rest_api_not_the_graphql_view():
    """Pinned to the literal, because every other test here reads the constant
    and so follows it wherever it goes.

    The two `gh` surfaces disagree and the misleading one is the friendlier
    command: `gh pr view --json comments` reports `github-actions`, while the
    REST endpoint `_state` actually reads reports `github-actions[bot]`. A
    session cross-checking the constant with `gh pr view` would "correct" it,
    after which the callout classifies its own comment as foreign and posts a
    duplicate on every push — and the PR that lands that change shows no
    symptom, because it touches no doctrine file.
    """
    assert dc.EXPECTED_AUTHOR == "github-actions[bot]"


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
        if args[0] == "api" and args[-1].startswith(".[] |"):
            return "".join(json.dumps(c) + "\n" for c in self.comments)
        return ""

    def did(self, *prefix: str) -> bool:
        return any(c[:len(prefix)] == prefix for c in self.calls)

    def call_with(self, needle: str) -> tuple[str, ...]:
        for call in self.calls:
            if any(needle in a for a in call):
                return call
        raise AssertionError(f"no call contained {needle!r}")

    def posted_body(self) -> str:
        for call in self.calls:
            if call[:2] == ("pr", "comment"):
                return call[call.index("--body") + 1]
        raise AssertionError("no comment was posted")

    def patched(self) -> tuple[str, str]:
        """(comment id, new body) of the single PATCH, or fail."""
        for call in self.calls:
            if call[0] == "api" and "PATCH" in call:
                return call[3].rsplit("/", 1)[-1], call[-1].removeprefix("body=")
        raise AssertionError("no comment was edited")

    def patch_calls(self) -> list[tuple[str, ...]]:
        return [c for c in self.calls if c[0] == "api" and "PATCH" in c]


@pytest.fixture
def gh(monkeypatch):
    def make(files=("AGENTS.md",), comments=(), labels=()):
        stub = Gh(list(files), [dict(c) for c in comments], list(labels))
        monkeypatch.setattr(dc, "_gh", stub)
        return stub
    return make


def _callout(files="`AGENTS.md`", author=BOT, cid=7):
    return {"id": cid, "author": author, "body": dc.CALLOUT.format(files=files)}


WITHDRAWN_COMMENT = {"id": 7, "author": BOT, "body": dc.WITHDRAWN}
NOISE = {"id": 1, "author": "Grimblaz", "body": "unrelated chatter about AGENTS.md"}
# The accidental case, and the reason ownership is checked: a review report on
# this very mechanism quotes the marker.
REPORT = {"id": 4242, "author": "Grimblaz",
          "body": f"## review report\n\nIdempotence is by `{dc.MARKER}`, verified present once.\n"}


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


def test_the_body_names_the_files_the_pr_actually_touched(gh):
    """A CLAUDE.md-only PR must not be sent to read the AGENTS.md diff."""
    stub = gh(["CLAUDE.md"])
    dc.run("79", None)
    body = stub.posted_body()
    assert "Read the `CLAUDE.md` diff" in body
    assert "AGENTS.md" not in body.split("<sub>")[0]


def test_label_is_created_before_it_is_applied(gh):
    """The mechanism must not depend on a label a human can delete."""
    stub = gh(["AGENTS.md"])
    dc.run("79", None)
    create = next(i for i, c in enumerate(stub.calls) if c[:2] == ("label", "create"))
    apply_ = next(i for i, c in enumerate(stub.calls) if c[:2] == ("pr", "edit"))
    assert create < apply_


def test_label_create_forces_and_carries_its_appearance(gh):
    """Without --force, `label create` errors on the second doctrine PR and
    turns a lawful change red — a guard blocking lawful work."""
    stub = gh(["AGENTS.md"])
    dc.run("79", None)
    call = stub.call_with("--force")
    assert call[:3] == ("label", "create", dc.LABEL)
    assert dc.LABEL_COLOR in call and dc.LABEL_DESC in call


# --- the negative case -------------------------------------------------------

def test_non_doctrine_pr_gets_neither(gh):
    stub = gh(["skills/authoring/SKILL.md", ".claude-plugin/plugin.json"])
    status, _ = dc.run("61", None)
    assert status == dc.OK
    assert not stub.did("pr", "edit")
    assert not stub.did("pr", "comment")
    assert not stub.did("label", "create")


def test_no_label_to_remove_is_not_a_removal(gh):
    stub = gh(["skills/authoring/SKILL.md"], labels=[])
    dc.run("61", None)
    assert not stub.did("pr", "edit")


# --- ownership: the review's HIGH -------------------------------------------

def test_a_foreign_comment_carrying_the_marker_does_not_suppress_the_callout(gh):
    """The repo is public, so anyone can comment. Degrade toward speaking:
    a duplicate callout is noise, a missing one is the bug this script fixes."""
    stub = gh(["AGENTS.md"], comments=[REPORT])
    status, lines = dc.run("79", None)
    assert status == dc.OK
    assert dc.MARKER in stub.posted_body()
    assert any("ignoring a marker-bearing comment by Grimblaz" in line for line in lines)


def test_a_foreign_comment_is_never_edited(gh):
    """Editing one would destroy a third party's comment — in practice, the
    review report that quoted the marker."""
    for files, labels in ((["skills/x/SKILL.md"], [dc.LABEL]), (["AGENTS.md"], [])):
        stub = gh(files, comments=[REPORT], labels=labels)
        dc.run("79", None)
        assert stub.patch_calls() == [], f"edited a foreign comment (files={files})"


def test_a_lookalike_comment_is_not_the_callout(gh):
    """Identity is the marker plus the author, not the prose."""
    stub = gh(["AGENTS.md"], comments=[NOISE])
    dc.run("79", None)
    assert dc.MARKER in stub.posted_body()


def test_our_own_callout_is_recognised(gh):
    stub = gh(["AGENTS.md"], comments=[NOISE, _callout()], labels=[dc.LABEL])
    status, lines = dc.run("79", None)
    assert status == dc.OK
    assert not stub.did("pr", "comment")
    assert not stub.did("pr", "edit")          # label already applied
    assert stub.patch_calls() == []            # body already correct
    assert any("already says this" in line for line in lines)


# --- one rule for the comment body ------------------------------------------

def test_dropping_the_doctrine_change_withdraws_the_callout(gh):
    stub = gh(["skills/authoring/SKILL.md"], comments=[_callout()], labels=[dc.LABEL])
    status, _ = dc.run("79", None)
    assert status == dc.OK
    assert stub.did("pr", "edit", "79", "--remove-label")
    assert stub.patched() == ("7", dc.WITHDRAWN)


def test_re_earning_the_change_reinstates_the_callout(gh):
    stub = gh(["AGENTS.md"], comments=[WITHDRAWN_COMMENT])
    status, _ = dc.run("79", None)
    assert status == dc.OK
    _, body = stub.patched()
    assert "Withdrawn" not in body and "changes the doctrine" in body
    assert not stub.did("pr", "comment")       # edited, not a second comment


def test_a_stale_touched_list_is_refreshed(gh):
    """The withdrawn/reinstated transition and the files-changed transition are
    the same operation; repairing only the first was the inconsistency."""
    stub = gh(["AGENTS.md", "CLAUDE.md"], comments=[_callout()], labels=[dc.LABEL])
    dc.run("79", None)
    _, body = stub.patched()
    assert "`AGENTS.md`, `CLAUDE.md`" in body


def test_an_already_withdrawn_callout_is_left_alone(gh):
    stub = gh(["skills/x/SKILL.md"], comments=[WITHDRAWN_COMMENT])
    dc.run("79", None)
    assert stub.patch_calls() == []


# --- reading the thread ------------------------------------------------------

def test_the_comment_read_walks_every_page(gh):
    """Without --paginate the default page size is 30, and on a long thread the
    callout falls off page 1 — the run then posts a second one."""
    stub = gh(["AGENTS.md"])
    dc.run("79", None)
    call = stub.call_with("/comments")
    assert "--paginate" in call
    assert any("per_page=100" in a for a in call)
    assert any("author: .user.login" in a for a in call)


# --- dry run -----------------------------------------------------------------

@pytest.mark.parametrize("files, comments, labels, expect", [
    (["AGENTS.md"], (), (), "posting the callout"),
    (["skills/x/SKILL.md"], [_callout()], [dc.LABEL], "removing the doctrine label"),
    (["skills/x/SKILL.md"], [_callout()], [dc.LABEL], "updating the callout"),
    (["AGENTS.md"], [WITHDRAWN_COMMENT], (), "updating the callout"),
    (["AGENTS.md", "CLAUDE.md"], [_callout()], [dc.LABEL], "updating the callout"),
])
def test_dry_run_reports_every_change_and_makes_none(gh, files, comments, labels, expect):
    stub = gh(files, comments=comments, labels=labels)
    status, lines = dc.run("79", None, dry_run=True)
    assert status == dc.OK
    assert any(expect in line for line in lines)
    for forbidden in (("pr", "comment"), ("pr", "edit"), ("label", "create")):
        assert not stub.did(*forbidden), f"dry run called {forbidden}"
    assert stub.patch_calls() == []


# --- failure is loud ---------------------------------------------------------

@pytest.mark.parametrize("fail_on, files, comments, labels", [
    ("pr diff", ["AGENTS.md"], (), ()),                       # paths unreadable
    ("issues/79 --jq", ["AGENTS.md"], (), ()),                # labels unreadable
    ("issues/79/comments", ["AGENTS.md"], (), ()),            # thread unreadable
    ("label create", ["AGENTS.md"], (), ()),                  # label uncreatable
    ("--add-label", ["AGENTS.md"], (), ()),                   # label unappliable
    ("pr comment", ["AGENTS.md"], (), ()),                    # callout unpostable
    ("--remove-label", ["skills/x/SKILL.md"], [_callout()], [dc.LABEL]),
    ("PATCH", ["skills/x/SKILL.md"], [_callout()], [dc.LABEL]),
])
def test_every_gh_call_site_exits_non_zero_when_rejected(gh, capsys, fail_on,
                                                         files, comments, labels):
    """A callout that silently no-ops is the bug this script replaces, not a
    milder form of it. All eight sites are driven, including the two on the
    edit path — the rarest one, and so the last to be noticed."""
    stub = gh(files, comments=comments, labels=labels)
    stub.fail_on = fail_on
    assert dc.main(["--pr", "79"]) == dc.FAILED
    out, err = capsys.readouterr()
    assert "FAILED" in err
    assert "::error title=doctrine-callout::" in out


def test_an_empty_change_set_is_a_failure_not_a_quiet_pass(gh, capsys):
    """Every PR changes something, so nothing is the one answer that cannot be
    told apart from a failure to read the diff."""
    stub = gh([])
    assert dc.main(["--pr", "79"]) == dc.FAILED
    assert "changes no files at all" in capsys.readouterr().err
    assert not stub.did("pr", "comment")


def test_real_gh_raises_on_a_rejected_call(monkeypatch, capsys):
    """The only test that drives `_gh` itself. Without it the non-zero-exit
    branch — the loudness guarantee — is never executed by anything, and a
    mutation replacing the raise with `return ""` survives the whole suite."""
    class Proc:
        returncode, stdout, stderr = 1, "", "HTTP 403: Resource not accessible"

    monkeypatch.setattr(dc.subprocess, "run", lambda *a, **k: Proc())
    with pytest.raises(dc.CalloutError) as exc:
        dc._gh("pr", "comment", "79", "--body", "x")
    assert "403" in str(exc.value)


def test_a_long_argument_does_not_bury_the_reason(monkeypatch):
    """The comment body is an argument; unelided it pushes the HTTP status onto
    the seventh line of the one message read under failure."""
    class Proc:
        returncode, stdout, stderr = 1, "", "HTTP 403"

    monkeypatch.setattr(dc.subprocess, "run", lambda *a, **k: Proc())
    with pytest.raises(dc.CalloutError) as exc:
        dc._gh("pr", "comment", "79", "--body", dc.CALLOUT.format(files="`AGENTS.md`"))
    message = str(exc.value)
    assert "chars]" in message and message.count("\n") == 0
    assert message.endswith("HTTP 403")


def test_unparseable_comment_payload_is_a_failure(gh, monkeypatch, capsys):
    stub = gh(["AGENTS.md"])

    def only_comments_broken(*args):
        if args[0] == "api" and args[-1].startswith(".[] |"):
            return "not json"
        return stub(*args)

    monkeypatch.setattr(dc, "_gh", only_comments_broken)
    assert dc.main(["--pr", "79"]) == dc.FAILED
    assert "could not parse a PR comment" in capsys.readouterr().err


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


def test_progress_survives_a_failure(gh, capsys):
    """`run()` raising discards what it accumulated, so the lines are printed as
    they happen — otherwise the log is thinnest exactly when it is read."""
    stub = gh(["AGENTS.md"])
    stub.fail_on = "pr comment"
    assert dc.main(["--pr", "79"]) == dc.FAILED
    assert "touches AGENTS.md" in capsys.readouterr().out


def test_pr_must_be_numeric(gh, capsys):
    """The workflow supplies an integer, but nothing enforced it: a PR
    reference from a less trusted caller reaches an API URL path."""
    gh(["AGENTS.md"])
    with pytest.raises(SystemExit):
        dc.main(["--pr", "1/../../evil-owner/evil-repo/issues/1"])


def test_repo_flag_reaches_every_call(gh):
    stub = gh(["AGENTS.md"])
    dc.run("79", "o/n")
    for call in stub.calls:
        if call[0] in ("pr", "label"):
            assert "--repo" in call and "o/n" in call
        if call[0] == "api":
            assert any("repos/o/n/" in a for a in call)

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
import re
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
    return {"id": cid, "author": author, "body": dc._body_from(files)}


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
    # DOCTRINE_PATHS order, not the caller's
        (["CLAUDE.md", "AGENTS.md"], ["AGENTS.md", "CLAUDE.md"]),
        # The charter carries the half of the doctrine that moved out of
        # AGENTS.md and additionally ships, so it is the same read.
        (["skills/charter/SKILL.md"], ["skills/charter/SKILL.md"]),
        # ...and it sorts by DOCTRINE_PATHS order too.
        (["skills/charter/SKILL.md", "AGENTS.md"], ["AGENTS.md", "skills/charter/SKILL.md"]),
        # A path merely ending in the doctrine name is not the doctrine.
        (["docs/charter/CHARTER.md"], []),
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
    """A CLAUDE.md-only PR must not be sent to read the AGENTS.md diff.

    Scoped to the two lines that carry the file list, where it used to search
    the whole body above the footer. The always-on figure now names AGENTS.md
    in every callout because that is the file its ceiling governs, and a
    whole-body search cannot tell a priced figure from an instruction -- it
    would fail this lawful rendering, and a guard that blocks lawful work
    fails as hard as one that passes unlawful work.
    """
    stub = gh(["CLAUDE.md"])
    dc.run("79", None)
    body = stub.posted_body()
    assert "Read the `CLAUDE.md` diff" in body
    instructions = [line for line in body.splitlines()
                    if line.startswith("**This PR changes the doctrine.**")
                    or line.startswith("Touched:")]
    assert len(instructions) == 2, instructions
    assert not any("AGENTS.md" in line for line in instructions), instructions


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
        dc._gh("pr", "comment", "79", "--body", dc._body_from("`AGENTS.md`"))
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


def test_the_callout_line_decomposes_its_own_total(tmp_path, monkeypatch):
    """The printed terms must sum to the total the same sentence states.

    They stopped doing so when the always-on figure split its roster by
    audience: the total was rebuilt from the roster this repository loads,
    under `.claude/skills/`, while this line went on printing the adopter's,
    from `skills/`. The two agree on any in-step tree, so nothing showed --
    and this job carries no `needs:` on `lint-and-test`, so it posts on
    exactly the trees where the roster guard is red and they disagree.

    Measured on a tree where they disagree, which is the only tree that can
    tell the two readers apart. The fix shipped unpinned and reverting it left
    the whole suite green -- the same shape as the mutation that survived in
    `always_on_at`, in the batch that closed it. [PR #210 cycle one, C1-F4]

    The same fixture now also has the two **runtimes** disagreeing, the entry
    being removed from one surface and left on the other, so the sentence is
    rendered in its divergent form here rather than its agreeing one. [#258]
    """
    import shutil

    import roster as _roster

    # The line resolves `tools/figures.py` against ROOT and that file reaches
    # `lint`, `winio` and the shipped engine, so the fixture carries the real
    # machinery rather than a stub: a mock here would pin the test's own
    # arithmetic instead of the renderer's choice of keys.
    repo = Path(__file__).resolve().parents[2]
    shutil.copytree(repo / "tools", tmp_path / "tools",
                    ignore=shutil.ignore_patterns("tests", "__pycache__"))
    shutil.copytree(repo / "lib", tmp_path / "lib",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(repo / "skills" / "authoring" / "scripts",
                    tmp_path / "skills" / "authoring" / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__"))

    (tmp_path / "AGENTS.md").write_bytes(b"a" * 100)
    (tmp_path / "CLAUDE.md").write_bytes(b"@AGENTS.md\n")
    for name, desc in (("charter", "Binding rules."), ("extra", "Trigger.")):
        cell = tmp_path / "skills" / name
        cell.mkdir(parents=True, exist_ok=True)
        (cell / "SKILL.md").write_bytes(
            ("---\nname: " + name + "\ndescription: " + desc
             + "\n---\n\nBody.\n").encode("utf-8"))
    _roster.write(tmp_path)
    # Out of step on purpose: one cell keeps its entry, one does not.
    (tmp_path / ".claude" / "skills" / "extra" / "SKILL.md").unlink()

    monkeypatch.setattr(dc, "ROOT", tmp_path)
    line = dc._always_on_line()

    flat = line.replace(",", "")
    # **One chain per runtime, and each must sum to the total it is printed
    # against.** The old shape was one `+` chain beside one scalar, and it
    # summed to whichever runtime happened to be long while the sentence
    # stated another's total -- so the sentence was right or wrong according
    # to which surface was short, and this test compensated by taking
    # `min(roster_terms)`, encoding exactly the knowledge the sentence
    # withheld from its reader. Nothing is compensated for here: every chain
    # is checked against its own stated total, which is a property no single
    # chain could have had. [PR #278 review, M13]
    chains = re.findall(r"([A-Za-z][A-Za-z ]*?) (\d+) = ([^;*]+)", flat)
    assert len(chains) >= 2, f"one chain per runtime was not rendered: {line}"
    for runtime, stated, chain in chains:
        # The last number of each addend is its value; an addend may also
        # carry a count ("9 name/description from ... 5,039"), and summing
        # every integer in the chain would add the count to the total.
        terms = [int(re.findall(r"(\d+)", part)[-1])
                 for part in chain.split(" + ")]
        assert sum(terms) == int(stated), (
            f"{runtime}'s printed terms sum to {sum(terms)}, not the "
            f"{stated} it states: {line}"
        )

    # The runtimes are named, and the divergent tree renders both rather than
    # collapsing to a claim of sameness.
    runtimes = {runtime.strip() for runtime, _, _ in chains}
    assert "Claude Code" in runtimes and "Codex" in runtimes, runtimes


def test_the_callout_carries_the_always_on_size(tmp_path, monkeypatch):
    """The budget the owner is deciding against, on the surface he decides on.

    Both arms: the figure is there when it derives, and its failure is a
    stated absence rather than a silent omission -- a callout that quietly
    drops a number is one nobody can trust the rest of.
    """
    body = dc._body(["AGENTS.md"])
    assert "Always-on surface here, per runtime:" in body
    assert "for an adopter" in body

    # Patching the module attribute now reaches the function, because root
    # resolves at call time rather than binding as a default -- the earlier
    # shape made this line inert and would have let a later test measure
    # the real repository while appearing to isolate it.
    monkeypatch.setattr(dc, "ROOT", tmp_path)
    degraded = dc._always_on_line()
    assert degraded.startswith("_Always-on surface: not derived")


def test_the_delta_survives_the_path_ci_actually_takes(gh):
    """The seam, not the function.

    Every pin written for the delta called the arithmetic directly, and no
    test in the suite passed a base through `run()` or `main()` at all. So
    `run()` dropping `base=base`, and `main()` dropping `base=args.base`,
    each posted a callout with no delta and left the whole suite green --
    reproducing byte-for-byte the artifact this review ruled an unmet
    acceptance criterion. The workflow's two halves of the same seam are
    pinned in the lint; these are the two inside the script.
    """
    stub = gh(["AGENTS.md"])
    dc.run("79", None, base="HEAD~1")
    assert re.search(r"\((?:[A-Za-z][A-Za-z ]*[-+][\d,]+, )*[A-Za-z][A-Za-z ]*[-+][\d,]+ this PR\)", stub.posted_body())


def test_main_threads_its_base_argument_through(gh):
    """The outermost seam: CI invokes `main`, not `run`."""
    stub = gh(["AGENTS.md"])
    dc.main(["--pr", "79", "--base", "HEAD~1"])
    assert re.search(r"\((?:[A-Za-z][A-Za-z ]*[-+][\d,]+, )*[A-Za-z][A-Za-z ]*[-+][\d,]+ this PR\)", stub.posted_body())


def test_no_base_still_posts_a_callout_without_a_delta(gh):
    """The lawful polarity of both: a PR whose base cannot be resolved is not
    a failure, and must still get its total."""
    stub = gh(["AGENTS.md"])
    dc.run("79", None)
    body = stub.posted_body()
    assert "Always-on surface here, per runtime:" in body and "this PR)" not in body


def test_the_delta_renders_its_sign_and_states_a_base_it_cannot_read():
    """Three renderings that must differ, because two of them did not.

    `--base` had no test of any kind: deleting its whole effect from `run()`
    left the suite green, and so did inverting every delta's sign. Worse, an
    unresolvable base returned "" -- byte-identical to no base at all -- which
    is how the delta shipped absent from every CI callout for a full cycle
    without anyone being able to see it from the comment.
    """
    plain = dc._body(["AGENTS.md"])
    measured = dc._body(["AGENTS.md"], base="HEAD~1")
    unreadable = dc._body(["AGENTS.md"], base="0" * 40)

    assert measured != plain, "--base must change the body"
    assert unreadable != plain, "an unreadable base is not the same as no base"
    # Shape only. The *direction* is pinned in test_repo_figures.py against a
    # tree whose movement is known -- this assertion matched either sign, and
    # stayed green when every delta was inverted.
    assert re.search(r"\((?:[A-Za-z][A-Za-z ]*[-+][\d,]+, )*[A-Za-z][A-Za-z ]*[-+][\d,]+ this PR\)", measured), measured
    assert "movement not derived" in unreadable and "0" * 40 in unreadable

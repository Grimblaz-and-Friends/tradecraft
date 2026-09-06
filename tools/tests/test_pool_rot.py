"""Tests for the evidence-rot check (issue #434, stage two).

Everything here runs offline. What is tested is the part that decides which
filings to name, which is where the whole value of the check sits: a report that
is mostly false positives is a report nobody reads, and the first run over this
repository's own pool was mostly false positives.

The extraction is guard-shaped and is probed in both polarities -- a path that
has really gone is named, and a path that is still there, or is a placeholder,
or sits inside a fence, is not.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "pool_rot.py"

spec = importlib.util.spec_from_file_location("pool_rot", SCRIPT)
rot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rot)

REAL_GH = rot.gh


@pytest.fixture(autouse=True)
def fence_the_wire(monkeypatch):
    """No test here reaches the network, and none opts in."""
    def refuse(*args, **kwargs):
        raise AssertionError(f"this test reached the network: {str(args)[:90]}")

    monkeypatch.setattr(rot, "gh", refuse)
    monkeypatch.setattr(rot.pool_engine(), "gh", refuse)


def tree(tmp_path, *paths):
    for rel in paths:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("the quick brown fox jumps over the lazy dog\n", encoding="utf-8")
    return tmp_path


def body_issue(number, body):
    return {"number": number, "title": "t", "body": body}


# ------------------------------------------------------- what counts as a path


def test_a_path_that_has_gone_is_named(tmp_path):
    root = tree(tmp_path, "tools/lint.py")
    found = rot.rot(root, [body_issue(1, "the guard at `tools/gone.py` is wrong")])
    assert [f["number"] for f in found] == [1]
    assert found[0]["gone"] == ["tools/gone.py"]


def test_a_path_that_is_still_there_is_not(tmp_path):
    """The lawful polarity. A check that named every filing would be a check
    nobody reads."""
    root = tree(tmp_path, "tools/lint.py")
    assert rot.rot(root, [body_issue(1, "the guard at `tools/lint.py` is wrong")]) == []


def test_a_path_inside_a_fenced_block_is_not_named(tmp_path):
    """Fences carry commands, probe transcripts and worked examples, which name
    files that never existed. Measured on this repository's own pool: skipping
    them removed two of eight hits, both invented filenames inside a probe."""
    root = tree(tmp_path, "tools/lint.py")
    body = "see below\n\n```\n$ python tools/never_existed.py\n```\n"
    assert rot.rot(root, [body_issue(1, body)]) == []


def test_a_placeholder_segment_is_not_a_path(tmp_path):
    root = tree(tmp_path, "tools/lint.py")
    for placeholder in (".github/instructions/NAME.instructions.md",
                        "docs/<file>.md",
                        "skills/N/SKILL.md"):
        assert rot.rot(root, [body_issue(1, f"a file at {placeholder}")]) == [], placeholder


def test_a_real_all_caps_filename_is_still_checked(tmp_path):
    """The negative control the placeholder test lacked, and the defect it did
    not catch: the first spelling of `PLACEHOLDER_RE` was `[A-Z]{2,}`, which
    reads `SKILL` out of every `.../SKILL.md` and discarded 152 of the 290 paths
    this repository's filings name. Every one of these is a real filename, and
    every one must be checked rather than skipped."""
    root = tree(tmp_path, "tools/lint.py", "skills/filing/SKILL.md")
    for real in ("docs/cells/board/SKILL.md", "docs/README.md",
                 "skills/engagement/SKILL.md", "docs/architecture/README.md"):
        found = rot.rot(root, [body_issue(1, f"the rule at {real}")])
        assert [f["gone"] for f in found] == [[real]], real
    # And the other polarity on the same shape, so the control discriminates:
    # an all-caps filename that is still there is not reported either.
    assert rot.rot(root, [body_issue(1, "the rule at skills/filing/SKILL.md")]) == []


def test_a_partial_path_out_of_the_middle_of_a_citation_is_not_named(tmp_path):
    """Without the extension requirement the pattern matched
    `docs/architecture/decisions/D` out of `[D-410](docs/architecture/...)`."""
    root = tree(tmp_path, "docs/architecture/decisions/D-410-x.md")
    body = "see D-410 in docs/architecture/decisions/D-410-x.md for the reasoning"
    assert rot.rot(root, [body_issue(1, body)]) == []


def test_a_word_that_merely_contains_a_zone_name_is_not_a_path(tmp_path):
    root = tree(tmp_path, "tools/lint.py")
    body = "the repository at github.com/owner/tools/other.py is not ours"
    found = rot.rot(root, [body_issue(1, body)])
    assert found == [], found


# ------------------------------------------------------- what it will not do


def test_nothing_is_ever_closed(monkeypatch, tmp_path, capsys):
    """The intent was that the path half is exact enough to close on. It is not:
    the surviving hits over this repository's own pool were mostly filings that
    name a path deliberately. So this reports, whatever the policy says."""
    sent = []

    def wire(args):
        if args[:2] == ["issue", "list"]:
            return json.dumps([{"number": 1, "title": "t", "labels": [],
                                "body": "the guard at `tools/gone.py`"}])
        sent.append(args)
        return ""

    monkeypatch.setattr(rot, "gh", wire)
    monkeypatch.setattr(rot.pool_engine(), "find_policy", lambda start=None: rot.pool_engine().DEFAULT_POLICY)
    real = rot.pool_engine().load_policy(rot.pool_engine().DEFAULT_POLICY)
    for closes in (False, True):
        sent.clear()
        real["fade"]["closes"] = closes
        monkeypatch.setattr(rot.pool_engine(), "load_policy", lambda path, p=real: p)
        assert rot.cmd_rot(None) == 0
        assert sent == [], f"closes={closes} wrote: {sent}"
    assert "nothing above was closed" in capsys.readouterr().out


def test_the_write_fence_in_that_probe_catches_a_write(monkeypatch):
    """The negative control: the probe above would report differently if a write
    happened, so its green means no write rather than a broken harness."""
    sent = []
    monkeypatch.setattr(rot, "gh", lambda args: sent.append(args) or "")
    rot.gh(["issue", "close", "1"])
    assert sent


def test_a_framed_issue_is_not_in_the_pool(monkeypatch):
    """The check is over the pool, and the board's own membership is not it."""
    policy = rot.pool_engine().load_policy(rot.pool_engine().DEFAULT_POLICY)
    monkeypatch.setattr(rot, "gh", lambda args: json.dumps([
        {"number": 1, "title": "t", "body": "b", "labels": [{"name": policy["framed"]["label"]}]},
        {"number": 2, "title": "t", "body": "b", "labels": []},
    ]))
    assert [i["number"] for i in rot.pool_bodies(policy, None)] == [2]


def test_a_read_at_its_limit_is_refused(monkeypatch):
    """A filing past a truncated read would go unchecked and the report would
    say nothing about it."""
    policy = rot.pool_engine().load_policy(rot.pool_engine().DEFAULT_POLICY)
    full = json.dumps([{"number": i, "title": "t", "body": "", "labels": []}
                       for i in range(rot.pool_engine().ISSUE_READ_LIMIT)])
    monkeypatch.setattr(rot, "gh", lambda args: full)
    with pytest.raises(rot.RotError):
        rot.pool_bodies(policy, None)

"""Tests for the push line (issue #434, stage three).

The push is the half of the brief stage one did not build: *something crossing a
line on both ratings is raised to you unasked*. Two commands carry it -- `pushed`
reads and `raise` writes -- and the split is what makes the mark mean *the ask
was put* rather than *this was printed once*.

Everything here runs offline. The write half is probed in both polarities with a
fence that is itself controlled, because a fence that caught nothing would let a
write-nothing claim pass while writing.
"""

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

CELL = Path(__file__).resolve().parents[1]
SCRIPT = CELL / "scripts" / "pool.py"

spec = importlib.util.spec_from_file_location("filing_pool_push", SCRIPT)
pool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pool)

ASSESSED = "assessed:no-cause"
RAISED = "raised"


def policy_dict(**over):
    base = {
        "axes": {
            "severity": {"meaning": "how bad", "color": "B60205",
                         "values": {"sev:1": 1, "sev:2": 2, "sev:3": 3}},
            "urgency": {"meaning": "how soon", "color": "D93F0B",
                        "values": {"urg:1": 1, "urg:2": 2, "urg:3": 3}},
        },
        "order": ["severity", "urgency"],
        "framed": {"label": "framed", "color": "0E8A16", "meaning": "decided"},
        "cause": {"label": "cause", "color": "B60205", "meaning": "a cause"},
        "assessed": {"label": ASSESSED, "color": "C5DEF5", "meaning": "asked"},
        "raised": {"label": RAISED, "color": "5319E7", "meaning": "put to the owner"},
        "shortlist_size": 3,
        "accrual": {"symptoms_per_band": 2},
        "fade": {"quiet_days": 30, "closes": False},
        "assessment": {"before_shortlist": 3, "per_cycle": 3},
        "push": {"severity": 3, "urgency": 3},
    }
    base.update(over)
    return base


def issue(number, labels=(), assessed=True, updated=None):
    names = list(labels) + ([ASSESSED] if assessed else [])
    out = {"number": number, "title": f"i{number}",
           "labels": [{"name": n} for n in names]}
    if updated is not None:
        out["updatedAt"] = updated
    return out


def ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


@pytest.fixture(autouse=True)
def fence_the_wire(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError(f"this test reached the network: {str(args)[:90]}")
    monkeypatch.setattr(pool, "gh", refuse)
    monkeypatch.setattr(pool.subprocess, "run", refuse)


def stub(monkeypatch, issues, parents=None, sent=None):
    def wire(args):
        if args[:2] == ["issue", "list"]:
            return json.dumps(issues)
        if sent is not None:
            sent.append(args)
            return ""
        raise AssertionError(f"a read-only command wrote: {args}")
    monkeypatch.setattr(pool, "gh", wire)
    monkeypatch.setattr(pool, "causal_parents", lambda policy, repo=None: dict(parents or {}))


# ------------------------------------------------------------- what crosses


def test_it_crosses_only_on_every_axis(monkeypatch):
    """Criterion 1. The brief's push is something crossing a line on *both*
    ratings; an item catastrophic but not urgent, or urgent but trivial, is what
    the pull is for."""
    stub(monkeypatch, [
        issue(1, labels=["sev:3", "urg:3"]),   # both -- crosses
        issue(2, labels=["sev:3", "urg:1"]),   # severity only
        issue(3, labels=["sev:1", "urg:3"]),   # urgency only
        issue(4, labels=["sev:1", "urg:1"]),   # neither
    ])
    items, _ = pool.read_pool(policy_dict())
    crossing = {it["number"] for it in items if pool.crosses(it, policy_dict())}
    assert crossing == {1}, crossing


def test_the_comparison_is_at_or_above(monkeypatch):
    """Criterion 1's boundary. The shipped line is the top band, and a strict
    `>` against a top band can never fire at all -- a threshold nobody edited
    would be a mechanism that silently does nothing."""
    policy = policy_dict(push={"severity": 2, "urgency": 2})
    stub(monkeypatch, [
        issue(1, labels=["sev:2", "urg:2"]),   # exactly at the line
        issue(2, labels=["sev:3", "urg:3"]),   # above it
        issue(3, labels=["sev:1", "urg:1"]),   # below it
    ])
    items, _ = pool.read_pool(policy)
    crossing = {it["number"] for it in items if pool.crosses(it, policy)}
    assert crossing == {1, 2}, crossing


def test_it_reads_the_effective_pair_and_not_the_labels(monkeypatch):
    """Criterion 2. The point of stage two is that a cause climbs as its
    symptoms accumulate, so a push reading the filer's labels would never fire
    for the item the accrual exists to surface. The severity lift comes from the
    symptoms' band and the urgency lift from their count -- four symptoms at
    `symptoms_per_band: 2` is two bands."""
    stub(monkeypatch, [
        issue(1, labels=["cause", "sev:1", "urg:1"]),
        *[issue(n, labels=["sev:3", "urg:1"]) for n in (2, 3, 4, 5)],
    ], parents={2: 1, 3: 1, 4: 1, 5: 1})
    items, _ = pool.read_pool(policy_dict())
    by = {it["number"]: it for it in items}
    assert by[1]["effective"] == {"severity": 3, "urgency": 3}, by[1]["effective"]
    assert pool.crosses(by[1], policy_dict())
    # The control: the same cause with no symptoms does not cross.
    stub(monkeypatch, [issue(1, labels=["cause", "sev:1", "urg:1"])])
    items, _ = pool.read_pool(policy_dict())
    assert not pool.crosses(items[0], policy_dict())


def test_an_unrated_or_clashed_axis_cannot_cross(monkeypatch):
    """`None` reaches no threshold, which is the answer `at_floor` gives too."""
    stub(monkeypatch, [
        issue(1, labels=["urg:3"]),                    # severity unrated
        issue(2, labels=["sev:1", "sev:3", "urg:3"]),  # severity clashed
    ])
    items, _ = pool.read_pool(policy_dict())
    assert not any(pool.crosses(it, policy_dict()) for it in items)


# ------------------------------------------------------ what pushed reports


def test_a_raised_item_is_not_named_again(monkeypatch, capsys):
    """Criterion 3, with its negative control: the same item unmarked is named,
    so the filter is doing something rather than being off."""
    over = ["sev:3", "urg:3"]
    stub(monkeypatch, [issue(1, labels=[*over, RAISED]), issue(2, labels=over)])
    pool.cmd_pushed(policy_dict(), None)
    out = capsys.readouterr().out
    assert "#2" in out and "#1" not in out, out


def test_a_framed_item_is_never_pushed(monkeypatch, capsys):
    """Criterion 8. The push is a route out of the pool, and something already
    on the board has left it."""
    stub(monkeypatch, [
        issue(1, labels=["sev:3", "urg:3", "framed"]),
        issue(2, labels=["sev:3", "urg:3"]),
    ])
    pool.cmd_pushed(policy_dict(), None)
    out = capsys.readouterr().out
    assert "#2" in out and "#1" not in out, out


def test_an_unassessed_crossing_is_still_pushed(monkeypatch, capsys):
    """Criterion 10, and the call reading 7 makes.

    D-441 decision 5 gates `shortlist`, and the amendment that ordered it scopes
    the gate to the pull -- the pool works out causes *before a session brings
    you a few*. A push is a line being crossed, not a session choosing what to
    bring, and gating it would silence an unassessed catastrophe precisely
    because nobody has got to it yet.
    """
    stub(monkeypatch, [issue(1, labels=["sev:3", "urg:3"], assessed=False)])
    assert pool.cmd_pushed(policy_dict(), None) == 0
    out = capsys.readouterr().out
    assert "#1" in out, out
    assert "?" in out, "the row should still say the cause question is open"


def test_pushed_says_so_when_nothing_has_crossed(monkeypatch, capsys):
    """The lawful polarity. A command that printed a bare header when there was
    nothing to do would read as broken."""
    stub(monkeypatch, [issue(1, labels=["sev:1", "urg:1"])])
    pool.cmd_pushed(policy_dict(), None)
    assert "nothing has crossed" in capsys.readouterr().out


# ------------------------------------------------------------- the two halves


def test_pushed_writes_nothing_in_either_polarity(monkeypatch, capsys):
    """Criterion 4. `stub` without `sent` raises on any non-read, so a write
    fails the test rather than being counted."""
    for closes in (False, True):
        stub(monkeypatch, [issue(1, labels=["sev:3", "urg:3"]),
                           issue(2, labels=["sev:3", "urg:3", RAISED])])
        assert pool.cmd_pushed(policy_dict(fade={"quiet_days": 30, "closes": closes}), None) == 0
    capsys.readouterr()


def test_the_fence_in_that_probe_catches_a_write(monkeypatch):
    """The negative control. Without this, `pushed writes nothing` would pass
    for a harness that could not see a write."""
    stub(monkeypatch, [issue(1, labels=["sev:3", "urg:3"])])
    with pytest.raises(AssertionError, match="a read-only command wrote"):
        pool.gh(["issue", "edit", "1", "--add-label", RAISED])


def test_raise_writes_the_mark_and_nothing_else(monkeypatch, capsys):
    """Criterion 5, and the write goes through the one chokepoint."""
    sent = []
    monkeypatch.setattr(pool, "gh", lambda args: sent.append(args) or "")
    pool.cmd_raise(policy_dict(), None, 7)
    assert sent == [["issue", "edit", "7", "--add-label", RAISED]], sent
    capsys.readouterr()


def test_raise_is_the_only_thing_that_writes_the_mark():
    """Criterion 5's second half, read off the source: a second writer would
    make the mark mean two things."""
    source = SCRIPT.read_text(encoding="utf-8")
    writers = [line for line in source.splitlines()
               if 'policy["raised"]["label"]' in line and "add=" in line]
    assert len(writers) == 1, writers


def test_the_mark_is_on_the_rail_and_the_asks_mark_is_not():
    """Criterion 6. `awaiting-owner` belongs to the `engagement` cell, which
    lets a repository rename it in doctrine; naming it here would give it a
    second governing home -- the shape D-441 decision 4 recorded for `cause`."""
    policy = policy_dict()
    assert RAISED in pool.writable_labels(policy)
    source = SCRIPT.read_text(encoding="utf-8")
    assert "awaiting-owner" not in source
    assert "awaiting-owner" not in (CELL / "scripts" / "pool-policy.json").read_text(encoding="utf-8")


# ------------------------------------------------------------- the policy


def test_a_policy_without_the_push_block_is_refused(tmp_path):
    """Criterion 7, on D-441 decision 8's ground: a policy written before this
    stage is refused with a message naming what to add, never defaulted."""
    policy = policy_dict()
    del policy["push"]
    path = tmp_path / "pool-policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8", newline="\n")
    with pytest.raises(pool.PoolError, match="push"):
        pool.load_policy(path)


@pytest.mark.parametrize("mutate, because", [
    (lambda p: p["push"].pop("urgency"), "a threshold on a subset of the axes"),
    (lambda p: p["push"].update({"effort": 2}), "a threshold on something that is not an axis"),
    (lambda p: p["push"].update({"severity": 9}), "a band the axis does not have"),
    (lambda p: p["push"].update({"severity": True}), "a boolean, which is an int and is not a band"),
    (lambda p: p.pop("raised"), "no raised block at all"),
    (lambda p: p["raised"].update({"label": "sev:1"}), "the raised label doubling as a rating"),
    (lambda p: p["raised"].update({"label": "framed"}), "the raised label doubling as the framed one"),
])
def test_a_push_policy_that_would_fire_wrongly_is_refused(tmp_path, mutate, because):
    policy = policy_dict()
    mutate(policy)
    path = tmp_path / "pool-policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8", newline="\n")
    with pytest.raises(pool.PoolError):
        pool.load_policy(path)


def test_the_shipped_policy_validates_and_ships_at_the_top_band():
    """The lawful polarity, and the one that would stop every command."""
    policy = pool.load_policy(pool.DEFAULT_POLICY)
    for name in policy["order"]:
        assert policy["push"][name] == max(policy["axes"][name]["values"].values()), name

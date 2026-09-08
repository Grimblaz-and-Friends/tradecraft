"""Tests for the push line (issue #434, stage three).

The push is the half of the brief stage one did not build: *something crossing a
line on both ratings is raised to you unasked*. Two commands carry it -- `pushed`
reads and `raise` writes -- and the split is what makes the mark mean *the ask
was put* rather than *this was printed once*.

Everything here runs offline. The write half is probed in both polarities with a
fence that is itself controlled, because a fence that caught nothing would let a
write-nothing claim pass while writing.
"""

import ast
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
    stub(monkeypatch, [issue(1, labels=["sev:3", "urg:3"], assessed=False),
                       issue(2, labels=["sev:3", "urg:3"], assessed=True)])
    assert pool.cmd_pushed(policy_dict(), None) == 0
    out = capsys.readouterr().out
    # Off the rows, not off the output. `_header` supplies a literal `?` as a
    # column heading on every listing this command prints, so `"?" in out` was
    # true whatever the rows said and the pin could not fail.
    rows = {ln[:2]: ln for ln in out.splitlines() if ln.startswith("#")}
    assert set(rows) == {"#1", "#2"}, out
    assert "?" in rows["#1"], rows["#1"]
    assert "?" not in rows["#2"], rows["#2"]


def test_pushed_says_so_when_nothing_has_crossed(monkeypatch, capsys):
    """The lawful polarity. A command that printed a bare header when there was
    nothing to do would read as broken."""
    stub(monkeypatch, [issue(1, labels=["sev:1", "urg:1"])])
    pool.cmd_pushed(policy_dict(), None)
    out = capsys.readouterr().out
    assert "nothing has crossed" in out
    assert "over the line (severity 3, urgency 3): 0" in out, out


def test_all_raised_does_not_read_as_nothing_crossed(monkeypatch, capsys):
    """The two empty states are opposites, and one sentence covered both.

    A repository whose refresh note carries what crossed had a run in which
    everything over the line had already been put to the owner writing *nothing
    has crossed* into that standing record. The header does not repair
    it: it prints the threshold and the unraised count, so before this the
    number of crossings appeared nowhere in the output.
    """
    over = ["sev:3", "urg:3"]
    stub(monkeypatch, [issue(1, labels=[*over, RAISED]),
                       issue(2, labels=[*over, RAISED])])
    assert pool.cmd_pushed(policy_dict(), None) == 0
    out = capsys.readouterr().out
    assert "nothing has crossed" not in out, out
    assert "already been put to the owner" in out, out
    assert "over the line (severity 3, urgency 3): 2" in out, out


def test_the_threshold_prints_in_the_policys_order(monkeypatch, capsys):
    """Every other printer in the module reads the axes in the policy's order;
    this one read `push`'s own key order, which a hand-written override sets."""
    policy = policy_dict(order=["urgency", "severity"])
    stub(monkeypatch, [issue(1, labels=["sev:1", "urg:1"])])
    pool.cmd_pushed(policy, None)
    assert "(urgency 3, severity 3)" in capsys.readouterr().out


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


def labelled(monkeypatch, sent, present=(RAISED,)):
    """A wire that answers the label read and records every write."""
    def wire(args):
        if args[:2] == ["label", "list"]:
            return json.dumps([{"name": n} for n in present])
        sent.append(args)
        return ""
    monkeypatch.setattr(pool, "gh", wire)


def test_raise_writes_the_mark_and_nothing_else(monkeypatch, capsys):
    """Criterion 5, and the write goes through the one chokepoint."""
    sent = []
    labelled(monkeypatch, sent)
    pool.cmd_raise(policy_dict(), None, 7)
    assert sent == [["issue", "edit", "7", "--add-label", RAISED]], sent
    capsys.readouterr()


def test_raise_refuses_when_the_repository_has_no_such_label(monkeypatch, capsys):
    """The state the mark exists to prevent.

    `raise` is the third of the three steps a refresh performs, so by the time
    it runs the ask has already been posted. A write that fails at the wire
    leaves the item asked but unmarked, and the next refresh asks the owner a
    second time -- which is what a repository that has not run `labels` gets on
    its first crossing.
    """
    sent = []
    labelled(monkeypatch, sent, present=("framed", "cause"))
    with pytest.raises(pool.PoolError, match="labels"):
        pool.cmd_raise(policy_dict(), None, 7)
    assert sent == [], "it must refuse before it writes, not after"
    capsys.readouterr()


def test_unraise_takes_the_mark_off(monkeypatch, capsys):
    """The inverse. Without it the only way back from a mark put on the wrong
    issue -- or from a decline the owner changed their mind about -- is a
    hand-edit on GitHub, which `frame`/`unframe` already refused to leave."""
    sent = []
    labelled(monkeypatch, sent)
    pool.cmd_unraise(policy_dict(), None, 7)
    assert sent == [["issue", "edit", "7", "--remove-label", RAISED]], sent
    capsys.readouterr()


def test_raise_is_the_only_command_that_writes_the_mark(monkeypatch, capsys):
    """Criterion 5's second half, driven rather than grepped.

    The line-scoped grep this replaces asked for a source line carrying both
    `policy["raised"]["label"]` and `add=`. Two independent runs defeated it by
    hoisting the label into a local first and got a green suite -- and so, in
    the end, did this change's own `raise`, which reads the label into `label`
    before writing it. Driving every command that writes a label catches that
    spelling and every other one.
    """
    seen: dict[str, list[str]] = {}
    current = [""]

    def spy(number, policy, *, add, remove, repo=None):
        seen.setdefault(current[0], []).extend(add)

    monkeypatch.setattr(pool, "edit_labels", spy)
    monkeypatch.setattr(pool, "issue_labels", lambda number, repo=None: [])
    monkeypatch.setattr(pool, "existing_labels", lambda repo=None: {RAISED})
    policy = policy_dict()
    commands = {
        "raise": lambda: pool.cmd_raise(policy, None, 1),
        "unraise": lambda: pool.cmd_unraise(policy, None, 1),
        "frame": lambda: pool.cmd_frame(policy, None, 1),
        "unframe": lambda: pool.cmd_unframe(policy, None, 1),
        "assess": lambda: pool.cmd_assess(policy, None, 1),
        "rate": lambda: pool.cmd_rate(policy, None, 1, {"severity": "sev:3"}),
    }
    for name, call in commands.items():
        current[0] = name
        call()
    assert sorted(seen) == sorted(commands), "every command must have been driven"
    writers = sorted(name for name, added in seen.items() if RAISED in added)
    assert writers == ["raise"], seen
    capsys.readouterr()


def test_every_write_site_is_a_command_that_test_drives():
    """The other half of the guard above, which drives a fixed list.

    A seventh call site added to a command the list does not name would write
    the mark unobserved, so the list and the source are held level here rather
    than by anyone remembering.
    """
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    sites = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "edit_labels":
                sites.add(fn.name)
    assert sites == {"cmd_raise", "cmd_unraise", "cmd_frame", "cmd_unframe",
                     "cmd_assess", "cmd_rate"}, sorted(sites)


def test_the_mark_is_on_the_rail_and_the_asks_mark_is_not():
    """Criterion 6. `awaiting-owner` belongs to the `engagement` cell, which
    lets a repository rename it in doctrine; naming it here would give it a
    second governing home -- the shape D-441 decision 4 recorded for `cause`."""
    policy = policy_dict()
    assert RAISED in pool.writable_labels(policy)
    source = SCRIPT.read_text(encoding="utf-8")
    assert "awaiting-owner" not in source
    assert "awaiting-owner" not in (CELL / "scripts" / "pool-policy.json").read_text(encoding="utf-8")


def test_the_mark_is_rendered_in_every_listing(monkeypatch, capsys):
    """Criterion 3's other half.

    `shortlist` does not filter what has been raised, and its first sort axis
    has no decay term, so a `sev:3` the owner declined sits first in every later
    shortlist. Before this nothing on the row said it had already been put, and
    a session raising that shortlist put it to the owner again.
    """
    over = ["sev:3", "urg:3"]
    stub(monkeypatch, [issue(1, labels=[*over, RAISED]), issue(2, labels=over)])
    pool.cmd_list(policy_dict(), None, None)
    out = capsys.readouterr().out
    rows = {ln[:2]: ln for ln in out.splitlines() if ln.startswith("#")}
    assert "!" in rows["#1"], rows["#1"]
    assert "!" not in rows["#2"], rows["#2"]
    assert "!" in out.splitlines()[1], "the column needs a heading"


def test_show_says_the_mark_is_set(monkeypatch, capsys):
    """`show` is the command a session runs about one issue, so the one fact
    that decides whether the push will name it again belongs in its answer."""
    over = ["sev:3", "urg:3"]
    stub(monkeypatch, [issue(1, labels=[*over, RAISED]), issue(2, labels=over)])
    pool.cmd_show(policy_dict(), None, 1)
    assert "raised:" in capsys.readouterr().out
    stub(monkeypatch, [issue(1, labels=[*over, RAISED]), issue(2, labels=over)])
    pool.cmd_show(policy_dict(), None, 2)
    assert "raised:" not in capsys.readouterr().out


# ------------------------------------------------- the fade, composed with crossing


def test_the_fade_takes_a_crossing_back_under_the_line(monkeypatch):
    """The composition decision 6 turns on, which nothing pinned.

    The fade is pinned in `test_pool.py` and `crosses` is pinned above; what was
    unguarded is the two together -- and that composition is the whole reason
    the mark has to be durable rather than left to the quiet clock.
    """
    policy = policy_dict()
    stub(monkeypatch, [issue(1, labels=["sev:3", "urg:3"], updated=ago(0)),
                       issue(2, labels=["sev:3", "urg:3"], updated=ago(31))])
    items = {it["number"]: it for it in pool.read_pool(policy, None)[0]}
    assert pool.crosses(items[1], policy) is True
    assert pool.crosses(items[2], policy) is False, items[2]["effective"]


def test_a_faded_crossing_is_not_pushed(monkeypatch, capsys):
    """The same composition at the command, not only at the predicate."""
    stub(monkeypatch, [issue(1, labels=["sev:3", "urg:3"], updated=ago(0)),
                       issue(2, labels=["sev:3", "urg:3"], updated=ago(31))])
    assert pool.cmd_pushed(policy_dict(), None) == 0
    out = capsys.readouterr().out
    assert "#1" in out and "#2" not in out, out


def test_touching_a_faded_crossing_puts_it_back_over_the_line(monkeypatch):
    """Why the quiet clock is not a bound on the asking.

    The fade reads the issue's own `updatedAt`, so any comment restarts it --
    including the comment an ask itself posts. An item over the line that is
    being discussed never fades out of the push, which is what makes the
    durable mark the only thing that stops the second ask.
    """
    policy = policy_dict()
    for days, expected in ((31, False), (0, True)):
        stub(monkeypatch, [issue(1, labels=["sev:3", "urg:3"], updated=ago(days))])
        item = pool.read_pool(policy, None)[0][0]
        assert pool.crosses(item, policy) is expected, (days, item["effective"])


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


def test_a_missing_block_is_refused_by_a_message_naming_every_added_block(tmp_path):
    """D-441 decision 8: a refusal names what to add. It named five of the
    seven blocks that have been added to the policy since its original shape,
    so the two this stage's own work depends on were the ones left out."""
    policy = policy_dict()
    del policy["accrual"]
    path = tmp_path / "pool-policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8", newline="\n")
    with pytest.raises(pool.PoolError) as caught:
        pool.load_policy(path)
    for block in ("cause", "assessed", "raised", "accrual", "fade",
                  "assessment", "push"):
        assert f"'{block}'" in str(caught.value), (block, str(caught.value))


def test_the_shipped_policy_validates_and_ships_at_the_top_band():
    """The lawful polarity, and the one that would stop every command."""
    policy = pool.load_policy(pool.DEFAULT_POLICY)
    for name in policy["order"]:
        assert policy["push"][name] == max(policy["axes"][name]["values"].values()), name

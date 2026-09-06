"""Behavioural tests for pool.py (issue #434).

Everything here runs offline. What is tested is the part that decides rather
than the part that talks to GitHub: the policy's validation, the pool's order,
the partition into pool and framed, and the rail that no label outside the
policy is ever written.

Two things here are guard-shaped and are probed in both polarities. The policy
validator must reject a policy that would order wrongly and must accept the one
this cell ships, because a validator that refused the shipped default would
stop every command. The label rail must refuse a label the policy does not name
and must let one it does through -- and it carries a negative control, because
a rail that refused everything would pass a one-sided probe while being
useless.
"""

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

CELL = Path(__file__).resolve().parents[1]
SCRIPT = CELL / "scripts" / "pool.py"

spec = importlib.util.spec_from_file_location("filing_pool", SCRIPT)
pool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pool)

# Captured before the fence below replaces the name. The two tests that
# exercise the launch shape itself are testing `gh`, not something that
# calls it, so they need the real one -- and taking it here rather than
# unpatching keeps them fenced on every other route.
REAL_GH = pool.gh


def policy_dict(**over):
    """The shape the shipped default has, small enough to mutate per test."""
    base = {
        "axes": {
            "severity": {"meaning": "how bad", "color": "B60205",
                         "values": {"sev:1": 1, "sev:2": 2, "sev:3": 3}},
            "urgency": {"meaning": "how soon", "color": "D93F0B",
                        "values": {"urg:1": 1, "urg:2": 2, "urg:3": 3}},
        },
        "order": ["severity", "urgency"],
        "framed": {"label": "framed", "color": "0E8A16", "meaning": "decided"},
        "shortlist_size": 3,
    }
    base.update(over)
    return base


def write_policy(path: Path, policy) -> Path:
    path.write_text(json.dumps(policy), encoding="utf-8", newline="\n")
    return path


def issue(number, title="t", labels=()):
    return {"number": number, "title": title,
            "labels": [{"name": name} for name in labels]}


@pytest.fixture(autouse=True)
def fence_the_wire(monkeypatch):
    """No test here reaches the network, and none opts in.

    Autouse rather than a helper each test calls: the fence the board's suite
    grew was a function three of sixty-five tests remembered, and the one that
    drove a mutation was not among them. A test needing a stub overrides the
    one route it stubs and stays fenced on the other.
    """
    def refuse(kind):
        def _refuse(*args, **kwargs):
            raise AssertionError(
                f"this test reached the network via {kind}: {str(args)[:90]}"
            )
        return _refuse

    monkeypatch.setattr(pool, "gh", refuse("gh"))
    monkeypatch.setattr(pool.subprocess, "run", refuse("subprocess"))


# ------------------------------------------------------------- the policy


def test_the_shipped_default_validates():
    """The lawful polarity, and the one that would stop every command."""
    policy = pool.load_policy(pool.DEFAULT_POLICY)
    assert policy["framed"]["label"]
    assert sorted(policy["order"]) == sorted(policy["axes"])


@pytest.mark.parametrize(
    "mutate, because",
    [
        (lambda p: p.update(axes={}), "no axes at all"),
        (lambda p: p["axes"]["severity"].pop("values"), "an axis with no values"),
        (lambda p: p["axes"]["severity"]["values"].update({"sev:1": "high"}),
         "a value that is not a number"),
        (lambda p: p["axes"]["severity"]["values"].update({"sev:1": True}),
         "a boolean, which is an int in Python and is not a rating"),
        (lambda p: p["axes"]["urgency"]["values"].update({"sev:1": 1}),
         "one label on two axes"),
        (lambda p: p.update(order=["severity"]), "an axis nothing orders by"),
        (lambda p: p.update(order=["severity", "urgency", "severity"]),
         "an axis ordered by twice"),
        (lambda p: p.update(framed={"label": "sev:1"}),
         "the framed label doubling as a rating"),
        (lambda p: p.update(framed={"label": "  "}), "a blank framed label"),
        (lambda p: p.update(shortlist_size=0), "a shortlist that raises nothing"),
        (lambda p: p.update(shortlist_size="five"), "a shortlist size that is not a number"),
    ],
)
def test_a_policy_that_would_order_wrongly_is_refused(tmp_path, mutate, because):
    policy = policy_dict()
    mutate(policy)
    path = write_policy(tmp_path / "pool-policy.json", policy)
    with pytest.raises(pool.PoolError):
        pool.load_policy(path)


def test_a_policy_that_is_not_json_names_the_file(tmp_path):
    path = tmp_path / "pool-policy.json"
    path.write_text("{not json", encoding="utf-8", newline="\n")
    with pytest.raises(pool.PoolError) as caught:
        pool.load_policy(path)
    assert str(path) in str(caught.value)


# -------------------------------------------------- where the policy is found


def test_an_override_at_the_repository_root_wins(tmp_path):
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    write_policy(root / "pool-policy.json", policy_dict())
    assert pool.find_policy(root) == root / "pool-policy.json"


def test_the_root_is_found_from_a_subdirectory(tmp_path):
    """The walk-up, which is the whole reason this is not `Path.cwd()`.

    A session running this from a subdirectory would otherwise get the shipped
    default while the repository's own override sat two directories up unread,
    and nothing in the output would say which one was used.
    """
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    write_policy(root / "pool-policy.json", policy_dict())
    deep = root / "a" / "b"
    deep.mkdir(parents=True)
    assert pool.find_policy(deep) == root / "pool-policy.json"


def test_a_repository_with_no_override_gets_the_shipped_default(tmp_path):
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    assert pool.find_policy(root) == pool.DEFAULT_POLICY


def test_a_worktree_whose_git_is_a_file_is_still_a_root(tmp_path):
    """`.git` is a file inside a worktree, which is what this repository is."""
    root = tmp_path / "worktree"
    root.mkdir()
    (root / ".git").write_text("gitdir: elsewhere", encoding="utf-8", newline="\n")
    write_policy(root / "pool-policy.json", policy_dict())
    assert pool.find_policy(root) == root / "pool-policy.json"


# ------------------------------------------------------------------ the rail


def test_a_label_the_policy_names_is_written(monkeypatch):
    """The lawful polarity: the rail must not block what the policy allows."""
    sent = []
    monkeypatch.setattr(pool, "gh", lambda args: sent.append(args) or "")
    pool.edit_labels(7, policy_dict(), add=["sev:2"], remove=["sev:1"])
    assert sent and "--add-label" in sent[0] and "sev:2" in sent[0]
    assert "--remove-label" in sent[0] and "sev:1" in sent[0]


@pytest.mark.parametrize("outsider", ["bug", "wontfix", "sev:9", "framed-ish"])
def test_a_label_the_policy_does_not_name_is_refused(outsider):
    """The unlawful polarity, over labels a repository really carries."""
    with pytest.raises(pool.PoolError) as caught:
        pool.edit_labels(7, policy_dict(), add=[outsider], remove=[])
    assert outsider in str(caught.value)


def test_the_rail_refuses_an_outsider_on_the_removal_side_too():
    """Removing is writing. A rail covering only additions would let a command
    strip a label the policy never named."""
    with pytest.raises(pool.PoolError):
        pool.edit_labels(7, policy_dict(), add=[], remove=["bug"])


def test_the_rail_probe_would_report_differently_if_the_set_were_wider(monkeypatch):
    """The negative control, drawn from the probe's own class.

    A rail that refused every label would pass the unlawful-polarity probe
    above while being useless, and the probe could not tell the two apart. So
    the same call is run against a widened writable set: it transmits, which
    shows the refusal above came from the policy's contents rather than from
    the call being refused unconditionally.
    """
    sent = []
    monkeypatch.setattr(pool, "gh", lambda args: sent.append(args) or "")
    monkeypatch.setattr(pool, "writable_labels", lambda policy: frozenset({"bug"}))
    pool.edit_labels(7, policy_dict(), add=["bug"], remove=[])
    assert sent and "bug" in sent[0]


def test_nothing_is_sent_when_there_is_nothing_to_change(monkeypatch):
    monkeypatch.setattr(pool, "gh", lambda args: pytest.fail("sent an empty edit"))
    pool.edit_labels(7, policy_dict(), add=[], remove=[])


def test_writable_labels_is_exactly_the_policy(monkeypatch):
    assert pool.writable_labels(policy_dict()) == frozenset(
        {"sev:1", "sev:2", "sev:3", "urg:1", "urg:2", "urg:3", "framed"}
    )


def test_the_framed_label_a_repository_renamed_is_what_frame_writes(monkeypatch):
    """The policy owns the vocabulary, so renaming it renames what is written."""
    sent = []
    monkeypatch.setattr(pool, "gh", lambda args: sent.append(args) or "")
    policy = policy_dict(framed={"label": "picked"})
    pool.cmd_frame(policy, None, 12)
    assert "picked" in sent[0] and "framed" not in sent[0]


# -------------------------------------------------------------- the partition


def stub_issues(monkeypatch, issues):
    monkeypatch.setattr(pool, "gh", lambda args: json.dumps(issues))


def test_an_issue_is_in_the_pool_unless_it_carries_the_framed_label(monkeypatch):
    stub_issues(monkeypatch, [
        issue(1, labels=["sev:3", "urg:1"]),
        issue(2, labels=["framed", "sev:1", "urg:1"]),
        issue(3),
    ])
    pool_items, framed = pool.read_pool(policy_dict())
    assert [it["number"] for it in framed] == [2]
    assert sorted(it["number"] for it in pool_items) == [1, 3]


def test_the_open_set_is_partitioned_with_nothing_in_both_and_nothing_lost(monkeypatch):
    numbers = list(range(1, 21))
    stub_issues(monkeypatch, [
        issue(n, labels=["framed"] if n % 4 == 0 else []) for n in numbers
    ])
    pool_items, framed = pool.read_pool(policy_dict())
    got = [it["number"] for it in pool_items] + [it["number"] for it in framed]
    assert sorted(got) == numbers
    assert len(set(got)) == len(numbers)


def test_a_read_that_comes_back_at_its_limit_is_refused(monkeypatch):
    """A partition over a truncated read is wrong in a way its output cannot show."""
    stub_issues(monkeypatch, [issue(n) for n in range(pool.ISSUE_READ_LIMIT)])
    with pytest.raises(pool.PoolError) as caught:
        pool.open_issues()
    assert "short" in str(caught.value)


def test_a_read_below_its_limit_is_accepted(monkeypatch):
    """The lawful polarity of the same guard: an ordinary board is not refused."""
    stub_issues(monkeypatch, [issue(n) for n in range(pool.ISSUE_READ_LIMIT - 1)])
    assert len(pool.open_issues()) == pool.ISSUE_READ_LIMIT - 1


# ------------------------------------------------------------------ the order


def ordered(monkeypatch, issues, policy=None):
    stub_issues(monkeypatch, issues)
    items, _ = pool.read_pool(policy or policy_dict())
    return [it["number"] for it in items]


def test_severity_dominates_urgency(monkeypatch):
    assert ordered(monkeypatch, [
        issue(1, labels=["sev:1", "urg:3"]),
        issue(2, labels=["sev:2", "urg:1"]),
    ]) == [2, 1]


def test_urgency_breaks_a_tie_on_severity(monkeypatch):
    assert ordered(monkeypatch, [
        issue(1, labels=["sev:2", "urg:1"]),
        issue(2, labels=["sev:2", "urg:3"]),
    ]) == [2, 1]


def test_the_older_filing_wins_a_tie_on_both(monkeypatch):
    assert ordered(monkeypatch, [
        issue(9, labels=["sev:2", "urg:2"]),
        issue(4, labels=["sev:2", "urg:2"]),
    ]) == [4, 9]


def test_the_policys_order_is_what_orders(monkeypatch):
    """Reversing `order` reverses which axis dominates, with no code change."""
    issues = [issue(1, labels=["sev:1", "urg:3"]), issue(2, labels=["sev:3", "urg:1"])]
    assert ordered(monkeypatch, issues) == [2, 1]
    assert ordered(monkeypatch, issues,
                   policy_dict(order=["urgency", "severity"])) == [1, 2]


def test_unrated_sits_below_every_rated_item_however_low(monkeypatch):
    """Unrated is not zero: it has not been judged, not judged harmless."""
    assert ordered(monkeypatch, [
        issue(1),
        issue(2, labels=["sev:1", "urg:1"]),
    ]) == [2, 1]


def test_half_rated_counts_as_unrated(monkeypatch):
    assert ordered(monkeypatch, [
        issue(1, labels=["sev:3"]),
        issue(2, labels=["sev:1", "urg:1"]),
    ]) == [2, 1]


def test_two_values_on_one_axis_are_reported_rather_than_resolved(monkeypatch):
    stub_issues(monkeypatch, [issue(1, labels=["sev:1", "sev:3", "urg:2"])])
    items, _ = pool.read_pool(policy_dict())
    assert items[0]["clashes"] == ["severity"]
    assert not pool.is_rated(items[0], policy_dict())
    assert "CLASH" in pool._line(items[0], policy_dict())


# -------------------------------------------------------------- the shortlist


def test_the_shortlist_holds_at_most_the_policys_size(monkeypatch, capsys):
    stub_issues(monkeypatch, [
        issue(n, labels=["sev:3", "urg:3"]) for n in range(1, 11)
    ])
    assert pool.cmd_shortlist(policy_dict(), None, None) == 0
    body = capsys.readouterr().out
    raised = [line for line in body.splitlines() if line.startswith("#")]
    assert len(raised) == 3


def test_the_shortlist_raises_nothing_that_is_already_framed(monkeypatch, capsys):
    stub_issues(monkeypatch, [
        issue(1, labels=["framed", "sev:3", "urg:3"]),
        issue(2, labels=["sev:1", "urg:1"]),
    ])
    pool.cmd_shortlist(policy_dict(), None, None)
    out = capsys.readouterr().out
    assert "#2" in out and "#1 " not in out


def test_the_shortlist_says_so_when_it_is_drawn_from_an_unrated_pool(monkeypatch, capsys):
    """Landing this leaves every filing unrated, so the first shortlists are the
    oldest issues rather than the highest-rated. Saying that is the difference
    between a report and a ranking nobody earned."""
    stub_issues(monkeypatch, [issue(n) for n in range(1, 11)])
    pool.cmd_shortlist(policy_dict(), None, None)
    assert "rather than the highest-rated" in capsys.readouterr().out


def test_a_fully_rated_pool_gets_no_such_warning(monkeypatch, capsys):
    """The lawful polarity: the caveat must not fire on the state it is about."""
    stub_issues(monkeypatch, [
        issue(n, labels=["sev:2", "urg:2"]) for n in range(1, 11)
    ])
    pool.cmd_shortlist(policy_dict(), None, None)
    assert "rather than the highest-rated" not in capsys.readouterr().out


def test_count_overrides_the_policys_size(monkeypatch, capsys):
    stub_issues(monkeypatch, [
        issue(n, labels=["sev:3", "urg:3"]) for n in range(1, 11)
    ])
    pool.cmd_shortlist(policy_dict(), None, 7)
    raised = [line for line in capsys.readouterr().out.splitlines()
              if line.startswith("#")]
    assert len(raised) == 7


# ------------------------------------------------------------------- rating


def test_rating_clears_every_other_value_on_that_axis(monkeypatch, capsys):
    """Set, not add. An issue left carrying two values on one axis is the clash
    state above, and a rate that only added would manufacture it."""
    sent = []
    monkeypatch.setattr(pool, "gh", lambda args: sent.append(args) or "")
    monkeypatch.setattr(pool, "issue_labels",
                        lambda number, repo=None: ["sev:1", "sev:3", "urg:1"])
    pool.cmd_rate(policy_dict(), None, 5, {"severity": "sev:2"})
    args = sent[0]
    assert args[args.index("--add-label") + 1] == "sev:2"
    removed = [args[i + 1] for i, a in enumerate(args) if a == "--remove-label"]
    assert sorted(removed) == ["sev:1", "sev:3"]
    assert "urg:1" not in removed, "the other axis is untouched"


def test_rating_removes_only_the_values_the_issue_actually_carries(monkeypatch):
    """Probed live on 2026-09-06 against a real repository:

        gh issue edit N --remove-label bug     -> exit 0   (issue lacks it)
        gh issue edit N --remove-label sev:1   -> exit 1   ('sev:1' not found)

    The second is a label the *repository* lacks, which is the state before
    `labels` has run -- so removing every other value unconditionally made the
    first `rate` in any repository fail at the wire, on the one command the
    cell tells a filer to use.
    """
    sent = []
    monkeypatch.setattr(pool, "gh", lambda args: sent.append(args) or "")
    monkeypatch.setattr(pool, "issue_labels", lambda number, repo=None: [])
    pool.cmd_rate(policy_dict(), None, 5, {"severity": "sev:2"})
    args = sent[0]
    assert "--remove-label" not in args, (
        "nothing to remove: the issue carries no value on that axis"
    )
    assert args[args.index("--add-label") + 1] == "sev:2"


def test_two_labels_on_one_axis_are_refused():
    with pytest.raises(pool.PoolError) as caught:
        pool.resolve_ratings(policy_dict(), ["sev:1", "sev:3"])
    assert "one value per axis" in str(caught.value)


def test_a_label_no_axis_names_is_refused():
    with pytest.raises(pool.PoolError) as caught:
        pool.resolve_ratings(policy_dict(), ["priority:high"])
    assert "priority:high" in str(caught.value)


def test_one_label_per_axis_resolves_to_its_axis():
    assert pool.resolve_ratings(policy_dict(), ["urg:2", "sev:1"]) == {
        "urgency": "urg:2", "severity": "sev:1",
    }


# ---------------------------------------------------------------- the labels


def test_labels_creates_only_what_is_missing(monkeypatch, capsys):
    """Never `--force`: that would rewrite the colour and description of a label
    a repository had already customised, from a command whose point is that it
    changes nothing it does not have to."""
    calls = []

    def wire(args):
        calls.append(args)
        if args[:2] == ["label", "list"]:
            return json.dumps([{"name": "sev:1"}, {"name": "bug"}])
        return ""

    monkeypatch.setattr(pool, "gh", wire)
    pool.cmd_labels(policy_dict(), None, dry_run=False)
    created = [a[2] for a in calls if a[:2] == ["label", "create"]]
    assert "sev:1" not in created
    assert sorted(created) == ["framed", "sev:2", "sev:3", "urg:1", "urg:2", "urg:3"]
    assert all("--force" not in a for a in calls)


def test_labels_dry_run_writes_nothing(monkeypatch):
    def wire(args):
        if args[:2] == ["label", "list"]:
            return json.dumps([])
        raise AssertionError(f"a dry run wrote: {args}")

    monkeypatch.setattr(pool, "gh", wire)
    assert pool.cmd_labels(policy_dict(), None, dry_run=True) == 0


# ------------------------------------------------------------------ show, gh


def test_show_says_which_side_an_issue_is_on(monkeypatch, capsys):
    stub_issues(monkeypatch, [
        issue(1, labels=["framed"]), issue(2, labels=["sev:2", "urg:1"]),
    ])
    pool.cmd_show(policy_dict(), None, 1)
    assert "is framed" in capsys.readouterr().out
    pool.cmd_show(policy_dict(), None, 2)
    out = capsys.readouterr().out
    assert "in the pool" in out and "sev:2" in out


def test_show_refuses_an_issue_that_is_not_open(monkeypatch):
    stub_issues(monkeypatch, [issue(1)])
    with pytest.raises(pool.PoolError) as caught:
        pool.cmd_show(policy_dict(), None, 99)
    assert "#99" in str(caught.value)


def test_a_missing_gh_says_so_rather_than_raising_a_file_error(monkeypatch):
    def absent(*args, **kwargs):
        raise FileNotFoundError("gh")

    monkeypatch.setattr(pool.subprocess, "run", absent)
    with pytest.raises(pool.PoolError) as caught:
        REAL_GH(["issue", "list"])
    assert "gh" in str(caught.value)


def test_every_gh_launch_names_all_three_streams(monkeypatch):
    """The one launch shape, checked at the one place launches happen."""
    seen = {}

    def capture(cmd, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(pool.subprocess, "run", capture)
    REAL_GH(["issue", "list"])
    assert seen["stdin"] is subprocess.DEVNULL
    assert seen["capture_output"] is True


def test_a_repository_is_named_only_when_one_is_given():
    assert pool._repo_args(None) == []
    assert pool._repo_args("o/r") == ["--repo", "o/r"]


# ------------------------------------------------------- what the review found


def test_two_labels_on_one_axis_sharing_a_value_are_refused(tmp_path):
    """`load_policy`'s docstring names non-distinct values as the silent
    wrong-order failure, and for a while only named it: two labels on one number
    order as a tie, so a repository believes it configured distinct bands while
    the axis collapses them."""
    policy = policy_dict()
    policy["axes"]["severity"]["values"] = {"sev:1": 1, "sev:2": 1}
    path = write_policy(tmp_path / "pool-policy.json", policy)
    with pytest.raises(pool.PoolError) as caught:
        pool.load_policy(path)
    assert "same value" in str(caught.value)


@pytest.mark.parametrize("bad", ["sev,high", "a,b", ","])
def test_a_label_name_carrying_a_comma_is_refused(tmp_path, bad):
    """`gh issue edit --add-label` splits on commas -- its own help demonstrates
    it with "bug,help wanted" -- so such a name would write labels the policy
    never named and leave the intended one unset. The write rail defeated by a
    name rather than by a call site, so it is refused where the vocabulary is
    admitted."""
    policy = policy_dict()
    policy["axes"]["severity"]["values"] = {bad: 1, "sev:2": 2}
    path = write_policy(tmp_path / "pool-policy.json", policy)
    with pytest.raises(pool.PoolError) as caught:
        pool.load_policy(path)
    assert "comma" in str(caught.value)


def test_a_comma_in_the_framed_label_is_refused_too(tmp_path):
    """The framed label reaches the same write path."""
    path = write_policy(tmp_path / "pool-policy.json",
                        policy_dict(framed={"label": "framed,decided"}))
    with pytest.raises(pool.PoolError):
        pool.load_policy(path)


def test_an_ordinary_colon_label_is_still_accepted(tmp_path):
    """The lawful polarity, and the shipped default's own shape: a guard that
    refused every punctuated name would reject the policy this cell ships."""
    assert pool.load_policy(pool.DEFAULT_POLICY)["framed"]["label"]


def test_a_clean_axis_survives_a_clash_on_another_axis(monkeypatch):
    """The clash test was over the whole list, so one clashed axis discarded
    every clean rating an item had -- the worst severity in the pool sorted
    below the mildest on issue number alone."""
    stub_issues(monkeypatch, [
        issue(3, labels=["sev:1", "urg:1", "urg:2"]),
        issue(7, labels=["sev:3", "urg:1", "urg:2"]),
        issue(9),
    ])
    items, _ = pool.read_pool(policy_dict())
    assert [it["number"] for it in items] == [7, 3, 9]


def test_a_clashed_item_still_sorts_below_a_cleanly_rated_one(monkeypatch):
    """The other half: a clash is still incomplete, so it does not overtake an
    item that is rated on every axis."""
    stub_issues(monkeypatch, [
        issue(3, labels=["sev:3", "urg:1", "urg:2"]),
        issue(7, labels=["sev:1", "urg:1"]),
    ])
    items, _ = pool.read_pool(policy_dict())
    assert [it["number"] for it in items] == [7, 3]


def test_shortlist_refuses_a_count_below_one(monkeypatch):
    """`shortlist_size` is validated on load; the flag overriding it was not, and
    a negative sliced from the end -- raising most of the pool while suppressing
    the caveat, because `len(rated) < size` is false for a negative."""
    stub_issues(monkeypatch, [issue(i, labels=["sev:2", "urg:2"]) for i in range(1, 11)])
    for bad in (0, -1, -8):
        with pytest.raises(pool.PoolError):
            pool.cmd_shortlist(policy_dict(), None, bad)


def test_list_refuses_a_limit_below_one(monkeypatch):
    """`--limit 0` printed the whole pool, on a falsy test where a `None` test
    was meant."""
    stub_issues(monkeypatch, [issue(i) for i in range(1, 6)])
    for bad in (0, -1):
        with pytest.raises(pool.PoolError):
            pool.cmd_list(policy_dict(), pool.DEFAULT_POLICY, None, bad)


def test_a_small_but_fully_rated_pool_gets_no_unrated_caveat(monkeypatch, capsys):
    """The caveat compared against the size asked for, so a pool of two rated
    items under a size of five was called partly unrated -- telling a reader to
    discount a ranking that was sound."""
    stub_issues(monkeypatch, [issue(i, labels=["sev:2", "urg:2"]) for i in (1, 2)])
    pool.cmd_shortlist(policy_dict(), None, None)
    out = capsys.readouterr().out
    assert "rather than the highest-rated" not in out
    assert "raising: 2" in out


def test_the_caveat_fires_when_an_unrated_item_is_actually_raised(monkeypatch, capsys):
    """The unlawful polarity of the same guard."""
    stub_issues(monkeypatch, [issue(1, labels=["sev:2", "urg:2"]), issue(2)])
    pool.cmd_shortlist(policy_dict(), None, None)
    assert "rather than the highest-rated" in capsys.readouterr().out


def test_the_label_read_refuses_when_it_comes_back_at_its_limit(monkeypatch):
    """The hazard the issue read refuses, on the label read next door: truncated,
    an existing label reads as missing and creating it fails partway through."""
    def wire(args):
        if args[:2] == ["label", "list"]:
            return json.dumps([{"name": f"l{i}"} for i in range(pool.LABEL_READ_LIMIT)])
        raise AssertionError("should not reach a create")

    monkeypatch.setattr(pool, "gh", wire)
    with pytest.raises(pool.PoolError) as caught:
        pool.cmd_labels(policy_dict(), None, dry_run=True)
    assert "came back at its limit" in str(caught.value)


def test_the_label_read_below_its_limit_is_accepted(monkeypatch, capsys):
    """The lawful polarity: an ordinary repository is not refused."""
    monkeypatch.setattr(pool, "gh", lambda args: json.dumps([{"name": "bug"}]))
    assert pool.cmd_labels(policy_dict(), None, dry_run=True) == 0


# ------------------------------------------------------------------- the CLI


def cli(monkeypatch, *argv):
    """Drive the real entry point. Nothing exercised the parser at all, so three
    flags survived deletion with the suite green and the documented invocation
    shape was wrong."""
    monkeypatch.setattr(pool, "find_policy", lambda start=None: pool.DEFAULT_POLICY)
    return pool.main(list(argv))


def test_the_repo_and_policy_flags_parse_before_the_subcommand(monkeypatch, capsys):
    """The Usage block documented them after it, where argparse exits 2."""
    assert cli(monkeypatch, "--repo", "o/r", "policy") == 0
    assert "writable labels:" in capsys.readouterr().out


def test_the_documented_usage_shape_is_the_one_that_runs(monkeypatch):
    """Every invocation the module docstring's Usage block shows, parsed by the
    real parser. Nothing drove the parser at all, which is how the block came to
    document `--repo` in a position argparse rejects with exit 2.

    Optionals in brackets are dropped and placeholders are filled, so what is
    checked is the *shape* -- the order of subcommand and options -- which is
    the part that was wrong.
    """
    forms = re.findall(r"^\s*python scripts/pool\.py (.+)$", pool.__doc__, re.M)
    assert forms, "the Usage block names no invocation"
    filler = {"N": "1", "LABEL": "sev:1", "PATH": "p.json", "OWNER/REPO": "o/r"}
    checked = 0
    for form in forms:
        bare = re.sub(r"\[[^\]]*\]", " ", form)          # drop the optionals
        argv = [filler.get(tok, tok) for tok in bare.split()]
        if not argv or argv[0].startswith("<"):
            continue                                      # the summary line
        pool.build_parser().parse_args(argv)
        checked += 1
    assert checked >= 9, f"only {checked} invocations were exercised"


def test_the_cli_refuses_a_negative_count_rather_than_raising_most_of_the_pool(
        monkeypatch, capsys):
    """Criterion 3's own falsifier, driven through the shipped entry point."""
    monkeypatch.setattr(pool, "gh", lambda args: json.dumps(
        [issue(i, labels=["sev:2", "urg:2"]) for i in range(1, 11)]))
    assert cli(monkeypatch, "shortlist", "--count", "-1") == 1
    assert "at least 1" in capsys.readouterr().err


def test_the_cli_reports_a_refusal_without_a_traceback(monkeypatch, capsys):
    """`main` turns a PoolError into one line on stderr and exit 1."""
    monkeypatch.setattr(pool, "gh", lambda args: json.dumps([]))
    assert cli(monkeypatch, "show", "999") == 1
    err = capsys.readouterr().err
    assert err.startswith("pool: ") and "Traceback" not in err

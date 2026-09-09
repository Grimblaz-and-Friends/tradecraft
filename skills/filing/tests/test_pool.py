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
from datetime import datetime, timedelta, timezone
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
        "tie_break": ["symptoms", "recent"],
        "framed": {"label": "framed", "color": "0E8A16", "meaning": "decided"},
        "cause": {"label": "cause", "color": "B60205", "meaning": "a cause"},
        "assessed": {"label": "assessed:no-cause", "color": "C5DEF5", "meaning": "asked"},
        "raised": {"label": "raised", "color": "5319E7", "meaning": "put to the owner"},
        "shortlist_size": 3,
        "accrual": {"symptoms_per_band": 2},
        "fade": {"quiet_days": 30, "closes": False},
        "assessment": {"before_shortlist": 3, "per_cycle": 3},
        "push": {"severity": 3, "urgency": 3},
    }
    base.update(over)
    return base


def write_policy(path: Path, policy) -> Path:
    path.write_text(json.dumps(policy), encoding="utf-8", newline="\n")
    return path


ASSESSED = "assessed:no-cause"


def issue(number, title="t", labels=(), assessed=True, updated=None):
    """One issue as `gh issue list --json` returns it.

    `assessed` defaults to True so that a test about ratings is not silently a
    test of the shortlist's assessment gate. The gate has its own tests, which
    pass False.
    """
    names = list(labels) + ([ASSESSED] if assessed else [])
    out = {"number": number, "title": title,
           "labels": [{"name": name} for name in names]}
    if updated is not None:
        out["updatedAt"] = updated
    return out


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
        (lambda p: p.update(tie_break=["age"]),
         "a tie-break key the script cannot compute"),
        (lambda p: p.update(tie_break=["recent", "recent"]),
         "a tie-break key consulted twice"),
        (lambda p: p.update(tie_break="recent"), "a tie-break that is not a list"),
        (lambda p: p.update(tie_break=[1]), "a tie-break entry that is not a name"),
        (lambda p: p.pop("tie_break"),
         "no tie-break at all, which is not defaulted because this file states "
         "the whole policy"),
    ],
)
def test_a_policy_that_would_order_wrongly_is_refused(tmp_path, mutate, because):
    policy = policy_dict()
    mutate(policy)
    path = write_policy(tmp_path / "pool-policy.json", policy)
    with pytest.raises(pool.PoolError):
        pool.load_policy(path)


def test_a_lawful_tie_break_the_default_does_not_ship_is_accepted(tmp_path):
    """The negative control for the five refusals above.

    A validator that refused every `tie_break` would pass each of those and
    stop every command in a repository that reordered the keys, which is the
    one thing the field exists to make cheap.
    """
    policy = policy_dict(tie_break=["recent", "symptoms"])
    path = write_policy(tmp_path / "pool-policy.json", policy)
    assert pool.load_policy(path)["tie_break"] == ["recent", "symptoms"]
    # And the empty list, which is a repository declaring the ordering #452
    # found it had by accident.
    path = write_policy(tmp_path / "pool-policy.json", policy_dict(tie_break=[]))
    assert pool.load_policy(path)["tie_break"] == []


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
        {"sev:1", "sev:2", "sev:3", "urg:1", "urg:2", "urg:3", "framed",
         "assessed:no-cause", "raised"}
    ), "the rail admits exactly the labels the policy names that something here writes"
    # And two names it must NOT admit: `cause`, which only the accrual reads,
    # and `awaiting-owner`, which the `engagement` cell governs and this script
    # never sees -- a second governing home for that name is the shape D-441
    # decision 4 recorded for the cause label.
    assert "cause" not in pool.writable_labels(policy_dict())
    assert "awaiting-owner" not in pool.writable_labels(policy_dict())


def test_the_framed_label_a_repository_renamed_is_what_frame_writes(monkeypatch):
    """The policy owns the vocabulary, so renaming it renames what is written."""
    sent = []
    monkeypatch.setattr(pool, "gh", lambda args: sent.append(args) or "")
    policy = policy_dict(framed={"label": "picked"})
    pool.cmd_frame(policy, None, 12)
    assert "picked" in sent[0] and "framed" not in sent[0]


# -------------------------------------------------------------- the partition


def stub_issues(monkeypatch, issues, parents=None):
    """The two reads `read_pool` makes: the issue list, and the parentage.

    The parentage is stubbed to empty by default. It is a separate read because
    neither `parent` nor `issueType` is in `gh issue list`'s field set, so it
    has to be GraphQL -- and it is this script's own rather than an import from
    a repository's board transport, which is repo-only and may not be reached
    from a shipped script.
    """
    monkeypatch.setattr(pool, "gh", lambda args: json.dumps(issues))
    monkeypatch.setattr(pool, "causal_parents", lambda policy, repo=None: parents or {})


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


def test_the_issue_number_is_the_last_resort_and_not_the_rule(monkeypatch):
    """With no symptoms and no stamps anywhere, both keys are equal and the
    number is all that is left. That it still decides is the point; that it
    decides *only here* is what #452 changed."""
    assert ordered(monkeypatch, [
        issue(9, labels=["sev:2", "urg:2"]),
        issue(4, labels=["sev:2", "urg:2"]),
    ]) == [4, 9]


def test_more_symptoms_wins_a_tie_on_both_ratings(monkeypatch):
    """#5 carries one symptom and #2 carries none.

    One symptom is below `symptoms_per_band`, so the accrual moves neither
    axis and the pair really is tied on the ratings -- which is what makes this
    a test of the tie-break rather than of the accrual. The numbers are the
    wrong way round on purpose: under the old rule #2 came first.
    """
    issues = [issue(5, labels=["sev:2", "urg:2"]),
              issue(2, labels=["sev:2", "urg:2"]),
              issue(9, labels=["sev:1", "urg:1"])]
    stub_issues(monkeypatch, issues, parents={9: 5})
    items, _ = pool.read_pool(policy_dict())
    assert [it["number"] for it in items] == [5, 2, 9]
    assert items[0]["effective"] == items[1]["effective"], "not a tie on ratings"


def test_the_same_pair_falls_back_to_the_number_when_no_key_runs(monkeypatch):
    """The negative control for the test above: with an empty `tie_break` the
    symptom count buys #5 nothing and the ordering is the one #452 records."""
    issues = [issue(5, labels=["sev:2", "urg:2"]),
              issue(2, labels=["sev:2", "urg:2"]),
              issue(9, labels=["sev:1", "urg:1"])]
    stub_issues(monkeypatch, issues, parents={9: 5})
    items, _ = pool.read_pool(policy_dict(tie_break=[]))
    assert [it["number"] for it in items] == [2, 5, 9]


def test_the_most_recently_touched_wins_where_symptoms_do_not(monkeypatch):
    """Both stamps sit inside one quiet window, so the fade has not moved
    either and the pair is tied on the ratings."""
    assert ordered(monkeypatch, [
        issue(5, labels=["sev:2", "urg:2"], updated=ago(0)),
        issue(2, labels=["sev:2", "urg:2"], updated=ago(3)),
    ]) == [5, 2]
    # The other polarity of the same fixture: swapping the stamps swaps the
    # order, so what decided is the stamp and not the number.
    assert ordered(monkeypatch, [
        issue(5, labels=["sev:2", "urg:2"], updated=ago(3)),
        issue(2, labels=["sev:2", "urg:2"], updated=ago(0)),
    ]) == [2, 5]


def test_an_item_with_no_stamp_does_not_win_a_recency_tie(monkeypatch):
    """It has no evidence of activity, so it cannot win a tie on activity.

    #2 is the one with no stamp and the lower number, so a run that sorted the
    stampless first -- or that fell through to the number -- would return
    [2, 5] and fail here.
    """
    assert ordered(monkeypatch, [
        issue(5, labels=["sev:2", "urg:2"], updated=ago(3)),
        issue(2, labels=["sev:2", "urg:2"]),
    ]) == [5, 2]


def test_the_policys_tie_break_order_is_what_breaks_ties(monkeypatch):
    """Reversing `tie_break` reverses which key decides, with no code change.

    #5 has the symptom and the older stamp; #2 has neither and the newer one,
    so the two keys disagree about the pair and each order picks a different
    winner.
    """
    issues = [issue(5, labels=["sev:2", "urg:2"], updated=ago(3)),
              issue(2, labels=["sev:2", "urg:2"], updated=ago(0)),
              issue(9, labels=["sev:1", "urg:1"])]
    stub_issues(monkeypatch, issues, parents={9: 5})
    first, _ = pool.read_pool(policy_dict(tie_break=["symptoms", "recent"]))
    assert [it["number"] for it in first] == [5, 2, 9]
    stub_issues(monkeypatch, issues, parents={9: 5})
    second, _ = pool.read_pool(policy_dict(tie_break=["recent", "symptoms"]))
    assert [it["number"] for it in second] == [2, 5, 9]


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


def raised_numbers(out: str) -> list[int]:
    return [int(re.match(r"#(\d+)", line).group(1))
            for line in out.splitlines() if line.startswith("#")]


def test_the_shortlist_names_what_broke_the_tie_at_its_cut(monkeypatch, capsys):
    """The whole of what #452 is for: five raised out of a tie, and a line
    saying how many were tied and which key put the last one raised above the
    first one not. Every stamp is inside one quiet window, so the fade has
    moved nothing and the five really are tied on the ratings."""
    stub_issues(monkeypatch, [
        issue(n, labels=["sev:3", "urg:3"], updated=ago(5 - n)) for n in range(1, 6)
    ])
    pool.cmd_shortlist(policy_dict(), None, None)
    out = capsys.readouterr().out
    assert raised_numbers(out) == [5, 4, 3]
    assert "5 in the pool are tied on the ratings and 3 of them raised" in out, out
    assert "most recently touched is what put #3 above #2" in out, out


def test_the_shortlist_does_not_claim_a_key_broke_a_tie_it_did_not(monkeypatch, capsys):
    """The polarity #452 records: no symptoms and no stamps, so neither key
    separates anything and the issue number is what chose. Saying the tie-break
    did it would be the accident wearing the word judgment."""
    stub_issues(monkeypatch, [
        issue(n, labels=["sev:3", "urg:3"]) for n in range(1, 6)
    ])
    pool.cmd_shortlist(policy_dict(), None, None)
    out = capsys.readouterr().out
    assert raised_numbers(out) == [1, 2, 3]
    assert "the tie-break separated none of them" in out, out
    assert "the lower issue number is what put #3 above #4" in out, out
    assert "most recently touched" not in out, out
    assert "symptoms under it" not in out, out


def test_the_shortlist_says_when_the_ratings_alone_chose(monkeypatch, capsys):
    """The third case, so that silence never has to be interpreted: a reader
    who saw no line could not tell a cut the ratings made from a tie-break that
    had stopped running."""
    stub_issues(monkeypatch, [
        issue(1, labels=["sev:3", "urg:3"]),
        issue(2, labels=["sev:3", "urg:2"]),
        issue(3, labels=["sev:2", "urg:3"]),
        issue(4, labels=["sev:2", "urg:2"]),
    ])
    pool.cmd_shortlist(policy_dict(), None, None)
    out = capsys.readouterr().out
    assert "nothing is tied at the cut: the ratings alone chose these 3" in out, out


def test_a_shortlist_holding_the_whole_pool_says_nothing_was_chosen(monkeypatch, capsys):
    """There is no cut, so there is nothing for a tie-break to have decided."""
    stub_issues(monkeypatch, [
        issue(1, labels=["sev:3", "urg:3"]),
        issue(2, labels=["sev:3", "urg:3"]),
    ])
    pool.cmd_shortlist(policy_dict(), None, None)
    assert "holds the whole pool" in capsys.readouterr().out


def test_the_shortlist_and_the_list_agree_about_the_order(monkeypatch, capsys):
    """One pool, one order. A shortlist ordered differently from the list that
    explains it would leave a reader unable to check the raised few against the
    rows above them."""
    issues = [issue(5, labels=["sev:3", "urg:3"], updated=ago(3)),
              issue(2, labels=["sev:3", "urg:3"], updated=ago(0)),
              issue(7, labels=["sev:3", "urg:3"]),
              issue(1, labels=["sev:2", "urg:2"], updated=ago(1)),
              issue(9, labels=["sev:1", "urg:1"])]
    stub_issues(monkeypatch, issues, parents={9: 5})
    pool.cmd_list(policy_dict(), None, None)
    listed = raised_numbers(capsys.readouterr().out)
    stub_issues(monkeypatch, issues, parents={9: 5})
    pool.cmd_shortlist(policy_dict(), None, None)
    few = raised_numbers(capsys.readouterr().out)
    assert few == listed[:3], (few, listed)


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
    assert sorted(created) == ["assessed:no-cause", "cause", "framed", "raised",
                               "sev:2", "sev:3", "urg:1", "urg:2", "urg:3"]
    assert all("--force" not in a for a in calls)


def test_every_label_a_command_needs_is_one_labels_creates(monkeypatch):
    """The gap that shipped: `writable_labels` gained the assessed label for the
    write rail and `label_specs` did not, so the setup command reported success
    while `assess` failed at the wire against a label the repository lacked. The
    cause label is the same shape -- never written here, read by the accrual,
    and unusable until something creates it."""
    calls = []

    def wire(args):
        calls.append(args)
        return json.dumps([]) if args[:2] == ["label", "list"] else ""

    monkeypatch.setattr(pool, "gh", wire)
    policy = policy_dict()
    pool.cmd_labels(policy, None, dry_run=False)
    created = {a[2] for a in calls if a[:2] == ["label", "create"]}
    assert pool.writable_labels(policy) <= created
    assert policy["cause"]["label"] in created
    # And the rail stays narrower than the create set: creating a label is not
    # licence to write it onto an issue.
    assert pool.writable_labels(policy) < created


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
            pool.cmd_list(policy_dict(), None, bad)


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
    monkeypatch.setattr(pool, "causal_parents", lambda policy, repo=None: {})
    return pool.main(list(argv))


def test_the_repo_and_policy_flags_parse_before_the_subcommand(monkeypatch, capsys):
    """The Usage block documented them after it, where argparse exits 2."""
    assert cli(monkeypatch, "--repo", "o/r", "policy") == 0
    assert "labels it writes onto an issue:" in capsys.readouterr().out


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


def test_every_command_says_which_policy_it_resolved(monkeypatch, capsys):
    """`--repo` steers the wire while the policy comes from the working
    directory, so a write against another repository carries this one's
    vocabulary. The commands that write said nothing at all about which policy
    they were writing from."""
    monkeypatch.setattr(pool, "gh", lambda args: json.dumps([]))
    for argv in (["framed"], ["list"], ["shortlist"], ["labels", "--dry-run"]):
        cli(monkeypatch, *argv)
        out = capsys.readouterr().out
        assert out.startswith("policy: "), (argv, out[:80])


def test_a_write_command_names_its_policy_before_it_writes(monkeypatch, capsys):
    """The sharp case: the label is written from the local policy even when
    --repo points elsewhere, so the line has to precede the write."""
    order = []
    monkeypatch.setattr(pool, "gh", lambda args: order.append("wrote") or "")
    monkeypatch.setattr(pool, "issue_labels", lambda number, repo=None: [])
    cli(monkeypatch, "--repo", "other/repo", "frame", "7")
    out = capsys.readouterr().out
    assert out.startswith("policy: ")
    assert order == ["wrote"]


def test_rating_two_axes_reads_the_issue_once(monkeypatch, capsys):
    """The read does not depend on the axis, so rating both used to make two
    identical `gh issue view` calls."""
    reads = []
    monkeypatch.setattr(pool, "gh", lambda args: "")
    monkeypatch.setattr(pool, "issue_labels",
                        lambda number, repo=None: reads.append(number) or [])
    pool.cmd_rate(policy_dict(), None, 5, {"severity": "sev:2", "urgency": "urg:1"})
    assert reads == [5]


def test_the_cli_reports_a_refusal_without_a_traceback(monkeypatch, capsys):
    """`main` turns a PoolError into one line on stderr and exit 1."""
    monkeypatch.setattr(pool, "gh", lambda args: json.dumps([]))
    assert cli(monkeypatch, "show", "999") == 1
    err = capsys.readouterr().err
    assert err.startswith("pool: ") and "Traceback" not in err


# ================================================== accrual, the fade, assessment


def ago(days):
    """An ISO-8601 stamp that many days in the past, as GitHub writes them."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")


# ------------------------------------------------------------------- accrual


def test_a_cause_is_at_least_as_bad_as_the_worst_thing_it_produces(monkeypatch):
    """The first axis accrues by maximum, not by count: a cause that produced a
    sev:3 is not a sev:1 problem however mildly anyone rated it."""
    stub_issues(monkeypatch, [
        issue(1, labels=["sev:1", "urg:1"]),
        issue(2, labels=["sev:3", "urg:1"]),
    ], parents={2: 1})
    items, _ = pool.read_pool(policy_dict())
    by = {it["number"]: it for it in items}
    assert by[1]["effective"]["severity"] == 3
    assert by[1]["ratings"]["severity"] == "sev:1", "the label itself is untouched"


def test_a_cause_climbs_on_the_second_axis_as_symptoms_accumulate(monkeypatch):
    """One band per `accrual.symptoms_per_band`, which is 2 in the test policy."""
    stub_issues(monkeypatch, [
        issue(1, labels=["sev:1", "urg:1"]),
        *[issue(n, labels=["sev:1", "urg:1"]) for n in (2, 3, 4, 5)],
    ], parents={2: 1, 3: 1, 4: 1, 5: 1})
    items, _ = pool.read_pool(policy_dict())
    by = {it["number"]: it for it in items}
    assert by[1]["effective"]["urgency"] == 3, "four symptoms, two per band, from 1"


def test_accrual_is_capped_at_the_axis_maximum(monkeypatch):
    """A cause with many symptoms does not climb past the scale a person can write."""
    stub_issues(monkeypatch, [
        issue(1, labels=["sev:1", "urg:1"]),
        *[issue(n, labels=["sev:1", "urg:1"]) for n in range(2, 20)],
    ], parents={n: 1 for n in range(2, 20)})
    items, _ = pool.read_pool(policy_dict())
    by = {it["number"]: it for it in items}
    assert by[1]["effective"]["urgency"] == 3, "the test policy's urgency tops out at 3"


def test_a_cause_that_accumulated_outranks_an_identically_labelled_one(monkeypatch):
    """Criterion 1: same labels, same bands, one carrying symptoms -- and the
    order separates them without anyone editing a label."""
    stub_issues(monkeypatch, [
        issue(10, labels=["sev:2", "urg:2"]),
        issue(11, labels=["sev:2", "urg:2"]),
        issue(12, labels=["sev:2", "urg:2"]),
        issue(13, labels=["sev:2", "urg:2"]),
    ], parents={12: 11, 13: 11})
    items, _ = pool.read_pool(policy_dict())
    assert items[0]["number"] == 11, [it["number"] for it in items]


def test_a_symptom_contributes_its_labelled_band_and_nothing_derived():
    """`_bare` is what a symptom contributes, and it reads labels only.

    A chain of causes would otherwise climb without limit and for no reason
    anybody wrote down. Pinned on `_bare` directly rather than through
    `read_pool`, because there the property is additionally held by call order
    -- symptoms are collected before any `effective` is computed -- and a test
    that rests on the ordering alone goes green under a change that removes the
    intent while keeping the order. Mutating `_bare` to return a derived pair
    reddens this; mutating `read_pool`'s call site does not, which is why this
    is the site that carries the pin.
    """
    item = {"ratings": {"severity": "sev:1", "urgency": "urg:1"}, "clashes": [],
            "effective": {"severity": 3, "urgency": 3}}
    assert pool._bare(item, policy_dict()) == {"severity": 1, "urgency": 1}


def test_a_chain_of_causes_accrues_one_level(monkeypatch):
    """The composition, over a two-level chain: #2 accrues from #3, and #1
    accrues #2's own band rather than #2's accrued one."""
    stub_issues(monkeypatch, [
        issue(1, labels=["sev:1", "urg:1"]),
        issue(2, labels=["sev:1", "urg:1"]),
        issue(3, labels=["sev:3", "urg:1"]),
    ], parents={2: 1, 3: 2})
    items, _ = pool.read_pool(policy_dict())
    by = {it["number"]: it for it in items}
    assert by[2]["effective"]["severity"] == 3
    assert by[1]["effective"]["severity"] == 1


def test_a_repository_with_no_cause_links_accrues_nothing(monkeypatch):
    """The lawful polarity: a mechanism nobody is using costs nothing."""
    stub_issues(monkeypatch, [issue(1, labels=["sev:2", "urg:2"])])
    items, _ = pool.read_pool(policy_dict())
    assert items[0]["effective"] == {"severity": 2, "urgency": 2}


def test_accrual_raises_a_rating_and_never_supplies_one(monkeypatch):
    """The clash and the blank both read as `None`, and filling either from the
    symptoms resolved a question the design refuses to resolve.

    An issue carrying two severity labels rode to the top of the pool at a value
    nobody wrote, its row saying only `CLASH` -- the one signal meaning a human
    still has to choose -- and an unrated cause sorted in the rated tier while
    `is_rated` and the header count both called it unrated. D-438 decision 3 is
    that two values on one axis are reported rather than resolved.
    """
    stub_issues(monkeypatch, [
        issue(10, labels=["sev:1", "sev:2", "urg:2"]),   # clashed severity
        issue(11, labels=["urg:2"]),                     # unrated severity
        issue(12, labels=["sev:2", "urg:2"]),            # rated, accrues
        issue(20, labels=["sev:3"]), issue(21, labels=["sev:3"]),
        issue(22, labels=["sev:3"]), issue(23, labels=["sev:3"]),
        issue(24, labels=["sev:3"]), issue(25, labels=["sev:3"]),
    ], parents={20: 10, 21: 10, 22: 11, 23: 11, 24: 12, 25: 12})
    items, _ = pool.read_pool(policy_dict())
    by = {it["number"]: it for it in items}

    assert by[10]["effective"]["severity"] is None, "a clash is not resolved"
    assert by[11]["effective"]["severity"] is None, "unrated is not supplied"
    # The control, on the same run: a cause that HAS a band still climbs to its
    # worst symptom's, so this pins the narrowing and not the mechanism.
    assert by[12]["effective"]["severity"] == 3

    # And the two agree with each other about which tier the item is in, which
    # they did not: `sort_key` called the item complete while `is_rated` and the
    # header count called it unrated, in one output.
    for number in (10, 11):
        assert not pool.is_rated(by[number], policy_dict())
        assert pool.sort_key(by[number], policy_dict())[0] == 1
    assert pool.sort_key(by[12], policy_dict())[0] == 0


# ---------------------------------------------------------------------- fade


def test_urgency_falls_one_band_per_quiet_window(monkeypatch):
    stub_issues(monkeypatch, [issue(1, labels=["sev:2", "urg:3"], updated=ago(65))])
    items, _ = pool.read_pool(policy_dict())
    assert items[0]["effective"]["urgency"] == 1, "two whole 30-day windows, from 3"


def test_severity_never_falls(monkeypatch):
    """Structural rather than a rule: only urgency carries a decay term."""
    stub_issues(monkeypatch, [issue(1, labels=["sev:3", "urg:3"], updated=ago(400))])
    items, _ = pool.read_pool(policy_dict())
    assert items[0]["effective"]["severity"] == 3
    assert items[0]["ratings"]["severity"] == "sev:3"


def test_the_fade_floors_rather_than_going_negative(monkeypatch):
    stub_issues(monkeypatch, [issue(1, labels=["sev:2", "urg:2"], updated=ago(3000))])
    items, _ = pool.read_pool(policy_dict())
    assert items[0]["effective"]["urgency"] == 1, "the test policy's urgency floor"


def test_a_quiet_issue_falls_below_an_equally_rated_active_one(monkeypatch):
    """Criterion 2's ordering half."""
    stub_issues(monkeypatch, [
        issue(1, labels=["sev:2", "urg:3"], updated=ago(90)),
        issue(2, labels=["sev:2", "urg:3"], updated=ago(0)),
    ])
    items, _ = pool.read_pool(policy_dict())
    assert [it["number"] for it in items] == [2, 1]


def test_an_issue_with_no_timestamp_fades_by_zero(monkeypatch):
    """Rather than by an amount nobody can check: a payload without the field is
    a stub or an older read, not evidence of quiet."""
    stub_issues(monkeypatch, [issue(1, labels=["sev:2", "urg:3"])])
    items, _ = pool.read_pool(policy_dict())
    assert items[0]["effective"]["urgency"] == 3


def test_the_fade_writes_nothing(monkeypatch):
    """Criterion 3. The whole reason the decay is derived: a write would bump
    `updatedAt`, which is the signal quiet is read from, so an item would decay
    once and then never again while looking exactly like one being kept alive."""
    sent = []

    def wire(args):
        if args[:2] == ["issue", "list"]:
            return json.dumps([issue(1, labels=["sev:2", "urg:3"], updated=ago(400))])
        sent.append(args)
        return "[]"

    monkeypatch.setattr(pool, "gh", wire)
    monkeypatch.setattr(pool, "causal_parents", lambda policy, repo=None: {})
    pool.cmd_list(policy_dict(), None, None)
    assert sent == [], f"the fade wrote: {sent}"


def test_the_write_fence_in_that_probe_catches_a_write(monkeypatch):
    """The negative control for the test above: it would report differently if a
    write happened, so its green means no write rather than a broken probe."""
    sent = []

    def wire(args):
        if args[:2] == ["issue", "list"]:
            return json.dumps([issue(1, labels=["sev:2", "urg:3"])])
        sent.append(args)
        return "[]"

    monkeypatch.setattr(pool, "gh", wire)
    monkeypatch.setattr(pool, "causal_parents", lambda policy, repo=None: {})
    monkeypatch.setattr(pool, "issue_labels", lambda number, repo=None: [])
    pool.cmd_frame(policy_dict(), None, 1)
    assert sent, "the fence sees writes when there are writes"


# ---------------------------------------------------------------- assessment


def test_an_assessed_issue_reads_differently_from_one_never_asked(monkeypatch):
    """Criterion 4. The difference the amendment required be visible is the
    presence or absence of one label, and it shows in the row."""
    stub_issues(monkeypatch, [
        issue(1, labels=["sev:2", "urg:2"], assessed=True),
        issue(2, labels=["sev:2", "urg:2"], assessed=False),
    ])
    items, _ = pool.read_pool(policy_dict())
    by = {it["number"]: it for it in items}
    assert by[1]["assessed"] and not by[2]["assessed"]
    assert "?" not in pool._line(by[1], policy_dict())
    assert "?" in pool._line(by[2], policy_dict())


def test_the_shortlist_refuses_over_an_unassessed_top(monkeypatch):
    """Criterion 5. An advisory line does not do what the amendment asks -- a
    session reads it and raises the symptoms anyway."""
    stub_issues(monkeypatch, [
        issue(n, labels=["sev:2", "urg:2"], assessed=False) for n in (1, 2, 3)
    ])
    with pytest.raises(pool.PoolError) as caught:
        pool.cmd_shortlist(policy_dict(), None, None)
    message = str(caught.value)
    assert "#1" in message and "#2" in message and "#3" in message
    assert "--unassessed" in message
    assert "assess <N> --none" in message


def test_the_shortlist_does_not_refuse_when_the_top_is_assessed(monkeypatch, capsys):
    """The lawful polarity: a gate that could not be passed would make the
    shortlist unavailable rather than better."""
    stub_issues(monkeypatch, [
        issue(n, labels=["sev:2", "urg:2"], assessed=True) for n in (1, 2, 3)
    ])
    assert pool.cmd_shortlist(policy_dict(), None, None) == 0
    assert "#1" in capsys.readouterr().out


def test_the_escape_raises_anyway(monkeypatch, capsys):
    stub_issues(monkeypatch, [
        issue(n, labels=["sev:2", "urg:2"], assessed=False) for n in (1, 2, 3)
    ])
    assert pool.cmd_shortlist(policy_dict(), None, None, unassessed=True) == 0
    assert "#1" in capsys.readouterr().out


def test_the_gate_looks_at_least_as_deep_as_count_asks(monkeypatch):
    """`--count` cannot outrun the gate by raising past the policy's depth."""
    policy = policy_dict(assessment={"before_shortlist": 1, "per_cycle": 3})
    stub_issues(monkeypatch, [
        issue(1, labels=["sev:3", "urg:3"], assessed=True),
        issue(2, labels=["sev:2", "urg:2"], assessed=False),
    ])
    with pytest.raises(pool.PoolError) as caught:
        pool.cmd_shortlist(policy, None, 2)
    assert "#2" in str(caught.value)


def test_assess_writes_the_policys_label_and_nothing_else(monkeypatch, capsys):
    sent = []
    monkeypatch.setattr(pool, "gh", lambda args: sent.append(args) or "")
    pool.cmd_assess(policy_dict(), None, 7)
    assert sent[0][sent[0].index("--add-label") + 1] == "assessed:no-cause"
    assert "--remove-label" not in sent[0]


def test_assess_is_admitted_by_the_rail(monkeypatch):
    """The one write stage two adds would otherwise be refused by the guard
    stage one built, which is why `writable_labels` had to widen."""
    assert "assessed:no-cause" in pool.writable_labels(policy_dict())


# --------------------------------------------------------------------- cycle


def test_the_cycle_bounds_what_it_names_to_assess(monkeypatch, capsys):
    """Criterion 6: the backlog is worked through at a stated rate rather than
    all at once."""
    stub_issues(monkeypatch, [
        issue(n, labels=["sev:2", "urg:2"], assessed=False) for n in range(1, 21)
    ])
    pool.cmd_cycle(policy_dict(), None)
    out = capsys.readouterr().out
    section = out.split("next to assess")[1]
    named = [line for line in section.splitlines() if line.strip().startswith("#")]
    assert len(named) == 3, "the test policy's per_cycle"
    assert "3 of 20 never asked" in out


def test_the_cycle_closes_nothing_where_the_policy_says_so(monkeypatch, capsys):
    """Criterion 7, the default polarity."""
    sent = []

    def wire(args):
        if args[:2] == ["issue", "list"]:
            return json.dumps([issue(1, labels=["sev:2", "urg:1"], updated=ago(400))])
        sent.append(args)
        return ""

    monkeypatch.setattr(pool, "gh", wire)
    monkeypatch.setattr(pool, "causal_parents", lambda policy, repo=None: {})
    pool.cmd_cycle(policy_dict(), None)
    out = capsys.readouterr().out
    assert "at the floor" in out and "#1" in out
    assert "fade.closes is false" in out
    assert sent == [], f"nothing may be written: {sent}"


def test_the_cycle_closes_at_the_floor_where_a_repository_turned_it_on(monkeypatch, capsys):
    """Criterion 7's other polarity. The brief agreed the close; the switch is a
    condition on when, not a licence never to build it."""
    sent = []

    def wire(args):
        if args[:2] == ["issue", "list"]:
            return json.dumps([issue(1, labels=["sev:2", "urg:1"], updated=ago(400))])
        sent.append(args)
        return ""

    monkeypatch.setattr(pool, "gh", wire)
    monkeypatch.setattr(pool, "causal_parents", lambda policy, repo=None: {})
    pool.cmd_cycle(policy_dict(fade={"quiet_days": 30, "closes": True}), None)
    assert len(sent) == 1, sent
    assert sent[0][:2] == ["issue", "close"]
    assert sent[0][sent[0].index("--reason") + 1] == "not planned"
    assert "closing #1 as not planned" in capsys.readouterr().out


def test_the_cycle_closes_nothing_that_has_not_floored(monkeypatch, capsys):
    """Even with the switch on: an item touched today does not close however low
    it is rated, and an item quiet for a window does not close unless the fade
    reached the floor.

    It does **not** say that a low filing is safe: one filed at the floor and
    left quiet does close, which the test below pins.
    """
    sent = []

    def wire(args):
        if args[:2] == ["issue", "list"]:
            return json.dumps([
                issue(1, labels=["sev:2", "urg:1"], updated=ago(0)),
                issue(2, labels=["sev:2", "urg:3"], updated=ago(31)),
            ])
        sent.append(args)
        return ""

    monkeypatch.setattr(pool, "gh", wire)
    monkeypatch.setattr(pool, "causal_parents", lambda policy, repo=None: {})
    pool.cmd_cycle(policy_dict(fade={"quiet_days": 30, "closes": True}), None)
    assert sent == [], "#1 is at the floor but was touched today; #2 is quiet but not floored"


def test_an_item_filed_at_the_floor_and_left_quiet_does_close(monkeypatch):
    """The case the test above claims to exclude and never ran, pinned as it
    actually behaves rather than as its neighbour's docstring described it.

    `at_floor` asks whether the item **is** at the bottom and quiet, not whether
    the fade ever moved it, so a filing somebody deliberately rated lowest closes
    one quiet window after it was filed -- at any severity. Whether that is right
    changes what `fade.closes` means and is the owner's; what is not optional is
    that the suite say which of the two it does.
    """
    sent = []

    def wire(args):
        if args[:2] == ["issue", "list"]:
            return json.dumps([issue(1, labels=["sev:3", "urg:1"], updated=ago(31))])
        sent.append(args)
        return ""

    monkeypatch.setattr(pool, "gh", wire)
    monkeypatch.setattr(pool, "causal_parents", lambda policy, repo=None: {})
    pool.cmd_cycle(policy_dict(fade={"quiet_days": 30, "closes": True}), None)
    assert [a[:3] for a in sent] == [["issue", "close", "1"]], sent


def test_a_dry_run_names_the_closes_and_makes_none(monkeypatch, capsys):
    """The switch is unattended and irreversible-ish, and the list of what it
    would close was readable only by turning it on."""
    sent = []

    def wire(args):
        if args[:2] == ["issue", "list"]:
            return json.dumps([issue(1, labels=["sev:3", "urg:1"], updated=ago(31))])
        sent.append(args)
        return ""

    monkeypatch.setattr(pool, "gh", wire)
    monkeypatch.setattr(pool, "causal_parents", lambda policy, repo=None: {})
    pool.cmd_cycle(policy_dict(fade={"quiet_days": 30, "closes": True}), None, dry_run=True)
    assert sent == [], sent
    assert "would close #1" in capsys.readouterr().out


# -------------------------------------------------------------- the policy


@pytest.mark.parametrize("mutate, because", [
    (lambda p: p.pop("cause"), "no cause label"),
    (lambda p: p.pop("assessed"), "no assessed label"),
    (lambda p: p.pop("accrual"), "no accrual block"),
    (lambda p: p.pop("fade"), "no fade block"),
    (lambda p: p.pop("assessment"), "no assessment block"),
    (lambda p: p.update(fade={"quiet_days": 30}), "closes not stated"),
    (lambda p: p.update(fade={"quiet_days": 0, "closes": False}), "a quiet window of zero"),
    (lambda p: p.update(accrual={"symptoms_per_band": 0}), "a band of zero symptoms"),
    (lambda p: p.update(assessment={"before_shortlist": 1, "per_cycle": 0}), "a cycle of zero"),
    (lambda p: p.update(assessed={"label": "framed"}), "the assessed label already in use"),
])
def test_a_policy_missing_stage_twos_fields_is_refused(tmp_path, mutate, because):
    policy = policy_dict()
    mutate(policy)
    path = write_policy(tmp_path / "pool-policy.json", policy)
    with pytest.raises(pool.PoolError):
        pool.load_policy(path)


def test_the_refusal_names_what_an_older_override_must_add(tmp_path):
    """The no-merge rule is stage one's decided shape, so a silent default here
    would hand a repository numbers it never wrote. It gets a migration message
    instead."""
    policy = policy_dict()
    policy.pop("accrual")
    path = write_policy(tmp_path / "pool-policy.json", policy)
    with pytest.raises(pool.PoolError) as caught:
        pool.load_policy(path)
    assert "'accrual'" in str(caught.value)


def test_fade_closes_must_be_stated_rather_than_defaulted(tmp_path):
    """It decides whether anything closes at all, so it is not inferred."""
    path = write_policy(tmp_path / "pool-policy.json",
                        policy_dict(fade={"quiet_days": 30, "closes": "yes"}))
    with pytest.raises(pool.PoolError) as caught:
        pool.load_policy(path)
    assert "true or false" in str(caught.value)


def test_the_shipped_default_carries_every_stage_two_field():
    """The lawful polarity of all of the above."""
    policy = pool.load_policy(pool.DEFAULT_POLICY)
    assert policy["accrual"]["symptoms_per_band"] >= 1
    assert policy["fade"]["closes"] is False, "the fade ships closing nothing"
    assert policy["assessment"]["per_cycle"] >= 1
    assert policy["cause"]["label"] and policy["assessed"]["label"]


def test_a_symptom_linked_under_its_cause_reads_as_assessed(monkeypatch):
    """The third answer, which has no label.

    Not asked, asked and it is its own, asked and here is its cause -- and the
    third's record is the sub-issue link. Read from the label alone, that answer
    read as *not asked*: the gate named the symptom, offered `link it under its
    cause` as its first remedy, and taking that remedy changed nothing the gate
    could see.
    """
    stub_issues(monkeypatch, [
        issue(1, labels=["cause", "sev:2", "urg:2"]),
        issue(2, labels=["sev:3", "urg:3"], assessed=False),
    ], parents={2: 1})
    items, _ = pool.read_pool(policy_dict())
    assert {it["number"]: it["assessed"] for it in items} == {1: True, 2: True}
    # And the gate it exists to clear actually clears.
    pool.cmd_shortlist(policy_dict(), None, None)


def test_an_unlinked_issue_still_blocks_the_gate(monkeypatch):
    """The negative control. Deriving the flag from the link must not disable the
    gate for everything else, or the fix is indistinguishable from deleting it."""
    stub_issues(monkeypatch, [
        issue(1, labels=["cause", "sev:2", "urg:2"]),
        issue(2, labels=["sev:3", "urg:3"], assessed=False),
        issue(3, labels=["sev:1", "urg:1"], assessed=False),
    ], parents={2: 1})
    with pytest.raises(pool.PoolError) as caught:
        pool.cmd_shortlist(policy_dict(), None, None)
    assert "#3" in str(caught.value) and "#2" not in str(caught.value)


def test_a_parent_without_the_cause_label_is_not_an_answer(monkeypatch):
    """The second control: an ordinary task decomposition is not an assessment,
    which is the same rule `causal_parents` applies to the accrual."""
    stub_issues(monkeypatch, [
        issue(1, labels=["sev:2", "urg:2"]),
        issue(2, labels=["sev:3", "urg:3"], assessed=False),
    ], parents={})
    items, _ = pool.read_pool(policy_dict())
    assert {it["number"]: it["assessed"] for it in items} == {1: True, 2: False}


def test_the_floor_and_the_fade_read_the_same_clock(monkeypatch):
    """They did not: `at_floor` re-derived quiet against the wall while judging
    values computed at an injected `now`, so the two disagreed about one item."""
    policy = policy_dict()
    stale = datetime.now(timezone.utc) - timedelta(days=1)
    item = {"number": 1, "title": "t", "ratings": {"severity": "sev:3", "urgency": "urg:3"},
            "clashes": [], "updated_at": stale, "assessed": True, "symptoms": []}
    later = datetime.now(timezone.utc) + timedelta(days=400)
    values = pool.effective(item, policy, now=later)
    assert values["urgency"] == 1, values
    assert pool.at_floor(item, policy, values, now=later)
    # The other polarity on the same item: at the real clock it has not floored.
    assert not pool.at_floor(item, policy, pool.effective(item, policy))


def test_a_gate_depth_of_zero_is_refused_rather_than_silently_ignored(tmp_path):
    """Zero is the value a repository reaches for to switch the gate off, and it
    loaded while `max(len(raised), 0)` discarded it and every shortlist went on
    refusing -- a floor the validator invited and the mechanism did not honour."""
    policy = policy_dict()
    policy["assessment"]["before_shortlist"] = 0
    path = write_policy(tmp_path / "pool-policy.json", policy)
    with pytest.raises(pool.PoolError):
        pool.load_policy(path)


def test_the_floor_header_names_the_axis_that_actually_faded(monkeypatch, capsys):
    """With two axes `order[1]` and `order[-1]` are the same and with three they
    are not, so the header named an axis that had not moved over rows the fade
    had floored on a different one."""
    policy = policy_dict()
    policy["axes"]["effort"] = {"meaning": "how big", "color": "FBCA04",
                                "values": {"eff:1": 1, "eff:2": 2, "eff:3": 3}}
    policy["order"] = ["severity", "urgency", "effort"]
    stub_issues(monkeypatch, [
        issue(1, labels=["sev:3", "urg:1", "eff:3"],
              updated=(datetime.now(timezone.utc) - timedelta(days=95)).isoformat()),
    ])
    pool.cmd_cycle(policy, None)
    out = capsys.readouterr().out
    assert "at the floor of urgency" in out
    assert "at the floor of effort" not in out


def test_cycle_does_not_call_an_unmoved_item_risen(monkeypatch, capsys):
    """Carrying a symptom is not rising, and neither is having moved.

    Below `accrual.symptoms_per_band` the bands are zero and the pair is
    unchanged, so the first spelling listed unmoved items under a heading saying
    what rose. The second tested `effective != _bare`, which is worse in a way
    the first was not: the fade is applied after the accrual, so an item with
    one symptom that has been quiet for a window differs from its bare pair by
    having gone *down* -- and every fixture here carried no `updatedAt`, so
    `quiet_windows` was 0 and no row could reach that case.
    """
    stub_issues(monkeypatch, [
        issue(1, labels=["sev:2", "urg:2"]),   # one symptom: 1 // 2 == 0 bands
        issue(2, labels=["sev:1", "urg:1"]),
        issue(3, labels=["sev:2", "urg:2"]),   # two symptoms: it really rises
        issue(4, labels=["sev:1", "urg:1"]), issue(5, labels=["sev:1", "urg:1"]),
        # One symptom AND quiet: it moved, downwards.
        issue(6, labels=["sev:2", "urg:3"], updated=ago(35)),
        issue(7, labels=["sev:1", "urg:1"]),
    ], parents={2: 1, 4: 3, 5: 3, 7: 6})
    pool.cmd_cycle(policy_dict(), None)
    out = capsys.readouterr().out
    risen = out.split("risen, from the symptoms under them:")[1].split("\n\n")[0]
    assert "#3" in risen, risen
    assert "#1" not in risen, risen
    assert "#6" not in risen, risen


def test_a_timestamp_with_no_offset_does_not_escape_the_refusal_contract(monkeypatch):
    """`PoolError` is documented as printed without a traceback. A stamp with no
    offset parses cleanly and then died at the subtraction with a raw
    `TypeError`, and the `except ValueError` above it reads as covering that."""
    for raw in ("2026-01-01T00:00:00", "2026-01-01"):
        item = {"number": 1, "title": "t", "ratings": {}, "clashes": [],
                "updated_at": pool._stamp(raw), "assessed": True, "symptoms": []}
        assert pool.quiet_windows(item, policy_dict()) > 0, raw
    # The lawful polarity: an offset-carrying stamp is unchanged by the repair.
    aware = pool._stamp("2026-01-01T00:00:00Z")
    naive = pool._stamp("2026-01-01T00:00:00")
    assert aware == naive


def test_show_distinguishes_what_list_distinguishes(monkeypatch, capsys):
    """Criterion 4 names `show` in its own falsifier, and the falsifier fired:
    two issues differing only in the assessment read byte-identical here, and a
    faded issue asserted its label as its current value while the row for the
    same issue in `list` carried the arrow."""
    stub_issues(monkeypatch, [
        issue(1, labels=["sev:2", "urg:2"]),
        issue(2, labels=["sev:2", "urg:2"], assessed=False),
        issue(3, labels=["sev:2", "urg:3"], updated=ago(65)),
    ])
    said = {}
    for number in (1, 2, 3):
        pool.cmd_show(policy_dict(), None, number)
        said[number] = capsys.readouterr().out
    assert said[1] != said[2].replace("#2", "#1")
    assert "not assessed" in said[2] and "not assessed" not in said[1]
    assert "reads as 1 now" in said[3], said[3]


def test_the_assessment_mark_has_its_own_column(monkeypatch):
    """Appended to the joined cells it sat under no header, hard against the last
    rating where it read as part of that value, and moved the title two columns
    between an assessed row and an unassessed one."""
    stub_issues(monkeypatch, [
        issue(1, labels=["sev:2", "urg:2"]),
        issue(2, labels=["sev:2", "urg:2"], assessed=False),
    ])
    items, _ = pool.read_pool(policy_dict())
    rows = [pool._line(it, policy_dict()) for it in items]
    assert rows[0].index("t") == rows[1].index("t"), rows
    header = pool._header(policy_dict())
    assert "?" in header
    assert header.index("?") == rows[1].index("?")
    # And every other heading sits over its own column, which none of them did:
    # the header padded `issue` to nine against a row prefix of eight.
    for name in policy_dict()["order"]:
        assert header.index(name) == rows[0].index("sev:" if name == "severity" else "urg:")


def test_a_two_digit_band_still_fits_its_column():
    """`len(v) + 2` reserved for `>N` and a policy with a band above nine renders
    `urg:10>10`, one column past its header."""
    policy = policy_dict()
    policy["axes"]["urgency"]["values"] = {f"urg:{i}": i for i in range(1, 11)}
    width = _widths_of(policy)[1]
    assert width >= len("urg:10>10"), width


def _widths_of(policy):
    return pool._widths(policy)


def test_the_causation_read_passes_its_cursor_as_a_variable(monkeypatch):
    """Interpolated into the query string, the server's own `endCursor` became
    part of the query this script sends. `_graphql` already passes variables over
    `-f` and explains why; the cursor goes the same way, and a `None` is left out
    rather than sent as the four characters `None`."""
    sent = []

    def wire(args):
        sent.append(args)
        page = len([a for a in sent if a[:2] == ["api", "graphql"]])
        return json.dumps({"data": {"repository": {"issues": {
            "pageInfo": {"hasNextPage": page == 1, "endCursor": "CUR"},
            "nodes": [],
        }}}})

    monkeypatch.setattr(pool, "gh", wire)
    pool.causal_parents(policy_dict(), "o/r")
    queries = [a for a in sent if a[:2] == ["api", "graphql"]]
    assert len(queries) == 2, queries
    assert all("CUR" not in a[3] for a in queries), "the cursor is in the query string"
    assert "after=None" not in " ".join(queries[0]), "a null cursor was sent as a string"
    assert ["-f", "after=CUR"] == queries[1][-2:], queries[1]


def test_the_causation_read_is_bounded(monkeypatch):
    """It looped forever on a `hasNextPage` that never goes false, where the
    issue read beside it refuses at a limit. A hang says less than a refusal."""
    def wire(args):
        return json.dumps({"data": {"repository": {"issues": {
            "pageInfo": {"hasNextPage": True, "endCursor": "CUR"},
            "nodes": [],
        }}}})

    monkeypatch.setattr(pool, "gh", wire)
    with pytest.raises(pool.PoolError) as caught:
        pool.causal_parents(policy_dict(), "o/r")
    assert str(pool.PAGE_LIMIT) in str(caught.value)


def test_outside_a_checkout_the_first_command_names_its_own_problem(monkeypatch, tmp_path):
    """`_infer_repo` had the right sentence and it fired only on the causation
    read. The first command anyone runs is `list`, which reaches the wire
    directly, so what came back was git's own message -- `failed to run git:
    fatal: not a git repository` -- naming neither this script's problem nor its
    remedy, and a consumer had to read the source to recover."""
    monkeypatch.chdir(tmp_path)
    assert not pool._in_checkout()
    with pytest.raises(pool.PoolError) as caught:
        pool._repo_args(None)
    assert "--repo OWNER/REPO" in str(caught.value)
    # Both lawful polarities: a named repo needs no checkout, and inside one the
    # inference is left to `gh` as before.
    assert pool._repo_args("o/r") == ["--repo", "o/r"]
    (tmp_path / ".git").mkdir()
    assert pool._repo_args(None) == []


def test_policy_says_the_same_thing_labels_does(monkeypatch, capsys):
    """The two commands disagreed about `cause`: created by one, absent from the
    only line in the other that says which labels this tool touches."""
    policy = policy_dict()
    pool.cmd_policy(policy, pool.DEFAULT_POLICY)
    out = capsys.readouterr().out
    created = out.split("labels it creates:")[1].split("\n")[0]
    for spec in pool.label_specs(policy):
        assert spec[0] in created, spec[0]
    assert policy["cause"]["label"] in created

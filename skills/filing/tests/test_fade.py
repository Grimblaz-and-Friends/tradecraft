"""Quiet pitches close independently of ratings; the wire is always fenced."""
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

CELL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('filing_fade', CELL / 'scripts/pool.py')
pool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pool)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError('unexpected network call')
    monkeypatch.setattr(pool, 'gh', refuse)
    monkeypatch.setattr(pool.subprocess, 'run', refuse)


def policy():
    return pool.load_policy(pool.DEFAULT_POLICY)


def issue(number, *, days=31, labels=(), state='OPEN', updated=None):
    return {'number': number, 'title': f'Pitch {number}', 'state': state,
            'labels': [{'name': label} for label in labels],
            'updatedAt': updated if updated is not None else
            (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()}


def wire(monkeypatch, initial, fresh=None):
    calls = []
    current = {it['number']: it for it in (fresh if fresh is not None else initial)}
    def gh(args):
        calls.append(args)
        if args[:2] == ['issue', 'list']:
            return json.dumps(initial)
        if args[:2] == ['issue', 'view']:
            return json.dumps(current[int(args[2])])
        if args[:2] == ['issue', 'close']:
            return ''
        raise AssertionError(args)
    monkeypatch.setattr(pool, 'gh', gh)
    return calls


def closes(calls):
    return [call for call in calls if call[:2] == ['issue', 'close']]


def test_fade_closes_rated_and_unrated_after_one_window(monkeypatch, capsys):
    calls = wire(monkeypatch, [issue(1), issue(2, labels=['sev:4', 'urg:4']),
                               issue(3, days=29), issue(4, labels=['framed'])])
    assert pool.main(['--repo', 'o/r', 'fade']) == 0
    assert [int(call[2]) for call in closes(calls)] == [2, 1]
    for call in closes(calls):
        assert call[call.index('--reason') + 1] == 'not planned'
        assert '--comment' in call
        assert 'Lapsed:' in call[call.index('--comment') + 1]
    assert '#1 closed as not planned' in capsys.readouterr().out


@pytest.mark.parametrize('fresh', [issue(1, labels=['framed']), issue(1, days=0),
                                   issue(1, state='CLOSED'), issue(1, updated='invalid'),
                                   issue(1, days=-1)])
def test_fade_rechecks_each_candidate_before_closing(monkeypatch, fresh):
    calls = wire(monkeypatch, [issue(1)], [fresh])
    assert pool.main(['--repo', 'o/r', 'fade']) == 0
    assert not closes(calls)
    view = next(call for call in calls if call[:2] == ['issue', 'view'])
    assert view[view.index('--json') + 1] == 'number,title,state,labels,updatedAt'


@pytest.mark.parametrize('stamp', [None, '', 'invalid', '2020-01-01', '2020-01-01T00:00:00', 23])
def test_missing_or_ambiguous_activity_never_licenses_a_close(monkeypatch, capsys, stamp):
    it = issue(1)
    it['updatedAt'] = stamp
    calls = wire(monkeypatch, [it])
    assert pool.main(['--repo', 'o/r', 'fade']) == 0
    assert not closes(calls)
    assert 'unknown activity' in capsys.readouterr().out


def test_exact_window_and_future_clock():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    item = pool._item(issue(1), policy())
    for offset, expected in [(timedelta(days=30), 'due'),
                              (timedelta(days=30, microseconds=-1), 'active'),
                              (timedelta(days=-1), 'future')]:
        item['updated_at'] = now - offset
        assert pool.fade_status(item, policy(), now) == expected


@pytest.mark.parametrize('preview', [True, False])
def test_preview_and_disabled_closing_write_nothing(monkeypatch, preview, capsys):
    p = policy()
    p['fade']['closes'] = preview
    calls = wire(monkeypatch, [issue(1)])
    pool.cmd_fade(p, 'o/r', dry_run=preview)
    assert not closes(calls)
    assert not any(call[:2] == ['issue', 'view'] for call in calls)
    assert 'would close #1' in capsys.readouterr().out


def test_negative_control_detects_an_eligibility_check_that_always_allows(monkeypatch):
    calls = wire(monkeypatch, [issue(1)], [issue(1, labels=['framed'])])
    pool.cmd_fade(policy(), 'o/r')
    assert not closes(calls)
    monkeypatch.setattr(pool, 'fade_status', lambda *args, **kwargs: 'due')
    pool.cmd_fade(policy(), 'o/r')
    assert closes(calls), 'the protected-purchase probe must detect a broken eligibility check'


def test_shortlist_is_ungated_read_only_and_ignores_retired_labels(monkeypatch, capsys):
    calls = wire(monkeypatch, [issue(1, labels=['assessed:no-cause', 'raised']), issue(2)])
    assert pool.main(['--repo', 'o/r', 'shortlist']) == 0
    assert all(call[:2] == ['issue', 'list'] for call in calls)
    out = capsys.readouterr().out
    assert '#1' in out and '#2' in out
    assert 'assess' not in out and 'push' not in out


def test_old_policy_keeps_working_without_using_its_retired_state(tmp_path, capsys):
    p = policy()
    p.update(assessed={'label': 'assessed:no-cause'}, raised={'label': 'raised'},
             assessment=None, accrual=None, push=None, tie_break=['symptoms', 'recent'])
    path = tmp_path / 'policy.json'
    path.write_bytes(json.dumps(p).encode('utf-8'))
    read = pool.load_policy(path)
    assert read['tie_break'] == ['recent']
    assert 'retired and ignored' in capsys.readouterr().err
    names = {name for name, *_ in pool.label_specs(read)}
    assert 'cause' in names
    assert 'raised' not in names and 'assessed:no-cause' not in names
    assert pool.writable_labels(read) == frozenset(
        ['framed', *[label for axis in p['axes'].values() for label in axis['values']]])


@pytest.mark.parametrize('command', ['cycle', 'assess', 'pushed', 'raise', 'unraise'])
def test_retired_commands_refuse_before_reaching_the_wire(command):
    with pytest.raises(SystemExit) as failure:
        pool.main([command])
    assert failure.value.code == 2


def test_ratings_do_not_accrue_or_decay(monkeypatch):
    wire(monkeypatch, [issue(1, days=90, labels=['sev:2', 'urg:3']),
                       issue(2, labels=['sev:2', 'urg:3'])])
    items, _ = pool.read_pool(policy(), 'o/r')
    assert all(pool.rating_values(it, policy()) == {'severity': 2, 'urgency': 3} for it in items)


def test_show_and_list_expose_activity_and_eligibility(monkeypatch, capsys):
    wire(monkeypatch, [issue(1)])
    pool.main(['--repo', 'o/r', 'list'])
    listed = capsys.readouterr().out
    assert 'last activity (UTC)' in listed and 'due' in listed
    pool.main(['--repo', 'o/r', 'show', '1'])
    shown = capsys.readouterr().out
    assert 'last activity:' in shown and 'fade: due' in shown


def test_explicit_repository_and_policy_work_outside_a_checkout(monkeypatch, tmp_path, capsys):
    source = pool.DEFAULT_POLICY
    monkeypatch.chdir(tmp_path)
    calls = wire(monkeypatch, [issue(1)])
    assert pool.main(['--repo', 'other/project', '--policy', str(source), 'fade', '--dry-run']) == 0
    assert calls[0][calls[0].index('--repo') + 1] == 'other/project'
    assert not closes(calls)
    output = capsys.readouterr().out
    assert str(source) in output and 'would close #1' in output

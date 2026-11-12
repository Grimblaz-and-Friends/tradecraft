"""The before-and-after launch comparison (#906 D6; AC-7 to AC-9)."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import launch_bound

HOLDER = "01234567-89ab-cdef-0123-456789abcdef"
OTHER_HOLDER = "89abcdef-0123-4567-89ab-cdef01234567"
OWN = "a" * 32


@pytest.fixture
def machine(tmp_path, monkeypatch):
    home = tmp_path / "home"
    for path in (home / ".tradecraft" / "dispatches", home / ".claude" / "plugins" / "cache" / "p"):
        path.mkdir(parents=True)
    (home / ".tradecraft" / "implementer-vendor").write_bytes(b"claude\n")
    (home / ".claude" / "settings.json").write_bytes(b"{}")
    (home / ".claude" / "CLAUDE.md").write_bytes(b"# rules\n")
    (home / ".claude" / "plugins" / "cache" / "p" / "plugin.json").write_bytes(b"{}")
    (home / ".claude" / "plugins" / "cache" / "p" / ".git").mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    checkouts = {name: tmp_path / name for name in ("main", "holder", "registered", "own")}
    for path in checkouts.values():
        path.mkdir()
        (path / ".git").mkdir()
        (path / "tracked.txt").write_bytes(b"x")
    nested = checkouts["holder"] / "nested"
    nested.mkdir()
    (nested / ".git").write_bytes(b"gitdir: elsewhere\n")
    (nested / "work.txt").write_bytes(b"x")
    monkeypatch.setattr(launch_bound, "main_clone",
                        lambda path: checkouts["main"] if path.is_dir() else None)
    rows = [{"root": str(checkouts["registered"]), "holder_root": str(checkouts["holder"]),
             "repository": "acme/widget", "issue": 5, "active": True,
             "holder_session_id": OTHER_HOLDER},
            {"root": str(checkouts["own"]), "holder_root": str(checkouts["holder"]),
             "repository": "acme/widget", "issue": 6, "active": True, "holder_session_id": HOLDER}]
    registry = home / ".tradecraft" / "implementation-worktrees.json"
    registry.write_text(json.dumps({"schema_version": 1, "worktrees": rows}), encoding="utf-8")
    store = home / ".tradecraft" / "dispatches"
    own_request = tmp_path / "records" / "own.md.request.json"
    own_request.parent.mkdir()
    own_request.write_bytes(b"{}")
    return {"home": home, "store": store, "registry": registry, "rows": rows,
            "own_request": own_request, "plugin": tmp_path / "plugin", **checkouts}


def comparison(machine, holder=HOLDER):
    (machine["plugin"]).mkdir(exist_ok=True)
    value = launch_bound.Comparison(root=machine["own"], env={}, launcher_plugin=machine["plugin"],
                                    own_output=machine["own_request"].with_name("own.md"),
                                    own_request=machine["own_request"], holder_session_id=holder,
                                    dispatch_id=OWN)
    value.take_before(60)
    return value


def stamp(delta=0):
    return (datetime.now(timezone.utc) + timedelta(seconds=delta)).isoformat()


def bundle(machine, name, *, dispatch, root=None, holder=None, work="acme/widget#5",
           opened=-3600, closed=-1800, elapsed=0):
    request = {"schema_version": 2, "dispatch_id": dispatch, "work": work, "stage": "build",
               "root": str(root) if root else None, "holder_session_id": holder,
               "launched_at": stamp(opened)}
    run = {"schema_version": 2, "dispatch_id": dispatch,
           "completed_at": stamp(closed) if closed is not None else None,
           "launcher_process": {"host": "elsewhere", "pid": 1},
           "elapsed_checkpoint_seconds": elapsed}
    (machine["store"] / f"{name}.md.request.json").write_text(json.dumps(request), encoding="utf-8")
    (machine["store"] / f"{name}.md.run.json").write_text(json.dumps(run), encoding="utf-8")
    (machine["store"] / f"{name}.md").write_bytes(b"result")


def changes(result):
    return {(f["item"], Path(f["path"]).name, f["change"]) for f in result["findings"]}


def rewrite_rows(machine, mutate):
    rows = json.loads(machine["registry"].read_bytes())["worktrees"]
    mutate(rows)
    machine["registry"].write_text(json.dumps({"schema_version": 1, "worktrees": rows}), encoding="utf-8")


def test_ac7_every_covered_item_is_found(machine):
    bundle(machine, "done", dispatch="b" * 32)
    before = comparison(machine)
    home = machine["home"]
    (home / ".tradecraft" / "implementer-vendor").write_bytes(b"codex\n")
    (home / ".tradecraft" / "model-rulings.json").write_bytes(b"{}")
    (home / ".claude" / "settings.json").write_bytes(b'{"x": 1}')
    (home / ".claude" / "CLAUDE.md").write_bytes(b"# changed\n")
    (home / ".claude" / "plugins" / "cache" / "p" / "plugin.json").write_bytes(b'{"v": 2}')
    (home / ".claude" / "plugins" / "cache" / "p" / "added.py").write_bytes(b"")
    (machine["store"] / "done.md.run.json").write_bytes(b'{"tampered": true}')
    machine["own_request"].write_bytes(b'{"rewritten": true}')
    (machine["registered"] / "tracked.txt").write_bytes(b"changed")
    (machine["holder"] / "new.txt").write_bytes(b"")
    (machine["main"] / "tracked.txt").unlink()
    rewrite_rows(machine, lambda rows: rows[1].update(active=False))
    result = before.finish(60)
    assert result["status"] == "findings"
    assert {("switch", "implementer-vendor", "modified"), ("rulings", "model-rulings.json", "added"),
            ("claude-settings", "settings.json", "modified"), ("claude-md", "CLAUDE.md", "modified"),
            ("plugins", "plugin.json", "modified"), ("plugins", "added.py", "added"),
            ("dispatch-records", "done.md.run.json", "modified"),
            ("own-request", "own.md.request.json", "modified"),
            ("checkout:" + str(machine["registered"]), "tracked.txt", "modified"),
            ("checkout:" + str(machine["holder"]), "new.txt", "added"),
            ("checkout:" + str(machine["main"]), "tracked.txt", "removed"),
            ("registry", "own", "row-changed")} <= changes(result)
    assert len({f["id"] for f in result["findings"]}) == len(result["findings"])


def test_ac7_deleted_bundle_and_unattributed_other_holder_row_are_findings(machine):
    bundle(machine, "done", dispatch="b" * 32)
    # The other holder's run ended before this run began: its row change is a finding.
    bundle(machine, "theirs", dispatch="c" * 32, root=machine["registered"], holder=OTHER_HOLDER)
    before = comparison(machine)
    for path in machine["store"].glob("done.md*"):
        path.unlink()
    rewrite_rows(machine, lambda rows: rows.pop(0))
    result = before.finish(60)
    assert ("dispatch-records", "done.md.run.json", "removed") in changes(result)
    assert ("registry", "registered", "row-changed") in changes(result)


def test_ac8_concurrent_run_nested_tree_git_and_own_root_are_not_flagged(machine):
    # An overlapping run of the other holder, for that row's work and root.
    # Unfinished, with its last checkpoint after this run's before-snapshot: still live.
    bundle(machine, "live", dispatch="d" * 32, root=machine["registered"], holder=OTHER_HOLDER,
           opened=-60, closed=None, elapsed=3600)
    before = comparison(machine)
    (machine["registered"] / "tracked.txt").write_bytes(b"their edit")
    (machine["holder"] / "nested" / "work.txt").write_bytes(b"builder edit")
    (machine["holder"] / ".git" / "index").write_bytes(b"commit")
    (machine["own"] / "tracked.txt").write_bytes(b"own edit")
    rewrite_rows(machine, lambda rows: rows[0].update(active=False))
    result = before.finish(60)
    assert result["status"] == "clean", result["findings"]
    attributed = {(Path(a["path"]).name, a["to"]["dispatch_id"]) for a in result["attributed"]}
    assert ("tracked.txt", "d" * 32) in attributed and ("registered", "d" * 32) in attributed


def test_ac8_late_starting_run_is_attributed(machine):
    before = comparison(machine)
    bundle(machine, "late", dispatch="e" * 32, root=machine["registered"], holder=OTHER_HOLDER,
           opened=0, closed=None)
    (machine["registered"] / "tracked.txt").write_bytes(b"their edit")
    result = before.finish(60)
    assert result["status"] == "clean" and result["attributed"][0]["to"]["dispatch_id"] == "e" * 32


@pytest.mark.parametrize("case", ["ended-before", "same-holder", "other-work-and-root"])
def test_ac8_each_attribution_has_its_negative(machine, case):
    holder = HOLDER if case == "same-holder" else OTHER_HOLDER
    closed = -1800 if case == "ended-before" else None
    root = machine["holder"] / "elsewhere" if case == "other-work-and-root" else machine["registered"]
    work = "acme/other#9" if case == "other-work-and-root" else "acme/widget#5"
    bundle(machine, "run", dispatch="f" * 32, root=root, holder=holder, work=work, closed=closed)
    rewrite_rows(machine, lambda rows: rows[0].update(holder_session_id=holder))
    before = comparison(machine)
    rewrite_rows(machine, lambda rows: rows[0].update(active=False))
    if case == "ended-before":
        (machine["registered"] / "tracked.txt").write_bytes(b"late edit")
    result = before.finish(60)
    assert ("registry", "registered", "row-changed") in changes(result)
    if case == "ended-before":
        assert ("checkout:" + str(machine["registered"]), "tracked.txt", "modified") in changes(result)


@pytest.mark.parametrize("elapsed, attributed", [(10, False), (3700, True)])
def test_ac8_a_hard_killed_run_is_live_only_up_to_its_last_checkpoint(machine, elapsed, attributed):
    # Launched an hour ago and never completed; its launcher is not active here.
    bundle(machine, "killed", dispatch="e" * 32, root=machine["registered"], holder=OTHER_HOLDER,
           opened=-3600, closed=None, elapsed=elapsed)
    before = comparison(machine)
    (machine["registered"] / "tracked.txt").write_bytes(b"a later edit")
    result = before.finish(60)
    change = ("checkout:" + str(machine["registered"]), "tracked.txt", "modified")
    if attributed:
        assert change not in changes(result)
        assert result["attributed"][0]["to"]["dispatch_id"] == "e" * 32
    else:
        assert change in changes(result) and result["attributed"] == []


def test_ac9_unreadable_and_timed_out_items_are_uncompared(machine, monkeypatch):
    before = comparison(machine)
    machine["registry"].write_bytes(b"not json")
    result = before.finish(0)
    uncompared = {f["item"] for f in result["findings"] if f["change"] == "uncompared"}
    assert "registry" in uncompared
    assert any(item.startswith("checkout:") for item in uncompared)
    assert result["status"] == "findings"
    assert launch_bound.unrecorded("killed")["findings"][0] == {
        "id": "unrecorded", "item": "comparison", "path": "", "change": "unrecorded", "reason": "killed"}


def test_absent_items_are_recorded_without_findings(machine):
    (machine["home"] / ".claude" / "CLAUDE.md").unlink()
    result = comparison(machine).finish(60)
    entry = next(c for c in result["coverage"] if c["item"] == "claude-md")
    assert entry["status"] == "absent" and result["status"] == "clean"


# --- One overlap list and one allowance ---------------------------------------

BEFORE_AT, AFTER_AT = "2026-11-11T10:00:00+00:00", "2026-11-11T11:00:00+00:00"
OTHER, STALE = "b" * 32, "c" * 32


def _store_run(store, name, *, dispatch, root, holder=None, launched="2026-11-11T09:00:00+00:00",
               completed=None):
    store.mkdir(parents=True, exist_ok=True)
    (store / f"{name}.md.request.json").write_text(json.dumps(
        {"dispatch_id": dispatch, "root": str(root), "holder_session_id": holder, "work": "acme/w#1",
         "launched_at": launched}), encoding="utf-8")
    (store / f"{name}.md.run.json").write_text(json.dumps(
        {"completed_at": completed, "elapsed_checkpoint_seconds": 99999}), encoding="utf-8")


def golden(tmp_path):
    """Synthetic before and after states touching every outcome ``compare`` records."""
    tmp = tmp_path.resolve()
    main, store = tmp / "main", tmp / "store"
    own, other, stale = main / "own", main / "other", main / "stale"
    _store_run(store, "other", dispatch=OTHER, root=other, holder=OTHER_HOLDER)
    _store_run(store, "stale", dispatch=STALE, root=stale, launched="2026-11-11T07:00:00+00:00",
               completed="2026-11-11T08:00:00+00:00")
    f1, f2 = ("file", 1, 1), ("file", 2, 2)
    row = {"root": str(other), "repository": "acme/w", "issue": 1, "holder_session_id": OTHER_HOLDER}

    def copy(path, branch, head):
        return {"path": str(path), "head": head, "branch": branch and "refs/heads/" + branch, "flags": []}

    def copies(*values):
        return {launch_bound.path_key(Path(value["path"])): value for value in values}

    a, b = tmp / "a", tmp / "b"
    plan = [{"item": "checkout:" + str(main), "path": str(main), "method": "checkout"},
            {"item": "claude-settings", "path": str(tmp / "settings.json"), "method": "sha256"},
            {"item": "registry", "path": str(tmp / "registry.json"), "method": "registry"},
            {"item": "dispatch-records", "path": str(store), "method": "records"},
            {"item": "refs:a", "path": str(a), "method": launch_bound.REFS_METHOD},
            {"item": "refs:b", "path": str(b), "method": launch_bound.REFS_METHOD}]
    before = {
        plan[0]["item"]: {"status": "compared", "entries": {
            "keep.txt": f1, "loose.txt": f1, "other/x.txt": f1, "own/y.txt": f1, "stale/z.txt": f1}},
        "claude-settings": {"status": "compared", "digest": "1"},
        "registry": {"status": "compared", "digest": "1", "rows": {str(other).casefold(): row}},
        "dispatch-records": {"status": "compared", "bundles": [], "entries": {str(store / "gone.md"): f1}},
        "refs:a": {"status": "compared", "default": "trunk", "default_rule": "origin HEAD",
                   "copies": copies(copy(a, "side", "h1"), copy(own, "feature-own", "h1"),
                                    copy(other, "trunk", "h1")),
                   "branches": {"refs/heads/side": "h1", "refs/heads/feature-own": "h1",
                                "refs/heads/trunk": "h1"}},
        "refs:b": {"status": "compared", "default": "main", "default_rule": "origin HEAD",
                   "copies": copies(copy(b, "main", "h1")), "branches": {"refs/heads/main": "h1"}}}
    after = {
        plan[0]["item"]: {"status": "compared", "entries": {
            "keep.txt": f1, "loose.txt": f2, "other/new.txt": f1, "other/x.txt": f2, "own/new": f1,
            "stale/z.txt": f2}},
        "claude-settings": {"status": "compared", "digest": "2"},
        "registry": {"status": "compared", "digest": "2", "rows": {}},
        "dispatch-records": {"status": "compared", "bundles": [], "entries": {}},
        "refs:a": {"status": "compared", "default": "trunk", "default_rule": "origin HEAD",
                   "copies": copies(copy(a, "side", "h1"), copy(own, "feature-own", "h3"),
                                    copy(other, "trunk", "h2")),
                   "branches": {"refs/heads/side": "h1", "refs/heads/feature-own": "h3",
                                "refs/heads/trunk": "h2"}},
        "refs:b": {"status": "compared", "default": "main", "default_rule": "origin HEAD",
                   "copies": copies(copy(b, "main", "h2")),
                   "branches": {"refs/heads/main": "h2", "refs/heads/feature-x": "h4",
                                "refs/heads/loose": "h5"}}}
    record = tmp / "run.claude.stdout.log"
    record.write_bytes(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "toolu_1", "name": "Bash",
         "input": {"command": "git push origin feature-x"}}]}}).encode() + b"\n")
    return {"plan": plan, "before": before, "after": after, "root": own, "holder_session_id": HOLDER,
            "store": store, "own_dispatch": OWN, "before_at": BEFORE_AT, "after_at": AFTER_AT,
            "elapsed_seconds": 1.0, "record": record, "home": tmp}


def normalized(result, tmp_path):
    """The result with run-specific values replaced, findings and listed keyed by content."""
    for kind in ("findings", "listed"):
        values = result[kind]
        assert [value["id"] for value in values] == sorted(value["id"] for value in values)
        for value in values:
            assert value["id"] == launch_bound._finding_id(value["item"], value["path"], value["change"])
    text = json.dumps({k: v for k, v in result.items() if k != "elapsed_seconds"}, sort_keys=True)
    text = text.replace(json.dumps(str(tmp_path.resolve()))[1:-1], "<tmp>").replace("\\\\", "/")
    value = json.loads(text)
    for kind in ("findings", "listed"):
        for entry in value[kind]:
            entry.pop("id")
        value[kind].sort(key=lambda entry: json.dumps(entry, sort_keys=True))
    return value


# What ``compare`` recorded for ``golden`` before its crediting was restructured, kept literal so
# the restructured ``compare`` is held to the earlier one's result, not to its own.
GOLDEN = {'after_at': '2026-11-11T11:00:00+00:00',
          'attributed': [{'change': 'added',
                          'item': 'checkout:<tmp>/main',
                          'path': '<tmp>/main/other/new.txt',
                          'to': {'dispatch_id': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'holder_session_id': None}},
                         {'change': 'modified',
                          'item': 'checkout:<tmp>/main',
                          'path': '<tmp>/main/other/x.txt',
                          'to': {'dispatch_id': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'holder_session_id': None}},
                         {'change': 'row-changed',
                          'item': 'registry',
                          'path': '<tmp>/main/other',
                          'to': {'dispatch_id': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
                                 'holder_session_id': '89abcdef-0123-4567-89ab-cdef01234567'}},
                         {'change': 'moved',
                          'item': 'refs:a',
                          'path': '<tmp>/main/other',
                          'to': {'dispatch_id': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'holder_session_id': None}},
                         {'change': 'moved',
                          'item': 'refs:a',
                          'path': 'refs/heads/trunk',
                          'to': {'dispatch_id': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'holder_session_id': None}}],
          'before_at': '2026-11-11T10:00:00+00:00',
          'coverage': [{'item': 'checkout:<tmp>/main', 'reason': None, 'status': 'compared'},
                       {'item': 'claude-settings', 'reason': None, 'status': 'compared'},
                       {'item': 'registry', 'reason': None, 'status': 'compared'},
                       {'item': 'dispatch-records', 'reason': None, 'status': 'compared'},
                       {'default_branch': 'trunk',
                        'default_rule': 'origin HEAD',
                        'item': 'refs:a',
                        'reason': None,
                        'status': 'compared'},
                       {'default_branch': 'main',
                        'default_rule': 'origin HEAD',
                        'item': 'refs:b',
                        'reason': None,
                        'status': 'compared'}],
          'findings': [{'branch': 'feature-x',
                        'change': 'added',
                        'checked_out_at': None,
                        'item': 'refs:b',
                        'kind': 'branch',
                        'path': 'refs/heads/feature-x',
                        'reason': "named in the run's record: Bash call toolu_1",
                        'tip_after': 'h4',
                        'tip_before': None},
                       {'change': 'modified',
                        'item': 'checkout:<tmp>/main',
                        'path': '<tmp>/main/loose.txt',
                        'reason': None},
                       {'change': 'modified',
                        'item': 'checkout:<tmp>/main',
                        'path': '<tmp>/main/stale/z.txt',
                        'reason': None},
                       {'change': 'modified',
                        'item': 'claude-settings',
                        'path': '<tmp>/settings.json',
                        'reason': None},
                       {'change': 'removed',
                        'item': 'dispatch-records',
                        'path': '<tmp>/store/gone.md',
                        'reason': None}],
          'listed': [{'branch': 'loose',
                      'change': 'added',
                      'checked_out_at': None,
                      'item': 'refs:b',
                      'kind': 'branch',
                      'path': 'refs/heads/loose',
                      'reason': "not named in the run's record",
                      'tip_after': 'h5',
                      'tip_before': None},
                     {'branch_after': 'main',
                      'branch_before': 'main',
                      'change': 'moved',
                      'folded_branch': {'branch': 'main',
                                        'change': 'moved',
                                        'tip_after': 'h2',
                                        'tip_before': 'h1'},
                      'item': 'refs:b',
                      'kind': 'working-copy',
                      'path': '<tmp>/b',
                      'reason': 'default branch',
                      'tip_after': 'h2',
                      'tip_before': 'h1'}],
          'record_lines_skipped': 0,
          'run_record': {'path': '<tmp>/run.claude.stdout.log', 'reason': None, 'status': 'read'},
          'schema_version': 1,
          'status': 'findings'}


@pytest.mark.parametrize("end", [None, "distant"])
def test_984_ac4_in_time_the_comparison_records_what_it_recorded_before(tmp_path, end):
    kwargs = golden(tmp_path)
    if end == "distant":
        import time
        kwargs.update(end=time.monotonic() + 3600, allowance="3600.0s, the comparison's own limit")
    assert normalized(launch_bound.compare(**kwargs), tmp_path) == GOLDEN


def _paths(tmp_path, count, runs=3):
    """``count`` changed paths outside the run's root, and ``runs`` unfinished runs in the store."""
    tmp = tmp_path.resolve()
    store = tmp / "store"
    for index in range(runs):
        _store_run(store, f"r{index}", dispatch=f"{index:032x}", root=tmp / f"elsewhere-{index}")
    item = "checkout:" + str(tmp / "main")
    plan = [{"item": item, "path": str(tmp / "main"), "method": "checkout"}]
    after = {item: {"status": "compared", "entries": {f"d/f{i}.txt": ("file", 1, 1) for i in range(count)}}}
    return {"plan": plan, "before": {item: {"status": "compared", "entries": {}}}, "after": after,
            "root": tmp / "main" / "own", "holder_session_id": HOLDER, "store": store,
            "own_dispatch": OWN, "before_at": BEFORE_AT, "after_at": AFTER_AT, "elapsed_seconds": 0.0}


def test_984_ac2_other_runs_processes_are_read_as_often_for_1000_paths_as_for_one(tmp_path, monkeypatch):
    counts = []
    liveness = launch_bound.lifecycle.liveness
    for count in (1, 1000):
        calls = []
        monkeypatch.setattr(launch_bound.lifecycle, "liveness", lambda run: calls.append(1) or liveness(run))
        result = launch_bound.compare(**_paths(tmp_path / str(count), count))
        assert len(result["findings"]) == count
        counts.append(len(calls))
    assert counts[0] == counts[1] > 0


def test_984_ac3_two_overlapping_runs_are_each_credited_their_own_changes(tmp_path):
    tmp = tmp_path.resolve()
    main, store = tmp / "main", tmp / "store"
    _store_run(store, "one", dispatch=OTHER, root=main / "one")
    _store_run(store, "two", dispatch=STALE, root=main / "two")
    item = "checkout:" + str(main)
    entries = {"one/a.txt": ("file", 1, 1), "two/b.txt": ("file", 1, 1), "three.txt": ("file", 1, 1)}
    result = launch_bound.compare(
        [{"item": item, "path": str(main), "method": "checkout"}],
        {item: {"status": "compared", "entries": {}}}, {item: {"status": "compared", "entries": entries}},
        root=main / "own", holder_session_id=HOLDER, store=store, own_dispatch=OWN,
        before_at=BEFORE_AT, after_at=AFTER_AT, elapsed_seconds=0.0)
    assert result["attributed"] == [
        {"item": item, "path": str(main / "one" / "a.txt"), "change": "added",
         "to": {"dispatch_id": OTHER, "holder_session_id": None}},
        {"item": item, "path": str(main / "two" / "b.txt"), "change": "added",
         "to": {"dispatch_id": STALE, "holder_session_id": None}}]
    assert [(f["path"], f["change"]) for f in result["findings"]] == [(str(main / "three.txt"), "added")]


def _clock(monkeypatch, start=1000.0):
    clock = [start]
    monkeypatch.setattr(launch_bound.time, "monotonic", lambda: clock[0])
    return clock


def _uncompared(result):
    return {entry["item"]: entry["reason"] for entry in result["coverage"] if entry["status"] == "uncompared"}


def test_984_a_store_read_that_runs_out_marks_what_it_could_not_examine(tmp_path, monkeypatch):
    clock = _clock(monkeypatch)
    read = launch_bound._recorded_run

    def slow(path, own):
        clock[0] += 20
        return read(path, own)

    monkeypatch.setattr(launch_bound, "_recorded_run", slow)
    kwargs = golden(tmp_path)
    result = launch_bound.compare(**kwargs, end=clock[0] + 10, allowance="10.0s, the comparison's own limit")
    value = normalized(result, tmp_path)
    ran_out = "comparison allowance ran out (10.0s, the comparison's own limit)"
    assert _uncompared(result) == {
        "checkout:" + str(tmp_path.resolve() / "main"): f"{ran_out}: 2 of 6 changes examined",
        "claude-settings": f"{ran_out}: 0 of 1 changes examined",
        "registry": f"{ran_out}: 0 of 1 changes examined",
        "refs:b": f"{ran_out}: 1 of 3 changes examined"}
    # A finding made in memory stays; nothing unexamined is credited or found as itself.
    assert result["attributed"] == []
    assert {(f["item"], f["change"]) for f in value["findings"]} == {
        ("dispatch-records", "removed"), ("checkout:<tmp>/main", "uncompared"),
        ("claude-settings", "uncompared"), ("registry", "uncompared"), ("refs:b", "uncompared")}
    # The default-branch rule still lists, including the move another run would have been credited.
    assert {(e["item"], e["path"], e["reason"]) for e in value["listed"]} == {
        ("refs:a", "<tmp>/main/other", "default branch"), ("refs:b", "<tmp>/b", "default branch")}
    assert result["status"] == "findings"
    assert result["run_record"] == {"path": str(kwargs["record"]), "status": "not-read", "reason": ran_out}


def test_984_a_stream_read_that_runs_out_keeps_the_credits_already_made(tmp_path, monkeypatch):
    clock = _clock(monkeypatch)
    read_bytes = Path.read_bytes
    kwargs = golden(tmp_path)

    def slow(path):
        if path == kwargs["record"]:
            clock[0] += 20
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", slow)
    result = launch_bound.compare(**kwargs, end=clock[0] + 10)
    expected = normalized(launch_bound.compare(**golden(tmp_path / "again")), tmp_path / "again")
    value = normalized(result, tmp_path)
    assert value["attributed"] == expected["attributed"]
    assert _uncompared(result) == {"refs:b": "comparison allowance ran out (10.0s): 1 of 3 changes examined"}
    assert [e["path"] for e in value["listed"]] == ["<tmp>/b"]
    assert [f for f in value["findings"] if f["item"] != "refs:b"] == \
        [f for f in expected["findings"] if f["item"] != "refs:b"]
    assert result["run_record"]["status"] == "not-read"


@pytest.mark.parametrize("scoped", [False, True])
def test_984_ac11_the_allowance_is_two_minutes_unless_the_recording_window_is_nearer(
        machine, monkeypatch, scoped):
    for index in range(300):
        bundle(machine, f"r{index}", dispatch=f"{index:032x}", root=machine["holder"] / f"x{index}",
               closed=None)
    clock = _clock(monkeypatch)
    reads = []
    read_bytes = Path.read_bytes

    def counted(path):
        if path.name.endswith(".request.json") and machine["store"] in path.parents:
            clock[0] += 1
            reads.append(path)
        return read_bytes(path)

    before = comparison(machine)
    (machine["registered"] / "tracked.txt").write_bytes(b"changed")
    monkeypatch.setattr(Path, "read_bytes", counted)
    if scoped:
        deadline = launch_bound.lifecycle.Deadline(100, started=clock[0])
        with launch_bound.lifecycle.deadline_scope(deadline):
            result = before.finish(60)
        seconds, bound = deadline.final_write_at - clock[0] + len(reads), "the launch's recording window"
    else:
        result = before.finish(60)
        seconds, bound = launch_bound.COMPARING_SECONDS, "the comparison's own limit"
    assert seconds <= len(reads) <= seconds + 1
    reason = _uncompared(result)["checkout:" + str(machine["registered"])]
    assert reason == f"comparison allowance ran out ({seconds:.1f}s, {bound}): 0 of 1 changes examined"


def _two_repositories(tmp_path):
    """Two repositories, each with a copy at an overlapping run's root and a branch no run made."""
    tmp = tmp_path.resolve()
    store, plan, before, after = tmp / "store", [], {}, {}
    for name, dispatch in (("a", OTHER), ("b", STALE)):
        other = tmp / f"{name}-other"
        _store_run(store, name, dispatch=dispatch, root=other)
        item = "refs:" + name
        plan.append({"item": item, "path": str(tmp / name), "method": launch_bound.REFS_METHOD})
        copies = {launch_bound.path_key(other): {"path": str(other), "head": "h1",
                                                 "branch": f"refs/heads/run-{name}", "flags": []}}
        state = {"status": "compared", "default": "trunk", "default_rule": "origin HEAD"}
        before[item] = {**state, "copies": copies, "branches": {f"refs/heads/run-{name}": "h1"}}
        after[item] = {**state, "copies": {key: {**copy, "head": "h2"} for key, copy in copies.items()},
                       "branches": {f"refs/heads/run-{name}": "h2", f"refs/heads/loose-{name}": "h3"}}
    record = tmp / "run.log"
    record.write_bytes(b"")
    return {"plan": plan, "before": before, "after": after, "root": tmp / "own", "holder_session_id": HOLDER,
            "store": store, "own_dispatch": OWN, "before_at": BEFORE_AT, "after_at": AFTER_AT,
            "elapsed_seconds": 0.0, "record": record}


@pytest.mark.parametrize("credited", [True, False])
def test_984_the_allowance_is_checked_between_repositories_never_inside_one(tmp_path, monkeypatch, credited):
    clock = _clock(monkeypatch)
    work_out = launch_bound._refs_changes

    def slow(name, first, second, root, live):
        result = work_out(name, first, second, root, live)
        if name == "refs:a" and bool(live) == credited:
            clock[0] += 20  # The allowance ends once this repository is worked out.
        return result

    monkeypatch.setattr(launch_bound, "_refs_changes", slow)
    in_time = launch_bound.compare(**_two_repositories(tmp_path / "in-time"))
    assert {a["item"] for a in in_time["attributed"]} == {"refs:a", "refs:b"}
    result = launch_bound.compare(**_two_repositories(tmp_path), end=clock[0] + 10)
    reasons = {e["item"]: e["reason"] for e in result["coverage"] if e["status"] == "uncompared"}
    ran_out = "comparison allowance ran out (10.0s)"
    if credited:
        # The first repository's credits stay; the second's creditable copy is not credited.
        assert {(a["item"], a["to"]["dispatch_id"]) for a in result["attributed"]} == {("refs:a", OTHER)}
        assert reasons == {"refs:a": f"{ran_out}: 2 of 3 changes examined",
                           "refs:b": f"{ran_out}: 0 of 2 changes examined"}
    else:
        # A repository never reached still stays in the record.
        assert result["attributed"] == []
        assert reasons == {"refs:a": f"{ran_out}: 0 of 2 changes examined",
                           "refs:b": f"{ran_out}: its working copies and branches were not worked out"}
    assert {f["item"] for f in result["findings"] if f["change"] == "uncompared"} == {"refs:a", "refs:b"}
    assert result["status"] == "findings" and result["run_record"]["status"] == "not-read"

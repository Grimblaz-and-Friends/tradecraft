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

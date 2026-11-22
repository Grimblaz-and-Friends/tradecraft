"""A stretch launch's comparison taken around a stage run in builder mode.

Each builder-mode stage runs whole between the two snapshots, with a stretch request in the store,
and the result is what that launch's comparison would report for what the stage wrote.
Design: lib/DESIGN.md#a-builders-own-checks-and-writes
"""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sys

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))

import launch_bound  # noqa: E402
import work  # noqa: E402

DISPATCH = "a" * 32


@contextmanager
def comparison_window(*, root: Path, tmp_path: Path, checkouts=()):
    """Snapshot before and after the block; ``window["result"]`` holds the comparison.

    ``window["unchanged"]`` is the same comparison without the own-row credit, so a test can
    show what that credit alone absolves: what the stage wrote, held by the
    unchanged rule.

    ``root`` is the stretch's own implementation root. ``checkouts`` are the holder checkouts the
    stage reads, registered so the comparison covers them as a live launch's would.
    """
    home = Path.home()
    store = home / ".tradecraft" / "dispatches"
    own = store / "stretch-window" / "result.md"
    own.parent.mkdir(parents=True, exist_ok=True)
    request = own.with_name("result.md.request.json")
    request.write_text(json.dumps({"schema_version": 2, "work": "o/r#5", "stage": "stretch",
                                   "dispatch_id": DISPATCH, "root": str(root), "vendor": "claude"}),
                       encoding="utf-8")
    registry = launch_bound.registry_path(home)
    if checkouts and not registry.exists():
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps({"schema_version": 1, "worktrees": [
            {"root": str(root), "holder_root": str(checkout), "active": True} for checkout in checkouts]}),
            encoding="utf-8")
    plugin = tmp_path / "window-plugin"
    plugin.mkdir(exist_ok=True)
    plan = launch_bound.coverage_plan(root=root, home=home, env={}, launcher_plugin=plugin,
                                      store=store, own_request=request)
    window = {"plan": plan}
    before_at = launch_bound.now()
    before = launch_bound.snapshot(plan, seconds=60, own_output=own)
    token = work._BUILDER.set({"role": "builder", "dispatch_id": DISPATCH, "session_id": "s",
                               "identity": "declared", "root": str(root), "request": str(request)})
    try:
        yield window
    finally:
        work._BUILDER.reset(token)
    after = launch_bound.snapshot(plan, seconds=60, own_output=own, before=before)
    window["result"] = launch_bound.compare(
        plan, before, after, root=root, holder_session_id=None, store=store, own_dispatch=DISPATCH,
        before_at=before_at, after_at=launch_bound.now(), elapsed_seconds=1.0, own_row_resnapshot=True)
    window["unchanged"] = launch_bound.compare(
        plan, before, after, root=root, holder_session_id=None, store=store, own_dispatch=DISPATCH,
        before_at=before_at, after_at=launch_bound.now(), elapsed_seconds=1.0)

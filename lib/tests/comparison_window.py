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

import dispatch_record as records  # noqa: E402
import launch_bound  # noqa: E402
import launch_tree  # noqa: E402
import run_lifecycle as lifecycle  # noqa: E402
import work  # noqa: E402

DISPATCH = "a" * 32


def stretch_launch(store: Path, *, root: Path, vendor: str = "claude", dispatch_id: str = DISPATCH,
                   work_id: str = "o/r#5", session_id: str = "s") -> dict:
    """A stretch launch's request record and pointer, written by the launcher's own writers.

    A record typed out by hand can agree with the code that reads it and still not be the shape the
    launcher writes, so the builder a test holds is read from these.
    """
    output = Path(store) / f"stretch-{dispatch_id[:8]}" / "result.md"
    pointer = launch_tree.pointer_directory(Path(store)) / f"{dispatch_id}.json"
    if pointer.is_file():
        # A second window in the same home holds the same launch, whose records the launcher writes once.
        return {**json.loads(pointer.read_bytes()), "output": str(output)}
    output.parent.mkdir(parents=True, exist_ok=True)
    request = records.sidecar(output, ".request.json")
    records.write_json(request, records.request_record(
        dispatch_id=dispatch_id, work=work_id, stage="stretch", settings_source="fixture launch",
        settings_scope="this stretch launch", vendor=vendor, model="claude-opus-5-5", effort="xhigh",
        continuity="fresh", permission_boundary="fixture boundary", root=Path(root)))
    pointer = launch_tree.write_pointer(
        Path(store), dispatch_id=dispatch_id, work=work_id, request=request,
        run=records.sidecar(output, ".run.json"), session_id=session_id,
        launcher=lifecycle.process_identity(), root=Path(root))
    return {**json.loads(pointer.read_bytes()), "output": str(output)}


def held_builder(pointer: dict) -> dict:
    """The builder the entrance holds for a stretch launch, as `_builder_identity` makes it from its pointer."""
    return {"role": "builder", "dispatch_id": pointer["dispatch_id"], "session_id": pointer["session_id"],
            "identity": "declared", "root": pointer["root"], "request": pointer["request"],
            "work": pointer["work"]}


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
    launch = stretch_launch(store, root=root)
    own = Path(launch["output"])
    request = Path(launch["request"])
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
    token = work._BUILDER.set(held_builder(launch))
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

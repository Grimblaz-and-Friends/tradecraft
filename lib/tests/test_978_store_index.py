"""The dispatch store index: each record read once per run, with today's results (#978)."""
from collections import Counter
import contextvars
import json
import os
from pathlib import Path
import sys

import pytest

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent))
sys.path.insert(0, str(TESTS))
import change_cost as cost
import cloud_build as cloud
import preflight
import run_lifecycle as lifecycle

# An audit hook cannot be removed, so it counts only while a test holds this list.
_OPENS: list | None = None


def _audit(event, args):
    # Only reads count; a test's own writes of records are not the index's opens.
    if (event == "open" and _OPENS is not None and isinstance(args[0], (str, bytes, os.PathLike))
            and set(str(args[1] or "r")) <= {"r", "b", "t"}):
        name = os.fsdecode(args[0])
        if name.endswith((".request.json", ".run.json")):
            _OPENS.append(str(Path(name).resolve()))


sys.addaudithook(_audit)


@pytest.fixture
def opens():
    global _OPENS
    _OPENS = []
    try:
        yield _OPENS
    finally:
        _OPENS = None


WORKS = ["acme/widget#12", "ACME/widget#12", "acme/widget#13", "other/thing#4"]
STAGES = ["build", "proof", "use", None]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())


def made_up_store(root, count=300):
    """A few hundred bundles across works and stages, with copies, damage and unparsable records."""
    for number in range(count):
        work, stage = WORKS[number % len(WORKS)], STAGES[number % len(STAGES)]
        dispatch = f"d{number % 250}"  # Some dispatch ids are copied into a second bundle.
        request = {"schema_version": 2, "work": work, "dispatch_id": dispatch,
                   "launched_at": f"2026-10-{1 + number % 28:02d}T{number % 24:02d}:00:00Z"}
        if stage:
            request["stage"] = stage
        if number % 37 == 0:
            request["launched_at"] = "not a time"
        if number % 41 == 0:
            request["schema_version"] = 1
        run = {"schema_version": 2, "dispatch_id": dispatch}
        if number % 3:
            run["completed_at"] = f"2026-10-{1 + number % 28:02d}T23:00:00Z"
            run["attempts"] = [{"elapsed_seconds": number}]
        stem = root / f"shard-{number % 7}" / f"b{number:04d}"
        write(stem.with_name(stem.name + ".request.json"), request)
        if number % 11 == 0:
            continue  # No run record yet.
        if number % 13 == 0:
            write(stem.with_name(stem.name + ".run.json"), b"{ damaged")
        elif number % 17 == 0:
            write(stem.with_name(stem.name + ".run.json"), [1, 2])
        elif number % 19 == 0:
            write(stem.with_name(stem.name + ".run.json"), {**run, "dispatch_id": "someone-else"})
        else:
            write(stem.with_name(stem.name + ".run.json"), run)
    write(root / "broken" / "x.request.json", b"{ not json")
    write(root / "broken" / "x.run.json", {"schema_version": 2})
    write(root / "broken" / "y.request.json", b"\xff\xfe\x00")
    write(root / "broken" / "z.request.json", [WORKS[0]])
    write(root / "broken" / "orphan.run.json", {"schema_version": 2, "dispatch_id": "orphan"})


QUERIES = [
    ("acme/widget#12", {"build"}, {}),
    ("acme/widget#12", {"build", "proof"}, {"exact_work": True}),
    ("acme/widget#12", {"use"}, {"after": "2026-10-10T00:00:00Z"}),
    ("acme/widget#12", {"proof"}, {"include_missing_stage": True}),
    ("acme/widget#13", {"build", "proof", "use"}, {"include_missing_stage": True, "after": "2026-10-05T00:00:00+00:00"}),
    ("other/thing#4", {"use"}, {"exact_work": True, "include_missing_stage": True}),
    ("nobody/none#1", {"build"}, {}),
]


def answers(store):
    return [lifecycle.launch_bundles(store, work, stages, **options) for work, stages, options in QUERIES]


def test_978_scoped_launch_bundles_equal_unscoped(tmp_path):
    made_up_store(tmp_path)
    assert lifecycle.store_index(tmp_path) is None
    expected = answers(tmp_path)
    assert any(expected) and any(row[3].get("recovery_error") for rows in expected for row in rows)
    with preflight.scope() as opened:
        assert answers(tmp_path) == expected
        assert answers(str(tmp_path)) == expected  # Another spelling shares the index and keeps its own.
        assert opened.current_parts()["markers"] > 0
    assert answers(tmp_path) == expected


def test_978_no_record_opened_twice_in_one_scope(tmp_path, opens):
    made_up_store(tmp_path)
    with preflight.scope():
        for _ in range(3):
            answers(tmp_path)
    counts = Counter(opens)
    assert counts and max(counts.values()) == 1, counts.most_common(3)
    assert sum(1 for name in counts if name.endswith(".request.json")) == len(list(tmp_path.rglob("*.request.json")))


def unscoped(function, *args, **options):
    """The same call with no run open, as a tool that opens no scope makes it."""
    return contextvars.Context().run(function, *args, **options)


def test_978_refresh_rereads_only_new_or_changed_records(tmp_path, opens):
    made_up_store(tmp_path)
    work, stages, options = QUERIES[0]
    with preflight.scope() as opened:
        before = lifecycle.launch_bundles(tmp_path, work, stages, **options)
        changed = tmp_path / "shard-1" / "b0001.request.json"
        value = json.loads(changed.read_bytes())
        changed.write_bytes(json.dumps({**value, "note": "rewritten with another size"}).encode())
        added = tmp_path / "shard-0" / "new.request.json"
        run = added.with_name("new.run.json")
        write(added, {"schema_version": 2, "work": work, "stage": "build", "dispatch_id": "new",
                      "launched_at": "2026-10-30T00:00:00Z"})
        write(run, {"schema_version": 2, "dispatch_id": "new", "completed_at": "2026-10-30T01:00:00Z"})
        del opens[:]
        # Another process's writes are not seen until a refresh.
        assert lifecycle.launch_bundles(tmp_path, work, stages, **options) == before
        assert opens == []
        opened.refresh()
        after = lifecycle.launch_bundles(tmp_path, work, stages, **options)
        assert sorted(opens) == sorted(str(path.resolve()) for path in (changed, added, run))
        assert after == unscoped(lifecycle.launch_bundles, tmp_path, work, stages, **options) != before
        assert [row[3] for row in after if row[2]["dispatch_id"] == "new"] == [
            {"schema_version": 2, "dispatch_id": "new", "completed_at": "2026-10-30T01:00:00Z"}]
        del opens[:]
        # A record the run writes itself is read again once forgotten.
        write(run, {"schema_version": 2, "dispatch_id": "new", "completed_at": "2026-10-30T02:00:00Z"})
        lifecycle.store_index(tmp_path).forget(run)
        again = lifecycle.launch_bundles(tmp_path, work, stages, **options)
        assert opens == [str(run.resolve())]
        assert again == unscoped(lifecycle.launch_bundles, tmp_path, work, stages, **options) != after


def test_978_changing_a_returned_record_changes_nothing_later(tmp_path):
    made_up_store(tmp_path)
    work, stages, options = QUERIES[0]
    with preflight.scope():
        first = lifecycle.launch_bundles(tmp_path, work, stages, **options)
        expected = json.loads(json.dumps(first))
        for _order, _path, request, run in first:
            request["work"] = "changed"
            request.setdefault("stage", "changed")
            run["attempts"] = "changed"
        index = lifecycle.store_index(tmp_path)
        for _path, _raw, value in index.requests():
            if isinstance(value, dict):
                value.clear()
        raw, value = index.run(next(tmp_path.rglob("*.run.json")))
        if isinstance(value, dict):
            value["dispatch_id"] = "changed"
        again = lifecycle.launch_bundles(tmp_path, work, stages, **options)
    assert json.loads(json.dumps(again)) == expected


def test_978_index_lists_in_rglob_order_and_keeps_failures(tmp_path):
    made_up_store(tmp_path, count=40)
    with preflight.scope():
        index = lifecycle.store_index(tmp_path)
        assert [path for path, _raw, _value in index.requests()] == list(tmp_path.rglob("*.request.json"))
        assert index.runs_listing() == list(tmp_path.rglob("*.run.json"))
        found = {path.name: (raw, value) for path, raw, value in index.requests()}
        assert isinstance(found["x.request.json"][1], ValueError) and found["x.request.json"][0] == b"{ not json"
        missing = index.run(tmp_path / "shard-0" / "b0000.run.json")
        assert isinstance(missing[0], OSError) and missing[1] is missing[0]
    assert lifecycle.store_index(tmp_path / "absent") is None


def test_978_cloud_session_attempts_equal_unscoped(tmp_path):
    for number, session in enumerate(["s1", "s2", "s1", "s1"]):
        request = {"cloud": {"session_id": session}, "launched_at": f"2026-10-0{4 - number}T00:00:00Z",
                   "requested": {"continuity": "fresh" if number == 0 else "resume"}}
        write(tmp_path / f"{number}" / "a.request.json", request)
        write(tmp_path / f"{number}" / "a.run.json", {"attempts": [{"number": number}]} if number != 2 else b"{")
    write(tmp_path / "bom" / "a.request.json", b"\xef\xbb\xbf" + json.dumps({"cloud": {"session_id": "s1"}}).encode())
    write(tmp_path / "wide" / "a.request.json", json.dumps({"cloud": {"session_id": "s1"}}).encode("utf-16"))
    expected = {session: cloud.session_attempts(tmp_path, session) for session in ("s1", "s2")}
    assert len(expected["s1"]) == 3 and expected["s1"][0][1] == {"attempts": [{"number": 3}]}
    with preflight.scope():
        assert {session: cloud.session_attempts(tmp_path, session) for session in ("s1", "s2")} == expected


def test_978_change_cost_contexts_equal_unscoped(tmp_path):
    import test_change_cost as fixtures
    inputs = {"repo": "acme/widget", "issue": 12, "dispatch_root": tmp_path / "dispatches",
              "rates_path": tmp_path / "rates.json", "terms_path": tmp_path / "terms.json",
              "gauges_path": tmp_path / "gauges.jsonl", "holder_path": tmp_path / "holder.jsonl"}
    fixtures.write_json(inputs["rates_path"], {"schema_version": 1, "rates": [fixtures.rate()]})
    fixtures.write_bundle(inputs, "target")
    fixtures.write_bundle(inputs, "foreign", work="other/widget#12")
    fixtures.write_bundle(inputs, "gap", completion=b"{")
    request_path, _run, _request = fixtures.write_bundle(inputs, "unattributable", completion=b"")
    request_path.write_bytes(b"{")
    orphan, _run, _request = fixtures.write_bundle(inputs, "orphan", completion=b"")
    orphan.unlink()
    for foreign in (None, []):
        skipped, scoped_skipped = [], []
        expected = cost._contexts(inputs["dispatch_root"], "acme/widget", 12, inputs["holder_path"], skipped,
                                  foreign_requests=foreign)
        scoped_foreign = None if foreign is None else []
        with preflight.scope():
            found = cost._contexts(inputs["dispatch_root"], "acme/widget", 12, inputs["holder_path"],
                                   scoped_skipped, foreign_requests=scoped_foreign)
        assert [(item.usage, item.request, item.position) for item in found] == \
            [(item.usage, item.request, item.position) for item in expected]
        assert scoped_skipped == skipped and scoped_foreign == foreign
    baseline = cost.report(**inputs)
    with preflight.scope():
        assert cost.report(**inputs) == baseline

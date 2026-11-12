import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import preflight


def _sums_to_total(split):
    return abs(sum(split["parts"].values()) - split["total_seconds"]) <= 1


def test_978_innermost_part_wins_and_parts_sum_to_total():
    with preflight.scope() as scope:
        with preflight.part("removals"):
            time.sleep(0.2)
            with preflight.part("markers"):
                time.sleep(0.3)
            time.sleep(0.1)
        split = scope.snapshot("report")
    parts = split["parts"]
    assert 0.25 <= parts["markers_seconds"] < 0.5
    assert 0.25 <= parts["removals_seconds"] < 0.5
    assert split["until"] == "report" and _sums_to_total(split)
    assert set(parts) == {f"{name}_seconds" for name in preflight.PARTS} | {"unattributed_seconds"}


def test_978_no_scope_reads_directly_and_reports_nothing():
    with preflight.part("github"):
        pass
    preflight.note_read(False, "refused")
    assert preflight.current() is None and preflight.snapshot("report") is None


def test_978_handoff_seeds_the_launcher_and_spawn_combines_both_intervals(tmp_path):
    with preflight.scope() as entrance:
        with preflight.part("github"):
            time.sleep(0.2)
        preflight.note_read(False, "job assignment refused")
        path = preflight.write_handoff(tmp_path / "handoff.json")
    seed = preflight.load_handoff(path)
    with preflight.scope(seed=seed) as launcher:
        assert launcher.started == entrance.started and launcher.fallback == 1
        with preflight.part("launch_preparation"):
            time.sleep(0.1)
        record = launcher.snapshot("request-record")
        mark = launcher.mark()
        with preflight.part("vendor"):
            time.sleep(0.2)
        seconds, parts = launcher.since(mark)
    assert record["parts"]["github_seconds"] >= 0.2 and _sums_to_total(record)
    assert parts["vendor_seconds"] >= 0.2 and abs(sum(parts.values()) - seconds) <= 1
    spawn = preflight.combine(record, seconds, parts)
    assert spawn["until"] == "spawn" and _sums_to_total(spawn)
    assert abs(spawn["total_seconds"] - (record["total_seconds"] + seconds)) <= 0.05
    assert spawn["read_route"]["fallback_reasons"] == ["job assignment refused"]
    json.dumps(spawn)


def test_978_a_launcher_called_directly_measures_from_its_own_start(tmp_path):
    assert preflight.load_handoff(None) is None
    assert preflight.load_handoff(tmp_path / "absent.json") is None
    with preflight.scope(seed=None) as launcher:
        assert time.monotonic() - launcher.started < 1

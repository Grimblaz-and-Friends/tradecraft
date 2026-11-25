"""The route fixture's `watch-` scenarios: a stand-in builder, the holder's wait on it, and the decision meanwhile.

All seven run at once from one exported copy of lib/, since each spends most of its time waiting on its stand-in.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import builder_wait  # noqa: E402
import route_fixture  # noqa: E402

WATCH = sorted(name for name in route_fixture.SCENARIOS if name.startswith("watch-"))
ENDS = {"watch-ready": "the builder's run ended: completed, success",
        "watch-stopped": "the builder's run ended: completed, failed",
        "watch-limit": "the builder's run ended: completed, interrupted, ceiling",
        "watch-crash": "the builder's launch ended without completing its record",
        "watch-replay": "the builder's run ended: completed, success"}


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    """Each scenario's output, from lib/ alone copied outside every registered worktree."""
    export = tmp_path_factory.mktemp("export")
    root = export / "lib"
    shutil.copytree(LIB, root, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    started = {name: subprocess.Popen([sys.executable, "-B", str(root / "tests" / "route_fixture.py"), name],
                                      stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      cwd=str(export))
               for name in WATCH}
    done = {}
    for name, process in started.items():
        out, err = process.communicate(timeout=240)
        done[name] = (process.returncode, out.decode("utf-8"), err.decode("utf-8", "replace"))
    return done


def test_the_list_names_the_seven_watch_scenarios():
    assert WATCH == ["watch-crash", "watch-hand", "watch-limit", "watch-none", "watch-ready", "watch-replay",
                     "watch-stopped"]


def lines(out: str, prefix: str) -> list[str]:
    return [line[len(prefix):] for line in out.splitlines() if line.startswith(prefix)]


def decision(out: str) -> dict:
    [report] = [json.loads(line) for line in out.splitlines() if line.startswith('{"')]
    return report


def clock(text: str) -> datetime:
    return datetime.strptime(text, "%H:%M:%S")


@pytest.mark.parametrize("name", sorted(route_fixture.WATCHED))
def test_a_watched_builder_is_read_as_its_records_say_and_the_wait_ends_with_it(runs, name):
    code, out, err = runs[name]
    assert code == 0, err
    waited = lines(out, "wait| ")
    assert waited[0].split(" ", 1)[1].startswith("builder for o/r#5: running ")
    assert waited[-1].split(" ", 1)[1].startswith(ENDS[name])
    # The decision taken while the stand-in ran agrees with the stand-in's own records at that moment.
    report = decision(out)
    detail = json.loads(report["detail"])
    assert (report["stage"], report["reason"]) == ("with-builder", "builder-live")
    block = []
    for line in out.split("--- the stand-in's own records at that moment ---\n", 1)[1].splitlines():
        if line.startswith(("wait| ", "---")):
            break
        block.append(line)
    records = json.loads("\n".join(block))
    assert detail["started_at"] == records["run"]["launched_at"]
    assert detail["limit_seconds"] == records["request_limit_seconds"] == route_fixture.WATCH_LIMIT
    assert abs(detail["running_seconds"] - records["run"]["elapsed_checkpoint_seconds"]) < 60
    # The decision names the very command the scenario started the wait with.
    assert detail["wait"] == out.split("the wait, started as the handed-off report prints it: ", 1)[1].split(" ---")[0]
    if name != "watch-replay":
        assert detail["steps"] == 7 and detail["last_step"] == "Bash: Run the job's tests a second time"
        assert detail["quiet_seconds"] < 60
    # The wait ended no earlier than its builder, and within a minute after it.
    ended = out.rsplit("--- the stand-in builder ended at ", 1)[1].split(" ---", 1)[0]
    builder, wait = ended.split("; the wait ended at ")
    gap = clock(wait.split(",")[0]) - clock(builder)
    assert timedelta(0) <= gap % timedelta(days=1) <= timedelta(minutes=1)


def test_the_replayed_log_is_printed_step_by_step_in_order(runs):
    _code, out, _err = runs["watch-replay"]
    printed = [line.split(" ", 1)[1] for line in lines(out, "wait| ")
               if line.split(" ", 1)[1].startswith(("step: ", "helper step: ", "earlier step: "))]
    expected = []
    for raw in (LIB / "tests" / route_fixture.REPLAY_LOG).read_bytes().splitlines():
        record = json.loads(raw)
        for block in (record.get("message") or {}).get("content") or []:
            if record.get("type") == "assistant" and block.get("type") == "tool_use":
                helper = record.get("parent_tool_use_id") is not None
                expected.append(("helper step: " if helper else "step: ")
                                + f"{block['name']}: {builder_wait._what(block['input'])}")
    # The last steps already in the log when the wait started are its earlier lines; every later one follows in order.
    later = [line for line in printed if not line.startswith("earlier step: ")]
    earlier = [line.split(": ", 1)[1] for line in printed if line.startswith("earlier step: ")]
    assert later and later == expected[len(expected) - len(later):]
    before = [line.split(": ", 1)[1] for line in expected[:len(expected) - len(later)]]
    assert earlier == before[len(before) - len(earlier):] and len(earlier) == min(3, len(before))


def test_a_builder_started_by_hand_is_not_measured_and_not_watched(runs):
    code, out, err = runs["watch-hand"]
    assert code == 0, err
    detail = json.loads(decision(out)["detail"])
    assert detail["measured"] is False and "running_seconds" not in detail
    [said] = lines(out, "wait| ")
    assert said.split(" ", 1)[1].startswith("the builder of o/r#5 was started by hand and isn't watched")


def test_with_no_builder_running_the_wait_says_how_the_last_one_ended(runs):
    code, out, err = runs["watch-none"]
    assert code == 0, err
    [said] = lines(out, "wait| ")
    assert said.split(" ", 1)[1].startswith("no launched builder of o/r#5 is running; its latest builder launch")
    assert said.endswith("completed, success")

"""Claude launch controls and the stream check for work outliving a reply (#887)."""
import json
import math
from pathlib import Path
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import dispatch_lifecycle as lifecycle
import dispatch_seat as seat
import dispatch_implementer as implementer

SESSION = "f0cb89b1-e040-4e6e-919b-4b4e58c717d2"
EXCLUDED = ("Monitor", "ScheduleWakeup", "CronCreate", "Workflow")


def system(subtype, **fields):
    return {"type": "system", "subtype": subtype, **fields}


def result(text="returned", turns=3):
    return {"type": "result", "subtype": "success", "is_error": False, "num_turns": turns,
            "session_id": SESSION, "result": text, "total_cost_usd": 0.1}


def started(task, **fields):
    return system("task_started", task_id=task, **{"is_backgrounded": False, "task_type": "local_bash",
                                                    **fields})


def notified(task, status):
    return system("task_notification", task_id=task, status=status)


def stream(*events):
    return ("\n".join(json.dumps(event) for event in events) + "\n").encode("utf-8")


def resumed_opener():
    """#886's face: a stop notice for the previous session, then an empty zero-turn result."""
    return (notified("old", "stopped"), system("init", session_id=SESSION),
            {**result(""), "num_turns": 0})


def healthy(*prefix):
    return stream(*prefix, system("init", session_id=SESSION), started("fg"), notified("fg", "completed"),
                  {"type": "assistant"}, system("post_turn_summary"), result())


def daemon_face():
    return stream(system("init", session_id=SESSION), started("bg", is_backgrounded=True),
                  started("fg"), notified("fg", "completed"), system("post_turn_summary"), result(),
                  system("task_updated", task_id="bg", patch={"status": "killed"}), notified("bg", "stopped"))


def late_reply_face():
    return stream(*resumed_opener(), system("init", session_id=SESSION), started("fg"),
                  notified("fg", "completed"), system("post_turn_summary"), result("the real return"),
                  system("init", session_id=SESSION), system("post_turn_summary"), result("a late reply"))


def workflow_face(*, summary=True, rewake=False):
    events = [system("init", session_id=SESSION), started("wf", task_type="local_workflow")]
    if summary:
        events.append(system("post_turn_summary"))
    events += [system("task_progress", task_id="wf"),
               system("task_updated", task_id="wf", patch={"status": "completed"}),
               notified("wf", "completed")]
    if not summary:
        # Without a summary the turn ends at the only result, after the start.
        events = events[:2] + [result("RETURNED")] + events[2:]
    else:
        events.append(result("RETURNED"))
    if rewake:
        events += [system("init", session_id=SESSION), result("The workflow has completed.")]
    return stream(*events)


def kinds(check):
    return sorted({cause["kind"] for cause in check["causes"]})


def test_R3_1_resumed_opener_is_not_work_outliving_the_return():
    check = lifecycle.claude_stream_check(healthy(*resumed_opener()))
    assert check["status"] == "clean", check
    assert check["return"]["result"] == "returned"
    assert check["result_lines"] == [3, 9] and check["return_line"] == 9 and check["turn_end_line"] == 8


def test_R3_2_daemon_face_fires_both_task_arms_naming_the_task():
    check = lifecycle.claude_stream_check(daemon_face())
    assert check["status"] == "work_outlived_return"
    assert kinds(check) == ["task_event_after_return", "task_running_at_return"]
    assert {cause["task_id"] for cause in check["causes"]} == {"bg"}
    assert [cause["line"] for cause in check["causes"]] == [7, 8, 2]
    assert check["return_line"] == 6 and check["backgrounded_tasks_observed"] == ["bg"]
    reason = lifecycle.stream_check_reason(check)
    assert "task bg" in reason and "stdout line 6" in reason


def test_R3_3_late_reply_fires_the_further_reply_arm_alone():
    check = lifecycle.claude_stream_check(late_reply_face())
    assert check["status"] == "work_outlived_return"
    assert check["causes"] == [{"kind": "further_reply", "task_id": None, "line": 11}]
    assert check["return_line"] == 8 and check["return"]["result"] == "the real return"


def test_R3_4_healthy_foreground_run_is_clean():
    check = lifecycle.claude_stream_check(healthy())
    assert check["status"] == "clean" and check["causes"] == []
    assert check["backgrounded_tasks_observed"] == []


def test_R3_6_task_still_running_at_the_turn_end_fires_alone():
    check = lifecycle.claude_stream_check(workflow_face())
    assert check["status"] == "work_outlived_return"
    assert check["causes"] == [{"kind": "task_running_at_return", "task_id": "wf", "line": 2}]
    assert check["backgrounded_tasks_observed"] == ["wf"]


def test_R3_6_without_a_summary_the_return_ends_the_turn():
    check = lifecycle.claude_stream_check(workflow_face(summary=False))
    assert kinds(check) == ["task_event_after_return", "task_running_at_return"]


def test_R3_6b_a_task_event_after_the_return_fires_alone():
    check = lifecycle.claude_stream_check(stream(system("init"), system("post_turn_summary"), result(),
                                                 started("new")))
    assert check["causes"] == [{"kind": "task_event_after_return", "task_id": "new", "line": 4}]


def test_R3_6c_full_workflow_face_fires_the_reply_and_running_arms():
    check = lifecycle.claude_stream_check(workflow_face(rewake=True))
    assert kinds(check) == ["further_reply", "task_running_at_return"]


@pytest.mark.parametrize("arm, face", [
    ("further_reply", late_reply_face),
    ("task_event_after_return", lambda: stream(system("init"), result(), started("new"))),
    ("task_running_at_return", workflow_face),
])
def test_R3_6d_each_arm_is_the_only_one_that_catches_its_face(arm, face):
    """Deleting any one arm leaves its face reading clean."""
    check = lifecycle.claude_stream_check(face())
    assert kinds(check) == [arm]


def test_R4_1_an_empty_or_returnless_stream_is_unread_never_clean():
    assert lifecycle.claude_stream_check(b"")["status"] == "unread"
    assert lifecycle.claude_stream_check(b"not json\n")["status"] == "unread"
    opener_only = lifecycle.claude_stream_check(stream(*resumed_opener()))
    assert opener_only["status"] == "unread" and opener_only["return_line"] is None
    assert "return" not in lifecycle.stream_check_record(opener_only)


@pytest.mark.parametrize("allocation", [60, 899.9876, 7063.31])
def test_R2_1_ceiling_follows_the_allocation_and_overrides_the_parent(allocation):
    expected = math.floor(allocation * 1000)
    env = lifecycle.claude_launch_env({"CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "0",
                                       "BASH_MAX_TIMEOUT_MS": "300000", "KEEP": "x"}, allocation)
    assert env == {"CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1", "BASH_MAX_TIMEOUT_MS": str(expected),
                   "KEEP": "x"}
    notice = lifecycle.claude_launch_notice(allocation).decode("utf-8")
    seconds = f"{expected / 1000:.3f}".rstrip("0").rstrip(".")
    assert f"{seconds} seconds ({expected} ms)" in notice and f"up to {expected}." in notice
    controls = lifecycle.claude_launch_controls(allocation, notice.encode(), disallowed=EXCLUDED)
    assert controls["command_ceiling_ms"] == expected and controls["background_tasks"] == "disabled"
    assert controls["disallowed_tools"] == list(EXCLUDED)


def implementer_args(tmp_path, **values):
    args = implementer.parser().parse_args([
        "--dispatch", str(tmp_path / "d"), "--root", str(tmp_path), "--work", "o/r#1",
        "--stage", values.pop("stage", "build"), "--settings-source", "s", "--settings-scope", "s",
        "--vendor", "claude"])
    args.model, args.effort = "claude-opus-5-5", "high"
    for key, value in values.items():
        setattr(args, key, value)
    return args


@pytest.mark.parametrize("stage", ["build", "floor", "review-disposition", "artifact"])
@pytest.mark.parametrize("continuity", ["fresh", "resume", "handover"])
def test_R1_4_every_claude_implementer_command_excludes_all_four_tools(tmp_path, stage, continuity):
    args = implementer_args(tmp_path, stage=stage, launch_settings_path=str(tmp_path / "s.json"),
                            resume=SESSION if continuity == "resume" else None,
                            session_id=SESSION if continuity == "handover" else None)
    command = implementer.build_command(args, ["claude"], tmp_path / "last")
    assert command.count("--disallowedTools=Monitor,ScheduleWakeup,CronCreate,Workflow") == 1
    assert "--disallowedTools" not in command
    assert not any(tool in value.split(",") for value in command for tool in EXCLUDED
                   if not value.startswith("--disallowedTools="))


@pytest.mark.parametrize("capability", ["read", "execute"])
def test_R1_4_seat_tools_lists_name_none_of_the_four(capability, tmp_path):
    command = seat.build_command("claude", ["claude"], tmp_path, tmp_path / "last", "m", "high", capability)
    tools = command[command.index("--tools") + 1].split(",")
    assert tools and not set(tools) & set(EXCLUDED)
    assert command[command.index("--allowedTools") + 1].split(",") == tools

"""The builder's handoff: its owed checks, its sections in order, and its exact bytes."""
from pathlib import Path
import hashlib
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import handoff


BRIEF = "Brief line one.\n\n| Row | Outcome |\n|---|---|\n| 1 | The thing — exactly. |\n"
ARTIFACT = "Plan.\n\nAC1. It holds.\nFresh reader: yes\n\nAC2. Another.\n"
ALLOWANCE = "You may push the branch and comment on the issue and its pull request."
DISPATCH = "0123456789abcdef0123456789abcdef"
HAND = {"tree": "/work/tree", "branch": "tradecraft/7-abc", "store": "/records", "dispatch": DISPATCH}
TITLES = ["Your role", "The affirmed brief", "The settled plan", "The checks you owe",
          "What you may write", "The readiness record", "Where the plan settles nothing", "How to finish"]


def compose(*, mechanical=False, criteria=("AC1",), use_owed=True, floor_owed=False, hand=None,
            notify="holder-7"):
    checks = handoff.owed_checks(criteria=list(criteria), mechanical=mechanical,
                                 use_owed=use_owed, floor_owed=floor_owed)
    return handoff.compose_handoff(
        brief=BRIEF, artifact=None if mechanical else ARTIFACT,
        lane_reason="A rename with nothing left to choose." if mechanical else None,
        checks=checks, allowance=ALLOWANCE, repo="acme/app", issue=7, holder_root="/holder/root",
        plugin_root="/plugin", notify=notify, hand=hand).decode("utf-8")


def headings(text):
    return [line[3:] for line in text.split("\n") if line.startswith("## ")]


def command_lines(text):
    return [line for line in text.split("\n") if line.startswith("python -B ")]


def test_1011_same_bytes_on_repeated_calls_lf_only():
    first = handoff.compose_handoff(
        brief=BRIEF, artifact=ARTIFACT, lane_reason=None,
        checks=handoff.owed_checks(criteria=["AC1"], mechanical=False, use_owed=True, floor_owed=True),
        allowance=ALLOWANCE, repo="acme/app", issue=7, holder_root="/holder/root", plugin_root="/plugin",
        notify="holder-7", hand=HAND)
    second = handoff.compose_handoff(
        brief=BRIEF, artifact=ARTIFACT, lane_reason=None,
        checks=handoff.owed_checks(criteria=["AC1"], mechanical=False, use_owed=True, floor_owed=True),
        allowance=ALLOWANCE, repo="acme/app", issue=7, holder_root="/holder/root", plugin_root="/plugin",
        notify="holder-7", hand=HAND)
    assert isinstance(first, bytes) and first == second
    assert b"\r" not in first and first.endswith(b"\n")
    assert handoff.handoff_digest(first) == hashlib.sha256(first).hexdigest()


def test_1011_sections_in_order_and_role_line():
    text = compose()
    assert headings(text) == TITLES
    assert text.startswith("## Your role\n\n" + handoff.ROLE + "\n")


def test_1011_brief_and_artifact_byte_for_byte_and_allowance_verbatim():
    text = compose()
    assert BRIEF in text and ARTIFACT in text and ALLOWANCE in text
    assert text.index(BRIEF) < text.index(ARTIFACT) < text.index("## The checks you owe")


def test_1011_owed_checks_order_and_shape():
    checks = handoff.owed_checks(criteria=["AC1", "AC3"], mechanical=False, use_owed=True, floor_owed=True)
    assert [check["stage"] for check in checks] == [
        "cold-reader", "acceptance-criterion", "acceptance-criterion", "use", "floor",
        "ready-reviewers", "proof", "reach"]
    assert [check["criterion"] for check in checks[1:3]] == ["AC1", "AC3"]
    assert checks[1]["command"] == ["run", "acceptance-criterion", "--criterion", "AC1"]
    assert checks[3]["command"] == ["run", "use", "--job-from-artifact"]
    assert all(set(check) == {"stage", "criterion", "command"} for check in checks)


def test_1011_one_criterion_command_per_criterion_and_none_otherwise():
    text = compose(criteria=("AC1", "AC2"))
    criterion = [line for line in command_lines(text) if " acceptance-criterion " in line]
    assert len(criterion) == 2
    assert criterion[0].endswith("--criterion AC1") and criterion[1].endswith("--criterion AC2")
    assert not [line for line in command_lines(compose(criteria=())) if " acceptance-criterion " in line]


def test_1011_use_command_only_when_owed():
    assert any(" run use " in line and line.endswith("--job-from-artifact") for line in command_lines(compose()))
    assert not any(" run use " in line for line in command_lines(compose(use_owed=False)))
    assert "--job-from-artifact" not in compose(use_owed=False)


def test_1011_every_command_names_repo_issue_and_holder_root_and_no_session_id():
    for kwargs in ({}, {"mechanical": True}, {"hand": HAND, "floor_owed": True}):
        text = compose(**kwargs)
        assert "--holder-session-id" not in text
        lines = command_lines(text)
        assert lines
        for line in lines:
            assert line.startswith("python -B /plugin/lib/work.py ")
            assert "--repo acme/app --issue 7 --root /holder/root" in line
    lines = command_lines(compose())
    assert lines[0] == "python -B /plugin/lib/work.py run cold-reader --repo acme/app --issue 7 --root /holder/root"
    assert any(line.startswith("python -B /plugin/lib/work.py run catch-up ") for line in lines)
    assert "When the decision orders it" in compose()


def test_1011_mechanical_lane_carries_reason_and_row_form_once_and_no_artifact():
    text = compose(mechanical=True, criteria=("AC1",))
    assert headings(text)[2] == "The mechanical lane"
    assert "A rename with nothing left to choose." in text
    assert ARTIFACT not in text and "--criterion" not in text
    rows = [line for line in command_lines(text) if "--row" in line]
    assert rows == ["python -B /plugin/lib/work.py run acceptance-criterion --repo acme/app --issue 7 "
                    "--root /holder/root --row N"]
    assert "launch each row you map to a fresh reader through this command" in text
    assert "each brief row's mapping" in text


def test_1011_exactly_one_of_artifact_and_lane_reason():
    for artifact, reason in ((None, None), ("plan", "reason")):
        with pytest.raises(ValueError):
            handoff.compose_handoff(brief=BRIEF, artifact=artifact, lane_reason=reason, checks=[],
                                    allowance=ALLOWANCE, repo="acme/app", issue=7, holder_root="/h",
                                    plugin_root="/p", notify=None)


def test_1011_record_contract_and_last_post_after_proof():
    text = compose()
    assert handoff.READINESS_MARKER in text
    record = text[text.index("## The readiness record"):text.index("## Where the plan settles nothing")]
    for field in ("schema_version", "builder", "checks", "findings", "rows", "decisions", "refusals", "stop",
                  "relaunch_of", "usage_log", "disposition", "commit", "reason"):
        assert f'"{field}"' in record
    assert "written when you decline it" in record
    assert "The record is the last thing you post at each ready report, after proof." in record
    finish = text[text.index("## How to finish"):]
    assert "Post proof, then the readiness record at the head you report ready, as the last post." in finish
    assert finish.index("Post proof") < finish.index("readiness record")
    assert "holder session named `holder-7`" in finish and "the owner tells the holder" in finish


def test_1011_record_example_reads_as_a_record():
    import readiness
    head = "a" * 40
    example = handoff.RECORD_EXAMPLE.replace("STARTED_BY", "launch").replace("FULL_COMMIT_SHA", head)
    example = example.replace('"DISPATCH_ID"', f'"{DISPATCH}"')
    readiness.payload(example, "ready")


def test_1011_both_stop_kinds():
    text = compose()
    stop = text[text.index("## Where the plan settles nothing"):text.index("## How to finish")]
    assert "`decisions`" in stop and "brief row" in stop
    assert "`shape` stop only when the brief's Shape is wrong" in stop
    assert "`cannot-launch` stop naming the first such check and why" in stop
    assert "Write no check's instructions, and choose nothing a check reads." in stop


def test_1011_hand_block_only_with_hand():
    plain = compose()
    assert "## Where you work" not in plain and handoff.NO_LAUNCH_BLOCK not in plain
    assert "TRADECRAFT_STRETCH_DISPATCH" not in plain
    text = compose(hand=HAND)
    assert headings(text) == TITLES + ["Where you work"]
    block = text[text.index("## Where you work"):]
    assert "`/work/tree`" in block and "`tradecraft/7-abc`" in block and "`/records`" in block
    assert f"export TRADECRAFT_STRETCH_DISPATCH={DISPATCH}" in block
    assert f"$env:TRADECRAFT_STRETCH_DISPATCH = '{DISPATCH}'" in block
    assert handoff.NO_LAUNCH_BLOCK in block
    assert '"started_by": "hand"' in text and '"started_by": "launch"' in plain


def test_1011_without_notify_the_builder_ends():
    finish = compose(notify=None)
    finish = finish[finish.index("## How to finish"):]
    assert "holder session named" not in finish and "the owner tells the holder" in finish

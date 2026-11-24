"""The builder's handoff: its owed checks, its sections in order, and its exact bytes."""
from pathlib import Path
import hashlib
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import handoff


BRIEF = "Brief line one.\n\n| Row | Outcome |\n|---|---|\n| 1 | The thing - exactly. |\n"
ARTIFACT = "Plan.\n\nAC1. It holds.\nFresh reader: yes\n\nAC2. Another.\n"
ALLOWANCE = "You may push the branch and comment on the issue and its pull request."
DISPATCH = "0123456789abcdef0123456789abcdef"
FLOOR = "npm run lint && npm test -- --ci"
HAND = {"tree": "/work/tree", "branch": "tradecraft/7-abc", "store": "/records", "dispatch": DISPATCH}
TITLES = ["Your role", "The affirmed brief", "The settled plan", "The checks you owe",
          "What you may write", "The readiness record", "Where the plan settles nothing", "How to finish"]


LANE_REASON = "A rename with nothing left to choose."
SEVEN_ROWS = [(number, f"**{number}. Row {number}.**") for number in range(1, 8)]


def compose(*, criteria=("AC1",), use_owed=True, floor_command=None, hand=None, notify="holder-7",
            mechanical=False, rows=SEVEN_ROWS, staged=False):
    checks = handoff.owed_checks(criteria=list(criteria), use_owed=use_owed, floor_command=floor_command,
                                 mechanical=mechanical, rows=rows if mechanical else None)
    return handoff.compose_handoff(
        brief=BRIEF, artifact=None if mechanical else ARTIFACT, lane_reason=LANE_REASON if mechanical else None,
        checks=checks, allowance=ALLOWANCE, repo="acme/app", issue=7, holder_root="/holder/root",
        plugin_root="/plugin", notify=notify, hand=hand, staged=staged).decode("utf-8")


def headings(text):
    return [line[3:] for line in text.split("\n") if line.startswith("## ")]


def command_lines(text):
    return [line for line in text.split("\n") if line.startswith("python -B ")]


def test_1011_same_bytes_on_repeated_calls_lf_only():
    first = handoff.compose_handoff(
        brief=BRIEF, artifact=ARTIFACT,
        checks=handoff.owed_checks(criteria=["AC1"], use_owed=True, floor_command=FLOOR),
        allowance=ALLOWANCE, repo="acme/app", issue=7, holder_root="/holder/root", plugin_root="/plugin",
        notify="holder-7", hand=HAND)
    second = handoff.compose_handoff(
        brief=BRIEF, artifact=ARTIFACT,
        checks=handoff.owed_checks(criteria=["AC1"], use_owed=True, floor_command=FLOOR),
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
    assert "Where it opens with a `status=draft` marker, it is the draft its settlement names" in text


def test_1011_owed_checks_order_and_shape():
    checks = handoff.owed_checks(criteria=["AC1", "AC3"], use_owed=True,
                                 floor_command=FLOOR)
    assert [check["stage"] for check in checks] == [
        "cold-reader", "acceptance-criterion", "acceptance-criterion", "use", "floor", "reach",
        "ready-reviewers", "proof"]
    assert [check["criterion"] for check in checks[1:3]] == ["AC1", "AC3"]
    assert checks[1]["command"] == ["run", "acceptance-criterion", "--criterion", "AC1"]
    assert checks[3]["command"] == ["run", "use", "--job-from-artifact"]
    assert checks[4] == {"stage": "floor", "criterion": None, "row": None, "command": [], "floor_command": FLOOR}
    assert all(set(check) == {"stage", "criterion", "row", "command"} and check["row"] is None
               for check in checks if check["stage"] != "floor")


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
    for kwargs in ({}, {"mechanical": True}, {"hand": HAND, "floor_command": FLOOR}):
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
    assert "post proof, then the readiness record at the head you report ready, as the last post." in finish
    assert finish.index("post proof") < finish.index("readiness record")
    assert "read your record back with the reach" in finish
    assert ("For the floor, `report` is its floor marker comment's id; for reach, your `reach-reading` "
            "comment's id, or null when reach flagged nothing.") in record
    assert "`row`, the brief row the decision would change, or null where it changes none." in record
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
    assert ("`shape` stop only when what the brief's Shape sentence says the change is proves wrong for the "
            "change") in stop
    assert "`cannot-launch` stop naming the first such check and why" in stop
    assert "Write no check's instructions, and choose nothing a check reads." in stop


def test_1011_hand_block_only_with_hand():
    plain = compose()
    assert "## Where you work" not in plain and handoff.NO_LAUNCH_BLOCK not in plain
    assert "export TRADECRAFT_STRETCH_DISPATCH" not in plain
    assert "`dispatch` your launch's dispatch id, which `TRADECRAFT_STRETCH_DISPATCH` in your environment holds" in plain
    text = compose(hand=HAND)
    assert headings(text) == TITLES + ["Where you work"]
    block = text[text.index("## Where you work"):]
    assert "`/work/tree`" in block and "`tradecraft/7-abc`" in block and "`/records`" in block
    assert f"export TRADECRAFT_STRETCH_DISPATCH={DISPATCH}" in block
    assert f"$env:TRADECRAFT_STRETCH_DISPATCH = '{DISPATCH}'" in block
    assert handoff.NO_LAUNCH_BLOCK in block
    assert '"started_by": "hand"' in text and '"started_by": "launch"' in plain


def test_1011_the_closing_line_and_who_posts_the_cold_reading():
    text = compose()
    assert "as a draft from your branch, with `Closes #7` alone on a line" in text
    cold = entry(checks_section(text), "cold-reader")
    assert cold.index("`open`") < cold.index("`status=clean`")
    assert "holds `run use`, `run ready-reviewers` and `run proof` until a `clean` stands at your head" in cold
    assert "staffing_status=STATUS same_vendor_reason=REASON -->" in cold and "status=clean" in cold and "Accepted: path:lines" in cold
    assert "Push your branch and open the draft pull request" in text and "proof are not." in text
    assert "a paragraph beginning `**Path departures:**`" in text and "keep it true up to proof." in text
    assert "Run the floor at the pull request's head." in text
    assert "`own-turn` with `added_by`" in text and "`.tradecraft/work.json` `connected_reviewers`" in text
    assert "Wait for each connected reviewer's review and answer it whole" in text
    assert "any departure from the plan a check required, with what you added" in text
    assert "implementing-pr" not in text and "builder-session" not in text
    assert "`<!-- tradecraft:launch-account:v1 dispatch=DISPATCH_ID -->`" in text and "`none-found`" in text
    assert "the read-only decision lists each report's under `builder_checks`" in text


def test_1011_without_notify_the_builder_ends():
    finish = compose(notify=None)
    finish = finish[finish.index("## How to finish"):]
    assert "holder session named" not in finish and "the owner tells the holder" in finish


def checks_section(text):
    return text[text.index("## The checks you owe"):text.index("## What you may write")]


def entry(section, title):
    """One numbered entry of the checks section, up to the next numbered entry or the catch-up line."""
    entries = re.split(r"\n(?=\d+\. )|\n(?=When the decision orders it)", section)
    [found] = [part for part in entries if re.match(r"\d+\. " + re.escape(title) + ":\n", part)]
    return found


def test_1011_use_line_says_the_entrance_decides_use_at_the_builders_head():
    use = entry(checks_section(compose()), "use")
    assert "settled plan carries a `Use session job` block" in use
    assert "The entrance decides at your head whether use is owed" in use
    assert "changed paths that do not exist at this handoff" in use
    assert "Use session job" not in checks_section(compose(use_owed=False))


def test_reach_is_listed_before_ready_reviewers_and_proof():
    for kwargs in ({}, {"floor_command": FLOOR}):
        stages = [check["stage"] for check in handoff.owed_checks(
            criteria=["AC1"], use_owed=True, floor_command=kwargs.get("floor_command"))]
        assert stages.index("reach") < stages.index("ready-reviewers") < stages.index("proof")
        section = checks_section(compose(**kwargs))
        assert section.index(". reach:") < section.index(". ready-reviewers:") < section.index(". proof:")


def test_1011_reach_entry_names_the_read_only_decision_and_the_reach_reading_form():
    reach = entry(checks_section(compose()), "reach")
    assert "python -B /plugin/lib/work.py --repo acme/app --issue 7 --root /holder/root\n" in reach
    assert "read-only decision; it prints the reach report" in reach
    assert "For every item it flags" in reach
    assert "first line is `<!-- tradecraft:reach-reading:v1 head=FULL_COMMIT_SHA -->`" in reach
    assert "no `holder-reading` companion" in reach
    for field in ("`schema_version` 1", "`turns`", "`dispatch_id`", "`items`", "`path`", "`disposition`",
                  "`basis`", "`superset_settlements`"):
        assert field in reach
    assert " run reach " not in compose()


def test_1011_floor_with_a_command_carries_it_word_for_word():
    floor = entry(checks_section(compose(floor_command=FLOOR)), "floor")
    assert "```text\n" + FLOOR + "\n```" in floor
    assert "Run it word for word" in floor
    assert "`<!-- tradecraft:floor:v1 head=FULL_COMMIT_SHA status=pass -->`" in floor
    assert "then the command alone in its own fenced block, then its exact output after that block" in floor
    assert "declared CI jobs" not in floor and " run floor " not in compose(floor_command=FLOOR)


def test_1011_floor_without_a_command_names_the_ci_jobs_and_the_cannot_launch_stop():
    text = compose(floor_command=None)
    floor = entry(checks_section(text), "floor")
    assert "The declared CI jobs are the floor; the holder supplied no floor command." in floor
    assert "post `status=stopped` with a `cannot-launch` stop naming the floor" in floor
    assert "Never write or pick a floor command yourself." in floor
    assert "```" not in floor and "tradecraft:floor:v1" not in text and " run floor " not in text


# The entrance's composition from an issue's own records.
from types import SimpleNamespace  # noqa: E402

import work  # noqa: E402

ENTRANCE_ARTIFACT = (
    "## Use session job\n\n```text\nUse it.\n```\n\n"
    "## Criteria\n\n"
    "**B1.** Reads the route. *Check:* tests.\n\n```text\nFresh reader: read tree\n```\n\n"
    "**B2.** The doctrine tells it.\nFresh reader: read tree\n\n"
    "```text\n**B9.** An example inside a fence.\nFresh reader: read tree\n```\n\n"
    "**B3.** The handoff text is whole.\nFresh reader: execute consumer tree use\n"
)


def _entrance_state(lane="Review risk: elevated\nReview lane: routine-panel\n", artifact=ENTRANCE_ARTIFACT):
    brief = SimpleNamespace(name="affirmed-brief", body="<!-- tradecraft:affirmed-brief:v1 -->\n\nRows.\n\n" + lane)
    return SimpleNamespace(
        repo="o/r", issue_number=5, pr=None, issue_markers=[brief],
        artifact_phase=SimpleNamespace(settled_artifact=SimpleNamespace(body=artifact, source_id="77"),
                                       source_error=None))


def _entrance_text(state, floor_command="make check", **extra):
    return work.compose_handoff_for(state, branch="tradecraft/5-ab", holder_root=Path("H"),
                                    plugin_root=Path("P"), notify="Start 5", floor_command=floor_command,
                                    **extra)


def test_1011_the_entrance_composes_one_text_from_the_brief_and_the_settled_plan():
    state = _entrance_state()
    assert work.fresh_reader_criteria(ENTRANCE_ARTIFACT) == ["B2", "B3"]
    text = _entrance_text(state)
    assert text == _entrance_text(state)
    decoded = text.decode("utf-8")
    assert state.issue_markers[0].body in decoded and ENTRANCE_ARTIFACT in decoded
    assert "--criterion B2" in decoded and "--criterion B3" in decoded
    assert "--criterion B1" not in decoded and "--criterion B9" not in decoded
    assert "--job-from-artifact" in decoded and "holder-session" not in decoded
    sentence = work.github_allowance.sentence(work.github_allowance.allowance_for(
        "stretch", repository="o/r", branch="tradecraft/5-ab", pull_request=None, issue=5))
    assert sentence in decoded


def test_1011_a_plan_without_a_use_job_owes_no_use_and_an_unsettled_plan_is_refused():
    no_use = ENTRANCE_ARTIFACT.replace("## Use session job\n\n```text\nUse it.\n```\n\n", "")
    assert "--job-from-artifact" not in _entrance_text(_entrance_state(artifact=no_use)).decode("utf-8")
    unsettled = _entrance_state()
    unsettled.artifact_phase.settled_artifact = None
    with pytest.raises(work.BuilderRefused) as refused:
        _entrance_text(unsettled)
    assert refused.value.code == "plan-unsettled"


def test_1011_the_entrance_carries_the_holders_floor_command_or_names_the_ci_jobs():
    state = _entrance_state()
    given = _entrance_text(state).decode("utf-8")
    assert "```text\nmake check\n```" in given and "declared CI jobs" not in given
    none = _entrance_text(state, floor_command=None).decode("utf-8")
    assert "The declared CI jobs are the floor; the holder supplied no floor command." in none
    assert "make check" not in none


# The mechanical lane: the lane's reason in place of the plan, and one reader for every row of the brief.

def test_owed_checks_on_the_mechanical_lane_give_one_row_reader_per_brief_row():
    checks = handoff.owed_checks(criteria=["AC1"], use_owed=False, floor_command=None, mechanical=True,
                                 rows=SEVEN_ROWS)
    readers = [check for check in checks if check["stage"] == "acceptance-criterion"]
    assert [check["row"] for check in readers] == list(range(1, 8))
    assert all(check["criterion"] is None for check in readers)
    assert [check["command"] for check in readers] == [
        ["run", "acceptance-criterion", "--row", str(number)] for number in range(1, 8)]
    # Row numbers alone give the same checks, and a row listed twice is owed once.
    assert handoff.owed_checks(criteria=[], use_owed=False, floor_command=None, mechanical=True,
                               rows=[1, 2, 3, 4, 5, 6, 7, 7]) == checks
    assert not hasattr(handoff, "ROW_PLACEHOLDER")


def test_the_mechanical_handoff_carries_the_lane_reason_every_row_command_and_no_plan_or_use():
    text = compose(mechanical=True, use_owed=False)
    assert headings(text)[2] == "The mechanical lane" and "The settled plan" not in headings(text)
    assert BRIEF in text and LANE_REASON in text and ARTIFACT not in text
    rows = [line for line in command_lines(text) if " acceptance-criterion " in line]
    assert rows == ["python -B /plugin/lib/work.py run acceptance-criterion --repo acme/app --issue 7 "
                    f"--root /holder/root --row {number}" for number in range(1, 8)]
    assert "--criterion" not in text and "--job-from-artifact" not in text
    assert "launch every row through its command; map each row in the record's `rows` to what carries it" in text
    record = text[text.index("## The readiness record"):text.index("## Where the brief settles nothing")]
    assert "a mapping of every row of the brief" in record and "Map every row" in record
    assert "a row check its `row` with `criterion` null" in record
    assert '"criterion": null, "row": 1' in record


def test_exactly_one_of_the_plan_and_the_lane_reason_is_handed_off():
    for artifact, reason in ((None, None), ("plan", "reason")):
        with pytest.raises(ValueError):
            handoff.compose_handoff(brief=BRIEF, artifact=artifact, lane_reason=reason, checks=[],
                                    allowance=ALLOWANCE, repo="acme/app", issue=7, holder_root="/h",
                                    plugin_root="/p", notify=None)


def test_both_record_examples_read_as_records():
    import readiness
    for example in (handoff.RECORD_EXAMPLE, handoff.MECHANICAL_RECORD_EXAMPLE):
        example = example.replace("STARTED_BY", "hand").replace("FULL_COMMIT_SHA", "a" * 40)
        readiness.payload(example.replace('"DISPATCH_ID"', f'"{DISPATCH}"'), "ready")


# The builder's steps: one fixed order, each step's hold, and the reasons the entrance returns tied to them.

def test_the_steps_render_in_their_fixed_order_with_their_holds():
    for kwargs in ({}, {"mechanical": True, "use_owed": False}, {"floor_command": FLOOR, "hand": HAND}):
        section = checks_section(compose(**kwargs))
        titles = re.findall(r"(?m)^(\d+)\. (.+):$", section)
        assert titles == [(str(number), step.title) for number, step in enumerate(handoff.BUILDER_STEPS, 1)]
        assert "The order is fixed wherever a hold names it" in section
        assert "not a fixed sequence" not in section
        for step in handoff.BUILDER_STEPS:
            assert step.sentence in section and (step.hold is None or step.hold in section)
    keys = [step.key for step in handoff.BUILDER_STEPS]
    # The entrance's own order: it reads the floor before the cold reading and the rest of its chain, and names
    # thread resolution only once the floor stands again after a late commit.
    assert keys == ["open-pull-request", "floor", "cold-reader", "criteria", "use", "reach", "ready-reviewers",
                    "answer-reviewers", "floor-again", "resolve-threads", "proof", "readiness-record", "read-back"]
    assert keys.index("use") < keys.index("ready-reviewers") < keys.index("floor-again") < keys.index("proof")
    # A sentence naming the floor by its number names the floor's own place in the table.
    assert keys.index("floor") + 1 == 2 and "as step 2 gives it" in handoff.STEPS["floor-again"].sentence


def test_each_owed_check_sits_under_the_step_that_launches_it():
    section = checks_section(compose(floor_command=FLOOR))
    assert "run cold-reader" in entry(section, "cold-reader")
    assert "--criterion AC1" in entry(section, "acceptance-criterion")
    assert "run use" in entry(section, "use") and FLOOR in entry(section, "floor")
    assert "run ready-reviewers" in entry(section, "ready-reviewers") and "run proof" in entry(section, "proof")
    assert "None is listed for this change." in entry(checks_section(compose(use_owed=False)), "use")


def test_the_resolve_step_names_resolving_each_answered_thread_and_when_it_is_owed():
    answer = entry(checks_section(compose()), "resolve the answered threads")
    assert "```text\n" + handoff.RESOLVE_THREAD_COMMAND + "\n```" in answer
    assert "`reviewer-thread-answered-unresolved`" in answer
    assert "`merge-blocked-unresolved-review-threads`" in answer
    assert "names it once the floor and the cold reading's `clean` both stand at your head" in answer
    # The form is the entrance's own, repeated here because this module imports nothing of the entrance.
    assert handoff.RESOLVE_THREAD_COMMAND == work.RESOLVE_THREAD_COMMAND


def test_the_floor_runs_again_after_a_later_commit_before_proof():
    again = entry(checks_section(compose(floor_command=FLOOR)), "the floor again")
    assert "After any commit made after the floor ran, run the floor again at the new head" in again
    assert "posting its marker" in again and "before you resolve threads or run proof" in again
    assert "The cold reading's `clean` and reach must stand at that new head too before proof" in again
    # On the mechanical lane a late commit makes every row owed again, said at the row step and here.
    section = checks_section(compose(mechanical=True))
    assert handoff.ROW_AGAIN not in again and handoff.ROW_AGAIN in entry(section, "the floor again")
    assert handoff.ROW_AGAIN in entry(section, "acceptance-criterion")


def test_the_stop_rule_and_how_to_finish_say_the_same_about_a_stopped_record():
    text = compose()
    assert "A stopped record is your last post; then finish as \"How to finish\" says." in handoff.STOP.sentence
    finish = text[text.index("## How to finish"):]
    assert "Where you stop, the stopped record is the last post instead." in finish
    assert "whether the record is ready or stopped, send one message to the holder session named `holder-7`" in finish
    assert "and take no further step: the holder resumes you if the change goes on." in finish
    alone = compose(notify=None)
    assert "whether the record is ready or stopped, end and take no further step: the owner tells" in alone


def test_a_reason_meaning_stop_points_at_the_stop_rule_the_text_carries():
    text = compose()
    assert handoff.STOP.sentence in text and handoff.STOP not in handoff.BUILDER_STEPS
    for reason in ("affirmed-brief-marker-absent", "builder-stopped", "cannot-launch"):
        assert handoff.ANSWERS[reason] == "stop"


def test_the_cold_reader_account_is_pasted_as_plain_lines_not_a_blockquote():
    cold = entry(checks_section(compose()), "cold-reader")
    assert ("Paste the report's account whole, as plain lines, not as a blockquote: the entrance matches the "
            "account line for line.") in cold


def test_a_staged_change_opens_without_a_closing_reference_and_posts_the_implementing_marker():
    text = compose(staged=True)
    write = text[text.index("## What you may write"):text.index("## The readiness record")]
    assert "Closes #" not in text and "with no closing reference in its body" in write
    assert "post on issue #7 a comment whose first line is `<!-- tradecraft:implementing-pr:v1 number=NUMBER -->`" in write
    assert "`Closes #7` alone on a line" in compose(staged=False)


def test_every_answered_reason_names_a_step_whose_sentence_the_text_carries():
    texts = [compose(), compose(mechanical=True, use_owed=False), compose(floor_command=FLOOR, staged=True)]
    assert set(handoff.ANSWERS.values()) <= set(handoff.STEPS)
    for reason, key in handoff.ANSWERS.items():
        for text in texts:
            assert handoff.step_sentence(key) in text, reason


def test_the_mechanical_and_staged_texts_are_the_same_bytes_on_every_call():
    for kwargs in ({"mechanical": True, "use_owed": False}, {"staged": True, "hand": HAND}):
        assert compose(**kwargs) == compose(**kwargs)


def test_the_stretch_allowance_says_a_body_file_is_named_outright_and_made_first():
    sentence = work.github_allowance.sentence(work.github_allowance.allowance_for(
        "stretch", repository="o/r", branch="tradecraft/5-ab", pull_request=None, issue=5))
    assert ("write a body file's path out in the command, never as a variable, and create the file in an "
            "earlier command of its own, not in the command that posts it.") in sentence

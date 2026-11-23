"""Compose the one text a holder hands a builder on the builder route, and its digest.

Design: lib/DESIGN.md#the-builder-route
"""
from __future__ import annotations

import hashlib
import shlex


ROLE = "You are this change's builder on the builder route. Carry it from this handoff to ready."
NO_LAUNCH_BLOCK = ("You run under these instructions alone, with no launch block: nothing refuses a write "
                   "outside your change but these instructions.")
READINESS_MARKER = "<!-- tradecraft:readiness:v1 head=SHA status=ready|stopped dispatch=ID -->"
DISPATCH_VARIABLE = "TRADECRAFT_STRETCH_DISPATCH"

# The record's payload, spelled out field by field; lib/readiness.py's payload() is what reads it.
RECORD_EXAMPLE = """```json
{
  "schema_version": 1,
  "builder": {"vendor": "VENDOR", "model": "MODEL", "started_by": "STARTED_BY", "usage_log": null},
  "checks": [
    {"stage": "acceptance-criterion", "criterion": "CRITERION_ID", "row": null,
     "dispatch": "DISPATCH_ID", "head": "FULL_COMMIT_SHA", "report": 1234567890, "relaunch_of": null}
  ],
  "findings": [
    {"report": 1234567890, "finding": "F1", "disposition": "fixed", "commit": "FULL_COMMIT_SHA"},
    {"report": 1234567890, "finding": "F2", "disposition": "declined", "reason": "WHY"}
  ],
  "rows": [],
  "decisions": [],
  "refusals": [],
  "stop": null
}
```"""


def _check(stage: str, criterion: str | None = None, *extra: str) -> dict:
    return {"stage": stage, "criterion": criterion, "command": ["run", stage, *extra]}


def owed_checks(*, criteria: list[str], use_owed: bool, floor_command: str | None) -> list[dict]:
    """The checks the builder owes, reach before the two checks held on it."""
    checks = [_check("cold-reader")]
    checks.extend(_check("acceptance-criterion", criterion, "--criterion", criterion) for criterion in criteria)
    if use_owed:
        checks.append(_check("use", None, "--job-from-artifact"))
    # The holder supplies the floor command once, at the handoff; the builder never writes or picks one.
    checks.append({"stage": "floor", "criterion": None, "command": [], "floor_command": floor_command})
    # No stage runs reach: the read-only decision reports it, and the builder answers it with a reach reading.
    checks.append({"stage": "reach", "criterion": None, "command": []})
    checks.append(_check("ready-reviewers"))
    checks.append(_check("proof"))
    return checks


def _argv(command: list[str], *, repo: str, issue: int, holder_root: str, plugin_root: str) -> list[str]:
    # No holder session id: in builder mode the entrance reads it from the builder's own launch.
    base = ["python", "-B", plugin_root.rstrip("/\\") + "/lib/work.py"]
    common = ["--repo", repo, "--issue", str(issue), "--root", holder_root]
    if command[:1] == ["run"]:
        return base + command[:2] + common + command[2:]
    return base + common + command


def _line(argv: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in argv)


def _block(argv: list[str]) -> list[str]:
    return ["```text", _line(argv), "```"]


def _checks_section(checks, *, repo, issue, holder_root, plugin_root) -> list[str]:
    def argv(command):
        return _argv(command, repo=repo, issue=issue, holder_root=holder_root, plugin_root=plugin_root)

    markers = "`" + plugin_root.rstrip("/\\") + "/skills/work/references/markers.md`"
    lines = ["Run each check through the entrance, from the change's tree. Each command composes its own "
             "dispatch and tree, launches a fresh reader and posts its report; a check's report is what "
             "your record answers.", "",
             "This list is not a fixed sequence, except where a check is held on another: ready-reviewers "
             "and proof are both held on reach, so answer reach before either.", ""]
    for number, check in enumerate(checks, 1):
        stage = check["stage"]
        block = _block(argv(check["command"]))
        if stage == "acceptance-criterion":
            title = "acceptance-criterion " + check["criterion"]
            note = None
        elif stage == "use":
            title = "use"
            # The use rules read the change's paths, which do not exist until the builder has built them.
            note = ("Use is listed because the settled plan carries a `Use session job` block. The "
                    "entrance decides at your head whether use is owed, because the use rules read changed "
                    "paths that do not exist at this handoff.")
        elif stage == "floor" and check["floor_command"] is not None:
            title = "floor"
            block = ["```text", check["floor_command"], "```"]
            note = ("The holder supplied this floor command at the handoff. Run it word for word at the "
                    "head you test and, once it passes there, post an issue or pull-request comment whose "
                    "first line is `<!-- tradecraft:floor:v1 head=FULL_COMMIT_SHA status=pass -->`, with "
                    "`head` the full commit id it ran at, carrying the command and its exact output.")
        elif stage == "floor":
            title = "floor"
            block = []
            note = ("The declared CI jobs are the floor; the holder supplied no floor command. If a builder "
                    "floor then falls due, post `status=stopped` with a `cannot-launch` stop naming the "
                    "floor. Never write or pick a floor command yourself.")
        elif stage == "reach":
            title = "reach"
            note = ("This is the read-only decision; it prints the reach report. For every item it flags, "
                    "post the `reach-reading` comment in the form " + markers + " gives it: an issue comment whose first line is "
                    "`<!-- tradecraft:reach-reading:v1 head=FULL_COMMIT_SHA -->`, with `head` the full "
                    "commit id the reading covers and no `holder-reading` companion, followed by exactly "
                    "one fenced `json` object holding the integer `schema_version` 1, `turns` (each turn's "
                    "`dispatch_id` and its `items`, one per flagged path, each with `path`, `disposition`, "
                    "a nonempty `basis` and that disposition's reference field) and, optionally, "
                    "`superset_settlements`.")
        else:
            title = stage
            note = None if stage != "cold-reader" else (
                "You post the cold reading's `open`, quoting the counting `cold-reader` report, and then its "
                "`clean`, in the `cold-reading` form " + markers + " gives. The entrance holds `run use`, "
                "`run ready-reviewers` and `run proof` until a `clean` stands at your head.")
        lines += [f"{number}. {title}:", ""] + block
        if note:
            lines += ["", note] if block else [note]
        lines.append("")
    lines += [
        "When the decision orders it, bring the branch up to its base with:", "",
        *_block(argv(["run", "catch-up"])), "",
        "Answer every connected reviewer, every finding by itself: each inline thread with a reply that "
        "opens with its bare disposition word (`fixed`, `yours`, `declined`, `duplicate` or `lapsed`, a "
        "declined or lapsed answer keeping its reason after the dash); each body finding in its own "
        "pull-request conversation comment that opens with the disposition word and links the source "
        "review with the finding's full identity as the link text, for example "
        "`fixed - restored the required check; "
        "[cr-comment:v1:IDENTITY](https://github.com/OWNER/REPO/pull/N#pullrequestreview-REVIEW_ID)`; "
        "and each unidentified review as a whole, in its own conversation comment linking that exact "
        "review: `fixed - addressed the review's unaccounted findings; "
        "[unidentified review](https://github.com/OWNER/REPO/pull/N#pullrequestreview-REVIEW_ID)`. "
        "One answer names one source link. Close each reviewer's answers with its "
        "`<!-- tradecraft:connected-reviewer:v1 name=NAME status=complete -->` reply once every comment "
        "from it is answered.", "",
        "After `ready-reviewers`, wait for each connected reviewer's review and answer it whole; then run "
        "proof, then post the readiness record.",
    ]
    return lines


def _record_section(started_by: str) -> list[str]:
    lines = [
        "Report ready, or stopped, with one issue comment whose first line is the marker", "",
        "```text", READINESS_MARKER, "```", "",
        "with `head` the full commit id you report, `status` ready or stopped, and `dispatch` your "
        "launch's dispatch id, which `" + DISPATCH_VARIABLE + "` in your environment holds; and with exactly one fenced json object after it, holding exactly these "
        "fields and no others:", "",
        RECORD_EXAMPLE.replace("STARTED_BY", started_by), "",
        "- `schema_version`: the integer 1.",
        f"- `builder`: your `vendor` and `model`, `started_by` `{started_by}`, and `usage_log`, the path "
        "of your usage log or null.",
        "- `checks`: one entry per check you ran: its `stage` (`use`, `acceptance-criterion`, "
        "`cold-reader`, `floor` or `reach`), its `criterion` id or null (an acceptance-criterion check "
        "always names one), its `row` or null, its `dispatch` id or null, the full commit `head` it read, "
        "its `report` comment id (null for a reach check that flagged nothing), and `relaunch_of`, the dispatch id of the errored check it relaunches, "
        "or null.",
        "- `findings`: exactly one entry for every finding of every check report, never two: its "
        "`report` comment id, its `finding` (`F1`, `F2` ... as the report numbers them), and a "
        "`disposition` of `fixed` with the full `commit` that fixed it, or `declined` with the "
        "`reason`, written when you decline it.",
        "- `rows`: each row you map: its `row`, `carried_by` (`test`, `check` or `fresh-reader`) and "
        "`where`; leave it empty when you map none.",
        "- `decisions`: each thing the plan left open that you decided: its `text`, your "
        "`recommendation`, and the brief `row` it would change, or null.",
        "- `refusals`: each command the entrance refused you: the `command`, its `reason`, and what "
        "you did `then`.",
        "- `stop`: null when ready; when stopped, its `kind` (`shape` or `cannot-launch`), its "
        "`reason`, and `check`, the check it could not launch (named for `cannot-launch`) or null.",
        "",
        "The record is the last thing you post at each ready report, after proof.",
    ]
    return lines


def compose_handoff(*, brief: str, artifact: str, checks: list[dict],
                    allowance: str, repo: str, issue: int, holder_root: str, plugin_root: str,
                    notify: str | None, hand: dict | None = None) -> bytes:
    """The handoff's exact UTF-8 bytes, LF line endings, the same on every call."""
    sections = [
        ("Your role", [ROLE]),
        ("The affirmed brief", [brief]),
        ("The settled plan", [artifact]),
        ("The checks you owe", _checks_section(checks, repo=repo, issue=issue,
                                               holder_root=holder_root, plugin_root=plugin_root)),
        ("What you may write", [allowance, "", f"Open the pull request as a draft from your branch, with "
                                f"`Closes #{issue}` alone on a line of its body, nothing after it: the "
                                "entrance finds the pull request by that line."]),
        ("The readiness record", _record_section("hand" if hand else "launch")),
        ("Where the plan settles nothing", [
            "Where the plan did not settle something, go on with your recommendation, record it in the "
            "record's `decisions`, and name any brief row it would change.",
            "",
            "Stop with `status=stopped` and a `shape` stop only when the brief's Shape is wrong for the "
            "change. Where a check cannot be launched, post `status=stopped` with a `cannot-launch` stop "
            "naming the first such check and why.",
            "",
            "Record in `decisions` too any departure from the plan a check required, with what you added.",
            "",
            "Write no check's instructions, and choose nothing a check reads.",
        ]),
        ("How to finish", [
            "Post proof, then the readiness record at the head you report ready, as the last post.",
            "",
            "Then read your record back with the reach check's command; where it shows the record "
            "unlawful or anything still owed at that head, repair it and post the record again.",
            "",
            (f"Then send one message to the holder session named `{notify}`; where your runtime offers "
             "no such message, end, and the owner tells the holder." if notify else
             "Then end; the owner tells the holder."),
        ]),
    ]
    if hand:
        dispatch = hand["dispatch"]
        sections.append(("Where you work", [
            f"Work in the tree `{hand['tree']}`, on the branch `{hand['branch']}`.",
            "",
            "You need: writes in that tree; writes in the practice's run-record store at "
            f"`{hand['store']}`; a signed-in `gh` that can push the branch and comment in `{repo}`; and "
            "network for both.",
            "",
            "Before your first command, set your dispatch:",
            "",
            "```text", f"export {DISPATCH_VARIABLE}={dispatch}", "```",
            "",
            "or, in PowerShell:",
            "",
            "```text", f"$env:{DISPATCH_VARIABLE} = '{dispatch}'", "```",
            "",
            NO_LAUNCH_BLOCK,
        ]))
    text = "\n\n".join("## " + title + "\n\n" + "\n".join(body) for title, body in sections) + "\n"
    return text.replace("\r\n", "\n").encode("utf-8")


def handoff_digest(text: bytes) -> str:
    """The handoff's sha256, in hex."""
    return hashlib.sha256(text).hexdigest()

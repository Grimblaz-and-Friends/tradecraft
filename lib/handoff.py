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
IMPLEMENTING_PR_MARKER = "<!-- tradecraft:implementing-pr:v1 number=NUMBER -->"
DISPATCH_VARIABLE = "TRADECRAFT_STRETCH_DISPATCH"
# The cold reading's Accepted line takes an em dash, built here so the text's constants stay ASCII.
DASH = chr(0x2014)
# The entrance's own form of the command that resolves an answered review thread. This module stays free
# of the entrance's imports, so the form is repeated here; the stretch allowance grants it only with the
# thread's node id written literally in place of THREAD_ID.
RESOLVE_THREAD_COMMAND = (
    "gh api graphql -f query='mutation($id:ID!){resolveReviewThread(input:{threadId:$id})"
    "{thread{isResolved}}}' -f id=THREAD_ID"
)
ROW_NOTE = ("Every row of the brief has its own reader here, whatever else carries it: launch every row "
            "through its command; map each row in the record's `rows` to what carries it. ")
# Said again under the floor again, where a late commit meets it.
ROW_AGAIN = ("Every row's reader must have a counting report at the head you report ready, so a commit made after "
             "the row readers ran makes every row owed again: run their readers again at the new head.")
ROW_NOTE += ROW_AGAIN

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
# On the mechanical lane a reader reads a brief row, and every row is mapped.
MECHANICAL_RECORD_EXAMPLE = RECORD_EXAMPLE.replace(
    '"criterion": "CRITERION_ID", "row": null', '"criterion": null, "row": 1').replace(
    '"rows": []', '"rows": [{"row": 1, "carried_by": "test", "where": "WHERE"}]')

ANSWER_REVIEWERS = (
    "Wait for each connected reviewer's review and answer it whole, every finding by itself: each inline "
    "thread with a reply that opens with its bare disposition word (`fixed`, `yours`, `declined`, "
    "`duplicate` or `lapsed`, a declined or lapsed answer keeping its reason after the dash); each body "
    "finding in its own pull-request conversation comment that opens with the disposition word and links "
    "the source review with the finding's full identity as the link text, for example "
    "`fixed - restored the required check; "
    "[cr-comment:v1:IDENTITY](https://github.com/OWNER/REPO/pull/N#pullrequestreview-REVIEW_ID)`; "
    "and each unidentified review as a whole, in its own conversation comment linking that exact "
    "review: `fixed - addressed the review's unaccounted findings; "
    "[unidentified review](https://github.com/OWNER/REPO/pull/N#pullrequestreview-REVIEW_ID)`. "
    "One answer names one source link. Close each reviewer's answers with its "
    "`<!-- tradecraft:connected-reviewer:v1 name=NAME status=complete -->` reply once every comment "
    "from it is answered, NAME being its name in the repository's `.tradecraft/work.json` "
    "`connected_reviewers`, the list of those configured; the read-only decision names any not yet run.")
RESOLVE_THREADS = (
    "Resolve each review thread you answered, with exactly this command, its node id written in place of "
    "THREAD_ID:\n\n```text\n" + RESOLVE_THREAD_COMMAND + "\n```\n\n"
    "Resolving is owed when the read-only decision names `reviewer-thread-answered-unresolved`, or the "
    "merge reads `merge-blocked-unresolved-review-threads`; a body finding has no thread. The entrance "
    "names it once the floor and the cold reading's `clean` both stand at your head, so take it after the "
    "floor again.")


class Step:
    """One step of the builder's sequence: its key, its title, what it asks, and the hold the entrance places on it."""

    __slots__ = ("key", "title", "sentence", "hold")

    def __init__(self, key: str, title: str, sentence: str, hold: str | None = None):
        self.key, self.title, self.sentence, self.hold = key, title, sentence, hold


CLEAN_HOLD = "The entrance holds it until the cold reading's `clean` stands at your head."
# The entrance reads the floor before the cold reading and the rest of its chain, so nothing after the floor is
# named until the floor stands at the head.
FLOOR_HOLD = "The entrance names it only once the floor stands at your head."
CLEAN_AND_REACH_HOLD = ("The entrance holds it until the cold reading's `clean` stands at your head and reach "
                        "is settled there.")
# The order the builder takes its steps in. The handoff renders it, and ANSWERS ties each reason the
# entrance returns a builder to the step that answers it, so the text keeps in step with the entrance.
BUILDER_STEPS = (
    Step("open-pull-request", "open the pull request",
         "Push your branch and open the draft pull request, as \"What you may write\" says. Its body carries a "
         "paragraph beginning `**Path departures:**` that names each stage the change skipped, bypassed or stalled "
         "at and why, or says the expected path ran without a departure; keep it true up to proof."),
    Step("floor", "floor", "Run the floor at the pull request's head."),
    Step("cold-reader", "cold-reader",
         "Run the cold reader and answer its reading until a `clean` stands at your head.", FLOOR_HOLD),
    Step("criteria", "acceptance-criterion",
         "Launch every reader listed here through its command, and answer each report in your record."),
    Step("use", "use", "Run use where it is owed.", CLEAN_HOLD),
    Step("reach", "reach",
         "Run the read-only decision and post the `reach-reading` for every item its reach report flags."),
    Step("ready-reviewers", "ready-reviewers", "Mark the pull request ready for its reviewers.",
         CLEAN_AND_REACH_HOLD),
    Step("answer-reviewers", "answer the reviewers", ANSWER_REVIEWERS),
    Step("floor-again", "the floor again",
         "After any commit made after the floor ran, run the floor again at the new head as step 2 gives it, "
         "posting its marker where step 2 gives a command, before you resolve threads or run proof. The cold "
         "reading's `clean` and reach must stand at that new head too before proof, as proof's hold requires."),
    Step("resolve-threads", "resolve the answered threads", RESOLVE_THREADS),
    Step("proof", "proof", "Run proof at your head.", CLEAN_AND_REACH_HOLD),
    Step("readiness-record", "the readiness record",
         "Post the readiness record at the head you report ready, as the last post, after proof."),
    Step("read-back", "read the record back",
         "Read your record back with the read-only decision: its `if_ended` is what the holder's final pass "
         "will read. Where it names the record unlawful or a step still owed at that head, take that step and "
         "every later step its commit makes stale, then post the record again; where its `owed_list` names "
         "several, take the earliest of them in this order first. Where it orders a catch-up, run "
         "the catch-up command below; where it names launch findings, post their launch-account first. Where "
         "it names only a wait, a check run, a gate or a reviewer still running, wait and read it again. You "
         "are done when it reads `final-pass` with `ready-reported`, or names only what stays the holder's: "
         "the merge's own verdict, a required gate on the merge, or a bought panel."),
)
# Not a step in the order: what a builder does when the change can't go on, which a reason meaning "stop"
# points at.
STOP = Step("stop", "stop",
            "Stop with `status=stopped` and a `shape` stop only when what the brief's Shape sentence says the "
            "change is proves wrong for the change, or the affirmed brief is no longer there to say it. Where a "
            "check cannot be launched, post `status=stopped` with a `cannot-launch` stop naming the first such "
            "check and why. A stopped record is your last post; then finish as \"How to finish\" says.")
STEPS = {step.key: step for step in (*BUILDER_STEPS, STOP)}
# An owed check is listed under the step that launches it, so the builder meets it, and the walk answers it, at
# that step rather than in a list of its own.
CHECK_STEPS = {"cold-reader": "cold-reader", "acceptance-criterion": "criteria", "use": "use", "floor": "floor",
               "reach": "reach", "ready-reviewers": "ready-reviewers", "proof": "proof"}

# Each reason the entrance can return a builder between the handoff and its ready record, in the decision
# itself or in its `if_ended`, and the step that answers it.
ANSWERS = {
    "builder-live": "read-back",
    "builder-stopped": "stop",
    "cannot-launch": "stop",
    "ready-record-not-at-head": "readiness-record",
    "builder-returned-without-pull-request": "open-pull-request",
    "base-moved-after-ready": "read-back",
    "base-synchronization-unavailable": "read-back",
    "ready-reported": "read-back",
    "owed-at-ready": "read-back",
    "launch-findings-unaccounted": "read-back",
    "declared-floor-blocked": "floor",
    "declared-floor-stalled": "floor",
    "declared-floor-unverifiable": "floor",
    "latest-check-run-pending": "read-back",
    "current-head-floor-missing-or-red": "floor-again",
    "cold-reading-absent": "cold-reader",
    "cold-reading-why-owed": "cold-reader",
    "cold-reading-stale": "cold-reader",
    "cold-reading-flag-reread": "cold-reader",
    "cold-reading-post-owed": "cold-reader",
    "cold-reading-close": "cold-reader",
    "cold-reading-unverifiable": "cold-reader",
    "floor-complete-pr-draft": "ready-reviewers",
    "required-connected-reviewer-has-not-run": "answer-reviewers",
    "reviewer-thread-lacks-disposition": "answer-reviewers",
    "reviewer-body-lacks-disposition": "answer-reviewers",
    "reviewer-thread-answered-unresolved": "resolve-threads",
    "merge-blocked-unresolved-review-threads": "resolve-threads",
    "bought-panel-incomplete": "read-back",
    "current-head-use-report-absent": "use",
    "current-head-proof-absent-or-outdated": "proof",
    "version-obligation-blocked": "read-back",
    "version-obligation-unverifiable": "read-back",
    "raw-output-blocked": "read-back",
    "raw-output-unverifiable": "read-back",
    "reach-pending": "reach",
    "reach-unmeasurable": "reach",
    "reach-reading-required": "reach",
    "current-head-gate-evaluation-absent": "read-back",
    "latest-gate-evaluation-pending": "read-back",
    "required-gate-unidentified": "read-back",
    "required-gate-evaluation-stale": "read-back",
    "latest-gate-evaluation-failed": "read-back",
    "latest-gate-evaluation-not-successful": "read-back",
    "merge-verdict-unknown": "read-back",
    "merge-blocked-required-gate": "read-back",
    "merge-blocked-unattributed": "read-back",
    "affirmed-brief-marker-absent": "stop",
}


def step_sentence(key: str) -> str:
    """One step's sentence, word for word as the handoff carries it."""
    return STEPS[key].sentence


def _check(stage: str, criterion: str | None = None, *extra: str, row: int | None = None) -> dict:
    return {"stage": stage, "criterion": criterion, "row": row, "command": ["run", stage, *extra]}


def owed_checks(*, criteria: list[str], use_owed: bool, floor_command: str | None,
                mechanical: bool = False, rows: list | None = None) -> list[dict]:
    """The checks the builder owes, reach before the two checks held on it.

    On the mechanical lane each of the brief's ``rows`` (as ``brief.rows`` gives them, or their numbers)
    is owed its own reader, in place of the plan's criteria.
    """
    checks = [_check("cold-reader")]
    if mechanical:
        # Every row gets a reader: a builder that chose which rows are read would be aiming its own check.
        numbers = [row[0] if isinstance(row, (tuple, list)) else row for row in rows or ()]
        checks.extend(_check("acceptance-criterion", None, "--row", str(number), row=number)
                      for number in dict.fromkeys(numbers))
    else:
        checks.extend(_check("acceptance-criterion", criterion, "--criterion", criterion) for criterion in criteria)
    if use_owed:
        checks.append(_check("use", None, "--job-from-artifact"))
    # The holder supplies the floor command once, at the handoff; the builder never writes or picks one.
    checks.append({"stage": "floor", "criterion": None, "row": None, "command": [], "floor_command": floor_command})
    # No stage runs reach: the read-only decision reports it, and the builder answers it with a reach reading.
    checks.append({"stage": "reach", "criterion": None, "row": None, "command": []})
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


def _check_entry(check: dict, block: list[str]) -> tuple[list[str], str | None]:
    """One owed check's command block and its note."""
    stage = check["stage"]
    if stage == "use":
        # The use rules read the change's paths, which do not exist until the builder has built them.
        return block, ("Use is listed because the settled plan carries a `Use session job` block. The "
                       "entrance decides at your head whether use is owed, because the use rules read changed "
                       "paths that do not exist at this handoff.")
    if stage == "floor" and check["floor_command"] is not None:
        return ["```text", check["floor_command"], "```"], (
            "The holder supplied this floor command at the handoff. Run it word for word at the "
            "head you test and, once it passes there, post an issue or pull-request comment whose "
            "first line is `<!-- tradecraft:floor:v1 head=FULL_COMMIT_SHA status=pass -->`, with "
            "`head` the full commit id it ran at, then the command alone in its own fenced block, "
            "then its exact output after that block.")
    if stage == "floor":
        return [], ("The declared CI jobs are the floor; the holder supplied no floor command. If a builder "
                    "floor then falls due, post `status=stopped` with a `cannot-launch` stop naming the "
                    "floor. Never write or pick a floor command yourself.")
    if stage == "reach":
        return block, (
            "This is the read-only decision; it prints the reach report. For every item it flags, "
            "post the `reach-reading` comment: an issue comment whose first line is "
            "`<!-- tradecraft:reach-reading:v1 head=FULL_COMMIT_SHA -->`, with `head` the full "
            "commit id the reading covers and no `holder-reading` companion, followed by exactly "
            "one fenced `json` object holding the integer `schema_version` 1, `turns` (each turn's "
            "`dispatch_id` and its `items`, one per flagged path, each with `path`, `disposition`, "
            "a nonempty `basis` and that disposition's reference field) and, optionally, "
            "`superset_settlements`. The dispositions and their fields: `row-or-criterion` with "
            "`requirement`, `generator` with `generator`, `restored` with `restored_by`, "
            "`owner-ruling` with `ruling_source`, and `own-turn` with `added_by`.")
    if stage == "cold-reader":
        # The entrance matches the account line for line, so a quoted copy would not be found.
        return block, (
            "Post the reading's `open`: a comment whose first line is `<!-- tradecraft:cold-reading:v1 "
            "head=SHA status=open staffing_status=STATUS same_vendor_reason=REASON -->`, with the "
            "reading's head and its report's staffing, `same_vendor_reason` only where that staffing is "
            "`degraded` and then the report's reason. Paste the report's account whole, as plain lines, "
            "not as a blockquote: the entrance matches the account line for line. Then write your review "
            "under \"Holder's review against the brief\" with an `Accepted: path:lines " + DASH + " KIND "
            + DASH + " reason` line for each flag you decline. After repairs run the reader again. Once "
            "nothing stands, post the same marker with `status=clean` and your head. The entrance holds "
            "`run use`, `run ready-reviewers` and `run proof` until a `clean` stands at your head.")
    return block, None


def _checks_section(checks, *, mechanical, repo, issue, holder_root, plugin_root) -> list[str]:
    def argv(command):
        return _argv(command, repo=repo, issue=issue, holder_root=holder_root, plugin_root=plugin_root)

    lines = ["Take these steps in this order. The order is fixed wherever a hold names it, and a step held "
             "on another waits for it. Run each check from the change's tree. The cold-reader, "
             "acceptance-criterion and use commands each launch a fresh reader and post its report, which "
             "your record answers; they, the floor and reach are the record's `checks`, and ready-reviewers "
             "and proof are not.", "",
             "A check's launch may leave launch findings, which the read-only decision reports; they hold "
             "your next step until you post an issue comment whose first line is `<!-- "
             "tradecraft:launch-account:v1 dispatch=DISPATCH_ID -->` for that launch, followed by exactly "
             "one fenced `json` object holding the integer `schema_version` 1 and `findings`: one entry per "
             "finding id the decision names, each with that `id`, a `party` (`owner`, `plugin-update`, "
             "`session`, `builder-damage`, `none-found` or `cloud-check`) and a nonempty `basis`. `session` "
             "also takes the session's id in `session`, and `builder-damage`, a command you made, takes "
             "`owner_report` and `practice_issue`.", ""]
    for number, step in enumerate(BUILDER_STEPS, 1):
        lines += [f"{number}. {step.title}:", "", step.sentence]
        if step.hold:
            lines += ["", step.hold]
        owed = [check for check in checks if CHECK_STEPS.get(check["stage"]) == step.key]
        if step.key == "criteria" and mechanical and owed:
            lines += ["", ROW_NOTE]
        elif step.key == "floor-again" and mechanical:
            lines += ["", ROW_AGAIN]
        elif step.key in ("criteria", "use") and not owed:
            lines += ["", "None is listed for this change."]
        for check in owed:
            block, note = _check_entry(check, _block(argv(check["command"])))
            if block:
                lines += [""] + block
            if note:
                lines += ["", note]
        lines.append("")
    lines += ["When the decision orders it, bring the branch up to its base with:", "",
              *_block(argv(["run", "catch-up"]))]
    return lines


def _record_section(mechanical: bool, started_by: str) -> list[str]:
    lines = [
        "Report ready, or stopped, with one issue comment whose first line is the marker", "",
        "```text", READINESS_MARKER, "```", "",
        "with `head` the full commit id you report, `status` ready or stopped, and `dispatch` your "
        "launch's dispatch id, which `" + DISPATCH_VARIABLE + "` in your environment holds; and with exactly "
        "one fenced json object after it, holding exactly these fields and no others:", "",
        (MECHANICAL_RECORD_EXAMPLE if mechanical else RECORD_EXAMPLE).replace("STARTED_BY", started_by), "",
        "- `schema_version`: the integer 1.",
        f"- `builder`: your `vendor` and `model`, `started_by` `{started_by}`, and `usage_log`, the path "
        "of your usage log or null.",
        "- `checks`: one entry per check you ran: its `stage` (`use`, `acceptance-criterion`, "
        "`cold-reader`, `floor` or `reach`), its `criterion` id or null, its `row` or null (an "
        "acceptance-criterion check names exactly one: a criterion check its `criterion` with `row` null, "
        "a row check its `row` with `criterion` null), its `dispatch` id or null, the full commit `head` it "
        "read, its `report` comment id, and `relaunch_of`, the dispatch id of the errored check it "
        "relaunches, or null. For the floor, `report` is its floor marker comment's id; for reach, your "
        "`reach-reading` comment's id, or null when reach flagged nothing.",
        "- `findings`: exactly one entry for every finding of every check report, never two: its "
        "`report` comment id, its `finding` (`F1`, `F2` ... as the report numbers them; the read-only "
        "decision lists each report's under `builder_checks`), and a "
        "`disposition` of `fixed` with the full `commit` that fixed it, or `declined` with the "
        "`reason`, written when you decline it.",
        "- `rows`: " + ("a mapping of every row of the brief: its `row` number, what carries it (`carried_by` "
                        "`test`, `check` or `fresh-reader`), and `where`. Map every row, each read by its own "
                        "reader too." if mechanical else
                        "each row you map: its `row`, `carried_by` (`test`, `check` or `fresh-reader`) and "
                        "`where`; leave it empty when you map none."),
        "- `decisions`: each thing the " + ("brief" if mechanical else "plan") + " left open that you "
        "decided: its `text`, your `recommendation`, and `row`, the brief row the decision would change, or null "
        "where it changes none.",
        "- `refusals`: each command the entrance refused you: the `command`, its `reason`, and what "
        "you did `then`.",
        "- `stop`: null when ready; when stopped, its `kind` (`shape` or `cannot-launch`), its "
        "`reason`, and `check`, the check it could not launch (named for `cannot-launch`) or null.",
        "",
        "The record is the last thing you post at each ready report, after proof.",
    ]
    return lines


def _opening(issue: int, staged: bool) -> str:
    if staged:
        # A merged implementing pull request already carries the closing reference, so a second would be ambiguous.
        return ("Open the pull request as a draft from your branch, with no closing reference in its body: "
                "this change already has a merged implementing pull request. Then post on issue "
                f"#{issue} a comment whose first line is `{IMPLEMENTING_PR_MARKER}`, NUMBER being your new "
                "pull request's number: the entrance finds the pull request by that marker.")
    return (f"Open the pull request as a draft from your branch, with `Closes #{issue}` alone on a line of its "
            "body, nothing after it: the entrance finds the pull request by that line.")


def compose_handoff(*, brief: str, checks: list[dict], allowance: str, repo: str, issue: int,
                    holder_root: str, plugin_root: str, notify: str | None, artifact: str | None = None,
                    lane_reason: str | None = None, hand: dict | None = None, staged: bool = False) -> bytes:
    """The handoff's exact UTF-8 bytes, LF line endings, the same on every call.

    It carries the settled ``artifact``, or on the mechanical lane the ``lane_reason`` in its place;
    exactly one is given.
    """
    if (artifact is None) == (lane_reason is None):
        raise ValueError("give exactly one of artifact and lane_reason")
    mechanical = artifact is None
    source = "brief" if mechanical else "plan"
    sections = [
        ("Your role", [ROLE]),
        ("The affirmed brief", [brief]),
        ("The mechanical lane", [
            "This change is on the owner-affirmed mechanical lane, with no settled plan: build from the "
            "brief's rows. Its reason:", "", lane_reason]) if mechanical else
        ("The settled plan", ["The text below is the settled plan. Where it opens with a `status=draft` "
                              "marker, it is the draft its settlement names, and the settlement is what "
                              "makes it the plan.", "", artifact]),
        ("The checks you owe", _checks_section(checks, mechanical=mechanical, repo=repo, issue=issue,
                                               holder_root=holder_root, plugin_root=plugin_root)),
        ("What you may write", [allowance, "", _opening(issue, staged)]),
        ("The readiness record", _record_section(mechanical, "hand" if hand else "launch")),
        (f"Where the {source} settles nothing", [
            f"Where the {source} did not settle something, go on with your recommendation, record it in the "
            "record's `decisions`, and name any brief row it would change.",
            "",
            STOP.sentence,
            "",
            f"Record in `decisions` too any departure from the {source} a check required, with what you added.",
            "",
            "Write no check's instructions, and choose nothing a check reads.",
        ]),
        ("How to finish", [
            "Where you report ready: post proof, then the readiness record at the head you report ready, as "
            "the last post. Where you stop, the stopped record is the last post instead.",
            "",
            "Then read your record back with the reach check's command; where it shows the record "
            "unlawful, or a ready record with anything still owed at that head, repair it and post the record "
            "again.",
            "",
            # One rule for both records, so a stopped builder's last act is the same as a ready one's.
            (f"Then, whether the record is ready or stopped, send one message to the holder session named "
             f"`{notify}` (where your runtime offers no such message, end, and the owner tells the holder) and "
             "take no further step: the holder resumes you if the change goes on."
             if notify else
             "Then, whether the record is ready or stopped, end and take no further step: the owner tells the "
             "holder, who resumes you if the change goes on."),
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

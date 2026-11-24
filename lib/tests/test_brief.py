import subprocess
import sys
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import brief

SCRIPT = LIB / "brief.py"


def draft(decision="**1. Keep the decision small.**"):
    return (
        "## Shape\n"
        "The result has the agreed shape.\n\n"
        "**Readers.** Owner and builder.\n\n"
        f"{decision}\n\n"
        "## Not this\n\n"
        "Review risk: ordinary\n"
        "Review lane: connected\n"
    )


@pytest.mark.parametrize("decision", [
    "| Decision | Why | Owner |\n| --- | --- | --- |\n| Keep it small | Because | Clear |",
    "## Row 1 - Keep the decision small",
    "**R1. Keep the decision small.**",
    "**1. Keep the decision small.**",
])
def test_each_established_decision_block_shape_is_accepted(decision):
    assert brief.missing_elements(draft(decision)) == ()


def test_heading_labels_may_carry_their_content_on_the_next_line():
    assert brief.missing_elements(draft()) == ()


@pytest.mark.parametrize(("risk", "lane"), brief.LANES)
def test_each_lawful_review_pair_is_accepted(risk, lane):
    text = draft().replace("ordinary", risk).replace("connected", lane)
    assert brief.missing_elements(text) == ()


@pytest.mark.parametrize(("needle", "element"), [
    ("## Shape\nThe result has the agreed shape.\n\n", "Shape"),
    ("**Readers.** Owner and builder.\n\n", "Readers"),
    ("**1. Keep the decision small.**\n\n", "decision block"),
    ("## Not this\n\n", "Not this"),
    ("Review risk: ordinary\nReview lane: connected\n", "Review risk / Review lane pair"),
])
def test_each_omission_is_refused_by_name(needle, element):
    assert brief.missing_elements(draft().replace(needle, "")) == (element,)


def test_missing_elements_are_returned_in_stable_form_order():
    assert brief.missing_elements("") == brief.ELEMENTS


@pytest.mark.parametrize("rows", [
    "Review risk: ordinary\n",
    "Review lane: connected\n",
    "Review risk: ordinary\nReview lane: substantial-panel\n",
    "Review risk: elevated\nReview lane: mechanical\n",
    "Review risk: critical\nReview lane: mechanical\n",
    "Review risk: ordinary\nReview risk: elevated\nReview lane: connected\n",
    "Review risk: ordinary\nReview lane: connected\nReview lane: connected\n",
    "Review risk: ordinary\nReview lane: connected\nReview lane: mechanical\n",
])
def test_missing_duplicate_or_crossed_review_rows_are_refused(rows):
    prefix = draft().split("Review risk:", 1)[0]
    assert brief.missing_elements(prefix + rows) == ("Review risk / Review lane pair",)


@pytest.mark.parametrize(("old", "new", "element"), [
    ("## Not this", "## Not in scope", "Not this"),
    ("**1. Keep the decision small.**", "Decision one discusses a row.", "decision block"),
])
def test_near_misses_do_not_satisfy_the_check(old, new, element):
    assert brief.missing_elements(draft().replace(old, new)) == (element,)


def test_presence_does_not_judge_content_reasons_or_reader_cells():
    defective = draft("**1. Bad.**")
    assert brief.missing_elements(defective) == ()


def test_required_elements_inside_one_fence_are_refused():
    fenced = f"```text\n{draft()}```\n"
    assert brief.missing_elements(fenced) == (
        "Shape",
        "Readers",
        "decision block",
        "Not this",
    )


def test_fenced_review_pair_remains_accepted_when_other_elements_are_real():
    pair = "Review risk: ordinary\nReview lane: connected\n"
    fenced_pair = f"```text\n{pair}```\n"
    assert brief.missing_elements(draft().replace(pair, fenced_pair)) == ()


def test_bare_pipe_header_is_not_a_decision_table():
    assert brief.missing_elements(draft("Decision | Why")) == ("decision block",)


def test_pipe_table_with_delimiter_and_data_row_is_accepted():
    table = "Decision | Why\n--- | ---\nKeep it small | Because"
    assert brief.missing_elements(draft(table)) == ()


@pytest.mark.parametrize("extra_row", [
    "Review risk: severe\n",
    "Review lane: bespoke\n",
])
def test_unrecognised_review_row_beside_lawful_pair_is_refused(extra_row):
    assert brief.missing_elements(draft() + extra_row) == (
        "Review risk / Review lane pair",
    )


def run_cli(path, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--check", str(path)],
        cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True,
    )


def assert_ascii_output(result):
    result.stdout.decode("ascii")
    result.stderr.decode("ascii")


def test_cli_runs_from_an_arbitrary_directory_and_states_its_limit(tmp_path):
    body = tmp_path / ("brief-" + chr(0x2603) + ".md")
    body.write_text(draft(), encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = run_cli(body, elsewhere)
    assert result.returncode == 0
    assert_ascii_output(result)
    output = result.stdout.decode("ascii")
    assert "required elements present" in output
    assert "content, reasons, and reader cells were not checked" in output


def test_cli_names_every_missing_element_on_standard_error(tmp_path):
    body = tmp_path / "brief.md"
    body.write_text("", encoding="utf-8")
    result = run_cli(body, tmp_path)
    assert result.returncode == 1
    assert result.stdout == b""
    error = result.stderr.decode("ascii")
    for element in brief.ELEMENTS:
        assert element in error


def test_cli_names_an_invalid_utf8_file_with_ascii_output(tmp_path):
    body = tmp_path / ("invalid-" + chr(0x2603) + ".md")
    body.write_bytes(b"\xff")
    result = run_cli(body, tmp_path)
    assert result.returncode == 1
    assert_ascii_output(result)
    assert "invalid-\\u2603.md is not valid UTF-8" in result.stderr.decode("ascii")


@pytest.mark.parametrize("kind", ["missing", "directory"])
def test_cli_names_an_unreadable_input(kind, tmp_path):
    path = tmp_path / ("unreadable-" + chr(0x2603))
    if kind == "directory":
        path.mkdir()
    result = run_cli(path, tmp_path)
    assert result.returncode == 1
    assert_ascii_output(result)
    error = result.stderr.decode("ascii")
    assert "could not read" in error
    assert "unreadable-\\u2603" in error


def test_cli_help_is_ascii_and_successful(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=tmp_path, stdin=subprocess.DEVNULL, capture_output=True,
    )
    assert result.returncode == 0
    assert_ascii_output(result)
    assert "--check FILE" in result.stdout.decode("ascii")


# A real affirmed brief in the bold-row form, its issue references removed: seven rows, each with reader cells.
AFFIRMED = """**Shape:** a holder designs a change with the owner through an affirmed brief and a settled plan, hands it once to a builder session that answers for getting it ready for final approval, running the practice's checks itself as its tools and keeping a record of each, and returns when the builder reports ready for one final pass before the release report. The product harm it answers: every product change pays for the holder relaying each step of the run on the lab's largest context; in the 30 days measured, 23 of the 39 holder sessions that launched a build held a product repository's change, and holders spent 83% of their cost from the first build on.

**Readers:** the owner; the holder (designs with the owner, writes the plan, hands off once and makes the final pass); the builder (a separate session that builds and answers for readiness); a judging seat (the plan's cold seat, the cold reader, the criterion readers, the use consumer and the connected reviewers); an adopter (its owner and sessions, which get the same routes).

**Rows**

**1. The builder answers for readiness. After one handoff it builds, runs every check the change owes, acts on what each returns, and reports ready only with a record showing each check run at its final commit.**
   - *Why:* the owner's design of 2026-11-21: "task the builder to ensure they are ready to submit their change for final approval, with the review steps and tests and everything else as tools they are handed to help them judge success". He also ruled that no check goes: "I don't want to remove the checks". In the 30 days measured, 865 of the 1,212 points holders sent builders after a first build (71%) were process steps or a check's finding passed on, which a builder can take from the source. 19,457 of the holders' 20,609 main-thread calls between first build and last check (94%) were made while nothing they had launched was running, on conversations with a median of 352K tokens when the first build launched.
   - *Owner:* after the handoff, no session brings you this change until the builder reports ready, unless the builder stops under row 3. **Checks:** on a real change run this way,
     - at the commit the builder reported ready, the practice's own reading of the change names nothing still owed except what stays with the holder or with you: the final pass, the release report, a panel you bought, and the merge;
     - every check in the record was launched from the builder's session;
     - between the handoff and the ready report, the holder's session sends the builder nothing and launches nothing, and every model call it makes follows a message from you or from another session.
   - *Holder:* hands off once, then launches no stage and sends the builder nothing until the ready report.
   - *Builder:* receives the affirmed brief, the settled plan and the checks as tools. It opens its pull request, waits for and answers the connected reviewers, catches up with the base, and keeps the record current.
   - *Judging seat:* launched by the builder where the holder launches it today; what it reads and returns is unchanged.
   - *Adopter:* gets the same route.

**2. The holder writes the plan before the handoff, and a cold seat settles it as today. The plan names every check the builder owes and carries the use session's job.**
   - *Why:* the owner's direction of 2026-11-21: "I think we should do the design plan first from the holder though before this, not just the brief", and, asked whether the holder or a separate writer writes it, "I'm fine with the holder writing the plan". 191 of the 1,212 points (16%) were the holder deciding an approach, scope or order mid-run, or answering the builder's question; a plan written by the session that makes those decisions settles them once, before the build. Today another session writes the plan and the holder then posts its own reading of it; a plan the holder writes needs no second reading. The cold seat stays because the holder was in the design conversation, so its plan is the one most likely to leave out what that conversation made obvious. The plan carries the checks and the use job so the builder never writes instructions for a session that judges its work.
   - *Owner:* unchanged; you affirm the brief and aren't asked about the plan. **Checks:** on a real change run this way,
     - the plan handed off is word for word the text a cold seat returned "would" on, or was settled by one of today's other recorded routes;
     - the use consumer's job, as its run record holds it, is word for word the job in the settled plan;
     - no plan-writer session was launched.
   - *Holder:* writes the plan from the design conversation and the code, has it settled, and posts no separate reading of it.
   - *Builder:* builds from a plan it didn't write. Where it finds the plan wrong it follows row 3 and doesn't rewrite it.
   - *Judging seat:* the cold seat judges the holder's plan by today's bar. The use consumer gets the plan's job.
   - *Adopter:* the same.

**3. The builder decides what to do about each finding and records every one it declines, with its reason. It never writes a check's instructions, chooses what a check reads, or changes a check's report. When it meets something the plan didn't settle, it goes on with its own recommendation and records it; it stops only when this brief's Shape is wrong for the change.**
   - *Why:* answering for readiness means deciding which findings are right for the change. In the 30 days, holders told builders not to act on a check's finding in 15 of 26 changes (49 points); those calls move to the builder, so each must be visible to whoever approves. A check is independent only while the party it checks can't aim it or edit it. Going on with a recorded recommendation is today's rule for a surprise after the build starts.
   - *Owner:* the release report lists every finding the builder declined, with the builder's reason and the holder's view, and every decision of the builder's that would change a row of the change's brief. **Checks:** on a real change run this way,
     - the count of findings across the posted check reports equals the count of entries in the record, each naming a commit or a decline with its reason;
     - each posted report is byte for byte the check's own return in its run record;
     - each check's instructions match what the entrance or the settled plan composed, with nothing added by the builder.
   - *Holder:* reads the declines and the recorded decisions first in its final pass, and samples the named commits against their findings.
   - *Builder:* may decline a finding, and writes why at the time.
   - *Judging seat:* its instructions, inputs and report are out of the builder's reach.
   - *Adopter:* the same.

**4. When the builder reports ready, the holder makes one final pass. It reads the record and the result against the brief and the plan, spot-checks whatever it needs to be confident, repeats no check the record shows was run, launches no review session, sends the builder back at most once, and writes the release report.**
   - *Why:* the owner's design of 2026-11-21: "the holder comes back at the end and makes a final pass at anything they want to check; spot checks, etc... whatever the holder needs to have confidence, but not repeating checks the builder already did - they should be able to see what was run and check the results"; "Spot checking the code is good, calling a full cold review agent is bad at that stage"; and "possibly 1 send back at the end if the holder sees problems". In the 30 days, 16 of 26 changes had at least one defect credited to the holder's own look at the builder's work (63 points). That look now happens here, later than it does today. A second send-back would rebuild the relay this change removes.
   - *Owner:* one release report per change, as today. It adds what the holder checked itself, what it sent back and what came of it, and anything still open after the send-back, under what needs your decision. **Checks:** on a real change run this way,
     - the holder launches no cold seat, cold reader, use session or review of the change between the ready report and the release report;
     - at most one send-back is recorded, and a problem found after it is in the release report;
     - the release report names each spot check and what it found.
   - *Holder:* as the row says. Merge readiness goes where it goes today.
   - *Builder:* answers one send-back in the same session, re-runs the checks its changes make stale, and reports ready again.
   - *Judging seat:* not launched by the holder at this stage; re-run by the builder only where a send-back changes what it read.
   - *Adopter:* the same.

**5. The builder's GitHub writes grow to match its step: its own branch, its own pull request (opening it, marking it ready, answering its review threads, posting its proof), and its records on the change's issue. Every other write is still refused, and it never merges. A refused call doesn't end or void the builder's run.**
   - *Why:* the rule that just landed stands: a dispatched session makes only the GitHub writes its own step needs. The builder's step is now the whole run to ready. That rule answered a dispatched agent writing to a product repository before anyone authorized it; here the affirmed brief and the handoff authorize these writes, to this change's own branch, pull request and issue only. A builder that carries the whole run will meet refusals. Today a Claude launch that had any tool call refused is recorded as failed and its return is thrown away, even when the session recovered and finished (an open issue). On this route that would throw away the ready report, so here a refusal the builder recovered from is recorded and the run stands. The same rule stays as it is for a check's own launch, where it guards against a check that was refused its commands and still reported success.
   - *Owner:* a builder can write only to its own change, and never merges. **Checks:**
     - in the launcher's tests, a builder on this route is allowed a push of its branch, opening and readying its pull request, a reply on its own thread and a comment on its change's issue, and is refused a comment on another issue, a push to another branch, a merge, a release and a workflow run;
     - a refusal in a real run appears in the record and the release report;
     - a real run in which the builder had a call refused still yields its ready report and its whole record;
     - a check whose launch failed because one of its own calls was refused is launched again, and both launches are in the record;
     - the record of a builder you started by hand in another app says it ran under its instructions alone, with no launch block.
   - *Holder:* no longer opens the pull request, readies reviewers or posts proof on this route.
   - *Builder:* makes those writes itself, gets a refusal for any other, and goes on after one.
   - *Judging seat:* unchanged; a seat makes no GitHub writes, and a seat's own refused call still fails its launch.
   - *Adopter:* the same allowance.

**6. The handoff is one text that any agent session can be started with. On Claude the holder starts the builder as its own session and doesn't wait on it. A Codex or Gemini builder is one you start by hand with the same text. The practice sets no vendor or model for a builder you start yourself.**
   - *Why:* the owner's design of 2026-11-21: "we can effectively trigger the build as a completely separate session then instead of a sub agent", and for another vendor, "I can just manually trigger codex or even Gemini because it's just a single manual trigger". A second round replayed one change: three judges ranked GPT-6.2 Sol's build first and Opus 5.5's last, at $1.89 against $6.49 at list price. With one start, trying another builder costs a paste and no further change to the practice. A probe on 2026-11-21 ran a Codex session on the lab's usual launch line: it started a signed-in Claude session, but its sandbox refused a write beside the practice's run records, and GitHub's command line wasn't signed in there. So a Codex builder launches a check only where the owner approves those steps or starts it with wider access; Gemini is untested. A check below records what a real run needed.
   - *Owner:* you can open the builder's session, watch it and stop it. For another vendor you paste one text, approve what its sandbox asks for or start it with the access the text names, and tell the holder when it reports ready. **Checks:**
     - a fresh Claude session given only the handoff text reaches a ready report on a real change with no message from the holder;
     - one Codex session you start with the same kind of text either reaches a ready report, or its record names the first check it couldn't launch and why;
     - every run's record names the vendor and model that built, from the run's own log where there is one.
   - *Holder:* starts a Claude builder once, and learns of the ready report from the builder or from you.
   - *Builder:* runs in its own session and its own tree; who started it changes nothing it owes.
   - *Judging seat:* staffed against the builder's actual vendor, as today.
   - *Adopter:* the same.

**7. The new route is the default from the release that lands it. Today's route stays beside it, taken only when you ask for it on a change or the change is one this brief leaves on it, and a change in flight finishes on the route it started. After the first five changes carried on the new route, the lab's coordinating session sets their cost and what got past them beside the 30-day baseline at its next read across changes, and you decide whether it stays the default.**
   - *Why:* the owner's direction of 2026-11-21: "I do want this new method as the default alongside the old for 5 runs - I don't want to have to ask for it". The saving is an estimate, and rows 3 and 4 name what the design gives up: the builder rules on findings against its own work, and the holder's catches arrive at the end. Five real changes settle both, and today's route stays so the lab can go back without a second change. Holders spent $5,549 from the first build on across 48 sessions in the 30 days, about $116 each; the comparison has that to beat after adding what the builder and the checks cost. That figure comes from a probe over the holders' own transcripts at list price, kept on this change's issue, and the five are measured with the same probe so the two sides are alike. The change's size is unknown until the plan; if the plan puts its diff near the lab reviewer's 600,000-byte budget, it lands in instalments.
   - *Owner:* a change you start takes the new route with no word from you about routes. One comparison follows the fifth, then one question about the default. **Checks:**
     - the first change picked up after this lands is handed off on the new route, and its record shows no message from you naming a route;
     - a change you ask to keep on today's route runs on it, and its record says so;
     - each of the first five release reports states the holder's cost before and after the handoff and the builder's whole cost, and the fifth says the comparison is due;
     - the comparison is posted on this change's issue, measures the five changes with the probe that produced the baseline, names its baseline figures, counts the builder's and the checks' cost with the holder's, and lists each send-back and each defect found after merge;
     - a change in flight on today's route when this lands reaches release with no new step.
   - *Holder:* takes the new route unless you say otherwise or the brief leaves the change on today's, and says in the record which route the change took and why.
   - *Builder:* unchanged by this row; it gets rows 1 to 6 on the new route and today's dispatches on today's.
   - *Judging seat:* unchanged.
   - *Adopter:* gets the new default with today's route still available. The five-change comparison is this lab's own and ships nothing.

**Delivery:** two pull requests.
- **The first lands the builder's tools and changes nothing on today's route:** the launcher's stage for a builder that carries a change to ready, row 5's write allowance and its rule that a refused call doesn't void that builder's run, and the entrance's builder-side checks, whose instructions and posted reports the builder can't touch. No change is carried on the new route until the second lands.
- **The second lands the route and is the release that makes it the default:** the holder-written plan, the handoff, the readiness record, the final pass and send-back, the release report's additions, the cost split and row 7's default.
- **The rows' checks worded "on a real change run this way" first run after the second merges,** on the first changes carried on the new route. Each result is recorded in that change's release report, and row 7's comparison gathers them on this issue. Before each merge the rows rest on tests, fixture runs and that pull request's use session.

**Not this:**
- No check is removed, shortened or made optional.
- Today's route isn't removed.
- No code runs the stretch as a scripted loop.
- No stage gets a second writer whose result is compared or merged with the first; the plan and the build each have one.
- The machine's vendor switch and the models the entrance picks for sessions it launches are unchanged. Which plans the owner buys is not this change's.
- A panel the owner buys is still run by the holder.
- The rule that fails a check's own launch when one of its calls is refused is unchanged.
- Cloud builds keep today's route.
- The holder's cost before the handoff isn't reduced; writing the plan adds to it.

Review risk: elevated
Review lane: routine-panel
"""


def test_rows_read_each_bold_row_of_an_affirmed_brief_whole():
    found = brief.rows(AFFIRMED)
    assert [number for number, _text in found] == list(range(1, 8))
    starts = [AFFIRMED.index(f"**{number}. ") for number in range(1, 8)]
    for (number, text), start, end in zip(found, starts, starts[1:]):
        assert text == AFFIRMED[start:end].rstrip("\n"), number
    # The last row runs to `Not this`, so its cells and the paragraph after it are not cut short.
    assert found[6][1] == AFFIRMED[starts[6]:AFFIRMED.index("**Not this:**")].rstrip("\n")
    assert found[0][1].endswith("   - *Adopter:* gets the same route.")
    assert brief.missing_elements(AFFIRMED) == ()


ROW_FORMS = {
    "bold": "**1. Keep it small.**\nBecause small is cheap.\n\n**2. Name it once.**\nBecause one name.\n",
    "heading": "## Row 1 - Keep it small\nBecause small is cheap.\n\n## Row 2 - Name it once\nBecause one name.\n",
    "table": ("| Decision | Why |\n| --- | --- |\n| Keep it small | Because small is cheap. |\n"
              "| Name it once | Because one name. |\n"),
}


@pytest.mark.parametrize("form", sorted(ROW_FORMS))
def test_rows_give_the_same_rows_in_each_form(form):
    found = brief.rows(draft(ROW_FORMS[form]))
    assert [number for number, _text in found] == [1, 2]
    for (_number, text), (decision, why) in zip(found, (("Keep it small", "Because small is cheap."),
                                                        ("Name it once", "Because one name."))):
        assert decision in text and why in text
    assert "Not this" not in found[-1][1] and "Review risk" not in found[-1][1]


def test_a_table_row_is_its_cells_joined():
    assert brief.rows(draft(ROW_FORMS["table"])) == [
        (1, "Keep it small | Because small is cheap."), (2, "Name it once | Because one name.")]


def test_a_fenced_example_of_a_row_is_no_row_and_stays_in_the_row_around_it():
    example = "```text\n**9. An example row.**\n## Row 8\n```"
    found = brief.rows(draft("**1. Keep it small.**\n\n" + example + "\nStill row one.\n\n**2. Name it once.**"))
    assert [number for number, _text in found] == [1, 2]
    assert example in found[0][1] and found[0][1].endswith("Still row one.")
    assert brief.rows(draft("```text\n**1. Only an example.**\n```")) == []


def test_a_heading_row_runs_to_the_next_heading_of_its_level_or_higher():
    found = brief.rows(draft("### Row 1 - Keep it small\nWhy.\n#### Detail\nMore.\n### Row 2 - Next\nWhy two.\n"))
    assert found[0] == (1, "### Row 1 - Keep it small\nWhy.\n#### Detail\nMore.")
    # The `## Not this` heading is higher, so it ends the last row.
    assert found[1] == (2, "### Row 2 - Next\nWhy two.")


@pytest.mark.parametrize("label", ["## Not this", "**Not this:**", "Not this:", "**Not this.** None."])
def test_a_bold_row_runs_to_the_not_this_label(label):
    text = "**1. Keep it small.**\nWhy.\n\n" + label + "\n- nothing\n"
    assert brief.rows(text) == [(1, "**1. Keep it small.**\nWhy.")]


def test_a_brief_without_rows_has_none():
    assert brief.rows("") == [] and brief.rows(draft("Decision one discusses a row.")) == []


def test_an_r_numbered_bold_row_reads_its_number():
    assert brief.rows("**R3. Keep it small.**\nWhy.\n") == [(3, "**R3. Keep it small.**\nWhy.")]

# D-944 — Code carries its reasons, and the release report reviews the owner's decisions

**Purpose:** record why instalment 1 of #942 ships the code-reasons rule, the three homes for the why, the release report's order and the brief's named checks in the shape it does. **Audience:** a future session changing how code carries its reasons, what a release report opens with, how a brief names its checks, or instalment 2's cold reader. **Success:** that reader can recover what was chosen over what for each in-scope row, and what instalment 2 changes, without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/942#issuecomment-6613335767) governs, with the [holder's calls](https://github.com/Grimblaz-and-Friends/tradecraft/issues/942#issuecomment-6613344889) beside it. Its pre-implementation artifact was [settled on the cap route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/942#issuecomment-6614306973). The lane is ordinary / connected, and no panel was bought. Its product harm is the owner merging agent-written code whose reasons he cannot recover from the code, so review becomes trust, and a later agent can undo a decision it never saw.

## Rows and their reasons

- **Row 1, a one-line conceptual reason where a newcomer would ask why, over a narrower test that reasons only where a choice could be undone.** The newcomer test was walked through six real cases from the products, and the undo test missed two of them. The line never says what the code does, never states a changeable number and never carries history, because code reads as current state (his 2026-09-19 ruling, recorded on #661). A reason needing more lines signals complexity or a design-document home rather than a longer comment, in his words "Needing longer comments is likely a sign of too much complexity". This reverses `frozen-documents.md`'s sentence that describing what code does is often what its reader needs.
- **Row 2, three homes and one pointer per covered file to a maintained design-document section, over code citing a decision record or issue directly.** Decisions pile up against a class while it lives on, so a class cannot point at one decision, and search cannot tell which decision is in force where a maintained list can. Only code a change adds is given a section; existing uncovered code is each repository's catch-up work (row 10).
- **Row 3, lasting reasons leave the brief before merge, over keeping the brief as the reasons' home.** The brief is not read after merge. A change that decides nothing owes no decision record only where a reader who never saw its issue can tell why it was made, because a builder's "only a fix" is not evidence of that.
- **Row 6, the release report opening with what needs the owner, then a review of each decision against what he expected, over the earlier convention of plain brief, what lands, evidence, worth knowing and cost.** What he reads should be what still needs a decision or his judgement. Upstream misses are listed only, because what follows from one belongs to the separate "bring it earlier" issue.
- **Row 7, at most three excerpts cut from the diff, over a code tour or retyped snippets.** A cut excerpt can be checked against the diff, and the brief rejects a tour as its own product.
- **Row 8, one collapsed section grouped by row, over leaving checks and process evidence inline.** He can find it without being expected to read it.
- **Row 9, named checks in the owner's cell, carried by criteria and traced by the cold seat, over checks derived only by the artifact author.** A check he never saw cannot stand for success he agreed; briefs get longer for it.
- **Row 11, shipped by default, over an opt-in.** These rules describe how any change should leave its code and reach its owner.

## The holder-level calls

- **C1. One new authoring reference, `code-reasons.md`, plus one charter sentence, over a new cell or `substrate`.** Authoring already owns where content lives and treats a comment beside code as a surface; `substrate` is about cross-platform behaviour; a new cell would add a skill name the owner lives with. The charter sentence reaches a builder writing product code who never matches authoring's description.
- **C2. The holder's duties under rows 1–3 and the interim in one new `the-stretch.md` section, "Reading the change for its reasons",** beside the existing after-each-turn duties, so instalment 2 edits one paragraph.
- **C3. One new engagement reference, `the-release-report.md`,** pointing to the report's existing parts where they live (`change-paths.md`, `the-stretch.md`, the connected-reviewer dispositions, the `filing` cell's ask) rather than copying them. `skills/work/SKILL.md` names it in the unbackticked form, because authoring and work cannot name engagement in the reserved form without a pointer cycle.
- **C4. Checks in the owner's cell after `Checks:`, over a separate column.** It keeps one column per reader and the release report quotes only the text before `Checks:`.
- **C5. `lib/brief.py` unchanged, over a per-row "has checks" content check.** Its check decides only that the form's parts are present.
- **C6. The only code change is the cold seat's composed prompt and its test,** because the seat reads only its dispatch (`_cold_stage_prompt` in `lib/work.py` and `test_explicit_cold_seat_prompt_carries_artifact_brief_and_check_contract` in `lib/tests/test_work.py`).
- **C7. The report's plain brief opens with what needs a decision, or that nothing does,** with the decision list directly after it, which is where `the-brief.md` puts a brief that ends in an ask.
- **C8. No pointer or design-document section in tradecraft's own code in this change.** tradecraft has no design documents, and the one code edit extends an existing string in an existing function; the brief's lasting reasons land here.
- **C9. No guard or lint for comments.** Telling a why from a what is judgement, and instalment 2's cold reader is the brief's check for it.
- **C10. This instalment's own release report uses the shape it builds,** composed by the holder from the implementation tree.

Builder calls inside those: the cold-seat trace paragraph now leads "checks the trace both ways, and against named checks" rather than "three directions", so the next paragraph's "that third one" keeps its referent; the `change-paths.md` clause sits on the release-report gate sentence, where bypasses are restated; a plain brief applying an earlier ruling puts that line after the report's what-needs-you sentence; and `code-reasons.md`'s generic example names a `design/` path, not `docs/`, so shipped text does not read as naming repo-only material.

## Rejected

A new cell; `substrate` as the home; a brief column for checks; a `brief.py` content check; a guard for comments; the narrower undo test for where a reason goes.

## The instalment split and its interim

Instalment 1 is rows 1, 2, 3, 6, 7, 8 and 9 under row 11. Rows 4 and 5 (the cold reader, its every-lane run and its cost) are instalment 2's, and row 10's catch-up issues come at instalment 2's landing. Until then the holder judges whether a change writing no decision record decided nothing and is understood without its brief, and nominates the excerpts worth a look. Only `the-stretch.md`'s performer paragraph names the holder for those two duties; `code-reasons.md`, `the-release-report.md` and the charter sentence name no performer. Instalment 2 replaces the performer there with the cold reader and adds its dispatch and isolation, the builder's and holder's reviews of its account, fix-and-reread and its run on every lane; the holder's own pointer, in-force, lasting-reason and return checks stay.

## Growth

The change adds two references and grows several cells, its governing-prose delta derived by `python tools/figures.py --base b19ba902fde4eb9dfaf4fac13bd744313fa48f04` on this pull request's head; the brief says briefs and reports get longer.

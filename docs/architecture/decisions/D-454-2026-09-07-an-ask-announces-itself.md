# D-454: An ask announces itself or is not put, and how a brief reached settled becomes a record

**Status:** Accepted 2026-09-07 (PR #454)

## Context

[#423](https://github.com/Grimblaz-and-Friends/tradecraft/issues/423), [#424](https://github.com/Grimblaz-and-Friends/tradecraft/issues/424) and [#428](https://github.com/Grimblaz-and-Friends/tradecraft/issues/428), worked as one change under one affirmed brief. The brief is [on #423](https://github.com/Grimblaz-and-Friends/tradecraft/issues/423#issuecomment-5564866660); the artifact is [settled there](https://github.com/Grimblaz-and-Friends/tradecraft/issues/423#issuecomment-5564904987) and [amended once on the reading](https://github.com/Grimblaz-and-Friends/tradecraft/issues/423#issuecomment-5564984744). What this entry records is the reading, not the brief.

Aspects 4 and 9 of the interaction map, [#391](https://github.com/Grimblaz-and-Friends/tradecraft/issues/391), close with this; the rest of that map stays open.

**What the tree held at the base**, `ccacec2`: `skills/engagement/SKILL.md` naming several kinds of ask across the cell without a word for the category, routing a reported call and an argued ask ruled at release to *"the work's issue, the PR body, the decision entry, or the review report"*, and stating a brief's disqualifiers without saying when they are applied; no label, query or record for what waits on the owner; `docs/cells/records/SKILL.md` carrying reviews, admissions and decisions and nothing about a brief; `tools/lint.py` shelling out to `git` alone; `tools/doctrine_callout.py` the only guard reading a pull request.

**Scope was the owner's and it reversed the session's recommendation.** The session recommended holding #423 back — its own filing says the merge-ruled ask is only *"the nearest thing to"* an incident, while #428's trigger had fired the day before. The owner ruled all three in, on a dependency the session had not weighed: *"all 3; the 3rd part of 434 is waiting on it"* — [#434](https://github.com/Grimblaz-and-Friends/tradecraft/issues/434)'s third stage is a push line that raises a pool item unasked, and it has nowhere to land until this exists.

## Decision

**1. The mark is what puts an ask, and that is the load-bearing sentence.** An ask is put by posting an ask block — what is being asked, where the work stands, what an answer unblocks — and marking what carries it. **An ask that is not marked is not put, and nothing that later happens to what carries it rules on it.** The failure this addresses is not the owner overlooking an ask; it is an ask that never announced itself as one, which is why the remedy is a condition on *being* an ask rather than a reminder to look harder.

The three lines are not decoration. The owner named three costs when the sitting probed his experience and took all three, declining the fourth option offered, which was that it had not cost him yet: reloading state per ask, not knowing what blocks what, and asks that do not announce themselves. **Each line answers one of them**, which is why the block is three lines and not one — and why the second line exists at all, reconstruction being paid once per ask rather than once per return.

**2. The mark composes with the existing routes rather than replacing them, and it is written at every site.** The cell already sends a reported call and an argued ask to four surfaces, three of which the owner reads for other reasons — which is the very thing the brief rules out as asking. The cold seat found that collision and it is the observation that changed the build rather than only the artifact. **What changes is not where an ask is carried but that it announces itself**, and that sentence is written into the clause routing a reported call and into the third of the three tests, not only into the new section. A rule stated once and left contradicted where the reader actually meets it is the defect this whole change is about; an exception has as many sites as the rule.

**A report is not an ask** and carries no mark — nothing turns on the owner's answer — which is stated at the routing clause because that clause carries both.

**3. The query is scoped to the repository, and that was measured rather than assumed.** Run unscoped, `gh search issues --label awaiting-owner --state open --include-prs` returns other people's repositories: the label is common enough that three unrelated repositories appeared in the first five rows. The shipped form carries `--repo <owner>/<repo>`. Both arms were run — repo-scoped with the label absent returns empty at exit 0, repo-scoped with a label that exists returns rows — so the sentence describes a command that was executed rather than one that reads plausibly.

**4. The scoring pass is a step over the finished draft, and its whole content is *when* and *how*.** The brief form already stated what is disqualified. What did not exist was a moment at which the list is applied. Opening the form immediately before drafting has failed to prevent the defect repeatedly, so the rule adds that the pass runs **on the finished text**, with **each disqualifier answered on its own** rather than as one impression of the whole.

**The mechanical/content split is the ground.** Over the briefs posted to this repository every one was clean of issue numbers, citations, paths and figures, and most carried implementation detail, evidence or an enumeration. Nothing but a reader can see the second kind, which is why this is a step somebody runs rather than a check something enforces — and it is the same fact that bounds the guard in decision 6.

**This change's own brief is the first instance and is reported as one instance.** The pass removed two content disqualifiers from it, both of which had survived a general re-reading of the form: a recounted incident, and a three-item list rhythm. One case is not a rate, and decision 5 exists so that the next fifty are countable.

**5. The record of an affirmation carries the brief's history; the row is appended at landing and read off three places.** The shipped obligation is that the affirmation record states puts, amendments, drafts the owner corrected before one was posted, and what the pass removed. **The session that was present is the only party holding those figures** — the drafts he corrected before one was posted leave no trace anywhere else, and they are exactly the ones a remedy has to be measured against, which is why this cannot be reconstructed later.

The repo-only half appends one row per change to `docs/settling.jsonl`, read off the affirmation comment, the artifact's settlement block and the pull request body. **Three sources, not two** — the cold seat caught the artifact claiming two, the enumeration of rounds going to the pull request body by the `engagement` cell's own routing.

**The wall decides the split.** A shipped cell may not name `docs/`, so the shipped half states the obligation and the repo-only half states where this repository keeps it; an adopter gets the obligation and no dangling path. **The first row is this change's own**, so the record ships exercised rather than empty — and it carries a `notes` field saying that this brief predates the rule putting the history in the affirmation comment, which is why its history is a further comment instead. That seam is stated rather than papered over.

**`reversed` is null at landing and a reversal is a later append, never an edit.** What counts as one is not settled by the brief, is not settled here, and is left to the session that appends the first.

**6. The declaration guard checks presence and never truth, and the bound is the same fact as decision 4.** Every pull request body carries a line beginning `**Waiting on you:**`; `tools/check_ask_declaration.py` refuses one without it in CI. **A guard that read the body to decide whether an unmarked ask is buried in it would be making a content judgement**, and the corpus in decision 4 is the measurement that those do not survive automation here — a grep for question-shaped prose would fire on nearly every body in this repository.

**What the line buys is the moment, not the check.** It falls where the whole body is in front of the author, so a buried ask has to be actively denied rather than merely omitted. **A green check is therefore not evidence the answer is right**, and the script's own docstring says so, because a guard whose green is read as coverage is the trap this repository has already been caught by.

**The marker requires content after it.** `**Waiting on you:**` alone does not satisfy the guard: an empty declaration would make the check unfailable, which asks the author for a token rather than an answer.

**It cannot live in `tools/lint.py`.** That was checked and not assumed — the lint shells out to `git ls-files`, `cat-file` and `check-ignore` and invokes `gh` nowhere, so it cannot see a pull request. The step sits beside the doctrine callout, which already has `gh` and a pull request number.

**7. The guard's tests carry a negative control from its own class.** Both polarities is the floor for guard-shaped code here. Beyond that, five near-miss markers must fail — unbolded, wrong words, wrong case, no colon inside the bold, single-emphasis. Without them the passing tests are equally consistent with a predicate returning the rest of any line containing the word *waiting*, which is the result the guard would be credited with and would not have taken.

**8. Both rules sit in the cell body rather than behind a pointer.** The `engagement` cell is the largest shipped body and carries no ceiling, so nothing forced the choice; it is judgement, recorded here so it is not re-rolled. Both fire at a moment the session is already inside the cell, and both are short. **A required step behind a pointer is a step a session may not load** — which is the failure mode the scoring pass exists to answer, so shedding it would have been the defect wearing the remedy's name.

**9. The label name is the owner's and is carried to release as an argued ask.** The cell lists *a name* among the decisions that are his. `awaiting-owner` is built and applied, with `waiting-on-you` and `needs-decision` argued against it on the pull request; the work proceeds on the recommendation and he rules at release. **The strongest case against the recommendation is recorded with it**: `needs-decision` would work unchanged in any repository, and `awaiting-owner` prefers precision here over portability everywhere, on a practice whose point is that it ships elsewhere.

## Consequences

An ask now has an object, so #434's third stage has a surface to write to and the push line can be built without inventing one.

**The rate #428 could only floor becomes countable** — but only for briefs landed from here, and only where sessions write the history honestly. The record is self-reported by the one party that holds the figures, which is unavoidable and is the weakest joint in this change.

**A green CI check now includes one that verified a sentence exists.** That is stated everywhere it could be misread, and it remains the thing most likely to be over-read by a future session.

The `landing` and `records` cells are repo-only and are flagged entire for the owner's read at release, as is any change to a shipped cell's name or description; this change touches the `engagement` cell's body only, which is not flagged.

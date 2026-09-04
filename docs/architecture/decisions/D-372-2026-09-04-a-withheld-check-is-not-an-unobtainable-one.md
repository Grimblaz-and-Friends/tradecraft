# D-372: The truncation route says which checks it covers — a check somebody withheld is not a check nobody in reach can supply, and the excluded case takes the label that already exists

**Status:** Accepted 2026-09-04 (PR #372)

**Evidence.** The gap as filed: [#367](https://github.com/Grimblaz-and-Friends/tradecraft/issues/367). The brief, posted at [issuecomment-5544648979](https://github.com/Grimblaz-and-Friends/tradecraft/issues/367#issuecomment-5544648979); the owner's affirmation — *"B, affirm"* — at [issuecomment-5544660305](https://github.com/Grimblaz-and-Friends/tradecraft/issues/367#issuecomment-5544660305); the artifact, settled `would` on its **first** cold seat with no adverse points, at [issuecomment-5544823599](https://github.com/Grimblaz-and-Friends/tradecraft/issues/367#issuecomment-5544823599).

## The condition

`skills/engagement/SKILL.md` carried a route by which a pre-implementation artifact reaches *settled* with no seat having judged it: where the cold check *"cannot be got at all"*, the artifact carries a recorded truncation in place of the verdict. **That condition was never bounded**, and the paragraph excluded exactly one neighbouring case, the adverse verdict.

**The witness that the gap was real is two consumers answering it in opposite directions on the same facts**, in [PR #364](https://github.com/Grimblaz-and-Friends/tradecraft/pull/364)'s experience session at [issuecomment-5536121198](https://github.com/Grimblaz-and-Friends/tradecraft/pull/364#issuecomment-5536121198), finding 4. One labelled its artifact *settled by a recorded truncation* where the check was withheld by the job's extent; the other refused — *"the check here wasn't unobtainable; it was withheld by your extent, which is a different thing."* That note's own diagnosis is the one this change acts on: *"nothing in the cell separates unobtainable from withheld."*

**A count this change got wrong about its own evidence, corrected here.** Commit `d1616ff`'s message says that session *"ran two cold consumers"*. It ran **three** — the note opens *"three consumers on the merged cell"*, all three under a dispatch-forbidding extent; two split on the truncation route and the third reached the cap instead. The commit message is frozen and the correction lives here. The artifact and the affirmation avoid the error by describing the split rather than the run.

## What was decided, and what was rejected

**The fork was the owner's and was put argued.** Three options, all live readings of *"cannot be got at all"*.

**Ruled — a check somebody withheld is not a check nobody in reach can supply.** The route covers a check no party within the session's reach can supply; where a bound someone set is what removed it, the artifact stays a **draft** and the withholding goes back to whoever set that bound.

- **Rejected — a bound the session cannot lift makes the check unobtainable.** This is the reading one of #364's consumers actually held and it is defensible: the route's own words are *"cannot be got at all"*, a forbidden dispatch is genuinely not gettable, and the label discloses that no seat judged the artifact. What defeats it is that this is the only one of four routes to *settled* needing no other party's act, so a party who can write a dispatch could make every artifact settled by writing one clause.
- **Rejected — a new label for the withheld case.** `draft` already means an artifact no seat has settled and already forbids building from it. A fifth label in a four-label family buys disclosure the existing one gives free.
- **Rejected — a definition of *unobtainable*, or a closed list of qualifying conditions.** The change excludes one case, the one the evidence produced. A list would license every case it failed to imagine, and no evidence exists for any case but the measured one.
- **Rejected as a session call — extending the boundary to the owner-ruling route at the cap.** That route needs the owner's act, and [D-300](D-300-2026-09-01-the-boundary-and-its-two-crossings.md) already sends an unreachable owner to *wait*. The residue that no sentence states it for the cap is recorded, and nothing here fires its promotion condition.

## The ground that decided it, stated correctly

**The affirmation carries three grounds, and this change's artifact wrongly said one of them carried the decision.** The artifact's correction section says *"The decisive ground in that comment — that the two readings part only where asking would have worked — is untouched and is what carries the decision."* Read at source, the affirmation's *"The ground that decided it"* carries three, two of them independent of the asking claim:

1. **The two readings part only where asking would have worked** — so the rule reduces to *ask first*, and nothing the route was written for is closed.
2. **The failure directions are not symmetric** — *"B's wrong call is a stall someone notices and lifts, A's is a plan nobody judged reading exactly like a plan somebody judged"* — which holds whatever is true of ground 1.
3. **Route uniqueness** — this is the one route needing no other party's act, *"which is what makes it the one reachable by mistake and the one whose boundary has to be the tight one."*

**Why the over-narrowing mattered rather than being a stylistic slip.** The review found a real defect in ground 1: a one-shot dispatched session cannot ask mid-run, so a session reading *"asking would have worked"* could reason that the readings do not part in its case and place itself on the unobtainable side — the change's own target failure reached through the sentence justifying it. Had the artifact's over-narrowing stood, a later session finding that defect would have read the artifact's own statement that this ground carries the decision and concluded the affirmed exclusion had lost its justification. **Grounds 2 and 3 are each sufficient and neither is touched.** The clause carrying ground 1 was cut from the shipped text in the review's fix batch; ground 3 survives in the shipped sentence and is why that clause was kept when the same batch was shedding.

**A second withdrawal, made in the artifact and repeated here because the artifact is frozen.** The affirmation rejected option A partly on the ground that *"the party who sets the extent is the party the check is run against."* That is false as stated — the extent-setter is commonly a parent session that wrote none of the artifact, which is the case in the evidence itself. What survives is weaker and sufficient: whoever sets the bound has an interest in the work completing and is not the party D-300 makes accountable for an unjudged reading.

## What the review changed, and what it left standing

Five seats, defense, judge; rulings at [pull/372#issuecomment-5545597457](https://github.com/Grimblaz-and-Friends/tradecraft/pull/372#issuecomment-5545597457). Six fixes landed in the shipped prose. Two are worth a later session's attention:

- **The `:95` collision.** This change put a second load-bearing sense of *withheld* into the cell 43 lines above a sentence reading *"Where the work cannot continue without a withheld act … test 1 applies"* — which routes to the **owner**, where the new rule routes to the bound-setter. The judge settled that `:95`'s sense is the irreversibility restraint's own and that the cold check is not an act that restraint withholds, the map assigning it to the unattended stretch. `:95` now reads *"an act this restraint withheld"*.
- **The report's recipient.** The first shipped wording said the withholding goes back to the bound-setter *"in the report the job already owes"* — an obligation `grep -rn "report the job\|the job already owes" skills/ lib/` finds nowhere but in that sentence. It now points at where this cell already sends a call the session made, which names a **place** rather than a party, and so also answers the case of a bound set by a standing rule with no party behind it.

**Left standing, recorded rather than fixed:** that both limbs of the operative condition can be satisfied by the session's own reasoning; that *reach* is defined nowhere; that a truncation's *form* sits behind a pointer conditioned on running a check the truncating session never ran; and that the installed plugin copy of this cell disagrees with the tree until someone updates it.

## Row 199's promotion condition, answered

Row 199 of `docs/recorded-findings.jsonl` asks that *"the next convergence's cold seat reports whether it treated a contrived implementation as an observation or as a blocker."* This was the first convergence cold seat since [D-364](D-364-2026-09-04-convergence-runs-on-real-text-and-stops-at-two.md) shipped that bar. **It treated them as observations.** It returned `would`, named no adverse points, and reported five things it had declined to fail the artifact on — including a real conformance defect it had verified against the tree. It blocked on none of them. That is the behaviour the bar asks for, and it is the first measurement the row has.

## Cost, stated because the next change inherits it

**Prose growth.** Derive with `python tools/lint.py` on the tree and `git show <sha>:skills/engagement/references/cold-seat.md`, comparing `dbcd056` against `2f949f6`: the `engagement` cell body and its `cold-seat` reference both grew, and the cell remains the largest in the practice with no body budget. **The review's fix batch shed less than its own ruling projected** — the judge estimated roughly −122 characters on the cell body from cutting one clause; the batch also *added* to four other sentences to close M5, M7 and M11, so the net shed was far smaller. Stated because the projection is on the record and a later session comparing it to the tree would otherwise find a discrepancy with no explanation.

**`skills/authoring/SKILL.md`'s net-growth rule is not discharged by this change**, and recorded row 195's promotion condition — *"when the cell body next grows without a shedding walk"* — fired here and is met only in part. The two shedding candidates that row names sit in paragraphs this change never touched, one adjacent to the cap; that walk is attached to the existing engagement-size board item, which is where row 195 says it goes.

**The review.** 7 dispatches — five seats, defense, judge — and 1,044,018 subagent tokens, excluding the convergence seat and the experience sessions, which are the change's cost. **The rulings comment states that total as 1,043,978, which is an arithmetic error of 40**; the summands it lists are correct and the correct total is above.

## The one matter put to the owner at release, and his ruling

An external reviewer (`chatgpt-codex-connector`) posted a P1 arguing that where an imposed bound removes the check and its setter cannot be reached, the session has no lawful route — the artifact stays a permanent draft and the report goes to someone unreachable — and asking that the withheld branch be scoped to reachable, removable bounds. The review dropped it as a ruling and surfaced it argued, because it asks to re-decide the affirmed fork rather than to repair the change.

**The owner declined it.** The exclusion stays unscoped: a bound whose setter cannot be reached leaves the artifact a draft, with the withholding reported where this cell already sends a call the session made.

**The ground is the asymmetry the affirmation already carries, and it is the one that survived the review intact.** A wrong call under this reading is a stall someone notices and lifts; a wrong call under the alternative is a plan nobody judged that reads exactly like a plan somebody judged. Scoping the exclusion to reachable bounds would reopen the unilateral route from the other end — an unreachable setter would route back to truncation, which is the door this change exists to close.

**One measurement bears on it and it arrived after the fork was put.** The second experience session's arm 4 ran precisely this standing case on the fixed tree — a one-shot session under a dispatch forbidding any other session, unable to ask mid-run — and produced the affirmed outcome: a draft labelled with warrant, plus the report of the withholding, and no reaching for a route out. The predicted dead end has one measurement against it and none for it.

**What the decline leaves open, stated rather than glossed:** a session genuinely stuck in that case has no forward move, and that is accepted rather than solved. The condition to watch is a real run reporting itself unable to proceed with no party to return the withholding to.

## Known limits

**The truncation arm of this change's first experience session did not stage.** The dispatch asserted that no dispatch facility existed; the consumer could see the Agent tool in its own toolset, correctly classified the claimed absence as a bound someone set, and held a draft. Acceptance criteria 2 and 3 were therefore not exercised by that run, and the over-tightening those criteria exist to catch rested on the diff alone until the second session staged the arm properly.

**Criterion 1's warrant stands at fewer measurements than this change's first session note claimed.** That note recorded *"warrant both times"*. Only one consumer's stated reason names the new text; the other reached the same label by reasoning that #364's consumer had already produced **under the unchanged text**, which by `engagement`'s own falsifier cannot be warrant for a sentence that did not then exist. The note is a posted record and is corrected by a further comment rather than an edit.

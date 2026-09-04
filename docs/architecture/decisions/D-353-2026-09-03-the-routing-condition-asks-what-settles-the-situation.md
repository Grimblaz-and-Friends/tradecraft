# D-353: The routing criterion's condition asks what settles the situation on its own, because the confound is independence rather than direction

**Status:** Accepted 2026-09-03 (PR #353)

**Evidence.** Everything quoted from a live file is pinned to this change's base `453b808`, the tip of `main` the branch was cut from. Cell-body figures are the rows of `python tools/lint.py`, run from the repository root. The measurements this entry reasons about were made by [D-320](D-320-2026-09-02-the-fences-are-measured-and-nearly-all-of-them-are-live.md)'s fence run and are not re-run here; that entry's evidence exposure — its figures resting on GitHub comments no in-repository reader can check — is inherited and is [#324](https://github.com/Grimblaz-and-Friends/tradecraft/issues/324). **This entry adds one exposure of its own**: the panel history it reasons from, including which seats found the defect and how the judge ruled it, lives on [PR #345](https://github.com/Grimblaz-and-Friends/tradecraft/pull/345)'s thread. It is stated rather than smoothed, and the design argument below does not rest on it — the argument rests on the shipped bullet's own text, which any reader here can open. The brief and its affirmation are on [#348](https://github.com/Grimblaz-and-Friends/tradecraft/issues/348#issuecomment-5534219929); the settled artifact is [there too](https://github.com/Grimblaz-and-Friends/tradecraft/issues/348#issuecomment-5534429795).

## The condition

[D-345] widened the routing-criterion bullet to cover text that keeps a reader *away* from a destination — its subject, its two quantities, its enumeration lead-in and route 1's predicate all moved. **The bolded sentence a criterion-writer applies as the test did not move with them,** and was byte-identical at `ed5a524`, `558e95d`, `afa566d` and `453b808`:

> **Reach is falsifiable only where nothing else the reader loads routes that same situation to the same place, or where what does routes it too weakly to mask the difference.**

*The same place* is where the text under test sends the reader. For a **bare exclusion** — a clause that fences a reader off without naming where to go instead — there is no such place, so the phrase has no referent at all. For a fence that does name one, the question faces the wrong way for the confound a fence most often meets.

[D-345] recorded the gap as sustained and unfixed, its judge ruling it a decision rather than a fix because the remedy re-opens the one sentence [D-338]'s panel, defense and judge certified as having *"survived every attack unamended."* **The charter is what makes that not an objection**: *"Decisions inform, never bind … it is never a citation against change, because if current behavior is wrong, the original reasoning probably was too."* D-338 pins its quotations to `70d59b7` and its certification claim is historical, so neither entry is falsified by this repair.

## The decision

**One replacement, in the condition and nowhere else.**

> **Reach is falsifiable only where nothing else the reader loads settles that same situation on its own, or where what does settles it too weakly to mask the difference.**

**The confound is independence, not direction, and that is the whole of the change.** An ablation separates unless something else decides the outcome **without the text under test**. Which way that something else pushes is irrelevant: anything resolving the situation *away from* the destination leaves both arms declining it, and anything pulling hard enough *toward* the destination leaves both arms opening it. Both mask. So the condition is one question rather than two facing opposite ways, and stating it as one is what makes it read in either polarity.

**`settles` is route 1's own predicate**, which the enumeration below already carries — *"the destination's own description settling the situation"* — so the list now reads as instances of the condition above it rather than against it. That is a side effect of choosing the right verb rather than a reason for choosing it, and it changes nothing about the list's class, which [D-338] fixed as *what has defeated reach*.

**Route 3 stays outside the condition, exactly as before.** The reader's own indifference is not something the reader *loads*, so no condition phrased over what the reader loads reaches it. [#348](https://github.com/Grimblaz-and-Friends/tradecraft/issues/348)'s first limb argued this was a defect; PR #345's defense had already disproved the framing, and this change neither relies on that limb nor alters the position.

## The wording the issue carried, and why it is not this one

#348 named a candidate from PR #345's `operational` seat: **`the same way` in place of `to the same place`**. It is shorter, it survives a bare exclusion, and it reads in the mirror for the confound the issue was about. **A cold seat falsified it, and the falsification is this entry's most useful half.**

The bullet's enumeration says its two routes *apply in either polarity*. Route 2 is **an always-on surface naming the destination** — which routes the reader *toward* it. Where the text under test is a fence, a surface pulling hard enough toward that destination leaves both arms opening it, so route 2 masks a fence exactly as it masks a positive trigger. `the same way` compares a competing route against the way the text under test runs, so in the mirror it would have excluded route 2 outright: **it repairs the sentence for routes 1 and 3 and breaks it for route 2**, handing back the same sentence-versus-list disagreement facing the other way. `away from the same place` does the same thing more obviously.

The seat's ground is checkable in the tree without any thread: the enumeration's own *apply in either polarity* is what convicts it.

## What was rejected

**Repairing the enumeration's lead-in instead of the condition, leaving the certified sentence untouched.** The documented failure happens *at* the bolded sentence, before a reader reaches the enumeration, so a repair sited in the list leaves the wrong answer reachable by the reader who produced it. It also costs characters on the largest cell body in the practice where this one saves them. Put to the owner as option 2 of three; not ruled — the owner affirmed option 1.

**Recording it and changing nothing.** The one observed consumer recovered, but at three passes and by letting a list item overrule the rule above it, and the available remedy is net-shorter, so cost is not available as a ground for declining. Put as option 3; not ruled.

**Folding it into [#303](https://github.com/Grimblaz-and-Friends/tradecraft/issues/303)**, the next run of this instrument, whose ablation target is the charter body. Rejected because #303 is a far larger and riskier change and hanging a five-character prose repair behind it delays the repair and muddies what that change's review judges.

**Giving the bare-exclusion case its own words.** Unnecessary: *settles that same situation* has a referent whether or not the text names a destination, so the two defects share one remedy.

**Touching the paragraph's density.** Both of PR #345's experience-session consumers reported reading this paragraph three times, which is a recorded finding in `docs/recorded-findings.jsonl` carrying the instruction *"Attach to the existing engagement-size board item rather than spawning a second"* — [#328](https://github.com/Grimblaz-and-Friends/tradecraft/issues/328) — and the promotion condition *"a third run reports the same three passes, or a consumer does not recover."* The affirmed brief put it out of scope in terms, so this is the owner's edge rather than the session's reading.

## The placement call, and what it cost

**The bullet stays in the body**, on [D-338]'s and [D-345]'s reasoning, unchanged: the list's other items are all in the body, and an instance separated from the rule it instantiates is one a reader meets without the rule that explains it.

**What it cost.** The `engagement` cell-body row of `python tools/lint.py`, run from the repository root at this change's base `453b808` and at its head: **22,627 → 22,622 characters, −5.** Still first of thirteen and still carrying no body budget. **This is the first change to that bullet in the D-338/D-345 sequence that shrinks it** — D-338 grew it and D-345 grew it by 721 — which is stated here because both of those entries are on the record as having grown an unbudgeted body deliberately, and a later size pass reading this row should know which change owns which direction. **No always-on row moved**: the edit is in a cell body, and the `.claude/skills/` and `.agents/skills/` copies `tools/roster.py` generates are name-and-description stubs carrying none of it.

## What the cold seat changed

**Three seats, each a fresh dispatch in its own worktree; two `would not`, then `would`.** All three confirmed `453b808` before reading anything. Each was handed the artifact inline **together with its sha256 and LF-normalised byte count and a path to the same bytes**, and told to stop and report a mismatch rather than return a verdict — which closes, for this change, the standing recorded finding that nothing between a dispatching session and a seat detects a truncated inline artifact. The third seat judged sha256 `7044b2b9fd706b13e05f651e66f0c608f6574859626fc2eb49394d7121dad683` over 18,779 bytes and recomputed both against the file and the inlined copy.

**Round 1 landed on one point, and it was a criterion rather than the design.** Acceptance criterion 2 asked a cold consumer, in the positive polarity, to name what defeats reach — a pass condition the enumeration supplies verbatim, and would still supply if the governing sentence were deleted outright. The criterion could not separate the specified repair from the over-correction it named, which is [D-166]'s own rule turned on the artifact that cites it. **The repair was to stop asking a consumer.** No consumer check can discriminate here, because the list rescues every reader; the criterion became a diff walked route by route — two routes by two polarities, four cells, any empty one a failure — and that walk is what rules out all three of the candidate wordings this entry names.

**Round 2 landed on the design, and produced the wording that shipped.** The draft asserted that in the mirror *"something routing the situation to X is not a confound at all — it is what makes the ablation informative."* Route 2 falsifies that, on the bullet's own *apply in either polarity*. The same round caught the third criterion asserting *"every session here loads it"* of a cell **body**, which is not on the always-on surface at all — true of the description, false of the thing being measured.

**Round 3 returned `would`, having run the four-cell walk independently**, and raised one observation it declined to land on: the artifact permitted the implementer to add this change's own `[D-N]` marker to the bullet, which would cost about eight characters against a five-character saving and so fail criterion 3. **No marker is added** — the bullet keeps `[D-338] [D-320] [D-345]`. That is a deliberate departure from this repository's ordinary habit of citing the entry that landed a line, taken because `docs/cells/records/SKILL.md` makes the citation permissive (*"may cite"*) and because a fourth marker would spend the whole saving on a bullet already carrying three.

## What this change does not decide

**Nothing about `engagement`'s size or density.** No budget is set, no size pass is run; the paragraph is five characters shorter and no easier to read, and the two-run density measurement stays where it is at [#328](https://github.com/Grimblaz-and-Friends/tradecraft/issues/328).

**Nothing about how a licensing run is built, dispatched or scored.** That is `spikes`, and [D-337] landed it. This entry says what the condition asks, not what a run testing it must carry.

**Nothing for [#303](https://github.com/Grimblaz-and-Friends/tradecraft/issues/303).** Route 2's structural status in the mirror is [D-320]'s statement, carried forward unresolved — and it is the datum this change's central judgement turns on, so #303 inherits a sharper reason to settle it rather than a settled answer.

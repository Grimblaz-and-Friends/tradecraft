# D-364: Convergence runs on real text and stops at two — the draft precedes the artifact for a truth-of-text change, the cold check's bar belongs to the instrument, and the third question is the owner's

**Status:** Accepted 2026-09-04 (PR #364)

**Evidence, and what an in-repository reader cannot check.** Everything quoted from a live file is pinned to this change's base `f4f3dbc`, the tip of `main` the branch was cut from. Cell-body figures are the rows of `python tools/lint.py`, run from the repository root. **The three incidents this entry reasons from are all outside this tree** — [#355](https://github.com/Grimblaz-and-Friends/tradecraft/issues/355) and [#356](https://github.com/Grimblaz-and-Friends/tradecraft/issues/356) record Grimblaz-and-Friends/Daemon PR #10, and [#360](https://github.com/Grimblaz-and-Friends/tradecraft/issues/360) collects the loop history — and both cold seats reported that they were barred from the issue threads and therefore affirmed none of those figures. They are carried with links, which is this tree's convention, and stated here as an exposure rather than smoothed; it is the same exposure tracked at [#324](https://github.com/Grimblaz-and-Friends/tradecraft/issues/324). **The design argument rests on none of them.** It rests on the three files this change edits, all openable here. The brief and its affirmation are on [#362](https://github.com/Grimblaz-and-Friends/tradecraft/issues/362#issuecomment-5535694206); the settled artifact is [there too](https://github.com/Grimblaz-and-Friends/tradecraft/issues/362#issuecomment-5535878522).

This is change **B** of the three [#360](https://github.com/Grimblaz-and-Friends/tradecraft/issues/360) sets up. Its three limbs were ruled by the owner on 2026-09-03 and admitted rather than argued; what this entry records is the design left to pickup — how the class is recognised, where the bar is sited and how it is worded, and how a cap is written against this file's own refusal of counts.

## The ordering, and the recognition test

`skills/engagement/SKILL.md` at `f4f3dbc` said only *"Then the artifact is written, and a cold seat settles it."* Nothing distinguished a change whose deliverable is a shape from one whose deliverable is the truth of some sentences, and for the second every criterion the artifact can carry is a property of prose that does not exist.

**The test ships as what *done* is, not as what the change looks like.** A change is in the class where it succeeds or fails on whether some claim the text makes is **true of what it describes**; where the fork is design, nothing outside the text makes the result true or false and the artifact stays first. Three candidate tests were rejected on the way:

- **"The fork is wording rather than shape."** Circular: once the words exist, the design is decided too, so the test fires on every prose change.
- **"The change corrects an existing sentence."** Under-reaches. A change that writes a *new* description of a mechanism owes the same run and corrects nothing.
- **"The issue says so."** Puts the routing in the filing rather than in the text a session holds, which is the failure [#355](https://github.com/Grimblaz-and-Friends/tradecraft/issues/355) itself deferred as the open question — whether the class can be recognised cheaply enough to route on.

**The test discriminates, and the cheapest demonstration is this change.** *Done* for #362 is whether three rules are the right rules; nothing outside the text makes them true or false. So #362 is **not** in its own class, and the artifact-first ordering applied to it. It was drafted first anyway, as a matter of course.

**What the test does not assign is a mixed change**, one that both installs a rule and corrects a false description. This change is that shape: the two consequential edits below — qualifying the section opener in `skills/engagement/SKILL.md` and the flow line in `docs/cells/landing/SKILL.md` — are corrections its own rules force. It is resolved here by drafting first regardless, and **recorded rather than written into the cell**: `engagement` is the largest cell body in the tree, the affirmed brief is no more granular than the test, and a session observed taking the other order on a mixed change is what promotes it.

**Nothing about the ceremony moves, and that was checked rather than assumed.** `AGENTS.md` at `f4f3dbc`: *"the artifact reading it is posted once settled, before the first commit."* A draft in a working tree is neither committed nor posted. [#355](https://github.com/Grimblaz-and-Friends/tradecraft/issues/355) had flagged a collision here — *"which would collide with the ordering the ceremony currently mandates"* — and there is none at the commit.

**But a sweep of the tree found one sentence the new ordering does falsify**, and the first draft of the artifact asserted the opposite. It had checked `AGENTS.md` and the *"Then the artifact is written"* sentence and concluded nothing else states an artifact-first ordering. Two more do. *"A draft is not built from"* survives — its *draft* is the draft **artifact**, in a window that opens only once the artifact exists. **The section's opening sentence does not**: *"The artifact settles what is being built before it is built"*, when the same change concedes in `docs/cells/landing/SKILL.md` that *"a slice of build precedes the artifact"* for this class. Conceding that in the repo-only cell and leaving the shipped one unamended is the exact defect this change exists to stop, so the opener is qualified. **A cold seat found this and declined to block on it**; it was fixed anyway, and the artifact's consulted section rewritten to say what the sweep actually returned.

## The bar

The asymmetry [#356](https://github.com/Grimblaz-and-Friends/tradecraft/issues/356) names is real in the tree: `skills/engagement/SKILL.md` binds the criteria *author* — *"A criterion a plausible wrong implementation would also pass measures nothing"* — and `skills/engagement/references/cold-seat.md` states no threshold for the *checker* at all. `plausible` is the load-bearing word and it appeared only on the side not doing the checking.

**The remedy is the same word, stated to the instrument.** *Would* asks whether an implementer who was not in the conversation, reading the artifact and the brief in good faith, builds what the brief agreed. A contrived implementation is an **observation**, not a blocker. And a dispatch may not raise it, the dispatcher being an interested party.

**It is sited in `engagement`, not in the review's dispatch contract.** #356 deferred that choice. `skills/adversarial-review/references/dispatch.md` at `f4f3dbc` contains neither *bar* nor *plausible*, and a bar sited there would not reach a cold check dispatched outside a review — which is most of them, the cold check being `engagement`'s own instrument rather than the review's. The review's contract is untouched, and whether a *panel* dispatch may set a bar is not decided here.

**It is also dispatch content, which is not decoration.** The seat does not read `cold-seat.md`, so a bar stated only in the file reaches nobody. The paragraph enumerating what every dispatch must carry now names it, on the same reasoning that paragraph already applied to the three verdicts: a dispatch omitting the bar leaves the seat to infer a threshold, which is the same gap read from the other end as the dispatcher setting one.

**A prohibition on the dispatcher setting any bar was rejected**, which was #356's other candidate. It leaves the seat with no threshold at all — the state that produced the incident — and it is unenforceable from inside a dispatch the dispatcher writes. Stating the bar and forbidding a stricter one does both jobs in one paragraph.

## The cap, written against this file's own objection

`skills/engagement/references/cold-seat.md` at `f4f3dbc` opened *"What bounds the re-runs"* with:

> **No count.** A count is crude, and worse than crude: it licenses shipping an unsettled artifact at round N.

**That objection is what the wording had to meet, and the meeting is in where the cap routes.** After the second adverse verdict the artifact is **still unsettled and stays unsettled**, and the next question goes to the owner. What the cap withholds is the third seat — the expensive thing — not the settlement, which is what the objection protects. So the paragraph's refusal is preserved in substance while its sentence is replaced; a session must not find a refusal of counts sitting above a count, which is why the paragraph goes rather than gaining a caveat.

**The two bounds that paragraph named survive beneath it**, and neither reached [#355](https://github.com/Grimblaz-and-Friends/tradecraft/issues/355)'s loop: every revision there changed a claim, and every verdict was a correct `would not`. **Only `would not` counts toward the cap** — `not settleable` settles the artifact by its own discharge, and a revision buying no fresh reading buys no round.

**The owner's ruling settles the artifact, and the label discloses that route.** *Settled by an owner ruling at the cap*, never the word bare, following the pattern the cell already uses for a discharged `not settleable` and a recorded truncation. The alternative — the owner rules and a third seat then runs — was rejected because the third seat is precisely what the cap exists to withhold.

**Two rules below the cap disagreed with it, and a cold seat found both.** [D-304]'s repeated-point rule has the work *proceeding on the recommendation* when its third response fires; the cap leaves the artifact unsettled and a draft is not built from. Both fire at the same instant whenever the second verdict lands on a point the first named, which on #355's evidence is the driving case. And `cold-seat.md`'s own rule sends an amended brief to *a fresh dispatch*, which is the one thing the cap withholds. **The cap states its precedence over both in its own text** rather than qualifying either sentence in place, on the ground that a session at the cap has necessarily loaded this file.

**This is a scheduled arrival inside the unattended stretch, and `skills/engagement/SKILL.md`'s *"Pinging inside the stretch spends the attention the affirmation bought"* now names it as the one exception.** [#360](https://github.com/Grimblaz-and-Friends/tradecraft/issues/360) records that on this board nothing but the owner noticing has ever ended a runaway loop; the cap makes that arrival happen on the second verdict instead.

## What this cost, and what it would have cost

**Two cold seats, `would` then `would`** — the second on a revision the first's non-blocking observations forced. The first round's verdict was favourable and the artifact was revised anyway, because three of its six observations named a false claim in the artifact or a contradiction the change would have introduced into shipped text. That is the sequence this change's own thesis predicts: the observations that mattered were the ones about text that existed.

**The cap would have interrupted the last change to merge.** [PR #353](https://github.com/Grimblaz-and-Friends/tradecraft/pull/353) records *"two `would not`, then `would`"*; under this rule its third seat is not dispatched and the owner is asked. That price was put to the owner above the brief, before the affirmation, so the affirmation is on a brief whose cost was stated.

## What is not decided here

- **A cold-seat A/B on the recognition test.** `skills/spikes` triggers on a candidate wording for a rule, and the test is a claim about what a reader does under a wording. Declined because the experience session this change owes under [D-295] runs the same two-arm measurement, and buying it twice is what [#360](https://github.com/Grimblaz-and-Friends/tradecraft/issues/360)'s trial exists to stop. **The consequence is that the recognition test ships measured by nothing until that session runs**, and if its design arm fails, the second sentence of the new paragraph is what changes.
- **Whether a two-round cap should bound a *review*'s rounds.** [#361](https://github.com/Grimblaz-and-Friends/tradecraft/issues/361)'s surface, and nothing here reaches it.
- **The verdict vocabulary.** Three verdicts, unchanged. The cap is not a fourth.

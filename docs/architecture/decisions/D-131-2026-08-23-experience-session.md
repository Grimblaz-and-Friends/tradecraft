# D-131: The experience session, and why the doctrine names it

**Status:** Accepted 2026-08-23 (PR #131)

## Context

The practice had two instruments that run things and neither of them uses the result. A spike runs *before* a decision, bounded by one named premise ([D-80](D-80-2026-08-19-spikes.md)). `wiring-falsifier` probes by execution *inside* a review, scoped to whether code enforces what prose claims. The nearest rival is the **`operational`** seat, which walks the artifact as its consumer — and it cannot occupy this position, because `skills/adversarial-review` puts the artifact's purpose statement in every seat's shared block and this instrument's consumer must receive no artifact at all; that roster's own taxonomy also classifies what `operational` is told to look for as a lens. Nothing used a built thing as its consumer would, knowing nothing of why, and reported what that was like. The term appeared nowhere in the repository.

Three things on the record made the gap concrete, and they are the reason this is not an invented requirement:

- **The one worked instance left no mechanism behind.** [D-96](D-96-2026-08-20-post-fix-terminus.md) scheduled PR #90's post-fix cycle 2 as the live test of two proposed terminus rules, before either was asserted. Both failed their test; the result was recorded rather than smoothed, and the rule that landed is the better one for it. That was invented ad hoc on [#93](https://github.com/Grimblaz-and-Friends/tradecraft/issues/93) and nothing carried it forward.
- **The trial road was retired without replacement.** [D-74](D-74-2026-08-19-constitutional-reset.md) removed the pre-reset mechanism for admitting what can only be validated by running, and `README.md` still promises that "lessons become guards, guards earn or retire process." What has happened since — D-96's live test, and the spike that closed #115 and #117 — earned and retired process on evidence from running, and each time left no mechanism behind.
- **[#121](https://github.com/Grimblaz-and-Friends/tradecraft/issues/121) is what only use finds.** No review filed it across four days of prosecution over the paragraph it lives in — the one-sign structure sat there as *"whether the remedy adds a rule, guard, or standing prose every later reader pays for, or removes one"* from [PR #74](https://github.com/Grimblaz-and-Friends/tradecraft/pull/74) on 2026-08-19 until PR #107 reworded it, so a `git log -S` on today's wording answers a different question and returns minutes. Every cold seat that actually priced under that paragraph hit it — on a docket built to contain the instance and when asked what was hardest to state, though none was pointed at the defect.

The anchor design is [#122](https://github.com/Grimblaz-and-Friends/tradecraft/issues/122): route every question to the cheapest instrument that can rule on it. This is its first slice.

## Decision

**A cell of its own, `skills/experience-session`**, defining the instrument in three pieces — a one-sentence charter naming the mission, a time-box declared before starting, a session note carrying what was lived — and requiring nothing further. Two duties: **discovery**, the unknown-unknowns a review structurally cannot reach, and **arbitration**, D-96's pattern generalised into a rule that a proposal asserting future behaviour names its falsifier and schedules the next real occasion as its live test.

**Trigger:** a change to how a later session must work — a skill's behaviour, or a mechanism's surface. Mechanical work is out. **Both edges were argued and are recorded here because the trigger's width is the dial the instrument's whole cost rides on:** narrower was rejected as excluding the class [#121](https://github.com/Grimblaz-and-Friends/tradecraft/issues/121) came from; every-non-mechanical-PR was rejected as the ratchet the anchor issue warns against. **Declining costs one line from birth**, recorded on the change's pull request or issue; no session blocks a pull request by existing or by being skipped.

### Home: its own cell, and why the two alternatives fail

`skills/engagement` was the issue's own first candidate and is rejected on its stated purpose: that cell keeps *the surfaces the owner enters* to the decisions genuinely his. An experience session is a session using a result on a real job with him not in the room, and its output is read by a review. Hosting it would turn `engagement`'s success criterion into a disjunction over two unlike jobs — the same failure [D-128](D-128-2026-08-23-filing-cell.md) refused for `filing`.

A `references/` file under an existing cell fails for the same reason, and fails `authoring`'s test directly: the trigger fires when a change to how a later session must work has just been built, with no artifact being written and no review running. That is an independent trigger, which is the test for a cell of its own — and under [D-104](D-104-2026-08-22-engagement-cell.md)'s ladder the burden sits on cramming, never on creating.

`skills/adversarial-review` was excluded by the slice's boundary: what standing a session note has *inside* a review is [#125](https://github.com/Grimblaz-and-Friends/tradecraft/issues/125).

### The doctrine names it, on the owner's ruling

The session recommended the opposite — that the cell fire on its skill description alone, keeping `AGENTS.md` at last-resort material, with a falsifier attached if it never fired. The owner ruled against it on 2026-08-23: **an instrument left to fire on a skill description alone does not fire**, taken as proven, and the contrary route is provable only by a spike carrying no context from the conversation that proposed it. No such spike was run, so the recommendation is withdrawn rather than deferred, and this entry records the ruling with its reason because the argument put to him went the other way.

The clause sits after *open the PR* and before *run the review*, because the note lands on the change's pull request or issue and the review is what reads it. The cell also permits a late run — *late is lawful, silent is not* — which is a fallback for a run that could not make the slot, not a licence to reorder the flow. **It carries the decline path in the same breath** — *"run the experience session the change bought or record the one line declining it"* — so the line states an order of work and cannot be read as a condition of merge. `AGENTS.md` goes 7830 → 7912 of its 8000 budget; nothing was routed out, and no eviction argument is smuggled into this change.

### No schema, ever, and that is the whole design

A template, a field list, a severity scale, a required count — each is the counter-bureaucracy failure the anchor names, and admitting one is how the instrument stops being cheap enough to run. The external form this borrows from is session-based test management (Bach's charter / time-box / debrief), whose virtue is precisely its refusal of further structure. **If this grows a fourth piece, it has failed.**

## The spike, and the one thing it changed

The artifact asserted that three pieces with no schema are enough — a mechanism nobody had executed under this wording, which is exactly the condition a spike is for, and #122's load-bearing reframe is that governing prose is a mechanism whose executor is a reader.

Two cold seats ran sessions against the draft text on real jobs — `skills/filing` on a filing, `skills/engagement` on [#108](https://github.com/Grimblaz-and-Friends/tradecraft/issues/108)'s artifact — carrying nothing from the conversation that wrote it and no statement that anything was under test. [The report](https://github.com/Grimblaz-and-Friends/tradecraft/issues/123#issuecomment-5387217403) carries both notes. **Held:** both notes came back first-person and ordered, both finished inside their boxes (13 and 10 calls of 25), neither asked for more structure, and neither produced a findings list.

**What it changed:** both seats volunteered a *where I was wrong* section that nothing required, and one recorded what the material got right, stating its own reason — a note has to distinguish no-friction from didn't-look. The cell now says both outright. That is the only line the spike moved; everything else it did was confirm.

## The experience session, and the seven things the spike had missed

This change's own new clause applies to this change, so a session ran on the built cell before its review: a cold seat chartered to use `skills/filing` on a real filing, following the cell as its instrument and carrying nothing from the conversation that wrote it. [Its note and the dispositions](https://github.com/Grimblaz-and-Friends/tradecraft/pull/131#issuecomment-5387360757) are on the pull request.

**It found seven things wrong with the cell, two of them contradictions, and the spike had returned *held* against text containing both.** That is the entry's sharpest evidence for the instrument, and it cuts against the spike as much as for it: a premise test confirms the premise it was given and finds nothing it was not looking for.

- The note was required to be **first person** from a consumer the same page required to receive *"no statement that anything is under test"* — and a cold consumer cannot be asked for a session note without being told there is a session.
- *"Nothing else is owed… a field list"* sat two sections above an ordered four-part note contents.
- Five further under-determinations: the time-box's unit and where it is recorded; a run whose authority is narrower than its job; a session running after its review closed; whether one duty alone is lawful; whether naming the material to the consumer is permitted.

**The meaning changes that fix batch made to shipped governing prose, named here because `authoring` requires every one of them to be named where amendments are recorded:** authorship of the note moved from the consumer to the chartering session; *"in order: what I set out to do, what I did, where I stalled, what I did instead"* was **deleted**, removing a required structure; *"late is lawful"* was added as a new permission; *"Either duty alone is a lawful session"* was added as another. Three further findings were dropped with their reasons, chief among them *who invents the job* — a definition of a real job is the schema pressure this design exists to refuse.

**What the spike also produced, and where that went:** findings against `skills/filing` and `skills/engagement` that no review had filed — the discovery duty working on its first run. They are enumerated with their disposition in the spike report and routed to filings against the cells they name, because this change's boundary is the instrument.

## Rejected

**A schema, in any amount.** Above; it is the design.

**A CI check, or any gate.** The admission ladder puts a mechanism first, and a mechanism is exactly wrong here: a check can observe that a note exists, never that it reports use, so it would buy compliance-shaped notes — the 0/8 shape [D-128](D-128-2026-08-23-filing-cell.md) records for compliance sentences, which is why `filing` refuses one. The decline path is one line for the same reason.

**A stage inside the review.** That is #125's question and would have decided it silently; a session that reports to a review is not a stage of one.

**Retrofitting sessions onto changes already landed.** Records are exhaust.

## What this does not settle

Whether real-use evidence outranks panel hypothesis inside a review, and how a note reaches the panel — [#125](https://github.com/Grimblaz-and-Friends/tradecraft/issues/125). Whether the spike trigger broadens — [#124](https://github.com/Grimblaz-and-Friends/tradecraft/issues/124), whose graduation condition D-104 already recorded.

# D-306: The charter carries the obligation to use what a change built, and sheds the admission ladder to the cell that owns it

**Status:** Accepted 2026-09-01 (PR #306)

## Context

A repository that adopted this practice completed a change and never ran its app, though its session reported having the `experience-session` cell loaded. [#294](https://github.com/Grimblaz-and-Friends/tradecraft/issues/294) carries the incident and the [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/294#issuecomment-5488754909).

[D-295](D-295-2026-09-01-the-trigger-and-its-fix-batch-reach-the-product-consumer.md) was Half A: it fixed the cell for a session that reaches it. **This is Half B — what gets an adopter there.** Half A's own review found the gap it leaves: a session whose change touched only what a product's users can do is routed by nothing an adopter is guaranteed to load.

## 1. The obligation lands in the charter, and carries its own merge-time anchor

The charter is the one surface an adopting repository directs every session to load. It gains, inside the **Release** bullet:

> **Before a change merges, one that altered how a later session must work or what someone using the result can do owes a use of that result** — or one line saying why none happened, which discharges it as fully; the `experience-session` cell carries both.

**Sited inside the bullet rather than beside it**, because the charter asserts *"Process weight concentrates at exactly two moments"* and a third bullet would contradict a sentence a few lines above it. It is an obligation on the change, not a moment the owner attends.

**It carries the timing itself rather than deferring it.** Read rather than grepped, because the obvious probe is hollow: `grep -i "merge"` over the base charter returns nothing at all — *"merge"* is not a substring of *"Merging"* — so it cannot see the one line the base charter did carry about merging, which is `- **Release.** Merging is the owner's, never the agent's.` That line allocates an act; it anchors no obligation on the change. Reading both files: the charter had no sentence dating an obligation to before-merge, and the cell's only timing word is *"before the review closes"* — a different gate, and one that nests inside merge rather than competing with it, since `skills/engagement/SKILL.md` defines a change ready for merge as one whose review has run and closed. So the brief's *"before it merges"* had no home, and this sentence is where it gets one.

**It routes rather than restates.** The sentence states three things — a trigger predicate, and the obligation's two limbs — and names the cell for everything else. **The predicate is a copy of the cell's, and that is a cost this entry states rather than claims to have avoided.** The first draft copied only one of the cell's two limbs and the review caught it; the wording above carries both, so the two surfaces agree today, but `skills/authoring/references/cell-structure.md` is right that copies kept in step by hand are the mechanism by which they drift, and nothing mechanical holds these two. What the routing buys is that the cell's elaboration — what counts as mechanical, what a note carries, how a run is isolated — exists in one place. The disjunction, a use *or* a line, is also what stops the sentence reading as a gate, which the cell expressly says it is not.

## 2. The outflow: the admission ladder sheds to the cell that owns it

This edits an always-on surface, so it owes an outflow. The charter's admission paragraph opened *"which the `authoring` cell carries in full"* and then restated the ladder anyway. `skills/authoring/references/routing.md` carries every rung. The restatement goes; the pointer and the shape stay.

**This is a deletion, not a relocation.** `routing.md` is a `references/` file, loaded on demand, so the rungs leave the always-on surface rather than moving across it — which `routing.md` itself names as the failure: *"is not an outflow; it is the same cost under a different heading."*

**What stays, and why it is the load-bearing half.** That owner-stated requirements are admitted rather than argued, and that an agent-proposed rule needs an incident from real work — *"a review finding about governing prose is not an incident."* `grep -rn "incident from real work\|specific approval of that rule" skills/` returns one hit. **Over-deleting it was the one wrong build here that no later edit recovers**, because nothing else an adopter loads carries it; the settled artifact quotes it verbatim and stakes a criterion on it for that reason alone.

**The deletion was probed before it shipped, and could have been refused.** The settled artifact's criterion 5 made the outflow contingent: *"A majority failing refuses the outflow."* Three cold seats in an adopter-faithful tree, asked a real admission question naming neither the ladder nor the cell, all three reached it through the shortened sentence and ran it in order. The [run is reported on the pull request](https://github.com/Grimblaz-and-Friends/tradecraft/pull/306#issuecomment-5497595499). Had they failed, this entry would record a refusal instead — which `routing.md` permits, and which is why the deletion is not merely asserted safe.

**The recorded entry keyed `skills/authoring/references/routing.md -- where a discharge or a deletion's evidence is written, against AGENTS.md's flow order` is met and not promoted.** Its promotion condition is *"a deletion lands with its evidence in neither an entry nor the PR body, or a session asks where to write it."* This deletion's evidence is in both.

**Cited by key rather than by ordinal, deliberately.** `docs/recorded-findings.jsonl` carries no identifier and states no indexing convention, and this change's own review proved the cost: the dispatching session cited zero-indexed and the terminal stage read one-indexed, so two stages disagreed in writing about which entry an ordinal named. The `artifact` string is stable under append; an ordinal is not. Filed as a class defect.

**A second entry's promotion condition fired here, and is named rather than left for a later reader to find.** The entry keyed `skills/charter/SKILL.md:26 against skills/engagement/SKILL.md:72 -- what 'at release' resolves to` promotes on *"a session resolves 'at release' against the charter's Release bullet and drops or misroutes an argued ask, **or the siting question is opened."*** This change opened it: §1's own subhead rules a siting inside that bullet. What was decided is the siting of **this obligation only**; the rest of the release band — the report and outcome delivered, every argued ask ruled there — still lives in `engagement` and is unsited. That remainder goes to the board rather than being settled here.

## 3. The description widens to match the body

`skills/experience-session/SKILL.md`'s frontmatter gains the third trigger limb and the fix-batch clause that widened with it in D-295, so the always-on triggering surface and the body stop disagreeing about when the cell fires. Nothing mechanical holds that agreement — D-295 §5 records that a body contradicting its own description lints clean — so it is held by this change and by the review, not by a guard.

**And it sheds *"and you want to know what use will hit"*.** That clause gated the obligation on appetite: the body says a change *buys* a session, so a session that had already concluded it needed none read the always-on trigger as not firing and never reached the decline rule — #294's own incident one surface up. Pre-existing text, in scope because a defect this change did not undertake is still a defect in the tree it produces. Deleting a condition on firing widens what the description triggers on, and that is the intent: it returns the description to the body's own test.

## 4. What was rejected

- **A third ceremony bullet.** It would contradict the charter's own "exactly two moments" four lines above it.
- **Restating in the charter what the cell carries.** The second half-owner `cell-structure.md` forbids; Half A's review found that exact defect in its predecessor and it is not being re-created here.
- **Rewording the pointer instead of refusing, had criterion 5 failed.** A failed probe would have been evidence the pointer *route* does not carry this content, not that this pointer was worded badly; a reworded pointer would need a second probe cycle, and a recorded refusal is lawful.
- **Reaching past the cell to name `skills/authoring/references/routing.md` directly.** One of the three probe seats reported that the `authoring` cell's *body* never enumerates the order, only its reference does. True, and not acted on: a cell is its body plus its references, shedding depth behind a pointer is this practice's structure, and three of three navigated the hop. Recorded as friction rather than repaired.
- **The qualifier on `AGENTS.md`'s mechanical list.** [PR #295](https://github.com/Grimblaz-and-Friends/tradecraft/pull/295)'s terminal stage ruled it not owed and named this tranche its home. That ruling stands; reopening it here would settle by the back door a standardization question the owner held.

## 5. What this change does not hold, and what holds it instead

Nothing mechanical enforces the obligation on an adopter, and nothing was built to — the affirmed brief excludes it, so that boundary is the owner's rather than this session's reading. What the change rests on is that the sentence reaches a session at all, which criterion 1 probed: [the experience session on this pull request](https://github.com/Grimblaz-and-Friends/tradecraft/pull/306#issuecomment-5497845173) records a cold consumer citing the release clause by name and then running a use of what it had built.

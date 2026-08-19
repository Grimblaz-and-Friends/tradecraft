# D-66: The boundary statement states scope, and moving it is the owner's

**Status:** Accepted 2026-08-18 (PR #66)

## Context

§6 states what the pre-implementation artifact's boundary statement is *for* — *"what makes a later scope question answerable from the artifact instead of from memory"* — and stops there. It never says whether the boundary **binds**, and the convergence gate's own `amended` outcome has no post-affirmation form: the gate ends *affirmed, amended, or rejected*, and nothing says how an affirmed boundary changes afterward.

**Sessions read a wall into that silence, and said so in their own filings.** Four issues opened on 2026-08-18 carry the sentence verbatim — *"routed out as sitting outside that change's boundary"* ([#51](https://github.com/Grimblaz-and-Friends/tradecraft/issues/51), [#54](https://github.com/Grimblaz-and-Friends/tradecraft/issues/54), [#55](https://github.com/Grimblaz-and-Friends/tradecraft/issues/55), [#56](https://github.com/Grimblaz-and-Friends/tradecraft/issues/56)) — and [#63](https://github.com/Grimblaz-and-Friends/tradecraft/issues/63) states the reasoning outright: *"Landing it there would have made the work nonconform to its own affirmation."* Each of those sessions followed the text faithfully, which is what makes this a defect in the text rather than in the sessions.

**The wall reading closes §7's exits by elimination.** With fix-here walled off, the guard home is closed by §2's recurrence-and-stability road on a first occurrence, `recorded` asserts *nobody will act on this* — false of a finding a panel sustained — and `owner-pending` is reserved for findings turning on an owner decision, which scope already was. `filed` is what remains. Every substantial change runs a panel built to find a lot; every panel finds things outside the boundary; the board fills at roughly five per change, by arithmetic rather than by anyone's appetite.

**The measurement, taken 2026-08-18.** 41 issues created since 2026-08-15, 26 open; 17 carry zero comments and **19 have had no activity after the day they were filed** — 73% untouched in the repository's first four days. Of the ten filed on 2026-08-18, none is closed and none has moved. Work items get picked up; routed-out findings do not, and the split is clean. Set against §6's own stated target, the predecessor's *"324 open issues; 40% untouched for 90+ days"*, the trajectory is the one §7 exists to prevent, reached in four days instead of eight months.

**The defect is an asymmetry, not merely a silence.** Widening the boundary changes what the owner affirmed and therefore feels costly; routing a finding out costs nothing and requires nobody. The free move is the one that manufactures issues, and no decision ever chose that gradient — it fell out of a rule that never said what it bound.

## Decision

**Statute delta:** §6's boundary statement gains what it binds and a form for changing it after affirmation — it states scope rather than prohibiting more, widening it is a re-affirmation the owner gives, both directions arrive as one batched question at a phase seam, and an unattended run widens nothing and puts no question. `AGENTS.md`'s always-on *Before implementing* line carries the obligation in substance.

**Displaces:** —

No existing rule is retired or loses a citation. The boundary-statement rule keeps [ADR-006:46] and its text is unchanged; the four new units sit after it and answer the question it left open.

### The four rule units, and why four rather than three

The affirmed artifact described three moves. They land as **four rule units** because §12 keys rule identity on the bold lead-in, so a rule with no lead-in of its own *"cannot be cited, superseded, or found"* (D-61, rejected option 3). The unattended route is a distinct rule a later change will need to cite; folding it into the batching rule as a trailing sentence would make it unfindable. **The substance is identical to what was affirmed and no boundary-statement item moves** — this is the shape of the landing, not its scope.

1. **What the boundary binds.** Stated as the purpose sentence's own consequence: a scope that is *answerable* is not thereby *fixed*. The rule is written to displace the wall reading rather than to sit beside it — a change that remedies something adjacent is not nonconforming for having remedied it, it is nonconforming for moving the boundary **silently**. A merely permissive wording was rejected: the sessions reached the wall from silence, and a permission that leaves the prohibition readable changes nothing.

2. **Widening is a re-affirmation.** The boundary is part of what was affirmed *as a whole*, so moving it is §5's convergence question put again over a smaller surface. **This is the same gate, not a new one**, which is what keeps it clear of §5's cut test — the test strikes a gate that cannot say what the human uniquely decides, and convergence's own answer covers this one. The record reuses the affirmation record's existing form: a comment on the work's issue naming the affirmed artifact comment, before the commit that relies on the wider boundary.

3. **Both directions are one decision.** The question is asked whole — widen and remedy here, or route out and name where each goes — once, at a phase seam, in §5's surfacing form. **Gating only the widening was rejected as strictly worse than the status quo**: routing out would stay free while widening acquired a cost, sharpening the very gradient this decision exists to level.

4. **The unattended lane.** It routes out, records, widens nothing, and does **not** halt. §5's zero-questions construction is untouched, and a halt would deliver the decision no sooner than the durable record already does. This follows the shape §7 gives the opening seam's batched question, including the fail-closed direction for a run whose lane is undetermined, so no new lane semantics are minted here.

### What is unchanged, and stated because a reader will ask

§7's five exits, the filing precondition and the pickup test all stand — what changes is how often the fix-here home is genuinely available, not the test for leaving it. The pricing rules are untouched on both surfaces: §6's *"argued rather than scored"* and §7's *"No field, threshold or query ships with this."* **No boundary edit reaches a priced-out finding**, which a panel agreed was *in* scope and declined on cost; that is a different question with a different instrument, and folding it in here would have smuggled sequenced work into this change.

### Not a trial

§2 opens the trial road where a mechanism's **absence is silent**, and is explicit that *"where the absence produces its own incident, the ordinary road is open and the trial road is not needed."* This absence produced ten visible filings in a single day. The ordinary promotion road is open and is the one taken.

## Rejected

1. **Making the boundary binding in text, and building an explicit exception process.** The honest inverse: it would settle the ambiguity in the other direction and preserve reviewability by construction. Rejected because it ratifies the gradient — an exception process is a cost on widening with nothing added to routing out — and because no rule ever decided the boundary should bind; ratifying it would be adopting an accident.
2. **Leaving widening to the session's judgment**, with no re-affirmation. Removes the wall and the owner in one stroke: the boundary is part of what was affirmed, and letting the author move it unilaterally makes the affirmation cover a scope the owner never saw. It also converts a scope decision into an unrecorded one, which is the defect §6's affirmation record exists to prevent.
3. **A new gate type for scope changes.** Fails §5's cut test on its own terms — it could not say what the human uniquely decides that convergence does not already decide — and §5's gate set *"evolves by evidence, not by accretion."*
4. **Per-finding questions as they arise.** §5 requires questions *"batched at phase seams, never dribbled mid-stream,"* and the per-finding shape is the five-interruptions-per-change cost that [#40](https://github.com/Grimblaz-and-Friends/tradecraft/issues/40)'s approach would have carried.
5. **Gating widening only.** See rule unit 3: strictly worse than the silence it replaces.
6. **A typed halt in the unattended lane** when findings fall outside the boundary. Dominated — the halt delivers the decision no sooner than the durable record, and costs the unattended lane its purpose. This is the same reasoning D-61 applied to the seam's option B.
7. **A guard.** Whether a change *could* lawfully have covered a finding is a judgment about scope, and no artifact a lint reads distinguishes a boundary honoured from a boundary that should have moved. §2's promotion road stays open if a checkable shape emerges.
8. **Re-dispositioning or closing the issues already filed.** They are this decision's exhibit, and re-judging them under a rule that did not exist when they were written is the retroactive reclassification §8 declined at corpus scale.
9. **Bundling the prioritisation work** — a read-only bucketing skill and its label — into this change. Sequenced after it by the owner's ruling of 2026-08-18, on a different road: the label is a boundary format under §2 and the skill that assigns it is a mechanism, and neither question belongs to a rule change about scope.
10. **Landing the three moves as three rule units.** See above: §12's identity model would leave the unattended route uncitable.

## Evidence

- The work item, its pre-implementation artifact, and the owner's affirmation record: [#65](https://github.com/Grimblaz-and-Friends/tradecraft/issues/65), artifact at [comment 5336151739](https://github.com/Grimblaz-and-Friends/tradecraft/issues/65#issuecomment-5336151739), affirmation at [comment 5336164698](https://github.com/Grimblaz-and-Friends/tradecraft/issues/65#issuecomment-5336164698).
- The four filings carrying the wall reading verbatim: [#51](https://github.com/Grimblaz-and-Friends/tradecraft/issues/51), [#54](https://github.com/Grimblaz-and-Friends/tradecraft/issues/54), [#55](https://github.com/Grimblaz-and-Friends/tradecraft/issues/55), [#56](https://github.com/Grimblaz-and-Friends/tradecraft/issues/56).
- The filing that states the reasoning outright — *"Landing it there would have made the work nonconform to its own affirmation"*: [#63](https://github.com/Grimblaz-and-Friends/tradecraft/issues/63).
- The elimination path to `filed`, and the exits it closes: statute §7's five-exit rule and §2's recurrence-and-stability road.
- The board measurement of 2026-08-18 — 41 created, 26 open, 19 with no activity after their filing day, none of the ten filed that day moved — taken from the repository's issue API.
- The target this trajectory is measured against: §6's Context, the predecessor's *"324 open issues; 40% untouched for 90+ days."*
- The surfacing form both the batched question and this decision's own options are built to: [D-61](D-61-2026-08-18-decision-surfacing-and-the-attended-seam.md).
- The unattended shape this decision follows rather than mints: §7's opening-seam rule, as amended by [D-61](D-61-2026-08-18-decision-surfacing-and-the-attended-seam.md).

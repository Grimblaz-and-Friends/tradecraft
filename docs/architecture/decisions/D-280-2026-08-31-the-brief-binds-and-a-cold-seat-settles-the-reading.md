# D-280: The owner affirms a brief, not the artifact — the brief binds, a cold seat settles the reading, and the routing to the standards an artifact owes is chosen by measurement

**Status:** Accepted 2026-08-31 (PR #280)

## Context

[#116](https://github.com/Grimblaz-and-Friends/tradecraft/issues/116) asked which artifact comment an affirmation record names when the artifact is amended after posting, framing the crux as *record or contract*. [#248](https://github.com/Grimblaz-and-Friends/tradecraft/issues/248) asked why a session writing a pre-implementation artifact is never routed to the behaviour-claim rule that names its surface, with three contested remedies and none ruled.

Both were picked up together, and the owner then made a ruling neither issue anticipated: **the conversation is the engagement surface, and the posted artifact is a record for the agents that build from it.** That was not new doctrine. [D-114](D-114-2026-08-22-convergence-is-interactive.md) had already ruled the posted comment *"the record of what was agreed, never where he first reads it"* and *"a record, **not a review surface**"*, and records a shorter wording dropping the first clause being put to the owner and declined. `skills/engagement/SKILL.md` carried that entry's ordering and never absorbed its record-not-a-review-surface half — the cell listed the artifact among the surfaces the owner enters, and directed it to open with the plain brief.

The session's own failure is the incident: it wrote the brief into the draft artifact and omitted it from the message that put the decision to the owner, who noticed and asked why. The rule was being applied to the record and not to the person.

## Decision

**1. Authority follows affirmation, not placement.** A brief the owner affirmed is the term of the agreement; the material under it interprets that term. Where the two conflict the brief governs; where the brief is silent, the material does. Everywhere else — a review report, a handback — a brief describes something that already exists and yields to its subject. This reverses `engagement`'s *"It is accountable, not authoritative … never a second contract competing with it."* Keyed to affirmation rather than to a list of surfaces, because a list drifts as surfaces are named.

**2. The brief locks, then the artifact is written, then a cold seat settles it.** The brief is settled in conversation and posted as its own comment when it locks; it locks once nothing still open could invalidate it, a question that would only add *detail* being the artifact's business. The artifact is the session's reading, and a seat with none of the conversation's history judges whether that reading would achieve the brief. Both halves get an artifact-visible carrier — the brief is a comment, the artifact carries the verdict — per the standard [D-261](D-261-2026-08-30-visible-compliance.md) landed four days earlier; without them both are judgments resolved against nothing, the weakest band that entry's sweep measured.

**3. A brief sits immediately before what it briefs.** On a document that is the top; on a message ending in a decision it is directly above the ask. The prior wording fixed it at the top of the surface, which on a message ending in a decision puts it as far from the ask as the message is long.

**4. An amendment is a further comment, never an edit (#116), and the crux dissolves rather than resolving.** Both framings reach the append route: under *record*, `AGENTS.md` bans mutation and [D-113](D-113-2026-08-22-component-sign-and-purpose-statement.md) names an affirmed artifact among *"append-only records the correction cannot reach"*; under *contract*, the practice had already written the reason on [#159](https://github.com/Grimblaz-and-Friends/tradecraft/issues/159#issuecomment-5403081979) — *"a contract that changes silently is not one."* So no ruling on the crux was needed. Who is involved splits by what changes: an amendment to the brief is re-agreed with the owner; one to the reading is the session's. **#116's body had its central evidence backwards** — it asserts editing is *"what the practice actually does"* — and [the correction comment on that issue](https://github.com/Grimblaz-and-Friends/tradecraft/issues/116) carries the deriving command.

**5. #248's routing was decided by measurement, not preference.** Eight cold seats, four candidate wordings of `authoring`'s frontmatter description, two unrelated artifact-writing jobs, no seat told what was under test; [the run is recorded on the issue](https://github.com/Grimblaz-and-Friends/tradecraft/issues/248#issuecomment-5473090623). **The issue's route 1 as originally worded is falsified**: narrowing the exclusion reached the standard 0 of 2, seats naming the narrowed clause as their reason for skipping — the shape `not for … pre-implementation artifact` is matched and the qualifier is not read. Deleting the exclusion reached the cell 2 of 2 and the standard 1 of 2. Naming the artifact in the *positive* trigger, with the exclusion reworded as a job, reached the standard 2 of 2. That wording ships unmodified; a shorter variant would ship an untested string, which is how the falsified candidate arose. **Route 3 is separately unlawful in form** — `check_sideways_deps` and `CHARTER_CELL` in `tools/lint.py` permit one cell-reference target at depth one, and `cell-structure.md`'s sibling carve-out is for exclusion rather than routing. The general problem is filed as [#255](https://github.com/Grimblaz-and-Friends/tradecraft/issues/255).

**6. The contingent-criteria machinery re-anchors.** [D-155](D-155-2026-08-24-measured-figure-lawful-in-the-artifact.md) has affirmation replacing each contingent criterion with the owner's ruling. With affirmation attached to the brief, nothing discharged one. **A fork that is the owner's now goes in the brief**, and criteria are written against the ruling it carries; the contingent form is for a fork still open at lock time, which the lock condition forbids. Found by the cold check, not by the drafting.

## What the owner approved, and what those approvals do not reach

Both are recorded on [#260](https://github.com/Grimblaz-and-Friends/tradecraft/issues/260), whose landing is their expiry, because that is where the party who must undo them will read.

- **The always-on ceilings may be exceeded.** `AGENTS_BUDGET_CHARS` and `CHARTER_BUDGET_CHARS` are raised, each to the measured body plus the margin its prior constant carried, so both remain a ceiling above a measured body rather than headroom to grow into. Each comment names the reason and #260, and each literal pin in `tools/tests/test_lint.py` moves with it — that pin exists so *"a change to either is a deliberate act with a red suite behind it"*, and it worked.
- **No outflow is discharged** for the four always-on edits. The three relocation moves are the failure #260 documents; the fourth, evidence-gated deletion, needs per-rule evidence that is #260's own deferred disposition, and discharging it ad hoc would pre-empt that with a one-rule sample. **Neither approval reaches `revising.md`'s duty to name every meaning change**, which the artifact's table carries.

This departs from [D-253](D-253-2026-08-30-guidance-on-its-readers-surface.md)'s *"No budget constant moved. The surfaces were made to fit; the ceilings were not raised"* — knowingly, on the owner's approval, and temporarily. That entry's own reasoning is why the batching here is one PR rather than two: splitting work contending for one budgeted surface pays a second outflow on headroom the first consumed.

## What was rejected, and why

- **Splitting the ceremony change from the two board gaps.** Recommended twice by the implementing session on the ground that the surfaces were too full, and withdrawn after reading [#245](https://github.com/Grimblaz-and-Friends/tradecraft/issues/245)'s landed rule: *"A ceiling reached is a trigger, not a wall … never a reason to leave the surface unedited."* The argument had been the exact reading that rule forbids.
- **Narrowing `authoring`'s exclusion** — falsified by the run above, 0 of 2.
- **Carrying the behaviour rule inline in `engagement`** — barred by `cell-structure.md`'s *"Two half-owners of one sentence kept in agreement by hand is never lawful."*
- **Ruling the record-or-contract crux** — unnecessary once both framings were shown to reach the same route.

## Known limits, stated rather than glossed

**The #248 routing does not reach Codex in this repository.** `check_project_roster` records that Codex *"is outside that scope and stays outside it"*, and [D-210](D-210-2026-08-26-project-roster-and-the-loaded-total.md) records that a Codex session loads no roster. The mechanism reaches sessions that load one — Claude Code here, and plugin adopters. Closing that is #255 and #260 territory.

**The run's own limits are on its record**: eight seats, two per arm; seats received the roster as text rather than through the harness, so it measures the wording's routing power and not the loading machinery, which [D-210] already establishes separately.

**The cold check could not verify the two approvals or the run** at the time it ran, both being external to the tree; the run has since been recorded on #248.

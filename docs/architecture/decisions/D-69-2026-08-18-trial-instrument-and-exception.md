# D-69: The trial road's falsifier and evidence stop being ledger-only, and a property may be excepted by naming what replaces it

**Status:** Accepted 2026-08-18 (PR #69)

## Context

§2's trial road exists to escape one failure: for a mechanism whose value cannot be shown without running it, *"start as nothing" means never start*. ADR-002 states the class that failure belongs to and records three prior instances of it — *"an evidence loop whose instrument cannot express the finding it tests for is not evidence"*: [PR #6](https://github.com/Grimblaz-and-Friends/tradecraft/pull/6) found a **schema** that could only answer no, [PR #12](https://github.com/Grimblaz-and-Friends/tradecraft/pull/12) found the **rule** above it doing the same, and the lifecycle above both.

**Properties 4 and 6 put the road back inside that class.** Both bound their obligations to the ledger — property 4's falsifier and review trigger to "a unit the instrument actually counts. The instrument is the ledger", property 6 to "ledger rows attributable to it". The ledger is a *defect* ledger by construction, and §8 refuses in terms to admit non-defect rows into it: *"no defect ledger can carry it without admitting non-defect rows and becoming a different instrument."* So the road admitted only mechanisms that **find** defects, and refused every mechanism whose value is that a defect is **never made** — not for want of evidence, but because the instrument could not express the finding.

**The incident.** [#28](https://github.com/Grimblaz-and-Friends/tradecraft/issues/28) proposes a discovery-phase spike, and its pre-implementation artifact hit both properties in the two places they bind.

- **Property 6 made the filed concept unadmissible.** The spike's motivating form — a cheap build *before* any artifact exists — can never write a ledger row, because a defect needs an artifact to sit in and nothing has been asserted yet. It also has no incident of its own, so the promotion road was shut too. The artifact's `D0` narrowed the concept to a form that produces rows, and the narrowing was forced by the instrument rather than chosen on the merits.
- **Property 4 forced a proxy meaning the unit it bans.** Property 4 ruled out elapsed time, sessions, pull requests and "uses", so the artifact's `D6` stated its review trigger as *24 distinct `source` values* and justified it in the same paragraph as *"roughly eight units of work"* — the banned unit reached through a permitted one.
- **And underneath both, a structural inversion.** A review trigger counted in the trial's own output can never fire on a trial that produced none, so property 3 fails against exactly the trial that most deserves cutting. That is a consequence of property 4 as written, not a drafting slip in #28.

**The road's own re-read trigger had the same shape.** It read: *"The first countable event that can say anything about the trial road is a ledger row whose `found_by` or `source` names a trial."* The ledger holds 819 rows across 68 `source` values and **zero** carrying a `trial` token; no trial has ever run. A road too strong to admit anything writes no row, its re-read trigger never fires, and it is unfalsifiable in precisely the case where it is wrong. This decision exists because a **failed admission** said something about the road, which that rule asserted was impossible.

**The evidence base, stated honestly.** One checkable instance — #28's failed admission — plus owner-reported recurrence at recollection grade, registered in [`evidence.md`](../evidence.md). ADR-002 already called its own basis thin ("two incidents, one day"), and this decision spends that thinness further. What weighs against that: the class is now four-times-recorded, three of those instances predating and independent of this one, and the fourth occurring inside the escape built for the first three.

## Decision

**Statute delta:** Properties 4 and 6 are restated around what they were always claims about — a falsifier counted in the trial's instrument and a review trigger counted in opportunity, and the record the trial's own promotion would demand rather than ledger rows specifically — a new rule permits excepting a property only by naming what stands in its place, and a mechanism the road could not admit joins a ledger row as a trigger to re-read the road.

**Displaces:** [ADR-002:54], [ADR-002:56], [ADR-002:60], [ADR-002:62], [ADR-002:70]

The three deltas are enumerated rather than blurred, per D-53's carve-out discipline and D-61's use of it. Two further edits are consequential repairs rather than decisions, and are listed after them.

### Delta 1 — property 4's two halves separate (#67 E1)

A falsifier and a review trigger are claims of different kinds, and one unit list served both. A **falsifier** asks *did it yield anything*, which must be counted in the trial's output. A **review trigger** asks *has it had enough chance to yield*, which is a claim about **opportunity** — and opportunity is exactly what units of work, pull requests and uses measure.

- **The inversion is the reason, and it is stated in the rule.** A trigger counted in the trial's own output cannot fire on a null trial, so the trial that most deserves cutting is the one whose review never arrives. Property 3 is inverted by property 4's counting rule, and no exception clause reaches that, because it is not an instrument problem.
- **The ban is kept where it was load-bearing.** Elapsed time still counts no yield and is still barred from a falsifier. What is dropped is the ban's reach into the trigger, where it had no purchase and produced laundering instead of discipline.
- **The trigger's unit is free and its size is not.** The owner grants the window at admission under property 5, so a generous one is a thing the owner declined to refuse. Property 4's warning that opportunity units are "the units a trigger will reach for first" was not baseless; the answer is that property 5 already holds that line, and no new bound is invented for it. **If trials start arriving with very generous triggers, that is this delta's failure and it earns a bound with a record behind it.**

### Delta 2 — property 6 is restated around its stated reason (#67 E2)

Property 6's reason was always the ratchet — "manufacturing exactly the record promotion demands." The reason is about *a record*; the text said *ledger rows*.

- **The obligation is untouched.** A trial still must produce, while it runs, the record its own promotion would demand, attributable to it. Only the assumption that the record is always a defect row is dropped.
- **The ledger stays the default**, with §8's optional `trial` token as the default attribution, so nothing changes for a trial whose evidence *is* defects — #28's spike among them, which under this delta needs no exception at all.
- **A named instrument is bound by three properties: durable, countable, attributable.** Those are what made the ledger fit, so they are what a substitute must show. The precedent for reaching outside the ledger is inside §2 already: property 3 reads the *review report* for whether a trial ran.
- **The instrument is part of what the owner admits**, and a trial whose instrument turns out not to count is cut like any other. This is where the delta's cost sits and it is not hidden: nothing checks an instrument's quality, and a badly chosen one yields a trial that cannot be cut — the accretion property 3 exists to prevent, entering through the door this delta opens.

### Delta 3 — a property may be excepted by naming what replaces it (#67 E3)

The owner's ruling of 2026-08-18 was that exceptions must at minimum be available.

- **The substitution requirement leads the rule**, because it is the load-bearing half. A waiver naming no substitute leaves property 3 nothing to fire on, and a trial nothing can cut is the furniture this road exists to prevent.
- **The exception is recorded with the marker** (property 2), so `git grep -in trial` reaches excepted trials alongside ordinary ones rather than splitting the class the marker exists to keep greppable together.
- **Four properties take no exception**, each for its own reason: 1, because excepting it admits rules as trials, the tax the road was built to exclude; 2, because a trial a reader cannot distinguish from earned prose is worse than no trial; 3, because excepting it excepts the point; 5, because it is the property that grants exceptions.
- **Naming the four rather than naming the two that *are* exceptable** keeps the rule true when a property is added later. Enumerating 4 and 6 as the exceptable pair would silently answer a question about any seventh property that nobody had asked.
- **Delta 2 is what keeps this an exception rather than a standing dispensation.** Without it, every prevention-shaped mechanism would need the same exception every time, which is a defect paid for repeatedly instead of fixed. The exception is left for the case delta 2 does not reach.

### Delta 4 — a failed admission joins the road's re-read trigger (#67 E4)

An admission that fails on a property is evidence about that property. A road too strong to admit anything produces no row, so a row-only trigger is unfalsifiable exactly where the road is wrong.

- **It is a norm and not an operation**, marked as such in the rule the way property 3 is. A failed admission leaves no record unless someone writes one; the first one written is this entry's own `## Evidence`.
- **Deleting the rule was the alternative and is worse.** The trigger was right to exist and wrong in its reach, and removing a re-read trigger on the evidence that it failed to fire moves in the wrong direction.

### Two consequential repairs, forced rather than chosen

Neither is an independent decision; each is a rule that becomes false the moment delta 2 lands.

1. **Enumeration is scoped.** *"[T]he live trials can be enumerated from the instrument itself"* stops being true once an instrument may not be the ledger. No new mechanism is needed: property 2's marker already enumerates instrument-independently, and `git grep -in trial` is the statute's own stated enumerator. So `SELECT DISTINCT trial` is scoped to ledger-instrument trials and the marker is named as the enumerator that reaches them all — one more thing property 2 is load-bearing for.
2. **Running clean is generalised.** *"The ledger alone cannot say a trial ran clean"* was written for a seat trial. The silence is general: any instrument recording only what a trial *found* cannot distinguish *ran and found nothing* from *never ran*. Property 3 now reads **the run record the trial names** for whether it ran, with the seat's review report kept as the named example rather than replaced, since it is the case the sentence was written for and the only one with a record.

Leaving either was rejected: §12's recorded concern is a governing sentence standing still while what it selects moves, and here both would be outright false rather than merely stale.

## Rejected

1. **The exception clause alone, leaving properties 4 and 6 as written** (#67 E0/A). Cheapest, and the only option that spends nothing on a single admission attempt. Rejected because it routes an entire class of mechanism — every one whose value is that something does not happen — through the owner's discretion on every admission, which is a standing waiver wearing an exception's clothes; §8's own reasoning about `unrecorded` applies, that a judged value with no lawful slot means the vocabulary is short and the fix is the vocabulary. It also leaves delta 1's inversion standing, which no instrument-shaped exception reaches.
2. **Deltas 1 and 2 without the re-read-trigger correction** (#67 E0/B). Rejected because that rule is now known false and sits inside the section being amended around it; and it is the rule that would otherwise be what catches the *next* over-strong property.
3. **Restating all six properties** (#67 E0/D). Four of them have no incident against them. Spending a real incident on a general rewrite is accretion in reverse.
4. **Widening property 4's single unit list to include units of work**, rather than splitting the two halves. Rejected because it drops the ban for the falsifier too, which is where the ban was load-bearing, leaving the property's reason covering nothing.
5. **Leaving property 4 and letting the exception clause absorb the inversion.** Rejected: the inversion is not an instrument problem, so every trial would file the same exception for the same reason.
6. **Letting a non-defect trial write non-defect rows into the ledger.** Rejected as barred by §8 in terms — it would be this decision breaking §8 to avoid amending §2.
7. **Keeping property 6 and routing prevention-shaped mechanisms through the exception each time.** Same objection as rejection 1, at one property's scope.
8. **A general exception clause with no properties carved out.** Rejected: stated generally it reaches properties where an exception is not a relaxation but a repeal — property 1 admits rules as trials, property 2 makes a trial indistinguishable from earned prose, property 3 is the point, and property 5 is incoherent to except since it grants the exceptions.
9. **Naming properties 4 and 6 as the only exceptable ones.** More honest about today and worse about tomorrow: a seventh property would inherit an answer nobody decided.
10. **Deleting the road's re-read trigger** (#67 E4/B). See delta 4.
11. **Leaving the enumeration claim and the *ran clean* rule to a reader to reconcile.** Both would be false, not stale.
12. **Folding this change into #28.** Declined by the owner on 2026-08-18: #28's own D0 and D6 turn on the properties amended here, so #28 waits and is rewritten against landed text rather than reasoning about pending text. #28 is [recorded as held](https://github.com/Grimblaz-and-Friends/tradecraft/issues/28#issuecomment-5336439852).
13. **A guard on any of this.** Whether a named instrument is durable, countable and attributable, and whether an exception's substitute is real, are correspondence — §12 puts that in review's hands, and §2 earns code by recurrence rather than plausibility.

## Evidence

- **The failed admission**, and the first record of delta 4's second event: [#28](https://github.com/Grimblaz-and-Friends/tradecraft/issues/28), pre-implementation artifact at [comment 5336236201](https://github.com/Grimblaz-and-Friends/tradecraft/issues/28#issuecomment-5336236201) — its `D0` records property 6 forcing the narrowing, its `D6` records the property 4 proxy and the trigger inversion.
- **This change's own artifact, affirmation and amendment**: [#67](https://github.com/Grimblaz-and-Friends/tradecraft/issues/67), artifact at [comment 5336437362](https://github.com/Grimblaz-and-Friends/tradecraft/issues/67#issuecomment-5336437362), affirmation record at [comment 5336705518](https://github.com/Grimblaz-and-Friends/tradecraft/issues/67#issuecomment-5336705518).
- **Owner-reported prior recurrence**, uncaptured at the time and registered at recollection grade: the *"requirement that cannot express its own finding"* row in [`evidence.md`](../evidence.md). It is corroboration and not the support this decision rests on, per that registry's rule that nothing recollection-grade may be a mandate's sole support.
- **The class this is the fourth instance of**, with its three prior ones: `ADR-002-material-lifecycle.md`'s *"an evidence loop whose instrument cannot express the finding it tests for is not evidence"*, citing [PR #6](https://github.com/Grimblaz-and-Friends/tradecraft/pull/6) and [PR #12](https://github.com/Grimblaz-and-Friends/tradecraft/pull/12).
- **The state of the instrument at decision time** — 819 ledger rows, 68 distinct `source` values, zero carrying a `trial` token. Re-run from the repository root: `python -c "import json,collections;r=[json.loads(l) for l in open('docs/ledger.jsonl',encoding='utf-8') if l.strip()];print(len(r),len({x['source'] for x in r}),sum(1 for x in r if 'trial' in x))"`
- **§8's refusal that closes rejection 6**: *"no defect ledger can carry it without admitting non-defect rows and becoming a different instrument."*

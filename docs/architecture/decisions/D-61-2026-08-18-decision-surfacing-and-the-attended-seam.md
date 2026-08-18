# D-61: Decision surfacing carries argued options, and the opening seam's question is attended-only

**Status:** Accepted 2026-08-18 (PR #61)

## Context

Two defects in the statute's text, landing together because they collide on one paragraph: [#45](https://github.com/Grimblaz-and-Friends/tradecraft/issues/45) rewrites §7's resurfacing rule and [#44](https://github.com/Grimblaz-and-Friends/tradecraft/issues/44) rewrites the `owner-pending` scoping rule immediately below it, and both also reach §5.

**The surfacing defect has an incident.** The largest `owner-pending` batch yet put to the owner, and the first to draw an objection — four rows, `M1`@`pr30-panel-2026-08-17` and `O4`/`O7`/`O11`@`pr34-panel-2026-08-17`, surfaced at the opening seam of [#42](https://github.com/Grimblaz-and-Friends/tradecraft/issues/42)'s design review — arrived as four single recommendations. The owner stopped and asked for alternatives before deciding the first of them: *"a recommendation is helpful, but I need choices with pros and cons or I'm not truly making informed decisions."* The surfacing itself left no primary record — this account is reconstructed from #44's body, written by the session that ran it, and the owner's words are quoted verbatim from there. The surfacing followed the text faithfully, which is what makes this a defect in the text rather than in the session. The sentence it followed — *"An agent that surfaces such a row owes a recommendation, not a menu"* — was aimed against menus-without-judgment, but read literally it licenses recommendation-without-alternatives. The new standard is the superset of both halves, not a reversal of either.

**The seam defect is an internal contradiction, not only a drift.** §6 said the seam *"does lawfully ask"* without qualification and §7 said *"every review's"* opening ledger read puts the question, while §5 says the unattended lane *"asks zero questions by construction"* and `skills/adversarial-review/SKILL.md`'s seam question has been attended-only since [PR #30](https://github.com/Grimblaz-and-Friends/tradecraft/pull/30). Three surfaces, three positions, and two of them inside this statute — so the conflict could not be repaired by aligning the skill to the rulebook, because the rulebook disagreed with itself. The owner had already ruled option A on the skill-vs-statute question, conversationally on 2026-08-18, from three argued alternatives recorded on #45.

**Delta 2 binds a class that is presently empty.** The ledger holds zero open `owner-pending` rows; #42's four were re-dispositioned in its bookkeeping commit ([PR #47](https://github.com/Grimblaz-and-Friends/tradecraft/pull/47)), so no held row is disturbed by the seam's rescoping and no urgency is claimed for it. **Delta 1 is not so bounded**: it is surface-agnostic by design, so the next gate any session opens is bound by it.

## Decision

**Statute delta:** A decision put to the owner carries the live options with their pros and cons and the recommendation among them — stated once in §5, with §5's third answer and §7's `owner-pending` scoping rule delegating to it — and the opening ledger read's batched question becomes attended-only, an unattended run reading the ledger for shape evidence, leaving the rows, and putting no question.

**Displaces:** [ADR-005:23], [ADR-006:56], [ADR-006:61], [ADR-006:63]

The two deltas are enumerated rather than blurred. Bundling two rule changes under one entry is the shape D-53's carve-out class exists to distrust; what that class actually forbids is a rule change smuggled in as something else, and the answer to it is naming each one, which is what follows.

### Delta 1 — the surfacing form (#44)

**A new rule in §5**, placed directly after the attended-lane question rule so that *argued* is defined immediately where the statute demands it of a question: a decision put to the owner carries the live options, each with its pros and cons, and the recommendation among them.

- **One definitional home, and the other sites delegate.** §5's third answer now reads *reasoning over the alternatives*, and §7's `owner-pending` scoping rule points at §5's form in place of the sentence it retires. Restating the standard at all three sites was rejected: the `M5` twin-site class is this repository's recorded incident and D-53 spent a whole restructure collapsing five such twins.
- **The scope is surface-agnostic** — a gate, an argued-case batch, an `owner-pending` surfacing, a typed halt report, a decision raised in conversation. What makes a decision informed does not vary by the surface it arrives on, and the narrower reading would have left the typed halt report — the unattended lane's only decision surface — outside a rule about informed deciding, for no stated reason.
- **The one-live-option clause is deliberate and is not an escape hatch.** Where exactly one option is live, the surfacing says so and says what it rejected **and why** — the reasoning is what makes the branch informative, and without it the cheap branch would carry less than the bare recommendation this rule replaces. Without the clause the rule reads as an absolute, and a session facing a genuine single-option case either fabricates alternatives or violates the rule — and a fabricated pair under-informs *worse* than the bare recommendation it was added to cure, because it presents a search that did not happen.
- **No guard ships.** Whether a surfacing actually presented alternatives is correspondence, which §12 puts in review's hands; a form check could see only that some options were listed, which is the failure mode rather than the rule. §2's promotion road stays open if it recurs.

### Delta 2 — the seam is attended-only (#45)

**§6's one-seam rule and §7's resurfacing rule are both scoped to attended reviews**, and both now state what an unattended run does instead: read the ledger for its shape evidence, leave the rows as they are, put no question.

- **This resolves a contradiction, not merely a drift.** §6's unqualified *does lawfully ask* asserted an exception to §5's zero-questions construction that §5 does not grant. After this change no statute rule contradicts it.
- **The aging backstop is untouched.** *Several such surfacings → `recorded`* keeps its threshold and its vagueness. What is added is the consequence that makes the existing word safe: an unattended run puts no question **and so is not a surfacing**. The amendment is what creates, *in this statute*, reviews that are not surfacings — the skill has produced them since #30 — so it is the amendment's business to say so.
- **The §6/§7 twin is kept, and that asymmetry with delta 1 is deliberate.** Both sections stated the seam rule at the merge base, cross-pointing at each other, so this change widens a twin it did not create; collapsing it would retire a rule in a section this decision is not otherwise amending, which is a second change smuggled into one.
- **The seam fails closed where the lane is undetermined**, both rules treating such a run as unattended. Added on the owner's ruling of 2026-08-18, surfaced with three argued options after this change's own review sustained that *attended* is load-bearing here and defined nowhere in the repository. It is the cheaper direction: a question wrongly withheld waits on a durable row, where a question wrongly put breaches §5 outright. **This amends the affirmed artifact's boundary statement**, which had put the lane set out of scope; nothing else in that boundary moves.
- **The skill's fuller gloss was not copied into the statute.** `SKILL.md` says *"surfacings, not reviews, since a run that skipped the seam never put the question and cannot count against it"*; the clause above delivers the same distinction where it is created, without buying a third structurally forced twin for it.

### The shipped zone, and the twin this decision accepts

`skills/adversarial-review/SKILL.md` instructed *"batch those open rows into one argued question"* and defined **argued** nowhere. Before this decision that cost little. After it, *argued* means a specific form, and ADR-004's wall guarantees a consumer running the skill without this repository's `docs/` cannot reach the statute that states it — so the gap is **widened by this decision rather than inherited by it**, and is fixed here. The skill now states the form in its own words.

**The duplication is structural, not chosen**, exactly as D-53's `sustained` gloss is: delegation is unavailable in that direction because the wall forbids the skill citing `docs/`. It therefore ships with the maintenance rule that makes duplication safe, stated at **both** sites — in §5 as D-53 put its own, and in the skill, which cannot cite this document — **a change to the form lands at both sites in the same change.** The plugin version rises to `0.13.0` accordingly.

Filing the skill's half as a follow-up was rejected as unlawful rather than merely unattractive: §7 permits filing only with both remedy homes rejected, and the fix-here home was available and cheap.

## Rejected

1. **Two pull requests, sequenced or concurrent.** #44 and #45 rewrite adjacent lines of one §7 block and both touch §5, so separate changes conflict textually and each must reason about the other's unlanded text; #44's standard governs how #45's own decision is surfaced, so building them apart means applying a rule from an unmerged pull request. The bundling objection is answered by enumeration above, not by separation.
2. **Restating the surfacing form at each of its three sites.** Three twins of a rule certain to be revised, in the file whose last amendment was a restructure to kill twins — the `M5` defect, chosen deliberately.
3. **Folding the form into §5's existing attended-lane rule with no new rule unit.** §12's identity model keys on the bold lead-in, so a standard with no lead-in of its own cannot be cited, superseded, or found; it would be unfindable inside a lane rule.
4. **Narrowing the form to the three surfaces #44 enumerates**, or to gates alone. The first excludes the typed halt report for no stated reason; the second excludes the `owner-pending` batch, which is the case that earned the rule.
5. **Silence on the one-live-option case, or a hard floor of two or more options always.** The first leaves the rule unstatable in a case that will arise; the second mandates the fabrication the rule exists to prevent, and contradicts §5's *confirmation of the predictable: do not ask*.
6. **Copying `SKILL.md`'s full "surfacings, not reviews" gloss into the statute** with D-53's twin-maintenance rule attached. A third forced twin plus its standing obligation, bought for a distinction the shorter clause already delivers.
7. **Leaving `skills/adversarial-review/SKILL.md` untouched.** It would knowingly ship a skill whose central instruction has a meaning stated only in the repo-only zone — precisely the failure ADR-004's wall exists to prevent.
8. **Filing the skill's half as a follow-up issue.** Fails §7's filing precondition, both remedy homes not having been rejected — which makes it filing by default, the practice that section exists to prevent.
9. **Reverting the skill and typed-halting unattended reviews at the seam** — #45's option B, declined by the owner. Dominated: the halt delivers the question no sooner than the durable row already does, and costs the unattended lane its purpose.
10. **A passive line in every unattended run's report listing open `owner-pending` rows** — #45's option C, deferred by the owner as the evidence-earned add-on if rows demonstrably age ("A for now"). Not built here, and not filed; it returns if the evidence arrives.
11. **A guard on question form.** See delta 1.
12. **Defining `attended` with a test**, rather than stating a fail-closed direction — declined by the owner: it closes the gap outright but costs a new rule unit and lead-in and changes what this decision decides, and §2 does not earn a rule for a distinction judgment carries until an incident says otherwise.
13. **Leaving the lane question to judgment**, keeping the `owner-pending` row open — declined by the owner: free, and the class is presently empty, but the record could then not distinguish a lawful skip from a wrong guess, which is the defect `SKILL.md`'s seam-polarity line prevents one level down.

## Evidence

- The incident that earns delta 1, and the joint pre-implementation artifact built to the standard it proposes: [#44](https://github.com/Grimblaz-and-Friends/tradecraft/issues/44), artifact at [comment 5334235731](https://github.com/Grimblaz-and-Friends/tradecraft/issues/44#issuecomment-5334235731), owner affirmation at [comment 5334277801](https://github.com/Grimblaz-and-Friends/tradecraft/issues/44#issuecomment-5334277801).
- The seam conflict, its three argued alternatives, and the owner's recorded option-A ruling: [#45](https://github.com/Grimblaz-and-Friends/tradecraft/issues/45).
- The rows whose surfacing produced the incident: `M1`@`pr30-panel-2026-08-17` and `O4`/`O7`/`O11`@`pr34-panel-2026-08-17` in `docs/ledger.jsonl`, all re-dispositioned in [PR #47](https://github.com/Grimblaz-and-Friends/tradecraft/pull/47).
- The skill behaviour the statute is aligned to, and the change that introduced it: `skills/adversarial-review/SKILL.md`, [PR #30](https://github.com/Grimblaz-and-Friends/tradecraft/pull/30).
- The twin-site class both the delegation choice and the accepted skill twin are argued against: (`pr19-panel-2026-08-17`, `M5`) in `docs/ledger.jsonl`, and D-53's *One twin deliberately kept*.
- The design review whose opening seam surfaced both defects: [#42](https://github.com/Grimblaz-and-Friends/tradecraft/issues/42).

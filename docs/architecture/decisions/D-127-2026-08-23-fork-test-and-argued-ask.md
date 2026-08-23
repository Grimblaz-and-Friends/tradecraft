# D-127: A decision is the owner's when it is a genuine fork, and the argued form governs every ask

**Status:** Accepted 2026-08-23 (PR #127)

## Context

The doctrine's `Review` section said: *"A decision only the owner can make is put to the owner argued — the live options, each with pros and cons, and a recommendation."* It asserted a form for a class it never defined. Nothing in the repository said what made a decision one only he could make, so the classification ran on session temperament and failed in both directions — sessions pre-clearing calls that were theirs to make, and sessions making calls he would have wanted. The owner named both failure modes on [#86](https://github.com/Grimblaz-and-Friends/tradecraft/issues/86) and settled the rule in conversation on 2026-08-20; the fabricated-gate half he had already stated in his global guidance, where *"a permission-to-proceed dressed as a judgment call is a fabricated gate"* is called out as something he had to say directly.

The form itself was not new. [D-61](D-61-2026-08-18-decision-surfacing-and-the-attended-seam.md) established it after the largest owner-pending batch yet put to him arrived as four bare recommendations and he stopped to say *"I need choices with pros and cons or I'm not truly making informed decisions."* What that decision could not do was define the class the form applies to, and it placed the rule inside a statute section about surfacing. Through the constitutional reset [D-74] the form survived into the doctrine's `Review` section — correct text, wrong scope: read where it sat, it governed findings.

**A shipped-zone gap sat on the same rule.** `skills/engagement` said anything needing the owner before PR review *"is put to him argued, on the existing rule"* and named no rule. The rule lived in root doctrine, which for a consumer who installs the plugin is their own file, not this one — so the cell shipped an instruction whose meaning it could not deliver. That is precisely the failure [D-61] fixed for `adversarial-review`, by making that skill state the form in its own words; `engagement` was written afterward and did not inherit the lesson.

## Decision

**The fork test lands in `Authority`, and the argued form travels with it.** A decision is the owner's when the live options differ in something he would care about **and** the wrong pick is not cheaply reversible; everything else the session decides and reports afterward with its reason, and asking where no fork exists is named as a defect rather than politeness. `Review` keeps its findings rule and loses the argued-form clause, which was never about review.

Two conjunctive halves, deliberately. Irreversibility alone — the alternative already half in place — misses the reversible-but-he-cares class: naming, daily experience, scope drift, which is exactly the class going wrong. Care alone would route everything.

**`Authority` rather than a new section**, because that section already carries the owner relationship and the plain brief the argued form sits on top of. The form is stated once and no site restates it — the twin-avoidance [D-61] spent its own restructure on.

**`skills/engagement` carries the calibration, the single-live-option case, and the report shape.** The cell already claimed *"any decision put to the owner"* as one of its two surfaces while giving it no section; it has one now. Three contents beyond the doctrine's test:

1. **Anchor examples**, one set per side plus the fabricated-gate tell — the session already holding a clear recommendation with no live alternative beside it.
2. **The single-live-option clause**, carried from [D-61]'s reasoning: without it the rule reads as an absolute, and a session facing a genuine single-option case either fabricates an alternative or violates the rule — and a fabricated pair under-informs worse than none, presenting a search that did not happen.
3. **The report-with-reason shape**, naming only surfaces that already exist — the PR body, the decision entry, the review report — and never only in chat. Deciding is licensed by the fork test; the report is what stops *decide and report* from degrading into *decide silently*.

The cell's purpose header moved in the same change, per `authoring`'s recheck rule: the skill now governs which decisions reach him at all, not only how the surfaces he enters read.

**Why the split falls there — the budget decided it, not taste.** `AGENTS.md` was 7,419 of 8,000 characters. The test measures net +284 and lands at 7,767; the anchor examples do not also fit. Doctrine's own admission ladder puts skill prose ahead of a doctrine line, so the examples went where the ladder points. The accepted cost is stated plainly: a session running without `engagement` loaded holds the test uncalibrated. The owner settled this at convergence.

**Admitted** on [D-77](D-77-2026-08-19-owner-approval-admission-path.md)'s owner-approval path — he stated the rule and affirmed its wording.

**Consumed downstream.** [#118](https://github.com/Grimblaz-and-Friends/tradecraft/issues/118)'s value check is a proceed/park/decline fork by this test, and its output shape is the argued form above; that issue's pickup reads this entry rather than re-deriving it. Nothing here decides anything for #118 or [#103](https://github.com/Grimblaz-and-Friends/tradecraft/issues/103).

## Rejected

- **An enumerated list of owner decisions**, everything unlisted the session's. Unambiguous, but lists go stale, novel decisions land on the wrong side by default, and the list grows the doctrine permanently. The hybrid actually chosen keeps anchor examples as calibration without letting them define.
- **Irreversibility only** — ask for irreversible or outward-facing acts and nothing else. Minimal, and half in place already, but it misses the class the issue was filed about. See the conjunction above.
- **The anchor examples in the doctrine, displacing another line to make room.** Calibration would bind before any context loads, which is the whole argument for doctrine placement. Declined by the owner: it makes this change carry an eviction argument it did not earn, which is a second decision smuggled into one.
- **A compressed tell-only line in the doctrine**, fuller examples in the skill, at roughly 120 characters. Offered as the cheapest real upgrade and declined — an asymmetric split with a standing maintenance cost, for the half the skill already carries.
- **Dropping the report-with-reason shape**, on the ground that the PR body already carries it in practice. Declined by the owner: the issue asked the artifact to settle it, and relying on established practice is what the fork test exists to stop relying on.
- **A guard.** Whether an ask actually presented live options is correspondence, which review judges; a form check could see only that some options were listed, which is the failure mode rather than the rule. [D-61] rejected a check on this exact rule and that reasoning is unchanged.
- **Touching `adversarial-review`'s copy of the form.** It is correct, [D-61] argued its duplication as structural — the zone wall forbids the skill citing a document it cannot reach — and re-opening it is a second change.

## Evidence

- [#86](https://github.com/Grimblaz-and-Friends/tradecraft/issues/86) — the settled artifact at [comment 5385760026](https://github.com/Grimblaz-and-Friends/tradecraft/issues/86#issuecomment-5385760026), affirmation at [comment 5385760419](https://github.com/Grimblaz-and-Friends/tradecraft/issues/86#issuecomment-5385760419).
- The incident that earned the argued form, and the owner's words: [D-61](D-61-2026-08-18-decision-surfacing-and-the-attended-seam.md) § Context.
- The dangling reference this change closes: `skills/engagement/SKILL.md` at the merge base, *"put to him argued, on the existing rule"*.
- The budget mechanism and its reason: `AGENTS_BUDGET_CHARS` in `tools/lint.py`.

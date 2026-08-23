# D-119: A cost estimate belongs outside the artifact, and two issues were closed by testing their premise instead of arguing it

**Status:** Accepted 2026-08-23 (PR #119)

## Context

Three issues were picked up as a group — [#112](https://github.com/Grimblaz-and-Friends/tradecraft/issues/112), [#115](https://github.com/Grimblaz-and-Friends/tradecraft/issues/115), [#117](https://github.com/Grimblaz-and-Friends/tradecraft/issues/117) — and the group is why only one of them is built here. #115 and #117 target the same term of `skills/adversarial-review/SKILL.md:65`; #112 declared itself **conditional** on #115's outcome (*"if #115 lands a remedy that fills the vacuum, this one may become unnecessary"*). That conditionality is what made the grouping worth doing: #115's outcome decides #112's scope and could not be known without testing it.

### The defect that was real

[D-107](D-107-2026-08-22-price-is-implementation-cost.md) item 6 gave `skills/engagement` the upstream rule: a cost estimate *"belongs **outside** the numbered criteria — in the artifact's own prose, the PR body, the decision entry, or the report. Written into a criterion it becomes what every stage of the review judges against."*

**The reason clause names typographic position; the mechanism is delivery.** For an implementation the affirmed artifact *is* the assignment, carried whole, so the authorised placement and the forbidden one reach every seat by the same route. D-107's own account of its criterion 7 names the vector as *"the review's shared block"* and then lands a rule that partitions the artifact instead.

**It fired one day later.** PR #113's artifact led its cost section with a forecast, written in deliberate compliance — outside the numbered criteria, labelled a fact — and the owner struck it. [D-113](D-113-2026-08-22-component-sign-and-purpose-statement.md) records that had it been dispatched, five seats would have read it.

### The premise that was not

#115's thesis is a falsifiable sentence: *a price has two named terms and only one can be computed, so a session pricing a remedy reaches for the count.* It is also D-107's recorded reopen condition. `skills/engagement/references/spikes.md` fires on **a mechanism nobody has executed**, and pricing under a re-worded clause is exactly that — so it was tested before the artifact asserted anything about it, and tested by parties other than the session that drafted the wording.

## Decision

**One sentence changed, in one shipped file. Nothing else ships.**

1. **`skills/engagement`'s acceptance-criteria bullet bars the artifact entirely**, and states the delivery reason rather than the positional one: *"a cost estimate belongs **outside the artifact** — in the PR body, the decision entry, or the report — because the whole artifact reaches every stage of the review, so a figure anywhere in it becomes what they judge against."*
2. **`skills/adversarial-review/SKILL.md` is byte-identical to `main`.** `:65` is not reopened. This was an acceptance criterion, not an omission.
3. **#115 and #117 are closed**, with the spike as the record and reopen conditions neither issue previously had.
4. **The defect the spike actually found is filed as [#121](https://github.com/Grimblaz-and-Friends/tradecraft/issues/121)**, not fixed here.

**The forecast breach closes without a second rule.** #112 listed *"keep the placement rule and add the forecast bar"* as a candidate. It is unnecessary: every surviving placement — PR body, decision entry, report — is written at or after landing, so a count over a tree that does not yet exist has nowhere lawful to live. `:57`'s principle is enforced by the container rather than restated.

**What the change costs the owner, recorded because it is the real objection.** He loses a cost signal at the convergence gate, which #112 named as the one moment he might legitimately want one. It is accepted because the only such signal ever produced was struck by him as the reflex it was, and because a forecast over a tree that does not exist was never evidence — `:57` says so on its face.

### The spike, and what it settled

Four cold dispatches, Opus 5, reading only a copy of `skills/adversarial-review/SKILL.md` and a four-remedy docket — no issues, no decision log, no git history. Two arms, differing **only** in `:65`'s second term: the shipped wording, and a candidate carrying a shape vocabulary and a `releases` trigger. The [report](https://github.com/Grimblaz-and-Friends/tradecraft/issues/115#issuecomment-5384143581) carries the method, the docket, and the seats' own words.

**#115's premise fell: zero word counts, four of four, both arms.** Every seat stated the obligation term in prose, with discrimination — *"a permanent per-ruling tax whose enforcement is entirely on reader judgment"*, *"the obligation created has no owner"*. D-107's reopen condition was tested and did not fire. **The falsification reaches the defense stage only**; occasion 3 was seat reports and occasion 4 was an artifact, and neither was tested. That limit is written into #115's closure as its reopen condition rather than smoothed over.

**#117's trap did not reproduce.** Its own exhibit — replacing `:37` with a one-liner carrying the same constraint — was priced by two seats reading the **unamended** trigger, and both declined the false credit: *"the term does not go negative: no rule or guard is removed, only its determinacy."* Closed as armor under `authoring`'s rule, whose test is whether the reader errs. PR #113's defense had already scored the filed evidence as *"a lower bar than the one D-113 itself paid to clear."*

**The candidate wording was withdrawn on its own evidence, and this is recorded because it was a near miss.** The shape vocabulary was adopted fluently by both arm-B seats — *"Standing, per routed finding, carried by the terminal stage"* — and solved nothing the file has. Its `releases an obligation later sessions carry` trigger let one seat of two count **reading** as a released obligation (*"the read saving is once-per-session"*), which would have readmitted prose's cost of existing as a price channel and undone the `{rule, guard}` narrowing D-107 made deliberately and D-113 restated. The other seat explicitly refused the same move, so the wording was under-determined rather than simply wrong — which is the harder failure to catch, and a review reading a diff would have had to reconstruct both readings to find it.

**Four of four seats independently named a defect neither issue asked about.** Asked what was hardest to state, every seat, unprompted, in both arms, named the obligation term's **sign**: it takes one value while a remedy routinely releases one obligation and creates another **on a different carrier**. #117 is its narrow case. **It is not fixed here** — every seat stated a defensible price anyway, so the clause is awkward rather than wrong, and fixing it would be the third rewrite of `:65` in four days inside the paragraph D-113 landed to settle. The owner was offered the immediate fix at the gate and declined it in favour of filing. Vehicle: [#121](https://github.com/Grimblaz-and-Friends/tradecraft/issues/121).

## Rejected

- **Building #115's shape vocabulary.** Tested, adopted, and it addressed a vacuum the spike says does not exist at the stage the issue diagnosed. Cost without a defect to justify it.
- **Building #117's net formulation.** Its motivating reader did not err across two cold seats on its own exhibit. `authoring`'s no-armor rule is dispositive, and the netting question it raises is answered in #121 without depending on a trigger nobody misreads.
- **Fixing the sign defect in this change.** Argued at the gate with pros and cons; the owner declined it. Against it: a third `:65` rewrite in four days, D-113's cost rows invalidated, and `:59`, `:67`(b), `:71`, `:75` and `:79` all consume *the price* and would need re-reading. For it: the evidence is unanimous and fresher than the single external reviewer that justified D-113's own restatement. A close call, recorded as one.
- **Moving the rule to `adversarial-review`'s dispatch contract** (#112's second candidate). It splits one idea across two cells and lands it in the paragraph with the worst amendment record in the repo. The rule is about what an artifact author writes, so it belongs where artifact authors read — D-90's placement argument, which D-107 invoked twice and once got wrong for exactly this reason.
- **Adding a separate forecast bar** (#112's third candidate). Redundant once the container closes; `authoring` forbids prose that can drift, and two rules about one figure is that shape.
- **Leaving #112 to `:17` at review time** (#112's fourth candidate). That is evidence about what the owner catches, not about what the rule requires — the distinction [#94](https://github.com/Grimblaz-and-Friends/tradecraft/issues/94) is this repo's worked example of.
- **Publishing a cost estimate in this change's artifact.** The artifact states none, and says so as its own acceptance criterion. The rule being landed is the reason.

## Deferred, with the evidence that would reopen them

- **The falsification does not reach seat reports or pre-implementation artifacts.** Those are the two stages #115's occasions 3 and 4 actually occurred at, and the spike tested neither. **Reopen on:** a seat report or an artifact carrying a count after this change lands. This is #115's closure condition and it is the weakest point in the case for closing it.
- **Two seats is a thin basis for closing #117.** Neither was told to price adversarially, and a replacement of a *guard* rather than governing prose was never put to them. **Reopen on:** any stage or external reviewer crediting a replacement as a release.
- **The PR body remains a lawful home for a figure, and a PR body can be read by a reviewer.** The external pass reads the diff and the PR; the dispatch contract does not carry the PR body to seats, so the propagation path this change closes stays closed. **Reopen on:** a dispatch carrying a PR body, or an external reviewer's finding shown to turn on a figure in one.
- **Nothing verifies that a `[D-N]` citation resolves**, and this entry ships none into the shipped zone — the amended bullet carries no citation, so a session changing it reaches this entry only through the PR. That is the same gap [#109](https://github.com/Grimblaz-and-Friends/tradecraft/issues/109) carries, in a shape it does not name. **Reopen on:** #109 landing, or a session amending this bullet without finding this entry.
- **The spike's own arms are gone by rule.** `spikes.md` requires a spike commit nothing, so the two file copies and the docket are not reproducible except from the report's quotation of them. A later session doubting the result must re-run it rather than inspect it. **Reopen on:** nothing — this is the standing cost of the spike rule, recorded so a reader does not go looking for the tree.

## Evidence

[#112](https://github.com/Grimblaz-and-Friends/tradecraft/issues/112), [#115](https://github.com/Grimblaz-and-Friends/tradecraft/issues/115), [#117](https://github.com/Grimblaz-and-Friends/tradecraft/issues/117), and [#121](https://github.com/Grimblaz-and-Friends/tradecraft/issues/121). The [spike report](https://github.com/Grimblaz-and-Friends/tradecraft/issues/115#issuecomment-5384143581) with its method, docket, arms and seat quotations; the [pre-implementation artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/112#issuecomment-5384150664) and its [affirmation record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/112#issuecomment-5384162562), which carries the declined alternative. [D-107](D-107-2026-08-22-price-is-implementation-cost.md) item 6, its account of criterion 7 and of #91's criterion 5, its `{rule, guard}` narrowing and its reopen condition on word-pricing. [D-113](D-113-2026-08-22-component-sign-and-purpose-statement.md) for the struck forecast, the two issues it filed, and its Decision item 1. PR #113's [defense report](https://github.com/Grimblaz-and-Friends/tradecraft/pull/113#issuecomment-5383879772) (M7's severity reasoning). `skills/authoring`'s no-armor rule and its no-drift rule; `skills/engagement/references/spikes.md` on when a spike fires and what it may leave behind.

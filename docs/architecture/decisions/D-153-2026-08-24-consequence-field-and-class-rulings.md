# D-153: A finding names what goes wrong if it stands, and that decides whether it is ruled alone or with its class

**Status:** Accepted 2026-08-24 (PR #153)

## Context

The review's cost had never been measured against what it bought. #138 measured both: **~184 staffed dispatches across the twenty reviews in `docs/reviews.jsonl` at `3175369`**, and a set of experiments turning the practice's own instruments on the pipeline. Three results bear on this change.

**Finding volume measures the instrument, not the artifact.** A single cold pass returned six findings against a defective revision and six against the same artifact after roughly fifty sustained findings had been repaired — severity collapsed to nothing, the count did not move. Across the whole index, sustained count against change size gives a Pearson correlation of **−0.02**, and 5 of 143 seat-dispatches ever returned zero findings.

**Almost nothing a fix batch lands reaches a consumer.** Cold seats working a realistic docket over the pre-review and post-fix revisions of one shipped cell behaved identically but for a single instruction change — about two of fifty sustained findings left a behavioral trace.

**The cost is per-finding processing, not panel width.** Each filed finding obliges a defense re-read and re-probe, a terminal ruling of its own, a fix, and a post-fix re-derivation. The owner's own exhibit was a single-seat post-fix round running over an hour, and the first full-pipeline field run put a number beside it: two fields on a JSONL row cost twelve dispatches, three terminal rulings, ~1.5M subagent tokens, with the panel earning its cost in round one and the two post-fix cycles not.

That field run also named a second failure the churn diagnosis in #122 does not cover. Its gap 3: both post-fix cycles found defects that were **real, probe-backed and correctly arbitrated**, with zero defects in the mechanism after the first fix batch — the questions were arbitrable and the answers right, and the *subject* had drifted from the change to the record of reviewing it. Its gap 5, routed to this issue by the owner, is the missing terminus for exactly that.

**Width is deliberately untouched.** The owner ruled on 2026-08-23 that lane choice and panel width wait until he has experienced these changes across several issues. The evidence would have supported a narrowing argument; his ruling is that experience comes first, and this change respects it.

## Decision

Five amendments, all inside existing sections of `skills/adversarial-review/SKILL.md`. No new section, no new stage, no new record.

**The consequence field.** A finding names the concrete consequence of standing unfixed — the action a consumer would take wrongly, or the failure that would occur. Coverage-first is byte-unchanged and nothing true goes unfiled: the field is a required part of a finding, never a licence to withhold one.

**Its claim is narrowed to what the evidence supports.** The spike's class arm classified all thirty-five docket items with **no explicit consequence field present**, inferring shape from the findings' wording. So the field does not enable the classing, and this entry does not claim it does. What it buys is that the finder states the consequence rather than a later stage inferring it, which is what makes the routing auditable — a distinction worth recording because the artifact as first drafted claimed more.

**Classing at the merge, with a guaranteed exemption.** Findings sharing a consequence shape and a remedy shape form one class. **Per-item treatment is guaranteed for every high, every medium, and every behavioral or executable consequence.** That guarantee is the safety of the whole mechanism: severity is the channel the evidence shows tracking the artifact rather than the instrument, so a saving taken from it is taken from the only output a review is known to vary.

**One price and one ruling per class, and severance as a duty.** The severance clause was drafted as a permission — *any member may be pulled out* — and the spike falsified that wording in the only way it could be falsified: the class arm dismissed two `low` record corrections the per-item arm fixed, both in a decision entry that freezes on merge, with severance available and unused. A permission a stage may decline is not a safeguard against a stage's own reasoning. It is now a duty, with two limbs: a member whose remedy is materially cheaper than its class's, and a member landing in a record that freezes.

**The post-fix look gets a bound and a second terminus.** It reads the fix diff and each sustained high's territory rather than the artifact over again. The next-pass ruling gains the **relevance terminus** — a pass continues only while the findings it expects are about the artifact, and a look returning only apparatus-facing material names that as the reason it stops. The count terminus is byte-unchanged and whichever fires first ends the cycle.

**A class ruling books its members, not itself.** `docs/reviews.jsonl`'s `dispositions` [D-136] is copied from the terminal ruling; under classing a copied count would book one where the same review booked nine a week earlier. Members are what the field counts, and the class count rides in the report — the field keeps one meaning across the boundary rather than changing it silently on the day classing arrived.

**What is superseded, knowingly.** [D-102] set the terminal docket's unit as one ruling per merged finding and per uncarried seat entry. That unit now admits a class. D-102's reason — that the docket is set by rule rather than by the dispatcher — is untouched and is why classing happens at the parent-owned merge under a stated definition rather than at a stage's discretion. Untouched entirely: [D-107] and [D-113]'s price semantics, coverage-first, and both existing termini.

## The evidence, and what it cost

The spike ran two terminal stages over one thirty-five-item docket reconstructed from PR #131's review with every disposition and fix order stripped, arms differing only in the class clause. **Thirty-five rulings became twenty; twenty-eight of thirty-five dispositions agreed; no high or medium diverged.** PR #131 was chosen because it is the worst case for batching — zero highs, a bookkeeping-heavy docket, the profile where a class rule has most opportunity to swallow something real. It still cost two cheap fixes, which is what the severance duty is written to catch, and the run is reported with that cost rather than around it.

**Net growth on governing prose is argued, not hidden.** The change adds 3,202 characters across the governing corpus, derived by `python tools/figures.py --base origin/main` at `3bca5e6`. Five mechanisms each carry their reason, on the skill governing the practice's most expensive activity; a tightening pass before commit shed 129 characters of clauses that carried a reason twice.

## The declared assumption

**Defense pricing per class is untested.** The spike ran the terminal stage only. Its falsifier: a defense arm given the same docket under class rules, compared against the per-item defense's prices. It is runnable against the same material, and this entry records the limb as assumed rather than shown.

## The seam

The post-fix look is scoped to include the review's own bookkeeping, while the relevance terminus stops a cycle returning only apparatus-facing material. These are compatible — bookkeeping is part of what a fix touched, and a *cycle* yielding nothing else has finished — but it is the change's least crisp joint, and it is named here rather than left to be discovered.

## What this does not close

The consequence field gives #122's failure mode 3 the distinction its field run found missing — nothing before this told an apparatus-facing finding from a product-facing one — but only in the report, not in the index, so the trend that issue says to watch still cannot be queried. Whether it should be a row field is #126's territory, not this change's.

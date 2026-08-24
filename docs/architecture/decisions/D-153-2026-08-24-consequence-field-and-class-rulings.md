# D-153: A finding names what goes wrong if it stands, and the batching that was built on top of it was measured and cut

**Status:** Accepted 2026-08-24 (PR #153)

## Context

The review's cost had never been measured against what it bought. #138 measured both, over the **twenty rows `docs/reviews.jsonl` held while that exploration ran** — `pr-74` through `pr-135`, before `pr-136` and `pr-141` were appended; at this change's merge base `3175369` the file already holds 22 rows and 160 seat entries, so every figure below re-derives only against `rows[:20]` and is stated that way rather than pinned to a tree it does not describe. On that corpus: **~184 staffed dispatches**, taken from the twenty posted reports' own stage tables rather than from the index — the index carries seat entries (143 over those rows), not dispatches, and no query over it returns 184.

**Finding volume measures the instrument, not the artifact.** A single cold pass returned six findings against a defective revision and six against the same artifact after roughly fifty sustained findings had been repaired — severity collapsed to nothing, the count did not move. Across those twenty rows, **5 of 143 seat-dispatches** ever returned zero findings — `python -c "import json; rows=[json.loads(l) for l in open('docs/reviews.jsonl',encoding='utf-8') if l.strip()][:20]; print(sum(len(r['seats']) for r in rows), sum(1 for r in rows for v in r['seats'].values() if v.get('raw')==0))"`. And sustained count against change size gives a Pearson correlation of **−0.02**, where *change size* is the PR's `additions + deletions` from `gh pr view <n> --json additions,deletions` paired with the row's summed `sustained`; the index carries no size column, so that pairing is the query and it must be rebuilt to re-run.

**The cost is per-finding processing, not panel width.** Each filed finding obliges a defense re-read and re-probe, a defense price, a terminal ruling of its own, a fix, and a post-fix re-derivation. The owner's exhibit was a single-seat post-fix round running over an hour; the first full-pipeline field run put a number beside it — two fields on a JSONL row cost twelve dispatches, three terminal rulings, ~1.5M subagent tokens, with the panel earning its cost in round one and the two post-fix cycles not.

That field run also named a failure the churn diagnosis in #122 does not cover. Its gap 3: both post-fix cycles found defects that were **real, probe-backed and correctly arbitrated**, with zero defects in the mechanism after the first fix batch — the questions were arbitrable and the answers right, and the *subject* had drifted from the change to the record of reviewing it. Its gap 5, routed here by the owner, is the missing terminus for exactly that.

**Width is deliberately untouched.** The owner ruled on 2026-08-23 that lane choice and panel width wait until he has experienced these changes across several issues.

## Decision

**The consequence field.** A finding names the concrete consequence of standing unfixed — the action a consumer would take wrongly, or the failure that would occur. Coverage-first is byte-unchanged and nothing true goes unfiled: the field is a required part of a finding, never a licence to withhold one. Its evidence is the best in the change: across this change's own review, all 63 raw findings carried one unprompted, no stage remarked on it as a cost, and it is what let a later stage sort the docket at all.

**Consequence shape, defined by where the consequence lands** — on the artifact a consumer will use, or on the record of having reviewed it — read from the site the finding cites rather than from what the finding is about, with a finding citing both kinds counted artifact-facing. Three consumers under an undefined earlier wording invented three different taxonomies and two stages of one review produced incompatible splits, so the definition is keyed to the cited site rather than to judgement.

**The report carries the split by consequence shape.** This is the instrument #122's failure mode 3 asks for and nothing could read: apparatus-facing versus product-facing, as a number, per pass.

**The post-fix look gets a bound and a second terminus.** It reads the fix diff, **whatever depends on it**, and each sustained high's territory, rather than the artifact over again — the middle element is the one a literal reading drops, and it carries a fix that moves a definition to every sentence turning on it. The next-pass ruling gains the **relevance terminus**: a pass continues only while the findings it expects are about the artifact, and a look returning only apparatus-facing material names that as the reason it stops. The count terminus is byte-unchanged; whichever fires first ends the cycle.

**Severity is named as three levels**, because the stages now key on the boundary.

## What was built, measured, and cut

The change as affirmed also carried a batching mechanism: findings sharing a consequence shape and a remedy shape classed at the merge, one defense price and one terminal ruling per class, a per-item exclusion protecting highs, mediums and behavioural consequences, and a severance duty pulling misfitting members back out. **It was built, reviewed, and removed before merge on the owner's decision.** The record of why is the point of this entry.

**It never fired.** Five stages tried to use it on real dockets — the parent-owned merge, the defense, the round-one judge, a post-fix prosecution cycle, and that cycle's terminal stage — and a cold consumer in a chartered experience session tried before any of them. **Every one formed zero classes.** Measured on the review's own 26 merged findings: classable 5, severed 4, largest surviving group 1, **rulings saved 0** — or **1** under a reading of the severance sentence the terminal stage rejected.

**The cause was structural, not drafting.** The exclusion held every artifact-facing finding; the severance duty's record limb reached everything else, because this repo's records all freeze by doctrine. The intersection of *classable* and *not severed* is empty for every docket this repo can produce — and what little survives is apparatus-facing material that the relevance terminus tells a review to stop working in anyway. Two mechanisms, each individually defensible, jointly with no domain.

**A repair was attempted and it did not hold.** A fix batch redrafted severance around a mispricing test; the cycle's terminal stage found that no fix had ordered it, that the redraft still read as independent disjuncts so the record limb fired unchanged, and that the check offered as verification could not discriminate — the spike's own lost pair sat in a single decision entry, so a record limb severs both regardless.

**What the owner decided.** Restore the affirmed per-item wording rather than amend an acceptance criterion he had settled personally, and **delete the machinery rather than ship it dormant**, since a mechanism that cannot fire still costs three stages a read-and-apply step and the corpus roughly half this change's prose. The measured gain from keeping it was between zero and one ruling in twenty-six.

**Consequences of the cut, stated:** [D-102]'s per-finding ruling unit is **not** superseded — the sentence is byte-identical to its pre-change form, and this entry supersedes nothing. The affirmed artifact's acceptance criteria 2, 3, 4, 5, 7 and 9 are withdrawn with the mechanism they describe; 1, 6, 8 and 10 stand. Governing-prose growth fell from +5,388 characters to **+2,730** (68,498 → 71,228), derived by `tools/figures.py` — `python tools/figures.py --base 3175369`, re-run against the tree this entry lands on, because the corpus the figure counts is the one the change writes into.

## What this does not settle, and what would reopen it

**Whether per-finding processing can be batched at all is open.** This change establishes that *this* design cannot, on this repo's dockets, and nothing more. A future attempt has a starting point rather than a blank page: the exclusion and the severance duty must be designed against each other from the first draft, and the acceptance criterion must measure rulings saved **net of severance**, or a structural zero reads as a pass.

**The reopen condition:** a docket on which a class of two or more forms and survives severance. None has been observed in five stages and one experience session.

**Two clauses came from the experience session rather than from the design**, and are recorded because a later session tightening them would otherwise remove a cold consumer's finding without knowing it was one: that a review must say out loud when a step produced nothing, and that the unit of ruling is not the unit of work. The first survives in the report's own reporting duty; the second went with the machinery it qualified.

**Net growth is argued, not hidden.** Roughly a third of the +2,730 is the review's own repairs — the panel's remedies were definitions the first draft left implicit, and closing them cost more words than the mechanisms did.

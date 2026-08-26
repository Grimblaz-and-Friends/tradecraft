# D-185: The report names who found each sustained high, so the width claim can retire by evidence from this repository's own record

**Status:** Accepted 2026-08-25 (PR #185)

## Context

`skills/adversarial-review/SKILL.md:23` sets the default panel at four seats and `:26` justifies it — *"a single pass kept 12% of the sustained yield, the best seat chosen with hindsight kept 46%, the fourth seat's marginal yield stayed real, and the fifth's went thin"* — entirely on the predecessor's six attributed rounds, [#1](https://github.com/Grimblaz-and-Friends/tradecraft/issues/1). That issue's own correction comment anticipated the obvious objection and answered it with a mechanism: *"tradecraft records the datum the predecessor lacked for 850 entries, so seats here retire by evidence"*, the datum being `found_by` on every ledger row, and *"Revisited by `found_by` evidence if the seat record ever contradicts it."*

**The mechanism was built and then lost.** `docs/ledger.jsonl` carries `found_by` on 834 of 869 rows, 96 of them high, and froze at the reset on 2026-08-19 [D-74]. `docs/reviews.jsonl` replaced it, and records per-seat *counts* rather than per-finding attribution. So the field designed to retire seats by evidence stopped being written at exactly the point the review pipeline started running daily.

**[#138](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138) deferred width to the owner's experience, and the owner lifted the deferral.** He set it on 2026-08-23 — *"Width is not to be revisited until he has experienced the emission-side changes across a few issues"* — and on 2026-08-25, asked whether the reviews since felt different, answered *"some has changed, but I'm not sure a lot has changed"* and directed the strand be picked up. The condition was not met on its own terms; he overrode it. Of the exploration's four directions, three were routed to heirs that have landed or are in flight; width went to no heir.

**Asked of the record, the claim answers only to within a bracket.** Archaeology over the 27 reviews in `docs/reviews.jsonl` booking at least one high recovered **92 distinct sustained highs** — as against the 145 seat *credits* the index books. Of those, 59 are round-one panel findings, and **36 of the 59 (61%) name no finder anywhere in the posted record**: not in the report, not in the terminal ruling, not in any comment. Of the 23 that do, 43% were sole-found by one seat and 57% co-found by two or more, and the best fixed two-seat policy retained 21 of 23 while a three-seat policy retained all 23. **The same fixed-policy computation over the ledger, which records one primary finder per finding and so cannot see a co-finder, puts that same pair — `claims-vs-evidence` with `cold-read`, the best fixed pair on both corpora — at 32 of 64.**

**Both ends of that bracket are biased toward their own conclusion** — the ledger by attributing to primaries alone, which makes width look necessary; the reports because a report is likelier to name finders when several seats concurred, which makes width look redundant. The 36 unattributed highs are what stands between them, and no further archaeology reaches them.

**Two cautions on any statistic drawn from the attributed 23, both found by this change's own review.** The set includes two **routine-lane** reviews — `pr-96` and `pr-99`, which `:22` fixes as one cold pass — where sole-finding was arithmetically forced because only one seat sat, so those rows carry no information about width. Excluding them leaves 21 panel highs whose sole-founders are `claims-vs-evidence` 6, `operational` 2, and every other seat **zero**. And the two estimators differ: the reports figures above are a **fixed** policy, while `:26`'s inherited curve and the per-round figures in the exploration record are **hindsight-best**, re-choosing the subset every round and upward-biased by construction.

**The datum is produced every review and thrown away.** `:64` obliges the merge to credit every finder, primary first, and the merged lists that were posted carry exactly that — [PR #119](https://github.com/Grimblaz-and-Friends/tradecraft/pull/119#issuecomment-5384244777) reads `Finders: cold-read-1 (primary), revision-diff-1, wiring-falsifier-2`, and [PR #97](https://github.com/Grimblaz-and-Friends/tradecraft/pull/97#issuecomment-5365206051) the same in a different format. Two of twenty-seven reviews published one; everywhere else it stayed a local file. This is the predecessor's failure reproduced, and #1 names it in as many words: *"the seat question was never answerable there because per-pass attribution was mostly never recorded."*

**Re-run recipe.** The ledger figures — 64 highs, the retention values, `wiring-falsifier`'s panel count — all require the grouping filter, without which none of them reproduces:

```bash
python -c "import json,collections; rows=[json.loads(l) for l in open('docs/ledger.jsonl',encoding='utf-8') if l.strip()]; rec=[r for r in rows if r['found_by']!='unrecorded']; print(len(rows), len(rec), sum(1 for r in rec if r['severity']=='high'))"
```

→ `869 834 96`. Then: group rows whose `found_by` is one of the five seat keys by `source`, keep sources with **at least three distinct seats** (19 rounds, 539 findings, 64 highs), and compute retention over rows with `severity == "high"`, holding the subset fixed across rounds. The report-side figures are recovered by reading, for each `docs/reviews.jsonl` row booking a high, its `report` URL and that PR's terminal-ruling comment, enumerating distinct sustained highs and taking each one's finders where stated; the enumeration is in [the exploration record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138#issuecomment-5415518688).

## Decision

**`:82`'s report-contents list gains one clause: each sustained high's finders** — every credited seat as the merge records them, primary first and a merge-added co-finder labeled as its own; or the stage or seat that originated it where no merge carried it; and where a merge carried it with no finder list to copy, that fact.

**Every credited seat, not the primary alone**, because primary-only attribution is precisely what makes the ledger's half of the bracket unusable: it cannot distinguish a high one seat found from a high all five found, and those two facts argue opposite conclusions about width.

**Primary first, and a merge-added co-finder labeled as the merge's own** — both attributes `:64` already makes the merge write, so copying them costs nothing. Without the primary tag the new corpus cannot be recomputed under the estimator the ledger corpus uses, and the two could not be set against each other; without the label, a co-finder the merge inferred publishes as seat evidence and inflates the co-finding rate in the exact direction the reports corpus is already biased. The clause cannot deliver what it was bought for without either.

**The stage or seat that originated it where no merge carried it.** 33 of the 92 highs recovered came from the post-fix look or the defense, and a routine-lane review has no real merge at all; an uncarried seat entry is ruled on by `:70` and the merge holds nothing for it, the gap `:66` found a carve-out necessary for. Keeping the field total rather than panel-only matters because a share computed over panel highs alone would silently misstate what a narrower panel forgoes.

**Where a merge carried it with no finder list to copy, the report says so.** Without it the rule produces the same silence it exists to close. It is also the instrument for acceptance criterion 3 — a review that has to write it has shown the obligation is misplaced, and belongs at the merge rather than at the report — which is why it is keyed to *a merge that carried the finding*: a finding no merge ever saw must not fire that signal.

**Sustained highs only.** The record runs zero to thirteen high credits per review, five reviews booking none, against roughly forty findings. Every width claim in the cell turns on highs; the ~88% of the corpus below high is the class #138 measured as instrument-intrinsic, and #143's whole design is to keep new obligations off the emission side. The scope is a floor on cost, not a claim that lows carry nothing.

**In the report, not in `docs/reviews.jsonl`.** Index rows freeze on landing, and a wrong permanent schema is the expensive mistake — the ground on which [PR #167 priced out its own index limb](https://github.com/Grimblaz-and-Friends/tradecraft/pull/167#issuecomment-5406492812) (*"`docs/reviews.jsonl`'s schema plus its guard, and rows freeze — a wrong shape is permanent"*). That limb was the session-note column and not this one, so only the ground transfers; no finders column has ever been priced. Prose is where a first attempt at a shape belongs.

**`:86` gains one sentence naming what the existing `high` column counts.** Not a schema change and not a new field — the column exists and its convention was never stated, so the two landed readings disagree: `pr-119` credits its single high to the primary seat alone while `pr-167` books 11 credits against its own notes' 6 distinct highs. The clause above supplies a warrant for the all-finders reading, and the change's own experience session recorded a cold consumer following it into the row and producing a column summing to three for one distinct high. Stating that the column carries credits and never distinct highs makes the ~7 rows already written under the other reading legible rather than repairable; they freeze wrong either way.

**No guard.** A report is a GitHub comment. `tools/lint.py` does validate the row's `report` URL, so a handle exists in principle, but a guard reaching it needs network and a token in CI and would red a frozen row it cannot repair — so the platform rung is priced out here rather than unavailable, and skill prose is the cheapest rung that remains.

**Width is not decided.** The trigger is on [#138](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138), which stays open as its vehicle: after six reviews have published finder data — roughly fifteen to twenty newly attributed highs — a session recomputes and brings the owner an argued call. The trigger lives on the issue rather than in the cell because a rule obliging a return visit would be governing prose bought for a one-time recomputation, and because #173 settled that a session owes no return visit by default. `:26` carries a `[D-185]` marker so the session that would otherwise re-derive width from the predecessor's figures finds the contest and the vehicle at the line it is reading.

## Rejected

**Deciding width now, on the attributed highs.** The direction the sample points is that the fourth and fifth seats bought nothing on the reports corpus, where three seats reach 100%. **On the ledger under the same fixed estimator they buy 21 of 64**, so "bought nothing" holds on one corpus and not the other. Lane-corrected, the two candidate pairs **tie at 19 of 21** — `operational` with `claims-vs-evidence`, and `cold-read` with `claims-vs-evidence` — so the attributed evidence does not separate them at all. That is the honest state, and it is not a basis for cutting a default. Six reviews of clean data costs a week and removes the objection.

**#138's Direction-1 pair as written** — *"one that executes, one that checks claims against sources."* It measures **19 of 23** on the reports and **29 of 64** on the ledger, against the best fixed pair's 21 of 23 and 32 of 64 — a margin the ledger carries alone, since the reports gap is the two routine-lane rows and lane-corrected the pairs tie. But the proposal names two **lenses**, not a vantage, and `:30` distinguishes them: either lens could be dispatched cold, so an objection resting on the pair dropping the `cold-read` *vantage* does not reach what was actually proposed. On the lane-corrected set the sole-founding seats are `claims-vs-evidence` and `operational` — which **is** Direction 1's pair — while `cold-read` sole-founds none. Recorded here because the proposal is on a live issue and a later session would otherwise adopt or reject it on figures that do not survive checking.

**Amending `:64`.** The merge rule already requires crediting every finder, and the two published exemplars show it obeyed; this review's own merge carried finders primary-first for all four of its highs. The failure is at publication. A rate trigger was considered instead and rejected as governing prose bought for a one-time job [D-173].

**Extending the obligation to dismissed highs.** It would roughly double the obligation and land the cost on emission to recover a noise signal the per-seat `raw`/`merged`/`sustained` columns already carry in aggregate. This price-out holds in every future change.

**Extending it to mediums and lows.** Same emission-side pressure; highs are what the claim under test turns on.

**Buying the measurement with a fresh five-seat run** against an already-reviewed revision. It closes the bracket on one artifact for roughly one panel's cost, where the record closes it on every future review for the price of a clause.

## What this does not close

**The bracket, until the record has run.** Nothing here recovers the 36 unattributed highs; they are lost.

**The two corpora disagree about `wiring-falsifier`.** It sole-found none of the attributed highs, and in the 19-round panel population is credited 11 panel highs at **13% density, third** behind `revision-diff` and `claims-vs-evidence`; over the whole ledger it is 15 highs at 16%, second. Those are two populations and the disagreement is genuine — it is what six reviews of clean data answers, and only if the reports carry the primary tag the clause now requires.

**Whether the escape branch will fire more often than it should.** Five of the six most recent panel rows could not produce a per-seat split at all — two of them attributing that to the merge. That is a real signal that merges are getting looser, and if the branch fires every time, criteria 1 and 2 go unmet and the six-review trigger never becomes due. It is the first thing the six reports measure. `pr-166` is the counter-case and the reason this is a watch rather than a defect: the same note that reports no per-seat split still names its high's finder.

**Whether the shape belongs in the index eventually.** Left open deliberately; the report is the trial.

**Which stage's severity reading "sustained high" keys on**, where the defense moves severity and the terminal stage settles it. Routed to [#180](https://github.com/Grimblaz-and-Friends/tradecraft/issues/180), which already owns the neighbouring convention gap.

**Seat attribution inside a multi-seat post-fix look**, which the stage limb records at stage granularity. Prospective — every landed row books post-fix under a single stage key — and routed to #138, where the recomputing session needs the warning.

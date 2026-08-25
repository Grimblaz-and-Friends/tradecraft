# D-185: The report names who found each sustained high, so the width claim can retire by evidence from this repository's own record

**Status:** Accepted 2026-08-25 (PR #185)

## Context

`skills/adversarial-review/SKILL.md:23` sets the default panel at four seats and `:26` justifies it — *"a single pass kept 12% of the sustained yield, the best seat chosen with hindsight kept 46%, the fourth seat's marginal yield stayed real, and the fifth's went thin"* — entirely on the predecessor's six attributed rounds, [#1](https://github.com/Grimblaz-and-Friends/tradecraft/issues/1). That issue's own correction comment anticipated the obvious objection and answered it with a mechanism: *"tradecraft records the datum the predecessor lacked for 850 entries, so seats here retire by evidence"*, the datum being `found_by` on every ledger row, and *"Revisited by `found_by` evidence if the seat record ever contradicts it."*

**The mechanism was built and then lost.** `docs/ledger.jsonl` carries `found_by` on 834 of 869 rows, 96 of them high, and froze at the reset on 2026-08-19 [D-74]. `docs/reviews.jsonl` replaced it, and records per-seat *counts* rather than per-finding attribution. So the field designed to retire seats by evidence stopped being written at exactly the point the review pipeline started running daily.

**[#138](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138) deferred width to the owner's experience, and the deferral came due.** Of the exploration's four directions, three were routed to heirs that have landed or are in flight; width went to no heir, and a board search on `width`, `panel`, `lane`, `seats` and `staffing` returns no issue that owns it.

**Asked of the record, the claim answers only to within a bracket.** Archaeology over the 27 reviews in `docs/reviews.jsonl` booking at least one high recovered **92 distinct sustained highs** — as against the 145 seat *credits* the index books, a distinction #138's synthesis had already flagged. Of those, 59 are round-one panel findings, and **36 of the 59 (61%) name no finder anywhere in the posted record**: not in the report, not in the terminal ruling, not in any comment. Of the 23 that do, 43% were sole-found by one seat and 57% co-found by two or more, and a fixed two-seat policy would have retained 21 of 23 while a three-seat policy retained all 23. The same computation over the ledger, which records one primary finder per finding and so cannot see a co-finder, puts the same two-seat pair at 40 of 64.

**Both ends of that bracket are biased toward their own conclusion** — the ledger by attributing to primaries alone, which makes width look necessary; the reports because a report is likelier to name finders when several seats concurred, which makes width look redundant. The 36 unattributed highs are what stands between them, and no further archaeology reaches them.

**The datum is produced every review and thrown away.** `:64` obliges the merge to credit every finder, primary first, and the merged lists that were posted carry exactly that — [PR #119](https://github.com/Grimblaz-and-Friends/tradecraft/pull/119#issuecomment-5384244777) reads `Finders: cold-read-1 (primary), revision-diff-1, wiring-falsifier-2`, and [PR #97](https://github.com/Grimblaz-and-Friends/tradecraft/pull/97#issuecomment-5365206051) the same. Two of twenty-seven reviews published one; everywhere else it stayed a local file. This is the predecessor's failure reproduced, and #1 names it in as many words: *"the seat question was never answerable there because per-pass attribution was mostly never recorded."*

Re-run recipe for every figure above:

```bash
python -c "import json,collections; rows=[json.loads(l) for l in open('docs/ledger.jsonl',encoding='utf-8') if l.strip()]; rec=[r for r in rows if r['found_by']!='unrecorded']; print(len(rows), len(rec), sum(1 for r in rec if r['severity']=='high'))"
```

The report-side figures are recovered by reading, for each `docs/reviews.jsonl` row booking a high, its `report` URL and that PR's terminal-ruling comment, enumerating distinct sustained highs and taking each one's finders where stated. The enumeration is in [the exploration record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138#issuecomment-5415518688).

## Decision

**`:82`'s report-contents list gains one clause: each sustained high's finders** — every credited seat rather than the primary alone, or the stage that originated it outside the panel, and where the merge recorded none, that it recorded none.

**Every credited seat, not the primary alone**, because primary-only attribution is precisely what makes the ledger's half of the bracket unusable: it cannot distinguish a high one seat found from a high all five found, and those two facts argue opposite conclusions about width.

**The stage, where the finding originated outside the panel.** 33 of the 92 highs recovered came from the post-fix look or the defense rather than from a seat. Those were recoverable from id prefixes with no ambiguity, so the clause costs nothing there and keeps the field total rather than panel-only — a share computed over panel highs alone would silently misstate what a narrower panel forgoes.

**Where the merge recorded none, the report says so.** Without it the rule produces the same silence it exists to close: a reader cannot tell an unattributed finding from a report that skipped the obligation. It is also the instrument for acceptance criterion 3 — a review that has to write it has shown the obligation is misplaced, and belongs at the merge rather than at the report.

**Sustained highs only.** Two to six per review against roughly forty findings. Every width claim in the cell turns on highs; the ~95% of the corpus below high is the class #138 measured as instrument-intrinsic, and #143's whole design is to keep new obligations off the emission side. The scope is a floor on cost, not a claim that lows carry nothing.

**In the report, not in `docs/reviews.jsonl`.** Index rows freeze on landing, and a wrong permanent schema is the expensive mistake — the ground on which [PR #167 priced out this exact index limb](https://github.com/Grimblaz-and-Friends/tradecraft/pull/167#issuecomment-5406492812) (*"`docs/reviews.jsonl`'s schema plus its guard, and rows freeze, so a wrong shape is permanent"*). Prose is where a first attempt at a shape belongs, and if the shape proves out, the index is a later change with a real exemplar behind it rather than a guess.

**No guard.** A report is a GitHub comment; no lint reaches it. The admission order's platform rung is genuinely unavailable here rather than merely unexamined, and skill prose is the cheapest rung remaining.

**Width is not decided.** The trigger is on [#138](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138), which stays open as its vehicle: after six reviews have published finder data — roughly fifteen to twenty newly attributed highs — a session recomputes and brings the owner an argued call. The trigger lives on the issue rather than in the cell because a rule obliging a return visit would be governing prose bought for a one-time recomputation, and because #173 settled that a session owes no return visit by default.

## Rejected

**Deciding width now, on the 23 attributed highs.** The direction the sample points is clear — the fourth and fifth seats bought nothing on either corpus, and the two seats carrying highs are `claims-vs-evidence` (sole-found 6 of 23) and `cold-read` (sole 2), not the executing pair #138's own Direction 1 proposed. But n=23 with a known bias toward exactly that conclusion is not a basis for cutting a default, and the owner deferred width once already on the ground that the evidence was thin. Six reviews of clean data costs a week and removes the objection.

**#138's Direction-1 pair as written** — *"one that executes, one that checks claims against sources."* It measures 21 of 23 on the reports and 40 of 64 on the ledger, and both highs it misses on the attributed set ([PR #96](https://github.com/Grimblaz-and-Friends/tradecraft/pull/96)'s C1, [PR #99](https://github.com/Grimblaz-and-Friends/tradecraft/pull/99)'s COLD-1) were sole-found by `cold-read`, the seat it drops. The executing seat it keeps, `operational`, files the most findings of any seat in the ledger (174) at the lowest high density (6%). Recorded here because the proposal is on a live issue and a later session would otherwise adopt it as the exploration's conclusion.

**Amending `:64`.** The merge rule already requires crediting every finder and the two published exemplars show it being obeyed. Nothing there is broken; the failure is entirely at publication.

**Extending the obligation to mediums and lows.** It would triple the data and land the cost on emission, which is the pressure #143 exists to relieve. Highs are what the claim under test turns on.

**Buying the measurement with a fresh five-seat run** against an already-reviewed revision, recording attribution properly. It closes the bracket on one artifact for roughly one panel's cost, where the record closes it on every future review for the price of a clause.

## What this does not close

**The bracket, until the record has run.** Nothing here recovers the 36 unattributed highs; they are lost.

**The two corpora disagree about `wiring-falsifier`**, which sole-found zero of the 23 attributed highs but is credited 11 panel highs and the second-highest high density (16%) in the ledger. That is a genuine conflict between a primary-only record and a co-finder-aware one, and it is exactly the question six reviews of clean data answers.

**Whether the shape belongs in the index eventually.** Left open deliberately; the report is the trial.

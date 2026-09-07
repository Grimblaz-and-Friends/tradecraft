# D-453: The merge names the enumerator of the uncarried class

**Status:** Accepted 2026-09-07 (PR #453)

## Context

[D-102](D-102-2026-08-21-merged-list-is-an-index.md) put the uncarried class on the terminal stage's docket **by rule** — *anything in a seat's report that no merged finding carries: a remedy, a dissent, an examination that declined to file* — and attached a ruling obligation to it. It then deferred the one thing that makes the class producible, and wrote its own reopen condition:

> **No stage is named as the enumerator** of the uncarried class. Priced out: the enumeration makes the class determinate, and a stage receiving a short list can now check it against the reports, which is what this review's terminal stage did (55 declined bullets against 8 docketed). **Reopen on:** a terminal stage ruling on a merge-supplied docket list without checking it against the reports.

**The premise it was priced on was that the terminal stage would check.** Eight rows of `docs/reviews.jsonl` bear on that. Read them with `python -c "import json;[print(json.loads(l)['artifact'],json.loads(l).get('notes','')) for l in open('docs/reviews.jsonl',encoding='utf-8') if l.strip()]"` at the commit that lands this entry, and match on `pr-270`, `pr-322`, `pr-371`, `pr-388`, `pr-410`, `pr-414`, `pr-431` and the row whose artifact names PR #429. They are not eight firings, and the split is what decides the remedy:

- **Two are clean firings of the condition** — a merge failing to account, with the reports in hand. `pr-410`: *"cold-read's F6 was neither carried nor listed uncarried, so it took no ruling."* `pr-414`: *"the second consecutive instance of it… fixed by the builder afterwards rather than declined, no stage remaining that could rule a decline."*
- **Four are firings whose cause lies upstream** — the seat reports never reached the stage that was supposed to check. `pr-371`, `pr-431`, the PR #429 row, and `pr-322` (*"its completeness on uncarried seat entries is unverifiable"*).
- **One is both at once, and it is the sharpest row on the record.** `pr-388`: *"the merge did not carry the seat reports whole, and it cost revision-diff's F2, which reached no stage and is recorded by the session that lost it."*
- **One is the premise working.** `pr-270` — the merge's account was false and the terminal stage's own sweep caught it. Once, and required by nothing.

**So the upstream class is the larger one**, five rows against three, and that is why this change closes the clean firings and leaves the rest to the dispatch contract, which already requires every predecessor stage's output whole. **This entry's drafting understated that corpus twice** — at five rows, and then, after a cold seat found a sixth, still at five. The panel found the remaining three. The figure is stated here as a match list rather than a count for that reason.

**The asymmetry is what decides where the catch goes.** `arbitration.md` rules that a **drop**, a **record** and a lens retirement are ruled by a stage that is not the session that built the change. A drop discovered after the terminal ruling therefore reaches a builder whose remaining moves are to fix, to put the matter to such a stage, or to file — and the one thing it may not do is decline. `pr-414` records that playing out.

**Counter-evidence, weighed and not decisive.** The four most recent rows in that file each state a nothing-uncarried figure, one of them checked at three stages independently, so sessions were already doing this unprompted — an argument that the words buy nothing. It is stronger than the drafting first allowed: for the class this change addresses, the last failure is `pr-414`, and eight later rows carry no instance of it. What holds the change up is not recency but that the behaviour is a habit no rule required, and that when it lapsed the loss was silent.

## Decision

**One clause, in the merge paragraph of `skills/adversarial-review/references/arbitration.md`, and no new stage or dispatch.** Before it dispatches the defense, the merge accounts for everything in a seat's report that no merged finding carries — the class the docket takes, so a finding and equally a remedy, a dissent, an examination that declined to file — naming each as an uncarried seat entry. The account is read off the seat's report itself, never off a total the seat states about itself; like entries are named as one block taking one ruling; and a qualification inside a carried finding travels with it.

**Placement is inherited from D-102, not re-argued.** The merger reads the merge paragraph, and that is where its obligation is.

**The class takes the docket sentence's own words, and the docket sentence gained the one item it was missing.** The first draft scoped the merge's account to a seat's *findings*, narrower than the class the docket consumes; a cold seat caught it before implementation. The review then found the mirror image — the docket's own gloss enumerated a remedy, a dissent and a declined examination but not **a finding**, which is the item actually lost on `pr-410` and `pr-414` — so that gloss now names it.

**The account is read off the report and never off the seat's own total**, because a seat's self-report has been wrong in the direction that hides a finding. [PR #414's final report](https://github.com/Grimblaz-and-Friends/tradecraft/pull/414#issuecomment-5554614857) records the instance in full: *"`operational` reported its raw count as 11 and filed twelve numbered findings; the merge carried all twelve, and the discrepancy is its own count rather than a lost finding."* **Nothing was lost that time** — the rule exists because the discrepancy is what a later stage would otherwise have to notice for itself, not because that instance cost a finding.

**The aggregation rule came from the first review run under the clause and is the least obvious part of this change.** *Naming each* over an unbounded class is indeterminate: D-102 measures the population at 55 declined bullets against 8 docketed, and this change's own review produced an eight-entry account whose blocks atomise to roughly thirty-eight, so the ruling count `arbitration.md` obliges could not be known. A block takes one ruling. The same review showed three qualifications of one shape treated three ways by one merge, which is why a qualification now travels with the finding that carries it.

**Neither the clause nor anything else here obliges a seat.** D-102 priced a seat-side production obligation as the most expensive recurring remedy on its docket. `dispatch.md`, `roster.md` and `the-record.md` are untouched by the diff. **That is true of the diff and not of the meaning**: the read-off-the-report rule reaches `the-record.md`'s *"The raw count is the seat's own to report"* without editing it, since a merge that enumerates independently will hold a truer count than the seat stated and nothing says which figure enters the report's column. That is recorded rather than fixed.

**The shipped class is wider than the sentence the owner approved, and that was a session call.** The affirmed restatement read *"every reviewer's finding"*; the clause covers a remedy, a dissent and a declined examination too. The widening came from a cold seat's adverse verdict, not from the owner, and is reported here because an account drawn over a narrower class than the docket it feeds is the same defect one step earlier. The settled artifact on the issue states the wider class in its own purpose, so it is on the record they hold.

**The cost, and how to check it.** Run `git diff ccacec2e9ed783c7f4584b6793b4e44bb5c2c351 <the commit that lands this entry> -- skills/adversarial-review/references/arbitration.md`. The base is pinned because a moving ref cannot be re-derived: an earlier draft of this entry named bare `main`, which was eight commits stale in the tree it was written in and would return an empty diff once this change merged. No offset is claimed; two false trailing clauses were deleted from the same paragraph, and that is netted into the figure the command returns rather than claimed separately.

## The second clause, and why it is not here

**The change was built with two clauses and ships with one.** The second put the check on the terminal stage: *that limb this stage checks against the seat reports rather than taking the merge's account of it*. The owner chose that two-stage shape from four argued options — a merge-only clause, a terminal-stage-only clause, both, and a mechanism over structured seat output — and the recommendation carried its own strongest counter-argument, that four consecutive reviews had already done this unprompted. **Where that counter-argument was put is this pull request's review, not the affirmation record**, which states only that a counter-case was carried.

**Acceptance criterion 3 named a cold-seat A/B as the check on that clause and said in terms that it fails if both arms re-derive.** The review's terminal stage sustained at high that the check had not run, and ordered it. It ran, and it fell: [the spike report](https://github.com/Grimblaz-and-Friends/tradecraft/issues/421#issuecomment-5565389899) records two arms differing in exactly that clause, a planted control cited in both, and **both arms re-deriving the account and catching the same two omissions**. The arm without the clause reached it from four sentences already in the file — *defer to no party*, *the merged list indexes the seat reports*, *the account is read off the seat's report itself*, and the docket sentence's own second limb — reasoning that the merge's account is a party's claim and so must be tested. **The arms separated on which sentence a stage cites, not on what it does.**

**The owner amended the affirmed brief on 2026-09-07 and ruled the clause deleted**, the brief having settled that the job was carried by two stages. The bound on what the spike licenses is in its report: it measured a stopped plan rather than conduct under load, and the false account it planted was arithmetically self-refuting, which is the easy case.

## Rejected

- **A merge-only clause was not rejected — it is what shipped**, by the route above rather than by first choice.
- **A terminal-stage-only clause.** It lands after the defense, so a recovered entry reaches the terminal stage with no verdict and no price, and it depends on the reports arriving whole — the thing that failed in five of the eight rows.
- **A mechanism.** Nothing produces machine-readable seat output, and the reliable input a guard would need is the seat-side obligation priced out above. D-102 separately rejected a mechanism here on the ground that no script can tell a faithful reduction from a lossy one — an argument that covers fidelity better than completeness, and which this change does not re-litigate.
- **A field in the final report stating that the check ran.** The account is content of the merged list, and a check that finds something produces a ruling the report already carries.

## Deferred, with the evidence that would reopen them

- **The upstream class is unaddressed here and is the larger one.** Five of the eight rows are a stage starved of the seat reports, which `dispatch.md` already forbids — so the gap is compliance rather than text. **Reopen on:** a further review whose terminal stage cannot enumerate the uncarried class because the reports did not reach it.
- **D-102's third deferral has moved and this change is why.** That entry priced out giving an uncarried entry a verdict and a price on the class being sparse; the clause now produces it by rule, and this change's own review ran clause (b) over eight such entries with no defense verdict and no price to read. **Reopen on:** a terminal stage that dismisses an uncarried docket entry for want of a price.
- **`the-record.md`'s per-seat `raw` column has no rule for the disagreement this clause creates.** Recorded rather than fixed: the remedy lands in a second shipped file the affirmed boundary did not reach.
- **Criterion 4's falsifier names `dispatch.md` and `roster.md` but not `the-record.md`**, and its first limb reads *the changed file*, singular — so a seat obligation sited in `the-record.md` would pass a criterion written to forbid it. **Reopen on:** a seat-output obligation landing there under a change claiming this criterion.
- **The re-authoring class stays open as [#120](https://github.com/Grimblaz-and-Friends/tradecraft/issues/120)** and is deliberately not tied to this cause: naming an enumerator would have prevented none of its three instances.

## Convergence, and what use and prosecution changed

**Two cold-seat rounds, one adverse.** Round 1 returned `would not` on clause 1's scope and on criterion 3's non-discrimination; round 2 returned `would`.

**The experience session changed the shipped text.** A cold consumer ran the merge stage of a five-seat review under the change, produced the account and the reconciliation correctly, and caught a seat that stated seven findings while filing eight — naming the read-off-the-report clause as what corrected its own first reading. But it read the merge clause three times, first taking *wider than that seat's findings* to mean the duplicates the merge had absorbed, and resolved it only from the docket paragraph three paragraphs below. A cold seat had predicted that and declined to fail the artifact on it; use settled it, and the clause now carries the class inline.

**The review then found more in this entry than in the clause**, which is the honest summary of it: a false superlative, a corpus understated twice, a citation truncated at a semicolon so that its source read as saying the opposite of what it was cited for, and a growth command against a moving ref. All are repaired above. The one shipped-prose defect the panel found that use had not — that the class was unbounded and the ruling count therefore indeterminate — is the aggregation rule.

**Findings this change's cause already had on the record.** `docs/recorded-findings.jsonl` row 148 is the held entry for exactly this defect — *"a seat finding carried in neither the merged list nor the uncarried list"*, promotion *"a second merge drops a seat finding"* — and its condition had fired twice before this change was picked up. Neither the pre-implementation artifact nor this entry's drafting read that record at all, which the review sustained; the entry cites it now, and D-453 is its disposition.

## Evidence

[#421](https://github.com/Grimblaz-and-Friends/tradecraft/issues/421) with its affirmed brief, affirmation record, [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/421#issuecomment-5564844813) and [spike report](https://github.com/Grimblaz-and-Friends/tradecraft/issues/421#issuecomment-5565389899); D-102's *Deferred* section, whose fifth item this entry resolves and whose second and third it moves; `docs/recorded-findings.jsonl` row 148; and the eight `docs/reviews.jsonl` rows named in Context.

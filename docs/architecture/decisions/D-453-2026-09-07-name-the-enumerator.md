# D-453: The merge produces the uncarried enumeration and the terminal stage checks it

**Status:** Accepted 2026-09-07 (PR #453)

## Context

[D-102](D-102-2026-08-21-merged-list-is-an-index.md) put the uncarried class on the terminal stage's docket **by rule** — *anything in a seat's report that no merged finding carries: a remedy, a dissent, an examination that declined to file* — and attached a ruling obligation to it. It then deferred the one thing that makes the class producible, and wrote its own reopen condition:

> **No stage is named as the enumerator** of the uncarried class. Priced out: the enumeration makes the class determinate, and a stage receiving a short list can now check it against the reports, which is what this review's terminal stage did (55 declined bullets against 8 docketed). **Reopen on:** a terminal stage ruling on a merge-supplied docket list without checking it against the reports.

**The premise it was priced on was that the terminal stage would check.** Five rows in `docs/reviews.jsonl` bear on that, and they are not five firings — read them with `python -c "import json;[print(json.loads(l)['artifact'],json.loads(l).get('notes','')) for l in open('docs/reviews.jsonl',encoding='utf-8') if l.strip()]"` at this entry's commit:

- **`pr-410` and `pr-414` are clean firings.** In each, a `cold-read` finding was neither carried into the merged list nor listed among the uncarried entries, so it took no ruling from any stage. `pr-414`'s row records the consequence exactly: *"fixed by the builder afterwards rather than declined, no stage remaining that could rule a decline."*
- **`pr-371` and the PR #429 row are firings whose cause lies upstream.** In both the reports never reached the judge, so the docket's uncarried limb went undischarged — a dispatch-contract breach rather than a stage declining to check. **This is the larger of the two classes**, and it is why clause 2 below closes the clean firings and depends on the dispatch contract for the rest.
- **`pr-270` is the premise working.** The merge's account was false and the terminal stage's own sweep caught it — once, and required by nothing.

**The asymmetry is what decides where the catch goes.** This file already rules that a **drop**, a **record** and a lens retirement are ruled by a stage that is not the session that built the change. So a drop discovered after the terminal ruling has exactly one disposition left — the fix — which is the one the builder may not decline. Every stage later than the merge is a worse place to catch it.

**Counter-evidence, weighed and not decisive.** The four most recent rows in that file each state a nothing-uncarried figure, one of them checked at three stages independently. Sessions were already doing this unprompted, which is an argument that the words buy nothing. It does not carry: the two rows immediately preceding those four are the two that record the departure, so the behaviour is real and not stable.

## Decision

**Two clauses in `skills/adversarial-review/references/arbitration.md`, no new stage and no new dispatch.** At the merge paragraph: before it dispatches the defense, the merge accounts for everything in a seat's report that no merged finding carries — the class the docket takes, so a finding and equally a remedy, a dissent, an examination that declined to file — naming each as an uncarried entry; and the account is read off the seat's report itself, never off a total the seat states about itself. At the docket paragraph: the terminal stage checks that second limb against the seat reports rather than taking the merge's account of it.

**Placement is inherited from D-102, not re-argued.** A session dispatching one stage does not read the paragraph governing another; the merger reads the merge paragraph and the session serving the terminal stage reads the docket sentence.

**The two clauses take the docket sentence's vocabulary and not a second one.** The first draft scoped the merge's account to a seat's *findings*, which is narrower than the class the docket consumes — a remedy, a dissent and a declined examination are none of them findings. An account drawn over a narrower class than the docket it feeds is the same defect one step earlier, and a cold seat caught it before implementation.

**The account is read off the report and never off the seat's own total**, because a seat's self-report has been wrong in the direction that hides a finding: [PR #414's final report](https://github.com/Grimblaz-and-Friends/tradecraft/pull/414#issuecomment-5554614857) records that *"`operational` reported its raw count as 11 and filed twelve numbered findings."*

**Neither clause obliges anything of a seat.** D-102 priced a seat-side production obligation as the most expensive recurring remedy on its docket, and nothing here reaches `dispatch.md`, `roster.md` or `the-record.md`.

**The owner chose this shape from four argued options** — a merge-only clause, a terminal-stage-only clause, both, and a mechanism over structured seat output — on [#421](https://github.com/Grimblaz-and-Friends/tradecraft/issues/421), recorded with the [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/421#issuecomment-5564715337) and its [affirmation record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/421#issuecomment-5564717021). The recommendation carried the strongest case against itself — that four consecutive reviews had already done this unprompted — and it was picked anyway.

**Net growth on a shipped governing file is the cost, and it is argued rather than offset.** No offset was found and none is claimed; the growth is derived from this PR's own diff (`git diff main -- skills/adversarial-review/references/arbitration.md`) rather than stated here, because a figure in a frozen entry cannot be re-derived after the branch moves.

## Rejected

- **A merge-only clause.** It leaves the interested party — in this repository's single-session lanes, the change's own author — certifying its own completeness, which is the exact authority D-102 took away from the merge.
- **A terminal-stage-only clause**, which is D-102's assumption made explicit. It lands after the defense, so a recovered entry reaches the terminal stage with no verdict and no price, and it depends on the reports arriving whole — the thing that failed in two of the five rows above.
- **A mechanism.** Nothing produces machine-readable seat output, and the reliable input a guard would need is exactly the seat-side obligation priced out above. D-102 separately rejected a mechanism here on the ground that no script can tell a faithful reduction from a lossy one — an argument that covers fidelity better than completeness, and which this change does not need to re-litigate because the owner ruled the prose route.
- **A field in the final report stating that the check ran.** The merge's account is already content of the merged list, and a check that finds something produces a ruling the report already carries. The field would grow a governing surface to record a silence.

## Deferred, with the evidence that would reopen them

- **Clause 2 may be redundant.** The unchanged docket sentence already obliges one ruling per uncarried seat entry, and D-102 records a terminal stage deriving the set unprompted — so a stage may re-derive with clause 2 absent. The artifact's acceptance criterion 3 is written to fail on exactly that finding. **Reopen on:** a cold-seat A/B whose arms differ in exactly clause 2 and in which both arms re-derive; the remedy is then to delete clause 2 and keep the merge clause alone.
- **The upstream class is unaddressed here and is the larger one.** Clause 2 obliges a check that a stage starved of the seat reports cannot perform, and two of the five rows are that starvation. `dispatch.md` already requires every predecessor stage's output whole, so the gap is compliance rather than text. **Reopen on:** a further review whose terminal stage cannot perform the clause-2 check because the reports did not reach it.
- **Criterion 4's falsifier names `dispatch.md` and `roster.md` but not `the-record.md`**, which `dispatch.md` designates as the home of what every recipient's output must carry — so a seat obligation written there would be the one place the named list misses. A round-2 cold seat raised it and declined to fail the artifact on it, the criterion's first limb still reaching it. **Reopen on:** a seat-output obligation landing in `the-record.md` under a change claiming this criterion.
- **The next hop — whether every ruling the terminal stage makes reaches the report — is out by the affirmed brief**, nothing on the record having shown it fail. **Reopen on:** a report found to omit a ruling the terminal stage made.
- **The re-authoring class stays open as [#120](https://github.com/Grimblaz-and-Friends/tradecraft/issues/120)**, and is deliberately not tied to this cause: naming an enumerator would have prevented none of its three instances.

## Convergence and the cold seat

**Two rounds, one adverse.** Round 1 returned `would not` on two points, both repaired: clause 1's scope, above; and acceptance criterion 3, which specified a single post-change run and so did not discriminate — the unchanged docket sentence already obliging the ruling meant a no-op implementation would have passed it. Round 2 returned `would`.

**Two claims the drafting asserted falsely, recorded because the artifact is settled and the retraction belongs somewhere.** The draft said D-102's reopen condition had *"fired four times"* — wrong on the condition's own words, `pr-270`'s terminal stage having checked; and wrong in count, round 2 finding a fifth bearing row, `pr-371`, that the drafting's own scan had missed. The draft also said the brief settled the no-mechanism scope; the brief names no mechanism either way, and the owner's pick among four options is what rules it out.

**The experience session changed the shipped text.** A cold consumer ran the merge stage of a five-seat review under this change and produced the account, the four uncarried entries and the reconciliation correctly — and caught a seat that stated seven findings while filing eight, naming the read-off-the-report clause as the rule that corrected its own first reading. But it read the merge clause three times, first taking *wider than that seat's findings* to mean the duplicates the merge had absorbed, and resolved it only from the docket paragraph two below, which spells the class out. The round-2 cold seat had predicted exactly this and declined to fail the artifact on it; use settled it, and a session note outranks panel hypothesis on behaviour. **The merge clause now carries the class inline** — a finding and equally a remedy, a dissent, an examination that declined to file — while keeping the tie to the docket so an editor can see the two are one class. Seven words, against a criterion the text was otherwise failing in use.

## Evidence

[#421](https://github.com/Grimblaz-and-Friends/tradecraft/issues/421) with its affirmed brief, affirmation record and [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/421#issuecomment-5564844813); D-102's *Deferred* section, whose fifth item this entry resolves; and the `pr-270`, `pr-371`, `pr-410`, `pr-414` and PR #429 rows of `docs/reviews.jsonl`.

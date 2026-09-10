# D-556 — An amendment to governing prose seats `revision-diff`, and the cap on causes goes

**Landed by** [PR #556](https://github.com/Grimblaz-and-Friends/tradecraft/pull/556). Closes no issue: both terms were left open by [#542](https://github.com/Grimblaz-and-Friends/tradecraft/issues/542), which closed with [PR #545](https://github.com/Grimblaz-and-Friends/tradecraft/pull/545) before they were ruled. Evidence pinned at `18af6c6` unless stated. **Supersedes [D-545] on the lane rule's buyer sentence and on the cap**, and nothing else in it.

## What was decided

[#542](https://github.com/Grimblaz-and-Friends/tradecraft/issues/542) shipped four rules and left two terms unsettled, both marked in its affirmed brief as the session's rather than the owner's. He ruled both on 2026-09-10, each put to him argued with options and a recommendation.

**An amendment to governing prose seats `revision-diff` beside the cold pass — one seat, not a panel.** And the two undefined names in that bullet collapse to one, `substantially new prose`, which is the roster's own term for the shape it selects on.

The bullet carried *"newly written foundational prose"* as the panel's trigger and *"substantially new prose"* as half of the fifth seat's, neither defined anywhere. Before #542 the ambiguity was absorbed by *"when in doubt, this lane"* pointing at the panel: a session that could not tell fell **up** to four seats. #542 moved that clause to the routine lane, so doubt fell **down** to one and the undefined term became the sole gate.

**The evidence that this was live rather than theoretical arrived on #542's own review.** Recorded finding R23 already had a consumer session filing a change as the routine lane and reaching five only by reasoning from claim density. Then #545 — itself an amendment to governing prose — took the one-seat lane under its own new rule and **lost three findings of one class**: a load-bearing sentence whose meaning changed without the change being recorded. That is exactly the `revision-diff` lens, and the one-seat lane did not seat it. Codex found one, CodeRabbit found two more after its rate limit reset. The seat rule is aimed at the measured failure rather than at the ambiguity in the abstract.

**The trigger needs no new definition.** `roster.md` already fixes *governing prose* for this choice in the broad sense — *"prose a later session is expected to act on, reaching a docstring that states a calling contract and not confined to always-on surfaces and cells"* — which is what [#236](https://github.com/Grimblaz-and-Friends/tradecraft/issues/236) closed on.

**The cap of three causes per review goes.** Two grounds, and the second is the one that decides it.

- **It never bound.** Two experience sessions on #542's material, twelve findings each, one filing each; and #545's own review disposed of nine findings and filed nothing at all. The three rules ahead of it emptied the queue before it was ever reached. There is no run in which it did anything.
- **Where it would bind, it wrote a falsehood into a record nothing may correct.** A fourth cause reaches the cap only by having *passed* the filing bar — for governing prose, an incident from real work or a run — so somebody has judged it worth someone's time. The cap then ruled it `record`, which `arbitration.md` defines as *"the evidence that acting is worth it not yet there"*, and `the-record.md` as *"by construction a worth-it judgment the evidence did not settle."* Both are false of a capped-out cause. Its only exit was recurrence, which for a one-off subject may never arrive.

**#545's review sustained that as a finding and did not fix it**, on the terminal stage's own recommendation that it ride the owner's ruling on the cap instead. Struck, the finding is discharged with no fix owed — which is what that deferral was for.

## What was rejected

**Adding *amendment to governing prose* to the panel buyers.** It was rejected while #542 was being built and again here. Nearly every change in this repository amends governing prose, so it re-inflates panel use to something close to universal and defeats what #542 was for. Seating one extra seat is a fraction of that cost and targets the same lens.

**Defining the two names as two separate bars.** More precise and more words, on a cell already at its constant. One name for one bar is what the roster already assumes.

**Keeping the cap with a reconciling clause.** That was the alternative if the owner kept it: a sentence distinguishing a capped-out cause from an ordinary record entry. It buys prose on a governing surface to repair a rule that has never fired.

**Replacing the cap with a reporting duty** — *a review filing more than three causes says why in its report* — was offered and not taken. Nothing now caps filings; the three rules that do the work are the record route, the text-only limb, and filing by cause.

## What this cost, and the one thing to look at

`skills/adversarial-review/references/arbitration.md` **−319**, `skills/adversarial-review/SKILL.md` **+54**; net **−265** characters. Unit is decoded UTF-8 characters, which is what `tools/lint.py` measures, derived as `len()` at `18af6c6` and at this branch. **The commit message states `arbitration.md` at −309 and that figure is wrong**; this is the derived one.

**The cell body lands over its constant.** `adversarial-review` **9,843 → 9,897** against 9,855, so **42 over**, where #542 had just brought it 12 under — 9 over at that change's base, 12 under at its tip, 42 over here. That is close to what the seat rule costs to state. No deletion was found that pays for it without removing something load-bearing: the candidate was the report's lane-recording obligation, which `skills/adversarial-review/references/the-record.md` also carries as a report field, and it was kept because the reader who acts on it is the one choosing the lane rather than the one writing the report. A body over its constant raises a pool item rather than refusing anything.

## The process this took, recorded because it departs from the default

A change that states rules ordinarily gets a brief settled with the owner and a pre-implementation artifact. **Neither was written here, on the owner's ruling** — both questions were put to him argued and answered in conversation, and he then ruled *"if it's just a simple change for each, we can just make a simple PR."* Ruling the process weight is his. No brief was settled, so no `docs/settling.jsonl` row is owed. The review still runs, under the rule this change introduces: an amendment to governing prose, so the cold pass plus `revision-diff`.

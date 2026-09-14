# D-617 — Source-comparison receipts, and a checker chosen by a property rather than a list

**Purpose:** preserve why the external pass got an executable receipt while the record checker got only a new selector, why the enumerator is bounded to the external pass, and what the run demonstrated about its own subject. **Audience:** a future session widening the enumerator beyond the external pass, revisiting which of a holder's writing is independently checked, or reopening whether a receipt should ignore cosmetic drift. **Success:** they can tell which claims here rest on a run and which on judgement, and they do not rebuild what was deliberately not built.

The owner affirmed [the implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/607#issuecomment-5659412506) after a design sitting; the artifact settled in one cold round, `would`, before the first commit.

## One cause, and the owner ruled it

#607 and #610 were filed separately and read as two problems: evidence assembled incompletely, and an independent checker pointed at some surfaces and not others. The sitting put the parentage question to the owner and he ruled *"one cause"*. The cause the implementation brief names is that **nothing compares what a holding session produced against what it was produced from** — #607 being that at the fetch and #610 at the prose.

**The two halves got different instruments and that is the decision worth keeping.** The fetch half is executable, so it got a command that refuses a read it cannot show complete. The prose half is not, so it got a selector change and no machinery at all. A session reaching for symmetry here should know the asymmetry was deliberate: a guard was built only where prose already stated the concept in one sentence and a machine could check it.

## Why the enumerator stops at the external pass

The owner ruled *"external pass only"*, answering the reach question #607 deferred. **That bound is on the command and not on the checker** — a distinction put to him explicitly before affirmation with the note that the narrower reading would empty half the change, and not corrected. Every dispatch assembled from a query has the same exposure; none of them is fixed here.

## The supersession, stated because a frozen record cannot state it itself

This change **supersedes [D-601](D-601-2026-09-13-dispatch-settings-and-evidence.md)'s narrowing** at its amendment paragraph, where the owner's amendment on #592 confined the fresh checker to *"only the change's own records — its decision entry, decision-index row, settling row and artifact settlement block"*. The checker is now selected by a property: holder-authored, durable, and carrying claims established by the tree, GitHub state or a stage return. That reaches the review report and the pull request body.

**D-601 is not made false by this.** This repository's own rule is that such content can only be superseded and not falsified, the record being of what somebody judged rather than of what the tree does. D-601 remains true of what the owner ruled on #592; this entry is where a later reader learns it was replaced.

**The review disputed this and was wrong in its filed form, which is worth keeping.** A seat read the widening as reversing an owner ruling without a marked ask. The terminal stage read the affirmed implementation brief, found the owner had affirmed the widening in his own plain-terms paragraph, and cut the finding from High to Low — leaving only the obligation to name the supersession, which is this section.

## What the run demonstrated about its own subject

**The instrument caught its own pull request drifting, twice, unprompted.** Two collections minutes apart returned identical counts — 5 / 6 / 2 / 13 — and different digests; replay named the object and a diff showed what moved. The second instance moved **two characters** in a configured reviewer's own comment. **No count could have seen either.** That is the change's central claim demonstrating itself, and it is also the reason [#619](https://github.com/Grimblaz-and-Friends/tradecraft/issues/619) exists: a receipt that goes stale on cosmetic churn, and a drift line that cannot say what moved, is a reconciliation loop with no stated terminator.

**The change's own rule collided with the roster on first use, and the roster won.** The new `dispatch.md` sentence put the external bundle inside the byte-identical shared block; `roster.md` withholds the pull request's comment thread from a cold seat. Staffing this change's own panel, the holder chose the roster and **broke byte-identity to do it** — the `cold-read` dispatch carried none of the bundle where the other four carried all of it. Two seats filed the collision, the defense demonstrated the breach from the dispatch bytes, and the remedy landed in `roster.md`, where the file already carried the pattern for exactly such a carve-out. **A rule that has to be departed from on its first use is the cheapest possible evidence about that rule**, and it was available only because the change was pointed at itself.

**Four of the review's findings were against the holding session's own records**, and the mechanism this change installs is what would have caught them. The pull request body carried four false figures because it was written before a repair commit and never re-derived after the push it described; a dispatch told all five seats the external bundle was collected one commit behind the head under review, which the bundle's own `commit_id` fields falsify. That last one is why `the-stretch.md` now says a dispatch's **factual** block is source-checked with the account it belongs to, while the dispatch as an instruction stays outside — a remedy the fix batch initially missed, having read the finding as wholly a record defect.

## What was deliberately not built

- **No widening of the collected population**, though the review established it is incomplete in both directions: automation writes into the pull request body itself and into check runs, neither of which is one of the three collections. The wording was qualified instead; widening `SOURCES` would change the bundle schema and was pitched, not bought.
- **No pre-posting check moved ahead of the terminal ruling.** The report's source check runs after the ruling and before posting; that placement was the artifact's reading, disputed by the other A/B arm, and ruled by the cold seat as not the owner's under the fork test.
- **No coverage bar adopted.** A configured reviewer's failed docstring-coverage check was lapsed on this repository's own convention, with the note that adopting such a bar would be the owner's call and not a review's.
- **No durable link mechanism.** The change requires a report carrying a receipt to carry a durable link to its uncommitted bundle and supplies no way to mint one. The requirement went unmet on this change's own report, named there rather than papered over.

## The run's shape, because the owner directed it

The artifact was written twice from the same affirmed implementation brief on a byte-identical dispatch — `gpt-5.6-sol` and `gpt-5.6-terra`, both at `xhigh` — and selected by a blind rating. **Sol cost 1.99× terra and the gap was almost entirely the rate card**: total input differed by 3.468% and sol emitted 1.33× the output tokens. The cheaper runtime produced the better-evidenced artifact, having run the page-loop contract live; the dearer one produced the better-engineered artifact and was chosen. Implementation ran on terra regardless, as the owner set. **The A/B twice caught what a single run would have shipped** — an invocation spelling the portability guard rejects, and a build order inverting settle-before-build — and the resumed winner corrected a wire claim the holding session had handed it.

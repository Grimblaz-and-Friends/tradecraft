# D-544 — A review disposes of its own findings, and only a decided cause leaves it as a number

**Landed by** [PR #544](https://github.com/Grimblaz-and-Friends/tradecraft/pull/544), closing [#542](https://github.com/Grimblaz-and-Friends/tradecraft/issues/542). Brief affirmed 2026-09-09 at [issue #542 comment](https://github.com/Grimblaz-and-Friends/tradecraft/issues/542#issuecomment-5609820464); artifact at [comment 5609956394](https://github.com/Grimblaz-and-Friends/tradecraft/issues/542#issuecomment-5609956394). Evidence pinned at `69ba49f` unless stated.

## What was decided

Every review here ended by creating issues, and it created them without anyone having decided the item was worth doing. Since the trial opened at 2026-09-04T22:34Z, 37 pull requests merged, 153 issues were created and 68 closed as completed. Three paragraph-sized changes landed overnight and their reviews filed seventeen issues, six rated lowest on both scales. Four rules move, on four shipped surfaces and one repo-only cell.

**A `record` ruling writes an entry and files nothing.** This reverts a term [#434](https://github.com/Grimblaz-and-Friends/tradecraft/issues/434)'s stage two landed at `ccacec2e` ([PR #441](https://github.com/Grimblaz-and-Friends/tradecraft/pull/441)) — that where the repository keeps a pool, a record is filed into it as well, *"which is what stops the record being a list nothing reads"*. **That premise was wrong when it was written.** `skills/adversarial-review/references/dispatch.md` already has every review fetch the findings record before its first dispatch — *"Findings an earlier review recorded against this artifact are fetched before the first dispatch"* — and a seat meeting an entry again is what promotes it. The record had a reader; the term added a second one and a number with it.

**A finding whose only consequence is that the text is wrong is fixed or dropped, and takes no entry and no number.** Clause (b) of `arbitration.md` routed exactly that class to `record`, and made it *"the precedence wherever fix and record both fit"*. A docstring, a comment, a wording is now fixed in the batch or dropped in the report with its reason. What stays `record` is the other limb alone: real, evidenced, and the evidence that acting is worth it not yet there.

**At most three causes leave one review, and every unfixed finding has exactly one of three ends** — a comment under a cause this review filed, an entry in the record, or a drop with its reason. The once-per-cause rule was already there and carried no number, so three filings against one edit in one night passed it.

**The one-seat lane is what a review runs by default.** `Choosing the shape` sent doubt to the panel — *"high blast radius — and when in doubt, this lane"* — and three of the last four reviews here were panels on paragraph-sized changes. Doubt now runs the one pass; the panel is bought by newly written foundational prose, new scripts or high blast radius, and declared risk buys width beyond either.

**Sites.** `skills/adversarial-review/references/arbitration.md` (clause (b), the pool-filing sentence, the once-per-cause paragraph, the refused-cause paragraph, the weight-argues-weight paragraph), `skills/adversarial-review/references/the-record.md` (the entry's fields, and the `issue` key it obliged), `skills/adversarial-review/SKILL.md` (both pointer lines and `Choosing the shape`), `skills/filing/SKILL.md` (the success line and the one exception to the prose bar), `docs/cells/records/SKILL.md` (where a `record` ruling goes).

## What was rejected

**Migrating the entries the term already wrote.** Records are exhaust; `docs/recorded-findings.jsonl` keeps every `issue` key it carries, because that filing did happen. The records cell now says so on the sentence that used to say the rulings themselves were not migrated.

**Making the refresh note's arrival-against-closure line obligatory.** The brief's measure — issues filed against issues closed, which has to fall below one for one — is read off a line `docs/cells/board/SKILL.md` already obliges: its watch-items bullet is *"Rate of arrival against rate of closure"*, and the drift-look section names the command supplying the arrival half. This change's own artifact first claimed nothing obliged it; that was false about the tree and the cold seat caught it. Nothing new is built to take the measure.

**Restating the doubt rule in both lane bullets.** It was written twice in the first draft. A restatement is what drifts, so it has one site: the bullet a chooser lands on.

## What this change did not settle

**Which issues the reverted term's closure covers is the owner's, and is open.** The brief's term is *"The handful of issues that term created are closed with a note naming their entry in the record."* It is not a handful. Every entry appended to `docs/recorded-findings.jsonl` at or after the term landed that names an issue was filed by it — the file held 314 lines at `ccacec2e^` and 323 at `ccacec2e` — which is **39 issues, 37 still open**, about a quarter of the pool. Twenty-seven of those were filed at the floor on both axes, which is the rating the term itself dictated; ten were rated above it by the filer. The recommendation put to the owner is to close the 27 and leave the 10, and **no issue is closed until he rules**: closing 37 live issues is an act no edit at review takes back and the map does not account for, and what he affirmed and the size of the class are not the same thing. The ask is at [comment 5609960202](https://github.com/Grimblaz-and-Friends/tradecraft/issues/542#issuecomment-5609960202).

**The cap of three is the session's term, not the owner's**, marked as such in the brief's affirmation record so it can be struck without touching the other three rules. Struck, the once-per-cause rule reverts to carrying no number and the three-ends sentence stands on its own.

## Cost

Net **−922 characters** across the five surfaces, every one of them negative: `skills/filing/SKILL.md` −413, `skills/adversarial-review/references/the-record.md` −279, `skills/adversarial-review/references/arbitration.md` −143, `docs/cells/records/SKILL.md` −82, `skills/adversarial-review/SKILL.md` −5.

**No cell body here grew, and two that were over their constant came in.** Measured with `python tools/lint.py` at `69ba49f` and at this branch: `adversarial-review` 9,864 → 9,859 against a constant of 9,855, so it is still 4 over but 5 less over than it was; `filing` 28,435 → 28,022 against 24,158; `records` 8,873 → 8,791 against 8,873, from exactly at its constant to 82 under. The first draft of `Choosing the shape` did grow the cell by 96, and three passes of consolidation took it back past where it started — folding the doubt rule to one site, merging the two declared-risk sentences, and moving this entry's own rationale out of `skills/adversarial-review/references/arbitration.md`.

One cold seat, one round, verdict `would`. Five corrections were made to the artifact after that verdict, each one the seat itself supplied the true version of, so the revision touched nothing the verdict turned on; the one that mattered was the false claim about the refresh note, above.

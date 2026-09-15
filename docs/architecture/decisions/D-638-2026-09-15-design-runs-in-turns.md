# D-638 — Design runs in turns, and the implementation brief makes every reader's outcome visible

**Landed by** [PR #638](https://github.com/Grimblaz-and-Friends/tradecraft/pull/638). Closes [#637](https://github.com/Grimblaz-and-Friends/tradecraft/issues/637). Governed by the [implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/637#issuecomment-5675050090) and its [affirmation record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/637#issuecomment-5675058184), affirmed on 2026-09-15. Evidence about the built tree is pinned at `09b9c97725edc273fc7f12c05887f45e920f7cb7` over base `b0a1f0f638d46dbe89e6c44361868b5e344d2f59`.

## What was decided

**Every non-mechanical change is designed with the owner in turns, with no trigger and no separate sitting.** A turn adds one decision-bearing layer and hands the work back: the session holds the pen, keeps the built-so-far line visible, and asks the owner for the idea or judgment only they can supply. The guess, strongest case against, named altitude, hunch as data, small build, and bounded divergence are habits of that one form rather than steps selected by a classifier. The smallest run is still one read and one affirm; removing the trigger does not require lengthening a coherent change.

**The session judges when the concept is done, puts the whole item, and the design ends only on affirmation.** The boundary is whether another turn would add a decision or only session-owned execution detail. Before the put, the session checks that every decision row has its Why, every reader cell is filled, and no row is execution detail. That check replaces the implementation brief's old scoring pass over the paragraph form's disqualifiers; descriptive plain briefs retain their disqualifier pass. The affirmation record carries what this pre-put check removed, or that it found nothing.

**The affirmed item keeps the name *implementation brief* and replaces its paragraph form.** It has one Shape sentence, names its Readers once, carries every decision that matters as a row with its Why and one cell per reader, and ends with Not this. This supersedes [D-602](D-602-2026-09-13-the-implementation-brief.md) on the implementation brief being a subtype of the paragraph form, while keeping D-602's distinction between the owner's terms and session-owned execution detail. It also supersedes [D-414](D-414-2026-09-05-the-design-sitting-and-three-habits.md) on a triggered sitting and on exactness requiring owner-authored words: the affirmed item itself is kept exact, none of it needs to have been typed by the owner, and an affirmation record quotes each push that changes a row once.

**The worked example becomes the fourth habit of every ask, and artifact acceptance criteria trace to the new term.** An explanation or proposal arrives built on a real case where reasonable; where it is not reasonable to build, the session says why and describes the case. In an artifact, every reader cell not marked `unchanged` has a criterion, every criterion names its row and reader cell or is labelled execution detail, and a cell-less criterion that is not execution detail exposes a decision that never received a turn. The cold seat checks both directions and judges whether a plausible builder would deliver every non-`unchanged` reader cell.

**From the start of build onward, a surprise is a diff against Shape and then the reader cells.** A wrong Shape stops because the affirmed term no longer covers the change. A changed row or reader cell becomes a proposed contingent row, put with the recommendation and its strongest case against while the run continues on that recommendation; a seat judges both readings. A surprise changing no cell is reported and the run continues. This narrows [D-436](D-436-2026-09-06-successor-stop-ordering.md): before build, a belief that the affirmed term is wrong still takes the amendment-and-re-settle route and build does not begin; from build onward only the Shape belief stops, while a row belief continues through the contingent-row route. The distinction preserves the owner's stated aim that most runs complete without intervention after build begins without widening the authority test for other questions.

## The file reading that built it

- `skills/engagement/SKILL.md` carries the one-form concept, the whole-item distinction, the fourth ask habit, the cell-aware surprise entry point, and the index to their depth.
- `skills/engagement/references/design-sitting.md` keeps its filename but is retitled and rewritten as *Designing in turns*. Frozen decisions and append-only records already cite the path; `git grep -n "design-sitting.md" 09b9c97725edc273fc7f12c05887f45e920f7cb7 -- docs/architecture/decisions docs/settling.jsonl` demonstrates those references. The locator therefore stays while no trigger, sitting mode, or close procedure survives in its contents.
- `skills/engagement/references/the-brief.md` owns the item, the pre-put row/Why/cell/execution check, whole-item affirmation, exactness, and its record. `the-ask.md` owns the four habits, including the real case and the reduced exact-words rule.
- `skills/engagement/references/the-artifact.md` owns row-and-reader-cell tracing and the boundary between execution criteria and a missing design turn. `cold-seat.md` puts the two-direction trace check into what the seat receives and sharpens `would` to delivery of reader cells.
- `skills/engagement/references/the-handoff.md` owns the before-build versus build-onward boundary. `the-stretch.md` owns the Shape/row/no-cell branches, the contingent row's carrier, release priority, and continuation. `waiting.md` loses the now-false instruction to draft until a brief could lock; its marker distinguishing a draft restatement remains because an unaffirmed draft is not the exact affirmed item.
- `.claude-plugin/plugin.json` carries the shipped-zone version bump, and the generated Claude and Codex roster copies carry the revised `engagement` description. `AGENTS.md` remains untouched because its Convergence ordering remains true. The decision entry and this index row are the only record work in this commit; the holder owns the settling row.

## The charter was read and left alone

The artifact proposed narrowing one charter clause. The settling seat observed that leaving it untouched satisfies every reader cell, and the build followed the narrower cost rule: edit an always-on sentence only where the new cell makes it false. The sentence checked was, at `09b9c97725edc273fc7f12c05887f45e920f7cb7`:

> **Every surface the owner enters opens with a plain brief; an implementation brief is a specific kind of brief with its own standards and binds when affirmed.**

The new implementation brief remains a brief, has its own standards, and binds on affirmation; only its paragraph form changed. The owner-authored sentence D-602 records as kept verbatim therefore stays verbatim. `git diff --quiet b0a1f0f638d46dbe89e6c44361868b5e344d2f59 09b9c97725edc273fc7f12c05887f45e920f7cb7 -- skills/charter/SKILL.md` demonstrates that no charter byte moved. Because the charter was not edited, no always-on outflow choice was made or owed.

## The artifact took two cold rounds

The first seat judged the initial artifact and returned `would not` on two points. First, its file map omitted `the-handoff.md`, leaving D-436's broad successor stop able to contradict the new continuation rule. Second, the row 8 governing sentence began at the unattended stretch rather than at mid-build, so it competed with `cold-seat.md`'s amendment-and-re-settle route while the artifact itself was still being settled.

Revision 2 added `the-handoff.md` to the map and drafted the exact stage split: before build, amend and re-settle; from build onward, continue on a row recommendation and stop only for wrong Shape. It narrowed the surprise sentence to the start of build, stated that `cold-seat.md` governs at the artifact stage, added a criterion across that boundary, and carried the adverse points beneath the purpose header. A fresh seat judged revision 2, returned `would`, and named no point. The settlement paragraph changed only the status and records both rounds; no claim changed after the successful verdict.

## Rejected

- **A trigger, fork count, or other classifier selecting the conversation form.** A session classifying its own work is the failure this change corrects. One turn form for every non-mechanical change makes the owner's participation present without requiring a ceremony to open it.
- **A scheduled owner read of a summary.** The owner sees the next decision-bearing layer each turn and the whole item at affirmation. A separate summary sitting would add a second form and spend attention even where one read and one affirm are enough.
- **Widening the fork test to classify surprises.** The authority test still decides whose call a question is. From build onward, surprises instead compare directly with the term the owner affirmed: Shape, then reader cells, then report-only. Importance and a generic owner-fork judgment are not competing surprise classifiers.

## Vocabulary deliberately left outside this cell

The `filing` cell's owner-provenance gloss still includes “came out of a sitting with them”, and the repo-only trial-intake tool and its tests still recognise “design sitting” as historical provenance. Neither is a trigger or an instruction to open a second conversation form. They were left because this change repairs the `engagement` cell and [#577](https://github.com/Grimblaz-and-Friends/tradecraft/issues/577) follows it; changing another cell or its repo-only parser would widen this decision. The remaining sites are demonstrated by `git grep -n -i -E "design sitting|came out of a sitting" 09b9c97725edc273fc7f12c05887f45e920f7cb7 -- skills/filing/references/what-a-filing-carries.md tools/trial_intake.py tools/tests/test_trial_intake.py`.

## Evidence and figures

The implementation surface and its generated mirrors are given by `git diff --name-only b0a1f0f638d46dbe89e6c44361868b5e344d2f59 09b9c97725edc273fc7f12c05887f45e920f7cb7`; its shape is given by `git diff --stat b0a1f0f638d46dbe89e6c44361868b5e344d2f59 09b9c97725edc273fc7f12c05887f45e920f7cb7`. Run `python tools/lint.py` and `python tools/check_version_bump.py` in a checkout at `09b9c97725edc273fc7f12c05887f45e920f7cb7` for the governing-prose and shipped-version guards. No derived output is frozen here.

[D-414] [D-436] [D-602]

# D-327: The board's two reads are different objects, and four GitHub behaviours are load-bearing rather than incidental

**Status:** Accepted 2026-09-02 (PR #327)

## The condition

The answer to *what should I pick up next* was produced by hand and lost with the conversation that produced it — [#83](https://github.com/Grimblaz-and-Friends/tradecraft/issues/83) records two such rankings in two days, each sound, each gone. The board this landed is the standing home for that answer. What follows is what a future session would otherwise re-derive by breaking it, and each of the four behaviours below was found by running the API rather than by reading its schema.

## Reconciling and settling are two jobs, and only one may halt

`tools/board.py` runs: target, reconcile, settle, order, note. (Pinned by path against this pull request's merge base `0b81d27`, not by a branch commit: this repository squash-merges, so a branch sha resolves in no plain clone afterwards.) **Reconciling** asks whether the board holds the open set. **Settling** asks whether the ordered read has caught up with the board. They return opposite answers about the same newly added issue — reconcile says place it, settle says wait for it — because reconcile's own writes are what make the ordered read short.

An earlier draft merged them into one membership comparison that halted on any mismatch. A cold seat walked it and found it would halt after *every filing*, which the artifact itself called the normal steady state: the item reconcile had just added was, one step later, "a board member missing from the ordered read". The board would have stopped refreshing the first time anyone filed an issue. **Merging them back is the undo this entry exists to prevent.** Reconcile never halts; settle halts only on exceeding its bound, and nothing writes an ordering from an unsettled read.

## `totalCount` goes stale in lockstep with the list it counts

`items(orderBy: {field: POSITION, direction: ASC})` is stale for several seconds after any write. The trap is that its `totalCount` is stale *with* it: a spike adding twelve items read back ten items and a `totalCount` of ten, together. **So a short read cannot be detected from the connection's own count**, and a script that checks the two against each other reports success over an incomplete set.

The target membership therefore always comes from `gh issue list`, never from the board. This is the same defect the hand-ranking hit from the other direction — its closing line claimed 65 open placed where it placed 81 — and it is why the reconciliation is written against an external authority rather than a self-report.

The read *without* `orderBy` returned the full membership at the moment the ordered one was short. That is an observed run and not a deduction: `ProjectV2.items` declares a `defaultValue` of `{field: POSITION, direction: ASC}` for `orderBy`, so the two queries should be identical and observably are not. An implementer who reads the schema and "corrects" the unordered read to pass `orderBy` explicitly makes the worse read the only read.

**But the unordered read is not fresh either, and the design does not rest on its being so.** A trial run's second pass read 78 of 86 items from it. What makes acting on a stale step-1 read safe is that its only consumer is the add/archive decision and `addProjectV2ItemById` is idempotent — a redundant add, never a duplicate — and that settling is the gate everything downstream waits on. Reading either board query as authoritative is the misreading; the external issue list is the authority and the idempotence is the tolerance.

## A single-select option re-sent without its id clears the field

`updateProjectV2Field` overwrites the option list wholesale. An existing option sent by name alone is recreated under a new id, and **every item value pointing at the old id is silently dropped** — a successful-looking write, no error, no warning. `ProjectV2SingleSelectFieldOptionInput.id` says so outright: *"Include this to preserve the option's identity during updates, preventing item field values from being cleared."*

The seed lost all of its `Bundle` values to this before it was found, and found it only because the board was read back and the column was empty. Every option-list write now sends existing options with their ids, and every option a run needs is added in one write rather than one per value, because each such write is another chance to clear the field. `test_ensure_options_sends_existing_options_with_their_ids_and_appearance` holds it at the call site, which is what decides; the renderer's own test could not see the defect, because the renderer was never the thing that decided. Both go red against the reintroduced fault.

**Rejected as a consequence: single-select option order as a second ordering primitive.** Ranking bundles by reordering the `Bundle` field's options is expressible and would have been cheaper per move than walking item positions. It was rejected because it makes every rank change a wholesale option rewrite — the destructive write above, on the hot path — and leaves two notions of order to reconcile. Item position is the sole ordering primitive.

## `statusUpdates(last:N)` returns the OLDEST notes

The connection declares `orderBy: {field: CREATED_AT, direction: DESC}`, so Relay's `last: N` slices the tail of a newest-first list — the N *oldest* updates. Settled by run rather than by schema: three notes posted in sequence to a scratch project returned `NOTE-ONE` for `last:1` and `NOTE-THREE` for `first:1`.

This mattered because the command that reads the notes back exists to stop the board's reasoning evaporating between sessions. Under `last:N` it would have served the seed note forever from the second refresh onward — the failure it was added to end, reintroduced in a form harder to notice than the absence had been, and invisible while the board held one note. `read_notes` asks for `first:N` and **states the ordering rather than inheriting it**, because a default that is right today is not a claim the next reader can check.

## `Band` is the ranking's shape; `Status` is availability

These look redundant and are not, and collapsing them is the second undo worth naming. **`Band`** records where in the ranking's own stratification an item sits. **`Status`** records whether it can be picked up. A cold seat caught the artifact building the first and not the second, on evidence that settles it: at seed, positions 1 and 2 are `#83` (`In progress`) and `#138` (`Deferred`), while the ranking's own answer to *what next* is further down. **A consumer that reads position 1 gets the wrong answer**, and a consumer that reads `Band` gets it too — the hand-ranking's `Standing` group held four items of mixed availability, of which the board carries two — `#83` in progress and `#138` deferred. The rule is the first item not marked `In progress`, `In flight`, `Blocked` or `Deferred`, **and not blank** — `sync` adds items without writing any field, so between a sync and the apply that ranks them every new item carries no status at all, and counting that as available is the same defect through a route no plan passes.

**`In flight` is asserted, not corroborated.** The settled artifact said the built-in read-only `Linked pull requests` field would corroborate it, so that the one state changing without anyone touching the board would maintain itself. It does not: the transport reads only single-select values, no subcommand surfaces the field, and `Status` is hand-written from the plan like every other value. The cell tells a refresher to read that column; making the transport read it is left open, and the sentence is corrected here rather than left standing as a description of something built.

## What was rejected, and what was left open

**Severity and cost labels, and RICE/WSJF scoring**, both rejected in #83's own filing and again at convergence: they display a ranking judgment rather than producing one, and the arithmetic is pseudo-precision at this board's scale.

**A ranked file in the repository**, rejected because every re-rank becomes a pull request — too expensive for something that moves on every merge, and squarely the bookkeeping-PR tripwire the records material names.

**Epic-level grouping.** [#218](https://github.com/Grimblaz-and-Friends/tradecraft/issues/218)'s deferral trigger has fired — the hand-ranking carried about ten groups and the grouping is load-bearing for the whole order — but this change absorbs only the flat `Bundle` label. #218's own subject is untouched: the parent convergence artifact, the emergent criteria no child owns, and the value-alone-where-possible criterion. A label states membership and says nothing about a group's shared *done*, which is precisely what #218 says is missing.

**Anything that decides when the agent runs**, excluded by the affirmed brief. No schedule, and no trigger added to the landing procedure or the doctrine. Staleness between refreshes is a consequence the owner accepted, not a hole.

## A fired reopen condition, named rather than left to be found

[D-128](D-128-2026-08-23-filing-cell.md) named the `filing` cell `filing` rather than `board` precisely because *"`board` would promise the ranking of [#83](https://github.com/Grimblaz-and-Friends/tradecraft/issues/83), which this does not build"*, and set **`Reopen on: #83 landing`**. That condition has now fired. This change gives *the board* a second, narrower referent — a Projects v2 project holding only open issues — while `filing`'s always-loaded description still opens on *"How a piece of work gets onto the board"* meaning the issue list.

**No consumer failure follows from it**, which is why nothing is rewritten here: `filing` operationalises its search two lines later as two named `gh` commands, both against the issue list, and the transport has no search at all. What remains is two always-loaded descriptions opening on one word with two referents. Reconciling them edits the shipped zone, which this change's boundary keeps untouched, so it is left to be designed once across `filing`, `engagement` and this cell together rather than patched at one of them.

## The doctrine's outflow

The fourth repo-only cell made `AGENTS.md`'s enumeration of them false, and an always-on edit owes an outflow. What was shed is the per-cell gloss: **every cell's description already loads in every session here and states what it covers**, so a gloss in the doctrine was a second copy to keep in step — the duplication this practice removes elsewhere, sitting on the surface that can least afford it. The names alone route. The always-on row after the change is inside its ceiling, priced by `python tools/lint.py` on the tree at hand.

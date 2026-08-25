# D-184: The always-on surface is one measured total, its ceilings ratchet, and outflow is owed on edit

**Status:** Accepted 2026-08-25 (PR #184)

## Context

#140 was filed against a doctrine file twenty characters from its budget, with the diagnosis that nothing had ever routed a rule out — the pressure valve was stated and had never fired. Two restructures later the file has 489 characters of headroom, and the diagnosis has been vindicated rather than answered: **the surface every session reads before acting grew through both of them.**

Measured on the trees themselves: **11,579** characters when the issue was filed (`AGENTS.md` 7,980 + no charter + 3,599 of cell descriptions), **15,065** after the charter split, **15,308** before this change. Each restructure moved prose from one always-on artifact to another and reported the file it emptied.

That was possible because no invocation reported the sum. `tools/figures.py` emitted the doctrine's size, later the charter's, and a per-cell description ceiling — three numbers about three surfaces, and nothing about what a session actually loads.

## Decision

**The always-on surface is one figure, reported for two audiences.** `figure_always_on` sums `AGENTS.md`, the charter's body, and every cell's `name` plus `description`, and reports the repository's total and an adopter's separately. They are different sets and conflating them is the error the figure exists to stop: a plugin's root `AGENTS.md` and `CLAUDE.md` land in a consumer's cache as inert files and are never loaded — owner-verified on this issue with a live control against an enabled plugin. An adopter reads the charter and the roster's descriptions and nothing else. Today: **15,160 here, 9,649 for an adopter.**

**Outflow is owed whenever an always-on surface is edited, not when a budget is reached.** It is the admission order read backwards — a rule a guard now holds becomes the rule plus the guard's name; a rule that binds only inside one activity moves to that activity's cell; a reason a decision entry already carries compresses to its citation. A surface that empties only under pressure empties once and refills, which is the recorded history of this one. Two constraints travel with it: it may never *drop* a rule, and it measures the whole surface rather than the file being edited, because routing a rule from one always-on artifact into another is the same cost under a different heading and reads as a reduction to anyone measuring one file.

The rule lives in `authoring`'s routing depth rather than its body, because its trigger is the routing trigger and the body had five characters of headroom. Its **firing condition is named in the always-loaded pointer**, since a session editing a doctrine file is not otherwise deciding where content goes and would not think to load it.

**Running the audit produced one move and one refusal, and the refusal is the more instructive.** The calling contract's runtime specifics compressed to `[D-156]`, which carries them. The zone wall's consumer-cache clause did not: [D-78](D-78-2026-08-19-carry-the-reasons.md) put that clause in the doctrine deliberately, because its absence had already caused a session to place content believing consumers never receive it. The outflow's first move is to read the citation, and here the citation said don't. **An audit that never declines is not applying the rule.**

**Both ceilings ratchet to what the tree measures.** `AGENTS.md` 8,000 → 6,000 against 5,511; the charter 6,000 → 5,600 against 5,353. Each margin is argued in the constant's own comment rather than here, so a session raising one reads the argument at the site it is changing. The charter's margin is deliberately tighter: its prose was not audited in this change, so the ceiling is the only pressure it gets.

**A cell body budget becomes a guard.** `authoring`'s cap of 7,359 was stated in #169 as that change's own evidence that depth-shedding is applicable rather than aspirational — and was enforced by nothing, living in a command string inside an entry that had frozen. `CELL_BODY_BUDGET_CHARS` holds it. The value is what #169's tree measured, not a new judgement; the point is that raising it is now a recorded decision rather than an edit nobody sees. It bit twice while this change was being written, which is the argument for it.

**Cells absent from that map are unbudgeted on purpose.** A number chosen for a cell nobody has argued about would be a ruling on its size arriving as a constant. `adversarial-review` is 30% of all cell prose and 2.22× the next largest; that is [#177](https://github.com/Grimblaz-and-Friends/tradecraft/issues/177)'s to decide, not this change's to pre-empt.

**#164 is discharged** — `AGENTS_BUDGET_CHARS` and `POINTER_BUDGET_CHARS` gain literal pins, on the ground its own filing states: a test deriving its bound from the constant it tests cannot catch a change to that constant. Every budget in the file is now red-probed, including the case where a budgeted cell is renamed away, which previously dropped the budget in silence because the guard skips a cell it cannot find.

**The callout carries the total.** A budget only bites where somebody sees it, and this one has only ever been read after the fact — in a write-up, by a session that had already decided what to add. The merge surface is the one moment the number can still change an outcome. A failed derivation degrades to a stated absence rather than a dropped line.

## Rejected

- **A roster aggregate ceiling.** It would make one cell's PR fail for another cell's prose. The aggregate gets a figure; the pressure it creates is informational, which is the correct shape for a shared resource no single change controls.
- **Per-cell budgets for every cell** (fork E.1, owner-ruled). Eight constants to choose and maintain, and a budget on `adversarial-review` either ratifies its current size or fails CI on day one — a decision about that cell smuggled in as a number.
- **Auditing the charter's prose** (fork D.1, owner-ruled). Its success criterion is that a session reading only it behaves correctly, which resists shedding by construction, and auditing it properly means re-deriving what a consumer needs — nearer #139's question than this one's. Measured and ratcheted instead.
- **Compressing the zone wall's consumer-cache clause**, on reading D-78. Recorded because a later audit will reach the same passage and should not have to re-derive the refusal.
- **A periodic sweep.** A scheduled re-reading of a file is a maintained record, which this repository's records rule rejects. The check is standing and fires on edit.
- **Making the outflow a doctrine line.** It is methodology about where content goes, and the surface it governs is the one it would have grown.

## Evidence

The affirmed artifact and the three rulings are on [#140](https://github.com/Grimblaz-and-Friends/tradecraft/issues/140#issuecomment-5411086400), with the affirmation recording them in the [comment beneath it](https://github.com/Grimblaz-and-Friends/tradecraft/issues/140#issuecomment-5411092445). The trajectory figures are re-derivable from the three trees named above; the current totals are emitted by `python tools/figures.py`.

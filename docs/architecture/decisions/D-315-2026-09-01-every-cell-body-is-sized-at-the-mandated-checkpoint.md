# D-315: Every cell body is sized at the checkpoint the flow already mandates, and nothing is capped

**Status:** Accepted 2026-09-01 (PR #315)

## The condition

`check_doctrine` iterates `CELL_BODY_BUDGET_CHARS`, not the cells. A cell absent from that map was sized by nothing at either command `docs/cells/landing/SKILL.md` mandates before a commit — **with one exception, and it is this entry's own headline**: `skills/charter/SKILL.md`'s body is a term in every always-on row, and the merge base already printed `charter body 5,851` at that very command. The unqualified form of this sentence is what a cold seat rejected in the artifact, and it survived into four restatements after the code had been repaired — and the cells absent from it had become the large ones. On the tree this landed against, the three governed bodies stood fifth, sixth and seventh — two under `CELL_BODY_BUDGET_CHARS`, the charter's under the always-on ceilings — and the largest unbudgeted body was more than twice the larger *body* cap.

That is [#302](https://github.com/Grimblaz-and-Friends/tradecraft/issues/302), which recorded a second instance from [#307](https://github.com/Grimblaz-and-Friends/tradecraft/pull/307)'s review: a change that reached past the only capped body it was weighing, with larger uncapped cells standing above both. **Narrowed deliberately** — D-307 §4 says *"No ceiling decided the placement, though one is named among the grounds for rejecting the alternative"*, and the wider reading was already amended out of this change's own artifact. "Budgeted" and "large" had come apart entirely.

## The decision

**Reporting and capping are separable, and this takes only the reporting half.** `CELL_BODY_BUDGET_CHARS`' own comment states why the map is sparse — *"a number chosen for a cell nobody has argued about would be a ruling on its size arriving as a constant"* — and that reasoning stands. Reporting a size asserts no number. The constant gains no entry, no cell newly reds, and the per-cell numbers wait on stage 2 of [#260](https://github.com/Grimblaz-and-Friends/tradecraft/issues/260), which redraws these bodies wholesale and would make any number argued now an argument against a partition about to be replaced. **The owner set that edge in the affirmed brief**, so it is theirs rather than the session's reading.

**A block, one row per cell, largest body first, whatever governs it.** Rows rather than one dense line because the ordering is the finding: it is what makes the coming-apart legible without the reader enumerating anything, and an ordering is only legible as rows.

**Derived from `roster.SOURCES`.** A hardcoded pair would pass every criterion while leaving a third source, added later, silently unmeasured — the list-shaped failure this change exists to remove, one level up.

**Hosted in `tools/figures.py`, loaded by path**, as `always_on_note` and `check_always_on_budget` already are. Pinned in the artifact rather than left to the implementer, because the report's own failure behaviour is testable only if a fixture tree can be built without the module it derives from; hosted in `lint.py` that criterion is vacuous rather than satisfied.

**Reports, never reds, and never goes silent.** It copies `always_on_note`, which states a figure it cannot derive and moves on. *Nothing to report* and *could not derive* each produce their own text, because silence says neither — and a report that vanishes when its input breaks reads exactly like a tree with nothing in it.

**Nothing evaluative.** No marker, threshold or word ranking a cell as large: that is a number invented for a cell nobody has argued about, and it would cross the brief's edge while changing no constant and redding nothing. The largest-first ordering is not such a marker — it orders every row alike and singles out none. The guard is a shape over every row rather than a list of forbidden words somebody thought of.

## The charter row, and the seat that caught it

**`skills/charter/SKILL.md`'s body is enforced today while absent from the map.** `tools/figures.py` folds it into every always-on row's `total` and into `adopter_total`, both of which `check_always_on_budget` reds on, at the same command. A report treating `CELL_BODY_BUDGET_CHARS` as the only budget in view prints `charter … no budget` — false, and false about the half of the brief that promises to say which cells have no limit.

**Three cold seats passed over this and the fourth caught it**, along with the fact that the acceptance criterion as then written *ratified* the wrong row instead of failing it. The row names both constants and says they are shared, stating no per-cell headroom: the row budget alone would read as ten thousand characters of room where the shared headroom is a few hundred, and the adopter total is the binding one — that is the same defect one step gentler, and it was taken as a reading amendment after the settling verdict.

## What was rejected

**A relative trigger** — failing when an unbudgeted body passes the largest budgeted one. It asserts no absolute number and fires exactly where the defect is, but it would have redded the tree on several cells immediately and forced the per-cell arguments the brief defers. Put to the owner in the brief with its cost stated; they took the brief as written. Recorded because a later session will reach for it.

**[#275](https://github.com/Grimblaz-and-Friends/tradecraft/issues/275), folded in by the first draft and dropped.** Its symptom is real and reproduces, but the misleading string is rendered in `figure_cell` at `skills/authoring/scripts/figures.py`, in the **shipped** zone: correcting it there is adopter-visible and owes a version bump, and correcting it in the repo-only wrapper leaves adopters with the wrong output. `tools/figures.py` is not a mandated checkpoint either, so #275 sits beside the brief's want rather than inside it. It stays open with that fork named.

**Joining `build_figures`' always-emitted list.** The artifact left it to the implementer; declined because the report's home is the lint checkpoint and joining would touch that module's docstring enumeration test for no gain.

**Capping a cell's total** — body plus everything beneath it. A ceiling on the total caps depth-shedding itself, which `CELL_BODY_BUDGET_CHARS`' comment already records.

## What the artifact cost, and what that bought

**Five cold-seat verdicts: two NO, three YES.** The blocking one was the charter row. The other NO landed on six points, one of which was a claim of this session's that inverted its own authority — it cited `always_on_note` as vanishing on failure when it does the opposite and is the model to copy.

**The ordering criterion was named by three separate seats.** Under [D-304]'s repeat rule that is evidence about the point rather than the sentence, and the diagnosis was **wrong shape**: each round chased one more ordering confound into a fixture — by name, by source, by budget status — and the set of wrong orderings a fixture must trap is not closed. Restated as a total property over the output, needing no fixture at all. That is the rule working as intended on its first use outside the convergence that produced it.

**Eight pins, each mutation-verified with bytecode cleared before every run** — the masking [#142](https://github.com/Grimblaz-and-Friends/tradecraft/issues/142) records. All eight went red against a mutation of the line they hold.

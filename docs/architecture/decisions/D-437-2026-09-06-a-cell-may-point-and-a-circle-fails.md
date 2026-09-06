# D-437: A cell may point at the cell owning a rule it needs, a circle of pointers fails the guard, and the always-on surface declares the roster

**Status:** Accepted 2026-09-06 (PR #437)

## Context

[#404](https://github.com/Grimblaz-and-Friends/tradecraft/issues/404), the second of the two roots the owner affirmed on 2026-09-05 under the cluster about full ceilings and copied sentences — *"I think your 2 roots are good."* Its sibling [#405](https://github.com/Grimblaz-and-Friends/tradecraft/issues/405) landed first, in [D-430](D-430-2026-09-06-intake-enters-the-board-by-cause.md).

**What the tree held at the base, `07511c3`.** `skills/authoring/references/cell-structure.md` said a skill *"names no sibling cell — name one and the two must move together from then on"*, with two escapes: the charter both ways, and a repo-only cell naming a shipped one. `tools/lint.py`'s `_name_form_is_sideways` enforced it on the reserved form `` `<name>` cell ``. The same bullet said what a session must then do: *"Where two cells both need one standard it gets one owning cell and the other carries none of it; routing it up to the charter is the fallback, reached only where no cell can hold it, that surface being the last resort."* The charter is always-on and budgeted by `ALWAYS_ON_ROW_BUDGET_CHARS` and `ALWAYS_ON_ADOPTER_BUDGET_CHARS`, so the fallback for a shared rule was a claim on one fixed pool. That is the cause the filing states, and thirteen open issues are linked under it as symptoms.

**The brief and what it corrected before it was drafted.** Settled in a design sitting on 2026-09-05 and affirmed there — *"affirm both, post them"* — at [comment 5555947422](https://github.com/Grimblaz-and-Friends/tradecraft/issues/404#issuecomment-5555947422). Three owner calls carry it: reach over waste, because *"it's hard to see when too much is loaded, much more obvious when too little"*; the always-on surface as router, *"I think the agents.md or charter being a router fits standard best practices… I'm good with this unless we see a better design"*; and code over prose wherever the ground is stable, *"as long as it fits in the right way"*. The shape came from his own challenge — *"we've solved this in code with build dependencies preventing circular dependencies for a while now… is there no way we can learn from coding best practices for prose?"* The filing's own fourth chain step, that a routing effect cannot be measured, had already been corrected on the issue and does not survive into the brief: [#272](https://github.com/Grimblaz-and-Friends/tradecraft/issues/272) closed by landing a rule for *when* reach is falsifiable, not by finding it unmeasurable.

## Decision

**1. The name form stops being judged one reference at a time and is judged as a graph.** `cell_pointer_graph` in `tools/lint.py` builds the practice's dependency graph from the reserved-form references between cells; `pointer_cycle_findings` reports a circle. A pointer is lawful, and a long chain of pointers is lawful. What a circle costs is what a circular dependency costs a build — neither end can be read, revised or removed without the other — and that coupling is what the ban prevented at the price of a copy.

**2. Three things the ban carried survive it, each for a reason of its own.** Every **path** form stays a finding, from the charter too: a rooted `skills/` path does not resolve once installed, while the name survives relocation, which is a reason self-containment never covered. `lib/` and `hooks/` may name **no** cell at all, neither being a cell, so deps still point down. And a **shipped cell naming a repo-only one** stays `check_cell_references`' finding rather than becoming an edge — reading it as an edge would price one defect as two and could report a circle one of whose hops is a finding rather than a pointer. The wall's refused direction therefore never enters the graph, and the cycle check inherits that rather than restating it.

**3. No cycle may run through the charter, and this is a decision rather than an omission.** Edges whose **target** is the charter are dropped before the graph is built; edges **from** it are kept. Two independent grounds, and either would be enough. A pointer at the charter loads nothing — an adopting repository has it before substantive work — so it can close no cycle *of loading*, which is what the check refuses. And keeping it would make every cell reach every other through the charter's own roster, so the reach figure below would report one number for the whole practice and rank nothing. Because no edge targets the charter, the exemption needs no second rule and the charter cannot sit in a ring.

**4. The finding names the ring member by member, with the line that makes each hop.** One representative circle per strongly connected component, found breadth-first from its alphabetically first member, so the same tree reports the same circle on every run. Not every simple cycle: a component can hold exponentially many, and printing them all answers a defect with a wall of text. Breaking any hop of the one printed changes the component, so the next run reports what is left rather than repeating itself.

**5. The reach figure is a note and never a finding, and no ceiling is created for it.** `python tools/lint.py` prints, per cell, the prose reachable by following every pointer transitively. A large reach is a fact about the graph, not a defect. A ceiling here would be a number chosen for a graph nobody has argued about — the edge `cell_body_note` already declines to cross — and it would cap the very pointer this change exists to permit.

**6. The unit is decoded UTF-8 characters, not bytes.** The placement reading posted on the issue said bytes, and it binds nothing by its own terms. Every other prose figure this repository prints — the always-on rows, the cell bodies, `figure_cell_total` — is in decoded characters, and two units inside one printed block is the confusion those figures' own comments were written to prevent. The basis is printed with the number, because a figure whose basis a reader cannot reconstruct is one they cannot act on.

**7. One prose measure, two readers.** `cell_prose` in `tools/figures.py` is extracted from `figure_cell_total` and used by both it and `pointer_reach_rows`. Two readings of *the prose this cell carries* would be two answers to one question, and the reach figure would then disagree with the per-cell figure a session read on the same run.

**8. The charter declares the roster: every shipped cell other than itself, with the one condition that loads it.** Shipped cells only — the wall forbids the charter naming a repo-only one, and an adopter has none of them; this repository's own four are already routed from `AGENTS.md`, which is its own editable surface. The line is a **load condition and never a second description**: each cell's description stays the authority on its triggers, and `skills/authoring/references/cell-structure.md` now says so, because after this change that file's *"the description is the whole triggering surface"* would otherwise be false.

**9. The roster's cost is admitted, not trimmed away.** It is always-on growth in every runtime row. `docs/admissions.jsonl` carries one row against `always-on-row`; the constants do not move. **The outflow ran over the charter paragraph by paragraph and found two things, both inside the item, and nothing outside it** — the roster's own closing sentence, which restated the pointer rule the `authoring` cell owns and which the line above it already routes a writer to, and its opening sentence, which explained itself twice. Nothing else sheds: every remaining paragraph is a rule that must bind before any cell loads, or a pointer at the cell that owns its depth, or the one rule whose reader has loaded no cell that could hold it, a decline recorded outside a review. Each was read against the question rather than assumed.

**10. The shipped half of check 5's cell predicate becomes the generator's, as the repo-only half already was.** It was a bare directory test, so a directory with no `SKILL.md` was a cell to that check and to nothing else — not to the generator, not to `check_cell_references`. [#291] had fixed exactly this on the repo-only half and left the shipped half standing.

**11. Nothing that could now be a pointer was made one.** No existing duplicated standard is collapsed here. This change lands the permission, the guard, the figure and the router; converting a specific copy into an owner plus pointers is per-symptom work with its own brief. The change is therefore judged on what a writer may now do, not on a reduction in duplicated prose, and none of the thirteen symptoms closes with it.

## The decision this reverses, named

`_name_form_is_sideways` carried, from [#260], the judgement that a repo-only cell naming another repo-only cell is *"the mesh of mutual references this rule exists to prevent, and which two cells in one repository can build as easily as two in a plugin."* That direction is now lawful, subject to the cycle check. **The premise is what changed, not the risk assessment**: a mesh is refused by shape now, where before the only instrument available was forbidding the first pointer. `test_the_walls_refused_direction_is_not_an_edge` pins that a ring built entirely from repo-only cells still closes the check. Named here because the charter has a prior decision superseded by reading it rather than obeyed, and the reviser owes the entry it supersedes a statement of what it reversed; a cold seat's unobliged observation is what surfaced it, the artifact having reversed it silently.

## Meaning changes, named

`skills/authoring/references/revising.md` requires every one where amendments are recorded.

1. **A cell naming a sibling stops being a defect and becomes the prescribed move.** Every rule keyed to *a cell names no sibling* now reads the other way. The reserved form is unchanged, so no existing text becomes unlawful.
2. **The charter's exemption stops being an exemption.** It was the single escape from a ban; it is now the one target whose edge costs nothing. Nothing a session may write changes, but the reason it may is different, and a later session tightening the "exemption" would be re-imposing a ban rather than narrowing a carve-out.
3. **The description is no longer the whole triggering surface** where a practice's always-on surface declares a roster. `cell-structure.md`'s first bullet is amended in place rather than left to be read as still true.
4. **Routing a shared rule up to the always-on surface stops being the fallback for two cells needing one standard** and is scoped to what it always should have been: a rule that must bind before any cell loads.

## What was deliberately left out

- **Direction rules on the pointer graph**, until a circle-free graph shows the need. The owner's own exclusion, carried in the brief.
- **Re-judging which open issues this cause explains**, including the two whose parentage is disputed on the record. The owner's exclusion.
- **Any measurement harness beyond the printed figure.** What sessions *actually* load, as against what they could reach, is named in the brief as later work.
- **A ceiling on reach**, per decision 5.

## Figures

Every figure this change turns on moves with the tree, and this entry freezes at its own commit. Derive them rather than reading a number here:

- the always-on rows, the adopter total and each cell's body: `python tools/lint.py`
- the pointer graph's reach, per cell, with its basis: the same command
- the governing-prose delta against this change's base: `python tools/figures.py --base 07511c3`

## Provenance

The affirmed brief is [comment 5555947422](https://github.com/Grimblaz-and-Friends/tradecraft/issues/404#issuecomment-5555947422), its affirmation record [5555947521](https://github.com/Grimblaz-and-Friends/tradecraft/issues/404#issuecomment-5555947521), and the settled pre-implementation artifact [5561412813](https://github.com/Grimblaz-and-Friends/tradecraft/issues/404#issuecomment-5561412813). One cold seat, one verdict, `would`. Two corrections were made after that verdict and bought no fresh reading, both being points the seat named itself outside its failing points: the artifact had asserted that no pointers exist to follow, where four already did, and one section said *every shipped cell* where its own criterion said every shipped cell other than the charter.

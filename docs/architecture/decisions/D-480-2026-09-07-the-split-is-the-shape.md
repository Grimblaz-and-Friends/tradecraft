# D-480: The split is the shape a cell has, and the ceiling files instead of refusing

**Status:** Accepted 2026-09-07 (PR #480)

## Context

`skills/authoring/references/cell-structure.md` has carried the right test for a long time — *a cell is too big when a session loads prose it had no use for* — and read as a move a writer may make when a body gets uncomfortable. Six cells had made it and seven had not, and two of the four largest bodies were already among the six — so the split was never a move only small cells made. Derive with `git ls-tree -r --name-only <base> | grep references/` and `lint._frontmatterless` over each `SKILL.md` at that revision.

**Prose had already been tried twice at this exact behaviour and had not held.** [#245](https://github.com/Grimblaz-and-Friends/tradecraft/issues/245) closed `COMPLETED` on the owner's own observation that agents seeing a budgeted file become afraid to edit it, and landed the reframe where writers read. [#302](https://github.com/Grimblaz-and-Friends/tradecraft/issues/302) closed `COMPLETED` having measured `engagement`'s body and produced reporting without capping. Between them the largest cell body more than doubled. Derive by measuring every `SKILL.md` body with `lint._frontmatterless` at `76b29e3`, which closed #245, and at `cc90dbc`, which closed #302, and comparing the largest at each. That history is the ground for everything mechanical here: a third change that only states the rule better fails the same way, and the guard is the one part a later session cannot quietly not do.

## Decision

**The split is stated as the shape a cell has rather than a move available under pressure**, and a body carrying one-trigger prose is unfinished whatever it measures. The disqualifier itself does not change; what changes is that it describes a state rather than an option.

**A cell with depth carries an index, and the index is the authority on what depth exists.** Inline pointers stay lawful; what they stop being is the record. `adversarial-review` had already written one by hand and it is the form the rest follow — trigger, file, précis, written for a reader deciding whether to open rather than lifted from the file's own load condition, which is written for a reader who already has.

**`check_depth_index` holds naming in both directions and not shape.** Whether the entries are collected into one table is the standard's business and a reader's judgment; whether every depth file is reachable at all is a fact, and a fact is what a guard can hold. It is the floor beneath the standard, which is how this practice already frames guards.

**The ceiling reports and never refuses.** `check_doctrine`'s `doctrine-budget` finding reddened the mandated lint and its message named shedding and routing content out. It is gone, and no cell-body size condition anywhere emits a finding or a non-zero exit. The owner's ruling is the ground: *"the standard is splitting and the ceiling directs to filing, not cutting content"*, and it *"can't be something that at all tells the agent not to add text to the skill."*

**Each ceiling is where its cell stood, measured rather than argued.** A ceiling is a record of a position, never a claim about where a body ought to be — which is [#328](https://github.com/Grimblaz-and-Friends/tradecraft/issues/328)'s question and stays open. **The first attempt at a number was unsatisfiable rather than merely wrong**: a single threshold separating cells that had shed from cells that had not required a value simultaneously above `engagement`, which has shed and is the largest body in the practice, and below the smallest cell that has not. No such number exists, and the draft had ruled out the escape by forbidding a chosen one.

**`skills/charter/SKILL.md` is deliberately absent from the map.** Its body is a term in every always-on row, so `check_always_on_budget` sizes it, and a ratified test pins it out of the body map as a smuggled second limit. That is also the standard's one stated exception. **The reason stated first was false and was corrected before landing**: shedding *does* relieve an always-on row, by exactly what moves, since the row counts the charter's `SKILL.md` body alone. What refuses the move is `check_charter_cell` — depth under the charter would be available and not binding. Stating only the cap would send a writer to a remedy that does not apply; stating the wrong reason sends them to one that does apply and is refused.

**Filing does not depend on a session choosing to file.** `tools/ceiling_filing.py` runs on push, reads `cells_over_ceiling`, and raises one pool item per cell over its ceiling under a standing cause. One item per **cell**, never per commit: the accrual counts symptoms under a cause, so a per-commit item would climb a band on one cell's growth and misreport how wide the class is.

**`skills/filing/SKILL.md` gains a carve-out, keyed to the evidence rather than to who raised it.** Its governing-prose bar asks for an incident or a run and a measurement is neither, so the charter governs: a rule conflicting with an owner decision is amended alongside the work, never blocked on. **The first wording of that carve-out scoped it to items a mechanism raised, which left this change's own landing filings failing the very bar being amended** — the same rule with two sites and an exception written at one.

**A ratchet set at landing cannot see a cell that was already large**, so the three largest cells carrying no depth at all — `filing`, `board` and `records` — are filed by this change rather than by the ceiling, that being the rule the selection follows — [#477](https://github.com/Grimblaz-and-Friends/tradecraft/issues/477), [#478](https://github.com/Grimblaz-and-Friends/tradecraft/issues/478), [#479](https://github.com/Grimblaz-and-Friends/tradecraft/issues/479) under [#476](https://github.com/Grimblaz-and-Friends/tradecraft/issues/476).

## Rejected

- **Generating the index.** The précis carries the value and a generator would have to lift it from each depth file's own load-condition line, which is written for a reader who has already opened the file. A generator producing worse prose than the hand-written exemplar is a net loss; the check is what must not be optional.
- **Leaving `CELL_BODY_BUDGET_CHARS` as a deliberate exception** beside the new mechanism. A cold seat found that this keeps a guard whose message names removal — the ruling's red line surviving inside the change meant to honour it — and that the criterion scoped to the new ceiling would have passed while the old guard still fired.
- **Recording each breach as a comment under the open cause**, which needs no amendment to the filing cell and is what that cell already permits. Rejected because accrual counts sub-issues rather than comments, so a comment-based design cannot raise the cause and the owner's stated purpose fails silently.
- **Converting the always-on row's cell-body term**, so that no cell body anywhere meets a blocking check. Put to the owner as one of two at the cold-seat cap; he ruled the other way. It reaches the surface the affirmed brief excluded, and the row measures something a split cannot reduce.
- **`1.0.0` for the version.** The bump had to pass main's 0.99.0; `0.100.0` carries no significance claim this change has not earned.

## Evidence

**Two cold-seat rounds, both `would not`, settled by the owner's ruling at the cap** — the route the `engagement` cell names, and the label says so rather than carrying the word bare. Round one landed on four points and round two on three; every point except one was repaired, and each was verified against the tree before it was acted on rather than taken from the seat.

**Three of this change's own defects were caught by this repository's guards rather than shipped.** `check_subprocess_streams` failed `tools/ceiling_filing.py` for leaving stdin unnamed on a call that redirected the other two. A `gh issue edit --add-sub-issue-of` call was written against a flag that does not exist at `gh` 2.80.0, which the `filing` cell already records and which was checked rather than assumed. And the suite caught nine fixture failures from the new guard, one of which was a ratified test refusing `charter` in the ceiling map.

**The baseline was measured twice.** Rebasing onto PR #454 moved three cell bodies after the first measurement, so four cells read as over on a ratchet that had just been set. A test pinning that this repository sits at its ceilings at landing was written and then removed: it was true of exactly one tree and false on any lawful growth, so it made a cell growing past its ceiling fail a test — the refusal the owner's ruling took out of the guard, arriving through the suite. **Nothing replaces it**, because staleness at landing and growth after it are the same observation to any later tree; what checks the baseline is the measurement the landing session runs.

**The accrual was observed rather than argued.** With three symptoms linked, `python skills/filing/scripts/pool.py show 476` reports the cause labelled `urg:1` and reading as 2 — one band, per the policy's `symptoms_per_band` of 2.

Each figure this entry rests on is derived by a command stated where it is used: `python tools/lint.py` for the always-on rows and the cell bodies, the script in [#455](https://github.com/Grimblaz-and-Friends/tradecraft/issues/455)'s body for the body-and-depth table, and `python -m pytest tools/tests skills -q` for the suite.

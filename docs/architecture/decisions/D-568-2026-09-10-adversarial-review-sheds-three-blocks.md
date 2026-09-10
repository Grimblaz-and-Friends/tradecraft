# D-568 — The `adversarial-review` cell sheds three one-trigger blocks, and D-193's judgment call is superseded

**Landed by** [PR #568](https://github.com/Grimblaz-and-Friends/tradecraft/pull/568), closing [#517](https://github.com/Grimblaz-and-Friends/tradecraft/issues/517). Brief affirmed 2026-09-09 at [issue #476 comment](https://github.com/Grimblaz-and-Friends/tradecraft/issues/476#issuecomment-5609749676), covering the whole set of nine; artifact settled at [issue #517 comment](https://github.com/Grimblaz-and-Friends/tradecraft/issues/517#issuecomment-5626999774) on one cold round, verdict `would`. **Evidence at two endpoints, and each figure says which.** What the tree held before this change is read at `686a3bc`; every figure describing the tree this change produces is derived at this branch, as `len()` over decoded UTF-8 with a cell body's frontmatter stripped the way `tools/lint.py` strips it.

## What was decided

`skills/adversarial-review/SKILL.md` at `686a3bc` was 9,871 characters of body against a ceiling of 9,855, five sections deep, with five `references/` files already beside it. Three of its blocks each serve one job among the cell's several and loaded for every session the cell fires for. Each moves whole:

- **`## Choosing the shape`** — the two lanes, what buys the panel and the fifth seat, and the line the report records — becomes `skills/adversarial-review/references/the-shape.md`.
- **Three of the eight evidence standards** — the test pin that must go red, deriving a correction from its source, and re-deriving a diagnosis against the tree a fix produces — join `skills/adversarial-review/references/after-the-fix.md` under a new heading. All three are keyed to fix time in their own words, and that file is the one their reader already opens by rule; its title and load condition widen from a batch that has landed to the writing of one, because that is when the arriving rules bind.
- **`## Closing a recurring class`** — lens promotion, and the two grounds any standing instruction to look retires on — becomes `skills/adversarial-review/references/lenses.md`.

The body keeps the purpose header, the pause discipline, the charter, the depth index and the five standards that bind every seat and every stage, and measures **8,114**. `tools/lint.py`'s ceiling for this cell rebaselines to it, as that map's own comment requires of a cell that sheds depth.

**Who was paying for the three blocks.** The cell's description declares four triggers and its purpose header names its audience, and between them they give **eight** reader populations: the session with a change ready for review, the session deciding review depth, the session dispositioning what an automated reviewer posted or a review tool returned, the session deciding whether another pass is worth running, every seat, the defense, the judge, and any session deciding what a finding met outside a review earns. The first two are one reader at one moment — the lane is chosen once, by the session that dispatches. **The other six never choose a lane, and none of them writes the fix batch either**, the batch being the dispatching session's last act. That is the disqualifier in `skills/authoring/references/cell-structure.md` applied as it is written: *a cell is too big when a session loads prose it had no use for*.

**Nothing is cut, and the claim is checked rather than asserted.** Of the non-blank lines of the pre-change body, every one appears verbatim in exactly one of the four files afterwards, with six exceptions: `L20` and `L47`, each promoted from a `##` heading to its file's `#` title; `L33`, the index entry for `after-the-fix.md`, replaced whole; and three repairs, below.

## The three repairs, and the class they belong to

**The class is a clause whose sense depended on what sat around it**, not a clause containing a particular word. Three members, and the sweep that found them was run twice — once over the body's positional vocabulary, once per moved block by reading the block itself in its new file.

- **`L28`**: *every stage above and the fix batch, once each* pointed at the stage list inside `## Choosing the shape`, which Move 1 takes out of the file. It now reads *every stage the chosen lane names*. Its second sentence, *Every stage is held to everything in this file*, is left alone and stays true of the charter and the five standards that remain.
- **`L49`** and **`L51`**: each named the evidence standards deictically — *these evidence standards*, *these standards* — from inside the file that held them, and from a sibling file the deixis resolves to nothing. Each now reads *the cell body's evidence standards*. `L51`'s *not only a lens promoted above* is deliberately **not** repaired: the paragraph it points at moves with it and stays above it.

**The first sweep's pattern set under-covered the class**, and the cold seat that settled the artifact caught it: the grep quoted in the artifact — `above`, `below`, `earlier`, `this file`, `these standards`, `this skill` — does not match `L49`'s *these evidence standards*. `L49` was caught by the second sweep instead, which is why the build is unaffected, and the miss is recorded because the narrow-pattern reading is [the same failure D-561 recorded on this programme's third cell](D-561-2026-09-10-records-sheds-three-sections.md) — *the class is a clause that depended on where it sat, not a clause containing the word* below. A pattern is a way of finding candidates; it is not the definition of the class.

## D-193 is superseded, and the grounds are recorded

[D-193](D-193-2026-08-25-review-cell-splits-at-the-reader.md) is the entry that split this cell, and it decided Move 1 the other way. Its Decision section: *"`Choosing the shape` stays in the body although a prosecution seat has no use for it: it is one of the cell's three declared triggers, and a session firing for deciding review depth alone should get its answer without a second hop. The disqualifier is a test about waste, not a rule to run to its limit."* Its Rejected list carries *"Moving `Choosing the shape` out of the body — maximal shedding by the letter of the disqualifier; it costs a whole declared trigger a second hop."* It was read in full before this change was designed, and it is superseded knowingly on three grounds, none of which was available to it:

- **The cell declares four triggers now, not three.** D-193's own asymmetry already put one of them — deciding whether another pass runs — a hop away, arguing that a body copy would buy half an answer where the hop buys all of it. `Choosing the shape` moves **whole**, so the hop buys all of it here too, and a declared trigger answered one hop away is this cell's established shape rather than a novelty.
- **[D-371](D-371-2026-09-04-the-review-runs-once.md) re-examined the same question on 2026-09-04 and recorded the opposite reading.** Its outflow search *"found two shed candidates in existing sections, `Choosing the shape` and `Closing a recurring class`, both of which pass the disqualifier and either of which would have fitted this addition"*, and it declined to act only because the restructuring lay outside that change's affirmed boundary. This change is that restructuring.
- **The affirmed brief is the term this change is held to**, and it states the test without D-193's softening: *"a main file holds what every firing needs, side files hold what one job needs."* `Choosing the shape` is not what every firing needs.

**What D-193 was protecting is real and is what this costs:** the session choosing a lane now takes a hop it did not take. What it was charging for that protection is the block's characters in every load by the six populations that never choose one.

## Two blocks a maximal read would also take, and why they stay

Recorded so a later session finishing this split does not read them as paragraphs somebody missed.

- **The charter's third bullet** — *The terminal ruling is about the artifact, not the finding count* — serves the terminal stage alone on a strict reading, and `skills/adversarial-review/references/arbitration.md` is where that stage's machinery lives. It stays because the charter section is the frame every prosecuting stage reads before it writes a finding, and the bullet is what tells a seat that its finding count is not the review's verdict. **What would change the call:** the ruling vocabulary growing past one bullet, or `arbitration.md` acquiring a statement of the three rulings that this one would then duplicate.
- **The preamble's pause discipline** is read by the dispatching session and constrains every seat. It is not one-trigger prose; it is the rule that a seat dispatched mid-run does not stop to ask.

## Sites

`skills/adversarial-review/SKILL.md` (three blocks out, two index entries in, one amended, one clause repaired); the two new files `skills/adversarial-review/references/the-shape.md` and `skills/adversarial-review/references/lenses.md`; `skills/adversarial-review/references/after-the-fix.md` (title, load condition, and the new `## While the fixes are written` section); `tools/lint.py` (this cell's row of `CELL_BODY_CEILING_CHARS`); `.claude-plugin/plugin.json` (0.111.0 → 0.112.0, the shipped zone being touched).

## What was rejected

**Splitting the evidence standards into a file of their own.** They are what the section's heading claims — every seat, every stage — and a body that shed them would route every firing through a file open to learn the rules that govern all of them.

**A file of the cell's own for the three fix-time standards, sitting beside `after-the-fix.md` rather than inside it.** It would give the fix batch's reader two files to open where the tree already has one whose load condition reaches them. What it would have avoided is widening `after-the-fix.md`'s title and load condition, which is a smaller cost than a second hop for one reader.

**Splitting the lens material between `roster.md` and `arbitration.md`** — promotion where seat briefs are written, retirement where a stage rules one. The affirmed brief says what moves is moved whole, and two half-files is how one rule becomes two that drift.

**Repairing the artifact's four imprecise supporting clauses.** The cold seat returned `would` and reported all four as observations. Editing a settled artifact makes it a draft again under the `engagement` cell's narrowing, and each of the four cuts in favour of the call it bears on. They are recorded on the pull request and in this entry instead.

## Cost

**The body shed 1,757 characters and the cell as a whole gained 1,282.** Decoded UTF-8 characters, which is what `tools/lint.py` measures: the body 9,871 → 8,114, against two new files, two new index entries, one amended index entry, one new section heading and the three repairs. **The growth is the point rather than a cost overrun.** A cell body is charged to every firing of the cell and its depth to none, so 1,282 characters added off the body buys 1,757 that six of the cell's eight reader populations no longer pay.

**The body renumbers from 51 lines to 38.** `docs/recorded-findings.jsonl` carries 48 entries whose `artifact` names this cell, and the three `skills/adversarial-review/SKILL.md:<line>` citations among them now resolve to different text — two of them, both `:41`, past the file's end. Nothing maintains that record, so this is stated rather than repaired; what keeps those entries findable is that `artifact` names the cell, which is the durable subject whichever of its files holds the sentence. **This is the second cell in the [#476](https://github.com/Grimblaz-and-Friends/tradecraft/issues/476) programme to strand entries that way** and the ruling recorded in [D-561](D-561-2026-09-10-records-sheds-three-sections.md) governs it: a split that moves prose inside a cell's own `references/` does not trigger the decision log's mover-pays repoint permission, the owner having ruled that on 2026-09-10.

## What this change did not settle

**Whether this body should be smaller still** is not asked here. The ceiling this change writes is where the body now stands, which is a measurement and not a claim about what it ought to be — [#328](https://github.com/Grimblaz-and-Friends/tradecraft/issues/328)'s question, still open.

**Whether a cold-seat dispatch may carry the artifact by path and digest rather than inline** is not settled here either. This dispatch did, for the second consecutive change in this programme, and reported it as a call; that is an incident an amendment to the `engagement` cell could rest on, and it is left where a later session can reach it rather than acted on inside a change whose brief is about cell structure.

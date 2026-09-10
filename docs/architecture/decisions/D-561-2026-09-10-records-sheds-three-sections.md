# D-561 — The `records` cell sheds three sections, and keeps the one the disqualifier reaches

**Landed by** [PR #561](https://github.com/Grimblaz-and-Friends/tradecraft/pull/561), closing [#479](https://github.com/Grimblaz-and-Friends/tradecraft/issues/479). Brief affirmed 2026-09-09 at [issue #476 comment](https://github.com/Grimblaz-and-Friends/tradecraft/issues/476#issuecomment-5609749676), covering the whole set of nine; artifact settled at [issue #479 comment](https://github.com/Grimblaz-and-Friends/tradecraft/issues/479#issuecomment-5613615372). Evidence pinned at `6c2125a` unless stated.

## What was decided

`docs/cells/records/SKILL.md` at `6c2125a` was one file of 8,820 characters below its frontmatter with no depth at all, and the cell's description names five triggers. Three of its five sections each serve one of those triggers and nothing else, so a session firing the cell for any other reason loaded them: `## Review, here` at 4,212 characters, `## How a brief reached settled` at 1,818, and `## Admissions, at a ceiling` at 1,546. Each becomes one file under `docs/cells/records/references/`, and the body keeps the purpose header, a three-entry depth index, and the two sections every firing needs. **2,347 characters**, and `tools/lint.py`'s ceiling for this body is rebaselined to it, as that map's own comment requires of a cell that sheds depth.

**Nothing is cut, and the claim is checked rather than asserted.** Of the 26 non-blank lines below the frontmatter at `6c2125a`, 21 appear verbatim exactly once across the four post-change files. The five that do not are the three headings that became file titles and two sentences repaired for position — each a clause that said *below* about a section now in a sibling file, repaired to name the body it now points into rather than a direction.

**`## Decisions` stays in the body, and that is this change's one judgment call.** The disqualifier in `skills/authoring/references/cell-structure.md` — *a cell is too big when a session loads prose it had no use for* — reaches part of it: its locator and its `[D-N]` marker serve *writing or citing a decision entry* alone. It stays for three reasons that are recorded here so a later session finishing the split does not read it as a paragraph somebody missed.

- **The arithmetic runs the wrong way.** The section is 306 characters. An index entry written the way the other three are — naming the path, the freeze and the citation marker, so a reader can decide whether to open it — costs about as much. Moving it would relieve a reader who does not need it by roughly nothing and cost a reader who does a file open, which is the disqualifier's own measure made worse in both directions. The estimate was put at *roughly 250* in the artifact and is low: the shortest of the three entries this change writes is 287 characters, which strengthens the case rather than weakening it.
- **It is not purely one-trigger prose.** Its freeze clause — *frozen on landing but for the two narrow repairs bounded in the log's README* — is what the description's fifth trigger reaches for, a session tempted to correct something already recorded being sent here for the one record whose freeze has named exceptions.
- **A live pointer lands on it.** `docs/cells/siting/SKILL.md:17` sends a reader for where a decision entry lives and under what freeze; after the split that is the first thing they meet.

**What would change the call:** the section growing to where an index entry is materially cheaper than it, or a second trigger's worth of decision-log material arriving beside it. Either makes a fourth depth file the right shape.

**Sites.** `docs/cells/records/SKILL.md` (the three sections out, the depth index in); the three new files under `docs/cells/records/references/`; `tools/lint.py` (the `records` row of `CELL_BODY_CEILING_CHARS`, and the `_check_cost` docstring, which named the body as where the cost exclusions bind and now names the depth file that carries them).

## What was rejected

**Splitting `## Records are exhaust` out with the others.** It binds any append whatever the trigger, and it is the general answer to the *tempted to correct* trigger. A body that shed it would route every firing through a file open to learn the one rule that governs all of them.

**Subdividing `docs/cells/records/references/what-a-review-records.md`.** At 4,366 characters it is much the largest of the three, but nothing in it serves fewer triggers than the file as a whole: `cost` and `target` are both read while recording one review's outcome.

**Giving the new depth files a ceiling of their own.** The lint prices a cell's `SKILL.md` and not its depth, so a cell can shed its way under a constant without shedding anything a reader loads. That asymmetry is [#457](https://github.com/Grimblaz-and-Friends/tradecraft/issues/457)'s subject and is deliberately not resolved here — this change would otherwise be deciding the ceiling mechanism, which the affirmed brief puts out of scope.

**Repairing the two wordings the second cold seat named.** It returned `would` and reported both as observations: the artifact says three headings were *promoted* where two were promoted and one replaced, and the *roughly 250* estimate above sits below the real shortest entry. Both cut in favour of the calls they bear on, and editing a settled artifact makes it a draft again under the `engagement` cell's narrowing. They are recorded on the pull request instead.

## Cost

**The body shed 6,473 characters and the cell as a whole gained 1,546.** Decoded UTF-8 characters, which is what `tools/lint.py` measures: the body 8,820 → 2,347, against 8,019 characters across the three new files, whose sum against the three sections that moved is the three titles, the three load conditions and the two repaired clauses. The depth index accounts for most of the body's remainder. `tools/lint.py` grew 27 characters, all of it the rebaselined constant and the repointed docstring.

**The growth is the point rather than a cost overrun.** A cell body is charged to every firing of the cell and its depth to none, so 1,546 characters added off the body buys 6,473 characters no session pays unless its trigger is the one that needs them.

## What this change did not settle

**Whether the `records` body should be smaller still** is not asked here. The ceiling this change writes is where the body now stands, which is a measurement and not a claim about what it ought to be — [#328](https://github.com/Grimblaz-and-Friends/tradecraft/issues/328)'s question, still open.

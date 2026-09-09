# D-544: A cell body's ceiling reports into the refresh note, and the merge job that filed from it is retired

**Status:** Accepted 2026-09-09 (PR #544)

## Context

[D-480](D-480-2026-09-07-the-split-is-the-shape.md) landed a ratchet on every cell body and a merge-time job to act on it: `tools/ceiling_filing.py` at `69ba49f` ran on every push to `main`, read `lint.cells_over_ceiling`, and created one pool item per cell over its ceiling under a standing cause, [#476](https://github.com/Grimblaz-and-Friends/tradecraft/issues/476). Its own docstring stated the dedupe that was meant to bound it — *"One item per cell, never one per commit."*

**It was bounded per cell and the pool still filled, because the population is cells and cells keep growing.** Eight of #476's open symptoms are that job's output or the landing filings that seeded it: [#477](https://github.com/Grimblaz-and-Friends/tradecraft/issues/477), [#478](https://github.com/Grimblaz-and-Friends/tradecraft/issues/478), [#479](https://github.com/Grimblaz-and-Friends/tradecraft/issues/479) from D-480's own landing, and [#514](https://github.com/Grimblaz-and-Friends/tradecraft/issues/514), [#515](https://github.com/Grimblaz-and-Friends/tradecraft/issues/515), [#517](https://github.com/Grimblaz-and-Friends/tradecraft/issues/517), [#518](https://github.com/Grimblaz-and-Friends/tradecraft/issues/518), [#519](https://github.com/Grimblaz-and-Friends/tradecraft/issues/519) in one run on 2026-09-08. Each says the same sentence about a different cell, and #476 was already framed and on the board — so none of them decided anything the cause had not already decided. Derive the class with `gh issue list --repo Grimblaz-and-Friends/tradecraft --search "ceiling-item:" --state open`, which reads the marker the script wrote into every body it created.

The owner asked on 2026-09-07 whether the ceilings were set right; a recommendation to move the measurement into the board's refresh note was put then, unruled, and put again on 2026-09-09. He affirmed the brief on [#543](https://github.com/Grimblaz-and-Friends/tradecraft/issues/543) that day.

## Decision

**The measurement is a reading, and it goes where this repository's readings go.** `python tools/lint.py` gains `over_ceiling_note`, one pasteable line built from `cells_over_ceiling`, and `docs/cells/board/SKILL.md` makes the refresh note carry it beside the charter's reach line, which [D-522](D-522-2026-09-08-the-refresh-owns-the-cycle.md) put there for the same reason.

**Ordered by overshoot rather than by body size**, and the two are pulled apart in the fixture so a size-ordered implementation reds rather than passing by coincidence. The block above it is already ordered by size; what this line adds is the subset a reader is being asked to act on. `none` is written in words, because *nothing is over* and *the derivation broke* are states a reader must tell apart and an absent line says neither.

**The job, the script, its test and the guard that held it wired are deleted.** `check_ceiling_filing_job` existed because a pull request removing the job touched no cell and no doctrine file, so nothing went red. That reasoning was sound for a mechanism meant to stay; it is not a reason to keep one the owner has retired.

**This amends the first half of the owner's [#455](https://github.com/Grimblaz-and-Friends/tradecraft/issues/455) ruling and supersedes D-480 on that point alone.** D-480 recorded *"Filing does not depend on a session choosing to file"* and built the job to guarantee it. What survives is his second half — that a ceiling may not tell a session not to add text — and nothing here refuses, trims, or holds back an addition. **This change is its own exhibit for that half**: its prose put `authoring`, `records` and `siting` over ceilings they had been sitting exactly on, and nothing refused it, asked it to trim, or filed about it. D-480's other decisions — the split as a cell's shape, the depth index, the ceiling as a measured position, the charter's absence from the map — are untouched.

**Five sentences stop saying a passed ceiling raises a work item and say it is reported**: `skills/authoring/SKILL.md`, `skills/authoring/references/cell-structure.md`, `skills/filing/SKILL.md`, and the repo-only `docs/cells/records/SKILL.md` and `docs/cells/siting/SKILL.md`. **The `filing` cell's measurement-alone carve-out stays.** Its warrant changes — a ceiling no longer directs to filing — but a session that reads the measurement and judges the growth worth acting on still has no incident to attach, which is the whole of what the carve-out is for.

**Check 8 of `tools/lint.py`'s numbered list is retired in place rather than renumbered.** Those numbers are cited from `tools/lint.py` itself, from `tools/roster.py`, from `tools/check_ask_declaration.py`, from `tools/tests/test_lint.py`, and from [D-232](D-232-2026-08-29-subprocess-stdin-and-the-roster-comparison.md), which names *lint check 19* and is frozen with no lawful repair for a number a later tree shifted. Closing the gap repoints every one of those silently. The docstring test was split to hold the two things worth holding — that the sequence has no hole, and that every check `run` calls is enumerated — and both arms were run against a deliberately broken tree before being kept.

**Five references in four frozen entries take the `UNREPAIRABLE_AFTER_LANDING` route**, the log's README naming it for a target retired rather than moved. Each characterises the deleted script rather than merely locating it, so none survives a repoint, and each row states its own reason.

## Rejected

- **Keeping the job and widening its dedupe** — one item per cell per quarter, or per N characters of growth. It prices the noise rather than removing it, and the noise was never the rate: an item that repeats a measurement is one the assessment cycle must still answer whenever it arrives.
- **Recording each breach as a comment on the standing cause** instead of the refresh note. D-480 rejected this because accrual counts sub-issues rather than comments; the objection survives, and a comment stream on a cause nobody is reading is a worse home than a note somebody reads at every refresh.
- **Renumbering the lint's check list to close the gap at 8.** Rejected on the frozen citation above. The cost of the gap is one paragraph of explanation in a docstring; the cost of closing it is a decision entry nobody may correct becoming quietly false.
- **Deleting `cells_over_ceiling` along with its only caller.** The brief keeps the lines where the measurement is taken, and the note needs a derivation; the function is what the new line reads.
- **Moving the ratchet constants beside a policy file.** Deferred by the brief, which keeps them in `tools/lint.py`.
- **Deciding which cells split.** That is #476's, and whether a ceiling's number is right at all is [#328](https://github.com/Grimblaz-and-Friends/tradecraft/issues/328), still open.

## Evidence

**One cold-seat round, verdict `would`**, settling the artifact on the first. The seat reported five observations it did not fail the artifact on. Four were confirmed against the tree and taken into the build — a fifth prose site the artifact's enumeration had missed, `docs/cells/siting/SKILL.md`; `cells_over_ceiling`'s own docstring, which named the caller being deleted; two shared test fixtures wiring the job for the *callout* tests; and the fact that the comment block above the job in `ci.yml` was two blocks, only one of them the ratchet's. One was checked and rejected: it placed D-232's citation at line 57, where `grep -n "lint check 19"` returns 58.

**The artifact's own account of how it found the sites was wrong, and is retracted on the issue.** It credited a grep that does not reach `skills/authoring/references/cell-structure.md` and does reach `docs/cells/siting/SKILL.md`, which the enumeration then omitted. The correction is a reading amendment, posted as a further comment rather than an edit, and it is what the build followed.

**The lint found a consequence neither the artifact nor the seat had reached** — the five stranded references above. Nothing in the change's own reasoning would have caught them; running the mandated command before committing did.

Each figure here is derived by a command stated where it is used: `python tools/lint.py` for the ceilings and the always-on rows, `python -m pytest tools/tests skills -q` for the suite, and `python tools/check_version_bump.py --base origin/main` for the version.

# D-544: A cell body's ceiling reports into the refresh note, and the merge job that filed from it is retired

**Status:** Accepted 2026-09-09 (PR #544)

## Context

[D-480](D-480-2026-09-07-the-split-is-the-shape.md) landed a ratchet on every cell body and a merge-time job to act on it: `tools/ceiling_filing.py` at `69ba49f` ran on every push to `main`, read `lint.cells_over_ceiling`, and created one pool item per cell over its ceiling under a standing cause, [#476](https://github.com/Grimblaz-and-Friends/tradecraft/issues/476). Its own docstring stated the dedupe that was meant to bound it — *"One item per cell, never one per commit."*

**It was bounded per cell and the pool still filled, because the population is cells and cells keep growing.** Eight of #476's open symptoms are that job's output or the landing filings that seeded it: [#477](https://github.com/Grimblaz-and-Friends/tradecraft/issues/477), [#478](https://github.com/Grimblaz-and-Friends/tradecraft/issues/478), [#479](https://github.com/Grimblaz-and-Friends/tradecraft/issues/479) from D-480's own landing, and [#514](https://github.com/Grimblaz-and-Friends/tradecraft/issues/514), [#515](https://github.com/Grimblaz-and-Friends/tradecraft/issues/515), [#517](https://github.com/Grimblaz-and-Friends/tradecraft/issues/517), [#518](https://github.com/Grimblaz-and-Friends/tradecraft/issues/518), [#519](https://github.com/Grimblaz-and-Friends/tradecraft/issues/519) across **two** runs on 2026-09-08, at `02:17` and `02:37`, twenty minutes and one merge apart. Each says the same sentence about a different cell, and #476 was already framed and on the board — so none of them decided anything the cause had not already decided. Derive the class by reading the marker out of the bodies, which is what identifies it:

```
gh issue list --repo Grimblaz-and-Friends/tradecraft --state open --limit 200 \
  --json number,body --jq '[.[]|select(.body|contains("ceiling-item:"))|.number]'
```

**Not by search.** `--search "ceiling-item:"` returns 18 open issues, GitHub tokenising the marker rather than matching it literally; an earlier draft of this entry offered that command and it does not derive the class it was offered for. The `--limit` is not decoration: the default is 30 against an open set already past it.

The owner asked on 2026-09-07 whether the ceilings were set right; a recommendation to move the measurement into the board's refresh note was put then, unruled, and put again on 2026-09-09. He affirmed the brief on [#543](https://github.com/Grimblaz-and-Friends/tradecraft/issues/543) that day.

## Decision

**The measurement is a reading, and it goes where this repository's readings go.** `python tools/lint.py` gains `over_ceiling_note`, one pasteable line built from `cells_over_ceiling`, and `docs/cells/board/SKILL.md` makes the refresh note carry it beside the charter's reach line, which [D-522](D-522-2026-09-08-the-refresh-owns-the-cycle.md) put there for the same reason.

**Ordered by overshoot rather than by body size**, and the two are pulled apart in the fixture so a size-ordered implementation reds rather than passing by coincidence. The block above it is already ordered by size; what this line adds is the subset a reader is being asked to act on. `none` is written in words, because *nothing is over* and *the derivation broke* are states a reader must tell apart and an absent line says neither.

**The job, the script, its test and the guard that held it wired are deleted.** `check_ceiling_filing_job` existed because a pull request removing the job touched no cell and no doctrine file, so nothing went red. That reasoning was sound for a mechanism meant to stay; it is not a reason to keep one the owner has retired.

**This amends the first half of the owner's [#455](https://github.com/Grimblaz-and-Friends/tradecraft/issues/455) ruling and supersedes D-480 on that point alone.** D-480 recorded *"Filing does not depend on a session choosing to file"* and built the job to guarantee it. What survives is his second half — that a ceiling may not tell a session not to add text — and nothing here refuses, trims, or holds back an addition. **This change is its own exhibit for that half**: its prose put `authoring`, `records` and `siting` over ceilings they had been sitting exactly on, and nothing refused it, asked it to trim, or filed about it. D-480's other decisions — the split as a cell's shape, the depth index, the ceiling as a measured position, the charter's absence from the map — are untouched.

**Five sentences stop saying a passed ceiling raises a work item and say it is reported**: `skills/authoring/SKILL.md`, `skills/authoring/references/cell-structure.md`, `skills/filing/SKILL.md`, and the repo-only `docs/cells/records/SKILL.md` and `docs/cells/siting/SKILL.md`. **The `filing` cell's measurement-alone carve-out stays.** Its warrant changes — a ceiling no longer directs to filing — but a session that reads the measurement and judges the growth worth acting on still has no incident to attach, which is the whole of what the carve-out is for.

**Check 8 of `tools/lint.py`'s numbered list is retired in place rather than renumbered**, because those numbers are how this file's checks are cited — from the file itself, from `tools/roster.py`, and from the decision log — and closing the gap repoints every citation **above** 8 while leaving those at or below it alone, silently in both cases.

**The exhibit an earlier draft of this entry gave for that call was false, and the correction is the point.** It said [D-232](D-232-2026-08-29-subprocess-stdin-and-the-roster-comparison.md) names *lint check 19* and that renumbering would break it. D-232's citation names docstring item **21**, and has since two insertions that predate this change — so it was already broken, and the gap protects nothing about it. The check actually run to verify it was `grep -n "lint check 19"`, which confirms where the string sits and not what the number refers to; that is the defect, and it survived a cold seat's specific challenge to the same citation. What the call rests on now is only the first paragraph: the scheme is the citation scheme, sound or not, and renumbering underneath it is a separate act from repairing it. [#551](https://github.com/Grimblaz-and-Friends/tradecraft/issues/551) carries what is wrong with the scheme, including D-232's own broken citation.

**The gap is held by a guard rather than by this paragraph.** `test_the_module_docstring_enumerates_every_check_run_calls` pins slot 8 by number. Without that pin — as this change first shipped it — deleting the slot and renumbering leaves the sequence hole-free and the live count right, so both of its assertions pass, the suite passes and the lint is green; three stages of this change's review probed exactly that. **The entry also claimed the split test holds "every check `run` calls is enumerated"; it holds a count**, so a renamed descriptor passes it. That claim is withdrawn.

**Five references in three frozen entries take the `UNREPAIRABLE_AFTER_LANDING` route** — D-480 twice, D-491, D-496 twice — the log's README naming it for a target retired rather than moved. Each characterises the deleted script rather than merely locating it, so none survives a repoint, and each row states its own reason. An earlier draft said *four entries*; it was five references and three files.

## Rejected

- **Keeping the job and widening its dedupe** — one item per cell per quarter, or per N characters of growth. It prices the noise rather than removing it, and the noise was never the rate: an item that repeats a measurement is one the assessment cycle must still answer whenever it arrives.
- **Recording each breach as a comment on the standing cause** instead of the refresh note. D-480 rejected this because accrual counts sub-issues rather than comments; the objection survives, and a comment stream on a cause nobody is reading is a worse home than a note somebody reads at every refresh.
- **Renumbering the lint's check list to close the gap at 8.** Rejected on the frozen citation above. The cost of the gap is one paragraph of explanation in a docstring; the cost of closing it is a decision entry nobody may correct becoming quietly false.
- **Deleting `cells_over_ceiling` along with its only caller.** The brief keeps the lines where the measurement is taken, and the note needs a derivation; the function is what the new line reads.
- **Moving the ratchet constants beside a policy file.** Deferred by the brief, which keeps them in `tools/lint.py`.
- **Deciding which cells split.** That is #476's, and whether a ceiling's number is right at all is [#328](https://github.com/Grimblaz-and-Friends/tradecraft/issues/328), still open.

## The argument this change inherits and does not answer

The `ci.yml` block this change deletes stated the case against it outright: *"Two closed issues -- #245 and #302 -- tried to get this behaviour by writing the rule down better, which is why it is a step that runs rather than an instruction a session may quietly not follow."* What replaces the step **is** an instruction a session may quietly not follow — a bullet in the board cell's note-owes list.

This entry does not claim to have answered that, and the honest state of the evidence cuts both ways. Against: [#511](https://github.com/Grimblaz-and-Friends/tradecraft/issues/511) measured the nearest twin on that same list, `pool_rot`, named in 0 of 35 notes with three postdating the commit that imposed it. For: the reach line, which took this exact placement one commit earlier in [PR #522](https://github.com/Grimblaz-and-Friends/tradecraft/pull/522), *was* performed on the very next note — two of this change's review seats found that independently and reported it against their own findings.

The difference between the two cases is that the owner ruled the filing itself was the problem, so the step that ran is not available as the remedy here. What is available, and is not taken in this change, is a check that the obligation leaves a trace. That is #511's, and it re-arms at the first refresh after this merges.

## Evidence

**One cold-seat round, verdict `would`**, settling the artifact on the first. The seat reported five observations it did not fail the artifact on. Four were confirmed against the tree and taken into the build — a fifth prose site the artifact's enumeration had missed, `docs/cells/siting/SKILL.md`; `cells_over_ceiling`'s own docstring, which named the caller being deleted; two shared test fixtures wiring the job for the *callout* tests; and the fact that the comment block above the job in `ci.yml` was two blocks, only one of them the ratchet's. One was checked and rejected: it placed D-232's citation at line 57, where `grep -n "lint check 19"` returns 58.

**The artifact's own account of how it found the sites was wrong, and is retracted on the issue.** It credited a grep that does not reach `skills/authoring/references/cell-structure.md` and does reach `docs/cells/siting/SKILL.md`, which the enumeration then omitted. The correction is a reading amendment, posted as a further comment rather than an edit, and it is what the build followed.

**The lint found a consequence neither the artifact nor the seat had reached** — the five stranded references above. Nothing in the change's own reasoning would have caught them; running the mandated command before committing did.

**The review's fix batch corrected eight claims in this entry and one shipped sentence, and they are named rather than quietly replaced.** A five-seat panel returned 64 raw findings, 35 distinct; the defense sustained 25, and the terminal stage ruled *fit once the named fixes land*. What was wrong here: the retired slot's exhibit (above); *four frozen entries* for three; *in one run* for two; a derivation command that returns 18 rather than the class of 8; a claim that the split test holds names when it holds a count; five repair rows crediting *PR #543*, which is an issue, the pull request being #544; and a claim that every figure here is derived by a command stated where it is used, which was false of this entry's own figures and is withdrawn — the commands below derive what the pull request body states, and this entry's counts are derived where each is used.

**One shipped sentence was false and is the most consequential thing the review found.** `skills/authoring/references/cell-structure.md` warranted the whole design to adopters with *"every fix batch grows a body or two, so a mechanism filing on the measurement files the same sentence about the same cells at every merge."* The job was live across **eight** merges to `main` (`git log --first-parent f5631de..69ba49f`) and filed on **two**; its per-cell dedupe held the rest. The correct account is this entry's own — the population is cells, and cells keep growing — and that is what the sentence now carries.

**The affirmed brief carries the same premise** (*"every merge creates a few issues"*) and is **not** edited. It is a posted record and this repository never maintains a record after its append; and under the `engagement` cell the clause is a describing one, which yields to its subject, so the defect is found in this review rather than in the brief. The brief's term is untouched by it: the reading belongs in the note whether the old job filed at eight merges or two. The lesson is that cell's own — *"A premise that could make the brief wrong is tested before it locks, not after"* — and the instrument for it, a spike, was not run.

**Acceptance criterion 3's literal falsifier fires and its substance holds.** `git grep -n "ceiling_filing"` returns five hits in live code — the repair rows this change itself added — plus `docs/reviews.jsonl`, and `ci.yml` declares `issues: write` on `doctrine-callout`, as it did at the base. No job that can create an issue runs on `push`: `doctrine-callout` is gated `if: github.event_name == 'pull_request'`. The criterion was written against a tree that never satisfied it.

**Two guards were added because the review probed their absence.** The line the refresh note copies is now pinned at the mandated command, and the retired slot is pinned by number — before the batch, deleting either left the suite and the lint green. [#551](https://github.com/Grimblaz-and-Friends/tradecraft/issues/551) and [#552](https://github.com/Grimblaz-and-Friends/tradecraft/issues/552) carry the two classes those instances belong to.

**The first experience session ran against `930e5df`, not the head**, which its note claimed; the correction is appended to the note. The bullet text is byte-identical at both, the eight-character difference being this entry's own citation, so what its consumer read is the shipped sentence.

The figures the pull request body states are derived by: `python tools/lint.py` for the ceilings and the always-on rows, `python -m pytest tools/tests skills -q` for the suite, and `python tools/check_version_bump.py --base origin/main` for the version.

# D-654: Every change is proven by running it for a three-week window — the floor, every connected reviewer once, and one use — with no panel, and the retired machinery deleted rather than switched off

**Status:** Accepted 2026-09-18 (PR #654)

## Context

The review pipeline finds true things about prose that almost never change what a session does, and the machinery built to manage its findings had become most of what this repository works on. The evidence is on [#652](https://github.com/Grimblaz-and-Friends/tradecraft/issues/652) with its derivations: 135 reviews in a month at a median 1,218,699 subagent tokens; 347 sustained highs, of which the only behavioural measure on the record — #138 spike 1, cited on #360 — puts roughly 2 of about 50 as having changed a cold consumer's behaviour; 380 findings judged real but not worth fixing, 212 of them against governing prose; one routine-lane change carrying 21,275 words across seven comments; a hearing that closed 108 pool items in five and a half minutes, essentially all as not planned; and 80 of 134 decision entries about review, filing, board or record machinery rather than about the practice's content.

The owner's direction of 2026-09-18 was to test all three connected reviewers together *in place of* the existing review structure. The implementation brief was designed in turns and affirmed whole that day; it governs this change and is quoted at the head of the settled pre-implementation artifact.

**Why a window rather than a repeal.** "In place of" is what isolates the variable. Three weeks of running with no panel produces a numerator — use-found defects against shipped cells per week, before and after — that argument alone cannot. The trial's own close-out, [#360](https://github.com/Grimblaz-and-Friends/tradecraft/issues/360), folds into the same window and is read on the same numerator rather than being discharged separately.

**What weighed against it, recorded because the window may vindicate it.** The cold read on always-on prose has demonstrated wins, and for three weeks the only guard on the charter is the doctrine callout, three reviewers and use. The callout does not reach a shipped cell's body or its `references/` files — that is a deliberate ruling recorded in `tools/doctrine_callout.py`, not an omission, and [#420](https://github.com/Grimblaz-and-Friends/tradecraft/issues/420) is the permanent fix — so for the window a binding rule can move in shipped depth with neither an owner flag nor a panel, which is where most of this change's own editing happened. The owner ruled on 2026-09-19 to proceed as affirmed, on the ground that adding a guard mid-window would confound exactly what the window measures and that merging is his own backstop. Two alternatives were argued and declined: extending the callout to shipped bodies for the window, and buying a panel for shipped cell bodies.

## Decision

The affirmed brief's seven rows land as affirmed. The default instruments become the executable floor, every connected reviewer once per pull request, and one experience session — no panel, defense, judge, review row or findings append. A panel is **bought by asking** on a pull request rather than owed. A pull request opens as a draft and is marked ready only once the floor and the experience session have run, because "ready" is the reviewers' trigger and so must mean proven. An unfixed finding takes one of exactly three ends — its own pull request now, the board as decided work or as a follow-up that states its fix, or the report's ask to the owner once — and there is no pool.

### The retired paths, and the one-command restore

Row 5 retires by deletion rather than by switching off, because switched-off code is still measured, tested, swept and reviewed, and git is the archive. **Every path below last stood at `a04e641`**, and `git restore --source=a04e641 -- <path>` brings any of them back into the working tree — one command over as many paths as you name. `git show a04e641:<path>` prints the blob and restores nothing, which is the check that was run against every path here, not the restore. The restore itself was run against `skills/filing/scripts/pool.py` at `a04e641` and returned it at the 44,903 bytes this table gives.

| retired path, with the commit it last stood at | bytes |
| --- | --- |
| `skills/filing/scripts/pool.py` at `a04e641` | 44,903 |
| `skills/filing/tests/test_pool.py` at `a04e641` | 44,644 |
| `skills/adversarial-review/scripts/external_pass.py` at `a04e641` | 17,247 |
| `skills/adversarial-review/tests/test_external_pass.py` at `a04e641` | 16,207 |
| `tools/pool_rot.py` at `a04e641` | 12,614 |
| `tools/tests/test_pool_rot.py` at `a04e641` | 8,985 |
| `skills/filing/tests/test_fade.py` at `a04e641` | 7,336 |
| `docs/cells/records/references/what-a-review-records.md` at `a04e641` | 4,028 |
| `skills/filing/references/pitch-template.md` at `a04e641` | 2,210 |
| `skills/filing/scripts/pool-policy.json` at `a04e641` | 1,834 |
| `skills/filing/references/the-pool.md` at `a04e641` | 1,504 |
| `skills/adversarial-review/references/index-row-template.md` at `a04e641` | 1,520 |

`skills/filing/references/pitch-template.md` at `a04e641` is retired into `skills/filing/references/issue-template.md` rather than simply deleted; git records it as a delete and an add, so it appears in both this table and the added set.

**Lint check 13 is retired as a numbered slot**, exactly as slot 8 already was, rather than renumbered. The numbers are how checks are cited from `tools/lint.py`, from `tools/roster.py` and from the decision log, and renumbering silently repoints every citation above the gap.

**Deleting the retired paths stranded nineteen references inside frozen decision entries.** Those entries may not be edited, so the nineteen take the disposition their own guard prescribes: `UNREPAIRABLE_AFTER_LANDING` in `tools/lint.py`, with a reason each. That mechanism predates this change and its guard message names it as the remedy.

### The meaning changes this change makes to governing prose

`revising.md` obliges every meaning change to be named where amendments are recorded. These are they.

- **"A review" stops meaning something a change owes and starts meaning something the owner buys.** The `adversarial-review` cell keeps its name, its lanes and its charter; what changes is that none of it runs unless asked for on a pull request. Sentences elsewhere that read as though a review runs by default are restated rather than left verbatim under a redefined term.
- **"Ready for merge" no longer includes a completed review or reconciled external comments.** `skills/engagement/SKILL.md`'s definition is restated against the instruments row 1 makes default.
- **The report's sources are split.** `the-stretch.md` gated the report on a terminal ruling and a fix batch among others; those become sources only where a panel was bought or those stages actually ran, while the floor, any experience session and the in-thread reviewer dispositions are the default sources.
- **An external reviewer's comment is disposed of by the builder in the thread, not ruled independently.** `arbitration.md`'s requirement of a ruling independent of the builder retires with the recording apparatus. The charter's `Outside a review, a decline is recorded on the work itself` is unedited and still satisfied: the pull request is the work and its thread is the record.
- **The one-line reply carries a disposition word** — `fixed`, `fixed — nothing else found it`, `duplicate of <the earlier comment>`, or `lapsed — <the rule we do not run>` — and a fix that needs no reply still gets a one-line `fixed`. Row 3 records nothing outside the thread, so this is not a new record; it is what makes row 6's per-reviewer half derivable at all, since a thread three weeks later says who commented and when but not whether a fix was already in hand. Without it one of row 6's four columns has no source. The session decided this and reported it rather than putting it; the owner confirmed it in the same conversation.
- **An issue is no longer a pitch sold out of a pool.** The `filing` cell's subject narrows from how a pitch is sold and bought to how a finding becomes an issue that states work, and an agent may put a follow-up on the board only where the issue states its fix.
- **"In the pool" is replaced by "not on the board"** wherever the board's own machinery used it, including in the cause-and-bundle passages, which carried the old term outside the paragraphs the change's map first named.

### The outflow's disposition, and the headroom this change spends

Six cell bodies re-baselined to their printed sizes: `adversarial-review` 8,799, `board` 5,224, `siting` 4,244, `landing` 3,358, `records` 2,565, `filing` 2,006. The `adversarial-review` cell's body grew 634 characters as the ratchet measures it, 8,165 to 8,799, while the cell as a whole went from 79,172 bytes across 13 files to 42,087 across 11 — the brief's "shrunk" is a fact about the cell, not about its body.

**The always-on row moved 16,360 → 16,910 of 16,943, leaving 33 characters of headroom where there were 583.** The artifact expected the charter's growth to be paid by outflow from the two rewritten descriptions; they shed 39 bytes against +589 from the charter's Release bullet and the new `## Code Review Rules` section in `AGENTS.md`, which is 347 bytes and exactly the five sentences the artifact specified. No admission row was owed, because the row is under its constant. **The next change touching always-on prose will owe one.** This is recorded rather than smoothed because it is a cost this change imposes on the next one, and because the artifact's stated funding mechanism did not hold.

### How the close-out date is fixed

**The window opens at the merge commit's committer timestamp and closes 21 calendar days later.** The exact ISO date is recorded at merge, in one comment on #652 and one on #360 — not here, because this entry is committed before the merge exists and a date derived from a merge that has not happened is a forecast. The artifact asked for the date in this entry as well; that is unreachable without forecasting, and the rule above is what fixes it. No date reaches the shipped zone at all, so no adopting repository reads itself as bound to an experiment its owner did not agree to.

#360 stays open through the window. #652 supersedes it only in part; row 6 folds its close-out into this window, so #360 is rescoped by that comment and closes when the table is read.

## How this change was settled, and one dispatch that did not qualify

The artifact took two cold-seat rounds. Round 1, a Codex seat, returned `would not` on five points; every one was verified against the tree before it was acted on, including a flatly false claim that `tools/tests/test_trial_intake.py` did not exist when it is tracked at 629 lines. A Codex implementer repaired all five, and round 2, a fresh Claude seat, returned `would`.

**The round-1 seat was first launched with `--requires execute`, which no Codex seat can supply**, because `lib/dispatch_seat.py` gives every Codex seat a read-only sandbox by construction. The launcher fell back onto Claude — the artifact's own implementer's vendor — and that seat returned `would`, scoring as mere observations four of the five points the correctly-staffed seat later landed. **That fallback settled nothing and was not used.** It is recorded here because it is the clearest evidence on this record for why the judging seat sits on the other vendor from the implementer's, and because a fallback triggered by a mis-declared capability is not the availability failure the fallback rule contemplates.

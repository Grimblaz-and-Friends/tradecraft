# D-1030 — The reviewers and use read the first complete build

**Purpose:** record why #1014 moves the cold reading behind the reviewers, use and the criterion readers, and what was chosen over what. **Audience:** a future session changing the order of a change's checks, what holds the ready step, the cold reading's gate, the builder's step text, or the release report's account of what the reviewers read. **Success:** that reader can recover each choice without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/1014#issuecomment-7153014506) governs. Its plan was [settled on the would route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/1014#issuecomment-7153339656), from [the holder's draft](https://github.com/Grimblaz-and-Friends/tradecraft/issues/1014#issuecomment-7153192615); its decisions are G1 to G7. The lane is ordinary / connected, and no panel was bought. This change ran on the order in force before it.

It supersedes [D-952](D-952-2026-11-04-the-cold-reader-reads-each-change.md)'s hold on readiness and use (its "Named stages hold too", as far as `run ready-reviewers` and `run use`) and [D-1012](D-1012-2026-11-21-a-builders-own-checks-and-writes.md) C16, that only a composed `use` is held while a clean cold reading is owed. Both are otherwise in force and aren't edited.

## What was chosen over what

- **The reviewers, use and the criterion readers read the first complete build, their findings are answered in one batch, and the cold reading runs after that batch, holding only proof and the release report.** Chosen over all of them, the cold reader included, reading the first complete build together, and over the earlier order, in which the cold reading held the ready step, use, proof and the release report. The owner ruled on 2026-11-24, "Reviewers and use first", on the fork put with those three options.
- **Nobody had decided the earlier order.** #942's affirmed brief, row 4, says only that the cold reader runs "After the build". [The plan for #942's second pull request](https://github.com/Grimblaz-and-Friends/tradecraft/issues/942#issuecomment-6623789242), section 3.6, put the hold at one point in the entrance, before the draft-to-`ready-reviewers` branch, because one point was enough to hold every later stage. D-952 names no other order considered. The use session was held by that same point, with no ruling behind it.
- **Why the reviewers go first.** They are the check that finds defects, and behind the reading they found them after the last planned build turn, after which the reading was made again. The reading is stale at every push, and its fixes are mostly comments and documents, the smallest changes to leave for last. The brief's Shape and row 1 carry the figures.
- **"Ready for review" now means the planned build is complete and its reviewers may send it back,** not that the practice's other checks have passed; the release report stays the one thing that says a change is waiting on its owner. Chosen over keeping the pull request a draft and having each reviewer read drafts, which would change every adopter's reviewer settings and the rule that reviewers skip drafts. This rested on the holder's recommendation, which the owner affirmed in the brief.
- **A second reviewer look stays permitted and not owed,** and a builder on the builder route may buy one by the same rule and records it. The release report shows which head the reviewers read and how much changed after, so the owner can buy one where that is large without paying for one on every change.
- **The builder route's five-change comparison counts on and names the order each change ran under.** Chosen over restarting the count when this lands, which would leave the comparison undecided for up to five more changes.
- **A builder already running when the practice is updated finishes on the copy its handoff named, in that copy's order.** The brief first said such a builder would meet the new order at its next read; both cold seats on the plan gave `would not` on that point, because a handoff names one installed copy and every command the builder runs goes through it. The owner amended row 6 on 2026-11-25 ("Affirm") over building a way to move a running builder onto the updated copy, which would have had one change's reports composed under two versions.

## Calls

These are the calls the plan made inside the rows (its section 8).

- **C1. A named reading is refused before its turn** (G2): `run cold-reader` refuses `cold-reading-not-yet-owed`, launching nothing and naming the stage to take first. Row 3 says when the reading is owed, and leaving it launchable from the floor on would keep the earlier order one command away.
- **C2. The first use and the use at the head are two questions** (G1). One question would either run use twice whenever the fix batch touches a shipped path, or let the fix batch start without a use report.
- **C3. On the relay route the criterion readers' turn is carried by the decisions' own words** (G1). The entrance reads use and the reviewers there, not criterion reports, and a relay-route record of them is a mechanism the brief did not buy. So the ask that rode the ready step moves to the first fix stage and to the decision that orders the reading, and the holder's account of the criteria sits before the cold reading. For the same reason the release report's fix field reads `unknown` there for a change that owes a criterion reader, and never `false` (G4).
- **C4. A relay-route use that changed something waits for the reviewers** (G1, step 6). It is a fix, and row 2 says the first fix waits.
- **C5. The reviewers' head is read from the pull request's timeline** (G4), the last commit before the first `ready_for_review` event, because that needs no new record and covers a pull request made ready by hand. A reviewer whose first review names another commit is named beside it. Only the release report reads the timeline.
- **C6. A change's order is read from what happened to it** (G5): whether a cold reading came before its ready step. A change in flight at landing is then named by the order it in fact ran under.
- **C7. A ledger entry written before the order was recorded reads `cold-reading-first`** (G5), because no other order existed then.
- **C8. Thread resolution comes before the cold reader in the builder's steps** (G3), because the entrance names it straight after the answers.
- **C9. The release report's sentence on what the reviewers read sits directly after "Needs your decision"** (G6), so the owner sees how much followed the reviewers' look without opening the collapsed section.
- **C10. A copy moved under its builder is the one case where a builder's order changes mid-run** (G7). An adopter's update installs a new copy beside the named one, so row 6's builder and adopter cells say the same thing there. Where the named copy is a working checkout that is moved, as in this repository, the copy's order is then the new one, and the decision and the refusals lead the builder to it.
- **C11. The checks that need a later change are read by the lab's coordinating session** (C14 of the plan), because this change's holder and builder have ended by then.

## Rejected

All checks, the cold reader included, reading the first complete build together; the earlier order; a draft read by each reviewer in place of the ready step; restarting the comparison's count; moving a running builder onto the updated copy; a relay-route record of criterion reports; a marker recording the head the reviewers read.

## Not this

No check is removed, shortened or made optional. What the cold reader is given, what it flags, how its flags are accepted and how a reread is scoped are unchanged. The reviewers still review once for each pull request and still skip drafts; no reviewer's settings or wait change, and no second look is made automatic. Reach still holds the ready step, and a bought panel sits where it sat. Bringing a change's design to its owner before the build stays with #948.

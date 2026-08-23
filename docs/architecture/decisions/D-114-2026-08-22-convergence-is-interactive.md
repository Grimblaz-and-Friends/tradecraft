# D-114: Convergence is settled in conversation, and the affirmed artifact is the handoff contract

**Status:** Accepted 2026-08-22 (PR #114)

## Context

The Convergence bullet read: the change *"gets a pre-implementation artifact as a comment on its issue (file one if none exists): purpose, acceptance criteria, boundary statement. Its review is the convergence gate: the owner affirms, amends, or rejects in conversation, and the session records the affirmation on the issue, naming the artifact comment, before the first commit."* Read in order, that says the artifact is posted first and the owner meets it there — his first read of what a session decided to build happens on the issue, and the conversation is where he reacts to it.

That is not the flow he stated ([#85](https://github.com/Grimblaz-and-Friends/tradecraft/issues/85), settled in conversation 2026-08-20): **interactive convergence → a stopping point → hand to an implementer → next needed at PR review.** Nor is it what the convergence that first practiced it actually did — [D-104](D-104-2026-08-22-engagement-cell.md)'s artifact was drafted in chat, revised there against seven owner amendments, and posted once settled, with its affirmation record already using the words *"the comment above is the settled version, and it is the handoff contract"* and *"the owner is next needed at PR review."* The practice was ahead of the rule, and a rule the practice contradicts is one a fresh session follows into the wrong order.

The second half is what the ordering buys. If the artifact is settled before it is posted, the posted version can be the whole handoff — which is what lets the work leave the conversation for a fresh session or another runtime. Nothing said so, and nothing said what state the work reaches before the owner is wanted again.

## Decision

**The doctrine carries the ordering.** The Convergence bullet now states that the artifact is drafted and settled with the owner in conversation — the convergence gate, where he affirms, amends, or rejects — and that only the settled version is posted, *"the record of what was agreed, never where he first reads it"*; and that with the affirmation recorded, *"he is next needed at PR review."*

Three meaning changes, all of ordering, named here rather than left to the diff:

1. Drafting and revision happen in conversation **before** the comment exists.
2. The posted comment is a record, **not a review surface** for him.
3. Affirmation opens a stretch that is **unattended by design**, ending at PR review.

A consequence the owner stated on [#85](https://github.com/Grimblaz-and-Friends/tradecraft/issues/85) rather than a fourth change: convergence has no unattended lane before affirmation. A session with no conversational channel to him stops at the gate; it does not post a draft.

What the artifact contains, the before-the-first-commit timing, and the mechanical-work exemption are verbatim. **The affirmation-record clause is not**, and the artifact's own *"everything else … is verbatim"* line was wrong about it: it read *"the session records the affirmation on the issue, naming the artifact comment"* and now reads *"The session records the affirmation, naming that comment"* — the locative was dropped, so the doctrine no longer states where an affirmation record is written. The review's panel filed it from four seats; the correction and the owner decision it raises are on [#85](https://github.com/Grimblaz-and-Friends/tradecraft/issues/85#issuecomment-5383920241). The `convergence gate` naming is kept and re-attached: the gate is the conversation, not the comment's review.

**`engagement` carries the completeness bar and the ping definition.** Affirmed, the artifact is the handoff contract, and that is the test for whether it is finished: nothing load-bearing may be left in chat, because an implementer who was not there builds the affirmed thing from the artifact alone — cross-runtime handoff rests on that property and nothing else. The cell also states what the affirmation buys: the owner is next needed when the change is on a pull request whose review has run and closed, every finding dispositioned, external reviewer comments reconciled, and the report posted.

**Why the split falls there.** The doctrine's admitted content is what must bind before any context loads, and it is budgeted; the ordering qualifies, because a session that has loaded nothing must still not post first. *How complete* an artifact must be is methodology for writing one, read by a session that already has the cell open — and `engagement` owns the artifact whole [D-104]. #85 left the split open and the owner affirmed this reading, against the alternative below.

**Admitted** on [D-77](D-77-2026-08-19-owner-approval-admission-path.md)'s owner-approval path: the owner stated the flow, and the rule was affirmed as worded.

## Rejected

- **Stating the handoff-contract bar in the doctrine as well.** It would bind without the cell being loaded. Rejected on `authoring`'s own *"never duplicated prose that can drift"* — the same line that made [D-104](D-104-2026-08-22-engagement-cell.md) delete the doctrine's copy of the plain brief's elements after that copy drifted before it even landed — and on budget: `AGENTS.md` lands at 7,406 of 8,000 characters, and #86 is the next claimant on the remainder.
- **A tighter wording at about +60 characters** instead of +153 bytes (+149 characters), dropping *"never where he first reads it"* and the `convergence gate` naming. Put to the owner and declined: the dropped clause is the defect being fixed, and buying about 90 characters by deleting the sentence that does the work is the wrong economy while the budget still has room.
- **A mechanism.** Nothing in CI can observe whether drafting happened in chat. No lint, label, or check is proposed, and the rule is enforced by the same thing that enforces the rest of the flow — a session reading it.
- **Enumerating the pre-PR steps in the doctrine's Convergence bullet.** The flow line already states them; restating them beside it creates a second contract that can drift. The ping definition is stated once, in `engagement`, where a session asking *"is he wanted yet?"* is already reading.

## Evidence

[#85](https://github.com/Grimblaz-and-Friends/tradecraft/issues/85) — the artifact at [comment 5383751853](https://github.com/Grimblaz-and-Friends/tradecraft/issues/85#issuecomment-5383751853) and its affirmation at [comment 5383752482](https://github.com/Grimblaz-and-Friends/tradecraft/issues/85#issuecomment-5383752482), both produced under the ordering this entry lands. The prior convergence that practiced it first: [#84](https://github.com/Grimblaz-and-Friends/tradecraft/issues/84), comments 5380975104 and 5380976787.

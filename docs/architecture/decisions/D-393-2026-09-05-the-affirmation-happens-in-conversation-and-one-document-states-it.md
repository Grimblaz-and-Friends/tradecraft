# D-393: The affirmation happens in conversation, the always-on copy of that rule is deleted rather than reconciled, and the posted record takes the document shape

**Status:** Accepted 2026-09-05 (PR #393)

## Context

Two defects in one passage of `skills/engagement/SKILL.md`'s brief section, worked as one change under one brief.

[#385](https://github.com/Grimblaz-and-Friends/tradecraft/issues/385): `skills/charter/SKILL.md:26` put the owner's affirmation in conversation with the post as the record — *"drafted and settled with them in conversation, where they affirm, amend, or reject, and is recorded where the work lives … never where they first read it"* — while `skills/engagement/SKILL.md:45` posted the locked brief first and made the affirmation an answer to it: *"posted as its own comment when it locks … **Locked is not affirmed**."* The charter loads before any cell. A consumer given an ordinary convergence job on [PR #381](https://github.com/Grimblaz-and-Friends/tradecraft/pull/381#issuecomment-5548172534), told nothing was under test, wrote: *"Those two cannot both be simply true: he cannot have affirmed in conversation a version that only exists after the conversation."*

[#387](https://github.com/Grimblaz-and-Friends/tradecraft/issues/387): the form bullet gave a document and a message ending in a decision, and governed a third surface it did not name — the posted record, which has no ask, so the placement clause's stated reason does not reach it. Two consumers in two rounds reached the right reading only by composing the cell with the charter.

## Decision

**Both rulings are the owner's, given in conversation and recorded on [#385](https://github.com/Grimblaz-and-Friends/tradecraft/issues/385#issuecomment-5549340643).**

**1. The affirmation happens in conversation; the post is the record.** Put with three argued options — affirm-in-conversation with the post as record; the locked brief posted first and the affirmation answering it; or both shapes lawful. His ruling was *"A"*. `:45` now states one sequence: drafted and revised in conversation, locked, **put to them there**, affirmed there, and the affirmed brief posted as the record — *"never the version they are being asked to approve."* `Locked is not affirmed` survives unchanged in force.

**2. The rule lives in one place, and the always-on copy is deleted rather than corrected to agree.** This was the owner's own question, asked of a recommendation that had kept the charter's sentence and edited the cell to match: *"why do we still have this located in 2 places and not just in the skill?"* It changed the remedy from reconciliation to deletion and made the change smaller. The charter keeps what must hold before anything loads; its retained pointer is widened to route what left.

**3. The widening is not optional, and the move check is what established that.** [#388](https://github.com/Grimblaz-and-Friends/tradecraft/pull/388) landed `cell-structure.md:7`'s rule the day before: *a standard moves only to a cell that reaches the reader it is taken from*, checked by reading each hop and **never by finding the source's words in the destination**. The first hop failed — the base pointer's *"what **it** contains, how it is settled"* has **the artifact** as its antecedent, so deleting the sentence above it would have left the always-on surface routing a reader nowhere for the brief. Found by reading the antecedent; a grep for the charter's phrasing returns nothing and passes.

**4. The posted record takes the document shape rather than a third one.** `:16` names *"a comment recording an agreement"* alongside a document, and the placement reason stays with the message case: *"The recorded form has no ask, so that reason does not reach it."* Session evidence that this reaches a reader is under Evidence.

**5. D-381 item 4 is superseded, and this entry is where that is named.** That decision sited its rule beside the exclusion bullet and left the locking paragraph alone, expressly *"so no second copy exists to drift."* E2 adds 229 characters at that paragraph restating `:21`'s rule. The review's judge sustained it, and the fix batch discharged it by removing the posting half from `:21` — *"What locks and gets posted"* → *"What locks"* — so one copy stands, at `:45`. The siting call is reversed knowingly: `:45` is where the sequence now lives, and the rule about what is posted belongs with it.

## Rejected

- **Correcting the charter to agree with the cell, keeping both.** The session's first recommendation. Rejected by the owner's second ruling: two documents stating one thing is how they came to disagree.
- **Posting the locked brief first and affirming the posted version** (option B). Byte-identical approval and record, and asynchronous approval; against it, an always-on edit deleting *"never where they first read it"*, and it is the branch a consumer said leaves a session posting and waiting.
- **Both shapes lawful** (option C). Every session then decides which it is in, which is the ambiguity being removed.
- **A third form shape for the posted record.** Its placement is identical to the document's; two rules where one holds.
- **Any repo-local edit.** `AGENTS.md:15` asserts no order between approval and post and stays true; stating the sequence there would rebuild the second copy on a different always-on surface. Recorded rather than fixed — see Known limits.
- **Adding the posted record to `:26`'s enumeration of brief-bearing surfaces.** Sustained by the review as real and ruled `record`: `:16` covers the placement, and a consumer produced the recorded form from the form bullet alone.
- **Deleting `:45`'s *", given in the conversation where they read it"*** as entailed, proposed by the `operational` seat. Dropped: it is the only sentence in the shipped tree stating where the ordinary-case affirmation is given, which is ruling 1. Deleting it deletes the fix.

## Evidence

The affirmed brief is on [#385](https://github.com/Grimblaz-and-Friends/tradecraft/issues/385#issuecomment-5549339096) with the [affirmation](https://github.com/Grimblaz-and-Friends/tradecraft/issues/385#issuecomment-5549340643) beneath it, the [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/385#issuecomment-5549381430) and its [amendment](https://github.com/Grimblaz-and-Friends/tradecraft/issues/385#issuecomment-5549384359).

The cold check ran one round and returned `would` with no adverse points, judging sha256 `00f385f04303aa133d238ad36aa776d7b0691629394395a85bfad86d3e56ec9e` at 12,859 bytes and confirming the tree at `8ed30af`. Three of its four observations are ruled in the amendment.

**Three cold consumers**, on throwaway trees from `12ce558`, none told anything was under test, [reported in full](https://github.com/Grimblaz-and-Friends/tradecraft/pull/393#issuecomment-5549533990). Two had the owner unreachable or effectively so and both stopped at the affirmation gate naming the sentence that stopped them. The third, resuming past an affirmation, posted the record with the brief opening the comment and no ask, and wrote unprompted: *"Recorded, not put: this is the record of an agreement settled in conversation, so it carries no ask."* It composed nothing to get there, where PR #381's consumers needed the cell and the charter together.

The review is a four-seat panel, defense and judge, six dispatches, [reported in full](https://github.com/Grimblaz-and-Friends/tradecraft/pull/393). Terminal ruling: fit for purpose once the named fixes land.

## Known limits, stated rather than glossed

**The changed sequence was exercised by one consumer, not three.** Two arms tested the gate; only the third reached past it. The dispatcher's error caused that: the arm with a nominally reachable owner was given a channel — *"put anything you need at the end of your final report"* — that reads as handing back, so it took the waiting route and the axis did not vary.

**This change grew shipped governing prose while its headline reports a shrink.** After the fix batch: charter 5,502 → 5,385 (−117), `engagement` 26,530 → 27,039 (+509), **net +392**. Nothing in the acceptance criteria measures a character of what the change adds, and nothing mechanically could — `engagement` carries no body budget, so 509 characters and 5,090 are the same green. That is the third instance of a class `docs/recorded-findings.jsonl` had recorded twice and acted on never; the judge promoted it, and the remedy is its own board issue.

**No guard distinguishes this change from the defect it removes.** With the charter reverted to `8ed30af` — #385 unfixed and actively contradicting the new `:45` — `lint` returns 0 findings, 816 tests pass, and the version guard is satisfied. Probed by the `wiring-falsifier` seat and reproduced independently by the defense and the judge. No new guard is asked for: `check_charter_cell` prices content checks out on purpose. The four criteria rest on reading and on one consumer.

**The owner's automated merge-time read understates this change.** `tools/doctrine_callout.py`'s paths cover the charter and repo-only cells, not shipped cell bodies, so the callout on this PR names `skills/charter/SKILL.md` and reports −117 — silent on the file carrying three of the four edits. Already [#386](https://github.com/Grimblaz-and-Friends/tradecraft/issues/386).

**Seven recipients, seven stale injections.** Every dispatched recipient across this change — the cold seat, four panel seats, the defense and the judge — was injected a `skills/charter/SKILL.md` carrying the paragraph #388 removed the day before, and several also carried this change's own pre-edit text. All seven judged against disk because `skills/engagement/references/cold-seat.md`'s isolation statement told them to. That clause is the difference between seven correct judgements and seven judgements of text that no longer exists.

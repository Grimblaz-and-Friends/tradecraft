# The plain brief and the implementation brief

**Loaded when** you are drafting or scoring a plain brief, designing, putting or recording an implementation brief with the owner, briefing the systemic cause behind a problem, amending an implementation brief or the reading of one already recorded, or handing work back after time away. A session that only needs to know an affirmed implementation brief binds does not need it; the cell body states that.

## The shared plain-brief form

- **Form:** a blockquote opening with a bold lead-in — `> **In plain terms:** …` — **immediately before what it briefs**. On a document whose opener it is, that is the top, with nothing above it but a title; on a message ending in a decision it is directly above the ask, because everything between a brief and its ask is what the reader has to hold to connect them. An implementation brief's recorded comment is the affirmed item itself rather than this paragraph form, and carries no ask.
- **Plain English, and no term the owner would have to look up.** It explains; it does not compress. Issue numbers, decision citations, file paths, and a figure or the command that derives it, are not plain English, and they belong below.
- **What earns a place in every plain brief:** what this is, why it matters, what the owner is being asked, and what they have already settled. A plain brief disqualifies implementation detail, supporting evidence, enumerations, and rejected alternatives; no disqualifier removes required content.
- **A plain brief on a change that applies a ruling the owner already made and decides nothing further opens by saying so and names the ruling.** That is the brief's first sentence, inside the blockquote, naming the rule and where they settled it **in the plain English the blockquote requires, never by issue number or decision citation**. **A brief that asks them something carries no such line**, and neither does one on work applying no prior ruling: what triggers it is having a ruling to name, never the absence of an ask.
- **Length is not a count.** The bar is readable in one pass, and longer is lawful where there is a reason for it. The disqualifier is what keeps a brief short; a word limit would reject a good six-sentence brief for being seven, which is why concision is stated as a rule about content rather than length.
- **A descriptive plain brief may put something out of scope**, and that boundary is accountable to the thing described. The implementation brief's `Not this` carries the binding edge the owner affirms; where it names no exclusion it excludes nothing, and the artifact's boundary supplies only the session's reading of the remaining edge.

## The implementation brief

**An implementation brief is the whole item the owner affirms before a change that owes one is built: one Shape sentence; the Readers named once; each decision that matters as a row carrying its Why and one cell per reader; and Not this.** A blank cell is visible and unlawful; `unchanged` is a filled cell.

The form ends with these two lines:

```text
Review risk: ordinary
Review lane: connected
```

The lawful pairs are `ordinary` with `connected`, `ordinary` with `mechanical`, `elevated` with `routine-panel`, and `critical` with `substantial-panel`; carrying the pair in the affirmed item makes its review depth available to the entrance rather than a later recollection.

**The holder proposes `mechanical`, and the owner's affirmation selects it.** It applies only to a determinate, bounded correction or application of an already settled outcome, with no substantive choice about the desired behavior or rule left for the builder. Restoring agreed behavior can qualify; a short diff alone cannot, and a one-sentence new behavior or rule still needs design. The entrance reads the affirmed pair rather than inferring it from paths, size or a casual mention. An affirmed mechanical lane skips the artifact, cold seat and use while retaining the applicable floor as defined by the work contract, connected reviewers and their dispositions, proof and the release report; it buys no panel.

A configured shared gate that does not read the affirmed mechanical lane may still fail when changed paths buy a use; the entrance preserves that result, and the explicit release report records it with any bypass and its reason.

The Readers name the owner, the holding session that designs with them and runs the stretch, the builder that writes the artifact and builds, and a judging seat, cold or review or consumer. For shipped work, the adopter's owner and sessions are one reader when their outcome is identical in every row. Each row states the decision, its reason, and what every reader gets. Session-owned execution choices — implementation approach, file layout, tools, and work order — stay out and belong in the artifact and build.

**The affirmed item is the exact text kept from affirmation onward; none of it needs to have been typed by the owner.** When a push changes a row, the affirmation record quotes that push once, while the revised row in the affirmed item is the term the builder reads.

**For an implementation brief affirmed in the earlier paragraph form, its agreed terms are read as its rows, and the seat judges whether the artifact delivers what that brief agreed.**

An item that put a question to the owner is re-put whole carrying their answer: each ruling written in as settled, and anything ruled out stated so the item stands without the conversation.

## Designing, putting, and recording the item

**Where the work picked up is a problem rather than a want, the implementation brief is for its systemic cause.** Before the first turn in `../references/design-sitting.md`'s form, ask why until the cause is systemic — one whose fix would have prevented this instance and its open siblings. The siblings the test found are tied to the cause before the whole item is put, so what the fix covers is on the record and not in the session's head. The instance falls out of the fix, or the implementation brief says why it does not; fixing the instance alone is the owner's exception. Where the why-chain leaves an instance-or-cause choice, open it with the owner as a turn, even when the session has a recommendation, carrying the recommendation and the strongest case against it. Record the choice as an implementation-brief row with its reason only after the owner rules, because the recommendation does not settle it. **Where those symptoms are already tied to a cause and the why-chain reaches a different one, the implementation brief disputes that parentage and recommends the new one.** The disputed symptoms are not re-tied until the owner rules; their ruling is what re-ties them. A cause still a hypothesis when the asking stops is a premise that could make the implementation brief wrong. A bundle is one set with one cause. A want that would make something currently wrong stop being wrong is a problem.

**The session judges the concept done when the next turn would add execution detail rather than a decision, then puts the whole implementation brief for affirmation.** Before putting it, check that every decision row has its reason, every reader cell is filled, no row is execution detail, and exactly one lawful `Review risk` and `Review lane` pair is present. The owner affirms the whole item or pushes it; the design ends only on affirmation, never on running row-by-row approval.

Before putting the item, run `python <plugin-root>/lib/brief.py --check FILE` over the finished draft; it decides only whether Shape, Readers, a decision block, Not this, and exactly one lawful `Review risk` / `Review lane` pair are present, never whether the rows carry their reasons and reader cells, execution detail stayed out, or the content is right.

**A builder starts only from an affirmed implementation brief.** A put, push, or draft is not the term.

Before putting a descriptive plain brief, score the finished text against each of that form's disqualifiers by name. Before putting an implementation brief, run the row-reason-cell-execution-risk-lane check above over the finished item. These are passes over what was written, not rereadings of the form before writing: [opening a form immediately before drafting has failed to prevent the defect](https://github.com/Grimblaz-and-Friends/tradecraft/issues/428). The record says what the applicable pass removed, and says so where it found nothing.

**The conversation with the owner is the engagement surface.** Three more are this cell's to name: a review's final report, where its descriptive plain brief opens the report as posted; a message handing work back after time away, which also carries where the work now stands; and the pre-implementation artifact, which carries the affirmed implementation brief because it binds there.

**The implementation brief is settled with the owner; the artifact is the session's reading of it.** The whole item is put once the session judges the concept done, and affirmation is the owner's answer to it in the conversation where they read it. **What is posted on the work's issue is the affirmed implementation brief, as the record of what was agreed** — never the version they are being asked to approve — the waiting rule (`../references/waiting.md`) is the exception, and the only one. **That record carries the implementation brief's own history:** how many times the whole item was put, how many amendments and by whom, how many drafts the owner corrected before one was posted, what the pre-put check removed, and each push that changed a row quoted once. Write it while the conversation is in hand. A premise that could make the implementation brief wrong is tested before the whole item is put.

Begin that recorded issue comment with the `work` cell's affirmation marker:

```text
<!-- tradecraft:affirmed-brief:v1 -->
```

## Amendments

**An amendment is a further comment, never an edit.** Preserve the earlier agreement and name what changes. A change to an affirmed row is agreed with the owner through the row-changing post-affirmation door, with the ask's cost stated, because that row is what they approve. A change only to the holder's reading is recorded with the holder's reason and needs no second verdict, since a re-check per reading amendment costs more than it buys. A question the record or precedent answers takes the coordinating-session route first.

**A review-lane change at any time is a new affirmed brief, never a holder reading.** The entrance selects the lane from the latest affirmed brief. Moving off the mechanical lane writes and settles the newly owed artifact; keeping the brief on that lane, or moving it onto that lane, owes no artifact, pointer or cold settlement. Where the new lane owes an artifact, the artifact carries the new brief and is settled against its terms.

**Before the first build, record an amendment to the implementation brief as a new affirmed brief.** Where its lane owes an artifact, revise the artifact to point to and carry that brief, and settle an already-judged artifact again against the changed term, because the builder must receive the agreed plan.

**From build onward, where the lane has a settled artifact and the amendment keeps that lane, record an owner-affirmed row change in an amended holder reading quoting the changed row whole and recording the owner's ruling.** That ruling governs the affected row while the other affirmed terms continue to bind. Do not re-post the brief, revise the artifact or buy another cold verdict: the builder receives the amended reading, and the built result still owes its floor, review and use. An amendment changing only the reading uses the same carrier with the holder's reason.

**On the mechanical lane, record the owner's amendment as a new affirmed brief.** That lane has no artifact or composed-prompt readings, so the new brief carries the changed terms to the builder.

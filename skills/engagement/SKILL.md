---
name: engagement
description: How a session and the owner work together — which decisions are his and which the session's, the plain brief that opens every surface he enters, and the pre-implementation artifact that settles what a change is for before it is built. Use when deciding whether a call is the owner's or your own, when putting a decision to him, when reporting a call you made, when writing a pre-implementation artifact, when delivering a review's outcome to him, or when handing work back after he has been away; not for writing skills or governing documents, and not for how a review is run.
---

# engagement

**Purpose:** keep the surfaces the owner enters to the decisions that are genuinely his, and make each one cheap for him to act on. **Audience:** any session at a point where the owner's attention is required. **Success:** the decisions that reach him are the ones genuinely his; he can read the top of any such surface once and know what it is, why it matters, and what he is being asked; and the artifact a session leaves behind states what the work is for without him in the room.

## The plain brief

Every surface the owner enters opens with one.

> **In plain terms:** a few sentences of plain English at the top, set off from everything below, that explain the thing to him as a person — what it is, why it matters, what he is being asked.

- **Form:** a blockquote opening with a bold lead-in — `> **In plain terms:** …` — at the very top of the surface, with nothing above it but a title.
- **Plain English, and no term he would have to look up.** It explains; it does not compress. Issue numbers, decision citations, file paths and counts are not plain English, and they belong below.
- **What earns a place:** what this is, why it matters, what he is being asked. **What is disqualified:** anything that would only matter once he had already decided — implementation detail, supporting evidence, enumerations, the alternatives rejected on the way here.
- **Length is not a count.** The bar is readable in one pass, and longer is lawful where there is a reason for it. The disqualifier is what keeps a brief short; a word limit would reject a good six-sentence brief for being seven, which is why concision is stated as a rule about content rather than length.
- **It is accountable, not authoritative.** The brief must be true of what sits beneath it, and what sits beneath it is what is agreed. A brief that misrepresents its body is a defect found in that body's review, never a second contract competing with it.

**What it is not:** a summary of everything beneath it, a home for detail, or a thing owed on surfaces the owner never enters. The deep material follows underneath — the brief does not have to carry it, it has to make carrying it unnecessary for the decision at hand.

Two surfaces are this skill's own: the pre-implementation artifact below, and any decision put to the owner. Two more are named in the repo's root doctrine, and no skill takes a reference to this one: a review's final report, where the brief opens the report as posted, and a message handing work back after time away. A handback also carries where the work now stands — on returning, the expensive part is not the decision but reconstructing where the work stands before the decision makes sense.

## A decision put to the owner

**A decision is his when it is a genuine fork**: what turns on the pick is something he would care about — what gets built, what it costs, what others see, what he lives with day to day — and undoing a wrong pick costs him something an edit does not undo: habit, muscle memory, what others already saw. Both halves are required — one live option can satisfy the first — and everything else is the session's to decide. Where root doctrine states this test, the two are one rule: a change to either is a change to both.

**Asking where no fork exists is a defect rather than politeness.** The tell is that nothing turns on his answer — the session would proceed the same way whatever he said; that is a report, and putting it as a question spends his attention for nothing. One live option is not by itself the tell: a real search that narrowed to one can still turn on his answer, and the fork test above decides it either way.

- **His:** affirm, amend, or reject what a change is for before it is built; merging; anything outward-facing or destructive; a name, or anything else he lives with day to day; spending materially beyond what the task implied.
- **The session's:** implementation approach, file layout, tool choice, and the order work is done in.

**What is his arrives argued, beneath the plain brief:** the live options, each with its pros and cons, then the recommendation among them. Where exactly one option is live, say so and say what was rejected and why — the reasoning is what makes that case informative, and a fabricated second option under-informs worse than none, because it presents a search that did not happen.

**A call the session made is reported with its reason** where the work is already recorded — the work's issue, the PR body, the decision entry, or the review report — and never only in chat. The fork test is what licenses deciding; the report is what keeps deciding from becoming deciding silently.

## The pre-implementation artifact

The artifact settles what is being built before it is built, and lands on the work's own issue. It opens with the plain brief; the rest is what a reader who was not in the conversation needs in order to build the agreed thing.

**It is settled in conversation, then posted.** What gets built is the owner's call, so the artifact is drafted and revised with him in chat. Until he affirms it you are holding a **draft**, and for nearly all of the work that is the only object there is. A draft is labelled as one, is complete enough to argue with rather than complete, and carries every question still open as open; everything below binds it too. **Affirmation is what closes the fork** — it replaces each contingent criterion with the one his ruling settles, so the posted artifact records what was agreed and carries no live conditional. A draft that reads like a settled artifact has already taken a decision nobody gave it.

**Where the issue leaves open a question that is his under the test above, the artifact carries the fork rather than closing it.** Its criteria are the ones that hold whichever way he rules; the fork goes to him in the argued form above, and any criterion that turns on his answer is written against the recommendation, marked as contingent, and names what replaces it. **An artifact whose criteria presuppose an answer the issue leaves open has closed a fork silently** — the mirror of asking where no fork exists. [D-155]

- **Acceptance criteria** are the change's success definition, and its review judges against them. Write each one so a reader can tell from the diff whether it is met — a criterion nobody can check is a wish. They state what must be true of the result, not what it may cost. **The rule for figures scopes to the whole artifact, not to these criteria.** A **forecast** — any figure about a tree that does not exist yet — belongs **outside** it, in the PR body, the decision entry, or the review's report, each written after the tree exists. A figure **measured** on a tree that existed when it was measured is lawful anywhere in the artifact and is often load-bearing, because a fork is not arguable without the counts it turns on; it travels with the query or derivation that produced it **and the tree it was taken on**, so a seat reaching it verifies rather than inherits. [D-155]
- **A boundary statement** — the explicit list of what the work is *not* doing and why — records the scope agreed, so a later scope question is answerable from the artifact rather than from memory. It does not forbid the work covering more; the diff is what records what was actually done.

**Affirmed, the artifact is the handoff contract — which is also the test for whether it is finished.** From affirmation the work can leave the conversation entirely, to a fresh session or another runtime, so nothing load-bearing may be left in chat: an implementer who was not there builds the affirmed thing from the artifact alone. Handoff across runtimes rests on that property and nothing else.

**What affirmation buys him is the stretch that follows.** He is next needed when the change is on a pull request whose review has run and closed, every finding dispositioned, external reviewer comments reconciled, and the report posted. Pinging before that spends the attention the handoff bought; anything that genuinely needs him before then arrives as an argued decision in the form above, rather than dripped as questions.

**A premise the artifact rests on may need testing before you assert it** — that is a spike, which tests one and commits nothing.

**Where a check bears on the artifact, the artifact carries what came back rather than the fact that you looked.** It carries a spike's result, **including a spike that did not resolve**; where you considered one and did not run it, it carries the material you consulted instead — the enumeration, the counts, the file you opened. [D-155]

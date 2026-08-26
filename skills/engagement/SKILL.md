---
name: engagement
description: How a session and the owner work together — which decisions are the owner's and which the session's, the plain brief that opens every surface they enter, and the pre-implementation artifact that settles what a change is for before it is built. Use when deciding whether a call is the owner's or your own, when putting a decision to them, when reporting a call you made, when writing a pre-implementation artifact, when delivering a review's outcome to them, or when handing work back after they have been away; not for writing skills or governing documents, and not for how a review is run.
---

# engagement

**Purpose:** keep the surfaces the owner enters to the decisions that are genuinely theirs, and make each one cheap for them to act on. **Audience:** any session at a point where the owner's attention is required. **Success:** the decisions that reach the owner are the ones genuinely theirs; they can read the top of any such surface once and know what it is, why it matters, and what they are being asked; and the artifact a session leaves behind states what the work is for without them in the room.

## The plain brief

Every surface the owner enters opens with one.

> **In plain terms:** a few sentences of plain English at the top, set off from everything below, that explain the thing to the owner as a person — what it is, why it matters, what they are being asked.

- **Form:** a blockquote opening with a bold lead-in — `> **In plain terms:** …` — at the very top of the surface, with nothing above it but a title.
- **Plain English, and no term the owner would have to look up.** It explains; it does not compress. Issue numbers, decision citations, file paths and the command behind any figure are not plain English, and they belong below.
- **What earns a place:** what this is, why it matters, what the owner is being asked. **What is disqualified:** anything that would only matter once they had already decided — implementation detail, supporting evidence, enumerations, the alternatives rejected on the way here.
- **Length is not a count.** The bar is readable in one pass, and longer is lawful where there is a reason for it. The disqualifier is what keeps a brief short; a word limit would reject a good six-sentence brief for being seven, which is why concision is stated as a rule about content rather than length.
- **It is accountable, not authoritative.** The brief must be true of what sits beneath it, and what sits beneath it is what is agreed. A brief that misrepresents its body is a defect found in that body's review, never a second contract competing with it.

**What it is not:** a summary of everything beneath it, a home for detail, or a thing owed on surfaces the owner never enters. The deep material follows underneath — the brief does not have to carry it, it has to make carrying it unnecessary for the decision at hand.

Two surfaces are this skill's own: the pre-implementation artifact below, and any decision put to the owner. Two more are this cell's to name: a review's final report, where the brief opens the report as posted, and a message handing work back after time away. A handback also carries where the work now stands — on returning, the expensive part is not the decision but reconstructing where the work stands before the decision makes sense.

## A decision put to the owner

**A decision is the owner's when it is a genuine fork**: what turns on the pick is something they would care about — what gets built, what it costs, what others see, what they live with day to day — and undoing a wrong pick costs them something an edit does not undo: habit, muscle memory, what others already saw. Both halves are required — one live option can satisfy the first — and everything else is the session's to decide. The statement of the test is the `charter` cell's — or an adopting repository's own doctrine, where that is where it lives; the calibration below is this cell's.

**Asking where no fork exists is a defect rather than politeness.** The tell is that nothing turns on their answer — the session would proceed the same way whatever they said; that is a report, and putting it as a question spends their attention for nothing. One live option is not by itself the tell: a real search that narrowed to one can still turn on their answer, and the fork test above decides it either way.

- **Theirs:** affirm, amend, or reject what a change is for before it is built; merging; anything outward-facing or destructive; a name, or anything else they live with day to day; spending materially beyond what the task implied.
- **The session's:** implementation approach, file layout, tool choice, and the order work is done in.

**What is theirs arrives argued, beneath the plain brief:** the live options, each with its pros and cons, then the recommendation among them. Where exactly one option is live, say so and say what was rejected and why — the reasoning is what makes that case informative, and a fabricated second option under-informs worse than none, because it presents a search that did not happen.

**A call the session made is reported with its reason** where the work is already recorded — the work's issue, the PR body, the decision entry, or the review report — and never only in chat. The fork test is what licenses deciding; the report is what keeps deciding from becoming deciding silently.

## The pre-implementation artifact

The artifact settles what is being built before it is built, and lands on the work's own issue. It opens with the plain brief; the rest is what a reader who was not in the conversation needs in order to build the agreed thing.

**It is settled in conversation, then posted.** What gets built is the owner's call, so the artifact is drafted and revised with them in chat. Until they affirm it you are holding a **draft**, and for nearly all of the work that is the only object there is. A draft is labelled as one, is complete enough to argue with rather than complete, and carries every question still open as open; everything below binds it too. **Affirmation is what closes the fork** — it replaces each contingent criterion with the one their ruling settles, so the posted artifact records what was agreed and carries no live conditional. A draft that reads like a settled artifact has already taken a decision nobody gave it.

**Where the issue leaves open a question that is theirs under the test above, the artifact carries the fork rather than closing it.** Its criteria are the ones that hold whichever way they rule; the fork goes to them in the argued form above, and any criterion that turns on their answer is written against the recommendation, marked as contingent, and names what replaces it. **An artifact whose criteria presuppose an answer the issue leaves open has closed a fork silently** — the mirror of asking where no fork exists. [D-155]

- **Acceptance criteria** are the change's success definition, and its review judges against them — so what they name is what every stage of that review inherits. **Write each one as something a consumer of the result can do, or no longer does wrongly** — whoever works under the built result, most often a session, in a situation the change exists for. A criterion about the artifact *conforming* — a count, a section present, a wording faithful, a file untouched — is lawful where it argues its own consumer-facing load, which it states; written for its own sake it ratifies the bookkeeping class the review can then no longer dismiss for want of a criterion it impairs. They state what must be true of the result, not what it may cost. [D-166]
- **Each criterion names the check that would falsify it** — a criterion nobody can check is a wish. The diff settles what the diff can settle, a command settles what a command can run, and what only use shows is settled by putting the situations to a session that has none of this change's history, or by the built result in use; the criterion says which. **Naming the check does not order it run**: the criterion states how the claim could be falsified, and what a change owes in runs is not this rule's to say. [D-166]
- **A criterion a plausible wrong implementation would also pass measures nothing.** Say what failing looks like before writing it; where the artifact carries a fork, a criterion held to survive it must be falsifiable on **every** branch it survives — the cheapest cross-branch criterion is one that is empty on a branch. [D-166]
- **The rule for figures scopes to the whole artifact, not to these criteria.** A **forecast** — any figure about a tree that does not exist yet — belongs **outside** it, in the PR body, the decision entry, or the review's report, each written after the tree exists. [D-155] A figure **measured** on a tree that exists is stated as the command that derives it and the tree it runs on, **never as the number**: the artifact freezes on affirmation, so a number in it is one a seat inherits rather than checks. [D-194]
- **A boundary statement** — the explicit list of what the work is *not* doing and why — records the scope agreed, so a later scope question is answerable from the artifact rather than from memory. It does not forbid the work covering more; the diff is what records what was actually done.

**Affirmed, the artifact is the handoff contract — which is also the test for whether it is finished.** From affirmation the work can leave the conversation entirely, to a fresh session or another runtime, so nothing load-bearing may be left in chat: an implementer who was not there builds the affirmed thing from the artifact alone. Handoff across runtimes rests on that property and nothing else.

**What affirmation buys the owner is the stretch that follows.** They are next needed when the change is on a pull request whose review has run and closed, every finding dispositioned, external reviewer comments reconciled, and the report posted. Pinging before that spends the attention the handoff bought; anything that genuinely needs them before then arrives as an argued decision in the form above, rather than dripped as questions.

**A premise the artifact rests on may need testing before you assert it** — that is a spike, which tests one and commits nothing.

**Where a check bears on the artifact, the artifact carries what came back rather than the fact that you looked.** It carries a spike's result, **including a spike that did not resolve**; where you considered one and did not run it, it carries the material you consulted instead — the enumeration, the query and the tree it ran on, the file you opened. [D-155]

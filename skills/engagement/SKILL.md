---
name: engagement
description: How a session and the owner work together — the plain brief that opens every surface he enters, and the pre-implementation artifact that settles what a change is for before it is built. Use when writing a pre-implementation artifact, when putting a decision to the owner, when delivering a review's outcome to him, or when handing work back after he has been away; not for writing skills or governing documents, and not for how a review is run.
---

# engagement

**Purpose:** make every surface the owner enters cheap for him to act on. **Audience:** any session at a point where the owner's attention is required. **Success:** he can read the top of any such surface once and know what it is, why it matters, and what he is being asked, and the artifact a session leaves behind states what the work is for without him in the room.

## The plain brief

Every surface the owner enters opens with one.

> **In plain terms:** a few sentences of plain English at the top, set off from everything below, that explain the thing to him as a person — what it is, why it matters, what he is being asked.

- **Form:** a blockquote opening with a bold lead-in — `> **In plain terms:** …` — at the very top of the surface, with nothing above it but a title.
- **Plain English, and no term he would have to look up.** It explains; it does not compress. Issue numbers, decision citations, file paths and counts are not plain English, and they belong below.
- **What earns a place:** what this is, why it matters, what he is being asked. **What is disqualified:** anything that would only matter once he had already decided — implementation detail, supporting evidence, enumerations, the alternatives rejected on the way here.
- **Length is not a count.** The bar is readable in one pass, and longer is lawful where there is a reason for it. The disqualifier is what keeps a brief short; a word limit would reject a good six-sentence brief for being seven, which is why concision is stated as a rule about content rather than length.
- **It is accountable, not authoritative.** The brief must be true of what sits beneath it, and what sits beneath it is what is agreed. A brief that misrepresents its body is a defect found in that body's review, never a second contract competing with it.

**What it is not:** a summary of everything beneath it, a home for detail, or a thing owed on surfaces the owner never enters. The deep material follows underneath — the brief does not have to carry it, it has to make carrying it unnecessary for the decision at hand.

Two surfaces are this skill's own: the pre-implementation artifact below, and any decision put to the owner. Two more are named in the repo's root doctrine, and no skill takes a reference to this one: a review's final report, where the brief opens the report as posted, and a message handing work back after time away. A handback carries what the work is, where it now stands, and what is being asked of him — on returning, the expensive part is not the decision but reconstructing where the work stands before the decision makes sense.

## The pre-implementation artifact

The artifact settles what is being built before it is built, on the work's own issue. It opens with the plain brief; the rest is what a reader who was not in the conversation needs in order to build the agreed thing.

- **Acceptance criteria** are the change's success definition, and its review judges against them. Write each one so a reader can tell from the diff whether it is met — a criterion nobody can check is a wish.
- **A boundary statement** — the explicit list of what the work is *not* doing and why — records the scope agreed, so a later scope question is answerable from the artifact rather than from memory. It does not forbid the work covering more; the diff is what records what was actually done.

**Where the artifact asserts something about material no enumeration you can consult covers, or about a mechanism nobody has executed, test that premise before you assert it** — a spike, which commits nothing. Reading a design settles neither, and the condition is narrow: most artifacts assert neither. [`references/spikes.md`](references/spikes.md) has the exclusions, the bound, the abandonment route, the report, and the standing permission to explore without a premise.

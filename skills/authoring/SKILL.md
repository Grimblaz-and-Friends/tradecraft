---
name: authoring
description: How to create and revise this practice's prose — the purpose header every governing document carries, which home each kind of content takes, what a cell owes the roster it joins, and the writing standards that keep it lean. Use when writing, restructuring or revising a skill or governing document, including a description alone or what sheds behind a pointer; when deciding where content belongs or editing an always-on surface; or when a write-up, a pre-implementation artifact included, states derived figures or describes current behaviour; not for how code is written, though where such a rule belongs is here; not for reviewing finished content, and not for deciding what a change is for.
---

# authoring

**Purpose:** make every governing document and skill in the practice accountable to a stated job, and what a write-up rests on — its figures, and its claims about how things behave — re-derivable rather than inherited. **Audience:** any session creating or revising a skill or governing document, or stating a derived figure or a behaviour claim in a write-up — in this repo or a repo that adopts the practice. **Success:** every document it governs can say what it is for, who reads it, and what its review should judge it against — and contains nothing that fails that test; every skill earns what it puts in a session's context and keeps the rest behind a pointer; every figure it governs is its command and tree, or lives where it re-derives, and every behaviour claim on a surface nobody goes back to correct names what demonstrates it.

## The purpose header

Every governing document and skill opens by answering three questions, a sentence or two each:

- **Purpose** — the job this document does; the question it answers.
- **Audience** — who reads it, and when.
- **Success** — what must be true for it to be doing its job. This is what its review judges against.

A document that cannot state these three is not ready to be written; the missing statement is its first defect. For a skill, the frontmatter `description` carries the trigger (use when / not for) and the body's opening carries the header.

## Routing — where content lives

Every piece of content has one home: methodology in a skill, a binding rule in the practice's always-on surface, rationale in a decision entry, what happened in append-only exhaust. Which one a given piece takes, and what a shipped standard owes its local application, are in `references/routing.md` — load it when the home is the question, or when editing an always-on surface, which is when outflow is owed.

**A ceiling reached is a trigger, not a wall.** A budgeted surface is designed to sit tight, so a full one is what calls for the moves in that file — never a reason to leave the surface unedited, or to shrink what is being added until it fits.

## Writing standards

- **Write for the stated audience, and assume it is capable.** The purpose header names who reads this document — usually model sessions, sometimes people — and every instruction is tested against that audience, not a generic reader: ask whether the stated audience needs it, or just the goal and constraints, remembering that what trips a session is not what trips a person. Most candidate instructions fail this test and should not be written.
- **State the rule with its reason; link the evidence.** The reason is one short clause that lets a reader apply the rule well and notice when it stops applying. The evidence — counts, incidents, history — goes behind a link. Prose that litigates its own justification taxes every future reader to persuade one who is not there.
- **Prefer the rule whose compliance is visible on the artifact its reader is producing**, over one asking for a judgment resolved against a document that is not in front of them. Measured over this practice's own merged history, the first kind holds with nothing enforcing it and the second is the weakest band there is ([the sweep](https://github.com/Grimblaz-and-Friends/tradecraft/issues/256)); what transfers is that separation, never a rate. Where only the second form can carry the rule, give it a carrier the writer already has open — a key in the record being appended, a line in the template being filled — because that is the move that converts one form into the other. Where the writer has no durable artifact open, say so where the choice is recorded rather than naming a carrier nothing retains.
- **Do not armor against misreadings.** A clause defending against a reader who would not actually err is pure cost. If a competent reader genuinely could go wrong, restate the sentence more plainly rather than appending a qualifier to it.
- **Deletion is a first-class edit.** Propose removals with the same energy as additions. Net growth of a governing document needs a justification the way a new rule does — the default direction of revision is shorter.
- **A derived figure is its command and the tree it runs on, never a number**; **a claim about current behaviour names the probe, test, ruling, or file that shows it**, on any surface nobody goes back to correct; and a quotation is pinned to the commit it shipped at. What such a document states must survive being read later, and a paraphrase of what the tree does is a copy that can be wrong while the original is right. This cell ships the mechanism at `scripts/figures.py`; the standards are in `references/frozen-documents.md` — load it before placing any of them. **A measurement a guard also performs is that mechanism's**, never a fresh one beside it — a cell body below its frontmatter has three plausible strips and the cheapest is your own, and a figure measuring differently from the guard judging it drifts while everything stays green.

## Revising governing prose

Changing prose that already governs something carries obligations writing new prose does not — read the decision a rule cites, name every meaning change, carry a rule's reasons with it when it moves, recheck the purpose header on the way out. The standards: `references/revising.md`.

## What a cell carries

The description as the whole always-loaded triggering surface, depth leaving the body for `references/` on a disqualifier rather than a size, and self-containment with its one-owner rule, the reserved `` `<name>` cell `` form a guard answers for, and the charter's exemption in both directions, are in `references/cell-structure.md` — load it when creating or restructuring a cell, writing or revising a description, or writing prose that names or relies on another cell.

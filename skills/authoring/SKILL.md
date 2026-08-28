---
name: authoring
description: How to create and revise this practice's prose — the purpose header every governing document carries, which home each kind of content takes, what a cell owes the roster it joins, and the writing standards that keep it lean. Use when writing, restructuring or revising a skill or governing document, including a description alone or what sheds behind a pointer; when deciding where content belongs or editing an always-on surface; or when a write-up states derived figures; not for how code is written, though where such a rule belongs is here; not for reviewing finished content, and not for a pre-implementation artifact.
---

# authoring

**Purpose:** make every governing document and skill in the practice accountable to a stated job, and the figures a write-up rests on re-derivable rather than inherited. **Audience:** any session creating or revising a skill or governing document, or stating derived figures in a write-up — in this repo or a repo that adopts the practice. **Success:** every document it governs can say what it is for, who reads it, and what its review should judge it against — and contains nothing that fails that test; every skill earns what it puts in a session's context and keeps the rest behind a pointer; every figure it governs lives where it re-derives, or names the command that does.

## The purpose header

Every governing document and skill opens by answering three questions, a sentence or two each:

- **Purpose** — the job this document does; the question it answers.
- **Audience** — who reads it, and when.
- **Success** — what must be true for it to be doing its job. This is what its review judges against.

A document that cannot state these three is not ready to be written; the missing statement is its first defect. For a skill, the frontmatter `description` carries the trigger (use when / not for) and the body's opening carries the header.

## Routing — where content lives

Every piece of content has one home: methodology in a skill, a binding rule in the practice's always-on surface, rationale in a decision entry, what happened in append-only exhaust. Which one a given piece takes, and what a shipped standard owes its local application, are in `references/routing.md` — load it when the home is the question, or when editing an always-on surface, which is when outflow is owed.

## Writing standards

- **Write for the stated audience, and assume it is capable.** The purpose header names who reads this document — usually model sessions, sometimes people — and every instruction is tested against that audience, not a generic reader: ask whether the stated audience needs it, or just the goal and constraints, remembering that what trips a session is not what trips a person. Most candidate instructions fail this test and should not be written.
- **State the rule with its reason; link the evidence.** The reason is one short clause that lets a reader apply the rule well and notice when it stops applying. The evidence — counts, incidents, history — goes behind a link. Prose that litigates its own justification taxes every future reader to persuade one who is not there.
- **Do not armor against misreadings.** A clause defending against a reader who would not actually err is pure cost. If a competent reader genuinely could go wrong, restate the sentence more plainly rather than appending a qualifier to it.
- **Deletion is a first-class edit.** Propose removals with the same energy as additions. Net growth of a governing document needs a justification the way a new rule does — the default direction of revision is shorter.
- **A derived figure is its command and the tree it runs on, never a number**, and a quotation is pinned to the commit it shipped at. A document that freezes cannot be revised while the tree moves on, so what it states must survive being read later. This cell ships the mechanism at `scripts/figures.py`; the standards are in `references/frozen-documents.md` — load it before a figure goes into anything that freezes.

## Revising governing prose

Changing prose that already governs something carries obligations writing new prose does not — read the decision a rule cites, name every meaning change, carry a rule's reasons with it when it moves, recheck the purpose header on the way out. The standards: `references/revising.md`.

## What a cell carries

- **The description is the whole triggering surface, and it is always loaded.** A cell's name and description sit in every session whether or not the cell fires; the body costs nothing until it does. So the description states its triggers explicitly and in the third person, states its non-triggers wherever a sibling could be mistaken for it, and stays mutually exclusive with the roster — the failure mode is under-triggering, and siblings compete for attention that thins as the always-on set grows ([IFScale](https://arxiv.org/abs/2507.11538); and on what attached tooling costs, [MCPGauge](https://arxiv.org/abs/2508.12566)). A guard checking a description is present, parseable and inside a ceiling is the floor beneath this standard, not the standard — your practice sets that ceiling and states it where the guard lives, because a ceiling a writer cannot read is one they size by imitation.
- **Depth leaves the body when only some firings need it.** What every firing needs stays in `SKILL.md`; what one trigger among several needs sits in `references/`, behind a pointer carrying a one-line précis of what is there and when to load it. The test is a disqualifier, not a size: a cell is too big when a session loads prose it had no use for, which a small cell can do and a large one need not. A `references/` file opens with its own load condition rather than a purpose header; it is depth inside the cell, and the cell's header governs it.
- **Cells are self-contained, and a shared standard has exactly one owner.** A skill carries whatever mix of prose, scripts and tests its job needs and names no sibling cell — name one and the two must move together from then on. The charter is the exception both ways: a cell may name it and it may name any cell, because it is loaded in every session already, so the citation costs no loading and cannot drift as a second copy can. A reference is written as the cell's name, in the reserved form `` `<name>` cell `` on one line — the `charter` cell — because the name is the part that survives relocation where a path does not, though a runtime may qualify it on the way in. Reserved means what it says: write any other sense of the word unbackticked, or a guard reading the form will answer for it. **Naming a sibling to exclude it is not naming it as a pointer**: a description saying which neighbouring job is not yours creates no dependency, and states that job rather than the cell that holds it. Where two cells both need one standard it routes up to the charter, or it gets one owning cell and the other carries none of it. Two half-owners of one sentence kept in agreement by hand is never lawful: the instruction to keep copies in step is the mechanism by which they drift.

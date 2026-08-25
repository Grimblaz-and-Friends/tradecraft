---
name: authoring
description: How to create and revise content in this practice — the purpose header every governing document carries, which home each kind of content belongs in, what a skill owes the roster it joins, and the writing standards that keep prose lean enough to survive review. Use when writing or restructuring a skill or governing document, when writing or revising a skill's description, when deciding whether a skill's prose should move behind a pointer, when deciding where a piece of content belongs, when revising governing prose, or when a write-up states derived figures (test counts, sizes, deltas); not for reviewing finished content (adversarial review's job), and not for a pre-implementation artifact.
---

# authoring

**Purpose:** make every governing document and skill in the practice accountable to a stated job, and the figures a write-up states checkable rather than inherited. **Audience:** any session creating or revising a skill or governing document, or stating derived figures in a write-up — in this repo or a repo that adopts the practice. **Success:** every document it governs can say what it is for, who reads it, and what its review should judge it against — and contains nothing that fails that test; every skill earns what it puts in a session's context and keeps the rest behind a pointer; every figure it governs travels with the derivation that produced it.

## The purpose header

Every governing document and skill opens by answering three questions, a sentence or two each:

- **Purpose** — the job this document does; the question it answers.
- **Audience** — who reads it, and when.
- **Success** — what must be true for it to be doing its job. This is what its review judges against.

A document that cannot state these three is not ready to be written; the missing statement is its first defect. For a skill, the frontmatter `description` carries the trigger (use when / not for) and the body's opening carries the header.

## Routing — where content lives

- **Methodology** — how work is done, what to consider, in what order, to what standard → a skill. A piece is its own skill when it has an independent trigger: a situation where it should fire without the parent job underway. Where the trigger is not independent and a cell already serves it, it is a `references/` file inside that skill, loaded on demand. Where no cell serves it at all, the answer is a new cell — the burden sits on cramming rather than on creating.
- **Binding rules** — what must hold before any context loads → the practice's always-on surface: a shipped charter where the rule travels to every repository that adopts the practice, the repo's own root doctrine where it does not. Budget at least one of them, because a budget is what forces the routing decision to be real; treat both as the last resort, after a mechanical check and after skill prose.
- **Rationale** — why this shape was chosen, what was rejected → the repo's decision log, one frozen entry per decision, written in the change that lands it. Rationale informs future judgment; it never binds it.
- **Records** — what happened → append-only exhaust: a review report, an index row. Never create a record that must be maintained after its append.

When one idea needs both a shipped standard and a local application, the standard ships — in the skill that teaches it, or in the practice's own always-on surface where it must bind before any skill fires — and the repo's own files carry the application, never the reverse, and never duplicated prose that can drift.

## Writing standards

- **Write for the stated audience, and assume it is capable.** The purpose header names who reads this document — usually model sessions, sometimes people — and every instruction is tested against that audience, not a generic reader: ask whether the stated audience needs it, or just the goal and constraints, remembering that what trips a session is not what trips a person. Most candidate instructions fail this test and should not be written.
- **State the rule with its reason; link the evidence.** The reason is one short clause that lets a reader apply the rule well and notice when it stops applying. The evidence — counts, incidents, history — goes behind a link. Prose that litigates its own justification taxes every future reader to persuade one who is not there.
- **Do not armor against misreadings.** A clause defending against a reader who would not actually err is pure cost. If a competent reader genuinely could go wrong, restate the sentence more plainly rather than appending a qualifier to it.
- **Deletion is a first-class edit.** Propose removals with the same energy as additions. Net growth of a governing document needs a justification the way a new rule does — the default direction of revision is shorter.
- **A frozen document carries its own evidence.** It cannot be revised while the tree moves on, so what it states must survive being read later: a count travels with the query that produced it, and a quotation is pinned to the commit it shipped at. This cell ships the mechanism at `scripts/figures.py`; the standards are in `references/frozen-documents.md`.

## Revising governing prose

Changing prose that already governs something carries obligations writing new prose does not — read the decision a rule cites, name every meaning change, carry a rule's reasons with it when it moves, recheck the purpose header on the way out. The standards: `references/revising.md`.

## What a cell carries

- **The description is the whole triggering surface, and it is always loaded.** A cell's name and description sit in every session whether or not the cell fires; the body costs nothing until it does. So the description states its triggers explicitly and in the third person, states its non-triggers wherever a sibling could be mistaken for it, and stays mutually exclusive with the roster — the failure mode is under-triggering, and siblings compete for attention that thins as the always-on set grows ([IFScale](https://arxiv.org/abs/2507.11538), [tool-definition cost](https://arxiv.org/abs/2508.12566)). A guard checking a description is present, parseable and inside its length is the floor beneath this standard, not the standard.
- **Depth leaves the body when only some firings need it.** What every firing needs stays in `SKILL.md`; what one trigger among several needs sits in `references/`, behind a pointer carrying a one-line précis of what is there and when to load it. The test is a disqualifier, not a size: a cell is too big when a session loads prose it had no use for, which a small cell can do and a large one need not.
- **Code a cell carries meets the substrate's standards.** Stdlib-first Python, because one substrate is one set of idioms to harden. Tests ride beside the script they cover, so what proves the code travels with it to every consumer. Guard-shaped code is probed in both polarities — the unlawful case caught, the lawful case left alone — since a guard blocking lawful work fails as hard as one passing unlawful work. The calling contract names no harness token: a path resolved against the directory of the file naming it works both in a source repository and in an installed plugin.
- **Cells are self-contained, and a shared standard has exactly one owner.** A skill carries whatever mix of prose, scripts and tests its job needs and names no sibling cell — name one and the two must move together from then on. The charter is the exception both ways: a cell may name it and it may name any cell, because it is loaded in every session already, so the citation costs no loading and cannot drift as a second copy can. A reference is written as the cell's name — the `charter` cell — which is the handle a runtime resolves. Where two cells both need one standard it routes up to the charter, or it gets one owning cell and the other carries none of it. Two half-owners of one sentence kept in agreement by hand is never lawful: the instruction to keep copies in step is the mechanism by which they drift.

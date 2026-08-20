---
name: authoring
description: How to create and revise content in this practice — the purpose header every governing document carries, which home each kind of content belongs in, and the writing standards that keep prose lean enough to survive review. Use when writing or restructuring a skill or governing document, when deciding where a piece of content belongs, or when revising governing prose; not for reviewing finished content (that is adversarial review's job).
---

# authoring

**Purpose:** make every document in the practice accountable to a stated job. **Audience:** any session creating or revising content, in this repo or a repo that adopts the practice. **Success:** every document it governs can say what it is for, who reads it, and what its review should judge it against — and contains nothing that fails that test.

## The purpose header

Every governing document and skill opens by answering three questions, a sentence or two each:

- **Purpose** — the job this document does; the question it answers.
- **Audience** — who reads it, and when.
- **Success** — what must be true for it to be doing its job. This is what its review judges against.

A document that cannot state these three is not ready to be written; the missing statement is its first defect. For a skill, the frontmatter `description` carries the trigger (use when / not for) and the body's opening carries the header.

## Routing — where content lives

- **Methodology** — how work is done, what to consider, in what order, to what standard → a skill. A piece becomes its own skill only when it has an independent trigger: a situation where it should fire without the parent job underway. Otherwise it is a `references/` file inside the skill it serves, loaded on demand.
- **Binding rules** — what must hold before any context loads → the repo's root doctrine. The doctrine is budgeted, so adding means displacing; treat it as the last resort, after a mechanical check and after skill prose.
- **Rationale** — why this shape was chosen, what was rejected → the repo's decision log, one frozen entry per decision, written in the change that lands it. Rationale informs future judgment; it never binds it.
- **Records** — what happened → append-only exhaust: a review report, an index row. Never create a record that must be maintained after its append.

When one idea needs both a shipped standard and a local application, the skill carries the standard and the repo's own files carry the application — never the reverse, and never duplicated prose that can drift.

## Writing standards

- **Write for the stated audience, and assume it is capable.** The purpose header names who reads this document — usually model sessions, sometimes people — and every instruction is tested against that audience, not a generic reader: ask whether the stated audience needs it, or just the goal and constraints, remembering that what trips a session is not what trips a person. Most candidate instructions fail this test and should not be written.
- **State the rule with its reason; link the evidence.** The reason is one short clause that lets a reader apply the rule well and notice when it stops applying. The evidence — counts, incidents, history — goes behind a link. Prose that litigates its own justification taxes every future reader to persuade one who is not there.
- **Do not armor against misreadings.** A clause defending against a reader who would not actually err is pure cost. If a competent reader genuinely could go wrong, restate the sentence more plainly rather than appending a qualifier to it.
- **Deletion is a first-class edit.** Propose removals with the same energy as additions. Net growth of a governing document needs a justification the way a new rule does — the default direction of revision is shorter.
- **Cells are self-contained.** A skill carries whatever mix of prose, scripts, and tests its job needs, depends on no other skill, and keeps its depth in its own `references/`. Anything else couples cells and breaks the one-loading story.

## Revising governing prose

- **Read the cited decision first.** Where a rule carries a decision citation, read that entry before changing the rule — then supersede it knowingly. The entry is input to your judgment, never a veto: if current behavior is wrong, the original reasoning probably was too.
- **Name every meaning change where amendments are recorded** — the decision entry, or the PR body where no entry is warranted. A silent meaning change, including a sentence left verbatim while a term it turns on is redefined, is the defect an amendment review exists to catch; do not make it find yours.
- **When rules move between documents, their reasons move with them** — or the change states that reasons are being dropped, and why. A migration that carries rules alone strands the clause a later reader needs to know when a rule stops applying, and the stranding is invisible afterward: the rule reads complete. Naming the drop is a lawful answer; silence is not, and asserting compliance is not either — the change names the reasons it carried or the ones it left.
- **A home is where knowledge compounds — in the artifact that uses it, not beside it.** A skill's lessons travel with the skill, to every machine, runtime, and consumer; that is the property that makes the routing above a closed list rather than an illustrative one, and the test any proposed new home has to pass.
- **Recheck the purpose header on the way out.** If the revision changed what the document is for or who reads it, the header moves in the same change — a stale success criterion misaims every future review of the document.

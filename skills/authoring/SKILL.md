---
name: authoring
description: How to create and revise content in this practice — the purpose header every governing document carries, which home each kind of content belongs in, and the writing standards that keep prose lean enough to survive review. Use when writing or restructuring a skill or governing document, when deciding where a piece of content belongs, when revising governing prose, or when a write-up states derived figures (test counts, sizes, deltas); not for reviewing finished content (that is adversarial review's job), and not for a pre-implementation artifact.
---

# authoring

**Purpose:** make every governing document in the practice accountable to a stated job, and the figures a write-up states checkable rather than inherited. **Audience:** any session creating or revising a skill or governing document, or stating derived figures in a write-up — in this repo or a repo that adopts the practice. **Success:** every document it governs can say what it is for, who reads it, and what its review should judge it against — and contains nothing that fails that test; every figure it governs travels with the derivation that produced it.

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

When one idea needs both a shipped standard and a local application, the skill carries the standard and the repo's own files carry the application — never the reverse, and never duplicated prose that can drift.

## Writing standards

- **Write for the stated audience, and assume it is capable.** The purpose header names who reads this document — usually model sessions, sometimes people — and every instruction is tested against that audience, not a generic reader: ask whether the stated audience needs it, or just the goal and constraints, remembering that what trips a session is not what trips a person. Most candidate instructions fail this test and should not be written.
- **State the rule with its reason; link the evidence.** The reason is one short clause that lets a reader apply the rule well and notice when it stops applying. The evidence — counts, incidents, history — goes behind a link. Prose that litigates its own justification taxes every future reader to persuade one who is not there.
- **Do not armor against misreadings.** A clause defending against a reader who would not actually err is pure cost. If a competent reader genuinely could go wrong, restate the sentence more plainly rather than appending a qualifier to it.
- **Deletion is a first-class edit.** Propose removals with the same energy as additions. Net growth of a governing document needs a justification the way a new rule does — the default direction of revision is shorter.
- **Pin a frozen document's evidence to the commit it shipped at.** A document that cannot be revised freezes while the tree keeps moving, so an unpinned quotation goes stale silently and a later reader cannot tell whether the citation was wrong or the file changed under it. Leave one unpinned only where your practice repairs references whose targets move; nothing repairs them by default.
- **A frozen document carrying counts carries the query that produced them.** It freezes with its arithmetic inside, so the query is the difference between a figure a later session can check and one it can only inherit. This cell ships the mechanism: `scripts/figures.py` derives the recurring figures — suite count, a document's size against its budget, prose delta against a named base — each printed with its basis and the tree it was measured on, so a write-up pastes the block instead of improvising the arithmetic. Derive figures there rather than by hand; and where the repository wraps this engine with its own parameters and repo-bound figures, prefer that wrapper — it is what keeps a figure agreeing with the guard that judges it. A figure needing a caller decision (the delta's base) must be given explicitly; the script refuses to pick a basis silently, because a silently chosen basis is how stated numbers diverge from checkable ones. The script sits beside this file at `scripts/figures.py`; invoke it by that path resolved against the directory this file is in, which is what makes one contract hold both in an installed plugin and in the source repository.
- **Cells are self-contained.** A skill carries whatever mix of prose, scripts, and tests its job needs, depends on no other skill, and keeps its depth in its own `references/`. Anything else couples cells and breaks the one-loading story.

## Revising governing prose

- **Read the cited decision first.** Where a rule carries a decision citation, read that entry before changing the rule — then supersede it knowingly. The entry is input to your judgment, never a veto: if current behavior is wrong, the original reasoning probably was too.
- **Name every meaning change where amendments are recorded** — the decision entry, or the PR body where no entry is warranted. A silent meaning change, including a sentence left verbatim while a term it turns on is redefined, is the defect an amendment review exists to catch; do not make it find yours.
- **When rules move between documents, their reasons move with them** — or the change states that reasons are being dropped, and why. A migration that carries rules alone strands the clause a later reader needs to know when a rule stops applying, and the stranding is invisible afterward: the rule reads complete. Naming the drop is a lawful answer; silence is not, and asserting compliance is not either — the change names, where amendments are recorded, the reasons it carried or the ones it left.
- **A home is where knowledge compounds — in the artifact that uses it, not beside it.** A skill's lessons travel with the skill, to every machine, runtime, and consumer; that is also the test any proposed new home has to pass.
- **Recheck the purpose header on the way out.** If the revision changed what the document is for or who reads it, the header moves in the same change — a stale success criterion misaims every future review of the document.

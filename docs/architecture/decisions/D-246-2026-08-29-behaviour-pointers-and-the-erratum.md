# D-246: A behaviour claim on a surface nobody corrects names its demonstrator, and a falsified frozen claim gains an erratum

**Status:** Accepted 2026-08-29 (PR #246)

## Context

[#242](https://github.com/Grimblaz-and-Friends/tradecraft/issues/242) and [#243](https://github.com/Grimblaz-and-Friends/tradecraft/issues/243) are two remedies for one defect class: a sentence that is wrong and cannot be fixed. They landed together on the settled [pre-implementation artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/242#issuecomment-5465977553), [affirmed](https://github.com/Grimblaz-and-Friends/tradecraft/issues/242#issuecomment-5466238759) with both owner decisions ruled.

**Why one change.** They meet in one sentence of `skills/authoring/references/frozen-documents.md` — its closing paragraph licenses an unpinned reference only "where your practice repairs references whose targets move", which is the freeze exception appearing inside the standard #243 extends. They also defer the same question from opposite ends: #243 defers where description stops and rationale begins, and #242 scopes its clause to a claim falsified by evidence the entry itself cites — a set that is close to the same set, because rationale has no demonstrator and cannot be falsified by a later tree at all. Drawn once they interlock. [D-167](D-167-2026-08-25-behavior-claims-carry-a-probe.md) is the precedent for landing two issues in one change to avoid opening one paragraph twice.

## 1. The standard's scope is what nobody goes back to correct, not the figure rule's list

[D-194](D-194-2026-08-25-figures-re-derive-at-read-time.md) put derived figures on surfaces that re-derive them; this extends the same move to behaviour claims, and **deliberately does not inherit that rule's list of surfaces.**

The two rules turn on different properties. The figure rule reaches what **nobody re-derives at read time**. This one reaches what **nobody goes back to correct**. The lists overlap but neither contains the other, and they separate in both directions. A **comment beside code** is in the figure rule and not this one, for a portability reason that rule states itself — it travels with the code, so a fixed tree named in it is false everywhere else — which has no analogue for a behaviour claim. An **append-only record** is in this one and not the figure rule, and it is the surface with no repair path at all.

A future session reading the two adjacent paragraphs will be tempted to unify the lists. **That is the undo this entry exists to prevent.** A code comment can be edited, so a wrong sentence in it is repaired by an ordinary fix and needs no errata path; and describing what the code does is frequently the exact thing its reader needs, where a pointer to a test would be worse prose. The cost of the pointer is only worth paying where the sentence cannot be repaired.

Irreducible rationale stays prose for a reason that is not taste: the decision, the alternatives rejected, and the why have no demonstrator to name, and cannot be falsified by a later tree — only superseded, which is what a new entry is for.

## 2. The marker is lawful under the test the repoint already passes

The log's existing permission is licensed as one edit that changes no claim [D-135]. A correction plainly changes a claim, so the clause could have read as breaking the freeze. It does not, because of how the shape divides the work: **the in-place `[corrected]` marker changes no claim, and the appended Erratum block — which is new text, not an edit — carries the change.** Claim-neutrality, not byte-immutability, is already this log's test.

The owner ruled the shape against two alternatives. A footer-only block leaves the reader who believes the wrong sentence and acts on it never reaching the correction, which is the harm being fixed. Striking in place rewrites the body, and an entry accumulating strikes stops reading as what was decided at the time.

## 3. The bounds, each against a specific failure

- **The falsifier must be the entry's own.** Otherwise the clause becomes supersession-by-erratum: any later tree could be cited to rewrite an old entry's conclusions, which is exactly the amendment the freeze exists to bar. The entry has to have been wrong when it landed, by what it already carried.
- **Judgment is out of reach.** A correction repairs a description of what the tree does. Reversal stays a new entry.
- **It rides with other work.** A pull request whose only content is errata is the tripwire. Stated on its own authority: the records rule names *record bookkeeping* and enumerates the jsonl files and the pre-reset archive, so it does not reach the live log, and its remedy — delete the record it books — has no meaning applied to an erratum.
- **No sweep.** The permission is for a falsified sentence met in the course of other work. A mandate to audit the log would create a record that must be maintained, which routing forbids outright.

The index row moves in the same change where the corrected sentence is what it summarises, because the row is the only route from a decision's number to its reasoning — `check_decision_index` in `tools/lint.py` is what states that job, and a row left wrong misroutes.

## 4. The outflow: one move, one refusal

The `authoring` description grew, so the always-on surface owed an outflow. `AGENTS.md` drops "when in doubt, ask the cheap question" — a rule leaving for a home that already holds it verbatim, `skills/charter/SKILL.md`'s convergence paragraph. Its Decisions line separately generalises to "the two narrow repairs" rather than enumerating, which is shorter than what it replaced.

**Compressing the CRLF fact to its `[D-186]` citation was considered and refused.** That entry's ruling 5 places the fact in `AGENTS.md` deliberately, because the moment it must be found is mid-task, when a session notices CRLF and has no reason to open the decision log. [D-225](D-225-2026-08-29-values-ranking-adopted.md) refused the same compression on the same ground; this is the second time that candidate has been raised and declined, which is itself worth recording so a third outflow does not spend the search again.

Re-derive by running `python tools/figures.py` on a tree at `a1cdba4` and on this one, and differencing the *always-on surface* line. **Not `--base`**, whose delta is over governing prose, a different corpus — [D-225](D-225-2026-08-29-values-ranking-adopted.md) already records that it does not answer this question, and this entry named it anyway for one revision.

## 5. Rejected

- **[D-135]'s rejection of this remedy, superseded knowingly.** That entry's Rejected list names it twice: *"Errata by appendix — an append-only dated errata section on landed entries. This is the amendment disease with a new name; an errata section is where an argument grows"*, and *"A general correction category. 'Correction' cannot be bounded — every fuzzy edge widens under pressure."* Both are answered by the same thing: **the bounds**. D-135's objection is to an *unbounded* correction category, and it drew the distinction itself — an act can be bounded where a category cannot. The falsifier must be the entry's own, judgment is out of reach, the repair rides with other work, and no sweep is licensed; the growth D-135 priced is what the last two bar. The owner ruled the shape without these two rejections in front of them, and affirmed the supersession once shown.
- **Decision entries only**, as the standard's reach. The recorded ground is that such a scope has no principled property behind it — it names a document type where the shipped rule names a property, and a rule keyed to a type cannot say what a new surface belongs to. Adjacency was *not* the ground: this entry holds two paragraphs apart in one file are fine where each names its own property, which is exactly what shipped.
- **The figure rule's list wholesale**, which is how the option was first put to the owner and was wrong: it inherited members assembled on mixed grounds without re-deriving why.
- **Reopening the figure rule** to disentangle the two senses of "freezes" across that whole file. The new paragraph states its own narrower scope beside it instead. Tidying a landed rule's wording is scope drift, and the conflation costs a reader nothing once each paragraph names its own property.
- **A guard on the erratum's shape.** A labelled block's three parts are checkable; whether a correction is *lawful* — whether the cited evidence really falsifies the sentence — is judgment no guard reaches. A check that verified the cheap half would read as verifying the expensive one.

## 6. The clause landed with no live customer

D-231, the entry from the review terminus that prompted both filings, records the incomplete-fixture defect it shipped through in its own text. A spot check of its behaviour sentences found none falsified by evidence it cites — that check is the ground, not the self-record, which would not entail it. **The warrant is the base rate, not a sentence anyone can point at today:** four consecutive prose-repair batches each reproduced the class they repaired in that one review, and the terminating-batch exemption [D-96] guarantees the last batch is unprosecuted wherever the terminus is drawn. A future session should not read the absence of errata as evidence the clause was unnecessary; it should read the first erratum as the clause working.

The standard is in `skills/authoring/references/frozen-documents.md` and `skills/authoring/SKILL.md`; the clause in `docs/architecture/decisions/README.md`; the always-on line and the outflow in `AGENTS.md`. [D-135](D-135-2026-08-23-repointed-reference.md) carries the repoint permission, its claim-neutrality test, and the two rejections §5 supersedes; [D-141](D-141-2026-08-23-figures-are-derived.md) and [D-194](D-194-2026-08-25-figures-re-derive-at-read-time.md) the figure rule this extends; [D-167](D-167-2026-08-25-behavior-claims-carry-a-probe.md) behaviour claims carrying probes inside a review, and the two-issues-one-change precedent; [D-96](D-96-2026-08-20-post-fix-terminus.md) the terminating-batch exemption; [D-186](D-186-2026-08-25-windows-text-mode-defaults.md) ruling 5 the refused compression.

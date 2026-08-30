# D-246: A behaviour claim on an unrevisable surface names its demonstrator, and a falsified frozen claim gains an erratum

**Status:** Accepted 2026-08-29 (PR #246)

## Context

[#242](https://github.com/Grimblaz-and-Friends/tradecraft/issues/242) and [#243](https://github.com/Grimblaz-and-Friends/tradecraft/issues/243) are two remedies for one defect class: a sentence that is wrong and cannot be fixed. They landed together on the settled [pre-implementation artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/242#issuecomment-5465977553), [affirmed](https://github.com/Grimblaz-and-Friends/tradecraft/issues/242#issuecomment-5466238759) with both owner decisions ruled.

**Why one change.** They meet in one sentence of `skills/authoring/references/frozen-documents.md` — its closing paragraph licenses an unpinned reference only "where your practice repairs references whose targets move", which is the freeze exception appearing inside the standard #243 extends. Whichever landed first, the second would reopen the other's paragraph. They also defer the same question from opposite ends: #243 defers where description stops and rationale begins, and #242 scopes its clause to a claim falsified by evidence the entry itself cites — a set that is close to the same set, because rationale has no demonstrator and cannot be falsified by a later tree at all. Drawn once they interlock. [D-167](D-167-2026-08-25-behavior-claims-carry-a-probe.md) is the precedent for landing two issues in one change to avoid opening one paragraph twice.

## 1. The standard's scope is revisability, not the figure rule's list

[D-194](D-194-2026-08-25-figures-re-derive-at-read-time.md) put derived figures on surfaces that re-derive them; this extends the same move to behaviour claims, and **deliberately does not inherit that rule's list of surfaces.**

The two rules turn on different properties. The figure rule reaches what **nobody re-derives**. This one reaches what **nobody may revise**. The lists overlap but are not the same, and the member that separates them is the comment beside code: it sits in the figure rule for a portability reason the rule states itself — it travels with the code, so a fixed tree named in it is false everywhere else — which has no analogue for a behaviour claim.

A future session reading the two adjacent paragraphs will be tempted to unify the lists. **That is the undo this entry exists to prevent.** A code comment can be edited, so a wrong sentence in it is repaired by an ordinary fix and needs no errata path; and describing what the code does is frequently the exact thing its reader needs, where a pointer to a test would be worse prose. The cost of the pointer is only worth paying where the sentence cannot be repaired.

Irreducible rationale stays prose for a reason that is not taste: the decision, the alternatives rejected, and the why have no demonstrator to name, and cannot be falsified by a later tree — only superseded, which is what a new entry is for.

## 2. The marker is lawful under the test the repoint already passes

The log's existing permission is licensed as one edit that changes no claim [D-135]. A correction plainly changes a claim, so the clause could have read as breaking the freeze. It does not, because of how the shape divides the work: **the in-place `[corrected]` marker changes no claim, and the appended Erratum block — which is new text, not an edit — carries the change.** Claim-neutrality, not byte-immutability, is already this log's test.

The owner ruled the shape against two alternatives. A footer-only block leaves the reader who believes the wrong sentence and acts on it never reaching the correction, which is the harm being fixed. Striking in place rewrites the body, and an entry accumulating strikes stops reading as what was decided at the time.

## 3. The four bounds, each against a specific failure

- **The falsifier must be the entry's own.** Otherwise the clause becomes supersession-by-erratum: any later tree could be cited to rewrite an old entry's conclusions, which is exactly the amendment the freeze exists to bar. The entry has to have been wrong when it landed, by what it already carried.
- **Judgment is out of reach.** A correction repairs a description of what the tree does. Reversal stays a new entry.
- **It rides with other work.** A pull request whose only content is errata is the tripwire the records rule already names.
- **No sweep.** The permission is for a falsified sentence met in the course of other work. A mandate to audit the log would create a record that must be maintained, which routing forbids outright.

The index row moves in the same change where the corrected sentence is what it summarises, because the row is the only route from a decision's number to its reasoning — `check_decision_index` in `tools/lint.py` is what states that job, and a row left wrong misroutes.

## 4. The outflow: one move, one refusal

The `authoring` description grew, so the always-on surface owed an outflow. `AGENTS.md` drops "when in doubt, ask the cheap question" — a rule leaving for a home that already holds it verbatim, `skills/charter/SKILL.md`'s convergence paragraph. Its Decisions line separately generalises to "the two narrow repairs" rather than enumerating, which is shorter than what it replaced.

**Compressing the CRLF fact to its `[D-186]` citation was considered and refused.** That entry's ruling 5 places the fact in `AGENTS.md` deliberately, because the moment it must be found is mid-task, when a session notices CRLF and has no reason to open the decision log. [D-225](D-225-2026-08-29-values-ranking-adopted.md) refused the same compression on the same ground; this is the second time that candidate has been raised and declined, which is itself worth recording so a third outflow does not spend the search again.

Re-derive the surface with `python tools/figures.py --base a1cdba4`: it is net smaller than at the merge base despite the grown description.

## 5. Rejected

- **Decision entries only**, as the standard's reach — it would sit directly beneath a broader list in the same file, and two adjacent scopes is a defect the day it lands.
- **The figure rule's list wholesale**, which is how the option was first put to the owner and was wrong: it inherited members assembled on mixed grounds without re-deriving why.
- **Reopening the figure rule** to disentangle the two senses of "freezes" across that whole file. The new paragraph states its own narrower scope beside it instead. Tidying a landed rule's wording is scope drift, and the conflation costs a reader nothing once each paragraph names its own property.
- **A guard on the erratum's shape.** A labelled block's three parts are checkable; whether a correction is *lawful* — whether the cited evidence really falsifies the sentence — is judgment no guard reaches. A check that verified the cheap half would read as verifying the expensive one.

## 6. The clause landed with no live customer

D-231, the entry from the review terminus that prompted both filings, records the incomplete-fixture defect it shipped through in its own text, so no falsified sentence survives in it. **The warrant is the base rate, not a sentence anyone can point at today:** four consecutive prose-repair batches each reproduced the class they repaired in that one review, and the terminating-batch exemption [D-178] guarantees the last batch is unread wherever the terminus is drawn. A future session should not read the absence of errata as evidence the clause was unnecessary; it should read the first erratum as the clause working.

## References

`skills/authoring/references/frozen-documents.md` and `skills/authoring/SKILL.md` for the standard; `docs/architecture/decisions/README.md` for the clause; `AGENTS.md` for the always-on line and the outflow. [D-135](D-135-2026-08-23-repointed-reference.md) for the repoint permission and its claim-neutrality test, [D-141](D-141-2026-08-23-figures-are-derived.md) and [D-194](D-194-2026-08-25-figures-re-derive-at-read-time.md) for the figure rule this extends, [D-167](D-167-2026-08-25-behavior-claims-carry-a-probe.md) for behaviour claims carrying probes inside a review and for the two-issues-one-change precedent, [D-178](D-178-2026-08-25-fix-batch-buys-a-second-run.md) for the terminating-batch exemption, [D-186](D-186-2026-08-25-windows-text-mode-defaults.md) ruling 5 for the refused compression.

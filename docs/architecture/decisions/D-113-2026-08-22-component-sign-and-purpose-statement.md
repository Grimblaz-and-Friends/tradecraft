# D-113: The price's sign attaches to the obligation, and the purpose statement is defined where it is first used

**Status:** Accepted 2026-08-22 (PR #113)

## Context

Two clauses in `skills/adversarial-review/SKILL.md`, in different paragraphs, sharing no term and no clause. They land together because they are one file, one panel, one cost record and one version bump — not because they are one idea. [D-90](D-90-2026-08-20-dispatch-contract.md) and [D-97](D-97-2026-08-21-dispatch-contract-restated.md) warn against bundling, and that warning is about welding several decisions into **one sentence**, which is what produced five versions of `:41` in a day. Two sentences that do not touch are a different shape, and the artifact argued the distinction before the gate rather than after.

### `:65` — the sign clause ([#111](https://github.com/Grimblaz-and-Friends/tradecraft/issues/111))

[D-107](D-107-2026-08-22-price-is-implementation-cost.md) defined price as implementation cost in two named parts and then asserted a sign in a standalone sentence: *"A remedy that removes a rule or guard prices negative."* The first part names **regression surface**, which is never negative and can be large — a rule cited at *n* sites forces *n* edits, `:58`'s own arithmetic. The second priced the remedy's **total**. So an expensive deletion read as free, clause (b) answered *"worth it"* trivially, and it would be sustained and fixed without its cost weighed.

**The base clause did not have this shape.** It made the sign one property of one named component — *"its complexity delta — whether the remedy adds a rule, guard, or standing prose…, or removes one."* D-107 promoted a component property to a standalone predicate while rewriting the definition around it. The promotion was not the subject of that change and is not recorded there as a choice.

**PR #107's round one priced this out as armor** — `authoring`'s rule that *"A clause defending against a reader who would not actually err is pure cost"* — reasoning that a reader would have to ignore the immediately preceding clause. **The premise was falsified inside the same PR.** An external automated reviewer, reading only the diff against `b0cd8a3` with no access to the review, produced exactly that reading unprompted: that the categorical sentence *"makes the whole remedy's price negative"* and *"can make the terminal stage approve a costly or risky deletion on a false price."* The armor rule turns on whether the reader errs; this one did. That is new evidence about value under D-107's own time-invariance test, and PR #107's cycle-1 terminal stage vacated its own price-out on it.

**It was routed rather than fixed there for three reasons, all of them about that moment.** A terminating ruling's fix batch takes no prosecution look (`:71`'s own exemption), so a shipped-zone edit to that sentence would have landed unreviewed; `authoring`'s no-armor rule directs the remedy to a *restatement* rather than the proposed qualifier, making it larger than a `+3`; and any `:65` edit invalidates every cost figure in D-107, in a batch that reviews nothing. All three evaporate in a change with a normal review attached.

### `:14` — the purpose statement ([#101](https://github.com/Grimblaz-and-Friends/tradecraft/issues/101))

`:14` required a review to begin from *purpose, audience, and success criteria*; `:41`'s assignment enumerated *purpose statement* alone. A dispatcher building from the contract could satisfy it carrying only a purpose sentence, and the recipient would then judge fitness — `:20`'s whole question — against a criterion set it never received. Raised by an external reviewer on PR #97 and sustained on independent grounds in that review's external-pass reconciliation, then routed because the enumeration is verbatim from the pre-change text and outside that change's affirmed boundary.

**#101 records that nothing in the shipped zone settles which reading is intended.** Reading every occurrence settles it. The term appears three times in the shipped zone, all in this file — `:16`, `:41`, `:79` — and `:16` reads *"the audience the artifact's purpose statement names."* A bare purpose sentence names no audience. **The file already used the term in the wide sense; what was missing is that nothing said so**, and a dispatcher reading `:41` alone got the narrow one.

## Decision

**Two restatements, no new rule, no new mechanism, no new stage.**

1. **`:65`'s sign becomes a component property again, by grammar.** *"the cost of implementing it, in two terms: what the fix touches (its regression surface), and what it obliges later sessions to do, **a term that goes negative** where the remedy removes a rule or guard."* One sentence instead of two; *in two terms* makes the price a sum; the sign is an appositive on the second term.
2. **`:14` defines the term it has always used.** *"Every review begins from the artifact's **purpose statement** — its stated purpose, audience, and success criteria."* All three uses resolve from it.
3. **Both lines cite this entry**; `:65` carries `[D-107] [D-113]`, on D-97's precedent that a lone citation routing to a frozen entry whose warnings concern deleted text strands the reader.

**Why an appositive and not a relative pronoun.** *"which goes negative"* would have been shorter and is the construction this file cannot afford. `:41`'s five versions in one day turned on exactly this: `each` reached only the predecessor outputs by nearest antecedent, `both` could not distribute over a non-pair, and `itself` could bind to `evidence standards`. D-97's remedy was to remove the pronouns rather than choose better ones. *"a term that"* names its own antecedent by category, so there is nothing for a later editor to tidy and nothing for nearest-antecedent to strand.

**Why a restatement and not the qualifier.** The proposed fix in the routed issue was *"prices negative on that obligation"* — three words appended. `authoring` is explicit that where a competent reader genuinely could go wrong the remedy is to *"restate the sentence more plainly rather than appending a qualifier to it"*, and the reader here demonstrably did go wrong. A qualifier would also have left the standalone sentence standing, which is the thing that reads as a total.

**The `{rule, guard}` narrowing survives, and is restated here because the sentence that carried it is gone.** D-107 records deliberately that the base clause reached `{rule, guard, standing prose}` and its landed clause reached `{rule, guard}` — prose removal no longer prices negative, because prose's cost of *existing* is not a price under the implementation-cost definition. That narrowing lived in the sentence this change rewrites and in D-107's prose. The restatement does not readmit prose, and a future editor reading only this entry still learns the exclusion and its reason.

**The addition side is left asymmetric, as D-107 left it.** A remedy that adds a rule or guard reaches the price only through what it obliges later sessions to do; D-107 rejected symmetrising the clause because it restores a cost channel against every guard-adding remedy in a repo whose admission order puts a mechanism first. Nothing here disturbs that, and *in two terms* does not imply symmetry between them.

**`:41` is not edited, and that is the decision rather than an omission.** Enumerating there — `purpose statement` → `purpose, audience and success criteria` — was the shape the routed issue proposed and the owner declined it. It would leave `:16` and `:79` on an undefined term while one site spelled it out, which is term drift inside one file and the exact defect `revision-diff` exists to catch. It would also open the paragraph with the worst amendment record in the repo for a defect a definition closes without touching it. #101 anticipated the ranking: *"a definition is cheaper than an enumeration."*

**The definition is local and duplicates nothing.** `skills/authoring` defines a **purpose header** as the same three fields, and cells are self-contained — no skill may reference another. This entry does not import that definition; it states what this file's own term denotes, which is a fact about this file. Had the fix instead restated `authoring`'s header prose here, it would be the duplicated prose that can drift that `authoring` forbids.

**Neither item is a widening.** `:14` already bound every review to three fields; the definition changes no obligation, it makes an existing one reachable from `:41` and `:79`. `:65`'s total was never intended to be signed; D-107's own Deferred section records the promotion as a defect the day it landed.

**Cost, derived from the finished tree by `wc -w` after the fix batch, and recorded here as a fact:**

| line | before | after | delta |
| --- | --- | --- | --- |
| `:14` | 50 | 55 | **+5** |
| `:65` | 134 | 141 | **+7** |
| file | 2833 | 2845 | **+12** |

**Two of those twelve words are the `[D-113]` citation tokens**, one per line. No estimate was published before the bytes existed — see below.

**The artifact carried a forecast and it was struck before any commit.** As first posted, the pre-implementation artifact led its cost section with `+9 standing words` and a projected before-and-after. The owner caught it and asked why counting was still the reflex one day after D-107 demoted it. The objection is sustained: the figure was compliant with `engagement`'s new rule — outside the numbered criteria, labelled a fact — and would still have propagated to every seat, because `:41` carries the assignment **whole** and the artifact *is* the assignment. That is the path D-107 records for #91's criterion 5 and for its own criterion 7, with only the typographic position changed. It also broke `:57` on its face: a count over a corpus the change writes into is a query, not a number, and this one was forecast before the corpus existed.

**Two issues came out of that, and both are outside this change's boundary.** [#112](https://github.com/Grimblaz-and-Friends/tradecraft/issues/112) carries the container defect — *outside the numbered criteria* is not *outside the shared block*. [#115](https://github.com/Grimblaz-and-Friends/tradecraft/issues/115) carries the root cause the owner asked for: a price has two named terms and only one can be computed, so every rule that demotes counting is refilled by the vacuum it leaves. Four recurrences across three changes, three fixes, all of them placement or wording.

## Rejected

- **Enumerating at `:41`.** Above. Owner's decision, argued with pros and cons at the gate.
- **Leaving `:101`'s gap alone.** Defensible: `:14` binds every review already, `:16` demonstrates the wide reading, and every dispatch in PR #97's own review carried full acceptance criteria. Declined because that is evidence about what dispatchers do, not about what the contract requires — the distinction [#94](https://github.com/Grimblaz-and-Friends/tradecraft/issues/94) is this repo's worked example of.
- **The `+3` qualifier at `:65`** — *"prices negative on that obligation."* Barred by `authoring`'s second limb once the reader is shown to err.
- **A relative pronoun instead of the appositive.** Shorter, and the construction that cost `:41` five versions.
- **Symmetrising the sign clause.** D-107's rejection stands and is not relitigated.
- **A boundary clause saying regression surface still counts on a removal.** That is armor by D-107's own reasoning, and it is what a restatement exists to make unnecessary. If a reader still reaches the total-sign reading under the appositive, the evidence is the finding — see below.
- **Amending `:16` or `:79` to spell the three fields out.** The definition reaches them. Spelling them out at three sites is the enumeration remedy multiplied.
- **Amending the frontmatter `description`.** D-107's reasoning holds unchanged: it carries the trigger, and a triggering string has a cross-repo regression surface untestable in this review.
- **Publishing a cost estimate in the artifact.** Struck at the owner's instruction; see above and #112.

## Deferred, with the evidence that would reopen them

- **Whether the appositive holds against a reader who has not read this entry.** The whole ground for the restatement is that one competent reader reached the total-sign reading; nothing proves the new wording closes it for the next one. **Reopen on:** any stage or external reviewer reading `:65` as signing a remedy's total, or pricing a removal without its regression surface.
- **`:41` still enumerates a term rather than the fields.** The definition at `:14` is upstream of it and a dispatcher who reads the contract without the charter is outside every reading of this file. **Reopen on:** a dispatch carrying a purpose sentence and no success criteria, or a recipient reporting it judged fitness against a criterion set it did not receive.
- **`purpose statement` has no definition outside this file.** A repo adopting the practice takes the skill and gets it; a repo writing its own artifacts does not. `authoring`'s purpose header is the same three fields under a different name, and cells cannot reference each other. **Reopen on:** a consumer repo where the two terms drift apart in use.
- **Nothing verifies that `[D-113]` resolves.** Two more citation tokens ship under the gap [#109](https://github.com/Grimblaz-and-Friends/tradecraft/issues/109) already carries; `[D-999]` passes lint and the full suite. **Reopen on:** #109 landing, or a bad citation shipping.
- **The count habit is not addressed here.** This change struck one forecast and filed two issues. The habit has now recurred four times across three changes and every remedy so far has been placement or wording. **Reopen on:** nothing — #112 and #115 are open work, not declined findings.

## Evidence

[#111](https://github.com/Grimblaz-and-Friends/tradecraft/issues/111) and [#101](https://github.com/Grimblaz-and-Friends/tradecraft/issues/101); the [pre-implementation artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/111#issuecomment-5383697708) carrying both items and its [affirmation record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/111#issuecomment-5383747792) with the owner's one amendment. [D-107](D-107-2026-08-22-price-is-implementation-cost.md) for the price definition, the `{rule, guard}` narrowing, the rejected symmetrisation, and the Deferred entry naming #111 as this work's vehicle; PR #107's [round-one ruling](https://github.com/Grimblaz-and-Friends/tradecraft/pull/107#issuecomment-5382133381) (the price-out), its [external-pass reconciliation](https://github.com/Grimblaz-and-Friends/tradecraft/pull/107#issuecomment-5382187333), and its [cycle-1 ruling](https://github.com/Grimblaz-and-Friends/tradecraft/pull/107#issuecomment-5382381186) (the vacatur); Codex's inline comment on `SKILL.md:65` against `b0cd8a3`. [D-97](D-97-2026-08-21-dispatch-contract-restated.md) and [D-90](D-90-2026-08-20-dispatch-contract.md) for `:41`'s amendment record, the pronoun failures, and the two-token citation form. `skills/authoring`'s no-armor rule, its no-drift rule, and its purpose header; `skills/adversarial-review/SKILL.md` at `:14`, `:16`, `:20`, `:41`, `:57`, `:58`, `:65`, `:71`, `:79`. [#112](https://github.com/Grimblaz-and-Friends/tradecraft/issues/112) and [#115](https://github.com/Grimblaz-and-Friends/tradecraft/issues/115) for what the struck estimate exposed.

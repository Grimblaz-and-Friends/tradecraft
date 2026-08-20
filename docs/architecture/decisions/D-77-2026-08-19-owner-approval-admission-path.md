# D-77: Owner approval is a second path onto the admission road

**Status:** Accepted 2026-08-19 (PR #77)

## Context

[D-74](D-74-2026-08-19-constitutional-reset.md) put a brake on the road that had been producing law faster than the practice could absorb it: *"Agent-proposed rules need an incident from real work — a review finding about governing prose is not an incident."* The brake works. Within hours of the reset it disqualified [PR #66](https://github.com/Grimblaz-and-Friends/tradecraft/pull/66) outright — four statute rules whose entire exhibit set was findings about governing prose, produced by two full review pipelines that ruled 78 findings without touching the product.

The edge is what [#70](https://github.com/Grimblaz-and-Friends/tradecraft/issues/70) had already measured: two shipped skills against roughly 292KB of governance, and the structural version stated in that issue's own words — the one finding the instrument cannot produce is whether the practice makes real engineering work better, *"because almost none has run through it."* Against that state the clause does not narrow the road for an agent-proposed rule; it **closes** it until product work exists. Anything a session notices before then has no admissible route at any material, including the cheap ones the ladder prefers.

The owner raised this on reading the reset, in conversation on 2026-08-19, and stated the remedy in the same breath.

## Decision

The admission road gains a second path: an agent-proposed rule is admitted by an incident from real work **or by the owner's specific approval of that rule**.

Three things about the shape.

**"Specific" is the load-bearing word.** The path admits *this* rule, named, at the moment of approval. It is not a licence a session can claim afterwards from a general remark in an earlier conversation — which is the failure that would turn one path into no brake at all.

**It sits inside the existing sentence rather than beside it.** The road stays one sentence a session reads in one pass. A second bullet would present two roads as alternatives of equal standing; they are not — the incident road is the default and this one is the exception the owner reaches for.

**No new recording obligation ships with it.** The doctrine already routes owner decisions through the convergence gate, which records the affirmation on the issue before the first commit. A second obligation to record the approval separately would reintroduce exactly the maintenance-bearing bookkeeping D-74 deleted.

The brake itself is untouched: the incident standard, the *"a review finding about governing prose is not an incident"* exclusion, the cheapest-reliable-material ladder, and the budget-displacement rule all stand unchanged.

**This entry's own change is exercised immediately.** The same pull request lands one sentence in `skills/authoring/SKILL.md` saying what a pre-implementation artifact's boundary statement is for. That sentence has no incident from real work behind it — its evidence is five filings about governing prose — and it is admitted on this path, on the owner's specific approval recorded on [#76](https://github.com/Grimblaz-and-Friends/tradecraft/issues/76). It is the first use of the path, and recording that here is what lets a later session see which road the line came in on.

## Rejected

- **Leaving the road as D-74 wrote it.** Defensible while the docket fills with product work, and the honest cost is that a real defect noticed in the meantime has nowhere lawful to go, at any material. The owner declined it.
- **A general owner licence** — "the owner may waive the incident requirement." One approval would then admit a class of rules, and the brake would hold only as long as nobody read it broadly.
- **Widening the incident standard itself** — counting findings about governing prose after all. That is the loop D-74 was built to break, and reopening it costs the whole reset.
- **A recorded-approval obligation** distinct from the affirmation record. Bookkeeping with a maintenance surface, against D-74's tripwire rule.
- **Carrying PR #66's surviving finding in on this path** — that boundary statements, what-statements and acceptance criteria are all read as walls. Declined on the merits, not on admissibility: the review charter holds that a possible misreading is a finding only where the stated audience plausibly would misread, and the authoring skill names armor against misreadings as pure cost. What is worth keeping is telling an author what the field is *for*, which is the sentence that landed.

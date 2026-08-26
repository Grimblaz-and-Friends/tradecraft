---
name: adversarial-review
description: Adversarial review of an artifact against its stated purpose — a differentiated panel (or a single cold pass for routine changes), an evidence-bound defense that prices each remedy, a terminal stage that weighs value against price, and executable post-fix re-validation. Use when a change is ready for review, when deciding review depth for an artifact, or when deciding whether another pass is worth running; not for choosing what to build, and not for committing and pushing the fixes afterward.
---

# adversarial-review

**Purpose:** find the defects that matter and only those, by prosecution under evidence rules. **Audience:** the session dispatching a review, and every seat, defense, and judge it dispatches. **Success:** the review answers one question — *is the artifact fit for its stated purpose?* — with every ruling traceable to evidence, and leaves the artifact no larger than that answer requires.

**Pause discipline: typed-halt.** From first dispatch to final ruling the pipeline is atomic — no questions mid-run, no interim fixes, no edits to the artifact under review. A finding that needs an owner decision is surfaced in the final report as exactly that, argued: the live options, each with pros and cons, and a recommendation among them. Safe in attended and unattended lanes alike.

## The charter — purpose first

Every review begins from the artifact's **purpose statement** — its stated purpose, audience, and success criteria [D-113]; for an implementation, its success criteria are the affirmed acceptance criteria on its issue. Where no statement exists, that absence is the review's first finding, and the review proceeds against the best statement the dispatching session can supply, recorded in the report.

- **A finding names the success criterion it impairs, for the stated audience.** "A reader might misread this" is a finding only if the stated audience plausibly would — the audience the artifact's purpose statement names, judged by that audience's own failure modes. Governing prose — prose a later session is expected to act on — is mostly read by model sessions, sometimes by the owner, and the two do not stumble in the same places: a session over-obeys stale text and follows references literally where a person skims and asks. A true observation that impairs no criterion is dismissed at the terminal stage without ceremony.
- **Deletions have equal standing with additions.** Any seat may propose that text or code be removed, held to the same evidence standards; on governing prose, net growth is itself a finding, and the burden of argument sits on keeping the words.
- **The terminal ruling is about the artifact, not the finding count**: fit for purpose, fit once the named fixes land, or not fit. Fit-for-purpose can be the ruling while true findings stand unfixed.

## Choosing the shape

- **Routine change**: one adversarial pass that reads the artifact **cold** (its index row books under `cold-read`), then defense — the terminal stage on this lane — then executable re-validation of fixes.
- **Substantial artifact** (newly written foundational prose, new scripts, high blast radius — and when in doubt, this lane): the four-seat panel, then defense, then judge, then re-validation. Width beyond four is bought by declared risk.
- **The report records which lane was chosen and why, in one line** — an unrecorded shape choice can never be audited later.

Why a panel and not one strong pass: seats find largely different defects. In the predecessor's attributed record (116 sustained findings across six rounds), a single pass kept 12% of the sustained yield, the best seat chosen with hindsight kept 46%, the fourth seat's marginal yield stayed real, and the fifth's went thin — four is the measured width ([the mining record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/1)). That basis is the predecessor's, contested on this repository's own record and due for recomputation once the reports carry finders [D-185].

## The pipeline, and where each stage's depth lives

Every stage is held to the charter above and the evidence standards below. Each stage's own machinery is one hop away, and the pointer says when to open it — a session on one step of the pipeline has no use for the rest.

- **Staffing a panel, or any review role** → `references/roster.md`: the four slots and the fifth name, the cold boundary operationally, and which tier each role gets.
- **Building a dispatch** → `references/dispatch.md`: the three parts in order, what a dispatch read cold does not receive, and which roles take no dispatcher's note.
- **Merging findings, defending, or ruling as the terminal stage** → `references/arbitration.md`: the merge's ownership and the consequence shape it records, the defense's verdicts and the price it states, and the terminal stage's docket and two clauses.
- **A fix batch that has landed, or an open pull request** → `references/after-the-fix.md`: the post-fix look's scope, the two conditions that end the cycle, and every external comment's disposition.
- **Closing the review** → `references/the-record.md`: what the final report carries, the next-pass ruling, the relevance terminus, and the index row with its counting conventions.

## Evidence standards — every seat, every stage

- **A finding states a concrete failure mode** and quotes the exact line or names the exact artifact, with the probe command where one was run — the defense must be able to re-run it. **It names the concrete consequence of standing unfixed** — the action a consumer of the artifact would take wrongly, or the failure that would occur — which is what every stage after it routes on, stated by the finder rather than inferred downstream from the finding's wording, which is what makes the routing auditable. Coverage-first: report everything with a statable failure mode; the filter is the terminal stage, never the prosecutor's nerve.
- **A load-bearing claim requires the check that would falsify it**; a claim that only carries understanding is held to honesty, not precision. A claim is load-bearing if a reader would act differently were it false, or if it is a rule's sole support. Load hides in absence claims, universals, superlatives, and counts — check those first.
- **A behavior claim is a hypothesis until a probe answers it** [D-167] — what a reader does under a wording, whether a mechanism fires, what using the result is like. It binds every stage and not the finder alone: a defense contesting behavior commissions the probe rather than arguing it, and no ruling sustains or dismisses a behavior claim on argument alone where a probe is cheap. **Severity is reached too**, because a high against governing prose whose harm claim is behavioral is settleable, where a probe is cheap, before a fix cycle is priced on it; a high in the executable class — a red lint, a guard that cannot fail — arrives with its probe and is not re-probed. Where a session note reports use of the artifact, **it outranks panel hypothesis on behavior and on nothing else** — on reasoning these standards rule unchanged.
- **An absence claim is discharged by reading to the end of the artifact**, not to the end of the section that should have contained the thing. Say what was read, not only what was searched for.
- **A new test pin must go red against the pre-fix revision** — a green suite proves nothing about the defect. **Probe a guard in both polarities**: the unlawful change caught, and the lawful change left alone; a guard that blocks lawful work fails as hard as one that passes unlawful work. **A probe must also be shown to answer the question it is credited with** — by a negative control drawn from the probe's own class, demonstrating it would have reported differently had the answer been different; a control outside that class can pass while the probe stays masked. A probe that reports a result it never took is *trusted*, which argument at least is not: [a size-preserving mutation masked by stale bytecode reported SURVIVES for a guard it never broke](https://github.com/Grimblaz-and-Friends/tradecraft/issues/142), and a defense published the false result.
- **Derive a correction from its source; never adjust a wrong claim until it looks right.** Re-run the query or re-read the passage at fix time and write what it returns. A count over a corpus the change itself writes into is a query, not a number. Land the fix where the claim is *read* as well as where it is written.
- **A fix changes the state the finding was diagnosed in** — re-derive the diagnosis and its probe against the tree the fix produces; a probe re-run unchanged answers the pre-fix question. A fix that reaches *n* sites creates *n* more to check, including sites the fix itself introduces.
- **Severity is a claim too**, and it measures harm-if-unfixed; the remedy's price is its separate half, and neither absorbs the other.

## Closing a recurring class

When the same defect class returns — across findings, reviews, or repos — the fix is never another seat: it is a **promoted lens**, worded so it would have caught the class's own motivating exemplar, carried in these evidence standards or a seat's brief. Seats catch instances; lenses retire classes.

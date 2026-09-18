---
name: adversarial-review
description: Adversarial review of an artifact against its stated purpose — a differentiated panel (or a cold pass for routine changes), an evidence-bound defense, a terminal stage and an executable floor. Use when a change is ready for review, when deciding review depth for an artifact, when dispositioning what an automated reviewer posted on a pull request or what a review tool you invoked returned, or when deciding whether another pass is worth running; not for choosing what to build, and not for committing and pushing the fixes afterward.
---

# adversarial-review

**Purpose:** find the defects that matter and only those, by prosecution under evidence rules. **Audience:** the session dispatching a review, every review role it dispatches, the implementer taking its fixes, and any session deciding what a finding met outside a review earns. **Success:** the review answers one question — *is the artifact fit for its stated purpose?* — with every ruling traceable to evidence, and leaves the artifact no larger than that answer requires.

**Pause discipline: typed-halt.** From first dispatch to final ruling the pipeline is atomic — no owner questions mid-run, no interim fixes, no edits to the artifact under review. A finding that needs an owner decision is surfaced in the final report as exactly that, argued.

Ownership of the unattended stretch, role separation and judging-seat staffing are the `engagement` cell's. On work owing no implementation brief, the review's dispatcher performs the coordination duties assigned here to the holder; the independent review roles remain separate from the author.

## The charter — purpose first

Every review begins from the artifact's **purpose statement** — its stated purpose, audience, and success criteria [D-113]; for an implementation, its success criteria are the settled acceptance criteria on its issue. Where no statement exists, that absence is the review's first finding, and the review proceeds against the best statement the dispatching session can supply, recorded in the report.

- **A finding names what goes wrong, for the stated audience.** "A reader might misread this" is a finding only if the stated audience plausibly would — the audience the artifact's purpose statement names, judged by that audience's own failure modes. Governing prose — prose a later session is expected to act on — is mostly read by model sessions, sometimes by the owner, and the two do not stumble in the same places: a session over-obeys stale text and follows references literally where a person skims and asks. **Impairing a stated criterion is not the test of a finding**: criteria say what a change is for, not everything that must be true of the tree it produces, so most real defects contradict none of them.
- **Deletions have equal standing with additions.** Any seat may propose that text or code be removed, held to the same evidence standards; on governing prose, net growth is itself a finding, and the burden of argument sits on keeping the words.
- **The terminal ruling is about the artifact, not the finding count**: fit for purpose, fit once the named fixes land, or not fit. Fit-for-purpose can be the ruling while true findings stand unfixed.

## The pipeline, and where each stage's depth lives

**A review is one round** — every stage the chosen lane names and the fix batch, once each — and what reads the result after it is use, not a further pass: [a bounded trial, scored](https://github.com/Grimblaz-and-Friends/tradecraft/issues/360) [D-371]. Every stage is held to everything in this file.

- **Choosing the shape a review takes, or deciding what depth an artifact buys** → `references/the-shape.md`: the two lanes and the stages each runs in order, what buys the panel and what buys a seat beyond it, and which lane runs where the choice is unclear.
- **Staffing a panel, or any review role** → `references/roster.md`: the seats and what each looks for, their capability map, what the width rests on, what a review withholds from a cold seat, and where a model advantage is concentrated.
- **Building a dispatch** → `references/dispatch.md`: what the shared block is for and why it is byte-identical, what a dispatch read cold does not receive, and what isolation is for every recipient.
- **Merging findings, defending, ruling as the terminal stage, or deciding what a finding met outside a review earns** → `references/arbitration.md`: the merge's ownership and consequence shape, the defense's verdicts and remedy price, and the independent terminal stage that buys, pitches or lapses each offer against the affirmed implementation brief.
- **Writing a review's fix batch, discharging what it owes once it has landed, an open pull request an automated reviewer may have posted on, or a review tool you invoked yourself** → `references/after-the-fix.md`: the three evidence standards that bind at fix time, the executable floor the batch owes, the use that reads the result, every external comment's disposition, and the commissioned pass.
- **Closing the review or writing the dispatches whose output the report reads** → `references/the-record.md`: what the final report and the index row are for, where each is posted, and what the row may not carry.
- **The same defect class returning across findings, reviews or repositories, or a standing instruction to look that may have outlived it** → `references/lenses.md`: why a returning class is closed by a lens rather than by another seat, how one is worded and where it is carried, the two grounds any standing instruction retires on, and what the report names.
- **Writing the dispatch itself** → `references/dispatch-template.md`: its fields.
- **Writing the final report itself** → `references/report-template.md`: its fields.
- **Appending the index row itself** → `references/index-row-template.md`: its keys and spellings.

## Evidence standards — every seat, every stage

- **A finding states a concrete failure mode** and quotes the exact line or names the exact artifact, with the probe command where one was run — the defense must be able to re-run it. **It names the concrete consequence of standing unfixed** — the action a consumer of the artifact would take wrongly, or the failure that would occur — which is what every stage after it routes on, stated by the finder rather than inferred downstream from the finding's wording, which is what makes the routing auditable. Coverage-first: report everything with a statable failure mode; the filter is the terminal stage, never the prosecutor's nerve.
- **A load-bearing claim requires the check that would falsify it**; a claim that only carries understanding is held to honesty, not precision. A claim is load-bearing if a reader would act differently were it false, or if it is a rule's sole support. Load hides in absence claims, universals, superlatives, and counts — check those first. **Two records are held to honesty whatever the load.** The **change's own** — decision entry, pull request body, commit message, index row — is a finding where a claim is false, not where one is imprecise: what ships is what a later session acts on, while these are read once beside the change [D-371]. The **review's own** — the merged list and the report — is not a subject at all, a retired lens. **Neither reaches the pre-implementation artifact or the implementation brief it carries**, which an implementer builds from and every stage judges against.
- **A behavior claim is a hypothesis until a probe answers it** [D-167] — what a reader does under a wording, whether a mechanism fires, what using the result is like. It binds every stage and not the finder alone: a defense contesting behavior runs the probe or returns the execution need to the holder rather than arguing it, and no ruling sustains or drops a behavior claim on argument alone where a probe is cheap. Where a session note reports use of the artifact, **it outranks panel hypothesis on behavior and on nothing else** — on reasoning these standards rule unchanged.
- **A stage unable to run a required check returns that need, not a ruling on it.** The holder checks execution needs before dispatch, supplying evidence or naming the gap, and re-dispatches a stage that returned one freshly, with the evidence, to finish the same round. Unavailable execution stays an explicit verification gap, never counter-evidence.
- **An absence claim is discharged by reading to the end of the artifact**, not to the end of the section that should have contained the thing. Say what was read, not only what was searched for.
- **Severity is a claim too**, and it measures harm-if-unfixed; the remedy's price is its separate half, and neither absorbs the other.

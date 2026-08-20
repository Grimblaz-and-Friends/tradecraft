---
name: adversarial-review
description: Adversarial review of an artifact against its stated purpose — a differentiated panel (or a single cold pass for routine changes), an evidence-bound defense that prices each remedy, a terminal stage that weighs value against price, and executable post-fix re-validation. Use when a change is ready for review, when deciding review depth for an artifact, or when deciding whether another pass is worth running; not for choosing what to build, and not for committing and pushing the fixes afterward.
---

# adversarial-review

**Purpose:** find the defects that matter and only those, by prosecution under evidence rules. **Audience:** the session dispatching a review, and every seat, defense, and judge it dispatches. **Success:** the review answers one question — *is the artifact fit for its stated purpose?* — with every ruling traceable to evidence, and leaves the artifact no larger than that answer requires.

**Pause discipline: typed-halt.** From first dispatch to final ruling the pipeline is atomic — no questions mid-run, no interim fixes, no edits to the artifact under review. A finding that needs an owner decision is surfaced in the final report as exactly that, argued: the live options, each with pros and cons, and a recommendation among them. Safe in attended and unattended lanes alike.

## The charter — purpose first

Every review begins from the artifact's stated purpose, audience, and success criteria; for an implementation, the affirmed acceptance criteria on its issue. Where no statement exists, that absence is the review's first finding, and the review proceeds against the best statement the dispatching session can supply, recorded in the report.

- **A finding names the success criterion it impairs, for the stated audience.** "A reader might misread this" is a finding only if the stated audience plausibly would — the audience the artifact's purpose statement names, judged by that audience's own failure modes. Governing prose — prose a later session is expected to act on — is mostly read by model sessions, sometimes by the owner, and the two do not stumble in the same places: a session over-obeys stale text and follows references literally where a person skims and asks. A true observation that impairs no criterion is dismissed at the terminal stage without ceremony.
- **Deletions have equal standing with additions.** Any seat may propose that text or code be removed, held to the same evidence standards; on governing prose, net growth is itself a finding, and the burden of argument sits on keeping the words.
- **The terminal ruling is about the artifact, not the finding count**: fit for purpose, fit once the named fixes land, or not fit. Fit-for-purpose can be the ruling while true findings stand unfixed.

## Choosing the shape

- **Routine change**: one adversarial pass that reads the artifact **cold** (its index row books under `cold-read`), then defense — the terminal stage on this lane — then executable re-validation of fixes.
- **Substantial artifact** (newly written foundational prose, new scripts, high blast radius — and when in doubt, this lane): the four-seat panel, then defense, then judge, then re-validation. Width beyond four is bought by declared risk.
- **The report records which lane was chosen and why, in one line** — an unrecorded shape choice can never be audited later.

Why a panel and not one strong pass: seats find largely different defects. In the predecessor's attributed record (116 sustained findings across six rounds), a single pass kept 12% of the sustained yield, the best seat chosen with hindsight kept 46%, the fourth seat's marginal yield stayed real, and the fifth's went thin — four is the measured width ([the mining record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/1)).

## The roster — four slots, five names

Three seats stand; the fourth is chosen by the artifact's shape. Seats differ or they are waste: a seat is added for a lens or vantage the panel lacks, never for a second pass at one it has. A **vantage** is where a seat reads from — cold, briefed, or as the consumer; a **lens** is what it is told to look for. What a dispatch prompt could have said is a lens, not a vantage.

- **`cold-read`** — fresh vantage, no lens brief: forms its own view of the artifact before any prior findings exist for it. A brief aims attention, and aimed attention has a shadow; this seat is what falls in it.
- **`wiring-falsifier`** — scripts and contracts: does the code enforce what the prose claims, does anything call it, can each guard actually fail? Probe by execution, not reading.
- **`operational`** — walk the artifact as its consumer: a fresh executor following the text, reporting where it under-determines or misleads action.
- **The fourth seat, by shape:** **`claims-vs-evidence`** on substantially new prose — verify every load-bearing claim, number, and quotation against its cited source; also the default when no shape fits. **`revision-diff`** on amendments to governing prose — report every load-bearing sentence whose *meaning* changed without the change being recorded (in the decision entry where one exists, else the PR body), including the sentence whose characters never changed while a term it turns on was redefined elsewhere in the change; the unit of comparison is the governing claim, not the diff hunk, so its read scope is the whole change. When the artifact is both shapes, both seats sit and the panel is five. A needed lens the roster lacks — `security` on a write path or trust boundary, `position` when the artifact builds on an unreviewed design (review the earlier artifact first; position beats depth) — takes the shape slot or widens the panel by declared risk, named in the report.

**The cold boundary, operationally**: the cold seat's dispatch carries the assignment and none of the review's history: no prior findings, no self-review, no conversation context, and not the PR's comment thread, which carries another party's findings within seconds of the PR opening. A cold seat is therefore always a fresh dispatch, never the session that authored or discussed the artifact.

## The dispatch contract

**Every dispatch is built in three parts, in this order.** The **shared block** first and nothing before it, byte-identical across every recipient at that stage: the assignment — artifact location, diff base, purpose statement, output format, evidence standards — and every predecessor stage's output whole, each carried verbatim or by link, never the dispatcher's paraphrase. Then a **dispatcher's note** where there is one, labeled as such and additive; the seat stage takes none, because a cold vantage sits there and aimed attention is what that vantage is defined against. Last the recipient's own identity, lens brief, and working location where it differs — the only per-recipient content. **Calling attention is lawful; filtering and restating are not.** An author compressing its own charter is an interested-party summary, and where the dispatching session is the author, one that retypes the assignment per recipient decides one recipient at a time what gets reviewed; one literal string cannot drift.

**Independence extends to every role**: defense and judge are staffed like seats — never the artifact's author, and the judge never a finder. In a single-session lane, all review roles are dispatches, not the authoring session reviewing itself.

**Seats that mutate the tree get their own worktree.** Mutation testing, red-probes, anything that writes: dispatch it isolated, or concurrent readers see files change underneath them mid-review.

## Staffing

Every seat runs at the strongest model tier the runtime's budget bears. Where the top tier is scarce, concentrate it where open-ended perception lives — the `cold-read` — and where single dispatches carry the most leverage — the judge. Terminal stages run at least the seats' reasoning effort. The report records which model and runtime staffed each seat, so per-runtime evidence can accumulate.

## Evidence standards — every seat, every stage

- **A finding states a concrete failure mode** and quotes the exact line or names the exact artifact, with the probe command where one was run — the defense must be able to re-run it. Coverage-first: report everything with a statable failure mode; the filter is the terminal stage, never the prosecutor's nerve.
- **A load-bearing claim requires the check that would falsify it**; a claim that only carries understanding is held to honesty, not precision. A claim is load-bearing if a reader would act differently were it false, or if it is a rule's sole support. Load hides in absence claims, universals, superlatives, and counts — check those first.
- **An absence claim is discharged by reading to the end of the artifact**, not to the end of the section that should have contained the thing. Say what was read, not only what was searched for.
- **A new test pin must go red against the pre-fix revision** — a green suite proves nothing about the defect. **Probe a guard in both polarities**: the unlawful change caught, and the lawful change left alone; a guard that blocks lawful work fails as hard as one that passes unlawful work.
- **Derive a correction from its source; never adjust a wrong claim until it looks right.** Re-run the query or re-read the passage at fix time and write what it returns. A count over a corpus the change itself writes into is a query, not a number. Land the fix where the claim is *read* as well as where it is written.
- **A fix changes the state the finding was diagnosed in** — re-derive the diagnosis and its probe against the tree the fix produces; a probe re-run unchanged answers the pre-fix question. A fix that reaches *n* sites creates *n* more to check, including sites the fix itself introduces.
- **Severity is a claim too**, and it measures harm-if-unfixed; the remedy's price is its separate half, and neither absorbs the other.

## Merge, defense, and the terminal stage

**Merge — parent-owned, before defense.** The dispatching session merges the seats' findings: a duplicate is the same failure mode at the same location; a merged finding credits every finder, primary (first-surfacing) first. A seat that fails or returns unusable output is re-dispatched once; a panel still short proceeds, and the report records the degraded width. Zero findings from all seats is a valid outcome.

**Defense — one pass, always.** Presume the artifact innocent; read every cited line independently; re-run every probe a finding rests on; challenge only with concrete counter-evidence. Verdict per finding: **disproved**, **conceded**, or **insufficient-to-disprove**, with the evidence for each. The defense may originate findings its re-runs surface and may move severity with evidence. **For every finding it does not disprove, it states the remedy's price**: what the fix touches (its regression surface) and its complexity delta — whether the remedy adds a rule, guard, or standing prose every later reader pays for, or removes one. Argued, never scored. Stating a price is not arguing a drop; a defense that declines a finding on cost without a priced-out ruling on the record has suppressed it. Where a defense verdict can be settled by running something, run it.

**The terminal stage's docket is set by rule, not by the dispatcher**: every merged finding, every defense verdict, and every collision or open matter any stage flagged. Matters the dispatcher wants settled arrive as a labeled note on that docket, never as the docket. **The terminal stage** — the judge on panels, the defense on routine reviews — applies two clauses per finding. **(a) Would acting on this improve the artifact against its stated purpose?** No → dismiss, saying which criterion was looked for and not found; still unclear after verification → dismiss. **(b) Is that improvement worth the remedy's price?** Yes → **sustain and fix**. No → **sustain and price out**: the finding was real, and the report records it with the price that declined it — never silently dropped. Rules: verify independently before sustaining (re-read the cited artifact, re-execute contested probes, state what was verified); defer to no party — reject conceded findings and raise argued-down severity where the evidence says so; settle severity and price at the evidence, not the average of positions; one ruling per merged finding, no rebuttal rounds. **Post the rulings to the PR or issue before the fix batch begins** — a ruling that lives only in a session cannot be read by the stage that follows it.

## Post-fix re-validation — mandatory, executable, fix-wide

Fixes are a defect source comparable to fresh diffs, and the repair that reproduces the class it closes is what this look most often finds. Run everything that runs — suites, lint, and the findings' own probes re-derived against the fixed tree. Scope to everything the fix touched, the review's own bookkeeping included: the merged finding list, the report, the commit message, and the PR body. Post the report before writing the index row that cites it. **Every fix batch gets at least one prosecution look, plus defense on anything it finds — ruled by the review's terminal stage — and that floor is never priced away.** The cycle ends when a look's findings are all dismissed or all priced out — it turns on what findings are worth, not on a clean look, which the record shows is an asymptote.

## The external pass — reconciled every time

Automated reviewers configured on the repository post on a PR without being asked, so publishing before the panel makes their pass concurrent rather than serial. Reconcile after the terminal stage and before the fix batch; reconcile again if a push triggered a re-review, which reads the fixes and so checks the fix batch independently of the post-fix look above. Every comment gets a disposition: duplicate of an internal finding (named as such), sustained and fixed, sustained and priced out with the price, or dropped on the evidence with a one-line reason. **Sustain on independent grounds or not at all** — an external reviewer's cited rule may not be one this repo runs; where the repo's own convention contradicts it, the convention wins and the drop says so. Record that the pass ran even when it produced nothing, and treat what actually posted as the input, never the roster — configured reviewers stub, rate-limit, and skip.

## Ending the review

The final report, posted to the PR or issue, carries: the lane and why; the purpose statement judged against; per-seat counts (raw / merged / sustained, highs broken out), with each seat's model and runtime; every finding's disposition, with each drop's one-line reason and each priced-out ruling's price; the external pass's outcome; the terminal fitness ruling; and the **next-pass ruling** — run or stop. The default is stop once a pass has sustained no high it will fix; continuing argues the next pass is worth its cost, and stopping names the residual risk accepted and what is expected to catch it instead. A run ruling binds the session that wrote it: dispatch the pass before closing, or record why not.

Where the repo keeps a review index, append one row per review — date, artifact, lane, per-seat counts, report URL — written once and never maintained. Before reading what such a record says, ask what it could have said: an evidence loop whose instrument cannot express the finding it tests for is not evidence, and a counts-only record is silent about everything its fields do not carry. A seat that ran and found nothing appears with zeros; a seat that failed unreplaced is omitted, with the report recording the degraded width. Where the repo keeps no index, the report alone is the record.

## Closing a recurring class

When the same defect class returns — across findings, reviews, or repos — the fix is never another seat: it is a **promoted lens**, worded so it would have caught the class's own motivating exemplar, carried in these evidence standards or a seat's brief. Seats catch instances; lenses retire classes.

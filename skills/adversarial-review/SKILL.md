---
name: adversarial-review
description: Adversarial review of a changeset or artifact — a differentiated four-seat panel (or single cold pass for routine changes), an evidence-bound defense, an evidence-verifying judge, and executable post-fix re-validation. Use when a change is ready for review, when deciding review depth for an artifact, or when a review finding needs defense or judgment; not for choosing what to build (that is design work) and not for committing and pushing the fixes afterward (landing changes is its own activity with its own guards).
---

# adversarial-review

Review as prosecution under evidence rules: seats hunt defects, a defense tries to disprove them, a judge rules on what survives, and the fixes are then re-validated by execution. The shape scales with the artifact; the evidence standards never do.

This skill never asks a question mid-pipeline: from the first seat's dispatch to the judge's ruling the pipeline is atomic — no interim fixes, no edits to the artifact under review, no engagement prompts. A finding that needs an owner decision is surfaced in the judge's report as exactly that (and recorded with disposition `owner-pending` where a defect ledger exists — that row is its durable home, resurfaced by the opening step below, never a filed follow-up), and the report is where the pipeline stops. Safe in attended and unattended lanes alike.

## Choosing the shape

In this skill's home repo, ADR-006 owns the default and this skill executes it; in any other repo, the shape rules below stand on their own, and sustained findings' attribution goes wherever that repo records defects — or stays in the review report when nowhere else exists.

- **Open the ledger first.** Where a defect ledger exists, read it before choosing the shape: it carries the de-escalation evidence, the accumulated seat yield, and any `owner-pending` rows — batch those open rows into one argued question, put it at this review's opening seam, and re-disposition to `recorded` (with a one-line reason) any that several reviews have now failed to get answered.
- **Routine change**: one adversarial pass that reads the artifact **cold**, then defense, then executable re-validation of any fixes. Defense's evidence verdicts terminate — no separate judge; the defense is the filter for this lane.
- **Substantial artifact** (newly written foundational prose, new scripts, high blast radius — and when in doubt, this lane: going below the default is bought only by ledger evidence, never by argument): the **four-seat differentiated panel** below, then defense, then judge, then executable re-validation. Width beyond four, or an additional external fresh-session reviewer, is bought by declared risk.
- **Record the classification.** The review report states which lane was chosen and why in one line — an unrecorded shape choice can never be audited or de-escalated later.

Why a panel and not one strong pass: seats find largely different defects, so one pass keeps a minority of what a panel finds and drops criticals with it — and the strongest seat is a different seat each time, so it cannot be picked in advance. Marginal yield is still real at the fourth seat and thin at the fifth, which is where the default sits. Evidence: [the seat-yield record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/1).

## The default roster — four seats

Seats differ or they are waste; these four names are also the canonical `found_by` values (with the stages: `defense`, `judge`, `post-fix`, `external`, `ci`):

- **`cold-read`** — fresh vantage, no lens brief: forms its own view of the artifact before any prior findings exist for it. A brief aims attention, and aimed attention has a shadow; this seat is what falls in it. Exhibit: [#922](https://github.com/Grimblaz/agent-orchestra/issues/922).
- **`claims-vs-evidence`** — for prose: verify every load-bearing claim, number, and quotation against its cited source. Newly written prose is where defects concentrate, because every fresh sentence is an unchecked claim. Exhibit: [#844](https://github.com/Grimblaz/agent-orchestra/issues/844).
- **`wiring-falsifier`** — for scripts and contracts: does the code enforce what the prose claims, does anything call it, can each guard actually fail? Probe by execution, not reading.
- **`operational`** — walk the artifact as its consumer: a fresh executor following the text, reporting where it under-determines or misleads action. A panel reads the artifact; only this seat runs it, which is a different question and finds a different class. Exhibit: [#878](https://github.com/Grimblaz/agent-orchestra/issues/878).

**Substitution, not silence**: a write path or trust boundary earns a `security` seat; an artifact built on an unreviewed design earns a `position` seat (review the earlier artifact first — ADR-006's position axis, the stronger escalation). Swaps and additions are recorded in the review report, and a swapped-in seat's name enters `found_by` as used.

**Differentiation axes**, strongest first: vantage (cold vs briefed vs consumer), lens family, position. **No clone seats** — a seat is added for a lens or vantage the panel lacks, not for a second pass at one it has. A judgment, not a measurement: redundancy is not worthless, but differentiation is the lever the record measures, and agreement between same-lens passes reads as confirmation when it is only correlation. Exhibit: [#882](https://github.com/Grimblaz/agent-orchestra/issues/882). Revisable in either direction by what `found_by` accumulates.

**The cold boundary, operationally**: the cold seat's dispatch carries the assignment (artifact location, diff base, output format, evidence standards) and none of the review's history — no prior findings, no self-review, no earlier ledgers, no conversation context. Those four exclusions are the auditable rule; a cold seat must therefore be a fresh dispatch, never the session that authored or discussed the artifact.

**Independence extends to every role**: defense and judge are staffed like seats — never the artifact's author, and the judge never a finder. In a single-session lane this means all review roles are dispatches, not the authoring session reviewing itself.

## Staffing and effort

Every seat runs at the strongest model tier its runtime's budget bears; **the bottom tier does not seat by default** — a budget judgment, not a measured cliff: the cheapest seat underperformed wherever it was attributed, and tier parity below the top was never tested at all. Where the top tier is scarce, concentrate it where open-ended perception lives — the `cold-read` — and where a single dispatch carries the most leverage — the judge of a foundational review. Revisable in either direction by what `found_by` accumulates; on a runtime where the top tier is not scarce, this collapses to "top tier everywhere." Evidence: [the seat-yield record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/1).

Reasoning effort: terminal stages (defense, judge) run at least the seats' effort, escalated where the runtime offers it; width escalations are governed by the panel rules above, never by effort settings — orchestration scale and per-dispatch reasoning are different levers and are not exchanged for one another.

*Dated example (2026-08, demotable per ADR-002 — an application of the rule, never the rule):* on Claude Code here, `cold-read` runs Fable, briefed seats and defense run Opus (defense one effort step up), the judge runs Opus at max — Fable for constitution-touching reviews; on a flat-budget runtime (e.g. Codex today), top tier throughout. The tier evidence is Claude-family only; the review report records which runtime and model staffed each seat so per-runtime evidence can accumulate alongside the rows (`source` itself stays the review-event key, per the constitution's ledger contract).

## Evidence standards — every seat, every stage

- **A finding states a concrete failure mode** and quotes the exact line or names the exact artifact, with the probe command where one was run — defense must be able to re-run it. Coverage-first: report everything with a statable failure mode, including low-severity and uncertain items; omission is reserved for items with no statable failure mode at all. The filter is the terminal stage — the judge on panels, the defense on routine reviews — never the prosecutor's nerve.
- **An absence claim, a universal, a superlative, or a count requires the check that would falsify it** — run it before the sentence ships, or hedge to what the record supports. Exhibits: [#882](https://github.com/Grimblaz/agent-orchestra/issues/882), [PR #2](https://github.com/Grimblaz-and-Friends/tradecraft/pull/2).
- **A new test pin must go red against the pre-fix revision.** Green suites prove nothing about the defect — a full suite passes with the defect live. Exhibit: the predecessor's [review-exhibits](https://github.com/Grimblaz/agent-orchestra/blob/main/skills/adversarial-review/references/review-exhibits.md).
- **A check is only as good as what it reads**: confirm a guard reads the artifact that ships, and mutate the guarded property to see the check fail. A checker with no caller is prose wearing a script's clothes.
- **Hold a remedy to the standard it enforces**, and re-read a correction's own source before writing the correction. A repair reproduces the class it closes often enough to check for by default: a regrade that declares a real record nonexistent, a quote repair that ships a freshly spliced quote, a crash fix applied at one call site while its twin sits untouched beside it. Exhibits: [PR #2](https://github.com/Grimblaz-and-Friends/tradecraft/pull/2), the predecessor's [review-exhibits](https://github.com/Grimblaz/agent-orchestra/blob/main/skills/adversarial-review/references/review-exhibits.md).
- **Severity is a claim too.** Overstated severity is a defect the defense can strike, and inflation is the commoner direction: a finding that reads as critical buys attention the evidence has not paid for.

## Merge — parent-owned, before defense

The parent (the dispatching session) merges the seats' ledgers before defense sees them: a duplicate is the **same failure mode at the same location**; the merged finding keeps **every finder** (primary first — the primary is the projection a defect-ledger row carries, per the constitution's `found_by` contract), and dual credit is preserved in the review report. The defense receives the merged ledger plus access to the artifact; the judge receives the merged ledger, the defense report, and access to the artifact — both must be able to re-execute any probe a verdict rests on.

**Error states**: a seat that fails or returns unusable output is re-dispatched once; a panel still short a seat after retry proceeds, and the report records the degraded width. Zero findings from all seats is a valid outcome — the defense has nothing to examine, the report says so, and no defect rows are written.

## Defense — one pass, always

Presume the artifact innocent; read every cited line independently; re-run every probe a finding rests on; challenge only with concrete counter-evidence. Verdict per finding: **disproved**, **conceded**, or **insufficient-to-disprove** — with the evidence for each. The defense may also originate findings its re-runs surface — re-running a probe reaches code no seat read — and may move severity with evidence.

Defense is what makes width safe: a wide panel without it ships its own noise. Its verdicts fail in one characteristic way — a confident disproof aimed at the wrong mechanism, exonerating a real defect — so where a verdict can be settled by running something, run it. Exhibit: [PR #950](https://github.com/Grimblaz/agent-orchestra/pull/950).

## Judge — panel reviews only, single-shot

The judge's test per finding: **will acting on this improve the artifact?** Yes → sustain; no → dismiss; still unclear after verification → dismiss ("Uncertainty is not a deferral bucket" — the predecessor's judgment skill, verbatim). Rules:

- **Verify independently before sustaining**: read the cited artifact, re-execute contested probes, state what was verified. Judging on the parties' evidence alone inherits whatever both sides missed; re-execution is where a judge finds what neither ledger holds. Exhibits: [PR #926](https://github.com/Grimblaz/agent-orchestra/pull/926), [PR #1034](https://github.com/Grimblaz/agent-orchestra/pull/1034).
- **No party is deferred to** — a judge may reject a finding the defense conceded, and raise severity the defense argued down. A concession is a party's assessment, not a verified fact.
- **Settle severity** at the evidence, not the average of the parties' positions.
- One ruling per merged finding, no rebuttal rounds; the ruling carries the finding's `found_by` unchanged.
- **Post the ruling to the review's durable surface** — the pull request or issue the ledger's `ref` points at — before the fix batch begins. A ruling that lives only in a session cannot be read by the stage that follows it, by a later review asking what a row was about, or by anyone auditing whether a sustained finding was actually fixed.

## Post-fix re-validation — mandatory, executable, fix-wide

Fixes are a defect source comparable to fresh diffs — written under time pressure, against a known-defective baseline, by someone who has stopped looking for defects and started removing them. A fix batch that no one looked at reads as clean for that reason alone. Rules:

- **Execute what executes, prosecute what doesn't.** Run every check that can run (suites, lint, the findings' own probes). Every reading stage shares a blind spot that only a live run closes: a line can be read correctly by everyone and still behave otherwise. Exhibit: [PR #1001](https://github.com/Grimblaz/agent-orchestra/pull/1001). For prose fixes, the executable look **is** the fix-diff prosecution pass plus whatever checks read prose (lint, link/quote verification) — re-reading your own fix is not re-validation.
- **Scope to everything the fix touched** — every code branch and every edited passage, not the guard named in the finding — **including the review's own bookkeeping**: the merged finding list, the defect rows written, the commit message, the report. No seat reviews the parent's output, which makes it the least-checked surface in the pipeline. Exhibit: [PR #2](https://github.com/Grimblaz-and-Friends/tradecraft/pull/2). Order: commit the fixes, write the rows, then look over both — and a defect found in bookkeeping already pushed is dispositioned `recorded`, since rewriting pushed history is not available. This scope elaborates the constitution's "every branch the fix touched"; it does not depart from it. Scoping a post-fix look to the guard the finding named is how a class survives its own remedy and returns in the fix's mirror image. Exhibits: [PR #887](https://github.com/Grimblaz/agent-orchestra/pull/887), [#886](https://github.com/Grimblaz/agent-orchestra/issues/886).
- One prosecution look at the fix diff (plus defense on anything it finds) is the shape; a clean look ends the cycle. Hold every remedy to the evidence standard above — the repair reproducing its own class is what this look most often finds.

## Closing a recurring class

When the same defect class returns — across findings, reviews, or repos — the fix is never another seat: it is a **promoted lens** (ADR-002's lifecycle), worded so it would have caught the class's own motivating exemplar, and carried in this skill's evidence standards or seat lenses. A class that has survived repeated panels will survive one more; what stops it is a lens that names its shape, because the next seat then looks for the shape instead of the instance. Exhibit: [#886](https://github.com/Grimblaz/agent-orchestra/issues/886). Seats catch instances; lenses retire classes.

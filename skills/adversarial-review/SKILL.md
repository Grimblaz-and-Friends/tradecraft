---
name: adversarial-review
description: Adversarial review of a changeset or artifact — a differentiated four-seat panel (or single cold pass for routine changes), an evidence-bound defense, an evidence-verifying judge, and executable post-fix re-validation. Use when a change is ready for review, when deciding review depth for an artifact, or when a review finding needs defense or judgment; not for choosing what to build (that is design work) and not for committing and pushing the fixes afterward (landing changes is its own activity with its own guards).
---

# adversarial-review

Review as prosecution under evidence rules: seats hunt defects, a defense tries to disprove them, a judge rules on what survives, and the fixes are then re-validated by execution. The shape scales with the artifact; the evidence standards never do.

This skill never asks a question mid-pipeline: from the first seat's dispatch to the judge's ruling the pipeline is atomic — no interim fixes, no edits to the artifact under review, no engagement prompts. A finding that needs an owner decision is surfaced in the judge's report as exactly that (and recorded with disposition `owner-pending` where a defect ledger exists), and the report is where the pipeline stops. Safe in attended and unattended lanes alike.

## Choosing the shape

In this skill's home repo, ADR-006 owns the default and this skill executes it; in any other repo, the shape rules below stand on their own, and sustained findings' attribution goes wherever that repo records defects — or stays in the review report when nowhere else exists.

- **Routine change**: one adversarial pass that reads the artifact **cold**, then defense, then executable re-validation of any fixes. Defense's evidence verdicts terminate — no separate judge; the defense is the filter for this lane.
- **Substantial artifact** (newly written foundational prose, new scripts, high blast radius — and when in doubt, this lane: going below the default is bought only by ledger evidence, never by argument): the **four-seat differentiated panel** below, then defense, then judge, then executable re-validation. Width beyond four, or an additional external fresh-session reviewer, is bought by declared risk.
- **Record the classification.** The review report states which lane was chosen and why in one line — an unrecorded shape choice can never be audited or de-escalated later.

Why a panel and not one strong pass: in the predecessor's record, across the six review rounds that preserved per-seat attribution (116 sustained findings), a single pass kept 12% of the sustained yield and lost nearly every critical and high; the best seat chosen with hindsight kept 46%, and the best seat's identity changed nearly every round ([the mining record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/1)). The same rounds set the width at four: the best three seats retained roughly 75–100% per round, the fourth seat's marginal yield stayed real — up to a fifth of a round's sustained findings, at times including highs — and the fifth seat's went thin.

## The default roster — four seats

Seats differ or they are waste; these four names are also the canonical `found_by` values (with the stages: `defense`, `judge`, `post-fix`, `external`, `ci`):

- **`cold-read`** — fresh vantage, no lens brief: forms its own view of the artifact before any prior findings exist for it. Cold sole-finds were load-bearing three separate times in the predecessor's record, twice described in its own dispositions as "missed by all three review lenses and caught only by the convergence cold-read" ([#922](https://github.com/Grimblaz/agent-orchestra/issues/922)).
- **`claims-vs-evidence`** — for prose: verify every load-bearing claim, number, and quotation against its cited source. Newly written generalized prose is where defects concentrate ([#844](https://github.com/Grimblaz/agent-orchestra/issues/844): 15 of 15 sustained findings, none in carried-verbatim text).
- **`wiring-falsifier`** — for scripts and contracts: does the code enforce what the prose claims, does anything call it, can each guard actually fail? Probe by execution, not reading.
- **`operational`** — walk the artifact as its consumer: a fresh executor following the text, reporting where it under-determines or misleads action. This is the differently-positioned vantage that caught what panels read past ([#878](https://github.com/Grimblaz/agent-orchestra/issues/878)'s escape fell to exactly this position).

**Substitution, not silence**: a write path or trust boundary earns a `security` seat; an artifact built on an unreviewed design earns a `position` seat (review the earlier artifact first — ADR-006's position axis, the stronger escalation). Swaps and additions are recorded in the review report, and a swapped-in seat's name enters `found_by` as used.

**Differentiation axes**, strongest first: vantage (cold vs briefed vs consumer), lens family, position. **No clone seats** — two seats with the same lens and vantage add noise, not coverage: same-lens redundancy contributed no unique sustained finding above a single low in either this repo's or the predecessor's record, and cross-pass concurrence once amplified a false finding into unearned confidence ([#882](https://github.com/Grimblaz/agent-orchestra/issues/882)).

**The cold boundary, operationally**: the cold seat's dispatch carries the assignment (artifact location, diff base, output format, evidence standards) and none of the review's history — no prior findings, no self-review, no earlier ledgers, no conversation context. Those four exclusions are the auditable rule; a cold seat must therefore be a fresh dispatch, never the session that authored or discussed the artifact.

**Independence extends to every role**: defense and judge are staffed like seats — never the artifact's author, and the judge never a finder. In a single-session lane this means all review roles are dispatches, not the authoring session reviewing itself.

## Staffing and effort

Every seat runs at the strongest model tier its runtime's budget bears; **the bottom tier never seats** — the one cliff the seat-yield record establishes (the predecessor's cheapest seat was weakest in every attributed round). Where the top tier is scarce, concentrate it where open-ended perception lives — the `cold-read` — and where single dispatches carry the most leverage — the judge of foundational reviews; briefed lens seats showed no measured yield gap one tier down. On a runtime where the top tier is not scarce, this rule collapses to "top tier everywhere."

Reasoning effort: terminal stages (defense, judge) run at least the seats' effort, escalated where the runtime offers it; width escalations are governed by the panel rules above, never by effort settings — orchestration scale and per-dispatch reasoning are different levers and are not exchanged for one another.

*Dated example (2026-08, demotable per ADR-002 — an application of the rule, never the rule):* on Claude Code here, `cold-read` runs Fable, briefed seats and defense run Opus (defense one effort step up), the judge runs Opus at max — Fable for constitution-touching reviews; on a flat-budget runtime (e.g. Codex today), top tier throughout. The tier evidence is Claude-family only; `source` on each ledger row should name the runtime/model that staffed the finding's seat so per-runtime evidence accumulates.

## Evidence standards — every seat, every stage

- **A finding states a concrete failure mode** and quotes the exact line or names the exact artifact, with the probe command where one was run — defense must be able to re-run it. Coverage-first: report everything with a statable failure mode, including low-severity and uncertain items; omission is reserved for items with no statable failure mode at all. The filter is the terminal stage — the judge on panels, the defense on routine reviews — never the prosecutor's nerve.
- **An absence claim requires a search you actually ran.** All three false findings in the predecessor's measured worst round were unsubstantiated "X never happens" claims, killed by defense with direct reads of the live tree ([#882](https://github.com/Grimblaz/agent-orchestra/issues/882)).
- **A new test pin must go red against the pre-fix revision.** Green suites prove nothing about the defect: the predecessor once had all 914 pre-existing tests green with six live defects, and trust came from 18 of 20 new pins going red pre-fix ([its own exhibits record](https://github.com/Grimblaz/agent-orchestra/blob/main/skills/adversarial-review/references/review-exhibits.md)).
- **A check is only as good as what it reads**: confirm a guard reads the artifact that ships, and mutate the guarded property to see the check fail. A checker with no caller is prose wearing a script's clothes.
- **Severity is a claim too.** Overstated severity is a defect the defense can strike — the predecessor's judges corrected severity repeatedly in both directions, and one ruling summarized a defense's yield as catching "severity inflation, not invention."

## Merge — parent-owned, before defense

The parent (the dispatching session) merges the seats' ledgers before defense sees them: a duplicate is the **same failure mode at the same location**; the merged finding keeps **every finder** (primary first — the primary is the projection a defect-ledger row carries, per the constitution's `found_by` contract), and dual credit is preserved in the review report. The defense receives the merged ledger plus access to the artifact; the judge receives the merged ledger, the defense report, and access to the artifact — both must be able to re-execute any probe a verdict rests on.

**Error states**: a seat that fails or returns unusable output is re-dispatched once; a panel still short a seat after retry proceeds, and the report and the ledger rows record the degraded width. Zero findings from all seats is a valid outcome — the defense has nothing to examine, the report says so, and no defect rows are written.

## Defense — one pass, always

Presume the artifact innocent; read every cited line independently; re-run every probe a finding rests on; challenge only with concrete counter-evidence. Verdict per finding: **disproved**, **conceded**, or **insufficient-to-disprove** — with the evidence for each. The defense may also originate findings its re-runs surface (in the predecessor's record it originated the only critical of a post-fix cycle, [PR #926](https://github.com/Grimblaz/agent-orchestra/pull/926)) and may move severity with evidence.

Defense is what makes width safe — 40+ false or inflated findings killed across the predecessor's mined rounds — but its verdicts are fallible in one recorded way: a confident disproof aimed at the wrong mechanism, exonerating a real defect that a live run then caught (its publicly verifiable instance is [PR #950](https://github.com/Grimblaz/agent-orchestra/pull/950)'s M14, Windows-blind, vindicated by a later commit). Where a defense verdict can be settled by running something, run it.

## Judge — panel reviews only, single-shot

The judge's test per finding: **will acting on this improve the artifact?** Yes → sustain; no → dismiss; still unclear after verification → dismiss ("Uncertainty is not a deferral bucket" — the predecessor's judgment skill, verbatim). Rules:

- **Verify independently before sustaining**: read the cited artifact, re-execute contested probes, state what was verified. The recorded high-value judge acts were all re-executions — live repros, scratch-tree reconstructions, a ship-blocker neither ledger caught ([PR #926](https://github.com/Grimblaz/agent-orchestra/pull/926)), a correction neither party held ([PR #1034](https://github.com/Grimblaz/agent-orchestra/pull/1034)).
- **No party is deferred to** — a judge may reject a finding the defense conceded, and raise severity the defense argued down; both happened in the record and both rulings were right.
- **Settle severity** at the evidence, not the average of the parties' positions.
- One ruling per merged finding, no rebuttal rounds; the ruling carries the finding's `found_by` unchanged.

## Post-fix re-validation — mandatory, executable, fix-wide

Fixes are a defect source comparable to fresh diffs: in the predecessor's record, three of one PR's five rounds each surfaced a defect introduced by a prior round's fix, and the only PR with zero fix-introduced defects on record is the only one that never looked. Rules:

- **Execute what executes, prosecute what doesn't.** Run every check that can run (suites, lint, the findings' own probes) — every reading stage, defense included, showed shared blind spots that only live runs caught (a latent defect once sat on a line that five passes, the defense, the judge, and the covering test had all read; the full-suite re-run caught it, [PR #1001](https://github.com/Grimblaz/agent-orchestra/pull/1001)). For prose fixes, the executable look **is** the fix-diff prosecution pass plus whatever checks read prose (lint, link/quote verification) — re-reading your own fix is not re-validation.
- **Scope to everything the fix touched** — every code branch and every edited passage, not the guard named in the finding. The predecessor's best-documented escape was mutation-tested post-fix and still missed because the scope was pinned to the named guard — and the defect class then recurred three times in the fix's own mirror image, on the implementing PR's own record ([PR #887](https://github.com/Grimblaz/agent-orchestra/pull/887); systemic remedy at [#886](https://github.com/Grimblaz/agent-orchestra/issues/886)).
- One prosecution look at the fix diff (plus defense on anything it finds) is the shape; a clean look ends the cycle.

## Closing a recurring class

When the same defect class returns — across findings, reviews, or repos — the fix is never another seat: it is a **promoted lens** (ADR-002's lifecycle), worded so it would have caught the class's own motivating exemplar, and carried in this skill's evidence standards or seat lenses. The predecessor's sibling-write-path class bit eight times across five issues, survived fifteen seat-readings and two post-fix cycles, and stopped recurring only when a checklist lens was worded to trace full write paths including downstream helpers ([#886](https://github.com/Grimblaz/agent-orchestra/issues/886)). Seats catch instances; lenses retire classes.

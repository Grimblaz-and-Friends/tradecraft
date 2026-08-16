---
name: adversarial-review
description: Adversarial review of a changeset or artifact — a differentiated panel (or single cold pass for routine changes), an evidence-bound defense, an evidence-verifying judge, and executable post-fix re-validation. Use when a change is ready for review, when deciding review depth for an artifact, or when a review finding needs defense or judgment; not for choosing what to build (that is design work) or for landing the fixes (that is persist-changes' territory).
---

# adversarial-review

Review as prosecution under evidence rules: seats hunt defects, a defense tries to disprove them, a judge rules on what survives, and the fixes are then re-validated by execution. The shape scales with the artifact; the evidence standards never do.

This skill never asks a question mid-pipeline: from the first seat's dispatch to the judge's ruling the pipeline is atomic — no interim fixes, no edits to the artifact under review, no engagement prompts. A finding that needs an owner decision is surfaced in the judge's report as exactly that, and the report is where the pipeline stops. Safe in attended and unattended lanes alike.

## Choosing the shape

ADR-006 owns the default and this skill executes it:

- **Routine change**: one adversarial pass that reads the artifact **cold**, then defense, then executable re-validation of any fixes. Defense's evidence verdicts terminate — no separate judge.
- **Substantial artifact** (newly written foundational prose, new scripts, high blast radius): a **differentiated panel** of about three seats, then defense, then judge, then executable re-validation. Panel width beyond three, or an external fresh-session reviewer, is bought by declared risk; going below the default is bought only by ledger evidence.

Why a panel and not one strong pass: in the predecessor's record, across the six review rounds that preserved per-seat attribution (116 sustained findings), a single pass kept 12% of the sustained yield and the best seat chosen with hindsight kept 46% — losing criticals and highs in every round, with the best seat's identity changing round to round ([the mining record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/1)).

## Seat design

Seats differ or they are waste. Differentiation axes, strongest first:

- **Vantage**: at least one seat reads **cold** — its dispatch carries the artifact and nothing else: no prior findings, no self-review, no earlier ledgers, no conversation history. Cold sole-finds were load-bearing four separate times in the predecessor's record, twice explicitly "missed by all three lenses and caught only by the cold read" ([#922](https://github.com/Grimblaz/agent-orchestra/issues/922)).
- **Lens**: each briefed seat gets a distinct lens family — claims-vs-evidence for prose (where defects concentrate in newly written generalized text: [#844](https://github.com/Grimblaz/agent-orchestra/issues/844), 15 of 15 sustained findings), wiring-and-falsifiers for scripts and contracts (does the code enforce what the prose claims; does anything call it; can the check's subject control its outcome), security/data-integrity where a write path exists.
- **Position**: reviewing an earlier artifact (the framing, the design) is a stronger escalation than another seat at the same artifact — ADR-006's position axis.

**No clone seats.** Two seats with the same lens and vantage add noise, not coverage: same-lens redundancy contributed no unique sustained finding in either this repo's or the predecessor's record, and cross-pass concurrence once amplified a false finding into unearned confidence ([#882](https://github.com/Grimblaz/agent-orchestra/issues/882)).

**Every finding records its finder.** The merged ledger keeps `found_by` (the seat name — and on a merged duplicate, every finder), and sustained findings carry it into the repo's defect ledger (the one ADR-006 defines, where this skill runs in its home repo). Seats retire or earn their place by that record, never by argument — the predecessor ran 850 ledger entries without this field and its seat question stayed unanswerable for the project's whole life.

## Evidence standards — every seat, every stage

- **A finding states a concrete failure mode** and quotes the exact line or names the exact artifact. Coverage-first: report everything with a statable failure mode, including low-severity and uncertain items; omission is reserved for items with no statable failure mode at all. The filter is the judge, not the prosecutor's nerve.
- **An absence claim requires a search you actually ran.** All three false findings in the predecessor's measured worst round were unsubstantiated "X never happens / X is never provided" claims, killed by a single file read ([#882](https://github.com/Grimblaz/agent-orchestra/issues/882)).
- **A new test pin must go red against the pre-fix revision.** Green suites prove nothing about the defect: the predecessor once had all 914 existing tests green with six live defects, and trust came from 18 of 20 new pins going red pre-fix ([PR #1006](https://github.com/Grimblaz/agent-orchestra/pull/1006)).
- **A check is only as good as what it reads**: confirm a guard reads the artifact that ships, and mutate the guarded property to see the check fail. A checker with no caller is prose wearing a script's clothes.
- **Severity is a claim too.** Overstated severity is a defect the defense can strike — in the predecessor's record judges corrected severity in both directions about twenty times, and once summarized a defense's whole yield as "severity inflation, not invention."

## Defense — one pass, always

Presume the artifact innocent; read every cited line independently; re-run every probe a finding rests on; challenge only with concrete counter-evidence. Verdict per finding: **disproved**, **conceded**, or **insufficient-to-disprove** — with the evidence for each. The defense may also originate findings its re-runs surface (in the predecessor's record it originated the only critical of a post-fix cycle, [PR #926](https://github.com/Grimblaz/agent-orchestra/pull/926)) and may move severity with evidence.

Defense is what makes width safe — 40+ false or inflated findings killed across the predecessor's mined rounds — but its verdicts are fallible in exactly one recorded way: a confident disproof aimed at the wrong mechanism, exonerating a real defect. Both recorded instances were caught by live execution, never by argument. Where a defense verdict can be settled by running something, run it.

## Judge — panel reviews only, single-shot

The judge's test per finding: **will acting on this improve the artifact?** Yes → sustain; no → dismiss; still unclear after verification → dismiss ("uncertainty is not a deferral bucket"). Rules:

- **Verify independently before sustaining**: read the cited artifact, re-execute contested probes, state what was verified. The recorded high-value judge acts were all re-executions — live repros, scratch-tree reconstructions, a ship-blocker neither ledger caught ([PR #926](https://github.com/Grimblaz/agent-orchestra/pull/926)), a correction neither party held ([PR #1034](https://github.com/Grimblaz/agent-orchestra/pull/1034)).
- **No party is deferred to** — a judge may reject a finding the defense conceded, and raise severity the defense argued down; both happened in the record and both rulings were right.
- **Settle severity** at the evidence, not the average of the parties' positions.
- One ruling per finding, no rebuttal rounds; the ruling names the finding's `found_by` unchanged.

## Post-fix re-validation — mandatory, executable, fix-wide

Fixes are a defect source comparable to fresh diffs: in the predecessor's record, three of one PR's five rounds each surfaced a defect introduced by a prior round's fix, and the only PR with zero fix-introduced defects on record is the only one that never looked. Rules:

- **Execute, don't re-read.** Every reading stage — panel, defense, judge — showed shared blind spots that only live runs caught (a latent defect once sat on a line that five passes, the defense, the judge, and the covering test had all read; the full-suite re-run caught it, [PR #1001](https://github.com/Grimblaz/agent-orchestra/pull/1001)).
- **Scope to every branch the fix touched**, not the guard named in the finding. The predecessor's best-documented escape was mutation-tested post-fix and still missed, because the mutation scope was pinned to the named guard — and the defect class then recurred three times in the fix's own mirror image ([#878](https://github.com/Grimblaz/agent-orchestra/issues/878) → [#886](https://github.com/Grimblaz/agent-orchestra/issues/886)).
- One prosecution look at the fix diff (plus defense on anything it finds) is the shape; a clean look ends the cycle.

## Closing a recurring class

When the same defect class returns — across findings, reviews, or repos — the fix is never another seat: it is a **promoted lens** (ADR-002's lifecycle), worded so it would have caught the class's own motivating exemplar, and carried in this skill's evidence standards or seat lenses. The predecessor's sibling-write-path class bit eight times across five issues, survived fifteen seat-readings and two post-fix cycles, and stopped recurring only when a checklist lens was worded to trace full write paths including downstream helpers ([#886](https://github.com/Grimblaz/agent-orchestra/issues/886)). Seats catch instances; lenses retire classes.

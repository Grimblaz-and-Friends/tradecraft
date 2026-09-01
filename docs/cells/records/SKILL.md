---
name: records
description: This repository's append-only records and its decision log — which record each kind of outcome appends to, where a decision entry lives and what freezes about it on landing, and the rule that no record here is ever maintained after its append. Use when appending to a record in this repository, when writing or citing a decision entry, when recording a review's outcome, or when tempted to correct or reconcile something already recorded; not for how a review reaches the outcome being recorded, and not for deciding where a rule or document belongs.
---

# records

**Purpose:** carry what this repository does with the exhaust its work produces, so a session recording an outcome appends in the right place and never maintains what it appended. **Audience:** any session here about to write to a record or a decision entry, or about to correct one. **Success:** every outcome lands in the record that holds it, decision entries are written where a later session finds them, and nothing is backfilled.

## Review, here

Every review appends one row to `docs/reviews.jsonl`, and every `record` ruling one entry to `docs/recorded-findings.jsonl`.

## Decisions

`docs/architecture/decisions/D-<PR#>-YYYY-MM-DD-<slug>.md`, written in the PR that lands a choice a future session would otherwise re-derive or unknowingly undo; frozen on landing but for the two narrow repairs bounded in the log's README. A rule or skill line may cite its decision (`[D-N]`).

## Records are exhaust

Records are append-only and never maintained: no backfilling, no reconciling, no re-dispositioning, ever. A PR whose only content is record bookkeeping is the tripwire: delete the record it books. `docs/ledger.jsonl`, `docs/seat-record.jsonl`, and the pre-reset constitution under `docs/architecture/` (statute, ADRs, evidence registry) are a frozen archive — readable history, never binding. [D-74]

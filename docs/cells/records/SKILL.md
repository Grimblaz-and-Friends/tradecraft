---
name: records
description: This repository's append-only records and its decision log — which record each kind of outcome appends to, the admission that lands a needed item over a ceiling, where a decision entry lives and what freezes about it on landing, and the rule that no record here is ever maintained after its append. Use when appending to a record in this repository, when a needed item will not fit under a ceiling, when writing or citing a decision entry, or when tempted to correct or reconcile something already recorded; not for deciding where a rule or document belongs.
---

# records

**Purpose:** carry what this repository writes to its own records — the exhaust its work produces, and the one record its guards read back — so a session appending here puts it in the right place and never maintains what it appended. **Audience:** any session here about to write to a record or a decision entry, or about to correct one. **Success:** every outcome lands in the record that holds it, decision entries are written where a later session finds them, and nothing is backfilled.

## Where this cell's depth lives

- **Landing a change that owed an implementation brief** → `references/the-settling-row.md`: the row `docs/settling.jsonl` takes at landing, the three places it is read off rather than recalled, the keys it carries and what a figure nobody can supply is written as, and why a reversal is a later append.
- **A needed item that will not fit under a ceiling, or a surface that has come back under one** → `references/admissions-at-a-ceiling.md`: the row `docs/admissions.jsonl` takes, one per ceiling the item exceeds; why an admission is not a raise and the constant does not move; why a cell body is not such a surface at all, its passing being reported rather than admitted; and the bank row that returns the space, which the tripwire does not reach.

## Decisions

`docs/architecture/decisions/D-<PR#>-YYYY-MM-DD-<slug>.md`, written in the PR that lands a choice a future session would otherwise re-derive or unknowingly undo; frozen on landing but for the two narrow repairs bounded in the log's README. A rule or skill line may cite its decision (`[D-N]`).

## Records are exhaust

Records are append-only and never maintained: no backfilling, no reconciling, no re-dispositioning, ever. A PR whose only content is record bookkeeping is the tripwire: delete the record it books. **Two records carve an exception and each states its own** — a reversal row on `docs/settling.jsonl` (`references/the-settling-row.md`) and a bank row on `docs/admissions.jsonl` (`references/admissions-at-a-ceiling.md`). `docs/ledger.jsonl`, `docs/seat-record.jsonl`, and the pre-reset constitution under `docs/architecture/` (statute, ADRs, evidence registry) are a frozen archive — readable history, never binding. [D-74]

**The review index `docs/reviews.jsonl` and held-findings store `docs/recorded-findings.jsonl` are closed history.** Nothing appends to either or reads either for subsequent work; their existing bytes remain. Findings now end in the pull request thread, their fix, an issue that states work, or the release report's ask.

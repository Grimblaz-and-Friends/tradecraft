---
name: records
description: This repository's append-only records and its decision log — which record each kind of outcome appends to, the admission that lands a needed item over a ceiling, where a decision entry lives and what freezes about it on landing, and the rule that no record here is ever maintained after its append. Use when appending to a record in this repository, when a needed item will not fit under a ceiling, when writing or citing a decision entry, when recording a review's outcome, or when tempted to correct or reconcile something already recorded; not for how a review reaches the outcome being recorded, and not for deciding where a rule or document belongs.
---

# records

**Purpose:** carry what this repository writes to its own records — the exhaust its work produces, and the one record its guards read back — so a session appending here puts it in the right place and never maintains what it appended. **Audience:** any session here about to write to a record or a decision entry, or about to correct one. **Success:** every outcome lands in the record that holds it, decision entries are written where a later session finds them, and nothing is backfilled.

## Review, here

Every review appends one row to `docs/reviews.jsonl`, and every `record` ruling one entry to `docs/recorded-findings.jsonl`. Beyond the fields the practice's own `the-record.md` names, a row here carries one more field, `cost`, and one more key on each entry of `highs`.

**`cost` — what the review took to run**, as `{"dispatches": n, "subagent_tokens": n}`.

- **`dispatches`** counts every subagent **the review** dispatched: its seats, its defense, and its judge, each of which runs once. **Not counted:** the convergence rounds and the cold seat that settles the artifact, spikes, experience sessions — including the one a fix batch buys, which the review dispatches but which is the change's cost — and a commissioned pass, which `after-the-fix.md` defines by provenance rather than by calling mechanism — so whether it dispatches agents of its own is not settled there, and it is excluded on the same ground as the rest. The row's subject is the review's own staffed stages, which is what the exclusions turn on — not on whose cost the excluded thing is. A spike the terminal stage commissions is dispatched by the review and is still excluded, being a distinct instrument that reports on the work's issue.
- **`subagent_tokens`** sums what those same dispatches returned. It is `null` where the runtime does not report per-dispatch tokens — an abstention claiming nothing, where a zero would claim no subagent ran. **`dispatches` may not abstain**: a runtime that made dispatches can count them, so a null there is a figure withheld rather than one unavailable, and the guard rejects it.

**Both are read off tool returns and neither is ever estimated**; a figure reconstructed from a transcript is the thing this field exists to stop. It is evidence for the next lane choice and never a ceiling to come under.

**`target` — the surface each sustained high hit**, carried on the high itself: `highs` entries are `{"high": "...", "target": "..."}`. Read from the site the finding cites, exactly as `arbitration.md` reads consequence shape, **and decided in this order, first match governing**:

1. **`record`** — this change's own paperwork, wherever it sits: its decision entry, its own index row, its pull request body, its commit message, its review report, its pre-implementation artifact and the brief that artifact carries. First, because the two of those that are in the tree sit in the repo-only zone and a zone test would swallow them. A row or entry landed by *earlier* work is not this change's paperwork and falls through.
2. **`shipped`** — what an adopter installs: the shipped zone `siting` names, or a generated mirror of it, which takes its source's label.
3. **`repo`** — everything else **in this tree**, by residue rather than by list, so every site in it has a lawful label.

**A site outside the tree that is not this change's own paperwork has no lawful value**, and the answer is to say so on the change rather than to invent one into a record nobody may correct.

A high citing sites of more than one kind takes the highest-reaching, `shipped` > `repo` > `record` — the same direction as `arbitration.md`'s rule that a finding citing both kinds is artifact-facing, and skewing against `record` for the reason [D-365] states.

**`target` and consequence shape are two values on one finding, read from the same site.** Shape asks whether the consequence lands on the work or on the record of having checked it; `target` asks which of the three surfaces above that site sits on. Neither is inferred from the other and neither is read from what the finding is *about* — `arbitration.md` forbids that for shape, and the same site rule governs here.

Booked per high rather than as counts because counts over findings are what could never be reconciled — `facing` is that failure on this record. [#357] [D-365]

## Admissions, at a ceiling

A needed item that puts a budgeted surface over its ceiling is admitted rather than cut, merged around or paid for by raising the number. The admission appends a row to `docs/admissions.jsonl` — one per ceiling the item exceeds, since a row carries one character count for every ceiling it names and two ceilings are seldom over by the same amount — carrying its date, the issue whose work required it, the ceilings it is charged against, the characters it admits there, what the item is, and what the outflow turned up first. **The constant does not move** — `tools/lint.py` enforces the constant plus what has been admitted against it, so a row buys its own item and no room for the next one, which is the difference between admitting and raising. When the surface comes back to or below its constant the lint says so, and the space is banked by **appending** a row with negative `chars`: a new fact about a new state, never a correction of the row it banks, so the append-only rule under *Records are exhaust* reaches it as an append and not as maintenance. **That section's bookkeeping tripwire does not reach this record** — a pull request whose only content is a bank row is discharging a finding, not booking exhaust, and deleting `docs/admissions.jsonl` would return every ceiling to its constant.

## Decisions

`docs/architecture/decisions/D-<PR#>-YYYY-MM-DD-<slug>.md`, written in the PR that lands a choice a future session would otherwise re-derive or unknowingly undo; frozen on landing but for the two narrow repairs bounded in the log's README. A rule or skill line may cite its decision (`[D-N]`).

## Records are exhaust

Records are append-only and never maintained: no backfilling, no reconciling, no re-dispositioning, ever. A PR whose only content is record bookkeeping is the tripwire: delete the record it books. `docs/ledger.jsonl`, `docs/seat-record.jsonl`, and the pre-reset constitution under `docs/architecture/` (statute, ADRs, evidence registry) are a frozen archive — readable history, never binding. [D-74]

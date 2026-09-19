---
name: records
description: This repository's frozen records and optional decision entries. Use when writing or citing a decision entry, consulting an old record, or considering an edit to recorded history; not for live workflow state or reports on current work.
---

# records

**Purpose:** preserve the repository's historical evidence without turning it into machinery that later work must maintain. **Audience:** a session deciding whether a choice needs a decision entry or reading an existing record. **Success:** durable choices remain findable, frozen history remains unchanged, and no record is created merely because a procedure used to ask for one.

## Decision entries are optional

Write `docs/architecture/decisions/D-<PR#>-YYYY-MM-DD-<slug>.md` only when omitting the entry would make a choice likely to be re-derived or unknowingly undone. Existing entries remain informative rather than binding and are frozen on landing except for the decision log's two documented reference repairs.

## Frozen records

`docs/ledger.jsonl`, `docs/seat-record.jsonl`, `docs/reviews.jsonl`, `docs/recorded-findings.jsonl`, and the pre-reset constitution under `docs/architecture/` are closed history. Nothing appends to them, reconciles them, or edits them; current work belongs on its issue, pull request, or report.

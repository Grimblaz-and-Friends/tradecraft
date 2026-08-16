# Working artifact — fix the defect ledger's instrument (from issue #5)

Pre-implementation artifact under ADR-006 §2. Contract, not recipe: no steps, no field definitions,
no mechanism. Lives on this branch only — its durable claims exit into ADR-006 and the lint before
merge, and the file is deleted (ADR-008 §2's wipe test governs).

## 1. Problem and observed evidence

ADR-006 §5's ledger carries three fields that have never held more than one value each:
`introduced` is `authoring` in 142 of 142 rows, `catchable` is `authoring-review` in 142 of 142,
`caught` is `adversarial-review` in 142 of 142. Three fields, zero variance.

§5 closes by making those fields the deciding evidence: *"'catchable at design, caught at
implementation' recurring in the ledger is the evidence that buys a standing pre-implementation
review; its absence is what retires one."* The vocabulary guarantees the absence. The test can
only acquit, and the acquittal would be a property of the schema rather than of the practice.

Two smaller defects in the same section: `found_by` enumerates no value for a defect the owner
surfaced, so the highest-yield finder on this repo's record has no bucket; and `ref` names "the
pull request or issue where its record lives" without saying that the surface must actually
enumerate findings — 107 of 142 rows point at a PR review comment carrying counts and highs, while
that PR's squashed commit message on `main` names findings individually, one hop away.

## 2. Epistemic map

**source-read**

- All 142 rows carry the three values above. (`docs/ledger.jsonl`, counted.)
- One `LEDGER_PHASES` set is defined at `tools/lint.py:60` and applied to all three fields at
  `tools/lint.py:268-270`. The set mixes kinds: `authoring` is a position, `adversarial-review`
  and `ci` are stages.
- **The position vocabulary does not need inventing.** ADR-006 §2 already names it: *"A framing, a
  design, a plan, and an implementation are each reviewable artifacts."*
- `found_by` is validated by *form* only — a lowercase token, `tools/lint.py:69` — not against a
  closed set. Adding `owner` is therefore a prose change to ADR-006 §5, not a lint change.
- `ref` is validated only as an `https://` prefix (`tools/lint.py:292-298`).
- Ref distribution: 57 → `pull/3`, 50 → `pull/2`, 35 → `commit/fa3345b`.
- The current vocabulary contains **no value able to express a position earlier than `authoring`**.
  So regardless of what any author judged, the field could not have recorded a distinction between
  positions.

**sample-inferred** *(contestable; may not set a tolerance or mandate a mechanism)*

- That the 142 rows' `introduced`/`catchable` values were defaults rather than judgments. Inferred
  from 100% uniformity plus the absence of any per-row reasoning. This claim does **not** carry the
  backfill decision — the source-read claim immediately above does, on the narrower and checkable
  ground that the schema could not have recorded such a judgment.
- That `caught: adversarial-review` is accurate rather than defaulted, inferred from `source`
  naming a review event on every row.

**known-unknown, left to the run**

- Exact membership of the stage vocabulary — whether `post-fix` becomes a stage or stays only a
  `found_by` value.
- Whether the lint should enforce ordering between the axes (catchable no later than caught).
- Whether re-pointing the 107 PR-targeted refs lands in this change or is recorded as owed.

## 3. What is being built

> ADR-006 §5's defect ledger records three fields that can each only ever hold one value, which
> makes the constitution's own test for whether upstream review is worth having unable to return
> anything but "no." We are fixing the instrument so that question can be answered by evidence:
> splitting the merged phase vocabulary into the two axes it actually contains — where a defect was
> made, and where it was caught — adding the owner as a recordable finder, and saying which surface
> `ref` must point at.
>
> We are **not** deciding whether upstream review happens, what an upstream artifact contains, or
> what triggers a review. Those wait for rows this fix makes possible.

## 4. Acceptance criteria

Each pins observable behaviour and carries its own proof standard.

1. **A defect decidable before any prose existed can be recorded as such, and a reader can tell it
   apart from one only findable by reading the prose.**
   *Proof:* author one row of each kind; they differ in at least one field's value; lint accepts
   both; a reader shown only the rows states which is which without other context.

2. **A row whose position was never judged is distinguishable from a row judged to be at the
   implementation position.** No value doubles as both "judged implementation" and "not judged."
   *Proof:* the two are different values, named in ADR-006 §5, and a reader shown one row alone can
   say which it is.

3. **A defect first surfaced by the owner has a lawful finder value** and is not forced into a seat
   name or into the not-recorded value.
   *Proof:* a row carrying it passes lint, and ADR-006 §5 enumerates it among the canonical values.

4. **Adding a position later does not require anyone to record a value they know to be wrong.**
   *Proof:* the contract states that where no position fits, the row records the not-judged value
   rather than the nearest wrong one, and that sentence can be pointed at; the position list has
   exactly one definition site in the lint.

5. **A reader holding any row can reach a description of that specific finding, or the row's target
   is one the contract admits does not carry one.**
   *Proof:* sample three rows per distinct `ref` target, follow each, and report whether the
   individual finding is named. A target that names only counts fails.

6. **Every pre-existing row stays lawful, and none of them asserts a position that was never
   judged.**
   *Proof:* lint clean over the whole file; the count of pre-existing rows asserting a judged
   position is zero.

**Vacuity check** — *is there a reading of these criteria under which every one passes and no work
happens?* Constructing the cheapest such reading: define both new vocabularies as copies of the
current set and change nothing else. That reading dies on criterion 1 — no field would distinguish
the two kinds — and again on criterion 2, since `authoring` would still serve as both "judged
implementation" and "never judged." A prose-only reading (add `owner`, touch nothing else) dies on
criteria 1, 2, 5 and 6. **No surviving reading**; criterion 2 is the clause doing the blocking.

## 5. Still open, classified

Beat-2 question, per entry: *could this change what we affirmed we are building, or change how we
would know it is done?*

| Entry | Verdict |
|---|---|
| Stage vocabulary membership | **No** — criteria 1–6 hold under any membership. Run settles it. |
| Ordering enforcement between axes | **No** — no criterion turns on it. Run settles it. |
| Re-pointing the 107 PR refs now vs recording it owed | **No** — criterion 5 pins the outcome either way; only the timing is open. Run settles it. |
| Who classifies the position field, and whether that judgment is trustworthy | **No, for this artifact** — the schema fix is correct regardless of who fills it, and no criterion here depends on the answer. Recorded because it *does* gate the decision this fix exists to enable, and is the open investigation's weakest point (issue #5). |

All no → **routine.** This is a contract fix to an existing section with the vocabulary already
named in ADR-006 §2; nothing open here could void a criterion.

# D-136: The review index records what came of the findings, and who staffed the review

**Status:** Accepted 2026-08-23 (PR #136)

## Context

`docs/reviews.jsonl` exists so process-weight questions are answerable when asked. It answered *how many findings each seat raised* and nothing about whether they mattered — so the question the last three decision entries circle was archaeology across prose reports rather than a query. The skill says this about the record at `skills/adversarial-review/SKILL.md:81` at `2090854`: *"a counts-only record is silent about everything its fields do not carry."*

A narrower defect made it concrete. `skills/adversarial-review/SKILL.md:49` at `2090854` requires every report to record the model and runtime that staffed each seat *"so per-runtime evidence can accumulate"* — and the index carried neither. The skill stated a purpose its own record could not serve.

The census, and how to re-derive it: `python -c "import json; rows=[json.loads(l) for l in open('docs/reviews.jsonl') if l.strip()]; print(len(rows))"` reports **20 rows** at this change's merge base, none carrying either field.

## Decision

**The row gains `dispositions`** — the terminal stage's own four, `fixed` / `routed` / `priced_out` / `dismissed`, copied from its ruling rather than re-derived. **And `staffing`** — `model` and `runtime`.

**`dismissed` is in the set** because it is the only field that measures **noise**. Measuring value while never measuring noise is how the predecessor's pipeline could only ratchet heavier, and it is the failure mode #122 names for this repo. It is near-derivable as merged minus sustained but not reliably: the terminal docket also carries anything in a seat's report that no merged finding carries [D-102], which is why the seat counts deliberately refuse to enforce `merged >= sustained`.

**Staffing is per review, not per seat.** Per-seat fields multiply the write cost of the field by the panel width — seven to eleven stage entries per row across the last twelve rows, two to eleven across all twenty — `python -c "import json; print([len(json.loads(l)['seats']) for l in open('docs/reviews.jsonl') if l.strip()])"` — and a mixed panel can record its split in the value, so the flat pair loses queryability on those rows and nothing else. Neither name is constrained to a vocabulary, because a fixed list would have to be amended before the first review staffed by a new runtime could be recorded at all; the **keys** are closed, so a per-seat shape cannot enter through `staffing` itself. It is not the whole key space: a top-level key and a seat's own counts mapping are both unvalidated, and closing them was priced out.

**Both are required of every row appended after the twenty that existed at landing, and validated whenever present.** Forward-only is enforced rather than stated: an optional field can never catch its own omission, and a record that silently fails to carry what it promises is the shape of the defect being closed.

**Grandfathered by position, not by date — and the first version got this wrong.** The affirmed artifact said "on or after this change lands", which was built as a date cutoff of 2026-08-24, the day after landing, because seven rows already carried the landing date — `python -c "import json, collections; print(collections.Counter(json.loads(l)['date'] for l in open('docs/reviews.jsonl') if l.strip()))"` — and the boundary forbids editing a landed row. An experience session then wrote this change's own first row and found the hole in eight tool calls: its hand reached for "today" before it re-read its brief, and a row dated one day early takes both fields as optional, passes lint in silence, and lands pre-schema in a file nobody may edit. Its own words — *"I got it right by copying the brief, not by understanding."* A schema obligation gated on a date the author types is one the author can opt out of with a typo. Position cannot be mistyped.

**The growth is argued, because net growth on governing prose is a finding on its own terms.** `skills/adversarial-review/SKILL.md:81` goes from 103 words to 221, and the whole skill's growth is that one line — 2,849 words to 2,967, measured on raw blob content against `2090854`. Two of the added clauses are the row's schema, which had lived only in enforcement code a shipped skill is forbidden to point at, and a consumer holding the plugin alone could not write a valid row without them. Two more are limits a reader would otherwise try to reason past and get wrong: that the disposition counts do not reconcile against the per-seat columns, and that an uneven panel says so in the value. The rest is one exemplar apiece for the two halves of `staffing`, because an instruction to spell a runtime consistently, shipped without a spelling to copy, is one no writer can obey — and the twenty linked reports already carry nine distinct spellings of one runtime, counting the backticked and unbackticked `claude-code` as one. The line was 225 words before this review and is shorter now; what remains is the schema and its two live limits, and nothing was found on it that could be routed out instead.

## What this does not close

#126 raised four questions. This closes **two**.

- **Disposition** — closed.
- **Per-runtime evidence** — closed for rows written from here. It does not reach back: of the twenty grandfathered rows, two ran genuinely mixed panels (`pr-77`, `pr-80`) and all but one declare their staffing in the linked report — a count inherited from the review that fetched all twenty, not derivable from the index, which is the defect being fixed, so the accumulation begins here rather than concluding.
- **Routing follow-through — not closed.** A row saying `routed: 2` does not verify either finding reached a vehicle. That needs the vehicle named, which is per-finding detail this deliberately excludes. **#126's own recommendation claims to close this question; it does not**, and that overclaim is corrected here rather than left standing in the issue that motivated the change.
- **Recurrence — not closed, and nothing was built for it.** #126 concedes a detector is likely armor until an incident says otherwise, and this change agrees.

## What the experience session changed

The session note is on the pull request. Three of its findings landed in this change rather than being answered:

- **The date cutoff became a position cutoff**, above.
- **The disposition keys are spelled out in the skill.** The session was handed "declined on price", the skill's verb is *price out*, and the key is `priced_out` — underscored, while every seat name in the same row is hyphenated and has a regex behind it while the disposition keys have none. It guessed right and reported that it would have guessed `declined`.
- **The skill now says the counts do not reconcile against the per-seat columns.** The session assumed `dispositions` partitions the merged findings, found the totals disagreed, went looking for a guard to tell it which side was wrong, and found instead the comment explaining why the seat-count invariants are deliberately absent. Its conclusion is the finding: *"the row is now permanent and I cannot tell you if it's arithmetically true."* No cross-check was added, because none is sound — the terminal docket carries entries no merged finding carries, and a dismissal was never sustained, so the two halves count different populations by construction. What was missing was saying so.

A fourth was recorded as unfixed on a false premise, and the review corrected both. The note said the row **cannot** express uneven staffing; that is untrue of its own record — the value is a free-form string and accepts `fable (cold-read), opus (rest)`. The premise offered for leaving it — that every row to date is uniform — was never checked and is false: `pr-77` and `pr-80` ran mixed panels, and `pr-80`'s split is `:49`'s recommended pattern inverted. The count is roughly one review in ten, not zero. The obstacle was the instruction rather than the schema, so the skill now tells an uneven panel to say so in the value, and the owner re-affirmed per-review staffing on the corrected figures.

## Three findings dispositioned here

The first two are the experience session's and were unaccounted for when this entry was first written; the third this review found while verifying the guard. Naming a finding in conversation is not a disposition.

- **The `merged` column has no defined convention** — whether a seat's count is its primary findings or every merged finding it contributed to. **Dropped, with the reason**: settling it binds every future row-writer, this change is about two new fields rather than an existing one, and no vehicle exists that would genuinely pick it up. Naming the line where the convention would live is a site, not a carrier, and calling that a route would record a follow-through that never happens. Recorded so a later reading of the index knows the column is not comparable across rows until it is settled; PR #135's row guessed primary-only, unstated.
- **Mutation probes can report a false result**, found while verifying this change's own guard: a size-preserving mutation of an integer constant is masked by stale bytecode, and one stage of this review published a SURVIVES it then had to retract. **Routed** to [#142](https://github.com/Grimblaz-and-Friends/tradecraft/issues/142), which carries the byte-exact reproduction and the necessary condition; it is a standard for how reviews are run, not a property of this artifact.
- **The schema's authority lives in the repo-only zone the shipped skill cannot point at.** **Dropped, with the reason**: the zone wall is doing what it is for, and the remedy inside this change is the one already taken — the skill now names both container keys and the four disposition values, so a consumer holding only the plugin can name the fields without reading enforcement code. What remains uncarried is the nesting and the numeric bar, which no shipped sentence can state without restating the lint.

## Rejected

- **Leaving the index and putting the loop in the reports** (#126's option B). Reports already carry dispositions, so the loop would stay closed by human memory — which is the currently-failing instrument: the word-count habit took the owner personally spotting it across three changes.
- **Periodic distillation** (#126's option C) — a session periodically reads the reports and appends a dated summary row. This is the closest shape on the board to the bookkeeping tripwire, and "periodic" work is the kind that silently stops.
- **Per-seat staffing**, which the issue's own recommendation proposed. It multiplies the write cost of the field by the panel width, and the flat pair loses only queryability on the rows that ran mixed.
- **A vocabulary for model and runtime names.** It would make the first Codex-staffed review unrecordable until the list was amended — the record blocking the evidence it exists to collect.
- **Editing landed rows to backfill either field.** Barred by the doctrine's records rule, and the reason the obligation starts after the rows already written rather than reaching back over them.
- **A cross-check that the dispositions reconcile with the seat counts.** It looks right and is wrong, the same way the seat counts' own absent invariants are: the terminal docket carries entries no merged finding carries, and a dismissal was never sustained. Two experience sessions each reached for that arithmetic and neither could complete it, which is why the skill now says the two halves count different populations rather than the lint pretending they do not.

## Evidence

[#126](https://github.com/Grimblaz-and-Friends/tradecraft/issues/126), the affirmed artifact at [comment 5387269115](https://github.com/Grimblaz-and-Friends/tradecraft/issues/126#issuecomment-5387269115) and its affirmation at [comment 5387270026](https://github.com/Grimblaz-and-Friends/tradecraft/issues/126#issuecomment-5387270026). The owner chose option A of the three the issue argued, in its narrowed form.

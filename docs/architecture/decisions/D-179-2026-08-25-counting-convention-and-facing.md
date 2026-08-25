# D-179: The row states its counting convention once, carries the split by consequence shape, and instrument firing is observed by a query rather than a mechanism

**Status:** Accepted 2026-08-25 (PR #179)

## Context

`docs/reviews.jsonl` gained `dispositions` and `staffing` in [D-136](D-136-2026-08-23-index-dispositions-and-staffing.md), and the rows written since exposed three things the record still could not say.

**The counting convention was being re-invented per row.** At this change's merge base `4d3860e` the file holds 31 rows. Rows 20–25 carry no `notes` at all; rows 26–30 each carry one of 98 to 297 words, and every one of them spends part of that defining what its own columns count — `pr-167` on what a seat's `merged` counts, `pr-169` on what the counted unit is, `pr-173` on summing across cycles. Four of those five also explain that their `seats` mapping books a `panel` aggregate because the merge recorded no per-seat split. Three separate undefined conventions, settled five times over, in prose no reader of a sixth row inherits.

```bash
python -c "import json; rows=[json.loads(l) for l in open('docs/reviews.jsonl',encoding='utf-8') if l.strip()]; [print(i, r['artifact'], len(r.get('notes','').split())) for i,r in enumerate(rows) if i>=20]"
```

D-136 dispositioned the `merged` column's undefined convention as **dropped, with the reason** — that settling it binds every future row-writer, that the change was about two new fields rather than an existing one, and that no vehicle existed which would genuinely pick it up. This is that vehicle, and the second instance is what makes it a pattern rather than an oversight.

**The split by consequence shape lived only in report prose.** [D-153](D-153-2026-08-24-consequence-field-and-the-batching-cut.md) made the report carry it, which is the instrument #122's third failure mode asks for. Of the five reviews whose reports post-date that requirement — rows 26 through 30 — three state the split (`pr-166`, `pr-167`, `pr-173`) and two do not (the `pr-156` amendment and `pr-169`, neither of whose reports has one). The three that do count **different populations**: `pr-167` splits 45 rulings as 44 artifact-facing to 1 apparatus-facing; `pr-173` splits round one's 20 *sustained* as 14 to 6. So the trend the design says to watch could not be read even by opening every report, and [#138](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138)'s cost recovery had to skip it.

**Nothing observed whether the instruments fire over real work.** The firing spike answered *does the text route correctly* and cannot answer *does a session bother*; a seat read the flow closely and skipped the step, and #124's own graduation argument turned on firing.

## Decision

### The counting convention is stated once, where the row's fields are defined

`skills/adversarial-review/SKILL.md` carries it in the record paragraph, which is the one surface a consumer holding only the plugin and a session in this repository both read. Four rules, no per-row annotation:

- **Every count sums across every cycle the review ran** — one row per review, never one per cycle. This is what the landed rows were written under (`pr-136`, `pr-173` both say so), so nothing already written changes meaning. The alternative — the terminal ruling alone — was rejected for exactly that: it would silently re-mean rows that can never be edited.
- **The unit counted is the finding as originated and dispositioned**, never a row of a ruling table. Folding two findings into one remedy is an execution convenience, not a merge. Taken from `pr-169`'s terminating ruling, which settled it for one row.
- **A seat's `merged` counts that seat's own findings surviving the merge**, so a finding spanning two merged entries counts once. Taken from `pr-167`, and it is the column D-136 dropped.
- **A seat key may book an aggregate** — `panel` where the merge recorded no per-seat split — saying in the row what it aggregates. Four of the last five rows did this and each explained it from scratch.

### The row gains `facing`

`{"artifact": N, "apparatus": M}`, splitting **the same population `dispositions` counts** — one entry per terminal ruling — by the consequence shape the merge already records per finding. Required of every row appended after the 31 extant at landing, validated whenever present.

**Keyed to the ruling rather than to the merged finding**, because the terminal docket also carries anything in a seat's report that no merged finding carries [D-102], and those take rulings too. A finding split across two limbs takes two rulings and contributes two entries, which is how `pr-167`'s 45 rulings over 42 items would be recorded.

**The lint checks that the two totals reconcile.** This is the one cross-total on the row that is sound. D-136 rejected a dispositions-versus-seat-counts check because the two halves count different populations by construction — the docket carries uncarried seat entries, and a dismissal was never sustained. `facing` is different in kind: it partitions the rulings `dispositions` counts, so a disagreement is an arithmetic error in a row about to become permanent, not two populations talking past each other. Two experience sessions each reached for the unsound arithmetic and neither could complete it; this one completes.

**Two grandfathering constants rather than one that moves.** `REVIEW_ROWS_GRANDFATHERED` stays at 20 and `REVIEW_ROWS_FACING_GRANDFATHERED` is 31. Raising a single constant would silently un-oblige `dispositions` and `staffing` for every row between the two boundaries, in a file the doctrine forbids editing. Position rather than date, per D-136: a date cutoff is one the author can opt out of with a typo, and an experience session found that hole in eight tool calls.

### Instrument firing is observed by a query, and nothing is built

The question is answerable today over exhaust that already exists, and the answer is clean. `skills/experience-session` landed with PR #131, merged `2026-08-23T22:00:26Z`. Twelve pull requests have merged since. Eleven carry an experience-session note or an explicit decline line in their body or comments. The twelfth is #132, merged `2026-08-23T18:45:45Z` — before #131 — which is the same reason #135's decline line gives. **Twelve of twelve accounted for; no observed skip.**

```bash
gh pr list --state merged --limit 30 --json number --jq '.[].number' | while read n; do printf '%s ' "$n"; gh pr view "$n" --json body,comments --jq '[.body, (.comments[].body)] | join("\n")' | grep -ci 'experience session\|session note'; done
```

A zero in the second column is the case to look at: it means neither a note nor a decline line was written. The query returns mentions rather than a classification, so a zero is a flag to read the PR, not a verdict on it.

**The reopen condition:** a real change found to have silently skipped an instrument — no note, no decline line, and no reason. The only skip on the record is [routing item 1.2](https://github.com/Grimblaz-and-Friends/tradecraft/issues/122#issuecomment-5388686795)'s, which is a *spike seat* — a probe, not an incident in real work — and the charter's admission rule takes that as insufficient to admit a mechanism.

## Rejected

- **The terminal ruling alone, as the aggregation convention.** Narrower, and it re-means the landed rows.
- **`facing` as report-only, with the decision recorded.** The report requirement already exists under D-153 and already leaked twice in five; reading a trend would mean opening N URLs and reconciling three incompatible populations by hand. The field is what routing item 1.4 and #122's failure mode 3 both asked for.
- **A canonical marker in the PR body for instrument firing.** It would buy precision the grep does not yet lack. Building it now is the counter-bureaucracy failure mode #122 names, on no incident.
- **Recording that firing is not observed at all**, without the query. Strictly worse than recording the query, which exists and cost nothing.
- **A per-cycle row.** It would answer where a review's cost concentrated, and it breaks one-row-per-review, which every landed row and every disposition ruling assumes.
- **Schematising `round` and `notes`.** Both are in active use as unvalidated top-level keys. Naming them here is a note, not a route; no vehicle is claimed.
- **Backfilling `facing` onto landed rows.** Barred by the doctrine's records rule, and the reason the obligation starts after the rows already written.

## What this does not close

- **The trend itself is not yet readable.** One row will carry `facing` when this lands. The instrument exists from here; the accumulation begins rather than concludes, exactly as D-136's per-runtime evidence did.
- **`notes` still carries per-row prose**, and nothing constrains what belongs there. This change removes the *need* to restate three conventions; it does not stop a row restating them.
- **Whether a routed finding reached its vehicle** stays unverified — D-136 named it, it needs the vehicle named per finding, and that is detail the row deliberately excludes.
- **The query is not routed to.** A session asking whether the instruments fire finds it here, in the decision log, and nothing points it here from the skills. That is the honest limit of building nothing.

## Cost

Governing prose grows **+908 characters** (89,683 → 90,591), derived by `python tools/figures.py --base 4d3860e` and re-run against the tree this entry lands on. The record paragraph goes from 221 words to 376 across two paragraphs, quoted pre-change at `skills/adversarial-review/SKILL.md:86` at `4d3860e`.

**The growth is argued rather than hidden**, because net growth on governing prose is a finding on its own terms. The alternative to these 155 words is not silence: it is the 1,067 words of `notes` the last five rows spent deriving the same conventions independently, none of which the sixth row inherits — and rows are permanent, so a row written under an unstated convention is wrong for good.

## Evidence

[#149](https://github.com/Grimblaz-and-Friends/tradecraft/issues/149), the affirmed artifact at [comment 5411145261](https://github.com/Grimblaz-and-Friends/tradecraft/issues/149#issuecomment-5411145261) and its affirmation at [comment 5411148218](https://github.com/Grimblaz-and-Friends/tradecraft/issues/149#issuecomment-5411148218). The owner ruled on all three forks the artifact carried. Warrant: field-run gap 8 and routing items 1.2 and 1.4 of the coverage design ([#122](https://github.com/Grimblaz-and-Friends/tradecraft/issues/122)).

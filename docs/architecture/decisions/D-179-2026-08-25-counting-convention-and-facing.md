# D-179: The row states its counting convention once, carries the split by consequence shape, and instrument firing is observed by a query rather than a mechanism

**Status:** Accepted 2026-08-25 (PR #179)

## Context

`docs/reviews.jsonl` gained `dispositions` and `staffing` in [D-136](D-136-2026-08-23-index-dispositions-and-staffing.md), and the rows written since exposed three things the record still could not say.

**The counting convention was being re-invented per row.** At this change's merge base `4d3860e` the file holds 31 rows. Rows 20–25 carry no `notes` at all; rows 26–30 each carry one of 98 to 297 words, and every one of them spends part of that defining what its own columns count — `pr-167` on what a seat's `merged` counts, `pr-169` on what the counted unit is, `pr-173` on summing across cycles. Four of those five also explain that their `seats` mapping books a `panel` aggregate because the merge recorded no per-seat split. Three separate undefined conventions, settled five times over, in prose no reader of a sixth row inherits.

```bash
python -c "import json; rows=[json.loads(l) for l in open('docs/reviews.jsonl',encoding='utf-8') if l.strip()]; [print(i, r['artifact'], len(r.get('notes','').split())) for i,r in enumerate(rows) if i>=20]"
```

D-136 dispositioned the `merged` column's undefined convention as **dropped, with the reason** — that settling it binds every future row-writer, that the change was about two new fields rather than an existing one, and that no vehicle existed which would genuinely pick it up. This is that vehicle, and the second instance is what makes it a pattern rather than an oversight.

**The split by consequence shape lived only in report prose.** [D-153](D-153-2026-08-24-consequence-field-and-the-batching-cut.md) made the report carry it, which is the instrument #122's third failure mode asks for. Of the five reviews whose reports post-date that requirement — rows 26 through 30 — three state a split at all (`pr-166`, `pr-167`, `pr-173`) and two state none (the `pr-156` amendment and `pr-169`). Measured against what D-153 actually requires — *"as a number, **per pass**"* — the compliance rate is **one of five**: only `pr-173` breaks its split out by pass. And the three that state one count **three different populations**: `pr-166` splits 26 panel-merged findings; `pr-167` splits 45 rulings as 44 artifact-facing to 1 apparatus-facing; `pr-173` labels its 14-to-6 as round one's *sustained* and calls that 20, which its own Counts table does not support — round one is 15 + 2 = 17, and 20 is the whole-review sustained total. That the label cannot be reconciled is itself the point: no two of the three can be compared. So the trend the design says to watch could not be read even by opening every report, and [#138](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138)'s cost recovery had to skip it.

**Nothing observed whether the instruments fire over real work.** The firing spike answered *does the text route correctly* and cannot answer *does a session bother*; a seat read the flow closely and skipped the step, and #124's own graduation argument turned on firing.

## Decision

### The counting convention is stated once, where the row's fields are defined

`skills/adversarial-review/SKILL.md` carries it in the record paragraph, which is the one surface a consumer holding only the plugin and a session in this repository both read. Four rules. Three of them retire per-row annotation; the fourth replaces it with a narrower one, naming what an aggregate covers:

- **Every count sums across every cycle the review ran** — one row per review, never one per cycle. This is what the landed rows were written under (`pr-136`, `pr-173` both say so), so nothing already written changes meaning. The alternative — the terminal ruling alone — was rejected for exactly that: it would silently re-mean rows that can never be edited.
- **The unit counted is the finding as originated and dispositioned**, never a row of a ruling table. Folding two findings into one remedy is an execution convenience, not a merge. Taken from `pr-169`'s terminating ruling, which settled it for one row.
- **A seat's `merged` counts that seat's own findings surviving the merge**, so a finding spanning two merged entries counts once. Taken from `pr-167`, and it is the column D-136 dropped.
- **A seat key may book an aggregate** — `panel` where the merge recorded no per-seat split — saying in the row what it aggregates. Four of the last five rows did this and each explained it from scratch.

### The row gains `facing`

`{"artifact": N, "apparatus": M}`, splitting **the same population `dispositions` counts** — one entry per terminal ruling — by the consequence shape defined at the merge. Required of every row appended after the 31 extant at landing, validated whenever present.

**For part of that population no shape is recorded anywhere, and this change does not close it.** `:66` records a shape per *merged finding*; `:70` gives a ruling to every uncarried seat entry as well, and those never reached the merge — on `pr-173`, 30 merged against 34 rulings, so 11.8% of the population has nothing to copy. The rule is unapplicable to them rather than merely unapplied: a shape is *"read from the site the finding cites"* and a declined examination cites no site. **So the row's writer derives that share rather than copying it**, which this change's own review demonstrated twice over — one cold consumer invented the values and said so in the row's notes, another refused and filed a row that reds the lint deliberately. Routed to its own change; see *What this does not close*.

**Keyed to the ruling rather than to the merged finding**, because the terminal docket also carries anything in a seat's report that no merged finding carries [D-102], and those take rulings too. A finding split across two limbs takes two rulings and contributes two entries, which is how `pr-167`'s 45 rulings over 42 items would be recorded.

**The lint checks that the two totals reconcile.** This is the one cross-total on the row that is sound. D-136 rejected a dispositions-versus-seat-counts check because the two halves count different populations by construction — the docket carries uncarried seat entries, and a dismissal was never sustained. `facing` is different in kind: it partitions the rulings `dispositions` counts, so a disagreement is an arithmetic error in a row about to become permanent, not two populations talking past each other. Two experience sessions each reached for the unsound arithmetic and neither could complete it; this one completes.

**Two grandfathering constants rather than one that moves.** `REVIEW_ROWS_GRANDFATHERED` stays at 20 and `REVIEW_ROWS_FACING_GRANDFATHERED` is 31. Raising a single constant would silently un-oblige `dispositions` and `staffing` for every row between the two boundaries, in a file the doctrine forbids editing. Position rather than date, per D-136: a date cutoff is one the author can opt out of with a typo, and an experience session found that hole in eight tool calls.

### Instrument firing is observed by a query, and nothing is built

The question is answerable today over exhaust that already exists, and the answer is clean. `skills/experience-session` landed with PR #131, merged `2026-08-23T22:00:26Z`. **Twelve pull requests are numbered above #131**, which is the population the query below selects, because `gh pr list` orders by number and not by merge time. Eleven of them carry an experience-session note or an explicit decline line in their body or comments. The twelfth is #132, which is numbered above #131 but merged `2026-08-23T18:45:45Z`, *before* it — the same reason #135's decline line gives, and the reason number order and merge order are not the same window. **Twelve of twelve accounted for; eleven carry a note or a decline; no observed skip.**

```bash
gh pr list --state merged --limit 30 --json number --jq '.[].number' | while read n; do printf '%s ' "$n"; gh pr view "$n" --json body,comments --jq '[.body, (.comments[].body)] | join("\n")' | grep -ci 'experience session\|session note'; done
```

**Read only the rows numbered above the PR that landed the instrument** — #131 here. The `--limit 30` window reaches well below it, and every PR at #128 and down predates the instrument, so ~17 of the zeros it returns are not skips and re-running it unqualified flags all of them. Inside the window, a zero in the second column is the case to look at: it means neither a note nor a decline line was written. The query returns mentions rather than a classification, so a zero is a flag to read the PR, not a verdict on it.

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
- **The position scheme has its own hole, and this entry chose it anyway.** A date cutoff can be dodged by a typo; a *position* cutoff can be dodged by a **deletion**. Delete one row and the next row appended falls under the boundary and is excused silently — measured on this change's own tree at `lint: 0 finding(s)`, and twelve deletions land a row entirely pre-schema. A constant set at the current row count, as this one is, is exempt-on-one-deletion the day it lands and narrows only as rows accrue. **A floor check (`31 <= len(rows)`) does not close it** — delete-one-then-append leaves the count unchanged — so the only remedy that closes it compares the index against `origin/main` as a prefix-extension, which would also be the first enforcement of the rule that no landed row is edited. That makes `check_review_index` git-aware, which it is not, and it is routed rather than ridden here. Deleting a row is already barred by the records rule, so the hole is reachable only through an act that is itself unlawful — which is why position still beat date, not that position had no weakness.
- **A concurrent pull request can land a row into the boundary's gap.** The constant is pinned to this change's *merge base*, and review rows land inside the pull request they review. If another open PR appends its row first, that row takes index 31 without `facing` and reds `main`. The lawful repair is raising `REVIEW_ROWS_FACING_GRANDFATHERED` to 32, which cannot un-oblige `dispositions` or `staffing` — the untouched 20 governs those — and un-obliges exactly the one row that genuinely predates the rule. What the two-constants argument above rejects is *one moving constant*, not a correction to the later one.
- **The query is not routed to.** A session asking whether the instruments fire finds it here, in the decision log, and nothing points it here from the skills. That is the honest limit of building nothing.

## Cost

Governing prose grows **+1,062 characters** (89,683 → 90,745), derived by `python tools/figures.py --base 4d3860e` and re-run against the tree this entry lands on. The record paragraph goes from 221 words to **397** across two paragraphs, quoted pre-change at `skills/adversarial-review/SKILL.md:86` at `4d3860e`; `:66` gains three words. The figure rose from +957 during this change's own review, which ordered two clauses into the cell — the split-limb rule and a third consumer of the consequence-shape axis.

**The growth is argued rather than hidden**, because net growth on governing prose is a finding on its own terms — and argued honestly, the ratio does not favour this change on a one-time comparison. **The `notes` prose these 176 words retire is 68 words**, band to 93: row 28's 20 on what a seat's `merged` counts, row 29's 35 on the counted unit, row 30's 13 on summing across cycles, plus up to 25 more of aggregate *justification*. Not retired: the aggregate *naming* clauses (25 words), which the fourth rule still mandates, and 12 words in row 28 restating a rule the cell already carried. The five rows' whole `notes` budget is 1,012 words — 98, 212, 171, 234 and 297 — and roughly 90% of it is per-review fact this change does not touch.

So the argument rests on the other two limbs. **Recurrence:** 68–93 across five rows is ~14–19 words of re-derivation per multi-cycle row, recurring forever, against 176 once — break-even around the tenth to thirteenth row. **Permanence:** rows are append-only, so a row written under an unstated convention is wrong for good, and no later row inherits a convention a previous row stated in prose. An earlier draft of this entry cited the whole 1,012 as the saving; that overstates by 11–15×, this change's own review measured it, and the corrected figure is recorded here because a future session citing D-179 as precedent for prose growth would otherwise inherit the inflated one.

## Evidence

[#149](https://github.com/Grimblaz-and-Friends/tradecraft/issues/149), the affirmed artifact at [comment 5411145261](https://github.com/Grimblaz-and-Friends/tradecraft/issues/149#issuecomment-5411145261) and its affirmation at [comment 5411148218](https://github.com/Grimblaz-and-Friends/tradecraft/issues/149#issuecomment-5411148218). The owner ruled on all three forks the artifact carried. Warrant: field-run gap 8 and routing items 1.2 and 1.4 of the coverage design ([#122](https://github.com/Grimblaz-and-Friends/tradecraft/issues/122)).

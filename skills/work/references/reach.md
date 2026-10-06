# Builder reach

**Loaded when** a builder has returned, the entrance reports reach uncertainty or removals, or the holder names readiness, proof or release reporting.

After every builder turn, the entrance measures that turn's authored removals; flagged items need the holder's head-bound reach reading before readiness, proof or release reporting, because criterion completion alone can miss content the turn removed outside the agreed work. This applies on every lane, including mechanical. No flagged items means no removal reading. An unmeasurable turn returns to the holder for true-range recovery or an explicit PR-superset settlement, even when that proved superset is empty.

## Read the report and return together

After a builder turn, read the builder's returned "should also go" notes alongside the reach report before settling its reach or continuing the change. Read both even when the report flags nothing: the notes recommend changes to content the builder kept; reach measures what it actually removed. A recommendation neither authorizes an unrequired removal nor supplies a reach disposition.

The report's additive `reach` object has schema version 1, current head, selected lineage and instalment, and ordered turns naming dispatch, stage, bundle, before/after revisions, measurement basis, flags, uncertainty and accepted reading source or outstanding paths. Its states are:

- `not-due`: no observed launched builder turn.
- `clear`: every measurable turn has no flags or complete accepted coverage, and each returned unmeasurable turn has an accepted settlement. Original uncertainty remains visible after settlement.
- `reading-required`: a measured turn has unaccounted flags.
- `unmeasurable`: a returned turn's range, ordering, records or attribution cannot be proved; the report names the missing fact and its stable turn reference.
- `pending`: live or unresolved cleanup evidence leaves recovery authoritative. A reach reading does not resolve recovery or buy another builder.

Flags remain visible while the normal next step is synchronization, floor, review repair or recovery. A later flag-free turn does not cancel an earlier account. The same path in two turns owes two accounts. A later restoration is a disposition, rather than an automatic clearance.

## What was measured

The entrance retains launched build, floor and review-disposition turns in the selected implementation lineage, including builds repairing use findings or resolving catch-up. It uses target attribution rather than successful term delivery, so a launched failure's committed changes remain visible. A proved unlaunched attempt contributes no turn. Sibling instalments and other lineages do not supply this one's evidence. Released lineage evidence remains relevant to its open implementing PR.

The request's `revision_before` and run's `revision_after` resolve to full commits in the implementing repository. The entrance proves their first-parent path. Equal proved endpoints are empty; a missing range never becomes today's HEAD or an older success. Missing or incompatible revisions, unavailable objects, incomplete records, uncertain attribution/order, changed ancestry and unsupported merge output name an uncertainty.

Without a merge, the turn's endpoint diff flags every deleted file (empty and binary included) and every textual file with more removed than added lines. Equality and growth do not flag. Binary modifications have unavailable line counts. External diff, textconv, renames and whitespace-ignore options do not determine these counts; a moved file appears as deletion plus addition.

With merges, the entrance partitions the first-parent history into maximal non-merge stretches and merge commits. It measures each stretch's endpoints and each merge's full `-c` combined patch with exact NUL-delimited raw paths. A line counts as added only with `+` in every parent column, and as removed only with `-` in every column, once for shared content. Mixed columns are carried content. A path deleted relative to all parents is a deletion. Counts aggregate across these authored portions, retaining deletion events and contributing revisions. A result identical to a parent contributes no resolution edit. First-parent merge totals, combined numeric statistics and remerge conflict-marker cleanup are not this measurement.

A flagged path is labelled a removed test when a case-insensitive directory component is `test`, `tests`, `__tests__`, `spec` or `specs`; the basename begins `test_`, `test-` or `test.`; its stem ends `_test` or `_spec`; or it has a `.test` or `.spec` segment before its extension. Conventional camel-case `Test*`, `*Test`, `*Tests`, `*Spec` and `*Specs` stems also count (`Test*` needs a camel-case boundary after `Test`). Names such as `contest.md` and `latest.json` do not count. This fixed predicate identifies paths, not test declarations; it has no repository setting or size threshold.

## Account for removals

Use the authorized issue-comment marker and fenced JSON contract in `markers.md`:

```text
<!-- tradecraft:reach-reading:v1 head=FULL_COMMIT_SHA -->
```

Every flagged item needs its exact path, a nonempty explanatory `basis`, and one lawful disposition with its named reference:

- `row-or-criterion` with `requirement`: the governing row or criterion requiring the removal/rewrite.
- `generator` with `generator`: the command or source producing this generated file.
- `restored` with `restored_by`: the later returned builder's dispatch ID and full head. Inspect the restored content; the entrance verifies identity and order, not adequacy.
- `owner-ruling` with `ruling_source`: the recorded owner's ruling permitting it.

Send anything without one of those bases back to the builder to restore before posting the reading. There is no rejection disposition authorizing retention. Read the criterion, generator or ruling you cite: the entrance enforces coverage, while the holder owns the truth of each account.

An ordinary `turns` entry covers the complete reported turn and follows its return. A reading can explicitly cover multiple outstanding turns. On initial adoption of this mechanism, account at the proved current head for each listed historical turn, retaining its identity and endpoints. Ordinary descendant progress retains accepted coverage; a newly flagged turn needs its own. Quoted, malformed, unauthorized, wrong-surface, partial, duplicate, extraneous or stale claims discharge nothing. A reach reading is never a whole-change `holder-reading`, an amended reading, artifact settlement or delivery of amended terms.

## Settle missing historical evidence

Prefer recovering the actual turn's endpoints from retained native run or other contemporaneous revision evidence. Preserve the original bundle. Record the dispatch, full `before` and `after`, and evidence `basis` in `recovered_ranges`. The entrance recomputes the range and validates lineage, ordering and ancestry; put complete recovered flags in `turns`. A recovered empty range needs no invented removal item. Recovery cannot substitute for an already measurable range.

When the true range cannot be established, settle the named turn by the implementing PR's superset. If no PR exists, open the draft implementing PR through the existing holder-owned route; reach does not block that step. Resolve ambiguous PR/instalment identity first.

The report pins the PR number, actual base revision, merge base and current head. Its superset measures each authored commit, using the same combined-parent instrument for merges. It conservatively retains the union of deletions and paths with any authored removed line, including ordinary flags; growth or later restoration never cancels candidates. Base-carried merge changes remain excluded. This conservative rule belongs only to the fallback; the ordinary range still uses net shrink.

In `superset_settlements`, name the report's exact `turn_reference` (a dispatch or stable bundle diagnostic when the dispatch is absent), the reason the true range cannot be measured, `basis: "pr-superset"`, all four PR bounds, and complete lawful `items` coverage. Each named uncertain turn needs its own settlement, even when sharing the same superset. An empty proved superset still needs its explicit settlement account. Naming superset alone or writing waiver prose settles nothing. Accepted coverage clears that turn's reach refusal while preserving its original uncertainty; a failed original ancestry or attribution check is not a second prerequisite for this route.

If superset objects are unavailable, restore the named base/head objects (for example by fetching their actual revisions), then retry. Restore local Git read capability after a read failure. For unsupported original merge output, regenerate canonical combined output from the superset objects. The read-only entrance fetches and repairs nothing; unavailable evidence is repaired, never waived or treated as empty reach. Ordinary descendant progress retains an accepted account; a rebase or amendment replacing its ancestry needs a new current-head account.

## Progression and custom dispatches

Unread flags or unsettled historical uncertainty prevent recommendations for readiness, proof and release reporting. Named `run ready-reviewers`, `run proof` and `run release-report` independently check reach and refuse before their effects, naming the head/turn and missing account or evidence. Floor, repair, catch-up and live/stopped recovery retain their own routes. Already-ready repairs owe the same new coverage. The required change-proof gate and proof document retain their wire contract; a stale proof or old green check cannot clear reach.

Every composed builder stage carries this instruction. Carry it yourself when composing a custom builder dispatch; supplied dispatches remain byte-for-byte:

> Remove or rewrite existing content only where a governing row or criterion requires it; keep the rest, and name in your return any additional removal or rewrite you recommend.

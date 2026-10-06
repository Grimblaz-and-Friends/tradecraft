# Builder reach

**Loaded when** a builder has returned, the entrance reports reach uncertainty or removals, or the holder names readiness, proof or release reporting.

After every builder turn, the entrance measures that turn's authored removals; flagged items need the holder's head-bound reach reading before readiness, proof or release reporting, because criterion completion alone can miss content the turn removed outside the agreed work. This applies on every lane, including mechanical. No flagged items means no removal reading. An unmeasurable turn returns to the holder for an explicit current-head PR-superset settlement, even when that proved superset is empty.

## Read the report and return together

After a builder turn, read the builder's returned "should also go" notes alongside the reach report before settling its reach or continuing the change. Read both even when the report flags nothing: the notes recommend changes to content the builder kept; reach measures what it actually removed. A recommendation neither authorizes an unrequired removal nor supplies a reach disposition.

The report's additive `reach` object has schema version 1, current head, selected lineage and instalment, and ordered turns naming dispatch, stage, bundle, before/after revisions, measurement basis, flags, uncertainty and accepted reading source or outstanding paths. Its states are:

- `not-due`: no observed launched builder turn.
- `clear`: every measurable turn has no flags or complete accepted coverage, and each returned unmeasurable turn has an accepted settlement. Original uncertainty remains visible after settlement.
- `reading-required`: a measured turn has unaccounted flags.
- `unmeasurable`: a returned turn's range, ordering, records or attribution cannot be proved; the report names the missing fact and its stable turn reference. An unexpected reach-evaluation failure is also reported here with its error type and message, without crashing the entrance or masking a run's original refusal.
- `pending`: live or unresolved cleanup evidence leaves recovery authoritative. A reach reading does not resolve recovery or buy another builder.

Flags remain visible while the normal next step is synchronization, floor, review repair or recovery. A later flag-free turn does not cancel an earlier account. The same path in two turns owes two accounts. A later restoration is a disposition, rather than an automatic clearance.

## What was measured

The entrance selects retained build, floor and review-disposition bundles by the request's repository and issue and the implementing PR's head branch, with the instalment where one is named. This includes builds repairing use findings or resolving catch-up and launched failures. Before a PR exists, the registered branch plays the same role. Recipient roots, holder roots and active/released registry rows do not select or exclude a PR's reach. A proved unlaunched attempt contributes no turn.

Git is read only through the holder checkout supplied by `--root`, never through a bundle's recorded worktree root. A turn is measured when its recorded `revision_before` and `revision_after` are full commit objects available there and on the PR head's first-parent ancestry. Equal proved endpoints are empty. A missing range never becomes today's HEAD or an older successful range.

Missing, invalid or unavailable endpoints, malformed or unreadable records, ambiguous ordering, missing attribution, changed ancestry and unsupported merge output each name an unmeasurable entry. These entries share one PR-level settlement obligation. The entrance correlates authorized builder-session markers with retained native session/vendor returns across the issue, with each return no later than its marker. A session accounted for by another branch belongs to that branch; a session with no matching retained bundle names its own uncertainty even beside retained turns. A later resume cannot conceal a lost earlier return.

Only the latest actual turn with a live launcher or recipient, unresolved spawn, or unproved cleanup is pending under recovery. Any other incomplete or failed turn has returned for reach purposes: its available endpoints are measured, or it is unmeasurable. A foreign-host liveness result alone does not create permanent pending reach. Historical-launch timestamps are identified as such in the report when native return timestamps are missing; they are not invented revision evidence. Unexpected evaluation failures name a settleable uncertainty, without masking another entrance error.

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

Settle missing historical evidence with one current-head PR-superset account. There is no recovered-range carrier. Preserve the original bundles. If no PR exists, open the draft implementing PR through the existing holder-owned route; reach does not block that step. Select the actual PR and named instalment first.

The report pins the PR number, actual base revision, merge base and current head, all read through the holder checkout. Its superset measures each authored commit using the same combined-parent instrument for merges. It conservatively retains the union of deletions and paths with any authored removed line, including ordinary flags; growth or later restoration never cancels candidates. Base-carried merge changes remain excluded. This conservative rule belongs only to the fallback; ordinary turn ranges still use net shrink.

In `superset_settlements`, name every covered entry's exact `turn_reference` (a dispatch or stable diagnostic), its uncertainty `reason`, `basis: "pr-superset"`, the four PR bounds, and complete lawful `items`. One reading may account for all named historical uncertainties with the same computed superset. Each entry is explicit, including when that superset is empty. Naming superset alone or writing waiver prose settles nothing. Accepted coverage clears reach while preserving the original uncertainty; the failed range, attribution or registration does not need to pass again.

The account's head equals the evaluated PR's current head. An ancestor account survives descendant progress only when no unmeasurable turn has returned after it. The entrance checks all uncertain returns against the reading's time and proves that later measured turns cover the entire first-parent suffix from the account head to today's PR head. A later or undated uncertainty, or unexplained intervening commits, needs a new current-head account. This prevents an arbitrary older empty head from covering a turn whose return revision is missing. Missing objects supply no invented historical endpoint. The actual PR base and merge base are recomputed; there is no per-turn historical base or neighboring-range recovery. Replaced ancestry needs a new current-head account. Ordinary measured `turns` accounts keep their existing contract.

If required superset objects are unavailable, fetch the named actual base/head revisions into the holder checkout, then retry. Restore local Git read capability after a read failure. Unsupported original merge output is regenerated canonically from the superset objects. The read-only entrance fetches and repairs nothing; unavailable evidence is repaired, never waived or treated as empty reach.

## Progression and custom dispatches

Unread flags or unsettled historical uncertainty prevent recommendations for readiness, proof and release reporting. Named `run ready-reviewers`, `run proof` and `run release-report` independently check reach and refuse before their effects, naming the head/turn and missing account or evidence. Floor, repair, catch-up and live/stopped recovery retain their own routes. Already-ready repairs owe the same new coverage. The required change-proof gate and proof document retain their wire contract; a stale proof or old green check cannot clear reach.

Every composed builder stage carries this instruction. Carry it yourself when composing a custom builder dispatch; supplied dispatches remain byte-for-byte:

> Remove or rewrite existing content only where a governing row or criterion requires it; keep the rest, and name in your return any additional removal or rewrite you recommend.

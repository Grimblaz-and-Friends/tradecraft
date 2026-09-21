# Recording and reading change paths

**Loaded when** writing the pull request body's path-departure paragraph, or when the observed cadence says to read across changes that have landed.

## Leave the unmarked part of the path

**The pull request body carries one paragraph beginning `**Path departures:**`: name each stage the change skipped, bypassed or stalled at and why, or say the expected path ran without a departure; do not restate the marker timeline.**

A skipped stage was not required by the path that applied. A bypassed stage was required and the change continued without it. A stalled stage was attempted but could not advance. Absence of a marker alone proves none of the three, which is why the holder records the call rather than asking the later reader to infer it.

The paragraph sits beside the change's existing record. It is the same convention in an adopting repository: no repository identity, product name or local tool is part of it.

## When the read fires

While a repository-specific evaluation already has a status read, the holder reads when it observes that status read or when five changes have merged after the interval's earlier bound, whichever comes first. The cutoff recorded by a read becomes the next interval's earlier bound and starts its merge count. Once that evaluation ends, five merged changes is the cadence.

The repository set is the practice repository identified by the installed plugin, the products named by its repository-owned work configuration, and the shared gate named by those products' configured gate job. Every merged pull request in that set counts; the read does not inherit a scorer's exclusions.

Use the previous note's recorded cutoff as the earlier bound. For the first read during an existing evaluation, use that evaluation's opening instant. For a first read with neither a previous note nor an existing evaluation, capture one UTC cutoff, use it as the earlier bound, and record it in a note that reads no interval; the next read starts there. Nothing before adoption is in scope because it could not carry the paragraph.

For every other read, capture one UTC cutoff immediately before the first repository query. For each repository in the configured set, run:

```text
gh api --method GET "repos/<owner>/<repository>/pulls?state=closed&sort=updated&direction=desc&per_page=100" --paginate --jq '.[] | select(.merged_at != null and .merged_at > "<earlier-bound-UTC>" and .merged_at <= "<cutoff-UTC>") | [.merged_at, .html_url] | @tsv'
```

The holder orders the returned rows by `merged_at`, counts across repositories, reads every row in the interval and records the cutoff in the note. A pull request merging after the cutoff belongs to the next interval even when it merges before the note is posted. This is an observed cadence, not a job, hook, score or other mechanism.

While the existing evaluation runs, its record issue carries the note. Afterwards all notes land on one standing issue for the read; the first holder who needs that destination opens it once.

## What the holder reads

For each landed change, read only:

- the authorized marker timeline on its work issue, ordered by GitHub creation time and retaining repeated markers, revisions and head values;
- the pull request body, including its existing record and `**Path departures:**` paragraph;
- the durable dispatch bundles belonging to the change, where retained.

Do not read chat transcripts. Missing evidence stays unknown rather than being reconstructed.

The ordered markers show what ran. The path-departure paragraph supplies the holder's unmarked calls. The dispatch bundles supply the request, returns, native usage, elapsed time where known and the products of each dispatch. Keep native quantities separate and keep unknowns unknown.

Derive the expected path from the practice version, repository configuration, change classification, bought use and review lane that applied to that change; there is no single sequence every change should resemble. Then state what the reader would have done in the same situation, clearly as a counterfactual.

Compare the actual, expected and reader paths by the evidence each actual path produced and what it cost: defects or corrections found, use and review findings, rework, stalls, dispatch usage, elapsed time and owner attention where the records establish them. Do not credit an unrun counterfactual with a finding it never produced. A difference is not a defect, and where the evidence does not support a better path the note says so.

## The note and its exits

Write one short narrative note for the interval. Name the changes and records consulted, describe each path and its material departures, compare outcomes and costs, and report no finding when the read found none.

The note has no template, field list, score, severity scale or required finding count.

Every finding takes exactly one exit:

- retain it in the reader's memory when it changes only that reader's future judgment and asks for no durable practice change;
- file an incident through the existing practice-failure route when the practice caused or exposed product harm, naming that harm and the record that demonstrates it;
- put a new implementation brief to the owner when a better path generalizes beyond the observed change.

Only the third exit asks the owner to rule. The note is not itself the brief, incident or memory entry, and an exit is incomplete until its existing route's requirements are met.

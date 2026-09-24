# The proof document

**Loaded when** composing, posting, or consuming `tradecraft:proof:v1`, or when running the holder-owned proof and reviewer-readiness commands.

## One document per pull-request head

`run proof` gathers the record again, composes one schema-version-1 object, and creates or updates the authenticated marker producer's pull-request comment for the current head. The holder supplies no body, head, evidence result, staffing value, or bundle identity, because the document is an output of the record rather than another claim about it. A retry rereads comments before deciding whether a write is still needed; documents for older heads stay unchanged, and competing authorized documents at one head are refused.

The command refetches the head and base before and after publication. A move before the write requires recomposition; a move during the write leaves the older-identity document in place and does not report current completion. When changed paths buy no use, the same comment carries the generated current-head `no-use` compatibility carrier and a policy-derived reason. A bought use keeps its source head and original note rather than manufacturing a current-head copy.

The comment begins with:

```text
<!-- tradecraft:proof:v1 head=FULL_HEAD -->
```

It then carries a fenced JSON object followed by a readable rendering of that same object. The JSON schema and interoperability fixtures are shipped beside this reference as `proof-v1.schema.json` and `proof-fixtures/`. Arrays have deterministic order and serialization uses sorted keys, two-space indentation, ASCII escapes and one final line feed, so unchanged evidence produces unchanged content.

## Evidence, declarations, and diagnostics

The object has nine top-level fields: `schema_version`, `identity`, `policy`, `floor`, `use`, `reviewers`, `dispositions`, `declarations`, and `diagnostics`.

- `identity` names the work, repository, issue, pull request, full head and producing plugin version.
- `policy` identifies the work configuration and use-policy path, repository revision and SHA-256 digest used to compose the result. The digest is over the raw Git blob at that revision, not checkout bytes. Proof refuses a present policy with staged, unstaged, untracked, deleted, renamed or conflicted changes and names the commit-or-revert remedy, because the document must describe the policy it used; an optional work configuration absent from both the revision and worktree retains `sha256: unavailable`.
- `floor`, `use`, `reviewers`, and `dispositions` retain public source identities. A source names its kind, repository, numeric or textual identity, URL, author, timestamp and relevant revision without copying the source body.
- `floor.checks` retains check id, exact name, application, workflow and run identities where available, head, status, conclusion and timestamps. Different workflows sharing a display name remain different records; only genuine reruns within one workflow compete by start time and numeric check id. A check leaves this ordinary set only when the base branch's required-workflow rule and the run's top-level source file positively identify it as a required gate.
- `use` distinguishes current-head, ancestor, generated and missing evidence. An ancestor use lists every intervening commit and both names of renamed paths; any use-bought path in any intervening commit makes it stale, including a change later reverted.
- `declarations` carry machine-local dispatch facts: dispatch id, requested settings, observed vendor/model/effort where the runtime exposed them, fallback, staffing and revision. Missing, ambiguous, incompatible, late or contradictory records use `status=unverifiable` and a reason; marker text never fills the missing value.
- `diagnostics` retain missing, invalid, ambiguous, stale or unavailable inputs. No diagnostic is converted into a success boolean.

The producer never writes a `verified` field or line. The readable rendering labels public material `evidence:`, local record material `declared:`, and limitations `diagnostic:`. The gate alone emits `verified:` after independently reading the public records; accessible local execution remains a declaration even when internally consistent.

## Applicable use evidence

A current-head use remains the ordinary case. An older use applies only when its evidence head is an ancestor of the pull-request head, the complete intervening commit list is available, and each commit changes no path the trusted use policy buys. The classification reads each commit rather than the final net diff and includes both `filename` and `previous_filename` for a rename. The relaxation applies only to use: floor and generated no-use evidence stay current-head.

## Publication and gate reruns

Posting proof does not certify readiness and may expose incomplete evidence. The command reads the pull request base branch's active rules and resolves each required workflow's source repository and exact path; it joins a run through the fixed read-only query for that run's top-level workflow file. After confirmed publication, it requests one rerun per distinct positively matched current-head run carrying complete run and workflow identities. Pending, stale, absent, `none` and `unidentified` sources perform no speculative rerun and report why; a display name and a called reusable workflow are never matching authority, and submission is never reported as a pass. The returned JSON names the comment action and each source, run identity, request state and observed pending result.

## Reviewer readiness

`run ready-reviewers` validates the current-head floor and applicable use evidence, applies `.tradecraft/work.json`'s optional `reviewer_label`, then marks a draft pull request ready and verifies both results. Omitted or null `reviewer_label` means no label is declared. The label is applied before the ready transition so ready-triggered integrations can see it. On an already-ready pull request the command repairs a missing label without toggling draft status; after a partial failure, repeating the command finishes the remaining operation.

Neither holder-owned command launches an agent, repairs the implementation, or advances another stage. The ordinary entrance waits for every configured reviewer separately, treats a review-limit, rate-limit, skipped, limited, upgrade or running notice as not reviewed, and requires authorized first-line dispositions on every top-level inline reviewer thread before recommending a fresh proof. A failed or pending gate evaluation then waits; it never routes back to the executable floor.

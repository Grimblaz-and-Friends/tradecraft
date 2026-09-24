# Connected reviewers

**Loaded when** configuring a connected reviewer, marking a pull request ready, dispositioning what one posted, or buying a second look after a non-mechanical fix.

Every connected reviewer fires once per pull request, when the pull request is marked ready, never per push. Open the pull request as a draft; run the executable floor and the required experience session, or post its declining line; then mark ready and apply the `reviewers` label. **Every change carries one or the other before ready, mechanical work included** — the line costs a sentence and is what makes ready mean proven. Codex fires on ready without that label. A repository with no connected reviewer owes nothing here.

On issue-backed product work, the `work` cell performs the state read: it returns waiting while a required reviewer has not run and sends only undispositioned threads to the builder. It does not retrigger a reviewer or turn the label into a stage marker.

The `reviewers` label gates Greptile and CodeRabbit. Removing and re-adding it may buy a second look after a non-mechanical fix; that look is permitted, not owed, and a mechanical fix buys none.

Every comment ends in its own thread, by a fix or a one-line reply carrying one of these dispositions: `fixed`; `fixed — nothing else found it`; `fixed in #<N>`; `yours — in the release report`; `declined — <why it earns no end>`; `duplicate of <the earlier comment>`; `lapsed — <the rule we do not run>`. **The list is closed, and it covers every end an unfixed finding has** — a true one you are not fixing here leaves by the follow-up pull request that carries it or by the one ask to the owner, so each has a word and neither is a silence. **A true comment that earns no end at all is declined here, on the work**, which is what the charter already does with a decline outside a review: a finding failing the `filing` cell's bar takes neither of its two ends, and without a word for that it reads as a builder who never answered. A fix still gets its one-line `fixed`, so a reviewer's silence remains distinguishable from the builder's. Nothing is bundled, receipted or recorded elsewhere.

Append the `work` cell's completion marker to the final disposition reply for that reviewer, replacing `NAME`:

```text
<!-- tradecraft:connected-reviewer:v1 name=NAME status=complete -->
```

Copy each block whole to the filename named above it.

## `greptile.json`

```json
{
  "autoReview": ["open"],
  "labels": ["reviewers"]
}
```

`autoReview: ["open"]` covers opening, reopening, ready-for-review and the trigger label. `triggerOnUpdates` is absent deliberately, because it triggers per-push reviews. Drafts are skipped by the reviewer.

## `.coderabbit.yaml`

```yaml
reviews:
  auto_review:
    enabled: true
    auto_incremental_review: false
    drafts: false
    labels:
      - reviewers
```

`auto_incremental_review: false` stops per-push reviews. `drafts: false` is written rather than inherited from a movable default. Add the repository's own branch names under `base_branches` where it wants to restrict the target branches.

## `AGENTS.md` — `## Code Review Rules`

```md
## Code Review Rules

Review pull requests only when they are marked ready; skip drafts. Post only P0/P1 findings a consumer would act on wrongly. Name the wrong action, not the wording. Where this repository's own convention contradicts a general rule, the convention wins and the comment says so. A deletion is as good a finding as an addition.
```

Codex has no configuration key for this contract; the section in the repository's own always-on agent file is the configuration.

## `connected-review.yml`

Copy this block whole and set the `CLAUDE_CODE_OAUTH_TOKEN` repository secret. Before activation, install the pinned Python and Claude CLI on a private repository's self-hosted runner; its hosted `report` job still consumes a small amount of hosted time when it runs. Add `github-actions[bot]` to `connected_reviewers` only after that repository's replay and identity checks pass. Removing and re-adding `reviewers` then requests the permitted second look at a new head; use the workflow's explicit dispatch to retry a skipped attempt.

```yaml
name: connected-review

on:
  pull_request_target:
    types: [ready_for_review, labeled]
  workflow_dispatch:
    inputs:
      pr_number:
        description: Pull request number to retry
        required: true
        type: string

concurrency:
  group: connected-review-${{ github.repository }}-${{ github.event.pull_request.number || inputs.pr_number }}
  cancel-in-progress: false

env:
  TRADECRAFT_REPOSITORY: Grimblaz-and-Friends/tradecraft
  TRADECRAFT_REVIEWER_REF: REPLACE_WITH_REVIEWED_COMMIT
  CLAUDE_CLI_VERSION: 2.1.261
  REVIEW_OWNER_LOGIN: Grimblaz

jobs:
  prepare:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: read
    outputs:
      admitted: ${{ steps.eligibility.outputs.admitted }}
      visibility: ${{ steps.eligibility.outputs.visibility }}
      head: ${{ steps.eligibility.outputs.head }}
      reason: ${{ steps.eligibility.outputs.reason }}
    steps:
      - name: Fetch trusted reviewer
        uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09
        with:
          repository: ${{ env.TRADECRAFT_REPOSITORY }}
          ref: ${{ env.TRADECRAFT_REVIEWER_REF }}
          path: .connected-review-runtime
          persist-credentials: false
      - name: Set up Python
        uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1
        with:
          python-version: "3.14"
      - name: Check eligibility
        id: eligibility
        env:
          GH_TOKEN: ${{ github.token }}
        run: python .connected-review-runtime/lib/connected_review.py eligibility

  review:
    needs: prepare
    if: needs.prepare.outputs.admitted == 'true'
    runs-on: ${{ needs.prepare.outputs.visibility == 'private' && 'self-hosted' || 'ubuntu-latest' }}
    timeout-minutes: 120
    permissions:
      contents: read
      pull-requests: write
    outputs:
      status: ${{ steps.review.outputs.status }}
      cause: ${{ steps.review.outputs.cause }}
    steps:
      - name: Fetch trusted reviewer
        uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09
        with:
          repository: ${{ env.TRADECRAFT_REPOSITORY }}
          ref: ${{ env.TRADECRAFT_REVIEWER_REF }}
          path: .connected-review-runtime
          persist-credentials: false
      - name: Set up hosted Python
        if: needs.prepare.outputs.visibility == 'public'
        uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1
        with:
          python-version: "3.14"
      - name: Install hosted Claude CLI
        if: needs.prepare.outputs.visibility == 'public'
        run: npm install --global @anthropic-ai/claude-code@2.1.261
      - name: Run finder and checker
        id: review
        env:
          CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          GH_TOKEN: ${{ github.token }}
        run: >-
          python .connected-review-runtime/lib/connected_review.py review
          --finder-prompt ".connected-review-runtime/skills/connected-review/references/finder.md"
          --checker-prompt ".connected-review-runtime/skills/connected-review/references/checker.md"

  report:
    needs: [prepare, review]
    if: always() && needs.prepare.result == 'success' && needs.prepare.outputs.admitted == 'true'
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      issues: write
      pull-requests: read
    steps:
      - name: Fetch trusted reporter
        uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09
        with:
          repository: ${{ env.TRADECRAFT_REPOSITORY }}
          ref: ${{ env.TRADECRAFT_REVIEWER_REF }}
          path: .connected-review-runtime
          persist-credentials: false
      - name: Set up Python
        uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1
        with:
          python-version: "3.14"
      - name: Reconcile review or report skip
        env:
          GH_TOKEN: ${{ github.token }}
          REVIEW_CAUSE: ${{ needs.review.outputs.cause }}
          REVIEW_RESULT: ${{ needs.review.result }}
          REVIEW_RUN_ID: ${{ github.run_id }}
        run: python .connected-review-runtime/lib/connected_review.py report
```

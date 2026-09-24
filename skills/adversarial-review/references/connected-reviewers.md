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

## `connected-review.yml` in the repository's GitHub Actions workflows directory

Copy this block whole to that directory and set the `CLAUDE_CODE_OAUTH_TOKEN` repository secret. Before activation, install `gh`, Python 3.14 and Claude CLI 2.1.280 on a private repository's self-hosted runner. The hosted `prepare` job, and the hosted `report` job when it runs, consume a small amount of hosted time. After that repository's replay and identity checks pass, its enabling change sets the reviewer ref to the frozen merged commit on the default branch, sets the `CONNECTED_REVIEW_ENABLED` repository variable to `true`, and adds `github-actions[bot]` to `connected_reviewers`; the ref below and the absent variable deliberately leave this copy dormant, and the ref is not a release pin. Two eligible events may prepare concurrently, but their review jobs serialize per pull request; the second rechecks the head and buys nothing when the first already completed it. A report also runs after preparation fails, re-derives eligibility without checking out pull-request content, and posts a skip only when it can establish that the attempt was eligible; an unreadable eligibility state stays visibly failed and posts nothing. Removing and re-adding `reviewers` requests the permitted non-mechanical second look at a new head; use the workflow's explicit dispatch to retry a skipped attempt.

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

env:
  TRADECRAFT_REPOSITORY: Grimblaz-and-Friends/tradecraft
  TRADECRAFT_REVIEWER_REF: SET_BY_ENABLEMENT_TO_FROZEN_MERGED_COMMIT
  CLAUDE_CLI_VERSION: 2.1.280
  REVIEW_OWNER_LOGIN: Grimblaz

jobs:
  prepare:
    if: vars.CONNECTED_REVIEW_ENABLED == 'true'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: read
    outputs:
      admitted: ${{ steps.eligibility.outputs.admitted }}
      visibility: ${{ steps.eligibility.outputs.visibility }}
      head: ${{ steps.eligibility.outputs.head }}
      reason: ${{ steps.eligibility.outputs.reason }}
      number: ${{ steps.eligibility.outputs.number }}
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
    concurrency:
      group: connected-review-${{ github.repository }}-${{ needs.prepare.outputs.number }}
      cancel-in-progress: false
    permissions:
      contents: read
      pull-requests: write
    outputs:
      status: ${{ steps.review.outputs.status }}
      cause: ${{ steps.review.outputs.cause }}
      usage: ${{ steps.review.outputs.usage }}
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
        run: npm install --global @anthropic-ai/claude-code@2.1.280
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
    if: >-
      always() && vars.CONNECTED_REVIEW_ENABLED == 'true' &&
      (needs.prepare.result != 'success' || needs.prepare.outputs.admitted == 'true')
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
          PREPARE_RESULT: ${{ needs.prepare.result }}
          REVIEW_CAUSE: ${{ needs.review.outputs.cause }}
          REVIEW_RESULT: ${{ needs.review.result }}
          REVIEW_RUN_ID: ${{ github.run_id }}
          REVIEW_USAGE: ${{ needs.review.outputs.usage }}
        run: python .connected-review-runtime/lib/connected_review.py report
```

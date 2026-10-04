# Lab reviewer releases

**Purpose:** operate the lab's shared reviewer and its manual release tag. **Audience:** the Steward releasing a reviewer and the holder rolling out its callers. **Success:** each release is identified by the completed review that ran it, private access is proved before the first stable caller lands, and a failed later release has a callable rollback target.

## Release control

The jobs and `CLAUDE_CLI_VERSION` live in `.github/workflows/connected-review-shared.yml`. Tradecraft's `.github/workflows/connected-review.yml` calls that workflow at `@main`; the other lab repositories call it at `@reviewer-stable`. The caller grants the union of the jobs' permissions and inherits secrets. Admission and reporting run hosted; an admitted private review runs on the caller's self-hosted runner. Only the finder step receives the Claude credential.

The shared workflow captures its own `job.workflow_repository`, `job.workflow_file_path` and `job.workflow_sha` before checkout. Every job validates that identity and its runtime checkout. Reviews name that tradecraft SHA and the verified Claude CLI version before the final attempt marker. Skip notices name the configured pin without claiming the CLI or finder ran. A moving tag is never resolved again inside a run. A full rerun may resolve it afresh, so read each posted review's provenance rather than assuming two attempts used the same release. GitHub documents the [job identity](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#job-context) and [runner and rerun rules](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations).

The shipped adopter template and its reference keep the copy-whole workflow with a frozen reviewer commit. Direct invocations post provenance only when their calling workflow supplies it. Lab releases do not change an adopter's chosen reviewer.

## First release and rollout

1. The holder verifies the gate half, change-proof #46, has landed and the lab's required gate resolves to that merged revision. Only then may #847's shared workflow and tradecraft stub merge. The Steward merges tradecraft and change-proof; product merges remain the owner's.
2. After #847 merges, obtain the next eligible tradecraft review at a head not already reviewed. Its completed posted review must show finder usage, the exact shared-workflow commit from merged `main`, and the verified CLI version. Findings are allowed. A skip, successful oversize preflight, existing same-head review, or #847's own pre-merge review cannot justify the tag: none exercises the newly merged reviewer. If workflow identity is unavailable or disagrees, hold release and return the observed failure to the builder through the holder before changing the selected identity approach.
3. Before the tag exists, the holder runs one private trial in each of Organizations-of-Verra, Daemon, Windgust-Questbook and Countdown-Clash, pinned to the merged release SHA. In each existing private repository, use a disposable base branch carrying the caller below at that immutable SHA, with a ready pull request targeting it, opened by the token owner and labelled to buy one review. Require a completed posted review on that caller's self-hosted runner naming the release SHA and verified CLI. A queued job proves no execution. Record each outcome on #847 before closing the trial pull request and deleting its branches. Unreadable policy is unproved access; a demonstrated organisation-policy prohibition goes through the holder to the owner with the required setting. A trial failure holds the tag and all downstream stubs, and returns to the builder for a tradecraft repair or to the owner for an organisation setting.
4. The Steward creates `reviewer-stable` at the exact reviewed and privately trialled release SHA. If `main` advanced, use the reviewed workflow SHA that contains the intended release, not the current tip. Verify that the target contains the callable workflow, record creation on #683 with its evidence, then let the holder proceed with the five carrier issues in sequence. Each carrier uses its own issue and the affirmed ordinary/mechanical lane. The Steward merges change-proof's stub; the owner merges the four products' stubs. No durable downstream stub lands before the gate half and tag.
5. Observe the first product review through an actual stable stub, retaining its posted revision, verified CLI, run/job and self-hosted runner identity. A copied workflow does not test the tag. If this initial production call fails, hold the remaining carriers and return the evidence for repair. There is no earlier callable tag target to restore at first creation.

The private trial evidence records repository, release SHA, base and head, run and job links, runner identity, verified CLI and posted review. Raw output stays outside commits; any retained tree summary names each evidence file's revision, SHA-256, size and reproducing command. Trials belong to the holder after merge; they are access checks, not a standing private canary service.

## Later release moves

Consider a move only after a merge changes reviewer code, the finder prompt, the shared workflow or the lab CLI pin. An unrelated tradecraft merge buys no move. Require one subsequent eligible tradecraft review that ran the finder and posted, with any number of findings, naming the released workflow commit and verified CLI. Select that SHA even if `main` has since advanced, and verify it includes the intended change.

The Steward moves the tag manually after recording the previous callable target and the qualifying review. The owner may hold or reverse a move. Observe the first product review actually using the moved stable stub. If it fails where the previous release worked, restore the previous callable target and record the failure and verified rollback. Do not restore a historical copy-whole pin: it lacks the callable workflow.

Each creation, move or rollback is recorded on #683 with the release SHA, completed tradecraft review and run links, previous target (absent for creation), verified new target, private trial links at first creation, first product observation, and any failure or rollback. The standing page carries observations; this document carries the procedure.

## Caller for the later carriers

Use this exact stub in each carrier; a private trial replaces `reviewer-stable` with the merged release's full SHA. Tradecraft's own stub uses `main`.

```yaml
name: connected-review

on:
  pull_request_target:
    types: [ready_for_review, labeled]

jobs:
  connected-review:
    permissions:
      actions: read
      contents: read
      pull-requests: write
    uses: Grimblaz-and-Friends/tradecraft/.github/workflows/connected-review-shared.yml@reviewer-stable
    secrets: inherit
```

The entrance, gate and cancellation reporter accept the exact leaf job name `review`, directly or following nonempty caller names separated by ` / `. Receipt credit still requires the calling repository's own fixed workflow, `pull_request_target`, matching run/head and completed successful job. Posted provenance identifies the reviewer; it adds no credit condition.

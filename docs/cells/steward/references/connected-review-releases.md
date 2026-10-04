# Lab reviewer releases

**Purpose:** operate the lab's shared reviewer and its manual release tag. **Audience:** the Steward releasing a reviewer and the holder rolling out its callers. **Success:** each release is identified by the completed review that ran it, the owner's settings report is recorded before the first stable caller lands, private execution is checked before the other three products proceed, and a failed later release has a callable rollback target.

## Release control

The jobs and `CLAUDE_CLI_VERSION` live in `.github/workflows/connected-review-shared.yml`. Tradecraft's `.github/workflows/connected-review.yml` calls that workflow at `@main`; the other lab repositories call it at `@reviewer-stable`. The caller grants the union of the jobs' permissions and inherits secrets. Admission and reporting run hosted; an admitted private review runs on the caller's self-hosted runner. Only the finder step receives the Claude credential.

The shared workflow captures its own `job.workflow_repository`, `job.workflow_file_path` and `job.workflow_sha` before checkout. Every job validates that identity and its runtime checkout. Reviews name that tradecraft SHA and the verified Claude CLI version before the final attempt marker. Skip notices name the configured pin without claiming the CLI or finder ran. A moving tag is never resolved again inside a run. A full rerun may resolve it afresh, so read each posted review's provenance rather than assuming two attempts used the same release. GitHub documents the [job identity](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#job-context) and [runner and rerun rules](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations).

The shipped adopter template and its reference keep the copy-whole workflow with a frozen reviewer commit. Direct invocations post provenance only when their calling workflow supplies it. Lab releases do not change an adopter's chosen reviewer.

## First release and rollout

1. The holder verifies the gate half, change-proof #46, has landed and the lab's required gate resolves to that merged revision. Only then may #847's shared workflow and tradecraft stub merge. The Steward merges tradecraft and change-proof; product merges remain the owner's.
2. After #847 merges, the Steward updates the installed plugin to the merged release, as it does after every tradecraft merge. It tells in-flight tradecraft holders that an entrance below the merged release reports a review from the shared workflow as owed even when the gate credits it, so they re-run on the merged release. Then obtain the next eligible tradecraft review at a head not already reviewed. Its completed posted review must show finder usage, the exact shared-workflow commit from merged `main`, and the verified CLI version. Findings are allowed. A skip, successful oversize preflight, existing same-head review, or #847's own pre-merge review cannot justify the tag: none exercises the newly merged reviewer. If workflow identity is unavailable or disagrees, hold release and return the observed failure to the builder through the holder before changing the selected identity approach.
3. The owner reads and reports the two organisation settings governing the private callers: the Actions policy (organisation Settings → Actions → General → Policies), which must allow `Grimblaz-and-Friends` reusable workflows or all; and the products' self-hosted runner group's workflow access (Settings → Actions → Runner groups → the products' group → Workflow access), which must be `All workflows` or include the called shared workflow. Reading them needs `admin:org`, which neither the holder nor the Steward holds. The owner changes either setting if needed. The holder records the owner's report confirming both settings on #847 before any downstream stub lands.
4. Before creating the tag, the Steward confirms that every product holder's entrance runs an installed plugin version at or above the merged release. After the clean tradecraft review and the owner's settings report confirming both settings, the Steward creates `reviewer-stable` at the exact reviewed release SHA. If `main` advanced, use the reviewed workflow SHA that contains the intended release, not the current tip. Verify that the target contains the callable workflow, record creation on #683 with its evidence, then let the holder proceed with the five carrier issues in sequence: change-proof's carrier first, then the four products in any order the holder sets. Each carrier uses its own issue and the affirmed ordinary/mechanical lane. The Steward merges change-proof's stub; the owner merges the four products' stubs. No durable downstream stub lands before the gate half and tag.
5. Land change-proof's stub first, then the first private product's stub in the order the holder sets. After it lands, that product's first review through the stable stub is the execution check: require a completed posted review from the self-hosted runner naming the tag's commit and the verified CLI. Hold the other three products' stubs until that review completes with this evidence. Retain its posted revision, verified CLI, run/job and runner identity. On failure, the owner merges a revert of that one product's stub, the rest stay held, and the evidence returns through the holder for repair. There is no earlier callable tag target to restore at first creation.

The holder records the owner's settings report on #847 and the first private product's execution evidence: repository, tag target SHA, review head, run and job links, self-hosted runner identity, verified CLI and posted review. Raw output stays outside commits; any retained tree summary names each evidence file's revision, SHA-256, size and reproducing command.

## Later release moves

Consider a move only after a merge changes reviewer code, the finder prompt, the shared workflow or the lab CLI pin. An unrelated tradecraft merge buys no move. Require one subsequent eligible tradecraft review that ran the finder and posted, with any number of findings, naming the released workflow commit and verified CLI. Select that SHA even if `main` has since advanced, and verify it includes the intended change.

The Steward moves the tag manually after recording the previous callable target and the qualifying review. The owner may hold or reverse a move. Observe the first product review actually using the moved stable stub. If it fails where the previous release worked, restore the previous callable target and record the failure and verified rollback. Do not restore a historical copy-whole pin: it lacks the callable workflow.

Each creation, move or rollback is recorded on #683 with the release SHA, completed tradecraft review and run links, previous target (absent for creation), verified new target, the owner's settings report on #847 at first creation, first product observation, and any failure, stub revert or tag rollback. The standing page carries observations; this document carries the procedure.

## Caller for the later carriers

Use this exact stub in each carrier. Tradecraft's own stub uses `main`.

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

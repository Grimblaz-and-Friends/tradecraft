---
name: connected-review
description: Run or configure the automatic connected reviewer whose single finder pass reports concrete, evidenced defects. Use for this reviewer's finder, workflow, retry, or replay. Do not use as an internal review stage or for dispositioning comments after publication.
---

# Connected review

**Purpose:** give a pull request one head-scoped review from the lab's chosen single finder pass. **Audience:** the automatic reviewer runtime and adopters configuring it. **Success:** an eligible event creates one completed review at the captured head, or one visible skip notice that cannot count as review.

## Where this cell's depth lives

- **Running the finder pass** -> `references/finder.md`: the concrete-failure contract, exclusions and structured fields.
- **Replaying the measured two-pass configurations** -> `references/checker.md`: the historical checker contract retained for replay reproducibility; the live workflow never loads it.

The canonical copy-whole workflow is `templates/connected-review.yml`. An enabling change installs it at `<adopter-root>/.github/workflows/connected-review.yml` only after replacing its marked reviewer ref with the merged commit on tradecraft's default branch, and adds the reviewer login in that same change; the marked placeholder is not runnable. That destination is fixed because receipt checks identify the workflow file from GitHub's run record. With a real ref installed, an absent reviewer login leaves the workflow dormant. Copy the workflow without extracting steps, because its unprivileged admission job, trusted runtime checkout, credential placement, runner split and hosted reporter form one security boundary.

## Contract

Run only for an open, ready pull request authored by the account named in `REVIEW_OWNER_LOGIN` in the same repository, after this reviewer's login is present in `connected_reviewers` of the base branch's `.tradecraft/work.json`. The named account is the one owner whose pull requests are reviewed and whose Claude token the secret holds; this copy already names the lab owner, `Grimblaz`, and refuses any other author's pull request without a notice. Ready events and events adding the label named by `reviewer_label` in that file may admit work; the repository must have that label, whose default is `reviewers`. Pushes and synchronize events do not. A completed review suppresses only another event at the same head, so a later explicitly requested look at a new head remains possible.

One fresh read-only finder process runs at `high`. It applies both coverage lenses to every changed hunk and names an input, execution path, root cause, wrong result and exact proof targets for each candidate. Trusted code validates the structured output and anchor shape, collapses candidates with the same root cause, and alone holds publication authority; the model process receives no GitHub credential and cannot publish.

Trusted code validates eligibility, schemas, candidate identity, evidence, payload limits and the head immediately before publication. It submits every deduplicated finding in one completed review; a finding whose anchor is not a commentable changed line stays in that review's body at its real path and line. Trusted code gives each body finding `<!-- tradecraft-review-finding:v1:RUN_ID:ORDINAL -->`, where the numeric attempt is the run id and the ordinal is its position among body findings, so the holder can answer it individually under the connected-reviewer answer contract. The finder invents no publication identity. A clean completed run submits the same review with no inline comments. Total findings and finder usage stay in that review, with the attempt marker last.

An admitted run that cannot complete gets one ordinary pull-request comment beginning `Review skipped:` and no review. Its review job remains failed, or cancelled when GitHub cancelled it, so after the cause clears retry that same run with `gh run rerun <run-id> --failed`; the rerun replaces the check on the pull-request head and either completes the review or turns green after suppressing itself because that head already has one. The workflow offers no separate dispatch retry because a dispatch check belongs to the default branch and cannot repair the head's check. Duplicate trigger events and already-reviewed heads are suppressed without a notice because they are not failed review attempts.

On a public repository the review job uses a hosted runner and installs its pinned toolchain. On a private repository the self-hosted runner provides `gh`, Python 3.14, Node and npm on the PATH of the account running it; on Windows, run the runner as that user or install the tools for all users, because a service account does not see per-user installs. Before snapshot handling, trusted code installs the pinned Claude CLI in the runner tool cache, selects only that installation and disables its auto-updater. That setup executes no pull-request content, and the finder remains read-only. The hosted report job checks out no pull-request content and receives no Claude token.

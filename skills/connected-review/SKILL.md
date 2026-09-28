---
name: connected-review
description: Run or configure the automatic connected reviewer whose single finder pass reports concrete, evidenced defects. Use for this reviewer's finder, workflow, retry, or replay. Do not use as an internal review stage or for dispositioning comments after publication.
---

# Connected review

**Purpose:** give a pull request one head-scoped review from the lab's chosen single finder pass. **Audience:** the automatic reviewer runtime and adopters configuring it. **Success:** an eligible event creates one completed review at the captured head, or one visible skip notice that cannot count as review.

## Where this cell's depth lives

- **Running the finder pass** -> `references/finder.md`: the concrete-failure contract, exclusions and structured fields.
- **Replaying the measured two-pass configurations** -> `references/checker.md`: the historical checker contract retained for replay reproducibility; the live workflow never loads it.

The canonical copy-whole workflow is `templates/connected-review.yml`. Copy it without extracting steps, because its unprivileged admission job, trusted runtime checkout, credential placement, runner split and hosted reporter form one security boundary.

## Contract

Run only for an open, ready pull request authored by the token owner in the same repository, after this reviewer's login is present in the base branch's connected-reviewer configuration. Ready and `reviewers`-label events may admit work; pushes and synchronize events do not. A completed review suppresses only another event at the same head, so a later explicitly requested look at a new head remains possible.

One fresh read-only finder process runs at `high`. It applies both coverage lenses to every changed hunk and names an input, execution path, root cause, wrong result and exact proof targets for each candidate. Trusted code validates the structured output and anchor shape, collapses candidates with the same root cause, and alone holds publication authority; the model process receives no GitHub credential and cannot publish.

Trusted code validates eligibility, schemas, candidate identity, evidence, payload limits and the head immediately before publication. It submits every deduplicated finding in one completed review; a finding whose anchor is not a commentable changed line stays in that review's body, and a clean completed run submits the same review with no inline comments. Finder usage stays in that review.

An admitted run that cannot complete gets one ordinary pull-request comment beginning `Review skipped:` and no review. Retry the workflow explicitly after the cause clears. Duplicate trigger events and already-reviewed heads are suppressed without a notice because they are not failed review attempts.

On a public repository the review job uses a hosted runner and installs its pinned toolchain. On a private repository the self-hosted runner provides Node and npm; before snapshot handling, trusted code installs the pinned Claude CLI in the runner tool cache, selects only that installation and disables its auto-updater. That setup executes no pull-request content, and the finder remains read-only. The hosted report job checks out no pull-request content and receives no Claude token.

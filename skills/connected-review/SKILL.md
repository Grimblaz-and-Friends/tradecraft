---
name: connected-review
description: Run or configure the automatic two-pass connected reviewer that proposes concrete defects, independently proves them, and publishes only survivors. Use for this reviewer's finder, checker, workflow, retry, or replay. Do not use as an internal review stage or for dispositioning comments after publication.
---

# Connected review

**Purpose:** give a pull request one head-scoped review whose comments have each survived an independent proof pass. **Audience:** the automatic reviewer runtime and adopters configuring it. **Success:** an eligible event creates one completed review at the captured head, or one visible skip notice that cannot count as review.

## Where this cell's depth lives

- **Running the candidate-finding pass** -> `references/finder.md`: the concrete-failure contract, exclusions and structured fields.
- **Running the independent proof pass** -> `references/checker.md`: the opposite burden, candidate-only boundary and uncertainty rule.

The canonical copy-whole workflow is `templates/connected-review.yml`. Copy it without extracting steps, because its unprivileged admission job, trusted runtime checkout, credential placement, runner split and hosted reporter form one security boundary.

## Contract

Run only for an open, ready pull request authored by the token owner in the same repository, after this reviewer's login is present in the base branch's connected-reviewer configuration. Ready and `reviewers`-label events may admit work; pushes and synchronize events do not. A completed review suppresses only another event at the same head, so a later explicitly requested look at a new head remains possible.

The finder and checker are fresh read-only processes. The finder names an input, execution path and wrong result for each candidate. The checker evaluates only those candidate IDs and keeps one only when the supplied tree or permitted verification demonstrates the same failure. Uncertainty drops the candidate. Model processes receive no GitHub credential and cannot publish.

Trusted code validates eligibility, changed-line anchors, schemas, candidate identity, evidence, payload limits and the head immediately before publication. It submits every survivor in one completed review; a clean completed run submits the same review with no inline comments. Usage from both passes stays in that review.

An admitted run that cannot complete gets one ordinary pull-request comment beginning `Review skipped:` and no review. Retry the workflow explicitly after the cause clears. Duplicate trigger events and already-reviewed heads are suppressed without a notice because they are not failed review attempts.

On a public repository the review job uses a hosted runner and installs its pinned toolchain. On a private repository it uses the owner's self-hosted runner and a preinstalled pinned toolchain; both passes remain read-only there. The hosted report job checks out no pull-request content and receives no Claude token.


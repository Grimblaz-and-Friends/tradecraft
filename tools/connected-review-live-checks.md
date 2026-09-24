# Connected reviewer live checks

**Purpose:** give the holder the live GitHub checks that cannot be proved inside the build tree. **Audience:** the holder running post-build fixture checks with the owner's token and runners. **Success:** every live-only falsifier has an observed result or a named departure; no simulated result is reported as the live check.

## Before running

Use neutral public and private fixture repositories owned by the token owner. Copy the canonical workflow whole, replace its dormant reviewer ref with the frozen merged commit on the default branch, set `CONNECTED_REVIEW_ENABLED` to `true`, set `CLAUDE_CODE_OAUTH_TOKEN`, and list `github-actions[bot]` as a connected reviewer only in those fixtures. Install `gh`, Python 3.14 and Claude CLI 2.1.280 on the private self-hosted runner. Record the fixture repository names, workflow run URLs, pull-request heads and the revision under test.

Do not add the login to a product repository during these checks. Enumerate each fixture's other workflows and recent comments by `github-actions[bot]`; if any unrelated output can satisfy the existing entrance or gate, record activation as failed and return the identity problem to the holder.

## Event and publication matrix

In both fixtures, open an owner-authored draft and exercise: ready, `reviewers` label, ready plus label, ordinary push, synchronize, non-reviewer label, another member's pull request, bot author, missing head metadata through the recorded fixture, owner fork and outsider fork. Confirm only eligible ready, label and explicit retry attempts can reach the token-bearing job. Confirm public work uses `ubuntu-latest`, private work uses the self-hosted runner, and the hosted report job receives no Claude token and checks out no pull-request tree.

For a clean result and a result with a survivor, retain the reviews API responses. Confirm one completed review at the captured head, exact inline comments, and finder/checker usage in the review body. Push head B after a completed review at head A, remove and re-add the label, and confirm one review at B; repeat the label event at B and confirm no further review or skip.

Change the head during analysis, lose the client response after an accepted review in the instrumented fixture, and fail after accepted publication. Confirm reconciliation produces neither a duplicate review nor a contradictory skip.

## Isolation probes

Run `python tools/probe_connected_review_confinement.py --output confinement.json` with the owner's token and the same Claude executable the workflow will use. Retain its CLI tool trace and report. This build supplies the probe but does not claim the real-CLI boundary passed; a firing hook, outside-path read or leaked environment canary fails the check.

Use a pull request containing hooks, repository and user settings, MCP configuration, build/install scripts, command-shaped titles and filenames, symlinks that point outside the tree, and environment canary names. On the private runner, retain the process trace and canary state showing that neither pass executed pull-request content, followed links, wrote outside its unique run directory, opened a network tool, or received shell, write, web, delegation or arbitrary MCP capability. Inspect the launched CLI arguments and effective managed-settings preflight result as well as the prompt.

On the public runner, confirm the ordinary checker remains read-only. If a later revision adds the optional verification tool, repeat the credential-read, host-write, container-socket and outbound-network probes inside its disposable token-free sandbox before treating public execution as available.

## Failure delivery and recovery

Inject a usage limit, authentication failure, malformed finder output, malformed checker output, execution timeout, cancellation while running and a publication transport failure. For every admitted unfinished attempt, retain exactly one ordinary comment whose first line begins `Review skipped:` and names the observed cause, no completed review, and the existing entrance/gate result showing review still owed. Retry the hosted reporter and confirm it does not duplicate the notice. Clear the cause, explicitly retry the workflow and confirm one completed review.

For the private fixture, take the self-hosted runner offline before dispatch and leave it offline through GitHub's actual queue expiry. Retain the review job record showing cancellation without a runner and the dependent hosted `report` job starting under `always()`. Confirm its single cause-specific notice and no review. Separately cancel once while queued and once while running; record whether GitHub schedules the dependent reporter in each case. If it does not, this delivery design fails the check; record a departure rather than substituting a mocked `needs.review.result`.

## Record

For each check record `pass`, `fail`, or `departure`, the workflow run and pull-request URLs, the exact reviewed head, and the retained API response or process trace. A check that cannot run because a token, runner, fixture repository or 24-hour observation window is unavailable is a departure with that reason, never a pass.

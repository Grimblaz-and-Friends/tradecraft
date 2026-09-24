# D-757 — Ship the connected reviewer dormant, then qualify it by repository

**Purpose:** preserve the connected reviewer's trust boundary, replay order and dormant enablement contract. **Audience:** a future session changing its workflow, two-pass runtime, replay harness or repository activation. **Success:** that session can distinguish what this pull request lands from the later evidence and repository-specific changes that make the reviewer count.

Governed by the affirmed implementation brief and settled artifact on [#746](https://github.com/Grimblaz-and-Friends/tradecraft/issues/746), including the holder's whole-change reading. The implementing pull request is [#757](https://github.com/Grimblaz-and-Friends/tradecraft/pull/757).

## Context

The practice needed a connected reviewer whose finder may propose defects but whose independent checker carries the burden of proof before anything is posted. Public repositories can use a disposable hosted runner; private repositories must protect the owner's machine by keeping both passes read-only. A completed review, including a clean one, is the only successful receipt. An unfinished attempt posts one notice beginning `Review skipped:` and cannot satisfy the entrance.

The replay bars are part of the bought outcome, but their evidence is not build evidence. The holder prepares the frozen tradecraft manifest independently, tuning occurs only against that corpus on this pull request before ready, and a grader who neither built nor tuned the reviewer judges it. Product replays follow only after the successful reviewer revision is merged and frozen.

## Decision

This pull request lands one shipped connected-review skill, a canonical copy-whole workflow, the trusted two-pass runtime, replay exporter and grader, recorded-fixture coverage, a real-CLI confinement probe, and the holder's live-check procedure. The finder and checker run as fresh processes; deterministic code owns event validation, snapshots, result validation and GitHub publication. Repository review rules come only from the base revision's root `## Code Review Rules` section. A private run offers no execution tool, and a public run remains read-only unless a later verified sandbox supplies the optional execution boundary.

The reviewer lands dormant. The workflow's one marked reviewer ref is deliberately not a release pin, and the enabling repository variable is absent. After a repository's applicable replay and identity checks pass, a separate enabling change replaces that ref with the frozen merged commit on the default branch, enables the workflow and adds its review identity to that repository's work configuration.

The holder's four artifact readings govern the implementation:

1. Duplicate suppression is per current head. A label event at an already reviewed head buys nothing; re-adding the label at a new head may buy the permitted second look.
2. Live GitHub checks remain the holder's after the build. This tree carries response-shaped fixtures, a procedure and the real-CLI probe; unavailable live evidence is a named departure, never a pass.
3. The build stops with a dormant reviewer and replay interfaces. The holder freezes the tradecraft manifest before tuning; tradecraft tuning and independent grading occur on #757 before ready; product replays occur unchanged after merge; activation is later and repository-specific.
4. Greptile removal is separate mechanical work. This change neither edits `greptile.json` nor adds the new login to a work configuration, and a rebase over a landed removal does not alter the independent measurement builds.

The workflow serializes only review jobs per repository and pull request, without cancellation. Preparation remains parallel and head-aware; the runtime checks the current head immediately before publication. A reporter reconciles the attempt identifier across completed reviews at any head before it can post one skip notice. It also handles an eligible preparation failure when current trusted API data can establish eligibility; inability to establish eligibility fails visibly and posts nothing.

Tuning round 1 responds to the aggregate tradecraft replay result recorded on [#746](https://github.com/Grimblaz-and-Friends/tradecraft/issues/746#issuecomment-5822972677): candidate discovery was the limiting pass while checked output remained clean. The finder remains one read-only pass with the existing candidate ceiling, but now runs at `max` effort and must cover every changed hunk, its callers and consumers, its tests and its governing prose before returning. It proposes every concrete input, path and wrong result without applying its own confidence threshold; the separate checker keeps its original prompt, `high` effort and proof burden. The changed finder prompt, pass-specific effort and harness metadata constitute a new reviewer version, so a complete tradecraft replay is required before any freeze.

## Rejected alternatives and consequences

**Enable this repository in the build.** Rejected because no replay-qualified frozen merged revision exists yet. A branch commit is not a stable activation pin, especially when the pull request may squash.

**Let a finder or checker publish directly.** Rejected because model processes must not hold GitHub authority and because a checker may correct a proposed anchor but may not invent a finding. A proved survivor that cannot be anchored inline stays in the same completed review body with its path and line.

**Count an unfinished run as a clean review.** Rejected because it recreates the Greptile limit-notice defect. Failures retain observed per-pass usage, post no review, and remain owed.

**Treat replay output as a build pass.** Rejected because corpus selection, tuning and independent grading belong to the ordered post-build work above. Missing bars, missing cases, a per-case error or an input leak makes a replay unscorable.

**Add finder passes or raise the candidate ceiling in the first tuning round.** Rejected because the aggregate evidence showed that the existing pass was not exploring the input or approaching its available output capacity. Systematic coverage and higher finder effort are the smaller recall intervention; the checker remains the precision boundary.

## Evidence

The parser, two-pass burden, usage propagation, attempt reconciliation, body fallback, workflow serialization, dormant pin, repository-rule extraction, receipt crediting, replay fail-closed behavior and incremental case records are exercised in `lib/tests/test_connected_review.py`, `tools/tests/test_connected_review_replay.py` and the connected-review packaging checks. `tools/probe_connected_review_confinement.py` and `tools/connected-review-live-checks.md` are procedures for evidence this build cannot honestly manufacture.

Run `python tools/lint.py` and `python -m pytest tools/tests skills lib/tests -q -n auto --dist loadfile` on the tree under review. Those commands and test surfaces are the evidence; this entry freezes no derived result.

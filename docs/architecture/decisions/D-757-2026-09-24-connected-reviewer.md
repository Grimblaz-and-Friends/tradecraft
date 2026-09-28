# D-757 — Ship the connected reviewer dormant, then qualify it by repository

**Purpose:** preserve the connected reviewer's trust boundary, replay order and dormant enablement contract. **Audience:** a future session changing its workflow, two-pass runtime, replay harness or repository activation. **Success:** that session can distinguish what this pull request lands from the later evidence and repository-specific changes that make the reviewer count.

Governed by the affirmed implementation brief and settled artifact on [#746](https://github.com/Grimblaz-and-Friends/tradecraft/issues/746), including the holder's whole-change reading. The implementing pull request is [#757](https://github.com/Grimblaz-and-Friends/tradecraft/pull/757).

## Context

The practice needed a connected reviewer whose finder may propose defects but whose independent checker carries the burden of proof before anything is posted. Public repositories can use a disposable hosted runner; private repositories must protect the owner's machine by keeping both passes read-only. A completed review, including a clean one, is the only successful receipt. An unfinished attempt posts one notice beginning `Review skipped:` and cannot satisfy the entrance.

The replay bars are part of the bought outcome, but their evidence is not build evidence. The holder prepares the frozen tradecraft manifest independently, tuning occurs only against that corpus on this pull request before ready, and a grader who neither built nor tuned the reviewer judges it. Product replays follow only after the successful reviewer revision is merged and frozen.

## Decision

This pull request lands one shipped connected-review skill, a canonical copy-whole workflow, the trusted two-phase runtime, replay exporter and grader, recorded-fixture coverage, a real-CLI confinement probe, and the holder's live-check procedure. The finder and each checker batch run fresh; deterministic code owns event validation, snapshots, result validation and GitHub publication. Repository review rules come only from the base revision's root `## Code Review Rules` section. A private run offers no execution tool, and a public run remains read-only unless a later verified sandbox supplies the optional execution boundary.

The reviewer lands dormant. The workflow's one marked reviewer ref is deliberately not a release pin, and the enabling repository variable is absent. After a repository's applicable replay and identity checks pass, a separate enabling change replaces that ref with the frozen merged commit on the default branch, enables the workflow and adds its review identity to that repository's work configuration.

The holder's four artifact readings govern the implementation:

1. Duplicate suppression is per current head. A label event at an already reviewed head buys nothing; re-adding the label at a new head may buy the permitted second look.
2. Live GitHub checks remain the holder's after the build. This tree carries response-shaped fixtures, a procedure and the real-CLI probe; unavailable live evidence is a named departure, never a pass.
3. The build stops with a dormant reviewer and replay interfaces. The holder freezes the tradecraft manifest before tuning; tradecraft tuning and independent grading occur on #757 before ready; product replays occur unchanged after merge; activation is later and repository-specific.
4. Greptile removal is separate mechanical work. This change neither edits `greptile.json` nor adds the new login to a work configuration, and a rebase over a landed removal does not alter the independent measurement builds.

The workflow serializes only review jobs per repository and pull request, without cancellation. Preparation remains parallel and head-aware; the runtime checks the current head immediately before publication. A reporter reconciles the attempt identifier across completed reviews at any head before it can post one skip notice. It also handles an eligible preparation failure when current trusted API data can establish eligibility; inability to establish eligibility fails visibly and posts nothing.

Tuning round 1 responds to the aggregate tradecraft replay result recorded on [#746](https://github.com/Grimblaz-and-Friends/tradecraft/issues/746#issuecomment-5822972677): candidate discovery was the limiting pass while checked output remained clean. The finder remains one read-only pass with the existing candidate ceiling, but now runs at `max` effort and must cover every changed hunk, its callers and consumers, its tests and its governing prose before returning. It proposes every concrete input, path and wrong result without applying its own confidence threshold; the separate checker keeps its original prompt, `high` effort and proof burden. The changed finder prompt, pass-specific effort and harness metadata constitute a new reviewer version, so a complete tradecraft replay is required before any freeze.

Tuning round 2 supersedes that freeze set under the owner's ruling. One deeper pass produced uneven candidate volume without reaching the recall bar, so two lower-effort lenses buy different search paths while per-pass caps retain the existing merged ceiling. The model remains `claude-opus-5-5` on Claude CLI 2.1.280; two fresh read-only finder processes run at `xhigh`, one with the `contracts` lens and one with the `state-inputs` lens, each capped at 50 candidates before their merged input reaches the single `high` checker. The finder prompt SHA-256 is `b04f167c85d26310e18b31bae19463a2173c255dc47995efb1616669cf4ed306`; the checker prompt SHA-256 is `a1026a460bdf131ec3c97f3495bda17855b0f38eb76c8fbf2de693c0082ed03c`; and the canonical settings SHA-256 is `9c502583df11b2ed2c0909b92bc80001a93b7f5aa78d6ac98150412343a98487`. `test_tuned_reviewer_prompt_and_settings_hashes_are_frozen` recalculates those identities on the tree under review.

Tuning round 3 supersedes round 2's freeze set. The supplied class-level diagnosis put the remaining constraint in proving rather than proposing, so one `xhigh` finder now applies the combined contracts and state-inputs coverage lens and returns at most 50 candidates. Each candidate supplies one to eight exact path-and-line proof targets. Fresh `xhigh` checker processes receive at most 25 candidates apiece, read those targets and trace the stated execution path before deciding. The structure therefore spends at most one finder and two checker processes on a case; removing the second proposer and halving the possible candidate input funds deeper, bounded proof without raising round 2's process ceiling. The checker still decides every supplied ID, never finds, and drops a candidate whose attempted trace does not show the failure.

The final freeze set is model `claude-opus-5-5` on Claude CLI 2.1.280, finder effort `xhigh`, checker effort `xhigh`, one combined finder pass capped at 50 candidates, and checker batches capped at 25. The finder prompt SHA-256 is `3b13819ec50d747a655c3634a6b663592c052bca8d1f3fa7c0f8ebc8473bf247`; the checker prompt SHA-256 is `c7c352d97e6b971ffff6343d113cbc299dd2a3c6c72363b6debee28e665a3f83`; and `test_tuned_reviewer_prompt_and_settings_hashes_are_frozen` recalculates those identities on the tree under review.

Later measurement support adds optional changed-file preloading without tuning that freeze set. It is off by default; when enabled, trusted code places up to 600,000 raw bytes of post-change UTF-8 text in each finder and checker prompt, ordered by changed-line count, while retaining the read tools for overflow and unchanged context. The default-off setting and budget are part of the reviewer identity, so a replay resume cannot cross configurations; the resulting canonical default settings SHA-256 is `b7d4b103c9ed31d42258e6f774161bad1f060a42d00c666ac484f800cdbd92a6`. Model, efforts, prompts, process structure and tool permissions do not change.

The finder instructions retain a first coverage sweep before deepening one file and a root cause separate from its symptoms. The checker instructions retain absent-content rejection and now require an attempted source trace before uncertainty can drop a candidate. `test_prompts_carry_opposite_burdens_and_all_named_exclusions` pins those instructions; `test_one_finder_combines_coverage_lenses_and_prefixes_candidates`, `test_candidate_requires_exact_bounded_proof_targets`, `test_checker_uses_fresh_xhigh_batches_and_decides_every_candidate` and `test_checker_collapses_candidates_with_the_same_root_cause` demonstrate the process structure and deterministic duplicate backstop. The checker burden, repository rules, five exclusions and private read-only tool boundary do not change.

## Rejected alternatives and consequences

**Enable this repository in the build.** Rejected because no replay-qualified frozen merged revision exists yet. A branch commit is not a stable activation pin, especially when the pull request may squash.

**Let a finder or checker publish directly.** Rejected because model processes must not hold GitHub authority and because a checker may correct a proposed anchor but may not invent a finding. A proved survivor that cannot be anchored inline stays in the same completed review body with its path and line.

**Count an unfinished run as a clean review.** Rejected because it recreates the Greptile limit-notice defect. Failures retain observed per-pass usage, post no review, and remain owed.

**Treat replay output as a build pass.** Rejected because corpus selection, tuning and independent grading belong to the ordered post-build work above. Missing bars, missing cases, a per-case error or an input leak makes a replay unscorable.

**Add finder passes or raise the candidate ceiling in the first tuning round.** Rejected because the aggregate evidence showed that the existing pass was not exploring the input or approaching its available output capacity. Systematic coverage and higher finder effort are the smaller recall intervention; the checker remains the precision boundary.

**Keep two finders while raising and batching the checker.** Rejected for the final tuning round because the supplied diagnosis showed ample nearby candidates already reaching the checker. Spending the second finder's process on bounded `xhigh` proof keeps the process ceiling fixed and lowers the maximum candidate load instead of buying more proposal breadth.

## Evidence

The parser, two-pass burden, usage propagation, attempt reconciliation, body fallback, workflow serialization, dormant pin, repository-rule extraction, receipt crediting, replay fail-closed behavior and incremental case records are exercised in `lib/tests/test_connected_review.py`, `tools/tests/test_connected_review_replay.py` and the connected-review packaging checks. `tools/probe_connected_review_confinement.py` and `tools/connected-review-live-checks.md` are procedures for evidence this build cannot honestly manufacture.

Run `python tools/lint.py` and `python -m pytest tools/tests skills lib/tests -q -n auto --dist loadfile` on the tree under review. Those commands and test surfaces are the evidence; this entry freezes no derived result.

# D-757 — Ship the connected reviewer dormant, then use the owner's chosen standard

**Purpose:** preserve the connected reviewer's chosen live configuration, trust boundary, measurement history and dormant enablement contract. **Audience:** a future session changing its workflow, live runtime, replay harness or repository activation. **Success:** that session keeps the one-pass `high` standard distinct from the earlier measured two-pass configurations and from optional measurements such as preload.

Governed by the affirmed implementation brief and settled artifact on [#746](https://github.com/Grimblaz-and-Friends/tradecraft/issues/746), including the holder's whole-change reading. The implementing pull request is [#757](https://github.com/Grimblaz-and-Friends/tradecraft/pull/757).

## Context

The practice needed a connected reviewer whose findings carry a concrete failure and evidence before anything is posted. Public repositories can use a disposable hosted runner; private repositories must protect the owner's machine by keeping the model pass read-only. A completed review, including a clean one, is the only successful receipt. An unfinished attempt posts one notice beginning `Review skipped:` and cannot satisfy the entrance.

The initial brief bought a finder and independent checker, then replay rounds measured several versions without clearing the initial overlap bar. The owner replaced that choice rule with the blind [value rubric](https://github.com/Grimblaz-and-Friends/tradecraft/issues/746#issuecomment-5863034480), read its [result](https://github.com/Grimblaz-and-Friends/tradecraft/issues/746#issuecomment-5863573384), and amended the [brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/746#issuecomment-5863654303) to choose one finder at `high` as every lab repository's standard.

## Decision

This pull request lands one shipped connected-review skill, a canonical copy-whole workflow, the trusted runtime, replay exporter and grader, recorded-fixture coverage, a real-CLI confinement probe, and the holder's live-check procedure. The live runtime launches exactly one fresh finder process at `high`; deterministic code owns event validation, snapshots, candidate validation, root-cause deduplication and GitHub publication. Repository review rules come only from the base revision's root `## Code Review Rules` section. A private run offers no execution tool, and the public run remains read-only. The checker implementation stays available only to the replay harness so the earlier measured configurations remain reproducible; it is not in the live workflow.

The reviewer lands dormant. The workflow's one marked reviewer ref is deliberately not a release pin, and the enabling repository variable is absent. A separate enabling change replaces that ref with the reviewed merged commit on the default branch, enables the workflow and adds its review identity to the repository's work configuration. The amended brief makes the chosen configuration standard in every lab repository without another repository-specific replay.

The holder's four artifact readings govern the implementation:

1. Duplicate suppression is per current head. A label event at an already reviewed head buys nothing; re-adding the label at a new head may buy the permitted second look.
2. Live GitHub checks remain the holder's after the build. This tree carries response-shaped fixtures, a procedure and the real-CLI probe; unavailable live evidence is a named departure, never a pass.
3. The build stops with a dormant reviewer and replay interfaces. The holder's frozen tradecraft corpus supported tuning and the later blind comparison; the amended brief supersedes the earlier product-replay gate, while activation remains a later repository change.
4. Greptile removal is separate mechanical work. This change neither edits `greptile.json` nor adds the new login to a work configuration, and a rebase over a landed removal does not alter the independent measurement builds.

The workflow serializes only review jobs per repository and pull request, without cancellation. Preparation remains parallel and head-aware; the runtime checks the current head immediately before publication. A reporter reconciles the attempt identifier across completed reviews at any head before it can post one skip notice. It also handles an eligible preparation failure when current trusted API data can establish eligibility; inability to establish eligibility fails visibly and posts nothing.

On 2026-09-28 the owner chose self-maintenance for the private runner's Claude CLI. The trusted runtime installs the pinned package under the runner tool cache only when its version is absent or different, resolves that exact installation before the existing version check, and disables its auto-updater. This trusted install precedes snapshot export and uses no pull-request content; install failure becomes a named skip with no fallback. Hosted runners retain their per-run global install.

## Owner's chosen standard

The owner fixed the comparison before reading the scores in the [value rubric](https://github.com/Grimblaz-and-Friends/tradecraft/issues/746#issuecomment-5863034480): each candidate and Greptile were scored blind on validity, the repository's act-on rule, novelty over the retained reviewers, acting cost, harm and noise. The [result](https://github.com/Grimblaz-and-Friends/tradecraft/issues/746#issuecomment-5863573384) found that the single Opus 5.5 finder at `high` produced about five times Greptile's consequential new findings at a lower noise share. The owner ruled that Greptile's noise scored on the same rubric, rather than the absolute earlier bar, was the relevant comparator and chose that `high` configuration for every lab repository in the [amended brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/746#issuecomment-5863654303).

The chosen live configuration uses the unchanged finder prompt at SHA-256 `3b13819ec50d747a655c3634a6b663592c052bca8d1f3fa7c0f8ebc8473bf247`, model `claude-opus-5-5`, effort `high`, and no checker; `test_live_reviewer_standard_is_one_high_finder_with_frozen_prompt` recalculates that identity on the tree under review. Deterministic validation and root-cause deduplication retain the proof-bearing candidate contract. Changed-file preload remains off by default while its separate measurement is pending.

## Measured alternatives — history, not the live default

Tuning round 1 responds to the aggregate tradecraft replay result recorded on [#746](https://github.com/Grimblaz-and-Friends/tradecraft/issues/746#issuecomment-5822972677): candidate discovery was the limiting pass while checked output remained clean. The finder remains one read-only pass with the existing candidate ceiling, but now runs at `max` effort and must cover every changed hunk, its callers and consumers, its tests and its governing prose before returning. It proposes every concrete input, path and wrong result without applying its own confidence threshold; the separate checker keeps its original prompt, `high` effort and proof burden. The changed finder prompt, pass-specific effort and harness metadata constitute a new reviewer version, so a complete tradecraft replay is required before any freeze.

Tuning round 2 superseded that measurement set under the owner's ruling. One deeper pass produced uneven candidate volume without reaching the recall bar, so two lower-effort lenses bought different search paths while per-pass caps retained the existing merged ceiling. Two fresh read-only finder processes ran at `xhigh`, one with the `contracts` lens and one with the `state-inputs` lens, before their merged input reached the `high` checker. That configuration was measured and then superseded.

Tuning round 3 superseded round 2's measurement set. The supplied class-level diagnosis put the remaining constraint in proving rather than proposing, so one `xhigh` finder applied the combined contracts and state-inputs coverage lens and returned at most 50 candidates. Fresh `xhigh` checker processes received at most 25 candidates apiece, read the supplied proof targets and traced the stated execution path before deciding. That configuration was measured and not chosen.

The last two-pass measurement set was model `claude-opus-5-5` on Claude CLI 2.1.280, finder effort `xhigh`, checker effort `xhigh`, one combined finder pass capped at 50 candidates, and checker batches capped at 25. The finder prompt SHA-256 is `3b13819ec50d747a655c3634a6b663592c052bca8d1f3fa7c0f8ebc8473bf247`; the checker prompt SHA-256 is `c7c352d97e6b971ffff6343d113cbc299dd2a3c6c72363b6debee28e665a3f83`; and `test_measured_two_pass_replay_defaults_and_prompt_hashes_remain_reproducible` recalculates those identities on the tree under review. This set was measured and not chosen.

Later measurement support added optional changed-file preloading without changing any measured prompt. It is off by default; when enabled, trusted code places up to 600,000 raw bytes of post-change UTF-8 text in each configured pass prompt, ordered by changed-line count, while retaining the read tools for overflow and unchanged context. The setting and budget are part of the reviewer identity, so a replay resume cannot cross configurations. The owner has not yet ruled on preload for the live standard.

The finder instructions retain a first coverage sweep before deepening one file and a root cause separate from its symptoms. `test_live_default_runs_one_high_finder_and_publishes_validated_deduplicated_findings`, `test_candidate_requires_exact_bounded_proof_targets` and `test_live_reviewer_standard_is_one_high_finder_with_frozen_prompt` demonstrate the chosen live structure. Historical replay tests retain the checker prompt and its measured configurations. The repository rules, five exclusions and private read-only tool boundary do not change.

## Rejected alternatives and consequences

**Enable this repository in the build.** Rejected because the reviewer ref must name the reviewed merged commit on the default branch. A branch commit is not a stable activation pin, especially when the pull request may squash.

**Let a model process publish directly.** Rejected because the model must not hold GitHub authority. A validated finding that cannot be anchored inline stays in the same completed review body with its path and line.

**Count an unfinished run as a clean review.** Rejected because it recreates the Greptile limit-notice defect. Failures retain observed per-pass usage, post no review, and remain owed.

**Treat replay output as a build pass.** Rejected because corpus selection, tuning and independent grading belong to the ordered post-build work above. Missing bars, missing cases, a per-case error or an input leak makes a replay unscorable.

**Add finder passes or raise the candidate ceiling in the first tuning round.** Rejected for that measured round because the aggregate evidence showed that the existing pass was not exploring the input or approaching its available output capacity. Systematic coverage and higher finder effort were the smaller intervention then.

**Keep two finders while raising and batching the checker.** Rejected for the final tuning round because the supplied diagnosis showed ample nearby candidates already reaching the checker. Spending the second finder's process on bounded `xhigh` proof keeps the process ceiling fixed and lowers the maximum candidate load instead of buying more proposal breadth.

## Evidence

The live single-pass launch, deterministic validation and deduplication, usage propagation, attempt reconciliation, body fallback, workflow serialization, dormant pin, repository-rule extraction, receipt crediting, replay fail-closed behavior and incremental case records are exercised in `lib/tests/test_connected_review.py`, `tools/tests/test_connected_review_replay.py` and the connected-review packaging checks. The replay suite separately preserves the measured checker configurations. `tools/probe_connected_review_confinement.py` and `tools/connected-review-live-checks.md` are procedures for evidence this build cannot honestly manufacture.

Run `python tools/lint.py` and `python -m pytest tools/tests skills lib/tests -q -n auto --dist loadfile` on the tree under review. Those commands and test surfaces are the evidence; this entry freezes no derived result.

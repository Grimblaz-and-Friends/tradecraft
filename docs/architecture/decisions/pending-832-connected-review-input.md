# Pending decision — connected-review input coverage and budget

**Purpose:** preserve the input-policy choice and its calibration for the connected reviewer. **Audience:** the holder assigning this record its implementing pull-request number and a future session revising the policy. **Success:** that reader can rederive the measurements, reproduce base-policy selection offline and distinguish a trusted over-budget skip from an ordinary failure.

This filename is provisional: the implementing pull request does not exist during build. The holder supplies its number on the resumed builder turn after opening that pull request, then renames this entry to the decision log's `D-<PR>-YYYY-MM-DD-<slug>.md` form and indexes it. Work [#832](https://github.com/Grimblaz-and-Friends/tradecraft/issues/832) is governed by the [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/832#issuecomment-5968895793), [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/832#issuecomment-5969032858) and its holder reading supplied to this build.

## Choice and evidence

The fixed lockfile basename list and the base commit's effective `linguist-generated` attribute select coverage. Lockfile recognition wins when both reasons apply. Resolving base attributes prevents a pull request from narrowing the review that judges it; newly landed rules first benefit later changes. No other attribute or repository exclusion setting is admitted. The original head snapshot stays intact for contextual reads.

The holder's recorded measurements at `b29f17594f715f237b25735b9abca0d1afd07ff7`, carried in the reading governing this build, were:

| Repository and head | Diff UTF-8 bytes | Complete finder stdin UTF-8 bytes | Observed attempt |
|---|---:|---:|---|
| tradecraft `f00669abddae448d2775e363454c4bf7fc9b3330` | 168,378 | 171,890 | Completed review |
| Countdown Clash `8b15ae6eb0e9816c391b7c5ac098a274806afcca` | 597,977 | 601,489 | Completed review, run 37120984228 |
| Countdown Clash `63dd6a83646166cc60e2f6b99df33ecf2c839e69` | 3,812,691 | 3,816,203 | Prompt is too long |

The budget `MAX_FINDER_PROMPT_BYTES = 600_000` rounds the larger fitting input down to the nearest 100,000. The reworked #144 input itself is 1,489 bytes over that policy before its lockfile is excluded, so the cap is conservative by construction. This is an initial UTF-8 stdin allowance, including the final structure suffix, not a token count or a guarantee about subsequent context use. Claude rejection below the allowance keeps the ordinary failure route.

Run `python tools/measure_connected_review_prompt.py` on this entry's implementing tree to reconstruct all three inputs, both unfiltered and with the built selection and coverage wrapper. It launches no model and fixes the snapshot path to the artifact's reference path. The unfiltered wrapper and frozen finder instructions reproduce the holder's command on `b29f175`; the instrument reports captured base and head identities beside every measurement. The fitting attempts are [tradecraft run 37084478518](https://github.com/Grimblaz-and-Friends/tradecraft/actions/runs/37084478518) and [Countdown Clash run 37120984228](https://github.com/Grimblaz-and-Friends/Countdown-Clash/actions/runs/37120984228).

## Meaning changes and replay recovery

This supersedes [D-757](D-757-2026-09-24-connected-reviewer.md)'s all-skips-exit-nonzero rationale only for the trusted preflight's over-budget result. The owner selected one review-owed reason for a bypass instead of a failed review job plus a missing review. The reporter remains the sole skip publisher, and the gate still owes a completed review. All other failures retain the failed-job retry route. There is no chunking, partial review, workflow-template change, model or effort change, or reviewer pin move.

Replay export schema 2 carries base attribute blobs, Git blob source identities and SHA-256 integrity data. Historical schema 1 exports remain inspectable and historical result records remain gradeable. A new run or resume requires schema 2; the recovery diagnostic gives an original source manifest containing repository, case IDs, pull-request numbers, base and head SHAs, and the exact export command into a new directory. Reviewer identity includes the coverage policy and byte budget; results retain the base-material digest for every case and resume compares those source hashes before reusing completed work.

The selection and attribute tests in `lib/tests/test_connected_review.py` demonstrate file-level filtering, precedence and isolation. `test_finder_exact_byte_boundary_includes_utf8_preload_and_exclusions` and `test_all_finders_are_measured_before_first_launch` exercise both launch polarities. `test_oversize_cli_handoff_and_reporter_publish_one_complete_skip` exercises successful exit, unchanged output transport, full coverage publication and duplicate suppression. `test_completed_review_coverage_is_not_a_notice_or_finding` checks receipt credit for clean, inline and body findings. Replay's offline, tamper, recovery and resume fixtures in `tools/tests/test_connected_review_replay.py` demonstrate the durable-record boundary.

Live GitHub job conclusions and external gate credit remain holder-owned checks in `tools/connected-review-live-checks.md`; the build's local stubs do not establish them. After merge the Steward receives the already-bought per-repository reviewer-pin follow-ons, one pull request per repository. The assigned plugin slot is `0.178.0`; `0.177.0` belongs to #830.

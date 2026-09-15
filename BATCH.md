# #609 review fix batch

## Rebase and baseline

- Rebasing onto `origin/main` produced one manifest conflict. The resolution retained upstream's `0.129.0` before the version gate required this branch's `0.130.0` bump.
- Rebased head before this batch's uncommitted manifest bump: `05c1d5d9cacc3fd7b35f5231b731f65223fef18f`.
- `python tools/lint.py`: `lint: 0 finding(s)`.
- `python -m pytest lib/tests -q`: `128 passed, 1 skipped in 96.96s (0:01:36)`.

## Ruled remedies

- The supplied materials directory lacks `JUDGE.md`; its complete two-part terminal ruling was recovered from issue comments `5673940545` and `5673940710` and read before implementation.
- Bumped the plugin manifest to `0.130.0`, as the version gate required after rebasing on upstream `0.129.0`.
- Made the capability boundary a checked, explicit `read`/`execute` contract in the dispatcher. A primary that cannot supply the requested capability is recorded unlaunched and a capable fallback is tried; no incapable resolver or child process runs.
- Made the Git-root preflight accept a detached linked worktree, refuse ordinary or subdirectory roots with a reason, ignore inherited `GIT_DIR`, `GIT_WORK_TREE`, and `GIT_COMMON_DIR`, and report safe ASCII Git failures. The suite fixture now creates an actual detached linked worktree.
- Removed unhonoured Claude resolver seams, injected PATH lookup for automatic Codex/Node resolution, and wrote an ASCII stderr diagnostic when an unusable PATH shim is skipped for an app bundle.
- Added the pinned caller-flow test, settings-source records for both boundary settings, exact CLI/help tests, and tests for unknown capabilities, capability-qualified fallback, Git probing, resolver seams, and the bundle diagnostic.
- Applied the bought review prose corrections in the seat-launcher records and review material, including execute-seat banking, selected rather than observed boundaries, qualified fallback, scope, pointer, and root-route language; preserved the OAuth `--bare` sentence while deleting the duplicate epilog.
- Added D-630 and its index row, superseding the live D-585/D-591/D-597 claims named by the judge while leaving D-591's owner term question open; the stretch now cites D-630 rather than D-597 for the enforcement rule.

## New pins and re-derived demonstrations

- Before the source fixes, the focused new-pin run returned `11 failed, 6 passed, 108 deselected, 1 error in 6.33s`. Its failures covered the capability fallback, detached-root and Git-environment behavior, setting sources, unknown capabilities, shim diagnostic, Claude seams, and injected Node lookup. The fixture teardown error was caused by the inherited Git environment and disappeared after the test itself cleared those variables before cleanup.
- After the source fixes, the same focused run returned `17 passed, 108 deselected in 7.80s`.
- H10 mutation: replacing the boundary function with the old false constant made its direct contract pin return `3 failed in 1.97s`; the exact boundary function was restored.
- M14 mutation: removing the explicit-override capability preflight made the override pin return `1 failed in 0.96s`, with an incapable Codex resolver call before Claude; the guard was restored.
- M13 mutation: bypassing shared automatic resolution with `vendor_cli.resolve_codex` made the caller-flow pin return `1 failed in 0.81s`; the shared resolver call was restored.
- L10 mutation: removing `required=True` from `--requires` made the parser pin return `1 failed in 0.46s`; the required option was restored.
- L11 mutation: renaming the public option made the copied-help pin return `1 failed in 0.32s`; its assertion now checks the option spelling with its choice metavariable, not a descriptive mention, and the public option was restored.
- Re-derived governing-prose measurement over `dispatch.md`, `the-record.md`, `roster.md`, `dispatch-records.md`, and `the-stretch.md`: the settled-build figure was `+1,381 characters, +216 words` against `origin/main` (two characters below the review's `+1,383` because this PowerShell capture does not retain the final newline in two files). The final batch is `+601 characters, +73 words` against `origin/main`, and `-780 characters, -143 words` relative to the rebased pre-fix build. The bought corrections therefore do not add net governing prose.

## Executable floor

- `python tools/lint.py` returned `lint: 0 finding(s)`.
- `python tools/check_version_bump.py` returned `12 shipped-zone file(s) changed ... version 0.129.0 -> 0.130.0` with merge base `b0a1f0f`, the fetched `origin/main` tip.
- Sustained-finding probes (boundary truthfulness, capability fallback and override, each Git-root polarity, copied help and parser spelling, setting sources, unknown capability, resolver seams, bundle diagnostic, and implementer caller flow): `18 passed in 71.00s (0:01:11)`.
- `python -m pytest lib/tests -q`: `143 passed, 1 skipped in 120.49s (0:02:00)`.
- `python tools/dev.py check`: `1388 passed, 1 skipped in 353.71s (0:05:53)`.
- The direct substrate script reported nine existing `harness-token` diagnostics in unmodified historical files and a pre-existing README line. It is not the repository's required lint entry point; `tools/lint.py`, which integrates its relevant guards, passed cleanly. No executable floor probe was unavailable for this batch.

## Bought record corrections outside this write boundary

- **L6:** the pull-request body must remove its frozen derived size/count output and state the command and tree instead. Its old `Ten files, +269/-33` is false at the reviewed revision, and its `settling row` still-owed line is false.
- **L7:** record that the base-red attempt was uninformative because the pre-capability CLI rejected `--requires` during fixture setup, rather than presenting it as a discriminating guard failure. The attached/detached negative control is the meaningful evidence.
- **L22:** reduce the pull-request body's unsupported `five` occurrences to the two substantiated instances unless the holder can enumerate all five.
- **D1:** correct `SESSION-NOTE.md:23`: the real timeout set `outcome=error` and ended the loop; the capability refusal never ran, so its non-fallback was the pre-existing rule rather than this change's capability guard.
- **D2:** cross-reference the merged M14/M16 pair: M14's irrelevant explicit-override guard is bought and M16's opposing deletion is lapsed.
- **D3:** restate H1's merge note as two independently return-destroying timeouts, at the 900-second default and at 2700 seconds; no third wiring launch occurred. The 2700-second figure is sourced by `out-wiring.md.run.json`.
- These records and the pull-request body are outside this root or require GitHub writes. They were not edited under the task's write and publication bounds.

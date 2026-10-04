# D-854 — one lab reviewer release control

**Purpose:** retain #847's release-control choice and the holder's implementation reading. **Audience:** the holder and a future session changing the lab reviewer. **Success:** that reader can distinguish lab release authority, runtime provenance and review credit without changing adopter control.

This entry is keyed to implementing pull request #854 for work issue #847. The governing sources are the [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/847#issuecomment-5982099648), [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/847#issuecomment-5982400986) and amended holder reading supplied with this build. The build base is `8b6fbdb3ad72fd98b9ca569fd6daae5a058f01e6`; the version increment uses `main` at `6dee8252afc62b4151bfec63ae455607972c9027`.

## Decisions and meaning changes

The owner chose one callable lab workflow with one CLI pin over repeated changes in every caller and over an organisation-required workflow. Tradecraft follows merged `main` as the public canary; the Steward controls the moving `reviewer-stable` tag for downstream callers. The owner held a dedicated private canary until a need appears. A completed finder review, including one with findings, can justify a release; a skip cannot.

The implementation uses the defining job's platform identity, not the caller's GitHub commit fields or a fresh lookup of a moving ref. Preparation captures the workflow SHA; later jobs require agreement, and every checkout checks HEAD before executing the runtime. A hosted reporter whose preparation produced no SHA recovers its own immutable workflow identity, without starting a finder. This choice follows the artifact's recommended interface; live availability remains a post-merge falsifier, not something local fixtures establish.

The holder's first amendment limits provenance to explicit callers. The runtime derives none, so the shipped copy-whole template and direct adopter review bodies remain unchanged. Completed lab reviews append the supplied reviewer SHA and executable-verified CLI version before the existing attempt marker. Failure and oversize notices distinguish a configured pin from verified execution. The final marker still controls receipt identity; provenance adds no credit condition.

The second amendment puts one private trial per repository at the merged release SHA, after #847 merges and before tag creation and any downstream stub. The holder owns those trials and their cleanup. A failure holds the tag and carriers. The initial production failure holds remaining carriers for repair because first creation has no prior callable rollback target; later moves retain the one-tag rollback.

Credit and cancellation now share an exact leaf-name predicate for direct and nested called jobs. This replaces the entrance's exact display-name comparison and cancellation's prefix match, preserving their other run, head, event, pagination, attempt and cause rules. The only shipped proof-reference meaning change is its job-name sentence. The gate half belongs to change-proof #46; other repositories' stubs and the Steward's tag are separate acts.

## Evidence and custody

The workflow identity and checkout tests in `tools/tests/test_connected_review_packaging.py` exercise captured SHA propagation, recovery, mismatch refusal and caller isolation. That file keeps adopter template/reference equivalence separate from lab stub/shared checks and checks job permissions, runner selection and secret placement. `lib/tests/test_connected_review.py` exercises optional provenance, exact body limits, coverage allowance and cancellation causes. `lib/tests/test_work.py` exercises the actual receipt consumer with direct/called names and rejected run provenance. These tests accompany this entry on its implementing tree; run `python tools/dev.py check` there.

Local fixtures establish no live private-policy access, called-runner execution or release canary. The holder retains those outcomes on #847 and the Steward records release acts on #683. No raw run output is committed. The operating procedure has one home in `docs/cells/steward/references/connected-review-releases.md`; it stays repo-only so an adopter receives no lab release dependency.

# D-728 — Put design and owner attention before signoff

**Purpose:** preserve why filings carry facts rather than solutions, how the owner affirms a mechanical lane, where post-affirmation questions go, and why a new guard is deleted in isolation before it ships. **Audience:** a future session changing filing, the implementation-brief lanes, the work entrance, or the owner-attention boundary. **Success:** that session can change one part without restoring solution-shaped filings, path-inferred mechanical work, artifact or use obligations for the mechanical lane, or unbounded asks after affirmation.

Governed by the [affirmed implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/728#issuecomment-5789002677), the [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/728#issuecomment-5806352930), and the holder's [whole-change reading](https://github.com/Grimblaz-and-Friends/tradecraft/issues/728#issuecomment-5806355035). The implementation began at `777c723df2907b42d84684b202c6aafb83df2bc4` and ships as `0.155.0`.

## Context

The practice put design into filings, repeated it at pickup, charged small determinate corrections for an artifact, cold judgment and use, and let questions after affirmation return to the owner through several independent rules. Two bought rules arrived with the same program: a stated filing cost must be run or marked unrun, and a newly written guard must prove each arm's necessity by deletion.

The owner ruled that the boundary is affirmation. Facts arrive before it; solution design happens with the owner at pickup and is recorded in the brief. After it, the holder decides and records inside the affirmed rows, uses the coordinating session as the first door for the record and precedent, and reaches the owner through two doors only.

## Decision

### Filing records facts; pickup buys and designs

A filing carries what happened or the observed want, where, evidence, provenance, ties, the originating change and observed product harm. It carries no fix, option menu, recommendation, value argument or strongest case against a remedy. An extending comment has the same shape. A stated cost includes the run and result that establish it or is marked `unrun`; pickup tests an unrun cost before relying on it and keeps an untestable one as an assumption.

At pickup the holder and owner design the solution in turns, and the implementation brief records that sitting. This supersedes D-590, D-654 and D-664 where they made an issue the product of an already bought fix or required the filing to carry that fix. Their search, evidence, provenance, tie and purchase-over-scheduling decisions remain.

This repository has one local exception to the shipped intake route. A holder sends a practice defect to the Steward as facts; the Steward verifies, searches, files, folds or declines with the reason; and the owner buys at pickup. A product holder still files a product defect in that product with its harm named. This supersedes D-691 only on who files a defect in this practice: `skills/engagement/references/cross-session-intake.md` remains byte-identical, so adopters retain its general sender-filing rule.

### Mechanical is an affirmed lane, not an inferred size

`ordinary` / `mechanical` is a fourth lawful risk-and-lane pair beside the three existing pairs. It means a determinate, bounded correction or application of an already settled outcome leaves no substantive behavior or rule choice for the builder. The holder proposes it and the owner's affirmation selects it. Diff size, changed paths, draft text and unauthorized comments cannot.

The entrance centralizes that pair and the use-policy result in one effective classification. A lawful mechanical brief proceeds directly to build, without an artifact, cold verdict or manufactured holder-reading marker, and the build prompt carries the exact brief and lane reason rather than an obsolete artifact. It retains the current-head floor, configured connected reviewers, thread dispositions, proof, gate result and release report, and buys no panel. Explicit `run STAGE` remains authoritative, including a holder who explicitly asks for a normally skipped stage.

Use is not required for the mechanical lane even when the changed paths match the use policy. `run proof` generates the current-head proof and compatibility carrier with `required=false`, `classification=not-required`, `applicability=generated`, the affirmed comment as source and the lane exemption as reason. The readable rendering and compatibility line carry the same reason, and reviewer readiness uses that same classification. A head move still requires fresh generated proof. The shared gate is unchanged: its actual result is preserved and the release report records any bypass and reason. Change-proof #21 owns teaching the gate the lane.

This supersedes D-638 and D-664 on mechanical work needing no affirmed term, and D-726 and D-733 where the state-driven entrance and proof classified use only from artifact evidence and changed paths. Their explicit-run authority, proof schema, current-head rules and retained release obligations remain.

### After affirmation, the holder records calls and the owner has two doors

The holder decides and records every call inside the affirmed rows, even when the brief or stage map settles it. A question the record or precedent can answer goes first to the repository's assigned coordinating session; absent one, the holder performs and records the same check. The owner is reached only when the answer changes an affirmed row or the expected saving to the lab exceeds the cost of asking. The existing argued ask states which case applies and its cost; unknown cost and saving stay unknown.

The boundary governs surprises, contingent rows, the two-round cold cap and release handbacks. Wrong Shape still stops; a row-changing surprise continues on the recorded recommendation while its qualifying ask is put; exhausted rounds or an owner-reserved subject alone creates no third door. An amendment still requires the owner's affirmation and is never a silent edit.

Every post-affirmation owner ask and its answer is recorded on the associated issue or pull request, including one first made in conversation. The cross-change read now reads those records and counts and names each put, qualification, stated cost, coordinating-session or precedent route and known outcome. It does not count holder calls or reports as asks. This narrows D-638's automatic owner route for build surprises and the cold cap while retaining its Shape stop, and extends D-679 and D-691's record read without changing their cadence or actor. D-454's one ask form and marking rule remain.

### A new guard proves each arm by deletion

Substrate keeps its both-polarities and same-class negative-control standard and adds one authoring duty: before a new guard ships, delete it through the existing `spikes` cell procedure. Where two arms dispose of the same input, delete each arm separately. A green deletion means the arm's necessity was not established, so the author removes it or demonstrates the distinct behavior it protects. The spike cell continues to own detached-worktree or throwaway-clone isolation and disposal; no mutation framework or CI stage is added.

## Meaning changes

- A filing is factual intake for pickup rather than a bought solution or work statement.
- The local Steward, not an individual holder, files, folds or declines defects in this practice; the shipped cross-session intake sentence is unchanged.
- A valid `ordinary` / `mechanical` pair is the only authority for the artifact, cold-seat and use exemptions; an adopter with no coordinating session uses the recorded holder fallback.
- The proof's generated no-use reason may be the affirmed mechanical lane and then names the affirmed comment as its source; it does not falsely claim changed paths failed to match.
- Settled inside-row calls are recorded, and owner asks after affirmation are limited to row changes or savings worth more than their stated cost.
- The cross-change read includes recorded asks and rulings and counts repeated owner attention.
- A newly written guard's necessity is tested by deletion, with overlapping arms deleted separately.

## Evidence and boundaries

Parser, routing, prompt, proof, no-use and readiness polarities are in `lib/tests/test_brief.py`, `lib/tests/test_work.py` and `lib/tests/test_proof.py`. Run `python -m pytest lib/tests/test_brief.py lib/tests/test_work.py lib/tests/test_proof.py -q`, `python tools/lint.py`, and `python -m pytest tools/tests skills lib/tests -q -n auto --dist loadfile` on the tree under review. Mutation evidence for new guard-shaped conditions uses the detached worktree procedure in the `spikes` cell.

The build's isolated deletion run mutated the two arms of `path_requires_use and not mechanical` separately. With the path-policy arm deleted, `test_effective_policy_uses_the_lane_not_path_smallness_to_exempt_use` failed because ordinary docs-only work acquired a use duty; with the mechanical arm deleted, it failed because matching-path mechanical work acquired one. Restoring both arms returned the test to green, and the detached worktree was disposed.

No design-sitting form, proof schema, automated lane classifier, ask counter, cost ranker, mutation framework or gate-capability detector is added. #705, #721, #735 and #740 remain outside this decision; the shared gate work remains change-proof #21's.

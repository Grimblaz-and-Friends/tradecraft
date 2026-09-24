# D-747 — Let repository rules and committed policy identify the proof

**Purpose:** preserve why the entrance identifies a required gate from branch rules and top-level workflow provenance, and why proof fingerprints committed policy while the ordinary read still inspects the checkout. **Audience:** a future session changing gate collection, release reporting, reruns, proof freshness, or policy-source handling. **Success:** that session can revise one mechanism without restoring display-name gate matching, false-green uncertainty handling, checkout-byte fingerprints, or proof refusals during an ordinary read.

Governed by the affirmed implementation brief and settled artifact on [#740](https://github.com/Grimblaz-and-Friends/tradecraft/issues/740), carrying [#742](https://github.com/Grimblaz-and-Friends/tradecraft/issues/742). The implementation began from `777c723df2907b42d84684b202c6aafb83df2bc4` and ships as `0.155.0`.

## Context

The entrance selected the gate by a shared check name and fingerprinted policy from checkout bytes while naming the checkout revision. `git show 777c723df2907b42d84684b202c6aafb83df2bc4:lib/work.py` demonstrates both starting paths. The holder's live probe recorded that a check run carries only numeric `check_suite.id`, while its REST workflow run carries `check_suite_node_id`; the fixed GraphQL query over that node returns the top-level file repository and path, and its workflow database identity agrees with the REST runtime workflow identity. The Daemon response-shape regression in `lib/tests/test_work.py` retains those fields and identities.

Those faults had one boundary in common: the proof document and release report described evidence adjacent to the repository record rather than the evidence the gate reads from it. A copied workflow could be mistaken for the required workflow, and checkout normalization or local policy edits could produce a digest the named revision did not contain.

## Decision

### Branch rules identify the requirement; run provenance identifies its evaluation

The entrance reads all active rules for the pull request's base repository and ref. Each required-workflow entry contributes its source repository id and exact path, with `ruleset_id`, `ruleset_source`, and `ruleset_source_type` retained as rule evidence. A successful read with no workflow rule is `none`; a failed, malformed, or incomplete read is `unidentified`.

For each Actions check, the REST workflow run supplies `check_suite_node_id`. A fixed read-only GraphQL query resolves the suite's top-level file repository and path and validates both run and runtime workflow identities against REST before joining them. Query batches are capped at GitHub's nodes limit. Source repository comparison is case-insensitive, path comparison is exact, and display names, reusable references, target-repository workflow ids, and configuration fields are never substitutes.

Top-level source identity classifies a run as gate or ordinary; runtime workflow identity still groups genuine reruns and supplies rerun identity. A positively matched gate leaves the ordinary floor. A check resolved to another source stays ordinary even when its display name or path is shared.

### Uncertainty cannot become green or send a possible gate back to the floor

An unresolved Actions run that could be a required source prevents a green claim even beside a matched success. While the workflow requirement is known or the rules are unreadable, such a red or pending run waits with the `unidentified` reason rather than being dispatched as an ordinary floor failure. Once provenance resolves it to another source, its ordinary conclusion applies normally.

Required-source results aggregate conservatively across every source. An explicit current failure is red; an unresolved candidate prevents green; stale, pending, and absent evidence remain distinct reasons. A pending current run retains the holder-readable pending reason and never becomes a generic claim that no run exists.

### The ordinary read and proof publication use different lawful policy views

The ordinary entrance continues to load `.tradecraft/work.json` and the use rules from the holder checkout, including an untracked or ignored work configuration, because those files control what that read inspects. It separately derives proof-source revisions and digests from raw Git blobs. Proof freshness uses the committed digest and committed use policy and excludes checkout-dirtiness diagnostics from the document comparison; the ordinary report still names those diagnostics.

`run proof` alone requires each present policy to be clean. Git status includes ignored files, so a present ignored policy cannot escape the refusal. The holder root must be the repository top level, ensuring status paths and full-tree blob paths describe the same files. An optional work configuration absent from both revision and worktree keeps unavailable provenance; no blob is invented.

Policy and pull-request stability are rechecked around publication. A post-publication policy race says the document was posted for the earlier state and completion is not current. Pull-request stability compares the head plus base repository and ref; an advancing base revision does not invalidate rules that are selected by repository and ref.

## Rejected alternatives and consequences

**Use the check-run suite object directly.** Rejected because the recorded and live check-run payload exposes only its numeric suite id; the workflow-run payload carries the GraphQL node identity.

**Group by top-level source file.** Rejected because classification and rerun grouping answer different questions. The source file says whether a run is the required gate; the runtime workflow id says which evaluations are genuine reruns of one producer.

**Treat every unresolved Actions check as ordinary.** Rejected because a failed required run with unavailable provenance would dispatch the executable floor, contradicting the holder-facing gate wait. Treating resolved nonmatching checks as uncertain was also rejected because it would hide real failures from copied workflows.

**Use committed policy for the whole ordinary read.** Rejected because it silently discards local work configuration and changes what the holder asked the entrance to inspect. Committed policy governs proof provenance and freshness; working policy governs the read.

**Bind proof stability to the base SHA.** Rejected because the required-workflow query is keyed by base repository and ref, so an unrelated base advance is not an identity change.

## Meaning changes

- D-733's gate verdict and rerun handoff now derive gate identity from branch rules and top-level file provenance rather than display names.
- An unresolved possible gate is held outside ordinary floor routing until its provenance is known; a resolved copy remains ordinary.
- Proof policy provenance and freshness use committed blobs, while the ordinary entrance retains checkout policy semantics and diagnostics.
- The holder root is explicitly the repository top level for policy status and blob identity.
- Pull-request publication stability no longer treats a base-branch SHA advance as a change of base identity.

## Evidence

The real Daemon response-shape fixture, required-versus-copy polarities, unresolved-provenance precedence, runtime-workflow grouping, GraphQL batching, pending and floor routing, rule evidence, base-coordinate, policy dirtiness, ignored-file, root, freshness, and publication-race cases are in `lib/tests/test_work.py`. The unchanged proof wire contract remains covered by `lib/tests/test_proof.py`.

Run `python -m pytest lib/tests/test_work.py lib/tests/test_proof.py -q -p no:cacheprovider` and `python tools/dev.py check` on the tree under review. The holder's read-only `gh api` probe on Daemon run `35790907386` and local run `35790907096` demonstrates the REST and GraphQL identity join retained by the fixture. These commands, records, and test surfaces are the evidence; no derived result is frozen here.

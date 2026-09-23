# D-733 — Proof is one act per head

**Landed by** [PR #733](https://github.com/Grimblaz-and-Friends/tradecraft/pull/733). Closes [#725](https://github.com/Grimblaz-and-Friends/tradecraft/issues/725), [#706](https://github.com/Grimblaz-and-Friends/tradecraft/issues/706), [#719](https://github.com/Grimblaz-and-Friends/tradecraft/issues/719), [#682](https://github.com/Grimblaz-and-Friends/tradecraft/issues/682), and [#712](https://github.com/Grimblaz-and-Friends/tradecraft/issues/712). Governed by the latest [affirmed implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/725#issuecomment-5793803434), the [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/725#issuecomment-5793803168), and the holder's [whole-change reading](https://github.com/Grimblaz-and-Friends/tradecraft/issues/725#issuecomment-5793803771). The model decision reads the [#731 protocol](https://github.com/Grimblaz-and-Friends/tradecraft/issues/731#issuecomment-5789688853) and its [recorded progress](https://github.com/Grimblaz-and-Friends/tradecraft/issues/731#issuecomment-5793813569).

## Context

Change proof had become several independent acts: the holder copied evidence into markers, a gate looked on different surfaces, readiness depended on a label not declared with the work, and checks with the same display name could hide one another. A proof could therefore stall on where evidence was posted or on a holder's transcription rather than on whether the change was demonstrated.

The same change carried the standing-default decision because #731 compares the models on #725's artifact and implementation roles. That comparison had not produced a definitive result for every role when the implementation was built. The owner's affirmed rule says a thin result preserves a named interim rather than turning non-detection into equivalence.

## Decision

### The entrance composes one proof document per head

`lib/proof.py` owns strict proof-v1 composition, validation, deterministic JSON, and the readable rendering. `lib/work.py` gathers the public record and local dispatch declarations, then the holder-owned `run proof` operation publishes one authenticated `tradecraft:proof:v1` comment for the current pull-request head. The wire contract ships in `skills/work/references/proof.md`, `skills/work/references/proof-v1.schema.json`, and `skills/work/references/proof-fixtures/`.

Public floor, use, reviewer, and disposition records stay evidence. Machine-local bundle and staffing facts stay declarations, including an explicit `unverifiable` value and reason where the matching record is missing or unusable. The producer emits neither a `verified` field nor a `verified:` line; the independent gate owns that conclusion. Re-running unchanged evidence updates no content, older-head documents remain, and conflicting authorized documents at one head are refused.

The read-only decision treats proof as holder-owned work and requires an explicit successful current-head gate conclusion before recommending `release-report`. When no current-head check exists, GitHub's `CONFLICTING` mergeability state is reported as the reason a run may be absent; unknown mergeability remains unknown. Same-name checks compete only within an identified producer workflow, and an unresolved workflow identity cannot let one run hide another.

For one compatibility release, proof also projects the lawful legacy use or generated no-use carrier. The marker remains an input to the entrance; [change-proof #20](https://github.com/Grimblaz-and-Friends/change-proof/issues/20) owns independent consumption of the document, and its removal follow-up owns retiring the legacy path.

### Readiness is one ordered, head-bound step

`.tradecraft/work.json` declares the optional reviewer label; this repository sets it to `reviewers`. The holder-owned `run ready-reviewers` operation validates the current-head floor and applicable use, applies that label, refetches and compares the head, marks a draft ready, and verifies both readiness and the head again. A push caused by the label or racing the ready mutation therefore cannot transfer old-head evidence to a new ready head. Repeating the operation repairs a missing label on an already-ready pull request without toggling its state.

Reviewer credit requires a separate substantive receipt from every configured reviewer. A notice that review was skipped, limited, rate-limited, still running, or unavailable receives no credit whether it arrived as a pull-request comment or review body. Every top-level inline finding requires an authorized first-line disposition.

### Row 6 installs named interims, not inferred winners

The owner's choice comes from the holder's role-specific recommendation when #731 closes; artifact selection, exploratory authoring, and vendor claims do not make that choice. Until a result is definitive under that protocol, the implemented values are explicitly **interim**:

- Codex implementer and Codex seats: `gpt-6-sol` at `xhigh`.
- Claude ordinary seats: `claude-opus-5-5` at `xhigh`.
- Claude cold and terminal seats: `claude-opus-5-5` at `max`.

Those full identifiers are pinned in `lib/dispatch_implementer.py` and `lib/dispatch_seat.py`; explicit per-change overrides still win. `skills/engagement/references/dispatch-records.md` now keeps three outcomes distinct: definitive separation recommends the better model, definitive confident no-difference recommends the cheaper model on relevant owner-paid cost evidence, and inconclusive, missing, or interrupted evidence retains the owner's named interim with its further runs recorded.

This supersedes [D-645](https://github.com/Grimblaz-and-Friends/tradecraft/blob/main/docs/architecture/decisions/D-645-2026-09-16-comparison-chosen-model-defaults.md) only where it treated a comparison that *separates nothing* as sufficient to choose the cheaper model. Failure to detect a difference is not a confident finding of no difference. D-645's comparison-first rule, role specificity, and owner-paid-cost qualification remain.

## Further comparison work owed by the interims

The interims remain labelled until #731 records a definitive recommendation and the owner chooses from it. If its present round remains inconclusive, the executable follow-up is:

- **Codex implementation and seat default:** in fresh isolated trees, run two further paired build repeats of `gpt-6-sol` at `xhigh` and the incumbent `gpt-5.6-sol` at `xhigh` from the same settled implementation artifact. Each repeat receives a byte-identical assignment, runs the hidden acceptance suite and `python tools/dev.py check`, and records commit completion and owner-paid cost evidence. Before launch, #731 records the confident-no-difference rule those repeats will be judged under. The unresolved decision is whether Sol 6 definitively separates, is confidently no different so cost decides, or remains interim.
- **Claude judging default:** run two further blind judging repeats for `claude-opus-5-5` at `xhigh`, `claude-opus-5-5` at `max`, and the incumbent `claude-opus-5` at `max`. Each repeat judges the same held-out best, middle, and weakest artifact set with the same known-miss and false-alarm scoring, in fresh sessions with provenance withheld. The unresolved decision is whether Opus 5.5 separates for ordinary and cold/terminal judgment without increasing false alarms, or remains interim at the owner's chosen efforts.

These repeats are owed comparison work, not part of PR #733's release floor, and they do not change the standing defaults without the resulting recommendation and owner choice.

## Rejected alternatives and consequences

**Let the holder type proof.** Rejected because the producer would be asserting its own success values and every transport move could invent another execution. Composition retains original provenance and lets the gate re-derive what GitHub exposes.

**Call declarations verified.** Rejected because the gate cannot independently read machine-local bundles. Authorized production establishes who declared a value, not whether an inaccessible execution occurred.

**Mark ready and repair the label later.** Rejected because ready-triggered reviewers can fire before the label they require exists. Label first, then a head-bound transition, is one retryable operation.

**Release on any terminal gate conclusion.** Rejected because `neutral`, `skipped`, and an absent conclusion establish no independent verification. Only explicit success advances to release reporting.

**Take the cheaper model whenever one run does not separate candidates.** Rejected because a thin or interrupted comparison is not a confident no-difference finding. It retains the named interim and makes the missing experiment visible.

## Evidence

The implementation surfaces are `lib/proof.py`, `lib/work.py`, `lib/dispatch_implementer.py`, `lib/dispatch_seat.py`, `.tradecraft/work.json`, and the shipped references named above. Their executable checks are in `lib/tests/test_proof.py`, `lib/tests/test_work.py`, `lib/tests/test_dispatch_implementer.py`, and `lib/tests/test_dispatch_seat.py`. The full repository floor is `python tools/dev.py check`; it runs after this entry and its index row are written, so this entry records the command and source surfaces rather than freezing its output.

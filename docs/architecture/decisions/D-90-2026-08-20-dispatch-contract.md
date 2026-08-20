# D-90: The dispatch contract

**Status:** Accepted 2026-08-20 (PR #90)

## Context

[D-78](D-78-2026-08-19-carry-the-reasons.md) admitted one dispatch rule: a review dispatch carries the artifact's purpose statement verbatim or by link, never the dispatcher's paraphrase. Its exhibit was PR #78's own panel, which judged a compressed charter and filed false findings against affirmed content.

The rule reached the purpose statement and nothing else. Every other packet a stage receives was still authored by the dispatching session — which is, in this repo's single-session lanes, the artifact's author. Two incidents followed within a day. On [#82](https://github.com/Grimblaz-and-Friends/tradecraft/issues/82): PR #81's six-seat panel was dispatched as six bespoke prompts, the shared material appearing in all six in varying wording and position, so a dispatcher free to retype the assignment six times could drift on it six ways — in exactly the sentence D-78 had just said must not be a paraphrase. On [#88](https://github.com/Grimblaz-and-Friends/tradecraft/issues/88): a judge dispatched with "six matters it must settle itself," a docket the parent chose, so whatever did not make the parent's list would never be judged. Both raised by the owner in conversation, both filed at his instruction.

## Decision

**Every dispatch is built in three parts, in this order**: a shared block, byte-identical across every recipient at that stage, carrying the assignment and every predecessor stage's output whole; then a dispatcher's note where there is one, labeled as such and additive; last the recipient's own identity and lens brief. Calling attention is lawful; filtering and restating are not. **The judge's docket is set by rule** — every merged finding, every defense verdict, every collision or open matter any stage flagged — with the dispatcher's "matters to settle" arriving as notes inside it.

This generalizes D-78 rather than sitting beside it. D-78's clauses naming the scope ("binds every dispatched role") and the reason (the author compressing its own charter is an interested-party summary) move into the general rule, and the cold-boundary parenthetical that carried them shortens to "(verbatim or by link)" — one home for the rule, so it cannot drift between two.

**Placement is part of the decision.** Both issues proposed extending the cold-boundary paragraph. The general rule sits after it instead, and the docket rule sits at the terminal stage: a session dispatching the judge never reads the cold-seat paragraph, and a rule binding every stage buried inside a rule about one stage stops firing for the others.

**#82's prompt-caching argument is not load-bearing.** Cache-hit telemetry for subagent dispatches is not visible from this runtime, so the premise is declared rather than asserted, with its falsifier: per-dispatch cache-read token counts across a panel run, if a runtime exposes them. The correctness half carries the rule alone.

## Rejected

- **Judge-as-orchestrator** — the judge running the review and dispatching its own seats. It removes the author's thumb from the scale and replaces it with the judge's: a judge that staffed the panel, wrote the briefs, and ran the merge is a party to everything it later rules on, which is what the independence rules ("the judge never a finder") exist to prevent. It also spends the fresh terminal vantage the staffing section says to protect most.
- **Two separate changes, one per issue.** They are one rule at two scopes and land at the same location; the second would rewrite the first's sentence under a gate that had affirmed only half the composition.
- **A prompt template or file format.** The rule constrains order and content, not markup. A template is a capability wrapper.
- **A mechanism.** No script can read a dispatch prompt's shape; the doctrine's admission order stops at skill prose here.

## Deferred, with the evidence that would reopen them

- **The parent-owned merge stays parent-owned.** Dedup can bury a finding, so the merge is in this defect class. The narrow duplicate definition — same failure mode at the same location — is the existing guard, and this change should not solve everything at once. **Reopen on:** the class recurring through the merge.
- **A clerk that is not the author.** If these prose rules fail the way prose rules sometimes do here, the named next step is moving review orchestration onto a fresh session that did not write the artifact — not onto the judge. [#85](https://github.com/Grimblaz-and-Friends/tradecraft/issues/85)'s handoff shape makes it nearly free once it lands. **Reopen on:** a recurrence after these rules are in force.

## Evidence

[#82](https://github.com/Grimblaz-and-Friends/tradecraft/issues/82) and [#88](https://github.com/Grimblaz-and-Friends/tradecraft/issues/88) (the two incidents and the settling conversation), the [affirmed artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/88#issuecomment-5359125382), D-78 (the narrow rule this generalizes and its charter-compression exhibit), and the PR #90 review record.

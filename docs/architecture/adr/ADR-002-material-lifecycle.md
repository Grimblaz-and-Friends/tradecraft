# ADR-002: The three materials, and the lifecycle between them

**Status:** Accepted 2026-08-15

## Context

Every rule in this system is expressed in one of three materials: **model judgment** (nothing written), **prose** (methodology the model reads), or **code** (contracts that execute). The predecessor repo supplied hard evidence about all three failure modes:

- **Prose contracts fail silently.** Nearly every recurring defect class was a format or state rule written in prose that a model then violated invisibly (marker syntax rules, assertion formats, comment-placement contracts). Each cost a debugging session; none would have existed had a script owned the format.
- **Code encoding unstable rules rots expensively.** An elaborate audit apparatus (manifest schemas, containment guards, drift detection) needed crash fixes in its final month, guarding rules that existed only because of how the then-current process happened to work. Worse, workflow logic pushed into code was root-caused *six times* to the same failure — a unit-tested library never wired to the live path. Workflow is exactly what changes when models improve.
- **Prose written for weaker models becomes a tax.** The root instruction file grew to thousands of always-loaded words because every incident defaulted to "add a paragraph" — paragraphs that fire every session, relevant or not, and never retire.

A one-axis rule ("if it can be violated silently, make it code") produces the second failure. The rule needs two axes — **checkability × durability** — and, more importantly, a lifecycle rather than a static assignment.

## Decision

**Every rule starts as model judgment.** Promotion is earned, never speculative:

1. **Judgment → prose**: when inconsistency across sessions has *actually cost something*, and the rule shapes judgment (what to consider, in what order, to what standard). Litmus: *would a strong senior engineer need this instruction, or just the goal and constraints?* Prose teaches; it never enforces.
2. **Prose → code**: only when the rule has (a) been violated at real cost, (b) survived change long enough to look stable, and (c) has a checkable form. Code is the retirement home for rules that have proven durable — never the first draft of a rule.

**Rule prose carries three things, and only the third belongs elsewhere.** The **specification** is the rule — four seats, one pass, an 8,000-character budget; numbers here are part of the rule and cannot rot. The **reason** is the mechanism a reader needs to apply the rule well and to notice when it stops applying; it is short, general, and stays inline, because a model reading mid-task will not follow a link and a rule whose point is invisible gets tidied away by whoever meets it next. The **evidence** is what proves the reason — counts, dates, incidents, prior findings — and it goes behind a pointer into the evidence registry: it is long, it drifts, it cannot be checked from the prose anyway, and reciting it spends every session's context serving a reader who is not there. Explain why; do not litigate it. A sweep deciding whether a rule is still load-bearing **follows the pointer**; a session applying the rule reads the reason and never needs to.

**Demotion is just as mandatory:**

- Prose is pruned when models stop needing it. Every prose rule carries its exhibit (why it exists), so a future sweep can tell load-bearing from vestigial.
- A code guard whose condition can no longer recur (the process it guarded changed) is deleted, not maintained. A test suite you are afraid to delete from is doctrine accreting in a compiler.

**The one exception that skips the lifecycle: boundary formats.** Formats and state at the GitHub boundary (markers, ledger rows, version stamps) are interchange formats whose whole point is durability across sessions and runtimes — stable by nature, and the site of every historical silent-violation incident. These are code from day one: the model never hand-writes them; it calls an emitter and a validator. (Interim waiver, recorded in ADR-006 §5: until the emitter library exists, ledger rows are hand-written and validated by the packaging lint — the smallest honest discharge of this rule, not an exception to it.)

## Consequences

- New rules are cheap to try (they start as nothing) and expensive to fossilize (promotion requires an incident record).
- Code volume stays proportional to *proven* stability, which is the brittleness control: when models or requirements change, the demolition surface is small.
- Every promotion and demotion is a recordable event, which is what lets process weight be governed by evidence (ADR-006).

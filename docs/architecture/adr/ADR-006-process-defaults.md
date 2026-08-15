# ADR-006: Process defaults — start light, escalate on evidence

**Status:** Accepted 2026-08-15 · Amended 2026-08-15 (review made artifact-positional, not implementation-only)

## Context

The predecessor started heavy and spent years earning its way lighter: a five-stage pipeline as the entrance, a five-pass review panel, and filing-by-default that turned every unit of work into two or three tracked follow-ups (324 open issues; 40% untouched for 90+ days). Its own measurements pointed the other way: the widest review panel once sustained a *false* finding, while re-running fixes cheaply caught real defects at a ~1-in-3 rate; the instrument for right-sizing process (a phase-containment ledger recording where defects were introduced vs caught) was the right idea, added years too late to shape the defaults.

## Decision

Invert the predecessor's defaults; keep its instrument from day one.

1. **The minimal lane is the entrance.** One conversation takes work from intent to done. Heavier lanes (staged design, deeper review, unattended runs) exist and are opt-in — chosen for cause, not defaulted into.
2. **Review attaches to artifacts, not only to code.** A framing, a design, a plan, and an implementation are each reviewable artifacts, and a defect is cheapest caught at the artifact where it was introduced — a design flaw found in the design costs a conversation; the same flaw found in the implementation costs the implementation. So escalation has **two axes**: *depth* (a wider or stronger review of one artifact) and **position** (reviewing an earlier artifact before building on it). When risk justifies exactly one escalation, position usually beats depth. In the minimal lane this costs almost nothing: the pre-implementation artifact may be a stated approach a paragraph long, and its review *is* the convergence gate (ADR-005) — the check always runs; what's opt-in is a dedicated adversarial challenge of the design or plan before implementation begins.
3. **Review default at any position: one adversarial pass plus mandatory re-validation of fixes.** Fix re-validation is non-negotiable at every depth (the evidence says it outperforms panel width). Depth and position are escalated per-change by declared risk, and de-escalated only by ledger evidence — in both directions, weight follows evidence, never cost arguments and never habit.
4. **Filing is the exception.** A finding's default disposition is *fix it now* or *drop it with a one-line reason*. Its two lawful homes are the change that found it, or a guard (ADR-002 promotion) — a guard fires when the condition recurs; an issue fires never. Proposing a tracked follow-up requires stating why both other homes were rejected, and the proposal must pass the pickup test: would this actually get picked up if time opened tomorrow?
5. **The ledger exists from the first PR.** One code-appended record of where each defect was introduced, where it was catchable, where it was caught. This is also what makes the position axis governable: "catchable at design, caught at implementation" recurring in the ledger is the evidence that buys a standing pre-implementation review; its absence is what retires one.
6. **Quality is still the first constraint.** None of the above relaxes *coverage* — what gets looked at — only the ceremony around it. When lightness and a needed check conflict, the check wins; the ledger is how a check proves it is no longer needed.

## Consequences

- Process weight is a managed quantity with an evidence loop, not a ratchet.
- The backlog measures intent: everything in it passed the pickup test, so it stays small enough to be real.
- Heavier process must recruit evidence to exist, which means the ledger gets consulted, which keeps the loop honest.

# ADR-001: Identity — a practice, not an orchestrator

**Status:** Accepted 2026-08-15

## Context

This project's predecessor (agent-orchestra) spent three years as a multi-agent orchestration system and spent those years collapsing its own premise: it began with a cast of persona agents (Experience-Owner, Solution-Designer, Issue-Planner, Code-Conductor, a dozen specialist shells) and ended with a single executor plus skill-as-adapter — the methodology had moved into skills, and the personas turned out to be costumes for weaker models. Meanwhile every capability it wrapped (subagents, planning, memory, review commands) was progressively shipped natively by the vendors underneath it.

## Decision

Tradecraft's identity is the **practice**, not the mechanism: the standards, memory, and judgment structure that turn frontier-model capability into trustworthy engineering. The test for whether something belongs here: *would a vendor ever ship this?* If yes (it is a capability), it does not belong. If no (it encodes our standards, our judgment economics, or our accumulated lessons), it does.

Agents are retained only as a **mechanism**, used when structurally required for one of exactly three things:

1. **Context isolation** — a subtask whose working material would pollute or overflow the parent.
2. **Adversarial independence** — a reviewer must not share the author's context, or it inherits the author's blind spots.
3. **Parallelism** — fan-out over independent work.

No persona agents. No agent is the home of methodology; methodology lives in skills (ADR-003).

## Consequences

- The repo's durable asset is its accumulated discipline, not its wrappers. Vendor feature releases are absorbed, not competed with.
- Thin dispatch shells (two or three, at the composition layer) are the entire agent surface.
- Anything that starts to look like an orchestration framework is presumptively out of scope and needs an argued exception.

# ADR-005: The interaction charter — where the human's time goes

**Status:** Accepted 2026-08-15

## Context

Human attention is the scarcest resource in the system, and the predecessor learned its economics the hard way: per-action approval prompts trained rubber-stamping, preference questions interrupted flow, and the one distinction that consistently worked was separating the *check* (always runs) from the *question* (fires only when the human's input can change the outcome). Its unattended lane also proved a contract worth keeping even though the implementation failed: zero questions by construction, typed halt reports instead.

## Decision

### The organizing question

Every touchpoint answers: **what does the human uniquely provide at this moment?** Three possible answers, each dictating a structure:

1. **Judgment only the human can supply** — intent, taste, priorities, risk appetite, and anything irreversible or outward-facing. These are **gates**: designed-in, non-overridable by pacing directives, and worth human time precisely because no model capability substitutes for them. The gate set (expected to evolve by evidence, not by accretion): *framing* ("is this the problem?"), *convergence* ("is this the approach?"), *commitment* ("is this the bet?" — scope/plan approval), and *release* (merge, publish, delete). A gate must be able to state what the human uniquely decides at it; a gate that cannot is automation wearing interaction's clothes, and is cut.
2. **Information the system can obtain** — never ask. A question containing a fact the agent could have looked up is a defect.
3. **Confirmation of the predictable** — do not ask. Act and report if reversible; if not, batch into an argued-case gate (per-item recommendation with reasoning; the human's approve/modify/drop is the interaction).

### Gate vs. question

The *check* always runs. The *question* fires only when the outcome is genuinely indeterminate — when the human's answer can actually change what happens next. A gate whose evidence determines the answer announces its conclusion, names the deciding evidence, carries a standing override, and proceeds.

### Consent travels with the decision

Once the human approves a decision, everything entailed by it executes without re-asking. Per-action re-approval is how approval fatigue destroys the gates that matter.

### Two lanes, structurally distinct

- **Attended**: conversational. Gates fire inline. Every question arrives as an argued recommendation — state, conflict, and evidence first, then the ask — batched at phase seams, never dribbled mid-stream.
- **Unattended**: **zero questions by construction.** Everything either proceeds by pre-approved rule or halts with a typed, legible halt report processed on the human's schedule. Free-prose stops that could be mistaken for completion are forbidden.

Every skill that can pause declares which lane it runs in. "Maybe ask, maybe halt" is the worst of both and is not a lawful shape.

## Consequences

- Human time concentrates at the four gate types and the batched exception queues of unattended runs; everything else is designed to cost nothing.
- Question quality is reviewable: a transcript's questions can be audited against answers 2 and 3 above.
- Pacing directives ("don't stop to ask") apply to preference questions and never to gates — the lever to skip a gate is the option the gate itself offers.

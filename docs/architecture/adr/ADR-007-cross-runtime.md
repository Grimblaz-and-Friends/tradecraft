# ADR-007: Cross-runtime — Claude and Codex above one practice

**Status:** Accepted 2026-08-15 · Amended† 2026-08-15 (the Context's timing claim corrected — the predecessor's Linux CI arrived not *in year three* but in its eighth month, 2026-08, retrofitted as its own multi-chunk project — evidence: [`6652ac8`](https://github.com/Grimblaz-and-Friends/tradecraft/commit/6652ac8)) · Substrate ruled 2026-08-15: **Python** · Amended† 2026-08-15 (§4 narrowed from *both-runtime* to **both-OS** CI: the Linux leg is the current *proxy* for Codex compatibility, and a true Codex check — the suite exercised by a Codex agent with a defined failure condition — does not exist yet and is not asserted before it does — evidence: the 35-finding full-repo adversarial pass, [`fa3345b`](https://github.com/Grimblaz-and-Friends/tradecraft/commit/fa3345b))

**Frozen 2026-08-18 by [D-53].** Historical record; operative rules live in the statute. Only status-line supersession pointers may be appended.

† *An entry marked this way was recorded retroactively on 2026-08-17 by the index sweep in [issue #18](https://github.com/Grimblaz-and-Friends/tradecraft/issues/18): it is dated by the commit that landed the change, and its motivation is reconstructed from that commit's own record rather than stated at the time. New entries append to the status line above, never past this note.*

## Context

The predecessor's cross-tool bet (Copilot + Claude) taught both halves of a lesson. What survived cheaply: tool-agnostic methodology bodies with thin per-platform adapters, and durable state on GitHub — neutral ground either runtime can read. What died expensively: deep per-tool machinery, and a scripting substrate (PowerShell) that carried Windows-shaped assumptions, a long catalog of silent-corruption traps, and friction against Linux sandboxes. Its Linux CI arrived only in its eighth month (2026-08), retrofitted as its own multi-chunk project rather than existing from the start.

## Decision

1. **The practice is runtime-neutral by construction.** Skills are written tool-agnostically; anything Claude- or Codex-specific lives in a declared adapter surface at the composition layer, never in a skill body.
2. **State on GitHub is the interchange layer.** Either runtime resumes any work from the durable record; no session-local state is load-bearing across sessions or tools.
3. **Root instructions have one canonical home.** `AGENTS.md` is canonical (Codex reads it natively); `CLAUDE.md` is a pointer to it, never a fork of it. Same doctrine budget (ADR-003) applies to the canonical file.
4. **Both-OS CI from the skeleton commit.** Tests run on Linux and Windows in Actions from day one. The Linux leg is the current *proxy* for Codex compatibility (Codex sandboxes are Linux with default Python) — a true Codex check, meaning the suite exercised by a Codex agent with a defined failure condition, does not exist yet and is pulled into existence when real Codex work arrives (ADR-009), not asserted before then.

### Substrate: Python (ruled 2026-08-15)

The core library and skill scripts use **Python**: present by default in Codex sandboxes, no build step, cross-platform, and the substrate models write with the fewest silent-corruption traps. Alternative considered and declined: TypeScript/Node (stronger typing for boundary schemas, at the cost of a toolchain step). PowerShell is explicitly rejected for new code on the evidence above.

## Consequences

- Switching or mixing runtimes is an implementation detail, which is the point: the practice is the durable layer, the model is a component.
- The adapter surface is small and enumerable, so "does this work on Codex?" is a checklist, not an investigation.
- One substrate means one set of idioms to harden, one CI matrix, one thing new scripts can assume.

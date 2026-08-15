# ADR-007: Cross-runtime — Claude and Codex above one practice

**Status:** Accepted 2026-08-15 (substrate choice: **proposed**, see below)

## Context

The predecessor's cross-tool bet (Copilot + Claude) taught both halves of a lesson. What survived cheaply: tool-agnostic methodology bodies with thin per-platform adapters, and durable state on GitHub — neutral ground either runtime can read. What died expensively: deep per-tool machinery, and a scripting substrate (PowerShell) that carried Windows-shaped assumptions, a long catalog of silent-corruption traps, and friction against Linux sandboxes. Its Linux CI arrived only in its eighth month (2026-08), retrofitted as its own multi-chunk project rather than existing from the start.

## Decision

1. **The practice is runtime-neutral by construction.** Skills are written tool-agnostically; anything Claude- or Codex-specific lives in a declared adapter surface at the composition layer, never in a skill body.
2. **State on GitHub is the interchange layer.** Either runtime resumes any work from the durable record; no session-local state is load-bearing across sessions or tools.
3. **Root instructions have one canonical home.** `AGENTS.md` is canonical (Codex reads it natively); `CLAUDE.md` is a pointer to it, never a fork of it. Same doctrine budget (ADR-003) applies to the canonical file.
4. **Both-runtime CI from the skeleton commit.** The core library's tests run on Linux and Windows in Actions from day one; Codex-compatibility is a standing CI dimension, not a retrofit.

### Substrate (proposed, not yet ruled)

The core library and skill scripts need one cross-platform substrate. **Proposed: Python** — present by default in Codex sandboxes, no build step, cross-platform, and the substrate models write with the fewest silent-corruption traps. Alternative considered: TypeScript/Node (stronger typing for boundary schemas, at the cost of a toolchain step). PowerShell is explicitly rejected for new code on the evidence above. This section flips to Accepted when the owner rules.

## Consequences

- Switching or mixing runtimes is an implementation detail, which is the point: the practice is the durable layer, the model is a component.
- The adapter surface is small and enumerable, so "does this work on Codex?" is a checklist, not an investigation.
- One substrate means one set of idioms to harden, one CI matrix, one thing new scripts can assume.

# ADR-003: Cells, bundles, and the five layers

**Status:** Accepted 2026-08-15

## Context

The predecessor was a monolith: skills referencing each other, agents referencing skills, a root file referencing everything — so every change was a release event, with cache-invalidation machinery and version-collision classes as the ongoing cost. Separately, its loading model proved that progressive disclosure works at two levels: a skill's body loads only when invoked, and its references load only when read.

## Decision

### The skill is the cell

The unit of everything is the **skill**: a self-contained cell carrying whatever mix of materials (ADR-002) its job requires — methodology prose, its own scripts and validators, its own tests, its own references. A skill about methodology may be pure prose; a skill wrapping a mechanical operation may be mostly script with a page of prose saying when to run it. The cell boundary, not the material, is what's uniform.

**Boundary rule:** a piece becomes its own skill when it has an **independent invocation trigger** — a situation where it should fire without the parent job being underway. If it only ever loads in service of one job, it is a `references/` file inside that job's skill, loaded on demand. Directory grouping (`skills/<area>/…`) is purely organizational and carries no loading or shipping semantics.

### Dependencies point down, never sideways

Skills may depend **downward** on one sanctioned core library — boundary formats and genuinely shared primitives only (ADR-002's exception) — and on nothing else. **No skill requires another skill.** Composition happens above the cells, not between them. A lint enforces both directions (ADR-004).

### The bundle is the plugin

Skills ship together in **one plugin** — discovered together, versioned together, firing independently. One plugin, because independent versioning multiplies release-hygiene machinery that already hurt at N=1, and no second audience with a different upgrade cadence exists yet. The no-sideways-dependency rule keeps a future split mechanical, so this decision is cheap to defer; revisit when a real second audience exists.

### The five layers

1. **State substrate** — durable state lives on GitHub (issues, PR comments, checks), never in session memory. All reads and writes go through the core library.
2. **Core library** — boundary-format emit/parse/validate and shared primitives. Small by constitutional intent.
3. **Skills** — the cells.
4. **Composition** — commands, thin dispatch shells (ADR-001), and lanes. All sequencing and all coupling live here, explicitly, so coupling is cheap to see and change.
5. **Doctrine** — a deliberately tiny root file with an enforced size budget: the constitution's pointers, not its content.

## Consequences

- A skill can be understood, tested, and shipped in isolation; a consumer who installs the bundle but uses one skill gets a complete experience.
- All coupling is quarantined in the composition layer, which is the only layer allowed to know the lane shapes.
- Splitting the bundle later requires no untangling, only repackaging.

# ADR-003: Cells, bundles, and the five layers

**Status:** Accepted 2026-08-15 · Amended† 2026-08-15 (layer 1 narrowed: "state" on GitHub means structured records — markers, ledger rows, version stamps, ADR-002's boundary formats — carried on issues, PR comments and checks, and ordinary git operations released to skills as runtime plumbing rather than routed through the core library — evidence: the 35-finding full-repo adversarial pass, [`fa3345b`](https://github.com/Grimblaz-and-Friends/tradecraft/commit/fa3345b)) · Amended† 2026-08-16 (the version-bump rule created — a change to any shipped-zone file bumps the plugin version, held as prose against a stated third instance — evidence: the rule had been missed twice, [PR #3](https://github.com/Grimblaz-and-Friends/tradecraft/pull/3), [`6bab536`](https://github.com/Grimblaz-and-Friends/tradecraft/commit/6bab536)) · Amended† 2026-08-16 (that rule rewritten from *the same commit* to *the pull request against its merge base*, and **promoted to code** as `tools/check_version_bump.py` wired into CI; its recurrence count **withdrawn as unreproducible rather than satisfied**; two guard constraints recorded — exit non-zero when the answer cannot be determined, and require a strictly increasing semantic version — evidence: the rule was missed again on the very PR recording the previous miss, and the first guard enforced per-branch while citing per-commit, [PR #6](https://github.com/Grimblaz-and-Friends/tradecraft/pull/6), [`10e07e6`](https://github.com/Grimblaz-and-Friends/tradecraft/commit/10e07e6)) — † *recorded retroactively 2026-08-17 by the index sweep in [issue #18](https://github.com/Grimblaz-and-Friends/tradecraft/issues/18): a marked entry is dated by the commit that landed the change, and its motivation is reconstructed from that commit's own record rather than stated at the time.*

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

Because the bundle is versioned as a unit, **a pull request that changes any shipped-zone file bumps the plugin version before it merges** — a consumer's only signal that installed and current differ. **Promoted to code 2026-08-16** (`tools/check_version_bump.py`, wired into CI): the owner's decision, taken after the rule was missed again on the very PR that recorded the previous miss.

The unit is the **pull request measured against its merge base**, not the individual commit. That is a deliberate correction to this rule's earlier wording, which said "in the same commit": this repository squash-merges, so the PR *is* the commit that lands, and a per-commit reading fails every intermediate commit of a multi-commit branch. The first attempt at this guard silently enforced per-branch while citing per-commit, and a panel found the mismatch — the rule was wrong, not the guard.

**The recurrence count that once gated this promotion is withdrawn, not satisfied.** An earlier version of this paragraph said the rule "has been missed twice" and would earn promotion "on a third instance". That basis was refuted by review: at commit granularity the misses run to eight, at merge granularity to zero, and no reconstructible basis produces three. Promotion here rests on the owner's decision plus the guard's own design, and a count nobody can reproduce is not evidence for anything. The counter is therefore gone rather than incremented, so nothing is left to go stale again.

**Two design constraints, both bought by the first attempt's withdrawal.** A guard that cannot determine the answer **exits non-zero** — the withdrawn one went silent whenever its base had moved, a state every merge produces, and printed the same line as a clean pass, so four failure modes were invisible. And the version must **strictly increase** as a semantic version; the withdrawn guard accepted a decrement.

### The five layers

1. **State substrate** — durable state lives on GitHub, never in session memory. "State" here means structured records — markers, ledger rows, version stamps, the boundary formats of ADR-002 — carried on issues, PR comments, and checks; those reads and writes go through the core library once it exists. Ordinary git operations (commit, push) are runtime plumbing, not boundary formats, and skills may perform them directly.
2. **Core library** — boundary-format emit/parse/validate and shared primitives. Small by constitutional intent.
3. **Skills** — the cells.
4. **Composition** — commands, thin dispatch shells (ADR-001), and lanes. All sequencing and all coupling live here, explicitly, so coupling is cheap to see and change.
5. **Doctrine** — a deliberately tiny root file with an enforced size budget: the constitution's pointers, not its content.

## Consequences

- A skill can be understood, tested, and shipped in isolation; a consumer who installs the bundle but uses one skill gets a complete experience.
- All coupling is quarantined in the composition layer, which is the only layer allowed to know the lane shapes.
- Splitting the bundle later requires no untangling, only repackaging.

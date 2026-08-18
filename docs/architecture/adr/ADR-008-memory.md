# ADR-008: Memory — the repo is the memory; vendor stores are inboxes

**Status:** Accepted 2026-08-15 · Amended† 2026-08-15 (§4 gains **one dated instrument**: every inbox entry carries its capture date and an entry older than **14 days is lapsed** — landed immediately or deleted — replacing the *"survives a few triages untouched"* pickup-test triage it had relied on, and the escape hatch narrowed from *if the inbox ever seems to need governance* to *more governance than this* — evidence: the retrospective proof that ADR-006's pickup prediction was false; the 35-finding full-repo adversarial pass, [`fa3345b`](https://github.com/Grimblaz-and-Friends/tradecraft/commit/fa3345b)) · Superseded in part by [D-53] (2026-08-18): ADR-008:17 — the constitutional lesson home becomes a statute amendment with its decision entry.

**Frozen 2026-08-18 by [D-53].** Historical record; operative rules live in the statute. Only status-line supersession pointers may be appended.

† *An entry marked this way was recorded retroactively on 2026-08-17 by the index sweep in [issue #18](https://github.com/Grimblaz-and-Friends/tradecraft/issues/18): it is dated by the commit that landed the change, and its motivation is reconstructed from that commit's own record rather than stated at the time. New entries append to the status line above, never past this note.*

## Context

The predecessor invested heavily in a session-memory system: a per-user store with an admission rule (recall triggers, exits, dated identities), compaction rules, sweep instruments, a ledger of the store's own history, and promotion machinery to move lessons into skills — machinery that itself needed manifests, audits, and crash fixes. Despite all of it, the core complaint stood: **improvements got left in memory.** Lessons accumulated in a private store, visible to one vendor's tooling on one machine, waiting for promotion projects that arrived in tranches months later.

The diagnosis, in this constitution's terms: memory was treated as an **archive requiring governance**, when the actual unsolved problem was that **exits were expensive**. Because landing a lesson in its durable home cost a project, lessons pooled in the store; because lessons pooled, the store needed admission rules, budgets, and sweeps; the governance then consumed the effort that cheap exits would have needed. The store's contents were also runtime-captive: invisible to any other vendor's tooling and lost to any other machine.

## Decision

1. **The repo is the system of record for everything learned.** A lesson's durable home is the one the material lifecycle (ADR-002) already defines: prose in the skill it improves (carrying its exhibit), a code guard where it has recurred, an ADR amendment where it is constitutional, or a repo-only doc where it is maintainer-facing. There is no fifth home called "memory."
2. **Vendor memory is an inbox, never an archive.** Claude's auto-memory, Codex's equivalents, and any session-local store are capture surfaces: cheap places to note a lesson mid-task. The wipe test defines the boundary: **wiping every vendor store must cost convenience, never knowledge.** Anything whose loss would matter has, by definition, not yet exited — and that is the defect to fix.
3. **Landing is same-session by default.** The session that learns a lesson lands it in its home before ending — the memory analog of ADR-006's "fix it in the PR that found it." Capture-without-landing is the exception, for lessons that genuinely cannot land now (e.g., mid-dispatch, or the home is contested), and the capture note states its intended home.
4. **No meta-governance — one dated instrument.** No admission contracts, no ledgers of the store's own history, no sweep machinery. Every inbox entry carries its capture date; **an entry older than 14 days is lapsed** — the retrospective proof that ADR-006's pickup prediction was false — and is landed immediately or deleted, nothing else. A capture note that invokes the "cannot land now" exception states its intended home, so a lapsed entry with no home named is deleted without debate. **If the inbox ever seems to need more governance than this, exits have gotten expensive again — fix the exits, don't govern the pool.**
5. **Cross-runtime memory is free because of 1.** Both runtimes read the same repo, the same skills, the same guards, the same GitHub state (ADR-007). Vendor stores never need to sync, because nothing load-bearing lives in them.
6. **Personal working-style knowledge** (how the maintainer works, standing preferences) follows the same rule with a different home: the user-global instruction files both runtimes read (`~/.codex/AGENTS.md` canonical-style, `~/.claude/CLAUDE.md`), or a repo-only doc where the preference is project-scoped. Whether project-scoped preferences belong in a public repo's repo-only zone or a private overlay is decided case-by-case at landing time.

## Consequences

- Knowledge compounds in the artifact that uses it, not beside it — a skill's lessons travel with the skill, to every machine, runtime, and consumer.
- The old promotion problem disappears structurally: there is no pool to promote *from*, only a small inbox that drains every session.
- The cost moved, honestly: same-session landing means sessions spend their last minutes filing lessons into skills. That is the deliberate trade — paid in the moment the context still exists, instead of months later by an archaeology project.

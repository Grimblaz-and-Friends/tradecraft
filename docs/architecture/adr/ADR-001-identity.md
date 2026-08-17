# ADR-001: Identity — a practice, not an orchestrator

**Status:** Accepted 2026-08-15 · Amended 2026-08-15 (real timing; persona value reopened) · Amended† 2026-08-15 (the belonging test replaced outright — *would a vendor ever ship this?* gives way to *name the standard, judgment rule, or recorded lesson this artifact enforces*, so a vendor shipping the same underlying action no longer disqualifies an artifact; and the structural persona ruling made reopenable by ledger or eval evidence, where it had read as settled — evidence: the 35-finding full-repo adversarial pass, [`fa3345b`](https://github.com/Grimblaz-and-Friends/tradecraft/commit/fa3345b)) — † *recorded retroactively 2026-08-17 by the index sweep in [issue #18](https://github.com/Grimblaz-and-Friends/tradecraft/issues/18): a marked entry is dated by the commit that landed the change, and its motivation is reconstructed from that commit's own record rather than stated at the time.*

## Context

This project's predecessor (agent-orchestra, first commit 2025-12-07) went in **eight months** from a cast of persona agents (Experience-Owner, Solution-Designer, Issue-Planner, Code-Conductor, a dozen specialist shells) to a single executor plus skill-as-adapter — the methodology had moved into skills, and maintaining the personas as separate agents proved to be cost without demonstrated benefit. That the collapse took only eight months sharpens the lesson: this structure decays fast. Meanwhile every capability it wrapped (subagents, planning, memory, review commands) was progressively shipped natively by the vendors underneath it.

## Decision

Tradecraft's identity is the **practice**, not the mechanism: the standards, memory, and judgment structure that turn frontier-model capability into trustworthy engineering. The belonging test is about what a thing **encodes**, not what it does: *name the standard, judgment rule, or recorded lesson this artifact enforces.* If it can be named, the artifact belongs — even when a vendor ships the same underlying action (vendors ship commit flows; a commit skill belongs only because and only insofar as it enforces our staging and verification standards). If no standard can be named, it is a capability wrapper and does not belong, however useful. Disputes are settled by that naming exercise, not by predictions about vendor roadmaps.

Agents are retained only as a **mechanism**, used when structurally required for one of exactly three things:

1. **Context isolation** — a subtask whose working material would pollute or overflow the parent.
2. **Adversarial independence** — a reviewer must not share the author's context, or it inherits the author's blind spots.
3. **Parallelism** — fan-out over independent work.

### Personas: structure ruled, value open

Two claims must not be conflated. **Ruled:** methodology never lives inside a persona — skills are its home (ADR-003), and no workflow may *depend* on a persona existing. This is what the predecessor's evidence actually supports: persona agents as structural units cost real maintenance and their removal lost nothing measured. The structural ruling reopens by the same route as the open question below: ledger or eval evidence that a persona-shaped structure caught or produced something the flat structure did not. **Open:** whether persona *framing* — casting a dispatch or skill prompt as an expert role — improves output quality. The research is genuinely mixed: a systematic study across 162 personas and four model families found no-to-slightly-negative accuracy effects ([Zheng et al., EMNLP 2024](https://arxiv.org/abs/2311.10054)), and later work found expert personas improve alignment but damage accuracy ([2026](https://arxiv.org/pdf/2603.18507)); yet task-specific gains from carefully designed expert personas are also reported ([2026](https://arxiv.org/pdf/2605.29420)), alongside real value for behavioral diversity in multi-agent settings and for tone. Disposition per ADR-002: persona framing may be adopted *per skill* where local evidence (ledger or eval) shows it helps that task, and is dropped where it doesn't. It starts as model judgment like everything else; it just never becomes load-bearing structure.

## Consequences

- The repo's durable asset is its accumulated discipline, not its wrappers. Vendor feature releases are absorbed, not competed with.
- Thin dispatch shells (two or three, at the composition layer) are the entire agent surface.
- Anything that starts to look like an orchestration framework is presumptively out of scope and needs an argued exception.

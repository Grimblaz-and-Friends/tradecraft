# D-630 — Capability-bound judging seats supersede the read-only transport claims

**Purpose:** preserve the meaning changes made when a judging job declares its capability, the launcher supplies or refuses it, and execute-capable Claude seats become available. **Audience:** a future session revising judging-seat transport, fallback staffing, or the evidence a dispatch record carries. **Success:** it can read the earlier decisions as their then-correct rationale, find the claims this change supersedes, and distinguish the owner question that remains from a decision this batch may make.

The owner affirmed [the implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/609#issuecomment-5671011763); its settled artifact requires explicit `read|execute` declarations, an execute-capable Claude route, detached-root verification, and a truthful selected-boundary record. The review of that result bought this entry because its changes reverse live descriptions in [D-585](D-585-2026-09-12-cross-vendor-seat-transport.md), [D-591](D-591-2026-09-13-one-holding-session-per-change.md), and [D-597](D-597-2026-09-13-equipping-a-dispatched-party.md).

## What this supersedes, and why the earlier readings were reasonable

- **D-585's shell-free Claude seat.** D-585 rejected general Bash while every judging seat was file-only, so its claimed read boundary would otherwise have depended on a shell command. This change deliberately supplies Bash only to a job declaring `execute`, records that Claude has no OS sandbox, and makes the dispatch name the execute seat's write boundary. The earlier refusal was reasonable for the old transport; it no longer describes the execute route.
- **D-585's ordinary-directory consequence.** D-585 says bypassing Codex's repository precheck lets the interface accept ordinary directories. This launcher now verifies a detached worktree before launching either vendor, so ordinary directories are refused. The retained `--skip-git-repo-check` flag is inert on this route; its deletion lapsed because the exact argv control remains valuable, not because ordinary directories still qualify.
- **D-591's unconditional qualifying fallback.** D-591 made an available fallback seat qualify, and grounded that breadth in the owner's affirmed #581 term. A fallback now qualifies only if it supplies the capability the job declared; an incapable primary is recorded as unlaunched while a capable fallback may proceed. Counting an under-equipped fallback as a judgment would contradict this change's explicit capability contract.
- **D-597's read-only judging-seat description.** D-597 correctly deferred a launcher until prose stated the concept, and its further objections concerned using `dispatch_seat.py` to launch a resumed implementer. This change does neither: it adds a one-shot judging-seat capability route after the concept exists. Its descriptive claims that the launcher is read-only and that execution gaps go to a seat with no shell are superseded. `the-stretch.md` now cites this entry for enforcement rather than treating D-597 as authority for it.

## The owner question D-591 leaves open

Whether #581's affirmed fallback term is still satisfied by a qualifying fallback that supplies the declared capability, or is amended by that condition, is the owner's decision. This entry records the narrowing and raises that question; it does not answer it. A later owner ruling must choose and record one of those readings before treating the term as settled.

## Record meanings that changed with execute capability

`revision_before` and `revision_after` still identify the recipient tree's committed revision, but an equal pair no longer establishes that an execute seat made no working-tree change. This batch records that narrower meaning without adding a shared working-tree field. It also records that the clause removed from `dispatch.md` about ambient defaults is still carried by `roster.md`; the selected permission boundary is a launcher request, not runtime observation.

## What this does not decide

This entry does not add a standing execution classification for the cold seat, defense, judge, or experience consumer; their job material declares a capability when it uses the launcher. It does not make detachment an OS write boundary, add containment to the record store, or add a working-tree-status field. Those are separate decisions, not omissions from this supersession.

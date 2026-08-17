# The constitution

The small set of decisions everything else answers to. Each ADR carries its exhibits — the evidence it was learned from — so a future sweep can tell load-bearing from vestigial (per ADR-002, that applies to these documents too).

| ADR | Decision | Status |
| --- | --- | --- |
| [ADR-001](ADR-001-identity.md) | A practice, not an orchestrator; agents demoted to mechanism; persona *structure* ruled out, persona *framing* value left open | Accepted, amended |
| [ADR-002](ADR-002-material-lifecycle.md) | Three materials; promotion earned, demotion mandatory; **a mechanism's *procedural specification* may enter by owner-admitted trial, marked and cut by default — any mechanism as of 2026-08-17, none yet run**; boundary formats skip the lifecycle | Accepted, amended |
| [ADR-003](ADR-003-cell-architecture.md) | Skills as self-contained cells; downward-only deps; one plugin bundle; five layers | Accepted, amended |
| [ADR-004](ADR-004-two-zones.md) | Repo-only vs shipped zones, lint-enforced | Accepted, amended |
| [ADR-005](ADR-005-interaction-charter.md) | Gate taxonomy; gate vs question; **commitment's question scoped by what the work's artifact states — answered early where the artifact states scope, firing where it does not or where design and plan are separate artifacts; below ADR-006 §2's floor its question is answered by §2's standing ruling**; consent travels with the decision; two lanes | Accepted, amended |
| [ADR-006](ADR-006-process-defaults.md) | Minimal lane default; review scaled by artifact weight (differentiated panel for substantial artifacts, seats recorded); position beats depth; **convergence gate before implementation, artifact on the work's issue, with a stated trivial floor below it whose mechanism-surface test is **reliance**, and which answers commitment's question by standing ruling**; filing is the exception; ledger from day one | Accepted, amended |
| [ADR-007](ADR-007-cross-runtime.md) | Runtime-neutral practice; GitHub as interchange; substrate: **Python** (ruled) | Accepted, amended |
| [ADR-008](ADR-008-memory.md) | The repo is the memory; vendor stores are inboxes with same-session landing; the wipe test | Accepted, amended |
| [ADR-009](ADR-009-predecessor-disposition.md) | Predecessor is reference material, not a source tree: nothing carries by default, pull-based rewrite, no presumption of correctness | Accepted |

## Open rulings and open questions

No rulings are pending from the owner. One evidence-driven question stays open inside its ADR: persona-framing value (ADR-001), decided per skill by ledger or eval evidence — no one needs to decide it now.

2026-08-15: a full-repo adversarial review (5 prosecutors, defense, judge) sustained 35 findings against the constitution, lint, and seed skill. The practice has since reviewed itself again, each review's sustained findings carried with its seat attribution in [../../ledger.jsonl](../../ledger.jsonl) and transcribed-claim provenance in [../evidence.md](../evidence.md).

## Amending

An ADR changes by commit like anything else, but the change must name the evidence that motivated it, and any lint rule enforcing the old text changes in the same commit (ADR-004).

**That naming has a surface, and it is the ADR's own `**Status:**` line** — a dated entry saying what changed and naming its evidence — with this index's Status column moving to `Accepted, amended` in the same commit — the unit the sentence above already uses, ADR-006 §2's pull-request unit being scoped to the trivial floor rather than declared universal. The **evidence-naming** obligation is not new; its surface is, and so is the index clause, which states what practice has done without exception since [`6c87931`](https://github.com/Grimblaz-and-Friends/tradecraft/commit/6c87931) rather than asking for anything new. The sentence above has always required the evidence to be named and never said *where*, and **eight of these nine ADRs fell through the gap** ([`fa3345b`](https://github.com/Grimblaz-and-Friends/tradecraft/commit/fa3345b) amended seven of the nine ADRs then existing, in ten separate amendments, and touched no status line; [`6bab536`](https://github.com/Grimblaz-and-Friends/tradecraft/commit/6bab536) amended four and touched none). **No generalization about commit shape survives the record** — the same review commit disclosed two amendments and silently made a third, and a single-ADR commit whose subject *was* that ADR disclosed nothing — so the failure is not that big commits swallow entries; entries were simply forgotten, and the surface is what makes forgetting visible.

The surface matters past the reader: `revision-diff`, the review seat whose whole job is a meaning change nobody recorded, tests against this exact line, so an unwritten entry is not merely an omission — it is the seat's input going missing. A genuinely cosmetic change — a typo, a dead link, a rewording a reader can check is meaning-identical — writes no entry, and is outside the sentence above; this is the trivial floor's triad (ADR-006 §2) borrowed for a different question, since what must be *recorded* and what must be *gated* are independent, and being below that floor never discharges an entry.

This stays prose rather than a guard, for two different reasons that should not be run together. Deciding whether a change was substantive is the judgment a check cannot make. The index half **is** mechanically checkable — and a guard on it would be worthless: it compares the cell against the line, so a missing entry and an `Accepted` cell agree, and the check returns clean on exactly the drifted tree this repairs. **If drift recurs now that the surface is named, that is the evidence a guard needs** — and it would have to read history, not the two surfaces against each other ([issue #18](https://github.com/Grimblaz-and-Friends/tradecraft/issues/18)).

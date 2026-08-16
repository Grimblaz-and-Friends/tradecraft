# The constitution

The small set of decisions everything else answers to. Each ADR carries its exhibits — the evidence it was learned from — so a future sweep can tell load-bearing from vestigial (per ADR-002, that applies to these documents too).

| ADR | Decision | Status |
| --- | --- | --- |
| [ADR-001](ADR-001-identity.md) | A practice, not an orchestrator; agents demoted to mechanism; persona *structure* ruled out, persona *framing* value left open | Accepted, amended |
| [ADR-002](ADR-002-material-lifecycle.md) | Three materials; promotion earned, demotion mandatory; **mechanisms enter by owner-admitted trial, marked and cut by default**; boundary formats skip the lifecycle | Accepted, amended |
| [ADR-003](ADR-003-cell-architecture.md) | Skills as self-contained cells; downward-only deps; one plugin bundle; five layers | Accepted |
| [ADR-004](ADR-004-two-zones.md) | Repo-only vs shipped zones, lint-enforced | Accepted |
| [ADR-005](ADR-005-interaction-charter.md) | Gate taxonomy; gate vs question; consent travels with the decision; two lanes | Accepted |
| [ADR-006](ADR-006-process-defaults.md) | Minimal lane default; review scaled by artifact weight (differentiated panel for substantial artifacts, seats recorded); position beats depth; **convergence gate before implementation, artifact on the work's issue**; filing is the exception; ledger from day one | Accepted, amended |
| [ADR-007](ADR-007-cross-runtime.md) | Runtime-neutral practice; GitHub as interchange; substrate: **Python** (ruled) | Accepted |
| [ADR-008](ADR-008-memory.md) | The repo is the memory; vendor stores are inboxes with same-session landing; the wipe test | Accepted |
| [ADR-009](ADR-009-predecessor-disposition.md) | Predecessor is reference material, not a source tree: nothing carries by default, pull-based rewrite, no presumption of correctness | Accepted |

## Open rulings and open questions

No rulings are pending from the owner. One evidence-driven question stays open inside its ADR: persona-framing value (ADR-001), decided per skill by ledger or eval evidence — no one needs to decide it now.

2026-08-15: a full-repo adversarial review (5 prosecutors, defense, judge) sustained 35 findings against the constitution, lint, and seed skill. The practice has since reviewed itself again, each review's sustained findings carried with its seat attribution in [../../ledger.jsonl](../../ledger.jsonl) and transcribed-claim provenance in [../evidence.md](../evidence.md).

## Amending

An ADR changes by commit like anything else, but the change must name the evidence that motivated it, and any lint rule enforcing the old text changes in the same commit (ADR-004).

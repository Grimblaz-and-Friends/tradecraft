# The constitution

The small set of decisions everything else answers to. Each ADR carries its exhibits — the evidence it was learned from — so a future sweep can tell load-bearing from vestigial (per ADR-002, that applies to these documents too).

| ADR | Decision | Status |
| --- | --- | --- |
| [ADR-001](ADR-001-identity.md) | A practice, not an orchestrator; agents demoted to mechanism | Accepted |
| [ADR-002](ADR-002-material-lifecycle.md) | Three materials; promotion earned, demotion mandatory; boundary formats skip the lifecycle | Accepted |
| [ADR-003](ADR-003-cell-architecture.md) | Skills as self-contained cells; downward-only deps; one plugin bundle; five layers | Accepted |
| [ADR-004](ADR-004-two-zones.md) | Repo-only vs shipped zones, lint-enforced | Accepted |
| [ADR-005](ADR-005-interaction-charter.md) | Gate taxonomy; gate vs question; consent travels with the decision; two lanes | Accepted |
| [ADR-006](ADR-006-process-defaults.md) | Minimal lane default; filing is the exception; ledger from day one | Accepted |
| [ADR-007](ADR-007-cross-runtime.md) | Runtime-neutral practice; GitHub as interchange; substrate **proposed: Python** | Accepted / substrate proposed |

## Open rulings

1. **Substrate** (ADR-007): Python proposed; TypeScript the considered alternative.
2. **Port vs rewrite**: what, if anything, carries over from the predecessor repo. Proposed: treat it purely as an evidence base — port lessons and tests, rewrite prose at frontier-model weight. Becomes ADR-008 when ruled.

## Amending

An ADR changes by commit like anything else, but the change must name the evidence that motivated it, and any lint rule enforcing the old text changes in the same commit (ADR-004).

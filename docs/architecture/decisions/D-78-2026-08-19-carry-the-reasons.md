# D-78: Carry the reasons

**Status:** Accepted 2026-08-19 (PR #78)

## Context

The reset (D-74) carried rules into the new doctrine and skills while their reasons stayed behind in the frozen archive — the same stranding the D-53 migration produced, measured by the #68 session at roughly 259 reason-grade clauses across the nine ADRs with about 30 resident only in the preamble. The `authoring` skill shipped by the reset states the opposing standard ("state the rule with its reason"), so the new regime failed its own rule on the day it landed. The strongest instance was a latent correctness defect: the doctrine's zone wall never said that `docs/` still reaches a consumer's plugin cache (the plugin's source is the repo root), so a session could put content there believing consumers never receive it. Raised on [#73](https://github.com/Grimblaz-and-Friends/tradecraft/issues/73), verified and filed as [#75](https://github.com/Grimblaz-and-Friends/tradecraft/issues/75), affirmed 2026-08-19.

## Decision

Four reasons are restored to the rules they govern, each sourced from its frozen home: the zone wall's depend-not-receive clause (ADR-004), the one-substrate consequences (ADR-007), the lens-vs-vantage distinction (the pre-reset review skill, via ADR-006's J1 ruling), and the instrument-expressiveness test (ADR-002/ADR-006) at the review-index contract. Restored reasons explain; they change no rule's requirement.

**One new rule is admitted** to the `authoring` skill: when rules move between documents, their reasons move with them, or the change states — where amendments are recorded — that reasons are being dropped, and why. Its companion clause carries the home test from ADR-008: knowledge compounds in the artifact that uses it, not beside it, which is the test any proposed new home must pass. This is the durable fix; it is what makes the next migration carry its reasons or say it did not, rather than strand them silently.

Two owner-directed amendments ride in the same PR, recorded in its body: the review's finding-validity bar and authoring's instruction test key to the audience the artifact's purpose statement names — no fixed persona — and every review dispatch carries the artifact's purpose statement verbatim or by link, never the dispatcher's paraphrase (incident: this PR's own panel judged a compressed charter and filed false findings against affirmed content).

## Rejected

- **A general sweep of the archive's remaining reason-grade clauses**: the accretion road; the migration rule makes it unnecessary going forward, and further restorations wait for a demonstrated live failure like the zone wall's.
- **Restoring reasons by citation into the archive** rather than restatement: a rule whose reason lives behind a link a mid-task reader will not follow is a rule without its reason.

## Evidence

[#75](https://github.com/Grimblaz-and-Friends/tradecraft/issues/75) (the verified claims and the affirmed artifact), [#73's discovery comment](https://github.com/Grimblaz-and-Friends/tradecraft/issues/73), the PR #78 review record (its panel found the one authored fragment that exceeded the affirmation, and its charter-compression incident is the dispatch rule's exhibit).

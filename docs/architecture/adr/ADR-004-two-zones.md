# ADR-004: Two zones — repo-local rules vs shipped standards

**Status:** Accepted 2026-08-15

## Context

The predecessor mixed its own governance (architecture docs, CI gates, contributor rules) with what it shipped downstream, then audited the boundary by hand, late, as a catalog document. Consumers of a plugin should get a zero-config, self-complete experience; contributors need rules consumers must never see or depend on.

## Decision

Two zones, with a mechanical wall between them:

- **Repo-only zone**: `docs/`, CI workflows and their scripts, contributor rules, this constitution. Excluded from plugin packaging. May reference anything.
- **Shipped zone**: `skills/`, the core library, composition-layer commands and shells, the plugin manifest. **Nothing in the shipped zone may reference the repo-only zone** — not a path, not a doc link, not a "see CONTRIBUTING" aside.

The wall is enforced by the **packaging lint** from the skeleton commit onward, failing the build on: shipped→repo-only references, sideways skill dependencies (ADR-003), and root-doctrine size over budget. The consumer experience is checked on every commit, not audited after the fact.

**Standards placement follows the zone rule:** a standard that downstream work must follow lives *in the skill that teaches it* (shipped). A rule about how *this repo* is built lives in the repo-only zone. When one idea needs both, the skill carries the standard and the repo doc carries only the local application — never the reverse, and never duplicated prose that can drift.

## Consequences

- "Will the plugin experience be optimal?" stops being a review question and becomes a build failure.
- Contributor docs can be as heavy as they need to be without taxing consumers.
- The lint is the constitution's enforcement arm; when an ADR here changes, the lint changes in the same commit.

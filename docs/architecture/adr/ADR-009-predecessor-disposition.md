# ADR-009: The predecessor is reference material, not a source tree

**Status:** Accepted 2026-08-15

## Context

The predecessor ([agent-orchestra](https://github.com/Grimblaz/agent-orchestra), 2025-12 → 2026-08) contains ~60 skills, a large script library with tests, and eight months of recorded lessons. The question was what carries into tradecraft. Three options were weighed: bulk port (fails the constitution on contact — sideways references, doctrine volume, prose-embedded formats, a rejected substrate), bulk rewrite up front (a speculative migration project, and the predecessor's own strongest evidence warns against it: the last time its repo-specific guidance was generalized for carry-over, all 15 of 15 sustained review findings were in the newly generalized prose — rewriting is precisely where claims outrun evidence), and pull-based rewrite.

The owner's ruling went a step past the recommendation, and this ADR records that stance: **tradecraft is a new project, not a continuation.** The predecessor is studied the way a post-mortem studies a system — its failures are as instructive as its successes, and starting over completely was chosen *because* many of its choices did not hold.

## Decision

1. **Nothing carries by default.** No file, skill, prose, or code is ported. A capability exists in tradecraft only when real work pulls it into existence.
2. **Pull-based rewrite.** When work needs something the predecessor addressed, the skill is authored fresh at frontier weight, with the predecessor open beside it as reference: its exhibits supply the *why*, its test cases supply the behavioral spec (re-expressed in Python), its design docs supply the rejected alternatives. Each pull is small, immediately exercised by the work that pulled it, and reviewed where the evidence says defects concentrate — the new prose.
3. **No presumption of correctness.** The predecessor's way of doing something is a data point, never a default. Every pull extracts the *lesson*, not the artifact, and asks explicitly: did this actually work there, and is the evidence for that success discriminating — or was it merely never falsified? Its failures are first-class evidence with equal standing, and many of this constitution's rules are distilled from them.
4. **Citations over copies.** The predecessor is public; lessons are cited by link (issue, design doc, commit), not transcribed. Copied text drifts; a citation stays attached to its evidence.
5. **Predecessor disposition.** agent-orchestra becomes the evidence base: public, citable, frozen for new practice-level work once tradecraft's skeleton and seed skill exist, remaining in daily service only until tradecraft covers the minimal lane end to end. No forced cutover date — tradecraft grows exactly as fast as real work migrates. The one standing discipline: when work encounters something the predecessor solved, the move is to pull it into tradecraft properly, not to keep doing it in the predecessor because the skill already exists there.

## Consequences

- Tradecraft's size tracks real demand; nothing exists that work didn't summon.
- The migration risk surface (newly written prose) arrives in reviewable, immediately-exercised increments instead of one bulk exposure.
- The predecessor's eight months keep paying rent as evidence without any of its weight, habits, or unexamined defaults coming along.

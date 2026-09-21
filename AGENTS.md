# tradecraft — repository doctrine

**Purpose:** the few repository-specific rules that must bind before any practice component loads. **Audience:** every session in this repository, every runtime. **Success:** a session reads the shipped charter first, respects the repository boundary, and admits only work that serves the products this practice exists to improve.

@skills/charter/SKILL.md

**Read `skills/charter/SKILL.md` now, before acting.** It is the binding charter this repository ships, and these repository-specific rules govern where they differ.

## Worth doing

When whether work is worth doing outruns the available evidence, argue it against `docs/values.md` by number; only the owner amends that ranking. Do not admit work whose subject is this practice itself unless it names the product harm it answers under `.tradecraft/work.json`, because the practice is a means to better product work rather than its own product.

## The one-way wall

Shipped (`skills/`, `lib/`, `commands/`, `agents/`, `hooks/`, `.claude-plugin/`) never references repo-only (`docs/`, `tools/`, `.github/`), and the wall runs one way: repo-only material may reference shipped material, but shipped material must stand on its own for an adopter.

The Steward is this repository's long-lived session for coordinating the lab and holds no change; before starting work or sending it evidence, read `docs/cells/steward/SKILL.md` so the lab's state and every change remain in distinct hands.

## Code Review Rules

Review pull requests only when they are marked ready; skip drafts. Post only P0/P1 findings a consumer would act on wrongly. Name the wrong action, not the wording. Where this repository's own convention contradicts a general rule, the convention wins and the comment says so. A deletion is as good a finding as an addition.

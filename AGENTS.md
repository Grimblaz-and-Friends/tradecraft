# tradecraft — doctrine (this repository's mechanics)

**Purpose:** what must bind in this repository before any cell fires, and where the rest of its mechanics live. **Audience:** every session in this repository, every runtime. **Success:** a competent session reading this file and the charter it names passes the gates correctly and reaches the cell holding whatever else it needs.

@skills/charter/SKILL.md

**Read `skills/charter/SKILL.md` now, before acting** — the line above imports it where the runtime supports imports, and Codex has none, so the instruction is what carries it there. It carries the binding half of this practice — authority and which decisions are the owner's, the two ceremony moments, review, and where content goes — and it is what this repository ships to anyone who adopts the practice. This file adds only what is specific to here. Where the two touch, the charter states the rule and this file states how it is done in this repository.

## The ceremony moments, here

- **Convergence.** The brief is posted as a comment on the work's issue (file one if none exists) and the affirmation recorded on the issue naming that comment; the artifact reading it is posted once settled, before the first commit; from there the owner is next needed at PR review. Mechanical work — a typo, a dependency bump, an append to a record — proceeds straight to a PR.
- **Release.** `ci.yml` flags any PR touching this file, `CLAUDE.md`, the `charter` cell, or a repo-only cell for the owner's specific review. [D-81]

## The wall, before anything is edited

**Shipped (`skills/`, `lib/`, `commands/`, `agents/`, `hooks/`, `.claude-plugin/`) never references repo-only (`docs/`, `tools/`, `.github/`), and the wall runs one way** — repo-only code and prose may reference shipped, which is how every tool here reaches `lib/` and how a repo-only cell names the cell owning a standard it applies. This is here rather than behind a pointer because a session can breach it in its first edit, before any cell fires.

## The rest of this repository's mechanics

Three repo-only cells carry them, loaded on demand in both runtimes and never shipped to an adopter: the `landing` cell for taking a change from a branch to a pull request, the `records` cell for this repository's append-only records and decision log, and the `siting` cell for where content goes here and what this tree assumes.

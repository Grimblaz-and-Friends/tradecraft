# tradecraft — doctrine (this repository's mechanics)

**Purpose:** what must bind in this repository before any cell fires, and where the rest of its mechanics live. **Audience:** every session in this repository, every runtime. **Success:** a competent session reading this file and the charter it names passes the gates correctly and reaches the cell holding whatever else it needs.

@skills/charter/SKILL.md

**Read `skills/charter/SKILL.md` now, before acting** — the line above imports it where the runtime supports imports, and Codex has none, so the instruction is what carries it there. It carries the binding half of this practice — authority and which decisions are the owner's, the two ceremony moments, review, and where content goes — and it is what this repository ships to anyone who adopts the practice. This file adds only what must bind before a cell fires; the cells below carry the rest, and where this file and the charter touch, the charter states the rule.

## Worth doing

**When the worth-it question outruns the evidence, argue it against `docs/values.md`, by number** — the ranking of what this practice values, the owner's alone to amend. It is here rather than in a cell because a session deciding whether work is worth doing has, at that moment, loaded nothing. [D-225]

## The ceremony moments, here

- **Convergence.** The brief is posted as a comment on the work's issue (file one if none exists) and the affirmation recorded on the issue naming that comment; the artifact reading it is posted once settled, before the first commit. Mechanical work — a typo, a dependency bump, an append to a record — proceeds straight to a PR.
- **Release.** `ci.yml` flags any PR touching this file, `CLAUDE.md`, the `charter` cell, or a repo-only cell for the owner's specific review. [D-81]

## The wall, before anything is edited

**Shipped (`skills/`, `lib/`, `commands/`, `agents/`, `hooks/`, `.claude-plugin/`) never references repo-only (`docs/`, `tools/`, `.github/`), and the wall runs one way** — repo-only code and prose may reference shipped, which is how every tool here reaches `lib/` and how a repo-only cell names the cell owning a standard it applies. This is here rather than behind a pointer because a session can breach it in its first edit, before any cell fires.

## What this tree does that will look like a defect

**CRLF on disk here is expected, not a defect** — a text-mode write produces it, `.gitattributes` normalises it in, and the committed bytes are unaffected. The symptom is ` M` from `git status` against an empty diff; notice it and move on. It is here rather than in a cell because the moment it must be found is mid-task, when a session notices CRLF and has no reason to go looking. [D-186]

## The rest of this repository's mechanics

Repo-only cells under `docs/cells/` carry them, loaded on demand in both runtimes and never loaded by an adopter: `board`, `landing`, `records`, `siting`. Every cell's own description loads in every session here and states what it covers, so the names route on their own. [D-327]

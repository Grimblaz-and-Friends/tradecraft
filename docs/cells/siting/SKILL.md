---
name: siting
description: Where a piece of content goes in this repository and what the local tree assumes — the routing map for a rule, a binding document or review evidence; the two zones and the one-way wall between them; and the substrate, line endings and canonical doctrine file every script and edit here can rely on. Use when deciding where something belongs in this repository, when editing an always-on surface, or when writing or moving a script, guard or document here; not for the practice's general authoring and code standards, which the cells teaching them carry, and not for the landing procedure.
---

# siting

**Purpose:** carry where content goes in this repository and what its tree assumes, so a session siting a rule, a document or a script puts it in the home this repository actually has. **Audience:** any session here deciding where something belongs, editing an always-on surface, or writing code against this tree. **Success:** a session that has read this can place any piece of content without defaulting it to the always-on surface, and writes code that survives both platforms this repository is tested on.

## Content routing, here

The charter carries the routing map. Specific to here:

- **Cell structure is the `authoring` cell's standard**, whose checkable subset the lint enforces here. Shared code lives only in `lib/`.
- **A binding rule the practice exports** → the `charter` cell, within its own job. **A rule or mechanic only this repository needs** → a repo-only cell under `docs/cells/`, whose description loads and whose body does not; the always-on doctrine carries only what must bind before any cell fires. [D-291]
- **A binding document under `docs/`** → a file there, and a line in the doctrine that binds rather than names it; `docs/values.md` is the shape. [D-225]
- **Review evidence** → the review report on the PR, plus its row in `docs/reviews.jsonl`; a decision entry lives at the path and under the freeze this repository's records material gives.

The charter states the admission order. **Every edit of an always-on surface owes an outflow**, at the budget or nowhere near it — the budget being the whole surface each runtime loads, which `python tools/lint.py` prices as it runs and `python tools/figures.py` reports — the `authoring` cell carries the three moves, the evidence-gated fourth, and what they may not do. [D-184]


## Structure and substrate

- **The two zones.** Shipped (`skills/`, `lib/`, `commands/`, `agents/`, `hooks/`, `.claude-plugin/`) never references repo-only (`docs/`, `tools/`, `.github/`) — not a path, not a doc link, and not a cell reference naming a repo-only cell; the lint enforces the checkable subset. Consumers must never *depend* on repo-only, which is not the same as never receiving it: the plugin's source is the repo root, so a git-source install clones everything and those files do reach a consumer's cache as inert content. General standards ship in the skill that teaches them, or in the `charter` cell where they must bind before any skill fires; repo-specific application lives in a repo-only cell. **Capability wrappers do not belong in any of them.**
- **The calling-contract rule is the `substrate` cell's**, whose checkable subset the lint and `tools/tests/test_portability.py` hold; why a token-bearing contract is dead in one runtime is [D-156].
- **Substrate here is Python**, tested on Linux and Windows in CI — one CI matrix, and one thing every new script can assume. PowerShell is rejected for new code. `AGENTS.md` is canonical because Codex reads it natively; `CLAUDE.md` is a pointer to it, never a fork.
- **The predecessor** ([agent-orchestra](https://github.com/Grimblaz/agent-orchestra)) is reference material with no presumption of correctness: pull lessons, never artifacts.
- **Vendor memory is an inbox, never an archive.** A lesson lands same-session in its home from the routing map above.

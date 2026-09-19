---
name: siting
description: Where a piece of content goes in this repository and what the local tree assumes — the homes for local rules, documents and review evidence; the two zones and the one-way wall between them; and the substrate and canonical doctrine file every script and edit here can rely on. Use when deciding where something belongs in this repository or when writing or moving a script, guard or document here; not for the practice's general authoring and code standards, which the cells teaching them carry, and not for the landing procedure.
---

# siting

**Purpose:** carry where content goes in this repository and what its tree assumes, so a session siting a rule, a document or a script puts it in the home this repository actually has. **Audience:** any session here deciding where something belongs, editing an always-on surface, or writing code against this tree. **Success:** a session that has read this can place any piece of content without defaulting it to the always-on surface, and writes code that survives both platforms this repository is tested on.

## Content routing, here

The `authoring` cell carries the general routing standard. Specific to here:

- **Cell structure is the `authoring` cell's standard**, whose checkable subset the lint enforces here. Shared code lives only in `lib/`.
- **A binding rule the practice exports** → the cell that owns the standard; the charter carries a rule itself only when it must bind before any other cell fires. **A rule or mechanic only this repository needs** → a repo-only cell under `docs/cells/`, whose description routes the session and whose body loads on demand.
- **A binding document under `docs/`** → a file there, and a line in the doctrine that binds rather than merely names it; `docs/values.md` is the shape.
- **Review evidence** → the review report on the PR; a decision entry lives at the path and under the freeze this repository's records material gives.


## Structure and substrate

- **The two zones.** Shipped (`skills/`, `lib/`, `commands/`, `agents/`, `hooks/`, `.claude-plugin/`) never references repo-only (`docs/`, `tools/`, `.github/`) — not a path, not a doc link, and not a cell reference naming a repo-only cell; the lint enforces the checkable subset. Consumers must never *depend* on repo-only, which is not the same as never receiving it: the plugin's source is the repo root, so a git-source install clones everything and those files do reach a consumer's cache as inert content. General standards ship in the skill that teaches them, or in the `charter` cell where they must bind before any skill fires; repo-specific application lives in a repo-only cell. **Capability wrappers do not belong in any of them.**
- **The calling-contract rule is the `substrate` cell's**, whose checkable subset `tools/substrate_lint.py`, the repository lint and their tests hold.
- **This repository runs the substrate guards through `python tools/lint.py`**; it imports the same repo-only predicates and supplies the live contract population, so one definition governs direct and integrated runs.
- **Substrate here is Python**, tested on Linux and Windows in CI — one CI matrix, and one thing every new script can assume. PowerShell is rejected for new code. `AGENTS.md` is canonical because Codex reads it natively; `CLAUDE.md` is a pointer to it, never a fork.
- **The predecessor** ([agent-orchestra](https://github.com/Grimblaz/agent-orchestra)) is reference material with no presumption of correctness: pull lessons, never artifacts.
- **Vendor memory is an inbox, never an archive.** A lesson lands same-session in its home from the routing map above.

# tradecraft — root instructions (canonical for all runtimes)

This repo is governed by its constitution: [docs/architecture/adr/README.md](docs/architecture/adr/README.md). Read the index before structural work; the ADRs override habit and this file stays within a lint-enforced size budget — durable guidance belongs in the skill it governs, not here.

Always-on rules:

- **Skills are self-contained cells.** No skill requires another skill; shared code lives only in `lib/`. Depth goes in the skill's own `references/`, loaded on demand. (ADR-003)
- **Two zones.** Nothing in the shipped zone (`skills/`, `lib/`, `commands/`, `agents/`, `.claude-plugin/`) may reference `docs/`, `tools/`, or `.github/`. (ADR-004)
- **Rules are earned.** New rules start as model judgment; prose is promoted by incident, code by recurrence + stability. Boundary formats (GitHub markers, ledger rows, version stamps) are the one day-one-code exception. (ADR-002)
- **Findings: fix now or drop with a one-line reason.** Filing an issue requires rejecting both the fix-here home and the guard home, and passing the pickup test. (ADR-006)
- **Lessons land same-session** in their repo home (skill prose, guard, or ADR). Vendor memory is an inbox, never an archive. (ADR-008)
- **The predecessor** ([agent-orchestra](https://github.com/Grimblaz/agent-orchestra)) **is reference material with no presumption of correctness.** Pull lessons, never artifacts. (ADR-009)
- **Substrate is Python**, stdlib-first, tested on Linux and Windows. (ADR-007)
- **Before committing:** branch first — `main` refuses direct pushes, so work lands on its own branch and reaches `main` through a PR whose CI checks must pass — then `python tools/lint.py`. Merging is the human's release gate (ADR-005), never the agent's.

`CLAUDE.md` is a pointer to this file and must never fork from it.

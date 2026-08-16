# tradecraft — root instructions (canonical for all runtimes)

This repo is governed by its constitution: [docs/architecture/adr/README.md](docs/architecture/adr/README.md). Read the index before structural work; the ADRs override habit and this file stays within a lint-enforced size budget — durable guidance belongs in the skill it governs, not here.

Always-on rules:

- **Skills are self-contained cells.** No skill requires another skill; shared code lives only in `lib/`. Depth goes in the skill's own `references/`, loaded on demand. (ADR-003)
- **Two zones.** Nothing in the shipped zone (`skills/`, `lib/`, `commands/`, `agents/`, `.claude-plugin/`) may reference `docs/`, `tools/`, or `.github/`. (ADR-004)
- **Rules are earned.** New *rules* start as model judgment; prose is promoted by incident, code by recurrence + stability. A **mechanism** has no judgment-tier form (a gate procedure, a skill, a script, a field, a format), so it takes the other road: the owner admits it as a **marked trial** that states its falsifier and review trigger up front, produces ledger rows, and is **cut by default** at that trigger — doing nothing removes it. Boundary formats (GitHub markers, ledger rows, version stamps) are the one day-one-code exception. (ADR-002)
- **Findings: fix now or drop with a one-line reason.** Filing an issue requires rejecting both the fix-here home and the guard home, and passing the pickup test. (ADR-006)
- **Lessons land same-session** in their repo home (skill prose, guard, or ADR). Vendor memory is an inbox, never an archive. (ADR-008)
- **The predecessor** ([agent-orchestra](https://github.com/Grimblaz/agent-orchestra)) **is reference material with no presumption of correctness.** Pull lessons, never artifacts. (ADR-009)
- **Substrate is Python**, stdlib-first, tested on Linux and Windows. (ADR-007)
- **Before implementing** anything above the trivial floor: write the pre-implementation artifact as a comment on the work's issue — filing one if none exists — weighted to acceptance criteria and a boundary statement. Its review is the convergence gate and it asks. The owner affirms in conversation; you then record that on the issue, naming the artifact comment, **before the first commit**. (ADR-006 §2)
- **Before committing:** branch first — `main` refuses direct pushes, so work lands on its own branch and reaches `main` through a PR whose CI checks must pass — then `python tools/lint.py` and `python tools/check_version_bump.py` — the second exists to answer before the commit, and had no caller telling anyone to run it. Merging is the human's release gate (ADR-005), never the agent's.
- **Then, without being asked: publish the branch, open the PR, run the review, reconcile the external comments** — in that order, so automated reviewers run concurrently with it. On a change that has a PR, running the review is a check, never a question; handing it back for the human to run invents a gate the charter does not have. Upstream artifacts (framing, design, plan) are different — their review *is* the convergence gate, and that one asks. (ADR-006 §3)
- **The PR body says what it closes** — `Closes #N`, or one line saying it closes none and why; silence and a deliberate no are otherwise the same string. (ADR-006 §3)

`CLAUDE.md` is a pointer to this file and must never fork from it.

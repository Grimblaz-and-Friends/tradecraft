# tradecraft — doctrine (this repository's mechanics)

**Purpose:** this repository's own mechanics, on top of the practice's binding rules. **Audience:** every session in this repository, every runtime. **Success:** a competent session reading this file and the charter it names behaves correctly at the gates and routes content to its right home.

**Read `charter/CHARTER.md` now, before acting.** It carries the binding half of this practice — authority and which decisions are the owner's, the two ceremony moments, review, and where content goes — and it is what this repository ships to anyone who adopts the practice. This file adds only what is specific to here. Where the two touch, the charter states the rule and this file states how it is done in this repository.

## The ceremony moments, here

- **Convergence.** The settled pre-implementation artifact is posted as a comment on its issue (file one if none exists). The session records the affirmation on the issue, naming that comment, before the first commit; from there the owner is next needed at PR review. Mechanical work — a typo, a dependency bump, an append to a record — proceeds straight to a PR; when in doubt, ask the cheap question.
- **Release.** `ci.yml` labels and comments on any PR touching this file, `CLAUDE.md`, or `charter/CHARTER.md`, flagging it for the owner's specific review — not `CODEOWNERS`, which cannot reach a PR's own author, today always him. [D-81]

## The flow

Branch first (`main` refuses direct pushes) → build → `python tools/lint.py` and `python tools/check_version_bump.py` → commit → publish the branch, open the PR, run the experience session the change bought or record the one line declining it, run the review, reconcile external reviewer comments — in that order, without being asked; on a change that has a PR, running the review is a check, never a question. The PR body states `Closes #N`, or one line saying it closes none and why. A shipped-zone change bumps the plugin version (the unit is the PR against its merge base).

## Review, here

The review report states what it judged against, and every review appends one row to `docs/reviews.jsonl`.

## Content routing, here

The charter carries the routing map. Specific to here:

- **Skills are self-contained cells:** no skill references another, shared code lives only in `lib/`, depth loads on demand from the skill's own `references/`.
- **A binding rule the practice exports** → `charter/CHARTER.md`, within its own job. **A rule or mechanic only this repository needs** → this file, within its budget.
- **Review evidence** → the review report on the PR, plus its row in `docs/reviews.jsonl`; a decision entry lives at the path under Decisions below.

The charter states the admission order; this file's budget is what makes it bite here. At the budget, adding a line means routing something out.

## Decisions

`docs/architecture/decisions/D-<PR#>-YYYY-MM-DD-<slug>.md`, written in the PR that lands a choice a future session would otherwise re-derive or unknowingly undo; frozen on landing but for a reference whose target moved, bounded in the log's README. A rule or skill line may cite its decision (`[D-N]`).

## Records are exhaust

Records are append-only and never maintained: no backfilling, no reconciling, no re-dispositioning, ever. A PR whose only content is record bookkeeping is the tripwire: delete the record it books. `docs/ledger.jsonl`, `docs/seat-record.jsonl`, and the pre-reset constitution under `docs/architecture/` (statute, ADRs, evidence registry) are a frozen archive — readable history, never binding. [D-74]

## Structure and substrate

- **Two zones.** Shipped (`skills/`, `lib/`, `commands/`, `agents/`, `charter/`, `hooks/`, `.claude-plugin/`) never references repo-only (`docs/`, `tools/`, `.github/`) — not a path, not a doc link; the lint enforces the checkable subset. Consumers must never *depend* on repo-only, which is not the same as never receiving it: the plugin's source is the repo root, so a git-source install clones everything and those files do reach a consumer's cache as inert content. General standards ship in the skill that teaches them; repo-specific application lives here.
- **A shipped calling contract names no harness token.** A script is invoked by a path resolved against the directory of the file that names it, so the same line works in the source repository and in an installed plugin; the lint enforces it. `${CLAUDE_PLUGIN_ROOT}` expands only in hook, monitor, and MCP configuration — never in a session's shell.
- **Substrate is Python**, stdlib-first, tested on Linux and Windows in CI — one substrate means one set of idioms to harden, one CI matrix, and one thing every new script can assume, which is what refuses a second language for a single helper. PowerShell is rejected for new code. `AGENTS.md` is canonical because Codex reads it natively; `CLAUDE.md` is a pointer to it, never a fork.
- **The predecessor** ([agent-orchestra](https://github.com/Grimblaz/agent-orchestra)) is reference material with no presumption of correctness: pull lessons, never artifacts.
- **Vendor memory is an inbox, never an archive.** A lesson lands same-session in its home from the routing table above.

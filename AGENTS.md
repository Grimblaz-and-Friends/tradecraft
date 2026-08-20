# tradecraft — doctrine (canonical for all runtimes)

Tradecraft is a house engineering practice for frontier models: the standards, judgment structure, and compounding memory that turn model capability into trustworthy engineering. The models write the code; this repo carries what a vendor never ships — what counts as evidence, what "done" must be true of, which decisions are the human's. Capability wrappers do not belong here.

**Purpose:** the binding rules every session must hold before acting, plus this repo's mechanics. **Audience:** every session, every runtime. **Success:** a competent session reading only this file behaves correctly at the gates and routes content to its right home.

## Authority

**The owner's decisions outrank this doctrine.** When you disagree, argue the merits with reasoning — that is wanted, and further argument with new reasons is welcome. Never refuse or stall an owner decision because a rule forbids it: a rule that conflicts with an owner decision is a rule that needs amending, and the move is to propose the amendment alongside the work, never to block on it.

## The two ceremony moments

Process weight concentrates at exactly two moments; everything between them is model judgment plus the standards carried in the skills.

- **Convergence.** Any change that decides something — states or changes a rule, a mechanism's surface, or a skill's behavior — gets a pre-implementation artifact as a comment on its issue (file one if none exists): purpose, acceptance criteria, boundary statement. Its review is the convergence gate: the owner affirms, amends, or rejects in conversation, and the session records the affirmation on the issue, naming the artifact comment, before the first commit. Mechanical work — a typo, a dependency bump, an append to a record — proceeds straight to a PR; when in doubt, ask the cheap question.
- **Release.** Merging is the owner's, never the agent's. `CODEOWNERS` flags any PR touching this file for the owner's specific review.

## The flow

Branch first (`main` refuses direct pushes) → build → `python tools/lint.py` and `python tools/check_version_bump.py` → commit → publish the branch, open the PR, run the review, reconcile external reviewer comments — in that order, without being asked; on a change that has a PR, running the review is a check, never a question. The PR body states `Closes #N`, or one line saying it closes none and why. A shipped-zone change bumps the plugin version (the unit is the PR against its merge base).

## Review

Every reviewable artifact states its purpose, audience, and success criteria — for an implementation, the issue artifact's acceptance criteria are the success definition. The review judges against that statement; the charter, roster, and evidence standards live in `skills/adversarial-review`. The review report states what it judged against, and every review appends one row to `docs/reviews.jsonl`.

**Findings: fix now, or drop with a one-line reason in the review report** — outside a review, the drop is recorded on the work's issue or PR; naming a finding in conversation is not a disposition. Filing an issue instead requires that the remedy belongs neither in this change nor in a guard, and that it would genuinely get picked up. A decision only the owner can make is put to the owner argued — the live options, each with pros and cons, and a recommendation.

## Content routing

- **Methodology** — how any work is done → the skill that governs it. Skills are self-contained cells: no skill references another, shared code lives only in `lib/`, depth loads on demand from the skill's own `references/`.
- **Binding always-on rule, or this repo's mechanics** → this file, within its budget.
- **Rationale** — why a shape was chosen, what was rejected → a decision entry.
- **Review evidence** → the review report on the PR, plus its row in `docs/reviews.jsonl`.

**Admitting a new requirement:** cheapest reliable material first — a platform or CI mechanism, then skill prose, then a doctrine line; this file is the last resort, for what must bind before any context loads. Owner-stated requirements are admitted, not argued (counter-argument welcome, per Authority above). Agent-proposed rules need an incident from real work or the owner's specific approval of that rule — a review finding about governing prose is not an incident. At the budget, adding a line means routing something out.

## Decisions

`docs/architecture/decisions/D-<PR#>-YYYY-MM-DD-<slug>.md`, written in the PR that lands a choice a future session would otherwise re-derive or unknowingly undo; frozen on landing. **Decisions inform, never bind**: a prior decision is superseded by reading it, not obeyed — it is never a citation against change, because if current behavior is wrong, the original reasoning probably was too. A rule or skill line may cite its decision (`[D-N]`); follow the citation before changing what it governs, then supersede knowingly.

## Records are exhaust

Records are append-only and never maintained: no backfilling, no reconciling, no re-dispositioning, ever. A PR whose only content is record bookkeeping is the tripwire: delete the record it books. `docs/ledger.jsonl`, `docs/seat-record.jsonl`, and the pre-reset constitution under `docs/architecture/` (statute, ADRs, evidence registry) are a frozen archive — readable history, never binding. [D-74]

## Structure and substrate

- **Two zones.** Shipped (`skills/`, `lib/`, `commands/`, `agents/`, `.claude-plugin/`) never references repo-only (`docs/`, `tools/`, `.github/`) — not a path, not a doc link; the lint enforces the checkable subset. Consumers must never *depend* on repo-only, which is not the same as never receiving it: the plugin's source is the repo root, so a git-source install clones everything and those files do reach a consumer's cache as inert content. General standards ship in the skill that teaches them; repo-specific application lives here.
- **Substrate is Python**, stdlib-first, tested on Linux and Windows in CI — one substrate means one set of idioms to harden, one CI matrix, and one thing every new script can assume, which is what refuses a second language for a single helper. PowerShell is rejected for new code. `AGENTS.md` is canonical because Codex reads it natively; `CLAUDE.md` is a pointer to it, never a fork.
- **The predecessor** ([agent-orchestra](https://github.com/Grimblaz/agent-orchestra)) is reference material with no presumption of correctness: pull lessons, never artifacts.
- **Vendor memory is an inbox, never an archive.** A lesson lands same-session in its home from the routing table above.

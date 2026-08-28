# D-222: Codex uses the shared plugin, a per-OS hook arm, and an explicit native launch contract

**Status:** Accepted 2026-08-27 (PR #222)

## Context

[ADR-007](../adr/ADR-007-cross-runtime.md) deliberately left a true Codex check unborn until real Codex work arrived. [Issue #24](https://github.com/Grimblaz-and-Friends/tradecraft/issues/24) is that arrival: implementation, probes, publication and review run in Codex on Windows against one affirmed compatibility artifact. The starting tree already installed in Codex from the existing Claude plugin manifests and exposed all nine skill descriptions without truncation. The gap was narrower than the old architecture forecast but had two parts: the default SessionStart command contains a Claude placeholder that Windows Codex cannot expand, and Codex CLI `0.150.0-alpha.8` logged a repaired plugin hook starting and completing while failing to add its documented plain stdout to model context.

## Decision

**There is no `.codex-plugin` adapter.** Codex consumes `.claude-plugin/marketplace.json`, `.claude-plugin/plugin.json`, `skills/`, and `hooks/hooks.json` directly. A second manifest would duplicate discovery and version state without adapting anything. The marketplace source stays the exact relative string `"./"`, which Codex discovery requires and `tools/lint.py` now pins.

**Hook portability is two command fields and two output forms over one emitter and one charter.** The default `command` remains Claude Code's `${CLAUDE_PLUGIN_ROOT}` form. `commandWindows` is the Codex Windows arm and uses `%PLUGIN_ROOT%`; both invoke `hooks/emit_charter.py`. Claude Code receives the frontmatterless charter as plain stdout. Codex's documented plugin-specific `PLUGIN_ROOT` variable selects its documented `hookSpecificOutput.additionalContext` JSON envelope, whose isolated spike reached model context where plain output did not. The hook's context limit exceeds the charter's enforced size budget. The portability suite executes the runtime forms from an installed-looking path and compares the context each carries to the same charter. Codex hook trust remains an adopter action: installation does not prove activation, so the documented path is to inspect and trust the hook through `/hooks`, then prove a fresh SessionStart event.

**The Codex review adapter is the native launch contract, not a shipped wrapper.** Every role launch explicitly names fresh-context inheritance, working root, sandbox or permission boundary, model and reasoning effort. Read-only roles use an ephemeral read-only session; a mutation role receives its own worktree and a write boundary confined there. The exact executable invocation is evidence in the review report and compatibility output, while the skill carries the runtime-neutral inputs. This keeps capability wrappers out of the practice and prevents a default model, inherited conversation, or authoring worktree from silently changing what a seat means.

**An external pass is outside the panel regardless of who invoked it.** Automated bot output and a self-invoked `codex review` did not receive the panel dispatch or seat contract. New review rows therefore carry top-level `external` raw and sustained counts, and `seats` contains only staffed roles. The 38 rows already present are immutable exhaust and remain grandfathered; every later row is checked in the new shape.

**The true Codex check is a real empty-consumer session with a defined failure.** `python tools/check_codex_compat.py` resolves an explicit binary, `PATH`, or the Windows app bundle; records the binary, CLI version, installed plugin version, model, reasoning effort and isolation settings; then launches a fresh empty directory. That directory has no repository `AGENTS.md`, so the exact sentinel is emitted only when the trusted hook supplied the charter and the installed catalog supplied all nine complete skill descriptions. Its preconditions are authentication, network access, the tree's plugin version installed and enabled, hook trust through `/hooks`, and a real Python interpreter.

## Rejected

- **A duplicated Codex manifest or copied skills.** The runtime already reads the shared package; duplication creates drift and no compatibility value.
- **A committed Codex review wrapper.** It would be a capability wrapper in the practice and freeze one runtime's CLI surface into shipped methodology. The explicit launch inputs and recorded invocation are sufficient.
- **A standing rule selecting Codex, a model, or a phase.** Runtime choice stays an implementation detail. This issue's seats use `gpt-5.6-sol` with high reasoning because the owner selected it for this run, not because every adopting repository inherits that setting.
- **Booking an external pass as a seat.** Invocation by the authoring session does not supply the cold boundary, shared block or lens contract that makes a panel seat evidence.

## Evidence

The affirmed artifact is [issue #24's convergence record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/24#issuecomment-5420394058). A cold Codex session on `gpt-5.6-sol` with high reasoning reproduced all nine full descriptions in the [skill-catalog probe](https://github.com/Grimblaz-and-Friends/tradecraft/issues/24#issuecomment-5446883255). The Windows command premise and successful `%PLUGIN_ROOT%` arm are recorded in the [hook spike](https://github.com/Grimblaz-and-Friends/tradecraft/issues/24#issuecomment-5446884633); the runtime-specific JSON output premise held in the [context-delivery spike](https://github.com/Grimblaz-and-Friends/tradecraft/issues/24#issuecomment-5448061498). The branch implementation and its final compatibility, experience and review evidence live on [PR #222](https://github.com/Grimblaz-and-Friends/tradecraft/pull/222).

# D-222: Codex shares the plugin, native repository adoption, and an explicit launch contract

**Status:** Accepted 2026-08-27 (PR #222)

## Context

[ADR-007](../adr/ADR-007-cross-runtime.md) deliberately left a true Codex check unborn until real Codex work arrived. [Issue #24](https://github.com/Grimblaz-and-Friends/tradecraft/issues/24) is that arrival: implementation, probes, publication and review run in Codex on Windows against one affirmed compatibility artifact. The starting tree already installed from the existing Claude plugin manifests and exposed all nine complete skill descriptions. Installation did not make the charter binding, and the attempted plugin lifecycle hook did not close that gap: direct execution worked, but neither plain nor JSON output from installed `SessionStart` and `UserPromptSubmit` hooks entered Codex model context.

Both runtimes already have a repository-instruction surface. Codex loads `AGENTS.md`; Claude Code can import that same file from `CLAUDE.md`. The compatibility problem is therefore adoption, not another delivery adapter.

## Decision

**There is one plugin and one charter source.** Codex consumes `.claude-plugin/marketplace.json`, `.claude-plugin/plugin.json`, and `skills/` directly. A second manifest or copied skills would duplicate discovery, version and rule state without adapting anything. The marketplace source stays the exact relative string `"./"`, which Codex discovery requires and `tools/lint.py` pins.

**A repository adopts Tradecraft through its canonical instructions.** Its `AGENTS.md` directs every session, before substantive action, to load and read the installed `tradecraft:charter` skill completely and to stop and tell the owner when it is unavailable. Claude reaches the same instruction through its existing root `CLAUDE.md` pointer; Codex reads it natively. A future runtime is supported when it reads `AGENTS.md` or offers a zero-logic native pointer to it. No lifecycle hook, copied charter, user-global instruction, MCP server or duplicate plugin is a fallback. Installation makes the skills available; the repository instruction makes the charter govern.

**The Codex review adapter is the native launch contract, not a shipped wrapper.** Every role launch explicitly names fresh-context inheritance, working root, sandbox or permission boundary, model and reasoning effort. Read-only roles use an ephemeral read-only session; a mutation role receives its own worktree and a write boundary confined there. The exact executable invocation is evidence in the review report and compatibility output, while the skill carries the runtime-neutral inputs. This keeps capability wrappers out of the practice and prevents a default model, inherited conversation or authoring worktree from silently changing what a seat means.

**An external pass is outside the panel regardless of who invoked it.** Automated bot output and a self-invoked `codex review` did not receive the panel dispatch or seat contract. Their outcome is reported qualitatively in the final report and in the review index's top-level `external` string. The row admits no arithmetic or revived `seats` field, so no external-count shape is added.

**The true Codex check is a cold-adopting repository with a defined failure.** `python tools/check_codex_compat.py` resolves an explicit binary, `PATH` or the Windows app bundle; verifies this tree's plugin version is installed and enabled; records the binary, CLI version, plugin version, model, reasoning effort, isolation settings and timeout; and creates a temporary git repository outside the source tree. That repository carries the supported `AGENTS.md` adoption instruction and a random sentinel whose value is absent from the prompt. A fresh ephemeral read-only Codex session returns it only after loading the complete charter, identifying both ceremony moments and reaching the charter's final paragraph. A missing or disabled plugin fails before launch; an unavailable charter fails inside the adopted flow; a launch failure or timeout is reported as a named compatibility failure. The earlier catalog probe separately proves that all nine descriptions reach their final exclusion clause.

## Rejected

- **A duplicated Codex manifest or copied skills.** The runtime already reads the shared package; duplication creates drift and no compatibility value.
- **A hook fallback in another event or output shape.** Plain output, the JSON envelope, `SessionStart` and `UserPromptSubmit` all failed in installed Codex sessions. Keeping a second path would leave governance dependent on a mechanism the compatibility check cannot prove and make runtimes follow different flows.
- **A committed Codex review wrapper.** It would be a capability wrapper and freeze one runtime's CLI surface into shipped methodology. The explicit launch inputs and recorded invocation are sufficient.
- **A standing rule selecting Codex, a model or a phase.** Runtime choice stays an implementation detail. This issue's seats use `gpt-5.6-sol` with high reasoning because the owner selected it for this run, not because every adopting repository inherits that setting.
- **Booking an external pass as a seat or count.** Invocation by the authoring session does not supply the cold boundary, shared block or lens contract that makes a panel seat evidence, and the current review row deliberately carries no arithmetic.

## Evidence

The owner affirmed the revised artifact in [issue #24's replacement convergence record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/24#issuecomment-5454211636). A cold Codex session on `gpt-5.6-sol` with high reasoning reproduced all nine full descriptions in the [skill-catalog probe](https://github.com/Grimblaz-and-Friends/tradecraft/issues/24#issuecomment-5446883255). The successive hook failures are recorded for [session-local JSON](https://github.com/Grimblaz-and-Friends/tradecraft/issues/24#issuecomment-5448061498), [installed `SessionStart` JSON](https://github.com/Grimblaz-and-Friends/tradecraft/issues/24#issuecomment-5448690197), and [installed `UserPromptSubmit`](https://github.com/Grimblaz-and-Friends/tradecraft/issues/24#issuecomment-5448774749). The branch implementation and its final compatibility, experience and review evidence live on [PR #222](https://github.com/Grimblaz-and-Friends/tradecraft/pull/222).

# D-626 — Disable pytest caching at each Codex launch

**Purpose:** preserve why the owner chose a launcher remedy for locked Windows leftovers and deferred the sandbox-mode fix. **Audience:** a future session changing Codex launch environment or pytest settings. **Success:** that session can reconsider the choice from its evidence without repeating the design.

The owner [affirmed #626's brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/626#issuecomment-5969533424) on 2026-10-03. The supplied [holder reading on #626](https://github.com/Grimblaz-and-Friends/tradecraft/issues/626) requires a decision entry. `626` is its provisional key until the implementing pull request exists; the holder resumes the builder to rename this entry and its index row to that number.

## Decision

Turn pytest caching off at every Codex implementer launch and explicit resume, and every Codex seat attempt, on every platform. Preserve the launcher's inherited `PYTEST_ADDOPTS` text and append `-p no:cacheprovider`, supplied through a command-line `shell_environment_policy.set.PYTEST_ADDOPTS` override. Choose a shared shipped helper and keep the override inside the Codex branches, without changing the parent environment or Claude launches. The [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/626#issuecomment-5969682578) specifies this implementation and its falsifiers; the holder reading leaves them unchanged.

The owner chose the launchers over per-repository pytest configuration because they are the common entrance for Codex dispatches in every adopting repository. Applying the choice on every platform keeps one launch behavior, accepting the loss of pytest's cache features. The affirmed brief's R1 names the affected features and records that tradecraft and change-proof use none of them.

The brief's history carries the Windows probes: protected temp-directory ACLs from Python, pytest's cache creation, the separate sandbox account, and successful removal after a cache-disabled Codex run. These observations justify the remedy; a recorded launch argument alone cannot prove the setting reaches a tool command. [Official OpenAI configuration documentation](https://learn.chatgpt.com/docs/config-file/config-advanced#shell-environment-policy), consulted on 2026-10-03, describes the include-filter interaction. The artifact therefore requires real launches through both launchers and an implementer resume, with plugin and environment assertions plus owner-account removal. That use belongs to the holder's later stage.

## Alternatives and limits

Defer `windows.sandbox = "mxc"`. The brief's 2026-10-03 probes under Codex 0.160.0 found that it retained owner-account ownership but did not pass tradecraft's setup and hard-link checks. The owner chose to wait for Codex's root fix rather than switch modes now. R2 gives the Steward a watch on [openai/codex#48721](https://github.com/openai/codex/issues/48721) and documented Windows modes at each cross-change read on #683; a trigger buys a floor rerun, and a passing switch comes back to the owner.

The owner left the shipped worktree-removal rule and personal Codex configuration unchanged, rejected per-repository pytest settings and Python-folder patches, and did not authorize an upstream tracker post. R3 assigns the holder an explicit-path, release-time inventory and one elevated-shell cleanup command when no Codex stage is running. The watch and cleanup stay lab-only; this implementation ships neither mechanism nor stale paths.

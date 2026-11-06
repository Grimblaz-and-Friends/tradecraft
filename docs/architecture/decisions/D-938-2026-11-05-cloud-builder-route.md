# D-938: For a set-up repository, the Claude implementer runs as a cloud session

**Status:** Accepted 2026-11-05 (#938)

**Evidence.** The affirmed brief and its amendment 1 on [#938](https://github.com/Grimblaz-and-Friends/tradecraft/issues/938) ([issuecomment-6669583777](https://github.com/Grimblaz-and-Friends/tradecraft/issues/938#issuecomment-6669583777)); the artifact settled by cap resolution ([issuecomment-6670723173](https://github.com/Grimblaz-and-Friends/tradecraft/issues/938#issuecomment-6670723173)) and the holder's whole-change reading. The spike rounds the brief links carry the tested premises.

## Decision

A repository the owner sets up runs every Claude implementer launch (artifact, build, repairs) as a Claude Code cloud session fired through that repository's routine. The route's mechanism and reasons live in `lib/DESIGN.md#the-cloud-route`, which code points at; the setup and reading steps are in the shipped reference `skills/work/references/cloud-builds.md`.

**What this narrows.** [D-939](D-939-2026-11-03-claude-launch-writes-stay-in-their-tree.md) binds every Claude author and builder launch to its tree, with a launch-owned file-tool guard and a before-and-after comparison of the owner's machine. A cloud launch runs on a remote machine, so neither applies to it: its record says the comparison didn't run and why. Everything else in D-939 stands, and a local Claude launch keeps both.

[D-924](D-924-2026-10-21-claude-launches-cannot-outlive-their-reply.md) gives every Claude launch two environment settings, `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` and a `BASH_MAX_TIMEOUT_MS` of its allocation, and excludes `Monitor`, `ScheduleWakeup`, `CronCreate` and `Workflow`. A cloud session's environment belongs to its routine's environment, which every launch through it shares, so the owner sets both settings once there: background tasks off, and a fixed command ceiling no longer than the shortest stage limit. The `Stop` hook records the values the session saw, and a missing or different value fails the attempt. The routine disallows the four tools and `verify` checks them. D-938 narrows D-924 for cloud launches only in that the command ceiling is fixed rather than set per launch. A local Claude launch keeps all of D-924.

[D-911](D-911-2026-10-13-claude-builders-load-their-tree-instructions.md) has a local Claude author or builder load its tree's root instructions through `--add-dir`, with a one-line shim for a tree whose rules live only in `AGENTS.md`, and reads which instruction files loaded from the session transcript. A cloud session loads the product clone's own `CLAUDE.md` and `AGENTS.md` as any cloud session does, so it needs neither the flag nor the shim; and the launcher can't read a cloud transcript, so the record takes the list of loaded instruction files from the run's own `instructions.md`. D-938 narrows D-911 for cloud launches in those two respects; a local Claude launch keeps all of D-911.

## Why

- **The route gives a builder that cannot reach the owner's machine** (value 1). So a failed fire stops the launch; a silent local fallback would undo the route's reason. For the same reason #906's before-and-after comparison is not run for a cloud build, and its record says why.
- **The task travels on the report branch**, because composed prompts carry artifacts up to 240,000 bytes and the fire takes 65,536 characters.
- **The report comes back on a branch, and the launcher posts it.** The run's own issue comments were refused by its safety screen, and a message to the holder elevates the run. Markers stay the holder's.
- **The practice pin follows the install record's commit**, not a checkout's `HEAD`, so it moves once per plugin update and never per merge, and a reload clears a version refusal.
- **A follow-up keeps its session's version** (the owner's ruling in amendment 1): a change is built and repaired by the session that holds its context, and the record names the loaded and installed commits so a judge can read a drift.
- **Cost comes from a shipped `Stop` hook**, which Claude Code runs rather than the model. The launcher re-checks its ledger without the transcript, and a ledger it cannot stand behind makes the cost unknown, never wrong, without discarding the work.
- **Attempt checks reuse the launch-findings hold** rather than adding a gate.
- **The practice's own repository is refused**, because its two clones would share one folder and its committed guard would govern a single-source build, which is untested.

## Open

The live halves of the acceptance criteria (U1–U10 of the artifact) run once the owner completes one repository's setup. Until then each is not yet run, never a pass.

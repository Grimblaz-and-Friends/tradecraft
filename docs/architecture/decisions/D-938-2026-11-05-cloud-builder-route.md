# D-938: For a set-up repository, the Claude implementer runs as a cloud session

**Status:** Accepted 2026-11-05 (#938)

**Evidence.** The affirmed brief and its amendment 1 on [#938](https://github.com/Grimblaz-and-Friends/tradecraft/issues/938) ([issuecomment-6669583777](https://github.com/Grimblaz-and-Friends/tradecraft/issues/938#issuecomment-6669583777)); the artifact settled by cap resolution ([issuecomment-6670723173](https://github.com/Grimblaz-and-Friends/tradecraft/issues/938#issuecomment-6670723173)) and the holder's whole-change reading. The spike rounds the brief links carry the tested premises.

## Decision

A repository the owner sets up runs its Claude implementer launches as a Claude Code cloud session fired through that repository's routine. The route carries the artifact, build, review-disposition and floor stages; any other Claude implementer stage, such as a source-verification account, stays local. A resume follows its session, so the switch has two exceptions: a session started locally before the repository was set up resumes locally, and a `cse_` cloud session resumes in the cloud after the switch entry is removed. Both exceptions await the owner's ruling (Open). The route's mechanism and reasons live in `lib/DESIGN.md#the-cloud-route`, which code points at; the setup and reading steps are in the shipped reference `skills/work/references/cloud-builds.md`.

**What this narrows.** [D-939](D-939-2026-11-03-claude-launch-writes-stay-in-their-tree.md) binds every Claude author and builder launch to its tree, with a launch-owned file-tool guard and a before-and-after comparison of the owner's machine. A cloud launch runs on a remote machine, so neither applies to it: its record says the comparison didn't run and why. Nor does D-939's memory setting: a cloud session's memory isn't switched off, and the owner's global instructions don't reach it, because it runs from its routine, not the owner's user settings. A local Claude launch keeps all of D-939.

[D-924](D-924-2026-10-21-claude-launches-cannot-outlive-their-reply.md) gives every Claude launch two environment settings, `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` and a `BASH_MAX_TIMEOUT_MS` of its allocation, and excludes `Monitor`, `ScheduleWakeup`, `CronCreate` and `Workflow`. A cloud session's environment belongs to its routine's environment, which every launch through it shares, so the owner sets both settings once there: background tasks off, and a fixed command ceiling no longer than the shortest stage limit. The `Stop` hook records the values the session saw. The attempt passes when background tasks are exactly off and the ceiling is positive and no longer than that limit, and fails otherwise; a shorter ceiling passes, so a stage limit that later grows isn't a failure, while one that shrinks needs the environment's ceiling lowered to match. The routine disallows the four tools and `verify` checks them. D-938 narrows D-924 for cloud launches in three respects: the command ceiling is fixed rather than set per launch; the notice of those settings travels in the cloud task's preamble, not the local launch notice; and the stream check that refuses work outliving its return reads not applicable, since the launcher reads no cloud stream. A local Claude launch keeps all of D-924.

[D-911](D-911-2026-10-13-claude-builders-load-their-tree-instructions.md) has a local Claude author or builder load its tree's root instructions through `--add-dir`, with a one-line shim for a tree whose rules live only in `AGENTS.md`, and reads which instruction files loaded from the session transcript. A cloud session loads the product clone's own `CLAUDE.md` and `AGENTS.md` as any cloud session does, so it needs neither the flag nor the shim; and the launcher can't read a cloud transcript, so the record takes the list of loaded instruction files from the run's own `instructions.md`. D-938 narrows D-911 for cloud launches in those two respects; a local Claude launch keeps all of D-911.

**The hook manifest.** [D-156](D-156-2026-08-24-installable-plugin-and-shipped-charter.md) made a shipped calling contract name no harness token, [D-222](D-222-2026-08-27-codex-runtime-compatibility.md) removed lifecycle hooks after they failed in installed Codex sessions, and [D-618](D-618-2026-09-14-the-guards-ship.md) keeps `check_harness_tokens` in `tools/lint.py`. D-938 ships `hooks/hooks.json` again and exempts it from that check, because a hook command must name `${CLAUDE_PLUGIN_ROOT}`. Codex loads the same manifest and, on Windows, runs a hook through PowerShell, so each command is written to be silent there and in bash.

## Why

- **The route gives a builder that cannot reach the owner's machine** ([value 1](../../values.md)). So a failed fire stops the launch; a silent local fallback would undo the route's reason. For the same reason #906's before-and-after comparison is not run for a cloud build, and its record says why.
- **The task travels on the report branch**, because composed prompts carry artifacts up to 240,000 bytes and the fire takes 65,536 characters.
- **The report comes back on a branch, and the launcher posts it.** The run's own issue comments were refused by its safety screen, and a message to the holder elevates the run. Markers stay the holder's.
- **The practice pin follows the install record's commit**, not a checkout's `HEAD`, so it moves once per plugin update and never per merge, and a reload clears a version refusal.
- **A follow-up keeps its session's version** (the owner's ruling in amendment 1): a change is built and repaired by the session that holds its context, and the record names the loaded and installed commits so a judge can read a drift.
- **Cost comes from a shipped `Stop` hook**, which Claude Code runs rather than the model. The launcher re-checks its ledger without the transcript, and a ledger it cannot stand behind makes the cost unknown, never wrong, without discarding the work.
- **Attempt checks reuse the launch-findings hold** rather than adding a gate.
- **The practice's own repository is refused**, because its two clones would share one folder and its committed guard would govern a single-source build, which is untested.

## Open

- **A cloud review-disposition's replies.** That stage's builder posts its reply dispositions on the pull request, and a cloud run's own GitHub posts may be refused by its safety screen. Who posts them for a cloud run is the owner's to rule, after a live probe.
- **The two resume exceptions** (a local session resumes locally after setup; a cloud session resumes in the cloud after its entry is removed) await the owner's ruling.
- **Native product instructions.** That the product's own `CLAUDE.md` or `AGENTS.md` loads natively in the cloud is untested; the task tells the run to read it, and `instructions_loaded` is the evidence.

The live halves of the acceptance criteria (U1–U10 of the artifact) run once the owner completes one repository's setup. Until then each is not yet run, never a pass.

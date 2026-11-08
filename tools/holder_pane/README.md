# Holder pane (lab-only)

**Purpose:** each holder session shows where its change stands in the flow: the stage, who it's waiting on, whether a running stage has stalled, the gate and floor, and the next step. The owner sees it in a pane, the status line and the session's sidebar name, and the holder is reminded of its own next step before it ends a turn (#888). **Audience:** the owner and the holder who install it and run its trial. **Success:** a holder session started after the install shows its change's state, and no builder, seat or session holding no change is touched.

This is a Claude Code mod that lives in tradecraft's repo-only `tools/` and is installed at **local scope** in each lab repository's main checkout. Nothing here ships in the plugin, no gate depends on it, and its tests are not collected by CI.

## What's here

| Path | What it is |
|---|---|
| `install.py` | Install, uninstall, and the existing-worktree copy. |
| `marketplace/.claude-plugin/marketplace.json` | The folder marketplace `tradecraft-holder-pane`, listing `holder-pane`. |
| `marketplace/holder-pane/hooks/register.ts` | The hooks module: a shim that watches the holder's own shell calls, draws, renames and reminds. |
| `marketplace/holder-pane/core/holder_pane.py` | All the logic, stdlib-only Python, one JSON object in and one out per subcommand. |
| `marketplace/holder-pane/hooks/register.test.ts` | The shim's behaviours under `claude plugin test`. |
| `tests/test_holder_pane.py` | pytest for the core and the installer, and static checks of the shim. |

## Install

Run from tradecraft's **main checkout**, once per lab repository's main checkout. The desktop app starts every session, worktree sessions included, with `--project-config-root` set to the repository's main checkout, and the CLI reads local-scope plugins and the local `env` block from there. So one install reaches every desktop session in that repository once it starts or restarts. The app also copies the main checkout's `.claude/settings.local.json` into each new session worktree, but that copy is not what loads the mod: in #915's probe with the desktop app's own CLI, an install made only in a worktree did not load under that flag, and one made in the main checkout did.

```text
python tools/holder_pane/install.py install --checkout D:/Code/tradecraft
python tools/holder_pane/install.py install --checkout D:/Code/Daemon
python tools/holder_pane/install.py install --checkout D:/Code/Countdown-Clash
python tools/holder_pane/install.py install --checkout D:/Code/change-proof
```

What it does, with the checkout as the working directory:

1. `claude plugin marketplace add <tradecraft main checkout>/tools/holder_pane/marketplace --scope local`
2. `claude plugin install holder-pane@tradecraft-holder-pane --scope local`
3. Merges `env.CLAUDE_CODE_ENABLE_FUNCTION_HOOKS = "1"` into that checkout's `.claude/settings.local.json`, keeping every other key.

- The executable defaults to the newest desktop-app Claude Code, the runtime holders run in. It's searched where the app keeps it now, `%LOCALAPPDATA%\Claude-Data\<app id>\claude-code\<version>\<build>\claude.exe`, and in its old place under `%APPDATA%\Claude\claude-code\`; the highest version wins. `--claude <exe>` overrides it.
- The first install in a checkout records what it found in `~/.tradecraft/status/.pane/installs.json`: whether it added the opt-in, and the checkout's `.claude/settings.local.json` as it was (its bytes, or that it was absent). A reinstall keeps that first record.
- Every call carries `--scope local`. `~/.claude/settings.json` is never written. The CLI's plugin registries (`~/.claude/plugins/known_marketplaces.json` and `installed_plugins.json`) do change: they are registries, not settings.
- It refuses, and runs nothing, unless `.claude/settings.local.json` is untracked and ignored in that checkout.

**Decisions in force:** the executable is searched where the desktop app keeps it now as well as in its old place, and the first install snapshots the checkout's local file so uninstall can restore it ([D-976](../../docs/architecture/decisions/D-976-2026-11-07-the-holder-pane-works-out-the-holders-own-steps.md)).

**Windgust-Questbook** tracks that file today, so the install refuses there. Once Windgust stops tracking it (the holder's Windgust issue, row 8), install there with the same command.

## A holder worktree created before the install

In the desktop app, restart that session: it reads the main checkout's install, so no copy is needed.

A session started outside the desktop app, without `--project-config-root`, reads its own worktree's local file instead. For such a session only, copy the main checkout's keys into that worktree once, then restart it:

```text
python tools/holder_pane/install.py install --worktree <the existing holder worktree>
```

## Uninstall

```text
python tools/holder_pane/install.py uninstall --checkout <main checkout>
```

1. `claude plugin uninstall holder-pane@tradecraft-holder-pane --scope local`.
2. `claude plugin marketplace remove tradecraft-holder-pane --scope local`, **only if no other checkout still has the pane**. The marketplace registration is shared by every checkout, so removing it while another checkout uses the pane would silently turn that pane and its reminder off. Another checkout has the pane when `installs.json` names it, its directory exists, and its own `.claude/settings.local.json` still enables `holder-pane@tradecraft-holder-pane`. The file is read as well as the record, so a checkout uninstalled by hand or deleted can't keep the registration forever. Desktop session worktrees aren't counted: they load the pane through the main checkout.
3. **The local file goes back as the first install found it.** The pane's keys are removed from what the file holds now (its `enabledPlugins` and `extraKnownMarketplaces` entries, and the opt-in only if this installer added it), with any container they leave empty that the file didn't hold before. If the result is the file as it was, its exact bytes are written back, or the file is deleted if the install created it. If the file changed after the install, the change is kept and the installer says the file couldn't be restored byte for byte. If the file, or the copy taken at the install, can't be read as a JSON object, the file is left as it is, the installer says why, and the install record is kept, so the copy isn't lost. A record written before the installer kept a snapshot drops every container the pane's keys leave empty.

It prints whether it kept the shared marketplace, and for which checkout. Session worktrees keep their copied file until they're removed.

**Decisions in force:** the shared registration stays while another checkout's own local file enables the pane, and the local file is restored from a snapshot taken at the first install ([D-976](../../docs/architecture/decisions/D-976-2026-11-07-the-holder-pane-works-out-the-holders-own-steps.md)).

## Updating

The marketplace is a folder with a relative source, so sessions read the plugin from the main checkout's folder itself. An update is a `git pull` in tradecraft's main checkout, then `/reload-plugins` or a restart in each holder session. `holder-pane`'s own version is raised with each change for the record; tradecraft's plugin version never moves for it.

## How it behaves

- **Sessions holding no change get nothing.** A session binds to a change only when its own shell call runs the entrance with `run <stage>` or `adopt` and `--repo`/`--issue` (a detached launcher wrapping those arguments counts). Until then the only work is an in-memory test of each shell command.
- **A restart binds only the change whose record names the session.** A session with no binding of its own binds to the one active change whose registry row carries its session id in `holder_session_id`; when its id is on active rows for more than one change, only those whose `holder_root` is the session's root count. Otherwise it stays empty until its next stage call binds it. Two holders can share one worktree, and binding by worktree alone would show the newer holder's change in the older one's session, rename it and remind it of steps that aren't its own.
- **A Steward is never touched.** A session titled `Steward`, or with a title ending in ` Steward` (for example `Daemon Steward`), never binds, is never renamed and has nothing written for it; a bound session retitled so is unbound and its files are removed. The exact title is the address a repository's holders reach their Steward by, so a renamed Steward vanishes from their view. When the title can't be read live, the desktop app's own record of the session is read for this test alone.
- **Reads.** The read-only entrance runs at most once every 35 minutes per change, across every session and trigger, never while another run for that change is under way, in the background, and never after the issue or pull request is terminal. A pull request merged while the issue stays open is holder-owned, so reading goes on. The read-only report doesn't name the implementing pull request, so each floored read finds it as the entrance does: one `gh pr list` call for a body with a whole-line closing reference (`Closes #N`). Only when none matches, two more calls follow: the issue's comments for an `implementing-pr` marker, honoured only from a login in the bound repository's `.tradecraft/work.json` `marker_producers`, as the entrance does, and that pull request's state. A read is stamped with the time it started, so a stage return made while it ran stays the newer reading. The whole read is bounded to 540 s, inside the shim's 600 s limit, and a read that never returns shows `read failed` once that budget has passed. A binding made with `--instalment` passes it on every read. A holder's own stage return is read from its local output and dispatch records, at no GitHub cost. A stage call that printed no report (a failed run prints only `work: <error>` and exits 1) is no return: the pane keeps its reading and shows `<stage> failed <time>`.
- **Stalled** shows only past the stage's deadline or when the entrance reports it. Otherwise a silent stage shows `quiet for N min`.
- **The name** is `#N · <state>`, changed only when the state changes. It's renamed only when the title's source is `auto` or `tool` and Claude Code's own permission check for the call answers `allow`; a title the owner set, an unknown source or a check that would prompt means no rename, and the pane says why. The title's source comes from the desktop app's session records, searched where the app keeps them now (`%LOCALAPPDATA%\Claude-Data\<app id>\claude-code-sessions\`) and then in the old places (`%APPDATA%\Claude\claude-code-sessions\` and the packaged app's `LocalCache`). When no record is found, the pane says `rename off: the app's session records weren't found` rather than skipping in silence, and searches again only after the record-search interval (`RECORD_SEARCH_SECONDS`), so hundreds of records aren't read on every tick.
- **A stage run in the background shows as running.** When `proof`, `ready-reviewers`, `release-report` or `catch-up` runs in the background, the pane shows `<stage> running`, with no reminder, and looks for its report on every tick: in the file the call's output was redirected to (`>`, `>>`, `&>`, `*>`, or a pipe to `tee`, `Tee-Object` or `Out-File`), or else in the task output file the launch names. A report counts only when it's complete (the last JSON object, starting a line and running to the end of the file) and the file was written since the call started, so a half-written report or an earlier run's file never reads as a return. The run's display also ends at the next stage call, or at an entrance read that started after Stop's list shows the task ended. A read that started while the stage still ran can't reflect it, so it ends nothing: the pane keeps looking for the report, which then becomes the newer reading. When Stop's list of background tasks no longer names the task and no report is found, the pane shows `<stage> failed <time>` if the file holds a `work:` line, and otherwise `<stage> ended`, still looking for the report until a newer reading comes. A foreground stage call whose report went to a file is read from that file the same way.
- **The holder's own post finishes its step, unconfirmed.** When the holder posts to its change's pull request or issue (`gh pr comment`, `gh issue comment`, `gh pr edit` with a body, or `gh api … issues/<n>/comments` as a POST) while the pane shows a step of its own, the pane shows `<stage> posted, unconfirmed` with `waiting_on: unknown`, and doesn't remind it, until the next reading taken after the post. A `run` step isn't finished by a post, because the pane sees the stage call that finishes it, so an unrelated comment never silences a reminder that's owed. A post whose command failed doesn't count. Every step but the release report is confirmed by the next read, because the entrance reads its marker, so a wrong "unconfirmed" corrects itself within one read.
- **A posted release report waits on the owner to merge.** No read ever sees a posted release report, since the entrance has no marker for it, so a wrong match would never correct itself. So only a post whose body opens with the report's title line, `**Release report: #<issue> → PR #<pr>**`, naming this change's issue and its pull request, counts. The pane reads the body the post sends: inline, from a heredoc, or from a local file the command names (`--body-file`, `-F body=@<file>`, `--input`), resolving `$NAME`, `${NAME}`, `$env:NAME`, `~`, a path relative to the last `cd`, and MSYS `/c/` drives. Release reports are posted from files, so the body is read from the file the command names, never from the command alone. A body it can't read leaves the step `posted, unconfirmed`, as for any other step. So does a report post whose own output doesn't show the comment GitHub created (its `…/issues/<n>#issuecomment-<id>` or `…/pull/<n>#issuecomment-<id>` URL), because a call can succeed while its post fails (`gh …; echo`); a post run in the background is read from its task output file as that fills. The post turns the pane to `waiting on you`, next `merge`, however the stage was run and whatever reading came before it. It records the head the title line names (`at head <sha>`), or else the head of the reading in force. That state ends only at a reading after the post that shows a different head, an entrance decision for a stage other than `release-report`, or a stage that dispatches new work for the same change: one matched to its launched bundle, or whose decision says it dispatched. A call the entrance refused launched nothing and leaves it standing. It belongs to its change: a session that runs a stage for another change and comes back finds it still standing. A catch-up's report carries the entrance's next decision, which counts as one: a catch-up whose next decision is at another stage ends it. A catch-up refused or still at `release-report` at the same head, a rerun of `release-report`, or an entrance read still at `release-report` at the same head leaves it standing, because a holder plausibly makes each of these between the post and the merge.
- **What the pane never reads.** Posts the command text doesn't show (from inside a script, comment edits by id, review comments) and shell body forms beyond those above (a PowerShell here-string, nested substitutions) aren't recognised; they leave the step owed, or unreadable, until the next read. None of this reaches GitHub, writes anywhere but the pane's own state, or starts a turn: the only GitHub reads are still the floored entrance read's.
- **The reminder** gives the holder one line, `next: <step> (yours)`, before it ends a turn whose next step is its own, once per distinct step, never twice in a row and never starting a turn.

**Decisions in force:** the pane works out the holder's own steps from its commands and local files, and the release report alone needs its title line; a posted report ends only on a new head, another stage decided, or new dispatched work; a restart binds by session id ([D-976](../../docs/architecture/decisions/D-976-2026-11-07-the-holder-pane-works-out-the-holders-own-steps.md)).

## The status file

Each bound session writes its latest reading to `~/.tradecraft/status/<owner>__<repo>__<issue>.json`, atomically and only when the content changes. Private state (bindings, per-session state, the read floor and lock, the cached entrance reading, the bundle index) lives under `~/.tradecraft/status/.pane/` and is not a contract. Two sessions bound to one change both write the file; the last write wins and `session_id` says whose it is.

| Field | Value |
|---|---|
| `schema_version` | `1` |
| `repository` | `owner/repo` |
| `issue` | the issue number |
| `session_name` | the session's live title at this write, renamed or not; if it can't be read, the last title the mod set; `null` when neither exists |
| `session_id` | the CLI session id |
| `stage` | the entrance's stage, or the stage the holder ran |
| `waiting_on` | `owner`, `holder`, `builder`, `ci`, `reviewer`, `none` or `unknown`; `unknown` also while a holder's own stage runs or has ended in the background, and while a step it posted is unconfirmed |
| `next_step` | the next step, as text |
| `gate` | the required gate's verdict, `green`, a gate-family reason, `not reached` when no implementing pull request is found, or `-` when one is open but this reading names no gate |
| `floor` | `{"outcome": ..., "satisfied": true, false or null}` |
| `status` | the entrance's status; for a reading taken locally, `returned`, `launched`, `running`, or `ended` (a background stage ended with no report found yet) |
| `source` | `entrance` or `stage-return` |
| `read_at` | when the reading was taken, ISO-8601 UTC |

## Checks

```text
python -m pytest tools/holder_pane/tests -q
<desktop claude.exe> plugin validate tools/holder_pane/marketplace/holder-pane
<desktop claude.exe> plugin test tools/holder_pane/marketplace/holder-pane
```

`tsc` checks the hooks module against the declarations the desktop build writes (its plugin-authoring skill's `types/claude-code.d.ts`), with that file's header `tsconfig.json` kept outside the mod folder.

## Trial checklist (row 9)

Run it on **one product change's holder first**, then on every holder. **The release record** is the change's release report on its pull request: record each result there.

**When each check runs.** Each check below is marked by kind.

- **Needs no stage call:** 6, 7, 9 and 12. These run before the merge of the pull request that changes the pane.
- **Needs a holder's stage calls:** 1, 2, 3, 4, 5, 8, 10, 11 and 13. These run on whichever change of the trial repository is next in flight: before the merge if one is, otherwise right after it. A change is in flight when it has an active registry row and its holder makes stage calls while the pane's pull request is open. A real holder's stage calls can't be staged on demand, so these checks wait for one.

The release report lists every check run before the merge, with its outcome, and names each check not yet run and why (no change in flight, or the change in flight hasn't reached that step). A check run after the report is posted and before the merge is added to the report's record before the merge. Checks run after the merge are recorded on the trial record with what was seen, naming any the next change didn't exercise. The rollout to every holder waits until all pass.

**Before installing,** snapshot the four files the install may touch, so check 7 can compare them byte for byte: `~/.claude/settings.json`, `~/.claude/plugins/known_marketplaces.json`, `~/.claude/plugins/installed_plugins.json`, and the checkout's `.claude/settings.local.json` (for example `copy` each to a dated folder; note it if the local file is absent).

1. **The pane draws** *(stage call)* in the desktop app (2.1.295 or newer) after the holder's first `run <stage>`. It opens as a pane tab titled `#N` beside the transcript (reopen it with `/holder-pane`). A correct pane shows, one line each: `stage`, `waiting on`, `next step`, `gate`, `floor`, `read <HH:MM> (<source>)`, and, while a stage runs, `elapsed <m>/<deadline>` and `quiet for N min`. The status line under the prompt shows the same state on one line, starting `#N · `.
2. **The sidebar name changes** *(stage call)* when the state changes. The title tool's result, `Renamed this session to "#N · <state>" (was "...")`, is in the session's debug log (`claude --debug`, or the desktop's session log); the sidebar shows the new name. Record each result. If the pane's `name` row reads `rename off: the app's session records weren't found`, the pane didn't find the desktop app's session records where it looks for them, so renaming is off: record that, and the check fails.
3. **The reminder fires** *(stage call)* at a release-report handoff. Bring one about by running `run release-report` on a change whose entrance reports `release-report` (all evidence complete). Before the holder stops, it gets `next: post the release report (yours)` once, and not again at its next stop. After it posts the report from a file with `gh pr comment <PR> --body-file <file>`, the pane shows `waiting on you` and `merge`.
4. **Reads stay within the floor** *(stage call)*. `<key>` in `~/.tradecraft/status/.pane/changes/<key>.json` is `<owner>__<repo>__<issue>`, for example `Grimblaz-and-Friends__tradecraft__888`. Sample its `last_read_started` (epoch seconds) every 10 minutes across the trial window; no two values may be less than 2,100 s apart.
5. **No builder or seat loads it** *(stage call)*. Launch a builder and a seat through the real `work.py run` from the installed checkout. Each bundle's stdout log is `~/.tradecraft/dispatches/<bundle>/*.claude.stdout.log` (its `.run.json` names it under `attempts[].stdout`). In the stream-json `system.init` line there, `holder-pane` must be absent from the plugin list.
6. **A session holding no change** *(no stage call)* in the same repository keeps its name and draws nothing: any repository's Steward, titled `Steward` or `<Name> Steward`. Run it with the trial repository's Steward (for Daemon, the `Daemon Steward` session). Observable: no `~/.tradecraft/status/.pane/bindings/<its session id>.json`, no `.pane/sessions/<its session id>.json`, no status file naming its `session_id`, and its title unchanged.
7. **The installer touches only local files** *(no stage call)*: run the install and uninstall without `--claude`, then compare the four snapshots byte for byte. `settings.json` must be identical and the registries restored; the local file must be byte-identical, or absent again if it was absent before.
8. **A hand-titled session** *(stage call)* gets no prompt and no rename, and its pane shows `rename skipped (owner-set title)`. A pane showing `rename off` instead means the records weren't found (check 2) and this check can't pass.
9. **Two checkouts share the marketplace** *(no stage call)*: install, without `--claude`, in a throwaway checkout beside the trial repository's, uninstall from the throwaway, and confirm the trial repository's `claude plugin list` still lists `holder-pane` and its pane still loads; the uninstall says it kept the shared marketplace. Then confirm that uninstalling from the last checkout removes it (in a pair of throwaway checkouts if the trial repository keeps the pane).
10. **A stage run in the background** *(stage call)*. The holder runs `proof` and `release-report` in the background with output to a file. The pane shows `<stage> running`, with no reminder, and then the stage's return. The holder posts the report from a file with `gh api … -F body=@<file>`, and the pane shows `waiting on you` / `merge`. There's no release-report reminder before or after the merge, and the pane stays on `merge` through any catch-up or `release-report` rerun at the same head before the merge.
11. **A holder's own post that finishes its step** *(stage call)*. The holder posts its use marker and stops in the same turn: the pane shows `use posted, unconfirmed` and no reminder, and is normal again after the next read. Any holder step it reaches without posting is reminded once.
12. **A restart in a worktree another change uses** *(no stage call)*. Reopen a finished holder (or any second session) in a worktree whose active registry row names another session: it stays empty and keeps its name. A holder restarted with its own active row gets its pane back.
13. **Another comment while the report is owed** *(stage call)*. Watched for, never staged: if the holder posts any other comment to the change's pull request or issue between `run release-report` and the report's post, the pane still shows the report as the holder's. Record it as not exercised when no such comment occurs.

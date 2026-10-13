# Holder pane (lab-only)

**Purpose:** each holder session shows where its change stands in the flow: the stage, who it's waiting on, whether a running stage has stalled, the gate and floor, and the next step. The owner sees it in a pane, the status line and the session's sidebar name, and the holder is reminded of its own next step before it ends a turn (#888). **Audience:** the owner and the holder who install it and run its trial. **Success:** a holder session started after the install shows its change's state, and no builder, seat or session holding no change is touched.

This is a Claude Code mod that lives in tradecraft's repo-only `tools/` and is installed at **local scope** in each lab repository's main checkout. Nothing here ships in the plugin, no gate depends on it, and its tests are not collected by CI.

## What's here

| Path | What it is |
|---|---|
| `install.py` | Install, uninstall, and the existing-worktree copy. |
| `marketplace/.claude-plugin/marketplace.json` | The folder marketplace `tradecraft-lab`, listing `holder-pane`. |
| `marketplace/holder-pane/hooks/register.ts` | The hooks module: a shim that watches the holder's own shell calls, draws, renames and reminds. |
| `marketplace/holder-pane/core/holder_pane.py` | All the logic, stdlib-only Python, one JSON object in and one out per subcommand. |
| `marketplace/holder-pane/hooks/register.test.ts` | The shim's behaviours under `claude plugin test`. |
| `tests/test_holder_pane.py` | pytest for the core and the installer, and static checks of the shim. |

## Install

Run from tradecraft's **main checkout**, once per lab repository's main checkout. The desktop app copies that checkout's `.claude/settings.local.json` into each new session worktree, so every holder session started afterwards gets the pane.

```text
python tools/holder_pane/install.py install --checkout D:/Code/tradecraft
python tools/holder_pane/install.py install --checkout D:/Code/Daemon
python tools/holder_pane/install.py install --checkout D:/Code/Countdown-Clash
python tools/holder_pane/install.py install --checkout D:/Code/change-proof
```

What it does, with the checkout as the working directory:

1. `claude plugin marketplace add <tradecraft main checkout>/tools/holder_pane/marketplace --scope local`
2. `claude plugin install holder-pane@tradecraft-lab --scope local`
3. Merges `env.CLAUDE_CODE_ENABLE_FUNCTION_HOOKS = "1"` into that checkout's `.claude/settings.local.json`, keeping every other key.

- The executable defaults to the newest desktop-app Claude Code under `%APPDATA%\Claude\claude-code\<version>\<hash>\claude.exe`, the runtime holders run in. `--claude <exe>` overrides it.
- Every call carries `--scope local`. `~/.claude/settings.json` is never written. The CLI's plugin registries (`~/.claude/plugins/known_marketplaces.json` and `installed_plugins.json`) do change: they are registries, not settings.
- It refuses, and runs nothing, unless `.claude/settings.local.json` is untracked and ignored in that checkout.

**Windgust-Questbook** tracks that file today, so the install refuses there. Once Windgust stops tracking it (the holder's Windgust issue, row 8), install there with the same command.

## A holder worktree created before the install

A session worktree created before the install doesn't have the local file. Copy the main checkout's keys into it once, then restart that session:

```text
python tools/holder_pane/install.py install --worktree <the existing holder worktree>
```

## Uninstall

```text
python tools/holder_pane/install.py uninstall --checkout <main checkout>
```

It runs `claude plugin uninstall holder-pane@tradecraft-lab --scope local`, then `claude plugin marketplace remove tradecraft-lab --scope local`, then removes the opt-in key (and `env` if that leaves it empty) only if this installer added it; an opt-in that was already there stays. Whether it added the key is recorded in `~/.tradecraft/status/.pane/installs.json`. Session worktrees keep their copied file until they're removed.

## Updating

The marketplace is a folder with a relative source, so sessions read the plugin from the main checkout's folder itself. An update is a `git pull` in tradecraft's main checkout, then `/reload-plugins` or a restart in each holder session. `holder-pane`'s own version is raised with each change for the record; tradecraft's plugin version never moves for it.

## How it behaves

- **Sessions holding no change get nothing.** A session binds to a change only when its own shell call runs the entrance with `run <stage>` or `adopt` and `--repo`/`--issue` (a detached launcher wrapping those arguments counts), or, at restart, when exactly one active registry row's `holder_root` is the session's root. Until then the only work is an in-memory test of each shell command. A session whose live title is `Steward` never binds.
- **Reads.** The read-only entrance runs at most once every 35 minutes per change, across every session and trigger, never while another run for that change is under way, in the background, and never after the issue or pull request is terminal. A pull request merged while the issue stays open is holder-owned, so reading goes on. The read-only report doesn't name the implementing pull request, so each floored read finds it as the entrance does: one `gh pr list` call for a body with a whole-line closing reference (`Closes #N`). Only when none matches, two more calls follow: the issue's comments for an `implementing-pr` marker, and that pull request's state. A read is stamped with the time it started, so a stage return made while it ran stays the newer reading. The whole read is bounded to 540 s, inside the shim's 600 s limit, and a read that never returns shows `read failed` once that budget has passed. A binding made with `--instalment` passes it on every read. A holder's own stage return is read from its local output and dispatch records, at no GitHub cost. A stage call that printed no report (a failed run prints only `work: <error>` and exits 1) is no return: the pane keeps its reading and shows `<stage> failed <time>`.
- **Stalled** shows only past the stage's deadline or when the entrance reports it. Otherwise a silent stage shows `quiet for N min`.
- **The name** is `#N · <state>`, changed only when the state changes. It's renamed only when the title's source is `auto` or `tool` and Claude Code's own permission check for the call answers `allow`; a title the owner set, an unknown source or a check that would prompt means no rename, and the pane says why.
- **The reminder** gives the holder one line, `next: <step> (yours)`, before it ends a turn whose next step is its own, once per distinct step, never twice in a row and never starting a turn.

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
| `waiting_on` | `owner`, `holder`, `builder`, `ci`, `reviewer`, `none` or `unknown` |
| `next_step` | the next step, as text |
| `gate` | the required gate's verdict, `green`, a gate-family reason, `not reached` when no implementing pull request is found, or `-` when one is open but this reading names no gate |
| `floor` | `{"outcome": ..., "satisfied": true, false or null}` |
| `status` | the entrance's status; for a reading taken locally, `returned`, `launched` or `running` |
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

**Before installing,** snapshot the four files the install may touch, so step 7 can compare them byte for byte: `~/.claude/settings.json`, `~/.claude/plugins/known_marketplaces.json`, `~/.claude/plugins/installed_plugins.json`, and the checkout's `.claude/settings.local.json` (for example `copy` each to a dated folder).

1. **The pane draws** in the desktop app (2.1.295 or newer) after the holder's first `run <stage>`. It opens as a pane tab titled `#N` beside the transcript (reopen it with `/holder-pane`). A correct pane shows, one line each: `stage`, `waiting on`, `next step`, `gate`, `floor`, `read <HH:MM> (<source>)`, and, while a stage runs, `elapsed <m>/<deadline>` and `quiet for N min`. The status line under the prompt shows the same state on one line, starting `#N · `.
2. **The sidebar name changes** when the state changes. The title tool's result, `Renamed this session to "#N · <state>" (was "...")`, is in the session's debug log (`claude --debug`, or the desktop's session log); the sidebar shows the new name. Record each result.
3. **The reminder fires** at a release-report handoff. Bring one about by running `run release-report` on a change whose entrance reports `release-report` (all evidence complete). Before the holder stops, it gets `next: post the release report (yours)`, once. After it posts the report with `gh pr comment <PR>`, the pane shows `waiting on you` and `merge`.
4. **Reads stay within the floor.** `<key>` in `~/.tradecraft/status/.pane/changes/<key>.json` is `<owner>__<repo>__<issue>`, for example `Grimblaz-and-Friends__tradecraft__888`. Sample its `last_read_started` (epoch seconds) every 10 minutes across the trial window; no two values may be less than 2,100 s apart.
5. **No builder or seat loads it.** Launch a builder and a seat through the real `work.py run` from the installed checkout. Each bundle's stdout log is `~/.tradecraft/dispatches/<bundle>/*.claude.stdout.log` (its `.run.json` names it under `attempts[].stdout`). In the stream-json `system.init` line there, `holder-pane` must be absent from the plugin list.
6. **A session holding no change** in the same repository (the Steward's, in tradecraft) keeps its name and draws nothing. Observable: no `~/.tradecraft/status/.pane/bindings/<its session id>.json`, no `.pane/sessions/<its session id>.json`, and no status file naming its `session_id`.
7. **The installer touches only local files:** after a real install and uninstall, compare the four snapshots byte for byte; `settings.json` must be identical, and the registries and the local file restored.
8. **A hand-titled session** gets no prompt and no rename, and its pane shows `rename skipped (owner-set title)`.
9. **Two checkouts share the marketplace:** install in two checkouts, uninstall from one, and confirm the other still loads the mod.

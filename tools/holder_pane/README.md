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

It runs `claude plugin uninstall holder-pane@tradecraft-lab --scope local`, then `claude plugin marketplace remove tradecraft-lab --scope local`, then removes the opt-in key (and `env` if that leaves it empty). Session worktrees keep their copied file until they're removed.

## Updating

The marketplace is a folder with a relative source, so sessions read the plugin from the main checkout's folder itself. An update is a `git pull` in tradecraft's main checkout, then `/reload-plugins` or a restart in each holder session. `holder-pane`'s own version is raised with each change for the record; tradecraft's plugin version never moves for it.

## How it behaves

- **Sessions holding no change get nothing.** A session binds to a change only when its own shell call runs the entrance with `run <stage>` or `adopt` and `--repo`/`--issue` (a detached launcher wrapping those arguments counts), or, at restart, when exactly one active registry row's `holder_root` is the session's root. Until then the only work is an in-memory test of each shell command. A session whose live title is `Steward` never binds.
- **Reads.** The read-only entrance runs at most once every 35 minutes per change, across every session and trigger, never while another run for that change is under way, in the background, and never after the change merges or closes. A holder's own stage return is read from its local output and dispatch records, at no GitHub cost.
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
| `gate` | the required gate's verdict, `green`, a gate-family reason, `not reached` before a pull request, or `-` |
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

Run it on **one product change's holder first**, then on every holder. Record each result in the release record.

1. **The pane draws** in the desktop app (2.1.295 or newer) after the holder's first `run <stage>`.
2. **The sidebar name changes** when the state changes: record the title tool's `Renamed ... (was ...)` results.
3. **The reminder fires** at a release-report handoff: `next: post the release report (yours)`, once, before the holder stops.
4. **Reads stay within the floor:** across the trial window, `last_read_started` in `~/.tradecraft/status/.pane/changes/<key>.json` never moves by less than 35 minutes.
5. **No builder or seat loads it:** launch a builder and a seat through the real `work.py run` from the installed checkout; `holder-pane` must be absent from the plugin list in each one's stream-json `system.init` line, in the bundle's stdout log.
6. **A session holding no change** in the same repository (the Steward's, in tradecraft) keeps its name and draws nothing.
7. **The installer touches only local files:** compare `~/.claude/settings.json` byte for byte before and after a real install and uninstall, and check the registries and local file are restored.
8. **A hand-titled session** gets no prompt and no rename, and its pane shows `rename skipped (owner-set title)`.
9. **Two checkouts share the marketplace:** install in two checkouts, uninstall from one, and confirm the other still loads the mod.

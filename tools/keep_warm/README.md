# Desktop keep-warm (lab-only)

**Purpose:** an idle desktop session of a practice repository keeps its prompt cache warm, so the owner's next real turn reads its conversation from the cache instead of paying to write it again (#983, row 5). **Audience:** the owner who approves the install, and the holder who installs it and runs its probes. **Success:** a desktop session idle for an hour answers one short keep-warm turn and its next real turn reads at least 0.9 of its prompt from the cache, while no keep-warm turn runs a tool, overlaps a running turn, outlives its cap or counts as the owner speaking.

This is a Claude Code mod that lives in tradecraft's repo-only `tools/` and is installed at **local scope** in each practice repository's main checkout, beside the holder pane and the Steward's wake. Nothing here ships in the plugin, because a mod is a desktop-app feature and shipped material names no lab tool. It covers the desktop sessions of a practice repository: holders and both Stewards.

## What's here

| Path | What it is |
|---|---|
| `install.py` | Install and uninstall, running the pane installer's shared steps under this mod's own names. |
| `marketplace/.claude-plugin/marketplace.json` | The folder marketplace `tradecraft-keep-warm`, listing `keep-warm`. |
| `marketplace/keep-warm/hooks/register.ts` | The hooks module: wiring only, every decision taken from the core. |
| `marketplace/keep-warm/hooks/register.test.ts` | The module's behaviours under `claude plugin test`. |
| `marketplace/keep-warm/core/keep_warm_desktop.py` | Every decision, stdlib-only Python, one JSON object out per subcommand. |
| `../tests/test_keep_warm_desktop.py` | pytest for the core and the installer, and static checks of the module; CI collects it. |

## Install

The install is a standing change on the owner's machine, so it waits for the merge and **the owner's approval, asked once**, of what it changes in each practice repository's main checkout:

- the marketplace record `tradecraft-keep-warm`, pointing at `tools/keep_warm/marketplace` in tradecraft's main checkout;
- `keep-warm@tradecraft-keep-warm` enabled at local scope in that checkout, so it loads in every desktop session the owner opens there;
- the hooks-module opt-in `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS = "1"` in that checkout's `.claude/settings.local.json`, the same key, value and file the pane's and the wake's installs write.

Until he approves, desktop sessions behave as today. Then run from tradecraft's **main checkout**, once per practice repository's main checkout, with the default state directory and no probe variable set:

```text
python tools/keep_warm/install.py install --checkout <main checkout>
```

What it does, with the checkout as the working directory:

1. `claude plugin marketplace add <tradecraft main checkout>/tools/keep_warm/marketplace --scope local`
2. `claude plugin install keep-warm@tradecraft-keep-warm --scope local`
3. Merges `env.CLAUDE_CODE_ENABLE_FUNCTION_HOOKS = "1"` into that checkout's `.claude/settings.local.json`, keeping every other key.

- Its marketplace and plugin names are its own, so no install here can repoint `steward-wake@tradecraft-lab` or `holder-pane@tradecraft-holder-pane`: a second `marketplace add` under a name already registered repoints it (#915).
- The executable defaults to the newest desktop-app Claude Code, found as the pane's installer finds it; `--claude <exe>` overrides it. Every call carries `--scope local`, and `~/.claude/settings.json` is never written.
- It refuses, and runs nothing, unless `.claude/settings.local.json` is untracked and ignored in that checkout.
- The first install in a checkout records in `~/.tradecraft-lab/keep-warm/installs.json` whether it added the opt-in, and the checkout's local file as it found it (its bytes, or that it was absent). A reinstall keeps that first record.
- A desktop session loads the mod at its next start or restart, as it does the pane: the app reads local-scope plugins from the repository's main checkout.

## Undo

```text
python tools/keep_warm/install.py uninstall --checkout <main checkout>
```

1. `claude plugin uninstall keep-warm@tradecraft-keep-warm --scope local`.
2. `claude plugin marketplace remove tradecraft-keep-warm --scope local`, **only if no other checkout still enables `keep-warm`**. Another checkout counts when `installs.json` names it, its directory exists, and its own `.claude/settings.local.json` still enables `keep-warm@tradecraft-keep-warm`; a file that can't be read counts as enabling it. So removing the mod from one repository leaves the others, the wake and the pane working.
3. The local file goes back as the first install found it, as the pane's uninstall restores its own (its README's "Uninstall"). **The opt-in is removed only when this installer added it and no `holder-pane@…`, `steward-wake@…` or `keep-warm@…` entry is still enabled in that file**; when one is, the uninstall says it kept the opt-in and for which. The pane's uninstall keeps it by the same rule, and the wake's Undo names `keep-warm@…` beside `holder-pane@…`. Mods uninstalled in another order than they were installed can leave the opt-in behind, because the last to go may have found it already there: once no lab mod is left in that file, remove the key by hand.

The state directory `~/.tradecraft-lab/keep-warm` stays; deleting it is the owner's call.

## Updating

The marketplace is a folder with a relative source, so sessions read the plugin from tradecraft's main checkout itself. An update is a `git pull` there, then a restart of each desktop session. `keep-warm`'s own version is raised with each change for the record.

## How it behaves

- **Only a practice repository's sessions.** At session start the core finds the session root's main checkout (`git worktree list --porcelain`'s first entry, else the root itself). Without `.tradecraft/work.json` there, the session is inert: no timer, and every `due` answers no.
- **About every 55 minutes, inside the cache's hour.** Every 60 s, while no turn runs and no keep-warm prompt is waiting to start, the module asks the core whether a turn is due. The core reads the session's last model call from its transcript (`~/.claude/projects/*/<session>.jsonl`, or under `CLAUDE_CONFIG_DIR`) and answers yes only when that call is at least 3,300 s and at most 3,420 s old.
- **Never over a running turn.** The module tracks the main turn from `turn.start` to `turn.complete` and asks nothing while one runs or while its own prompt is pending; the core answers no to `--turn-running 1` whatever else holds.
- **Not after the cache has lapsed.** A last call more than 3,420 s old, as after the app restarts, stops the session until its next real turn: rebuilding a lapsed cache for an absent owner is the cost this exists to avoid.
- **A cap.** At most eight keep-warm turns, within eight hours of the session's last real turn; no turn once the context is at 0.90 of the window (1,000,000 tokens when the window is unknown).
- **The turn's text** is `[tradecraft keep-warm] This turn is the practice's keep-warm, not the owner speaking. Answer with one word and use no tools.` It is answered with one word.
- **No tools in a keep-warm turn.** While the keep-warm turn runs, the module refuses each tool call the model makes with the mod API's `tool.call` guard (`{ deny }`), declared in the desktop build's plugin-authoring `types/claude-code.d.ts`; the call never runs and nothing else sent changes. Another mod's own calls, such as the pane's title read, are not the model's and pass. The core also reads every finished keep-warm turn back: a `tool_use` in it, a turn it can't find in the transcript, or a first call that missed (one that read nothing from the cache, whatever it wrote, or wrote more than max(20,000 tokens, 0.05 × what it read)) is logged and stops the session until its next real turn.
- **Not the owner.** The Steward's handover gate is unchanged: by the wake module's own comment, a prompt a mod submits does not pass through the wake's `prompt.submit` hook, and a build whose prompt does pass it gives the origin `plugin`, which `origin-is-owner` counts as not the owner. P5 checks it. The pane gives no reminder during a keep-warm turn: it reads this mod's session file, and while `turn_open` is true its reminder stays owed for the holder's next real turn.
- **No status line, no files from the module.** The pane and the wake own the status line. Only the core writes, under the state directory: `sessions/<session>.json` and `log.jsonl`, which records each submission, each warm turn's cache figures, each stop with its reason, and the module's own faults.

**Decisions in force:** this section, settled on #983 (row 5 of its affirmed brief).

## The state directory and probe settings

`--state-dir`, else `KEEP_WARM_LAB_STATE_DIR`, else `~/.tradecraft-lab/keep-warm`. The probe-only timings `KEEP_WARM_DESKTOP_INTERVAL_SECONDS`, `KEEP_WARM_DESKTOP_LAPSE_SECONDS`, `KEEP_WARM_DESKTOP_CAP_SECONDS` and `KEEP_WARM_DESKTOP_TICK_SECONDS` are refused against the default directory, as the wake's are, so a probe sets `KEEP_WARM_LAB_STATE_DIR` to its own directory. The module passes the directory and the timings it reads to every core call.

## Checks

```text
python -m pytest tools/tests/test_keep_warm_desktop.py -q
<desktop claude.exe> plugin validate tools/keep_warm/marketplace/keep-warm
<desktop claude.exe> plugin test tools/keep_warm/marketplace/keep-warm
```

## Probe checklist

Running these is the holder's, after the merge and before the standing install. Each runs in a throwaway checkout that has `.tradecraft/work.json`, with the mod installed there and uninstalled afterwards, and a probe state directory with probe timings wherever the check allows. **Before installing,** snapshot the four files the pane's check 7 names (`~/.claude/settings.json`, `~/.claude/plugins/known_marketplaces.json`, `~/.claude/plugins/installed_plugins.json` and the checkout's `.claude/settings.local.json`); after the uninstall, they must be restored byte for byte. Record each result on the change's release record.

- **P1 — a warm turn pays (AC30).** Production timings, a desktop session idle 66 minutes with the mod on: exactly one keep-warm turn, answered in one word, and the next real turn's first call reads at least 0.9 of its prompt from the cache. With the mod off, the same idle shows the reload.
- **P2 — the cap (AC31).** A short `KEEP_WARM_DESKTOP_CAP_SECONDS`: no keep-warm turn after it.
- **P3 — no tool call (AC32).** Read every keep-warm turn of P1 and P2 in the transcript for `tool_use`: there is none, and `log.jsonl` names no `tool-use` stop.
- **P4 — a restart after the lapse (AC33).** Restart the app 61 minutes or more after the session's last call: no keep-warm turn until a real one.
- **P5 — not the owner (AC34).** A session titled `Steward` with the wake on, using a probe state directory for both: `handover-due`'s `--since-owner` input and `origins.log`'s last owner line are the same before and after a keep-warm turn.
- **P6 — no practice, no turn (AC35).** A checkout without `.tradecraft/work.json`: no keep-warm turn.
- **P7 — the pane holds its reminder (AC36).** A holder session with the pane on and a step of its own owed: the keep-warm turn still ends in one word with no tool call, and the reminder comes at the holder's next real turn.
- **P8 — one removal leaves the rest (AC37).** Installed in two throwaway checkouts and uninstalled from one: `claude plugin list` in the other still lists `keep-warm`, and the wake's and the pane's status lines still draw.

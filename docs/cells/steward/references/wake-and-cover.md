# The Steward's wake, handover and cover

**Purpose:** operate the marker and watermark on #683, the `steward-wake` mod, the handover and the hourly cover that #890 built. **Audience:** the Steward, a Steward resumed from a handover, and a replacement installing or undoing any of it. **Success:** every Steward post is marked, handled intake moves the watermark, each wake turn is answered for what woke it, a handover loses nothing the Steward owed, and a stopped cover is reported to the owner.

Everything runs through `tools/steward_watch.py` in the Steward's checkout. Each command prints one line of ASCII JSON. The mod and the cover call the same script, so they never disagree about what counts as intake or a due read.

## The marker and the watermark

Every comment the Steward posts on #683 opens with exactly one first line:

```text
<!-- lab:steward:v1 kind=KIND [read=N] -->
```

`KIND` is `post`, `read-note` or `watermark`, and `read=N` appears on read notes only. Only the first line counts: a marker quoted later in a comment does not make it the Steward's. A marker counts only on a comment from the owner's account (`Grimblaz`), which every lab session writes with: tradecraft is public, so a marker copied by anyone else is intake like any other comment and never a watermark. The `lab:` namespace keeps these out of the shipped `tradecraft:` marker vocabulary.

Exactly one comment is the watermark, edited in place:

```text
<!-- lab:steward:v1 kind=watermark handled=COMMENT_ID read=N cutoff=ISO_UTC alerts=ISSUE -->
```

`handled` is the last page comment the Steward has handled, `read` and `cutoff` are the last read's number and recorded cutoff, and `alerts` is the alert issue. **Intake** is every unmarked comment whose id is above `handled`; ids are compared, not times, so an edit to an old comment is not intake. Zero watermark comments, or more than one, makes every reading command exit non-zero naming the fault, with no trigger, no alert and no recorded cover success; repair the page before anything else.

## The commands

Each command takes `--page N` (default 683; any other page is a probe) and `--state-dir`.

| Command | What it does |
|---|---|
| `post --kind post\|read-note [--read N] --body-file F` | Prepends the marker and posts. Every Steward comment on #683 goes through it. Write the comment's text to a file first (your scratchpad will do), leaving the marker out because the command adds it, then pass that file's path. |
| `handled COMMENT_ID` | Moves `handled` forward to a comment on the page, refusing a lower or foreign id, and prints every unmarked comment it newly covers so you see what you are declaring handled. |
| `read-recorded --read N --cutoff ISO` | After a read note posts, sets `read` and `cutoff`, so the next read can come due. |
| `status` | Prints the watermark, open intake, the next read's merge count, each repository's reach, the cover's state and the handover's state. |
| `seed --handled ID --read N --cutoff ISO --alerts ISSUE` | Creates the watermark; refused if one exists. Install only. |

The mod and the cover use the rest (`wake`, `mark-woken`, `origin-is-owner`, `handover-due`, `handover-step`, `handover-check`, `resume-text`, `cover`, `post-alert`, `cover-task`, `config`); `--help` on each names its arguments.

## The state directory

All local state lives in one directory: `--state-dir`, else the environment variable `STEWARD_LAB_STATE_DIR`, else `~/.tradecraft-lab/steward`. It holds the handover state file `handover.md` and its previous copy `handover.prev.md`, the handover's record `handover-state.json`, the wake's record `woken.json`, `origins.log`, the cover's `cover-registered.json`, `cover-last-success.json`, `cover-last-run.json` and `cover.lock`, and the `handover-disabled` switch. It sits outside every scratchpad and checkout, so it survives a clear, a checkout move and a replacement Steward.

Only the script writes there; the mod writes no file and keeps no store. **Probe-only settings are refused against the default directory:** the `STEWARD_WAKE_*` overrides (tick, handover tokens, owner-quiet seconds, settle seconds, simulated clear refusal, page), the cover's `--probe-hold` and `--probe-hang`, a page other than 683, and a cover task with probe options. A probe therefore sets `STEWARD_LAB_STATE_DIR` to its own directory, and the production install sets neither. A probe session also runs with no connectors and with `gh` denied, because a probe that follows a wake, refusal or resume prompt acts as a Steward would: #890's build probes tried to write the owner board and post on #683 until they were run that way. Wake keys are recorded per page, so a probe page's keys can neither suppress nor prune the live page's.

## The wake

Every 300 seconds the mod runs `wake`, which reads the watermark, the page's intake and merged pull requests across the six lab repositories (tradecraft, change-proof and the four product repositories in `.tradecraft/work.json`). It names two kinds of trigger:

- **`read:N+1`**, when five or more merges have `mergedAt` strictly after the watermark's `cutoff`. Its turn says `steward-wake: read N+1 is due (M merges since CUTOFF)`; run the cross-change read, post its note with `post --kind read-note --read N+1`, then `read-recorded`.
- **`intake:ID`**, for each intake comment. Its turn says `steward-wake: new intake on #683: LINK`; handle it under the cell's intake rules, then `handled ID`.

Each key wakes the Steward once: after the mod submits a trigger's turn it records the key, and a key stays recorded while its trigger stands. A due read therefore wakes once until `read-recorded` moves the watermark, and an intake left unhandled is not woken again; the cover alerts on it after an hour. Nothing else starts a turn, and while nothing is new the mod makes no model call. When a read and intake are new in the same tick, the mod submits one turn per key, the read first and then each intake in id order; each starts once the session is idle, so they run one after another and each names its own trigger. A failed read of any repository wakes nothing and records nothing; the status line names it, and the cover's state is still reported, so a stale cover's note reaches you even then.

## The handover

The mod tracks, in memory, whether a turn is running, when the last one ended, the last Stop event's background tasks and crons, the subagents' statuses, and when the owner last spoke. Every prompt's origin goes through `origin-is-owner --record`, which appends the kind, the time and the verdict (no text) to `origins.log`. Only `plugin`, `peer`, `peer-send-message`, `task-notification`, `scheduled-trigger`, `projects-relay`, `coordinator`, `observer` and `observer-activity` are not the owner; every other kind counts as him, so an unsure guard delays a handover rather than firing one. A mod load also counts as the owner having just spoken.

**The gate** (`handover-due`) opens only when all of these hold: context above 250,000 tokens; no turn running; 60 seconds since the last turn ended with none started since; no background task, cron or busy subagent; an hour since the owner last spoke; and no `handover-disabled` file. When it is waiting on anything but size, the status line names what.

**The sequence:**

1. **Request.** The mod submits a turn naming the handover id and the state file's full path, which is always `handover.md` in the state directory. Write that file, then end your turn. Its first line is `<!-- lab:steward-handover:v1 id=ID old_session=SESSION written=ISO -->`, and it carries four headings: **In progress**, **Promises and deadlines**, **Running tasks and output paths**, and **The owner's unrecorded words, verbatim**. Under each put only what #683, the memory store, the open issues and the owner board do not already carry, or `none`. The previous file is moved to `handover.prev.md`.
2. **Check.** After the turn settles, `handover-check` passes only if the header carries this id, its `written=` time is not before the request, and all four headings are present. A failing file, or none within 15 minutes, abandons the attempt with a status line, and it is not retried for an hour.
3. **Clear.** At a quiet moment (no turn running, and 60 seconds since the last one ended), the mod runs `/clear` as if typed. The name "Steward" survives a clear, so holders still reach it by name.
4. **Resume.** When the clear arrives, the mod submits the resume turn. It names the handover, the state file, this cell and the old conversation id, which "Resume previous session" retrieves. Confirm each state-file item against #683, the memory store, the open issues and the owner board. Record an item you cannot confirm on #683 with `post`, naming the handover id, so it does not live only in this session; one that needs the owner also goes on the owner board. Then take up keeping the owner board current. A resume with no state file (it was never written, or the directory was lost) follows the cell's handoff rule alone: #683, the memory store, the open issues and the owner board. If a turn ran after the file was written, the resume says so: read that last exchange in the old conversation. If the file failed its check, rebuild what you owe from the old conversation before anything else.

**If the clear is refused**, or no clear arrives within 120 seconds, the mod submits a turn carrying the refusal. Ask the owner, in your reply and on the owner board, to type `/clear`. Until he does, the wake keeps running, and every turn carries a note: bring `handover.md` up to date and rewrite its `written=` time before ending the turn, so the file is current whenever his `/clear` arrives. His `/clear` resumes exactly as step 4. Only the request-to-clear window, at most about 17 minutes, pauses the wake; a trigger found meanwhile fires once it ends. A reload of the mod abandons an active attempt and keeps one awaiting the owner.

## The cover

Windows' task scheduler runs `cover` hourly under `pythonw.exe`, so no console opens, and every `gh` child is launched with no window. The task runs only while the owner is logged on and uses his existing `gh` login, ignores a new start while one is running, and is stopped after five minutes; the run itself gives up after four, and a lock in the state directory refuses a second live run.

Each run reads the watermark, the intake, merges across all six repositories and the alert issue's bot comments, and finds the waiting items: an intake comment unhandled for more than an hour, and a read whose fifth merge landed more than three hours ago with no read note and no watermark advance. Items already named in a `github-actions[bot]` comment on the alert issue (its first line is `<!-- lab:steward-alert:v1 items=K1,K2 -->`) are dropped, so each item is alerted once. If any remain, it dispatches `.github/workflows/steward-alert.yml` on `main` with the alert issue and the keys. That job, as `github-actions[bot]`, posts one comment mentioning the owner with each key and its public #683 link, because a comment under the owner's own account would not notify him. It carries no title, author or product text, and is no check on any pull request.

A run records `cover-last-success.json` only when every read, and any dispatch, succeeded; every run records `cover-last-run.json` with its outcome. `cover --dry-run` reads the same data and prints the waiting items, the keys it would dispatch and each repository's reach, and writes nothing but its own lock.

**When the cover is stale** — more than two hours since the later of its registration and its last success, so a fresh install is not stale before the cover's first run, while one registered but never successful is — the mod pins a status line and your next turn carries one note saying so. Tell the owner the cover has stopped working, with the last success time, then look at `cover-last-run.json` for why (an expired `gh` login looks exactly like this). Each stale episode is noted once.

## Install

**First ask the owner, once, to approve the install's standing changes:** a marketplace record at user level that enables no plugin, the mod enabled at local scope in your checkout, an hourly scheduled task on his machine, a new alert issue, and a watermark comment on #683. Then, with the default state directory and no probe variable set:

1. Check with `git status` that nothing of your own is at risk, and bring your checkout to a commit that contains #890's change.
2. Handle any pending #683 intake.
3. Open the alert issue in tradecraft. Its body opens with the line `<!-- lab:steward-alerts:v1 -->`, followed by plain English saying it carries the cover's alerts.
4. `python tools/steward_watch.py seed --handled <newest #683 comment id> --read <current read> --cutoff <its cutoff> --alerts <alert issue>`.
5. `python tools/steward_watch.py cover-task --register`. It records its registration time, and the cover is registered before the mod loads, so the mod's first wake does not report a cover that has never had its chance to run.
6. From your checkout: `claude plugin marketplace add <checkout>\tools\steward-wake`, then `claude plugin install steward-wake@tradecraft-lab --scope local`, then `/reload-plugins`.
7. Prove the dispatch route: `gh workflow run steward-alert.yml --repo Grimblaz-and-Friends/tradecraft --ref main -f issue=<alert issue> -f items=probe:1`, and check the bot comment mentions the owner. Then, with one item actually waiting, run `cover` twice in a row and check the alert issue gains exactly one bot comment for that key.
8. Record the install on #890 and #683, with the before-and-after diff of `~/.claude/settings.json`, `~/.claude/plugins/known_marketplaces.json` and `~/.claude/plugins/installed_plugins.json`.

**Watch after install, and record on #890:**

- **The desktop app's prompt origin.** Ask the owner to type one message in your desktop session, then read the last line of `origins.log`: it must say `owner=yes`. If it says `owner=no`, create `handover-disabled` in the state directory, which stops every handover; record the finding on #890 and leave the file until the classification is fixed.
- **The first live handover.** Record that the name `Steward` is unchanged and holders still reach it by name, that the Remote Control link still serves the owner's phone (one message he sends from it afterwards), and whether the conversation id changed. Record the resume prompt the mod submitted, checking each element above. Compare that handover's `handover.md` item by item against your resume turn's reply: each item confirmed, or recorded as unconfirmable.

## Undo

1. `claude plugin uninstall steward-wake@tradecraft-lab --scope local`, then `/reload-plugins`.
2. `claude plugin marketplace remove tradecraft-lab`
3. `python tools/steward_watch.py cover-task --unregister`, which also removes the cover's registration record.
4. Close the alert issue.
5. The state directory `~/.tradecraft-lab/steward` stays where it is. Read its `handover.md` first and carry anything still owed to #683; deleting the directory afterwards is the owner's call, because it is a delete. The install sets no `STEWARD_LAB_STATE_DIR`, so there is nothing to unset; if one was set by hand for a probe, unset it.
6. Deleting the watermark comment is the owner's call, because it is a delete.

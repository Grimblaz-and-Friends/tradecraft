# D-986 — Dispatched sessions make only their step's GitHub writes

**Purpose:** record why every dispatched session that can write (the artifact author, the builder and the use consumer), and any session one of them starts, is held to the GitHub writes its own step needs, and what was chosen over what. **Audience:** a future session changing the launchers' bound (`lib/github_allowance.py`, `lib/github_write_guard.py`), the composed prompts' allowance sentence, or the grant route. **Success:** that reader can recover what was chosen over what without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/894#issuecomment-6749088039) governs. Its pre-implementation artifact was [settled on the cap route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/894#issuecomment-6751383662), with the holder readings 6751424278 and 6752764186. The lane is ordinary / connected, and no panel was bought. The two cases on record are #886's author, which pushed because a brief line read as an order, and #890's probe sessions, which inherited the owner's login and claude.ai connectors. Nothing reached a product either time.

## Rows and their reasons

- **Row 1, every writer and every session it starts.** One cause produced both cases: every dispatched session held the owner's full GitHub login, and nothing said which writes its step could make. The owner chose every writer over the artifact author alone. A cloud build is told its allowance, but its run record says the launch block did not run, because the block runs on this machine.
- **Row 2, the allowance is the writes each duty already needs.** The author and use consumer make none. A builder pushes its own branch, and in review-disposition also replies on and resolves its own pull request's threads and answers body findings there. Reads stay open. The holder's endpoints stay the holder's.
- **Row 3, instructions and a launch block together** (the owner's ruling). Instructions alone would have stopped #886's author, but never reach a session the builder starts; only the launch environment and settings do. The command check is a tripwire on an unfenced shell, not a fence, so the run record is what makes a refusal visible.
- **Row 4, a write outside the allowance is granted only where the affirmed brief names it** (the owner's ruling, over the holder granting a write it judges reversible). In a product repository a pushed branch can start workflows or a deploy that deleting the branch doesn't undo.
- **Row 5, Codex gets the instructions and environment, and the check where Codex can carry it.**

## Calls made inside the rows

- **The use consumer keeps `--safe-mode`; its check rides `CLAUDE_CODE_SHELL_PREFIX`.** A spike showed settings hooks do not run under `--safe-mode`, but the prefix does. Dropping `--safe-mode` would change what the use consumer loads, outside every row.
- **A child must start with `--setting-sources user --settings "$TRADECRAFT_CHILD_SETTINGS"`.** Without it, a child loads the product tree's project and local settings, where `disableAllHooks` or an `env` block could turn its check off. `--safe-mode`, `--bare`, `CLAUDE_CODE_SIMPLE`, a second or inline `--settings`, `env -i`, and a connector change are refused by name.
- **"Push credential" means git's credential.** The `gh` login stays, because many reads need it, and the check refuses `gh` writes. It is removed only when the allowance, grants included, permits no push, because a grant git cannot carry out grants nothing.
- **A refusal is reported, not held.** It fails the command and lands in the run record and every entrance and release report; it changes no outcome and needs no launch account.
- **A here-document body is data unless a shell reads it.** A builder's commit and persist routes pass whatever their message names; a shell reading a here-document, and a substitution bash would run, are still judged.
- **The persist-changes push runs inside Python and is unseen.** It is the builder's own-branch push, and the script gap row 3's reason accepts.
- **The allowance command takes the stage as a positional argument** and reads the branch from the implementation tree, because the entrance's stage is already positional.
- **Codex stays on the not-supported branch.** A spike on `codex-cli 0.167.0-alpha.3.2` found the rules language works (`codex execpolicy check --rules <file> git push origin x:y` decides `forbidden` for a `prefix_rule(["git","push"], forbidden)`), but no source a launch can supply for one run: the app-server protocol schema has no rules-path key, `-c` accepts unknown keys without error so cannot confirm one, and the binary loads rules only from user or project `.rules` files and `requirements.toml`. Each means writing into the product tree, the owner's Codex home or the machine's policy. So a Codex launch's own commands go unchecked and its run record says `not-run` with the version; a Claude session it starts carries the same child settings and is checked.

## Rejected

- **Instructions alone**, and **the artifact author alone** (the owner's rulings).
- **The holder granting a write it judges reversible** (the owner's ruling).
- **A check of GitHub after each run** for a write that got around the command check: not in the brief.
- **A per-launch `CODEX_HOME`** to carry Codex rules: it would lose the owner's Codex login.

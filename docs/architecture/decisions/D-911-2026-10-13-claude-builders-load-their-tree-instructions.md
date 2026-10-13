# Claude builders load their own tree's instructions (#893)

**Purpose:** retain why a Claude author or builder now starts with its tree's root instructions loaded by the runtime, and what was tried and rejected. **Audience:** maintainers of the implementer launch and adopters reading its records. **Success:** a maintainer can change the route knowing what each alternative cost and how each criterion was checked.

The owner bought #893 and affirmed narrowing it to guaranteed delivery ("1", then "affirm", 2026-10-12). Before it, a Claude launch excluded project sources (`--setting-sources user`, D-786's guard against the holder hook) and the entrance's preamble only asked the builder to read "the repository root instructions and applicable ancestor and nested instructions". Delivery rested on that sentence, the files sat in the conversation as something read early, and nothing recorded them; from a tree nested in the holder checkout, "ancestor" also reached the holder's copy from another commit. A Codex builder's runtime loads its tree's `AGENTS.md`. The settled artifact is [6140231341](https://github.com/Grimblaz-and-Friends/tradecraft/issues/893#issuecomment-6140231341); it amends D-786 only by adding delivery.

## The route

- **Native delivery.** Every Claude launch adds `--add-dir <its working tree>` and the child sets `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`, with `--setting-sources user` unchanged. Fresh launches, resumes, repairs and Codex-to-Claude handovers all build through `build_command` in `lib/dispatch_implementer.py` and the child environment from `lib/implementer_policy.py`. The runtime loads the tree's root `CLAUDE.md` (or the one under its `.claude` directory) and its `.claude` rules with their imports; it loads no project hook, setting, skill, command, agent or output style, and no `CLAUDE.local.md`.
- **The `AGENTS.md` fallback** (the holder's call inside row 1). A tree with no root `CLAUDE.md`, in either place, but with `AGENTS.md` gets a one-line shim `CLAUDE.md`, added with a second `--add-dir`: first in `<git dir>/tradecraft-instructions-<dispatch id>/` with a relative import, else in the invocation's temporary directory with an absolute one, spaces escaped `\ `, removed when the invocation ends.
- **Call 5, `#` in both import paths** (the holder's ruling): the launcher refuses the Claude launch before any bundle or process, naming the tree. Writing the shim into the working tree (rejected: a launcher file the builder can see and commit) and expanding imports into `--append-system-prompt-file` (rejected: reimplements import rules and depends on prompt snapshots on resume) were the other options.
- **The record.** Claude's `init` carries no instruction inventory on 2.1.280, but the session transcript carries `{"type":"attachment","attachment":{"type":"instructions","files":[{path,type,content}]}}`. `claude_instructions` in `lib/implementer_environment.py` reads it after the run: path, runtime type, `sha256` and `bytes` of the recorded content, `delivered` against the transcript's pre-launch length, and `launcher_shim`; `known` fresh, `partial` on resume, `unknown` with its reason otherwise. The entrance's `implementer_environments` repeats it per attempt as `instructions`.
- **The preamble** now says the root instructions are already loaded, sends the builder to applicable `CLAUDE.md` or `AGENTS.md` inside its tree, and tells it not to read instruction files above the tree.

**Rejected routes.** `--setting-sources user,project` ran the project hook and loaded tree skills, commands, agents and output style. `--append-system-prompt-file` with launcher-expanded imports reimplements the runtime and freezes on resume under `--system-prompt-snapshot`. `--bare` drops OAuth, hooks and auto-memory, which #886 retains.

## Evidence

Spikes before the artifact (Claude Code 2.1.280, throwaway trees, tools off so a phrase could arrive only as loaded context), summarised from the settled artifact:

| Arm | Delivered |
|---|---|
| Today's flags | no tree phrase |
| `--add-dir` + variable | root, `AGENTS.md`, import, import-of-import; no holder, nested or `CLAUDE.local.md` phrase; hook never ran |
| `user,project` | the same plus the hook marker and tree skills, commands, agents, style |
| Shim, temporary directory, absolute import | spaces only when escaped `\ `; `é`, `(`, `'` raw; `#` in no form |
| Shim, git directory, relative import | delivered for ` #` in a normal checkout and for a linked worktree under `Hold #2 é y`; `git status` clean in both trees |
| Resume with route / without | new and changed imports delivered / neither |

**Row 2's open edge (holder reading 1).** A settings-declared `permissions.additionalDirectories` might also have its `CLAUDE.md` loaded under the new variable. A flag-scope arm (`--settings` declaring a directory whose `CLAUDE.md` carries a canary) held only the tree's phrases, with and without the variable. A discriminating arm confirmed the setting was in force: the same launch with `Read` allowed in default permission mode read that directory's file, and without the setting the read was denied. A second `--add-dir` to the same directory did deliver its canary, so the canary was loadable. The edge did not hold; no neutralisation was added. A user-scope variant was not run, to keep the owner's `~/.claude` untouched; settings scopes merge into the same permission context.

**Build checks, at this change's launch code** (Haiku 4.5 canary arms, tools off unless stated; about $0.47 at list across the edge arms and these):

- **C1.** Today's flags held no phrase; the new launch held the four tree phrases and none from the holder, a nested `CLAUDE.md` in a subdirectory or `CLAUDE.local.md`. Its record read `known`: the user `CLAUDE.md` and the four tree files.
- **C2.** `space dir/tree one`, `a #1 b`, `café (x86) o'k` and a linked worktree under `Hold #2 é y` each held `AGENTS.md`'s phrase and its import's, with the shim in the git directory recorded `launcher_shim: true`; trees clean afterwards, the linked holder's own canary absent.
- **C3.** Two fresh sessions; between runs a canary was added to an imported file and a new import added. The resume built by `build_command` held both new phrases and recorded `partial`, the changed files `this-invocation`; a control resume of the other session without the route held neither.
- **C5.** Opus 5.5 at high through `dispatch_implementer.py` in a worktree whose committed `.claude/settings.json` carries a refusing `PreToolUse` hook and a marker-writing `SessionStart` hook wrote and committed a file, with no denial and no marker.
- **C9.** With tools on, the new launch's `init` listed no tree skill, command, agent or output style and held none of their phrases; the `user,project` control listed all four kinds and wrote the only marker line.

No raw run output is retained; the throwaway trees were removed.

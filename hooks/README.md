# hooks

One hook: `SessionStart` runs `emit_charter.py`, which prints the body of the
`charter` cell on stdout, so a session in a repository that has installed this
plugin holds the practice's binding rules before it acts. The cell is the same
file a session can invoke by name — one file, two doors — and the emitter
strips its frontmatter, which is addressed to the runtime's skill index rather
than to a reader. Without it a consumer receives the
skills and no doctrine unless it asks for the charter cell by name — a plugin's
root `AGENTS.md` and `CLAUDE.md` land
in the install cache but are never loaded as context, which the vendor's own
plugin validator says in as many words.

**Why a script rather than `cat`.** `cat` was the first shape and it failed three
ways that only a Windows adopter would have seen. Under `powershell.exe` 5.1 —
the interpreter Claude Code falls back to when Git Bash is absent, which is the
default Windows state — `cat` is an alias for `Get-Content`, which reads a
BOM-less UTF-8 file as ANSI: every em dash and curly quote in the charter arrived
corrupted. `Get-Content`'s `-Path` is wildcard-interpreted, so a `[` anywhere in
the plugin cache path made the read fail. And it failed at **exit 0 with empty
stdout** — which, against the runtime contract "exit 0: stdout is shown to the
model", is indistinguishable from a hook that deliberately emitted nothing. The
script decodes explicitly, opens by literal path, and exits non-zero with a
reason on stderr.

**What that trade cost, stated rather than dropped.** `cat` needed no interpreter
on PATH. `python` does, and it is absent on Linux installations that carry only
`python3` — there the hook exits 1 having emitted nothing, and because a
non-zero `SessionStart` hook shows stderr to the user and never to the model, the
session proceeds with no doctrine and no signal that any was expected. CI does
not close this: `actions/setup-python` puts `python` on both runners' PATH, so
the matrix cannot see the case. What the source repository does check is that
the declared command runs at all: its portability suite executes this command
and compares the output to the charter byte for byte, so the hook cannot rot
silently in the environments that suite does cover.

**Why plain stdout rather than the JSON envelope.** Both runtimes accept either:
Claude Code adds plain stdout as context for `SessionStart`, and so does Codex.
Plain text has one fewer thing to get wrong. Two upstream reports bear on the
choice and are named so a later session can check them rather than trust this
paragraph: [anthropics/claude-code#12151](https://github.com/anthropics/claude-code/issues/12151)
(open) reports plugin-sourced `SessionStart` output not reaching context, with
its most recent evidence specific to the `additionalContext` envelope; and
[#53682](https://github.com/anthropics/claude-code/issues/53682) contains a
reproduction in which a plugin hook emitting **plain stdout** did reach the
agent's context, while a malformed bare-`{additionalContext}` hook did not. If a
runtime later requires the envelope, that is a change to `hooks.json`, not to the
charter.

**Why `${CLAUDE_PLUGIN_ROOT}` is lawful here** when a shipped calling contract may
not name it: this is hook configuration, which is where the token actually
expands. Claude Code substitutes it as a path placeholder before any shell sees
the command, on every platform; Codex sets it as an environment variable,
explicitly for compatibility with plugins written against it, which works
wherever its hook shell expands one — and not on Windows (below).

**Known gap: Codex on Windows.** Codex runs a plugin hook through `cmd.exe /C`
and delivers the root as an environment variable rather than substituting it, so
`${CLAUDE_PLUGIN_ROOT}` is passed through literally and the command cannot
resolve. No single command string serves both a textual placeholder and a
`%VAR%`-style environment variable, so this hook does not deliver the charter to
a Windows Codex adopter. Claude Code on Windows is unaffected, because it
substitutes before any shell runs. An adopter in that quadrant gets the skills
and can invoke the charter cell by name, which is the same file this hook reads
out and the reason the charter ships as a cell at all.

**Trust.** Claude Code gates plugin hooks on workspace trust plus the
`disableAllHooks` setting; there is no per-plugin, hooks-only decline, so an
adopter who does not want this hook declines the plugin. Codex does have
hook-level trust and reviews a plugin's hooks before arming them.

# hooks

One hook: `SessionStart` emits `charter/CHARTER.md` on stdout, so a session in a
repository that has installed this plugin holds the practice's binding rules
before it acts. Without it a consumer receives the skills and no doctrine at all
— a plugin's root `AGENTS.md` and `CLAUDE.md` land in the install cache but are
never loaded as context.

**Why `cat` rather than a script.** The substrate rule governs code this practice
writes; the cheapest reliable material here is to write none. `cat` needs no
interpreter on PATH — `python` is absent on many Linux installations that carry
only `python3`, and a hook that names the wrong one fails silently in exactly the
environments this change exists to serve. `cat` resolves on POSIX shells and is
an alias for `Get-Content` in PowerShell, which is the shell Claude Code uses on
Windows when Git Bash is absent.

**Why plain stdout rather than the JSON envelope.** Both runtimes accept either:
Claude Code adds plain stdout as context for `SessionStart`, and so does Codex.
Plain text has one fewer thing to get wrong, and a report of plugin-supplied
`additionalContext` being dropped was closed as not planned, so the envelope is
not the safer path. If a runtime later requires the envelope, the change is to
this file's command, not to the charter.

**Why `${CLAUDE_PLUGIN_ROOT}` is lawful here** when a shipped calling contract may
not name it: this is hook configuration, which is one of the three places the
token actually expands. Claude Code substitutes it as a path placeholder before
the shell sees the command; Codex sets it as an environment variable, explicitly
for compatibility with plugins written against it.

**Trust.** Both runtimes require a one-time approval before a plugin's hooks run.
An adopter who declines still gets the skills; they do not get the charter.

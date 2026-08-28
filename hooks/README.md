# hooks

One hook: `SessionStart` runs `emit_charter.py`, which sends the body of the
`charter` cell through the runtime's model-context output, so a session in a
repository that has installed this plugin holds the practice's binding rules
before it acts. The cell is the same file a session can invoke by name — one
file, two doors — and the emitter strips its frontmatter, which is addressed to
the runtime's skill index rather than to a reader. Without it a consumer receives the
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
the declared command runs at all: its portability suite executes each runtime
form and compares the context it carries to the charter byte for byte, so the
hook cannot rot silently in the environments that suite does cover.

**Why two output forms.** Claude Code receives plain stdout. Codex receives the
documented `hookSpecificOutput.additionalContext` JSON envelope, selected by
Codex's plugin-specific `PLUGIN_ROOT` environment variable. Codex documents
plain `SessionStart` stdout as model context too, but CLI `0.150.0-alpha.8`
logged the installed hook starting and completing without giving that text to
the model. An isolated [Sol/high spike](https://github.com/Grimblaz-and-Friends/tradecraft/issues/24#issuecomment-5448061498)
proved the JSON envelope reaches context in the same runtime. The adapter lives
in the emitter, not the charter; `additionalContextLimit` stays above the
charter's enforced size budget so Codex cannot silently replace it with a
truncated preview.

**Why the root tokens are lawful here** when a shipped calling contract may not
name one: this is hook configuration, where the runtime supplies the plugin
root. Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` in the default command
before a shell sees it. Codex selects `commandWindows` on Windows and supplies
`PLUGIN_ROOT` to `cmd.exe`, which expands `%PLUGIN_ROOT%`; Codex also sets the
Claude-named variable for plugin compatibility. Both commands invoke the same
emitter and therefore deliver the same charter, in the output form their runtime
actually carries; the portability suite runs both Windows paths from an
installed-looking root and compares their delivered context byte for byte.

**Trust.** Claude Code gates plugin hooks on workspace trust plus the
`disableAllHooks` setting; there is no per-plugin, hooks-only decline, so an
adopter who does not want this hook declines the plugin. Codex does not
automatically trust an installed plugin's hooks: open `/hooks`, inspect this
command, and trust it before expecting the charter at `SessionStart`.

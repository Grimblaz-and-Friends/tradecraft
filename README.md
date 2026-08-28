# tradecraft

A house engineering practice for frontier models.

The models write the code. Tradecraft is what makes it engineering: the standards, memory, and judgment structure that turn raw capability into work you can trust — portable across vendors, compounding with use.

## What this is, in one elimination

Anything that is a *capability* — orchestration, subagents, planning modes, memory primitives, review commands — the vendors will eventually ship better than anyone can wrap it. Tradecraft deliberately contains none of that. It contains what a vendor will never ship, because it isn't theirs to know:

- **Standards** — what counts as evidence, what "done" must be true of, what a finding turns into.
- **Judgment economics** — which decisions belong to the human, structured as gates; everything else structured to cost them nothing.
- **Compounding** — lessons become guards, guards earn or retire process. A raw session is brilliant and amnesiac; this system gets better with use.
- **Vendor independence** — the practice sits above Claude and Codex and survives switching between them.

## How it's built

The unit of everything is the **skill**: a self-contained cell carrying whatever mix of prose (methodology), code (contracts), and tests its job requires. Skills never depend on each other sideways, with one exception the `authoring` cell states in full: any cell may name the charter, and it may name any cell, because it is already loaded before any of them fire. The plugin is just the bundle they ship in.

Content lives in three homes ([D-74](docs/architecture/decisions/D-74-2026-08-19-constitutional-reset.md)): the **doctrine** — the practice's binding half in [the charter](skills/charter/SKILL.md), a cell that ships, and this repository's own mechanics in [AGENTS.md](AGENTS.md), which does not — the **skills** (methodology, plus the charter itself, which is a cell so that a session can pull it deliberately), and the **[decision log](docs/architecture/decisions/)** (frozen rationale that informs, never binds). Every governing document states its purpose, audience, and success criteria, and its review judges against that statement — the review practice itself is the `adversarial-review` skill. Each review appends one row to [docs/reviews.jsonl](docs/reviews.jsonl); records are append-only exhaust, never maintained.

## Install it

Tradecraft is a plugin. Installing it gives your repository the skills and the
practice's binding rules; it is the same package in both runtimes, because Codex
reads Claude's plugin manifests by name.

**Claude Code**

```
claude plugin marketplace add Grimblaz-and-Friends/tradecraft --scope project
claude plugin install tradecraft@tradecraft --scope project
```

**Codex**

```
codex plugin marketplace add Grimblaz-and-Friends/tradecraft
codex plugin add tradecraft@tradecraft
```

`--scope project` writes `extraKnownMarketplaces` and `enabledPlugins` into your
repository's `.claude/settings.json`, so the declaration is checked in and the
content is not. Omit it and the CLI defaults to `user` scope, which arms the
plugin — and its session-start hook — in *every* repository on that machine.
Codex installs at user scope by design, with the same consequence: a repository
cannot auto-install a plugin by committing configuration.

What a teammate gets from cloning a repository that carries only the checked-in
declaration is not something we have measured; every CLI surface we tried
refused to act on the declaration alone. Treat the two commands above as the
supported path for each person, not as something one person does for a team.

**Pinning.** `version` in `plugin.json` is the pin that works today: an adopter
receives an update only when we bump it. Marketplace sources also accept a `ref`
(a branch or tag), and Codex takes `--ref` on `marketplace add` — but Claude
Code's `plugin marketplace add` exposes no flag for it, so setting one means
editing the marketplace entry by hand. A commit `sha` pins *plugin* sources, not
marketplace sources, and this plugin's source is a relative path, so `sha` does
not apply to it at all.

**What lands in your session.** Every skill's name and description sit in every
session's context — about 1,060 tokens for the eight methodology cells, plus
about 140 for the charter — and each skill's body loads only when it fires. One of
those skills is the charter itself, so wherever the hook below does not reach
you, a session can still be asked for the practice's rules by name. On top of that,
the plugin ships one `SessionStart` hook, which emits [the charter](skills/charter/SKILL.md)
— about 1,000 tokens of binding rules — so the practice governs rather than
merely being available. That matcher is match-all, so the charter is re-emitted
on resume, clear, compact and fork as well as at startup: budget per
`SessionStart` event, not per session, and expect a long compacting session to
pay it several times.

Note that `claude plugin details` gets the cost wrong in your favour: it reports
the always-on figure as skills only, and annotates the hook `(harness-only — no
model context cost)`. The hook does cost you context.

**One more thing that can go wrong.** The hook runs `python`. On a Linux host
that carries only `python3` it will exit without emitting, and a failed
session-start hook reports to you, not to the model — so the session simply
proceeds without the charter. If `python -V` does not work on your machine, this
plugin's hook gives you nothing. The charter is itself one of the skills, so a
session can still be asked for it by name — but that is availability, not
governance: nothing announces the absence to the model, so someone has to know
to ask.

**On declining the hook.** Claude Code gates plugin hooks on workspace trust and
the `disableAllHooks` setting; there is no supported way to take this plugin's
skills while declining its hook. Codex keeps hook trust separate from plugin
installation: after installing, open `/hooks`, inspect the command, and trust it
before expecting the charter at `SessionStart`. On Windows Codex selects the
plugin's `commandWindows` arm, where `cmd.exe` expands the supplied
`%PLUGIN_ROOT%`; Claude Code continues to use the default placeholder command.
Both arms invoke the same emitter and deliver the same charter. Claude Code
receives plain stdout; Codex's plugin-specific environment selects its
`hookSpecificOutput.additionalContext` JSON envelope, which works around a
plain-output delivery defect observed in CLI `0.150.0-alpha.8`.

**Re-run the Codex compatibility check.** First install this tree's plugin
version, open `/hooks`, inspect its command, and trust it. Then, from a host
shell with an authenticated Codex CLI and a real `python` interpreter, run:

```
python tools/check_codex_compat.py
```

The check records the resolved Codex executable and version, the installed
plugin version, and the explicitly selected model, reasoning effort, read-only
sandbox, and ephemeral session. It launches from an empty consumer directory,
so the charter cannot arrive through this repository's `AGENTS.md`. On Windows
it can find the Codex app-bundle executable even when `codex` is absent from
`PATH`; `--codex PATH` pins an exact executable on any platform.

**What does not reach you, by design.** Everything under `docs/`, `tools/`, and
`.github/` is this repository's own machinery. A git-source install clones the
whole repository, so those files do arrive in your plugin cache, but nothing
shipped references them and nothing you use should.

## Status

Installable and proven in a consumer repository (2026-08-24), by running it: the install path, skill discovery and hook registration; both shipped scripts from the installed cache; the declared hook command emitting the charter byte-for-byte; and — in an attended session in that repository — the charter arriving in the session's context from the hook, and the `charter` cell invocable by name. Before that, reset complete (2026-08-19): the doctrine, the shipped skills (`persist-changes`, `adversarial-review`, `authoring`, `engagement`, `filing`, `spikes`, `experience-session`), and the packaging lint with Linux + Windows CI. The pre-reset constitution — a twelve-section statute over a frozen nine-ADR preamble — is a frozen archive under [docs/architecture/](docs/architecture/), and its records sit beside it in [docs/ledger.jsonl](docs/ledger.jsonl) (869 defect rows) and [docs/seat-record.jsonl](docs/seat-record.jsonl): all readable history, never binding.

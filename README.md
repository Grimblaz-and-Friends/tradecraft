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

Tradecraft is one plugin package for both runtimes. Installation makes its nine
skills available; repository adoption makes the charter binding.

**Claude Code**

```sh
claude plugin marketplace add Grimblaz-and-Friends/tradecraft --scope project
claude plugin install tradecraft@tradecraft --scope project
```

**Codex**

```sh
codex plugin marketplace add Grimblaz-and-Friends/tradecraft
codex plugin add tradecraft@tradecraft
```

`--scope project` writes `extraKnownMarketplaces` and `enabledPlugins` into your
repository's `.claude/settings.json`, so the declaration is checked in and the
content is not. Omit it and the CLI defaults to `user` scope. Codex installs at
user scope by design. In either runtime a repository cannot auto-install a
plugin by committing configuration.

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

## Adopt it in a repository

Put the following in the repository's canonical `AGENTS.md`:

```md
## Tradecraft

Before substantive action, load and read the installed `tradecraft:charter`
skill completely. If it is unavailable, stop and tell the owner that Tradecraft
is not installed or enabled.
```

Claude Code can consume the same instruction through a root `CLAUDE.md` whose
first non-empty line is `@AGENTS.md`. Codex reads `AGENTS.md` directly. A future
runtime joins the same flow by reading `AGENTS.md` natively or through a
zero-logic pointer; a runtime that supports neither is not currently supported.

This distinction is deliberate: installation is availability, not adoption.
Every skill's name and description can be present while no instruction makes
the practice govern the session. The repository instruction closes that gap and
fails loudly when the plugin or charter is unavailable. There is no lifecycle
hook, copied charter, global instruction, or second plugin manifest to keep in
sync.

**Re-run the Codex compatibility check.** First install this tree's plugin
version. Then, from a host shell with authenticated Codex and a real `python`
interpreter, run:

```sh
python tools/check_codex_compat.py
```

The check records the resolved Codex executable and version, the installed
plugin version, and the explicitly selected model, reasoning effort, read-only
sandbox, and ephemeral session. It creates a temporary git repository outside
this source tree, writes only the adoption instruction above plus a random
sentinel to that repository's `AGENTS.md`, and proves the installed charter and
all nine complete descriptions reached the cold session. On Windows it can find
the Codex app-bundle executable even when `codex` is absent from `PATH`;
`--codex PATH` pins an exact executable on any platform.

**What does not reach you, by design.** Everything under `docs/`, `tools/`, and
`.github/` is this repository's own machinery. A git-source install clones the
whole repository, so those files do arrive in your plugin cache, but nothing
shipped references them and nothing you use should.

## Status

Installable as one shared plugin in Claude Code and Codex. Repository adoption is explicit through canonical `AGENTS.md`; Claude's root pointer reaches the same file, and the Codex compatibility check proves the native path in an isolated consumer repository. Before that, reset complete (2026-08-19): the doctrine, the shipped skills (`persist-changes`, `adversarial-review`, `authoring`, `engagement`, `filing`, `spikes`, `experience-session`), and the packaging lint with Linux + Windows CI. The pre-reset constitution — a twelve-section statute over a frozen nine-ADR preamble — is a frozen archive under [docs/architecture/](docs/architecture/), and its records sit beside it in [docs/ledger.jsonl](docs/ledger.jsonl) (869 defect rows) and [docs/seat-record.jsonl](docs/seat-record.jsonl): all readable history, never binding.

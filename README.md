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

The unit of everything is the **skill**: a self-contained cell carrying whatever mix of prose (methodology), code (contracts), and tests its job requires. Skills never depend on each other sideways. The plugin is just the bundle they ship in.

Content lives in three homes ([D-74](docs/architecture/decisions/D-74-2026-08-19-constitutional-reset.md)): the **doctrine** — the practice's binding half in [the charter](charter/CHARTER.md), which ships, and this repository's own mechanics in [AGENTS.md](AGENTS.md), which does not — the **skills** (all methodology), and the **[decision log](docs/architecture/decisions/)** (frozen rationale that informs, never binds). Every governing document states its purpose, audience, and success criteria, and its review judges against that statement — the review practice itself is the `adversarial-review` skill. Each review appends one row to [docs/reviews.jsonl](docs/reviews.jsonl); records are append-only exhaust, never maintained.

## Install it

Tradecraft is a plugin. Installing it gives your repository the seven skills and
the practice's binding rules; it is the same package in both runtimes, because
Codex reads Claude's plugin manifests by name.

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
content is not. Codex installs at user scope by design — a repository cannot
auto-install a plugin by committing configuration.

**Pinning.** The marketplace entry takes `ref` (a branch or tag) and `sha`; when
both are set the `sha` wins. `version` in `plugin.json` pins the plugin itself,
so an adopter receives an update only when it is bumped. Codex takes `--ref`.
Pin if you want the practice to change on your schedule rather than ours.

**What lands in your session.** Seven skill descriptions sit in every session's
context; each skill's body loads only when it fires. On top of that, the plugin
ships one `SessionStart` hook, which emits [the charter](charter/CHARTER.md) —
roughly 1,100 tokens of binding rules — into each session, so the practice
governs rather than merely being available. Both runtimes ask you to trust a
plugin's hooks once before they run; decline and you still get the skills, but
not the charter. Note that `claude plugin details` gets this wrong in your favour: it reports
the always-on figure as skills only, and annotates the hook
`(harness-only — no model context cost)`. The hook does cost you context.
Budget for the skill descriptions plus the charter, not for the number the
CLI prints.

**What does not reach you, by design.** Everything under `docs/`, `tools/`, and
`.github/` is this repository's own machinery. A git-source install clones the
whole repository, so those files do arrive in your plugin cache, but nothing
shipped references them and nothing you use should.

## Status

Installable and proven in a consumer repository (2026-08-24). Before that, reset complete (2026-08-19): the doctrine, seven shipped skills (`persist-changes`, `adversarial-review`, `authoring`, `engagement`, `filing`, `spikes`, `experience-session`), and the packaging lint with Linux + Windows CI. The pre-reset constitution — a twelve-section statute over a frozen nine-ADR preamble — is a frozen archive under [docs/architecture/](docs/architecture/), and its records sit beside it in [docs/ledger.jsonl](docs/ledger.jsonl) (869 defect rows) and [docs/seat-record.jsonl](docs/seat-record.jsonl): all readable history, never binding.

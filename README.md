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

The constitution — the small set of decisions everything else answers to — lives in [docs/architecture/adr/](docs/architecture/adr/). Start with [ADR-001](docs/architecture/adr/ADR-001-identity.md).

## Status

Pre-skeleton. The constitution is being drafted and argued; no shippable skills exist yet.

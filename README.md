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

Content lives in three homes ([D-74](docs/architecture/decisions/D-74-2026-08-19-constitutional-reset.md)): the **doctrine** ([AGENTS.md](AGENTS.md), one budgeted page of binding rules), the **skills** (all methodology), and the **[decision log](docs/architecture/decisions/)** (frozen rationale that informs, never binds). Every governing document states its purpose, audience, and success criteria, and its review judges against that statement — the review practice itself is the `adversarial-review` skill. Each review appends one row to [docs/reviews.jsonl](docs/reviews.jsonl); records are append-only exhaust, never maintained.

## Status

Reset complete (2026-08-19): the doctrine, three shipped skills (`persist-changes`, `adversarial-review`, `authoring`), and the packaging lint with Linux + Windows CI. The pre-reset constitution — a twelve-section statute over a frozen nine-ADR preamble — and its records ([docs/ledger.jsonl](docs/ledger.jsonl), 869 defect rows; [docs/seat-record.jsonl](docs/seat-record.jsonl)) are a frozen archive under [docs/architecture/](docs/architecture/): readable history, never binding.

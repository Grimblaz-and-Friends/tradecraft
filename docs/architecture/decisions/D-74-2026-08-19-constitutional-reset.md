# D-74: The constitutional reset

**Status:** Accepted 2026-08-19 (PR #74)

## Context

Five days after the repo's first review, governance outweighed the product it governed by roughly 4× and the constitution's share of all review findings had climbed from 21% to 66% (measured in [#70](https://github.com/Grimblaz-and-Friends/tradecraft/issues/70)). The owner's diagnosis, developed in the conversation behind [#73](https://github.com/Grimblaz-and-Friends/tradecraft/issues/73): the review pipeline validated whether findings were *true* but nothing validated whether they *mattered* to a document's purpose; the statute was the only writable home for a norm, so every relief arrived as more law; and the ledger's per-finding resolution was far finer than the monthly-grade decisions it fed, making the record itself a workload. The seats' individual yields were real — the instrument was sharp and aimed at the wrong target.

## Decision

Replace the statute and its machinery with three content homes and a purpose-anchored review:

- **Doctrine** (`AGENTS.md`, one page, budget-enforced): binding always-on rules and this repo's mechanics. The owner's decisions outrank it; a session argues merits, never refuses by rule-citation. New requirements take the cheapest reliable material first: platform/CI mechanism → skill prose → doctrine line. Agent-proposed rules need an incident from real work; a review finding about governing prose is not an incident.
- **Skills**: all methodology, including a new `authoring` skill carrying the purpose/audience/success header standard and content routing.
- **Decisions** (this log): frozen rationale that informs and never binds — superseded by being read, not obeyed. Entries take this lighter shape; `check_constitution.py` and the fixed entry skeleton retire.

The review is re-chartered (in `skills/adversarial-review`): every review judges against the artifact's stated purpose, audience, and success criteria; a finding names the criterion it impairs; deletions have equal standing with additions; net growth of governing prose is itself a finding; the terminal question is fitness for purpose, which can be *yes* while true findings stand.

Records become exhaust: `docs/ledger.jsonl` and `docs/seat-record.jsonl` are frozen as history, replaced by `docs/reviews.jsonl` — one row per review, validated by the lint, never maintained after its append. A PR whose only content is record bookkeeping is the tripwire that deletes the record it books.

Ceremony survives at exactly two moments — convergence and release — because both prior systems failed the same way: any fixed procedure attached to a high-frequency activity accretes. `CODEOWNERS` flags doctrine changes for the owner's merge-time review, as a platform mechanism rather than a prose rule.

## Superseded

The statute (`docs/architecture/constitution.md`), the nine frozen ADRs, and decision entries D-53 through D-69 are a frozen archive from this decision forward: readable history, never binding. Rules that carried forward into the doctrine did so by restatement there, not by reference. The trial road, the trivial floor and its canonical rebuttal forms, the ledger vocabularies, the `owner-pending` machinery, and the fixed decision-entry skeleton end here without replacement. Also ending without replacement, named so no ending is silent: the repo-only-doc lesson home; the rule that going below the review default is bought only by evidence, never argument; the interaction charter's non-gate rules (never-ask-what-you-can-look-up among them); and the condition that shipped-zone https pointers into this repository are lawful only while it is public.

## Rejected

- **Amending in place**: the empirical record showed amendments grew the statute on every simplifying PR.
- **A product-work moratorium alone**: delays the mess without changing the structure that produces it.
- **Exempting governing prose from agent review**: avoids the disease; re-chartering the review treats it.

## Evidence

[#70](https://github.com/Grimblaz-and-Friends/tradecraft/issues/70) (the measurements), [#73](https://github.com/Grimblaz-and-Friends/tradecraft/issues/73) (the affirmed pre-implementation artifact and its acceptance criteria).

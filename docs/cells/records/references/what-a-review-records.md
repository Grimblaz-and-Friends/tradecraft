# What a review records

**Loaded when** you are recording a review's outcome — appending its row, appending an entry for a ruling of `record`, or reading either back.

Every review appends one row to `docs/reviews.jsonl`, and every `record` ruling one entry to `docs/recorded-findings.jsonl` **and nothing else — no filing into the pool**. The entry is the review's accounting and what the next review's dispatch fetches. Neither is maintained afterwards, and rows already written are not migrated: an entry carrying an `issue` from when the ruling also filed one keeps it, that filing having happened, and what moved is where a ruling goes from now, not what the record holds. Beyond the fields the practice's own `the-record.md`, in the `adversarial-review` cell, names, a row here carries one more field, `cost`, and one more key on each entry of `highs`.

**`cost` — what the review took to run**, as `{"dispatches": n, "subagent_tokens": n}`.

- **`dispatches`** counts every subagent **the review** dispatched: its seats, its defense, and its judge. **Not counted:** the convergence rounds and the cold seat that settles the artifact, spikes, experience sessions — including the one a fix batch buys, which the review dispatches but which is the change's cost — and a commissioned pass, which that cell's `after-the-fix.md` defines by provenance rather than by calling mechanism — so whether it dispatches agents of its own is not settled there, and it is excluded on the same ground as the rest. The row's subject is the review's own staffed stages, which is what the exclusions turn on — not on whose cost the excluded thing is. A spike the terminal stage commissions is dispatched by the review and is still excluded, being a distinct instrument that reports on the work's issue.
- **`subagent_tokens`** sums what those same dispatches returned. It is `null` where the runtime does not report per-dispatch tokens — an abstention claiming nothing, where a zero would claim no subagent ran. **`dispatches` may not abstain**: a runtime that made dispatches can count them, so a null there is a figure withheld rather than one unavailable, and the guard rejects it.

**Both are read off tool returns and neither is ever estimated**; a figure reconstructed from a transcript is the thing this field exists to stop. It is evidence for the next lane choice and never a ceiling to come under.

**`target` — the surface each sustained high hit**, carried on the high itself: `highs` entries are `{"high": "...", "target": "..."}`. Read from the site the finding cites, exactly as its `arbitration.md` reads consequence shape, **and decided in this order, first match governing**:

1. **`record`** — this change's own paperwork, wherever it sits: its decision entry, its own index row, its pull request body, its commit message, its review report, its pre-implementation artifact and the brief that artifact carries. First, because the two of those that are in the tree sit in the repo-only zone and a zone test would swallow them. A row or entry landed by *earlier* work is not this change's paperwork and falls through.
2. **`shipped`** — what an adopter installs: the shipped zone `siting` names, or a generated mirror of it, which takes its source's label.
3. **`repo`** — everything else **in this tree**, by residue rather than by list, so every site in it has a lawful label.

**A site outside the tree that is not this change's own paperwork has no lawful value**, and the answer is to say so on the change rather than to invent one into a record nobody may correct.

A high citing sites of more than one kind takes the highest-reaching, `shipped` > `repo` > `record` — the same direction as `arbitration.md`'s rule that a finding citing both kinds is artifact-facing, and skewing against `record` for the reason [D-365] states.

**`target` and consequence shape are two values on one finding, read from the same site.** Shape asks whether the consequence lands on the work or on the record of having checked it; `target` asks which of the three surfaces above that site sits on. Neither is inferred from the other and neither is read from what the finding is *about* — `arbitration.md` forbids that for shape, and the same site rule governs here.

Booked per high rather than as counts because counts over findings are what could never be reconciled — `facing` is that failure on this record. [#357] [D-365]

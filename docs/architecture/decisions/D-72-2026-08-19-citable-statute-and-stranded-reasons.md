# D-72: The statute becomes citable, and five stranded reasons come home

**Status:** Accepted 2026-08-19 (PR #72)

## Context

[D-53](D-53-2026-08-18-log-and-statute.md) froze the nine ADRs and extracted their operative rules into the statute. [#68](https://github.com/Grimblaz-and-Friends/tradecraft/issues/68) was filed on the owner's observation that sessions kept reading and citing ADR-002 afterwards, and asked whether that was a defect or the design.

**It was neither, and the question was answered before it was asked.** §12's first rule already states the holding — *"a reader learns the rule from one place and its provenance from another"* — and §2 drew the same line before the split existed: *"a sweep deciding whether a rule is still load-bearing follows the pointer; a session applying the rule reads the reason and never needs to."* The record's roles are three, not two: applying, revising, sweeping. Acceptance criterion 8 of #42's artifact made *"a reviser with no instruction to read the cited entry"* a nonconforming run, and the design panel dismissed the objection to it at **MF34** — *"a reader told to 'read the cited entry' who finds a frozen ADR section reads that section, which is the obligation's evident discharge."* `AGENTS.md` is right as written and is not softened here.

Discovery then found two defects the question's framing did not predict. Neither was visible to any measurement over the tree; **both were surfaced by owner-supplied transcripts of live sessions**, and that is itself the reason the class went unnoticed — each looks identical to a lawful citation-follow from outside.

**The attribution gap.** §12 identifies a statute rule *by its bold lead-in*. There is no short identifier, so the only compact token on a rule is `[ADR-NNN:L]`, which names a frozen file. Prose wanting rule-level attribution reaches for it. The exhibit is a working session's own text, which switches granularity at exactly the point the statute stops offering an identifier: *"**§8** already defines severity as harm-if-unfixed"* and *"**§6** has already ruled…"* where a section suffices, then *"a boundary format under **ADR-002**"* and *"**ADR-002** opened admission-by-trial"* where a particular rule is meant. Both attributed rules are fully in force in the statute, at `[ADR-002:37]` and `[ADR-002:39]`. Nothing was misread. **57 sites outside the constitutional surfaces cited dead law as live authority** — 48 in guard messages, so a contributor's first contact with the constitution was a lint failure citing a document headed *"Nothing here is in force."*

**Stranded reasons.** §2 requires a rule's **reason** to stay inline, *"because a model reading mid-task will not follow a link and a rule whose point is invisible gets tidied away by whoever meets it next."* A six-part survey read all nine frozen ADRs against the statute: **~259 reason-grade clauses, 28 resident only in the preamble** — ~89% survival, so a bounded sweep and not a re-migration.

The mechanism is on the record. **MF23** (sustained high) demanded a completeness instrument for the migration because *"a **dropped** rule leaves nothing to name."* Errata **QF5** fixed its unit: *"the inventory's unit is the **bold-led claim, not the line** … or its line is marked non-rule."* The statute's rule unit *is* a bold-led item, so the instrument's positive coverage was rules, and everything else was discharged by marking a line non-rule — a set [PR #53](https://github.com/Grimblaz-and-Friends/tradecraft/pull/53)'s inventory comment never enumerates. **There was a rule-completeness check and no reason-completeness counterpart**, and §2's obligation attaches to clauses, most of which are non-bold prose. D-53's own account of ADR-003:33 surviving *"only because a drafter wrote it into a section it believed was not its home"* is the near-miss already in the record.

The losses cluster where non-bold prose is dense: `## Consequences` and `## Context` blocks — D-53's sweep of those was explicitly scoped to *"an operative only/never/entire"* — and paragraphs where a class statement was interleaved with its instance counts and the whole passage was compressed as evidence.

## Decision

**Statute delta:** §12 gains the reader-role split with the reviser's read obligation and a citation form for the statute's own rules; five reasons resident only in the frozen preamble are stated inline at the rules that turn on them; and the 57 tree sites citing frozen ADRs as live authority are re-pointed at the statute.

**No frozen rule is displaced.** Every reason landed here is an *extraction* in D-53's own sense — the frozen line stated it, the statute now states it too, and nothing the preamble says is superseded. The two §12 additions are newly minted rules. This is why no `Displaces:` line appears above, and it is stated rather than left to inference.

### What lands, and why each was chosen

**B1 — the statute becomes citable.** A rule is cited `§N`, or `§N "<bold lead-in fragment>"` where a particular rule is meant, reusing the disambiguator §12 already permits on ADR tokens. **No positional numbering is minted**, because a rule's identity is its bold lead-in and a scheme that renumbered on insertion would silently retarget every citation already taken — the hazard D-53 sustained as `PF2` and proved rather than computed.

**B2 — the sweep.** Guard message prefixes now name the section holding the rule: `zone-wall (§4)`, `sideways-dep (§3)`, `doctrine (§9)`, `doctrine-budget (§3)`, `ledger (§8)`, `seat-record (§8)`, `version-bump (§3)`. Guard *behaviour* is unchanged — these are message strings and their pins. `adversarial-review` takes the name form it already used for the statute. **`persist-changes` gains a route to live law it never had**: its only two constitutional pointers named frozen ADRs, it mentioned the statute nowhere, and §4's wall bars a path reference, so a consumer had no route at all. It now carries §4's lawful `https://` form.

**One citation is deliberately kept.** `check_version_bump.py`'s note that *"ADR-003 was corrected rather than the guard"* records an event that happened while ADR-003 was live. Re-pointing it would make a true historical statement false. The freeze moves where new history is born, not where old history lives.

**A5 — the five reasons.** Chosen on one line: these bite a session *applying* a rule, where no mitigation exists, because §2 says an applying session *"never needs to"* follow the pointer and §4's wall means a shipped-zone consumer never can.

1. **§9, substrate singularity** ([ADR-007:28]). §9 gave four *Python-specific* virtues, none of them an argument against a **second** substrate. A session asked whether one helper could be TypeScript found every stated reason satisfied or inapplicable, and nothing that refused.
2. **§4, packaging mechanics** ([ADR-004:17]). The statute said consumers must never *depend* on `docs/`; the frozen *"note honestly"* clause — repo-only files **do** reach a consumer's plugin cache as inert files — went with the extraction. Still current fact: `.claude-plugin/marketplace.json` carries `"source": "./"`.
3. **§6, the lens/vantage discriminator** ([ADR-006:48]). Two rules turn on the distinction and `vantage` occurred **once** in the whole statute, inside one of them. Any gap could be labelled a vantage gap and pass both as written.
4. **§10, what makes something a home** ([ADR-008:26]). §10's first rule listed four homes and barred a fifth with **no reason at all** — it answered *which four* and never *by what property*.
5. **§2, the instrument-expressiveness class** ([ADR-002:47]). Stated as its own rule unit, sibling to *"a count nobody can reproduce is not evidence for anything"* — which is the same shape of standard and reached the statute by the same route.

### The fifth, and why it is stated as a general rule rather than repaired in place

The class sentence appears **twice in the preamble, against two different instruments**: ADR-002:47 applies it to the trial road, ADR-006:122 to a ledger schema whose value set *"guaranteed"* its own verdict. Only the trial-road-scoped half travelled, as trial property 4's *"blocks a governing distinction written in a unit the instrument does not carry."* That does not reach a schema forcing its own answer, and **§8 — the section that *is* the instrument — carried none of it**: zero statute occurrences of `cannot express`, `guaranteed`, `variance` or `rigged`. Eight of ADR-006's twelve strandings cluster there; the statute carried every field contract and nearly every behavioural reason and dropped the self-skeptical layer above them.

Its trial-road instance is **not** repaired here, because [#67](https://github.com/Grimblaz-and-Friends/tradecraft/issues/67) / [PR #69](https://github.com/Grimblaz-and-Friends/tradecraft/pull/69) is already landing that fix — replacing the single re-read trigger with *"two events say something about the trial road."* Stating the class generally complements it and avoids the twin site D-53 fought to eliminate.

**This item is the best-evidenced in the set, and the only one observed rather than surveyed.** #67's session recorded that reading ADR-002 *"turned this from 'the properties are strict' into something more specific"* — the statute alone produced a weaker and less correct diagnosis, and the frozen class statement is what sharpened it. That is a **reason** by §2's own definition (*"the working principle a reader needs … to notice when it stops applying"*), not the evidence read it was first taken for. The instance count that followed was the evidence half, correctly behind the pointer.

### What is deferred, and the honest cost of deferring it

**The remaining 23 strandings are deferred to [#70](https://github.com/Grimblaz-and-Friends/tradecraft/issues/70)'s ruling**, not dropped, and are enumerated on #68 by ADR and line so the set stays auditable. They are deferred because landing them is pure statute growth, and #70 has opened the question of whether constitutional growth is currently priced correctly — 83% of all ledger findings are on prose, the constitution's share of findings ran 21% → 66% over four days, and governance outweighs the shipped zone by roughly 4×.

**The argument for deferring them is weaker than it first looked, and that is recorded rather than smoothed over.** The initial reasoning was that a reviser reads the frozen ADR anyway under criterion 8, so an amend-time stranded reason is half-mitigated. #67 shows the mitigation is *lossy*: the session did read it, but only after anchoring on the statute's incomplete version. It recovered; nothing guarantees the next one does, and a session that never feels the need to look never looks. **This is a priority ordering, not a safety argument.**

## Rejected

1. **Landing all 28 reasons in this change.** Rejected: a 28-site insertion plus a 57-site sweep is a bulk edit reviewed as one unit, so a reviewer could not affirm the governance rule without also affirming a long editorial pass — and it is the most statute growth at the moment #70 opened whether that growth is priced correctly.
2. **B1 and B2 alone, with no reasons.** Rejected by the owner: it is the cheapest option and the only one that shrinks the constitutional surface, but it leaves five sites where a session gets a wrong answer today, one of them observed in live work. B fixes attribution; it puts no missing reason anywhere.
3. **The null result** — record both classes, sweep neither. Rejected: #68 rightly named the null as a real outcome, and it stopped being available once the survey found two defects with named mechanisms, five wrong-answer sites, and 57 tree sites contradicting a landed rule.
4. **Minting positional rule identifiers (`§2.14`) to close the attribution gap.** Rejected: it reproduces the retargeting hazard that made D-53 choose the bold lead-in as identity, where an insertion silently moves every later rule's number under citations already taken.
5. **A guard for either class.** Rejected as premature under §2 — reason-completeness has recurred once, and §12 already assigns this kind of question to review: *"CI checks form, position and existence; review checks correspondence."* A guard on B2's recurrence is the lawful follow-up **if it recurs**, and is named here so the trigger is legible rather than forgotten.
6. **Softening `AGENTS.md`'s read-the-cited-decision instruction**, which #68 raised as a live possibility. Rejected on the record: it discharges acceptance criterion 8 and was blessed at MF34. What was missing was a statute home for the obligation, which this entry supplies.

## Evidence

- The work's issue, its two artifact revisions, the affirmation record, and the full enumeration of the 23 deferred strandings: [#68](https://github.com/Grimblaz-and-Friends/tradecraft/issues/68).
- The split this corrects the downstream surfaces of: [D-53](D-53-2026-08-18-log-and-statute.md), [#42](https://github.com/Grimblaz-and-Friends/tradecraft/issues/42), [PR #53](https://github.com/Grimblaz-and-Friends/tradecraft/pull/53) — MF11, MF23, MF25, MF34 and errata QF5 are all in that record.
- The session whose transcript is the stranded-reason exhibit, and which independently repairs the trial-road instance: [#67](https://github.com/Grimblaz-and-Friends/tradecraft/issues/67), [PR #69](https://github.com/Grimblaz-and-Friends/tradecraft/pull/69).
- The attribution-gap exhibit: the design conversation during preparation of [#40](https://github.com/Grimblaz-and-Friends/tradecraft/issues/40), quoted in #68's revision 2. #40 is itself an instance, filed as *"ADR-006 §4, which governs findings"* while this statute's §4 is Zones.
- The measurements that scope what is deferred, and the question they raise: [#70](https://github.com/Grimblaz-and-Friends/tradecraft/issues/70).
- The citation census this change is measured against, taken from the tree: 274 rule units, 248 citing frozen ADR lines only, 25 citing `[D-N]` only, 1 citing both, across 145 distinct frozen lines; 25 rules cite a line already displaced. The before-and-after figures are in PR #72's body.

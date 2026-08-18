# D-53: Split the constitution into a decision log and a statute

**Status:** Accepted 2026-08-18 (PR #53)

## Context

The nine ADRs were a hybrid: a record of decisions and the rulebook in force, in one set of documents. ADR-002 states the rules for that material — specification and its short inline reason stay inline, evidence goes behind a pointer, and demotion is as mandatory as promotion — and none had ever been exercised. No sweep existed, and its absence was silent: a session reading ADR-006 could not tell *nobody has swept* from *a sweep found nothing to move*.

The cost was on the record in the files themselves. A repair made in ADR-006 §3 alone left §5 stating the unqualified version of the same claim (`M5`, [PR #19](https://github.com/Grimblaz-and-Friends/tradecraft/pull/19)). §5's own text records a literal count that "was stale within the hour: eight rows landed between the read and the writing, and the figure shipped wrong in three places here and twice on the pull request." ADR-002's stated reason for the pointer rule — recited evidence "is long, it drifts, it cannot be checked from the prose anyway, and reciting it spends every session's context serving a reader who is not there" — went unapplied to the constitution's densest file.

The design phase ran five revisions and closed on 2026-08-18. Revision 1 proposed a consolidation pass within the hybrid and was rejected by the owner in favour of splitting the surfaces. Revisions 2 through 5 were shaped by a dedicated adversarial challenge of the design itself: a four-seat panel (69 raw → 39 sustained, 9 high), a post-fix cycle (21 surviving, 4 high), and a final look (15 filed, 1 high) — a monotone yield decline that is this repository's first de-escalation-grade evidence and is what the convergence declaration rests on.

## Decision

**Statute delta:** The nine ADRs freeze as a historical preamble and their operative rules are extracted into a single always-current statute at `docs/architecture/constitution.md`, whose rules cite the frozen line or decision entry that last shaped them; future constitutional change is a statute edit carried with a decision entry in `docs/architecture/decisions/`.

**Displaces:** [ADR-004:28], [ADR-006:61], [ADR-006:72], [ADR-006:92], [ADR-008:17]

The migration is meaning-preserving **except** for the enumerated carve-out class below. Each member is a rule change, dispositioned here rather than folded into the extraction, because a rule change smuggled in as restructure is the failure this entry exists to make impossible.

### The carve-out class, closed

1. **The amendment procedure.** The ADR index README's *Amending* section is retired with the surface that carried it. Its successor is the statute's §12: the log's entry shape, the freeze and supersession forms, the entry obligation, and the guard/review boundary. The evidence-naming obligation that section carried forward is preserved — it now lives in the entry format's `## Evidence` section rather than in a status line.
2. **The prose↔guard coupling** — [ADR-004:28] said *"when an ADR changes, any lint rule enforcing the old text changes in the same commit."* ADRs can no longer change, so the trigger could never fire. Rehomed as *when this statute changes*. **Its unit was deliberately not touched**: "in the same commit" stands, because changing it to the pull request is a second change inside one carve-out member and the class is closed. The commit-vs-pull-request inconsistency against §6's global unit is filed rather than fixed here.
3. **The lesson-home list** — [ADR-008:17] named *"an ADR amendment where it is constitutional"* as one of four homes. Rehomed as *a statute amendment with its decision entry*. The four-home shape and the *"no fifth home called 'memory'"* bar are unchanged.
4. **The vocabulary-growth path** — [ADR-006:72] and [ADR-006:92] grew `found_by`, positions and stages *"by amending this section."* Rehomed as *by a decision entry amending this section*, which is the same act under the new surfaces.
5. **`artifact: constitution` re-denoted.** The value denoted the ADR set. It now denotes all three constitutional surfaces — the statute, the decision log, and the frozen preamble. **One value rather than three**, on two grounds: 284 of 686 existing rows carry it, and re-denotation keeps every one of them true where minting `statute`/`decision-log`/`frozen-adr` would leave each ambiguous between the rulebook and the record its rules came from; and the vocabulary names a *kind* of material for right-sizing process, not a file, which the row's `ref` already identifies. The accepted cost is that a query for "defects in the operative rulebook" needs `ref` and cannot be answered from `artifact` alone.
6. **`artifact` gains the growth rule it never had.** `found_by`, positions and stages each grew by amendment; `artifact` stated no rule, and the silence was readable as either a closed set or an open one. It now grows by decision entry, like its neighbours, and no value is added before a query wants one.
7. **A finding's lawful exits: the five-exit enumeration governs, and the standalone two-home claim is retired.** [ADR-006:61] said *"its two lawful homes are the change that found it, or a guard"*; the same ADR elsewhere enumerated five exits. The five-exit list survives — ADR-006 itself diagnoses the two-home sentence as the defect (*"the clause would close three doors while leaving open the one nearest to hand"*), the two-home paragraph is contradicted three sentences later by its own creation of `owner-pending`, `filed` did not exist as a disposition when it was written, and `AGENTS.md` already states the five-exit reading. **"The two remedy homes" is preserved as a scoped term** naming the change and the guard, because the filing precondition — *both other homes rejected* — is unreadable without a referent, and it is cited by three surviving rules. Affirmed by the owner in conversation, 2026-08-18.
8. **The widened interim waiver.** ADR-002's boundary-format rule makes interchange formats code from day one; the waiver in ADR-006 §5 covered the ledger's rows and the seat record's. Entry files and citation tokens are formats created by this decision and are hand-written and validator-checked under the same waiver, stated where it binds rather than exceeded silently. **No claim is made on ADR-002's day-one-code exception for them** — the freeze marker and the supersession pointer ride that class because ADR-002 names markers by kind; the entry skeleton and citation tokens do not, and their validators ship as part of the mechanism this decision admits.

### What the extraction recovered

Three classes of rule would have been dropped by an extraction that read only `## Decision` sections, and are named here because the migration inventory's purpose is that a dropped rule is a visible row and never an invisible absence:

- **Seven rules live in `## Consequences` or `## Context` blocks**, each carrying an operative *only*/*never*/*entire* stated nowhere else: [ADR-001:30], [ADR-001:31], [ADR-003:48], [ADR-004:28], [ADR-005:48], [ADR-002:11], [ADR-002:17].
- **One rule sits inside a dead paragraph** — [ADR-003:33]'s *"a count nobody can reproduce is not evidence for anything"* is a general evidence standard embedded in a withdrawal record for a retracted recurrence count. It survives because a drafter wrote it into a section it believed was not its home, on the reasoning that a visibly-misplaced rule is recoverable and a silently-dropped one is not.
- **One operative constraint was stated affirmatively nowhere but inside a list of unenforced rules** — the ordering between `introduced` and `catchable` appeared only as a parenthetical in [ADR-006:94]. It has its own rule unit now.

### Defects fixed by the extraction

- **`severity` had no meaning at its definitional home.** [PR #49](https://github.com/Grimblaz-and-Friends/tradecraft/pull/49) wrote *"severity measures harm-if-unfixed"* into ADR-006 §3, where it exists to give the terminal stage's second clause a half to weigh against; §5's field contract stated only the value set. The statute states it once, in §8, and §6 delegates. Recorded here because the first assembly of the statute reproduced the same twin and was corrected before commit — the `M5` class, caught inside the change that closes it.
- **Five twin sites collapsed to one home each**: the doctrine budget (three sites), the no-load-bearing-session-state invariant (three), methodology's home (two), the merge-base unit (two), and `found_by`'s yield-vs-precision claim (two — the `M5` exhibit itself).

### One twin deliberately kept

The seat record's `sustained` gloss is stated in both the statute and `skills/adversarial-review/SKILL.md`. The duplication is **structurally forced, not merely deliberate**: the skill is in the shipped zone and ADR-004 forbids it referencing `docs/`, so delegation is unavailable in that direction, and the skill states its own portability requirement. The statute therefore adds the maintenance rule that makes duplication safe and that neither source stated — **a change to the gloss lands at both sites in the same change.** That, not collapsing, is what prevents the `M5` recurrence here.

### Citations are minted against the post-freeze tree

The freeze markers were inserted first, then citations taken from the tree as it lands. Eight ADRs shifted by exactly +2, verified byte-identical otherwise. **ADR-006 has five offsets** — +0, +2, +10, +14, +16 — because PRs #49 and #50 inserted paragraphs mid-file. A uniform +2 would have silently retargeted every §3, §4 and §5 citation at real but wrong text; that hazard was sustained as `PF2` in the design review and is the reason the mapping was proved rather than computed.

## Rejected

1. **A consolidation pass within the hybrid** (design revision 1) — rejected by the owner: it treats the symptom while keeping the structure that regenerates it, and must adjudicate case by case the class of records that defend their own inline length, which the split dissolves.
2. **Classic ADR discipline without a statute** — immutable ADRs and no extracted rulebook. Rejected: sessions would replay the log to learn current rules, and `AGENTS.md` is a budgeted summary, not a rulebook.
3. **Multiple statute files, one per domain** — rejected: multiple files multiply twin sites, and (`pr19-panel-2026-08-17`, `M5`) is the recorded incident class. One file, revisable by evidence if it grows unwieldy.
4. **A pairing guard requiring a statute edit and an entry in the same pull request, as ADR-002's first mechanism trial** — affirmed once, then rejected on the post-fix record: its falsifier keyed on a `disposition` distinction the ledger cannot express, its trigger fired after roughly two amendment pull requests instead of five on every shape in the live corpus, and its cut was priced above its keep, inverting the trial road's cost asymmetry. The same-pull-request obligation is prose in §12 instead. The lawful path back is a §8 amendment giving the ledger a trial-outcome distinction, on its own gate.
5. **Minting `statute` / `decision-log` / `frozen-adr` as `artifact` values** — rejected on the grounds in carve-out 5.
6. **A lint size budget on the statute** — rejected: the number would be speculative, and the doctrine budget guards an always-loaded file, where the statute is read on demand.

### The guards, and the verification that they block

Two guards ship in `tools/check_constitution.py`, both form/position/existence only, with 17 committed red-first pins in `tools/tests/test_check_constitution.py`. Each runs as a `pull_request`-gated step **inside the existing `lint-and-test` job**, never a new job.

**Ruleset verified 2026-08-18** (`gh api repos/Grimblaz-and-Friends/tradecraft/rulesets/20898154`): the required status checks are exactly `lint-and-test (ubuntu-latest)` and `lint-and-test (windows-latest)`, and **`strict_required_status_checks_policy` is `true`**. Both facts are load-bearing and are recorded so a later relaxation is a visible dependency break rather than a silent one: the required contexts are why a step in that job *blocks*, and the strict policy is what forces branch currency before merge, which is what makes evaluating append-only against the merge base sound rather than bypassable by a stale branch.

The guards exit **2 when they cannot determine** an answer. A guard that goes quiet when its base has moved prints the same line as a clean pass, which is how four failure modes became invisible in this repository's first version of the version-bump guard.

## Evidence

- The work's issue and its full design record, including all five artifact revisions, the panel review, the post-fix cycle, and the affirmations: [#42](https://github.com/Grimblaz-and-Friends/tradecraft/issues/42).
- The named dependency that landed first — a canonical form for the constitution-presumption rebuttal: [#37](https://github.com/Grimblaz-and-Friends/tradecraft/issues/37), [PR #50](https://github.com/Grimblaz-and-Friends/tradecraft/pull/50).
- The twin-site exhibit this restructure is measured against: (`pr19-panel-2026-08-17`, `M5`) in `docs/ledger.jsonl`.
- The design review's yield curve, which grounds the convergence declaration: 69 raw → 39 sustained (9 high); 21 surviving (4 high); 15 filed (1 high). The curve is stated in frozen [ADR-006:54] and in `docs/architecture/evidence.md`; `docs/seat-record.jsonl`'s rows under `issue42-design-panel-2026-08-18` carry the raw figure only, since `sustained` there credits every finder and sums to 51.
- Open items this decision does not settle, carried forward: [#22](https://github.com/Grimblaz-and-Friends/tradecraft/issues/22), [#26](https://github.com/Grimblaz-and-Friends/tradecraft/issues/26), [#35](https://github.com/Grimblaz-and-Friends/tradecraft/issues/35), [#36](https://github.com/Grimblaz-and-Friends/tradecraft/issues/36), [#38](https://github.com/Grimblaz-and-Friends/tradecraft/issues/38), [#44](https://github.com/Grimblaz-and-Friends/tradecraft/issues/44), [#45](https://github.com/Grimblaz-and-Friends/tradecraft/issues/45), [#46](https://github.com/Grimblaz-and-Friends/tradecraft/issues/46), [#51](https://github.com/Grimblaz-and-Friends/tradecraft/issues/51), [#54](https://github.com/Grimblaz-and-Friends/tradecraft/issues/54).

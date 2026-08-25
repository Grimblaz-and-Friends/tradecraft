# D-166: Acceptance criteria state consumer behavior, and each names the check that would falsify it

**Status:** Accepted 2026-08-25 (PR #166)

## Context

The owner asked, on 2026-08-23, why judging findings against a document's purpose was not helping. [#144](https://github.com/Grimblaz-and-Friends/tradecraft/issues/144) is the answer: the review's terminal clause (a) reads its success criteria from the affirmed acceptance criteria, and the rule producing those criteria was asking for the wrong thing.

### The rule as it stood

`skills/engagement/SKILL.md` at `b9bcdeb`: *"Write each one so a reader can tell from the diff whether it is met — a criterion nobody can check is a wish."*

True as far as it goes, and **no decision entry states or cites it** — verified by search over `docs/architecture/decisions/`, so this entry supersedes nothing by number. What it reaches, though, is conformance: what a diff can show is that a count is right, a section is present, a wording is faithful, a file is untouched. `skills/adversarial-review/SKILL.md:14` then makes those criteria the success definition every review stage inherits, and `:69`'s clause (a) dismisses only what impairs no criterion. A bookkeeping finding impairs a conformance criterion, so the filter sustains it — **because the criteria told it to**. The volume the practice has been paying for at review time was ratified upstream, at convergence.

### What was measured

The deliverable was a wording, so `skills/spikes`' trigger fired and a cold-seat A/B ran during drafting. Two arms differing in exactly the criteria bullet; two real dockets; then clause (a) applied to twelve of **PR #132's own** independently-verified findings, once against each arm's criteria. Six dispatches, Opus 5, Claude Code (Windows), throwaway.

**Arm A reproduced the defect from a standing start.** Given issue #124's change, it wrote **15 criteria: 14 conformance, 1 executable** — the shape of the [real affirmed artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/124#issuecomment-5387189939), which carries 15 with criterion 13 (`python tools/lint.py` … pass) as its only runnable one. Arm B wrote **12, every one behavioral with a named check**, and kept the executable class.

**Clause (a) on D1, D24, D5, D15, D20, D28, D31, D32, D33, D23, D22, D3:** Arm A dismissed **5 of 12**, Arm B **8 of 12**. The delta is three findings, all record-accuracy — D28 (a seat count restated 2-of-6 as 2-of-2), D32 (a docket size stated as nine when arms saw seven and eight), D23 (four argument-bearing words dropped in a compression) — and under Arm A each was sustained *by naming criterion 13 or 14*. All four consumer-facing findings survived both arms, the red-lint finding among them, so the executable class is not suppressed.

**On the second docket** — issue #133, which carries an open fork — Arm B's seat wrote unprompted *"If the owner rules that the table has no order, this criterion is empty on that branch"* and stated a per-branch falsifier on two more; Arm A produced defensible contingent criteria and no per-branch falsifier. 9 criteria against 7.

**The shape was already being invented by hand.** PR #155's own [artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/152#issuecomment-5390811885) carries behavioral criteria 1–4 each naming the experience session as its check, with 5–7 diff- or command-checkable — one PR before this one, unprompted. [D-155](D-155-2026-08-24-measured-figure-lawful-in-the-artifact.md) separately records a cold seat reaching this thesis from the author's side and rewriting a criterion that *"passes on any wording at all."*

## Decision

**1. Criteria state consumer behavior; conformance is the exception that argues for itself.** Each criterion is something a session working under the shipped thing can do, or no longer does wrongly. A criterion about the artifact conforming is lawful **where it argues its own consumer-facing load, which it states** — written for its own sake it ratifies the bookkeeping class the purpose filter then cannot dismiss. This is what gives clause (a) teeth, and **it buys them with no change to the review**: `skills/adversarial-review/SKILL.md` is byte-identical to `main`, which the measurement above is the whole warrant for.

**2. Diff-checkability narrows to falsifiability with a named instrument.** *Each criterion names the check that would falsify it* — the diff for what the diff settles, a command for what a command runs, a cold docket or the built result in use for what only use shows. **This narrows the old sentence rather than repealing it**, and *a criterion nobody can check is a wish* survives verbatim: what changes is that the diff stops being the only lawful instrument, not that checkability stops being required.

**3. A criterion a plausible wrong implementation would also pass measures nothing** — say what failing looks like before writing it. Where the artifact carries a fork, a criterion held to survive it must be falsifiable on **every** branch it survives, because the cheapest cross-branch criterion is one empty on a branch. This closes the second surface PR #155's terminal ruling routed to #144 (N8), which [D-155] cedes in as many words; that entry's criterion 5 required the sentence be byte-identical to `main`, and it was, so nothing here contradicts it.

**4. Naming the check does not order it run.** Put to the owner as the one fork, because the Arm B seat declared "Run owed" against 8 of its 12 criteria unprompted — up to eight cold dockets per change. **He ruled no.** The criterion states how the claim could be falsified and stops there; what a change owes in runs is owned by `skills/experience-session` and by `AGENTS.md`'s flow line, and a third statement of one duty is the drift [D-155]'s item 4 closed.

## Rejected

- **A rule about how many criteria to write.** #144 left count guidance open. Declined by the session and reported: the shape rule cut counts on its own in both dockets — 15→12 and 9→7 — so a number is a second rule for an effect the first already produces, and [#143](https://github.com/Grimblaz-and-Friends/tradecraft/issues/143)'s evidence is that instruments game counts rather than obey them.
- **Strengthening clause (a) to dismiss the conformance class directly.** This was the alternative to changing the criteria, and the run is the argument against it: the filter needed no amendment to shed three findings, and two findings both arms dismissed (D24 and D20, sustained by the real panel at high and strong-medium) say one A/B is not enough evidence to touch a review stage.
- **The change owing a run, or a recorded decline, per behavioral criterion.** Put to the owner and declined. Priced at up to eight cold dockets per change — or eight decline lines, which is the bookkeeping class this change exists to shrink.
- **One run per change, the experience session naming the criteria it covered.** Also put to him and declined. It is what PR #155 did in practice, but it restates the neighbouring cell's duty at a discount rather than avoiding it.
- **A guard.** Nothing mechanical distinguishes a behavioral criterion from a conformance one.
- **An offsetting deletion to hold the cell's size flat.** The change is net growth on `skills/engagement/SKILL.md` and the PR body carries the measured delta with its justification. `skills/authoring` asks that net growth be justified, not balanced, and deleting text to make a size claim true is the failure PR #132's ruling named at D9(a).

## Deferred, with the evidence that would reopen them

- **Both arms dismissed two findings the real panel sustained at high and strong-medium** — D24, a false superlative in a frozen entry, and D20, a claim in the shipped cell falsified by the change itself. That loss belongs to clause (a) against any criteria set, since the control produced it too, but a criteria rule that cannot reach a shipped cell's own false claim is worth watching. **Reopen on:** a review that dismisses a finding about shipped prose being false, and a later session acting on that prose wrongly.
- **The rule asserts what a cold session does under it, and the arms that measured it were prompt-contained rather than tree-isolated** — seats were instructed not to open repository files, not prevented. **Reopen on:** the experience session this change buys finding a seat that still writes a conformance checklist under the amended bullet, or one that reads it as licensing an unfalsifiable criterion.
- **Nothing distinguishes a criterion that genuinely argues its consumer-facing load from one that asserts it in a clause.** The exception in decision 1 is stated as a duty to argue, and a session can discharge it with a sentence. **Reopen on:** a conformance criterion whose stated load does not survive being questioned at review.
- **One seat per arm per docket.** The counts above are two runs, not a distribution. **Reopen on:** a second A/B whose arms do not separate.

## Evidence

[#144](https://github.com/Grimblaz-and-Friends/tradecraft/issues/144) and its comment routing PR #155's N8; the [affirmed artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/144#issuecomment-5404960073) and its [affirmation](https://github.com/Grimblaz-and-Friends/tradecraft/issues/144#issuecomment-5404967572), which carry the A/B in full with its limits. PR #166's body for the figures and their derivation. [#124](https://github.com/Grimblaz-and-Friends/tradecraft/issues/124)'s affirmed artifact and PR #132's terminal ruling for the twelve findings and the fifteen criteria that ratified them; [#133](https://github.com/Grimblaz-and-Friends/tradecraft/issues/133) for the fork docket. [D-155](D-155-2026-08-24-measured-figure-lawful-in-the-artifact.md) for the cession of this sentence, the fork rule this one qualifies, and the one-standard-one-owner reasoning decision 4 turns on. [#143](https://github.com/Grimblaz-and-Friends/tradecraft/issues/143) for the emission floor this meets from the criteria side. `skills/engagement/SKILL.md` at `b9bcdeb` for the rule as it stood.

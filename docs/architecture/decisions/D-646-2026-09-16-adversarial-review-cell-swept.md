# D-646 — The adversarial-review cell swept: three templates take what a session copies, two incidents go to this entry, and the body returns to its ceiling

**Landed by** [PR #646](https://github.com/Grimblaz-and-Friends/tradecraft/pull/646). Closes [#634](https://github.com/Grimblaz-and-Friends/tradecraft/issues/634). Governed by the implementation brief affirmed on [#571](https://github.com/Grimblaz-and-Friends/tradecraft/issues/571#issuecomment-5627498365) on 2026-09-10, which commissions each cell's sweep as its own reviewed change without a fresh affirmation; [D-575] landed the principle. **That brief as first affirmed carved this cell out**, and [D-575]`:9` records the carve-out as the brief then stated it; the owner's [amendment of 2026-09-14](https://github.com/Grimblaz-and-Friends/tradecraft/issues/571#issuecomment-5674412155) ruled it spent once #572 had landed, which is what put this sweep in scope. As every entry does, D-575 informs rather than binds, and reading it is how the carve-out was found rather than obeyed.

Evidence pinned at `b036238` unless stated, over base `c679fd5`. The pre-implementation artifact drafted its text against `6376ccb`, and the two quotations below are pinned there.

## What was decided

The `adversarial-review` cell keeps every concept it carried. What leaves is the case a session could decide from the concept, the armour clause, the second statement of something already said, the incident narration an entry can hold, and the field list a session copies at the moment of writing. Eighty-one passages were classed sentence by sentence in the artifact before anything was built: **34 kept** — three of them marked the owner's and not sharpened — **40 sharpened**, of which 21 also sent a clause somewhere; **3 to templates**; **1 to this entry**; **2 to another cell**; **1 cut unwritten**; **none to a guard**.

**Why none to a guard, which is this cell's particular constraint.** `skills/authoring/references/routing.md` states at its tip that a rule leaves prose for a guard or a script's message only where the reader who loses the sentence receives that guard. This cell's reader is an adopter, who receives `skills/` and `lib/` and nothing under `tools/`. The one guard that already checks this cell's output, `check_review_index` in `tools/lint.py`, is repo-only — so the index row's schema, which that guard checks, **ships as a template instead of collapsing into the guard**. What did go to a script's message is only what `skills/adversarial-review/scripts/external_pass.py` already prints at the moment of the mistake; that script and its tests are byte-identical across this change.

## Item 3 of the reading, and the decision it took: three templates, one per output

The reading's third item sends the fields of an output to one template file. This cell emits three things a session copies while writing, each with its fields spread through prose: the **dispatch**, the **final report**, and the **index row**. The reading named the report and the row; the dispatch is the third because it is what every review role receives and what D-617's collision was about.

A template is a script's material under the charter principle — it is what a session copies, not what it reasons from — so the fields left the prose for three files and the prose kept what each output is for and who reads it. The convention, which the settled sweeps followed and the `authoring` artifact states once: flat files directly in `references/`, named `<thing>-template.md`, each opening with a `**Loaded when**` line and a one-line instruction to copy it whole, carrying fields, angle-bracket placeholders and one-line hints and **no sentence of reasoning or incident**, each with one index entry in the body. Flat rather than nested is repo mechanics — `REFERENCES_REF` in `tools/lint.py` admits no slash, and `check_depth_index` uses `rglob` — and is deliberately not restated in shipped prose.

**One gap the templates close.** `skills/engagement/references/the-brief.md` states that a review's final report is a surface the owner enters, where its descriptive plain brief opens the report as posted. The report's field list carried no brief. `report-template.md` now opens with the plain-brief line and names the form as the `engagement` cell's.

## Every deletion, and which material took it

As the brief requires: the change that removes a rule says which it was. Deletions fall in two places and both are tabled — the passages that leave whole, and the sentences and clauses cut out of lines the table otherwise classes as *sharpened*. **What the tables do not enumerate is compression inside an index entry or a pointer précis**, where a trigger clause or a phrase naming what a depth file holds was shortened in place; those lines are classed as rewritten and the diff is the whole record of them.

### The passages that leave whole

| passage | class | where it went |
| --- | --- | --- |
| `roster.md:14-30` at `6376ccb` — the width paragraph, the three-row retention table, and its five following paragraphs | to entry | Quoted verbatim below, pinned. [D-336] records what the recomputation settled but does **not** hold the table. Prose keeps the concept — the width rests on this repository's record, the fifth chair buys the other shape seat, worth-it is a judgement and not a measurement, the corpus predates the deletion lens — and the two links the recipe lives at. No figure was altered or re-derived; they left shipped prose for this entry. |
| `dispatch.md:9`'s observed-evidence clause and its two observed-incident sentences at `6376ccb` | to entry | Quoted verbatim below, pinned. [D-222] holds neither. Prose keeps the concept — the root's copy is the change's, the recipient told injected always-on text is not governing — with its reason and the fact that naming the root alone has not stopped it. |
| `dispatch.md:11` at `6376ccb`, the positioning procedure | to another cell + to template | Building a tree at a revision, for any instrument's run, is the `experience-session` cell's (D-491 decision 3); the one line a recipient runs on a root it cannot rebuild, and its failure case, are `dispatch-template.md`'s. |
| `after-the-fix.md:5`, the holder-resumes sentence and the Source-verification pointer | to another cell | `skills/engagement/references/the-stretch.md`. Prose keeps one pointer sentence. |
| `the-record.md:9-21`, the eleven-field list of the final report | to template | `report-template.md`. Prose keeps the concept — the report is the review's whole evidence to a reader who was not in it; per-seat counts are credits [D-185]; the unit is the finding as originated and dispositioned. |
| `the-record.md:23` — "**The review closes here.** There is no further pass to rule on — a review is one round (`../references/after-the-fix.md`) — so the report names the residual risk accepted and what is expected to catch it instead: the experience session on the fixed tree, and friction met under the merged material once it is in use." — that path as the line wrote it, at `6376ccb` | cut, unwritten | The third intra-cell copy of *a review is one round*, which `SKILL.md` and `after-the-fix.md` each state. What catches the residual risk is the standing intake, already stated; the residual-risk field is `report-template.md`'s. |
| `the-record.md:29`, the bot-comment-is-not-a-seat sentence | to template | The concept is `after-the-fix.md`'s definition of a commissioned pass; what remained was a hint on a key, now in `index-row-template.md`. |
| The three new depth-index entries' clause `, copied whole and filled` | cut, unwritten — **classed here, not by the artifact** | **A deletion this change made of its own new text.** The artifact's table classes the three new entries as *to template* and supplies no class for this clause, because the clause did not exist when the table was written; §6's last bullet requires this entry to class any line the table missed, and this is that class. Ruled during the build and reasoned in *The ceiling call* below. Each template already opens with the instruction in its own words. |

### The sentences and clauses cut out of sharpened lines

A line classed *sharpen* keeps its concept and its reason. These are what left those lines. **Every quotation below is an exact contiguous substring of the line named, at `6376ccb`, carrying that line's own emphasis markup and eliding nothing inside itself.** **No row below touches one of the sentences marked the owner's**, which are tabled separately and lost nothing.

| line at `6376ccb` | what was cut | its class |
| --- | --- | --- |
| `SKILL.md:10` | "**That last bars the tree other stages read, never a seat's own isolated one**, so a seat dispatched to write does the job it was dispatched for" | a case `dispatch.md`'s isolation contract decides |
| `SKILL.md:10` | *"the live options, each with pros and cons, and a recommendation among them"* | to another cell — the ask's argued form is `engagement`'s `the-ask.md` |
| `SKILL.md:10` | *"Safe in attended and unattended lanes alike"* | armour |
| `SKILL.md:24` | *"Each stage's own machinery is one hop away, and the pointer says when to open it — a session on one step of the pipeline has no use for the rest"* | to another cell — the cell's shape is `authoring`'s `cell-structure.md`, restated here |
| `SKILL.md:37` | *"Load hides in absence claims, universals, superlatives, and counts — check those first"* | a how the definition already decides |
| `SKILL.md:37` | the six-cycle exhibit link | to entry — [D-371], now the citation |
| `SKILL.md:38` | "**Severity is reached too**, because a high against governing prose whose harm claim is behavioral is settleable, where a probe is cheap, before a fix is priced on it; a high in the executable class — a red lint, a guard that cannot fail — arrives with its probe and is not re-probed" | a case lines 36, 38 and 41 decide together |
| `SKILL.md:39` | *"a returned need is stage output, not an owner question"* | typed-halt decides it |
| `SKILL.md:39` | *"the same assignment and only the history the role permits"* | the byte-identical block and the roster's withholding already say it |
| `the-shape.md:7` | *", in one line"* | to template — the report template's field says so |
| `roster.md:7` | *"and where the artifact is both shapes, both shape seats sit and the panel is five"* | the first of three copies; the fifth chair is `the-shape.md:6`'s |
| `roster.md:11` | *"The consumer walk this seat used to run is now done for real by the experience session the change buys"* | history, D-295's |
| `roster.md:12` | *"which here is this skill's broad sense, prose a later session is expected to act on, reaching a docstring that states a calling contract and not confined to always-on surfaces and cells"* | the cell's second definition of *governing prose*; `SKILL.md:18` holds the one |
| `roster.md:12` | *"(in the decision entry where one exists, else the PR body)"* → *"where amendments are recorded"* | to another cell — which surface records an amendment is `authoring`'s `revising.md` |
| `roster.md:12` | *"When the artifact is both shapes, both seats sit and the panel is five"* | the third copy |
| `roster.md:32` | *"The dispatch names this explicit exception to assignment identity"* | the dispatch contract and the template already say it |
| `roster.md:32` | *"The judge's separation from finders is in the dispatch contract"* | an unwritten pointer; `dispatch.md` states it |
| `roster.md:38` | *"Each launch names its model and reasoning effort explicitly; a runtime default is not review evidence"* | to another cell — `engagement`'s `dispatch-records.md` |
| `roster.md:38` | "The report records which model, effort and runtime staffed each seat, so per-runtime evidence can accumulate; how that value is spelled is the record's (`../references/the-record.md`), and one spelling per runtime is what makes it a query." — that path as the line wrote it, at `6376ccb` | to template — the field and its hint; the reason stays once in `the-record.md` |
| `dispatch.md:5` | every field enumeration of the shared block | to template — `dispatch-template.md` |
| `dispatch.md:5` | *"A proved-empty bundle is evidence too"* | kept at `after-the-fix.md:25`, where the bundle is defined |
| `dispatch.md:5` | *"Writing either per recipient is how a dispatcher ends up repeating a byte-identical section outside the block whose definition is that it is byte-identical"* | armour |
| `dispatch.md:7` | the launch-record sentence | to another cell — `engagement`'s `dispatch-records.md` |
| `dispatch.md:9` | the observed-evidence clause beginning `which on this practice's own evidence`, cut from the middle of a sentence whose remainder stayed; the two observed-incident sentences; and the diffing armour | to entry — all three quoted below |
| `dispatch.md:13` | the pointer to `the-record.md` | the report template carries the field |
| `dispatch.md:15` | the flag-by-flag explanation of `git worktree add --detach <path> <base>` | to template; the contract decides the case |
| `dispatch.md:15` | *"At a named revision the flag changes nothing observable, which is why a check over the two forms proves nothing"* | armour |
| `dispatch.md:15` | "**Detached, the base may be the change under review** — a seat probing that change has to hold it" | a case the contract decides |
| `dispatch.md:17` | the incident narration of the removal taken while a cold seat was verifying | to entry — [D-392]`:19` holds it |
| `dispatch.md:17` | *"and whether the tree was cut with `--detach` is not what decides it"* | armour |
| `arbitration.md:5` | *"The account is read off the seat's report itself, never off a total the seat states about itself"* | D-102's index concept decides it; D-453 argues it |
| `arbitration.md:5` | *"a seat's declined examinations are one entry rather than fifty — while a qualification inside a carried finding travels with it"* | the example, and a case |
| `arbitration.md:11` | *"Stating a price is not arguing a drop; a defense that declines a finding without a ruling on the record has suppressed it"* | armour; `:19`'s lapse rule decides it |
| `arbitration.md:11` | *"Where a defense verdict can be settled by running something, run it"* | `SKILL.md:38`'s |
| `arbitration.md:21` | the three restated filing rules — search first; fresh evidence extends an open pitch; a closed pitch is history | to another cell — the `filing` cell owns them |
| `arbitration.md:23` | *"severity and remedy price are separate judgments, not an average of positions"* | `SKILL.md:41`'s |
| `arbitration.md:23` | *"A disputed behavior claim goes to a spike where a run can settle it cheaply, before the fate is ruled"* | `SKILL.md:38`'s applied |
| `arbitration.md:27` | the two intra-cell copies of the floor obligation | one pointer clause; the same-tree clause moved to `after-the-fix.md:25`, where the reconciliation is stated |
| `after-the-fix.md:3` | *"as they did when the cell body held them"* | history of the split |
| `after-the-fix.md:15` | the stage enumeration | `SKILL.md` and `the-shape.md` state the round |
| `after-the-fix.md:15` | the six-cycles exhibit link | to entry — [D-371]; a second copy of one exhibit |
| `after-the-fix.md:19` | who rechecks which record, and the source-check sequence | to another cell — `engagement`'s `the-stretch.md` |
| `after-the-fix.md:21` | *"where it rewrote what the material instructs, or changed what a consumer can do"* | to another cell — the second-run trigger is `experience-session`'s |
| `after-the-fix.md:21` | *"and nothing further"* | **resolves finding §1.3** — this cell no longer says what the repair batch buys beyond the floor, which `when-one-fires.md` decides |
| `after-the-fix.md:25` | *"The holder's external-pass job starts in a shell with authenticated `gh`, network access, and its supplied permission or approval route"* | to script message — what `external_pass.py` says at the moment |
| `after-the-fix.md:25` | *"Retry a failed collection or verification"* | to script message |
| `after-the-fix.md:25` | *"A stale receipt cannot close the review"* | drift-buys-a-new-bundle decides it |
| `after-the-fix.md:25` | "Record what actually posted even when it produced nothing; configured reviewers stub, rate-limit, and skip." and the `external` booking | to template — `index-row-template.md` |
| `after-the-fix.md:25` | the four external dispositions enumerated | to template — `report-template.md` |
| `after-the-fix.md:27` | *"none of the availability states above can apply to it"* | armour |
| `after-the-fix.md:27` | *"who invoked it is not what makes a seat"* | armour |
| `after-the-fix.md:27` | *"both of which would misdescribe its provenance"* | the reason restated |
| `the-record.md:5` | the receipt's five fields | to template — `report-template.md` |
| `the-record.md:5` | the explanation of what the source check is and is not | to another cell — `engagement`'s `the-stretch.md` |
| `the-record.md:7` | the per-field producer mapping | compressed to one sentence |
| `the-record.md:27` | the key enumeration and the two spellings | to template — `index-row-template.md` |
| `the-record.md:27` | "**This licence reaches facts about the run and nothing further**; a count of findings under any name is the arithmetic this cutover retired." | armour restating the no-arithmetic sentence above it |
| `the-record.md:27` | *"evidence for the next lane choice rather than a ceiling to come under"* | to `the-shape.md`, which owns cost-is-evidence-never-a-ceiling; a pointer clause remains |
| `the-record.md:31` | the degraded-width row hint | to template — `index-row-template.md`'s `staffing` hint |
| `lenses.md:5` | *"wherever in the cell they sit"* | armour from the split |
| `lenses.md:7` | *"wherever they sit"* | armour from the split |

## The two passages quoted here, pinned to `6376ccb`

Read them with `git show 6376ccb:skills/adversarial-review/references/roster.md | sed -n '14,30p'` and `git show 6376ccb:skills/adversarial-review/references/dispatch.md | sed -n '9p'`. Nothing in either is altered, re-derived or re-argued; they are here because the concept that cites them stayed in the prose and the evidence did not.

### `roster.md:14-30` — the width's measurement on this repository's record

> **The width is measured, and on this repository's own record.** Across the 25 panel-lane reviews in `tradecraft` dated 2026-08-26 or later that booked a sustained high — the window opening where reports began naming each high's finders — 81 panel-originated sustained highs were recovered, **55 of them carrying attribution** and 50 of those naming a primary finder. Retention of those highs by the panels this roster actually staffs:
>
> | the panel | of the 55 attributed | of the 50 naming a primary |
> | --- | --- | --- |
> | four — the standing seats and `claims-vs-evidence` | 91% | 84% |
> | four — the standing seats and `revision-diff` | 87% | 80% |
> | five — both shape seats sitting | 100% | 100% |
>
> The corpus is the highs the **round-one panel itself originated**, so the five-seat row is 100% by construction: this measures redundancy within a panel, never what a panel detects — highs first found by a defense, an external pass, or the post-fix look this practice ran before a review became one round are outside it. Both columns are given because they bracket, and neither is the answer alone: the first cannot tell a high one seat found from one all five found, the second cannot see a co-finder at all and drops the five attributed highs that name no primary. **These are the panels this roster permits, not best-available subsets** — the recomputation also orders seats by hindsight, and every interior point of that ordering describes a panel this roster does not staff, so its curve is not comparable to the table above.
>
> **The corpus predates `operational`'s deletion lens.** Its highs were found by panels whose `operational` seat walked the artifact as its consumer; what the lens above does to these figures is unmeasured, and the corpus is historical so it cannot be recomputed. Read the table as what those seats retained, never as a forecast for the seats now staffed.
>
> **What the fifth chair buys is whichever shape seat the fourth did not take**, and the table prices it on that historical corpus: adding `claims-vs-evidence` to a panel that seated `revision-diff` is 13 points, adding `revision-diff` to one that seated `claims-vs-evidence` is 9, and 20 and 16 respectively counting primaries. Those are the seven and five highs each seat sole-finds — 12 of the 20 sole-found highs in the corpus between them, the two strongest records on it. Whether that is worth a dispatch is a worth-it judgement and not a measurement.
>
> **What the figures cannot settle**, which matters as much as what they say: 26 of the 81 panel highs name no finder anywhere, all but one because six whole reviews published no attribution at all. Over all 81, the four-seat panel seating `claims-vs-evidence` lands between 62% and 94% and the one seating `revision-diff` between 59% and 91%, depending on whether the unattributed resemble the attributed; both intervals are derived here over the roster's panels, where [the recomputation](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138#issuecomment-5519548671) states 65% to 98% for a hindsight-chosen four this roster does not staff. That comment carries the corpus, the per-seat table and the re-run recipe, as narrowed by [its correction](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138#issuecomment-5519836260); together they discharge the trigger [D-185] set, and [D-336] records what it settled.
>
> **The predecessor's figure is retired rather than carried here** — a single pass keeping 12% of sustained yield ([the mining record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/1)). It measured yield across every severity, a different quantity from the highs-only retention above, so the two cannot be set beside each other. Nothing refuted that figure: [a local spike](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138#issuecomment-5389959332) separately put one cold pass on this practice's own artifacts at close to the same 12%.

### `dispatch.md:9` — the observations about injected governing text

The line's concept and its reason stayed in the cell; what left is the evidence standing behind them, which [D-222] does not hold. Three fragments of that line at `6376ccb`, each exact and contiguous, and not contiguous with each other because the first was cut from the middle of a sentence whose remainder stayed:

> which on this practice's own evidence can be a tree that is neither the change, its base, nor the default branch

> Naming the working root is not enough on its own [D-222]: the stale text arrives beside it, and only an isolated root plus that statement has been observed to make a recipient reject it.

> **Nor does diffing against the default branch establish it**, a seat having been handed text from a tree that was neither the change, its base, nor that branch.

## The fourteen ownership calls

Applied without re-deciding, each settled elsewhere: the dispatch contract's cold-seat half → `engagement`, its review half → this cell (#577); the isolation procedure → `experience-session` (D-491 decision 3); the second-run trigger and the declining line → `experience-session` (#583); the row's repo-only side, `cost` and `target` → `records` (#612); the site-read rule → `arbitration.md:7` (records call 5). Made here:

1. **The dispatch's fields are this cell's, stated once in `dispatch-template.md`**; the launch record — model, effort, permission boundary, and the source of each — is `engagement`'s, and `dispatch.md:7`'s and `roster.md:38`'s copies go.
2. **What isolation *is* for a review recipient stays here** (D-392) — its own detached tree at the revision, a write boundary where it writes, removable at the review's close; **how** a tree is built at a revision is `experience-session`'s (D-491); the one line for a root that cannot be rebuilt, and its failure case, are the template's, no other cell stating them.
3. **The report's fields are this cell's, stated once in `report-template.md`**, and the report opens with the plain brief whose form is `engagement`'s.
4. **The row's shipped keys and spellings are this cell's, stated once in `index-row-template.md`**; the licence that a repository states which dispatches its cost counts stays in `the-record.md`'s prose, because the `records` cell reads it there.
5. **"Governing prose" is defined once, at `SKILL.md:18`**; `roster.md:12`'s second definition goes, and a docstring stating a calling contract is a case the one definition decides.
6. **What buys the fifth chair is `the-shape.md:6`'s**; `roster.md:7` and `:12` lose their copies.
7. **Cost as evidence and never a ceiling is `the-shape.md:7`'s**; `the-record.md` keeps only that cost is read off returns and points at the shape page.
8. **Which surface records an amendment is `authoring`'s**; `roster.md:12`'s parenthetical goes.
9. **Who resumes the builder, the Source-verification rule and the record-recheck sequence are `engagement`'s**; `after-the-fix.md:5`, `:19` and `the-record.md:5` keep one pointer each.
10. **The filing standard's rules are `filing`'s**; `arbitration.md:21` keeps the pointer and the lapse clause, and nothing in that cell is touched here.
11. **The argued form of an owner question is `engagement`'s**; `SKILL.md:10` keeps only that the question goes to the report argued.
12. **Incident narration no existing entry holds comes to this entry, quoted verbatim and pinned, and the concept cites it** — `roster.md:14-30` and `dispatch.md:9`'s observed-evidence clause with its two observations. Where an existing entry holds the incident — D-392 for `dispatch.md:15` and `:17`, D-371 for `SKILL.md:37` and `after-the-fix.md:15` — it is cited and nothing is quoted again.
13. **The lens briefs stay in `roster.md`**; the dispatch template names them as what the recipient's part copies, so a seat's identity has one home.
14. **`external_pass.py`'s refusals are the script's**, not this cell's prose to restate: *gh not on PATH*, *gh api failed*, *unstable between complete drains; run collect again*, *source drift in \<label\>*, *source failure while verifying*.

## The findings this sweep resolved, and the reading each took

- **§1.3** — what a repair batch buys beyond the floor. Resolved by this cell no longer saying: *"and nothing further"* is cut from `after-the-fix.md:21`, and `experience-session`'s `when-one-fires.md` decides it.
- **§2.3** — two definitions of *governing prose*. Resolved to one, at `SKILL.md:18`; `roster.md:12`'s goes. `grep -rn "prose a later session is expected to act on" skills/adversarial-review` returns exactly one line.
- **§3.9** — the report's field list carried no plain brief, while `engagement` says the report is a surface the owner enters. Resolved by `report-template.md` opening with the plain-brief line and naming the form as that cell's.
- **§4.2** — the dispatch's fields spread through three files. Resolved to `dispatch-template.md`.
- **§4.3** — the report's and the row's fields interleaved with the history of retired counts. Resolved to `report-template.md` and `index-row-template.md`; the retirement's reason stays in prose, the schema does not.
- **§5.8** — the retention table as shipped evidence. Resolved by quoting it here and leaving the concept, per `skills/authoring/SKILL.md`'s rule that evidence sits behind a link.

## The route named for `dispatch.md:11`, and the residue

The positioning procedure's route is: the sentence in `dispatch.md` → the `experience-session` cell's own depth index → `skills/experience-session/references/isolation.md`, whose load condition covers **whichever instrument's run it is**.

**The residue, stated rather than hidden.** `skills/experience-session/references/running-one.md:5`, which the sweep's findings and the #583 artifact both cite for positioning, no longer holds it — D-591 replaced that line with the holder-charters sentence. And `isolation.md` builds a tree at a commit without naming a tool-cut root. That is why the one-line remedy for a root a recipient cannot rebuild stayed in this cell's template rather than becoming a pointer: at `6376ccb` no other cell stated it.

## Cross-cell copies of this cell's concerns, left standing on purpose

Named here by file so the next sweeps do not re-find them, each belonging to its own change: `skills/engagement/references/cold-seat.md` and `skills/spikes/references/cold-seat-ab.md` (positioning — the `engagement` artifact already routes its copy); `docs/cells/landing/SKILL.md` (the experience-session line); `docs/cells/records/references/what-a-review-records.md`, which points here lawfully.

**The shift the `records` sweep must know:** the licence sentence its settled artifact reads as `the-record.md:28` — "**A repository recording it says in its own material which dispatches it counts**" — lands at **`the-record.md:13`** after this change. `grep -n "which dispatches it counts" skills/adversarial-review/references/the-record.md` finds it there.

## Citations added by this change

[D-371] at `SKILL.md`'s load-bearing-claim bullet, in place of the exhibit link it and `after-the-fix.md` both carried; [D-392] at `dispatch.md`'s isolation contract and its removal rule; [D-336] and [D-646] at `roster.md`'s width paragraph; [D-222] and [D-646] at `dispatch.md`'s governing-text paragraph.

## What the build had to re-derive, and one correction to the record it was handed

The artifact settled against `6376ccb` and `main` moved before the build. A note on #634 recorded the dependency and attributed the five edited cell files to **PR #638** at `c679fd5`. **That attribution is wrong.** `git show --stat c679fd5 -- skills/adversarial-review` prints nothing, and `git log --oneline 6376ccb..c679fd5 -- skills/adversarial-review` returns exactly one commit: `de2802b`, **PR #630**, the capability-declaring dispatch change ([D-630]). #638 edited `skills/engagement/` instead. The note's own `git diff --stat b0a1f0f c679fd5` spanned both commits and credited the later one. The five files and 19 lines are the same either way, so nothing the build carried changed — only the provenance.

#630's sentences are affirmed decisions and were carried into the sharpened lines rather than reverted: the capability map in the roster précis, the execution requirement on `wiring-falsifier`, the seat-launcher capability paragraph, the capability-bound truncation sentence (which is also one of the owner's, and is untouched), the `seat-launcher-incompatible` rule, the capability-`execute` write boundary with its time bound, and the achieved-width field, which went into `report-template.md` with the rest of the field list. The launch-record sentence at `dispatch.md:7` was still cut to `engagement`, whose `dispatch-records.md` states it including #630's *selected means the launcher's request, not runtime observation* reading.

## The ceiling call

The artifact drafted a body of 8,104 against a re-baselined ceiling of 8,104, leaving ten characters against the standing row of 8,114. #630's insertion is 22 characters — the phrase `their capability map` is 20, and its comma and following space are the other two — so the built body first measured **8,126**, twelve over.

Re-baselining to 8,126 was refused. The ratchet's own comment prescribes re-baselining for a cell that *sheds*, and a constant left above a smaller body measures nothing until the body regrows to it; the artifact records making the same refusal once already in its probe, at 8,429, and sweeping three more body passages instead. So more body shed here: **the clause `, copied whole and filled` left all three template index entries**, since each template already opens with that instruction in its own words, so one rule stood written six times across the cell. It is the only redundancy this change introduced — the three entries are new here — so cutting it relitigated nothing the artifact settled, where cutting any other body passage would have, every one being a keep row or an already-sharpened one.

Three clauses at 25 characters each brought the body to **8,051**, and `CELL_BODY_CEILING_CHARS["skills/adversarial-review/SKILL.md"]` in `tools/lint.py` was re-baselined from `8_114` to `8_051` in the same change, so the ratchet follows the shed down rather than standing above it.

## The owner's sentences, and what was not touched

Four passages are the owner's and none is sharpened: `arbitration.md`'s truncation-and-fallback rule whole (the term affirmed on #581, as #630 rewrote it), **Work is bought, never owed** whole and **The affirmed implementation brief is the budget** whole (both D-590), and `roster.md`'s three tier sentences (D-601). Not marked, and why: D-617's *"external pass only"* bounds the enumerator rather than a sentence in this cell, and the three-collections sentence is the review's qualification and was sharpened.

Also untouched, each for its own reason: the `filing` cell (its own sweep); `arbitration.md:7`'s consequence-shape axis (#377 and #456 own it); `the-shape.md:6`'s panel triggers and `roster.md:38`'s tiers, both what-preferences the owner has not stated; the frontmatter description, so no roster regeneration; `scripts/`, `tests/`, `lib/` and every guard. Nothing was built for #595 — the report template carries `pitched #N` as a fate and leaves a pitch section to add.

**No settling row is appended.** The brief is #571's, affirmed once for every sweep, and its row already stands on `docs/settling.jsonl`. A second row would record the same affirmation twice. This is the same call the settled sweeps made, so the sweeps agree; the `records` cell's own sweep may decide otherwise for all of them at once.

## Figures

Every figure here is a command with both endpoints pinned, never a transcribed output.

- Shipped prose: `git diff --stat c679fd5 b036238 -- skills`, and `find skills -name "*.md" -exec cat {} + | wc -c` run in a tree at each of `c679fd5` and `b036238`.
- The cell body and its ceiling: `python -c "import sys; sys.path.insert(0,'tools'); import lint; from pathlib import Path; print(len(lint._frontmatterless(Path('skills/adversarial-review/SKILL.md').read_text(encoding='utf-8'))))"` at each endpoint, against `CELL_BODY_CEILING_CHARS["skills/adversarial-review/SKILL.md"]` in `tools/lint.py`, and `python tools/lint.py`'s *cell bodies here* block.
- What this cell lost and gained: `git diff --stat c679fd5 b036238 -- skills/adversarial-review`.
- What #630 changed and this build carried: `git diff 6376ccb c679fd5 -- skills/adversarial-review`.
- The class count, over the artifact's §2 table on [#634](https://github.com/Grimblaz-and-Friends/tradecraft/issues/634): its rows by `grep -cE '^\| ([0-9]|new)'` and its class column by `awk -F'|' '{print $4}' | sort | uniq -c`, both run over that comment's body fetched with `gh api repos/Grimblaz-and-Friends/tradecraft/issues/comments/5674502610 --jq .body`.

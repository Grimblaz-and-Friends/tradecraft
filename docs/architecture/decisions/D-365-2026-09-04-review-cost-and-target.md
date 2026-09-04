# D-365: What a review cost is a fact about the run, the surface each high hit rides on the high, and a positional exemption belongs to one record

**Status:** Accepted 2026-09-04 (PR #365)

**Evidence, and this entry's exposures.** Everything quoted from a live file is pinned to this change's base `f4f3dbc`, the tip of `main` the branch was cut from; figures over `docs/reviews.jsonl` are stated as the command that derives them and were run at that base. **Two exposures are this entry's own.** The convergence rounds — three cold seats, their verdicts and the points each landed on — live on [#357](https://github.com/Grimblaz-and-Friends/tradecraft/issues/357) and in the settled artifact posted there; the design argument below does not rest on them. And the premise that a review's cost is capturable without estimating rests on one throwaway dispatch made from the drafting session, whose return is quoted below and which no in-repository reader can re-open; it is re-runnable in eight seconds by anyone with the harness, which is why it was spiked rather than asserted. The brief and its affirmation are [on the issue](https://github.com/Grimblaz-and-Friends/tradecraft/issues/357#issuecomment-5535709874); the artifact is [there too](https://github.com/Grimblaz-and-Friends/tradecraft/issues/357#issuecomment-5535915220).

## Why the row could not carry this before

[D-194]'s cutover put a hard sentence into `skills/adversarial-review/references/the-record.md`, byte-identical at `f4f3dbc`:

> **The row carries no arithmetic.**

Read literally it forbids two integers about the run, and the guard enforced it literally: `QUALITATIVE_FIELDS` is a closed set, so any new key at all drew *"arithmetic under a fresh name is the arithmetic this cutover retired"*. That closure was right — a review had found the same totals under `counts` or `totals` passing clean — but the sentence overshot what it was written to stop.

**What it was written to stop was arithmetic over the findings**, and `staffing` is the proof, in the guard's own comment at `f4f3dbc`:

> `staffing` survives the cutover -- a model and a runtime are facts about who ran the review, not arithmetic about it, and this row is the only queryable home the per-runtime evidence has.

**So the sentence is narrowed rather than the field excepted.** *No arithmetic over the findings* is what it always meant; `cost` sits on the same ground `staffing` already stood on. The distinction is not a loophole but the whole of it: a count of findings was hand-totalled and reconcilable by nothing, while a count of dispatches is a fact the run produced.

## Cost

`{"dispatches": n, "subagent_tokens": n}`, scoped to the review — first seat dispatch to terminal ruling, cycles, defence, judge and any commissioned pass included. Convergence, cold seats, spikes and experience sessions are the change's cost, not the review's, and the row's subject is the review. **A comparison against the by-hand figures on #355, #143 and #296 must say which of the two it is comparing**, because several of those are change-wide; that is the honest limit of what this field lets #360 score.

**Neither figure is estimated, and that was tested before it was asserted.** One throwaway dispatch from the drafting session returned:

> `subagent_tokens: 42872`, `tool_uses: 0`, `duration_ms: 1384`

So a closing session sums exact per-dispatch returns. It is `claude-code (windows)` evidence only, which is why `subagent_tokens` may be `null` — an abstention claiming nothing, where a zero would claim no subagent ran. `dispatches` may **not** abstain: a runtime that made dispatches can count them, so a null there is a figure withheld rather than one unavailable. Wall-clock was rejected as measuring queueing, and a seat count as already carried by `staffing` and the report.

**It is evidence and not a target.** That sentence had to land where a lane is *chosen* rather than where a review is *closed* — a cold seat's second verdict is what caught the placement — so it sits on the lane-heuristic bullet in `skills/adversarial-review/SKILL.md`, beside the promise that motivated the whole issue: *"an unrecorded shape choice can never be audited later."*

## Target, and why it is not counts

Each sustained high becomes `{"high": ..., "target": ...}` rather than the row gaining a count per bucket. **`facing` is why.** It was the last attempt to book this axis as counts, and at `f4f3dbc` it sits on 8 of 74 rows with none written since 2026-08-26 —

    python -c "import json;print([(i, r['date']) for i, r in enumerate(map(json.loads, open('docs/reviews.jsonl', encoding='utf-8'))) if 'facing' in r])"

— its own defining comment recording that the three reports which stated a split before it landed each counted a different population. A label riding on the text it describes cannot fail to reconcile, and the list's length remains what answers *how many highs* [D-185].

**Three values, not the owner's stated two.** His 2026-09-03 direction on #360 named a binary: shipped text, or the change's record. The amendment was put to him with the concrete case — this change's own deliverable is `docs/cells/`, `tools/` and its tests, so under a binary every high its review sustains against the guard files as *paperwork*, in the first row the trial scores — and he affirmed the third value on 2026-09-04. Owner-stated requirements are admitted, not argued; this one was argued and then re-affirmed, which is the route the charter names.

**Ordered, first match governing**, which is what makes them a partition rather than three enumerations that overlap: `record` (this change's own paperwork) is tested first, because a decision entry and an index row live inside the other two zones and a zone test would swallow them; then `shipped`; then `repo` as the **residual**, so every site in the tree has a lawful label. Both properties were adverse-verdict repairs: revision 2 defined `repo` as "anything under `docs/`" and so labelled this change's own decision entry two ways at once, and left `README.md`, the dotfiles and the generated mirrors outside all three.

**`target` and the merge's consequence shape are different axes.** `arbitration.md` reads consequence shape from the site the finding cites and resolves a both-kinds finding upward; `target` copies both moves, so the two never point opposite ways. But one asks whose machinery the finding is about and the other which surface it hit, and a finding about the review's own bookkeeping inside a shipped file is `apparatus` and `shipped` at once. The guard's own test rejects `artifact` and `apparatus` as `target` values, because reaching for them is the confusion this axis most invites.

## The positional exemption belongs to one record

`check_review_index` carried four boundaries, each grandfathering the rows that predated a schema. **All four were facts about one file and were applied to any file of that name.** The consequence is [#268]: in a tree whose index has not started, row 0 is below every boundary, so the guard demanded the per-seat counting shape that `the-record.md` abolished. Two experience-session consumers hit it independently and both refused to clear the red the way the message asked — clearing it meant inventing counts that never reached them into a record nobody may correct.

**The file is now identified by the sha256 of its first non-blank row's bytes**, and anything that is not this record gets zero for every boundary and is held to the current shape. That also closes the defect's unnoticed other direction: before this, such a tree's rows 0–38 would have *admitted* the abolished counting shape silently.

**Row 0's `artifact` was rejected as the sentinel.** It is `pr-74`, which no repository is prevented from writing, and `artifact` is not unique even within this file — `pr-156` appears on two rows:

    python -c "import json,collections;print({a:c for a,c in collections.Counter(json.loads(l)['artifact'] for l in open('docs/reviews.jsonl',encoding='utf-8') if l.strip()).items() if c>1})"

Records here are append-only, so row 0's bytes are as stable as its name and far harder to collide with. A truncated copy of this file therefore reads as foreign, which is deliberate: a record that lost its first row was mutated, and holding what remains to the current shape is the safer of the two wrong answers.

**The cost is in the tests, and it was predicted.** The suite built synthetic indexes whose row 0 is a pre-cutover row, so under the gate every boundary in those trees goes to zero at once. Prepending the real origin row was tried first and rejected: it shifts every synthetic position by one, which silently rewrites what a dozen positional tests were pinning. `_write_index` instead declares its synthetic file to be this record by repointing the constant, with an autouse fixture restoring it; `_write_foreign_index` is the helper that deliberately does not, and `_index_tree` runs the real file under the real constant.

## What it cost the always-on budget

The lane-heuristic clause puts the `adversarial-review` body at 9,121 against a 9,000 ceiling, and is admitted at 121 characters on the first row of `docs/admissions.jsonl` rather than trimmed to fit. It has no cheaper home: a reference is opened after the lane is picked, and the `records` cell that defines the field is loaded at the close. The draft was cut from 165 characters to 137 before admitting, and the surviving half — *a review that needed its cost was worth it* — is the part that blocks the misreading the field invites. The constant does not move.

## What the convergence changed

Three cold rounds, each landing only new points, which is what said reading was still paying. The first found that the shipped *no arithmetic* sentence forbade the whole change and that the draft named no home at all for the semantics — they existed only in the artifact and in lint error strings. The second found the not-a-target sentence in the wrong file and the label vocabulary not covering its own tree. The owner was asked at the two-round cap he affirmed on 2026-09-03 and directed a third, which returned `would`.

**One point round 3 raised is left open rather than closed here:** a cited site *outside* this repository has no lawful `target`, since `repo` is the residual of this tree. The near cases — the affirmed brief, the artifact itself — are absorbed by `record`'s leading test. If a review sustains a high on a site this vocabulary cannot label, that is a defect in the vocabulary and belongs on the board, not a value invented at the close into a record nobody may correct.

# The release report

**Loaded when** composing a change's release report, or deciding what goes first in it.

**The release report is the owner's surface at release, so it opens with what needs them and puts everything settled by checks out of the way.** What they read is what still needs a decision or their judgement: whether their decisions did what they expected. Everything else stays findable without being in their path.

## Its order

1. **Title line and plain brief.** The title line is `**Release report: #N → PR #M** at head <sha>`. The plain brief takes `the-brief.md`'s form, and its first sentence says what needs the owner's decision, or that nothing does. Where `the-brief.md` asks a brief to name a ruling it applies, that line follows this one.
2. **Needs your decision.** Directly after the plain brief: every reviewer finding dispositioned `yours — in the release report`, every open ask on the change, the `filing` cell's one release-report purchase ask, and every bypass of a required stage or gate recorded in the `**Path departures:**` paragraph (`change-paths.md`), any restore decision a builder-damage launch account leaves with the owner (the `work` cell's launch-findings reference), and any merge block named because required review threads stay unresolved (the connected-reviewer disposition rule) — or the word "nothing". An ask keeps its own form and mark, which are `the-ask.md`'s, and the purchase ask keeps the `filing` cell's; the report orders and links them, never restating their forms. A bypass or a merge block is listed so the owner merges knowing it: their answer is the merge decision itself, which is already theirs, so it takes no ask form.
3. **Your decisions, and what they did.** One entry per affirmed row whose owner cell names something the owner will see or judge. Each entry carries:
   - what they decided — the row, in a phrase;
   - what they expected — the owner cell's text before `Checks:`, quoted, never the checks;
   - where it landed — links into the code at the report's head;
   - evidence of what it did — output and screenshots from the use runs, the use consumer's observations wherever a use ran, measurements, and how the code reads, from the cold reader's account of the change's reading for its reasons (`the-stretch.md`);
   - one verdict: **as expected**, **different** and how, or **not shown**.

   No `Checks:` text appears in an entry; a row's named checks and their outcomes sit only in the collapsed section, under that row, because the owner agreed them at design and need not read them again. A row whose owner cell is `unchanged` or names nothing to judge appears only there. A brief affirmed before rows named their checks is read the same way, its owner cell standing whole as the expectation.
4. **Upstream misses.** Beside the entries: each call made after affirmation that the fork test this cell states would have made the owner's, but that was made without reaching them, with where it was made. They are listed only; what follows from a miss is not this reference's to say.
5. **Worth a look.** At most three excerpts, each cut from the added or changed lines of the change's diff at the report's head (`git diff <base>...<head>`) rather than retyped, and each carrying a link to its lines and one line on why it is worth reading. The holder chooses them from the nominations in the cold reader's account.
6. **Settled by checks.** One collapsed `<details>` section, grouped by affirmed row. First, each row's checks and their outcomes: the row's named checks where it names them, and the criterion results with their evidence. Then, for a change that wrote no decision record, the cold reader's account of why the change was made, which judges whether it decided nothing and is understood without its brief (`the-stretch.md`). Then the process evidence: the required gate and its verdict, answered reviewer findings, comments from other authors noted unanswered (`change-paths.md`), uses, reach, size, cost (with keep-warm as its own line, carrying its price and outcome counts, and the turns that reloaded anyway, both from the cost report's `keep_warm` and `reloads`), the cold readings, the launch write bound the launch-findings reference has the report quote, every GitHub write granted to a step with the brief comment and row it rests on and every write a step was refused (the `grants` and `refusals` of `run release-report`'s `github_write_bound`, which says `unknown` when a launch's record could not be read), and departures that need no decision. The cold readings are listed one per reading, rereads included: its head, whether it read the whole change, the flags it raised, which the holder routed and which it accepted with each acceptance's reason, and its model, effort, duration and list-price cost; `run release-report` returns all but the cost under `cold_readings`, from the readings and `open` comments the gate holds, and the cost comes from that run's dispatch record. The owner judges the holder's acceptances from this list. Check outcomes and process evidence never appear above this section.

## On the builder route

**On the builder route (`the-stretch.md`), `run release-report` adds `builder_route` to its payload, and the report places it within the order above.** The holder gives each decline its view, `agrees`, `differs` or `cannot-judge`, because where a decline goes turns on it; a decline given no view needs the owner.

- **Needs your decision** adds, in this order:
  1. the final-pass block: each spot check the holder made and what it found, what it sent back and what came of it, and what stays open after the send-back;
  2. each decline, from a check report or a connected reviewer, where the holder's view differs from the builder's or the holder can't judge it;
  3. every builder decision that would change a brief row;
  4. a handoff whose text differs from the composed one (`handoff_plan` reads `differs`, holder-written or altered);
  5. one line counting the remaining declines and pointing at their list.
- **Declined findings** is an uncollapsed entry directly after "Your decisions, and what they did". It lists every other decline, check reports' and connected reviewers' alike, each with the builder's reason and the holder's view, and declines sharing a reason are listed together under it. No decline appears only in the collapsed section.
- **Settled by checks** adds the route and its reason, the cost split (the holder before the handoff, the holder after it, and the builder), every limit above its default with its reason, each catch-up resume, and each row check's reading.

The payload's other fields (the readiness reading, what was owed at each ready record, the send-back, the holder's quiet and its launches after ready, plan-writer launches and refusals) are the evidence these placements draw on, and stay in the collapsed section.

## What it leaves where it is

**The pull request body keeps its existing record and its `**Path departures:**` paragraph** (`change-paths.md`), because the report is the owner's surface and the body is the change's record.

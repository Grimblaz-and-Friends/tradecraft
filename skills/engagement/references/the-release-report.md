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
6. **Settled by checks.** One collapsed `<details>` section, grouped by affirmed row. First, each row's checks and their outcomes: the row's named checks where it names them, and the criterion results with their evidence. Then, for a change that wrote no decision record, the cold reader's account of why the change was made, which judges whether it decided nothing and is understood without its brief (`the-stretch.md`). Then the process evidence: the required gate and its verdict, answered reviewer findings, comments from other authors noted unanswered (`change-paths.md`), uses, reach, size, cost, the cold reader's cost per run with its model, effort and duration, the launch write bound the launch-findings reference has the report quote, and departures that need no decision. Check outcomes and process evidence never appear above this section.

## What it leaves where it is

**The pull request body keeps its existing record and its `**Path departures:**` paragraph** (`change-paths.md`), because the report is the owner's surface and the body is the change's record.

# D-338: A routing criterion names which quantity it claims, and reach is falsifiable only where nothing else routes the situation

**Status:** Accepted 2026-09-03 (PR #338)

**Evidence.** Two runs, neither commissioned by this change and neither re-run for it: [#272's cold-seat A/B](https://github.com/Grimblaz-and-Friends/tradecraft/issues/272#issuecomment-5500944347) and [#255's five-arm harness run](https://github.com/Grimblaz-and-Friends/tradecraft/issues/255#issuecomment-5486527919). The brief and its affirmation are on [#272](https://github.com/Grimblaz-and-Friends/tradecraft/issues/272#issuecomment-5520329963); the settled artifact is [there too](https://github.com/Grimblaz-and-Friends/tradecraft/issues/272#issuecomment-5520387705).

## The condition

`skills/engagement/SKILL.md` carried the general rule — *"A criterion a plausible wrong implementation would also pass measures nothing"* [D-166] — and no instance of it. **PR #269's criterion 1 was written under that rule and passed a check that could not fail.** It read *a session whose only job is reconciling what an automated reviewer posted on a pull request reaches this cell*, named its falsifier as a cold seat holding only the roster, was affirmed by the owner, run, and marked met. That PR's terminal ruling recorded it as a criterion a plausible wrong implementation would also pass, and promoted the recorded finding that became #272.

The session that wrote it had the general rule loaded. That is the whole argument for an instance: a rule stated only in the abstract was applied by a competent session and did not catch the case it exists to catch.

## The decision

**One bullet, immediately after the rule it instantiates.** A criterion claiming a piece of text routes a reader names **which of two quantities** it claims — that a reader *reaches* the destination, or that a reader's *stated reason* names the text. **Reach is falsifiable only where nothing else the reader loads routes that same situation to the same place**, and two routes are named because both have actually defeated a run: the destination's own summary sentence sitting above the trigger under test, and an always-on surface naming the destination. **Warrant stays falsifiable where reach does not**, so the rule hands over a replacement rather than removing a form and leaving nothing in its place.

**The rule is keyed to the second route, not to the quantity.** This is the change's central judgement, it was the owner's ruling, and it is the one thing a later session is most likely to flatten back.

The disposition that scoped this work proposed *"a routing criterion is falsifiable only as a warrant … and never as reach."* **That wording is false against this repository's own second measurement.** #255's port run reached the standard's file **5/6 in the port arm against 0/6 in the control** and 1/6 with a direct cell name — a reach readout that separated cleanly. What killed reach in #272's run was not the quantity: it was that the description's opening summary still routed `substrate` after the trigger clause was deleted, so **both arms carried a working route**. The same defeat is visible in #255 as a control rather than as a surprise — its `brief` case saturated **5/5 in every arm including the negative control**, which that report attributes to the always-on charter sentence naming `engagement`: *"Every arm therefore had a working route and the case could not discriminate."*

So the two runs do not disagree. They are the same mechanism observed with and without a second route, and the rule states the mechanism rather than one of its outcomes.

## What was rejected

**A flat ban on the reach form** — *never write "a session reaches this cell"; write the warrant instead*. It is one clause shorter and needs no judgement from the writer. It was rejected because it would classify #255's port measurement as unfalsifiable, and a rule that outlaws a measurement the repository has already run successfully teaches the next session the wrong thing about its own instruments. Put to the owner as option 2; not ruled.

**Recording the incident and adding no rule**, on the ground that [D-166]'s general rule already covers it. Rejected as the status quo that produced the incident. Put as option 3; not ruled.

**Generalising to any criterion about reader behaviour.** The evidence covers routing — a reader arriving at a destination — and nothing was measured about criteria of other shapes. Generalising from two runs would be the superlative-without-enumeration error [#302](https://github.com/Grimblaz-and-Friends/tradecraft/issues/302) has already caught once here.

**Deleting `substrate`'s `when choosing a language for new code,` clause**, which #272's spike priced at 39 always-on characters at no routing cost. [D-320] reads the same evidence the other way — keep on any citation, and every treatment seat cited it — and scoped its own rule to fence clauses expressly to avoid the collision, leaving no rule for positive triggers. **That contradiction is [#325](https://github.com/Grimblaz-and-Friends/tradecraft/issues/325)'s sixth question and is not settled here.** This entry licenses no deletion.

**A third run.** The premise this rests on is that the second route is what discriminates, and the two existing runs exercise it in opposite directions. A run built to re-measure what they agree on would spend seats to confirm what was already reported.

## The placement call, and what it cost

**The bullet is in the body, not behind a pointer.** `engagement` has the largest body in the tree and no budget — the cell-body rows of `python tools/lint.py`, run from the repository root. Against that: the acceptance-criteria list is five items and all five are in the body, `skills/authoring/SKILL.md` sheds depth to `references/` on a disqualifier rather than on a size, and an instance separated from the rule it instantiates is one a reader meets without the rule that explains it. Moving the whole list behind a pointer is a restructure of the cell and was not in this change's boundary.

## What this change does not decide

**The instrument's own rules stay with the instrument**, on #325 — the planted control, the void rule, keep-on-any-citation and the forced per-cell verdict. This entry says when a criterion is falsifiable; it does not say what a licensing run must carry, and a clause here that constrained how an A/B is built would land the same obligation in two cells.

**Nothing the charter names moves.** Whether an always-on surface should stop naming cells outright is [#303](https://github.com/Grimblaz-and-Friends/tradecraft/issues/303)'s, and #255's evidence runs the other way there — the charter sentence was the one pointer followed in every arm, 5 of 5, where a direct cell name in a body routed 1 of 6.

One cold-seat verdict, `would`, on sha256 `a371ae4b39d036406a707d5aa5e406b9b27640fcc486d5983d303bb2b8246ef4` / 9,564 bytes. It confirmed the base commit on its first read and returned two non-adverse observations — a figure stated as a number where the cell being edited requires the command that derives it, and a grep whose output was wider than the sentence above it. Both were repaired under the no-fresh-reading carve-out, changing no claim the verdict turned on.

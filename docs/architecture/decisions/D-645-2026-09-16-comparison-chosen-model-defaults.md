# D-645 — Standing model defaults follow comparisons, not price rank

**Landed by** [PR #645](https://github.com/Grimblaz-and-Friends/tradecraft/pull/645). Closes [#604](https://github.com/Grimblaz-and-Friends/tradecraft/issues/604). Governed by the [implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/604#issuecomment-5706890208) and its [affirmation record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/604#issuecomment-5706897382), affirmed on 2026-09-16. Evidence about the first built tree is pinned at `066c9d797963b9837973ddd4736cdc06c7e87de7` over base `c679fd520ee690e524c12658639cb1a3813af587`; the launcher comments with their filled `[D-645]` citations are pinned at `ea06a68d6c7c23a40b27c5515b46f0a7c0455c6a`.

## What was decided

**A standing default is chosen by what comparisons have shown rather than by a model's price rank.** A comparison that separates two models lets the better result earn its cost. A comparison that separates nothing makes the cheaper model the default and leaves the dearer model to a change that records its case. Where no comparison exists, the existing default stands and is named as un-compared: that describes the evidence and supplies no finding in its favour.

The review roster's instruction to run every seat at *“the strongest model tier the runtime's budget bears”* had to leave whole. Narrowing it would have preserved the premise that tier or affordable price selects a model before evidence does, while the new rule governs implementers as well as review seats. The `engagement` cell therefore owns the shared choice, and the roster points there while retaining only its scarce-advantage staffing rule. The deleted sentence's owner-override clause was already carried by `engagement`; keeping a narrowed copy would have left two owners for the same exception.

That surviving concentration sentence changed its trigger too: scarcity now modifies the demonstrated advantage — how often or where it exists — rather than the budget available for a top-tier model. The allocation that follows still concentrates such an advantage in `cold-read` and judge roles.

**A separating comparison outranks a non-separating one because failure to detect a difference is not a finding that none exists.** This clause was absent from the first draft. Running that draft over the evidence exposed an unresolved Sol/Terra conflict: the owner's code pilot detected no quality separation, while [D-617](D-617-2026-09-14-source-comparison-receipts.md) separated their artifacts and chose Sol. Without a tiebreak, the same rule could retain the cheaper model from the pilot or choose the better artifact from D-617. Testing the rule before asserting it produced the precedence clause.

## What the comparisons established, and what they did not

[PR #602](https://github.com/Grimblaz-and-Friends/tradecraft/pull/602) records a blind Astra/Sol artifact comparison from identical assignments and trees. The seat selected Sol because its artifact was executable against this repository's mechanisms where Astra's resolved the same questions by declaring them out of scope. It also found no material factual error in either draft and called the margin real but not a blowout. The result supports a preference on artifact authorship; it does not establish a universal capability gap. For that turn Sol cost 57% more than Astra despite a 60% lower unit price because it used four times the input and three times the output. The different currency does not dispose of that datum: subscription allocation tracks token volume, though one artifact, one seat and one change is a data point rather than a measurement.

[D-617](D-617-2026-09-14-source-comparison-receipts.md) records the blind Sol/Terra artifact comparison at `xhigh` from a byte-identical dispatch. Terra produced the better-evidenced artifact, having run the page-loop contract live; Sol produced the better-engineered artifact and was chosen. The owner ran implementation on Terra regardless. That split is why the entry records the selection rather than flattening it into a claim that Sol was better on every dimension. Sol cost 1.99× Terra while total input differed by 3.468% and Sol emitted 1.33× the output tokens, so the gap was almost entirely the rate card. Near-identical token volume at nearly twice the rate-card price is the record's clearest evidence that rate-card cost and allocation burn can rank differently.

These runs also discharge [D-601](D-601-2026-09-13-dispatch-settings-and-evidence.md)'s open statement that the Astra/Sol artifact comparison remained unrun and unanswered. They answer the deferred comparison; they do not reverse D-601's decision about dispatch settings and evidence.

The owner's code-task pilot recorded on [#604](https://github.com/Grimblaz-and-Friends/tradecraft/issues/604) detected no separation among Astra, Sol, and Terra on its implementations and planted-defect reviews. Non-detection is narrower than equality. Together the sources support Sol as the best-evidenced standing Codex default, with a per-change override for work that can make a recorded case for Astra or another model.

`opus` stays as the Claude default while being named as un-compared. No run has compared it with a Claude sibling, and deleting the roster's strongest-tier sentence removed the only justification it ever had. Moving a judging default on no evidence would spend possible quality on an unsupported inference, so the value stays and the un-compared clause makes its inertia explicit. No preference for `opus` is claimed.

## The cost that counts and the half of #606 this buys

**The relevant cost is what the owner pays, which may differ from the rate the runtime advertises.** The comparison records use rate-card equivalents; those figures rank options only as far as rate-card equivalence tracks the owner's subscription allocation burn. The owner's observation that Astra drains that allocation faster than its advertised price implies is therefore relevant to the default even though the runtime record cannot measure it.

This lands the statement arm of [#606](https://github.com/Grimblaz-and-Friends/tradecraft/issues/606): the record's own prose now says that comparison money is a rate-card equivalent and that subscription burn is outside the bundle. It does not add a conversion rate, measured ratio, field, or extractor. The measurement arm remains whole, as the [#606 status comment](https://github.com/Grimblaz-and-Friends/tradecraft/issues/606#issuecomment-5706905686) records; closing or rescoping that issue remains the owner's release call.

## Why the evidence sits at the constants too

The shared rule belongs in the `engagement` cell, but a maintainer changing a launcher constant may never load that cell. Each constant therefore names what its present value rests on: Sol's two blind artifact preferences and the pilot's non-separation on the Codex side, and the absence of any sibling comparison on the Claude side. The comment is at the action surface so changing a value makes the evidential obligation visible where it can be discharged.

The built implementation is read from:

- `skills/engagement/references/dispatch-records.md` at `066c9d797963b9837973ddd4736cdc06c7e87de7` for the shared default and cost rule.
- `skills/adversarial-review/references/roster.md` at `066c9d797963b9837973ddd4736cdc06c7e87de7` for the deleted tier premise, the owner pointer, and the scarce-advantage staffing rule.
- `lib/dispatch_seat.py` and `lib/dispatch_implementer.py` at `ea06a68d6c7c23a40b27c5515b46f0a7c0455c6a` for the defaults and evidence comments with their filled decision citations; `066c9d797963b9837973ddd4736cdc06c7e87de7` introduced the same values and comments with landing placeholders.
- `lib/tests/test_dispatch_seat.py` at `066c9d797963b9837973ddd4736cdc06c7e87de7` and `lib/tests/test_dispatch_implementer.py` at `066c9d797963b9837973ddd4736cdc06c7e87de7` for the default-launch assertions and the non-default Astra override.
- `.claude-plugin/plugin.json` at `066c9d797963b9837973ddd4736cdc06c7e87de7` for the shipped version.

## What the cold seat left non-blocking

The cold seat that settled the artifact recorded three observations for the pull request and this entry rather than reopening the artifact:

- **The roster edit is one sentence wider than the implementation brief's Builder cell describes.** Deleting the tier sentence also required repairing the dependent sentence's *top tier* premise. The seat ruled that repair inside the briefed scope rather than an unbriefed choice.
- **Criterion 2's reach clause is weakly falsifiable.** The `engagement` description and its depth index already route a staffing session to `dispatch-records.md`, which can mask the difference made by the roster pointer. The prose edits still deliver the reader cell.
- **“Outside the bundle by the rule below” relies on an adjacent rather than exact noun.** The rule below names a price table, a subscription charge, and a reconstructed invoice rather than allocation burn. Allocation burn remains outside what the bundle holds, so the clause is true while its locator is less exact than its wording suggests.

## What was deliberately not done

- **No subscription-burn measurement** — no conversion rate, measured ratio, new field, or extractor. #606 keeps that arm.
- **No Terra deferral.** D-617 supplies a separating comparison and closes the default question in Sol's favour while preserving Terra's better-evidenced result and the owner's implementation choice.
- **No re-check date.** An un-compared default carries its evidential status without pretending a reliable calendar follows from the vendor's undocumented allocation accounting.
- **No Claude comparison and no pitch to run one.** `opus` remains explicitly un-compared.
- **No annotation of the published figures on #592, #596, or #601.** Those records are not maintained.

## Evidence and re-derivation

The implementation surface is given by `git diff --name-only c679fd520ee690e524c12658639cb1a3813af587 066c9d797963b9837973ddd4736cdc06c7e87de7`; its content is given by `git diff c679fd520ee690e524c12658639cb1a3813af587 066c9d797963b9837973ddd4736cdc06c7e87de7 -- .claude-plugin/plugin.json lib/dispatch_implementer.py lib/dispatch_seat.py lib/tests/test_dispatch_implementer.py lib/tests/test_dispatch_seat.py skills/adversarial-review/references/roster.md skills/engagement/references/dispatch-records.md`. The filled launcher citations are given by `git diff 066c9d797963b9837973ddd4736cdc06c7e87de7 ea06a68d6c7c23a40b27c5515b46f0a7c0455c6a -- lib/dispatch_seat.py lib/dispatch_implementer.py`. Run `python tools/lint.py`, `python tools/check_version_bump.py --base c679fd520ee690e524c12658639cb1a3813af587`, and `python -m pytest lib/tests/test_dispatch_seat.py lib/tests/test_dispatch_implementer.py` in a checkout at `066c9d797963b9837973ddd4736cdc06c7e87de7` to re-run the governing-prose, shipped-version, and launcher checks. No derived output is frozen here.

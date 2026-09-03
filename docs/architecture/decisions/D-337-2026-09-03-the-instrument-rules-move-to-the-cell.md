# D-337: The cold-seat A/B's instrument rules move to the cell that owns the method, split by what each rule is for

**Status:** Accepted 2026-09-03 (PR #337)

**Evidence.** The settled pre-implementation artifact and the affirmed brief it carries: [artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/325#issuecomment-5520123176), [brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/325#issuecomment-5519854757), [affirmation](https://github.com/Grimblaz-and-Friends/tradecraft/issues/325#issuecomment-5519856156). The review's final report, its terminal rulings and both experience session notes: [report](https://github.com/Grimblaz-and-Friends/tradecraft/pull/337#issuecomment-5521384705). Figures are `python tools/lint.py` and `python tools/figures.py`, on the tree each names.

## The condition

[D-320](D-320-2026-09-02-the-fences-are-measured-and-nearly-all-of-them-are-live.md)'s fence run established four rules that decide whether a cold-seat A/B's result can be trusted, and they were written down only in that entry. **A decision entry informs and never binds**, so a session opening `skills/spikes/SKILL.md` to run one found none of them — and the same run had shown that **a malformed docket item reads exactly like a dead clause**, which is the failure those rules exist to separate. `grep -rn` over `skills/` for *planted*, *is void*, *uninformative*, *keep-on-any* and *per-cell verdict* returned nothing at the merge base.

## The decision

**The scope splits by what each rule is for, which is the owner's ruling and the one fork this change carried.** The planted control, the void rule and the forced per-item verdict bind **any** cold-seat A/B whose finding could be a null, because they are what makes a null readable at all. Keep-on-any-citation binds **only** a run whose output licenses a deletion, because it is an asymmetry that means nothing where one arm's silence removes no text.

The alternatives were argued and rejected. **All four binding only a deletion-licensing run** leaves an A/B run for any other purpose reading nulls with nothing to say they are uninterpretable — and the incident behind this change, a malformed item reading as a dead clause, is not deletion-specific. **All four binding universally** makes keep-on-any-citation a rule about nothing on most runs, and a list carrying such prose trains its reader to skim.

**Placement follows the same cut and is the session's, not the owner's.** Rules every run of that kind needs sit in the cell body; the deletion conditions shed behind a pointer into `skills/spikes/references/licensing-a-deletion.md`, the cell's first `references/` file.

**Two rules landed that the brief did not name, both the session's and both reported as such.** *What counts as a citation* landed because keep-on-any-citation is inoperable without it — a session told one citation keeps has no way to score one. And the **near-miss docket rule** landed scoped to the same runs as the general three, because an item that is not a near-miss is what made a live clause read dead, and that failure is not deletion-specific.

**The forced walk runs after the unprompted question, never instead of it.** The cell already told a session to ask what a seat would do before asking what the rule says; a forced walk asked first hands the seat the label. Landing D-320's rule flat would have contradicted the sentence above it.

## What the review changed, and the one thing it turned on

Five seats, a defence, a judge, then a fix batch, a prosecution look, a second defence and a terminating ruling. **Nine sustained highs**, of which four failed the purpose statement in its own words: a whole-class run could license a deletion, a run dispatched inside this repository read valid while both arms were the same arm, a run that separated cleanly was discarded, and a void run was never *shown* to be void because nothing reported it.

**The one it turned on was the owner's ruling itself.** The change's commit message stated the scope — *"bind any cold-seat A/B whose finding could be a null"* — and that clause was **nowhere in the tree**; the properties landed unconditional. Two seats and the defence reached it independently. **The merge dropped it from both its lists**, and it was recovered only because the defence ran its own read of the seat reports rather than taking the merge on trust. That apparatus fact is recorded, with its promotion condition.

**Two errors this entry retracts rather than leaves standing.** The merged finding list asserted that the cell *"prescribes the arrangement that collapses the arms"*; it does not — the detached-worktree sentence is scoped to a different kind of spike, and the defect was a missing warning. And it presented as fact that #303 is a whole-class ablation by construction, which is an inference the source entry does not state.

**The instrument's own ceilings did not all travel, and that is deliberate.** D-320 records that a clause whose substance a seat can reconstruct from the cell name alone can never clear this instrument. What landed is the disclosure — *say which arm a keep came from* — rather than a rule change, because stopping ablated-arm citations from counting changes the instrument and is the owner's. That, whether the record's own citations count as keeps, and whether the void gate should read every arm, went to [#340](https://github.com/Grimblaz-and-Friends/tradecraft/issues/340) as one question with three limbs.

## What use found that reading could not

Two experience sessions, and the second changed the outcome. The first found the record-search gap — nothing told a session to look for a prior citation before spending six seats — which a real consumer built by analogy from `filing` and named as the one thing that should land as text.

The second **evidenced acceptance criterion 5, which the terminal stage had refused to record as met**: the first consumer reached the reference file from a directory listing before reading the pointer, so the criterion was unfalsified rather than met. The second reached it **from the body**, on a run licensing no deletion — which the pre-fix load condition would have shut, so the fix is why the criterion is evidenced.

It also **falsified criterion 7's headline while leaving its stated falsifier unmet**: the cell's rules describe an ablation, and the shape its own trigger names first is a substitution. Every downstream rule assumes one arm lacks the text, so the consumer translated the keep rule and said the translation was its own. That is [#342](https://github.com/Grimblaz-and-Friends/tradecraft/issues/342).

## Rejected

**Amending `skills/authoring/references/routing.md`'s grounds for deleting always-on prose** — the affirmed brief put it out of scope, and it stays recorded. **Fixing #321's trigger/fence contradiction here**, a defect in the same file but a second change under one brief. **Setting a budget for `spikes` in `CELL_BODY_BUDGET_CHARS`**, on the standing ground that a number for a cell nobody has argued about is a ruling arriving as a constant. **Pointing `spikes` at the isolation procedure**, which fires `sideways-dep` twice against a clean-tree control of zero findings — the prohibition was probed, not assumed, and the routing question went to [#341](https://github.com/Grimblaz-and-Friends/tradecraft/issues/341). **Reverting the near-miss limb's widening**, which would reintroduce a defect with a recorded incident in order to close one with none. **Spending the second review cycle** on five word-level substitutions a terminating ruling had already written out verbatim.

## The cost, stated because the next change to this cell inherits it

The cell body went from 9,619 characters to 12,857 — **+33.7%**, moving `spikes` from fifth-largest of thirteen to **second**, with no budget — plus a 2,455-character reference file. The round-one ruling bound its fix batch to an accounting of about +300 characters net; the batch came in at roughly **five and a half times** that, because the two additions the judge rated most serious were the two its estimate had not priced. `python tools/lint.py` prints the current figure beside every other cell.

**No always-on surface moved**, on four independent runs at both the merge base and the head: Claude Code 16,237, Codex 16,226, an adopter 11,046. That is the whole reason these rules could be stated at the length they needed — they sit below the surface every session and every adopter pays for.

# D-135: The freeze admits a repointed reference, and a guard makes it fire

**Status:** Accepted 2026-08-23 (PR #135)

## Context

An entry is frozen on landing. [D-74](D-74-2026-08-19-constitutional-reset.md) has support for that — the empirical record showed amendments grew the statute on every simplifying PR, and this repo's own ledger carried a per-finding resolution far finer than the decisions it fed, making the record itself a workload. Both diseases stay cured here.

The freeze also barred repair. The doctrine tells a session to *"follow the citation before changing what it governs"*, and a moved file leaves that instruction pointing at nothing. PR #104 moved the spikes reference out of `authoring` and stranded three citations; PR #132 moved it again the next day, stranding three more and authoring a fourth that was dead on arrival. Neither repointed anything, because neither was permitted to.

**The census, and how to re-derive it.** Empty both recorded sets in `tools/lint.py` and count what `check_entry_references` reports, per tree:

| tree | occurrences | distinct (entry, reference) pairs |
| --- | --- | --- |
| `03acc1a`, before PR #132 | 11 | 10 |
| `15b13cd`, the tree this change was built against | 15 | 13 |
| this change, after the carve | 13 | 12 |

The thirteen remaining occupy thirteen rows, because the record is keyed by line.

## Decision

**The freeze admits one edit that changes no claim: repointing a reference whose target moved, to its current location.** Surrounding prose does not move and nothing is added or removed. A sentence that quotes or characterises its target is not a bare locator, so **where repointing would leave that sentence untrue of the target at its new home, the reference stays as it is** — and where the sentence survives the move, it is repointed. The test is truth, not the presence of a characterisation; the carve below is the worked example.

**The mover pays.** The repair rides with a change that moves the target and covers every reference to it, whichever earlier move stranded it — never as a change of its own. **Moving a target and rewriting the text an entry quotes is one change for this purpose:** split across two, they end in a live path over a false quotation, which is worse for a reader than the dead path it replaces, because a dead path announces itself and a false one does not.

**Where there is nothing left to repoint** — the target retired rather than moved, or a move that would falsify the sentence — the reference is recorded with its reason. Without that disposition the check reds with no lawful answer, and a guard that blocks lawful work fails as hard as one that passes unlawful work.

**The rule does not ship alone.** `tools/lint.py` resolves the references a decision entry writes in backticks or a markdown link. Three things are deliberately not references: a bare filename, an unbackticked path, and a slash-joined token whose shape claims no path — no known extension and no first segment this repo declares as a root, which is what keeps `A/B` from reading as a file. A reference is lawful four ways: it resolves, it is pinned to the commit it shipped at, it is in the baseline of what was already dead, or it is recorded as unrepairable since. The guard reports a recorded reference that has come back to life, so the record cannot rot; that it only ever *shrinks* is held by the suite, which pins its membership.

**`skills/authoring` gains the prevention half:** a frozen document pins its evidence to the commit it shipped at, and one carrying counts carries the query that produced them.

**The carve**, authorized by the owner on 2026-08-23 and binding mover-pays from here: `D-99:37` and `D-119:66`.

## What was left standing, and why

- **`D-119:19`** quotes *"a mechanism nobody has executed"* — a phrase PR #132 deleted while moving the file it cites. Repointing would leave the sentence quoting words its target does not contain. **PR #132 is the incident that admitted the quotation clause**: the spike could not have found it, because its rehearsal moved the file without rewriting it.
- **`D-80:15`, `D-102:50`, `D-104:36`, `D-132:19`** each state where the file *was* at some past moment. Repointing falsifies the sentence rather than repairing it.
- **`D-53`'s four.** Two name files PR #74 deleted; two name files it **renamed** to `-archived`, and those are left because `D-53:15` calls its target the *"always-current statute"*, which an `-archived` path would contradict.
- **`D-69`'s two dead links** were in the carve the owner approved and were dropped from it, recorded as a session narrowing with its reason. Nothing directs a reader into the pre-reset archive to act, so the repair buys a reader nothing. Note what this is **not**: being a frozen archive makes `D-53`–`D-69` non-binding, not unrepairable, and no rule seals them against a repoint.
- **`D-90:25`** is a path that was never in this repository. **`D-99:37`** also names an agents directory a spike created and did not commit; it was recorded here and then dropped, because the shape filter stopped reading `.claude/…` as a path claim at all. That was not tidying: the directory is untracked and ungitignored, so a session that created it locally got a different answer from `python tools/lint.py` than CI did — and the local answer told it to delete a row that CI needs. A mandatory gate may not have two answers. Naming it here without backticks is deliberate — a bare mention claims nothing about where a thing lives, and the guard fired on this entry's own draft when it carried the path instead.

**Where this change departed from the spike.** Both mover seats declined `D-99:37`, on two grounds: that the repair belongs to the change that moved the target, and that repointing a sentence stating where something was originally placed changes a claim. The first is superseded by the rule adopted here, which covers every reference to a moved target whichever move stranded it. The second was weighed and rejected on the text: `D-99:37` says the spike is *declared open under* that path and sends a reader there to work on it, and the abandonment route it points at is still in the target — so the sentence survives the move. Both carve targets carry a characterising clause, and both characterisations were verified against `skills/spikes/SKILL.md` before repointing; neither is a bare pointer.

## Evidence

A [six-seat, three-arm cold A/B spike](https://github.com/Grimblaz-and-Friends/tradecraft/issues/108#issuecomment-5387212629), run before this was written rather than after. **Zero widening events across six seats.** One audit seat catalogued ~101 verbatim quotations in landed entries that no longer match the tree and edited none; both audit seats refused repoints that would have altered a claim. The mover arm used the permission and stayed inside it, both seats repointing the same two path tokens in `D-119` and nothing else in any frozen entry.

It also established the rule is **inert alone** — four seats across two dockets independently concluded the stranded references were unreachable — and two seats independently proposed the guard, which is why the check ships here instead of being routed.

**The spike held, and it did not test three things**: whether the permission stays narrow over time, whether it holds under schedule pressure or for an author repairing its own entry, and the guard's precision. The third was routed to this change's acceptance criteria, and the review that judged them found real defects in it — so the routing was necessary and was not sufficient on its own.

The affirmed artifact and its affirmation record are on [#108](https://github.com/Grimblaz-and-Friends/tradecraft/issues/108#issuecomment-5387850968).

## Rejected

- **Leaving the freeze absolute.** It leaves a reader the doctrine sends to a citation arriving at nothing, with no lawful repair. It also blocks the repo-wide link resolution [#87](https://github.com/Grimblaz-and-Friends/tradecraft/issues/87) contemplates, whose failures would land in frozen entries — though not [#109](https://github.com/Grimblaz-and-Friends/tradecraft/issues/109), whose citing surface is shipped prose and never frozen.
- **Errata by appendix** — an append-only dated errata section on landed entries. This is the amendment disease with a new name; an errata section is where an argument grows, and it grows the document D-74 froze to stop growing.
- **A general correction category.** "Correction" cannot be bounded — every fuzzy edge widens under pressure. *Repointing a reference* and *carrying your query* are acts, and acts can be bounded.
- **Shipping the repointing rule and routing its guard to a later change.** The spike measured that rule inert without a mechanism: no change would ever again be the mover for the already-stranded references, so nothing would have fired. That argument is specific to this rule and does not carry to the two prevention rules in `skills/authoring`, which bind at authoring time on a party who is present — but neither has a mechanism either, and this entry's own first draft broke the carries-the-query rule in the same commit that shipped it. They are shipped as prose knowingly.
- **Recording the strand in the new entry instead**, the precedent [D-97](D-97-2026-08-21-dispatch-contract-restated.md) set in *"A citation this change strands"*. Cheaper, and already house practice, but it does not help the reader the doctrine actually sends: someone following `D-99`'s citation lands on nothing and has no way to know another entry discusses it.

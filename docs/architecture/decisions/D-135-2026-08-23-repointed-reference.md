# D-135: The freeze admits a repointed reference, and a guard makes it fire

**Status:** Accepted 2026-08-23 (PR #135)

## Context

An entry is frozen on landing. [D-74](D-74-2026-08-19-constitutional-reset.md) has measured support for that — amendments grew the statute on every simplifying PR, and the predecessor's per-finding resolution made the record itself a workload. Both diseases stay cured here.

The freeze also barred repair. The doctrine tells a session to *"follow the citation before changing what it governs"*, and a moved file leaves that instruction pointing at nothing. PR #104 moved the spikes reference out of `authoring` and stranded three citations; PR #132 moved it again two days later and stranded two more. Neither repointed anything, because neither was permitted to.

The census at fix time, so a later reader re-derives rather than trusts: `python tools/lint.py` with `BASELINE_UNRESOLVABLE` emptied reported **fifteen occurrences across twelve distinct (entry, reference) pairs**.

## Decision

**The freeze admits exactly one edit: repointing a reference the entry already makes, to the same target at its current location.** Surrounding prose does not move, no claim changes, nothing is added or removed. The repair rides with a change that moves the target and covers every reference to that target, whichever earlier move stranded it — never as a change of its own.

**A reference the entry quotes or characterizes is not a pure locator.** Where repointing would leave the sentence untrue of the target at its new home, it stays as it is.

**The rule does not ship alone.** `tools/lint.py` resolves every reference a decision entry makes; a reference is lawful three ways — it resolves, it is pinned to the commit it shipped at, or it is in `BASELINE_UNRESOLVABLE`. That set may only shrink, and a test pins its size so growing it cannot pass unnoticed. The guard is what makes the permission fire on the mover's PR, which is the only moment the repair is lawful.

**`skills/authoring` gains the prevention half:** an entry pins its evidence to the commit it shipped at, and an entry carrying counts carries the query that produced them.

**The carve**, authorized by the owner on 2026-08-23 and binding mover-pays from this entry forward: `D-99:37` and `D-119:66`, both bare pointers to living material. Nothing else in any entry is touched, now or later.

## What was left standing, and why

- **`D-119:19`** quotes *"a mechanism nobody has executed"* — a phrase PR #132 deleted while moving the file it cites. Repointing the path would leave the sentence quoting words its target does not contain. **PR #132 is the incident that admitted the quotation clause**: the spike could not have found it, because its rehearsal moved the file without rewriting it.
- **`D-80:15`, `D-102:50`, `D-104:36`, `D-132:19`** each state where the file *was* at the moment their entry was written. Repointing falsifies the sentence rather than repairing it.
- **`D-53`'s four references** name files this repo deliberately retired in the reset. The entry correctly records what it built.
- **`D-69`'s two dead links** were in the carve the owner approved and were dropped from it. `D-53` through `D-69` are the pre-reset **frozen archive** — a second and stronger seal than the landing freeze — and nothing directs a reader into the archive to act, so the repair would breach the seal to fix navigation nobody uses. Recorded as a session narrowing with its reason.
- **`D-90:25`** is a path that was never in this repository; **`D-99:37`** also names an agents directory a spike created and did not commit. Naming it here without backticks is deliberate — a bare mention claims nothing about where a thing lives, which is the distinction the guard encodes, and the guard fired on this entry's own draft when it carried the path instead.

## Evidence

A [six-seat, three-arm cold A/B spike](https://github.com/Grimblaz-and-Friends/tradecraft/issues/108#issuecomment-5387212629), run before this was written rather than after. **Zero widening events across six seats.** The audit arm declined ~101 stale verbatim quotations unprompted and refused repoints that would have altered a claim; the mover arm used the permission and stayed inside it, both seats repointing the same two path tokens and nothing else in any frozen entry.

It also established the rule is **inert alone** — four seats across two dockets independently concluded the stranded references were unreachable — and two seats independently proposed the guard, which is why the check ships here instead of being routed to a later change.

**The spike held with its untested case named:** it did not test whether the permission stays narrow over time, across many movers, or under schedule pressure. Six disinterested, unhurried seats at one moment is not a longitudinal result, and this entry does not claim one.

The affirmed artifact and its affirmation record are on [#108](https://github.com/Grimblaz-and-Friends/tradecraft/issues/108#issuecomment-5387850968).

## Rejected

- **Leaving the freeze absolute.** It makes the guard in #87 and #109 unbuildable: a check whose only lawful response to failure is "acknowledge and proceed" is not a check.
- **Errata by appendix** — an append-only dated errata section on landed entries. This is the amendment disease with a new name; an errata section is where an argument grows, and it grows the document D-74 froze to stop growing.
- **A general correction category.** "Correction" cannot be bounded — every fuzzy edge widens under pressure. *Repointing a reference* and *carrying your query* are acts, and acts can be bounded.
- **Shipping the rule and routing the guard to #109.** The spike showed the rule alone changes no session's behavior; shipping governing prose that provably does nothing is what this repo exists to stop producing.
- **Recording the strand in the new entry instead**, the precedent [D-97](D-97-2026-08-21-dispatch-contract-restated.md) set in *"A citation this change strands"*. It is cheaper and it is already house practice, but it does not help the reader the doctrine actually sends: someone following `D-99`'s citation lands on nothing and has no way to know another entry discusses it.

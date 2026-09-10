---
name: filing
description: How work gets into the pool and how it leaves — the search that runs before a new issue is created, the ties that put its relationship to the board on the record at birth, the findings a cause carries as comments until its fix disposes of them, and the line between the evidence a filing carries and the design it leaves for whoever picks it up. Use when about to create an issue, when deciding whether something belongs on one that already exists, when deciding whether a finding about governing prose has earned one, or when asking whether anything has got bad enough to put to the owner unasked; not for the pre-implementation artifact written when the work is picked up.
---

# filing

**Purpose:** make a filing useful to the session that picks it up, however long that takes and however far the practice's vocabulary moves in between, and keep out of the pool what nothing acts differently for. **Audience:** any session about to create an issue — usually mid-review or mid-implementation, rarely while writing anything else. **Success:** every filing arrives with its relationship to the board already on the record, and carries evidence that still holds at pickup rather than a design that does not; it lands in the pool with a rating rather than on the board as work nobody decided on; a finding about governing prose that changes nothing a session does takes no number; and one recorded under its cause is disposed when that cause's fix lands rather than lost with it.

## Where this cell's depth lives

- **About to create an issue, deciding whether what you hold belongs on one that is already open, or landing a change that fixes a cause carrying findings recorded under it** → `references/the-search.md`: what the search must cover and the commands that run it, and the five lawful outcomes it decides between — the batch that lands several defects as one number, the two that file nothing, and the disposal a cause's fix owes every finding recorded under it.
- **Writing the tie block of a new issue or an extending comment, or setting or reading the cause link between two issues** → `references/naming-a-tie.md`: the closed tie set and what a ranking does with each row, the sub-issue link and the label that makes it causation, the causal relationship nobody could set and the flagged prose that stands in for it, and where the block goes in the body.
- **Writing the body of a filing or an extending comment, or deciding whether a finding about governing prose has earned a number** → `references/what-a-filing-carries.md`: evidence against design and why the line falls there, the incident-or-run bar and the one measurement it does not refuse, the evidence floor, and the provenance line's closed list of origins.
- **Reading the pool or running its script — rating, listing, shortlisting, the cycle, the push — or asking whether anything has got bad enough to put to the owner unasked** → `references/the-pool.md`: the pull and the push and how a crossing is put, the commands in the order they run, and the accrual, the fade, the tie-break and the assessment that move a filing after it lands.

## A filing searches before it lands

**Nothing is filed before the search that finds whether what you hold already has a home**, and that search decides between five outcomes, two of which create no issue at all. What it must cover, the commands, and the five: `references/the-search.md`.

## A filing lands in the pool, not on the board

**A filing a session made on its own lands in the pool** -- what has been noticed, with its evidence and a rating, and not yet decided on. **The board holds what has been decided on and only that.** An open issue is in the pool unless it carries the framed label, so nothing is written to put it there and a filer who forgets cannot lose one.

**What the owner filed, or told a session to file, is decided work from the start and goes straight to the board.** The line is *who decided*, not whether the thing is a defect or an idea: an owner filing something has already decided it is worth doing, and a pool that made them pull their own filing back out would have them waiting on themselves. So an owner-originated filing is **framed at birth** -- they run `frame` on it, or a session filing on their instruction frames it and says in the issue that it is the owner's ask. **A session may not frame its own filing**, which is the whole of the bar; nothing reads authorship off the wire, and a repository that wants owner filings pooled too says so in its own doctrine rather than in the policy, no command here reading such a field.

**A filing carries two ratings the filer proposes, on separate axes: how severe it is, and how urgent** -- each one label from a set the policy names. Ideas are rated the same way as defects, by what is at stake rather than by what a wrong act would cost, so what waits in the pool is one kind of thing. **The owner confirms ratings only on the few a shortlist puts to them**, never one filing at a time.

**Work leaves the pool two ways, and what is in the pool is what a session noticed rather than what the owner asked for.** The pull and the push, the commands that run them, and everything that moves a filing while it waits are `references/the-pool.md`.

**The script sits beside this file at `scripts/pool.py`, and every path this cell writes is resolved against the directory of the file that names it** -- which is what makes one contract hold in an installed plugin and in this cell's own source repository alike, and is why a file in this cell's depth names the same script one directory up. A session running from somewhere else prefixes the directory of the file the path is written in — this one for a path written here, that file's own for a path written in this cell's depth; [sessions that did not have concluded the script does not exist](https://github.com/Grimblaz-and-Friends/tradecraft/issues/504).

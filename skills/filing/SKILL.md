---
name: filing
description: How a piece of work gets onto the board — the search that runs before a new issue is created, the ties that put its relationship to the board on the record at birth, and the line between the evidence a filing carries and the design it leaves for whoever picks it up. Use when about to create an issue, or when deciding whether something belongs on one that already exists; not for deciding whether a finding is worth filing at all, and not for the pre-implementation artifact written when the work is picked up.
---

# filing

**Purpose:** make a filing useful to the session that picks it up, however long that takes and however far the practice's vocabulary moves in between. **Audience:** any session about to create an issue — usually mid-review or mid-implementation, rarely while writing anything else. **Success:** every filing arrives with its relationship to the board already on the record, and carries evidence that still holds at pickup rather than a design that does not.

## A filing searches before it lands

Before creating an issue, search the board.

**The search is not done until it has been run against the subject's identifier, the mechanism's name, and the defect's own words, over issues in every state, across the whole board rather than a first page.** All three parts are load-bearing and each has been observed failing. One query is not a search: on this practice's own board, searching `check_version_bump` returns neither of the two open issues whose titles *begin* with `check_version_bump.py`, and only the query carrying the extension returns them. Most issue listings default to open-only and to a first page shorter than a working board, and both truncations are silent — so both are set deliberately, and a filing that skips either can report an empty board it never read. A closed issue is the record of what was already decided, already tried, or left behind when its parent closed.

Three outcomes, each lawful:

- **Extend** an **open** issue — a comment, not a new number. A closed match is a tie, never a home.
- **File new with named ties** — the relationship goes on the record at birth instead of being reconstructed at ranking time: [#94](https://github.com/Grimblaz-and-Friends/tradecraft/issues/94) and [#95](https://github.com/Grimblaz-and-Friends/tradecraft/issues/95) were filed by one review against one sentence, neither naming the other, and were merged into a single PR only later.
- **File standalone** — the search turned up nothing that earns a tie.

An extending comment carries the same list and meets the same floor as a filing; its tie is the issue it lands on.

### Naming a tie

**A tie name earns its place by changing what a ranking does with the pair.** That is what keeps the set closed, and the test any addition to it must pass.

| tie | what it asserts | what a ranking does with it |
| --- | --- | --- |
| **same-subject #N** | same file, paragraph, or mechanism | consider one PR for both |
| **same-class #N** | different subject, same defect shape | one remedy may serve both |
| **sequenced-after #N** / **blocks #N** | this cannot start until that lands / that cannot start until this does | order the pair, do not bundle it |
| **supersedes #N** / **superseded-by #N** | this replaces that, or that replaces this, in whole or in part | close or rescope the replaced one |

Both ordering relationships are written in both directions, because a filing that unblocks an existing issue would otherwise have to edit that issue to record the order.

**The verb names and what they assert read the same whether the tied issue is open or closed; the ranking consequence does not.** Against a closed target it is that the issue is read, not that it is scheduled.

Write the ties as the **first element of the issue body, before any heading or prose**, one per line as `<verb> #N — <one clause of why>`. One pair may carry more than one verb, one per line; a relationship none of the four expresses is carried in the same block in prose and flagged as a candidate for the set. Consistent placement is what lets a session ranking the board find ties without reading every body — [#33](https://github.com/Grimblaz-and-Friends/tradecraft/issues/33) named [#20](https://github.com/Grimblaz-and-Friends/tradecraft/issues/20) and [#52](https://github.com/Grimblaz-and-Friends/tradecraft/issues/52) named #35, both truthfully, and both in a closing line nobody ranking the board would reach.

Where the search turned up nothing that earns a tie, the block says so — *no siblings on the board* — because that is a fact a ranking uses. **Do not state that the search was performed.** The ties are its artifact: a filing naming them has demonstrably searched, and a compliance sentence nobody can check buys nothing.

## Creation carries the want; pickup does the work

**Carried at creation:** the want or defect in plain terms; the incident or evidence that makes it real; why it will actually get picked up; the ties above; and what discovery must settle, named as deliberately deferred.

**Left for pickup:** the framing, the options and their argument, the remedy design, the pre-implementation artifact. Filing is not convergence.

**Record what happened; do not decide what to do.** The line is not how much a filing carries but which kind of thing it carries. Evidence — a file and line, a quoted sentence, a count, an incident that occurred — survives however far the vocabulary moves, *provided it is written as an observation anyone can re-run rather than as a citation into vocabulary that can retire*. Design — options, remedy shapes, names for structures — is written in today's vocabulary and decays with it. [#38](https://github.com/Grimblaz-and-Friends/tradecraft/issues/38) is the exhibit for both halves and for the proviso: its frame was dead vocabulary before anyone opened it, and the observation underneath survived only because its successor could restate it against an authority that still existed.

**The floor:** carry enough evidence that a session picking the work up can confirm the problem is real without redoing the discovery that found it.

**A filing does not announce that it is minimal.** Provenance is a different thing and belongs: who directed the work, or which review sustained it, is a fact the picker-up uses.

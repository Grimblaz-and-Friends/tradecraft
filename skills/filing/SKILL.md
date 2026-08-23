---
name: filing
description: How a piece of work gets onto the board — the search that runs before a new issue is created, the ties that put its relationship to the board on the record at birth, and the line between the evidence a filing carries and the design it leaves for whoever picks it up. Use when about to create an issue, or when deciding whether something belongs on one that already exists; not for deciding whether a finding is worth filing at all, and not for the pre-implementation artifact written when the work is picked up.
---

# filing

**Purpose:** make a filing useful to the session that picks it up, however long that takes and however far the practice's vocabulary moves in between. **Audience:** any session about to create an issue — usually mid-review or mid-implementation, rarely while writing anything else. **Success:** every filing arrives with its relationship to the board already on the record, and carries evidence that still holds at pickup rather than a design that does not.

## A filing searches before it lands

Before creating an issue, search the board. Three outcomes, each lawful:

- **Extend** an existing issue — a comment, not a new number.
- **File new with named ties** — the relationship goes on the record at birth instead of being reconstructed at ranking time, which is where it otherwise surfaces: two issues a day apart against the same file, in the same defect shape, discovered as one piece of work only once somebody sat down to order the board ([#20](https://github.com/Grimblaz-and-Friends/tradecraft/issues/20) and [#33](https://github.com/Grimblaz-and-Friends/tradecraft/issues/33)).
- **File standalone** — the search found nothing.

**The search covers issues in every state.** A closed issue is the record of what was already decided, already tried, or left behind when its parent closed, and skipping it costs a filing the arguments it then re-derives; the extra reach is a flag on one command.

### Naming a tie

**A tie name earns its place by changing what a ranking does with the pair.** That is what keeps the set closed, and the test any addition to it must pass.

| tie | what it asserts | what a ranking does with it |
| --- | --- | --- |
| **same-subject #N** | same file, paragraph, or mechanism | consider one PR for both |
| **same-class #N** | different subject, same defect shape | one remedy may serve both |
| **sequenced-after #N** | cannot start until that lands | order it, do not bundle it |
| **supersedes / superseded-by #N** | replaces that in whole or in part | close or rescope the other |

The verbs read the same whether the tied issue is open or closed. Write them in one block directly under the filing's opening, one per line as `<verb> #N — <one clause of why>`; consistent placement is what lets a session ranking the board find them without reading every body.

Where the search found nothing, say so as a fact about the board — *no siblings on the board* — because that is something a ranking uses. **Do not state that the search was performed.** The ties are its artifact: a filing naming them has demonstrably searched, and a compliance sentence nobody can check buys nothing.

## Creation carries the want; pickup does the work

**Carried at creation:** the want or defect in plain terms; the incident or evidence that makes it real; why it will actually get picked up; the ties above; and what discovery must settle, named as deliberately deferred.

**Left for pickup:** the framing, the options and their argument, the remedy design, the pre-implementation artifact. Filing is not convergence.

**Record what happened; do not decide what to do.** The line is not how much a filing carries but which kind of thing it carries. Evidence — a file and line, a quoted sentence, a count, an incident that occurred — stays true however far the vocabulary moves. Design — options, remedy shapes, names for structures — is written in today's vocabulary and decays with it. [#38](https://github.com/Grimblaz-and-Friends/tradecraft/issues/38) is the exhibit for both halves: its evidence reached pickup intact, its frame was dead vocabulary before anyone opened it, and it had to be rescoped into a new issue.

**The floor, so this is not read as licence to file a bare title:** carry enough evidence that a session picking the work up can confirm the problem is real without redoing the discovery that found it.

**A filing does not announce that it is minimal.** Thinness is this rule rather than a claim to make about one filing. Provenance is a different thing and belongs: who directed the work, or which review sustained it, is a fact the picker-up uses.

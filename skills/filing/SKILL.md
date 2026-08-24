---
name: filing
description: How a piece of work gets onto the board — the search that runs before a new issue is created, the ties that put its relationship to the board on the record at birth, and the line between the evidence a filing carries and the design it leaves for whoever picks it up. Use when about to create an issue, or when deciding whether something belongs on one that already exists; not for deciding whether a finding is worth filing at all, and not for the pre-implementation artifact written when the work is picked up.
---

# filing

**Purpose:** make a filing useful to the session that picks it up, however long that takes and however far the practice's vocabulary moves in between. **Audience:** any session about to create an issue — usually mid-review or mid-implementation, rarely while writing anything else. **Success:** every filing arrives with its relationship to the board already on the record, and carries evidence that still holds at pickup rather than a design that does not.

## A filing searches before it lands

Before creating an issue, search the board.

**The search is not done until it has been run against the subject's identifier, every name the mechanism goes by, and the defect in the words the board would already have used — over issues in every state, across the whole board rather than a first page.** All three parts are load-bearing, and each of them fails silently when it is run wrong.

**Run it as commands.** Either surface serves; the two settings that matter are spelled differently on each, and a wrong spelling is a hard error on one and a quiet half-search on the other.

```
gh search issues "<one term>" --repo <owner>/<repo> --limit 100
gh issue list --repo <owner>/<repo> --state all --limit 100 --search "<one term>"
```

`--state all` is valid on `gh issue list` and rejected outright by `gh search issues`, where every state is the **absence** of the flag. Left alone, both surfaces default to open-only or to a first page shorter than a working board, and both truncations are silent — so a filing that takes the defaults can report an empty board it never read. A closed issue is the record of what was already decided, already tried, or left behind when its parent closed.

**One term per query, because the failure runs in both directions.** Too broad misses the exact string: on this practice's own board, `check_version_bump` returns none of the issues whose titles *begin* with `check_version_bump.py`, and only the query carrying the extension returns them. Too narrow returns a truthful zero: terms are ANDed, so `post-fix seat` returns a fraction of what `post-fix` alone does. Neither result says which of the two happened to it.

**A mechanism usually answers to three names** — its key, the term the prose uses for it, the file that records it — and they return near-disjoint sets. `post-fix`, `prosecution look` and `reviews.jsonl` all name one mechanism and share almost nothing; only the last of them surfaced the issue that decided the filing that found this. Running one of the three looks exactly like running the search.

**The defect's own words are the board's, not yours.** The other two parts are printed on the artifact in front of you; this one is a guess at what somebody else called the same thing. Lift the phrase from the material — the sentence of the rule being breached, the term a decision entry already used — rather than coining it, because a coined phrase is queried against a board that could never have contained it.

Three outcomes, each lawful:

- **Extend** an **open** issue — a comment, not a new number. A closed match is a tie, never a home. **Read the host to its end first: extend only where a ruling that closes it would dispose of your defect too.** An issue whose own closure would leave your defect unremedied is a tie, and extending buries it under a disposal that never reaches it.
- **File new with named ties** — the relationship goes on the record at birth instead of being reconstructed at ranking time: [#94](https://github.com/Grimblaz-and-Friends/tradecraft/issues/94) and [#95](https://github.com/Grimblaz-and-Friends/tradecraft/issues/95) were two lawful filings against one sentence whose pairing had to be reconstructed when they were merged into a single PR later, because neither of them named the other.
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

Both paired relationships are written in both directions; `blocks` exists because a filing that unblocks an existing issue would otherwise have to edit that issue to record the order.

**A pass that creates more than one issue is not done until each of them names the others.** The numbers do not exist until creation, so the first filing's tie block is completed inside the same pass — which is not the edit `blocks` exists to avoid, because that one mutates an issue a ranking may already have read and this one closes a filing nobody has seen yet.

**The same four relationships apply whether the tied issue is open or closed; there is no separate closed-issue vocabulary.** What shifts is the ranking consequence — against a closed target it is that the issue is read, not that anything is scheduled — and, on the ordering row, the assertion itself: `sequenced-after` is already satisfied and `blocks` does not hold.

Write the ties as the **first element of the issue body, before any heading or prose**, one per line as `<verb> #N — <one clause of why>`. One pair may carry more than one verb, one per line; a relationship none of the four expresses is carried in the same block in prose and flagged as a candidate for the set. Consistent placement is what lets a session ranking the board find ties without reading every body — [#33](https://github.com/Grimblaz-and-Friends/tradecraft/issues/33) named [#20](https://github.com/Grimblaz-and-Friends/tradecraft/issues/20) and [#52](https://github.com/Grimblaz-and-Friends/tradecraft/issues/52) named #35, both truthfully, and both in a closing line nobody ranking the board would reach.

Where the search turned up nothing that earns a tie, the block says so **as a fact about the board** — *no siblings on the board* — because that is what a ranking uses. Where one limb could only be run on a phrase you coined, its zero is a fact about the phrase rather than the board, and the block claims the narrower thing. **Do not state that the search was performed.** The ties are its artifact: a filing naming them has demonstrably searched, and a compliance sentence nobody can check buys nothing.

## Creation carries the want; pickup does the work

**Carried at creation:** the want or defect in plain terms; the incident or evidence that makes it real; why it will actually get picked up; the ties above; and what discovery must settle, named as deliberately deferred.

**Left for pickup:** the framing, the options and their argument, the remedy design, the pre-implementation artifact. Filing is not convergence.

**Record what happened; do not decide what to do.** The line is not how much a filing carries but which kind of thing it carries. Evidence — a file and line, a quoted sentence, a count, an incident that occurred — survives however far the vocabulary moves, *provided it is written as an observation anyone can re-run rather than as a citation into vocabulary that can retire*. Design — options, remedy shapes, names for structures — is written in today's vocabulary and decays with it. [#38](https://github.com/Grimblaz-and-Friends/tradecraft/issues/38) is the exhibit for both halves and for the proviso: its frame was dead vocabulary before anyone opened it, and the observation underneath survived only because its successor could restate it against an authority that still existed.

**Where the evidence is itself a rule, the rule's own sentence is the observation.** Quote it, with its location — the quote survives the file moving and the location alone is the citation the proviso warns about. Saying which rule is breached is evidence; saying what should replace it is design, and stays out.

**The floor:** carry enough evidence that a session picking the work up can confirm the problem is real without redoing the discovery that found it.

**A filing does not announce that it is minimal.** Provenance is a different thing and belongs: who directed the work, or which review sustained it, is a fact the picker-up uses.

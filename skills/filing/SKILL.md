---
name: filing
description: How a piece of work gets onto the board — the search that runs before a new issue is created, the ties that put its relationship to the board on the record at birth, and the line between the evidence a filing carries and the design it leaves for whoever picks it up. Use when about to create an issue, or when deciding whether something belongs on one that already exists; not for deciding whether a finding is worth filing at all, and not for the pre-implementation artifact written when the work is picked up.
---

# filing

**Purpose:** make a filing useful to the session that picks it up, however long that takes and however far the practice's vocabulary moves in between. **Audience:** any session about to create an issue — usually mid-review or mid-implementation, rarely while writing anything else. **Success:** every filing arrives with its relationship to the board already on the record, and carries evidence that still holds at pickup rather than a design that does not.

## A filing searches before it lands

Before creating an issue, search the board.

**The search is not done until it has been run against the subject's identifier, every name the mechanism goes by, and the defect in the board's own words — over issues in every state, across the whole board rather than a first page.** All three parts are load-bearing.

**Run it as commands.** The two surfaces differ on all-states and on multi-word queries, so pick one deliberately:

```
gh search issues "post-fix" --repo OWNER/REPO --limit 1000
gh issue list --repo OWNER/REPO --state all --limit 1000 --search "post-fix"
```

`--state all` is valid on `gh issue list` and rejected outright by `gh search issues`, where every state is the **absence** of the flag. Left at its default of thirty, either surface returns a first page with no warning there was more. A closed issue records what was already decided, already tried, or left behind when its parent closed.

**A quoted argument is one term, and the surfaces read it differently:** `gh search issues` sends it as a phrase, `gh issue list --search` ANDs its words. A name containing a space is a term; a lifted sentence is not — take its distinctive word. `gh search issues "manifest exemption wider"` returns nothing where the other surface returns the open issue titled that.

**One term per query, because the failure runs both ways.** A near-miss on the string returns nothing: on this practice's own board, `check_version_bump` returns none of the issues whose titles *begin* with `check_version_bump.py`; only the query carrying the extension returns them. Adding a word narrows hard: `post-fix seat` returns four where `post-fix` returns fifty-one. Neither result says which happened to it.

**A mechanism usually answers to three names** — its key, the term the prose uses for it, the file that records it — and one can be the only one that reaches what you need. On this practice's own board `post-fix`, `prosecution look` and `reviews.jsonl` name one mechanism; only `reviews.jsonl` returns [#126](https://github.com/Grimblaz-and-Friends/tradecraft/issues/126), the issue that decided the filing that found this. Running one of the three looks exactly like running the search.

**The defect's own words are the board's, not yours.** The other two are printed on the artifact in front of you; this one guesses what somebody else called the same thing. Lift it from the material — the rule being breached, the term a decision entry used — rather than coining it, because a coined phrase is queried against a board that could never have contained it.

Three outcomes, each lawful:

- **Extend** an **open** issue — a comment, not a new number. A closed match is a tie, never a home. **Extend only where a ruling that closes the host would dispose of your defect too** — read its comments as well as its body, since an issue is re-scoped where it is discussed. Otherwise it is a tie, and extending buries your defect under a disposal that never reaches it.
- **File new with named ties** — the relationship goes on the record at birth instead of being reconstructed at ranking time: [#94](https://github.com/Grimblaz-and-Friends/tradecraft/issues/94) and [#95](https://github.com/Grimblaz-and-Friends/tradecraft/issues/95) were two lawful filings against one sentence whose pairing had to be reconstructed when they were merged into a single PR later, because neither of them named the other.
- **File standalone** — nothing turned up that earns a tie.

An extending comment carries the same list and meets the same floor; its tie is the issue it lands on.

### Naming a tie

**A tie name earns its place by changing what a ranking does with the pair.** That is what keeps the set closed, and the test any addition to it must pass.

| tie | what it asserts | what a ranking does with it |
| --- | --- | --- |
| **same-subject #N** | same file, paragraph, or mechanism | consider one PR for both |
| **same-class #N** | different subject, same defect shape | one remedy may serve both |
| **sequenced-after #N** / **blocks #N** | this cannot start until that lands / that cannot start until this does | order the pair, do not bundle it |
| **supersedes #N** / **superseded-by #N** | this replaces that, or that replaces this, in whole or in part | close or rescope the replaced one |

Both paired relationships are written in both directions; `blocks` exists because a filing that unblocks an existing issue would otherwise have to edit that issue to record the order.

**A pass that creates more than one issue is not done until each of them names the others.** The numbers do not exist until creation, so the first filing's tie block is completed inside the same pass, by editing its body (`gh issue edit`) — a tie in a comment lands where nobody ranking the board will reach it. That is not the edit `blocks` avoids: that one mutates an issue a ranking may already have read; this one closes a filing nobody has seen yet.

**The same four relationships apply whether the tied issue is open or closed; there is no separate closed-issue vocabulary.** What shifts is the ranking consequence — against a closed target it is that the issue is read, not that anything is scheduled — and, on the ordering row, the assertion itself: `sequenced-after` is already satisfied and `blocks` does not hold.

Write the ties as the **first element of the issue body, before any heading or prose**, one per line as `<verb> #N — <one clause of why>`. One pair may carry more than one verb, one per line; a relationship none of the four expresses is carried in the same block in prose and flagged as a candidate for the set. Consistent placement is what lets a session ranking the board find ties without reading every body — [#33](https://github.com/Grimblaz-and-Friends/tradecraft/issues/33) named [#20](https://github.com/Grimblaz-and-Friends/tradecraft/issues/20) and [#52](https://github.com/Grimblaz-and-Friends/tradecraft/issues/52) named #35, both truthfully, and both in a closing line nobody ranking the board would reach.

Where the search turned up nothing that earns a tie, the block says so **as a fact about the board** — *no siblings on the board* — because that is what a ranking uses. Where one limb could only be run on a phrase you coined, its zero is a fact about the phrase rather than the board, and the block claims the narrower thing. **Do not state that the search was performed.** The ties are its artifact: a filing naming them has demonstrably searched, and a compliance sentence nobody can check buys nothing.

## Creation carries the want; pickup does the work

**Carried at creation:** the want or defect in plain terms; the evidence that makes it real; why it will get picked up; the ties above; and what discovery must settle, named as deliberately deferred.

**Left for pickup:** the framing, the options and their argument, the remedy design, the pre-implementation artifact. Filing is not convergence.

**Record what happened; do not decide what to do.** The line is not how much a filing carries but which kind of thing it carries. Evidence — a file and line, a quoted sentence, a count, an incident that occurred — survives however far the vocabulary moves, *provided it is written as an observation anyone can re-run rather than as a citation into vocabulary that can retire*. Design — options, remedy shapes, names for structures — is written in today's vocabulary and decays with it. [#38](https://github.com/Grimblaz-and-Friends/tradecraft/issues/38) is the exhibit for both halves and for the proviso: its frame was dead vocabulary before anyone opened it, and the observation underneath survived only because its successor could restate it against an authority that still existed.

**Where the evidence is itself a rule, the rule's own sentence is the observation.** Quote it with its location: the quote survives the file moving, where the location alone is the citation the proviso warns about. Which rule is breached is evidence; what replaces it is design, and stays out.

**The floor:** carry enough evidence that a session picking the work up can confirm the problem is real without redoing the discovery that found it.

**A filing does not announce that it is minimal.** Provenance is different and belongs: who directed the work, or which review sustained it, is a fact the picker-up uses.

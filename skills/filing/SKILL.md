---
name: filing
description: How a piece of work gets onto the board — the search that runs before a new issue is created, the ties that put its relationship to the board on the record at birth, the evidence a filing about governing prose must carry to be filed at all, the findings a cause carries as comments until its fix disposes of them, and the line between the evidence a filing carries and the design it leaves for whoever picks it up. Use when about to create an issue, when deciding whether something belongs on one that already exists, or when deciding whether a finding about governing prose has earned one; not for the pre-implementation artifact written when the work is picked up.
---

# filing

**Purpose:** make a filing useful to the session that picks it up, however long that takes and however far the practice's vocabulary moves in between, and keep off the board what nothing acts differently for. **Audience:** any session about to create an issue — usually mid-review or mid-implementation, rarely while writing anything else. **Success:** every filing arrives with its relationship to the board already on the record, and carries evidence that still holds at pickup rather than a design that does not; a finding about governing prose that changes nothing a session does takes no number; and one recorded under its cause is disposed when that cause's fix lands rather than lost with it.

## A filing searches before it lands

Before creating an issue, search the board.

**The search is not done until it has been run against the subject's identifier, every name the mechanism goes by, and the defect in the board's own words — over issues in every state, across the whole board rather than a first page.** All three parts are load-bearing.

**Run it as commands,** substituting your own repository. The two surfaces differ on all-states and on multi-word queries, so pick one deliberately:

```
gh search issues "post-fix" --repo OWNER/REPO --limit 1000
gh issue list --repo OWNER/REPO --state all --limit 1000 --search "post-fix"
```

`--state all` is valid on `gh issue list` and rejected outright by `gh search issues`, where every state is the **absence** of the flag. Left at its default of thirty, either surface returns a first page with no warning there was more. A closed issue records what was already decided, already tried, or left behind when its parent closed.

**A quoted argument is one term, and the surfaces read it differently:** `gh search issues` sends it as a phrase, `gh issue list --search` ANDs its words. A name containing a space is a term; a lifted sentence is not — take its distinctive word. `gh search issues "manifest exemption wider"` returns nothing where the other surface returns [#20](https://github.com/Grimblaz-and-Friends/tradecraft/issues/20), whose title carries all three words but not adjacently.

**One term per query, because the failure runs both ways.** A near-miss on the string returns nothing: on this practice's own board, `check_version_bump` returns none of the issues whose titles *begin* with `check_version_bump.py`. Adding a word narrows hard on either surface: `post-fix terminus` returns a small fraction of what `post-fix` alone does. Neither result says which happened to it.

**A mechanism usually answers to three names** — its key, the term the prose uses for it, the file that records it — and one can be the only one that reaches what you need. On this practice's own board `post-fix`, `prosecution look` and `reviews.jsonl` name one mechanism; only `reviews.jsonl` returns [#126](https://github.com/Grimblaz-and-Friends/tradecraft/issues/126), the issue that decided the filing that found this. Running one of the three looks exactly like running the search.

**The defect's own words are the board's, not yours.** The other two are printed on the artifact in front of you; this one guesses what somebody else called the same thing. Lift it from the material — the rule being breached, the term a decision entry used — rather than coining it, because a coined phrase is queried against a board that could never have contained it.

Five outcomes, each lawful:

- **Extend** an **open** issue — a comment, not a new number. A closed match is a tie, never a home. **Extend only where a ruling that closes the host would dispose of your defect too** — read its comments as well as its body, since an issue is re-scoped where it is discussed. Otherwise it is a tie, and extending buries your defect under a disposal that never reaches it.
- **Record it under its cause** — where the cause is already on the board and what you hold is one of the instances it was observed producing, the finding lands as a comment on that cause and takes no number of its own. **The extend rule above does not govern it**, and what stands in for that rule is what answers the same burial: not that a ruling closing the cause disposes of the finding, but that **a change fixing a cause disposes of every finding recorded under it — clearing it, or filing it then as its own issue: a finding the fix left standing is one that now needs a fix of its own, and the fix having left it standing is the evidence for that, so the bar below does not run on it.** A finding already carrying a number is tied `caused-by` its cause rather than moved onto it. **A finding takes a number of its own while its cause is still open only where it needs fixing now, and that call is the owner's.**
- **File new with named ties** — the relationship goes on the record at birth instead of being reconstructed at ranking time.
- **File one issue carrying the batch** — where the defects in hand share one cause you can point at, they land as one number rather than several cross-tied ones: each defect with its own evidence, the shared probes stated once, pickup dispositioning them item by item. **The test is a cause you observed, never a fix you would have to design** — what one change would take is remedy design, which this cell leaves to pickup — **and not the surface either**: a shared file neither decides it nor is required. **Where the symptoms already carry numbers, the cause takes its own and the ties below group them**; one number is for what is in your hands at once. [#94](https://github.com/Grimblaz-and-Friends/tradecraft/issues/94) and [#95](https://github.com/Grimblaz-and-Friends/tradecraft/issues/95) are the cost of not taking it — two lawful filings against one sentence, merged into a single PR later, whose pairing had to be reconstructed at ranking time. [#151](https://github.com/Grimblaz-and-Friends/tradecraft/issues/151) and [#152](https://github.com/Grimblaz-and-Friends/tradecraft/issues/152) show the form a batch takes and are not an exhibit for the test: each was warranted by one opening of one cell, which is the surface.
- **File standalone** — nothing turned up that earns a tie.

[#233](https://github.com/Grimblaz-and-Friends/tradecraft/issues/233), [#234](https://github.com/Grimblaz-and-Friends/tradecraft/issues/234) and [#235](https://github.com/Grimblaz-and-Friends/tradecraft/issues/235) came out of one review, each naming the others. #233 and #234 share one cause, line-ending handling every guard passes; #235 named a third file and was closed without a change of its own, its subject discharged by a pull request already in flight. A shared file would have split the pair and grouped nothing.

An extending comment carries the creation list and meets the same evidence standard, and so does a finding recorded under its cause — **except the bar below, which neither owes: an extending comment inherits its host's, and a recorded finding its cause's**, one filing carrying the incident or the run being what puts them all on the board. The tie is the issue the comment lands on.

### Naming a tie

**A tie name earns its place by changing what a ranking does with the pair.** That is what keeps the set closed, and the test any addition to it must pass.

| tie | what it asserts | what a ranking does with it |
| --- | --- | --- |
| **same-subject #N** | same file, paragraph, or mechanism | consider one PR for both |
| **same-class #N** | different subject, same defect shape | one remedy may serve both |
| **the sub-issue link**, cause as parent | this produced that — the symptom is what the cause was observed doing, and fixing the cause may discharge it or leave it standing | rank the cause above its symptoms and work them as one group led by it; do not schedule a symptom on its own while its cause is open |
| **sequenced-after #N** / **blocks #N** | this cannot start until that lands / that cannot start until this does | order the pair, do not bundle it |
| **supersedes #N** / **superseded-by #N** | this replaces that, or that replaces this, in whole or in part | close or rescope the replaced one |

Each paired relationship **written as a verb** is written in both directions; `blocks` exists because a filing that unblocks an existing issue would otherwise have to edit that issue to record the order.

**The cause relationship is not a verb at all: it is GitHub's sub-issue link, the cause as parent, the parent carrying a `cause` label.** [D-429] The link means a task split into parts everywhere else, and the label is the only thing saying this one means causation — **an unlabelled parent is invisible to everything downstream**, which is a silent failure rather than a loud one. One link is carried by both issues, so a session opening a symptom sees its cause and a session opening the cause sees every symptom, whichever was filed first and without either body saying so. **GitHub refuses a second parent**, so a symptom carries one cause and the question of what two would mean cannot be asserted.

**No `gh` subcommand sets the link**, so it is a mutation over the two issues' node ids, which `gh issue view <N> --json id` returns. The label is an ordinary one and `--label` puts it on, but it has to exist in the repository before it will:

```
gh label create cause --description "Observed cause of the issues linked under it"
gh api graphql -f query='mutation{addSubIssue(input:{issueId:"<cause id>",
  subIssueId:"<symptom id>"}){subIssue{number parent{number}}}}'
```

**Re-parenting takes `removeSubIssue` first**, the second `addSubIssue` being refused while the first link stands.

A causal relationship you believe but cannot set — the cause in another repository, or no access — goes in the tie block as flagged prose that **says which it is**: nobody will ever link it, so the prose is the record; or it is waiting on access, so the prose comes out when the link goes in. Nothing else tells them apart afterwards, and neither is a candidate for the tie set — causation has a home already.

**A symptom whose only relationship is its cause writes no tie line at all**, the link being the record — and its block does not then claim *no siblings on the board*, which would be false of an issue that has a parent. Say that its cause is linked.

**A pass that creates more than one issue is not done until each of them names the others.** The numbers do not exist until creation, so the first filing's tie block is completed inside the same pass, by editing its body (`gh issue edit`) — a tie in a comment lands where nobody ranking the board will reach it. That is not the edit `blocks` avoids: that one mutates an issue a ranking may already have read; this one closes a filing nobody has seen yet.

**The same five relationships apply whether the tied issue is open or closed; there is no separate closed-issue vocabulary.** What shifts is the ranking consequence — against a closed target it is that the issue is read, not that anything is scheduled — and, on the ordering row, the assertion itself: `sequenced-after` is already satisfied and `blocks` does not hold.

Write the ties as the **first element of the issue body, before any heading or prose**, one per line as `<verb> #N — <one clause of why>`. One pair may carry more than one verb, one per line; a relationship none of the five expresses is carried in the same block in prose and flagged as a candidate for the set. Consistent placement is what lets a session ranking the board find ties without reading every body — [#33](https://github.com/Grimblaz-and-Friends/tradecraft/issues/33) named [#20](https://github.com/Grimblaz-and-Friends/tradecraft/issues/20) and [#52](https://github.com/Grimblaz-and-Friends/tradecraft/issues/52) named #35, both truthfully, and both in a closing line nobody ranking the board would reach.

Where the search turned up nothing that earns a tie, the block says so **as a fact about the board** — *no siblings on the board* — because that is what a ranking uses. Where one limb could only be run on a phrase you coined, its zero is a fact about the phrase rather than the board, and the block claims the narrower thing. **Do not state that the search was performed.** The ties are its artifact, and a compliance sentence nobody can check buys nothing.

## Creation carries the want; pickup does the work

**Carried at creation:** the want or defect in plain terms; the evidence that makes it real; why it will get picked up; the ties above; what discovery must settle, named as deliberately deferred; and, where the subject is governing prose, the incident or the run below.

**Left for pickup:** the framing, the options and their argument, the remedy design, the pre-implementation artifact. Filing is not convergence.

**Record what happened; do not decide what to do.** The line is not how much a filing carries but which kind of thing it carries. Evidence — a file and line, a quoted sentence, a count, an incident that occurred — survives however far the vocabulary moves, *provided it is written as an observation anyone can re-run rather than as a citation into vocabulary that can retire*. Design — options, remedy shapes, names for structures — is written in today's vocabulary and decays with it. [#38](https://github.com/Grimblaz-and-Friends/tradecraft/issues/38) is the exhibit for both halves and for the proviso: its frame was dead vocabulary before anyone opened it, and the observation underneath survived only because its successor could restate it against an authority that still existed.

**Where the evidence is itself a rule, the rule's own sentence is the observation.** Quote it with its location: the quote survives the file moving, where the location alone is the citation the proviso warns about. Which rule is breached is evidence; what replaces it is design, and stays out.

**A filing whose subject is governing prose — prose a later session is expected to act on — carries an incident from real work, or a run: the same situation put to a session under the text as it stands and under what would replace it, behaving differently.** The breached rule's own sentence above is what is wrong with the text; this is what acts differently for it, and a filing carrying only the first is not filed. The bar sits at creation because an issue picked up is a brief, an artifact and a change — a rule by another door — so a rule about prose reaches the board on the evidence a rule needs; what an incident is not is the `charter` cell's. **Not filed is not binned:** where the cause is already on the board the finding is recorded under it, above; where none is, nothing is filed and the finding waits for the incident or the run that would earn one. Nothing else is gated here — a defect in a script or a guard carries its consequence in the failure it produces.

**Where the defect can be demonstrated, the demonstration is the evidence** — the probe command and its output, not a sentence reporting what running it shows. A reproduction cannot be misread, survives the vocabulary moving around it, and hands the pickup its first acceptance criterion. Prose is the fallback rather than the default, and it is the right form for what has no failing run: a want, an idea, an incident that occurred, and a breached rule, whose own sentence is the observation above. On governing prose each of the four is half of what the filing carries, the bar above being the other.

**The floor:** carry enough evidence that a session picking the work up can confirm the problem is real without redoing the discovery that found it.

**A filing does not announce that it is minimal.** Provenance is different and belongs: who directed the work, or which review sustained it, is a fact the picker-up uses.

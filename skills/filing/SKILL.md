---
name: filing
description: How work gets into the pool and how it leaves — the search that runs before a new issue is created, the ties that put its relationship to the board on the record at birth, the findings a cause carries as comments until its fix disposes of them, and the line between the evidence a filing carries and the design it leaves for whoever picks it up. Use when about to create an issue, when deciding whether something belongs on one that already exists, when deciding whether a finding about governing prose has earned one, or when asking whether anything has got bad enough to put to the owner unasked; not for the pre-implementation artifact written when the work is picked up.
---

# filing

**Purpose:** make a filing useful to the session that picks it up, however long that takes and however far the practice's vocabulary moves in between, and keep out of the pool what nothing acts differently for. **Audience:** any session about to create an issue — usually mid-review or mid-implementation, rarely while writing anything else. **Success:** every filing arrives with its relationship to the board already on the record, and carries evidence that still holds at pickup rather than a design that does not; it lands in the pool with a rating rather than on the board as work nobody decided on; a finding about governing prose that changes nothing a session does takes no number unless a review ruled it `record`, which is the one thing that bar admits; and one recorded under its cause is disposed when that cause's fix lands rather than lost with it.

## A filing searches before it lands

Before creating an issue, search every issue in the repository — the pool, the board and what is closed.

**The search is not done until it has been run against the subject's identifier, every name the mechanism goes by, and the defect in the repository's own words — over issues in every state, across the whole set rather than a first page.** All three parts are load-bearing.

**Run it as commands,** substituting your own repository. The two surfaces differ on all-states and on multi-word queries, so pick one deliberately:

```
gh search issues "post-fix" --repo OWNER/REPO --limit 1000
gh issue list --repo OWNER/REPO --state all --limit 1000 --search "post-fix"
```

`--state all` is valid on `gh issue list` and rejected outright by `gh search issues`, where every state is the **absence** of the flag. Left at its default of thirty, either surface returns a first page with no warning there was more. A closed issue records what was already decided, already tried, or left behind when its parent closed.

**A quoted argument is one term, and the surfaces read it differently:** `gh search issues` sends it as a phrase, `gh issue list --search` ANDs its words. A name containing a space is a term; a lifted sentence is not — take its distinctive word. `gh search issues "manifest exemption wider"` returns nothing where the other surface returns [#20](https://github.com/Grimblaz-and-Friends/tradecraft/issues/20), whose title carries all three words but not adjacently.

**One term per query, because the failure runs both ways.** A near-miss on the string returns nothing: on this practice's own board, `check_version_bump` returns none of the issues whose titles *begin* with `check_version_bump.py`. Adding a word narrows hard on either surface: `post-fix terminus` returns a small fraction of what `post-fix` alone does. Neither result says which happened to it.

**A mechanism usually answers to three names** — its key, the term the prose uses for it, the file that records it — and one can be the only one that reaches what you need. On this practice's own board `post-fix`, `prosecution look` and `reviews.jsonl` name one mechanism; only `reviews.jsonl` returns [#126](https://github.com/Grimblaz-and-Friends/tradecraft/issues/126), the issue that decided the filing that found this. Running one of the three looks exactly like running the search.

**The defect's own words are the repository's, not yours.** The other two are printed on the artifact in front of you; this one guesses what somebody else called the same thing. Lift it from the material — the rule being breached, the term a decision entry used — rather than coining it, because a coined phrase is queried against a set that could never have contained it.

Five outcomes, each lawful:

- **Extend** an **open** issue — a comment, not a new number. A closed match is a tie, never a home. **Extend only where a ruling that closes the host would dispose of your defect too** — read its comments as well as its body, since an issue is re-scoped where it is discussed. Otherwise it is a tie, and extending buries your defect under a disposal that never reaches it.
- **Record it under its cause** — where the cause is already an open issue, framed or in the pool, and what you hold is one of the instances it was observed producing, the finding lands as a comment on that cause and takes no number of its own. **The extend rule above does not govern it**, and what stands in for that rule is what answers the same burial: not that a ruling closing the cause disposes of the finding, but that **a change fixing a cause disposes of every finding recorded under it — clearing it, or filing it then as its own issue: a finding the fix left standing is one that now needs a fix of its own, and the fix having left it standing is the evidence for that, so the bar below does not run on it.** A finding already carrying a number is tied `caused-by` its cause rather than moved onto it. **A finding takes a number of its own while its cause is still open only where it needs fixing now, and that call is the owner's.**
- **File new with named ties** — the relationship goes on the record at birth instead of being reconstructed at ranking time.
- **File one issue carrying the batch** — where the defects in hand share one cause you can point at, they land as one number rather than several cross-tied ones: each defect with its own evidence, the shared probes stated once, pickup dispositioning them item by item. **The test is a cause you observed, never a fix you would have to design** — what one change would take is remedy design, which this cell leaves to pickup — **and not the surface either**: a shared file neither decides it nor is required. **Where the symptoms already carry numbers, the cause takes its own and the ties below group them**; one number is for what is in your hands at once. [#94](https://github.com/Grimblaz-and-Friends/tradecraft/issues/94) and [#95](https://github.com/Grimblaz-and-Friends/tradecraft/issues/95) are the cost of not taking it — two lawful filings against one sentence, merged into a single PR later, whose pairing had to be reconstructed at ranking time. [#151](https://github.com/Grimblaz-and-Friends/tradecraft/issues/151) and [#152](https://github.com/Grimblaz-and-Friends/tradecraft/issues/152) show the form a batch takes and are not an exhibit for the test: each was warranted by one opening of one cell, which is the surface.
- **File standalone** — nothing turned up that earns a tie.

[#233](https://github.com/Grimblaz-and-Friends/tradecraft/issues/233), [#234](https://github.com/Grimblaz-and-Friends/tradecraft/issues/234) and [#235](https://github.com/Grimblaz-and-Friends/tradecraft/issues/235) came out of one review, each naming the others. #233 and #234 share one cause, line-ending handling every guard passes; #235 named a third file and was closed without a change of its own, its subject discharged by a pull request already in flight. A shared file would have split the pair and grouped nothing.

An extending comment carries the creation list and meets the same evidence standard, and so does a finding recorded under its cause — **except the ratings, which neither carries, having no number of its own to put a label on: the host's stand, and the cause's**, and **except the bar below, which neither owes: an extending comment inherits its host's, and a recorded finding its cause's**, one filing carrying the incident or the run being what puts them all on the board. The tie is the issue the comment lands on.

### Naming a tie

**A tie name earns its place by changing what a ranking does with the pair.** That is what keeps the set closed, and the test any addition to it must pass.

| tie | what it asserts | what a ranking does with it |
| --- | --- | --- |
| **same-subject #N** | same file, paragraph, or mechanism | consider one PR for both |
| **same-class #N** | different subject, same defect shape | one remedy may serve both |
| **the sub-issue link**, cause as parent | this produced that — the symptom is what the cause was observed doing, and fixing the cause may discharge it or leave it standing | rank the cause above the symptoms a ranking holds and work them as one group led by it; do not schedule a symptom on its own while its cause is open |
| **sequenced-after #N** / **blocks #N** | this cannot start until that lands / that cannot start until this does | order the pair, do not bundle it |
| **supersedes #N** / **superseded-by #N** | this replaces that, or that replaces this, in whole or in part | close or rescope the replaced one |

Each paired relationship **written as a verb** is written in both directions; `blocks` exists because a filing that unblocks an existing issue would otherwise have to edit that issue to record the order.

**The cause relationship is not a verb at all: it is GitHub's sub-issue link, the cause as parent, the parent carrying a `cause` label.** [D-429] The link means a task split into parts everywhere else, and the label is the only thing saying this one means causation — **an unlabelled parent is invisible to everything downstream**, which is a silent failure rather than a loud one. One link is carried by both issues, so a session opening a symptom sees its cause and a session opening the cause sees every symptom, whichever was filed first and without either body saying so. **GitHub refuses a second parent**, so a symptom carries one cause and the question of what two would mean cannot be asserted.

**No `gh` subcommand set the link as of 2.80.0**, so it is a mutation over the two issues' node ids, which `gh issue view <N> --json id` returns — check your own `gh issue create --help` for a `--parent` flag first, since an absence claim about a tool is only as old as the version it was checked against. The label is an ordinary one and `--label` puts it on, but it has to exist in the repository before it will:

```bash
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

## A filing lands in the pool, not on the board

**A filing a session made on its own lands in the pool** -- what has been noticed, with its evidence and a rating, and not yet decided on. **The board holds what has been decided on and only that.** An open issue is in the pool unless it carries the framed label, so nothing is written to put it there and a filer who forgets cannot lose one.

**What the owner filed, or told a session to file, is decided work from the start and goes straight to the board.** The line is *who decided*, not whether the thing is a defect or an idea: an owner filing something has already decided it is worth doing, and a pool that made them pull their own filing back out would have them waiting on themselves. So an owner-originated filing is **framed at birth** -- they run `frame` on it, or a session filing on their instruction frames it and says in the issue that it is the owner's ask. **A session may not frame its own filing**, which is the whole of the bar; nothing reads authorship off the wire, and a repository that wants owner filings pooled too says so in its own doctrine rather than in the policy, no command here reading such a field.

**A filing carries two ratings the filer proposes, on separate axes: how severe it is, and how urgent** -- each one label from a set the policy names. Ideas are rated the same way as defects, by what is at stake rather than by what a wrong act would cost, so what waits in the pool is one kind of thing. **The owner confirms ratings only on the few a shortlist puts to them**, never one filing at a time.

**Work leaves the pool two ways, and what is in the pool is what a session noticed rather than what the owner asked for.**

**The pull, which is the ordinary one.** They say they want something, a session raises a few with the case for and against each, and they pick one. **That pick is the decision that the work is worth doing, and it is what frames the filing** -- the brief settled afterwards still decides what the work is for and at what cost, and may send it back to the pool if the cause turns out bigger than the pick assumed.

**The push, which a repository wires rather than gets.** An item whose *effective* rating reaches the policy's `push` threshold on **every** axis is worth the owner's attention without their asking, and `scripts/pool.py pushed` is what finds those. **Nothing runs it for you.** A repository decides where it runs -- a board refresh, a scheduled job, a session's own habit -- and **a repository that runs it nowhere has the pull as its only route**, which is a coherent way to use this and not a failure. **What crosses need not be a rating anyone set.** A filer proposing the top band on both axes crosses at once; but the accrual also lifts a cause over the line as its symptoms accumulate, so the push reaches the thing nobody rated urgently enough as well. What it never does is make a top band out of quantity -- severity is read as the worst of a cause and its symptoms and never as their sum, so any number of mild symptoms crosses nothing, and a top-band severity has to exist on the cause or under it either way.

**A crossing is put as an ask, on the surface every other ask uses** -- the `engagement` cell's, so it waits in one place beside everything else the owner owes an answer to rather than in a second list. Then `scripts/pool.py raise <N>` marks it, so the pool does not ask twice. **The mark is durable on purpose**: when the owner answers, the ask's own mark comes off and this one stays, so an item they declined stops asking until somebody takes the label off -- which is the act of saying *ask me again*. The cost of that is stated rather than solved: an item declined once goes quiet even if it later gets worse, and only the pull reaches it after that.

`scripts/pool.py` does the mechanics, and the judgment -- what a rating should be, what the case against a candidate is -- stays the session's:

**In this order.** A consumer setting the pool up read this block top to bottom and it failed on the third line, `shortlist` being gated on work the two lines above it do. Add `--repo OWNER/REPO` to any of them when you are not inside the repository's own checkout, **before the subcommand** — it is a global option, and appended after one it is an unrecognised argument. A refresher lost two tries of three to reading it as one more thing on the line. **Every path here is relative to this cell's own directory** — `scripts/pool.py` sits beside this file — so a session sent here by another cell, running from somewhere else, prefixes the path to this cell. One did not, and searched the tree for it.

```bash
python scripts/pool.py labels                              # so the policy's labels exist -- again after an upgrade adds one
python scripts/pool.py list                                # what is in the pool, and what is rated
python scripts/pool.py rate 123 --rating sev:3 --rating urg:2
python scripts/pool.py cycle                               # what rose, what faded, what to assess next
python scripts/pool.py assess 123 --none                   # asked, and it is its own cause
python scripts/pool.py shortlist                           # the pull -- gated on the two lines above
python scripts/pool.py pushed                              # the push -- what crossed the line, unasked
python scripts/pool.py raise 123                           # ...and was put to the owner, so ask once
python scripts/pool.py show 123                            # one issue, and why its row reads as it does
python scripts/pool.py frame 123                           # the owner picked it
python scripts/pool.py unframe 123                         # the brief sent it back to the pool
```

`scripts/pool-policy.json` carries the labels, the bands, the tie-break and the shortlist size; a repository overrides it with a file of that name at its own root, and one that wants a wholly different approach says so in its own doctrine and does not run any of this.

**An unrated filing is not a low-rated one.** It sorts below everything rated and is reported as unrated, because it has not been judged harmless -- it has not been judged.

**Items the ratings leave equal are ordered by the policy's `tie_break`** — as shipped, more symptoms under it first, then most recently touched, the issue number the last resort; `shortlist` names which key put the last item it raised above the first it did not, scoped to that pair. **Recency is the issue's own `updatedAt`, so your own `rate` or `assess` write moves an item up it** — the same signal the fade reads quiet from. [#452](https://github.com/Grimblaz-and-Friends/tradecraft/issues/452)

**A filing does not keep the rating it was given, and nothing rewrites its labels.** A cause is read as at least as bad as the worst thing it produced, and climbs a band for every `accrual.symptoms_per_band` symptoms under it — so below that number a symptom moves nothing, which is the mechanism and not a fault. Anything nobody touches falls a band per quiet window, while the axis it is ranked on first never moves: **the policy's `order` decides which is which**, and with the order shipped here that is urgency falling and severity holding. Both show in a row as `label>value` where the derived value differs from the label — `urg:3>1` is a filing rated 3 that two quiet windows have read down to 1, and its label is still `urg:3`. **An axis nobody rated, or rated twice, stays that way**: accrual raises a rating and never supplies one, so a `-` or a `CLASH` in a row means somebody still has to choose. Both are derived when the pool is read, so the labels stay the filer's proposal — a fade that wrote would reset the very signal it reads quiet from. **So do not re-rate an item to match what its row shows.** A consumer tried it: setting `urg:1` on a row reading `urg:3>1` writes the decayed number in as the proposal *and* touches the issue, so the next quiet window decays it again from the lower floor — a ratchet, one well-meant correction at a time. If a faded item still matters, say so where saying so counts: comment on it, link it under its cause, or bring it up in the next shortlist. **Not `raise <N>`** -- that is the push's mark and it silences the push for that item, which is the opposite of drawing attention to it. At the floor an item is named, and closed as *not planned* only where a repository has set `fade.closes`, which ships false. The close keeps the body and every comment, so nothing is lost and reopening costs a click — **but nothing reopens it for you**: every read here asks for open issues, so a later symptom lands under a cause the pool can no longer see.

**Most of the pool has never been asked whether it has a cause, and that is not the same as having none.** There are three answers and only two of them are a label: one asked and found to be its own carries the assessed label, one never asked carries nothing, and **one whose cause is known is recorded by the sub-issue link above** — which is read as the answer it is, so linking a symptom under its cause is what clears it. A row carries `?` in its own column while nobody has asked. `shortlist` refuses over an unassessed top so that what it raises are causes rather than symptoms, and `cycle` names a bounded few more each time so the backlog is worked through without anyone paying for it at once.

## Creation carries the want; pickup does the work

**Carried at creation:** the want or defect in plain terms; the evidence that makes it real; the two ratings above; why it will get picked up; the ties above; who found it, in the line below; what discovery must settle, named as deliberately deferred; and, where the subject is governing prose, the incident or the run below.

**Left for pickup:** the design framing, the options and their argument, the remedy design, the pre-implementation artifact. Filing is not convergence.

**Record what happened; do not decide what to do.** The line is not how much a filing carries but which kind of thing it carries. Evidence — a file and line, a quoted sentence, a count, an incident that occurred — survives however far the vocabulary moves, *provided it is written as an observation anyone can re-run rather than as a citation into vocabulary that can retire*. Design — options, remedy shapes, names for structures — is written in today's vocabulary and decays with it. [#38](https://github.com/Grimblaz-and-Friends/tradecraft/issues/38) is the exhibit for both halves and for the proviso: its frame was dead vocabulary before anyone opened it, and the observation underneath survived only because its successor could restate it against an authority that still existed.

**Where the evidence is itself a rule, the rule's own sentence is the observation.** Quote it with its location: the quote survives the file moving, where the location alone is the citation the proviso warns about. Which rule is breached is evidence; what replaces it is design, and stays out.

**A filing whose subject is governing prose — prose a later session is expected to act on — carries an incident from real work, or a run: the same situation put to a session under the text as it stands and under what would replace it, behaving differently.** The breached rule's own sentence above is what is wrong with the text; this is what acts differently for it, and a filing carrying only the first is not filed. The bar sits at creation because an issue picked up is a brief, an artifact and a change — a rule by another door — so a rule about prose reaches the pool on the evidence a rule needs; what an incident is not is the `charter` cell's. **Not filed is not binned:** where the cause is already an open issue the finding is recorded under it, above; where none is, nothing is filed and the finding waits for the incident or the run that would earn one. **A finding a review ruled `record` is the one thing this bar does not refuse**, and the exception is narrow on purpose: that ruling is a stage which is not the builder judging the finding real, evidenced, and not yet worth acting on, which is the pool's own state rather than the board's. It lands rated low, where the ranking and the shortlist reach it — and where, in a repository that has set `fade.closes`, the fade eventually disposes of it. **That switch ships off**, so by default nothing closes and the filing waits to be read rather than to expire. Nothing else is gated here — a defect in a script or a guard carries its consequence in the failure it produces.

**One item is admitted on its measurement alone: one whose whole evidence is a ceiling measurement over this practice's own prose.** Such an item names the surface, the number and the command that derives it, and that is the whole of what it carries as evidence — there is no incident to attach, because nothing has gone wrong yet: the measurement *is* the observation, and what it observes is a surface that has grown past where it stood. Its two ratings are the raising party's proposal like any other, and the owner confirms only the few raised to them. **The carve-out is keyed to that evidence and not to who raised it**, so it reaches an item a mechanism opens and one a change opens as it lands, which are the same item arriving by two doors; every other filing about governing prose meets the bar above. It exists because a ceiling that directs to filing is worth nothing if the filing it directs to is refused.

**Where the defect can be demonstrated, the demonstration is the evidence** — the probe command and its output, not a sentence reporting what running it shows. A reproduction cannot be misread, survives the vocabulary moving around it, and hands the pickup its first acceptance criterion. Prose is the fallback rather than the default, and it is the right form for what has no failing run: a want, an idea, an incident that occurred, and a breached rule, whose own sentence is the observation above. On governing prose each of the four is half of what the filing carries, the bar above being the other.

**The floor:** carry enough evidence that a session picking the work up can confirm the problem is real without redoing the discovery that found it.

**A filing does not announce that it is minimal.** Provenance is different and belongs, and it is carried as an element rather than left to the prose: **one line under the heading `**Provenance:**`, whose first word after that heading is one origin from a closed list** — `review` for a review seat, a defense, a terminal stage or judge, or an external reviewer; `use` for an experience session, a cold seat or consumer, a dispatched recipient, or an A/B run **outside a review**; `owner` for work the owner directed or that came out of a sitting with them; `session` for something a session noticed while doing other work; `instrument` for what a script or a guard raised. After that word the line says whatever the picker-up will use — which review, which run, which date. **The list is closed because the point is a key rather than a description.** Where none of the five fits, the line names the nearest and says why in the same line. **It goes with the evidence**, the tie block above staying the body's first element.

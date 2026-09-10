# Refreshing the board

**Loaded when** you are refreshing the board after it moved — running the checks a refresh owes, writing its plan, clearing a symptom's hold as its cause closes, or looking at the board in the browser.

## The board's face, and its three fields

**In the browser**, the board is at `https://github.com/orgs/Grimblaz-and-Friends/projects/5`. Its `Queue` view carries `Band` and `Bundle` as columns, so the grouping is legible without reading any prose — which is the whole reason the fields exist, and they were invisible there until someone looked. **To collapse the board by bundle, group the view by `Bundle` once, from the view menu.** That is a click and not a command: `updateProjectV2View` sets a view's name, layout, filter and which fields it shows, and has no grouping in its configuration input, so a session can restore the columns and cannot restore the grouping. The same is true of the auto-add workflow.

`Band` records where in the board's own shape an item sits — `Standing`, `Front`, `Bundles`, `Review-set`, `Tail`. **It is not availability**, with one exception the transport enforces: `Standing` claims an item is out of contention, so a `Standing` row must carry a status that says so, and a plan pairing `Standing` with `Queued` is refused. `Bundle` names the group an issue is worked as part of, so a session can see what belongs together without reading any prose. **The test is what one change would take, or one cause the group carries a tie to, and shared origin is not a bundle** — issues that merely came out of the same review, or name the same issue in a tie that is not the cause link, are related and not grouped; labelling them as one tells the next ranking session to plan one pull request for unrelated mechanisms. Three shapes are lawful and the name should say which: a **prospective pull request**, where one change closes the whole group; a **cause-led group**, where one issue is the cause the rest are linked under as sub-issues; and a **cluster**, where the group moves and is deferred together but a change may take only part of it — `PR #322` closed three of one five-item cluster and left two open, which is that shape working rather than failing. **Where a filer had them all in hand under one cause they could point at, they should have been one number rather than several**, which is the `filing` cell's batch rule; a bundle of that shape on the board is a filing that was split and is worth re-reading as one. `Status` is availability; the board's built-in `Linked pull requests` column is what a refresher reads to keep `In flight` true.

## What reaches the board, and what moves the pool

**Nothing reaches this board that has not been framed**, and `sync` refuses to empty a populated board on an empty framed set rather than reading a setup mistake as a decision; `sync --allow-empty` is how an operator says the emptiness is real. **Three routes frame something and the shortlist is only one of them** — what the owner filed, or told a session to file, is decided from the start and arrives framed, and a crossing the push put to them unasked is framed if they take it, so a refresh meeting a framed issue that went through no shortlist is meeting the ordinary case rather than a mistake. The `filing` cell owns that rule.

**The pool moves between refreshes once it has ratings to move, and two things read that.** Nothing moves before that: membership is the absence of the framed label, so every open issue is in the pool from the start, but the fade reaches only what somebody has rated and the accrual only what carries cause links. The `filing` cell's own script carries a `cycle` command, which reports what rose from the symptoms under it, what faded to the floor, and the next bounded few nobody has asked about a cause; `python tools/pool_rot.py` names the filings that name a **path** the tree no longer holds — paths only, since a quote check shipped for one revision and was deleted as an approximate half nothing ran. Neither closes anything here — the fade closes only where a repository sets `fade.closes`, and the rot check never does, its two survivors over this repository's own pool being one genuine rot and one filename invented inside a probe.

## What a refresh runs before it ranks

**Run the `filing` cell's `pushed` command as part of the refresh, and finish every crossing it names.** What a crossing then takes is the `filing` cell's procedure, not restated here. A refresh that reads the list and stops leaves an item the owner never heard about, so a crossing read is a crossing carried through. The note carries what crossed, which the command separates from everything over the line already having been put.

**Run `python tools/pool_rot.py` as part of the refresh**, and put what it names in the note. It is cheap, it is the only thing in this repository that looks at whether a filing's evidence still exists, and a check nothing obliges is a check nobody runs — which is what it was for one revision. It closes nothing and reports two or three rows; reading them is the whole of the obligation.

**Run the `filing` cell's `cycle` command as part of the refresh, and answer the ones it names.** Nothing else runs it. Ask why for each, then link it under its cause or `assess <N> --none`; what an assessment takes is that cell's. **How many it names is its `assessment.per_cycle`, and the shortlist gate those answers clear reads a second key, `assessment.before_shortlist`**, so re-pacing the pool moves both. **The note carries how many were answered, what each answer was, and which were left** — nothing else stores an answer. [D-522]

## Writing the plan: the bundle, the two guards `apply` enforces, and the owner's exception

**Start from what is on the board.** Move what a named board change justifies and leave the rest. This is not a restriction on what you may move; you may move anything you can argue for. It is that rebuilding the order from a blank page re-rolls the bundling judgment — the expensive part, and the part that varies most between sessions — and costs the board roughly an order of magnitude more writes than adjusting what changed.

**A cause and its framed open symptoms are one bundle, and the refresh reads it off the sub-issue links rather than re-deriving it.** A symptom sitting in the pool is not on the board at all, so it is neither ranked nor blocked and never reaches the guard below. Name the bundle for the cause, rank the cause above every symptom, and give each symptom a status that takes it out of contention while the cause is open — `Blocked` ordinarily, and `In flight` for a symptom that has a pull request open against it, whether that fix came out of the cause or not — the body's reading rule being unable to see `Bundle` or position. [D-415] [D-429] **`apply` refuses a plan that leaves a symptom in contention, or ranks one above its cause**, so those two are checked rather than remembered and the refusal names the symptom, its cause and what to do; **the bundle name is not checked** and is yours to get right.

**`causes` prints the cause groups over the open set, marking each member the board does not hold**, so the parentage is in hand before the plan is written rather than discovered by being refused. It is not the set the guard reads: the guard runs over plan rows, so a symptom in the pool never reaches it, and a plan row written for one is refused.

```bash
python tools/board.py causes
```

Read it from there and not by hand. The links are fields, and `gh issue list` exposes neither `parent` nor `issueType`, so the one-call body read this paragraph used to name cannot carry them; a hand-written GraphQL read can, and the one this cell used to print was capped at a hundred against an open set already past it — the short-read hazard this whole cell is about, arriving through the command offered as the remedy. `causes` pages.

A parent carrying no `cause` label is an ordinary task decomposition and is not a bundle, so it never reaches the guard; **a causal relationship carried in prose because it could not be linked groups the same way and reaches the guard no more than that one does**, the refresh being judgment rather than a parser. **Keep the bundle name to letters, digits, spaces and `#/_.()-`** — the transport refuses anything else at parse time, and this repository's issue titles are dense in colons, em dashes and ampersands, so a name lifted from one usually has to be trimmed.

The owner may rule a symptom worked on its own while its cause is open; that exception is his, and the note carries it in his words — **and so does the plan**, on a comment line naming `owner-exception`, the issue number and the sentence he actually ruled. **His ruling lifts both halves of the guard for that symptom** — it may be available, and it may rank above its cause — a symptom being worked being a claim about both. A bare flag is refused, so is a placeholder in his place, and so is any line that reads as the directive and misses its form — an ignored line would leave the plan refused for lacking the very ruling someone had just written into it. His words are the point of it. **`show` does not carry an exception forward**, the plan being rebuilt from the board's own rows, so a live one is re-entered from the last note at every refresh until its cause closes.

## Reconciling against settling

**Two jobs that look alike and must not be merged.** *Reconciling* asks whether the board holds the framed set. *Settling* asks whether the ordered read has caught up with the board. They return opposite answers about the same newly added issue — reconcile says place it, settle says wait for it — so a single membership comparison cannot do both, and only settling may stop the run.

## The commands, in the order they run

If the board does not exist yet, `python tools/board.py init` creates it and its fields once. It refuses when a project of that title already exists, because a second one leaves the title ambiguous and every command refusing.

```
python tools/board.py sync --dry-run        # what it would add and archive
python tools/board.py sync                  # reconcile, then settle
python tools/board.py show --plan plan.tsv  # current state, one issue per line
#   edit plan.tsv: reorder lines, and give every new row a band, bundle and status
python tools/board.py apply --plan plan.tsv --dry-run
python tools/board.py apply --plan plan.tsv
#   write the note from what sync and apply reported, then:
python tools/board.py note --body note.md
```

**What that note owes its reader is `../references/the-refresh-note.md`.** Obligations live there that neither `sync` nor `apply` reports, so a note written from what those two returned is short of them.

**Issues `sync` just added arrive blank**, so `show` writes them with `-` in every column and `apply` refuses the plan until each has been placed. That refusal is the point — an unplaced row would otherwise sit in the order claiming nothing — but it means the plan is edited before `apply`, never round-tripped untouched. A bundle name may hold letters, digits, spaces and `#/_.()-`; anything else is refused at parse time, because it would not survive being sent to GitHub intact.

**The target membership always comes from `gh issue list`, filtered to the framed set, never from the board.** The board's ordered connection returns a short list and a matching short `totalCount` together for several seconds after any write, so it cannot be asked whether it is complete — the count goes stale in lockstep with the list. A refresh that trusted it would rank an incomplete set and report success. `sync` waits up to **60 seconds** for the ordered read to catch up and then halts, naming what never appeared. **The remedy is to run `sync` again** — the adds it already made stand, and adding an item already present is a no-op, so a second pass costs nothing and usually settles. Standing a whole board up is the case that reaches the bound; a refresh placing one or two issues does not.

**A trial run against a scratch board starts empty, and that is the one case this order does not fit.** `sync` will report every framed issue as an arrival and `apply`'s diff will have no prior order to compare against, so neither supplies the deltas a note is written from, and ranking from what `show` returns would be the blank-page rebuild this cell tells you not to do. Read the live board first — `gh project item-list <number> --owner <owner> --format json --limit 200`, which writes nothing — and edit that order into your plan. **The limit is not optional:** that command defaults to 30, and a base you ranked from a truncated read is the short-read hazard this whole cell is about, arriving through the one command offered as the remedy. Check `totalCount` in the payload against what you got. Say in the note that the run was a trial and where its base came from.

`plan.tsv` and `note.md` are working files, not part of the tree — write them outside the repository, or delete them when the refresh is done.

---
name: board
description: This repository's ranked board and the standing answer to what to pick up next — how to read it, how a refresh reconciles it against the framed set and settles the ordered read before writing, and what the refresh note owes including the look at shipped work that docs/values.md asks for. Use when asking what to work on next here, when the board has moved, or when writing or reading a refresh note; not for whether work is worth doing, and not for filing.
---

# board

**Purpose:** keep a standing, honest answer to *what should I pick up next* between conversations, so the judgment that produced it is inherited rather than re-rolled. **Audience:** any session here reading the board for its next piece of work, or refreshing it after the board moved. **Success:** a session can read the answer off the board without ranking anything; a session that finds nothing available on it knows the answer comes from the pool rather than from ranking harder; a refresh moves what changed and says what it moved and why; and no refresh ever writes an ordering from a read it could not confirm was complete.

The board is a GitHub Projects v2 project titled `tradecraft board`, linked to this repository. **It holds the framed issues and only those** — the work somebody decided to do. A refresh archives an item whose issue has closed or has gone back to the pool, so the board is not where to look for what was already decided or tried, and it is not where a filing lands. `tools/board.py` is its transport: it does everything that is not judgment, so judgment is what your context is spent on. Every command runs from the repository root and needs `gh` carrying both the `project` and `repo` scopes. `TRADECRAFT_BOARD_TITLE` points the transport at a different board — a scratch one for a trial run — and `TRADECRAFT_BOARD_OWNER` and `_REPO` move it to another repository; two projects sharing a title is refused rather than guessed at.

## Reading it

**The answer is the first item that is not `In progress`, `In flight`, `Blocked` or `Deferred`, and not blank.** Position alone is not the answer and never was: the top of the board is usually something already being worked. A consumer that reads position 1 and stops has read the board wrong.

```
python tools/board.py next     # the answer, with its title and what is behind it
python tools/board.py show     # the whole board, in order, as a plan file
python tools/board.py notes    # the last refresh notes, newest first
```

**In the browser**, the board is at `https://github.com/orgs/Grimblaz-and-Friends/projects/5`. Its `Queue` view carries `Band` and `Bundle` as columns, so the grouping is legible without reading any prose — which is the whole reason the fields exist, and they were invisible there until someone looked. **To collapse the board by bundle, group the view by `Bundle` once, from the view menu.** That is a click and not a command: `updateProjectV2View` sets a view's name, layout, filter and which fields it shows, and has no grouping in its configuration input, so a session can restore the columns and cannot restore the grouping. The same is true of the auto-add workflow.

`next --count N` widens what it shows either side of the answer; `notes --limit N` asks for more notes. `show` prints the plan format — bare issue numbers, no titles — because it feeds `apply`; `show --plan FILE` writes that file and prints only the path it wrote.

**Read the last note before you act on the order.** The board carries the conclusion; the note carries the reasoning that produced it, and the deltas that say which parts of the order are fresh judgment rather than inherited. A session that reads the order alone re-derives what the previous one already worked out.

`Band` records where in the board's own shape an item sits — `Standing`, `Front`, `Bundles`, `Review-set`, `Tail`. **It is not availability**, with one exception the transport enforces: `Standing` claims an item is out of contention, so a `Standing` row must carry a status that says so, and a plan pairing `Standing` with `Queued` is refused. `Bundle` names the group an issue is worked as part of, so a session can see what belongs together without reading any prose. **The test is what one change would take, or one cause the group carries a tie to, and shared origin is not a bundle** — issues that merely came out of the same review, or name the same issue in a tie that is not the cause link, are related and not grouped; labelling them as one tells the next ranking session to plan one pull request for unrelated mechanisms. Three shapes are lawful and the name should say which: a **prospective pull request**, where one change closes the whole group; a **cause-led group**, where one issue is the cause the rest are linked under as sub-issues; and a **cluster**, where the group moves and is deferred together but a change may take only part of it — `PR #322` closed three of one five-item cluster and left two open, which is that shape working rather than failing. **Where a filer had them all in hand under one cause they could point at, they should have been one number rather than several**, which is the `filing` cell's batch rule; a bundle of that shape on the board is a filing that was split and is worth re-reading as one. `Status` is availability, and it is written by hand from the plan like every other value — **including `In flight`, which nothing corroborates for you**; the board's built-in `Linked pull requests` column is what a refresher reads to keep it true.

## What is not on it

**Every other open issue is in the pool: filed and not yet decided on.** The board answers *what next* out of decided work, so when it runs out the move is not to rank harder -- it is to raise a shortlist out of the pool and put it to the owner. **That shortlist is gated**: it refuses while anything at the top of the pool has never been asked whether it has a cause, naming which items block and what answers for each, so the move begins with those questions rather than with the shortlist. `--unassessed` shortlists anyway and gives up the guarantee. The pool, its ratings and the script that lists it are the `filing` cell's; the form that ask takes is the `engagement` cell's.

**Nothing reaches this board that has not been framed**, and `sync` refuses to empty a populated board on an empty framed set rather than reading a setup mistake as a decision; `sync --allow-empty` is how an operator says the emptiness is real. **Three routes frame something and the shortlist is only one of them** — what the owner filed, or told a session to file, is decided from the start and arrives framed, and a crossing the push put to them unasked is framed if they take it, so a refresh meeting a framed issue that went through no shortlist is meeting the ordinary case rather than a mistake. The `filing` cell owns that rule.

**The pool moves between refreshes once it has ratings to move, and two things read that.** Nothing moves before that: membership is the absence of the framed label, so every open issue is in the pool from the start, but the fade reaches only what somebody has rated and the accrual only what carries cause links. The `filing` cell's own script carries a `cycle` command, which reports what rose from the symptoms under it, what faded to the floor, and the next bounded few nobody has asked about a cause; `python tools/pool_rot.py` names the filings that name a **path** the tree no longer holds — paths only, since a quote check shipped for one revision and was deleted as an approximate half nothing ran. Neither closes anything here — the fade closes only where a repository sets `fade.closes`, and the rot check never does, its two survivors over this repository's own pool being one genuine rot and one filename invented inside a probe.

## Refreshing it

Run a refresh when the board moved — an issue framed or returned to the pool, an issue closed, a pull request merged, a dependency shifted. A filing no longer moves it.

**Run the `filing` cell's `pushed` command as part of the refresh, and finish every crossing it names.** What a crossing then takes is the `filing` cell's procedure, not restated here. A refresh that reads the list and stops leaves an item the owner never heard about, so a crossing read is a crossing carried through. The note carries what crossed, which the command separates from everything over the line already having been put.

**Run `python tools/pool_rot.py` as part of the refresh**, and put what it names in the note. It is cheap, it is the only thing in this repository that looks at whether a filing's evidence still exists, and a check nothing obliges is a check nobody runs — which is what it was for one revision. It closes nothing and reports two or three rows; reading them is the whole of the obligation.

**Run the `filing` cell's `cycle` command as part of the refresh, and answer the ones it names.** Nothing else runs it. Ask why for each, then link it under its cause or `assess <N> --none`; what an assessment takes is that cell's. **How many it names is its `assessment.per_cycle`, and the shortlist gate those answers clear reads a second key, `assessment.before_shortlist`**, so re-pacing the pool moves both. **The note carries how many were answered, what each answer was, and which were left** — nothing else stores an answer. [D-522]

**Start from what is on the board.** Move what a named board change justifies and leave the rest. This is not a restriction on what you may move; you may move anything you can argue for. It is that rebuilding the order from a blank page re-rolls the bundling judgment — the expensive part, and the part that varies most between sessions — and costs the board roughly an order of magnitude more writes than adjusting what changed.

**A cause and its framed open symptoms are one bundle, and the refresh reads it off the sub-issue links rather than re-deriving it.** A symptom sitting in the pool is not on the board at all, so it is neither ranked nor blocked and never reaches the guard below. Name the bundle for the cause, rank the cause above every symptom, and give each symptom a status that takes it out of contention while the cause is open — `Blocked` ordinarily, and `In flight` for a symptom that has a pull request open against it, whether that fix came out of the cause or not — the reading rule above being unable to see `Bundle` or position. [D-415] [D-429] **`apply` refuses a plan that leaves a symptom in contention, or ranks one above its cause**, so those two are checked rather than remembered and the refusal names the symptom, its cause and what to do; **the bundle name is not checked** and is yours to get right.

**`causes` prints the cause groups over the open set, marking each member the board does not hold**, so the parentage is in hand before the plan is written rather than discovered by being refused. It is not the set the guard reads: the guard runs over plan rows, so a symptom in the pool never reaches it, and a plan row written for one is refused.

```bash
python tools/board.py causes
```

Read it from there and not by hand. The links are fields, and `gh issue list` exposes neither `parent` nor `issueType`, so the one-call body read this paragraph used to name cannot carry them; a hand-written GraphQL read can, and the one this cell used to print was capped at a hundred against an open set already past it — the short-read hazard this whole cell is about, arriving through the command offered as the remedy. `causes` pages.

A parent carrying no `cause` label is an ordinary task decomposition and is not a bundle, so it never reaches the guard; **a causal relationship carried in prose because it could not be linked groups the same way and reaches the guard no more than that one does**, the refresh being judgment rather than a parser. **Keep the bundle name to letters, digits, spaces and `#/_.()-`** — the transport refuses anything else at parse time, and this repository's issue titles are dense in colons, em dashes and ampersands, so a name lifted from one usually has to be trimmed.

The owner may rule a symptom worked on its own while its cause is open; that exception is his, and the note carries it in his words — **and so does the plan**, on a comment line naming `owner-exception`, the issue number and the sentence he actually ruled. **His ruling lifts both halves of the guard for that symptom** — it may be available, and it may rank above its cause — a symptom being worked being a claim about both. A bare flag is refused, so is a placeholder in his place, and so is any line that reads as the directive and misses its form — an ignored line would leave the plan refused for lacking the very ruling someone had just written into it. His words are the point of it. **`show` does not carry an exception forward**, the plan being rebuilt from the board's own rows, so a live one is re-entered from the last note at every refresh until its cause closes.

**Two jobs that look alike and must not be merged.** *Reconciling* asks whether the board holds the framed set. *Settling* asks whether the ordered read has caught up with the board. They return opposite answers about the same newly added issue — reconcile says place it, settle says wait for it — so a single membership comparison cannot do both, and only settling may stop the run.

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

**Issues `sync` just added arrive blank**, so `show` writes them with `-` in every column and `apply` refuses the plan until each has been placed. That refusal is the point — an unplaced row would otherwise sit in the order claiming nothing — but it means the plan is edited before `apply`, never round-tripped untouched. A bundle name may hold letters, digits, spaces and `#/_.()-`; anything else is refused at parse time, because it would not survive being sent to GitHub intact.

**The target membership always comes from `gh issue list`, filtered to the framed set, never from the board.** The board's ordered connection returns a short list and a matching short `totalCount` together for several seconds after any write, so it cannot be asked whether it is complete — the count goes stale in lockstep with the list. A refresh that trusted it would rank an incomplete set and report success. `sync` waits up to **60 seconds** for the ordered read to catch up and then halts, naming what never appeared. **The remedy is to run `sync` again** — the adds it already made stand, and adding an item already present is a no-op, so a second pass costs nothing and usually settles. Standing a whole board up is the case that reaches the bound; a refresh placing one or two issues does not.

**A trial run against a scratch board starts empty, and that is the one case this order does not fit.** `sync` will report every framed issue as an arrival and `apply`'s diff will have no prior order to compare against, so neither supplies the deltas a note is written from, and ranking from what `show` returns would be the blank-page rebuild this cell tells you not to do. Read the live board first — `gh project item-list <number> --owner <owner> --format json --limit 200`, which writes nothing — and edit that order into your plan. **The limit is not optional:** that command defaults to 30, and a base you ranked from a truncated read is the short-read hazard this whole cell is about, arriving through the one command offered as the remedy. Check `totalCount` in the payload against what you got. Say in the note that the run was a trial and where its base came from.

`plan.tsv` and `note.md` are working files, not part of the tree — write them outside the repository, or delete them when the refresh is done.

## What the refresh note owes its reader

The note is posted as a project status update, dated and kept, and read back with `notes`. It is what the owner actually reads, so it carries what a board cannot. **Its material comes from two places and neither alone is enough:** `sync` reports what arrived and what was archived, `apply` reports what moved and what was relabelled. `apply`'s diff cannot see membership — it refuses any plan whose membership differs from the board — so a note written from it alone will call a refresh unchanged that added and closed issues.

- **The deltas** — what moved, what arrived, what closed, each with its one-line reason. Not a restatement of the board. **A refresh that changed nothing says so**, in one line.
- **The watch-items** — what the board as a whole is trending toward, which no single item shows. Rate of arrival against rate of closure, and any single item whose settling would reshape everything behind it.
- **The assessments** — the answers the cycle above produced, and which it left.
- **The drift look**, below.
- **The reach line** — the charter's row from `python tools/lint.py`'s pointer-reach block, beside the figure the last note to carry one gave and that note's date. It covers the charter and the shipped cells it reaches, so repo-only prose here can grow without moving it. [D-522]
- **The ceiling line** — the same command's `cell bodies over where they stood` line, copied whole: every cell body past where it stood when its ratchet was set, and by how much. **It is a reading and nothing files from it**, which is the point of carrying it here — the growth reaches the person who decides whether a split is worth buying, at the moment they are already reading the board. `none` is a result like any other and is carried too, an absent line being indistinguishable from a refresh that did not look. [D-544]

Reasons, not conclusions alone: the note is read cold days later by someone reconstructing why the board looks like this. **A figure in a note carries the command that derives it** — the note is kept and never edited, so a number standing alone cannot be re-checked by the reader who needs it most.

## The drift look

`docs/values.md` asks for a periodic look at what actually shipped — *"if it's all short-horizon and measurable, the drift is happening regardless of how each call felt"* — and nothing else performs it. Every refresh note carries an observation over recently closed work, derived rather than recalled:

```
gh issue list --repo Grimblaz-and-Friends/tradecraft --state closed --limit 40 \
  --json number,title,closedAt,stateReason --jq '[.[]|select(.stateReason=="COMPLETED")]'
gh issue list --repo Grimblaz-and-Friends/tradecraft --state all --limit 400 \
  --search 'created:>=YYYY-MM-DD' --json number --jq length
```

`stateReason` is not optional: without it the set includes work closed `NOT_PLANNED`, so the look forms its observation partly over things that were declined rather than shipped. The second command supplies the arrival half of the watch-items; substitute a date and say in the note which window you used.

**State an observation, not a list.** A list of closed issue numbers is material for the look, not the look — a reader given one can say only that a single instance is not drift, which is the wall this exists to get past. Name what the shipped mix is weighted toward, and whether prevention, tooling and craft are represented in it or only the measurable.

## The board is a work surface, not a record

**The board is not a record.** It is a live surface like the issue list itself, maintained precisely *because* it is not history, and rewriting it is the point rather than a violation. The refresh notes are the append-only part: each is kept, none is edited. A session that declines to touch the board on records grounds has misread which of the two it is looking at.

---
name: board
description: This repository's ranked board and the standing answer to what to pick up next — how to read it, how a refresh reconciles it against the open issue list and settles the ordered read before writing, and what the refresh note owes including the look at shipped work that docs/values.md asks for. Use when asking what to work on next here, when the board has moved, or when writing or reading a refresh note; not for whether work is worth doing, and not for filing.
---

# board

**Purpose:** keep a standing, honest answer to *what should I pick up next* between conversations, so the judgment that produced it is inherited rather than re-rolled. **Audience:** any session here reading the board for its next piece of work, or refreshing it after the board moved. **Success:** a session can read the answer off the board without ranking anything; a refresh moves what changed and says what it moved and why; and no refresh ever writes an ordering from a read it could not confirm was complete.

The board is a GitHub Projects v2 project titled `tradecraft board`, linked to this repository. **It holds the open issues and only those** — a refresh archives an item whose issue has closed, so the board is not where to look for what was already decided or tried. `tools/board.py` is its transport: it does everything that is not judgment, so judgment is what your context is spent on. Every command runs from the repository root and needs `gh` carrying both the `project` and `repo` scopes. `TRADECRAFT_BOARD_TITLE` points the transport at a different board — a scratch one for a trial run — and `TRADECRAFT_BOARD_OWNER` and `_REPO` move it to another repository; two projects sharing a title is refused rather than guessed at.

## Reading it

**The answer is the first item that is not `In progress`, `In flight`, `Blocked` or `Deferred`, and not blank.** Position alone is not the answer and never was: the top of the board is usually something already being worked. A consumer that reads position 1 and stops has read the board wrong.

```
python tools/board.py next     # the answer, with its title and what is behind it
python tools/board.py show     # the whole board, in order, as a plan file
python tools/board.py notes    # the last refresh notes, newest first
```

`next --count N` widens what it shows either side of the answer; `notes --limit N` asks for more notes. `show` prints the plan format — bare issue numbers, no titles — because it feeds `apply`; `show --plan FILE` writes that file and prints only the path it wrote.

**Read the last note before you act on the order.** The board carries the conclusion; the note carries the reasoning that produced it, and the deltas that say which parts of the order are fresh judgment rather than inherited. A session that reads the order alone re-derives what the previous one already worked out.

`Band` records where in the board's own shape an item sits — `Standing`, `Front`, `Bundles`, `Review-set`, `Tail`. **It is not availability**, with one exception the transport enforces: `Standing` claims an item is out of contention, so a `Standing` row must carry a status that says so, and a plan pairing `Standing` with `Queued` is refused. `Bundle` names the prospective single change an issue belongs to, so a session can see what one pull request would close together without reading any prose. `Status` is availability, and it is written by hand from the plan like every other value — **including `In flight`, which nothing corroborates for you**; the board's built-in `Linked pull requests` column is what a refresher reads to keep it true.

## Refreshing it

Run a refresh when the board moved — an issue filed or closed, a pull request merged, a dependency shifted.

**Start from what is on the board.** Move what a named board change justifies and leave the rest. This is not a restriction on what you may move; you may move anything you can argue for. It is that rebuilding the order from a blank page re-rolls the bundling judgment — the expensive part, and the part that varies most between sessions — and costs the board roughly an order of magnitude more writes than adjusting what changed.

**Two jobs that look alike and must not be merged.** *Reconciling* asks whether the board holds the open set. *Settling* asks whether the ordered read has caught up with the board. They return opposite answers about the same newly added issue — reconcile says place it, settle says wait for it — so a single membership comparison cannot do both, and only settling may stop the run.

If the board does not exist yet, `python tools/board.py init` creates it and its fields once. It refuses when a project of that title already exists, because a second one leaves the title ambiguous and every command refusing.

```
python tools/board.py sync                  # reconcile, then settle
python tools/board.py show --plan plan.tsv  # current state, one issue per line
#   edit plan.tsv: reorder lines, and give every new row a band, bundle and status
python tools/board.py apply --plan plan.tsv --dry-run
python tools/board.py apply --plan plan.tsv
#   write the note from what sync and apply reported, then:
python tools/board.py note --body note.md
```

**Issues `sync` just added arrive blank**, so `show` writes them with `-` in every column and `apply` refuses the plan until each has been placed. That refusal is the point — an unplaced row would otherwise sit in the order claiming nothing — but it means the plan is edited before `apply`, never round-tripped untouched. A bundle name may hold letters, digits, spaces and `#/_.()-`; anything else is refused at parse time, because it would not survive being sent to GitHub intact.

**The target membership always comes from `gh issue list`, never from the board.** The board's ordered connection returns a short list and a matching short `totalCount` together for several seconds after any write, so it cannot be asked whether it is complete — the count goes stale in lockstep with the list. A refresh that trusted it would rank an incomplete set and report success. `sync` waits up to **60 seconds** for the ordered read to catch up and then halts, naming what never appeared. **The remedy is to run `sync` again** — the adds it already made stand, and adding an item already present is a no-op, so a second pass costs nothing and usually settles. Standing a whole board up is the case that reaches the bound; a refresh placing one or two issues does not.

**A trial run against a scratch board starts empty, and that is the one case this order does not fit.** `sync` will report every open issue as an arrival and `apply`'s diff will have no prior order to compare against, so neither supplies the deltas a note is written from, and ranking from what `show` returns would be the blank-page rebuild this cell tells you not to do. Read the live board first — `gh project item-list <number> --owner <owner> --format json`, which writes nothing — and edit that order into your plan. Say in the note that the run was a trial and where its base came from.

`plan.tsv` and `note.md` are working files, not part of the tree — write them outside the repository, or delete them when the refresh is done.

## What the refresh note owes its reader

The note is posted as a project status update, dated and kept, and read back with `notes`. It is what the owner actually reads, so it carries what a board cannot. **Its material comes from two places and neither alone is enough:** `sync` reports what arrived and what was archived, `apply` reports what moved and what was relabelled. `apply`'s diff cannot see membership — it refuses any plan whose membership differs from the board — so a note written from it alone will call a refresh unchanged that added and closed issues.

- **The deltas** — what moved, what arrived, what closed, each with its one-line reason. Not a restatement of the board. **A refresh that changed nothing says so**, in one line.
- **The watch-items** — what the board as a whole is trending toward, which no single item shows. Rate of arrival against rate of closure, and any single item whose settling would reshape everything behind it.
- **The drift look**, below.

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

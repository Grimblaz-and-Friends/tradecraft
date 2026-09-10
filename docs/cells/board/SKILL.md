---
name: board
description: This repository's ranked board and the standing answer to what to pick up next — how to read it, how a refresh reconciles it against the framed set and settles the ordered read before writing, and what the refresh note owes including the look at shipped work that docs/values.md asks for. Use when asking what to work on next here, when the board has moved, or when writing or reading a refresh note; not for whether work is worth doing, and not for filing.
---

# board

**Purpose:** keep a standing, honest answer to *what should I pick up next* between conversations, so the judgment that produced it is inherited rather than re-rolled. **Audience:** any session here reading the board for its next piece of work, or refreshing it after the board moved. **Success:** a session can read the answer off the board without ranking anything; a session that finds nothing available on it knows the answer comes from the pool rather than from ranking harder; a refresh moves what changed and says what it moved and why; and no refresh ever writes an ordering from a read it could not confirm was complete.

The board is a GitHub Projects v2 project titled `tradecraft board`, linked to this repository. **It holds the framed issues and only those** — the work somebody decided to do. A refresh archives an item whose issue has closed or has gone back to the pool, so the board is not where to look for what was already decided or tried, and it is not where a filing lands. `tools/board.py` is its transport: it does everything that is not judgment, so judgment is what your context is spent on. Every command runs from the repository root and needs `gh` carrying both the `project` and `repo` scopes. `TRADECRAFT_BOARD_TITLE` points the transport at a different board — a scratch one for a trial run — and `TRADECRAFT_BOARD_OWNER` and `_REPO` move it to another repository; two projects sharing a title is refused rather than guessed at.

## Where this cell's depth lives

- **Refreshing the board after it moved, clearing a symptom's hold when its cause closes, or looking at the board in the browser** → `references/refreshing-it.md`: where the board is in the browser and what its `Queue` view cannot be restored to, what the three fields mean and who writes them, what reaches the board and what moves the pool between refreshes, the cause-and-symptom bundle and the two guards `apply` enforces over a plan, the owner's exception and the form it takes, reconciling against settling, the commands in the order they run, and the trial run that is the one case that order does not fit.
- **Writing a refresh note, or reading one to see what it should have carried** → `references/the-refresh-note.md`: what a note owes — the deltas, the watch-items, the assessments, what crossed, the rot rows, the drift look, the reach line and the ceiling line — the rule that a figure in it carries the command that derives it, and the look at recently closed work that `docs/values.md` asks for, with the commands the look is derived from.

## Reading it

**The answer is the first item that is not `In progress`, `In flight`, `Blocked` or `Deferred`, and not blank.** Position alone is not the answer and never was: the top of the board is usually something already being worked. A consumer that reads position 1 and stops has read the board wrong. **Where a row out of contention shares the answer's bundle name, it is usually a symptom held while its cause is open** — `references/refreshing-it.md` carries the three shapes a bundle takes, and the bundle column is the only place any of them shows.

```
python tools/board.py next     # the answer, with its title and what is behind it
python tools/board.py show     # the whole board, in order, as a plan file
python tools/board.py notes    # the last refresh notes, newest first
```

`next --count N` widens what it shows either side of the answer; `notes --limit N` asks for more notes. `show` prints the plan format — bare issue numbers, no titles — because it feeds `apply`; `show --plan FILE` writes that file and prints only the path it wrote.

**Every status is written by hand from the last refresh's plan — `In flight` included, which nothing corroborates for you.** A row can be stale in either direction.

**Read the last note before you act on the order.** The board carries the conclusion; the note carries the reasoning that produced it, and the deltas that say which parts of the order are fresh judgment rather than inherited. A session that reads the order alone re-derives what the previous one already worked out.

## What is not on it

**Every other open issue is in the pool: filed and not yet decided on.** The board answers *what next* out of decided work, so when it runs out the move is not to rank harder -- it is to raise a shortlist out of the pool and put it to the owner. **That shortlist is gated**: it refuses while anything at the top of the pool has never been asked whether it has a cause, naming which items block and what answers for each, so the move begins with those questions rather than with the shortlist. `--unassessed` shortlists anyway and gives up the guarantee. The pool, its ratings and the script that lists it are the `filing` cell's; the form that ask takes is the `engagement` cell's.

## Refreshing it

Run a refresh when the board moved — an issue framed or returned to the pool, an issue closed, a pull request merged, a dependency shifted. A filing no longer moves it.

What a refresh runs before it ranks, what it reconciles and settles before it writes, and the guards over the plan: `references/refreshing-it.md`. What the note it ends on owes its reader: `references/the-refresh-note.md`.

## The board is a work surface, not a record

**The board is not a record.** It is a live surface like the issue list itself, maintained precisely *because* it is not history, and rewriting it is the point rather than a violation. The refresh notes are the append-only part: each is kept, none is edited. A session that declines to touch the board on records grounds has misread which of the two it is looking at.

---
name: board
description: This repository's ranked board and the standing answer to what to pick up next — how to read it, how a refresh reconciles it against the open issue list and settles the ordered read before writing, and what the refresh note owes including the look at shipped work that docs/values.md asks for. Use when asking what to work on next here, when the board has moved, or when writing or reading a refresh note; not for whether work is worth doing, and not for filing.
---

# board

**Purpose:** keep a standing, honest answer to *what should I pick up next* between conversations, so the judgment that produced it is inherited rather than re-rolled. **Audience:** any session here reading the board for its next piece of work, or refreshing it after the board moved. **Success:** a session can read the answer off the board without ranking anything; a refresh moves what changed and says what it moved and why; and no refresh ever writes an ordering from a read it could not confirm was complete.

The board is a GitHub Projects v2 project titled `tradecraft board`, linked to this repository. `tools/board.py` is its transport: it does everything that is not judgment, so judgment is what your context is spent on. Reading it needs the `project` scope on `gh`. The title is the only handle the transport has, so `TRADECRAFT_BOARD_TITLE` points it at a different board -- a scratch one for a trial run -- and two projects sharing a title is refused rather than guessed at.

## Reading it

**The answer is the first item that is not `In progress`, `In flight`, `Blocked` or `Deferred`.** Position alone is not the answer and never was: the top of the board is usually something already being worked. A consumer that reads position 1 and stops has read the board wrong.

```
python tools/board.py next     # the answer, with its title and what is behind it
python tools/board.py show     # the whole board, in order, as a plan file
python tools/board.py notes    # the last refresh notes, newest first
```

`next` applies the rule for you. `show` prints the plan format -- bare issue numbers, no titles -- because it round-trips into `apply`; `show --plan FILE` writes that file and prints nothing else.

**Read the last note before you act on the order.** The board carries the conclusion; the note carries the reasoning that produced it, and the deltas that say which parts of the order are fresh judgment rather than inherited. A session that reads the order alone re-derives what the previous one already worked out.

`Band` records where in the board's own shape an item sits — `Standing`, `Front`, `Bundles`, `Review-set`, `Tail`. It is not availability and must not be read as one. `Bundle` names the prospective single change an issue belongs to, so a session can see what one pull request would close together without reading any prose. `Status` is availability, and `In flight` is corroborated by the built-in read-only `Linked pull requests` field rather than asserted.

## Refreshing it

Run a refresh when the board moved — an issue filed or closed, a pull request merged, a dependency shifted.

**Start from what is on the board.** Move what a named board change justifies and leave the rest. This is not a restriction on what you may move; you may move anything you can argue for. It is that rebuilding the order from a blank page re-rolls the bundling judgment — the expensive part, and the part that varies most between sessions — and costs the board roughly an order of magnitude more writes than adjusting what changed.

**Two jobs that look alike and must not be merged.** *Reconciling* asks whether the board holds the open set. *Settling* asks whether the ordered read has caught up with the board. They return opposite answers about the same newly added issue — reconcile says place it, settle says wait for it — so a single membership comparison cannot do both, and only settling may stop the run.

If the board does not exist yet, `python tools/board.py init` creates it and its fields once. It is safe only before the board has items: it rewrites the provisioned `Status` field's options wholesale, which would clear that column on a board already carrying values.

```
python tools/board.py sync                  # reconcile, then settle
python tools/board.py show --plan plan.tsv  # current state, one issue per line
#   edit plan.tsv: reorder lines, change band, bundle or status
python tools/board.py apply --plan plan.tsv --dry-run
python tools/board.py apply --plan plan.tsv
python tools/board.py note --body note.md
```

**The target membership always comes from `gh issue list`, never from the board.** The board's ordered connection returns a short list and a matching short `totalCount` together for several seconds after any write, so it cannot be asked whether it is complete — the count goes stale in lockstep with the list. A refresh that trusted it would rank an incomplete set and report success. `sync` halts rather than proceeding if the ordered read never catches up, and names what never appeared. **The remedy is to run `sync` again** -- the adds it already made stand, and adding an item already present is a no-op, so a second pass costs nothing and usually settles.

## What the refresh note owes its reader

The note is posted as a project status update, dated and kept, and read back with `notes`. It is what the owner actually reads, so it carries what a board cannot:

- **The deltas** — what moved, what arrived, what closed, each with its one-line reason. Not a restatement of the board. **A refresh that changed nothing says so**, in one line.
- **The watch-items** — what the board as a whole is trending toward, which no single item shows. Rate of arrival against rate of closure, and any single item whose settling would reshape everything behind it.
- **The drift look**, below.

Reasons, not conclusions alone: the note is read cold days later by someone reconstructing why the board looks like this.

## The drift look

`docs/values.md` asks for a periodic look at what actually shipped — *"if it's all short-horizon and measurable, the drift is happening regardless of how each call felt"* — and nothing else performs it. Every refresh note carries an observation over recently closed work, derived rather than recalled:

```
gh issue list --repo Grimblaz-and-Friends/tradecraft --state closed --limit 40 --json number,title,closedAt
```

**State an observation, not a list.** A list of closed issue numbers is material for the look, not the look — a reader given one can say only that a single instance is not drift, which is the wall this exists to get past. Name what the shipped mix is weighted toward, and whether prevention, tooling and craft are represented in it or only the measurable.

## The board is a work surface, not a record

Records here are append-only and never maintained. **The board is not one.** It is a live surface like the issue list itself, maintained precisely *because* it is not history, and rewriting it is the point rather than a violation. The refresh notes are the append-only part: each is kept, none is edited. A session that declines to touch the board on records grounds has misread which of the two it is looking at.

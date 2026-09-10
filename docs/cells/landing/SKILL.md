---
name: landing
description: This repository's own procedure for taking a change from a fresh branch to an open pull request — the order the steps run in, the guards that must pass before a commit, what the pull request body states, and when the plugin version is bumped. Use when a change here is ready to build, validate, commit or publish, when opening or returning to its pull request, or when deciding what a change still owes; not for how a review reaches its findings, and not for what a change is for.
---

# landing

**Purpose:** carry this repository's own landing procedure, so a session taking a change from a branch to a pull request does the steps in the order that works here. **Audience:** any session in this repository with a change ready to validate, commit or publish. **Success:** a session that has read this leaves a branch, a commit and a pull request that the guards and the owner's merge-time read all accept, without having been told the order.

## Where this cell's depth lives

- **Deciding where the flow starts for the change in hand — whether it is mechanical work, or a change whose delivery is the truth of some text** → `references/where-the-flow-starts.md`: the mechanical exemption and whose list it is, the two neighbouring lists it is not, and the slice of build that precedes the artifact on a truth-of-text change.
- **Writing a pull request body here, checking a draft of one before anything is opened, or returning to one already open** → `references/the-pull-request-body.md`: the waiting-on-you line and what its green check does not say, the closing references and the spelling GitHub parses, and everything a change fixing a cause disposes of on the way out, closing on the plugin version a shipped-zone change bumps.

## The flow

Branch first (`main` refuses direct pushes) → settle the brief, then the artifact as the `engagement` cell settles it, a truth-of-text change drafting its replacement text first → build → `python tools/lint.py` and `python tools/check_version_bump.py` → commit → append the settling row the `records` cell owns, where the change owed a brief → publish the branch, open the PR, run the experience session the change bought or record the one line declining it — owed equally where the change concluded it bought none, unless it was purely mechanical — run the review, reconcile external reviewer comments — in that order, without being asked; on a change that has a PR, running the review is a check, never a question. A batch rewriting what the material instructs, or changing what someone using the result can do, buys one more, or the line declining it. [D-178] [D-295]

**The stretch from the pull request through the review is run by the session that opened it.** Nothing routes a pull request to another one — the pool raises issues, and the ask mark, which a pull request may carry, routes to the owner and never to a session — so a stretch handed on at the pull request is handed to nobody: [PR #451](https://github.com/Grimblaz-and-Friends/tradecraft/pull/451) deferred both its experience session and its review to a fresh session in its own body, and merged unreviewed the same day it opened, `2026-09-07T02:55:57Z` to `2026-09-07T20:18:50Z`. [D-496]

**Not every change starts that chain at its first step**, mechanical work having no brief and no artifact to settle, and a change delivering the truth of some text taking a slice of build before the artifact. Which work is which, and why each is stated here at all: `references/where-the-flow-starts.md`.

## What the pull request owes

**The body carries a line declaring which marked asks this change is waiting on, and a closing reference for every issue its fix discharged.** What each of those must say, the check CI runs over the first and what a green one is not evidence of, and everything a change fixing a cause disposes of on the way out: `references/the-pull-request-body.md`.

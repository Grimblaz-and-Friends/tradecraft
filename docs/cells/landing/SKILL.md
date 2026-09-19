---
name: landing
description: This repository's own procedure for taking a change from a fresh branch to an open pull request — the order the steps run in, the guards that must pass before a commit, and what the pull request body states. Use when a change here is ready to build, validate, commit or publish, when opening or returning to its pull request, or when deciding what a change still owes; not for how a review reaches its findings, and not for what a change is for.
---

# landing

**Purpose:** carry this repository's own landing procedure, so a session taking a change from a branch to a pull request does the steps in the order that works here. **Audience:** any session in this repository with a change ready to validate, commit or publish. **Success:** a session that has read this leaves a branch, a commit and a pull request that the guards and the owner's merge-time read all accept, without having been told the order.

## Where this cell's depth lives

- **Your change may be mechanical, or may deliver the truth of some text, and you want to know what that changes about the order above** → `references/where-the-flow-starts.md`: which step each skips and which it never skips, whose list decides *mechanical* and the two neighbouring lists it is not, and the slice of build that precedes the artifact on a truth-of-text change.
- **Anything owed at or after the commit — what the pull request body must say, or what is left before this change can merge** → `references/the-pull-request-body.md`: the waiting-on-you line and what its green check does not say, the closing reference or the line saying it closes none, the spelling GitHub parses, and everything a change fixing a cause disposes of on the way out.

## The flow

Branch first (`main` refuses direct pushes) → settle the implementation brief, then the artifact as the `engagement` cell settles it, a truth-of-text change drafting its replacement text first → build → run the floor — `python -m pytest tools/tests skills lib/tests -q` and `python tools/lint.py` → commit → publish the branch and **open the pull request as a draft** → run the experience session the change bought or record the one line declining it — owed equally where the change concluded it bought none, and by mechanical work too → **mark ready and apply `reviewers`** → dispose every connected reviewer's comment in its thread. A panel runs only where the implementation brief's review-risk line bought one, because review depth cannot depend on a later memory. A batch rewriting what the material instructs, or changing what someone using the result can do, buys one more experience session, or the line declining it.

**On a change with an affirmed implementation brief, the `engagement` cell's holder publishes the implementer's commits, opens the pull request, and carries it through use, the connected reviewers, any bought panel, and reporting.** Opening it transfers no responsibility. **On a change owing no implementation brief, the session that opens the pull request still runs its remaining stretch.** Nothing routes a pull request to another session, because no recipient receives such a handoff.

**Not every change starts that chain at the implementation brief**, mechanical work having none to settle and no artifact either, and a change delivering the truth of some text taking a slice of build before the artifact. Which work is which — the `charter` cell's convergence rule, loaded in every session already — and why each is stated at all: `references/where-the-flow-starts.md`.

# D-81: The doctrine callout is CI, not CODEOWNERS

**Status:** Accepted 2026-08-19 (PR #81)

## Context

The owner's standing requirement, stated at the reset's convergence, is a call-out at merge time whenever `AGENTS.md` changes, so he specifically reads that diff. [D-74](D-74-2026-08-19-constitutional-reset.md) named `.github/CODEOWNERS` as the mechanism, "as a platform mechanism rather than a prose rule" — the admission order's cheapest tier, and the right instinct. CODEOWNERS fires by auto-requesting a review, and GitHub never requests a review from a pull request's own author. Sessions in this repo run as the owner's account, so every PR is authored by the only human who merges, and the callout could not reach him: #74, #77 and #78 all touch `AGENTS.md` and all return `reviewRequests: []`. The only surviving trace was the passive shield icon in Files-changed, which is not a callout. Two live sentences — the doctrine's Release line and CODEOWNERS' own comment — described a flag that had never once fired. Discovered 2026-08-19 when the owner looked for #78's callout and found nothing; filed as [#79](https://github.com/Grimblaz-and-Friends/tradecraft/issues/79).

## Decision

The callout is a CI step (`tools/doctrine_callout.py`, a `ci.yml` job on pull-request events), not CODEOWNERS. When a PR's diff touches `AGENTS.md` or `CLAUDE.md` it applies the `doctrine` label and posts one comment — the PR header and the notification stream, which are the surfaces the owner is actually reading at merge time. Idempotence is by an HTML marker in the comment body rather than a stored id, so it survives re-runs and lost workflow runs. A PR that stops touching doctrine has the label removed and the comment withdrawn; re-earning the change reinstates it, because a callout that outlives its reason is the same defect as one that never fires.

**Every failure is loud.** Unreadable paths, a rejected label call, a rejected comment call — each exits non-zero and turns the check red. This is the version-bump guard's lesson applied to a second mechanism: its withdrawn predecessor failed open four ways while printing a clean pass, and the whole content of this incident is that a callout can look installed while doing nothing.

`CODEOWNERS` stays, its comment corrected to say what it delivers: the shield icon, and a real review request the day a non-owner contributor opens a PR. It is a mechanism that works for everyone except today's sole author.

## Rejected

- **Deleting `CODEOWNERS`** as dead weight: it is not dead, only inapplicable to a single-author repo, and it would have to be rebuilt for the first outside contributor.
- **A blocking check.** The callout labels and speaks; it does not gate the merge. Merging is the owner's, and a gate no agent can satisfy is only re-run noise.
- **A doctrine line telling sessions to flag doctrine PRs.** The admission order puts a platform mechanism ahead of prose for exactly this reason: a prose rule fires only when a session reads and obeys it, which is the weaker of the two guarantees, and the doctrine already carries this line at its budget.
- **Widening the file set** to skills or decision entries: a different requirement, with no incident behind it.

## Evidence

[#79](https://github.com/Grimblaz-and-Friends/tradecraft/issues/79) (the incident, its probe, and the affirmed pre-implementation artifact); PR #81, which touches `AGENTS.md` and is therefore its own live positive acceptance test; dry runs against #61 and #59, the two recent PRs touching neither doctrine file, which call out nothing.

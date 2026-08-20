# D-81: The doctrine callout is CI, not CODEOWNERS

**Status:** Accepted 2026-08-19 (PR #81)

## Context

The owner's standing requirement, carried in the affirmed artifact behind the reset ([#73](https://github.com/Grimblaz-and-Friends/tradecraft/issues/73)), is a call-out at merge time whenever `AGENTS.md` changes, so he specifically reads that diff. [D-74](D-74-2026-08-19-constitutional-reset.md) named `.github/CODEOWNERS` as the mechanism, "as a platform mechanism rather than a prose rule" — the admission order's cheapest tier, and the right instinct. CODEOWNERS fires by auto-requesting a review, and GitHub never requests one from a pull request's own author — exactly so for an individual code-owner entry, which is what this repo has; a team entry containing the author is still requested. Sessions here run as the owner's account, so today every PR is authored by the only human who merges, and the callout could not reach him: the issue timelines of #74, #77 and #78 carry no `review_requested` event at all.

**The instrument matters, because the first one was wrong.** This was originally evidenced by `gh pr view --json reviewRequests` returning `[]` on those three PRs, which does not establish the claim: that field reports *pending* requests, so it cannot tell "never requested" from "requested then fulfilled". And #74 could not have produced a request for any reason — it is the PR that *added* `.github/CODEOWNERS`, and CODEOWNERS is read from the base branch, where it did not yet exist. The panel reviewing this change caught both. The timeline is the diagnostic instrument, and on it the conclusion holds.

The only surviving trace was the passive shield icon in Files-changed, which is not a callout. Two live sentences — the doctrine's Release line and CODEOWNERS' own comment — described a flag that had never once fired. Discovered 2026-08-19 when the owner looked for #78's callout and found nothing; filed as [#79](https://github.com/Grimblaz-and-Friends/tradecraft/issues/79).

## Decision

The callout is a CI step (`tools/doctrine_callout.py`, a `ci.yml` job on pull-request events), not CODEOWNERS. When a PR's diff touches `AGENTS.md` or `CLAUDE.md` it applies the `doctrine` label and posts one comment — the PR header and the notification stream, which are the surfaces the owner is actually reading at merge time.

**Identity is the marker plus the author, and the comment is idempotent by content.** The callout is found by an HTML marker in the body rather than a stored id, so it survives re-runs and lost workflow runs — but a marker alone is not identity. The repository is public, so any account can post a comment containing that string, and the review of this change showed the accidental path is the likely one: this repo posts review reports as PR comments, and a report about this mechanism quotes the marker. Without an author check, such a comment suppresses the callout entirely (exit 0, green check) and the edit path overwrites its body. So a marker-bearing comment from anyone but the workflow account is neither treated as the callout nor ever edited, and the run says whose it was. **The degradation is deliberately toward speaking**: this mechanism exists because a callout did not fire, so a duplicate is noise while a missing one is the bug.

Given ownership, one rule covers the comment: render what the PR deserves now, and make the thread say that. Posting, withdrawing when the doctrine change is dropped, reinstating when it returns, and refreshing a `Touched:` list that a later push made stale are the same operation at four moments — a callout that outlives its reason is the same defect as one that never fires.

**Every failure is loud.** Unreadable paths, an empty change set, a rejected label call, a rejected comment call — each exits non-zero, turns the check red, and emits a workflow error annotation. This is the version-bump guard's lesson applied to a second mechanism: its withdrawn predecessor failed open four ways while printing a clean pass, and the whole content of this incident is that a callout can look installed while doing nothing.

**But loud-on-failure and pinned-when-present are different guarantees**, and the script can only carry the first: a PR that deletes the job touches no doctrine file, so nothing fires and nothing goes red — the mechanism would disappear exactly as silently as the one it replaces. `tools/lint.py` carries the second, asserting that the job is declared and runs the script. It lives there because the lint is a required status check, which the callout deliberately is not.

`CODEOWNERS` stays, its comment corrected to say what it delivers: the shield icon, and a review request the day a non-owner contributor opens a PR — one that notifies but blocks nothing, since the ruleset requires no code-owner review. It is a mechanism that works for everyone except today's sole author.

## Rejected

- **Deleting `CODEOWNERS`** as dead weight: it is not dead, only inapplicable to a single-author repo, and it would have to be rebuilt for the first outside contributor.
- **A blocking check.** The callout labels and speaks; it does not gate the merge. Merging is the owner's, and a gate no agent can satisfy is only re-run noise.
- **A doctrine line telling sessions to flag doctrine PRs.** The admission order puts a platform mechanism ahead of prose for exactly this reason: a prose rule fires only when a session reads and obeys it, which is the weaker of the two guarantees, and the doctrine already carries this line at its budget.
- **Widening the file set** to skills or decision entries: a different requirement, with no incident behind it.

## Evidence

[#79](https://github.com/Grimblaz-and-Friends/tradecraft/issues/79) (the incident and the affirmed pre-implementation artifact); the issue timelines of #74, #77 and #78, carrying no `review_requested` event; PR #81, which touches `AGENTS.md` and is therefore its own live positive acceptance test, observed labelling, commenting, and declining to comment twice across two runs; dry runs against #59, #61, #72 and #80 — every PR touching neither doctrine file — which call out nothing. The review that landed this change is its own second exhibit: it found the callout suppressible by any comment quoting its marker, and falsified three of this entry's first-draft claims, including the probe corrected above.

# D-141: A write-up's figures are derived by a shipped engine, applied here by a wrapper that imports the guards

**Status:** Accepted 2026-08-23 (PR #141)

## Context

[D-135](D-135-2026-08-23-repointed-reference.md) landed the rule — a frozen document carrying counts carries the query that produced them — and shipped it knowingly without a mechanism. Issue #137 measured what that costs: across PRs #135 and #136, every figure a write-up carried forward or stated from memory was wrong at least once (the governing-prose growth figure three times, from CRLF-vs-LF, filter-vs-raw-blob, and moved-merge-base basis drift; a staffing universal reached an affirmed artifact), and every figure computed at the moment of writing was right. The recurring figures are all derivable in seconds; the failure was that each derivation was re-improvised per change with its basis chosen fresh and usually unstated.

## Decision

**Two pieces, split by generality.** The figure engine — suite count, a document's size against a budget, prose delta against an explicit base, each figure emitted inseparably from its basis and tree — is general to the practice, not to this repository: the failure it fixes is a property of model sessions writing write-ups, and the rule it mechanizes already ships to consumers in `skills/authoring`. So the engine ships in that cell (`skills/authoring/scripts/figures.py`, tests in the cell, the pattern `skills/persist-changes` set), and the repo-specific application stays in `tools/figures.py`.

**The wrapper imports the guards it must agree with.** The budget comes from `tools/lint.py`'s own constant and the decision-log census reuses `check_entry_references`' own extraction and resolution with both recorded sets emptied — D-135's prescribed derivation. Dependencies point the lawful direction, repo-only importing shipped, and the agreement is pinned by test equality against the guards rather than by parallel arithmetic that can drift.

**No basis is ever chosen silently.** The bases are fixed in code and printed with every figure — the doc measure is a universal-newline read because that is what a text-mode budget guard measures; the delta is raw base blobs vs working-tree bytes, decoded UTF-8, CRLF normalized to LF. The one basis that is a caller decision, the delta's base ref, is a required argument, and incomplete inputs are a loud refusal. Silent basis-picking produced three of the wrong numbers in the evidence.

**Discovery rides the skill's trigger, not the doctrine.** `skills/authoring`'s description now fires when a write-up states derived figures, and its carries-the-query rule names the mechanism. `AGENTS.md` is untouched: a shipped trigger reaches every consumer and costs none of the doctrine's remaining budget.

## Rejected

- **Repo-only in `tools/`, the first draft's shape.** Assessed on "no consumers exist yet", which the owner rejected at convergence: consumers are the point of the plugin, and judging generality by the current consumer count would keep every general mechanism repo-bound forever. Judged on the merits, the engine is practice-general and the census alone is guard-bound.
- **A CI gate verifying a PR body's stated figures reproduce.** Owner decided no at convergence: it would fail write-ups on rewording, and the script changes the economics enough that the class should be watched with the mechanism available before buying a gate.
- **Folding guard migration into this change.** Moving the guards themselves (doctrine budget, entry references, the rest of the lint) into the shipped zone so consumers get mechanical enforcement was raised at convergence and deliberately bounded out — it is its own convergence with its own boundary questions, and it would swallow a small script inside a large restructuring.
- **A doctrine pointer.** Naming the script in the flow line would spend part of `AGENTS.md`'s last 20 characters of headroom and reach only this repo's sessions; the trigger extension reaches every consumer for free.
- **Figures beyond the recurring set.** The issue's table is evidence from two changes, not a specification; a figure is added when it demonstrably recurs.

## Evidence

The affirmed artifact and affirmation record are on [#137](https://github.com/Grimblaz-and-Friends/tradecraft/issues/137#issuecomment-5389922457), with the owner's two decisions at the gate recorded in the [affirmation](https://github.com/Grimblaz-and-Friends/tradecraft/issues/137#issuecomment-5389923285). The PR body's own verification figures were emitted by the script it lands — including the census disagreeing with D-135's frozen table by one, which is the class under repair, left unreconciled because records are exhaust.

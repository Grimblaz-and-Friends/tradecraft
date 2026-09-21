# D-691 — Steward and cross-session intake

**Landed by** [PR #691](https://github.com/Grimblaz-and-Friends/tradecraft/pull/691). Closes [#684](https://github.com/Grimblaz-and-Friends/tradecraft/issues/684). Governed by the [affirmed implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/684#issuecomment-5764217706), the [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/684#issuecomment-5764572118), its [`would` verdict](https://github.com/Grimblaz-and-Friends/tradecraft/issues/684#issuecomment-5764691940), and the [holder's whole-change reading](https://github.com/Grimblaz-and-Friends/tradecraft/issues/684#issuecomment-5764728913). The implementation content before this entry is `97d332f1ac26571de3bfc61a9138d6301a8e84d2`; its base is `760eb072acac2b8d43eb364d7e97da527f03aa29`.

## Context

The lab had named one long-lived coordinating role, but the role, its intake and its replacement state lived only in a session and a live page. That let the coordinating session hold changes beside their holder sessions and left an adopter with no shipped instruction for sending evidence across sessions. The owner chose the split recorded on #684: the reusable intake ships, while the Steward remains this repository's own application of it.

## Decision

### The intake ships; the Steward stays local

`skills/engagement/references/cross-session-intake.md` carries the portable rule: where repository doctrine names a long-lived coordinating session and the runtime can reach it, a session sends evidence and a pointer, files what it can itself, and the receiver verifies the message against the record before acting. `skills/engagement/SKILL.md` routes that trigger to the reference. Keeping it in engagement depth makes the rule available to adopters without charging every engagement firing for prose used only by cross-session intake; putting it in the engagement body was rejected for that cost, while a new shipped cell was rejected because intake has no independent actor or job outside engagement.

The local role lives in `docs/cells/steward/SKILL.md`, with one binding sentence in `AGENTS.md`. The sentence makes every session distinguish the lab's coordinator from a change holder before starting work; the cell carries the role's duties on demand. This is the holder's correction to the artifact's proposed whole section in `AGENTS.md`: keeping the whole role always-on would charge every repository session for local depth, while omitting the sentence would leave the cell unrouted at the moment the distinction matters.

At the provisional implementation named above, the shipped intake names no Steward, lab, repository or product, and shipped material does not depend on the repo-only cell. The standard therefore travels without exporting this repository's operating model.

### One page carries the lab, and a replacement starts from durable state

`docs/cells/steward/SKILL.md` designates [#683](https://github.com/Grimblaz-and-Friends/tradecraft/issues/683) as both the Steward's standing page and the standing issue that `skills/engagement/references/change-paths.md` already provides for read notes. The same object carries the read watermark, rulings waiting on the owner, changes ready for pickup, work in flight with its holders and residues. A second standing issue was rejected because it would separate the read's notes from the state they describe.

A replacement reads #683, the Steward's memory store and the open issues. The memory store is an inbox for retained judgment rather than the lab's archive; #683 and the open issues carry the load-bearing state. This reconciliation with `docs/cells/siting/SKILL.md` is the second holder correction to the artifact: memory may affect the reader's future judgment, but nothing the role needs may live only in a session.

### Reader supersedes holder only as the read's actor

This decision supersedes [D-679] only on who performs the cross-change read. In `skills/engagement/references/change-paths.md`, the reader is whichever session repository doctrine assigns, need not hold a change, and falls back to the change's holder when doctrine assigns nobody. D-679's cadence, repository set, evidence method, note and exits remain unchanged.

The word *holder* remains where it still means the session holding an individual change: that session records the change's path-departure paragraph, and the paragraph supplies that holder's unmarked calls. It no longer implies that the same session must perform the cross-change read.

D-679 remains frozen. Its affirmed row 1 instead received the owner-reagreed actor clause as an [append-only amendment on #677](https://github.com/Grimblaz-and-Friends/tradecraft/issues/677#issuecomment-5764872302), preserving the original record while making the supersession visible where that row was settled.

### The shipped version advances and the changed behavior buys use

`.claude-plugin/plugin.json` advances to `0.145.0` because the intake reference and cross-change actor ship to adopters. The changed `skills/**` paths match the existing runtime-or-user-surface rule in `lib/use-rules.json`, so PR #691 also owes a fresh experience session before release.

## Cost and rejected alternatives

The change adds one shipped engagement reference, one repo-only cell and one always-on sentence. That cost keeps the reusable standard with the practice and the local application out of an adopter's doctrine. Also rejected were shipping the Steward itself, putting the whole role in root doctrine, creating a second standing page, treating memory as an archive, adding a message mechanism, and changing the read's cadence or evidence method.

## Evidence

The final implementation surface is re-derived with `git diff --name-only 760eb072acac2b8d43eb364d7e97da527f03aa29 <pull-request-head>` and its content with `git diff 760eb072acac2b8d43eb364d7e97da527f03aa29 <pull-request-head>`. The structural floor is `git diff --check`, `python tools/lint.py`, and `python -m pytest tools/tests skills lib/tests -q -n auto --dist loadfile` on that head. The pull request body carries the final-head floor and fresh-consumer experience evidence; this entry cannot name that head because adding the entry and its index row produces it.

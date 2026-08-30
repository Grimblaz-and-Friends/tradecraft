# D-253: Operative guidance lands on its reader's surface — the zone wall's second direction, the fourth `docs/` kind, the budget as a trigger, and the strip that has one owner

**Status:** Accepted 2026-08-30 (PR #253)

## Context

[#237](https://github.com/Grimblaz-and-Friends/tradecraft/issues/237), [#245](https://github.com/Grimblaz-and-Friends/tradecraft/issues/245) and [#190](https://github.com/Grimblaz-and-Friends/tradecraft/issues/190) are filed as one class: a rule this repository holds, written only where its reader never goes — a code comment, a lint constant's comment, a sibling docstring and a test name. [#228](https://github.com/Grimblaz-and-Friends/tradecraft/issues/228) is the fourth kind of the same failure, a rule written nowhere at all. They landed together on the settled [pre-implementation artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/237#issuecomment-5469358844), [affirmed](https://github.com/Grimblaz-and-Friends/tradecraft/issues/237#issuecomment-5469359438) with the owner ruling its one open item.

**Why one change.** They pair onto two budgeted surfaces — `AGENTS.md` for #237 and #228, the `authoring` cell body for #245 and #190. Split across pull requests, the second `AGENTS.md` edit rebases onto a file whose headroom the first consumed and pays a second outflow for the same surface. The batching is about the shared scarcity, not about the shared class.

## 1. The zone wall's second direction goes in the doctrine, not in a cell

`AGENTS.md` stated the wall one way — shipped never references repo-only — which is correct and silent about the reverse. The permission lived in comments in `tools/check_version_bump.py` and `tools/roster.py`.

**The doctrine is where it goes, because that is where the rule is.** The alternative the filing left open was the `substrate` cell, which costs no always-on characters and already tells a session how to resolve `lib/` against its own file. It was rejected: a cell is shipped, so it may not name `docs/`, `tools/` or `.github/` at all, and the zone shape those names define is this repository's rather than the practice's. A cell could only have stated a general principle about a wall it is forbidden to describe, while the rule a session actually misreads stayed one-directional where it is written.

**The evidence is two consumers, not a reading.** PR #232's two cold experience sessions, different jobs, both stalled and both resolved it by opening a neighbouring script. Both got it right; the route is what does not generalise, and a session resolving it the other way hand-rolls rather than importing `lib/winio.py` — the duplication [D-186] created `lib/` to end — with nothing failing, because the lint's zone wall checks the banned direction exactly.

**No guard is available for the lawful direction.** Nothing can check that a repo-only script which *needed* `lib/` reached for it, and the filing said so. This is prose because the mechanism tier is empty here, not because prose was preferred over a mechanism.

## 2. Both `AGENTS.md` additions landed, funded by two outflow moves

The draft artifact carried this as its one open item: the file's remaining headroom did not obviously fund two additions, and the fallback was landing #237 and leaving #228 on the board with its "next edit with headroom" trigger intact. **The owner ruled: land both, with a second outflow.**

The two moves, both from `skills/authoring/references/routing.md`:

- **The calling-contract bullet keeps the rule and its guards' names; its reason compresses to `[D-156]`.** Which mechanism enforces which part of it is the guards' to hold, not the always-on surface's. This is moves 1 and 3 together.
- **The version-bump unit moves to the guard that computes it.** `check_version_bump.py` derives the unit — the PR against its merge base — and the flow line already names that command two clauses earlier. Move 1.

**Three prior attempts on this file were unavailable and were not retried.** [D-225] records them: one compression accepted, the CRLF clause **refused** because D-186 §5 records that placement as deliberate — the fact has to be found mid-task, when a session notices CRLF and has no reason to open the decision log — and the flow's fix-batch clause removed as a move and **reversed under review**, because [D-178] bought the two-surface arrangement with its own experience session and a Codex session loads no cell description at all [D-210]. A session looking for headroom in this file should read D-225 before proposing any of the three again.

**Neither addition was shaved to fit.** #237 exists because a rule was too terse; buying its remedy with terseness would have reproduced the defect it fixes. Where the arithmetic pressed, the answer was a second outflow.

## 3. The budget ceiling is a trigger, and the sentence has one owner

The owner observed the pattern repeating across sessions: a session seeing a budgeted file becomes reluctant to edit it, which inverts the budget's design — a tight surface is meant to *trigger* restructuring. The operative sentence already existed, in `tools/lint.py`'s budget-constant comment, a repo-only file no session editing a skill opens.

**It is hoisted to the `authoring` cell's Routing section, and the lint comment now points at it.** Two half-owners of one sentence kept in agreement by hand is what that cell forbids, so the comment carries no second copy. The direction of that pointer is the lawful one this same change wrote down in §1.

**Note what this change is itself evidence for.** It brought both `AGENTS.md` and the `authoring` cell body to a headroom neither had at its merge base, by moving three rules to homes that already held them rather than by declining the edits. That is the sentence being applied in the change that states it.

## 4. The cell-body strip has one owner, and a guard now says so

The rule — anything measuring a cell body uses the strip the shipped engine provides — was real, pinned by `test_the_body_strip_the_engine_ships_is_the_one_the_guard_applies`, and written down only in `tools/figures.py`'s docstring and that test's name. It was defended against the two implementations that already existed, and against a third by nothing.

**A third was already in the tree.** `tools/check_codex_compat.py` used `text.split("---", 2)[2]`, which keeps the two newlines the engine strips. Harmless where it was used — the result is only split into paragraphs — and green on both the lint and the suite, which is the filing's prediction found already true rather than forecast. It is converted to the engine, and a test measures the two-character difference rather than asserting it.

**A guard, not prose alone, because the admission order puts the mechanism tier first** and the filing had already said the near-miss would have been caught by one where prose would only have been caught if read. `check_body_strip_owner` is the mechanism; one line in the cell names the rule for the reader the guard cannot reach.

Four design calls, made by the session and recorded here:

- **Exemptions are `(path, function)` pairs, not files.** Recorded by file, a module holding a sanctioned implementation would license every strip written under it afterwards — and that is the module most likely to attract one. The suite pins that the set only shrinks, the same guarantee `check_entry_references`' recorded sets carry.
- **`tools/lint.py` keeps its own strip, recorded rather than removed.** A guard that imported from the tree it audits could not report on a tree whose authoring cell is broken or absent, which is the tree this check is most needed on. `_frontmatter_fields` is recorded beside it because it reads the fields *inside* the frontmatter, and the predicate cannot tell that apart from reading the body below it.
- **Test files are out of scope, stated rather than widened away.** They build frontmatter fixtures rather than strip one to measure. Scanned, eleven test functions match the shape and none is an instance; that ratio is why the exclusion was worth stating as the check's one blind spot rather than closing.
- **The predicate requires the marker and the slice to be connected.** The first form asked only whether a function held a marker constant and a subscript anywhere in it, and reddened the very script the change had just converted — a guard firing on the compliant form teaches the reverse of its rule. `test_a_function_that_only_mentions_a_marker_is_left_alone` holds it there.

## 5. What was left open

- **The `authoring` cell's description does not trigger for a session writing a tool that measures a cell body**, which is #190's actual consumer. Its headroom would not carry a new trigger without a trade, and [#188](https://github.com/Grimblaz-and-Friends/tradecraft/issues/188) settled that description deliberately. The guard reaches that consumer whether or not the cell fires, which is why the guard is the primary remedy here and the prose the secondary one. Named rather than closed.
- **The class is not widened** beyond the body strip to every measurement a guard also performs. The body strip is the instance that was observed.
- **[#241](https://github.com/Grimblaz-and-Friends/tradecraft/issues/241) stays on the board.** Same class, different subject — the stdio rule's undocumented import binding — and nothing here reaches it.
- **No budget constant moved.** The surfaces were made to fit; the ceilings were not raised.

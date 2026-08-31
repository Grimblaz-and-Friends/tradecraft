# D-270: The version guard's bound is the base ref's tip as well as its merge base, and the manifest's exemption is a field rather than a file

**Status:** Accepted 2026-08-30 (PR #270)

## Context

`tools/check_version_bump.py` is the guard `AGENTS.md`'s flow tells every session to run before it commits. Three defects in it were on the board, all reachable only from the same file, and this change takes them together.

**The bound was the merge base alone.** The guard re-derived `merge-base(HEAD, <base ref>)` and compared the plugin version against that revision, which answers *did this branch raise the version it started from* — a question about the branch's history, not about the version. A branch cut before a sibling landed therefore bumped onto a number `main` already carried and reported a clean pass. [#110](https://github.com/Grimblaz-and-Friends/tradecraft/issues/110) records **six** instances, and they are not all one shape — a distinction the first draft of this entry did not make, and which its review supplied:

| # | Instance | State of the base when it was recorded |
| --- | --- | --- |
| 1 | [#107](https://github.com/Grimblaz-and-Friends/tradecraft/pull/107) | `main` had moved and taken `0.22.0` |
| 2 | [#113](https://github.com/Grimblaz-and-Friends/tradecraft/pull/113)/[#114](https://github.com/Grimblaz-and-Friends/tradecraft/pull/114) | **`main` unmoved** — both open, both at `0.24.0` |
| 3 | [#119](https://github.com/Grimblaz-and-Friends/tradecraft/pull/119) | `main` had moved and taken `0.25.0` |
| 4 | the `0.29.0` collision routed from [#122](https://github.com/Grimblaz-and-Friends/tradecraft/issues/122) | `main` had moved and taken `0.29.0` |
| 5 | [#155](https://github.com/Grimblaz-and-Friends/tradecraft/pull/155) | **`main` unmoved** — four concurrent PRs off `3175369` |
| 6 | [#262](https://github.com/Grimblaz-and-Friends/tradecraft/pull/262) | `main` had moved and taken `0.56.0` |

**Four of the six are the moved-tip shape this bound closes** at the moment the version is picked. The other two are concurrent open pull requests off a base that has not moved, which no bound reading only `HEAD` and the base ref can see; this bound reaches them once the sibling lands, which is earlier than the merge button where their own records say the cost was paid, but later than the rest. That residue is [#279](https://github.com/Grimblaz-and-Friends/tradecraft/issues/279).

**Nor was each caught at the merge button**: #107's was caught by a defense mid-review, #113's by a round-one `wiring-falsifier` seat, #262's while resolving merge conflicts. Only #119's was literally at the button, after its final report had been posted.

[#206](https://github.com/Grimblaz-and-Friends/tradecraft/issues/206) is the same want filed independently from PR #193's post-fix ruling, with a further incident; it closed before this change and its proposed shape is what landed here.

**#262's instance is the one that shaped the remedy.** Its shape is not a branch that never merges `main` in; it is the *conflict-resolution window* of a merge that does. Both sides made the identical edit to the version line, git auto-merged it silently with no conflict marker, and the guard passed on a number `main` already carried — then self-healed once the merge was committed and the merge base advanced, so the guard went red only after the session had stopped asking. That the guard is green exactly while the version is being decided is what rules out a remedy keyed to merge time.

**The manifest was exempt as a file.** `.claude-plugin/plugin.json` was dropped from the shipped-touched set wholesale. The reason for the exemption is real and narrow — `version` lives there, so counting the manifest would make every bump its own justification — but the file also carries `name` and `description`, which are consumer-facing copy. The circularity argument reaches one key and was spending the whole file. [#20](https://github.com/Grimblaz-and-Friends/tradecraft/issues/20), where the judge on PR #9 left it to the owner as *"a real design question with no incident record"* and it was ruled a defect in an existing guard rather than a new rule.

**The comparison's int cast was unpinned.** `0.9.0 -> 0.10.0`, landed by PR #30, was this repository's first decade-crossing bump. Every bump fixture used `1.0.0 -> 1.1.0` and the decrement fixture used `1.0.0 -> 0.9.0`; all of them survive a lexical comparison unchanged, so no test distinguished `tuple(int(p) for p in parts)` from `tuple(parts)`. [#33](https://github.com/Grimblaz-and-Friends/tradecraft/issues/33).

## Decision

**The new version must exceed the version at two revisions: the merge base and the base ref's tip.** `_resolve_base` returns the tip alongside the merge base and the ref's own name, so the ref a caller names is honoured in both readings of it rather than silently re-derived back to the fork point — which is what PR #107's defense probed when it passed `--base 4938f77` and still got a pass.

**Three failure sentences, not one, because they are different faults.** A version that did not rise keeps the existing message. A version that rose but not past the tip gets its own, naming the tip, what it carries, and the merge base that predates it, and telling the session to bring the base in and raise again — and that message splits once more, because *equal to* the tip is a collision a consumer could not disambiguate while *below* it is not a collision at all. Saying `ALREADY CARRIES 1.1.0` of a tip at `1.2.0` handed the reader who verifies — the behaviour the experience session documented — a claim they falsify in one look.

**The PASS discloses what it read, and the freshness note goes where fetching is the act.** The guard does not fetch, so a stale remote-tracking ref yields a stale tip and a confident exit 0 on the very collision this change exists for — and in that state `tip == base`, so the moved-tip clause is suppressed and the false PASS is textually identical to a true one. The first draft put the freshness disclosure on the *failing* line, which is the path taken when the ref was fresh enough to catch the collision; a session cannot act on a warning printed only when the warning was unnecessary. Every PASS that consulted the second bound now names the revision it read, and a **remote-tracking** ref carries the freshness note. A local branch and a raw sha do not: neither goes stale from not fetching, and a clause that is a no-op on two of three paths teaches a reader to skip it on the third. Fetching itself stays out — it makes an offline run fail and a fast run slow — and the residue is [#279](https://github.com/Grimblaz-and-Friends/tradecraft/issues/279).

**The exemption narrows from the file to the field.** The manifest counts as a shipped-zone change when its parsed contents *excluding* `version` differ from the base's. A bump alone still does not, so the circularity stays prevented. The comparison runs only when the manifest is in the change set, so the common untouched case adds no git calls. That is a claim about the comparison and not about the guard's answer: a manifest-untouched run whose base ref's tip carries an unreadable manifest does now return UNDETERMINED where it previously returned PASS or FAIL, which is the tip read rather than this one and is pinned by `test_an_unreadable_base_tip_version_is_undetermined`.

**A manifest edit the guard cannot read on the *current* side is UNDETERMINED, and only that side.** This widens exit 2 to one case that passed before — a broken manifest as the only change, shipped zone otherwise clean — which is what the affirmed artifact disclosed and what the session decided and reported rather than asking. It follows the script's own doctrine, *"anything this script cannot establish, it says out loud and exits non-zero"*.

The first draft read **both** sides unconditionally, which widened exit 2 much further than that and in a direction nobody affirmed. The commonest instance of an unreadable *base* manifest is a manifest that is simply new: an adopting repository's first pull request, where the base will never grow the file and **no act on the branch can clear the red** — a hard failure with no named remedy on the one pull request every adopting session must ship, in a guard whose stated audience includes them. Nothing to compare against is not a question the guard failed to answer, so the base side is gated out. That regression was the only behavioural defect this change introduced, and it was found by the review rather than by the change.

**The int cast is pinned in both directions**, and carries a docstring saying what it is load-bearing for. A decade-crossing bump is a bump; a decade-crossing decrement is still a decrement. The same mutant fails one closed and the other open, which is why one test is not enough.

**And the gate in front of that cast had to agree with it.** `isdigit` accepts characters `int()` refuses — the superscript two among them — so a manifest could pass the gate and kill the guard with an uncaught `ValueError` whose process exit code **1** reads as FAIL, the wrong one of three outcomes. `isdecimal` is the predicate that matches the cast. The same class sat one function away: `_manifest_at` called `read_text` unguarded, so a manifest that is not UTF-8, or that cannot be read at all, escaped as a traceback rather than the UNDETERMINED the script promises. Three independent findings of one class — this review's `operational` seat at the semver gate, and both external reviewers at the read — closed together.

## What was rejected

**CI rather than the script.** [#110](https://github.com/Grimblaz-and-Friends/tradecraft/issues/110) raised it, and the case for it is real: `ci.yml` already passes `--base origin/$BASE_REF`, and the collision is about staleness relative to the remote at merge time. Rejected because every recorded instance is about the *local* run being green at the moment the session picks the version. #262's is explicit — the guard is green while the decision is being made and red only afterwards — and #119's records the collision surviving lint, the guard, CI and a five-seat review, surfacing only when GitHub reported `mergeable=CONFLICTING` after the final report was posted. A CI-only remedy cannot reach the moment where the cost is paid. Putting it in the script gives CI the same fix through the entry point it already calls.

**A flag to opt out of the second bound.** Nothing named a case that wants one bound, and a guard with a mode that weakens it is a guard whose failures have a documented workaround.

**Leaving #33 to the guard.** Rejected in the issue as already-occupied: the guard exists and is right; what was missing is the coverage that keeps it right, and a guard cannot be its own coverage.

## Evidence

Both polarities probed for every pin, by mutating `tools/check_version_bump.py` in place and running `tools/tests/test_check_version_bump.py` against each mutant. **Fourteen mutants and two controls, re-derived on the tree this entry lands in** — the first draft's table was measured before a fix that changed one of its rows and never re-derived, which its own review caught and which is the reason the procedure is written out above rather than left as "the four mutants".

| Mutant | Tests that go red |
| --- | --- |
| *control:* unmutated | none — `54 passed` |
| *control:* `check()` returns PASS immediately | 48 — the harness reaches the code |
| the tip bound removed (`new > old` alone) | 5 |
| the tip read removed entirely | 8 |
| the wholesale manifest exemption restored | 7 |
| `_parse_semver` returns `tuple(parts)` | 2 — both decade pins |
| the `isdigit` gate restored in front of the `int` cast | 1 |
| `read_text` left unguarded in `_manifest_at` | 1 |
| the `isinstance(data, dict)` check dropped | 1 |
| the base-side readability gate dropped | 1 |
| the freshness note never printed | 2 |
| the freshness note always printed | 3 |
| the unit sentence printed unconditionally | 1 |
| the collision sentence printed unconditionally | 1 |
| `_shown_ref` never abbreviating | 1 |
| the "shipped zone untouched" wording restored | 1 |

No mutant survived. The two controls are what make the rest of the column mean anything: an unmutated run reds nothing, and a guard that returns PASS unconditionally reds 48 of 54 — so the harness demonstrably reaches the code, which a green column alone could not establish. Every run clears every `__pycache__` and invokes `python -B ... -p no:cacheprovider`; without that a size-preserving mutation can report a false SURVIVES, which is [#142](https://github.com/Grimblaz-and-Friends/tradecraft/issues/142) and which this repository has already published once.

**A defect the mutants found that no reader had.** An early form of the base-side gate reddened 23 tests with a `KeyError` rather than a behaviour change: the field comparison reached its base manifest out of the read-memo, which only the gate's own call had populated. The outcome was correct and the coupling invisible, so a later edit to that gate would have produced a crash rather than a wrong answer. The value is now bound where it is read.

**One pin does not discriminate and says so.** `test_a_branch_level_with_its_base_is_unaffected` asserts that the tip clause is absent when the base has not moved, which the pre-fix guard also produced, having no tip clause to print. It is a regression pin on the quiet case, disclosed in its own docstring on the standard `test_unreadable_base_version_is_undetermined` already set in that file. `test_a_description_edit_with_a_bump_passes` had the same weakness and was strengthened instead: a bare PASS is what the pre-fix guard returned too — by calling the zone untouched, which is the defect — so it asserts the manifest is named.

Every figure outside the table above is re-derivable at the tree this entry lands in by `python -m pytest tools/tests skills -q`, `python tools/lint.py` and `python tools/check_version_bump.py`. **The table is not**, and saying otherwise was the defect that let its one wrong cell stand: each row requires editing `tools/check_version_bump.py` in place and re-running `tools/tests/test_check_version_bump.py`, with every `__pycache__` cleared and `python -B` — without which a size-preserving mutation can report a false SURVIVES ([#142](https://github.com/Grimblaz-and-Friends/tradecraft/issues/142)). The census above is re-derivable by `gh issue view 110 --comments`. The affirmed pre-implementation artifact is [issue #110's comment 5472397011](https://github.com/Grimblaz-and-Friends/tradecraft/issues/110#issuecomment-5472397011), with the affirmation naming it in [the comment beneath](https://github.com/Grimblaz-and-Friends/tradecraft/issues/110#issuecomment-5472397901). The change touches no shipped-zone file and takes no version bump.

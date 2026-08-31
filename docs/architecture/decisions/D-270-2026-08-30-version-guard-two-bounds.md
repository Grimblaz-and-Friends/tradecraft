# D-270: The version guard's bound is the base ref's tip as well as its merge base, and the manifest's exemption is a field rather than a file

**Status:** Accepted 2026-08-30 (PR #270)

## Context

`tools/check_version_bump.py` is the guard `AGENTS.md`'s flow tells every session to run before it commits. Three defects in it were on the board, all reachable only from the same file, and this change takes them together.

**The bound was the merge base alone.** The guard re-derived `merge-base(HEAD, <base ref>)` and compared the plugin version against that revision, which answers *did this branch raise the version it started from* — a question about the branch's history, not about the version. A branch cut before a sibling landed therefore bumped onto a number `main` already carried and reported a clean pass, and kept reporting it through every commit, every local run, and CI. Five recorded instances, on [#107](https://github.com/Grimblaz-and-Friends/tradecraft/pull/107), [#113](https://github.com/Grimblaz-and-Friends/tradecraft/pull/113), [#119](https://github.com/Grimblaz-and-Friends/tradecraft/pull/119), [#155](https://github.com/Grimblaz-and-Friends/tradecraft/pull/155) and [#262](https://github.com/Grimblaz-and-Friends/tradecraft/pull/262), each caught by hand — three of them only after a full review had been paid for. [#110](https://github.com/Grimblaz-and-Friends/tradecraft/issues/110).

**#262's instance is the one that shaped the remedy.** Its shape is not a branch that never merges `main` in; it is the *conflict-resolution window* of a merge that does. Both sides made the identical edit to the version line, git auto-merged it silently with no conflict marker, and the guard passed on a number `main` already carried — then self-healed once the merge was committed and the merge base advanced, so the guard went red only after the session had stopped asking. That the guard is green exactly while the version is being decided is what rules out a remedy keyed to merge time.

**The manifest was exempt as a file.** `.claude-plugin/plugin.json` was dropped from the shipped-touched set wholesale. The reason for the exemption is real and narrow — `version` lives there, so counting the manifest would make every bump its own justification — but the file also carries `name` and `description`, which are consumer-facing copy. The circularity argument reaches one key and was spending the whole file. [#20](https://github.com/Grimblaz-and-Friends/tradecraft/issues/20), where the judge on PR #9 left it to the owner as *"a real design question with no incident record"* and it was ruled a defect in an existing guard rather than a new rule.

**The comparison's int cast was unpinned.** `0.9.0 -> 0.10.0`, landed by PR #30, was this repository's first decade-crossing bump. Every bump fixture used `1.0.0 -> 1.1.0` and the decrement fixture used `1.0.0 -> 0.9.0`; all of them survive a lexical comparison unchanged, so no test distinguished `tuple(int(p) for p in parts)` from `tuple(parts)`. [#33](https://github.com/Grimblaz-and-Friends/tradecraft/issues/33).

## Decision

**The new version must exceed the version at two revisions: the merge base and the base ref's tip.** `_resolve_base` returns the tip alongside the merge base and the ref's own name, so the ref a caller names is honoured in both readings of it rather than silently re-derived back to the fork point — which is what PR #107's defense probed when it passed `--base 4938f77` and still got a pass.

**Two failures, not one, because they call for different acts.** A version that did not rise keeps the existing message. A version that rose onto one the base ref already carries gets its own, naming the tip, the version it carries, and the merge base that predates it, and telling the session to bring the base in and raise the version again. Both list the files.

**The message discloses its own freshness.** The guard does not fetch, so `origin/main` is only as fresh as the session's last fetch, and the failing line says so. Fetching inside a guard the flow runs before every commit is a surface this change declines to add: it makes an offline run fail and a fast run slow, and the disclosure buys the same correction for nothing.

**The exemption narrows from the file to the field.** The manifest counts as a shipped-zone change when its parsed contents *excluding* `version` differ from the base's. A bump alone still does not, so the circularity stays prevented. The comparison runs only when the manifest is in the change set, so the common untouched case adds no git calls and returns exactly what it returned before.

**A manifest edit the guard cannot read is UNDETERMINED.** This widens exit 2 to one case that passed before — a broken manifest as the only change, shipped zone otherwise clean. It follows the script's own stated doctrine, *"anything this script cannot establish, it says out loud and exits non-zero"*, and the alternative is a guard that silently calls the zone untouched because it could not read the file it was asked about. The session decided this and reported it in the affirmed artifact rather than putting it as a question; nothing turned on the owner's answer.

**The int cast is pinned in both directions**, and carries a docstring saying what it is load-bearing for. A decade-crossing bump is a bump; a decade-crossing decrement is still a decrement. The same mutant fails one closed and the other open, which is why one test is not enough.

## What was rejected

**CI rather than the script.** [#110](https://github.com/Grimblaz-and-Friends/tradecraft/issues/110) raised it, and the case for it is real: `ci.yml` already passes `--base origin/$BASE_REF`, and the collision is about staleness relative to the remote at merge time. Rejected because every recorded instance is about the *local* run being green at the moment the session picks the version. #262's is explicit — the guard is green while the decision is being made and red only afterwards — and #119's records the collision surviving lint, the guard, CI and a five-seat review, surfacing only when GitHub reported `mergeable=CONFLICTING` after the final report was posted. A CI-only remedy cannot reach the moment where the cost is paid. Putting it in the script gives CI the same fix through the entry point it already calls.

**A flag to opt out of the second bound.** Nothing named a case that wants one bound, and a guard with a mode that weakens it is a guard whose failures have a documented workaround.

**Leaving #33 to the guard.** Rejected in the issue as already-occupied: the guard exists and is right; what was missing is the coverage that keeps it right, and a guard cannot be its own coverage.

## Evidence

Both polarities probed for every pin, by mutating `tools/check_version_bump.py` in place and running `tools/tests/test_check_version_bump.py` against each mutant. Four mutants, each caught:

| Mutant | Tests that go red |
| --- | --- |
| the tip bound removed (`new > old` alone) | `test_a_version_already_taken_on_the_base_tip_is_refused`, `test_the_taken_version_message_says_what_to_do_next` |
| the tip read removed entirely | the two above, plus `test_a_bump_past_the_moved_tip_still_passes` and `test_an_unreadable_base_tip_version_is_undetermined` |
| the wholesale manifest exemption restored | `test_a_description_edit_alone_is_a_shipped_change`, `test_an_unreadable_manifest_edit_is_undetermined_not_a_pass` |
| `_parse_semver` returns `tuple(parts)` | `test_a_minor_bump_across_a_decade_boundary_is_a_bump`, `test_a_decrement_across_a_decade_boundary_is_not_a_bump` |

**One pin does not discriminate and says so.** `test_a_branch_level_with_its_base_is_unaffected` asserts that the tip clause is absent when the base has not moved, which the pre-fix guard also produced, having no tip clause to print. It is a regression pin on the quiet case, disclosed in its own docstring on the standard `test_unreadable_base_version_is_undetermined` already set in that file. `test_a_description_edit_with_a_bump_passes` had the same weakness and was strengthened instead: a bare PASS is what the pre-fix guard returned too — by calling the zone untouched, which is the defect — so it asserts the manifest is named.

Every figure is re-derivable at the tree this entry lands in by `python -m pytest tools/tests skills -q`, `python tools/lint.py` and `python tools/check_version_bump.py`. The affirmed pre-implementation artifact is [issue #110's comment 5472397011](https://github.com/Grimblaz-and-Friends/tradecraft/issues/110#issuecomment-5472397011), with the affirmation naming it in [the comment beneath](https://github.com/Grimblaz-and-Friends/tradecraft/issues/110#issuecomment-5472397901). The change touches no shipped-zone file and takes no version bump.

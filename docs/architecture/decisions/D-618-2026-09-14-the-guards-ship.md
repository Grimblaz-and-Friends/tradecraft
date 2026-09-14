# D-618 — The guards ship: *to a guard* becomes a destination an adopter reaches, and a rule may not leave prose for a material the reader never receives

**Landed by** [PR #618](https://github.com/Grimblaz-and-Friends/tradecraft/pull/618). Closes [#616](https://github.com/Grimblaz-and-Friends/tradecraft/issues/616). Governed by the implementation brief affirmed on [#616](https://github.com/Grimblaz-and-Friends/tradecraft/issues/616#issuecomment-5663861495) on 2026-09-14; [D-575] landed the principle whose *to a guard* destination this makes real. Evidence pinned at `51fc257` over base `4bafb82` unless stated.

## What was decided

The five checks that hold the `substrate` cell's own standards — `check_emitted_ascii`, `check_stdio_wired`, `check_docstring_not_piped`, `check_subprocess_streams` and `check_harness_tokens` — move out of `tools/lint.py` into `skills/substrate/scripts/lint.py`, which is both the implementation this repository imports and the command a session runs. Their proofs move with them to `skills/substrate/tests/test_substrate_lint.py`. `tools/lint.py` keeps no second copy of any predicate, regex, traversal, finding or message; its one remaining local piece is the population it hands `check_harness_tokens`, which is this repository's own contract roots. That is repo-only code importing shipped code, the lawful direction of the wall, and the same engine-and-wrapper split `skills/authoring/scripts/figures.py` and `tools/figures.py` already use.

`skills/substrate/SKILL.md` names the moment: run the guards before committing Python work the cell governs, by a path resolved against the directory of the file naming it. `skills/authoring/references/routing.md` gains the condition that governs every future routing decision:

> **A rule leaves prose for a guard or a script's own message only where the reader who loses the sentence receives that guard or script** — otherwise the move replaces a rule with silence.

## What this supersedes, and why the earlier reading was reasonable

[D-611] recorded the opposite reading of the same fact, and recorded it deliberately: *"it has two readers and only one of them gets the guards … So `to guard` here means the rule is already what a guard reads and says, and the shipped prose keeps the concept an adopter needs in order to write its own — never a pointer at this repository's."* That was correct about the wall and correct about what was then buildable. It was wrong about what had to stay true: an adopter who cannot receive the guard has not been sent to a guard at all, and for one family of launcher wrappers the surviving concept did not tell that reader what to do. The sweep's own deletion is what surfaced it, and the repository's configured external reviewer raised it on that pull request.

The wall did not need amending and was not amended. What was missing was a shipped home for the executable material and a shipped moment that runs it.

## The premise that was tested rather than argued, and what came back

The reframing on #616 asserted the five guards were *"portable as written"*, established structurally — that they depend only on `_python_files`, `_read_text` and `_git_ignored`. The affirmed implementation brief put the run inside this change rather than accepting that. It was run, and the assertion was false for three of the five.

- `check_emitted_ascii` and `check_stdio_wired` caught a root-level positive control unchanged.
- `check_docstring_not_piped`, `check_subprocess_streams` and `check_harness_tokens` **missed** the same control, their walks being keyed to `SHIPPED_DIRS` and `REPO_ONLY_NAMES`, and caught it once identical content sat under a recognised root. Their predicates survived the move; their enumerators did not.
- An isolated copy of `tools/lint.py` with no repo-only zone present raised `ModuleNotFoundError: No module named 'roster'`. That is why the shipped `check_harness_tokens` owns no roster dependency and takes its population from the wrapper.

Both polarities were run in every tree, with a no-Python negative control that returned clean from every check. The full evidence — commands, tree manifest, controls and raw output — is the spike report retained with this change's dispatch bundle; the trees were a tracked copy of a real 124-file Python repository that is not this one, at `b5ea46e`, plus a synthetic target.

## Rejected

- **A plugin hook, slash command or anything else that runs the guards by itself.** [D-222] rejected a lifecycle hook as a delivery route after plain output, the JSON envelope, `SessionStart` and `UserPromptSubmit` all failed to reach model context in installed Codex sessions. A hook that fired in one runtime and was dead in the other is the exact defect `check_harness_tokens` exists to prevent. Put to the owner as a live option alongside the shape that landed, and declined by him.
- **Restoring the deleted sentence about `getoutput`, `getstatusoutput` and `os.popen`.** That was the small version #616 was filed as, and the independent reconciliation stage recommended it. It is not owed once the guard reaches the reader: the shipped `check_subprocess_streams` names that family at the moment of the mistake, which is what the material promises. Also put to the owner and declined.
- **A guard on the new routing condition.** The checkable form would need each check to declare the cell that owns it. [D-575]'s own rule is that a mechanism is admitted only for a concept prose already states in one sentence, and that sentence did not exist until this change landed it. It becomes a live pitch now that it does. Two existing guards already cover the naming half: the zone wall refuses a shipped cell naming `tools/`, and `tools/tests/test_portability.py` resolves every `scripts/*.py` path a skill names against that skill's own directory. What neither can see is a rule deleted while naming nothing, which is what the sentence is for.

## Calls the session made, recorded so no later reader re-derives them

- **The tests landed at `skills/substrate/tests/test_substrate_lint.py`**, not under the `scripts/tests/` directory the artifact proposed nor under the basename it proposed with it. That basename is already `tools/tests/test_lint.py`'s, and this tree carries no `conftest.py`, no `__init__.py` and no pytest configuration, so the combined run CI performs would have errored at collection. The chosen path also matches the existing `skills/<cell>/tests/` convention. The artifact records file layout as session-owned; the cold seat returned this as an observation while asking nothing of the artifact for it.
- **The travelling test spec-loads the shipped module under a distinct name** rather than importing a bare `lint`, which would contend with `tools/lint.py` in `sys.modules` inside one pytest process.
- **The `substrate` cell body is now above where it stood**, by the run-moment bullet. A body ceiling reports rather than refuses, and the figure is the board refresh note's to derive.

## Evidence

The implementation brief and its [affirmation record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/616#issuecomment-5663867515) are on the issue, with the [dispatch-settings line](https://github.com/Grimblaz-and-Friends/tradecraft/issues/616#issuecomment-5663867957) the owner set for this change. The [pre-implementation artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/616#issuecomment-5664380405) carries the spike's result and was settled by one cold seat on the other vendor from the implementer's, which returned `would`, named no point against it, and confirmed the revision it read by following this repository's worktree `gitdir` pointer to its `HEAD` — local `main` was stale at `76ea486` while the work sat at `4bafb82`, so a seat taking the repository default would have judged the tree before [D-611] landed. `python tools/lint.py` and `python tools/check_version_bump.py` are clean at `51fc257`; the suite is green there but for `tools/tests/test_dev.py::test_external_scratch_keeps_real_fixtures_outside_git`, which fails identically on base `4bafb82` under the same capture setting and passes at `51fc257` under `--capture=sys` — the condition [#615](https://github.com/Grimblaz-and-Friends/tradecraft/issues/615) was filed for, and untouched by this change.

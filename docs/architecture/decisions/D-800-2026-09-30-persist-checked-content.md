# D-800 — Persist the content that was staged

**Purpose:** preserve why persistence checks committed content before publication and retracts only its own rewritten, unpushed commit. **Audience:** a future session changing the persistence guarantee, commit identity, undo or hook boundary. **Success:** that session can revise the mechanism without restoring false success over unchecked content, discarding concurrent work or turning persistence into a hook bypass.

Recorded in [PR #800](https://github.com/Grimblaz-and-Friends/tradecraft/pull/800), implementing [#796](https://github.com/Grimblaz-and-Friends/tradecraft/issues/796). Governed by the [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/796#issuecomment-5910574728), [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/796#issuecomment-5911283961), [`would` cold verdict](https://github.com/Grimblaz-and-Friends/tradecraft/issues/796#issuecomment-5911282320) and [holder reading](https://github.com/Grimblaz-and-Friends/tradecraft/issues/796#issuecomment-5911298059). The [build return](https://github.com/Grimblaz-and-Friends/tradecraft/issues/796#issuecomment-5911977185) records implementation commit `16f3b0a938421599b9980fc93e75f722bb2d0414`. This change's release version is `0.162.0`.

## Context

Organizations of Verra's enabling change needed a byte-exact copy of the reviewer workflow and its configuration. The [incident record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/796) reports that lint-staged rewrote those files during the commit, after validation; persistence reported success because the pushed commit was the remote head. [Commit `fee3da87fee2`](https://github.com/Grimblaz-and-Friends/Organizations-of-Verra/commit/fee3da87fee2e2f46eed2747a7af9a2a4d1acc36) landed changed quote styles and an array reflow. [Commit `792214a03cdd`](https://github.com/Grimblaz-and-Friends/Organizations-of-Verra/commit/792214a03cdd705d1c43791b3192197af70c301d) restored the frozen configuration; the incident records that recovery used `HUSKY=0`.

Arrival alone therefore could not establish that checked content landed. The affirmed brief also records Windgust Questbook's exposure through the same hook tool, superseding the issue body's earlier claim that only Verra was exposed. The script cannot know a product's validation, so the decision treats the content staged by the caller as checked and verifies its identity through the commit and push.

## Decision

The affirmed rows are:

1. **Compare complete content after committing and before pushing.** Any difference between the saved staged tree and the committed tree, including a hook-added path, refuses before publication on one line. Success requires both committed/staged equality and that same commit being the verified remote head. This is the last point at which this run can stop unchecked content before it leaves the machine.
2. **Retract only this run's own unpushed mismatch under the recorded-head guard.** The branch must still point exactly at the identified run commit directly on the recorded start. Undo restores that start and the initially empty staging area while leaving working files with the hook's output. Otherwise nothing is undone and the refusal says so. It names changed paths and the checked-tree identifier, warns to restore promptly because routine Git cleanup can prune an unreferenced tree, and gives both routes: check the rewrite and run again, or restore the checked content. Leaving the rewritten commit on the branch would let a later push carry it; an unconditional undo could instead discard another session's work.
3. **Keep repository hooks in force.** No skip flag or environment override is added. A byte-exact file that conflicts with formatting belongs in that product holder's hook-configuration work, because the hook is the repository's own rule.

This narrows the cell's history exclusion to that single guarded retraction. The separate pre-loaded-index advice in [#774](https://github.com/Grimblaz-and-Friends/tradecraft/issues/774), product hook configuration, validation inside the script and repair of Verra's already-pushed history remain outside this change. An ordinary rejected push still leaves its equal-tree commit locally; mismatch recovery does not apply to that outcome.

## Holder calls and dispatch

The holder reading kept the brief unchanged and settled these calls from the blind judge's notes:

1. **Bound the named paths and retain full recovery identifiers.** A repository-wide formatting hook could otherwise create an unbounded refusal line. Name a fixed prefix, count the remainder, and name the full run commit beside the checked tree so a diff can recover the complete list.
2. **A message-only hook remains a passing control.** A `commit-msg` hook may change the message without changing content; tree equality must keep that lawful path working.
3. **Permit a simpler undo if needed.** Conditional `git update-ref` followed by index-only `git read-tree` was lawful if the index-lock implementation proved fragile, especially on Windows. Either form must report an index failure or intervening branch movement truthfully; the brief buys the guard and resulting state, rather than a particular lock implementation.
4. **List every new refusal with its reason.** This includes equal-tree branch movement before push, because a session must be able to find each refusal the script's logic reaches in the cell.

The cold seat also identified the persistent branch-reflog side effect of command-scoped `core.logAllRefUpdates=true`. The holder accepted it inside the guard's purpose, provided the script and cell disclose it; a no-trace identity mechanism would have been equally lawful if uncertain identity still forbade undo.

The build ran from a holder-supplied dispatch carrying the entrance's composed build prompt followed by the holder reading verbatim, labelled as governing where it differed. This delivered the calls the entrance's artifact-only prompt would omit. It directed the builder to retain and push the branch already checked out, rather than relying on an entrance-created branch name. The holder reading and posted build return preserve that departure and its reason.

## Implementation calls

The builder retained the **reflog identity route**: a unique action, the recorded transition from the start and the commit's sole parent identify the run's commit even after a post-commit descendant. Missing, ambiguous or inconsistent evidence permits no undo or push. The command-scoped setting changes no persistent configuration, but a repository that disabled reflogs gains a branch reflog and Git continues appending to it. The script's docstring and cell disclose this accepted side effect. The identity mechanism avoids trusting a later resolution of `HEAD`.

The builder retained the **index-lock transaction over the permitted simpler form** because the tested Windows form prevents ordinary Git index writers from interleaving the ref/index restoration. Git prepares a complete start index separately; the real index's exclusive lock excludes ordinary commits and checkouts while the recorded branch is conditionally updated and the prepared index installed. Closing the lock file before replacement supports Windows. The expected-old ref update also protects against ref-only writers. Final branch, symbolic-ref and index checks report skipped or incomplete recovery rather than retrying an undo. The sole parent is established once because the identified commit object is immutable; the atomic update itself supplies the head guard, replacing a redundant check before the write. The build return records these reasons, and the pinned transaction tests below demonstrate their separate failure cases.

The builder chose **ten named paths**, the `MAX_MISMATCH_PATHS` constant in the pinned script. Full-tree, NUL-delimited differences use no rename detection or caller-path filter, and names are escaped to ASCII for one-line output. The full commit and tree IDs retain access to paths beyond the bound. Recovery stays path-scoped so unrelated working edits survive; hook-only additions need inspection/removal when restoring the checked result. No permanent backup ref or automatic working-file restore is created.

The builder **pushes the compared commit explicitly** and compares the complete remote object ID. Symbolic-branch or head movement before push refuses even with equal trees; later movement cannot substitute unchecked `HEAD` content. This makes the object compared, pushed and verified the same object.

## Evidence and limits

`skills/persist-changes/scripts/persist.py` at `16f3b0a938421599b9980fc93e75f722bb2d0414` is the mechanical demonstrator; `skills/persist-changes/SKILL.md` at `16f3b0a938421599b9980fc93e75f722bb2d0414` records the corresponding success, history, recovery and hook boundaries.

`skills/persist-changes/tests/test_persist.py` at `16f3b0a938421599b9980fc93e75f722bb2d0414` retains real repositories, hooks and receive-attempt witnesses. `test_unchanged_tree_and_message_only_hook_persist` demonstrates the holder's message control; `test_whole_tree_mismatch_never_attempts_push_and_undo_preserves_work` covers rewrites, additions, deletions, modes and escaped paths. The reflog-disabled control demonstrates the disclosed side effect. The descendant, conditional-ref-race, held-lock, normal-Git-write, index-install-failure, final-state-movement and linked-worktree cases demonstrate the chosen identity and transaction boundaries. Saved-tree restore and revalidated-rerun cases retain both recovery routes; the rejecting-hook case preserves the repository's authority. The build return retains the isolated guard-deletion evidence.

Re-run the focused evidence with `python -m pytest skills/persist-changes/tests/test_persist.py -q` against implementation commit `16f3b0a938421599b9980fc93e75f722bb2d0414`. The build return records local Windows validation and the repository checks rather than this entry freezing their suite counts.

**Linux execution was not established locally.** The build return records that this Windows host had no installed WSL distribution. `.github/workflows/ci.yml` at `16f3b0a938421599b9980fc93e75f722bb2d0414` supplies the Linux and Windows matrix for the full suite, including these hook fixtures. That coverage is a workflow declaration, not a claim that this builder ran Linux or that CI has passed. Consumer use, review and proof remain separate holder-owned stages.

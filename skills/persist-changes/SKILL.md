---
name: persist-changes
description: Land finished work on the current branch safely — stage intended files, commit with an honest message, verify committed content matches staged content, push to the tracked remote, and verify its head. Use whenever a validated change is ready to commit and push; never for new-branch creation or push-rejection recovery.
---

# persist-changes

The mechanical sequence is owned by a script; the judgment about *what* to land and *what to say* stays with you.

**Purpose:** land validated work with staging, message, committed content, and push held to this practice's standards. **Audience:** any session with a finished change ready to land on its current branch. **Success:** the committed content equals the staged content and that commit is the verified remote head, with an honest message — or the stop is a typed one-line reason.

**Pause discipline: typed-halt.** This skill never asks a question: every stop the script's own logic reaches is a typed one-line `not-persisted: <reason>`, so it is safe in unattended runs.

Creating branches or pull requests, amending or rewriting history, and recovering from a rejected push are decisions above this skill, with one history exception: the script retracts its own unpushed commit when its content differs from what it staged, only while the recorded branch still points exactly to that run's commit directly on its recorded start head. This keeps unchecked content from riding a later push without discarding another session's commit.

## The mechanical part — the script owns it

The script sits beside this file at `scripts/persist.py`. Invoke it by that path resolved against the directory this file is in:

```
python scripts/persist.py -m "<message>" <path> [<path> ...]
```

It operates on **the repository containing your current directory**, and **paths are resolved from that repository's root** no matter where you invoke it from.

What the script's own logic refuses, and why, is below; each refusal is said again on the line where it stops.

- **Broad staging is refused, not just avoided**: name the files or directories. Broad staging committed compiled cache artifacts in tradecraft's own skeleton commit ([30fb484](https://github.com/Grimblaz-and-Friends/tradecraft/commit/30fb48482448ded6f45ccd9a2eb6ddb413bdee10) shipped `__pycache__` files).
- **A pre-loaded index is refused**: silently inheriting someone else's staged changes is how unrelated work ends up in your commit.
- **The push goes to the branch's tracked remote**: the upstream remote if configured, the sole remote otherwise; with multiple remotes and no upstream it refuses rather than guessing, because a guess pushes to and then verifies the wrong remote.
- **Uncertain commit identity is refused**: missing, ambiguous or inconsistent reflog evidence, or a commit whose sole parent is not the recorded start head, permits neither undo nor push. Git's reflog interface identifies the run's commit under files or reftable storage even after a post-commit hook makes another; repositories with reflogs disabled gain a branch reflog so this guard has trustworthy evidence.
- **Changed committed content is refused before push**: the whole committed tree must equal the saved staged tree, including paths a hook added, because unchecked bytes must not land. The refusal names up to ten changed paths, the count beyond that, the run commit and the saved checked tree. It reports whether the guarded undo restored the original branch and the run's changed index paths, was skipped, or was incomplete; unrelated index entries and flags, including another actor's staged work, survive. Working files retain the hook's output. A changed branch, wrong parent, held index lock, failed index preparation or preservation check, conditional-update failure, or recovery I/O failure prevents a claim of completed undo. If undo was skipped or incomplete, inspect remaining local history and staging before retrying. **Running again lands the working files exactly as the hook left them**, so run again only after checking and accepting that rewrite. **A byte-exact file takes the restore route:** restore intended paths from the saved tree with `git restore --source=<tree> --worktree -- <paths>` and inspect/remove hook-only additions. Restore promptly: routine Git cleanup can prune the unreferenced saved tree. `git diff --no-renames --name-only <tree> <commit>` recovers the full changed-path list.
- **Branch movement before push is refused**: even with equal trees, the symbolic branch and its head must still be the recorded branch and run commit. The push names that commit explicitly so later movement cannot substitute unchecked content.
- **The push is verified, not assumed**: success requires both committed/staged equality and the remote head being that same commit.
- **Force-push does not exist here**: no flag, no environment override. A rejected push is information, not an obstacle.
- **Hooks stay in force**: there is no skip flag or environment override. A rejecting hook still blocks the commit; when formatting conflicts with a byte-exact file, that product's holder owns the hook-configuration change.
- **Detached HEAD, wrong branch, and absent remote branches are refused**: detached HEAD and absent remote branches are unconditional refusals, while `--expect-branch <name>` arms the wrong-branch refusal by naming the intended branch.

## The judgment part — yours

- **What belongs in the commit:** the validated change, plus any findings you fixed inline while making it — and nothing else.
- **The message:** say what changed and why, with enough evidence that a reader can trust it without re-deriving it. A message that would be true of any commit ("fix issues") is too short to be honest — the script enforces only a floor; the standard is yours to meet.
- **When the push fails:** stop and read the reason line — it carries git's actual error. A rejection saying the branch takes no direct pushes at all, or that changes must go through a pull request, is routing information rather than a fault. **The commit already exists on the branch you are on** — the reason line names it — so branch from it, restore the protected branch to its remote, then publish the branch. Moving it is a step to take, not an error to retry, and re-running the script is not the repair because a second run stages nothing. Deciding how to integrate or recover beyond this is above this skill because it depends on context a staging tool cannot see.

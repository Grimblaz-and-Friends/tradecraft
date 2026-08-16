---
name: persist-changes
description: Land finished work on the current branch safely — stage exactly the intended files, commit with an honest message, push to the branch's tracked remote, and verify the push actually arrived. Use whenever a validated change is ready to commit and push; never for new-branch creation or push-rejection recovery.
---

# persist-changes

Lands finished work on the current branch: deliberate staging, an honest commit message, a verified push to the right remote. The mechanical sequence is owned by a script; the judgment about *what* to land and *what to say* stays with you.

This skill never asks a question: every stop is a typed one-line `not-persisted: <reason>`, so it is safe in unattended runs.

## When to use

After a piece of work is validated and ready to land on the branch you are already on. Not for: creating branches or pull requests (the script refuses to create a remote branch), amending or rewriting history, or recovering from a rejected push — those are decisions above this skill.

## The mechanical part — the script owns it

Installed as a plugin:

```
python "${CLAUDE_PLUGIN_ROOT}/skills/persist-changes/scripts/persist.py" -m "<message>" <path> [<path> ...]
```

Working inside this skill's own source repository, the script is at `skills/persist-changes/scripts/persist.py`. Either way it operates on **the repository containing your current directory**, and **paths are resolved from that repository's root** no matter where you invoke it from. It exits `0` only on a verified push; every other outcome is a loud one-line `not-persisted: <reason>`.

Its guards. Two carry recorded incidents; the other four are service rationale carried from the predecessor project — promoted with the skill and awaiting their first recorded incident here, which should be added to this list when it happens:

- **Broad staging is refused, not just avoided** *(incident-backed)*: the repo root (`.`), glob patterns, and pathspec magic are rejected — name the files or directories. Broad staging committed compiled cache artifacts in tradecraft's own skeleton commit ([30fb484](https://github.com/Grimblaz-and-Friends/tradecraft/commit/30fb48482448ded6f45ccd9a2eb6ddb413bdee10) shipped `__pycache__` files), and in the predecessor project a stray zero-byte file dropped by a concurrent agent was one broad `git add` away from landing in a commit.
- **A pre-loaded index is refused** *(rationale)*: if anything is already staged before the script runs, it stops — silently inheriting someone else's staged changes is how unrelated work ends up in your commit.
- **The push goes to the branch's tracked remote** *(rationale)*: the upstream remote if configured, the sole remote otherwise; with multiple remotes and no upstream it refuses rather than guessing. A hardcoded default would push a fork-based contributor's work to the wrong remote and then verify the wrong remote.
- **The push is verified, not assumed** *(rationale)*: the script compares the target remote's branch head against the new commit and only then reports success — pinned by a test that resets the remote ref server-side and expects `not-persisted`.
- **Force-push does not exist here** *(rationale)*: no flag, no environment override. A rejected push is information, not an obstacle.
- **Detached HEAD, wrong branch, and absent remote branches are refused** *(rationale)*: `--expect-branch <name>` makes the intended branch explicit when it matters, and a branch that doesn't exist on the remote yet must be published deliberately, outside this skill.

## The judgment part — yours

- **What belongs in the commit:** the validated change, plus any findings you fixed inline while making it — and nothing else. If you notice unrelated modified files, that is a question to resolve, not something to sweep in.
- **The message:** say what changed and why, with enough evidence that a reader can trust it without re-deriving it. A message that would be true of any commit ("fix issues", "update files") is too short to be honest — the script enforces only a floor; the standard is yours to meet.
- **When the push fails:** stop and read the reason line — it carries git's actual error. Divergence means fetch and inspect; auth and missing-remote errors mean the environment needs attention. Some protection rejections *are* repairable in place (a missing signature, a stale branch under a strict status-check policy) — repair those and re-run. But a rejection saying the branch takes no direct pushes at all, or that changes must go through a pull request, is routing information rather than a fault: that work belongs on its own branch with a PR. **The commit already exists on the branch you are on** — the reason line names it — so moving it is part of the step: branch from it, restore the protected branch to its remote, then publish. Publishing is deliberately outside this skill, so it is a step to take, not an error to retry. Deciding how to integrate or recover is deliberately outside this script, because the right answer depends on context a staging tool cannot see.

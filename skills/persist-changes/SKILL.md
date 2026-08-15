---
name: persist-changes
description: Land finished work on the current branch safely — stage exactly the intended files, commit with an honest message, push, and verify the push actually arrived. Use whenever a validated change is ready to commit and push; never for new-branch creation or push-rejection recovery.
---

# persist-changes

Lands finished work on the current branch: deliberate staging, an honest commit message, a verified push. The mechanical sequence is owned by a script; the judgment about *what* to land and *what to say* stays with you.

## When to use

After a piece of work is validated and ready to land on the branch you are already on. Not for: creating branches or pull requests, amending or rewriting history, or recovering from a rejected push — those are decisions above this skill.

## The mechanical part — `scripts/persist.py` owns it

```
python scripts/persist.py -m "<message>" <path> [<path> ...]
```

(paths relative to the repository root; run from anywhere inside the repo). The script stages **exactly the paths you name**, refuses surprises, commits, pushes, and confirms the remote actually has the new commit. It exits `0` only on a verified push; every other outcome is a loud one-line `not-persisted: <reason>`.

Its guards, and the incidents they come from:

- **Never stage broadly.** There is no `add -A` path through this script. Broad staging committed compiled cache artifacts in this very repository's first skeleton commit ([30fb484](https://github.com/Grimblaz-and-Friends/tradecraft/commit/30fb484c) shipped `__pycache__` files), and in the predecessor project a stray zero-byte file dropped by a concurrent agent was one broad `git add` away from landing in a commit.
- **A pre-loaded index is refused.** If anything is already staged before the script runs, it stops — silently inheriting someone else's staged changes is how unrelated work ends up in your commit. Unstage them or name them explicitly.
- **The push is verified, not assumed.** The script compares the remote branch head against the new commit and only then reports success. A push that silently didn't land reads as done and surfaces days later as "where did that fix go?"
- **Force-push does not exist here.** No flag, no environment override. If the push is rejected, that is information, not an obstacle.
- **Detached HEAD and wrong-branch states are refused** (`--expect-branch <name>` makes the intended branch explicit when it matters).

## The judgment part — yours

- **What belongs in the commit:** the validated change, plus any findings you fixed inline while making it — and nothing else. If you notice unrelated modified files, that is a question to resolve, not something to sweep in.
- **The message:** say what changed and why, with enough evidence that a reader can trust it without re-deriving it. A message that would be true of any commit ("fix issues", "update files") is too short to be honest — the script enforces only a floor; the standard is yours to meet.
- **When the push is rejected:** stop and look. Fetch, inspect what diverged, and decide how to integrate — that decision (merge, rebase, or hand it to a human) is deliberately outside this script, because the right answer depends on context a staging tool cannot see.

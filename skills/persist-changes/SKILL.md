---
name: persist-changes
description: Land finished work on the current branch safely — stage exactly the intended files, commit with an honest message, push to the branch's tracked remote, and verify the push actually arrived. Use whenever a validated change is ready to commit and push; never for new-branch creation or push-rejection recovery.
---

# persist-changes

The mechanical sequence is owned by a script; the judgment about *what* to land and *what to say* stays with you.

**Purpose:** land validated work with staging, message, and push held to this practice's standards. **Audience:** any session with a finished change ready to land on its current branch. **Success:** exactly the named files land with an honest message and a verified push — or the stop is a typed one-line reason.

**Pause discipline: typed-halt.** This skill never asks a question: every stop the script's own logic reaches is a typed one-line `not-persisted: <reason>`, so it is safe in unattended runs.

Creating branches or pull requests, amending or rewriting history, and recovering from a rejected push are decisions above this skill.

## The mechanical part — the script owns it

The script sits beside this file at `scripts/persist.py`. Invoke it by that path resolved against the directory this file is in:

```
python scripts/persist.py -m "<message>" <path> [<path> ...]
```

It operates on **the repository containing your current directory**, and **paths are resolved from that repository's root** no matter where you invoke it from.

What the script refuses, and why, is below; each refusal is said again on the line where it stops.

- **Broad staging is refused, not just avoided**: name the files or directories. Broad staging committed compiled cache artifacts in tradecraft's own skeleton commit ([30fb484](https://github.com/Grimblaz-and-Friends/tradecraft/commit/30fb48482448ded6f45ccd9a2eb6ddb413bdee10) shipped `__pycache__` files).
- **A pre-loaded index is refused**: silently inheriting someone else's staged changes is how unrelated work ends up in your commit.
- **The push goes to the branch's tracked remote**: it is never guessed, because a guess pushes to and then verifies the wrong remote.
- **The push is verified, not assumed**: success is claimed only when the remote head is the new commit.
- **Force-push does not exist here**: no flag, no environment override. A rejected push is information, not an obstacle.
- **Detached HEAD, wrong branch, and absent remote branches are refused**.

## The judgment part — yours

- **What belongs in the commit:** the validated change, plus any findings you fixed inline while making it — and nothing else.
- **The message:** say what changed and why, with enough evidence that a reader can trust it without re-deriving it. A message that would be true of any commit ("fix issues") is too short to be honest — the script enforces only a floor; the standard is yours to meet.
- **When the push fails:** stop and read the reason line — it carries git's actual error. A rejection saying the branch takes no direct pushes at all, or that changes must go through a pull request, is routing information rather than a fault. **The commit already exists on the branch you are on** — the reason line names it — so branch from it, restore the protected branch to its remote, then publish the branch. Moving it is a step to take, not an error to retry, and re-running the script is not the repair because a second run stages nothing. Deciding how to integrate or recover beyond this is above this skill because it depends on context a staging tool cannot see.

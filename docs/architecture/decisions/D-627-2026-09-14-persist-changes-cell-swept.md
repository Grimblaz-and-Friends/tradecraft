# D-627 — The persist-changes cell swept: the concepts stay, six rules go to the script's own refusals, and the one paragraph a cold run said was load-bearing comes back

**Landed by** [PR #627](https://github.com/Grimblaz-and-Friends/tradecraft/pull/627). Closes [#587](https://github.com/Grimblaz-and-Friends/tradecraft/issues/587). Governed by the implementation brief affirmed on [#571](https://github.com/Grimblaz-and-Friends/tradecraft/issues/571#issuecomment-5627498365) on 2026-09-10, which commissions each cell's sweep as its own reviewed change without a fresh affirmation; [D-575] landed the principle. Evidence pinned at `3605b26` unless stated, over base `6376ccb`.

## What was decided

The `persist-changes` cell keeps every concept it carried and sheds what its own shipped script already says at the moment of the mistake. This cell's shed is unlike the others in the programme: it wraps a script, and the script stops on one typed line that states the refusal. So the dominant destination here is **not a new guard and not a new script message, but a message that already existed** — where mechanics go to the script, the lines were already printing them and are cited below by number; **no script line was added**. The force-push refusal stays in prose because a flag that does not exist produces argparse's line, not the script's. `skills/persist-changes/scripts/persist.py` and `skills/persist-changes/tests/test_persist.py` are byte-identical to their state at `6376ccb`, which the acceptance criteria pin by diff.

The [pre-implementation artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/587#issuecomment-5649379380) settled all 22 dispositions sentence by sentence before anything was built, and one cold seat on the other vendor returned `would` with no points against it.

**One of those dispositions was reversed by use, which is the part of this entry worth reading.** The artifact cut a protected-branch procedure and wrote its own falsifier for that cut. The run falsified it. The procedure is back, and the section below says what the run did.

## Every passage that left, and which material took it

As the brief requires: the change that removes a rule says which it was. Deletions fall in two places and both are tabled — passages that leave whole, and sentences cut out of lines classed *sharpen*.

### The two passages that left whole

| passage | class | where it went |
| --- | --- | --- |
| `SKILL.md:14` — the `## When to use` heading | cut, unwritten | Its only sentence was the frontmatter description's own trigger, which every session already holds; what survived of the section moved under the purpose header, leaving the heading with nothing beneath it. |
| `SKILL.md:28` — *"Its guards. Two carry recorded incidents; the other four are service rationale carried from the predecessor project — promoted with the skill and awaiting their first recorded incident here, which should be added to this list when it happens:"* | to entry | This entry, below. Provenance is rationale; *"should be added to this list when it happens"* is a maintenance instruction about editing the file, which is unwritten; and the count was false about the tree. One sentence replaces it, naming what the script refuses and that each refusal is said again on the line it stops with. |

### The sentences cut out of sharpened lines

| sentence cut | from | to |
| --- | --- | --- |
| *"Lands finished work on the current branch: deliberate staging, an honest commit message, a verified push to the right remote."* | `:8` | unwritten — a copy of the frontmatter description at `:3` |
| *"The judgment section below is what you decide before invoking it and after it stops, never a question the skill puts to you mid-run."* | `:12` | unwritten — restates the split `:8` states |
| *"After a piece of work is validated and ready to land on the branch you are already on."* | `:16` | unwritten — a copy of the description's trigger |
| the parenthetical *"(the script refuses to create a remote branch)"* | `:16` | script message `persist.py:134` — `remote branch {remote}/{remote_branch} does not exist -- publishing a new branch is outside this skill; push it deliberately first` |
| *"which is what makes one contract hold both in an installed plugin and in this skill's own source repository"* | `:20` | the `substrate` cell, `SKILL.md:22` — *"**A path resolved against the directory of the file naming it** works in a source repository and in an installed plugin alike."* **No pointer replaces it**: the job here needs the path, not the standard, and `substrate`'s own description routes a reader who wants the why. |
| *"It exits `0` only on a verified push; every other outcome is a loud one-line `not-persisted: <reason>`."* | `:26` | script message `persist.py:106`, the argparse description printed by `--help`. `:10` and `:12` already said it twice in this body. |
| the second incident — a stray zero-byte file dropped by a concurrent agent, one broad `git add` from a commit | `:30` | this entry. A second example, where the principle allows one. The surviving example is the `30fb484` link, kept deliberately. |
| the enumeration of the three refused staging forms (repo root, globs, pathspec magic) | `:30` | script messages `persist.py:67` (`pathspec magic is refused`), `:69` (`glob patterns are refused`), `:78` (`the repository root is refused -- staging everything is the broad form this skill exists to prevent; name the paths`) |
| *"if anything is already staged before the script runs, it stops"* | `:31` | script message `persist.py:128` — `index already has staged changes ('{first}', ...) -- unstage them or name them explicitly` |
| the fallback order (upstream if configured, sole remote otherwise, refuse on multiple) | `:32` | `pick_remote` at `persist.py:84-100`, and its refusal line `:98` — `branch '{branch}' has no upstream and {n} remotes exist -- set an upstream (git branch --set-upstream-to) so the push target is explicit` |
| *"A hardcoded default would push a fork-based contributor's work to the wrong remote and then verify the wrong remote."* | `:32` | this entry — the argument against a rejected alternative |
| *"pinned by a test that resets the remote ref server-side and expects `not-persisted`"* | `:33` | `tests/test_persist.py:107-109`, whose own docstring carries it. Evidence about a guard, which `skills/authoring/references/routing.md:22` says is otherwise paid for twice. |
| the `--expect-branch` mechanics | `:35` | `persist.py:109`, the flag's own `--help` text |
| *"If you notice unrelated modified files, that is a question to resolve, not something to sweep in."* | `:39` | unwritten — a case already decided by the preceding *"and nothing else"* |
| *"update files"* | `:40` | unwritten — a second example of the generic commit-message failure; *"fix issues"* stays as the one example |
| the divergence / auth / missing-remote case list, the repairable-protection examples, and the do-not-re-run warning | `:41` | unwritten and script message — git's own text names divergence, auth, a missing remote and the repairable protection conditions, and `persist.py:139` says `nothing to commit for the given paths` at the moment a second run happens |
| six `*(incident-backed)*` and `*(rationale)*` tags | `:30-35` | this entry, in the provenance section below |

**The `:41` protected-branch procedure is not in this table.** It was cut and then restored; the section below is its record.

## The guards' provenance, and the count the cell had wrong

`SKILL.md:28` claimed two guards carried recorded incidents and four carried service rationale. **The tree did not bear that out.** At `6376ccb`, `grep -c "(incident-backed)" skills/persist-changes/SKILL.md` → `1` and `grep -c "(rationale)"` → `5`; the script's own docstring at `persist.py:4-7` agrees with the tree and not with the paragraph, saying *"Guard rationale and incident records live in the skill's SKILL.md — the broad-staging guard carries recorded incidents; the others carry service rationale from the predecessor project, promoted with the skill under ADR-009 and awaiting their first recorded incident here."*

So the provenance, read off the tree rather than off the sentence: **one guard is incident-backed** — broad staging — **and five are carried as service rationale** from the predecessor project, promoted with the skill under ADR-009 and still awaiting a first recorded incident here.

The broad-staging guard's two incidents, cited rather than re-transcribed because the registry that holds them is a frozen archive:

- `__pycache__` artifacts shipped through broad staging in this repository's own skeleton commit, [30fb484](https://github.com/Grimblaz-and-Friends/tradecraft/commit/30fb48482448ded6f45ccd9a2eb6ddb413bdee10) — `docs/architecture/evidence-archived.md:21`, graded repo-verifiable. **This one stays in the prose** as the single example the principle allows.
- A stray zero-byte file dropped by a concurrent agent in the predecessor project, one broad `git add` from landing — `docs/architecture/evidence-archived.md:20`, graded recollection-grade. This is the second example, and it is here.

The **rejected alternative** behind the tracked-remote guard: a hardcoded `origin`. It was rejected because it would push a fork-based contributor's work to the wrong remote and then verify that same wrong remote, so the verification would confirm the mistake rather than catch it.

## The protected-branch procedure: cut, falsified by use, restored

`SKILL.md:41` carried a procedure for a push rejected because the branch takes no direct pushes: the commit already exists on your branch, so branch from it, restore the protected branch to its remote, then publish. The artifact classed this as a case the concept already reaches, whose application in *this* repository is the repo-only `landing` cell's (`docs/cells/landing/SKILL.md:17`, *"Branch first (`main` refuses direct pushes)"*) — which shipped prose cannot name across the wall.

**It wrote its own falsifier for that call, and the run falsified it.**

Criterion 5 put one situation to sessions holding none of this change's history, once under the base text and once under the cut text, each in its own throwaway adopting repository with a bare `origin` whose `pre-receive` hook rejects `refs/heads/main`, each on `main` with a validated one-file change, each told only *land this with the persist-changes skill*. Four consumers ran, two arms twice; the arms of a round differ in exactly one file.

| arm | body | outcome |
| --- | --- | --- |
| alpha, charlie | base `6376ccb` | **landed** — branched from the stranded commit, restored `main` to its remote, published the branch |
| bravo, delta | cut text `555d186` | **stopped** — commit left on local `main`, ahead 1, no branch anywhere |

The criterion's falsifier is a cut-text session leaving the commit on the protected branch where the base session did not. That is what happened, in both rounds, and the base arms credited the paragraph by name — one of them: *"The persist-changes skill names this case directly and says it is routing information rather than a fault — branch from the commit that already exists, restore the protected branch to its remote, then publish, with publishing deliberately outside the skill and re-running it explicitly wrong (the commit exists, so a second run would stage nothing). I followed that."* The cut-text arms read what remained as putting recovery above the skill and stopped: *"I stopped there rather than routing around it."*

So **the procedure returns**, at `3605b26`, as the concept and its reason rather than as the case list: a rejection saying the branch takes no direct pushes is routing information rather than a fault, the commit already exists and the reason line names it, so branch from it, restore the protected branch, publish — re-running the script is not the repair, because a second run stages nothing. **What does not return is the rest of `:41`'s cut**: the divergence/auth/missing-remote case list stays unwritten, since git's own text names those.

This addition is licensed by the affirmed brief through the artifact's own acceptance criterion, not by a review finding. The artifact's instruction to its fix batch — that a governing sentence added on a finding alone is not owner-approved and says so rather than adds it — is untouched by this, and still binds anything the review proposes.

**Two limits on the run, stated because they bound what it proves.** The isolation procedure requires telling a consumer the tree has no pull-request board, and both cut-text consumers cited that in reasoning a topic branch would be pointless; the base consumers had the identical sentence and published a branch regardless, so the text is the variable and the premise is constant, but a tree with a real forge might move the cut-text arm and this run cannot say. And the first round ran on a tree whose archive carried `skills/` without `lib/`, so the script died on `ModuleNotFoundError: winio` before `main()`; both consumers reached the rejection by other routes and reported the breakage, the fixture was rebuilt to gate on `persist.py --help` running in the extract, and the two rounds agree arm for arm. The [session note](https://github.com/Grimblaz-and-Friends/tradecraft/pull/627#issuecomment-5671629158) carries both in full.

PR #3's incident is what put the paragraph there in the first place: `6bab536`'s message records at its lines 13-14 that *"main is protected and nothing said so - the first push of the branch was rejected"*, and at 29-30 that *"the persist-changes routing left the rejected commit stranded on the protected branch"* — a review high. The run above is that same failure reproduced under the cut text, which is why the cut did not stand.

## Four calls the sweep made, stated so a later sweep does not re-make them

**This cell emits no template, and that is a decision rather than an omission.** The reading governing these sweeps sends an output's fields to a template. This cell emits nothing a session copies at the moment of writing except the invocation, which is already a fenced block and stays one. The commit message has no fields — a template for it would be the *"fix issues"* failure the message bullet names, in another form — and the `not-persisted: <reason>` line is the script's output, not the session's. So no `references/` directory, no index owed, and `check_depth_index` at `tools/lint.py:4775` has nothing to check here.

**The calling contract's reason is `substrate`'s; the path is this cell's, and no pointer was added.** This cell keeps the application — where the script sits and that it is invoked by a path resolved against this file's directory — because that is what a consumer copies. The guard on the spelling is repo-only (`tools/tests/test_portability.py`, `test_skill_names_its_scripts_relative_to_the_naming_file`), so shipped prose cannot name it either way.

**The typed-halt label is not a shared standard.** `skills/adversarial-review/SKILL.md:10` and this cell's `:12` each state the halt property of their own instrument under the same label; neither owns the other's sentence, and neither is a copy.

**The ceiling followed the body down, twice.** `CELL_BODY_CEILING_CHARS["skills/persist-changes/SKILL.md"]` was re-baselined from `5_549` to `2_819` at the build and to `3_258` when the procedure returned. The constant's own comment prescribes this for a cell that sheds, and a ceiling left where it stood would measure nothing until the body regrew to meet it.

## What was left open, and for whom

- **Of the four issues the artifact named, only #292 is open**: [#39](https://github.com/Grimblaz-and-Friends/tradecraft/issues/39) (argparse failures bypass the typed-halt line), [#205](https://github.com/Grimblaz-and-Friends/tradecraft/issues/205) (three subprocess-failure sites report the subcommand or intent rather than the command), and [#267](https://github.com/Grimblaz-and-Friends/tradecraft/issues/267) (the flow does not state its remote assumption) are closed; [#292](https://github.com/Grimblaz-and-Friends/tradecraft/issues/292) (the flow says commit then publish while the sanctioned commit tool refuses that order on a new branch) remains open. They are script and `landing` work the brief does not fund. **#292 in particular is not closed here**: whether the flow reorders commit-then-publish is the `landing` cell's sweep's or #292's own fix.
- **Two copies of this cell's concerns live elsewhere and were not cut**: `skills/filing`'s calling-contract sentence ([D-524] decision 6), which #572's sweep takes; and `docs/cells/landing/SKILL.md:17`'s *"Branch first (`main` refuses direct pushes)"* and *"publish the branch"*, which are this repository's own application and that cell's to keep or reshape. A copy is cut only in the cell being swept.
- **Publishing a branch stays unwritten in the shipped zone.** The description's exclusion and `persist.py:134` are the what; the how of `git push -u` is the reader's.

## No settling row, and the reason

`docs/settling.jsonl` takes one row per change owing an implementation brief, recording how that brief reached settled. This change's brief is #571's, affirmed once for every sweep it commissions, and its row is already on that record (`grep -n '"issue": 571' docs/settling.jsonl`). A second row would record the same affirmation twice with the same history figures. The cold check's rounds are on the pull request instead. The `engagement` and `substrate` sweeps made the same call, so the programme agrees.

## Figures

Stated as commands with both endpoints pinned, never as outputs.

- **Shipped prose delta** (the brief's own measure): `find skills -name "*.md" -exec cat {} + | wc -c`, run once on each of `6376ccb` and `3605b26`. Both endpoints are named, so this needs no checkout.
- **The body against its ceiling:** `python tools/lint.py`, run in a checkout at `3605b26`, which reads the constant back and reports any cell standing over where it stood. `tools/figures.py` reads the working tree and has no option naming a tip, so cut one: `git worktree add --detach <path> 3605b26`.
- **What the diff touches:** `git diff --stat 6376ccb 3605b26`, and `git diff 6376ccb 3605b26 -- tools/lint.py` for the single constant.
- **The cell's script and tests unchanged:** `git diff --quiet 6376ccb 3605b26 -- skills/persist-changes/scripts skills/persist-changes/tests`.

[D-575] [D-186] [D-314] [D-524]

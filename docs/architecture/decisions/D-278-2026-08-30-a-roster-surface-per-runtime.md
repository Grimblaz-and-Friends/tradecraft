# D-278 — One roster surface per runtime, and the always-on total stops being one number

**Purpose:** record why this repository generates a second roster into `.agents/skills/`, why the two surfaces are not one, and why the always-on figure now reports per runtime. **Audience:** a session changing the roster generator, its guard, or the always-on figure. **Success:** a reader can tell which parts were measured, which were chosen, and what was rejected with its price.

## The defect

[#199](https://github.com/Grimblaz-and-Friends/tradecraft/issues/199) established that this repository never loaded its own cell descriptions and fixed it with a generated roster under `.claude/skills/` ([D-210](D-210-2026-08-26-project-roster-and-the-loaded-total.md)). That remedy is one runtime wide. Codex discovers a project's own skills under `.agents/skills`, this repository had no such directory, and so every trigger the practice deliberately routes to a description reached every adopter, reached a Claude Code session here, and reached a Codex session working here not at all — including the `substrate` cell, which exists substantially to keep this practice portable across the two runtimes it claims.

`check_project_roster` carried the exclusion in its own docstring for eleven weeks: *Codex is outside that scope and stays outside it*, with the note that a universal would have asserted a fix Codex never received [PR #210 review, M10]. The sentence was true and correct when written. What nobody re-checked is that Codex acquired a loading surface afterwards.

## What was measured, and in which direction

The change rests on facts about two runtimes, so both were run. One temporary git repository held `zorbex-alpha` under `.agents/skills/` and `zorbex-beta` under `.claude/skills/`; every probe was forbidden to read, list, glob or search files and told to answer from loaded context alone.

- **Codex** (`codex exec --ephemeral --sandbox read-only`, codex-cli 0.150.0-alpha.12.2) returned `zorbex-alpha` with its description verbatim and did not return beta.
- **Claude Code** (`claude -p`, run twice under different phrasings) returned `zorbex-beta` and answered that `zorbex-alpha` was not available to it, while listing every skill it did hold.

**So the split is symmetric and neither directory reaches the other's runtime.** That is what closes off the cheap shapes: one shared directory serves one runtime, and a link between them was already dead here for the reason [D-210](D-210-2026-08-26-project-roster-and-the-loaded-total.md) records — `mklink /D` is refused without privilege on the owner's machine, git carries `core.symlinks=false`, and MSYS `ln -s` silently copies.

**Against this branch**, a Codex session in the session worktree and one in a plain checkout were each asked for every offered skill whose identifier ends in `substrate`, and whether its description carries the phrase `the streams a launch must name`. Both returned two entries: one YES holding this tree's description, one NO holding the plugin version installed on that machine, which predates that clause.

**The trap that cost three probes, recorded because the next session will hit it.** Asked instead whether an *unprefixed* `charter` or `substrate` was offered, the same sessions answered NO — with the plugin installed, both entries surface to the model under the plugin-qualified identifier, so a question about the *name* cannot discriminate and a question about the *description* can. A control entry under a name no plugin uses was offered immediately, which is how discovery was separated from labelling. **A negative answer about a name is not evidence a surface failed to load.**

## The mechanism

`tools/roster.py` gains a `Surface` — a directory and the runtime that loads it — and `SURFACES` holds one row per runtime. `verify()` and `write()` loop over it; `expected()`, `roster_names()` and `inside_roster()` take the surface they are working on.

**Findings are per surface, and each names its runtime.** A cell stale in both directories draws two findings, because they are two files and repairing one leaves the other serving a superseded trigger to the other runtime — which is #199's defect with the runtimes swapped. The single exception is unparseable frontmatter, reported once: the cell is what has to change, and it is one file however many copies of it are owed.

**The frontmatter is identical on every surface and the body is not.** What loads must be one cell's block copied verbatim, or one trigger fires two ways. What explains the file names the runtime that copy exists for, which keeps [PR #210 review, M10]'s discipline alive after the exclusion it was written about has gone: a session opening the copy it is not served by learns that from the file rather than concluding it is a stray duplicate.

**Ownership is checked on every surface, not the first.** [PR #210 cycle one, C1-F2/C1-F3] records that checking it on one path is what let hand-written content go on being destroyed after the removal branch stopped. A second surface is a second set of those paths, and `tools/tests/test_roster.py::test_ownership_holds_on_every_surface_not_just_the_first` is what fires on the loop that forgets.

## The always-on total stops being one number

The quantity is per runtime, so the figure reports it that way: `here` carries a row per surface, read from the directory that runtime loads, and **`repo_total` is the smallest of them**.

**Why the smallest rather than the largest, or the first.** On a tree the roster guard passes, every row holds the same number and the choice is invisible. Where they diverge, the smallest cannot overstate what some session here reads, and the rows printed beside it name which runtime is short — so a reader cannot take the scalar and miss the divergence. The largest was rejected on this change's own arrival: with the base loading nothing into Codex, a maximum would have reported this pull request's movement as **zero**. Derived at `8e816e9` by `python tools/figures.py` against `origin/main`; the base's `repo_total` is its Codex row, and the movement is the whole of what a Codex session here now loads and did not.

This is #199's correction one layer out. `is_roster_path` is made per surface rather than widened to accept either directory, because a predicate matching both would let one surface's entries be counted into the other's total — the same defect, where the number stays put while a runtime stops loading anything.

**Both renderers are the figure's and the callout borrows them.** The merge callout's sentence and `figure_always_on`'s value string would otherwise be two wordings of one decomposition, and the callout is the one the owner reads at the moment he merges. It carries no `needs:` on `lint-and-test`, so it posts on exactly the trees where the roster guard is red and the runtimes disagree [PR #210 review, M1].

## Rejected

- **Accepting the split and recording it in prose** — a doctrine or `authoring` line telling authors that a description-borne trigger does not reach a Codex session here. It pays with a rule what the mirror pays with a generator already built and reviewed, and the admission order puts a mechanism ahead of prose. The gap would also widen with every future change that routes a trigger to a description. This was the fork put to the owner; he picked the mirror.
- **Shipping `.agents/skills` to adopters.** Measured rather than assumed: the installed plugin's cache holds the whole repository root, `.claude/skills/` with all nine entries included, and a Codex probe in a bare directory listed the nine cells **once each**. So the plugin loader reads only the plugin's own `skills/`, and a second `SKILL.md` tree at the plugin root reaches a consumer's cache inert — the same standing as `.claude/skills/`.
- **The `SKILL.md` specification's reference validator in CI.** The guards here already hold more than it checks — frontmatter fields, byte-for-byte agreement with the cell, ownership, line endings — and an external toolchain for less is not worth the dependency. Declined and recorded rather than filed.
- **Admitting `.agents` to `REPO_ROOTS`**, for the reason [D-210](D-210-2026-08-26-project-roster-and-the-loaded-total.md) gives about `.claude`: a session can drop other directories under it, and resolving against one would give `python tools/lint.py` two answers for the same commit.
- **Collapsing the per-surface findings into one line naming both directories.** They are two files that can be independently wrong — one present and one missing, one generated and one hand-written — and a collapsed line would have to be re-split the moment they differ, which is the state the guard exists for.

## What this change did not touch

No shipped file, so no version bump; `python tools/check_version_bump.py --base main` agrees. No always-on surface, so no outflow was owed. No doctrine rule was added, per the admission order — the mechanism carries it. [D-210](D-210-2026-08-26-project-roster-and-the-loaded-total.md)'s sentence that *a Codex session here loads neither roster and stays at 11,351* is now history rather than a defect, and frozen entries are not repaired.

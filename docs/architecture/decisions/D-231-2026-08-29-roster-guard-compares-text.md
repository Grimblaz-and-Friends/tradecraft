# D-231: The roster guard compares text, because the line endings its files carry on disk are not this repository's to set

**Status:** Accepted 2026-08-29 (PR #231)

## Context

`tools/roster.py` writes one entry per cell under `.claude/skills/`, carrying the cell's frontmatter so that this repository's own descriptions load in a Claude Code session working here — the mechanism [D-210](D-210-2026-08-26-project-roster-and-the-loaded-total.md) landed for [#199](https://github.com/Grimblaz-and-Friends/tradecraft/issues/199). `roster.verify`, which `check_project_roster` calls on every lint run, compared `target.read_bytes() == want`.

On Windows that comparison reported a finding per cell in every Claude Code worktree, before the session had touched anything. The entries were CRLF on disk; the cells were LF. `git status` reported nothing and `git diff` was empty, because `.gitattributes` (`* text=auto eol=lf`) holds the index at LF and normalises on the way in, so nothing in git's view differed. [#224](https://github.com/Grimblaz-and-Friends/tradecraft/issues/224)

**The cause is a copy, not a checkout, and that was settled by running both.** `git worktree add --detach <path> HEAD` off `8b080c8` produces LF entries, no `.claude/settings.local.json`, and `python tools/lint.py` at exit 0. The Claude Code worktree off the same commit produces CRLF entries, the gitignored file, and a finding per cell. The harness copies `.claude/` rather than checking it out, and the copy rewrites the line endings.

Two things follow, and together they are why this could not be left as it was.

- **The flow requires a green `tools/lint.py` before committing**, and a session that had changed nothing had no way to tell this red from one it had caused. [D-186](D-186-2026-08-25-windows-text-mode-defaults.md)'s ruling 5 anticipated CRLF on disk here and told sessions the symptom was ` M` from `git status` against an empty diff — *notice it and move on*. It did not anticipate a red guard, which is not something a session moves on from. #224 records five steps spent diagnosing it and [#162](https://github.com/Grimblaz-and-Friends/tradecraft/issues/162) records four on the same family of cause.
- **The command the finding named did not close it.** `python tools/roster.py --write` rewrote the nine entries LF and the lint went green, but git recorded nothing because the index already held LF — so the repair left no trace in any diff, and the next worktree started red again.

There was a second red beside the first, which #224 did not record: `tools/tests/test_roster.py::test_this_repository_carries_a_roster_for_every_cell` asserted both `roster.verify(ROOT) == []` and `b"\r" not in entry.read_bytes()` against the on-disk tree, and both were false there. So the suite failed beside the lint, from the one cause, and neither was nameable by the session as its own doing.

## Decision

**1. `matches()` compares with `\r\n` normalised, and both call sites go through it.** `roster.verify` and `roster.write` share it, so the guard and the writer keep the one definition `expected()` already exists to hold.

The warrant is not that line endings do not matter. It is that **a newline difference at this site can neither reach the repository nor be repaired in the tree it appears in.** `.gitattributes` normalises the entry to LF on the way into the index, so a CRLF entry and its LF twin are the same commit; and the CRLF is written by a copy no command here performs, so re-running the writer clears one working tree and the next one starts over. Reporting it was a finding with no lawful response, on a tree nobody had touched — and a guard that reds a tree nobody can fix is a guard somebody deletes, which the suite's own lawful-polarity test already says in as many words.

**2. Both sides are normalised, not only the entry on disk.** `want` is built from a cell git checks out LF, so today only the entry side can differ. Normalising one side would make an unclearable red possible the moment a cell arrived CRLF too: the entry would normalise to LF, `want` would not, `--write` would write `want`, and the re-verify would fail again. The symmetric form stays self-consistent whatever either side carries. The cost of the symmetry is nothing; the cost of the asymmetry is a red the one named command cannot clear, which is the defect this entry exists to close, rebuilt one layer down.

**3. `\r\n` only, never a lone `\r`.** That pair is what a Windows text-mode write produces and what was observed. A bare carriage return is not a line ending anything here emits, so an entry carrying one is corrupt rather than copied, and forgiving it would silently accept the corruption. Pinned by a test in that polarity.

**4. The tree-level test stops asserting the entries are LF on disk.** That assertion was the wrong instrument for what it wanted. What the generator writes is pinned deterministically in `tmp_path` by `test_the_generator_introduces_no_carriage_return_of_its_own`, where no later copy can move it; asserting it again against the working tree asserted a property of whatever produced that tree, which is not this repository.

**5. The substrate cell's third text-mode rule is not amended, and neither is `AGENTS.md`.** The rule says a file that will later be compared, restored or measured is *written and read as bytes*; `roster.write` still writes bytes and still has its guard. What this decision separates is the **write** half from the **compare** half, at one site where the file leaves this repository's control between the two. That is a bound on the rule's reach rather than a change to it, and it is stated in `matches()` where a session would look for it before tightening the comparison back.

`AGENTS.md`'s D-186 sentence stays as it is because it stays true and because the fix removes the red rather than teaching sessions to live with it. No always-on surface is edited here, so no outflow is owed. [D-184]

## The exposure #224 asked about, enumerated

The filing deferred *whether anything else the two-zone layout tracks under `.claude/` has the same exposure*. It does not, and there was already a precedent for the answer.

`git ls-files .claude` returns the nine roster entries and nothing else. Reading every `read_bytes()` call under `tools/` and `skills/`, exactly two things consume them: `roster`, which compared bytes, and `_normalized_chars` in `skills/authoring/scripts/figures.py`, which reached for the same move first and states the same reason — *"one fixed basis, so a file's count cannot depend on which OS checked it out."* One sibling had it and the other did not; this change closes the half that was open, and the two now agree.

## What was rejected

- **Reporting a line-ending-only mismatch as its own finding, or as a note.** It leaves the check red on a clean tree, which is the defect. There is no action a session can take that clears it durably, and a finding naming a fix that does not fix is worse than silence.
- **Fixing the copy.** Outside this repository — established by running the plain-worktree comparison above.
- **A checked-in normalisation.** `.gitattributes` already does everything git can do here; the index was already LF throughout, which is exactly why `git status` was clean and the red looked like a real defect.
- **A shared helper in `lib/`.** The enumeration above found one byte-identity comparison against a `.claude/` file. A shipped module for a single repo-only caller buys a plugin version bump and no second consumer.

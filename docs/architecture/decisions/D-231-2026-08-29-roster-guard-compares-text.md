# D-231: The roster guard compares text, because the line endings its files carry on disk are not this repository's to set

**Status:** Accepted 2026-08-29 (PR #231)

## Context

`tools/roster.py` writes one entry per cell under `.claude/skills/`, carrying the cell's frontmatter so that this repository's own descriptions load in a Claude Code session working here — the mechanism [D-210](D-210-2026-08-26-project-roster-and-the-loaded-total.md) landed for [#199](https://github.com/Grimblaz-and-Friends/tradecraft/issues/199). `roster.verify`, which `check_project_roster` calls on every lint run, compared `target.read_bytes() == want`.

In a Claude Code **session** worktree on Windows that comparison reported a finding per cell before the session had touched anything. The entries were CRLF on disk; the cells under `skills/` were LF. `git diff` was empty, because `.gitattributes` (`* text=auto eol=lf`) normalises the entry to LF on the way into the index, so a CRLF entry and its LF twin are ordinarily the same commit. [#224](https://github.com/Grimblaz-and-Friends/tradecraft/issues/224)

### The mechanism, and the population it reaches

**A harness copy writes those files in text mode; git's checkout does not.** Established by three measurements, the last two of which this change's own review had to run after five reviewers reached the opposite conclusion.

- `git worktree add --detach <path> HEAD` off `8b080c8` produces LF entries and `python tools/lint.py` at exit 0.
- **The creation trace.** Over all 118 tracked files in the worktree this change was built in, mtimes fall into two operations 100ms apart: ten files at `15:40:03.936–.948`, every one CRLF — the nine roster entries **and `CLAUDE.md`** — then 108 files at `15:40:04.050+`, every one LF, including `.gitattributes` and `AGENTS.md`. The CRLF group is not an index-order prefix: `.claude-plugin/` sorts before `.claude/skills/` byte-wise and lands in the *later* group. So it is not part of git's sequential checkout.
- **The census.** `CLAUDE.md`'s line endings across every worktree on the owner's machine: 14 of 15 session worktrees CRLF, 0 of 16 `agent-*` subagent worktrees, source checkout LF. The single LF session tree predates the roster.

**So `CLAUDE.md` is the discriminator, and it is the cheap check this entry exists to hand forward.** Nothing in this repository ever rewrites it, where `roster.py --write` erases the evidence under `.claude/skills/` the moment anyone clears the red. Its line endings are therefore a permanent fossil of how a worktree was created, readable in one command.

**Scope, stated narrowly because the wide version misled five readers.** Session worktrees exhibit this; `agent-*` subagent worktrees do not, and they are Claude Code worktrees too. A first draft of this entry said *every* Claude Code worktree, and every one of the five review seats — all sitting in `agent-*` trees — checked its own tree, found LF, and reported the recorded cause as false. That is the re-tightening pressure this entry is written to prevent, observed rather than argued.

**`core.autocrlf=true` is not the cause**, though it is set in the system gitconfig here: git checked out 108 files LF in the same second in the same tree, and `git check-attr` reports `eol: lf`. **Nor was the source CRLF and the copy faithful**: the source `CLAUDE.md` is LF with an mtime three weeks older than any of the CRLF copies. A byte-preserving copy *does* also happen — `.claude/settings.local.json` carries the source's mtime to the microsecond in every worktree, LF ones included — which is why the presence of that gitignored file is **not** evidence of the text-mode copy and is not offered here as any.

### Why it could not be left

- **The flow requires a green `tools/lint.py` before committing**, and a session that had changed nothing had no way to tell this red from one it had caused. [D-186](D-186-2026-08-25-windows-text-mode-defaults.md)'s ruling 5 anticipated CRLF on disk here and told sessions to notice the ` M`-against-empty-diff symptom and move on — `AGENTS.md`'s wording. It did not anticipate a red guard, which is not something a session moves on from. #224 records five steps spent diagnosing it, and [#162](https://github.com/Grimblaz-and-Friends/tradecraft/issues/162) four on the same family of cause.
- **The command the finding named did not close it.** `python tools/roster.py --write` rewrote the nine entries LF and the lint went green, but git recorded nothing because the index already held LF — so the repair left no trace in any diff, and the next worktree started red again.

**What `git status` reports, precisely, because the first draft of this entry got it wrong.** In the worktree this change was built in it reported nothing — but that tree's index stat cache had already been rewritten by a staging pass, and the cache holds the CRLF sizes. In a tree whose entries are CRLF and whose cache holds the LF sizes, `git status` reports ` M` on all nine and `git update-index --refresh` will not clear it, because CRLF changes the file size and git re-reads on a size mismatch regardless of mtime; a single `git add -A` stages nothing and makes it clean permanently. Both observations are real and the entry names the tree rather than generalising. The ` M` case is exactly the symptom `AGENTS.md` already describes, so that sentence stands.

There was a second red beside the first, which #224 did not record: `tools/tests/test_roster.py::test_this_repository_carries_a_roster_for_every_cell` asserted both `roster.verify(ROOT) == []` and `b"\r" not in entry.read_bytes()` against the on-disk tree, and both were false there.

## Decision

**1. `matches()` compares with `\r\n` normalised, and both call sites go through it.** `roster.verify` and `roster.write` share it, so the guard and the writer keep the one definition `expected()` already exists to hold.

The warrant is not that line endings do not matter. It is that **a newline difference at this site is normally invisible to the repository and cannot be repaired in the tree it appears in.** `.gitattributes` normalises the entry to LF on the way into the index; and the CRLF is written by a copy no command here performs, so re-running the writer clears one working tree and the next one starts over. Reporting it was a finding with no lawful response, on a tree nobody had touched — and a guard that reds a tree nobody can fix is a guard somebody deletes, which the suite's own lawful-polarity test already says in as many words.

**The invisibility has a bound, and it is not decorative.** Git's `text=auto` refuses to normalise **any file containing a lone carriage return** — one bare `\r` anywhere disables the conversion for that whole file, and every CRLF in it is then committed verbatim. So "a CRLF entry and its LF twin are the same commit" is true only while neither carries a lone CR. This is not hypothetical: **this change's own first draft committed two literal control bytes into this entry's index row**, which is how the bound was found, and a repository-wide scan of all 118 tracked blobs found that file the only CR-bearing one. A roster entry in that composition would be forgiven by `matches()` and recorded by git — where the pre-change byte comparison fired and `--write` repaired it. That exposure is real, it is not closed here, and it is filed rather than papered over.

**2. Both sides are normalised, not only the entry on disk.** `want` is built from a cell git checks out LF, so today only the entry side can arrive CRLF from the harness copy. Normalising one side would make an unclearable red possible the moment a cell arrived CRLF too: the entry would normalise, `want` would not, `--write` would write `want`, and the re-verify would fail again. The symmetric form stays self-consistent whatever either side carries. The cost of the symmetry is nothing; the cost of the asymmetry is a red the one named command cannot clear, which is the defect this entry exists to close, rebuilt one layer down.

**3. `\r\n` only, never a lone `\r`.** That pair is what a Windows text-mode write produces and what was observed. A bare carriage return is not a line ending anything here emits, so an entry carrying one is corrupt rather than copied, and forgiving it would silently accept the corruption. Pinned by a **pair** of fixtures, which is the only way it can be pinned: a stray `\r` inside an otherwise-CRLF entry discriminates against "strip every carriage return", and an all-CR entry discriminates against "treat a lone `\r` as a line ending". Either fixture alone leaves one of those two mutants alive, and the first version of this change shipped only the first and claimed the bound was pinned.

**4. The tree-level test stops asserting the entries are LF on disk.** That assertion was the wrong instrument for what it wanted. What the generator writes is pinned deterministically in `tmp_path` by `test_the_generator_introduces_no_carriage_return_of_its_own`, where no later copy can move it; asserting it again against the working tree asserted a property of whatever produced that tree, which is not this repository. The residual is that nothing now checks the *committed* roster is LF, and `tools/lint.py` has no carriage-return check at all — routed, with the guard in ruling 1's bound.

**5. The substrate cell's third text-mode rule is not amended, and neither is `AGENTS.md`.** The rule says a file that will later be compared, restored or measured is *written and read as bytes*; `roster.write` still writes bytes and still has its guard. What this decision separates is the **write** half from the **compare** half, at one site where the file leaves this repository's control between the two. That is a bound on the rule's reach rather than a change to it, and it is stated in `tools/roster.py`'s module docstring — under the heading *"Written as bytes, compared as text"* — which then routes a reader down to `matches()` for the warrant.

No always-on surface is edited here, so no outflow is owed. [D-184]

## The exposure #224 asked about

The filing deferred *whether anything else the two-zone layout tracks under `.claude/` has the same exposure*. **It does not** — and the enumeration that establishes it is not the one this entry first gave.

`git ls-files .claude` returns the nine roster entries and nothing else. Tracing every read of them during one lint run — by patching `Path.read_bytes` and `read_text` and running `lint.main()` — the readers are `roster.expected`, `roster.verify`, `lint._read_text`, `tools/figures.py:read`, and `lint.check_doctrine`. **Only `roster` compares them**; every other reader either counts characters or matches text, and each normalises newlines already. So the answer is right and the `lib/`-helper rejection stands.

The first draft claimed *"exactly two things consume them"*, naming `_normalized_chars` in `skills/authoring/scripts/figures.py` as the sibling that reached for the same move first. **That was wrong in both directions.** `_normalized_chars` reads a roster entry in no run this repository performs — its only caller is `figure_delta`, whose `PROSE_PATHS` do not include `.claude` — and the readers that do were invisible to a census scoped to `read_bytes()` calls, one of which (`lint._read_text`) is a `read_bytes()` call the stated method should have found. The predicate `_normalized_chars` uses is still the same move for the same reason; it is simply not the sibling at this site.

## What was rejected

- **Reporting a line-ending-only mismatch as its own finding, or as a note.** It leaves the check red on a clean tree, which is the defect. There is no action a session can take that clears it durably, and a finding naming a fix that does not fix is worse than silence.
- **Fixing the copy.** Outside this repository — the harness writes those ten files, and git writes the other 108 in the same second.
- **A checked-in normalisation.** `.gitattributes` already does everything git can do here; the index was already LF throughout, which is why `git diff` was empty and the red looked like a real defect.
- **A shared helper in `lib/`.** One byte-identity comparison against a `.claude/` file exists. A shipped module for a single repo-only caller buys a plugin version bump and no second consumer.

## What the change's own review turned up

- **Five of five seats reported the recorded cause as false, and all five were wrong for one shared reason** — every seat ran in an `agent-*` worktree, the population the copy does not reach. The defense found `CLAUDE.md` and inverted the finding. The lesson is in ruling 1's scope sentence and in the census above: a claim about *what a harness does* needs the population it was measured over stated with it, or the next reader's own tree becomes a counterexample.
- **The first draft committed the only carriage-return bytes in the repository**, into this entry's own index row, in a sentence about carriage returns — because the row was written through a Python script whose `\r` escapes became control characters. `check_decision_index` reads with universal newlines and its regex still matched the truncated line, so the lint was green over a table row split in two with an empty code span where the bound should read. The class is routed as a lint check.
- **Two of the change's four original mutation pins did not discriminate.** Running the mutants rather than reading the tests caught it before review; the review then caught that the *replacement* fixture killed a different mutant than the one it replaced, leaving the lone-`\r` bound unpinned while the commit message published a matrix reading as full coverage. Ruling 3 now carries the pair.
- **`frontmatter()`'s raw-byte slice is line-ending-blind**, so a cell CRLF'd *after* its entry was generated produces a `want` that has lost a blank line — a false out-of-step finding whose named command then commits a real content change that reds Linux CI. Pre-existing and unchanged here; filed. Three docstrings in the first draft asserted the shape was unreachable or pinned, and only the both-CRLF composition was.

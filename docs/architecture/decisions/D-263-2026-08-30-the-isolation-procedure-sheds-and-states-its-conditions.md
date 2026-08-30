# D-263: The isolation procedure leaves the always-on body and states the conditions it carries; the isolation rule gains a second direction

**Status:** Accepted 2026-08-30 (PR #263)

## Context

Five issues, one file. [#183](https://github.com/Grimblaz-and-Friends/tradecraft/issues/183), [#212](https://github.com/Grimblaz-and-Friends/tradecraft/issues/212), [#213](https://github.com/Grimblaz-and-Friends/tradecraft/issues/213) and [#238](https://github.com/Grimblaz-and-Friends/tradecraft/issues/238) are the `experience-session` cell's tree-building and isolation paragraph and the fence it carries; [#227](https://github.com/Grimblaz-and-Friends/tradecraft/issues/227) is the `When one fires` section three paragraphs above it. They landed on one settled [pre-implementation artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/183#issuecomment-5470781889), affirmed as drafted.

**Why one change.** The scarcity is shared and it is one paragraph, not one budget: four of the five rewrite the same prose, and each issue names the others as a candidate for a single pass. Split, the second pull request rebases onto a paragraph the first replaced, and each of the four pays its own plugin version bump and its own experience session for the same material.

**The filings' premises were re-derived, not inherited.** Each of #183's four conditions was reproduced on a throwaway repository before it was written about, and #212's falsified sentence was reproduced by building the tree it describes. The commands and their results are in the pull request; one of them was found by hitting it — the fence's tar caveat fired during this work, which is how `--force-local` came to be named.

## 1. The procedure sheds to `skills/experience-session/references/isolation.md`; the rule it serves stays

The cell's body carried a git fence and its caveats. **The split is between the rule and the procedure**: the isolation rule binds every dispatch, and the tree-building procedure binds only a dispatch that needs a repository tree.

The `authoring` cell's test is a disqualifier rather than a size — a cell is too big when a session loads prose it had no use for. This cell's most frequent firing is the `When one fires` consult, which asks whether a change buys a session at all and paid for a git fence to answer. That firing is why the shed is the right move independently of what the four issues add; the room it buys is why four answers fit without accretion.

**The alternative was to keep it in the body and accept the growth.** It was rejected on the disqualifier, not on the character count: this cell is unbudgeted in `tools/lint.py`'s map on purpose, so no ceiling forced anything. `python tools/figures.py --cell skills/experience-session/SKILL.md` reports the body and the cell total on whatever tree it runs on, and a body cap is dodgeable by moving prose one directory down, which is exactly what this change does — the figure to read is the total, which grew.

## 2. The dispatcher's check is re-aimed from the command to the extracted tree

`git archive` honours the `.gitattributes` of the tree it archives. `export-subst` expands `$Format:` placeholders inside the copied files, so a file carrying the subject placeholder arrives stamped with the commit's subject — and a fix batch's subject routinely says outright what is under test. `export-ignore` omits a path the pathspec names, and says nothing.

**Neither is set in this repository and both are live for an adopter**, version-stamping being a common reason to set the first. That asymmetry is the whole reason this is prose in a shipped cell rather than a guard in `tools/`: a guard here would defend a repository that has the condition turned off, and would not travel to the ones that do not.

**The remedy is one check, not two conditions and two checks.** The cell already had the dispatcher confirm the tree carried the material; it now has the dispatcher inspect the extracted tree — that it holds the material, that nothing in it states what is under test, and that no path named is missing. A leak reads as text naming the change; a drop reads as a path asked for and absent. **One inspection covers both attributes and covers a build step that went wrong for a reason nobody has thought of yet**, which enumerating attributes would not.

**A different copy mechanism was considered and not taken.** The filing left it open. Nothing off the shelf gives a history-free copy of an arbitrary commit while ignoring export attributes, and the inspection is owed anyway — the dispatcher already had to look at the tree for other reasons.

## 3. The fence quotes its paths and sets an identity

Two of #183's conditions are fence defects with no design content: the placeholders were unquoted, so a substituted `<outside>` holding a space split into several arguments, and `git init` leaves a repository with no author identity, so a consumer the cell explicitly tells it may commit dies on `Author identity unknown` wherever no global identity is configured. This machine has one, which is why the procedure had never failed here.

Both are fixed in the fence itself. The identity is `consumer` / `consumer@invalid`, chosen to say nothing about the change — the fence is inside the isolation, and a name derived from the branch or the batch would be a leak of the kind section 2 exists to catch.

**`--force-local` is named.** The cell already warned that GNU tar reads a leading drive letter as a remote host, and told the reader to spell the path in the form their tar accepts. That is a description of the failure without its remedy; the remedy is now stated alongside the error text a reader will actually see.

## 4. The roster is all-or-nothing, which relaxes "only the paths the job needs"

The sentence [#199](https://github.com/Grimblaz-and-Friends/tradecraft/issues/199) falsified said an archived tree carries cell files but not the description roster, and told a dispatcher wanting descriptions to move the cells into `.claude/skills/`. Since PR #210 made that directory tracked, an archive naming it carries the roster, and the prescribed hand-copy reds the lint nine ways with a remedy that then deletes what was copied.

**The replacement is not another route; it is naming the right paths.** An archive carries only what the pathspec names, so a run that must exercise triggers names the loading surface together with the cells it points at.

**The load-bearing fact is that the roster entries are pointers.** Each entry carries the cell's frontmatter over a body that points at `skills/<name>/SKILL.md`. Naming the surface alone therefore hands a consumer nine descriptions whose every pointer dead-ends — verified both ways on this tree before the prose was written. **So the cell now states one case where the tree carries more than the job needs**, and states the reason, because the previous instruction read as forbidding it.

The third failure mode the filing named — a dispatcher enumerating "the paths the job needs" having no reason to list a loading surface, and silently producing the pre-#199 condition inside the instrument built to detect it — is answered by the same sentence naming the surface explicitly.

## 5. The isolation rule gains its second direction

[#174](https://github.com/Grimblaz-and-Friends/tradecraft/issues/174) closed this shape for the tree and produced the `git archive` procedure. The rule that resulted governs what may **leave** the isolation and is silent on what may be **read into** it, so a consumer holding a network and the repository's name can fetch the pull request that states what is under test. One did, on PR #210's fourth session, and volunteered it.

**The remedy is prose, and the mechanical alternative was rejected with a reason.** Dispatching without network or credentials is not available in the lanes these runs use, and would break any job whose success genuinely needs the network — which the cell elsewhere goes out of its way to keep runnable. So: the dispatch says to work from the tree, and the account asked for at the end names what the run consulted.

**The detection is the part that matters.** This leak surfaced only because a consumer was asked an open question and volunteered its sources. A rule with no way of firing would be a rule that reads as closed; obliging the end-of-job account to name what was consulted is what makes the next breach visible, and it costs a clause in a report the cell already asks for.

**Searching the board for the job's own sake stays lawful**, which the filing raised: `filing`'s search step is a legitimate job, and what is out of bounds is the change's own record rather than the board.

## 6. #227 is a wording repair, and the rule is unchanged

The cell held that mechanical work owes nothing at all, that a record-only fix batch is that case, and — three sentences later — that *"Declining costs one line, and always will."* A cold consumer read the paragraph three times and wrote both answers down.

**Read precisely, the clauses were already consistent**: the declining sentence's own condition is *where a change bought a session and none ran*, and mechanical work buys none. What failed was the reading, and `and always will` is why — an absolute tacked to a conditional scans as overriding the sentence above it.

**So the precondition becomes the sentence's subject** and the absolute goes. **Picking a new default was rejected**: it would be a rule change nobody's evidence asked for, and #227's evidence is a reader's difficulty, not a wrong outcome. The `authoring` standard is the ground — where a competent reader genuinely could go wrong, restate the sentence plainly rather than append a qualifier — and that is what distinguishes this from armoring, which the same standard forbids.

## 7. A code job is told which steps it cannot take

The cell mandates a tree with no remote and forbids acts against the live board; `AGENTS.md` mandates a flow that branches, publishes, opens a pull request and comments on an issue. A consumer given a code job meets both and spends a step deciding which to drop. The one on PR #232 resolved it well and flagged it; the cost is the instrument's noise floor, and a consumer resolving it badly returns a note about the doctrine rather than about the change.

**The cell gives, not the doctrine.** The three options were an explicit suspension in the dispatch, a statement in the cell that the isolation suspends those steps, or scoping the flow in `AGENTS.md`. The third touches the always-on surface, which the admission order puts last and which has little headroom; the first two are cheap and are where the condition is created. Both landed — the reference says the dispatch says it, which is the cell instructing the dispatcher rather than the doctrine changing.

**The leak question the filing turned on is answered rather than left.** A dispatch line about the flow names the doctrine, which is harmless where the doctrine is not itself what is under test; where it is, the run gets the throwaway remote and scratch board the cell already provides, and the dispatch says nothing. That escape hatch existed already and is now load-bearing.

**It is scoped to code jobs by construction** — the material lives in the tree-building reference, and a job needing no repository never loads it, which is the filing's third question.

## 8. What was left open

- **#183's fifth item is not taken.** Whether the cell should say that `.claude/skills/` isolates the repository's cells without isolating the host's personal skills directory is a fact about a runtime rather than about the procedure, and no run has produced friction from it.
- **No guard was added for any of this.** The admission order puts a mechanism first, and section 2 records why one is wrong here specifically: the archive conditions are off in this repository and on in an adopter's. The other four are prose about what a dispatcher tells a consumer, which nothing here can check.
- **#223 and #198 are untouched**, and were named out of scope in the affirmed boundary: the first is `adversarial-review`'s file, the second is repo-only tooling.
- **The `--force-local` remedy is stated for GNU tar and is not a portability claim** about every tar on every `PATH`; the surrounding sentence still tells the reader to spell the path in the form their own tar accepts.

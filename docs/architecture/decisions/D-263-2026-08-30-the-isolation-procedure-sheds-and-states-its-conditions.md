# D-263: The isolation procedure leaves the always-on body and states the conditions it carries; the isolation rule gains a second direction

**Status:** Accepted 2026-08-30 (PR #263)

## Context

Five issues, one file. [#183](https://github.com/Grimblaz-and-Friends/tradecraft/issues/183), [#212](https://github.com/Grimblaz-and-Friends/tradecraft/issues/212), [#213](https://github.com/Grimblaz-and-Friends/tradecraft/issues/213) and [#238](https://github.com/Grimblaz-and-Friends/tradecraft/issues/238) are the `experience-session` cell's tree-building and isolation paragraph and the fence it carries; [#227](https://github.com/Grimblaz-and-Friends/tradecraft/issues/227) is the `When one fires` section three paragraphs above it. They landed on one settled [pre-implementation artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/183#issuecomment-5470781889), affirmed as drafted.

**Why one change.** The scarcity is shared and it is one paragraph, not one budget: four of the five rewrite the same prose, and each issue names the others as a candidate for a single pass. Split, the second pull request rebases onto a paragraph the first replaced, and each of the four pays its own plugin version bump and its own experience session for the same material.

**The filings' premises were re-derived, not inherited.** Each of #183's four conditions was reproduced on a throwaway repository before it was written about, and #212's falsified sentence was reproduced by building the tree it describes. The commands and their results are in the pull request; one of them was found by hitting it — the fence's tar caveat fired during this work, which is how `--force-local` came to be named.

## 1. The procedure sheds to `skills/experience-session/references/isolation.md`; the rule it serves stays

The cell's body carried a git fence and its caveats. **The split is between the rule and the procedure**: the isolation rule binds every dispatch, and the tree-building procedure binds only a dispatch that needs a repository tree.

The `authoring` cell's test is a disqualifier rather than a size — a cell is too big when a session loads prose it had no use for. The `When one fires` consult, which asks only whether a change buys a session, paid for a git fence to answer that; nothing here measures how often each firing happens, so the ground is that this firing needs none of the procedure rather than that it is the commonest.

**The shed bought no headroom, and this entry first claimed it did.** The body ends within a few characters of where it began, because roughly as many characters of new always-on rule arrived as the fence's text left, while the total grew by more than a third. What the consult no longer loads is a procedure it had no use for; what it loads instead is rules that bind it. That is a better trade than the word *room* describes, and it is not the same trade.

**The alternative was to keep it in the body and accept the growth.** It was rejected on the disqualifier, not on the character count: this cell is unbudgeted in `tools/lint.py`'s map on purpose, so no ceiling forced anything. `python tools/figures.py --cell skills/experience-session/SKILL.md --cell-budget N` reports the body and the cell total on whatever tree it runs on. The flag is required and its value is the caller's: for a cell absent from the budget map any value is accepted, so the headroom it prints means nothing here and the total is what to read. A body cap is dodgeable by moving prose one directory down, which is exactly what this change does — the figure to read is the total, which grew.

## 2. The dispatcher's check is re-aimed from the command to the extracted tree

`git archive` honours the `.gitattributes` of the tree it archives. `export-subst` expands `$Format:` placeholders inside the copied files, so a file carrying the subject placeholder arrives stamped with the commit's subject — and a fix batch's subject routinely says outright what is under test. `export-ignore` omits a path the pathspec names, and says nothing.

**Neither is set in this repository and both are live for an adopter**, version-stamping being a common reason to set the first. That asymmetry is the whole reason this is prose in a shipped cell rather than a guard in `tools/`: a guard here would defend a repository that has the condition turned off, and would not travel to the ones that do not.

**The remedy is one check, not two conditions and two checks.** The cell already had the dispatcher confirm the tree carried the material; it now has the dispatcher inspect the extracted tree — that it holds the material, that nothing in it states what is under test, and that no path named is missing. A leak reads as text naming the change; a drop reads as a path asked for and absent. **One inspection covers both attributes and covers a build step that went wrong for a reason nobody has thought of yet**, which enumerating attributes would not.

**A different copy mechanism was considered and not taken.** The filing left it open, and this entry first said no route existed. One does: `git read-tree` into a temporary index followed by `git checkout-index` yields a history-free copy of an arbitrary commit and ignores both attributes, path-restricted or whole, probed twice in this change's review. **It was rejected on its failure mode rather than its absence** — a pathspec matching nothing exits 0 and delivers an empty tree where `git archive` is fatal, so adopting it would trade a loud failure for a silent one inside a procedure whose whole defect class is silent failure. The inspection is owed either way.

## 3. The fence quotes its paths and sets an identity

Two of #183's conditions are fence defects with no design content: the placeholders were unquoted, so a substituted `<outside>` holding a space split into several arguments, and `git init` leaves a repository with no author identity, so a consumer the cell explicitly tells it may commit dies on `Author identity unknown` wherever no global identity is configured. This machine has one, which is why the procedure had never failed here.

Both are fixed in the fence itself. The identity is `consumer` / `consumer@invalid`, chosen to say nothing about the change — the fence is inside the isolation, and a name derived from the branch or the batch would be a leak of the kind section 2 exists to catch.

**`--force-local` is named, and scoped where the reader meets it.** The cell warned that GNU tar reads a leading drive letter as a remote host and left the reader to find the remedy. Naming it alone would have been worse than silence: bsdtar — what `tar` resolves to in Windows PowerShell, on this repository's own primary platform — takes the drive letter unaided and **rejects the flag**, exiting 1 with nothing extracted, which this change's review found by running it. So the reference states both tars and which needs which, rather than one tar's remedy as though it were the remedy.

## 4. The roster is all-or-nothing, which relaxes "only the paths the job needs"

The sentence [#199](https://github.com/Grimblaz-and-Friends/tradecraft/issues/199) falsified said an archived tree carries cell files but not the description roster, and told a dispatcher wanting descriptions to move the cells into `.claude/skills/`. Since PR #210 made that directory tracked, an archive naming it carries the roster, and the route the sentence prescribed reds the lint with a remedy that then deletes what was put there. **No count is stated here**: it moves with the tree and with which operation is performed, and the sentence prescribed *move* while the number that circulated belonged to *copy*. `python tools/lint.py` after each, on whatever tree you are on, is the derivation — three stages of this change's review measured three different numbers for the one sentence.

**The replacement is not another route; it is naming the right paths.** An archive carries only what the pathspec names, so a run that must exercise triggers names the loading surface together with the cells it points at.

**The load-bearing fact is that the roster entries are pointers.** Each entry carries the cell's frontmatter over a body that points at `skills/<name>/SKILL.md`. Naming the surface alone therefore hands a consumer nine descriptions whose every pointer dead-ends — verified both ways on this tree before the prose was written. **So the cell now states one case where the tree carries more than the job needs**, and states the reason, because the previous instruction read as forbidding it.

The third failure mode the filing named — a dispatcher enumerating "the paths the job needs" having no reason to list a loading surface, and silently producing the pre-#199 condition inside the instrument built to detect it — is answered by the same sentence naming the surface explicitly.

## 5. The isolation rule gains its second direction

[#174](https://github.com/Grimblaz-and-Friends/tradecraft/issues/174) closed this shape for the tree and produced the `git archive` procedure. The rule that resulted governs what may **leave** the isolation and is silent on what may be **read into** it, so a consumer holding a network and the repository's name can fetch the pull request that states what is under test. One did, on PR #210's fourth session, and volunteered it.

**The remedy is prose, and the mechanical alternative was rejected with a reason.** Dispatching without network or credentials is not available in the lanes these runs use, and would break any job whose success genuinely needs the network — which the cell elsewhere goes out of its way to keep runnable. So: the dispatch says to work from the tree, and the account asked for at the end names what the run consulted.

**The detection is the part that matters.** This leak surfaced only because a consumer was asked an open question and volunteered its sources. A rule with no way of firing would be a rule that reads as closed; obliging the end-of-job account to name what was consulted is what makes the next breach visible, and it costs a clause in a report the cell already asks for.

**Searching the board for the job's own sake stays lawful**, which the filing raised: `filing`'s search step is a legitimate job, and what is out of bounds is the change's own record rather than the board.

## 6. #227 is a wording repair, and the rule is unchanged

The cell held that mechanical work owes nothing at all, that a record-only fix batch is that case, and — three sentences later — that *"Declining costs one line, and always will."* (`skills/experience-session/SKILL.md` at `76b29e3`) A cold consumer read the paragraph three times and wrote both answers down.

**Read precisely, the clauses were already consistent**: the declining sentence's own condition is *where a change bought a session and none ran*, and mechanical work buys none. What failed was the reading, and `and always will` is why — an absolute tacked to a conditional scans as overriding the sentence above it.

**A cold A/B was run on this section rather than reasoned about** ([spike report](https://github.com/Grimblaz-and-Friends/tradecraft/issues/183#issuecomment-5471477611)), three seats given only the section text and the record-only-fix-batch situation, each asked for its verdict, its confidence, how many passes it needed, and what fought it: seat A on the pre-change text, seat B on the text with the declining clause repaired, seat C on the text with a second clause narrowed. **All three answered `NOTHING IS OWED` at high confidence in two passes** — which is the affirmed criterion's bar of one pass **not met**, the answer itself being unanimous and confident. What moved was only the friction each named — A named `and always will` and the unqualified *a fix batch is itself a change to how a later session must work* (both at `76b29e3`); B named only the second; C named neither.

**So the second clause was narrowed on that evidence**, to *a fix batch that rewrote what the material instructs*, which is what the paragraph's own rule already says and what its final sentence concludes. Both A and B reported that the unqualified form reads as the opposite of the carve-out four sentences below it.

**What the A/B does not show is that any of this made the rule easier to apply.** Verdict, confidence and pass count are identical across all three seats, and seat C named two fresh frictions — the paragraph stating its rule before its exception, and `is the mechanical case above` being a backward cross-reference. **That regress is where this stopped, and the stop is recorded rather than filed**: chasing it costs either a restructure of a paragraph whose rule is not in dispute, or inlining the mechanical category into a second place, which the `authoring` cell forbids. The warrant for stopping is the three matching verdicts — #227's evidence was a consumer that wrote *both* answers down, and no seat here did.

**So the precondition becomes the sentence's subject** and the absolute goes. **Picking a new default was rejected**: it would be a rule change nobody's evidence asked for, and #227's evidence is a reader's difficulty, not a wrong outcome. The `authoring` standard is the ground — where a competent reader genuinely could go wrong, restate the sentence plainly rather than append a qualifier — and that is what distinguishes this from armoring, which the same standard forbids.

## 7. A code job is told which steps it cannot take

The cell mandates a tree with no remote and forbids acts against the live board; `AGENTS.md` mandates a flow that branches, publishes, opens a pull request and comments on an issue. A consumer given a code job meets both and spends a step deciding which to drop. The one on PR #232 resolved it well and flagged it; the cost is the instrument's noise floor, and a consumer resolving it badly returns a note about the doctrine rather than about the change.

**The cell gives, not the doctrine.** The three options were an explicit suspension in the dispatch, a statement in the cell that the isolation suspends those steps, or scoping the flow in `AGENTS.md`. The third touches the always-on surface, which the admission order puts last and which has little headroom; the first two are cheap and are where the condition is created. Both landed — the reference says the dispatch says it, which is the cell instructing the dispatcher rather than the doctrine changing.

**The leak question the filing turned on is answered rather than left.** A dispatch line about the flow names the doctrine, which is harmless where the doctrine is not itself what is under test; where it is, the run gets the throwaway remote and scratch board the cell already provides, and the dispatch says nothing. That escape hatch existed already and is now load-bearing.

**This change's own experience session reports the first form of that remedy did not work, and the reference was rewritten because of it.** The dispatch carried exactly what the reference then prescribed — the tree has no remote, the steps leaving it are not the job — and the consumer still spent a step, because its difficulty was **convergence**: an artifact owed on an issue *before the first commit*, which is not a step that leaves the isolation the way pushing does, and which an enumeration of publish steps does not reach. It named a second obligation the enumeration missed entirely — a decline has nowhere to be recorded in a tree with no board — and its own cold seat hit that one independently. So the reference states the general form instead: every obligation needing a remote or a board, including those owed before a commit and those with nowhere to land. Affirmed criterion 5 is **not met** by the form this section originally landed.

**It is scoped to code jobs by construction** — the material lives in the tree-building reference, and a job needing no repository never loads it, which is the filing's third question.

## 8. What was left open

- **#183's fifth item is not taken.** Whether the cell should say that `.claude/skills/` isolates the repository's cells without isolating the host's personal skills directory is a fact about a runtime rather than about the procedure, and no run has produced friction from it.
- **No guard was added for any of this.** The admission order puts a mechanism first, and section 2 records why one is wrong here specifically: the archive conditions are off in this repository and on in an adopter's. The other four are prose about what a dispatcher tells a consumer, which nothing here can check.
- **#223 and #198 are untouched**, and were named out of scope in the affirmed boundary: the first is `adversarial-review`'s file, the second is repo-only tooling.
- **Whether `AGENTS.md` should scope its own flow to a tree with a remote is filed rather than answered.** This entry rejected that option on always-on cost, and the experience session is evidence the rejected option addressed the friction a consumer actually hit. The affirmed boundary bars the edit, not the issue.
- **What a revealed read-back breach does to the run** — void, rerun, or recorded — is filed. Section 5's rule detects and stops there, and settling the disposition inside this change would decide a rule it did not set out to decide.
- **`--force-local` is a per-tar remedy and is stated as one.** What is not claimed is that the two tars named exhaust what a reader's `PATH` may hold.

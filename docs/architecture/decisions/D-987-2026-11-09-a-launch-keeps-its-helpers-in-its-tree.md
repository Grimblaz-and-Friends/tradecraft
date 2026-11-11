# D-987 — A launch keeps its helpers in its tree

**Purpose:** record why #963 refuses a launched author's or builder's helper its own working copy, and compares each covered repository's working copies and branches, holding only on those the run's own record names, and what was chosen over what. **Audience:** a future session changing the launch's helper guard, its own instruction file, or the comparison's refs items. **Success:** that reader can recover what was chosen over what without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/963#issuecomment-6749180999) governs. Its pre-implementation artifact was [settled on the cap route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/963#issuecomment-6750846058). The lane is ordinary / connected, and no panel was bought.

## Rows and their reasons

- **Row 1, tell and block.** The owner's global instructions tell every session to give a file-editing helper its own working copy, and the runtime puts that copy under the main checkout, outside the launch's write bound ([D-939](D-939-2026-11-03-claude-launch-writes-stay-in-their-tree.md)). An instruction alone competes with that rule and can lose; a refusal alone leaves the recipient guessing. The owner ruled "Tell and block". A refused call still costs the launch its return until #962 lands, so the instruction is what keeps refusals rare.
- **Row 2, compare copies and branches, and hold only the named ones.** The pre-tool check can't stop a copy made from the shell, and the tree walk stops at every nested copy, so nothing saw the copies, branches and commits three incidents left. The run's record logs every helper's shell commands, and in each incident it named the copy. The owner ruled "Tied ones hold": holding on every new copy would also hold on the sessions and helper copies others start during a long build.
- **Row 3, report and never remove.** A copy can hold the only record of a helper's work, and a branch may belong to another session; removing either can't be undone, so cleanup is the owner's.

## Calls made inside the rows

- **C1. The rule travels in the launch's own instruction file, written for every Claude launch,** not only for a tree whose rules live in `AGENTS.md` ([D-911](D-911-2026-10-13-claude-builders-load-their-tree-instructions.md)). A prompt line reaches only a prompt the entrance composed; the file reaches every launch, including one whose dispatch the holder wrote, through the same `--add-dir` channel as the global rule it competes with.
- **C2. Every `isolation` value is refused,** because each asks for a copy other than the launch's tree.
- **C3. An agent type is allowed only when known safe.** A definition's `isolation` can't be seen in the call, and a lookup with gaps would let an isolating type through; a definition the guard can't read with certainty refuses, and is read before the launch starts so it fails there. The built-in list comes from a live launch on Claude Code 2.1.280 that called each offered type and saw no copy appear; a later type is refused until confirmed.
- **C4. `EnterWorktree` is always refused,** including with a path to an existing copy, where the file guard would refuse every edit anyway.
- **C5. Every covered repository is compared, the run's own included,** and only the copy at the run's root and its checked-out branch are its own, because a linked copy the run makes can lie outside its root.
- **C6. A branch checked out at a changed copy is folded into that copy's entry,** so one account entry covers both and either name holds it.
- **C7. Naming reads every string in every tool call's input, by the recipient or a helper, never tool results.** Relative paths resolve against every directory the calling agent named. This can hold more often than tracking the shell's exact directory would, never less; text written into files counts too, so a common branch word or `..` in file content can hold. Quoted and escaped paths are read whole, and a branch also counts as named when it is the last part of a named path, as `git worktree add ../x` makes branch `x`.
- **C8. The default branch never holds,** even when the record can't be read: nearly every record names it and other sessions move it. It is the remote's `HEAD`; a repository with no remote uses its main copy's branch; and where a remote has no `HEAD` none is identified, because the main copy may hold a feature branch, and exempting it would let a named change go unheld.
- **C9. A refs comparison needs the run's record.** Given none, the launch couldn't have compared what its run named, so the comparison as a whole is recorded `unrecorded`; given one it can't read, each entry it found is held, so the holder sees which copies and branches it couldn't clear.

## Rejected

- **Instruction only, or refusal only** (row 1's reason).
- **Holding on every new copy or branch** (row 2's reason).
- **Excluding the run's own repository from the comparison.** A copy it makes outside its root would go unseen.
- **Looking agent types up in only some sources.** An isolating type defined elsewhere would pass.
- **Removing leftovers** (row 3's reason).

## Not this

No fence on the recipient's shell commands (#937), no change to how a refused call is recorded (#962), no hold on the runtime's own plugin bookkeeping (#946), no change to Codex launches, and no removal of copies and branches already left behind.

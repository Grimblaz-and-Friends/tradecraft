# Building the isolated tree

**Loaded when** the run needs a repository tree of its own and you are about to build it. A job that needs no repository does not need this file, and the isolation rule it serves is in the cell.

Build from the change's content without its history, carrying only the paths the job needs and never the change's own record — its decision entry, its index row, its pull request body, the review's reports, whose titles alone can state what is under test.

```
git archive -o "<outside>/tree.tar" <the change's commit> <the paths the job needs>
mkdir "<outside>/consumer"
tar -x -f "<outside>/tree.tar" -C "<outside>/consumer"
git init "<outside>/consumer"
git -C "<outside>/consumer" config user.name consumer
git -C "<outside>/consumer" config user.email consumer@invalid
```

`<outside>` is any directory not under the change's repository, and the quotes are what let it hold a space. `git init` runs whether or not the job commits — git resolves upward, so an un-initialised tree answers the consumer's first `git log` with the branch name and the fix batch's own commit subjects. The identity is set for the same reason the tree is initialised at all: a fresh repository inherits none, so on a machine with no global identity the consumer's first commit dies on `Author identity unknown`, and a job whose success *is* a commit fails for a reason that has nothing to do with the material. Spell the `-f` path in the form the `tar` on your `PATH` accepts — GNU tar reads a leading drive letter as a remote host and answers `Cannot connect to C: resolve failed`; `--force-local` takes it as written. A checkout, a clone, or a worktree hands over that branch name and those subjects outright.

**Two archive attributes can make the tree neither content-complete nor history-free**, because `git archive` honours the `.gitattributes` of the tree it archives. `export-subst` expands `$Format:` placeholders inside the copied files, so a file carrying the subject placeholder arrives stamped with the commit's subject — and a fix batch's subject routinely says outright what is under test. `export-ignore` omits a path from the archive even when the pathspec names it, and says nothing. Neither is set in this repository; both are live for anyone who adopts the practice, and version-stamping is a common reason to set the first. This is why the cell has the dispatcher inspect the extracted tree rather than trust the command that produced it: a leak shows up as text naming the change, and a drop shows up as a path that was asked for and is not there.

**Descriptions load from where the runtime looks, and an archive carries only the paths you name.** Where the run must exercise cells' triggers rather than their bodies, name the loading surface in the pathspec together with the cells it points at — here, `.claude/skills/` and `skills/`. The surface alone hands the consumer a roster whose every pointer dead-ends; neither hands it a tree that tests bodies only, which it does silently, and which is the condition this instrument exists to detect. This is the one case where the tree carries more than the job needs, and the reason is that the roster is all-or-nothing.

**A code job meets the repository's own flow and cannot finish it.** A doctrine prescribing branch, publish, open a pull request and comment on an issue is unsatisfiable in a tree with no remote and no board, and a consumer that meets it spends the run deciding which half to drop rather than on the material. So the dispatch says the tree has no remote and that the steps leaving it are not part of the job. That names the doctrine, which is harmless where the doctrine is not itself what is under test; where it is, say nothing and give the run the throwaway remote and scratch board instead.

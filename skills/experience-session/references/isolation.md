# Building the isolated tree

**Loaded when** a run needs a repository tree of its own and you are about to build it, whichever instrument's run it is. A job that needs no repository does not need this file, and the isolation rule it serves is in the cell whose run it is.

Build from the change's content without its history, carrying the paths the job needs and never the change's own record — its decision entry, its index row, its pull request body, the review's reports, whose titles alone can state what is under test.

**Choose the consumer's mode before naming archive paths.** An adopter-mode tree carries the material as shipped to an adopter and the adopter-visible loading surface needed to reach it. A repository-session-mode tree also carries the repository's ordinary entry surface, its root instructions, and every path either directs that session to for the job. Derive those paths from the repository being used; this reusable reference cannot name one repository's layout. In either mode, exclude the change's own record and record the selected mode and carried entry or loading surfaces in the note, so missing context is not reported as friction in the change.

**Those two rules collide, and where they do the collision is yours to resolve rather than to discover.** A job that runs the repository's own checks usually needs the directory that also holds the change's record. `git archive` takes exclude pathspecs — `':(exclude)<path>'` — so the directory can come without the entry. Expect a residue: an index row, a log, or a generated summary can restate the change while sitting in a file the job needs, and no pathspec separates them. Where that is so, say in the note that the tree carried it, and weigh the run's coldness accordingly. **Neither horn is clean, so pick the one whose noise you can characterise, and look before you dispatch.** An exclude orphans whatever pointed at what you removed, and the check that then fires can name the very file you took out — so run the job's own checks on the extract, read what they print, and keep excluding until they are quiet or you can tell the consumer what to ignore. Omitting the whole directory is usually the worse horn: the failures are many and the consumer cannot tell them from its own breakage.

```
git -C "<the change's repository>" archive -o "<outside>/tree.tar" <the change's commit> <the paths the job needs>
mkdir -p "<outside>/consumer"
tar -x -f "<outside>/tree.tar" -C "<outside>/consumer"
git init "<outside>/consumer"
git -C "<outside>/consumer" config user.name consumer
git -C "<outside>/consumer" config user.email consumer@invalid
git -C "<outside>/consumer" config core.longpaths true
git -C "<outside>/consumer" config core.autocrlf false
git -C "<outside>/consumer" config commit.gpgsign false
git -C "<outside>/consumer" add --all
git -C "<outside>/consumer" commit -m consumer
git -C "<outside>/consumer" checkout --detach HEAD
```

The final three commands make one neutral snapshot and detach `HEAD`. The seat launcher accepts only a detached Git top-level, so the snapshot supplies a commit to detach from and its neutral subject carries no description of the change. Before dispatching, confirm that the commit succeeded, `git rev-list --count HEAD` reports one, and `git symbolic-ref -q HEAD` exits 1.

`<outside>` is any directory not under the change's repository. **Quote every path you substitute in, and quote them one at a time** — that is what lets any of them hold a space, the dispatcher's own repository path as much as the throwaway one. The pathspec placeholder is plural and takes no single pair of quotes: each path in it needs its own.

**The block has no failure gate, so read what it printed.** Each command can run after an earlier failure: a mistyped pathspec makes `git archive` fatal, while initialization and later Git commands can still print output from an empty or incomplete tree. Confirm that the extract is non-empty, that the neutral commit succeeded, that `git rev-list --count HEAD` reports one before the consumer starts, and that `git symbolic-ref -q HEAD` exits 1 before going on.

**Spell the `-f` path in the form your own `tar` accepts, and check which one that is.** GNU tar reads a leading drive letter as a remote host and answers `Cannot connect to C: resolve failed`; `--force-local` makes it accept the path. bsdtar — what `tar` resolves to in Windows PowerShell — takes the drive letter unaided and **rejects `--force-local` outright**, exiting 1 with nothing extracted. So the flag is GNU tar's remedy and is a failure anywhere else; a relative path needs neither.

**`core.longpaths` is set because the consumer's commit fails without it** on Windows at path lengths these runs reach — a throwaway directory named for the job, under a scratch root, is already long, and whether the setting is on is the dispatcher's machine's answer rather than the tree's. The failure lands mid-job on the consumer as `Filename too long`, after the dispatcher's own inspection has passed.

**`core.autocrlf` is disabled because the archive already carries the bytes the consumer should read, and an inherited `true` can rewrite them when Git detaches the neutral commit.** This covers a source with no attributes file as well as one whose attributes leave archived bytes unchanged. It cannot override attributes the source applies while creating the archive: if those attributes request another line ending or working-tree encoding, `git archive` has already emitted different bytes before the consumer's configuration exists.

**The identity and signing settings are set because the fence itself makes the neutral commit, and the consumer may need to commit again as part of the job.** A fresh repository inherits whatever global and system configuration the dispatcher's machine holds — **the isolation is a tree, not a configuration** — so a global `commit.gpgsign` with no usable key can kill the neutral commit on `gpg failed to sign the data`, while a machine with no global identity can kill it on `Author identity unknown`. Give the synthetic identity a name that says nothing about the change. **`git init` still earns its place beyond supplying that commit**: Git resolves upward, so a tree extracted under another repository answers the consumer's Git reads from that enclosing repository. Where `<outside>` is genuinely outside every repository, initialization instead establishes the neutral history the launcher can verify. A checkout, clone, or worktree hands over the change's branch and subjects outright.

**Archive attributes can make the tree neither byte-identical, content-complete nor history-free**, because `git archive` honours the attributes in force for the tree it archives. A text or encoding attribute can transform a committed blob before it reaches the tar file; consumer configuration cannot undo that. `export-subst` expands `$Format:` placeholders inside the copied files: the subject placeholder arrives carrying the commit's subject, and a fix batch's subject routinely says outright what is under test — `%d` yields the branch name, which is what `git init` is here to suppress, and `%b` the body, which is where issue numbers live. `export-ignore` omits a path the pathspec names, and says nothing; with a pathspec naming only an ignored path it exits 0 and produces an empty archive, where a pathspec matching nothing is normally fatal.

**Do not conclude from a clean `.gitattributes` that none is set.** These attributes also fire from `.git/info/attributes`, which is untracked, in no tree, invisible to `git status`, and not carried by a clone. The reassurance a reader can actually check is the weaker one, which is why what follows is a look at the result rather than a look at the configuration.

**The existing checks do not prove byte identity.** `git add` can normalise changed working bytes back to the source blob, so a clean status, a matching tree, one commit, detached `HEAD`, the path listing and the leak search can all pass over altered files. For every regular file the archive carries, compare the committed source blob with the consumer's raw working-file bytes:

```
git -C "<the change's repository>" rev-parse "<the change's commit>:<path>"
git -C "<outside>/consumer" hash-object --no-filters -- "<path>"
```

The two object IDs must match for every file. If they do not, do not dispatch: change how that path is exported so the archive contains the committed blob bytes, because no setting applied after extraction can repair bytes the source's archive attributes already transformed.

**So inspect the extract, and inspect it as an operation.** Listing the tree catches a missing path and nothing else — a leak lives inside a file the dispatcher named and would tick off as present. Read the content: search the extract for the branch name, the issue and pull request numbers, the decision entry's slug, and any word the change is about. **And check paths at the granularity that fails, not the one you typed** — `export-ignore` set below a named directory leaves the named path present and a file under it gone, so comparing the pathspec against the top-level listing passes while material is missing. Compare against what the job needs.

**A tree built from a commit is not a tree built from your working copy.** Where the run is the second session a review's fix batch buys, the fixes have to be committed first: `git archive` has no working-tree mode, so it silently delivers the pre-fix text and the inspection passes, the file being present at the wrong version.

**Descriptions load from where the runtime looks, and an archive carries only the paths you name.** Where the run must exercise cells' triggers rather than their bodies, name the loading surface your runtime reads in the pathspec, together with the cells it points at — those are two paths in a repository whose roster entries point at the cells, and one where the cells sit on the loading surface already. Name a path that does not exist in your tree and `git archive` is fatal, so check before you copy anyone's pair. Getting this wrong has three outcomes and only one is loud: naming a surface whose targets you left out gives a roster whose every pointer dead-ends; naming the cells alone gives a tree that tests bodies only, **silently**, which is the condition this instrument exists to detect; naming nothing that exists fails outright. **The note says which of these the tree was**, because a note from a bodies-only tree otherwise reads exactly like one from a full-roster tree. This is the one case where the tree carries more than the job strictly needs, and the reason is that a roster is all-or-nothing.

**A code job meets the repository's own flow and cannot finish it.** A doctrine prescribing branch, publish, open a pull request and comment on an issue is unsatisfiable in a tree with no remote and no board, and a consumer that meets it spends the run deciding what to drop rather than on the material. **State the general form rather than a list**, because the list is always short: the obligations that fail are every one needing a remote or a board, and they include the ones owed *before* a commit rather than after it — a pre-implementation artifact posted to an issue, an affirmation recorded there — and the ones with nowhere to land, such as a record of something declined. So the dispatch says the tree has no remote and no board, and that nothing requiring either is part of the job. That names the doctrine, which is harmless where the doctrine is not itself what is under test; where it is, say nothing and give the run the throwaway remote and scratch board instead.

# Building the isolated tree

**Loaded when** a run needs a repository tree of its own and you are about to build it, whichever instrument's run it is. A job that needs no repository does not need this file, and the isolation rule it serves is in the cell whose run it is.

Build from the change's committed content without its history, carrying the paths the job needs and never the change's own record — its decision entry, index row, pull request body or review reports, whose titles alone can state what is under test.

**Choose the consumer's mode before naming paths.** The mode determines which loading surfaces the command requires and carries:

| Mode | Required inputs | Included surfaces |
|---|---|---|
| `adopter` | one or more `--loading-surface` values | requested job paths and adopter-visible loading surfaces |
| `repository-session` | `--front-page`, `--root-instructions`, and any repeated `--directed-path` values | requested job paths, front page, root instructions and directed paths |

Derive those repository-specific paths yourself; the reusable command validates and carries the declared mode rather than inventing a layout. Build the tree through the work entrance:

```text
python <plugin-root>/lib/work.py tree \
  --repo OWNER/REPO --issue N --root HOLDER_PATH \
  --mode adopter|repository-session --output OUTSIDE_PATH \
  --path JOB_PATH [--path JOB_PATH ...] MODE-SPECIFIC-OPTIONS
```

Use repeated `--exclude-record` values for record paths or patterns and repeated `--deny-text` values for leak probes. `OUTSIDE_PATH` must not exist and must be outside the registered implementation repository.

The command resolves the registered implementation root and its clean committed revision internally. It archives the declared paths without shell-specific tar behavior, refuses a missing required file or `export-ignore` omission, compares every extracted regular file's raw object id with its committed source blob, and refuses archive transformations such as `export-subst` or line-ending conversion. It then makes one neutral commit in a new repository with no remote and detached `HEAD`, and writes the work identifier, source revision, mode, surfaces, exclusions, file object ids and verification digest to adjacent `.tradecraft-tree.json` metadata rather than into the tree.

The holder's use command names both the job and that metadata:

```text
python <plugin-root>/lib/work.py run use \
  --repo OWNER/REPO --issue N --root HOLDER_PATH \
  --dispatch JOB --tree-metadata OUTSIDE_PATH.tradecraft-tree.json
```

The entrance revalidates the metadata, source revision, raw bytes and neutral detached root before the consumer launches. Altered metadata, a dirty or advanced source, a changed consumer file, a branch, a remote or shared source history refuses the run.

**The record exclusion and context rules can collide, and where they do the collision is yours to resolve rather than to discover.** A job may need a directory that also holds the change's record, while a file the job needs may restate that record. Use exclusions where they leave the job coherent; where content cannot be separated, say in the session note what residue the tree carried and weigh the run's coldness accordingly. Omitting a whole required directory is usually the worse horn because its failures are many and indistinguishable from consumer friction.

**Inspect the result as an operation before dispatching.** Run the job's own checks in the tree, read what they print, and search for the branch name, issue and pull request numbers, decision slug, terms the change is about, and descriptions of the consumer's isolated situation. Keep excluding until the tree is quiet or the job can name unavoidable residue. The command proves the declared paths and bytes; it cannot decide whether an unlisted but meaningful sentence leaks the expected answer.

**A tree built from a commit is not a tree built from the working copy.** Commit a review fix batch before building its second consumer tree, because the archive otherwise delivers the pre-fix content while every structural check still passes.

**Descriptions load from where the runtime looks, and a tree carries only the paths named.** When the run exercises cell triggers rather than bodies, carry the loading surface together with every target it directs the session to. A roster without its targets dead-ends; targets without their loading surface silently test bodies only. The session note says which mode and surfaces the metadata records.

**A code job meets the repository's own flow and cannot finish it.** The neutral tree has no remote or board, so its dispatch says that obligations requiring either are outside the job. Where that doctrine is itself under test, give the run a throwaway remote and scratch board instead of briefing it around the missing surfaces.

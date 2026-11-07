# D-968 — A consumer tree keeps its record elsewhere

**Purpose:** record why #897 moves the entrance's record of a consumer's tree out of the folder around it, for both trees the entrance builds, and what was chosen over what. **Audience:** a future session changing `work.py tree`, `run use`, the cold reader's tree, or where the entrance keeps what it records about a tree. **Success:** that reader can recover what was chosen over what without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/897#issuecomment-6703013576) governs. Its pre-implementation artifact was [settled on the cap route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/897#issuecomment-6703433880). The lane is ordinary / connected, and no panel was bought.

## Rows and their reasons

- **Row 1, the use tree's record leaves the tree's folder.** The entrance wrote its record of a use tree beside the tree, naming the change, the holder's checkout and what was withheld, and an execute-capable use consumer that listed its folder read it (#877's use). `run use` refused a record anywhere else, so the holder couldn't move it.
- **Row 2, `run use` refuses a tree that still has a record beside it.** Trees built before the move would otherwise keep the exposure. Only the entrance's own record is refused, because side-by-side before-and-after trees and job fixtures are lawful layouts.
- **Row 3, `tree` refuses a path whose two nearest folder names carry the change's issue or open pull-request number.** The tree's path appears in every command the consumer runs; Verra #484's trees were built at `D:\t\tree484I1` and Daemon #95's at `...\scratchpad\use95c\tree`. Higher folders are left alone because the runtime usually names them and a session id's random digits would refuse holders by chance.
- **Row 4, the cold reader's tree gets the same,** by the owner's ruling "Both trees". Both trees wrote their record through one helper, so the fix is made there.
- **Row 5, the guidance says the tree's folder belongs to the consumer.** Holders had put notes beside trees, and consumers read them; holder files stay lawful under row 2, so the rule against notes is guidance.

## Calls made inside the rows

- **C1. The record's name is a digest of the tree's resolved path, over a random id.** `run use` must keep proving that a record belongs to the tree it names, which adjacency proved before; a path-derived name keeps that proof with nothing in the tree's folder. The path is compared as the platform compares paths, so Windows' case-insensitive paths match.
- **C2. `tree` replaces a stale record whose tree is gone; the cold reader never replaces one.** A holder who deletes a tree can no longer see its record to delete it too, and a record proves nothing without its tree. A reading's record is evidence the gate reads, and each reading's path is unique.
- **C3. A tree is refused if the entrance's records sit anywhere below its folder, or if it sits inside them.** This is what makes "nothing beside the tree" hold for every tree, including one at `~/tree`; it refuses only outputs placed in the home folder, its parents, or the records.
- **C4. The open pull-request lookup fails closed.** Without it row 3's pull-request check can't be decided. The issue number is checked first, without the network, and only the open class is checked: the row names the open pull request, because an open pull request is the change under test, while a merged one belongs to work already landed, such as an earlier instalment.
- **C5. The cold reader's tree goes in a fresh system temporary folder and is kept after the run.** Row 4 needs it in a folder of its own, outside the records. The gate needs only its record, but readings have always kept their tree, so what the reader saw can still be inspected when a holder disputes a flag.
- **C6. The gate looks for a reading's record in the entrance's records first, then beside its tree,** so readings recorded before the move, held by pull requests open when it lands, keep counting without a migration.
- **C7. `--tree-metadata` and the printed `tree_metadata` keep their names,** because row 1 says holders run `tree` and `run use` as before.

## Made while building

- **One derivation of the entrance's records serves `tree`, `run use` and the cold reader.** In use they are the same folder; a single helper keeps a test or a future caller from splitting them, which would refuse every tree `tree` printed.
- **The record path a holder passes is resolved before it is compared,** so the printed path still matches when passed back relative or with other separators.

## Repaired after the cold reading

- **`tree` refuses an output with the entrance's former record file beside its path, naming it and saying to remove it, and `run use`'s refusal says to remove that file and rebuild.** Row 2 tells the holder to rebuild, and a tree rebuilt at the same path would otherwise meet the same refusal, since the entrance never removes a file it doesn't open.
- **A reading whose record is in neither place is reported at its path in the entrance's records,** where it belongs, rather than beside its tree.

## Answered connected-review findings

- **A sibling tree's former record is refused too.** The lab reviewer found that `tree` and `run use` checked only `<tree>.tradecraft-tree.json`, so a tree rebuilt beside an older sibling tree kept that sibling's record, which names its change, in the consumer's folder. Both now refuse any entrance tree record in the tree's folder, naming it. Tree folders, job fixtures and other files stay lawful, as row 2 requires.

## What this supersedes

[D-726](D-726-2026-09-22-entrance-as-holder-instrument.md) holds consumer trees to "adjacent digest-bound metadata". That clause is superseded: the record now lives in the entrance's records, bound to its tree by a name derived from the tree's path rather than by adjacency. Everything else in D-726's consumer trees, and [D-736](D-736-2026-09-23-truthful-entrance-and-launch.md)'s landed-commit source, stays in force.

## Rejected

- **Keeping the record beside the tree under a less telling name.** Any file in the consumer's folder is read; the name doesn't hide what it holds.
- **Checking every folder in the tree's path for the change's numbers.** The Steward's review of the brief changed row 3 to two folders, for the session-id reason above.
- **Refusing every file beside a use tree.** Job fixtures and comparison trees are lawful layouts (row 2).
- **Migrating existing records or old trees.** Pre-change use trees are rebuilt, which row 2's refusal says, and earlier readings are read where they are (C6).

## Not this

No fence on, or account of, what a consumer reads elsewhere on the machine, such as the entrance's records, session transcripts or GitHub, because its shell has no fence and that is a separate cause. No change to the cold seat's empty tree, which carries no record, and none to how exclusions match directories, which is #739's.

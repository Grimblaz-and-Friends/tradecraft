# Design of the shipped library

**Purpose:** say what the shipped library's mechanisms do now and why, for whoever changes them next. **Audience:** a session or person opening code here that points at one of these sections. **Success:** that reader finds the reasons behind the code here, complete, without the issue that built it or any decision record.

The decision log stays in the practice's own repository and doesn't ship, so this document is where a reader of the library finds the reasons, and each section states its reasons whole. The decisions in force are named by their decision-log ids for a maintainer searching the log; they are not pointers a reader follows. Code added under the code-reasons standard opens with a pointer to its section; existing code is brought in by the repository's catch-up.

## The cold reader

**What it does now.** Once a builder turn exists for a change, `run cold-reader` builds an isolated reading tree from the change set. The tree carries every changed regular file, whatever its contents, and a change holding a file the tree can't carry, such as a symlink, is refused as `cold-reading-tree-refused`, naming the path; for each file the reading covers, the Markdown file each `path#anchor` pointer in it names; and the files linked inside that anchored section. A first reading covers every changed file, and a reread covers only the files it owes, though it still carries the rest for reference. All of it is verified against its committed blobs in one neutral detached commit; the archive ignores the machine's line-ending settings, so any repository builds, while an attribute the repository itself sets that rewrites committed bytes, such as `eol=crlf`, still does and is refused. A tree that names the change's branch is refused before launch, and issue or pull-request numbers in any carried file are counted as residue. One fresh read-only seat, on Claude unless the change names another, reads the tree against the code-reasons standard and returns an account in a fixed form, ending with a capped handful of excerpts it nominates as worth a look. The stage checks only that form, including that each flag names a file the tree carries other than the diff file.

The holder posts the account whole in one `open` comment with its own review against the brief beneath it. In that review it accepts any flag it judges not worth another round, one `Accepted:` line per flag with a one-line reason; an acceptance that names no single flag sets the comment aside. An accepted flag doesn't stand and owes no reread, and a `Can tell: no` can't be accepted. The resumed builder reviews the account and fixes what the holder routed. A later `clean` comment closes the reading. It counts only when posted after the builder's review of the latest `open` reading, or after that `open` itself where the acceptances leave nothing standing or owed, at the current head, with nothing below still owed; on every hold the gate returns, a `clean` posted after the latest `open` is set aside as invalid, while one posted before it closed an older reading and is left alone. Until a current `clean` stands, the entrance's decision holds readiness, use, proof and the release report, and it asks only once the change's floor has passed:

- a reading is current per changed file, by the file's blob and the blobs of the document its pointer names and the files linked inside that section;
- a flag the holder didn't accept stands until a later reading that read its path, or a document or record a path it read depends on, no longer raises it; once nothing in the change reaches its path, the reread of what changed answers for it;
- after the builder's review, a reread covers every stale file and every changed file that a standing flag names, or whose pointer reaches the document or listed record it names;
- a `Can tell: no` stands until a later reading of the whole change says `yes`;
- a damaged record holds the gate as unverifiable rather than vanishing;
- only this pull request's readings count: a reading records its branch and pull request, and one recorded without them counts only when this change's history holds the head it read;
- the builder is resumed only for what the latest `open` routed to it, a flag left unaccepted or a `Can tell: no`, and only a turn that returned something counts as its review;
- an `open` carries the head its reading read;
- `run ready-reviewers`, `run use`, `run proof` and `run release-report` refuse while the gate holds, because naming a stage skips the decision the gate sits in; each reports its own refusals first, since a repair those owe would stale the reading anyway.

The reader launches on its role's vendor and records a same-vendor reason whenever it lands on the builder's vendor, fallback included, and it never starts until a build bundle or the builder's session marker proves which vendor built the change.

The reading tree is built in a temporary folder of its own, holding only the tree and outside the entrance's records, which keep the reading's record and diff, written as consumer trees' records are, and its prompt. The gate finds a reading's record there or, for a reading recorded before the records kept it, where that reading left it, beside its tree; a record found in neither place is reported at its path in the records. The tree itself is kept after the run; a tree whose record could not be written is removed, with any diff written for it, because no reading can be judged without its record.

**Why.**

- A reader who saw the brief can't show what the code alone explains, so the reader never sees the issue, brief, pull-request text or branch name.
- The entrance, not the holder, chooses the inputs and composes the prompt, because whoever holds the brief could aim the reader through them.
- The tree follows only `path#anchor` pointers, never a file a changed file merely mentions, because that is the one route the code-reasons standard gives from code to its reasons, and a pointer that doesn't resolve then reaches the reader as the dead end it is rather than being patched by whoever built the tree.
- Every link inside a pointed section is carried, not only its decision records, because the entrance can't tell a decision record by its path.
- The holder's review rides in the `open` comment because a change on the mechanical lane has no holder reading to carry it, and one marker with `open` and `clean` serves every lane alike.
- The builder reviews each posted reading that leaves anything standing or owed, because the builder holds the reasons it decided while building and is the one who fixes what the reading finds; a reading the holder's acceptances leave with nothing to fix closes without that turn, so the loop can end on the holder's judgement, and the holder's own review against the brief still looks for misreadings.
- Every changed path is read, with no classifier deciding what counts as code, because a classifier would be configuration every adopting repository owes.
- Blob identity is what the entrance can compare, and counting the pointed document's blobs rereads a file whose fix landed only in its document.
- A flag must name a file the reading held, and a standing flag owes a reread of what reaches it, so that every flag has a way out through a reading the gate orders.
- The holder takes the owner's release report's excerpts worth a look from the reader's nominations, and the report shows only a few, so the reader nominates only a few.
- The gate waits for the floor because a repair the floor still owes would change the files a reading has just read.
- The reader takes the setting the owner ruled for fresh judging seats, so a reading costs and judges like the other cold seats it sits beside.
- The holder can accept a flag, because a bar that only a reading with no flag can clear has no guaranteed end; the acceptance carries its reason and the release report lists every one, so the owner judges each from what the holder wrote.
- An acceptance must name exactly one flag of its reading, so a mistyped line fails rather than accepting nothing.
- A `Can tell: no` can't be accepted, because why the change was made must reach the record that outlives it.
- There is no round cap, because every flag is either judged by a later reading or accepted with a reason, and a cap would let a change close over a flag nobody judged. A flag that keeps coming back ends when the holder accepts it or names it a false claim about the tree, which is probed; a passage of the wrong shape, which is restated whole; or a fork, which is put to the owner.
- Every judgement fails closed, so a `clean` can't pass over a flag, a reading or a record the gate can't see.
- The reader works in its tree's folder, so that folder holds the tree alone; a record or prompt there would name the change.
- A reading recorded before the records kept it still counts, because pull requests open when that layout changed hold such readings.
- The reading tree is kept after the run, though the gate needs only its record, so that what the reader saw can still be inspected when a holder disputes a flag.

**Decisions in force:** D-795, seat defaults follow the owner's rulings; D-944, code carries its reasons; D-952, the cold reader reads each change for its reasons; D-968, a consumer tree keeps its record elsewhere.

## Consumer trees

**What it does now.** `work.py tree` builds a use consumer's tree from committed bytes: a new repository with one neutral detached commit, no remote and no shared history, holding only the declared job paths and loading surfaces, each file proved against its committed blob. Its record of the tree names the change, the source checkout and revision, what was excluded and every carried file, under a digest. `tree` writes that record whole to the entrance's own records, under `trees/`, in a file named by a digest of the tree's resolved path, prints the path as `tree_metadata`, and leaves nothing but the tree in the folder the tree sits in. `run use` takes that path, proves the record's integrity, re-proves the source revision, the neutral repository and the tree's bytes, and launches the consumer with the tree as its root. The cold reader's reading tree is recorded the same way.

Before anything is built or launched:

- `tree` refuses an output that exists, one inside the source, one inside the entrance's records, and one whose folder holds those records at any depth;
- `tree` refuses an output whose folder holds an entrance tree record file, `<tree>.tradecraft-tree.json` for this tree or any other, naming that file and saying to remove it;
- `tree` refuses an output whose own name, or the name of the folder it sits in, carries the change's issue number or an open pull request's number as a whole run of digits, checking the issue number first, without the network; a merged pull request's number is not checked, folders higher up are not examined, and when the issue, its comments or its pull requests can't be read, `tree` refuses;
- `run use` refuses a tree whose folder holds such a record file, naming the file and saying to remove it and rebuild the tree it records, without opening it; any other file beside a tree, such as a job fixture or a second tree, is lawful;
- `run use` refuses a record that isn't at the path derived from the tree it names, one whose digest doesn't match, and every mismatch of source, revision, bytes or repository shape.

`tree` replaces a record left at its path by a tree since deleted, so a deleted tree can be rebuilt where it was; a reading's record is never replaced.

**Why.**

- The tree's folder is the consumer's working space: a consumer lists it and works in it, so a record there would tell it which change it is judging, where the holder's checkout is, and what was withheld.
- The record's name is derived from the tree's resolved path, compared as the platform compares paths, so a record still proves which tree it belongs to without sitting next to it, and one copied to another tree's path is refused.
- Only the entrance's own records beside a tree are refused, because a tree built before the record moved, or one with its record put back, keeps the exposure, while side-by-side trees and job fixtures are layouts a job needs. A sibling tree's record counts too: it names its change as plainly to a consumer listing the folder.
- `tree` refuses a path with the record file beside it, because a tree built there would meet `run use`'s refusal again; removing the file is the holder's, since the entrance never opens it to tell whose it is.
- Only an open pull request's number is checked, because an open pull request is the change under test, while a merged one belongs to work already landed, such as an earlier instalment.
- Only the tree's folder and the folder it sits in are checked for the change's numbers, because those two names appear in every command the consumer runs and are the ones a holder chooses; folders higher up are usually named by the runtime, and the random digits of a session id would refuse holders by chance.
- An unreadable pull-request lookup refuses, because a check that can't be decided would otherwise pass the path it exists to stop.
- The entrance's records may not sit in or below the tree's folder, so that nothing but the tree is there for every tree, including one built in the home folder.
- A stale record is replaced because a holder who deletes a tree can't see its record to delete it too, and a record proves nothing without its tree.
- Every record is written to a temporary file and then moved into place, so a partial record never stands.
- This keeps the record out of the consumer's folder only. A consumer whose shell reaches the rest of the machine can still find the entrance's records, which is a separate exposure.

**Decisions in force:** D-726, the entrance is the holder's instrument, which builds neutral, mode-declared, history-free consumer trees; D-736, a landed commit is a lawful consumer-tree source; D-968, a consumer tree keeps its record elsewhere.

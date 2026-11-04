# Design of the shipped library

**Purpose:** say what the shipped library's mechanisms do now and why, for whoever changes them next. **Audience:** a session or person opening code here that points at one of these sections. **Success:** that reader finds the reasons behind the code here, complete, without the issue that built it or any decision record.

The decision log stays in the practice's own repository and doesn't ship, so this document is where a reader of the library finds the reasons, and each section states its reasons whole. The decisions in force are named by their decision-log ids for a maintainer searching the log; they are not pointers a reader follows. Code added under the code-reasons standard opens with a pointer to its section; existing code is brought in by the repository's catch-up.

## The cold reader

**What it does now.** Once a builder turn exists for a change, `run cold-reader` builds an isolated reading tree from the change set. The tree carries every changed file, whatever kind of file it is; for each file the reading covers, the Markdown file each `path#anchor` pointer in it names; and the files linked inside that anchored section. A first reading covers every changed file, and a reread covers only the files it owes, though it still carries the rest for reference. All of it is verified against its committed blobs in one neutral detached commit. A tree that names the change's branch is refused before launch, and issue or pull-request numbers in any carried file are counted as residue. One fresh read-only seat, on Claude unless the change names another, reads the tree against the code-reasons standard and returns an account in a fixed form, ending with a capped handful of excerpts it nominates as worth a look. The stage checks only that form, including that each flag names a file the tree carries other than the diff file.

The holder posts the account whole in one `open` comment with its own review against the brief beneath it, and the resumed builder reviews the account and makes its fixes. A later `clean` comment closes the reading. It counts only when posted after the builder's review of the latest `open` reading, at the current head, with nothing below still owed; on every hold the gate returns, a `clean` posted after the latest `open` is set aside as invalid, while one posted before it closed an older reading and is left alone. Until a current `clean` stands, the entrance's decision holds readiness, use, proof and the release report, and it asks only once the change's floor has passed:

- a reading is current per changed file, by the file's blob and the blobs of the document its pointer names and the records that section lists;
- a flag stands until a later reading that read its path, or a document or record a path it read depends on, no longer raises it; once nothing in the change reaches its path, the reread of what changed answers for it;
- after the builder's review, a reread covers every stale file and every changed file that a standing flag names, or whose pointer reaches the document or listed record it names;
- a `Can tell: no` stands until a later reading of the whole change says `yes`;
- a damaged record holds the gate as unverifiable rather than vanishing.

**Why.**

- A reader who saw the brief can't show what the code alone explains, so the reader never sees the issue, brief, pull-request text or branch name.
- The entrance, not the holder, chooses the inputs and composes the prompt, because whoever holds the brief could aim the reader through them.
- The holder's review rides in the `open` comment because a change on the mechanical lane has no holder reading to carry it, and one marker with `open` and `clean` serves every lane alike.
- The builder reviews each posted reading before it can close, because the builder holds the reasons it decided while building and is the one who fixes what the reading finds.
- Every changed path is read, with no classifier deciding what counts as code, because a classifier would be configuration every adopting repository owes.
- Blob identity is what the entrance can compare, and counting the pointed document's blobs rereads a file whose fix landed only in its document.
- A flag must name a file the reading held, and a standing flag owes a reread of what reaches it, so that every flag has a way out through a reading the gate orders.
- The holder takes the owner's release report's excerpts worth a look from the reader's nominations, and the report shows only a few, so the reader nominates only a few.
- The gate waits for the floor because a repair the floor still owes would change the files a reading has just read.
- The reader takes the setting the owner ruled for fresh judging seats, so a reading costs and judges like the other cold seats it sits beside.
- There is no round cap, because every flag is judged by a later reading and a cap would let a change close over a flag nobody judged. A flag that keeps coming back ends when the holder names it a false claim about the tree, which is probed; a passage of the wrong shape, which is restated whole; or a fork, which is put to the owner.
- Every judgement fails closed, so a `clean` can't pass over a flag, a reading or a record the gate can't see.

**Decisions in force:** D-795, seat defaults follow the owner's rulings; D-944, code carries its reasons; D-952, the cold reader reads each change for its reasons.

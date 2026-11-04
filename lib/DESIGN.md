# Design of the shipped library

**Purpose:** say what the shipped library's mechanisms do now and why, for whoever changes them next. **Audience:** a session or person opening code here that points at one of these sections. **Success:** that reader reaches the reasons and the decisions in force behind the code without the issue that built it.

Each section names the decisions currently in force behind its code by their decision-log ids. The decision log stays in the practice's own repository and doesn't ship, so an id here is a name to look up there, not a link. Code added under the code-reasons standard opens with a pointer to its section; existing code is brought in by the repository's catch-up.

## The cold reader

**What it does now.** After each build, `run cold-reader` builds an isolated reading tree from the change set. The tree carries the changed files, the Markdown file each `path#anchor` pointer in them names, and the files linked inside that anchored section, verified against their committed blobs in one neutral detached commit. A tree that names the change's branch is refused before launch, and issue or pull-request numbers in a record the change adds are counted as residue. One fresh read-only seat reads the tree against the code-reasons standard and returns an account in a fixed form, and the stage checks only that form. The entrance's decision then holds readiness, use, proof and the release report until a current `clean` reading stands:

- a reading is current per changed file, by the file's blob and the blobs of the document its pointer names and the records that section lists;
- a flag stands until a later reading whose reach includes its path no longer raises it;
- a `Can tell: no` stands until a later reading of the whole change says `yes`;
- a damaged record holds the gate as unverifiable rather than vanishing.

**Why.**

- A reader who saw the brief can't show what the code alone explains, so the reader never sees the issue, brief, pull-request text or branch name.
- The entrance, not the holder, chooses the inputs and composes the prompt, because whoever holds the brief could aim the reader through them.
- Blob identity is what the entrance can compare, and counting the pointed document's blobs rereads a file whose fix landed only in its document.
- Every judgement fails closed, so a `clean` can't pass over a flag, a reading or a record the gate can't see.

**Decisions in force:** D-944, code carries its reasons; D-952, the cold reader reads each change for its reasons.

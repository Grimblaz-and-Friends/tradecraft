# D-0 — The cold reader reads each change for its reasons

**Purpose:** record why instalment 2 of #942 builds the cold reader the way it does, and that it ends [D-944](D-944-2026-11-03-code-carries-its-reasons.md)'s interim. **Audience:** a future session changing the `cold-reader` stage, the `cold-reading` marker, what the reader may hold, or when a change's reading is current. **Success:** that reader can recover what was chosen over what without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/942#issuecomment-6613335767) governs. Instalment 2's pre-implementation artifact was [settled on the cap route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/942#issuecomment-6623789242). The lane is ordinary / connected, and no panel was bought.

## Rows and their reasons

- **Row 4, a fresh reader who never sees the issue, brief, pull-request text or branch name checks that the code explains itself, over the holder judging it.** The owner's proposal: a reader who never saw the issue should get "everything it needs from the adr, live documentation and code itself". Flags alone miss confident misreadings, so the reader writes what each section is for and why, and the builder and holder both review that account. Correcting the account would hide the gap the check exists to find, so it is never corrected by hand, and each fix is made in the code or the documents, preferring the code, and then reread.
- **Row 5, the reader runs on every change that alters code, the mechanical lane included.** Reasons must hold everywhere, and a small change's reading is small. The brief estimated about $4 at list for a change of around a thousand lines, from #943's use consumer at $3.86 and 14 minutes on Opus 5.5 at `xhigh`; this change measures its own run in its release report.
- **The interim ends.** D-944 left the holder judging whether a change with no decision record decided nothing and is understood without its brief, and nominating the excerpts worth a look. Both now belong to the cold reader. The holder keeps its own pointer, in-force, lasting-reason and return checks.

## Calls made inside the rows

- **C1. A named entrance stage, `run cold-reader`, over a holder-written seat dispatch.** The holder holds the brief and could aim the reader through its dispatch, and a stage gives the every-lane gate somewhere to live.
- **C2. The entrance derives the reader's inputs only along row 4's list.** It follows `path#anchor` pointers from changed files to Markdown files that exist at the head, and from each pointed section only the links inside it. A file a changed file merely mentions isn't carried, so an unresolvable pointer reaches the reader as a dead end rather than being patched by whoever built the tree. The entrance can't tell a decision record by its path, so another link inside a pointed section is carried too; the holder's pointer check catches that malformed section.
- **C3. One `cold-reading` marker with `open` and `clean`, the holder's review riding in the `open` comment,** because the mechanical lane manufactures no `holder-reading` marker and row 5 requires that lane covered.
- **C4. A reading is current by blob, per changed path and per dependency; a reread is per file.** Blob identity is what the entrance can compare. Counting the pointed document's and listed records' blobs rereads a flagged file whose fix landed only in its document. A merge from the base that touches none of them owes no reread.
- **C5. Every implementing pull request is read, with no classification of what counts as code,** because a path classifier is configuration every adopter would owe.
- **C6. The cold classification's defaults, Claude Opus 5.5 at `xhigh`,** keeping [D-795](D-795-2026-09-29-seat-defaults-follow-owner-rulings.md)'s seat rulings and matching the setting the brief's estimate assumed.
- **C7. No round cap.** Row 4 fixes every flag. A returning flag takes the artifact rule's three-way naming, and a fork takes the existing owner door.
- **C8. The stage is `cold-reader` and the marker `cold-reading`,** after the brief's own name for the seat.
- **C9. Decision records a change adds may carry its issue and pull-request numbers in the reader's tree.** Row 4 lists them as inputs; the reader has no network tool, so their links are dead to it, and the occurrences are recorded as residue.
- **C10. The account's why answer opens with `Can tell: yes|no`, and only a reading of the whole current change clears a `no`.** The entrance can then hold `clean` on row 3's test mechanically, and a reread of a few fixed files answers only for those files.

## Made while building

- **The gate is due once a builder turn exists for the change, as reach is.** A pull request with no recorded or observed builder turn has nothing the entrance can attribute a reading to.
- **Suites about other stages run past the gate through one opt-in test fixture,** so the gate's own tests exercise it and the rest of the suite keeps testing what it was written for.
- **The diff travels inline below a size bound and as one file in the reader's root above it,** so a large change's prompt stays readable.

## Deferred

- **#772's lock.** Row 4's "a document fix made after the build returns to the owner for his lock" waits on #772, which is affirmed but not built, so shipped prose says nothing about it yet.
- **Row 10's catch-up issues** are filed when this instalment lands.

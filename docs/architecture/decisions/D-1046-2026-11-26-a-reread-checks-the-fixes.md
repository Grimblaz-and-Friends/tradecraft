# D-1046 — A cold reread checks the fixes, and a flag stands only on what the change wrote

**Purpose:** record why the first instalment of #981 changes what the cold reader's gate orders after a first reading, what a reread is shown and asked, and which flags stand. **Audience:** a future session changing the `cold-reader` stage, its reading record, or what clears a flag. **Success:** that reader can recover what was chosen over what without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/981#issuecomment-7193757733) governs. This instalment builds its rows 3 and 4, which its Delivery paragraph lands first; rows 1, 2 and 5 (two first readers, the reader list, the model update) are the second instalment's. The plan was [settled on the cap route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/981#issuecomment-7194453636). The lane is ordinary / connected, and no panel was bought.

This record ends two calls of [D-952](D-952-2026-11-04-the-cold-reader-reads-each-change.md): its C4, "a reread is per file", and the rule that a pointed document's blob makes the files pointing to it stale. Every other call of D-952 and [D-997](D-997-2026-11-11-a-flag-may-name-several-lines.md) stands.

## The fault

Every reread was a new audit. The reader was told nothing of earlier flags, fixes or acceptances, was shown each reread file's whole diff from the base again, and every flag it raised had to be fixed or accepted, so a reading loop ended only by acceptance. On #946, 22 rereads raised 45 flags, 37 of them on lines the previous fix had not touched, at $28.43 at list; the issue's cross-change read 42 measured 339 of 379 rereads' flags on lines no fix touched. A reader also flagged old lines of files a change only edits, which the code-reasons standard leaves to the repository's catch-up, and someone accepted them by hand.

## What was chosen over what

- **A reread checks the fixes and judges nothing else again (row 3), over narrowing the reread from a file to a section.** The owner's ruling: "Check the fixes". A section reread still audits again, so the loop would still end only by acceptance.
- **A flag stands only on what the change wrote (row 4), over leaving the reader free and accepting old-line flags by hand.** The owner's ruling: "Only what it wrote". Two readers, in the second instalment, would double the hand acceptances.
- **The entrance holds row 4 by placement, over refusing a return that flags an old line.** A refused return is read again, which is the cost this change exists to remove, so the reader is told the rule and the entrance lists what falls outside it.

## Calls made inside the rows

- **The judged lines are sealed in the record,** over recomputing them at each judgement, because the gate re-reads every reading on every decision and a pruned head would turn a settled reading unverifiable. The record's schema moves to version 2, so an entrance older than this refuses a new reading rather than misreading it as a whole-file one.
- **A line is gained unless the last reading read it as one of the change's lines,** over counting only edited lines, because a merge resolved by keeping the change's side over a base edit makes a line the change's without editing it, and the brief names a change through with lines no reader read as its risk.
- **Both neighbours of a removal count,** because a removal has no line of its own and a reader told to flag "the place" may name either side.
- **A fix-check covers only paths with gained lines and carries every standing flag by its number,** over covering a flagged file or every file pointing to its document: a flag judged by number needs no covering, and coverage would otherwise grow with the number of pointing files.
- **The document-gap kinds may name an untouched pointed document in a first reading only.** That is the one reading of the whole change; a fix that opens a new gap is flagged at the gained line that opens it, such as the pointer or decision the fix adds.
- **A reread is shown marked excerpts, not a diff since the last reading,** because that diff shows a base merge's lines as added, which the entrance never judges. What is given up is a fix's removed text; the reader has the earlier flag's words and the code as it now stands.
- **A line-less flag stands only where its whole file is judged,** because on a file the change only edits it can't be told from a flag on old lines.
- **A `not-answered` flag becomes the reread's own flag,** so the existing acceptance line accepts it in the newest `open`.
- **A reread writes no sections and nominates nothing,** because it judges only the fixes.
- **A why-check covers every changed path,** so the existing rule that only a reading of the whole change clears a `no` stands as written, while its flags stay on the gained lines.
- **An acceptance naming a flag outside the change is harmless,** over an error, because the acceptance rule exists to catch a line that accepts nothing, and this one names a real flag.
- **Version 1 flags that name lines are placed; those that name none stand.** The changes in flight when this lands are the ones Delivery lands it first for; a version 1 reader was never told to give lines.

## Made while building

- **A later reading of whole files clears a flag on a path it reaches, as every reading did before.** The plan kept that rule between two version 1 readings; the build applies it to any later version 1 or first reading, so a first reading overtaken by another first reading, as when a once-refused return later counts, never leaves its flags with no way to clear. The gate orders a first reading only when there is none, so no other order reaches it.
- **An earlier flag's lines are numbered as its file stood when the flag was raised,** and a reread is told so, because a fix since may have moved them.
- **A builder's reading report counts as findings only what stands:** its new flags that stand, each earlier flag it left `not-answered`, and a `Can tell: no`. The entrance places them from the sealed reading record its dispatch was recomposed from, when it reads the posted report, and lists the flags outside the change apart beside the findings, so a builder's readiness record owes them no entry and no builder-route release report shows a hand decline of a line the change didn't write. The placement isn't written into the posted comment, because a report counts only while it equals the stored return byte for byte. The builder first had every flag counted and declined by hand, which the holder set aside under row 4's owner cell.
- **The release report's figures for a flag outside the change come only from `outside`;** `flags`, `accepted` and `routed` hold flags that stand, so no hand acceptance of an old line reaches the owner.

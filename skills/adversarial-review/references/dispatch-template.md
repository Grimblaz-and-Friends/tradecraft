# Dispatch template

**Loaded when** you are sending a review role its work — a seat, a defense, a judge. Copy this file whole and fill every field; `../references/dispatch.md` says why it has this shape.

`<title line — byte-identical across every recipient of this round>`

## Shared block — byte-identical across every recipient against the same diff base

- **Artifact:** `<location>`; **diff base:** `<sha>`; **revision under review:** `<sha>`.
- **Purpose statement:** `<purpose, audience and success criteria, verbatim or by link; for an implementation, the settled acceptance criteria on its issue>`.
- **Evidence standards:** `<the cell body's, verbatim or by link>`.
- **What every recipient's output carries:** the revision it actually worked at, or that it reached none; whether its tree was its own or shared with any other recipient; its raw finding count; and, for each finding, what the evidence standards ask.
- **Revision, and what lands you there:** `git rev-parse --short HEAD` prints `<sha>` before anything else. `<Where the root was cut by a tool: run git checkout --detach <sha>, never with -f; if it aborts, read the right bytes with git show <sha>:<path> and report that you could not detach rather than proceeding. Omit where the dispatcher positioned the root; the recipient then only verifies and reports.>` Any doctrine or charter text reaching you from anywhere else is not the governing text.
- **Session note reporting use of the artifact:** `<whole, or "none">`.
- **Diff:** `<whole, or by link>`.
- **Executable probe evidence:** `<commands, revisions, results, and every execution gap>`.
- **Predecessor stages' output:** `<each whole, never summarised; none for a seat>`.
- **External pass:** `<the bundle by file or link and its complete receipt block as the script printed it, replay command included; or the receipt of a proved-empty bundle. Withheld from cold-read, and that dispatch says so here.>`
- **An execution need you cannot meet is returned, never ruled on.**

## Dispatcher's note — labeled as such, additive; no seat takes one

`<None for a seat. For a defense or judge: matters to settle, as a labeled note on the docket and never as the docket.>`

## Recipient

- **Role and lens:** `<the seat's name and its lens brief copied from ../references/roster.md; none for cold-read; the defense or the terminal stage as ../references/arbitration.md states it>`.
- **Working root:** `<absolute path of its own detached tree; where the role writes, that tree is its write boundary>`.
- **Output shape:** `<findings | a verdict per finding with its evidence and remedy price | a ruling per docket entry with its fate and one-line reason>`.

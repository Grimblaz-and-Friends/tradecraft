# D-967 — The standing page in parts, edited by a repo tool, with an archive

**Purpose:** record why #891 splits the lab's standing page into a short pickup body and six linked part comments, edits it only through `tools/steward_page.py`, and archives what leaves it. **Audience:** a future session changing the page's shape, the tool, its markers, its limit or the archive. **Success:** that reader can recover what was chosen over what without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/891) governs. The pre-implementation artifact was [settled on the cap route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/891#issuecomment-6703516778). The lane is ordinary / connected, and no panel was bought.

This record supersedes none. [D-691](D-691-2026-09-21-steward-and-cross-session-intake.md) designates #683 as the standing page and the read's standing issue, and that stays; this record changes only the page's form.

## The owner's answers

Given together on 2026-11-07 ("Take all three"):

- **Where the parts live: each part in its own Steward comment on #683, with the body shrunk to what a holder needs at pickup,** over one body kept small by archiving and limits, and over a separate issue for each part.
- **How the page is edited: the page is its own data, and a repo tool edits it one entry at a time,** over generating the page from data kept on his machine, and over rules alone with the Steward's one-off scripts.
- **The archive: one closed archive issue that gains one comment per read,** over removed entries going nowhere new.

## The holder's calls inside the rows

- **A 20,000-byte limit for every part, the body included,** about 5,000 tokens, the size the owner and the Steward compared the lab against. Archiving alone leaves "In flight" far over it, so only the current-state rule held by a limit keeps parts small.
- **The route past the limit is a reason the Steward gives, shown in the part until it is back under,** because a refusal with no way past could stall the Steward mid-ruling.
- **The Steward's part is a sixth part,** holding rulings that bind only the Steward, rulings waiting on the owner and what the Steward owes, so the body can fit its limit. A ruling a holder applies stays in the body until it retires; moving it out to make the body fit is not a lawful use of that part.
- **Landed means a merged pull request or an issue closed as completed.** `archive --closed` removes a ruling only once its change landed, and `archive --read` refuses while a ruling's change closed without landing until the Steward re-points it with `replace --issue` or keeps it with its reason. A ruling is kind `ruling` or `steward-ruling`: row 4 says a ruling retires when its carrying change lands, and one that binds only the Steward is still a ruling. The holder first drew this line at kind `ruling` alone and corrected it after the cold reading. Every other kind, `owner-wait` included, leaves on any close, because a ready item or an owner wait closed as not planned has been declined.
- **The move keeps a ruling ledger:** one row for every entry of the old page's two rulings sections, saying where it went, why for a row sent to the Steward's part, and the retiring change or "declined" for a row archived. The body's rulings become marked `ruling` entries through `load body`, and `status` counts them against the ledger.
- **The write window is stated, not closed.** The tool re-reads each part immediately before its own write and refuses on any difference from the saved copy, and `archive` does so for each part it rewrites. A hand edit landing between that re-read and the write is overwritten and survives only in GitHub's edit history.
- **An issue closed with no state reason counts as closed without landing,** and an entry's `issue=` may name a pull request as well as an issue.

## Calls the artifact made

- **C1. A new script, `tools/steward_page.py`, imports `tools/steward_watch.py`** for the marker, the GitHub wrapper, the state directory and the probe refusal, rather than adding commands to a script already about the wake, the handover and the cover. `steward_watch.py` is unchanged.
- **C2. Part comments are posted through the wake's `post` path, with the part marker on line two,** so the marker grammar, the wake and the intake route are unchanged, and only a comment from the owner's account counts as a part.
- **C3. Fixed part names and kinds; the kind decides the part.** The tool can't judge whom a ruling binds, so the ledger records that judgement at the move.
- **C4. The body opens with the page marker naming the archive issue, and the tool regenerates the index on every body write,** touching only a body that carries the page marker.
- **C5. An entry's marker ends its first line,** after a renderer spike showed a marker at the start of a list item turns the rest of the item into raw text. Ids are eight random hex digits.
- **C6. Entry text comes from a UTF-8 file,** refused with a byte-order mark or a control character other than newline and tab.
- **C7. The limit counts the exact text written, markers and reason block included,** and every writing command takes `--over-reason`.
- **C8. The saved copy lives in the Steward's state directory** and moves only after a write is read back and matches.
- **C9. Issue state is read through GraphQL in batches of fifty;** an unresolved reference is an error, never open.
- **C10. Archive order: refuse on an unresolved ruling, stale-check, post or append, verify, then rewrite each part with a re-read before it.**
- **C11. A move between parts writes the destination first,** so a failure leaves a duplicate rather than a loss.
- **C12. `keep` shows its reason on the entry:** on a ready entry's one line, otherwise on a continuation line.
- **C13. The move's commands:** `init-archive`, `archive --move`, `create-part`, `load` (the body included) and `body`.
- **C14. A repo-only design document, `tools/DESIGN.md`,** because no design document covered `tools/`, and `lib/DESIGN.md` ships and may not name repo-only code.
- **C15. Every command takes `--page` and `--state-dir` and prints one line of ASCII JSON;** a page other than 683 is refused against the default state directory.

## Made while building

- **GitHub's comment cap is 262,144 UTF-8 bytes, not a character count.** #957's premise test ([comment 6674635185](https://github.com/Grimblaz-and-Friends/tradecraft/issues/957#issuecomment-6674635185)) had 262,144 ASCII bytes accepted and 262,145 refused, and 87,000 three-byte em dashes (260,858 bytes) accepted while 100,000 (299,858 bytes) were refused, each refusal reading "maximum is 65536 characters". This build's own probe agrees: a 65,537-character comment was accepted, and 262,145 characters and 140,000 two-byte characters were refused. The archive's cap check counts bytes.
- **Text files may carry CRLF line endings, which are normalised to LF,** as text read from GitHub is; a lone carriage return is still refused.
- **Entry and preamble text may mention the wake's `lab:steward:v1` marker,** because live rulings name it, but not a structure marker this tool reads (`lab:steward-part`, `-entry`, `-over`, `-index`, `-archive`). The move's archive file may carry any of them, because it holds the old page word for word.
- **Any fault on the page blocks every write.** The Steward repairs a fault by hand, then runs `accept` on the part, so no write builds on a part the tool cannot read.
- **The archive skips an entry whose exact text read N's comment already holds,** marker and id included, so a re-run never posts twice, and an entry changed since it was posted is posted again in its new form rather than removed unrecorded.
- **`replace --clear-kept` clears `kept`;** otherwise `replace` and a move to another kind carry a kept entry's shown reason onto its new text.
- **`body` refuses a body that already carries the page marker,** because it writes no entries and would otherwise drop the body's rulings without archiving them.
- **`create-part` checks the body's limit and saved copy before posting,** using a longer stand-in comment id for the new index line, so a refusal there rarely comes after the new part exists.
- **Only an unresolvable reference is retried singly.** gh fails a whole GraphQL query when one number in it is neither an issue nor a pull request, so a failed batch is split to name that reference; any other gh failure, such as an expired login, stops the read with its own error rather than reporting every reference unresolved.
- **A refusal after a write names what was written,** for every command: a move between parts stopped at its source, `create-part` stopped at the body's rewrite, or an archive stopped at a part.
- **The archive issue's second line names its page** (`<!-- lab:steward-archive-page:v1 page=N -->`), under the marker C10 names, so a probe page's archive is never taken for #683's. `init-archive` refuses while an archive for the page already exists, open or closed, and reports the new issue before closing it, so a failed close still names it.
- **`body` refuses until the archive issue holds the move's comment from the owner's account,** so the old page cannot be overwritten before what leaves it is archived, whatever order the Steward runs the move in.
- **A malformed `issue=` value is a fault and is never sent to GitHub,** so `status` names it rather than failing on it.
- **`init-archive` refuses once the body names an archive,** and closes the new issue as completed.

## What the cold rounds changed

Two cold verdicts ran on the artifact, the second reaching the two-round cap; the holder decided each point inside the affirmed rows ([first](https://github.com/Grimblaz-and-Friends/tradecraft/issues/891#issuecomment-6703278659), [second](https://github.com/Grimblaz-and-Friends/tradecraft/issues/891#issuecomment-6703418714)).

- **The first round** confined the Steward's part to rulings that bind only the Steward or wait on the owner, and added the ruling ledger; limited `--closed` to rulings whose change landed and added the "closed without landing" list; made `archive` re-read each part before rewriting it; gave every writing command `--over-reason`; put a ready entry's kept reason on its one line; and replaced a timestamp comparison with the probe's list of write URLs as the check that the build never wrote #683.
- **The second round** made `archive --read` refuse while a ruling's change closed without landing; turned the body's rulings into marked entries at the move through `load body`, counted by `status` against the ledger; and moved what the rounds changed out of the artifact into this record and the pull request.
- **Retraction.** The first draft claimed that a hand edit landing inside the tool's write window was caught. It is not: GitHub has no conditional update, so an edit landing between the tool's last re-read and its write is overwritten and survives only in GitHub's edit history. The design document states the window that way.

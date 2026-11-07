# The standing page in parts

**Purpose:** operate #683 as a pickup body and six part comments through `tools/steward_page.py`, archive what leaves it at each read, and move the old single-body page into parts once. **Audience:** the Steward, a resumed Steward, and a replacement. **Success:** every page edit goes through the tool, no part grows past its limit unseen, nothing leaves the page without first reaching the archive, and a holder reading only the body finds every ruling it applies.

Run every command from the Steward's checkout as `python tools/steward_page.py COMMAND`. Each prints one line of ASCII JSON. A refusal exits non-zero with `error`, and adds only what applies to it: `part`, with `diff` and `live_sha256` for a stale copy or `live` and `live_sha256` where there is no copy or `accept`'s SHA no longer matches; `bytes` for a part over its limit; `faults`, `unresolved` or `closed_without_landing` for what blocked the run; `missing` for entries an archive comment read back without; and `written`, the writes already made, when the refusal came after a write. An archive halted at a part adds `stopped_at`, and its `written` is `[]` when a re-run stops at its first part before writing anything. Each command takes `--page N` (default 683; any other page is a probe, refused against the default state directory) and `--state-dir`, resolved as `tools/steward_watch.py` resolves it.

## The parts and their kinds

| Part | Where | Entry kinds |
|---|---|---|
| `body` | #683's issue body | `ruling`: a ruling a holder applies |
| `steward` | comment | `steward-ruling` (binds only the Steward), `owner-wait` (waits on the owner), `owed` (what the Steward owes) |
| `read` | comment | `read`: the latest read |
| `ready` | comment | `ready` |
| `flight` | comment | `flight` |
| `traps` | comment | `trap` |
| `residues` | comment | `residue` |

The kind decides the part, so `add` takes a kind and no part. The tool refuses a `ruling` anywhere but the body and any other kind in it; a ruling leaves the body only through the archive. **Put a ruling in the `steward` part only if it binds only the Steward or waits on the owner.** A ruling a holder applies stays in the body until it retires, and the tool cannot judge whom a ruling binds, so that judgement is yours.

## The markers

- **A part comment** opens with `<!-- lab:steward:v1 kind=post -->` and carries `<!-- lab:steward-part:v1 part=NAME -->` on its second line. It counts only from the owner's account; a second comment naming the same part is a fault.
- **The body** opens with `<!-- lab:steward-part:v1 part=body archive=N -->`, `N` being the archive issue. The tool rewrites the index between `<!-- lab:steward-index:v1 begin -->` and `<!-- lab:steward-index:v1 end -->` on every body write and after every `create-part`, one link per part, and a part not yet created shows `(not yet created)`.
- **An entry** is one top-level list item whose first line ends with `<!-- lab:steward-entry:v1 id=ID kind=KIND issue=REF -->`, plus ` kept=yes` once kept. `ID` is eight random hex digits. `REF` is `none` or `REPO#N`, an issue or pull request in tradecraft, change-proof or one of the four products; nothing else is accepted. An entry that seems to wait on two issues is two entries, or names the one whose closing ends it.
- **An over-limit block** is `<!-- lab:steward-over:v1 -->` under the part's marker lines, then the visible `> **Over its 20,000-byte limit at N bytes:** REASON`.

Everything above a part's first entry is its preamble. Entry and preamble text comes from a UTF-8 file you write without the list prefix or any marker; the tool adds both. It refuses a byte-order mark, a control character (C0 other than newline and tab, delete, or C1), and the structure markers above; it accepts a mention of the wake's own `lab:steward:v1` marker. A ready entry is one line, and the ready list is renumbered on every write.

**A fault blocks every write to a part.** An unmarked top-level list item after the first entry, a duplicate id, a part carried by two comments, a counted comment whose part marker sits anywhere but its second line, a kind in the wrong part, a misplaced marker, index delimiters out of order or missing one end, a body page marker that names no archive issue, a repository outside the lab, or a kept entry whose `Kept after its issue closed:` reason can't be read is one. `status` names it. **Repairing a fault is the one edit you make by hand:** repair the part `status` names, then `accept` it. `init-archive` and `archive --move` write no part, so they run on a faulty page.

## The commands

Every command that writes a part also takes `--over-reason R`.

| Command | What it does |
|---|---|
| `status` | Writes nothing, not even a saved copy. Per part: link, bytes, limit, over-limit reason, copy state (`in-step`, `differs`, `no-copy`) and faults; for the body, its `ruling` entries and their count, its archive issue and whether its index is current. Also the missing parts, every fault, comments carrying a part marker that do not count, the `closed`, `closed_without_landing` and `kept` lists, and each reference that could not be resolved. |
| `show PART` | The live part, its SHA-256 and its entries. |
| `accept PART --sha SHA` | Records the live part as the saved copy, only if its SHA-256 is still `SHA`. |
| `add --kind K --issue REF --text-file F [--position N \| --after ID]` | Adds one entry to its kind's part, at the end unless placed. |
| `replace ID [--text-file F] [--issue REF] [--clear-kept]` | Replaces an entry's text or its issue. A kept entry keeps its shown reason unless `--clear-kept`. |
| `move ID (--position N \| --after ID)` | Reorders an entry within its part. |
| `move ID --kind K --text-file F [--position N \| --after ID]` | Moves an entry to another kind, with new text, writing the destination before removing the source; a failure between leaves a duplicate that `status` shows. |
| `keep ID --reason TEXT` | Sets `kept=yes` and shows `Kept after its issue closed: TEXT`, on a ready entry's one line, otherwise on a continuation line. |
| `preamble PART --text-file F` | Replaces a part's preamble; on the body it also rewrites the index. |
| `create-part PART --text-file F` | Posts a new part comment with F as its preamble; refused if the part exists. |
| `load PART --file entries.json` | Fills a part that holds no entries from a JSON list of `{kind, issue, text}`, each field text; it checks every entry before writing. Accepts the body. |
| `body --text-file F --archive N --rulings R` | The move only: writes the body's preamble, page marker, index and every ruling in R, a JSON list of `{kind, issue, text}`, in one write over the accepted copy; a rulings file that fails its checks writes nothing, and the old body stands. Refused once the body carries the page marker, and until archive issue N holds the move's comment. |
| `init-archive --title T` | Creates the archive issue, opening with `<!-- lab:steward-archive-issue:v1 -->` and a second line `<!-- lab:steward-archive-page:v1 page=N -->` naming its page, and closes it. It records the new issue's number in the state directory as soon as the issue exists, so it refuses once the body names an archive, or while that record or GitHub's issue listing names an archive for this page; the record covers a quick re-run the listing has not caught up with. |
| `archive --read N [--closed] [--ids ID ...]` | Archives at read N (below), into the archive issue the body names; `--archive` is refused. |
| `archive --move --archive N --file F` | Posts F whole, under the line `<!-- lab:steward-archive:v1 event=move -->` and a heading `## The move, DATE`, as the move's one archive comment, before anything is removed. Refused once the archive holds a move comment. |

## The limit

**Each part, the body included, is held to 20,000 bytes of the exact UTF-8 text the tool would write,** markers and any over-limit block counted. A write that would leave a part over is refused and writes nothing unless you give `--over-reason`; the part then shows that reason and its size until a write brings it back under, which removes the block. Every write that leaves a part over needs a reason, even one that shrinks it: `--over-reason same` restates the reason already shown and is refused where none is. On `archive` and `create-part`, the one reason applies to each part the command leaves over.

## The saved copy and the write window

The tool keeps each part's last confirmed text as `page-<PAGE>/<part>.json` in the state directory, and moves it only after a write is read back and matches. **Immediately before each write it re-reads the live part:** if the live part differs from the copy, or from the text this command read when it started, as when another run has written it since, it writes nothing to that part and prints a unified diff from the copy to the live text, with the live SHA-256; with no copy it writes nothing and prints the live part and its SHA-256. Review what you are shown, run `accept PART --sha SHA`, and redo the edit. A read-back that differs from what was written is reported and leaves the copy as it was, so your next edit shows you the difference.

**The window.** GitHub has no conditional update for a comment or an issue body. A hand edit that lands between the tool's last re-read and its write is overwritten; it survives only in GitHub's edit history, and the tool does not detect it.

## The archive and keep rules

**Landed** means a pull request that merged or an issue closed as completed. An issue closed as not planned, as a duplicate or with no reason, and a pull request closed unmerged, closed without landing. `status` reads every entry's reference fifty at a time and lists:

- **closed:** every entry whose reference closed, except the next two lists;
- **closed without landing:** every unkept ruling, `ruling` or `steward-ruling`, whose reference closed without landing;
- **kept:** every entry with `kept=yes`, with its reason.

`issue=none` never appears in a closed list. A reference that cannot be resolved is never treated as open: `status` lists it under `unresolved` and exits normally, and `archive --read` refuses.

`archive --read N` runs in this order:

1. **It refuses while any ruling is closed without landing,** naming each. Re-point each with `replace --issue` to its new carrying change, or to `none`, or `keep` it with its reason. A reference that cannot be resolved also refuses the run.
2. **It reads and stale-checks every part it will change** before posting anything, and refuses the whole run on a stale or over-limit part.
3. **It selects:** `--closed` takes every closed entry that is not kept, a ruling (`ruling` or `steward-ruling`) only once its change landed, and every other kind, `owner-wait` included, on any close; `--ids` takes exactly the entries named, which is how a ruling with no carrying change, a declined item and a ruling the owner retired leave.
4. **It posts** the removed entries, each exactly as it stood, marker included, grouped under their part's title, as read N's one comment on the archive issue; a re-run appends only the entries that comment does not already hold whole, compared from each entry's marked line to its end. It refuses a comment over GitHub's 262,144-byte cap.
5. **It reads the comment back** and removes nothing unless every entry is in it.
6. **It rewrites each affected part,** re-reading it first. A part that changed stops the run there, leaving it and every later part unwritten, and prints the diff; `accept` that part and re-run the same command. Entries already in read N's comment are removed without being posted again, and an `--ids` id that comment already holds is accepted though it has left the page; an id neither on the page nor in that comment is refused.

No other command removes an entry. Keep an entry whose issue has closed but which still applies with `keep`, giving why.

## At each read

1. Run `status`.
2. Review its lists: re-point each ruling under "closed without landing" with `replace --issue`, or keep it with its reason; keep anything else that must stay, with its reason; and collect the ids of retired and declined entries.
3. Run `archive --read N --closed --ids ...`.
4. Put the `status` output in the read's job, and ask the read seats to read the body and follow its links, report each part over its limit with its reason, and report any entry listed as closed that is still on the page without a reason.

## The move

Once, after the change that built the tool merges, with the default state directory:

1. Fast-forward your checkout.
2. `init-archive --title ...`, and note its number.
3. Draft the new parts from #683. Split the page into its parts; trim each entry to what applies now, posting the history and pickup notes you remove onto the entry's own issue with `gh issue comment` where that issue lacks them; collect the text that leaves into one file, with the trimmed history of entries that have no issue of their own and, for every ruling it archives, the change that retired it or "declined"; place each ruling by whom it binds; and write the **ruling ledger**: one row for every entry of the old "Rulings a holder applies" and "Rulings waiting on the owner" sections, giving its first words, where it went (the body, the `steward` part, or the move's archive comment), why for a row sent to the `steward` part (it binds only the Steward, or it waits on the owner), and the retiring change or "declined" for a row archived. Record the old body's SHA-256 from `show body` as you draft.
4. `archive --move --archive N --file <that file>`, before anything is removed.
5. `create-part` and `load` for the six comment parts.
6. `accept body --sha <the SHA you recorded>`, which refuses a body changed since you drafted, then `body --text-file <how the page is used> --archive N --rulings rulings.json` with every ruling the ledger sends to the body.
7. `status`. Every part must be under its limit; a part that cannot get there without dropping something still in force goes to the owner with its size before any `--over-reason` is written. The body's ruling count must equal the ledger's body rows, each row's first words found in one of those entries.
8. Update your own scripts that parse the old section headings, and the read-job template, to match "At each read".
9. Report the moved page to the owner, with each part's size and the ledger.

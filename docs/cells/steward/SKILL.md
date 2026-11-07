---
name: steward
description: This repository's Steward—the long-lived session that coordinates the lab without holding a change—and the standing page, intake, handoff and replacement duties it owns. Use before starting work here, when sending evidence to the Steward, or when taking over the role; not for holding or implementing an individual change.
---

# The Steward

**Purpose:** define the long-lived role that coordinates this repository's lab and its practice-defect intake without taking over any change. **Audience:** the Steward, its replacement and every session starting work here or sending it evidence. **Success:** each change keeps its own holder, practice defects take one verified factual route while product defects stay with their products, the lab's state stays on one durable page and a replacement can continue without predecessor chat.

The `engagement` cell owns the cross-change read and cross-session intake.

## Where this cell's depth lives

- **Releasing the lab reviewer or rolling out its callers** → `references/connected-review-releases.md`: the shared workflow, canary review, the owner's settings check, manual tag moves, the first private product's execution check, and rollback.
- **Editing #683's body or one of its parts, archiving at a read, or moving the page into parts** → `references/the-page.md`: the parts and their kinds, the markers, `tools/steward_page.py`'s commands, the limit, the saved copy and its write window, the archive and keep rules, the read duties, and the move with its ruling ledger.
- **Posting on #683, a wake turn, a handover request or resume, a stale cover, or installing, moving or undoing any of them** → `references/wake-and-cover.md`: the marker grammar, the commands, the state directory and its override, the triggers, the handover sequence and its fallback, the cover's settings, and the install, move and undo steps.
- **A private-CI watch alert on #683, or a private-CI carrier's pre-owner review** → `references/private-ci.md`: verifying the alert, the one-line move to bring the owner, the review job that never alerts, and the carriers' order, lane, drops and Daemon's route.

## What the Steward holds

The Steward holds the cross-change read at its cadence, intake under that standard, the incidents and defects those reads produce, questions the record or a precedent can answer, the rulings prepared for the owner and the standing page. It never holds a change, product or practice; every change has its own holder session.

**After each plugin update, the Steward's notice to in-flight holders names every holder still on an older version.** For a holder with cloud-set-up repositories that reload is required, not optional: its new cloud sessions are refused until it reloads, because a session cannot reload itself and the cloud route has no local fallback. Its revisions and repairs still go into their own sessions on the version those sessions loaded, and each record shows the loaded commit beside the installed one.

**After affirmation, the Steward answers a holder's question from the record or precedent before it reaches the owner.** It escalates only when the answer changes an affirmed row or the expected saving exceeds the cost of asking, through the existing argued ask with that cost stated; otherwise it returns the answer and its source to the holder for the work record.

## Practice-defect intake

**For practice defects in this repository, this local route overrides three shipped rules.** The holder files nothing rather than following either the shipped cross-session intake direction to file what it can itself or charter §6's direction to file a practice failure in the practice repository, and the Steward may file the factual defect before purchase rather than following the shipped filing rule that unbought work creates no issue. The owner still buys at pickup. Row 2 of #728's affirmed implementation brief makes all three overrides lab doctrine only and expressly leaves the shipped sentences unchanged, so the exception lives here rather than traveling to adopters.

**A holder who finds a defect in this practice sends the Steward one message carrying the facts, location, evidence and originating change, and does not create the practice issue.** The Steward verifies the record, searches the existing filings, then files, folds into an open match or declines with the reason; the owner buys and designs the work at pickup. This local route prevents duplicate filings and re-filing a declined remedy without making the Steward the solution's owner.

**A product defect remains that product holder's to file in the product repository, with the product harm named.** The lab coordinates the practice; it does not absorb a product's work.

## The standing page

[#683](https://github.com/Grimblaz-and-Friends/tradecraft/issues/683) stays the lab's one standing page, the standing issue for the cross-change read and the intake address. **Its body is the pickup part:** the rulings a holder applies, an index linking every other part, and how the page is used. **A session reads the body at pickup,** follows a link only when it needs a part, and takes work by its issue. Six parts each live in one Steward comment on #683, edited in place: the Steward's part, the latest read, the ready list, in flight, the traps and the residues. **The Steward's part holds only rulings that bind only the Steward, rulings waiting on the owner, and what the Steward owes; a ruling a holder applies stays in the body until it retires.**

**Every entry holds only what applies now:** what to do and the record it rests on. Its history, evidence and incidents go on its own issue, an earlier read's summary stays on that read's note, and a ready entry is one line: the issue, its defect in plain words, and its place. **Each part, the body included, is held to 20,000 bytes,** so a session reading one part never loads the rest; a part over the limit shows the Steward's reason until it is back under.

**Every Steward edit of the body or a part goes through `tools/steward_page.py`, entry by entry, and the Steward writes no one-off page scripts.** The one edit made by hand is the repair of a part the tool reports as faulty, which the Steward then records with the tool's `accept`. The Steward updates the page after each read, ruling and pickup. At each cross-change read at the latest, every entry whose change has landed, whose ruling has retired, or that was declined leaves the page, posted word for word as that read's one comment on the closed archive issue, so nothing the owner ruled disappears without a searchable record. **A ruling retires only when its carrying change lands.** A ruling whose change closed without landing is re-pointed or kept with its reason before the read's archive runs, and a ruling with no carrying change stays until the owner retires it.

## Wake, handover and cover

The Steward stays one standing session that the owner and holders message by name, and three mechanisms keep it answering without a model call while nothing is new (#890). Every lab GitHub write uses the owner's account, so author cannot tell the Steward's posts from intake; a marker can.

- **Mark every post and move the watermark.** Every comment the Steward posts on #683 opens with the Steward marker: a note goes through `tools/steward_watch.py post`, and a part comment through `tools/steward_page.py`, which posts it by the same route. One marked comment, the watermark, records the last page comment the Steward has handled, the last read with its cutoff, and the alert issue. An unmarked comment above the watermark is unhandled intake, so once a comment is handled the Steward moves the watermark with `handled`, and after each read note it records the read with `read-recorded`.
- **A wake turn names its trigger.** The `steward-wake` mod reads GitHub every five minutes with no model call and starts one turn per new trigger: a read that has come due (the fifth merge across the lab since the last read's cutoff) or a new intake comment. The turn's text names which, and the Steward acts on it as it would on a message. The mod is enabled at local scope in tradecraft's main checkout, so it loads in every tradecraft desktop session, but it starts only in the session titled `Steward`. Its code, the script it runs and the cover all come from the Steward's own checkout, so the Steward fast-forwards that checkout after each tradecraft merge.
- **Hand over at 250,000 tokens through the state file.** Past that size, at a quiet moment (no turn running or queued, nothing in the background, nothing from the owner in the last hour), the mod asks the Steward to write a state file holding only what the four records below do not carry, then clears the session in place and queues a turn that resumes from that file. Clearing in place keeps the name "Steward", so holders reach it as before. If the clear is refused, the Steward asks the owner to type `/clear` and keeps the state file current until he does.
- **Tell the owner when the cover is stale.** An hourly task on the owner's machine, with no model, has a tradecraft workflow mention the owner on the alert issue when intake has waited more than an hour or a read more than three hours. When more than two hours have passed since the later of the cover's registration and its last success, the mod says so in the Steward's next turn, and the Steward tells the owner, because a silent cover looks the same as an answered lab.

## The handoff

A replacement or resumed Steward reads #683, the Steward's memory store, the open issues and the owner board, and the handover state file when one is present, then continues. The memory store is an inbox for retained judgment, not the lab's archive; #683 and the open issues carry the load-bearing state, and the state file carries only what a handover leaves in flight. Nothing the role needs may live only in a session, and a Steward that cannot be replaced from those records has left the record wrong.

# D-997 — A flag may name several lines

**Purpose:** record why #958 lets a cold reader's flag name several lines or ranges of one file, why a holder accepts such a flag only by its whole location, why an `open` quoting a refused return now says so, and what that does to returns refused before it landed. It also records the calls made inside the brief's rows. **Audience:** a future session changing the cold reader's account form, the acceptance line, or how the gate counts stored returns. **Success:** that reader can recover what was chosen over what without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/958#issuecomment-6803149480) governs. Its pre-implementation artifact was [settled on the would route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/958#issuecomment-6803716503). The lane is ordinary / connected, and no panel was bought. This record supersedes none; it changes what one sentence of [D-952](D-952-2026-11-04-the-cold-reader-reads-each-change.md) means, below.

## The fault

The reader was told a flag's location only as `path:lines`, while the form check took one line or one range. Readers naming one finding at several places wrote a comma list, and the check refused the whole return for it, so a paid reading was discarded for a form nobody had stated. A holder who then posted that return whole in an `open` was told its account "differs from every retained cold-reader return", because the gate dropped refused returns before comparing the quote; on one product change the holder found the real cause only by calling the form check by hand.

## What was chosen over what

- **Accept lists, over forbidding them in the reader's instruction and keeping the check** (the owner's ruling, 2026-11-11: "Accept lists"). The gate holds and clears a flag by its file, never by its lines, so a list owes the gate nothing more. The owner was told the case against: a flag naming many places is accepted or routed as one unit, so a holder can't accept some places and route others.
- **Part of a list names no flag in an acceptance line,** over accepting the whole flag from part of it or splitting it into one flag per place. The gate keeps no record of a flag's separate places, so accepting part of one would need a second kind of flag. A holder who would accept some places routes the flag and says which places in its review.
- **Every other malformed flag line still refuses the whole reading.** Whether one bad line should discard a reading at all was left alone; the reading whose flags carry indented sub-points stays refused.
- **Earlier refusals are left to count, over keeping them refused by a new record** of each stage's verdict. Keeping them would need that record and a rule for which check governs, to preserve refusals that were the defect.

## What D-952's sentence now means

D-952 says: "A return the stage refused for its form is skipped, because it was never a reading." The gate has never kept the stage's verdict: it judges every stored return with the current form check each time it runs. From this change on, that sentence means a return **the current check** refuses. A return the stage refused only for a comma list counts as a reading from this landing, and one that is its change's newest reading is owed its `open` like any other. The comment beside the skip in `lib/work.py` says the same.

## Calls made inside the rows

- **Any run of spaces or tabs after a comma, none before one.** Row 1 says "with or without a space", for leniency on stray formatting, and the check's other separators already take a run.
- **An acceptance names a list flag when its items are the flag's items in the same order,** compared after dropping whitespace and reading an en dash as a hyphen. A reordered list names no flag, like a partial one.
- **The refused-quote reason** is `cold-reading account quotes a cold-reader return the form check refuses, so it is not a reading: <first form error>`. Where the account matches several refused returns, the latest completed one gives the error, and a counted reading always wins.
- **Only a refused return that passes a reading's filters is named:** this pull request's lineage, completed before the `open` was posted, and, for a return recorded without lineage, this change's history holding the head it read. Any other is "differs", as before.
- **`skills/work/SKILL.md` is not edited.** Its sentence that a malformed flag line fails the stage stays true; the forms live in the reader's prompt and in the marker reference.

## The store when this landed

The holder judged this machine's retained cold-reader returns at 2026-11-11T21:27Z with the check on `main` (`2abdc8c`) and with this change's check (`ef905f8`):

- 174 retained returns; `main`'s check refused 20, this change's refuses 1.
- The 19 that now count held 56 malformed flag lines between them, every one a comma list of lines and ranges, and all 19 say `Can tell: yes`.
- No return `main` counted is refused by this change's check.
- All 1,354 flag lines `main`'s pattern parses parse to the same path, lines, kind and text under this change's.
- The one return still refused is #918's, whose flags carry indented sub-points.
- The largest list among the 56 names 20 places.

The tests are in `lib/tests/test_cold_reader.py`: the list forms and near-misses, the parse table of the forms that parsed before, the prompt, whole-list and partial acceptance, the release report's rows, the refused-quote reason and its lineage and history filters, and a newest once-refused return being owed its post.

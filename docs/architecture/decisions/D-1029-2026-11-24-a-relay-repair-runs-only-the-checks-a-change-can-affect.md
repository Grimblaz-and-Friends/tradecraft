# D-1029 — A relay repair runs only the checks a change since their last run can affect

**Purpose:** record why #901 has a relay build or repair turn scope the checks it runs itself, who decides the scope, and the calls made inside the brief's rows. **Audience:** a future session changing what a composed build, floor or reviewer-disposition turn runs and returns, or what the holder accepts before readiness. **Success:** that reader can recover what was chosen over what without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/901#issuecomment-7149217641) governs. Its plan was [settled on the would route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/901#issuecomment-7149492081). The lane is ordinary / connected, and no panel was bought. This record replaces the every-turn rerun that [D-850](D-850-2026-10-04-declared-ci-floor.md) introduced ("run remaining builder-executable checks" at every build or repair) and supersedes nothing else in it. [D-885](D-885-2026-10-10-version-and-row-accounting.md)'s accounting by affirmed row on the mechanical lane stands, its renewed results after a repair now being the renewed account this record describes.

## The fault

The composed paragraph told the builder to run every builder-executable check at the end of every turn, and nothing scoped a repair. On Daemon #86, as the issue records, a repair committed a small fix, re-ran a 25-minute capture and was stopped at the stage's 3,600-second limit; its return was lost and a resume recovered it, about 42 extra minutes. The interim rule had the holder name the affected checks in a note on every repair.

## What was chosen over what

- **The relay route's composed sentence and its prose copies, over also changing the builder route's re-run rules, and over closing #901 and keeping the interim ruling** (the owner's "Yes, all three"). No change has yet run a repair on the builder route, and #1011's comparison is where that cost will show.
- **The builder decides which checks a change can affect, with a reason for each it carries, over a holder's note on every repair, and over a plan that declares each check's inputs for the entrance to compute.** The builder knows what it changed, and these are checks it already runs on its own work, so the scope hands it no independent check: a fresh reader's check stays the holder's to launch, and CI runs every committed test at every head. A holder's note naming a check always wins.
- **A check is scoped by everything since the revision it last ran at, over the turn's own changes** (the Steward's review of the draft). A turn stopped before its checks, or a merge of the base, would otherwise leave an affected check carried.
- **No time budget for long checks.** Scoping removes the repeat.
- **No check by the entrance of the builder's scope.** The record is the builder's reasons and the holder's reading of them.

## Calls made inside the rows

- **One text for a first build and a repair.** Row 1 states one condition for both, and a first build has no earlier result, so it runs everything.
- **"No earlier result" means none the builder can cite by revision,** whether from its own return or one posted on the change, so a session that took a change over and can find no such return runs the check.
- **In doubt, run it.** Row 1 turns on "can affect", and a builder that cannot rule an effect out has not shown the check unaffected.
- **A holder's note is a holder reading carried in the dispatch, or the holder's own dispatch text,** the two carriers the relay route has. On the mechanical lane the composed prompt carries no readings, so a note there travels only in a holder-written dispatch.
- **A note binds the turn it comes with** (from the connected reviewer). Every holder reading after the settlement is carried into every later composed turn, so a note obeyed on every turn would rerun its long check on each one; the builder skips a named check that an earlier turn of its own already ran after receiving that reading. On the mechanical lane the note goes in a dispatch the holder writes, which must carry the end-of-turn account itself, because the composed prompt there carries no reading.
- **One function writes both lane wordings,** so they cannot drift; every sentence the brief didn't touch is kept word for word.
- **The work cell's summary paragraph is edited too,** though the brief names two references, because leaving it would have the summary contradict the references it points to. The lab's landing cell already speaks of the holder's accounting rather than of reruns, and is left as it is.
- **The fixture's `holder` arm has no `prompt` and no `verify`.** It has no builder turn to compose, and a holder may meet a false reason by asking the builder for the run, which no log can show; its session's report is read instead.

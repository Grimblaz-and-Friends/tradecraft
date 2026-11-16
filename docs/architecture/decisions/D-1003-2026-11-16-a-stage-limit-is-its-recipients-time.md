# D-1003 — A stage's limit is its recipient's time, and the entrance's own work before the launch has its own cap

**Purpose:** record why `--timeout-seconds` now names the time a stage's recipient gets, counted from its start; why the entrance's and its launcher's work before that start has a separate cap; what of D-840 this replaces; and the calls made inside the brief's rows. This is the second of two pull requests for #978, carrying its rows 5 and 6. **Audience:** a future session changing a run's deadline, where a launch's window opens, how a recipient is allotted its time, or what a run prints before it starts. **Success:** that reader can recover what was chosen over what without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/978#issuecomment-6814859608) governs. Its pre-implementation artifact for this instalment was [settled on the cap route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/978#issuecomment-6908197526) after two `would not` verdicts, with no affirmed row changed and no owner ruling needed. The lane is ordinary / connected, and no panel was bought. This record keeps [D-998](D-998-2026-11-12-the-entrance-does-its-pre-launch-work-once.md) as it is and replaces one sentence of [D-840](D-840-2026-10-03-interrupted-launch-continuity.md), named below.

## What went wrong

One limit covered the entrance's work and the recipient's since #833, because the holder's shell stopped commands at two hours. That stop is gone in the runtime the lab's holders use, and the entrance's time came out of the recipient's unseen: a build that declared 7,200 seconds was allotted 2,956 after a 69-minute preflight and was stopped mid-turn; a cold reader was launched with 5 seconds; another build got 735 of 5,400; a floor declared at 10,800 seconds refused after 59 minutes with nothing launched, its holder believing it had three hours.

## The owner's rulings

- **What a stage's limit covers.** The holder put A (the limit is the recipient's time, with the entrance's work capped separately) and B (one limit for the whole run, plus a refusal when too little is left), and recommended A. The owner ruled "Recipient only" and "A is good, and we can start with 15 minutes".
- **A larger cap for one run,** with its reason, over no way past the cap: without it a loaded machine or a very large repository could run no stage until a release changed the figure. The owner affirmed it as put.

## What of D-840 this replaces

D-840 is not edited. Its sentence "The caller declares its actual limit; one deadline includes preflight, fallback and recording" is replaced by: the declared limit is the recipient's time from its start; every recipient a launch starts gets it whole, and an attempt spawns only by the cap's end; the entrance's and launcher's work before the recipient has its own cap; the reserve follows the limit; and the run prints the latest time it can return.

Everything else in D-840 stands: the retained session and continuation after a stop, Git content as the progress rule, the build-only budget with its accounting and override reason, the reserve's formula (now over the allotted time), the checkpoint interval and margin, the hard-kill capture guarantee, and the reserve that lets a launcher stop and complete its record before its caller kills it.

## A run's two phases

One `Deadline` holds both. Before the recipient starts, its end is the printed latest return (the call plus the cap, the allotted time and the reserve), reads are cut at the cap's end, and `require_cap` checks before each step that must reach the spawn by the cap's end that enough of the cap is left for it, and a read or write the cap's end cuts refuses the same way. When the recipient starts, `open_window` sets the end to that start plus the allotted time plus the reserve, so the part of the cap the run did not use is not spent and the work after a recipient stops keeps the one reserve it had before. A window opened after the cap's end, which only a machine suspended between two bounded steps can cause, keeps the printed time and is recorded.

## Calls made inside the rows

The holder decided each of these; none changes an affirmed row.

- **C1, every recipient gets its whole limit, and an attempt spawns only by the cap's end.** Each spawned attempt opens its own window. A seat's fallback whose turn comes too late to reach its spawn by the cap's end is not started and is recorded unavailable, naming the cap. Set aside: one window shared by a seat's attempts, which would start a fallback after a spawned primary with only the rest of the window, a case the brief's closed list of exceptions does not name. Its cost: a primary that runs long and then returns unavailable can leave no fallback.
- **C2, an attempt that spawned nothing opens no window and names no spawn.** It withdraws the window, drops its spawn interval, and the next attempt's interval keeps its preparation. Nothing started, so nothing is owed a limit.
- **C3, a cloud recipient starts at the send:** the routine fire, or the follow-up's `--cloud` send, the last act the launcher controls. Set aside: opening at the fire's answer, which could let a slow answer push the start past the cap after the check. A follow-up's split is stamped at the send, because its request record is first written after it.
- **C4, a local launch's last cap check is at the request record's first write,** with an allowance for every attempt's steps before its spawn (20 seconds for a version read, 120 for a compared before-snapshot, and a 5-second margin). The request record is written before the before-snapshot so a stopped launcher leaves a record (D-998), and a refusal after that write would leave a bundle. Set aside: no allowance, with the before-snapshot cut at the cap and its unreached items recorded `uncompared`.
- **C5, the entrance follows the window through a launch notice** the launcher writes when it opens or withdraws its window. Set aside: waiting to the latest end, which would keep a launcher hung after an early spawn alive for the unused part of the cap.
- **C6, the return-time line goes to standard output, first,** where the holder already reads the stage's report.
- **C7, a declared cap must exceed 900 seconds.** A smaller one would shorten a run, which the brief does not name; a caller stopped at a fixed time declares its limit less the cap and the reserve.
- **C8, a write begun before the window is not cut at the cap's end,** only where it would outlast the printed return less the reserve, and none begins after the cap. Set aside: cutting every write at the cap's end, which leaves half-made worktrees and pushes at every default limit.
- **Every declared cap is recorded** in a file under the entrance's records before the run's first read, with its outcome added once known, so a refusal at the cap, which leaves no bundle, still leaves the holder's reason; `run release-report` lists every one.
- **The run's clock starts at the process's creation** where the platform gives it, so module loading counts in the split; a split says which start it used.

## Not this

- The default limits, the 14,400-second build budget, the ceiling's length and the reserve's formula.
- The launch comparison's after-walk and final write keep the time they had (#984, #989).
- The limit running out inside a stage's own work, as in a `run catch-up` merge, behaves as before.
- Nothing is kept between runs; sessions are not kept warm; the vendor program's own start is shown, not shortened.

The tests are `lib/tests/test_978_window.py`, `lib/tests/test_978_clock.py`, `lib/tests/test_978_wait_tick.py`, `lib/tests/test_978_launch_window.py`, `lib/tests/test_978_seat_window.py`, the `test_978` tests in the scale, split and cloud-build suites, and the changed expectations in the run-lifecycle, launcher, cloud-build and recovery suites.

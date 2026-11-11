# D-983 — A waiting session kept warm

**Purpose:** record why #983 keeps a waiting local Claude builder or author in the model's one-hour cache with an outside resume that saves nothing, how that resume is bounded, and which approaches were dropped. **Audience:** a future session changing `lib/keep_warm.py`, the launcher's start and stop calls, the cost report's keep-warm line, or the lab's desktop keep-warm mod. **Success:** that reader can recover what was chosen over what without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/983) governs; its pre-implementation artifact was [settled on the cap route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/983#issuecomment-6790407877). The lane is ordinary / connected, and no panel was bought. This record supersedes none.

## What was chosen over what

- **Keep idle sessions warm, over making waking cheap** (the owner, 2026-11-10: "A, keep warm"). Shrinking a session before it waits, or sending a small late turn to a fresh session, was not built.
- **An outside resume that saves nothing, over an in-session turn,** for local builders and authors. `--no-session-persistence` leaves the transcript and the session's running total as they were; a premise run read 105,244 tokens and wrote none. A desktop session can't be reached that way (an outside ping read nothing and wrote all 162,530 tokens), so the lab's desktop mod submits a short visible turn instead, by the owner's ruling (2026-11-11: "Yes, both").
- **Tools refused by a hook, over a flag.** Every tool-list flag changes what the model is sent, so the ping would write its conversation again.
- **The stop at the launcher's start, over the stage call.** The wait between a stage call and its launch ran 35 to 69 minutes in the record (#978).
- **A cap of eight hours.** Counting every unreturned session as pinged for the whole cap, the four-week net saving peaked there.
- **A ping that reads nothing is a miss whatever it wrote,** and otherwise a write above the larger of 20,000 tokens and 5% of the read. The allowance absorbs the one-time write at a session's first resume without hiding a lapsed or mismatched cache.
- **An unreadable change state is read once more a minute later before it ends keep-warm** (the holder's reading before the build): one GitHub read timing out and answering a minute later was observed on the day.
- **The entrance starts the runner, after its own cleanup.** On Windows through WMI, with the environment in memory and no window; on Linux and macOS by a double fork. No platform needs a user service manager. macOS survival is a premise the first macOS run settles; a runner that dies anywhere is recorded `runner-gone`.
- **A ping is a row in the change's cost records, never a launch record,** so it is never selected as the latest launch and owes no comparison or account.

## Rejected

- **A shim directory named by session,** so its path would not vary between turns. A different instruction path does not cost the cache, so the change to real launches bought nothing.
- **Leaving an accepted author without keep-warm,** on the reading that its next turn's new directory would miss the cache anyway. A resumed turn in a different directory, and a ping from one, read the cache.
- **Starting the Linux runner with `systemd-run --user`, and running no keep-warm where no user service manager answers.** The entrance can start the runner after its own cleanup with a double fork, which needs no service manager and leaves no platform out.

## Calls made inside the rows

- **The entrance names a start token.** It cannot know the launcher's dispatch id before the launch, so it passes `--keep-warm-token` and starts the spec whose `start.pending` carries it.
- **A shim placed outside its original directory imports the ping directory's `AGENTS.md` by absolute path.** A relative import resolves only from its own directory; the absolute form is the launcher's own second placement.
- **The desktop mod refuses tools through the mod API's `tool.call` hook during its own turn,** with the core's turn-end check as a second line.

The tests are `lib/tests/test_keep_warm.py`, the keep-warm tests in `lib/tests/test_change_cost.py` and `lib/tests/test_work.py`, and `tools/tests/test_keep_warm_desktop.py`.

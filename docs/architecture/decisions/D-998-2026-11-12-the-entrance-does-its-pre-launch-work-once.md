# D-998 — The entrance does its pre-launch work once, contains each read directly, and says where that time went

**Purpose:** record why the entrance now does each piece of its work before a launch once in a run, contains each read without a second process, names a time-out as time running out, and prints how long it took before the launch and on what; what the launch is for that split; and the calls made inside the brief's rows. This is the first of two pull requests for #978, carrying its rows 1 to 4. **Audience:** a future session changing how the entrance reads the dispatch store, measures removals, finds a change's pull requests, contains a read, or times its own work. **Success:** that reader can recover what was chosen over what without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/978#issuecomment-6814859608) governs. Its pre-implementation artifact for this instalment was [settled on the cap route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/978#issuecomment-6816161484) after two `would not` verdicts, with no affirmed row changed and no owner ruling needed. The lane is ordinary / connected, and no panel was bought. This record supersedes none. It keeps [D-840](D-840-2026-10-03-interrupted-launch-continuity.md)'s guarantee that one caller deadline bounds a run and stops a hung read with what it started, by another route on Windows; it changes how often [D-872](D-872-2026-10-06-build-reach.md)'s removals count reads Git, not what it reports; and it leaves [D-996](D-996-2026-11-11-one-overlap-list-and-one-allowance.md)'s and [D-939](D-939-2026-11-03-claude-launch-writes-stay-in-their-tree.md)'s reads of the store in the launcher as they are.

## Two pull requests

The owner ruled "Two, speed first" over one pull request for all six rows; the holder had given him the case against, a second pass through review and proof for protection more than relief. This one carries rows 1 to 4 and changes no flag's meaning. The second carries rows 5 and 6, which make a stage's limit the time its recipient gets, with the entrance's own work capped separately, and count a floor's and a review disposition's ceiling from the launch; it gets its own artifact and its own record. Until it lands, a slow entrance can still leave a stage a short window; rows 1 and 2 make that rarer.

## What was slow

Measured on #938, 24 builder turns, at `lib/` at `8c411e9`:

- A read-only decide took 434 to 572 seconds. It ran the removals count twice, 1,884 Git processes each time, and 1,998 of its 3,780 reads were one process per file version.
- It rescanned the whole dispatch store 90 times, for 489,916 reads of request and run records and 281 seconds of the launcher's own time.
- Every decide listed every pull request the repository has had.
- A launching stage ran the removals count once more between composing its prompt and launching.
- Inside a named stage each read started a Python worker that then started the command: 381 ms against 63 ms direct on a quiet machine, 3,679 ms against 239 ms on a busy one. A named stage took 2,368 seconds to refuse where the decide took 434 to 572 for the same reads.
- When a proof stage's hour ended inside the removals count, every unread turn said "commit object … unavailable: fetch that revision", 53 times in one output, and holders fetched revisions they already had.

No record said where the time before a launch went, so finding these took a spike.

## What was chosen over what

- **Each piece of work once per run, in one run scope, over a memo inside each reader.** The scope opens at the entrance's entry and in each launcher and lasts only for that process. A memo that only one reader used would leave the other readers rescanning; the standing test fails on any record read twice.
- **Request records read once and run records only when a reader selects their bundle, over reading every record once.** On the lab store the request records were 18.2 MB and the run records 218.9 MB. A bundle needs both records to count anywhere, so reading the request first changes no result.
- **The issue's own references, over the repository-wide pull-request listing.** Candidates come from the issue itself, authorized `implementing-pr` markers, the issue's timeline (same-repository pull requests only) and GitHub's closing-reference graph, each kept only if its current body closes the issue by today's rule. The listing's cost grew with every pull request the repository ever had. A missed candidate would read as no pull request and start a second builder, so both the timeline and the graph are read.
- **A parent-held kill-on-close job on Windows, over the worker process.** The read starts suspended, is assigned to a job whose handle it does not inherit, and is resumed with `NtResumeProcess`; closing the job on every return removes whatever the read started. The spike measured it at 32 ms against 31 ms plain and 293 ms through the worker, and the grandchild was gone at the bound. `NtResumeProcess` is undocumented and the spike ran on one machine outside any sandbox, so where the job can't be set up the read takes the worker route and the run's `read_route` says so, never an uncontained read.
- **`RunTimeout` as a `TimeoutError` subclass carrying a limit phrase, over new message texts.** Callers and tests match on the existing messages, so they stay; the phrase is added where a time-out is reported. `limit_phrase` is the one place a limit is named, so the second pull request's cap and counted-from-launch ceiling add phrases without touching these call sites.

## The launch, and the split's two intervals

In this practice's records the launch is the launcher's first write of the request record. `launched_at` is stamped earlier, when the record is built, and between the stamp and the write the launcher adds launch controls, the write bound and its self-test, the launch snapshot and, in the implementer launcher, the runtime version and the revision before. Both come before the comparison's before-snapshot and the recipient's spawn.

So the split has two intervals:

1. **The request record's split** (`until: request-record`) runs from the call to that first write, and is carried in the write. It ends at the write rather than at the stamp so the reads between the two are counted.
2. **Each spawned attempt's `pre_spawn_seconds` and `pre_spawn_parts`** run to the attempt's spawn: the before-snapshot and, in the seat launcher, the attempt's version read. The first attempt is measured from that write and each later attempt from the end of the attempt before it, when that attempt's recipient returned, because a recipient's run is not the launcher's work; counted from the write, a fallback's interval would carry the whole primary run. An attempt that spawned nothing starts no new interval, so its preparation is counted in the next.

Together they run from the call to the recipient's start, the interval the second pull request will cap. After a launch returns, the entrance prints `until: spawn`, the request record's split with the first spawned attempt's parts added part by part; where no attempt was spawned, it prints the request record's split as written (`until: request-record`); a decide or a refusal by the entrance prints `until: report`, and a launcher that refuses before writing its request record prints its own `until: handoff` line on the standard error it shares with the holder, which the entrance neither reads nor repeats: its own line after that refusal reads `until: report`. The parts are `github`, `removals`, `markers`, `launch_preparation` and `vendor`, the innermost part winning, with the rest `unattributed`.

Set aside:

- **Writing the request record later, after the before-snapshot, so one interval reaches the spawn.** A launcher stopped during the snapshot would then leave no request record, the loss #833 fixed, and the comparison covers the run's own request record, which must exist first.
- **Ending the split at the `launched_at` stamp.** The reads between the stamp and the write would fall in no interval.
- **Moving `launched_at`.** D-996's overlap list reads it as the run's opening.
- **Measuring every attempt from the request record's write.** A fallback after a primary that ran for its whole window would report that window as the launcher's own work.

## Calls made inside the rows

The holder decided each of these; none changes an affirmed row.

- **C1, the vendor program's own start, is its processes before the launch:** its version read, its plugin list and its configuration discovery, each of which starts the vendor program. Over measuring from the spawn to the vendor's first event, because that falls after the launch, inside the recipient's own time, so it can't be a part of a split that ends there. Removing the worker around those reads does not shorten the vendor's own start, which the brief leaves as it is.
- **C2, all four candidate sources,** over the timeline alone. The timeline sufficed in every case probed, including the pull requests whose closing reference was added in a later edit (#952 for #942, #726 for #669 and #685); the closing graph costs one GraphQL read and covers a case the timeline might miss, where a miss starts a second builder. #938's timeline carries a pull request from another repository, so the same-repository filter is needed.
- **C3, the store index lists again after a child that is not a read returns, which is where the run's own records are written (its launcher),** over relisting before every read or never. Only those events change what this run's questions depend on; records other runs write in between are not this run's evidence, and today a run likewise sees the store only as it stood at each read.
- **C4, the decide's reads go through the contained route too,** over leaving them on an uncontained `subprocess.run`. Row 2 covers every read the entrance makes; the decide and a named stage then start the same processes, and a hung decide read no longer leaves a child behind.
- **C5, the POSIX route stays as it is.** A contained read there already starts no second process (a process group and its descendants), so row 2 only extends that containment to the reads that were uncontained.
- **C6, one `git cat-file --batch` per diff inventory, read one blob at a time through a streaming read,** over one `cat-file blob` process per blob and over collecting the batch whole. A turn's processes then grow with its commits and merges rather than its files, and memory stays bounded by the largest blob, as before. Where Windows containment is refused, binary detection falls back to one contained read per blob.

## Not this

- Nothing is kept between runs, and the dispatch store is not pruned or re-laid-out (#705).
- The launch comparison's before-snapshot, overlap list and after-walk keep their own reads in the launcher, at another moment and for another question, and their allowances (#984, #989).
- The vendor program's own start is shown, not shortened.
- The recipient's own launch, Codex configuration discovery, the cloud vendor command, child scripts that are not reads, and the connected reviewer's workflow keep their routes.
- The Git writes the cloud route and the recipient tree make (`push`, `fetch`, `merge`; `init`, `config`, `commit`, `checkout`) take the contained route with `writes=True`, over an uncontained route of their own, so a hung write is stopped with what it started. A read held open past its end is refused as cut short, but a write that exited 0 has already happened, so it is judged by its exit status and stands, with `output_complete` false.

The tests are `lib/tests/test_preflight.py`, `lib/tests/test_978_reads.py`, `lib/tests/test_978_store_index.py`, `lib/tests/test_978_work.py`, `lib/tests/test_978_split.py`, `lib/tests/test_978_scale.py`, and the `test_978` tests in the removals, cloud-build and both launchers' suites.

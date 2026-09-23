---
name: work
description: The single state-driven entrance for a product change. Use when the owner names an issue to work on or continue; use its stage commands only when a power user deliberately wants one stage. Not for deciding whether work is worth doing, changing an affirmed brief, choosing vendor defaults, merging, or answering an owner ask.
---

# work

**Purpose:** turn one issue number into the next stage its GitHub evidence calls for. **Audience:** the holder continuing an affirmed product change, and a power user running one named stage. **Success:** the issue and its linked pull request are read without mutation, exactly one next stage is selected, and no recipient is instructed to continue into another stage.

## Where this cell's depth lives

- **Recording or reading evidence that advances the entrance** → `references/markers.md`: each marker's exact form, lawful values, producer, surface and moment.

For the ordinary entrance, run:

```text
python <plugin-root>/lib/work.py --repo OWNER/REPO --issue N --root HOLDER_PATH
```

The fifth merge across the practice's repositories since the last cross-change note, or the status read of a running evaluation, calls for engagement's read across landed changes.

In this repository, `<plugin-root>` is the repository checkout root. For an adopter, it is the installed plugin directory containing `lib/work.py`. `--root` is always the holder checkout: it supplies `.tradecraft/work.json` and `lib/use-rules.json` and anchors the registered implementation root, but is never itself the implementation root.

## Decide, then run on the holder's word

The ordinary entrance performs GitHub GETs and local reads only. It does not sweep or write the registry, create a directory or worktree, publish a branch, write a dispatch file or invoke a launcher. Its JSON report carries the schema version, `work`, `producer_version`, next stage, continuity, reason, detail, holder/runnable/waiting/terminal status, lawful and invalid marker claims, and the latest run selected for every exact check name. For checks, `started_at` and then numeric run id choose the latest run; an older conclusion never defeats a newer success or pending run.

Run a stage only when the holder says to:

```text
python <plugin-root>/lib/work.py run STAGE \
  --repo OWNER/REPO --issue N --root HOLDER_PATH \
  --holder-session-id ID [--dispatch FILE]
```

`STAGE` is `artifact`, `cold-seat`, `build`, `floor`, `use`, `review-disposition` or `release-report`. The named stage is authority: `run` validates and performs exactly it, without requiring it to equal the recommendation or advancing after the return. `--holder-session-id` is required when an implementer is launched or resumed. A holder-supplied dispatch must be outside the registered implementation root and reaches the launcher byte-for-byte; otherwise the composed implementer prompt carries one-stage bounds, the exact affirmed brief, the latest artifact, compact stage facts and explicit `gh api --method GET` commands, never the issue or pull-request record.

Every decision and dispatch request records `work` and the producing plugin version. Before any registry mutation, branch publication, temporary root or launch, `run` checks the named stage's safety table. A refusal names the stage, found version, minimum version and missing mechanism. A resumed stage uses the latest matching successful bundle first; an unsafe or unstamped bundle refuses and never falls back to a session marker. Only when no matching bundle exists may the authorized `builder-session` marker supply continuity.

Marker claims are validated against their existing contract before they advance the decision: producer, surface, exact attributes, lawful values, required prose and unambiguous identity must hold. Claims produced by a dispatched stage must also agree with the latest matching successful bundle completed before the marker. Builder session, floor head and pass, and cold/use staffing therefore come from their run records rather than from marker text alone. The exact contracts remain in `references/markers.md`.

## Roots and holder-owned endpoints

A fresh `run build` creates and registers the implementation worktree, publishes its entrance-created branch to the uniquely selected remote, sets its upstream and verifies the remote head before launching. The builder commits and pushes there, then returns; when its lawful session marker exists without a pull request, the next report is the holder-owned `open-pull-request` step rather than another build. Later implementer stages resolve and prove that registered root internally, so the holder command names no protected implementation path. The path-based holder guard remains authoritative: a direct launcher command naming the protected root is still refused.

`run cold-seat` creates an empty temporary repository outside the change, gives it one neutral detached commit and no remote or shared history, and removes it after the seat returns. Its prompt remains the exact artifact, exact brief and cold-check contract, with no fetch command or record.

`run use` requires both the holder's job and a tree produced below:

```text
python <plugin-root>/lib/work.py run use ... \
  --dispatch JOB --tree-metadata TREE.tradecraft-tree.json
```

It validates the adjacent metadata, source revision, detached neutral repository and carried bytes before launching the consumer through `dispatch_seat.py`. `run release-report` launches nobody and returns the report handoff to the holder; it refuses a custom dispatch. Repeating either the ordinary decision or the release-report handoff cannot buy another recipient.

Build a consumer tree with the same door:

```text
python <plugin-root>/lib/work.py tree \
  --repo OWNER/REPO --issue N --root HOLDER_PATH \
  --mode adopter|repository-session --output PATH \
  --path PATH [--path PATH ...] MODE-SPECIFIC-OPTIONS
```

Adopter mode requires one or more `--loading-surface` values. Repository-session mode requires `--front-page` and `--root-instructions` and accepts repeated `--directed-path` values. Repeated `--exclude-record` pathspecs remove records; repeated `--deny-text` probes refuse leaks. The command archives the registered root's clean committed revision, refuses omissions and transformations, compares every regular file's raw object id, initializes one history-free detached repository and writes the work, revision, mode, surfaces, exclusions and verification to adjacent metadata. The holder still inspects the result and characterizes unavoidable residue before use.

The entrance consumes the affirmed brief and recorded evidence; it never decides what work is for, the brief's terms, a vendor or model default, whether to merge, or an owner ask. Ambiguous pull requests, holder reading, ready/reviewer setup, waiting, panel coordination and terminal states return to the holder.

## Registration commands

`release` and `adopt` retain their direct forms and sweep active registrations before their state change. Release makes the selected row inactive without deleting its worktree or branch:

```text
python <plugin-root>/lib/work.py release --repo OWNER/REPO --issue N --root HOLDER_PATH [--instalment VALUE]
```

Adopt proves and registers a holder-named existing worktree without dispatching or deleting another:

```text
python <plugin-root>/lib/work.py adopt --repo OWNER/REPO --issue N \
  --root HOLDER_PATH --implementation-root IMPLEMENTATION_PATH \
  --holder-session-id ID [--instalment VALUE]
```

Where named instalment registrations exist, adopt requires `--instalment`, because omission must not deactivate a sibling instalment. `holder_write_guard=available` records only that the holder checkout declares the full write-refusing hook; without it, revision and status snapshots detect a breach but do not enforce the boundary.

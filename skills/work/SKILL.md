---
name: work
description: The read-only decision and explicit execution entrance for one product change. Use when the owner names an issue to inspect or continue, when the holder runs one named stage, posts generated proof, prepares connected reviewers, or builds a consumer tree; release and adopt remain registration commands. Not for deciding whether work is worth doing, changing an affirmed brief, choosing vendor defaults, merging, or answering an owner ask.
---

# work

**Purpose:** let one holder inspect a change without mutation, explicitly run the stage it names, and build a verified consumer tree through the same door. **Audience:** the holder deciding or continuing an affirmed product change. **Success:** the ordinary invocation reports the evidence and recommended next step read-only; `run STAGE` validates and performs exactly that stage; `tree` builds the declared consumer tree; `release` and `adopt` retain their registration behavior; and no recipient continues into another stage.

## Where this cell's depth lives

- **Recording or reading evidence that advances the entrance** → `references/markers.md`: each marker's exact form, lawful values, producer, surface and moment.
- **Composing or consuming proof, preserving ancestor use, or preparing reviewers** → `references/proof.md`: the proof wire contract, public/declaration split, publication behavior and holder-owned commands.
- **Implementing the independent proof consumer** → `references/proof-fixtures/README.md`: the positive document and semantic rejection cases shared with the gate.

For the ordinary entrance, run:

```text
python <plugin-root>/lib/work.py --repo OWNER/REPO --issue N --root HOLDER_PATH
```

The fifth merge across the practice's repositories since the last cross-change note, or the status read of a running evaluation, calls for engagement's read across landed changes.

In this repository, `<plugin-root>` is the repository checkout root. For an adopter, it is the installed plugin directory containing `lib/work.py`. `--root` is always the holder checkout: it supplies `.tradecraft/work.json` and `lib/use-rules.json` and anchors the registered implementation root, but is never itself the implementation root.

## Decide, then run on the holder's word

The ordinary entrance performs GitHub GETs and local reads only. It does not sweep or write the registry, create a directory or worktree, publish a branch, write a dispatch file or invoke a launcher. Its JSON report carries the schema version, `work`, `producer_version`, next stage, continuity, reason, detail, holder/runnable/waiting/terminal status, lawful and invalid marker claims, and the latest run selected for every exact check name and producer workflow. For checks, `started_at` and then numeric check id choose a genuine workflow's latest run; two workflows sharing a display name remain separate.

An implementing pull request counts only through its own standalone closing reference or the issue's lawful `implementing-pr` marker. While the issue is open, an open candidate wins over every merged candidate because it is the change in flight. With no open candidate, one merged candidate returns a holder-owned state naming that pull request; it is neither a fresh build nor terminal. Multiple candidates in the winning class are refused, and a closed unmerged pull request does not count. A nonempty product list in `.tradecraft/work.json` makes the repository's issues practice-facing and requires a listed product incident unless an affirmed brief has already admitted the work; a missing or empty list disables that check because the practice exists to serve product work. The same file names connected-reviewer and marker-producer logins, so other accounts cannot satisfy review or advance the entrance; where no connected reviewer is configured, no connected review is required.

An affirmed brief counts only with exactly one lawful `Review risk` and `Review lane` pair. Changed paths are matched against the schema-versioned use rules; a bought use requires a current-head use note or a proved ancestor use whose every intervening commit buys no use, while the other branch requires the proof command's current-head no-use carrier. These are evidence guards, not choices the entrance makes.

Run a stage only when the holder says to:

```text
python <plugin-root>/lib/work.py run STAGE \
  --repo OWNER/REPO --issue N --root HOLDER_PATH \
  --holder-session-id ID [--dispatch FILE] [--timeout-seconds N] \
  [--claude PATH] [--codex PATH]
```

`STAGE` is `artifact`, `cold-seat`, `build`, `floor`, `use`, `review-disposition`, `proof`, `ready-reviewers` or `release-report`. The named stage is authority: `run` validates and performs exactly it, without requiring it to equal the recommendation or advancing after the return. The default timeout is 7200 seconds for `build`, because a build must outlast a passing full check and 3600 seconds did not for this change; every other stage defaults to 3600 seconds. `--holder-session-id` is required when an implementer is launched or resumed; pass the runtime's session identifier, or a stable holder token when it exposes none, so launcher and registry keep holder and builder identities distinct. A holder-supplied dispatch must be outside the registered implementation root and reaches the launcher byte-for-byte; otherwise the composed implementer prompt carries one-stage bounds, the exact affirmed brief, the latest artifact, compact stage facts and explicit `gh api --method GET` commands, never the issue or pull-request record.

Every decision and dispatch request records `work` and the producing plugin version. Before any registry mutation, branch publication, temporary root or launch, `run` checks the named stage's safety table. A refusal names the stage, found version, minimum version and missing mechanism. A resumed stage selects its matching bundle and valid session together and checks that bundle's version; matching bundle evidence with no session, an unsupported schema, or an unsafe or unstamped version refuses. Only when no matching bundle exists may the authorized `builder-session` marker supply continuity.

Marker claims are validated against their existing contract before they advance the decision: producer, surface, exact attributes, lawful values, required prose and unambiguous identity must hold. Claims produced by a dispatched stage must also agree with the latest matching successful bundle completed before the marker. Builder session, floor head and pass, and cold/use staffing therefore come from their run records rather than from marker text alone. The exact contracts remain in `references/markers.md`.

Before each entrance launch, `run` maps every implementer stage to `implementer`, `run cold-seat` to `cold-seat`, and `run use` to `use-consumer`; reads that role only from the latest lawful whole-choice override line; and otherwise reads the selected launcher's standing default without changing it. An `ordinary-seat` or `terminal-seat` entry is parsed, validated and resolved, but reaches a launch only when the holder passes those resolved values to `dispatch_seat.py` directly with the marker comment as their source. A role omitted from the latest line, or whose entry names another vendor, takes the selected launcher's default rather than inheriting an older override. Model and effort, their separate sources and their scope are passed explicitly to the launcher. A holder-supplied `--claude` or `--codex` path is validated and forwarded; without one, `run` discovers that runtime and forwards the discovered path. An unavailable executable remains an unavailable attempt rather than acquiring a requested setting as an observed one.

## Roots and holder-owned endpoints

A fresh `run build` creates and registers the implementation worktree below the holder checkout's `.claude/worktrees/`, keeps that parent in the repository-local exclude file so it is neither committed nor shown in status, publishes its entrance-created branch to the uniquely selected remote, sets its upstream and verifies the remote head before launching. The builder stays on that branch, commits and pushes there, then returns; when its lawful session marker exists without a pull request, the next report is the holder-owned `open-pull-request` step rather than another build. Later implementer stages resolve and prove that registered root internally, so the holder command names no protected implementation path. The path-based holder guard remains authoritative: a direct launcher command naming the protected root is still refused.

A merged implementing pull request on an open issue names that pull request and returns the holder-owned decision about what the issue still owes: close it, explicitly run another build, or run a use owed after the merge from a landed commit. A further build is fresh; the entrance does not infer it from the still-open issue, and it refuses while the merged implementation's registration remains active so the holder can `release` that registration first.

`holder_write_guard=available` records only that the holder checkout declares the complete write-refusing `PreToolUse` hook; it does not claim the runtime loaded it. Without that declaration the registration records `unavailable`, and revision and status snapshots detect a breach without claiming to enforce the boundary.

`run cold-seat` creates an empty temporary repository outside the change, gives it one neutral detached commit and no remote or shared history, and removes it after the seat returns. Its prompt remains the exact artifact, exact brief and cold-check contract, with no fetch command or record.

`run proof` and `run ready-reviewers` are holder-owned endpoints and launch nobody. The former composes and publishes the current-head proof from the record and requests a specifically identified gate rerun; the latter applies the optional configured reviewer label before marking the pull request ready. Their full contract is `references/proof.md`.

`run use` requires both the holder's job and a tree produced below:

```text
python <plugin-root>/lib/work.py run use ... \
  --dispatch JOB --tree-metadata TREE.tradecraft-tree.json
```

It validates the adjacent metadata, source revision, detached neutral repository and carried bytes before launching the consumer through `dispatch_seat.py`. `run release-report` launches nobody and returns the report handoff to the holder; it refuses a custom dispatch. That handoff names the required gate verdict at the current head as `green`, `red`, `stale` or `absent`, with the identified run, and a non-green verdict directs the holder to restate the `**Path departures:**` paragraph at that head with the bypass and its reason. It records rather than forbids a bypass, because merging remains the owner's decision. Repeating either the ordinary decision or the release-report handoff cannot buy another recipient.

Build a consumer tree with the same door:

```text
python <plugin-root>/lib/work.py tree \
  --repo OWNER/REPO --issue N --root HOLDER_PATH \
  [--revision COMMIT] \
  --mode adopter|repository-session --output PATH \
  --path PATH [--path PATH ...] MODE-SPECIFIC-OPTIONS
```

Adopter mode requires one or more `--loading-surface` values. Repository-session mode requires `--front-page` and `--root-instructions` and accepts repeated `--directed-path` values. Repeated `--exclude-record` pathspecs remove records; repeated `--deny-text` probes refuse leaks. Without `--revision`, `tree` archives the active registered implementation root's clean committed `HEAD`. With `--revision`, it uses the holder repository without consulting or writing a registration, resolves the named commit, refreshes the selected remote's default-branch head, and refuses unless the commit is an ancestor of that remote head. Metadata always records the exact source revision and whether a registration was used. Both routes retain the same declared-path, loading-surface, exclusion, denied-text, raw-object-id, file-mode, detached-history and clean-tree guarantees. Before use, validation selects the registered source or holder source from the integrity-checked metadata claim, re-proves the recorded revision and carried bytes, and for an unregistered source refreshes and re-proves remote-default reachability. The holder still inspects the result and characterizes unavoidable residue before use.

The entrance consumes the affirmed brief and recorded evidence; it never decides what work is for, the brief's terms, a vendor or model default, whether to merge, or an owner ask. An ambiguous pull request returns to the holder, who records the lawful `implementing-pr` marker or opens the pull request that should exist; holder reading, waiting, panel coordination and terminal states likewise return to the holder.

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

The holder and implementation roots must be distinct top-level worktrees in the same repository, and an entrance-shaped branch for another issue is refused. Where named instalment registrations exist, adopt requires `--instalment`, because omission must not deactivate a sibling instalment.

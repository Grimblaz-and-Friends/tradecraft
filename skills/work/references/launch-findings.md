# Launch findings

**Loaded when** the entrance holds a change on `launch-findings-unaccounted`, its report's `launch_findings` names a held bundle, or the holder quotes a Claude launch's write bound in a release report.

A Claude author or builder can write, and so can a use consumer given a shell. Its file-editing tools (Write, Edit, MultiEdit and NotebookEdit) are confined by a launch-owned check on each target path: a target outside its tree and its own session scratchpad is refused, names the path and fails the turn. Memory is switched off in its process environment, and a file-tool write to the memory store is refused regardless, because the store lies outside both. Shell commands have no OS fence on this route. So every writing launch also compares what it must not touch before and after its run, because a shell write lands and can only be found afterwards.

## What the comparison covers

- the machine implementer switch and the model rulings file;
- the owner's Claude settings, his always-loaded `CLAUDE.md` and the installed plugins;
- the implementation worktree registry, the dispatch store's completed run records and the run's own request record;
- every checkout an active registration names, holder checkouts included, each registered repository's main clone, and the launcher's own plugin root when no covered checkout is that root.

A checkout's comparison leaves out its `.git` and stops at any nested worktree or clone, because every builder edits its own nested tree and commits into the shared `.git`. Edits inside the run's own tree are its own work. A change under the tree of another recorded run whose launch window overlapped this one is that run's, and a registry row naming another holder's session is that holder's only while a recorded run of theirs for that row's work or tree overlapped. Attributed changes stay visible under `attributed`. An item that could not be read or walked in time is an `uncompared` finding, because silence about it could hide damage.

The request's `write_bound` states what applied: the guarded tools and allowed paths, the scratchpad form, the guard's self-test, the memory request and fallback, the planned coverage, and `shell: no OS fence`. The run record's `launch_comparison` carries each item's status and every finding with its `id`; an author's or builder's run record also carries `write_guard` (refusals, calls completed with no guard decision, and calls the runtime rejected before they ran). Quote that bound in the release report.

## The hold

Any bundle for this change whose comparison has findings, or whose request has a write-bound baseline but whose stopped launch left no comparison (`unrecorded`), holds every next stage, the holder-named `run <stage>` included. A launch still running owes no account: its report entry reads `running`, because its comparison is written when it stops, and the live-launch routing governs it meanwhile. The run itself is untouched: a finding never fails or discards it.

The hold releases when a trusted `launch-account` marker for that bundle's dispatch names exactly its finding ids (the `launch-account` contract in `markers.md`). Name each finding's party from what you know, never by default:

- `owner` — the owner changed it;
- `plugin-update` — an installed plugin changed under the run;
- `session` — another named session changed it; give its id in `session`;
- `builder-damage` — the launch's own recipient changed it;
- `none-found` — you inspected what the finding names and found no change needing a party; the `basis` says what you inspected and how.

An `uncompared` finding or an `unrecorded` comparison is not a change anyone made, so inspect before naming a party. For `uncompared`, inspect the item it names; for `unrecorded`, inspect every item in the request's `write_bound.comparison.coverage`. When the inspection finds nothing, `none-found` is the true party; when it finds a change, name the party that made it instead, and builder damage still goes to the owner and the practice.

For builder damage, tell the owner first, who decides any restore. Then file the practice's `product-incident` record as the charter directs for a practice failure. The account names both, in `owner_report` and `practice_issue`. A bundle recorded before this bound neither holds nor clears; the report says `not recorded: launched before #906`.

# Launch findings

**Loaded when** the entrance holds a change on `launch-findings-unaccounted`, its report's `launch_findings` names a held bundle, or the holder quotes a Claude launch's write bound in a release report.

A Claude author or builder can write, and so can a use consumer given a shell. Exactly these launches are bound: local Claude author and builder launches, and the Claude use consumer given a shell. Other Claude seats given a shell are not compared, and Codex launches are unchanged. Its file-editing tools (Write, Edit, MultiEdit and NotebookEdit) are confined by a launch-owned check on each target path: a target outside its tree and its own session scratchpad is refused, names the path and fails the turn. Memory is switched off in its process environment, and a file-tool write to the memory store is refused regardless, because the store lies outside both. Shell commands have no OS fence on this route. So each of those launches also compares what it must not touch before and after its run, because a shell write lands and can only be found afterwards.

## What the comparison covers

- the machine implementer switch and the model rulings file;
- the owner's Claude settings, the owner's always-loaded `CLAUDE.md` and the installed plugins;
- the implementation worktree registry, the dispatch store's completed run records and the run's own request record;
- every checkout an active registration names, holder checkouts included, each registered repository's main clone, and the launcher's own plugin root when no covered checkout is that root.

A checkout's comparison leaves out its `.git` and stops at any nested worktree or clone, because every builder edits its own nested tree and commits into the shared `.git`. Edits inside the run's own tree are its own work. A change under the tree of another recorded run whose launch window overlapped this one is that run's, and a registry row naming another holder's session is that holder's only while a recorded run of theirs for that row's work or tree overlapped. Attributed changes stay visible under `attributed`. An item that could not be read or walked in time is an `uncompared` finding, because silence about it could hide damage.

The request's `write_bound` states what applied: the guarded tools and allowed paths, the scratchpad form, the guard's self-test, the memory request and fallback, the planned coverage, and `shell: no OS fence`. The run record's `launch_comparison` carries each item's status and every finding with its `id`; an author's or builder's run record also carries `write_guard` (refusals, calls completed with no guard decision, and calls the runtime rejected before they ran). Quote that bound in the release report.

**A cloud build is not compared.** A cloud builder runs on a remote machine and cannot reach this one, so its run record's comparison reads `cloud-not-run` with that reason, a clear status that holds nothing; a local build still runs its comparison. The work cell's cloud-builds reference owns the route.

## The hold

Any bundle for this change whose comparison has findings, or whose request has a write-bound baseline but whose stopped launch left no comparison (`unrecorded`), holds every next stage, the holder-named `run <stage>` included. A launch still running owes no account: its report entry reads `running`, because its comparison is written when it stops, and the live-launch routing governs it meanwhile. The run itself is untouched: a finding never fails or discards it.

**A failed cloud attempt check holds the same way.** A cloud attempt whose change-branch check, `[skip ci]` check, practice-check record, `environment` check, permission-mode check or local-tree check failed carries a `cloud-check:<name>` finding, and its account names that id with the `cloud-check` party, whose basis names the check and what the holder verified, except the local-tree check: only the local tree containing the returned branch tip releases it, never an account, because the next stage builds from that tree. The report is still kept and posted.

The hold releases when a trusted `launch-account` marker for that bundle's dispatch, posted after its findings exist, names exactly its finding ids (the `launch-account` contract in `markers.md`). An account posted before the run completed, or for an unrecorded comparison before the launch began, counts for nothing. Name each finding's party by what made the change, from what you know, never by default:

- `owner` — the owner changed it;
- `plugin-update` — the runtime's plugin machinery changed it: an installed plugin, a marketplace, or the runtime's cached plugin or marketplace data was installed, updated or refreshed. This holds whether another process did it or the launched runtime itself did, while starting or running, as long as no tool call or command the launched recipient made did. The `basis` says what shows that, such as the change's timing against the launch's session start and a stream with no tool call that touched it;
- `session` — another named session changed it; give its id in `session`;
- `builder-damage` — a tool call or command the launched recipient (the builder, author or use consumer) made changed it. The launched runtime's own plugin maintenance is not builder damage;
- `none-found` — you inspected what the finding names and found no change needing a party; the `basis` says what you inspected and how.

An `uncompared` finding or an `unrecorded` comparison is not a change anyone made, so inspect before naming a party. For `uncompared`, inspect the item it names; for `unrecorded`, inspect every item in the request's `write_bound.comparison.coverage`. When that coverage is empty because planning it failed, inspect what "What the comparison covers" above lists on this machine, and say so in `basis`. When the inspection finds nothing, `none-found` is the true party; when it finds a change, name the party that made it instead, and builder damage still goes to the owner and the practice.

For builder damage, tell the owner first. A notice the owner will see counts, such as an issue comment addressed to them while they are away; the account does not wait for the owner's restore decision, which stays theirs. Then file the practice's `product-incident` record as the charter directs for a practice failure. The account names both: `owner_report` is the notice's URL, or another exact locator where the notice is not on GitHub, and `practice_issue` is the filing. A bundle recorded before this bound neither holds nor clears; the report says `not recorded: launched before #906`.

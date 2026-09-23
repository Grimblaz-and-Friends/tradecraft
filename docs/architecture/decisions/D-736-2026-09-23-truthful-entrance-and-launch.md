# D-736 — Make completion, landed work, and launch choices explicit

**Purpose:** preserve why the entrance reads Codex completion from its stream, retains merged implementation evidence, admits a landed consumer-tree source, and resolves launch choices before invoking a launcher. **Audience:** a future session changing dispatch interpretation, work-state routing, consumer-tree sources, or per-change launch settings. **Success:** that session can change one mechanism without reviving the four manual routes this decision removes, and can see that no standing model or effort default moved.

Governed by the affirmed implementation brief and settled artifact on [#727](https://github.com/Grimblaz-and-Friends/tradecraft/issues/727), carrying #729 and #730 with #688 folded into the completion rule. The implementation began at `35f67420ecf114dcd2dfa415de53ff66a9ca8489`.

## Context

At the implementation base, the two launchers interpreted Codex separately, the implementer treated every `error` event as fatal, and only its last-message file could supply output. `git show 35f67420ecf114dcd2dfa415de53ff66a9ca8489:lib/dispatch_implementer.py` and the same command for `lib/dispatch_seat.py` demonstrate those paths. `git show 35f67420ecf114dcd2dfa415de53ff66a9ca8489:lib/work.py` demonstrates that the entrance discarded merged implementing pull requests for an open issue, required an active registration for `tree`, and supplied neither explicit model/effort values nor runtime executables to its launchers. `git show 35f67420ecf114dcd2dfa415de53ff66a9ca8489:lib/recipient_tree.py` demonstrates that consumer metadata and validation were bound to the registered source's `HEAD`.

These were four faces of the same fault: the entrance held enough evidence to tell the truth but required the holder to route around it. A reconnect could turn completed work into a failed bundle; landed work could look unbuilt; a post-merge use had no source; and an owner's model choice remained outside the launch.

## Decision

### The Codex stream owns completion without rewriting history

Both launchers use one JSONL interpretation. `turn.completed` with no `turn.failed` is complete; an `error` event is retained and counted rather than promoted to a turn failure. The nonempty last-message file remains preferred, with the last completed stream `agent_message` as fallback. A complete turn with neither records `completed_no_output`, carries its matching reason and publishes no empty return or verdict. Exit status remains evidence and does not override that stream judgment.

Completion records already written remain immutable. Bundle selection reads request and run JSON only; it never reinterprets a retained stream to repair an old outcome. This deliberately leaves the known pre-change error bundles on their recorded recovery routes.

### Merged implementation evidence returns to the holder

For an open issue, candidate selection first considers open implementing pull requests and only then merged ones. Ambiguity is evaluated within the winning class; a closed-unmerged pull request is never a candidate. With one merged candidate and no open one, the ordinary entrance names that pull request in a holder-owned state. It recommends neither a fresh build nor terminal closure, because only the holder can say whether the issue should close or owes another instalment. Explicit `run build` remains the route to that instalment, and refuses until the holder releases the merged implementation's still-active registration.

### A landed commit is a second lawful consumer-tree source

D-726's registered implementation root is no longer the only lawful source. `tree --revision COMMIT` uses the clean holder repository without reading or writing the implementation registry, refreshes the selected remote's GitHub-reported default branch, verifies its remote head, and requires the named commit to be its ancestor. Integrity-checked metadata records the exact revision and `registration_used=false`; `run use` then refreshes the remote-default head and repeats that ancestry proof before re-proving the revision, bytes, modes, neutrality, and clean trees against the holder source. The registered route keeps its existing guarantees.

### The entrance resolves every launch input

The latest lawful `model-override` issue marker is one whole role-scoped choice. It replaces earlier lines rather than merging with them; omitted roles and vendor mismatches use that launcher's standing default. The entrance maps the stage to its role, resolves model and effort plus each value's source, validates a holder-supplied runtime path or discovers one when none is supplied, and passes every selected path explicitly. A judging fallback therefore carries its own value/source pair rather than the primary vendor's override.

No standing model or effort default changed. The launcher constants and their D-645 evidence remain intact; this decision changes how a per-change choice reaches them, not what they are.

## Rejected alternatives and consequences

**Repair retained bundles on read.** Rejected because an immutable completion record and a newly inferred outcome would disagree, and because the known bundles already have explicit recovery routes.

**Treat a merged pull request as active or terminal.** Rejected because it is neither the change currently in flight nor enough evidence to decide the issue owes nothing else.

**Allow any locally reachable revision.** Rejected because a post-merge use judges shipped material. Reachability from a freshly verified remote default head is the boundary that says it landed.

**Merge successive override lines or infer prose.** Rejected because the holder could not tell which old role choice still survived, and a parser would turn discussion into authority. One exact whole-choice marker makes reset and omission visible.

**Leave defaults and executable discovery implicit in the child.** Rejected because the dispatch record would still be unable to distinguish the entrance's choice from child-local discovery, especially across a fallback.

## Meaning changes

- D-726's registered implementation root is no longer the only lawful consumer-tree source.
- An open issue's merged implementing pull request is retained as holder-owned evidence rather than discarded or treated as terminal.
- The entrance resolves and forwards settings and holder-supplied or discovered runtime executables instead of leaving launcher defaults and discovery implicit.
- Dispatch outcome reads Codex completion from the stream while historical bundle outcomes remain immutable.

## Evidence

The stream parser, reconnect, no-output, reason, unavailable-runtime record, and immutable-history polarities are in `lib/tests/test_dispatch_record.py`, `lib/tests/test_dispatch_implementer.py`, `lib/tests/test_dispatch_seat.py`, and `lib/tests/test_work.py`. Merged-candidate precedence, active-registration refusal, exact whole-choice overrides, separate value sources, explicit executable forwarding, creation-and-use landed reachability, registration absence, and metadata integrity are in `lib/tests/test_work.py`; revision-pinned bytes and metadata are in `lib/tests/test_recipient_tree.py`.

Run `python -m pytest lib/tests/test_dispatch_record.py lib/tests/test_dispatch_implementer.py lib/tests/test_dispatch_seat.py lib/tests/test_recipient_tree.py lib/tests/test_work.py -q -p no:cacheprovider`, `python tools/dev.py check`, and `git diff 35f67420ecf114dcd2dfa415de53ff66a9ca8489 -- .claude-plugin/plugin.json` on the tree under review. These commands and test surfaces are the evidence; no derived result is frozen here.

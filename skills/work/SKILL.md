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
python <plugin-root>/lib/work.py --repo OWNER/REPO --issue N --root PATH --holder-session-id ID
```

The fifth merge across the practice's repositories since the last cross-change note, or the status read of a running evaluation, calls for engagement's read across landed changes.

In this repository, `<plugin-root>` is the repository checkout root. For an adopter, `<plugin-root>` is the installed plugin directory containing `lib/work.py`. For the ordinary entrance, `--root` remains the holder checkout: it supplies `.tradecraft/work.json` and `lib/use-rules.json` and anchors the durable implementation worktree, but is never itself the implementation root.

`--holder-session-id` is required whenever the selected stage launches or resumes a builder; pass the runtime's session identifier, or a stable holder token when that runtime exposes none, so the launcher and worktree registry can keep holder and builder identities distinct.

The script reads issue, pull-request, check, review and comment state with GitHub REST GET requests. A pull request becomes the implementing one only through its own standalone closing reference or the issue's explicit marker, and multiple candidates are refused. A nonempty repository-owned product list makes every issue in that repository practice-facing and requires an incident from the list unless an affirmed brief has already admitted the work; with a missing or empty list, nothing is practice-facing and the check does not apply, because the practice is a means to better product work rather than its own product. The same repository-owned work configuration names connected-reviewer and marker-producer logins, so other accounts cannot satisfy review or advance the entrance; with no connected reviewer configured, no review is required and the decision says so.

An affirmed-brief marker counts only with exactly one lawful `Review risk` and `Review lane` pair. Changed paths are matched against the repository's schema-versioned JSON use rules; a bought use needs a current-head note, and the other branch needs its explicit no-use line. These are guards read by the entrance rather than choices it makes.

Power users may put one of `artifact`, `cold-seat`, `build`, `floor`, `use`, `review-disposition` or `release-report` before the options. That runs only the named stage and exits, except `use`, which returns the holder handoff without dispatching. The direct `release` command below occupies the same positional slot but is not a stage and never dispatches. Every builder prompt names one stage and tells the recipient to return rather than start another.

**A stage whose value depends on its recipient not knowing the expected answer is never dispatched by the entrance with the change's record or registered implementation root.** It returns to the holder with the manual isolation and dispatch step named, because the holder must inspect both the recipient tree and the job's extent before launch.

The entrance consumes the affirmed brief and recorded evidence; it never decides whether work is worth doing, what the change is for, the brief's terms, a vendor or model default, whether to merge, or an owner ask. `ambiguous-pr` returns to the holder, who names the implementing pull request on the issue with the `implementing-pr` marker or opens the one that should exist. Holder-reading, ready/reviewer setup, waiting, panel coordination and terminal states also return to the holder without an unattended recipient.

Before a fresh build dispatch, the entrance creates a branch and implementation worktree below the holder checkout's `.claude/worktrees/`, then atomically registers and dispatches into that root. Before creating the worktree, it writes `/.claude/worktrees/` to the holder checkout's repository-local exclude file, which is not committed and is not visible in `git status`. Every later stage the entrance dispatches resolves the registered root, including an artifact or cold seat reached after build, so proof reads the change rather than the holder's checkout. The builder remains on the entrance-created branch rather than creating or switching to another.

`holder_write_guard=available` records that the holder checkout's project settings declare the write-refusing `PreToolUse` hook; it does not claim the runtime loaded or enforced it. Without that complete declaration the entrance records `unavailable`, and revision and status snapshots provide detection only, because detection is not equivalent enforcement.

Every entrance run sweeps active registrations and makes one inactive only when its uniquely identified implementing pull request is closed or merged, or when no implementing pull request is identified and the issue is closed. That sweep considers every active registration on the machine, not only registrations for the repository named by `--repo`. A holder can release one directly with `python <plugin-root>/lib/work.py release --repo OWNER/REPO --issue N --root HOLDER_PATH [--instalment VALUE]`; release changes only the registry row and leaves its worktree and branch in place, because they may contain work the holder still needs.

For a resumed implementer stage, the entrance first recovers the latest matching session from the machine-local dispatch bundles and otherwise accepts the issue's authorized `builder-session` marker; if neither can supply the required continuity, it returns a non-dispatching decision naming the stage and missing evidence.

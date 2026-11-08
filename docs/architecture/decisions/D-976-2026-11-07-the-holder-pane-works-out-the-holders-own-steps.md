# D-976 — The holder pane works out the holder's own steps

**Purpose:** record why the lab-only holder pane (`tools/holder_pane/`) now works out for itself when the holder has finished one of its own steps, and why it stopped assuming one checkout, one session per worktree, one Steward name and the desktop app's old file locations. It also records what was chosen over what. **Audience:** a future session changing the pane's core, its shim or its installer, or deciding whether the release report needs a marker of its own. **Success:** that reader can recover what was chosen over what without the issues.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/940#issuecomment-6711515488) governs. Its pre-implementation artifact was [settled on the cap route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/940#issuecomment-6712361136). The lane is ordinary / connected, and no panel was bought. The four defects come from #888's trial on Daemon: #940, #941, #954 and #961.

## Rows and their reasons

- **Row 1, the pane works out the holder's own steps.**
  - Daemon #95's holder ran `proof` and `release-report` in the background, so the pane never saw them return. It missed the posted report and showed the owner's merge as the holder's step for 13 h 56 min (#961).
  - Another holder posted its use marker and stopped in the same turn, and was reminded twice to post it (#954).
  - A post of the holder's own now shows that step "posted, unconfirmed" until the next read. A background stage shows as running until the pane sees it end.
  - The release report is the exception: only a post whose body opens with the report's title line counts, and that post turns the pane to the owner's merge.
- **Row 2, the desktop app's session records are found where the app keeps them now,** and the pane says "rename off" when it can't find them. The app had moved its files, so no Daemon session was renamed, and nobody knew until the trial looked.
- **Row 3, every `<Name> Steward` is exempt, as `Steward` was.** Daemon's holders reach their Steward by the exact title `Daemon Steward`. A renamed Steward would vanish from their view.
- **Row 4, a restart binds only the change whose row names the session (#941).** Two holders shared one worktree, so binding by worktree alone would show the newer change in the older holder's session.
- **Row 5, the installer is safe across checkouts.** One uninstall in a throwaway checkout removed the shared registration and silently turned Daemon's pane off. Uninstall also left an emptied settings file behind, and the installer looked for Claude Code only in the app's old place.
- **Row 6, the trial checklist gains the kinds of check the first run missed:** a background stage, a holder's own post, and a restart in a worktree another change uses. Checks that need no stage call run before the merge. Checks that need a holder's stage calls run on whichever Daemon change is next in flight, before the merge if one is, otherwise right after, because a real holder's stage calls can't be staged on demand.

## The owner's rulings

- **The pane works out the holder's steps for itself, over a release-report marker the entrance reads** (ruling "A", 2026-11-07). A marker would change every adopter's release report and move the plugin's version, more than the fix he bought.
- **The release report alone needs its title line.**
  - Every other step is confirmed by the next read, because the entrance reads its marker, so a wrong "unconfirmed" corrects itself within one read.
  - No read ever sees a posted release report, so a wrong match there would never correct itself.
  - Every release report on record was posted from a file. So the line is read from the body the post sends, never from the command alone.

## Calls made inside the rows

- **No `prompt.submit` hook.** The API's `task-notification` turn would report a background stage's end, but hooking prompts would breach #888's rule that the mod never touches a turn. Instead the core reads the stage's report from the file the call's output went to, on each tick and Stop, and Stop's `background_tasks` list says when the task has ended. An entrance read ends the running display only when it started after that end: a read taken while the stage ran can't reflect it, and ending there would remind the holder to rerun a stage already running.
- **A post marks only a step a stage call doesn't finish.** A `run` step is finished by the stage call, which the pane sees. Treating an unrelated comment as finishing `run proof` would silence a reminder that's owed. At the release report, only an unreadable body marks the step, since a readable one either carries the title line or isn't the report.
- **A posted release report ends only on one of three things, each dated after the post:**
  - a reading at a new head;
  - an entrance decision for a stage other than `release-report`;
  - a dispatching launch for the same change, one matched to its launched bundle or whose decision says it dispatched. A refused call launched nothing.

  A holder plausibly runs catch-up, or reruns `release-report`, between the post and the merge. Since no read ever sees the posted report, a state cleared at the same head would never come back, which is #961 again.
- **A report counts only when its post's own output shows the comment GitHub created.** A call can succeed while its post fails (`gh …; echo`), and a report counted that was never posted would never be corrected. Without that evidence the post is "posted, unconfirmed", which the next read corrects. Reports are kept by change, so one change's report never overwrites another's.
- **A restart binds by `holder_session_id`.** Every registry row already carries it. Root narrows only when one id names more than one change.
- **Uninstall keeps the shared marketplace while another checkout has the pane.**
  - Another checkout counts only when its own local file still enables the pane, not when it is merely recorded. Otherwise a checkout uninstalled by hand, or deleted, would keep the registration forever.
  - Desktop session worktrees aren't counted, because they load the pane through the main checkout.
- **The local file is restored from a snapshot the first install takes.** It goes back byte for byte when nothing else changed, and is removed when the install created it. A later change is kept, and the installer says so.

## Rejected

- **A release-report marker the entrance reads.** Ruled out by the owner, for the reason above.
- **Ending the posted-report state on any later stage call, with the head match removed.** This was tried in the artifact's first draft and dropped: a catch-up or `release-report` rerun at the same head would bring #961 back. The first cold seat gave that reason.
- **Matching the title line on the command alone.** No release report on record would have matched, and #888's check 3 would have regressed. The Steward's review of the brief found this.
- **Binding a restart by worktree alone.** That is #941.
- **Keeping the shared marketplace on `installs.json` alone.** A stale record would keep it forever.

## Not this

- Nothing shipped changes: `lib/work.py`, the entrance and the plugin's version are untouched.
- #888's rules are unchanged: lab-only, read-only, at most one read every 35 minutes, one reminder per step, and no waking a holder.
- The rollout to every holder stays #888's row 9 step, after this change's rerun on Daemon passes.

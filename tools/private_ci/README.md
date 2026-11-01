# Private CI on the owner's laptop (lab-only)

**Purpose:** the four private product repositories' CI runs on a locked-down Linux runner inside WSL2 on BLAZ-TOP, so no private-repository job spends paid Actions minutes. Only the required gate and the reviewer's prepare and report jobs stay hosted, inside the free 3,000 minutes, and a daily watch says when that remainder grows (#929). **Audience:** the owner who installs it, the holder who walks the install with him and files the carriers, and the Steward who receives the watch's alerts. **Success:** the install proves row 1's isolation from inside a real job, both instances run product jobs, and each product moves by a carrier that changes little more than `runs-on:`.

Nothing here ships in the plugin. The tests are `tools/tests/test_private_ci.py`, which CI collects.

## What it is, and why

- **The runner** is a WSL2 distribution, `tradecraft-ci` (Ubuntu 24.04, the release `ubuntu-latest` provides), holding two runner instances, `blaz-top-wsl-1` and `blaz-top-wsl-2`. They run as the account `ci-runner` and register in the organization runner group `private-ci`, with the label `private-ci` and none of GitHub's default labels.
- **Nothing a job runs can reach your Windows side** (row 1). The distribution mounts no Windows drive, interop and the Windows `PATH` are off, WSLg and GPU passthrough are off (C4), networking stays on WSL's default NAT, and `ci-runner` has no root route: no sudoers entry, a locked root password, no root-granting group, and `NoNewPrivileges=true` on both services. WSL's defaults would otherwise hand a job your files with your Windows permissions and let it launch Windows programs as you. `guiApplications=false` is a global `.wslconfig` setting: it also applies to any distribution you add later.
- **The reviewer's review job stays on the Windows runner** (row 3). It asks for any `self-hosted` runner, and the Linux instances carry no `self-hosted` label, so it can't land there; the Windows runner lacks `private-ci`, so product CI can't land on it. Moving the review job is #930.
- **At most half the laptop** (row 5): WSL is capped at 8 threads and 12 GB, and the two instances share that.
- **While the laptop is off or asleep**, product checks wait in GitHub's queue. The hosted gate still runs and shows what's waiting. A job left queued past 24 hours is dropped by GitHub, and the watch task re-runs it at your next logon. A job running when Windows sleeps is lost; re-run it by hand.

## What's here

| Path | What it is |
|---|---|
| `setup.py` | `install` (re-runnable), `verify`, `probe [--after-restart \| --require-idle MINUTES]`, `status`, `uninstall`. Runs on Windows from your terminal. |
| `guest/provision.sh` | Runs as root inside the distribution: account, `/etc/wsl.conf`, packages, runner unpack, registration, services. |
| `guest/wsl.conf` | The distribution's `/etc/wsl.conf`, written verbatim. |
| `guest/isolation_check.py` | Row 1's check, run inside a job, and by `verify` as root and as `ci-runner`. |
| `probe/` | The probe workflow and its smoke script, pushed to Countdown-Clash's `lab/private-ci-probe`. |
| `watch.py`, `hosted.json` | The daily watch, the logon re-run, and the declared hosted list. |
| `keepalive.py` | Held by the start task at logon: one hidden `wsl.exe` that keeps the distribution up. |

Local state lives in `~/.tradecraft-lab/private-ci/`: `install.json` (each instance's registration request, never the token), the installed copy under `bin/` that the tasks run, and the watch's caches.

## Install (once, at the pull request's final head)

The holder walks these with you. Registration needs an organization-admin token, which no session holds, so you type it into the setup yourself.

1. In the organization's Settings → Actions → Runner groups, create `private-ci`: selected repositories set to Organizations-of-Verra, Daemon, Countdown-Clash and Windgust-Questbook; "Allow public repositories" off; workflow access set to all workflows. Tell the holder it covers those four and allows no public repository. A public repository's fork pull request could name the label, which is why the group must exclude them.
2. Open Settings → Actions → Runners → New self-hosted runner, and leave the page open for its registration token.
3. From a tradecraft checkout at the head, run `python tools/private_ci/setup.py install`. Type the token only into its prompt, and answer any Windows prompt. It ends by running `verify`.
4. In Settings → Actions → Runners, read each runner's labels and tell the holder: `blaz-top-wsl-1` and `blaz-top-wsl-2` should show only `private-ci`, and `BLAZ-TOP` should not show `private-ci` (C19).
5. Run `python tools/private_ci/setup.py probe`.
6. Simulate a reboot: run `wsl --shutdown`, then `schtasks /Run /TN tradecraft-lab-private-ci-start`, wait a minute, then run `python tools/private_ci/setup.py probe --after-restart`.
7. After 30 idle minutes, run `python tools/private_ci/setup.py probe --require-idle 30`.

The holder records each probe's JSON summary, with your group and label reports, in the release report. `install` refuses to change a `.wslconfig` setting you chose (`networkingMode`, `processors`, `memory` or `guiApplications` set to something else); it names the key, and you decide.

## Re-running after a change

`install` is re-runnable. Over a complete install it prompts for nothing, registers nothing, and reports every step unchanged. If a review fix changes anything the setup or the check reads, run `install` and `probe` again at the new head.

## The probe

`probe` refuses on a dirty tree, so the commit it names is what ran. It pushes a parentless commit holding only the probe files to `lab/private-ci-probe` in Countdown-Clash, so the push starts only the probe workflow. Its jobs:

- `local`, two jobs on `runs-on: private-ci`: row 1's check in a real job, then a 60-second hold so both instances must be busy at once.
- `smoke`, on `runs-on: private-ci`: `setup-node`, `pwsh`, Chromium installed without `--with-deps` or `install-deps` and launched headless, and `setup-dotnet` 8.0.x, all as `ci-runner` under `NoNewPrivileges`.
- `labels`, four jobs asking for `private-ci` with `self-hosted`, `Linux`, `X64` or `Windows`. Each must still be queued after five minutes in which no runner, Windows or Linux, runs a job (C18). The probe then cancels them; queued jobs cost nothing.

While it runs it holds a listener on Windows `127.0.0.1`, and fails if a job connects to it. It observes the Windows runner only by asking whether processes named `Runner.Listener.exe` and `Runner.Worker.exe` are running. `--after-restart` and `--require-idle` first confirm, without entering the distribution, that `wsl -l -v` shows `tradecraft-ci` as `Running` and the keepalive is alive, because entering a stopped distribution boots it (C17).

The branch stays after merge so a later re-check (and #930's) is one push. Deleting it is your call.

## Moving a job

Moving a job between hosted and local is one `runs-on:` value: `private-ci` to run it here, `ubuntu-latest` to send it back. It's made in that product through its own entrance on the `ordinary` / `mechanical` lane. A job meant to stay hosted is instead one line added to `hosted.json`, in tradecraft, on the same lane.

## The watch

The task `tradecraft-lab-private-ci-watch` runs `watch.py logon` at your logon and daily at 09:00: the re-run, the watch, then the re-run again for up to four hours, so a run with several dropped jobs is re-run in turn.

- **The re-run** re-runs any private-repository job GitHub dropped after 24 hours queued, whatever runner it asked for, the reviewer's review job included. It makes at most one call per run per pass, and only on a completed run: one run-level `rerun-failed-jobs` when every failed job in the run was dropped, otherwise one job-level re-run of the next dropped job. It never re-runs a job that ran, or one a person cancelled.
- **The watch** posts one comment on #683 when a moved repository runs a hosted job not on `hosted.json`'s list, or when the month's hosted minutes are on pace past 1,500. A repository counts as moved once one of its jobs, other than the probe's, has run on a `private-ci` runner; until then `status` lists it as awaiting its carrier. Each alert is posted once.
- `python tools/private_ci/watch.py status` prints what it sees, posting nothing.

**Residual:** nothing alerts when the watch itself stops (C13). `status` shows its last run and last success.

## The carriers

Each product moves in its own carrier change after #929 merges (row 8). This section is what a holder files and writes them from.

**The order, and why.** Each carrier is filed only after the one before it has merged and its first local run has passed.

1. **Countdown-Clash**, the smallest product (97 minutes in October). Its first local run is the live check, so missing tools surface there cheapest.
2. **Organizations-of-Verra**, about 72% of October's minutes.
3. **Windgust-Questbook**.
4. **Daemon**.

**The lane condition.** A carrier is `ordinary` / `mechanical` where it only changes `runs-on:` and drops what row 7's setup now provides. A carrier that needs anything more gets its own brief. Each carrier's lane is affirmed by the owner on that product's own brief.

**Each carrier's diff.**

- Every job in that product's own workflows gets `runs-on: private-ci`. The `connected-review.yml` caller and the gate are excluded, because neither moves.
- **Organizations-of-Verra** also drops `--with-deps` from `e2e.yml` :30 (`npx playwright install --with-deps chromium` becomes `npx playwright install chromium`) and removes the cache-hit step at :33 (`npx playwright install-deps chromium`).
- **Daemon** also updates the two places that record hosted-only CI:
  - the CI line in `docs/roadmap.md` :74, which reads "runs on GitHub-hosted Linux runners only";
  - the comment in `ci.yml` :18, which reads "GitHub-hosted Linux only, per the roadmap's CI paragraph and ADR-0005".

  If the line numbers have moved, find them by those quotations. ADR-0005 (`0005-local-sim-no-ci.md`) governs what CI runs, so it stays as it is. Daemon's carrier goes by Daemon's brief route as it stands then: #918's trial ends 2026-11-06, and its judge settles what follows.

**The Steward's part.** The Steward gives each carrier its pre-owner review (`docs/cells/steward/references/private-ci.md`).

A branch not caught up with its carrier keeps running hosted, because a push runs the workflow file at the pushed commit. The watch shows such runs until the branch catches up.

## Undo

```text
python tools/private_ci/setup.py uninstall
python tools/private_ci/setup.py uninstall --unregister-distribution
```

The first removes the two tasks. The second also deletes the `tradecraft-ci` distribution and everything in it. What stays yours: remove `blaz-top-wsl-1` and `blaz-top-wsl-2` under Settings → Actions → Runners, delete the `private-ci` runner group, and remove `processors`, `memory` and `guiApplications` from `%UserProfile%\.wslconfig` if you want WSL's defaults back. A product that has moved needs its carrier reverted first, or its jobs wait for a runner that no longer exists.

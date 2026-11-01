# The private repositories' CI runs on the owner's own runner (#929)

**Purpose:** retain why the four private product repositories' CI moves to a locked-down Linux runner in WSL2 on the owner's laptop, what keeps pull-request code away from his Windows side, and how the watch and the logon re-run read GitHub's job records. **Audience:** maintainers of `tools/private_ci/`, the Steward who receives its alerts and reviews its carriers, and whoever later moves the review job (#930) or replaces the host. **Success:** a maintainer can loosen a setting, change the re-run or move the host knowing what was rejected, which reading of GitHub's records each predicate rests on, and which costs were accepted.

The owner bought #929 and affirmed its brief on 2026-11-01 at 00:03Z ("Affirmed"), from his direction of 2026-10-24 ("All private repo ci will need to be on local runners"). It answers Daemon #94's harm: Daemon #110 had been held at its required gate since 2026-10-24T03:39:37Z by the Actions billing stop. The artifact was settled by the recorded cap resolution ([6551562697](https://github.com/Grimblaz-and-Friends/tradecraft/issues/929#issuecomment-6551562697)) after two "would not" verdicts; the holder's second reading ([6552463887](https://github.com/Grimblaz-and-Friends/tradecraft/issues/929#issuecomment-6552463887)) directed this entry. The implementation is `tools/private_ci/setup.py` at `72601e9c672af06dad549d47c8f9ce44aca1a4bf`, with `tools/private_ci/guest/isolation_check.py`, `tools/private_ci/guest/provision.sh`, `tools/private_ci/watch.py` and `tools/private_ci/hosted.json` at the same commit, tested by `tools/tests/test_private_ci.py` at `72601e9c672af06dad549d47c8f9ce44aca1a4bf`.

## The host

Linux in a WSL2 distribution, `tradecraft-ci` (Ubuntu 24.04, the release `ubuntu-latest` provides), on BLAZ-TOP: turn 1, "Yes, B". It keeps today's Linux jobs on Linux, and the laptop already runs every session that opens a product pull request. Rejected:

- **Replacing Windows with Linux** on the laptop: a separate, later decision, out of this change.
- **An always-on machine:** new hardware for the owner to own and keep, where the laptop is already on whenever product work happens.
- **The existing Windows runner as it is:** it runs as the owner, beside the review job's cached Claude CLI and token (#881's lab case), and the products' jobs are Linux jobs.

## Why WSL's defaults aren't safe, and the settings that replace them

The runner executes pull-request code, so row 1's wall is the security boundary. WSL's defaults would hand a job the owner's Windows files with his Windows permissions (automounted drives) and let it launch Windows programs as him (interop and the Windows `PATH`). The settings:

- **No Windows drive:** `[automount] enabled=false` and `mountFsTab=false`, so an `fstab` line can't mount one either; `fstab` is root-owned and holds no Windows-backed entry.
- **No interop:** `[interop] enabled=false` and `appendWindowsPath=false`.
- **No root route.** The account `ci-runner` has no sudoers entry, root's password stays locked, and the account is in no root-granting group. Docker group membership counts as root, so `docker`, `lxd`, `incus`, `disk`, `libvirt` and the admin groups are all refused. Both runner services carry `NoNewPrivileges=true`, so no setuid binary can raise a job even if sudoers is later misconfigured.
- **NAT networking**, WSL's default, because mirrored networking lets a job reach Windows services that listen only on `127.0.0.1`.
- **WSLg and GPU passthrough off** (`guiApplications=false`, `[gpu] enabled=false`). WSLg is a display and clipboard bridge into the owner's session, and GPU support mounts Windows driver directories.

**How `verify` tests what a job can't read.** A shell opened with `wsl -u ci-runner` lacks the service's `NoNewPrivileges`, so the check run there would fail every correct install; `verify` runs it as root under `setpriv --reuid=ci-runner --regid=ci-runner --init-groups --no-new-privs --reset-env` instead (C16). Under `NoNewPrivileges`, `sudo -n true` fails whatever sudoers says, so it proves no_new_privs and nothing about sudoers (verdict 2, point 2). As root, `verify` asks sudo itself with `LC_ALL=C sudo -l -U ci-runner` and accepts only sudo 1.9.15p5's sentence for a user with no rights (`plugins/sudoers/display.c` at the `SUDO_1_9_15p5` tag, the version Ubuntu 24.04 ships), and reads root's shadow field. Asking sudo covers every route it resolves, group rules and aliases included, and passes Ubuntu's stock `%sudo` and `%admin` rules, which a file scan would flag. Any other output fails closed. The proof that a real job gets these settings is the probe workflow's run, which `verify` doesn't replace.

## Paid minutes, not hosted minutes

The problem is paid minutes (turn 2, "B is good, but we need to be sure we can easily adjust if one of those steps grows, or we add something else"). The required gate and the reviewer's prepare and report jobs stay hosted: about 390 of October's 3,833 minutes, inside the free 3,000, and they keep the gate visible while the laptop is away. `hosted.json` declares exactly those three by run path and job name, confirmed in all four repositories' live records.

## Pinning on the runner side, in both directions

Each Linux instance registers in its own group, `private-ci`, with `--labels private-ci --no-default-labels`, and the Windows runner lacks `private-ci`. Product CI then can't land on the Windows runner, and the review job, which asks for any `self-hosted` runner, can't land on Linux. Rejected: a workflow targeting change. Products call the reviewer at the pinned `reviewer-stable` tag (`2524d99`), so a change on `main` reaches none of them until the tag moves, and tradecraft's own reviews run hosted, so the install couldn't test it (turn 4, row 3). The review job stays on the Windows runner; moving it and retiring that runner is #930.

## The watch, locally, and the one-line move

The watch and the re-run run from a scheduled task under the owner's `gh`, not as a hosted workflow (C5): reading private job records needs a credential tradecraft's `GITHUB_TOKEN` lacks, and a public repository's Actions holding a secret with private reach would widen what pull-request-adjacent code can touch. It alerts with one comment on the standing page, #683, carrying no Steward marker, so the Steward's wake reads it as intake. Moving a job is one `runs-on:` value on the mechanical lane (turn 3, "Watch + one-line move"). A settings switch was ruled out: it would touch every workflow, the gate's included, and leave a move with no reviewed record.

## The re-run's design

Each pass makes at most one call per run, and only on a completed run whose attempt has passed the one recorded at its last call. It makes one run-level `rerun-failed-jobs` when every job in the latest attempt that didn't succeed was dropped for queue time, and otherwise one job-level re-run of the lowest-id owed job; `logon` then follows for up to 240 minutes so a mixed run's next owed job is taken in turn. Verdict 2 showed why: one single-job call per job hits an attempt still in progress at the second call, and the rest are then skipped as superseded. Latest occurrences are read across all attempts, so either shape of a new attempt's job list works.

Two readings of how a dropped job appears in GitHub's records, both from Daemon run 40055997670's second attempt, the job the billing stop left with no runner:

- **A job that never got a runner still reads runner group 0**, the group hosted jobs carry. So group 0 means hosted only for a job that got a runner; a job without one is hosted only when every label it asked for names a GitHub-hosted image. Without this, a dropped `self-hosted` review job would read as hosted and alert.
- **Its `started_at` equals its `created_at`**, so a start time can't say it never started. "Never started" is an empty runner name, runner id 0 and no steps.

No live queue-expired record existed to read; GitHub's limits page says such a job is "automatically cancelled", and the re-run accepts `failure` or `cancelled`. Whether `rerun-failed-jobs` re-runs that conclusion is left to the first live case, with the job-level call as the path that works regardless.

## The install as the change's exercise

The owner installs at the pull request's final head, before merge (row 6). Registration needs an organization-admin token no session holds, and a use seat could reach only a throwaway distribution that never registered. The setup asks for the token with no echo in his terminal and pipes it on stdin to the distribution, where `config.sh` reads it as `ACTIONS_RUNNER_INPUT_TOKEN` (runner 2.338.0's `CommandSettings` falls back to that input when no token argument is given). The probes then show isolation from inside a real job, two instances, the smoke steps, and the label jobs left queued through five all-idle minutes.

## Accepted costs

- Every product merge waits on the laptop being on; a job left queued past 24 hours is re-run at the next logon, and a job running when Windows sleeps is lost.
- Jobs share `ci-runner`'s home between runs, with no per-job clean image. The wall is between jobs and Windows, not between products.
- Nothing alerts when the watch itself stops (C13); `status` shows its last run and last success.
- `guiApplications=false` is global to the laptop's WSL, so it applies to any distribution added later.

**Live-only.** Whether any Windows-backed mount survives the settings (C9's contingent allowlist), the `.runner` field names the instance match reads, and the provisioning steps themselves are settled at the owner's install, and its probe summaries go in the release report. No raw run output is retained.

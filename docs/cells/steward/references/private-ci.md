# Private CI: the watch's alerts and the carriers

**Purpose:** what the Steward does with a private-CI watch alert on #683 and with each product's private-CI carrier (#929). **Audience:** the Steward and its replacement. **Success:** every alert is verified and answered with a one-line move the owner can take, and each carrier gets its pre-owner review in row 8's order.

The runner, the watch and the carriers are described in `tools/private_ci/README.md`.

## A watch alert is intake

A comment on #683 opening with `<!-- lab:private-ci-watch:v1 keys=... -->` carries no Steward marker, so the wake counts it as intake.

1. Verify it from a tradecraft checkout with the owner's `gh`: `python tools/private_ci/watch.py status`. Its `would_alert` and per-repository readings show what the watch sees now.
2. For each unlisted job, bring the owner one line:
   - its `runs-on:` changed to `private-ci`, made in that product through its own entrance on the `ordinary` / `mechanical` lane; or
   - if the job is meant to stay hosted, one line added to `tools/private_ci/hosted.json` in tradecraft, on the same lane.
3. For a pace alert, bring the move of the largest contributor the alert names.
4. Mark the alert handled.

**The reviewer's review job never alerts.** It runs self-hosted on the Windows runner, which isn't hosted, and moving it is #930's. An alert's fix never touches the shared reviewer workflow or `reviewer-stable`.

## The carriers

They go in row 8's order, each filed only after the one before it has merged and its first local run has passed: Countdown-Clash first, then Organizations-of-Verra, Windgust-Questbook and Daemon.

- **The lane.** A carrier is `ordinary` / `mechanical` where it only changes `runs-on:` and drops what row 7's setup makes possible. A carrier that needs anything beyond that needs its own brief.
- **Verra's two drops.** `--with-deps` in `e2e.yml` :30 and the cache-hit `install-deps` step at :33.
- **Daemon's two record updates.** The CI line in Daemon's roadmap (`roadmap.md` :74 under its `docs`: "runs on GitHub-hosted Linux runners only") and `ci.yml` :18 ("GitHub-hosted Linux only, per the roadmap's CI paragraph and ADR-0005"). ADR-0005 stays as it is.
- **Daemon's route.** Daemon's carrier goes by Daemon's brief route as it stands at the time: #918's trial ends 2026-11-06, and its judge settles what follows.

The Steward gives each carrier its pre-owner review against that list.

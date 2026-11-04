# D-947 — A job that publishes outside its repository runs on GitHub's machines, not the owner's runner

**Purpose:** record why Countdown-Clash's and Windgust-Questbook's GitHub Pages deploys went back to GitHub-hosted runners after #929 moved them, and the rule that follows for any publishing job. **Audience:** a future session deciding where a private product's job runs, or answering a private-CI watch alert. **Success:** that reader keeps a publishing job hosted, and leaves checking jobs on the runner, without re-deriving why.

The owner's affirmed brief on #945 governs. It applies his answer to the question #929's last carrier put to him on Windgust-Questbook #333: "merge, github's machines". The lane is ordinary / mechanical.

**Why publishing jobs leave the runner.** The runner's two instances run as one account with one home and neither is ephemeral, so a job can leave files that a later job uses. A pull request's code runs there in `validate` before anyone reviews it, so a deploy from `main` that ran there later could build and publish with what that code left behind. On a GitHub-hosted runner each job starts on a clean machine.

**Why checking jobs stay.** The owner kept `validate`-type jobs on the runner with the carry-over accepted, as #929's settled artifact chose: every job is started by the owner or a session on his credentials, each repository's only collaborator is the owner, and forking is off.

**What this reverses.** #929's affirmed row 2 moved every job in the products' own workflows, "Pages deployments included". For publishing jobs that no longer holds; [D-931](D-931-2026-11-01-private-ci-on-the-owners-runner.md) stands otherwise.

**Countdown-Clash's deploy builds its own copy.** Its `deploy` published the `dist/` that `validate` built and uploaded, and on a push to `main` that `validate` runs on the runner. Changing only `deploy`'s runner would still publish files built there, so `deploy` now installs and builds from its own checkout, as Windgust-Questbook's already did. It keeps `needs: validate`, so it still waits for `main`'s checks, and while the laptop sleeps a Countdown-Clash merge waits to publish. Two alternatives were rejected: changing only `runs-on:`, which leaves the harm in place, and running `validate` hosted on pushes to `main`, which puts a checking job back on GitHub against the owner's answer.

**One entry on the hosted list.** `tools/private_ci/hosted.json` declares both deploys with one entry, because the watch matches its list by workflow path and job name, not by repository. The watch reads its installed copy, so the entry counts once `install` has re-run.

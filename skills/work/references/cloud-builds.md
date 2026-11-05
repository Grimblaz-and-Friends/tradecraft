# Cloud builds

**Loaded when** setting a repository up for cloud builds, switching one off, or reading a cloud attempt's route, profile mark, practice drift, attempt checks or cost.

For a set-up repository, every Claude implementer launch (artifact, build, repairs) runs as a Claude Code cloud session that the launcher starts through that repository's routine. A cloud builder cannot reach the owner's machine, which is the route's reason. A failed launch stops and says why; it never falls back to a local builder. A Codex implementer is untouched.

## The switch

`~/.tradecraft/cloud-builds.json` sits beside `implementer-vendor` and is never committed:

```json
{"schema_version": 1,
 "practice": {"repository": "OWNER/tradecraft", "branch": "cloud-practice"},
 "repositories": {"OWNER/product": {"routine_id": "trig_...", "token_file": "C:/.../product.token",
                                    "setup_record": "...", "set_up_at": "..."}}}
```

An absent file or entry means the local route. Removing an entry switches its repository back to local. A malformed file, an unknown schema, a missing field, or an entry naming the practice's own repository refuses every Claude launch, naming the file and the fault, because a broken switch must not quietly mean local. Only `lib/cloud_setup.py verify --phase complete` writes it; the holder guard refuses a shell write to it, and a local build's launch comparison covers it.

## One-time setup, per repository

1. The holder runs `python <plugin-root>/lib/cloud_setup.py body --repo OWNER/REPO --environment ENV_ID` (with `--practice-repo` and `--practice-branch` for a fork) and creates the routine with that body through its `RemoteTrigger` tool. The body has no schedule, clears every account connector, disallows `PushNotification`, names the product and the practice as sources, and checks the practice out at the pin branch without its `/CLAUDE.md`, `/AGENTS.md` and `/.claude/`.
2. The holder reads the routine back with `RemoteTrigger get`, saves the response, and runs `verify --phase created --readback FILE`. An update can drop fields while answering 200, so only the read-back shows what landed; any difference prints `setup FAILED: <field>` and stops. `verify` reads the connectors at `mcp_connections` (and `session_request.config.mcp_servers`), the schedule at `cron_expression`, and the sources, disallowed tools, model and effort under `job_config.ccr.session_context`.
3. The owner visits the routine on claude.ai once: adds its API trigger, sets model Opus 5.5 and effort high in its editor, and saves the trigger's token to a file. The API cannot do any of these.
4. The holder reads the routine back again and runs `verify --phase complete --readback FILE --token-file PATH`, which also requires `claude-opus-5-5` at `high` and a readable token file. A clean pass writes the setup record to `~/.tradecraft/cloud-setup/<owner>__<repo>.json`, creates the pin branch at the installed commit when it is absent, and writes the switch entry.

**The trigger is proved by the first launch, not by setup.** No read-back field shows an API trigger, so `verify` does not check for one. The first cloud launch must get a `cse_` session back from its fire; a fire that fails refuses the launch and starts nothing local.

One cloud environment serves every set-up repository, with `CLAUDE_CODE_PLUGIN_DIRS=/home/user/<practice repository name>`. A product's toolchain, if the environment lacks it, is the environment's setup script, outside this practice.

**The practice's own repository is refused.** Its product and practice clones would share one folder and its committed guard would govern a single-source build, which is untested. Its builds stay local.

**Adopters** follow the same steps on their own account and environment, against a fork of the practice they can push to, kept level with the release they install. A fork behind the installed commit cannot be fast-forwarded, and every new cloud session is refused until it catches up.

## A launch

The launcher reads the token file (refusing, naming only the file, when it is missing, empty or not one line of printable ASCII), then reads the installed commit from the plugin install record's `gitCommitSha`, never a checkout's `HEAD`. A launcher whose `plugin.json` version is older than the installed one is refused and told to reload. It fast-forwards the shared pin branch to the installed commit only when the pin is behind, so the pin moves once per plugin update; a pin ahead of or diverged from the installed commit refuses with "reload".

For a build or repair it publishes the change branch; for an artifact it checks the holder's commit is on the remote. It creates a report branch `claude/tradecraft-report-<issue>-<stage>-<dispatch>` with one `[skip ci]` commit holding the task as `tradecraft-cloud/dispatch.md`, and fires the routine with a short `TRADECRAFT-CLOUD-RUN v1` header naming the work, checkout, practice commit and report branch. A fire is never retried.

The run first checks its practice clone: the plugin hook on the prompt, and the saved prompt's first instruction as the fallback. A clone at another commit, or holding an excluded file, records `PRACTICE MISMATCH` with both commits and stops before building. Otherwise the run does the task and pushes `report.md` (its whole return) and `instructions.md` (the instruction files it loaded) in one `[skip ci]` commit. It never posts on the issue or messages a session.

The practice's `Stop` hook acts only when `CLAUDE_CODE_REMOTE` is set, and outside the cloud does nothing and prints nothing. After each turn it totals the session's usage over distinct message ids across the main transcript and every subagent transcript, records the main session's model and effort and the permission mode, copies the recorded practice check, and pushes `usage.json` in a `[skip ci]` commit. Its `report_blob` naming the pushed report is the launcher's finish signal.

The launcher then keeps the report as the published output, posts it whole on the issue (in labelled parts past GitHub's comment limit), deletes only the report branch it named for that dispatch, and fast-forwards the local implementation tree.

## Follow-ups

A revision or repair goes as a follow-up message into the session it continues, through `claude -p … --cloud cse_…` under the owner's claude.ai login on the launching machine; without that login it refuses and says so. It keeps the practice version its session loaded, even after a plugin update: it makes no pin compare and no version check, and its record names `session_loaded`, `installed_at_send` and `drift`. A judge reading a newer rule than a drifted follow-up ran reads that record.

## Reading a cloud attempt

The entrance's implementer environments show, per cloud attempt:

- `route` and the session id;
- `cloud_profile` and `off_profile`: a main session not wholly on `claude-opus-5-5` at `high` is marked, and no recorded effort reads as Opus 5.5's medium default. Ask the owner to correct the routine's editor settings;
- `permission_mode`, which a builder should hold as `auto`;
- `cloud_checks`: the change-branch check (a build's run advanced the change branch from its fire-time tip), the `[skip ci]` check, and the practice-check record. A failure holds the next stage as a launch finding does;
- `ledger_check`: the hook's ledger re-checked without the transcript. A failure makes the attempt's cost unknown with its faults and shows as an attempt fault; it changes nothing else;
- for a follow-up, `practice_drift`;
- `instructions_applied` and `instructions_loaded`: the product's `CLAUDE.md` and `AGENTS.md` load, and no repository's committed hooks or permission rules apply, because the session starts above its clones.

The launch comparison reads `cloud-not-run` with its reason, a clear status. Cost is each attempt's delta of the session's running total, priced per model at the rate card; a model with no rate row is unpriced, never zero.

## Decisions in force

- The task travels on the report branch, because composed prompts exceed the fire's 65,536-character limit.
- The launcher posts the report and the holder keeps every marker.
- The installed commit comes from the install record, so the pin moves on plugin updates and never on merges.
- A follow-up keeps its session's version; a new session loads exactly the installed one.
- Attempt checks reuse the launch-findings hold rather than adding a gate.

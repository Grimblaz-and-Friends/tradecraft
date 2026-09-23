# D-726 — Make the entrance the holder's instrument

**Landed by** [PR #726](https://github.com/Grimblaz-and-Friends/tradecraft/pull/726). Closes [#724](https://github.com/Grimblaz-and-Friends/tradecraft/issues/724). Governed by the [affirmed implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/724#issuecomment-5787041296), the [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/724#issuecomment-5787287271), its cold [`would` verdict](https://github.com/Grimblaz-and-Friends/tradecraft/issues/724#issuecomment-5787287039), and the [holder's whole-change reading](https://github.com/Grimblaz-and-Friends/tradecraft/issues/724#issuecomment-5787287457). The implementation began at `cb6209a338444dbec447f38319a167948db0e542`; the connected-review repair began at `4efa5a1730bb09de4a35551294cfad87e42c376b`.

## Context

The entrance had accumulated two incompatible jobs. Reading the issue also selected and dispatched a recipient, so an observation could mutate the registry, create a worktree, publish a branch, or buy another run. Its prompts serialized the change record, its check read treated any historical red as current, its cold seat inherited the change's worktree and history, and neither decisions nor bundles said which practice version produced them. Failures across product changes then required the holder or owner to reconstruct the intended stage and launch it by hand.

The affirmed brief ruled that one holder session owns the stretch and the entrance is its instrument. Looking is read-only; running is explicit and performs the holder-named stage; prompts carry the brief, artifact, compact facts and fetch commands rather than the record; unsafe version combinations refuse by stage; and recipients receive no worktree cut from the change root. The holder retains every judgment because the mechanism should make repeated facts consistent without turning those facts into unattended authority.

## Decision

### One door has separate read, run, tree and registration forms

The ordinary invocation reads GitHub and local configuration and returns a versioned, work-identified report without mutation. It validates evidence from both lawful marker surfaces and groups check runs by exact name, with the latest `started_at` and run id winning. A lawful builder-session claim with no pull request returns the holder-owned `open-pull-request` step; completed release evidence returns the holder-owned `release-report` step.

`run STAGE` is the only stage-launching form. The stage argument is the holder's authority and need not equal the report's recommendation; one invocation validates and performs that stage and returns. Implementer prompts contain one-stage bounds, the exact affirmed brief, the latest artifact when one exists, compact stage facts and explicit GET commands. They do not contain issue or pull-request threads. `run use` instead requires the holder's job and validated consumer-tree metadata, while `run release-report` launches nobody. The existing `release` and `adopt` forms remain registration operations.

The prompt or holder job is validated before a build creates or registers a root or publishes a branch. A settled artifact is deliberately not a build precondition: the holder-named stage is authoritative under the brief, and the charter exempts purely mechanical work from an artifact. Where an artifact exists, the bounded build prompt carries it.

### Version and bundle provenance are safety evidence

Every decision and dispatch request records the work identifier and the version read from the shipped manifest. A resumed stage selects the bundle and valid session together, validates the request and run schemas, and checks that selected request's producer version. Matching bundles without a valid session refuse; a builder-session marker is fallback only when no matching bundle exists. Dispatched marker claims are likewise checked against the latest unambiguous successful bundle completed before the marker, so session, revision, return and staffing claims cannot outrun their source record.

The stage-safety table records the first version carrying each mechanism:

| Stage | Minimum | Mechanism |
| --- | --- | --- |
| `artifact` | `0.152.0` | bounded prompt and explicit run |
| `cold-seat` | `0.152.0` | neutral cold root and explicit run |
| `build` | `0.152.0` | bounded prompt, verified publication and explicit run |
| `floor` | `0.149.0`, then `0.152.0` | registered implementation root, then bounded prompt and explicit run |
| `use` | `0.152.0` | validated consumer tree and explicit run |
| `review-disposition` | `0.149.0`, then `0.152.0` | registered implementation root, then bounded prompt and explicit run |
| `release-report` | `0.152.0` | holder-owned report |

The registered-root pin is the manifest version at commit `f121ac38c6cc14d33b7cc2feb20970c50a7d0e4a`, which introduced that mechanism; `git show f121ac38c6cc14d33b7cc2feb20970c50a7d0e4a:.claude-plugin/plugin.json` is the reproducing command. The other pins use the version this pull request ships. Version comparison follows SemVer prerelease precedence and refuses a producer from another major before applying a mechanism minimum, because ordering a structurally incompatible record above a floor would silently treat it as readable.

### Recipient roots prove only what their jobs need

The cold seat runs in a temporary standalone repository with one neutral empty detached commit, no remote, copied file or shared Git history. The prompt supplies the exact brief and artifact inline, and the directory is removed on return. The holder guard therefore remains a path authority: direct commands naming a protected implementation root are denied, while `work.py run` names only the holder root and resolves the implementation root internally.

`lib/recipient_tree.py` builds the consumer root for adopter or repository-session mode. It archives only the declared paths and loading surfaces from the registered root's clean committed revision, refuses exclusions or archive transformations that remove or alter them, preserves each committed `100644` or `100755` mode, and commits them into a standalone detached repository. Adjacent digest-bound metadata records work, source, mode, surfaces, exclusions, object ids and file modes. Before use, validation requires the neutral commit's complete path/mode/object set to equal that manifest and refuses changed, untracked or ignored entries.

### A fresh build is publish-before-launch, including retry

Fresh build creates and registers the entrance branch, selects the sole or tracked remote, publishes the branch, sets its upstream and verifies the remote head before launching. If publication fails, the registration remains as the recoverable anchor; another fresh `run build` republishes and verifies that existing registered branch before launch. The refusal tells the holder to repair remote selection, authentication or connectivity and retry. This preserves the created worktree without allowing the failed first attempt to turn the next run into an unverified launch.

## Rejected alternatives and consequences

**Keep decision and dispatch coupled.** Rejected because looking would remain a paid, mutating act and could repeat a stage on evidence that needed holder judgment. The holder-owned endpoints and explicit `run STAGE` boundary are the control surface.

**Serialize the issue and pull-request record into every prompt.** Rejected because it hands recipients context their one stage does not need and makes unrelated comments change prompt bytes. Explicit GET commands let a recipient fetch only current state its stage genuinely needs.

**Cut recipient worktrees from the change root.** Rejected because cold judgment then carries project settings, plugin declarations and history, and each linked worktree can register another plugin installation. Neutral repositories carry only the declared inputs.

**Exempt launcher names in the holder guard.** Rejected because command spelling is not authority and would let a direct launcher name a protected implementation path. The sanctioned command avoids naming that path; canonical containment remains the guard's rule.

**Make a settled artifact and cold verdict prerequisites of `run build`.** Rejected because it contradicts the holder's explicit stage authority and would bar the charter's purely mechanical path. Build still requires an authorized affirmed brief; prompt input validation occurs before any build mutation.

**Delete a registration after failed first publication.** Rejected because the worktree and branch are useful recovery state. Republish-and-verify on every fresh build reaches the same safety boundary without discarding them.

**Trust marker text or choose a session separately from its bundle.** Rejected because either allows typed evidence to claim facts its source record does not establish. Schema, session, producer version and claim are one provenance chain.

## Evidence

The implementation and connected-review repair are exercised by the read-only decision, explicit-run, latest-check, marker-contract, version-boundary, publication-retry, bounded-prompt, neutral-root and consumer-tree tests in `lib/tests/test_work.py` and `lib/tests/test_recipient_tree.py`. The full repository floor is `python tools/dev.py check`; it runs after this entry and index row are written, so this frozen entry names the command and test surfaces rather than an output from a commit it cannot yet cite.

# Connected reviewers

**Loaded when** configuring a connected reviewer, marking a pull request ready, dispositioning what one posted, or buying a second look after a non-mechanical fix.

Every connected reviewer fires once per pull request, when the pull request is marked ready, never per push. Open the pull request as a draft; run the executable floor and the required experience session, or post its declining line; then mark ready and apply the `reviewers` label. **Mechanical work owes neither the session nor the declining line**, so it is marked ready once the floor has run. Codex fires on ready without that label. A repository with no connected reviewer owes nothing here.

The `reviewers` label gates Greptile and CodeRabbit. Removing and re-adding it may buy a second look after a non-mechanical fix; that look is permitted, not owed, and a mechanical fix buys none.

Every comment ends in its own thread, by a fix or a one-line reply carrying one of these dispositions: `fixed`; `fixed — nothing else found it`; `fixed in #<N>`; `boarded as #<N>`; `yours — in the release report`; `duplicate of <the earlier comment>`; `lapsed — <the rule we do not run>`. **The list is closed, and it covers every end an unfixed finding has** — a true one you are not fixing here leaves by its own pull request, by the board with its fix stated, or by the one ask to the owner, so each of those has a word and none of them is a silence. A fix still gets its one-line `fixed`, so a reviewer's silence remains distinguishable from the builder's. Nothing is bundled, receipted or recorded elsewhere.

Copy each block whole to the filename named above it.

## `greptile.json`

```json
{
  "autoReview": ["open"],
  "labels": ["reviewers"]
}
```

`autoReview: ["open"]` covers opening, reopening, ready-for-review and the trigger label. `triggerOnUpdates` is absent deliberately, because it triggers per-push reviews. Drafts are skipped by the reviewer.

## `.coderabbit.yaml`

```yaml
reviews:
  auto_review:
    enabled: true
    auto_incremental_review: false
    drafts: false
    labels:
      - reviewers
```

`auto_incremental_review: false` stops per-push reviews. `drafts: false` is written rather than inherited from a movable default. Add the repository's own branch names under `base_branches` where it wants to restrict the target branches.

## `AGENTS.md` — `## Code Review Rules`

```md
## Code Review Rules

Review pull requests only when they are marked ready; skip drafts. Post only P0/P1 findings a consumer would act on wrongly. Name the wrong action, not the wording. Where this repository's own convention contradicts a general rule, the convention wins and the comment says so. A deletion is as good a finding as an addition.
```

Codex has no configuration key for this contract; the section in the repository's own always-on agent file is the configuration.

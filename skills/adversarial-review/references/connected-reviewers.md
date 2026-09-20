# Connected reviewers

**Loaded when** configuring a connected reviewer, marking a pull request ready, dispositioning what one posted, or buying a second look after a non-mechanical fix.

Every connected reviewer fires once per pull request, when the pull request is marked ready, never per push. Open the pull request as a draft; run the executable floor and the required experience session, or post its declining line; then mark ready and apply the `reviewers` label. **Every change carries one or the other before ready, mechanical work included** — the line costs a sentence and is what makes ready mean proven. Codex fires on ready without that label. A repository with no connected reviewer owes nothing here.

On issue-backed product work, the `work` cell performs the state read: it returns waiting while a required reviewer has not run and sends only undispositioned threads to the builder. It does not retrigger a reviewer or turn the label into a stage marker.

The `reviewers` label gates Greptile and CodeRabbit. Removing and re-adding it may buy a second look after a non-mechanical fix; that look is permitted, not owed, and a mechanical fix buys none.

Every comment ends in its own thread, by a fix or a one-line reply carrying one of these dispositions: `fixed`; `fixed — nothing else found it`; `fixed in #<N>`; `yours — in the release report`; `declined — <why it earns no end>`; `duplicate of <the earlier comment>`; `lapsed — <the rule we do not run>`. **The list is closed, and it covers every end an unfixed finding has** — a true one you are not fixing here leaves by the follow-up pull request that carries it or by the one ask to the owner, so each has a word and neither is a silence. **A true comment that earns no end at all is declined here, on the work**, which is what the charter already does with a decline outside a review: a finding failing the `filing` cell's bar takes neither of its two ends, and without a word for that it reads as a builder who never answered. A fix still gets its one-line `fixed`, so a reviewer's silence remains distinguishable from the builder's. Nothing is bundled, receipted or recorded elsewhere.

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

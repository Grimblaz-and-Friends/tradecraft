# D-426 — The intake gate sits where issues are created, and asks for a named wrong action

**Decided:** a filing whose subject is governing prose names the wrong action — who acts wrongly today, in what situation, and what they do wrong — or it is not filed. The requirement lands in `skills/filing/SKILL.md`, the cell every filing loads, rather than at the review's terminal stage.

Owner-affirmed on 2026-09-05 on [#405](https://github.com/Grimblaz-and-Friends/tradecraft/issues/405). Both forks below were his and were put argued with a recommendation; he took the recommendation on each. The scope call was the session's and is recorded as such.

## What the defect was

Three sentences in the shipped tree put a finding onto the board. Two self-gate, both in `skills/adversarial-review/references/after-the-fix.md` at `bab184c` — friction met under merged material, and an experience session's finding, are use-originated by construction. The third, in `skills/adversarial-review/references/arbitration.md` at `bab184c`, clause (b), did not:

> …to the board where it would be worth someone's time as its own issue — never filed merely to be seen not dropping it.

That phrase was the whole test. The consumer-consequence bar that would have supplied it opens the same clause — *"**The batch** admits only a finding whose stated consequence is one a consumer would experience"* — and so reaches the fix batch rather than this route; the precedence sentence two after it is scoped to *"wherever fix and record both fit"*. Fix and record; not the board. `skills/filing/SKILL.md` at `bab184c` then declined the question in its description: *"not for deciding whether a finding is worth filing at all."* The cell every filing loads said the worth question was elsewhere, and the elsewhere said only that it should be worth it.

## Fork one — where the gate sits

**Rejected: a bar at the review's terminal stage alone**, extending `arbitration.md`'s existing precedence to cover the board route. It was the smaller change and the session's first instinct. It was rejected on a probe run to discriminate between exactly these two shapes — most open issues state no intake route at all, and only a minority state a review ruling:

```
gh issue list --repo Grimblaz-and-Friends/tradecraft --state open --limit 1000 --json number,body \
  --jq '[.[]|select(.body|test("sustained by [^.]{0,40}review|review sustained|ruled a decision rather than a fix|PR #[0-9]+.s review|judge ruled|terminal stage ruled";"i"))]|length'
```

against the same query without the filter for the denominator. A bar sited at the terminal stage would therefore govern a fraction of the visible intake, and — nothing recording which door an issue came in by — its effect could never be checked afterward. [#416](https://github.com/Grimblaz-and-Friends/tradecraft/issues/416) is the specimen of that route: *"sustained by PR #415's review and ruled a decision rather than a fix."*

**Rejected: no bar at all, and a capped lane instead**, funding prose-rule work as a standing share of capacity under `docs/values.md`'s allocation model and letting a new finding displace the weakest rather than add. Rejected because `docs/values.md` reserves allocation for value that *resists* measurement, and this value can be checked — whether a session acts differently. It also bounds the rate of *working* rather than of *writing*, which is not the want #405 states.

## Fork two — what the gate asks for

**Rejected: a demonstrated wrong action** — an incident that occurred, or a probe showing a session acting wrongly. Strictly stronger and genuinely unfakeable, and rejected because it contradicts `filing`'s own line that creation carries the want and pickup does the work, and would have blocked most filings that are real, #405 itself included on its own terms.

**Rejected: named at filing, demonstrated at pickup.** This moves the gate to the exit rather than the intake; the board still fills at the same rate.

**The known weakness of what was chosen, recorded so a later session need not rediscover it:** a named wrong action is a claim, not evidence, and a fluent session can name a plausible wrong action for almost any imprecise sentence — which is how the phrase it replaces leaked. What makes it bite is that the action must be one taken *today*, under the text as it stands, and that its situation be concrete enough to put to a session holding none of the history. **If the intake rate does not move, this is the first thing to re-examine, and the demonstrated form above is the next option up.**

## The scope call, which was the session's

The requirement reaches filings about governing prose and not every filing. A defect in a script or a guard already carries its consequence in the failure it produces, and the leak the evidence shows is specific to prose. The wider scope was offered to the owner explicitly as a live option and not taken.

## Why an always-on surface moved

`filing`'s description had to change: after this the disclaimer would be false, and a session holding a prose finding and asking whether it earns an issue would be routed away from the one cell that now answers. Under `skills/authoring/references/cell-structure.md` the description is the whole triggering surface, so the edit is a trigger-half change — the new job named, the false non-trigger removed — rather than a summary of the cell's contents. The outflow order in `skills/authoring/references/routing.md` is owed on any always-on edit; it was run and discharged by a refusal, written in the pull request body.

## What was left alone

`arbitration.md` is unchanged. A review-ruled finding that fails this bar already has a home there — the `record` ruling, with recurrence as its promotion path — and restating that disposition in `filing` would be the second copy of a rule that the charter names as the thing that drifts.

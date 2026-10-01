# D-806 — GPT-6.1 Sol becomes the default artifact author

**Purpose:** preserve the owner's artifact-author ruling and the comparison and costs it rests on. **Audience:** a future session changing artifact-author defaults. **Success:** that session can revise the choice without mistaking its limited comparison evidence for a universal model ranking or silently restoring a superseded default.

Recorded in [PR #806](https://github.com/Grimblaz-and-Friends/tradecraft/pull/806), implementing [#804](https://github.com/Grimblaz-and-Friends/tradecraft/issues/804).

## Context

[D-786](D-786-2026-09-29-role-specific-implementers-and-vendor-handover.md) selected Astra 6 at `xhigh` for artifact authors and GPT-6.1 Sol at `xhigh` for builders. The [issue](https://github.com/Grimblaz-and-Friends/tradecraft/issues/804) names the product cost of retaining the author choice: Organizations of Verra, Daemon and Windgust-Questbook pay more for each artifact, and holders must remember an override to obtain the model the owner has since chosen.

The Steward's [2026-09-30 reading of the author comparison](https://github.com/Grimblaz-and-Friends/tradecraft/issues/737#issuecomment-5911232878) records these observations, with Sol listed first in each cost and time pair:

| Instance | GPT-6.1 Sol score | Astra 6 score | Cost at list (Sol / Astra) | Wall time (Sol / Astra) |
|---|---|---|---|---|
| #796 | 36/40, 90.0% | 35/40, 87.5% | $0.55 / $2.24 | 1,253 s / 498 s |
| #792 | 40/42, 95.2% | 37/42, 88.1% | $0.48 / $2.57 | 891 s / 388 s |

The reading's rule, fixed before the instances ran, counted Sol as matching when its score was no more than five percentage points below Astra's and it hit no more traps. Both models hit no traps in either instance; Sol matched and scored higher in both. The reading reports Sol's drafts at about a quarter to a fifth of Astra's list cost and about 2.4 times its wall time. It also records the #792 key's dependence on an item whose premise changed during the run; its reading still holds when that item is removed.

The [issue's case against the switch](https://github.com/Grimblaz-and-Friends/tradecraft/issues/804) is the longer wall time and the #796 judge's observation that Astra closed a path Sol left open: a rewritten commit riding a later push. The comparison supports this author choice on those two instances; it does not establish that Sol is better on every artifact or implementation task.

## Decision

The owner's [2026-09-30 ruling, recorded by the Steward](https://github.com/Grimblaz-and-Friends/tradecraft/issues/737#issuecomment-5920638420), and the [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/804#issuecomment-5922007389) select `gpt-6.1-sol` at `xhigh` as the standing Codex artifact author. The default carries the ruled choice so holders need no author override to obtain it. The ruling also closes the author comparison series and requires no further comparison instance on #798.

This supersedes D-786's artifact-author line. D-786 stays as written as the historical record. Its builder profile, the Claude author profile, judging-seat settings, model-override grammar and machine-local ruling bridge retain their existing choices. The release identifier for this change is `0.164.0` in `.claude-plugin/plugin.json`.

## Evidence

`lib/dispatch_implementer.py` at `fc988d25847974106ee76780e3c3747f9a97f6ee` carries the selected `PROFILES["artifact_author"]["codex"]` pair and the comment citing the ruling. At that commit, `test_implementer_vendor_file_and_role_overrides_are_independent` and `test_report_launch_plan_is_read_only` in `lib/tests/test_work.py` demonstrate the default's resolution, role and vendor independence, and reported launch settings.

The comparison figures above are observations from comment `5911232878`, not a fresh rate-card estimate. Retrieve the source with `gh api --method GET repos/Grimblaz-and-Friends/tradecraft/issues/comments/5911232878`; the ruling and affirmed brief are comments `5920638420` and `5922007389`, respectively. Validate the tree under review with `python tools/lint.py` and `python -m pytest tools/tests skills lib/tests -q`; the entry records commands rather than a frozen suite count.

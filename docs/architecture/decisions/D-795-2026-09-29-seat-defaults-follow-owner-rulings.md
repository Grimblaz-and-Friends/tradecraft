# D-795 — Seat defaults follow the owner's rulings

**Purpose:** preserve the owner's choice of judging-seat defaults and the separate experience-consumer effort. **Audience:** a future session changing seat staffing or the use route. **Success:** that session can revise the defaults without silently undoing an owner ruling or lowering the use consumer's effort through the cold classification.

Recorded in [PR #795](https://github.com/Grimblaz-and-Friends/tradecraft/pull/795), implementing [#787](https://github.com/Grimblaz-and-Friends/tradecraft/issues/787).

## Context

[D-733](D-733-2026-09-23-proof-as-one-act-per-head.md) recorded `gpt-5.6-sol` at `xhigh` as the interim Codex judging-seat choice, and Claude cold and terminal seats at `max`. [D-786](D-786-2026-09-29-role-specific-implementers-and-vendor-handover.md) changed the implementer profiles while retaining that judging-seat model.

On 2026-09-29, the owner [accepted `xhigh` for cold and terminal seats after the real-defect check](https://github.com/Grimblaz-and-Friends/tradecraft/issues/737#issuecomment-5899143068), keeping use consumers at `max` until they have their own evidence. The owner then [chose GPT-6.1 Sol for Codex judging seats](https://github.com/Grimblaz-and-Friends/tradecraft/issues/787#issuecomment-5899421869). These choices become standing defaults so each holder need not repeat them as overrides.

## Decision

| Role | Model | Effort |
|---|---|---|
| Claude ordinary seat | `claude-opus-5-5` | `high` |
| Claude cold or terminal seat | `claude-opus-5-5` | `xhigh` |
| Claude experience consumer through `run use` | `claude-opus-5-5` | `max` |
| Codex judging seat | `gpt-6.1-sol` | `xhigh` |

The use route keeps its recorded classification `cold` and supplies a separate Claude effort default, sourced as `work entrance use-consumer default`. A `use_consumer` override still wins. A consumer launched directly through `dispatch_seat.py --classification cold` takes `xhigh`, so a hand launch retaining `max` supplies `--claude-effort max`.

Applying the lowered cold effort to use consumers would contradict the owner's separate ruling. Adding a new record classification is unnecessary: the route can preserve the class vocabulary and name its own effort source.

This supersedes D-733's interim Codex judging-seat model and Claude cold and terminal efforts. It preserves the Claude seat model, ordinary effort, Codex effort, and D-786's artifact-author and builder profiles. The compatibility probe's separate model is unchanged. The Steward retains retirement of #683's interim override lines after landing.

## Evidence

`lib/dispatch_seat.py` and `lib/work.py` at `9239bb6c480b57db9388851f1322b51dcdd457bc` carry the chosen defaults and separate use route. At that commit, `test_claude_effort_defaults_from_judgment_classification` and `test_real_child_receives_large_utf8_dispatch_and_exact_launch` in `lib/tests/test_dispatch_seat.py` demonstrate the direct launcher defaults; `test_launch_settings_read_program_b_defaults_with_accurate_sources` and `test_run_use_launches_only_with_the_holder_job_and_validated_tree` in `lib/tests/test_work.py` demonstrate the effort sources, retained cold classification, and override precedence.

Validate the tree under review with `python tools/dev.py lint` and `python tools/dev.py test tools/tests skills lib/tests -q -n auto --dist loadfile`; the entry records the commands rather than freezing a suite count.

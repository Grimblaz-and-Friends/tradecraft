# D-824 — Disable the apps feature for Codex judging seats

**Purpose:** preserve the feature boundary and the deliberate decision to fix this instance without measuring a launched seat's capabilities. **Audience:** a future session changing seat isolation or dispatch records. **Success:** that session understands why per-app configuration is insufficient and why no capability check was built.

Governed by [#783's affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/783#issuecomment-5958636706), rows 1 and 2 and its Not this. The implementation is `9f130ecf0e7740a21cf88b7b01cdf2a747911c18` in [pull request #824](https://github.com/Grimblaz-and-Friends/tradecraft/pull/824).

## Decision

Every Codex judging seat disables the apps feature with `--disable apps`, retaining `apps._default.enabled=false` beside it. Its recorded boundary names `apps=disabled-by-feature`. Relying on the per-app remedy alone, landed for [#625 in #665's first instalment](https://github.com/Grimblaz-and-Friends/tradecraft/pull/666), is rejected: the holder's pre-put probe in the affirmed brief's history still found the `codex_apps` catalogue under those flags. That history records the two Codex arms and their canary reads, the unknown-feature control, and the separate Claude read-tool probe; these are the holder's observations. A Codex that does not recognise the feature switch fails the launch visibly. Detecting an older Codex to retry with the switch dropped is rejected because it restores the boundary this change removes.

The owner affirmed fixing this instance without building a measurement of what a launched seat actually holds. The boundary is recorded from launch flags, rather than observed capabilities; the brief traces the recurring gap through [#625](https://github.com/Grimblaz-and-Friends/tradecraft/issues/625), [#732](https://github.com/Grimblaz-and-Friends/tradecraft/issues/732), [#771](https://github.com/Grimblaz-and-Friends/tradecraft/issues/771) and [#783](https://github.com/Grimblaz-and-Friends/tradecraft/issues/783). Its row 2 gives the reasons: Codex records no startup server inventory, so the available measurement is a model run whose apps answer is the model's own report, while each attempt already records its runtime version for tracing later drift. The absence of a capability check is this affirmed choice, not an implementation omission.

The brief excludes implementer-launch and Claude-launch changes, reading catalogue resources, rewriting past records, and the separate charter-stop cause in #782.

## Evidence and process

`lib/dispatch_seat.py` at `9f130ecf0e77` demonstrates the command, flag-derived boundary, refusal route and runtime-version record. `lib/tests/test_dispatch_seat.py` at `9f130ecf0e77` pins primary and fallback launches, boundary records and feature rejection without retry or publication. `skills/engagement/references/dispatch-records.md` at `9f130ecf0e77` carries the shipped account of that boundary.

The brief was put whole without design turns, with row 2's fork already argued to a recommendation; the Steward recorded that departure as [#769's second instance](https://github.com/Grimblaz-and-Friends/tradecraft/issues/769#issuecomment-5958656836).

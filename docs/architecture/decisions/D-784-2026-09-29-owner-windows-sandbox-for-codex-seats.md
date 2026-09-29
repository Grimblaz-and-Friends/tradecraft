# D-784 — Let each Windows machine choose its Codex seat sandbox

**Purpose:** preserve why a Windows Codex judging seat imports exactly its machine owner's sandbox mode, and why an unusable mode is pre-launch unavailability rather than a result interpreted after the seat returns. **Audience:** a future session changing Codex seat isolation, Windows launch configuration, availability fallback, or dispatch records. **Success:** that session can revise the mechanism without restoring a fixed sandbox mode, importing the owner's wider configuration, or accepting a blind seat as a successful judge.

Governed by [issue #771](https://github.com/Grimblaz-and-Friends/tradecraft/issues/771), its [affirmed implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/771#issuecomment-5880944839), [pre-implementation artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/771#issuecomment-5881033567), [`would`-route settlement](https://github.com/Grimblaz-and-Friends/tradecraft/issues/771#issuecomment-5881145237), [cold verdict](https://github.com/Grimblaz-and-Friends/tradecraft/issues/771#issuecomment-5881144979), and [holder reading](https://github.com/Grimblaz-and-Friends/tradecraft/issues/771#issuecomment-5881148328). The implementation is commit `9e87c5537ecb363dc465b5d9eba9684569fc8b0e` in [pull request #784](https://github.com/Grimblaz-and-Friends/tradecraft/pull/784).

## Context

The launcher had begun ignoring the owner's Codex configuration to keep signed-in apps and other owner state out of judging seats. On this Windows machine that same configuration held `[windows].sandbox`, which the Codex runtime needed before its read-only seat could execute a file-reading command. The [issue record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/771) preserves the resulting failure: a seat had every attempted read refused by policy, returned prose saying it was blocked, and was nevertheless recorded as a qualified success.

The brief's three-arm probe on Codex CLI 0.155.0-alpha.16 separated the setting from the launcher policy. The shipped isolated command read nothing; adding the owner's `elevated` value read the file; changing only that value to `unelevated` ran commands but denied the file. The launcher could therefore neither choose one portable constant nor omit the machine's choice while claiming the seat could read.

## Decision

### Carry one owner value, unchanged

On Windows, a Codex read seat takes exactly `[windows].sandbox` from the effective owner configuration: `config.toml` beneath `CODEX_HOME` when that environment variable is set, otherwise `config.toml` beneath the user's `.codex` directory. The launcher passes the nonempty string as one encoded configuration override and records its resolved file-and-key source. It does not validate the value by replacing it with a launcher preference; the machine's owner chose the sandbox implementation that machine can use.

Every other owner setting remains excluded. `--strict-config`, `--ignore-user-config`, the explicit default-app disable, and the seat's separate `--sandbox read-only` policy remain. The Windows value selects the runtime's local sandbox implementation; `read-only` remains the judging seat's filesystem policy. Keeping those layers distinct restores command access without reversing the configuration isolation that caused this issue to be worth fixing.

### Refuse an unusable value before launch and use availability fallback

A missing configuration file, missing key, unreadable or malformed TOML, or a non-string or empty value cannot supply a Windows Codex read seat. The Codex attempt is recorded as unlaunched and unavailable before executable resolution, with the cause naming `windows.sandbox` and its source or read failure. The existing one-step availability fallback then tries the caller's distinct capable vendor; if none can finish, the unavailable Codex attempt and reason remain and no Codex verdict is published.

This cannot be repaired by inspecting the return. Codex does not put the refused commands in the stream this launcher reads, while a lawful read seat may answer entirely from its prompt and run no command. A successful-looking return therefore cannot prove that the seat could read. The missing mode is a capability the machine cannot supply, known before launch; it is not an in-run permission denial, which remains outside availability fallback.

For a launched Windows Codex attempt, the request and attempt boundaries state both sandbox layers, the selected mode, and its resolved source, and the setting-source map carries that provenance. A refused attempt claims no live permission boundary. This lets a later holder distinguish the sandbox policy requested from the machine implementation that actually ran it.

## Rejected alternatives and boundaries

**Fix the launcher to `elevated`, `unelevated`, or another universal mode.** Rejected because the probe demonstrated materially different behavior from the two sandbox values tried—the machine owner's configured `elevated` value and the comparison arm `unelevated`—and the brief establishes that no one value serves every machine. A launcher constant would silently replace the machine owner's working choice.

**Load the owner's whole Codex configuration, drop `--ignore-user-config`, or carry apps and plugins with the sandbox setting.** Rejected because it reverses the isolation bought when signed-in apps were removed from judging seats. Parsing the file does not make its other values launch inputs or record values; only `windows.sandbox` crosses.

**Make the holder pass a flag or add a parallel holder-entry option.** Rejected because the caller would have to repeat machine configuration, direct launcher callers would miss it, and the common launcher already owns both direct and work-constructed judging seats.

**Detect a blind seat after it returns.** Rejected because the observed refusal is absent from the stream the launcher interprets, and absence of a command is lawful behavior for some read jobs. Treating every no-command turn as failure would reject valid cold seats while still lacking proof of what the runtime allowed.

**Use `codex sandbox` as a model-free pre-launch check.** Rejected on the holder's 2026-09-28 design observation against Codex CLI 0.155.0-alpha.16: that command refuses to run without `--permission-profile <NAME>`, offers no `--ignore-user-config`, describes `-c` as overriding values loaded from `~/.codex/config.toml`, and layers `-p` on the base user configuration. It would test a different configuration boundary from the isolated seat launch.

**Repair the charter stop or the still-visible app surface here.** Rejected as different causes. Carrying the practice plugin into a judging seat would give it the practice it is meant to judge without; the visible-app leak was a separate observed surface and changed no affirmed row. The holder routed those facts to the Steward, which filed [#782 and #783](https://github.com/Grimblaz-and-Friends/tradecraft/issues/771#issuecomment-5880963529).

## Evidence retained with the implementation

`lib/dispatch_seat.py` at `9e87c55` demonstrates the single-value selection, encoded override, pre-launch refusal, fallback, and boundary/source record. `lib/tests/test_dispatch_seat.py` at `9e87c55` retains configured `elevated` and `unelevated` cases, unrelated-setting sentinels, literal encoding, every unusable-source class, no-resolution refusal, successful and unavailable fallback, recorded provenance, and the unchanged non-Windows, Claude, and execute paths. `skills/engagement/references/dispatch-records.md` at `9e87c55` is the shipped description of the same boundary. These pinned files and the issue records above are the demonstrators; this entry freezes no test count.

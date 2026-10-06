# Launch settings and the ruling bridge

**Purpose:** let a holder see a launch's settings and let a sourced machine ruling reach still-defaulted fields. **Audience:** holders, whoever records a machine ruling on the owner's word, and callers of either launcher. **Success:** the report, printed plan, command and retained sources agree, and a ruling yields to explicit choices and lapses when its replaced default changes.

The entrance's `launch_settings` names the stage, role, continuity, primary vendor/model/effort and each source. Judging stages also show fallback settings and their eligibility. Each selection includes its running `baseline`, which is the pair a bridge entry must replace. A resume separately shows the selected session's recorded request and native observations; the current request is not evidence of the historical model. `run` resolves afresh and prints that plan before invoking a launcher. Both launchers print settings before the recipient starts.

For artifact runs, `artifact_copy` also names the actual recipient `root`, canonical `holder_root`, captured `source_commit`, `committed_only: true`, observed `remotes: []`, allocation identity and external `lifecycle_record`. Its `lfs_mode: pointers` and `lfs_pointer_count` name the pointer policy and observed tracked-path count; a planned allocation reports a null count until checkout. When retained files are missing or damaged, `artifact_copy_recovery` names the old copy, cause and lost working files, and the author receives that explanation in its entrance context. The captured commit stays distinct from the author's later revisions. The executed plan marks the copy `verified: true`; a read-only plan marks a proposed allocation `selection: planned`, `root: null`, `remotes: null` and `verified: false`, or names a recorded retained copy without claiming a fresh allocation. Its `permission_boundary` distinguishes Codex's workspace-write route from Claude's lack of an OS write sandbox, because a root alone establishes no confinement.

## Machine file

Read the running pair from the report or launcher's printed settings before writing `~/.tradecraft/model-rulings.json`. The reader creates nothing. Versions older than the release that ships this bridge ignore the file; a session running one of those versions must move to a bridge-capable version before a ruling can reach it.

```json
{
  "schema_version": 1,
  "entries": [
    {
      "id": "example-cold-ruling",
      "role": "cold_seat",
      "vendor": "claude",
      "replaces": {"model": "old-model", "effort": "old-effort"},
      "model": "ruled-model",
      "effort": "ruled-effort",
      "source": "https://github.com/OWNER/REPO/issues/N#issuecomment-ID"
    }
  ]
}
```

These are illustrative values, not a ruling to install. Roles use the override marker's spellings: `artifact_author`, `implementer`, `ordinary_seat`, `cold_seat`, `terminal_seat`, `use_consumer`. Vendors are `codex` and `claude`. All shown fields are required and no others are accepted. IDs and role/vendor pairs are unique. Strings are nonempty; models and efforts contain no whitespace or colon. The source is a record locator, retained rather than fetched. Duplicate JSON keys, unsupported schemas and unreadable or malformed present files refuse resolution before launch side effects. Absence or an empty entries list preserves the running defaults. Holder endpoints that launch nobody do not read this file.

## Precedence and lapse

An explicit issue choice or direct launcher field wins, then an applicable bridge, then the shipped default. The latest lawful issue override remains a whole choice: omitted roles and a clearing line return to default resolution, including the bridge. Direct callers may supply just one field; the other still defaults. A supplied value remains explicit even if its text equals the default. The bridge never selects a vendor.

An entry applies only when both fields of `replaces` exactly equal that call's running baseline. Any change to either field makes it `lapsed`; the printed plan names the entry, ruling source, expected pair and running pair. Readers leave the file intact. Each entry point keeps its own baseline: the entrance's Claude use effort is `max`, while a direct seat still uses its classification default. An older bridge-capable version can still match a pair that a newer version has changed.

Each supplied field's retained source names the resolved file path, entry ID, role/vendor, replaced and ruled pairs and ruling locator, so a reader can reconstruct the choice after the file changes or disappears. A run uses one snapshot for its printed plan and command. Direct seats resolve both vendors together and keep that snapshot through fallback; a later invocation reads afresh.

Direct seats accept `--role` using the same six spellings. Seat roles must agree with `--classification`; `use_consumer` uses `cold`. Without a role, stage `use` infers `use_consumer`, stage `cold-seat` infers `cold_seat`, and other stage labels infer the seat role from classification. Author and implementer roles belong to `dispatch_implementer.py`. The entrance passes the role explicitly.

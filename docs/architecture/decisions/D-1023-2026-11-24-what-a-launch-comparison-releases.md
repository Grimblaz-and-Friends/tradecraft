# D-1023 — What a launch comparison releases

**Purpose:** record why #946 has a Claude launch's before-and-after comparison release the plugin files every session's runtime keeps up, and read the two plugin install records by what they say, rather than holding a change for each. It also records the calls made inside the brief's rows. **Audience:** a future session changing what a launch comparison holds on, or adding a kind it releases. **Success:** that reader can recover what was chosen over what without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/946#issuecomment-7145641431) governs. Its [pre-implementation artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/946#issuecomment-7146109619) was settled by the recorded cap resolution, and one builder carried the change to ready on the builder route. The lane is ordinary / connected, and no panel was bought. This record supersedes none; it narrows [D-939](D-939-2026-11-03-claude-launch-writes-stay-in-their-tree.md)'s comparison, which held every unattributed change and read every file by size and time or digest.

## What it cost before

Over the comparisons recorded on the owner's machine that ended before 24 November 2026, 540 launches held their change's next stage until the holder posted an account, 104 of them from 13 November on. Replaying those records under the released kinds and the version-folder rule releases 423 of the 540, and 91 of the 104. One plugin update during a product build alone put 1,174 findings into its comparison.

## What was chosen over what

- **Release by kind (route A), over crediting a change only when it fell outside the launched session's own commands (B), and over fencing what the builder can reach (C).** The owner first chose B ("B, reopen #937", 2026-11-24). Its premise, that the runtime's housekeeping lands between the builder's commands, was then measured: a launch's tool calls cover a median 82% of its window, so B could release at most about 28% of held launches. The owner switched to A ("Switch to A"). C's choice of fence stays the owner's, on #937.
- **Read the two install records by content, over releasing them like the caches and over holding them as before** (the owner's ruling, "Read by content"). They decide which plugin code every later session loads and where its updates come from, so a launch that really changed them should still hold; the app rewrites their time fields at every refresh. This is the first content read in the comparison, against D-939's rule that trees are compared by size and time and single files by digest. Only these two files are read, and only the release's basis and a held change's reason carry any of their contents into the run record.
- **Release at the comparison, not at the entrance.** Only the comparison holds the install records' starting contents, and a record made before this keeps its findings and hold untouched; reading an old record under the new rules would release some of its findings and not others.
- **A released change stays in the run record** under `released`, rather than leaving the comparison, so a holder or a read across changes can see what was released and catch a kind that releases more than it should.

## Calls made inside the rows

- **Only the listed fields are compared.** In `known_marketplaces.json`, the marketplace names and each one's `source` and `installLocation`; in `installed_plugins.json`, the plugin keys and each key's entries as `scope`, `projectPath`, `installPath` and `version`. The file's own `version` and any field the app adds later, such as `gitCommitSha`, are ignored, as the brief's "only when" requires.
- **An install entry is paired with its successor by scope and project,** or, when one entry left a key and one came, with that one, so a held change can name the field that moved. A pair releases only when `version` and `installPath` both moved and the new path is a version folder added in the same comparison.
- **The catalog cache is matched by its name's prefix,** `plugin-directory-cache…json`, so a renamed catalog version still releases. Its contents list what could be installed, not what loads.
- **The version-folder rule crosses items** by absolute path, so a launcher running from a version an update retired doesn't hold on its own files.
- **A kind that names a folder or a file releases only that type** where the walk knows it, so a link or a folder named like an upkeep file still holds. A recorded finding carries no type, so the replay reads by name, as the brief's counts did.
- **Where two kinds fit one change, the first names it,** so an in-use marker inside a retired version is recorded as an in-use marker.
- **A released change carries an `id` made as a finding's is,** so a later reader can cross-reference it with an account.
- **The existing golden comparison test pops `released` and asserts it empty** before comparing the rest to its literal, because the golden covers no plugins folder; the literal is unchanged.

The tests are `lib/tests/test_launch_release.py` (each kind in both items and with either separator, what still holds, the install records and marketplace clones, the run record and the entrance's reading, a record from before, and the fixture driver), with `lib/tests/release_fixture.py` driving the real snapshot and comparison for the use session, and `lib/tests/test_launch_bound.py`.

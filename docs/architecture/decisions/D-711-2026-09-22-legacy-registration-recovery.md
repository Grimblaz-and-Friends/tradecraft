# D-711 — Recover legacy implementation registrations without weakening isolation

**Landed by** [PR #711](https://github.com/Grimblaz-and-Friends/tradecraft/pull/711). Closes [#702](https://github.com/Grimblaz-and-Friends/tradecraft/issues/702). Governed by the [affirmed implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/702#issuecomment-5770455724), the [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/702#issuecomment-5770596893), its cold [`would` verdict](https://github.com/Grimblaz-and-Friends/tradecraft/issues/702#issuecomment-5770596785), and the [holder's whole-change reading](https://github.com/Grimblaz-and-Friends/tradecraft/issues/702#issuecomment-5770605984). This correction was authored against `a7d00b6774aee46c0dfc9c2a655ca3391034898e`; the change's base is `2a0d4596fb63608e71b269f9aea63886b9e50ad3`.

## Context

Commit `f121ac38c6cc14d33b7cc2feb20970c50a7d0e4a` added `holder_root` and `branch` to implementation-worktree registrations and then required both when resolving an active row. A row written by an older entrance therefore became unusable while active. Releasing it did not provide a route back once a pull request existed: every remaining stage required an active registration, while fresh creation remained a fresh-build path only.

This decision records two recovery routes, the isolation boundary between them, and the reversal made when connected review supplied a consequence omitted from the first ruling. It does not repeat PR #711's path departures, which remain in that pull request's body.

## Decision

### An exact legacy row migrates only into a distinct implementation root

The resolver treats a row as legacy only when both `holder_root` and `branch` are absent. It takes the canonical holder root from the invocation and proves that the row's named root exists and is its Git worktree top level. If the two resolved roots are the same path, migration refuses and names `adopt` with a distinct implementation root as the recovery route. Otherwise it reads the implementation tree's attached branch, proves that both roots share a Git common directory, writes the invocation root and observed branch atomically, and applies the ordinary current-row checks. The first migrated read cannot compare the invocation with a holder value the old row never recorded.

That proof gap remains visible rather than silent. The decision says `implementation registration migrated; recorded-holder check was not enforced on this run`, preserving any existing detail. Later reads use the persisted current shape and enforce the ordinary holder and branch comparisons. Before this fix batch, the shared resolver and its use-stage path are visible in [`lib/work.py` at `a7d00b6774aee46c0dfc9c2a655ca3391034898e`](https://github.com/Grimblaz-and-Friends/tradecraft/blob/a7d00b6774aee46c0dfc9c2a655ca3391034898e/lib/work.py); the same-root refusal is the isolation correction this batch adds there.

### `adopt` is the explicit recovery route

Where migration cannot safely use the recorded root, `adopt` registers a holder-named existing worktree without dispatching or moving it. The command requires holder identity and proves that the holder and implementation roots are distinct Git worktree top levels sharing one Git common directory. It accepts any attached branch except a branch with another issue's entrance-created `tradecraft/<issue>-<twelve hex characters>` shape. Fresh registration checks no pre-existing branch shape because it creates the branch itself; accepting an ordinary legacy branch therefore does not weaken the affirmed row's requirement that adoption use proofs no weaker than fresh registration's.

Adoption also refuses an omitted `--instalment` when any named instalment registration exists for the repository and issue. Omission otherwise makes `_row_matches_change` issue-wide and could silently deactivate sibling instalments. Requiring the holder to name the intended instalment preserves those rows and leaves the registry unchanged on ambiguity. On success, one atomic write deactivates the matching registration rows and appends one current-shaped active row.

At the authoring commit, [`lib/work.py` at `a7d00b6774aee46c0dfc9c2a655ca3391034898e`](https://github.com/Grimblaz-and-Friends/tradecraft/blob/a7d00b6774aee46c0dfc9c2a655ca3391034898e/lib/work.py) shows both constraints this batch replaces: the current-issue branch-shape requirement and issue-wide matching when `instalment` is absent. [`lib/tests/test_work.py` at `a7d00b6774aee46c0dfc9c2a655ca3391034898e`](https://github.com/Grimblaz-and-Friends/tradecraft/blob/a7d00b6774aee46c0dfc9c2a655ca3391034898e/lib/tests/test_work.py) is the pre-fix test surface extended by this batch.

### The same-root choice was reversed when the builder-write consequence was put

The settled artifact's AC5 made `adopt` refuse the holder checkout as an implementation root, while AC2's four migration proofs were all satisfied by a legacy row whose `root` was that checkout. Neither the brief nor the artifact settled the disagreement. The first builder decision accepted same-root migration. Its reason was that refusal would recreate the all-stage wedge, while the holder guard would make the accepted checkout read-only to the holder. A bounded probe supported that description: migration persisted `holder_root == root`; [`lib/holder_tree_guard.py` at `a7d00b6774aee46c0dfc9c2a655ca3391034898e`](https://github.com/Grimblaz-and-Friends/tradecraft/blob/a7d00b6774aee46c0dfc9c2a655ca3391034898e/lib/holder_tree_guard.py) refused a holder write there and allowed a finite read-only command. On that description, the owner ruled on 2026-09-22, **"keep it as built, mark it ready"**.

That description omitted the decisive actor. Migration does not merely register a tree the holder can inspect: the entrance dispatches the builder into the resolved implementation root. The holder write guard restrains holder tools and does not restrain builder writes, so accepting the holder checkout gives the builder write access to the very tree the separate-worktree format exists to isolate. Codex raised that omission in connected review. Because the first ruling was made without this consequence, the choice was put to the owner again rather than treated as settled.

The owner superseded the earlier ruling on 2026-09-22: same-root migration refuses, and `adopt` widens to accept a distinct same-repository legacy worktree on an ordinary attached branch while still refusing another issue's entrance branch. The earlier quoted ruling remains above as the actual first ruling, but it no longer governs what ships. Widened adoption is what makes the refusal safe: the row is not silently trusted and the holder has an explicit route to register a distinct legacy tree rather than being stranded.

### The measured population is evidence, not an inferred holder identity

The [holder's recorded classification](https://github.com/Grimblaz-and-Friends/tradecraft/issues/702#issuecomment-5770755281) inspected whether each of the six legacy roots on this machine carries a `.git` directory, the main-checkout form, or a `.git` file, the linked-worktree form. Three were main checkouts:

- Daemon #31 at `C:\Users\Micah\Code\Daemon`;
- change-proof #13 at `C:\Users\Micah\Code\change-proof`; and
- Organizations-of-Verra #467 at `C:\Users\Micah\Code\Organizations-of-Elos`.

The other three were linked worktrees for tradecraft #678, #684 and #700. All six roots existed when classified.

That observation has two limits. First, a main checkout is only a proxy for *the root a holder would pass*. Migration compares the recorded `root` with the invocation's `--root`, and no legacy row contains the holder root whose equality is at issue. The classification establishes the shape and its examples, not what a past holder invoked. Second, the population is not closed. A session running a pre-`f121ac3` entrance from a cached plugin version can still write a new row of this shape; [#707](https://github.com/Grimblaz-and-Friends/tradecraft/issues/707) owns that version-straddle problem.

### The earlier holder-warning rider stays here, not in shipped prose

Before the reversal, the holder recommended warning that same-root migration could make a repository's main checkout read-only to the holder. The owner initially ruled on the migration choice, not that rider. The holder then recommended, and the owner agreed on 2026-09-22, that the observation belongs in this entry rather than shipped prose: the condition requires a row written before `f121ac3`, so a current first-time installer cannot reach it and should not be bound by an instruction about it.

The superseding refusal removes the behavior that warning would have explained, so no holder-facing sentence is added. Evidence that an adopter upgraded across `f121ac3` with a row in flight would change the population premise and reopen whether recovery guidance belongs in shipped prose; finding that evidence is #707's territory.

## Rejected alternatives and consequences

**Infer the holder root from the repository's other worktree.** Rejected because there is no unique other worktree. The affirmed brief records `git worktree list` on the design tree at `2a0d4596fb63608e71b269f9aea63886b9e50ad3` returning 110 worktrees sharing this repository's common directory. The invocation is the only available holder claim, and migration says exactly which comparison that prevents on the first safe read.

**Refuse every legacy row outright.** Rejected because it strands the work the registration was protecting. The durable-record standard in [`skills/substrate/SKILL.md` at `a7d00b6774aee46c0dfc9c2a655ca3391034898e`](https://github.com/Grimblaz-and-Friends/tradecraft/blob/a7d00b6774aee46c0dfc9c2a655ca3391034898e/skills/substrate/SKILL.md) states that a record-shape change owes existing records a migration or recovery route for this reason. This decision refuses only the unsafe same-root case and supplies widened adoption as its recovery.

**Require every adopted branch to have the current issue's entrance shape.** Rejected because old entrances legitimately registered ordinary branches, making that proof exclude the exact population explicit recovery must reach. Refusing only another issue's entrance-shaped branch retains the misidentification guard without pretending fresh registration proved a pre-existing branch shape.

**Make release the only recovery.** Rejected because release merely makes the row inactive. With a pull request open, the dispatch-root selection in [`lib/work.py` at `a7d00b6774aee46c0dfc9c2a655ca3391034898e`](https://github.com/Grimblaz-and-Friends/tradecraft/blob/a7d00b6774aee46c0dfc9c2a655ca3391034898e/lib/work.py) does not create a fresh tree for a resumed stage and returns `no active implementation registration matches`. `adopt` is the explicit way to make release reversible without weakening automatic selection.

## Evidence

The fix batch adds `test_legacy_migration_refuses_holder_root_and_names_adopt`, `test_adopt_accepts_a_non_entrance_branch`, `test_adopt_refuses_another_issues_entrance_branch_without_changing_registry`, and `test_adopt_requires_an_instalment_when_named_registrations_exist`. The full repository floor is `python tools/dev.py check`; it is run after this entry and its index row are written, so this frozen entry cannot name the commit those additions produce.

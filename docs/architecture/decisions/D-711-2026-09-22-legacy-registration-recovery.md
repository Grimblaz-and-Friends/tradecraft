# D-711 — Recover legacy implementation registrations without weakening proof

**Landed by** [PR #711](https://github.com/Grimblaz-and-Friends/tradecraft/pull/711). Closes [#702](https://github.com/Grimblaz-and-Friends/tradecraft/issues/702). Governed by the [affirmed implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/702#issuecomment-5770455724), the [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/702#issuecomment-5770596893), its cold [`would` verdict](https://github.com/Grimblaz-and-Friends/tradecraft/issues/702#issuecomment-5770596785), and the [holder's whole-change reading](https://github.com/Grimblaz-and-Friends/tradecraft/issues/702#issuecomment-5770605984). The implementation before this entry is `624298a42b33e635ee0ddf96b0ec70ef51a991a3`; its base is `2a0d4596fb63608e71b269f9aea63886b9e50ad3`.

## Context

Commit `f121ac38c6cc14d33b7cc2feb20970c50a7d0e4a` added `holder_root` and `branch` to implementation-worktree registrations and then required both when resolving an active row. A row written by an older entrance therefore became unusable while active. Releasing it did not provide a route back once a pull request existed: every remaining stage required an active registration, while fresh creation remained a fresh-build path only.

This decision records the two recovery routes and the one disagreement between them that surfaced after the artifact settled. It does not repeat PR #711's path departures, which remain in that pull request's body.

## Decision

### An exact legacy row migrates on proved facts

The resolver in [`lib/work.py` at `624298a`](https://github.com/Grimblaz-and-Friends/tradecraft/blob/624298a42b33e635ee0ddf96b0ec70ef51a991a3/lib/work.py) treats a row as legacy only when both `holder_root` and `branch` are absent. It takes the canonical holder root from the invocation, proves that the row's named root exists and is its Git worktree top level, reads that tree's attached branch, and proves that holder and implementation roots share a Git common directory. It then writes the two recovered fields atomically and applies the ordinary current-row checks, except that the first migrated read cannot compare the invocation with a holder value the old row never recorded.

That proof gap is visible rather than silent. The dispatching decision says `implementation registration migrated; recorded-holder check was not enforced on this run`, preserving any existing detail. Later reads use the persisted current shape and enforce the ordinary holder and branch comparisons. The migration, refusal, persistence-failure, decision-output and later-enforcement cases are demonstrated by [`lib/tests/test_work.py` at `624298a`](https://github.com/Grimblaz-and-Friends/tradecraft/blob/624298a42b33e635ee0ddf96b0ec70ef51a991a3/lib/tests/test_work.py).

### `adopt` is the explicit recovery route

Where migration cannot reach a row, `adopt` registers a holder-named existing worktree without dispatching or moving it. The command requires holder identity; proves the holder and implementation roots are distinct Git worktree top levels with one common directory; requires an attached branch matching `tradecraft/<issue>-<twelve hex characters>`; deactivates every competing row for the named change; and writes one current-shaped active row. [`lib/work.py` at `624298a`](https://github.com/Grimblaz-and-Friends/tradecraft/blob/624298a42b33e635ee0ddf96b0ec70ef51a991a3/lib/work.py) carries the command and [`lib/tests/test_work.py` at `624298a`](https://github.com/Grimblaz-and-Friends/tradecraft/blob/624298a42b33e635ee0ddf96b0ec70ef51a991a3/lib/tests/test_work.py) demonstrates success, unchanged-registry refusals, one-active-row atomicity and non-dispatch.

The branch-shape proof is stronger than fresh registration's repository and worktree proofs. The affirmed row permits that strengthening: adoption exists to recover an entrance-created tree, not to claim an arbitrary same-repository checkout. It therefore refuses the holder checkout itself as well as a tree for another issue.

### Same-root migration is accepted even though same-root adoption is refused

The artifact's AC5 requires `adopt` to refuse the holder checkout as an implementation root. AC2's migration proofs do not: a legacy row whose `root` is the checkout passed as `--root` can exist, be its Git top level, have an attached branch and share its own common directory. Neither the brief nor the artifact settled that disagreement. The [holder's note](https://github.com/Grimblaz-and-Friends/tradecraft/issues/702#issuecomment-5770744912) put both consequences on the record.

The builder kept migration accepting that row. A bounded floor probe at `624298a42b33e635ee0ddf96b0ec70ef51a991a3` created a temporary repository and exact legacy active row with `root` equal to the invocation's holder root, then called the resolver and holder guard directly. Migration returned that root and persisted `holder_root == root` plus the observed branch; the guard in [`lib/holder_tree_guard.py` at `624298a`](https://github.com/Grimblaz-and-Friends/tradecraft/blob/624298a42b33e635ee0ddf96b0ec70ef51a991a3/lib/holder_tree_guard.py) refused a `Write` beneath it and allowed the finite read-only command `Get-Content fixture.txt`. The probe used only temporary state and left the repository and live registry unchanged.

Refusing this case would recreate the all-stage wedge for work an older entrance legitimately put in a main checkout. Accepting it preserves the change while treating that checkout as the active implementation tree: the holder may inspect it but does not write there until the registration is released. Explicit adoption remains stricter because it is a deliberate current-version recovery with a separate entrance-created tree available as its safe target. On 2026-09-22 the owner ruled, **"keep it as built, mark it ready"**.

### The measured population is evidence, not an inferred holder identity

The [holder's recorded classification](https://github.com/Grimblaz-and-Friends/tradecraft/issues/702#issuecomment-5770755281) inspected whether each of the six legacy roots on this machine carries a `.git` directory, the main-checkout form, or a `.git` file, the linked-worktree form. Three were main checkouts:

- Daemon #31 at `C:\Users\Micah\Code\Daemon`;
- change-proof #13 at `C:\Users\Micah\Code\change-proof`; and
- Organizations-of-Verra #467 at `C:\Users\Micah\Code\Organizations-of-Elos`.

The other three were linked worktrees for tradecraft #678, #684 and #700. All six roots existed when classified.

That observation has two limits. First, a main checkout is only a proxy for *the root a holder would pass*. Migration compares the recorded `root` with the invocation's `--root`, and no legacy row contains the holder root whose equality is at issue. The classification therefore establishes the shape and its live examples, not what a past holder invoked. Second, the population is not closed. A session running a pre-`f121ac3` entrance from a cached plugin version can still write a new row of this shape; [#707](https://github.com/Grimblaz-and-Friends/tradecraft/issues/707) owns that version-straddle problem.

### The holder-facing warning remains unresolved and stays local

The holder recommended warning before the behavior that same-root migration can make a repository's main checkout read-only to the holder. The owner ruled on keeping the implementation, not on whether that warning should become a holder-facing instruction. The rider therefore remains unresolved.

The holder later recommended, and the owner agreed on 2026-09-22, that the rider belongs in this entry rather than shipped prose. A freshly installed current plugin cannot create the condition: it requires a row written before `f121ac3`. Shipping an instruction would bind adopters to a state they cannot reach. Evidence that an adopter upgraded across `f121ac3` with such a row in flight would reopen the siting; finding and recording that version straddle belongs to #707.

## Rejected alternatives and consequences

**Infer the holder root from the repository's other worktree.** Rejected because there is no unique other worktree. The affirmed brief records `git worktree list` on the design tree at `2a0d4596fb63608e71b269f9aea63886b9e50ad3` returning 110 worktrees sharing this repository's common directory. The invocation is the only available holder claim, and migration says exactly which comparison that prevents on the first read.

**Refuse legacy rows outright.** Rejected because it strands the work the registration was protecting. The durable-record standard in [`skills/substrate/SKILL.md` at `624298a`](https://github.com/Grimblaz-and-Friends/tradecraft/blob/624298a42b33e635ee0ddf96b0ec70ef51a991a3/skills/substrate/SKILL.md) states that a record-shape change owes existing records a migration or recovery route for this reason.

**Make release the only recovery.** Rejected because release merely makes the row inactive. With a pull request open, the dispatch-root selection in [`lib/work.py` at `624298a`](https://github.com/Grimblaz-and-Friends/tradecraft/blob/624298a42b33e635ee0ddf96b0ec70ef51a991a3/lib/work.py) does not create a fresh tree for a resumed stage and returns `no active implementation registration matches`. `adopt` is the explicit way to make release reversible without weakening automatic selection.

## Evidence

The implementation behavior is demonstrated by the focused migration and adoption tests in [`lib/tests/test_work.py` at `624298a`](https://github.com/Grimblaz-and-Friends/tradecraft/blob/624298a42b33e635ee0ddf96b0ec70ef51a991a3/lib/tests/test_work.py), with the same-root case bounded by the temporary probe recorded above. The full repository floor is `python tools/dev.py check`; it is run after this entry and its index row are written, so this frozen entry cannot name the commit that those additions produce.

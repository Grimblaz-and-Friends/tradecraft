# D-394: The doctrine callout watches what loads before a cell fires, and the Release bullet is corrected rather than the tool widened

**Status:** Accepted 2026-09-05 (PR #394)

## Context

Three issues against one mechanism, `tools/doctrine_callout.py`, worked as one change because they share one function and one always-on sentence.

The callout exists because `CODEOWNERS` cannot perform the owner's merge-time read: it fires by requesting a review, and GitHub never requests one from a pull request's own author, which today every PR here has [D-81]. It is therefore the only thing putting a doctrine diff in front of him before he merges.

[#277](https://github.com/Grimblaz-and-Friends/tradecraft/issues/277): a cell's `name` plus `description` loads in every session whether or not the cell fires, and an edit to it fired nothing. Three incidents preceded the filing — [D-107] and [D-230] each rewrote the terminal stage's test and each left `adversarial-review`'s description asserting the retired one, falsified twice and merged twice with lint green; PR #269 repaired that string and, in doing so, edited an always-on surface with no flag.

[#293](https://github.com/Grimblaz-and-Friends/tradecraft/issues/293): `gh pr diff --name-only` reports a rename by its destination alone, so a doctrine file renamed *out* of the doctrine matched neither the exact set nor the prefix set. The exact half had `tools/lint.py` as a backstop; the prefix half had none, so a future repo-only cell renamed out with the roster regenerated in the same change left nothing red.

[#386](https://github.com/Grimblaz-and-Friends/tradecraft/issues/386): a shipped cell's **body** is in neither set either, and PR #381 merged two new binding rules into the largest cell body in the tree and bumped the plugin version with no flag raised. `AGENTS.md`'s Release bullet described a reach that covered the doctrine files, the charter and the repo-only cells, and asserted it as the guarantee — while the nine shipped cells' bodies, where the practice's rules actually live, went unwatched.

## Decision

**1. The flag widens to cell frontmatter, and to that alone.** Ruled by the owner on 2026-08-31 on #277, from three options put by PR #269's terminal ruling. `touched_frontmatter` compares the block `roster.frontmatter` returns at two revisions rather than matching a path, because **no path match can express *the description changed*** — and firing on the cell's path would fire on every body edit, which is the cheap fix #277 declined and the thing decision 2 rules against. Reusing `roster.frontmatter` is deliberate: it returns exactly the block that loads, so no rival definition of what a description is comes into existence.

**2. Shipped cell bodies are not flagged, and the Release bullet is corrected instead.** Ruled by the owner on 2026-09-05, on measurement rather than argument. Over the 40 most recently merged pull requests, the flag fires on **15** today, on **17** once frontmatter is in, and on **35** if bodies are. A flag on seven of every eight pull requests is one nobody reads, and the module's own comment already names that failure: *"a false callout trains the owner to ignore the true one."* `docs/values.md` rank 3, owner attention, is what decides it, against rank 1 for the claim the sentence was making. So the guarantee is brought down to the mechanism rather than the mechanism up to the guarantee — which is the honest direction when the wider guarantee is one nobody wants paid for.

**3. The charter is the one shipped cell whose body still fires, and every sentence says so.** `DOCTRINE_PATHS` watches it entire because `AGENTS.md` imports it, making its body always-on. It is excluded from the frontmatter arm for exactly the reason the repo-only cells are: the path arm already reports it, and a second report is a defect rather than coverage. **The first draft of the Release bullet denied this** — it said "a shipped cell's body is not flagged" while naming the charter two clauses earlier — so a test now fails if the carve-out is ever dropped.

**4. Rename sources come from a second, narrow lookup beside the diff read, not from replacing it.** `changed_paths`' docstring argues deliberately for `gh pr diff --name-only` over a local merge-base diff, and that argument is untouched. `renamed_from` reads `previous_filename` from the files endpoint, which is the one datum the primary read structurally cannot carry, and pagination is confined to that call.

**5. Both sides of the frontmatter comparison are named revisions, `--head` defaulting to the working tree.** CI passes no head and reads the checked-out merge commit exactly as `_always_on_delta` does, so nothing about CI changes. The parameter exists because **a working-tree head made the arm's own falsifier unrunnable**: sweeping a range of pull requests from one checkout compares every base against the same tree and reports changes belonging to other pull requests as though they belonged to this one. A criterion whose run cannot be performed is a wish.

**6. Line endings are normalised before the blocks are compared.** This tree stores LF in git and a text-mode write leaves CRLF on disk, which the doctrine names as expected rather than a defect. A raw compare of a blob against the working tree would differ on every cell on every run and flag every pull request — the false callout the mechanism exists to avoid, arriving through the guard added to prevent a miss.

**7. No base plus a changed shipped cell is a refusal, not a pass.** Answering the frontmatter question "no" by default is how a description edit merged unflagged three times. It exits non-zero, matching the module's standing rule that every failure is loud.

## Rejected

**Widening `DOCTRINE_PATHS` to shipped cell bodies.** The measured 35-of-40. #386 filed this as a live option and argued both sides; the owner declined it.

**Giving bodies a quieter surface** — named inside the callout comment, without the label or the "read before merging" framing. Rejected because the comment is what lands in notifications, so this spends the attention while appearing not to.

**Triggering on the version bump rather than the path.** Floated on #386, and `check_version_bump.py` already computes the shipped set. It flags the same 35, so it inherits decision 2's whole objection.

**Narrowing the repo-only cells to their frontmatter**, which would have made the reach one clean principle instead of a principle plus a carve-out. Rejected as out of scope and stated so in the affirmed brief: it shrinks the owner's merge-time read, which is a separate decision needing its own case. The reach is therefore *what loads before a cell fires, plus repo-only cells entire*, and the bullet says both halves rather than claiming the tidier rule.

**Calling the reach "the always-on surface" in the bullet.** `tools/figures.py` prices every roster entry on a runtime's surface into that total, and `roster.is_generated` exists precisely because a hand-written project skill can sit there — one that nothing here fires on. At this tree all 13 priced entries are cells, so the divergence is latent; the label would still have claimed a reach the tool does not implement, which is the defect being repaired. The longer enumeration is true.

## What this cost, recorded because it is evidence about the instrument

The pre-implementation artifact drew **two consecutive `would not` verdicts** and is settled by an owner ruling at the two-round cap rather than by any seat affirming it. Round 1 caught decision 3's contradiction; round 2 caught decision 5's unrunnable falsifier. Both were real, neither was reachable by reading the artifact alone, and the second bought a design change rather than a wording change — so the cap arrived with the rounds still paying, which is worth knowing the next time the cap is argued about.

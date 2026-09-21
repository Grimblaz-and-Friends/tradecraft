# D-701: Adopt change-proof with a guarded policy mirror

**Status:** Accepted 2026-09-21 (PR #701)

## Context

The organization-level change-proof check runs on this repository's pull requests, but the base branch at `8db7a36529180afa62b9ea145a25ab635876f315` has no `.github/change-proof.json`. The failure recorded on [#700](https://github.com/Grimblaz-and-Friends/tradecraft/issues/700) therefore concerns missing trusted configuration rather than the evidence a change produced. The owner ruled to adopt the gate here, and the [affirmed implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/700#issuecomment-5768842216) fixes the policy's content as the use rules already in force.

The entrance still reads `lib/use-rules.json` by default, as [`lib/work.py` at the base](https://github.com/Grimblaz-and-Friends/tradecraft/blob/8db7a36529180afa62b9ea145a25ab635876f315/lib/work.py#L859) demonstrates. Issue [#672](https://github.com/Grimblaz-and-Friends/tradecraft/issues/672) owns any decision about that default path. Replacing either policy copy with a pointer in this change would settle #672 incidentally, while leaving two unguarded copies would invite a later rules edit to change what one mechanism requires without changing the other.

## Decision

`.github/change-proof.json` is a literal JSON copy of the rules object in `lib/use-rules.json`. Neither file is designated as canonical, and the entrance's default path is unchanged.

`tools/tests/test_change_proof_policy.py` loads both files as JSON and asserts that their decoded objects are equal. Semantic equality is the invariant: whitespace and final-newline differences are irrelevant, while a changed schema version, rule, path, order or additional content fails the repository suite. The test stays under `tools/tests/` because it reads the repository-only `.github/` tree; placing it under shipped `lib/tests/` would cross the one-way wall.

PR #701 is expected to fail change-proof even when its implementation is sound. The gate reads trusted policy from the base tip, which cannot contain the policy until this pull request lands. The pull request therefore states that bootstrap condition in its proof and the owner merges on the connected reviewers' evidence, rather than bypassing review with a direct push.

## Rejected alternatives and consequences

Making either policy file point at the other, or changing the entrance default, was rejected because #672 owns that decision. Keeping two literal copies without a guard was rejected because review would then be the only drift detector. Carrying the rationale only in the pull request body was rejected because the session that later takes up #672 reads this decision log, not necessarily a merged pull request body. Adding a repository workflow was rejected because the organization rule already invokes the gate.

A future rules change must update both JSON objects in one passing change. This repository accepts that duplication until #672 deliberately supersedes it. The introducing red check is accepted only for this bootstrap condition; after the policy reaches the base branch, later pull requests are judged against that trusted copy.

## Evidence

The [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/700#issuecomment-5768942528), its [cold `would` verdict](https://github.com/Grimblaz-and-Friends/tradecraft/issues/700#issuecomment-5768998009), and the [holder's amended reading](https://github.com/Grimblaz-and-Friends/tradecraft/issues/700#issuecomment-5769022852) govern the implementation.

The policy and guard first stand together at `e5ebc262a3d10c7b51f9f0ed9e27e3328deeb70f`. `python -m pytest tools/tests/test_change_proof_policy.py -q` demonstrates equality there. The guard's opposite polarity was exercised by changing only the policy's parsed `schema_version`, observing that command fail, restoring the value and observing it pass. The repository floor is `git diff --check`, `python tools/lint.py`, and `python -m pytest tools/tests skills lib/tests -q -n auto --dist loadfile`; PR #701 carries the final-head results after this entry and its index row join the build.

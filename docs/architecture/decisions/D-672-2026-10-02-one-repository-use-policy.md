# D-672: One repository policy for entrance use rules

**Status:** Accepted by the owner 2026-10-02; number 672 is provisional until the implementing pull request exists.

## Context

[D-701](D-701-2026-09-21-change-proof-policy-mirror.md) retained two policy copies until issue [#672](https://github.com/Grimblaz-and-Friends/tradecraft/issues/672) decided the entrance default. The old selection is demonstrated by `lib/work.py` at `f80d0e93327102a3a3cfcba5668ae3f6f32c9e3b`; the mirror and its equality test are recorded by D-701. An adopter's rules belong to its repository, rather than to the installed practice.

The owner chose "One source" and [affirmed the brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/672#issuecomment-5961048690). The [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/672#issuecomment-5961284376) and [holder reading](https://github.com/Grimblaz-and-Friends/tradecraft/issues/672#issuecomment-5961297089) carry the implementation and its release slot.

## Decision

The entrance default is the holder repository's `.github/change-proof.json`, in tradecraft and adopters alike. An absent default refuses with that policy's resolved path. This supersedes D-701's two-copy arrangement: retire `lib/use-rules.json` at `f80d0e93327102a3a3cfcba5668ae3f6f32c9e3b` and its equality test, retaining the repository's policy without changing its rules.

Retain `--use-rules PATH` as an explicit replacement for that run, including setup before a committed default exists. Expand a home spelling before resolving a relative value under `--root`; retain an absolute value's location. The holder root, rather than the shell's working directory, is the anchor because a holder may invoke the entrance from another worktree or directory. Existing proof cleanliness and committed-source requirements still apply.

The work cell names the repository policy and documents the override beside the invocation. Its purpose, audience and success remain applicable. No rule reason moved or was dropped: this changes the source selection and adds the override explanation prescribed by the artifact.

## Rejected alternatives and consequences

A fallback to practice-shipped rules was rejected: a product must be classified by its own policy, and practice paths cannot stand in for product paths. Keeping a second copy with the equality guard was rejected because the one-source decision removes the duplication it guarded. Removing the override was rejected because setup may need an available file before the repository's default lands. Resolving a relative override from the shell was rejected because the same holder invocation would select different files after changing directory.

Keep landed decision entries as history. The exact retired references in D-679, D-691 and D-701 take `UNREPAIRABLE_AFTER_LANDING` in `tools/lint.py`, each with its own reason; repointing them would change what their sentences characterize. The shared proof examples are retained byte-for-byte, including their legacy source declaration. No gate or schema changes are part of this decision.

## Evidence

`lib/tests/test_work.py` carries `test_adopter_default_uses_its_product_policy_without_lib`, `test_missing_default_names_repository_policy_without_fallback`, `test_default_proof_names_and_hashes_committed_repository_policy`, `test_explicit_setup_override_replaces_absent_default`, `test_invalid_override_does_not_fall_back_to_valid_default` and `test_override_uses_holder_root_from_conflicting_working_directory`. The existing policy snapshot, dirty-policy and publication-race tests retain the committed-byte and cleanliness falsifiers. The build return on #672 carries results for the focused tests and repository floor; later consumer use remains holder-owned.

`.claude-plugin/plugin.json` takes the holder-assigned `0.175.0` slot. The decision number is provisional under the holder reading and will be renamed to the implementing pull request's number on the builder's first resumed turn.

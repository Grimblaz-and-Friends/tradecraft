# D-859 — Required governing records reach implementer prompts

**Purpose:** preserve the choice to carry holder calls through the entrance and test the connection between admission and prompt content. **Audience:** a future session changing implementer prompts, holder readings or stage gates. **Success:** it can reconsider the choice and its rejected alternatives from the affirmed record and pinned implementation evidence.

The owner affirmed [#799's implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/799#issuecomment-5982587902) on 2026-10-04. Its design record and the [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/799#issuecomment-5982790937) govern [pull request #859](https://github.com/Grimblaz-and-Friends/tradecraft/pull/859).

## Decision and rejected alternatives

Composed `build`, `floor` and `review-disposition` prompts carry every holder reading after the effective settlement in the current term, whatever its result. Complete bodies follow the settled artifact in record order. The readings govern where they differ from that artifact, and the newest governs where readings differ from each other; the affirmed brief remains binding over both. Keeping earlier calls preserves directions a later reading does not revisit. Carrying `no-amendment` bodies prevents a mislabelled result from hiding a call.

The owner chose the reading as the one vehicle in design turn 1, ruling A. A later direction to the builder on the settled artifact is another `holder-reading result=amended`, because both kinds of reading record the holder's calls without a new verdict. This rejected a new `holder-direction` marker and readings-only carriage that would leave later directions to a holder-written dispatch.

In turn 2, ruling B preserved a holder-written dispatch byte-for-byte and named the existing registered-tree branch protection in the work cell. The owner rejected appending the entrance's branch sentence to that dispatch and rejected leaving the wording unchanged: the existing branch-mismatch refusal answered the holder's by-hand branch check without changing dispatch transport. This choice concerns attached branch identity, not whether commits can advance its head.

In turn 3, ruling A chose the cause over fixing only the missing reading. The gate and prompt had been written separately with nothing checking that required evidence reached the builder. A governing-source contract test therefore holds every composed implementer prompt to the records its stage requires: the affirmed brief, the settled artifact where due, and the holder readings counted. This adds no admission rule or common gate/prompt framework.

The Steward's review changed the holder outcome for a term delivered in instalments: the holder still scopes each stage with its own dispatch. The composed prompt carries the whole artifact and reading history, and nothing in this change scopes those sources to an instalment. The exception preserves staged delivery without changing marker syntax or adding a marker.

## Pinned implementation evidence

The implementation evidence is pinned to build commit `31df7352b0a94c18f1c803e0fff59f4e10473c9c` rather than described from a moving tree:

- `lib/work.py` at `31df7352b0a94c18f1c803e0fff59f4e10473c9c`: `_artifact_phase` retains the applicable ordered reading sources, and `_stage_prompt` carries their complete bodies with the precedence instruction.
- `lib/tests/test_work.py` at `31df7352b0a94c18f1c803e0fff59f4e10473c9c`: `test_admitted_implementer_prompt_carries_its_governing_sources` constructs admission and carriage expectations from the same fixture collection, independently of the production selector. It covers `artifact`, `build`, `floor` and `review-disposition`, including the mechanical exemption. The final-effective-settlement, lawful-route and validated-claim tests demonstrate the reading boundary and order. `test_fresh_build_creates_and_reuses_a_branch_worktree_without_touching_holder` demonstrates byte-exact holder dispatch transport and the registered launch root; `test_later_dispatch_refuses_when_the_registered_tree_changes_branch` demonstrates refusal after switching or renaming that branch.
- `skills/work/SKILL.md` at `31df7352b0a94c18f1c803e0fff59f4e10473c9c`: the governing-record rule, instalment exception and documented branch protection.
- `skills/work/references/markers.md` at `31df7352b0a94c18f1c803e0fff59f4e10473c9c`: the widened `holder-reading` moment for later directions, with its form and lawful results retained.

The affirmed boundaries leave stage admission, settlement routes, mechanical carriage, explicit artifact and cold-seat prompts, branch binding, the change-proof gate and #811's review-thread work unchanged.

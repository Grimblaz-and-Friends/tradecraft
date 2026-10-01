# D-816 — Answer identified body findings and unidentified reviews individually

**Purpose:** preserve the reading of #809's affirmed body-disposition rule and the entrance/gate split. **Audience:** a future session changing review accounting, answer matching or reviewer publication. **Success:** that session keeps reviewer credit separate from answer completeness and can reuse the live-record cases without changing the proof contract.

Governed by [#809's affirmed brief and settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/809). The owner explicitly ruled that nitpicks count.

## Decision and meaning changes

The thread-only summaries now name individual body and whole-review answers as well. The protocol stays in the connected-reviewer reference: a body finding has no reply thread, so its answer is one authorized conversation comment linking its full identity to a source review; an unaccounted declaration gets a separate answer linking the unidentified review. The existing disposition words and inline formatting rule remain the terms read in D-775. Bare body openings make these new conversation answers directly checkable without widening stage-marker authority.

The identity-only thread exemption preserves one answer for a restated finding. Counts stay local to each submitted review: inline roots join through their review id, replies add no findings, and CodeRabbit's actionable declaration and each body section have separate scopes. This keeps surplus nitpick identities from hiding an outside-diff deficit. The unidentified classification remains after its answer, and identified findings beside it still need individual answers. Code examples and identity-free fix prompts earn no accounting credit. The shared cases in `skills/work/references/proof-fixtures/v1-review-body-dispositions.json` and `test_shared_live_record_cases` demonstrate the compatibility boundary; a vendor removing every recognizable identity and declaration remains outside the permitted signals.

This records the off-diff exception to #746's inline-placement reading, consistent with D-757's body-placement rationale: trusted `review_payload` keeps the real path and line and supplies the numeric attempt plus body ordinal identity. The finder generates no publication identity. `test_payload_body_identities_preserve_location_and_accounting` demonstrates clean, inline-only, body-only and mixed payloads, and preserves the final attempt marker.

The entrance checks missing body answers before proof or release, while reviewer-run credit continues to require its existing notice and shared-Actions provenance rules. `test_prior_head_body_obligation_precedes_proof_and_legacy_green_gate`, `test_body_identity_does_not_credit_an_unproved_actions_review`, and `test_explicit_release_handoff_names_unanswered_bodies_despite_green_gate` demonstrate those distinct outcomes. Explicit proof publication remains permitted with incomplete evidence; `test_body_diagnostics_use_unchanged_proof_contract_before_and_after_answer` demonstrates the unchanged schema and inline disposition shape.

Lower cells describe the answer obligations and point to the named connected-reviewer contract in prose; they do not add a reverse dependency into adversarial review, whose existing dependency on engagement and work would create a pointer cycle. The owning reference carries the examples and reasons.

## Shared-rule repair

The holder's repair dispatch records the Steward's ruling with [change-proof #38](https://github.com/Grimblaz-and-Friends/change-proof/issues/38): CodeRabbit declarations use the whole counted-comments title shapes, with a leading symbol run stripped, while other non-lab reviewers' section titles start with `Findings`. This narrows the earlier declaration reading so a walkthrough's security heading creates no obligation. `test_coderabbit_requires_a_whole_structural_counted_comments_title` and the `757-walkthrough-*` shared cases demonstrate the boundary. The existing CodeRabbit `section-without-count-missing-entry` case now retains its explicit identity obligation without treating its `Findings` heading as a declaration.

The same ruling gives section extent and identity ownership one rule across title shapes, limits inline accounting to empty or explicitly zero counted-section content, and keeps inline code spans within paragraphs. The regressions `test_next_summary_ends_bold_section_before_its_identity_can_mask_a_deficit`, `test_counted_prose_section_cannot_spend_an_inline_root_as_its_body_identity` and `test_inline_code_paragraph_boundary_preserves_live_declarations_and_identities` show the repaired surfaces. `test_mixed_case_logins_preserve_authorized_answers_and_exemptions` supplies the login-case regression against the already normalized work configuration. Reviewer identity emission, proof fields, plugin version and pins retain their earlier choices; catch-up and the executable floor remain the holder's later stages.

## Split and adoption

The entrance half ships first. The sibling change-proof gate reads the same GitHub surfaces and the shared cases independently, with no additional proof fields or entrance import. Its implementation and the reviewer pin bumps remain the Steward's follow-ons. No workflow pin, reviewer trigger, vendor configuration, charter sentence or merged-pull-request obligation changes here. The standing page's merge order assigns this change plugin 0.170.0; the holder supplies its #751 catch-up before release.

The consumer experience session and any later review remain holder-owned stages. This decision entry is a build record, not their result.

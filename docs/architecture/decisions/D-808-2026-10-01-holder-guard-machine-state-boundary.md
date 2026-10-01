# D-808 — Protect the holder's machine-state boundaries by subject

**Purpose:** preserve why the holder guard protects specific machine-state subjects rather than their enclosing directory. **Audience:** a future session changing holder access to machine state, dispatch evidence or shell refusal messages. **Success:** that session can revise the boundary without accidentally opening the machine's vendor choice, editing dispatch evidence or restoring the bundle-handling workaround.

Recorded in [PR #808](https://github.com/Grimblaz-and-Friends/tradecraft/pull/808), implementing [#743](https://github.com/Grimblaz-and-Friends/tradecraft/issues/743). The [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/743#issuecomment-5922463039) supplies the decisions and rejected alternatives below. This change's release version is `0.164.0`.

## Context

The affirmed brief records holders on Organizations of Verra and Daemon changes being refused shell reads of dispatch bundles and told they had tried to edit the registry. They worked around the refusal by copying records through a model, although the entrance later checks those records. Treating all of the machine-local directory as the registry also prevented the Steward from writing the model-rulings file directly.

The registry identifies registered builder trees; its directory also holds unrelated machine state. The decision draws the boundary around the subjects a holder must not change, rather than making their common location an authority boundary.

## Decision

Shell protection applies to the machine-local registry file and `implementer-vendor` when the command cannot be proved read-only. Naming includes the file, a containing directory, a matching wildcard path or an attached redirection target, resolved in each non-directory-change segment's working directory, because deleting, moving or overwriting through those spellings is still a write to the file. Edit, Write and NotebookEdit remain refused on those files and throughout `dispatches/`. The model-rulings file and ordinary siblings are open, subject to the existing registered-tree boundary. Row 1 of the affirmed brief establishes that split; the original build and its demonstrators are pinned below.

**Keep the vendor-choice file protected.** The Steward identified that opening it would let a holder move every change's fresh builds to another vendor with one write. Row 1 also records that a resumed Codex builder encounters a handover when the switch reads Claude. The owner remains the only role that flips the switch; narrowing the folder boundary must not silently transfer that authority.

**Keep dispatch bundles closed to the edit tools and open to the shell.** The Steward pointed to the work cell's bundle-as-source-of-truth rule and recommended retaining edit protection; the owner affirmed that recommendation. An Edit that fixes a return before posting can change the evidence from which markers are produced. Reads cost nothing: file-reading tools already pass without guard checks. Shell access lets holders hash, script over, post and launch from bundles without copying records through a model. The owner explicitly accepted that shell writes to bundles remain possible; this is a boundary choice, not bundle integrity or complete write confinement.

**Explain a shell refusal as missing read-only proof.** Row 2 requires the message to identify the protected subject or registered-tree boundary and name missing Git helper flags when those alone repair the command. It does not infer an attempted edit from an unproved command. The finite recognizer and builder-tree decisions remain the terms of the brief.

## Rejected alternatives

- **Keep the original folder boundary.** It refused ordinary bundle handling and rulings writes because they shared the registry's directory, producing the product-work workaround recorded in the brief.
- **Open the dispatch store fully.** This was the owner's alternative to the Steward's recommendation. The owner affirmed the recommendation as written, retaining protection against edit tools changing a return before it is posted.
- **Widen the read-only allowlist.** The brief's Not this explicitly excludes it. Correcting which machine-state subjects invoke protection answers the bundle refusal while preserving the recognizer used for protected files and registered builder trees.

## Evidence and limits

The following original-build evidence is pinned to commit `ee89f9c81247fef1835d72789d57748c575eb42d`; it predates the connected-review repair of the additional shell spellings recorded above:

- `lib/holder_tree_guard.py` at `ee89f9c81247fef1835d72789d57748c575eb42d`: `_machine_boundaries`, `_protected_file_subject`, `_shell_protected_file` and `decision` demonstrate the subject boundary; `_read_only_git_missing_guards` and `_unproved_shell_reason` demonstrate the refusal explanations.
- `lib/tests/test_holder_tree_guard.py` at `ee89f9c81247fef1835d72789d57748c575eb42d`: `test_machine_file_boundaries` and `test_machine_protected_shell_files` cover protected and open subjects; `test_dispatch_shell_handling_is_open` covers bundle handling and the accepted shell-write opening. `test_open_machine_paths_do_not_open_builder_tree` preserves the registered-tree boundary. `test_helper_hint_alone_repairs_the_command` and `test_independent_refusal_does_not_recommend_helper_flags` demonstrate the explanation's repair condition.
- `skills/work/references/markers.md` at `ee89f9c81247fef1835d72789d57748c575eb42d` supplies the bundle-as-source-of-truth rule the Steward cited. `skills/engagement/references/the-stretch.md` at `ee89f9c81247fef1835d72789d57748c575eb42d` states the holder-guard boundary beside its existing explanation.

The brief excludes changes to the read-only allowlist, builder-tree decisions apart from messages, vendor-selection authority, the relative hook path, and bundle tamper evidence or stored return digests. Literal-path detection retains its existing limits.

The [directory-change finding](https://github.com/Grimblaz-and-Friends/tradecraft/pull/808#discussion_r4151155914), [directory and pattern finding](https://github.com/Grimblaz-and-Friends/tradecraft/pull/808#discussion_r4151156944), and [changed-directory and redirection finding](https://github.com/Grimblaz-and-Friends/tradecraft/pull/808#discussion_r4151156950) supply the repair's failure cases. In the repair tree shipping this entry, `test_shell_containing_directory_cannot_remove_protected_files`, `test_shell_patterns_cannot_change_protected_files`, `test_shell_changed_directory_resolves_protected_files` and `test_shell_attached_redirection_resolves_protected_file` demonstrate their refusals; `test_shell_machine_path_negative_controls_remain_open` demonstrates the retained openings, and `test_refused_registry_deletion_keeps_active_roots` demonstrates retained registration after refusal.

Re-run the build's focused evidence with `python -m pytest lib/tests/test_holder_tree_guard.py -q` against the pinned build commit. Validate this release record and its index with `python tools/lint.py`, and the repair tree with `python -m pytest tools/tests skills lib/tests -q -n auto --dist loadfile`. These are reproducible checks, not claims that a later holder-owned stage has run.

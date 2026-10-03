# D-835 — Native staffing is judged from the record

**Purpose:** preserve why native judging seats use the entrance's producer rule rather than a holder-supplied identity or unchecked staffing value. **Audience:** a future session changing native recording, staffing validation or proof declarations. **Success:** that session can recover the owner’s choice, its rejected alternatives and its compatibility boundary without repeating the design.

Records [#830's affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/830#issuecomment-5968455595), its design ruling on 2026-10-03, and the [holder reading](https://github.com/Grimblaz-and-Friends/tradecraft/issues/830#issuecomment-5968566750).

## Context and reason

The [filing](https://github.com/Grimblaz-and-Friends/tradecraft/issues/830) records Windgust-Questbook #294's stalled use: its consumer needed the desktop app's built-in browser, so the run used the native agent tool bracketed by the recorder. The entrance rejected its qualified marker because the native run supplied no staffing at the level validation read. The old native write and entrance read are demonstrated by `finish_native` in `lib/dispatch_record.py` at `b29f17594f715f237b25735b9abca0d1afd07ff7` and `_bundle_marker_error` in `lib/work.py` at `b29f17594f715f237b25735b9abca0d1afd07ff7`.

The owner ruled “1, judged from the record.” The holder should not retype a fact the retained records already hold, and the native and launcher routes should not choose different producers for one seat. The launcher's revision and lineage rules protect an earlier use from a later rebuild; copying a usage value proves neither vendor nor independence.

## Decision

For a native use or cold verdict, the entrance compares the actual seat vendor with the producer selected by the launcher's own rule. Use selects the implementer at the marker's head through `RESUME_SOURCE_STAGES["build"]`; cold judgment selects the artifact author with `_producer_vendor(state, frozenset({"artifact"}))`, without a revision or source root. A differing vendor is qualified; a matching vendor is degraded; an unproved producer invalidates the marker with its diagnostic. Validation and the proof declaration share that judgment rather than reading native staffing from usage.

Native `begin` records an optional same-vendor reason in the immutable request. An accepted degraded marker repeats that reason. Native `finish` records the vendor that actually ran a use or cold seat when a runtime launched, and native usage staffing is `unknown`: recording facts does not certify staffing.

Historical native bundles remain intact. Where no actual vendor was recorded, the requested vendor supplies the seat identity because the native route runs what it was asked to run. Differing-vendor evidence can qualify without a rerun; same-vendor evidence lacking a recorded reason cannot be accepted as degraded. The holder reading establishes the instance's producer as a Codex floor whose revision exactly matches the use head, passing over later descendant repairs.

## Rejected alternatives and boundaries

The design offered two alternatives to the chosen entrance judgment. Computing staffing in the recorder from a holder-typed producer vendor was rejected because it would require the holder to re-enter recorded identity and create a separate source for the comparison. Falling back to the usage record's hard-coded value was rejected because an unchecked qualified value could conceal a same-vendor seat instead of establishing independence.

The decision leaves launcher records and acceptance, marker forms, the cross-vendor rule and the change-proof gate unchanged. It adds no native producer route for artifact or build, no holder-typed producer input, and no rerun of Windgust-Questbook #294's use.

## Evidence

The shared judgment is `_native_staffing` and its two consumers in `lib/work.py` at `fcee017ba6bcf609b3ad70a19342b5fcdf3bbc98`. The request and completion writes are in `lib/dispatch_record.py` at `fcee017ba6bcf609b3ad70a19342b5fcdf3bbc98`; the holder's native instructions are in `skills/engagement/references/dispatch-records.md` at `fcee017ba6bcf609b3ad70a19342b5fcdf3bbc98`.

`test_native_cross_vendor_marker_and_declaration_share_record_judgment`, `test_native_same_vendor_acceptance_needs_recorded_matching_reason` and `test_historical_native_instance_uses_exact_floor_and_last_pre_marker_request` in `lib/tests/test_work.py` at `fcee017ba6bcf609b3ad70a19342b5fcdf3bbc98` demonstrate the shared judgment, reason requirement and historical selection. Recorder writes are covered by `test_native_records_facts_without_certifying_staffing` in `lib/tests/test_dispatch_record.py` at `fcee017ba6bcf609b3ad70a19342b5fcdf3bbc98`. This entry claims no later consumer-use or review result.

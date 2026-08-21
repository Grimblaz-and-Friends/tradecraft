# The decision log

One file per decision, named `D-<N>-YYYY-MM-DD-<slug>.md` where `<N>` is the pull request that landed it. An entry is written in the PR that lands a choice a future session would otherwise re-derive or unknowingly undo, and is frozen on landing.

**Decisions inform, never bind.** An entry records what was known and rejected when the choice was made; it is superseded by being read, not obeyed, and is never a citation against change. A rule or skill line may cite its entry as `[D-N]`; follow the citation before changing what it governs, then supersede knowingly. Reversal is by a new entry, never by editing an old one.

Entries D-53 through D-69 were written under the pre-reset statute's fixed skeleton and are part of the frozen archive ([D-74](D-74-2026-08-19-constitutional-reset.md)); decisions before the log existed are in the [frozen ADRs](../adr/README.md).

| Entry | Decision |
| --- | --- |
| [D-53](D-53-2026-08-18-log-and-statute.md) | Split the constitution into a decision log and a statute; freeze the nine ADRs |
| [D-59](D-59-2026-08-18-work-prose.md) | `artifact` gains `work-prose` in the ledger vocabulary |
| [D-61](D-61-2026-08-18-decision-surfacing-and-the-attended-seam.md) | Decisions put to the owner carry argued options; the opening seam's question becomes attended-only |
| [D-69](D-69-2026-08-18-trial-instrument-and-exception.md) | The trial road's falsifier and evidence stop being ledger-only |
| [D-74](D-74-2026-08-19-constitutional-reset.md) | **The constitutional reset**: three content homes, purpose-anchored review, records as exhaust; the statute and its machinery become a frozen archive |
| [D-77](D-77-2026-08-19-owner-approval-admission-path.md) | The admission road gains a second path: an agent-proposed rule is admitted by an incident from real work, or by the owner's specific approval of that rule |
| [D-78](D-78-2026-08-19-carry-the-reasons.md) | Four reasons restored to the rules they govern; migrations must carry reasons or name the drop; review dispatches carry the charter verbatim |
| [D-80](D-80-2026-08-19-spikes.md) | Spikes: test a premise before you assert it — one named premise, a throwaway that commits nothing, reported whether it held, fell, or was abandoned |
| [D-81](D-81-2026-08-19-doctrine-callout.md) | The doctrine callout is a CI label and comment, not `CODEOWNERS`, which cannot request a review from the PR's own author |
| [D-90](D-90-2026-08-20-dispatch-contract.md) | Every dispatch is a shared block with nothing before it, carrying the assignment — byte-identical across recipients dispatched against the same diff base — and every predecessor stage's output whole, both verbatim or by link, never the dispatcher's paraphrase; then a labeled additive note; last the recipient's own identity, output format, skill-worded lens brief, and working location. The terminal stage's docket is set by rule, not by the dispatcher |
| [D-96](D-96-2026-08-20-post-fix-terminus.md) | The post-fix cycle ends when a look sustains no high it will fix whose remedy changes the artifact; a finding whose remedy is not a change to the artifact is recorded and routed, never buying a further round; the mandatory floor names its exemption to match — every fix batch but the one a terminating ruling orders. Until then the cycle continues without asking, so round one's ruling names the cycle budget — and exceeding it puts the review to the owner in that cycle's ruling rather than ending it |
| [D-99](D-99-2026-08-21-dispatch-prompt-caching.md) | The dispatch prompt is not cacheable at any size: the harness's post-system breakpoint sits at the end of the whole request, so one differing byte collapses the hit — cross-seat cache sharing is structurally impossible and the cost argument for the shared block is dead for panels |

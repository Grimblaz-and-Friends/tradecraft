# The decision log

One file per constitutional decision, named `D-<N>-YYYY-MM-DD-<slug>.md` where `<N>` is the pull request that landed it. An entry freezes what was known when the decision was made; the rules it put in force live in the [statute](../constitution.md), and each statute rule cites the entry or frozen ADR line that last shaped it.

An entry is accepted when it lands on `main`, and is then immutable except for status-line supersession pointers. Reversal is by superseding entry, never by revert. The procedure is the statute's §12.

| Entry | Decision | Displaces | Superseded by |
| --- | --- | --- | --- |
| [D-53](D-53-2026-08-18-log-and-statute.md) | Split the constitution into a decision log and a statute; freeze the nine ADRs as a historical preamble | ADR-004:28, ADR-006:61, ADR-006:72, ADR-006:92, ADR-008:17 | — |
| [D-59](D-59-2026-08-18-work-prose.md) | `artifact` gains `work-prose`: one value for every prose surface the statute mandates outside the tree | ADR-006:72 | — |
| [D-61](D-61-2026-08-18-decision-surfacing-and-the-attended-seam.md) | A decision put to the owner carries argued options with pros and cons plus the recommendation; the opening seam's batched question is attended-only | ADR-005:23, ADR-006:56, ADR-006:61, ADR-006:63 | — |
| [D-72](D-72-2026-08-19-citable-statute-and-stranded-reasons.md) | The statute gains the reader-role split and a citation form for its own rules; five reasons resident only in the frozen preamble land inline | — | — |

Decisions taken before the split are in the [frozen ADRs](../adr/README.md), which remain the record for every rule whose citation names them.

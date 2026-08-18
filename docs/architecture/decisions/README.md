# The decision log

One file per constitutional decision, named `D-<N>-YYYY-MM-DD-<slug>.md` where `<N>` is the pull request that landed it. An entry freezes what was known when the decision was made; the rules it put in force live in the [statute](../constitution.md), and each statute rule cites the entry or frozen ADR line that last shaped it.

An entry is accepted when it lands on `main`, and is then immutable except for status-line supersession pointers. Reversal is by superseding entry, never by revert. The procedure is the statute's §12.

| Entry | Decision | Displaces |
| --- | --- | --- |
| [D-53](D-53-2026-08-18-log-and-statute.md) | Split the constitution into a decision log and a statute; freeze the nine ADRs as a historical preamble | ADR-004:28, ADR-006:61, ADR-006:72, ADR-006:92, ADR-008:17 |

Decisions taken before the split are in the [frozen ADRs](../adr/README.md), which remain the record for every rule whose citation names them.

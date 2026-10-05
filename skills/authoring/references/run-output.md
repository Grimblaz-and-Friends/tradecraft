# Recording run output

**Loaded when** recording or requesting raw run evidence, or using its summary to judge or reproduce a result.

Raw run output is never committed, attached, uploaded, inlined as a dump or copied into a dispatch bundle. Record its summary in the repository's existing run-report location, or in the pull request when there is none; create no evidence store for the discarded files. The summary is the whole retained record, so evidence does not swell the change or move the dump elsewhere.

Write an authored account of the run's conclusions and limitations, with one entry for each raw file produced for the change:

| Field | Record |
|---|---|
| `file` | The raw file's identity. |
| `revision` | The tree that produced it, rather than the later commit containing the report. |
| `sha256` | SHA-256 of the exact file bytes, measured before discarding it. |
| `size_bytes` | The exact byte length, measured before discarding it. |
| `command` | The command that reproduces it at that revision. |

Reproducing instructions include the required working directory, arguments and environment or setup prerequisites when they affect the run. A discarded script or temporary directory is not a reproducer: the summary must let another session run without the original. These metadata are observations of that run; derived figures still take this cell's command-and-tree rule in `../references/frozen-documents.md`.

Builders return those entries and discard their ignored or temporary raw copies after recording them. Holders request, read and retain the summaries; judging seats use them to judge results and check a disputed figure by re-running its command at its producing revision and comparing the hash and length. A nondeterministic rerun may disagree with the original hash, and no retained original remains to consult; record that limitation rather than keep a copy.

Dispatch requests, native runtime logs, source returns and usage retention keep their existing contract. This standard introduces no dispatch retention or pruning mechanism.

# D-1044 — Tradecraft's suite runs the required gate, copied at a named commit, over the proofs its entrance composes

**Purpose:** record why #1035's tradecraft half holds a byte copy of change-proof's gate script and runs it over proofs the entrance composes in the test run, why the entrance now declares the markers a proof may name as a source, and the calls made inside the brief's rows. **Audience:** a future session changing what the entrance's proof names, refreshing the copy, or changing how either repository reads a builder's use report. **Success:** that reader can recover what was chosen over what without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/1035#issuecomment-7182059376), amended once, governs; it is shared with change-proof #58, which carried rows 1 and 2 and landed in change-proof #59. Its plan for this half was [settled on the would route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/1035#issuecomment-7183098184). The lane is ordinary / connected, and no panel was bought. This record supersedes none.

## The fault

On 2026-11-25 three tradecraft pull requests on the builder route (#1029, #1023, #1030) failed the required gate on one line, `missing: an authorized valid public use source: marker is invalid or unauthorized`. #1011 had made the builder's use report the proof's use source on that route, and the gate read only a `use` marker. The entrance and the gate are two implementations of one proof contract, and nothing ran one against the other before a tradecraft change merged: the first test of what #1011 composed was a real pull request at the real gate.

## What was chosen over what

- **A byte copy of the gate's script held in tradecraft, over reading change-proof's `main` as the check runs** (the owner's ruling "Include the check", and the Steward's review of row 3). A live read would go red from a failed fetch or an unrelated gate merge, a builder cannot rerun a job and would answer with a new commit, and a floor at one commit would stop being repeatable.
- **The copy under `tools/gate/`, over a copy under `lib/tests/fixtures/` with a blob-id exemption from the one-way wall.** The check is the lab's own and a product repository is unchanged by it, so 190 KB of another repository's script does not ship to every adopter; under `tools/` its `.github/` strings need no wall exemption.
- **One stand-in GitHub that both readers read, over building the entrance's state by hand and translating it into the gate's endpoints.** A translation is a third model of GitHub that can drift from both, which is the fault itself. Each case serves its records and a real Git history; the entrance runs `run proof`'s own stage (`_execute_proof`), which snapshots the committed policy, collects them and publishes, the stand-in accepts the proof comment it posts, and the gate's `run()` reads the same records. A read the stand-in does not serve fails the case.
- **A declaration of the markers a proof may name as a source (`PROOF_SOURCE_MARKERS`), held by a refusal in `compose_proof`, over a test that greps `compose_proof` for the markers it names.** Row 3's fourth check has to fail on its own when the entrance learns a new source; a list the composition is held to is the one thing a test can read and the code cannot outgrow.
- **A new shared fixture file, over adding cases to `v1-valid.json` or `v1-negative-cases.json`.** change-proof pins byte copies of those files, and a new file leaves the pins true.
- **The comparison with the gate at `9664769` as a command the builder ran, over a committed second copy.** A second 180 KB copy would prove one line once.

## Calls made inside the rows

- **The suite stands in for two things a proof does not name:** the cold reader's `clean`, which is a launched seat's bundle, and reach, read from the holder's launch turns. Everything a proof names is collected from the stand-in.
- **The relay case's `use` and `floor` markers are posted with no dispatch bundle behind them,** so its proof carries the entrance's `invalid-marker-claim` diagnostics and two unverifiable declarations; the gate reads neither, and the case passes on the public records it does read.
- **The refusal leaves a source the state holds no comment for to the gate,** such as a brief in the issue body, or a hand-built state whose comments carry no ids, because the gate refuses a missing record by the record it finds and every existing test passes unchanged.
- **The substrate lint passes over the copy only at its recorded bytes.** Its rules are for code this repository writes; an edited copy is judged like any file here.
- **The shared fixture's counting case is the entrance's own `check_report_body` output,** pinned by a test in `lib/tests/test_proof_sources.py`, so the case the gate is tested on is the report this entrance posts.

The tests are in `tools/tests/test_gate_agreement.py`, `lib/tests/test_proof_sources.py` and `tools/tests/test_substrate_lint.py`.

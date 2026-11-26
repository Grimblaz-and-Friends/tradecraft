# The copied gate

**Purpose:** say what this folder holds, what a red from the test that uses it means, and what a session may do about one. **Audience:** a tradecraft session whose change turns `tools/tests/test_gate_agreement.py` red, and its holder. **Success:** a reader of this page and the failing test's message can tell a defect to repair from a gate change owed, and never greens the test by editing a case or the copy.

`check.py` is change-proof's `proof/check.py`, byte for byte, at the commit `source.json` names, with its byte count and SHA-256. It is another repository's script, held here so tradecraft's own floor can run the required gate's reading over what tradecraft's entrance composes, with nothing fetched as the test runs. A copy, not a read of change-proof's `main`, keeps a result at a tradecraft commit the same forever: a fetch can fail, an unrelated gate merge can move it, and a builder that cannot rerun a job would answer either with a new commit.

The copy's own comments cite `README.md`, as in `README.md, "Evidence contract"`: that is [change-proof's README](https://github.com/Grimblaz-and-Friends/change-proof/blob/main/README.md), beside the script in its own repository, not this page. The copy is never edited, so its citations stay as change-proof wrote them.

## What the test does

`test_gate_agreement.py` stands up one in-process GitHub over a real Git history for each stand-in change its `CASES` names: the builder route with a use report at the head, the builder route with a use report at an earlier commit, the relay route with a `use` marker, the mechanical lane, and a change whose paths buy no use. The entrance collects that GitHub and publishes its proof there through its own publish step, and the copied gate reads the same GitHub. Each case must print `change-proof: PASS`, and each case whose paths buy use must print its use line. The same file also checks the copy's bytes against `source.json`, runs the shared use-report cases in `skills/work/references/proof-fixtures/v1-builder-use-report.json` through the copy, checks that the marker reference's `check-report` section names every report attribute the copy reads, since a holder learns from that section why the gate refused a report, fails unless every case ran and passed, and fails, naming it, when `lib/work.py`'s `PROOF_SOURCE_MARKERS` lets the entrance name a use or floor source by a marker no case's proof named.

## What a red means

A red on a case means one thing: the entrance under test composes a proof the copied gate refuses. The failure message quotes every `missing:` line the gate printed.

- **Where the change did not mean to alter what a proof names,** it is a defect in the change. The builder repairs it in the entrance.
- **Where the change meant to alter what a proof names,** the gate must change first, in change-proof. The builder does not repair it here; it returns it to its holder as a gate change owed, and the holder tells the Steward.

A red on the copy's integrity means its bytes are not the ones `source.json` records. A red on coverage means a marker was added to `PROOF_SOURCE_MARKERS` with no case whose proof names it; add the case.

## What no session does

- **Never edit a case, its expected lines, or the copy to make the test pass.** Each is the agreement being tested, so editing it hides the disagreement it found.
- **Never skip or deselect a case.** A closing test fails unless every case ran and passed in that session.

## Refreshing the copy

A change that needs a newer gate refreshes the copy in its own diff: fetch `proof/check.py` by GET at a commit already on change-proof's `main`, never from a branch or a pull request's head, and record that commit, the byte count and the SHA-256 in `source.json`. Its holder confirms the named commit is `main`'s tip or an ancestor of it, with `gh api --method GET repos/Grimblaz-and-Friends/change-proof/compare/COMMIT...main`, and that the bytes at that commit match the recorded digest.

## The substrate lint

`tools/substrate_lint.py`'s Python-file guards pass over the copy only while its bytes match `source.json`, since their rules are for code this repository writes; an edited copy is judged like any file here. Its whole-file guards read the copy as they read every file.

**Decision in force:** [D-1044](../../docs/architecture/decisions/D-1044-2026-11-26-the-suite-runs-the-copied-gate-over-composed-proofs.md), whose calls include this one.

## Decisions in force

[D-1044](../../docs/architecture/decisions/D-1044-2026-11-26-the-suite-runs-the-copied-gate-over-composed-proofs.md), the suite running the required gate, copied at a named commit, over the proofs the entrance composes: the copy, its place under `tools/`, the stand-in both readers read, and the lint's pass over the copy.

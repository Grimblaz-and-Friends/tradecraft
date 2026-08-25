# D-186: Windows text-mode defaults, decided once — an ASCII rule chosen for its guard, and a byte-identity rule with none

**Status:** Accepted 2026-08-25 (PR #186)

## Context

Python's text mode on Windows does two silent things whichever way the obvious call is written: it encodes `stdout` and `stderr` to the platform's locale codepage — cp1252, *including when the destination is a pipe* — and it translates `\n` to `\r\n` on writes. A pipe is what a CI log, an agent harness and a captured command all are, so the encoding half fires precisely where the output is machine-read.

Three issues had accumulated against the pair. [#147](https://github.com/Grimblaz-and-Friends/tradecraft/issues/147) was the encoding half, filed after the fix had been applied per-script three times: `skills/authoring/scripts/figures.py` crashed printing an arrow and was fixed on stdout, the same script's stderr was found unreconfigured afterwards by a review's defense seat, and `hooks/emit_charter.py` carried a third, separate hand-rolled reconfiguration that #147 did not count. [#162](https://github.com/Grimblaz-and-Friends/tradecraft/issues/162) and [#163](https://github.com/Grimblaz-and-Friends/tradecraft/issues/163) were the newline half filed twice from different ends — one from a session that spent four steps reaching a wrong recorded cause, one from a mutation harness whose CRLF rewrite made `git diff --numstat` report zero content change.

They were worked as one change because they share a substrate default and because #162's own text invited it. The decision below is three rulings, not one.

## Decision

**1. The encoding half is a rule about characters, and it was chosen for its guard rather than for its cost.** Machine-read output stays ASCII: no Python file in the repository states a non-ASCII character in a string constant that is not a docstring. Docstrings and comments are exempt because neither reaches a stream, so the house prose style is untouched everywhere it is actually read as prose.

The rejected option was the obvious one — a shared helper in `lib/`, which every script's `main()` calls, collapsing the three ad-hoc sites. It loses on **guardability**, and that is the whole reason this class survived three instance-patches: *"the helper was called on this entry path"* can only be checked approximately, and that approximation is not hypothetical here — it is exactly how `figures.py` had its stdout fixed and its stderr found unreconfigured afterwards. *"These bytes are ASCII"* is exact. A class patched a site at a time is closed by the guard that can see the next site, not by a fourth patch.

Two consequences worth recording. `lib/` is **not** created, so the zone question of what a root importable by both zones would mean defers at no cost — it remains a declared root that `tools/lint.py` already treats as a non-cell whose dependencies point down, holding no file. And `PYTHONIOENCODING` / `PYTHONUTF8` in CI was rejected as **measured-insufficient** rather than merely weaker: both fix the bytes, and neither reaches a consumer running a shipped script from a plugin cache or a session running one locally.

**2. The newline half is prose, in the same cell.** A file that will later be compared, restored or measured is written and read as bytes, with byte-identity asserted on restore. The operative failure is not encoding at all: a text-mode write turns LF into CRLF, version control reports the tree clean against an LF blob, and a validator asked about the same content can answer differently — so a harness can measure a tree its own commit does not contain.

Its warrant is narrower than #163 claimed, and the entry says so rather than inheriting the filing's framing. `claude plugin validate` does flip on line endings, confirmed on this change's tree, but only in **conjunction** with an unquoted `: ` inside a frontmatter value:

```
description: Not a cell: it decides nothing.     LF rc=0    CRLF rc=1
description: A simple description, no colon      LF rc=0    CRLF rc=0
description: "Not a cell: it decides nothing."   LF rc=0    CRLF rc=0
```

Across all eight shipped `SKILL.md` frontmatters there are **zero** such values. The rule is therefore preventive against a mutation seat introducing a colon into a description — which is what mutation testing does to prose — and not a response to a firing defect.

**3. Nothing guards the newline half, and the decline is the recorded part.** The surface is scratchpad scripts a session writes, runs once and discards; the repository owns no file-writing Python outside its tests, so no guard aimed at repo scripts can reach it. The only candidate is a `PostToolUse` hook matched on Bash, and the hooks documentation warns such a hook must not modify files — so it could report but not fix.

This is consciously against [D-137](https://github.com/Grimblaz-and-Friends/tradecraft/issues/137)'s thesis that a rule with no mechanism does not bind. The price of the mechanism is a hook firing on every Bash call to police a harm measured at one incident and four steps; the price of the decline is that the rule rests on prose. The second was judged cheaper, and it is recorded here so a later session finds a weighed decline rather than an omission.

**4. The recorded fact is separate from the rule, and lives on the always-on surface.** `AGENTS.md` states that CRLF on disk here is expected, that `.gitattributes` normalises it on the way in, and that the committed bytes are unaffected. This is not the rule restated: the rule stops harnesses from lying, and the fact stops sessions from investigating — the actual cost of the 2026-08-24 incident, which was budget spent on a false lead plus a wrong cause recorded as settled. It sits in `AGENTS.md` rather than in a cell or in this entry because the moment it must be found is mid-task, when a session notices CRLF and has no reason to open the decision log.

**A criterion deliberately left without a mechanism.** The artifact's criterion 3 — a seat measuring a tree gets the verdict the committed bytes would give — is discharged by ruling 2's prose and by nothing else. A test failing on CRLF in the working tree was considered and rejected as self-contradictory: it would make CRLF a red suite at the same moment ruling 4 tells a session it is harmless, which is two answers to one question.

## What the change's own work turned up

- **The guard produced 44 findings on the pre-change tree**, across six files, matching an independent AST census run before the check existed.
- **The escape form cannot evade it.** One rewritten message was written as the six-character `\u2014` rather than the character — invisible to a search for the character, reaching the stream as the character regardless. The check reads decoded values and caught it.
- **The check would have crashed the lint.** `rglob("*.py")` matches *directories* named `*.py`, and an existing delivery test creates exactly that shape, taking every other check down with it. Found by that test, fixed, and pinned by its own regression.
- **Three unprompted instances during the spikes.** Two throwaway probe scripts died — a `charmap` decode error reading a subprocess's output, and an encode error printing an arrow — neither of them testing for it. That is #162's recurrence claim observed rather than argued.

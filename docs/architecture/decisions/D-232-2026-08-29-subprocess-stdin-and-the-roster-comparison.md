# D-232: Every subprocess launch names its stdin, and the roster's comparison stops reading line endings off the disk

**Status:** Accepted 2026-08-29 (PR #232)

## Context

[#229](https://github.com/Grimblaz-and-Friends/tradecraft/issues/229) recorded that `python -m pytest tools/tests` on Windows failed a **different set of tests every run**, every failure tracing to one error — `OSError: [WinError 6] The handle is invalid` out of `subprocess`. Five consecutive full-suite runs on `8b080c8` gave five different results, from `12 failed / 30 errors` to a run that did not finish; every affected module passed in isolation; and CI had never reproduced it, including a green `windows-latest` leg on that very commit.

The filing deliberately left the cause open, naming three candidates — handle exhaustion, interference from endpoint security, something specific to `subprocess` on Python 3.14 — and asking whether CI was genuinely unaffected or had merely not yet lost the coin toss.

A **second and unrelated** cause of a red local run was found while isolating the first. The owner was given the scope fork with the evidence and ruled that it lands here rather than on its own issue; the argued options and that ruling are on the issue.

## Decision

### 1. Every `subprocess` launch names its stdin, and the mechanism is recorded rather than the symptom

**An unnamed `stdin` means inherit, and on Windows what gets inherited can be a handle that no longer exists.** `subprocess` implements inheritance as `GetStdHandle(STD_INPUT_HANDLE)` followed by `DuplicateHandle`. Anything that redirects fd 0 — pytest's default capture, most harnesses — closes the handle the process's std-handle table still points at, while `GetStdHandle` goes on returning the stale value. The duplicate then raises, from a call that has nothing to do with the command being run.

**The intermittency is the whole cost, and it is explained rather than tolerated.** Windows recycles handle values. When some unrelated object in the process happens to hold the recycled value the duplicate *succeeds* — and the child silently receives an unrelated handle as its stdin — and when the value is free, the launch raises. Nothing about the test, the ordering, or the machine has to change for the answer to flip, which is exactly the shape #229 measured.

Three probes settled it, at `8b080c8`:

- A per-test probe of `GetStdHandle(STD_INPUT_HANDLE)` across a full run. **The handle value never changed for the whole run while its validity oscillated between valid and invalid many times over**, with `os.isatty(0)` reporting `True` throughout — the signature of a closed handle whose value is being recycled, not of a redirected descriptor. That distinction is the load-bearing one: a redirected descriptor would have shown a changed value or a false `isatty`, and either would have pointed somewhere else.
- `python -m pytest tools/tests -q --capture=no`, twice. Every `WinError 6` failure disappeared and no other failure changed.
- The two call sites already immune are the two that never appeared in a failure list: `tools/check_codex_compat.py` named `stdin=subprocess.DEVNULL` explicitly, and `tools/lint.py` passed `input=`, which implies `stdin=PIPE`. Neither had been reasoned about as protection; both were.

**`DEVNULL` rather than `PIPE`.** None of the programs launched here is meant to read input, and an inherited-or-piped stdin is the thing being removed; `input=` remains lawful where the program is genuinely given something to read, which is what `check-ignore --stdin` does.

**The two shipped scripts are the half that matters beyond this suite.** `skills/authoring/scripts/figures.py` and `skills/persist-changes/scripts/persist.py` reach consumers. `persist.py` would have reported this as `git rev-parse failed`, naming a cause that is not the cause — a consumer sent to their git configuration by the one script that knew better.

### 2. CI's silence is explained, and recorded as not-evidence

An Actions runner has no console on fd 0, so `GetStdHandle` returns `None` and `subprocess` takes its `CreatePipe` branch, never touching a stale handle. **The green Windows leg was not luck and is not reassurance**: that path cannot reach the defect, so it can never report on it. This is recorded because #229 asked the question directly — *whether CI is genuinely unaffected or merely has not lost the coin toss yet* — and the answer is a third thing, structurally immune, which is the answer a later session would otherwise re-derive from the same green checks.

Stated as the mechanism read out of `subprocess.py`, not as a measurement: no runner was instrumented.

**Endpoint security is closed as not the cause.** #229 floated it, citing `codex doctor` reporting that Defender can interfere. The probes above account for every observation without it. Closed rather than left open, so the next session reading #229 does not spend the budget.

### 3. The guard is a call-site check, and its bound is stated

`check_subprocess_stdin` — lint check 19 — flags any `subprocess.run` / `Popen` / `call` / `check_call` / `check_output` naming neither `stdin=` nor `input=`, over both zones, in the qualified form and in the bare name `from subprocess import run` binds.

**A call forwarding `**kwargs` is left alone**, and that is a decision rather than an oversight. Whether stdin is inside the mapping cannot be read off the call, and reddening there would block lawful work — the polarity the `substrate` cell says fails as hard as the other. The alternative, demanding an explicit `stdin=` beside a `**kwargs` that may already carry one, prescribes a remedy that raises `TypeError`. The bound is held as a test rather than left to the docstring.

### 4. The roster's comparison normalizes CRLF; its write does not

`roster.verify()` compared the **working-tree bytes** of `.claude/skills/<cell>/SKILL.md` against its cell. A worktree whose entries had been rewritten in text mode by the harness that created it therefore reported every cell out of step, and took `python tools/lint.py` red, against a tree `git status` called clean and a commit whose bytes were untouched — before the session had changed anything.

**That is the condition [D-186] ruling 5 already declares expected here rather than a defect, and this guard was the one place calling it one.** The warrant is that inconsistency, not frequency: it holds however often the rewrite happens, and the frequency is in fact unsettled — across the worktrees on the machine where this was found, only the two most recently created carried CRLF under `.claude/skills/`, every older one carrying it on `CLAUDE.md` alone, which nothing compares. Ordered by mtime the boundary was clean and fell on the day of the finding, pointing outside this repository at something that was not identified.

**The write side is untouched, and the asymmetry is the recorded part.** `write()` still emits bytes, so `python tools/roster.py --write` remains the remedy that restores the canonical ones. Two questions with two answers: `verify` asks whether the tree is lawful, and a line-ending difference cannot make it unlawful, because `.gitattributes` pins the index to LF on every platform and a drift that is *only* line endings cannot reach a commit. `write` asks what bytes to put on disk, and there the original argument in `tools/roster.py` stands unchanged. A `write()` that had followed `verify` into normalizing would leave a CRLF entry on disk with nothing left able to say so; a test pins that it does not.

The module docstring's own warrant moved with it. It had justified byte handling by saying *these files are compared by `check_project_roster` on every lint run [...] so the bytes are the same everywhere and the comparison is exact* — a sentence this change makes false in its second half. Left standing, a session checking the stated reason would find it false and reason correctly to undoing the fix.

## What was rejected

- **Repairing the std-handle table in a `conftest.py`, or turning pytest's capture off.** Either makes this suite green and leaves both shipped scripts broken for every consumer. Wrong half, and the half that does not reach anyone outside this repository.
- **Chasing the growth question.** #229 asked whether the suite grew into this, offering one pre-#222 clean run as the only datum. The mechanism makes growth a modulator — more handle churn, more chances to lose the toss — rather than a cause, so re-running `4c4805c` would settle nothing that bears on the fix.
- **Fixing the harness that rewrites `.claude/`.** It is outside this repository. Only this repository's response to it is in scope.

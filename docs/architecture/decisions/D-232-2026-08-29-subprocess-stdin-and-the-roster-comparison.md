# D-232: A launch redirects nothing or names all three streams, and the roster's comparison stops reading line endings off the disk

**Status:** Accepted 2026-08-29 (PR #232)

## Context

[#229](https://github.com/Grimblaz-and-Friends/tradecraft/issues/229) recorded that `python -m pytest tools/tests` on Windows failed a **different set of tests every run**, every failure tracing to one error — `OSError: [WinError 6] The handle is invalid` out of `subprocess`. Five consecutive full-suite runs on `8b080c8` gave five different results, from `12 failed / 30 errors` to a run that did not finish; every affected module passed in isolation; and CI had never reproduced it, including a green `windows-latest` leg on that very commit.

The filing deliberately left the cause open, naming three candidates — handle exhaustion, interference from endpoint security, something specific to `subprocess` on Python 3.14 — and asking whether CI was genuinely unaffected or had merely not yet lost the coin toss.

A **second and unrelated** cause of a red local run was found while isolating the first. The owner was given the scope fork with the evidence and ruled that it lands here rather than on its own issue; the argued options and that ruling are on the issue.

**This entry was rewritten by its own review**, and says so because the correction is the useful part. The change first shipped the rule as *every launch names its stdin*, and a four-seat panel measured that this **manufactures the defect on a launch that did not have it**. Four further claims in the first draft of this entry — the probe's discriminator, CI's immunity, the consumer harm, and a count — were each falsified by a seat or the defense. What follows is the corrected version; the first is in the diff of this pull request, and the panel's evidence is on it.

## Decision

### 1. A launch redirects nothing, or names all three streams

**The rule is about the whole call, not about stdin.** On Windows `subprocess._get_handles` opens with `if stdin is None and stdout is None and stderr is None: return (-1, ...)`. A launch that redirects **nothing** never asks `GetStdHandle` anything and cannot fail this way. Redirect one stream and the others resolve through the process's std-handle table — which can still name a handle something has since closed. `DuplicateHandle` on that raises, from a call that has nothing to do with the command being run.

**Requiring `stdin=` alone was worse than requiring nothing**, and this is the entry's load-bearing correction. Measured under real pytest capture, twenty launches per case in a fresh process each, by two stages independently:

```
bare (redirects nothing)          0/20
stdin=DEVNULL only               20/20  [WinError 6]
capture_output only               0/20  ... 20/20 in other runs -- the intermittent one
stdin=DEVNULL + capture_output    0/20
stdin=DEVNULL + stdout=PIPE      20/20  [WinError 6]
all three named                   0/20
```

The mandated keyword converts a 0/20 launch into a 20/20 failure, and the guard's first version flagged the 0/20 shape and prescribed exactly that edit — the lawful-polarity failure the `substrate` cell names, in its sharpest form.

**It fails intermittently, which is the part that costs.** Windows recycles handle values. When some unrelated object in the process happens to hold the recycled value, the duplicate *succeeds* — and the child silently receives an unrelated handle as its stdin. When the value is free, the launch raises. Nothing about the test, the ordering, or the machine has to change for the answer to flip, which is the shape #229 measured.

**The condition is neither "fd 0 was redirected" nor "fd 0 was redirected in-process".** Both were proposed and both were measured false: a child *born* with fd 0 on NUL or on a pipe has fd 0 redirected and is immune (0/25), and an in-process `dup2` inside such a child left it immune too, moving the table's value with it. The condition is that **the std-handle table still names a handle something has since closed** — reproduced in a shell-launched process where the identical `dup2` left the value unmoved at `656` and flipped the launch 0/15 → 15/15.

**That condition is deliberately not the rule.** A reader cannot check whether their harness left the table stale. They can check their own call, which is why the rule is stated as a property of the call — *redirect none, or name all three* — and why the corrected sentence is shorter than the false one it replaces.

**Two corroborations, and the count is three rather than two.** `tools/check_codex_compat.py` named `stdin=subprocess.DEVNULL`, `tools/lint.py` passed `input=`, and `tools/tests/test_portability.py:152` named `stdin=subprocess.DEVNULL` — three sites, and all three are absent from every failure list in #229 while sitting inside the measured suite. The first draft said two, in four places. The correspondence is three-for-three and the inference is stronger for it.

**`DEVNULL` rather than `PIPE`**: none of the programs launched here is meant to read input. `input=` remains lawful where the program is genuinely given something to read, which is what `check-ignore --stdin` does. **On `run`, `input=None` is not**, because it never reaches `run`'s `if input is not None: kwargs['stdin'] = PIPE` — but on `check_output` it is, because that wrapper rewrites `None` to `b''` before calling `run`. An external reviewer contested this with a cited answer saying `input=None` behaves as `input=b''`; the source contradicts them for `run` and **agrees with them for `check_output`**, so the sentence is narrowed rather than left as a flat contradiction. The split is why the guard asks which launcher it is looking at.

**What the shipped scripts were actually doing, corrected.** The first draft claimed `persist.py` would report this as `git rev-parse failed`. It would not: `WinError 6` is an `OSError` raised *by* `subprocess.run`, before any returncode exists, so the `returncode` check is never reached and the script emitted an unhandled traceback through `subprocess.py:1431` — the exact frame #229 quotes. That was asserted from reading the happy path and never run; the defense ran it. **The residual is real and is not closed here**: any `OSError` from those launches still breaks `persist.py`'s documented one-line output contract — `git` absent from `PATH` reproduces it at the tip — and wrapping them is shipped consumer code outside this change's affirmed boundary, so it is filed rather than fixed.

### 2. CI's silence is explained, and recorded as not-evidence

The first draft said an Actions runner has no console on fd 0, so `GetStdHandle` returns `None` and `subprocess` takes its `CreatePipe` branch. **That is not the mechanism.** `GetStdHandle` returns `None` only for a genuinely detached process handed no std handles at all; a child handed NUL or a pipe gets a live handle.

**The conclusion survives on a different mechanism.** Those children were immune anyway, 0/25, including after an in-process `dup2`: a process **born** with its streams already redirected inherits a table naming handles that are still open, and that is itself the immunity. A CI step's interpreter is exactly that shape. So the green Windows leg is still not reassurance — but because of what the runner *is*, not because of a branch it takes.

This is recorded because #229 asked the question directly — *whether CI is genuinely unaffected or merely has not lost the coin toss yet* — and because the first answer named a cause that measurement contradicts. A later session re-deriving it from the wrong cause would reach the wrong conclusion about a runner whose stdin is a pipe.

**Endpoint security is closed as not the cause.** #229 floated it, citing `codex doctor` reporting that Defender can interfere. The probes account for every observation without it.

### 3. The guard is a call-site check, and its bound is stated honestly

`check_subprocess_streams` — lint check 19 — is silent on a call that redirects nothing, and reports one that redirects some streams while leaving another unnamed. It resolves the callee through **both** import forms including aliases and dotted imports, and it reads each launcher **against that launcher's own source rather than against `run`'s**: `check_output` redirects `stdout` by construction and pipes `input=None`, `capture_output` exists only on `run`, and `input` only on `run` and `check_output`.

**That per-launcher reading is the review's largest correction to this change and it took two cycles.** The first version required `stdin=` alone, which manufactured the defect on a launch that redirected nothing. The second read every launcher as `run` — so it certified `check_output(cmd)`, measured failing 20/20, and reddened four `check_output` shapes measured at 0/20. **Three proposed remedies across the two cycles diagnosed correctly and prescribed a fix that would have reddened lawful work**, every one of them by assuming a wrapper behaves as `run` does; each was caught only because a defense ran the counterfactual in both polarities unprompted. That is recorded in `docs/recorded-findings.jsonl` against the evidence standards, which bind a guard under review to both polarities and say nothing about a finding's own proposed remedy.

**Each of those is a hole a version of this check shipped**, and none was anticipated — the module alias was found by three seats and both external reviewers, `stdin=None` and `input=None` by two seats, the `getoutput` family by three, and `check_output` and the positional forms by the post-fix look. **A completeness claim about a guard's own bounds is what turns a gap into a false all-clear**, and this entry made that mistake twice: the first version's docstring claimed *"Two consequences follow and are the guard's stated limits"* and four spellings escaped; the second announced it was not stating a closed list and then stated one of two items, which positional arguments and `*args` escaped. **The bound is now a criterion and not a list**: the check reads *keyword arguments*, and anything positional, splatted, or not a literal is unread. Unread is silence — whether a stream is redirected is genuinely unknown there, and reddening on it blocks lawful work.

**`getoutput`, `getstatusoutput` and `os.popen` are named rather than stream-checked**, because the rule has no compliant form for them: each redirects a stream by construction **and** exposes no stdin parameter. Silence there read as permission, which made the shipped rule unsatisfiable rather than merely unenforced. **`check_output` is deliberately not among them**, and the distinction is the load-bearing half: it also redirects by construction, but it *does* have a compliant form — `stdin=` and `stderr=`, measured 0/20 — so naming it unconditionally, which is what the look proposed, would redden lawful work. Under the shipped guard there is no spelling of `check_output` that is both clean and safe, which is true of the guard and false of the underlying safety property; both halves are stated because collapsing them is what produced the wrong remedy.

The guard **does not filter through `.gitignore`** where two sibling checks do, and **does not walk repository-root `.py` files**. Both are priced out rather than overlooked: the first costs a `git check-ignore` subprocess per run against a condition `.gitignore` already steers outside every walked directory, and the second diverges this check's walk alone for a file class this tree does not have. Both reopen if their condition arrives.

### 3a. The `substrate` description gains a launch trigger, and the outflow is refused with its reason

The cell gained a standard and a `references/` file and its **description** gained neither, so the one occasion the standard exists for — a script launching another program — was absent from the surface that decides whether the cell loads. For an adopter that is the whole of the enforcement: `tools/lint.py` is repo-only and ships to nobody. Under-triggering is the failure mode the `authoring` cell names, and a cold-seat A/B run by this change's defense reproduced it — the one arm-A seat that declined the cell declined it in exactly those terms, *"no printing, file writes, or path lookups … despite being 'a script.'"* The mechanism is demonstrated; the **rate is not**, at 1 of 6 against 0 of 4, and it is recorded that way rather than as a measured frequency.

A description is an always-on surface, so the edit owes an outflow. **It is refused, and this is the refusal.** All three moves were examined and none applies, for one structural reason: each move relocates *a rule*, and a description contains no rules. It carries a name, a summary of what the cell holds, and the triggers that decide when it loads.

- *A rule a guard now holds becomes the rule plus the guard's name* — there is no rule here to compress. The guard is named in the cell's body, which is not always-on.
- *A rule that binds only inside one activity moves to that activity's cell* — the content already **is** the cell's; what sits in the description is the pointer that makes the cell fire. Moving a trigger into the body is precisely the failure [D-210] records, where every trigger routed to a description reached every adopter and missed this repository.
- *A reason a decision entry carries compresses to its citation* — the description carries no reasons.

So the surface grows, by the difference between two runs of `python tools/figures.py` — on this PR's tree and on a worktree at `916af5d` — differencing the *from this practice for an adopter* value on the `always-on surface` line. It is paid for because a rule nobody loads costs the same in bytes and delivers nothing, which is [D-192]'s own ground for the ninth cell.

**One thing this refusal exposes and does not fix:** the outflow's three moves are each defined over a rule, so an edit to a *description* can never discharge by a move and can only ever be refused. That may be correct — descriptions are the surface least able to give anything up — but the rule reads as though a move were generally available, and a session meeting it for the first time on a description edit will look for one that cannot exist. Recorded rather than argued here; it is the `authoring` cell's to settle.

### 4. The roster's comparison normalizes CRLF on the entry side; its write does not

`roster.verify()` compared the **working-tree bytes** of `.claude/skills/<cell>/SKILL.md` against its cell. A worktree whose entries had been rewritten in text mode by the harness that created it therefore reported every cell out of step, and took `python tools/lint.py` red, against a tree `git status` called clean and a commit whose bytes were untouched — before the session had changed anything.

**That is the condition [D-186] ruling 5 already declares expected here rather than a defect, and this guard was the one place calling it one.** The warrant is that inconsistency, not frequency.

**The frequency is a race, not a change.** The first draft inferred a clean boundary in worktree creation times "pointing outside this repository at something that was not identified". Re-enumerated, CRLF and LF interleave among worktrees created by the same tooling — two 36 seconds apart with opposite results — so there is no boundary and no day it changed. What is established is that the condition is live: 3 of 26 worktrees measured carry it, including ones created for this change's own review.

**The write side is untouched, and the asymmetry is the recorded part.** `verify` asks whether the tree is lawful, and a line-ending difference cannot make it unlawful, because `.gitattributes` pins the index to LF on every platform. `write` asks what bytes to put on disk, so `--write` still restores the canonical ones. A `write()` that had followed `verify` into normalizing would leave a CRLF entry on disk with nothing able to say so; a test pins that it does not.

**The fix is one-sided and that is recorded rather than implied.** With the *cell* in CRLF, `expected()` has already lost a byte before the comparison sees anything — `frontmatter()`'s own documented bound — so `verify` still reports and `--write` converges to green having rewritten every entry. The repair belongs in `frontmatter()`, which other checks read; the broken polarity is unobserved (0 of 26 worktrees) where the fixed one is live (3 of 26). Filed rather than fixed here.

One consequence is accepted: `--write` still repairs a CRLF entry and nothing surfaces that. Any line from `verify` would reinstate the noise this removed, so the remedy is recorded in `in_step`'s docstring instead, where a session asking why its tree looks modified will be reading.

The module docstring's own warrant moved with it, and so did the shipped rule. `tools/roster.py` had justified byte handling by saying the files *"are compared by `check_project_roster` on every lint run [...] so the bytes are the same everywhere and the comparison is exact"* — false in its second half after this change. `skills/substrate/references/text-mode.md`'s third rule said the same thing to every adopter, and its warrant paragraph claimed the rule was *"preventive against a mutation seat […] rather than a response to a defect already firing"*, which this change falsifies. Both now state the write and the comparison as two questions with two answers.

## What was rejected

- **Repairing the std-handle table in a `conftest.py`, or turning pytest's capture off.** Either makes this suite green and leaves both shipped scripts broken for every consumer. Wrong half.
- **Chasing the growth question.** #229 asked whether the suite grew into this. The mechanism makes growth a modulator — more handle churn, more chances to lose the toss — rather than a cause.
- **Fixing the harness that rewrites `.claude/`.** It is outside this repository. Only this repository's response to it is in scope.
- **Adding `getoutput`/`getstatusoutput` to the stream-checked launchers.** There is no keyword to add, so the finding has to say something different from the others: use `run` instead.
- **Surfacing `--write` from `verify` in the CRLF condition.** That is the noise this change removed, re-added under another name.

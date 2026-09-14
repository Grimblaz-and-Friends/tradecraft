# D-611 — The substrate cell swept: the concepts stay, three rules go to the guards, three histories to their entries

**Landed by** [PR #611](https://github.com/Grimblaz-and-Friends/tradecraft/pull/611). Closes [#582](https://github.com/Grimblaz-and-Friends/tradecraft/issues/582). Governed by the implementation brief affirmed on [#571](https://github.com/Grimblaz-and-Friends/tradecraft/issues/571#issuecomment-5627498365) on 2026-09-10, which commissions each cell's sweep as its own reviewed change without a fresh affirmation; [D-575] landed the principle. Evidence pinned at `c475289` unless stated, over base `76ea486`.

## What was decided

The `substrate` cell keeps every concept it carried and sheds what a guard, a script's own message, or a decision entry already holds. Twenty passages stay verbatim, ten are sharpened to their concept, and eight leave whole for another material; four of the ten sharpened lines also shed a sentence, and those are classed too. The pre-implementation artifact settled all 38 dispositions sentence by sentence before anything was built, and one cold seat on the other vendor returned `would` with no points against it.

**Why this cell's shed is unusual: it has two readers and only one of them gets the guards.** A session inside this repository meets five checks in `tools/lint.py` that already read these rules and say the right thing at the moment of the mistake. A session in an adopting repository receives the cell and none of them, and the wall forbids a shipped cell naming `tools/`. So *to guard* here means the rule is already what a guard reads and says, and the shipped prose keeps the concept an adopter needs in order to write its own — never a pointer at this repository's.

## Every passage that left, and which material took it

As the brief requires: the change that removes a rule says which it was. **Deletions fall in two places and both are tabled below** — eight passages that leave whole, and four sentences cut out of lines the sweep classes as sharpened. The brief's requirement is about deletions, not about rows, so both tables are owed.

### The eight passages that leave whole

Nine rows for eight passages: `text-mode.md:8`'s fifth-and-sixth sentences are split across two rows because their halves went to different materials, which is itself what this change's review found.

| passage | class | where it went |
| --- | --- | --- |
| `subprocess-streams.md:11-17` — *The compliant forms* and its five bullets (`run(cmd, stdin=DEVNULL, capture_output=True)`; `input=` and `input=None`; bare `run(cmd)`; `check_output`; the `getoutput`/`getstatusoutput`/`os.popen` family) | to guard | `check_subprocess_streams`. Its message names the missing streams and the `DEVNULL` form, and suppresses the *"or redirect none of them"* escape exactly where the launcher redirects by construction; `_IMPLICIT` holds `check_output`'s `stdout`, `_TAKES_INPUT` its `input=` rewriting, `_NO_STDIN` the family with no compliant form. [D-232] holds every per-launcher fact and the two review cycles that found them. |
| `subprocess-streams.md:19` — *"`stdin=None` is the default spelled out"* | to guard | `_redirected` reads a literal `None` as no redirect. A case the concept decides. |
| `subprocess-streams.md:29-31` — the enumeration of what a call-site check cannot see (a second positional argument, a splat, a non-literal `capture_output`, `stdout=NL` where `NL = None`) | to guard, and to entry | `_redirected`'s docstring states it as a criterion; [D-232] holds the bound verbatim together with the three wrong statements of it. The prose keeps one sentence — a call-site check reads the callee and its keyword arguments and stays silent where the redirect is genuinely unknown, because reddening there blocks lawful work. |
| `subprocess-streams.md:9` — the measurement table (`run(cmd)` 0/20, `stdin=DEVNULL` 20/20, `stdin=DEVNULL, capture_output=True` 0/20) | to entry | [D-232]. Evidence, not concept. The prose keeps the sentence the figures were evidence *for*: the stdin-only rule converts an immune call into a failing one, which is why the rule is about the whole call. |
| `text-mode.md:8`, sentences 5-6 — *"The two properties are the rule; a helper is only how a practice discharges them"* and the reach-for-it instruction | to script message | `check_stdio_wired`'s finding already says to import `utf8_stdio` from `lib/winio.py`, resolving `lib/` against the file's own directory rather than the working directory, and to call it as the first statement. One sentence replaces them, naming `lib/winio.py`'s `utf8_stdio()` as this tree's setup. |
| `text-mode.md:8`, sentence 6's second half — *"neither redefine nor shadow the name: a local no-op with the right name satisfies a call site while setting nothing up"* | to entry (a recorded incident) | **Not to the guard's message, which never mentions shadowing.** [D-252]`:42` records the guard reading only that a name arrived by an import — not its source module, and not that the call still resolves to it — and [#254](https://github.com/Grimblaz-and-Friends/tradecraft/issues/254) is that incident filed with both reproductions and their negative controls. The owner read #254 at his hearing of 2026-09-12 and closed it **not planned**: *"a guard for a class with no instance is bought when the instance arrives."* So the rule's material is the recorded incident, which is one of the brief's four, and the guard is deliberately unchanged. |
| `text-mode.md:25` — *"Say so where you state the rule. Leave it unsaid and whoever notices their redirected output changed goes hunting their editor…"* | to entry | [D-186], whose own text carries the incident. A writing instruction whose entire content was the incident. |
| `text-mode.md:27-29` — the byte-comparison narration (a guard reported every file out of step on a tree version control called clean, because the harness had rewritten one side in text mode) | to entry | [D-232]. The prose keeps one sentence: the third rule is not about encoding, and it has fired on a real tree. |
| `text-mode.md:8`, sentence 8 — *"A guard that reads the import binding is a proxy for this and never a substitute…"* | cut, unwritten | A second statement in the same file of the bound `:19` already carries. Not a concept; a duplicate. |

### The four sentences cut out of sharpened lines

A line classed *sharpen* keeps its concept and its reason. Four of the ten also had a whole sentence removed, and each of those is a deletion the brief requires be classed. **This table was missing from the entry as first written, and both the review's `revision-diff` seat and its defense established that; the entry's earlier claim that no sharpened line sent a sentence elsewhere was false.**

| sentence cut | from | to |
| --- | --- | --- |
| the enumeration of what a literal check flags and misses — *"a filename or a regex source"*, `chr()`, a format call, a `__str__` | base `text-mode.md:15` | `check_emitted_ascii`'s **docstring**, which names each case; its **message** carries the operative half — *"in a non-docstring string constant"*, the wording [D-186]`:57-62` records was chosen because the first version claimed a property it never computed. The enumeration is the docstring's, not the message's |
| *"and that objection is why a helper is sometimes rejected outright"* | base `text-mode.md:19` | [D-186]`:22`, a recorded incident; it is history, not concept |
| *"Ban the construction rather than reasoning about whether the stream happens to be set up: the ban keeps the exemption honest, which is a warrant that survives changes to how streams are configured."* | base `text-mode.md:35` | `check_docstring_not_piped`'s docstring, which states the warrant and why it survives; [D-186]`:33` holds it |
| *"both were missed by people reasoning from `run` — including, three times over, by reviewers proposing fixes for the first two"* | base `subprocess-streams.md:21` | [D-232]`:60`. The concept stays and now carries the single `check_output` example the principle allows, in place of the forms list |

**The remaining six sharpened lines sent no sentence to another material**: each was reduced to its concept and its reason, and the diff is the whole record of what went. The one further deletion among them — *"So state the two halves apart"* at base `text-mode.md:31` — is a writing instruction whose halves follow it, and it is unwritten rather than moved.

## Three calls the sweep made, stated so a later sweep does not re-make them

**This cell emits no template, and that is a decision rather than an omission.** The reading that governs these sweeps sends an output's fields to a template and keeps in prose what the output is for. What a session copies at the moment of writing under this cell is *code* — the entry point's first statement, the compliant launch form — and each is already what a guard's message says at the moment of the mistake. A template here would be a script skeleton, which is a new script, which the brief puts out of scope.

**One premise the dispatch carried was run and not confirmed, and the record says so, so no later sweep re-finds a copy that is not there.** The dispatch said the both-polarities rule and the negative-control requirement had copies in `skills/adversarial-review` and `docs/cells/siting` to be cut. They do not. Searched at `bd71c4f` and again at `76ea486` for the rule's own vocabulary and for the surrounding concepts; the nearest sentences elsewhere are different rules — `skills/adversarial-review/references/after-the-fix.md`'s new-test-pin-goes-red-pre-fix, and `skills/adversarial-review/references/roster.md`'s `wiring-falsifier` lens. [D-376] records the rule moving *whole* to `substrate` and the owner ruling the description amended rather than the rule moved back. **This cell owns both, and no copy was cut anywhere.** If a later sweep finds one under words these searches did not try, it is that cell's to cut and point here — never this cell's to keep a second time.

**Three citations were added rather than assumed**, so a reader following a shed rule reaches what took it: [D-252] at `text-mode.md:19`, [D-186] at `:23`, [D-232] at `:27`. Each was checked to hold what the prose sends it before the sentence was written.

## Two things observed and deliberately not fixed, for the `siting` sweep

**Which guard holds which checkable subset of the text-mode and subprocess rules is not stated anywhere a reader can reach.** `skills/authoring/references/routing.md` says what survives in prose is the concept *plus the guard's name*; the wall forbids a shipped cell naming a repo-only guard, and the repo-only `siting` cell — which does exactly this for cell structure and for the calling contract — does not do it for these two. This is the one place that instruction cannot be discharged in the shipped cell, and the sweep named it rather than naming `tools/lint.py` from `skills/`.

**`check_stdio_wired`'s docstring overclaims what its check establishes.** It says the import-binding check *"is what makes 'it was called' mean 'the helper was called'"*. [D-252] records the guard reading that a name arrived by an import — not its source module, and not that the call still resolves to it — so a shadowed or borrowed `utf8_stdio` passes green while the script emits CRLF; the guard itself is [#254](https://github.com/Grimblaz-and-Friends/tradecraft/issues/254). Both the artifact's author and the cold seat observed it independently. A docstring in a repo-only tool is code rather than governing prose, and the brief funds a swept rule's move and not a repair the sweep noticed.

## The ceiling followed the body down

`CELL_BODY_CEILING_CHARS["skills/substrate/SKILL.md"]` is re-baselined to the body's size at this change's tip. The constant's own comment prescribes this for a cell that sheds depth, and a ceiling left where it stood would measure nothing until the body regrew to meet it.

## No settling row, and the reason

`docs/settling.jsonl` takes one row per change owing an implementation brief, recording how that brief reached settled. This change's brief is #571's, affirmed once for every sweep it commissions, and its row is already on that record. A second row would record the same affirmation twice. The cold check's rounds are on the pull request instead. The `engagement` cell's sweep made the same call, so the sweeps agree.

## Figures

Stated as commands with both endpoints pinned, never as outputs. **`tools/figures.py` reads the working tree and has no option naming a tip**, so the tip is pinned by the checkout the command runs in, not by a flag — cut one and run there:

```
git worktree add --detach <path> c475289
```

- **Shipped prose delta** (the brief's own measure), from that checkout's root: `python tools/figures.py --base 76ea486 --cell skills/substrate/SKILL.md --cell-budget 2922`. `--cell` refuses without `--cell-budget`, and the budget given must equal the enforced one or the script says so. This prints the prose delta against the base and the cell's body against its ceiling in one run. The raw form of the delta alone is `find skills -name "*.md" -exec cat {} + | wc -c`, run once on each of `76ea486` and `c475289`, which needs no checkout because both endpoints are named.
- **The ceiling the body is measured against:** `python tools/lint.py` in that same checkout, which reads the constant back and reports any cell over where it stood.
- **What the diff touches:** `git diff --stat 76ea486 c475289`, and `git diff 76ea486 c475289 -- tools/lint.py` for the single constant. These name both commits and run from any checkout of the repository.

[D-575] [D-232] [D-186] [D-252] [D-156] [D-376]

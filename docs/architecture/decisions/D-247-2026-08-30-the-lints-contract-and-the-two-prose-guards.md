# D-247: The lint's checks report one at a time, the frontmatter slice takes a line ending, and the two prose guards skip for two different reasons

**Status:** Accepted 2026-08-30 (PR #247)

## Context

Three issues, all defects in what `python tools/lint.py` reports — which is the one command this repository's flow mandates between an edit and a commit. [#239](https://github.com/Grimblaz-and-Friends/tradecraft/issues/239): `run()` was a single `+` chain, so any check that raised discarded every finding computed before it. [#234](https://github.com/Grimblaz-and-Friends/tradecraft/issues/234): `frontmatter()` took one byte after the frontmatter terminator, which on a CRLF cell is the carriage return, so the copied block lost a newline and the repair the finding named committed a change no local diff could show. [#233](https://github.com/Grimblaz-and-Friends/tradecraft/issues/233): the two predicates its own review had deferred, for prose that names a control character and loses it.

**What each mechanism does is on the mechanism**, in docstrings this entry does not restate. `run()`, `frontmatter()`, `check_hollow_code_span` and `check_committed_carriage_return` carry their own accounts, with the probes and the tests that pin them. A cold consumer asked to write this entry reported that doing so was *"largely transcription from code into the log"* — so what follows is only the choices, which the code does not carry, and what was rejected.

## Decision

### 1. Isolate every check rather than fixing the one that crashed

The trigger was a check formatting `node.lineno` on an `ast.Module`. Fixing that one crash was available and was rejected: the chain's shape is what turns any future check's bug into a total loss of the run, and nineteen other checks shared it. **Rejected:** a decorator on each check — a new check joins the chain by being added to a tuple, and one that forgot the decorator would silently reinstate the defect.

### 2. The finding claims only what it computed

A raising check yields a finding naming the check, the exception, and the frame **inside this repository**. It does not say the rest of the tree is clean, and does not guess what the check would have found. **Rejected:** naming the innermost frame outright, which lands in the standard library and prints an unsearchable bare basename that reads like a repository path.

### 3. Repair the slice, not one of its callers

`frontmatter()` is where the bound was documented and what other readers call. **Rejected:** normalising inside `expected()`, which fixes the one caller and leaves the bound live for the next.

### 4. Non-empty whitespace, and no exclusion list

The predicate for a hollow code span is content that is whitespace **and not empty**. This is the answer to the question [#233](https://github.com/Grimblaz-and-Friends/tradecraft/issues/233) deferred — *how the exclusion for the doubled-backtick idiom is written* — and it dissolved rather than being decided: every false positive that predicate produces has content that is *exactly* empty, because the idiom's inner span is the gap between the doubled backticks. **Rejected:** a list of the idiom's call sites, which goes stale the next time anybody writes about fences.

### 5. Read the working tree, not only the index

The carriage-return guard reads three populations: the index copy, the working copy where git classifies it differently, and untracked files git is not told to ignore. **Rejected, and this was the shipped answer for two commits:** reading the index alone. `AGENTS.md` runs the lint before staging and `persist.py` refuses a pre-loaded index, so the index provably does not hold the session's work — the guard could not fire until the run *after* the bytes had landed, on a file that is by then often frozen. The pull request body asserted this choice *"changes cost and not answers"*; it changed answers.

### 6. Two skip lists, because the two guards skip for two different reasons

The frozen archive is skipped by both guards. The live append-only records — `docs/reviews.jsonl` and `docs/recorded-findings.jsonl` — are skipped by the **prose** guard only. **Rejected, and also shipped briefly:** one shared list. A hollow code span in a review row is intended content, since a finding must quote the line it names; a lone carriage return there is corruption of the row's own JSON, and [#233](https://github.com/Grimblaz-and-Friends/tradecraft/issues/233)'s motivating instance was exactly a row appended by a script whose escapes had become control bytes.

### 7. Three issues in one pull request

They are three defects in one consumer's contract, they interlock, and their files are disjoint. Reviewed under one purpose statement and not disturbed by it.

## What this entry does not settle

- **Unifying the three fence implementations** — [#249](https://github.com/Grimblaz-and-Friends/tradecraft/issues/249), which also carries the finding that on an indented fence marker `check_hollow_code_span` is correct and `_unfenced_numbered` is not, so a naive unification would regress the newer check.
- **Validating `docs/recorded-findings.jsonl`** — [#251](https://github.com/Grimblaz-and-Friends/tradecraft/issues/251).
- Four findings held for evidence rather than acted on, each with its promotion condition, in `docs/recorded-findings.jsonl`.

No always-on surface is edited, so no outflow is owed. [D-184]

## Consequence

The flow's first mandated step now answers with a list in every case a session can reach, including one where a check itself is broken. The cost is that a lint run reads three git populations rather than one and walks the whole tree rather than the Python files; measured at 1.077s before and 1.275s after, on the command a session runs before every commit.

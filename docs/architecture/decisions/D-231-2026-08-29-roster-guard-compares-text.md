# D-231: Which worktrees rewrite the roster, the bound on what the comparison forgives, and a guard for prose that names a control character

**Status:** Accepted 2026-08-29 (PR #231)

## Context, and what this entry does not decide

[#224](https://github.com/Grimblaz-and-Friends/tradecraft/issues/224) was a Claude Code session worktree opening with a finding per cell from `check_project_roster`, on a tree nobody had touched: the entries under `.claude/skills/` were CRLF, the cells were LF, and `roster.verify` compared bytes. The flow requires a green `tools/lint.py` before committing, and the session had no way to tell that red from one it had caused.

**[D-232](D-232-2026-08-29-subprocess-stdin-and-the-roster-comparison.md) decided the remedy, independently and first**, closing [#229](https://github.com/Grimblaz-and-Friends/tradecraft/issues/229): `in_step()` compares with CRLF normalised, `write()` keeps emitting bytes, and `--write` stays the command that restores canonical ones. This change reached a byte-identical predicate on its own branch and **defers to that entry** — including on the half the two branches disagreed about, where this one had routed `write()` through the predicate too, so `--write` would report honestly rather than churn. That is a landed decision with its own review and its own recorded consequence, and re-litigating it on a second branch would be this repository deciding one mechanism twice.

What is left is what D-232 does not carry, and this entry is scoped to exactly that.

## Decision

**1. The mechanism, and the population it reaches — stated narrowly, because the wide version is worse than useless.**

A Claude Code **session** worktree comes up with ten files written in text mode by the harness — the nine roster entries **and `CLAUDE.md`** — while git checks out the other tracked files LF in the same second. Established by a creation-mtime trace: two write operations 100ms apart, and the CRLF group is not an index-order prefix, `.claude-plugin/` sorting before `.claude/skills/` and landing in the later group. So it is not part of git's checkout.

**`agent-*` subagent worktrees do not do this, and they are Claude Code worktrees too.** Across one machine, `CLAUDE.md` was CRLF in 14 of 15 session trees and 0 of 16 agent trees, the source checkout LF.

**`CLAUDE.md` is the durable check.** Nothing in this repository rewrites it, where `--write` erases the evidence under `.claude/skills/` the moment anyone clears the red — so its line endings are a fossil of how a worktree was made, readable in one command.

The scope sentence is the load-bearing part. A first draft said *every* Claude Code worktree, and all five seats of this change's review — each running in an `agent-*` tree — checked their own tree, found LF, and reported the recorded cause as false. One reviewer inverted it by finding the discriminator no stage had looked for.

**`core.autocrlf=true`, set in the system gitconfig on that machine, is not the cause**: git checked out the other tracked files LF in the same second in the same tree. **Nor was the source CRLF and the copy faithful**: the source `CLAUDE.md` is LF with an mtime three weeks older than any copy. A byte-preserving copy *does* also happen — the gitignored local settings file carries the source's mtime to the microsecond in every worktree, LF ones included — which is why its presence is **not** evidence of the text-mode copy and is not offered here as any.

**2. What the normalised comparison forgives has a bound, and it is one character wide.**

Git's `text=auto` refuses to normalise **any file holding a lone carriage return**, committing every CRLF in it verbatim. That does **not** make an entry carrying one forgiven: `in_step()` returns False and the finding fires, which is what two paired fixtures pin. The exposed case is the one where the **cell** carries a lone carriage return **inside its frontmatter block** — `frontmatter()` copies that block faithfully, so `want` carries it too, the entry agrees as text, and git commits the CRLF verbatim.

| composition | `in_step()` | finding |
| --- | --- | --- |
| CRLF entry, plus a stray lone CR | False | fires |
| LF entry, plus a stray lone CR | False | fires |
| all-CR entry | False | fires |
| **cell carries the lone CR inside its frontmatter** | **True** | **silent** |

Two narrowings a review pass had to make to this paragraph, both in the direction this change kept failing in. The bound reaches a lone carriage return **inside the frontmatter block only** — one in a cell's body puts none into `want`, since `expected()` copies only the block, so there is no exposure. And an earlier draft said the guard forgives any lone-CR entry, which inverted the finding into a false negative against two passing tests. Recorded on [#234](https://github.com/Grimblaz-and-Friends/tradecraft/issues/234), whose repair site is the same function.

**3. Pinning that bound takes two fixtures, and neither half does it alone.** A stray carriage return inside an otherwise-CRLF entry kills "strip every carriage return"; an all-CR entry kills "treat a lone carriage return as a line ending". This change shipped only the first for one revision, having replaced the second without checking what it had been discriminating against, while a mutation matrix in a commit message read as full coverage.

**4. A control character in a docstring is a guard's business, and the guard reads the compiled value.** `check_docstring_control_chars` bans any control character but a line feed or a tab in a docstring's compiled value. A docstring is not raw, so a backslash followed by r, written in one, *is* a carriage return at runtime.

It reads the compiled value rather than the bytes because the instance that motivated it had clean bytes on disk and four carriage returns in `__doc__`. **The two surfaces are disjoint for the carriage return specifically, and overlap elsewhere:** Python's tokenizer folds a lone carriage return in source to a line feed before a docstring compiles, so that one character is invisible here and visible only to a byte scan — while other raw control bytes on disk do survive into the compiled value and are reported, a raw NUL excepted, which raises `SyntaxError` and is check 14's to report. The committed-byte scan and the remaining predicates are [#233](https://github.com/Grimblaz-and-Friends/tradecraft/issues/233).

Admitted on measurement rather than principle: the docstring predicate returned zero false positives across every tracked file, and the class it catches fired repeatedly inside the one change that added it — a committed decision-log row split by two control bytes, a docstring carrying carriage returns after a repair turned its bytes into escapes it never doubled, a code span that lost the character it named, and the check's own registration sentence. Named rather than counted: the count was wrong the moment the next instance landed.

**5. The tree-level roster test asks that every cell has an entry, not that nothing else is there**, and stops asserting the entries are LF on disk. Both were reds a session could not clear while doing what the material tells it to. `.claude/skills/` is the runtime's documented home for a project's own skills and `MARKER` exists to leave a hand-written one alone, so writing one turned the suite red while the lint stayed green; and the on-disk assertion is a property of whatever produced the tree, false in every session worktree. A cold session found the first by being asked to add a project skill. What the generator writes is still pinned in `tmp_path`, where no later copy can move it.

**No always-on surface is edited, so no outflow is owed.** [D-184]

## What was rejected

- **Reporting a line-ending-only mismatch as its own finding.** It leaves the check red on a clean tree, which is the defect; no action clears it durably.
- **Chasing the copier.** The harness writes those ten files and git writes the rest in the same second; neither is this repository's to change.
- **A checked-in normalisation.** `.gitattributes` already does everything git can do here.
- **Deciding the comparison a second time.** D-232 decided it; this entry defers rather than agreeing in parallel.

## What the change's review turned up

- **Five of five seats reported the recorded cause as false, and all five were wrong for one shared reason** — every seat ran in the population the mechanism does not reach. A claim about what a harness does needs the population it was measured over stated beside it, or the next reader's own tree is a counterexample.
- **The recurring defect was one shape stated six ways:** a claim about what reads what, or what a guard forgives, wider than the population measured. Each round fixed an instance and wrote another, including the guard added to end the class, whose first run caught its own docstring. The repair that held was the one that stopped asserting: the reader census now records its command and its falsifier instead of its answer.
- **An external reviewer, receiving no dispatch and no purpose statement, found the load-bearing inverted claim five hours before any of five seats, two defenses and two terminal stages.**
- **The lint had no carriage-return check of any kind** when this began; it has one half of one now, and the other half is filed. Any check that raises still discards the other checks' findings — [#239](https://github.com/Grimblaz-and-Friends/tradecraft/issues/239), found when the new guard crashed the whole lint on a control character in a module docstring.
- **The `substrate` cell's warrant for the text-mode rule says the defect class has never fired.** It fired here, on real trees, with no conjunction and no mutation seat — [#235](https://github.com/Grimblaz-and-Friends/tradecraft/issues/235), which the affirmed boundary made the owner's.

# D-97: The dispatch contract, restated

**Status:** Accepted 2026-08-21 (PR #97)

## Context

[D-90](D-90-2026-08-20-dispatch-contract.md) landed the dispatch contract and then records, in its own Decision section, that the sentence carrying it had **five versions in one day** and that two single words were left load-bearing: `both`, because the fidelity clause trailed its pair and `each` reached only one conjunct by nearest antecedent; and `itself`, because byte-identity had to reach back across an intervening list to the assignment. That entry says in terms that "tidying it back reopens a high."

A sentence whose correctness depends on a reader not tidying it is a sentence that will be tidied. `skills/authoring/SKILL.md` already names the remedy — *"If a competent reader genuinely could go wrong, restate the sentence more plainly rather than appending a qualifier to it"* — and all five amendments had been qualifiers. Filed as [#95](https://github.com/Grimblaz-and-Friends/tradecraft/issues/95), which also carried four gaps the expression left open, and [#94](https://github.com/Grimblaz-and-Friends/tradecraft/issues/94), which asked whether one clause of it should be reworded, reasoned, mechanized, or withdrawn.

**They are one change.** #94's clause sits inside #95's sentence; settling it separately would rewrite that sentence under a gate that had affirmed half of it, which is the reason D-90 gave for not splitting #82 and #88.

## Decision

**The fidelity clause leads the pair instead of trailing it, and byte-identity stands alone.** `both` and `itself` are **gone rather than replaced**: a clause that precedes both items needs no distributive word, so nearest-antecedent has nothing to strand, and byte-identity as its own sentence with `the assignment` as subject needs no anchoring pronoun. This is the point of the restatement — a fix that swapped one qualifier for a better one would have been the sixth amendment, not the remedy the authoring skill prescribes.

Four gaps close in the same text. **Part one carries the assignment and predecessor output *and nothing else***, because the note bar is scoped to part two while the motivating incident was two steers measured *inside* the byte-identical span — aiming prose in part one was lawful and unlabeled. **`in this skill's own words` is fronted**, governing the recipient's identity as well as its lens brief, because identity was an unconstrained free-text slot sitting one noun left of the brief that amendment 3 constrained, with the relabelling defeat still open there. **The contract names its one exception where the contract is read** — a dispatch read cold does not receive predecessor output — because `:41` bound every dispatch to carry it while `:37` exempted the cold read, with no cross-reference either way; that is D-90's own placement argument applied to its own exception. And **`the seat stage`, which occurred exactly once in the shipped zone and was defined nowhere, becomes `no seat dispatch takes one, on either lane`** — `seat` is defined by the roster. The bar's scope is deliberately unchanged: it still covers every seat, not only the cold one. The previous phrase simply had no definition to check that against, so a dispatcher could not tell whether a cold post-fix prosecutor was bound.

**#94's clause is reworded and given its reason inline:** `and nothing before it` becomes **`with no per-recipient content before it — a preamble is somewhere to put such framing ahead of the assignment`**. The old wording barred the wrong thing. It forbade a byte-identical title line, which is harmless and which every compliant dispatch in the corpus uses, and it never named per-recipient framing, which is what the hazard actually is and what went wrong every time.

**The record was measured, not argued.** A spike read the first `type: "user"` record of every `~/.claude/projects/<slug>/*/subagents/agent-*.jsonl` across all sixteen tradecraft project slugs — the main clone and fifteen worktrees — and computed the common prefix across sibling dispatches. **286 records enumerated, 286 prompts recovered, 0 failures.**

| dispatch group | n | shared prefix | position zero |
|---|---|---|---|
| PR #90 five-seat panel (17:20Z, before the clause landed) | 5 | 5,025 chars | `# Review assignment` |
| PR #90 post-fix cycle 2 (20:06Z, after) | 2 | 31 chars | `# Review assignment — post-fix prosecution look, PR #90, cycle 2` |
| PR #96 post-fix cycle A (00:11Z, after) | 4 | 5,836 chars | `## ASSIGNMENT` |
| PR #96 post-fix cycle B (02:11Z, after) | 2 | 6,150 chars | `## ASSIGNMENT` |

**#94's "0/8 … nobody obeyed it once" is true of the eight and false as a record.** The very next review ran **6/6 compliant** at 5,836 and 6,150 characters of shared prefix, diverging at `## YOUR IDENTITY`. Two caveats belong with that number: those six were dispatched after #94 was filed at 22:30Z, so it is obedience-after-being-caught rather than spontaneous; and the panel row predates the clause, so it evidences that the shape is natural, not that anyone complied. What it does settle is that the rule is followable and that "genuinely inert, obedience has no payoff" is not the explanation.

**The failure has one shape, not three.** All eight breaks are a *disambiguating subtitle* on a **post-fix-cycle** dispatch — the dispatcher labelling a prompt for its own bookkeeping while sending sequentially over hours with two cycles in flight. Panel dispatches, five prompts fired from one template in ninety seconds, never needed a subtitle and never broke it. The failing population is one dispatch shape, not the four stage types #94 counted.

**Net growth is +11 words on the paragraph, justified rather than paid back**, and the owner ruled that explicitly. The gap closures cost 8, the reason clause and fronted modifier 11, and compressing D-90's 48-word justification tail returned 20 — that tail being exactly the prose the authoring skill sends behind a link, which D-90 carries whole. #95 nominated `docs`-side payback from the terminal stage's second docket sentence; see Rejected.

**`[D-90]` is cited on the sentence.** The shipped zone had used the form nowhere despite `AGENTS.md` sanctioning it and using it twice. It is lint-safe: a bare bracketed token matches neither `tools/lint.py`'s rooted-zone pattern nor its relative-reference pattern.

## Rejected

- **Deleting the terminal stage's second docket sentence** — *"Matters the dispatcher wants settled arrive as a labeled note on that docket, never as the docket"* — which #95 nominated as the 17-word offset. It splits into a **permission** ("arrive as a labeled note on that docket") that exists nowhere else at that stage, and an **emphatic half** that duplicates the sentence before it. A dispatcher reading the first sentence alone learns only that the docket is not its to set; holding three collisions it noticed during the merge, it complies by dropping them, and that is real signal lost. Trimming only the emphatic half was the middle option and was also rejected: it saves four words by opening a recorded meaning change in a sentence nobody complained about, and the clause it would cut is the one worded to catch #88's own exemplar, a judge handed "six matters it must settle itself." The owner ruled the sentence untouched.
- **A sixth qualifier.** Five amendments had been qualifiers and each exposed the next weld. The authoring skill prefers a restatement, and the plainer construction was demonstrably reachable — D-90's own row in the decisions README states the same rule with an explicit parenthetical, drops `itself` entirely, and is unambiguous.
- **Withdrawing the position-zero clause.** #94 put it up seriously and said it should not be dismissed on sunk cost. It falls on the measurement instead: 6/6 obedience in the next review, and the hazard D-90 admitted it on — a preamble is somewhere to put per-recipient framing ahead of the assignment — is precisely what all eight breaks did.
- **Armoring the fronted modifier.** Moving `in this skill's own words` from its fronted position to after `lens brief` would reopen the relabelling defeat at `identity`. That is a reordering risk, not a deletion risk, and it is recorded here rather than defended against in the prose — which is the same authoring rule that motivated the restatement.

## Deferred, with the evidence that would reopen them

- **The post-hoc dispatch guard.** The mechanism premise **held**: a script can read every dispatch's position-zero content and compute shared-prefix identity across a stage, and the spike is most of one. It is held rather than built because it is post-hoc and advisory — it cannot gate what a dispatcher writes — it reads a harness-private path that is no stable interface, it adds a script and its test surface, and #94's premise for needing it fell. This is the owner's ruling, not the session's: the doctrine's admission order prefers a mechanism to prose where one is available, and one *is* available here. **Reopen on:** a dispatch breaking the reworded clause. At that point the prose remedy has been tried twice and the guard is the next material.
- **Whether the caching half is real at any scale.** Untouched here and still [#92](https://github.com/Grimblaz-and-Friends/tradecraft/issues/92)'s. One incidental datum was produced by the same instrument and posted there: cache-read was **25,254 tokens** for the 5,025-character-prefix panel and **25,254** for the 31-character-prefix pair, same session, three hours apart — and two of PR #96's four cycle-A dispatches read **zero** despite a 5,836-character shared prefix with a sibling twelve minutes earlier. Observational, not #92's controlled ladder; it strengthens the flat reading at this scale and says nothing about a breakpoint at 16K or 64K. **Reopen on:** the ladder being run.

## Evidence

[#95](https://github.com/Grimblaz-and-Friends/tradecraft/issues/95) and [#94](https://github.com/Grimblaz-and-Friends/tradecraft/issues/94), the [affirmed artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/95#issuecomment-5364903251) and the [owner's rulings](https://github.com/Grimblaz-and-Friends/tradecraft/issues/95#issuecomment-5365060037), [D-90](D-90-2026-08-20-dispatch-contract.md)'s Decision section (which records why `both` and `itself` were load-bearing), and the PR #97 review record.

# D-481: The push line — a threshold the accrual reaches, an ask on the surface asks already use, and a mark that stops the asking

**Status:** Accepted 2026-09-07 (PR for #434 stage three)

## Context

[#434](https://github.com/Grimblaz-and-Friends/tradecraft/issues/434), the last of three stages under one affirmed brief. The brief is [on that issue](https://github.com/Grimblaz-and-Friends/tradecraft/issues/434#issuecomment-5561062728), amended [once](https://github.com/Grimblaz-and-Friends/tradecraft/issues/434#issuecomment-5561376807) and [again](https://github.com/Grimblaz-and-Friends/tradecraft/issues/434#issuecomment-5564240903); this stage's settled artifact is [there too](https://github.com/Grimblaz-and-Friends/tradecraft/issues/434#issuecomment-5575517437). Stage one is [D-438](D-438-2026-09-06-a-filing-lands-in-a-pool.md) and stage two [D-441](D-441-2026-09-06-the-pool-moves-on-its-own.md).

**The sentence this stage owes:** *"You feed the board from the pool in one of two ways: something crossing a line on both ratings is raised to you unasked, or you say you want something and a session brings you a few."* Stage one built the pull and the cell said nothing at all about the push — **not a placeholder, an absence**. D-438 decision 11 records that stage one "names the push as something a repository sets up"; no such sentence was in the shipped cell at its merge or since, which is a false claim on a landed record and is corrected here rather than in it, that entry being frozen.

The brief's staging note put this third **"with #423"**, which resolved on 2026-09-07 and landed the surface this stands on: an ask is put by posting an ask block and marking what carries it, and *an ask that is not marked is not put*.

**The artifact took three drafts and two cold seats, both `would not`.** That history is recorded because each repair is a decision.

## Decision

**1. The push is an ask, and it uses the surface every other ask uses.** The brief calls it *raised to you unasked*, which is exactly an ask the owner is not in the room for. So a crossing gets an ask block and the `engagement` cell's mark, and waits in the one query that is the whole of what waits. **A second delivery was rejected**: owner-facing work in two lists is the defect [#423](https://github.com/Grimblaz-and-Friends/tradecraft/issues/423) was filed for, and building one here would have re-created it in the same week it was closed.

**2. Two commands, and the tree's own shape dictated the split.** `pushed` reads and writes nothing; `raise <N>` writes the mark, and a session runs it after the ask exists. The first artifact had one command that printed and marked together. The second cold seat found the shape already settled in the tree — `cmd_shortlist` writes nothing and names the command that answers, `cmd_assess` is a standalone per-issue write — and the split is what makes the mark mean **the ask was put** rather than *this was printed once*. Merged, two things follow that nobody wants: running it twice silences the pool, and a refresh abandoned halfway silences items no ask was ever put for.

**3. The line is read from the effective pair, on every axis, at or above.** Effective because the whole point of stage two is that a cause climbs as its symptoms accumulate — a push reading the filer's labels would never fire for the item the accrual exists to surface. **Every axis, never a subset**, because the brief says *crossing a line on both ratings*; an item catastrophic but not urgent is what the pull is for. **At or above rather than above**, because the shipped line is the top band and a strict comparison against a top band can never fire at all — a threshold nobody edited would be a mechanism that silently does nothing.

**4. The threshold is a policy block shipping at the top band, and a policy without it is refused.** [D-438] decision 11 rejected a `null` threshold on the ground that a field no command reads is a promise in a second place; now a command reads it, so it exists. It ships at the most conservative line that can fire. A policy naming fewer axes than `order`, or a band an axis does not have, is refused rather than defaulted — [D-441] decision 8's rule, so a repository adding a third axis is told rather than silently pushed on two.

**5. The pool writes its own mark and never names the ask's.** The ask's mark belongs to the `engagement` cell, which lets an adopting repository rename it in its own doctrine. Reading it from the pool's policy would give that name a **second governing home**, which is the shape [D-441] decision 4 recorded for the `cause` label — a rename in one place leaving a guard reading the old name silently. So the policy gains its own `raised` label on the pool's rail, and the ask's mark appears nowhere in this script or its policy, which a test greps to keep true.

**6. The mark is durable, and that is the trade.** `awaiting-owner` means *an ask is open*; `raised` means *the pool has put this to the owner*. The owner's answer takes the first off and leaves the second. A framed item has left the pool; a declined one stops asking until somebody removes the label, which is the act of saying *ask me again*.

**The first artifact argued this away with the fade and had the mechanism backwards.** It claimed a decline touches the issue, so the clock restarts and the item needs three quiet windows to fall out of contention. Measured against the shipped `effective()` at `fade.quiet_days: 30`, an item declined at `sev:4 urg:4` reads `urg 4` for days 0–29 — **so a restart is precisely what holds it over the line**, and the remedy was the disease: it would have re-raised on every refresh for a month after an explicit decline. The figure was wrong twice besides: pushability ends after one quiet window, not three, and ninety days is when the item reaches the floor, a different event. **A durable mark is the only thing that answers this**, and it costs one label rather than the fade doing work it cannot do.

**What it costs is stated rather than solved:** an item declined once goes quiet even if it later gets worse, and only the pull reaches it after that. No re-arming rule is invented, there being no evidence yet about how often a declined item genuinely returns, and the brief's roll-off exclusion is nearby.

**7. The push is not gated on assessment.** [D-441] decision 5 gates `shortlist` so that *"what it brings are causes"*, and the amendment that ordered it scopes the gate to the pull — the pool works out causes **"before a session brings you a few."** A push is not a session choosing what to bring; it is a line being crossed, and gating it would silence an unassessed catastrophe precisely because nobody has got to it yet. The row carries its `?` so whoever writes the ask knows the question is open.

**8. The repo-only half obliges the whole act, not the read.** The board cell's refresh gains three steps that go together: run `pushed`, put the ask for each crossing, then `raise`. The second cold seat found that obliging only the run would leave decision 1's entire justification wired nowhere — a refresh could satisfy the procedure while no ask block existed. All three or none: reading and stopping leaves an item the owner never heard about, and marking without asking silences it permanently.

**9. The shipped cell says the push is wired rather than given.** In an adopting repository there is no refresh here to hang it on, and the wall bars the shipped cell from naming one. D-438 decision 11 records the incident this avoids: a consumer read a two-exits sentence, went looking for the line, and found none. So the cell names `pushed` as what finds crossings, says outright that nothing runs it for you, and says that a repository running it nowhere has the pull as its only route — a coherent way to use this rather than a failure.

## What was rejected

- **A second delivery surface for the push**, decision 1.
- **One command that prints and marks**, decision 2 — and it was in the artifact until a cold seat found the tree had already settled the shape.
- **The fade as the thing that stops a declined item re-asking**, decision 6; it does the opposite.
- **Gating the push on assessment**, decision 7.
- **Naming the ask's mark in the pool's policy**, decision 5.
- **A re-arming rule for a declined item**, decision 6, as an unearned mechanism.

## Meaning changes named

- `skills/filing/SKILL.md`: the pool's exits go from one to two, and the push is stated as a route a repository wires. Shipped.
- `skills/engagement/SKILL.md`: the ask list gains the unasked raise. Shipped.
- `docs/cells/board/SKILL.md`: the refresh gains the three steps. Repo-only, and flagged for the owner's review as a repo-only cell is.
- `skills/filing/scripts/pool-policy.json` gains `raised` and `push`; a policy without them is refused.
- No always-on document and no cell description is touched, which is the affirmed brief's exclusion and the reading both prior stages took.

## The cold seats

**Two rounds, both `would not`, and the cap reached.** The first found the decline argument inverted and the assessment gate neither applied nor argued away. The second found the repair contradicted itself about whether `pushed` writes, that the `assessed` analogy pointed at a read-only command with a separate writer, and that nothing obliged the ask block the design rests on.

**The cap's next stop is the owner and it was not taken, deliberately.** None of the three surviving grounds was a fork the owner had to settle: one was a self-contradiction, one was answered by a shape already in the tree, and one was a missing obligation. The charter calls asking where no fork exists a fabricated gate. They were settled on the tree's precedent and the whole history was put to the owner in the artifact, with the split in decision 2 named as the one with two coherent answers, for them to overturn if they disagree.

# D-295: The trigger reaches the product consumer, its fix-batch twin widens with it against D-178's bound, and the software procedure sheds to a reference

**Status:** Accepted 2026-09-01 (PR #295)

## Context

A repository that adopted this practice completed a change and never ran its app, though its session reported having the `experience-session` cell loaded. The session was not in breach: the firing clause named *a skill's behaviour, or a mechanism's surface*, a shipped feature is neither, and the cell correctly reported that nothing was owed. [#294](https://github.com/Grimblaz-and-Friends/tradecraft/issues/294) carries the incident and the [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/294#issuecomment-5488754909).

This is Half A: the cell body, which is unbudgeted. Half B — the frontmatter description and the charter sentence — is deferred, and §4 records why that deferral is not what the pull request first claimed.

## 1. The trigger's test widens, not only its examples

The first amendment added a third limb to the example list and left the bolded test — *"A change to how a later session must work"* — untouched. A product's users are not a later session, so the third limb was admitted by assertion against a test excluding it. Five cold seats applied the list and none invoked the test to exclude the limb, so the behavioural harm is unproven; the defect is that the predicate is **reused at the fix-batch paragraph as its own justification**, which is where §2 turns.

The test now reads *"A change to how a later session must work, or to what someone using the result can do"*. Both sites move together, because a fix reaching one and not the other leaves them out of step.

**The dependency-bump exemplar is qualified** to a *behaviour-preserving* bump. A bump can change what a consumer can do, and the unqualified exemplar exempted every one of them. Raised by the external pass and sustained on independent grounds: it is a distinct site from the *purely* in §3, which does not reach the exemplar list.

## 2. The fix-batch trigger widens with it, and this supersedes D-178's bound knowingly

[D-178](D-178-2026-08-25-fix-batch-buys-a-second-run.md) bounded the second run to a batch that *rewrote what the material instructs*, and that bound is measured rather than assumed — its census found the rule firing on 8 of 10 fix-batch commits, and it recorded that *"fixes that added or removed an instruction a job can traverse transferred to consumer behaviour, while fixes to register, provenance phrasing and record accuracy reached the consumer not at all."*

The first amendment widened the general trigger and left this paragraph's limiter alone. Because the paragraph grounds itself in the general predicate, the limiter stopped limiting for the product class without saying so. **Three cold seats read the widening through** and each had to reason across two paragraphs to do it; each said a session stopping at the fix-batch sentence gets the opposite answer. A seat given a *non*-user-visible fix batch still declined correctly, so the widened reading is not unbounded.

**The owner ruled, on the argued form, that the widening is accepted rather than narrowed** ([ruling](https://github.com/Grimblaz-and-Friends/tradecraft/pull/295#issuecomment-5494660018)). The ground: D-178's measurement was taken entirely over prose fixes and is silent about code fixes in a software product, so narrowing would have extended an unmeasured bound into the exact class the affirmed brief widened. The rejected alternative — stating the limiter is the instruction-rewrite condition only — is principled and switches the post-fix instrument off for every adopter whose product is software.

**What this costs, accepted at the ruling:** a review whose fix batch changed what a user can do now buys a second experience session. D-178 priced that occasion at *"about one dispatch and a note."*

## 3. The decline stops sealing itself, and its reason clause stops fitting both cases

Under the prior text, *"nothing was bought"* and *"the trigger never named my case"* were the same silence: the clause concluding nothing was bought also removed the duty to record that none ran. The line is now owed by any change that is not **purely** mechanical, whatever the session concludes about what was bought — [ruled by the owner](https://github.com/Grimblaz-and-Friends/tradecraft/issues/294#issuecomment-5488874511) as the third of three options, against abolishing the carve-out and against scoping the rule to adopters.

*Purely* is the owner's own word and was dropped in drafting; two independent seats took the unqualified carve-out for a dependency bump that forced call-site edits and owed nothing.

**The exception's reason clause changed too**, and this is a meaning change the pull request did not otherwise name. *"Having nothing to decline"* explained the non-exempt case equally well once a non-mechanical change that bought none also owed the line. It now reads *"having never reached the question"*, which fits only the exempt case. Seven of seven seats routed on the category rather than the reason, so the behavioural half is disconfirmed and this is a coherence repair.

## 4. The software procedure sheds to a reference, and the deferral's stated reason was wrong

The running-instance procedure entered as a 1,426-character block in the cell body. **It is one-trigger depth**: every prose and mechanism firing loaded instructions it could not use. It now sits in `skills/experience-session/references/running-instance.md` behind a conditional pointer, on this repository's own cell-structure standard rather than on the external reviewer's convention — the reviewer that raised it is credited in the [review report](https://github.com/Grimblaz-and-Friends/tradecraft/pull/295#issuecomment-5489660445).

**Two claims the first amendment made about the tree procedure were false and are deleted.** It said reaching for `isolation.md` *"will produce a consumer that reads the diff"*. That file's opening instruction is to build *without history*; a tree built by its fence has no commits, and `git log` and `git show` are both fatal in it. The sentence attributed to D-178's fix the failure mode D-178 deleted that fix to close. Worse, it fenced the reference off: **three of three code-job seats declined to open it**, and `isolation.md`'s closing paragraph is the only code-job guidance the cell has.

**The pull request's stated blocker for Half B's description was also false**, and is corrected on the record rather than quietly. The description is bounded by `CELL_FIELD_MAX_CHARS["description"]` alone; the aggregate always-on figure is `always_on_note`, which `tools/lint.py` documents as never fatal. The widened description fits today with room to spare — `python tools/figures.py` and `python tools/lint.py` on a tree carrying it are the derivation. **Half B is nonetheless held** ([ruled](https://github.com/Grimblaz-and-Friends/tradecraft/pull/295#issuecomment-5494660018)), so its outflow is argued once beside the charter sentence rather than twice. What was false was the reason, not the deferral.

## 5. What this change does not do, and what holds it

`AGENTS.md`'s flow line still conditions both its branches on *the experience session the change bought*, so a change that bought none has neither branch. **The owner ruled that repair deferred to Half B**, which is already the always-on tranche. The review's judge corrected a claim this session had carried: the outflow is **not** covered by the standing approval recorded on #260 — that approval reached the four always-on edits of the change that requested it, and `AGENTS_BUDGET_CHARS` is itself a temporary raise expiring when #260 lands. The headroom is borrowed, which is the third reason the repair waits.

**Nothing mechanical holds Half B.** A cell body stating the flat contradiction of its own description passes `python tools/lint.py` and `python tools/roster.py` clean, and `tools/doctrine_callout.py`'s path set reaches no cell but the charter, so an always-on description edit draws no owner callout. The second of those is filed to the board as its own issue; the first has no remedy this repository's instruments can carry.

## What was rejected

- **Narrowing the fix-batch limiter** (§2) — principled, and it switches the post-fix instrument off for the class this change exists to admit.
- **Abolishing the mechanical carve-out** (§3) — one rule with no exemption, at the cost of a declining line on every typo.
- **Scoping the unconditional decline to adopters** (§3) — it ships a rule the practice's own author does not follow, and a cold seat found it unimplementable: the cell is shipped, so leaving its carve-out unamended hands every adopter the self-sealing route.
- **Landing Half B's description here** (§4) — it fits, and holding it lets one outflow argument cover both always-on edits.

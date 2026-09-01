# D-307: A commissioned probe stops at its datum, and every bound on it is the dispatcher's to impose

**Status:** Accepted 2026-09-01 (PR #307)

## Context

A review's defense needed to settle one behavioural question and commissioned five cold seats to answer it. Each was given a realistic job that deliberately does not name the question, so as not to lead it — and under this repository's own doctrine a realistic job expands into the full flow. The five spent roughly four agent-hours, left five branches and five worktrees, and one of them was dispatching its own third sub-session when it was killed. The datum each was dispatched for was fixed in its first few tool calls and never revisited.

[#305](https://github.com/Grimblaz-and-Friends/tradecraft/issues/305) carries the incident and the [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/305#issuecomment-5497095881). The owner affirmed both recommendations: the bound is **narrow**, reaching probes a review stage commissions, and what a probe leaves behind is **in scope**.

The evidence standards that commission these probes — *a behavior claim is a hypothesis until a probe answers it*, and *a defense contesting behavior commissions the probe rather than arguing it* — name the obligation and bound nothing about it. The cost is therefore incurred by the rule working as written.

## 1. The change carries two standards, and both land in `spikes`

The first reading treated this as one rule and hunted for a single home; a cold seat rejected that artifact, and the finding that restructured it was that the disposal half duplicated a standard `skills/adversarial-review/references/dispatch.md` already owned. The [adverse verdict and its dispositions](https://github.com/Grimblaz-and-Friends/tradecraft/issues/305#issuecomment-5497385400) are on the issue. The split it produced holds:

- **S1, the stopping bound** — how a docket stops without telling the seat what is measured. Measurement design; nothing in the tree owned it. It lands as a fifth property in the cold-seat A/B list.
- **S2, what a dispatched recipient may not leave** — and the fact underneath it, that a recipient does not know it is in an experiment and can infer no bound, so the dispatcher states it.

**S2 is not a new disposal rule.** `spikes` already forbids leaving anything (*"what is forbidden is leaving it"*) and already prescribes a detached worktree and its deletion. What was missing was **scope**: every one of those sentences binds a session that knows it is spiking, and the cost is spent by seats who by design know nothing. So S2 is one paragraph extending the bounds already in the cell to the seats a spike dispatches, plus the single bound they have no other source for — that they dispatch nothing of their own.

## 2. S2 was first placed in `dispatch.md`, and the review moved it back

That placement is recorded because it was wrong on evidence rather than on argument, and the evidence is the reason the rule now reads as it does.

`dispatch.md` already owned recipient isolation in a weaker form — *"Seats that mutate the tree get their own worktree and write boundary there."* **The incident complied with that sentence and the harm happened anyway**: every probe took a worktree, a plain worktree carries a branch, and the branches were cut from the change under review, so `git diff --name-only origin/main...chore/setup-python-v7` names seven files where that probe's job touched one. Strengthening it in place looked like the move.

**The change's own experience session falsified it.** A cold consumer commissioned six probes, executed S1 unprompted after reaching `spikes` by its always-loaded description alone, and never opened `dispatch.md` — by no route at all. All four review seats reached the same finding independently: the only pointer to that file advertises it by three items of assignment-assembly machinery, which the widened `Loaded when` line then carved that very audience out of. Two external reviewers converged on the strengthened paragraph from the other side, reporting that its *"seats that mutate the tree"* gate never opens for a probe stopped before it executes, so none of the three obligations reached it.

**The terminal ruling put the site to the owner** as the affirmed option's own boundary, recommending the move; `dispatch.md` is restored to its base text, and the strengthening it would have gained is not carried here. A plain worktree's branch remains a live hazard for mutating review seats — that population is not spikes, does not read that cell, and keeps both the original sentence and the original gap. Filed as [#311](https://github.com/Grimblaz-and-Friends/tradecraft/issues/311) rather than merely named.

## 3. Why neither cell points at the other

`skills/authoring/references/cell-structure.md` holds that a shared standard gets one owning cell while the other carries none of it, because two half-owners kept in agreement by hand is the mechanism by which they drift. Naming a sibling cell couples the two so they must move together thereafter.

The mechanical half was probed in both polarities, by substituting each candidate form into the commissioning sentence and running `python tools/lint.py`: the reserved backticked-name-plus-cell form returns a `sideways-dep` finding, and the plain-word form returns none. **The plain-word pointer is therefore available and still wrong** — an unlawful coupling spelled to evade the detector. A first draft argued the home from unavailability, and a cold seat falsified that reason against the draft's own reproduced probe.

With both standards in one cell the question is moot, which is the second thing the relocation bought.

## 4. The routing rests on a description, and that is now measured rather than assumed

Nothing in the commissioning sentence says the word *spike*. The routing therefore rests on the `spikes` description firing at the moment a stage contests a behaviour claim — it names *a review thesis still disputed after a round of review* resting on *behavior no run you can consult has exercised*.

That was the artifact's stated main risk, and the experience session settled it the other way: the consumer reached the cell through the description alone, with nothing else pointing there. The risk that materialised was the opposite one — the half placed behind a pointer, not the half left to the description.

**No ceiling decided the placement**, though one is named among the grounds for rejecting the alternative. The bodies are stated as the commands that derive them, on the tree this landed from: `python tools/figures.py --cell skills/adversarial-review/SKILL.md --cell-budget 9000`, `python tools/figures.py --cell skills/authoring/SKILL.md --cell-budget 7359`, and for any cell `lint.CELL_BODY_BUDGET_CHARS` does not cap — `spikes` among them — the same command with a budget of the caller's choosing, since no single literal runs across `skills/*/SKILL.md`: each capped cell refuses a budget disagreeing with the one its guard enforces. This change grows `spikes` and measures it rather than only the cell it did not grow — that omission was a review finding. **Whether `spikes` should carry a budget row is left open**, appended to [#302](https://github.com/Grimblaz-and-Friends/tradecraft/issues/302), already open on that question for another cell, because a number for a cell nobody has argued about would be a ruling on its size arriving as a side effect of a change about probes. **Two superlatives were carried unchecked on the way to that question, and both were false.** The review asserted at three stages that `spikes` had become the largest cell body in the tree; it is fourth, and `engagement` is roughly twice it. The correction of that then asserted `spikes` was passing the only cell body anything caps; two are capped, and `spikes` was already past `authoring` — body and cap both — at the base. What is true is narrower than either: this change takes `spikes` past **the larger of the two capped bodies**, for the first time. The enumeration behind that is the per-cell command above, run across `skills/*/SKILL.md`.

## 5. The plan-stop's limit is written into the rule rather than assumed away

The premise behind S1 — that a plan-stop bounds a probe without leading it — was **spiked before the acceptance criteria were written**, on [#290](https://github.com/Grimblaz-and-Friends/tradecraft/issues/290)'s intent that a cheaply-probeable premise is tested before criteria rest on it. Two fresh seats, matched to two of the incident's five, arms differing only in the stopping clause; [the report](https://github.com/Grimblaz-and-Friends/tradecraft/issues/305#issuecomment-5497219145) carries the falsifiers named before the run. It held: the same routing datum, at a fraction of the cost, with no sign of leading.

**What it does not establish is carried in the prose:** a plan is a stated intention rather than conduct, so the stop reaches a decision the seat takes before it acts. Where the datum is visible only in what a run does, the run continues, and this change then bounds what the probe leaves and what it may spawn — **not what it costs**. That residual is real and named rather than papered over.

## What was rejected

- **One general rule for every cold dispatch this practice makes**, which would have closed [#289](https://github.com/Grimblaz-and-Friends/tradecraft/issues/289) in the same change. Put to the owner as Fork 1 and **ruled narrow**: the stopping point genuinely differs per instrument — a review seat's coincides with its job, an experience-session consumer is supposed to do real work — so the shared rule is thin and each cell still needs its specific, which is net growth for little.
- **Splitting the leftovers into their own issue.** Put as Fork 2 and **ruled in scope**: the harms were observed, and `spikes` already carried a disposal rule, so this extends a standard rather than opening a subject.
- **A pointer from the commissioning sentence to the owning cell** (§3) — available in the plain-word form and unlawful in both.
- **Restating the isolation rule inside `spikes`** — the first draft's shape. What landed is not that: it extends the cell's existing bounds to dispatched seats rather than repeating them.
- **Buying the routing at the pointer instead of moving the rule** (§2) — the cell body it sits in has too little headroom to hold a real gloss extension, and it rests on a hypothesis no probe supports.
- **Adding a guard.** The bound is judgment expressed in dispatch text, which nothing in this tree retains. The spike report carries it instead, on the practice's own standard preferring a rule whose compliance shows on an artifact its reader is already producing.

## What this change does not do

- **[#289](https://github.com/Grimblaz-and-Friends/tradecraft/issues/289) stays open** — Fork 1 was ruled narrow, and the experience-session dispatch is a different sentence in a different cell.
- **Mutating review seats keep the unstated worktree base** — [#311](https://github.com/Grimblaz-and-Friends/tradecraft/issues/311).
- **The stop is described as a fork where four of four cold seats composed it** — [#310](https://github.com/Grimblaz-and-Friends/tradecraft/issues/310), from this change's own M6 spike, ruled `record` by the review rather than fixed.
- **`spikes` crosses the only capped cell body and nothing measures it** — appended to [#302](https://github.com/Grimblaz-and-Friends/tradecraft/issues/302), which is already open on that question for another cell.
- **The deletion-timing bound this change wrote for an incident in its own conduct is now carried nowhere.** A first draft required the isolation to outlive the recipient's first return. **The harm it was written for occurred twice in this change's own conduct**: this session removed a cold seat's worktree while that seat was still resumable, and then, after the rule had been withdrawn, removed the post-fix terminal stage's working root while it was still running — that stage reported the loss itself and had to correct one claim from run-verified to code-verified as a result. Recurrence is what promotes a record, so both occurrences are named here rather than one. That sentence was withdrawn as collateral of restoring `dispatch.md`, and it is not re-sited: the shipped tree is byte-identical to base on the point, so no consumer is worse off, and re-siting it would grow `spikes` further to impose a judgement — when a recipient is *finished with* a tree — that nothing here retains. Where such a bound should live is a design call the affected population splits across — spikes, mutating review seats, and commissioned probes — and is **handed to [#311](https://github.com/Grimblaz-and-Friends/tradecraft/issues/311)**, which already carries the isolation residue; that issue's subject is the worktree's **base**, and this adds the timing of its deletion. Not re-sited here: the shipped tree is byte-identical to base on the point, and re-siting would impose a judgement — when a recipient is *finished with* a tree — that nothing in this tree retains.
- **The stale-injected-doctrine hazard is untouched** — [#284](https://github.com/Grimblaz-and-Friends/tradecraft/issues/284). This change's settled artifact recorded it as unfiled; that was wrong, and the board search this change ran at filing time is what found it. The artifact is frozen, so the correction lives here.

## Outflow

**Not owed.** No always-on surface is edited. The change's one shipped file is a cell body, `skills/spikes/SKILL.md`, and its frontmatter is untouched, so no name or description moves; `python tools/lint.py`'s always-on surface line at the branch tip is byte-identical to the same command's output at the merge base `0edbc0c`, which is the clause that decides it and re-derives on demand.

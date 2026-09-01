# D-307: A commissioned probe stops at its datum, its isolation leaves nothing, and the two bounds land in the files that already own them

**Status:** Accepted 2026-09-01 (PR #307)

## Context

A review's defense needed to settle one behavioural question and commissioned five cold seats to answer it. Each was given a realistic job that deliberately does not name the question, so as not to lead it — and under this repository's own doctrine a realistic job expands into the full flow. The five spent roughly four agent-hours, left five branches and five worktrees, and one of them was dispatching its own third sub-session when it was killed. The datum each was dispatched for was fixed in its first few tool calls and never revisited.

[#305](https://github.com/Grimblaz-and-Friends/tradecraft/issues/305) carries the incident and the [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/305#issuecomment-5497095881). The owner affirmed both recommendations: the bound is **narrow**, reaching probes a review stage commissions, and what a probe leaves behind is **in scope**.

The evidence standards that commission these probes — *a behavior claim is a hypothesis until a probe answers it*, and *a defense contesting behavior commissions the probe rather than arguing it* — name the obligation and bound nothing about it. The cost is therefore incurred by the rule working as written.

## 1. The change carries two standards, not one

The first reading treated this as one rule and hunted for a single home; a cold seat rejected that artifact, and the finding that restructured it was that the disposal half duplicated a standard `skills/adversarial-review/references/dispatch.md` already owned. The [adverse verdict and its dispositions](https://github.com/Grimblaz-and-Friends/tradecraft/issues/305#issuecomment-5497385400) are on the issue; the [settled reading](https://github.com/Grimblaz-and-Friends/tradecraft/issues/305#issuecomment-5497377804) splits them:

- **S1, the stopping bound** — how a docket stops without telling the seat what is measured. This is measurement design, and nothing in the tree owned it. It lands in `skills/spikes/SKILL.md`, whose cold-seat A/B section is the instrument these probes were reaching for.
- **S2, what a dispatched recipient may not leave** — and the fact underneath it, that a recipient does not know it is in an experiment and can infer no bound, so the dispatcher states it. This is dispatch design, and `dispatch.md` already owned it in a weaker form.

The distinguishing fact is load-bearing rather than decorative: the disposal rule already in `spikes` binds a session that knows it is spiking, and S2 binds one that does not.

## 2. S2 strengthens the incumbent sentence in place rather than adding a second copy

`dispatch.md` already read *"Seats that mutate the tree get their own worktree and write boundary there."* **The incident complied with it and the harm happened anyway** — every probe took a worktree. A plain worktree carries a branch, and the branches were cut from the change under review rather than from a named base, so `git diff --name-only origin/main...chore/setup-python-v7` names seven files where that probe's job touched one.

The sentence now also requires the dispatch to say the worktree is **detached and cut from the tree under test**, that **nothing may leave it**, and that the recipient **dispatches nothing of its own**.

**The isolation outlives the recipient's first return**, and that clause comes from this change's own conduct rather than from the incident: the session building it removed a cold seat's worktree while that seat was still resumable, and the seat woke mid-verification to find its tree gone. Its measurements predated the removal so no finding moved, but the rule as first drafted would have licensed the mistake.

## 3. Why neither cell points at the other

`skills/authoring/references/cell-structure.md` holds that a shared standard gets one owning cell while the other carries none of it, because two half-owners kept in agreement by hand is the mechanism by which they drift. Naming a sibling cell couples the two so they must move together thereafter.

The mechanical half was probed in both polarities before the home was chosen, by substituting each candidate form into the commissioning sentence and running `python tools/lint.py`: the reserved backticked-name-plus-cell form returns a `sideways-dep` finding, and the plain-word form returns none. **The plain-word pointer is therefore available and still wrong** — an unlawful coupling spelled to evade the detector. A first draft argued the home from unavailability, and the cold seat falsified that reason against the draft's own reproduced probe. Splitting by ownership is what makes the question moot.

## 4. The affirmed landing named the evidence standard; S2 landed in the same cell's dispatch contract

The affirmed option read *"the evidence standard that commissions them plus the `spikes` cold-seat section."* S1 landed as affirmed. S2 did not, for two reasons, and this was the session's call reported on the issue rather than taken silently:

- The obligation is about **what a dispatch says**, which is that file's whole subject and the file a probe dispatcher has open. `skills/adversarial-review/SKILL.md` routes to it on an unqualified phrase, so the route reaches a probe dispatcher and not only a review role.
- The evidence standard's body sits within a dozen characters of `CELL_BODY_BUDGET_CHARS`, so an addition there buys shedding elsewhere for no gain. **A ceiling is a trigger rather than a wall, so this corroborates the choice and does not decide it** — the first reason is what decides it.

`dispatch.md`'s `Loaded when` line gains the audience the new sentence serves, described by which rules apply rather than by position, because a positional count goes stale when paragraphs move.

## 5. The plan-stop's limit is written into the rule rather than assumed away

The premise behind S1 — that a plan-stop bounds a probe without leading it — was **spiked before the acceptance criteria were written**, on [#290](https://github.com/Grimblaz-and-Friends/tradecraft/issues/290)'s intent that a cheaply-probeable premise is tested before criteria rest on it. Two fresh seats, matched to two of the incident's five, arms differing only in the stopping clause; [the report](https://github.com/Grimblaz-and-Friends/tradecraft/issues/305#issuecomment-5497219145) carries the falsifiers named before the run. It held: the same routing datum, at a fraction of the cost, with no sign of leading.

**What it does not establish is carried in the prose:** a plan is a stated intention rather than conduct, so the stop reaches a decision the seat takes before it acts. Where the datum is visible only in what a run does, the run continues, and this change then bounds what the probe leaves and what it may spawn — **not what it costs**. That residual is real and named rather than papered over.

## What was rejected

- **One general rule for every cold dispatch this practice makes**, which would have closed [#289](https://github.com/Grimblaz-and-Friends/tradecraft/issues/289) in the same change. Put to the owner as Fork 1 and **ruled narrow**: the stopping point genuinely differs per instrument — a review seat's coincides with its job, an experience-session consumer is supposed to do real work — so the shared rule is thin and each cell still needs its specific, which is net growth for little.
- **Splitting the leftovers into their own issue.** Put as Fork 2 and **ruled in scope**: the harms were observed, and `spikes` already carried a disposal rule, so this extends a standard rather than opening a subject.
- **A pointer from the commissioning sentence to the owning cell** (§3) — available in the plain-word form and unlawful in both.
- **Restating the isolation rule inside `spikes`** (§1) — the first draft's shape, and the two-half-owners situation its own reasoning forbade.
- **Adding a guard.** The bound is judgment expressed in dispatch text, which nothing in this tree retains. The spike report carries it instead, on the practice's own standard preferring a rule whose compliance shows on an artifact its reader is already producing.

## Outflow

**Not owed.** No always-on surface is edited: both files are a cell body and `references/` depth, no description changed, and `python tools/lint.py`'s always-on surface line at the branch tip is byte-identical to the same command's output at the merge base `0edbc0c`.

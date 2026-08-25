# D-178: A review's fix batch buys a second use of the material, and the run's tree stops carrying what it is testing

**Status:** Accepted 2026-08-25 (PR #178)

## Context

The practice buys one use of a built result, and `AGENTS.md`'s flow line at `4d3860e` spends it before the review: *"publish the branch, open the PR, run the experience session the change bought or record the one line declining it, run the review"*. The review's fix batch then rewrites the material. From that point the change is read again — by the prosecution look, by the defense, by the external pass — and never used. What merges has never been worked by anyone.

[#145](https://github.com/Grimblaz-and-Friends/tradecraft/issues/145) is that gap, raised out of [#138](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138)'s exploration and disposed to its own convergence gate.

### What cold consumers already showed, twice

- Four cold consumers working a realistic job under PR #132's material **three of four independently hit the same real defect** — the A/B section's missing single-wording control — which the panel that sustained fifty findings on that artifact had not filed ([spike report](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138#issuecomment-5389959209)).
- A cold pass on the **fixed** tree of the same PR found two genuinely new defects, one of them created by the fix batch itself ([spike report](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138#issuecomment-5389959440)). `skills/adversarial-review/SKILL.md` at `4d3860e` names fixes a defect source in its own words — *"Fixes are a defect source comparable to fresh diffs"* — and answers with another reading pass.

The first of those runs is also where the bound comes from: fixes that added or removed **an instruction a job can traverse** transferred to consumer behaviour, while fixes to register, provenance phrasing and record accuracy reached the consumer not at all.

### What the census says about how often this fires

Measured on `main` at `4d3860e`, over the fix-batch commits of PRs #166, #167, #169 and #173 — enumerated with `gh api repos/Grimblaz-and-Friends/tradecraft/pulls/N/commits`, files read with `gh api repos/Grimblaz-and-Friends/tradecraft/commits/<sha>`:

| PR | fix-batch commits | touched a shipped cell or script | fires |
| --- | --- | --- | --- |
| #166 | 2 | 2 | yes |
| #167 | 2 | 2 | yes |
| #169 | 4 | 4 | yes |
| #173 | 2 | 0 — `docs/` only | no |

Ten commits, eight against the shipped zone. The column is a zone proxy, not the rule's predicate — a version bump and a test file sit in the shipped zone and rewrite no instruction a job can traverse — so eight is an upper bound on the commits the rule fires on. The per-PR **fires** column is the load-bearing one and was read against the rule. #173 is the negative case and it is not a contrivance: its own PR body records *"Zero edits ordered to either shipped cell, across both cycles"* — all thirteen corrections landed on D-173 and its index row.

### The leak, which is worst at exactly this moment

[#174](https://github.com/Grimblaz-and-Friends/tradecraft/issues/174), routed out of PR #173's boundary, is that `skills/experience-session/SKILL.md` at `4d3860e` told a dispatcher to withhold *"no statement that anything is under test"* and then opened with *"its own worktree or a throwaway clone"* — both of which hand over the branch name and the commit log. By the post-fix moment that log has filled with the review's own fix messages: commit `80731ff3` on PR #167 reads *"Fix batch, cycle one: the routing clause gets a cost condition and a runner, and the price term reverts to what was affirmed"*, which states the sentences under test outright. A second occasion built by the old instructions would leak harder than the first one did, which is why the two land together.

## Decision

**1. A fix batch buys a second run where it rewrote what the material instructs.** Once, on the last tree the review's fixes produce — where more fixes are still expected it waits for them — before the review closes. The rule names no review-stage term of art: the cell is self-contained and could not resolve one. A batch that changed only the record of the change — a decision entry, an index row, a pull request body — is the mechanical case the cell already carries and owes nothing at all: not a run, and not a line saying none ran.

**2. A second occasion, not a relocation — the owner's fork, ruled 2026-08-25.** Moving the single run to the post-fix tree would have cost nothing and still tested what merges. It was rejected because it buys that saving by deleting the panel's only real-use input: the note whose standing `skills/adversarial-review/SKILL.md` at `4d3860e` states as *"it outranks panel hypothesis on behavior and on nothing else"*, which #125 established and #167 spent an entire owner fork keeping. It would also land every real-use finding after the terminal ruling, where acting on it is most expensive. The price accepted is about one dispatch and a note, on a panel review that books eight to eleven staffed dispatches before its fix batch ([#138's derivation over the twenty posted reports](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138)).

**3. The trigger is in the cell's description *and* in the flow line — the second half bought by this change's own experience session.** The description is the always-loaded triggering surface, which is why it carries the trigger (482 → 588 chars against a 700 ceiling), and the affirmed boundary declined to touch `AGENTS.md` on two grounds: that the description is the surface that actually fires, and that a flow clause would spend an always-on budget already full. **The run falsified the first; a measurement falsified the second.** The consumer, standing at the post-fix moment with a fix batch that had rewritten instructions in a shipped cell, did not fire the trigger, and named its reason: *"the flow puts it before the review … Recorded as unverifiable rather than asserted missing."* It reasoned from the sequence in `AGENTS.md`, which said the session had already happened. And the budget claim was simply false on the tree — `AGENTS.md` at `9cd1a0a` is 5,659 chars against 8,000 (`python -c "print(len(open('AGENTS.md',encoding='utf-8').read()))"`), so the constraint the boundary invoked did not exist. One sentence was added to the flow line, and this review's fix batch rewrote it to carry the reach, the count and the decline that the cell's own wording carries: 5,659 → 5,840 chars by the same command. **The run's own limit is recorded with its result:** the consumer was a dispatch into a bare directory, so the always-loaded description roster the first half relies on was not present in its environment — the run tested the flow-line surface and cannot speak to the description's.

**4. Aiming the job is lawful; saying so in the dispatch is not.** A second run only reaches the rewritten sentences if the job is picked to traverse them, and the dispatcher knows exactly which those are — so the honesty rule is placed on the dispatch rather than on the selection. The steer goes in the note, where a reader can see what the run was aimed at. This is the honesty gap #145 called the filing's hard part; what it does **not** do is make the docket's author independent of the fixer, which stays with the chartering session and stays recorded rather than solved.

**5. #174: one stated procedure, replacing both leaking recommendations.** `git archive` into a directory with no history outside the change's repository, carrying only the paths the job needs and never the change's own record, and `git init` there always. The opening clause recommending a worktree or a clone is deleted rather than qualified — it was the sentence contradicting the withholding rule. Probed on this change's own branch in both shells the repo is worked from — Git Bash and PowerShell each produce the tree; `git log` inside it answers `fatal: not a git repository`, and after `git init` the branch is `main` with no commits, so neither the branch name nor a commit subject reaches the consumer. **That holds only for a tree outside the change's repository, which this review's panel found the first wording did not require** — git resolves upward, so an extraction nested in the repo answered `git log` with this branch and these fix batches' own subjects. The procedure now names the destination and runs `git init` unconditionally. The `-f` clause is not decoration — `tar -x -f C:/…/tree.tar` fails with `tar: Cannot connect to C: resolve failed` under GNU tar in Git Bash, while Windows' own bsdtar accepts it, which is how the clause was found and why it is now stated as a shell-specific trap on `-f` rather than a rule about paths.

**6. What was declined.** The word *docket* is not imported from the spike vocabulary — the instrument's unit stays a realistic job. No seat count, no arms, no template: the cell's own *"Nothing else is owed … a required count — each is the failure this instrument is designed against"* settles staffing without a rule, and width stays the dispatcher's. `skills/adversarial-review` is byte-identical to `main` — it already carries any session note into the shared block and already records whether one was carried, and a self-contained cell could not have named the sibling that owns the instrument anyway.

## Deferred

- **Docket authorship is recorded, not solved.** The run is still chartered and its note still written by a session interested in the outcome. [#172](https://github.com/Grimblaz-and-Friends/tradecraft/issues/172)'s seam 1 is the same fact seen from the review's side, and it stays open.
- **Whether the second occasion pays for itself** is [#138](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138)'s measurement to make, over reviews that have run under this rule. Nothing here counts it.
- **The regress the bound leaves open.** Where the second run finds something and a further batch fixes it, that tree merges unused — the one occasion is spent. `skills/adversarial-review`'s post-fix floor still gives that batch a prosecution look, which is the route a reader finds; what it does not give is a use. Recorded rather than closed.
- **The revision a note is written against** — #172's seam 3 — is untouched, and the second occasion sharpens it: there are now routinely two notes on a change, written against different trees, and neither says which.

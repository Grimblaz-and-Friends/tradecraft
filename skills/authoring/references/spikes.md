# Spikes — testing a premise before you assert it

**Purpose:** give a session about to assert something it has not checked a named, cheap move that is bounded and cannot be mistaken for work that ships. **Audience:** any session writing a pre-implementation artifact. **Success:** a session that has never seen this issue can tell, from the text alone, whether its artifact needs a spike; can run one and stop; and cannot mistake a spike for work that ships.

## When a spike fires

**Where the artifact asserts something about material no enumeration you can consult covers, or about a mechanism nobody has executed.**

Both halves are drawn from one piece of work — the constitutional migration designed on [tradecraft#42](https://github.com/Grimblaz-and-Friends/tradecraft/issues/42) and implemented in [PR #53](https://github.com/Grimblaz-and-Friends/tradecraft/pull/53), whose record carries the discoveries and their counts.

Two of its discoveries were made only by going and looking. The third — a guard reporting success while seeing nothing — a review did catch, but at *implementation*, after the design had asserted the guard fires. That is the claim: **reading a design settles neither what is in the material nor whether a mechanism fires**, and a spike moves that check in front of the assertion rather than behind it.

The condition is narrow on purpose: most artifacts assert neither, and a phase that always fires has stopped being a decision.

**It is not for design questions.** Prose consistency, citation correctness and reasoning defects are what an adversarial review is for; building tells you nothing about them, and spiking to catch them pays a build to do a reader's job.

## Running one

**One spike tests one named premise.** Write the premise down before you start — the sentence from the artifact that you are trying to falsify. That sentence is the whole bound: the spike stops the moment the premise is answered, either way.

**Where it does not resolve, abandon it.** The premise then enters the artifact as a declared assumption with the falsifier that would settle it. An abandoned spike costs a paragraph; an unbounded one becomes the work.

The bound is the question's shape rather than a clock, because a figure for a build's cost goes stale as models get faster.

**Report on the work's issue — held, fell, or abandoned.** Write what you tested, what came back, and what the artifact says because of it, before the revision that relies on it. Without the report, *ran and found nothing* and *never ran* are the same silence — and for the abandoned spike that report is the only thing a reader at the gate can weigh against a premise still declared open.

## A spike commits nothing

**No tracked file, no branch, no pull request.** Work that wants to be committed has stopped being a spike and is ordinary work, taking the ordinary flow.

That is what a spike *is*, not a rule about disposing of one — which is why it reaches no gate: convergence fires on the artifact the spike feeds, after it, and release has nothing to merge. What the spike found is reviewed at that gate inside the artifact carrying it, so what a spike avoids is the review pipeline's cost and never its coverage.

The obvious pressure is to copy working code out, and **the rule cannot detect that** — a tree where a session spiked and copied is indistinguishable from one where it wrote the code fresh. What bounds the damage is that leaked code must be written again through the ordinary flow, where it is reviewed like anything else: a leak costs duplicated effort, never unreviewed code.

Mutating a tracked file to see whether a guard fires is a spike, not an exception — and it needs the repository's files, so use a **detached** worktree (`git worktree add --detach`, which creates no branch where plain `add` does) or a throwaway clone, and delete it.

## Exploring without a premise

Sometimes the useful move is to go build something with no question formed yet, because you do not know enough to ask. **That is yours to do, unprompted, and nothing here needs to authorise it** — the named-premise pattern above is the one worth writing down, not the only one permitted.

It is left unproceduralised deliberately: its stopping condition is judgment rather than an answered question. Say what you learned in the artifact — including that you learned nothing, which is the case a silent session leaves indistinguishable from never having looked — and keep the disposal rule: exploration commits nothing either.

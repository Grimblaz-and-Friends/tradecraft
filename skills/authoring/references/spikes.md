# Spikes — testing a premise before you assert it

**Purpose:** give a session about to assert something it has not checked a named, cheap move that is bounded and cannot be mistaken for work that ships. **Audience:** any session writing a pre-implementation artifact. **Success:** a session can tell whether its artifact needs a spike, can run one and stop, and cannot leave one behind in the tree.

## When a spike fires

**Where the artifact asserts something about material nobody has enumerated, or about a mechanism nobody has executed.**

Both halves are drawn from one piece of work whose design reached revision four plus fifteen errata, on premises that were false about the material ([tradecraft#42](https://github.com/Grimblaz-and-Friends/tradecraft/issues/42)). Three of its most consequential discoveries were made while building and appear in none of its review counts: an inventory recovered seven operative rules living in the wrong blocks; a document assumed one post-freeze offset and had five; and sabotaging a script's `main()` to return zero left the first seventeen guard pins green, because the tests could not see the channel CI actually reads.

Reading finds none of these. Each is a claim about **what is in the material** or **whether the mechanism fires** — and those are the two claims a spike is for. The condition is narrow on purpose: most artifacts assert neither, and a phase that always fires has stopped being a decision.

**It is not for design questions.** Prose consistency, citation correctness and reasoning defects are what an adversarial review is for; building tells you nothing about them, and spiking to catch them pays a build to do a reader's job.

## Running one

**One spike tests one named premise.** Write the premise down before you start — the sentence from the artifact that you are trying to falsify. That sentence is the whole bound: the spike stops the moment the premise is answered, either way.

**Where it does not resolve, abandon it.** The premise then enters the artifact as a declared assumption with the falsifier that would settle it. An abandoned spike costs a paragraph; an unbounded one becomes the work.

The bound is the question's shape rather than a clock or a token budget, because a figure for a build's cost is exactly the kind that goes stale as models get faster, and a two-hour spike with no stated question is unbounded in the way that matters anyway.

**Report on the work's issue, whether the premise held or fell.** A spike that confirms its premise is worth as much as one that breaks it and leaves no other trace — without the report, *ran and found nothing* and *never ran* are the same silence. Write what you tested, what came back, and what the artifact now says because of it, before the revision that relies on it.

## A spike commits nothing

Scratch tree or throwaway worktree. **No tracked file, no branch, no pull request.** Work that wants to be committed has stopped being a spike and is ordinary work, taking the ordinary flow.

This is what the spike *is*, not a rule about what to do with it afterwards — which is why there is nothing to dispose of and no gate to reach. Convergence fires on the artifact the spike feeds, after it; release has nothing to merge. What the spike found is reviewed at that gate as part of the artifact carrying it, so what a spike avoids is the review pipeline's cost and never its coverage.

The obvious pressure is to copy working code out. **The rule cannot detect that** — a tree where a session spiked and copied is indistinguishable from one where it wrote the code fresh, and saying so is more useful than pretending otherwise. What bounds the damage is that code leaving a spike has to be written again through the ordinary flow, where it is reviewed like anything else: the cost of a leak is duplicated effort, never unreviewed code.

Mutating a tracked file to see whether a guard fires is a spike, not an exception to this — do it in a throwaway worktree and discard it.

## Exploring without a premise

Sometimes the useful move is to go build something with no question formed yet, because you do not know enough to ask. **That is yours to do, unprompted, and nothing here needs to authorise it** — the named-premise pattern above is the one worth writing down, not the only one permitted.

It is left unproceduralised deliberately. Its stopping condition is judgment rather than an answered question, so a procedure would either invent a budget that goes stale or pretend to a bound it does not have. Say what you learned in the artifact, and keep the disposal rule: exploration commits nothing either.

---
name: spikes
description: Testing a premise by running it before you assert it — a bounded, throwaway experiment that commits nothing, and the cold-seat A/B pattern for premises about what a reader does under a wording. Use when a claim in a pre-implementation artifact, a review thesis still disputed after a round, a candidate wording for a rule, or a question that arises while building turns on material you cannot survey or on behavior no run you can consult has exercised; not for design and reasoning questions, which an adversarial review settles, and not for work that ships.
---

# spikes

**Purpose:** give a session about to assert something it has not checked a named, cheap move that is bounded and cannot be mistaken for work that ships. **Audience:** any session about to commit to a premise it has not tested — writing a pre-implementation artifact, arguing a review finding, proposing a rule, or building. **Success:** a session that has never seen this file can tell, from the text alone, whether the premise in front of it needs a spike; can run one and stop; and cannot mistake a spike for work that ships.

## When a spike fires

**Where a load-bearing premise turns on material no enumeration you can consult covers, or on behavior no run you can consult has exercised** — both limbs keyed to what you can consult, because a trigger turning on what anyone has ever done is one no session can evaluate. A premise is load-bearing when something you are about to assert rests on it and changes if it is false: a claim in a pre-implementation artifact, a thesis still disputed after a round of review, the wording of a rule you are proposing. Which surface asserts it does not matter. The first limb is material you cannot survey, not material you have not surveyed — where the answer sits in files you can open, open them.

**Neither limb fires on a question whose answer you are simply going to consume.** Where nothing you write down rests on it, going and finding out is ordinary work; what makes the paradigm case a spike is not that the guard is expensive to run, but that an artifact is affirmed and handed off on the strength of it.

**Governing prose is a mechanism whose executor is a reader**, so a wording is spikeable at all: reading it settles no more than reading a design settles whether a guard fires. It is then a premise like any other, and the condition above is what decides — a wording fires the trigger where something you are about to assert rests on how a reader will take it and the reading is genuinely in doubt, never merely because the sentence is new.

**Reading a design settles neither what is in the material nor whether a mechanism fires**, and a spike moves that check in front of the assertion rather than behind it. Both limbs come from [one migration](https://github.com/Grimblaz-and-Friends/tradecraft/pull/53), where two discoveries were made only by going and looking, and a third — a guard reporting success while seeing nothing — was caught only at implementation, after the design had already asserted the guard fires.

The condition is narrow on purpose: most premises are neither, and a phase that always fires has stopped being a decision.

**It is not for design questions.** A spike arbitrates what a reader or a mechanism *does*, never whether an argument is sound: prose consistency, citation correctness and reasoning defects are what an adversarial review is for, building tells you nothing about them, and spiking to catch them pays a build to do a reader's job. Where a wording is disputed, the object of the dispute decides it — what a reader will do under the wording is a spike; where the wording belongs is not.

## Running one

**One spike tests one named premise.** Write the premise down before you start — the sentence you are trying to falsify, in the words you would have asserted it. That sentence is the whole bound: the spike stops the moment the premise is answered, either way.

**Where it does not resolve, abandon it.** The premise then enters whatever you were writing — an artifact, a finding, a proposed wording — as a declared assumption with the falsifier that would settle it. An abandoned spike costs a paragraph; an unbounded one becomes the work.

The bound is the question's shape rather than a clock, because a figure for a build's cost goes stale as models get faster.

**Report on the work's issue — held, fell, or abandoned.** Open the report `# Spike report — <premise>`, so that every run is findable by one search of the board and the practice needs no index it would have to commit something to write. Say what you tested, what came back, and what it changes in what you are writing, before the revision that relies on it. Without the report, *ran and found nothing* and *never ran* are the same silence — and for the abandoned spike that report is the only thing a reader at the gate can weigh against a premise still declared open.

## Cold-seat A/B, for a premise about what a reader does

Where the executor is a reader, the run you need is a fresh session, and it costs one dispatch. Four properties, and each is what keeps the result evidence rather than one more opinion:

- **Fresh dispatches.** A seat that has read the argument is not a cold reader, and the session that proposed the wording is the last party whose read of it is worth anything.
- **No repo history** — no issues, no decision log, no git; only the shipped material a real consumer would arrive with.
- **A realistic docket**, written out: the situations the wording has to sort. A seat asked to discuss a sentence discusses it; a seat asked to work a docket executes it.
- **Arms differing in exactly the sentence under test.** Anything else that moves between arms is a second variable, and the result stops being attributable to the wording.

**Ask what the seat would do before asking what the rule says.** The label a seat puts on a situation is the cheap measurement; what it reaches for unprompted is the one that transfers — and where the two disagree, the second is the finding. [The worked exemplar](https://github.com/Grimblaz-and-Friends/tradecraft/issues/115#issuecomment-5384143581) carries the docket, the arms, and what came back from each.

## A spike commits nothing

**Nothing committed, no branch, no pull request** — modify whatever you need to inside the throwaway; what is forbidden is leaving it. Work that wants to be committed has stopped being a spike and is ordinary work, taking the ordinary route.

That is what a spike *is*, not a rule about disposing of one — and it is why a spike needs no process of its own. Whatever approvals your repo puts on an artifact or on a merge, a spike reaches none of them: it produces neither. What it found is reviewed with the work that carries it, so a spike skips the review's cost and never its coverage.

The obvious pressure is to copy working code out, and **the rule cannot detect that** — a tree where a session spiked and copied is indistinguishable from one where it wrote the code fresh. What bounds the damage is that leaked code must be written again through the ordinary flow, where it is reviewed like anything else: a leak costs duplicated effort, never unreviewed code.

Mutating a tracked file to see whether a guard fires is a spike, not an exception — and it needs the repository's files, so use a **detached** worktree (`git worktree add --detach`, which creates no branch where plain `add` does) or a throwaway clone, and delete it.

## Exploring without a premise

Sometimes the useful move is to go build something with no question formed yet, because you do not know enough to ask. **That is yours to do, unprompted, and nothing here needs to authorise it** — the named-premise pattern above is the one worth writing down, not the only one permitted.

It is left unproceduralised deliberately: its stopping condition is judgment rather than an answered question. Say what you learned in the work it feeds — including that you learned nothing, which is the case a silent session leaves indistinguishable from never having looked — and keep the disposal rule: exploration commits nothing either.

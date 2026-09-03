---
name: spikes
description: Testing a premise by running it before you assert it — a bounded, throwaway experiment that commits nothing, and the cold-seat A/B pattern for premises about what a reader does under a wording. Use when something you are about to assert — a claim in a pre-implementation artifact, a review thesis still disputed after a round, a candidate wording for a rule, an answer you reached while building — rests on material you cannot survey or on behavior no run you can consult has exercised; not for design and reasoning questions, which an adversarial review settles, and not for work that ships.
---

# spikes

**Purpose:** give a session about to assert something it has not checked a named, cheap move that is bounded and cannot be mistaken for work that ships. **Audience:** any session about to commit to a premise it has not tested — writing a pre-implementation artifact, arguing a review finding, proposing a rule, or building. **Success:** a session that has never seen this file can tell, from the text alone, whether the premise in front of it needs a spike; can run one and stop; and cannot mistake a spike for work that ships.

## When a spike fires

**Where a load-bearing premise turns on material no enumeration you can consult covers, or on behavior no run you can consult has exercised** — both limbs keyed to what you can consult, because a trigger turning on what anyone has ever done is one no session can evaluate. A premise is load-bearing when something you are about to assert rests on it and changes if it is false: a claim in a pre-implementation artifact, a thesis still disputed after a round of review, the wording of a rule you are proposing. Which surface asserts it does not matter. The first limb is material you cannot survey, not material you have not surveyed — where the answer sits in files you can open, open them.

**Neither limb fires on a question whose answer you are simply going to consume.** Where nothing you write down rests on it, going and finding out is ordinary work; what makes the paradigm case below a spike is not that the guard is expensive to run, but that an artifact is settled and handed off on the strength of it.

**Governing prose is a mechanism whose executor is a reader**, so a wording is spikeable at all: reading it settles no more than reading a design settles whether a guard fires. It is then a premise like any other, and the condition above is what decides — a wording fires the trigger where something you are about to assert rests on how a reader will take it and the reading is genuinely in doubt, never merely because the sentence is new.

**Reading a design settles neither what is in the material nor whether a mechanism fires**, and a spike moves that check in front of the assertion rather than behind it. Both limbs come from [one migration](https://github.com/Grimblaz-and-Friends/tradecraft/pull/53), where two discoveries were made only by going and looking, and a third — a guard reporting success while seeing nothing — was caught by a review only at implementation, after the design had already asserted the guard fires.

The condition is narrow on purpose: most premises turn on neither, and a phase that always fires has stopped being a decision.

**It is not for design questions.** A spike arbitrates what a reader or a mechanism *does*, never whether an argument is sound: prose consistency, citation correctness and reasoning defects are what an adversarial review is for, building tells you nothing about them, and spiking to catch them pays a build to do a reader's job. Where a wording is disputed, the object of the dispute decides it — what a reader will do under the wording is a spike; where the wording belongs is not.

## Running one

**One spike tests one named premise.** Write the premise down before you start — the sentence you are trying to falsify, in the words you would have asserted it. That sentence is the whole bound: the spike stops the moment the premise is answered, either way.

**Where it does not resolve, abandon it.** The premise then enters whatever you were writing — an artifact, a finding, a proposed wording — as a declared assumption with the falsifier that would settle it. An abandoned spike costs a paragraph; an unbounded one becomes the work. [D-173]

The bound is the question's shape rather than a clock, because a figure for a build's cost goes stale as models get faster.

**Report on the work's issue, filing one if none exists — held, fell, or abandoned.** Open the report `# Spike report — <the premise, named>`, so one search of the issue tracker for `Spike report` finds every run and the practice needs no index it would have to commit something to write. Say what you tested, what came back, and what it changes in what you are writing, before the revision that relies on it; where you dispatched seats, say where each was stopped and what it was told it could not leave, which is the one durable trace a dispatch leaves. Without the report, *ran and found nothing* and *never ran* are the same silence — and for the abandoned spike that report is the only thing whoever approves the work can weigh against a premise still declared open.

## Cold-seat A/B, for a premise about what a reader does

Where the executor is a reader, the run you need is a fresh session. Six properties, and each is what keeps the result evidence rather than one more opinion:

- **Fresh dispatches.** A seat that has read the argument is not a cold reader, and the session that proposed the wording is the last party whose read of it is worth anything.
- **No repo history** — no issues, no decision log, no git; only the shipped material a real consumer would arrive with.
- **A realistic docket**, written out: the situations the wording has to sort. A seat asked to discuss a sentence discusses it; a seat asked to work a docket executes it. **Where the rule under test opens only for a particular actor, the docket has to put a seat in that position**: a docket no seat can enter through the rule's own door tests the rule's absence, and both arms then agree for the reason that the rule never fired. **Each item is a near-miss**: the text under test has to be a plausible wrong answer to it, never the obvious one. And **where that text is an exclusion, no item may be a job the excluding cell's own positive trigger names** — such an item arrives at that cell's door, every seat opens the cell in both arms, and a clause that works reads dead.
- **A planted control among the items.** One item certifies the run instead of measuring anything: material invented for the run, built to the same near-miss shape as the real items and never landed, so that a seat reaching for it shows the run could read a signal of that shape at all. A control pitched easier than the measurements passes while they stay blind. **Where it rides follows the run's shape** — where the ablated arm strips a whole class of text at once the plant goes with them and rides in the intact arm alone; where only the text under test is removed it rides unchanged in both arms, which is what keeps the arms differing in exactly the sentence under test.
- **Arms differing in exactly the sentence under test.** Anything else that moves between arms is a second variable, and the result stops being attributable to the wording.
- **A docket that stops where the measurement is taken.** Ask for the seat's plan before it executes — every step, its reason, and the text it relied on — and stop it there. What you are measuring sits inside that plan among everything else, so the stop leads nothing where naming the step to stop at would, and the datum arrives in minutes rather than in the hours a real job takes ([#305](https://github.com/Grimblaz-and-Friends/tradecraft/issues/305)). It reaches a decision the seat takes before it acts, which is a stated intention rather than conduct; where the datum is visible only in what a run does, the run continues.

**Every bound in this cell is yours to impose on the seat, because it cannot infer one.** It does not know it is in a spike — that is the point — so the stop above and the disposal below reach it only by being written into its dispatch, along with the one bound it has no other source for: that it dispatches nothing of its own. A seat handed an ordinary job does what the repository says that job takes, recursively, and [five commissioned to settle one question ran the practice's whole flow](https://github.com/Grimblaz-and-Friends/tradecraft/issues/305), one of them dispatching its own.

**Ask what the seat would do before asking what the rule says.** The label a seat puts on a situation is the cheap measurement; what it reaches for unprompted is the one that transfers — and where the two disagree, the second is the finding. **Then force a verdict on every candidate, so that a silence is evidence.** A seat asked only what it would do never mentions what it declined, and on a near-miss a correct route needs no mention of the text under test at all. The forced walk comes second for the reason just given — asked first it hands the seat the label and contaminates the unprompted answer — and its compliance certifies nothing on its own, since a walk requiring a reasoned verdict on everything cannot return the negative. [The worked exemplar](https://github.com/Grimblaz-and-Friends/tradecraft/issues/115#issuecomment-5384143581) carries the docket, the arms, and what came back from each.

**Read the plant before you read the measurement.** Where no seat cited the plant in the intact arm the run is **void** and licenses nothing, whatever the other items returned: it has not shown it could detect a signal of that shape, so its silences say nothing. The control certifies the run, not the item — an item no seat treated as a live candidate is uninformative rather than null, and is rebuilt, which is the docket-door bullet above.

**Where the run's output would be the removal of the text under test, it owes more than a valid run: `references/licensing-a-deletion.md`** — what a null has to look like before text may go, and what counts as a seat having cited it. Load it when a deletion is what the run is for, and not otherwise.

## A spike commits nothing

**Nothing committed, no branch, no pull request** — modify whatever you need to inside the throwaway; what is forbidden is leaving it. Work that wants to be committed has stopped being a spike and is ordinary work, taking the ordinary route.

That is what a spike *is*, not a rule about disposing of one — and it is why a spike needs no process of its own. Whatever approvals your repo puts on an artifact or on a merge, a spike reaches none of them: it produces neither. What it found is reviewed with the work that carries it, wherever that work is itself reviewed, so a spike skips the review's cost and never its coverage. **Where the carrier is a ruling rather than an artifact** — a review's own output is posted, not reviewed — the report is posted with it, and the coverage falls where the result is acted on: the change it drives is reviewed like any other change, and where it drives none the report is the whole of what covers it.

The obvious pressure is to copy working code out, and **the rule cannot detect that** — a tree where a session spiked and copied is indistinguishable from one where it wrote the code fresh. What bounds the damage is that leaked code must be written again through the ordinary flow, where it is reviewed like anything else: a leak costs duplicated effort, never unreviewed code.

Mutating a tracked file to see whether a guard fires is a spike, not an exception — and it needs the repository's files, so use a **detached** worktree (`git worktree add --detach`, which creates no branch where plain `add` does) or a throwaway clone, and delete it.

## Exploring without a premise

Sometimes the useful move is to go build something with no question formed yet, because you do not know enough to ask. **That is yours to do, unprompted, and nothing here needs to authorise it** — the named-premise pattern above is the one worth writing down, not the only one permitted.

It is left unproceduralised deliberately: its stopping condition is judgment rather than an answered question. Say what you learned on the work's issue — including that you learned nothing, which is the case a silent session leaves indistinguishable from never having looked — and keep the disposal rule: exploration commits nothing either.

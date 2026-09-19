---
name: spikes
description: Testing a premise by running it before you assert it — a bounded, throwaway experiment that commits nothing, and the cold-seat A/B pattern for premises about what a reader does under a wording. Use when something you are about to assert — a claim in a pre-implementation artifact, a review thesis still disputed after a round, a candidate wording for a rule, an answer you reached while building — rests on material you cannot survey or on behavior no run you can consult has exercised; not for design and reasoning questions, which an adversarial review settles, and not for work that ships.
---

# spikes

**Purpose:** give a session about to assert something it has not checked a named, cheap move that is bounded and cannot be mistaken for work that ships. **Audience:** any session about to commit to a premise it has not tested — writing a pre-implementation artifact, arguing a review finding, proposing a rule, or building. **Success:** a session that has never seen this cell can tell, from the text alone, whether the premise in front of it needs a spike; can run one and stop; and cannot mistake a spike for work that ships.

## Where this cell's depth lives

- **Running a spike whose premise is about what a reader does under a wording — designing the arms, building the docket and the planted control, or reading what came back** → `references/cold-seat-ab.md`: the six properties that keep the result evidence rather than opinion, where the planted control rides in each run shape, how it is read before a silence, and the route into scoring.
- **Scoring a cold-seat A/B's planted control, or the run's output would be the removal of the text under test** → `references/licensing-a-deletion.md`: the record search, the citation test, which disposition a scored run reaches, and what a substitution measures.
- **Writing any spike's report** → `references/spike-report-template.md`: the fields for its premise, run, return, effect and disposition, including the reader-run controls and the non-premise forms.
- **Writing the dispatch for a cold-seat A/B seat** → `references/ab-dispatch-template.md`: the arm's material, docket, filled stop, ordered questions, bounds and return.

## When a spike fires

**Where a load-bearing premise turns on material no enumeration you can consult covers, or on behavior no run you can consult has exercised** — both limbs keyed to what you can consult, because a trigger turning on what anyone has ever done is one no session can evaluate. A premise is load-bearing when something you are about to assert rests on it and changes if it is false: a claim in a pre-implementation artifact, a thesis still disputed after a round of review, the wording of a rule you are proposing. The first limb is material you cannot survey, not material you have not surveyed — where the answer sits in files you can open, open them.

**Neither limb fires on a question whose answer you are simply going to consume.** Where nothing you write down rests on it, going and finding out is ordinary work; what makes the paradigm case below a spike is not that the guard is expensive to run, but that an artifact is settled and handed off on the strength of it.

**Governing prose is a mechanism whose executor is a reader**, so a wording is spikeable at all: reading it settles no more than reading a design settles whether a guard fires. It is then a premise like any other, and the condition above is what decides — a wording fires the trigger where something you are about to assert rests on how a reader will take it and the reading is genuinely in doubt, never merely because the sentence is new.

**Reading a design settles neither what is in the material nor whether a mechanism fires**, and a spike moves that check in front of the assertion rather than behind it. Both limbs come from [one migration](https://github.com/Grimblaz-and-Friends/tradecraft/pull/53), where two discoveries were made only by going and looking, and a third — a guard reporting success while seeing nothing — was caught by a review only at implementation, after the design had already asserted the guard fires.

**It is not for design questions.** A spike arbitrates what a reader or a mechanism *does*, never whether an argument is sound: spiking to catch design and reasoning questions pays a build to do a reader's job. Where a wording is disputed, the object of the dispute decides it — what a reader will do under the wording is a spike; where the wording belongs is not.

## Running one

**One spike tests one named premise.** Write the premise down before you start — the sentence you are trying to falsify, in the words you would have asserted it. That sentence is the whole bound: the spike stops the moment the premise is answered, either way.

**Where it does not resolve, abandon it.** The premise then enters whatever you were writing — an artifact, a finding, a proposed wording — as a declared assumption with the falsifier that would settle it. An abandoned spike costs a paragraph; an unbounded one becomes the work.

**Report on the work's issue, filing one if none exists, before the revision that relies on it.** Copy `references/spike-report-template.md` whole. Its shared heading makes every run findable with one issue-tracker search, without an index this instrument cannot commit to maintain. Without the report, *ran and found nothing* and *never ran* are the same silence; for an abandoned spike it is the only thing whoever approves the work can weigh against a premise still declared open.

**Where the premise is about what a reader does under a wording, the run is a cold-seat A/B: `references/cold-seat-ab.md`** — its six properties, plant reading and scoring route, with `references/ab-dispatch-template.md` for each seat's dispatch.

## A spike commits nothing

**Nothing committed, no branch, no pull request** — modify whatever you need to inside the throwaway; what is forbidden is leaving it. Work that wants to be committed has stopped being a spike and is ordinary work, taking the ordinary route.

That is what a spike *is*, not a rule about disposing of one — and it is why a spike needs no process of its own. Whatever approvals your repo puts on an artifact or on a merge, a spike reaches none of them: it produces neither. What it found is reviewed with the work that carries it, wherever that work is itself reviewed, so a spike skips the review's cost and never its coverage. **Where the carrier is not itself reviewed — a review's own ruling — coverage falls where the result is acted on.**

The obvious pressure is to copy working code out, and **the rule cannot detect that** — a tree where a session spiked and copied is indistinguishable from one where it wrote the code fresh. What bounds the damage is that leaked code must be written again through the ordinary flow, where it is reviewed like anything else: a leak costs duplicated effort, never unreviewed code.

Mutating a tracked file to see whether a guard fires is a spike, not an exception — and it needs the repository's files, so use a **detached** worktree (`git worktree add --detach`, which creates no branch where plain `add` does) or a throwaway clone, and delete it.

## Exploring without a premise

Sometimes the useful move is to go build something with no question formed yet, because you do not know enough to ask. **That is yours to do, unprompted, and nothing here needs to authorise it** — the named-premise pattern above is the one worth writing down, not the only one permitted.

It is left unproceduralised deliberately: its stopping condition is judgment rather than an answered question. Say what you learned on the work's issue — including that you learned nothing — and keep the disposal rule: exploration commits nothing either.

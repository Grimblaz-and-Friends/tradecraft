# Putting a decision to the owner

**Loaded when** you are putting a decision to the owner — composing the argued form it arrives in, or handing work back to them after time away — or putting one where they are not in the room to read it: writing the ask block, marking what carries it, or reading what waits.

**What is theirs arrives argued:** the live options, each with its pros and cons, then the recommendation among them — above the brief, which sits last, immediately before the ask it briefs. Where exactly one option is live, say so and say what was rejected and why — the reasoning is what makes that case informative, and a fabricated second option under-informs worse than none, because it presents a search that did not happen.

**A shortlist raised out of work that has been filed and not yet decided on takes that same form**, and its answer is itself the decision that the work is worth doing rather than a step toward one.

**Three habits qualify every ask, whether or not the work opened a design sitting.** A question carries the session's own guess at the answer, so the owner corrects rather than composes — made to supply from scratch what the session could have guessed, they are spending their attention on typing. A recommendation carries the strongest case against itself, not only the cons of the options it beat: [the case against a recommendation travels with it](https://github.com/Grimblaz-and-Friends/tradecraft/issues/402). And a ruling of theirs is recorded in their own words, or in the one restatement of those words they approved — **kept exactly from then on and never reworded again**, since that is the sentence a later session is held to. [D-414]

**An ask is anything a session needs from the owner that the session may not settle** — a brief put for affirmation, an argued ask ruled at release, a shortlist raised out of work not yet decided on, an item raised out of that work unasked because it crossed a line its policy draws, a handback after time away. The occasions are not a closed list; what makes something an ask is that **the matter is not the session's to close**, whether or not the work waits on the answer. **Waiting is not the test and never was**: an argued ask ruled at release has the work proceeding on the recommendation, and it is an ask.

**An ask the owner is not in the room for is put by posting an ask block and marking what carries it.** The block is a comment on the issue or pull request the ask concerns, and carries three lines:

- **What is being asked** — the decision, in one sentence.
- **Where the work stands** — enough that the question makes sense without the owner reconstructing the work first.
- **What an answer unblocks** — what proceeds once it is answered and what does not, so the owner sees which answer frees the most work.

**The mark is a label on what carries the block — `awaiting-owner`, unless the adopting repository's own doctrine names another.** **Create it before the first ask**; applying a label that does not exist is refused.

**An ask that is not marked is not put, and nothing that later happens to what carries it rules on it.** A question written into a pull request body and marked nowhere is not answered by the merge; it was never asked.

**An ask put to the owner in conversation is put, and carries no mark**, the conversation being the engagement surface. The mark is for an ask they are not in the room for.

**One query is the whole of what waits, and it is scoped to the repository.** Unscoped, the label is a common one and the search returns other people's work.

```bash
gh search issues --repo <owner>/<repo> --label <the mark> --state open --include-prs --limit 100
```

**An empty result and a wrong label name are the same output** — no rows, exit zero — so a query that has never returned anything is worth checking against the repository's label set before it is read as *nothing waits*. **The limit is not decoration**: the default is thirty and a truncated page is indistinguishable from a complete one, so a result that comes back at whatever limit was asked for is a short read rather than the whole of what waits.

**The mark comes off when the ask is answered**, by the session that reads the answer. A closed issue or a merged pull request leaves the set on its own, so nothing has to be swept.

**Where the owner cannot be reached at all, the waiting rule (`../references/waiting.md`) governs**, and it decides whether the ask block and its mark above apply — read it before putting an ask into an absence rather than after.
